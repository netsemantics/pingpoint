import unittest
import os
from pingpoint.inventory import Inventory, Device

class TestInventory(unittest.TestCase):

    def setUp(self):
        """Set up a clean inventory for each test."""
        self.test_file = "test_inventory_devices.json"
        # Ensure no old test file is lying around
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        self.inventory = Inventory(persistence_file=self.test_file)

    def tearDown(self):
        """Clean up the test file after each test."""
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def test_new_device_join(self):
        """Test that a new device is correctly added to the inventory."""
        scan_result = [{'mac': 'AA:BB:CC:00:11:22', 'ip': '192.168.1.100', 'vendor': 'TestVendor'}]
        self.inventory.update_from_scan(scan_result)
        
        self.assertEqual(len(self.inventory.all_devices()), 1)
        device = self.inventory.get_device('AA:BB:CC:00:11:22')
        self.assertIsNotNone(device)
        self.assertEqual(device.status, 'online')
        self.assertEqual(device.vendor, 'TestVendor')
        
        self.assertEqual(len(self.inventory.events), 1)
        self.assertEqual(self.inventory.events[0]['type'], 'device_joined')

    def test_device_goes_offline_and_reconnects(self):
        """Test the full offline -> online cycle."""
        mac = 'AA:BB:CC:00:11:22'
        scan1 = [{'mac': mac, 'ip': '192.168.1.100'}]
        
        # 1. Device joins
        self.inventory.update_from_scan(scan1)
        device = self.inventory.get_device(mac)
        self.assertEqual(device.status, 'online')

        # 2. Device is missing once (should still be online)
        self.inventory.update_from_scan([])
        self.assertEqual(device.status, 'online')
        self.assertEqual(self.inventory._offline_counters.get(mac), 1)

        # 3. Device is missing twice (should be marked offline)
        self.inventory.update_from_scan([])
        self.assertEqual(device.status, 'offline')
        self.assertIsNone(self.inventory._offline_counters.get(mac)) # Counter should be cleared
        self.assertEqual(self.inventory.events[0]['type'], 'device_offline')

        # 4. Device reconnects
        self.inventory.update_from_scan(scan1)
        self.assertEqual(device.status, 'online')
        self.assertEqual(self.inventory.events[0]['type'], 'device_reconnected')

    def test_ip_address_change(self):
        """Test that a new IP for a known device is recorded."""
        mac = 'AA:BB:CC:00:11:22'
        scan1 = [{'mac': mac, 'ip': '192.168.1.100'}]
        self.inventory.update_from_scan(scan1)
        
        device = self.inventory.get_device(mac)
        self.assertIn('192.168.1.100', device.ip_addresses)
        
        scan2 = [{'mac': mac, 'ip': '192.168.1.101'}]
        self.inventory.update_from_scan(scan2)
        
        self.assertIn('192.168.1.101', device.ip_addresses)
        self.assertEqual(len(device.ip_addresses), 2)
        self.assertEqual(self.inventory.events[0]['type'], 'ip_change')

    def test_persistence(self):
        """Test that the inventory is saved and loaded correctly."""
        scan_result = [{'mac': 'AA:BB:CC:00:11:22', 'ip': '192.168.1.100'}]
        self.inventory.update_from_scan(scan_result)
        self.inventory.save_to_disk()

        # Create a new inventory instance to load from the file
        new_inventory = Inventory(persistence_file=self.test_file)
        self.assertEqual(len(new_inventory.all_devices()), 1)
        device = new_inventory.get_device('AA:BB:CC:00:11:22')
        self.assertIsNotNone(device)
        self.assertEqual(device.status, 'online')


if __name__ == '__main__':
    unittest.main()
