import re
import sys
from traceback import format_exc
from copy import copy
from datetime import datetime
from typing import List
from asyncio_extras import threadpool

from sqlalchemy.orm.session import object_session
from sqlalchemy import or_

import discord
from discord.ext import commands

from ._base import base_cog
from ..storage.tables import Guild, Stub as DBStub
from .requestsystem import request, PermissionLevel


class Stub:
    """
    Provides helper functions for stub data.
    """

    def __init__(self, stub: DBStub, bot=None):
        if stub is None:
            raise ValueError('No stub passed.')

        self.bot: commands.Bot = bot or object_session(stub).bot

        # stub data
        self.id: int = stub.id
        self.author: int = stub.author_id
        self.tags: List[str] = [t.name for t in stub.tags]
        self.origin_guild: discord.Guild = self.bot.get_guild(stub.origin_guild_id)
        self.guilds: List[discord.Guild] = [self.bot.get_guild(g.id) for g in stub.guilds]
        self.is_global: bool = stub.is_global
        self.timestamp: datetime = stub.timestamp
        self.text: str = stub.text
        self.image: str = stub.image
        self.method: str = stub.method

        # some methods take advantage of this.
        # set after creation externally. methods using this should be aware.
        self.calling_message: discord.Message = None

    def author_in(self, dest: discord.abc.Messageable) -> discord.User:
        """
        Get the Member object for the author in the given destination.
        This ensures, for example, that nicknames function in Guilds.
        """
        if isinstance(dest, discord.TextChannel):
            return dest.guild.get_member(self.author)
        if isinstance(dest, (discord.DMChannel, discord.GroupChannel)):
            return self.bot.get_user(self.author)

    async def send_to(self, destination: discord.abc.Messageable) -> discord.Message:
        """
        Send this tag as an embed to the specified destination.
        """
        author = self.author_in(destination)
        e = discord.Embed(description=f'ERROR METHOD NOT FOUND {self.method}')
        c: str = None

        # emote converter, for legacy tag data
        # unconverted_emotes = set(re.findall(r':\w+:', self.text))
        # for emote in unconverted_emotes:
        #     rep = discord.utils.get(self.bot.emojis, name=emote[1:-1])
        #     if rep is not None:
        #         self.text = self.text.replace(emote, f'<:{rep.name}:>')

        if self.method is None:  # default case
            e = discord.Embed(
                description=self.text,
                timestamp=self.timestamp
            ).set_footer(
                text=f"{self.id} — {', '.join(self.tags)}"
            )

            if author is not None:
                e.set_author(
                    name=author.display_name,
                    icon_url=author.avatar_url
                )

            if self.image is not None:
                e.set_image(url=self.image)
        elif self.method == 'simple':
            print(self.text)
            e = discord.Embed(
                description=self.text
            ).set_footer(
                text=f"{self.id} — {', '.join(self.tags)}"
            )

        return await destination.send(embed=e, content=c)


class Tags(base_cog(shortcut=True, session=True)):
    """
    Tags that describe content called Stubs.
    Stubs can contain many things, from images, to text, to commands.
    Stubs are limited to the guild they were created in by default.
    Rather than re-adding a tag in another guild, it is best to give it access there.
    """

    @staticmethod
    def valid_tag(t: str) -> bool:
        return bool(re.match(r'^[A-za-z0-9_\-]+$', t))

    async def get(self, guild: discord.Guild, *tags, stub_id: int=None) -> Stub:
        """
        Get a Stub based on tags or optionally by id.

        If a stub_id is passed, tags will be ignored.
        If either the id or the tag combination does not exist, will return nothing.
        """
        try:
            if stub_id is not None:
                async with threadpool(), self.bot.db.get_specific_stub(guild, stub_id) as stub:
                    return Stub(stub)
            else:
                async with threadpool(), self.bot.db.get_random_stub(guild, *tags) as stub:
                    return Stub(stub)
        except StopAsyncIteration:
            # tag not found. potentially show near matches? TODO
            pass

    async def create(self, message: discord.Message, *tags: List[str], method: str=None, is_global: bool=False, image=None):
        """
        Creates a stub from a message, tags, and the optional method and is_global.
        The message object should be in the state it will be stored in. Command calls and such will not be stripped.
        """
        link = image or message.attachments[0].url if message.attachments else None

        stub = await self.bot.db.create_stub(
            author=message.author,
            tags=tags,
            timestamp=message.created_at,
            guild=message.guild,
            text=message.content,
            method=method,
            is_global=is_global
        )
        if link is not None:
            await self.bot.db.set_stub_image(stub.id, link)
            stub.image = link
        return Stub(stub, bot=self.bot)

    async def parse_and_get(self, guild: discord.Guild, *args: List[str]) -> Stub:
        """
        Wrapper for Tags.get to parse the args for ids and default to the first id passed, if any.
        """
        for a in args:
            if a.isnumeric():
                return await self.get(guild, stub_id=int(a))
        return await self.get(guild, *args)

    @commands.group(aliases=('tag', 'tags'), name='stub', invoke_without_command=True)
    async def _stub(self, ctx, *tags_or_id):
        """
        Get a random stub with the specified tags or id.
        If multiple tags are passed, only stubs with *all* of these tags are returned.
        """
        try:
            t = await self.parse_and_get(ctx.guild, *tags_or_id)
            if t is not None:
                await t.send_to(ctx.channel)
            else:
                raise commands.BadArgument(message='No stub found.')
        except (ValueError, AttributeError):
            print(format_exc(), file=sys.stderr)
            raise commands.BadArgument(message='No stub found.')

    @_stub.group(name='add', invoke_without_command=True)
    async def _stub_add(self, ctx: commands.Context, tag_name: str, *, text: str=''):
        """
        [Legacy] Add a stub with a specified tag.

        The first word after 'add' will be the tag used, and the rest of the message will be included in the stub.
        Image attachments will be saved but will require approval.
        """
        if not ctx.invoked_subcommand:
            m = copy(ctx.message)
            m.content = text
            t = await self.create(m, tag_name)
            await t.send_to(ctx.channel)

    @_stub_add.command(name='raw', hidden=True)
    @request(level=PermissionLevel.GLOBAL)
    async def _stub_add_raw(self, ctx, text: str, image: str, method: str, is_global: bool, *tags: str):
        """
        Add a stub using very specific syntax. Not recommended to use directly.

        The calling message will be used for permission resolution, but the contents will determine stub contents.
        """
        m = copy(ctx.message)
        m.content = text
        t = await self.create(
            m, *tags,
            method=method or None,
            is_global=is_global or False,
            image=image or None
        )
        await t.send_to(ctx.channel)

    @_stub_add.command(name='message', aliases=('m',))
    async def _stub_add_message(self, ctx: commands.Context, message_id: int, *tags: str):
        """
        Add a message as a stub with tags specified in this command call.
        """
        if any(not self.valid_tag(t) for t in tags):
            await ctx.send('Tags must only contain numbers, letters, - and _.')
            return

        # seemingly roundabout system is really to funnel things through more readable requests
        m = copy(await ctx.channel.get_message(message_id))
        m.content = '{}stub add raw "{}" "" "" False {}'.format(
            ctx.prefix,
            m.content,
            ' '.join(tags)
        )
        await self.bot.process_commands(m)

    @_stub.command(name='list')
    async def _stub_list(self, ctx: commands.Context):
        """
        List the tags that are available here.
        """
        await ctx.send(', '.join(t.name for t in await self.bot.db.get_tags_in(ctx.guild)))

    @_stub.command()
    @request(level=PermissionLevel.GLOBAL)
    async def credit(self, ctx: commands.Context, stub_id: int, user: discord.User):
        """
        Credits a user with creation of a stub.
        """
        async with threadpool(), self.bot.db.get_user(user) as u:
            s = object_session(u)
            stub = s.query(DBStub).join(DBStub.guilds).filter(
                DBStub.id == stub_id,
                or_(Guild.id == ctx.guild.id, DBStub.is_global)
            ).first()
            stub.author = u

    @staticmethod
    def stub_bypass(ctx: commands.Context):
        if ctx.invoked_with == 'help':
            return True  # Always display in help since no args are passed.
        if ctx.bot.owner == ctx.author:
            return True  # Always allow owner to delete
        # everything else will depend on the particular stub, so it should be done in the command

    @_stub.command(name='delete', aliases=('remove',))
    @request(bypass=stub_bypass)
    async def _stub_delete(self, ctx, stub_id: int):
        """
        Delete a stub.

        Can be performed by the author or moderators.
        """
        if ctx.bypassed:
            await self.bot.db.delete_stub(stub_id)
        else:
            async with threadpool(), self.bot.db.get_specific_stub(ctx.guild, stub_id) as s:
                if s is None:
                    raise commands.CheckFailure(f"{stub_id} not found in this guild.")
                if ctx.request_approved or ctx.author.guild_permissions.manage_guild or s.author_id == ctx.author.id:
                    s.delete()
                else:
                    raise commands.CheckFailure(f"You do not have permission to do that.")
        await ctx.affirmative()

    @_stub.command(name='method')
    @request(bypass=stub_bypass)
    async def _stub_method(self, ctx, stub_id: int, *, method: str):
        """
        Set the method this stub uses.
        """
        async with threadpool(), self.bot.db.get_specific_stub(ctx.guild, stub_id) as s:
            if s is None:
                raise commands.CheckFailure(f"{stub_id} not found in this guild.")
            if ctx.request_approved or ctx.bypassed or ctx.author.guild_permissions.manage_guild or s.author_id == ctx.author.id:
                s.method = method
            else:
                raise commands.CheckFailure(f"You do not have permission to do that.")
        await ctx.affirmative()


def setup(bot):
    bot.add_cog(Tags(bot))
