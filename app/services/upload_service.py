"""
Upload Service Module
Handles file validation, Pillow image verification, UUID generation,
and storage orchestration supporting both local and AWS S3 backends.
"""

import os
import uuid
import logging
from io import BytesIO
from typing import Optional, Dict, Any, Tuple
from werkzeug.utils import secure_filename
from PIL import Image, UnidentifiedImageError

from app.services.s3_storage_service import s3_storage_service, S3StorageService
from app.services.database_service import database_service, DatabaseService

logger = logging.getLogger(__name__)


class UploadValidationError(Exception):
    """Custom exception raised when upload validation fails."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class UploadService:
    """Service class for handling secure image ingestion, validation, and storage routing."""

    DEFAULT_ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}
    DEFAULT_ALLOWED_MIMES = {'image/jpeg', 'image/png'}
    DEFAULT_MAX_SIZE = 10 * 1024 * 1024  # 10 MB

    @staticmethod
    def validate_image_content(
        file,
        max_size: Optional[int] = None,
        allowed_extensions: Optional[set] = None,
        allowed_mimes: Optional[set] = None
    ) -> Dict[str, Any]:
        """
        Performs thorough validation on the uploaded file:
        - Presence & non-empty filename
        - Sanitization & extension verification (.jpg, .jpeg, .png)
        - MIME-type verification
        - Size bounds enforcement (0 < size <= max_size)
        - Pillow image integrity verification and dimension extraction

        :return: Dictionary containing validated image stream and metadata.
        """
        if max_size is None:
            max_size = UploadService.DEFAULT_MAX_SIZE
        if allowed_extensions is None:
            allowed_extensions = UploadService.DEFAULT_ALLOWED_EXTENSIONS
        if allowed_mimes is None:
            allowed_mimes = UploadService.DEFAULT_ALLOWED_MIMES

        # 1. Check file existence
        if file is None or not hasattr(file, 'filename'):
            logger.warning("Upload rejected: File object is missing")
            raise UploadValidationError("No file selected", status_code=400)

        raw_filename = file.filename or ""
        if not raw_filename.strip():
            logger.warning("Upload rejected: Empty filename received")
            raise UploadValidationError("No file selected", status_code=400)

        # 2. Sanitize filename & check extension
        sanitized_filename = secure_filename(raw_filename)
        if not sanitized_filename or '.' not in sanitized_filename:
            logger.warning("Upload rejected: Unsafe or extensionless filename '%s'", raw_filename)
            raise UploadValidationError("Only JPG, JPEG and PNG images are allowed", status_code=400)

        ext = sanitized_filename.rsplit('.', 1)[-1].lower()
        if ext not in allowed_extensions:
            logger.warning("Upload rejected: Unsupported extension '.%s'", ext)
            raise UploadValidationError("Only JPG, JPEG and PNG images are allowed", status_code=400)

        # 3. Validate MIME type
        mimetype = (file.mimetype or "").lower().strip()
        if mimetype not in allowed_mimes:
            logger.warning("Upload rejected: Invalid MIME type '%s'", mimetype)
            raise UploadValidationError("Only JPG, JPEG and PNG images are allowed", status_code=400)

        # 4. Read file content and check file size
        file.seek(0)
        content = file.read()
        file_size = len(content)

        if file_size == 0:
            logger.warning("Upload rejected: 0 byte empty file")
            raise UploadValidationError("Uploaded file is empty", status_code=400)

        if file_size > max_size:
            logger.warning("Upload rejected: File size %d exceeds limit of %d bytes", file_size, max_size)
            raise UploadValidationError("File size exceeds maximum limit of 10 MB", status_code=413)

        # 5. Content verification using Pillow (PIL)
        try:
            # First pass: verify file structure and integrity
            verify_stream = BytesIO(content)
            with Image.open(verify_stream) as img:
                img.verify()

            # Second pass: read format and dimensions
            inspect_stream = BytesIO(content)
            with Image.open(inspect_stream) as img:
                img_format = img.format.upper() if img.format else ""
                width, height = img.size

        except (UnidentifiedImageError, IOError, SyntaxError, Exception) as err:
            logger.warning("Upload rejected: Pillow failed to decode image content: %s", str(err))
            raise UploadValidationError("Corrupted or invalid image file", status_code=400)

        # Format enforcement
        if img_format not in {'JPEG', 'PNG'}:
            logger.warning("Upload rejected: Decoded format '%s' not in supported list", img_format)
            raise UploadValidationError("Only JPG, JPEG and PNG images are allowed", status_code=400)

        return {
            "content": content,
            "filename": sanitized_filename,
            "ext": ext,
            "mimetype": mimetype,
            "img_format": img_format,
            "width": width,
            "height": height,
            "size": file_size
        }

    @staticmethod
    def save_local(validated_data: Dict[str, Any], upload_folder: str) -> Dict[str, Any]:
        """
        Saves the validated image to local storage (instance/uploads/) using a UUID filename.
        Enforces path traversal protection and duplicate prevention.
        """
        image_id = str(uuid.uuid4())
        ext = validated_data["ext"]
        normalized_ext = 'jpg' if ext in ('jpg', 'jpeg') else 'png'
        unique_filename = f"{image_id}.{normalized_ext}"

        abs_upload_folder = os.path.abspath(upload_folder)
        os.makedirs(abs_upload_folder, exist_ok=True)

        destination_path = os.path.abspath(os.path.join(abs_upload_folder, unique_filename))

        # Path traversal guard
        if not destination_path.startswith(abs_upload_folder + os.sep):
            logger.error("Security alert: Attempted path traversal for file '%s'", unique_filename)
            raise UploadValidationError("Security violation: Invalid storage path", status_code=400)

        # Prevent overwriting if UUID already exists
        if os.path.exists(destination_path):
            unique_filename = f"{image_id}_{uuid.uuid4().hex[:8]}.{normalized_ext}"
            destination_path = os.path.abspath(os.path.join(abs_upload_folder, unique_filename))

        # Write to disk
        with open(destination_path, 'wb') as dest_file:
            dest_file.write(validated_data["content"])

        logger.info(
            "Image successfully stored locally: id=%s original='%s' stored='%s' size=%d bytes dimensions=%dx%d",
            image_id, validated_data["filename"], unique_filename,
            validated_data["size"], validated_data["width"], validated_data["height"]
        )

        return {
            "image_id": image_id,
            "filename": validated_data["filename"],
            "stored_filename": unique_filename,
            "size": validated_data["size"],
            "format": validated_data["img_format"],
            "width": validated_data["width"],
            "height": validated_data["height"],
            "upload_status": "LOCAL_UPLOAD_COMPLETED",
            "storage_backend": "local"
        }

    @staticmethod
    def validate_and_save(
        file,
        upload_folder: str,
        max_size: Optional[int] = None,
        allowed_extensions: Optional[set] = None,
        allowed_mimes: Optional[set] = None
    ) -> Dict[str, Any]:
        """
        Module 2 backward-compatible method for validating and saving locally.
        """
        validated = UploadService.validate_image_content(
            file=file,
            max_size=max_size,
            allowed_extensions=allowed_extensions,
            allowed_mimes=allowed_mimes
        )
        return UploadService.save_local(validated, upload_folder)

    @staticmethod
    def process_upload(
        file,
        storage_backend: str = 'local',
        upload_folder: str = 'instance/uploads',
        s3_bucket: Optional[str] = None,
        s3_prefix: str = 'uploads/',
        s3_expiry: int = 3600,
        s3_service: Optional[S3StorageService] = None,
        db_service: Optional[DatabaseService] = None,
        max_size: Optional[int] = None,
        allowed_extensions: Optional[set] = None,
        allowed_mimes: Optional[set] = None
    ) -> Dict[str, Any]:
        """
        Unified upload processing method supporting both 'local' and 's3' storage backends.
        Validates the image first, then routes to the selected storage provider.
        When backend is 's3', creates a database record with status 'PENDING' before
        uploading to S3, and updates to 'FAILED' if the S3 upload encounters an error.
        """
        # Validate file before any storage operation
        validated = UploadService.validate_image_content(
            file=file,
            max_size=max_size,
            allowed_extensions=allowed_extensions,
            allowed_mimes=allowed_mimes
        )

        backend = (storage_backend or 'local').strip().lower()

        if backend == 's3':
            active_s3_service = s3_service or s3_storage_service
            active_db_service = db_service or database_service

            image_id = str(uuid.uuid4())
            _, unique_filename, s3_key = active_s3_service.generate_object_key(
                ext=validated["ext"],
                prefix=s3_prefix,
                image_id=image_id
            )

            # Persist record in RDS with PENDING status BEFORE initiating S3 upload
            # Ensures Lambda cannot receive an S3 event before the database record exists
            if active_db_service and active_db_service.is_configured():
                try:
                    active_db_service.create_image_record({
                        "image_id": image_id,
                        "original_filename": validated["filename"],
                        "bucket_name": s3_bucket or "",
                        "original_s3_key": s3_key,
                        "original_format": validated["img_format"],
                        "original_width": validated["width"],
                        "original_height": validated["height"],
                        "original_size_bytes": validated["size"],
                        "content_type": validated["mimetype"],
                        "processing_status": "PENDING"
                    })
                except Exception as db_err:
                    logger.error("Failed to persist initial PENDING image record in MySQL: %s", str(db_err))
                    raise

            try:
                s3_result = active_s3_service.upload_image(
                    file_content=validated["content"],
                    filename=validated["filename"],
                    content_type=validated["mimetype"],
                    bucket_name=s3_bucket,
                    prefix=s3_prefix,
                    expiry=s3_expiry,
                    image_id=image_id
                )
            except Exception as upload_err:
                if active_db_service and active_db_service.is_configured():
                    try:
                        active_db_service.update_image_record(image_id, {
                            "processing_status": "FAILED",
                            "error_message": f"S3 upload error: {str(upload_err)}"
                        })
                    except Exception as status_err:
                        logger.error("Failed to update status to FAILED after S3 failure: %s", str(status_err))
                raise

            # Augment result with image metadata and processing status
            s3_result["width"] = validated["width"]
            s3_result["height"] = validated["height"]
            s3_result["format"] = validated["img_format"]
            s3_result["processing_status"] = "PENDING"
            return s3_result

        # Default: local storage
        return UploadService.save_local(validated, upload_folder)


upload_service = UploadService()
