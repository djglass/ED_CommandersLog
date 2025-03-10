import chromadb
from sentence_transformers import SentenceTransformer
import json
import os

# Paths
DATA_FOLDER = "rag_data"  # Folder where all JSON knowledge files are stored

# Initialize ChromaDB client
try:
    chroma_client = chromadb.PersistentClient(path="elite_rag_db")
    collection = chroma_client.get_or_create_collection("elite_dangerous_lore")
    print("✅ Connected to ChromaDB.")
except Exception as e:
    print(f"❌ ERROR: Failed to connect to ChromaDB: {e}")
    exit()

# Initialize embedding model
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
print("✅ Embedding model loaded.")

# Function to add knowledge entries
def add_knowledge_entry(entry):
    try:
        if not isinstance(entry, dict):  # Ensure entry is a dictionary
            raise TypeError(f"Expected dictionary, got {type(entry)}")

        text = f"{entry['name']}: {entry['description']} (Capital: {entry.get('capital', 'Unknown')}, Leader: {entry.get('leader', 'Unknown')})"
        embedding = embedding_model.encode(text).tolist()
        collection.add(ids=[entry["id"]], embeddings=[embedding], metadatas=[{"text": text}])
        print(f"✅ Added to database: {entry['name']}")
    except Exception as e:
        print(f"❌ ERROR: Failed to add entry - {e}")

# Load JSON files dynamically
def load_all_json_data():
    """Loads all JSON files in the rag_data folder and stores them in ChromaDB."""
    if not os.path.exists(DATA_FOLDER):
        print(f"❌ ERROR: Data folder not found: {DATA_FOLDER}")
        return
    
    files_found = False
    for filename in os.listdir(DATA_FOLDER):
        if filename.endswith(".json"):
            files_found = True
            json_file = os.path.join(DATA_FOLDER, filename)
            print(f"\n🔍 Loading Data from: {filename}")
            
            with open(json_file, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)  # Ensure data loads as JSON
                    if isinstance(data, dict):  # Handle single dictionary case
                        data = [data]  # Convert to list for processing
                    elif not isinstance(data, list):  # Ensure it's a list
                        raise TypeError(f"Invalid JSON format in {filename}")

                    for entry in data:
                        add_knowledge_entry(entry)
                except json.JSONDecodeError as e:
                    print(f"❌ ERROR: Failed to read {filename} - {e}")

    if not files_found:
        print("⚠️ WARNING: No JSON files found in 'rag_data/'. Please add data files.")

# Run data loading for all JSON files
print("\n📂 Scanning 'rag_data/' folder for JSON knowledge files...")
load_all_json_data()

# Verify stored data
try:
    stored_data = collection.get()
    print(f"\n📌 Database Verification: {len(stored_data['ids'])} entries stored.")
    for i, metadata in enumerate(stored_data["metadatas"]):
        print(f"🔹 {i+1}. {metadata['text']}")
except Exception as e:
    print(f"❌ ERROR: Failed to retrieve stored data - {e}")

print("\n✅ All knowledge data stored successfully!")
