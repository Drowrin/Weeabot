import re
import aiohttp
import json
from difflib import SequenceMatcher
import traceback

import bs4

import discord
from discord.ext import commands

import utils
import checks


base_url = "https://mywaifulist.moe"


class WaifuData(object):
    """Data structure for waifu data from mywaifulist.moe"""

    detail_fields = ['height', 'weight', 'bust', 'birthday', 'origin', 'hip', 'blood_type']

    __slots__ = (
        'id', 'creator_id', 'name', 'description', 'slug', 'created_at', 'updated_at', 'weight', 'height', 'bust',
        'hip', 'blood_type', 'origin', 'birthday', 'series_id', 'display_picture', 'likes', 'trash',
        'series_name', 'series_url', 'image', 'message'
    )

    @staticmethod
    async def from_slug(slug, session, **data):
        return await WaifuData.from_link(f"{base_url}/waifu/{slug}", session, **data)

    @staticmethod
    async def from_link(url, session, **data):
        async with session.get(url) as r:
            return WaifuData.from_html(await r.text(), **data)

    @staticmethod
    def from_html(html, **data):
        soup = bs4.BeautifulSoup(html, "html.parser")

        try:
            data.update(json.loads(soup.select("#waifu")[0]["waifu"]))
        except IndexError:
            # not passed a valid page
            raise commands.BadArgument("Not found.")

        data['series_name'] = soup.select(".waifu-series a")[0].text
        data['series_url'] = soup.select(".waifu-series a")[0]['href']
        data['image'] = data['display_picture'] or soup.select("img.waifu-display-picture")[0]['src']
        data['birthday'] = data['birthday'].split(" ")[0]

        return WaifuData(**data)

    def __init__(self, **kwargs):
        self.message = None
        for k, v in kwargs.items():
            try:
                setattr(self, k, v)
            except AttributeError:
                print(f"Warning: {k} was passed but not expected.")

    def __repr__(self):
        return f"<WaifuData {self.name}>"

    @property
    def details(self) -> dict:
        return {
            k: getattr(self, k)
            for k in self.detail_fields
            if (lambda x: x and x not in ("0.00", '-0001-11-30 00:00:00', '-0001-11-30'))(getattr(self, k))
        }

    @property
    def percent(self) -> float:
        """Percentage representation of score. +-1 from full negative to full positive."""
        return 2 * (self.likes / (self.likes + self.trash)) - 1

    @property
    def embed(self) -> discord.Embed:
        """The discord.Embed representation of this waifu."""
        if self.likes >= 2*self.trash:
            c = discord.Colour.purple()
        elif self.trash >= 2*self.likes:
            c = discord.Colour.red()
        else:
            c = discord.Colour.blue()

        e = discord.Embed(
            title=self.name,
            description=utils.str_limit('\n'.join([
                f"`+{self.likes} | {self.percent:0.2%} | {self.trash}-`",
                f"[{self.series_name}]({base_url}{self.series_url})",
                self.description
            ]), 2048),
            url=f"{base_url}/waifu/{self.slug}",
            timestamp=discord.utils.parse_time(self.created_at),
            colour=c
        ).set_image(
            url=self.image
        ).set_footer(
            text=f"slug: {self.slug}"
        )

        if self.details:
            e.add_field(
                name="Details",
                value="```{}```".format(utils.remove_leading_space('\n'.join([
                    "".join([
                        f"{k:>{len(max(self.details.keys(), key=len))}}|{v:<{len(max(self.details.values(), key=len))+2}}"
                        for k, v in i
                    ])
                    for i in utils.even_split(self.details.items(), 2)
                ])))
            )

        return e

    async def send(self, ctx):
        """Send the complete message for this waifu."""
        await ctx.bot.send_message(ctx.message.channel, self.message, embed=self.embed)


class WaifuList(object):
    """data structure representing a user list from mywaifulist.moe"""

    __slots__ = ('likes', 'trash')

    @staticmethod
    async def from_id(i, session, **data):
        return await WaifuList.from_link(f"{base_url}/user/{i}", session, **data)

    @staticmethod
    async def from_link(url, session, **data):
        async with session.get(url) as r:
            return WaifuList.from_html(await r.text(), **data)

    @staticmethod
    def from_html(html, **data):
        soup = bs4.BeautifulSoup(html, "html.parser")

        data['likes'] = [w['href'].split('/')[-1] for w in soup.select('#liked .row-fluid .waifu-card-title a')]
        data['trash'] = [w['href'].split('/')[-1] for w in soup.select('#trash .row-fluid .waifu-card-title a')]

        return WaifuList(**data)

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            try:
                setattr(self, k, v)
            except AttributeError:
                print(f"Warning: {k} was passed but not expected.")

    def __repr__(self):
        return f"<WaifuList with {len(self.likes)} likes and {len(self.trash)} trash>"


class MyWaifuList(utils.SessionCog):
    """Commands for mywaifulist.moe"""

    async def get_user(self, i):
        return await WaifuList.from_id(i, self.session)

    async def loose_search(self, term) -> list:
        return await self.search(re.split(r'[ -]', term)[0])

    async def search(self, term) -> list:
        """search for a term."""
        async with self.session.get(f"{base_url}/search/{term}") as r:
            return json.loads(await r.text())

    async def get_waifu(self, name) -> WaifuData:
        """get a waifu by name or slug."""
        try:
            return await WaifuData.from_slug(name, self.session)
        except commands.BadArgument:
            # try search
            try:
                likely_slug = max(
                    await self.loose_search(name),
                    key=lambda x: SequenceMatcher(None, name, x['slug']).ratio()
                )['slug']
                return await WaifuData.from_slug(
                    likely_slug, self.session,
                    message=f"No exact match found. Closest: {likely_slug}"
                )
            except ValueError:
                raise commands.BadArgument("Not found.")

    @commands.group()
    async def waifu(self):
        """waifu commands"""

    @waifu.command(pass_context=True)
    async def details(self, ctx, *, slug_or_name):
        """Get details about a waifu

        The 'slug' is the last part of the url on mywaifulist.moe.
        It will often be the character's name separated by hyphens.

        You can also pass in part of or the whole character name to attempt to get a close match."""
        await (await self.get_waifu(slug_or_name)).send(ctx)

    @waifu.command(aliases=('search',))
    async def find(self, query):
        """See the closest matches to a search query.

        Single word queries tend to work better, though multi-word names work sometimes."""
        await self.bot.say(utils.str_limit('Results: ' + ', '.join([s['slug'] for s in await self.search(query)]), 2048))


def setup(bot):
    bot.add_cog(MyWaifuList(bot))

