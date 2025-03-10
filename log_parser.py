import json
import glob
import os
import re
import logging
from datetime import datetime
from collections import defaultdict
from typing import Tuple, List, Dict, Any, Optional

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Load configuration with error handling
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
try:
    with open(CONFIG_PATH, "r") as f:
        config: Dict[str, Any] = json.load(f)
except Exception as e:
    logging.error(f"Failed to load config from {CONFIG_PATH}: {e}")
    raise

# Directories and file paths
log_dir: str = os.path.expandvars(config.get("log_directory", "logs"))
log_files: List[str] = glob.glob(os.path.join(log_dir, "Journal.*.log"))
cargo_file: str = os.path.join(log_dir, "Cargo.json")
backpack_file: str = os.path.join(log_dir, "Backpack.json")
ship_locker_file: str = os.path.join(log_dir, "ShipLocker.json")
session_log_file: str = os.path.join(log_dir, "session_logs.json")       # Historical logs

# Define output folder and file names for history and processed index
rag_data_folder = os.path.join(os.path.dirname(__file__), "rag_data")
HISTORY_FILE = os.path.join(rag_data_folder, "commander_history.json")
INDEX_FILE = os.path.join(rag_data_folder, "commander_history_index.json")

# Load previous material states with error handling (unchanged)
previous_state_file: str = os.path.join(log_dir, "previous_state.json")
if os.path.exists(previous_state_file):
    try:
        with open(previous_state_file, "r", encoding="utf-8") as f:
            previous_materials: Dict[str, Dict[str, int]] = json.load(f)
    except Exception as e:
        logging.warning(f"Failed to load previous state from {previous_state_file}: {e}")
        previous_materials = {"Cargo": {}, "Backpack": {}, "ShipLocker": {}}
else:
    previous_materials = {"Cargo": {}, "Backpack": {}, "ShipLocker": {}}


def save_previous_state(data: Dict[str, Any]) -> None:
    try:
        with open(previous_state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        logging.info("Previous state saved successfully.")
    except Exception as e:
        logging.error(f"Error saving previous state: {e}")


def save_session_log(session_data: Dict[str, Any]) -> None:
    logs: List[Any] = []
    if os.path.exists(session_log_file):
        try:
            with open(session_log_file, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception as e:
            logging.warning(f"Failed to load existing session logs: {e}")
    logs.append(session_data)
    try:
        with open(session_log_file, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=4)
        logging.info("Session log saved successfully.")
    except Exception as e:
        logging.error(f"Error saving session log: {e}")


def get_log_timestamp(filename: str) -> str:
    match = re.search(r"Journal\.(\d{4}-\d{2}-\d{2}T\d{6})", filename)
    return match.group(1) if match else "0000-00-00T000000"


def process_event(data: Dict[str, Any]) -> Optional[str]:
    event = data.get("event", "")
    timestamp_str = data.get("timestamp", "Unknown Timestamp")
    
    # Skip non-essential events like Music.
    if event in ["Music"]:
        return None

    if event == "FSDJump":
        return f"Arrived in {data.get('StarSystem', 'Unknown System')} at {timestamp_str}."
    elif event == "Location":
        return f"Currently at {data.get('StarSystem', 'Unknown System')} on {data.get('Body', 'Unknown Body')} at {timestamp_str}."
    elif event == "FuelScoop":
        return f"Fuel scooped: total fuel now {data.get('Total', 'Unknown')} tons at {timestamp_str}."
    elif event == "Repair":
        return f"Repaired {data.get('Item', 'Unknown item')} at {timestamp_str}."
    elif event == "HullDamage":
        return f"Hull damage: integrity at {data.get('Health', 'Unknown')}% at {timestamp_str}."
    elif event in ["Docked", "Undocked"]:
        station = data.get("StationName", "Unknown Station")
        return f"{event} at {station} at {timestamp_str}."
    elif event == "MiningRefined":
        return f"Refined {data.get('Type', 'Unknown Type')} while mining at {timestamp_str}."
    elif event == "MarketBuy":
        return f"Purchased {data.get('Count', 'Unknown')}x {data.get('Type', 'Unknown')} for trading at {timestamp_str}."
    elif event == "MarketSell":
        return f"Sold {data.get('Count', 'Unknown')}x {data.get('Type', 'Unknown')} for {data.get('TotalSale', 'Unknown')} credits at {timestamp_str}."
    elif event == "Bounty":
        return f"Claimed a bounty of {data.get('Reward', 'Unknown')} credits at {timestamp_str}."
    elif event == "ThargoidEncounter":
        return f"Encountered a Thargoid vessel at {timestamp_str}."
    elif event == "Materials":
        raw_total = sum(item.get("Count", 0) for item in data.get("Raw", []))
        manu_total = sum(item.get("Count", 0) for item in data.get("Manufactured", []))
        encoded_total = sum(item.get("Count", 0) for item in data.get("Encoded", []))
        return (f"Gathered Materials at {timestamp_str}: "
                f"Raw: {raw_total}, Manufactured: {manu_total}, Encoded: {encoded_total}.")
    elif event in ["FSSSignalDiscovered", "ReceiveText"]:
        return f"{event} at {timestamp_str}."
    else:
        return f"{event} event at {timestamp_str}."


def load_processed_index() -> set:
    """Load processed log filenames from the index file."""
    if os.path.exists(INDEX_FILE):
        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                index = json.load(f)
            if isinstance(index, list):
                return set(index)
            else:
                logging.warning("Unexpected index format; reinitializing.")
                return set()
        except Exception as e:
            logging.error(f"Error loading index file: {e}")
            return set()
    else:
        return set()


def save_processed_index(processed_logs: set) -> None:
    """Save processed log filenames to the index file."""
    try:
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(list(processed_logs), f, indent=4)
        logging.info("Processed log index saved successfully.")
    except Exception as e:
        logging.error(f"Error saving processed log index: {e}")


def update_commander_history() -> None:
    """
    Scans all log files in the log directory and builds a daily history of the Commander's activities.
    It creates/updates a JSON file in the rag_data folder (commander_history.json) with daily event summaries.
    A separate index file (commander_history_index.json) is maintained for processed log filenames.
    Common events like FSSSignalDiscovered and ReceiveText are aggregated,
    and non-essential events (e.g., Music) are ignored.
    """
    if not os.path.exists(rag_data_folder):
        os.makedirs(rag_data_folder)
    
    # Load existing history; if none exists, initialize it.
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history_data = json.load(f)
            if not isinstance(history_data, dict):
                logging.warning("Unexpected history format; reinitializing.")
                history_data = {}
        except Exception as e:
            logging.error(f"Error loading commander history: {e}")
            history_data = {}
    else:
        history_data = {}
    
    processed_logs = load_processed_index()
    
    # Temporary dictionary to aggregate events by day and event type.
    daily_events = defaultdict(lambda: defaultdict(list))
    
    # Find all log files in the log directory.
    all_log_files = glob.glob(os.path.join(log_dir, "Journal.*.log"))
    new_logs = [lf for lf in all_log_files if lf not in processed_logs]
    
    if not new_logs:
        logging.info("No new log files to process for commander history.")
        return
    
    for logfile in new_logs:
        logging.info(f"Processing log file: {logfile}")
        try:
            with open(logfile, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event_data = json.loads(line)
                    except Exception as e:
                        logging.warning(f"Skipping invalid JSON line in {logfile}: {e}")
                        continue
                    
                    timestamp_str = event_data.get("timestamp")
                    if not timestamp_str:
                        continue
                    try:
                        event_dt = datetime.fromisoformat(timestamp_str.replace("Z", ""))
                    except Exception as e:
                        logging.warning(f"Invalid timestamp format in {logfile}: {timestamp_str}")
                        continue
                    date_key = event_dt.strftime("%Y-%m-%d")
                    
                    event_type = event_data.get("event", "Unknown Event")
                    # Skip non-essential events.
                    if event_type in ["Music"]:
                        continue
                    
                    description = process_event(event_data)
                    if not description:
                        continue
                    
                    # Aggregate common events.
                    if event_type in ["FSSSignalDiscovered", "ReceiveText"]:
                        daily_events[date_key][event_type].append(description)
                    else:
                        daily_events[date_key]["other"].append(description)
            processed_logs.add(logfile)
        except Exception as e:
            logging.error(f"Error processing log file {logfile}: {e}")
    
    # Build the final summary for each day.
    final_history = {}
    for day, events_by_type in daily_events.items():
        summary_lines = []
        for event_type, descriptions in events_by_type.items():
            if event_type in ["FSSSignalDiscovered", "ReceiveText"]:
                count = len(descriptions)
                example = descriptions[0] if descriptions else ""
                summary_lines.append(f"{event_type}: {count} events (e.g., {example})")
            else:
                summary_lines.extend(descriptions)
        final_history[day] = summary_lines

    # Update history data with new aggregated summaries.
    history_data.update(final_history)
    
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history_data, f, indent=4)
        logging.info(f"Commander history updated successfully at {HISTORY_FILE}.")
    except Exception as e:
        logging.error(f"Error saving commander history to {HISTORY_FILE}: {e}")
    
    save_processed_index(processed_logs)


if __name__ == "__main__":
    update_commander_history()
