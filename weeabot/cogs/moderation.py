import asyncio
import humanize
import dateparser
import discord
from datetime import datetime

from asyncio_extras import threadpool

from discord.ext import commands

from . import BaseCog
from .stats import do_not_track
from ..storage.tables import JailSentence


class Moderation(BaseCog):
    """
    Moderation and guild management tools.
    """

    def __init__(self, bot):
        super(Moderation, self).__init__(bot)
        self.jail_events = {}
        self.bot.loop.create_task(self.check_jails())

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

    # Jails
    async def check_jails(self):
        """
        Load stored jails into memory and start their timers.
        """
        await self.bot.init.wait()
        js = await self.bot.db.get_all_jails()
        for j in js:
            self.arrest(j)

    def arrest(self, sentence: JailSentence):
        """
        Activate this JailSentence.
        """
        async def a():
            waittime = sentence.finished - datetime.now()
            guild: discord.Guild = sentence.guild.get()
            if guild is None:
                print(f"Could not arrest, couldn't get {guild}")
                return

            member = guild.get_member(sentence.user)

            # get or create role
            role = discord.utils.get(guild.roles, id=sentence.guild.jail_role_id)
            if role is None:
                p = discord.Permissions()
                p.update(
                    read_messages=False,
                    send_messages=False
                )
                role = await guild.create_role(
                    name="prisoner",
                    permissions=p
                )
                await self.bot.db.set_jail_role(guild, role)

            # get or create channel
            channel = self.bot.get_channel(sentence.guild.jail_id)
            if channel is None:
                po = discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True
                )
                channel = await guild.create_text_channel(
                    name="jail",
                    overwrites={
                        role: po
                    }
                )
                await self.bot.db.set_jail_channel(guild, channel)

            if role not in member.roles:
                await member.add_roles(role, reason="jail")
                await channel.send(f"{member.mention} has been arrested! Time remaining: {humanize.naturaldelta(waittime)}")

            # handle freeing after duration or freed by command.
            self.jail_events[sentence.id] = asyncio.Event()
            async def auto_free():
                await asyncio.sleep(waittime.seconds)
                self.jail_events[sentence.id].set()
            self.bot.loop.create_task(auto_free())
            await self.jail_events[sentence.id].wait()

            # free user
            await member.remove_roles(role, reason="freed from jail")
            await guild.default_channel.send(f"{member.mention} is free!")

            async def task():
                await self.bot.db.delete_jail(sentence)
            await self.bot.loop.create_task(task())

        self.bot.loop.create_task(a())

    @commands.command(aliases=('arrest',), no_pm=True)
    async def jail(self, ctx, user: str, *, duration: str="1 hour"):
        """
        Jail a user for a specified amount of time. Accepts a user or "me".

        The format for the duration is fairly flexible. Just speak naturally.
        """
        if user == 'me':
            user = ctx.author
        elif ctx.author.permissions_in(ctx.channel).kick_members:
            user = await commands.MemberConverter().convert(ctx, user)
        else:
            raise commands.BadArgument("You do not have permission to do that.")

        current_time = datetime.now()
        finished = dateparser.parse(duration)

        # to handle "1 day" cases, which dateparser treats as "1 day ago"
        if (finished - current_time).total_seconds() < 0:
            finished = dateparser.parse(duration + " from now")

        # create jail
        j = JailSentence(
            user=user.id,
            finished=finished
        )
        async def task():
            async with self.bot.db.get_guild(ctx.guild) as g:
                g.jail_sentences.append(j)
        self.bot.loop.create_task(task())

        self.arrest(j)
        await ctx.affirmative()

    async def unjail(self, guild: discord.Guild, user: discord.User):
        """
        Free a user from the guild's jail.
        """
        async with threadpool(), self.bot.db.get_jail(guild, user) as j:
            if j is None:
                raise commands.BadArgument("User is not in jail!")
            self.jail_events[j.id].set()

    @commands.command(aliases=('unjail',), no_pm=True)
    @commands.has_permissions(kick_members=True)
    @do_not_track
    async def free(self, ctx, user: str):
        """
        Free the user from jail. Accepts a user's tag, name, or "me" to target yourself.
        """
        # get user in case of "me"
        if user == 'me':
            user = ctx.author
        else:
            user = await commands.MemberConverter().convert(ctx, user)

        await self.unjail(ctx.guild, user)

    @commands.group(no_pm=True, invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    @do_not_track
    async def config(self, ctx, setting, *, value=None):
        """
        Bot settings for this guild.
        """
        c = self.bot.guild_configs.get(setting)
        if c is None:
            raise commands.BadArgument(f"{setting} not found.")
        val = await c(ctx)
        async with threadpool(), self.bot.db.get_or_create_guild_config(ctx.guild, setting) as conf:
            conf.value = val
        await ctx.send("Set `{}` to `{}`".format(setting, val))

    @config.command(no_pm=True)
    @do_not_track
    async def list(self, ctx):
        """
        List the bot settings for this guild.
        """
        await ctx.send('\n'.join([
            await c.status_str(ctx.guild)
            for c in self.bot.guild_configs.values()
        ]))


def setup(bot):
    bot.add_cog(Moderation(bot))
