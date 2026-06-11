from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models.db import get_db

rates_bp = Blueprint('rates', __name__, url_prefix='/rates')

def login_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

@rates_bp.route('/')
@login_required
def index():
    db = get_db()
    cursor = db.cursor()
    
    # Filters
    crop_filter = request.args.get('crop', '')
    city_filter = request.args.get('city', '')
    market_filter = request.args.get('market', '')
    
    query = "SELECT * FROM crop_rates WHERE is_active = 1"
    params = []
    
    if crop_filter:
        query += " AND crop_name = %s"
        params.append(crop_filter)
    if city_filter:
        query += " AND city = %s"
        params.append(city_filter)
    if market_filter:
        query += " AND market_name LIKE %s"
        params.append(f'%{market_filter}%')
    
    query += " ORDER BY date_recorded DESC, crop_name"
    
    cursor.execute(query, params)
    rates = cursor.fetchall()
    
    # Get unique lists for filters
    cursor.execute("SELECT DISTINCT crop_name FROM crop_rates WHERE is_active = 1 ORDER BY crop_name")
    crops = [row['crop_name'] for row in cursor.fetchall()]
    
    cursor.execute("SELECT DISTINCT city FROM crop_rates WHERE is_active = 1 ORDER BY city")
    cities = [row['city'] for row in cursor.fetchall()]
    
    # Get average rates by crop
    cursor.execute("""
        SELECT crop_name, 
               AVG(rate_per_kg_pkr) as avg_rate_kg,
               MIN(rate_per_kg_pkr) as min_rate_kg,
               MAX(rate_per_kg_pkr) as max_rate_kg,
               COUNT(*) as market_count
        FROM crop_rates 
        WHERE is_active = 1 
        AND date_recorded >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
        GROUP BY crop_name
        ORDER BY avg_rate_kg DESC
    """)
    avg_rates = cursor.fetchall()
    
    cursor.close()
    
    return render_template('rates/index.html',
                         rates=rates,
                         crops=crops,
                         cities=cities,
                         avg_rates=avg_rates,
                         filters={
                             'crop': crop_filter,
                             'city': city_filter,
                             'market': market_filter
                         })

@rates_bp.route('/crop/<crop_name>')
@login_required
def crop_detail(crop_name):
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT * FROM crop_rates 
        WHERE crop_name = %s AND is_active = 1
        ORDER BY date_recorded DESC, city
    """, (crop_name,))
    rates = cursor.fetchall()
    
    if not rates:
        flash('No rate data found for this crop.', 'info')
        return redirect(url_for('rates.index'))
    
    # Get price history for chart
    cursor.execute("""
        SELECT DATE_FORMAT(date_recorded, '%Y-%m-%d') as date, 
               AVG(rate_per_kg_pkr) as avg_price
        FROM crop_rates 
        WHERE crop_name = %s 
        AND date_recorded >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        GROUP BY date_recorded
        ORDER BY date_recorded
    """, (crop_name,))
    price_history = cursor.fetchall()
    
    # Get market comparison
    cursor.execute("""
        SELECT city, market_name, rate_per_kg_pkr, quality_grade
        FROM crop_rates
        WHERE crop_name = %s AND is_active = 1
        AND date_recorded = (SELECT MAX(date_recorded) FROM crop_rates WHERE crop_name = %s)
        ORDER BY rate_per_kg_pkr DESC
    """, (crop_name, crop_name))
    market_comparison = cursor.fetchall()
    
    cursor.close()
    
    return render_template('rates/detail.html',
                         crop_name=crop_name,
                         rates=rates,
                         price_history=price_history,
                         market_comparison=market_comparison)
