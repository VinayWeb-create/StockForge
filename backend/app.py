"""
app.py — StockForge Flask REST API
====================================
"""

import os
import io
import json
import time
from datetime import datetime, timedelta
from functools import wraps

from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env

import pandas as pd
import yfinance as yf
from flask import (Flask, request, jsonify, session,
                   send_file, send_from_directory, make_response)
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash

import ml_utils

import config
import db_utils

import logger_config
import cache_utils

# ── Logging Setup ─────────────────────────────────────────────────────────────
logger = logger_config.setup_logging()

# ── App Setup ─────────────────────────────────────────────────────────────────
app_config = config.get_config()

app = Flask(__name__)
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend')
app.secret_key = app_config.SECRET_KEY

# Session configuration for production
app.config.update(
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=not app_config.DEBUG,
    SESSION_COOKIE_HTTPONLY=True,
)

# Standardize CORS to handle multi-origin requests correctly.
# In production, recommend setting ALLOWED_ORIGINS env var.
allowed_origins = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000,http://localhost:5000,http://127.0.0.1:5000,http://localhost:5500,http://127.0.0.1:5500').split(',')
CORS(app,
     origins=allowed_origins,
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

# ── Redis Check for Components ────────────────────────────────────────────────
redis_available = False
try:
    import redis
    r = redis.from_url(app_config.REDIS_URL)
    r.ping()
    redis_available = True
    logger.info("Redis is available for Limiter and SocketIO.")
except Exception:
    logger.warning("Redis NOT available. Falling back to in-memory storage for Limiter and disabling SocketIO message queue.")

# SocketIO Setup
socketio_kwargs = {'cors_allowed_origins': "*"}
if redis_available:
    socketio_kwargs['message_queue'] = app_config.SOCKETIO_MESSAGE_QUEUE

socketio = SocketIO(app, **socketio_kwargs)

# Rate Limiter Setup
limiter_storage = app_config.RATELIMIT_STORAGE_URI if redis_available else "memory://"
limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri=limiter_storage,
    default_limits=["200 per day", "50 per hour"],
    strategy="fixed-window"
)

# ── Redis Setup (Caching) ──────────────────────────────────────────────────────
redis_client = cache_utils.get_redis_client(app_config.REDIS_URL)

# ── MongoDB Setup ─────────────────────────────────────────────────────────────
try:
    db, client = db_utils.get_db_connection(
        app_config.MONGO_URI, 
        app_config.DATABASE_NAME
    )
except Exception as e:
    print(f"CRITICAL: Failed to connect to MongoDB. Application may not function correctly. Error: {e}")
    db, client = None, None

# Collections (initialized if db is available)
if db is not None:
    users_col   = db['users']
    session_col = db['stock_sessions']
    history_col = db['history']
    
    # Create Indexes for performance
    try:
        users_col.create_index([("email", ASCENDING)], unique=True)
        session_col.create_index([("user_id", ASCENDING)], unique=True)
        history_col.create_index([("user_id", ASCENDING), ("timestamp", DESCENDING)])
        logger.info("MongoDB indexes verified/created.")
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")
else:
    # Fallback to None if connection fails on startup
    users_col = session_col = history_col = None

# ── Helpers ───────────────────────────────────────────────────────────────────

def ok(data: dict, code: int = 200):
    return jsonify(data), code

def err(msg: str, code: int = 400):
    return jsonify({'error': msg}), code

def serialize(obj):
    """Make MongoDB documents JSON-safe."""
    if isinstance(obj, list):
        return [serialize(o) for o in obj]
    if isinstance(obj, dict):
        return {k: (str(v) if isinstance(v, ObjectId) else serialize(v)) for k, v in obj.items()}
    return obj


def login_required(f):
    """Decorator: require an authenticated session."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return err('Unauthorized — please log in', 401)
        return f(*args, **kwargs)
    return wrapper


def get_current_session(user_id: str) -> dict | None:
    """Fetch the current working session document for a user."""
    return session_col.find_one({'user_id': user_id})


def save_session_data(user_id: str, update: dict):
    """Upsert the user's current working session."""
    session_col.update_one(
        {'user_id': user_id},
        {'$set': {**update, 'updated_at': datetime.utcnow()}},
        upsert=True
    )


def log_history(user_id: str, symbol: str, source: str, rows: int, cleaned: bool = False):
    """Append an entry to the user's analysis history."""
    history_col.insert_one({
        'user_id':   user_id,
        'symbol':    symbol,
        'source':    source,
        'rows':      rows,
        'cleaned':   cleaned,
        'timestamp': datetime.utcnow().isoformat(),
    })


# ── AUTH ENDPOINTS ────────────────────────────────────────────────────────────

def serve_frontend(filename: str):
    """Serve frontend assets from this project directory."""
    path = os.path.join(FRONTEND_DIR, filename)
    if not os.path.isfile(path):
        return err(f'Frontend file not found: {filename}', 404)
    return send_from_directory(FRONTEND_DIR, filename)


@app.route('/', methods=['GET'])
def frontend_root():
    return serve_frontend('index.html')


@app.route('/index.html', methods=['GET'])
def frontend_index():
    return serve_frontend('index.html')


@app.route('/dashboard.html', methods=['GET'])
def frontend_dashboard():
    return serve_frontend('dashboard.html')


@app.route('/style.css', methods=['GET'])
def frontend_style():
    return serve_frontend('style.css')


@app.route('/script.js', methods=['GET'])
def frontend_script():
    return serve_frontend('script.js')


@app.route('/signup', methods=['POST'])
def signup():
    """Create a new user account."""
    body = request.get_json() or {}
    name     = body.get('name', '').strip()
    email    = body.get('email', '').strip().lower()
    password = body.get('password', '')

    if not name or not email or not password:
        return err('All fields are required')
    if len(password) < 6:
        return err('Password must be at least 6 characters')
    if users_col.find_one({'email': email}):
        return err('An account with that email already exists')

    hashed = generate_password_hash(password)
    result = users_col.insert_one({
        'name':       name,
        'email':      email,
        'password':   hashed,
        'created_at': datetime.utcnow(),
    })

    user_id = str(result.inserted_id)
    session['user_id']    = user_id
    session['user_email'] = email
    session['user_name']  = name

    return ok({'message': 'Account created', 'user': {'id': user_id, 'name': name, 'email': email}}, 201)


@app.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    """Authenticate user and create session."""
    body = request.get_json() or {}
    email    = body.get('email', '').strip().lower()
    password = body.get('password', '')

    if not email or not password:
        return err('Email and password required')

    user = users_col.find_one({'email': email})
    if not user or not check_password_hash(user['password'], password):
        return err('Invalid email or password', 401)

    user_id = str(user['_id'])
    session['user_id']    = user_id
    session['user_email'] = email
    session['user_name']  = user.get('name', '')

    return ok({'message': 'Login successful', 'user': {
        'id':    user_id,
        'name':  user.get('name'),
        'email': email,
    }})


@app.route('/logout', methods=['POST'])
def logout():
    """Clear session."""
    session.clear()
    return ok({'message': 'Logged out'})


@app.route('/me', methods=['GET'])
@login_required
def me():
    return ok({'user': {'id': session['user_id'], 'name': session.get('user_name'), 'email': session.get('user_email')}})


# ── DATA INGESTION ────────────────────────────────────────────────────────────

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    """
    Upload CSV file → parse → store in MongoDB session.
    Expects multipart/form-data with 'file' field.
    """
    if 'file' not in request.files:
        return err('No file uploaded')

    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return err('Only CSV files are supported')

    try:
        file_bytes = file.read()
        df = ml_utils.parse_csv(file_bytes)

        if df.empty:
            return err('CSV file is empty')

        records = ml_utils.df_to_records(df)
        save_session_data(session['user_id'], {
            'raw_data':   records,
            'symbol':     file.filename.replace('.csv', ''),
            'source':     'upload',
        })
        log_history(session['user_id'], file.filename.replace('.csv', ''), 'upload', len(records))

        return ok({'message': 'Upload successful', 'data': records, 'rows': len(records)})

    except Exception as e:
        return err(f'Failed to parse CSV: {str(e)}')


@app.route('/fetch-stock', methods=['POST'])
@login_required
def fetch_stock():
    """
    Fetch live stock data from Yahoo Finance using yfinance.
    Body: { symbol, period, interval }
    """
    body     = request.get_json() or {}
    symbol   = body.get('symbol', '').strip().upper()
    period   = body.get('period', '3mo')
    interval = body.get('interval', '1d')

    if not symbol:
        return err('Stock symbol is required')

    # Try cache first
    cache_key = f"stock_data:{symbol}:{period}:{interval}"
    if redis_client:
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                logger.info(f"Cache hit for {symbol}")
                data = json.loads(cached_data)
                save_session_data(session['user_id'], {
                    'raw_data': data['records'],
                    'symbol':   symbol,
                    'source':   'yfinance_cached',
                })
                return ok({'message': 'Data fetched from cache', **data})
        except Exception as e:
            logger.error(f"Cache read error: {e}")

    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)

        if df.empty:
            return err(f'No data found for symbol: {symbol}. Check the ticker and try again.')

        # Reset index to make Date a column
        df = df.reset_index()
        df = ml_utils.normalize_columns(df)

        # Format date
        date_col = 'Date'
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col]).dt.strftime('%Y-%m-%d')

        # Keep only OHLCV columns
        keep = [c for c in ['Date', 'Open', 'High', 'Low', 'Close', 'Volume'] if c in df.columns]
        df   = df[keep]

        records = ml_utils.df_to_records(df)
        save_session_data(session['user_id'], {
            'raw_data': records,
            'symbol':   symbol,
            'source':   'yfinance',
        })
        log_history(session['user_id'], symbol, 'yfinance', len(records))

        response_data = {'message': 'Data fetched', 'data': records, 'rows': len(records), 'symbol': symbol}
        
        # Save to cache
        if redis_client:
            try:
                redis_client.setex(cache_key, 3600, json.dumps(response_data)) # 1 hour cache
            except Exception as e:
                logger.error(f"Cache write error: {e}")

        return ok(response_data)

    except Exception as e:
        return err(f'Failed to fetch {symbol}: {str(e)}')


# ── PROCESSING ENDPOINTS ──────────────────────────────────────────────────────

@app.route('/clean-data', methods=['POST'])
@login_required
def clean_data():
    """Clean the raw dataset stored in the current session."""
    sess = get_current_session(session['user_id'])
    if not sess or not sess.get('raw_data'):
        return err('No data loaded. Upload or fetch a dataset first.')

    try:
        df = pd.DataFrame(sess['raw_data'])
        cleaned_df, cleaning_stats = ml_utils.clean_dataframe(df)

        cleaned_records = ml_utils.df_to_records(cleaned_df)
        save_session_data(session['user_id'], {
            'cleaned_data': cleaned_records,
        })
        log_history(session['user_id'], sess.get('symbol', '?'), sess.get('source', '?'), len(cleaned_records), cleaned=True)

        return ok({'cleaned': cleaned_records, 'stats': cleaning_stats})

    except Exception as e:
        return err(f'Cleaning failed: {str(e)}')


@app.route('/detect-outliers', methods=['POST'])
@login_required
def detect_outliers():
    """Run outlier detection on current dataset."""
    sess   = get_current_session(session['user_id'])
    method = (request.get_json() or {}).get('method', 'iqr')

    if not sess or not sess.get('raw_data'):
        return err('No data loaded')

    try:
        # Use cleaned data if available, else raw
        raw = sess.get('cleaned_data') or sess['raw_data']
        df  = pd.DataFrame(raw)

        annotated_df, out_stats = ml_utils.detect_outliers(df, method=method)

        # Store annotated data in session (without __outlier flag)
        clean_records = ml_utils.df_to_records(annotated_df)
        save_session_data(session['user_id'], {'outlier_data': clean_records})

        return ok({'data': clean_records, 'stats': out_stats})

    except Exception as e:
        return err(f'Outlier detection failed: {str(e)}')


@app.route('/remove-outliers', methods=['POST'])
@login_required
def remove_outliers():
    """Remove flagged outliers from the session dataset."""
    sess = get_current_session(session['user_id'])
    if not sess or not sess.get('outlier_data'):
        return err('Run outlier detection first')

    try:
        df = pd.DataFrame(sess['outlier_data'])
        if '__outlier' in df.columns:
            df = df[df['__outlier'] == False].drop(columns=['__outlier'])

        records = ml_utils.df_to_records(df)
        save_session_data(session['user_id'], {
            'raw_data':     records,
            'cleaned_data': records,
            'outlier_data': None,
        })
        return ok({'data': records, 'rows': len(records)})

    except Exception as e:
        return err(f'Remove outliers failed: {str(e)}')


@app.route('/normalize', methods=['POST'])
@login_required
def normalize():
    """Normalize numeric columns of the current dataset."""
    sess   = get_current_session(session['user_id'])
    method = (request.get_json() or {}).get('method', 'minmax')

    if not sess or not sess.get('raw_data'):
        return err('No data loaded')

    try:
        raw = sess.get('cleaned_data') or sess['raw_data']
        df  = pd.DataFrame(raw)
        norm_df = ml_utils.normalize_dataframe(df, method=method)

        norm_records = ml_utils.df_to_records(norm_df)
        save_session_data(session['user_id'], {'normalized_data': norm_records})

        return ok({'normalized': norm_records, 'method': method})

    except Exception as e:
        return err(f'Normalization failed: {str(e)}')


# ── ANALYTICS ENDPOINTS ───────────────────────────────────────────────────────

@app.route('/predict', methods=['POST'])
@login_required
def predict():
    """
    Run Linear Regression price prediction.
    Body: { forecast_days: int, background: bool }
    """
    body          = request.get_json() or {}
    forecast_days = body.get('forecast_days', 30)
    use_bg        = body.get('background', False)
    
    sess = get_current_session(session['user_id'])
    if not sess or not sess.get('raw_data'):
        return err('No data loaded')

    try:
        raw = sess.get('cleaned_data') or sess['raw_data']
        df  = pd.DataFrame(raw)
        
        if use_bg:
            from tasks import run_prediction_task
            task = run_prediction_task.delay(df.to_json(), int(forecast_days), method='linear')
            return ok({'message': 'Prediction started in background', 'task_id': task.id}, 202)
        
        result = ml_utils.predict_stock_price(df, forecast_days=int(forecast_days))
        return ok(result)
    except Exception as e:
        return err(f'Prediction failed: {str(e)}')


@app.route('/predict-arima', methods=['POST'])
@login_required
def predict_arima():
    """
    Run ARIMA price prediction.
    """
    body          = request.get_json() or {}
    forecast_days = body.get('forecast_days', 30)
    use_bg        = body.get('background', False)

    sess = get_current_session(session['user_id'])
    if not sess or not sess.get('raw_data'):
        return err('No data loaded')

    try:
        raw = sess.get('cleaned_data') or sess['raw_data']
        df  = pd.DataFrame(raw)

        if use_bg:
            from tasks import run_prediction_task
            task = run_prediction_task.delay(df.to_json(), int(forecast_days), method='arima')
            return ok({'message': 'ARIMA Prediction started in background', 'task_id': task.id}, 202)

        result = ml_utils.predict_arima(df, forecast_days=int(forecast_days))
        return ok(result)
    except Exception as e:
        return err(f'ARIMA Prediction failed: {str(e)}')


# ── REALTIME UPDATES (WebSockets) ─────────────────────────────────────────────

@socketio.on('join')
def on_join(data):
    """Join a stock update room."""
    room = data['symbol']
    from flask_socketio import join_room
    join_room(room)
    emit('status', {'msg': f'Joined {room}'})
    logger.info(f"User joined room: {room}")

@socketio.on('subscribe_live')
def handle_subscribe_live(data):
    """Start a simulation or subscribe to live feed."""
    symbol = data.get('symbol')
    # In a prod app, we'd trigger a background worker that fetches data 
    # and emits back via socketio.
    emit('stock_update', {'symbol': symbol, 'price': 150.0 + (0.5 * time.time() % 10), 'time': datetime.utcnow().isoformat()})


@app.route('/compare-stocks', methods=['POST'])
@login_required
def compare_stocks():
    """
    Fetch and compare closing prices for multiple symbols.
    Body: { symbols: ['AAPL', 'TSLA', 'MSFT'], period: '3mo' }
    """
    body    = request.get_json() or {}
    symbols = body.get('symbols', [])
    period  = body.get('period', '3mo')

    if len(symbols) < 2:
        return err('Provide at least 2 symbols')

    try:
        series = []
        dates  = None

        for sym in symbols[:5]:  # max 5 symbols
            ticker = yf.Ticker(sym.upper())
            df     = ticker.history(period=period)
            if df.empty:
                continue
            df = df.reset_index()
            df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')

            if dates is None:
                dates = df['Date'].tolist()

            series.append({
                'symbol': sym.upper(),
                'prices': [round(float(v), 4) if v is not None else None for v in df['Close'].tolist()],
            })

        if not series:
            return err('No data returned for any symbol')

        return ok({'dates': dates, 'series': series})

    except Exception as e:
        return err(f'Comparison failed: {str(e)}')


@app.route('/get-dashboard-data', methods=['GET'])
@login_required
def get_dashboard_data():
    """Return summary stats for the overview dashboard."""
    sess = get_current_session(session['user_id'])
    if not sess or not sess.get('raw_data'):
        return ok({'stats': None, 'data': []})

    raw = sess.get('cleaned_data') or sess['raw_data']
    df  = pd.DataFrame(raw)
    stats = ml_utils.compute_dashboard_stats(df)

    return ok({'stats': stats, 'data': ml_utils.df_to_records(df, max_rows=500)})


# ── DOWNLOAD ENDPOINTS ────────────────────────────────────────────────────────

@app.route('/download/<dtype>', methods=['GET'])
@login_required
def download(dtype):
    """
    Stream a CSV file for download.
    dtype: 'raw' | 'cleaned' | 'normalized'
    """
    sess = get_current_session(session['user_id'])
    if not sess:
        return err('No session data')

    data_map = {
        'raw':        sess.get('raw_data'),
        'cleaned':    sess.get('cleaned_data'),
        'normalized': sess.get('normalized_data'),
    }
    records = data_map.get(dtype)
    if not records:
        return err(f'No {dtype} data available. Run the corresponding processing step first.')

    df  = pd.DataFrame(records)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)

    symbol   = sess.get('symbol', 'stock')
    filename = f'{symbol}_{dtype}.csv'

    return send_file(
        buf,
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename
    )


# ── HISTORY ────────────────────────────────────────────────────────────────────

@app.route('/history', methods=['GET'])
@login_required
def history():
    """Return the user's analysis history (most recent 50)."""
    docs = list(history_col.find(
        {'user_id': session['user_id']},
        {'_id': 0}
    ).sort('timestamp', -1).limit(50))

    return ok({'history': docs})


# ── HEALTH CHECK ──────────────────────────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    """Ping endpoint for deployment health checks."""
    return ok({'status': 'ok', 'timestamp': datetime.utcnow().isoformat()})


# ── STATIC FILE SERVING ───────────────────────────────────────────────────────

@app.route('/')
def index():
    """Serve the landing/login page."""
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/dashboard.html')
def dashboard_page():
    """Serve the dashboard page."""
    return send_from_directory(FRONTEND_DIR, 'dashboard.html')

@app.route('/<path:path>')
def serve_static(path):
    """Serve other static assets (css, js, images)."""
    return send_from_directory(FRONTEND_DIR, path)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    port  = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    print(f"\nStockForge API running on http://localhost:{port}")
    print(f"   MongoDB: {app_config.MONGO_URI}")
    print(f"   Debug:   {debug}\n")
    socketio.run(app, host='0.0.0.0', port=port, debug=debug)
