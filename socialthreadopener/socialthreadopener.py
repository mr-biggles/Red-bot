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

    __version__ = "1.0.4"

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
        
        # Expressions régulières améliorées pour YouTube
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

    # [Toutes tes commandes exactement pareilles]
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
        Définit le format du nom des threads (pour YouTube seulement)
        Variables disponibles: {title}, {platform}, {author}
        Exemple: {title} | par {author}
        """
        await self.config.guild(ctx.guild).thread_name_format.set(format_string)
        await ctx.send(f"✅ Format des noms de threads défini: `{format_string}`\n📝 Note: Ce format s'applique seulement à YouTube. Instagram et TikTok utilisent 'Thread de [nom]'")

    @social_thread.command(name="titles")
    async def toggle_titles(self, ctx):
        """Active/désactive la récupération automatique des titres (YouTube uniquement)"""
        current = await self.config.guild(ctx.guild).fetch_titles()
        await self.config.guild(ctx.guild).fetch_titles.set(not current)
        status = "activée" if not current else "désactivée"
        await ctx.send(f"✅ Récupération des titres YouTube {status}!\n📝 Note: Instagram et TikTok utilisent toujours 'Thread de [nom]'")

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
        
        embed.add_field(
            name="Titres YouTube",
            value="✅ Activée" if guild_config["fetch_titles"] else "❌ Désactivée",
            inline=True
        )

        embed.add_field(
            name="Longueur max titres",
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

    # Commande pour tester manuellement la récupération de titre
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
        
        # Detection améliorée pour YouTube
        for platform, pattern in self.url_patterns.items():
            if guild_config["platforms"][platform]:
                if platform == "youtube":
                    # Recherche plus précise pour YouTube
                    youtube_matches = re.findall(r'(?:https?://)?(?:www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]+)', message.content, re.IGNORECASE)
                    if youtube_matches:
                        detected_platforms.append(platform)
                        # Reconstruit l'URL complète
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

    async def _get_youtube_title(self, url: str) -> Optional[str]:
        """Récupère le titre YouTube avec plusieurs méthodes de fallback"""
        try:
            print(f"🎬 Récupération titre YouTube: {url}")
            
            # Headers pour simuler un navigateur réel
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
                        print(f"❌ Erreur HTTP {response.status}")
                        return None
                    
                    # Lire le contenu
                    try:
                        html = await response.text(encoding='utf-8')
                    except:
                        html = await response.text(encoding='latin-1')
                    
                    print(f"📄 Taille HTML: {len(html)} caractères")
                    
                    # Méthodes d'extraction dans l'ordre de préférence
                    patterns = [
                        # Meta property og:title (le plus fiable)
                        (r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']*)["\']', "og:title"),
                        # Meta name title
                        (r'<meta\s+name=["\']title["\']\s+content=["\']([^"\']*)["\']', "meta title"),
                        # JSON-LD structured data
                        (r'"videoDetails":\s*{[^}]*"title":\s*"([^"]*)"', "videoDetails JSON"),
                        # Page title
                        (r'<title>([^<]+?)\s*(?:-\s*YouTube)?</title>', "page title"),
                        # Alternate patterns
                        (r'<meta\s+property="twitter:title"\s+content="([^"]*)"', "twitter:title"),
                        (r'"title":{"runs":\[{"text":"([^"]*)"', "runs title"),
                    ]
                    
                    for pattern, method_name in patterns:
                        matches = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
                        if matches:
                            for match in matches:
                                title = match.strip()
                                if title and len(title) > 3:
                                    # Nettoie le titre
                                    cleaned_title = self._clean_youtube_title(title)
                                    if len(cleaned_title) > 3:
                                        print(f"✅ Titre trouvé via {method_name}: '{cleaned_title}'")
                                        return cleaned_title
                    
                    # Si aucun pattern ne fonctionne, cherche toute balise title
                    title_search = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
                    if title_search:
                        raw_title = title_search.group(1).strip()
                        cleaned_title = self._clean_youtube_title(raw_title)
                        if len(cleaned_title) > 3:
                            print(f"✅ Titre trouvé via title fallback: '{cleaned_title}'")
                            return cleaned_title
                    
                    print("❌ Aucun titre trouvé dans le HTML")
                    # Debug: sauvegarde un extrait pour analyse
                    if "youtube" in html.lower():
                        print("📝 Page semble être YouTube mais titre non trouvé")
                        # Recherche toute occurrence de "title" pour debug
                        title_occurrences = re.findall(r'title[^>]*>([^<]{10,100})', html, re.IGNORECASE)
                        for i, occurrence in enumerate(title_occurrences[:3]):
                            print(f"🔍 Debug title {i+1}: {occurrence[:50]}...")
                    
                    return None
                    
        except asyncio.TimeoutError:
            print("⏰ Timeout lors de la récupération du titre YouTube")
            return None
        except Exception as e:
            print(f"💥 Erreur récupération titre YouTube: {type(e).__name__}: {e}")
            return None

    def _clean_youtube_title(self, title: str) -> str:
        """Nettoie spécifiquement les titres YouTube"""
        if not title:
            return ""
        
        # Décode les entités HTML
        import html
        title = html.unescape(title)
        
        # Supprime les suffixes YouTube communs
        suffixes_to_remove = [
            r'\s*-\s*YouTube\s*$',
            r'\s*\|\s*YouTube\s*$',
            r'\s*•\s*YouTube\s*$',
            r'\s*-\s*Video\s*$',
        ]
        
        for suffix in suffixes_to_remove:
            title = re.sub(suffix, '', title, flags=re.IGNORECASE)
        
        # Nettoie les espaces et caractères indésirables
        title = re.sub(r'\s+', ' ', title).strip()
        title = re.sub(r'^[^\w]+|[^\w]+$', '', title)  # Supprime la ponctuation au début/fin
        
        return title

    async def _create_thread_simplified(self, message: discord.Message, platforms: list, urls: dict, config: dict):
        """Version simplifiée de création de thread"""
        try:
            thread_name = ""
            author_name = message.author.display_name
            
            print(f"🧵 Création thread pour: {platforms}")
            print(f"📋 Config fetch_titles: {config['fetch_titles']}")
            
            # Logique simplifiée selon la plateforme
            if "youtube" in platforms and config["fetch_titles"]:
                # Pour YouTube : essaie de récupérer le titre
                url = urls.get("youtube")
                print(f"🎬 Traitement YouTube avec URL: {url}")
                if url:
                    title = await self._get_youtube_title(url)
                    if title and len(title.strip()) > 0:
                        # Tronque si nécessaire
                        max_length = config.get('max_title_length', 80)
                        if len(title) > max_length:
                            title = title[:max_length-3] + "..."
                        
                        # Utilise le format configuré
                        try:
                            thread_name = config["thread_name_format"].format(
                                title=title,
                                platform="YouTube",
                                author=author_name
                            )
                        except KeyError:
                            thread_name = title
                        
                        print(f"🎬 Thread YouTube avec titre: '{thread_name}'")
                    else:
                        print(f"❌ Aucun titre récupéré, utilisation du fallback")
            
            # Si pas de titre YouTube ou autres plateformes
            if not thread_name or len(thread_name.strip()) == 0:
                if len(platforms) == 1:
                    platform = platforms[0]
                    if platform in ["instagram", "tiktok"]:
                        thread_name = f"Thread de {author_name}"
                        print(f"📱 Thread {platform}: '{thread_name}'")
                    elif platform == "youtube":
                        thread_name = f"Vidéo de {author_name}"
                        print(f"🎬 Thread YouTube (fallback): '{thread_name}'")
                else:
                    # Plusieurs plateformes
                    thread_name = f"Thread de {author_name}"
                    print(f"🔀 Thread multi-plateformes: '{thread_name}'")
            
            # Nettoie le nom pour Discord
            thread_name = re.sub(r'[<>:"/\\|?*]', '', thread_name)
            thread_name = re.sub(r'\s+', ' ', thread_name).strip()
            
            if len(thread_name) > 100:
                thread_name = thread_name[:97] + "..."
            
            if len(thread_name) < 1:
                thread_name = f"Thread de {author_name}"
            
            print(f"🎯 Nom final: '{thread_name}'")
            
            # Crée le thread
            thread = await message.create_thread(
                name=thread_name,
                auto_archive_duration=1440
            )
            
            # Message d'introduction adapté
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
            
        except discord.HTTPException as e:
            print(f"💥 Erreur création thread: {e}")
        except Exception as e:
            print(f"💥 Erreur inattendue: {e}")
            import traceback
            traceback.print_exc()

    def cog_unload(self):
        """Nettoyage lors du déchargement du cog"""
        pass


async def setup(bot):
    await bot.add_cog(SocialThreadOpener(bot))
