import os
import json
import logging
from typing import List, Any

def merge_ships(data_dir: str, output_filename: str) -> None:
    """
    Merges ship data from all JSON files in the specified directory that start with 'ships_'
    into one combined JSON file.
    
    Args:
        data_dir (str): The directory containing the ship JSON files.
        output_filename (str): The filename for the combined output JSON.
    """
    merged_ships: List[Any] = []
    
    if not os.path.exists(data_dir):
        logging.error(f"Data directory not found: {data_dir}")
        return
    
    for filename in os.listdir(data_dir):
        if filename.startswith("ships_") and filename.endswith(".json"):
            filepath = os.path.join(data_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        merged_ships.extend(data)
                    else:
                        logging.warning(f"Data in {filename} is not a list; skipping file.")
            except Exception as e:
                logging.error(f"Error reading {filepath}: {e}")
    
    try:
        with open(output_filename, "w", encoding="utf-8") as out_file:
            json.dump(merged_ships, out_file, indent=2)
        logging.info(f"✅ Merged {len(merged_ships)} ships into {output_filename}")
    except Exception as e:
        logging.error(f"Error writing output file {output_filename}: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    DATA_DIR = os.path.join(os.path.dirname(__file__), "rag_data")
    OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "ships_combined.json")
    merge_ships(DATA_DIR, OUTPUT_FILE)
