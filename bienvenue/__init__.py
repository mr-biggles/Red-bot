from .bienvenue import Bienvenue


async def setup(bot):
    await bot.add_cog(Bienvenue(bot))
