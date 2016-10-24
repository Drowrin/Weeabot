import asyncio
import datetime
# noinspection PyUnresolvedReferences
import discord
# noinspection PyUnresolvedReferences
from discord.ext import commands
from utils import *

from twitter import Api


def get_shitpost_channel(b: discord.ext.commands.Bot, server: discord.Server):
    return b.server_configs.get(server.id, {}).get('shitpost_channel', None)


class Twitter(SessionCog):
    """"""

    def __init__(self, bot):
        super(Twitter, self).__init__(bot)
        self.bot = bot
        self.twitter = Api(**tokens['twitter'])
        self.last = self.bot.status.get("last_tweet", None)
        self.bot.loop.create_task(self.twitter_repost())

    @commands.command(pass_context=True)
    @is_server_owner()
    async def shitpost_channel(self, ctx):
        channel = ctx.message.channel
        if channel.server.id not in self.bot.server_configs:
            self.bot.server_configs[channel.server.id] = {}
        self.bot.server_configs[channel.server.id]['shitpost_channel'] = channel.id
        await self.bot.say('\N{OK HAND SIGN}')
        self.bot.dump_server_configs()

    async def twitter_repost(self):
        """Early implementation of reposting twitter images to discord."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed:
            try:
                tweet = self.twitter.GetUserTimeline('4462881555')[0]
            except:
                print("Connection to twitter failed. {}".format(datetime.datetime.now()))
            if tweet.text != self.last:
                self.last = tweet.text
                self.bot.status["last_tweet"] = tweet.text
                self.bot.dump_status()
                print("Latest shitpost: ", tweet.text)
                media_url = tweet.media[0].media_url
                with await download_fp(self.session, media_url) as fp:
                    for server in self.bot.servers:
                        if get_shitpost_channel(self.bot, server) is not None:
                            channel = server.get_channel(get_shitpost_channel(self.bot, server))
                            await self.bot.send_file(channel, fp, filename="shitpost.jpeg")
                            fp.seek(0)
            await asyncio.sleep(300)


def setup(bot):
    bot.add_cog(Twitter(bot))
