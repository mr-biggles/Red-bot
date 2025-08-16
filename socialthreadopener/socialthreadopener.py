import re
import asyncio
import aiohttp
import json
from typing import Optional
import discord
from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import humanize_list

class SocialThreadOpener(commands.Cog):
    """
    Crée automatiquement des threads pour les liens YouTube, TikTok, Instagram, Facebook, Imgur et les GIFs
    """

    __version__ = "1.2.0"

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=208903205982044161, force_registration=True
        )

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
                "gif": True
            },
            "fetch_titles": True,
            "fallback_format": "Discussion: {platform}",
            "max_title_length": 80,
            # Nouvelles options pour la modération
            "link_only_mode": False,
            "delete_non_links": False,
            "warning_message": "❌ Ce canal est réservé aux liens YouTube, TikTok, Instagram, Facebook, Imgur et aux GIF uniquement!",
            "whitelist_roles": [],
            "allow_media": True,
        }

        self.config.register_guild(**default_guild)

        # Expressions régulières améliorées
        self.url_patterns = {
            "youtube": re.compile(
                r'(?:https?://)?(?:www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]+)',
                re.IGNORECASE
            ),
            "tiktok": re.compile(
                r'(?:https?://)?(?:www\.)?(tiktok\.com/@[^/\s]+/video/\d+|vm\.tiktok\.com/[a-zA-Z0-9]+)',
                re.IGNORECASE
            ),
            "instagram": re.compile(
                r'(?:https?://)?(?:www\.)?(instagram\.com/(?:p|reel|reels)/[a-zA-Z0-9_-]+)',
                re.IGNORECASE
            ),
            "facebook": re.compile(
                r'(?:https?://)?(?:www\.)?(facebook\.com|fb\.watch)/[a-zA-Z0-9\/?=%&-]+',
                re.IGNORECASE
            ),
            "imgur": re.compile(
                r'(?:https?://)?(?:www\.)?(i\.)?imgur\.com/(?:a/|gallery/|t/)?[a-zA-Z0-9]+',
                re.IGNORECASE
            )
        }

        # Extensions de fichiers GIF
        self.gif_extensions = {'.gif', '.gifv'}

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

    @social_thread.command(name="removechannel")
    async def remove_channel(self, ctx, channel: discord.TextChannel = None):
        """Retire un canal de la liste des canaux surveillés"""
        if channel is None:
            channel = ctx.channel

        async with self.config.guild(ctx.guild).channels() as channels:
            if channel.id in channels:
                channels.remove(channel.id)
                await ctx.send(f"✅ Canal {channel.mention} retiré de la surveillance!")
            else:
                await ctx.send(f"⚠️ Canal {channel.mention} n'était pas surveillé!")

    @social_thread.command(name="linkonly")
    async def toggle_link_only(self, ctx):
        """Active/désactive le mode 'liens uniquement' pour les canaux surveillés"""
        current = await self.config.guild(ctx.guild).delete_non_links()
        await self.config.guild(ctx.guild).delete_non_links.set(not current)

        status = "✅ ACTIVÉ" if not current else "❌ DÉSACTIVÉ"

        if not current:
            await ctx.send(f"🔒 **Mode 'liens uniquement' {status}!**\n"
                          f"▫️ Les messages sans liens YouTube/TikTok/Instagram/Facebook/Imgur/GIF seront supprimés dans les canaux surveillés\n"
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

        status = "✅ AUTORISÉS" if not current else "❌ NON AUTORISÉS"
        await ctx.send(f"📎 **Fichiers et images {status}** dans le mode 'liens uniquement'!")

    @social_thread.command(name="channels")
    async def list_channels(self, ctx):
        """Liste les canaux surveillés"""
        channels_ids = await self.config.guild(ctx.guild).channels()
        if not channels_ids:
            await ctx.send("Aucun canal n'est surveillé.")
            return

        channels = []
        for channel_id in channels_ids:
            channel = ctx.guild.get_channel(channel_id)
            if channel:
                channels.append(channel.mention)

        if channels:
            await ctx.send(f"**Canaux surveillés:** {humanize_list(channels)}")
        else:
            await ctx.send("Aucun canal valide trouvé dans la liste.")

    @social_thread.command(name="settings")
    async def show_settings(self, ctx):
        """Affiche la configuration actuelle"""
        guild_config = await self.config.guild(ctx.guild).all()

        embed = discord.Embed(
            title="⚙️ Configuration Social Thread Opener",
            color=0x00ff00 if guild_config["enabled"] else 0xff0000
        )

        # Status principal
        embed.add_field(
            name="📊 Statut général",
            value="✅ Activé" if guild_config["enabled"] else "❌ Désactivé",
            inline=True
        )

        # Mode liens uniquement
        embed.add_field(
            name="🔒 Mode liens uniquement",
            value="✅ Activé" if guild_config.get("delete_non_links", False) else "❌ Désactivé",
            inline=True
        )

        # Médias autorisés
        embed.add_field(
            name="📎 Fichiers/Images",
            value="✅ Autorisés" if guild_config.get("allow_media", True) else "❌ Interdits",
            inline=True
        )

        # Plateformes activées
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

        # Message d'avertissement (seulement si mode actif)
        if guild_config.get("delete_non_links", False):
            warning = guild_config.get("warning_message", "Message par défaut")
            embed.add_field(
                name="⚠️ Message d'avertissement",
                value=f"```{warning[:100]}{'...' if len(warning) > 100 else ''}```",
                inline=False
            )

        # Rôles exemptés
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

        # Commandes utiles
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
        # Vérifications de base
        if message.author.bot or not message.guild:
            return

        guild_config = await self.config.guild(message.guild).all()

        if not guild_config["enabled"]:
            return

        # Vérifie si c'est un canal surveillé
        if guild_config["channels"] and message.channel.id not in guild_config["channels"]:
            return

        # Ignore les threads
        if isinstance(message.channel, discord.Thread):
            return

        # Vérifie les permissions
        if not message.channel.permissions_for(message.guild.me).manage_messages:
            print("⚠️ Pas de permissions pour supprimer les messages")
            return

        if not message.channel.permissions_for(message.guild.me).create_public_threads:
            return

        print(f"🔍 Message analysé de {message.author.display_name}: '{message.content[:50]}...'")

        # ÉTAPE 1: VÉRIFICATION MODÉRATION EN PREMIER
        delete_non_links = guild_config.get("delete_non_links", False)
        print(f"🔒 Mode liens uniquement: {delete_non_links}")

        if delete_non_links:
            # Vérifications d'exemption
            is_exempt = await self._is_user_exempt(message, guild_config)
            print(f"👑 Utilisateur exempté: {is_exempt}")

            if not is_exempt:
                has_social_links = self._has_social_media_links(message, guild_config)
                print(f"🔗 A des liens sociaux: {has_social_links}")

                if not has_social_links:
                    # Vérifie si médias autorisés
                    has_media = bool(message.attachments or message.embeds)
                    allow_media = guild_config.get("allow_media", True)
                    print(f"📎 A des médias: {has_media}, autorisés: {allow_media}")

                    if not (has_media and allow_media):
                        # SUPPRIME LE MESSAGE
                        await self._delete_and_warn(message, guild_config)
                        return  # ARRÊTE ici, ne crée pas de thread

        # ÉTAPE 2: SI PAS SUPPRIMÉ, VÉRIFIE POUR THREADS
        detected_platforms, detected_urls = self._detect_social_links(message, guild_config)

        if detected_platforms:
            print(f"📱 Plateformes détectées pour thread: {detected_platforms}")

            if guild_config["delay"] > 0:
                await asyncio.sleep(guild_config["delay"])

            await self._create_thread_simplified(message, detected_platforms, detected_urls, guild_config)

    async def _is_user_exempt(self, message: discord.Message, config: dict) -> bool:
        """Vérifie si l'utilisateur est exempté de la modération"""
        # Admins et modérateurs sont toujours exemptés
        if message.author.guild_permissions.manage_messages or message.author.guild_permissions.administrator:
            return False

        # Vérifie les rôles exemptés
        whitelist_roles = config.get("whitelist_roles", [])
        if whitelist_roles:
            user_roles = [role.id for role in message.author.roles]
            if any(role_id in user_roles for role_id in whitelist_roles):
                return True

        return False

    def _has_social_media_links(self, message: discord.Message, config: dict) -> bool:
        """Vérifie si le message contient des liens de réseaux sociaux supportés"""
        # Vérifie les liens dans le contenu
        for platform, pattern in self.url_patterns.items():
            if config["platforms"][platform] and pattern.search(message.content):
                return True

        # Vérifie les GIFs dans les pièces jointes
        if config["platforms"]["gif"]:
            for attachment in message.attachments:
                if any(attachment.filename.lower().endswith(ext) for ext in self.gif_extensions):
                    return True

        return False

    def _detect_social_links(self, message: discord.Message, config: dict) -> tuple:
        """Détecte les liens sociaux pour créer des threads"""
        detected_platforms = []
        detected_urls = {}

        # Détection des liens dans le contenu
        for platform, pattern in self.url_patterns.items():
            if config["platforms"][platform]:
                if platform == "youtube":
                    youtube_matches = re.findall(
                        r'(?:https?://)?(?:www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]+)',
                        message.content, re.IGNORECASE
                    )
                    if youtube_matches:
                        detected_platforms.append(platform)
                        url_base, video_id = youtube_matches[0]
                        if "youtu.be/" in url_base or "youtube.com/shorts/" in url_base:
                            detected_urls[platform] = f"https://www.youtube.com/watch?v={video_id}"
                        else:
                            detected_urls[platform] = f"https://www.youtube.com/watch?v={video_id}"
                else:
                    matches = pattern.findall(message.content)
                    if matches:
                        detected_platforms.append(platform)
                        # Pour Facebook et Imgur, on prend le premier lien trouvé
                        if platform in ["facebook", "imgur"]:
                            full_match = pattern.search(message.content)
                            if full_match:
                                detected_urls[platform] = full_match.group(0)

        # Détection des GIFs dans les pièces jointes
        if config["platforms"]["gif"]:
            for attachment in message.attachments:
                if any(attachment.filename.lower().endswith(ext) for ext in self.gif_extensions):
                    detected_platforms.append("gif")
                    detected_urls["gif"] = attachment.url

        return detected_platforms, detected_urls

    async def _delete_and_warn(self, message: discord.Message, config: dict):
        """Supprime le message et envoie un avertissement"""
        try:
            print(f"🗑️ Suppression du message de {message.author.display_name}")

            # Supprime le message
            await message.delete()

            # Prépare le message d'avertissement
            warning_msg = config.get("warning_message", "❌ Ce canal est réservé aux liens YouTube, TikTok, Instagram, Facebook, Imgur et aux GIF uniquement!")

            # Crée un message temporaire avec bouton
            view = DismissView()

            try:
                warning_message = await message.channel.send(
                    f"🚫 {message.author.mention} {warning_msg}",
                    view=view,
                    delete_after=20  # Supprime après 20 secondes
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

            # Cas spécial pour YouTube (récupération du titre)
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

            # Si pas de nom de thread ou nom vide, on utilise un nom par défaut
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
                else:
                    thread_name = f"Contenu de {author_name}"

            # Nettoyage du nom du thread
            thread_name = re.sub(r'[<>:"/\\|?*]', '', thread_name)
            thread_name = re.sub(r'\s+', ' ', thread_name).strip()

            if len(thread_name) > 100:
                thread_name = thread_name[:97] + "..."

            if len(thread_name) < 1:
                thread_name = f"Thread de {author_name}"

            # Création du thread
            thread = await message.create_thread(
                name=thread_name,
                auto_archive_duration=1440
            )

            # Message d'introduction du thread
            if len(platforms) == 1:
                platform = platforms[0]
                if platform == "youtube":
                    intro = f"Thread créé pour discuter de cette vidéo YouTube partagée par {message.author.mention}!"
                elif platform == "instagram":
                    intro = f"Thread créé pour discuter de ce post Instagram partagé par {message.author.mention}!"
                elif platform == "tiktok":
                    intro = f"Thread créé pour discuter de cette vidéo TikTok partagée par {message.author.mention}!"
                elif platform == "facebook":
                    intro = f"Thread créé pour discuter de ce post Facebook partagé par {message.author.mention}!"
                elif platform == "imgur":
                    intro = f"Thread créé pour discuter de cette image Imgur partagée par {message.author.mention}!"
                elif platform == "gif":
                    intro = f"Thread créé pour discuter de ce GIF partagé par {message.author.mention}!"
            else:
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
