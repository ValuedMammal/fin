from datetime import datetime
from sqlalchemy import Table, Column, ForeignKey, Integer, String, Float, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, relationship


default_cash = 1_000_000

class Base(DeclarativeBase):
    pass


# Primary (mapped) tables
user = Table(
    "user",
    Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("username", String, nullable=False),
    Column("hash", String, nullable=False),
    Column("cash", Float, nullable=False, default=default_cash)
)

asset = Table(
    "asset",
    Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("cls", String, default='stock'),
    Column("symbol", String, nullable=False),
    Column("name", String, nullable=False),
    Column("price", Float)
)

trade = Table(
    "trade",
    Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("type", String, nullable=False),
    Column("asset_id", ForeignKey("asset.id")),
    Column("user_id", ForeignKey("user.id")),
    Column("qty", Float, nullable=False),
    Column("price", Float, nullable=False),
    Column("time", TIMESTAMP, nullable=False, default=datetime.utcnow())
)

skull = Table(
    "skull",
    Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False),
    Column("description", String, nullable=False),
)

# Join table
holding = Table(
    "holding",
    Base.metadata,
    Column("asset_id", ForeignKey("asset.id"), primary_key=True),
    Column("user_id", ForeignKey("user.id"), primary_key=True),
    Column("qty", Float, nullable=False)
)

# Join table - not mapped
badge = Table(
    "badge",
    Base.metadata,
    Column("skull_id", ForeignKey("skull.id"), primary_key=True),
    Column("user_id", ForeignKey("user.id"), primary_key=True),
)

# Not mapped
settings = Table(
    "settings",
    Base.metadata,
    Column("user_id", ForeignKey("user.id")),
    Column("theme", String, nullable=True)
)

# Declarative w imperative table method
class User(Base):
    __table__ = user

    # Badges
    badges: Mapped[list["Skull"]] = relationship(secondary=badge, back_populates="s_owners")

    # Holdings
    holdings: Mapped[list["Hodl"]] = relationship(back_populates="user")


class Asset(Base):
    __table__ = asset

    # Holders (unused)
    # holders: Mapped[list["Hodl"]] = relationship(back_populates="asset")


class Trade(Base):
    __table__ = trade


class Skull(Base):
    __table__ = skull

    # Badge owners
    s_owners: Mapped[list["User"]] = relationship(secondary=badge, back_populates="badges")


class Hodl(Base):
    __table__ = holding
 
    user: Mapped["User"] = relationship(back_populates="holdings")
    # asset: Mapped["Asset"] = relationship(back_populates="holders")



# below instead of creating a mapped class, we defined the badge table above as a join table of two foreign keys belonging to mapped classes
# User and Skull. then we create a relationship wherein each primary class has an additional attribute (badges, owners)
# that consists of a list of objects from the other class. when a user earns a badge, the corresponding skull object is added to his/her collection,
# and sqlalchemy handles all insert/updates of the intermediate badge table. in theory, a similar idea applies to the holding table, however
# because holdings have an extra column (quantity owned) that needs explicit updates, it makes sense to map each holding to a Hodl object.

# class Badge(Base):
#     __table__ = badge


# testing junk data
sql_data = [
    "insert into user (username, hash, cash) values ('test', 'pbkdf2:sha256:260000$zzyAjwpvjn8PLcjH$385d0f56484b89a1f336a2a7ac40749bcad1f8b083d2ca9a26b6414af8ca9802', 1000)",
    "insert into asset (symbol, name, price) values ('AAPL', 'Apple Inc', 100.00)",
    "insert into asset (symbol, name, price) values ('TSLA', 'Tesla', 100.00)",
]
    # "insert into holding (asset_id, qty, user_id) values (2, 1, 1)",
    # "insert into holding (asset_id, qty, user_id) values (2, 1, 1)",
    # "insert into skull (name, description) values ('Achiever', 'Make a trade')"

    # "insert into badge (skull_id, user_id) values (1, 1)"




