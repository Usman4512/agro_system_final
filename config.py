import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-in-production')

    MYSQL_HOST        = os.environ.get('MYSQL_HOST', '127.0.0.1')
    MYSQL_USER        = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD    = os.environ.get('MYSQL_PASSWORD', 'Usman$5000')
    MYSQL_DB          = os.environ.get('MYSQL_DB', 'agrosystem')
    MYSQL_PORT        = int(os.environ.get('MYSQL_PORT', 3306))
    MYSQL_CURSORCLASS = 'DictCursor'

    UPLOAD_FOLDER      = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)

    MAIL_SERVER         = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT           = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS        = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_DEBUG          = os.environ.get('MAIL_DEBUG', 'False').lower() == 'true'
    MAIL_USERNAME       = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD       = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'Agro System <noreply@agrosystem.com>')

    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@agrosystem.com')

    # Payment — YOUR JazzCash/Easypaisa numbers
    JAZZCASH_NUMBER  = os.environ.get('JAZZCASH_NUMBER', '03XX-XXXXXXX')
    EASYPAISA_NUMBER = os.environ.get('EASYPAISA_NUMBER', '03XX-XXXXXXX')
    OWNER_NAME       = os.environ.get('OWNER_NAME', 'Agro System')
