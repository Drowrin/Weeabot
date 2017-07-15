import discord
from discord.ext import commands
from . import BaseCog
from .stats import do_not_track


class Moderation(BaseCog):
    """
    Moderation and guild management tools.
    """

    def __init__(self, bot):
        super(Moderation, self).__init__(bot)

    @commands.command()
    @commands.has_permissions(administrator=True)
    @do_not_track
    async def autorole(self, ctx: commands.Context, role: discord.Role):
        """
        Set a role to be assigned to all new users.
        """
        self.bot.guild_configs[role.guild.id]['autorole'] = role.id
        await self.bot.guild_configs.save()
        await ctx.send(f"New members will now be given the {role.name} role.")

    async def on_member_join(self, member: discord.Member):
        try:
            ar = self.bot.guild_configs[member.guild.id]['autorole']
        except KeyError:
            pass
        else:
            role = discord.utils.get(member.guild.roles, id=ar)
            await member.add_roles(role)

    async def on_guild_join(self, guild):
        await self.bot.owner.send(f"Joined Guild: {guild} {guild.id}")
        p = self.bot.command_prefix
        await guild.send(f"Hello! Use {p}help and {p}services to see what I can do.")


def setup(bot):
    bot.add_cog(Moderation(bot))
