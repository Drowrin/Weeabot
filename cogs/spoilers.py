import discord
from discord.ext import commands

from cogs.requestsystem import request, RequestLevel


def get_channel(ctx):
    """Get the spoiler channel info for this channel. Assumes this is a valid spoiler channel."""
    return [(n, c) for n, c in ctx.bot.server_configs[ctx.message.server.id]['spoilers'].items()
            if c['id'] == ctx.message.channel.id][0]


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


class Spoilers:
    """Spoiler channels."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.group()
    async def spoiler(self):
        """Spoiler channel commands.

    These commands are intended for content updated periodically. For example weekly releases.
    It may be more of an inconvenience than a convenience to apply these commands to other content.
    (a group of people working through a long series for example)."""

    @spoiler.command(pass_context=True, name='add', no_pm=True)
    @request(level=RequestLevel.server, owner_bypass=False)
    async def _add(self, ctx, name: str):
        """Add a spoiler channel."""
        if ctx.message.server.id not in self.bot.server_configs:
            self.bot.server_configs[ctx.message.server.id] = {}
        if 'spoilers' not in self.bot.server_configs[ctx.message.server.id]:
            self.bot.server_configs[ctx.message.server.id]['spoilers'] = {}
        try:
            everyone_perms = discord.PermissionOverwrite(read_messages=False)
            role_perms = discord.PermissionOverwrite(read_messages=True)
            role = await self.bot.create_role(ctx.message.server, name=name, mentionable=True)
            role_present = await self.bot.create_role(ctx.message.server, name=name + "_present")
            everyone = discord.ChannelPermissions(target=ctx.message.server.default_role, overwrite=everyone_perms)
            role_over = discord.ChannelPermissions(target=role_present, overwrite=role_perms)
            channel = await self.bot.create_channel(ctx.message.server, name, everyone, role_over)
            await self.bot.add_roles(ctx.message.author, role, role_present)
            self.bot.server_configs[ctx.message.server.id]['spoilers'][name] = {
                'id': channel.id,
                'author': ctx.message.author.id,
                'trusted': [ctx.message.author.id],
                'role': role.id,
                'role_present': role_present.id
            }
            self.bot.dump_server_configs()
        except discord.errors.HTTPException:
            await self.bot.say("Invalid name or that name is taken. Names must be alphanumeric.")

    @spoiler.command(pass_context=True, name='remove', no_pm=True)
    @is_spoiler_channel()
    @is_author()
    async def _remove(self, ctx):
        """Remove this spoiler channel."""
        name, spoil = get_channel(ctx)
        role = discord.utils.get(ctx.message.server.roles, id=spoil['role'])
        role_present = discord.utils.get(ctx.message.server.roles, id=spoil['role_present'])
        chan = self.bot.get_channel(spoil['id'])
        await self.bot.delete_channel(chan)
        await self.bot.delete_role(ctx.message.server, role)
        await self.bot.delete_role(ctx.message.server, role_present)
        del self.bot.server_configs[ctx.message.server.id]['spoilers'][name]
        self.bot.dump_server_configs()

    @spoiler.command(pass_context=True, name='list', no_pm=True)
    async def _list(self, ctx):
        """List the spoiler channels on this server."""
        try:
            await self.bot.say('\n'.join([f'{n}: {s.get("status", "No status listed.")}' for n, s in self.bot.server_configs[ctx.message.server.id]['spoilers'].items()]))
        except (TypeError, KeyError):
            await self.bot.say('None')

    @spoiler.command(pass_context=True, name='status', no_pm=True)
    async def _status(self, ctx, name: str):
        """Check the status of a spoiler channel."""
        if name not in self.bot.server_configs[ctx.message.server.id].get('spoilers', {}):
            await self.bot.say(f"{name} not found")
            return
        try:
            stat = self.bot.server_configs[ctx.message.server.id]['spoilers'][name].get('status', 'No status listed.')
            await self.bot.say(f'Status of {name}: {stat}')
        except KeyError:
            await self.bot.say("No status listed.")

    @spoiler.command(pass_context=True, name='join', no_pm=True)
    async def _join(self, ctx, name: str):
        """Join a spoiler channel."""
        if name in [r.name for r in ctx.message.author.roles]:
            await self.bot.say(f"You are already in that channel.")
            return
        try:
            c = self.bot.server_configs[ctx.message.server.id]['spoilers'][name]
            role = discord.utils.get(ctx.message.server.roles, id=c['role'])
            role_present = discord.utils.get(ctx.message.server.roles, id=c['role_present'])
            await self.bot.add_roles(ctx.message.author, role, role_present)
            await self.bot.send_message(discord.Object(c['id']), f"Welcome {ctx.message.author.mention} to {name}.")
        except KeyError:
            await self.bot.say("not found.")

    @spoiler.command(pass_context=True, name='trust', no_pm=True)
    @is_spoiler_channel()
    @is_author()
    async def _trust(self, ctx, user: discord.Member):
        """Allow a user to update this channel."""
        _, spoil = get_channel(ctx)
        spoil['trusted'].append(user.id)
        self.bot.dump_server_configs()
        await self.bot.say(f"{user.display_name} is now trusted.")

    @spoiler.command(pass_context=True, name='untrust', no_pm=True)
    @is_spoiler_channel()
    @is_author()
    async def _untrust(self, ctx, user: discord.Member):
        """Remove a user's ability to update this channel."""
        _, spoil = get_channel(ctx)
        if user.id == spoil['author']:
            await self.bot.say("You can't untrust the author.")
            return
        spoil['trusted'].remove(user.id)
        self.bot.dump_server_configs()
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
        name, spoil = get_channel(ctx)
        message = f'{ctx.message.author.mention} updated {name} in {ctx.message.server.name} with status: "{status}"'
        users = [u for u in ctx.message.server.members if
                 (spoil['role'] in [r.id for r in u.roles]) and
                 u.id != ctx.message.author.id]
        for m in users:
            await self.bot.remove_roles(m, discord.utils.get(ctx.message.server.roles, id=spoil['role_present']))
            await self.bot.send_message(m, message)
        spoil['status'] = status
        self.bot.dump_server_configs()
        await self.bot.affirmative()

    @spoiler.command(pass_context=True, no_pm=True)
    @is_spoiler_channel()
    @is_trusted()
    async def set_status(self, ctx, *, status=None):
        """Set the status of the channel without updating it."""
        name, spoil = get_channel(ctx)
        spoil['status'] = status or "No status listed."
        message = f'{ctx.message.author.mention} changed status {name} in {ctx.message.server.name} to: "{status}"'
        users = [u for u in ctx.message.server.members if
                 (spoil['role'] in [r.id for r in u.roles]) and
                 u.id != ctx.message.author.id]
        for m in users:
            await self.bot.send_message(m, message)
        self.bot.dump_server_configs()
        await self.bot.affirmative()

    @spoiler.command(pass_context=True, name='catchup', no_pm=True)
    async def _catchup(self, ctx, name: str):
        """Call this when you are caught up to regain access to the channel."""
        if name not in [r.name for r in ctx.message.author.roles]:
            await self.bot.say("You are not in that channel.")
            return
        try:
            c = self.bot.server_configs[ctx.message.server.id]['spoilers'][name]
            role_present = discord.utils.get(ctx.message.server.roles, id=c['role_present'])
            await self.bot.add_roles(ctx.message.author, role_present)
            await self.bot.send_message(discord.Object(c['id']), f"{ctx.message.author.display_name} is now caught up on {name}.")
        except KeyError:
            await self.bot.say("not found.")


def setup(bot):
    bot.add_cog(Spoilers(bot))
