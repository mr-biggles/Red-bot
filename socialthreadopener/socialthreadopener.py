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
    Crée automatiquement des threads pour les liens YouTube, TikTok et Instagram
    """

    __version__ = "1.1.0"

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
                "instagram": True
            },
            "fetch_titles": True,
            "fallback_format": "Discussion: {platform}",
            "max_title_length": 80,
            # Nouvelles options pour la modération
            "link_only_mode": False,
            "delete_non_links": False,
            "warning_message": "❌ Ce canal est réservé aux liens YouTube, TikTok et Instagram uniquement!",
            "whitelist_roles": [],  # Rôles exemptés de la restriction
            "allow_media": True,  # Permet les fichiers/images
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
                r'(?:https?://)?(?:www\.)?(instagram\.com/(?:p|reel)/[a-zA-Z0-9_-]+)',
                re.IGNORECASE
            )
        }
        
        # Pattern pour détecter les URLs générales
        self.general_url_pattern = re.compile(
            r'https?://[^\s<>"{}|\\^`\[\]]+',
            re.IGNORECASE
        )

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

    # 🆕 NOUVELLES COMMANDES DE MODÉRATION
    @social_thread.command(name="linkonly")
    async def toggle_link_only(self, ctx, channel: discord.TextChannel = None):
        """Active/désactive le mode 'liens uniquement' pour un canal surveillé"""
        if channel is None:
            channel = ctx.channel
        
        channels = await self.config.guild(ctx.guild).channels()
        if channel.id not in channels:
            await ctx.send(f"❌ {channel.mention} n'est pas un canal surveillé! Ajoutez-le d'abord avec `{ctx.prefix}st addchannel`")
            return
        
        current = await self.config.guild(ctx.guild).delete_non_links()
        await self.config.guild(ctx.guild).delete_non_links.set(not current)
        
        status = "activé" if not current else "désactivé"
        await ctx.send(f"🔒 Mode 'liens uniquement' {status} pour tous les canaux surveillés!\n"
                      f"{'Les messages sans liens sociaux seront supprimés.' if not current else 'Les messages sans liens sociaux ne seront plus supprimés.'}")

    @social_thread.command(name="setwarning")
    async def set_warning_message(self, ctx, *, message: str):
        """Définit le message d'avertissement pour les messages supprimés"""
        await self.config.guild(ctx.guild).warning_message.set(message)
        await ctx.send(f"✅ Message d'avertissement défini:\n```{message}```")

    @social_thread.command(name="addrole")
    async def add_whitelist_role(self, ctx, role: discord.Role):
        """Ajoute un rôle à la liste des exemptions (peut poster sans liens)"""
        async with self.config.guild(ctx.guild).whitelist_roles() as roles:
            if role.id not in roles:
                roles.append(role.id)
                await ctx.send(f"✅ Rôle {role.mention} ajouté aux exemptions!")
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
        
        status = "autorisés" if not current else "non autorisés"
        await ctx.send(f"📎 Fichiers et images {status} dans les canaux 'liens uniquement'!")

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
            await ctx.send(f"Canaux surveillés: {humanize_list(channels)}")
        else:
            await ctx.send("Aucun canal valide trouvé dans la liste.")

    @social_thread.command(name="platforms")
    async def toggle_platform(self, ctx, platform: str):
        """Active/désactive une plateforme (youtube, tiktok, instagram)"""
        platform = platform.lower()
        if platform not in ["youtube", "tiktok", "instagram"]:
            await ctx.send("❌ Plateforme invalide! Utilisez: youtube, tiktok, ou instagram")
            return
        
        async with self.config.guild(ctx.guild).platforms() as platforms:
            platforms[platform] = not platforms[platform]
            status = "activée" if platforms[platform] else "désactivée"
            await ctx.send(f"✅ Plateforme {platform.title()} {status}!")

    @social_thread.command(name="format")
    async def set_format(self, ctx, *, format_string: str):
        """
        Définit le format du nom des threads (pour YouTube seulement)
        Variables disponibles: {title}, {platform}, {author}
        """
        await self.config.guild(ctx.guild).thread_name_format.set(format_string)
        await ctx.send(f"✅ Format des noms de threads défini: `{format_string}`\n📝 Note: Ce format s'applique seulement à YouTube.")

    @social_thread.command(name="titles")
    async def toggle_titles(self, ctx):
        """Active/désactive la récupération automatique des titres (YouTube uniquement)"""
        current = await self.config.guild(ctx.guild).fetch_titles()
        await self.config.guild(ctx.guild).fetch_titles.set(not current)
        status = "activée" if not current else "désactivée"
        await ctx.send(f"✅ Récupération des titres YouTube {status}!")

    @social_thread.command(name="delay")
    async def set_delay(self, ctx, seconds: int):
        """Définit le délai avant création du thread (en secondes)"""
        if seconds < 0 or seconds > 60:
            await ctx.send("❌ Le délai doit être entre 0 et 60 secondes!")
            return
        
        await self.config.guild(ctx.guild).delay.set(seconds)
        await ctx.send(f"✅ Délai défini à {seconds} secondes!")

    @social_thread.command(name="titlelength")
    async def set_title_length(self, ctx, length: int):
        """Définit la longueur maximum des titres YouTube (20-80 caractères)"""
        if length < 20 or length > 80:
            await ctx.send("❌ La longueur doit être entre 20 et 80 caractères!")
            return
        
        await self.config.guild(ctx.guild).max_title_length.set(length)
        await ctx.send(f"✅ Longueur maximum des titres YouTube définie à {length} caractères!")

    @social_thread.command(name="settings")
    async def show_settings(self, ctx):
        """Affiche la configuration actuelle"""
        guild_config = await self.config.guild(ctx.guild).all()
        
        embed = discord.Embed(
            title="Configuration Social Thread Opener",
            color=0x00ff00 if guild_config["enabled"] else 0xff0000
        )
        
        embed.add_field(
            name="Statut",
            value="✅ Activé" if guild_config["enabled"] else "❌ Désactivé",
            inline=True
        )
        
        embed.add_field(
            name="Mode liens uniquement",
            value="🔒 Activé" if guild_config.get("delete_non_links", False) else "🔓 Désactivé",
            inline=True
        )
        
        embed.add_field(
            name="Fichiers autorisés",
            value="📎 Oui" if guild_config.get("allow_media", True) else "📎 Non",
            inline=True
        )
        
        embed.add_field(
            name="Délai",
            value=f"{guild_config['delay']} secondes",
            inline=True
        )
        
        embed.add_field(
            name="Format YouTube",
            value=f"`{guild_config['thread_name_format']}`",
            inline=False
        )
        
        embed.add_field(
            name="Format Instagram/TikTok",
            value="`Thread de {author}`",
            inline=False
        )
        
        if guild_config.get("delete_non_links", False):
            embed.add_field(
                name="Message d'avertissement",
                value=f"```{guild_config.get('warning_message', 'Message par défaut')}```",
                inline=False
            )
        
        # Rôles exemptés
        whitelist_roles = guild_config.get("whitelist_roles", [])
        if whitelist_roles:
            roles = []
            for role_id in whitelist_roles[:3]:
                role = ctx.guild.get_role(role_id)
                if role:
                    roles.append(role.mention)
            if roles:
                roles_text = ", ".join(roles)
                if len(whitelist_roles) > 3:
                    roles_text += f" +{len(whitelist_roles) - 3} autres"
                embed.add_field(
                    name="Rôles exemptés",
                    value=roles_text,
                    inline=False
                )
        
        # Plateformes et canaux (code existant)
        platforms_status = []
        for platform, enabled in guild_config["platforms"].items():
            status = "✅" if enabled else "❌"
            platforms_status.append(f"{status} {platform.title()}")
        
        embed.add_field(
            name="Plateformes",
            value="\n".join(platforms_status),
            inline=True
        )
        
        channels_ids = guild_config["channels"]
        if channels_ids:
            channels = []
            for channel_id in channels_ids[:3]:
                channel = ctx.guild.get_channel(channel_id)
                if channel:
                    channels.append(channel.mention)
            
            if channels:
                channels_text = "\n".join(channels)
                if len(channels_ids) > 3:
                    channels_text += f"\n... +{len(channels_ids) - 3} autres"
                embed.add_field(
                    name="Canaux surveillés",
                    value=channels_text,
                    inline=True
                )
        
        embed.add_field(
            name="Nouvelles commandes",
            value="`linkonly` - Mode liens uniquement\n`setwarning` - Message d'avertissement\n`addrole/removerole` - Rôles exemptés\n`allowmedia` - Autoriser médias",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @social_thread.command(name="testtitle")
    async def test_title(self, ctx, url: str):
        """Teste la récupération de titre pour une URL YouTube"""
        if "youtube" not in url and "youtu.be" not in url:
            await ctx.send("❌ Ce n'est pas une URL YouTube valide!")
            return
        
        await ctx.send("🔍 Test de récupération de titre...")
        
        title = await self._get_youtube_title(url)
        if title:
            await ctx.send(f"✅ Titre trouvé: **{title}**")
        else:
            await ctx.send("❌ Impossible de récupérer le titre")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Écoute les messages pour détecter les liens ET modérer si nécessaire"""
        if message.author.bot or not message.guild:
            return
        
        guild_config = await self.config.guild(message.guild).all()
        
        if not guild_config["enabled"]:
            return
        
        if guild_config["channels"] and message.channel.id not in guild_config["channels"]:
            return
        
        if isinstance(message.channel, discord.Thread):
            return
        
        if not message.channel.permissions_for(message.guild.me).create_public_threads:
            return
        
        # 🆕 VÉRIFICATION DU MODE "LIENS UNIQUEMENT"
        if guild_config.get("delete_non_links", False):
            should_delete = await self._should_delete_message(message, guild_config)
            if should_delete:
                return  # Message supprimé, on arrête le traitement
        
        # Continue avec la logique normale de détection de liens
        detected_platforms = []
        detected_urls = {}
        
        # Detection des plateformes
        for platform, pattern in self.url_patterns.items():
            if guild_config["platforms"][platform]:
                if platform == "youtube":
                    youtube_matches = re.findall(r'(?:https?://)?(?:www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]+)', message.content, re.IGNORECASE)
                    if youtube_matches:
                        detected_platforms.append(platform)
                        if "youtu.be/" in youtube_matches[0][0]:
                            detected_urls[platform] = f"https://www.youtube.com/watch?v={youtube_matches[0][1]}"
                        elif "youtube.com/shorts/" in youtube_matches[0][0]:
                            detected_urls[platform] = f"https://www.youtube.com/watch?v={youtube_matches[0][1]}"
                        else:
                            detected_urls[platform] = f"https://www.youtube.com/watch?v={youtube_matches[0][1]}"
                        print(f"🔍 URL YouTube détectée: {detected_urls[platform]}")
                else:
                    matches = pattern.findall(message.content)
                    if matches:
                        detected_platforms.append(platform)
        
        if not detected_platforms:
            return
        
        print(f"📱 Plateformes détectées: {detected_platforms}")
        
        if guild_config["delay"] > 0:
            await asyncio.sleep(guild_config["delay"])
        
        await self._create_thread_simplified(message, detected_platforms, detected_urls, guild_config)

    async def _should_delete_message(self, message: discord.Message, config: dict) -> bool:
        """Détermine si un message doit être supprimé dans le mode 'liens uniquement'"""
        try:
            # Vérifie les permissions (admin, modo, etc.)
            if message.author.guild_permissions.manage_messages or message.author.guild_permissions.administrator:
                return False
            
            # Vérifie les rôles exemptés
            whitelist_roles = config.get("whitelist_roles", [])
            if whitelist_roles:
                user_roles = [role.id for role in message.author.roles]
                if any(role_id in user_roles for role_id in whitelist_roles):
                    print(f"👑 {message.author.display_name} a un rôle exempté")
                    return False
            
            # Vérifie si le message contient des liens de médias sociaux supportés
            has_social_link = False
            for platform, pattern in self.url_patterns.items():
                if config["platforms"][platform] and pattern.search(message.content):
                    has_social_link = True
                    break
            
            if has_social_link:
                print(f"✅ Message avec lien social autorisé de {message.author.display_name}")
                return False
            
            # Vérifie si le message contient des fichiers/médias (si autorisé)
            if config.get("allow_media", True) and (message.attachments or message.embeds):
                print(f"📎 Message avec média autorisé de {message.author.display_name}")
                return False
            
            # Si on arrive ici, le message doit être supprimé
            print(f"🗑️ Message de {message.author.display_name} va être supprimé (pas de lien social)")
            
            # Supprime le message
            await message.delete()
            
            # Crée une vue avec bouton pour le message éphémère
            view = DismissView()
            warning_msg = config.get("warning_message", "❌ Ce canal est réservé aux liens YouTube, TikTok et Instagram uniquement!")
            
            # Envoie le message éphémère (visible seulement par l'utilisateur)
            try:
                await message.channel.send(
                    f"{message.author.mention} {warning_msg}",
                    view=view,
                    delete_after=15  # Supprime automatiquement après 15 secondes
                )
            except discord.HTTPException:
                # Si l'envoi échoue, utilise la méthode de fallback
                temp_msg = await message.channel.send(f"{message.author.mention} {warning_msg}")
                await asyncio.sleep(10)
                try:
                    await temp_msg.delete()
                except:
                    pass
            
            return True
            
        except discord.HTTPException as e:
            print(f"❌ Erreur lors de la suppression: {e}")
            return False
        except Exception as e:
            print(f"💥 Erreur inattendue lors de la modération: {e}")
            return False

    # [Garde toutes tes méthodes existantes: _get_youtube_title, _clean_youtube_title, _create_thread_simplified]
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
                    if platform in ["instagram", "tiktok"]:
                        thread_name = f"Thread de {author_name}"
                    elif platform == "youtube":
                        thread_name = f"Vidéo de {author_name}"
                else:
                    thread_name = f"Thread de {author_name}"
            
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
            
            if len(platforms) == 1:
                platform = platforms[0]
                if platform == "youtube":
                    intro = f"Thread créé pour discuter de cette vidéo YouTube partagée par {message.author.mention}!"
                elif platform == "instagram":
                    intro = f"Thread créé pour discuter de ce post Instagram partagé par {message.author.mention}!"
                elif platform == "tiktok":
                    intro = f"Thread créé pour discuter de cette vidéo TikTok partagée par {message.author.mention}!"
                else:
                    intro = f"Thread créé pour discuter du contenu {platform.title()} partagé par {message.author.mention}!"
            else:
                platform_list = ", ".join([p.title() for p in platforms])
                intro = f"Thread créé pour discuter du contenu {platform_list} partagé par {message.author.mention}!"
            
            await thread.send(intro)
            print(f"🎉 Thread créé avec succès!")
            
        except Exception as e:
            print(f"💥 Erreur création thread: {e}")

    def cog_unload(self):
        """Nettoyage lors du déchargement du cog"""
        pass


# 🆕 CLASSE POUR LE BOUTON "FERMER" SUR LES MESSAGES D'AVERTISSEMENT
class DismissView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)  # 5 minutes
    
    @discord.ui.button(label="✖️ Fermer", style=discord.ButtonStyle.secondary)
    async def dismiss_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.message.delete()
        except:
            await interaction.response.send_message("Message supprimé!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(SocialThreadOpener(bot))
