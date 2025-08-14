from .socialthreadopener import SocialThreadOpener

async def setup(bot):
    await bot.add_cog(SocialThreadOpener(bot))