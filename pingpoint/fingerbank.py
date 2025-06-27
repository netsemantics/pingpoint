import requests
import logging
from typing import Optional
from .models import Fingerprint, Device

class FingerbankClient:
    """
    A client for interacting with the Fingerbank API.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.fingerbank.org/api/v2"

    def enrich_device(self, device: Device) -> bool:
        """
        Enriches a device object with data from the Fingerbank API.

        Args:
            device: The device object to enrich.

        Returns:
            True if the device was successfully enriched, False otherwise.
        """
        if not device.fingerprint:
            logging.warning(f"Device {device.friendly_name} has no fingerprint to enrich.")
            return False

        payload = self._prepare_payload(device.fingerprint, device.mac)
        headers = {"Content-Type": "application/json"}
        url = f"{self.base_url}/combinations/interrogate?key={self.api_key}"

        try:
            logging.info(f"Querying Fingerbank for device {device.friendly_name}")
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            if data.get('device_name'):
                # If the friendly_name is still the default (MAC address), update it.
                if device.friendly_name == device.mac:
                    device.friendly_name = data.get('device_name')

                # Always update the vendor if available
                device.vendor = data.get('device', {}).get('vendor', {}).get('name') or device.vendor
                
                # Extract vulnerabilities
                if 'vulnerabilities' in data:
                    device.vulnerabilities = data['vulnerabilities']
                    logging.info(f"Found {len(data['vulnerabilities'])} vulnerabilities for {device.friendly_name}.")

                logging.info(f"Successfully enriched device {device.friendly_name} from Fingerbank.")
                return True
            else:
                logging.info(f"Fingerbank had no information for device {device.friendly_name}")
                return False

        except requests.RequestException as e:
            logging.error(f"Fingerbank API request failed: {e}")
            return False

    def _prepare_payload(self, fingerprint: Fingerprint, mac: str) -> dict:
        """Prepares the payload for the Fingerbank API request."""
        payload = {
            "mac": mac,
            "dhcp_fingerprint": fingerprint.os_match,
        }
        # Add open ports to the payload if available
        if fingerprint.ports:
            payload["open_ports"] = [p["portid"] for p in fingerprint.ports]

        return payload
