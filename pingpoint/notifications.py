import requests
import logging
from .inventory import Device

def send_notification(webhook_url: str, event_type: str, device: Device):
    """
    Sends a notification to the configured Home Assistant webhook.

    Args:
        webhook_url: The Home Assistant webhook URL.
        event_type: The type of event (e.g., 'device_joined', 'device_offline').
        device: The device object related to the event.
    """
    if not webhook_url:
        logging.warning("Webhook URL is not configured. Skipping notification.")
        return

    payload = {
        "event": event_type,
        "device": device.friendly_name,
        "ip": ", ".join(device.ip_addresses),
        "mac": device.mac,
        "vendor": device.vendor,
        "time": device.last_seen.isoformat()
    }

    try:
        logging.info(f"Sending notification for event '{event_type}' for device {device.mac}")
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes
        logging.info("Notification sent successfully.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send notification to Home Assistant: {e}")

# Example of how to use it:
if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    from datetime import datetime

    load_dotenv()
    TEST_WEBHOOK_URL = os.getenv("TEST_WEBHOOK_URL")

    if not TEST_WEBHOOK_URL:
        print("Please set TEST_WEBHOOK_URL in your .env file to test notifications.")
    else:
        logging.basicConfig(level=logging.INFO)
        test_device = Device(
            mac="DE:AD:BE:EF:00:01",
            ip_addresses=["192.168.1.99"],
            friendly_name="Test Device",
            vendor="TestVendor Inc.",
            last_seen=datetime.now()
        )
        send_notification(TEST_WEBHOOK_URL, "device_joined", test_device)
