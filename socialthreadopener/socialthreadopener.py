import re
import asyncio
import aiohttp
import json
from typing import Optional
import discord
from redbot.core import commands, Config
from redbot.core.bot import Red

class SocialThreadOpener(commands.Cog):
    """Ouvre automatiquement des threads pour les liens sociaux"""
    
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        
        # Configuration par défaut
        default_guild = {
            "enabled_channels": [],
            "youtube": {"enabled": True, "emoji": "📺"},
            "tiktok": {"enabled": True, "emoji": "🎵"},
            "instagram": {"enabled": True, "emoji": "📸"},
            "facebook": {"enabled": True, "emoji": "👤"}
        }
        
        self.config.register_guild(**default_guild)
        
        # Patterns pour détecter les URLs
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
            ),
            "facebook": re.compile(
                r'(?:https?://)?(?:www\.)?(facebook\.com/(?:watch|reel|share|.*?/videos?|.*?/posts?)/[a-zA-Z0-9_-]+|fb\.watch/[a-zA-Z0-9_-]+)',
                re.IGNORECASE
            )
        }

    async def get_video_title(self, url: str, platform: str) -> Optional[str]:
        """Récupère le titre d'une vidéo"""
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return None
                    
                    content = await response.text()
                    
                    # Chercher différents patterns de titre
                    title_patterns = [
                        r'<title[^>]*>([^<]+)</title>',
                        r'"title":"([^"]*)"',
                        r'<meta[^>]*property="og:title"[^>]*content="([^"]*)"',
                        r'<meta[^>]*name="title"[^>]*content="([^"]*)"'
                    ]
                    
                    for pattern in title_patterns:
                        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
                        if match:
                            title = match.group(1).strip()
                            # Nettoyer le titre
                            title = re.sub(r'\s+', ' ', title)
                            title = title[:100] + "..." if len(title) > 100 else title
                            return title
                    
                    return None
        except Exception as e:
            print(f"Erreur lors de la récupération du titre: {e}")
            return None

    @commands.Cog.listener()
    async def on_message(self, message):
        """Écoute les messages pour détecter les liens sociaux"""
        if message.author.bot:
            return
            
        if not message.guild:
            return
        
        # Vérifier si le canal est activé
        enabled_channels = await self.config.guild(message.guild).enabled_channels()
        if message.channel.id not in enabled_channels:
            return
        
        # Détecter les liens
        detected_platforms = []
        for platform, pattern in self.url_patterns.items():
            if pattern.search(message.content):
                platform_config = await self.config.guild(message.guild).get_raw(platform)
                if platform_config["enabled"]:
                    detected_platforms.append((platform, platform_config["emoji"]))
        
        if not detected_platforms:
            return
        
        # Créer le thread
        try:
            # Récupérer le titre si possible
            title_parts = []
            for platform, emoji in detected_platforms:
                pattern = self.url_patterns[platform]
                match = pattern.search(message.content)
                if match:
                    full_url = match.group(0)
                    if not full_url.startswith('http'):
                        full_url = 'https://' + full_url
                    
                    video_title = await self.get_video_title(full_url, platform)
                    if video_title:
                        title_parts.append(f"{emoji} {video_title}")
                    else:
                        title_parts.append(f"{emoji} {platform.title()}")
            
            # Nom du thread
            if title_parts:
                thread_name = " | ".join(title_parts)
            else:
                platforms_str = " & ".join([f"{emoji} {platform.title()}" for platform, emoji in detected_platforms])
                thread_name = f"💬 Discussion {platforms_str}"
            
            # Limiter la longueur du nom
            if len(thread_name) > 100:
                thread_name = thread_name[:97] + "..."
            
            # Créer le thread
            thread = await message.create_thread(
                name=thread_name,
                auto_archive_duration=1440  # 24 heures
            )
            
            # Message de bienvenue
            welcome_messages = {
                "youtube": "Discutons de cette vidéo YouTube ! 🎬",
                "tiktok": "Que pensez-vous de ce TikTok ? 💃",
                "instagram": "Réagissons à ce post Instagram ! ✨",
                "facebook": "Parlons de ce contenu Facebook ! 💭"
            }
            
            if len(detected_platforms) == 1:
                platform, emoji = detected_platforms[0]
                welcome_msg = welcome_messages.get(platform, "Discutons de ce contenu !")
            else:
                welcome_msg = "Plusieurs contenus à discuter ! 🎉"
            
            await thread.send(welcome_msg)
            
        except discord.Forbidden:
            pass  # Pas de permissions
        except discord.HTTPException:
            pass  # Erreur Discord
        except Exception as e:
            print(f"Erreur lors de la création du thread: {e}")

    @commands.group(name="socialthread", aliases=["st"])
    @commands.admin_or_permissions(manage_guild=True)
    async def socialthread(self, ctx):
        """Commandes pour configurer l'ouverture automatique de threads"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @socialthread.command(name="add")
    async def add_channel(self, ctx, channel: discord.TextChannel = None):
        """Ajoute un canal à la liste des canaux surveillés"""
        if channel is None:
            channel = ctx.channel
        
        enabled_channels = await self.config.guild(ctx.guild).enabled_channels()
        
        if channel.id in enabled_channels:
            await ctx.send(f"❌ Le canal {channel.mention} est déjà surveillé !")
            return
        
        enabled_channels.append(channel.id)
        await self.config.guild(ctx.guild).enabled_channels.set(enabled_channels)
        
        await ctx.send(f"✅ Canal {channel.mention} ajouté à la surveillance des liens sociaux !")

    @socialthread.command(name="remove")
    async def remove_channel(self, ctx, channel: discord.TextChannel = None):
        """Retire un canal de la liste des canaux surveillés"""
        if channel is None:
            channel = ctx.channel
        
        enabled_channels = await self.config.guild(ctx.guild).enabled_channels()
        
        if channel.id not in enabled_channels:
            await ctx.send(f"❌ Le canal {channel.mention} n'est pas surveillé !")
            return
        
        enabled_channels.remove(channel.id)
        await self.config.guild(ctx.guild).enabled_channels.set(enabled_channels)
        
        await ctx.send(f"✅ Canal {channel.mention} retiré de la surveillance !")

    @socialthread.command(name="list")
    async def list_channels(self, ctx):
        """Affiche la liste des canaux surveillés"""
        enabled_channels = await self.config.guild(ctx.guild).enabled_channels()
        
        if not enabled_channels:
            await ctx.send("❌ Aucun canal n'est actuellement surveillé.")
            return
        
        channels_mention = []
        for channel_id in enabled_channels:
            channel = ctx.guild.get_channel(channel_id)
            if channel:
                channels_mention.append(channel.mention)
            else:
                channels_mention.append(f"Canal supprimé (ID: {channel_id})")
        
        embed = discord.Embed(
            title="📺 Canaux Surveillés",
            description="\n".join(f"• {channel}" for channel in channels_mention),
            color=discord.Color.blue()
        )
        
        await ctx.send(embed=embed)

    @socialthread.command(name="toggle")
    async def toggle_platform(self, ctx, platform: str):
        """Active/désactive une plateforme (youtube, tiktok, instagram, facebook)"""
        platform = platform.lower()
        valid_platforms = ["youtube", "tiktok", "instagram", "facebook"]
        
        if platform not in valid_platforms:
            await ctx.send(f"❌ Plateforme invalide ! Plateformes disponibles: {', '.join(valid_platforms)}")
            return
        
        current_state = await self.config.guild(ctx.guild).get_raw(platform, "enabled")
        new_state = not current_state
        
        await self.config.guild(ctx.guild).set_raw(platform, "enabled", value=new_state)
        
        status = "✅ activée" if new_state else "❌ désactivée"
        await ctx.send(f"Plateforme **{platform.title()}** {status} !")

    @socialthread.command(name="emoji")
    async def set_emoji(self, ctx, platform: str, emoji: str):
        """Change l'emoji d'une plateforme"""
        platform = platform.lower()
        valid_platforms = ["youtube", "tiktok", "instagram", "facebook"]
        
        if platform not in valid_platforms:
            await ctx.send(f"❌ Plateforme invalide ! Plateformes disponibles: {', '.join(valid_platforms)}")
            return
        
        await self.config.guild(ctx.guild).set_raw(platform, "emoji", value=emoji)
        await ctx.send(f"✅ Emoji pour **{platform.title()}** changé en {emoji} !")

    @socialthread.command(name="settings")
    async def show_settings(self, ctx):
        """Affiche les paramètres actuels"""
        guild_config = await self.config.guild(ctx.guild).all()
        
        embed = discord.Embed(
            title="⚙️ Paramètres SocialThread",
            color=discord.Color.green()
        )
        
        # Canaux surveillés
        if guild_config["enabled_channels"]:
            channels_list = []
            for channel_id in guild_config["enabled_channels"]:
                channel = ctx.guild.get_channel(channel_id)
                channels_list.append(channel.mention if channel else f"Canal supprimé ({channel_id})")
            embed.add_field(
                name="📺 Canaux Surveillés",
                value="\n".join(channels_list),
                inline=False
            )
        else:
            embed.add_field(
                name="📺 Canaux Surveillés",
                value="Aucun canal configuré",
                inline=False
            )
        
        # Plateformes
        platforms_info = []
        for platform in ["youtube", "tiktok", "instagram", "facebook"]:
            config = guild_config[platform]
            status = "✅" if config["enabled"] else "❌"
            platforms_info.append(f"{config['emoji']} **{platform.title()}**: {status}")
        
        embed.add_field(
            name="🌐 Plateformes",
            value="\n".join(platforms_info),
            inline=False
        )
        
        await ctx.send(embed=embed)

    @socialthread.command(name="test")
    async def test_detection(self, ctx, *, url: str):
        """Test la détection d'URL"""
        detected = []
        for platform, pattern in self.url_patterns.items():
            if pattern.search(url):
                detected.append(platform)
        
        if detected:
            await ctx.send(f"✅ URL détectée comme: **{', '.join(detected)}**")
        else:
            await ctx.send("❌ Aucune plateforme détectée dans cette URL")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Gère les réactions sur les messages de thread"""
        if payload.emoji.name == "🗑️":
            try:
                channel = self.bot.get_channel(payload.channel_id)
                if isinstance(channel, discord.Thread):
                    message = await channel.fetch_message(payload.message_id)
                    user = self.bot.get_user(payload.user_id)
                    
                    if user and not user.bot:
                        # Créer un bouton de suppression
                        view = discord.ui.View()
                        delete_button = discord.ui.Button(
                            label="Supprimer le thread",
                            style=discord.ButtonStyle.danger,
                            emoji="🗑️"
                        )
                        
                        async def delete_callback(interaction):
                            if interaction.user.guild_permissions.manage_threads or interaction.user == channel.owner:
                                await channel.delete()
                            else:
                                await interaction.response.send_message("❌ Vous n'avez pas la permission de supprimer ce thread.", ephemeral=True)
                        
                        delete_button.callback = delete_callback
                        view.add_item(delete_button)
                        
                        await message.reply("Voulez-vous vraiment supprimer ce thread ?", view=view)
            except:
                pass

# Interface de suppression de thread
class ThreadDeleteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label='Supprimer le thread', style=discord.ButtonStyle.danger, emoji='🗑️')
    async def delete_thread(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message("Cette commande ne fonctionne que dans un thread!", ephemeral=True)
            return
            
        # Vérifier les permissions
        if not (interaction.user.guild_permissions.manage_threads or 
                interaction.user == interaction.channel.owner or
                interaction.user.guild_permissions.administrator):
            await interaction.response.send_message("❌ Vous n'avez pas la permission de supprimer ce thread!", ephemeral=True)
            return
        
        # Supprimer le thread
        try:
            await interaction.channel.delete()
        except:
            await interaction.response.send_message("Message supprimé!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(SocialThreadOpener(bot))
