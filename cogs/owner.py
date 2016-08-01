# noinspection PyUnresolvedReferences
import discord
import pickle
import inspect
import copy

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
        self.req_msg = None
        self.path = 'requests.pkl'
        try:
            with open(self.path, 'rb') as f:
                self.requests = pickle.load(f)
        except FileNotFoundError:
            self.requests = []
            with open(self.path, 'wb') as f:
                pickle.dump(self.requests, f, -1)

    def message(self):
        return "Requests\n-----\n{}".format('\n'.join(['{0} | <{1.channel.server}: {1.channel}> {1.author}: {1.content}'
                                                      .format(self.requests.index(req), req) for req in self.requests]))

    async def send_req_msg(self, dest=None):
        if not len(self.requests):
            if self.req_msg is not None:
                await self.bot.delete_message(self.req_msg)
                self.req_msg = None
            return
        dest = dest or self.bot.owner
        if self.req_msg is not None:
            await self.bot.edit_message(self.req_msg, self.message())
        else:
            self.req_msg = await self.bot.send_message(dest, self.message())
    
    async def add_request(self, mes):
        self.requests.append(mes)
        with open(self.path, 'wb') as f:
            pickle.dump(self.requests, f, -1)
        await self.send_req_msg()

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

    @req.command(aliases=('l',))
    @is_owner()
    async def list(self):
        """Display current requests."""
        if len(self.requests):
            await self.bot.say(self.message())
        else:
            await self.bot.say("No requests.")
    
    @req.command(aliases=('a',))
    @is_owner()
    async def accept(self, *, indexes: str=None):
        """Accept requests made by users."""
        indexes = parse_indexes(indexes)
        for i in indexes:
            try:
                r = self.requests[i]
            except IndexError:
                raise commands.BadArgument('{} is out of range.'.format(i))
            await self.bot.send_message(r.channel, '{0.author}, Your request was accepted.```{0.content}```'.format(r))
            await self.bot.process_commands(r)
            self.requests.remove(r)
            await self.send_req_msg()
        with open(self.path, 'wb') as f:
            pickle.dump(self.requests, f, -1)
    
    @req.command(aliases=('r',))
    @is_owner()
    async def reject(self, *, indexes: str=None):
        """Reject requests made by users."""
        indexes = parse_indexes(indexes)
        for i in indexes:
            try:
                r = self.requests[i]
            except IndexError:
                raise commands.BadArgument('{} is out of range.'.format(i))
            await self.bot.send_message(r.channel, '{0.author}, Your request was denied.```{0.content}```'.format(r))
            self.requests.remove(r)
            await self.send_req_msg()
        with open(self.path, 'wb') as f:
            pickle.dump(self.requests, f, -1)
    
    @req.command(aliases=('c',))
    @is_owner()
    async def clear(self):
        """Clear remaining requests."""
        self.requests = []
        with open(self.path, 'wb') as f:
            pickle.dump(self.requests, f, -1)
        await self.send_req_msg()
        
    @commands.command()
    @is_owner()
    async def avatar(self, link: str):
        """Change the bot's avatar."""
        with await download_fp(self.session, link) as fp:
            await self.bot.edit_profile(avatar=fp.read())

    @commands.command()
    @is_owner()
    async def username(self, name: str):
        """Change the bot's username."""
        await self.bot.edit_profile(username=name)

    @commands.command(pass_context=True)
    @is_owner()
    async def nick(self, ctx, nick: str):
        """Change the bot's nickname."""
        await self.bot.change_nickname(ctx.message.server.get_member(self.bot.user.id), nick)

    @commands.command()
    @is_owner()
    async def extensions(self):
        """List loaded and unloaded extentsions."""
        await self.bot.say('Loaded: {}\nAll: {}'.format(' '.join(self.bot.cogs.keys()),
                                                        ' '.join([x for x in listdir('cogs') if '.py' in x])))

    @commands.command(name='load')
    @is_owner()
    async def load_extension(self, ext):
        """Load an extension."""
        try:
            self.bot.load_extension(ext)
        except Exception as e:
            await self.bot.say('{}: {}'.format(type(e).__name__, e))
        else:
            await self.bot.say('{} loaded.'.format(ext))

    @commands.command(name='unload')
    @is_owner()
    async def unload_extension(self, ext):
        """Unload an extension."""
        if ext in self.bot.required_extensions:
            await self.bot.say("{} is a required extension.".format(ext))
            return
        try:
            self.bot.unload_extension(ext)
        except Exception as e:
            await self.bot.say('{}: {}'.format(type(e).__name__, e))
        else:
            await self.bot.say('{} unloaded.'.format(ext))
    
    @commands.command(name='reload')
    @is_owner()
    async def reload_extension(self, ext):
        """Reload an extension."""
        try:
            self.bot.unload_extension(ext)
            self.bot.load_extension(ext)
        except Exception as e:
            await self.bot.say('{}: {}'.format(type(e).__name__, e))
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
    
    @commands.command()
    @is_owner()
    async def restart(self):
        """Restart the bot."""
        self.bot.do_restart = True
        await self.bot.logout()


def setup(bot):
    bot.add_cog(Tools(bot))
