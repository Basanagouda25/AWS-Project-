"""
Packaging Script for AWS Lambda Deployment
Module 5: Automated Image Preprocessing System Using AWS

Builds a deployment ZIP archive ('dist/image-preprocessing-lambda.zip') containing:
1. 'image_processor.py' (Lambda handler with RDS integration)
2. Linux x86_64 compatible Pillow build (manylinux2014_x86_64 for Python 3.12)
3. Pure-Python PyMySQL for database connectivity

Usage:
    python package_lambda.py
"""

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BUILD_DIR = BASE_DIR / 'build_lambda'
DIST_DIR = BASE_DIR / 'dist'
LAMBDA_SRC = BASE_DIR / 'lambda' / 'image_processor.py'
ZIP_OUTPUT = DIST_DIR / 'image-preprocessing-lambda.zip'


def clean():
    """Remove previous build and distribution artifacts."""
    print("🧹 Cleaning previous build artifacts...")
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)


def download_linux_pillow():
    """
    Downloads and installs manylinux2014_x86_64 compatible Pillow for Python 3.12
    into the build directory. Boto3 is pre-installed in the Lambda runtime.
    """
    print("📦 Installing Linux x86_64 compatible Pillow for Python 3.12...")
    cmd = [
        sys.executable, "-m", "pip", "install",
        "--target", str(BUILD_DIR),
        "--platform", "manylinux2014_x86_64",
        "--implementation", "cp",
        "--python-version", "3.12",
        "--only-binary=:all:",
        "--upgrade",
        "Pillow"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Failed to install Linux Pillow dependencies:\n{result.stderr}")
        sys.exit(1)
    print("✅ Linux Pillow binaries installed successfully.")


def install_pymysql():
    """
    Installs pure-Python PyMySQL package into the build directory.
    PyMySQL has no platform-specific C extensions, making it 100% compatible with Linux Lambda.
    """
    print("📦 Installing PyMySQL for AWS RDS MySQL connectivity...")
    cmd = [
        sys.executable, "-m", "pip", "install",
        "--target", str(BUILD_DIR),
        "--upgrade",
        "pymysql"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Failed to install PyMySQL dependency:\n{result.stderr}")
        sys.exit(1)
    print("✅ PyMySQL installed successfully.")


def copy_handler():
    """Copies image_processor.py into the root of the build directory."""
    print(f"📄 Copying Lambda handler from {LAMBDA_SRC}...")
    if not LAMBDA_SRC.exists():
        print(f"❌ Error: {LAMBDA_SRC} not found!")
        sys.exit(1)
    dest_path = BUILD_DIR / 'image_processor.py'
    shutil.copy2(LAMBDA_SRC, dest_path)
    print("✅ Lambda handler copied.")


def create_zip():
    """Compresses the build directory into a deployment ZIP package."""
    print(f"🗜️  Creating deployment archive at {ZIP_OUTPUT}...")
    with zipfile.ZipFile(ZIP_OUTPUT, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(BUILD_DIR):
            for file in files:
                file_path = Path(root) / file
                archive_name = file_path.relative_to(BUILD_DIR)
                # Skip .dist-info and unnecessary cache files to reduce package size
                if '__pycache__' in str(archive_name):
                    continue
                zf.write(file_path, arcname=str(archive_name))

    size_mb = ZIP_OUTPUT.stat().st_size / (1024 * 1024)
    print(f"🎉 Deployment package created successfully: {ZIP_OUTPUT} ({size_mb:.2f} MB)")


def main():
    print("======================================================================")
    print("AWS Lambda Deployment Packager — Module 5 (Image Preprocessor + RDS)")
    print("Target: Python 3.12 / Linux x86_64")
    print("======================================================================")
    clean()
    download_linux_pillow()
    install_pymysql()
    copy_handler()
    create_zip()
    print("======================================================================")
    print("Ready to deploy! Upload 'dist/image-preprocessing-lambda.zip' to AWS Lambda.")
    print("Handler: image_processor.lambda_handler")
    print("======================================================================")


if __name__ == '__main__':
    main()
