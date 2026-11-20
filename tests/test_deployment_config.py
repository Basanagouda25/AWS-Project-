"""
Automated Deployment Configuration Tests — Module 7
Automated Image Preprocessing System Using AWS

Validates that all production deployment configurations, entry points,
Gunicorn settings, Nginx configurations, IAM policies, and systemd units
strictly adhere to the production deployment specifications.
"""

import json
import os
import sys
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent


def test_1_wsgi_entry_point():
    """1. Test that wsgi.py defines a valid WSGI application object for Gunicorn."""
    wsgi_file = BASE_DIR / "wsgi.py"
    assert wsgi_file.exists(), "wsgi.py entry point must exist in project root"

    import wsgi
    assert hasattr(wsgi, "app"), "wsgi.py must export 'app' callable for Gunicorn"
    assert wsgi.app is not None
    assert wsgi.app.debug is False, "Production WSGI app must have debug mode disabled"


def test_2_production_config_settings():
    """2. Test that ProductionConfig enforces strict production parameters."""
    from config import ProductionConfig

    assert ProductionConfig.DEBUG is False, "DEBUG must be False in production"
    assert ProductionConfig.TESTING is False, "TESTING must be False in production"
    assert ProductionConfig.MAX_CONTENT_LENGTH == 10 * 1024 * 1024, "Max file upload size must be 10 MB"
    assert ProductionConfig.ALLOWED_EXTENSIONS == {'png', 'jpg', 'jpeg'}


def test_3_gunicorn_configuration_file():
    """3. Test deployment/gunicorn.conf.py settings."""
    conf_path = BASE_DIR / "deployment" / "gunicorn.conf.py"
    assert conf_path.exists(), "deployment/gunicorn.conf.py must exist"

    # Load configuration module dynamically
    gunicorn_namespace = {}
    with open(conf_path, "r", encoding="utf-8") as f:
        code = f.read()
    exec(code, gunicorn_namespace)

    assert "bind" in gunicorn_namespace
    assert "127.0.0.1:8000" in gunicorn_namespace["bind"], "Gunicorn must bind internally to 127.0.0.1:8000"
    assert gunicorn_namespace.get("timeout", 0) >= 60, "Timeout must be at least 60 seconds for uploads"
    assert gunicorn_namespace.get("workers", 0) >= 2, "Gunicorn must configure at least 2 workers"
    assert gunicorn_namespace.get("worker_class") == "sync"


def test_4_nginx_configuration_file():
    """4. Test deployment/nginx.conf parameters."""
    nginx_path = BASE_DIR / "deployment" / "nginx.conf"
    assert nginx_path.exists(), "deployment/nginx.conf must exist"

    content = nginx_path.read_text(encoding="utf-8")
    assert "listen 80" in content, "Nginx must listen on port 80"
    assert "client_max_body_size 10M;" in content, "Nginx must allow up to 10 MB uploads"
    assert "proxy_pass" in content, "Nginx must configure proxy_pass"
    assert "127.0.0.1:8000" in content or "flask_gunicorn" in content, "Nginx must proxy to Gunicorn on port 8000"
    assert "X-Forwarded-For" in content, "Nginx must forward client IP headers"
    assert "location /static/" in content, "Nginx must serve static files directly"


def test_5_systemd_service_file():
    """5. Test deployment/gunicorn.service unit structure."""
    service_path = BASE_DIR / "deployment" / "gunicorn.service"
    assert service_path.exists(), "deployment/gunicorn.service must exist"

    content = service_path.read_text(encoding="utf-8")
    assert "[Unit]" in content
    assert "[Service]" in content
    assert "[Install]" in content
    assert "WorkingDirectory=/var/www/aws-image-preprocessing" in content
    assert "gunicorn.conf.py" in content
    assert "wsgi:app" in content
    assert "Restart=always" in content
    assert "User=ec2-user" in content


def test_6_iam_policy_json_validity():
    """6. Test deployment/iam_policy.json follows least-privilege principles."""
    policy_path = BASE_DIR / "deployment" / "iam_policy.json"
    assert policy_path.exists(), "deployment/iam_policy.json must exist"

    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    assert policy.get("Version") == "2012-10-17"
    statements = policy.get("Statement", [])
    assert len(statements) >= 1

    actions = []
    resources = []
    for stmt in statements:
        assert stmt.get("Effect") == "Allow"
        stmt_actions = stmt.get("Action", [])
        if isinstance(stmt_actions, str):
            stmt_actions = [stmt_actions]
        actions.extend(stmt_actions)

        stmt_resources = stmt.get("Resource", [])
        if isinstance(stmt_resources, str):
            stmt_resources = [stmt_resources]
        resources.extend(stmt_resources)

    # Validate least privilege: S3 PutObject and GetObject are granted
    assert "s3:PutObject" in actions
    assert "s3:GetObject" in actions

    # Guard: No full wildcard action or AdministratorAccess
    assert "*" not in actions, "IAM policy must not grant wildcard '*' actions"
    assert "*:*" not in actions

    # Verify resource scoping
    assert any("uploads/*" in r for r in resources), "Policy must cover uploads prefix"
    assert any("processed/*" in r for r in resources), "Policy must cover processed prefix"


def test_7_iam_trust_policy_validity():
    """7. Test deployment/iam_trust_policy.json allows EC2 assumption."""
    trust_path = BASE_DIR / "deployment" / "iam_trust_policy.json"
    assert trust_path.exists(), "deployment/iam_trust_policy.json must exist"

    trust_doc = json.loads(trust_path.read_text(encoding="utf-8"))
    statements = trust_doc.get("Statement", [])
    assert len(statements) >= 1
    stmt = statements[0]
    assert stmt.get("Action") == "sts:AssumeRole"
    assert stmt.get("Principal", {}).get("Service") == "ec2.amazonaws.com"


def test_8_setup_and_deploy_scripts_exist():
    """8. Test that shell provisioning and deployment scripts exist with proper shebang."""
    setup_path = BASE_DIR / "deployment" / "ec2_setup.sh"
    deploy_path = BASE_DIR / "deployment" / "deploy.sh"

    assert setup_path.exists(), "ec2_setup.sh must exist"
    assert deploy_path.exists(), "deploy.sh must exist"

    setup_content = setup_path.read_text(encoding="utf-8")
    assert setup_content.startswith("#!/usr/bin/env bash") or setup_content.startswith("#!/bin/bash")
    assert "dnf" in setup_content or "yum" in setup_content, "Must support Amazon Linux package manager"
    assert "nginx" in setup_content
    assert "venv" in setup_content

    deploy_content = deploy_path.read_text(encoding="utf-8")
    assert deploy_content.startswith("#!/usr/bin/env bash") or deploy_content.startswith("#!/bin/bash")
    assert "systemctl restart gunicorn" in deploy_content
    assert "systemctl" in deploy_content
    assert "/health" in deploy_content, "deploy.sh must probe /health endpoint"


def test_9_production_env_example():
    """9. Test deployment/production.env.example configuration keys."""
    env_example = BASE_DIR / "deployment" / "production.env.example"
    assert env_example.exists(), "deployment/production.env.example must exist"

    content = env_example.read_text(encoding="utf-8")
    required_keys = [
        "FLASK_ENV=production",
        "DEBUG=False",
        "STORAGE_BACKEND=s3",
        "AWS_REGION=ap-south-1",
        "S3_BUCKET_NAME=",
        "DB_HOST=",
        "DB_PORT=3306",
        "DB_USER=",
        "DB_NAME=image_preprocessing"
    ]
    for key in required_keys:
        assert key in content, f"production.env.example must specify '{key}'"


def test_10_production_error_handlers_safe():
    """10. Test that production error handlers return clean JSON without exposing stack traces."""
    from app import create_app
    from config import ProductionConfig

    app = create_app(config_class=ProductionConfig)
    client = app.test_client()

    # 404 test
    res = client.get("/non-existent-endpoint-404")
    assert res.status_code == 404
    data = res.get_json()
    assert data["status"] == "error"
    assert "Traceback" not in str(data)

