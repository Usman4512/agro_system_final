import os
from flask import Flask, render_template, session, redirect, url_for
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

from models.db import init_app, get_db, ensure_db_initialized
init_app(app)

with app.app_context():
    try:
        ensure_db_initialized()
    except Exception as e:
        app.logger.error(f'Database initialization failed: {e}')

from routes.auth      import auth_bp
from routes.dashboard import dashboard_bp
from routes.crops     import crops_bp
from routes.admin     import admin_bp
from routes.rates     import rates_bp
from routes.payment   import payment_bp

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(crops_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(rates_bp)
app.register_blueprint(payment_bp)

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))
    return redirect(url_for('auth.login'))

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
