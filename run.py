import os

from weeabot import Weeabot

bot = Weeabot(os.path.join('config', 'config.yml'), command_prefix='$')


@bot.command()
async def test(ctx):
    await ctx.affirmative()

    async def t(reaction, user):
        print(reaction, user)

    bot.reactionlisteners.add(ctx.message, t)
    print(await ctx.confirm('yes/no'))


if __name__ == '__main__':
    bot.run()
