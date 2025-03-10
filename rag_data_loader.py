import os
import json
import logging
from typing import Any, Dict, List
import chromadb
from sentence_transformers import SentenceTransformer

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Define the data folder for RAG files
DATA_FOLDER: str = os.path.join(os.path.dirname(__file__), "rag_data")

# Initialize ChromaDB client
try:
    chroma_client = chromadb.PersistentClient(path="elite_rag_db")
    collection = chroma_client.get_or_create_collection("elite_dangerous_lore")
    logging.info("✅ Connected to ChromaDB.")
except Exception as e:
    logging.error(f"❌ ERROR: Failed to connect to ChromaDB: {e}")
    exit(1)

# Initialize embedding model
try:
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    logging.info("✅ Embedding model loaded.")
except Exception as e:
    logging.error(f"❌ ERROR: Failed to load embedding model: {e}")
    exit(1)

def add_knowledge_entry(entry: Dict[str, Any]) -> None:
    """
    Adds a knowledge entry to the ChromaDB collection.
    
    Args:
        entry (Dict[str, Any]): A dictionary representing a knowledge entry. Must include 'id', 'name', and 'description' keys.
    """
    try:
        if not isinstance(entry, dict):
            raise TypeError(f"Expected dictionary, got {type(entry)}")
        
        text = (
            f"{entry['name']}: {entry['description']} "
            f"(Capital: {entry.get('capital', 'Unknown')}, Leader: {entry.get('leader', 'Unknown')})"
        )
        embedding: List[float] = embedding_model.encode(text).tolist()
        collection.add(ids=[entry["id"]], embeddings=[embedding], metadatas=[{"text": text}])
        logging.info(f"✅ Added to database: {entry['name']}")
    except Exception as e:
        logging.error(f"❌ ERROR: Failed to add entry - {e}")

def load_all_json_data() -> None:
    """
    Loads all JSON files in the DATA_FOLDER and stores their content in ChromaDB.
    Supports both dictionary and list formats.
    """
    if not os.path.exists(DATA_FOLDER):
        logging.error(f"❌ ERROR: Data folder not found: {DATA_FOLDER}")
        return

    files_found: bool = False
    for filename in os.listdir(DATA_FOLDER):
        if filename.endswith(".json"):
            files_found = True
            json_file = os.path.join(DATA_FOLDER, filename)
            logging.info(f"\n🔍 Loading data from: {filename}")
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Ensure data is a list for uniform processing
                    if isinstance(data, dict):
                        data = [data]
                    elif not isinstance(data, list):
                        raise TypeError(f"Invalid JSON format in {filename}")

                    for entry in data:
                        if isinstance(entry, dict):
                            add_knowledge_entry(entry)
                        else:
                            logging.warning(f"⚠️ Skipped non-dictionary entry in {filename}: {entry}")
            except json.JSONDecodeError as e:
                logging.error(f"❌ ERROR: Failed to decode JSON in {filename} - {e}")
            except Exception as e:
                logging.error(f"❌ ERROR processing file {filename}: {e}")
    
    if not files_found:
        logging.warning("⚠️ WARNING: No JSON files found in 'rag_data/'. Please add data files.")

# Run data loading for all JSON files in the DATA_FOLDER
logging.info("\n📂 Scanning 'rag_data/' folder for JSON knowledge files...")
load_all_json_data()

# Verify stored data in the database
try:
    stored_data = collection.get()
    ids = stored_data.get("ids", [])
    metadatas = stored_data.get("metadatas", [])
    logging.info(f"\n📌 Database Verification: {len(ids)} entries stored.")
    for i, metadata in enumerate(metadatas):
        logging.info(f"🔹 {i+1}. {metadata.get('text', 'No text')}")
except Exception as e:
    logging.error(f"❌ ERROR: Failed to retrieve stored data - {e}")

logging.info("\n✅ All knowledge data stored successfully!")
