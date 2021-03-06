import unicodedata
import random
import copy
import asyncio

import discord
from discord.ext import commands

import utils
import checks


class Pointless(utils.SessionCog):
    """Nothing to see here."""

    def __init__(self, bot: commands.Bot):
        super(Pointless, self).__init__(bot)
        self.oc = 1
        self.do_messages = {}

    async def text_embed(self, message: discord.Message, text: str):
        try:
            await self.bot.say(embed=discord.Embed(
                description=text
            ).set_author(
                name=message.author.display_name,
                icon_url=message.author.avatar_url or message.author.default_avatar_url
            ))
            await self.bot.delete_message(message)
        except discord.HTTPException:
            await self.bot.say("The formatting went too far for discord.")

    async def get_text(self, ctx: commands.Context) -> str:
        t = ctx.invoked_with.join(ctx.message.clean_content.split(ctx.invoked_with)[1:])
        if t:
            return t
        async for m in self.bot.logs_from(ctx.message.channel, limit=1, before=ctx.message):
            await self.bot.delete_message(m)
            if m.clean_content:
                return m.clean_content
            if m.embeds:
                return m.embeds[0]['description']
            raise commands.BadArgument("No suitable text found.")

    @commands.group(name='text', aliases=('t',))
    async def text_command(self):
        """Text transformations."""

    @text_command.command(pass_context=True, aliases=('a',))
    async def aesthetic(self, ctx):
        """AESTHETIC"""
        text = await self.get_text(ctx)
        translated = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ?!\"#$%&\'()*+,-./\\~'
        fullwidth = str.maketrans(translated, ''.join(chr(ord(c) + 0xFEE0) for c in translated))
        await self.text_embed(ctx.message, text.translate(fullwidth))

    @text_command.command(pass_context=True, aliases=('r',))
    async def reverse(self, ctx):
        """esreveR"""
        text = await self.get_text(ctx)
        fmt = "\N{RIGHT-TO-LEFT OVERRIDE}{}\N{LEFT-TO-RIGHT OVERRIDE}"
        await self.text_embed(ctx.message, fmt.format(text))

    @text_command.command(pass_context=True, aliases=('z',))
    async def zalgo(self, ctx):
        """ZALGO"""
        source = (await self.get_text(ctx)).upper()
        zalgo_chars = [chr(i) for i in range(0x0300, 0x036F + 1)]
        zalgo_chars.extend(['\u0488', '\u0489'])
        zalgoized = [letter + ''.join(random.choice(zalgo_chars) for _ in range(random.randint(1, 25)))
                     for letter in source]
        await self.text_embed(ctx.message, ''.join(zalgoized))

    @text_command.command(pass_context=True, aliases=('e',))
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
            await self.bot.say('Repetition limit exceeded.')
            return

        # prepare to do
        msg = copy.copy(ctx.message)
        msg.content = command

        # do
        while self.do_messages[msg.id] < n <= limit:
            self.do_messages[msg.id] += 1
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
