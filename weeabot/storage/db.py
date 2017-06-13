import discord
from asyncio_extras import threadpool, async_contextmanager
from sqlalchemy import Column, engine, orm
from .tables import User

class DBHelper:
    """
    Collection of async helper functions for accessing the database.
    """

    def __init__(self, dsn):
        self.dsn = dsn
        # Will be set on once prepaired
        self._make_session = None

    async def prepare(self):
        """
        Prepare the db for use. Required before anything else.
        """
        async with threadpool():
            e = engine.create_engine(self.dsn)
            self._make_session = orm.sessionmaker(bind=e)

    @async_contextmanager
    async def session(self):
        """
        Yields a session to access the db, and runs code in an executor.
        """
        async with threadpool():
            s = self._make_session()
            try:
                yield s
                s.commit()
            except:
                s.rollback()
                raise
            finally:
                s.close()

    async def get_user(self, user: discord.User):
        """
        Get a user's profile from the database. Will create if nonexistent.
        """
        async with self.session() as s:
            u = s.query(User).filter(User.id == user.id).first()
            if u is None:
                u = User(id=user.id)

        return u

