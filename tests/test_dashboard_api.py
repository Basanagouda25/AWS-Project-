"""
Automated Unit & Integration Tests for Module 6: Dashboard & Image Processing Results
Tests all 18 requirements:
1. Dashboard statistics endpoint
2. Correct total image count
3. Correct completed count
4. Correct pending count
5. Correct processing count
6. Correct failed count
7. Image pagination
8. Invalid pagination parameters
9. Newest-first sorting
10. Image details endpoint
11. Missing image ID (404)
12. Original presigned URL generation
13. Processed presigned URL generation
14. Pending image without processed preview
15. Failed image details
16. File-size reduction calculation
17. Database failure handling
18. S3 presigned URL failure handling
Uses unittest.mock to operate entirely in-memory with zero AWS credentials or network access.
"""

from unittest.mock import MagicMock, patch
import pytest

from app import create_app
from config import TestingConfig
from app.services.database_service import database_service, DatabaseError
from app.services.s3_storage_service import s3_storage_service
from app.routes import calculate_size_reduction


@pytest.fixture
def mock_db():
    """Provides a mocked PyMySQL connection and cursor for Dashboard testing."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    database_service.set_mock_connection(mock_conn)
    database_service._host = "mock-rds.amazonaws.com"
    yield mock_conn, mock_cursor
    database_service.set_mock_connection(None)
    database_service._host = None


@pytest.fixture
def client(mock_db):
    """Provides Flask test client."""
    app = create_app(config_class=TestingConfig)
    app.config.update({
        "TESTING": True,
        "STORAGE_BACKEND": "s3",
        "S3_BUCKET_NAME": "test-image-bucket",
        "DB_HOST": "mock-rds.amazonaws.com"
    })
    return app.test_client()


# ==============================================================================
# 18 Test Cases for Module 6 Dashboard APIs
# ==============================================================================

def test_1_dashboard_statistics_endpoint(client, mock_db):
    """1. Test that GET /api/dashboard/stats returns HTTP 200 and success response."""
    _, mock_cursor = mock_db
    mock_cursor.fetchall.return_value = [
        {"processing_status": "COMPLETED", "count": 25},
        {"processing_status": "PENDING", "count": 5},
        {"processing_status": "PROCESSING", "count": 3},
        {"processing_status": "FAILED", "count": 2}
    ]

    response = client.get('/api/dashboard/stats')
    assert response.status_code == 200
    assert response.is_json
    payload = response.get_json()
    assert payload['success'] is True
    assert 'data' in payload


def test_2_correct_total_image_count(client, mock_db):
    """2. Test that total_images equals sum of all processing status counts."""
    _, mock_cursor = mock_db
    mock_cursor.fetchall.return_value = [
        {"processing_status": "COMPLETED", "count": 50},
        {"processing_status": "PENDING", "count": 20},
        {"processing_status": "PROCESSING", "count": 10},
        {"processing_status": "FAILED", "count": 5}
    ]

    response = client.get('/api/dashboard/stats')
    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['total_images'] == 85


def test_3_correct_completed_count(client, mock_db):
    """3. Test that completed status count accurately matches COMPLETED records."""
    _, mock_cursor = mock_db
    mock_cursor.fetchall.return_value = [
        {"processing_status": "COMPLETED", "count": 42}
    ]

    response = client.get('/api/dashboard/stats')
    data = response.get_json()['data']
    assert data['completed'] == 42


def test_4_correct_pending_count(client, mock_db):
    """4. Test that pending count accurately matches PENDING records."""
    _, mock_cursor = mock_db
    mock_cursor.fetchall.return_value = [
        {"processing_status": "PENDING", "count": 7}
    ]

    response = client.get('/api/dashboard/stats')
    data = response.get_json()['data']
    assert data['pending'] == 7


def test_5_correct_processing_count(client, mock_db):
    """5. Test that processing count accurately matches PROCESSING records."""
    _, mock_cursor = mock_db
    mock_cursor.fetchall.return_value = [
        {"processing_status": "PROCESSING", "count": 4}
    ]

    response = client.get('/api/dashboard/stats')
    data = response.get_json()['data']
    assert data['processing'] == 4


def test_6_correct_failed_count(client, mock_db):
    """6. Test that failed count accurately matches FAILED records."""
    _, mock_cursor = mock_db
    mock_cursor.fetchall.return_value = [
        {"processing_status": "FAILED", "count": 3}
    ]

    response = client.get('/api/dashboard/stats')
    data = response.get_json()['data']
    assert data['failed'] == 3


def test_7_image_pagination(client, mock_db):
    """7. Test image pagination returns proper subset, limit, offset, and page metadata."""
    _, mock_cursor = mock_db
    mock_cursor.fetchone.return_value = {"total": 25}
    mock_cursor.fetchall.return_value = [
        {"image_id": f"uuid-{i}", "original_filename": f"img{i}.jpg", "processing_status": "COMPLETED"}
        for i in range(10)
    ]

    response = client.get('/api/images?page=2&per_page=10')
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    data = payload['data']

    assert len(data['images']) == 10
    pagination = data['pagination']
    assert pagination['page'] == 2
    assert pagination['per_page'] == 10
    assert pagination['total_records'] == 25
    assert pagination['total_pages'] == 3
    assert pagination['has_next'] is True
    assert pagination['has_prev'] is True

    # Check query LIMIT %s OFFSET %s
    queries = [call[0][0] for call in mock_cursor.execute.call_args_list]
    params = [call[0][1] for call in mock_cursor.execute.call_args_list if len(call[0]) > 1]
    assert any("LIMIT %s OFFSET %s" in q for q in queries)
    assert any((10, 10) == p for p in params)


def test_8_invalid_pagination_parameters(client):
    """8. Test invalid pagination arguments return HTTP 400 Bad Request."""
    res_negative = client.get('/api/images?page=-1')
    assert res_negative.status_code == 400

    res_zero = client.get('/api/images?page=0')
    assert res_zero.status_code == 400

    res_non_int = client.get('/api/images?page=abc')
    assert res_non_int.status_code == 400

    res_too_large = client.get('/api/images?per_page=1000')
    assert res_too_large.status_code == 400


def test_9_newest_first_sorting(client, mock_db):
    """9. Test that SQL query for image list enforces ORDER BY created_at DESC."""
    _, mock_cursor = mock_db
    mock_cursor.fetchone.return_value = {"total": 1}
    mock_cursor.fetchall.return_value = [
        {"image_id": "uuid-1", "original_filename": "photo.jpg", "processing_status": "COMPLETED"}
    ]

    client.get('/api/images?page=1&per_page=5')
    queries = [call[0][0] for call in mock_cursor.execute.call_args_list]
    assert any("ORDER BY `created_at` DESC" in q for q in queries)


def test_10_image_details_endpoint(client, mock_db):
    """10. Test retrieving metadata for a specific image by image_id."""
    _, mock_cursor = mock_db
    target_id = "5d08365d-6611-41f2-a1ef-5326a61fdd7f"
    mock_cursor.fetchone.return_value = {
        "image_id": target_id,
        "original_filename": "spiderman.jpg",
        "bucket_name": "aws-project-2515",
        "original_s3_key": "uploads/spiderman.jpg",
        "processed_s3_key": "processed/spiderman_processed.jpg",
        "original_format": "JPEG",
        "processed_format": "JPEG",
        "original_width": 1920,
        "original_height": 1080,
        "processed_width": 800,
        "processed_height": 450,
        "original_size_bytes": 2000000,
        "processed_size_bytes": 400000,
        "processing_status": "COMPLETED"
    }

    response = client.get(f'/api/images/{target_id}')
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    data = payload['data']
    assert data['image_id'] == target_id
    assert data['original_filename'] == "spiderman.jpg"
    assert data['processing_status'] == "COMPLETED"


def test_11_missing_image_id(client, mock_db):
    """11. Test querying a non-existent image ID returns HTTP 404."""
    _, mock_cursor = mock_db
    mock_cursor.fetchone.return_value = None

    response = client.get('/api/images/non-existent-uuid-999')
    assert response.status_code == 404
    payload = response.get_json()
    assert payload['success'] is False
    assert "not found" in payload['message'].lower()


def test_12_original_presigned_url_generation(client, mock_db):
    """12. Test that original image presigned URL is generated using S3 service."""
    _, mock_cursor = mock_db
    mock_cursor.fetchone.return_value = {
        "image_id": "test-uuid",
        "original_filename": "cat.jpg",
        "bucket_name": "aws-project-2515",
        "original_s3_key": "uploads/cat.jpg",
        "processing_status": "PENDING"
    }

    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://s3.ap-south-1.amazonaws.com/test/uploads/cat.jpg?token=123"
    s3_storage_service.set_client(mock_s3)

    try:
        response = client.get('/api/images/test-uuid')
        assert response.status_code == 200
        data = response.get_json()['data']
        assert data['original_url'] is not None
        assert "uploads/cat.jpg" in data['original_url']
    finally:
        s3_storage_service.set_client(None)


def test_13_processed_presigned_url_generation(client, mock_db):
    """13. Test that processed presigned URL is generated when status is COMPLETED."""
    _, mock_cursor = mock_db
    mock_cursor.fetchone.return_value = {
        "image_id": "test-uuid-completed",
        "original_filename": "cat.jpg",
        "bucket_name": "aws-project-2515",
        "original_s3_key": "uploads/cat.jpg",
        "processed_s3_key": "processed/cat_processed.jpg",
        "processing_status": "COMPLETED"
    }

    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.side_effect = lambda ClientMethod, Params, ExpiresIn: (
        f"https://s3.ap-south-1.amazonaws.com/{Params['Bucket']}/{Params['Key']}?sig=abc"
    )
    s3_storage_service.set_client(mock_s3)

    try:
        response = client.get('/api/images/test-uuid-completed')
        assert response.status_code == 200
        data = response.get_json()['data']
        assert data['processed_url'] is not None
        assert "processed/cat_processed.jpg" in data['processed_url']
    finally:
        s3_storage_service.set_client(None)


def test_14_pending_image_without_processed_preview(client, mock_db):
    """14. Test that pending images do NOT generate processed presigned URLs."""
    _, mock_cursor = mock_db
    mock_cursor.fetchone.return_value = {
        "image_id": "test-pending",
        "original_filename": "pending.jpg",
        "bucket_name": "aws-project-2515",
        "original_s3_key": "uploads/pending.jpg",
        "processed_s3_key": None,
        "processing_status": "PENDING"
    }

    response = client.get('/api/images/test-pending')
    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['processed_url'] is None


def test_15_failed_image_details(client, mock_db):
    """15. Test that failed images retain and report safe error_message without crashing."""
    _, mock_cursor = mock_db
    mock_cursor.fetchone.return_value = {
        "image_id": "test-failed",
        "original_filename": "bad.jpg",
        "bucket_name": "aws-project-2515",
        "original_s3_key": "uploads/bad.jpg",
        "processed_s3_key": None,
        "processing_status": "FAILED",
        "error_message": "Corrupted image file: cannot identify image file"
    }

    response = client.get('/api/images/test-failed')
    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['processing_status'] == "FAILED"
    assert "Corrupted image" in data['error_message']
    assert data['processed_url'] is None


def test_16_file_size_reduction_calculation():
    """16. Test file-size reduction percentage formula and larger processed edge-case."""
    # Normal reduction: 1,000,000 bytes -> 200,000 bytes (80% reduction)
    norm = calculate_size_reduction(1000000, 200000)
    assert norm['bytes_saved'] == 800000
    assert norm['percentage'] == 80.0
    assert norm['is_reduction'] is True
    assert norm['is_larger'] is False

    # Processed image is larger: 100,000 bytes -> 120,000 bytes (-20% larger)
    larger = calculate_size_reduction(100000, 120000)
    assert larger['bytes_saved'] == -20000
    assert larger['percentage'] == -20.0
    assert larger['is_reduction'] is False
    assert larger['is_larger'] is True

    # Missing sizes or zero
    assert calculate_size_reduction(None, 100) is None
    assert calculate_size_reduction(100, None) is None
    assert calculate_size_reduction(0, 100) is None


def test_17_database_failure_handling(client, mock_db):
    """17. Test that database errors return HTTP 500 JSON without exposing stack traces."""
    _, mock_cursor = mock_db
    mock_cursor.execute.side_effect = Exception("MySQL connection dropped")

    res_stats = client.get('/api/dashboard/stats')
    assert res_stats.status_code == 500
    assert res_stats.get_json()['success'] is False

    res_list = client.get('/api/images')
    assert res_list.status_code == 500
    assert res_list.get_json()['success'] is False


def test_18_s3_presigned_url_failure_handling(client, mock_db):
    """18. Test that S3 errors during presigned URL generation do not crash the details API."""
    _, mock_cursor = mock_db
    mock_cursor.fetchone.return_value = {
        "image_id": "test-s3-fail",
        "original_filename": "s3_err.jpg",
        "bucket_name": "aws-project-2515",
        "original_s3_key": "uploads/s3_err.jpg",
        "processing_status": "COMPLETED",
        "processed_s3_key": "processed/s3_err_processed.jpg"
    }

    # Simulate S3 service exception when generating URL
    with patch.object(s3_storage_service, 'generate_presigned_url', side_effect=Exception("S3 offline")):
        response = client.get('/api/images/test-s3-fail')
        assert response.status_code == 200
        data = response.get_json()['data']
        # URLs should be None gracefully rather than crashing with 500
        assert data['original_url'] is None
        assert data['processed_url'] is None
