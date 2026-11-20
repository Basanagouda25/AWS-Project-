"""
Application Routes Definition
Contains route endpoints for web interface, health diagnostics, and image upload API.
Supports both local and AWS S3 cloud storage backends.
"""

from flask import Blueprint, jsonify, render_template, request, current_app
from app.services.upload_service import upload_service, UploadValidationError
from app.services.s3_storage_service import (
    S3StorageError,
    S3ConfigurationError,
    S3AuthenticationError,
    S3AccessDeniedError,
    S3BucketNotFoundError,
    S3ServiceUnavailableError
)
from app.services.database_service import (
    database_service,
    DatabaseError,
    DatabaseConnectionError
)
from app.services.s3_storage_service import s3_storage_service

main_bp = Blueprint('main', __name__)


@main_bp.route('/', methods=['GET'])
@main_bp.route('/dashboard', methods=['GET'])
def index():
    """
    Landing page route.
    Renders modern dashboard showcasing project status, upload interface, and AWS architecture.
    """
    storage_backend = current_app.config.get('STORAGE_BACKEND', 'local').lower()
    s3_bucket = current_app.config.get('S3_BUCKET_NAME') or current_app.config.get('S3_BUCKET', '')

    context = {
        'project_title': 'Automated Image Preprocessing System Using AWS',
        'module_title': 'Module 1: Project Foundation Completed',
        'module2_title': 'Module 2: Image Ingestion & Upload Interface Completed',
        'module3_title': 'Module 3: AWS S3 Cloud Storage Integration Completed',
        'module4_title': 'Module 4: AWS Lambda Automated Preprocessing Active',
        'module5_title': 'Module 5: Amazon RDS MySQL Database Connected',
        'module6_title': 'Module 6: Dashboard & Processing Results Active',
        'backend_status': 'Running',
        'storage_backend': storage_backend,
        's3_bucket': s3_bucket,
        'aws_region': current_app.config.get('AWS_REGION', 'ap-south-1'),
        'environment': 'Development' if current_app.config.get('DEBUG') else 'Production',
        'max_file_size_mb': int(current_app.config.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024) / (1024 * 1024))
    }
    return render_template('index.html', **context)


@main_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check diagnostic endpoint.
    Returns JSON status confirming API readiness and individual service health.
    """
    db_status = database_service.check_health()
    return jsonify({
        "status": "success",
        "message": "Image Preprocessing API is running",
        "services": {
            "flask": "healthy",
            "database": db_status
        }
    }), 200


@main_bp.route('/api/upload', methods=['POST'])
def upload_image():
    """
    Image Upload Endpoint (Module 2 & 3).
    Validates uploaded image and stores it locally or in AWS S3 based on STORAGE_BACKEND.
    """
    # 1. Check if the 'image' field is present in the multipart request
    if 'image' not in request.files:
        current_app.logger.warning("Upload rejected: 'image' form key missing")
        return jsonify({
            "success": False,
            "status": "error",
            "message": "No file selected"
        }), 400

    file = request.files['image']

    # 2. Check if user submitted an empty field
    if not file or not file.filename or file.filename.strip() == '':
        current_app.logger.warning("Upload rejected: Empty filename received")
        return jsonify({
            "success": False,
            "status": "error",
            "message": "No file selected"
        }), 400

    try:
        storage_backend = current_app.config.get('STORAGE_BACKEND', 'local').lower()
        upload_folder = current_app.config.get('UPLOAD_FOLDER')
        max_size = current_app.config.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024)
        allowed_exts = current_app.config.get('ALLOWED_EXTENSIONS', {'jpg', 'jpeg', 'png'})
        allowed_mimes = current_app.config.get('ALLOWED_MIME_TYPES', {'image/jpeg', 'image/png'})

        s3_bucket = current_app.config.get('S3_BUCKET_NAME') or current_app.config.get('S3_BUCKET')
        s3_prefix = current_app.config.get('S3_OBJECT_PREFIX', 'uploads/')
        s3_expiry = current_app.config.get('S3_PRESIGNED_URL_EXPIRY', 3600)

        # Execute upload through unified upload service
        result = upload_service.process_upload(
            file=file,
            storage_backend=storage_backend,
            upload_folder=upload_folder,
            s3_bucket=s3_bucket,
            s3_prefix=s3_prefix,
            s3_expiry=s3_expiry,
            max_size=max_size,
            allowed_extensions=allowed_exts,
            allowed_mimes=allowed_mimes
        )

        # Format response according to backend
        if storage_backend == 's3':
            return jsonify({
                "success": True,
                "status": "success",
                "message": "Image uploaded successfully to AWS S3",
                "image_id": result.get("image_id"),
                "storage_backend": "s3",
                "filename": result["filename"],
                "s3_key": result["s3_key"],
                "presigned_url": result["presigned_url"],
                "upload_status": "S3_UPLOAD_COMPLETED",
                "processing_status": result.get("processing_status", "PENDING"),
                "data": result
            }), 200

        # Local storage response (retaining Module 2 compatibility)
        return jsonify({
            "success": True,
            "status": "success",
            "message": "Image uploaded successfully",
            "storage_backend": "local",
            "filename": result["filename"],
            "data": result
        }), 200

    except UploadValidationError as val_err:
        current_app.logger.warning("Upload validation failed: %s", val_err.message)
        return jsonify({
            "success": False,
            "status": "error",
            "message": val_err.message
        }), val_err.status_code

    except S3ConfigurationError as cfg_err:
        current_app.logger.error("S3 configuration error: %s", cfg_err.message)
        return jsonify({
            "success": False,
            "status": "error",
            "message": cfg_err.message
        }), cfg_err.status_code

    except S3AuthenticationError as auth_err:
        current_app.logger.error("S3 authentication error: %s", auth_err.message)
        return jsonify({
            "success": False,
            "status": "error",
            "message": auth_err.message
        }), auth_err.status_code

    except S3AccessDeniedError as acc_err:
        current_app.logger.error("S3 access denied: %s", acc_err.message)
        return jsonify({
            "success": False,
            "status": "error",
            "message": acc_err.message
        }), acc_err.status_code

    except S3BucketNotFoundError as bkt_err:
        current_app.logger.error("S3 bucket not found: %s", bkt_err.message)
        return jsonify({
            "success": False,
            "status": "error",
            "message": bkt_err.message
        }), bkt_err.status_code

    except S3ServiceUnavailableError as srv_err:
        current_app.logger.error("S3 service unavailable: %s", srv_err.message)
        return jsonify({
            "success": False,
            "status": "error",
            "message": srv_err.message
        }), srv_err.status_code

    except S3StorageError as s3_err:
        current_app.logger.error("S3 storage error: %s", s3_err.message)
        return jsonify({
            "success": False,
            "status": "error",
            "message": s3_err.message
        }), s3_err.status_code

    except DatabaseConnectionError as conn_err:
        current_app.logger.error("Database connection failure: %s", conn_err.message)
        return jsonify({
            "success": False,
            "status": "error",
            "message": "Database connection error: Unable to connect to metadata store"
        }), 500

    except DatabaseError as db_err:
        current_app.logger.error("Database error during upload: %s", db_err.message)
        return jsonify({
            "success": False,
            "status": "error",
            "message": "Database error: Failed to record image metadata"
        }), 500

    except Exception as err:
        current_app.logger.error("Unexpected server exception during upload: %s", str(err), exc_info=True)
        return jsonify({
            "success": False,
            "status": "error",
            "message": "An unexpected server error occurred during upload processing"
        }), 500


# ==============================================================================
# Module 6: Dashboard Statistics & Processing Results APIs
# ==============================================================================

def calculate_size_reduction(original_size, processed_size):
    """
    Calculates file size reduction percentage:
    Formula: ((Original Size - Processed Size) / Original Size) * 100
    Handles cases where processed image is larger without false savings.
    """
    if original_size is None or processed_size is None or original_size <= 0:
        return None
    diff = original_size - processed_size
    pct = round((diff / original_size) * 100, 2)
    return {
        "bytes_saved": diff,
        "percentage": pct,
        "is_reduction": diff > 0,
        "is_larger": diff < 0
    }


@main_bp.route('/api/dashboard/stats', methods=['GET'])
def get_dashboard_stats():
    """
    Dashboard summary statistics endpoint.
    Returns counts for total_images, completed, pending, processing, and failed.
    """
    try:
        stats = database_service.get_dashboard_statistics()
        return jsonify({
            "success": True,
            "status": "success",
            "data": stats
        }), 200
    except DatabaseError as err:
        current_app.logger.error("Failed to fetch dashboard statistics: %s", err.message)
        return jsonify({
            "success": False,
            "status": "error",
            "message": "Database error while fetching statistics"
        }), 500
    except Exception as err:
        current_app.logger.error("Unexpected error in dashboard stats: %s", str(err))
        return jsonify({
            "success": False,
            "status": "error",
            "message": "Internal server error fetching dashboard statistics"
        }), 500


@main_bp.route('/api/images', methods=['GET'])
def list_images():
    """
    Paginated image listing endpoint.
    Query parameters:
        page: int >= 1 (default 1)
        per_page: int between 1 and 100 (default 10)
    Returns list of image records sorted newest first with pagination metadata.
    """
    page_param = request.args.get('page', 1)
    per_page_param = request.args.get('per_page', 10)

    try:
        page = int(page_param)
        per_page = int(per_page_param)
        if page < 1 or per_page < 1 or per_page > 100:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "status": "error",
            "message": "Invalid pagination parameters"
        }), 400

    try:
        result = database_service.get_images_paginated(page=page, per_page=per_page)
        records = result.get("records", [])

        # Enrich records with preview URLs
        s3_bucket = current_app.config.get('S3_BUCKET_NAME') or current_app.config.get('S3_BUCKET')
        enriched_records = []
        for rec in records:
            bucket = rec.get('bucket_name') or s3_bucket
            orig_key = rec.get('original_s3_key')
            proc_key = rec.get('processed_s3_key')
            status = rec.get('processing_status')

            rec_copy = dict(rec)
            rec_copy['original_url'] = s3_storage_service.get_preview_url(bucket, orig_key)
            if status == 'COMPLETED' and proc_key:
                rec_copy['processed_url'] = s3_storage_service.get_preview_url(bucket, proc_key)
            else:
                rec_copy['processed_url'] = None

            rec_copy['reduction'] = calculate_size_reduction(
                rec.get('original_size_bytes'),
                rec.get('processed_size_bytes')
            )
            enriched_records.append(rec_copy)

        return jsonify({
            "success": True,
            "status": "success",
            "data": {
                "images": enriched_records,
                "pagination": result.get("pagination", {})
            }
        }), 200

    except DatabaseError as err:
        current_app.logger.error("Failed to fetch image records: %s", err.message)
        return jsonify({
            "success": False,
            "status": "error",
            "message": "Database error while fetching image records"
        }), 500
    except Exception as err:
        current_app.logger.error("Unexpected error in list_images: %s", str(err))
        return jsonify({
            "success": False,
            "status": "error",
            "message": "Internal server error fetching image records"
        }), 500


@main_bp.route('/api/images/<image_id>', methods=['GET'])
def get_image_detail(image_id):
    """
    Image metadata and comparison endpoint.
    Retrieves full image record, generates presigned URLs for original and processed objects,
    and calculates file size reduction percentage.
    """
    if not image_id or not image_id.strip():
        return jsonify({
            "success": False,
            "status": "error",
            "message": "Invalid image identifier"
        }), 400

    try:
        record = database_service.get_image_details(image_id.strip())
        if not record:
            return jsonify({
                "success": False,
                "status": "error",
                "message": "Image record not found"
            }), 404

        s3_bucket = record.get('bucket_name') or current_app.config.get('S3_BUCKET_NAME') or current_app.config.get('S3_BUCKET')
        orig_key = record.get('original_s3_key')
        proc_key = record.get('processed_s3_key')
        status = record.get('processing_status')

        data = dict(record)
        data['original_url'] = s3_storage_service.get_preview_url(s3_bucket, orig_key)
        if status == 'COMPLETED' and proc_key:
            data['processed_url'] = s3_storage_service.get_preview_url(s3_bucket, proc_key)
        else:
            data['processed_url'] = None

        data['reduction'] = calculate_size_reduction(
            record.get('original_size_bytes'),
            record.get('processed_size_bytes')
        )

        return jsonify({
            "success": True,
            "status": "success",
            "data": data
        }), 200

    except DatabaseError as err:
        current_app.logger.error("Database error fetching image %s: %s", image_id, err.message)
        return jsonify({
            "success": False,
            "status": "error",
            "message": "Database error while fetching image details"
        }), 500
    except Exception as err:
        current_app.logger.error("Unexpected error fetching image %s: %s", image_id, str(err))
        return jsonify({
            "success": False,
            "status": "error",
            "message": "Internal server error fetching image details"
        }), 500
