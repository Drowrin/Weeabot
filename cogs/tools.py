# noinspection PyUnresolvedReferences
import traceback

import discord
import inspect
import copy
import pickle

# noinspection PyUnresolvedReferences
from discord.ext import commands
from utils import *


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
        raise commands.BadArgument()
    return out


class Tools(SessionCog):
    """Utilities and management commands."""

    user_limit = 5
    server_limit = 30
    global_limit = 100

    def __init__(self, bot: commands.Bot):
        super(Tools, self).__init__(bot)
        self.path = 'requests.pkl'
        try:
            with open(self.path, 'rb') as f:
                self.requests = pickle.load(f)
            if len(self.requests) == 0:
                self.requests = {"owner": self.empty()}
        except FileNotFoundError:
            self.requests = {"owner": self.empty()}
        self._dump()

    @staticmethod
    def empty():
        return {"msg": None, "list": []}

    def _dump(self):
        with open(self.path, 'wb') as f:
            pickle.dump(self.requests, f, -1)

    async def save(self):
        """Save the current data to disk."""
        await self.bot.loop.run_in_executor(None, self._dump)

    def all_req(self):
        r = []
        for serv in self.requests:
            for m in self.requests[serv]['list']:
                r.append(m)
        return r
    
    def get_serv(self, server):
        if server not in self.requests:
            self.requests[server] = self.empty()
        return self.requests[server]

    def message(self, server):
        if server == 'owner':
            header = "Global Requests\n-----\n{}"
            line = '{0} | <{1.channel.server}: {1.channel}> {1.author}: {1.content}'
        else:
            header = "{} Requests\n-----\n".format(self.bot.get_server(server).name) + '{}'
            line = '{0} | <{1.channel}> {1.author}: {1.content}'
        cont = []
        for req in self.get_serv(server)['list']:
            ind = self.get_serv(server)['list'].index(req)
            cont.append(line.format(ind, req))
        if len(cont) == 0:
            cont = ['No requests.']
        return header.format('\n'.join(cont))

    async def send_req_msg(self, server, dest=None):
        if not len(self.requests):
            if self.get_serv(server)['msg'] is not None:
                await self.bot.delete_message(self.get_serv(server)['msg'])
                self.requests[server]['msg'] = None
            return
        dest = dest or self.bot.owner if server == 'owner' else self.bot.get_server(server).owner
        self.get_serv(server)['msg'] = await self.bot.send_message(dest, self.message(server))
    
    async def add_request(self, mes, server):
        if len(list(filter(lambda e: e.author.id == mes.author.id, self.all_req()))) >= self.user_limit:
            await self.bot.send_message(mes.channel, "{}, user request limit reached ({}).".format(mes.author.display_name, self.user_limit))
            return
        if len(list(filter(lambda e: e.server.id == mes.server.id, self.all_req()))) >= self.server_limit:
            await self.bot.send_message(mes.channel, "{}, server request limit reached ({}).".format(mes.server.name, self.server_limit))
            return
        if len(self.all_req()) >= self.global_limit:
            await self.bot.send_message(mes.channel, "Global request limit reached ({}).".format(self.global_limit))
            return
        await self.bot.send_message(mes.channel, "Sent request to {}.".format(
             self.bot.owner.name if server == 'owner' else mes.server.owner.display_name))
        self.get_serv(server)['list'].append(mes)
        await self.save()
        await self.send_req_msg(server)

    @commands.group(name='request', aliases=('req',))
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

    @req.group(pass_context=True, aliases=('l',), invoke_without_command=True)
    @is_server_owner()
    async def list(self, ctx):
        """Display current requests."""
        if ctx.message.server is not None:
            servs = [ctx.message.server]
        else:
            servs = list(filter(lambda e: e.owner.id == ctx.message.author.id, self.bot.servers))
        for server in servs:
                await self.bot.say(self.message(server.id))
        if ctx.message.author.id == self.bot.owner.id:
                await self.bot.say(self.message('owner'))

    @list.command(aliases=('g',))
    @is_owner()
    async def glob_list(self):
            await self.bot.say(self.message('owner'))

    @req.group(pass_context=True, aliases=('a', 'approve'), invoke_without_command=True)
    @is_server_owner()
    async def accept(self, ctx, *, indexes: str=None):
        """Accept requests made by users."""
        form = '{0.author.mention}, Your request was {1}.```{0.content}```'
        indexes = parse_indexes(indexes)
        rs = []
        for i in indexes:
            try:
                rs.append(self.get_serv(ctx.message.server.id)['list'][i])
            except IndexError:
                await self.bot.say("{} out of range.".format(i))
        for r in rs:
            await self.bot.send_message(r.channel, form.format(r, 'accepted'))
            self.get_serv(ctx.message.server.id)['list'].remove(r)
            self.get_serv('owner')['list'].append(r)
            await self.bot.process_commands(r)
            self.get_serv('owner')['list'].remove(r)
        await self.send_req_msg(ctx.message.server.id)
        await self.save()

    @accept.group(aliases=('g',))
    @is_owner()
    async def glob_accept(self, *, indexes: str=None):
        form = '{0.author.mention}, Your request was accepted.```{0.content}```'
        indexes = parse_indexes(indexes)
        rs = []
        for i in indexes:
            try:
                rs.append(self.get_serv('owner')['list'][i])
            except IndexError:
                await self.bot.say("{} out of range.".format(i))
        for r in rs:
            await self.bot.send_message(r.channel, form.format(r))
            await self.bot.process_commands(r)
            self.get_serv('owner')['list'].remove(r)
        await self.send_req_msg('owner')
        await self.save()

    async def reject_requests(self, server, indexes: [int]):
        rs = []
        for i in indexes:
            try:
                rs.append(self.get_serv(server)['list'][i])
            except IndexError:
                await self.bot.say('{} is out of range.'.format(i))
        for r in rs:
            await self.bot.send_message(r.channel, '{0.author}, Your request was denied.```{0.content}```'.format(r))
        self.get_serv(server)['list'] = []
        await self.send_req_msg(server)
        await self.save()

    @req.group(pass_context=True, aliases=('r',), invoke_without_command=True)
    @is_server_owner()
    async def reject(self, ctx, *, indexes: str=None):
        """Reject requests made by users."""
        serv = ctx.message.server
        if serv is None:
            await self.bot.say("Server not found.")
            return
        indexes = parse_indexes(indexes)
        await self.reject_requests(serv.id, indexes)

    @reject.command(aliases=('g',))
    @is_owner()
    async def glob_reject(self, *, indexes: str=None):
        indexes = parse_indexes(indexes)
        await self.reject_requests('owner', indexes)
    
    @req.group(pass_context=True, aliases=('c',), invoke_without_command=True)
    @is_server_owner()
    async def clear(self, ctx, server: str):
        """Clear remaining requests.
        
        User 'here' as the server argument to clear requests from this server.
        Otherwise use a server name."""
        if server == 'here':
            serv = ctx.message.server
        else:
            serv = discord.utils.get(self.bot.servers, name=server, owner=ctx.message.author)
        if serv is None:
            await self.bot.say("Server not found.")
            return
        await self.reject_requests(serv.id, list(range(len(self.get_serv(serv.id)['list']))))

    @clear.command(aliases=('g',))
    @is_owner()
    async def glob_clear(self):
        await self.reject_requests('owner', list(range(len(self.get_serv('owner')['list']))))

    @commands.command(aliases=('oauth',))
    async def invite(self):
        """Get the oauth link for the bot."""
        perms = discord.Permissions.none()
        perms.administrator = True
        await self.bot.say(discord.utils.oauth_url((await self.bot.application_info()).id, perms))

    @commands.command(aliases=('contribute',))
    async def source(self):
        """Link to the bot's repository."""
        await self.bot.say('<https://github.com/Drowrin/Weeabot>')

    @commands.group()
    async def emoji(self):
        """Emoji related commands."""

    @emoji.command(name='add', pass_context=True, no_pm=True)
    @request(level=RequestLevel.server)
    async def __add(self, ctx, name: str, link: str=None):
        """Add an emoji by link or attachement."""
        if link is None and len(ctx.message.attachments) == 0:
            await self.bot.say("No image proovided.")
            return
        link = link or ctx.message.attachments[0]['url']
        with await download_fp(self.session, link) as image:
            try:
                await self.bot.create_custom_emoji(ctx.message.server, name=name, image=image.read())
            except:
                await self.bot.say(traceback.print_exc())

    @commands.group()
    async def change(self):
        """Change a part of the bot's profile.

        Subcommands are limited access."""
        pass
        
    @change.command()
    @is_owner()
    async def avatar(self, link: str):
        """Change the bot's avatar."""
        with await download_fp(self.session, link) as fp:
            await self.bot.edit_profile(avatar=fp.read())

    @change.command()
    @is_owner()
    async def username(self, name: str):
        """Change the bot's username."""
        await self.bot.edit_profile(username=name)

    @change.command(pass_context=True)
    @request(level=RequestLevel.server, )
    async def nick(self, ctx, nick: str):
        """Change the bot's nickname."""
        await self.bot.change_nickname(ctx.message.server.get_member(self.bot.user.id), nick)
    
    @commands.command(pass_context=True)
    @is_owner()
    async def debug(self, ctx, *, code: str):
        """Evaluates an expression to see what is happening internally."""
        code = code.strip('` ')
        python = '```py\n{}\n```'

        env = {
            'bot': self.bot,
            'ctx': ctx,
            'message': ctx.message,
            'server': ctx.message.server,
            'channel': ctx.message.channel,
            'author': ctx.message.author
        }

        env.update(globals())

        try:
            result = eval(code, env)
            if inspect.isawaitable(result):
                result = await result
        except Exception as e:
            await self.bot.say(python.format('{}: {}'.format(type(e).__name__, e)))
            return

        await self.bot.say(python.format(result))

    @commands.command(pass_context=True, aliases=('exec',))
    @is_owner()
    async def execute(self, ctx, *, code: str):
        """Evaluates an expression to see what is happening internally."""
        code = code.strip('` ')
        python = '```py\n{}\n```'

        env = {
            'bot': self.bot,
            'ctx': ctx,
            'message': ctx.message,
            'server': ctx.message.server,
            'channel': ctx.message.channel,
            'author': ctx.message.author
        }

        env.update(globals())

        # noinspection PyBroadException
        try:
            exec(code, env)
            await self.bot.say('\N{OK HAND SIGN}')
        except Exception:
            await self.bot.say(python.format(traceback.format_exc()))

    @commands.command(pass_context=True)
    @is_owner()
    async def inspect(self, ctx, m_id: str):
        """Inspect the contents of a message."""
        await self.bot.say(str([c for c in (await self.bot.get_message(ctx.message.channel, m_id)).content]))

    @commands.command()
    @is_owner()
    async def logout(self):
        """Make the bot log out."""
        await self.bot.logout()

    @commands.group(name='testing')
    @is_owner()
    async def test(self):
        pass

    @test.command(pass_context=True, name='list')
    @is_owner()
    async def list_test(self):
        servs = [self.bot.get_server(x).name for x in self.bot.config.testing_servers]
        chans = [discord.utils.get(self.bot.get_all_channels(), id=x).name for x in self.bot.config.testing_channels]
        await self.bot.say('servers:\n{}\n\nchannels:\n{}'.format(servs, chans))

    @test.command(pass_context=True, name='add', no_pm=True)
    @is_owner()
    async def add_test(self, ctx, typ: str='channel'):
        """args are 'channel' or 'server'"""
        if typ == 'channel':
            self.bot.config.testing_channels.append(ctx.message.channel.id)
        if typ == 'server':
            self.bot.config.testing_servers.append(ctx.message.server.id)
        else:
            await self.bot.say("Possible args are 'channel' and 'server'")
            return
        await self.bot.config.save()
        await self.bot.say("Added. \N{OK HAND SIGN}")

    @test.command(pass_context=True, name='remove', no_pm=True)
    @is_owner()
    async def remove_test(self, ctx, typ: str='channel'):
        """args are 'channel' or 'server'"""
        if typ == 'channel':
            self.bot.config.testing_channels.remove(ctx.message.channel.id)
        if typ == 'server':
            self.bot.config.testing_servers.remove(ctx.message.server.id)
        else:
            await self.bot.say("Possible args are 'channel' and 'server'")
            return
        await self.bot.config.save()
        await self.bot.say("Removed. \N{OK HAND SIGN}")


def setup(bot):
    bot.add_cog(Tools(bot))
