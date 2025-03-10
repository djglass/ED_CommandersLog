import requests # type: ignore
import json
import os
import re
from log_parser import parse_latest_log

# Load config
config_path = os.path.join(os.path.dirname(__file__), "config.json")
with open(config_path, "r") as f:
    config = json.load(f)

# Load Elite Dangerous knowledge base
try:
    with open("elite_dangerous_knowledge.json", "r") as f:
        knowledge_base = json.load(f)
except FileNotFoundError:
    knowledge_base = {"events": {}, "materials": {}, "terms": {}, "lore": {}, "environments": {}}

LM_STUDIO_API = config["lm_studio_api"]
MODEL_NAME = config["model_name"]

def retrieve_knowledge(session_activities):
    """Retrieves relevant Elite Dangerous knowledge based on logged session activities."""
    knowledge_snippets = []
    
    for activity in session_activities:
        # Match events
        for event, description in knowledge_base["events"].items():
            if event in activity:
                knowledge_snippets.append(f"- {event}: {description}")
        
        # Match materials
        for category, materials in knowledge_base["materials"].items():
            for material in materials:
                if material.split(" - ")[0] in activity:
                    knowledge_snippets.append(f"- {material}")
        
        # Match terms
        for term, definition in knowledge_base["terms"].items():
            if term in activity:
                knowledge_snippets.append(f"- {term}: {definition}")

    return "\n".join(knowledge_snippets) if knowledge_snippets else "No additional knowledge needed."

def generate_log(cmdr_name, log_entry, session_activities):
    """Generates a Commander’s Log **STRICTLY using log data (no generation).**"""
    
    # Retrieve relevant knowledge for the session
    retrieved_knowledge = retrieve_knowledge(session_activities)

    prompt = f"""
    [SYSTEM MESSAGE: You are an AI that STRICTLY formats logs in Elite Dangerous. YOU CANNOT GENERATE NEW CONTENT.]

    === Commander’s Log ===
    {log_entry}

    === Session Activities ===
    {', '.join(session_activities)}

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
    - **DO NOT generate dialogue, AI warnings, or crew interactions.**
    - **DO NOT add descriptions, reflections, or creative writing.**
    - **DO NOT add any locations, anomalies, or events that are NOT in logs.**
    - **ONLY format the provided log data into the above JSON format.**

    **Now, strictly return the log in JSON format. DO NOT ADD ANY ADDITIONAL CONTENT.**
    """

    response = requests.post(
        LM_STUDIO_API,
        json={
            "model": MODEL_NAME,
            "prompt": prompt,
            "max_tokens": 400,  # **Prevents extra content**
            "temperature": 0.0,  # **FULL ZERO CREATIVITY**
            "top_p": 0.1,        # **STRONGLY limits randomness**
        }
    )

    return response.json()["choices"][0]["text"]

if __name__ == "__main__":
    cmdr_name, log_entry, session_activities, ship_status, powerplay, timestamps = parse_latest_log()
    if log_entry:
        enhanced_log = generate_log(cmdr_name, log_entry, session_activities)
        print(f"\n📖 {cmdr_name}’s Enhanced Commander’s Log:\n")
        print(enhanced_log)
    else:
        print("No valid hyperspace jump or location data found!")
