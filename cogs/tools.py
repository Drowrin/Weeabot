import traceback
import inspect
import json
import dateutil.parser

import discord
from discord.ext import commands

import checks
import utils


class Tools(utils.SessionCog):
    """Utilities and management commands."""

    def __init__(self, bot: commands.Bot):
        super(Tools, self).__init__(bot)

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
    async def change(self):
        """Change a part of the bot's profile.

        Subcommands are limited access."""
        pass
        
    @change.command()
    @checks.is_owner()
    async def avatar(self, link: str):
        """Change the bot's avatar."""
        with await utils.download_fp(self.session, link) as fp:
            await self.bot.edit_profile(avatar=fp.read())

    @change.command()
    @checks.is_owner()
    async def username(self, name: str):
        """Change the bot's username."""
        await self.bot.edit_profile(username=name)

    @commands.command(pass_context=True)
    @checks.is_owner()
    async def pickmessage(self, ctx, message_id):
        """puts a message object in bot.temp_message"""
        self.bot.temp_message = await self.bot.get_message(ctx.message.channel, message_id)
    
    @commands.command(pass_context=True)
    @checks.is_owner()
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
        except Exception:
            await self.bot.say(python.format(traceback.format_exc()))
            return

        try:
            await self.bot.say(python.format(result))
        except discord.HTTPException:
            await self.bot.say("Output too large")

    @commands.command(pass_context=True, aliases=('exec',))
    @checks.is_owner()
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

        try:
            exec(code, env)
        except Exception:
            await self.bot.say(python.format(traceback.format_exc()))
            return

        await self.bot.say('\N{OK HAND SIGN}')

    @commands.command(pass_context=True)
    @checks.is_owner()
    async def inspect(self, ctx, m_id: str):
        """Inspect the contents of a message."""
        await self.bot.say(str([c for c in (await self.bot.get_message(ctx.message.channel, m_id)).content]))

    @commands.command()
    @checks.is_owner()
    async def logout(self):
        """Make the bot log out."""
        await self.bot.say(":sob: bye")
        await self.bot.logout()

    @commands.group(name='testing')
    @checks.is_owner()
    async def test(self):
        pass

    @test.command(pass_context=True, name='list')
    @checks.is_owner()
    async def list_test(self):
        servs = [self.bot.get_server(x).name for x in self.bot.config.testing_servers]
        chans = [discord.utils.get(self.bot.get_all_channels(), id=x).name for x in self.bot.config.testing_channels]
        await self.bot.say('servers:\n{}\n\nchannels:\n{}'.format(servs, chans))

    @test.command(pass_context=True, name='add', no_pm=True)
    @checks.is_owner()
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
        await self.bot.affirmative()

    @test.command(pass_context=True, name='remove', no_pm=True)
    @checks.is_owner()
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
        await self.bot.affirmative()

    @commands.command(pass_context=True)
    @checks.is_server_owner()
    async def moderator_role(self, ctx, role: discord.Role):
        """Set the moderator role for this server."""
        self.bot.server_configs[ctx.message.server.id]['moderator_role'] = role.id
        self.bot.dump_server_configs()
        await self.bot.affirmative()


def setup(bot):
    bot.add_cog(Tools(bot))
