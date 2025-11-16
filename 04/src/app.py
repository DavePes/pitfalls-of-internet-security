import os
import re

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    abort,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Boolean, Column, Integer, String, Text
from sqlalchemy.pool import StaticPool
from argon2 import PasswordHasher

try:
    from redis import Redis
    from rq import Queue

    redis_conn = Redis(host="redis", port=6379)
    report_queue = Queue("default", connection=redis_conn)
    RQ_ENABLED = True
except Exception:
    RQ_ENABLED = False

# ------------------------------------------------------------
# App setup
# ------------------------------------------------------------

ph = PasswordHasher()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(64))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "poolclass": StaticPool,
    "connect_args": {"check_same_thread": False},
}

HCAPTCHA_SECRET = os.environ.get(
    "HCAPTCHA_SECRET", "0x0000000000000000000000000000000000000000"
)
HCAPTCHA_SITEKEY = os.environ.get(
    "HCAPTCHA_SITEKEY", "10000000-ffff-ffff-ffff-000000000001"
)

db = SQLAlchemy()
db.init_app(app)


# ------------------------------------------------------------
# Models
# ------------------------------------------------------------


class User(db.Model):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    is_admin = Column(Boolean, default=False)
    note_content = Column(Text, default="")


# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------


def get_current_user():
    user_id = session.get("user_id")
    if user_id:
        return db.session.get(User, user_id)
    return None


@app.context_processor
def inject_user():
    return dict(current_user=get_current_user(), hcaptcha_sitekey=HCAPTCHA_SITEKEY)


def require_login():
    user = get_current_user()
    if not user:
        flash("Please log in first.", "danger")
        abort(403)
    return user


def require_admin():
    user = get_current_user()
    if not user or not user.is_admin:
        abort(403)
    return user


# ------------------------------------------------------------
# CSP Header
# ------------------------------------------------------------


@app.after_request
def set_csp(response):
    response.headers["Content-Security-Policy"] = (
        "script-src 'self' https://hcaptcha.com https://*.hcaptcha.com 'unsafe-eval'; "
        "style-src 'self' https://cdn.jsdelivr.net/npm/bulma@1.0.1/css/bulma.min.css https://hcaptcha.com https://*.hcaptcha.com; "
        "frame-src https://hcaptcha.com https://*.hcaptcha.com;"
        "connect-src 'self' https://hcaptcha.com https://*.hcaptcha.com;"
        "img-src 'self';"
        "base-uri 'none';"
        "default-src 'none';"
        "frame-ancestors 'none'"
    )
    return response


# ------------------------------------------------------------
# Routes
# ------------------------------------------------------------


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Username and password are required", "danger")
            return redirect(url_for("register"))

        existing_user = db.session.query(User).filter_by(username=username).first()
        if existing_user:
            flash("Username already exists", "danger")
            return redirect(url_for("register"))

        user = User(
            username=username,
            password_hash=ph.hash(password),
            is_admin=False,
            note_content="Welcome to your Personal Space! Edit this note to make it your own.",
        )
        db.session.add(user)
        db.session.commit()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = db.session.query(User).filter_by(username=username).first()

        if not user:
            flash("Invalid username or password", "danger")
            return redirect(url_for("login"))

        try:
            ph.verify(user.password_hash, password)
        except Exception:
            flash("Invalid username or password", "danger")
            return redirect(url_for("login"))

        session["user_id"] = user.id
        session["username"] = user.username
        flash(f"Welcome back, {user.username}!", "success")
        return redirect(url_for("space"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for("index"))


@app.route("/space")
def space():
    current_user = require_login()

    # Admin can view other users' spaces
    view_user = current_user
    if current_user.is_admin:
        username = request.args.get("user")
        if username:
            view_user = db.session.query(User).filter_by(username=username).first()
            if not view_user:
                flash("User not found", "danger")
                return redirect(url_for("space"))

    return render_template("space.html", view_user=view_user)


@app.route("/space/edit", methods=["GET"])
def space_edit():
    current_user = require_login()
    return render_template("space_edit.html")


@app.route("/space/update", methods=["POST"])
def space_update():
    current_user = require_login()

    # Verify hCaptcha
    # For testing with hCaptcha test keys, we accept any response (this is also the case in ReCodEx)
    # In real production, we would verify with hCaptcha API
    hcaptcha_response = request.form.get("h-captcha-response", "")
    if not hcaptcha_response:
        flash("Please complete the hCaptcha verification", "danger")
        return redirect(url_for("space_edit"))

    # Admin can update other users' spaces
    view_user = current_user
    if current_user.is_admin:
        username = request.args.get("user")
        if username:
            view_user = db.session.query(User).filter_by(username=username).first()
            if not view_user:
                flash("User not found", "danger")
                return redirect(url_for("space_edit"))

    content = request.form.get("content", "")
    view_user.note_content = content
    db.session.commit()

    flash("Updated!", "success")
    return redirect(url_for("space"))


@app.route("/space/request_guidance", methods=["POST"])
def request_guidance():
    current_user = require_login()

    appHostname = os.environ.get("INTERNAL_HOST", "http://web:8080")

    if RQ_ENABLED:
        report_queue.enqueue(
            "handler.visit", f"{appHostname}/space?user={current_user.username}"
        )
        flash(
            "Your request has been sent to the admin. They will review your space shortly.",
            "info",
        )
    else:
        flash("Guidance requests are currently unavailable", "warning")

    return redirect(url_for("space"))


@app.route("/meditation")
def meditation():
    return render_template("meditation.html")


@app.route("/health")
def health():
    return "OK"


# ------------------------------------------------------------
# Database initialization
# ------------------------------------------------------------


def init_db():
    with app.app_context():
        db.create_all()

        # Create admin user with flag in note
        admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
        flag = os.environ.get("FLAG", "pitfalls{fake_flag}")

        admin = User(
            username="admin",
            password_hash=ph.hash(admin_password),
            is_admin=True,
            note_content=f"Welcome admin! Your flag is: {flag}",
        )
        db.session.add(admin)
        db.session.commit()


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    app.run(debug=False, host="0.0.0.0", port=8080)
