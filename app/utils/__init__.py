"""
Utilities Package
Helper functions for validation, file handling, and response formatting.
"""

from typing import Any, Dict, Optional
from flask import jsonify


def api_response(status: str, message: str, data: Optional[Dict[str, Any]] = None, code: int = 200):
    """Standardized JSON API response structure."""
    payload = {
        "status": status,
        "message": message
    }
    if data is not None:
        payload["data"] = data
    return jsonify(payload), code


def allowed_file(filename: str, allowed_extensions: set) -> bool:
    """Check if the provided filename has an approved extension."""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in allowed_extensions

