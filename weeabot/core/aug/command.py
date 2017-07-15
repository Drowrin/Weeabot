from discord.ext import commands
from . import augmenter


@augmenter.add(commands.Command)
class Command:
    """
    Added functionality to commands.Command
    """

    @property
    def tracked(self):
        """
        True if this command's usage is tracked.
        """
        return getattr(self.callback, 'tracked', True)
