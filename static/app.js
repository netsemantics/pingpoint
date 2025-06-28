document.addEventListener('DOMContentLoaded', () => {
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    const htmlElement = document.documentElement;

    function applyTheme(theme) {
        htmlElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        if (theme === 'dark') {
            themeToggleBtn.innerHTML = '🌙';
        } else {
            themeToggleBtn.innerHTML = '☀️';
        }
    }

    themeToggleBtn.addEventListener('click', () => {
        const newTheme = localStorage.getItem('theme') === 'dark' ? 'light' : 'dark';
        applyTheme(newTheme);
    });

    // Load initial theme
    const initialTheme = localStorage.getItem('theme') || 'light';
    applyTheme(initialTheme);

    const deviceTableBody = document.getElementById('device-table-body');
    const timelineContainer = document.getElementById('timeline');
    const edgemaxBtn = document.getElementById('edgemax-scan-btn');
    const nmapBtn = document.getElementById('nmap-scan-btn');
    const scanStatus = document.getElementById('scan-status');
    let timeline = null; // To hold the timeline instance

    const triggerScan = async (scanType) => {
        scanStatus.textContent = `Initiating ${scanType} scan...`;
        edgemaxBtn.disabled = true;
        nmapBtn.disabled = true;
        try {
            const response = await fetch(`/api/scan/${scanType}`, { method: 'POST' });
            const result = await response.json();
            scanStatus.textContent = result.message;
        } catch (error) {
            scanStatus.textContent = `Failed to start ${scanType} scan.`;
            console.error(`Error triggering ${scanType} scan:`, error);
        } finally {
            // Re-enable buttons after a short delay
            setTimeout(() => {
                edgemaxBtn.disabled = false;
                nmapBtn.disabled = false;
            }, 2000);
        }
    };

    edgemaxBtn.addEventListener('click', () => triggerScan('edgemax'));
    nmapBtn.addEventListener('click', () => triggerScan('nmap'));


    const updateDeviceDetails = async (mac, friendlyName, notes, alertOnOffline) => {
        try {
            const response = await fetch(`/api/device/${mac}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    friendly_name: friendlyName,
                    notes: notes,
                    alert_on_offline: alertOnOffline
                })
            });
            if (!response.ok) {
                throw new Error('Failed to save details.');
            }
            alert('Device details saved successfully!');
        } catch (error) {
            console.error(`Failed to update device ${mac}:`, error);
            alert('Failed to save device details.');
        }
    };


    const fetchEvents = async () => {
        try {
            const response = await fetch('/api/events');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const events = await response.json();
            renderTimeline(events);
        } catch (error) {
            console.error("Failed to fetch events:", error);
        }
    };

    const renderTimeline = (events) => {
        const getClassName = (eventType) => {
            switch (eventType) {
                case 'device_joined': return 'new-device';
                case 'device_reconnected': return 'returning-device';
                case 'device_offline': return 'offline-device';
                case 'device_ip_change': return 'ip-change-device';
                default: return '';
            }
        };

        const items = new vis.DataSet(events.map((event, index) => ({
            id: index,
            content: ``, // Keep content empty for a smaller icon-like appearance
            start: event.timestamp,
            title: `<b>${event.message}</b><br>
                    Device: ${event.device.friendly_name || event.device.mac}<br>
                    IP: ${event.device.ip_addresses.join(', ')}<br>
                    Time: ${new Date(event.timestamp).toLocaleString()}`,
            className: getClassName(event.type),
            type: 'point' // Use points for a cleaner look
        })));

        const options = {
            stack: false,
            height: '200px',
            showMajorLabels: true,
            showMinorLabels: true,
            zoomable: true,
            zoomMin: 1000 * 60 * 5, // 5 minutes
            zoomMax: 1000 * 60 * 60 * 24 * 30, // 1 month
            tooltip: {
                followMouse: true,
                overflowMethod: 'flip'
            }
        };

        if (timeline) {
            timeline.setOptions(options);
            timeline.setItems(items);
        } else {
            timeline = new vis.Timeline(timelineContainer, items, options);
        }
        timeline.fit();
    };

    const fetchDevices = async () => {
        try {
            const response = await fetch('/api/devices');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const devices = await response.json();
            renderDeviceTable(devices);
        } catch (error) {
            console.error("Failed to fetch devices:", error);
            deviceTableBody.innerHTML = '<tr><td colspan="6">Failed to load devices.</td></tr>';
        }
    };

    const renderDeviceTable = (devices) => {
        deviceTableBody.innerHTML = ''; // Clear existing rows

        if (devices.length === 0) {
            deviceTableBody.innerHTML = '<tr><td colspan="9">No devices found.</td></tr>';
            return;
        }

        // Group devices by subnet
        const devicesBySubnet = devices.reduce((acc, device) => {
            const subnet = device.subnet || 'Unknown Subnet';
            if (!acc[subnet]) {
                acc[subnet] = [];
            }
            acc[subnet].push(device);
            return acc;
        }, {});

        for (const subnet in devicesBySubnet) {
            const subnetRow = document.createElement('tr');
            subnetRow.innerHTML = `<td colspan="10" style="background-color: #e9ecef; font-weight: bold;">${subnet}</td>`;
            deviceTableBody.appendChild(subnetRow);

            const subnetDevices = devicesBySubnet[subnet];
            // Sort devices within the subnet
            subnetDevices.sort((a, b) => {
                if (a.status === b.status) return 0;
                return a.status === 'online' ? -1 : 1;
            });

            subnetDevices.forEach(device => {
                const row = document.createElement('tr');
                row.dataset.mac = device.mac;
                const statusClass = device.status === 'online' ? 'status-online' : 'status-offline';
                
                row.innerHTML = `
                    <td><span class="status-dot ${statusClass}"></span> ${device.status}</td>
                    <td><input type="text" class="editable" data-field="friendly_name" value="${(device.friendly_name !== device.mac ? device.friendly_name : '') || ''}" placeholder="Add name..."></td>
                    <td>${device.hostname || 'N/A'}</td>
                    <td>${device.subnet || 'N/A'}</td>
                    <td>${device.mac}</td>
                    <td>${device.ip_addresses.join(', ') || 'N/A'}</td>
                    <td>${device.vendor || 'Unknown'}</td>
                    <td>${device.category || 'N/A'}</td>
                    <td><input type="text" class="editable" data-field="notes" value="${device.notes || ''}" placeholder="Add notes..."></td>
                    <td>
                        ${device.vulnerabilities ? 'Yes' : 'No'}
                    </td>
                    <td>${new Date(device.last_seen).toLocaleString()}</td>
                    <td><input type="checkbox" class="critical-checkbox" data-field="alert_on_offline" ${device.alert_on_offline ? 'checked' : ''}></td>
                    <td><button class="save-btn">Save</button></td>
                `;
                deviceTableBody.appendChild(row);
            });
        }

        // Add event listeners for the new save buttons
        document.querySelectorAll('.save-btn').forEach(button => {
            button.addEventListener('click', (e) => {
                const row = e.target.closest('tr');
                const mac = row.dataset.mac;
                const friendlyNameInput = row.querySelector('[data-field="friendly_name"]');
                const notesInput = row.querySelector('[data-field="notes"]');
                const criticalCheckbox = row.querySelector('[data-field="alert_on_offline"]');
                updateDeviceDetails(mac, friendlyNameInput.value, notesInput.value, criticalCheckbox.checked);
            });
        });


        // Add focus/blur listeners for expanding input fields
        document.querySelectorAll('#device-table-body input[type="text"]').forEach(input => {
            input.addEventListener('focus', (e) => {
                e.target.style.width = '220px';
            });
            input.addEventListener('blur', (e) => {
                e.target.style.width = '140px';
            });
        });
    };

    const fetchData = () => {
        fetchDevices();
        fetchEvents();
    };

    // Initial fetch
    fetchData();

    // Refresh data every 30 seconds
    setInterval(fetchData, 30000);
});
