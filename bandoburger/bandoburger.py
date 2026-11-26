import asyncio
import io
import unicodedata
from typing import Callable, Dict, List, Optional

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
    ("sauce", "Sauces (burger + BBQ)", "🥫"),
]
LABEL = {k: l for k, l, _ in INGREDIENTS}
EMOJI = {k: e for k, _, e in INGREDIENTS}
NO_PING = discord.AllowedMentions.none()
COLOR = 0xF2A516
TTL = 5  # secondes avant que les messages privés du bot disparaissent
MENU_TTL = 30  # menu « c'est toi qui le ramènes » sans action


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


MAX_TAKERS = 10  # personnes max sur un même ingrédient


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


def find_taker(it: dict, user_id: int) -> Optional[dict]:
    return next((t for t in it["takers"] if t["who"] == user_id), None)


def fmt_takers(it: dict, skip: Optional[int] = None) -> str:
    return ", ".join(f"<@{t['who']}>" + (f" · {t['qty']}" if t["qty"] else "")
                     for t in it["takers"] if t["who"] != skip)


class BandoBurger(commands.Cog):
    """BandoBurger : qui ramène quoi pour le burger, avec le burger qui se monte en direct."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=0xB4D0B0B6, force_registration=True)
        self.config.register_guild(channel_id=None, message_id=None, items={})
        self._locks: Dict[int, asyncio.Lock] = {}

    async def cog_load(self):
        # vue persistante : les boutons des panneaux existants remarchent après un redémarrage
        self.bot.add_view(PanelView(self))

    async def red_delete_data_for_user(self, *, requester, user_id: int):
        for gid, data in (await self.config.all_guilds()).items():
            items = {k: upgrade_item(v) for k, v in (data.get("items") or {}).items()}
            changed = False
            for it in items.values():
                before = len(it["takers"])
                it["takers"] = [t for t in it["takers"] if t["who"] != user_id]
                changed |= len(it["takers"]) != before
            if changed:
                await self.config.guild_from_id(gid).items.set(items)

    # ---------- état ----------

    def _lock(self, guild_id: int) -> asyncio.Lock:
        return self._locks.setdefault(guild_id, asyncio.Lock())

    async def get_items(self, guild: discord.Guild) -> dict:
        items = await self.config.guild(guild).items()
        return {k: upgrade_item(items.get(k)) for k, _, _ in INGREDIENTS}

    async def is_mod(self, member: discord.Member) -> bool:
        return await self.bot.is_mod(member) or member.guild_permissions.manage_messages

    async def mutate(self, guild: discord.Guild, fn: Callable[[dict], Optional[str]]) -> Optional[str]:
        """Applique fn aux items sous verrou, sauvegarde, met à jour le panneau."""
        async with self._lock(guild.id):
            items = await self.get_items(guild)
            result = fn(items)
            await self.config.guild(guild).items.set(items)
            await self.refresh(guild, items)
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
        if taken == total:
            title = "🍔 BandoBurger — burger complet !"
        else:
            title = "🍔 BandoBurger — qui prend quoi ?"
        embed = discord.Embed(title=title, description="\n".join(lines), color=COLOR)
        embed.set_footer(text=f"{taken}/{total} pris"
                              " · clique sur un ingrédient pour le prendre (à plusieurs, c'est possible)")
        embed.set_image(url="attachment://burger.png")
        return embed

    async def build_file(self, items: dict) -> discord.File:
        state = {k: ("taken" if it["takers"] else "free") for k, it in items.items()}
        png = await asyncio.get_running_loop().run_in_executor(None, render_burger, state)
        return discord.File(io.BytesIO(png), filename="burger.png")

    async def refresh(self, guild: discord.Guild, items: Optional[dict] = None) -> bool:
        conf = self.config.guild(guild)
        cid, mid = await conf.channel_id(), await conf.message_id()
        channel = guild.get_channel_or_thread(cid) if cid else None
        if not channel or not mid:
            return False
        if items is None:
            items = await self.get_items(guild)
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
            msg = await self.mutate(ctx.guild, fn)
        except Nope as e:
            return await ctx.send(str(e), ephemeral=True, allowed_mentions=NO_PING)
        if not await self.config.guild(ctx.guild).message_id():
            msg += f"\n-# Aucun tableau affiché : lance `{ctx.clean_prefix}burger start`."
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
        """Affiche le tableau BandoBurger (qui prend quoi)."""
        items = await self.get_items(ctx.guild)
        await ctx.send(embed=self.build_embed(items), file=await self.build_file(items),
                       allowed_mentions=NO_PING)

    @bando.command(name="start")
    @commands.guild_only()
    @commands.mod_or_permissions(manage_messages=True)
    async def bando_start(self, ctx: commands.Context, vider: bool = False):
        """Poste le tableau interactif dans ce salon.

        `vider` : True pour repartir d'une liste vide. L'ancien tableau perd ses boutons.
        """
        conf = self.config.guild(ctx.guild)
        async with self._lock(ctx.guild.id):
            if vider:
                await conf.items.set({})
            old_c, old_m = await conf.channel_id(), await conf.message_id()
            if old_c and old_m:
                old = ctx.guild.get_channel_or_thread(old_c)
                if old:
                    try:
                        await old.get_partial_message(old_m).edit(view=None)
                    except discord.HTTPException:
                        pass
            items = await self.get_items(ctx.guild)
            msg = await ctx.send(embed=self.build_embed(items), file=await self.build_file(items),
                                 view=PanelView(self, items), allowed_mentions=NO_PING)
            await conf.channel_id.set(msg.channel.id)
            await conf.message_id.set(msg.id)

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
        """Tu ne prends plus cet ingrédient. Les modos peuvent retirer quelqu'un : `burger lache steak @pseudo`"""
        try:
            key = find_key(ingredient)
        except Nope as e:
            return await ctx.send(str(e), ephemeral=True)
        target = membre or ctx.author
        if target != ctx.author and not await self.is_mod(ctx.author):
            return await ctx.send("Seuls les modos peuvent retirer quelqu'un d'autre.", ephemeral=True)
        await self._run(ctx, self.act_release(key, target))

    @bando.command(name="quantite")
    @commands.guild_only()
    async def bando_quantite(self, ctx: commands.Context, ingredient: str, *, quantite: str = ""):
        """Change la quantité d'un de tes ingrédients. Ex : `burger quantite steak 8`"""
        try:
            key = find_key(ingredient)
        except Nope as e:
            return await ctx.send(str(e), ephemeral=True)
        await self._run(ctx, self.act_qty(key, ctx.author, quantite))

    @bando.command(name="assigne")
    @commands.guild_only()
    @commands.mod_or_permissions(manage_messages=True)
    async def bando_assigne(self, ctx: commands.Context, ingredient: str, membre: discord.Member,
                            *, quantite: Optional[str] = None):
        """(Modo) Ajoute quelqu'un sur un ingrédient, ou change sa quantité."""
        try:
            key = find_key(ingredient)
        except Nope as e:
            return await ctx.send(str(e), ephemeral=True)
        await self._run(ctx, self.act_take(key, membre, quantite))

    @bando.command(name="reset")
    @commands.guild_only()
    @commands.mod_or_permissions(manage_messages=True)
    async def bando_reset(self, ctx: commands.Context):
        """(Modo) Vide toute la répartition."""
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
    """Les 7 boutons du tableau. Persistante (timeout=None, custom_id fixes)."""

    def __init__(self, cog: BandoBurger, items: Optional[dict] = None):
        super().__init__(timeout=None)
        self.cog = cog
        for i, (key, label, emo) in enumerate(INGREDIENTS):
            it = upgrade_item((items or {}).get(key))
            n = len(it["takers"])
            if n:
                style = discord.ButtonStyle.primary
            else:
                style = discord.ButtonStyle.secondary
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
        cog, guild, user = self.cog, interaction.guild, interaction.user
        if guild is None:
            return
        if interaction.message and interaction.message.id != await cog.config.guild(guild).message_id():
            return await interaction.response.send_message(
                "Ce tableau n'est plus actif, utilise le plus récent.", ephemeral=True, delete_after=TTL)

        it = (await cog.get_items(guild))[key]
        if find_taker(it, user.id):
            view = MineView(cog, key, interaction)
            return await interaction.response.send_message(
                f"{EMOJI[key]} Tu es sur **{LABEL[key]}**. Tu veux faire quoi ?",
                view=view, ephemeral=True)
        await interaction.response.defer()
        try:
            await cog.mutate(guild, cog.act_take(key, user))
            it = (await cog.get_items(guild))[key]
        except Nope as e:
            msg = await interaction.followup.send(str(e), ephemeral=True, allowed_mentions=NO_PING, wait=True)
            return await msg.delete(delay=TTL)
        msg = await interaction.followup.send(
            f"{EMOJI[key]} Tu prends **{LABEL[key]}**"
            + (f" avec {others}" if (others := fmt_takers(it, skip=user.id)) else "")
            + ". Reclique dessus pour mettre ta quantité ou le lâcher.",
            ephemeral=True, allowed_mentions=NO_PING, wait=True)
        await msg.delete(delay=TTL)


class MineView(discord.ui.View):
    """Menu privé quand tu cliques sur un ingrédient que tu as déjà pris."""

    def __init__(self, cog: BandoBurger, key: str, origin: discord.Interaction):
        super().__init__(timeout=MENU_TTL)
        self.cog, self.key, self.origin = cog, key, origin

    async def close_menu(self):
        self.stop()
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
            msg = await self.cog.mutate(interaction.guild, fn)
        except Nope as e:
            msg = str(e)
        done = await interaction.edit_original_response(content=msg, allowed_mentions=NO_PING)
        await done.delete(delay=TTL)

    @discord.ui.button(label="Quantité", emoji="✏️", style=discord.ButtonStyle.primary)
    async def quantity(self, interaction: discord.Interaction, button: discord.ui.Button):
        items = await self.cog.get_items(interaction.guild)
        me = find_taker(items[self.key], interaction.user.id)
        await interaction.response.send_modal(QtyModal(self.cog, self.key, me["qty"] if me else "", self))

    @discord.ui.button(label="Je lâche", emoji="↩️", style=discord.ButtonStyle.danger)
    async def release(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._apply(interaction, self.cog.act_release(self.key, interaction.user))


class QtyModal(discord.ui.Modal):
    def __init__(self, cog: BandoBurger, key: str, current: str, menu: Optional["MineView"] = None):
        super().__init__(title=f"Quantité : {LABEL[key]}"[:45])
        self.cog, self.key, self.menu = cog, key, menu
        self.qty = discord.ui.TextInput(label="Combien ?", placeholder="ex. 8 steaks, 2 paquets…",
                                        default=current or None, required=False, max_length=60)
        self.add_item(self.qty)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("⏳", ephemeral=True)
        if self.menu:
            await self.menu.close_menu()
        try:
            msg = await self.cog.mutate(interaction.guild,
                                        self.cog.act_qty(self.key, interaction.user, self.qty.value))
        except Nope as e:
            msg = str(e)
        done = await interaction.edit_original_response(content=msg, allowed_mentions=NO_PING)
        await done.delete(delay=TTL)
