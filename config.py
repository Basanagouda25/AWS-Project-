"""
Configuration Management Module
Automated Image Preprocessing System Using AWS

Loads environment variables from .env file using python-dotenv.
Provides configuration classes for different execution environments.
Supports dual storage backends ('local' and 's3') and Amazon RDS MySQL integration.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Load .env file if it exists
env_path = BASE_DIR / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()


class Config:
    """Base configuration class with default values and environment fallbacks."""

    # Flask Core
    SECRET_KEY = os.getenv('SECRET_KEY', 'default-dev-secret-key-change-in-production')
    DEBUG = False
    TESTING = False

    # Storage Backend Selection: 'local' (default) or 's3'
    STORAGE_BACKEND = os.getenv('STORAGE_BACKEND', 'local').strip().lower()

    # AWS S3 Configuration
    # Default AWS Region is ap-south-1 (Mumbai) as required
    AWS_REGION = os.getenv('AWS_REGION', 'ap-south-1')
    S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME') or os.getenv('S3_BUCKET', 'aws-image-preprocessing-bucket')
    S3_BUCKET = S3_BUCKET_NAME  # Backward compatibility alias
    S3_PRESIGNED_URL_EXPIRY = int(os.getenv('S3_PRESIGNED_URL_EXPIRY', 3600))
    S3_OBJECT_PREFIX = os.getenv('S3_OBJECT_PREFIX', 'uploads/')

    # Optional explicit AWS credentials (AWS credential chain is preferred)
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', '') or None
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', '') or None

    # Amazon RDS MySQL Database Configuration (Module 5)
    DB_HOST = os.getenv('DB_HOST', '')
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    DB_USER = os.getenv('DB_USER', 'admin')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_NAME = os.getenv('DB_NAME', 'image_preprocessing')
    DB_CONNECT_TIMEOUT = int(os.getenv('DB_CONNECT_TIMEOUT', 10))

    # Uploads Configuration
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'instance', 'uploads')
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB maximum file size limit
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png'}


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True


class TestingConfig(Config):
    """Testing environment configuration."""
    TESTING = True
    DEBUG = True
    SECRET_KEY = 'testing-secret-key'
    STORAGE_BACKEND = 'local'
    S3_BUCKET_NAME = 'test-image-bucket'
    S3_BUCKET = 'test-image-bucket'
    S3_PRESIGNED_URL_EXPIRY = 3600
    S3_OBJECT_PREFIX = 'uploads/'
    DB_HOST = None
    DB_PORT = 3306
    DB_USER = 'test_user'
    DB_PASSWORD = 'test_password'
    DB_NAME = 'test_image_preprocessing'
    DB_CONNECT_TIMEOUT = 5
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'instance', 'test_uploads')
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024


class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG = False
    TESTING = False


# Configuration mapping
config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config(config_name=None):
    """Retrieve the configuration class by environment name or default to development."""
    if not config_name:
        config_name = os.getenv('FLASK_ENV', 'development').lower()
    return config_by_name.get(config_name, DevelopmentConfig)
