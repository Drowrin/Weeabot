import copy
import pickle

import typing

from enum import Enum

import discord
from discord.ext import commands

import utils
import checks

from discord.ext.commands.bot import _get_variable


class RequestLimit(commands.CommandError):
    pass


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
    try:
        for i in indexes:
            if len(i.split('-')) == 2:
                spl = i.split('-')
                out = out + list(range(int(spl[0]), int(spl[1]) + 1))
            else:
                out.append(int(i))
    except ValueError:
        raise commands.BadArgument("invalid index format")
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
        self.requests[server] = [r for r in self.requests[server] if r not in rs]

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

    def get_ind(self, server, mes):
        """get the index of a message in a server."""
        try:
            return self.get_serv(server).index(mes)
        except ValueError:
            return None

    async def send_req_msg(self, server, msg: discord.Message, ind, *, dest=None, new=False):
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
        if dest == self.bot.owner or isinstance(dest, discord.PrivateChannel):
            if msg.channel.is_private:
                source = "PM"
            else:
                source = "{}: {}".format(msg.server.name, msg.channel.name)
            e.add_field(name="Source", value=source)
        ret = await self.bot.send_message(dest, content="New request added!" if new else None, embed=e)

        # accept/reject buttons
        pos, neg = ['👍', '👎']
        async def callback(reaction, user):
            if user == self.bot.owner or self.bot.user_is_moderator(user):
                s = 'owner' if reaction.message.channel.is_private else reaction.message.server.id
                if reaction.emoji == pos:
                    await self.accept_requests(user, s, self.get_ind(s, msg))
                    return
                elif reaction.emoji == neg:
                    await self.reject_requests(s, [self.get_ind(s, msg)])
                    return
            self.bot.add_react_listener(ret, callback)
        await self.bot.add_reaction(ret, pos)
        await self.bot.add_reaction(ret, neg)
        self.bot.add_react_listener(ret, callback)

        return ret

    async def add_request(self, mes: discord.Message, server, delete_source):
        if mes in self.get_serv(server):
            # if the message is already in the specified server's list, no reason to re-add it
            return

        if len(list(filter(lambda e: e.author.id == mes.author.id, self.all_req()))) >= self.user_limit:
            raise RequestLimit("{}, user request limit reached ({}).".format(mes.author.display_name, self.user_limit))
        if len(list(filter(lambda e: e.server.id == mes.server.id, self.all_req()))) >= self.server_limit:
            raise RequestLimit("{}, server request limit reached ({}).".format(mes.server.name, self.server_limit))
        if len(self.all_req()) >= self.global_limit:
            raise RequestLimit("Global request limit reached ({}).".format(self.global_limit))

        # rehost images on imgur, since we will be deleting the original image
        if len(mes.attachments) == 1:
            url = mes.attachments[0]['url']
            im = self.bot.imgur.upload_image(url=url)
            mes.attachments[0]['url'] = im.link

        # add the request to the specified server's list
        ind = len(self.get_serv(server))
        await self.send_req_msg(server, mes, ind, new=True)
        if server != 'owner' or mes.server.owner.id == mes.author.id:
            await self.send_req_msg(server, mes, ind, dest=mes.channel, new=True)
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

    @req.command(pass_context=True, aliases=('l',))
    @commands.check(lambda ctx: checks.owner(ctx) or checks.moderator(ctx))
    async def list(self, ctx):
        """Display current requests."""
        server = 'owner' if ctx.message.channel.is_private else ctx.message.server.id
        reqs = self.get_serv(server)
        if len(reqs) == 0:
            await self.bot.say("None.")
            return
        for ind, r in enumerate(reqs):
            await self.send_req_msg(server, r, ind, dest=ctx.message.channel)

    async def send_req_status(self, rs, stat):
        # sort messages by channel and author
        for r_list in utils.partition(rs, lambda i: i.author.id + i.channel.id):
            s = r_list[0]
            l = '\n'.join([r.clean_content for r in r_list])
            await self.bot.send_message(s.channel, embed=discord.Embed(
                title=f'These requests were {stat}',
                description=f'```{l}```'
            ).set_author(
                name=s.author.display_name,
                icon_url=s.author.avatar_url or s.author.default_avatar_url
            ))

    async def accept_requests(self, approver, server, *indexes):
        _internal_approver = approver

        rs = self.get_serv(server)

        oor = [i for i in indexes if not 0 <= i < len(rs)]
        if oor:
            await self.bot.say(utils.str_limit(f'Out of range: {oor}', 2000))

        await self.send_req_status(rs, f'approved by {_internal_approver.mention}')

        for r in rs:
            await self.bot.process_commands(r)
        self.remove_from_serv(server, rs)
        await self.save()

    @req.command(pass_context=True, aliases=('a', 'approve'))
    @commands.check(lambda ctx: checks.owner(ctx) or checks.moderator(ctx))
    async def accept(self, ctx, *, indexes: str="0"):
        """Accept requests made by users.

        Request 0 is chosen if no index is passed.

        Separate indexes by spaces. To express a range of indexes, put a dash between them.
        \"0 3-6 8\" for example would be the indexes 0, 3, 4, 5, 6, and 8.

        Be aware that after this command, indexes on unaffected requests will be changed."""
        indexes = parse_indexes(indexes)

        server = 'owner' if ctx.message.channel.is_private else ctx.message.server.id

        await self.accept_requests(ctx.message.author, server, *indexes)

    async def reject_requests(self, server, indexes: [int]):
        rs = self.get_serv(server)
        oor = [i for i in indexes if not 0 <= i < len(rs)]
        if oor:
            await self.bot.say(utils.str_limit(f'Out of range: {oor}', 2000))

        await self.send_req_status(rs, 'denied')

        self.remove_from_serv(server, rs)
        await self.save()

    @req.command(pass_context=True, aliases=('r', 'deny', 'd'))
    @commands.check(lambda ctx: checks.owner(ctx) or checks.moderator(ctx))
    async def reject(self, ctx, *, indexes: str=None):
        """Reject requests made by users.

        Request 0 is chosen if no index is passed.

        Separate indexes by spaces. To express a range of indexes, put a dash between them.
        \"0 3-6 8\" for example would be the indexes 0, 3, 4, 5, 6, and 8.

        Be aware that after this command, indexes on unaffected requests will be changed."""
        server = 'owner' if ctx.message.channel.is_private else ctx.message.server.id
        indexes = parse_indexes(indexes)
        await self.reject_requests(server, indexes)

    @req.command(pass_context=True, aliases=('c',))
    @checks.is_server_owner()
    async def clear(self, ctx):
        """Clear remaining requests."""
        server = 'owner' if ctx.message.channel.is_private else ctx.message.server.id
        await self.reject_requests(server, list(range(len(self.get_serv(server)))))


def setup(bot):
    bot.add_cog(RequestSystem(bot))
