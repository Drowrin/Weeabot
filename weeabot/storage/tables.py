from datetime import datetime

import discord

from sqlalchemy import func, Column, Table, ForeignKey, BigInteger, Integer, String, Boolean, DateTime, Text, PickleType
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import relationship, Session, reconstructor

from ..cogs.requestsystem import PermissionLevel


__all__ = ('Base', 'User', 'CommandUsage', 'Guild', 'JailSentence', 'Poll', 'Channel', 'TweetStream', 'Spoiler', 'Stub', 'Tag',
           'Reminder', 'Request')


class _Base:
    """
    Base functionality of tables.
    """

    @property
    def __repr_props__(self):
        """
        An iterable defining what properties to expose in __repr__.
        Defaults to everything. Override in subclasses to change this behavior.
        """
        return self.__mapper__.columns.keys()

    id = Column(Integer, primary_key=True)

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    def __repr__(self):
        return "<{} {}>".format(type(self).__name__, ' '.join(["{}={}".format(k, getattr(self, k)) for k in self.__repr_props__]))

    def __str__(self):
        return self.__repr__()


Base = declarative_base(cls=_Base)


class DiscordObject:
    """
    Common functionality of discord objects.
    """
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=False, unique=True)

    @reconstructor
    def on_load(self):
        self.bot = Session.object_session(self).bot

    def get(self):
        """
        Get the corresponding discord.py object.
        """
        getter = getattr(self.bot, f"get_{self.__tablename__}")
        return getter(self.id)


class CommandUsage(Base):
    """
    For tracking how commands are used.
    """
    user_id = Column(BigInteger, ForeignKey('user.id'))
    user = relationship("User", back_populates="usage")
    name = Column(String, nullable=False)
    count = Column(Integer, nullable=False, default=0)


class User(DiscordObject, Base):
    """
    Representation of a User.
    """
    xp = Column(Integer, nullable=False, default=0)

    twitch = Column(String, nullable=True)
    ffxiv = Column(String, nullable=True)
    mal = Column(String, nullable=True)
    mwl = Column(String, nullable=True)

    usage = relationship("CommandUsage", order_by=CommandUsage.count,
                         back_populates="user", cascade="all, delete, delete-orphan")

    stubs = relationship('Stub', back_populates='author')

    def get_member(self, guild):
        """
        Get the corresponding member to this user in the specified guild.
        guild just needs to have a .id attribute, so it can be either tables.Guild or discord.Guild
        """
        return self.bot.get_guild(guild.id).get_member(self.id)


class Guild(DiscordObject, Base):
    """
    Representation of a Guild.
    """
    # channels = relationship("Channel", back_populates="guild", cascade="all, delete, delete-orphan")

    poll_channel_id = Column(BigInteger, ForeignKey('channel.id'))
    poll_channel = relationship("Channel", foreign_keys=[poll_channel_id])
    polls = relationship("Poll", back_populates="guild",
                         cascade="all, delete, delete-orphan")

    twitch_channel_id = Column(BigInteger, ForeignKey('channel.id'))
    twitch_channel = relationship("Channel", foreign_keys=[twitch_channel_id])

    jail_id = Column(BigInteger, ForeignKey('channel.id'))
    jail = relationship("Channel", foreign_keys=[jail_id])
    jail_role_id = Column(BigInteger)
    jail_sentences = relationship("JailSentence", back_populates="guild")

    stubs = relationship("Stub", back_populates='guild')


class JailSentence(Base):
    """
    Describes how long a member has been sentenced to jail.
    """
    guild_id = Column(BigInteger, ForeignKey('guild.id'))
    guild = relationship("Guild", back_populates="jail_sentences")

    user = Column(BigInteger)
    finished = Column(DateTime)


class Poll(Base):
    """
    Reprisents a poll running in this guild's poll channel.
    """
    guild_id = Column(BigInteger, ForeignKey('guild.id'))
    guild = relationship("Guild", back_populates="polls")
    author_id = Column(BigInteger, ForeignKey('user.id'))
    author = relationship("User")
    start = Column(DateTime, nullable=False, server_default=func.now())
    question = Column(String, nullable=False)
    answers = Column(ARRAY(String, dimensions=1))
    type = Column(String, nullable=False)
    results = Column(ARRAY(BigInteger, dimensions=2))


class Channel(DiscordObject, Base):
    """
    Representation of a Channel.
    """
    # These aren't really necessary due to `DiscordObject.get()`
    # guild_id = Column(BigInteger, ForeignKey('guild.id'))
    # guild = relationship("Guild", back_populates="channels", foreign_keys=[guild_id])
    hidden = Column(Boolean, nullable=False, default=False)
    tweetstreams = relationship("TweetStream", back_populates="channel")
    spoiler = relationship("Spoiler", uselist=False, back_populates="channel")


class TweetStream(Base):
    """
    Contains information necessary to repost tweets to a channel.
    """
    channel_id = Column(BigInteger, ForeignKey('channel.id'))
    channel = relationship("Channel", back_populates="tweetstreams")
    twitter_id = Column(BigInteger)
    last_tweet = Column(String)


spoiler_association_table = Table(
    'spoiler_association', Base.metadata,
    Column('spoiler_id', Integer, ForeignKey('spoiler.id')),
    Column('user_id', BigInteger, ForeignKey('user.id'))
)


class Spoiler(Base):
    """
    Contains information necessary to the operation of a spoiler channel.
    """
    channel_id = Column(BigInteger, ForeignKey('channel.id'))
    channel = relationship("Channel", back_populates="spoiler")
    members = relationship("User", secondary=spoiler_association_table)
    creator = Column(BigInteger)
    status = Column(String)


# association table to create many-to-many relationship
tag_association_table = Table(
    'tag_association',
    Base.metadata,
    Column('stub_id', ForeignKey('stub.id'), primary_key=True),
    Column('tag_id', ForeignKey('tag.id'), primary_key=True)
)


class Stub(Base):
    """
    User defined and organized content.
    """
    tags = relationship(
        'Tag',
        secondary=tag_association_table,
        back_populates='stubs'
    )

    author_id = Column(BigInteger, ForeignKey('user.id'))
    author = relationship("User", back_populates='stubs')

    timestamp = Column(DateTime)
    text = Column(Text)
    image = Column(String)
    method = Column(String)

    guild_id = Column(BigInteger, ForeignKey('guild.id'))
    guild = relationship("Guild", back_populates='stubs')


class Tag(Base):
    """
    Used to organize and access Stubs.
    """
    stubs = relationship(
        'Stub',
        secondary=tag_association_table,
        back_populates='tags'
    )

    name = Column(String, nullable=False, unique=True)


class Reminder(Base):
    """
    A reminder sent to a user after a specified time.
    """
    channel_id = Column(BigInteger, ForeignKey('channel.id'))
    channel = relationship("Channel")

    finished = Column(DateTime)

    user_id = Column(BigInteger, ForeignKey('user.id'))
    user = relationship("User")

    message = Column(String)


class Request(Base):
    """
    Represents a request made through cogs.requestsystem
    """
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=False, unique=True)
    level = Column(Integer)
    current_level = Column(Integer, default=0)
    status_message = Column(BigInteger)

    @property
    def approved(self):
        return self.current_level >= self.level

    async def get_message(self):
        return await self.bot.get_message(self.id)

    async def get_status_message(self):
        try:
            return await self.bot.get_message(self.status_message)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

    async def send_status(self):
        m = await self.get_message()
        s = "{} your request has been elevated! Status: {}/{}".format(
            m.author.mention, PermissionLevel(self.current_level).name, PermissionLevel(self.level).name
        )
        sm = await self.get_status_message()
        if sm is None:
            sm = await m.channel.send(s)
        else:
            await sm.edit(s)
        return sm
