from .universalaffiliate import UniversalAffiliate

async def setup(bot):
    await bot.add_cog(UniversalAffiliate(bot))
