import aiohttp
import inspect
import traceback
import itertools
from functools import total_ordering
from asyncio_extras import threadpool


def base_cog(shortcut=False, session=False):
    """
    Generate a cog template with certain flags.
    shortcut: Add this cog as an attribute of the bot. The name will be the class name lowercase.
    session: If True will add an aiohttp.ClientSession as self.session.
    """

    class BaseCog:
        """
        Common functionality of cogs.
        """

        profile_fields = {}
        services = {}
        object_hooks = {}
        guild_configs = {}

        @classmethod
        def profile_field(cls, *, name=None, description=None, inline=True, order=0):
            """
            Decorator that adds a profile field function to this cog.
            Should take unpacked data and return a formatted string for the embed field value.
            Name will be taken from the function name if none is given.
            Description will be taken from the docstring if none is given.
            inline controls whether the field will be inline.
            order is a priority where lower is near the top. Can be negative. Defaults to 0
            """

            @total_ordering
            class ProfileField:
                bot = None  # set on cog load

                def __init__(self, f):
                    self.name = name or f.__name__
                    cls.profile_fields[self.name] = self
                    self.callback = f
                    self.description = (description or f.__doc__ or "").strip()
                    self.handler = None
                    self.order_priority = order
                    self.getter = None
                    self.setter = None

                def __eq__(self, other):
                    return self.order_priority == other.order_priority

                def __lt__(self, other):
                    return self.order_priority < other.order_priority

                def error_handler(self, f):
                    """
                    Register the error handler for this formatter.
                    If none and there is an error, field will simply display ERROR.
                    Function should take as parameters the exception followed by the data, returning a result.
                    """
                    self.handler = f

                def set_getter(self, f):
                    """
                    Decorator to override the default get function.
                    Useful if you don't need to get data from a profile field in
                    the db or want to do extra processing on it first.
                    Should take ctx and user and return the data.
                    """
                    self.getter = f

                def set_setter(self, f):
                    """
                    Register the setter function for this formatter.
                    Used to let a user set their own value for the field.
                    Do not register this if the data is generated.
                    The function should be a coroutine that takes a ctx, user, and value(string from user)
                    and returns the data to be stored (will be pickled).
                    If no data should be stored and the function handles everything, or in failure, just return none.
                    """
                    self.setter = f

                async def __call__(self, ctx, user, embed):
                    try:
                        data = await self.get(ctx, user)
                        if data is None:
                            return
                        result = self.callback(data)
                        if inspect.isawaitable(result):
                            result = await result
                    except Exception as e:
                        traceback.print_exc()
                        result = self.handler(e, user) if self.handler else "ERROR"
                    if result is not None:
                        embed.add_field(
                            name=self.name,
                            value=result,
                            inline=inline
                        )

                async def get(self, ctx, user):
                    if self.getter is not None:
                        return await self.getter(ctx, user)
                    async with threadpool(), ctx.bot.db.get_profile_field(user, self.name) as f:
                        return f.value if f is not None else None

                async def status_str(self, ctx, user):
                    return "{}\t:\t{}```{}```".format(
                        self.name,
                        await self.get(ctx, user),
                        self.description
                    )

            return ProfileField

        @classmethod
        def service(cls, name=None):
            """
            Decorator to describe a service offered by this cog. Function should return the description.
            Can be a coroutine.
            Name will be taken from the function name if none is given.
            """

            def dec(func):
                cls.services[name or func.__name__] = func
                return func

            return dec

        @classmethod
        def object_hook(cls, name=None):
            """
            Decorator to add an object hook. These hooks are used to translate between json and objects.
            This function should return an object from json.
            Use the decorator hook.to_json to register the function to transform back to json.
            Name will be taken from the function name if none is given.
            """

            def dec(func):
                class Hook:
                    def __init__(self):
                        self.from_json = func
                        self.json = None

                    def __call__(self, *args, **kwargs):
                        return self.from_json(*args, **kwargs)

                    def to_json(self, f):
                        self.json = f
                        return f

                h = Hook()
                cls.defaults[name or func.__name__] = h
                return h

            return dec

        @classmethod
        def guild_config(cls, name=None, description=None, default=None):
            """
            Decorator to add a guild config.
            This can be a coroutine.
            Should take a context and return the setting to be stored. (will be pickled)
            The Description will be taken from the docstring if none is given.
            Name will be taken from the function name if none is given.
            A default can be given for when there is no value.
            """

            class GuildConfigWrapper:
                bot = None  # set on cog load

                def __init__(self, f):
                    self.name = name or f.__name__
                    self.callback = f
                    cls.guild_configs[self.name] = self
                    self.description = description or f.__doc__.strip()
                    self.default = default
                    self._transform = None

                async def __call__(self, ctx):
                    result = self.callback(ctx)
                    if inspect.isawaitable(result):
                        result = await result
                    return result

                async def status_str(self, guild):
                    return "{}\t:\t{}```{}```".format(
                        self.name,
                        await self.get(guild),
                        self.description
                    )

                def transform(self, f):
                    """
                    Decorator to set the transform function for this config.
                    Called between getting results from the db and returning them.
                    Should be a coroutine.
                    Takes a reference to self and the data. Returns data.
                    """
                    self._transform = f

                async def get(self, guild):
                    c = await self.bot.db.get_guild_config(guild, self.name)
                    result = c.value if c is not None else self.default
                    if self._transform:
                        result = await self._transform(self, result)
                    return result

            return GuildConfigWrapper

        def __init__(self, bot):
            self.bot = bot

            bot.services.update(self.services)
            bot.profile_fields.update(self.profile_fields)
            bot.object_hooks.update(self.object_hooks)
            bot.guild_configs.update(self.guild_configs)

            for o in itertools.chain(self.services.values(), self.guild_configs.values()):
                o.bot = bot

            if shortcut:
                setattr(bot, type(self).__name__.lower(), self)

            if session:
                self.session = aiohttp.ClientSession(loop=bot.loop)

        def __unload(self):
            for k in self.services:
                del self.bot.services[k]
            for k in self.profile_fields:
                del self.bot.profile_fields[k]
            for k in self.object_hooks:
                del self.bot.object_hooks[k]
            for k in self.guild_configs:
                del self.bot.guild_configs[k]

            delattr(self.bot, type(self).__name__.lower())
            if session:
                self.bot.loop.create_task(self.session.close())

    return BaseCog