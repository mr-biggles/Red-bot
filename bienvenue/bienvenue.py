"""Carte de bienvenue configurable pour Red-DiscordBot V3."""

import asyncio
import io
import logging
from pathlib import Path

import discord
from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError
from redbot.core import Config, commands
from redbot.core.data_manager import cog_data_path

log = logging.getLogger("red.bienvenue")
W, H = 1000, 360
MAX_BG_BYTES = 8 * 1024 * 1024


class Bienvenue(commands.Cog):
    """Accueille les membres avec une bannière personnalisée."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=68492013755, force_registration=True)
        self.config.register_guild(
            enabled=False,
            channel_id=None,
            title="Bienvenue {member} !",
            message=(
                "Bienvenue {mention} sur **{server}** ! 🎉\n"
                "📜 Consulte le règlement, 👋 présente-toi et 🎭 choisis tes rôles."
            ),
        )
        self.data_dir = cog_data_path(self)

    def _bg_path(self, guild_id: int) -> Path:
        return self.data_dir / f"fond_{guild_id}.png"

    @staticmethod
    def _placeholders(template: str, member: discord.Member) -> str:
        replacements = {
            "{member}": member.display_name,
            "{mention}": member.mention,
            "{server}": member.guild.name,
            "{count}": str(member.guild.member_count or 0),
        }
        for key, value in replacements.items():
            template = template.replace(key, value)
        return template

    def _render(self, avatar_bytes: bytes, background: bytes | None) -> io.BytesIO:
        # Aucun nom, compteur ou titre n'est dessiné sur l'image.
        if background:
            with Image.open(io.BytesIO(background)) as raw:
                img = ImageOps.fit(raw.convert("RGB"), (W, H), method=Image.Resampling.LANCZOS)
        else:
            default = Path(__file__).with_name("bando_lovers.png")
            with Image.open(default) as raw:
                img = ImageOps.fit(raw.convert("RGB"), (W, H), method=Image.Resampling.LANCZOS)

        img = img.convert("RGBA")
        # Avatar positionné dans le cercle du fond Bando Lovers (à gauche).
        # Masque carré + ellipse : cercle rigoureusement rond.
        diameter = 199
        center_x, center_y = 226, 174
        left = center_x - diameter // 2
        top = center_y - diameter // 2
        with Image.open(io.BytesIO(avatar_bytes)) as raw_avatar:
            avatar = ImageOps.fit(raw_avatar.convert("RGBA"), (diameter, diameter), method=Image.Resampling.LANCZOS)
        mask = Image.new("L", (diameter, diameter), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, diameter - 1, diameter - 1), fill=255)
        img.paste(avatar, (left, top), mask)

        output = io.BytesIO()
        img.convert("RGB").save(output, format="PNG", optimize=True)
        output.seek(0)
        return output

    async def _make_image(self, member: discord.Member) -> io.BytesIO:
        avatar_bytes = await member.display_avatar.replace(size=256, format="png").read()
        path = self._bg_path(member.guild.id)
        background = await asyncio.to_thread(path.read_bytes) if path.exists() else None
        return await asyncio.to_thread(self._render, avatar_bytes, background)

    async def _send_welcome(self, channel: discord.TextChannel, member: discord.Member):
        settings = await self.config.guild(member.guild).all()
        text = self._placeholders(settings["message"], member)
        title = self._placeholders(settings["title"], member)
        image = await self._make_image(member)
        embed = discord.Embed(title=title, description=text, color=discord.Color.blurple())
        embed.set_image(url="attachment://bienvenue.png")
        await channel.send(
            embed=embed,
            file=discord.File(image, filename="bienvenue.png"),
            allowed_mentions=discord.AllowedMentions(users=[member], roles=False, everyone=False),
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        settings = await self.config.guild(member.guild).all()
        if not settings["enabled"] or not settings["channel_id"]:
            return
        channel = member.guild.get_channel(settings["channel_id"])
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            await self._send_welcome(channel, member)
        except (discord.HTTPException, OSError, UnidentifiedImageError, ValueError):
            log.exception("Impossible d'envoyer la bienvenue sur %s", member.guild.id)

    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.group(name="bienvenue", invoke_without_command=True)
    async def bienvenue(self, ctx):
        """Paramètres de la carte de bienvenue."""
        await ctx.send_help()

    @bienvenue.command(name="salon")
    async def salon(self, ctx, salon: discord.TextChannel):
        """Définit le salon d'accueil : [p]bienvenue salon #accueil"""
        await self.config.guild(ctx.guild).channel_id.set(salon.id)
        await ctx.send(f"✅ Salon d'accueil : {salon.mention}")

    @bienvenue.command(name="activer")
    async def activer(self, ctx):
        """Active l'accueil automatique."""
        if not await self.config.guild(ctx.guild).channel_id():
            return await ctx.send("⚠️ Définis d'abord le salon avec `[p]bienvenue salon #accueil`.")
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send("✅ Messages de bienvenue activés.")

    @bienvenue.command(name="desactiver")
    async def desactiver(self, ctx):
        """Désactive l'accueil automatique."""
        await self.config.guild(ctx.guild).enabled.set(False)
        await ctx.send("✅ Messages de bienvenue désactivés.")

    @bienvenue.command(name="titre")
    async def titre(self, ctx, *, texte: str):
        """Change le titre du message. Variables : {member}, {server}, {count}."""
        if len(texte) > 200:
            return await ctx.send("⚠️ Titre trop long (200 caractères maximum).")
        await self.config.guild(ctx.guild).title.set(texte)
        await ctx.send("✅ Titre enregistré.")

    @bienvenue.command(name="texte")
    async def texte(self, ctx, *, texte: str):
        """Change le texte d'accueil. Variables : {member}, {mention}, {server}, {count}."""
        if len(texte) > 3000:
            return await ctx.send("⚠️ Texte trop long (3000 caractères maximum).")
        await self.config.guild(ctx.guild).message.set(texte)
        await ctx.send("✅ Texte enregistré.")

    @bienvenue.command(name="banniere")
    async def banniere(self, ctx):
        """Définis une image de fond en joignant un fichier PNG/JPG à la commande."""
        if not ctx.message.attachments:
            return await ctx.send("⚠️ Joins une image PNG ou JPG au même message que la commande.")
        attachment = ctx.message.attachments[0]
        if attachment.size > MAX_BG_BYTES:
            return await ctx.send("⚠️ Image trop volumineuse (8 Mo maximum).")
        try:
            raw = await attachment.read()
            def prepare():
                with Image.open(io.BytesIO(raw)) as source:
                    if source.format not in ("JPEG", "PNG", "WEBP"):
                        raise ValueError("Format non supporté")
                    converted = ImageOps.fit(source.convert("RGB"), (W, H), method=Image.Resampling.LANCZOS)
                    out = io.BytesIO()
                    converted.save(out, "PNG")
                    return out.getvalue()
            data = await asyncio.to_thread(prepare)
            await asyncio.to_thread(self._bg_path(ctx.guild.id).write_bytes, data)
        except (OSError, ValueError, UnidentifiedImageError, discord.HTTPException):
            return await ctx.send("❌ Image invalide. Utilise un PNG, JPG ou WEBP valide.")
        await ctx.send("✅ Bannière enregistrée ! Fais `[p]bienvenue test` pour voir le rendu.")

    @bienvenue.command(name="retirerbanniere")
    async def retirer_banniere(self, ctx):
        """Revient à la bannière Bando Lovers fournie avec le cog."""
        self._bg_path(ctx.guild.id).unlink(missing_ok=True)
        await ctx.send("✅ Fond personnalisé retiré : bannière Bando Lovers par défaut restaurée.")

    @bienvenue.command(name="test")
    @commands.bot_has_permissions(embed_links=True, attach_files=True)
    async def test(self, ctx, membre: discord.Member = None):
        """Affiche un aperçu ici (par défaut avec ton avatar)."""
        try:
            await self._send_welcome(ctx.channel, membre or ctx.author)
        except (discord.HTTPException, OSError, ValueError, UnidentifiedImageError):
            log.exception("Echec du test de bienvenue")
            await ctx.send("❌ Impossible de créer le message. Vérifie les permissions et l'image.")

    @bienvenue.command(name="config")
    async def voir_config(self, ctx):
        """Affiche les paramètres de ce serveur."""
        data = await self.config.guild(ctx.guild).all()
        salon = ctx.guild.get_channel(data["channel_id"]) if data["channel_id"] else None
        await ctx.send(
            f"**Accueil :** {'activé' if data['enabled'] else 'désactivé'}\n"
            f"**Salon :** {salon.mention if salon else 'non défini'}\n"
            f"**Titre :** {discord.utils.escape_mentions(data['title'])}\n"
            f"**Texte :** {discord.utils.escape_mentions(data['message'])}\n"
            f"**Bannière perso :** {'oui' if self._bg_path(ctx.guild.id).exists() else 'non'}",
            allowed_mentions=discord.AllowedMentions.none(),
        )
