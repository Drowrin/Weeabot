import random
import copy

import discord
from discord.ext import commands

from ._base import base_cog


class Toys(base_cog()):
    """
    Pointless stuff goes here.
    """

    def __init__(self, bot):
        super(Toys, self).__init__(bot)
        self.do_messages = {}
        self.atk = self.bot.content['attack']
        self.guns = {}

    @staticmethod
    async def text_embed(message: discord.Message, text: str):
        try:
            await message.channel.send(embed=discord.Embed(
                description=text
            ).set_author(
                name=message.author.display_name,
                icon_url=message.author.avatar_url
            ))
            await message.delete()
        except discord.HTTPException:
            await message.channel.send("The formatting went too far for discord.")

    async def get_text(self, ctx: commands.Context) -> str:
        t = ctx.invoked_with.join(ctx.message.clean_content.split(ctx.invoked_with)[1:])
        if t:
            return t
        async for m in ctx.message.channel.history(limit=1, before=ctx.message):
            await self.bot.delete_message(m)
            if m.clean_content:
                return m.clean_content
            if m.embeds:
                return m.embeds[0]['description']
            raise commands.BadArgument("No suitable text found.")

    @commands.group(name='text', aliases=('t',))
    async def text_command(self, ctx):
        """
        Text transformations.
        """

    @text_command.command(aliases=('a',))
    async def aesthetic(self, ctx):
        """
        AESTHETIC
        """
        text = await self.get_text(ctx)
        translated = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ?!\"#$%&\'()*+,-./\\~'
        fullwidth = str.maketrans(translated, ''.join(chr(ord(c) + 0xFEE0) for c in translated))
        await self.text_embed(ctx.message, text.translate(fullwidth))

    @text_command.command(aliases=('z',))
    async def zalgo(self, ctx):
        """ZALGO"""
        source = (await self.get_text(ctx)).upper()
        zalgo_chars = [chr(i) for i in range(0x0300, 0x036F + 1)]
        zalgo_chars.extend(['\u0488', '\u0489'])
        zalgoized = [letter + ''.join(random.choice(zalgo_chars) for _ in range(random.randint(1, 25)))
                     for letter in source]
        await self.text_embed(ctx.message, ''.join(zalgoized))

    @text_command.command(aliases=('e',))
    async def emoji(self, ctx):
        """EMOJI"""
        text = (await self.get_text(ctx)).upper()
        translated = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ!'
        translated_to = ''.join([
            '\N{NEGATIVE SQUARED LATIN CAPITAL LETTER A}',
            '\N{NEGATIVE SQUARED LATIN CAPITAL LETTER B}',
            '\N{COPYRIGHT SIGN}',
            '\N{LEFTWARDS ARROW WITH HOOK}',
            '\N{BANKNOTE WITH EURO SIGN}',
            '\N{CARP STREAMER}',
            '\N{COMPRESSION}',
            '\N{PISCES}',
            '\N{INFORMATION SOURCE}',
            '\N{SILHOUETTE OF JAPAN}',
            '\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}',
            '\N{WOMANS BOOTS}',
            '\N{CIRCLED LATIN CAPITAL LETTER M}',
            '\N{CAPRICORN}',
            '\N{HEAVY LARGE CIRCLE}',
            '\N{NEGATIVE SQUARED LATIN CAPITAL LETTER P}',
            '\N{LEO}',
            '\N{REGISTERED SIGN}',
            '\N{HEAVY DOLLAR SIGN}',
            '\N{LATIN CROSS}',
            '\N{OPHIUCHUS}',
            '\N{ARIES}',
            '\N{CHART WITH UPWARDS TREND}',
            '\N{CROSS MARK}',
            '\N{BANKNOTE WITH YEN SIGN}',
            '\N{CIRCLED LATIN CAPITAL LETTER Z}',
            '\N{WARNING SIGN}',
        ])
        emoji = str.maketrans(translated, translated_to)
        await self.text_embed(ctx.message, '      '.join(text.translate(emoji).split()))

    @commands.command(pass_context=True)
    async def do(self, ctx, n: int, *, command):
        """Repeat a command up to 5 times."""
        limit = 5

        # handle user input
        if not command.startswith(self.bot.command_prefix):
            command = self.bot.command_prefix + command
        if n > limit:
            n = limit

        # check times run
        if ctx.message.id not in self.do_messages:
            self.do_messages[ctx.message.id] = 0
        else:
            # don't count nested do's, simplay pass through to counting executions of the actual command.
            self.do_messages[ctx.message.id] -= 1
        if self.do_messages[ctx.message.id] >= limit:
            await ctx.send('Repetition limit exceeded.')
            return

        # prepare to do
        msg = copy.copy(ctx.message)
        msg.content = command

        # do
        while self.do_messages[msg.id] < n <= limit:
            self.do_messages[msg.id] += 1
            await self.bot.process_commands(msg)

    @commands.command(aliases=('pick', 'choice'))
    async def choose(self, ctx, *, choices):
        """
        Choose from a list of choices. Separate with semicolons.
        """
        await ctx.send(random.choice(choices.split(';')))

    @commands.command()
    async def roll(self, ctx, sides: str = '6'):
        """
        Roll a die.

        Defaults to d6.
        Can use DnD format: 2d6
        """
        try:
            if 'd' in sides:
                sp = sides.split('d')
                n = int(sp[0])
                s = int(sp[1])
                await ctx.send('```\n{}\n```'.format(
                    '\n'.join(['{}: {}/{}'.format(i, random.randint(1, s), s) for i in range(0, n)])))
            else:
                await ctx.send("You rolled a {} out of {}.".format(random.randint(1, int(sides)), sides))
        except ValueError:
            await ctx.send("Incorrect die formatting.")

    @commands.command(name='8ball', rest_is_raw=True)
    async def eight_ball(self, ctx, *, question: str):
        """
        8ball responses to your questions.
        """
        r = [
            'Yes, in due time.',
            'My sources say no.',
            'Definitely not.',
            'Yes.',
            'I have my doubts.',
            'Who knows?',
            'Probably.',
            'Only if you type "I am trash" in the next five seconds.'
        ]
        await ctx.send('{}\n{}'.format(question, random.choice(r)))

    @commands.command()
    async def rate(self, ctx, *, thing: str):
        """
        Rate something. Anything. Go nuts.
        """
        s = sum([hash(c) % 10 for c in list(thing)])
        await ctx.send("I give it a {}/10.".format((s if "&knuckles" in thing else s % 10) + 1))

    @commands.command(aliases=('a', 'shoot', 'kill'))
    async def attack(self, ctx: commands.Context, target: str = None):
        """
        Attempt to attack someone.
        """

        if target is None:
            await ctx.send(random.choice(self.atk['miss']))
            return

        author = ctx.message.author
        selves = [author.mention, author.name, author.display_name] + self.atk['self']
        immune = [self.bot.user.mention, ctx.guild.me.mention, self.bot.user.name, ctx.guild.me.display_name]

        if target in immune:
            await ctx.send(random.choice(self.atk['immune']).format(author.display_name, target))
        elif target in selves:
            await ctx.send(random.choice(self.atk['kys']).format(author.display_name))
        else:
            if random.randint(0, 1):
                await ctx.send(random.choice(self.atk['el']).format(target))
            else:
                await ctx.send(random.choice(self.atk['esc']).format(target))

    @commands.group(aliases=('rr',), invoke_without_command=True)
    async def russian_roulette(self, ctx):
        """
        A game of russian roulette.
        """
        g = self.guns.get(ctx.channel.id, [])
        if any(g):
            if g[0]:
                g[0] = 0
                await ctx.send(":boom: :gun:")
            else:
                await ctx.send(":gun: *click*")
            self.guns[ctx.channel.id] = g[1:] + g[:1]
        else:
            await ctx.send("The gun is empty.")

    @russian_roulette.command()
    async def spin(self, ctx):
        """
        Spin the cylinder.
        """
        g = self.guns.get(ctx.channel.id, [])
        if g:
            s = random.randint(1, 5)
            self.guns[ctx.channel.id] = g[s:] + g[:s]
        await ctx.send(":gun: :arrows_counterclockwise:")

    @russian_roulette.command()
    async def reload(self, ctx, bullets: int):
        """
        Reload the gun with a certain number of bullets.
        """
        if bullets not in range(0, 7):
            await self.bot.say("Slow down there partner.")
            return
        self.guns[ctx.channel.id] = [0, 0, 0, 0, 0, 0]
        while sum(self.guns[ctx.channel.id]) < bullets:
            self.guns[ctx.channel.id][random.randint(0, 5)] = 1
        await ctx.send("There are now {} bullets in the gun.".format(bullets))


def setup(bot):
    bot.add_cog(Toys(bot))
