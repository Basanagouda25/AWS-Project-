"""
Services Package
Modular business logic and cloud integrations (S3, RDS, Lambda).
Decouples routing controllers from backend services and cloud SDKs.
"""

from app.services.upload_service import upload_service, UploadService, UploadValidationError
from app.services.s3_storage_service import (
    s3_storage_service,
    S3StorageService,
    S3StorageError,
    S3ConfigurationError,
    S3AuthenticationError,
    S3AccessDeniedError,
    S3BucketNotFoundError,
    S3ServiceUnavailableError
)
from app.services.database_service import (
    database_service,
    DatabaseService,
    DatabaseError,
    DatabaseConnectionError
)

__all__ = [
    'upload_service',
    'UploadService',
    'UploadValidationError',
    's3_storage_service',
    'S3StorageService',
    'S3StorageError',
    'S3ConfigurationError',
    'S3AuthenticationError',
    'S3AccessDeniedError',
    'S3BucketNotFoundError',
    'S3ServiceUnavailableError',
    'database_service',
    'DatabaseService',
    'DatabaseError',
    'DatabaseConnectionError'
]
