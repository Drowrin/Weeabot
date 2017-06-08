from discord.ext import commands

from weeabot import utils
from .message import Message


class Context(utils.wrapper(commands.Context)):
    """
    Additional shortcuts and features for commands.Context
    Mostly syntactic sugar
    """

    async def affirmative(self):
        """
        Shortcut to ctx.message.affirmative()
        """
        return await self.message.affirmative()

    async def negative(self):
        """
        Shortcut to ctx.message.negative()
        """
        return await self.message.negative()

    async def confirm(self, *args, user=None, **kwargs):
        """
        Use reactions to get a Yes/No response from the user.

        user is the user to respond only to. Defaults to the author.
        Additional arguments will be passed to self.send
        """
        m = await self.send(*args, **kwargs)
        return await Message(self.bot, m).confirm(user or self.message.author)
