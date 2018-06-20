import random
import json
import pyimgur
import traceback
import datetime
import re
import math
from io import BytesIO

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
from .. import utils


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

    async def count_booru(self, url, tags):
        params = {'page': 'dapi', 's': 'post', 'q': 'index', 'limit': 0, 'tags': tags}
        async with self.session.get(url + '/index.php', params=params) as r:
            try:
                return int(re.search(r'count="(\d+)"', await r.text()).group(1))
            except AttributeError:
                raise commands.BadArgument("API ERROR")

    async def fetch_booru_image(self, url: str, tags: str, *filters: List[Callable[[dict], bool]], count=None):
        count = count or await self.count_booru(url, tags)
        params = {'page': 'dapi', 's': 'post', 'q': 'index', 'json': 1,
                  'pid': 0 if count <= 100 else random.randint(0, count // 100 - 1), 'tags': tags}
        async with self.session.get(url + '/index.php', params=params) as r:
            if r.status != 200:
                return f'Something went wrong. Error {r.status}'
            t = await r.text()
            try:
                ims = json.loads(t)
            except json.JSONDecodeError:
                return "API error"
            filtered = [i for i in ims if not any(f(i) for f in filters)]

            if len(filtered):
                return random.choice(filtered)
            else:
                return "No results"

    async def post_booru_image(self, ctx, url: str, tags: str, *filters: List[Callable[[dict], bool]]):
        """post the returned image from a booru, or it's error message."""
        tmp = await ctx.send("getting image from booru")
        im = await self.fetch_booru_image(url, tags, *filters)
        if isinstance(im, dict):
            count = await self.count_booru(url, tags)
            if 'file_url' in im:
                img_url = f'{url.split(":")[0]}:{im["file_url"]}'
            else:
                img_url = f'{url}/images/{im["directory"]}/{im["image"]}'
            e = discord.Embed(
                title='This Image',
                description=shorten(im['tags'].replace('_', r'\_').replace(' ', ', '), 2048, placeholder='...'),
                url=f'{url}/index.php?page=post&s=view&id={im["id"]}'
            ).set_author(
                name=f"{count} Images with these tags",
                url=f"{url}/index.php?page=post&s=list&tags={'+'.join(tags.split())}"
            ).set_image(
                url=img_url
            )
            try:
                await tmp.edit(content=None, embed=e)
            except discord.HTTPException as e:
                await tmp.edit(content=f'HTTP Error: {e.code}')
        else:
            await tmp.edit(content=im)

    @commands.group(invoke_without_command=True)
    async def safebooru(self, ctx, * tags: str):
        """
        Get an image from safebooru based on tags.
        """
        await self.post_booru_image(ctx, "http://safebooru.com", tags, lambda im: im['rating'] == 'e')

    @commands.group(invoke_without_command=True)
    @commands.is_nsfw()
    async def gelbooru(self, ctx, *, tags: str):
        """
        Get an image from gelbooru based on tags.
        """
        await self.post_booru_image(ctx, "http://gelbooru.com", tags)

    @commands.group(invoke_without_command=True)
    @commands.is_nsfw()
    async def rule34(self, ctx, *, tags: str):
        """
        Get an image from rule34.xxx based on tags.
        """
        await self.post_booru_image(ctx, "http://rule34.xxx", tags)

    async def post_booru_collage(self, ctx, url: str, tags: str, *filters: List[Callable[[dict], bool]]):
        """
        Make a collage from a booru.
        """
        if await self.count_booru(url, tags) < 5:
            raise commands.BadArgument("Not enough images with those tags. Need at least 5 static images.")

        tmp = await ctx.send(f"Collecting images")

        async def gen():
            total_images = 0
            errors = 0

            while True:
                im = await self.fetch_booru_image(url, tags, *filters)
                if isinstance(im, str):
                    return

                if 'file_url' in im:
                    img_url = f'{url.split(":")[0]}:{im["file_url"]}'
                else:
                    img_url = f'{url}/images/{im["directory"]}/{im["image"]}'
                with await utils.download_fp(self.session, img_url) as fp:
                    try:
                        v = fp
                        iv = Image.open(v)
                        yield iv
                    except (OSError, ValueError) as e:
                        if errors < 5:
                            await self.bot.say("```py\n{}\n{}\n{}```".format(
                                e, img_url,
                                f'{url}/index.php?page=post&s=view&id={im["id"]}'
                            ))
                            errors += 1
                        else:
                            ctx.send('Too many errors. Try again later or with different tags.')
                            return

                total_images += 1
                await tmp.edit(content=f"Collecting images {total_images}")

        with await self.make_collage(gen) as f:
            file = discord.File(f, filename='collage.png')
            await ctx.send(
                content=None, file=file,
                embed=discord.Embed().set_image(url=f'attachment://{file.filename}')
            )

    @safebooru.command(name='collage')
    async def booru_collage(self, ctx, *, tags: str):
        """
        Get an image collage from safebooru based on tags.
        """
        await self.post_booru_collage(ctx, "http://safebooru.org", tags, lambda im: im['rating'] == 'e')

    @gelbooru.command(name='collage')
    @commands.is_nsfw()
    async def gelbooru_collage(self, ctx, *, tags: str):
        """
        Get an image collage from gelbooru based on tags.
        """
        await self.post_booru_collage(ctx, "http://gelbooru.com", tags)

    @rule34.command(name='collage')
    @commands.is_nsfw()
    async def rule34xxx_collage(self, ctx, *, tags: str):
        """
        Get an image from rule34.xxx based on tags.
        """
        await self.post_booru_collage(ctx, "http://rule34.xxx", tags)

    async def make_collage(self, gen) -> BytesIO:
        """
        Make a collage out of the images returned by the async generator.
        """
        # approximate desired values
        width = 1000
        height = 1000
        rows = 3
        line_width = 2

        # calculate other values
        row_height = height / rows
        min_row_width = width * 2 / 3

        # create image jagged array. (row width, images)
        image_array = [[0, []]]
        async for im in gen():
            def process(pi):
                # make new row if current is too large and we can make more rows
                if image_array[-1][0] >= width:
                    if len(image_array) == rows:
                        return True
                    image_array.append([0, []])

                # load and perform initial resize on image.
                pscale = row_height / pi.size[1]
                pi = pi.resize([int(d * pscale) for d in pi.size], Image.ANTIALIAS)
                pi.thumbnail((width, row_height))

                # add to image array
                image_array[-1][0] += pi.size[0] + (line_width if len(image_array[-1][1]) else 0)
                image_array[-1][1].append(pi)

            if await self.bot.loop.run_in_executor(None, process, im):
                break

        def fit_to_image():
            # remove last row if below minimum.
            if image_array[-1][0] < min_row_width:
                del image_array[-1]

            # fit each row to width
            for i, (row_width, ims) in enumerate(image_array):
                lines_amount = line_width * (len(ims) - 1)
                if row_width != width:
                    scale = width / (row_width - lines_amount)
                    image_array[i][1] = [fi.resize([int(d * scale) for d in fi.size], Image.ANTIALIAS) for fi in ims]

            # get the actual output height
            out_height = sum(ims[1][0].size[1] for ims in image_array) + ((len(image_array) - 1) * line_width)

            # create new Image object
            image = Image.new('RGB', (width, int(out_height)))

            # draw images on output image
            y = 0
            for _, ims in image_array:
                x = 0
                for i in ims:
                    image.paste(i, (x, y))
                    x += i.size[0] + line_width
                y += ims[0].size[1] + line_width

            fp = BytesIO()
            image.save(fp, 'PNG')
            fp.seek(0)
            return fp

        return await self.bot.loop.run_in_executor(None, fit_to_image)

    @commands.command(pass_context=True, name='collage')
    async def _image_collage(self, ctx: commands.Context, *tags):
        """
        Generate a collage from images in a tag.
        """
        async def gen():
            stubs = await self.bot.db.get_stubs(ctx.guild, *tags, limit=30, force_images=True)
            images = [s.image for s in stubs]

            if len(images) < 5:
                raise commands.BadArgument(message="Not enough images in that tag. Need at least 5 static images.")

            for i in images:
                async with self.session.get(i) as resp:
                    imagedata = BytesIO(await resp.read())
                    imagedata.seek(0)
                im = Image.open(imagedata)
                yield im

        # processing can take a while, so we type to acknowledge the command and run it in and executor.
        async with ctx.typing():
            with await self.make_collage(gen) as f:
                file = discord.File(f, filename='collage.png')
                await ctx.send(file=file, embed=discord.Embed().set_image(url=f'attachment://{file.filename}'))


def setup(bot):
    bot.add_cog(Images(bot))
