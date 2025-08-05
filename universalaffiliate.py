from redbot.core import commands, Config, checks
from redbot.core.bot import Red
import re
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

URL_REGEX = re.compile(r'(?P<url>https?://[^\s<>()]+)', re.IGNORECASE)

DEFAULT_IGNORED_DOMAINS = {
    "discord.com", "discord.gg", "ptb.discord.com", "canary.discord.com",
    "cdn.discordapp.com", "media.discordapp.net", "tenor.com", "giphy.com"
}

class UniversalAffiliate(commands.Cog):
    __author__ = "you"
    __version__ = "1.0.0"

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=0xAFF1C0DE, force_registration=True)
        self.config.register_guild(
            enabled=True, param_name="aff", param_value="moncode",
            mode="blocklist", allowlist=set(), blocklist=set(DEFAULT_IGNORED_DOMAINS),
            repost=False
        )

    @staticmethod
    def _normalize_domain(netloc: str) -> str:
        return netloc.lower().removeprefix("www.")

    def _should_process_domain(self, domain, mode, allow, block):
        d = self._normalize_domain(domain)
        if mode == "all":
            return d not in block
        if mode == "allowlist":
            return d in allow
        return d not in block

    def _inject_param(self, url, param, value):
        trailing = ""
        while url and url[-1] in ").,!?;:":
            trailing = url[-1] + trailing
            url = url[:-1]
        parsed = urlparse(url)
        q = dict(parse_qsl(parsed.query, keep_blank_values=True))
        if param in q:
            return url + trailing
        q[param] = value
        new_parsed = parsed._replace(query=urlencode(q, doseq=True))
        return urlunparse(new_parsed) + trailing

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.bot:
            return
        conf = await self.config.guild(message.guild).all()
        if not conf["enabled"]:
            return
        urls = [m.group("url") for m in URL_REGEX.finditer(message.content)]
        if not urls:
            return
        new_content = message.content
        modified = False
        for url in urls:
            try:
                parsed = urlparse(url.rstrip(").,!?;:"))
            except:
                continue
            domain = parsed.netloc
            if not domain or not self._should_process_domain(domain, conf["mode"], set(conf["allowlist"]), set(conf["blocklist"])):
                continue
            new_url = self._inject_param(url, conf["param_name"], conf["param_value"])
            if new_url != url:
                new_content = new_content.replace(url, new_url)
                modified = True
        if not modified:
            return
        if conf["repost"] and message.channel.permissions_for(message.guild.me).manage_messages:
            try:
                await message.delete()
            except:
                pass
            await message.channel.send(f"{message.author.mention} → lien aff ajouté :\n{new_content}")
        else:
            await message.reply(f"Aff ajouté :\n{new_content}", mention_author=False)

    @commands.group(name="aff", invoke_without_command=True)
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def aff_group(self, ctx):
        await ctx.send_help()

    @aff_group.command(name="status")
    async def status(self, ctx):
        conf = await self.config.guild(ctx.guild).all()
        await ctx.send(
            f"Enabled: `{conf['enabled']}`\n"
            f"Param: `{conf['param_name']}={conf['param_value']}`\n"
            f"Mode: `{conf['mode']}`\n"
            f"Repost: `{conf['repost']}`\n"
            f"Allowlist: {', '.join(sorted(conf['allowlist'])) or '—'}\n"
            f"Blocklist: {', '.join(sorted(conf['blocklist'])) or '—'}"
        )

    # autres commandes set, allow, block, repost (logique identique à l’exemple précédent)
    # ...
