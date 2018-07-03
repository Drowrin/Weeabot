from PIL import Image, ImageFont, ImageDraw
import moviepy.editor
import numpy
import textwrap

import discord
from discord.ext import commands

from ._base import base_cog


class Spoilers(base_cog()):
    """
    Mark messages as spoilers and hide them.
    """

    @commands.command()
    async def spoiler(self, ctx: commands.Context, topic: str, *, message: str):
        """
        Send a spoiler message and hide it.
        """
        width = 300
        font_size = 12
        s_offset = 50
        e_offset = 35

        m: discord.Message = ctx.message
        await m.delete()  # immediately delete the message so it isn't left up while processing

        w = textwrap.wrap(message, 1.7*width/font_size)
        lines = len(w)
        message = '\n'.join(w)

        font = ImageFont.truetype('NimbusSanL-Reg.otf', font_size)

        def textframe(s: str):
            f = Image.new("RGBA",
                          (width, (font_size*lines)+s_offset+e_offset),
                          (0, 0, 0, 255))
            draw = ImageDraw.Draw(f)
            draw.text((20, s_offset), s, (255, 255, 255), font)
            return moviepy.editor.ImageClip(numpy.array(f))

        clip = moviepy.editor.concatenate_videoclips([
            textframe(topic).set_duration(.1),
            textframe(message).set_duration(.1)
        ])

        clip.write_videofile('tmp.mp4', fps=30)

        d = discord.File('tmp.mp4', filename='SPOILERS.mp4')
        await ctx.send(
            content=f'{ctx.author.mention} wrote spoilers about {topic}. Click play to read them.',
            file=d
        )


def setup(bot):
    bot.add_cog(Spoilers(bot))
