from .honeypot import Honeypot


def setup(bot):
    bot.add_cog(Honeypot(bot))