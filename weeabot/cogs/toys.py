import random

import discord
from discord.ext import commands

from ._base import base_cog


class Toys(base_cog()):
    """
    Pointless stuff goes here.
    """

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


def setup(bot):
    bot.add_cog(Toys(bot))
