from datetime import datetime
from typing import Optional, List
import logging
from .scanner import NmapScanner
from .fingerbank import FingerbankClient
from .config import load_config
from pathlib import Path
from .models import Device, Fingerprint


class Inventory:
    """Manages the collection of all known devices."""
    def __init__(self, persistence_file: Path, offline_debounce_scans: int = 2):
        self.devices = {}  # Keyed by MAC address
        self.persistence_file = persistence_file
        self.events = [] # To log recent events
        self.offline_debounce_scans = offline_debounce_scans
        # A temporary dict to track how many consecutive scans a device has been missing
        self._offline_counters = {}
        self.load_from_disk()

    def _add_event(self, event_type: str, device: Device, message: str, webhook_url: Optional[str] = None):
        """
        Adds a new event to the log and triggers a notification if applicable.
        """
        logging.info(message)
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "device": device.to_dict(),
            "message": message
        }
        self.events.insert(0, event)
        if len(self.events) > 200:
            self.events.pop()

        # Notification logic
        # Import here to avoid circular dependency
        from .notifications import send_notification
        if event_type == "device_joined":
            send_notification(webhook_url, event_type, device)
        elif event_type == "device_offline" and device.alert_on_offline:
            send_notification(webhook_url, event_type, device)

    def update_from_scan(self, scan_results: List[dict], webhook_url: Optional[str] = None):
        """
        Updates the inventory based on a list of devices found in a new scan.
        Detects new devices, status changes, and IP changes.
        """
        logging.info(f"Raw scan results: {scan_results}")
        now = datetime.now()
        scanned_macs = set()

        for scanned_device_data in scan_results:
            mac = scanned_device_data.get('mac')
            if not mac:
                continue
            
            mac = mac.upper()
            scanned_macs.add(mac)
            
            existing_device = self.get_device(mac)
            ip = scanned_device_data.get('ip')

            if existing_device is None:
                # New device found
                new_device = Device(
                    mac=mac,
                    ip_addresses=[ip] if ip else [],
                    vendor=scanned_device_data.get('vendor'),
                    hostname=scanned_device_data.get('hostname'),
                    subnet=scanned_device_data.get('subnet'),
                    status="online",
                    first_seen=now,
                    last_seen=now,
                    friendly_name=mac  # Default friendly_name to MAC address
                )
                self.devices[mac] = new_device
                self._add_event("device_joined", new_device, f"New device {mac} joined with IP {ip}", webhook_url)
                
                # Perform fingerprint scan for the new device
                if ip and ip != '----------':
                    nmap_scanner = NmapScanner(subnets=[])
                    fingerprint = nmap_scanner.scan_for_fingerprint(ip)
                    if fingerprint:
                        new_device.fingerprint = fingerprint
                        logging.info(f"Successfully fingerprinted new device {new_device.friendly_name}")
                        
                        # Enrich with Fingerbank data
                        config = load_config(Path(__file__).parent.parent / "config.yaml")
                        fb_api_key = config.get('fingerbank', {}).get('api_key')
                        if fb_api_key:
                            fb_client = FingerbankClient(api_key=fb_api_key)
                            fb_client.enrich_device(new_device)
                        else:
                            logging.warning("Fingerbank API key not found in config.yaml. Skipping enrichment.")

            else:
                # Existing device, update its state
                existing_device.last_seen = now
                
                # Update hostname if it's not already set
                if not existing_device.hostname and scanned_device_data.get('hostname'):
                    existing_device.hostname = scanned_device_data.get('hostname')
                    # Also update friendly_name if it was using the default (MAC address)
                    if not existing_device.friendly_name or existing_device.friendly_name == existing_device.mac:
                        existing_device.friendly_name = existing_device.hostname

                if existing_device.status == "offline":
                    existing_device.status = "online"
                    self._add_event("device_reconnected", existing_device, f"Device {existing_device.friendly_name} came back online.", webhook_url)
                
                if ip and ip not in existing_device.ip_addresses:
                    existing_device.ip_addresses.append(ip)
                    self._add_event("ip_change", existing_device, f"Device {existing_device.friendly_name} detected with new IP {ip}", webhook_url)

                # Reset the offline counter since the device was seen
                self._offline_counters.pop(mac, None)

        # Check for devices that are now offline
        inventory_macs = set(self.devices.keys())
        missing_macs = inventory_macs - scanned_macs

        for mac in missing_macs:
            device = self.get_device(mac)
            if device.status == "online":
                self._offline_counters[mac] = self._offline_counters.get(mac, 0) + 1
                if self._offline_counters[mac] >= self.offline_debounce_scans:
                    device.status = "offline"
                    self._add_event("device_offline", device, f"Device {device.friendly_name} is now offline.", webhook_url)
                    # Remove from counter once marked offline
                    self._offline_counters.pop(mac, None)

        self.save_to_disk()


    def get_device(self, mac: str) -> Optional[Device]:
        """Retrieves a device by its MAC address."""
        return self.devices.get(mac)

    def all_devices(self) -> List[Device]:
        """Returns a list of all devices."""
        return list(self.devices.values())

    def update_device_details(self, mac: str, friendly_name: str, notes: str, alert_on_offline: bool) -> Optional[Device]:
        """Updates the friendly name, notes, and alert settings for a specific device."""
        device = self.get_device(mac)
        if device:
            device.friendly_name = friendly_name
            device.notes = notes
            device.alert_on_offline = alert_on_offline
            self.save_to_disk()
            return device
        return None

    def save_to_disk(self):
        """Saves the current inventory to a JSON file."""
        try:
            with open(self.persistence_file, "w") as f:
                import json
                json.dump([dev.to_dict() for dev in self.devices.values()], f, indent=2)
        except IOError as e:
            logging.error(f"Error saving inventory to {self.persistence_file}: {e}")

    def load_from_disk(self):
        """Loads the inventory from a JSON file."""
        try:
            with open(self.persistence_file, "r") as f:
                import json
                devices_data = json.load(f)
                self.devices = {dev['mac']: Device.from_dict(dev) for dev in devices_data}
        except FileNotFoundError:
            # It's okay if the file doesn't exist on first run
            self.devices = {}
        except (IOError, json.JSONDecodeError) as e:
            logging.error(f"Error loading inventory from {self.persistence_file}: {e}")
            self.devices = {}


# Example of how to use it:
if __name__ == '__main__':
    # --- Test Device Class ---
    print("--- Testing Device Class ---")
    device = Device(mac="AA:BB:CC:DD:EE:FF", ip_addresses=["192.168.1.10"], vendor="Apple", hostname="my-iphone")
    print(f"New Device: {device}")
    device_dict = device.to_dict()
    print(f"As Dictionary: {device_dict}")
    device_from_dict = Device.from_dict(device_dict)
    print(f"From Dictionary: {device_from_dict}")
    assert device == device_from_dict

    # --- Test Inventory Class ---
    print("\n--- Testing Inventory Class ---")
    test_persistence_file = "test_devices.json"
    
    # 1. Test basic save and load
    inventory = Inventory(persistence_file=test_persistence_file)
    inventory.devices[device.mac] = device
    inventory.save_to_disk()
    new_inventory = Inventory(persistence_file=test_persistence_file)
    assert len(new_inventory.all_devices()) == 1
    assert new_inventory.get_device("AA:BB:CC:DD:EE:FF") is not None

    # 2. Test update_from_scan logic
    print("\n--- Testing Scan Logic ---")
    inventory = Inventory(persistence_file=test_persistence_file)
    
    # Scan 1: A new device appears
    scan1 = [{'mac': '11:22:33:44:55:66', 'ip': '192.168.1.50', 'vendor': 'Netgear'}]
    inventory.update_from_scan(scan1)
    print(f"Event: {inventory.events[0]['message']}")
    assert len(inventory.all_devices()) == 1
    assert inventory.get_device('11:22:33:44:55:66').status == 'online'

    # Scan 2: The device is still here
    inventory.update_from_scan(scan1)
    assert len(inventory.events) == 1 # No new event

    # Scan 3: The device is missing (should not be offline yet)
    inventory.update_from_scan([])
    assert inventory.get_device('11:22:33:44:55:66').status == 'online'
    assert len(inventory.events) == 1 # No new event

    # Scan 4: The device is missing again (should be marked offline)
    inventory.update_from_scan([])
    print(f"Event: {inventory.events[0]['message']}")
    assert inventory.get_device('11:22:33:44:55:66').status == 'offline'
    assert len(inventory.events) == 2

    # Scan 5: The device reappears
    inventory.update_from_scan(scan1)
    print(f"Event: {inventory.events[0]['message']}")
    assert inventory.get_device('11:22:33:44:55:66').status == 'online'
    assert len(inventory.events) == 3

    # Clean up
    import os
    if os.path.exists(test_persistence_file):
        os.remove(test_persistence_file)
    print(f"\nCleaned up {test_persistence_file}.")
