from .socialthreadopener import SocialThreadOpener

__red_end_user_data_statement__ = "This cog does not persistently store data about users."

async def setup(bot):
    cog = SocialThreadOpener(bot)
    await bot.add_cog(cog)
