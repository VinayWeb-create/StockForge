# 📈 StockForge — AI-Powered Stock Data Wrangling & Analysis System

A production-grade full-stack web application for stock market data ingestion, cleaning, outlier detection, normalization, and AI-powered price prediction — built with Flask, MongoDB, and Chart.js.

---

## 🏗️ Folder Structure

```
project-root/
├── frontend/
│   ├── index.html        ← Login / Signup page
│   ├── dashboard.html    ← Main dashboard (all features)
│   ├── style.css         ← Shared design system (dark/light theme)
│   └── script.js         ← All frontend logic, API calls, charts
│
├── backend/
│   ├── app.py            ← Flask REST API (all endpoints)
│   ├── ml_utils.py       ← ML & data processing (pandas, sklearn, etc.)
│   └── requirements.txt  ← Python dependencies
│
└── README.md
```

---

## ✨ Features

| Category | Feature |
|---|---|
| **Auth** | Signup / Login / Logout with bcrypt password hashing |
| **Data Ingestion** | CSV upload · yfinance live fetch |
| **Data Cleaning** | Null removal · deduplication · date parsing · sort |
| **Outlier Detection** | IQR · Z-Score · Isolation Forest (ML) |
| **Normalization** | MinMaxScaler · StandardScaler |
| **Analytics** | Closing price chart · Volume bar · OHLC lines · MA7/MA20/MA50 |
| **AI Prediction** | Linear Regression forecast with R², MAE, next-day prediction |
| **Multi-Stock** | Compare up to 5 tickers side-by-side |
| **Download** | Export raw / cleaned / normalized datasets as CSV |
| **History** | Full session history per user in MongoDB |
| **UI/UX** | Dark/Light mode · Responsive · Toast alerts · Loading overlays |

---

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.11+
- MongoDB (local or Atlas)
- A modern browser

### 1. Clone / Download

```bash
git clone https://github.com/yourname/stockforge
cd stockforge
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv

# Mac/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Configure MongoDB

By default the app connects to `mongodb://localhost:27017/`.

To use MongoDB Atlas or a custom URI, set the environment variable:

```bash
export MONGO_URI="mongodb+srv://user:pass@cluster.mongodb.net/"
```

### 4. Start the Backend

```bash
cd backend
python app.py
```

The API will be available at `http://localhost:5000`.

### 5. Open the Frontend

Simply open `frontend/index.html` in your browser, or serve it with any static file server:

```bash
# Using Python
cd frontend
python -m http.server 5500

# Then open http://localhost:5500
```

---

## 🔌 REST API Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/signup` | ✗ | Create account |
| POST | `/login` | ✗ | Log in |
| POST | `/logout` | ✓ | Log out |
| GET | `/me` | ✓ | Current user |
| POST | `/upload` | ✓ | Upload CSV |
| POST | `/fetch-stock` | ✓ | Fetch from yfinance |
| POST | `/clean-data` | ✓ | Clean current dataset |
| POST | `/detect-outliers` | ✓ | Detect outliers |
| POST | `/remove-outliers` | ✓ | Remove flagged outliers |
| POST | `/normalize` | ✓ | Normalize data |
| POST | `/predict` | ✓ | AI price prediction |
| POST | `/compare-stocks` | ✓ | Multi-ticker comparison |
| GET | `/download/<type>` | ✓ | Download CSV (raw/cleaned/normalized) |
| GET | `/get-dashboard-data` | ✓ | Dashboard summary stats |
| GET | `/history` | ✓ | User session history |
| GET | `/health` | ✗ | Health check |

---

## 📊 CSV Format

Expected columns (case-insensitive):

```
Date, Open, High, Low, Close, Volume
```

Example:
```csv
Date,Open,High,Low,Close,Volume
2024-01-02,185.23,186.57,184.11,185.92,55821900
2024-01-03,183.00,184.26,181.44,184.25,53309000
```

---

## 🧠 ML / Data Science Details

### Data Cleaning
- Null rows dropped
- Duplicate rows removed
- Dates parsed to `YYYY-MM-DD`
- Numeric columns coerced
- Sorted by date ascending

### Outlier Detection

| Method | Approach |
|--------|----------|
| **IQR** | Q1 − 1.5×IQR ↔ Q3 + 1.5×IQR on Close price |
| **Z-Score** | \|z\| > 3.0 on Close price |
| **Isolation Forest** | Unsupervised ML on OHLCV; contamination=5% |

### Normalization

| Scaler | Formula |
|--------|---------|
| **MinMax** | `(x - min) / (max - min)` → [0, 1] |
| **Standard** | `(x - μ) / σ` → N(0,1) |

### AI Prediction
- Feature: integer day index
- Target: Close price
- Model: `LinearRegression` (scikit-learn)
- Metrics: R² Score, Mean Absolute Error
- Output: N-day forecast beyond the dataset

---

## 🚀 Deployment Guide

### Docker (Recommended)

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  backend:
    build: ./backend
    ports: ["5000:5000"]
    environment:
      - MONGO_URI=mongodb://mongo:27017/
      - SECRET_KEY=your-prod-secret
    depends_on: [mongo]
  mongo:
    image: mongo:7
    volumes: [mongo_data:/data/db]
  frontend:
    image: nginx:alpine
    volumes: [./frontend:/usr/share/nginx/html:ro]
    ports: ["80:80"]
volumes:
  mongo_data:
```

### Deploy to Render

1. Push to GitHub
2. Create a Web Service → build `pip install -r requirements.txt`
3. Start command: `gunicorn -b 0.0.0.0:$PORT app:app`
4. Set env vars: `MONGO_URI`, `SECRET_KEY`

### Frontend on Vercel / Netlify

Upload the `frontend/` folder directly — it's pure HTML/CSS/JS with no build step.
Update `API` constant in `script.js` to your deployed backend URL.

---

## 🛡️ Security Notes

- Passwords hashed with **bcrypt** via Werkzeug
- Session secrets should be set via environment variables in production
- CORS restricted to known origins
- `SESSION_COOKIE_SECURE=True` in production (HTTPS required)
- Input validation on all endpoints

---

## 📦 Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML5 · CSS3 · Vanilla JS · Chart.js 4 |
| Backend | Python 3.11 · Flask 3 · Flask-CORS |
| Database | MongoDB 7 · PyMongo |
| Data | Pandas · NumPy · SciPy |
| ML | Scikit-learn (IsolationForest, LinearRegression, Scalers) |
| Market Data | yfinance |
| Auth | Werkzeug password hashing · Flask sessions |

---

## 🙌 Credits

Built as a production-level portfolio project demonstrating:
- Full-stack Python/JS development
- RESTful API design
- ML pipeline integration
- MongoDB data persistence
- Professional UI/UX design

---

*MIT License — StockForge 2024*
