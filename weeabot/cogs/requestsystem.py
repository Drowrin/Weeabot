import copy
import os

from enum import IntEnum
from textwrap import shorten
from asyncio_extras import threadpool

import discord
from discord.ext import commands


class RequestLimit(commands.CommandError):
    pass


class PermissionLevel(IntEnum):
    NONE, GUILD, GLOBAL = range(3)


def request(bypass=lambda ctx: False, level: PermissionLevel=PermissionLevel.SERVER):

    def decorator(func):
        async def request_predicate(ctx):
            ctx.bypassed = ''

            # Not allowed in PMs.
            if ctx.message.channel.is_private:
                raise commands.NoPrivateMessage()
            # allow permitted users immediately
            if ctx.author == ctx.bot.owner:
                return True
            if level == PermissionLevel.GULID and ctx.author.guild_permissions.manage_guild:
                return True
            # requests cog must be loaded to use requests.
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
            return False

        return commands.check(request_predicate)(func)

    return decorator

# TODO: this will be used later in accept logic
for l in PermissionLevel:
    if level >= l > r.current_level:
        if l == PermissionLevel.GLOBAL:
            ctx.bot.owner.send(
                "New request {}\n```{}```\n{}".format(
                    r.id, ctx.message.content, '\n'.join([a.url for a in ctx.message.attachments])
                )
            )