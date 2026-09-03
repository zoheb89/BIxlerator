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

# Load configurations from config.yml with fallback
def load_config(file_path=None):
    file_path = file_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yml")
    try:
        with open(file_path, "r") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        # Return default config if file not found
        return {
            "api": {
                "key": "your_api_key_here",
                "url": "your_api_url_here",
                "model_name": "your_model_name_here"
            }
        }

# Access configurations
config = load_config()
API_KEY = os.getenv("BLXLERATOR_LLM_API_KEY") or config["api"]["key"]
API_URL = os.getenv("BLXLERATOR_LLM_API_URL") or config["api"]["url"]
MODEL_NAME = os.getenv("BLXLERATOR_LLM_MODEL") or config["api"]["model_name"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output_data')
LOG_FILE = os.path.join(BASE_DIR, 'log_pii_engine.txt')

API_TIMEOUT = 120
MAX_RETRIES = 3
RETRY_BASE_DELAY = 5

# Ensure output directory exists
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
    """
    Generates a prompt for a GenAI model to detect PII columns based *only* on metadata (column names),
    adhering to global compliance standards.
    """
    return f"""
You are an expert data privacy and compliance analyst, specializing in global regulations like GDPR, CCPA, and HIPAA.
Your task is to analyze the following list of column headers from a dataset and identify which columns are likely to contain Personally Identifiable Information (PII).

**CRITICAL INSTRUCTION: You are only given the column names (metadata). You must infer the potential contents based on these names and your knowledge of common data schemas and global PII definitions. No actual data rows are provided.**

Analyze the column names for indicators of PII, including but not limited to:

1.  **Direct Identifiers:**
    *   Full names (e.g., `FullName`, `customer_name`, `name`)
    *   Email addresses (`email`, `user_email`)
    *   National identification numbers (`ssn`, `national_id`)
    *   Phone numbers (`phone`, `contact_number`)
    *   Mailing or street addresses (`address`, `street`, `city`, `zip_code`)
    *   Account numbers, credit card numbers (`account_no`, `cc_number`)
    *   Driver's license, passport numbers (`drivers_license`, `passport_id`)

2.  **Indirect or Quasi-Identifiers (can identify a person when combined):**
    *   Date of birth (`dob`, `birth_date`)
    *   Full postal codes (`postal_code`)
    *   Geographic location data (`latitude`, `longitude`, `gps_coords`)
    *   Usernames, screen names, and user URLs (`username`, `user_id`, `url`)
    *   IP addresses (`ip_address`)
    *   Device identifiers (`device_id`, `imei`)

3.  **Sensitive PII (Special Category Data under GDPR/HIPAA):**
    *   Race or ethnic origin (`ethnicity`)
    *   Health or medical information (`medical_record_no`, `diagnosis`, `health_status`)
    *   Biometric data (`fingerprint_id`, `face_scan`)
    *   Genetic data (`dna_sequence`)
    *   Religious or philosophical beliefs (`religion`)
    *   Political opinions, trade union membership.

Here is the list of column headers to analyze:
{column_list_str}

Based on your expert analysis of these names, return a JSON array of the column names that are likely to contain PII. Be conservative; if a column name is ambiguous but could plausibly contain PII (e.g., 'details', 'profile_info'), include it.

**Response Format**: Return ONLY a valid JSON array of the identified PII column names. Do not include explanations or any other text.
Example: ["name", "email", "phone", "address", "username", "url"]

Response:
"""

def call_pii_detection_api(column_list_str):
    """
    Call the GenAI API to detect PII columns based on the list of column names.
    """
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

    logging.info("Sending API request for PII detection based on column metadata...")
    logging.info(f"Prompt sent to API (truncated):\n{prompt[:1000]}...")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logging.info(f"API call attempt {attempt}/{MAX_RETRIES}")
            response = requests.post(API_URL, headers=headers, json=payload, timeout=API_TIMEOUT)
            response.raise_for_status()
            resp_json = response.json()
            logging.info(f"Full API Response:\n{json.dumps(resp_json, indent=2)}")

            output_str = resp_json.get("content", "")
            pii_columns = []
            if isinstance(output_str, str):
                json_match = re.search(r'\[.*?\]', output_str, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    try:
                        pii_columns = json.loads(json_str)
                    except json.JSONDecodeError:
                        logging.error(f"Failed to parse extracted JSON string: {json_str}")
                        pii_columns = []
                else:
                    logging.warning(f"Could not find a JSON array in the API response content: {output_str}")
            else:
                 logging.warning(f"API response content was not a string: {output_str}")

            logging.info(f"Successfully parsed PII columns from metadata: {pii_columns}")
            return pii_columns

        except requests.exceptions.RequestException as e:
            logging.error(f"API call failed on attempt {attempt}: {e}")
            if 'response' in locals() and response is not None:
                logging.error(f"Response Status: {response.status_code}, Response Body: {response.text}")
            if attempt >= MAX_RETRIES:
                raise
            time.sleep(RETRY_BASE_DELAY * attempt)
        except Exception as e:
            logging.error(f"An unexpected error occurred during API call: {e}")
            raise
    return []

# =========================
# PII COLUMN SCANNING
# =========================

def scan_pii_columns(file_path):
    """
    Scan a CSV file's metadata (column names) to identify columns likely to contain PII.
    """
    setup_logger()
    logging.info("=== PII Metadata Scan Engine Execution Started ===")
    try:
        logging.info(f"Starting PII metadata scan for file: {file_path}")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        df_header = pd.read_csv(file_path, nrows=0)
        all_columns = df_header.columns.tolist()
        logging.info(f"Extracted {len(all_columns)} column headers for analysis.")

        if not all_columns:
            logging.warning("CSV file contains no columns. Cannot perform PII scan.")
            return []

        column_list_str = json.dumps(all_columns, indent=2)
        pii_columns = call_pii_detection_api(column_list_str)

        valid_pii_columns = [col for col in pii_columns if col in all_columns]
        if len(valid_pii_columns) != len(pii_columns):
            invalid_cols = set(pii_columns) - set(valid_pii_columns)
            logging.warning(f"AI returned some columns that do not exist in the source file: {list(invalid_cols)}")

        logging.info(f"PII metadata scan finished. Detected columns: {valid_pii_columns}")
        return valid_pii_columns

    except Exception as e:
        logging.error(f"An error occurred during PII metadata scan: {e}")
        raise

# =========================
# ENCRYPTION AND DECRYPTION
# =========================

def mask_pii_data(file_path, columns, key, output_dir=OUTPUT_DIR):
    setup_logger()
    logging.info("=== PII Masking Execution Started ===")
    try:
        logging.info(f"Starting PII masking for file: {file_path} on columns: {columns}")
        os.makedirs(output_dir, exist_ok=True)
        if not os.path.exists(file_path): raise FileNotFoundError(f"File not found: {file_path}")
        if not columns: raise ValueError("No columns specified for masking")

        cipher = Fernet(key)
        df = pd.read_csv(file_path, na_filter=False, dtype=str)

        for col in columns:
            col = col.strip()
            if col in df.columns:
                df[col] = df[col].apply(
                    lambda x: cipher.encrypt(x.encode()).decode() if x != '' else x
                )
                logging.info(f"Successfully masked column: {col}")
            else:
                logging.warning(f"Column '{col}' to mask not found in the file")

        base_name = os.path.basename(file_path)
        name_without_ext = os.path.splitext(base_name)[0]
        masked_file_path = os.path.join(output_dir, f"masked_{name_without_ext}.csv")

        df.to_csv(masked_file_path, index=False)
        logging.info(f"Masked file saved at: {masked_file_path}")
        return masked_file_path
    except Exception as e:
        logging.error(f"Error during PII data masking: {e}")
        raise

def unmask_pii_data(file_path, columns, key, output_dir=OUTPUT_DIR):
    setup_logger()
    logging.info("=== PII Unmasking Execution Started ===")
    try:
        logging.info(f"Starting PII unmasking for file: {file_path} on columns: {columns}")
        os.makedirs(output_dir, exist_ok=True)
        if not os.path.exists(file_path): raise FileNotFoundError(f"File not found: {file_path}")
        if not columns: raise ValueError("No columns specified for unmasking")

        cipher = Fernet(key)
        
        df = pd.read_csv(file_path, na_filter=False, dtype=str)

        def decrypt_value(val):
            if val == '':
                return val
            try:
                return cipher.decrypt(val.encode()).decode()
            except (InvalidToken, TypeError, AttributeError):
                logging.warning(f"Could not decrypt value: '{val}'. It might not have been encrypted. Leaving it as is.")
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
        logging.info(f"Unmasked file saved at: {unmasked_file_path}")
        return unmasked_file_path
    except Exception as e:
        logging.error(f"Error during PII data unmasking: {e}")
        raise
