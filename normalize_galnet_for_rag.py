import os
import json

INPUT_FILE = os.path.join("rag_data", "galnet_articles.json")
OUTPUT_FILE = os.path.join("rag_data", "galnet_articles_rag.json")

def convert_entry(article):
    return {
        "id": f"galnet_{article.get('uid', 'unknown')}",
        "name": article.get("title", "Untitled"),
        "description": article.get("content", "").strip()
    }

def normalize_galnet():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Input file not found: {INPUT_FILE}")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            if not isinstance(data, list):
                print("❌ galnet_articles.json is not a list.")
                return
        except json.JSONDecodeError:
            print("❌ Invalid JSON in galnet_articles.json.")
            return

    converted = [convert_entry(entry) for entry in data]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(converted, f, indent=2)

    print(f"✅ Normalized {len(converted)} articles to: {OUTPUT_FILE}")

if __name__ == "__main__":
    normalize_galnet()
