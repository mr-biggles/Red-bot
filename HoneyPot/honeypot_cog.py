import asyncio
import logging
from typing import Optional, Union

import discord
from discord.ext import tasks
from redbot.core import Config, checks, commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box, pagify

log = logging.getLogger("red.honeypot")


class Honeypot(commands.Cog):
    """
    Un cog honeypot pour attraper les utilisateurs indésirables.
    Surveille les channels désignés et effectue des actions automatiques.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=261543945, force_registration=True
        )

        default_guild = {
            "honeypot_channels": [],
            "action": "ban",  # ban, kick, mute, delete_only
            "log_channel": None,
            "auto_delete": True,
            "mute_role": None,
            "notification_message": "🍯 Honeypot déclenché par {user} dans {channel}",
            "dm_user": True,
            "dm_message": "Vous avez déclenché un honeypot sur {guild}. Votre message a été supprimé.",
            "excluded_roles": [],
            "excluded_users": [],
            "cooldown": 5,  # secondes entre les actions
        }

        default_member = {
            "triggered_count": 0,
            "last_trigger": 0,
        }

        self.config.register_guild(**default_guild)
        self.config.register_member(**default_member)
        
        # Cache pour éviter le spam
        self.action_cache = {}
        
    def format_help_for_context(self, ctx: commands.Context) -> str:
        """Format d'aide du cog."""
        return f"{super().format_help_for_context(ctx)}\n\nVersion: 2.0.0"

    @commands.group(name="honeypot", aliases=["hp"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def honeypot(self, ctx: commands.Context) -> None:
        """
        Commandes pour gérer le système honeypot.
        
        Un honeypot surveille certains channels et déclenche des actions
        automatiques quand des utilisateurs y postent des messages.
        """
        pass

    @honeypot.command(name="addchannel", aliases=["add"])
    async def honeypot_add_channel(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """Ajouter un channel au système honeypot."""
        async with self.config.guild(ctx.guild).honeypot_channels() as channels:
            if channel.id in channels:
                await ctx.send(f"❌ {channel.mention} est déjà un honeypot.")
                return
            channels.append(channel.id)
        
        await ctx.send(f"✅ {channel.mention} ajouté aux honeypots.")
        log.info(f"Channel {channel.id} ajouté aux honeypots sur {ctx.guild.id}")

    @honeypot.command(name="removechannel", aliases=["remove", "rem"])
    async def honeypot_remove_channel(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """Retirer un channel du système honeypot."""
        async with self.config.guild(ctx.guild).honeypot_channels() as channels:
            if channel.id not in channels:
                await ctx.send(f"❌ {channel.mention} n'est pas un honeypot.")
                return
            channels.remove(channel.id)
        
        await ctx.send(f"✅ {channel.mention} retiré des honeypots.")
        log.info(f"Channel {channel.id} retiré des honeypots sur {ctx.guild.id}")

    @honeypot.command(name="listchannels", aliases=["list"])
    async def honeypot_list_channels(self, ctx: commands.Context) -> None:
        """Lister tous les channels honeypot."""
        channels = await self.config.guild(ctx.guild).honeypot_channels()
        if not channels:
            await ctx.send("❌ Aucun channel honeypot configuré.")
            return
        
        channel_list = []
        for channel_id in channels:
            channel = ctx.guild.get_channel(channel_id)
            if channel:
                channel_list.append(f"• {channel.mention}")
            else:
                channel_list.append(f"• Channel supprimé (ID: {channel_id})")
        
        embed = discord.Embed(
            title="🍯 Channels Honeypot",
            description="\n".join(channel_list),
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)

    @honeypot.command(name="action")
    async def honeypot_action(self, ctx: commands.Context, action: str) -> None:
        """
        Définir l'action à effectuer quand un honeypot est déclenché.
        
        Actions disponibles:
        - ban: Bannir l'utilisateur
        - kick: Expulser l'utilisateur  
        - mute: Mute l'utilisateur (nécessite un rôle mute configuré)
        - delete_only: Supprimer seulement le message
        """
        valid_actions = ["ban", "kick", "mute", "delete_only"]
        
        if action.lower() not in valid_actions:
            await ctx.send(f"❌ Action invalide. Actions disponibles: {', '.join(valid_actions)}")
            return
        
        await self.config.guild(ctx.guild).action.set(action.lower())
        await ctx.send(f"✅ Action définie sur: **{action.lower()}**")

    @honeypot.command(name="muterole")
    async def honeypot_mute_role(self, ctx: commands.Context, role: discord.Role) -> None:
        """Définir le rôle utilisé pour mute les utilisateurs."""
        await self.config.guild(ctx.guild).mute_role.set(role.id)
        await ctx.send(f"✅ Rôle mute défini sur: {role.mention}")

    @honeypot.command(name="logchannel")
    async def honeypot_log_channel(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None) -> None:
        """Définir le channel de logs (ou None pour désactiver)."""
        if channel is None:
            await self.config.guild(ctx.guild).log_channel.set(None)
            await ctx.send("✅ Channel de logs désactivé.")
        else:
            await self.config.guild(ctx.guild).log_channel.set(channel.id)
            await ctx.send(f"✅ Channel de logs défini sur: {channel.mention}")

    @honeypot.command(name="autodelete")
    async def honeypot_auto_delete(self, ctx: commands.Context, enabled: bool) -> None:
        """Activer/désactiver la suppression automatique des messages."""
        await self.config.guild(ctx.guild).auto_delete.set(enabled)
        status = "activée" if enabled else "désactivée"
        await ctx.send(f"✅ Suppression automatique {status}.")

    @honeypot.command(name="exclude")
    async def honeypot_exclude(self, ctx: commands.Context, target: Union[discord.Role, discord.Member]) -> None:
        """Exclure un rôle ou utilisateur du système honeypot."""
        if isinstance(target, discord.Role):
            async with self.config.guild(ctx.guild).excluded_roles() as roles:
                if target.id not in roles:
                    roles.append(target.id)
                    await ctx.send(f"✅ Rôle {target.mention} exclu des honeypots.")
                else:
                    await ctx.send(f"❌ Rôle {target.mention} déjà exclu.")
        else:
            async with self.config.guild(ctx.guild).excluded_users() as users:
                if target.id not in users:
                    users.append(target.id)
                    await ctx.send(f"✅ Utilisateur {target.mention} exclu des honeypots.")
                else:
                    await ctx.send(f"❌ Utilisateur {target.mention} déjà exclu.")

    @honeypot.command(name="unexclude")
    async def honeypot_unexclude(self, ctx: commands.Context, target: Union[discord.Role, discord.Member]) -> None:
        """Retirer l'exclusion d'un rôle ou utilisateur."""
        if isinstance(target, discord.Role):
            async with self.config.guild(ctx.guild).excluded_roles() as roles:
                if target.id in roles:
                    roles.remove(target.id)
                    await ctx.send(f"✅ Rôle {target.mention} plus exclu des honeypots.")
                else:
                    await ctx.send(f"❌ Rôle {target.mention} n'était pas exclu.")
        else:
            async with self.config.guild(ctx.guild).excluded_users() as users:
                if target.id in users:
                    users.remove(target.id)
                    await ctx.send(f"✅ Utilisateur {target.mention} plus exclu des honeypots.")
                else:
                    await ctx.send(f"❌ Utilisateur {target.mention} n'était pas exclu.")

    @honeypot.command(name="settings", aliases=["config"])
    async def honeypot_settings(self, ctx: commands.Context) -> None:
        """Afficher la configuration actuelle du honeypot."""
        config = await self.config.guild(ctx.guild).all()
        
        # Channels
        channels = []
        for channel_id in config["honeypot_channels"]:
            channel = ctx.guild.get_channel(channel_id)
            if channel:
                channels.append(channel.mention)
            else:
                channels.append(f"Channel supprimé (ID: {channel_id})")
        
        # Log channel
        log_channel = "Désactivé"
        if config["log_channel"]:
            log_ch = ctx.guild.get_channel(config["log_channel"])
            log_channel = log_ch.mention if log_ch else "Channel supprimé"
        
        # Mute role
        mute_role = "Non configuré"
        if config["mute_role"]:
            role = ctx.guild.get_role(config["mute_role"])
            mute_role = role.mention if role else "Rôle supprimé"
        
        embed = discord.Embed(
            title="🍯 Configuration Honeypot",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="Channels Honeypot",
            value="\n".join(channels) if channels else "Aucun",
            inline=False
        )
        
        embed.add_field(name="Action", value=config["action"], inline=True)
        embed.add_field(name="Channel de logs", value=log_channel, inline=True)
        embed.add_field(name="Suppression auto", value="✅" if config["auto_delete"] else "❌", inline=True)
        embed.add_field(name="Rôle mute", value=mute_role, inline=True)
        embed.add_field(name="DM utilisateur", value="✅" if config["dm_user"] else "❌", inline=True)
        embed.add_field(name="Cooldown", value=f"{config['cooldown']}s", inline=True)
        
        await ctx.send(embed=embed)

    async def is_user_excluded(self, member: discord.Member) -> bool:
        """Vérifier si un utilisateur est exclu du système honeypot."""
        config = await self.config.guild(member.guild).all()
        
        # Vérifier utilisateurs exclus
        if member.id in config["excluded_users"]:
            return True
        
        # Vérifier rôles exclus
        user_role_ids = [role.id for role in member.roles]
        if any(role_id in config["excluded_roles"] for role_id in user_role_ids):
            return True
        
        return False

    async def log_honeypot_trigger(self, member: discord.Member, channel: discord.TextChannel, message: discord.Message, action_taken: str) -> None:
        """Logger le déclenchement d'un honeypot."""
        config = await self.config.guild(member.guild).all()
        log_channel_id = config["log_channel"]
        
        if not log_channel_id:
            return
        
        log_channel = member.guild.get_channel(log_channel_id)
        if not log_channel:
            return
        
        # Incrémenter le compteur
        async with self.config.member(member).all() as member_data:
            member_data["triggered_count"] += 1
            member_data["last_trigger"] = message.created_at.timestamp()
        
        member_data = await self.config.member(member).all()
        
        embed = discord.Embed(
            title="🍯 Honeypot Déclenché",
            color=discord.Color.red(),
            timestamp=message.created_at
        )
        
        embed.add_field(name="Utilisateur", value=f"{member} ({member.id})", inline=True)
        embed.add_field(name="Channel", value=channel.mention, inline=True)
        embed.add_field(name="Action", value=action_taken, inline=True)
        embed.add_field(name="Nombre de déclenchements", value=member_data["triggered_count"], inline=True)
        
        if message.content:
            content = message.content[:1000] + "..." if len(message.content) > 1000 else message.content
            embed.add_field(name="Message", value=f"```{content}```", inline=False)
        
        if message.attachments:
            attachments = [att.filename for att in message.attachments]
            embed.add_field(name="Pièces jointes", value=", ".join(attachments), inline=False)
        
        try:
            await log_channel.send(embed=embed)
        except discord.HTTPException:
            log.error(f"Impossible d'envoyer le log dans {log_channel_id}")

    async def send_dm_to_user(self, member: discord.Member, guild: discord.Guild) -> None:
        """Envoyer un DM à l'utilisateur."""
        config = await self.config.guild(guild).all()
        
        if not config["dm_user"]:
            return
        
        dm_message = config["dm_message"].format(
            user=str(member),
            guild=guild.name
        )
        
        try:
            await member.send(dm_message)
        except discord.HTTPException:
            log.warning(f"Impossible d'envoyer un DM à {member} ({member.id})")

    async def execute_action(self, member: discord.Member, channel: discord.TextChannel, message: discord.Message, action: str) -> str:
        """Exécuter l'action configurée."""
        try:
            if action == "ban":
                await member.ban(reason="Honeypot déclenché", delete_message_days=0)
                return "Utilisateur banni"
            
            elif action == "kick":
                await member.kick(reason="Honeypot déclenché")
                return "Utilisateur expulsé"
            
            elif action == "mute":
                mute_role_id = await self.config.guild(member.guild).mute_role()
                if not mute_role_id:
                    return "Rôle mute non configuré"
                
                mute_role = member.guild.get_role(mute_role_id)
                if not mute_role:
                    return "Rôle mute introuvable"
                
                await member.add_roles(mute_role, reason="Honeypot déclenché")
                return "Utilisateur mute"
            
            elif action == "delete_only":
                return "Message supprimé uniquement"
            
            else:
                return "Action inconnue"
                
        except discord.HTTPException as e:
            log.error(f"Erreur lors de l'exécution de l'action {action}: {e}")
            return f"Erreur lors de l'action: {str(e)}"

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Écouter les messages dans les channels honeypot."""
        # Ignorer les bots et les DMs
        if not message.guild or message.author.bot:
            return
        
        # Vérifier si c'est un channel honeypot
        honeypot_channels = await self.config.guild(message.guild).honeypot_channels()
        if message.channel.id not in honeypot_channels:
            return
        
        # Vérifier si l'utilisateur est exclu
        if await self.is_user_excluded(message.author):
            return
        
        # Vérifier le cooldown
        cache_key = f"{message.guild.id}_{message.author.id}"
        import time
        current_time = time.time()
        cooldown = await self.config.guild(message.guild).cooldown()
        
        if cache_key in self.action_cache:
            if current_time - self.action_cache[cache_key] < cooldown:
                return
        
        self.action_cache[cache_key] = current_time
        
        # Supprimer le message si configuré
        auto_delete = await self.config.guild(message.guild).auto_delete()
        if auto_delete:
            try:
                await message.delete()
            except discord.HTTPException:
                log.warning(f"Impossible de supprimer le message {message.id}")
        
        # Exécuter l'action
        action = await self.config.guild(message.guild).action()
        action_result = await self.execute_action(message.author, message.channel, message, action)
        
        # Envoyer DM à l'utilisateur
        await self.send_dm_to_user(message.author, message.guild)
        
        # Logger l'événement
        await self.log_honeypot_trigger(message.author, message.channel, message, action_result)
        
        log.info(f"Honeypot déclenché par {message.author} ({message.author.id}) dans {message.channel} - Action: {action_result}")

    def cog_unload(self) -> None:
        """Nettoyage lors du déchargement du cog."""
        self.action_cache.clear()


def setup(bot: Red) -> None:
    """Charger le cog."""
    bot.add_cog(Honeypot(bot))