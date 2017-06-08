import asyncio
import os
import random

import discord
from discord.ext import commands

from weeabot import utils
from .context import Context
from .message import Message


class Weeabot(commands.Bot):
    """
    Simple additions to commands.Bot
    """

    def __init__(self, *args, **kwargs):
        # get config file first, since it can contain args passed to super.__init__.
        self.config = utils.Config(os.path.join('config', 'config.json'), default={
            "prefix": "~",
            "description": "Weeabot",
            "ignored_cogs": [],
            "chatterbot": {
                "import_path": "chatterbot.storage.MongoDatabaseAdapter",
                "database_uri": "mongodb://localhost:27017/",
                "database": "chatterbot-database"
            },
            "trusted": []
        })
        if 'command_prefix' not in kwargs:
            kwargs['command_prefix'] = self.config.prefix
        if 'description' not in kwargs:
            kwargs['description'] = self.config.description

        # init commands.Bot
        super(Weeabot, self).__init__(*args, **kwargs)

        self.owner = None  # set in on_ready

        self.content = utils.content

        # storage of information related to continuing operation of the bot
        self.guild_configs = utils.Storage('status', 'guilds.json')
        self.status = utils.Storage('status', 'status.json')

        # added to by cogs
        self.services = {}
        self.formatters = {}
        self.verbose_formatters = {}
        self.defaults = {}
        self.object_hooks = {}

        self.loop.create_task(self.load_extensions())
        self.loop.create_task(self.random_status())

        self.init = asyncio.Event(loop=self.loop)

    def run(self, token=None, **kwargs):
        if not utils.tokens.discord_token:
            print(f'Please add your token to {utils.tokens._path}')
            input()
            quit()
        super(Weeabot, self).run(token or utils.tokens.discord_token, **kwargs)

    async def on_message(self, message):
        await self.process_commands(Message(self, message))

    async def process_commands(self, message):
        ctx = Context(self, await self.get_context(message))
        await self.invoke(ctx)

    async def update_owner(self):
        await self.wait_until_ready()
        self.owner = (await self.application_info()).owner

    async def load_extensions(self):
        """
        Load extensions and handle errors.
        """
        await self.init.wait()
        for n in os.listdir(os.path.join('weeabot', 'cogs')):
            if n[:-3] not in self.config.ignored_cogs and n.endswith('.py') and not n.startswith('_'):
                self.load_extension(f'weeabot.cogs.{n[:-3]}')

    async def on_ready(self):
        await self.update_owner()
        print(f'Bot: {self.user.name}:{self.user.id}')
        print(f'Owner: {self.owner.name}:{self.owner.id}')
        print('------------------')
        self.init.set()

    async def random_status(self):
        """Rotating statuses."""
        await self.init.wait()
        while not self.is_closed:
            n = random.choice(self.content.statuses)
            await self.change_presence(game=discord.Game(name=n, url='', type=0))
            await asyncio.sleep(60)
