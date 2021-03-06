import json
import io
import aiohttp
import traceback
import itertools
import asyncio
import random
import re
import datetime
from os import path
from os import listdir
from discord.ext import commands
from datetime import timedelta
from collections import defaultdict


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


def cooldown_reset_if(predicate):
    """A check that always passes. Resets the cooldown if the predicate is true.

    Predicate takes ctx."""

    def inner(ctx):
        if predicate(ctx):
            ctx.command.reset_cooldown(ctx)
        return True

    return commands.check(inner)


def down_to_seconds(td: timedelta):
    return timedelta(seconds=td.seconds)


def down_to_minutes(td: timedelta):
    return timedelta(minutes=(td.seconds // 60))


def partition(l, hashf):
    d = defaultdict(list)
    for i in l:
        d[hashf(i)].append(i)
    return list(d.values())


def even_split(l, max_size):
    for i in range(0, len(l), max_size):
        yield list(l)[i:i + max_size]


def remove_leading_space(s):
    s = s.split('\n')
    n = min([sum(1 for _ in itertools.takewhile(str.isspace, l)) for l in s])
    return "\n".join(l[n:] for l in s)


def full_id(message):
    if message.channel.is_private:
        return f'P{message.channel.id}{message.id}'
    else:
        return f'S{message.server.id}{message.channel.id}{message.id}'


class Config:
    def __init__(self, config_path, default=None):
        default = default or {}
        self.path = config_path
        self._db = open_json(config_path)
        write = False
        for n in default:
            if n not in self._db:
                self._db[n] = default[n]
                write = True
        self.__dict__.update(self._db)
        if write:
            self._dump()

    def __getattr__(self, name):
        return self.__dict__.get(name, None)

    def _dump(self):
        for k in self._db:
            self._db[k] = self.__dict__[k]
        with open(self.path, 'w') as f:
            json.dump(self._db, f, ensure_ascii=True, indent=2)

    async def save(self):
        await asyncio.get_event_loop().run_in_executor(None, self._dump)


def safe(call, *exceptions):
    try:
        return call()
    except exceptions:
        return None


def duration(dur: str) -> datetime.timedelta:
    def gettime(s: str, d: str):
        try:
            r = re.search(r"\d[\d.]*\s*{}".format(s), d)
            if r is None:
                return 0
            return int(re.match(r"\d+", r.group()).group())
        except (TypeError, ValueError, AttributeError):
            print(f'Error in utils.duration(). passed strings: {s}:{d}')
            traceback.print_exc()
            return 0

    seconds = gettime('s', dur)
    seconds += gettime('m', dur) * 60
    seconds += gettime('h', dur) * 3600
    seconds += gettime('d', dur) * 86400
    return timedelta(seconds=seconds)


tokens = open_json(path.join('config', 'tokens.json'))
content = Config(path.join('config', 'content.json'), default={
    "icons": {
        "tag": "https://maxcdn.icons8.com/Share/icon/Ecommerce//price_tag1600.png"
    },
    "emoji": ["<3", "(\uff89\u25d5\u30ee\u25d5)\uff89*:\uff65\uff9f\u2727", "(\u261e\uff9f\u30ee\uff9f)\u261e"],
    "statuses": ["dramatic posing", "with myself"],
    "memes": {},
    "overlays": {},
    "attack": {
        "self": ["me", "myself", "my"],
        "esc": ["{} managed to escape!", "{} is a slippery bastard.", "{} was really a clone!",
                "It reflected off of {}!", "{} blocked!"],
        "el": ["ELIMINATED {}", "Bopped {}", "{} was removed from existence.", "{} is sleeping with fishes.",
               "{} is 'life challenged'"],
        "miss": ["Someday you'll hit something...", "Stop wasting ammo.", "Baka",
                 "*You shoot at the sky\nYou attempt a badass pose\nTo mask your missed shot*"],
        "kys": ["{} played themself.", "{} spread their brain on the wall.", "{} ended it all.", "{} embraced sdeath"],
        "immune": ["{0} attempted to bop {1} but they were too powerful!", "{1} laughs at {0}'s feeble attempt.",
                   "{1} doesn't even flinch, but glares at {0}."]
    },
    "tag_responses": {
        "sdeath": ["sdeath"],
        "disapproval": ["daddy"],
        "nobully": ["no bully", "don't bully", "not bully"],
        "bully": ["bully"]
    }
})
