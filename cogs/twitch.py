import asyncio
import traceback
# noinspection PyUnresolvedReferences
import discord
# noinspection PyUnresolvedReferences
from discord.ext import commands
from utils import *
import checks


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
        self.updateloop()
        self.services = {
            "Twitch": """Create a channel named 'twitch-streams' to get notifications when server members go live.
            Members must use the ~addtwitch command to get notifications about their streams."""
        }

    @property
    def channels(self):
        return [c for c in [self.get_channel(s) for s in self.bot.servers] if c is not None]

    def get_channel(self, server: discord.Server):
        try:
            return server.get_channel(self.bot.server_configs[server.id]['twitch_channel'])
        except KeyError:
            return None

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
            await self.bot.profiles.put_by_id(usr.id, 'twitch', {'name': twitch.lower(), 'lastOnline': '0000-00-00T00:00:00Z'})
        except commands.BadArgument as e:
            await self.bot.say(e)
            return
        await self.bot.say("Added {} as {}.".format(usr.display_name, twitch))

    @commands.command(pass_context=True)
    @checks.is_server_owner()
    async def twitch_channel(self, ctx):
        """Set the channel twitch streams will be posted to.

        All users in this server who have set their twitch account with the bot
        will have links posted here when they go live."""
        channel = ctx.message.channel
        if channel.server.id not in self.bot.server_configs:
            self.bot.server_configs[channel.server.id] = {}
        self.bot.server_configs[channel.server.id]['twitch_channel'] = channel.id
        await self.bot.say('\N{OK HAND SIGN}')
        self.bot.dump_server_configs()

    async def getstreams(self):
        headers = {"accept": "application:vnd.twitchtv.v3+json", "Client-ID": tokens['twitch_id']}

        def getstream(name: str, streamlist):
            for s in streamlist:
                if name.lower() == s['channel']['name'].lower():
                    return s
            return None

        while not self.bot.is_closed:
            users = {u: self.bot.profiles.get_field_by_id(u, 'twitch')
                     for u, p in self.bot.profiles.all().items()
                     if 'twitch' in p}
            api = "https://api.twitch.tv/kraken/streams?channel={}".format(','.join([t['name'] for t in users.values()]))
            async with self.session.get(api, headers=headers) as r:
                response = await r.json()
            try:
                streams = response['streams']
            except KeyError:
                print('Twitch connection error.')
            else:
                if response['_total'] > 0:
                    for c in self.channels:
                        serv = c.server
                        users_here = {u: users[u] for u in users if u in [x.id for x in serv.members]}
                        for uid, t in users_here.items():
                            try:
                                stream = getstream(t['name'], streams)
                                if stream is not None:
                                    if stream['created_at'] != t['lastOnline']:
                                        t['lastOnline'] = stream['created_at']
                                        await self.bot.send_message(c, "{} is now streaming {} at {}".format(
                                            serv.get_member(uid).display_name,
                                            stream['game'],
                                            'https://www.twitch.tv/{}'.format(t['name'])
                                        ))
                            except (KeyError, TypeError, AttributeError):
                                print('error processing ' + t['name'])
                                traceback.print_exc()
                await self.bot.profiles.save()
            await asyncio.sleep(120)


def setup(bot):
    bot.add_cog(Twitch(bot))
