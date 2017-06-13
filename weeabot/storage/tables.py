
from sqlalchemy.ext.declarative import declarative_base, declared_attr


class Base(declarative_base()):
    """
    Base functionality of tables.
    """

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()


class User(Base):
    pass

