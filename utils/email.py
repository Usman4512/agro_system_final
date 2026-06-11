import smtplib
import secrets
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app, render_template_string, url_for

def generate_verification_token():
    """Generate a secure random token for email verification."""
    return secrets.token_urlsafe(32)

def send_email(subject, recipient, html_content, text_content=None):
    """Send an email using SMTP."""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = current_app.config['MAIL_DEFAULT_SENDER']
        msg['To'] = recipient

        if text_content:
            msg.attach(MIMEText(text_content, 'plain'))
        msg.attach(MIMEText(html_content, 'html'))

        server = smtplib.SMTP(
            current_app.config['MAIL_SERVER'],
            current_app.config['MAIL_PORT']
        )

        if current_app.config['MAIL_USE_TLS']:
            server.starttls()

        server.login(
            current_app.config['MAIL_USERNAME'],
            current_app.config['MAIL_PASSWORD']
        )

        server.sendmail(
            current_app.config['MAIL_DEFAULT_SENDER'],
            recipient,
            msg.as_string()
        )
        server.quit()
        return True
    except Exception as e:
        current_app.logger.error(f"Email sending failed: {str(e)}")
        if current_app.config.get('MAIL_DEBUG'):
            current_app.logger.info(f"Debug email content to {recipient}: {msg.as_string()}")
        return False

def send_verification_email(user_email, token, username):
    """Send email verification link to user."""
    verification_url = url_for('auth.verify_email', token=token, _external=True)
    
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
            body { font-family: 'Poppins', Arial, sans-serif; margin: 0; padding: 0; background: #f0f4f0; }
            .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 16px; overflow: hidden; box-shadow: 0 8px 32px rgba(0,0,0,0.1); }
            .header { background: linear-gradient(135deg, #2d5016 0%, #4a7c23 50%, #7cb342 100%); padding: 40px 30px; text-align: center; }
            .header h1 { color: white; margin: 0; font-size: 28px; font-weight: 700; }
            .header p { color: #c8e6c9; margin: 10px 0 0; font-size: 16px; }
            .content { padding: 40px 30px; }
            .content h2 { color: #2d5016; font-size: 22px; margin-bottom: 15px; }
            .content p { color: #555; font-size: 15px; line-height: 1.7; margin-bottom: 20px; }
            .btn { display: inline-block; background: linear-gradient(135deg, #4a7c23 0%, #7cb342 100%); color: white; text-decoration: none; padding: 16px 40px; border-radius: 50px; font-weight: 600; font-size: 16px; margin: 20px 0; box-shadow: 0 4px 15px rgba(74,124,35,0.3); }
            .btn:hover { background: linear-gradient(135deg, #3d6a1e 0%, #6ba035 100%); }
            .footer { background: #f8faf8; padding: 25px 30px; text-align: center; border-top: 1px solid #e8f5e9; }
            .footer p { color: #777; font-size: 13px; margin: 5px 0; }
            .highlight { background: #e8f5e9; padding: 15px; border-radius: 10px; margin: 20px 0; border-left: 4px solid #4a7c23; }
            .url-box { background: #f5f5f5; padding: 15px; border-radius: 8px; word-break: break-all; font-size: 13px; color: #555; margin: 15px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Agro Management System</h1>
                <p>Your Complete Agriculture Solution</p>
            </div>
            <div class="content">
                <h2>Welcome, {{ username }}!</h2>
                <p>Thank you for registering with <strong>Agro Management System</strong>. To complete your registration and access all features, please verify your email address.</p>
                
                <div class="highlight">
                    <strong>Why verify?</strong>
                    <ul style="margin: 10px 0; padding-left: 20px; color: #555;">
                        <li>Access all dashboard features</li>
                        <li>Receive market rate alerts</li>
                        <li>Save your crop data securely</li>
                        <li>Get weather notifications</li>
                    </ul>
                </div>
                
                <center><a href="{{ verification_url }}" class="btn">Verify My Email Address</a></center>
                
                <p style="margin-top: 25px; font-size: 13px; color: #888;">If the button doesn't work, copy and paste this link into your browser:</p>
                <div class="url-box">{{ verification_url }}</div>
                
                <p style="font-size: 13px; color: #888;">This verification link will expire in <strong>24 hours</strong>.</p>
            </div>
            <div class="footer">
                <p>&copy; 2024 Agro Management System. All rights reserved.</p>
                <p>If you didn't create this account, please ignore this email.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    Welcome to Agro Management System, {username}!
    
    Please verify your email by clicking the link below:
    {verification_url}
    
    This link will expire in 24 hours.
    
    If you didn't create this account, please ignore this email.
    """
    
    html_content = render_template_string(html_template, username=username, verification_url=verification_url)
    
    return send_email(
        'Verify Your Email - Agro Management System',
        user_email,
        html_content,
        text_content
    )

def send_password_reset_email(user_email, token, username):
    """Send password reset link to user."""
    reset_url = url_for('auth.reset_password', token=token, _external=True)
    
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: 'Poppins', Arial, sans-serif; margin: 0; padding: 0; background: #f0f4f0; }
            .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 16px; overflow: hidden; box-shadow: 0 8px 32px rgba(0,0,0,0.1); }
            .header { background: linear-gradient(135deg, #2d5016 0%, #4a7c23 50%, #7cb342 100%); padding: 40px 30px; text-align: center; }
            .header h1 { color: white; margin: 0; font-size: 28px; }
            .content { padding: 40px 30px; }
            .content h2 { color: #2d5016; }
            .content p { color: #555; font-size: 15px; line-height: 1.7; }
            .btn { display: inline-block; background: linear-gradient(135deg, #4a7c23 0%, #7cb342 100%); color: white; text-decoration: none; padding: 16px 40px; border-radius: 50px; font-weight: 600; margin: 20px 0; }
            .footer { background: #f8faf8; padding: 25px; text-align: center; }
            .url-box { background: #f5f5f5; padding: 15px; border-radius: 8px; word-break: break-all; font-size: 13px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Password Reset Request</h1>
            </div>
            <div class="content">
                <h2>Hello, {{ username }}</h2>
                <p>We received a request to reset your password. Click the button below to create a new password:</p>
                <center><a href="{{ reset_url }}" class="btn">Reset Password</a></center>
                <p style="margin-top: 25px; font-size: 13px; color: #888;">Or copy this link:</p>
                <div class="url-box">{{ reset_url }}</div>
                <p style="font-size: 13px; color: #888;">This link expires in <strong>1 hour</strong>. If you didn't request this, please ignore this email.</p>
            </div>
            <div class="footer">
                <p>&copy; 2024 Agro Management System</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    html_content = render_template_string(html_template, username=username, reset_url=reset_url)
    text_content = f"Reset your password: {reset_url}\nThis link expires in 1 hour."
    
    return send_email(
        'Password Reset - Agro Management System',
        user_email,
        html_content,
        text_content
    )

def send_welcome_email(user_email, username):
    """Send welcome email after successful verification."""
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: 'Poppins', Arial, sans-serif; margin: 0; padding: 0; background: #f0f4f0; }
            .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 16px; overflow: hidden; }
            .header { background: linear-gradient(135deg, #2d5016, #4a7c23, #7cb342); padding: 40px; text-align: center; }
            .header h1 { color: white; margin: 0; }
            .content { padding: 40px; }
            .features { display: flex; flex-wrap: wrap; gap: 15px; margin: 25px 0; }
            .feature { flex: 1 1 45%; background: #e8f5e9; padding: 20px; border-radius: 12px; text-align: center; }
            .feature h4 { color: #2d5016; margin: 10px 0 5px; }
            .feature p { color: #555; font-size: 13px; margin: 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Welcome to Agro System!</h1>
            </div>
            <div class="content">
                <h2>Hi {{ username }},</h2>
                <p>Your email has been verified successfully! Here's what you can do now:</p>
                <div class="features">
                    <div class="feature">
                        <h4>Manage Crops</h4>
                        <p>Track planting to harvest</p>
                    </div>
                    <div class="feature">
                        <h4>View Rates</h4>
                        <p>Live market prices in PKR</p>
                    </div>
                    <div class="feature">
                        <h4>Inventory</h4>
                        <p>Manage farm supplies</p>
                    </div>
                    <div class="feature">
                        <h4>Analytics</h4>
                        <p>Track farm performance</p>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    html_content = render_template_string(html_template, username=username)
    return send_email('Welcome to Agro Management System!', user_email, html_content)
