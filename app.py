import ipaddress
import os
import re
import secrets

from flask import (
    Flask,
    abort,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

import store
from collector import collect_metrics

HOST = "127.0.0.1"
PORT = 5050
AUTH_ERROR = "Invalid username or password."
_DUMMY_HASH = None


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", ""),
        DATABASE=os.path.join(app.root_path, "monitor.db"),
        HOST=HOST,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        COLLECT_METRICS=collect_metrics,
        MAX_CONTENT_LENGTH=16 * 1024,
    )
    if config:
        app.config.update(config)
    if not app.config["SECRET_KEY"]:
        raise RuntimeError("FLASK_SECRET_KEY is not set")

    store.init_db(app.config["DATABASE"])

    @app.context_processor
    def inject_csrf():
        return {"csrf_token": csrf_token}

    @app.teardown_appcontext
    def close_db(_error):
        connection = g.pop("db", None)
        if connection is not None:
            connection.close()

    @app.before_request
    def require_session():
        if request.endpoint in {"setup", "setup_submit", "signin", "signin_submit", "static"} or request.endpoint is None:
            return None
        if session.get("user") == "admin":
            return None
        if store.admin_hash(get_db()) is None:
            return redirect(url_for("setup"))
        return redirect(url_for("signin"))

    @app.get("/setup")
    def setup():
        if store.admin_hash(get_db()) is not None:
            return redirect(url_for("signin"))
        return render_template("setup.html", error=None)

    @app.post("/setup")
    def setup_submit():
        if store.admin_hash(get_db()) is not None:
            return redirect(url_for("signin"))
        if not csrf_ok():
            abort(400)
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if not password:
            return render_template("setup.html", error="Choose a password."), 400
        if password != confirm:
            return render_template("setup.html", error="Passwords do not match."), 400
        store.save_admin(get_db(), generate_password_hash(password))
        flash("Password saved. Sign in.")
        return redirect(url_for("signin"))

    @app.get("/signin")
    def signin():
        if store.admin_hash(get_db()) is None:
            return redirect(url_for("setup"))
        if session.get("user") == "admin":
            return redirect(url_for("index"))
        return render_template("signin.html", error=None)

    @app.post("/signin")
    def signin_submit():
        if store.admin_hash(get_db()) is None:
            return redirect(url_for("setup"))
        if not csrf_ok():
            abort(400)
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if not credentials_ok(get_db(), username, password):
            return render_template("signin.html", error=AUTH_ERROR), 200
        session.clear()
        session["user"] = "admin"
        session["csrf_token"] = secrets.token_urlsafe(32)
        return redirect(url_for("index"))

    @app.post("/signout")
    def signout():
        if not csrf_ok():
            abort(400)
        session.clear()
        return redirect(url_for("signin"))

    @app.get("/")
    def index():
        servers = store.list_servers(get_db())
        return render_template("index.html", servers=servers, error=None, form=empty_form())

    @app.post("/servers")
    def add_server():
        if not csrf_ok():
            abort(400)
        form = {
            "display_name": request.form.get("display_name", "").strip(),
            "host": request.form.get("host", "").strip(),
            "port": request.form.get("port", "").strip(),
            "ssh_user": request.form.get("ssh_user", "").strip(),
        }
        password = request.form.get("ssh_password", "")
        error = validate_server(form, password)
        if error:
            servers = store.list_servers(get_db())
            return render_template("index.html", servers=servers, error=error, form=form), 400
        store.add_server(
            get_db(),
            form["display_name"],
            form["host"],
            int(form["port"]),
            form["ssh_user"],
            password,
        )
        return redirect(url_for("index"))

    @app.post("/servers/<int:server_id>/delete")
    def delete_server(server_id):
        if not csrf_ok():
            abort(400)
        store.delete_server(get_db(), server_id)
        return redirect(url_for("index"))

    @app.get("/servers/<int:server_id>")
    def server_detail(server_id):
        summary = store.get_server_summary(get_db(), server_id)
        if summary is None:
            abort(404)
        snapshot = snapshot_for(server_id)
        return render_template("server.html", server=summary, snapshot=snapshot)

    @app.get("/servers/<int:server_id>/metrics")
    def server_metrics(server_id):
        summary = store.get_server_summary(get_db(), server_id)
        if summary is None:
            abort(404)
        return jsonify(public_snapshot(snapshot_for(server_id)))

    return app


def get_db():
    if "db" not in g:
        g.db = store.connect(current_database())
    return g.db


def current_database():
    return current_app.config["DATABASE"]


def csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def csrf_ok():
    sent = request.form.get("csrf_token", "")
    stored = session.get("csrf_token", "")
    if not sent or not stored:
        return False
    return secrets.compare_digest(sent, stored)


def credentials_ok(connection, username, password):
    stored = store.admin_hash(connection)
    if username != "admin" or stored is None:
        check_password_hash(dummy_hash(), password or "unused")
        return False
    return check_password_hash(stored, password)


def dummy_hash():
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = generate_password_hash("unused-dummy-value")
    return _DUMMY_HASH


def empty_form():
    return {"display_name": "", "host": "", "port": "22", "ssh_user": ""}


def validate_server(form, password):
    name = form["display_name"]
    if not name or len(name) > 80 or any(ord(char) < 32 for char in name):
        return "Enter a display name."
    if not valid_host(form["host"]):
        return "Enter a valid host."
    if not re.fullmatch(r"\d{1,5}", form["port"]):
        return "Enter a port from 1 to 65535."
    port = int(form["port"])
    if port < 1 or port > 65535:
        return "Enter a port from 1 to 65535."
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,32}", form["ssh_user"]):
        return "Enter an SSH user name."
    if not password or len(password) > 256:
        return "Enter an SSH password."
    return None


def valid_host(value):
    if not value or len(value) > 253:
        return False
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        pass
    hostname = value[:-1] if value.endswith(".") else value
    if ".." in hostname:
        return False
    labels = hostname.split(".")
    for label in labels:
        if not label or len(label) > 63:
            return False
        if label.startswith("-") or label.endswith("-"):
            return False
        if not re.fullmatch(r"[A-Za-z0-9-]+", label):
            return False
    return True


def snapshot_for(server_id):
    login = store.get_server_login(get_db(), server_id)
    if login is None:
        return {"error": "unreachable"}
    raw = current_app.config["COLLECT_METRICS"](
        {
            "host": login["host"],
            "port": login["port"],
            "ssh_user": login["ssh_user"],
            "ssh_password": login["ssh_password"],
        }
    )
    return public_snapshot(raw)


def public_snapshot(raw):
    if not isinstance(raw, dict):
        return {"error": "could not read metrics"}
    error = raw.get("error")
    if error:
        return {"error": error}
    return {
        "error": None,
        "cpu_percent": raw.get("cpu_percent"),
        "memory": raw.get("memory"),
        "network": raw.get("network") or [],
        "ports": raw.get("ports") or [],
    }


def main():
    try:
        application = create_app()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    application.run(host=HOST, port=PORT)


if __name__ == "__main__":
    main()
