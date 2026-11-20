# AWS EC2 Production Deployment Runbook — Module 7

This runbook provides complete, beginner-friendly instructions for deploying the **Automated Image Preprocessing System** to an **Amazon Web Services (AWS) EC2** virtual server using **Nginx** and **Gunicorn**.

---

## 1. Target Production Architecture

```text
User Browser / Administrator
        │
        ▼ (Port 80 HTTP / 443 HTTPS)
AWS EC2 Elastic Network Interface (Public IP)
        │
        ▼
Nginx Reverse Proxy (/etc/nginx/conf.d/image_preprocessing.conf)
        ├── Serves static assets directly (/static/ ➔ /var/www/aws-image-preprocessing/static/)
        ├── Enforces 10 MB maximum request body limit (client_max_body_size 10M)
        └── Proxies application traffic to 127.0.0.1:8000
                │
                ▼
Gunicorn WSGI Application Server (3 workers on 127.0.0.1:8000)
        │
        ▼
Flask 3.x Application Factory (`wsgi:app`)
        ├── AWS S3: Streams raw assets via IAM Role (no keys stored on disk)
        └── AWS RDS MySQL: Transacts image lifecycle states through private VPC
                │
                ├─────────────────────────────────────────┐
                ▼ (ObjectCreated:Put Event)              ▼ (VPC Port 3306)
        AWS Lambda Preprocessor                 Amazon RDS MySQL
        (Pillow 800×800 JPEG resize)            (`image_records` table)
```

---

## 2. Step-by-Step EC2 Instance Launch Guide

### Step 1: Open EC2 in AWS Console
1. Log in to the [AWS Management Console](https://console.aws.amazon.com/).
2. In the top-right region selector, select **Asia Pacific (Mumbai) `ap-south-1`** (the same region as your S3 bucket and RDS database).
3. In the search bar, type **EC2** and navigate to the EC2 Dashboard.
4. Click the orange **Launch instance** button.

### Step 2: Configure Instance Details
- **Name**: `image-preprocessing-webserver`
- **Application and OS Images (AMI)**:
  - Select **Amazon Linux**.
  - Choose **Amazon Linux 2023 AMI** (`kernel 6.1`, `x86_64`).
- **Instance Type**:
  - Select **`t3.micro`** (2 vCPUs, 1.0 GiB RAM, Free Tier eligible for new accounts).
  - *Note: If using AWS Graviton, choose `t4g.micro` with `arm64` architecture.*
- **Key Pair (Login)**:
  - Select an existing key pair or click **Create new key pair**.
  - Key pair name: `image-prep-ec2-key`
  - Key pair type: **RSA**
  - Private key file format: **`.pem`** (for OpenSSH on Windows 11 / Linux / macOS).
  - Download and save the `.pem` file to a secure local folder (e.g. `C:\Users\<user>\.ssh\`).

### Step 3: Network & Security Group Settings
Under **Network settings**, click **Edit**:
- **VPC**: Select your default VPC (the same VPC where your RDS database resides).
- **Auto-assign public IP**: **Enable** (required for public browser and SSH access).
- **Firewall (security groups)**: Choose **Create security group**.
  - Security group name: `ec2-webserver-sg`
  - Description: `Security group for Image Preprocessing Flask Webserver`
  - Configure the inbound rules listed in Section 3 below.

### Step 4: Configure Storage
- **Root Volume**: **10 GiB** General Purpose SSD (`gp3`).
- Leave encryption enabled with default AWS KMS key.

### Step 5: Launch Instance
Click **Launch instance**. Provisioning takes approximately 30–60 seconds.

---

## 3. Security Group Configuration

### A. EC2 Web Server Security Group (`ec2-webserver-sg`)

Configure the following inbound rules:

| Type | Protocol | Port Range | Source | Description |
| :--- | :--- | :--- | :--- | :--- |
| **SSH** | TCP | `22` | **My IP** (`x.x.x.x/32`) | Secure terminal access restricted to your current IP |
| **HTTP** | TCP | `80` | `0.0.0.0/0` | Public web access to Nginx reverse proxy |
| **HTTPS** | TCP | `443` | `0.0.0.0/0` | Secure SSL web access (future/production) |

> ⚠️ **Strict Rule**: Never expose Gunicorn port `8000` or Flask development port `5000` to `0.0.0.0/0`. Nginx handles all public traffic on port `80` and proxies internally to `127.0.0.1:8000`.

### B. Amazon RDS MySQL Security Group (`rds-mysql-sg`)

Ensure the private RDS database authorizes inbound connections from EC2:

| Type | Protocol | Port Range | Source | Description |
| :--- | :--- | :--- | :--- | :--- |
| **MySQL/Aurora** | TCP | `3306` | `ec2-webserver-sg` (SG ID) | Authorizes Flask on EC2 to access MySQL |
| **MySQL/Aurora** | TCP | `3306` | `sg-lambda-processor` | Authorizes AWS Lambda to access MySQL |

> 🔒 **Security Guarantee**: Amazon RDS MySQL remains completely private inside the VPC (`Public access: No`) with zero exposure to `0.0.0.0/0`.

---

## 4. EC2 IAM Instance Role Setup (Keyless S3 Access)

Using an IAM instance role eliminates the need to store static `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` credentials on the EC2 server.

### Step 1: Create IAM Role in AWS Console
1. Navigate to the **IAM Console** > **Roles** > **Create role**.
2. **Trusted entity type**: Select **AWS service**.
3. **Use case**: Select **EC2**, then click **Next**.
4. Click **Create policy** (opens in a new tab):
   - Switch to the **JSON** tab and paste the contents of [`deployment/iam_policy.json`](file:///c:/Users/basan/Desktop/AWS%20Project/deployment/iam_policy.json):
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Sid": "AllowS3ImageUploadAndRead",
         "Effect": "Allow",
         "Action": [
           "s3:PutObject",
           "s3:GetObject"
         ],
         "Resource": [
           "arn:aws:s3:::aws-project-2515/uploads/*",
           "arn:aws:s3:::aws-project-2515/processed/*"
         ]
       },
       {
         "Sid": "AllowS3BucketInspection",
         "Effect": "Allow",
         "Action": [
           "s3:ListBucket",
           "s3:GetBucketLocation"
         ],
         "Resource": [
           "arn:aws:s3:::aws-project-2515"
         ]
       }
     ]
   }
   ```
   - Policy Name: `EC2-S3-ImageProcessing-Policy`
   - Click **Create policy**.
5. Back in the **Create role** tab, refresh and select `EC2-S3-ImageProcessing-Policy`.
6. Role Name: **`EC2-S3-ImageProcessing-Role`**.
7. Click **Create role**.

### Step 2: Attach Role to Your EC2 Instance
1. Go to the **EC2 Console** > **Instances**.
2. Select your instance (`image-preprocessing-webserver`).
3. Click **Actions** > **Security** > **Modify IAM role**.
4. Select **`EC2-S3-ImageProcessing-Role`** and click **Update IAM role**.

---

## 5. Connecting from Windows 11 via OpenSSH

Windows 11 includes OpenSSH Client by default.

### Step 1: Set File Permissions for Key File (Windows PowerShell)
Windows file permissions can be too permissive for SSH keys. Run this in PowerShell:
```powershell
# Navigate to your key folder
cd "$HOME\.ssh"

# Disable inheritance and grant read access strictly to your Windows user account
icacls "image-prep-ec2-key.pem" /inheritance:r /grant:r "$($env:USERNAME):(R)"
```

### Step 2: Connect to EC2
In PowerShell:
```powershell
ssh -i "image-prep-ec2-key.pem" ec2-user@<YOUR-EC2-PUBLIC-IP>
```
Type `yes` when prompted to verify the host authenticity fingerprint.

*(Alternative: You can also use **EC2 Instance Connect** in the AWS Console by clicking the **Connect** button on your instance summary page).*

---

## 6. Transferring Application Source Code to EC2

### Method A: Git Clone (Recommended)
If your repository is hosted on GitHub / GitLab:
```bash
# On EC2:
sudo mkdir -p /var/www/aws-image-preprocessing
sudo chown -R ec2-user:ec2-user /var/www/aws-image-preprocessing
cd /var/www/aws-image-preprocessing

git clone <YOUR-GIT-REPO-URL> .
```

### Method B: SCP Archive Upload (From Windows 11)
From your Windows 11 PowerShell terminal in your project directory:
```powershell
# Create deployment archive (excluding venv and cache)
tar --exclude='venv' --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.git' -czvf app.tar.gz .

# Secure copy to EC2
scp -i "C:\path\to\image-prep-ec2-key.pem" app.tar.gz ec2-user@<YOUR-EC2-PUBLIC-IP>:/tmp/

# Extract on EC2:
ssh -i "C:\path\to\image-prep-ec2-key.pem" ec2-user@<YOUR-EC2-PUBLIC-IP> "sudo mkdir -p /var/www/aws-image-preprocessing && sudo chown -R ec2-user:ec2-user /var/www/aws-image-preprocessing && tar -xzvf /tmp/app.tar.gz -C /var/www/aws-image-preprocessing"
```

---

## 7. Server Provisioning & Deployment Execution

Once connected to your EC2 instance:

```bash
cd /var/www/aws-image-preprocessing

# 1. Make scripts executable
chmod +x deployment/ec2_setup.sh
chmod +x deployment/deploy.sh

# 2. Run initial system provisioning (Installs Python 3, Nginx, virtualenv, dependencies)
./deployment/ec2_setup.sh

# 3. Create production .env configuration file
cp deployment/production.env.example .env
chmod 600 .env

# Edit .env and enter your actual RDS MySQL database password
nano .env
```

Ensure `.env` contains:
```env
FLASK_ENV=production
DEBUG=False
PORT=8000
SECRET_KEY=9a48d8a7c2b3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9
STORAGE_BACKEND=s3
AWS_REGION=ap-south-1
S3_BUCKET_NAME=aws-project-2515
S3_PRESIGNED_URL_EXPIRY=3600
S3_OBJECT_PREFIX=uploads/
DB_HOST=image-preprocessing-db.cn46oieisfo8.ap-south-1.rds.amazonaws.com
DB_PORT=3306
DB_USER=admin
DB_PASSWORD=YOUR_ACTUAL_RDS_PASSWORD
DB_NAME=image_preprocessing
DB_CONNECT_TIMEOUT=10
```

Deploy and activate services:
```bash
./deployment/deploy.sh
```

---

## 8. Service Monitoring & Operational Commands

### Gunicorn WSGI Service
```bash
# Check service status
sudo systemctl status gunicorn

# View real-time application logs
sudo journalctl -u gunicorn -f

# Restart Gunicorn after code updates
sudo systemctl restart gunicorn
```

### Nginx Reverse Proxy
```bash
# Check service status
sudo systemctl status nginx

# Test configuration syntax
sudo nginx -t

# View access and error logs
sudo tail -f /var/log/nginx/image_preprocessing_access.log
sudo tail -f /var/log/nginx/image_preprocessing_error.log

# Reload Nginx configuration without downtime
sudo systemctl reload nginx
```

---

## 9. Verification & Live Acceptance Checklist

Open your browser and navigate to: `http://<YOUR-EC2-PUBLIC-IP>`

- [ ] **Homepage & Navigation**: Application loads with top navigation bar and sidebar.
- [ ] **Dashboard Cards**: Reflects live counts from Amazon RDS MySQL.
- [ ] **System Health**: Navigate to `/health` (or Health tab) — reports `flask: healthy` and `database: connected`.
- [ ] **Image Upload**: Upload a test JPG/PNG file in **Upload Image**.
- [ ] **S3 Verification**: Raw file appears in `s3://aws-project-2515/uploads/`.
- [ ] **Lambda Execution**: CloudWatch logs confirm automated invocation and Pillow transformation.
- [ ] **Processed Storage**: Processed file appears in `s3://aws-project-2515/processed/`.
- [ ] **Database Integrity**: Record status updates from `PENDING` ➔ `PROCESSING` ➔ `COMPLETED`.
- [ ] **Comparison Modal**: Click **View Details** to inspect side-by-side presigned URLs and optimization savings percentage.
- [ ] **Reboot Resilience**: Run `sudo reboot`, wait 60 seconds, and verify the site automatically comes back online.

---

## 10. Cost Management & Resource Safety

> 💡 **Student Budget Warning**: Cloud resources incur costs when left running. Follow this guide to minimize charges.

### Cost Breakdown
| AWS Component | Pricing Model | Optimization Tips |
| :--- | :--- | :--- |
| **EC2 (`t3.micro`)** | ~$0.0104/hr ($7.50/mo if running 24/7) | Free tier covers 750 hrs/mo for first 12 months. |
| **Public IPv4 Address** | $0.005/hr (~$3.60/mo) | AWS charges for all allocated in-use public IPv4 addresses. |
| **EBS Storage (`gp3`)** | $0.08 per GB-month (~$0.80/mo for 10 GB) | Charged whether EC2 is running or stopped! |
| **RDS MySQL (`db.t3.micro`)** | ~$0.017/hr ($12.24/mo) | Free tier covers 750 hrs/mo for first 12 months. |
| **AWS S3** | $0.023 per GB-month | Negligible for small image datasets (<$0.10). |
| **AWS Lambda** | 1M free requests/mo | $0.00 (within free tier). |

### Stopping vs. Terminating EC2
- **Stopping EC2**:
  - Compute hourly charge **stops**.
  - **EBS storage and public IPv4 continue to incur charges**.
  - When restarted, the public IP address will change (unless an Elastic IP is used).
- **Terminating EC2**:
  - Permanently deletes the instance and root EBS volume.
  - Zero ongoing charges for EC2 or root EBS.

### Post-Demonstration Cleanup Checklist
When you have finished testing or presenting your project:
1. **Stop EC2**: If demonstrating again tomorrow, go to **EC2 Console** > Select instance > **Instance state** > **Stop instance**.
2. **Stop RDS**: Go to **RDS Console** > Select `image-preprocessing-db` > **Actions** > **Stop temporarily** *(stops compute for up to 7 days)*.
3. **Terminate EC2**: If completed permanently, click **Instance state** > **Terminate instance**.
4. **Delete S3 Objects**: Empty the `uploads/` and `processed/` folders in S3 if no longer needed.

