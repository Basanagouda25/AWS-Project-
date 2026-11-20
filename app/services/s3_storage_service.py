"""
AWS S3 Cloud Storage Service
Automated Image Preprocessing System Using AWS

Handles secure uploads of validated images to Amazon S3 bucket (ap-south-1 Mumbai)
and generates time-limited presigned GET URLs with private bucket access.
"""

import os
import uuid
import logging
from typing import Optional, Dict, Any

from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    PartialCredentialsError,
    EndpointConnectionError,
    ParamValidationError
)

logger = logging.getLogger(__name__)


class S3StorageError(Exception):
    """Base exception for S3 storage failures."""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class S3ConfigurationError(S3StorageError):
    """Raised when S3 bucket or configuration is missing."""
    def __init__(self, message: str = "AWS S3 bucket is not configured"):
        super().__init__(message, status_code=500)


class S3AuthenticationError(S3StorageError):
    """Raised when AWS credentials are missing, invalid, or expired."""
    def __init__(self, message: str = "AWS credentials error: Unable to authenticate with AWS S3"):
        super().__init__(message, status_code=500)


class S3AccessDeniedError(S3StorageError):
    """Raised when S3 bucket access is forbidden (403)."""
    def __init__(self, message: str = "Access denied to AWS S3 bucket"):
        super().__init__(message, status_code=403)


class S3BucketNotFoundError(S3StorageError):
    """Raised when S3 bucket does not exist (404)."""
    def __init__(self, message: str = "AWS S3 bucket not found"):
        super().__init__(message, status_code=404)


class S3ServiceUnavailableError(S3StorageError):
    """Raised when AWS service or network endpoint cannot be reached."""
    def __init__(self, message: str = "AWS S3 service is currently unavailable"):
        super().__init__(message, status_code=503)


class S3StorageService:
    """Service class for Amazon S3 object ingestion and presigned URL generation."""

    def __init__(self, region_name: str = 'ap-south-1', client=None):
        self.region_name = region_name
        self._client = client

    def get_client(self):
        """Lazy initialization of Boto3 S3 client to avoid credential checks at startup."""
        if self._client is not None:
            return self._client

        import boto3
        from botocore.config import Config as BotoConfig

        boto_cfg = BotoConfig(
            region_name=self.region_name,
            signature_version='s3v4',
            retries={'max_attempts': 3, 'mode': 'standard'}
        )
        self._client = boto3.client('s3', region_name=self.region_name, config=boto_cfg)
        return self._client

    def set_client(self, client):
        """Allows injecting a mock or stubbed Boto3 client for isolated unit tests."""
        self._client = client

    def generate_object_key(self, ext: str, prefix: str = 'uploads/', image_id: Optional[str] = None) -> tuple[str, str, str]:
        """
        Generates a secure UUID4-based filename and S3 object key.
        Returns (image_id, unique_filename, s3_key).
        """
        if not image_id:
            image_id = str(uuid.uuid4())
        normalized_ext = 'jpg' if ext.lower() in ('jpg', 'jpeg') else 'png'
        unique_filename = f"{image_id}.{normalized_ext}"
        
        # Ensure prefix ends with a slash and has no leading slash
        clean_prefix = prefix.strip('/')
        if clean_prefix:
            s3_key = f"{clean_prefix}/{unique_filename}"
        else:
            s3_key = unique_filename

        return image_id, unique_filename, s3_key

    def generate_presigned_url(self, bucket_name: str, s3_key: str, expiry: int = 3600) -> str:
        """
        Generates a temporary presigned GET URL for secure, time-limited read access.
        Never makes the object or bucket publicly accessible.
        """
        client = self.get_client()
        return client.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': bucket_name,
                'Key': s3_key
            },
            ExpiresIn=expiry
        )

    def get_preview_url(self, bucket_name: Optional[str], s3_key: Optional[str], expiry: int = 3600) -> Optional[str]:
        """
        Safely generates a presigned GET URL for image preview.
        Returns None if key is missing or if S3 client encounters an error.
        """
        if not bucket_name or not s3_key:
            return None
        try:
            return self.generate_presigned_url(bucket_name=bucket_name, s3_key=s3_key, expiry=expiry)
        except Exception as err:
            logger.warning("Could not generate presigned preview URL for s3://%s/%s: %s", bucket_name, s3_key, str(err))
            return None

    def upload_image(
        self,
        file_content: bytes,
        filename: str,
        content_type: str,
        bucket_name: Optional[str],
        prefix: str = 'uploads/',
        expiry: int = 3600,
        image_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Uploads validated image bytes directly to AWS S3 and creates a presigned URL.

        :param file_content: In-memory image bytes.
        :param filename: Original or sanitized filename (used for extension extraction).
        :param content_type: Verified MIME type ('image/jpeg' or 'image/png').
        :param bucket_name: Target S3 bucket name.
        :param prefix: Key prefix (default 'uploads/').
        :param expiry: Presigned URL validity duration in seconds (default 3600).
        :param image_id: Optional predefined UUID for the image record.
        :return: Dictionary containing S3 upload details and presigned URL.
        """
        if not bucket_name or not str(bucket_name).strip():
            logger.error("S3 upload failed: S3_BUCKET_NAME is not configured")
            raise S3ConfigurationError("AWS S3 bucket is not configured")

        # Extract extension
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'jpg'
        image_id, unique_filename, s3_key = self.generate_object_key(ext=ext, prefix=prefix, image_id=image_id)

        client = self.get_client()

        # Upload image to S3 (Private object, NO public-read ACL)
        try:
            logger.info("Uploading %d bytes to s3://%s/%s (ContentType=%s)",
                        len(file_content), bucket_name, s3_key, content_type)
            client.put_object(
                Bucket=bucket_name,
                Key=s3_key,
                Body=file_content,
                ContentType=content_type
            )
        except (NoCredentialsError, PartialCredentialsError) as err:
            logger.error("AWS credentials error during S3 put_object: %s", str(err))
            raise S3AuthenticationError()
        except EndpointConnectionError as err:
            logger.error("AWS endpoint unreachable: %s", str(err))
            raise S3ServiceUnavailableError()
        except ClientError as err:
            error_code = err.response.get('Error', {}).get('Code', '')
            logger.error("S3 ClientError [%s]: %s", error_code, str(err))
            if error_code in ('AccessDenied', 'AllAccessDisabled'):
                raise S3AccessDeniedError()
            elif error_code in ('NoSuchBucket', 'NotFound'):
                raise S3BucketNotFoundError()
            elif error_code in ('InvalidAccessKeyId', 'SignatureDoesNotMatch', 'ExpiredToken'):
                raise S3AuthenticationError()
            elif error_code in ('ServiceUnavailable', 'SlowDown'):
                raise S3ServiceUnavailableError()
            else:
                raise S3StorageError(f"AWS S3 error: {error_code or 'Upload failed'}")
        except BotoCoreError as err:
            logger.error("BotoCoreError during S3 upload: %s", str(err))
            raise S3ServiceUnavailableError()
        except (S3StorageError,):
            raise
        except Exception as err:
            logger.error("Unexpected error during S3 upload: %s", str(err), exc_info=True)
            raise S3StorageError("An unexpected error occurred while uploading to AWS S3")

        # Generate presigned GET URL
        try:
            presigned_url = self.generate_presigned_url(
                bucket_name=bucket_name,
                s3_key=s3_key,
                expiry=expiry
            )
        except (NoCredentialsError, PartialCredentialsError):
            raise S3AuthenticationError()
        except ClientError as err:
            error_code = err.response.get('Error', {}).get('Code', '')
            if error_code in ('AccessDenied',):
                raise S3AccessDeniedError()
            raise S3StorageError("Failed to generate presigned URL for uploaded image")
        except Exception as err:
            logger.error("Error generating presigned URL for %s: %s", s3_key, str(err))
            raise S3StorageError("Failed to generate presigned URL for uploaded image")

        return {
            "image_id": image_id,
            "filename": unique_filename,
            "original_filename": filename,
            "s3_key": s3_key,
            "presigned_url": presigned_url,
            "content_type": content_type,
            "size": len(file_content),
            "upload_status": "S3_UPLOAD_COMPLETED",
            "storage_backend": "s3"
        }


# Default singleton instance
s3_storage_service = S3StorageService()

