import json
import discord
import operator
from discord.ext import commands
from utils import *


def count_formatter(ctx, field, fields):
    top_command = max(field, key=field.get)
    fields.append('Most used command: ({}) {}'.format(field[top_command], top_command))


def custom_formatter(ctx, field, fields):
    fields.append('Cusomt fields: {}'.format(field))


def default_formatter(ctx, field, fields):
    pass


def level(xp: int):
    return int(xp ** .5)


class Profile(SessionCog):
    """Profile related commands.

    Only default support is for command count and custom fields.
    Support for specific fields are added by other cogs so that they are disabled."""

    formatters = {'command_count': count_formatter, 'custom': custom_formatter}
    verbose_formatters = {}

    def __init__(self, bot):
        super(Profile, self).__init__(bot)
        self.path = 'profiles.json'
        try:
            with open(self.path, 'r') as f:
                self._db = json.load(f)
        except FileNotFoundError:
            self._db = {}

    def _dump(self):
        with open(self.path, 'w') as f:
            json.dump(self._db, f, ensure_ascii=True)
    
    async def save(self):
        """Save the current data to disk."""
        await self.bot.loop.run_in_executor(None, self._dump)
    
    def get_by_id(self, uid: str):
        """Get the whole profile sructure of a user by their id. Generates if needed."""
        if uid not in self._db:
            self._db[uid] = {'stat': {'xp': 0}}
        return self._db[uid]
    
    def get_field_by_id(self, uid: str, key: str):
        up = self.get_by_id(uid)
        if key not in up:
            up[key] = {}
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
    
    async def inc_use(self, uid: str, func: str):
        cc = self.get_field_by_id(uid, 'command_count')
        if func not in cc:
            cc[func] = 0
        cc[func] += 1
        await self.put_by_id(uid, 'command_count', cc)
    
    async def on_command_completion(self, command, ctx):
        """Event listener for command_completion."""
        await self.inc_use(ctx.message.author.id, full_command_name(ctx, command))
    
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
            up = self._db[usr.id]
            fields = ['**{}**\nLevel {}\n{}\n\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~'.format(
                usr.display_name, level(up['stat']['xp']), usr.top_role)]
            try:
                for name, field in up.items():
                    self.bot.formatters.get(name, default_formatter)(ctx, field, fields)
            except commands.BadArgument as e:
                await self.bot.say(e)
                return
            fields.append('\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~')
            with await download_fp(self.session, usr.avatar_url) as fp:
                await self.bot.upload(fp, filename='avatar.png', content='\n'.join(fields))

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

    @remove.command()
    async def all(self, field: str):
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
