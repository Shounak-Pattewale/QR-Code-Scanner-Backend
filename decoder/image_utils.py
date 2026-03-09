"""
decoder/image_utils.py
----------------------
OpenCV image preprocessing passes used to build variants before decoding.

Each function takes an ndarray and returns a new ndarray.
The source image is never mutated.

Why multiple variants?
    Real-world package labels are blurry, faded, poorly lit, or printed
    on reflective/damaged surfaces. Running the same decoders on different
    preprocessed versions dramatically improves the decode success rate.
"""

import cv2
import numpy as np


# Maximum pixel dimension (longest side) before downscaling on input.
# Prevents memory exhaustion from large phone photos on the server.
MAX_INPUT_DIM = 2000

# Scale factor used for the upscale variant.
UPSCALE_FACTOR = 2.0


def load_from_bytes(data: bytes) -> np.ndarray:
    """
    Decode raw image bytes (JPEG, PNG, etc.) into an OpenCV BGR array.

    Raises ValueError if the bytes cannot be decoded into a valid image.
    """
    arr   = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not decode image — unsupported format or corrupt data.")
    return image


def constrain(image: np.ndarray, max_dim: int = MAX_INPUT_DIM) -> np.ndarray:
    """
    Downscale image so its longest side does not exceed max_dim.
    Images already smaller than max_dim are returned unchanged.
    Aspect ratio is always preserved.
    """
    h, w  = image.shape[:2]
    if max(h, w) <= max_dim:
        return image
    scale = max_dim / max(h, w)
    return cv2.resize(image, (max(1, int(w * scale)), max(1, int(h * scale))),
                      interpolation=cv2.INTER_AREA)


def to_gray(image: np.ndarray) -> np.ndarray:
    """
    Convert BGR image to single-channel grayscale.
    No-op if the image is already grayscale.
    """
    if len(image.shape) == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def upscale(image: np.ndarray, scale: float = UPSCALE_FACTOR) -> np.ndarray:
    """
    Upscale image using INTER_CUBIC interpolation.
    Helps thin barcode bars become wide enough for decoders to resolve.
    """
    return cv2.resize(image, None, fx=scale, fy=scale,
                      interpolation=cv2.INTER_CUBIC)


def adaptive_threshold(gray: np.ndarray) -> np.ndarray:
    """
    Adaptive Gaussian threshold — computes a local threshold per pixel
    based on its neighbourhood.

    Best for: uneven lighting, shadows, glossy label surfaces.
    """
    return cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31, 7
    )


def binary_threshold(gray: np.ndarray, level: int = 127) -> np.ndarray:
    """
    Simple global binary threshold.
    Best for: clean, well-lit labels with uniform background.
    """
    _, out = cv2.threshold(gray, level, 255, cv2.THRESH_BINARY)
    return out


def otsu_threshold(gray: np.ndarray) -> np.ndarray:
    """
    Otsu's method — automatically finds the optimal global threshold
    by minimising intra-class intensity variance.
    Best for: bimodal histograms (dark bars on light background).
    """
    _, out = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return out


def clahe(gray: np.ndarray) -> np.ndarray:
    """
    Contrast Limited Adaptive Histogram Equalisation.
    Enhances local contrast without amplifying noise.
    Best for: labels shot under uneven warehouse fluorescent lighting.
    """
    processor = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return processor.apply(gray)


def sharpen(image: np.ndarray) -> np.ndarray:
    """
    Unsharp-mask sharpening via a 3x3 Laplacian kernel.
    Enhances bar edges on blurry or out-of-focus labels.
    """
    kernel = np.array([[0, -1,  0],
                       [-1, 5, -1],
                       [0, -1,  0]])
    return cv2.filter2D(image, -1, kernel)


def invert(image: np.ndarray) -> np.ndarray:
    """
    Invert pixel values.
    Handles labels where bars are lighter than the background
    (common with some thermal printers and faded stickers).
    """
    return cv2.bitwise_not(image)


def rotate(image: np.ndarray, angle: int) -> np.ndarray:
    """
    Rotate image by 90, 180, or 270 degrees clockwise.
    Handles labels photographed sideways or upside-down.
    """
    codes = {90: cv2.ROTATE_90_CLOCKWISE,
             180: cv2.ROTATE_180,
             270: cv2.ROTATE_90_COUNTERCLOCKWISE}
    return cv2.rotate(image, codes[angle]) if angle in codes else image
