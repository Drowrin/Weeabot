# noinspection PyUnresolvedReferences
import discord
# noinspection PyUnresolvedReferences
from discord.ext import commands

import random

import asyncio

from utils import *


class Config:
    def __init__(self, **fields):
        self.__dict__.update(fields)

    def __getattr__(self, name):
        return self.__dict__.get(name, None)


class Weeabot(commands.Bot):
    """Simple additions to commands.Bot"""
    def __init__(self, *args, **kwargs):
        super(Weeabot, self).__init__(*args, **kwargs)
        self.owner = None  # set in on_ready
        self.config = Config(**open_json('config.json'))
        self.content = Config(**open_json('content.json'))
        self.formatters = {}
        self.verbose_formatters = {}
        self.defaults = {}
        self.load_extension('cogs.profiles')
        self.load_extension('cogs.tools')
        self.loop.create_task(self.load_extensions())
    
    @property
    def profiles(self):
        return self.get_cog('Profile')
    
    @property
    def tools(self):
        return self.get_cog('Tools')

    async def load_extensions(self):
        """Load extensions and handle errors."""
        await self.wait_until_ready()
        for ext in self.config.base_extensions:
            try:
                self.load_extension(ext)
            except Exception as e:
                await self.send_message(self.owner, 'Failure loading {}\n{}: {}\n'.format(ext, type(e).__name__, e))

    async def update_owner(self):
        await self.wait_until_ready()
        self.owner = (await self.application_info()).owner

    def add_cog(self, cog):
        super(Weeabot, self).add_cog(cog)
        self.formatters.update(getattr(cog, 'formatters', {}))
        self.verbose_formatters.update(getattr(cog, 'verbose_formatters', {}))
        self.defaults.update(getattr(cog, 'defaults', {}))

    def remove_cog(self, name):
        cog = self.get_cog(name)
        if hasattr(cog, 'formatters'):
            for f in cog.formatters:
                del self.formatters[f]
        if hasattr(cog, 'verbose_formatters'):
            for f in cog.verbose_formatters:
                del self.verbose_formatters[f]
        if hasattr(cog, 'defaults'):
            for d in cog.defaults:
                del self.defaults[d]
        super(Weeabot, self).remove_cog(name)

desc = """
Weeabot
I have a lot of (mostly) useless commands. Enjoy!
"""
bot = Weeabot(command_prefix='~', description=desc)


@bot.group(name='testing')
@is_owner()
async def test():
    pass


@test.command(pass_context=True, name='list')
@is_owner()
async def list_test():
    servs = [bot.get_server(x) for x in bot.config['testing_servers']]
    chans = [discord.utils.get(bot.get_all_channels(), id=x) for x in bot.config['testing_channels']
    await bot.say('servers:\n{}\n\nchannels:\n{}'.format(servs, chans))


@test.command(pass_context=True, name='add', no_pm=True)
@is_owner()
async def add_test(ctx, typ: str='channel'):
    """args are 'channel' or 'server'"""
    if typ == 'channel':
        bot.config['testing_channels'].append(ctx.message.channel.id)
    if typ == 'server':
        bot.config['testing_servers'].append(ctx.message.server.id)
    else:
        await bot.say("Possible args are 'channel' and 'server'")
        return
    await bot.say("Added. \N{OK HAND SIGN}")
    

@test.command(pass_context=True, name='remove', no_pm=True)
@is_owner()
async def remove_test(ctx, typ: str='channel'):
    """args are 'channel' or 'server'"""
    if typ == 'channel':
        bot.config['testing_channels'].remove(ctx.message.channel.id)
    if typ == 'server':
        bot.config['testing_servers'].remove(ctx.message.server.id)
    else:
        await bot.say("Possible args are 'channel' and 'server'")
        return
    await bot.say("Removed. \N{OK HAND SIGN}")


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
async def on_server_join(server):
    """Called when the bot joins a server or creates one."""
    await bot.send_message(bot.owner, "Joined Server: {}".format(server))


@bot.event
async def on_ready():
    await bot.update_owner()
    print('Bot: {0.name}:{0.id}'.format(bot.user))
    print('Owner: {0.name}:{0.id}'.format(bot.owner))
    print('------------------')


async def random_status():
    """Rotating statuses."""
    await bot.wait_until_ready()
    while not bot.is_closed:
        n = random.choice(bot.content.statuses)
        g = discord.Game(name=n, url='', type=0)
        await bot.change_status(game=g, idle=False)
        await asyncio.sleep(60)


if __name__ == '__main__':
    bot.loop.create_task(random_status())
    bot.run(tokens['discord_token'])
