from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models.db import get_db, get_user_by_id, log_activity, create_notification, activate_subscription
import os

payment_bp = Blueprint('payment', __name__, url_prefix='/payment')

PLANS = {
    'basic':    {'name': 'Basic',    'price': 500,  'months': 1,  'features': ['Crop Management', 'Market Rates', 'Inventory', 'Expenses', 'Dashboard']},
    'standard': {'name': 'Standard', 'price': 1500, 'months': 1,  'features': ['Everything in Basic', 'Priority Support', 'Export Reports', 'Bulk Data Entry']},
    'premium':  {'name': 'Premium',  'price': 3000, 'months': 1,  'features': ['Everything in Standard', 'API Access', 'Multiple Farm Profiles', 'Dedicated Support']},
}

JAZZCASH_NUMBER = os.environ.get('JAZZCASH_NUMBER', '03XX-XXXXXXX')
EASYPAISA_NUMBER = os.environ.get('EASYPAISA_NUMBER', '03XX-XXXXXXX')
OWNER_NAME = os.environ.get('OWNER_NAME', 'Agro System')


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wrapper


@payment_bp.route('/')
@login_required
def plans():
    user = get_user_by_id(session['user_id'])
    return render_template('payment/plans.html',
                           plans=PLANS,
                           user=user,
                           jazzcash=JAZZCASH_NUMBER,
                           easypaisa=EASYPAISA_NUMBER,
                           owner=OWNER_NAME)


@payment_bp.route('/submit/<plan>', methods=['GET', 'POST'])
@login_required
def submit(plan):
    if plan not in PLANS:
        flash('Invalid plan selected.', 'danger')
        return redirect(url_for('payment.plans'))

    plan_info = PLANS[plan]
    user = get_user_by_id(session['user_id'])

    if request.method == 'POST':
        transaction_id  = request.form.get('transaction_id', '').strip()
        jazzcash_number = request.form.get('jazzcash_number', '').strip()

        if not transaction_id or not jazzcash_number:
            flash('Please fill in Transaction ID and your JazzCash/Easypaisa number.', 'danger')
            return render_template('payment/submit.html',
                                   plan=plan, plan_info=plan_info,
                                   jazzcash=JAZZCASH_NUMBER,
                                   easypaisa=EASYPAISA_NUMBER,
                                   owner=OWNER_NAME)

        db = get_db()
        cur = db.cursor()
        cur.execute("""
            INSERT INTO payment_requests
            (user_id, plan, amount_pkr, jazzcash_number, transaction_id, status)
            VALUES (%s, %s, %s, %s, %s, 'pending')
        """, (session['user_id'], plan, plan_info['price'], jazzcash_number, transaction_id))
        db.commit()
        cur.close()

        log_activity(session['user_id'], 'payment_submitted',
                     f'Payment request submitted for {plan} plan - TxID: {transaction_id}')
        create_notification(session['user_id'],
                            'Payment Request Submitted',
                            f'Your Rs. {plan_info["price"]} payment request for {plan_info["name"]} plan has been received. We will activate your account within 24 hours after verification.',
                            'info')

        flash('Payment request submitted! Your account will be activated within 24 hours after verification.', 'success')
        return redirect(url_for('payment.pending'))

    return render_template('payment/submit.html',
                           plan=plan, plan_info=plan_info,
                           jazzcash=JAZZCASH_NUMBER,
                           easypaisa=EASYPAISA_NUMBER,
                           owner=OWNER_NAME)


@payment_bp.route('/pending')
@login_required
def pending():
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT * FROM payment_requests
        WHERE user_id = %s ORDER BY created_at DESC LIMIT 5
    """, (session['user_id'],))
    requests = cur.fetchall()
    cur.close()
    return render_template('payment/pending.html', requests=requests)


# ── Admin payment management ──────────────────────────────────

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return wrapper


@payment_bp.route('/admin/requests')
@admin_required
def admin_requests():
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT pr.*, u.full_name, u.username, u.email, u.phone
        FROM payment_requests pr
        JOIN users u ON pr.user_id = u.id
        ORDER BY pr.created_at DESC
    """)
    requests = cur.fetchall()
    cur.close()
    return render_template('payment/admin_requests.html', requests=requests, plans=PLANS)


@payment_bp.route('/admin/approve/<int:req_id>', methods=['POST'])
@admin_required
def approve(req_id):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM payment_requests WHERE id = %s", (req_id,))
    req = cur.fetchone()

    if not req:
        flash('Payment request not found.', 'danger')
        return redirect(url_for('payment.admin_requests'))

    # Activate subscription
    activate_subscription(req['user_id'], req['plan'], months=1)

    # Mark request approved
    cur.execute("""
        UPDATE payment_requests SET status='approved', admin_note='Verified and activated'
        WHERE id = %s
    """, (req_id,))
    db.commit()
    cur.close()

    # Notify farmer
    plan_info = PLANS.get(req['plan'], {})
    create_notification(req['user_id'],
                        'Subscription Activated!',
                        f'Your {plan_info.get("name","") } plan has been activated for 1 month. Thank you for subscribing to Agro System!',
                        'success')
    log_activity(session['user_id'], 'payment_approved',
                 f'Approved payment for user {req["user_id"]} — plan: {req["plan"]}')

    flash('Payment approved and subscription activated!', 'success')
    return redirect(url_for('payment.admin_requests'))


@payment_bp.route('/admin/reject/<int:req_id>', methods=['POST'])
@admin_required
def reject(req_id):
    note = request.form.get('note', 'Payment could not be verified.')
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM payment_requests WHERE id=%s", (req_id,))
    req = cur.fetchone()

    if req:
        cur.execute("""
            UPDATE payment_requests SET status='rejected', admin_note=%s WHERE id=%s
        """, (note, req_id))
        db.commit()
        create_notification(req['user_id'],
                            'Payment Not Verified',
                            f'Your payment request could not be verified. Reason: {note}. Please resubmit with correct details.',
                            'error')
    cur.close()
    flash('Payment request rejected.', 'warning')
    return redirect(url_for('payment.admin_requests'))
