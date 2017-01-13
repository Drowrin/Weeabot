from discord.ext import commands
from utils import CheckMsg


def owner(ctx):
    return ctx.message.author == ctx.bot.owner


def trusted(ctx):
    return owner(ctx) or ctx.message.author.id in ctx.bot.trusted


def notprivate(ctx):
    return not ctx.message.channel.is_private


def server_owner(ctx):
    return notprivate(ctx) and (trusted(ctx) or ctx.message.server.owner == ctx.message.author)


def moderator(ctx):
    return notprivate(ctx) and (server_owner(ctx) or ctx.bot.server_configs[ctx.message.server.id].get('moderator_role', None) in [r.id for r in ctx.message.author.roles])


def is_owner():
    """Decorator to allow a command to run only if it is called by the owner."""
    return commands.check(owner)


def is_trusted():
    """Decorator to check for trusted users or higher."""
    return commands.check(trusted)


def is_server_owner():
    """Decorator to allow a command to run only if called by the server owner or higher"""
    return commands.check(server_owner)


def is_moderator():
    """Allows only moderators or higher."""
    return commands.check(moderator)


def is_channel(name: str):
    """Decorator to allow a command to run only if it is in a specified channel (by name)."""

    def _is_channel(ctx):
        try:
            ch = commands.ChannelConverter(ctx, name).convert()
        except commands.BadArgument:
            raise commands.CheckFailure(f'Only allowed in a channel called {name}.')
        if ctx.message.channel.id != ch.id:
            raise commands.CheckFailure(f'Only allowed in {ch.mention}.')
        return True

    return commands.check(_is_channel)


def testing(ctx):
    if ctx.message.channel.is_private:
        if ctx.message.author.id == ctx.bot.owner.id:
            return True
        return False
    if ctx.message.server.id in ctx.bot.config.testing_servers:
        return True
    if ctx.message.channel.id in ctx.bot.config.testing_channels:
        return True
    return False


def is_testing():
    """Only allowed in 'safe' environments.

    Servers and channels approved by the bot owner, or in PMs by the bot owner.

    Intended for testing new features before making them more public."""
    return commands.check(testing)


def profiles():
    """Make sure the command only runs if the profiles cog is loaded."""
    return commands.check(lambda ctx: ctx.bot.profiles is not None)


def tools():
    """Make sure the command only runs if the tools cog is loaded."""
    return commands.check(lambda ctx: ctx.bot.tools is not None)


def has_tag(tag: str):
    """Check if the channel has a specific [tag] in its description.

    Used for restricting certain commands or types of commands to certain channels."""

    def predicate(ctx):
        if ctx.message.channel.topic is None or f'[{tag}]' not in ctx.message.channel.topic:
            raise CheckMsg(f"This command can only be used in a [{tag}] channel.")
        return True

    return commands.check(predicate)
