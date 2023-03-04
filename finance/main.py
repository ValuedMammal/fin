import time
from flask import (
    current_app, Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from sqlalchemy import select, text

from finance.db import Session
from finance.auth import login_required
from finance.model import User, Asset, Hodl, Trade, Skull


bp = Blueprint("main", __name__)

    

@bp.route("/", methods=["GET"])
@login_required
def index():
        
    user_id = g.user["id"]
    asset_val = 0.0
    holdings = []    

    # Portfolio view
    with Session() as cur:
        u = cur.get(User, user_id)
        cash = float(u.cash)
        sel = text(
            '''
            SELECT * FROM asset, holding
            WHERE holding.asset_id = asset.id
            AND holding.user_id =:i
            ORDER BY name ASC
            '''
            ).bindparams(i=user_id)

        for row in cur.execute(sel).all():
            if row is not None:
                asset_val += (row.qty * row.price)
                holdings.append(row)
        
        # Set theme preference
        theme = cur.execute(text(
            'select theme from settings where user_id = :i'
            ),    {"i": user_id}
        ).scalar()

    if theme == 'dark':
        session["theme"] = 'dark' 
    elif theme == 'auto':
        hr = time.localtime().tm_hour
        session["theme"] = 'dark' if hr > 18 or hr < 7 else None            
    else:
        session["theme"] = None
    
    total = usd(cash + asset_val)
    cash = usd(cash)
    asset_val = usd(asset_val)

    return render_template("index.html", holdings=holdings, cash=cash, asset_val=asset_val, total=total)
    

@bp.route("/trade", methods=["GET", "POST"])
@login_required
def trade():
    
    # POST
    if request.method == "POST":
        user_id = g.user["id"]
        symbol = request.form.get("symbol").upper()
        view = request.form.get("view")
        type = request.form.get("type")
        badges = get_badges()
        events = []     # listen for achievement events

        with Session() as du:
            
            # Get user inventory
            u = du.get(User, user_id)
            cash = u.cash
            
            # Query for asset
            row = du.execute(
                select(Asset).where(Asset.symbol == symbol)
            ).scalar()
            if row is None:
                unseen = True
                du.rollback()
            else:
                unseen = False
                price = row.price
                asset_id = row.id
                
                # is holding?
                h = du.get(Hodl, (asset_id, user_id))
                if h is None:
                    qty = 0
                    new = True
                else:
                    qty = h.qty
                    new = False
                    # rollback
        
        if unseen:        
            quote = lookup(symbol)
            if quote is None:
                flash("None")
                return redirect(url_for(view))
            else:
                price = quote["price"]
                name = quote["name"]
        
        shares = int(request.form.get("shares"))
        val = round((shares * price), 4)
        if shares is None or shares < 1:
            flash("invalid quantity")
            return redirect(url_for(view))

        error = None
        
        # buy
        if type == 'buy':
            if val > cash:
                error = "rejected low cash"
            cash -= val
            qty += shares

        # sell
        elif type == 'sell':
            if qty == 0:
                error = "you don't own it"
            elif shares > qty:
                error = "rejected low inventory"
            else:
                profit = is_profit(asset_id, price, qty)
                cash += val
                qty -= shares

        if error is not None:
            flash(error)
            return redirect(url_for(view))
        
        # Update tables: asset, holding, user, trade
        with Session() as du:

            # insert or update asset
            if unseen:
                du.add(
                    Asset(symbol=symbol, name=name, price=price)
                )
            else:
                a = du.get(Asset, asset_id)
                a.price = price
            
            # set cash
            u = du.get(User, user_id)
            u.cash = round(cash, 4)
            
            # insert or update hodl
            if new:
                du.add(
                    Hodl(asset_id=asset_id, user_id=user_id, qty=qty)
                )
                # get new obj to append to user collection
                h = du.execute(select(Hodl).where(
                    Hodl.asset_id == asset_id, Hodl.user_id == user_id
                )).scalar()
                u.holdings.append(h)
            else:
                h = du.get(Hodl, (asset_id, user_id))
                h.qty = qty

            # insert trade
            du.add(
                Trade(type=type, user_id=user_id, asset_id=asset_id, qty=shares, price=price)
            )
            du.commit()
        flash("done")     
        
        # Tally achievements
        if 1 not in badges:     # s1: make a trade
            events.append(1)
        if view == 'index' and 2 not in badges:     # s2: no time wasted
            events.append(2)
        if type == 'sell' and profit == True and 4 not in badges:    # s4: profiteer 
            events.append(4)
        if shares > 999 and 5 not in badges:    # s5: big bags
            events.append(5)
        if len(events) > 1 and 3 not in badges:     # s3: two-fer
            events.append(3)
        if len(events) > 0:
            new_badges = add_badges(events)
            for name in new_badges:
                flash(f"Achievement: {name}")

        return redirect(url_for("index"))
    
    # GET
    return render_template("trade.html")


@bp.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    
    # POST
    if request.method == "POST":

    
        # lookup
        symbol = request.form.get("symbol").upper()
        with Session() as cur:
            row = cur.execute(select(Asset).where(
                Asset.symbol == symbol
            )).scalar()
            if row is not None:
                price = round(row.price, 2)
                flash(f"{symbol}: ${price}")
            else:
                flash("None")
        
        # def look_up():
            # pass
        
        return render_template("quote.html")

    # GET
    return render_template("quote.html")


@bp.route("/watch", methods=["POST"])
@login_required
def watch():
    """Add a symbol to user watch list"""
    
    asset_id = request.form.get("asset")
    symbol = request.form.get("symbol")

    with Session() as cur:
        cur.add(
            Hodl(asset_id=asset_id, user_id=g.user["id"], qty=0)
        )
        cur.commit()
    
    flash(f"added {symbol}")
    return redirect(url_for("main.quote"))


@bp.route("/unwatch", methods=["POST"])
@login_required
def unwatch():
    """Remove a symbol from watch list"""
    
    user_id = g.user["id"]
    asset_id = request.form.get("asset")
    with Session() as cur:
        h = cur.get(Hodl, (asset_id,user_id))
        cur.delete(h)
        cur.commit()
    return redirect("/")


@bp.route("/search", methods=["GET"])
@login_required
def search():
    """Handle a request for database records"""
    # search assets for exact symbol or name like
    # return 1 row w symbol, name
    # if watching, say so, else render button to watch

    user_id = g.user["id"]
    list =[]
    s = request.args.get("q").upper()
    with Session() as cur:
        
        # get holdings including watch only
        sel = select(Hodl.asset_id).where(Hodl.user_id == user_id)
        for asset in cur.scalars(sel):
            list.append(asset)
        
        # fetch asset row
        if s is not None:
            row = cur.execute(text(
                '''
                SELECT * FROM asset 
                WHERE symbol =:sym OR name LIKE :nam
                '''),   {
                        "sym": s,
                        "nam": '%' + s + '%'
                    }
            ).first()
        else:
            row = None

    return render_template("search.html", row=row, watching=list)


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    
    if request.method == "POST":
        default_cash = 1_000_000
        theme =  request.form.get("theme")
        if theme is not None:
            
            # Set theme
            with Session() as cur:
                cur.execute(text('UPDATE settings SET theme =:s WHERE user_id =:i'),
                    {"s": theme, "i": g.user["id"]}
                )
                cur.commit()
           
            if theme == 'dark':
                session["theme"] = 'dark' 
            elif theme == 'auto':
                hr = time.localtime().tm_hour
                session["theme"] = 'dark' if hr > 18 or hr < 7 else None
            else:
                session["theme"] = None

            return redirect(url_for("main.settings"))
        
        # reset one - tables: trade, holding, badge, user
        elif request.form.get("reset") == "me":
            user_id = g.user["id"]
            with Session() as cur:
                cur.execute(text('delete from trade where user_id =:i'), {"i": user_id})
                cur.execute(text('delete from holding where user_id =:i'), {"i": user_id})
                cur.execute(text('delete from badge where user_id =:i'), {"i": user_id})
                u = cur.get(User, user_id)
                u.cash = default_cash
                cur.commit()
        
        # reset all
        elif request.form.get("reset") == "all":
            with Session() as cur:
                cur.execute(text('delete from trade'))
                cur.execute(text('delete from holding'))
                cur.execute(text('delete from badge'))
                cur.execute(text('update user set cash = :i'), {"i": default_cash})
                cur.commit()
            
        return redirect(url_for("index"))

    # GET
    user_id = g.user["id"]
    badges = get_badges()
    with Session() as cur:
        unlockables = cur.execute(select(Skull)).scalars().all()
    
    # pass user badges and list of unlockables
    return render_template("settings.html", badges=badges, unlockables=unlockables)


def get_badges():
    """Return a list of achievement id, given user_id"""

    badges = []
    with Session() as cur:
        u = cur.get(User, g.user["id"])
        for skull in u.badges:
            badges.append(skull.id)
    return badges


def add_badges(events):
    """Add earned achievements to user badge collection"""
    # return a list of achievement names to display to user
    
    # For each skull id passed in by events, we get a skull object from the ORM
    # and append it to the user collection. On commit, an automatic INSERT to the 
    # badge table is emitted with the combined (skull,user) foreign keys
    names = []
    with Session() as cur:
        u = cur.get(User, g.user["id"])
        for skull_id in events:
            skull = cur.get(Skull, skull_id)
            u.badges.append(skull)
            names.append(skull.name)
        cur.commit()
        
    return names


def is_profit(asset_id, price, qty):
    """Return True if proceeds from sale exceeds cash outlay"""
    
    # long side only
    # is holding this symbol? assume yes since we're currently selling
    # qty arg is qty owned before sale
    # profit is True if this trade price > (net historical basis)        
    
    # Query all trades of this symbol
    with Session() as cur:
        tb = cur.execute(select(Trade).where(
            Trade.user_id == g.user["id"],
            Trade.asset_id == asset_id        
        )).scalars().all()

        # Avg basis = (total outlay - total proceeds) / current qty
        sum = 0
        for row in tb:
            if row.type == 'buy':
                sum += (row.price * row.qty)
            else:
                sum -= (row.price * row.qty)
        basis = sum / qty

    return (price > basis)


def lookup(symbol):
    """Look up quote for symbol."""

    return None
    # Contact API
    # try:
        # api_key = os.environ.get("API_KEY")
        # url = f"https://some-foo.bar/stock/{urllib.parse.quote_plus(symbol)}/quote?token={api_key}"
        # response = requests.get(url)
        # response.raise_for_status()
    # except requests.RequestException:
    #     return None
    # Parse response
    # try:
    #     quote = response.json()
    #     return {
    #         "name": quote["companyName"],
    #         "price": float(quote["latestPrice"]),
    #         "symbol": quote["symbol"]
    #     }
    # except (KeyError, TypeError, ValueError):
    #     return None

def usd(value):
    """Format value as USD."""
    return f"{value:,.2f}"    