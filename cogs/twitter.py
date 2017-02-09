import asyncio
import datetime

import discord
from discord.ext import commands

import utils
import checks

from twitter import Api


def get_shitpost_channel(b: discord.ext.commands.Bot, server: discord.Server):
    return b.server_configs.get(server.id, {}).get('shitpost_channel', None)


class Twitter(utils.SessionCog):
    """"""

    def __init__(self, bot):
        super(Twitter, self).__init__(bot)
        self.bot = bot
        self.twitter = Api(**utils.tokens['twitter'])
        self.last = self.bot.status.get("last_tweet", None)
        self.bot.loop.create_task(self.twitter_repost())

    @commands.command(pass_context=True)
    @checks.is_server_owner()
    async def shitpost_channel(self, ctx):
        channel = ctx.message.channel
        if channel.server.id not in self.bot.server_configs:
            self.bot.server_configs[channel.server.id] = {}
        self.bot.server_configs[channel.server.id]['shitpost_channel'] = channel.id
        await self.bot.affirmative()
        self.bot.dump_server_configs()

    async def twitter_repost(self):
        """Early implementation of reposting twitter images to discord."""
        await self.bot.init.wait()
        while not self.bot.is_closed:
            try:
                tweet = self.twitter.GetUserTimeline('4462881555')[0]
            except:
                print("Connection to twitter failed. {}".format(datetime.datetime.now()))
            else:
                if tweet.text != self.last:
                    self.last = tweet.text
                    self.bot.status["last_tweet"] = tweet.text
                    self.bot.dump_status()
                    media_url = tweet.media[0].media_url
                    for server in self.bot.servers:
                        if get_shitpost_channel(self.bot, server) is not None:
                            channel = server.get_channel(get_shitpost_channel(self.bot, server))
                            try:
                                e = discord.Embed().set_image(url=media_url)
                                await self.bot.send_message(channel, embed=e)
                            except discord.errors.HTTPException:
                                print("could not post twitter image.")
            await asyncio.sleep(300)


def setup(bot):
    bot.add_cog(Twitter(bot))
