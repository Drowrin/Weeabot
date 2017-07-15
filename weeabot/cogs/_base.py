import aiohttp

from ..core import Weeabot

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

        @classmethod
        def formatter(cls, name=None):
            """
            Decorator that adds a formatter function to this cog.
            Can be a coroutine.
            Name will be taken from the function name if none is given.
            """

            def dec(func):
                cls.formatters[name or func.__name__] = func
                return func

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

        def __init__(self, bot: Weeabot):
            self.bot = bot

            bot.services.update(self.services)
            bot.defaults.update(self.defaults)
            bot.formatters.update(self.formatters)
            bot.verbose_formatters.update(self.verbose_formatters)
            bot.object_hooks.update(self.object_hooks)

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

            delattr(self.bot, type(self).__name__.lower())
            self.bot.loop.create_task(self.session.close())

    return BaseCog
