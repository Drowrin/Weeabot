import re
import aiohttp
import functools
from datetime import datetime

import bs4

import discord
from discord.ext import commands

import utils
import checks


class CacheData:
    """Helper data structure for caching data from lodestone."""

    def __init__(self, data, last_updated: datetime=None, timeout: int=1800):
        self.last_updated = last_updated or datetime.now()
        self.timeout = timeout  # initial value of .5 hours
        self.data = data

    @property
    def is_valid(self):
        return (datetime.now() - self.last_updated).seconds < self.timeout


def lazy_property(default="ERROR", name: str=None):
    """
    default is what is returned when an exception occurs. If callable, is called on self.
    name overrides the name pulled from the function name if given.
    """
    def wrapper(func):
        n = f'_{name or func.__name__}'

        @property
        @functools.wraps(func)
        def prop(self):
            val = getattr(self, n)
            if val is None:
                try:
                    val = func(self)
                except:
                    val = default(self) if callable(default) else default
                setattr(self, n, val)
            return val

        return prop

    return wrapper


class CharacterData(object):
    """Data structure for character information on Lodestone. Parses from html."""

    def __init__(self, **kwargs):
        if 'html' in kwargs:
            self.soup = bs4.BeautifulSoup(kwargs['html'], "html.parser")

        self._name = kwargs.get('name')
        self._server = kwargs.get('server')
        self._title = kwargs.get('title')
        self._race = kwargs.get('race')
        self._clan = kwargs.get('clan')
        self._gender = kwargs.get('gender')
        self._grand_company = kwargs.get('grand_company')
        self._free_company = kwargs.get('free_company')
        self._classes = kwargs.get('classes')
        self._image_full = kwargs.get('image_full')
        self._image_face = kwargs.get('image_face')

    @lazy_property()
    def name(self):
        return self.soup.find('p', class_='frame__chara__name').text

    @lazy_property()
    def server(self):
        return self.soup.find('p', class_='frame__chara__world').text

    @lazy_property(default=None)
    def title(self):
        return self.soup.find('p', class_='frame__chara__title').text

    @lazy_property()
    def race(self):
        block = self.soup.find('p', class_='character-block__title', string='Race/Clan/Gender').parent
        return list(block.find('p', class_='character-block__name').stripped_strings)[0]

    @lazy_property()
    def clan(self):
        block = self.soup.find('p', class_='character-block__title', string='Race/Clan/Gender').parent
        return list(block.find('p', class_='character-block__name').stripped_strings)[1].split(' / ')[0]

    @lazy_property()
    def gender(self):
        block = self.soup.find('p', class_='character-block__title', string='Race/Clan/Gender').parent
        return list(block.find('p', class_='character-block__name').stripped_strings)[1].split(' / ')[1]

    @lazy_property(default=None)
    def grand_company(self):
        block = self.soup.find('p', class_='character-block__title', string='Grand Company').parent
        return block.find('p', class_='character-block__name').text.split(' / ')

    @lazy_property(default=None)
    def free_company(self):
        return {
            'name': self.soup.find('div', class_='character__freecompany__name').find('a').text,
            'id': self.soup.find('div', class_='character__freecompany__name').find('a')['href'].split('/')[-2],
            'crest': [i['src'] for i in self.soup.find('div', class_='character__freecompany__crest__image').find_all('img')]
        }

    @lazy_property()
    def classes(self):
        return {
            li.find('img')['data-tooltip']: li.text.strip()
            for li in self.soup.select('.character__level__list li')
            if li.text.strip() != '-'
        }

    @lazy_property(default=None)
    def image_full(self):
        return self.soup.find('div', class_='character__detail__image').find('img')['src']

    @lazy_property(default=None)
    def image_face(self):
        return self.soup.find('div', class_='frame__chara__face').find('img')['src']


class CharacterProfile:
    """Represents a character profile on Lodestone. Uses lazy evaluation and caching."""

    def __init__(self, **kwargs):
        self.id = kwargs.pop('id')

    @property
    def as_json(self):
        return {'id': self.id}

    @property
    def profile_url(self):
        return f'{FFXIV.lodestone_url}/character/{self.id}'

    async def get_data(self, session) -> CharacterData:
        if self.id in FFXIV.cache and FFXIV.cache[self.id].is_valid:
            data = FFXIV.cache[self.id].data
        else:
            async with session.get(self.profile_url) as r:
                data = CharacterData(html=await r.text())

            FFXIV.cache[self.id] = CacheData(data)

        return data

    async def profile_embed(self, session):
        data = await self.get_data(session)

        classes = '\n'.join([f"{n:<{max(len(n) for n in data.classes)}} | {l}" for n, l in data.classes.items()])

        e = discord.Embed(
            title=data.name,
            url=self.profile_url,
            description=f"{data.title or ''}\n{data.race}\nServer: {data.server}"

        )
        if data.image_face:
            e.set_thumbnail(
                url=data.image_face
            )
        if data.image_full:
            e.set_image(
                url=data.image_full
            )

        if data.free_company:
            e.add_field(
                name="Free Company",
                value=data.free_company['name']
            )
        if data.grand_company:
            e.add_field(
                name="Grand Company",
                value='\n'.join(data.grand_company)
            )

        e.add_field(
            name="Classes",
            value=f'```{classes}```',
            inline=False
        )

        return e


class FFXIV(utils.SessionCog):

    lodestone_url = 'http://na.finalfantasyxiv.com/lodestone'
    cache = {}

    def from_member(self, mem: discord.Member):
        up = self.bot.profiles.get_by_id(mem.id)
        if 'ffxiv' not in up:
            raise commands.BadArgument(f'{mem.display_name} has no lodestone profile saved.')
        return CharacterProfile(**up['ffxiv'])

    def __init__(self, bot):
        super(FFXIV, self).__init__(bot)
        self.formatters = {'ffxiv_inline': self.ffxiv_formatter}

    async def ffxiv_formatter(self, field):
        c = CharacterProfile(**field)
        try:
            data = await c.get_data(self.session)
        except:
            return {
                'name': 'FFXIV',
                'content': f'[{c.profile_url}]({c.profile_url})'
            }
        else:
            return {
                'name': 'FFXIV',
                'content': f"[{data.name}]({c.profile_url})" if data is not None else c.profile_url
            }

    @commands.group(invoke_without_command=True, pass_context=True)
    @checks.profiles()
    async def ffxiv(self, ctx):
        """Commands related to Final Fantasy XIV"""
        ctx.message.content = ctx.message.content.replace('ffxiv', 'ffxiv profile', 1)
        await self.bot.process_commands(ctx.message)

    @ffxiv.command(pass_context=True)
    async def profile(self, ctx, user: discord.Member=None):
        """Display info on your character or optionally another user's."""
        user = user or ctx.message.author
        await self.bot.say(embed=await self.from_member(user).profile_embed(self.session))

    @ffxiv.command(pass_context=True)
    async def add(self, ctx, link_to_profile: str):
        """Register your FFXIV profile with the bot.

        link should be of this format: http://na.finalfantasyxiv.com/lodestone/character/########
        """
        link_to_profile = link_to_profile.strip('<>')
        try:
            fid = re.match(r'https?://na\.finalfantasyxiv\.com/lodestone/character/(\d{8})', link_to_profile).group(1)
        except AttributeError:
            raise commands.BadArgument("Link was not properly formatted.")

        c = CharacterProfile(id=fid)

        await self.bot.profiles.put_by_id(ctx.message.author.id, 'ffxiv', c.as_json)
        await self.bot.affirmative()


def setup(bot):
    bot.add_cog(FFXIV(bot))
