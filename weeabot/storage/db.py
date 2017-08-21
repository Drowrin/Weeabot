import random
import discord
from asyncio_extras import threadpool, async_contextmanager
from sqlalchemy import engine, orm, and_, or_, func
from typing import List
from datetime import datetime
from .tables import *


class DBHelper:
    """
    Collection of async helper functions for accessing the database.
    """

    def __init__(self, dsn, bot):
        self.dsn = dsn
        self.bot = bot
        # Will be set on once prepaired
        self._engine: engine = None
        self._make_session = None

    async def prepare(self):
        """
        Prepare the db for use. Required before anything else.
        """
        async with threadpool():
            self._engine: engine = engine.create_engine(self.dsn)
            Base.metadata.create_all(self._engine)
            self._make_session = orm.sessionmaker(bind=self._engine, expire_on_commit=False)

    @async_contextmanager
    async def session(self):
        """
        Yields a session to access the db.
        """
        s = self._make_session()
        s.bot = self.bot
        try:
            yield s
            s.commit()
        except:
            s.rollback()
            raise
        finally:
            s.close()

    @async_contextmanager
    async def get_user(self, user: discord.User):
        """
        Get a user's profile from the database. Will create a row if nonexistent.
        """
        async with self.session() as s:
            u = s.query(User).filter(User.id == user.id).first()
            if u is None:
                u = User(id=user.id)
                s.add(u)

            yield u

    async def inc_xp(self, user: discord.User):
        """
        Increments a user's xp.
        """
        async def task():
            async with self.get_user(user) as u:
                u.xp = (u.xp or 0) + 1
        await self.bot.loop.create_task(task())

    async def create_profile_field(self, user: discord.User, key, value):
        """
        GCreate a profile field.
        """
        async with threadpool(), self.session() as s:
            p = ProfileField(
                user_id=user.id,
                key=key,
                value=value
            )
            s.add(p)
        return p

    @async_contextmanager
    async def get_profile_field(self, user: discord.User, key):
        """
        Get a profile field or None.
        """
        async with self.session() as s:
            yield s.query(ProfileField).filter(
                ProfileField.user_id == user.id,
                ProfileField.key == key
            ).first()

    async def create_twitch_user(self, user_id: int, twitch_id: int, name: str):
        """
        Create a twitch user from all 3 fields.
        """
        async with threadpool(), self.session() as s:
            t = TwitchUser(
                user_id=user_id,
                twitch_id=twitch_id,
                name=name
            )
            s.add(t)
            return t

    async def get_twitch_by_user(self, user: discord.User):
        """
        Get twitch info based on user.
        """
        async with threadpool(), self.session() as s:
            return s.query(TwitchUser).filter(TwitchUser.user_id == user.id).first()

    async def get_twitch_by_id(self, id: int):
        """
        Get twitch info by twitch id.
        """
        async with threadpool(), self.session() as s:
            return s.query(TwitchUser).filter(TwitchUser.twitch_id == id).first()

    async def get_twitch_by_name(self, name: str):
        """
        Get twitch info by twitch username.
        """
        async with threadpool(), self.session() as s:
            return s.query(TwitchUser).filter(func.lower(TwitchUser.name) == func.lower(name)).first()

    async def get_all_twitch_users(self):
        """
        Get all twitch users.
        """
        async with threadpool(), self.session() as s:
            return s.query(TwitchUser).all()

    @async_contextmanager
    async def get_guild(self, guild: discord.Guild):
        """
        Get a guild from the database. Will create a row if nonexistent.
        """
        async with self.session() as s:
            g = s.query(Guild).filter(Guild.id == guild.id).first()
            if g is None:
                g = Guild(id=guild.id)
                s.add(g)

            yield g

    async def get_top_users(self, guild: discord.Guild, limit: int=5):
        """
        Get the top users for the specified guild.
        """
        async with threadpool(), self.session() as s:
            return {
                u.get_member(guild): u.xp
                for u in
                s.query(User).
                    filter(User.id.in_([m.id for m in guild.members])).
                    order_by(User.xp.desc()).
                    limit(limit)
            }

    async def set_jail_role(self, guild: discord.Guild, role: discord.Role):
        """
        Sets the specified guild's jail role.
        """
        async with threadpool(), self.get_guild(guild) as g:
            g.jail_role_id = role.id

    async def set_jail_channel(self, guild: discord.Guild, channel: discord.TextChannel):
        """
        Sets the specified guild's jail channel.
        """
        async with threadpool(), self.session() as s:
            g = s.query(Guild).filter(Guild.id == guild.id).first()
            if g is None:
                g = Guild(id=guild.id)
                s.add(g)
            c = s.query(Channel).filter(Channel.id == channel.id).first()
            if c is None:
                c = Channel(id=channel.id)
                s.add(c)
            g.jail = c

    @async_contextmanager
    async def get_jail(self, guild: discord.Guild, user: discord.User):
        """
        Get a jail based on a guild and a user.
        """
        async with self.session() as s:
            yield s.query(JailSentence).\
                options(orm.joinedload(JailSentence.guild)).\
                filter(JailSentence.user == user.id, JailSentence.guild_id == guild.id).first()

    async def get_all_jails(self):
        """
        Get all the jail sentences from all guilds. Used at bot startup/cog-reload.
        """
        async with self.session() as s:
            return s.query(JailSentence).options(orm.joinedload(JailSentence.guild)).all()

    async def delete_jail(self, jail: JailSentence):
        """
        Remove a JailSentence from the db.
        """
        async with self.session() as s:
            s.delete(jail)

    @async_contextmanager
    async def get_channel(self, channel: discord.TextChannel):
        """
        Get a channel from the database. Will create a row if nonexistent
        """
        async with self.session() as s:
            c = s.query(Channel).filter(Channel.id == channel.id).first()
            if c is None:
                c = Channel(id=channel.id)
                s.add(c)

            yield c

    @async_contextmanager
    async def get_poll(self, id):
        """
        Get a Poll by id. Does not create missing rows.
        """
        async with self.session() as s:
            yield s.query(Poll).filter(Poll.id == id).first()

    async def inc_command_usage(self, user, name):
        """
        Increment the command usage count of a particular user and command.
        """
        async def task():
            async with self.session() as s:
                usage = s.query(CommandUsage).filter(CommandUsage.user_id == user.id).filter(
                    CommandUsage.name == name).first()

                if usage is None:
                    u = s.query(User).filter(User.id == user.id).first()

                    if u is None:
                        u = User(id=user.id)
                        s.add(u)

                    usage = CommandUsage(user=u, name=name, count=0)
                    u.usage.append(usage)

                usage.count += 1
        await self.bot.loop.create_task(task())

    @async_contextmanager
    async def get_total_usage(self, name):
        """
        Get a list of all CommandUsage objects for a command.
        """
        async with self.session() as s:
            yield s.query(CommandUsage).filter(CommandUsage.name == name).all()

    async def get_user_usage(self, user: discord.User):
        """
        Get a dictionary of command name --> usage count for this user.
        """
        async with self.session() as s:
            usages = s.query(CommandUsage).filter(CommandUsage.user_id == user.id).all()
            return {u.name: u.count for u in usages}

    async def create_stub(self, author: discord.User, tags: List[str], timestamp: datetime, guild: discord.Guild,
                          text: str=None, image: str=None, method: str=None, is_global=False):
        """
        Create a stub from all properties.
        """
        if len(tags) == 0:
            raise TypeError("missing argument(s): tags")
        async with threadpool(), self.session() as s:
            tags = [await self.get_tag(t, s=s) for t in tags]
            u = s.query(User).filter(User.id == author.id).first()
            if u is None:
                u = User(id=author.id)
                s.add(u)
            g = s.query(Guild).filter(Guild.id == guild.id).first()
            if g is None:
                g = Guild(id=guild.id)
                s.add(g)
            stub = Stub(
                author=u,
                timestamp=timestamp,
                origin_guild_id=guild.id,
                guilds=[g],
                is_global=is_global,
                tags=tags,
                text=text,
                image=image,
                method=method
            )
            s.add(stub)
            return stub

    async def set_stub_image(self, stub_id: int, path: str):
        """
        Set the image path of a stub.
        """
        async with threadpool(), self.session() as s:
            stub = s.query(Stub).filter(Stub.id == stub_id).first()
            stub.image = path

    @async_contextmanager
    async def get_specific_stub(self, guild, stub_id):
        """
        Get a specific stub by id. Does not create missing rows.
        """
        async with self.session() as s:
            yield s.query(Stub).join(Stub.guilds).filter(
                Stub.id == stub_id,
                or_(Guild.id == guild.id, Stub.is_global)
            ).first()

    @async_contextmanager
    async def get_random_stub(self, guild, *tags, force_images=False):
        """
        Get a random stub with the given tags. Can return None
        """
        async with self.session() as s:
            filters = [Stub.tags.any(name=t) for t in tags]
            if force_images:
                filters.append(Stub.image != None)
            stubs = s.query(Stub).join(Stub.guilds).filter(*filters, or_(Guild.id == guild.id, Stub.is_global))
            count = int(stubs.count())
            if count != 0:
                yield stubs.offset(random.randrange(0, count)).first()

    async def get_stubs(self, guild, *tags, limit=1, force_images=False):
        """
        Get a collection of stubs based on tags. Can return an empty list.
        """
        async with threadpool(), self.session() as s:
            filters = [Stub.tags.any(name=t) for t in tags]
            if force_images:
                filters.append(Stub.image != None)
            stubs = s.query(Stub).join(Stub.guilds).filter(*filters, or_(Guild.id == guild.id, Stub.is_global))
            return stubs.order_by(func.random()).limit(limit).all()

    async def make_stub_global(self, stub_id):
        """
        Set the global status of a stub.
        """
        async with threadpool(), self.session() as s:
            stub = s.query(Stub).filter(Stub.id == stub_id).first()
            stub.is_global = True

    async def delete_stub(self, stub_id):
        """
        Delete a stub.
        """
        async with threadpool(), self.session() as s:
            stub = s.query(Stub).filter(Stub.id == stub_id).first()
            s.delete(stub)

    async def get_tag(self, name, s=None):
        """
        Get a specific tag by name. Creates missing rows.
        """
        if s is None:
            async with threadpool(), self.session() as session:
                return await self.get_tag(name, s=session)

        t = s.query(Tag).filter(Tag.name == name).first()

        if t is None:
            t = Tag(name=name)
            s.add(t)
        return t

    async def get_tags_in(self, guild: discord.Guild):
        """
        Get the tags visible to this guild. Includes globals.
        """
        async with threadpool(), self.session() as s:
            return s.query(Tag).join('stubs', 'guilds').filter(or_(Guild.id == guild.id, Stub.is_global)).all()

    @async_contextmanager
    async def get_request(self, message_id):
        """
        Get a request from the db. Does not create new entries.
        """
        async with self.session() as s:
            yield s.query(Request).filter(Request.message == message_id).first()

    async def get_request_from_status(self, message_id):
        """
        Get a request from the db. Does not create new entries. Can return None.
        """
        async with self.session() as s:
            r = s.query(Request).filter(Request.status_message == message_id).first()
            return r.message if r is not None else None

    @async_contextmanager
    async def get_or_create_request(self, ctx, level, status_message=None):
        """
        Create a request based on context. Creates missing entries.
        """
        async with self.session() as s:
            r = s.query(Request).filter(Request.message == ctx.message.id).first()
            if r is None:
                r = Request(
                    message=ctx.message.id,
                    user_id=ctx.author.id,
                    channel=ctx.channel.id,
                    guild=ctx.guild.id,
                    level=level.value,
                    current_level=0,
                    status_message=status_message.id if status_message is not None else None
                )
                s.add(r)
            yield r

    @async_contextmanager
    async def get_or_create_guild_config(self, guild: discord.Guild, key):
        """
        Get a guild config. Creates missing entries.
        """
        async with self.session() as s:
            c = s.query(GuildSetting).filter(
                GuildSetting.guild_id == guild.id,
                GuildSetting.key == key
            ).first()
            if c is None:
                c = GuildSetting(
                    guild_id=guild.id,
                    key=key,
                    value=self.bot.guild_configs[key].default
                )
                s.add(c)
            yield c

    async def get_guild_config(self, guild: discord.Guild, key):
        """
        Get a guild config or None.
        """
        async with threadpool(), self.session() as s:
            return s.query(GuildSetting).filter(
                GuildSetting.guild_id == guild.id,
                GuildSetting.key == key
            ).first()
