"""
Gunicorn Production Configuration
Automated Image Preprocessing System Using AWS - Module 7

Configuration file for Gunicorn WSGI server executing on AWS EC2.
Bound to 127.0.0.1:8000 behind Nginx reverse proxy.
"""

import multiprocessing
import os

# Server Socket Binding
# Gunicorn binds to internal localhost interface only; Nginx handles public traffic on port 80/443
bind = os.getenv("GUNICORN_BIND", "127.0.0.1:8000")
backlog = 2048

# Worker Processes
# Standard formula: 2 x CPU cores + 1. For t3.micro (2 vCPUs), this yields 3-4 workers.
cpu_count = multiprocessing.cpu_count()
workers = int(os.getenv("GUNICORN_WORKERS", max(2, min(4, cpu_count * 2 + 1))))
threads = int(os.getenv("GUNICORN_THREADS", 2))
worker_class = "sync"

# Worker Lifecycle & Memory Protection
# Periodically restarts workers after serving requests to prevent memory leaks on micro instances
max_requests = 1000
max_requests_jitter = 100
timeout = 120  # Allows up to 2 minutes for 10 MB image upload & S3 streaming
keepalive = 5
graceful_timeout = 30

# Logging
# Log to standard streams to integrate with systemd/journalctl
accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" (%(D)s µs)'
capture_output = True

# Process Naming
proc_name = "aws_image_preprocessing"

