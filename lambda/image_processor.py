"""
AWS Lambda Function: Automated Image Preprocessing Pipeline with RDS Integration
Module 5: Automated Image Preprocessing System Using AWS

Triggered automatically by Amazon S3 ObjectCreated events on the 'uploads/' prefix.
1. Connects to Amazon RDS MySQL database.
2. Finds the image record by 'original_s3_key'.
3. Transitions record status to 'PROCESSING'.
4. Downloads raw image from S3.
5. Resizes to a maximum of 800x800, converts to JPEG (quality 80) via Pillow.
6. Uploads processed image to S3 'processed/' prefix.
7. Transitions record status to 'COMPLETED' with processed metadata and timestamp.
8. On failure, transitions record status to 'FAILED' with safe error message.
9. Ensures database and S3 resources are safely cleaned up.
"""

import io
import json
import logging
import os
import urllib.parse
import uuid
from typing import Optional, Dict, Any, Tuple

from PIL import Image, ImageOps, UnidentifiedImageError

# Configure structured logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Module Constants
MAX_WIDTH = 800
MAX_HEIGHT = 800
JPEG_QUALITY = 80
INPUT_PREFIX = 'uploads/'
OUTPUT_PREFIX = 'processed/'
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png'}

# S3 and DB singletons / injection hooks for unit testing
_s3_client = None
_db_connection = None
_db_connection_factory = None


def get_s3_client():
    """Retrieve or lazily initialize the Boto3 S3 client."""
    global _s3_client
    if _s3_client is None:
        import boto3
        _s3_client = boto3.client('s3')
    return _s3_client


def set_s3_client(client):
    """Inject a custom or mock Boto3 S3 client for automated testing."""
    global _s3_client
    _s3_client = client


def set_db_connection(conn):
    """Inject a mock database connection for automated unit testing."""
    global _db_connection
    _db_connection = conn


def set_db_connection_factory(factory):
    """Inject a custom connection factory callable for unit testing."""
    global _db_connection_factory
    _db_connection_factory = factory


def is_db_configured() -> bool:
    """Checks if RDS MySQL environment variables are configured."""
    host = os.getenv('DB_HOST', '').strip()
    if not host or 'your-rds-endpoint' in host.lower():
        return False
    return True


def get_db_connection():
    """
    Establishes a PyMySQL connection using environment variables,
    or returns an injected test mock.
    Never exposes passwords in log statements.
    """
    global _db_connection, _db_connection_factory
    if _db_connection_factory is not None:
        return _db_connection_factory()

    if _db_connection is not None:
        return _db_connection

    if not is_db_configured():
        logger.info("RDS Database is not configured in Lambda environment; skipping RDS operations.")
        return None

    import pymysql
    from pymysql.cursors import DictCursor

    host = os.getenv('DB_HOST')
    port = int(os.getenv('DB_PORT', 3306))
    user = os.getenv('DB_USER', 'admin')
    password = os.getenv('DB_PASSWORD', '')
    db_name = os.getenv('DB_NAME', 'image_preprocessing')
    timeout = int(os.getenv('DB_CONNECT_TIMEOUT', 5))

    try:
        logger.info("Connecting to MySQL at %s:%d, db=%s, user=%s", host, port, db_name, user)
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=db_name,
            connect_timeout=timeout,
            charset='utf8mb4',
            cursorclass=DictCursor,
            autocommit=False
        )
        return conn
    except Exception as db_err:
        logger.error("Failed to connect to RDS MySQL database: %s", str(db_err))
        raise


def find_image_record(conn, original_s3_key: str) -> Optional[Dict[str, Any]]:
    """
    Looks up image record in MySQL using the unique original_s3_key.
    Uses parameterized query.
    """
    sql = "SELECT `image_id`, `processing_status` FROM `image_records` WHERE `original_s3_key` = %s LIMIT 1;"
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (original_s3_key,))
        record = cursor.fetchone()
        return record
    except Exception as err:
        logger.error("Failed to query image_record for key '%s': %s", original_s3_key, str(err))
        raise
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass


def create_initial_record_if_missing(conn, bucket_name: str, original_s3_key: str) -> str:
    """
    Creates an initial database record if the record was not previously inserted
    (e.g., when ingested from local development or direct upload).
    """
    filename = os.path.basename(original_s3_key)
    base_name, ext = os.path.splitext(filename)
    try:
        uuid_obj = uuid.UUID(base_name)
        image_id = str(uuid_obj)
    except (ValueError, AttributeError):
        image_id = str(uuid.uuid4())

    img_format = ext.lstrip('.').upper() or 'UNKNOWN'
    sql = """
        INSERT INTO `image_records` (
            `image_id`, `original_filename`, `bucket_name`, `original_s3_key`,
            `original_format`, `processing_status`
        ) VALUES (%s, %s, %s, %s, %s, 'PROCESSING');
    """
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (image_id, filename, bucket_name, original_s3_key, img_format))
        conn.commit()
        logger.info("Created initial database record image_id=%s for key '%s'", image_id, original_s3_key)
        return image_id
    except Exception as err:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.warning("Could not insert initial record for key '%s': %s", original_s3_key, str(err))
        return image_id
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass


def update_db_status_processing(conn, original_s3_key: str) -> bool:
    """
    Updates record status to 'PROCESSING'.
    Guards against overwriting an already 'COMPLETED' status.
    """
    sql = """
        UPDATE `image_records`
        SET `processing_status` = 'PROCESSING'
        WHERE `original_s3_key` = %s AND `processing_status` != 'COMPLETED';
    """
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (original_s3_key,))
        conn.commit()
        rc = getattr(cursor, 'rowcount', 1)
        updated = (rc > 0) if isinstance(rc, int) else True
        logger.info("Database record updated to PROCESSING for key '%s'", original_s3_key)
        return updated
    except Exception as err:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error("Failed to update status to PROCESSING for '%s': %s", original_s3_key, str(err))
        raise
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass


def update_db_status_completed(
    conn,
    original_s3_key: str,
    processed_s3_key: str,
    processed_format: str,
    processed_width: int,
    processed_height: int,
    processed_size_bytes: int
) -> bool:
    """
    Updates record with processed image metadata, status 'COMPLETED', and processed timestamp.
    Uses parameterized query and commits transaction.
    """
    sql = """
        UPDATE `image_records`
        SET `processing_status` = 'COMPLETED',
            `processed_s3_key` = %s,
            `processed_format` = %s,
            `processed_width` = %s,
            `processed_height` = %s,
            `processed_size_bytes` = %s,
            `processed_at` = CURRENT_TIMESTAMP
        WHERE `original_s3_key` = %s;
    """
    params = (
        processed_s3_key,
        processed_format,
        processed_width,
        processed_height,
        processed_size_bytes,
        original_s3_key
    )
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        rc = getattr(cursor, 'rowcount', 1)
        updated = (rc > 0) if isinstance(rc, int) else True
        logger.info("Database record updated to COMPLETED for key '%s'", original_s3_key)
        return updated
    except Exception as err:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error("Failed to update status to COMPLETED for '%s': %s", original_s3_key, str(err))
        raise
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass


def update_db_status_failed(conn, original_s3_key: str, error_msg: str) -> bool:
    """
    Updates record status to 'FAILED' with safe error message.
    Guards against exposing internal secrets.
    """
    safe_error = str(error_msg)[:500] if error_msg else "Unknown image processing failure"
    sql = """
        UPDATE `image_records`
        SET `processing_status` = 'FAILED',
            `error_message` = %s
        WHERE `original_s3_key` = %s;
    """
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (safe_error, original_s3_key))
        conn.commit()
        rc = getattr(cursor, 'rowcount', 1)
        updated = (rc > 0) if isinstance(rc, int) else True
        logger.info("Database record updated to FAILED for key '%s'", original_s3_key)
        return updated
    except Exception as err:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error("Failed to update status to FAILED for '%s': %s", original_s3_key, str(err))
        return False
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass


def generate_processed_key(original_key: str, output_prefix: str = OUTPUT_PREFIX) -> str:
    """
    Generates a deterministic S3 object key for the processed image.
    Example: 'uploads/photo123.png' -> 'processed/photo123_processed.jpg'
    """
    filename = os.path.basename(original_key)
    base_name = os.path.splitext(filename)[0]
    clean_prefix = output_prefix.rstrip('/')
    return f"{clean_prefix}/{base_name}_processed.jpg"


def process_image_bytes(
    image_bytes: bytes,
    max_dimensions: Tuple[int, int] = (MAX_WIDTH, MAX_HEIGHT),
    quality: int = JPEG_QUALITY
) -> Tuple[bytes, Tuple[int, int], Tuple[int, int]]:
    """
    Opens, orients, composites, resizes, and converts image bytes to JPEG.

    :param image_bytes: Raw binary image stream.
    :param max_dimensions: Maximum (width, height) bounding box.
    :param quality: JPEG compression quality (0-100).
    :return: Tuple of (processed_jpeg_bytes, original_dimensions, processed_dimensions).
    """
    input_stream = io.BytesIO(image_bytes)
    with Image.open(input_stream) as img:
        original_dimensions = img.size  # (width, height)
        logger.info("Opened original image: format=%s, size=%s, mode=%s",
                    img.format, original_dimensions, img.mode)

        # 1. Correct EXIF orientation if metadata exists
        try:
            img = ImageOps.exif_transpose(img)
            logger.info("Applied EXIF orientation transposition if present")
        except Exception as exif_err:
            logger.warning("Could not apply EXIF orientation transposition: %s", str(exif_err))

        # 2. Handle transparency / alpha channels before JPEG conversion
        # JPEG has no alpha support, so composite onto a pure white background
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            logger.info("Compositing transparent image (mode %s) onto white background", img.mode)
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[3])  # Alpha channel as mask
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # 3. Resize with aspect ratio preserved (never enlarge smaller images)
        orig_w, orig_h = img.size
        if orig_w > max_dimensions[0] or orig_h > max_dimensions[1]:
            # Pillow's thumbnail preserves aspect ratio without enlargement
            img.thumbnail(max_dimensions, Image.Resampling.LANCZOS)
            logger.info("Resized image from %dx%d to %dx%d",
                        orig_w, orig_h, img.width, img.height)
        else:
            logger.info("Image (%dx%d) is within %dx%d bounds. No resizing required.",
                        orig_w, orig_h, max_dimensions[0], max_dimensions[1])

        processed_dimensions = img.size

        # 4. Save to in-memory buffer as JPEG with configured quality
        output_stream = io.BytesIO()
        img.save(output_stream, format='JPEG', quality=quality, optimize=True)
        processed_bytes = output_stream.getvalue()

    return processed_bytes, original_dimensions, processed_dimensions


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda entrypoint. Triggered by S3 ObjectCreated events.

    :param event: AWS event notification payload.
    :param context: Lambda runtime execution context.
    :return: Execution summary dictionary.
    """
    logger.info("AWS Lambda Image Processor invoked. Event summary: %s",
                json.dumps(event, default=str))

    # 1. Validate incoming event payload
    if not isinstance(event, dict) or 'Records' not in event or not event['Records']:
        logger.warning("Event contains no Records. Terminating execution early.")
        return {
            "statusCode": 400,
            "body": json.dumps({"message": "No Records found in event payload", "processed": []})
        }

    s3_client = get_s3_client()
    processed_records = []
    skipped_records = []

    # Initialize DB connection per invocation
    db_conn = None
    try:
        db_conn = get_db_connection()
    except Exception as conn_err:
        logger.error("Failed to establish DB connection in Lambda handler: %s", str(conn_err))
        raise

    try:
        for record in event['Records']:
            # Guard against non-S3 event records
            if 's3' not in record or 'bucket' not in record['s3'] or 'object' not in record['s3']:
                logger.warning("Skipping non-S3 or malformed record: %s", record)
                skipped_records.append({"reason": "Malformed S3 record"})
                continue

            bucket_name = record['s3']['bucket'].get('name')
            raw_key = record['s3']['object'].get('key', '')

            # Decode URL-encoded object key (e.g., spaces as '+' or '%20')
            object_key = urllib.parse.unquote_plus(raw_key)

            logger.info("Processing S3 record: bucket='%s', key='%s'", bucket_name, object_key)

            # 2. Recursive Loop Protection: Ensure key starts with 'uploads/'
            if not object_key.startswith(INPUT_PREFIX):
                logger.info("Skipping object outside '%s' prefix: s3://%s/%s",
                            INPUT_PREFIX, bucket_name, object_key)
                skipped_records.append({
                    "bucket": bucket_name,
                    "key": object_key,
                    "reason": f"Object not under prefix '{INPUT_PREFIX}'"
                })
                continue

            # Prevent processing already processed objects
            if object_key.startswith(OUTPUT_PREFIX):
                logger.warning("Recursive trigger protection: Object already in '%s'. Skipping.", OUTPUT_PREFIX)
                skipped_records.append({
                    "bucket": bucket_name,
                    "key": object_key,
                    "reason": "Recursive loop prevented"
                })
                continue

            # 3. File extension verification
            _, ext = os.path.splitext(object_key)
            if ext.lower() not in SUPPORTED_EXTENSIONS:
                logger.warning("Unsupported file extension '%s' for s3://%s/%s. Skipping.",
                               ext, bucket_name, object_key)
                skipped_records.append({
                    "bucket": bucket_name,
                    "key": object_key,
                    "reason": f"Unsupported extension '{ext}'"
                })
                continue

            # 4. Lookup image record in MySQL & update status to PROCESSING
            if db_conn:
                try:
                    db_record = find_image_record(db_conn, object_key)
                    if db_record:
                        logger.info("Found database record image_id=%s for key '%s'",
                                    db_record.get('image_id'), object_key)
                        update_db_status_processing(db_conn, object_key)
                    else:
                        logger.warning("No matching database record found for key '%s'; creating initial record", object_key)
                        create_initial_record_if_missing(db_conn, bucket_name, object_key)
                except Exception as db_ex:
                    logger.error("Database error during status lookup/transition: %s", str(db_ex))
                    raise

            # 5. Download original image from S3
            try:
                logger.info("Downloading s3://%s/%s", bucket_name, object_key)
                download_response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
                original_image_bytes = download_response['Body'].read()
                logger.info("Downloaded %d bytes successfully", len(original_image_bytes))
            except Exception as dl_err:
                logger.error("Failed to download image s3://%s/%s: %s",
                             bucket_name, object_key, str(dl_err), exc_info=True)
                if db_conn:
                    update_db_status_failed(db_conn, object_key, f"S3 download failed: {str(dl_err)}")
                raise RuntimeError(f"S3 download failed for s3://{bucket_name}/{object_key}: {str(dl_err)}")

            # 6. Process image via Pillow
            try:
                processed_bytes, orig_dim, proc_dim = process_image_bytes(
                    image_bytes=original_image_bytes,
                    max_dimensions=(MAX_WIDTH, MAX_HEIGHT),
                    quality=JPEG_QUALITY
                )
            except (UnidentifiedImageError, IOError, ValueError) as img_err:
                logger.error("Corrupted or unreadable image file s3://%s/%s: %s",
                             bucket_name, object_key, str(img_err), exc_info=True)
                if db_conn:
                    update_db_status_failed(db_conn, object_key, f"Corrupted image: {str(img_err)}")
                raise RuntimeError(f"Image processing failed for s3://{bucket_name}/{object_key}: {str(img_err)}")
            except Exception as proc_err:
                logger.error("Unexpected error during image processing for s3://%s/%s: %s",
                             bucket_name, object_key, str(proc_err), exc_info=True)
                if db_conn:
                    update_db_status_failed(db_conn, object_key, f"Processing error: {str(proc_err)}")
                raise RuntimeError(f"Image processing failed for s3://{bucket_name}/{object_key}: {str(proc_err)}")

            # 7. Generate destination S3 object key
            processed_key = generate_processed_key(object_key, output_prefix=OUTPUT_PREFIX)

            # 8. Upload processed JPEG to S3 under 'processed/'
            try:
                logger.info("Uploading processed image (%d bytes) to s3://%s/%s",
                            len(processed_bytes), bucket_name, processed_key)
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=processed_key,
                    Body=processed_bytes,
                    ContentType='image/jpeg'
                )
                logger.info("Successfully uploaded processed image to s3://%s/%s",
                            bucket_name, processed_key)
            except Exception as up_err:
                logger.error("Failed to upload processed image to s3://%s/%s: %s",
                             bucket_name, processed_key, str(up_err), exc_info=True)
                if db_conn:
                    update_db_status_failed(db_conn, object_key, f"S3 upload failed: {str(up_err)}")
                raise RuntimeError(f"S3 upload failed for s3://{bucket_name}/{processed_key}: {str(up_err)}")

            # 9. Update database record to COMPLETED
            if db_conn:
                update_db_status_completed(
                    conn=db_conn,
                    original_s3_key=object_key,
                    processed_s3_key=processed_key,
                    processed_format='JPEG',
                    processed_width=proc_dim[0],
                    processed_height=proc_dim[1],
                    processed_size_bytes=len(processed_bytes)
                )

            # Record processing metrics
            record_summary = {
                "bucket": bucket_name,
                "original_key": object_key,
                "processed_key": processed_key,
                "original_dimensions": f"{orig_dim[0]}x{orig_dim[1]}",
                "processed_dimensions": f"{proc_dim[0]}x{proc_dim[1]}",
                "original_size_bytes": len(original_image_bytes),
                "processed_size_bytes": len(processed_bytes),
                "status": "SUCCESS"
            }
            processed_records.append(record_summary)
            logger.info("Processing complete for record: %s", json.dumps(record_summary))

    finally:
        # Guaranteed cleanup of database connection
        if db_conn:
            try:
                db_conn.close()
                logger.info("Closed Lambda database connection safely.")
            except Exception as close_err:
                logger.warning("Error closing database connection: %s", str(close_err))

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Lambda image processing cycle completed",
            "processed": processed_records,
            "skipped": skipped_records
        })
    }


if __name__ == '__main__':
    # Local CLI preview invocation
    sample_event = {
        "Records": [
            {
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "awsRegion": "ap-south-1",
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": "sample-bucket"},
                    "object": {"key": "uploads/sample+test.jpg"}
                }
            }
        ]
    }
    print("Testing Lambda handler syntax:")
    print(lambda_handler(sample_event, None))
