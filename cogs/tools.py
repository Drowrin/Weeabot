import traceback
import copy
import re
import sys

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

    @commands.command(pass_context=True, name='exec')
    @checks.is_owner()
    async def execute(self, ctx, *, code: str):
        """Code is executed as a coroutine and the return is output to this channel."""
        lang = re.match(r'```(\w+\s*\n)', code)
        code = code.strip('` ')
        if lang:
            code = code[len(lang.group(1)):]
        block = f'```{lang[1] if lang else "py"}\n{{}}\n```'

        env = {
            'bot': self.bot,
            'ctx': ctx,
            'message': ctx.message,
            'server': ctx.message.server,
            'channel': ctx.message.channel,
            'author': ctx.message.author
        }
        env.update(globals())

        embed = discord.Embed(
            description=block.format(code)
        ).set_footer(
            text=f'Python {sys.version.split()[0]}',
            icon_url='https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/200px-Python-logo-notext.svg.png'
        )

        # prepare to execute
        lines = code.split('\n')
        exec('async def _():\n    ' + '\n    '.join(lines) + '\nctx.exec = _', env)

        embed.color = discord.Colour.blue()
        embed.title = "In Progress"
        msg = await self.bot.say(embed=embed)

        # clean up code afterwards
        embed.description = None

        try:
            result = await ctx.exec()
            if result is not None:
                embed.add_field(
                    name='Result',
                    value=block.format(result)
                )
            embed.colour = discord.Colour.green()
            embed.title = "Success"
        except Exception as e:
            embed.add_field(
                name='Exception',
                value=block.format(''.join(traceback.format_exception(type(e), e, None)))
            )
            embed.colour = discord.Colour.red()
            embed.title = "Failure"
        await self.bot.edit_message(msg, embed=embed)

    @commands.command()
    @checks.is_owner()
    async def logout(self):
        """Make the bot log out."""
        await self.bot.say(":sob: bye")
        await self.bot.logout()

    @commands.command(pass_context=True)
    @checks.is_server_owner()
    async def moderator_role(self, ctx, role: discord.Role):
        """Set the moderator role for this server."""
        self.bot.server_configs[ctx.message.server.id]['moderator_role'] = role.id
        self.bot.dump_server_configs()
        await self.bot.affirmative()

    @commands.command(pass_context=True, name='as')
    @checks.is_trusted()
    async def _as_user(self, ctx, user: discord.Member, *, command):
        """Run a command as another member."""
        m = copy.copy(ctx.message)
        m.author = user
        m.content = command
        await self.bot.process_commands(m)


def setup(bot):
    bot.add_cog(Tools(bot))
