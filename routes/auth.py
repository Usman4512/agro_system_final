from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from models.db import get_db, get_user_by_email, get_user_by_username, get_user_by_id, get_user_by_token, verify_user_email, log_activity, create_notification
from utils.email import generate_verification_token, send_verification_email, send_password_reset_email, send_welcome_email

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip().lower()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        phone = request.form.get('phone', '').strip()
        city = request.form.get('city', '').strip()
        province = request.form.get('province', '')
        farm_size = request.form.get('farm_size', 0)
        farm_type = request.form.get('farm_type', '')
        
        # Validation
        errors = []
        if not full_name or len(full_name) < 3:
            errors.append('Full name must be at least 3 characters.')
        if not username or len(username) < 4:
            errors.append('Username must be at least 4 characters.')
        if not email or '@' not in email:
            errors.append('Please enter a valid email address.')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if password != confirm_password:
            errors.append('Passwords do not match.')
        if not phone:
            errors.append('Phone number is required.')
        if not city:
            errors.append('City is required.')
        if not province:
            errors.append('Please select your province.')
            
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('register.html', form_data=request.form)
        
        db = get_db()
        cursor = db.cursor()
        
        # Check if email exists
        if get_user_by_email(email):
            flash('This email is already registered. Please login.', 'warning')
            return redirect(url_for('auth.login'))
        
        # Check if username exists
        if get_user_by_username(username):
            flash('Username is already taken. Please choose another.', 'warning')
            return render_template('register.html', form_data=request.form)
        
        # Generate verification token
        token = generate_verification_token()
        token_expires = datetime.now() + timedelta(hours=24)
        
        # Hash password
        password_hash = generate_password_hash(password, method='scrypt')
        
        try:
            cursor.execute("""
                INSERT INTO users (full_name, username, email, password_hash, phone, city, province, 
                                 farm_size, farm_type, verification_token, token_expires)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (full_name, username, email, password_hash, phone, city, province, 
                  farm_size, farm_type, token, token_expires))
            db.commit()
            
            # Send verification email
            if send_verification_email(email, token, username):
                flash('Registration successful! Please check your email to verify your account.', 'success')
                return redirect(url_for('auth.verify_pending', email=email))
            else:
                flash('Account created but we could not send verification email. Please contact support.', 'warning')
                return redirect(url_for('auth.login'))
                
        except Exception as e:
            db.rollback()
            current_app.logger.error(f'Registration error: {e}')
            flash('An error occurred. Please try again.', 'danger')
            return render_template('register.html', form_data=request.form)
        finally:
            cursor.close()
    
    return render_template('register.html')

@auth_bp.route('/verify-pending')
def verify_pending():
    email = request.args.get('email', '')
    return render_template('verify_pending.html', email=email)

@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    user = get_user_by_token(token)
    
    if not user:
        flash('Invalid or expired verification link.', 'danger')
        return redirect(url_for('auth.login'))
    
    # Check if token is expired
    if user['token_expires'] and user['token_expires'] < datetime.now():
        flash('Verification link has expired. Please request a new one.', 'warning')
        return redirect(url_for('auth.resend_verification'))
    
    if verify_user_email(token):
        # Send welcome email
        send_welcome_email(user['email'], user['username'])
        
        # Create welcome notification
        create_notification(
            user['id'],
            'Welcome to Agro System!',
            'Your email has been verified successfully. Start managing your farm now!',
            'success'
        )
        
        flash('Email verified successfully! You can now login.', 'success')
    else:
        flash('Verification failed. Please try again or contact support.', 'danger')
    
    return redirect(url_for('auth.login'))

@auth_bp.route('/resend-verification', methods=['GET', 'POST'])
def resend_verification():
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = get_user_by_email(email)
        
        if not user:
            flash('No account found with this email.', 'danger')
            return render_template('resend_verification.html')
        
        if user['is_verified']:
            flash('Your email is already verified. Please login.', 'info')
            return redirect(url_for('auth.login'))
        
        # Generate new token
        token = generate_verification_token()
        token_expires = datetime.now() + timedelta(hours=24)
        
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            UPDATE users SET verification_token = %s, token_expires = %s WHERE id = %s
        """, (token, token_expires, user['id']))
        db.commit()
        cursor.close()
        
        send_verification_email(email, token, user['username'])
        flash('A new verification email has been sent.', 'success')
        return redirect(url_for('auth.verify_pending', email=email))
    
    return render_template('resend_verification.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        username_or_email = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        if not username_or_email or not password:
            flash('Please enter both username/email and password.', 'warning')
            return render_template('login.html')
        
        # Check if input is email or username
        user = get_user_by_email(username_or_email.lower())
        if not user:
            user = get_user_by_username(username_or_email.lower())
        
        if not user:
            flash('Invalid username or email.', 'danger')
            return render_template('login.html')
        
        if not check_password_hash(user['password_hash'], password):
            flash('Invalid password.', 'danger')
            log_activity(user['id'], 'failed_login', 'Failed login attempt', ip_address=request.remote_addr)
            return render_template('login.html')
        
        if user['status'] == 'suspended':
            flash('Your account has been suspended. Please contact support.', 'danger')
            return render_template('login.html')
        
        if not user['is_verified']:
            flash('Please verify your email before logging in.', 'warning')
            return redirect(url_for('auth.verify_pending', email=user['email']))
        
        # Set session
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        session['full_name'] = user['full_name']
        session.permanent = remember
        
        # Log activity
        log_activity(user['id'], 'login', 'User logged in successfully', ip_address=request.remote_addr)
        
        flash(f'Welcome back, {user["full_name"]}!', 'success')
        
        # Redirect based on role
        if user['role'] == 'admin':
            return redirect(url_for('admin.index'))
        return redirect(url_for('dashboard.index'))
    
    return render_template('login.html')

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = get_user_by_email(email)
        
        if not user:
            # Don't reveal if email exists
            flash('If an account exists, a password reset link will be sent.', 'info')
            return redirect(url_for('auth.login'))
        
        token = generate_verification_token()
        token_expires = datetime.now() + timedelta(hours=1)
        
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            UPDATE users SET verification_token = %s, token_expires = %s WHERE id = %s
        """, (token, token_expires, user['id']))
        db.commit()
        cursor.close()
        
        send_password_reset_email(email, token, user['username'])
        flash('Password reset link has been sent to your email.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('forgot_password.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))
    
    user = get_user_by_token(token)
    
    if not user or (user['token_expires'] and user['token_expires'] < datetime.now()):
        flash('Invalid or expired reset link.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        
        if not password or len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('reset_password.html', token=token)
        
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password.html', token=token)
        
        password_hash = generate_password_hash(password, method='scrypt')
        
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            UPDATE users SET password_hash = %s, verification_token = NULL, token_expires = NULL WHERE id = %s
        """, (password_hash, user['id']))
        db.commit()
        cursor.close()
        
        flash('Password reset successful! Please login with your new password.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('reset_password.html', token=token)

@auth_bp.route('/logout')
def logout():
    if 'user_id' in session:
        log_activity(session['user_id'], 'logout', 'User logged out')
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))
