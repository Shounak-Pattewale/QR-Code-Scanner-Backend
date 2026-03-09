"""
decoder/pipeline.py
-------------------
Builds preprocessing variants from a raw image and runs the decoder
chain across each one, stopping at the first success.

Variant order (cheapest to most aggressive):
    1.  original
    2.  downscaled         — prevents OOM on huge phone photos
    3.  grayscale
    4.  upscaled 2x        — helps thin/small barcodes
    5.  adaptive_thresh    — best for uneven lighting
    6.  thresh_binary      — best for clean, uniform labels
    7.  thresh_otsu        — automatic level selection
    8.  clahe              — local contrast for fluorescent lighting
    9.  sharpened          — blurry / out-of-focus labels
    10. inverted           — light bars on dark background
    11. inv_thresh         — inverted + threshold combo
    12. sharpened_rot_90   — label photographed sideways
    13. sharpened_rot_180  — label photographed upside-down
    14. sharpened_rot_270

Dependencies: image_utils.py, decoders.py
"""

from __future__ import annotations

import logging

import numpy as np

from .image_utils import (
    constrain, to_gray, upscale,
    adaptive_threshold, binary_threshold, otsu_threshold,
    clahe, sharpen, invert, rotate,
)
from .decoders import try_pyzbar, try_pylibdmtx, try_zxing


logger = logging.getLogger(__name__)


def build_variants(original: np.ndarray) -> list[tuple[str, np.ndarray]]:
    """
    Build all preprocessing variants from the original image.
    Returns a list of (name, ndarray) tuples in pipeline order.
    """
    variants: list[tuple[str, np.ndarray]] = []

    variants.append(("original", original))

    # Downscale large inputs to prevent memory exhaustion
    base = constrain(original)
    if base.shape != original.shape:
        variants.append(("downscaled", base))

    gray = to_gray(base)
    variants.append(("grayscale", gray))

    variants.append(("upscaled_2x",     upscale(gray)))
    variants.append(("adaptive_thresh", adaptive_threshold(gray)))
    variants.append(("thresh_binary",   binary_threshold(gray)))
    variants.append(("thresh_otsu",     otsu_threshold(gray)))
    variants.append(("clahe",           clahe(gray)))

    sharpened = sharpen(adaptive_threshold(gray))
    variants.append(("sharpened", sharpened))

    inverted = invert(gray)
    variants.append(("inverted",   inverted))
    variants.append(("inv_thresh", binary_threshold(inverted)))

    for angle in (90, 180, 270):
        variants.append((f"sharpened_rot_{angle}", rotate(sharpened, angle)))

    return variants


def run_decoder_chain(image: np.ndarray, variant_name: str) -> dict | None:
    """
    Run all three decoders on a single image variant.
    Returns on the first success, None if all fail.

    Order: pyzbar → pylibdmtx → ZXing
    pylibdmtx is before ZXing because the client uses GS1 DataMatrix
    labels frequently, which pylibdmtx handles better and faster.
    """
    logger.debug("Trying variant: %s", variant_name)

    for decoder_fn in (try_pyzbar, try_pylibdmtx, try_zxing):
        result = decoder_fn(image)
        if result:
            result["variant"] = variant_name
            logger.info(
                "%s hit on '%s': %.60s",
                result["engine"], variant_name, result["code"]
            )
            return result

    return None


def run(image_bytes: bytes) -> dict:
    """
    Main pipeline entry point.

    Accepts raw image bytes, builds all variants, runs decoders,
    and returns a structured result dict.

    Always returns a dict — never raises to the caller.

    Success:
        {"found": True,  "code": "...", "engine": "...",
         "type": "...", "variant": "..."}

    Failure:
        {"found": False, "code": "", "engine": "",
         "type": "", "variant": ""}
    """
    from .image_utils import load_from_bytes

    empty = {"found": False, "code": "", "engine": "", "type": "", "variant": ""}

    try:
        original = load_from_bytes(image_bytes)
        variants = build_variants(original)

        for variant_name, variant_image in variants:
            result = run_decoder_chain(variant_image, variant_name)
            if result:
                return {
                    "found":   True,
                    "code":    result["code"],
                    "engine":  result["engine"],
                    "type":    result["type"],
                    "variant": result["variant"],
                }

        logger.info("All variants exhausted — decode failed.")
        return empty

    except ValueError as exc:
        logger.error("Pipeline error: %s", exc)
        return empty
    except Exception as exc:
        logger.exception("Pipeline unexpected error: %s", exc)
        return empty
