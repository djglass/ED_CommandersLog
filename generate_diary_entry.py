import argparse
import glob
import json
import os
import logging
from ai_generation import generate_diary, save_diary

# === PATHS ===
BASE_DIR = os.path.dirname(__file__)
COMMANDER_LOGS_FOLDER = os.path.join(BASE_DIR, "rag_data", "commander_logs")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def list_available_log_dates():
    json_files = sorted(glob.glob(os.path.join(COMMANDER_LOGS_FOLDER, "*.json")))
    return [os.path.splitext(os.path.basename(f))[0] for f in json_files]

def load_commander_log(date: str):
    log_file = os.path.join(COMMANDER_LOGS_FOLDER, f"{date}.json")
    if not os.path.exists(log_file):
        raise FileNotFoundError(f"No log file for date: {date}")

    with open(log_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        commander = data.get("commander", "Unknown Commander")
        activities = []
        for category, entries in data.get("categories", {}).items():
            activities.extend(entries)
        return commander, activities

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Commander Toadie Mudguts' Personal Log")
    parser.add_argument("--date", help="Log date (YYYY-MM-DD)")
    args = parser.parse_args()

    date = args.date
    available = list_available_log_dates()

    if not available:
        print("❌ No commander logs found.")
        exit()

    if not date:
        print("\n📅 Available Commander Log Dates:")
        for i, d in enumerate(available):
            print(f"{i+1}. {d}")
        choice = input("\nEnter number to select date or press Enter to use latest: ")
        if choice.strip().isdigit():
            index = int(choice.strip()) - 1
            if 0 <= index < len(available):
                date = available[index]
        if not date:
            date = available[-1]  # Default to latest

    try:
        commander, session_activities = load_commander_log(date)
        log_text = generate_diary(commander, date, session_activities)
        print(f"\n📖 {commander}'s Personal Log ({date}):\n")
        print(log_text)
        save_diary(date, log_text)
    except Exception as e:
        print(f"❌ Error: {e}")
