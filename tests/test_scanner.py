import unittest
from unittest.mock import patch, MagicMock
from pingpoint.scanner import parse_edgemax_arp, parse_edgemax_leases, NmapScanner, scan_network

# Mock data for EdgeMax
MOCK_ARP_DATA = """IP address       HW type     HW address           Flags Mask            Iface
192.168.1.1      0x1         00:11:22:33:44:55    C                     eth1
192.168.1.10     0x1         AA:BB:CC:DD:EE:FF    C                     eth1
192.168.1.12     0x1         <incomplete>         C                     eth1
"""

MOCK_LEASES_DATA = """IP address      Hardware Address   Lease expiration     Pool       Client Name
----------      ----------------   ------------------   ----       -----------
192.168.1.10    aa:bb:cc:dd:ee:ff  2025/06/23 04:14:37  LAN_POOL   test-device
192.168.1.20    11:22:33:44:55:66  2025/06/23 04:15:00  LAN_POOL   another-device
"""

# Mock data for Nmap
MOCK_NMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE nmaprun>
<nmaprun scanner="nmap" args="nmap -sn -oX - 192.168.1.1/24" start="1719173717" startstr="Sat Jun 22 16:15:17 2025" version="7.92" xmloutputversion="1.05">
<host starttime="1719173717" endtime="1719173717"><status state="up" reason="arp-response" reason_ttl="0"/>
<address addr="192.168.1.1" addrtype="ipv4"/>
<address addr="00:11:22:33:44:55" addrtype="mac" vendor="Ubiquiti"/>
</host>
<host starttime="1719173718" endtime="1719173718"><status state="up" reason="arp-response" reason_ttl="0"/>
<address addr="192.168.1.10" addrtype="ipv4"/>
<address addr="AA:BB:CC:DD:EE:FF" addrtype="mac" vendor="Apple"/>
</host>
</nmaprun>
"""

MOCK_CONFIG = {
    'edgemax': {
        'host': '192.168.1.1',
        'port': 22,
        'username': 'test',
        'password': 'password'
    },
    'subnets': ['192.168.1.0/24']
}

class TestScanner(unittest.TestCase):

    def test_parse_edgemax_arp(self):
        devices = parse_edgemax_arp(MOCK_ARP_DATA)
        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0]['ip'], '192.168.1.1')
        self.assertEqual(devices[0]['mac'], '00:11:22:33:44:55')
        self.assertEqual(devices[1]['ip'], '192.168.1.10')
        self.assertEqual(devices[1]['mac'], 'AA:BB:CC:DD:EE:FF')

    def test_parse_edgemax_leases(self):
        devices = parse_edgemax_leases(MOCK_LEASES_DATA)
        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0]['ip'], '192.168.1.10')
        self.assertEqual(devices[0]['mac'], 'aa:bb:cc:dd:ee:ff')
        self.assertEqual(devices[1]['ip'], '192.168.1.20')
        self.assertEqual(devices[1]['mac'], '11:22:33:44:55:66')

    @patch('pingpoint.scanner.subprocess.run')
    def test_nmap_scanner(self, mock_run):
        mock_run.return_value.stdout = MOCK_NMAP_XML
        scanner = NmapScanner(subnets=['192.168.1.1/24'])
        results = scanner.scan()
        self.assertEqual(len(results), 2)
        self.assertEqual(results[1]['ip'], '192.168.1.10')
        self.assertEqual(results[1]['mac'], 'AA:BB:CC:DD:EE:FF')
        self.assertEqual(results[1]['vendor'], 'Apple')

    @patch('pingpoint.scanner.EdgeMaxScanner')
    def test_scan_network_primary_success(self, MockEdgeMaxScanner):
        # Mock the EdgeMaxScanner instance and its scan method
        mock_scanner_instance = MockEdgeMaxScanner.return_value
        mock_scanner_instance.scan.return_value = [
            {'ip': '192.168.1.10', 'mac': 'aa:bb:cc:dd:ee:ff', 'hostname': 'test-device', 'subnet': 'LAN_POOL', 'vendor': None},
            {'ip': '192.168.1.20', 'mac': '11:22:33:44:55:66', 'hostname': 'another-device', 'subnet': 'LAN_POOL', 'vendor': None}
        ]

        results = scan_network(MOCK_CONFIG)
        
        # Should have 2 unique devices from the combined mock data
        self.assertEqual(len(results), 2)
        macs = {d['mac'] for d in results}
        self.assertIn('aa:bb:cc:dd:ee:ff', macs)
        self.assertIn('11:22:33:44:55:66', macs)

    @patch('pingpoint.scanner.EdgeMaxScanner')
    @patch('pingpoint.scanner.NmapScanner')
    def test_scan_network_fallback_to_nmap(self, MockNmapScanner, MockEdgeMaxScanner):
        # Make the EdgeMaxScanner fail
        MockEdgeMaxScanner.side_effect = Exception("SSH Connection Failed")

        # Mock the NmapScanner instance and its scan method
        mock_nmap_instance = MockNmapScanner.return_value
        mock_nmap_instance.scan.return_value = [{'ip': '192.168.1.10', 'mac': 'AA:BB:CC:DD:EE:FF', 'vendor': 'Apple'}]

        results = scan_network(MOCK_CONFIG)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['mac'], 'AA:BB:CC:DD:EE:FF')
        MockNmapScanner.assert_called_once_with(subnets=MOCK_CONFIG['subnets'])


if __name__ == '__main__':
    unittest.main()
