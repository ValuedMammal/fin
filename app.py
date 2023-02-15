import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required, lookup, Portfolio, usd


# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

dev = True
if not dev:
    # Read api key
    with open("api.txt", 'r') as file:
        os.environ["API_KEY"] = file.read()    
    if not os.environ.get("API_KEY"):
        raise RuntimeError("API_KEY not set")


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

    # POST
    if request.method == "POST":

        # Toggle theme preference
        if "mood" in request.form:
            id = session["user_id"]
            row = db.execute("SELECT * FROM settings WHERE user_id=?", id)
            theme = row[0]["theme"]
            if theme == "light":
                db.execute("UPDATE settings SET theme='dark' WHERE user_id=?", id)
            else:
                db.execute("UPDATE settings SET theme='light' WHERE user_id=?", id)
            return redirect("/")

        # have this turned off while we sort out new api functionality
        # For all asset id in holdings
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
    else:
        user_id = session["user_id"]
        row = db.execute("SELECT * FROM users, settings WHERE settings.user_id=users.id AND users.id=?", user_id)
        user = row[0]["username"]
        cash = row[0]["cash"]
        session["theme"] = row[0]["theme"]

        # Query db for holdings
        holdings = []
        tab = db.execute("SELECT symbol, name, qty, price, qty*price\
                        FROM    holdings h, assets a\
                        WHERE   h.asset_id=a.id\
                        AND     h.user_id=?", user_id)
        
        # User portfolio empty
        if len(tab) == 0:
            session["portfolio"] = Portfolio(cash, holdings)
            return render_template("newuser.html", user=user, cash=cash)
        
        # Create portfolio
        sum = 0
        for row in range(len(tab)):
            value = round(tab[row]["qty*price"], 2)
            hodl = {
                "symbol": tab[row]["symbol"],
                "name": tab[row]["name"],
                "qty": tab[row]["qty"],
                "price": tab[row]["price"],
                "value": value
            }
            holdings.append(hodl)
            sum += hodl["value"]
        total = sum + cash

        # Keep user portfolio in session
        session["portfolio"] = Portfolio(cash, holdings)

        # Expanded view data - get symbols for user's recent trades
        table = []
        tb = db.execute("SELECT DISTINCT\
                                a.price, symbol, name\
                        FROM    assets a, trades t\
                        WHERE   t.asset_id=a.id\
                        AND     t.user_id=?\
                        ORDER BY time DESC", user_id)
        for row in range(len(tb)):
            d = {
                "price": tb[row]["price"],
                "symbol": tb[row]["symbol"],
                "name": tb[row]["name"]
            }
            table.append(d)
            if len(table) == 25:
                break

        # Fill in table with generic records - filter duplicates - hacky
        if len(table) < 25:
            tb = db.execute("SELECT price, symbol, name FROM assets LIMIT 25")
            for row in range(len(tb)):
                tb[row]["match"] = 0
                for i in range(len(table)):
                    if tb[row]["symbol"] == table[i]["symbol"]:
                        tb[row]["match"] += 1

                if tb[row]["match"] == 0:
                    d = {
                        "price": tb[row]["price"],
                        "symbol": tb[row]["symbol"],
                        "name": tb[row]["name"]
                    }
                    table.append(d)
                    if len(table) == 25:
                        break

        return render_template("advanced.html",\
            holdings=holdings, user=user, cash=cash, table=table, sum=sum, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # GET
    if request.method == "GET":
        return render_template("buy.html")

    # POST
    user_id = session["user_id"]
    p = session["portfolio"]
    max = None
    dollars = None
    try:
        symbol = request.form.get("symbol").upper()
    except:
        return redirect("/buy")
    if symbol == '':
        return redirect("/buy")

    # Max BUY order
    if "maximum-order-size" in request.form:
        max = True
    
    # Trade dollar value instead of shares
    elif "dollars" in request.form:
        value = round(float(request.form["dollars"]), 2)
        dollars = True

    # Quick-order - shares from quick order form
    elif "quick-order" in request.form:
        shares = round(float(request.form.get("shares")), 2)
        multi = int(request.form.get("multiplier"))
        if not shares or not shares > 0:
            flash("invalid quantity")
            return redirect("/")
        else:
            shares = (shares * multi)

    # Standard buy order, get shares
    else:
        try:
            shares = request.form.get("shares")
            shares = round(float(shares), 2)
        except:
            flash("invalid quantity")
            return redirect("/buy")
        if not shares or not shares > 0:
            flash("invalid quantity")
            return redirect("/buy")

    # Symbol lookups
    row = db.execute("SELECT * FROM assets WHERE symbol=?", symbol)
    if len(row) == 0:      # not in our db, not supported under dev config
        unseen = True
    else:
        asset_id = row[0]["id"]
        unseen = False

    # we are admin - lookup is a dummy fn #
    if dev:
        quote = lookup(row)
    else:
        quote = lookup(symbol)
        if quote is None:
            flash("symbol not found")
            return render_template("buy.html")
    symbol = quote["symbol"]
    name = quote["name"]
    price = quote["price"]

    # Check user cash
    cash = p.cash
    if max:
        shares = round((cash / price), 2)
        cash = 0
    else:
        if dollars:
            shares = round((value / price), 2)
        else:
            value = (price * shares)
        if value > cash:
            flash("rejected: low cash")
            return render_template("buy.html")
        else:
            cash -= value

    # Get user holdings for this asset
    new_hodl = True
    hodl = p.holdings
    for i in range(len(hodl)):
        if symbol == hodl[i]["symbol"]:
            qty = hodl[i]["qty"]
            new_hodl = False
            break

    # Update records - assets, holdings, cash, trades
    if unseen:
        asset_id = db.execute("INSERT INTO assets (class, symbol, name, price) VALUES ('stock',?,?,?)", symbol, name, price)
    else:
        db.execute("UPDATE assets SET price=? WHERE id=?", price, asset_id)
    if new_hodl:  # not in user holdings or watching
        db.execute("INSERT INTO holdings (asset_id, qty, user_id) VALUES (?, ?, ?)", asset_id, shares, user_id)
    else:
        qty += shares
        db.execute("UPDATE holdings SET qty=? WHERE asset_id=? and user_id=?", qty, asset_id, user_id)
    db.execute("UPDATE users SET cash=? WHERE id=?", cash, user_id)
    db.execute("INSERT INTO trades (type, user_id, asset_id, qty, price, time)\
        VALUES ('buy',?,?,?,?,datetime('now'))", user_id, asset_id, shares, price)

    if max or shares > 100:
        flash("executed")
    else:
        flash("done")
    return redirect("/")


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


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            flash("please enter username")
            return redirect("login.html")

        # Ensure password was submitted
        if not request.form.get("password"):
            flash("please enter password")
            return redirect("login.html")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            flash("invalid credentials")
            return redirect("login.html")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["portfolio"] = None

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote")
@login_required
def quote():
    """Go to quote search page."""

    return render_template("quote.html", quote=None)


@app.route("/quoted")
@login_required
def get_quote():
    """Request a stock quote via a pre-configured API"""

    symbol = request.args.get("name").upper()

    # List of symbols in user holdings
    symbols = []
    hodl = session["portfolio"].holdings
    for i in range(len(hodl)):
        symbols.append(hodl[i]["symbol"])

    # Retrieve asset symbol - logic follows dynamic table data, see /search route
    row = db.execute("SELECT symbol FROM assets WHERE symbol=? OR name LIKE ? LIMIT 1", symbol, '%'+ symbol +'%')
    if len(row) == 0:   # not in our db

        # Lookup and insert new asset
        quote = lookup(symbol)
        if quote is None:
            flash("symbol not found")
            return render_template("quote.html")
        else:
            price = quote["price"]
            symbol = quote["symbol"]
            name = quote["name"]
            db.execute("INSERT INTO assets (class, symbol, name, price) VALUES ('stock',?,?,?)", symbol, name, price)

    # Lookup and update last price
    else:
        quote = lookup(row)
        price = quote["price"]
        # db.execute("UPDATE assets SET price=? WHERE symbol=?", price, symbol) # off for dev

    flash("Found {}: ${}".format(symbol, price))
    if "quick-search" in request.args:
        return redirect("/")
    else:
        return render_template("quote.html", quote=quote, symbols=symbols)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # GET
    if request.method == "GET":
        return render_template("register.html")

    # POST
    else:
        
        # Validate input
        username = request.form["username"]
        if username is None:
            return render_template("register.html")

        row = db.execute("SELECT * FROM users WHERE username = ?", username)
        if not len(row) == 0:
            flash("sry, username taken")
            return redirect("/register")
        if not request.form["password"] or not request.form["password"] == request.form["confirmation"]:
            flash("err bad password")
            return redirect("/register")

        # Add new user to db
        pw = request.form["password"]
        hash = generate_password_hash(pw)
        id = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)
        db.execute("INSERT INTO settings (user_id) VALUES (?)", id)
        return redirect("/login")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # GET
    if request.method == "GET":

        # Get user holdings
        symbols = []
        p = session["portfolio"]
        hodl = p.holdings
        for i in range(len(hodl)):
            if hodl[i]["qty"] != 0:
                s = hodl[i]["symbol"]
                symbols.append(s)

        return render_template("/sell.html", symbols=symbols)

    # POST
    user_id = session["user_id"]
    max = None
    dollars = None
    try:
        symbol = request.form.get("symbol").upper() # note this is a catch-all for 3 req forms
    except:
        return redirect("/sell")
    if symbol == '':
        return redirect("/sell")

    # Max order size (SELL)
    if "maximum-order-size" in request.form:
        max = True
    
    # Trade dollar value instead of shares
    elif "dollars" in request.form:
        value = round(float(request.form["dollars"]), 2)
        dollars = True

    # Quick order form - shares come from separate form, then follow same
    elif "quick-order" in request.form:
        try:
            shares = round(float(request.form.get("shares")), 2)
            multi = int(request.form.get("multiplier"))
            shares = (shares * multi)
        except:
            flash("invalid quantity")
            return redirect("/")
        if not shares > 0:
            flash("invalid quantity")
            return redirect("/")

    # Standard sell order
    else:
        try:
            shares = round(float(request.form.get("shares")), 2)
        except:
            flash("invalid quantity")
            return redirect("/sell")
        if not shares or not shares > 0:
            flash("invalid quantity")
            return redirect("/sell")

    # Validate input
    row = db.execute("SELECT * FROM assets WHERE symbol=?", symbol)
    if len(row) == 0:   # if owned, then symbol should return an asset id
        flash("err bad symbol")
        return redirect("sell.html")
    else:
        asset_id = row[0]["id"]
        last_price = row[0]["price"]

    p = session["portfolio"]
    hodl = p.holdings
    cash = p.cash
    held = None
    qty = 0
    for i in range(len(hodl)):
        if symbol == hodl[i]["symbol"] and hodl[i]["qty"] > 0:
            qty = hodl[i]["qty"]
            held = True
            break
    if not held:
        flash("rejected: you don't own that")
        return redirect("/sell")
    if max or dollars:
        pass
    elif shares > qty:
        flash("rejected: low shares")
        return redirect("/sell")

    # Lookup quote
    if dev:
        price = last_price
    else:
        quote = lookup(symbol)
        if quote is None:
            flash("symbol not found")
            return render_template("sell.html")
        else:
            price = quote["price"]

    if max:
        shares = qty # total owned before sale
        qty = 0
    elif dollars:
        shares = round((value / price), 2)
        qty -= shares
    else:
        qty -= shares

    cash += (shares * price)

    # Update records - assets, holdings, users, trades
    db.execute("UPDATE assets SET price=? WHERE id=?", price, asset_id)
    db.execute("UPDATE holdings SET qty=? WHERE asset_id=? AND user_id=?", qty, asset_id, user_id)
    db.execute("UPDATE users SET cash=? WHERE id=?", cash, user_id)
    db.execute("INSERT INTO trades (type, user_id, asset_id, qty, price, time)\
        VALUES ('sell',?,?,?,?,datetime('now'))", user_id, asset_id, shares, price)
    if max or shares > 100:
        flash("executed")
    else:
        flash("done")
    return redirect("/")

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
    symbols = []
    hodl = session["portfolio"].holdings
    for i in range(1, len(hodl)):
        s = hodl[i]["symbol"]
        symbols.append(s)

    # Pull row of database matching symbol or name
    q = request.args.get("q").upper()
    if q:
        row = db.execute("SELECT * FROM assets WHERE symbol=? OR name LIKE ? LIMIT 1", q, '%'+ q +'%')
    else:
        row = []

    # We pass db row and user portfolio to search.html
    # jinja: if symbol in watchlist, say so, else render button to add it
    return render_template("search.html", row=row, symbols=symbols)


@app.route("/watch", methods=["POST"])
@login_required
def watch():
    """Add a stock symbol to user watch list"""

    s = request.form["symbol"]      # sym comes directly from our db through /search route
    if not s:
        flash('backend err see admin')
        return redirect("/quote")
    else:
        row = db.execute("SELECT * FROM assets WHERE symbol=?", s)
        asset_id = row[0]["id"]
        user_id = session["user_id"]
        session["portfolio"].holdings += {
            "symbol": s,
            "name": row[0]["name"],
            "qty": 0,
            "price": row[0]["price"],
            "value": 0,
        }
        db.execute("INSERT INTO holdings (asset_id, qty, user_id) VALUES (?,0,?)", asset_id, user_id)
        flash("added {}".format(s))
        return redirect("/quote")


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


@app.route("/publish", methods=["POST"])
@login_required
def publish():
    """Send user to social network to share trades"""
    # #
    return apology("Not implemented")