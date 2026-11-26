from .bandoburger import BandoBurger

__red_end_user_data_statement__ = (
    "Ce cog enregistre l'identifiant Discord des membres qui prennent un ingrédient, "
    "par serveur. Ces données sont supprimées sur demande."
)


async def setup(bot):
    await bot.add_cog(BandoBurger(bot))
