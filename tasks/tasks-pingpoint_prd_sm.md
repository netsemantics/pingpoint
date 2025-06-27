## Relevant Files

- `pingpoint/main.py` – Main application entry point, orchestrates scanning and API startup.
- `pingpoint/config.py` – Manages loading and validation of application settings from a file.
- `pingpoint/scanner.py` – Implements the network scanning logic for both EdgeMax (SSH) and Nmap.
- `pingpoint/inventory.py` – Manages the device inventory, state changes, and persistence to JSON.
- `pingpoint/api.py` – Defines the FastAPI endpoints for the web UI.
- `pingpoint/notifications.py` – Handles sending alerts to Home Assistant.
- `static/` – Directory for frontend assets (HTML, CSS, JS).
- `tests/test_scanner.py` – Unit tests for the scanning module.
- `tests/test_inventory.py` – Unit tests for the inventory management logic.
- `devices.json` – The persisted device inventory file.
- `config.yaml` – Configuration file for the application.

### Notes

- The application will be structured as a Python package named `pingpoint`.
- Tests will be placed in a separate `tests/` directory and run with `pytest`.

## Tasks

- [x] 1.0 Setup Core Project Structure and Configuration Management
  - [x] 1.1 Create the initial directory structure (`pingpoint/`, `tests/`, `static/`).
  - [x] 1.2 Implement `config.py` to load settings (subnets, credentials, webhook URL) from `config.yaml`.
  - [x] 1.3 Create `main.py` to initialize the application, load config, and set up logging.
  - [x] 2.0 Implement Network Scanning Engine (EdgeMax & Nmap)
  - [x] 2.1 Implement the EdgeMax SSH client in `scanner.py` using Paramiko to run `show dhcp leases` and `show arp`.
  - [x] 2.2 Implement the Nmap fallback in `scanner.py` to parse `nmap -sn` XML output.
  - [x] 2.3 Create a unified `scan()` function that tries the primary method and uses the fallback on failure.
  - [x] 2.4 Add unit tests in `tests/test_scanner.py` with mock data for both SSH and Nmap outputs.
- [x] 3.0 Develop Device Inventory and State Persistence
  - [x] 3.1 Create the `Device` data class/dataclass in `inventory.py`.
  - [x] 3.2 Implement the `Inventory` class to manage the collection of devices.
  - [x] 3.3 Implement logic to detect new, reconnected, offline, and IP-changed devices based on scan results.
  - [x] 3.4 Implement JSON serialization/deserialization for the inventory, with periodic saving.
  - [x] 3.5 Add unit tests in `tests/test_inventory.py` for all state transition logic.
- [x] 4.0 Build Web Application (API & Frontend)
  - [x] 4.1 Set up a basic FastAPI application in `api.py`.
  - [x] 4.2 Create the `/api/devices` endpoint to return the current device list.
  - [x] 4.3 Create the `/api/events` endpoint to return a log of recent events.
  - [x] 4.4 Develop the `index.html` file in `static/` with a device table and an element for the timeline.
  - [x] 4.5 Write JavaScript to fetch data from the API endpoints and dynamically update the UI.
  - [x] 4.6 Integrate a timeline library (e.g., `vis-timeline`) to visualize events.
- [x] 5.0 Implement Notification Service and Finalize Deployment
  - [x] 5.1 Implement the `send_notification()` function in `notifications.py` to POST to the Home Assistant webhook.
  - [x] 5.2 Integrate the notification call into the inventory module to trigger on relevant events.
  - [x] 5.3 Create a `Dockerfile` to package the application with its dependencies (Python, Nmap).
  - [x] 5.4 Write a `README.md` with instructions for configuration and deployment.
- [x] 6.0 Enhance Device Scanning with Nmap and Fingerprinting
  - [x] 6.1 Add Nmap scan for new devices identified by EdgeMax to capture vendor info and create a device fingerprint.
  - [x] 6.2 Store the device fingerprint data.
  - [x] 6.3 Integrate with Fingerbank API to enrich device details using the collected fingerprint.
  - [x] 6.4 Capture and store any vulnerability information returned by Fingerbank.
- [x] 7.0 Improve UI for Device Management
  - [x] 7.1 Add a "Save" button to the UI to persist manual edits to device information.
  - [x] 7.2 Add a "Critical Device" field/toggle to the device details to enable immediate offline notifications.
- [ ] 8.0 Enhance UI/UX and Theming
  - [x] 8.1 Reorganize the device list to group devices by subnet.
  - [x] 8.2 Implement a light theme for the application.
  - [x] 8.3 Implement a dark theme for the application.
  - [x] 8.4 Add a theme-toggle button to switch between light and dark modes.
  - [ ] 8.5 Implement dynamic resizing for editable fields to expand on focus.
- [ ] 9.0 Refine Timeline Display
  - [ ] 9.1 Relocate the timeline to the top of the dashboard.
  - [ ] 9.2 Redesign timeline events to use smaller icons with details appearing on hover.
  - [ ] 9.3 Implement color-coding for timeline events: green for returning devices, blue for offline devices, and red for new devices.
- [ ] 10.0 Add Configuration Management UI
  - [ ] 10.1 Create a new configuration page in the UI.
  - [ ] 10.2 Implement functionality on the configuration page to read and write to the `config.yaml` file.
