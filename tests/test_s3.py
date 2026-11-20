"""
Automated Unit and Integration Tests for Module 3: AWS S3 Cloud Storage Integration
Uses unittest.mock to guarantee repeatability without requiring real AWS credentials or connections.
"""

import io
import os
import uuid
from unittest.mock import MagicMock
import pytest
from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
    PartialCredentialsError,
    EndpointConnectionError
)
from PIL import Image

from app import create_app
from config import TestingConfig
from app.services.s3_storage_service import (
    S3StorageService,
    s3_storage_service,
    S3ConfigurationError,
    S3AuthenticationError,
    S3AccessDeniedError,
    S3BucketNotFoundError,
    S3ServiceUnavailableError
)


# ==============================================================================
# Helper Functions & Fixtures
# ==============================================================================

def create_in_memory_image(format='JPEG', size=(120, 120), color='blue'):
    """Helper to generate valid image bytes in memory."""
    buf = io.BytesIO()
    mode = 'RGBA' if format.upper() == 'PNG' else 'RGB'
    img = Image.new(mode, size, color=color)
    img.save(buf, format=format)
    buf.seek(0)
    return buf


@pytest.fixture
def mock_s3_client():
    """Provides a mocked Boto3 S3 client."""
    client = MagicMock()
    client.put_object.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200}}
    client.generate_presigned_url.return_value = (
        'https://test-image-bucket.s3.ap-south-1.amazonaws.com/uploads/sample-uuid.jpg'
        '?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=mock&X-Amz-Expires=3600'
    )
    return client


@pytest.fixture
def s3_app(mock_s3_client, tmp_path):
    """Create Flask application configured for S3 storage with injected mock client."""
    test_upload_dir = str(tmp_path / "uploads")
    app = create_app(config_class=TestingConfig)
    app.config.update({
        "TESTING": True,
        "STORAGE_BACKEND": "s3",
        "S3_BUCKET_NAME": "test-image-bucket",
        "S3_BUCKET": "test-image-bucket",
        "S3_PRESIGNED_URL_EXPIRY": 3600,
        "S3_OBJECT_PREFIX": "uploads/",
        "UPLOAD_FOLDER": test_upload_dir,
        "MAX_CONTENT_LENGTH": 10 * 1024 * 1024
    })
    # Inject mock S3 client into the singleton service
    s3_storage_service.set_client(mock_s3_client)
    yield app
    # Clean up mock client
    s3_storage_service.set_client(None)


@pytest.fixture
def s3_client(s3_app):
    """Test client for S3 application."""
    return s3_app.test_client()


# ==============================================================================
# Module 3 Tests: S3 Storage Service & API Integration
# ==============================================================================

def test_1_s3_upload_success(s3_client, mock_s3_client):
    """1. Test successful image upload in S3 mode returns HTTP 200 and S3 metadata."""
    img_bytes = create_in_memory_image(format='JPEG', size=(300, 200), color='cyan')
    data = {
        'image': (img_bytes, 'cloud_photo.jpg', 'image/jpeg')
    }
    response = s3_client.post('/api/upload', data=data, content_type='multipart/form-data')

    assert response.status_code == 200
    assert response.is_json
    payload = response.get_json()

    assert payload['success'] is True
    assert payload['status'] == 'success'
    assert payload['storage_backend'] == 's3'
    assert payload['upload_status'] == 'S3_UPLOAD_COMPLETED'
    assert 'Image uploaded successfully to AWS S3' in payload['message']
    assert payload['s3_key'].startswith('uploads/')
    assert 'presigned_url' in payload
    assert payload['presigned_url'].startswith('https://')

    # Verify Boto3 put_object was called
    assert mock_s3_client.put_object.called
    call_kwargs = mock_s3_client.put_object.call_args.kwargs
    assert call_kwargs['Bucket'] == 'test-image-bucket'
    assert call_kwargs['ContentType'] == 'image/jpeg'


def test_2_correct_s3_object_key_generation(s3_client, mock_s3_client):
    """2. Test that S3 object key is generated with a valid UUID4 and correct extension."""
    img_bytes = create_in_memory_image(format='PNG', size=(150, 150), color='magenta')
    data = {
        'image': (img_bytes, 'art.png', 'image/png')
    }
    response = s3_client.post('/api/upload', data=data, content_type='multipart/form-data')

    assert response.status_code == 200
    payload = response.get_json()
    s3_key = payload['s3_key']

    # Extract filename from 'uploads/<uuid>.png'
    assert s3_key.startswith('uploads/')
    filename = s3_key.replace('uploads/', '')
    assert filename.endswith('.png')

    uuid_str = filename.rsplit('.', 1)[0]
    uuid_obj = uuid.UUID(uuid_str, version=4)
    assert str(uuid_obj) == uuid_str


def test_3_correct_uploads_prefix(s3_client, mock_s3_client, s3_app):
    """3. Test that object keys strictly honor the configured S3 prefix."""
    img_bytes = create_in_memory_image(format='JPEG', size=(80, 80))
    s3_client.post('/api/upload', data={'image': (img_bytes, 'pic.jpg', 'image/jpeg')},
                   content_type='multipart/form-data')

    call_kwargs = mock_s3_client.put_object.call_args.kwargs
    assert call_kwargs['Key'].startswith('uploads/')

    # Test custom prefix
    s3_app.config['S3_OBJECT_PREFIX'] = 'custom_folder/'
    img_bytes2 = create_in_memory_image(format='JPEG', size=(80, 80))
    res2 = s3_client.post('/api/upload', data={'image': (img_bytes2, 'pic2.jpg', 'image/jpeg')},
                          content_type='multipart/form-data')
    assert res2.status_code == 200
    assert res2.get_json()['s3_key'].startswith('custom_folder/')


def test_4_correct_content_type(s3_client, mock_s3_client):
    """4. Test that the correct Content-Type is passed to Boto3 put_object."""
    # Test JPEG
    jpeg_bytes = create_in_memory_image(format='JPEG', size=(50, 50))
    s3_client.post('/api/upload', data={'image': (jpeg_bytes, 'img.jpeg', 'image/jpeg')},
                   content_type='multipart/form-data')
    assert mock_s3_client.put_object.call_args.kwargs['ContentType'] == 'image/jpeg'

    # Test PNG
    png_bytes = create_in_memory_image(format='PNG', size=(50, 50))
    s3_client.post('/api/upload', data={'image': (png_bytes, 'img.png', 'image/png')},
                   content_type='multipart/form-data')
    assert mock_s3_client.put_object.call_args.kwargs['ContentType'] == 'image/png'


def test_5_presigned_url_generation(s3_client, mock_s3_client):
    """5. Test that Boto3 generate_presigned_url is invoked with correct parameters."""
    img_bytes = create_in_memory_image(format='JPEG', size=(60, 60))
    response = s3_client.post('/api/upload', data={'image': (img_bytes, 'view.jpg', 'image/jpeg')},
                              content_type='multipart/form-data')

    assert response.status_code == 200
    assert mock_s3_client.generate_presigned_url.called

    call_kwargs = mock_s3_client.generate_presigned_url.call_args.kwargs
    assert call_kwargs['ClientMethod'] == 'get_object'
    assert call_kwargs['Params']['Bucket'] == 'test-image-bucket'
    assert call_kwargs['Params']['Key'].startswith('uploads/')
    assert call_kwargs['ExpiresIn'] == 3600


def test_6_presigned_url_expiration_configuration(s3_client, mock_s3_client, s3_app):
    """6. Test that presigned URL expiration time is configurable via S3_PRESIGNED_URL_EXPIRY."""
    s3_app.config['S3_PRESIGNED_URL_EXPIRY'] = 7200
    img_bytes = create_in_memory_image(format='JPEG', size=(60, 60))
    response = s3_client.post('/api/upload', data={'image': (img_bytes, 'expire.jpg', 'image/jpeg')},
                              content_type='multipart/form-data')

    assert response.status_code == 200
    call_kwargs = mock_s3_client.generate_presigned_url.call_args.kwargs
    assert call_kwargs['ExpiresIn'] == 7200


def test_7_missing_bucket_configuration(s3_client, mock_s3_client, s3_app):
    """7. Test that missing S3_BUCKET_NAME returns HTTP 500 with clear configuration error."""
    s3_app.config['S3_BUCKET_NAME'] = ''
    s3_app.config['S3_BUCKET'] = ''

    img_bytes = create_in_memory_image(format='JPEG', size=(60, 60))
    response = s3_client.post('/api/upload', data={'image': (img_bytes, 'nobucket.jpg', 'image/jpeg')},
                              content_type='multipart/form-data')

    assert response.status_code == 500
    assert response.is_json
    payload = response.get_json()
    assert payload['success'] is False
    assert 'AWS S3 bucket is not configured' in payload['message']
    assert not mock_s3_client.put_object.called


def test_8_aws_credentials_and_access_failure(s3_client, mock_s3_client):
    """8. Test handling of AWS credential failures and AccessDenied errors."""
    img_bytes = create_in_memory_image(format='JPEG', size=(60, 60))

    # Case 8a: Missing/Invalid credentials (NoCredentialsError -> 500)
    mock_s3_client.put_object.side_effect = NoCredentialsError()
    res_cred = s3_client.post('/api/upload', data={'image': (img_bytes, 'auth_fail.jpg', 'image/jpeg')},
                              content_type='multipart/form-data')
    assert res_cred.status_code == 500
    assert 'Unable to authenticate with AWS S3' in res_cred.get_json()['message']

    # Case 8b: Access Denied (ClientError AccessDenied -> 403)
    img_bytes_denied = create_in_memory_image(format='JPEG', size=(60, 60))
    mock_s3_client.put_object.side_effect = ClientError(
        {'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}}, 'PutObject'
    )
    res_deny = s3_client.post('/api/upload', data={'image': (img_bytes_denied, 'denied.jpg', 'image/jpeg')},
                              content_type='multipart/form-data')
    assert res_deny.status_code == 403
    assert 'Access denied to AWS S3 bucket' in res_deny.get_json()['message']


def test_9_s3_service_exceptions(s3_client, mock_s3_client):
    """9. Test handling of AWS service unavailability and missing bucket errors."""
    img_bytes = create_in_memory_image(format='JPEG', size=(60, 60))

    # Case 9a: Network / Service Unreachable (EndpointConnectionError -> 503)
    mock_s3_client.put_object.side_effect = EndpointConnectionError(endpoint_url='https://s3.ap-south-1.amazonaws.com')
    res_down = s3_client.post('/api/upload', data={'image': (img_bytes, 'net_err.jpg', 'image/jpeg')},
                              content_type='multipart/form-data')
    assert res_down.status_code == 503
    assert 'AWS S3 service is currently unavailable' in res_down.get_json()['message']

    # Case 9b: Bucket does not exist (NoSuchBucket -> 404)
    img_bytes_nobkt = create_in_memory_image(format='JPEG', size=(60, 60))
    mock_s3_client.put_object.side_effect = ClientError(
        {'Error': {'Code': 'NoSuchBucket', 'Message': 'The specified bucket does not exist'}}, 'PutObject'
    )
    res_nobkt = s3_client.post('/api/upload', data={'image': (img_bytes_nobkt, 'missing_bkt.jpg', 'image/jpeg')},
                               content_type='multipart/form-data')
    assert res_nobkt.status_code == 404
    assert 'AWS S3 bucket not found' in res_nobkt.get_json()['message']


def test_10_local_storage_fallback(s3_client, mock_s3_client, s3_app):
    """10. Test that switching STORAGE_BACKEND='local' stores files locally without invoking Boto3 S3."""
    s3_app.config['STORAGE_BACKEND'] = 'local'
    img_bytes = create_in_memory_image(format='JPEG', size=(90, 90), color='green')
    mock_s3_client.put_object.reset_mock()

    response = s3_client.post('/api/upload', data={'image': (img_bytes, 'local_fallback.jpg', 'image/jpeg')},
                              content_type='multipart/form-data')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['storage_backend'] == 'local'
    assert payload['data']['upload_status'] == 'LOCAL_UPLOAD_COMPLETED'

    # S3 client must not be contacted in local mode
    assert not mock_s3_client.put_object.called

    # Local file exists
    upload_folder = s3_app.config['UPLOAD_FOLDER']
    assert os.path.exists(upload_folder)
    assert len(os.listdir(upload_folder)) == 1


def test_11_invalid_image_rejected_before_s3(s3_client, mock_s3_client):
    """11. Test that invalid files, corrupt images, and oversized files are rejected before S3 upload."""
    mock_s3_client.put_object.reset_mock()

    # Invalid extension
    bad_file = io.BytesIO(b"fake text content")
    res_ext = s3_client.post('/api/upload', data={'image': (bad_file, 'test.pdf', 'application/pdf')},
                             content_type='multipart/form-data')
    assert res_ext.status_code == 400
    assert not mock_s3_client.put_object.called

    # Corrupted image bytes
    corrupt_bytes = io.BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00corrupt")
    res_corrupt = s3_client.post('/api/upload', data={'image': (corrupt_bytes, 'corrupt.jpg', 'image/jpeg')},
                                 content_type='multipart/form-data')
    assert res_corrupt.status_code == 400
    assert not mock_s3_client.put_object.called

    # Oversized file (>10MB)
    big_bytes = io.BytesIO(b"0" * (10 * 1024 * 1024 + 1024))
    res_big = s3_client.post('/api/upload', data={'image': (big_bytes, 'huge.jpg', 'image/jpeg')},
                             content_type='multipart/form-data')
    assert res_big.status_code == 413
    assert not mock_s3_client.put_object.called


def test_12_no_real_aws_connection_required(mock_s3_client):
    """12. Test that S3StorageService can operate entirely via mock without network access or AWS keys."""
    service = S3StorageService(region_name='ap-south-1', client=mock_s3_client)
    sample_bytes = b"fake-valid-bytes"

    result = service.upload_image(
        file_content=sample_bytes,
        filename='mock_test.jpg',
        content_type='image/jpeg',
        bucket_name='standalone-mock-bucket',
        prefix='uploads/',
        expiry=1800
    )

    assert result['s3_key'].startswith('uploads/')
    assert result['upload_status'] == 'S3_UPLOAD_COMPLETED'
    assert result['storage_backend'] == 's3'
    assert mock_s3_client.put_object.called
    assert mock_s3_client.generate_presigned_url.called
