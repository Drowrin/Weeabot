# noinspection PyUnresolvedReferences
import discord
# noinspection PyUnresolvedReferences
from discord.ext import commands

import inspect
import traceback


class BaseCog:
    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True, aliases=('d',))
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

        # noinspection PyBroadException
        try:
            result = eval(code, env)
            if inspect.isawaitable(result):
                result = await result
        except Exception:
            result = traceback.format_exc()

        await self.bot.edit_message(ctx.message, python.format('INPUT: {}\nOUTPUT: {}'.format(code, result)))


def setup(bot):
    bot.add_cog(BaseCog(bot))
