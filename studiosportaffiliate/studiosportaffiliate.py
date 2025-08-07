import discord
from redbot.core import commands, Config
import re


class StudiosportAffiliate(commands.Cog):
    """
    COG pour poster automatiquement un lien affilié quand quelqu'un poste un lien studiosport.fr
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)
        
        default_guild = {
            "affiliate_link": "https://www.studiosport.fr/?utm_source=bandolovers&utm_medium=affiliation&utm_campaign=affi-bandolovers",
            "enabled": True,
            "channels": []  # Liste vide = tous les canaux
        }
        
        self.config.register_guild(**default_guild)
        
    @commands.Cog.listener()
    async def on_message(self, message):
        """Surveille les messages pour détecter les liens studiosport.fr"""
        
        # Ignorer les messages du bot
        if message.author.bot:
            return
            
        # Vérifier si le COG est activé pour ce serveur
        if not message.guild:
            return
            
        enabled = await self.config.guild(message.guild).enabled()
        if not enabled:
            return
            
        # Vérifier si le canal est autorisé (si la liste n'est pas vide)
        allowed_channels = await self.config.guild(message.guild).channels()
        if allowed_channels and message.channel.id not in allowed_channels:
            return
        
        # Regex pour détecter les liens studiosport.fr
        studiosport_pattern = r'https?://(?:www\.)?studiosport\.fr[^\s]*'
        
        if re.search(studiosport_pattern, message.content, re.IGNORECASE):
            affiliate_link = await self.config.guild(message.guild).affiliate_link()
            
            # Message de réponse
            response_message = (
                "N'oublie pas de passer par notre lien affilié, si tu as déjà fait ton panier, "
                "n'hésite pas à le refaire après avoir cliqué sur le lien. Merci.\n\n"
                f"{affiliate_link}"
            )
            
            try:
                await message.channel.send(response_message)
            except discord.HTTPException:
                pass  # Ignorer les erreurs d'envoi
    
    @commands.group(name="studiosport")
    @commands.admin()
    async def studiosport_group(self, ctx):
        """Commandes pour configurer StudiosportAffiliate (Admin seulement)"""
        pass
    
    @studiosport_group.command(name="setlink")
    async def set_affiliate_link(self, ctx, *, link: str):
        """Définir le lien affilié (Admin seulement)"""
        await self.config.guild(ctx.guild).affiliate_link.set(link)
        await ctx.send(f"✅ Lien affilié configuré : {link}")
    
    @studiosport_group.command(name="getlink")
    async def get_affiliate_link(self, ctx):
        """Voir le lien affilié actuel"""
        link = await self.config.guild(ctx.guild).affiliate_link()
        await ctx.send(f"📎 Lien affilié actuel : {link}")
    
    @studiosport_group.command(name="toggle")
    async def toggle_affiliate(self, ctx):
        """Activer/désactiver le COG"""
        current = await self.config.guild(ctx.guild).enabled()
        await self.config.guild(ctx.guild).enabled.set(not current)
        status = "activé" if not current else "désactivé"
        await ctx.send(f"✅ StudiosportAffiliate {status}")
    
    @studiosport_group.command(name="addchannel")
    async def add_channel(self, ctx, channel: discord.TextChannel = None):
        """Ajouter un canal autorisé (laisser vide pour le canal actuel)"""
        if not channel:
            channel = ctx.channel
            
        async with self.config.guild(ctx.guild).channels() as channels:
            if channel.id not in channels:
                channels.append(channel.id)
                await ctx.send(f"✅ Canal {channel.mention} ajouté à la liste")
            else:
                await ctx.send(f"❌ Canal {channel.mention} déjà dans la liste")
    
    @studiosport_group.command(name="removechannel")
    async def remove_channel(self, ctx, channel: discord.TextChannel = None):
        """Retirer un canal de la liste autorisée"""
        if not channel:
            channel = ctx.channel
            
        async with self.config.guild(ctx.guild).channels() as channels:
            if channel.id in channels:
                channels.remove(channel.id)
                await ctx.send(f"✅ Canal {channel.mention} retiré de la liste")
            else:
                await ctx.send(f"❌ Canal {channel.mention} n'était pas dans la liste")
    
    @studiosport_group.command(name="listchannels")
    async def list_channels(self, ctx):
        """Voir la liste des canaux autorisés"""
        channels = await self.config.guild(ctx.guild).channels()
        
        if not channels:
            await ctx.send("📋 Aucun canal spécifique configuré (fonctionne sur tous les canaux)")
            return
            
        channel_mentions = []
        for channel_id in channels:
            channel = ctx.guild.get_channel(channel_id)
            if channel:
                channel_mentions.append(channel.mention)
            else:
                channel_mentions.append(f"Canal supprimé ({channel_id})")
        
        await ctx.send(f"📋 Canaux autorisés :\n" + "\n".join(channel_mentions))
    
    @studiosport_group.command(name="clearchannels")
    async def clear_channels(self, ctx):
        """Vider la liste des canaux (fonctionne sur tous les canaux)"""
        await self.config.guild(ctx.guild).channels.set([])
        await ctx.send("✅ Liste des canaux vidée. Le COG fonctionne maintenant sur tous les canaux.")
    
    @studiosport_group.command(name="status")
    async def show_status(self, ctx):
        """Afficher la configuration actuelle"""
        enabled = await self.config.guild(ctx.guild).enabled()
        link = await self.config.guild(ctx.guild).affiliate_link()
        channels = await self.config.guild(ctx.guild).channels()
        
        status_text = "✅ Activé" if enabled else "❌ Désactivé"
        channels_text = f"{len(channels)} canaux spécifiques" if channels else "Tous les canaux"
        
        embed = discord.Embed(title="StudiosportAffiliate - Configuration", color=0x00ff00 if enabled else 0xff0000)
        embed.add_field(name="Statut", value=status_text, inline=True)
        embed.add_field(name="Canaux", value=channels_text, inline=True)
        embed.add_field(name="Lien affilié", value=link, inline=False)
        
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(StudiosportAffiliate(bot))
