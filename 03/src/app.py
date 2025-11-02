import os
import re
from datetime import datetime

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
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
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


class Post(db.Model):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    author = Column(String(64), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Flag(db.Model):
    __tablename__ = "flags"
    id = Column(Integer, primary_key=True)
    flag = Column(Text, nullable=False)


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
    return dict(current_user=get_current_user())


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
    posts = db.session.query(Post).order_by(Post.created_at.desc()).all()
    return render_template("index.html", posts=posts, current_username=(get_current_user().username if get_current_user() is not None else None))


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

        user = User(username=username, password_hash=ph.hash(password), is_admin=False)
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
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for("index"))


@app.route("/post/create", methods=["POST"])
def create_post():
    current_user = get_current_user()
    if not current_user:
        flash("Please log in first.", "danger")
        return redirect(url_for("index"))
    # author = request.form.get("author", "").strip()
    content = request.form.get("content", "").strip()

    if not content:
        flash("Content is required", "danger")
        return redirect(url_for("index"))

    post = Post(author=current_user.username, content=content)
    db.session.add(post)
    db.session.commit()

    flash("Post created successfully!", "success")
    return redirect(url_for("index"))


@app.route("/post/<int:post_id>")
def post_detail(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        abort(404)
    return render_template("post_detail.html", post=post)


@app.route("/post/<int:post_id>/report", methods=["POST"])
def report_post(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        abort(404)

    appHostname = os.environ.get("INTERNAL_HOST", "http://web:8080")

    if RQ_ENABLED:
        report_queue.enqueue("handler.visit", f"{appHostname}/post/{post_id}")
        flash("Post reported to admin. They will review it shortly.", "info")
    else:
        flash("Reporting is currently unavailable", "warning")

    return redirect(url_for("index"))


@app.route("/admin")
def admin_panel():
    _ = require_admin()

    filter_query = request.args.get("filter", "")
    try:
        # Sanitize filter
        filter_query = re.sub(r"flag", "", filter_query, flags=re.IGNORECASE)
        if filter_query:
            sql = f"SELECT * FROM posts WHERE {filter_query}"
            result = db.session.execute(db.text(sql))
            posts = result.fetchall()
        else:
            posts = db.session.query(Post).order_by(Post.created_at.desc()).all()

        return render_template("admin.html", posts=posts, filter_query=filter_query)
    except Exception as e:
        print(f"Error in admin_panel: {e}")


@app.route("/health")
def health():
    return "OK"


# ------------------------------------------------------------
# Database initialization
# ------------------------------------------------------------


def init_db():
    with app.app_context():
        db.create_all()

        # Create admin user
        admin_password = os.environ.get("ADMIN_PASSWORD", None)
        admin = User(
            username="admin", password_hash=ph.hash(admin_password), is_admin=True
        )
        db.session.add(admin)

        # Add flag to separate table
        flag = Flag(flag=os.environ.get("FLAG", "pitfalls{fake_flag}"))
        db.session.add(flag)

        # Add some sample posts
        posts = [
            Post(
                author="Alice",
                content="Welcome to <i>Náměstí</i>! This is a great platform.",
            ),
            Post(author="Bob", content="Just posted my first message here!"),
            Post(
                author="Charlie", content="Looking forward to connecting with everyone."
            ),
        ]
        for post in posts:
            db.session.add(post)

        db.session.commit()


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    app.run(debug=False, host="0.0.0.0", port=8080)
