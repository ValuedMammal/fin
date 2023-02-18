import os
import requests
import urllib.parse

from flask import redirect, render_template, request, session, g
from functools import wraps


class User:
    def __init__(self, id, name, cash):
        self.id = id
        self.name = name
        self.theme = None
        self.cash = cash
        self.holdings = []


def get_symbols(watching=False):
    """Return list of symbols in user holdings"""
    
    h = g.user.holdings
    symbols = []
    if watching:    # include symbols where qty held is 0
        for i in range(len(h)):
            symbols.append(h[i]["symbol"])
    else:
        for i in range(len(h)):
            if h[i]["qty"] > 0:
                symbols.append(h[i]["symbol"])
    return symbols


def quantity_owned(symbol):
    """Return quantity owned of an asset by symbol"""
    
    h = g.user.holdings
    for i in range(len(h)):
        if symbol == h[i]["symbol"]:
            qty = h[i]["qty"]
            return qty
    return None


def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


# for dev purpose
def fetch_quote(row):    
    return {
        "symbol": row[0]["symbol"],
        "name": row[0]["name"],
        "price": row[0]["price"]
    }


def lookup(symbol):
    """Look up quote for symbol."""

    # Contact API
    try:
        api_key = os.environ.get("API_KEY")
        url = f"https://cloud.iexapis.com/stable/stock/{urllib.parse.quote_plus(symbol)}/quote?token={api_key}"
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        quote = response.json()
        return {
            "name": quote["companyName"],
            "price": float(quote["latestPrice"]),
            "symbol": quote["symbol"]
        }
    except (KeyError, TypeError, ValueError):
        return None


def two_f(value):
    """Format value as USD."""
    return f"{value:,.2f}"
    



