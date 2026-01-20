import aiohttp
import asyncio
from redbot.core import commands, Config
from redbot.core.bot import Red

TWITCH_API = "https://api.twitch.tv/helix"

class TwitchAlert(commands.Cog):
    """Annonce quand un live Twitch démarre"""

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
            access_token=None
        )

        self.bot.loop.create_task(self.live_loop())

    # =========================
    # 🔑 Twitch Token
    # =========================
    async def get_token(self):
        token = await self.config.access_token()
        if token:
            return token

        client_id = await self.config.twitch_client_id()
        client_secret = await self.config.twitch_client_secret()

        if not client_id or not client_secret:
            return None

        url = "https://id.twitch.tv/oauth2/token"
        params = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, params=params) as resp:
                data = await resp.json()
                token = data.get("access_token")
                await self.config.access_token.set(token)
                return token

    # =========================
    # 🔁 Loop live
    # =========================
    async def live_loop(self):
        await self.bot.wait_until_ready()

        while True:
            await self.check_live()
            await asyncio.sleep(await self.config.refresh())

    async def check_live(self):
        streamer = await self.config.twitch_channel()
        if not streamer:
            return

        token = await self.get_token()
        if not token:
            return

        headers = {
            "Client-ID": await self.config.twitch_client_id(),
            "Authorization": f"Bearer {token}"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{TWITCH_API}/streams?user_login={streamer}",
                headers=headers
            ) as resp:
                data = await resp.json()

        is_live = bool(data.get("data"))
        was_live = await self.config.is_live()

        if is_live and not was_live:
            await self.send_announcement()

        await self.config.is_live.set(is_live)

    # =========================
    # 📢 Annonce
    # =========================
    async def send_announcement(self):
        channel_id = await self.config.discord_channel()
        streamer = await self.config.twitch_channel()
        message = await self.config.message()
        ping = await self.config.ping()

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        content = message.format(
            streamer=streamer,
            url=f"https://twitch.tv/{streamer}"
        )

        if ping == "everyone":
            content = "@everyone\n" + content
        elif ping == "here":
            content = "@here\n" + content

        await channel.send(
            content,
            allowed_mentions={
                "everyone": ping in ["everyone", "here"],
                "roles": False,
                "users": False
            }
        )

    # =========================
    # 📘 Commandes
    # =========================
    @commands.group()
    async def alertetwitch(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @alertetwitch.command()
    @commands.is_owner()
    async def twitchid(self, ctx, client_id: str):
        await self.config.twitch_client_id.set(client_id)
        await self.config.access_token.clear()
        await ctx.send("✅ Twitch **Client ID** enregistré")

    @alertetwitch.command()
    @commands.is_owner()
    async def twitchsecret(self, ctx, secret: str):
        await self.config.twitch_client_secret.set(secret)
        await self.config.access_token.clear()
        await ctx.send("✅ Twitch **Client Secret** enregistré")

    @alertetwitch.command()
    async def channel(self, ctx, streamer: str):
        await self.config.twitch_channel.set(streamer.lower())
        await ctx.send(f"✅ Chaîne Twitch : **{streamer}**")

    @alertetwitch.command()
async def salon(self, ctx, channel: commands.TextChannel):
    """Définit le salon d'annonce"""
    await self.config.discord_channel.set(channel.id)
    await ctx.send(f"✅ Salon défini : {channel.mention}")

    @alertetwitch.command()
    async def message(self, ctx, *, message: str):
        await self.config.message.set(message)
        await ctx.send("✅ Message mis à jour")

    @alertetwitch.command()
    async def refresh(self, ctx, seconds: int):
        await self.config.refresh.set(max(seconds, 30))
        await ctx.send(f"✅ Refresh : {seconds}s")

    @alertetwitch.command()
    async def ping(self, ctx, mode: str):
        if mode not in ["off", "everyone", "here"]:
            return await ctx.send("⛔ off / everyone / here")
        await self.config.ping.set(mode)
        await ctx.send(f"✅ Ping : {mode}")
