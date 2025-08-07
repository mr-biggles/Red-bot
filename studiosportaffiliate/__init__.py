from .studiosportaffiliate import StudiosportAffiliate


async def setup(bot):
    await bot.add_cog(StudiosportAffiliate(bot))
