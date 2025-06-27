from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import List, Optional
import yaml

from pingpoint.inventory import Inventory
from pingpoint.scanner import EdgeMaxScanner, NmapScanner
from pingpoint.config import load_config
from pathlib import Path
import logging

# Path to the project root directory
ROOT_DIR = Path(__file__).parent.parent

class DeviceDetails(BaseModel):
    friendly_name: str
    notes: str
    alert_on_offline: bool

class EdgeMaxConfig(BaseModel):
    host: str
    port: int = 22
    username: str
    password: Optional[str] = None

class HomeAssistantConfig(BaseModel):
    webhook_url: Optional[str] = None

class FingerbankConfig(BaseModel):
    api_key: Optional[str] = None

class AppConfig(BaseModel):
    scan_interval: int = Field(..., alias='scan_interval')
    subnets: List[str]
    edgemax: EdgeMaxConfig
    home_assistant: HomeAssistantConfig = Field(..., alias='home_assistant')
    fingerbank: FingerbankConfig

# Initialize the FastAPI app
app = FastAPI(
    title="PingPoint",
    description="A home network monitoring service.",
    version="1.0.0"
)

# This will be our single, shared inventory instance
# In a real application, you might manage this dependency more robustly
inventory = Inventory(persistence_file=ROOT_DIR / "devices.json")

# Mount the 'static' directory to serve frontend files
# The path is constructed relative to the project root
app.mount("/static", StaticFiles(directory=ROOT_DIR / "static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serves the main dashboard page."""
    with open(ROOT_DIR / "static/index.html") as f:
        return HTMLResponse(content=f.read(), status_code=200)

@app.get("/config", response_class=HTMLResponse)
async def read_config_page(request: Request):
    """Serves the configuration page."""
    with open(ROOT_DIR / "static/config.html") as f:
        return HTMLResponse(content=f.read(), status_code=200)


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
    inventory.save_to_disk()
    return updated_device

@app.get("/api/config")
async def get_config():
    """Returns the current application configuration."""
    try:
        return load_config(ROOT_DIR / "config.yaml")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load configuration: {e}")

@app.put("/api/config")
async def update_config(new_config: AppConfig):
    """Updates the application configuration."""
    config_path = ROOT_DIR / "config.yaml"
    try:
        # Load existing config to preserve any fields not exposed in the UI
        existing_config = load_config(config_path)

        # Update with new values
        update_data = new_config.dict(by_alias=True, exclude_unset=True)

        # Deep merge dictionaries
        def merge_configs(old, new):
            for k, v in new.items():
                if isinstance(v, dict) and k in old and isinstance(old[k], dict):
                    merge_configs(old[k], v)
                else:
                    # Do not update password/api_key if it's not provided
                    if k in ['password', 'api_key'] and not v:
                        continue
                    old[k] = v
            return old

        final_config = merge_configs(existing_config, update_data)

        with open(config_path, 'w') as f:
            yaml.dump(final_config, f, default_flow_style=False, sort_keys=False)

        return {"message": "Configuration updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update configuration: {e}")


# To run this application for development:
# uvicorn pingpoint.api:app --reload
