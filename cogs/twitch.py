import asyncio
import json
import websockets
import dateutil.parser
import random

import discord
from discord.ext import commands

import utils
import checks

import traceback

from Weeabot import Weeabot


def twitch_formatter(field):
    return {'name': 'Twitch', 'content': '<https://www.twitch.tv/{}>'.format(field['name'])}


class Twitch(utils.SessionCog):
    """Check Twitch stream status for users who have linked their accounts.
    
    If a channel exists with the name 'twitch-streams', automatic updates will be posted there when a user goes live."""

    formatters = {'twitch': twitch_formatter}

    def __init__(self, bot: Weeabot):
        super(Twitch, self).__init__(bot)
        self.loop = None
        self.ws = None
        self.updateloop()
        self.services = {
            "Twitch": f"""Create a channel named 'twitch-streams' to get notifications when server members go live.
            Members must use the {bot.command_prefix}addtwitch command to get notifications about their streams."""
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
    @checks.profiles()
    async def addtwitch(self, ctx, twitch_username: str):
        """Add your twitch name to your profile.

        Automatic updates when you go live will be posted in the twitch stream channel'.
        If the channel doesn't exist, this feature is disabled."""
        headers = {"accept": "application:vnd.twitchtv.v5+json", "Client-ID": utils.tokens['twitch_id']}
        url = 'https://api.twitch.tv/kraken/search/channels'
        params = {'query': twitch_username}
        async with self.session.get(url=url, headers=headers, params=params) as r:
            chan = (await r.json())['channels'][0]
            if await self.bot.confirm(f"Closest account found: <{chan['url']}>\nIs this correct?"):
                await self.bot.profiles.put_by_id(ctx.message.author.id, 'twitch', {
                    'name': twitch_username.lower(),
                    'id': chan['_id']
                })
                await self.bot.affirmative()

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
        await self.bot.affirmative()
        self.bot.dump_server_configs()

    def t_users(self):
        return {
            p['twitch']['name'].lower(): {'did': u, 'tid': p['twitch']['id']}
            for u, p in self.bot.profiles.all().items()
            if 'twitch' in p
        }

    async def twitch_listen(self):
        # subscribe to channels
        await self.ws.send(json.dumps({
            'type': 'LISTEN',
            'nonce': f'Weeabot{random.randrange(200,300)}',
            'data': {
                'topics': [f'video-playback.{tname.lower()}' for tname in self.t_users().keys()]
            }
        }))

        # wait for response and handle errors
        r = json.loads(await self.ws.recv())
        return r['error']

    async def getstreams(self):
        headers = {"accept": "application:vnd.twitchtv.v5+json", "Client-ID": utils.tokens['twitch_id']}

        self.ws = await websockets.connect('wss://pubsub-edge.twitch.tv')

        if await self.twitch_listen():
            print('Failed to subscribe.')
            return

        while not self.bot.is_closed:
            # initiate heartbeat
            await self.ws.send(json.dumps({"type": "PING"}))

            # check heartbeat
            try:
                await asyncio.wait_for(self.ws.recv(), 10)
            except asyncio.TimeoutError:
                print("twitch heartbeat failed. Reconnecting.")
                self.ws = await websockets.connect('wss://pubsub-edge.twitch.tv')

            # wait for event
            try:
                r = json.loads(await asyncio.wait_for(self.ws.recv(), 270))
            except asyncio.TimeoutError:
                pass
            else:
                try:
                    print(f'Twitch event received: {r}')
                    name = r['data']['topic'].split('.')[1]
                    message = json.loads(r['data']['message'])

                    # check message type
                    if message['type'] == 'stream-up':

                        # get user ids
                        us = self.t_users()
                        did = us[name]['did']
                        tid = us[name]['tid']

                        # get stream data. retry a few times if the api is delayed
                        url = f'https://api.twitch.tv/kraken/streams/{tid}'
                        async with self.session.get(url=url, headers=headers) as r:
                            for i in range(5):
                                stream = (await r.json())['stream']
                                if stream:
                                    break
                                else:
                                    await asyncio.sleep(2)

                        # get box art
                        api = 'https://api.twitch.tv/kraken/search/games'
                        params = {'query': stream["game"]}
                        async with self.session.get(api, params=params, headers=headers) as r:
                            box = (await r.json())['games'][0]['box']['large']

                        # send messages to each twitch stream if the user is in that server
                        for c in self.channels:
                            mem = c.server.get_member(did)
                            if mem is not None:
                                e = discord.Embed(
                                    title=stream['channel']['status'],
                                    url=stream['channel']['url'],
                                    description=f'**Game** | {stream["game"]}',
                                    timestamp=discord.utils.parse_time(
                                        dateutil.parser.parse(stream['created_at']).isoformat())
                                ).set_image(
                                    url=stream['preview']['medium'] + f'?rand={stream["_id"]}'
                                ).set_thumbnail(
                                    url=box
                                ).set_author(
                                    name=f"{mem.display_name} started streaming",
                                    icon_url=stream['channel']['logo'] or mem.avatar_url or mem.default_avatar_url
                                )
                                try:
                                    await self.bot.send_message(c, embed=e)
                                except discord.HTTPException as ex:
                                    print(ex.response)
                except:
                    traceback.print_exc()

        self.ws.close()

    async def getstreamsold(self):
        headers = {"accept": "application:vnd.twitchtv.v5+json", "Client-ID": utils.tokens['twitch_id']}

        def getstream(name: str, streamlist):
            for s in streamlist:
                if name.lower() == s['channel']['name'].lower():
                    return s
            return None

        while not self.bot.is_closed:
            users = {u: self.bot.profiles.get_field_by_id(u, 'twitch')
                     for u, p in self.bot.profiles.all().items()
                     if 'twitch' in p}
            api = "https://api.twitch.tv/kraken/streams"
            params = {'channel': ','.join([t['name'] for t in users.values()])}
            async with self.session.get(api, headers=headers, params=params) as r:
                response = await r.json()
            try:
                streams = response['streams']
            except KeyError:
                print('Twitch connection error.')
            else:
                if response['_total'] > 0:
                    for c in self.channels:
                        serv: discord.Server = c.server
                        users_here = {u: users[u] for u in users if u in [x.id for x in serv.members]}
                        for uid, t in users_here.items():
                            try:
                                stream = getstream(t['name'], streams)
                                if stream is not None:
                                    if stream['created_at'] != t['lastOnline']:
                                        t['lastOnline'] = stream['created_at']
                                        u = serv.get_member(uid)
                                        api = 'https://api.twitch.tv/kraken/search/games'
                                        params = {'query': stream["game"]}
                                        async with self.session.get(api, params=params, headers=headers) as r:
                                            print(await r.json())
                                            box = (await r.json())['games'][0]['box']['large']
                                        e = discord.Embed(
                                            title=stream['channel']['status'],
                                            url=stream['channel']['url'],
                                            description=f'**Game** | {stream["game"]}',
                                            timestamp=discord.utils.parse_time(dateutil.parser.parse(stream['created_at']).isoformat())
                                        ).set_image(
                                            url=stream['preview']['medium'] + f'?rand={stream["_id"]}'
                                        ).set_thumbnail(
                                            url=box
                                        ).set_author(
                                            name=f"{u.display_name} started streaming",
                                            icon_url=stream['channel']['logo'] or u.avatar_url or u.default_avatar_url
                                        ).set_footer(
                                            text=f'{stream["video_height"]}p {stream["average_fps"]}fps'
                                        )
                                        try:
                                            await self.bot.send_message(c, embed=e)
                                        except discord.HTTPException as ex:
                                            print(ex.response)
                            except (KeyError, TypeError, AttributeError):
                                print('error processing ' + t['name'])
                                traceback.print_exc()
                await self.bot.profiles.save()
            await asyncio.sleep(120)


def setup(bot):
    bot.add_cog(Twitch(bot))
