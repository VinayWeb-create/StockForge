import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'stockforge-dev-secret-change-in-prod')
    
    # MongoDB
    MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
    DATABASE_NAME = os.environ.get('MONGO_DB_NAME', 'stockforge')
    
    # JWT (for future-proofing / production)
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    
    # Redis (Caching & Celery)
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    
    # Rate Limiting
    RATELIMIT_STORAGE_URI = REDIS_URL
    
    # Flask-SocketIO
    SOCKETIO_MESSAGE_QUEUE = REDIS_URL
    
    # Misc
    DEBUG = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    PORT = int(os.environ.get('PORT', 5000))

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    # In production, cookies should be secure
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

config_by_name = {
    'dev': DevelopmentConfig,
    'prod': ProductionConfig
}

def get_config():
    env = os.environ.get('FLASK_ENV', 'dev')
    return config_by_name.get(env, DevelopmentConfig)
