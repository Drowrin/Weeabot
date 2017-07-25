import copy
import os

from enum import IntEnum
from textwrap import shorten
from asyncio_extras import threadpool

import discord
from discord.ext import commands

from ._base import base_cog


class RequestLimit(commands.CommandError):
    pass


class PermissionLevel(IntEnum):
    NONE, GUILD, GLOBAL = range(3)


def get_user_level(ctx: commands.Context) -> PermissionLevel:
    """
    Get the highest level available to a user based on context.
    """
    if ctx.author == ctx.bot.owner:
        return PermissionLevel.GLOBAL
    if ctx.author.guild_permissions.manage_guild:
        return PermissionLevel.GUILD
    return PermissionLevel.NONE


def request(bypass=lambda ctx: False, level: PermissionLevel=PermissionLevel.GUILD):

    def decorator(func):
        async def request_predicate(ctx):
            ctx.bypassed = ''

            user_level = get_user_level(ctx)

            # Not allowed in PMs.
            if ctx.message.channel.is_private:
                raise commands.NoPrivateMessage()
            # allow permitted users immediately regardless
            if level == user_level:
                return True
            # requests cog must be loaded to elevate non-permitted users
            if ctx.bot.requestsystem is None:
                return False
            # Always pass on help so it shows up in the list.
            if ctx.command.name == 'help':
                return True
            # bypass predicates
            if bypass(ctx):
                ctx.bypassed = True
                return True

            # handle request elevation/resolution
            r = await ctx.bot.db.get_request(ctx.message.id)
            if r is None:  # new request. Add to low level
                r = await ctx.bot.db.create_request(ctx, level)
                await r.send_status()
            else:  # request exists
                if r.approved:
                    await r.send_status()
                    await ctx.bot.db.delete_request(r)
                    return True
                for l in PermissionLevel:
                    if level >= l > r.current_level:
                        if l == PermissionLevel.GLOBAL:
                            ctx.bot.owner.send(
                                "New request {}\n```{}```\n{}".format(
                                    r.id, ctx.message.content, '\n'.join([a.url for a in ctx.message.attachments])
                                )
                            )
            return False

        return commands.check(request_predicate)(func)

    return decorator


class RequestSystem(base_cog(shortcut=True)):
    """
    Handles elevating requests of un-permitted users to permitted users.
    """

    user_limit = 5
    server_limit = 30
    global_limit = 100


@RequestSystem.guild_config(default=False)
async def requests(ctx):
    """
    Turn the request system on or off
    """
    current = await ctx.bot.guild_configs['requests'].get(ctx)
    v = ctx.kwargs.get('value')
    if v:
        try:
            return {'on': True, 'off': False}[v.lower()]
        except KeyError:
            raise commands.BadArgument(f'invalid value: `{v}`')
    return not current


def setup(bot):
    bot.add_cog(RequestSystem(bot))
