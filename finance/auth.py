import functools
from flask import (
    current_app, Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import select, text

from finance.db import Session
from finance.model import User

bp = Blueprint("auth", __name__, url_prefix="/auth")



@bp.after_app_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@bp.before_app_request
def load_logged_in_user():
   
    if "user_id" not in session:
        g.user = None
    else:
        user_id = session.get("user_id")
        name = session.get("username")
        g.user = {
            "id": user_id,
            "name": name
            }
        return     


@bp.route("/register", methods=["GET", "POST"])
def register():
   
    view = "/auth/register"

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        error = None

        if not username:
            error = "pls enter username"
        elif not password:
            error = "password required"

        # Insert new user
        if error is None:
            with Session() as du:
                r = du.execute(select(User).where(User.username == username)).scalar()
                if r is not None:
                    error = f"sry, {username} taken"
                else:
                    u = User(username=username, hash=generate_password_hash(password))
                    du.add(u)
                    user_id = du.execute(select(User.id).where(User.username == username)).scalar()
                    du.execute(text('INSERT INTO settings (user_id) VALUES (:i)'),
                        {"i": user_id}
                    )
                    du.commit()

        if error is not None:
            flash(error)
            return render_template("auth/login.html", view=view)
        
        return redirect(url_for("auth.login"))

    # GET
    return render_template("auth/login.html", view=view)


@bp.route("/login", methods=["GET", "POST"])
def login():
   
    view = "/auth/login"

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        error = None

        # Validate user
        with Session() as cur:
            row = cur.execute(
                select(User).where(
                    User.username == username
            )).scalar()
            if row is None:
                error = "bad username"
            elif not check_password_hash(row.hash, password):
                error = "invalid credentials"

        if error is not None:
            flash(error)
            return render_template("auth/login.html", view=view)
        
        session.clear()
        session["user_id"] = row.id
        session["username"] = username
        session["theme"] = None
        return redirect(url_for("index"))      
   
    # GET
    return render_template("auth/login.html", view=view)


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


# Wrap view functions to require login
def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
           return redirect(url_for("auth.login"))

        return view(**kwargs)

    return wrapped_view