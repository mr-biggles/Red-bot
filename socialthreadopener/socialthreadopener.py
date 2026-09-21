import re
import asyncio
import aiohttp
import json
from typing import Optional
import discord
from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import humanize_list

default_guild = {
    "enabled": False,
    "channels": [],
    "thread_name_format": "{title}",
    "delay": 2,
    "platforms": {
        "youtube": True,
        "tiktok": True,
        "instagram": True,
        "facebook": True,
        "imgur": True,
        "gif": True,
        "twitch": True
    },
    "fetch_titles": True,
    "fallback_format": "Discussion: {platform}",
    "max_title_length": 80,
    "link_only_mode": False,
    "delete_non_links": False,
    "warning_message": "❌ Ce canal est réservé aux liens YouTube, TikTok, Instagram, Facebook, Imgur, Twitch, Biginsta et aux GIF uniquement!",
    "whitelist_roles": [],
    "allow_media": True,
}

class SocialThreadOpener(commands.Cog):
    """
    Crée automatiquement des threads pour les liens YouTube, TikTok, Instagram, Facebook, Imgur, Twitch et les GIFs
    """

    __version__ = "1.2.3"

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=208903205982044161, force_registration=True
        )

        self.config.register_guild(**default_guild)

        # Expressions régulières améliorées
        self.url_patterns = {
            "youtube": re.compile(
                r'(?:https?://)?(?:www\.)?(youtube\.com/(?:watch\?v=|shorts/|live/|embed/|v/|clip/)|youtu\.be/)([a-zA-Z0-9_-]+)',
                re.IGNORECASE
            ),
            "tiktok": re.compile(
                r'(?:https?://)?(?:www\.)?(tiktok\.com/@[^/\s]+/video/\d+|vm\.tiktok\.com/[a-zA-Z0-9]+)',
                re.IGNORECASE
            ),
            "instagram": re.compile(
                r'(?:https?://)?(?:www\.)?(instagram\.com/(?:p|reel|share|reels)/[a-zA-Z0-9_-]+)',
                re.IGNORECASE
            ),
            "facebook": re.compile(
                r'(?:https?://)?(?:www\.)?(facebook\.com|fb\.watch)/[a-zA-Z0-9\/?=%&-]+',
                re.IGNORECASE
            ),
            "imgur": re.compile(
                r'(?:https?://)?(?:www\.)?(i\.)?imgur\.com/(?:a/|gallery/|t/)?[a-zA-Z0-9]+',
                re.IGNORECASE
            ),
            "twitch": re.compile(
                r'(?:https?://)?(?:www\.)?(twitch\.tv/(?:videos/\d+|[a-zA-Z0-9_]+(?:/clip/[a-zA-Z0-9_-]+)?)|clips\.twitch\.tv/[a-zA-Z0-9_-]+)',
                re.IGNORECASE
            ),
            "biginsta": re.compile(
                r'(?:https?://)?(?:www\.)?(?:biginsta\.com|b\.biginsta\.com)(?:/[^\s]*)?',
                re.IGNORECASE
            )
        }

        # Extensions de fichiers vidéo et GIF
        self.gif_extensions = {'.gif', '.gifv'}
        self.video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v', '.3gp'}

    @commands.group(name="socialthread", aliases=["st"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def social_thread(self, ctx):
        """Configuration du Social Thread Opener"""
        pass

    @social_thread.command(name="enable")
    async def enable_social_thread(self, ctx):
        """Active le Social Thread Opener pour ce serveur"""
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send("✅ Social Thread Opener activé pour ce serveur!")

    @social_thread.command(name="disable")
    async def disable_social_thread(self, ctx):
        """Désactive le Social Thread Opener pour ce serveur"""
        await self.config.guild(ctx.guild).enabled.set(False)
        await ctx.send("❌ Social Thread Opener désactivé pour ce serveur.")

    @social_thread.command(name="addchannel")
    async def add_channel(self, ctx, channel: discord.TextChannel = None):
        """Ajoute un canal à la liste des canaux surveillés"""
        if channel is None:
            channel = ctx.channel

        async with self.config.guild(ctx.guild).channels() as channels:
            if channel.id not in channels:
                channels.append(channel.id)
                await ctx.send(f"✅ Canal {channel.mention} ajouté à la surveillance!")
            else:
                await ctx.send(f"⚠️ Canal {channel.mention} déjà dans la liste!")

    @social_thread.command(name="linkonly")
    async def toggle_link_only(self, ctx):
        """Active/désactive le mode liens uniquement"""
        current = await self.config.guild(ctx.guild).delete_non_links()
        await self.config.guild(ctx.guild).delete_non_links.set(not current)

        status = "✅ ACTIVÉ" if not current else "❌ DÉSACTIVÉ"

        if not current:
            await ctx.send(f"🔒 **Mode 'liens uniquement' {status}!**\n"
                          f"▫️ Les messages sans liens YouTube/TikTok/Instagram/Facebook/Imgur/Twitch/Biginsta/GIF seront supprimés dans les canaux surveillés\n"
                          f"▫️ Un message d'avertissement sera envoyé à l'utilisateur\n"
                          f"▫️ Les admins et rôles exemptés ne sont pas affectés")
        else:
            await ctx.send(f"🔓 **Mode 'liens uniquement' {status}!**\n"
                          f"▫️ Tous les messages sont maintenant autorisés")

    @social_thread.command(name="setwarning")
    async def set_warning_message(self, ctx, *, message: str):
        """Définit le message d'avertissement pour les messages supprimés"""
        if len(message) > 200:
            await ctx.send("❌ Le message d'avertissement ne peut pas dépasser 200 caractères!")
            return

        await self.config.guild(ctx.guild).warning_message.set(message)
        await ctx.send(f"✅ **Message d'avertissement défini:**\n```{message}```")

    @social_thread.command(name="addrole")
    async def add_whitelist_role(self, ctx, role: discord.Role):
        """Ajoute un rôle à la liste des exemptions (peut poster sans liens)"""
        async with self.config.guild(ctx.guild).whitelist_roles() as roles:
            if role.id not in roles:
                roles.append(role.id)
                await ctx.send(f"✅ Rôle {role.mention} ajouté aux exemptions du mode 'liens uniquement'!")
            else:
                await ctx.send(f"⚠️ Rôle {role.mention} déjà dans les exemptions!")

    @social_thread.command(name="removerole")
    async def remove_whitelist_role(self, ctx, role: discord.Role):
        """Retire un rôle de la liste des exemptions"""
        async with self.config.guild(ctx.guild).whitelist_roles() as roles:
            if role.id in roles:
                roles.remove(role.id)
                await ctx.send(f"✅ Rôle {role.mention} retiré des exemptions!")
            else:
                await ctx.send(f"⚠️ Rôle {role.mention} n'était pas dans les exemptions!")

    @social_thread.command(name="allowmedia")
    async def toggle_allow_media(self, ctx):
        """Active/désactive l'autorisation des fichiers/images sans liens"""
        current = await self.config.guild(ctx.guild).allow_media()
        await self.config.guild(ctx.guild).allow_media.set(not current)

    @social_thread.command(name="status")
    async def show_status(self, ctx):
        """Affiche la configuration actuelle"""
        guild_config = await self.config.guild(ctx.guild).all()

        embed = discord.Embed(title="📊 Status Social Thread Opener", color=discord.Color.blue())

        embed.add_field(
            name="🔒 Mode liens uniquement",
            value="✅ Activé" if guild_config.get("delete_non_links", False) else "❌ Désactivé",
            inline=True
        )

        embed.add_field(
            name="📎 Fichiers/Images",
            value="✅ Autorisés" if guild_config.get("allow_media", True) else "❌ Interdits",
            inline=True
        )

        platforms = []
        for platform, enabled in guild_config["platforms"].items():
            if enabled:
                platforms.append(platform.title())
        if platforms:
            embed.add_field(
                name="🌐 Plateformes activées",
                value=", ".join(platforms),
                inline=False
            )

        if guild_config.get("delete_non_links", False):
            warning = guild_config.get("warning_message", "Message par défaut")
            embed.add_field(
                name="⚠️ Message d'avertissement",
                value=f"```{warning[:100]}{'...' if len(warning) > 100 else ''}```",
                inline=False
            )

        whitelist_roles = guild_config.get("whitelist_roles", [])
        if whitelist_roles:
            roles = []
            for role_id in whitelist_roles[:5]:
                role = ctx.guild.get_role(role_id)
                if role:
                    roles.append(f"@{role.name}")
            if roles:
                embed.add_field(
                    name="👑 Rôles exemptés",
                    value=", ".join(roles),
                    inline=False
                )

        embed.add_field(
            name="🔧 Commandes principales",
            value="`!st linkonly` - Activer mode liens uniquement\n"
                  "`!st setwarning` - Message d'avertissement\n"
                  "`!st addrole` - Exempter un rôle\n"
                  "`!st allowmedia` - Autoriser médias",
            inline=False
        )

        await ctx.send(embed=embed)

    @social_thread.command(name="test")
    async def test_moderation(self, ctx):
        """Teste si le mode modération fonctionne dans ce canal"""
        guild_config = await self.config.guild(ctx.guild).all()

        if not guild_config["enabled"]:
            await ctx.send("❌ Le cog n'est pas activé!")
            return

        if ctx.channel.id not in guild_config["channels"]:
            await ctx.send("❌ Ce canal n'est pas surveillé!")
            return

        if not guild_config.get("delete_non_links", False):
            await ctx.send("❌ Le mode 'liens uniquement' n'est pas activé!")
            return

        await ctx.send("✅ **Test de modération:**\n"
                      f"▫️ Canal surveillé: ✅\n"
                      f"▫️ Mode liens uniquement: ✅\n"
                      f"▫️ Écris un message sans lien pour tester!")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Gère la modération ET la création de threads"""
        if message.author.bot or not message.guild:
            return

        guild_config = await self.config.guild(message.guild).all()

        if not guild_config["enabled"]:
            return

        if guild_config["channels"] and message.channel.id not in guild_config["channels"]:
            return

        if isinstance(message.channel, discord.Thread):
            return

        if not message.channel.permissions_for(message.guild.me).manage_messages:
            print("⚠️ Pas de permissions pour supprimer les messages")
            return

        if not message.channel.permissions_for(message.guild.me).create_public_threads:
            return

        print(f"🔍 Message analysé de {message.author.display_name}: '{message.content[:50]}...'")

        platforms, urls = self._detect_social_links(message, guild_config)

        if platforms:
            await self._create_thread_simplified(message, platforms, urls, guild_config)
        elif guild_config.get("delete_non_links", False):
            if message.author.guild_permissions.administrator:
                return
            whitelist_roles = guild_config.get("whitelist_roles", [])
            author_role_ids = [r.id for r in message.author.roles]
            if any(r in author_role_ids for r in whitelist_roles):
                return
            if guild_config.get("allow_media", True) and message.attachments:
                return
            await self._delete_and_warn(message, guild_config)

    def _has_social_content(self, message: discord.Message, config: dict) -> bool:
        """Vérifie si le message contient du contenu social"""
        for platform, pattern in self.url_patterns.items():
            if config["platforms"].get(platform, True):
                if pattern.search(message.content):
                    return True

        if config["platforms"].get("gif", True):
            for attachment in message.attachments:
                if any(attachment.filename.lower().endswith(ext) for ext in self.gif_extensions):
                    return True
                if any(attachment.filename.lower().endswith(ext) for ext in self.video_extensions):
                    return True

        return False

    def _detect_social_links(self, message: discord.Message, config: dict) -> tuple:
        """Détecte les liens sociaux pour créer des threads"""
        detected_platforms = []
        detected_urls = {}

        for platform, pattern in self.url_patterns.items():
            if not config["platforms"].get(platform, True):
                continue

            matches = pattern.findall(message.content)
            if matches:
                detected_platforms.append(platform)

                if platform == "youtube":
                    full_match = pattern.search(message.content)
                    if full_match:
                        url_base = full_match.group(1)
                        video_id = full_match.group(2)

                        if "youtu.be/" in url_base:
                            detected_urls[platform] = f"https://www.youtube.com/watch?v={video_id}"
                        elif "clip/" in url_base:
                            detected_urls[platform] = f"https://www.youtube.com/clip/{video_id}"
                        elif "shorts/" in url_base:
                            detected_urls[platform] = f"https://www.youtube.com/shorts/{video_id}"
                        else:
                            detected_urls[platform] = f"https://www.youtube.com/watch?v={video_id}"

                elif platform in ["facebook", "imgur"]:
                    full_match = pattern.search(message.content)
                    if full_match:
                        detected_urls[platform] = full_match.group(0)

        if config["platforms"].get("gif", True):
            for attachment in message.attachments:
                if any(attachment.filename.lower().endswith(ext) for ext in self.gif_extensions):
                    detected_platforms.append("gif")
                    detected_urls["gif"] = attachment.url
                elif any(attachment.filename.lower().endswith(ext) for ext in self.video_extensions):
                    detected_platforms.append("video")
                    detected_urls["video"] = attachment.url

        return detected_platforms, detected_urls

    async def _delete_and_warn(self, message: discord.Message, config: dict):
        """Supprime le message et envoie un avertissement"""
        try:
            print(f"🗑️ Suppression du message de {message.author.display_name}")

            await message.delete()

            warning_msg = config.get("warning_message", "❌ Ce canal est réservé aux liens YouTube, TikTok, Instagram, Facebook, Imgur, Twitch, Biginsta et aux GIF uniquement!")

            view = DismissView()

            try:
                await message.channel.send(
                    f"🚫 {message.author.mention} {warning_msg}",
                    view=view,
                    delete_after=20
                )
                print(f"⚠️ Avertissement envoyé à {message.author.display_name}")
            except Exception as e:
                print(f"❌ Erreur envoi avertissement: {e}")

        except discord.NotFound:
            print("⚠️ Message déjà supprimé")
        except discord.Forbidden:
            print("❌ Pas de permissions pour supprimer")
        except Exception as e:
            print(f"💥 Erreur suppression: {e}")

    async def _get_youtube_title(self, url: str) -> Optional[str]:
        """Récupère le titre YouTube avec plusieurs méthodes de fallback"""
        try:
            print(f"🎬 Récupération titre YouTube: {url}")

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none'
            }

            timeout = aiohttp.ClientTimeout(total=20)
            connector = aiohttp.TCPConnector(ssl=False)

            async with aiohttp.ClientSession(timeout=timeout, headers=headers, connector=connector) as session:
                async with session.get(url, allow_redirects=True) as response:
                    print(f"📡 Status HTTP: {response.status}")

                    if response.status != 200:
                        return None

                    try:
                        html = await response.text(encoding='utf-8')
                    except:
                        html = await response.text(encoding='latin-1')

                    patterns = [
                        (r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']*)["\']', "og:title"),
                        (r'<meta\s+name=["\']title["\']\s+content=["\']([^"\']*)["\']', "meta title"),
                        (r'"videoDetails":\s*{[^}]*"title":\s*"([^"]*)"', "videoDetails JSON"),
                        (r'<title>([^<]+?)\s*(?:-\s*YouTube)?</title>', "page title"),
                        (r'<meta\s+property="twitter:title"\s+content="([^"]*)"', "twitter:title"),
                        (r'"title":{"runs":\[{"text":"([^"]*)"', "runs title"),
                    ]

                    for pattern, method_name in patterns:
                        matches = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
                        if matches:
                            for match in matches:
                                title = match.strip()
                                if title and len(title) > 3:
                                    cleaned_title = self._clean_youtube_title(title)
                                    if len(cleaned_title) > 3:
                                        print(f"✅ Titre trouvé via {method_name}: '{cleaned_title}'")
                                        return cleaned_title

                    return None

        except Exception as e:
            print(f"💥 Erreur récupération titre YouTube: {e}")
            return None

    def _clean_youtube_title(self, title: str) -> str:
        """Nettoie spécifiquement les titres YouTube"""
        if not title:
            return ""

        import html
        title = html.unescape(title)

        suffixes_to_remove = [
            r'\s*-\s*YouTube\s*$',
            r'\s*\|\s*YouTube\s*$',
            r'\s*•\s*YouTube\s*$',
            r'\s*-\s*Video\s*$',
        ]

        for suffix in suffixes_to_remove:
            title = re.sub(suffix, '', title, flags=re.IGNORECASE)

        title = re.sub(r'\s+', ' ', title).strip()
        title = re.sub(r'^[^\w]+|[^\w]+$', '', title)

        return title

    async def _create_thread_simplified(self, message: discord.Message, platforms: list, urls: dict, config: dict):
        """Version simplifiée de création de thread"""
        try:
            thread_name = ""
            author_name = message.author.display_name

            print(f"🧵 Création thread pour: {platforms}")

            if "youtube" in platforms and config["fetch_titles"]:
                url = urls.get("youtube")
                if url:
                    title = await self._get_youtube_title(url)
                    if title and len(title.strip()) > 0:
                        max_length = config.get('max_title_length', 80)
                        if len(title) > max_length:
                            title = title[:max_length-3] + "..."

                        try:
                            thread_name = config["thread_name_format"].format(
                                title=title,
                                platform="YouTube",
                                author=author_name
                            )
                        except KeyError:
                            thread_name = title

            if not thread_name or len(thread_name.strip()) == 0:
                if len(platforms) == 1:
                    platform = platforms[0]
                    if platform == "instagram":
                        thread_name = f"Post Instagram de {author_name}"
                    elif platform == "tiktok":
                        thread_name = f"Vidéo TikTok de {author_name}"
                    elif platform == "youtube":
                        thread_name = f"Vidéo YouTube de {author_name}"
                    elif platform == "facebook":
                        thread_name = f"Post Facebook de {author_name}"
                    elif platform == "imgur":
                        thread_name = f"Image Imgur de {author_name}"
                    elif platform == "gif":
                        thread_name = f"GIF de {author_name}"
                    elif platform == "twitch":
                        thread_name = f"Stream/Clip Twitch de {author_name}"
                    elif platform == "biginsta":
                        thread_name = f"Post Biginsta de {author_name}"
                    elif platform == "video":
                        thread_name = f"Vidéo de {author_name}"
                else:
                    thread_name = f"Contenu de {author_name}"

            thread_name = re.sub(r'[<>:"/\\|?*]', '', thread_name)
            thread_name = re.sub(r'\s+', ' ', thread_name).strip()

            if len(thread_name) > 100:
                thread_name = thread_name[:97] + "..."

            if len(thread_name) < 1:
                thread_name = f"Thread de {author_name}"

            thread = await message.create_thread(
                name=thread_name,
                auto_archive_duration=1440
            )

            platform_list = ", ".join([p.title() for p in platforms])
            intro = f"Thread créé pour discuter du contenu {platform_list} partagé par {message.author.mention}!"

            await thread.send(intro)
            print(f"🎉 Thread '{thread_name}' créé avec succès!")

        except Exception as e:
            print(f"💥 Erreur création thread: {e}")

    def cog_unload(self):
        """Nettoyage lors du déchargement du cog"""
        pass


# Classe pour le bouton "Fermer" sur les messages d'avertissement
class DismissView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="✖️ Fermer", style=discord.ButtonStyle.secondary)
    async def dismiss_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.message.delete()
        except:
            await interaction.response.send_message("Message supprimé!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(SocialThreadOpener(bot))
