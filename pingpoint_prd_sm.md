## Introduction

A home network monitoring service to continuously track devices across multiple IPv4 subnets, detect joins/leaves, and send alerts via Home Assistant. It runs as a long-running application (Node.js or Python) on a home server (e.g. Proxmox VM or container), uses EdgeMax router data as primary source with Nmap fallback, and offers a simple web UI without authentication.

---

## Goals

- **Discover devices** on configurable subnets (e.g. `10.10.0.0/16` and `10.30.0.0/16`) every 1–5 min.  
- **Maintain inventory** (MAC, IP, vendor, hostname, friendly name, status, first/last seen, alert settings).  
- **Notify** Home Assistant (via webhook) on:  
  - *Unknown device joins* (always).  
  - *Offline events* for user-tagged critical devices.  
- **Web UI** to view/edit devices and see an interactive events timeline.

---

## Architecture Overview

1. **Data Feed (v1 Mandatory)**
   - **EdgeMax SSH** every cycle (1–5 min) to `show dhcp leases` and `show arp`.  
   - **Fallback** to `nmap -sn` if SSH fails; parse XML for IP/MAC/vendor/hostname.  
2. **State Management**
   - In-memory store keyed by MAC; fields include IP(s), vendor (OUI), hostname, custom name, status, timestamps, and alert flags.  
   - Dump to JSON on shutdown and every 20 min; reload on startup.  
3. **Web API & Frontend**
   - REST endpoints: `/devices`, `/events`, `/events/timeline.json`.  
   - Simple HTML/JS dashboard showing:  
     - **Device Table**: status dot, name, IP, MAC, last seen, alert toggle.  
     - **Detail/Edit**: edit name, notes, critical-alert toggle.  
     - **Events Timeline**: using `vis-timeline` or `TimelineJS`; join/leave/IP-change icons, zoom/pan, date filter.  
   - Auto-refresh via AJAX at a configurable interval (e.g. 1 min).  
4. **Notifications**
   - On event, POST JSON to Home Assistant webhook URL.  
   - Payload example:
     ```json
     {
       "event":"device_joined",
       "device":"Unknown",
       "ip":"10.30.1.25",
       "mac":"AA:BB:CC:DD:EE:FF",
       "vendor":"Espressif",
       "time":"2025-06-22T15:00:00-04:00"
     }
     ```
   - HA handles delivery (e.g. WhatsApp mobile push).

---

## Functional Requirements

### 1. Scanning & Change Detection

- **Interval**: configurable 1–5 min; default 2 min.  
- **Primary**: SSH → EdgeRouter leases/ARP.  
- **Fallback**: Nmap ping scan (`nmap -sn`) across subnets.  
- **Detect**:
  - **New** (unknown MAC): add to inventory; generate “new device” event + alert.  
  - **Reconnect** (known offline → online): log event; optional alert if flagged.  
  - **Offline** (missed ≥ 2 scans): log event; if critical → alert.  
  - **IP Change** (same MAC, new IP): update record; log event.  
- **Debounce** to avoid flapping: require 2 consecutive misses for offline.

### 2. Inventory & Persistence

- **Fields**: MAC, current IP(s), vendor, hostname, friendly name, status, first/last seen timestamps, alert settings, notes.  
- **Storage**: JSON file (`devices.json`) persisted every 20 min and on significant updates.

### 3. Web UI

- **No auth**, accessible on LAN.  
- **Device List**: sortable/filterable table with status, name, IP, last seen, alert toggle.  
- **Edit Panel**: inline or modal for name/notes/alert settings.  
- **Events Tab**: timeline view of recent events with icons and tooltips.  
- **Config**: file-based (subnets, scan interval, SSH creds, HA webhook, timeline options).

### 4. EdgeMax Integration

- **SSH Credentials** stored securely (encrypted config).  
- **Commands**: `show dhcp leases`, `show arp`.  
- **Fallback**: Nmap scan if SSH fails; UI shows service-health warning.

---

## Technology & Deployment

- **Language**: Node.js (Express) or Python (FastAPI) with Paramiko for SSH.  
- **Dependencies**: Nmap installed on host or container (`--cap-add=NET_RAW` if Docker).  
- **Launch** via systemd, pm2, or Docker. Provide a Dockerfile installing runtime, Paramiko (if Python), and Nmap.  
- **Resource Use**: minimal—CPU peaks during scans, low memory (< 100 MB).

---

## MVP Checklist

1. **EdgeMax SSH feed** operational, fallback to Nmap.  
2. **Device inventory** with persistence (in-memory + JSON).  
3. **Web dashboard**:  
   - Real-time device table.  
   - Interactive events timeline.  
4. **HA notifications** on new device joins and critical device offline.  
5. **Config file**: subnets, scan schedule, EdgeRouter SSH creds, HA webhook, timeline settings.

---

## Future Considerations

- IPv6 support via router neighbor tables or mDNS.  
- Router integration for DHCP hostnames (e.g. UniFi API).  
- Extended notifications (email, MQTT).  
- Optional deeper port/vulnerability scans.  
- Mobile app or authenticated remote UI.

## Additional features to be added 

- Add NMAP scanning of devices that are identified via EdgeMax dhcp leases & arp
  - NMAP to capture vendor info and help to generate a device fingerprint
  - Only NMAP scan devices when they are new and join for the first time
  - Capture this data for retention
- Fingerprint to be used with Fingerbank API to get additional detail
  - Your Fingerbank account has been activated and is ready to be used.
  - Username: your_username
  - API key: your_fingerbank_api_key
  - Docs here - https://api.fingerbank.org/api_doc/2.html
  - Capture any vulnerabilities identified by fingerbank
- Add save button to UI to save manual edits to device info
  - Add field to the device info that indicates 'Critical Device' that should get immediate drop notifications
- improve the look and feel of the app
  - separate the info into sections by subnet
  - add a light theme
  - add a dark theme
  - add button to toggle between themes
  - expand the size of the editable fields on entry into the field
- update the timeline 
  - move to the top
  - improve the look by making the icons small with info only on hover over
  - color existing returning devices in green
  - color dropping devices in blue
  - color new devices in red
- add configuration page to the UI 
  - configuration to update the yaml file