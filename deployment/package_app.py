"""
Package the Image Preprocessing application into an app.tar.gz archive for EC2 deployment.
Excludes virtual environments, cache files, local .env, and git metadata.
"""

import os
import tarfile

EXCLUDE_DIRS = {
    'venv', '.venv', '__pycache__', '.pytest_cache', '.git', 'dist'
}

EXCLUDE_EXTENSIONS = {
    '.pyc', '.pyo', '.tar.gz', '.zip'
}

EXCLUDE_FILES = {
    '.env'  # Prevent local credentials/configs from overwriting production settings
}

def should_exclude(tarinfo):
    name = tarinfo.name.replace('\\', '/')
    parts = name.split('/')
    
    # Check if any parent folder is in EXCLUDE_DIRS
    for part in parts:
        if part in EXCLUDE_DIRS:
            return None
            
    base = os.path.basename(name)
    if base in EXCLUDE_FILES:
        return None
        
    _, ext = os.path.splitext(base)
    if ext in EXCLUDE_EXTENSIONS:
        return None
        
    return tarinfo

def create_archive(output_path="app.tar.gz", root_dir="."):
    print(f"Creating archive {output_path} from {root_dir}...")
    with tarfile.open(output_path, "w:gz") as tar:
        for item in os.listdir(root_dir):
            if item in EXCLUDE_DIRS or item in EXCLUDE_FILES or item == output_path:
                continue
            item_path = os.path.join(root_dir, item)
            tar.add(item_path, arcname=item, filter=should_exclude)
    print(f"Successfully created {output_path} ({os.path.getsize(output_path)} bytes)")

if __name__ == "__main__":
    create_archive()

