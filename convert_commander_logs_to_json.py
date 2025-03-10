import os
import json
import re

LOGS_DIR = os.path.join(os.path.dirname(__file__), "rag_data", "commander_logs")
OUTPUT_DIR = os.path.join(LOGS_DIR, "json")

os.makedirs(OUTPUT_DIR, exist_ok=True)

def parse_md_log(md_path):
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    log_data = {
        "commander": None,
        "date": None,
        "categories": {}
    }

    current_category = None

    for line in lines:
        line = line.strip()
        if line.startswith("# Commander"):
            # Extract commander name and log date
            match = re.match(r"# Commander ([\w\s]+) - Log (\d{4}-\d{2}-\d{2})", line)
            if match:
                log_data["commander"] = match.group(1).strip()
                log_data["date"] = match.group(2)
        elif line.startswith("## "):
            current_category = line[3:].strip()
            log_data["categories"][current_category] = []
        elif line.startswith("- ") and current_category:
            event = line[2:].strip()
            log_data["categories"][current_category].append(event)

    return log_data

def convert_all_logs():
    print(f"🔍 Converting .md logs in {LOGS_DIR} to JSON...\n")
    count = 0
    for filename in os.listdir(LOGS_DIR):
        if filename.endswith(".md"):
            md_path = os.path.join(LOGS_DIR, filename)
            log_data = parse_md_log(md_path)
            if log_data["commander"] and log_data["date"]:
                json_path = os.path.join(OUTPUT_DIR, f"{log_data['date']}.json")
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(log_data, f, indent=2)
                print(f"✅ Converted: {filename} → {json_path}")
                count += 1
            else:
                print(f"⚠️ Skipped: {filename} (missing header info)")
    print(f"\n🎉 Done. {count} logs converted.")

if __name__ == "__main__":
    convert_all_logs()
