import random
import json
import pyimgur
import traceback
import datetime
import re
import math

from typing import Callable
from typing import List

from PIL import Image, ImageFont, ImageDraw, ImageSequence
from os import path
from os import listdir
from os import makedirs
from io import BytesIO
from textwrap import shorten

import discord
from discord.ext import commands

from ._base import base_cog


class Images(base_cog(session=True)):
    """
    Image lookup and manipulation.
    """

    @commands.command(aliases=('b', 'idiot'))
    async def baka(self, ctx: commands.Context, user: str=None):
        """
        ...b-baka
        """
        if user is None:
            user = ctx.author
        else:
            try:
                user = await commands.MemberConverter().convert(ctx, user)
            except commands.BadArgument:
                user = ctx.author

        chosen = random.choice(listdir(path.join('images', 'bakas')))
        props = [int(s) for s in chosen.split('.')[0].split('_')]  # properties of text are stored in filename

        f = ImageFont.truetype("ZinPenKeba-R.otf", props[0])

        t = user.display_name
        t = t[:props[1] - 3] + '...' if len(t) > props[1] else t
        i = 'you idiot...'

        im = Image.open(path.join('images', 'bakas', chosen))
        d = ImageDraw.Draw(im)
        tw, th = d.textsize(t, f)
        iw, ih = d.textsize(i, f)
        d.text((props[2] - (tw // 2), props[3] - (th // 2)), t, (0, 0, 0), font=f)
        d.text((props[4] - (iw // 2), props[5] - (ih // 2)), i, (0, 0, 0), font=f)
        with BytesIO() as fp:
            im.save(fp, 'PNG')
            fp.seek(0)
            file = discord.File(fp, filename='baka.png')
            await ctx.send(
                file=file,
                embed=discord.Embed().set_image(url=f'attachment://{file.filename}')
            )


def setup(bot):
    bot.add_cog(Images(bot))
