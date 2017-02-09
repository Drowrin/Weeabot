import unicodedata
import random
import copy
import re
import asyncio

from discord.ext import commands
from cleverbot import Cleverbot

import utils
import checks


class Pointless(utils.SessionCog):
    """Nothing to see here."""

    def __init__(self, bot: commands.Bot):
        super(Pointless, self).__init__(bot)
        self.cleverbot = Cleverbot('weeabotpointless')
        self.oc = 1
        self.services = {
            "Conversation": "Tag the bot at the beginning of a message to have a conversation with it."
        }

    @commands.group(name='text', aliases=('t',))
    async def text_command(self):
        """Text transformations."""

    @text_command.command(pass_context=True, aliases=('a',))
    async def aesthetic(self, ctx):
        """AESTHETIC"""
        text = ctx.invoked_with.join(ctx.message.clean_content.split(ctx.invoked_with)[1:])
        if len(text) == 0:
            return
        translated = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ?!\"#$%&\'()*+,-./\\~'
        fullwidth = str.maketrans(translated, ''.join(chr(ord(c) + 0xFEE0) for c in translated))
        await self.bot.say(text.translate(fullwidth))

    @text_command.command(aliases=('r',))
    async def reverse(self, *, text: str):
        """esreveR"""
        # noinspection PyUnresolvedReferences
        await self.bot.say("\N{RIGHT-TO-LEFT OVERRIDE}{}\N{LEFT-TO-RIGHT OVERRIDE}".format(text))

    @text_command.command(pass_context=True, aliases=('z',))
    async def zalgo(self, ctx):
        """ZALGO"""
        source = ctx.invoked_with.join(ctx.message.clean_content.split(ctx.invoked_with)[1:]).upper()
        if len(source) == 0:
            return
        zalgo_chars = [chr(i) for i in range(0x0300, 0x036F + 1)]
        zalgo_chars.extend(['\u0488', '\u0489'])
        zalgoized = [letter + ''.join(random.choice(zalgo_chars) for _ in range(random.randint(1, 25)))
                     for letter in source]
        await self.bot.say(''.join(zalgoized))

    @text_command.command(pass_context=True, aliases=('e',))
    async def emoji(self, ctx):
        """EMOJI"""
        text = ctx.invoked_with.join(ctx.message.clean_content.split(ctx.invoked_with)[1:]).upper()
        if len(text) == 0:
            return
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
        banned = [f'{self.bot.command_prefix}req', f'{self.bot.command_prefix}do']
        if any([x in command for x in banned]):
            await self.bot.say(f"That command may not be used in {self.bot.command_prefix}do.")
            return
        if n > 5:
            await self.bot.say("Too many times.")
            return
        msg = copy.copy(ctx.message)
        msg.content = command
        for i in range(n):
            await self.bot.process_commands(msg)

    @commands.command(pass_context=True)
    @checks.is_owner()
    async def overload(self, ctx, tag):
        """Overload a tag's use."""
        msg = copy.copy(ctx.message)
        msg.content = '~' + tag
        for i in range(25):
            await self.bot.process_commands(msg)

    async def on_message(self, message):
        if message.author.bot or utils.is_command_of(self.bot, message) or message.channel.is_private:
            return

        if message.server.me in message.mentions:
            # conversation with the bot
            if 'thank' in message.content.lower() or 'thx' in message.content.lower():
                await self.bot.send_message(message.channel, "You're welcome {}".format(random.choice(self.bot.content.emoji)))
            else:
                c = self.cleverbot.ask(message.clean_content)
                await self.bot.send_message(message.channel, f"{message.author.mention} {c}")
        else:
            if "\N{OK HAND SIGN}" in message.content:
                self.oc += 1
                if not self.oc % 3:
                    await self.bot.send_affirmative(message)
                    return

    @commands.command(pass_context=True)
    @checks.is_owner()
    async def typing(self, ctx):
        while True:
            await self.bot.send_typing(ctx.message.channel)
            await asyncio.sleep(10)


def setup(bot):
    bot.add_cog(Pointless(bot))
