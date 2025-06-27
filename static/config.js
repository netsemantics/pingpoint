document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('config-form');
    const notification = document.getElementById('notification');

    const showNotification = (message, isError = false) => {
        notification.textContent = message;
        notification.className = 'notification'; // Reset classes
        notification.classList.add(isError ? 'error' : 'success');
        notification.style.display = 'block';
        setTimeout(() => {
            notification.style.display = 'none';
        }, 5000);
    };

    // Fetch current configuration and populate the form
    const loadConfig = async () => {
        try {
            const response = await fetch('/api/config');
            if (!response.ok) {
                throw new Error('Failed to load configuration.');
            }
            const config = await response.json();

            // Populate general settings
            document.getElementById('scan-interval').value = config.scan_interval || 2;
            document.getElementById('subnets').value = (config.subnets || []).join(', ');

            // Populate EdgeMax settings
            if (config.edgemax) {
                document.getElementById('edgemax-host').value = config.edgemax.host || '';
                document.getElementById('edgemax-port').value = config.edgemax.port || 22;
                document.getElementById('edgemax-user').value = config.edgemax.username || '';
            }

            // Populate Home Assistant settings
            if (config.home_assistant) {
                document.getElementById('ha-webhook-url').value = config.home_assistant.webhook_url || '';
            }

        } catch (error) {
            showNotification(error.message, true);
        }
    };

    // Handle form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(form);
        const data = {};

        // Basic fields
        data.scan_interval = parseInt(formData.get('scan_interval'), 10);
        data.subnets = formData.get('subnets').split(',').map(s => s.trim()).filter(s => s);

        // Nested structures
        data.edgemax = {
            host: formData.get('edgemax_host'),
            port: parseInt(formData.get('edgemax_port'), 10),
            username: formData.get('edgemax_user'),
            password: formData.get('edgemax_password')
        };
        data.home_assistant = {
            webhook_url: formData.get('ha_webhook_url')
        };
        data.fingerbank = {
            api_key: formData.get('fb_api_key')
        };

        // Filter out empty password/api_key fields so they are not sent
        if (!data.edgemax.password) {
            delete data.edgemax.password;
        }
        if (!data.fingerbank.api_key) {
            delete data.fingerbank.api_key;
        }

        try {
            const response = await fetch('/api/config', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to save configuration.');
            }

            showNotification('Configuration saved successfully!');
        } catch (error) {
            showNotification(error.message, true);
        }
    });

    // Initial load
    loadConfig();
});
