"""Entry point for production servers:  gunicorn expense_tracker.wsgi:app"""
import sys

from .config import ConfigError
from .web import create_app

try:
    app = create_app()
except ConfigError as exc:  # fail fast with a clear message instead of a stack trace
    sys.stderr.write(f"CONFIGURATION ERROR: {exc}\n")
    raise SystemExit(3)
