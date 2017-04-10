import discord
from discord.ext import commands

from cogs.requestsystem import request
import checks
from Weeabot import Weeabot


def get_field(ctx, f: str):
    return [
        c[f] for n, c in ctx.bot.server_configs.get(ctx.message.server.id, {}).get('spoilers', {}).items()
    ]


def is_spoiler_channel():
    return commands.check(lambda ctx: ctx.message.channel.id in get_field(ctx, 'id'))


def is_trusted():

    def predicate(ctx):
        if ctx.message.author.id in [ctx.message.server.owner.id, ctx.bot.owner.id]:
            return True
        try:
            name = [n for n, c in ctx.bot.server_configs[ctx.message.server.id]['spoilers'].items()
                    if c['id'] == ctx.message.channel.id][0]
            return ctx.message.author.id in ctx.bot.server_configs[ctx.message.server.id]['spoilers'][name]['trusted']
        except (IndexError, KeyError):
            return False

    return commands.check(predicate)


def is_author():
    def predicate(ctx):
        if ctx.message.author.id in [ctx.message.server.owner.id, ctx.bot.owner.id]:
            return True
        try:
            name = [n for n, c in ctx.bot.server_configs[ctx.message.server.id]['spoilers'].items()
                    if c['id'] == ctx.message.channel.id][0]
            return ctx.message.author.id == ctx.bot.server_configs[ctx.message.server.id]['spoilers'][name]['author']
        except (IndexError, KeyError):
            return False

    return commands.check(predicate)


class SpoilerChannel:
    """data structure containing spoiler channel info"""

    def __init__(self, bot: Weeabot, name, server, **kwargs):
        self.bot = bot
        self.name = name
        self.server = server
        self.status = kwargs.pop('status', 'No status listed.')
        self.creator = kwargs.pop('author', kwargs.pop('creator', ''))  # to deal with old format
        self.members = kwargs.pop('members', [])
        self.trusted = kwargs.pop('trusted', [])
        self.id = kwargs.pop('id', '')

        self.channel = bot.get_channel(self.id)

        # import from old system
        # if 'role' in kwargs:
        #     print(f'converting {name} in {server} to new format')
        #     s: discord.Server = bot.get_server(self.server)
        #     r = discord.utils.get(s.roles, id=kwargs['role'])
        #     r_p = discord.utils.get(s.roles, id=kwargs['role_present'])
        #     members = [m for m in s.members if r in m.roles]
        #     self.members = [m.id for m in members]
        #     for m in members:
        #         bot.loop.create_task(self.can_read(m))
        #     bot.loop.create_task(bot.delete_role(s, r))
        #     bot.loop.create_task(bot.delete_role(s, r_p))

    async def can_read(self, member: discord.Member):
        """Allow this user to read the channel."""
        await self.bot.edit_channel_permissions(
            channel=self.channel,
            target=member,
            overwrite=discord.PermissionOverwrite(read_messages=True)
        )

    async def cant_read(self, member: discord.Member):
        """Disallow this user from reading the channel."""
        await self.bot.delete_channel_permissions(self.channel, member)

    def members_except(self, member: discord.Member):
        """Get all the discord.Member objects except the one passed."""
        return [self.bot.get_server(self.server).get_member(m) for m in self.members if m != member.id]

    def json(self):
        """encode as a json-safe dict that can be unpacked into the constructor."""
        return {
            'status': self.status,
            'creator': self.creator,
            'trusted': self.trusted,
            'members': self.members,
            'id': self.id
        }


class Spoilers:
    """Spoiler channels."""

    def __init__(self, bot: Weeabot):
        self.channels = list(sum([
            [
                SpoilerChannel(bot, channel, server, **value)
                for channel, value in data['spoilers'].items()
            ]
            for server, data in bot.server_configs.items() if 'spoilers' in data
        ], []))
        self.bot = bot

    def get_channel(self, ctx) -> SpoilerChannel:
        return discord.utils.find(
            lambda spoiler: spoiler.channel == ctx.message.channel,
            self.channels
        )

    def save(self, channel: SpoilerChannel):
        """Save a spoiler channel's data."""
        self.bot.server_configs[channel.server.id]['spoilers'][channel.name] = channel.json()
        self.bot.dump_server_configs()

    def dump(self):
        for channel in self.channels:
            self.bot.server_configs[channel.server.id]['spoilers'][channel.name] = channel.json()
        self.bot.dump_server_configs()

    @commands.group()
    async def spoiler(self):
        """Spoiler channel commands.

    These commands are intended for content updated periodically. For example weekly releases.
    It may be more of an inconvenience than a convenience to apply these commands to other content.
    (a group of people working through a long series for example).

    More commands are available within a spoiler channel. Try reading this info when in one.

    Channel creators have access to the trust, untrust, and remove commands."""

    @spoiler.command(pass_context=True, name='add', no_pm=True)
    @request()
    @checks.is_server_owner()
    async def _add(self, ctx, name: str):
        """Add a spoiler channel."""
        if ctx.message.server.id not in self.bot.server_configs:
            self.bot.server_configs[ctx.message.server.id] = {}
        if 'spoilers' not in self.bot.server_configs[ctx.message.server.id]:
            self.bot.server_configs[ctx.message.server.id]['spoilers'] = {}
        try:
            everyone_perms = discord.PermissionOverwrite(read_messages=False)
            everyone = discord.ChannelPermissions(target=ctx.message.server.default_role, overwrite=everyone_perms)
            can_read = discord.PermissionOverwrite(read_messages=True)
            channel = await self.bot.create_channel(ctx.message.server, name, everyone, (ctx.message.author, can_read))
            spoiler = SpoilerChannel(
                self.bot,
                name,
                ctx.message.server.id,
                status="No status listed.",
                author=ctx.message.author.id,
                members=[ctx.message.author.id],
                trusted=[ctx.message.author.id],
                id=channel.id
            )
            self.channels.append(spoiler)
            self.save(spoiler)

        except discord.errors.HTTPException:
            await self.bot.say("Invalid name or that name is taken. Names must be alphanumeric.")

    @spoiler.command(pass_context=True, name='remove', no_pm=True)
    @is_spoiler_channel()
    @is_author()
    async def _remove(self, ctx):
        """Remove this spoiler channel."""
        spoiler = self.get_channel(ctx)
        await self.bot.delete_channel(spoiler.channel)
        del self.bot.server_configs[spoiler.server]['spoilers'][spoiler.name]
        self.channels.remove(spoiler)
        self.bot.dump_server_configs()

    @spoiler.command(pass_context=True, name='list', no_pm=True)
    async def _list(self, ctx):
        """List the spoiler channels on this server."""
        await self.bot.say('\n'.join([f'{s.name}: {s.status}' for s in filter(lambda c: c.server == ctx.message.server.id, self.channels)]))

    @spoiler.command(pass_context=True, name='status', no_pm=True)
    async def _status(self, ctx, name: str):
        """Check the status of a spoiler channel."""
        spoiler = discord.utils.find(
            lambda spoil: spoil.name == name and spoil.server == ctx.message.server.id,
            self.channels
        )
        if spoiler is None:
            await self.bot.say("Not found.")
            return
        await self.bot.say(f'Status of {name}: {spoiler.status}')

    @spoiler.command(pass_context=True, name='join', aliases=('catchup',), no_pm=True)
    async def _join(self, ctx, *names):
        """Join a spoiler channel or multiple channels."""
        for name in names:
            spoiler = discord.utils.find(
                lambda c: c.server == ctx.message.server.id and c.name == name,
                self.channels
            )
            if spoiler is None:
                await self.bot.say("Not found.")
                return
            await spoiler.can_read(ctx.message.author)
            if ctx.message.author.id in spoiler.members:
                await self.bot.send_message(spoiler.channel, f"{ctx.message.author.mention} is caught up")
            else:
                spoiler.members.append(ctx.message.author.id)
                self.save(spoiler)
                await self.bot.send_message(spoiler.channel, f"Welcome {ctx.message.author.mention} to {name}.")

    @spoiler.command(pass_context=True, no_pm=True)
    async def stealthjoin(self, ctx, *names):
        """Just like join but adds you to the member list (you'll get messages about updates) without spoiling you."""
        for name in names:
            spoiler = discord.utils.find(
                lambda c: c.server == ctx.message.server.id and c.name == name,
                self.channels
            )
            if spoiler is None:
                await self.bot.say("Not found.")
                return
            if ctx.message.author.id not in spoiler.members:
                await self.bot.send_message(spoiler.channel, f"{ctx.message.author.mention} stealthjoined.")
            await self.bot.affirmative()

    @spoiler.command(pass_context=True, no_pm=True)
    @is_spoiler_channel()
    async def leave(self, ctx):
        """Leave this spoiler chat."""
        spoiler = self.get_channel(ctx)
        if ctx.message.author.id == spoiler.creator:
            await self.bot.say("The channel creator can not leave the spoiler channel.")
            return
        spoiler.members.remove(ctx.message.author.id)
        if ctx.message.author.id in spoiler.trusted:
            spoiler.trusted.remove(ctx.message.author.id)
        self.save(spoiler)
        await self.bot.affirmative()

    @spoiler.command(pass_context=True, name='trust', no_pm=True)
    @is_spoiler_channel()
    @is_author()
    async def _trust(self, ctx, user: discord.Member):
        """Allow a user to update this channel."""
        spoiler = self.get_channel(ctx)
        spoiler.trusted.append(user.id)
        self.save(spoiler)
        await self.bot.say(f"{user.display_name} is now trusted.")

    @spoiler.command(pass_context=True, name='untrust', no_pm=True)
    @is_spoiler_channel()
    @is_author()
    async def _untrust(self, ctx, user: discord.Member):
        """Remove a user's ability to update this channel."""
        spoiler = self.get_channel(ctx)
        if user.id == spoiler.creator:
            await self.bot.say("You can't untrust the author.")
            return
        spoiler.trusted.remove(user.id)
        self.save(spoiler)
        await self.bot.say(f"{user.display_name} is now untrusted.")

    @spoiler.command(pass_context=True, name='update', no_pm=True)
    @is_spoiler_channel()
    @is_trusted()
    async def _update(self, ctx, *, status=None):
        """Update this spoiler channel.

        This will block everyone from viewing this channel until they catch up.

        The status will be sent to all users, and displayed to users when they view this channel's status.
        As such, it should not contain spoilers itself. Instead, you could list an episode/chapter number or a
        description (such as 'new arc')."""
        spoiler = self.get_channel(ctx)
        message = (
            f'{ctx.message.author.mention} updated {spoiler.name} in {ctx.message.server.name} with status: "{status}"\n'
            f'to rejoin, call `{self.bot.command_prefix}spoiler catchup {spoiler.name}` in {ctx.message.server.name}'
        )
        for m in spoiler.members_except(ctx.message.author):
            await spoiler.cant_read(m)
            await self.bot.send_message(m, message)
        spoiler.status = status
        self.save(spoiler)
        await self.bot.affirmative()

    @spoiler.command(pass_context=True, no_pm=True)
    @is_spoiler_channel()
    @is_trusted()
    async def set_status(self, ctx, *, status=None):
        """Set the status of the channel without updating it."""
        spoiler = self.get_channel(ctx)
        spoiler.status = status or "No status listed."
        message = f'{ctx.message.author.mention} changed status {spoiler.name} in {ctx.message.server.name} to: "{status}"'
        for m in spoiler.members_except(ctx.message.author):
            await self.bot.send_message(m, message)
        self.save(spoiler)
        await self.bot.affirmative()


def setup(bot):
    bot.add_cog(Spoilers(bot))
