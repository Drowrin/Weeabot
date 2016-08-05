# noinspection PyUnresolvedReferences
import discord
import unicodedata
# noinspection PyUnresolvedReferences
import random
import copy

# noinspection PyUnresolvedReferences
from discord.ext import commands
from cleverbot import Cleverbot

from utils import *


class Pointless(SessionCog):
    """Nothing to see here."""

    def __init__(self, bot):
        super(Pointless, self).__init__(bot)
        self.cleverbot = Cleverbot()
        self.oc = 1
        self.services = {
            "Conversation": "Tag the bot at the beginning of a message to have a conversation with it.",
            "Reactions": "The bot will react to these words: {}".format(', '.join(self.bot.content.reactions.keys()))
        }
    
    @commands.group(name='text', aliases=('t',))
    async def text_command(self):
        """Text transformations."""
    
    @text_command.command(pass_context=True, aliases=('a',))
    async def aesthetic(self, ctx):
        """AESTHETIC"""
        text = ctx.invoked_with.join(ctx.message.clean_content.split(ctx.invoked_with)[1:])
        translated = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ?!\"#$%&\'()*+,-./\\~'
        fullwidth = str.maketrans(translated, ''.join(chr(ord(c) + 0xFEE0) for c in translated))
        await self.bot.say(text.translate(fullwidth))

    @text_command.command(pass_context=True, aliases=('z',))
    async def zalgo(self, ctx):
        """ZALGO"""
        source = ctx.invoked_with.join(ctx.message.clean_content.split(ctx.invoked_with)[1:]).upper()
        zalgo_chars = [chr(i) for i in range(0x0300, 0x036F + 1)]
        zalgo_chars.extend(['\u0488', '\u0489'])
        random_extras = [chr(i) for i in range(0x1D023, 0x1D046)]
        source = ''.join([s + random.choice(random_extras) if random.randint(1, 5) == 1 else '' for s in source])
        zalgoized = [letter + ''.join(random.choice(zalgo_chars) for _ in range(random.randint(1, 25)))
                     for letter in source]
        await self.bot.say(''.join(zalgoized))

    @text_command.command(pass_context=True, aliases=('e',))
    async def emoji(self, ctx):
        """EMOJI"""
        text = ctx.invoked_with.join(ctx.message.clean_content.split(ctx.invoked_with)[1:]).upper()
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
        await self.bot.say('      '.join(text.translate(emoji).split()))

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

    @commands.command(aliases=('no',))
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
        banned = ['~req']
        if any([x in command for x in banned]):
            await self.bot.say("That command may not be used.")
            return
        if n > 5:
            await self.bot.say("Too many times.")
            return
        msg = copy.copy(ctx.message)
        msg.content = command
        for i in range(n):
            await self.bot.process_commands(msg)

    async def on_message(self, message):
        if message.author.bot or is_command_of(self.bot, message):
            return
        for prompt in self.bot.content.reactions:
            if prompt in message.content.lower():
                r = self.bot.content.reactions[prompt][1]
                i = get_random_file(path.join('images', 'collections'), self.bot.content.reactions[prompt][0])
                if i is None:
                    await self.bot.send_message(message.channel, r)
                else:
                    await self.bot.send_file(message.channel, i, content=r)
        if "\N{OK HAND SIGN}" in message.content:
            self.oc += 1
            if not self.oc % 3:
                await self.bot.send_message(message.channel, "\N{OK HAND SIGN}")
                return
        if message.content.startswith(message.server.me.mention if message.server else self.bot.user.mention):
            await self.bot.send_message(message.channel, "{} {}".format(
                message.author.mention, self.cleverbot.ask(message.content[(len(self.bot.user.mention) + 1):])))
            return


def setup(bot):
    bot.add_cog(Pointless(bot))
