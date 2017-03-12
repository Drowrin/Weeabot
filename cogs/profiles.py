import operator
import os
import json
import inspect

import discord
from discord.ext import commands

import utils

from Weeabot import bot

def count_formatter(field):
    maxcoms = 5

    def digits(v):
        return len(str(v))

    def addcom(l, coms):
        if len(l) == maxcoms or len(coms) == 0:
            return l
        i = max(coms, key=coms.get)
        l.append(i)
        return addcom(l, {k: v for k, v in coms.items() if k != i})

    f = addcom([], field)
    if len(f) > 0:
        cw = digits(max([field[x] for x in f]))
        iw = digits(maxcoms)
        return {'name': 'Top Commands', 'content': '\n'.join([f'`|{i + 1:>{iw}}|{field[x]:>{cw}}| {bot.command_prefix}{x}`' for i, x in enumerate(f)])}


def custom_formatter(field):
    return field


def default_formatter(field):
    pass


def level(xp: int):
    return int(xp ** .5)


def stat_default():
    return {'xp': 0}


def command_count_default():
    return {}


class Profile(utils.SessionCog):
    """Profile related commands.

    Only default support is for command count and custom fields.
    Support for specific fields are added by other cogs so that they are disabled."""

    defaults = {'stat': stat_default, 'command_count': command_count_default}
    formatters = {'command_count': count_formatter, 'custom': custom_formatter}
    verbose_formatters = {}

    def __init__(self, bot):
        super(Profile, self).__init__(bot)
        self.path = os.path.join('status', 'profiles.json')
        try:
            with open(self.path, 'r') as f:
                self._db = json.load(f)
        except FileNotFoundError:
            self._db = {}
        for f in bot.tracking_filter:
            for u in self._db:
                if 'command_count' in self._db[u]:
                    self._db[u]['command_count'] = {k: v for k, v in self._db[u]['command_count'].items() if f not in k}
        self.dump()

    def dump(self):
        with open(self.path, 'w') as f:
            json.dump(self._db, f, ensure_ascii=True)

    async def save(self):
        """Save the current data to disk."""
        await self.bot.loop.run_in_executor(None, self.dump)

    def get_by_id(self, uid: str):
        """Get the whole profile sructure of a user by their id. Generates if needed."""
        if uid not in self._db:
            self._db[uid] = {k: v() for k, v in self.bot.defaults.items()}
        return self._db[uid]

    def get_field_by_id(self, uid: str, key: str):
        up = self.get_by_id(uid)
        if key not in up:
            up[key] = self.bot.defaults[key]()
        return up[key]

    async def put_by_id(self, uid: str, key: str, value):
        """Adda a profile, if needed, and edit it."""
        if uid not in self._db:
            self._db[uid] = {}
        self._db[uid][key] = value
        await self.save()

    async def remove_by_id(self, uid: str):
        """Remove a profile from the structure."""
        del self._db[uid]
        await self.save()

    async def remove_field_by_id(self, uid: str, key: str):
        """Remove an element of a profile."""
        del self._db[uid][key]
        await self.save()

    def __contains__(self, item):
        return self._db.__contains__(item)

    def __len__(self):
        return self._db.__len__()

    def all(self):
        return self._db

    async def on_message(self, message):
        """Event listener to record message length."""
        stat = self.get_field_by_id(message.author.id, 'stat')
        stat['xp'] = stat.get('xp', 0) + len(message.clean_content)

    @commands.group(invoke_without_command=True, pass_context=True, name='profile', aliases=('p',))
    async def prof(self, ctx, user: str=None):
        """Show some information on a user.
        
        You can pass in a user, or it will default to you."""
        if ctx.invoked_subcommand is None:
            if user is None:
                usr = ctx.message.author
            else:
                try:
                    usr = commands.MemberConverter(ctx, user).convert()
                except commands.BadArgument as e:
                    await self.bot.say(e)
                    return
            up = self.get_by_id(usr.id)
            e = discord.Embed(
                color=usr.colour,
                timestamp=usr.joined_at,
                description="{} | Level {}".format(usr.top_role, level(up['stat']['xp']))
            )
            e.set_author(name=usr.display_name)
            e.set_thumbnail(url=usr.avatar_url)
            e.set_footer(text="Joined at")
            order = sorted(self.bot.formatters)
            order.reverse()
            for name in order:
                prof = name
                inline = False
                if name.endswith('_inline'):
                    inline = True
                    prof = name[:-len('_inline')]

                try:
                    value = self.bot.formatters.get(name, default_formatter)(up[prof])
                    if inspect.isawaitable(value):
                        value = await value
                except KeyError:
                    value = None

                if value is not None:
                    e.add_field(name=value['name'], value=value['content'], inline=inline)
            await self.bot.say(embed=e)

    @commands.command(pass_context=True)
    async def leaderboard(self, ctx):
        """Leaderboard of active users."""
        members = {k.id: level(self.get_field_by_id(k.id, 'stat').get('xp', 0))
                   for k in ctx.message.server.members if not k.bot}
        top = sorted(members.items(), key=operator.itemgetter(1), reverse=True)[:5]
        names = {k: ctx.message.server.get_member(k).display_name for k, v in top}
        await self.bot.say('```\nLEVEL | NAME\n------------\n{}\n```'.format(
            '\n'.join(['{1:<6}: {0}'.format(names[k], v) for k, v in top])))

    @prof.group(invoke_without_command=True, pass_context=True)
    async def remove(self, ctx, field: str, *users: str):
        """Remove a field from a list of profiles."""
        field = field.strip('\'"')
        if ctx.invoked_subcommand is None:
            if not users:
                usrs = [ctx.message.author]
            else:
                usrs = []
                for user in users:
                    try:
                        usrs.append(commands.MemberConverter(ctx, user).convert())
                    except commands.BadArgument as e:
                        await self.bot.say(e)
            for usr in usrs:
                try:
                    await self.remove_field_by_id(usr.id, field)
                except KeyError as e:
                    await self.bot.say('{} not found in {}.\n{}'.format(field, usr.display_name, e))

    @remove.command(name='all')
    async def _all(self, field: str):
        """Remove a field from all profiles."""
        field = field.strip('\'"')
        for uid in self._db:
            try:
                await self.remove_field_by_id(uid, field)
            except KeyError as e:
                await self.bot.say('{} not found in {}.\n{}'.format(field, uid, e))

    @prof.command(pass_context=True, name='category', aliases=('c',))
    async def _category(self, ctx, cat: str, usr: discord.User=None):
        """Get information on a specific part of a profile."""
        if usr is None:
            usr = ctx.message.author
        if cat in self.bot.verbose_formatters:
            formatter = self.bot.verbose_formatters[cat]
        elif cat in self.bot.formatters:
            formatter = self.bot.formatters[cat]
        else:
            raise commands.BadArgument('{} not found.'.format(cat))
        if cat not in self.get_by_id(usr.id):
            raise commands.BadArgument('{} not found for {}.'.format(cat, usr.display_name))
        try:
            f = []
            formatter(ctx, self.get_by_id(usr.id)[cat], f)
            await self.bot.say(f[0])
        except IndexError:
            await self.bot.say("None.")


def setup(bot):
    bot.add_cog(Profile(bot))
