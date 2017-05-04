import asyncio
import datetime

import discord
from discord.ext import commands

import utils
import checks


class Moderation:
    """Moderation commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if 'jails' not in self.bot.status:
            self.bot.status['jails'] = {}
            self.bot.dump_status()
        self.bot.loop.create_task(self.check_jails())
        self.jail_events = {}

    async def get_jail(self, server: discord.Server) -> (discord.Role, discord.Channel):
        """Get the jail role and channel of a server. If it doesn't exist, add it."""
        s = self.bot.server_configs[server.id]
        if 'jails' in s:
            role = discord.utils.get(server.roles, id=s['jails']['role'])
            channel = server.get_channel(s['jails']['channel'])
            if role is not None and channel is not None:
                return role, channel

        server_perms = discord.Permissions()
        server_perms.read_messages = False
        server_perms.send_messages = False
        role = await self.bot.create_role(server, name="prisoner", hoist=True, permissions=server_perms)

        po = discord.PermissionOverwrite(read_messages=True)
        prisoner = discord.ChannelPermissions(target=role, overwrite=po)
        eo = discord.PermissionOverwrite(read_messages=False)
        everyone = discord.ChannelPermissions(target=server.default_role, overwrite=eo)

        channel = await self.bot.create_channel(server, "jail", prisoner, everyone)

        s['jails'] = {
            'role': role.id,
            'channel': channel.id
        }
        self.bot.dump_server_configs()
        return role, channel

    async def arrest(self, mid: str):
        """Make an arrest based on member id key in the jails dict.

        Creates an event.
        Creates the channel and role if they don't exist."""
        async def a():
            try:
                j = self.bot.status['jails'][mid]
            except KeyError:
                print(f'Jail keyerror {mid}')
                return
            finished = discord.utils.parse_time(j['finished']) - datetime.datetime.now()
            server = self.bot.get_server(j['server'])
            if server is None:
                print(f"Could not arrest, couldn't get server. {j}")
                return
            user: discord.Member = server.get_member(j['user'])

            role, channel = await self.get_jail(server)

            if role not in user.roles:
                # arrest them
                await self.bot.add_roles(user, role)
                await self.bot.send_message(channel, f"{user.mention} has been arrested! Time remaining: {utils.down_to_seconds(finished)}")

            # handle freeing after duration, or freed by command.
            self.jail_events[mid] = asyncio.Event()
            async def auto_free():
                await asyncio.sleep(finished.seconds)
                self.jail_events[mid].set()
            self.bot.loop.create_task(auto_free())
            await self.jail_events[mid].wait()

            # free user
            await self.bot.remove_roles(user, role)
            await self.bot.send_message(server, f"{user.mention} is free!")

            del self.bot.status['jails'][mid]
            self.bot.dump_status()
        self.bot.loop.create_task(a())

    async def check_jails(self):
        await self.bot.init.wait()
        for mid in self.bot.status['jails']:
            await self.arrest(mid)

    @commands.command(pass_context=True, aliases=('arrest',), no_pm=True)
    async def jail(self, ctx, user: str, *, duration: str="1h"):
        """Jail a user for a specified amount of time. Accepts a user or "me".

        The format for the duration uses units. For example, something like 3 hours and 20 minutes or 4m 15s.
        Without permissions, you can only jail yourself.
        Will create a jail channel and role if they don't already exist."""
        # Get user, and check permissions
        if user == 'me':
            user = ctx.message.author
        elif checks.moderator(ctx):
            user = commands.MemberConverter(ctx, user).convert()
        else:
            raise utils.CheckMsg("You do not have permission to do that.")

        td = utils.duration(duration)
        current_time = datetime.datetime.now()

        # create jail
        self.bot.status['jails'][ctx.message.id] = {
            'finished': str(current_time + td),
            'server': ctx.message.server.id,
            'user': user.id
        }
        await self.arrest(ctx.message.id)
        self.bot.dump_status()
        await self.bot.affirmative()

    async def unjail(self, server: discord.Server, user: discord.Member):
        def pred(jdata):
            _, j = jdata
            return j['server'] == server.id and j['user'] == user.id

        jid, _ = discord.utils.find(pred, self.bot.status['jails'].items())
        self.jail_events[jid].set()

    @commands.command(pass_context=True, aliases=('unjail',), no_pm=True)
    @checks.is_moderator()
    async def free(self, ctx, user: str):
        """Free the user from jail. Accepts a user or "me"."""
        # Get user, and check permissions
        if user == 'me':
            user = ctx.message.author
        else:
            user = commands.MemberConverter(ctx, user).convert()

        await self.unjail(ctx.message.server, user)


def setup(bot):
    bot.add_cog(Moderation(bot))
