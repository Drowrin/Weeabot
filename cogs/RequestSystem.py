# noinspection PyUnresolvedReferences
import traceback
import copy
import pickle

# noinspection PyUnresolvedReferences
from discord.ext import commands
from utils import *
import checks


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

    def __init__(self, bot):
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
        await self.bot.say(
            "This will enable the requests system in this server. Several new features will become available.\n"
            "These are features that would generally be limited to moderater/admin/bot-owner control.\n"
            "However, with this system, normal members can 'request' these commands, and those with proper privelege\n"
            "can simply approve/deny it without having to re-run the command themselves.\n"
            "\n"
            "This will create a new channel, where requests will be sent.\n"
            "Anyone you give access to this channel will be able to approve requests.\n"
            "\n"
            "Are you sure you want to enable this (yes|no)?\n"
            "It can be disabled at any time with command disable_requests.\n"
        )
        response = await self.bot.wait_for_message(author=ctx.message.author)
        if not response.content.startswith('y'):
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

    @staticmethod
    def req_message(server, req, ind) -> dict:
        if server == 'owner':
            line = '<{0.channel.server}: {0.channel}> {0.author}: {0.content}'
        else:
            line = '{0.channel.mention} {0.author.mention}: {0.content}'
        return {'name': str(ind), 'value': line.format(req)}

    async def send_req_msg(self, server, msg, ind, *, dest=None):
        dest = dest or request_channel(self.bot, self.bot.get_server(server)) or self.bot.owner
        e = discord.Embed(colour=msg.author.colour)
        # noinspection PyArgumentList
        e.add_field(**self.req_message(server, msg, ind))
        await self.bot.send_message(dest, embed=e)

    async def add_request(self, mes, server):
        if len(list(filter(lambda e: e.author.id == mes.author.id, self.all_req()))) >= self.user_limit:
            await self.bot.send_message(mes.channel,
                                        "{}, user request limit reached ({}).".format(mes.author.display_name,
                                                                                      self.user_limit))
            return
        if len(list(filter(lambda e: e.server.id == mes.server.id, self.all_req()))) >= self.server_limit:
            await self.bot.send_message(mes.channel, "{}, server request limit reached ({}).".format(mes.server.name,
                                                                                                     self.server_limit))
            return
        if len(self.all_req()) >= self.global_limit:
            await self.bot.send_message(mes.channel, "Global request limit reached ({}).".format(self.global_limit))
            return
        ind = len(self.get_serv(server))
        await self.bot.send_message(mes.channel, "Sent request to {} at index {}.".format(
            self.bot.owner.name if server == 'owner' else mes.server.owner.display_name,
            ind
        ))
        self.get_serv(server).append(mes)
        await self.save()
        await self.send_req_msg(server, mes, ind)

    @commands.group(name='request', aliases=('req', 'r'))
    async def req(self):
        """Request based commands."""

    @req.command(pass_context=True, name='feature', aliases=('f', 'make', 'm'))
    @request(owner_bypass=False, server_bypass=False)
    async def req_make(self, ctx, *, command):
        """Send a request for a command, or request a feature."""
        msg = copy.copy(ctx.message)
        msg.content = command
        if is_command_of(ctx.bot, msg):
            await self.bot.process_commands(msg)
        else:
            await self.bot.send_message(msg.channel, "Added to todo list.")
            await self.bot.send_message(self.bot.owner, "Todo: {}".format(msg.content))

    @req.group(pass_context=True, aliases=('l',), invoke_without_command=True, no_pm=True)
    @checks.is_server_owner()
    async def list(self, ctx):
        """Display current requests."""
        e = discord.Embed(title='Requests', colour=ctx.message.server.me.colour)
        for ind, r in enumerate(self.get_serv(ctx.message.server.id)):
            # noinspection PyArgumentList
            e.add_field(**self.req_message(ctx.message.server.id, r, ind))
        await self.bot.say(embed=e)

    @list.command(aliases=('g',))
    @checks.is_owner()
    async def glob_list(self):
        e = discord.Embed(title='Requests')
        for ind, r in self.get_serv('owner'):
            # noinspection PyArgumentList
            e.add_field(**self.req_message('owner', r, ind))
        await self.bot.say(embed=e)

    @req.group(pass_context=True, aliases=('a', 'approve'), invoke_without_command=True)
    @checks.is_server_owner()
    async def accept(self, ctx, *, indexes: str=None):
        """Accept requests made by users."""
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
            self.get_serv(ctx.message.server.id).remove(r)
        await self.save()

    @accept.group(aliases=('g',))
    @checks.is_owner()
    async def glob_accept(self, *, indexes: str=None):
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
        await self.save()

    async def reject_requests(self, server, indexes: [int]):
        rs = []
        for i in indexes:
            try:
                rs.append(self.get_serv(server)[i])
            except IndexError:
                await self.bot.say('{} is out of range.'.format(i))
        for r in rs:
            await self.bot.send_message(r.channel, '{0.author}, Your request was denied.```{0.content}```'.format(r))
        self.remove_from_serv(server, rs)
        await self.save()

    @req.group(pass_context=True, aliases=('r',), invoke_without_command=True)
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

    @commands.command()
    @request(owner_bypass=False)
    async def reqtest(self):
        await self.bot.say('reqtest completed')


def setup(bot):
    bot.add_cog(RequestSystem(bot))
