import click
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from finance.model import Base

engin = create_engine("sqlite+pysqlite:///instance/finance.db" , echo=True)
Session = sessionmaker(engin)

# Create tables
def init_db():
    Base.metadata.create_all(bind=engin)


# Add cli command
@click.command("init-db")
def init_db_command():
   init_db()
   click.echo("Database initialized.")


# Register db functions with the app
def init_app(app):
    app.cli.add_command(init_db_command)


    
