import os
import json

# Root folder for RAG data
RAG_FOLDER = os.path.join(os.path.dirname(__file__), "rag_data")

def validate_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

            # Case 1: List of dictionaries for RAG knowledge entries
            if isinstance(data, list):
                bad_entries = [e for e in data if not (isinstance(e, dict) and "id" in e and "name" in e and "description" in e)]
                return "rag_list", len(bad_entries), len(data)

            # Case 2: Commander log format
            elif isinstance(data, dict) and {"commander", "date", "categories"}.issubset(data.keys()):
                return "commander_log", 0, 1

            else:
                return "unknown", 1, 1

    except json.JSONDecodeError:
        return "invalid", 1, 0

def run_validation():
    print(f"\U0001F4C2 Validating JSON files in: {RAG_FOLDER} (including subfolders)\n")

    for root, dirs, files in os.walk(RAG_FOLDER):
        for filename in files:
            if filename.endswith(".json"):
                if filename == "processed_index.json":
                    continue  # Skip non-RAG tracking files

                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, RAG_FOLDER)

                result, bad_count, total = validate_file(filepath)

                if result == "rag_list":
                    if bad_count > 0:
                        print(f"⚠️ {rel_path}: {bad_count}/{total} RAG entries are invalid.")
                    else:
                        print(f"✅ {rel_path}: All RAG entries valid.")
                elif result == "commander_log":
                    print(f"✅ {rel_path}: Commander log format valid.")
                elif result == "invalid":
                    print(f"❌ {rel_path}: Invalid JSON format.")
                else:
                    print(f"❌ {rel_path}: Unknown structure.")

    print("\n✅ Validation complete.")

if __name__ == "__main__":
    run_validation()
