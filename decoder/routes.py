"""
decoder/routes.py
-----------------
Flask blueprint exposing two endpoints:

    GET  /decoder/ping
        Health check. Returns app status and which decoder
        libraries are available on this machine.

    POST /decoder/decode
        Upload an image file, get a decoded barcode back.
        Accepts multipart/form-data with field name "image".
        Also accepts raw image bytes in the request body.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from .pipeline import run as run_pipeline


logger     = logging.getLogger(__name__)
decoder_bp = Blueprint("decoder", __name__, url_prefix="/decoder")


# ---------------------------------------------------------------------------
# GET /decoder/ping
# ---------------------------------------------------------------------------

@decoder_bp.get("/ping")
def ping():
    """
    Health check endpoint.

    Returns:
        200 — app is running, with library availability flags so you
              can confirm pyzbar / pylibdmtx / ZXing are installed
              before sending real images.

    Example response:
        {
            "status": "ok",
            "libraries": {
                "pyzbar":      true,
                "pylibdmtx":   true,
                "zxing_jars":  false
            }
        }
    """
    libraries = {
        "pyzbar":     _check_pyzbar(),
        "pylibdmtx":  _check_pylibdmtx(),
        "zxing_jars": _check_zxing_jars(),
    }
    return jsonify({"status": "ok", "libraries": libraries}), 200


# ---------------------------------------------------------------------------
# POST /decoder/decode
# ---------------------------------------------------------------------------

@decoder_bp.post("/decode")
def decode():
    """
    Decode a barcode / QR / DataMatrix from an uploaded image.

    Accepts:
        multipart/form-data  — field name: "image"
        application/octet-stream — raw bytes in request body

    Returns 200 whether or not a code was found (check "found" field).
    Returns 400 if no image was provided or the file is empty.

    Success response:
        {
            "found":   true,
            "code":    "0104600494519598...",
            "engine":  "pyzbar",
            "type":    "CODE128",
            "variant": "adaptive_thresh"
        }

    Failure response (image received but no code found):
        {
            "found":   false,
            "code":    "",
            "engine":  "",
            "type":    "",
            "variant": ""
        }
    """
    image_bytes = _extract_image_bytes(request)

    if image_bytes is None:
        return jsonify({"error": "No image provided. Send a file under the 'image' field "
                                 "or raw bytes in the request body."}), 400

    if len(image_bytes) == 0:
        return jsonify({"error": "Image file is empty."}), 400

    logger.info("Received image — %d bytes", len(image_bytes))

    result = run_pipeline(image_bytes)

    if result["found"]:
        logger.info("Decode success — engine: %s, variant: %s",
                    result["engine"], result["variant"])
    else:
        logger.info("Decode failed — all variants exhausted.")

    return jsonify(result), 200


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_image_bytes(req) -> bytes | None:
    """
    Extract image bytes from the request.

    Tries multipart form field "image" first, then falls back to the
    raw request body. Returns None if nothing useful is found.
    """
    # Multipart file upload
    if "image" in req.files:
        file = req.files["image"]
        if file.filename:
            return file.read()

    # Raw body (e.g. from mobile apps posting directly)
    if req.data:
        return req.data

    return None


def _check_pyzbar() -> bool:
    try:
        from pyzbar.pyzbar import decode  # noqa: F401
        return True
    except ImportError:
        return False


def _check_pylibdmtx() -> bool:
    try:
        from pylibdmtx.pylibdmtx import decode  # noqa: F401
        return True
    except ImportError:
        return False


def _check_zxing_jars() -> bool:
    from .decoders import ZXING_CORE_JAR, ZXING_JAVASE_JAR
    return ZXING_CORE_JAR.exists() and ZXING_JAVASE_JAR.exists()
