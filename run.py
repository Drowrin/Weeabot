import os
import re
import sys
import traceback
import textwrap

from weeabot import Weeabot

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
async def image(ctx):
    f = discord.File(os.path.join('images', 'test.png'))
    await ctx.send(
        file=f,
        embed=discord.Embed().set_image(url=f'attachment://{f.filename}')
    )


@bot.command(pass_context=True, name='exec')
async def execute(ctx, *, code: str):
    """Code is executed as a coroutine and the return is output to this channel."""
    lang = re.match(r'```(\w+\s*\n)', code)
    code = code.strip('` ')
    if lang:
        code = code[len(lang.group(1)):]
    block = f'```{lang[1] if lang else "py"}\n{{}}\n```'

    env = {
        'bot': bot,
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


if __name__ == '__main__':
    bot.run()
