import random
import discord
from asyncio_extras import threadpool, async_contextmanager
from sqlalchemy import engine, orm
from .tables import *


class DBHelper:
    """
    Collection of async helper functions for accessing the database.
    """

    def __init__(self, dsn, bot):
        self.dsn = dsn
        self.bot = bot
        # Will be set on once prepaired
        self._engine = None
        self._make_session = None

    async def prepare(self):
        """
        Prepare the db for use. Required before anything else.
        """
        async with threadpool():
            self._engine = engine.create_engine(self.dsn)
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

    @async_contextmanager
    async def get_channel(self, channel: discord.TextChannel):
        """
        Get a channel from the database. Will create a row if nonexistent
        """
        async with self.session() as s:
            c = s.query(Channel).filter(Channel.id == channel.id).first()
            if c is None:
                g = s.query(Guild).filter(Guild.id == channel.guild.id).first()
                if g is None:
                    g = Guild(id=channel.guild.id)
                    s.add(g)
                c = Channel(id=channel.id)
                s.add(c)
                g.channels.append(c)

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

    @async_contextmanager
    async def get_total_usage(self, name):
        """
        Get a list of all CommandUsage objects for a command.
        """
        async with self.session() as s:
            yield s.query(CommandUsage).filter(CommandUsage.name == name).all()

    @async_contextmanager
    async def get_specific_stub(self, id):
        """
        Get a specific stub by id. Does not create missing rows.
        """
        async with self.session() as s:
            yield s.query(Stub).filter(Stub.id == id).first()

    @async_contextmanager
    async def get_tag(self, name):
        """
        Get a specific tag by name. Creates missing rows.
        """
        async with self.session() as s:
            t = s.query(Tag).filter(Tag.name == name).first()

            if t is None:
                t = Tag(name)
                s.add(t)

            yield t

    @async_contextmanager
    async def get_random_stub(self, *tags):
        """
        Get a random stub with the given tags. Can return None
        """
        async with self.session() as s:
            filters = [Stub.tags.any(name=t) for t in tags]
            stubs = s.query(Stub).filter(*filters).all()
            yield random.choice(stubs) if stubs else None
