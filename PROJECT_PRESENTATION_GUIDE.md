# Automated Image Preprocessing System Using AWS
## Complete Project Presentation & Viva Defense Guide

---

## 1. 30-Second Elevator Pitch

> *"Respected Professor, my project is an **Automated Image Preprocessing System built on AWS Cloud Infrastructure**. It is designed to solve a major cloud scalability challenge: traditional web servers often crash or run out of memory when multiple users upload high-resolution images simultaneously.*
> 
> *Instead of processing heavy image files synchronously on the web server, my architecture offloads all compute to an **event-driven, serverless pipeline**. When a user uploads a photo, our EC2 server validates it and streams it to **Amazon S3**. S3 immediately triggers an **AWS Lambda function** in the background, which auto-orients, resizes, and compresses the image using Pillow, then stores the optimized version back in S3 and updates an **Amazon RDS MySQL database**. The user monitors everything in real time through a modern SaaS admin dashboard running on **Nginx and Gunicorn**."*

---

## 2. Cloud Architecture Diagram

```text
User Browser / Client
        │
        ▼ (Port 80 HTTP)
Amazon EC2 (t3.micro - Amazon Linux 2023)
        │
        ├── Nginx (Reverse Proxy, Gzip Compression, Caching)
        └── Gunicorn WSGI (Flask 3.x Application Factory)
                │
                ├──────────────────────────────────────────────┐
                ▼ (IAM Role: IMDSv2 - Keyless)                 ▼ (VPC Port 3306)
        Amazon S3 Bucket                                Amazon RDS MySQL
        (aws-project-2515)                              (image_preprocessing)
        uploads/original.jpg                            Status: PENDING
                │
                ▼ (S3 Event: ObjectCreated:Put)
        AWS Lambda Preprocessor
        (image-preprocessing-lambda)
                │
                ├── Downloads raw image from S3 uploads/
                ├── Corrects EXIF rotation & resizes to max 800×800
                ├── Compresses & uploads to S3 processed/
                │
                ▼ (Updates RDS Record via VPC)
        Amazon RDS MySQL
        Status: COMPLETED (85%–99% size reduction saved)
```

---

## 3. The 6-Step Image Lifecycle (Explain This Sequence)

| Step | Action | AWS Service | Technical Detail |
| :---: | :--- | :--- | :--- |
| **1** | **Upload & Validation** | **EC2 (Flask)** | The user uploads a JPG/PNG. Flask and Pillow validate file magic bytes, MIME type, and enforce a 10 MB limit. |
| **2** | **Metadata Persistence** | **Amazon RDS MySQL** | Flask writes an initial record with status **`PENDING`** into the private MySQL database. |
| **3** | **Raw Image Ingestion** | **Amazon S3** | Flask streams the original file to `s3://aws-project-2515/uploads/<uuid>.jpg` using IAM role temporary credentials. |
| **4** | **Event Trigger** | **S3 Event Notification** | S3 detects `ObjectCreated:Put` on prefix `uploads/` and asynchronously triggers the Lambda function. |
| **5** | **Serverless Processing** | **AWS Lambda** | Lambda boots in milliseconds, connects to RDS to update status to **`PROCESSING`**, auto-rotates EXIF tags, resizes the image to 800×800, compresses it, and saves it to `s3://aws-project-2515/processed/<uuid>_processed.jpg`. |
| **6** | **Completion & Audit** | **RDS & Dashboard** | Lambda updates MySQL to **`COMPLETED`** with output dimensions, file sizes, and processing timestamps. The dashboard reflects the update via real-time REST APIs. |

---

## 4. Key Engineering & Security Highlights (What Impresses Evaluators)

1. **Decoupled Asynchronous Serverless Architecture**:
   - The web server never runs heavy image resizing algorithms. If 1,000 images are uploaded simultaneously, EC2 CPU stays near 0% while AWS Lambda scales serverlessly in parallel.
2. **Keyless Security via IAM Instance Profile (Zero Hardcoded Keys)**:
   - Neither the source code nor the EC2 server contains hardcoded `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY`.
   - The EC2 instance retrieves automatically rotating temporary credentials using an **IAM Instance Profile Role** via AWS Instance Metadata Service Version 2 (**IMDSv2**).
3. **Private Database Isolation (Defense-in-Depth)**:
   - Amazon RDS MySQL has **`Public access: No`** and no public IP.
   - Port 3306 is locked down strictly to the EC2 security group and Lambda security group inside the VPC.
4. **Least-Privilege IAM Policy**:
   - The IAM policy only grants `s3:PutObject` and `s3:GetObject` on the specific prefixes (`uploads/*` and `processed/*`) of bucket `aws-project-2515`.
5. **Significant Bandwidth & Storage Optimization**:
   - The system achieves an average of **85% to 99% reduction in file size** while preserving visual fidelity, drastically reducing cloud egress bandwidth costs and mobile page load times.

---

## 5. Live Demonstration Script (Step-by-Step for the Teacher)

1. **Step 1: Show System Health**
   - Click **System Health** in the sidebar.
   - Point out: *"Here you can see both Flask and our private Amazon RDS MySQL database are reported as `healthy` and `connected` with sub-50ms latency."*
2. **Step 2: Show the Live Dashboard**
   - Click **Dashboard**.
   - Point to the 4 summary cards: *"These counts (`Total Images`, `Successfully Processed`, `In-Flight`, `Failed`) are queried live from our Amazon RDS MySQL database."*
3. **Step 3: Upload a Live Photo**
   - Go to **Upload Image**. Select a real photo from your computer (e.g., a 2 MB or 5 MB photo) and click **Upload Image**.
   - Show the prompt: *"The original image was immediately validated, given a UUID4 tracking ID, stored in S3, and a `PENDING` record was created in RDS."*
4. **Step 4: Review Automated Results**
   - Click **Processing Results** (or **All Images**).
   - Show the newly processed image:
     - Point out the original size vs. processed size (e.g. 5 MB &rarr; 40 KB, 99% saved!).
     - Click **View Details / Compare** to open the side-by-side comparison modal showing original vs. compressed quality.

---

## 6. Top 7 Viva / Teacher Questions & Model Answers

### Q1: Why use Amazon S3 instead of saving uploaded images on the EC2 hard drive?
> **Answer**: *"EC2 EBS storage is localized to a single virtual machine, has size limits, and cannot easily trigger serverless pipelines. Storing images in Amazon S3 provides 99.999999999% (11 9's) durability, unlimited elastic scalability, native event notifications to trigger AWS Lambda, and secure time-limited presigned URLs without exposing our bucket publicly."*

### Q2: Why use AWS Lambda for image processing instead of doing it directly in Python Flask?
> **Answer**: *"Image processing using Pillow is CPU- and memory-intensive. If multiple users upload large images simultaneously on EC2, the web application would freeze or exhaust its worker threads. Offloading processing to AWS Lambda achieves a decoupled, event-driven architecture that scales horizontally on demand without consuming web server compute."*

### Q3: How does the Lambda function know when a new image is uploaded?
> **Answer**: *"We configured an **S3 Event Notification** on the bucket. Whenever a new object is created under the `uploads/` prefix (`s3:ObjectCreated:Put`), S3 automatically emits an event that invokes our `image-preprocessing-lambda` function, passing the bucket name and object key in the event JSON."*

### Q4: Why is the RDS database set to 'Public access: No', and how does EC2 connect to it?
> **Answer**: *"For cybersecurity best practices, databases should never have public IP addresses or be exposed to the internet. Both EC2 and RDS reside within the same AWS Virtual Private Cloud (VPC). We configured security group rules that authorize inbound traffic on MySQL port 3306 strictly from the EC2 web server security group and the Lambda security group."*

### Q5: What is the purpose of Nginx in front of Gunicorn?
> **Answer**: *"Nginx acts as a high-performance reverse proxy and web server. It handles client connections, serves static files (`css`, `js`, fonts) directly from disk with gzip compression, enforces the 10 MB request limit, and protects Gunicorn from slow-client attacks. Gunicorn is the WSGI server that executes our Python Flask code."*

### Q6: Where are your AWS access keys stored on the EC2 instance?
> **Answer**: *"We do not store static AWS access keys on EC2. Instead, we follow AWS best practices by attaching an **IAM Instance Profile Role** (`EC2-S3-ImageProcessing-Role`) to the EC2 instance. The Boto3 SDK automatically queries AWS IMDSv2 (`169.254.169.254`) to obtain short-lived, auto-rotating security tokens."*

### Q7: What happens if an uploaded image is corrupted or someone uploads a text file with a .jpg extension?
> **Answer**: *"Our application uses multi-layer validation. First, it validates the file extension and MIME type. Second, it uses Python Pillow (`Image.open(stream).verify()`) to decode and inspect the underlying image data structures. If the file is not a genuine, readable image, it is rejected immediately with HTTP 400 before touching S3 or creating database records."*

