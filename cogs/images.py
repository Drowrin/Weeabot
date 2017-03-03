import random
import json
import pyimgur
import traceback
import datetime
import re

from typing import Callable
from typing import List

from PIL import Image, ImageFont, ImageDraw
from os import path
from os import listdir
from os import makedirs
from io import BytesIO

import discord
from discord.ext import commands

import utils
import checks


from cogs.tagsystem import TagItem
from cogs.requestsystem import request


class Images(utils.SessionCog):
    """Image related commands."""

    def __init__(self, bot):
        super(Images, self).__init__(bot)
        self.memes = bot.content.memes
    
    async def get_random_image(self, album_id):
        """Get a random image from an imgur album."""
        image_list = (await self.bot.loop.run_in_executor(self.bot.imgur.get_album(album_id))).images
        return random.choice(image_list).link

    async def baka_image(self, ctx, t: str):
        t = t[:7] + '...' if len(t) > 10 else t
        i = 'you idiot...'
        f = ImageFont.truetype("ZinPenKeba-R.otf", 12)
        im = Image.open(path.join('images', 'collections', 'pout', 'baka.png'))
        d = ImageDraw.Draw(im)
        tw, th = d.textsize(t, f)
        iw, ih = d.textsize(i, f)
        d.text((250 - (tw // 2), 125 - (th // 2)), t, (0, 0, 0), font=f)
        d.text((255 - (iw // 2), 150 - (ih // 2)), i, (0, 0, 0), font=f)
        with BytesIO() as fp:
            im.save(fp, 'PNG')
            fp.seek(0)
            await self.bot.send_file(ctx.message.channel, fp, filename='baka.png')

    @commands.command(pass_context=True, aliases=('b',))
    async def baka(self, ctx, user: str=None):
        """...Baka"""
        if user is None:
            t = ctx.message.author.display_name
        else:
            try:
                t = commands.MemberConverter(ctx, user).convert().display_name
            except commands.BadArgument:
                t = user
        await self.baka_image(ctx, t)

    @commands.command()
    @checks.is_owner()
    async def convert_images_to_tag(self):
        """Use to convert preexisting image libraries to the tag system."""
        col_count = 0
        tag_count = 0
        for col in listdir(path.join('images', 'collections')):
            coldir = path.join('images', 'collections', col)
            for im in listdir(coldir):
                # noinspection PyBroadException
                try:
                    t = TagItem(
                        self.bot.user.id,
                        str(datetime.datetime.fromtimestamp(int(path.getmtime(path.join(coldir, im))))),
                        [col],
                        text=None,
                        image=path.join(coldir, im)
                    )
                    self.bot.tag_map[col] = t
                    tag_count += 1
                except:
                    await self.bot.say(traceback.format_exc())
            col_count += 1
        await self.bot.say("Imported {} items into {} tags. :ok_hand:".format(tag_count, col_count))

    @commands.group(pass_context=True, invoke_without_command=True, aliases=('i',))
    async def image(self, ctx, category: str, filetype: str=None):
        """Image commands.

        Get an image from a category or search through several online services with subcommands."""

        def predicate(tag: TagItem):
            if tag.image is None:
                return False
            if filetype is None:
                return True
            if tag.image.endswith(filetype):
                return True
            return False

        try:
            t = self.bot.tag_map.get(ctx.message, category, predicate=predicate)
        except KeyError:
            t = None
        if t is None:
            await self.bot.say("None found.")
            return
        await t.run(ctx)

    @image.command(pass_context=True, name='add')
    @request()
    @checks.is_owner()
    @checks.is_moderator()
    async def _image_add(self, ctx, collection: str, *link: str):
        """Request to add an image to a category.

        If you are not the owner, sends a request to them.
        The owner can add images and also new categories using this command."""
        links = link or [x['url'] for x in ctx.message.attachments]
        if not links:
            raise commands.BadArgument('Invalid Usage: No images.')
        coldir = path.join('images', 'collections')
        if collection not in listdir(coldir):
            if await self.bot.confirm("That collection doesn't exist, add it?", self.bot.owner):
                makedirs(path.join(coldir, collection))
                await self.bot.notify("Added collection: {}".format(collection))
            else:
                return
        for link in links:
            if '//imgur.com/' in link:
                link = self.bot.imgur.get_image(link.split('/')[-1]).link
            name = "{}.{}".format(str(hash(link[-10:])), link.split('.')[-1])
            if name in listdir(path.join(coldir, collection)):
                await self.bot.notify("{} already existed, adding as temp. Correct soon so it isn't lost".format(name))
                name = 'temp.png'
            try:
                await utils.download(self.session, link, path.join(coldir, collection, name))
                t = TagItem(ctx.message.author.id, str(ctx.message.timestamp), [collection],
                            image=path.join(coldir, collection, name))
                self.bot.tag_map[collection] = t
                await t.run(ctx)
            except OSError:
                await self.bot.notify(
                    "Invalid link. Make sure it points directly to the file and ends with a valid file extension.")

    @image.command(pass_context=True, name='add_album')
    @request()
    async def _add_album(self, ctx, link: str, *collections):
        """Add all the images in an imgur album.

        The link should be to a valid imgur album or gallery album.
        After that you may list multiple collections to put each image in."""
        # input checking
        if len(collections) == 0:
            await self.bot.say("No tags given.")
            return
        a = self.bot.imgur.get_at_url(link)
        if not isinstance(a, pyimgur.Album):
            await self.bot.say('Not a valid imgur album.')
            return

        # initial response
        m = await self.bot.say(f'Getting {len(a.images)} images...')

        # add all images
        for im in a.images:
            link = im.link
            n = "{}.{}".format(str(hash(link[-10:])), link.split('.')[-1])
            await utils.download(self.session, link, path.join('images', n))
            i_path = path.join('images', n)

            t = TagItem(ctx.message.author.id, str(ctx.message.timestamp), collections, image=i_path)
            for name in collections:
                self.bot.tag_map[name] = t
        await self.bot.edit_message(m, f'Added {len(a.images)} images to {",".join(collections)}')

    @image.command(name='list')
    async def _image_list(self):
        """Get a list of all the categories and reactions."""
        r_list = [x[0] for x in self.bot.content.reactions.values() if x[0] is not None]
        c_list = [x for x in listdir(path.join('images', 'collections')) if x not in r_list]
        await self.bot.say("List of categories: {}\nList of reactions: {}".format(", ".join(c_list), ", ".join(r_list)))
        
    async def fetch_booru_image(self, url: str, tags: str, *filters: List[Callable[[dict], bool]]):
        tmp = await self.bot.say("getting image from booru")
        params = {'page': 'dapi', 's': 'post', 'q': 'index', 'limit': 0, 'tags': tags}
        async with self.session.get(url + '/index.php', params=params) as r:
            count = int(re.search(r'count="(\d+)"', await r.text()).group(1))
        if count == 0:
            await self.bot.edit_message(tmp, "No results")
            return
        params = {'page': 'dapi', 's': 'post', 'q': 'index', 'json': 1, 'pid': 0 if count <= 100 else random.randint(0, count // 100 - 1), 'tags': tags}
        async with self.session.get(url + '/index.php', params=params) as r:
            if r.status != 200:
                await self.bot.edit_message(tmp, f'Something went wrong. Error {r.status}')
                return
            t = await r.text()
            ims = json.loads(t)
            filtered = [i for i in ims if not any(f(i) for f in filters)]

            if len(filtered):
                im = random.choice(filtered)
                e = discord.Embed(
                    title='This Image',
                    description=utils.str_limit(im['tags'].replace('_', r'\_').replace(' ', ', '), 2048),
                    url=f'{url}/index.php?page=post&s=view&id={im["id"]}'
                ).set_author(
                    name=f"{count} Images with these tags",
                    url=f"{url}/index.php?page=post&s=list&tags={'+'.join(tags.split())}"
                ).set_image(
                    url=f'{url}/images/{im["directory"]}/{im["image"]}'
                )
                try:
                    await self.bot.edit_message(tmp, '\N{ZERO WIDTH SPACE}', embed=e)
                except discord.HTTPException as e:
                    await self.bot.edit_message(tmp, f'HTTP Error: {e.code}')
            else:
                await self.bot.edit_message(tmp, "No results")

    @image.command(name='booru')
    async def _booru(self, *, tags: str):
        """Get an image from safebooru based on tags."""
        await self.fetch_booru_image("http://safebooru.org", tags, lambda im: im['rating'] == 'e')

    @image.command(name='gelbooru')
    @checks.has_tag("lewd")
    async def _gelbooru(self, *, tags: str):
        """Get an image from gelbooru based on tags."""
        await self.fetch_booru_image("http://gelbooru.com", tags)

    @image.command(name='rule34xxx')
    @checks.has_tag('lewd')
    async def _rule34xxx(self, *, tags: str):
        """Get an image from rule34.xxx based on tags."""
        await self.fetch_booru_image("http://rule34.xxx", tags)
              
    @image.command(pass_context=True, name='reddit', aliases=('r',))
    async def _r(self, ctx, sub: str, window: str='month'):
        """Get an image from a subreddit.

        Optional argument is a time window following reddit's time windows."""
        tmp = await self.bot.say("getting image from r/%s" % sub)
        gal = self.bot.imgur.get_subreddit_gallery(sub, sort='top', window=window, limit=50)
        if len(gal) <= 1:
            await self.bot.edit_message(tmp, 'no images found at r/%s. did you spell it right?' % sub)
            return
        im = random.choice(gal)
        if im is pyimgur.Album:
            im = await self.bot.loop.run_in_executor(self.bot.imgur.get_image(self.get_random_image(im.id)))
        if im.is_nsfw and not checks.tagged(ctx, 'lewd'):
            await self.bot.edit_message(tmp, "no ecchi.")
            return
        await self.bot.edit_message(tmp, "{0.title}\n{0.link}".format(im))

    @image.command(pass_context=True, name='collage', aliases=('c',))
    async def _image_collage(self, ctx, name):
        """Generate a collage from images in a tag."""
        types = ('.png', '.jpg', '.jpeg')

        def process(fp):
            # get list of image
            try:
                tags = self.bot.tag_map.get_items(name, pred=lambda i: i.image and i.image.endswith(types))[:]
                random.shuffle(tags)
                images = [i.image for i in tags]
            except KeyError:
                raise commands.BadArgument("Key not found.")

            if len(images) < 5:
                raise commands.BadArgument("Not enough images in that tag. Need at least 5 static images.")

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
            for fn in images:
                # make new row if current is too large and we can make more rows
                if image_array[-1][0] >= width:
                    if len(image_array) == rows:
                        break
                    image_array.append([0, []])

                # load and perform initial resize on image.
                i = Image.open(fn)
                scale = row_height / i.size[1]
                i = i.resize([int(d * scale) for d in i.size], Image.ANTIALIAS)
                i.thumbnail((width, row_height))

                # add to image array
                image_array[-1][0] += i.size[0] + (line_width if len(image_array[-1][1]) else 0)
                image_array[-1][1].append(i)

            # remove last row if below minimum.
            if image_array[-1][0] < min_row_width:
                del image_array[-1]

            # fit each row to width
            for i, (row_width, ims) in enumerate(image_array):
                lines_amount = line_width * (len(ims) - 1)
                if row_width != width:
                    scale = width / (row_width - lines_amount)
                    image_array[i][1] = [im.resize([int(d * scale) for d in im.size], Image.ANTIALIAS) for im in ims]

            # get the actual output height
            out_height = sum(ims[1][0].size[1] for ims in image_array) + ((len(image_array) - 1) * line_width)

            # create new Image object
            image = Image.new('RGB', (width, int(out_height)))

            # draw images on output image
            y = 0
            for _, ims in image_array:
                x = 0
                for im in ims:
                    image.paste(im, (x, y))
                    x += im.size[0] + line_width
                y += ims[0].size[1] + line_width

            image.save(fp, 'PNG')
            fp.seek(0)

        # processing can take a while, so we type to acknowledge the command and run it in and executor.
        await self.bot.type()
        with BytesIO() as f:
            await self.bot.loop.run_in_executor(None, lambda: process(f))
            await self.bot.upload(f, filename=f'{name}_collage.png')

    @commands.group(pass_context=True, invoke_without_command=True)
    async def meme(self, ctx, name: str, *, c: str=""):
        """Choose an image and text to add to the image."""
        if ctx.invoked_subcommand is None:
            if name not in self.memes.keys():
                await self.bot.say(name + " not found.")
                return
            if len(c) <= 0:
                await self.bot.say(self.memes[name])
                return
            cs = c.split()
            tt = ' '.join(cs[:len(cs) // 2])
            tb = ' '.join(cs[len(cs) // 2:])
            replacements = [["-", "--"], ["_", "__"], ["?", "~q"], ["%", "~p"], [" ", "%20"], ["''", "\""]]
            for r in replacements:
                tt = tt.replace(r[0], r[1])
                tb = tb.replace(r[0], r[1])
            with await utils.download_fp(self.session, "http://memegen.link/custom/{0}/{1}.jpg?alt={2}".format(
                    tt, tb, self.memes[name])) as fp:
                await self.bot.upload(fp, filename='meme.jpg')

    @meme.command(name='list')
    async def _meme_list(self):
        """Lists all available templates."""
        await self.bot.say('Available Templates: ' + ', '.join(self.memes.keys()))

    @meme.command(name='add')
    @request()
    async def _meme_add(self, name: str, link: str):
        """Add a template to the collection. Can't be GIF"""
        if '.gif' in link[-5:]:
            await self.bot.say("The image can not be a gif.")
            return
        if name in self.memes.keys():
            await self.bot.say("{} already taken.".format(name))
            return
        self.memes[name] = link
        self.bot.content.memes = self.memes
        await self.bot.content.save()
        await self.bot.say('Added {}'.format(name))


def setup(bot):
    bot.add_cog(Images(bot))
