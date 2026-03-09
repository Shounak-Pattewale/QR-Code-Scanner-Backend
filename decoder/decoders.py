"""
decoder/decoders.py
-------------------
Wrappers for the three barcode decoding backends.

Decoder order (used by pipeline.py):
    1. pyzbar      — fastest, no subprocess, handles most 1D + QR
    2. pylibdmtx   — DataMatrix / GS1 DataMatrix specialist
    3. ZXing CLI   — slowest, broadest format support, last resort

All functions return a result dict on success or None on failure.
Exceptions are always caught and logged — decoders never raise to callers.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from pyzbar.pyzbar import decode as pyzbar_decode
from pylibdmtx.pylibdmtx import decode as dmtx_decode


logger = logging.getLogger(__name__)

# ZXing jar paths — override via ZXING_TOOLS_DIR environment variable
_TOOLS_DIR       = Path(os.environ.get("ZXING_TOOLS_DIR", "tools"))
ZXING_CORE_JAR   = _TOOLS_DIR / "core-3.5.3.jar"
ZXING_JAVASE_JAR = _TOOLS_DIR / "javase-3.5.3.jar"
ZXING_TIMEOUT_S  = 10


def try_pyzbar(image: np.ndarray) -> dict | None:
    """
    Attempt decoding with pyzbar (wraps libzbar).

    Handles: Code128, GS1-128, EAN-13, EAN-8, UPC, QR Code,
             PDF417, Code39, ITF and more.
    Does NOT handle DataMatrix — use pylibdmtx for that.
    """
    try:
        results = pyzbar_decode(image)
        for result in results:
            try:
                return {
                    "engine": "pyzbar",
                    "type":   result.type,
                    "code":   result.data.decode("utf-8"),
                }
            except (UnicodeDecodeError, AttributeError):
                continue
    except Exception as exc:
        logger.debug("pyzbar error: %s", exc)
    return None


def try_pylibdmtx(image: np.ndarray) -> dict | None:
    """
    Attempt decoding with pylibdmtx (wraps libdmtx).

    Specialised for DataMatrix and GS1 DataMatrix — the formats most
    commonly used on pharmaceutical and logistics labels.
    pylibdmtx requires a PIL Image rather than an ndarray.
    """
    try:
        pil = (Image.fromarray(image) if len(image.shape) == 2
               else Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)))

        results = dmtx_decode(pil)
        for result in results:
            try:
                return {
                    "engine": "pylibdmtx",
                    "type":   "DataMatrix",
                    "code":   result.data.decode("utf-8"),
                }
            except (UnicodeDecodeError, AttributeError):
                continue
    except Exception as exc:
        logger.debug("pylibdmtx error: %s", exc)
    return None


def try_zxing(image: np.ndarray) -> dict | None:
    """
    Attempt decoding with ZXing Java CLI.

    Broadest format support — used as a last resort because it spawns
    a Java subprocess and writes a temporary file to disk.

    ZXing stdout format:
        file:///tmp/x.png (FORMAT)
        Raw result:
        <decoded value>

    Returns None if jars are missing or Java is not installed.
    """
    if not ZXING_CORE_JAR.exists() or not ZXING_JAVASE_JAR.exists():
        logger.debug("ZXing jars not found at %s — skipping.", _TOOLS_DIR)
        return None

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        cv2.imwrite(tmp_path, image)

        completed = subprocess.run(
            ["java", "-cp", f"{ZXING_CORE_JAR}:{ZXING_JAVASE_JAR}",
             "com.google.zxing.client.j2se.CommandLineRunner", tmp_path],
            capture_output=True, text=True, timeout=ZXING_TIMEOUT_S,
        )

        if completed.returncode != 0 or not completed.stdout:
            return None

        stdout = completed.stdout

        # Extract decoded value — appears after "Raw result:\n"
        value = None
        if "Raw result:" in stdout:
            value = stdout.split("Raw result:\n", 1)[1].split("\n")[0].strip()
        else:
            lines = [l.strip() for l in stdout.splitlines() if l.strip()]
            value = lines[1] if len(lines) > 1 else (lines[0] if lines else None)

        if not value:
            return None

        # Extract barcode format from first line e.g. "file.png (CODE_128)"
        fmt        = "unknown"
        first_line = stdout.splitlines()[0]
        if "(" in first_line and ")" in first_line:
            fmt = first_line.split("(")[1].split(")")[0]

        return {"engine": "zxing", "type": fmt, "code": value}

    except subprocess.TimeoutExpired:
        logger.warning("ZXing timed out after %ss.", ZXING_TIMEOUT_S)
        return None
    except Exception as exc:
        logger.debug("ZXing error: %s", exc)
        return None
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
