import json
import asyncio
from os import path, makedirs


def wrapper(cls):
    """
    Add functionality and attributes to an instantiated object even with __slots__.
    """
    class Wrapper(cls):
        __slots__ = ('__internal', '__client')

        def __init__(self, client, internal):
            self.__internal = internal
            self.__client = client

        def __getattr__(self, item):
            if item == f'_{cls.__name__}__client':
                return self.__client
            return getattr(self.__internal, item)
    return Wrapper


def open_json(fn: str):
    """Open a json file and handle the errors."""
    makedirs(path.dirname(fn), exist_ok=True)
    try:
        with open(fn) as f:
            return json.load(f)
    except FileNotFoundError:
        with open(fn, 'w') as f:
            json.dump({}, f)
            return {}


def full_id(message):
    return f'P{message.channel.id}{message.id}'


class Config:
    def __init__(self, config_path, default=None):
        default = default or {}
        self.__dict__['_path'] = config_path
        self.__dict__['_db'] = open_json(config_path)
        write = False
        for n in default:
            if n not in self._db:
                self._db[n] = default[n]
                write = True
        if write:
            self._dump()

    def __getattr__(self, name):
        if name == '_db':
            return self.__dict__['_db']
        if name == '_path':
            return self.__dict__['_path']
        return self._db.get(name, None)

    def __setattr__(self, key, value):
        if key in ['_path', '_db']:
            self.__dict__[key] = value
        else:
            self._db[key] = value

    def _dump(self):
        with open(self._path, 'w') as f:
            json.dump(self._db, f, ensure_ascii=True, indent=2)

    async def save(self):
        await asyncio.get_event_loop().run_in_executor(None, self._dump)


def full_command_name(command):
    """Return the 'full' command name.

    This is, essentially, the beginning of the message that called the command.
    However, base command names are used, not aliases.

    Separated by spaces, just as the command was called."""
    names = [command.name]
    while command.parent:
        command = command.parent
        names.insert(0, command.name)
    return ' '.join(names)


class Storage:
    def __init__(self, *storage_path):
        self.__dict__['path'] = path.join(*storage_path)
        self.__dict__['_db'] = open_json(self.path)

    def __getitem__(self, item):
        if item not in self._db:
            self._db[item] = {}
        return self._db

    def __setitem__(self, key, value):
        self._db[key] = value

    def _dump(self):
        with open(self.path, 'w') as f:
            json.dump(self._db, f, ensure_ascii=True, indent=2)

    async def save(self):
        await asyncio.get_event_loop().run_in_executor(None, self._dump)


tokens = Config(path.join('config', 'tokens.json'), default={
    "imgur_token": "",
    "imgur_secret": "",
    "discord_token": "",
    "discord_ClientID": "",
    "twitch_id": "",
    "twitch_secret": "",
    "twitter": {
        "consumer_key": "",
        "consumer_secret": "",
        "access_token_key": "",
        "access_token_secret": ""
    },
    "anilist_id": "",
    "anilist_secret": "",
    "cleverbot_api_key": ""
})
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
