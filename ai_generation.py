import json
import os
import logging
import requests
from typing import List, Dict
from sentence_transformers import SentenceTransformer
import chromadb

# === CONFIG ===
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

LM_STUDIO_API = config.get("lm_studio_api", "")
MODEL_NAME = config.get("model_name", "")
BASE_DIR = os.path.dirname(__file__)
RAG_DATA_FOLDER = os.path.join(BASE_DIR, "rag_data")
COMMANDER_LOGS_FOLDER = os.path.join(RAG_DATA_FOLDER, "commander_logs")
DIARY_OUTPUT_FOLDER = os.path.join(BASE_DIR, "diary_logs")
PROMPT_LOG_FILE = os.path.join(BASE_DIR, "diary_prompt.log")
os.makedirs(DIARY_OUTPUT_FOLDER, exist_ok=True)

# === INIT: Embedding + Vector Store ===
chroma_client = chromadb.PersistentClient(path="elite_rag_db")
collection = chroma_client.get_or_create_collection("elite_dangerous_lore")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def compress_activities(activities: List[str]) -> List[str]:
    from collections import defaultdict
    prefix_counts = defaultdict(list)
    for act in activities:
        prefix = act.split("**")[0].strip().rstrip(":")
        prefix_counts[prefix].append(act)

    compressed = []
    for prefix, lines in prefix_counts.items():
        if len(lines) > 3:
            sample = lines[0].replace("**", "")
            compressed.append(f"{prefix} ({len(lines)}x): '{sample}'")
        else:
            compressed.extend(lines)
    return compressed

def retrieve_knowledge(activities: List[str], top_k: int = 4) -> str:
    combined = []
    for activity in activities:
        embedding = embedding_model.encode(activity).tolist()
        try:
            results = collection.query(query_embeddings=[embedding], n_results=top_k)
            for md in results.get("metadatas", [[]])[0]:
                if md.get("text"):
                    combined.append(md["text"])
        except Exception as e:
            logging.warning(f"RAG failed: {e}")
    return "\n".join(combined[:5]) if combined else ""

def build_messages(commander: str, date: str, activities: List[str]) -> List[Dict[str, str]]:
    compressed = compress_activities(activities)
    knowledge = retrieve_knowledge(compressed)

    system_msg = {
        "role": "system",
        "content": (
            "You are Commander Toadie Mudguts, grizzled pilot of the Krait Mk II 'Rust Lancer'. "
            "This is your personal log. No summaries. No analysis. No 'thinking aloud'. Just your voice."
        )
    }

    user_content = f"=== LOG ENTRY: CMDR TOADIE MUDGUTS – {date} ===\n\n"
    user_content += "Another day out in the black...\n\n"
    user_content += "\n".join(f"- {line}" for line in compressed)
    if knowledge:
        user_content += f"\n\nBits I heard around the station:\n{knowledge}"
    user_content += "\n\nClose the log however you like. End with: **[End of Log]**"

    return [system_msg, {"role": "user", "content": user_content}]

def generate_diary(commander: str, date: str, activities: List[str]) -> str:
    messages = build_messages(commander, date, activities)
    try:
        with open(PROMPT_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(messages, f, indent=2)
        response = requests.post(
            LM_STUDIO_API,
            json={
                "model": MODEL_NAME,
                "messages": messages,
                "max_tokens": 1200,
                "temperature": 0.7,
                "top_p": 0.9,
            },
            timeout=180
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logging.error(f"Error generating diary: {e}")
        return "Error: Unable to generate diary entry."

def save_diary(date: str, content: str):
    output_path = os.path.join(DIARY_OUTPUT_FOLDER, f"{date}.txt")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        logging.info(f"📝 Diary saved to: {output_path}")
    except Exception as e:
        logging.error(f"❌ Failed to save diary: {e}")
