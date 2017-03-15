import asyncio
import json
import websockets
import dateutil.parser
from datetime import datetime
from datetime import timedelta
import random

import discord
from discord.ext import commands

import utils
import checks

import traceback

from Weeabot import Weeabot


def twitch_formatter(field):
    return {
        'name': 'Twitch',
        'content': f'[{field["name"]}](https://www.twitch.tv/{field["name"]})'
    }


class Twitch(utils.SessionCog):
    """Check Twitch stream status for users who have linked their accounts.
    
    If a channel exists with the name 'twitch-streams', automatic updates will be posted there when a user goes live."""

    formatters = {'twitch_inline': twitch_formatter}

    def __init__(self, bot: Weeabot):
        super(Twitch, self).__init__(bot)
        self._ws = None
        self.reconnect = False
        self.next_connect = datetime.now()
        self.connecting = asyncio.Lock()
        self.listeners = []
        self.tasks = []
        self.updateloop()
        self.services = {
            "Twitch": f"""Create a channel named 'twitch-streams' to get notifications when server members go live.
            Members must use the {bot.command_prefix}addtwitch command to get notifications about their streams."""
        }

    @property
    def channels(self):
        return [
            c for c in
            [
                s.get_channel(
                    self.bot.server_configs[s.id].get('twitch_channel')
                )
                for s in self.bot.servers
            ]
            if c is not None
        ]

    def __unload(self):
        self.stoploop()
    
    def startloop(self):
        if len(self.tasks) == 0:
            self.tasks.append(self.bot.loop.create_task(self.dispatcher()))
            self.tasks.append(self.bot.loop.create_task(self.heartbeat()))
            self.tasks.append(self.bot.loop.create_task(self.getstreams()))
    
    def stoploop(self):
        for t in self.tasks:
            t.cancel()
        self.tasks = []
        self.reconnect = True
    
    def updateloop(self):
        if len(self.channels):
            self.startloop()
        else:
            self.stoploop()

    async def on_channel_delete(self, channel):
        self.updateloop()

    async def on_channel_create(self, channel):
        self.updateloop()

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
                await self.twitch_listen()
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

    async def update_stream(self, messages, did, tid):
        headers = {"accept": "application:vnd.twitchtv.v5+json", "Client-ID": utils.tokens['twitch_id']}

        try:
            # get stream data. retry a few times if the api is delayed
            url = f'https://api.twitch.tv/kraken/streams/{tid}'
            stream = None
            for i in range(15):
                async with self.session.get(url=url, headers=headers) as r:
                    stream = (await r.json())['stream']
                if stream:
                    break
                else:
                    print('couldnt get stream, retying soon...')
                    await asyncio.sleep(20)
            if stream is None:
                for m in messages:
                    mem = m.server.get_member(did)
                    await self.bot.edit_message(m, embed=discord.Embed(
                                description='Waiting for Twitch API...'
                            ).set_author(
                                name=f"{mem.display_name} started streaming",
                                icon_url=mem.avatar_url or mem.default_avatar_url,
                                url=f'https://www.twitch.tv/{self.bot.profiles.get_by_id(did)["twitch"]["name"]}'
                            ))

            # get box art
            api = 'https://api.twitch.tv/kraken/search/games'
            params = {'query': stream["game"]}
            async with self.session.get(api, params=params, headers=headers) as r:
                box = (await r.json())['games'][0]['box']['large']

            # send messages to each twitch stream if the user is in that server
            for m in messages:
                mem = m.server.get_member(did)
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
                        await self.bot.edit_message(m, embed=e)
                    except discord.HTTPException as ex:
                        print(ex.response)
        except:
            traceback.print_exc()

    async def connect(self):
        if datetime.now() < self.next_connect:
            sleep = (self.next_connect - datetime.now()).seconds
            print(sleep)
            await asyncio.sleep(sleep)
        self.next_connect = datetime.now() + timedelta(seconds=120)
        print('connecting to twitch...')
        ws = await websockets.connect('wss://pubsub-edge.twitch.tv')

        await ws.send(json.dumps({
            'type': 'LISTEN',
            'nonce': f'Weeabot{random.randrange(200,300)}',
            'data': {
                'topics': [f'video-playback.{tname.lower()}' for tname in self.t_users().keys()]
            }
        }))

        # wait for response and handle errors
        r = json.loads(await ws.recv())
        print(r)
        if r['error']:
            print(f'error subscribing: {r["error"]}')
            self.stoploop()
        return ws

    async def get_ws(self):
        if self.reconnect:
            print('attempting reconnect')
            await self._ws.close()
            self._ws = None
            self.reconnect = False
        await self.connecting.acquire()
        if self._ws is None:
            self._ws = await self.connect()
        self.connecting.release()
        return self._ws

    async def recv(self, *args, **kwargs):
        ws = await self.get_ws()
        return await ws.recv(*args, **kwargs)

    async def send(self, *args, **kwargs):
        ws = await self.get_ws()
        return await ws.send(*args, **kwargs)

    async def dispatcher(self):
        while not self.bot.is_closed:
            r = json.loads(await self.recv())
            self.dispatch(r)

    def dispatch(self, r):
        t = r['type']
        print(f'Twitch event received: {r}')

        # special reconnect case
        if t == 'RECONNECT':
            self.reconnect = True
            return

        removed = []
        li = [l for l in self.listeners if t in l[1]]
        for l in li:
            removed.append(l)
            l[0].set_result(r)

        self.listeners = [l for l in self.listeners if l not in removed]

    async def heartbeat(self):
        while not self.bot.is_closed:
            # initiate heartbeat
            await self.send(json.dumps({"type": "PING"}))

            # wait for response or time out
            try:
                await self.wait_for_event("PONG", timeout=10)
            except asyncio.TimeoutError:
                print('PONG timeout')
                self.reconnect = True
            else:
                await asyncio.sleep(240)

    def wait_for_event(self, *events, timeout=None):
        f = self.bot.loop.create_future()
        self.listeners.append((f, events))

        return asyncio.wait_for(f, timeout, loop=self.bot.loop)

    async def getstreams(self):
        while not self.bot.is_closed:
            try:
                r = await self.wait_for_event("MESSAGE")
                name = r['data']['topic'].split('.')[1]
                message = json.loads(r['data']['message'])

                # check message type
                if message['type'] == 'stream-up':

                    # get user ids
                    us = self.t_users()
                    did = us[name]['did']
                    tid = us[name]['tid']

                    # send initial messages
                    messages = []
                    for c in self.channels:
                        mem = c.server.get_member(did)
                        messages.append(await self.bot.send_message(c, embed=discord.Embed(
                            description='Waiting for Twitch API...'
                        ).set_author(
                            name=f"{mem.display_name} started streaming",
                            icon_url=mem.avatar_url or mem.default_avatar_url,
                            url=f'https://www.twitch.tv/{name}'
                        )))

                    self.bot.loop.create_task(self.update_stream(messages, did, tid))
            except:
                traceback.print_exc()


def setup(bot):
    bot.add_cog(Twitch(bot))
