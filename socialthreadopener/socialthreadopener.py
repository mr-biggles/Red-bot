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

    __version__ = "1.1.1"

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
            "link_only_mode": False,
            "delete_non_links": False,
            "warning_message": "❌ Ce canal est réservé aux liens YouTube, TikTok et Instagram uniquement!",
            "whitelist_roles": [],
            "allow_media": True,
        }
        
        self.config.register_guild(**default_guild)
        
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

    @commands.group(name="socialthread", aliases=["st"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def social_thread(self, ctx):
        """Configuration du Social Thread Opener"""
        pass

    @social_thread.command(name="enable")
    async def enable_social_thread(self, ctx):
        """Active le Social Thread Opener"""
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send("✅ Social Thread Opener activé!")

    @social_thread.command(name="disable")
    async def disable_social_thread(self, ctx):
        """Désactive le Social Thread Opener"""
        await self.config.guild(ctx.guild).enabled.set(False)
        await ctx.send("❌ Social Thread Opener désactivé!")

    @social_thread.command(name="addchannel")
    async def add_channel(self, ctx, channel: discord.TextChannel = None):
        """Ajoute un canal à surveiller"""
        if channel is None:
            channel = ctx.channel
        
        async with self.config.guild(ctx.guild).channels() as channels:
            if channel.id not in channels:
                channels.append(channel.id)
                await ctx.send(f"✅ Canal {channel.mention} ajouté à la surveillance!")
            else:
                await ctx.send(f"⚠️ Canal {channel.mention} déjà surveillé!")

    @social_thread.command(name="removechannel")
    async def remove_channel(self, ctx, channel: discord.TextChannel = None):
        """Retire un canal de la surveillance"""
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
        """Active/désactive le mode 'liens uniquement'"""
        current = await self.config.guild(ctx.guild).delete_non_links()
        await self.config.guild(ctx.guild).delete_non_links.set(not current)
        
        if not current:
            await ctx.send("🔒 **Mode 'liens uniquement' ACTIVÉ!** Les messages sans liens seront supprimés.")
        else:
            await ctx.send("🔓 **Mode 'liens uniquement' désactivé.** Tous les messages sont autorisés.")

    @social_thread.command(name="settings")
    async def show_settings(self, ctx):
        """Affiche la configuration actuelle"""
        config = await self.config.guild(ctx.guild).all()
        
        embed = discord.Embed(title="⚙️ Configuration Social Thread Opener", color=0x2F3136)
        embed.add_field(name="🔧 État", value="✅ Activé" if config["enabled"] else "❌ Désactivé", inline=True)
        embed.add_field(name="🔒 Mode liens uniques", value="✅ Activé" if config["delete_non_links"] else "❌ Désactivé", inline=True)
        embed.add_field(name="📎 Médias autorisés", value="✅ Oui" if config["allow_media"] else "❌ Non", inline=True)
        
        if config["channels"]:
            channels = [f"<#{ch}>" for ch in config["channels"]]
            embed.add_field(name="📺 Canaux surveillés", value="\n".join(channels), inline=False)
        else:
            embed.add_field(name="📺 Canaux surveillés", value="Aucun canal configuré", inline=False)
        
        embed.add_field(name="⚠️ Message d'avertissement", value=config["warning_message"], inline=False)
        
        await ctx.send(embed=embed)

    @social_thread.command(name="test")
    async def test_config(self, ctx):
        """Teste la configuration actuelle"""
        config = await self.config.guild(ctx.guild).all()
        
        embed = discord.Embed(title="🧪 Test de Configuration", color=0x00ff00)
        
        # Tests
        tests = []
        if config["enabled"]:
            tests.append("✅ Cog activé")
        else:
            tests.append("❌ Cog désactivé")
        
        if config["channels"]:
            if ctx.channel.id in config["channels"]:
                tests.append("✅ Canal actuel surveillé")
            else:
                tests.append("⚠️ Canal actuel non surveillé")
        else:
            tests.append("⚠️ Aucun canal configuré")
        
        if config["delete_non_links"]:
            tests.append("✅ Mode liens uniquement activé")
        else:
            tests.append("ℹ️ Mode liens uniquement désactivé")
        
        # Permissions
        perms = ctx.channel.permissions_for(ctx.guild.me)
        if perms.manage_messages:
            tests.append("✅ Permission de gérer les messages")
        else:
            tests.append("❌ Pas de permission de gérer les messages")
            
        if perms.create_public_threads:
            tests.append("✅ Permission de créer des threads")
        else:
            tests.append("❌ Pas de permission de créer des threads")
        
        embed.description = "\n".join(tests)
        await ctx.send(embed=embed)

    def _has_social_media_links(self, message: discord.Message, guild_config: dict) -> bool:
        """Vérifie si le message contient des liens de médias sociaux configurés"""
        platforms = guild_config.get("platforms", {})
        
        for platform, enabled in platforms.items():
            if enabled and platform in self.url_patterns:
                if self.url_patterns[platform].search(message.content):
                    return True
        return False

    def _detect_social_links(self, message: discord.Message, guild_config: dict):
        """Détecte les liens de médias sociaux dans un message"""
        detected_platforms = []
        detected_urls = []
        platforms = guild_config.get("platforms", {})
        
        for platform, enabled in platforms.items():
            if enabled and platform in self.url_patterns:
                matches = self.url_patterns[platform].findall(message.content)
                if matches:
                    detected_platforms.append(platform)
                    detected_urls.extend(matches)
        
        return detected_platforms, detected_urls

    async def _is_user_exempt(self, message: discord.Message, guild_config: dict) -> bool:
        """Vérifie si un utilisateur est exempté des restrictions"""
        # Admins et modérateurs sont toujours exemptés
        if message.author.guild_permissions.manage_messages:
            return True
        
        # Vérification des rôles whitelist
        whitelist_roles = guild_config.get("whitelist_roles", [])
        if whitelist_roles:
            user_role_ids = [role.id for role in message.author.roles]
            if any(role_id in user_role_ids for role_id in whitelist_roles):
                return True
        
        return False

    async def _delete_and_warn(self, message: discord.Message, guild_config: dict):
        """Supprime un message et envoie un avertissement"""
        try:
            warning_msg = guild_config.get("warning_message", "❌ Ce canal est réservé aux liens uniquement!")
            
            # Suppression du message
            await message.delete()
            
            # Avertissement éphémère (via DM car pas de slash command)
            try:
                embed = discord.Embed(
                    title="⚠️ Message supprimé",
                    description=warning_msg,
                    color=0xff4444
                )
                embed.add_field(
                    name="📝 Votre message",
                    value=f"```{message.content[:500]}{'...' if len(message.content) > 500 else ''}```",
                    inline=False
                )
                embed.add_field(
                    name="📍 Dans le canal",
                    value=message.channel.mention,
                    inline=True
                )
                
                await message.author.send(embed=embed)
            except discord.Forbidden:
                # Si on ne peut pas DM, on envoie un message temporaire
                temp_msg = await message.channel.send(
                    f"{message.author.mention}, {warning_msg}",
                    delete_after=10
                )
        
        except Exception as e:
            print(f"Erreur suppression/avertissement: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Gère la modération ET la création de threads"""
        print(f"🔍 MESSAGE REÇU: '{message.content[:50]}...' de {message.author.display_name}")
        
        if message.author.bot:
            print("❌ Message de bot - ignoré")
            return
            
        if not message.guild:
            print("❌ Pas de serveur - ignoré")
            return
        
        guild_config = await self.config.guild(message.guild).all()
        print(f"⚙️ Config loaded: enabled={guild_config['enabled']}")
        
        if not guild_config["enabled"]:
            print("❌ Cog désactivé - ignoré")
            return
        
        print(f"📋 Canaux surveillés: {guild_config['channels']}")
        print(f"💬 Canal actuel: {message.channel.id}")
        
        if guild_config["channels"] and message.channel.id not in guild_config["channels"]:
            print("❌ Canal non surveillé - ignoré")
            return
        
        if isinstance(message.channel, discord.Thread):
            print("❌ Dans un thread - ignoré")
            return
        
        print(f"🤖 Permissions bot: manage_messages={message.channel.permissions_for(message.guild.me).manage_messages}")
        print(f"🧵 Permissions bot: create_threads={message.channel.permissions_for(message.guild.me).create_public_threads}")
        
        if not message.channel.permissions_for(message.guild.me).manage_messages:
            print("❌ Pas de permission manage_messages")
            return
            
        if not message.channel.permissions_for(message.guild.me).create_public_threads:
            print("❌ Pas de permission create_threads")
            return
        
        print(f"🔍 Analyse du message: '{message.content[:100]}...'")
        
        # MODÉRATION EN PREMIER
        delete_non_links = guild_config.get("delete_non_links", False)
        print(f"🔒 Mode liens uniquement ACTIF: {delete_non_links}")
        
        if delete_non_links:
            print("🔒 DÉBUT DE LA MODÉRATION")
            
            is_exempt = await self._is_user_exempt(message, guild_config)
            print(f"👑 Utilisateur exempté: {is_exempt}")
            
            if not is_exempt:
                has_social_links = self._has_social_media_links(message, guild_config)
                print(f"🔗 Message a des liens sociaux: {has_social_links}")
                
                if not has_social_links:
                    has_media = bool(message.attachments or message.embeds)
                    allow_media = guild_config.get("allow_media", True)
                    print(f"📎 A des médias: {has_media}, médias autorisés: {allow_media}")
                    
                    if not (has_media and allow_media):
                        print("🗑️ MESSAGE VA ÊTRE SUPPRIMÉ!")
                        await self._delete_and_warn(message, guild_config)
                        return
                    else:
                        print("✅ Message avec médias autorisé")
                else:
                    print("✅ Message avec liens sociaux autorisé")
            else:
                print("✅ Utilisateur exempté - message autorisé")
        else:
            print("🔓 Mode liens uniquement INACTIF")
        
        # CRÉATION DE THREADS
        print("🧵 VÉRIFICATION POUR THREADS...")
        detected_platforms, detected_urls = self._detect_social_links(message, guild_config)
        
        if detected_platforms:
            print(f"📱 Plateformes détectées pour thread: {detected_platforms}")
            
            if guild_config["delay"] > 0:
                await asyncio.sleep(guild_config["delay"])
            
            await self._create_thread_simplified(message, detected_platforms, detected_urls, guild_config)
        else:
            print("❌ Aucune plateforme détectée pour thread")

    async def _create_thread_simplified(self, message: discord.Message, platforms: list, urls: list, guild_config: dict):
        """Version simplifiée pour créer un thread"""
        try:
            author_name = message.author.display_name
            
            if len(platforms) == 1:
                platform = platforms[0]
                thread_name = f"{platform.title()} - {author_name}"
            else:
                thread_name = f"Thread de {author_name}"
            
            # Nettoyage du nom
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
            
            # Message d'introduction
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
            print(f"🎉 Thread '{thread_name}' créé!")
            
        except Exception as e:
            print(f"💥 Erreur thread: {e}")


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
