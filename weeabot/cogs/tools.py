import io
import copy
import re
import sys
import textwrap
import traceback

import discord
from discord.ext import commands

from . import base_cog
from .stats import do_not_track


class Tools(base_cog(session=True)):
    """
    Bot Admin Tools
    """

    def __global_check(self, ctx):
        """
        Only allow bot owner to use these tools.
        """
        return ctx.bot.owner == ctx.author

    @commands.group()
    @do_not_track
    async def change(self, ctx):
        """
        Change part of the bot's profile.
        """

    @change.command()
    @do_not_track
    async def avatar(self, ctx, link: str = None):
        """
        Change the avatar.
        """
        if link is None:
            try:
                link = ctx.message.attachments[0]
            except IndexError:
                raise commands.BadArgument("No image provided.")
        async with self.session.get(link) as r:
            fp = io.BytesIO()
            val = await r.read()
            fp.write(val)
            fp.seek(0)
        await self.bot.user.edit(avatar=fp)

    @change.command(aliases=('name',))
    @do_not_track
    async def username(self, ctx, *, name):
        """
        Change the username.
        """
        try:
            await self.bot.user.edit(username=name)
        except (discord.ClientException, discord.HTTPException):
            raise commands.BadArgument("Error changing name. Too long? Improper characters?")
        await ctx.affirmative()

    @commands.command(name='exec')
    @do_not_track
    async def _execute(self, ctx, *, code: str):
        """
        Code is executed as a coroutine and the result is output to this channel.
        """
        lang = re.match(r'```(\w+\s*\n)', code)
        code = code.strip('` ')
        if lang:
            code = code[len(lang.group(1)):]
        block = f'```{lang[1] if lang else "py"}\n{{}}\n```'

        env = {
            'bot': self.bot,
            'ctx': ctx,
            'message': ctx.message,
            'guild': ctx.message.guild,
            'channel': ctx.message.channel,
            'author': ctx.message.author
        }
        env.update(globals())

        embed = discord.Embed(
            description=block.format(textwrap.shorten(code, width=1000))
        ).set_footer(
            text=f'Python {sys.version.split()[0]}',
            icon_url='https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/200px-Python-logo-notext.svg.png'
        )

        # prepare to execute
        lines = code.split('\n')
        exec('async def _():\n    ' + '\n    '.join(lines) + '\nctx.exec = _', env)

        embed.color = discord.Colour.blue()
        embed.title = "\N{TIMER CLOCK}"
        msg = await ctx.send(embed=embed)

        # clean up code afterwards
        embed.description = None

        try:
            result = await ctx.exec()
            if result is not None:
                embed.add_field(
                    name='Result',
                    value=block.format(textwrap.shorten(str(result), width=1000))
                )
            embed.colour = discord.Colour.green()
            embed.title = "\N{OK HAND SIGN}"
        except Exception as e:
            embed.add_field(
                name='Exception',
                value=block.format(''.join(traceback.format_exception(type(e), e, None)))
            )
            embed.colour = discord.Colour.red()
            embed.title = "\N{CROSS MARK}"
        try:
            await msg.edit(embed=embed)
        except discord.HTTPException:
            print(embed.fields[0].value)
            embed.remove_field(0)
            embed.description = "Output too large, check logs"
            await msg.edit(embed=embed)

    @commands.command(aliases=('close',))
    @do_not_track
    async def logout(self, ctx):
        """
        Make the bot log out and close.
        """
        await ctx.send(':sob: bye')
        await self.bot.close

    @commands.command(name='as')
    @do_not_track
    async def _as_user(self, ctx, user: discord.Member, *, command):
        """
        Run a command as another user.
        """
        m = copy.copy(ctx.message)
        m.author = user
        m.content = command
        await self.bot.process_commands(m)


def setup(bot):
    bot.add_cog(Tools(bot))
