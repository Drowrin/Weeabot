import asyncio
import traceback
# noinspection PyUnresolvedReferences
from discord.ext import commands
from utils import *


# noinspection PyUnusedLocal
def twitch_formatter(ctx, field, fields):
    fields.append('Twitch: <https://www.twitch.tv/{}>'.format(field['name']))


class Twitch(SessionCog):
    """Check Twitch stream status for users who have linked their accounts.
    
    If a channel exists with the name 'twitch-streams', automatic updates will be posted there when a user goes live."""

    formatters = {'twitch': twitch_formatter}

    def __init__(self, bot):
        super(Twitch, self).__init__(bot)
        self.loop = None
        self.channels = []
        self.updateloop()
        self.services = {
            "Twitch": """Create a channel named 'twitch-streams' to get notifications when server members go live.
            Members must use the ~addtwitch command to get notifications about their streams."""
        }
    
    def __unload(self):
        self.stoploop()
    
    def startloop(self):
        if self.loop is None:
            self.loop = self.bot.loop.create_task(self.getstreams())
    
    def stoploop(self):
        if self.loop is not None:
            self.loop.cancel()
        self.loop = None
    
    def updateloop(self):
        self.channels = list(filter(lambda e: e.name == 'twitch-streams', self.bot.get_all_channels()))
        if len(self.channels):
            self.startloop()
        else:
            self.stoploop()

    # noinspection PyUnusedLocal
    async def on_channel_delete(self, channel):
        self.updateloop()

    # noinspection PyUnusedLocal
    async def on_channel_create(self, channel):
        self.updateloop()

    # noinspection PyUnusedLocal
    async def on_channel_update(self, before, after):
        self.updateloop()
    
    @commands.command(pass_context=True)
    @profiles()
    async def addtwitch(self, ctx, twitch: str):
        """Add your twitch name to your profile.
        
        Automatic updates when you go live will be posted in a channel called 'twitch-streams'.
        If the channel doesn't exist, this feature is disabled."""
        try:
            usr = ctx.message.author
            await self.bot.profiles.put_by_id(usr.id, 'twitch', {'name': twitch, 'lastOnline': '0000-00-00T00:00:00Z'})
        except commands.BadArgument as e:
            await self.bot.say(e)
            return
        await self.bot.say("Added {} as {}.".format(usr.display_name, twitch))

    async def getstreams(self):
        up = self.bot.profiles.all()
        headers = {"accept": "application:vnd.twitchtv.v3+json", "Client-ID": tokens['twitch_id']}
        while not self.bot.is_closed:
            for dest in self.channels:
                serv = dest.server
                twitchmembers = [mem for mem in serv.members if 'twitch' in up.get(mem.id, {})]
                for mem in twitchmembers:
                    try:
                        i = up[mem.id]['twitch']
                        api = "https://api.twitch.tv/kraken/streams/{}".format(i['name'])
                        async with self.session.get(api, headers=headers) as r:
                            chan = await r.json()
                        if chan['stream']['created_at'] != i['lastOnline']:
                            i['lastOnline'] = chan['stream']['created_at']
                            await self.bot.send_message(dest, "{} is now streaming {} at {}".format(
                                mem.display_name, chan['stream']['game'],
                                'https://www.twitch.tv/{}'.format(i['name'])))
                            await self.bot.profiles.put_by_id(mem.id, 'twitch', i)
                    except (KeyError, TypeError):
                        pass
                        # print(traceback.format_exc())
            await asyncio.sleep(300)


def setup(bot):
    bot.add_cog(Twitch(bot))
