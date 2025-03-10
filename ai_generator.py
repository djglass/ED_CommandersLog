import json
import os
import logging
import requests
import glob
from datetime import datetime
from typing import List, Dict, Any, Tuple

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Load configuration
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
try:
    with open(CONFIG_PATH, "r") as f:
        config: Dict[str, Any] = json.load(f)
except Exception as e:
    logging.error(f"Failed to load config from {CONFIG_PATH}: {e}")
    raise

LM_STUDIO_API: str = config.get("lm_studio_api", "")
MODEL_NAME: str = config.get("model_name", "")

RAG_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "rag_data")
knowledge_base: Dict[str, Any] = {
    "events": {},
    "materials": {},
    "terms": {},
    "lore": {},
    "environments": {}
}

# Load JSON knowledge files into the knowledge base
if os.path.exists(RAG_DATA_FOLDER):
    for filename in os.listdir(RAG_DATA_FOLDER):
        if filename.endswith(".json"):
            filepath = os.path.join(RAG_DATA_FOLDER, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        for key, value in data.items():
                            if key in knowledge_base and isinstance(value, (dict, list)):
                                if isinstance(value, dict):
                                    knowledge_base[key].update(value)
                                else:
                                    if isinstance(knowledge_base[key], list):
                                        knowledge_base[key].extend(value)
                                    else:
                                        knowledge_base[key] = value
                            else:
                                logging.warning(f"Ignored key in {filename}: {key}")
                    elif isinstance(data, list):
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
                        logging.warning(f"Invalid structure in {filename}")
            except Exception as e:
                logging.error(f"Failed to load {filename}: {e}")
else:
    logging.warning(f"RAG folder not found at {RAG_DATA_FOLDER}. Using empty knowledge base.")

def extract_json_string(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
    start = text.find('{')
    end = text.rfind('}')
    return text[start:end+1] if start != -1 and end != -1 and end > start else text

def retrieve_knowledge(session_activities: List[str]) -> str:
    snippets: List[str] = []

    for activity in session_activities:
        for event, desc in knowledge_base.get("events", {}).items():
            if event in activity:
                snippets.append(f"- {event}: {desc}")

        for cat, materials in knowledge_base.get("materials", {}).items():
            if isinstance(materials, list):
                for mat in materials:
                    if isinstance(mat, str):
                        name = mat.split(" - ")[0]
                        if name in activity:
                            snippets.append(f"- {mat}")

        for term, definition in knowledge_base.get("terms", {}).items():
            if term in activity:
                snippets.append(f"- {term}: {definition}")

    return "\n".join(snippets) if snippets else "No additional knowledge needed."

def build_prompt(cmdr_name: str, log_entry: str, session_activities: List[str], retrieved_knowledge: str) -> str:
    activity_text = ", ".join(session_activities)
    return f"""
[SYSTEM MESSAGE: You are an AI that STRICTLY formats logs in Elite Dangerous. YOU CANNOT GENERATE NEW CONTENT.]

=== Commander’s Log ===
{log_entry}

=== Session Activities ===
{activity_text}

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
""".strip()

def enforce_strict_rules(log_json: Dict[str, Any]) -> Dict[str, Any]:
    placeholders = {
        "star_system": "[REAL STAR SYSTEM FROM LOG]",
        "location": "[REAL LOCATION FROM LOG]",
        "security_status": "[REAL SECURITY STATUS]",
        "ship_status": {
            "fuel": "[FUEL STATUS IF LOGGED]",
            "modules": "[MODULE STATUS IF LOGGED]"
        },
        "activities": ["[REAL EVENTS FROM SESSION LOG]"],
        "notable_events": ["[Bounty, mining success, exobiology discovery, combat, trading]"]
    }

    for key, placeholder in placeholders.items():
        if key not in log_json or not log_json[key]:
            log_json[key] = placeholder
        elif key == "ship_status":
            for sub_key, sub_val in placeholder.items():
                if sub_key not in log_json[key] or not log_json[key][sub_key]:
                    log_json[key][sub_key] = sub_val

    return log_json

def generate_log(cmdr_name: str, log_entry: str, session_activities: List[str]) -> str:
    knowledge = retrieve_knowledge(session_activities)
    prompt = build_prompt(cmdr_name, log_entry, session_activities, knowledge)

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
            timeout=90
        )
        response.raise_for_status()
        log_text = response.json()["choices"][0]["text"]
        cleaned = extract_json_string(log_text)
        log_json = json.loads(cleaned)
        return json.dumps(enforce_strict_rules(log_json), indent=2)
    except Exception as e:
        logging.error(f"Error generating log: {e}")
        return "Error: Unable to generate Commander’s Log."

def get_latest_log() -> Tuple[str, str, List[str]]:
    logs_dir = os.path.join(os.path.dirname(__file__), "rag_data", "commander_logs")
    markdown_files = glob.glob(os.path.join(logs_dir, "*.md"))
    if not markdown_files:
        logging.error("No commander log files found.")
        return "", "", []

    latest_file = max(markdown_files, key=os.path.getmtime)
    with open(latest_file, "r", encoding="utf-8") as f:
        content = f.read()

    first_line = content.splitlines()[0]
    cmdr_name = "Unknown Commander"
    if first_line.startswith("# Commander"):
        try:
            parts = first_line.split()
            if len(parts) >= 3:
                cmdr_name = parts[2]
        except Exception as e:
            logging.warning(f"Could not parse commander name: {e}")

    session_activities = [
        line.strip()[2:]
        for line in content.splitlines()
        if line.strip().startswith("- ")
    ]

    return cmdr_name, content, session_activities

if __name__ == "__main__":
    cmdr_name, log_entry, session_activities = get_latest_log()
    if log_entry:
        enhanced_log = generate_log(cmdr_name, log_entry, session_activities)
        print(f"\n📖 {cmdr_name}’s Enhanced Commander’s Log:\n")
        print(enhanced_log)
    else:
        print("No valid commander log found.")
