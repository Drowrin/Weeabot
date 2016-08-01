import sys
# noinspection PyUnresolvedReferences
import discord
# noinspection PyUnresolvedReferences
from discord.ext import commands

import random

import asyncio

from utils import *


class Weeabot(commands.Bot):
    """Simple additions to commands.Bot"""
    def __init__(self, *args, **kwargs):
        super(Weeabot, self).__init__(*args, **kwargs)
        self.owner = None  # set in on_ready
        self.formatters = {}
        self.verbose_formatters = {}
        self.load_extension('cogs.profiles')
        self.load_extension('cogs.owner')
        self.required_extensions = {'Tools': 'owner', 'Profile': 'profiles'}
    
    @property
    def profiles(self):
        return self.get_cog('Profile')
    
    @property
    def tools(self):
        return self.get_cog('Tools')

    def add_cog(self, cog):
        super(Weeabot, self).add_cog(cog)
        self.add_formats(cog)

    def remove_cog(self, name):
        cog = self.get_cog(name)
        if hasattr(cog, 'formatters'):
            for f in cog.formatters:
                del self.formatters[f]
        if hasattr(cog, 'verbose_formatters'):
            for f in cog.verbose_formatters:
                del self.formatters[f]
        super(Weeabot, self).remove_cog(name)

    def add_formats(self, formattable):
        self.formatters.update(getattr(formattable, 'formatters', {}))
        self.verbose_formatters.update(getattr(formattable, 'verbose_formatters', {}))


desc = """
Weeabot
I have a lot of (mostly) useless commands. Enjoy!
"""
bot = Weeabot(command_prefix='~', description=desc)

base_extensions = ['cogs.rng',
                   'cogs.images',
                   'cogs.mal',
                   'cogs.pointless',
                   'cogs.twitch']

status = open_json('statuses.json') or []


@bot.event
async def on_command_error(err, ctx):
    d = ctx.message.channel
    if type(err) is commands.NoPrivateMessage:
        await bot.send_message(d, '{} can not be used in private messages.'.format(ctx.command.name))
    elif type(err) is commands.DisabledCommand:
        await bot.send_message(d, 'This command is disabled.')
    elif type(err) in (commands.BadArgument, commands.errors.MissingRequiredArgument):
        await bot.send_message(d, 'Invalid usage. Use {}help {}'.format(bot.command_prefix, ctx.command.name))
    elif type(err) is commands.CheckFailure:
        await bot.send_message(d, err)
    elif type(err) is commands.CommandNotFound:
        pass
    else:
        raise err


@bot.event
async def on_ready():
    bot.owner = list(await bot.application_info())[-1]
    print(bot.owner)
    print('Bot: {0.name}:{0.id}'.format(bot.user))
    print('Owner: {0.name}:{0.id}'.format(bot.owner))
    print('------------------')
    await load_extensions()


async def random_status():
    """Rotating statuses."""
    await bot.wait_until_ready()
    while not bot.is_closed:
        n = random.choice(status)
        g = discord.Game(name=n, url='', type=0)
        await bot.change_status(game=g, idle=False)
        await asyncio.sleep(60)


async def load_extensions():
    """Load extensions and handle errors."""
    for ext in base_extensions:
        try:
            bot.load_extension(ext)
        except Exception as e:
            await bot.send_message(bot.owner, 'Failure loading {}\n{}: {}\n'.format(ext, type(e).__name__, e))


if __name__ == '__main__':
    bot.do_restart = False
    bot.loop.create_task(random_status())
    bot.run(tokens['discord_token'])
    if bot.do_restart:
        os.execv('Weeabot.py', sys.argv)
