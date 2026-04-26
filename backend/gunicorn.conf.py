"""
Gunicorn configuration for production (uvicorn worker class).

Usage:
  gunicorn -c gunicorn.conf.py backend.main:app

Or without a config file:
  gunicorn backend.main:app -k uvicorn.workers.UvicornWorker \
    --workers 4 --bind 0.0.0.0:8000 --worker-connections 1000
"""

import multiprocessing

# ── Binding ────────────────────────────────────────────────────
bind = "0.0.0.0:8000"

# ── Workers ────────────────────────────────────────────────────
# Standard formula: 2 × CPU cores + 1
# Cap at 8 so ML model RAM usage stays manageable
workers = min(multiprocessing.cpu_count() * 2 + 1, 8)
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000

# ── Timeouts ───────────────────────────────────────────────────
# Reports endpoint can take a few seconds on first load (PDF gen)
timeout = 120
keepalive = 5

# ── Logging ────────────────────────────────────────────────────
accesslog = "-"
errorlog = "-"
loglevel = "info"
