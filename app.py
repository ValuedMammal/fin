import os
import time

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, g
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import (
    apology, fetch_quote, login_required, lookup, two_f, User
)


# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = two_f

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_COOKIE_NAME"] = "dev"
app.SESSION_COOKIE_NAME = "dev"
Session(app)

# Configure CS50 Library to use SQLite database
with open("db.txt", 'r') as f:
    db_file = f.read()
db = SQL("sqlite:///" + db_file)

dev = True
# dev = False
if not dev:
    # Read api key
    with open("api.txt", 'r') as file:
        os.environ["API_KEY"] = file.read()    
    if not os.environ.get("API_KEY"):
        raise RuntimeError("API_KEY not set")


@app.before_request
def load_user():
    """Load app globals for current user"""
    
    if "user_id" not in session:
        g.user = None
        return        
    else:
        user_id = session["user_id"]
        row = db.execute('SELECT username, cash, theme' 
                ' FROM  users u, settings s'
                ' WHERE s.user_id=u.id'
                ' AND   u.id=?', user_id)
        #
        name = row[0]["username"]
        cash = row[0]["cash"]
        theme = row[0]["theme"]
        g.user = User(user_id, name, cash)
        g.user.theme = theme
        #
        tb = db.execute('SELECT symbol, name, qty, price'
            ' FROM    holdings h, assets a'
            ' WHERE   h.asset_id=a.id'
            ' AND     h.user_id=?', (user_id,)
        )
        if len(tb) > 0:
            for i in range(len(tb)):
                g.user.holdings.append(tb[i])
        return


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Show portfolio of stocks"""

    user_id = session["user_id"]
    
    # POST
    if request.method == "POST":
        # have this turned off while we sort out new api functionality
        # For all asset id in holdings
        if "refresh" in request.form:
            tab = db.execute("SELECT symbol FROM assets, holdings\
                WHERE holdings.asset_id=assets.id")

            # Lookup quote
            for i in range(len(tab)):
                symbol = tab[i]["symbol"]
                quote = lookup(symbol)
                price = quote["price"]

                # Update our assets db
                db.execute("UPDATE assets SET price=? WHERE symbol=?", price, symbol)
            return redirect("/")

    # GET
    if g.user.theme == 'dark':
        session["theme"] = 'dark'
    elif g.user.theme == 'auto':
        hr = time.localtime().tm_hour
        if hr > 18 or hr < 7:
            session["theme"] = 'dark'
    else:
        session["theme"] = 'light'

    # Create portfolio
    cash = g.user.cash
    h = g.user.holdings
    
    # Portfolio empty
    if len(h) == 0:
        return render_template("newuser.html", cash=cash)
    
    # Crunch sums
    sum = 0
    holdings = []
    for i in range(len(h)):
        holdings.append(h[i])
        value = (h[i]["qty"] * h[i]["price"])
        holdings[i]["value"] = round(value, 2)
        sum += value

    # Expanded view data - get symbols for user's recent trades
    tb = db.execute('SELECT DISTINCT a.price, symbol, name'
            ' FROM    assets a, trades t'
            ' WHERE   t.asset_id=a.id'
            ' AND     t.user_id=?'
            ' ORDER BY time DESC', (user_id)
    )
    table = []
    symbols = []
    for row in range(len(tb)):
        s = tb[row]["symbol"]
        d = {
            "price": tb[row]["price"],
            "symbol": s,
            "name": tb[row]["name"]
        }
        symbols.append(s)
        table.append(d)            
        if len(table) == 25:
            break

    # Fill in table with generic records - filter duplicates
    if len(table) < 25:
        tb = db.execute("SELECT price, symbol, name FROM assets LIMIT 25")
        for row in range(len(tb)):
            if tb[row]["symbol"] not in symbols:
                d = {
                    "price": tb[row]["price"],
                    "symbol": tb[row]["symbol"],
                    "name": tb[row]["name"]
                }
                table.append(d)
            if len(table) == 25:
                break

    return render_template("advanced.html", holdings=holdings, cash=cash, table=table, sum=sum)


@app.route("/quote")
@login_required
def quote():
    """Go to quote search page."""

    return render_template("quote.html", symbols=get_symbols(watching=True))


@app.route("/quoted")
@login_required
def get_quote():
    """Request a stock quote via a pre-configured API"""

    location = "/" if "quick-search" in request.args else "/quote"
    error = None        
    symbol = request.args.get("name").upper()
    quote = lookup(symbol)
    if quote is None:
        error = "symbol not found"
    else:
        symbol = quote["symbol"]
        name = quote["name"]
        price = quote["price"]

        # Query db for asset
        row = db.execute("SELECT symbol FROM assets WHERE symbol=?", symbol)
        
        # Insert new asset
        if len(row) == 0:
            db.execute("INSERT INTO assets (class, symbol, name, price) VALUES ('stock',?,?,?)", symbol, name, price)

        # Update last price
        else:
            db.execute("UPDATE assets SET price=? WHERE symbol=?", price, symbol) # off for dev

    if error is not None:
        flash(error)
        return redirect(location)
    
    flash(f"Found {symbol}: ${price}")
    return redirect(location)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # GET
    if request.method == "GET":
        return render_template("buy.html")

    # POST
    user_id = session["user_id"]
    badges = get_badges(user_id)
    error = None
    events = []     # listen for new achievements, stores skull_id
    location = "/buy"
    max = None
    dollars = None
    
    # Parse req
    try:
        symbol = request.form.get("symbol").upper()
    except:
        error = "invalid symbol"
    if symbol == '':
        return redirect("/buy")

    # Max BUY order
    if "maximum-order-size" in request.form:
        value = g.user.cash
        max = True
    
    # Trade dollar value instead of shares
    elif "dollars" in request.form:
        try:
            value = round(float(request.form["dollars"]), 2)
        except:
            error = "invalid quantity"
        else:
            dollars = True
            if value < 1:
                error = "invalid quantity"

    # Quick-order - shares from quick order form, always return home - put another try block here?
    elif "quick-order" in request.form:
        try:
            shares = float(request.form["shares"])
            multi = float(request.form["multiplier"])
        except:
            error = "invalid quantity"
        else:
            location = "/"
            shares = round(shares * multi, 4)
            if not shares or not shares > 0:
                error = "invalid quantity"

    # Standard buy order, get shares
    else:
        try:
            shares = float(request.form["shares"])
        except:
            error = "invalid quantity"
        if not shares or not shares > 0:
            error = "invalid quantity"
    
    if error is not None:
        flash(error)
        return redirect(location)
    
    # Symbol lookups
    row = db.execute("SELECT * FROM assets WHERE symbol=?", symbol)
    try:
        asset_id = row[0]["id"]
        unseen = False
    # not in our db, not supported under dev config
    except:
        asset_id = None
        unseen = True

    # we are admin - lookup is a dummy fn #
    if dev:
        quote = fetch_quote(row)
    else:
        quote = lookup(symbol)
        if quote is None:
            error = "symbol not found"
    symbol = quote["symbol"]
    price = quote["price"]

    # Check user inventory and finalize trade
    cash = g.user.cash
    if max or dollars:
        shares = round((value / price), 4)
    else:
        value = round((price * shares), 2)
    if value > cash:
        error = "rejected: low cash"
    qty = quantity_owned(symbol)
    if qty is None:
        qty = 0
        new_hodl = True
    else:
        new_hodl = False
    cash -= value
    qty += shares
    trade = {
        "type": "buy",
        "asset_id": asset_id,
        "shares": shares,
        "unseen": unseen,
        "user_id": user_id,
        "new_hodl": new_hodl,
    }
    if error is not None:
        flash(error)
        return redirect(location)
    
    save_trade(quote, trade, qty, cash)
    if 1 not in badges: # event s1
        events.append(1)
    if location == "/" and 2 not in badges: # event s2
        events.append(2)
    if shares >= 1000 and 5 not in badges: # event s5
        events.append(5)
    if len(events) > 1 and 3 not in badges: # event s3
        events.append(3)

    if max or shares > 100:
        flash("executed")
    else:
        flash("done")    
    if len(events) > 0:
        new_badges = add_badges(events)
        for i in range(len(new_badges)):
            name = new_badges[i]
            flash(f"Achievement: {name}")
    return redirect("/")    


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # GET
    if request.method == "GET":
        return render_template("/sell.html", symbols=get_symbols())

    # POST
    user_id = session["user_id"]
    badges = get_badges(user_id)
    location = "/sell"
    error = None
    events = []
    max = None
    dollars = None
    
    # Parse req
    try:
        symbol = request.form.get("symbol").upper()
    except:
        error = "invalid symbol"
    if symbol == '':    # do nothing
        return redirect(location)

    # Max order size
    if "maximum-order-size" in request.form:
        max = True
    
    # Trade dollar value instead of shares
    elif "dollars" in request.form:
        try:
            value = round(float(request.form["dollars"]), 2)
        except:
            error = "invalid quantity"
        else:
            dollars = True
            if value < 1:
                error = "invalid quantity"

    # Quick order form - shares come from separate form, always return home
    elif "quick-order" in request.form:
        try:
            shares = float(request.form["shares"])
            multi = float(request.form["multiplier"])
        except:
            error = "invalid quantity"
        else:    
            location = "/"
            shares = round(shares * multi, 4)
            if not shares or not shares > 0:
                error = "invalid quantity"

    # Standard sell order
    else:
        try:
            shares = round(float(request.form.get("shares")), 2)
        except:
            error = "invalid quantity"
        if not shares or not shares > 0:
            error = "invalid quantity"
    
    if error is not None:
        flash(error)
        return redirect(location)
    
    # Lookup quote
    row = db.execute("SELECT * FROM assets WHERE symbol=?", symbol)
    try:
        asset_id = row[0]["id"]
    except:
        flash("symbol not found")
        return redirect(location)
    if dev:
        quote = fetch_quote(row)
    else:
        quote = lookup(symbol)
    if quote is None:
        flash("symbol not found")
        return redirect(location)
    else:    
        price = quote["price"]

    # Check user inventory and finalize trade
    cash = g.user.cash
    qty = quantity_owned(symbol)
    if max:
        shares = qty
    elif dollars:
        shares = round((value / price), 4)
    if qty == 0 or qty is None:
        error = "rejected: you don't own that"
    elif shares > qty:
        error = "rejected: low shares"
    cash += (price * shares)
    profit = is_profit(asset_id, price, qty)
    qty -= shares
    trade = {
        "type": "sell",
        "asset_id": asset_id,
        "shares": shares,
        "unseen": False,
        "user_id": user_id,
        "new_hodl": False,
    }
    if error is not None:
        flash(error)
        return redirect(location)
    
    save_trade(quote, trade, qty, cash)
    if location == "/" and 2 not in badges: # event s2
        events.append(2)
    if profit and 4 not in badges: # event s4
        events.append(4)
    if shares >= 1000 and 5 not in badges: # event s5
        events.append(5)
    if len(events) > 1 and 3 not in badges: # event s3
        events.append(3)
    
    if max or shares > 100:
        flash("executed")
    else:
        flash("done")
    if len(events) > 0:
        new_badges = add_badges(events)
        for i in range(len(new_badges)):
            name = new_badges[i]
            flash(f"Achievement: {name}")
    return redirect("/")


# Update records - assets, holdings, cash, trades
# qty and cash are after trade result
def save_trade(quote, trade, qty, cash):
    
    user_id = session["user_id"]
    symbol = quote["symbol"]
    name = quote["name"]
    price = quote["price"]
    type = trade["type"]
    asset_id = trade["asset_id"]
    shares = trade["shares"]

    # Insert asset
    if trade["unseen"] == True:
        asset_id = db.execute("INSERT INTO assets (class, symbol, name, price) VALUES ('stock',?,?,?)", symbol, name, price)
    # Update asset
    else:
        db.execute("UPDATE assets SET price=? WHERE id=?", price, asset_id)

    # Insert holding
    if trade["new_hodl"] == True:
        db.execute("INSERT INTO holdings (asset_id, qty, user_id) VALUES (?, ?, ?)", asset_id, qty, user_id)
    # Update holding
    else:
        db.execute("UPDATE holdings SET qty=? WHERE asset_id=? and user_id=?", qty, asset_id, user_id)

    db.execute("UPDATE users SET cash=? WHERE id=?", cash, user_id)
    db.execute('INSERT INTO trades (type, user_id, asset_id, qty, price)'
        ' VALUES (?,?,?,?,?)', type, user_id, asset_id, shares, price)
    return


@app.route("/watch", methods=["POST"])
@login_required
def watch():
    """Add a stock symbol to user watch list"""

    s = request.form["symbol"]      # sym comes directly from our db through /search route
    if not s:
        flash('backend err see admin')
        return redirect("/quote")
    row = db.execute("SELECT * FROM assets WHERE symbol=?", s)
    asset_id = row[0]["id"]
    user_id = session["user_id"]
    db.execute("INSERT INTO holdings (asset_id, qty, user_id) VALUES (?,0,?)", asset_id, user_id)        
    flash(f"added {s}")
    return redirect("/quote")


@app.route("/unwatch", methods=["POST"])
@login_required
def unwatch():
    """Remove stock symbol from watchlist"""

    row = db.execute("SELECT id FROM assets WHERE symbol=?", request.form["symbol"])
    db.execute("DELETE FROM holdings WHERE asset_id=? AND user_id=?", row[0]["id"], session["user_id"])
    return redirect("/")


@app.route("/search", methods=["GET"])
@login_required
def search():
    """Handle a scripted request for database records"""

    # List of symbols in user holdings
    symbols = get_symbols(watching=True)

    # Pull row of database matching symbol or name
    q = request.args.get("q").upper()
    if q:
        row = db.execute("SELECT * FROM assets WHERE symbol=? OR name LIKE ? LIMIT 1", q, '%'+ q +'%')
    else:
        row = []

    # We pass db row and user portfolio to search.html
    # jinja: if symbol in watchlist, say so, else render button to add it
    return render_template("search.html", row=row, symbols=symbols)


@app.route("/stat", methods=["GET"])
def stats():
    """Display leaderboard for all users"""

    # We need list of user dicts sorted by portfolio sum
    list = []

    # For each user, get largest holding and total value of holdings ex-cash
    users = db.execute("SELECT * FROM users")
    for user in range(len(users)):
        id = users[user]["id"]
        name = users[user]["username"]

        # Largest symbol - 1 row
        large = db.execute("SELECT symbol, max(qty*price) FROM holdings, assets, users\
                WHERE holdings.asset_id=assets.id\
                AND holdings.user_id=users.id\
                AND holdings.user_id=?",id)

        # Total portfolio - 1 row
        sum = db.execute("SELECT sum(qty*price) FROM holdings, assets, users\
                WHERE holdings.asset_id=assets.id\
                AND holdings.user_id=users.id\
                AND holdings.user_id=?",id)

        if sum[0]["sum(qty*price)"] is None:     # lacking price data
            continue
        else:
            dict = {
                    "user_id": id,
                    "name": name,
                    "symbol": large[0]["symbol"],
                    "sum": round(float(sum[0]["sum(qty*price)"]), 2)
                    }
            if len(list) == 0: # first iteration
                list.append(dict)
            elif dict["sum"] < list[-1]["sum"]:
                list.append(dict)       # same result, use or:
            else:
                for i in range(len(list)):
                    if dict["sum"] > list[i]["sum"]:      # linear search, we can do better
                        list.insert(i, dict)
                        break

    return render_template("stat.html", list=list)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Query for user trades
    trades = db.execute("SELECT type, symbol, qty, t.price, time\
                    FROM    trades t, assets a, users u\
                    WHERE   t.asset_id=a.id \
                    AND     t.user_id=u.id\
                    AND     u.id=?\
                    ORDER BY time DESC", session["user_id"])

    return render_template("history.html", trades=trades)


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # POST
    if request.method == "POST":
        error = None
        if not request.form.get("username"):
            error = "pls enter username"
        elif not request.form.get("password"):
            error = "pls enter password"
        if error is not None:
            flash(error)
            return render_template("login.html")
        
        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            error = "invalid credentials"
            flash(error)
            return render_template("login.html")
        
        # Keep user in session
        session["user_id"] = rows[0]["id"]
        session["theme"] = None
        return redirect("/")

    # GET
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # GET
    if request.method == "GET":
        return render_template("register.html")

    # POST
    error = None
    username = request.form.get("username")
    if username == '' or username is None:
        error = "pls enter username" 
    else:
        row = db.execute("SELECT * FROM users WHERE username = ?", username)
        if not len(row) == 0:
            error = "sry, username taken"
        elif not request.form["password"] or not request.form["password"] == request.form["confirmation"]:
            error = "err bad password"

    if error is not None:
        flash(error)
        return redirect("/register")
        
    # Add new user
    pw = request.form["password"]
    hash = generate_password_hash(pw)
    id = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)
    db.execute("INSERT INTO settings (user_id) VALUES (?)", id)
    return redirect("/login")


@app.route("/publish", methods=["POST"])
@login_required
def publish():
    """Send user to social network to share trades"""
    # #
    return apology("Not implemented")


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


def is_profit(asset_id, price, qty):
    """Return True if proceeds from sale exceeds cash outlay"""
    
    # long side only
    # is holding this symbol? assume yes since we're currently selling
    # qty arg is qty owned before sale
    # profit is True if this trade price > average cost basis        
    
    # Query all trades of this symbol
    tb = db.execute('select * from trades'
            ' where asset_id = ?'
            ' and user_id = ?' , asset_id, g.user.id)
    
    # Avg basis = (total outlay - total proceeds) / current qty
    sum = 0
    for row in range(len(tb)):
        t = tb[row]
        if t["type"] == 'buy':
            sum += (t["price"] * t["qty"])
        else:
            sum -= (t["price"] * t["qty"])
    basis = sum / qty
    return (price > basis)


def get_badges(id): 
    """Query database for user's earned badges"""
    ##
    l = []
    tb = db.execute('SELECT skull_id FROM badges WHERE user_id=?', id)
    if len(tb) > 0:
        for i in range(len(tb)):
            l.append(tb[i]["skull_id"])
    return l


def add_badges(events):
    """Update user achievements"""
    ##
    user_id = session["user_id"]
    for i in range(len(events)):
        skull_id = events[i]
        db.execute('INSERT INTO badges (skull_id, user_id) VALUES (?,?)', skull_id, user_id)

    l = []
    tb = db.execute('SELECT id, name FROM skulls')
    for i in range(len(tb)):
         if tb[i]["id"] in events:
             l.append(tb[i]["name"])
    return l


@app.route("/settings", methods=["GET" , "POST"])
@login_required
def settings():
    """Configure user settings"""
    
    user_id = session["user_id"]
    
    # GET
    if request.method == "GET":
        badges = get_badges(user_id)
        unlockables = db.execute('select * from skulls where id < 6') # named badges 1-5
        return render_template("settings.html", badges=badges, unlockables=unlockables)
    
    # POST
    if "theme" in request.form:
        theme = request.form.get("theme")
        db.execute('UPDATE settings SET theme=? WHERE user_id=?', theme, user_id)
        
        # here, duplicating code from index route, plus we've hard coded the time of day
        # when dark is active. the alternative is to place the logic in `before_request`
        # but that seems overkill when already handled by session. ideally, we get user preference
        # from device OS but that's beyond the current scope
        if theme == 'dark':
            session["theme"] = 'dark'
        elif theme == 'auto':
            hr = time.localtime().tm_hour
            if hr > 18 or hr < 7:
                session["theme"] = 'dark'
        else:
            session["theme"] = 'light'
        flash("saved")
        return redirect("/settings")
        
    # Reset this user
    default_cash = 1*(10**6)

    if "reset-me" in request.form:
        db.execute('DELETE FROM trades WHERE user_id=?', user_id)
        db.execute('DELETE FROM holdings WHERE user_id=?', user_id)
        db.execute('UPDATE users SET cash=? WHERE id=?', default_cash, user_id)
        db.execute('DELETE FROM badges WHERE user_id=?', user_id)
    
    # Reset all
    else:
        db.execute('DELETE FROM trades WHERE user_id LIKE "%"')
        db.execute('DELETE FROM holdings WHERE user_id LIKE "%"')
        db.execute('UPDATE users SET cash=? WHERE id LIKE "%"', default_cash)
        db.execute('DELETE FROM badges WHERE user_id LIKE "%"')
        
    flash("done")
    return redirect("/")
    