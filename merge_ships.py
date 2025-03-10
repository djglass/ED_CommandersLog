import os, json

DATA_DIR = "./rag_data"
output = []

for filename in os.listdir(DATA_DIR):
    if filename.startswith("ships_") and filename.endswith(".json"):
        with open(os.path.join(DATA_DIR, filename), "r", encoding="utf-8") as f:
            data = json.load(f)
            output.extend(data)

with open("ships_combined.json", "w", encoding="utf-8") as out_file:
    json.dump(output, out_file, indent=2)

print(f"✅ Merged {len(output)} ships into ships_combined.json")
