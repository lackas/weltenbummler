"""Weltenbummler: a family map of the countries each of us has visited."""

import json
import os
import secrets
from datetime import timedelta
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from . import cli
from .db import close_db, get_db
from .users import UserError, authenticate, create_user, new_password, set_password

NOTE_MAX = 2000


def _secret_key(instance_path):
    path = Path(instance_path) / "secret_key"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_hex(32))
        path.chmod(0o600)
    return path.read_text().strip()


def _country_ids(static_folder):
    """Every id on the map: countries ("DEU") and US states ("US-CA")."""
    topology = json.loads((Path(static_folder) / "countries.json").read_text())
    return {geometry["id"] for layer in topology["objects"].values() for geometry in layer["geometries"]}


def create_app(config=None):
    app = Flask(__name__, instance_path=os.environ.get("WELTENBUMMLER_INSTANCE"))
    app.config.update(
        DATABASE=str(Path(app.instance_path) / "weltenbummler.sqlite"),
        # Chrome and Edge cap cookies at 400 days, so that is the practical maximum
        PERMANENT_SESSION_LIFETIME=timedelta(days=400),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("WELTENBUMMLER_INSECURE_COOKIE") != "1",
    )
    if config:
        app.config.update(config)
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = _secret_key(app.instance_path)
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    app.config["COUNTRIES"] = _country_ids(app.static_folder)

    app.teardown_appcontext(close_db)
    cli.register(app)

    @app.before_request
    def load_user():
        g.user = None
        uid, epoch = session.get("uid"), session.get("epoch")
        if uid is None:
            return
        user = get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
        # a password reset bumps the epoch and so ends every older session
        if user is not None and user["session_epoch"] == epoch:
            g.user = user
        else:
            session.clear()

    @app.after_request
    def security_headers(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
            "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'; "
            "object-src 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                if request.path.startswith("/api/"):
                    abort(401)
                return redirect(url_for("login"))
            return view(*args, **kwargs)

        return wrapped

    def admin_required(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if not g.user["is_admin"]:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    @app.get("/login")
    def login():
        return render_template("login.html")

    @app.post("/login")
    def login_post():
        user = authenticate(get_db(), request.form.get("name", ""), request.form.get("password", ""))
        if user is None:
            flash("Name oder Passwort stimmt nicht.")
            return render_template("login.html", name=request.form.get("name", "")), 401
        session.clear()
        session.permanent = True
        session["uid"] = user["id"]
        session["epoch"] = user["session_epoch"]
        return redirect(url_for("index"))

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/")
    @login_required
    def index():
        return render_template("index.html")

    @app.get("/password")
    @login_required
    def password():
        return render_template("password.html")

    @app.post("/password")
    @login_required
    def password_post():
        db = get_db()
        if authenticate(db, g.user["name"], request.form.get("old", "")) is None:
            flash("Das bisherige Passwort stimmt nicht.")
            return render_template("password.html"), 400
        new = request.form.get("new", "")
        if len(new) < 8:
            flash("Das neue Passwort braucht mindestens 8 Zeichen.")
            return render_template("password.html"), 400
        set_password(db, g.user["id"], new)
        # stay logged in here, everywhere else is logged out by the epoch bump
        session["epoch"] = g.user["session_epoch"] + 1
        flash("Passwort geändert.")
        return redirect(url_for("index"))

    @app.get("/admin")
    @admin_required
    def admin():
        users = get_db().execute("SELECT * FROM users ORDER BY is_admin DESC, id").fetchall()
        return render_template("admin.html", users=users)

    @app.post("/admin/users")
    @admin_required
    def admin_create():
        password = new_password()
        try:
            create_user(get_db(), request.form.get("name", ""), password)
        except UserError as e:
            flash(str(e))
        else:
            flash(f"{request.form['name'].strip()} angelegt, Passwort: {password}")
        return redirect(url_for("admin"))

    @app.post("/admin/users/<int:user_id>/reset")
    @admin_required
    def admin_reset(user_id):
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            abort(404)
        password = new_password()
        set_password(db, user_id, password)
        flash(f"Neues Passwort für {user['name']}: {password}")
        return redirect(url_for("admin"))

    @app.get("/api/data")
    @login_required
    def api_data():
        db = get_db()
        users = [
            {"id": u["id"], "name": u["name"], "visits": {}}
            for u in db.execute("SELECT id, name FROM users ORDER BY id")
        ]
        by_id = {u["id"]: u for u in users}
        for v in db.execute("SELECT user_id, country, note FROM visits"):
            by_id[v["user_id"]]["visits"][v["country"]] = v["note"]
        return jsonify(me={"id": g.user["id"], "admin": bool(g.user["is_admin"])}, users=users)

    def _editable_visit(user_id, country):
        if g.user["id"] != user_id and not g.user["is_admin"]:
            abort(403)
        if country not in app.config["COUNTRIES"]:
            abort(404)
        if get_db().execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None:
            abort(404)

    @app.put("/api/users/<int:user_id>/visits/<country>")
    @login_required
    def api_put_visit(user_id, country):
        _editable_visit(user_id, country)
        # JSON only: a cross-site form cannot send it without a CORS preflight
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or not isinstance(body.get("note", ""), str):
            abort(400)
        note = body.get("note", "")[:NOTE_MAX]
        db = get_db()
        db.execute(
            "INSERT INTO visits (user_id, country, note) VALUES (?, ?, ?) "
            "ON CONFLICT (user_id, country) DO UPDATE SET note = excluded.note",
            (user_id, country, note),
        )
        db.commit()
        return jsonify(country=country, note=note)

    @app.delete("/api/users/<int:user_id>/visits/<country>")
    @login_required
    def api_delete_visit(user_id, country):
        _editable_visit(user_id, country)
        if request.headers.get("X-Requested-With") != "weltenbummler":
            abort(400)
        db = get_db()
        db.execute("DELETE FROM visits WHERE user_id = ? AND country = ?", (user_id, country))
        db.commit()
        return "", 204

    return app
