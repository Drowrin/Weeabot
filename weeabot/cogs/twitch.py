import asyncio
import json
import traceback
import websockets
import random
from dateutil.parser import parse
from datetime import datetime, timedelta

import discord
from discord.ext import commands

from asyncio_extras import threadpool

from . import base_cog
from ..storage.tables import ProfileField


class Twitch(base_cog(session=True)):
    """
    Twitch commands.
    """

    def __init__(self, bot):
        super(Twitch, self).__init__(bot)
        self._ws = None
        self.reconnect = False
        self.next_connect = datetime.now()
        self.connecting = asyncio.Lock()
        self.listeners = []
        self.tasks = []
        self.startloop()

    def __unload(self):
        super(Twitch, self).__unload()
        self.stoploop()

    def stoploop(self):
        for t in self.tasks:
            t.cancel()
        self.tasks = []
        self.reconnect = True

    def startloop(self):
        if len(self.tasks) == 0:
            self.tasks.append(self.bot.loop.create_task(self.dispatcher()))
            self.tasks.append(self.bot.loop.create_task(self.heartbeat()))
            self.tasks.append(self.bot.loop.create_task(self.getstreams()))

    async def all_twitch_users(self):
        """
        Get all the users with twitch profiles.
        """
        async with threadpool(), self.bot.db.session() as s:
            return {
                u.value['name']: {'tid': u.value['id'], 'did': u.user_id}
                for u in
                s.query(ProfileField).filter(ProfileField.key == 'twitch').all()
            }

    async def update_stream(self, messages, did, tid):
        headers = {"accept": "application:vnd.twitchtv.v5+json", "Client-ID": self.bot.config['twitch_id']}

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
                    print('couldnt get stream, retrying soon...')
                    await asyncio.sleep(20)
            if stream is None:
                for m in messages:
                    mem = m.guild.get_member(did)
                    async with threadpool(), self.bot.db.get_profile_field(m, 'twitch') as pf:
                        t_name = pf.value['name']
                    await m.edit(embed=discord.Embed(
                        description='Waiting for Twitch API...'
                    ).set_author(
                        name=f"{mem.display_name} started streaming",
                        icon_url=mem.avatar_url or mem.default_avatar_url,
                        url=f'https://www.twitch.tv/{t_name}'
                    ))

            # get box art
            api = 'https://api.twitch.tv/kraken/search/games'
            params = {'query': stream["game"]}
            async with self.session.get(api, params=params, headers=headers) as r:
                box = (await r.json())['games'][0]['box']

            # send messages to each twitch stream if the user is in that server
            for m in messages:
                mem = m.guild.get_member(did)
                if mem is not None:
                    e = discord.Embed(
                        title=stream['channel']['status'],
                        url=stream['channel']['url'],
                        description=f'**Game** | {stream["game"]}',
                        timestamp=discord.utils.parse_time(
                            parse(stream['created_at']).isoformat())
                    ).set_image(
                        url=stream['preview']['medium'] + f'?rand={stream["_id"]}'
                    ).set_thumbnail(
                        url=box
                    ).set_author(
                        name=f"{mem.display_name} started streaming",
                        icon_url=stream['channel']['logo'] or mem.avatar_url or mem.default_avatar_url
                    )
                    try:
                        await m.edit(embed=e)
                    except discord.HTTPException as ex:
                        print(ex.response)
        except:
            traceback.print_exc()

    async def send_listen(self, ws=None, extra=None):
        if ws is None:
            ws = await self.get_ws()
        names = [t["name"].lower() for t in await self.all_twitch_users()]
        if extra:
            names = names + extra
        await ws.send(json.dumps({
            'type': 'LISTEN',
            'nonce': f'Weeabot{random.randrange(200,300)}',
            'data': {
                'topics': ['video-playback.{}'.format(t) for t in names]
            }
        }))

        # wait for response and handle errors
        r = json.loads(await ws.recv())
        if r['error']:
            print(f'error subscribing: {r["error"]}')
            return r['error']

    async def connect(self):
        if datetime.now() < self.next_connect:
            sleep = (self.next_connect - datetime.now()).seconds
            print(f"Twitch connection sleeping for {sleep}s")
            await asyncio.sleep(sleep)
        self.next_connect = datetime.now() + timedelta(seconds=120)
        print('connecting to twitch...')
        ws = await websockets.connect('wss://pubsub-edge.twitch.tv')

        if await self.send_listen(ws):
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
                    us = await self.all_twitch_users()
                    did = us[name]['did']
                    tid = us[name]['tid']

                    # send initial messages
                    messages = []
                    for c in await self.channels():
                        mem = c.guild.get_member(did)
                        messages.append(await c.send(embed=discord.Embed(
                            description='Waiting for Twitch API...'
                        ).set_author(
                            name=f"{mem.display_name} started streaming",
                            icon_url=mem.avatar_url or mem.default_avatar_url,
                            url=f'https://www.twitch.tv/{name}'
                        )))

                    self.bot.loop.create_task(self.update_stream(messages, did, tid))
            except:
                traceback.print_exc()


@Twitch.guild_config()
async def twitch_channel(ctx):
    """
    The channel where twitch streams will be posted to.
    """
    return ctx.channel.id


@twitch_channel.transform
async def get_full_channel(ctx, c_id):
    return ctx.bot.get_channel(c_id)


@Twitch.profile_field(inline=True, name='twitch')
async def twitch_profile(data):
    """
    Twitch account used to send automatic stream notifications and other commands.
    """
    return f'[{data["name"]}](https://www.twitch.tv/{data["name"]})'


@twitch_profile.set_setter
async def twitch_setter(ctx, user, value):
    http_args = {
        'headers': {"accept": "application:vnd.twitchtv.v5+json", "Client-ID": ctx.bot.config['twitch_id']},
        'url': 'https://api.twitch.tv/kraken/search/channels',
        'params': {'query': value}
    }

    async with ctx.bot.get_cog('Twitch').session.get(**http_args) as r:
        chan = (await r.json())['channels'][0]
    if await ctx.confirm(f"Closest account found: <{chan['url']}>\nIs this correct?"):
        await ctx.bot.get_cog('Twitch').send_listen(extra=[value])
        return {'name': value, 'id': chan['_id']}
    print('end reached')


def setup(bot):
    bot.add_cog(Twitch(bot))