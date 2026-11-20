"""
Application Factory for Automated Image Preprocessing System Using AWS
"""

import os
from flask import Flask, jsonify
from config import get_config


def create_app(config_class=None):
    """
    Flask Application Factory.
    Initializes and configures the Flask application.
    """
    # Initialize Flask app pointing to root-level templates and static folders
    base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    template_dir = os.path.join(base_dir, 'templates')
    static_dir = os.path.join(base_dir, 'static')

    app = Flask(
        __name__,
        template_folder=template_dir,
        static_folder=static_dir
    )

    # Load configuration
    if config_class is None:
        config_class = get_config()
    app.config.from_object(config_class)

    # Ensure upload directory exists
    upload_folder = app.config.get('UPLOAD_FOLDER')
    if upload_folder:
        os.makedirs(upload_folder, exist_ok=True)

    # Register blueprints
    from app.routes import main_bp
    app.register_blueprint(main_bp)

    # Register error handlers
    register_error_handlers(app)

    return app


def register_error_handlers(app):
    """Register HTTP error handlers for consistent API and HTML responses."""

    @app.errorhandler(400)
    def bad_request_error(error):
        return jsonify({
            "status": "error",
            "message": getattr(error, 'description', "Bad request")
        }), 400

    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({
            "status": "error",
            "message": "Resource not found",
            "code": 404
        }), 404

    @app.errorhandler(413)
    def request_entity_too_large(error):
        return jsonify({
            "status": "error",
            "message": "File size exceeds maximum limit of 10 MB"
        }), 413

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            "status": "error",
            "message": "Internal server error",
            "code": 500
        }), 500
