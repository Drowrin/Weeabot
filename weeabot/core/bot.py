import datetime
import os
import re
import asyncio
import random
import humanize

from copy import copy

import discord
from discord.ext import commands

from weeabot import utils
from . import aug
from weeabot.storage.db import DBHelper
from ruamel import yaml
from vibora import Vibora


class Weeabot(commands.Bot):
    """
    Simple additions to commands.Bot
    """

    def __init__(self, config_path, *args, content_path=None, **kwargs):
        # run augmentation
        aug.augmenter.properties['__client'] = lambda x: self
        aug.augmenter()

        # get config file first, since it can contain args passed to super.__init__.
        with open(config_path) as c:
            self.config = yaml.load(c, Loader=yaml.Loader)

        bot_kwargs = {}
        bot_kwargs.update(kwargs)
        if 'command_prefix' not in bot_kwargs:
            bot_kwargs['command_prefix'] = self.config['prefix']
        if 'description' not in bot_kwargs:
            bot_kwargs['description'] = self.config['description']

        # init commands.Bot
        super(Weeabot, self).__init__(*args, **bot_kwargs)

        # load content.yml
        if content_path is None:
            content_path = os.path.join(os.path.dirname(config_path), 'content.yml')
        with open(content_path) as c:
            self.content = yaml.load(c, Loader=yaml.Loader)

        # set in on_ready
        self.owner = None
        self.author = None

        # added to by cogs
        self.services = {}
        self.profile_fields = {}
        self.object_hooks = {}
        self.guild_configs = {}

        # webserver
        from ..web.base import base
        from ..web.oauth import OAuthHelper
        self.oauth = OAuthHelper(self)
        self.web = Vibora()
        self.web.components.add(self)  # make this bot instance available in any route
        self.web.add_blueprint(base, prefixes={'base': '/'})

        # database
        self.db = DBHelper(self.config['db']['dsn'], self)

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

    async def update_owner(self):
        await self.wait_until_ready()
        self.owner = (await self.application_info()).owner
        self.author = await self.get_user_info(81149671447207936)

    async def load_extensions(self):
        """
        Load extensions and handle errors.
        """
        for n in self.config['default_cogs']:
            self.load_extension(n)

    async def on_message(self, message):
        await self.init.wait()
        await self.process_commands(message)

    async def on_command_error(self, ctx: commands.Context, exception):

        # nice error report formatting
        name = re.sub(r'(?!^)([A-Z][a-z]+)', r' \1', exception.__class__.__name__)
        message = f"{name}: {exception}" if len(str(exception)) else name

        # repond to user input error
        if isinstance(exception, commands.UserInputError):
            await ctx.send(message)
            return

        # tag fallback from command not found
        # essentially allows shortcutting out stub calls
        if isinstance(exception, commands.CommandNotFound):
            if await self.db.does_tag_exist(ctx.guild, ctx.invoked_with):
                # inject stub command call for proper tracking etc
                m = copy(ctx.message)
                m.content = f'{ctx.prefix}stub {ctx.message.content[len(ctx.prefix):]}'
                await self.process_commands(m)
            else:
                pass  # Here is where fuzzy searching could be done.
            return

        await super(Weeabot, self).on_command_error(ctx, exception)

    @utils.run_once
    async def on_ready(self):
        await self.update_owner()
        print(f'Bot: {self.user.name}:{self.user.id}')
        print(f'Owner: {self.owner.name}:{self.owner.id}')
        print('------------------')
        await self.load_extensions()
        await self.web.run(**self.config['web']['server'])
        await self.db.prepare()
        self.loop.create_task(self.random_status())
        self.init.set()

    async def random_status(self):
        """Rotating statuses."""
        while not self.is_closed():
            n = random.choice(self.content['statuses'])
            await self.change_presence(activity=discord.Game(name=n, url='', type=0))
            await asyncio.sleep(60)
