import click
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from finance.helpers import usd
from finance.model import Base
from hidden import secrets


Session = sessionmaker()

def get_db(path=None):
    if path is None:
        return create_engine("sqlite+pysqlite:///instance/finance.db", echo=True)
    else:
        return create_engine("sqlite+pysqlite:///" + path, echo=True)


# Create tables
def init_db(engine):
    Base.metadata.create_all(bind=engine)


def close_db():
    # test if a db session still active?
    pass


# Add cli command
@click.command("init-db")
def init_db_command():
    init_db(engine=get_db())
    click.echo("Database initialized.")


# Register db functions with the app
def init_app(app):
    # app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.jinja_env.filters["usd"] = usd
    if os.environ.get("API_KEY") is None:
        os.environ["API_KEY"] = secrets["api"]

    
   
