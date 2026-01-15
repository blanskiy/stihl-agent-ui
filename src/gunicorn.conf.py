# Simple gunicorn configuration for STIHL Analytics Agent
import multiprocessing
import os

# Binding
bind = "0.0.0.0:50505"

# Workers
num_cpus = multiprocessing.cpu_count()
workers = (num_cpus * 2) + 1
worker_class = "uvicorn.workers.UvicornWorker"

# Timeouts
timeout = 120

# Logging
log_file = "-"
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Performance
max_requests = 1000
max_requests_jitter = 50

# Development mode
if not os.getenv("RUNNING_IN_PRODUCTION"):
    reload = True
