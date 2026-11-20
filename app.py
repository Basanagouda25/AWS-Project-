"""
Application Entry Point
Automated Image Preprocessing System Using AWS

Run locally via:
    python app.py
Serves application on http://127.0.0.1:5000
"""

import os
from app import create_app
from config import get_config

# Create application using environment-defined configuration
config_obj = get_config()
app = create_app(config_class=config_obj)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '127.0.0.1')
    debug_mode = app.config.get('DEBUG', True)

    print(f" * Starting Automated Image Preprocessing Server")
    print(f" * Environment: {os.environ.get('FLASK_ENV', 'development')}")
    print(f" * Target AWS Region: {app.config.get('AWS_REGION')}")
    print(f" * Listening on http://{host}:{port}")

    app.run(host=host, port=port, debug=debug_mode)

