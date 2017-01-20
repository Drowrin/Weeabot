import copy
import pickle

import typing

from enum import Enum

import discord
from discord.ext import commands

import utils
import checks

from discord.ext.commands.bot import _get_variable


class PermissionInfo:
    def __init__(self, ch: typing.List[str], tar: typing.Callable[[commands.Context], str]):
        self.checks = ch
        self.target = tar

    def requests(self, ctx):
        return ctx.bot.requestsystem.get_serv(self.target(ctx))

    def add_request(self, ctx):
        ctx.bot.loop.create_task(
            ctx.bot.requestsystem.add_request(ctx.message, self.target(ctx), ctx.delete_source)
        )


class PermissionLevel(Enum):
    BOT = PermissionInfo(
        ['owner', 'trusted'],
        lambda _: 'owner'
    )
    SERVER = PermissionInfo(
        ['server_owner', 'moderator'],
        lambda ctx: ctx.message.server.id
    )

    @classmethod
    def from_check(cls, ch: typing.Callable):
        """Get the appropriate PermissionLevel member based on the passed check."""
        for level in cls:
            if ch.__name__ in level.value.checks:
                return level


def request(bypasses=list(), bypasser=any, delete_source=True):

    def would_pass(ch: typing.Callable[[commands.Context], bool], ctx: commands.Context, a: discord.Member) -> bool:
        if a is None:
            return False
        c = copy.copy(ctx)
        c.message = copy.copy(ctx.message)
        c.message.author = a
        return ch(c)

    def decorator(func):

        # default checks
        req_checks = [checks.trusted, checks.moderator]

        # get checks below this decorator
        if isinstance(func, commands.Command):
            req_checks = [f for f in func.checks if f in checks.who]
            func.checks = [f for f in func.checks if f not in checks.who]
        else:
            if hasattr(func, '__commands_checks__'):
                req_checks = [f for f in func.__commands_checks__ if f in checks.who]
                func.__commands_checks__ = [f for f in func.__commands_checks__ if f not in checks.who]

        # reorder checks to permission order
        req_checks.sort(key=checks.who.index)

        def request_predicate(ctx):
            ctx.bypassed = ''
            ctx.delete_source = delete_source
            approver = _get_variable('_internal_approver')

            # Not allowed in PMs.
            if ctx.message.channel.is_private:
                raise commands.NoPrivateMessage()
            # requests cog must be loaded to use requests.
            if ctx.bot.requestsystem is None:
                return False
            # requests must be enabled on the server.
            if request_channel(ctx.bot, ctx.message.channel.server) is None:
                return False
            # Always pass on help so it shows up in the list.
            if ctx.command.name == 'help':
                return True
            # bypass predicates
            if bypasser(bypass(ctx) for bypass in bypasses):
                ctx.bypassed = True
                return True

            # check the predicates added by decorators
            for i, c in enumerate(req_checks):
                level = PermissionLevel.from_check(c)

                # check if was it bypassed by author having required permissions
                if c(ctx):
                    ctx.bypassed = level.name

                wp = would_pass(c, ctx, approver)

                if (ctx.bypassed or wp) and i == 0:   # top level permission needed, request goes through
                    return True

                # check for elevation at this level
                if wp and ctx.message in level.value.requests(ctx) or ctx.bypassed:
                    # elevate to next position.
                    nc = req_checks[i - 1]
                    nlevel = PermissionLevel.from_check(nc)
                    nlevel.value.add_request(ctx)
                    return False

            # Otherwise, this is a fresh request, add it to the lowest level
            level = PermissionLevel.from_check(req_checks[-1])
            level.value.add_request(ctx)
            return False

        if isinstance(func, commands.Command):
            func.checks.append(request_predicate)
        else:
            if not hasattr(func, '__commands_checks__'):
                func.__commands_checks__ = []

            func.__commands_checks__.insert(0, request_predicate)

        return func

    return decorator


def request_channel(bot, server: discord.Server):
    try:
        return server.get_channel(bot.server_configs.get(server.id, {}).get('request_channel', None))
    except AttributeError:
        return None


def parse_indexes(indexes: str = None):
    if not indexes:
        return [0]
    indexes = indexes.split()
    out = []
    for i in indexes:
        if len(i.split('-')) == 2:
            spl = i.split('-')
            out = out + list(range(int(spl[0]), int(spl[1]) + 1))
        else:
            out.append(int(i))
    return out


class RequestSystem:
    """Request system."""

    user_limit = 5
    server_limit = 30
    global_limit = 100

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.path = 'requests.pkl'
        try:
            with open(self.path, 'rb') as f:
                self.requests = pickle.load(f)
            if len(self.requests) == 0:
                self.requests = {"owner": []}
        except FileNotFoundError:
            self.requests = {"owner": []}
        self._dump()

    def _dump(self):
        with open(self.path, 'wb') as f:
            pickle.dump(self.requests, f, -1)

    async def save(self):
        """Save the current data to disk."""
        await self.bot.loop.run_in_executor(None, self._dump)

    def all_req(self):
        r = []
        for serv in self.requests:
            for m in self.requests[serv]:
                r.append(m)
        return r

    def get_serv(self, server):
        if server not in self.requests:
            self.requests[server] = []
        return self.requests[server]

    def remove_from_serv(self, server, rs):
        self.requests[server] = [r for r in self.requests[server] if r.id not in [rm.id for rm in rs]]

    @commands.command(pass_context=True, no_pm=True)
    @checks.is_server_owner()
    async def enable_requests(self, ctx):
        """Enable requests in this server."""
        if not await self.bot.confirm(
            "This will enable the requests system in this server. Several new features will become available.\n"
            "These are features that would generally be limited to moderater/admin/bot-owner control.\n"
            "However, with this system, normal members can 'request' these commands, and those with proper privelege\n"
            "can simply approve/deny it without having to re-run the command themselves.\n"
            "\n"
            "This will create a new channel, where requests will be sent.\n"
            "Anyone you give access to this channel will be able to approve requests.\n"
            "\n"
            "Are you sure you want to enable this?\n"
            "It can be disabled at any time with command disable_requests.\n"
        ):
            await self.bot.say("Cancelled.")
            return
        e_overwrite = discord.PermissionOverwrite(read_messages=False)
        e_perms = discord.ChannelPermissions(target=ctx.message.server.default_role, overwrite=e_overwrite)
        c = await self.bot.create_channel(ctx.message.server, 'requests', e_perms)
        self.bot.server_configs.get(ctx.message.server.id, {})['request_channel'] = c.id
        self.bot.dump_server_configs()

    @commands.command(pass_context=True, no_pm=True)
    @checks.is_server_owner()
    @commands.check(lambda ctx: request_channel(ctx.bot, ctx.message.server) is not None)
    async def disable_requests(self, ctx):
        """Disable all requests in this server.

        This will leave behind the old channel as a record. delete it or rename it before re-enabling requests."""
        self.bot.server_configs.get(ctx.message.server.id, {})['request_channel'] = None
        self.bot.dump_server_configs()

    async def send_req_msg(self, server, msg: discord.Message, ind, *, dest=None):
        dest = dest or request_channel(self.bot, self.bot.get_server(server)) or self.bot.owner
        e = discord.Embed(
            title="Index: {}".format(ind),
            description=msg.content,
            colour=msg.author.colour,
            timestamp=msg.timestamp
        )
        url = discord.Embed.Empty
        if len(msg.attachments) == 1:
            url = msg.attachments[0]['url']
            e.set_image(url=url)
        e.set_author(
            name=msg.author.display_name,
            icon_url=msg.author.default_avatar_url if not msg.author.avatar else msg.author.avatar_url,
            url=url
        )
        if server == 'owner':
            if msg.channel.is_private:
                source = "PM"
            else:
                source = "{}: {}".format(msg.server.name, msg.channel.name)
            e.add_field(name="Source", value=source)
        return await self.bot.send_message(dest, content="New request added!", embed=e)

    async def add_request(self, mes: discord.Message, server, delete_source):
        if len(list(filter(lambda e: e.author.id == mes.author.id, self.all_req()))) >= self.user_limit:
            await self.bot.send_message(mes.channel, "{}, user request limit reached ({}).".format(mes.author.display_name, self.user_limit))
            return
        if len(list(filter(lambda e: e.server.id == mes.server.id, self.all_req()))) >= self.server_limit:
            await self.bot.send_message(mes.channel, "{}, server request limit reached ({}).".format(mes.server.name, self.server_limit))
            return
        if len(self.all_req()) >= self.global_limit:
            await self.bot.send_message(mes.channel, "Global request limit reached ({}).".format(self.global_limit))
            return

        # rehost images on imgur, since we will be deleting the original image
        if len(mes.attachments) == 1:
            url = mes.attachments[0]['url']
            im = self.bot.imgur.upload_image(url=url)
            mes.attachments[0]['url'] = im.link

        ind = len(self.get_serv(server))
        await self.send_req_msg(server, mes, ind)
        if server != 'owner' or mes.server.owner.id == mes.author.id:
            await self.send_req_msg(server, mes, ind, dest=mes.channel)
        self.get_serv(server).append(mes)
        await self.save()
        if delete_source:
            try:
                await self.bot.delete_message(mes)
            except discord.NotFound:
                pass

    @commands.group(name='request', aliases=('req', 'r'))
    async def req(self):
        """Request based commands."""

    @req.group(pass_context=True, aliases=('l',), invoke_without_command=True, no_pm=True)
    @checks.is_server_owner()
    async def list(self, ctx):
        """Display current requests."""
        for ind, r in enumerate(self.get_serv(ctx.message.server.id)):
            await self.send_req_msg(ctx.message.server.id, r, ind, dest=ctx.message.channel)

    @list.command(aliases=('g',), pass_context=True)
    @checks.is_owner()
    async def glob_list(self, ctx):
        for ind, r in self.get_serv('owner'):
            await self.send_req_msg('owner', r, ind, dest=ctx.message.channel)

    @req.group(pass_context=True, aliases=('a', 'approve'), invoke_without_command=True)
    @checks.is_server_owner()
    async def accept(self, ctx, *, indexes: str="0"):
        """Accept requests made by users."""
        _internal_approver = ctx.message.author
        try:
            indexes = parse_indexes(indexes)
        except ValueError:
            await self.bot.say("invalid index format")
            return
        rs = []
        for i in indexes:
            try:
                rs.append(self.get_serv(ctx.message.server.id)[i])
            except IndexError:
                await self.bot.say("{} out of range.".format(i))
        for r in rs:
            await self.bot.process_commands(r)
        self.remove_from_serv(ctx.message.server.id, rs)
        await self.save()

    @accept.group(aliases=('g',), pass_context=True)
    @checks.is_owner()
    async def glob_accept(self, ctx, *, indexes: str="0"):
        _internal_approver = ctx.message.author
        try:
            indexes = parse_indexes(indexes)
        except ValueError:
            await self.bot.say("invalid index format")
            return
        rs = []
        for i in indexes:
            try:
                rs.append(self.get_serv('owner')[i])
            except IndexError:
                await self.bot.say("{} out of range.".format(i))
        for r in rs:
            await self.bot.process_commands(r)
        self.remove_from_serv('owner', rs)
        await self.save()

    async def reject_requests(self, server, indexes: [int]):
        rs = []
        for i in indexes:
            try:
                rs.append(self.get_serv(server)[i])
            except IndexError:
                await self.bot.say('{} is out of range.'.format(i))
        for r in rs:
            await self.bot.send_message(r.channel, '{0.author}, Your request was denied.'.format(r))
        self.remove_from_serv(server, rs)
        await self.save()

    @req.group(pass_context=True, aliases=('r', 'deny', 'd'), invoke_without_command=True)
    @checks.is_server_owner()
    async def reject(self, ctx, *, indexes: str=None):
        """Reject requests made by users."""
        serv = ctx.message.server
        try:
            indexes = parse_indexes(indexes)
        except ValueError:
            await self.bot.say("invalid index format")
            return
        await self.reject_requests(serv.id, indexes)

    @reject.command(aliases=('g',))
    @checks.is_owner()
    async def glob_reject(self, *, indexes: str=None):
        try:
            indexes = parse_indexes(indexes)
        except ValueError:
            await self.bot.say("invalid index format")
            return
        await self.reject_requests('owner', indexes)

    @req.group(pass_context=True, aliases=('c',), invoke_without_command=True)
    @checks.is_server_owner()
    async def clear(self, ctx):
        """Clear remaining requests."""
        serv = ctx.message.server
        await self.reject_requests(serv.id, list(range(len(self.get_serv(serv.id)))))

    @clear.command(aliases=('g',))
    @checks.is_owner()
    async def glob_clear(self):
        await self.reject_requests('owner', list(range(len(self.get_serv('owner')))))


def setup(bot):
    bot.add_cog(RequestSystem(bot))
