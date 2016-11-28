import discord
from discord.ext import commands
from utils import *


def owner(ctx):
    return ctx.message.author == ctx.bot.owner


def trusted(ctx):
    return owner(ctx) or False  # add here when trusted code is in


def notprivate(ctx):
    return not ctx.message.channel.is_private


def server_owner(ctx):
    return notprivate(ctx) and (trusted(ctx) or ctx.message.server.owner == ctx.message.author)


def moderator(ctx):
    return notprivate(ctx) and (server_owner(ctx) or False)  # add here when moderator code is in.


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

