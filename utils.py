import json
import io
import aiohttp
from functools import wraps
from discord.ext import commands


def is_owner():
    """Decorator to allow a command to run only if it is called by the owner."""
    return commands.check(lambda ctx: ctx.message.author.id == ctx.bot.owner.id)


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


def request_command(base=commands.command, owner_pass=True, **comargs):
    """Decorator to add a 'request command'.
    
    Request commands follow a set of behaviors:
        1. If the owner calls the command, it goes through normally.
        2. If another user calls the command, the call is stored, but not acted upon.
        3. Stored commands may be accepted or rejected by the owner.
            If accepted, a request command is invoked as if the original author had called it.
    
    Request commands are pickled to disk, so they persist through restarts.
    
    A 'base' decorator may be passed in. The default is discord.ext.commands.command"""
    pass_ctx = comargs.get('pass_context', False)
    comargs['pass_context'] = True

    def dec(func):
        @wraps(func)
        async def wrapp(*args, **kwargs):
            has_self = not isinstance(args[0], commands.Context)
            ctx = args[1] if has_self else args[0]  # for inside a class where first arg is self
            arglist = [*args]
            if not pass_ctx:
                del arglist[1 if has_self else 0]
            a = tuple(arglist)
            if ctx.message.id not in ctx.bot.tools.get_serv(ctx.message.server.id)['list']:
                if ctx.message.author.id != ctx.bot.owner.id or not owner_pass:
                    if ctx.message.author == ctx.message.server.owner:
                        await ctx.bot.say("Sent request to {}.".format(ctx.bot.owner.display_name))
                        await ctx.bot.tools.add_request(ctx.message, 'owner')
                        return
                    else:
                        await ctx.bot.say("Sent request to {}.".format(ctx.message.server.owner.display_name))
                        await ctx.bot.tools.add_request(ctx.message, ctx.message.server.id)
                        return
            result = await func(*a, **kwargs)
            return result
        return base(**comargs)(wrapp)
    return dec


def text_transform_command(base=commands.command, clean=True, **comargs):
    """Decorator to add a Text Transform Command.
    
    Text transform commands need to behave a bit differently when written.
    They should take their arguments as normal, but return the value to be said instead of interacting with discord.
    The decorator handles discord interaction.
    
    A 'base' decorator may be passed in. The default is discord.ext.commands.command
    clean=True by default. if True, it cleans discord mentions to plain text. Used with raw conversion."""
    pass_ctx = comargs.get('pass_context', False)
    comargs['pass_context'] = True
    
    def dec(func):
        @wraps(func)
        async def wrapp(*args, **kwargs):
            has_self = not isinstance(args[0], commands.Context)
            ctx = args[1] if has_self else args[0]  # for inside a class where first arg is self
            arglist = [*args]
            if not pass_ctx:
                del arglist[1 if has_self else 0]
            a = tuple(arglist)
            if clean:
                result = await func(*a, **kwargs, text=ctx.invoked_with.join(
                    ctx.message.clean_content.split(ctx.invoked_with)[1:]))
            else:
                result = await func(*a, **kwargs)
            if not ctx.message.channel.is_private:
                await ctx.bot.delete_message(ctx.message)
            await ctx.bot.say('{}: {}'.format(ctx.message.author.mention, result))
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


class SessionCog:
    """Simple class to take care of using a aiohttp session in a cog."""
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    def __unload(self):
        self.bot.loop.create_task(self.session.close())


tokens = open_json('tokens.json')
