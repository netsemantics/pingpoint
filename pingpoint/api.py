from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pingpoint.inventory import Inventory
from pingpoint.scanner import EdgeMaxScanner, NmapScanner
from pingpoint.config import load_config
from pathlib import Path

# Path to the project root directory
ROOT_DIR = Path(__file__).parent.parent

class DeviceDetails(BaseModel):
    friendly_name: str
    notes: str
    alert_on_offline: bool

# Initialize the FastAPI app
app = FastAPI(
    title="PingPoint",
    description="A home network monitoring service.",
    version="1.0.0"
)

# This will be our single, shared inventory instance
# In a real application, you might manage this dependency more robustly
inventory = Inventory(persistence_file=str(ROOT_DIR / "devices.json"))

# Mount the 'static' directory to serve frontend files
# The path is constructed relative to the project root
app.mount("/static", StaticFiles(directory=ROOT_DIR / "static"), name="static")

@app.get("/")
async def read_root():
    """
    Root endpoint, can be used for a simple health check.
    """
    return {"message": "PingPoint API is running."}


@app.get("/api/devices")
async def get_devices():
    """
    Returns a list of all known devices from the inventory.
    """
    return inventory.all_devices()


@app.get("/api/events")
async def get_events():
    """
    Returns a list of recent events.
    """
    return inventory.events


def run_and_update_scan(scanner_instance):
    """Helper function to run a scan and update the inventory."""
    config = load_config(ROOT_DIR / "config.yaml")
    webhook_url = config.get('home_assistant', {}).get('webhook_url')
    try:
        results = scanner_instance.scan()
        inventory.update_from_scan(results, webhook_url)
        inventory.save_to_disk()
    except Exception as e:
        logging.error(f"Manual scan failed: {e}")


@app.post("/api/scan/edgemax")
async def trigger_edgemax_scan(background_tasks: BackgroundTasks):
    """Triggers a network scan using the EdgeMax router."""
    try:
        config = load_config(ROOT_DIR / "config.yaml")
        em_config = config['edgemax']
        scanner = EdgeMaxScanner(
            host=em_config['host'],
            port=em_config['port'],
            username=em_config['username'],
            password=em_config['password']
        )
        background_tasks.add_task(run_and_update_scan, scanner)
        return {"message": "EdgeMax scan initiated in the background."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scan/nmap")
async def trigger_nmap_scan(background_tasks: BackgroundTasks):
    """Triggers a network scan using Nmap."""
    try:
        config = load_config(ROOT_DIR / "config.yaml")
        scanner = NmapScanner(subnets=config['subnets'])
        background_tasks.add_task(run_and_update_scan, scanner)
        return {"message": "Nmap scan initiated in the background."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/device/{mac}")
async def update_device(mac: str, details: DeviceDetails):
    """Updates a device's friendly name, notes, and alert settings."""
    updated_device = inventory.update_device_details(
        mac=mac.upper(),
        friendly_name=details.friendly_name,
        notes=details.notes,
        alert_on_offline=details.alert_on_offline
    )
    if updated_device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return updated_device


# To run this application for development:
# uvicorn pingpoint.api:app --reload
