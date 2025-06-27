import logging
from pathlib import Path
from pingpoint.config import load_config

def setup_logging():
    """Configures basic logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

import time
import threading
import uvicorn
from pingpoint.scanner import scan_network
from pingpoint.api import app, inventory

def run_scanner(inventory_instance):
    """The main scanning loop."""
    config_path = Path(__file__).parent.parent / "config.yaml"

    while True:
        try:
            config = load_config(config_path)
            scan_interval_minutes = config.get('scan_interval', 2)
            webhook_url = config.get('home_assistant', {}).get('webhook_url')

            logging.info("Starting network scan...")
            scan_results = scan_network(config)
            inventory_instance.update_from_scan(scan_results, webhook_url)
            inventory_instance.save_to_disk()
            logging.info(f"Scan complete. Found {len(scan_results)} devices.")
        except Exception as e:
            logging.error(f"An error occurred during the scan cycle: {e}")
            # Set a default scan interval in case of config load failure
            scan_interval_minutes = 2
        
        logging.info(f"Waiting {scan_interval_minutes} minutes for the next scan.")
        time.sleep(scan_interval_minutes * 60)

def main():
    """Main entry point for the PingPoint application."""
    setup_logging()
    logging.info("Starting PingPoint application...")

    try:
        # Construct path to config.yaml in the project root
        config_path = Path(__file__).parent.parent / "config.yaml"
        config = load_config(config_path)
        logging.info("Configuration loaded successfully.")
    except FileNotFoundError as e:
        logging.error(f"FATAL: Configuration file not found at {config_path.resolve()}. Please create it from config.yaml.example. Error: {e}")
        return
    except Exception as e:
        logging.error(f"FATAL: An unexpected error occurred during startup: {e}")
        return

    # Start the scanner in a background thread
    scanner_thread = threading.Thread(target=run_scanner, args=(inventory,), daemon=True)
    scanner_thread.start()

    # Start the FastAPI server
    logging.info("Starting web server on http://0.0.0.0:8000")
    try:
        uvicorn.run(app, host="0.0.0.0", port=8000)
    finally:
        logging.info("Shutting down. Saving inventory...")
        inventory.save_to_disk()
        logging.info("Inventory saved.")


if __name__ == "__main__":
    main()
