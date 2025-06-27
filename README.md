# PingPoint Network Monitor

PingPoint is a home network monitoring service that continuously tracks devices across multiple subnets, detects when they join or leave the network, and sends alerts via Home Assistant.

## Features

- **Device Discovery**: Scans configured subnets to find active devices.
- **Primary/Fallback Scanning**: Uses SSH to an EdgeMax router for primary data, with an Nmap-based fallback.
- **Device Inventory**: Maintains a persistent JSON-based inventory of all known devices.
- **Event Logging**: Tracks device events like joins, leaves, and IP changes.
- **Web Dashboard**: A simple, no-auth web UI to view devices and an interactive event timeline.
- **Home Assistant Notifications**: Sends webhook notifications for new devices and for critical devices going offline.

## Getting Started

### Prerequisites

- [Docker](https://www.docker.com/get-started)
- An EdgeMax router (optional, for primary scanning method)
- Nmap (installed on the host or within the Docker container)
- A Home Assistant instance with a configured webhook (for notifications)

### Configuration

1.  **Copy the example configuration:**
    ```bash
    cp config.yaml.example config.yaml
    ```

2.  **Edit `config.yaml`:**
    - `subnets`: A list of network ranges to scan (e.g., `192.168.1.0/24`).
    - `scan_interval`: How often to scan the network, in minutes.
    - `edgemax`: Credentials for your EdgeMax router. If you don't have one, the application will fall back to using Nmap.
    - `home_assistant`: The `webhook_url` for your Home Assistant integration.

### Deployment with Docker

1.  **Build the Docker image:**
    ```bash
    docker build -t pingpoint .
    ```

2.  **Run the Docker container:**
    ```bash
    docker run -d \
      --name pingpoint \
      -p 8000:8000 \
      -v $(pwd)/config.yaml:/app/config.yaml \
      -v $(pwd)/devices.json:/app/devices.json \
      --restart unless-stopped \
      pingpoint
    ```
    - This command mounts your local `config.yaml` and `devices.json` into the container, ensuring your configuration and device list are persisted across container restarts.

### Accessing the Dashboard

Once the container is running, you can access the web dashboard at `http://<your-server-ip>:8000`.

## Development

To run the application locally for development:

1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run the API server:**
    The application's scanning loop and the web server are not yet integrated to run in a single command. To run the web server for UI development:
    ```bash
    uvicorn pingpoint.api:app --reload
    ```
    The dashboard will be available at `http://127.0.0.1:8000`.
