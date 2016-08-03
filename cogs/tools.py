# noinspection PyUnresolvedReferences
import discord
import inspect
import copy
import traceback
import pickle

# noinspection PyUnresolvedReferences
from discord.ext import commands
from os import listdir
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
    """Commands that only the owner can use."""
    
    def __init__(self, bot):
        super(Tools, self).__init__(bot)
        self.path = 'requests.json'
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
    
    def get_serv(self, server):
        if server not in self.requests:
            self.requests[server] = self.empty()
        return self.requests[server]

    async def get_msg(self, server, msg, channel=None):
        if server == 'owner':
            dest = self.bot.owner
        else:
            dest = self.bot.get_server(self.get_serv(server)).owner
        return await self.bot.get_message(discord.Object(id=(channel or await self.bot.get_private_channel(dest))), msg)

    async def get_req_msg(self, server):
        return await self.get_msg(server, self.get_serv(server)['msg'])

    async def message(self, server):
        if server == 'owner':
            header = "Global Requests\n-----\n{}"
            line = '{} | <{1.channel.server}: {1.channel}> {1.author}: `{1.content}`'
        else:
            header = "{} Requests\n-----\n{}".format(server.name, '{}')
            line = '{} | <{1.channel}> {1.author}: `{1.content}`'
        cont = []
        for req in self.get_serv(server)['list']:
            ind = self.get_serv(server)['list'].index(req)
            cont.append(line.format(ind, req))
        return header.format('\n'.join(cont))

    async def send_req_msg(self, server, dest=None):
        if not len(self.requests):
            if self.get_serv(server)['msg'] is not None:
                await self.bot.delete_message(self.get_serv(server)['msg'])
                self.get_serv(server)['msg'] = None
            return
        dest = dest or self.bot.owner if server == 'owner' else self.bot.get_server(server).owner
        if self.get_serv(server)['msg'] is not None:
            await self.bot.edit_message(self.get_serv(server)['msg'], await self.message(server))
        else:
            self.get_serv(server)['msg'] = await self.bot.send_message(dest, await self.message(server))
    
    async def add_request(self, mes, server):
        self.get_serv(server)['list'].append(mes)
        await self.save()
        await self.send_req_msg(server)

    @request_command(commands.group, owner_pass=False, pass_context=True,
                     aliases=('request',), invoke_without_command=True)
    async def req(self, ctx, *, command):
        """Send a request for a command."""
        msg = copy.copy(ctx.message)
        msg.content = command
        if is_command_of(ctx.bot, msg):
            await self.bot.process_commands(msg)
        else:
            await self.bot.send_message(msg.channel, "Added to todo list.")
            await self.bot.send_message(self.bot.owner, "Todo: {}".format(msg.content))

    @req.group(pass_context=True, aliases=('l',), invoke_without_command=True)
    @is_owner()
    async def list(self, ctx):
        """Display current requests."""
        if ctx.message.server is not None:
            servs = [ctx.message.server]
        else:
            servs = list(filter(lambda e: e.owner.id == ctx.message.author.id, self.bot.servers)) +
                ['owner' if ctx.message.author.id == self.bot.owner.id]
        for server in servs:
            if len(self.get_serv(server)['list']):
                await self.bot.say(self.message(server))
            else:
                await self.bot.say("No requests.")

    @list.command(aliases=('g',))
    @is_owner()
    async def glob_list(self):
        if len(self.get_serv('owner')['list']):
            await self.bot.say(await self.message('owner'))
        else:
            await self.bot.say("No requests.")

    @req.group(pass_context=True, aliases=('a',), invoke_without_command=True)
    @is_owner()
    async def accept(self, ctx, *, indexes: str=None):
        """Accept requests made by users."""
        indexes = parse_indexes(indexes)
        for i in indexes:
            try:
                re = self.get_serv(ctx.message.server.id)['list'][i]
                c = await self.bot.get_server(ctx.message.server.id).get_channel(re[1])
                r = await self.get_msg(ctx.message.server.id, re[0], channel=c)
            except IndexError:
                await self.bot.say("{} out of range.".format(i))
                return
            await self.bot.send_message(r.channel, '{0.author}, Your request was elevated.```{0.content}```'.format(r))
            await self.add_request(r.id, 'owner')
            self.get_serv(ctx.message.server.id)['list'].remove(re)
            await self.send_req_msg(ctx.message.server.id)
        await self.save()

    @accept.group(aliases=('g',))
    @is_owner()
    async def glob_accept(self, *, indexes: str=None):
        indexes = parse_indexes(indexes)
        for i in indexes:
            try:
                re = self.get_serv('owner')['list'][i]
                r = await self.get_msg('owner', re[0])
            except IndexError:
                await self.bot.say("{} out of range.".format(i))
                return
            await self.bot.send_message(r.channel, '{0.author}, Your request was accepted.```{0.content}```'.format(r))
            await self.bot.process_commands(r.id)
            self.get_serv('owner')['list'].remove(re)
            await self.send_req_msg('owner')
        await self.save()

    async def reject_requests(self, server, indexes: [int]):
        for i in indexes:
            try:
                re = self.get_serv(server)['list'][i]
                r = await self.get_msg(server, re[0], channel=re[1])
                await self.bot.send_message(r.channel, '{0.author}, Your request was denied.```{0.content}```'.format(r))
                self.get_serv(server)['list'].remove(re)
                await self.send_req_msg(server)
            except IndexError:
                await self.bot.say('{} is out of range.'.format(i))
        await self.save()

    @req.group(pass_context=True, aliases=('r',), invoke_without_command=True)
    @is_owner()
    async def reject(self, ctx, *, indexes: str=None):
        """Reject requests made by users."""
        indexes = parse_indexes(indexes)
        await self.reject_requests(ctx.message.server.id, indexes)

    @reject.command(aliases=('g',))
    @is_owner()
    async def glob_reject(self, *, indexes: str=None):
        indexes = parse_indexes(indexes)
        await self.reject_requests('owner', indexes)
    
    @req.group(pass_context=True, aliases=('c',), invoke_without_command=True)
    @is_owner()
    async def clear(self, ctx):
        """Clear remaining requests."""
        ser = ctx.message.server.id
        await self.reject_requests(ser, list(range(len(self.get_serv(ser)['list']) - 1)))

    @clear.command(aliases=('g',))
    @is_owner()
    async def glob_clear(self):
        await self.reject_requests('owner', list(range(len(self.get_serv('owner')['list']) - 1)))

    @commands.command(aliases=('oauth',))
    async def invite(self):
        """Get the oauth link for the bot."""
        perms = discord.Permissions.none()
        perms.read_messages = True
        perms.send_messages = True
        perms.manage_roles = True
        perms.ban_members = True
        perms.kick_members = True
        perms.manage_messages = True
        perms.embed_links = True
        perms.read_message_history = True
        perms.attach_files = True
        perms.external_emojis = True
        await self.bot.say(discord.utils.oauth_url(tokens['discord_ClientID'], perms))

    @commands.group()
    async def change(self):
        """Change a part of the bot's profile."""
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
    @is_owner()
    async def nick(self, ctx, nick: str):
        """Change the bot's nickname."""
        await self.bot.change_nickname(ctx.message.server.get_member(self.bot.user.id), nick)

    @commands.group(aliases=('e',), invoke_without_command=True)
    @is_owner()
    async def extensions(self):
        """Extension related commands.

        Invoke without a subcommand to list extensions."""
        await self.bot.say('Loaded: {}\nAll: {}'.format(' '.join(self.bot.cogs.keys()),
                                                        ' '.join([x for x in listdir('cogs') if '.py' in x])))

    @extensions.command(name='load', alises=('l',))
    @is_owner()
    async def load_extension(self, ext):
        """Load an extension."""
        # noinspection PyBroadException
        try:
            self.bot.load_extension(ext)
        except Exception:
            await self.bot.say('```py\n{}\n```'.format(traceback.format_exc()))
        else:
            await self.bot.say('{} loaded.'.format(ext))

    @extensions.command(name='unload', aliases=('u',))
    @is_owner()
    async def unload_extension(self, ext):
        """Unload an extension."""
        if ext in self.bot.config.required_extensions:
            await self.bot.say("{} is a required extension.".format(ext))
            return
        # noinspection PyBroadException
        try:
            self.bot.unload_extension(ext)
        except Exception:
            await self.bot.say('```py\n{}\n```'.format(traceback.format_exc()))
        else:
            await self.bot.say('{} unloaded.'.format(ext))
    
    @extensions.command(name='reload', aliases=('r',))
    @is_owner()
    async def reload_extension(self, ext):
        """Reload an extension."""
        # noinspection PyBroadException
        try:
            self.bot.unload_extension(ext)
            self.bot.load_extension(ext)
        except Exception:
            await self.bot.say('```py\n{}\n```'.format(traceback.format_exc()))
        else:
            await self.bot.say('{} reloaded.'.format(ext))
    
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
    
    @commands.command()
    @is_owner()
    async def logout(self):
        """Make the bot log out."""
        await self.bot.logout()


def setup(bot):
    bot.add_cog(Tools(bot))
