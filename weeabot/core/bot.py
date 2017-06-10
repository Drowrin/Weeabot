import datetime
import asyncio
import random
import humanize

import discord
from discord.ext import commands

from weeabot import utils
from .context import Context
from .message import Message

from ruamel import yaml
from kyoukai import Kyoukai

from ..web.base import base


class Weeabot(commands.Bot):
    """
    Simple additions to commands.Bot
    """

    def __init__(self, config_path, *args, **kwargs):
        # get config file first, since it can contain args passed to super.__init__.\
        with open(config_path) as c:
            self.config = yaml.load(c, Loader=yaml.Loader)
        if 'command_prefix' not in kwargs:
            kwargs['command_prefix'] = self.config['prefix']
        if 'description' not in kwargs:
            kwargs['description'] = self.config['description']

        # init commands.Bot
        super(Weeabot, self).__init__(*args, **kwargs)

        # set in on_ready
        self.owner = None
        self.author = None

        # storage of information related to continuing operation of the bot
        self.guild_configs = utils.Storage('status', 'guilds.json')
        self.status = utils.Storage('status', 'status.json')

        # added to by cogs
        self.services = {}
        self.formatters = {}
        self.verbose_formatters = {}
        self.defaults = {}
        self.object_hooks = {}

        # webserver
        self.web = Kyoukai("Weeabot")

        @self.web.root.before_request
        async def add_bot(ctx):
            # add the bot to the ctx so it can be accessed in requests
            # pretty much everything else can be accessed through the bot so it is the only thing necessary
            ctx.bot = self
            return ctx

        self.loop.create_task(self.load_extensions())
        self.loop.create_task(self.random_status())

        self.init = asyncio.Event(loop=self.loop)

        self.start_time = datetime.datetime.now()

    @property
    def uptime(self):
        """
        How long the bot has been running, formatted with humanize.
        """
        return humanize.naturaldelta(datetime.datetime.now() - self.start_time)

    def run(self, token=None, **kwargs):
        if not self.config['discord_token']:
            print('Please add your token to the config')
            input()
            quit()
        super(Weeabot, self).run(token or self.config['discord_token'], **kwargs)

    async def on_message(self, message):
        await self.process_commands(Message(self, message))

    async def process_commands(self, message):
        ctx = Context(self, await self.get_context(message))
        await self.invoke(ctx)

    async def update_owner(self):
        await self.wait_until_ready()
        self.owner = (await self.application_info()).owner
        self.author = await self.get_user_info(81149671447207936)

    async def load_extensions(self):
        """
        Load extensions and handle errors.
        """
        await self.init.wait()
        for n in self.config['default_cogs']:
            self.load_extension(n)

    async def on_ready(self):
        await self.update_owner()
        print(f'Bot: {self.user.name}:{self.user.id}')
        print(f'Owner: {self.owner.name}:{self.owner.id}')
        print('------------------')
        self.web.register_blueprint(base)
        self.web.finalize()
        await self.web.start(**self.config['web']['server'])
        self.init.set()

    async def random_status(self):
        """Rotating statuses."""
        await self.init.wait()
        while not self.is_closed:
            n = random.choice(self.content.statuses)
            await self.change_presence(game=discord.Game(name=n, url='', type=0))
            await asyncio.sleep(60)
