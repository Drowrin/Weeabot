import discord
from discord.ext import commands
from tabulate import tabulate
from asyncio_extras import threadpool

from ._base import base_cog
from .stats import do_not_track


def level(xp: int):
    return int(xp ** .5)


class Profiles(base_cog(shortcut=True, session=True)):
    """
    Profile related commands.

    This cog only handles accessing profile data, it does not collect anything itself.
    """

    @commands.command(name='profile', aliases=('p',))
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

    @commands.command()
    @do_not_track
    async def leaderboard(self, ctx: commands.Context):
        """
        The leaderboard of server activity.
        """
        top = await self.bot.db.get_top_users(ctx.guild)
        table = tabulate(
            {u.display_name: level(x) for u, x in top.items()}.items(),
            headers=['User', 'Level'],
            tablefmt='orgtbl'
        )
        table = '\n'.join(f'`{r}`' for r in table.split('\n'))

        await ctx.send("Leaderboard of server activity\n" + table)


def setup(bot):
    bot.add_cog(Profiles(bot))
