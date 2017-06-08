import asyncio

from weeabot import utils
from . import base_cog


class ReactionListeners(base_cog(shortcut=True)):
    """
    Listen to reactions on messages and invoke callbacks.
    """

    def __init__(self, bot):
        super(ReactionListeners, self).__init__(bot)
        self.listeners = {}

    def add(self, msg, callback):
        """
        add a listener to perform an action when a reaction is done on a given message.

        Callback should be a coroutine, with the same args as on_reaction_add(reaction, user).
        Does not persist through restarts.
        """
        self.listeners[utils.full_id(msg)] = callback

    async def on_reaction_add(self, reaction, user):
        m = reaction.message
        callback = self.listeners.pop(utils.full_id(m), asyncio.coroutine(lambda *args: None))
        await callback(reaction, user)


def setup(bot):
    bot.add_cog(ReactionListeners(bot))
