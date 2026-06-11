import MySQLdb
from MySQLdb.cursors import DictCursor
from flask import current_app, g
import click
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

DEFAULT_ADMIN_PASSWORD = 'admin123'

class Database:
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        app.teardown_appcontext(self.close_db)

    def get_connection(self):
        if 'db' not in g:
            host = current_app.config['MYSQL_HOST']
            # Cloud SQL Unix socket support
            if host.startswith('/'):
                g.db = MySQLdb.connect(
                    unix_socket=host,
                    user=current_app.config['MYSQL_USER'],
                    password=current_app.config['MYSQL_PASSWORD'],
                    database=current_app.config['MYSQL_DB'],
                    cursorclass=DictCursor,
                    charset='utf8mb4'
                )
            else:
                g.db = MySQLdb.connect(
                    host=host,
                    user=current_app.config['MYSQL_USER'],
                    password=current_app.config['MYSQL_PASSWORD'],
                    database=current_app.config['MYSQL_DB'],
                    port=current_app.config['MYSQL_PORT'],
                    cursorclass=DictCursor,
                    charset='utf8mb4'
                )
        return g.db

    def close_db(self, e=None):
        db = g.pop('db', None)
        if db is not None:
            db.close()

db = Database()

def init_app(app):
    db.init_app(app)
    app.cli.add_command(init_db_command)

def get_db():
    return db.get_connection()

def init_db():
    connection = db.get_connection()
    cursor = connection.cursor()

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            full_name VARCHAR(100) NOT NULL,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            phone VARCHAR(20),
            address TEXT,
            city VARCHAR(50),
            province VARCHAR(50),
            farm_size DECIMAL(10,2) DEFAULT 0,
            farm_type VARCHAR(50),
            role ENUM('farmer','admin','dealer') DEFAULT 'farmer',
            is_verified TINYINT(1) DEFAULT 0,
            verification_token VARCHAR(255),
            token_expires TIMESTAMP NULL,
            profile_image VARCHAR(255),
            status ENUM('active','inactive','suspended') DEFAULT 'active',
            subscription_status ENUM('trial','active','expired') DEFAULT 'trial',
            subscription_plan VARCHAR(20) DEFAULT 'basic',
            subscription_expiry DATE NULL,
            trial_started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    ''')

    # Crops table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crops (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            crop_name VARCHAR(100) NOT NULL,
            crop_type ENUM('food_crop','cash_crop','vegetable','fruit','livestock','other') DEFAULT 'food_crop',
            variety VARCHAR(100),
            season ENUM('rabi','kharif','zaid','year_round') NOT NULL,
            area_acres DECIMAL(10,2) NOT NULL,
            planting_date DATE,
            expected_harvest_date DATE,
            actual_harvest_date DATE,
            status ENUM('planned','planted','growing','ready_to_harvest','harvested','failed') DEFAULT 'planned',
            yield_expected_kg DECIMAL(10,2),
            yield_actual_kg DECIMAL(10,2),
            expenses_pkr DECIMAL(12,2) DEFAULT 0,
            revenue_pkr DECIMAL(12,2) DEFAULT 0,
            notes TEXT,
            image_path VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # Crop Rates table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crop_rates (
            id INT AUTO_INCREMENT PRIMARY KEY,
            crop_name VARCHAR(100) NOT NULL,
            variety VARCHAR(100),
            market_name VARCHAR(100) NOT NULL,
            city VARCHAR(50),
            rate_per_kg_pkr DECIMAL(10,2) NOT NULL,
            rate_per_40kg_pkr DECIMAL(10,2),
            quality_grade ENUM('A','B','C','premium','standard','low') DEFAULT 'standard',
            date_recorded DATE NOT NULL,
            is_active TINYINT(1) DEFAULT 1,
            source VARCHAR(255),
            created_by INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')

    # Inventory table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            item_name VARCHAR(100) NOT NULL,
            item_category ENUM('seed','fertilizer','pesticide','tool','equipment','fuel','other') NOT NULL,
            quantity DECIMAL(10,2) NOT NULL,
            unit VARCHAR(20) NOT NULL,
            cost_per_unit_pkr DECIMAL(10,2),
            total_cost_pkr DECIMAL(12,2),
            supplier VARCHAR(100),
            purchase_date DATE,
            expiry_date DATE,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # Expenses table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            expense_category ENUM('seeds','fertilizer','pesticide','labor','irrigation','fuel','equipment','transport','storage','other') NOT NULL,
            description TEXT NOT NULL,
            amount_pkr DECIMAL(12,2) NOT NULL,
            expense_date DATE NOT NULL,
            payment_method ENUM('cash','bank_transfer','credit','other') DEFAULT 'cash',
            receipt_number VARCHAR(50),
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # Weather Logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weather_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            city VARCHAR(50) NOT NULL,
            temperature_c DECIMAL(5,2),
            humidity_percent DECIMAL(5,2),
            rainfall_mm DECIMAL(8,2),
            wind_speed_kmh DECIMAL(5,2),
            condition_text VARCHAR(100),
            recorded_date DATE NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')

    # Activity Log table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            activity_type VARCHAR(50) NOT NULL,
            description TEXT NOT NULL,
            related_table VARCHAR(50),
            related_id INT,
            ip_address VARCHAR(45),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')

    # Notifications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            title VARCHAR(200) NOT NULL,
            message TEXT NOT NULL,
            notification_type ENUM('info','warning','success','error') DEFAULT 'info',
            is_read TINYINT(1) DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # Payment Requests table (NEW)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_requests (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            plan VARCHAR(20) NOT NULL,
            amount_pkr DECIMAL(10,2) NOT NULL,
            jazzcash_number VARCHAR(20),
            transaction_id VARCHAR(100),
            screenshot_path VARCHAR(255),
            status ENUM('pending','approved','rejected') DEFAULT 'pending',
            admin_note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # Insert default admin
    default_admin_hash = generate_password_hash(DEFAULT_ADMIN_PASSWORD, method='scrypt')
    cursor.execute('''
        INSERT IGNORE INTO users (id, full_name, username, email, password_hash, role,
                                  is_verified, status, subscription_status)
        VALUES (1, 'System Admin', 'admin', 'admin@agrosystem.com', %s, 'admin', 1, 'active', 'active')
    ''', (default_admin_hash,))

    # Insert sample crop rates
    sample_rates = [
        ('Wheat',     'Desi',      'Lahore Grain Market',          'Lahore',      65.00,  2600.00, 'A',        '2024-05-14'),
        ('Wheat',     'High Yield','Karachi Commodity Exchange',   'Karachi',     68.00,  2720.00, 'premium',  '2024-05-14'),
        ('Rice',      'Basmati',   'Gujranwala Mandi',             'Gujranwala', 280.00, 11200.00, 'premium',  '2024-05-14'),
        ('Rice',      'IRRI-6',    'Larkana Market',               'Larkana',     95.00,  3800.00, 'B',        '2024-05-14'),
        ('Cotton',    'MNH-786',   'Multan Cotton Market',         'Multan',     185.00,  7400.00, 'A',        '2024-05-14'),
        ('Sugarcane', 'CP-77',     'Faisalabad Mandi',             'Faisalabad',  12.00,   480.00, 'standard', '2024-05-14'),
        ('Maize',     'Hybrid',    'Sahiwal Grain Market',         'Sahiwal',     58.00,  2320.00, 'A',        '2024-05-14'),
        ('Potato',    'Cardinal',  'Okara Vegetable Market',       'Okara',       42.00,  1680.00, 'B',        '2024-05-14'),
        ('Tomato',    'Roma',      'Vehari Mandi',                 'Vehari',      38.00,  1520.00, 'standard', '2024-05-14'),
        ('Onion',     'Red',       'Peshawar Sabzi Mandi',         'Peshawar',    55.00,  2200.00, 'A',        '2024-05-14'),
        ('Chickpea',  'Desi',      'Quetta Grain Market',          'Quetta',     180.00,  7200.00, 'premium',  '2024-05-14'),
        ('Mango',     'Chaunsa',   'Multan Fruit Market',          'Multan',     150.00,  6000.00, 'premium',  '2024-05-14'),
        ('Apple',     'Kashmiri',  'Murree Fruit Market',          'Murree',     120.00,  4800.00, 'A',        '2024-05-14'),
        ('Sunflower', 'Hysun-33',  'Hyderabad Oilseed Market',     'Hyderabad',  110.00,  4400.00, 'standard', '2024-05-14'),
    ]
    for rate in sample_rates:
        cursor.execute('''
            INSERT IGNORE INTO crop_rates
            (crop_name, variety, market_name, city, rate_per_kg_pkr, rate_per_40kg_pkr, quality_grade, date_recorded)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', rate)

    connection.commit()
    cursor.close()

@click.command('init-db')
@with_appcontext
def init_db_command():
    init_db()
    click.echo('Database initialized successfully!')

def ensure_db_initialized():
    db_conn = get_db()
    cursor = db_conn.cursor()
    try:
        cursor.execute("SHOW TABLES LIKE 'users'")
        if cursor.fetchone() is None:
            init_db()
    finally:
        cursor.close()

# ── Helper functions ──────────────────────────────────────────

def get_user_by_email(email):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cur.fetchone(); cur.close(); return user

def get_user_by_username(username):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cur.fetchone(); cur.close(); return user

def get_user_by_id(user_id):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone(); cur.close(); return user

def get_user_by_token(token):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE verification_token = %s", (token,))
    user = cur.fetchone(); cur.close(); return user

def verify_user_email(token):
    conn = get_db(); cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET is_verified = 1, verification_token = NULL, token_expires = NULL
        WHERE verification_token = %s AND token_expires > NOW()
    """, (token,))
    conn.commit()
    rows = cur.rowcount; cur.close(); return rows > 0

def log_activity(user_id, activity_type, description,
                 related_table=None, related_id=None, ip_address=None):
    conn = get_db(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO activity_log
        (user_id, activity_type, description, related_table, related_id, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (user_id, activity_type, description, related_table, related_id, ip_address))
    conn.commit(); cur.close()

def create_notification(user_id, title, message, notification_type='info'):
    conn = get_db(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO notifications (user_id, title, message, notification_type)
        VALUES (%s, %s, %s, %s)
    """, (user_id, title, message, notification_type))
    conn.commit(); cur.close()

# ── Subscription helpers ──────────────────────────────────────

TRIAL_DAYS = 30

def check_subscription(user):
    """
    Returns (is_allowed, status_string).
    Admins always allowed. Trial users allowed within 30 days.
    Active users allowed if expiry is in the future.
    """
    if user['role'] == 'admin':
        return True, 'admin'

    sub = user.get('subscription_status', 'trial')

    if sub == 'active':
        expiry = user.get('subscription_expiry')
        if expiry and expiry >= datetime.now().date():
            return True, 'active'
        # Expiry passed — mark expired
        _mark_expired(user['id'])
        return False, 'expired'

    if sub == 'trial':
        started = user.get('trial_started_at') or user.get('created_at')
        if started:
            if isinstance(started, str):
                started = datetime.strptime(started[:19], '%Y-%m-%d %H:%M:%S')
            days_left = TRIAL_DAYS - (datetime.now() - started).days
            if days_left > 0:
                return True, f'trial:{days_left}'
        _mark_expired(user['id'])
        return False, 'expired'

    return False, 'expired'

def _mark_expired(user_id):
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE users SET subscription_status='expired' WHERE id=%s", (user_id,))
    conn.commit(); cur.close()

def activate_subscription(user_id, plan, months=1):
    conn = get_db(); cur = conn.cursor()
    expiry = (datetime.now() + timedelta(days=30 * months)).date()
    cur.execute("""
        UPDATE users
        SET subscription_status='active', subscription_plan=%s, subscription_expiry=%s
        WHERE id=%s
    """, (plan, expiry, user_id))
    conn.commit(); cur.close()
