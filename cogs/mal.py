# noinspection PyUnresolvedReferences
import discord
import xmltodict
import asyncio
# noinspection PyUnresolvedReferences
from discord.ext import commands
from utils import *


# noinspection PyUnusedLocal
def mal_formatter(ctx, field, fields):
    fields.append('MAL: <http://myanimelist.net/animelist/{}>'.format(field))


class MAL(SessionCog):
    """Commands that access MyAnimeList."""
    
    formatters = {'mal': mal_formatter}
    
    async def getmal_retry(self, user: discord.User, retries: int=5, tmp=None):
        for i in range(0, retries):
            result = await self.getmal(user)
            if result is not None:
                return result
            else:
                if tmp is not None:
                    await self.bot.edit_message(tmp, "Error reading from MAL, retrying" + '.' * i)
                await asyncio.sleep(1)
        if tmp is not None:
            await self.bot.edit_message(tmp, "Could not connect to MAL, try again later.")

    async def getmal(self, user: discord.User):
        up = self.bot.profiles.get_by_id(user.id)
        if 'mal' not in up:
            raise commands.BadArgument("{} has no saved MAL username.".format(user.display_name))
        mn = up['mal']
        params = {'u': mn, 'type': 'anime', 'status': 'all'}
        async with self.session.get('http://myanimelist.net/malappinfo.php', params=params) as r:
            if r.status != 200:
                return
            xml = xmltodict.parse(await r.text())
        if len(xml['myanimelist']) <= 1:
            raise commands.BadArgument("{} is not a valid MAL username.".format(mn))
        return xml['myanimelist']
    
    async def random_anime(self, stat, user: discord.User):
        """Helper function. Picks an anime from a MAL based on status."""
        mal = (await self.getmal(user))['anime']
        w = [anime for anime in mal if anime['my_status'] in stat]
        if len(w) == 0:
            raise commands.BadArgument("No anime in the specified status.")
        return random.choice(w)
    
    async def pick_anime(self, ctx, stat, user: str=None):
        """Helper function. Picks an anime from a MAL based on a status and handles communicating it."""
        if user is None:
            usr = ctx.message.author
        else:
            try:
                usr = commands.MemberConverter(ctx, user).convert()
            except commands.BadArgument as e:
                await self.bot.say(e)
                return
        tmp = await self.bot.say("Choosing a show...")
        try:
            anime = await self.random_anime(stat, usr)
        except commands.BadArgument as e:
            await self.bot.edit_message(tmp, e)
            return
        await self.bot.edit_message(tmp, "{} should watch {}\n{}".format(
            usr.mention, anime['series_title'], anime['series_image']))

    async def putmal(self, uid, mal):
        await self.bot.profiles.put_by_id(uid, 'mal', mal)
    
    @commands.command(pass_context=True)
    @profiles()
    async def addmal(self, ctx, mal: str, user: str=None):
        """Add a mal username to the profile of a user."""
        try:
            if user is None:
                usr = ctx.message.author
            else:
                usr = commands.MemberConverter(ctx, user).convert()
            await self.putmal(usr.id, mal)
        except commands.BadArgument as e:
            await self.bot.say(e)
            return
        await self.bot.say("Added {} as {}.".format(mal, usr.display_name))
    
    @commands.command(pass_context=True)
    @profiles()
    async def watch(self, ctx, user: str=None):
        """Select a show to watch based on a MAL user.
        
        Defaults to your own MAL if it is saved."""
        await self.pick_anime(ctx, ['3', '6'], user)
        
    @commands.command(pass_context=True)
    @profiles()
    async def rewatch(self, ctx, user: str=None):
        """Select a show to rewatch based on a MAL user.
        
        Defaults to your own MAL if it is saved."""
        await self.pick_anime(ctx, ['2'], user)
    
    @commands.command(pass_context=True, aliases=('fite',))
    @profiles()
    async def fight(self, ctx, user2: str, threshold: int=2):
        """Fight about MAL scores.
        
        Finds an anime the two users disagree on based on score.
        Bigger disagreements are more likely.
        If a threshold is supplied, only shows with a larger difference will be selected."""
        user1 = ctx.message.author
        try:
            user2 = commands.MemberConverter(ctx, user2).convert()
        except commands.BadArgument as e:
            await self.bot.say(e)
            return
        tmp = await self.bot.say(
            "Getting MAL information for {} and {}...".format(user1.display_name, user2.display_name))
        try:
            mal1 = await self.getmal_retry(user1, tmp=tmp)
            mal2 = await self.getmal_retry(user2, tmp=tmp)
        except commands.BadArgument as e:
            await self.bot.edit_message(tmp, e)
            return
        anime1 = mal1['anime']
        anime2 = mal2['anime']
        dict1 = {anime['series_title']: anime for anime in anime1}
        dict2 = {anime['series_title']: anime for anime in anime2}
        common = {title: abs(int(dict1[title]['my_score']) - int(dict2[title]['my_score']))
                  for title in dict1.keys() if title in dict2.keys()}
        common = {title: common[title] for title in common.keys() if common[title] >= threshold and
                  dict1[title]['myscores'] != '0' and dict2[title]['my_scores'] != '0'}
        if len(common) <= 0:
            await self.bot.edit_message(tmp, "Nothing in common, or no disagreements above the threshold.")
            return
        wlist = [[title]*common[title] for title in common.keys()]
        chosen = random.choice(wlist)[0]
        await self.bot.edit_message("{}({}) should fight {}({}) about {}".format(
            user1.mention, dict1[chosen]['my_score'], user2.mention, dict2[chosen]['my_score'], chosen))


def setup(bot):
    bot.add_cog(MAL(bot))
