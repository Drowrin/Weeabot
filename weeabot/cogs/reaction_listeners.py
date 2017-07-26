from . import base_cog


class ReactionListener:
    def __init__(self, message, callback, single_use=True, user=None, reactions=None):
        self.message = message
        self.callback = callback
        self.single_use = single_use
        self.user = user
        self.reactions = reactions

    async def __call__(self, reaction, user):
        r = await self.callback(reaction, user)
        self.single_use = bool(r) if r is not None else self.single_use

    def check(self, reaction, user):
        if self.user is not None:
            if user != self.user:
                return False
        if self.reactions is not None:
            if reaction.emoji not in self.reactions:
                return False
        if reaction.message == self.message:
            return True
        return False


class ReactionListeners(base_cog(shortcut=True)):
    """
    Listen to reactions on messages and invoke callbacks.
    """

    def __init__(self, bot):
        super(ReactionListeners, self).__init__(bot)
        self.listeners = {}

    def add(self, message, callback):
        """
        add a listener to perform an action when a reaction is done on a given message.

        Callback should be a coroutine, with the same args as on_reaction_add(reaction, user).
        Return, if any, is used as bool to determine if this listener should stay.
        Does not persist through restarts.
        """

        self.listeners[message.id] = ReactionListener(message, callback)

    async def on_reaction_add(self, reaction, user):
        m = reaction.message
        callback = self.listeners.get(m.id)
        if callback is not None and callback.check(reaction, user):
            await callback(reaction, user)
            if callback.delete_after:
                try:
                    del self.listeners[m.id]
                except KeyError:
                    # can happen when multiple reactions happen quickly
                    pass


def setup(bot):
    bot.add_cog(ReactionListeners(bot))
