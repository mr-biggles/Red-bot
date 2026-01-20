import aiohttp
import asyncio

from redbot.core import commands, Config
from redbot.core.bot import Red
from discord import TextChannel, AllowedMentions

TWITCH_API = "https://api.twitch.tv/helix"
TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"


class TwitchAlert(commands.Cog):
    """Annonce automatiquement quand un live Twitch démarre"""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=9988776655)

        self.config.register_global(
            twitch_channel=None,
            discord_channel=None,
            message="🔴 **{streamer} est en live !**\n👉 {url}",
            refresh=120,
            is_live=False,
            ping="off",
            twitch_client_id=None,
            twitch_client_secret=None,
            access_token=None,
        )

        self.task = self.bot.loop.create_task(self.live_loop())

    def cog_unload(self):
        self.task.cancel()

    # ───────────────────────────────
    # GROUPE DE COMMANDES
    # ───────────────────────────────
    @commands.group()
    @commands.is_owner()
    async def alertetwitch(self, ctx):
        """Configuration des alertes Twitch"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    # ───────────────────────────────
    # CONFIGURATION TWITCH
    # ───────────────────────────────
    @alertetwitch.command()
    async def twitchid(self, ctx, client_id: str):
        await self.config.twitch_client_id.set(client_id)
        await self.config.access_token.clear()
        await ctx.send("✅ **Client ID Twitch** enregistré")

    @alertetwitch.command()
    async def twitchsecret(self, ctx, secret: str):
        await self.config.twitch_client_secret.set(secret)
        await self.config.access_token.clear()
        await ctx.send("✅ **Client Secret Twitch** enregistré")

    @alertetwitch.command()
    async def channel(self, ctx, streamer: str):
        await self.config.twitch_channel.set(streamer.lower())
        await self.config.is_live.set(False)
        await ctx.send(f"✅ Chaîne Twitch configurée : **{streamer}**")

    # ───────────────────────────────
    # CONFIGURATION DISCORD
    # ───────────────────────────────
    @alertetwitch.command()
    async def salon(self, ctx, channel: TextChannel):
        await self.config.discord_channel.set(channel.id)
        await ctx.send(f"✅ Salon d'annonce défini : {channel.mention}")

    @alertetwitch.command()
    async def message(self, ctx, *, message: str):
        await self.config.message.set(message)
        await ctx.send("✅ Message personnalisé enregistré")

    @alertetwitch.command()
    async def refresh(self, ctx, seconds: int):
        seconds = max(seconds, 30)
        await self.config.refresh.set(seconds)
        await ctx.send(f"✅ Vérification toutes les **{seconds} secondes**")

    @alertetwitch.command()
    async def ping(self, ctx, mode: str):
        if mode not in ("off", "everyone", "here"):
            return await ctx.send("⛔ Valeurs autorisées : off / everyone / here")
        await self.config.ping.set(mode)
        await ctx.send(f"✅ Ping configuré : **{mode}**")

    # ───────────────────────────────
    # TWITCH API
    # ───────────────────────────────
    async def get_access_token(self):
        client_id = await self.config.twitch_client_id()
        secret = await self.config.twitch_client_secret()

        if not client_id or not secret:
            return None

        async with aiohttp.ClientSession() as session:
            async with session.post(
                TWITCH_TOKEN_URL,
                params={
                    "client_id": client_id,
                    "client_secret": secret,
                    "grant_type": "client_credentials",
                },
            ) as resp:
                data = await resp.json()
                token = data.get("access_token")

                if token:
                    await self.config.access_token.set(token)
                    return token
        return None

    async def api_headers(self):
        token = await self.config.access_token()
        if not token:
            token = await self.get_access_token()
        if not token:
            return None

        return {
            "Client-ID": await self.config.twitch_client_id(),
            "Authorization": f"Bearer {token}",
        }

    async def is_stream_live(self, streamer: str):
        headers = await self.api_headers()
        if not headers:
            return False

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(
                f"{TWITCH_API}/streams",
                params={"user_login": streamer},
            ) as resp:
                data = await resp.json()
                return bool(data.get("data"))

    # ───────────────────────────────
    # BOUCLE LIVE
    # ───────────────────────────────
    async def live_loop(self):
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            streamer = await self.config.twitch_channel()
            channel_id = await self.config.discord_channel()

            if streamer and channel_id:
                is_live = await self.is_stream_live(streamer)
                was_live = await self.config.is_live()

                if is_live and not was_live:
                    await self.send_alert(streamer)
                    await self.config.is_live.set(True)

                if not is_live:
                    await self.config.is_live.set(False)

            await asyncio.sleep(await self.config.refresh())

    async def send_alert(self, streamer: str):
        channel_id = await self.config.discord_channel()
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        message = await self.config.message()
        url = f"https://twitch.tv/{streamer}"

        ping = await self.config.ping()
        prefix = ""
        if ping == "everyone":
            prefix = "@everyone "
        elif ping == "here":
            prefix = "@here "

        content = prefix + message.format(
            streamer=streamer,
            url=url,
        )

        await channel.send(
            content,
            allowed_mentions=AllowedMentions(
                everyone=ping != "off",
                roles=False,
                users=False,
            ),
        )


def setup(bot: Red):
    bot.add_cog(TwitchAlert(bot))
