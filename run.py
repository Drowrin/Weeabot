import os

from weeabot import Weeabot
from weeabot.core.context import Context

import discord

bot = Weeabot(os.path.join('config', 'config.yml'), command_prefix='$')


@bot.command()
async def test(ctx):
    await ctx.affirmative()

    async def t(reaction, user):
        print(reaction, user)

    bot.reactionlisteners.add(ctx.message, t)
    print(await ctx.confirm('yes/no'))


@bot.command()
async def image(ctx: Context):
    f = discord.File(os.path.join('images', 'test.png'))
    await ctx.send(
        file=f,
        embed=discord.Embed().set_image(url=f'attachment://{f.filename}')
    )


if __name__ == '__main__':
    bot.run()
