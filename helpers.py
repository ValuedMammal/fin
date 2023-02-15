import os
import requests
import urllib.parse

from flask import redirect, render_template, request, session
from functools import wraps


class Portfolio:
    def __init__(self, cash, holdings):
        self.cash = cash
        self.holdings = holdings

class Holding:
    pass

# Return list of symbols in holdings (non-zero qty only?)
def get_symbols():
    if "user_id" not in session:
        return None     # unnecessary? won't call fn unless logged in
    h = session["portfolio"].holdings    # is this always true?
    symbols = []
    for i in range(len(h)):
        if h[i]["qty"] > 0:
            symbols.append(h[i]["name"])
    return symbols

# Return qty owned of symbol
def quantity_owned(symbol):
    if "user_id" not in session:
        return None
    h = session["portfolio"].holdings
    for i in range(len(h)):
        if symbol == h[i]["symbol"]:
            qty = h[i]["qty"]
            return qty
    return 0


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


def lookup(row):
    
    return {
        "symbol": row[0]["symbol"],
        "name": row[0]["name"],
        "price": row[0]["price"]
    }


# def lookup(symbol):
#     """Look up quote for symbol."""

#     # Contact API
#     try:
#         api_key = os.environ.get("API_KEY")
#         url = f"https://cloud.iexapis.com/stable/stock/{urllib.parse.quote_plus(symbol)}/quote?token={api_key}"
#         response = requests.get(url)
#         response.raise_for_status()
#     except requests.RequestException:
#         return None

#     # Parse response
#     try:
#         quote = response.json()
#         return {
#             "name": quote["companyName"],
#             "price": float(quote["latestPrice"]),
#             "symbol": quote["symbol"]
#         }
#     except (KeyError, TypeError, ValueError):
#         return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"
