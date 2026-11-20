#!/usr/bin/env bash
# ==============================================================================
# Production Deployment & Service Management Script
# Automated Image Preprocessing System Using AWS - Module 7
#
# Usage:
#   chmod +x deployment/deploy.sh
#   ./deployment/deploy.sh
# ==============================================================================

set -euo pipefail

# Visual Formatting
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

APP_DIR="/var/www/aws-image-preprocessing"
cd "${APP_DIR}"

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}  Deploying Flask Application via Gunicorn & Nginx                     ${NC}"
echo -e "${BLUE}======================================================================${NC}"

# 1. Verify Production Environment Configuration File
echo -e "\n${YELLOW}[1/6] Checking production environment file (.env)...${NC}"
if [ ! -f "${APP_DIR}/.env" ]; then
    echo -e "${RED}ERROR: .env file not found in ${APP_DIR}!${NC}"
    echo -e "${YELLOW}Please create ${APP_DIR}/.env using deployment/production.env.example as a template.${NC}"
    exit 1
fi

# Restrict .env permissions strictly to ec2-user
chmod 600 "${APP_DIR}/.env"
echo -e "${GREEN}Configuration file verified and permissions secured (chmod 600).${NC}"

# 2. Ensure Instance Temporary Folders Exist
echo -e "\n${YELLOW}[2/6] Preparing upload directories and permissions...${NC}"
mkdir -p "${APP_DIR}/instance/uploads"
chmod 755 "${APP_DIR}/instance/uploads"

# 3. Update Python Virtual Environment Dependencies
echo -e "\n${YELLOW}[3/6] Installing/Updating Python dependencies in venv...${NC}"
"${APP_DIR}/venv/bin/pip" install --upgrade pip
"${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

# 4. Validate Server Configurations
echo -e "\n${YELLOW}[4/6] Validating Gunicorn and Nginx configurations...${NC}"
# Copy latest configs if modified
sudo cp "${APP_DIR}/deployment/nginx.conf" /etc/nginx/conf.d/image_preprocessing.conf
sudo cp "${APP_DIR}/deployment/gunicorn.service" /etc/systemd/system/gunicorn.service
sudo systemctl daemon-reload

# Validate Gunicorn entry point and syntax
"${APP_DIR}/venv/bin/gunicorn" --check-config --config "${APP_DIR}/deployment/gunicorn.conf.py" wsgi:app
echo -e "${GREEN}Gunicorn configuration syntax: OK${NC}"

# Validate Nginx syntax
sudo nginx -t
echo -e "${GREEN}Nginx configuration syntax: OK${NC}"

# 5. Restart Gunicorn and Reload Nginx
echo -e "\n${YELLOW}[5/6] Restarting Gunicorn WSGI and reloading Nginx...${NC}"
sudo systemctl restart gunicorn
sudo systemctl restart nginx

# Verify Gunicorn is actively running
sleep 2
if sudo systemctl is-active --quiet gunicorn; then
    echo -e "${GREEN}Gunicorn service is ACTIVE and running.${NC}"
else
    echo -e "${RED}ERROR: Gunicorn failed to start! Checking journalctl logs...${NC}"
    sudo journalctl -u gunicorn -n 25 --no-pager
    exit 1
fi

if sudo systemctl is-active --quiet nginx; then
    echo -e "${GREEN}Nginx reverse proxy service is ACTIVE and running.${NC}"
else
    echo -e "${RED}ERROR: Nginx failed to start!${NC}"
    sudo systemctl status nginx --no-pager
    exit 1
fi

# 6. Perform Local Endpoint Health Check
echo -e "\n${YELLOW}[6/6] Verifying application health check on http://127.0.0.1/health...${NC}"
MAX_RETRIES=5
RETRY_COUNT=0
HEALTHY=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -e "Attempt ${RETRY_COUNT}/${MAX_RETRIES}..."

    HTTP_STATUS=$(curl -s -o /tmp/health_response.json -w "%{http_code}" http://127.0.0.1/health || true)

    if [ "$HTTP_STATUS" -eq 200 ]; then
        HEALTHY=true
        break
    else
        echo -e "${YELLOW}Server returned HTTP ${HTTP_STATUS}. Retrying in 2 seconds...${NC}"
        sleep 2
    fi
done

if [ "$HEALTHY" = true ]; then
    echo -e "${GREEN}======================================================================${NC}"
    echo -e "${GREEN}  DEPLOYMENT SUCCESSFUL!                                              ${NC}"
    echo -e "${GREEN}======================================================================${NC}"
    cat /tmp/health_response.json
    echo ""

    # Fetch Public IP if reachable via AWS IP check
    PUBLIC_IP=$(curl -s --connect-timeout 3 http://checkip.amazonaws.com 2>/dev/null || echo "your-ec2-public-ip")
    echo -e "\n${BLUE}Public Application URL:${NC} http://${PUBLIC_IP}"
    echo -e "${BLUE}Dashboard View:${NC}         http://${PUBLIC_IP}/dashboard"
    echo -e "${BLUE}Health Diagnostics:${NC}     http://${PUBLIC_IP}/health"
else
    echo -e "${RED}======================================================================${NC}"
    echo -e "${RED}  HEALTH CHECK FAILED!                                                ${NC}"
    echo -e "${RED}======================================================================${NC}"
    cat /tmp/health_response.json 2>/dev/null || true
    echo -e "\nInspect live application logs via:"
    echo -e "  sudo journalctl -u gunicorn -f"
    echo -e "  sudo tail -f /var/log/nginx/image_preprocessing_error.log"
    exit 1
fi

