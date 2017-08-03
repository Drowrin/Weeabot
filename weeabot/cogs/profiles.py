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

    @commands.group(name='profile', aliases=('p',), invoke_without_command=True)
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
        order = sorted(self.bot.profile_fields.values())
        for f in order:
            await f(ctx, user, e)

        await ctx.send(embed=e)

    def get_settable_fields(self):
        return {k: v for k, v in self.bot.profile_fields.items() if v.setter is not None}

    @prof.group(name='set', invoke_without_command=True)
    async def _set(self, ctx, key, *, value=None):
        """
        Set the value of a profile field.
        """
        if key not in self.get_settable_fields():
            raise commands.BadArgument("Unknown key")
        result = await self.bot.profile_fields[key].setter(ctx, ctx.author, value)
        if result is not None:
            async with threadpool(), self.bot.db.get_profile_field(ctx.author, key) as f:
                if f is not None:
                    f.value = result
                    await ctx.affirmative()
                    return
            await self.bot.db.create_profile_field(ctx.author, key, result)
            await ctx.affirmative()
        else:
            await ctx.negative()

    @_set.command(name='list')
    async def _set_list(self, ctx):
        """
        List the fields you can set in your profile.
        """
        await ctx.send('\n'.join([
             await c.status_str(ctx, ctx.author)
             for c in self.get_settable_fields().values()
         ]))

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
        table = '\n'.join('`{}`'.format(r) for r in table.split('\n'))

        await ctx.send("Leaderboard of server activity\n" + table)


def setup(bot):
    bot.add_cog(Profiles(bot))
