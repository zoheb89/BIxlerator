import yaml
import requests
import base64
import os
import sys
import logging
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_PATH = LOG_DIR / "image_generation.log"

def _setup_logger():
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    logger = logging.getLogger("image_generation")
    logger.setLevel(logging.INFO)
    # Remove existing handlers to ensure a fresh file each run
    for h in list(logger.handlers):
        logger.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass
    fh = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s\t%(levelname)s\t%(message)s"))
    logger.addHandler(fh)
    return logger

LOGGER = _setup_logger()

# Load configurations from config.yml
def load_config(file_path=None):
    file_path = file_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yml")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Config file not found: {file_path}")
    with open(file_path, "r") as file:
        return yaml.safe_load(file)

# Access configurations
config = load_config()
API_KEY = os.getenv("BLXLERATOR_IMAGE_API_KEY") or config["image_api"]["key"]
API_URL = os.getenv("BLXLERATOR_IMAGE_API_URL") or config["image_api"]["url"]
MODEL_NAME = os.getenv("BLXLERATOR_IMAGE_MODEL") or config["image_api"]["model_name"]
PROVIDER = os.getenv("BLXLERATOR_IMAGE_PROVIDER") or config["image_api"]["provider"]

def _strip_data_url_prefix(b64: str) -> str:
    # Handles data URLs like: data:image/png;base64,XXXX
    if b64.startswith("data:"):
        return b64.split(",", 1)[1]
    return b64

def _guess_ext_from_b64(b64: str) -> str:
    # Common signatures
    if b64.startswith("iVBORw0KGgo"):  # PNG
        return ".png"
    if b64.startswith("/9j/"):  # JPEG
        return ".jpg"
    if b64.startswith("R0lGODlh") or b64.startswith("R0lGODdh"):  # GIF
        return ".gif"
    if b64.startswith("UklGR"):  # WebP (RIFF header base64)
        return ".webp"
    return ".png"

def save_base64_images(images, out_dir="outputs", prefix="image"):
    LOGGER.info("Saving %d image(s) to %s with prefix '%s'", len(images or []), out_dir, prefix)
    os.makedirs(out_dir, exist_ok=True)
    saved_paths = []
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    for idx, b64 in enumerate(images or []):
        b64_clean = _strip_data_url_prefix(b64)
        ext = _guess_ext_from_b64(b64_clean)
        filename = f"{prefix}_{ts}_{idx+1}{ext}"
        path = os.path.join(out_dir, filename)
        try:
            with open(path, "wb") as f:
                f.write(base64.b64decode(b64_clean))
            saved_paths.append(path)
            LOGGER.info("Saved image %d -> %s", idx + 1, path)
        except Exception as e:
            LOGGER.error("Failed to save image %d: %s", idx + 1, e)
            print(f"Failed to save image {idx+1}: {e}", file=sys.stderr)
    return saved_paths

def _preview_text(s: str, n: int = 500) -> str:
    if not isinstance(s, str):
        return str(s)
    return s if len(s) <= n else s[:n] + "... [truncated]"

def _redact_headers(headers: dict) -> dict:
    safe = dict(headers or {})
    if "x-api-key" in safe:
        safe["x-api-key"] = "***REDACTED***"
    return safe

# Function to call the API
def call_image_generation_api(text, width, height, timeout=60):
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
    }
    payload = {
        "modelId": MODEL_NAME,
        "provider": PROVIDER,
        "text": text,
        "width": width,
        "height": height,
    }

    # Log the outgoing request (redact API key; preview text)
    LOGGER.info(
        "API Request -> POST %s | headers=%s | payload=%s",
        API_URL,
        _redact_headers(headers),
        {
            "modelId": MODEL_NAME,
            "provider": PROVIDER,
            "width": width,
            "height": height,
            "text_len": len(text or ""),
            "text_preview": _preview_text(text or "", 500),
        },
    )

    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=timeout)
        status = resp.status_code
        ctype = resp.headers.get("Content-Type", "")
        text_preview = _preview_text(resp.text, 2000)
        LOGGER.info("API Response <- status=%s | content-type=%s", status, ctype)
        LOGGER.info("API Response Body Preview: %s", text_preview)
        resp.raise_for_status()
        try:
            data = resp.json()
            # Log brief JSON structure info
            if isinstance(data, dict):
                keys = list(data.keys())
                LOGGER.info("API Response JSON keys: %s", keys)
            else:
                LOGGER.info("API Response JSON type: %s", type(data).__name__)
            return data
        except ValueError:
            LOGGER.error("Response body is not valid JSON")
            return None
    except requests.exceptions.RequestException as e:
        LOGGER.error("Error calling the API: %s", e)
        print(f"Error calling the API: {e}", file=sys.stderr)
        return None

def extract_images_from_response(result):
    # Expected shape based on your sample:
    # { "type": "image", "content": { "images": ["<b64>", ...] }, ... }
    if not result:
        LOGGER.warning("extract_images_from_response called with empty result")
        return []

    try:
        if result.get("type") == "image":
            content = result.get("content", {})
            images = content.get("images") or content.get("image") or []
            if isinstance(images, list):
                LOGGER.info("Extracted %d image(s) from result.content.images", len(images))
                return images
            if isinstance(images, str):
                LOGGER.info("Extracted 1 image from result.content.image")
                return [images]
        # Fallbacks for other shapes
        if "images" in result and isinstance(result["images"], list):
            LOGGER.info("Extracted %d image(s) from result.images", len(result["images"]))
            return result["images"]
        if "image" in result and isinstance(result["image"], str):
            LOGGER.info("Extracted 1 image from result.image")
            return [result["image"]]
    except Exception as e:
        LOGGER.error("Error parsing images from response: %s", e)

    LOGGER.warning("No images found in response structure")
    return []

if __name__ == "__main__":
    # this is a test prompt , during code execution actual prompt will come from the UI.
    text = """generate a chair on moon"""
    width = 1024
    height = 1024

    LOGGER.info("Script started under __main__ with width=%s height=%s", width, height)
    result = call_image_generation_api(text, width, height)
    if not result:
        LOGGER.error("API call returned no result. Exiting with code 1.")
        sys.exit(1)

    images_b64 = extract_images_from_response(result)
    if not images_b64:
        LOGGER.error("No images found in API response.")
        print("No images found in API response.", file=sys.stderr)
        print("Raw response:", result)
        sys.exit(2)

    out_dir = "image_output"
    saved = save_base64_images(images_b64, out_dir=out_dir, prefix="generated")
    if saved:
        LOGGER.info("Saved %d image(s) to %s", len(saved), out_dir)
        print("Saved files:")
        for p in saved:
            print(f"- {p}")
    else:
        LOGGER.error("Failed to save any images. Exiting with code 3.")
        print("Failed to save any images.", file=sys.stderr)
        sys.exit(3)
