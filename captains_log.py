from log_parser import parse_latest_log
from ai_generator import generate_log

def main():
    """Runs the entire Commander’s Log process."""
    cmdr_name, log_entry, session_activities, ship_status, powerplay, timestamps = parse_latest_log()

    if log_entry:
        enhanced_log = generate_log(cmdr_name, log_entry, session_activities)
        print(f"\n📖 {cmdr_name}’s Enhanced Commander’s Log:\n")
        print(enhanced_log)
    else:
        print("No valid hyperspace jump or location data found!")

if __name__ == "__main__":
    main()
