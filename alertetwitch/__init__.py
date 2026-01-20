from .twitchalert import TwitchAlert

async def setup(bot):
    await bot.add_cog(TwitchAlert(bot))
