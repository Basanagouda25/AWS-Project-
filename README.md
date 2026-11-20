# Automated Image Preprocessing System Using AWS

A production-grade, modular, and cloud-native Python Flask application designed for automated image ingestion, preprocessing, metadata storage, serverless workflow management, real-time operational dashboard analytics, and production deployment on Amazon Web Services (AWS).

---

## 📌 Module Status Overview

- **Module 1: Project Foundation & Environment Setup** — ✅ **COMPLETED & VERIFIED**
- **Module 2: Frontend & Image Upload System** — ✅ **COMPLETED & VERIFIED**
- **Module 3: AWS S3 Cloud Storage Integration** — ✅ **COMPLETED & VERIFIED**
- **Module 4: AWS Lambda Automated Image Processing** — ✅ **COMPLETED & VERIFIED**
- **Module 5: Amazon RDS MySQL Database Integration** — ✅ **COMPLETED & VERIFIED**
- **Module 6: Dashboard & Processing Results** — ✅ **COMPLETED & VERIFIED**
- **Module 7: End-to-End Orchestration & EC2 Deployment** — ✅ **COMPLETED & DEPLOYMENT-READY**

---

## 🚀 Module 7 — AWS EC2 Production Deployment (New)

Module 7 packages and deploys the entire image preprocessing system to an **Amazon Web Services (AWS) EC2** virtual server using a production-grade three-tier architecture: **Nginx** (Reverse Proxy) ➔ **Gunicorn** (WSGI Application Server) ➔ **Flask 3.x** Application Factory.

### Production System Architecture
```text
User / Administrator (Internet)
        │
        ▼ (Port 80 HTTP / 443 HTTPS)
Public IP / Domain on AWS EC2
        │
        ▼
Nginx Web Server Reverse Proxy (/etc/nginx/conf.d/image_preprocessing.conf)
        ├── Direct static asset caching (/static/ ➔ /var/www/aws-image-preprocessing/static/)
        ├── 10 MB client upload body limit enforcement (client_max_body_size 10M)
        └── Reverse proxies application requests to 127.0.0.1:8000
                │
                ▼
Gunicorn WSGI Application Server (3 workers on 127.0.0.1:8000)
        │
        ▼
Flask 3.x WSGI Application (`wsgi:app`)
        ├── AWS S3: Streams raw assets via IAM Role (no static keys stored on disk)
        └── AWS RDS MySQL: Transacts image lifecycle states through private VPC
                │
                ├─────────────────────────────────────────┐
                ▼ (ObjectCreated:Put Event)              ▼ (VPC Port 3306)
        AWS Lambda Preprocessor                 Amazon RDS MySQL
        (Pillow 800×800 JPEG resize)            (`image_records` table)
```

---

### EC2 Production Configuration Summary

| Property | Value | Description |
| :--- | :--- | :--- |
| **AWS Service** | Amazon EC2 | Scalable virtual compute instance |
| **Operating System** | Amazon Linux 2023 (AL2023) | Secure, optimized Linux runtime (Kernel 6.1) |
| **Architecture** | `x86_64` | Standard Intel/AMD 64-bit architecture |
| **Instance Type** | `t3.micro` | 2 vCPUs, 1.0 GiB RAM (Free Tier eligible) |
| **Storage** | 10 GiB General Purpose SSD (`gp3`) | Encrypted root volume |
| **Reverse Proxy** | Nginx 1.24+ | Reverse proxy, static asset cache, 10MB upload limit |
| **WSGI Server** | Gunicorn 21.2+ | Process manager running 3 sync workers on `127.0.0.1:8000` |
| **Service Manager** | Systemd | Auto-restart on reboot or failure (`gunicorn.service`) |
| **S3 Authentication** | EC2 IAM Instance Role | Zero long-term credentials stored on server |
| **Database Network** | Private VPC Subnet | MySQL port 3306 restricted strictly to EC2 Security Group |

---

### Key Production Deployment Deliverables (`deployment/`)

All deployment configurations and automation scripts are located in the `deployment/` directory:

1. **`wsgi.py`**: Production WSGI application entry point for Gunicorn (`wsgi:app`), enforcing `DEBUG = False`.
2. **`deployment/gunicorn.conf.py`**: Production server settings (internal binding to `127.0.0.1:8000`, 3 workers, 120s timeout for image uploads, access/error logging).
3. **`deployment/gunicorn.service`**: Systemd unit file providing automatic process supervision, logging via `journalctl`, and self-healing restart on failure.
4. **`deployment/nginx.conf`**: Nginx site configuration with `client_max_body_size 10M;`, static file caching, and reverse proxy forwarding headers.
5. **`deployment/iam_policy.json`**: Least-privilege IAM policy document granting EC2 access to `s3:PutObject` and `s3:GetObject` on `aws-project-2515`.
6. **`deployment/ec2_setup.sh`**: Automated provisioning script for Amazon Linux 2023 (system update, Python 3.12, venv, Nginx, permissions).
7. **`deployment/deploy.sh`**: Zero-downtime deployment script (pulls source, installs requirements, reloads Nginx/Gunicorn, and runs a curl `/health` probe).
8. **`deployment/production.env.example`**: Secure production environment template.
9. **`deployment/README.md`**: Complete step-by-step deployment runbook.

---

### Security Group Architecture

```text
[Internet: 0.0.0.0/0]
         │
         ├── Port 80 (HTTP) ───► [EC2 Security Group: ec2-webserver-sg]
         ├── Port 443 (HTTPS) ─► [EC2 Security Group: ec2-webserver-sg]
         └── Port 22 (SSH) ────► [EC2 Security Group: Restricted to Developer's IP]
                                             │
                                             ▼ (Port 3306 inside VPC only)
                                 [RDS Security Group: rds-mysql-sg]
                                 (Source: ec2-webserver-sg ID)
```

> 🔒 **Security Guarantee**: Amazon RDS MySQL remains strictly private inside the VPC (`Public access: No`). Port 3306 is accessible ONLY from the EC2 and Lambda security groups.

---

### Cost & Resource Management (Student Demonstration Safety)

| Component | Cost Model | Cleanup / Management |
| :--- | :--- | :--- |
| **EC2 `t3.micro`** | ~$0.0104/hr | Free tier covers 750 hrs/month for 12 months. |
| **Public IPv4 Address** | $0.005/hr (~$3.60/month) | AWS charges for all allocated in-use public IPv4 addresses. |
| **EBS Storage (10 GB gp3)** | $0.08 per GB-month (~$0.80/month) | Billed while stopped or running until terminated! |
| **RDS MySQL `db.t3.micro`**| ~$0.017/hr | Free tier covers 750 hrs/month for 12 months. |

- **Stopping vs. Terminating**:
  - *Stopping EC2* halts hourly compute charges, but EBS root storage and public IPv4 continue billing.
  - *Terminating EC2* permanently deletes the instance and attached root volume, stopping all charges.
- **Post-Demo Shutdown**:
  When your project evaluation is finished, follow the shutdown checklist in `deployment/README.md` to stop or terminate EC2 and temporarily stop RDS to avoid unwanted cloud charges.

---

## 📊 Module 6 — Dashboard & Processing Results

Module 6 introduces a responsive, real-time SaaS administrative dashboard for monitoring image ingestion, automated serverless processing workflows, relational database records, and asset optimization metrics.

### Dashboard Navigation & Views

| View Panel | Description | Key Capabilities |
| :--- | :--- | :--- |
| **1. System Dashboard** | Executive overview & performance dashboard | 4 live summary cards, recent uploads table, AWS stack overview |
| **2. Upload Image** | Ingestion workspace (Modules 2 & 3) | Drag-and-drop dropzone, client/server Pillow validation, direct S3 upload |
| **3. All Images** | Relational catalog data table | Paginated records (10, 25, 50 rows), newest-first sorting, status badges |
| **4. Processing Results** | Optimization gallery | Side-by-side comparison cards, optimization percentage badges, details modal |
| **5. System Health** | Cloud infrastructure diagnostics | Operational status of Flask, RDS MySQL, S3 bucket, and raw `/health` JSON |

---

## 🗄️ Module 5 — AWS RDS MySQL Database Integration

Module 5 integrates **Amazon Relational Database Service (Amazon RDS) MySQL 8.x** into the image processing pipeline. The database acts as the single source of truth for tracking image lifecycle stages (`PENDING` ➔ `PROCESSING` ➔ `COMPLETED` / `FAILED`), preserving image dimensions, storage keys, byte sizes, and timestamps across both the Flask ingestion layer and the AWS Lambda serverless processing engine.

---

## ⚡ Module 4 — AWS Lambda Automated Image Processing

Module 4 implements an automated, event-driven serverless image transformation pipeline using **AWS Lambda** and **Pillow (PIL)**. Whenever an image is uploaded to the S3 bucket under the `uploads/` prefix, AWS S3 automatically invokes the Lambda function to orient, resize, compress, and store the optimized JPEG asset under the `processed/` prefix in the same bucket.

---

## ☁️ Module 3 — AWS S3 Cloud Storage Integration

Module 3 integrates Amazon Web Services (AWS) S3 cloud object storage directly into the ingestion pipeline. Validated image uploads are streamed directly to an Amazon S3 bucket hosted in the **Asia Pacific (Mumbai) `ap-south-1`** region with private bucket access and time-limited presigned GET URLs.

---

## 📌 Module 2: Frontend & Image Upload System

Module 2 provides a complete, secure client-side and server-side image upload pipeline with drag-and-drop, client validation, live preview, and Pillow server verification.

---

## 📌 Module 1: Project Foundation & Environment Setup

Module 1 establishes the production architecture, WSGI structure, blueprints, error handlers, and `/health` diagnostics.

---

## 🛠️ Technology Stack

| Component | Technology | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Language** | Python | 3.12+ | Core runtime environment |
| **Web Framework** | Flask | 3.1.x | Web routing, blueprints & API endpoints |
| **Web Server / Reverse Proxy**| Nginx | 1.24+ | Reverse proxy, static asset caching, upload size limit |
| **WSGI Server** | Gunicorn | 21.2+ | Production WSGI HTTP server (3 sync workers) |
| **Virtual Server** | Amazon EC2 | AL2023 | Cloud host instance in `ap-south-1` (Mumbai) |
| **Serverless Compute** | AWS Lambda | Python 3.12 | Event-driven image preprocessing & thumbnailing |
| **AWS SDK** | Boto3 | 1.43.x | Amazon S3 PutObject, GetObject and Presigned URLs |
| **Relational Database** | Amazon RDS | MySQL 8.0+ | Private transactional metadata persistence |
| **Database Driver** | PyMySQL | 1.2.x | Pure-Python client for RDS MySQL connectivity |
| **Image Processing**| Pillow (PIL) | 10.4.x / 12.2.x | EXIF transpose, aspect resizing, JPEG conversion |
| **Testing** | Pytest | 8.4.x | Automated test suite (102 tests passing) |

---

## 📁 Project Directory Structure

```text
AWS-IMAGE-PREPROCESSING/
│
├── app.py                      # Local development application entry point
├── wsgi.py                     # Production WSGI application entry point for Gunicorn
├── config.py                   # Environment configuration (local/s3/RDS/production)
├── package_lambda.py           # Packager for Linux Pillow + PyMySQL Lambda ZIP
├── requirements.txt            # Project dependencies
├── .env.example                # Template for environment variables (S3, RDS, Flask)
├── .gitignore                  # Git ignore rules (protects .env from version control)
├── README.md                   # Comprehensive project documentation
│
├── deployment/                 # Module 7: Production EC2 Deployment Artifacts
│   ├── README.md               # Step-by-step EC2 launch, deployment, and runbook
│   ├── ec2_setup.sh            # Server provisioning script for Amazon Linux 2023
│   ├── deploy.sh               # Service management & zero-downtime deployment script
│   ├── gunicorn.conf.py        # Production Gunicorn configuration (127.0.0.1:8000)
│   ├── gunicorn.service        # Systemd service unit for Gunicorn
│   ├── nginx.conf              # Nginx reverse proxy configuration (port 80)
│   ├── iam_policy.json         # Least-privilege IAM policy for EC2-to-S3 access
│   ├── iam_trust_policy.json   # IAM trust policy for EC2 service role assumption
│   └── production.env.example  # Production environment variable template
│
├── app/                        # Application package
│   ├── __init__.py             # Flask application factory
│   ├── routes/                 # Blueprint route controllers
│   │   └── __init__.py         # Home (/), health (/health), upload (/api/upload), dashboard APIs
│   ├── services/               # Modular service layer
│   │   ├── __init__.py         # Service layer exports
│   │   ├── upload_service.py   # Unified image validation & local/s3/RDS orchestration
│   │   ├── s3_storage_service.py # Dedicated AWS S3 Boto3 integration & presigned URLs
│   │   └── database_service.py # Amazon RDS MySQL transactional client & dashboard queries
│   ├── models/                 # Data representations
│   │   └── __init__.py         # Image record model definition
│   └── utils/                  # Utility helpers
│       └── __init__.py         # API response and file helpers
│
├── templates/                  # Jinja2 HTML templates
│   └── index.html              # Modern SaaS dashboard with sidebar, tables, cards & modal
│
├── static/                     # Static assets
│   ├── css/
│   │   └── style.css           # Cloud theme styling, responsive grid, table, and modal styles
│   ├── js/
│   │   └── main.js             # View switching, pagination, gallery, modal, and upload logic
│   └── images/                 # Image assets
│
├── lambda/                     # AWS Lambda Serverless Functions
│   ├── __init__.py             # Package initializer
│   └── image_processor.py      # Pillow transformation pipeline + RDS status tracking
│
├── dist/                       # Lambda deployment package
│   └── image-preprocessing-lambda.zip # Linux x86_64 Pillow + PyMySQL + Handler
│
├── database/                   # Database scripts
│   └── schema.sql              # MySQL DDL schema for image_records on Amazon RDS
│
├── tests/                      # Automated test suite (102 Tests)
│   ├── __init__.py             # Test package initializer
│   ├── test_app.py             # 18 Pytest unit & integration tests (Modules 1 & 2)
│   ├── test_s3.py              # 12 Pytest unit & integration tests (Module 3 S3)
│   ├── test_lambda_processor.py # 27 Pytest unit tests (Module 4 & 5 Lambda + RDS)
│   ├── test_database_service.py # 17 Pytest unit & integration tests (Module 5 Database)
│   ├── test_dashboard_api.py   # 18 Pytest unit & integration tests (Module 6 Dashboard & Analytics)
│   └── test_deployment_config.py # 10 Pytest deployment unit tests (Module 7 EC2 & Production)
│
└── instance/                   # Local instance configuration and storage
    └── uploads/                # Temporary local storage for ingested images
```

---

## 💻 Running the Application & Tests

### Start Local Development Server
```powershell
.\venv\Scripts\python.exe app.py
```
Open [http://127.0.0.1:5000](http://127.0.0.1:5000) or [http://127.0.0.1:5000/dashboard](http://127.0.0.1:5000/dashboard).

### Run Production WSGI Server Locally (Gunicorn)
```powershell
gunicorn --config deployment/gunicorn.conf.py wsgi:app
```

### Run Full Test Suite (102 Tests)
```powershell
.\venv\Scripts\pytest.exe -v
```

```text
============================= 102 passed in 2.22s =============================
```
