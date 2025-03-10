import json
import glob
import os
import re
from datetime import datetime
from collections import defaultdict

# Load config
config_path = os.path.join(os.path.dirname(__file__), "config.json")
with open(config_path, "r") as f:
    config = json.load(f)

log_dir = os.path.expandvars(config["log_directory"])
log_files = glob.glob(os.path.join(log_dir, "Journal.*.log"))
status_file = os.path.join(log_dir, "Status.json")
cargo_file = os.path.join(log_dir, "Cargo.json")
backpack_file = os.path.join(log_dir, "Backpack.json")
ship_locker_file = os.path.join(log_dir, "ShipLocker.json")
previous_state_file = os.path.join(log_dir, "previous_state.json")  # Store previous session data
session_log_file = os.path.join(log_dir, "session_logs.json")  # Store historical logs

# Load previous material states from file if available
if os.path.exists(previous_state_file):
    with open(previous_state_file, "r", encoding="utf-8") as f:
        previous_materials = json.load(f)
else:
    previous_materials = {"Cargo": {}, "Backpack": {}, "ShipLocker": {}}

def save_previous_state(data):
    """Save material states to a file for persistent tracking."""
    with open(previous_state_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def save_session_log(session_data):
    """Save session logs for historical tracking."""
    if os.path.exists(session_log_file):
        with open(session_log_file, "r", encoding="utf-8") as f:
            logs = json.load(f)
    else:
        logs = []

    logs.append(session_data)

    with open(session_log_file, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=4)

def get_log_timestamp(filename):
    """Extracts timestamp from Elite Dangerous log filenames."""
    match = re.search(r"Journal\.(\d{4}-\d{2}-\d{2}T\d{6})", filename)
    return match.group(1) if match else "0000-00-00T000000"

def parse_latest_log():
    """Finds and extracts system location, CMDR name, session activities, and ship status from the latest Elite Dangerous log."""
    if not log_files:
        return None, None, [], {"fuel": "Unknown", "modules": "No reported damage"}, None, {}

    # Sort files by filename timestamp instead of creation time
    latest_file = max(log_files, key=get_log_timestamp)

    cmdr_name = "Commander"
    latest_entry = None
    session_activities = []
    ship_status = {"fuel": "Unknown", "modules": "No reported damage"}
    powerplay_faction = None
    event_timestamps = {}

    print(f"DEBUG: Reading log file: {latest_file}")  # Debugging

    with open(latest_file, "r", encoding="utf-8") as file:
        for line in file:
            try:
                data = json.loads(line)
                event_time = data.get("timestamp", "Unknown Timestamp")

                # Extract CMDR Name
                if "Commander" in data:
                    cmdr_name = f"CMDR {data['Commander']}"

                # Extract System & Location
                if data.get("event") == "FSDJump":
                    latest_entry = f"Commander’s Log: Arrived in {data['StarSystem']} at {event_time}."
                    event_timestamps["location"] = event_time
                elif data.get("event") == "Location":
                    latest_entry = f"Commander’s Log: Currently at {data['StarSystem']} - {data['Body']} at {event_time}."
                    event_timestamps["location"] = event_time

                # Track ship status
                if data.get("event") == "FuelScoop":
                    ship_status["fuel"] = f"{data['Total']} tons (after scooping)"
                elif data.get("event") == "Repair":
                    session_activities.append(f"Repaired {data['Item']} at {event_time}.")
                elif data.get("event") == "HullDamage":
                    ship_status["modules"] = f"Hull integrity at {data['Health']}%."

                # Track activities
                if data.get("event") in ["Docked", "Undocked"]:
                    session_activities.append(f"{data['event']} at {data['StationName']} at {event_time}.")
                elif data.get("event") == "MiningRefined":
                    session_activities.append(f"Refined {data['Type']} while mining at {event_time}.")
                elif data.get("event") == "MarketBuy":
                    session_activities.append(f"Purchased {data['Count']}x {data['Type']} for trading at {event_time}.")
                elif data.get("event") == "MarketSell":
                    session_activities.append(f"Sold {data['Count']}x {data['Type']} for {data['TotalSale']} credits at {event_time}.")
                elif data.get("event") == "Bounty":
                    session_activities.append(f"Claimed a bounty of {data['Reward']} credits at {event_time}.")
                elif data.get("event") == "ThargoidEncounter":
                    session_activities.append(f"Encountered a Thargoid vessel at {event_time}.")

            except json.JSONDecodeError:
                continue  # Skip invalid JSON lines

    # Read Cargo, Backpack, and ShipLocker for Material Changes
    material_logs = []
    summary_changes = {"Added": defaultdict(int), "Removed": defaultdict(int)}

    for filename, category in [(cargo_file, "Cargo"), (backpack_file, "Backpack"), (ship_locker_file, "ShipLocker")]:
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    current_materials = {}
                    
                    if "Items" in data:
                        for item in data["Items"]:
                            current_materials[item["Name"]] = item["Count"]
                    
                    # Compare with previous state
                    for material, count in current_materials.items():
                        prev_count = previous_materials[category].get(material, 0)
                        if count > prev_count:
                            summary_changes["Added"][material] += count - prev_count
                        elif count < prev_count:
                            summary_changes["Removed"][material] += prev_count - count

                    # Update stored state
                    previous_materials[category] = current_materials

                except json.JSONDecodeError:
                    print(f"WARNING: Could not read {filename}")

    # Generate summary
    summary_text = []
    for change_type, materials in summary_changes.items():
        if materials:
            summary_text.append(f"{change_type}: " + ", ".join([f"{count}x {mat}" for mat, count in materials.items()]))

    if summary_text:
        session_activities.append("Inventory updates: " + " | ".join(summary_text))

    # Save new material states for future comparisons
    save_previous_state(previous_materials)

    # Save session log
    session_data = {
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
        print(f"{cmdr}: {log_entry}")
        print(f"\nShip Status: {ship_status}")
        if activities:
            print("\nSession Activities:")
            for activity in activities:
                print(f"- {activity}")
        print("\nEvent Timestamps:", timestamps)
    else:
        print("No valid hyperspace jump or location data found!")
