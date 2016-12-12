import random
import traceback
import asyncio
import os
import json
import sys

from collections import defaultdict

import pyimgur

import discord
from discord.ext import commands

import utils
import checks


class Config:
    def __init__(self, config_path):
        self.path = config_path
        self._db = utils.open_json(config_path)
        self.__dict__.update(self._db)

    def __getattr__(self, name):
        return self.__dict__.get(name, None)

    def _dump(self):
        for k in self._db:
            self._db[k] = self.__dict__[k]
        with open(self.path, 'w') as f:
            json.dump(self._db, f, ensure_ascii=True)

    async def save(self):
        await asyncio.get_event_loop().run_in_executor(None, self._dump)


class Weeabot(commands.Bot):
    """Simple additions to commands.Bot"""
    def __init__(self, *args, **kwargs):
        if 'description' not in kwargs:
            kwargs['description'] = "Weeabot"
        super(Weeabot, self).__init__(*args, **kwargs)
        self.owner = None  # set in on_ready
        self.config = Config('config.json')
        self.content = Config('content.json')
        self.stats = defaultdict(dict)
        self.stats.update(utils.open_json('stats.json'))
        self.server_configs = utils.open_json('servers.json')
        self.status = utils.open_json('status.json')
        self.imgur = pyimgur.Imgur(utils.tokens['imgur_token'], utils.tokens["imgur_secret"])
        self.services = {}
        self.formatters = {}
        self.verbose_formatters = {}
        self.defaults = {}
        self.loop.create_task(self.load_extensions())

    def dump_server_configs(self):
        with open('servers.json', 'w') as f:
            json.dump(self.server_configs, f, ensure_ascii=True)

    def dump_status(self):
        with open('status.json', 'w') as f:
            json.dump(self.status, f, ensure_ascii=True)

    def dump_stats(self):
        with open('stats.json', 'w') as f:
            json.dump(self.stats, f, ensure_ascii=True)
    
    @property
    def profiles(self):
        return self.get_cog('Profile')
    
    @property
    def tools(self):
        return self.get_cog('Tools')

    @property
    def requestsystem(self):
        return self.get_cog('RequestSystem')

    @property
    def tag_map(self):
        return self.get_cog('TagMap')

    async def load_extensions(self):
        """Load extensions and handle errors."""
        await self.wait_until_ready()
        self.load_extension('cogs.profiles')
        self.load_extension('cogs.tools')
        self.load_extension('cogs.requestsystem')
        self.load_extension('cogs.tagsystem')
        for ext in self.config.base_extensions:
            self.load_extension(ext)

    async def update_owner(self):
        await self.wait_until_ready()
        self.owner = (await self.application_info()).owner

    def add_cog(self, cog):
        super(Weeabot, self).add_cog(cog)
        self.services.update(getattr(cog, 'services', {}))
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

    async def notify(self, message: str):
        await self.say(message)
        await self.send_message(self.owner, message)

    def inc_use(self, fcn):
        if fcn not in self.stats['command_use']:
            self.stats['command_use'][fcn] = 0
        self.stats['command_use'][fcn] += 1
        self.dump_stats()

    async def on_command_completion(self, command, ctx):
        """Event listener for command_completion."""
        fcn = utils.full_command_name(ctx, command)
        if "tag" not in fcn and ("image" not in fcn and fcn not in ["image reddit", "image booru"]):
            self.inc_use(fcn)

    async def on_command_error(self, err, ctx):
        if hasattr(ctx.command, "on_error"):
            return

        d = ctx.message.channel

        if type(err) is commands.NoPrivateMessage:
            await self.send_message(d, '{} can not be used in private messages.'.format(ctx.command.name))

        elif type(err) is commands.DisabledCommand:
            await self.send_message(d, 'This command is disabled.')

        elif type(err) in (commands.BadArgument, commands.errors.MissingRequiredArgument):
            name = utils.full_command_name(ctx, ctx.command)
            await self.send_message(d, 'Invalid usage. Use {}help {}'.format(self.command_prefix, name))

        elif type(err) is utils.CheckMsg:
            await self.send_message(d, err)

        elif type(err) is commands.CheckFailure:
            pass

        elif type(err) is commands.CommandNotFound:
            if ctx.invoked_with.isdigit():
                if int(ctx.invoked_with) < len(self.tag_map):
                    try:
                        await self.tag_map.get_by_id(int(ctx.invoked_with)).run(ctx)
                    except IndexError:
                        await self.send_message(ctx.message.channel, "id not found.")
                else:
                    await self.send_message(ctx.message.channel, "id not found.")
            elif ctx.invoked_with.lower() in self.tag_map.taglist:
                t = ctx.invoked_with.split()[0]
                if self.profiles is not None:
                    await self.profiles.inc_use(ctx.message.author.id, "tag " + t)
                await self.tag_map[t].run(ctx)

        else:
            print('Ignoring exception in command {}'.format(ctx.command), file=sys.stderr)
            traceback.print_exception(type(err), err, err.__traceback__, file=sys.stderr)

    async def on_server_join(self, server):
        """Called when the bot joins a server or creates one."""
        await bot.send_message(self.owner, "Joined Server: {}".format(server))
        await bot.send_message(server.default_channel, "Hello! use ~help and ~services to see what I can do.")

    async def on_member_join(self, member):
        """Called whenever a new member joins a server."""
        try:
            ar = self.server_configs[member.server.id]['autorole']
            role = discord.utils.get(member.server.roles, id=ar)
            await self.add_roles(member, role)
        except KeyError:
            pass

    async def on_ready(self):
        await self.update_owner()
        print('Bot: {0.name}:{0.id}'.format(bot.user))
        print('Owner: {0.name}:{0.id}'.format(bot.owner))
        print('------------------')


bot = Weeabot(command_prefix='~')


@bot.command(name='services')
async def service_command():
    """Show how to use non-command features of the bot."""
    fmt = '```\n{}:\n\n{}\n```'
    await bot.say('\n'.join([fmt.format(k, v) for k, v in bot.services.items()]))


@bot.group(aliases=('e',), invoke_without_command=True)
@checks.is_owner()
async def extensions():
    """Extension related commands.

    Invoke without a subcommand to list extensions."""
    await bot.say('Loaded: {}\nAll: {}'.format(' '.join(bot.cogs.keys()),
                                               ' '.join([x for x in os.listdir('cogs') if '.py' in x])))


@extensions.command(name='load', alises=('l',))
@checks.is_owner()
async def load_extension(ext):
    """Load an extension."""
    # noinspection PyBroadException
    try:
        if not ext.startswith('cogs.'):
            ext = 'cogs.{}'.format(ext)
        bot.load_extension(ext)
    except Exception:
        await bot.say('```py\n{}\n```'.format(traceback.format_exc()))
    else:
        await bot.say('{} loaded.'.format(ext))


@extensions.command(name='unload', aliases=('u',))
@checks.is_owner()
async def unload_extension(ext):
    """Unload an extension."""
    if ext in bot.config.required_extensions:
        await bot.say("{} is a required extension.".format(ext))
        return
    # noinspection PyBroadException
    try:
        bot.unload_extension(ext)
    except Exception:
        await bot.say('```py\n{}\n```'.format(traceback.format_exc()))
    else:
        await bot.say('{} unloaded.'.format(ext))


@extensions.command(name='reload', aliases=('r',))
@checks.is_owner()
async def reload_extension(ext):
    """Reload an extension."""
    # noinspection PyBroadException
    try:
        if not ext.startswith('cogs.'):
            ext = 'cogs.{}'.format(ext)
        bot.unload_extension(ext)
        bot.load_extension(ext)
    except Exception:
        await bot.say('```py\n{}\n```'.format(traceback.format_exc()))
    else:
        await bot.say('{} reloaded.'.format(ext))


@bot.command(pass_context=True)
@checks.is_server_owner()
async def autorole(ctx, role: str):
    """Automatically assign a role to new members."""
    try:
        role = commands.RoleConverter(ctx, role).convert()
    except commands.BadArgument:
        await bot.say("Can't find {}".format(role))
        return
    bot.server_configs.get(role.server.id, {})['autorole'] = role.id
    bot.dump_server_configs()
    await bot.say("New members will now be given the {} role.".format(role.name))


async def random_status():
    """Rotating statuses."""
    await bot.wait_until_ready()
    while not bot.is_closed:
        n = random.choice(bot.content.statuses)
        await bot.change_presence(game=discord.Game(name=n, url='', type=0))
        await asyncio.sleep(60)


if __name__ == '__main__':
    bot.loop.create_task(random_status())
    bot.run(utils.tokens['discord_token'])
