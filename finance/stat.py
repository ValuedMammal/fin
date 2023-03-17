import time
from flask import (
    current_app, Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from sqlalchemy import select, text

from finance.auth import login_required
from finance.db import Session
from finance.model import User

bp = Blueprint("stat", __name__, url_prefix="/stat")
  

@bp.route("/history", methods=["GET"])
@login_required
def history():

    user_id = g.user["id"]
    
    # history
    with Session() as du:
        tb = du.execute(text('''
                SELECT type, symbol, qty, trade.price, time
                FROM trade, asset
                WHERE trade.asset_id = asset.id
                AND trade.user_id =:i
                ORDER BY time DESC
                    '''), {"i": user_id}
        ).all()
    
    return render_template("/stat/history.html", trades=tb)


@bp.route("/leaders")
def leaders():
    """Display leaderboard for all users"""

    list = []
    with Session() as cur:

        # For each user, get largest holding and total asset value (ex-cash)
        for user in cur.execute(select(User)).scalars().all():
            user_id = user.id
            name = user.username

            # Largest symbol - 1 row
            large = cur.execute(text(
                '''
                SELECT symbol, max(qty*price) 
                FROM holding, asset
                WHERE holding.asset_id = asset.id
                AND holding.user_id =:i''' ), {"i": user_id}
            ).first()

            # Total portfolio - 1 row
            sum = cur.execute(text(
                '''
                SELECT sum(qty*price) 
                FROM holding, asset
                WHERE holding.asset_id = asset.id
                AND holding.user_id =:i'''), {"i": user_id}
            ).scalar()
            
            if sum is not None:
                dict = {
                        "user_id": user_id,
                        "name": name,
                        "symbol": large.symbol,
                        "sum": sum
                }
            
            # no holdings for this user
            else:
                dict = {
                        "user_id": user_id,
                        "name": name,
                        "symbol": "None",
                        "sum": 0
                }
            if len(list) == 0: # first iteration
                list.append(dict)
            elif dict["sum"] < list[-1]["sum"]:
                list.append(dict)
            else:
                for i in range(len(list)):
                    if dict["sum"] > list[i]["sum"]:
                        list.insert(i, dict)
                        break
    
    return render_template("/stat/leaders.html", list=list)


@bp.route("/publish", methods=["POST"])
def publish():
    flash("not implemented")
    return redirect(url_for("stat.leaders"))
