import json
import io
import aiohttp
import random
from os import path
from os import listdir
from discord.ext import commands


class CheckMsg(commands.CheckFailure):
    """Exception raised when a check fails and a message should be sent."""
    pass


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


async def download(session: aiohttp.ClientSession, link: str, fn: str):
    """Quick and easy download utility."""
    async with session.get(link) as r:
        val = await r.read()
        with open(fn, "wb") as f:
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
