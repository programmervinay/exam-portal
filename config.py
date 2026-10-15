import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'emp-v2-super-secret-key-mad2-iitm-2026')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f"sqlite:///{os.path.join(BASE_DIR, 'emp_v2.db')}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT Configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'emp-v2-super-secure-jwt-token-secret-key-iitm-mad2-2026-portal')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)
    JWT_HEADER_TYPE = 'Bearer'
    
    # Redis & Caching Configuration
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CACHE_TYPE = os.environ.get('CACHE_TYPE', 'RedisCache')
    CACHE_REDIS_URL = REDIS_URL
    CACHE_DEFAULT_TIMEOUT = 300  # 5 minutes
    
    # Celery Configuration
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', REDIS_URL)
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', REDIS_URL)
    CELERY_TIMEZONE = 'Asia/Kolkata'
    
    # Storage paths
    EXPORTS_FOLDER = os.path.join(BASE_DIR, 'backend', 'exports')
    REPORTS_FOLDER = os.path.join(BASE_DIR, 'backend', 'reports')
