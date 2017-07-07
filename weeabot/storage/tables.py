from sqlalchemy import func, Column, Table, ForeignKey, BigInteger, Integer, String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import relationship, Session


__all__ = ('User', 'CommandUsage', 'Guild', 'Poll', 'Channel', 'Stub', 'Tag')


class _Base:
    """
    Base functionality of tables.
    """

    id = Column(Integer, primary_key=True)

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    def __repr__(self, **kwargs):
        return "<{} {}>".format(type(self).__name__, ' '.join(["{}={}".format(k, v) for k, v in kwargs.items()]))

    def __str__(self):
        return self.__repr__()


Base = declarative_base(cls=_Base)


class DiscordObject:
    """
    Common functionality of discord objects.
    """
    id = Column(BigInteger, primary_key=True, autoincrement=False, unique=True)

    @property
    def bot(self):
        s = Session.object_session(self)
        return s.bot  # set right after session creation

    def __repr__(self, **kwargs):
        if 'id' not in kwargs:
            kwargs['id'] = self.id
        return super(DiscordObject, self).__repr__(**kwargs)

    def get(self):
        """
        Get the corresponding discord.py object.
        """
        getter = getattr(self.bot, f"get_{self.__tablename__}")
        return getter(self.id)


class CommandUsage(Base):
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
    #channels = relationship("Channel", back_populates="guild", cascade="all, delete, delete-orphan")

    poll_channel_id = Column(BigInteger, ForeignKey('channel.id'))
    poll_channel = relationship("Channel", foreign_keys=[poll_channel_id])
    polls = relationship("Poll", back_populates="guild",
                         cascade="all, delete, delete-orphan")

    twitch_channel_id = Column(BigInteger, ForeignKey('channel.id'))
    twitch_channel = relationship("Channel", foreign_keys=[twitch_channel_id])

    jail_id = Column(BigInteger, ForeignKey('channel.id'))
    jail = relationship("Channel", foreign_keys=[jail_id])

    stubs = relationship("Stub", back_populates='guild')


class Poll(Base):
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
    #guild_id = Column(BigInteger, ForeignKey('guild.id'))
    #guild = relationship("Guild", back_populates="channels", foreign_keys=[guild_id])
    hidden = Column(Boolean, nullable=False, default=False)
    twitter = Column(String)
    spoiler = Column(Boolean, nullable=False, default=False)
    spoiler_members = Column(ARRAY(BigInteger, dimensions=1))
    spoiler_trusted = Column(ARRAY(BigInteger, dimensions=1))
    spoiler_creator = Column(BigInteger)
    spoiler_status = Column(String)


# association table to create many-to-many relationship
tag_association_table = Table(
    'association',
    Base.metadata,
    Column('stub_id', ForeignKey('stub.id'), primary_key=True),
    Column('tag_id', ForeignKey('tag.id'), primary_key=True)
)


class Stub(Base):
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
    stubs = relationship(
        'Stub',
        secondary=tag_association_table,
        back_populates='tags'
    )

    name = Column(String, nullable=False, unique=True)
