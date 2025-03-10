import logging
from log_parser import parse_latest_log
from ai_generator import generate_log
from typing import Any

def main() -> None:
    """
    Runs the entire Commander’s Log process by parsing the latest log and generating an enhanced log.
    """
    try:
        cmdr_name, log_entry, session_activities, ship_status, powerplay, timestamps = parse_latest_log()
        if log_entry:
            enhanced_log: str = generate_log(cmdr_name, log_entry, session_activities)
            logging.info(f"\n📖 {cmdr_name}’s Enhanced Commander’s Log:\n{enhanced_log}")
        else:
            logging.info("No valid hyperspace jump or location data found!")
    except Exception as e:
        logging.error(f"An error occurred while generating the log: {e}")

if __name__ == "__main__":
    # Set up basic logging configuration
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    main()
