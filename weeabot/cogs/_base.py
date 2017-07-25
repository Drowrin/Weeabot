import aiohttp
import inspect
import traceback
from functools import total_ordering
from discord import Embed


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

        formatters = {}
        verbose_formatters = {}
        services = {}
        defaults = {}
        object_hooks = {}
        guild_configs = {}

        @classmethod
        def formatter(cls, *, name=None, inline=True, order=0):
            """
            Decorator that adds a formatter function to this cog.
            The function should take user data from the db and return field contents.
            Optionally a coroutine.
            Name will be taken from the function name if none is given.
            inline controls whether the field will be inline.
            order is a priority where lower is near the top. Can be negative. Defaults to 0
            """

            def dec(func):
                @total_ordering
                class ProfileFormatter:
                    order_priority = order
                    handler = None

                    def __eq__(self, other):
                        return self.order_priority == other.order_priority

                    def __lt__(self, other):
                        return self.order_priority < other.order_priority

                    def __init__(self, user):
                        self.user = user

                    async def __call__(self, embed: Embed):
                        try:
                            result = func(self.user)
                            if inspect.isawaitable(result):
                                result = await result
                        except Exception as e:
                            traceback.print_exc()
                            result = self.handler(e, self.user) if self.handler else "ERROR"
                        embed.add_field(
                            name=name,
                            value=result,
                            inline=inline
                        )

                    def error_handler(self, f):
                        """
                        Register the error handler for this formatter.
                        If none and there is an error, field will simply display ERROR.
                        Function should take as parameters the exception followed by the data, returning a result.
                        """
                        self.handler = f

                cls.formatters[name or func.__name__] = ProfileFormatter
                return ProfileFormatter

            return dec

        @classmethod
        def verbose_formatter(cls, name=None):
            """
            Decorator that adds a verbose formatter function to this cog.
            Can be a coroutine.
            Name will be taken from the function name if none is given.
            """

            def dec(func):
                cls.verbose_formatters[name or func.__name__] = func
                return func

            return dec

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
        def default(cls, name=None):
            """
            Decorator to add a default profile field. Function should return the default value.
            Can be a coroutine.
            Name will be taken from the function name if none is given.
            """

            def dec(func):
                cls.defaults[name or func.__name__] = func
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
                def __init__(self, f):
                    self.name = name or f.__name__
                    self.callback = f
                    cls.guild_configs[self.name] = self
                    self.description = description or f.__doc__
                    self.default = default

                async def __call__(self, ctx):
                    result = self.callback(ctx)
                    if inspect.isawaitable(result):
                        result = await result
                    return result

                async def status_str(self, ctx):
                    return "{}\t:\t{}\t:\t{}".format(
                        self.name,
                        self.description.strip(),
                        await self.get(ctx)
                    )

                async def get(self, ctx):
                    c = await ctx.bot.db.get_guild_config(ctx.guild, self.name)
                    return c.value if c is not None else self.default

            return GuildConfigWrapper

        def __init__(self, bot):
            self.bot = bot

            bot.services.update(self.services)
            bot.defaults.update(self.defaults)
            bot.formatters.update(self.formatters)
            bot.verbose_formatters.update(self.verbose_formatters)
            bot.object_hooks.update(self.object_hooks)
            bot.guild_configs.update(self.guild_configs)

            if shortcut:
                setattr(bot, type(self).__name__.lower(), self)

            if session:
                self.session = aiohttp.ClientSession(loop=bot.loop)

        def __unload(self):
            for k in self.services:
                del self.bot.services[k]
            for k in self.defaults:
                del self.bot.defaults[k]
            for k in self.formatters:
                del self.bot.formatters[k]
            for k in self.verbose_formatters:
                del self.bot.verbose_formatters[k]
            for k in self.object_hooks:
                del self.bot.object_hooks[k]
            for k in self.guild_configs:
                del self.bot.guild_configs[k]

            delattr(self.bot, type(self).__name__.lower())
            self.bot.loop.create_task(self.session.close())

    return BaseCog
