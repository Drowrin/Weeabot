from discord.ext import commands
from . import base_cog


def do_not_track(command):
    """
    Decorator to flag a command as not tracked.
    """
    if isinstance(command, (commands.Command, commands.Group)):
        command.callback.tracked = False
    else:
        command.tracked = False
    return command


class Stats(base_cog(shortcut=True)):
    """
    Track usage.
    """

    async def inc_use(self, user, command):
        """
        Increment the usage count of a particular command and user.
        """
        if not command.tracked:
            return

        await self.bot.db.inc_command_usage(user, command.qualified_name)

    async def on_command_completion(self, ctx):
        await self.inc_use(ctx.message.author, ctx.command)


def setup(bot):
    bot.add_cog(Stats(bot))
