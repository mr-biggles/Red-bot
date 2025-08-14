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

    __version__ = "1.0.2"

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
            "max_title_length": 80
        }
        
        self.config.register_guild(**default_guild)
        
        # Expressions régulières pour détecter les liens
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

    # [Garde toutes tes commandes exactement comme elles sont - je les abrège ici pour la lisibilité]
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
        Définit le format du nom des threads
        Variables disponibles: {title}, {platform}, {author}
        Exemple: {title} | par {author}
        """
        await self.config.guild(ctx.guild).thread_name_format.set(format_string)
        await ctx.send(f"✅ Format des noms de threads défini: `{format_string}`")

    @social_thread.command(name="titles")
    async def toggle_titles(self, ctx):
        """Active/désactive la récupération automatique des titres"""
        current = await self.config.guild(ctx.guild).fetch_titles()
        await self.config.guild(ctx.guild).fetch_titles.set(not current)
        status = "activée" if not current else "désactivée"
        await ctx.send(f"✅ Récupération des titres {status}!")

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
        """Définit la longueur maximum des titres (20-80 caractères)"""
        if length < 20 or length > 80:
            await ctx.send("❌ La longueur doit être entre 20 et 80 caractères!")
            return
        
        await self.config.guild(ctx.guild).max_title_length.set(length)
        await ctx.send(f"✅ Longueur maximum des titres définie à {length} caractères!")

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
            name="Délai",
            value=f"{guild_config['delay']} secondes",
            inline=True
        )
        
        embed.add_field(
            name="Format des threads",
            value=f"`{guild_config['thread_name_format']}`",
            inline=False
        )
        
        embed.add_field(
            name="Format de fallback",
            value=f"`{guild_config['fallback_format']}`",
            inline=False
        )
        
        embed.add_field(
            name="Récupération des titres",
            value="✅ Activée" if guild_config["fetch_titles"] else "❌ Désactivée",
            inline=True
        )

        embed.add_field(
            name="Longueur max des titres",
            value=f"{guild_config.get('max_title_length', 80)} caractères",
            inline=True
        )
        
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
            for channel_id in channels_ids[:5]:
                channel = ctx.guild.get_channel(channel_id)
                if channel:
                    channels.append(channel.mention)
            
            if channels:
                channels_text = "\n".join(channels)
                if len(channels_ids) > 5:
                    channels_text += f"\n... et {len(channels_ids) - 5} autres"
                embed.add_field(
                    name="Canaux surveillés",
                    value=channels_text,
                    inline=True
                )
        
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Écoute les messages pour détecter les liens"""
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
        
        # Détecte les plateformes dans le message
        detected_platforms = []
        detected_urls = {}
        
        for platform, pattern in self.url_patterns.items():
            if guild_config["platforms"][platform]:
                matches = pattern.findall(message.content)
                if matches:
                    detected_platforms.append(platform)
                    # Reconstruit l'URL complète
                    if platform == "youtube":
                        detected_urls[platform] = f"https://www.{matches[0]}{matches[1] if len(matches) > 1 else ''}"
                    else:
                        detected_urls[platform] = f"https://www.{matches[0]}"
        
        if not detected_platforms:
            return
        
        print(f"Plateformes détectées: {detected_platforms}")
        print(f"URLs détectées: {detected_urls}")
        
        if guild_config["delay"] > 0:
            await asyncio.sleep(guild_config["delay"])
        
        await self._create_thread(message, detected_platforms, detected_urls, guild_config)

    async def _get_video_title(self, url: str, platform: str) -> Optional[str]:
        """Récupère le titre d'une vidéo depuis l'URL avec des méthodes très améliorées"""
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            print(f"🔍 Récupération du titre pour: {url} (plateforme: {platform})")

            # Headers différents selon la plateforme
            headers = self._get_headers_for_platform(platform)
            
            timeout = aiohttp.ClientTimeout(total=20)
            
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(url, allow_redirects=True) as response:
                    print(f"📡 Status HTTP: {response.status}")
                    
                    if response.status != 200:
                        print(f"❌ Echec HTTP {response.status}")
                        return None
                    
                    content_type = response.headers.get('content-type', '')
                    print(f"📄 Content-Type: {content_type}")
                    
                    html = await response.text()
                    print(f"📝 HTML récupéré: {len(html)} caractères")
                    
                    # Essaie plusieurs méthodes selon la plateforme
                    title = await self._extract_title_multi_method(html, platform, url)
                    
                    if title:
                        clean_title = self._clean_title(title, platform)
                        print(f"✅ Titre trouvé et nettoyé: '{clean_title}'")
                        return clean_title
                    else:
                        print(f"❌ Aucun titre trouvé pour {platform}")
                    
                    return None
                    
        except asyncio.TimeoutError:
            print(f"⏰ Timeout lors de la récupération pour {url}")
            return None
        except Exception as e:
            print(f"💥 Erreur lors de la récupération du titre pour {url}: {e}")
            return None

    def _get_headers_for_platform(self, platform: str) -> dict:
        """Retourne des headers spécifiques selon la plateforme"""
        base_headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
        }
        
        if platform == "youtube":
            base_headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        elif platform == "tiktok":
            base_headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        elif platform == "instagram":
            base_headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        
        return base_headers

    async def _extract_title_multi_method(self, html: str, platform: str, url: str) -> Optional[str]:
        """Utilise plusieurs méthodes pour extraire le titre selon la plateforme"""
        
        title = None
        
        if platform == "youtube":
            title = self._extract_youtube_title_improved(html)
        elif platform == "tiktok":
            title = self._extract_tiktok_title_improved(html)
        elif platform == "instagram":
            title = self._extract_instagram_title_improved(html)
        
        # Méthode de fallback universelle
        if not title:
            title = self._extract_generic_title(html)
        
        return title

    def _extract_youtube_title_improved(self, html: str) -> Optional[str]:
        """Version améliorée pour YouTube"""
        patterns = [
            # Pattern pour le JSON ytInitialPlayerResponse
            r'"videoDetails":\s*{[^}]*"title":\s*"([^"]*)"',
            # Pattern pour le titre dans les métadonnées
            r'<meta\s+property="og:title"\s+content="([^"]*)"',
            r'<meta\s+name="title"\s+content="([^"]*)"',
            # Pattern pour le titre dans initialData
            r'"title":\s*{\s*"runs":\s*\[\s*{\s*"text":\s*"([^"]*)"',
            # Pattern simple dans le title
            r'<title>([^<]+?)\s*-\s*YouTube</title>',
            # Pattern de secours
            r'<title>([^<]+)</title>'
        ]
        
        for i, pattern in enumerate(patterns):
            try:
                match = re.search(pattern, html, re.IGNORECASE | re.MULTILINE)
                if match:
                    title = match.group(1).strip()
                    print(f"🎯 YouTube titre trouvé avec pattern {i+1}: '{title}'")
                    if len(title) > 3 and not any(ignore in title.lower() for ignore in ['youtube', 'error', '404']):
                        return title
            except Exception as e:
                print(f"Erreur pattern {i+1}: {e}")
                continue
        
        print("❌ Aucun titre YouTube trouvé")
        return None

    def _extract_tiktok_title_improved(self, html: str) -> Optional[str]:
        """Version améliorée pour TikTok"""
        patterns = [
            # Patterns pour TikTok
            r'"desc":\s*"([^"]+)"',
            r'"description":\s*"([^"]+)"',
            r'<meta\s+name="description"\s+content="([^"]*)"',
            r'<meta\s+property="og:description"\s+content="([^"]*)"',
            r'"videoObject":\s*{[^}]*"description":\s*"([^"]*)"',
            r'"DetailVideo":[^{]*{[^}]*"desc":\s*"([^"]*)"',
            r'<title>([^<]+?)\s*\|\s*TikTok</title>',
            r'<title>([^<]+)</title>'
        ]
        
        for i, pattern in enumerate(patterns):
            try:
                match = re.search(pattern, html, re.IGNORECASE | re.MULTILINE)
                if match:
                    title = match.group(1).strip()
                    print(f"🎯 TikTok titre trouvé avec pattern {i+1}: '{title}'")
                    if len(title) > 5 and not any(ignore in title.lower() for ignore in ['tiktok', 'error', 'login', 'sign up']):
                        return title
            except Exception as e:
                print(f"Erreur pattern {i+1}: {e}")
                continue
        
        print("❌ Aucun titre TikTok trouvé")
        return None

    def _extract_instagram_title_improved(self, html: str) -> Optional[str]:
        """Version améliorée pour Instagram"""
        patterns = [
            # Patterns spécifiques Instagram
            r'"edge_media_to_caption":\s*{\s*"edges":\s*\[\s*{\s*"node":\s*{\s*"text":\s*"([^"]*)"',
            r'"caption":\s*"([^"]*)"',
            r'"accessibility_caption":\s*"([^"]*)"',
            r'<meta\s+property="og:title"\s+content="([^"]*)"',
            r'<meta\s+name="description"\s+content="([^"]*)"',
            r'"title":\s*"([^"]*)"',
            # Pattern pour les nouvelles versions d'Instagram
            r'"comet_sections":[^{]*"message":{"text":"([^"]*)"',
            r'window\.__additionalDataLoaded[^{]*"caption":"([^"]*)"',
            r'<title>([^<]+)</title>'
        ]
        
        for i, pattern in enumerate(patterns):
            try:
                match = re.search(pattern, html, re.IGNORECASE | re.MULTILINE)
                if match:
                    title = match.group(1).strip()
                    print(f"🎯 Instagram titre trouvé avec pattern {i+1}: '{title[:50]}...'")
                    # Filtre les titres Instagram génériques ou vides
                    if (len(title) > 8 and 
                        not any(ignore in title.lower() for ignore in 
                               ['instagram', 'login', 'sign up', 'create account', 'error', 'not found']) and
                        not title.startswith(('@', '#')) and
                        title not in ['', ' ', 'null', 'undefined']):
                        return title
            except Exception as e:
                print(f"Erreur pattern {i+1}: {e}")
                continue
        
        print("❌ Aucun titre Instagram trouvé")
        return None

    def _extract_generic_title(self, html: str) -> Optional[str]:
        """Méthode de fallback générique"""
        patterns = [
            r'<meta\s+property="og:title"\s+content="([^"]*)"',
            r'<meta\s+name="title"\s+content="([^"]*)"',
            r'<title>([^<]+)</title>'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                if len(title) > 3:
                    print(f"🔄 Titre générique trouvé: '{title}'")
                    return title
        
        return None

    def _clean_title(self, title: str, platform: str) -> str:
        """Nettoie et formate le titre de manière plus agressive"""
        if not title:
            return ""
            
        print(f"🧹 Nettoyage du titre: '{title}'")
        
        # Décode les caractères HTML
        html_entities = {
            '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', 
            '&#39;': "'", '&apos;': "'", '&nbsp;': ' ',
            '&#x27;': "'", '&#x2F;': '/', '&#x3D;': '='
        }
        
        for entity, char in html_entities.items():
            title = title.replace(entity, char)
        
        # Supprime les caractères d'échappement et unicode
        title = re.sub(r'\\u[0-9a-fA-F]{4}', '', title)
        title = re.sub(r'\\[nrtfb]', ' ', title)
        title = title.replace('\n', ' ').replace('\t', ' ').replace('\r', ' ')
        
        # Supprime les suffixes de plateforme
        suffixes = {
            'youtube': [' - YouTube', ' | YouTube', ' - Youtube', ' | Youtube'],
            'tiktok': [' | TikTok', ' - TikTok', ' | tiktok', ' - tiktok'],
            'instagram': [' • Instagram', ' | Instagram', ' - Instagram']
        }
        
        if platform in suffixes:
            for suffix in suffixes[platform]:
                title = re.sub(re.escape(suffix) + r'\s*$', '', title, flags=re.IGNORECASE)
        
        # Nettoie les espaces et caractères indésirables
        title = re.sub(r'\s+', ' ', title)
        title = re.sub(r'^[^\w\s]*|[^\w\s]*$', '', title)
        title = title.strip()
        
        print(f"✨ Titre nettoyé: '{title}'")
        return title

    async def _create_thread(self, message: discord.Message, platforms: list, urls: dict, config: dict):
        """Crée un thread pour le message"""
        try:
            thread_name = ""
            max_length = config.get('max_title_length', 80)
            
            print(f"🧵 Création de thread pour: {platforms}")
            
            # Récupère le titre si activé
            if config["fetch_titles"]:
                for platform in platforms:
                    if platform in urls:
                        url = urls[platform]
                        print(f"🔄 Récupération pour {platform}: {url}")
                        
                        title = await self._get_video_title(url, platform)
                        if title and len(title.strip()) > 0:
                            # Tronque le titre si nécessaire
                            if len(title) > max_length:
                                title = title[:max_length-3] + "..."
                            
                            # Formate le nom du thread
                            try:
                                thread_name = config["thread_name_format"].format(
                                    title=title,
                                    platform=platform.title(),
                                    author=message.author.display_name
                                )
                                print(f"✅ Thread nommé: '{thread_name}'")
                                break
                            except KeyError as e:
                                print(f"❌ Erreur de format: {e}")
                                thread_name = title
                                break
                        else:
                            print(f"❌ Pas de titre pour {platform}")
            
            # Si pas de titre trouvé, utilise le format de fallback
            if not thread_name or len(thread_name.strip()) == 0:
                platform_name = platforms[0].title() if len(platforms) == 1 else f"{len(platforms)} plateformes"
                try:
                    thread_name = config["fallback_format"].format(
                        platform=platform_name,
                        author=message.author.display_name
                    )
                except KeyError:
                    thread_name = f"Discussion {platform_name}"
                print(f"🔄 Utilisation du fallback: '{thread_name}'")
            
            # Nettoie le nom du thread pour Discord
            thread_name = re.sub(r'[<>:"/\\|?*]', '', thread_name)
            thread_name = re.sub(r'\s+', ' ', thread_name).strip()
            
            if len(thread_name) > 100:
                thread_name = thread_name[:97] + "..."
            
            if len(thread_name) < 1:
                thread_name = f"Discussion {platforms[0].title()}"
            
            print(f"🎯 Nom final du thread: '{thread_name}'")
            
            # Crée le thread
            thread = await message.create_thread(
                name=thread_name,
                auto_archive_duration=1440
            )
            
            # Message d'introduction
            platform_list = ", ".join([p.title() for p in platforms])
            intro_message = f"Thread créé automatiquement pour discuter du contenu {platform_list} partagé par {message.author.mention}!"
            
            await thread.send(intro_message)
            print(f"🎉 Thread créé avec succès!")
            
        except discord.HTTPException as e:
            print(f"💥 Erreur HTTP lors de la création du thread: {e}")
        except Exception as e:
            print(f"💥 Erreur inattendue: {e}")
            import traceback
            traceback.print_exc()

    def cog_unload(self):
        """Nettoyage lors du déchargement du cog"""
        pass


async def setup(bot):
    await bot.add_cog(SocialThreadOpener(bot))
