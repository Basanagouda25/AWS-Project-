#!/usr/bin/env bash
# ==============================================================================
# EC2 Provisioning Script for Amazon Linux 2023
# Automated Image Preprocessing System Using AWS - Module 7
#
# Usage:
#   chmod +x deployment/ec2_setup.sh
#   ./deployment/ec2_setup.sh
# ==============================================================================

set -euo pipefail

# Visual Formatting
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}  AWS EC2 Server Setup — Automated Image Preprocessing System         ${NC}"
echo -e "${BLUE}  Target OS: Amazon Linux 2023 / Architecture: x86_64                 ${NC}"
echo -e "${BLUE}======================================================================${NC}"

# 1. Update OS System Packages
echo -e "\n${YELLOW}[1/7] Updating Amazon Linux 2023 core packages...${NC}"
sudo dnf update -y

# 2. Install Development Tools, Python, Git, and Nginx
echo -e "\n${YELLOW}[2/7] Installing Python 3, Development Tools, Git, and Nginx...${NC}"
# Attempt python3.12, fallback to python3 if already provided by Amazon Linux 2023
if sudo dnf list available python3.12 >/dev/null 2>&1; then
    sudo dnf install -y python3.12 python3.12-pip python3.12-devel git nginx gcc
    PYTHON_BIN="python3.12"
else
    sudo dnf install -y python3 python3-pip python3-devel git nginx gcc
    PYTHON_BIN="python3"
fi

$PYTHON_BIN --version
nginx -v

# 3. Create Web Application Directory & Set Permissions
APP_DIR="/var/www/aws-image-preprocessing"
echo -e "\n${YELLOW}[3/7] Setting up application directory at ${APP_DIR}...${NC}"
sudo mkdir -p "${APP_DIR}"
sudo chown -R ec2-user:ec2-user "${APP_DIR}"
sudo chmod 755 "${APP_DIR}"

# 4. Create Dedicated Log Directories
echo -e "\n${YELLOW}[4/7] Creating log directories for Gunicorn and Nginx...${NC}"
sudo mkdir -p /var/log/gunicorn
sudo chown -R ec2-user:ec2-user /var/log/gunicorn
sudo mkdir -p /var/log/nginx
sudo chown -R nginx:nginx /var/log/nginx

# 5. Setup Python Virtual Environment
echo -e "\n${YELLOW}[5/7] Initializing Python virtual environment...${NC}"
if [ ! -d "${APP_DIR}/venv" ]; then
    $PYTHON_BIN -m venv "${APP_DIR}/venv"
    echo -e "${GREEN}Virtual environment created at ${APP_DIR}/venv${NC}"
fi

"${APP_DIR}/venv/bin/pip" install --upgrade pip setuptools wheel

# 6. Configure Nginx Reverse Proxy
echo -e "\n${YELLOW}[6/7] Configuring Nginx reverse proxy...${NC}"
# Backup and remove default nginx welcome server if it exists
if [ -f /etc/nginx/nginx.conf ]; then
    # Disable default server block if present in main config to prevent port 80 collisions
    sudo sed -i 's/default_server//g' /etc/nginx/nginx.conf 2>/dev/null || true
fi

# Copy project Nginx configuration
if [ -f "${APP_DIR}/deployment/nginx.conf" ]; then
    sudo cp "${APP_DIR}/deployment/nginx.conf" /etc/nginx/conf.d/image_preprocessing.conf
    echo -e "${GREEN}Installed /etc/nginx/conf.d/image_preprocessing.conf${NC}"
fi

# Test Nginx configuration syntax
sudo nginx -t

# 7. Configure Systemd Service for Gunicorn
echo -e "\n${YELLOW}[7/7] Configuring systemd Gunicorn service...${NC}"
if [ -f "${APP_DIR}/deployment/gunicorn.service" ]; then
    sudo cp "${APP_DIR}/deployment/gunicorn.service" /etc/systemd/system/gunicorn.service
    sudo systemctl daemon-reload
    sudo systemctl enable gunicorn
    sudo systemctl enable nginx
    echo -e "${GREEN}Gunicorn and Nginx systemd services enabled on boot.${NC}"
fi

echo -e "\n${GREEN}======================================================================${NC}"
echo -e "${GREEN}  Server provisioning complete!                                        ${NC}"
echo -e "${GREEN}  Next steps:                                                          ${NC}"
echo -e "${GREEN}  1. Copy production .env to ${APP_DIR}/.env                           ${NC}"
echo -e "${GREEN}  2. Run ./deployment/deploy.sh to start the live application          ${NC}"
echo -e "${GREEN}======================================================================${NC}"

