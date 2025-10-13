import os
import uuid
import time
import shutil
from flask import Flask, render_template, request, redirect, url_for, session
from flask.templating import render_template_string
from werkzeug.utils import secure_filename
import requests
import hashlib
import threading

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['SESSION_FOLDER'] = 'sessions'
app.config['SESSION_TIMEOUT'] = 86400  # 24 hours in seconds

# Ensure sessions directory exists
os.makedirs(app.config['SESSION_FOLDER'], exist_ok=True)

def get_session_id():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        session['created_at'] = time.time()
    return session['session_id']

def get_session_folder():
    session_id = get_session_id()
    session_folder = os.path.join(app.config['SESSION_FOLDER'], session_id)

    # Create session folder if it doesn't exist
    if not os.path.exists(session_folder):
        os.makedirs(session_folder, exist_ok=True)

        default_note = os.path.join('notes', 'My_Family_Tea_Recipe.txt')
        if os.path.exists(default_note):
            shutil.copy2(default_note, session_folder)

    return session_folder

def cleanup_old_sessions():
    try:
        current_time = time.time()
        for session_dir in os.listdir(app.config['SESSION_FOLDER']):
            session_path = os.path.join(app.config['SESSION_FOLDER'], session_dir)
            if os.path.isdir(session_path):
                # Check if session is older than timeout
                creation_time = os.path.getctime(session_path)
                if current_time - creation_time > app.config['SESSION_TIMEOUT']:
                    shutil.rmtree(session_path)
                    print(f"Cleaned up old session: {session_dir}")
    except Exception as e:
        print(f"Error during cleanup: {e}")

"""Run cleanup every hour"""
def periodic_cleanup():
    while True:
        time.sleep(3600)  # Sleep for 1 hour
        cleanup_old_sessions()

# Start cleanup thread (can be disabled via environment variable)
if not os.environ.get('DISABLE_AUTO_CLEANUP', False):
    cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
    cleanup_thread.start()

def parse_header(content):
    header = content.split('==========')[1].strip().split("\n")
    title = header[0].split(':')[1].strip()
    author = header[1].split(':')[1].strip()
    return title, author

def get_notes():
    notes_folder = get_session_folder()
    notes = []
    for filename in os.listdir(notes_folder):
        if filename.endswith(".txt"):
            with open(os.path.join(notes_folder, filename), 'r') as f:
                title, author = parse_header(f.read())
                notes.append({'filename': filename, 'title': title, 'author': author})
    return notes

def get_note(filename):
    notes_folder = get_session_folder()
    #return os.path.join(notes_folder, filename)
    try:
        with open(os.path.join(notes_folder, filename), 'r') as f:
            return f.read()
    except Exception:
        return None

@app.route('/')
def index():
    notes = get_notes()
    return render_template('index.html', notes=notes)

@app.route('/note/<path:filename>')
def note(filename):
    note_content = get_note(filename)
    if note_content:
        return render_template('note.html', note=note_content)
    else:
        return "Note not found", 404

@app.route('/create', methods=['GET', 'POST'])
def create():
    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        content = request.form['content']

        # Create a secure filename
        filename = secure_filename(title) + ".txt"
        notes_folder = get_session_folder()

        with open(os.path.join(notes_folder, filename), 'w') as f:
            f.write(f"""==========
Title: {title}
Author: {author}
==========
{content}
""")

        return redirect(url_for('index'))
    return render_template('create.html')

@app.route('/check_broken_integrity')
def check_broken_integrity():
    get_session_id()
    session_data = {app.config['SESSION_COOKIE_NAME']: request.cookies.get(app.config['SESSION_COOKIE_NAME'])}

    res = requests.get("http://127.0.0.1:8080/note/My_Family_Tea_Recipe.txt",
                      cookies=session_data)

    if res.status_code != 200:
        return render_template_string("Page not available :(")

    if "e17db96b0c37d98550eaef20f7370363636f20ad7944d92235ca9e0cd1221629" != hashlib.sha256(res.text.encode()).hexdigest():
        return render_template_string(
                    "Integrity compromised! Here is your integrity flag: {{flag}}",
                    flag=os.environ.get("FLAG_I", "pitfalls{fake_flag}"),
                )
    return render_template_string("Integrity intact!")

@app.route('/check_broken_availability')
def check_broken_availability():
    get_session_id()
    session_data = {app.config['SESSION_COOKIE_NAME']: request.cookies.get(app.config['SESSION_COOKIE_NAME'])}
    res = requests.get("http://127.0.0.1:8080/",
                      cookies=session_data)
    if res.status_code != 200:
        return render_template_string(
                    "Availability compromised! Here is your availability flag: {{flag}}",
                    flag=os.environ.get("FLAG_A", "pitfalls{fake_flag}"),
                )
    return render_template_string("Availability intact!")

@app.route('/reset')
def new_session():
    session.clear()
    return redirect(url_for('index'))

@app.route('/health')
def health():
    return "OK"

if __name__ == '__main__':
    with open("/confidential.txt", "r+") as confidential_file:
        confidential_content = confidential_file.read()
        confidential_content = confidential_content.replace("pitfalls{fake_flag}", os.environ.get("FLAG_C", "pitfalls{fake_flag}"))
        confidential_file.seek(0)
        confidential_file.write(confidential_content)
        confidential_file.truncate()
    app.run(debug=False, host='0.0.0.0', port=8080)
