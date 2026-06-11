from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models.db import get_db, log_activity

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        if session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return wrapper

@admin_bp.route('/')
@admin_required
def index():
    db = get_db()
    cursor = db.cursor()
    
    # Summary stats
    cursor.execute("SELECT COUNT(*) as total FROM users WHERE role = 'farmer'")
    total_farmers = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM users WHERE role = 'farmer' AND created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)")
    new_farmers = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM crops")
    total_crops = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM crop_rates WHERE is_active = 1")
    total_rates = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM users WHERE is_verified = 0")
    pending_verifications = cursor.fetchone()['total']
    
    # Recent farmers
    cursor.execute("""
        SELECT * FROM users WHERE role = 'farmer' 
        ORDER BY created_at DESC LIMIT 10
    """)
    recent_farmers = cursor.fetchall()
    
    # Recent activities
    cursor.execute("""
        SELECT al.*, u.username, u.full_name 
        FROM activity_log al
        LEFT JOIN users u ON al.user_id = u.id
        ORDER BY al.created_at DESC LIMIT 20
    """)
    recent_activities = cursor.fetchall()
    
    # Crop distribution by type
    cursor.execute("""
        SELECT crop_type, COUNT(*) as count FROM crops GROUP BY crop_type
    """)
    crop_distribution = cursor.fetchall()
    
    # Monthly registrations
    cursor.execute("""
        SELECT DATE_FORMAT(created_at, '%%b %%Y') as month, COUNT(*) as count
        FROM users WHERE role = 'farmer' AND created_at >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
        GROUP BY DATE_FORMAT(created_at, '%%b %%Y')
        ORDER BY MIN(created_at)
    """)
    monthly_registrations = cursor.fetchall()
    
    cursor.close()
    
    return render_template('admin/dashboard.html',
                         total_farmers=total_farmers,
                         new_farmers=new_farmers,
                         total_crops=total_crops,
                         total_rates=total_rates,
                         pending_verifications=pending_verifications,
                         recent_farmers=recent_farmers,
                         recent_activities=recent_activities,
                         crop_distribution=crop_distribution,
                         monthly_registrations=monthly_registrations)

@admin_bp.route('/farmers')
@admin_required
def farmers():
    db = get_db()
    cursor = db.cursor()
    
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    verification_filter = request.args.get('verification', '')
    
    query = "SELECT * FROM users WHERE role = 'farmer'"
    params = []
    
    if search:
        query += " AND (full_name LIKE %s OR email LIKE %s OR username LIKE %s OR city LIKE %s)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%'])
    if status_filter:
        query += " AND status = %s"
        params.append(status_filter)
    if verification_filter == 'verified':
        query += " AND is_verified = 1"
    elif verification_filter == 'unverified':
        query += " AND is_verified = 0"
    
    query += " ORDER BY created_at DESC"
    
    cursor.execute(query, params)
    farmers = cursor.fetchall()
    cursor.close()
    
    return render_template('admin/farmers.html', farmers=farmers, 
                         search=search, status_filter=status_filter, verification_filter=verification_filter)

@admin_bp.route('/farmers/<int:user_id>/verify-email', methods=['POST'])
@admin_required
def verify_farmer_email(user_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT is_verified FROM users WHERE id = %s AND role = 'farmer'", (user_id,))
    user = cursor.fetchone()
    if not user:
        flash('Farmer not found.', 'danger')
        cursor.close()
        return redirect(url_for('admin.farmers'))
    if user['is_verified']:
        flash('This account is already verified.', 'info')
        cursor.close()
        return redirect(url_for('admin.farmers'))

    cursor.execute("UPDATE users SET is_verified = 1, verification_token = NULL, token_expires = NULL WHERE id = %s", (user_id,))
    db.commit()
    cursor.close()

    log_activity(session['user_id'], 'admin_verify_email', f'Verified email for farmer {user_id}')
    flash('Farmer email verified successfully.', 'success')
    return redirect(url_for('admin.farmers', verification='unverified'))

@admin_bp.route('/farmers/<int:user_id>')
@admin_required
def farmer_detail(user_id):
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    farmer = cursor.fetchone()
    
    if not farmer:
        flash('Farmer not found.', 'danger')
        return redirect(url_for('admin.farmers'))
    
    # Get farmer's crops
    cursor.execute("SELECT * FROM crops WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
    crops = cursor.fetchall()
    
    # Get farmer's stats
    cursor.execute("SELECT COUNT(*) as total FROM crops WHERE user_id = %s", (user_id,))
    total_crops = cursor.fetchone()['total']
    
    cursor.execute("SELECT SUM(expenses_pkr) as total FROM crops WHERE user_id = %s", (user_id,))
    total_expenses = cursor.fetchone()['total'] or 0
    
    cursor.execute("SELECT SUM(revenue_pkr) as total FROM crops WHERE user_id = %s", (user_id,))
    total_revenue = cursor.fetchone()['total'] or 0
    
    cursor.close()
    
    return render_template('admin/farmer_detail.html',
                         farmer=farmer, crops=crops,
                         total_crops=total_crops,
                         total_expenses=total_expenses,
                         total_revenue=total_revenue)

@admin_bp.route('/farmers/<int:user_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_farmer_status(user_id):
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT status FROM users WHERE id = %s", (user_id,))
    result = cursor.fetchone()
    
    if not result:
        flash('User not found.', 'danger')
        return redirect(url_for('admin.farmers'))
    
    new_status = 'suspended' if result['status'] == 'active' else 'active'
    cursor.execute("UPDATE users SET status = %s WHERE id = %s", (new_status, user_id))
    db.commit()
    cursor.close()
    
    log_activity(session['user_id'], 'admin_action', f'Changed user {user_id} status to {new_status}')
    flash(f'User status changed to {new_status}.', 'success')
    return redirect(url_for('admin.farmers'))

@admin_bp.route('/rates')
@admin_required
def rates():
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT cr.*, u.username as added_by 
        FROM crop_rates cr
        LEFT JOIN users u ON cr.created_by = u.id
        ORDER BY cr.date_recorded DESC
    """)
    rates = cursor.fetchall()
    cursor.close()
    
    return render_template('admin/rates.html', rates=rates)

@admin_bp.route('/rates/add', methods=['POST'])
@admin_required
def add_rate():
    crop_name = request.form.get('crop_name', '').strip()
    variety = request.form.get('variety', '').strip()
    market_name = request.form.get('market_name', '').strip()
    city = request.form.get('city', '').strip()
    rate_per_kg = request.form.get('rate_per_kg', 0)
    rate_per_40kg = request.form.get('rate_per_40kg', 0)
    quality_grade = request.form.get('quality_grade', 'standard')
    date_recorded = request.form.get('date_recorded')
    source = request.form.get('source', '')
    
    if not crop_name or not market_name or not rate_per_kg:
        flash('Please fill in all required fields.', 'danger')
        return redirect(url_for('admin.rates'))
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO crop_rates (crop_name, variety, market_name, city, rate_per_kg_pkr, 
                              rate_per_40kg_pkr, quality_grade, date_recorded, source, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (crop_name, variety, market_name, city, rate_per_kg, rate_per_40kg, 
           quality_grade, date_recorded, source, session['user_id']))
    db.commit()
    cursor.close()
    
    log_activity(session['user_id'], 'rate_add', f'Added rate for {crop_name}')
    flash(f'Rate for {crop_name} added successfully.', 'success')
    return redirect(url_for('admin.rates'))

@admin_bp.route('/rates/<int:rate_id>/delete', methods=['POST'])
@admin_required
def delete_rate(rate_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE crop_rates SET is_active = 0 WHERE id = %s", (rate_id,))
    db.commit()
    cursor.close()
    
    log_activity(session['user_id'], 'rate_delete', f'Deactivated rate ID: {rate_id}')
    flash('Rate has been deactivated.', 'success')
    return redirect(url_for('admin.rates'))

@admin_bp.route('/activities')
@admin_required
def activities():
    db = get_db()
    cursor = db.cursor()
    
    page = request.args.get('page', 1, type=int)
    per_page = 50
    offset = (page - 1) * per_page
    
    cursor.execute("""
        SELECT al.*, u.username, u.full_name 
        FROM activity_log al
        LEFT JOIN users u ON al.user_id = u.id
        ORDER BY al.created_at DESC
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    activities = cursor.fetchall()
    
    cursor.close()
    
    return render_template('admin/activities.html', activities=activities, page=page)

@admin_bp.route('/reports')
@admin_required
def reports():
    db = get_db()
    cursor = db.cursor()
    
    # Summary reports
    cursor.execute("SELECT COUNT(*) as total FROM users WHERE role = 'farmer'")
    total_farmers = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM crops")
    total_crops = cursor.fetchone()['total']
    
    cursor.execute("SELECT SUM(expenses_pkr) as total FROM crops")
    total_expenses = cursor.fetchone()['total'] or 0
    
    cursor.execute("SELECT SUM(revenue_pkr) as total FROM crops WHERE status = 'harvested'")
    total_revenue = cursor.fetchone()['total'] or 0
    
    # Crops by province
    cursor.execute("""
        SELECT u.province, COUNT(c.id) as crop_count, SUM(c.area_acres) as total_acres
        FROM crops c
        JOIN users u ON c.user_id = u.id
        GROUP BY u.province
    """)
    province_stats = cursor.fetchall()
    
    # Top crops by area
    cursor.execute("""
        SELECT crop_name, SUM(area_acres) as total_acres, COUNT(*) as farmer_count
        FROM crops GROUP BY crop_name ORDER BY total_acres DESC LIMIT 10
    """)
    top_crops = cursor.fetchall()
    
    cursor.close()
    
    return render_template('admin/reports.html',
                         total_farmers=total_farmers,
                         total_expenses=total_expenses,
                         total_revenue=total_revenue,
                         province_stats=province_stats,
                         top_crops=top_crops)

@admin_bp.route('/payments')
@admin_required
def payments():
    from flask import redirect, url_for
    return redirect(url_for('payment.admin_requests'))
