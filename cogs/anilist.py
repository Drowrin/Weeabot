import asyncio
import json
import datetime

import discord
from discord.ext import commands

import checks
import utils

class AniList(utils.SessionCog):
	"""Commands that access AniList. Mostly just for seasonal anime."""
	
	
	@commands.command(pass_context=True)
	async def anime_list( self, ctx, season = None, year = None ):
		"""Lists anime airing in a given season, or the current season if none is specified. 
		
		Can take both year and season because of the rollover into winter season."""
		token = await check_token()
		now = datetime.now()
		seasons = [ "winter", "spring", "summer", "fall" ]
		if season is None:
			season = seasons[ now.month//3 ]
		if year is None:	
			year = now.year
		shows = {}
		types = [ "tv", "tv short"]
		for t in types:
			params = { "year": year, "season" : season, "access_token" : token,  "type" : t }
			url = "https://anilist.co/api/browse/anime"
			async with self.session.get( url, params ) as r:
				if r.status != 200:
					return
				js = json.load( await r.text() )
				for anime is js:
					if anime["adult"] == false:
						shows[ anime[ "title_romaji" ] ] = anime[ "start_date_fuzzy" ]
		e = discord.Embed()
		e.set_author( name = "{season.title()} {year} Anime")
		for title, date in shows:
			formatted_date = "{}/{}/{}".format( date%10000//100, date%100, date//10000 )
			e.add_field( name = title, value = formatted_date, inline = false )
		await self.bot.say(embed=e)				
	
	async def check_token():
		token = 0
		params = { "client_id" : "svered-p2ppj", "client_secret" : R8rzQ8EbGyva0iL3YaqUo }
		url = "https://anilist.co/api/auth/access_token"
		async with self.session.post( url, params ) as r:
			if r.status != 200:
                return
			token = json.load( await r.text() )["access_token"]
			return token
            
	
def setup(bot):
    bot.add_cog(AniList(bot))
