import os
import json
import glob
import re
import logging
from datetime import datetime
from collections import defaultdict

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Paths and directories
LOG_DIR = os.path.join(
    os.environ["USERPROFILE"],
    "Saved Games",
    "Frontier Developments",
    "Elite Dangerous"
)
OUTPUT_DIR = "rag_data/commander_logs"
INDEX_FILE = "rag_data/processed_index.json"

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load processed log index
if os.path.exists(INDEX_FILE):
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        processed_logs = set(json.load(f))
else:
    processed_logs = set()


def extract_events(logfile):
    """Extracts key events from a single Elite Dangerous log file and groups them by date."""
    daily_events = defaultdict(lambda: defaultdict(list))

    try:
        with open(logfile, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    event_data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                timestamp = event_data.get("timestamp")
                if not timestamp:
                    continue
                
                event_date = datetime.fromisoformat(timestamp.replace("Z", "")).strftime("%Y-%m-%d")
                event_type = event_data.get("event", "Unknown Event")

                # Process only meaningful events
                if event_type == "FSDJump":
                    system = event_data.get("StarSystem", "Unknown System")
                    daily_events[event_date]["Travel"].append(f"Jumped to **{system}**.")

                elif event_type == "Docked":
                    station = event_data.get("StationName", "Unknown Station")
                    system = event_data.get("StarSystem", "Unknown System")
                    daily_events[event_date]["Docking"].append(f"Docked at **{station}** in **{system}**.")

                elif event_type == "Undocked":
                    station = event_data.get("StationName", "Unknown Station")
                    daily_events[event_date]["Docking"].append(f"Undocked from **{station}**.")

                elif event_type == "Location":
                    system = event_data.get("StarSystem", "Unknown System")
                    body = event_data.get("Body", "Deep Space")
                    daily_events[event_date]["Location"].append(f"Current location: **{system}**, **{body}**.")

                elif event_type == "Bounty":
                    reward = event_data.get("Reward", 0)
                    daily_events[event_date]["Combat"].append(f"Claimed a bounty of **{reward:,} Cr**.")

                elif event_type == "MarketBuy":
                    count = event_data.get("Count", 1)
                    item = event_data.get("Type", "Unknown Item")
                    daily_events[event_date]["Trade"].append(f"Purchased **{count}x {item}**.")

                elif event_type == "MarketSell":
                    count = event_data.get("Count", 1)
                    item = event_data.get("Type", "Unknown Item")
                    profit = event_data.get("TotalSale", 0)
                    daily_events[event_date]["Trade"].append(f"Sold **{count}x {item}** for **{profit:,} Cr**.")

                elif event_type == "Materials":
                    raw_mats = len(event_data.get("Raw", []))
                    encoded_mats = len(event_data.get("Encoded", []))
                    manu_mats = len(event_data.get("Manufactured", []))
                    daily_events[event_date]["Materials"].append(
                        f"Gathered materials: **{raw_mats} Raw**, **{encoded_mats} Encoded**, **{manu_mats} Manufactured**."
                    )

                elif event_type == "MissionAccepted":
                    mission_type = event_data.get("Name", "Unknown Mission")
                    daily_events[event_date]["Missions"].append(f"Accepted mission: **{mission_type}**.")

                elif event_type == "MissionCompleted":
                    mission_type = event_data.get("Name", "Unknown Mission")
                    payout = event_data.get("Reward", 0)
                    daily_events[event_date]["Missions"].append(f"Completed mission: **{mission_type}**, earning **{payout:,} Cr**.")

    except Exception as e:
        logging.error(f"Error processing {logfile}: {e}")

    return daily_events


def save_markdown_summaries(daily_events):
    """Saves daily events into Markdown files."""
    for date, events in daily_events.items():
        md_file = os.path.join(OUTPUT_DIR, f"{date}.md")

        with open(md_file, "w", encoding="utf-8") as f:
            f.write(f"# Commander TOADIE MUDGUTS - Log {date}\n\n")

            for category, entries in events.items():
                f.write(f"## {category}\n")
                for entry in entries:
                    f.write(f"- {entry}\n")
                f.write("\n")

        logging.info(f"Saved daily log: {md_file}")


def main():
    """Scans all logs, extracts summaries, and writes Markdown files."""
    all_log_files = glob.glob(os.path.join(LOG_DIR, "Journal.*.log"))
    new_logs = [lf for lf in all_log_files if lf not in processed_logs]

    if not new_logs:
        logging.info("No new logs to process.")
        return

    all_events = defaultdict(lambda: defaultdict(list))

    for logfile in new_logs:
        logging.info(f"Processing {logfile}...")
        events = extract_events(logfile)

        for date, event_dict in events.items():
            for category, entries in event_dict.items():
                all_events[date][category].extend(entries)

        processed_logs.add(logfile)

    save_markdown_summaries(all_events)

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(list(processed_logs), f, indent=4)

    logging.info("Processing complete.")


if __name__ == "__main__":
    main()
