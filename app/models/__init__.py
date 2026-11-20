"""
Models Package
Data models and representations for image preprocessing jobs and metadata.
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class ImageRecord:
    """Represents an image asset tracked within the system (Module 3 integration)."""
    id: Optional[int] = None
    original_filename: str = ""
    s3_original_key: str = ""
    s3_processed_key: Optional[str] = None
    mime_type: str = ""
    file_size_bytes: int = 0
    status: str = "pending"  # pending, processing, completed, failed
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

