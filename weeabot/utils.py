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
