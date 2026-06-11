import MySQLdb
from MySQLdb.cursors import DictCursor
from flask import current_app, g
import click
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

TRIAL_DAYS = 30
DEFAULT_ADMIN_PASSWORD = "Usman$5000"


# ================= DATABASE CLASS =================
class Database:
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)

    def init_app(self, app):
        app.teardown_appcontext(self.close_db)

    def get_connection(self):
        if "db" not in g:
            host = current_app.config["MYSQL_HOST"]

            # Cloud / Unix socket
            if host and host.startswith("/"):
                g.db = MySQLdb.connect(
                    unix_socket=host,
                    user=current_app.config["MYSQL_USER"],
                    password=current_app.config["MYSQL_PASSWORD"],
                    database=current_app.config["MYSQL_DB"],
                    cursorclass=DictCursor,
                    charset="utf8mb4"
                )
            else:
                g.db = MySQLdb.connect(
                    host=host,
                    user=current_app.config["MYSQL_USER"],
                    password=current_app.config["MYSQL_PASSWORD"],
                    database=current_app.config["MYSQL_DB"],
                    port=int(current_app.get("MYSQL_PORT", 3306)) if hasattr(current_app, "get") else 3306,
                    cursorclass=DictCursor,
                    charset="utf8mb4"
                )

        return g.db

    def close_db(self, e=None):
        db = g.pop("db", None)
        if db:
            db.close()


db = Database()


def get_db():
    return db.get_connection()


# ================= USER FUNCTIONS (FIXED) =================
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


def get_user_by_token(token):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE verification_token=%s", (token,))
    user = cur.fetchone()
    cur.close()
    return user


def verify_user_email(token):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET is_verified=1, verification_token=NULL, token_expires=NULL
        WHERE verification_token=%s AND token_expires > NOW()
    """, (token,))
    conn.commit()
    rows = cur.rowcount
    cur.close()
    return rows > 0


# ================= LOGGING =================
def log_activity(user_id, activity_type, description,
                 related_table=None, related_id=None, ip_address=None):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO activity_log
        (user_id, activity_type, description, related_table, related_id, ip_address)
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (user_id, activity_type, description, related_table, related_id, ip_address))
    conn.commit()
    cur.close()


def create_notification(user_id, title, message, notification_type="info"):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO notifications (user_id, title, message, notification_type)
        VALUES (%s,%s,%s,%s)
    """, (user_id, title, message, notification_type))
    conn.commit()
    cur.close()


# ================= SUBSCRIPTION =================
def check_subscription(user):
    if user["role"] == "admin":
        return True, "admin"

    status = user.get("subscription_status", "trial")

    if status == "active":
        if user.get("subscription_expiry") and user["subscription_expiry"] >= datetime.now().date():
            return True, "active"
        return False, "expired"

    if status == "trial":
        created = user.get("trial_started_at") or user.get("created_at")
        if isinstance(created, str):
            created = datetime.strptime(created[:19], "%Y-%m-%d %H:%M:%S")

        if (datetime.now() - created).days <= TRIAL_DAYS:
            return True, "trial"
        return False, "expired"

    return False, "expired"


def activate_subscription(user_id, plan, months=1):
    conn = get_db()
    cur = conn.cursor()
    expiry = (datetime.now() + timedelta(days=30 * months)).date()

    cur.execute("""
        UPDATE users
        SET subscription_status='active',
            subscription_plan=%s,
            subscription_expiry=%s
        WHERE id=%s
    """, (plan, expiry, user_id))

    conn.commit()
    cur.close()