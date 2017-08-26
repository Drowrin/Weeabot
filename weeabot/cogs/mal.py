import asyncio
import xmltodict
import random

import discord
from discord.ext import commands

from ._base import base_cog


async def mal_embed(data) -> discord.Embed:
    stat = data['my_status']  # in order from 1: CW, Comp, Hold, Drop, <nothing>, PTW, All
    stat_text = ['Watching', 'Completed', 'On Hold', 'Dropped', '', 'Plan To Watch', 'All'][int(stat) - 1]
    score = f'Score: {data["my_score"].replace("0", "-")}/10'
    progress = f'Progress: {data["my_watched_episodes"]}/{data["series_episodes"]}'
    episodes = f'Episodes: {data["series_episodes"]}'

    def form(*args):
        return ' | '.join(args)

    if stat in '134':
        ft = form(stat_text, score, progress)
    elif stat in '2':
        ft = form(stat_text, score, episodes)
    elif stat in '6':
        ft = form(stat_text, episodes)
    else:
        ft = stat_text

    return discord.Embed(
        title=data['series_title'],
        url=f'https://myanimelist.net/anime/{data["series_animedb_id"]}'
    ).set_image(
        url=data['series_image']
    ).set_footer(
        text=ft
    )


class MAL(base_cog(session=True)):
    """
    MyAnimeList
    """

    async def getmal_retry(self, ctx, user: discord.User, retries: int = 5, tmp=None):
        for i in range(0, retries):
            result = await self.getmal(ctx, user)
            if result is not None:
                return result
            else:
                if tmp is not None:
                    await self.bot.edit_message(tmp, "Error reading from MAL, retrying" + '.' * i)
                await asyncio.sleep(1)
        if tmp is not None:
            await self.bot.edit_message(tmp, "Could not connect to MAL, try again later.")

    async def getmal(self, ctx, user: discord.User):
        mal = await self.bot.profile_fields['MyAnimeList'].get(ctx, user)
        if mal is None:
            raise commands.BadArgument("{} has no saved MAL username.".format(user.display_name))
        params = {'u': mal, 'type': 'anime', 'status': 'all'}
        async with self.session.get('https://myanimelist.net/malappinfo.php', params=params) as r:
            if r.status != 200:
                return
            xml = xmltodict.parse(await r.text())
        if len(xml['myanimelist']) <= 1:
            raise commands.BadArgument("{} is not a valid MAL username.".format(mal))
        return xml['myanimelist']

    async def random_anime(self, ctx, stat, user: discord.User):
        """Helper function. Picks an anime from a MAL based on status."""
        mal = (await self.getmal(ctx, user))['anime']
        w = [anime for anime in mal if anime['my_status'] in stat]
        if len(w) == 0:
            raise commands.BadArgument("No anime in the specified status.")
        return random.choice(w)

    async def pick_anime(self, ctx, stat, user: str = None, msg: discord.Message = None):
        """Helper function. Picks an anime from a MAL based on a status and handles communicating it."""
        if user is None:
            usr = ctx.message.author
        elif isinstance(user, (discord.User, discord.Member)):
            usr = user
        else:
            try:
                usr = await commands.MemberConverter().convert(ctx, user)
            except commands.BadArgument as e:
                await ctx.send(content=e)
                return

        if msg:
            await msg.edit(content="Choosing a show...")
        else:
            msg = await ctx.send(content="Choosing a show...")

        try:
            anime = await self.random_anime(ctx, stat, usr)
        except commands.BadArgument as e:
            await msg.edit(content=e)
            return
        await msg.edit(content=f"{usr.mention} should watch", embed=await mal_embed(anime))

        # refresh button
        emoji = '🔄'

        async def callback(*_):
            await self.pick_anime(ctx, stat, usr, msg)
            await msg.clear_reactions()
            await msg.add_reaction(emoji)

        await msg.add_reaction(emoji)
        self.bot.reactionlisteners.add(msg, callback, single_use=False, user=ctx.author, reactions=[emoji])

    @commands.command()
    async def watch(self, ctx, user: str = None):
        """
        Select a show to watch based on a MAL user.

        Defaults to your own MAL if it is saved.
        """
        await self.pick_anime(ctx, ['3', '6'], user)

    @commands.command()
    async def rewatch(self, ctx, user: str = None):
        """
        Select a show to rewatch based on a MAL user.

        Defaults to your own MAL if it is saved.
        """
        await self.pick_anime(ctx, ['2'], user)


@MAL.profile_field(name='MyAnimeList')
async def mal_profile(data):
    """
    MyAnimeList profile used in several other commands.
    """
    return f"[{data}](https://myanimelist.net/animelist/{data})"


@mal_profile.set_setter
async def mal_profile_setter(ctx, user, value):
    return value


def setup(bot):
    bot.add_cog(MAL(bot))
