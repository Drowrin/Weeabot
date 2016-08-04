import json
import io
import aiohttp
import random
from os import path
from os import listdir
from functools import wraps
from discord.ext import commands


def is_owner():
    """Decorator to allow a command to run only if it is called by the owner."""
    return commands.check(lambda ctx: ctx.message.author.id == ctx.bot.owner.id)


def is_server_owner():
    """Decorator to allow a command to run only if called by the server owner."""
    return commands.check(lambda ctx: not ctx.message.channel.is_private and ctx.message.server.owner.id == ctx.message.author.id)


def testing(ctx):
    if ctx.message.channel.is_private:
        if ctx.message.author.id == ctx.bot.owner.id:
            return True
        return False
    if ctx.message.server.id in ctx.bot.config.testing_servers:
        return True
    if ctx.message.channel.id in ctx.bot.config.testing_channels:
        return True
    return False


def is_testing():
    """Only allowed in 'safe' environments.
    
    Servers and channels approved by the bot owner, or in PMs by the bot owner.
    
    Intended for testing new features before making them more public."""
    return commands.check(testing)


def loaded_profiles(bot):
    return bot.profiles is not None


def profiles():
    """Make sure the command only runs if the profiles cog is loaded."""
    return commands.check(lambda ctx: loaded_profiles(ctx.bot))


def loaded_tools(bot):
    return bot.tools is not None


def tools():
    """Make sure the command only runs if the tools cog is loaded."""
    return commands.check(lambda ctx: loaded_tools(ctx.bot))


def is_channel(name: str):
    """Decorator to allow a command to run only if it is in a specified channel (by name)."""
    def _is_channel(ctx):
        try:
            ch = commands.ChannelConverter(ctx, name).convert()
        except commands.BadArgument:
            raise commands.CheckFailure('Only allowed in a channel called {}.'.format(name))
        if ctx.message.channel.id != ch.id:
            raise commands.CheckFailure('Only allowed in {}.'.format(ch.mention))
        return True
    return commands.check(_is_channel)


def get_user(bot, idn: str):
    """Get a user from all servers the bot is in."""
    for s in bot.servers:
        u = s.get_member(idn)
        if u:
            return u


# noinspection PyUnusedLocal
def full_command_name(ctx, command):
    """Return the 'full' command name.
    
    This is, essentially, the beginning of the message that called the command.
    However, base command names are used, not aliases.
    
    Separated by spaces, just as the command was called."""
    command = ctx.command
    names = [command.name]
    while command.parent:
        command = command.parent
        names.insert(0, command.name)
    return ' '.join(names)


def request(owner_bypass=True, server_bypass=True, bypasses=[], bypasser=any):
    """Decorator to make a command requestable.
    
    Requestable commands are commands you want to lock down permissions for.
    However, requestable commands can still be called by members but will need to be approved before executing.
    
    The following behaivior is followed:
        1. If a member calls the command, a request is sent to the server owner including the command and args.
        2. Server owners can approve these requests, which are then elevated as requests to the bot owner.
        3. If a server owner calls the command, a request is sent directly to the bot owner.
        4. If the bot owner approves the request, it is executed normally.
        5. If the bot owner calls the command, it executes normally.
        6. Similarly, if the bot owner accepts a local request on a server they own, it bypasses the global check.
    
    Requests can only be called in PMs by the bot owner.
    
    Requested commands are pickled to disk, so they persist through restarts.
    
    Attributes
    ----------
    owner_bypass : Optional[bool]
        If ``True``, the bot owner can bypass the requests system entirely.
        Defaults to ``True``.
    server_bypass : Optional[bool]
        If ``True``, the server owner can bypass the server level of requests.
        Defaults to ``True``.
    bypasses : list
        A list of bypass predicates accepting ctx to be used on the command.
        This differs from a list of checks in that it immediately bypasses the requests system.
        Defaults to an empty list.
    bypasser : callable
        This is a predicate that takes the list of results from 'bypasses'.
        If ``True`` is returned, the request system is bypassed.
        Defaults to ``any``.
    """
    
    def request_predicate(ctx):
        # tools cog must be loaded to use requests.
        if not loaded_tools(ctx.bot):
            return False
        # Always pass on help so it shows up in the list.
        if ctx.command.name == 'help':
            return True
        # Bot owner bypass.
        if ctx.message.author.id == ctx.bot.owner.id and owner_bypass:
            return True
        # Not allowed in PMs.
        if ctx.message.channel.is_private:
            raise commands.CheckFailure("This command can not be called from PMs.")
        if bypasser(bypass(ctx) for bypass in bypasses):
            return True
        # If its already at the global level and has been accepted, it passes.
        if ctx.message in ctx.bot.tools.get_serv('owner')['list']:
            return True
        # If it is at the server level and has been accepted, elevate it. Also, server owner bypass.
        if ctx.message.id == ctx.message.server.owner.id or ctx.message in ctx.bot.tools.get_serv(ctx.message.server.id)['list']:
            ctx.bot.loop.create_task(ctx.bot.tools.add_request(ctx.message, 'owner'))
            return False
        # Otherwise, this is a fresh request, add it to the server level.
        ctx.bot.loop.create_task(ctx.bot.tools.add_request(ctx.message, ctx.message.server.id))
        return False
    
    return commands.check(request_predicate)


def request_command(base=commands.command, **comargs):
    pass_ctx = comargs.get('pass_context', False)
    comargs['pass_context'] = True

    def dec(func):
        @wraps(func)
        async def wrapp(*args, **kwargs):
            has_self = not isinstance(args[0], commands.Context)
            ctx = args[1] if has_self else args[0]  # for inside a class where first arg is self
            if ctx.message.channel.is_private and ctx.message.author.id != ctx.bot.owner.id:
                await ctx.bot.say("Requests can not be made from PMs.")
            arglist = [*args]
            if not pass_ctx:
                del arglist[1 if has_self else 0]
            a = tuple(arglist)
            if ctx.message.author.id != ctx.bot.owner.id and ctx.message not in ctx.bot.tools.get_serv('owner')['list']:
                if ctx.message.author.id == ctx.message.server.owner.id \
                        or ctx.message in ctx.bot.tools.get_serv(ctx.message.server.id)['list']:
                    await ctx.bot.tools.add_request(ctx.message, 'owner')
                    return
                else:
                    await ctx.bot.tools.add_request(ctx.message, ctx.message.server.id)
                    return
            result = await func(*a, **kwargs)
            return result
        return base(**comargs)(wrapp)
    return dec


async def download(session: aiohttp.ClientSession, link: str, path: str):
    """Quick and easy download utility."""
    async with session.get(link) as r:
        val = await r.read()
        with open(path, "wb") as f:
            f.write(val)


async def download_fp(session: aiohttp.ClientSession, link: str):
    """Download to a memory filepointer, instead of disk."""
    async with session.get(link) as r:
        fp = io.BytesIO()
        val = await r.read()
        fp.write(val)
        fp.seek(0)
    return fp


def is_command_of(bot, message):
    """Determine if a message is a command of a bot."""
    prefix = bot.command_prefix
    if callable(prefix):
        prefix = prefix(bot, message)
    return any([message.content.startswith(p) for p in list(prefix)])


def open_json(fn: str):
    """Open a json file and handle the errors."""
    try:
        with open(fn) as f:
            return json.load(f)
    except FileNotFoundError:
        with open(fn, 'w') as f:
            json.dump({}, f)
            return {}


def get_random_file(d: str, s: str, t: str = None):
    """Get a file from a subdirectory."""
    if s in listdir(d):
        d = path.join(d, s)
        if t:
            return path.join(d, random.choice([f for f in listdir(d) if f.endswith(t)]))
        else:
            return path.join(d, random.choice(listdir(d)))


class SessionCog:
    """Simple class to take care of using a aiohttp session in a cog."""
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    def __unload(self):
        self.bot.loop.create_task(self.session.close())


tokens = open_json('tokens.json')
