from enum import IntEnum
from asyncio_extras import threadpool

import discord
from discord.ext import commands

from ._base import base_cog
from ..storage.tables import Request
from .stats import do_not_track


class RequestLimit(commands.CommandError):
    pass


class PermissionLevel(IntEnum):
    NONE, GUILD, GLOBAL = range(3)


def request(bypass=lambda ctx: False, level: PermissionLevel = PermissionLevel.GUILD):
    def decorator(func):
        async def request_predicate(ctx):
            ctx.bypassed = ''

            user_level = ctx.bot.requestsystem.get_user_level(ctx.author)

            # Not allowed in PMs.
            if isinstance(ctx.message.channel, (discord.DMChannel, discord.GroupChannel)):
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
            async with threadpool(), ctx.bot.db.get_or_create_request(ctx, level) as r:
                if r.approved:
                    r.delete()
                    return True
            if level >= PermissionLevel.GLOBAL > r.current_level:
                m = ctx.bot.owner.send(
                    "<r{}> | New request ```{}\n{}```}".format(
                        r.message, ctx.message.content, '\n'.join([a.url for a in ctx.message.attachments])

                    )
                )
                async def callback(reaction, user):
                    return await ctx.bot.requestsystem.handle_evaluation(
                        r.message, user,
                        accept={'\N{THUMBS UP SIGN}': True, '\N{THUMBS DOWN SIGN}': False}[reaction.emoji]
                    )
                await m.add_reaction('\N{THUMBS UP SIGN}')
                await m.add_reaction('\N{THUMBS DOWN SIGN}')
                ctx.bot.reactionlisteners.add(
                    m,
                    callback,
                    user=ctx.bot.owner,
                    reactions=('\N{THUMBS UP SIGN}', '\N{THUMBS DOWN SIGN}')
                )
            await ctx.bot.requestsystem.send_status(r)
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

    async def get_message(self, r: Request):
        """
        Get the message that goes with a request.
        """
        return await self.bot.get_channel(r.channel).get_message(r.message)

    async def get_status_message(self, r: Request):
        """
        Get the status message for a request, or None.
        """
        try:
            return await self.bot.get_channel(r.channel).get_message(r.status_message)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

    async def send_status(self, r: Request, rejected=False):
        m = await self.get_message(r)
        if rejected:
            s = f"{m.author.mention} your request {r.message} has been rejected!"
        else:
            s = "{} your request {} has been elevated! Status: {}/{}".format(
                m.author.mention, r.message,
                PermissionLevel(r.current_level).name, PermissionLevel(r.level).name
            )
        sm: discord.Message = await self.get_status_message(r)
        if sm is None:
            sm = await self.bot.get_channel(r.channel).send(s)
            async with self.bot.db.get_request(m.id) as rdb:
                rdb.status_message = sm.id
        else:
            await sm.edit(content=s)

        await sm.add_reaction('\N{THUMBS UP SIGN}')
        await sm.add_reaction('\N{THUMBS DOWN SIGN}')
        self.bot.reactionlisteners.add(
            sm,
            self.reaction_handler,
            user=m.author,
            reactions=('\N{THUMBS UP SIGN}', '\N{THUMBS DOWN SIGN}')
        )

        return sm

    def get_user_level(self, user: discord.User) -> PermissionLevel:
        """
        Get the highest level available to a user based on context.
        """
        if user == self.bot.owner:
            return PermissionLevel.GLOBAL
        try:
            if user.guild_permissions.manage_guild:
                return PermissionLevel.GUILD
        except AttributeError:
            pass
        return PermissionLevel.NONE

    async def attempt_approval(self, mess_id, user: discord.User):
        """
        Evaluate user's top permission level and elevate request if permitted.
        """
        user_level = self.get_user_level(user)
        async with threadpool(), self.bot.db.get_request(mess_id) as req:
            if user_level > req.current_level:
                req.current_level = user_level.value
        await self.bot.process_commands(await self.bot.get_channel(req.channel).get_message(req.message))
        return req.approved  # to destroy the listener if approved

    async def attempt_rejection(self, mess_id, user):
        """
        Evaluate user's top permission level and reject request if above current level.
        """
        user_level = self.get_user_level(user)
        async with threadpool(), self.bot.db.get_request(mess_id) as req:
            if user_level > req.current_level:
                req.delete()
        if user_level > req.current_level:
            await self.send_status(req, rejected=True)
            return True
        return False

    async def reaction_handler(self, reaction, user):
        """
        Callback for handling reactions on status messages.
        """
        mess_id = await self.bot.db.get_request_from_status(reaction.message.id)
        await self.handle_evaluation(
            mess_id, user,
            accept={'\N{THUMBS UP SIGN}': True, '\N{THUMBS DOWN SIGN}': False}[reaction.emoji]
        )

    async def handle_evaluation(self, mess_id, user, accept=True):
        """
        handle evaluation separately because DRY.
        """
        if accept:
            return await self.attempt_approval(mess_id, user)
        else:
            return await self.attempt_rejection(mess_id, user)

    @commands.command()
    @request()
    @do_not_track
    async def req(self, ctx):
        """
        test req feature
        """
        await ctx.send('did the thing')

    @commands.group(aliases=('r',))
    @commands.check(lambda ctx: ctx.bot.requestsystem.get_user_level(ctx.author) > PermissionLevel.NONE)
    @do_not_track
    async def request(self, ctx):
        """
        Request management commands.
        """

    @request.command(aliases=('a', 'approve'))
    @do_not_track
    async def accept(self, ctx, request_id: int):
        """
        Accept a request based on id. Useful if reactions were broken by a bot restart.
        """
        await self.attempt_approval(request_id, ctx.author)

    @request.command(aliases=('r',))
    @do_not_track
    async def reject(self, ctx, request_id: int):
        """
        Reject a request based on it. Useful if reactions were broken by a bot restart.
        """


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
