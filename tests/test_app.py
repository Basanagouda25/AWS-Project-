"""
Automated Unit and Integration Tests for Automated Image Preprocessing System
Module 1 and Module 2 Comprehensive Test Suite
"""

import io
import os
import uuid
import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage
from app import create_app
from config import TestingConfig
from app.services.upload_service import upload_service


# ==============================================================================
# Test Fixtures & Helpers
# ==============================================================================

@pytest.fixture
def app(tmp_path):
    """Create and configure an isolated Flask app for testing with a temporary upload folder."""
    test_upload_dir = str(tmp_path / "uploads")
    app = create_app(config_class=TestingConfig)
    app.config.update({
        "TESTING": True,
        "UPLOAD_FOLDER": test_upload_dir,
        "MAX_CONTENT_LENGTH": 10 * 1024 * 1024
    })
    yield app


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


def create_in_memory_image(format='JPEG', size=(120, 120), color='blue'):
    """Helper to generate valid image bytes in memory."""
    buf = io.BytesIO()
    mode = 'RGBA' if format.upper() == 'PNG' else 'RGB'
    img = Image.new(mode, size, color=color)
    img.save(buf, format=format)
    buf.seek(0)
    return buf


# ==============================================================================
# Module 1 Existing Tests (Preserved 100%)
# ==============================================================================

def test_app_starts_successfully(app):
    """Test that the application starts and has correct configuration."""
    assert app is not None
    assert app.config['TESTING'] is True
    assert app.config['AWS_REGION'] == 'ap-south-1'


def test_home_page_status_code(client):
    """Test GET / returns HTTP 200."""
    response = client.get('/')
    assert response.status_code == 200


def test_home_page_required_content(client):
    """
    Test that the landing page renders all required Module 1 elements:
    - Project title: Automated Image Preprocessing System Using AWS
    - Module badge: Module 1: Project Foundation Completed
    - Backend Status: Running
    - Four AWS tech cards: EC2, S3, RDS, Lambda
    """
    response = client.get('/')
    assert response.status_code == 200
    html_content = response.data.decode('utf-8')

    # Required textual content
    assert "Automated Image Preprocessing System Using AWS" in html_content
    assert "Module 1: Project Foundation Completed" in html_content
    assert "Backend Status: Running" in html_content

    # Four AWS Technology cards
    assert "Amazon EC2" in html_content
    assert "Amazon S3" in html_content
    assert "Amazon RDS" in html_content
    assert "AWS Lambda" in html_content


def test_health_check_status_code(client):
    """Test GET /health returns HTTP 200."""
    response = client.get('/health')
    assert response.status_code == 200


def test_health_check_response_body(client):
    """
    Test that GET /health returns the exact required JSON structure:
    {
      "status": "success",
      "message": "Image Preprocessing API is running"
    }
    """
    response = client.get('/health')
    assert response.status_code == 200
    assert response.is_json

    data = response.get_json()
    assert data is not None
    assert data.get('status') == 'success'
    assert data.get('message') == 'Image Preprocessing API is running'


def test_404_error_handling(client):
    """Test accessing an unknown route returns JSON error with 404 code."""
    response = client.get('/non-existent-route')
    assert response.status_code == 404
    assert response.is_json

    data = response.get_json()
    assert data.get('status') == 'error'
    assert data.get('code') == 404


# ==============================================================================
# Module 2 New Tests: Image Upload System & Validation
# ==============================================================================

def test_1_valid_jpeg_upload(client):
    """1. Test uploading a valid JPEG image returns HTTP 200 and format=JPEG."""
    image_bytes = create_in_memory_image(format='JPEG', size=(250, 180), color='navy')
    data = {
        'image': (image_bytes, 'photo.jpg', 'image/jpeg')
    }
    response = client.post('/api/upload', data=data, content_type='multipart/form-data')

    assert response.status_code == 200
    assert response.is_json
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['data']['format'] == 'JPEG'
    assert payload['data']['width'] == 250
    assert payload['data']['height'] == 180
    assert payload['data']['upload_status'] == 'LOCAL_UPLOAD_COMPLETED'


def test_2_valid_png_upload(client):
    """2. Test uploading a valid PNG image returns HTTP 200 and format=PNG."""
    image_bytes = create_in_memory_image(format='PNG', size=(320, 240), color='teal')
    data = {
        'image': (image_bytes, 'graphic.png', 'image/png')
    }
    response = client.post('/api/upload', data=data, content_type='multipart/form-data')

    assert response.status_code == 200
    assert response.is_json
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['data']['format'] == 'PNG'
    assert payload['data']['width'] == 320
    assert payload['data']['height'] == 240
    assert payload['data']['upload_status'] == 'LOCAL_UPLOAD_COMPLETED'


def test_3_missing_file_in_request(client):
    """3. Test uploading with missing file field returns HTTP 400."""
    response = client.post('/api/upload', data={}, content_type='multipart/form-data')
    assert response.status_code == 400
    assert response.is_json
    payload = response.get_json()
    assert payload['status'] == 'error'
    assert "No file selected" in payload['message']


def test_4_invalid_file_extension(client):
    """4. Test uploading a file with an invalid extension (e.g. .txt or .pdf) returns HTTP 400."""
    text_content = io.BytesIO(b"Hello world text file")
    data = {
        'image': (text_content, 'document.txt', 'text/plain')
    }
    response = client.post('/api/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    assert response.is_json
    payload = response.get_json()
    assert payload['status'] == 'error'
    assert "Only JPG, JPEG and PNG images are allowed" in payload['message']


def test_5_oversized_file(client, app):
    """5. Test uploading a file exceeding 10 MB limit returns HTTP 413."""
    # 10 MB + 1024 bytes
    oversized_bytes = io.BytesIO(b"0" * (10 * 1024 * 1024 + 1024))
    data = {
        'image': (oversized_bytes, 'large_image.jpg', 'image/jpeg')
    }
    response = client.post('/api/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 413
    assert response.is_json
    payload = response.get_json()
    assert payload['status'] == 'error'
    assert "exceeds maximum limit of 10 MB" in payload['message']


def test_6_invalid_image_content(client):
    """6. Test file with .jpg extension but containing non-image content is rejected by Pillow (HTTP 400)."""
    fake_content = io.BytesIO(b"This is fake content with .jpg extension")
    data = {
        'image': (fake_content, 'fake.jpg', 'image/jpeg')
    }
    response = client.post('/api/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    assert response.is_json
    payload = response.get_json()
    assert payload['status'] == 'error'
    assert "Corrupted or invalid image file" in payload['message']


def test_7_corrupted_image(client):
    """7. Test file with truncated/corrupted JPEG binary header is rejected by Pillow (HTTP 400)."""
    corrupted_bytes = io.BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00corrupted_bytes_no_image_data")
    data = {
        'image': (corrupted_bytes, 'corrupt.jpg', 'image/jpeg')
    }
    response = client.post('/api/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    assert response.is_json
    payload = response.get_json()
    assert payload['status'] == 'error'
    assert "Corrupted or invalid image file" in payload['message']


def test_8_uuid_based_unique_filenames(client, app):
    """8. Test that uploaded files are saved with a valid UUID4 filename on disk."""
    image_bytes = create_in_memory_image(format='JPEG', size=(50, 50))
    data = {
        'image': (image_bytes, 'my_photo.jpg', 'image/jpeg')
    }
    response = client.post('/api/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 200
    payload = response.get_json()

    image_id = payload['data']['image_id']
    # Validate image_id is a valid UUID
    uuid_obj = uuid.UUID(image_id, version=4)
    assert str(uuid_obj) == image_id

    # Verify file exists in UPLOAD_FOLDER with the UUID
    upload_folder = app.config['UPLOAD_FOLDER']
    expected_file = os.path.join(upload_folder, f"{image_id}.jpg")
    assert os.path.exists(expected_file)


def test_9_successful_json_response(client):
    """9. Test exact contract of the successful JSON response."""
    image_bytes = create_in_memory_image(format='PNG', size=(1920, 1080), color='white')
    data = {
        'image': (image_bytes, 'wallpaper.png', 'image/png')
    }
    response = client.post('/api/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 200
    assert response.is_json

    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['message'] == 'Image uploaded successfully'

    data_field = payload['data']
    assert 'image_id' in data_field
    assert data_field['filename'] == 'wallpaper.png'
    assert data_field['size'] > 0
    assert data_field['format'] == 'PNG'
    assert data_field['width'] == 1920
    assert data_field['height'] == 1080
    assert data_field['upload_status'] == 'LOCAL_UPLOAD_COMPLETED'


def test_10_upload_directory_creation(client, app):
    """10. Test that if the upload directory does not exist, it is created automatically."""
    new_dir = os.path.join(app.config['UPLOAD_FOLDER'], "nested_test_dir")
    if os.path.exists(new_dir):
        os.rmdir(new_dir)
    app.config['UPLOAD_FOLDER'] = new_dir

    image_bytes = create_in_memory_image(format='JPEG', size=(80, 80))
    data = {
        'image': (image_bytes, 'auto_dir.jpg', 'image/jpeg')
    }
    response = client.post('/api/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 200
    assert os.path.exists(new_dir)
    assert len(os.listdir(new_dir)) == 1


def test_11_empty_filename(client):
    """11. Test upload with empty filename is rejected with HTTP 400."""
    image_bytes = create_in_memory_image(format='JPEG', size=(40, 40))
    data = {
        'image': (image_bytes, '', 'image/jpeg')
    }
    response = client.post('/api/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    assert response.is_json
    payload = response.get_json()
    assert payload['status'] == 'error'
    assert "No file selected" in payload['message']


def test_12_duplicate_filenames_do_not_overwrite(client, app):
    """12. Test that uploading two files with the same original filename produces distinct files without overwriting."""
    # First file: blue 100x100
    img1 = create_in_memory_image(format='JPEG', size=(100, 100), color='blue')
    res1 = client.post('/api/upload', data={'image': (img1, 'sample.jpg', 'image/jpeg')}, content_type='multipart/form-data')
    assert res1.status_code == 200
    id1 = res1.get_json()['data']['image_id']

    # Second file: red 100x100
    img2 = create_in_memory_image(format='JPEG', size=(100, 100), color='red')
    res2 = client.post('/api/upload', data={'image': (img2, 'sample.jpg', 'image/jpeg')}, content_type='multipart/form-data')
    assert res2.status_code == 200
    id2 = res2.get_json()['data']['image_id']

    # IDs must be different
    assert id1 != id2

    # Both files must independently exist on disk in the upload directory
    upload_folder = app.config['UPLOAD_FOLDER']
    file1_path = os.path.join(upload_folder, f"{id1}.jpg")
    file2_path = os.path.join(upload_folder, f"{id2}.jpg")

    assert os.path.exists(file1_path)
    assert os.path.exists(file2_path)
    assert file1_path != file2_path
