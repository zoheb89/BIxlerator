import os
import time
import json
import argparse
import logging
import sys
import yaml
import requests
from pathlib import Path
from datetime import datetime


# Load configurations from config.yml
def load_config(file_path=None):
    file_path = file_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yml")
    with open(file_path, "r") as file:
        return yaml.safe_load(file)

# =========================
# CONFIGURABLE PARAMETERS
# =========================

# Access configurations
config = load_config()
API_KEY = os.getenv("BLXLERATOR_LLM_API_KEY") or config["api"]["key"]
API_URL = os.getenv("BLXLERATOR_LLM_API_URL") or config["api"]["url"]
MODEL_NAME = os.getenv("BLXLERATOR_LLM_MODEL") or config["api"]["model_name"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output_data')
LOG_FILE = os.path.join(BASE_DIR, 'log_map_doc_generator.txt')
API_TIMEOUT = 180
MAX_RETRIES = 4
RETRY_BASE_DELAY = 5

# =========================
# PROMPT TEMPLATE WITH DATE
# =========================

def get_documentation_prompt(qlik_script):
    prompt = "Hello"
    today_str = datetime.now().strftime("%d-%b-%Y")
    qlik_script = qlik_script[:1000]
    return f"""
Create a comprehensive Qlik script documentation file targeting both developers and business analysts. The documentation should be structured in Markdown format with clear headings and tables for readability in a text file.

Generation Date: {today_str}

Given the following Qlik script, analyze it thoroughly and create a professional mapping document that explains both the technical implementation and business purpose:

===== QLIK SCRIPT START =====
{qlik_script}
===== QLIK SCRIPT END =====

## Documentation Requirements

Create a comprehensive mapping document with these precise sections:

1. DOCUMENT TITLE AND PURPOSE
   - Title should include the business function of the script
   - State this document is for both developers and business analysts
   - Include generation date as today's date in dd-mon-yyyy format

2. BUSINESS OVERVIEW
   - Identify the script's primary business purpose
   - List key business questions the script helps answer
   - Summarize the main outputs and their business value

3. DATA FLOW DIAGRAM
   - Create an ASCII diagram showing data flow from sources to outputs
   - Show all intermediate tables and their relationships
   - Use simple box and arrow notation for clarity

4. DATA SOURCES
   - Table format with columns: Source Name | Business Purpose | Technical Details | Location
   - Include all external files, QVDs, Excel sources, and database connections
   - Note any access requirements or refresh frequencies

5. DATA DICTIONARY
   - Provide field definitions for key tables
   - Include both business definitions and technical notes for each field
   - Focus on both input fields and calculated/derived fields

6. BUSINESS RULES
   - Table format with columns: Business Rule | Technical Implementation | Business Impact
   - Extract all business logic embedded in the script
   - For complex formulas, explain both the syntax and business meaning
   - Include any filtering conditions and their business justification

7. SCRIPT STRUCTURE
   - Table with columns: Block | Lines | Developer Notes | Business Purpose
   - Break the script into logical blocks
   - Explain why each section exists from both technical and business perspectives

8. KEY TRANSFORMATIONS
   - Highlight important data transformations with code examples
   - Explain the business value of each transformation
   - Include any complex calculations with explanation

9. TECHNICAL DEPENDENCIES
    - List all dependencies with criticality and impact if unavailable
    - Include file dependencies, variables, and execution order requirements
    - Note any external script dependencies

10. SCRIPT STATISTICS
    - Summary statistics about the script (lines, tables, variables, etc.)
    - Present as a simple bullet list

## Formatting Guidelines
- Use clear Markdown formatting throughout
- Create properly formatted tables with headers and alignment
- Use headings, subheadings, and horizontal rules for clear section separation
- Include code blocks with syntax highlighting for Qlik expressions
- Ensure the document is readable in plain text format
- Balance technical details for developers with business context for analysts
- Use bullet points and numbered lists where appropriate for readability
"""



def reset_log():
    with open(LOG_FILE, "w") as f:
        f.write("=== Document generation log ===\n\n")

def log_api_call(payload, headers):
    try:
        with open(LOG_FILE, "a") as f:
            f.write("\n--- API CALL ---\n")
            f.write(f"Time: {datetime.now()}\n")
            f.write(f"URL: {API_URL}\n")
            f.write(f"Headers: {json.dumps(headers, indent=2)}\n")
            f.write(f"Payload: {json.dumps(payload, indent=2)}\n")
    except Exception as e:
        logging.error(f"Failed to log API call: {str(e)}")

def log_api_response(resp_json, raw_response):
    try:
        with open(LOG_FILE, "a") as f:
            f.write("\n--- API RESPONSE ---\n")
            f.write(f"Time: {datetime.now()}\n")
            f.write(f"Raw Response: {raw_response}\n")
            f.write(f"Parsed Response: {json.dumps(resp_json, indent=2)}\n")
    except Exception as e:
        logging.error(f"Failed to log API response: {str(e)}")

def read_qlik_script(file_path):
    logging.info(f"Reading Qlik script from {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            logging.info(f"Successfully read {len(content)} characters from script file")
            return content
    except FileNotFoundError:
        logging.error(f"File not found: {file_path}")
        raise
    except IOError as e:
        logging.error(f"Error reading file: {str(e)}")
        raise

def call_documentation_api(qlik_script):
    prompt = get_documentation_prompt(qlik_script)
    print("PROMPT LENGTH =", len(prompt))
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
            #"modelName": MODEL_NAME,
            #"provider": "azure",
            "modelName": "qwen.qwen3-32b-v1:0",
            "provider": "bedrock",
            "systemPrompt": "Qlik Documentation Expert",
            "sessionId": f"session_{int(time.time())}",
            "modelKwargs": {
                "maxTokens": 3000,
                "temperature": 0,
                "streaming": False,
                "topP": 0.9
            
            }
        }
    }
    
    logging.info("Sending API request for Qlik script documentation")
    log_api_call(payload, headers)
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logging.info(f"API call attempt {attempt}/{MAX_RETRIES}")
            print("DOC URL =", API_URL)
            print("DOC MODEL =", MODEL_NAME)
            import json
            print(json.dumps(payload, indent=2))
            print("PROMPT LENGTH =", len(prompt))
            response = requests.post(
                API_URL, 
                headers=headers, 
                json=payload, 
                timeout=API_TIMEOUT,
                verify=True
            )
            print("STATUS =", response.status_code)
            print("RAW RESPONSE =", response.text[:2000])
            response.raise_for_status()
            raw_response = response.text
            resp_json = response.json()
            log_api_response(resp_json, raw_response)
            
            response_text = ""
            if 'content' in resp_json:
                response_text = resp_json['content']
            elif 'data' in resp_json and 'output' in resp_json['data']:
                response_text = resp_json['data']['output']
            elif 'output' in resp_json:
                response_text = resp_json['output']
            else:
                error_msg = f"Unexpected API response structure: {json.dumps(resp_json, indent=2)}"
                logging.error(error_msg)
                if attempt == MAX_RETRIES:
                    raise Exception(error_msg)
                continue
                
            logging.info(f"API call successful, received {len(response_text)} characters")
            return response_text
            
        except requests.exceptions.HTTPError as e:
            logging.error(f"HTTP error on attempt {attempt}: {str(e)}")
            if hasattr(e.response, "status_code") and e.response.status_code == 429:
                wait_time = RETRY_BASE_DELAY * attempt
                logging.warning(f"API rate limited (HTTP 429). Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
            elif attempt == MAX_RETRIES:
                raise Exception(f"All API call attempts failed. Last error: {str(e)}")
                
        except requests.exceptions.Timeout as e:
            logging.error(f"Timeout error on attempt {attempt}: {str(e)}")
            wait_time = RETRY_BASE_DELAY * attempt
            logging.warning(f"API request timeout. Waiting {wait_time} seconds before retrying...")
            time.sleep(wait_time)
            if attempt == MAX_RETRIES:
                raise Exception(f"All API call attempts timed out. Last error: {str(e)}")
                
        except requests.exceptions.ConnectionError as e:
            logging.error(f"Connection error on attempt {attempt}: {str(e)}")
            wait_time = RETRY_BASE_DELAY * attempt
            logging.warning(f"Connection error. Waiting {wait_time} seconds before retrying...")
            time.sleep(wait_time)
            if attempt == MAX_RETRIES:
                raise Exception(f"All API call attempts failed with connection errors. Last error: {str(e)}")
                
        except Exception as e:
            logging.error(f"Unexpected error on attempt {attempt}: {str(e)}")
            wait_time = RETRY_BASE_DELAY * attempt
            logging.warning(f"Unexpected error. Waiting {wait_time} seconds before retrying...")
            time.sleep(wait_time)
            if attempt == MAX_RETRIES:
                raise Exception(f"All API call attempts failed with unexpected errors. Last error: {str(e)}")
    
    raise Exception("All API call attempts failed")

def write_documentation_file(documentation, script_path):
    output_filename = f"{Path(script_path).stem}_documentation.md"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    
    logging.info(f"Writing documentation to {output_path}")
    
    try:
        with open(output_path, 'w', encoding='utf-8') as file:
            file.write(documentation)
        logging.info(f"Successfully wrote {len(documentation)} characters to documentation file")
        return output_path
    except IOError as e:
        logging.error(f"Error writing documentation file: {str(e)}")
        raise

def generate_qlik_documentation(script_path):
    try:
        start_time = time.time()
        logging.info(f"Starting documentation generation for {script_path}")
        
        qlik_script = read_qlik_script(script_path)
        documentation = call_documentation_api(qlik_script)
        output_path = write_documentation_file(documentation, script_path)
        
        execution_time = time.time() - start_time
        logging.info(f"Documentation generation completed in {execution_time:.2f} seconds")
        
        success_message = f"""
Documentation generation successful!

Input file: {script_path}
Output file: {output_path}
Execution time: {execution_time:.2f} seconds
Documentation length: {len(documentation)} characters

The mapping document provides a comprehensive analysis of the Qlik script 
for both developers and business analysts.
"""
        return output_path, success_message
        
    except Exception as e:
        logging.exception("Documentation generation failed")
        error_message = f"Error generating Qlik script documentation: {str(e)}"
        return None, error_message


def main():
    parser = argparse.ArgumentParser(description='Generate documentation for a Qlik script')
    parser.add_argument('script_path', help='Path to the Qlik script file')
    
    reset_log()  # Overwrite log file at each run

    # Setup logging AFTER resetting log file
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, mode='a'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    try:
        args = parser.parse_args()
        output_path, message = generate_qlik_documentation(args.script_path)
        
        if output_path:
            print("\n" + "="*50)
            print("SUCCESS")
            print("="*50)
            print(message)
        else:
            print("\n" + "="*50)
            print("ERROR")
            print("="*50)
            print(message)
            sys.exit(1)
            
    except Exception as e:
        logging.exception("Unhandled exception in main")
        print(f"An unexpected error occurred: {str(e)}")
        print(f"See log file for details: {LOG_FILE}")
        sys.exit(1)

if __name__ == "__main__":
    main()
