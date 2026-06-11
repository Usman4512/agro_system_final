import os
import MySQLdb
from MySQLdb.cursors import DictCursor
from flask import current_app, g
import click
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

# =========================
# DATABASE CONNECTION CLASS
# =========================

class Database:
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        app.teardown_appcontext(self.close_db)

    def get_connection(self):
        if 'db' not in g:
            g.db = MySQLdb.connect(
                host=os.environ.get("MYSQL_HOST"),
                user=os.environ.get("MYSQL_USER"),
                password=os.environ.get("MYSQL_PASSWORD"),
                database=os.environ.get("MYSQL_DB"),
                port=int(os.environ.get("MYSQL_PORT", 3306)),
                cursorclass=DictCursor,
                charset='utf8mb4'
            )
        return g.db

    def close_db(self, e=None):
        db = g.pop('db', None)
        if db is not None:
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
# DATABASE INITIALIZATION
# =========================

def init_db():
    connection = db.get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            full_name VARCHAR(100),
            email VARCHAR(100),
            password_hash VARCHAR(255),
            role VARCHAR(20) DEFAULT 'farmer',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.commit()
    cursor.close()

# =========================
# CLI COMMAND
# =========================

@click.command('init-db')
@with_appcontext
def init_db_command():
    init_db()
    click.echo('Database initialized successfully!')

# =========================
# AUTO CHECK DB
# =========================

def ensure_db_initialized():
    db_conn = get_db()
    cursor = db_conn.cursor()
    try:
        cursor.execute("SHOW TABLES LIKE 'users'")
        if cursor.fetchone() is None:
            init_db()
    finally:
        cursor.close()

# =========================
# HELPERS
# =========================

def get_user_by_email(email):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=%s", (email,))
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

def create_user(full_name, email, password):
    conn = get_db()
    cur = conn.cursor()
    password_hash = generate_password_hash(password)

    cur.execute("""
        INSERT INTO users (full_name, email, password_hash)
        VALUES (%s, %s, %s)
    """, (full_name, email, password_hash))

    conn.commit()
    cur.close()