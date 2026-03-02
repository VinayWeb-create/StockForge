"""
ml_utils.py — StockForge ML & Data Processing Utilities
=========================================================
All heavy-lifting pandas / numpy / sklearn operations live here,
keeping app.py clean and focused on routing.
"""

import io
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score, mean_absolute_error
from datetime import datetime, timedelta
from statsmodels.tsa.arima.model import ARIMA
import warnings
warnings.filterwarnings("ignore")

# ── Column Aliases ────────────────────────────────────────────────────────────
# Support both title-case and lower-case column names
COLUMN_MAP = {
    'date':   ['Date', 'date', 'DATE', 'Datetime', 'datetime'],
    'open':   ['Open', 'open', 'OPEN'],
    'high':   ['High', 'high', 'HIGH'],
    'low':    ['Low',  'low',  'LOW'],
    'close':  ['Close','close','CLOSE', 'Adj Close', 'adj_close'],
    'volume': ['Volume','volume','VOLUME','Vol'],
}

NUMERIC_COLS = ['open', 'high', 'low', 'close', 'volume']


def _resolve_col(df: pd.DataFrame, logical: str) -> str | None:
    """Return actual column name in df that matches the logical name."""
    for candidate in COLUMN_MAP.get(logical, [logical]):
        if candidate in df.columns:
            return candidate
    return None


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename columns to standard Title-Case names."""
    rename = {}
    for logical, candidates in COLUMN_MAP.items():
        for c in candidates:
            if c in df.columns:
                rename[c] = logical.title()
                break
    return df.rename(columns=rename)


# ── CSV Parsing ───────────────────────────────────────────────────────────────

def parse_csv(file_bytes: bytes) -> pd.DataFrame:
    """
    Parse uploaded CSV bytes into a DataFrame.
    Normalises column names and returns clean-ish df.
    """
    df = pd.read_csv(io.BytesIO(file_bytes))
    df = normalize_columns(df)
    return df


# ── Data Cleaning ─────────────────────────────────────────────────────────────

def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Perform comprehensive data cleaning:
    1. Drop rows with null values
    2. Remove duplicate rows
    3. Parse and standardise Date column
    4. Sort by date ascending
    5. Convert numeric columns

    Returns:
        cleaned_df : cleaned DataFrame
        stats      : dict with counts of what was removed
    """
    original_len = len(df)
    stats = {}

    # 1. Drop nulls
    before_null = len(df)
    df = df.dropna()
    stats['nulls_removed'] = before_null - len(df)

    # 2. Drop duplicates
    before_dupe = len(df)
    df = df.drop_duplicates()
    stats['duplicates_removed'] = before_dupe - len(df)

    # 3. Parse date column
    date_col = _resolve_col(df, 'date') or 'Date'
    if date_col in df.columns:
        try:
            df[date_col] = pd.to_datetime(df[date_col])
            df[date_col] = df[date_col].dt.strftime('%Y-%m-%d')
        except Exception:
            pass  # leave as-is if unparseable

    # 4. Convert numeric columns
    for logical in NUMERIC_COLS:
        col = _resolve_col(df, logical)
        if col:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # 5. Sort by date
    if date_col in df.columns:
        df = df.sort_values(date_col).reset_index(drop=True)

    stats['rows_removed']   = original_len - len(df)
    stats['rows_remaining'] = len(df)

    return df, stats


# ── Outlier Detection ─────────────────────────────────────────────────────────

def detect_outliers_iqr(df: pd.DataFrame, col: str = 'Close') -> np.ndarray:
    """
    IQR-based outlier detection.
    Returns boolean mask: True = outlier.
    """
    actual_col = _resolve_col(df, col.lower()) or col
    if actual_col not in df.columns:
        return np.zeros(len(df), dtype=bool)

    q1 = df[actual_col].quantile(0.25)
    q3 = df[actual_col].quantile(0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return (df[actual_col] < lower) | (df[actual_col] > upper)


def detect_outliers_zscore(df: pd.DataFrame, col: str = 'Close', threshold: float = 3.0) -> np.ndarray:
    """
    Z-Score outlier detection.
    Rows with |z| > threshold are flagged.
    """
    actual_col = _resolve_col(df, col.lower()) or col
    if actual_col not in df.columns:
        return np.zeros(len(df), dtype=bool)

    z = np.abs(stats.zscore(df[actual_col].fillna(df[actual_col].median())))
    return z > threshold


def detect_outliers_isolation_forest(df: pd.DataFrame) -> np.ndarray:
    """
    Isolation Forest — ML-based multivariate outlier detection.
    Uses Open, High, Low, Close, Volume features.
    Returns boolean mask: True = outlier.
    """
    feature_cols = []
    for logical in NUMERIC_COLS:
        col = _resolve_col(df, logical)
        if col:
            feature_cols.append(col)

    if not feature_cols:
        return np.zeros(len(df), dtype=bool)

    X = df[feature_cols].fillna(0).values
    model = IsolationForest(contamination=0.05, random_state=42, n_estimators=100)
    preds = model.fit_predict(X)
    return preds == -1   # -1 = outlier in sklearn convention


def detect_outliers(df: pd.DataFrame, method: str = 'iqr') -> tuple[pd.DataFrame, dict]:
    """
    Dispatcher for outlier detection methods.

    Args:
        df     : input DataFrame
        method : 'iqr' | 'zscore' | 'isolation_forest'

    Returns:
        annotated_df : df with __outlier bool column added
        stats        : detection statistics
    """
    if method == 'iqr':
        mask = detect_outliers_iqr(df)
    elif method == 'zscore':
        mask = detect_outliers_zscore(df)
    elif method == 'isolation_forest':
        mask = detect_outliers_isolation_forest(df)
    else:
        raise ValueError(f'Unknown method: {method}')

    result = df.copy()
    result['__outlier'] = mask.tolist()

    outlier_count = int(mask.sum())
    total_rows    = len(df)

    stats = {
        'method':        method,
        'outlier_count': outlier_count,
        'total_rows':    total_rows,
        'outlier_pct':   round(outlier_count / total_rows * 100, 2) if total_rows else 0,
    }
    return result, stats


# ── Normalization ─────────────────────────────────────────────────────────────

def normalize_dataframe(df: pd.DataFrame, method: str = 'minmax') -> pd.DataFrame:
    """
    Normalize numeric columns using specified scaler.

    Args:
        df     : input DataFrame
        method : 'minmax' | 'standard'

    Returns:
        Normalized DataFrame (date column preserved as-is)
    """
    numeric_actual = []
    for logical in NUMERIC_COLS:
        col = _resolve_col(df, logical)
        if col and col in df.columns:
            numeric_actual.append(col)

    if not numeric_actual:
        return df

    result = df.copy()

    if method == 'minmax':
        scaler = MinMaxScaler()
    elif method == 'standard':
        scaler = StandardScaler()
    else:
        raise ValueError(f'Unknown method: {method}')

    result[numeric_actual] = scaler.fit_transform(result[numeric_actual].fillna(0))

    return result


# ── AI Price Prediction ───────────────────────────────────────────────────────

def predict_stock_price(df: pd.DataFrame, forecast_days: int = 30) -> dict:
    """
    Linear Regression price prediction.

    Features: day index (integer ordinal of date)
    Target:   Close price

    Returns dict with:
        actual_dates, actual_prices,
        forecast_dates, forecast_prices,
        r2, mae, next_day
    """
    close_col = _resolve_col(df, 'close') or 'Close'
    date_col  = _resolve_col(df, 'date')  or 'Date'

    if close_col not in df.columns:
        raise ValueError('No Close column found in dataset')

    # Build feature: numeric day index
    clean = df[[date_col, close_col]].dropna().copy() if date_col in df.columns else df[[close_col]].dropna().copy()
    clean = clean.reset_index(drop=True)

    X = np.arange(len(clean)).reshape(-1, 1)
    y = clean[close_col].values.astype(float)

    model = LinearRegression()
    model.fit(X, y)

    y_pred = model.predict(X)
    r2     = r2_score(y, y_pred)
    mae    = mean_absolute_error(y, y_pred)

    # Forecast future days
    last_idx = len(clean)
    future_X = np.arange(last_idx, last_idx + forecast_days).reshape(-1, 1)
    future_prices = model.predict(future_X).tolist()

    # Build date labels
    if date_col in clean.columns:
        try:
            last_date = pd.to_datetime(clean[date_col].iloc[-1])
        except Exception:
            last_date = datetime.today()
    else:
        last_date = datetime.today()

    forecast_dates = [(last_date + timedelta(days=i+1)).strftime('%Y-%m-%d') for i in range(forecast_days)]
    actual_dates   = clean[date_col].tolist() if date_col in clean.columns else [str(i) for i in range(len(clean))]

    return {
        'actual_dates':    [str(d) for d in actual_dates[-120:]],  # last 120 actual points
        'actual_prices':   y[-120:].tolist(),
        'forecast_dates':  forecast_dates,
        'forecast_prices': future_prices,
        'r2':              float(round(r2, 6)),
        'mae':             float(round(mae, 4)),
        'next_day':        float(round(future_prices[0], 2)),
    }


def predict_arima(df: pd.DataFrame, forecast_days: int = 30) -> dict:
    """
    ARIMA (AutoRegressive Integrated Moving Average) price prediction.
    """
    close_col = _resolve_col(df, 'close') or 'Close'
    date_col  = _resolve_col(df, 'date')  or 'Date'

    if close_col not in df.columns:
        raise ValueError('No Close column found in dataset')

    # ARIMA needs a series with date index
    clean = df[[date_col, close_col]].dropna().copy() if date_col in df.columns else df[[close_col]].dropna().copy()
    
    if date_col in clean.columns:
        clean[date_col] = pd.to_datetime(clean[date_col])
        clean.set_index(date_col, inplace=True)
    
    y = clean[close_col].values.astype(float)
    
    # Fit ARIMA model (Order (5,1,0) is a common starting point for stock prices)
    try:
        model = ARIMA(y, order=(5, 1, 0))
        model_fit = model.fit()
        
        # Forecast
        forecast = model_fit.forecast(steps=forecast_days)
        future_prices = forecast.tolist()
        
        # Calculate accuracy on training data (in-sample)
        y_pred = model_fit.predict(start=0, end=len(y)-1)
        r2 = r2_score(y, y_pred)
        mae = mean_absolute_error(y, y_pred)
        
        # Build date labels
        last_date = pd.to_datetime(df[date_col].iloc[-1]) if date_col in df.columns else datetime.today()
        forecast_dates = [(last_date + timedelta(days=i+1)).strftime('%Y-%m-%d') for i in range(forecast_days)]
        actual_dates = df[date_col].tolist() if date_col in df.columns else [str(i) for i in range(len(df))]
        
        return {
            'actual_dates':    [str(d) for d in actual_dates[-120:]],
            'actual_prices':   y[-120:].tolist(),
            'forecast_dates':  forecast_dates,
            'forecast_prices': [float(round(p, 4)) for p in future_prices],
            'r2':              float(round(r2, 6)),
            'mae':             float(round(mae, 4)),
            'next_day':        float(round(future_prices[0], 2)),
            'method':          'ARIMA'
        }
    except Exception as e:
        # Fallback to linear if ARIMA fails (e.g. not enough data)
        return predict_stock_price(df, forecast_days=forecast_days)


# ── Dashboard Analytics ───────────────────────────────────────────────────────

def compute_dashboard_stats(df: pd.DataFrame) -> dict:
    """Compute summary stats for overview dashboard."""
    close_col = _resolve_col(df, 'close') or 'Close'
    vol_col   = _resolve_col(df, 'volume') or 'Volume'

    closes  = pd.to_numeric(df[close_col],  errors='coerce').dropna() if close_col  in df.columns else pd.Series(dtype=float)
    volumes = pd.to_numeric(df[vol_col],    errors='coerce').dropna() if vol_col    in df.columns else pd.Series(dtype=float)

    return {
        'total_rows':  len(df),
        'highest':     float(closes.max())   if len(closes)  else None,
        'lowest':      float(closes.min())   if len(closes)  else None,
        'average':     float(closes.mean())  if len(closes)  else None,
        'total_volume': float(volumes.sum()) if len(volumes) else None,
    }


# ── DataFrame → JSON-safe dicts ───────────────────────────────────────────────

def df_to_records(df: pd.DataFrame, max_rows: int = None) -> list[dict]:
    """Convert df to list of dicts safe for JSON serialization."""
    if max_rows:
        df = df.head(max_rows)
    # Replace NaN / inf with None
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.where(pd.notnull(df), None)
    return df.to_dict(orient='records')
