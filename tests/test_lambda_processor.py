"""
Automated Unit Tests for Module 4: AWS Lambda Automated Image Preprocessing
Tests all 19 processing, resizing, format conversion, and S3 event handling requirements.
Uses unittest.mock to operate entirely in-memory with zero AWS credentials or network access.
"""

import io
import json
import os
import sys
import urllib.parse
from unittest.mock import MagicMock
import pytest
import pymysql
from botocore.exceptions import ClientError
from PIL import Image

# Add lambda directory to sys.path to safely import image_processor without keyword collisions
LAMBDA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lambda'))
if LAMBDA_DIR not in sys.path:
    sys.path.insert(0, LAMBDA_DIR)

import image_processor as ip
from image_processor import (
    lambda_handler,
    process_image_bytes,
    generate_processed_key,
    set_s3_client,
    set_db_connection,
    set_db_connection_factory,
    MAX_WIDTH,
    MAX_HEIGHT,
    JPEG_QUALITY,
    INPUT_PREFIX,
    OUTPUT_PREFIX
)


# ==============================================================================
# Helper Functions & Fixtures
# ==============================================================================

def create_raw_image(format='JPEG', size=(1200, 900), color='blue', mode='RGB') -> bytes:
    """Creates a raw image in memory and returns bytes."""
    buf = io.BytesIO()
    img = Image.new(mode, size, color=color)
    img.save(buf, format=format)
    return buf.getvalue()


def create_transparent_png(size=(400, 400)) -> bytes:
    """Creates an RGBA PNG with transparent sections."""
    buf = io.BytesIO()
    img = Image.new('RGBA', size, color=(0, 0, 0, 0))  # Full transparent
    # Add a red square in the center
    for x in range(100, 300):
        for y in range(100, 300):
            img.putpixel((x, y), (255, 0, 0, 255))
    img.save(buf, format='PNG')
    return buf.getvalue()


def build_s3_event(bucket: str, key: str) -> dict:
    """Constructs a standard AWS S3 ObjectCreated event dictionary."""
    return {
        "Records": [
            {
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "awsRegion": "ap-south-1",
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": bucket},
                    "object": {"key": key}
                }
            }
        ]
    }


@pytest.fixture
def mock_s3():
    """Provides a mocked Boto3 S3 client for the Lambda module."""
    client = MagicMock()
    # Default get_object returns valid JPEG bytes
    default_bytes = create_raw_image(format='JPEG', size=(1200, 900), color='navy')
    client.get_object.return_value = {
        'Body': io.BytesIO(default_bytes),
        'ContentType': 'image/jpeg'
    }
    client.put_object.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200}}

    set_s3_client(client)

    # Provide a default mock DB connection so unit tests never attempt live network I/O
    default_db_conn = MagicMock()
    default_db_cursor = MagicMock()
    default_db_conn.cursor.return_value = default_db_cursor
    default_db_cursor.fetchone.return_value = {"image_id": "test-uuid", "processing_status": "PENDING"}
    set_db_connection(default_db_conn)

    yield client

    set_s3_client(None)
    set_db_connection(None)


# ==============================================================================
# 19 Test Cases for Module 4 Lambda Image Preprocessor
# ==============================================================================

def test_1_valid_jpeg_image_processing():
    """1. Test valid JPEG image processing converts to compliant JPEG."""
    raw_bytes = create_raw_image(format='JPEG', size=(1000, 800), color='green')
    proc_bytes, orig_dim, proc_dim = process_image_bytes(raw_bytes)

    assert orig_dim == (1000, 800)
    with Image.open(io.BytesIO(proc_bytes)) as out_img:
        assert out_img.format == 'JPEG'
        assert out_img.mode == 'RGB'


def test_2_valid_png_image_processing():
    """2. Test valid PNG image processing converts to JPEG format."""
    raw_bytes = create_raw_image(format='PNG', size=(900, 600), color='purple', mode='RGBA')
    proc_bytes, orig_dim, proc_dim = process_image_bytes(raw_bytes)

    assert orig_dim == (900, 600)
    with Image.open(io.BytesIO(proc_bytes)) as out_img:
        assert out_img.format == 'JPEG'
        assert out_img.mode == 'RGB'


def test_3_resizing_larger_than_800x800():
    """3. Test resizing an image larger than 800x800 limits both dimensions to <= 800."""
    raw_bytes = create_raw_image(format='JPEG', size=(1600, 1200))
    proc_bytes, orig_dim, proc_dim = process_image_bytes(raw_bytes)

    assert orig_dim == (1600, 1200)
    assert proc_dim[0] <= 800
    assert proc_dim[1] <= 800
    assert proc_dim == (800, 600)  # 4:3 ratio preserved


def test_4_preserving_aspect_ratio():
    """4. Test preserving aspect ratio for both landscape and portrait images."""
    # Landscape 2:1
    land_bytes = create_raw_image(format='JPEG', size=(1600, 800))
    _, _, land_dim = process_image_bytes(land_bytes)
    assert land_dim == (800, 400)

    # Portrait 1:2
    port_bytes = create_raw_image(format='JPEG', size=(800, 1600))
    _, _, port_dim = process_image_bytes(port_bytes)
    assert port_dim == (400, 800)


def test_5_not_enlarging_smaller_images():
    """5. Test that images smaller than 800x800 are not enlarged."""
    small_bytes = create_raw_image(format='JPEG', size=(450, 320))
    _, orig_dim, proc_dim = process_image_bytes(small_bytes)

    assert orig_dim == (450, 320)
    assert proc_dim == (450, 320)  # Dimensions unchanged


def test_6_jpeg_output_quality_configuration():
    """6. Test JPEG output quality configuration creates valid outputs with expected compression."""
    raw_bytes = create_raw_image(format='JPEG', size=(1200, 1000))
    high_q_bytes, _, _ = process_image_bytes(raw_bytes, quality=80)
    low_q_bytes, _, _ = process_image_bytes(raw_bytes, quality=30)

    # Lower quality results in smaller file size
    assert len(low_q_bytes) < len(high_q_bytes)
    with Image.open(io.BytesIO(high_q_bytes)) as img_high:
        assert img_high.format == 'JPEG'
    with Image.open(io.BytesIO(low_q_bytes)) as img_low:
        assert img_low.format == 'JPEG'


def test_7_png_transparency_handling():
    """7. Test that transparent PNGs are composited onto a white background before JPEG conversion."""
    png_bytes = create_transparent_png(size=(300, 300))
    proc_bytes, _, _ = process_image_bytes(png_bytes)

    with Image.open(io.BytesIO(proc_bytes)) as out_img:
        assert out_img.format == 'JPEG'
        assert out_img.mode == 'RGB'
        # The top-left corner was transparent, now it should be white (255, 255, 255)
        pixel_top_left = out_img.getpixel((10, 10))
        assert pixel_top_left == (255, 255, 255)
        # Center square was red (255, 0, 0)
        pixel_center = out_img.getpixel((150, 150))
        # Allow slight compression artifact tolerance for JPEG
        assert pixel_center[0] > 240
        assert pixel_center[1] < 20
        assert pixel_center[2] < 20


def test_8_exif_orientation_handling():
    """8. Test that EXIF orientation transpose does not crash and processes correctly."""
    # Create image with mock EXIF
    img = Image.new('RGB', (600, 400), color='orange')
    exif = img.getexif()
    exif[0x0112] = 6  # Orientation code 6: Rotate 90 CW
    buf = io.BytesIO()
    img.save(buf, format='JPEG', exif=exif)

    proc_bytes, orig_dim, proc_dim = process_image_bytes(buf.getvalue())
    assert proc_bytes is not None
    # Dimension is transposed from 600x400 to 400x600 by EXIF orientation 6
    assert proc_dim == (400, 600)


def test_9_correct_output_naming():
    """9. Test correct output naming convention."""
    assert generate_processed_key("uploads/photo123.jpg") == "processed/photo123_processed.jpg"
    assert generate_processed_key("uploads/abc123.png") == "processed/abc123_processed.jpg"
    assert generate_processed_key("uploads/nested/image.jpeg") == "processed/image_processed.jpg"


def test_10_correct_processed_prefix():
    """10. Test that processed output keys strictly use 'processed/' prefix."""
    output_key = generate_processed_key("uploads/test_file.png")
    assert output_key.startswith("processed/")
    assert not output_key.startswith("uploads/")


def test_11_bucket_and_object_key_extraction(mock_s3):
    """11. Test correct extraction of bucket and object key from S3 event."""
    event = build_s3_event(bucket="my-custom-bucket", key="uploads/my_photo.jpg")
    response = lambda_handler(event, None)

    assert response['statusCode'] == 200
    assert mock_s3.get_object.called
    call_args = mock_s3.get_object.call_args.kwargs
    assert call_args['Bucket'] == "my-custom-bucket"
    assert call_args['Key'] == "uploads/my_photo.jpg"


def test_12_url_encoded_s3_object_keys(mock_s3):
    """12. Test that URL-encoded S3 keys (+ and %20 and parentheses) are properly decoded."""
    raw_key = "uploads/my+vacation%20photo%281%29.png"
    event = build_s3_event(bucket="test-bucket", key=raw_key)

    response = lambda_handler(event, None)
    assert response['statusCode'] == 200

    # Verify download called with decoded key
    download_key = mock_s3.get_object.call_args.kwargs['Key']
    assert download_key == "uploads/my vacation photo(1).png"

    # Verify upload called with decoded processed key
    upload_key = mock_s3.put_object.call_args.kwargs['Key']
    assert upload_key == "processed/my vacation photo(1)_processed.jpg"


def test_13_unsupported_file_extension(mock_s3):
    """13. Test that unsupported file extensions are safely skipped without processing."""
    event = build_s3_event(bucket="test-bucket", key="uploads/document.pdf")
    response = lambda_handler(event, None)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert len(body['skipped']) == 1
    assert "Unsupported extension" in body['skipped'][0]['reason']
    assert not mock_s3.get_object.called
    assert not mock_s3.put_object.called


def test_14_corrupted_image(mock_s3):
    """14. Test that corrupted image bytes raise a RuntimeError so Lambda marks failure."""
    mock_s3.get_object.return_value = {
        'Body': io.BytesIO(b"\xff\xd8\xffcorrupted_binary_header_garbage"),
        'ContentType': 'image/jpeg'
    }
    event = build_s3_event(bucket="test-bucket", key="uploads/corrupt.jpg")

    with pytest.raises(RuntimeError) as exc_info:
        lambda_handler(event, None)
    assert "Image processing failed" in str(exc_info.value)
    assert not mock_s3.put_object.called


def test_15_empty_or_malformed_event():
    """15. Test handling of empty or malformed event payloads."""
    res_empty = lambda_handler({}, None)
    assert res_empty['statusCode'] == 400

    res_none = lambda_handler(None, None)
    assert res_none['statusCode'] == 400

    res_no_records = lambda_handler({"Records": []}, None)
    assert res_no_records['statusCode'] == 400


def test_16_event_for_object_outside_uploads_prefix(mock_s3):
    """16. Test that objects outside 'uploads/' prefix (and in 'processed/') are skipped to prevent recursion."""
    # Test key outside uploads
    event_outside = build_s3_event(bucket="test-bucket", key="documents/invoice.jpg")
    res_outside = lambda_handler(event_outside, None)
    assert res_outside['statusCode'] == 200
    assert not mock_s3.get_object.called

    # Test key already in processed/ (prevent recursive loop)
    event_recursive = build_s3_event(bucket="test-bucket", key="processed/image_processed.jpg")
    res_rec = lambda_handler(event_recursive, None)
    assert res_rec['statusCode'] == 200
    assert not mock_s3.get_object.called
    assert not mock_s3.put_object.called


def test_17_s3_download_failure(mock_s3):
    """17. Test that S3 download failure raises RuntimeError to trigger Lambda retry."""
    mock_s3.get_object.side_effect = ClientError(
        {'Error': {'Code': 'NoSuchKey', 'Message': 'The specified key does not exist'}}, 'GetObject'
    )
    event = build_s3_event(bucket="test-bucket", key="uploads/missing.jpg")

    with pytest.raises(RuntimeError) as exc_info:
        lambda_handler(event, None)
    assert "S3 download failed" in str(exc_info.value)


def test_18_s3_upload_failure(mock_s3):
    """18. Test that S3 upload failure raises RuntimeError."""
    mock_s3.put_object.side_effect = ClientError(
        {'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}}, 'PutObject'
    )
    event = build_s3_event(bucket="test-bucket", key="uploads/valid.jpg")

    with pytest.raises(RuntimeError) as exc_info:
        lambda_handler(event, None)
    assert "S3 upload failed" in str(exc_info.value)


def test_19_successful_processing_and_upload(mock_s3):
    """
    19. Test full successful processing and upload cycle:
    - Original object in S3 is NEVER overwritten
    - Processed object is uploaded under 'processed/'
    - Processed object key is not eligible for recursive cycle
    - No real AWS connection required
    """
    test_image_bytes = create_raw_image(format='PNG', size=(1400, 1050), color='teal', mode='RGBA')
    mock_s3.get_object.return_value = {
        'Body': io.BytesIO(test_image_bytes),
        'ContentType': 'image/png'
    }

    event = build_s3_event(bucket="aws-project-2515", key="uploads/banner.png")
    response = lambda_handler(event, None)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert len(body['processed']) == 1

    proc_record = body['processed'][0]
    assert proc_record['bucket'] == "aws-project-2515"
    assert proc_record['original_key'] == "uploads/banner.png"
    assert proc_record['processed_key'] == "processed/banner_processed.jpg"
    assert proc_record['original_dimensions'] == "1400x1050"
    assert proc_record['processed_dimensions'] == "800x600"  # 4:3 ratio preserved
    assert proc_record['status'] == "SUCCESS"

    # Verify upload call
    assert mock_s3.put_object.called
    put_kwargs = mock_s3.put_object.call_args.kwargs
    assert put_kwargs['Bucket'] == "aws-project-2515"
    assert put_kwargs['Key'] == "processed/banner_processed.jpg"
    assert put_kwargs['ContentType'] == 'image/jpeg'

    # Verify original object was NEVER overwritten
    assert put_kwargs['Key'] != "uploads/banner.png"

    # Verify that the resulting key would be skipped if an event fired on it (preventing recursive loop)
    recursive_check_event = build_s3_event(bucket="aws-project-2515", key=proc_record['processed_key'])
    mock_s3.reset_mock()
    rec_response = lambda_handler(recursive_check_event, None)
    assert rec_response['statusCode'] == 200
    assert not mock_s3.get_object.called
    assert not mock_s3.put_object.called


# ==============================================================================
# Module 5 Tests: Lambda RDS Integration (Tests 20-27)
# ==============================================================================

@pytest.fixture
def mock_lambda_db():
    """Provides a mocked PyMySQL connection for Lambda handler."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    set_db_connection(conn)
    yield conn, cursor
    set_db_connection(None)


def test_20_lambda_db_record_lookup(mock_s3, mock_lambda_db):
    """20. Test that Lambda queries database for matching record using original_s3_key."""
    conn, cursor = mock_lambda_db
    cursor.fetchone.return_value = {"image_id": "uuid-123", "processing_status": "PENDING"}

    event = build_s3_event(bucket="test-bucket", key="uploads/lookup_test.jpg")
    response = lambda_handler(event, None)

    assert response['statusCode'] == 200
    assert cursor.execute.called
    # Check lookup query was executed with uploads/lookup_test.jpg
    executed_queries = [call[0][0] for call in cursor.execute.call_args_list]
    executed_params = [call[0][1] for call in cursor.execute.call_args_list]
    assert any("SELECT `image_id`" in q for q in executed_queries)
    assert any(("uploads/lookup_test.jpg",) == p for p in executed_params)


def test_21_lambda_db_status_update_processing(mock_s3, mock_lambda_db):
    """21. Test that Lambda updates record status to PROCESSING upon receiving event."""
    conn, cursor = mock_lambda_db
    cursor.fetchone.return_value = {"image_id": "uuid-123", "processing_status": "PENDING"}

    event = build_s3_event(bucket="test-bucket", key="uploads/status_test.jpg")
    response = lambda_handler(event, None)

    assert response['statusCode'] == 200
    executed_queries = [call[0][0] for call in cursor.execute.call_args_list]
    assert any("`processing_status` = 'PROCESSING'" in q for q in executed_queries)
    assert conn.commit.called


def test_22_lambda_db_status_update_completed(mock_s3, mock_lambda_db):
    """22. Test that successful Lambda processing transitions record status to COMPLETED."""
    conn, cursor = mock_lambda_db
    cursor.fetchone.return_value = {"image_id": "uuid-123", "processing_status": "PENDING"}

    event = build_s3_event(bucket="test-bucket", key="uploads/complete_test.jpg")
    response = lambda_handler(event, None)

    assert response['statusCode'] == 200
    executed_queries = [call[0][0] for call in cursor.execute.call_args_list]
    assert any("`processing_status` = 'COMPLETED'" in q for q in executed_queries)
    assert conn.commit.called


def test_23_lambda_db_status_update_failed_on_error(mock_s3, mock_lambda_db):
    """23. Test that image processing failure transitions record status to FAILED with error message."""
    conn, cursor = mock_lambda_db
    cursor.fetchone.return_value = {"image_id": "uuid-123", "processing_status": "PENDING"}
    # Return corrupt bytes to trigger processing failure
    mock_s3.get_object.return_value = {
        'Body': io.BytesIO(b"\xff\xd8\xffnot_a_valid_image"),
        'ContentType': 'image/jpeg'
    }

    event = build_s3_event(bucket="test-bucket", key="uploads/corrupt_test.jpg")
    with pytest.raises(RuntimeError):
        lambda_handler(event, None)

    executed_queries = [call[0][0] for call in cursor.execute.call_args_list]
    assert any("`processing_status` = 'FAILED'" in q for q in executed_queries)
    assert conn.commit.called


def test_24_lambda_db_metadata_storage_accuracy(mock_s3, mock_lambda_db):
    """24. Test that processed format, dimensions, size, and s3 key are accurately persisted."""
    conn, cursor = mock_lambda_db
    cursor.fetchone.return_value = {"image_id": "uuid-123", "processing_status": "PENDING"}
    img_bytes = create_raw_image(format='PNG', size=(1200, 900), mode='RGB')
    mock_s3.get_object.return_value = {'Body': io.BytesIO(img_bytes), 'ContentType': 'image/png'}

    event = build_s3_event(bucket="test-bucket", key="uploads/meta_test.png")
    response = lambda_handler(event, None)

    assert response['statusCode'] == 200
    # Find the COMPLETED query call
    completed_call = None
    for call in cursor.execute.call_args_list:
        if "`processing_status` = 'COMPLETED'" in call[0][0]:
            completed_call = call
            break

    assert completed_call is not None
    params = completed_call[0][1]
    # params: (processed_s3_key, processed_format, processed_width, processed_height, processed_size_bytes, original_s3_key)
    assert params[0] == "processed/meta_test_processed.jpg"
    assert params[1] == "JPEG"
    assert params[2] == 800
    assert params[3] == 600
    assert params[4] > 0
    assert params[5] == "uploads/meta_test.png"


def test_25_lambda_db_connection_failure(mock_s3):
    """25. Test that database connection failure raises exception to trigger Lambda retry."""
    failing_factory = MagicMock(side_effect=pymysql.OperationalError(2003, "Can't connect to RDS MySQL"))
    set_db_connection_factory(failing_factory)

    try:
        event = build_s3_event(bucket="test-bucket", key="uploads/conn_fail.jpg")
        with pytest.raises(Exception):
            lambda_handler(event, None)
    finally:
        set_db_connection_factory(None)


def test_26_lambda_db_missing_record_handling(mock_s3, mock_lambda_db):
    """26. Test handling when S3 event arrives for a key not currently in the database."""
    conn, cursor = mock_lambda_db
    # Lookup returns None (no record found)
    cursor.fetchone.return_value = None

    event = build_s3_event(bucket="test-bucket", key="uploads/orphan_image.jpg")
    response = lambda_handler(event, None)

    # Should still process image safely
    assert response['statusCode'] == 200
    assert mock_s3.put_object.called


def test_27_lambda_db_connection_cleanup(mock_s3, mock_lambda_db):
    """27. Test that database connection is safely closed in finally block upon completion."""
    conn, cursor = mock_lambda_db
    cursor.fetchone.return_value = {"image_id": "uuid-123", "processing_status": "PENDING"}

    event = build_s3_event(bucket="test-bucket", key="uploads/cleanup_test.jpg")
    lambda_handler(event, None)

    assert conn.close.called

