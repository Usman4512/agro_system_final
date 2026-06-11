import os
import MySQLdb
from MySQLdb.cursors import DictCursor
from flask import g, current_app
import click
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

# =========================
# DATABASE CORE
# =========================

class Database:
    def __init__(self, app=None):
        if app:
            self.init_app(app)

    def init_app(self, app):
        app.teardown_appcontext(self.close_db)

    def get_connection(self):
        if 'db' not in g:
            g.db = MySQLdb.connect(
                host=os.getenv("MYSQL_HOST"),
                user=os.getenv("MYSQL_USER"),
                password=os.getenv("MYSQL_PASSWORD"),
                database=os.getenv("MYSQL_DB"),
                port=int(os.getenv("MYSQL_PORT", 3306)),
                cursorclass=DictCursor,
                charset="utf8mb4"
            )
        return g.db

    def close_db(self, e=None):
        db = g.pop('db', None)
        if db:
            db.close()


db = Database()

# =========================
# INIT APP
# =========================

def init_app(app):
    db.init_app(app)
    app.cli.add_command(init_db_command)

def get_db():
    return db.get_connection()

# =========================
# INIT DATABASE TABLES
# =========================

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            full_name VARCHAR(100),
            username VARCHAR(50) UNIQUE,
            email VARCHAR(100) UNIQUE,
            password_hash VARCHAR(255),
            role VARCHAR(20) DEFAULT 'farmer',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    cur.close()

# =========================
# CLI COMMAND
# =========================

@click.command('init-db')
@with_appcontext
def init_db_command():
    init_db()
    click.echo("Database initialized successfully!")

# =========================
# AUTO INIT CHECK
# =========================

def ensure_db_initialized():
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SHOW TABLES LIKE 'users'")
        if not cur.fetchone():
            init_db()
    finally:
        cur.close()

# =========================
# REQUIRED USER FUNCTIONS
# =========================

def get_user_by_email(email):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    cur.close()
    return user


def get_user_by_username(username):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=%s", (username,))
    user = cur.fetchone()
    cur.close()
    return user


def get_user_by_id(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    user = cur.fetchone()
    cur.close()
    return user

# =========================
# OPTIONAL HELPERS
# =========================

def create_user(full_name, username, email, password):
    conn = get_db()
    cur = conn.cursor()

    password_hash = generate_password_hash(password)

    cur.execute("""
        INSERT INTO users (full_name, username, email, password_hash)
        VALUES (%s, %s, %s, %s)
    """, (full_name, username, email, password_hash))

    conn.commit()
    cur.close()