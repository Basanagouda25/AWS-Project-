"""
Automated Unit Tests for Module 5: Amazon RDS MySQL Database Integration
Tests all 14 database operations, transaction lifecycles, and error scenarios.
Uses unittest.mock to operate entirely in-memory with zero RDS credentials or network access.
"""

import io
import uuid
from unittest.mock import MagicMock, patch
import pytest
import pymysql
from PIL import Image

from app import create_app
from config import TestingConfig
from app.services.database_service import (
    database_service,
    DatabaseService,
    DatabaseError,
    DatabaseConnectionError
)
from app.services.s3_storage_service import s3_storage_service


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def mock_db_components():
    """Provides a mocked PyMySQL connection and cursor."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


@pytest.fixture
def configured_db_service(mock_db_components):
    """Provides a DatabaseService instance preconfigured with mock connection."""
    mock_conn, _ = mock_db_components
    service = DatabaseService(
        host="image-rds.ap-south-1.rds.amazonaws.com",
        port=3306,
        user="test_admin",
        password="test_secret_password",
        db_name="image_preprocessing",
        connect_timeout=5
    )
    service.set_mock_connection(mock_conn)
    return service


# ==============================================================================
# 14 Test Cases for Module 5 Database Service
# ==============================================================================

def test_1_database_connection_configuration():
    """1. Test reading database connection settings from constructor and properties."""
    service = DatabaseService(
        host="rds-instance.ap-south-1.rds.amazonaws.com",
        port=3307,
        user="custom_user",
        password="secret_pass_123",
        db_name="test_preprocessing",
        connect_timeout=8
    )

    assert service.host == "rds-instance.ap-south-1.rds.amazonaws.com"
    assert service.port == 3307
    assert service.user == "custom_user"
    assert service.password == "secret_pass_123"
    assert service.db_name == "test_preprocessing"
    assert service.connect_timeout == 8
    assert service.is_configured() is True


def test_2_successful_connection_using_mocks(mock_db_components):
    """2. Test successful database connection establishment via PyMySQL mock."""
    mock_conn, mock_cursor = mock_db_components
    mock_cursor.fetchone.return_value = {'1': 1}

    with patch('pymysql.connect', return_value=mock_conn) as mock_connect:
        service = DatabaseService(
            host="rds-host.ap-south-1.rds.amazonaws.com",
            port=3306,
            user="admin",
            password="password",
            db_name="image_preprocessing"
        )
        conn = service.get_connection()

        assert conn is mock_conn
        assert mock_connect.called
        call_kwargs = mock_connect.call_args.kwargs
        assert call_kwargs['host'] == "rds-host.ap-south-1.rds.amazonaws.com"
        assert call_kwargs['port'] == 3306
        assert call_kwargs['database'] == "image_preprocessing"
        assert call_kwargs['user'] == "admin"
        assert call_kwargs['charset'] == "utf8mb4"
        assert call_kwargs['autocommit'] is False


def test_3_connection_failure():
    """3. Test database connection failure raises DatabaseConnectionError safely."""
    with patch('pymysql.connect', side_effect=pymysql.MySQLError(2003, "Can't connect to MySQL server")):
        service = DatabaseService(
            host="unreachable-rds.internal",
            port=3306,
            user="admin",
            password="super_secret_password"
        )

        with pytest.raises(DatabaseConnectionError) as exc_info:
            service.get_connection()

        # Verify password is NEVER leaked in exception message
        assert "super_secret_password" not in str(exc_info.value)
        assert "Database connection failed" in str(exc_info.value)


def test_4_creating_image_record(configured_db_service, mock_db_components):
    """4. Test creating a new image record with status PENDING and correct schema fields."""
    mock_conn, mock_cursor = mock_db_components
    image_uuid = str(uuid.uuid4())

    record_data = {
        "image_id": image_uuid,
        "original_filename": "photo_test.png",
        "bucket_name": "aws-project-2515",
        "original_s3_key": f"uploads/{image_uuid}.png",
        "original_format": "PNG",
        "original_width": 1920,
        "original_height": 1080,
        "original_size_bytes": 1048576,
        "content_type": "image/png",
        "processing_status": "PENDING"
    }

    result_id = configured_db_service.create_image_record(record_data)

    assert result_id == image_uuid
    assert mock_cursor.execute.called

    # Parameterized query verification: verify SQL template has %s and params are passed as tuple
    sql, params = mock_cursor.execute.call_args.args
    assert "INSERT INTO image_records" in sql
    assert params[0] == image_uuid
    assert params[1] == "photo_test.png"
    assert params[2] == "aws-project-2515"
    assert params[3] == f"uploads/{image_uuid}.png"
    assert params[4] == "PNG"
    assert params[9] == "PENDING"

    # Transaction committed
    assert mock_conn.commit.called


def test_5_updating_image_record(configured_db_service, mock_db_components):
    """5. Test updating an existing image record with processed details."""
    mock_conn, mock_cursor = mock_db_components
    mock_cursor.rowcount = 1
    image_uuid = str(uuid.uuid4())

    updates = {
        "processing_status": "COMPLETED",
        "processed_s3_key": f"processed/{image_uuid}_processed.jpg",
        "processed_format": "JPEG",
        "processed_width": 800,
        "processed_height": 600,
        "processed_size_bytes": 245000
    }

    updated = configured_db_service.update_image_record(image_uuid, updates)

    assert updated is True
    assert mock_cursor.execute.called
    sql, params = mock_cursor.execute.call_args.args
    assert "UPDATE `image_records` SET" in sql
    assert "`processing_status` = %s" in sql
    assert "`processed_s3_key` = %s" in sql
    assert image_uuid in params
    assert mock_conn.commit.called


def test_6_retrieving_image_by_id(configured_db_service, mock_db_components):
    """6. Test retrieving an image record by image_id."""
    _, mock_cursor = mock_db_components
    target_id = "test-uuid-12345"
    mock_record = {
        "image_id": target_id,
        "original_filename": "avatar.jpg",
        "processing_status": "COMPLETED"
    }
    mock_cursor.fetchone.return_value = mock_record

    record = configured_db_service.get_image_by_id(target_id)

    assert record == mock_record
    assert mock_cursor.execute.called
    sql, params = mock_cursor.execute.call_args.args
    assert "WHERE `image_id` = %s" in sql
    assert params == (target_id,)


def test_7_retrieving_image_by_s3_key(configured_db_service, mock_db_components):
    """7. Test retrieving an image record by original_s3_key."""
    _, mock_cursor = mock_db_components
    s3_key = "uploads/unique-key-abc.jpg"
    mock_record = {
        "image_id": "uuid-999",
        "original_s3_key": s3_key,
        "processing_status": "PROCESSING"
    }
    mock_cursor.fetchone.return_value = mock_record

    record = configured_db_service.get_image_by_s3_key(s3_key)

    assert record == mock_record
    assert mock_cursor.execute.called
    sql, params = mock_cursor.execute.call_args.args
    assert "WHERE `original_s3_key` = %s" in sql
    assert params == (s3_key,)


def test_8_listing_image_records(configured_db_service, mock_db_components):
    """8. Test listing paginated image records ordered by created_at DESC."""
    _, mock_cursor = mock_db_components
    mock_rows = [
        {"image_id": "id-1", "original_filename": "pic1.jpg"},
        {"image_id": "id-2", "original_filename": "pic2.png"}
    ]
    mock_cursor.fetchall.return_value = mock_rows

    records = configured_db_service.get_all_images(limit=10, offset=0)

    assert len(records) == 2
    assert records[0]["image_id"] == "id-1"
    sql, params = mock_cursor.execute.call_args.args
    assert "ORDER BY `created_at` DESC LIMIT %s OFFSET %s" in sql
    assert params == (10, 0)


def test_9_parameterized_sql_execution(configured_db_service, mock_db_components):
    """9. Test that all user and application inputs strictly use parameterized %s execution."""
    _, mock_cursor = mock_db_components
    malicious_input = "test.png'; DROP TABLE image_records; --"

    record_data = {
        "image_id": "safe-id",
        "original_filename": malicious_input,
        "bucket_name": "test-bucket",
        "original_s3_key": "uploads/safe.png",
        "processing_status": "PENDING"
    }

    configured_db_service.create_image_record(record_data)

    sql, params = mock_cursor.execute.call_args.args
    # The SQL query itself must NOT contain raw concatenated input
    assert malicious_input not in sql
    # It must be cleanly placed in the parameter tuple
    assert malicious_input in params


def test_10_transaction_commit(configured_db_service, mock_db_components):
    """10. Test that successful database transactions are explicitly committed."""
    mock_conn, _ = mock_db_components

    configured_db_service.create_image_record({
        "image_id": "test-commit-id",
        "original_filename": "commit.png",
        "bucket_name": "bucket",
        "original_s3_key": "uploads/commit.png"
    })

    assert mock_conn.commit.called
    assert not mock_conn.rollback.called


def test_11_transaction_rollback(configured_db_service, mock_db_components):
    """11. Test that failed database transactions trigger rollback."""
    mock_conn, mock_cursor = mock_db_components
    mock_cursor.execute.side_effect = pymysql.MySQLError("Duplicate entry for key")

    with pytest.raises(DatabaseError):
        configured_db_service.create_image_record({
            "image_id": "dup-id",
            "original_filename": "dup.png",
            "bucket_name": "bucket",
            "original_s3_key": "uploads/dup.png"
        })

    assert mock_conn.rollback.called


def test_12_connection_and_cursor_cleanup(configured_db_service, mock_db_components):
    """12. Test that connections and cursors are safely closed in finally blocks."""
    mock_conn, mock_cursor = mock_db_components

    configured_db_service.get_image_by_id("some-id")

    assert mock_cursor.close.called
    assert mock_conn.close.called


def test_13_processing_status_protection(configured_db_service, mock_db_components):
    """13. Test that status updates do not downgrade an already COMPLETED status."""
    _, mock_cursor = mock_db_components
    image_uuid = "completed-record-id"

    # Attempt to set status back to PROCESSING
    configured_db_service.update_image_record(image_uuid, {"processing_status": "PROCESSING"})

    sql, params = mock_cursor.execute.call_args.args
    assert "`processing_status` != 'COMPLETED'" in sql


def test_14_handling_missing_records(configured_db_service, mock_db_components):
    """14. Test handling of non-existent records gracefully without raising exceptions."""
    _, mock_cursor = mock_db_components
    mock_cursor.fetchone.return_value = None
    mock_cursor.rowcount = 0

    record = configured_db_service.get_image_by_id("non-existent-uuid")
    assert record is None

    updated = configured_db_service.update_image_record("non-existent-uuid", {"processing_status": "COMPLETED"})
    assert updated is False


# ==============================================================================
# Flask Integration Tests with Mocked Database
# ==============================================================================

def test_15_health_check_reports_database_status():
    """15. Test GET /health diagnostic endpoint reports database health status."""
    app = create_app(config_class=TestingConfig)
    client = app.test_client()

    # In TestingConfig, DB_HOST is None, so database_service.check_health() is 'not_configured'
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert 'services' in data
    assert data['services']['flask'] == 'healthy'
    assert data['services']['database'] == 'not_configured'


def test_16_upload_creates_pending_db_record_before_s3(mock_db_components):
    """16. Test that /api/upload creates a PENDING database record before invoking S3."""
    mock_conn, mock_cursor = mock_db_components
    mock_s3 = MagicMock()
    mock_s3.put_object.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200}}
    mock_s3.generate_presigned_url.return_value = "https://s3.ap-south-1.amazonaws.com/test-bucket/uploads/sample.jpg"

    s3_storage_service.set_client(mock_s3)
    database_service.set_mock_connection(mock_conn)
    database_service._host = "mock-rds.amazonaws.com"

    try:
        app = create_app(config_class=TestingConfig)
        app.config.update({
            "STORAGE_BACKEND": "s3",
            "S3_BUCKET_NAME": "test-bucket",
            "DB_HOST": "mock-rds.amazonaws.com"
        })
        client = app.test_client()

        # Create valid image
        buf = io.BytesIO()
        img = Image.new('RGB', (100, 100), color='purple')
        img.save(buf, format='JPEG')
        buf.seek(0)

        response = client.post('/api/upload', data={'image': (buf, 'photo.jpg', 'image/jpeg')}, content_type='multipart/form-data')
        assert response.status_code == 200
        payload = response.get_json()
        assert payload['success'] is True
        assert payload['processing_status'] == 'PENDING'
        assert payload['image_id'] is not None

        # Verify DB insert was called with status PENDING
        assert mock_cursor.execute.called
        queries = [call[0][0] for call in mock_cursor.execute.call_args_list]
        params = [call[0][1] for call in mock_cursor.execute.call_args_list]
        assert any("INSERT INTO image_records" in q for q in queries)
        assert any("PENDING" in p for p in params)
        assert mock_conn.commit.called

    finally:
        s3_storage_service.set_client(None)
        database_service.set_mock_connection(None)
        database_service._host = None


def test_17_upload_marks_failed_db_record_on_s3_error(mock_db_components):
    """17. Test that S3 upload failure updates database record status to FAILED."""
    from botocore.exceptions import ClientError
    mock_conn, mock_cursor = mock_db_components
    mock_s3 = MagicMock()
    mock_s3.put_object.side_effect = ClientError({'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}}, 'PutObject')

    s3_storage_service.set_client(mock_s3)
    database_service.set_mock_connection(mock_conn)
    database_service._host = "mock-rds.amazonaws.com"

    try:
        app = create_app(config_class=TestingConfig)
        app.config.update({
            "STORAGE_BACKEND": "s3",
            "S3_BUCKET_NAME": "test-bucket",
            "DB_HOST": "mock-rds.amazonaws.com"
        })
        client = app.test_client()

        buf = io.BytesIO()
        img = Image.new('RGB', (100, 100), color='orange')
        img.save(buf, format='JPEG')
        buf.seek(0)

        response = client.post('/api/upload', data={'image': (buf, 'photo.jpg', 'image/jpeg')}, content_type='multipart/form-data')
        assert response.status_code == 403  # S3AccessDenied returns 403

        # Verify DB update was called with status FAILED
        queries = [call[0][0] for call in mock_cursor.execute.call_args_list]
        params = [call[0][1] for call in mock_cursor.execute.call_args_list]
        assert any("UPDATE `image_records`" in q for q in queries)
        assert any("FAILED" in p for p in params)

    finally:
        s3_storage_service.set_client(None)
        database_service.set_mock_connection(None)
        database_service._host = None

