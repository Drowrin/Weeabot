import re
import aiohttp
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


class CharacterData(object):
    """Data structure for character information on Lodestone. Parses from html."""

    @staticmethod
    def from_html(html, **data):
        soup = bs4.BeautifulSoup(html, "html.parser")

        data['name'] = soup.select('.player_name_txt h2 a')[0].text.strip()
        data['server'] = soup.select('.player_name_txt h2 span')[0].text.strip()[1:-1]
        try:
            data['title'] = soup.select('.chara_title')[0].text.strip()
        except (AttributeError, IndexError):
            data['title'] = None
        data['race'], data['clan'], data['gender'] = soup.select('.chara_profile_title')[0].text.split(' / ')
        data['gender'] = 'male' if data['gender'].strip('\n\t')[-1] == u'\u2642' else 'female'

        try:
            data['grand_company'] = discord.utils.get(soup.select('.chara_profile_box_info dd'), text="Grand Company").parent.select('.txt_name')[0].text.split('/')
        except (AttributeError, IndexError):
            data['grand_company'] = None

        try:
            data['free_company'] = None
            for elem in soup.select('.chara_profile_box_info'):
                if 'Free Company' in elem.text:
                    fc = elem.select('a.txt_yellow')[0]
                    data['free_company'] = {
                        'id': re.findall(r'(\d+)', fc['href'])[0],
                        'name': fc.text,
                        'crest': [x['src'] for x in
                                  elem.find('div', attrs={'class': 'ic_crest_32'}).findChildren('img')]
                    }
                    break
        except (AttributeError, IndexError):
            data['free_company'] = None

        data['classes'] = {}
        for tag in soup.select('.class_list .ic_class_wh24_box'):
            class_ = tag.text

            if not class_:
                continue

            level = tag.next_sibling.next_sibling.text

            if level == '-':
                level = 0
                exp = 0
                exp_next = 0
            else:
                level = int(level)
                exp = int(tag.next_sibling.next_sibling.next_sibling.next_sibling.text.split(' / ')[0])
                exp_next = int(tag.next_sibling.next_sibling.next_sibling.next_sibling.text.split(' / ')[1])

            data['classes'][class_] = dict(level=level, exp=exp, exp_next=exp_next)

        data['image_full'] = soup.select('.bg_chara_264 img')[0].get('src')
        data['image_face'] = soup.select('.player_name_thumb a img')[0].get('src')

        return CharacterData(**data)

    def __init__(self, **kwargs):
        self.name = kwargs.pop('name')
        self.server = kwargs.pop('server')
        self.title = kwargs.pop('title')
        self.race = kwargs.pop('race')
        self.clan = kwargs.pop('clan')
        self.gender = kwargs.pop('gender')
        self.grand_company = kwargs.pop('grand_company')
        self.free_company = kwargs.pop('free_company')
        self.classes = kwargs.pop('classes')
        self.image_full = kwargs.pop('image_full')
        self.image_face = kwargs.pop('image_face')


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
                data = CharacterData.from_html(await r.text())

            FFXIV.cache[self.id] = CacheData(data)

        return data

    async def profile_embed(self, session):
        data = await self.get_data(session)

        classes = {n: d for n, d in data.classes.items() if d['level']}
        classes = '\n'.join([f"{n:<{max(len(n) for n in classes)}} | {d['level']}" for n, d in classes.items()])

        e = discord.Embed(
            title=data.name,
            url=self.profile_url,
            description=f"""
            {data.title or ''}
            {data.race}
            Server: {data.server}
            """

        ).set_thumbnail(
            url=data.image_face
        ).set_image(
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

    @commands.group()
    @checks.profiles()
    async def ffxiv(self):
        """Commands related to Final Fantasy XIV"""

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
