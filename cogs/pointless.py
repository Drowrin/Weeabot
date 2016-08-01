import discord
import unicodedata
import random
import aiohttp
import copy

from discord.ext import commands
from cleverbot import Cleverbot
from utils import *


def _insert_randoms(text):
    random_extras = [unichr(i) for i in range(0x1D023, 0x1D045 + 1)]
    newtext = []
    for char in text:
        newtext.append(char)
        if random.randint(1, 5) == 1:
            newtext.append(random.choice(random_extras))
    return u''.join(newtext)


def _is_narrow_build():
    try:
        unichr(0x10000)
    except ValueError:
        return True
    return False


class Pointless(SessionCog):
    """Nothing to see here."""

    def __init__(self, bot):
        super(Pointless, self).__init__(bot)
        self.cleverbot = Cleverbot()
        self.oc = 1

    @text_transform_command()
    async def aesthetic(self, *, text):
        """AESTHETIC"""
        translated = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ?!\"#$%&\'()*+,-./\\~'
        fullwidth = str.maketrans(translated, ''.join(chr(ord(c) + 0xFEE0) for c in translated))
        return text.translate(fullwidth)

    @text_transform_command()
    async def zalgo(self, *, text):
        """ZALGO"""
        zalgo_chars = [chr(i) for i in range(0x0300, 0x036F + 1)]
        zalgo_chars.extend([u'\u0488', u'\u0489'])
        source = text.upper()
        if not _is_narrow_build:
            source = _insert_randoms(source)
        zalgoized = []
        for letter in source:
            zalgoized.append(letter)
            zalgo_num = random.randint(0, 50) + 1
            for _ in range(zalgo_num):
                zalgoized.append(random.choice(zalgo_chars))
        response = random.choice(zalgo_chars).join(zalgoized)
        return response

    @text_transform_command()
    async def emoji(self, *, text):
        """EMOJI"""
        text = text.upper()
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
        return '        '.join(text.translate(emoji).split())

    @commands.command()
    async def jojoke(self):
        """ゴ"""
        await self.bot.say("""
        ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ
        ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ
        ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ

        ＴＨＩＳ ＭＵＳＴ ＢＥ ＴＨＥ ＷＯＲＫ ＯＦ ＡＮ ＥＮＥＭＹ 「ＳＴＡＮＤ」！！

        ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ
        ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ
        ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ ゴ
        """)

    @commands.command()
    async def charname(self, *, char: str):
        """Look up the name of a char"""
        char = char.replace(' ', '')
        await self.bot.say('\n'.join(unicodedata.name(c, 'Name not found.') for c in char))

    @commands.command(pass_context=True, aliases=('fuck', 'eff'))
    async def foaas(self, ctx, *, name: str):
        """Express your anger."""
        headers = {"accept": "text/plain"}
        d = [
            "off",
            "you",
            "donut",
            "shakespeare",
            "linus",
            "king",
            "chainsaw",
            "outside",
            "madison",
            "yoda",
            "nugget",
            "bus",
            "shutup",
            "gfy",
            "back",
            "keep"]
        url = "https://www.foaas.com/{}/{}/{}".format(random.choice(d), name, ctx.message.author.mention)
        async with self.session.get(url, headers=headers) as r:
            await self.bot.say(await r.text())

    @commands.command()
    async def yes(self):
        await self.bot.say("yes")

    @commands.command(pass_context=True)
    async def rip(self, ctx, ripped: str=None):
        """RIP"""
        if ripped is None:
            ripped = ctx.message.author.display_name
        elif ripped == 'me':
            ripped = ctx.message.author.display_name
        else:
            try:
                ripped = commands.MemberConverter(ctx, ripped).convert().display_name
            except commands.BadArgument:
                pass
        await self.bot.say('<http://ripme.xyz/{}>'.format(ripped))

    @commands.command(pass_context=True)
    async def do(self, ctx, n: int, *, command):
        """Repeat a command up to 5 times."""
        if n > 5:
            raise commands.BadArgument("Too many times.")
        msg = copy.copy(ctx.message)
        msg.content = command
        for i in range(n):
            await self.bot.process_commands(msg)

    async def on_message(self, message):
        if message.author.bot or is_command_of(self.bot, message):
            return
        if "\N{OK HAND SIGN}" in message.content:
            self.oc += 1
            if not self.oc % 3:
                await self.bot.send_message(message.channel, "\N{OK HAND SIGN}")
                return
        if message.content.startswith(self.bot.user.mention):
            await bot.send_message(message.channel, message.author.mention + ": " +
                                   self.cleverbot.ask(message.content[len(self.bot.user.mention) + 1:]))
            return


def setup(bot):
    bot.add_cog(Pointless(bot))
