import asyncio
import io
import unicodedata
from typing import Callable, Dict, Optional

import discord
from redbot.core import Config, commands
from redbot.core.bot import Red

from .render import render_burger

# (clé, nom affiché, emoji)
INGREDIENTS = [
    ("pain", "Pain burger (brioché)", "🍞"),
    ("steak", "Steak haché à l'oignon", "🥩"),
    ("cheddar", "Cheddar", "🧀"),
    ("oignon", "Oignons frits", "🧅"),
    ("bacon", "Bacon", "🥓"),
    ("salade", "Salade", "🥬"),
    ("cornichon", "Cornichons", "🥒"),
    ("sauceburger", "Sauce burger", "🥫"),
    ("saucebbq", "Sauce BBQ", "🍖"),
]
LABEL = {k: l for k, l, _ in INGREDIENTS}
EMOJI = {k: e for k, _, e in INGREDIENTS}
NO_PING = discord.AllowedMentions.none()
COLOR = 0xF2A516
TTL = 5  # secondes avant que les messages privés du bot disparaissent
MENU_TTL = 30  # menu « tu es sur … » sans action
MAX_TAKERS = 10  # personnes max sur un même ingrédient
STICKY_DELAY = 4  # secondes de calme avant de redescendre le tableau en bas du salon (tant qu'il n'est pas plein)


class Nope(Exception):
    """Action refusée, message affiché tel quel à l'utilisateur."""


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower().strip())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def find_key(text: str) -> str:
    n = _norm(text)
    if not n:
        raise Nope("Précise un ingrédient.")
    exact = [k for k, l, _ in INGREDIENTS if n in (k, _norm(l))]
    if exact:
        return exact[0]
    hits = [k for k, l, _ in INGREDIENTS if k.startswith(n) or n in _norm(l)]
    if len(hits) == 1:
        return hits[0]
    choix = ", ".join(k for k, _, _ in INGREDIENTS)
    raise Nope(f"Ingrédient « {text} » introuvable. Choix : {choix}")


def empty_item() -> dict:
    return {"takers": []}


def upgrade_item(it: Optional[dict]) -> dict:
    """Passe l'ancien format {who, qty, done} au format {takers: [{who, qty}]}."""
    if not it:
        return empty_item()
    if "takers" in it:
        return it
    if it.get("who"):
        return {"takers": [{"who": it["who"], "qty": it.get("qty", "")}]}
    return empty_item()


def normalize_items(raw: Optional[dict]) -> dict:
    raw = dict(raw or {})
    if "sauce" in raw and "sauceburger" not in raw:  # ancienne ligne unique « Sauces »
        raw["sauceburger"] = raw["sauce"]
    return {k: upgrade_item(raw.get(k)) for k, _, _ in INGREDIENTS}


def is_full(items: dict) -> bool:
    return all(it["takers"] for it in items.values())


def find_taker(it: dict, user_id: int) -> Optional[dict]:
    return next((t for t in it["takers"] if t["who"] == user_id), None)


def fmt_takers(it: dict, skip: Optional[int] = None) -> str:
    return ", ".join(f"<@{t['who']}>" + (f" · {t['qty']}" if t["qty"] else "")
                     for t in it["takers"] if t["who"] != skip)


class BandoBurger(commands.Cog):
    """BandoBurger : qui ramène quoi pour le burger, avec le burger qui se monte en direct.

    Un tableau par salon : un `burger start` dans un autre salon en crée un nouveau.
    """

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=0xB4D0B0B6, force_registration=True)
        # ancien format (un seul tableau par serveur), gardé pour la migration
        self.config.register_guild(channel_id=None, message_id=None, items={})
        # un tableau par salon
        self.config.register_channel(message_id=None, owner=None, items={}, sticky=True)
        self._locks: Dict[int, asyncio.Lock] = {}
        self._sticky_tasks: Dict[int, asyncio.Task] = {}

    async def cog_unload(self):
        for task in self._sticky_tasks.values():
            task.cancel()

    async def cog_load(self):
        await self._migrate_guild_panels()
        # vue persistante : les boutons des tableaux existants remarchent après un redémarrage
        self.bot.add_view(PanelView(self))

    async def _migrate_guild_panels(self):
        for gid, data in (await self.config.all_guilds()).items():
            cid = data.get("channel_id")
            if cid and not await self.config.channel_from_id(cid).message_id():
                await self.config.channel_from_id(cid).set(
                    {"message_id": data.get("message_id"), "owner": None, "items": data.get("items") or {},
                     "sticky": True})
            await self.config.guild_from_id(gid).clear()

    async def red_delete_data_for_user(self, *, requester, user_id: int):
        for cid, data in (await self.config.all_channels()).items():
            conf = self.config.channel_from_id(cid)
            items = normalize_items(data.get("items"))
            changed = False
            for it in items.values():
                before = len(it["takers"])
                it["takers"] = [t for t in it["takers"] if t["who"] != user_id]
                changed |= len(it["takers"]) != before
            if changed:
                await conf.items.set(items)
            if data.get("owner") == user_id:
                await conf.owner.set(None)

    # ---------- état ----------

    def _lock(self, channel_id: int) -> asyncio.Lock:
        return self._locks.setdefault(channel_id, asyncio.Lock())

    def conf(self, channel_id: int):
        return self.config.channel_from_id(channel_id)

    async def get_items(self, channel_id: int) -> dict:
        return normalize_items(await self.conf(channel_id).items())

    async def is_mod(self, member: discord.Member) -> bool:
        return await self.bot.is_mod(member) or member.guild_permissions.manage_messages

    async def can_manage(self, member: discord.Member, channel_id: int) -> bool:
        """Celui qui a lancé le tableau, ou un modo."""
        return member.id == await self.conf(channel_id).owner() or await self.is_mod(member)

    async def mutate(self, guild: discord.Guild, channel_id: int,
                     fn: Callable[[dict], Optional[str]]) -> Optional[str]:
        """Applique fn aux items du salon sous verrou, sauvegarde, met à jour le tableau."""
        async with self._lock(channel_id):
            if not await self.conf(channel_id).message_id():
                raise Nope("Il n'y a pas de tableau en cours dans ce salon. Lance `burger start`.")
            items = await self.get_items(channel_id)
            result = fn(items)
            await self.conf(channel_id).items.set(items)
            await self.refresh(guild, channel_id, items)
        return result

    # ---------- rendu ----------

    def build_embed(self, items: dict) -> discord.Embed:
        lines = []
        for k, label, emo in INGREDIENTS:
            it = items[k]
            if it["takers"]:
                lines.append(f"{emo} **{label}** — {fmt_takers(it)}")
            else:
                lines.append(f"{emo} **{label}** — *personne pour l'instant*")
        taken = sum(1 for it in items.values() if it["takers"])
        total = len(INGREDIENTS)
        title = "🍔 BandoBurger — burger complet !" if taken == total else "🍔 BandoBurger — qui prend quoi ?"
        embed = discord.Embed(title=title, description="\n".join(lines), color=COLOR)
        embed.set_footer(text=f"{taken}/{total} pris"
                              " · clique sur un ingrédient pour le prendre (à plusieurs, c'est possible)")
        embed.set_thumbnail(url="attachment://burger.png")  # petit, à droite de la liste
        return embed

    async def build_file(self, items: dict) -> discord.File:
        state = {k: ("taken" if it["takers"] else "free") for k, it in items.items()}
        png = await asyncio.get_running_loop().run_in_executor(None, render_burger, state)
        return discord.File(io.BytesIO(png), filename="burger.png")

    async def refresh(self, guild: discord.Guild, channel_id: int, items: Optional[dict] = None) -> bool:
        conf = self.conf(channel_id)
        mid = await conf.message_id()
        channel = guild.get_channel_or_thread(channel_id)
        if not channel or not mid:
            return False
        if items is None:
            items = await self.get_items(channel_id)
        try:
            await channel.get_partial_message(mid).edit(
                embed=self.build_embed(items),
                attachments=[await self.build_file(items)],
                view=PanelView(self, items),
                allowed_mentions=NO_PING,
            )
        except discord.NotFound:
            await conf.message_id.set(None)
            return False
        except discord.HTTPException:
            return False
        return True

    # ---------- tableau toujours en bas du salon ----------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None:
            return
        cid = message.channel.id
        # le tableau lui-même (message du bot avec des boutons) ne déclenche rien
        if message.author.id == self.bot.user.id and message.components:
            return
        conf = self.conf(cid)
        mid = await conf.message_id()
        if not mid or message.id == mid or not await conf.sticky():
            return
        if is_full(await self.get_items(cid)):
            return  # burger complet : le tableau ne redescend plus
        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return
        old = self._sticky_tasks.get(cid)
        if old and not old.done():
            old.cancel()  # on attend que ça se calme avant de reposter
        self._sticky_tasks[cid] = asyncio.create_task(self._repost_later(message.channel))

    async def _repost_later(self, channel):
        try:
            await asyncio.sleep(STICKY_DELAY)
            await self.repost(channel)
        except asyncio.CancelledError:
            pass

    async def repost(self, channel) -> None:
        """Reposte le tableau en dernier message du salon et supprime l'ancien."""
        cid = channel.id
        conf = self.conf(cid)
        async with self._lock(cid):
            mid = await conf.message_id()
            if not mid or channel.last_message_id == mid:
                return
            items = await self.get_items(cid)
            if is_full(items):
                return
            try:
                new = await channel.send(embed=self.build_embed(items), file=await self.build_file(items),
                                         view=PanelView(self, items), allowed_mentions=NO_PING)
            except discord.HTTPException:
                return
            await conf.message_id.set(new.id)
            try:
                await channel.get_partial_message(mid).delete()
            except discord.HTTPException:
                pass

    # ---------- actions partagées (boutons + commandes) ----------

    def act_take(self, key: str, member: discord.Member, qty: Optional[str] = None):
        """Ajoute member sur l'ingrédient (ou met à jour sa quantité s'il y est déjà)."""
        def fn(items):
            it = items[key]
            me = find_taker(it, member.id)
            if me:
                if qty is None:
                    raise Nope(f"{member.mention} est déjà sur **{LABEL[key]}**.")
                me["qty"] = qty.strip()[:60]
                return f"{EMOJI[key]} Quantité de {member.mention} pour **{LABEL[key]}** : {me['qty'] or 'retirée'}"
            if len(it["takers"]) >= MAX_TAKERS:
                raise Nope(f"Déjà {MAX_TAKERS} personnes sur **{LABEL[key]}**, ça suffit 😄")
            others = fmt_takers(it)
            it["takers"].append({"who": member.id, "qty": (qty or "").strip()[:60]})
            return f"{EMOJI[key]} **{LABEL[key]}** → {member.mention}" + (f" (avec {others})" if others else "")
        return fn

    def act_release(self, key: str, member: discord.Member):
        def fn(items):
            it = items[key]
            if not find_taker(it, member.id):
                raise Nope(f"{member.mention} n'est pas sur **{LABEL[key]}**.")
            it["takers"] = [t for t in it["takers"] if t["who"] != member.id]
            rest = fmt_takers(it)
            return (f"{EMOJI[key]} {member.mention} ne prend plus **{LABEL[key]}**. "
                    + (f"Reste : {rest}" if rest else "Plus personne dessus."))
        return fn

    def act_qty(self, key: str, member: discord.Member, qty: str):
        def fn(items):
            me = find_taker(items[key], member.id)
            if not me:
                raise Nope(f"Tu n'es pas sur **{LABEL[key]}**. Prends-le d'abord.")
            me["qty"] = qty.strip()[:60]
            return f"{EMOJI[key]} Ta quantité pour **{LABEL[key]}** : {me['qty'] or 'retirée'}"
        return fn

    # ---------- commandes ----------

    async def _run(self, ctx: commands.Context, fn):
        try:
            msg = await self.mutate(ctx.guild, ctx.channel.id, fn)
        except Nope as e:
            return await ctx.send(str(e).replace("`burger", f"`{ctx.clean_prefix}burger"),
                                  ephemeral=True, allowed_mentions=NO_PING)
        await ctx.send(msg, allowed_mentions=NO_PING)

    async def _ing_autocomplete(self, interaction: discord.Interaction, current: str):
        n = _norm(current)
        return [
            discord.app_commands.Choice(name=f"{e} {l}", value=k)
            for k, l, e in INGREDIENTS
            if not n or n in _norm(l) or k.startswith(n)
        ][:25]

    @commands.hybrid_group(name="burger", fallback="tableau", invoke_without_command=True)
    @commands.guild_only()
    async def bando(self, ctx: commands.Context):
        """Affiche le tableau BandoBurger de ce salon (sans boutons)."""
        if not await self.conf(ctx.channel.id).message_id():
            return await ctx.send(f"Pas de tableau en cours ici. Lance `{ctx.clean_prefix}burger start`.",
                                  ephemeral=True)
        items = await self.get_items(ctx.channel.id)
        await ctx.send(embed=self.build_embed(items), file=await self.build_file(items),
                       allowed_mentions=NO_PING)

    @bando.command(name="start")
    @commands.guild_only()
    async def bando_start(self, ctx: commands.Context, vider: bool = False):
        """Lance un tableau dans ce salon (ouvert à tout le monde).

        Un tableau par salon : les tableaux des autres salons ne sont pas touchés.
        S'il y en a déjà un ici, il est reposté en bas avec la même répartition.
        `vider` : True pour repartir à zéro (celui qui a lancé le tableau ou un modo).
        """
        cid = ctx.channel.id
        conf = self.conf(cid)
        async with self._lock(cid):
            old_mid = await conf.message_id()
            if old_mid and vider and not await self.can_manage(ctx.author, cid):
                return await ctx.send("Seul celui qui a lancé ce tableau, ou un modo, peut le vider.",
                                      ephemeral=True)
            if old_mid:
                try:
                    await ctx.channel.get_partial_message(old_mid).edit(view=None)
                except discord.HTTPException:
                    pass
            if not old_mid or vider:
                await conf.items.set({})
                await conf.owner.set(ctx.author.id)
            items = await self.get_items(cid)
            msg = await ctx.send(embed=self.build_embed(items), file=await self.build_file(items),
                                 view=PanelView(self, items), allowed_mentions=NO_PING)
            await conf.message_id.set(msg.id)

    @bando.command(name="stop")
    @commands.guild_only()
    async def bando_stop(self, ctx: commands.Context):
        """Clôture le tableau de ce salon (celui qui l'a lancé ou un modo). Le message reste visible."""
        cid = ctx.channel.id
        conf = self.conf(cid)
        async with self._lock(cid):
            mid = await conf.message_id()
            if not mid:
                return await ctx.send("Pas de tableau en cours ici.", ephemeral=True)
            if not await self.can_manage(ctx.author, cid):
                return await ctx.send("Seul celui qui a lancé ce tableau, ou un modo, peut le clôturer.",
                                      ephemeral=True)
            items = await self.get_items(cid)
            embed = self.build_embed(items)
            embed.title = "🍔 BandoBurger — clôturé"
            embed.set_footer(text="Tableau clôturé")
            try:
                await ctx.channel.get_partial_message(mid).edit(embed=embed, view=None, allowed_mentions=NO_PING)
            except discord.HTTPException:
                pass
            await conf.clear()
        await ctx.send("🔒 Tableau clôturé.")

    @bando.command(name="actifs")
    @commands.guild_only()
    async def bando_actifs(self, ctx: commands.Context):
        """Liste les tableaux en cours sur le serveur."""
        lines = []
        for cid, data in (await self.config.all_channels()).items():
            ch = ctx.guild.get_channel_or_thread(cid)
            if not ch or not data.get("message_id"):
                continue
            items = normalize_items(data.get("items"))
            taken = sum(1 for it in items.values() if it["takers"])
            lines.append(f"{ch.mention} — {taken}/{len(INGREDIENTS)} pris")
        await ctx.send("\n".join(lines) or "Aucun tableau en cours.", allowed_mentions=NO_PING)

    @bando.command(name="collant")
    @commands.guild_only()
    async def bando_collant(self, ctx: commands.Context):
        """(Organisateur ou modo) Active / désactive le tableau qui redescend en bas du salon tant qu'il n'est pas complet."""
        cid = ctx.channel.id
        if not await self.conf(cid).message_id():
            return await ctx.send("Pas de tableau en cours ici.", ephemeral=True)
        if not await self.can_manage(ctx.author, cid):
            return await ctx.send("Seuls l'organisateur du tableau ou un modo peuvent changer ça.", ephemeral=True)
        now = not await self.conf(cid).sticky()
        await self.conf(cid).sticky.set(now)
        await ctx.send("📌 Le tableau redescendra en bas du salon tant qu'il n'est pas complet." if now
                       else "Le tableau ne redescend plus tout seul.")

    @bando.command(name="prend")
    @commands.guild_only()
    async def bando_prend(self, ctx: commands.Context, ingredient: str, *, quantite: Optional[str] = None):
        """Tu prends un ingrédient, seul ou à plusieurs. Ex : `burger prend steak 1 paquet`

        Si tu es déjà dessus, ça met juste à jour ta quantité.
        """
        try:
            key = find_key(ingredient)
        except Nope as e:
            return await ctx.send(str(e), ephemeral=True)
        await self._run(ctx, self.act_take(key, ctx.author, quantite))

    @bando.command(name="lache")
    @commands.guild_only()
    async def bando_lache(self, ctx: commands.Context, ingredient: str, membre: Optional[discord.Member] = None):
        """Tu ne prends plus cet ingrédient. L'organisateur ou un modo peut retirer quelqu'un : `burger lache steak @pseudo`"""
        try:
            key = find_key(ingredient)
        except Nope as e:
            return await ctx.send(str(e), ephemeral=True)
        target = membre or ctx.author
        if target != ctx.author and not await self.can_manage(ctx.author, ctx.channel.id):
            return await ctx.send("Seuls l'organisateur du tableau ou un modo peuvent retirer quelqu'un.",
                                  ephemeral=True)
        await self._run(ctx, self.act_release(key, target))

    @bando.command(name="quantite")
    @commands.guild_only()
    async def bando_quantite(self, ctx: commands.Context, ingredient: str, *, quantite: str = ""):
        """Change ta quantité sur un ingrédient. Ex : `burger quantite steak 8`"""
        try:
            key = find_key(ingredient)
        except Nope as e:
            return await ctx.send(str(e), ephemeral=True)
        await self._run(ctx, self.act_qty(key, ctx.author, quantite))

    @bando.command(name="assigne")
    @commands.guild_only()
    async def bando_assigne(self, ctx: commands.Context, ingredient: str, membre: discord.Member,
                            *, quantite: Optional[str] = None):
        """(Organisateur ou modo) Ajoute quelqu'un sur un ingrédient, ou change sa quantité."""
        try:
            key = find_key(ingredient)
        except Nope as e:
            return await ctx.send(str(e), ephemeral=True)
        if not await self.can_manage(ctx.author, ctx.channel.id):
            return await ctx.send("Seuls l'organisateur du tableau ou un modo peuvent assigner.", ephemeral=True)
        await self._run(ctx, self.act_take(key, membre, quantite))

    @bando.command(name="reset")
    @commands.guild_only()
    async def bando_reset(self, ctx: commands.Context):
        """(Organisateur ou modo) Vide la répartition du tableau de ce salon."""
        if not await self.can_manage(ctx.author, ctx.channel.id):
            return await ctx.send("Seuls l'organisateur du tableau ou un modo peuvent le vider.", ephemeral=True)

        def fn(items):
            for k in items:
                items[k] = empty_item()
            return "🧹 Tableau vidé."
        await self._run(ctx, fn)

    for _cmd in (bando_prend, bando_lache, bando_quantite, bando_assigne):
        _cmd.autocomplete("ingredient")(_ing_autocomplete)
    del _cmd


# ---------- interface Discord ----------


class PanelView(discord.ui.View):
    """Les boutons d'un tableau. Persistante (timeout=None, custom_id fixes) :
    le salon du clic dit de quel tableau il s'agit."""

    def __init__(self, cog: BandoBurger, items: Optional[dict] = None):
        super().__init__(timeout=None)
        self.cog = cog
        for i, (key, label, emo) in enumerate(INGREDIENTS):
            it = upgrade_item((items or {}).get(key))
            n = len(it["takers"])
            style = discord.ButtonStyle.primary if n else discord.ButtonStyle.secondary
            short = label.split(" (")[0] + (f" ×{n}" if n > 1 else "")
            btn = discord.ui.Button(label=short, emoji=emo, style=style,
                                    custom_id=f"bandoburger:{key}", row=i // 4)
            btn.callback = self._make_callback(key)
            self.add_item(btn)

    def _make_callback(self, key: str):
        async def callback(interaction: discord.Interaction):
            await self.on_ingredient(interaction, key)
        return callback

    async def on_ingredient(self, interaction: discord.Interaction, key: str):
        cog, guild, user, cid = self.cog, interaction.guild, interaction.user, interaction.channel_id
        if guild is None:
            return
        if interaction.message and interaction.message.id != await cog.conf(cid).message_id():
            return await interaction.response.send_message(
                "Ce tableau n'est plus actif, utilise le plus récent.", ephemeral=True, delete_after=TTL)

        it = (await cog.get_items(cid))[key]
        if find_taker(it, user.id):
            return await interaction.response.send_message(
                f"{EMOJI[key]} Tu es sur **{LABEL[key]}**. Tu veux faire quoi ?",
                view=MineView(cog, key, cid, interaction), ephemeral=True)
        await interaction.response.defer()
        try:
            await cog.mutate(guild, cid, cog.act_take(key, user))
            it = (await cog.get_items(cid))[key]
        except Nope as e:
            msg = await interaction.followup.send(str(e), ephemeral=True, allowed_mentions=NO_PING, wait=True)
            return await msg.delete(delay=TTL)
        others = fmt_takers(it, skip=user.id)
        msg = await interaction.followup.send(
            f"{EMOJI[key]} Tu prends **{LABEL[key]}**" + (f" avec {others}" if others else "")
            + ". Reclique dessus pour mettre ta quantité ou le lâcher.",
            ephemeral=True, allowed_mentions=NO_PING, wait=True)
        await msg.delete(delay=TTL)


class MineView(discord.ui.View):
    """Menu privé quand tu cliques sur un ingrédient où tu es déjà."""

    def __init__(self, cog: BandoBurger, key: str, channel_id: int, origin: Optional[discord.Interaction]):
        super().__init__(timeout=MENU_TTL)
        self.cog, self.key, self.cid, self.origin = cog, key, channel_id, origin

    async def close_menu(self):
        self.stop()
        if self.origin is None:
            return
        try:
            await self.origin.delete_original_response()
        except discord.HTTPException:
            pass

    async def on_timeout(self):
        await self.close_menu()

    async def _apply(self, interaction: discord.Interaction, fn):
        self.stop()
        await interaction.response.edit_message(content="⏳", view=None)
        try:
            msg = await self.cog.mutate(interaction.guild, self.cid, fn)
        except Nope as e:
            msg = str(e)
        done = await interaction.edit_original_response(content=msg, allowed_mentions=NO_PING)
        await done.delete(delay=TTL)

    @discord.ui.button(label="Quantité", emoji="✏️", style=discord.ButtonStyle.primary)
    async def quantity(self, interaction: discord.Interaction, button: discord.ui.Button):
        items = await self.cog.get_items(self.cid)
        me = find_taker(items[self.key], interaction.user.id)
        await interaction.response.send_modal(QtyModal(self.cog, self.key, self.cid, me["qty"] if me else "", self))

    @discord.ui.button(label="Je lâche", emoji="↩️", style=discord.ButtonStyle.danger)
    async def release(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._apply(interaction, self.cog.act_release(self.key, interaction.user))


class QtyModal(discord.ui.Modal):
    def __init__(self, cog: BandoBurger, key: str, channel_id: int, current: str,
                 menu: Optional[MineView] = None):
        super().__init__(title=f"Quantité : {LABEL[key]}"[:45])
        self.cog, self.key, self.cid, self.menu = cog, key, channel_id, menu
        self.qty = discord.ui.TextInput(label="Combien ?", placeholder="ex. 8 steaks, 2 paquets…",
                                        default=current or None, required=False, max_length=60)
        self.add_item(self.qty)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("⏳", ephemeral=True)
        if self.menu:
            await self.menu.close_menu()
        try:
            msg = await self.cog.mutate(interaction.guild, self.cid,
                                        self.cog.act_qty(self.key, interaction.user, self.qty.value))
        except Nope as e:
            msg = str(e)
        done = await interaction.edit_original_response(content=msg, allowed_mentions=NO_PING)
        await done.delete(delay=TTL)
