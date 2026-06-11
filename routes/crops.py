from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models.db import get_db, log_activity, create_notification
from datetime import datetime

crops_bp = Blueprint('crops', __name__, url_prefix='/crops')

def login_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

@crops_bp.route('/')
@login_required
def index():
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()
    
    # Filter options
    status_filter = request.args.get('status', '')
    season_filter = request.args.get('season', '')
    search = request.args.get('search', '')
    
    query = "SELECT * FROM crops WHERE user_id = %s"
    params = [user_id]
    
    if status_filter:
        query += " AND status = %s"
        params.append(status_filter)
    if season_filter:
        query += " AND season = %s"
        params.append(season_filter)
    if search:
        query += " AND (crop_name LIKE %s OR variety LIKE %s)"
        params.extend([f'%{search}%', f'%{search}%'])
    
    query += " ORDER BY created_at DESC"
    
    cursor.execute(query, params)
    crops = cursor.fetchall()
    
    # Get summary stats
    cursor.execute("""
        SELECT status, COUNT(*) as count FROM crops WHERE user_id = %s GROUP BY status
    """, (user_id,))
    status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
    
    cursor.close()
    
    return render_template('crops/list.html', 
                         crops=crops, 
                         status_counts=status_counts,
                         filters={'status': status_filter, 'season': season_filter, 'search': search})

@crops_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    if request.method == 'POST':
        user_id = session['user_id']
        crop_name = request.form.get('crop_name', '').strip()
        crop_type = request.form.get('crop_type', '')
        variety = request.form.get('variety', '').strip()
        season = request.form.get('season', '')
        area_acres = request.form.get('area_acres', 0)
        planting_date = request.form.get('planting_date')
        expected_harvest_date = request.form.get('expected_harvest_date')
        yield_expected_kg = request.form.get('yield_expected_kg', 0)
        expenses_pkr = request.form.get('expenses_pkr', 0)
        notes = request.form.get('notes', '')
        
        if not crop_name or not season or not area_acres:
            flash('Please fill in all required fields.', 'danger')
            return render_template('crops/add.html', form_data=request.form)
        
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO crops (user_id, crop_name, crop_type, variety, season, area_acres, 
                             planting_date, expected_harvest_date, yield_expected_kg, 
                             expenses_pkr, notes, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'planted')
        """, (user_id, crop_name, crop_type, variety, season, area_acres,
              planting_date, expected_harvest_date, yield_expected_kg,
              expenses_pkr, notes))
        db.commit()
        crop_id = cursor.lastrowid
        cursor.close()
        
        log_activity(user_id, 'crop_add', f'Added new crop: {crop_name}', 'crops', crop_id)
        create_notification(user_id, f'{crop_name} Added', 
                          f'Your {crop_name} crop has been added successfully.', 'success')
        
        flash(f'{crop_name} has been added successfully!', 'success')
        return redirect(url_for('crops.index'))
    
    return render_template('crops/add.html')

@crops_bp.route('/view/<int:crop_id>')
@login_required
def view(crop_id):
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT * FROM crops WHERE id = %s AND user_id = %s", (crop_id, user_id))
    crop = cursor.fetchone()
    
    if not crop:
        flash('Crop not found.', 'danger')
        return redirect(url_for('crops.index'))
    
    # Get related expenses
    cursor.execute("""
        SELECT * FROM expenses WHERE user_id = %s AND description LIKE %s ORDER BY expense_date DESC
    """, (user_id, f'%{crop["crop_name"]}%'))
    related_expenses = cursor.fetchall()
    
    cursor.close()
    
    return render_template('crops/view.html', crop=crop, related_expenses=related_expenses)

@crops_bp.route('/edit/<int:crop_id>', methods=['GET', 'POST'])
@login_required
def edit(crop_id):
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT * FROM crops WHERE id = %s AND user_id = %s", (crop_id, user_id))
    crop = cursor.fetchone()
    
    if not crop:
        flash('Crop not found.', 'danger')
        return redirect(url_for('crops.index'))
    
    if request.method == 'POST':
        crop_name = request.form.get('crop_name', '').strip()
        crop_type = request.form.get('crop_type', '')
        variety = request.form.get('variety', '').strip()
        season = request.form.get('season', '')
        area_acres = request.form.get('area_acres', 0)
        planting_date = request.form.get('planting_date')
        expected_harvest_date = request.form.get('expected_harvest_date')
        actual_harvest_date = request.form.get('actual_harvest_date')
        status = request.form.get('status', crop['status'])
        yield_expected_kg = request.form.get('yield_expected_kg', 0)
        yield_actual_kg = request.form.get('yield_actual_kg', 0)
        expenses_pkr = request.form.get('expenses_pkr', 0)
        revenue_pkr = request.form.get('revenue_pkr', 0)
        notes = request.form.get('notes', '')
        
        cursor.execute("""
            UPDATE crops SET 
                crop_name = %s, crop_type = %s, variety = %s, season = %s, area_acres = %s,
                planting_date = %s, expected_harvest_date = %s, actual_harvest_date = %s,
                status = %s, yield_expected_kg = %s, yield_actual_kg = %s,
                expenses_pkr = %s, revenue_pkr = %s, notes = %s
            WHERE id = %s AND user_id = %s
        """, (crop_name, crop_type, variety, season, area_acres,
              planting_date, expected_harvest_date, actual_harvest_date,
              status, yield_expected_kg, yield_actual_kg,
              expenses_pkr, revenue_pkr, notes, crop_id, user_id))
        db.commit()
        cursor.close()
        
        log_activity(user_id, 'crop_edit', f'Updated crop: {crop_name}', 'crops', crop_id)
        flash(f'{crop_name} has been updated successfully!', 'success')
        return redirect(url_for('crops.view', crop_id=crop_id))
    
    cursor.close()
    return render_template('crops/edit.html', crop=crop)

@crops_bp.route('/delete/<int:crop_id>', methods=['POST'])
@login_required
def delete(crop_id):
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT crop_name FROM crops WHERE id = %s AND user_id = %s", (crop_id, user_id))
    crop = cursor.fetchone()
    
    if not crop:
        flash('Crop not found.', 'danger')
        return redirect(url_for('crops.index'))
    
    cursor.execute("DELETE FROM crops WHERE id = %s AND user_id = %s", (crop_id, user_id))
    db.commit()
    cursor.close()
    
    log_activity(user_id, 'crop_delete', f'Deleted crop: {crop["crop_name"]}', 'crops', crop_id)
    flash(f'{crop["crop_name"]} has been deleted.', 'success')
    return redirect(url_for('crops.index'))

@crops_bp.route('/harvest/<int:crop_id>', methods=['POST'])
@login_required
def harvest(crop_id):
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()
    
    actual_yield = request.form.get('actual_yield_kg', 0)
    revenue = request.form.get('revenue_pkr', 0)
    
    cursor.execute("""
        UPDATE crops SET 
            status = 'harvested', 
            actual_harvest_date = CURDATE(),
            yield_actual_kg = %s,
            revenue_pkr = %s
        WHERE id = %s AND user_id = %s
    """, (actual_yield, revenue, crop_id, user_id))
    db.commit()
    cursor.close()
    
    log_activity(user_id, 'crop_harvest', f'Harvested crop ID: {crop_id}', 'crops', crop_id)
    flash('Crop has been marked as harvested!', 'success')
    return redirect(url_for('crops.view', crop_id=crop_id))

# Inventory routes
@crops_bp.route('/inventory')
@login_required
def inventory():
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()
    
    category_filter = request.args.get('category', '')
    
    query = "SELECT * FROM inventory WHERE user_id = %s"
    params = [user_id]
    
    if category_filter:
        query += " AND item_category = %s"
        params.append(category_filter)
    
    query += " ORDER BY created_at DESC"
    
    cursor.execute(query, params)
    items = cursor.fetchall()
    
    # Get totals by category
    cursor.execute("""
        SELECT item_category, COUNT(*) as count, SUM(total_cost_pkr) as total 
        FROM inventory WHERE user_id = %s 
        GROUP BY item_category
    """, (user_id,))
    category_totals = cursor.fetchall()
    
    cursor.close()
    
    return render_template('crops/inventory.html', items=items, category_totals=category_totals)

@crops_bp.route('/inventory/add', methods=['POST'])
@login_required
def add_inventory():
    user_id = session['user_id']
    item_name = request.form.get('item_name', '').strip()
    item_category = request.form.get('item_category', '')
    quantity = request.form.get('quantity', 0)
    unit = request.form.get('unit', '')
    cost_per_unit = request.form.get('cost_per_unit_pkr', 0)
    total_cost = float(quantity) * float(cost_per_unit) if quantity and cost_per_unit else 0
    supplier = request.form.get('supplier', '')
    purchase_date = request.form.get('purchase_date')
    expiry_date = request.form.get('expiry_date')
    notes = request.form.get('notes', '')
    
    if not item_name or not item_category:
        flash('Item name and category are required.', 'danger')
        return redirect(url_for('crops.inventory'))
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO inventory (user_id, item_name, item_category, quantity, unit, 
                             cost_per_unit_pkr, total_cost_pkr, supplier, purchase_date, 
                             expiry_date, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (user_id, item_name, item_category, quantity, unit, cost_per_unit, 
           total_cost, supplier, purchase_date, expiry_date, notes))
    db.commit()
    cursor.close()
    
    log_activity(user_id, 'inventory_add', f'Added inventory: {item_name}', 'inventory', cursor.lastrowid)
    flash(f'{item_name} added to inventory.', 'success')
    return redirect(url_for('crops.inventory'))

# Expenses routes
@crops_bp.route('/expenses')
@login_required
def expenses():
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()
    
    category_filter = request.args.get('category', '')
    
    query = "SELECT * FROM expenses WHERE user_id = %s"
    params = [user_id]
    
    if category_filter:
        query += " AND expense_category = %s"
        params.append(category_filter)
    
    query += " ORDER BY expense_date DESC"
    
    cursor.execute(query, params)
    expense_list = cursor.fetchall()
    
    # Get totals
    cursor.execute("""
        SELECT SUM(amount_pkr) as total FROM expenses WHERE user_id = %s
    """, (user_id,))
    total_expenses = cursor.fetchone()['total'] or 0
    
    cursor.execute("""
        SELECT expense_category, SUM(amount_pkr) as total 
        FROM expenses WHERE user_id = %s 
        GROUP BY expense_category
    """, (user_id,))
    category_totals = cursor.fetchall()
    
    cursor.close()
    
    return render_template('crops/expenses.html', 
                         expenses=expense_list, 
                         total_expenses=total_expenses,
                         category_totals=category_totals)

@crops_bp.route('/expenses/add', methods=['POST'])
@login_required
def add_expense():
    user_id = session['user_id']
    expense_category = request.form.get('expense_category', '')
    description = request.form.get('description', '').strip()
    amount_pkr = request.form.get('amount_pkr', 0)
    expense_date = request.form.get('expense_date')
    payment_method = request.form.get('payment_method', 'cash')
    receipt_number = request.form.get('receipt_number', '')
    notes = request.form.get('notes', '')
    
    if not description or not amount_pkr:
        flash('Description and amount are required.', 'danger')
        return redirect(url_for('crops.expenses'))
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO expenses (user_id, expense_category, description, amount_pkr, 
                            expense_date, payment_method, receipt_number, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (user_id, expense_category, description, amount_pkr, 
           expense_date, payment_method, receipt_number, notes))
    db.commit()
    cursor.close()
    
    log_activity(user_id, 'expense_add', f'Added expense: Rs. {amount_pkr}', 'expenses', cursor.lastrowid)
    flash(f'Expense of Rs. {amount_pkr} has been recorded.', 'success')
    return redirect(url_for('crops.expenses'))
