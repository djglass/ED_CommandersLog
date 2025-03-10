import json
import os
import logging
import requests
import glob
from datetime import datetime
from typing import List, Dict, Any

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Load configuration with error handling
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
try:
    with open(CONFIG_PATH, "r") as f:
        config: Dict[str, Any] = json.load(f)
except Exception as e:
    logging.error(f"Failed to load config from {CONFIG_PATH}: {e}")
    raise

LM_STUDIO_API: str = config.get("lm_studio_api", "")
MODEL_NAME: str = config.get("model_name", "")

# Load knowledge from RAG folder instead of a single file
RAG_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "rag_data")
# Initialize the knowledge base with expected keys
knowledge_base: Dict[str, Any] = {
    "events": {},
    "materials": {},
    "terms": {},
    "lore": {},
    "environments": {}
}

if os.path.exists(RAG_DATA_FOLDER):
    for filename in os.listdir(RAG_DATA_FOLDER):
        if filename.endswith(".json"):
            filepath = os.path.join(RAG_DATA_FOLDER, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        # Merge keys that match our expected structure
                        for key, value in data.items():
                            if key in knowledge_base:
                                if isinstance(value, dict):
                                    knowledge_base[key].update(value)
                                elif isinstance(value, list):
                                    # If the knowledge base key is a list, extend it; otherwise, replace it.
                                    if isinstance(knowledge_base[key], list):
                                        knowledge_base[key].extend(value)
                                    else:
                                        knowledge_base[key] = value
                    elif isinstance(data, list):
                        # If the file contains a list, iterate over each item
                        for item in data:
                            if isinstance(item, dict):
                                for key, value in item.items():
                                    if key in knowledge_base:
                                        if isinstance(value, dict):
                                            knowledge_base[key].update(value)
                                        elif isinstance(value, list):
                                            if isinstance(knowledge_base[key], list):
                                                knowledge_base[key].extend(value)
                                            else:
                                                knowledge_base[key] = value
                            else:
                                logging.warning(f"List item in {filename} is not a dictionary, skipping.")
                    else:
                        logging.warning(f"File {filename} does not contain a dictionary or list, skipping.")
            except Exception as e:
                logging.error(f"Error loading {filename}: {e}")
else:
    logging.warning(f"RAG folder not found at {RAG_DATA_FOLDER}. Using empty knowledge base.")

def extract_json_string(text: str) -> str:
    """
    Attempts to extract a JSON substring from the given text.
    It removes markdown code fences if present and returns the substring between
    the first '{' and the last '}'.
    """
    text = text.strip()
    # Remove markdown code fences if they exist
    if text.startswith("```"):
        text = text.strip("`").strip()
    # Find the boundaries of the JSON content
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
    return text

def retrieve_knowledge(session_activities: List[str]) -> str:
    """
    Retrieves relevant Elite Dangerous knowledge snippets based on session activities.
    Performs substring matches for events, materials, and terms.
    """
    knowledge_snippets: List[str] = []
    
    for activity in session_activities:
        # Match events
        for event, description in knowledge_base.get("events", {}).items():
            if event in activity:
                knowledge_snippets.append(f"- {event}: {description}")
        
        # Match materials; assumes each material string has a format like "MaterialName - Description"
        for category, materials in knowledge_base.get("materials", {}).items():
            if isinstance(materials, list):
                for material in materials:
                    material_name = material.split(" - ")[0]
                    if material_name in activity:
                        knowledge_snippets.append(f"- {material}")
            else:
                logging.warning(f"Unexpected format for materials in category '{category}'.")
        
        # Match terms
        for term, definition in knowledge_base.get("terms", {}).items():
            if term in activity:
                knowledge_snippets.append(f"- {term}: {definition}")

    return "\n".join(knowledge_snippets) if knowledge_snippets else "No additional knowledge needed."

def build_prompt(cmdr_name: str, log_entry: str, session_activities: List[str], retrieved_knowledge: str) -> str:
    """
    Constructs the prompt template for LM Studio using the log data, session activities,
    and the retrieved knowledge.
    """
    activities_text = ", ".join(session_activities)
    prompt = f"""
[SYSTEM MESSAGE: You are an AI that STRICTLY formats logs in Elite Dangerous. YOU CANNOT GENERATE NEW CONTENT.]

=== Commander’s Log ===
{log_entry}

=== Session Activities ===
{activities_text}

=== Knowledge Reference ===
{retrieved_knowledge}

=== OUTPUT STRICT FORMAT ===
{{
  "star_system": "[REAL STAR SYSTEM FROM LOG]",
  "location": "[REAL LOCATION FROM LOG]",
  "security_status": "[REAL SECURITY STATUS]",
  "ship_status": {{
    "fuel": "[FUEL STATUS IF LOGGED]",
    "modules": "[MODULE STATUS IF LOGGED]"
  }},
  "activities": [
    "[REAL EVENTS FROM SESSION LOG]"
  ],
  "notable_events": [
    "[Bounty, mining success, exobiology discovery, combat, trading]"
  ]
}}

=== STRICT RULES ===
- DO NOT generate dialogue, AI warnings, or crew interactions.
- DO NOT add descriptions, reflections, or creative writing.
- DO NOT add any locations, anomalies, or events that are NOT in logs.
- ONLY format the provided log data into the above JSON format.

Now, strictly return the log in JSON format. DO NOT ADD ANY ADDITIONAL CONTENT.
"""
    return prompt.strip()

def enforce_strict_rules(log_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enforces that the output strictly adheres to the required format.
    For example, if 'notable_events' is empty or missing, it will be replaced with the placeholder.
    """
    placeholders = {
        "star_system": "[REAL STAR SYSTEM FROM LOG]",
        "location": "[REAL LOCATION FROM LOG]",
        "security_status": "[REAL SECURITY STATUS]",
        "ship_status": {
            "fuel": "[FUEL STATUS IF LOGGED]",
            "modules": "[MODULE STATUS IF LOGGED]"
        },
        "activities": [
            "[REAL EVENTS FROM SESSION LOG]"
        ],
        "notable_events": [
            "[Bounty, mining success, exobiology discovery, combat, trading]"
        ]
    }
    
    for key, placeholder in placeholders.items():
        if key not in log_json or (isinstance(log_json[key], list) and not log_json[key]):
            log_json[key] = placeholder
        elif key == "ship_status":
            for sub_key, sub_placeholder in placeholder.items():
                if sub_key not in log_json[key] or not log_json[key][sub_key]:
                    log_json[key][sub_key] = sub_placeholder

    return log_json

def generate_log(cmdr_name: str, log_entry: str, session_activities: List[str]) -> str:
    """
    Generates a Commander’s Log by formatting the log data using LM Studio API.
    The function constructs a prompt with log entry, session activities, and relevant knowledge.
    Returns the JSON-formatted log as a string.
    """
    retrieved_knowledge: str = retrieve_knowledge(session_activities)
    prompt: str = build_prompt(cmdr_name, log_entry, session_activities, retrieved_knowledge)
    
    try:
        response = requests.post(
            LM_STUDIO_API,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "max_tokens": 400,
                "temperature": 0.0,
                "top_p": 0.1,
            },
            timeout=20
        )
        response.raise_for_status()
        response_data = response.json()
        log_text: str = response_data["choices"][0]["text"]
        logging.info("Log generated successfully.")
        
        cleaned_log_text = extract_json_string(log_text)
        
        try:
            log_json = json.loads(cleaned_log_text)
        except json.JSONDecodeError as json_err:
            logging.error(f"Error parsing generated log as JSON: {json_err}")
            return "Error: Unable to generate Commander’s Log."
        
        strict_log = enforce_strict_rules(log_json)
        return json.dumps(strict_log, indent=2)
    
    except requests.exceptions.RequestException as req_err:
        logging.error(f"Request error while generating log: {req_err}")
    except (KeyError, ValueError, json.JSONDecodeError) as parse_err:
        logging.error(f"Error parsing response: {parse_err}")
    
    return "Error: Unable to generate Commander’s Log."

def get_latest_log() -> (str, str, List[str]):
    """
    Retrieves the most recent Commander log from the 'rag_data/commander_logs' folder.
    Extracts the commander name from the header and collects session activities from bullet points.
    Returns a tuple of (cmdr_name, log_entry, session_activities).
    """
    logs_dir = os.path.join(os.path.dirname(__file__), "rag_data", "commander_logs")
    markdown_files = glob.glob(os.path.join(logs_dir, "*.md"))
    
    if not markdown_files:
        logging.error("No commander log files found.")
        return "", "", []
    
    # Select the latest file based on modification time
    latest_file = max(markdown_files, key=os.path.getmtime)
    with open(latest_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Assume first line contains the commander header: "# Commander <NAME> - Log <DATE>"
    first_line = content.splitlines()[0]
    cmdr_name = "Unknown Commander"
    if first_line.startswith("# Commander"):
        try:
            # Example header: "# Commander TOADIE MUDGUTS - Log 2025-03-09"
            parts = first_line.split()
            if len(parts) >= 3:
                cmdr_name = parts[2]
        except Exception as e:
            logging.warning(f"Could not parse commander name: {e}")
    
    # Extract session activities from bullet points
    session_activities = []
    for line in content.splitlines():
        if line.strip().startswith("- "):
            # Remove bullet and extra whitespace
            session_activities.append(line.strip()[2:])
    
    return cmdr_name, content, session_activities

if __name__ == "__main__":
    cmdr_name, log_entry, session_activities = get_latest_log()
    if log_entry:
        enhanced_log: str = generate_log(cmdr_name, log_entry, session_activities)
        print(f"\n📖 {cmdr_name}’s Enhanced Commander’s Log:\n")
        print(enhanced_log)
    else:
        print("No valid commander log found!")
