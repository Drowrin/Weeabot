from discord.ext import commands
from . import augmenter


@augmenter.add(commands.Context)
class Context:
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
        return await m.confirm(user or self.message.author)

    @property
    def argstring(self):
        """
        The unprocessed `argument` portion of the command call.
        """
        return ' '.join(self.message.content.split(self.invoked_with))
