import os
import time
import json
import logging
import pandas as pd
import requests
from cryptography.fernet import Fernet, InvalidToken
import yaml
import re

# =========================
# CONFIGURABLE PARAMETERS
# =========================

def load_config(file_path=None):
    file_path = file_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yml")
    try:
        with open(file_path, "r") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        return {
            "api": {
                "key": "",
                "url": "",
                "model_name": ""
            }
        }

config = load_config()
api_config = config.get("api", {}) if isinstance(config, dict) else {}
API_KEY = os.getenv("BIXLERATOR_LLM_API_KEY") or api_config.get("key", "")
API_URL = os.getenv("BIXLERATOR_LLM_API_URL") or api_config.get("url", "")
MODEL_NAME = os.getenv("BIXLERATOR_LLM_MODEL") or api_config.get("model_name", "")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output_data")
LOG_FILE = os.path.join(BASE_DIR, "log_pii_engine.txt")

API_TIMEOUT = 120
MAX_RETRIES = 3
RETRY_BASE_DELAY = 5

os.makedirs(OUTPUT_DIR, exist_ok=True)

# =========================
# LOGGING SETUP
# =========================

def setup_logger():
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, mode="w"),
            logging.StreamHandler()
        ]
    )

# =========================
# GENAI PROMPT AND API CALL
# =========================

def get_pii_detection_prompt(column_list_str):
    """Generate a metadata-only prompt for GenAI-assisted PII classification."""
    return f"""
You are an expert data privacy and compliance analyst, specializing in global regulations like GDPR, CCPA, and HIPAA.
Your task is to analyze the following list of column headers from a dataset and identify which columns are likely to contain Personally Identifiable Information (PII).

CRITICAL INSTRUCTION: You are only given the column names (metadata). You must infer the potential contents based on these names. No actual data rows are provided.

Analyze the column names for indicators of PII, including but not limited to:

1. Direct Identifiers:
   - Full names (FullName, customer_name, name)
   - Email addresses (email, user_email)
   - National identification numbers (ssn, national_id)
   - Phone numbers (phone, contact_number)
   - Mailing or street addresses (address, street, city, zip_code)
   - Account numbers and credit card numbers (account_no, cc_number)
   - Driver's license and passport numbers (drivers_license, passport_id)

2. Indirect or Quasi-Identifiers:
   - Date of birth (dob, birth_date)
   - Postal codes (postal_code)
   - Geographic location data (latitude, longitude, gps_coords)
   - Usernames, screen names and user URLs (username, user_id, url)
   - IP addresses (ip_address)
   - Device identifiers (device_id, imei)

3. Sensitive PII:
   - Race or ethnic origin (ethnicity)
   - Health or medical information (medical_record_no, diagnosis, health_status)
   - Biometric data (fingerprint_id, face_scan)
   - Genetic data (dna_sequence)
   - Religious or philosophical beliefs (religion)
   - Political opinions and trade union membership

Here is the list of column headers to analyze:
{column_list_str}

Return ONLY a valid JSON array containing the original column names that are likely to contain PII.
Be conservative; if a column name is ambiguous but could plausibly contain PII, include it.
Example: ["name", "email", "phone", "address"]

Response:
"""

def call_pii_detection_api(column_list_str):
    """Call the configured GenAI endpoint for metadata-only PII classification."""
    if not API_KEY:
        raise RuntimeError("PII GenAI is not configured: BIXLERATOR_LLM_API_KEY is missing.")
    if not API_URL:
        raise RuntimeError("PII GenAI is not configured: BIXLERATOR_LLM_API_URL is missing.")
    if not MODEL_NAME:
        raise RuntimeError("PII GenAI is not configured: BIXLERATOR_LLM_MODEL is missing.")

    prompt = get_pii_detection_prompt(column_list_str)
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "x-api-key": API_KEY
    }
    payload = {
        "action": "run",
        "modelInterface": "langchain",
        "data": {
            "mode": "chain",
            "text": prompt,
            "files": [],
            "modelName": MODEL_NAME,
            "provider": "azure",
            "systemPrompt": "You are a PII Detection Expert. Respond only with valid JSON arrays.",
            "sessionId": f"session_{int(time.time())}",
            "modelKwargs": {
                "maxTokens": 3000,
                "temperature": 0,
                "streaming": False,
                "topP": 0.9
            }
        }
    }

    setup_logger()
    logging.info("Sending GenAI PII classification request using CSV column metadata only.")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logging.info(f"API call attempt {attempt}/{MAX_RETRIES}")
            response = requests.post(API_URL, headers=headers, json=payload, timeout=API_TIMEOUT)
            response.raise_for_status()
            resp_json = response.json()
            logging.info(f"Full API response received. HTTP {response.status_code}")

            output_str = resp_json.get("content", "")
            if not isinstance(output_str, str):
                raise RuntimeError("PII GenAI response did not contain string content.")

            json_match = re.search(r"\[.*?\]", output_str, re.DOTALL)
            if not json_match:
                raise RuntimeError(f"PII GenAI response did not contain a JSON array: {output_str[:500]}")

            pii_columns = json.loads(json_match.group(0))
            if not isinstance(pii_columns, list) or not all(isinstance(x, str) for x in pii_columns):
                raise RuntimeError("PII GenAI returned an invalid JSON array format.")

            logging.info(f"Successfully classified PII columns: {pii_columns}")
            return pii_columns

        except requests.exceptions.RequestException as e:
            logging.error(f"API call failed on attempt {attempt}: {e}")
            if 'response' in locals() and response is not None:
                logging.error(f"Response Status: {response.status_code}, Response Body: {response.text[:2000]}")
            if attempt >= MAX_RETRIES:
                raise RuntimeError(f"PII GenAI API request failed after {MAX_RETRIES} attempts: {e}") from e
            time.sleep(RETRY_BASE_DELAY * attempt)
        except Exception:
            logging.exception("PII GenAI classification failed.")
            raise

    raise RuntimeError("PII GenAI classification failed unexpectedly.")

# =========================
# PII COLUMN SCANNING
# =========================

def scan_pii_columns(file_path):
    """Read CSV headers only and classify likely PII columns with GenAI."""
    setup_logger()
    logging.info("=== PII Metadata Scan Engine Execution Started ===")
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        df_header = pd.read_csv(file_path, nrows=0)
        all_columns = df_header.columns.tolist()
        logging.info(f"Extracted {len(all_columns)} column headers for analysis.")

        if not all_columns:
            raise ValueError("CSV file contains no columns. Cannot perform PII scan.")

        column_list_str = json.dumps(all_columns, indent=2)
        pii_columns = call_pii_detection_api(column_list_str)
        valid_pii_columns = [col for col in pii_columns if col in all_columns]

        if len(valid_pii_columns) != len(pii_columns):
            invalid_cols = set(pii_columns) - set(valid_pii_columns)
            logging.warning(f"AI returned columns not present in source: {list(invalid_cols)}")

        logging.info(f"PII metadata scan finished. Detected columns: {valid_pii_columns}")
        return valid_pii_columns
    except Exception as e:
        logging.exception(f"An error occurred during PII metadata scan: {e}")
        raise

# =========================
# ENCRYPTION AND DECRYPTION
# =========================

def mask_pii_data(file_path, columns, key, output_dir=OUTPUT_DIR):
    setup_logger()
    logging.info("=== PII Masking Execution Started ===")
    try:
        os.makedirs(output_dir, exist_ok=True)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        if not columns:
            raise ValueError("No columns specified for masking")

        cipher = Fernet(key)
        df = pd.read_csv(file_path, na_filter=False, dtype=str)

        for col in columns:
            col = col.strip()
            if col in df.columns:
                df[col] = df[col].apply(lambda x: cipher.encrypt(x.encode()).decode() if x != '' else x)
                logging.info(f"Successfully masked column: {col}")
            else:
                logging.warning(f"Column '{col}' to mask not found in the file")

        base_name = os.path.basename(file_path)
        name_without_ext = os.path.splitext(base_name)[0]
        masked_file_path = os.path.join(output_dir, f"masked_{name_without_ext}.csv")
        df.to_csv(masked_file_path, index=False)
        return masked_file_path
    except Exception as e:
        logging.exception(f"Error during PII data masking: {e}")
        raise

def unmask_pii_data(file_path, columns, key, output_dir=OUTPUT_DIR):
    setup_logger()
    logging.info("=== PII Unmasking Execution Started ===")
    try:
        os.makedirs(output_dir, exist_ok=True)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        if not columns:
            raise ValueError("No columns specified for unmasking")

        cipher = Fernet(key)
        df = pd.read_csv(file_path, na_filter=False, dtype=str)

        def decrypt_value(val):
            if val == '':
                return val
            try:
                return cipher.decrypt(val.encode()).decode()
            except (InvalidToken, TypeError, AttributeError):
                logging.warning(f"Could not decrypt value: '{val}'. Leaving it unchanged.")
                return val

        for col in columns:
            col = col.strip()
            if col in df.columns:
                df[col] = df[col].apply(decrypt_value)
                logging.info(f"Successfully processed column for unmasking: {col}")
            else:
                logging.warning(f"Column '{col}' to unmask not found in the file")

        base_name = os.path.basename(file_path)
        name_without_ext = os.path.splitext(base_name)[0]
        unmasked_file_path = os.path.join(output_dir, f"unmasked_{name_without_ext}.csv")
        df.to_csv(unmasked_file_path, index=False)
        return unmasked_file_path
    except Exception as e:
        logging.exception(f"Error during PII data unmasking: {e}")
        raise
