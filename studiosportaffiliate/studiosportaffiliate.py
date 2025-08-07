import re
import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

class StudiosportAffiliate(commands.Cog):
    """
    COG pour transformer automatiquement les liens StudioSport en liens d'affiliation
    """
    
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        
        # Configuration par défaut
        default_guild = {
            "enabled": True,
            "utm_source": "bandolovers",
            "utm_medium": "affiliation", 
            "utm_campaign": "affi-bandolovers",
            "message": "N'hésite pas à passer par notre lien partenaire StudioSport ! 🎯"
        }
        
        self.config.register_guild(**default_guild)
        
        # Pattern pour détecter les liens StudioSport
        self.studiosport_pattern = re.compile(
            r'https?://(?:www\.)?studiosport\.fr/[^\s]+',
            re.IGNORECASE
        )
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Écoute tous les messages pour détecter les liens StudioSport
        """
        # Ignore les messages du bot
        if message.author.bot:
            return
            
        # Ignore les messages sans serveur (MP)
        if not message.guild:
            return
            
        # Vérifie si le COG est activé sur ce serveur
        if not await self.config.guild(message.guild).enabled():
            return
            
        # Cherche les liens StudiosPort dans le message
        links = self.studiosport_pattern.findall(message.content)
        
        if links:
            # Traite le premier lien trouvé
            original_link = links[0]
            affiliate_link = await self.add_utm_params(message.guild, original_link)
            custom_message = await self.config.guild(message.guild).message()
            
            # Envoie la réponse
            embed = discord.Embed(
                description=f"{custom_message}\n\n🔗 **Lien partenaire:**\n{affiliate_link}",
                color=discord.Color.blue()
            )
            embed.set_footer(text="Lien d'affiliation StudioSport")
            
            try:
                await message.reply(embed=embed, mention_author=False)
            except discord.HTTPException:
                # Fallback si les embeds ne fonctionnent pas
                await message.reply(f"{custom_message}\n{affiliate_link}", mention_author=False)
    
    async def add_utm_params(self, guild: discord.Guild, url: str) -> str:
        """
        Ajoute les paramètres UTM au lien
        """
        utm_source = await self.config.guild(guild).utm_source()
        utm_medium = await self.config.guild(guild).utm_medium()
        utm_campaign = await self.config.guild(guild).utm_campaign()
        
        # Vérifie si l'URL a déjà des paramètres
        separator = "&" if "?" in url else "?"
        
        utm_params = f"utm_source={utm_source}&utm_medium={utm_medium}&utm_campaign={utm_campaign}"
        
        return f"{url}{separator}{utm_params}"
    
    @commands.group(name="studiosport", aliases=["sp"])
    @commands.admin_or_permissions(manage_guild=True)
    async def studiosport_settings(self, ctx):
        """
        Configuration du COG StudioSport
        """
        pass
    
    @studiosport_settings.command(name="toggle")
    async def toggle_studiosport(self, ctx):
        """
        Active ou désactive le COG sur ce serveur
        """
        current = await self.config.guild(ctx.guild).enabled()
        await self.config.guild(ctx.guild).enabled.set(not current)
        
        status = "activé" if not current else "désactivé"
        await ctx.send(f"✅ Le COG StudioSport a été **{status}** sur ce serveur.")
    
    @studiosport_settings.command(name="message")
    async def set_message(self, ctx, *, message: str):
        """
        Définit le message personnalisé qui accompagne le lien
        
        Exemple: [p]studiosport message Profite de notre partenariat avec StudioSport !
        """
        await self.config.guild(ctx.guild).message.set(message)
        await ctx.send(f"✅ Message mis à jour : `{message}`")
    
    @studiosport_settings.command(name="utm")
    async def set_utm(self, ctx, source: str, medium: str, campaign: str):
        """
        Configure les paramètres UTM
        
        Exemple: [p]studiosport utm bandolovers affiliation affi-bandolovers
        """
        await self.config.guild(ctx.guild).utm_source.set(source)
        await self.config.guild(ctx.guild).utm_medium.set(medium)
        await self.config.guild(ctx.guild).utm_campaign.set(campaign)
        
        await ctx.send(f"✅ Paramètres UTM mis à jour :\n"
                      f"• Source: `{source}`\n"
                      f"• Medium: `{medium}`\n"
                      f"• Campaign: `{campaign}`")
    
    @studiosport_settings.command(name="test")
    async def test_link(self, ctx, url: str = None):
        """
        Teste la transformation d'un lien StudioSport
        
        Exemple: [p]studiosport test https://www.studiosport.fr/exemple
        """
        if not url:
            url = "https://www.studiosport.fr/exemple-produit.html"
        
        if not self.studiosport_pattern.match(url):
            await ctx.send("❌ Ce n'est pas un lien StudioSport valide.")
            return
        
        affiliate_link = await self.add_utm_params(ctx.guild, url)
        
        embed = discord.Embed(
            title="🔧 Test de transformation de lien",
            color=discord.Color.green()
        )
        embed.add_field(name="Lien original", value=f"```{url}```", inline=False)
        embed.add_field(name="Lien transformé", value=f"```{affiliate_link}```", inline=False)
        
        await ctx.send(embed=embed)
    
    @studiosport_settings.command(name="status")
    async def show_status(self, ctx):
        """
        Affiche la configuration actuelle
        """
        config = await self.config.guild(ctx.guild).all()
        
        status = "✅ Activé" if config["enabled"] else "❌ Désactivé"
        
        embed = discord.Embed(
            title="📊 Configuration StudioSport",
            color=discord.Color.blue()
        )
        embed.add_field(name="Statut", value=status, inline=True)
        embed.add_field(name="Message", value=f"`{config['message']}`", inline=False)
        embed.add_field(name="UTM Source", value=f"`{config['utm_source']}`", inline=True)
        embed.add_field(name="UTM Medium", value=f"`{config['utm_medium']}`", inline=True)
        embed.add_field(name="UTM Campaign", value=f"`{config['utm_campaign']}`", inline=True)
        
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(StudiosportAffiliate(bot))
