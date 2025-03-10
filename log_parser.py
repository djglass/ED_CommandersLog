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
previous_state_file: str = os.path.join(log_dir, "previous_state.json")  # Persistent state
session_log_file: str = os.path.join(log_dir, "session_logs.json")       # Historical logs

# Load previous material states with error handling
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
    """Save material states to a file for persistent tracking."""
    try:
        with open(previous_state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        logging.info("Previous state saved successfully.")
    except Exception as e:
        logging.error(f"Error saving previous state: {e}")


def save_session_log(session_data: Dict[str, Any]) -> None:
    """Save session logs for historical tracking."""
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
    """Extract timestamp from log filename using regex."""
    match = re.search(r"Journal\.(\d{4}-\d{2}-\d{2}T\d{6})", filename)
    return match.group(1) if match else "0000-00-00T000000"


def process_event(
    data: Dict[str, Any],
    session_activities: List[str],
    ship_status: Dict[str, str],
    event_timestamps: Dict[str, str]
) -> Optional[str]:
    """
    Process a single log event.
    
    Updates session_activities, ship_status, and event_timestamps based on the event type.
    Returns a location log entry if the event indicates a change in location.
    """
    event: str = data.get("event", "")
    event_time: str = data.get("timestamp", "Unknown Timestamp")
    location_entry: Optional[str] = None

    if event == "FSDJump":
        location_entry = f"Commander’s Log: Arrived in {data.get('StarSystem', 'Unknown System')} at {event_time}."
        event_timestamps["location"] = event_time
    elif event == "Location":
        location_entry = f"Commander’s Log: Currently at {data.get('StarSystem', 'Unknown System')} - {data.get('Body', 'Unknown Body')} at {event_time}."
        event_timestamps["location"] = event_time
    elif event == "FuelScoop":
        ship_status["fuel"] = f"{data.get('Total', 'Unknown')} tons (after scooping)"
    elif event == "Repair":
        session_activities.append(f"Repaired {data.get('Item', 'Unknown item')} at {event_time}.")
    elif event == "HullDamage":
        ship_status["modules"] = f"Hull integrity at {data.get('Health', 'Unknown')}%."
    elif event in ["Docked", "Undocked"]:
        station: str = data.get("StationName", "Unknown Station")
        session_activities.append(f"{event} at {station} at {event_time}.")
    elif event == "MiningRefined":
        session_activities.append(f"Refined {data.get('Type', 'Unknown Type')} while mining at {event_time}.")
    elif event == "MarketBuy":
        session_activities.append(f"Purchased {data.get('Count', 'Unknown')}x {data.get('Type', 'Unknown')} for trading at {event_time}.")
    elif event == "MarketSell":
        session_activities.append(f"Sold {data.get('Count', 'Unknown')}x {data.get('Type', 'Unknown')} for {data.get('TotalSale', 'Unknown')} credits at {event_time}.")
    elif event == "Bounty":
        session_activities.append(f"Claimed a bounty of {data.get('Reward', 'Unknown')} credits at {event_time}.")
    elif event == "ThargoidEncounter":
        session_activities.append(f"Encountered a Thargoid vessel at {event_time}.")

    return location_entry


def parse_latest_log() -> Tuple[Optional[str], Optional[str], List[str], Dict[str, str], Optional[str], Dict[str, str]]:
    """
    Parse the latest Elite Dangerous log file and extract:
    - Commander name
    - Latest location entry log (if any)
    - Session activities
    - Ship status
    - Powerplay faction (if available; currently unused)
    - Event timestamps
    """
    if not log_files:
        logging.error("No log files found.")
        return None, None, [], {"fuel": "Unknown", "modules": "No reported damage"}, None, {}

    latest_file: str = max(log_files, key=get_log_timestamp)
    logging.info(f"Reading log file: {latest_file}")

    cmdr_name: str = "Commander"
    latest_entry: Optional[str] = None
    session_activities: List[str] = []
    ship_status: Dict[str, str] = {"fuel": "Unknown", "modules": "No reported damage"}
    powerplay_faction: Optional[str] = None
    event_timestamps: Dict[str, str] = {}

    try:
        with open(latest_file, "r", encoding="utf-8") as file:
            for line in file:
                try:
                    data: Dict[str, Any] = json.loads(line)
                    # Update commander name if available
                    if "Commander" in data:
                        cmdr_name = f"CMDR {data['Commander']}"
                    # Process the event and update state accordingly
                    entry: Optional[str] = process_event(data, session_activities, ship_status, event_timestamps)
                    if entry:
                        latest_entry = entry
                except json.JSONDecodeError:
                    logging.warning("Skipping invalid JSON line in log file.")
                except Exception as e:
                    logging.error(f"Error processing line in log file: {e}")
    except Exception as e:
        logging.error(f"Error reading log file {latest_file}: {e}")

    # Process inventory changes from Cargo, Backpack, and ShipLocker
    summary_changes: Dict[str, Dict[str, int]] = {"Added": defaultdict(int), "Removed": defaultdict(int)}
    for filename, category in [(cargo_file, "Cargo"), (backpack_file, "Backpack"), (ship_locker_file, "ShipLocker")]:
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    current_materials: Dict[str, int] = {}
                    if "Items" in data:
                        for item in data["Items"]:
                            current_materials[item["Name"]] = item["Count"]
                    for material, count in current_materials.items():
                        prev_count: int = previous_materials.get(category, {}).get(material, 0)
                        if count > prev_count:
                            diff = count - prev_count
                            summary_changes["Added"][material] += diff
                        elif count < prev_count:
                            summary_changes["Removed"][material] += prev_count - count
                    previous_materials[category] = current_materials
            except json.JSONDecodeError:
                logging.warning(f"Could not decode JSON from {filename}.")
            except Exception as e:
                logging.error(f"Error processing file {filename}: {e}")

    # Log materials collected as individual events
    for material, count in summary_changes["Added"].items():
        session_activities.append(f"Collected {count}x {material}.")

    # Generate a summary text for inventory updates (optional redundancy)
    summary_text: List[str] = []
    for change_type, materials in summary_changes.items():
        if materials:
            changes = ", ".join([f"{count}x {mat}" for mat, count in materials.items()])
            summary_text.append(f"{change_type}: {changes}")
    if summary_text:
        session_activities.append("Inventory updates: " + " | ".join(summary_text))

    # Save updated material state and session log
    save_previous_state(previous_materials)
    session_data: Dict[str, Any] = {
        "commander": cmdr_name,
        "log_entry": latest_entry,
        "ship_status": ship_status,
        "activities": session_activities,
        "event_timestamps": event_timestamps
    }
    save_session_log(session_data)

    return cmdr_name, latest_entry, session_activities, ship_status, powerplay_faction, event_timestamps


if __name__ == "__main__":
    cmdr, log_entry, activities, ship_status, powerplay, timestamps = parse_latest_log()
    if log_entry:
        logging.info(f"{cmdr}: {log_entry}")
        logging.info(f"Ship Status: {ship_status}")
        if activities:
            logging.info("Session Activities:")
            for activity in activities:
                logging.info(f"- {activity}")
        logging.info(f"Event Timestamps: {timestamps}")
    else:
        logging.info("No valid hyperspace jump or location data found!")
