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
                device_name = data.get('device_name')
                # If the friendly_name is still the default (MAC address), update it.
                if device.friendly_name == device.mac:
                    device.friendly_name = device_name

                # Parse category and vendor from device_name
                if '/' in device_name:
                    parts = device_name.split('/', 1)
                    device.category = parts[0].strip()
                    device.vendor = parts[1].strip()
                else:
                    # If no slash, the whole name is the category
                    device.category = device_name.strip()
                    device.vendor = None

                # Extract vulnerabilities and handle different response formats
                vulnerabilities = data.get('vulnerabilities')

                # The API may return a dictionary with a 'message' key for no CVEs,
                # an empty list, or a list of CVEs.
                if vulnerabilities and vulnerabilities != {'message': 'No CVEs for this device'}:
                    device.vulnerabilities = True
                    logging.info(f"Vulnerabilities found for {device.friendly_name}.")
                else:
                    device.vulnerabilities = False

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
