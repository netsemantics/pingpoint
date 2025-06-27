# PRD: Home Network Device Monitoring Service

## Introduction

This document outlines the requirements for a home network monitoring service, inspired by the Fing app/Fingbox functionality and the **PokeBox** project. The goal is to continuously scan the local network (multiple subnets) to detect devices, track when they join or leave, and provide notifications and a simple web UI for management. The service will be built as a long-running Node.js application running on a home server (Proxmox environment) without requiring specialized hardware (like Fingbox). It will leverage **Nmap** for network scanning and integrate with existing infrastructure (UniFi/EdgeMax router and Home Assistant) to enhance device identification and user notifications. The solution should be simple, mostly in-memory, and easy to deploy in a home environment.

## Goals and Objectives

* **Continuous Network Scanning:** Automatically discover all devices on the home network (initially IPv4 only) by regularly scanning the defined subnets. Detect when new devices connect or known devices disconnect, similar to Fing’s real-time network monitoring.
* **Device Inventory & State Tracking:** Maintain an inventory of devices (IP, MAC, etc.) and track their online/offline status. Assign user-friendly names to devices (from Nmap scans when possible or manually by the user). Persist this information so that device identities and last-seen timestamps survive restarts.
* **Notifications on Changes:** Push timely notifications through Home Assistant when significant events occur, such as an **unknown/new device** joining the network or a critical device going offline. Home Assistant will then relay alerts (e.g. via WhatsApp) to the user’s phone.
* **User Interface (UI):** Provide a lightweight web-based UI (no authentication needed on the local LAN) to display the list of devices and their details. The UI should allow the user to label devices with custom names or notes and mark certain devices as important (to receive drop alerts).
* **Integration with Router/APIs:** Leverage available APIs or data from the UniFi/EdgeMax router to improve device discovery and identification (e.g. get DHCP lease info, ARP table, or device names from the router). This can complement Nmap scanning for accuracy.
* **Simplicity and Reliability:** The service should run primarily in memory for speed, periodically saving state to a local JSON file (every \~20 minutes) for persistence. It must be resilient to brief outages; losing up to 20 minutes of data in a crash or power loss is acceptable. The design will favor simplicity over heavy infrastructure – no complex databases or authentication are required in the initial version.

## System Overview

To meet the above goals, the system will consist of the following components and workflows:

* **Network Scanner Module:** Uses Nmap (or similar tools) to scan the target subnets on a schedule (e.g. every 1–5 minutes). It will identify active devices by their IP addresses, MAC addresses (when possible), and attempt to gather additional info such as vendor (from MAC OUI) or hostname. This module detects **changes**: new devices (appearing IP/MAC not seen before), **re-connections** (device seen again after being offline), and **disconnections** (previously active device not found). It may use ping/ARP scanning techniques for efficiency. Nmap’s ping-scan mode (`nmap -sn`) can quickly find hosts that are up without doing full port scans.

* **State Management:** In-memory data structures will maintain a list of known devices and their status. Each device entry may include fields like MAC, IP addresses (device could have multiple or change IP over time), last seen time, friendly name, type/vendor, and flags like “always alert on disconnect”. The service will log events (joins, drops, IP changes) to enable history viewing. Periodically (e.g. every 20 minutes) or upon significant changes, this state will be serialized to a JSON file on disk. This ensures a restart only loses the most recent few minutes of data. Using a simple JSON file meets the persistence requirement without the overhead of a full database. (We anticipate the number of devices is moderate, so in-memory and JSON are sufficient. In future, if needed, upgrading to SQLite or another lightweight DB is possible but not in scope for v1.)

* **Web-Based UI:** A built-in web server (likely an Express.js app in Node) will serve a dashboard on the local network (e.g. `http://servername:PORT`). The UI will present a **device table** listing all discovered devices with their details. The user can click on a device to edit its friendly name or add notes. The UI will highlight which devices are currently online vs. offline (e.g. green dot for active, gray for inactive). For usability, devices might be grouped by network (10.10.x.x vs 10.30.x.x) or by status. The interface should also provide an “Events” view, showing recent join/drop events with timestamps (similar to Fing’s timeline of network events). This helps users see when devices came online or went offline. *(Refer to Pi.Alert’s web interface for inspiration: it provides sections for connected devices, events, presence history, etc.)*

  &#x20;*Example UI from an open-source network scanner (Pi.Alert), showing a list of devices, their network details, and status. Our web UI will present similar information, allowing custom naming and highlighting new or offline devices.*

* **Notification Integration:** The service will integrate with Home Assistant for notifications. On detecting an event of interest (e.g. *New Device X connected* or *Critical Device Y went offline*), the service will send a notification to Home Assistant. This could be done via Home Assistant’s REST API or a webhook trigger. For example, an **HTTP POST** with JSON details (device name, IP, event type) can be sent to a pre-configured Home Assistant webhook URL. Home Assistant can then process the event (perhaps using an automation) and forward a message to the user’s phone (e.g. via WhatsApp integration or the Home Assistant mobile app). By using Home Assistant as the notification hub, we leverage its existing ecosystem (no need to implement WhatsApp API directly in our app). The notification content should be concise, e.g.: “**\[Network Alert] New device connected: MAC AA\:BB\:CC\:DD\:EE\:FF, IP 10.30.1.25**” or “**Device ‘Thermostat’ (IP 10.30.1.25) is offline**”. The system will ensure that **unknown devices** (not previously seen/approved) trigger an immediate alert as a potential intruder, and that **critical devices** dropping offline also raise an alert. (The user will define which devices are critical via the UI toggles or a config.)

* **Router and Network Integration:** To account for multiple subnets and firewall segmentation, the service will need to handle scanning both the **Main LAN (10.10.x.x)** and the **IoT LAN (10.30.x.x)**. The scanning component must either:
  a) Have network access to both subnets (e.g. the server running the service has interfaces on both networks, or VLAN trunks, so it can perform ARP scans on each), **or**
  b) Use route-based scanning from the main network to the IoT network. In route-based scanning, Nmap can send ping probes from 10.10 to devices in 10.30. Since the router allows initiated traffic from 10.10 → 10.30, these probes should reach IoT devices. However, pure ARP scans won’t work across subnets (ARP is non-routable), so Nmap will rely on ICMP echo and other techniques to detect hosts. One consideration: the EdgeMax firewall might block or not respond to certain scans. We may need to ensure ICMP echo requests (pings) are permitted from 10.10 to 10.30. If they are not by default, the user can add a firewall rule to allow ping and/or specific scanning traffic. The service documentation will note this requirement.
  Additionally, to get more device info (like MAC addresses on the IoT network, or hostnames), the service can query the router’s data. For example, if the router’s API or SSH interface can provide the DHCP lease table or ARP cache for the IoT subnet, the service could retrieve MAC addresses and hostnames for IPs it sees. This is an **optional enhancement**: initial implementation will primarily rely on Nmap’s results, but we plan hooks for router integration. The UniFi controller (if running) or EdgeOS API might allow querying connected clients. By leveraging these, the app can obtain device names that DHCP knows or ones the user labeled in the UniFi controller, and cross-reference MAC addresses (especially useful for IoT devices which the main network scanner might otherwise show as “unknown”).

* **Performance and Frequency:** Scans should run at a configurable interval. Initially, a scan every **1–5 minutes** is desired (the user can choose the exact frequency; e.g. 2 minutes as a default). This interval balances timeliness of detection with network load. Nmap ping scans on a home /24 subnet typically complete in a few seconds, so a scan every couple of minutes is feasible. We will avoid extremely frequent scans (e.g. every few seconds) to prevent excessive network chatter or router strain. The scanning should be done sequentially or in a staggered way if multiple subnets are scanned, to avoid saturating the system. Because the service runs continuously on a home server, it should be lightweight in resource usage: mainly idle between scans, a burst of CPU during scans, and minimal memory (just storing device list and UI data).

## Functional Requirements

### 1. Continuous Network Scanning

* **Supported Networks/Subnets:** The service will monitor two IPv4 subnets: `10.10.0.0/16` (main LAN, or specific sub-range as configured) and `10.30.0.0/16` (IoT LAN). (Exact ranges can be configurable; for example, if only 10.10.1.0/24 and 10.30.1.0/24 are used, we can limit scans to those ranges.) Initially, IPv6 is out of scope – the system will focus on IPv4 addresses only. (Future versions may add IPv6 support once we determine a strategy for discovering IPv6 devices, which can be more complex due to the vast address space and reliance on MDNS/ND instead of scanning an entire /64.)

* **Scan Method:** Use **Nmap** in ping-scan mode to discover active hosts. This equates to running a command like `nmap -sn 10.10.0.0/16 10.30.0.0/16` (or iterating subnets separately). Ping scan (`-sn`) will send ICMP echo requests, and possibly ARP requests for hosts on the same L2 network, to identify live hosts without doing a port scan. The scanner module should parse Nmap results to extract: IP address, MAC address (for local subnet results, Nmap will report the MAC and vendor when run on local LAN), and reverse DNS hostname (Nmap does DNS lookup by default on found hosts).

  * If Nmap doesn’t return MAC for IoT devices (because they are not on the same L2), the scanner can attempt additional steps for those: for each discovered IoT IP, query the router or use a fallback like an ARP request via router (if possible) to get the MAC. Alternatively, the service may issue a quick **ARP scan** on the IoT subnet by temporarily enabling an ARP request (if the server has an interface there). Another approach is to use **`arp-scan` utility** as Pi.Alert does, but that also requires L2 access. Since our main server might only be on 10.10, we lean on Nmap’s IP-based detection for IoT network.

* **Device Identification:** For each discovered device, the system will determine a **unique key** to track it. The MAC address is ideal as a unique identifier (it’s constant for the device’s network interface). Therefore, when available, MAC will be used to index devices in our inventory. If a device’s IP changes over time, we can still recognize it as the same device via MAC. In cases where a MAC isn’t immediately known (e.g. IoT subnet device, where we only got an IP from Nmap), the system can temporarily use the IP as an identifier but should update to the MAC once it’s learned (e.g. by querying the router’s ARP table or when the device communicates with the main network).

  * The system can use additional clues to identify devices: for example, **reverse DNS lookup** to get a hostname (Nmap’s output may include this). Many IoT or local devices register a DHCP hostname (like `thermostat.lan` or `Johns-iPhone.local`). Also, **MAC OUI lookup** can reveal the manufacturer (e.g. MAC starting with `FC:AB:90` might correspond to Apple, indicating an iPhone or Mac device). This can be shown in the UI and help guess device type. In the future, more active fingerprinting could be added (like Nmap OS detection or open port scanning), but for now we will keep scanning non-intrusive and lightweight.

* **Scan Frequency:** The default scan interval will be in the range of 1–5 minutes (configurable). The user suggested somewhere between 1 and 5 minutes, which we will make a setting (perhaps a default of 2 minutes). We’ll also implement a mechanism to **avoid overlapping scans** – i.e. if one scan cycle takes longer than the interval (unlikely for small networks, but possible on slower hardware or large subnets), the next cycle should not start until the previous completes to prevent piling up.

* **Handling Multiple Subnets:** The service will scan both subnets in one cycle. If the scanning server has direct interfaces on both, it can run two scans (one in each subnet using ARP/ping). If it only has access from one side (10.10), it will scan the 10.10 subnet via ARP/ping and the 10.30 subnet via routed ping. The configuration should allow specifying multiple target networks. We need to ensure the scanning methodology for the IoT network yields results: ICMP echo (ping) and possibly a TCP ping (Nmap by default may send an ACK or SYN to port 443 or 80 as a fallback when ICMP is not answered). The firewall might permit pings, but if not, we might consider allowing the router to respond or adjusting rules accordingly (the user can add firewall exceptions if needed).

* **Scanning Privileges:** Note that Nmap requires certain privileges for raw packet scans. When deploying the service, it will need the ability to run Nmap (the `nmap` binary must be installed on the system). If running in a Docker container, we may need to run the container with `--cap-add=NET_RAW` or in privileged mode so that Nmap can send ICMP/ARP packets. This will be documented in the deployment instructions. On a Proxmox host or VM, running the Node service as root (or with sufficient permissions) might be necessary for full network scanning capability.

* **Change Detection Logic:** After each scan, the system compares the results with the previous state to identify changes:

  * **New Device:** An IP/MAC appears that was not present in the last state (and not in the known devices list). This triggers a “new device” event. The device is added to the inventory (with a default name like “Unknown device” if it can’t be identified). An alert is generated for Home Assistant if the device is truly unknown (not just an IP change of a known MAC).
  * **Reconnection:** A device that was known but offline in the last state is now seen online again. This could be a normal event (e.g. a phone reconnecting to Wi-Fi). We may log it in the event history (“Device X back online at 14:32”) but by default not send a notification unless perhaps the user wants to know (this could be a configurable notification for specific devices, e.g. notify when a family member’s phone connects as presence detection). For initial scope, we’ll likely not notify on every reconnection of common devices to avoid spamming, unless configured.
  * **Disconnection:** A device that was previously online is missing from the latest scan. To avoid flapping (temporary misses), we might consider marking a device “offline” only after it misses a couple of consecutive scans or after a slightly longer interval (e.g. if not seen for 2 scan cycles or 5 minutes). Once confirmed, we log a “device went offline” event. If that device is marked as critical/always-on by the user, we also send a notification. If it’s a regular device, we typically wouldn’t notify every offline (since phones going to sleep or powering off is routine), but the event is still recorded.
  * **IP Change:** If a known device’s IP address changes (but MAC is same), the system should update the device entry with the new IP. This is common if DHCP assigns a new IP. We’ll treat it as an update, not as a new device. Possibly log an event like “Device X IP changed from 10.10.1.5 to 10.10.1.7”.
  * These detected changes correspond to those found in similar tools; for instance, Pi.Alert explicitly tracks new connections, disconnections, IP changes, and alerts for always-connected device down.

### 2. Device Inventory and Data Management

* **Device Records:** Each device discovered will have a record containing:

  * **MAC Address** (unique ID if available)
  * **IP Address(es)** (current IP, and possibly a history or list of known IPs if it changed or if device has multiple interfaces)
  * **Vendor/OUI** (derived from MAC prefix if possible, e.g. “Apple, Inc.”)
  * **Detected Hostname** (if any, from DNS or mDNS)
  * **Custom Name (Friendly Name):** A user-defined name for easy recognition (e.g. “John’s iPhone” or “Living Room TV”). The system will auto-populate this with any detected name from Nmap or the router initially (for example, if reverse DNS gives `john-phone.lan`, we might set friendly name to “john-phone” as a starting point). The user can change it via the UI. This name should be stored persistently (in the JSON state file) so it remains associated with that device’s MAC even if the IP changes or the device is offline for a while.
  * **Status:** Online/Offline flag. Possibly with a timestamp of last seen online and last seen offline.
  * **First Seen:** Timestamp when this device was first ever observed (useful for audit or curiosity – “this device first joined on Jan 5, 2024”).
  * **Last Seen:** Timestamp of the most recent scan in which the device was seen (for offline devices, this tells how long they have been offline).
  * **Alerts Settings:** A flag or setting if the user wants notifications for this device going offline or coming online. For example, a checkbox “Notify if offline” to designate critical devices (security cameras, servers, etc.), and possibly “Notify on join” (maybe for new/unknown devices this is globally always on, but for known devices the user might toggle if they care). We anticipate by default:

    * Unknown devices: always notify on first seen (security measure).
    * Known important devices: user can mark to notify on offline.
    * Other known devices: no notify on offline (to avoid noise).
  * **Network/Subnet:** Which network this device is on (10.10 or 10.30), in case we want to filter or segment in the UI.
  * **Additional Info:** We can include a free-text notes field the user can edit (e.g. “This is the smart thermostat in living room”).

* **Data Storage:** As specified, we will implement an in-memory data store (likely just a JavaScript object or Map of devices keyed by MAC). Updates from scans will modify this in-memory structure. For persistence, the service will write the data to a JSON file on disk at a regular interval (e.g. every 20 minutes) and on graceful shutdown. The JSON will likely contain an array or object of devices, each with the fields above, plus maybe a separate log of recent events.

  * The choice of JSON text file makes it easy for a user to inspect or manually edit if needed, and avoids requiring a separate DB service. The file (e.g. `devices.json`) will reside on the local filesystem of the server (or in a mounted volume if in a container).
  * On startup, the service will read this file to pre-populate the known devices list. If the file is missing or corrupted, the service will start with an empty list (all devices will be treated as new on first scan, and a new file will be created).
  * The state save interval (20 minutes by default) is a balance between data safety and reducing unnecessary disk I/O. Losing 20 minutes of data is acceptable; the main impact would be missing some event history if the server crashes. The core knowledge (like friendly names) won’t be lost unless the crash happened right after a user edited something and before save – this is an acceptable risk given the simplicity goal. Advanced approach could involve writing out immediately on critical changes (like adding a new device or renaming), but that can be optional to keep things simple.
  * **Potential DB upgrade:** If in the future we need more robust storage or to store a long history of events, we might move to SQLite (which Pi.Alert uses for example) or another embedded DB. But for now, JSON is sufficient since the number of devices (perhaps <100) and events is small.

* **Event Log:** The service will maintain a recent event log (in-memory and optionally persisted or at least persist last X events). Events include: device X joined, device Y left, device Z IP changed, etc., with timestamps. This can be shown in the UI (“Events” page). We might store the last N events (like 100) in memory, and also append to a log file if persistence of all events is desired. However, a full audit log is optional – the primary need is to notify on important events and show some history in the UI for context. To keep storage minimal, we might not log every routine reconnection unless flagged for monitoring.

### 3. Web UI Requirements

* **Accessibility:** The web interface will run on a configurable port (default 8080) and be accessible without authentication from the local network. The user explicitly does not want to require login for the UI, since it’s within a protected home network. We will include a disclaimer that the UI is open to anyone on the LAN – but since it only shows network info and allows labeling, this is likely fine. If needed, the user can restrict access by host firewall or by not exposing the port outside the LAN/VPN.
* **UI Framework:** We can implement the UI using a simple Node.js web framework (Express for backend API + plain HTML/JS or a minimal frontend framework for interactivity). The UI doesn’t have to be fancy, but it should be clear and easy to use. We will use a responsive design (possibly Bootstrap or similar) to make it accessible via desktop or mobile browser. Fing’s mobile app is an inspiration, but our UI will be browser-based.
* **Device List View:** The main page will list all devices being monitored. For each device, display columns such as:

  * Status indicator (online/offline, e.g. a colored dot).
  * Device Name (friendly name if set, otherwise something like vendor or generic “Unknown \[MAC]”).
  * IP address (if online, show current IP; if offline, maybe show “Last known IP”).
  * MAC address (and possibly vendor, could be shown as tooltip or smaller text).
  * Last Seen time (or “Currently Online since \[time]”).
  * If a device is offline, show “Last seen 20m ago” or “Last seen on \[date/time]”.
  * Perhaps an icon or label for the network (like “Main” vs “IoT”), or segment the list by network with sub-headings.
  * Option to mark a device as favorite or critical (maybe a star icon or a bell icon for “notify on drop”).
    This table should be sortable or filterable, if possible (e.g. sort by status to see all online devices at top).
* **Device Detail / Edit:** The user can select a device (e.g. clicking its row) to open a detail panel or separate page where they can:

  * Edit the friendly name.
  * See extended info (all known IPs, first seen date, etc.).
  * Mark/unmark it for notifications on offline/online.
  * Possibly manually classify the device type (e.g. “Phone”, “Laptop”, “Camera”) for their reference.
  * Save changes (which update the in-memory state and will be persisted on next save cycle).
  * If the UI is more advanced, we might have inline editing (e.g. click on name in table to edit directly).
* **Add/Remove Devices:** Generally, devices are auto-added when discovered. We won’t allow the user to “add” a device manually that hasn’t been seen (except maybe to pre-set a label for a device they *expect* to join, though that’s an edge case and not needed for now). Removal: possibly allow deleting a device from the list (e.g. if it was a one-time guest device and the user doesn’t care to keep it in the list). Removing would forget its name and history. We should confirm if this is needed; it might be nice to clean out stale devices after a long time. For v1, a manual delete function could be provided, or we just keep everything and maybe allow filtering out “not seen in 6 months” etc. This is a minor detail and can be added if time permits.
* **Events View:** A section of the UI will list recent events in chronological order (new device joins, disconnects, alerts sent, etc.). Each entry might include timestamp, device name (or MAC/IP if unknown), and description of event. This helps to visually see what happened on the network and when. For example:

  * “08:32 – New device joined: **Amazon Echo** at 10.30.5.123 (MAC XX\:XX\:XX)”
  * “08:33 – **John’s iPhone** reconnected (10.10.1.5)”
  * “08:50 – **Thermostat** (10.30.5.50) went offline – ALERT sent”
  * etc.
    This is similar to Fing’s timeline view and Pi.Alert’s events.
* **UI Refresh:** The data on the UI should update regularly to reflect current state. We can either use periodic AJAX refresh (e.g. fetch device list JSON every 30 seconds) or use WebSocket if we want instant updates. Simpler is periodic refresh or a “Refresh” button. Since scan interval is a few minutes, a refresh every 1 minute is fine. We can implement the device list as a client-side dynamic table pulling from a REST endpoint (the service can expose `/devices` returning JSON of devices, and `/events` for events).
* **No Auth & Security:** Without login, we should ensure that any state-changing operations (like renaming a device) are only accessible from within the LAN. We assume a trusted environment. (If this was a product, we’d consider at least optional auth, but since user explicitly says none needed, we comply.) We might log in the service if a new device was named or critical-flag changed, just for audit, but that’s internal.
* **Home Assistant Configuration UI:** We might provide a small UI section to configure the Home Assistant connection (like URL and an authentication token or webhook ID). This could also be a simple config file the user edits. For ease, a config JSON or YAML loaded at startup might define scanning settings and HA webhook URL, etc., rather than a UI form. Keeping config out of UI is okay for v1 (the user of this system is technical and can edit a config file with their Home Assistant webhook URL, for instance).

### 4. Notifications & Integration Details

* **Event Filtering for Notifications:** The service should decide which events generate a push to Home Assistant. As discussed:

  * **Unknown Device Joins:** Always notify immediately. These are devices that have not been seen before (not in our known list) – could be an intruder or a new device in the house. The notification will include whatever info we have (MAC, IP, maybe vendor). The user can then decide if it’s expected (and later label it in the UI). This feature is akin to an “intruder alert” or new device discovery that Fingbox/Pi.Alert provide.
  * **Known Device Online:** Usually no notification (unless explicitly marked for it). An exception might be if the user wants to know when a particular device comes online (for example, a child’s phone connecting could indicate they came home). This can be handled by allowing a per-device “notify on connect” flag.
  * **Known Device Offline:** Only notify if the device is tagged as critical (always-on). For example, if a security camera or a server goes offline, that’s important. If a normal device like a phone disconnects, we don’t alert. (If the user wants, they could mark even a phone for alerts, but default off.)
  * **Device IP change:** No immediate user notification (this is an internal event; it doesn’t usually require user action). It will be reflected in the UI.
  * **Multiple Notifications Consideration:** If a device is flapping (e.g. goes on/off repeatedly due to network issues), the system should avoid spamming. Perhaps have a cooldown – e.g. once a device offline alert is sent, wait a few minutes before sending another for the same device going up/down. Also possibly aggregate if many new devices join at once (but in a home network that’s rare).
* **Home Assistant Webhook/API:** The simplest integration is via webhook. The user can set up an **automation trigger** in Home Assistant that listens for a webhook (Home Assistant allows defining a webhook ID and then any HTTP POST to `http://<HA_IP>:8123/api/webhook/<ID>` will trigger it). Our service will be configured with the URL of Home Assistant (likely the HA runs on the same LAN) and the webhook ID or an authentication token. Two methods:

  * *Option A: Webhook (no auth required in payload if using pre-shared secret URL).*
  * *Option B: Home Assistant REST API (requires an HA Long-Lived Access Token in header for authentication, then we can call the `events` API or `services` to create a notification directly).*
    Webhook is straightforward: we define, for example, a webhook called `network_monitor` in Home Assistant. In our app config, we set the HA base URL and that webhook. When an event happens, the app sends an HTTP POST with JSON like `{"event": "device_joined", "device": "Unknown", "ip": "10.30.1.25", "mac": "AA:BB:CC:...","vendor":"Espressif", "time":"2025-06-21T20:15:00Z"}`. Home Assistant receives it and can then use its templating to compose a WhatsApp message or a persistent notification. This decouples the logic – our app doesn’t need to know how to send WhatsApp; it just hands off to HA.
    If using the direct API approach, our app might call Home Assistant’s notification service (e.g. POST to `/api/services/notify/notify_whatsapp` with a message). But that requires storing an HA token in our config and perhaps is less flexible. Likely the webhook/automation route is best for user’s customization. We will document how to set this up.
* **Example Notification Flow:** If a new device with MAC `00:11:22:33:44:55` joins:

  * Our service creates an event internally and also sends an HTTP POST to HA. Home Assistant, upon receiving, triggers an automation that maybe calls the notify platform (WhatsApp). The user’s phone then gets: “Network Alert: New device joined - MAC 00:11:22:33:44:55, IP 10.30.1.25 (Vendor: Espressif)”. The user can then decide if that’s, say, a new IoT gadget they installed or something suspicious.
  * If the living room camera (which user marked as critical) goes offline, after e.g. 2 missed pings (say in \~3 minutes), our service sends a webhook: `{event: "device_offline", device: "Living Room Camera", ..., duration_offline: "3 minutes"}`. HA then sends: “Alert: Device ‘Living Room Camera’ is offline.”
  * Possibly, when it comes back, we might not notify (unless user wanted an “online” alert).
* **Home Assistant ←→ App Status:** It might be useful (future idea) to expose our device status to Home Assistant as a sensor. For instance, some people might want to use Home Assistant’s dashboard to view devices. This could be done via MQTT or HA’s API (creating entities for devices). For now, this is out of scope, but we note that as an extension, the app could publish device presence to Home Assistant (like create a `device_tracker` entity for each device). However, that can get complicated and is not required; the user primarily asked for notifications and a separate web UI.
* **E-mail or Other Notifications:** While not explicitly requested (user specifically wants integration with HA and WhatsApp), the system could also have a built-in email notification feature as an alternative. PokeBox, for example, likely could send emails or other push notifications when things change. Pi.Alert focuses on email alerts by default. We will focus on Home Assistant integration, but design it such that adding an SMTP email notifier or other channels later is possible. Perhaps have a notification interface where we can plug in different backends (for now just the HA webhook backend).

### 5. Integration with UniFi/EdgeMax Router

*(This section outlines how we might use router integration to enhance the system, though the exact implementation depends on router model and available APIs. It’s somewhat optional for initial version but important to consider.)*

* **Purpose:** The router (and Wi-Fi access points) often already know about connected devices – e.g., DHCP leases, ARP tables, and in the case of UniFi, a controller that aggregates info (device hostname, which AP it’s on, signal strength, etc.). Tapping into this can improve our monitoring. Specifically, it can:

  * Provide **device naming**: If the user has named devices in the UniFi Controller or if the DHCP hostname is descriptive, we can use that to label devices automatically.
  * Provide **MAC to IP mapping** quickly: Instead of scanning, we could retrieve the DHCP lease list (which has MAC/IP for all clients, including ones that might not respond to ping). This can help catch devices that are quiet on the network but still connected.
  * **Online/Offline status**: The UniFi controller often knows when a device disconnects (especially Wi-Fi clients). However, relying solely on it would duplicate Fing functionality. We will use it as supplementary data.

* **EdgeOS/EdgeRouter:** If the network uses an EdgeRouter (EdgeMAX), there isn’t a full REST API by default like UniFi, but there is a way to execute CLI commands via SSH or read system files. For example, EdgeOS stores DHCP leases in `/var/lib/dhcpd/leases` or similar, and ARP cache can be fetched with `arp -an`. We could have the app SSH into the router (if credentials are provided) and parse these. That’s a bit advanced, and security-wise storing router credentials is sensitive. We might skip this in v1, unless the user is comfortable setting up a read-only API. There is a community EdgeOS API library which could be explored if needed.

* **UniFi Controller:** If the user’s router is actually a UniFi Security Gateway or Dream Machine, and they have a UniFi Network Controller running, then we can leverage UniFi’s API. The UniFi controller has an API endpoint for “list clients” which returns JSON of all known clients (with fields like MAC, hostname, IP, uptime, etc.). Using this requires the controller’s address and an API key or login. If the user is running Home Assistant, they might already have UniFi integration which is doing similar things. As a simpler approach, we might skip direct UniFi integration at first and rely on scanning, but keep this as a potential enhancement.

  * Perhaps for the IoT network, the UniFi AP knows all connected WiFi clients (MAC, IP). It might be easier to just scan though given complexity.

* **Scope decision:** For the initial implementation, the network scanning should be sufficient to detect devices. Router integration is a *nice-to-have* to enrich the data:

  * **DHCP hostnames:** We can implement a simple read of `/etc/hosts` or similar if the router populates DHCP hostnames in DNS (the scanning server could do a reverse DNS lookup for each IP; if the router is the DNS server, it might resolve `10.10.1.100` to `Camera.lan`). Nmap does reverse DNS by default, so we might already get these names without special calls.
  * **MAC vendor DB:** We will include a local OUI database or use a library to map MAC to vendor string. This is straightforward (there are Node libraries or we can embed a list).
  * Given the user runs a UniFi/Edge, they might also have the **Unifi Protect** (camera system) or others; but that’s beyond our scope. We only consider network.

* **Firewall Considerations:** The user noted that their firewall blocks uninitiated traffic from IoT (10.30) to main (10.10). Our app will initiate from main side, so it should be fine. But, if in the future we have the app trying to directly query devices (like open a connection to a device on IoT, say to check a port), that might be seen as initiated from main so allowed. We have to be careful not to inadvertently allow IoT devices a path to attack main network through our service. For example, if we run a web UI on the main network but bind it to all interfaces, an IoT device could try to connect to that UI (since from IoT to main it’s blocked unless main initiated). However, since main doesn’t initiate a connection to IoT devices’ browsers, IoT devices can’t reach the UI unless we explicitly allow or the firewall incorrectly identifies it. We will ensure the web UI listens only on the main network interface (or 0.0.0.0 which includes main, but firewall will block IoT inbound anyway). So likely not an issue.

### 6. Future Expansion (Out of Scope for v1 but considered)

* **IPv6 Support:** In the future, if IPv6 becomes needed (if the LAN uses it), we’d need a different scanning approach (e.g., sniffing neighbor announcements or querying router neighbor tables) as scanning an IPv6 /64 by brute force is impractical. We would possibly integrate with router (which knows connected IPv6 addresses via DHCPv6 or NDP) or use MDNS/LLMNR to find IPv6 hosts. This will require research and likely separate implementation parallel to IPv4 scanning.
* **Security/Vulnerability Scanning:** The user mentioned possibly adding security scans later. This could mean:

  * **Port Scanning of devices:** e.g. regularly scan each device’s open ports and detect new open ports or services. This would help detect if a device opens an unexpected service (which could indicate compromise). It’s essentially using Nmap in a deeper mode (which Fingbox does have some intrusion detection aspects, and Pi.Alert’s author mentions IDS/IPS as a next step). This could produce a lot of data and false alarms, so it’s not in initial scope.
  * **Vulnerability DB integration:** possibly checking device OS or firmware versions if known, etc. This is complex.
  * **Intrusion detection:** integrating with SNMP or Suricata, etc. Also complex.
  * We note that our architecture (with scheduled scanning and a web UI) could be extended to incorporate these. Perhaps as separate modules or optional scans. For instance, a future version might allow the user to press “Scan ports on this device” from the UI to investigate it, or schedule a weekly port scan for known devices. But to keep things simple, v1 will not include detailed port scanning or IDS.
* **Device Blocking/Response:** Fingbox can block new devices via ARP spoofing as a defense. We will **not** implement any blocking or active network defense in this app (at least not initially). It would require manipulating ARP or router settings to quarantine a device. If needed in future, since the user has an EdgeMax router, one could imagine the app making an API/SSH call to add the device to a blocked list (e.g. add a firewall rule or put it in a VLAN). But that’s beyond our current scope and better handled by network equipment or manual user action once alerted.
* **Improved UI features:** Future improvements might include graphs (like how many devices online over time, ala Pi.Alert’s “concurrent devices” graph), or a calendar view of presence, etc. For now, our UI will be basic and focused on real-time status and recent events.

## Non-Functional Requirements

* **Deployment Environment:** The service will run on a home server (likely Debian or similar Linux under Proxmox, or in a container). It must be easy to install. We can provide a Docker container for convenience (ensuring it’s privileged enough for Nmap). Alternatively, a Node.js script that can be launched via pm2 or systemd. Minimal external dependencies: Nmap must be installed, Node.js runtime.
* **Platform:** Node.js (v14+ or v18+). The choice is because the user is familiar with Node and we want to integrate with Home Assistant (which is Python-based, but integration is via HTTP so language is flexible). Using Node also allows using its web frameworks for the UI and perhaps existing libraries for Nmap or network scanning. (Python was used in PokeBox and Pi.Alert, but we’ll do Node as desired).
* **Reliability:** The service should run 24/7 without user intervention. It should handle exceptions (e.g. if Nmap fails or times out, the app catches that and tries again next cycle). Memory footprint should remain stable (avoid memory leaks). We should also ensure that a scanning error on one cycle doesn’t stop the whole service (catch errors and continue).
* **Volume of Data:** Home networks typically have tens of devices. Our data structures and JSON will be small (tens of KB). Even logging events over a year might reach a few thousand entries – still manageable in memory. Performance is not a big concern; the biggest load might be Nmap scanning large subnets (10.10/16 has 65k addresses, which could take some time if done naively). We may restrict scanning to actual used ranges (maybe user knows it’s only .1.x or .10.x used). Alternatively, use a technique to discover network segments (e.g. check DHCP scope). This can be configured. If scanning a /16 is too slow, we adjust strategy (maybe use multiple smaller Nmap calls or use `-PS` host discovery with specific ports).
* **Usability:** The user interface should be clean and not overly complicated. We will document how to operate the system, how to configure which subnets to scan, how to configure the HA webhook, etc., likely in a README. The UI should present important info at a glance (current devices, alerts). The user can rely on Home Assistant notifications for the urgent info and use the web UI for deeper inspection or configuration.

## Comparison to PokeBox (Reference)

*PokeBox was a similar project that inspired this solution. For context, PokeBox was a dockerized app (Python-based) that continuously scanned a network and sent notifications on changes. It required creating an admin user for its web interface (indicating a login-protected UI), and likely stored data in a database inside the container (volume `pokedata:/var/dbdata`). PokeBox leveraged Nmap as well (the Dockerfile installed nmap). Functionally, it scanned the Wi-Fi network, detected new devices and presumably could send alerts (possibly via email or other configured channels). Our service will achieve the same core functionality but tailored to our needs (multiple subnets, Home Assistant integration, no login UI, etc.). The UI for PokeBox presumably listed devices and allowed some management; since it required an admin user, it might have been built on a web framework like Django. We do not require multi-user support or authentication, simplifying our implementation.*

*(Additionally, Fing’s Fingbox device performs similar 24/7 monitoring – scanning for new devices, alerting on offline devices, and even active blocking. This PRD essentially outlines a self-hosted alternative to Fingbox: using software to accomplish network scanning and alerting on a home network using existing hardware. Community discussions indicate that an open-source solution is often “Nmap behind a nice interface” – which is exactly what we aim to build.)*

## Open Questions & Considerations

* **Naming of Devices:** Aside from using reverse DNS and OUI, do we want to implement any other device name detection (NetBIOS name for Windows devices, MDNS for Apple/IoT devices, etc.)? This could improve initial naming (e.g. showing “John-iPhone.local” instead of Unknown). It might require additional network queries (MDNS multicast) which could be done periodically. This is not required but would polish the experience.
* **Marking Critical Devices:** How will the user mark a device as “always notify on disconnect”? In the UI, perhaps a toggle or a star icon. We need to clarify the UI design for this. Additionally, should we assume all devices on the main LAN (10.10) are “protected” and thus important? The user mentioned “I want to protect devices on 10.10.x.x - but really the IOT devices as well.” This suggests all devices are of interest, but likely the main LAN devices might be more personal (thus security-critical) while IoT might be more likely to get compromised (thus we also want to monitor them). We will treat both networks equally in scanning and allow marking any device from either network as critical for alerts.
* **Scan Interval Configuration:** We assume 1–5 minutes is fine. Does the user want to be able to change this easily (via UI or config)? Possibly a config file setting is enough. If in UI, could be a drop-down for scan frequency. For now, we can set it in a config file or env variable and not complicate the UI.
* **Handling Large Subnet (Performance):** If the user truly scans a /16, Nmap might take longer. In testing, `nmap -sn` on a /16 can still be fairly quick if hosts respond to ping, but if many addresses are unused, Nmap might mark them down quickly. However, if the network doesn’t respond to ping for unused IPs, Nmap will attempt and wait for timeouts. This can slow the scan. We might need to adjust Nmap options (e.g. `-T4` aggressive timing, or limit to common alive host range). Possibly ask the user if their subnets are fully used or mostly empty – maybe limit to /24s or use multiple smaller range scans. Alternatively, use ARP-scan on local /16 which might be faster on L2 (but IoT we can’t ARP-scan directly). We might chunk the /16 into /24s and scan sequentially to manage time. This needs some consideration or testing.
* **Proxmox Environment:** The app will run on a Proxmox home server. Likely as a VM or LXC container. If a container, ensure it has raw socket access (in LXC, “unprivileged” containers may have restrictions). We might have to advise running it in a privileged container or as a VM for full functionality.
* **User Roles and Auth:** Not needed now, but if in future the user wanted remote access to the UI (from outside home), we’d then consider adding authentication. For now, we won’t. We trust the home LAN users.
* **Mobile App Integration:** Fing has a mobile app. Our solution is web-only. If the user wanted mobile notifications, we rely on Home Assistant. If they wanted a direct mobile app or push, that’s not planned. The web UI should be mobile-friendly though.
* **Testing:** We should test with a variety of devices (phones, smart TVs, etc.) to ensure they are discovered. Some IoT devices might not respond to ping to save power. In such cases, our scanner might miss them even if they are connected. This is where router integration or examining Pi-hole queries helps (Pi.Alert’s approach of checking Pi-hole DNS queries or DHCP leases catches devices that don’t ping). If the user runs Pi-hole, we could also integrate that, but that’s an edge case. For initial release, we document that some devices may not show as “online” if they don’t respond to pings. However, most devices do respond to some form of probe (or we could try a TCP SYN to port 443 which many devices will answer with a RST if closed, marking them as up). Nmap does some of that by default in ping-scan mode (it uses multiple probe types). We might adjust Nmap options if needed to catch stubborn devices.
* **Dependencies:** Nmap installation is a must. On Debian/Ubuntu, we will ask user to `apt-get install nmap` if not using Docker. If Docker, base image should include nmap. Node modules: possibly use a library like `node-nmap` or simply call Nmap via child\_process and parse XML/grepable output. Using XML output from Nmap might be easiest to parse reliably. Alternatively, we can call `arp-scan` for local nets. Implementation detail to decide in design phase.

By addressing the above requirements, the resulting application will provide a comprehensive yet lightweight solution for home network monitoring – keeping track of devices in both trusted and IoT segments, similar to commercial solutions like Fingbox but fully under the user’s control. The system will continuously watch for changes and inform the user through their existing Home Assistant notification setup, while also allowing the user to view and manage device information via a web interface. This PRD serves as a blueprint for development, and any clarifications needed can be discussed (per the Open Questions) to ensure the implementation meets the user’s needs effectively.

## References

* Fingbox concept and features
* PokeBox project overview (continuous network scan & notifications)
* Pi.Alert open-source tool (device scan methods and monitoring features)
* Community discussion on using Nmap for home network monitoring
* Nmap usage for ping scans (host discovery)


### **Addendum #1 – Scope & Architecture Updates**

---

#### 1  Integration with UniFi EdgeMax Router (now **mandatory** in v1)

| Topic                    | Updated Requirement                                                                                                                                                                  |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Data-source priority** | 1. **EdgeMax SSH** session to pull live ARP + DHCP tables; 2. fallback/verification with Nmap only when the router feed is unavailable or a MAC/IP still looks “unknown.”            |
| **Commands / files**     | • `show dhcp leases` (dynamic) and `show dhcp server leases state all` (includes static-maps) for full lease list ([community.ui.com][1])  <br>• `show arp` for L2⇄L3 mapping.       |
| **Polling cadence**      | SSH scrape every scan cycle (1-5 min) because it is lightweight compared with running Nmap across /16 ranges.                                                                        |
| **Auth method**          | Password-auth or key-based SSH; store creds in an **encrypted** config file (e.g., `edgerouter.yaml`).  Use *read-only* user if possible.                                            |
| **Failure handling**     | If SSH login or parsing fails, log the error, fall back to Nmap for that cycle, and raise a **service-health** warning in the UI.                                                    |
| **Implementation hint**  | In Python, wrap SSH calls with **Paramiko**; parse CLI output into dicts.  Provide an abstraction layer so the rest of the app consumes a single “device feed” regardless of source. |
| **Security note**        | Document that the EdgeRouter user must be limited to `show` commands; do **not** store a full-privilege password in plain text.                                                      |

---

#### 2  UI Enhancement – Interactive Event Timeline

| Topic             | Updated Requirement                                                                                                                                                                                                            |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Control**       | Use an open-source timeline widget; baseline candidates: <br>• **Knight Lab TimelineJS** (simple, JSON-driven) ([timeline.knightlab.com][2]) <br>• **vis-timeline** from vis.js (groupable, zoom & pan) ([visjs.github.io][3]) |
| **Placement**     | New **“Events” tab** showing a horizontal timeline of join/leave/IP-change events.  Each item: icon (🟢 join / 🔴 drop), device name, timestamp tooltip, click → jumps to device detail.                                       |
| **Data format**   | Service exposes `/events/timeline.json` in the format required by the chosen library (KnightLab JSON or vis-timeline item list).                                                                                               |
| **User controls** | Zoom, pan, and a date-range filter (e.g., last 24 h / 7 d).  For very active networks, group events by device row when using vis-timeline.                                                                                     |
| **Styling**       | Match main dashboard theme for consistency.  Keep colours accessible (dark-mode support inherited from PRD spec).                                                                                                              |

---

#### 3  Backend Language Choice

| Decision Point                   | Clarification                                                                                                                                                                                                                                                                                     |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Python vs Node**               | The backend **may switch to Python** for quicker SSH parsing and to align with many network-monitoring OSS projects (Pi.Alert, etc.).  Either **Flask** or **FastAPI** gives us: <br>• async tasks (scan scheduler) <br>• lightweight REST endpoints for UI <br>• easy integration with Paramiko. |
| **Impact on existing PRD items** | *No functional changes*—all endpoints (`/devices`, `/events`, timeline feed) remain.  Front-end stays in plain HTML/JS; only the API layer changes.                                                                                                                                               |
| **Nmap invocation**              | Keep shelling out to `nmap` (`subprocess.run`) as fallback so code-path parity is preserved between Python and Node versions.                                                                                                                                                                     |
| **Deployment**                   | Provide a Dockerfile that installs Python 3.11, Paramiko, FastAPI/uvicorn, and Nmap.  Container still needs `--cap-add=NET_RAW` for fallback scans.                                                                                                                                               |

---

#### 4  Revised **MVP** Checklist (first release)

1. **EdgeRouter feed operational** → device inventory populates via SSH every ≤ 5 min.
2. **Nmap fallback** works automatically if router feed fails.
3. **Web Dashboard** shows:

   * real-time device table (existing spec)
   * **Events timeline** with zoom/pan.
4. **Notifications** still delivered through Home Assistant webhook on *new device* or *critical device offline*.
5. **Persistence**: in-memory + periodic JSON dump (20 min).
6. **Config file** holds: subnet list, scan interval, EdgeRouter SSH creds, Home Assistant webhook URL, timeline view options.

---

*This Addendum is to be read as authoritative for v1 planning; all items marked “mandatory” override the corresponding optional design notes in the original PRD.*

[1]: https://community.ui.com/questions/ERLite-3-How-do-i-get-a-list-of-all-active-DHCP-leases-including-static/53fa2e1c-a570-4a60-82ef-fd1ef4395429?utm_source=chatgpt.com "How do i get a list of all active DHCP leases, including static?"
[2]: https://timeline.knightlab.com/?utm_source=chatgpt.com "Timeline JS - Knight Lab"
[3]: https://visjs.github.io/vis-timeline/docs/timeline/?utm_source=chatgpt.com "timeline - vis.js - A dynamic, browser based visualization library."
