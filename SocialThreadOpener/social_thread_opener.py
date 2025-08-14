import re
import asyncio
from typing import Optional
import discord
from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import humanize_list


class SocialThreadOpener(commands.Cog):
    """
    Crée automatiquement des threads pour les liens YouTube, TikTok et Instagram
    """

    __version__ = "1.0.0"

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=208903205982044161, force_registration=True
        )
        
        default_guild = {
            "enabled": False,
            "channels": [],
            "thread_name_format": "Discussion: {platform}",
            "delay": 2,  # Délai en secondes avant création du thread
            "platforms": {
                "youtube": True,
                "tiktok": True,
                "instagram": True
            }
        }
        
        self.config.register_guild(**default_guild)
        
        # Expressions régulières pour détecter les liens
        self.url_patterns = {
            "youtube": re.compile(
                r'(?:https?://)?(?:www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[a-zA-Z0-9_-]+',
                re.IGNORECASE
            ),
            "tiktok": re.compile(
                r'(?:https?://)?(?:www\.)?(tiktok\.com/@[^/]+/video/\d+|vm\.tiktok\.com/[a-zA-Z0-9]+)',
                re.IGNORECASE
            ),
            "instagram": re.compile(
                r'(?:https?://)?(?:www\.)?(instagram\.com/p/[a-zA-Z0-9_-]+|instagram\.com/reel/[a-zA-Z0-9_-]+)',
                re.IGNORECASE
            )
        }

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
        Variables disponibles: {platform}, {author}
        Exemple: Discussion: {platform} par {author}
        """
        await self.config.guild(ctx.guild).thread_name_format.set(format_string)
        await ctx.send(f"✅ Format des noms de threads défini: `{format_string}`")

    @social_thread.command(name="delay")
    async def set_delay(self, ctx, seconds: int):
        """Définit le délai avant création du thread (en secondes)"""
        if seconds < 0 or seconds > 60:
            await ctx.send("❌ Le délai doit être entre 0 et 60 secondes!")
            return
        
        await self.config.guild(ctx.guild).delay.set(seconds)
        await ctx.send(f"✅ Délai défini à {seconds} secondes!")

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
            for channel_id in channels_ids[:5]:  # Limite à 5 pour l'affichage
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
        # Ignore les bots et les messages sans guild
        if message.author.bot or not message.guild:
            return
        
        guild_config = await self.config.guild(message.guild).all()
        
        # Vérifie si le cog est activé
        if not guild_config["enabled"]:
            return
        
        # Vérifie si le canal est surveillé
        if guild_config["channels"] and message.channel.id not in guild_config["channels"]:
            return
        
        # Vérifie si c'est un thread (on ne crée pas de threads dans les threads)
        if isinstance(message.channel, discord.Thread):
            return
        
        # Vérifie les permissions
        if not message.channel.permissions_for(message.guild.me).create_public_threads:
            return
        
        # Détecte les plateformes dans le message
        detected_platforms = []
        for platform, pattern in self.url_patterns.items():
            if guild_config["platforms"][platform] and pattern.search(message.content):
                detected_platforms.append(platform)
        
        if not detected_platforms:
            return
        
        # Attend le délai configuré
        if guild_config["delay"] > 0:
            await asyncio.sleep(guild_config["delay"])
        
        # Crée le thread
        await self._create_thread(message, detected_platforms, guild_config)

    async def _create_thread(self, message: discord.Message, platforms: list, config: dict):
        """Crée un thread pour le message"""
        try:
            # Détermine le nom du thread
            platform_name = platforms[0].title() if len(platforms) == 1 else f"{len(platforms)} plateformes"
            
            thread_name = config["thread_name_format"].format(
                platform=platform_name,
                author=message.author.display_name
            )
            
            # Limite la longueur du nom (Discord limite à 100 caractères)
            if len(thread_name) > 100:
                thread_name = thread_name[:97] + "..."
            
            # Crée le thread
            thread = await message.create_thread(
                name=thread_name,
                auto_archive_duration=1440  # 24 heures
            )
            
            # Message d'introduction optionnel
            platform_list = ", ".join([p.title() for p in platforms])
            intro_message = f"Thread créé automatiquement pour discuter du contenu {platform_list} partagé par {message.author.mention}!"
            
            await thread.send(intro_message)
            
        except discord.HTTPException as e:
            # Log l'erreur sans faire planter le bot
            print(f"Erreur lors de la création du thread: {e}")
        except Exception as e:
            print(f"Erreur inattendue dans Social Thread Opener: {e}")

    def cog_unload(self):
        """Nettoyage lors du déchargement du cog"""
        pass


async def setup(bot):
    await bot.add_cog(SocialThreadOpener(bot))