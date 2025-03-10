import os
import json

# Root folder for RAG data
RAG_FOLDER = os.path.join(os.path.dirname(__file__), "rag_data")

def is_valid_entry(entry):
    return isinstance(entry, dict) and all(k in entry for k in ["id", "name", "description"])

def validate_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                bad_entries = [e for e in data if not is_valid_entry(e)]
                return len(bad_entries), len(data)
            else:
                return -1, 0  # Not a list
    except json.JSONDecodeError:
        return -2, 0  # Invalid JSON

def run_validation():
    print(f"📂 Validating JSON files in: {RAG_FOLDER} (including subfolders)\n")
    
    for root, dirs, files in os.walk(RAG_FOLDER):
        for filename in files:
            if filename.endswith(".json"):
                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, RAG_FOLDER)
                bad_count, total = validate_file(filepath)
                
                if bad_count == -1:
                    print(f"❌ {rel_path}: Top-level object is not a list.")
                elif bad_count == -2:
                    print(f"❌ {rel_path}: Invalid JSON format.")
                elif bad_count > 0:
                    print(f"⚠️ {rel_path}: {bad_count}/{total} entries are invalid.")
                else:
                    print(f"✅ {rel_path}: All entries valid.")
    
    print("\n✅ Validation complete.")

if __name__ == "__main__":
    run_validation()
