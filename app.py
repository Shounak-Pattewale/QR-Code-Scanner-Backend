"""
app.py
------
Entry point for the standalone decoder test app.

Endpoints:
    GET  /decoder/ping    — health check
    POST /decoder/decode  — upload an image, get a barcode back

Usage:
    pip install flask flask-cors opencv-python pyzbar pillow pylibdmtx numpy
    python app.py

Logs:
    Console  — always shown, level INFO by default
    File     — written to logs/decoder.log, rotates at 5MB, keeps 3 backups
    Level    — set LOG_LEVEL env var to DEBUG / INFO / WARNING (default: INFO)

    DEBUG shows every variant attempted.
    INFO  shows only hits and failures.
"""

import logging
import logging.handlers
import os
from pathlib import Path

from flask import Flask
from flask_cors import CORS

from decoder.routes import decoder_bp


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging():
    """
    Configure logging for the app.

    Two handlers:
      1. Console (StreamHandler)  — always on, good for development and ngrok
      2. File (RotatingFileHandler) — written to logs/decoder.log
         Rotates at 5 MB, keeps the last 3 log files.
         Useful for reviewing what happened during a test session.

    Log level is controlled by the LOG_LEVEL environment variable.
    Default is INFO. Set to DEBUG to see every variant attempted.
    """
    log_level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)

    # Create logs/ directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Log format — timestamp, level, module, message
    fmt = logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. Console handler
    console = logging.StreamHandler()
    console.setFormatter(fmt)

    # 2. Rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "decoder.log",
        maxBytes=5 * 1024 * 1024,   # 5 MB per file
        backupCount=3,               # keep decoder.log, decoder.log.1, .2, .3
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    # Apply to the root logger so all modules (decoder.*, flask) are captured
    root = logging.getLogger()
    root.setLevel(log_level)
    root.addHandler(console)
    root.addHandler(file_handler)

    # Quieten noisy Flask/Werkzeug access logs at DEBUG level
    logging.getLogger("werkzeug").setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app():
    app = Flask(__name__)

    # Allow the frontend (port 5000) to call this API (port 5001)
    CORS(app)

    app.register_blueprint(decoder_bp)
    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    setup_logging()

    logger = logging.getLogger(__name__)
    logger.info("Starting decoder app on port 5001")
    logger.info("Log level: %s", os.environ.get("LOG_LEVEL", "INFO"))
    logger.info("Logs also written to: logs/decoder.log")

    app = create_app()
    app.run(debug=False, host="0.0.0.0", port=5001)