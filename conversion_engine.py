import os
import time
import json
import re
import yaml
import requests
import pandas as pd
from pathlib import Path
try:
    from qvd import qvd_reader
except ImportError:
    qvd_reader = None


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
LOG_FILE = os.path.join(BASE_DIR, 'conversion_emgine.txt')

BATCH_SIZE = 3
MAX_RETRIES = 4
RETRY_BASE_DELAY = 5
API_TIMEOUT = 20


STRICT_SYSTEM_PROMPT = """
You are a Qlik-to-DAX conversion expert. Your task is to convert each QlikView expression into an accurate and optimized Power BI DAX expression.

## Conversion Rules:
- Output only the DAX expression as plain text.
- Use appropriate DAX functions based on the QlikView logic:
  ### Set Analysis:
    - Use CALCULATE for context transitions.
    - Use FILTER for conditional logic.
    - Use IN, =, <>, >=, <= for comparisons.
    - Use CONTAINSSTRING for wildcards (e.g., "*Manager*").
    - Use logical operators (&&, ||) for compound conditions.
  ### Aggregations:
    - Use SUM, COUNT, AVERAGE, MIN, MAX for simple aggregations.
    - Use SUMX, COUNTX, AVERAGEX, MAXX, MINX for row-context or nested aggregations.
    - Use SUMMARIZE to replicate AGGR behavior.
  ### Conditional Logic:
    - Use SWITCH(TRUE(), ...) for Pick/Match or nested IFs.
    - Use IF for binary conditions.
  ### Time Intelligence:
    - Use TODAY(), YEAR(), MONTH(), DATEADD, DATEDIFF for date-based logic.
    - Use OFFSET or PREVIOUSYEAR for Above(), Before(), etc.
  ### String & Wildcard Matching:
    - Use CONTAINSSTRING, SEARCH, LEFT, RIGHT, LEN for string manipulation.
  ### Calculated Dimensions:
    - Use ADDCOLUMNS, SELECTCOLUMNS, or calculated columns in models.
  ### Synthetic Keys / Composite Keys:
    - Use RELATEDTABLE, TREATAS, or bridge tables if needed.

## Output Format:
Return results as a JSON list:
[
    {
        "index": 0,
        "dax_expression": "converted DAX or empty if cannot convert",
        "comment": "empty if converted successfully, or detailed expert recommendation if not"
    },
    ...
]

## Fallback Behavior:
If direct conversion is not possible:
- Leave "dax_expression" empty.
- Provide a detailed, step-by-step expert recommendation in "comment", including:
  - Why direct conversion is not feasible.
  - A suggested workaround or alternative DAX logic, with example code.
  - Guidance on required table structure, columns, or row context.
  - Any limitations or considerations for the manual approach.
  - Avoid generic comments. Always provide actionable, technical advice tailored to the specific QlikView expression.

## Additional Notes:
- Do not include any explanation outside the JSON structure.
- Do not summarize or repeat the input expressions.
- Focus on precision, performance, and readability of the DAX output.
- Ensure compatibility with Power BI Desktop syntax.
"""

QLIK_TO_PYTHON_PROMPT_TEMPLATE = """
You are an expert in both Qlik scripting and Python programming. Your task is to convert the provided Qlik script into Python code with 100% accuracy, ensuring that all business logic, data transformations, calculations, and data flows are preserved exactly as in the original Qlik script.

**Instructions:**
- Carefully analyze the Qlik script and identify all functions, expressions, variables, data loading, transformations, aggregations, set analysis, and control flow logic.
- For every Qlik function (including but not limited to: LOAD, RESIDENT, JOIN, CONCATENATE, APPLYMAP, MAPPING, GROUP BY, IF, PICK, WILDMATCH, MATCH, EXISTS, PEEK, PREVIOUS, AUTOGENERATE, INLINE, LET/SET variables, FOR/NEXT loops, WHILE loops, SUB routines, Section Access, Date/Time functions, String functions, Numeric functions, Aggregation functions, Set Analysis, and any custom expressions), provide an equivalent implementation in Python.
- Use pandas for all data loading, transformation, and manipulation tasks.
- If a Qlik function does not have a direct Python equivalent, implement a custom Python function that replicates its behavior exactly.
- Maintain the same data flow, logic, and structure as the original Qlik script.
- Ensure all variables, control flow (loops, conditions), and script sections are faithfully translated.
- Comment the Python code to indicate which part of the Qlik script each section corresponds to.
- If the Qlik script references external data sources (CSV, Excel, SQL, etc.), use pandas to load the data and specify the file path as a variable.
- For Section Access, implement equivalent row-level security logic in Python using pandas.
- For Qlik's set analysis and advanced aggregations, use pandas groupby, filtering, and aggregation functions to achieve the same result.
- For Qlik's mapping tables and ApplyMap, use pandas merge or map functions.
- For Qlik's variable assignments (LET/SET), use Python variables.
- For Qlik's script errors or null handling, use appropriate pandas or Python error handling.
- Ensure the output Python code is ready to run without any modifications and produces the same results as the original Qlik script.
- Do not omit or reinterpret any logic, calculation, or transformation.
- The Python code must be 100% compatible with standard Python 3.x and pandas.
- If any assumptions are made, clearly state them in comments.

**Additional Requirements:**
- If the Qlik script loads or saves `.qvd` files, replace all such references with `.csv` in the Python code.
- Add a comment wherever a `.qvd` file is referenced, stating: "QVD must be converted to CSV for processing."
- Output only the Python code, starting from the first import statement and ending at the last line of code. Do not include any explanations, markdown, or extra comments outside the code.

**Input Qlik Script:**
{qlik_script}

**Output:**
- Fully functional Python code that performs exactly the same logic and data processing as the input Qlik script.
- Detailed comments mapping each Python section to the original Qlik script logic and functions.
- Any custom Python functions required to replicate Qlik-specific behavior.
- Clear instructions for any required external files or dependencies.

**Example Output Structure:**
# Section: Data Load (Qlik LOAD statement)
# Section: Variable Assignment (Qlik LET/SET)
# Section: Data Transformation (Qlik JOIN, CONCATENATE, etc.)
# Section: Aggregation and Set Analysis
# Section: Output/Export

**Remember:** The goal is to achieve a 100% accurate, bug-free, and ready-to-run Python script that mirrors the Qlik script logic in every detail.
"""

os.makedirs(OUTPUT_DIR, exist_ok=True)

_processing_lock = False
api_call_count = 0
api_responses = []

def reset_log():
    with open(LOG_FILE, "w") as f:
        f.write("=== Qlik to DAX Conversion Log ===\n\n")

reset_log()

def reset_processing_lock():
    global _processing_lock
    _processing_lock = False

def reset_api_tracking():
    global api_call_count, api_responses
    api_call_count = 0
    api_responses = []

def get_api_summary():
    global api_call_count, api_responses
    summary = f"Total API calls made: {api_call_count}\n\n"
    for i, response in enumerate(api_responses, 1):
        summary += f"API Call {i}:\n"
        summary += f"Status: {response['status']}\n"
        summary += f"Expressions processed: {response['batch_size']}\n"
        summary += f"Response length: {len(response['response'])} characters\n"
        summary += f"Response preview: {response['response'][:200]}...\n"
        summary += "-" * 50 + "\n"
    return summary

def ask_llm_batch(expressions_batch, context):
    global api_call_count, api_responses
    api_call_count += 1
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "x-api-key": API_KEY
    }
    batch_text = ""
    for i, expr in enumerate(expressions_batch):
        cleaned_expr = re.sub(r'"+', '"', str(expr))
        cleaned_expr = cleaned_expr.replace('"""', "'").replace('""', "'").replace('\n', ' ').strip()
        batch_text += f"{i}: {cleaned_expr}\n\n"
    context = context[:1500]
    prompt = (
        f"{STRICT_SYSTEM_PROMPT}\n\n"
        f"Context:\n{context}\n\n"
        f"Convert the following QlikView expressions to Power BI DAX expressions. "
        f"Start each response with the index number followed by a colon, then the DAX expression:"
        f"\n\n{batch_text}"
    )
    payload = {
        "action": "run",
        "modelInterface": "langchain",
        "data": {
            "mode": "chain",
            "text": prompt,
            "files": [],
            "modelName": MODEL_NAME,
            "provider": "azure",
            "systemPrompt": "STRICT_SYSTEM_PROMPT",
            "sessionId": f"session_{int(time.time())}",
            "modelKwargs": {
                "maxTokens": 4096,
                "temperature": 0,
                "streaming": False,
                "topP": 0.9
            }
        }
    }
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"API call #{api_call_count} for {len(expressions_batch)} expressions, attempt {attempt}/{MAX_RETRIES}")
        try:
            response = requests.post(
                API_URL, 
                headers=headers, 
                json=payload, 
                timeout=API_TIMEOUT,
                verify=True
            )
            response.raise_for_status()
            resp_json = response.json()
            response_text = ""
            status = "Success"
            if 'content' in resp_json:
                response_text = resp_json['content']
            elif 'data' in resp_json and 'output' in resp_json['data']:
                response_text = resp_json['data']['output']
            elif 'output' in resp_json:
                response_text = resp_json['output']
            elif 'message' in resp_json:
                response_text = f"API Error: {resp_json['message']}"
                status = "Error"
            else:
                response_text = f"Unexpected API response: {resp_json}"
                status = "Unexpected"
            with open(LOG_FILE, "a") as logf:
                logf.write(f"\n--- API Call #{api_call_count} ---\n")
                logf.write(f"Batch: {expressions_batch}\n")
                logf.write(f"Response:\n{response_text}\n")
                logf.write(f"Status: {status}\n")
                logf.write(f"Timestamp: {time.ctime()}\n")
                logf.write("-" * 40 + "\n")
            api_responses.append({
                "status": status,
                "batch_size": len(expressions_batch),
                "response": response_text,
                "timestamp": time.time()
            })
            print(f"API call #{api_call_count} completed - Status: {status}")
            return response_text, True
        except requests.exceptions.HTTPError as e:
            if hasattr(e.response, "status_code") and e.response.status_code == 429:
                print(f"API rate limited (HTTP 429). Waiting {RETRY_BASE_DELAY * attempt} seconds before retrying...")
                time.sleep(RETRY_BASE_DELAY * attempt)
                continue
            error_message = f"HTTP error: {str(e)}"
            with open(LOG_FILE, "a") as logf:
                logf.write(f"\n--- API Call #{api_call_count} ---\n")
                logf.write(f"Batch: {expressions_batch}\n")
                logf.write(f"Response:\n{error_message}\n")
                logf.write(f"Status: HTTP Error\n")
                logf.write(f"Timestamp: {time.ctime()}\n")
                logf.write("-" * 40 + "\n")
            api_responses.append({
                "status": "HTTP Error",
                "batch_size": len(expressions_batch),
                "response": error_message,
                "timestamp": time.time()
            })
            print(f"API call #{api_call_count} failed with HTTP error: {str(e)}")
            if attempt == MAX_RETRIES:
                return error_message, False
        except requests.exceptions.Timeout as e:
            print(f"API call #{api_call_count} failed with timeout: {str(e)}. Waiting {RETRY_BASE_DELAY * attempt} seconds before retrying...")
            time.sleep(RETRY_BASE_DELAY * attempt)
            if attempt == MAX_RETRIES:
                error_message = f"Request timeout: {str(e)}"
                with open(LOG_FILE, "a") as logf:
                    logf.write(f"\n--- API Call #{api_call_count} ---\n")
                    logf.write(f"Batch: {expressions_batch}\n")
                    logf.write(f"Response:\n{error_message}\n")
                    logf.write(f"Status: Timeout\n")
                    logf.write(f"Timestamp: {time.ctime()}\n")
                    logf.write("-" * 40 + "\n")
                api_responses.append({
                    "status": "Timeout",
                    "batch_size": len(expressions_batch),
                    "response": error_message,
                    "timestamp": time.time()
                })
                return error_message, False
        except requests.exceptions.ConnectionError as e:
            print(f"API call #{api_call_count} failed with connection error: {str(e)}. Waiting {RETRY_BASE_DELAY * attempt} seconds before retrying...")
            time.sleep(RETRY_BASE_DELAY * attempt)
            if attempt == MAX_RETRIES:
                error_message = f"Connection error: {str(e)}"
                with open(LOG_FILE, "a") as logf:
                    logf.write(f"\n--- API Call #{api_call_count} ---\n")
                    logf.write(f"Batch: {expressions_batch}\n")
                    logf.write(f"Response:\n{error_message}\n")
                    logf.write(f"Status: Connection Error\n")
                    logf.write(f"Timestamp: {time.ctime()}\n")
                    logf.write("-" * 40 + "\n")
                api_responses.append({
                    "status": "Connection Error",
                    "batch_size": len(expressions_batch),
                    "response": error_message,
                    "timestamp": time.time()
                })
                return error_message, False
        except Exception as e:
            print(f"API call #{api_call_count} failed with exception: {str(e)}. Waiting {RETRY_BASE_DELAY * attempt} seconds before retrying...")
            time.sleep(RETRY_BASE_DELAY * attempt)
            if attempt == MAX_RETRIES:
                error_message = f"Unexpected error: {str(e)}"
                with open(LOG_FILE, "a") as logf:
                    logf.write(f"\n--- API Call #{api_call_count} ---\n")
                    logf.write(f"Batch: {expressions_batch}\n")
                    logf.write(f"Response:\n{error_message}\n")
                    logf.write(f"Status: Exception\n")
                    logf.write(f"Timestamp: {time.ctime()}\n")
                    logf.write("-" * 40 + "\n")
                api_responses.append({
                    "status": "Exception",
                    "batch_size": len(expressions_batch),
                    "response": error_message,
                    "timestamp": time.time()
                })
                return error_message, False

def parse_batch_response(response_text, batch_size):
    try:
        parsed = json.loads(response_text)
        if isinstance(parsed, list):
            results = []
            for i in range(batch_size):
                if i < len(parsed) and isinstance(parsed[i], dict):
                    results.append({
                        "index": i,
                        "dax_expression": parsed[i].get("dax_expression", "").strip(),
                        "comment": parsed[i].get("comment", "").strip()
                    })
                else:
                    results.append({
                        "index": i,
                        "dax_expression": "",
                        "comment": ""
                    })
            return results
    except Exception:
        pass
    results = []
    index_pattern = re.compile(r'(\d+)[\s]*:[\s]*(.*?)(?=\d+[\s]*:|$)', re.DOTALL)
    matches = list(index_pattern.finditer(response_text))
    expressions = {}
    for match in matches:
        index = int(match.group(1))
        content = match.group(2).strip()
        expressions[index] = content
    for i in range(batch_size):
        if i in expressions:
            content = expressions[i]
            dax_keywords = ['SUM(', 'CALCULATE(', 'FILTER(', 'IF(', 'MAX(', 'MIN(', 'AVERAGE(', 'COUNT(', 
                            'SUMX(', 'MAXX(', 'DISTINCTCOUNT(', 'DIVIDE(', 'VALUES(', 'ALL(', 'RELATED(']
            dax_expr = ""
            comment = ""
            if any(keyword.lower() in content.lower() for keyword in dax_keywords):
                if re.search(r'[A-Za-z]+\([^()]*(\([^()]*\)[^()]*)*\)', content):
                    dax_expr = content
                else:
                    comment = content
            else:
                comment = content
            results.append({
                "index": i,
                "dax_expression": dax_expr,
                "comment": comment
            })
        else:
            results.append({
                "index": i,
                "dax_expression": "",
                "comment": ""
            })
    return results

def convert_qvd(qvd_path):
    global _processing_lock
    if _processing_lock:
        return None, "Processing already in progress"
    _processing_lock = True
    try:
        output_filename = f"{Path(qvd_path).stem}_dataset.csv"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        try:
            if qvd_reader is None:
                raise ImportError("The qvd package is not installed. Install qvd==0.0.15 to enable QVD conversion.")
            df = qvd_reader.read(qvd_path)
            print("Successfully read QVD file using 'qvd_reader' library")
            print("QVD conversion to CSV successful.")
            df.columns = [col.lstrip('%') for col in df.columns]
            df.to_csv(output_path, index=False)
            log_message = f"Successfully converted '{Path(qvd_path).name}' to CSV format. Output saved at: {output_path}"
            return output_path, log_message
        except ImportError as e:
            error_message = f"""
QVD Reader Library Not Found!

The 'qvd' library with 'qvd_reader' module is required to read QVD files.

To fix this issue:

1. Install the QVD library:
   pip install qvd

2. If that doesn't work, try:
   pip install --upgrade qvd

3. Alternative QVD libraries:
   pip install pqvd
   pip install qlikview-qvd

4. If installation fails, convert your QVD file to CSV using QlikView:
   - Open QlikView
   - Load your QVD file
   - Export table as CSV

Import error details: {str(e)}
            """
            return None, error_message.strip()
        except AttributeError as e:
            error_message = f"""
QVD Reader Module Error!

The 'qvd_reader' module doesn't have the expected 'read' attribute.
This usually means the QVD library version is incompatible.

Solutions:
1. Try reinstalling the QVD library:
   pip uninstall qvd
   pip install qvd

2. Try a different QVD library:
   pip install pqvd

3. Check the QVD library documentation for the correct usage

4. Convert your QVD file to CSV using QlikView/QlikSense

Technical error: {str(e)}
            """
            return None, error_message.strip()
        except Exception as e:
            error_message = f"""
Error Reading QVD File!

Failed to read the QVD file: {str(e)}

This could be due to:
1. Corrupted QVD file
2. Incompatible QVD format version
3. File permission issues
4. Insufficient memory

Solutions:
1. Check if the QVD file opens correctly in QlikView
2. Try converting the file to CSV in QlikView first
3. Ensure the file is not corrupted
4. Check file permissions

Technical error: {str(e)}
            """
            return None, error_message.strip()
    except Exception as e:
        error_message = f"Unexpected error during QVD conversion: {e}"
        return None, error_message
    finally:
        _processing_lock = False

def clean_expression(expr):
    if pd.isna(expr):
        return ""
    expr = str(expr)
    expr = expr.strip()
    expr = re.sub(r'[\r\n\t]', ' ', expr)
    expr = re.sub(r'[^\x20-\x7E]', '', expr)
    expr = re.sub(r'\s+', ' ', expr)
    expr = expr.replace('\u200b', '')
    return expr

def convert_qlik_to_dax(excel_path):
    global _processing_lock
    if _processing_lock:
        return None, "Processing already in progress"
    reset_api_tracking()
    reset_log()
    _processing_lock = True
    try:
        output_filename = f"{Path(excel_path).stem}_converted.xlsx"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        df = pd.read_excel(excel_path)
        if "QLIK EXPRESSIONS" not in df.columns:
            raise ValueError("The uploaded file must contain a 'QLIK EXPRESSIONS' column.")
        df["QLIK EXPRESSIONS"] = df["QLIK EXPRESSIONS"].apply(clean_expression)
        all_expressions = df["QLIK EXPRESSIONS"].tolist()
        valid_expressions = []
        expression_positions = []
        for idx, expr in enumerate(all_expressions):
            if expr:
                valid_expressions.append(expr)
                expression_positions.append(idx)
        if not valid_expressions:
            raise ValueError("No valid expressions found in the QLIK EXPRESSIONS column.")
        dax_expressions = [""] * len(all_expressions)
        comments = [""] * len(all_expressions)
        total_batches = (len(valid_expressions) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"Starting conversion of {len(valid_expressions)} expressions in {total_batches} batches")
        processed_count = 0
        successful_batches = 0
        failed_batches = 0
        for i in range(0, len(valid_expressions), BATCH_SIZE):
            batch = valid_expressions[i:i + BATCH_SIZE]
            batch_positions = expression_positions[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            context = "Convert the following Qlik expressions to Power BI DAX expressions."
            try:
                print(f"Processing batch {batch_num}/{total_batches} (expressions {i+1}-{min(i+BATCH_SIZE, len(valid_expressions))})")
                response, success = ask_llm_batch(batch, context)
                if not success:
                    print(f"API call failed for batch {batch_num} after {MAX_RETRIES} attempts")
                    for j in range(len(batch)):
                        original_position = batch_positions[j]
                        dax_expressions[original_position] = ""
                        comments[original_position] = f"API connection failed for expression: {batch[j]}"
                        processed_count += 1
                    failed_batches += 1
                    continue
                results = parse_batch_response(response, len(batch))
                for j, result in enumerate(results):
                    if j >= len(batch_positions):
                        continue
                    original_position = batch_positions[j]
                    dax_expr = result.get("dax_expression", "")
                    comment = result.get("comment", "")
                    if comment.strip().lower() == "empty":
                        comment = ""
                    dax_expressions[original_position] = dax_expr
                    comments[original_position] = comment
                    processed_count += 1
                successful_batches += 1
                print(f"Batch {batch_num} completed successfully ({processed_count}/{len(valid_expressions)} expressions processed)")
                time.sleep(float(os.getenv("BLXLERATOR_INTER_BATCH_DELAY", "0")))
            except Exception as e:
                print(f"Batch {batch_num} failed with exception: {e}")
                for j in range(len(batch)):
                    original_position = batch_positions[j]
                    dax_expressions[original_position] = ""
                    comments[original_position] = f"Processing error for expression: {batch[j]} - {str(e)}"
                    processed_count += 1
                failed_batches += 1
        df["PBI EXPRESSIONS"] = dax_expressions
        df["COMMENTS"] = comments
        df.to_excel(output_path, index=False)
        api_summary = get_api_summary()
        log_message = f"""
Conversion Summary:
- Total expressions in file: {len(all_expressions)}
- Valid expressions processed: {len(valid_expressions)}
- Empty/invalid expressions skipped: {len(all_expressions) - len(valid_expressions)}
- Successful batches: {successful_batches}
- Failed batches: {failed_batches}
- Total batches: {total_batches}
- Output file: {output_path}

{api_summary}

File successfully saved with columns:
- Original columns preserved
- PBI EXPRESSIONS: Contains converted DAX expressions
- COMMENTS: Contains explanations for failed conversions

Note: If you see connection errors, this may be due to network issues or API rate limiting.
Try again in a few minutes if many batches failed.
        """.strip()
        print(f"Processing completed: {successful_batches}/{total_batches} batches successful")
        return output_path, log_message
    except Exception as e:
        error_message = f"Error converting Qlik expressions to DAX: {e}"
        print(error_message)
        return None, error_message
    finally:
        _processing_lock = False

def convert_qlik_script_to_python(txt_path):
    with open(LOG_PATH_QLIK_TO_PY, "w", encoding="utf-8") as logf:
        logf.write(f"=== Qlik Script to Python Conversion Log ===\n\n")
    global _processing_lock
    if _processing_lock:
        return None, "Processing already in progress"
    _processing_lock = True
    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            qlik_script = f.read()
        prompt = QLIK_TO_PYTHON_PROMPT_TEMPLATE.format(qlik_script=qlik_script)
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
                "systemPrompt": "Qlik-to-Python",
                "sessionId": f"session_{int(time.time())}",
                "modelKwargs": {
                    "maxTokens": 3500,
                    "temperature": 0,
                    "streaming": False,
                    "topP": 0.9
                }
            }
        }
        for attempt in range(1, 5):
            try:
                time.sleep(float(os.getenv("BLXLERATOR_INTER_BATCH_DELAY", "0")))
                with open(LOG_PATH_QLIK_TO_PY, "a", encoding="utf-8") as logf:
                    logf.write(f"\n--- API Request (Attempt {attempt}) ---\n")
                    logf.write(f"Prompt:\n{prompt}\n")
                response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
                response.raise_for_status()
                resp_json = response.json()
                with open(LOG_PATH_QLIK_TO_PY, "a", encoding="utf-8") as logf:
                    logf.write(f"\n--- API Response (Attempt {attempt}) ---\n")
                    logf.write(f"Response:\n{json.dumps(resp_json, indent=2)}\n")
                raw = ""
                if 'content' in resp_json:
                    raw = resp_json['content']
                elif 'data' in resp_json and 'output' in resp_json['data']:
                    raw = resp_json['data']['output']
                elif 'output' in resp_json:
                    raw = resp_json['output']
                else:
                    raw = ""
                code = ""
                code_blocks = re.findall(r"```python(.*?)```", raw, re.DOTALL | re.IGNORECASE)
                if code_blocks:
                    code = code_blocks[0].strip()
                else:
                    code_blocks = re.findall(r"```(.*?)```", raw, re.DOTALL)
                    if code_blocks:
                        code = code_blocks[0].strip()
                    else:
                        code = raw.strip()
                code = re.sub(r"(['\"])([^'\"]*?\.qvd)(['\"])", lambda m: m.group(1) + m.group(2).replace('.qvd', '.csv') + m.group(3), code)
                def add_comment_once(line, comment):
                    return line if comment in line else (line + f" {comment}")
                lines = code.splitlines()
                new_lines = []
                for line in lines:
                    if re.search(r"read_csv\([^\)]*\.csv[^\)]*\)", line):
                        line = add_comment_once(line, "# QVD must be converted to CSV for processing")
                    if re.search(r"to_csv\([^\)]*\.csv[^\)]*\)", line):
                        line = add_comment_once(line, "# Output file will be saved as CSV instead of QVD")
                    new_lines.append(line)
                code = "\n".join(new_lines)
                output_py_path = os.path.join(OUTPUT_DIR, f"{Path(txt_path).stem}_converted.py")
                with open(output_py_path, "w", encoding="utf-8") as f:
                    f.write(code)
                log_message = f"Conversion successful. Output saved at: {output_py_path}"
                return output_py_path, log_message
            except Exception as e:
                with open(LOG_PATH_QLIK_TO_PY, "a", encoding="utf-8") as logf:
                    logf.write(f"\n--- API Error (Attempt {attempt}) ---\n")
                    logf.write(f"{str(e)}\n")
                if attempt == 4:
                    return None, f"API call failed after 4 attempts: {str(e)}"
                time.sleep(5 * attempt)
    finally:
        _processing_lock
