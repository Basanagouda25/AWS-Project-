"""
WSGI Production Entry Point
Automated Image Preprocessing System Using AWS - Module 7

This module serves as the production WSGI application interface for Gunicorn.
It instantiates the Flask application with the production configuration class
and ensures debug mode is strictly disabled.

Usage with Gunicorn:
    gunicorn --config deployment/gunicorn.conf.py wsgi:app
"""

import os
from app import create_app
from config import get_config

# Ensure production configuration is strictly used for WSGI server
env_name = os.getenv('WSGI_ENV', os.getenv('FLASK_ENV', 'production')).lower()
# For production WSGI entry point, use ProductionConfig unless in testing
if env_name == 'testing':
    from config import TestingConfig
    config_class = TestingConfig
else:
    from config import ProductionConfig
    config_class = ProductionConfig

# Instantiate application factory
app = create_app(config_class=config_class)

# Ensure debug mode is strictly disabled in production WSGI
app.config['DEBUG'] = False
app.debug = False

if __name__ == '__main__':
    # Local fallback for direct python wsgi.py invocation
    port = int(os.environ.get('PORT', 8000))
    host = os.environ.get('HOST', '127.0.0.1')
    app.run(host=host, port=port, debug=False)
