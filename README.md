# Decoder Test App

Standalone Flask API for testing the barcode / QR / DataMatrix decoder pipeline.
No authentication, no database — just upload an image and get a code back.

## Structure

```
decoder_app/
  app.py                  — app factory + entry point
  requirements.txt
  decoder/
    __init__.py
    routes.py             — GET /decoder/ping, POST /decoder/decode
    pipeline.py           — variant builder + pipeline runner
    image_utils.py        — OpenCV preprocessing passes
    decoders.py           — pyzbar, pylibdmtx, ZXing wrappers
```

## Setup

**1. System packages (Ubuntu / WSL)**
```bash
sudo apt-get install -y libzbar0 libdmtx0b libdmtx-dev default-jre
```

**2. Python packages**
```bash
pip install -r requirements.txt
```

**3. ZXing Java jars (optional — last-resort fallback)**
```bash
mkdir -p tools && cd tools
wget https://repo1.maven.org/maven2/com/google/zxing/javase/3.5.3/javase-3.5.3.jar
wget https://repo1.maven.org/maven2/com/google/zxing/core/3.5.3/core-3.5.3.jar
```
If the jars are missing, ZXing is simply skipped — the other decoders still run.

## Run

```bash
python app.py
```

App starts at `http://localhost:5000`.

For HTTPS (required for camera access on mobile), use ngrok:
```bash
ngrok http 5000
```

## Endpoints

### GET /decoder/ping
Health check. Confirms the app is running and shows which libraries are available.

```bash
curl http://localhost:5000/decoder/ping
```

```json
{
    "status": "ok",
    "libraries": {
        "pyzbar":     true,
        "pylibdmtx":  true,
        "zxing_jars": false
    }
}
```

### POST /decoder/decode
Upload an image and get a decoded barcode back.

**Multipart form:**
```bash
curl -X POST http://localhost:5000/decoder/decode \
     -F "image=@/path/to/label.jpg"
```

**Raw bytes:**
```bash
curl -X POST http://localhost:5000/decoder/decode \
     --data-binary @/path/to/label.jpg \
     -H "Content-Type: image/jpeg"
```

**Success response:**
```json
{
    "found":   true,
    "code":    "0104600494519598...",
    "engine":  "pyzbar",
    "type":    "CODE128",
    "variant": "adaptive_thresh"
}
```

**Failure response** (image received but no code found):
```json
{
    "found":   false,
    "code":    "",
    "engine":  "",
    "type":    "",
    "variant": ""
}
```
