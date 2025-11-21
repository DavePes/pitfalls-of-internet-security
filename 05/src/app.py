import asyncio
import json
import lzma
import os
import threading
from datetime import datetime

import yaml
from argon2 import PasswordHasher
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.pool import StaticPool

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

db = SQLAlchemy()
db.init_app(app)

# ------------------------------------------------------------
# Global State
# ------------------------------------------------------------


class GlobalState:
    def __init__(self):
        self._state = {}
        self._lock = threading.Lock()

    def get_safe_mode(self):
        with self._lock:
            return self._state.get("safe_mode")

    def set_safe_mode(self, value):
        with self._lock:
            self._state["safe_mode"] = value

    def ensure_defaults(self):
        with self._lock:
            self._state["safe_mode"] = True
            self._state["import_in_progress"] = False

    def update(self, state):
        with self._lock:
            self._state = state

    def get(self, name):
        with self._lock:
            return self._state.get(name)

    @property
    def lock(self):
        """Get the lock for external use if needed."""
        return self._lock


gs = GlobalState()

# ------------------------------------------------------------
# Models
# ------------------------------------------------------------


class User(db.Model):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    is_admin = Column(Boolean, default=False)


class Conversion(db.Model):
    __tablename__ = "conversions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    yaml_input = Column(Text, nullable=False)
    json_output = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


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
    return dict(current_user=get_current_user(), safe_mode=gs.get_safe_mode())


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
# Routes
# ------------------------------------------------------------


@app.route("/")
def index():
    # TODO: add warning about degraded performance when some import is in progress
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
        return redirect(url_for("converter"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for("index"))


@app.route("/converter")
def converter():
    current_user = require_login()

    conversions = (
        db.session.query(Conversion)
        .filter_by(user_id=current_user.id)
        .order_by(Conversion.created_at.desc())
        .all()
    )

    return render_template("converter.html", conversions=conversions)


@app.route("/convert", methods=["POST"])
def convert():
    current_user = require_login()

    yaml_input = request.form.get("yaml_input", "").strip()

    if not yaml_input:
        flash("Please provide YAML input", "danger")
        return redirect(url_for("converter"))

    try:
        current_mode = gs.get_safe_mode()

        if current_mode:
            parsed = yaml.safe_load(yaml_input)
        else:
            parsed = yaml.load(yaml_input, Loader=yaml.Loader)

        json_output = json.dumps(parsed, indent=2)

        conversion = Conversion(
            user_id=current_user.id,
            yaml_input=yaml_input,
            json_output=json_output,
        )
        db.session.add(conversion)
        db.session.commit()

        flash("Conversion successful!", "success")
    except Exception as e:
        flash(f"Conversion failed: {str(e)}", "danger")

    return redirect(url_for("converter"))


@app.route("/admin/config", methods=["GET", "POST"])
def admin_config():
    current_user = require_admin()

    if request.method == "POST":
        mode = request.form.get("safe_mode")

        gs.set_safe_mode(mode == "true")

        flash(
            f"Parser mode updated to: {'safe_load' if gs.get_safe_mode() else 'load'}",
            "success",
        )
        return redirect(url_for("admin_config"))

    return render_template("admin_config.html")


@app.route("/import", methods=["GET", "POST"])
async def import_conversions():
    current_user = require_login()

    if request.method == "GET":
        return render_template("import.html")

    if "file" not in request.files:
        flash("No file uploaded", "danger")
        return redirect(url_for("import_conversions"))

    file = request.files["file"]

    if file.filename == "":
        flash("No file selected", "danger")
        return redirect(url_for("import_conversions"))

    if not file.filename.endswith(".yaml.xz"):
        flash("Please upload a .yaml.xz file (LZMA compressed YAML)", "danger")
        return redirect(url_for("import_conversions"))

    try:
        compressed_data = file.read()

        gs.update({"import_in_progress": True})

        decompressed_data = await asyncio.to_thread(lzma.decompress, compressed_data)

        yaml_content = decompressed_data.decode("utf-8")

        parsed = yaml.safe_load(yaml_content)
        json_output = json.dumps(parsed, indent=2)

        conversion = Conversion(
            user_id=current_user.id,
            yaml_input=yaml_content,
            json_output=json_output,
        )
        db.session.add(conversion)
        db.session.commit()

        flash("Import successful!", "success")
    except lzma.LZMAError as e:
        flash(f"Decompression failed: {str(e)}", "danger")
    except Exception as e:
        flash(f"Import failed: {str(e)}", "danger")
    finally:
        gs.ensure_defaults()

    return redirect(url_for("converter"))


@app.route("/history")
def history():
    current_user = require_login()

    conversions = (
        db.session.query(Conversion)
        .filter_by(user_id=current_user.id)
        .order_by(Conversion.created_at.desc())
        .all()
    )

    return render_template("history.html", conversions=conversions)


@app.route("/health")
def health():
    return "OK"


# ------------------------------------------------------------
# Database initialization
# ------------------------------------------------------------


def init_db():
    with app.app_context():
        db.create_all()

        admin_password = os.environ.get("ADMIN_PASSWORD")

        admin = User(
            username="admin",
            password_hash=ph.hash(admin_password),
            is_admin=True,
        )
        db.session.add(admin)

        db.session.commit()


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------


def create_app():
    init_db()
    gs.ensure_defaults()
    return app
