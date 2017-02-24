import random
import traceback
import asyncio
import os
import json
import sys

from collections import defaultdict
from datetime import timedelta

import pyimgur

import discord
from discord.ext import commands
from discord.ext.commands.bot import _get_variable

import utils
import checks
from cogs.requestsystem import RequestLimit


class Weeabot(commands.Bot):
    """Simple additions to commands.Bot"""

    tracking_filter = ['debug', 'exec', 'help', 'req', 'profile']

    def __init__(self, *args, **kwargs):
        if 'description' not in kwargs:
            kwargs['description'] = "Weeabot"
        super(Weeabot, self).__init__(*args, **kwargs)
        self.owner = None  # set in on_ready
        self.trusted = utils.open_json('trusted.json')
        self.config = utils.Config('config.json')
        self.content = utils.Config('content.json')
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
        self.init = asyncio.Event(loop=self.loop)
        self.react_listeners = {}

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
        await self.init.wait()
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
        """Send a message to the channel and also PM to the bot owner."""
        await self.say(message)
        await self.send_message(self.owner, message)

    async def send_affirmative(self, message: discord.Message):
        """React to a message with the affirmative emote.

        If that is not available due to permissions, the emote will be said instead. If even that is unavailable, PM."""
        try:
            await self.add_reaction(message, '\N{OK HAND SIGN}')
        except discord.Forbidden:
            try:
                await self.send_message(message.channel, '\N{OK HAND SIGN}')
            except discord.Forbidden:
                await self.send_message(message.author, f'`{message.clean_content}` in `{message.channel}` success.')

    async def affirmative(self):
        """Equivalent to send_affirmative(ctx.message)

        React to the message that called the command with the affirmative emote.

        If that is not available due to permissions, the emote will be said instead. If even that is unavailable, PM."""
        await self.send_affirmative(_get_variable('_internal_message'))

    async def send_negative(self, message: discord.Message):
        """React to a message with the affirmative emote.

        If that is not available due to permissions, the emote will be said instead. If even that is unavailable, PM."""
        try:
            await self.add_reaction(message, '\N{CROSS MARK}')
        except discord.Forbidden:
            try:
                await self.send_message(message.channel, '\N{CROSS MARK}')
            except discord.Forbidden:
                await self.send_message(message.author, f'`{message.clean_content}` in `{message.channel}` failure.')

    async def negative(self):
        """Equivalent to send_negative(ctx.message)

        React to the message that called the command with the negative emote.

        If that is not available due to permissions, the emote will be said instead. If even that is unavailable, PM."""
        await self.send_negative(_get_variable('_internal_message'))

    async def confirm(self, message, user=None):
        """Use reactions to get a Yes/No response from the user.

        If message is a discord.Message, that message will be used for the reactions.
        If message is a string or an embed, a new message will be sent with `bot.say()` (only in commands)."""
        if isinstance(message, str):
            message = await self.say(content=message)
        elif isinstance(message, discord.Embed):
            message = await self.say(embed=message)
        await self.add_reaction(message, '\N{THUMBS UP SIGN}')
        await self.add_reaction(message, '\N{THUMBS DOWN SIGN}')
        user = user or _get_variable('_internal_author')
        reaction = await self.wait_for_reaction(['\N{THUMBS UP SIGN}', '\N{THUMBS DOWN SIGN}'], user=user, message=message)
        await self.remove_reaction(message, '\N{THUMBS UP SIGN}', message.server.me)
        await self.remove_reaction(message, '\N{THUMBS DOWN SIGN}', message.server.me)
        return reaction.reaction.emoji == '\N{THUMBS UP SIGN}'

    async def process_commands(self, message):
        """Override process_commands to add _internal_message"""
        _internal_message = message
        await super(Weeabot, self).process_commands(message)

    def inc_use(self, uid, fcn):
        if any([x in fcn for x in self.tracking_filter]):
            return
        if fcn not in self.stats['command_use']:
            self.stats['command_use'][fcn] = 0
        self.stats['command_use'][fcn] += 1
        if self.profiles is not None:
            if uid not in self.profiles.all():
                self.profiles.all()[uid] = {}
            if 'command_count' not in self.profiles.all()[uid]:
                self.profiles.all()[uid]['command_count'] = {}
            if fcn not in self.profiles.all()[uid]['command_count']:
                self.profiles.all()[uid]['command_count'][fcn] = 0
            self.profiles.all()[uid]['command_count'][fcn] += 1
            self.profiles.dump()
        self.dump_stats()

    def add_react_listener(self, msg, callback):
        """add a listener to perform an action when a reaction is done on a given message.

        Callback should be a coroutine, with the same args as on_raction_add(reaction, user).
        Does not persist through restarts."""
        self.react_listeners[utils.full_id(msg)] = callback

    def user_is_moderator(self, u):
        if not isinstance(u, discord.Member):
            return False
        s = u.server
        return s.owner == u or self.server_configs[s.id].get('moderator_role', None) in [r.id for r in u.roles]


bot = Weeabot(command_prefix='~')


@bot.event
async def on_reaction_add(reaction, user):
    m = reaction.message
    callback = bot.react_listeners.pop(utils.full_id(m), None)
    if callback:
        await callback(reaction, user)


@bot.event
async def on_command_error(err, ctx):
    if hasattr(ctx.command, "on_error"):
        return

    d = ctx.message.channel

    if type(err) is RequestLimit:
        await bot.send_message(d, err)

    if type(err) is commands.NoPrivateMessage:
        await bot.send_message(d, f'{ctx.command.name} can not be used in private messages.')

    elif type(err) is commands.DisabledCommand:
        await bot.send_message(d, 'This command is disabled.')

    elif type(err) in (commands.BadArgument, commands.errors.MissingRequiredArgument):
        name = utils.full_command_name(ctx, ctx.command)
        await bot.send_message(d, f'Invalid usage. Use `{bot.command_prefix}help {name}`\n{f"```{err}```" if str(err) else None}')

    elif type(err) is utils.CheckMsg:
        await bot.send_message(d, err)

    elif type(err) is commands.CheckFailure:
        pass

    elif type(err) is commands.CommandOnCooldown:
        def timestr(seconds):
            return utils.down_to_seconds(timedelta(seconds=seconds))

        await bot.send_message(d, f"This command is on a {timestr(err.cooldown.per)} cooldown. Try again in {timestr(err.retry_after)}")

    elif type(err) is commands.CommandNotFound:
        if ctx.invoked_with.isdigit():
            if int(ctx.invoked_with) < len(bot.tag_map):
                try:
                    await bot.tag_map.get_by_id(int(ctx.invoked_with)).run(ctx)
                except IndexError:
                    await bot.send_message(ctx.message.channel, "id not found.")
            else:
                await bot.send_message(ctx.message.channel, "id not found.")
        elif ctx.invoked_with.lower() in bot.tag_map.taglist:
            t = ctx.invoked_with.split()[0]
            try:
                await bot.tag_map.get(ctx.message, t).run(ctx)
            except KeyError:
                pass

    else:
        print(f'Ignoring exception in command {ctx.command}', file=sys.stderr)
        traceback.print_exception(type(err), err, err.__traceback__, file=sys.stderr)


@bot.event
async def on_command_completion(command, ctx):
    """Event listener for command_completion."""
    fcn = utils.full_command_name(ctx, command)
    if "tag" not in fcn and ("image" not in fcn and fcn not in ["image reddit", "image booru"]):
        bot.inc_use(ctx.message.author.id, fcn)


@bot.event
async def on_ready():
    await bot.update_owner()
    print(f'Bot: {bot.user.name}:{bot.user.id}')
    print(f'Owner: {bot.owner.name}:{bot.owner.id}')
    print('------------------')
    bot.init.set()


@bot.event
async def on_member_join(member):
    """Called whenever a new member joins a server."""
    try:
        ar = bot.server_configs[member.server.id]['autorole']
        role = discord.utils.get(member.server.roles, id=ar)
        await bot.add_roles(member, role)
    except KeyError:
        pass


@bot.event
async def on_server_join(server):
    """Called when the bot joins a server or creates one."""
    await bot.send_message(bot.owner, f"Joined Server: {server}")
    await bot.send_message(server.default_channel, f"Hello! use {bot.command_prefix}help and {bot.command_prefix}services to see what I can do.")


@bot.command(name='services')
async def service_command():
    """Show how to use non-command features of the bot."""
    await bot.say('\n'.join([f'```\n{k}:\n\n{v}\n```' for k, v in bot.services.items()]))


@bot.group(aliases=('e',), invoke_without_command=True)
@checks.is_owner()
async def extensions():
    """Extension related commands.

    Invoke without a subcommand to list extensions."""
    loaded = ' '.join(bot.cogs.keys())
    all_ex = ' '.join([x for x in os.listdir('cogs') if '.py' in x])
    await bot.say(f'Loaded: {loaded}\nAll: {all_ex}')


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
    await bot.init.wait()
    while not bot.is_closed:
        n = random.choice(bot.content.statuses)
        await bot.change_presence(game=discord.Game(name=n, url='', type=0))
        await asyncio.sleep(60)


if __name__ == '__main__':
    bot.loop.create_task(random_status())
    bot.run(utils.tokens['discord_token'])
