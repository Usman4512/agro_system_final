from functools import wraps
from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from models.db import get_db, get_user_by_id, log_activity, create_notification, check_subscription
from datetime import datetime

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wrapper

def subscription_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login.', 'warning')
            return redirect(url_for('auth.login'))
        user = get_user_by_id(session['user_id'])
        allowed, status = check_subscription(user)
        if not allowed:
            flash('Your subscription has expired. Please subscribe to continue.', 'warning')
            return redirect(url_for('payment.plans'))
        # Pass trial days remaining to templates via session
        if status.startswith('trial:'):
            session['trial_days_left'] = int(status.split(':')[1])
        else:
            session.pop('trial_days_left', None)
        return f(*args, **kwargs)
    return wrapper

@dashboard_bp.route('/')
@login_required
@subscription_required
def index():
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) as total FROM crops WHERE user_id = %s", (user_id,))
    total_crops = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as total FROM inventory WHERE user_id = %s", (user_id,))
    inventory_count = cursor.fetchone()['total']

    cursor.execute("""
        SELECT COUNT(*) as total FROM crops WHERE user_id = %s
        AND expected_harvest_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 14 DAY)
    """, (user_id,))
    upcoming_harvests = cursor.fetchone()['total']

    cursor.execute("SELECT SUM(expenses_pkr) as total FROM crops WHERE user_id = %s", (user_id,))
    total_expenses = cursor.fetchone()['total'] or 0

    cursor.execute("""
        SELECT SUM(revenue_pkr) as total FROM crops WHERE user_id = %s AND status = 'harvested'
    """, (user_id,))
    total_revenue = cursor.fetchone()['total'] or 0

    cursor.execute("""
        SELECT COUNT(*) as total FROM crops WHERE user_id = %s AND status IN ('planted','growing')
    """, (user_id,))
    active_crops = cursor.fetchone()['total']

    cursor.execute("SELECT * FROM crops WHERE user_id = %s ORDER BY created_at DESC LIMIT 5", (user_id,))
    recent_crops = cursor.fetchall()

    cursor.execute("SELECT * FROM expenses WHERE user_id = %s ORDER BY created_at DESC LIMIT 5", (user_id,))
    recent_expenses = cursor.fetchall()

    cursor.execute("SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC LIMIT 5", (user_id,))
    notifications = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = 0", (user_id,))
    unread_count = cursor.fetchone()['count']

    cursor.execute("""
        SELECT DATE_FORMAT(created_at, '%%b') as month,
               COUNT(*) as crop_count,
               SUM(expenses_pkr) as expenses,
               MIN(created_at) as month_start
        FROM crops
        WHERE user_id = %s AND created_at >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
        GROUP BY DATE_FORMAT(created_at, '%%b')
        ORDER BY month_start
    """, (user_id,))
    monthly_data = cursor.fetchall()

    cursor.execute("""
        SELECT crop_name, SUM(revenue_pkr) as revenue
        FROM crops WHERE user_id = %s AND status = 'harvested'
        GROUP BY crop_name ORDER BY revenue DESC LIMIT 5
    """, (user_id,))
    top_crops = cursor.fetchall()

    cursor.close()

    return render_template('dashboard.html',
                           user=user,
                           total_crops=total_crops,
                           inventory_count=inventory_count,
                           upcoming_harvests=upcoming_harvests,
                           total_expenses=total_expenses,
                           total_revenue=total_revenue,
                           active_crops=active_crops,
                           profit=total_revenue - total_expenses,
                           recent_crops=recent_crops,
                           recent_expenses=recent_expenses,
                           notifications=notifications,
                           unread_count=unread_count,
                           monthly_data=monthly_data,
                           top_crops=top_crops)

@dashboard_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@subscription_required
def profile():
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()

    if request.method == 'POST':
        full_name  = request.form.get('full_name', '').strip()
        phone      = request.form.get('phone', '').strip()
        address    = request.form.get('address', '').strip()
        city       = request.form.get('city', '').strip()
        province   = request.form.get('province', '')
        farm_size  = request.form.get('farm_size', 0)
        farm_type  = request.form.get('farm_type', '')

        cursor.execute("""
            UPDATE users SET full_name=%s, phone=%s, address=%s, city=%s,
                             province=%s, farm_size=%s, farm_type=%s
            WHERE id=%s
        """, (full_name, phone, address, city, province, farm_size, farm_type, user_id))
        db.commit()
        session['full_name'] = full_name
        log_activity(user_id, 'profile_update', 'Profile updated')
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('dashboard.profile'))

    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    return render_template('profile.html', user=user)

@dashboard_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    from werkzeug.security import generate_password_hash, check_password_hash
    user_id          = session['user_id']
    current_password = request.form.get('current_password', '')
    new_password     = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    if not current_password or not new_password or not confirm_password:
        flash('All fields are required.', 'danger')
        return redirect(url_for('dashboard.profile'))
    if new_password != confirm_password:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('dashboard.profile'))
    if len(new_password) < 6:
        flash('Password must be at least 6 characters.', 'danger')
        return redirect(url_for('dashboard.profile'))

    db = get_db(); cur = db.cursor()
    cur.execute("SELECT password_hash FROM users WHERE id=%s", (user_id,))
    user = cur.fetchone()

    if not check_password_hash(user['password_hash'], current_password):
        flash('Current password is incorrect.', 'danger')
        cur.close()
        return redirect(url_for('dashboard.profile'))

    cur.execute("UPDATE users SET password_hash=%s WHERE id=%s",
                (generate_password_hash(new_password, method='scrypt'), user_id))
    db.commit(); cur.close()
    log_activity(user_id, 'password_change', 'Password changed')
    flash('Password changed successfully!', 'success')
    return redirect(url_for('dashboard.profile'))

@dashboard_bp.route('/notifications')
@login_required
def notifications():
    user_id = session['user_id']
    db = get_db(); cur = db.cursor()
    page     = request.args.get('page', 1, type=int)
    per_page = 20
    offset   = (page - 1) * per_page

    cur.execute("""
        SELECT * FROM notifications WHERE user_id=%s
        ORDER BY created_at DESC LIMIT %s OFFSET %s
    """, (user_id, per_page, offset))
    notifications = cur.fetchall()

    cur.execute("UPDATE notifications SET is_read=1 WHERE user_id=%s", (user_id,))
    db.commit(); cur.close()
    return render_template('notifications.html', notifications=notifications, page=page)
