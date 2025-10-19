import os
from flask import Flask, render_template, request, redirect, url_for, flash
from sqlalchemy import Column, String, Text
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import declarative_base
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad, unpad
from Cryptodome.Random import get_random_bytes
import hmac
import json
import hashlib
from argon2 import PasswordHasher

ph = PasswordHasher()

app = Flask(__name__)
# app.secret_key = (
#     os.environ.get("SECRET_KEY", "").encode()
#     if os.environ.get("SECRET_KEY")
#     else get_random_bytes(32)
# )
app.secret_key = b"ABCdef123#@!XYZabc456$%^7890QWER"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
Base = declarative_base()


class Course(Base):
    __tablename__ = "courses"
    code = Column(String, primary_key=True, unique=True, index=True)
    name = Column(String)
    sylabus = Column(Text)
    password = Column(String)
    private_note = Column(Text)


db = SQLAlchemy(model_class=Base)
db.init_app(app)


def get_course_by_code(course_code: str):
    return db.session.query(Course).filter(Course.code == course_code).first()


def create_course(code: str, name: str, sylabus: str, private_note: str):
    password = os.urandom(8).hex()
    hashed_password = ph.hash(password.strip())
    db_course = Course(
        code=code,
        name=name.strip(),
        sylabus=sylabus.strip(),
        private_note=private_note.strip(),
        password=hashed_password,
    )
    db.session.add(db_course)
    db.session.commit()
    db.session.refresh(db_course)
    return db_course, password


def get_courses():
    return db.session.query(Course).all()


with app.app_context():
    db.create_all()
    if not get_courses():
        _, _ = create_course(
            "NMAI057",
            "Linear Algebra 1",
            "Basics of linear algebra (vector spaces and linear maps, solutions of linear equations, matrices).",
            "Everything is just linear transformation.",
        )
        _, _ = create_course(
            "NTIN060",
            "Algorithms and Data Structures 1",
            "Introductory lecture on the basic types of algorithms and data structures necessary for their implementation.",
            "The universe runs in O(1).",
        )
        _, _ = create_course(
            "NTIN061",
            "Algorithms and Data Structures 2",
            "Lecture about various types of algorithms and their time complexity (follows NTIN060 Algorithms and data structures 1).",
            "P != NP",
        )
        _, _ = create_course(
            "NAIL025",
            "Evolutionary Algorithms 1",
            "Models of evolution, genetic algorithms, representation and operators of selection, mutation and crossover.",
            "Strongest survive.",
        )
        _, _ = create_course(
            "NSWI205",
            "Pitfalls of computer security",
            "An introductory course on computer security. It presents basic types of attacks on security of computer systems and applications, along with counter-measures against them.",
            os.environ.get("FLAG", "pitfalls{fake_flag}"),
        )


def encrypt_cookie(course_code: str) -> str:
    cookie_obj = {"courseid": course_code.strip()}
    payload = json.dumps(cookie_obj)
    iv = get_random_bytes(AES.block_size)
    cipher = AES.new(app.secret_key, AES.MODE_CBC, iv)
    padded_data = pad(payload.encode(), AES.block_size)
    encrypted_data = cipher.encrypt(padded_data)
    mac = hmac.new(app.secret_key, encrypted_data, hashlib.sha256).hexdigest()
    return iv.hex() + encrypted_data.hex() + mac


def decrypt_cookie(cookie: str) -> str | None:
    try:
        iv = bytes.fromhex(cookie[:32])
        encrypted_data = bytes.fromhex(cookie[32:-64])
        mac = cookie[-64:]
        expected_mac = hmac.new(
            app.secret_key, encrypted_data, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(mac, expected_mac):
            return None
        cipher = AES.new(app.secret_key, AES.MODE_CBC, iv)
        decrypted_data = unpad(cipher.decrypt(encrypted_data), AES.block_size)
        cookie_obj = json.loads(decrypted_data.decode().strip())
        if not "courseid" in cookie_obj:
            return None
        return cookie_obj["courseid"]
    except (ValueError, IndexError, json.JSONDecodeError):
        return None


@app.route("/")
def index():
    courses = get_courses()
    return render_template("index.html", courses=courses)


@app.route("/course/<string:course_code>")
def course(course_code: str):
    course = get_course_by_code(course_code)
    if not course:
        return "Course not found", 404

    cookie = request.cookies.get("session")
    if cookie:
        decrypted_course_code = decrypt_cookie(cookie)
        if decrypted_course_code == course_code:
            return render_template(
                "course.html", course=course, private_note=course.private_note
            )

    return render_template("course.html", course=course)


@app.route("/create", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        code = request.form["code"].strip()
        name = request.form["name"].strip()
        sylabus = request.form["sylabus"].strip()
        private_note = request.form["private_note"].strip()
        try:
            _, password = create_course(code, name, sylabus, private_note)
            flash(
                f"Course created successfully! Your password is: {password}", "success"
            )
            return redirect(url_for("index"))
        except Exception as e:
            flash(f"An error occurred: {str(e)}", "danger")
            return redirect(url_for("index"))
    return render_template("create.html")


@app.route("/login/<string:course_code>", methods=["GET", "POST"])
def login(course_code: str):
    course = get_course_by_code(course_code)
    if not course:
        return "Course not found", 404

    if request.method == "POST":
        password = request.form["password"].strip()
        try:
            _ = ph.verify(str(course.password), password)
        except Exception:
            flash("Invalid password", "danger")
            return render_template("login.html", course=course)

        resp = redirect(url_for("course", course_code=course_code))
        resp.set_cookie("session", encrypt_cookie(course_code))
        return resp
    
    return render_template("login.html", course=course)


@app.route("/health")
def health():
    return "OK"


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8080)
