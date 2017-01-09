import json
from datetime import datetime, timedelta
import dateutil.parser

import discord
from discord.ext import commands
import utils


class AniList(utils.SessionCog):
    """Commands that access AniList. Mostly just for seasonal anime."""

    @commands.command()
    @commands.cooldown(1, 1800, commands.BucketType.channel)
    async def anime_list(self, season=None, year=None):
        """Lists anime airing in a given season, or the current season if none is specified.

        Can take both year and season because of the rollover into winter season."""
        daynames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        seasons = ["winter", "spring", "summer", "fall"]
        season_colors = {
            'winter': discord.Colour.lighter_grey(),
            'spring': discord.Colour.green(),
            'summer': discord.Colour.gold(),
            'fall': discord.Colour.orange()
        }
        types = ["tv", "tv short"]

        def datestr(da: datetime):
            if da is None:
                return "Not Listed"
            return dateutil.parser.parse(da).strftime("%m/%d/%Y")

        token = await self.check_token()
        now = datetime.now()
        season = season or seasons[now.month // 3]
        year = year or now.year
        days = [[], [], [], [], [], [], []]


        m = await self.bot.say("collecting info")

        for t in types:
            params = {"access_token": token, "year": year, "season": season, "type": t}
            url = "https://anilist.co/api/browse/anime"
            async with self.session.get(url, params=params) as r:
                js = await r.json()
                if r.status != 200:
                    await self.bot.edit_message(m, f"error in api call: response {r.status}\n{r.reason}\n{js['error_message']}")
                    return
                for anime in js:
                    if not anime["adult"]:
                        url = f"https://anilist.co/api/anime/{anime['id']}"
                        async with self.session.get(url, params={"access_token": token}) as r2:
                            anime = await r2.json()
                            d = dateutil.parser.parse(anime["start_date"])
                            days[d.weekday()].append(anime)
        anilist_url = f'http://anilist.co/browse/anime?sort=start_date-desc&year={year}&season={season}'
        e: discord.Embed = discord.Embed(
            title=f"{season.title()} {year} Anime",
            url=anilist_url,
            color=season_colors[season]
        )
        for day, shows in enumerate(days):
            shows = sorted(shows, key=lambda a: a['start_date_fuzzy'])
            value = [
                f"""*{anime['title_romaji']}*
                {datestr(anime['start_date'])} — {datestr(anime['end_date'])}
                {f"Time until next episode: {timedelta(seconds=anime['airing']['countdown'])}"
                    if anime['airing'] is not None and 'countdown' in anime['airing'] else ''
                }
                """
                for anime in shows
            ]

            pages = [[]]
            for v in value:
                if len('\n'.join(pages[-1])) + len(v) < 1024:
                    pages[-1].append(v)
                else:
                    pages.append([v])

            e.add_field(name=daynames[day], value='\n'.join(pages[0]), inline=False)
            for p in pages[1:]:
                e.add_field(name='\N{ZERO WIDTH SPACE}', value='\n'.join(p), inline=False)

        await self.bot.delete_message(m)
        await self.bot.say(embed=e)

    async def check_token(self):
        params = {"client_id": utils.tokens['anilist_id'], "client_secret": utils.tokens['anilist_secret'], "grant_type": "client_credentials"}
        url = "https://anilist.co/api/auth/access_token"
        async with self.session.post(url, params=params) as r:
            if r.status != 200:
                await self.bot.say(f"error in check_token call: response {r.status}")
                return
            token = (await r.json())["access_token"]
            return token


def setup(bot):
    bot.add_cog(AniList(bot))
