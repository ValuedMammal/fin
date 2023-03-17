import time

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from sqlalchemy import select, text

from finance.auth import login_required
from finance.db import Session
from finance.helpers import lookup, usd
from finance.model import User, Asset, Hodl, Trade, Skull

bp = Blueprint("main", __name__)


@bp.route("/", methods=["GET"])
@login_required
def index():
        
    user_id = g.user["id"]
    asset_val = 0
    holdings = []    

    # Portfolio view
    with Session() as cur:
        u = cur.get(User, user_id)
        cash = u.cash
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
            'SELECT theme FROM settings WHERE user_id = :i'
            ), {"i": user_id}
        ).scalar()

    if theme == 'dark':
        session["theme"] = 'dark' 
    elif theme == 'auto':
        hr = time.localtime().tm_hour
        session["theme"] = 'dark' if hr > 18 or hr < 7 else None            
    else:
        session["theme"] = None
    
    total = (cash + asset_val)

    return render_template("index.html", holdings=holdings, cash=cash, asset_val=asset_val, total=total)
    

@bp.route("/trade", methods=["GET", "POST"])
@login_required
def trade():
    
    # POST
    if request.method == "POST":
        user_id = g.user["id"]
        symbol = request.form.get("symbol").upper()
        shares = int(request.form.get("shares"))
        view = request.form.get("view")
        type = request.form.get("type")
        badges = get_badges()
        events = []     # listen for achievement events

        # Fetch quote
        asset_id = None
        quote = lookup(symbol)
        if quote is None:
            flash("None")
            return redirect(url_for(view))
        price = quote["price"]
        name = quote["name"]
        val = (shares * price)

        # Get user inventory
        qty = 0
        with Session() as db:
            u = db.get(User, user_id)
            cash = u.cash
            a = db.execute(select(Asset).where(Asset.symbol == symbol)).scalar()
            if a is not None:
                asset_id = a.id
                h = db.get(Hodl, (asset_id,user_id))
                if h is not None:
                    qty = h.qty
        
        # buy
        error = None
        if type == 'buy':
            if val > cash:
                error = "rejected low cash"
            cash -= val
            qty += shares

        # sell
        else:
            if qty == 0:
                error = "you don't own it"
            elif shares > qty:
                error = "rejected low inventory"
            else:
                profit = is_profit(asset_id, val, qty)
                cash += val
                qty -= shares

        if error is not None:
            flash(error)
            return redirect(url_for(view))
        
        # Update tables: asset, holding, user, trade
        with Session() as db:
            if asset_id is None:
                db.add(
                    Asset(symbol=symbol, name=name, price=price)
                )
                a = db.execute(select(Asset).where(Asset.symbol == symbol))
                asset_id = a.id
            else:
                a = db.get(Asset, asset_id)
                a.price = price           

            h = db.get(Hodl, (asset_id,user_id))
            if h is None:
                db.add(
                    Hodl(asset_id=asset_id, user_id=user_id, qty=qty)
                )
            else:
                h.qty = qty

            u = db.get(User, user_id)
            u.cash = cash

            db.add(
                Trade(type=type, user_id=user_id, asset_id=asset_id, qty=shares, price=price)
            )
            db.commit()
        
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


@bp.route("/quote", methods=["POST"])
@login_required
def quote():
    
    if request.method == "POST":
        user_id = g.user["id"]
        
        # Lookup
        symbol = request.form.get("symbol").upper()
        quote = lookup(symbol)
        if quote is not None:
            name = quote["name"]
            price = quote["price"]
        
            # Update db
            with Session() as db:
                a = db.execute(select(Asset).where(
                    Asset.symbol == symbol
                )).scalar()
                if a is None:
                    db.add(
                        Asset(symbol=symbol, name=name, price=price)
                    )
                    a = db.execute(select(Asset).where(Asset.symbol == symbol)).scalar()
                else:
                    a.price = price
                
                # Add to watching if not present
                h = db.get(Hodl, (a.id, user_id))
                if h is None:
                    db.add(
                        Hodl(asset_id=a.id, user_id=user_id, qty=0)
                    )
                db.commit()
            
            flash("Found: {} ${}".format(symbol, usd(price)))
            return redirect("/")

        flash("None")
        return redirect("/")


@bp.route("/watch", methods=["POST"])
@login_required
def watch():
    """Add a symbol to user watch list"""
    
    asset_id = request.form.get("asset")
    symbol = request.form.get("symbol")

    with Session() as db:
        db.add(
            Hodl(asset_id=asset_id, user_id=g.user["id"], qty=0)
        )
        db.commit()
    
    flash(f"added {symbol}")
    return redirect(url_for("main.quote"))


@bp.route("/unwatch", methods=["POST"])
@login_required
def unwatch():
    """Remove a symbol from watch list"""
    
    user_id = g.user["id"]
    asset_id = request.form.get("asset")
    with Session() as db:
        h = db.get(Hodl, (asset_id,user_id))
        db.delete(h)
        db.commit()
    return redirect("/")


@bp.route("/search", methods=["GET"])
@login_required
def search():
    """Handle a request for database records"""
    # search assets for exact symbol or name like
    # return 1 row w symbol, name
        
    s = request.args.get("q").upper()
    if s is None or s == '':
        row = None
    else:
        with Session() as db:
            row = db.execute(text(
                '''
                SELECT * FROM asset 
                WHERE symbol =:sym OR name LIKE :nam
                '''), {
                    "sym": s,
                    "nam": '%' + s + '%'
                }).first()
    
    return render_template("search.html", row=row)


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    
    if request.method == "POST":
        default_cash = 1_000_000
        theme =  request.form.get("theme")
        if theme is not None:
            
            # Set theme
            with Session() as db:
                db.execute(text('UPDATE settings SET theme =:s WHERE user_id =:i'),
                    {"s": theme, "i": g.user["id"]}
                )
                db.commit()
           
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
            with Session() as db:
                db.execute(text('delete from trade where user_id =:i'), {"i": user_id})
                db.execute(text('delete from holding where user_id =:i'), {"i": user_id})
                db.execute(text('delete from badge where user_id =:i'), {"i": user_id})
                u = db.get(User, user_id)
                u.cash = default_cash
                db.commit()
        
        # reset all
        elif request.form.get("reset") == "all":
            with Session() as db:
                db.execute(text('delete from trade'))
                db.execute(text('delete from holding'))
                db.execute(text('delete from badge'))
                db.execute(text('update user set cash = :i'), {"i": default_cash})
                db.commit()
            
        return redirect(url_for("index"))

    # GET
    user_id = g.user["id"]
    badges = get_badges()
    with Session() as db:
        unlockables = db.execute(select(Skull)).scalars().all()
    
    return render_template("settings.html", badges=badges, unlockables=unlockables)


def get_badges():
    """Return a list of achievement id, given user id"""

    badges = []
    with Session() as db:
        u = db.get(User, g.user["id"])
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
    with Session() as db:
        u = db.get(User, g.user["id"])
        for skull_id in events:
            skull = db.get(Skull, skull_id)
            u.badges.append(skull)
            names.append(skull.name)
        db.commit()
        
    return names


def is_profit(asset_id, value, qty):
    """Return True if proceeds from sale exceeds cash outlay"""
    # param: asset, 
    # param: this sale value, 
    # param: prev qty owned    

    # profit is True if this trade val > outlay of current holdings
    
    # Query all trades of this symbol
    with Session() as db:
        sel = text(
            '''
            SELECT * from trade
            WHERE trade.asset_id = :a
            AND trade.user_id = :i
            ORDER BY time DESC
            '''
        ).bindparams(a=asset_id, i=g.user["id"])

        # Crunch value spent
        owned = 0
        spent = 0
        for row in db.execute(sel).all():
            val = row.price * row.qty
            if row.type == 'buy':
                owned += row.qty
                spent += val
            else:
                owned -= row.qty
                spent -= val
            if owned == qty:
                break

    return (value > spent)