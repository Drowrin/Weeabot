import operator
import os
import json
import inspect
import traceback

import discord
from discord.ext import commands

from asyncio_extras import threadpool

from .. import utils
from ._base import base_cog
from .stats import do_not_track


def level(xp: int):
    return int(xp ** .5)


class Profiles(base_cog(shortcut=True, session=True)):
    """
    Profile related commands.

    This cog only handles accessing profile data, it does not collect anything itself.
    """

    @commands.group(invoke_without_command=True, name='profile', aliases=('p',))
    @do_not_track
    async def prof(self, ctx: commands.Context, user: discord.Member=None):
        """
        Show information on a user.

        If no user is passed, will default to you.
        """
        if user is None:
            user = ctx.author

        async with threadpool(), self.bot.db.get_user(user) as u:
            e = discord.Embed(
                color=user.colour,
                timestamp=user.joined_at,
                description=f"{user.top_role} | Level {level(u.xp or 0)}"
            ).set_author(
                name=user.display_name
            ).set_thumbnail(
                url=user.avatar_url
            ).set_footer(
                text="Joined at"
            )
            order = sorted(self.bot.formatters.values())
            for f in order:
                await f(u)(e)

        await ctx.send(embed=e)



def setup(bot):
    bot.add_cog(Profiles(bot))
