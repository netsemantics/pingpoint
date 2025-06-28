import paramiko
import logging
import subprocess
import xml.etree.ElementTree as ET
from typing import Optional, List
from .models import Fingerprint

class NmapScanner:
    """
    A scanner that uses Nmap to find devices on the network.
    """
    def __init__(self, subnets):
        self.subnets = subnets

    def scan(self):
        """
        Runs an Nmap scan across the configured subnets.

        Returns:
            A list of dictionaries, where each dictionary represents a host
            and contains 'ip', 'mac', and 'vendor' keys.
        """
        logging.info(f"Starting Nmap scan for subnets: {', '.join(self.subnets)}")
        results = []
        for subnet in self.subnets:
            try:
                # -sn: Ping Scan - disables port scan
                # --privileged: Assume user has privileges
                # -oX -: Output scan in XML format to stdout
                command = ["nmap", "-sn", "--privileged", "-oX", "-", subnet]
                process = subprocess.run(
                    command,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=300 # 5 minutes timeout
                )
                results.extend(self._parse_xml(process.stdout, subnet))
            except FileNotFoundError:
                logging.error("Nmap command not found. Please ensure Nmap is installed and in your system's PATH.")
                raise
            except subprocess.CalledProcessError as e:
                logging.error(f"Nmap scan for {subnet} failed: {e.stderr}")
                continue # Continue to the next subnet
            except Exception as e:
                logging.error(f"An unexpected error occurred during Nmap scan for {subnet}: {e}")
                continue

        logging.info(f"Nmap scan finished. Found {len(results)} hosts.")
        return results

    def _parse_xml(self, xml_output, subnet):
        """Parses the XML output from Nmap."""
        hosts = []
        root = ET.fromstring(xml_output)
        for host in root.findall('host'):
            status = host.find('status')
            if status is not None and status.get('state') == 'up':
                ip_addr = host.find('address[@addrtype="ipv4"]').get('addr')
                mac_addr_element = host.find('address[@addrtype="mac"]')
                mac_addr = mac_addr_element.get('addr') if mac_addr_element is not None else None
                vendor = mac_addr_element.get('vendor') if mac_addr_element is not None else None
                hosts.append({'ip': ip_addr, 'mac': mac_addr, 'vendor': vendor, 'subnet': subnet})
        return hosts

    def scan_for_fingerprint(self, ip_address: str) -> Optional[Fingerprint]:
        """
        Performs a detailed Nmap scan on a single IP to create a device fingerprint.

        Args:
            ip_address: The IP address of the device to scan.

        Returns:
            A Fingerprint object, or None if the scan fails or the host is down.
        """
        logging.info(f"Starting fingerprint scan for IP: {ip_address}")
        try:
            # -A: Enable OS detection, version detection, script scanning, and traceroute
            # -oX -: Output scan in XML format to stdout
            command = ["nmap", "-A", "-oX", "-", ip_address]
            process = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=600  # 10 minutes timeout for aggressive scan
            )
            return self._parse_fingerprint_xml(process.stdout)
        except FileNotFoundError:
            logging.error("Nmap command not found. Please ensure Nmap is installed and in your system's PATH.")
            raise
        except subprocess.CalledProcessError as e:
            logging.error(f"Nmap fingerprint scan for {ip_address} failed: {e.stderr}")
            return None
        except Exception as e:
            logging.error(f"An unexpected error occurred during Nmap fingerprint scan for {ip_address}: {e}")
            return None

    def _parse_fingerprint_xml(self, xml_output: str) -> Optional[Fingerprint]:
        """Parses the XML output from a detailed Nmap scan into a Fingerprint object."""
        try:
            root = ET.fromstring(xml_output)
            host = root.find('host')
            if host is None or host.find('status').get('state') != 'up':
                return None

            fingerprint = Fingerprint()

            # Get hostname
            hostname_elem = host.find('hostnames/hostname')
            if hostname_elem is not None:
                fingerprint.hostname = hostname_elem.get('name')

            # Get OS information
            os_match = host.find('os/osmatch')
            if os_match is not None:
                fingerprint.os_match = os_match.get('name')
                fingerprint.os_accuracy = os_match.get('accuracy')

            # Get open ports and services
            ports_elem = host.find('ports')
            if ports_elem is not None:
                for port in ports_elem.findall('port'):
                    if port.find('state').get('state') == 'open':
                        service = port.find('service')
                        port_info = {
                            'portid': port.get('portid'),
                            'protocol': port.get('protocol'),
                            'service_name': service.get('name') if service is not None else 'unknown',
                            'product': service.get('product') if service is not None else None,
                            'version': service.get('version') if service is not None else None,
                        }
                        fingerprint.ports.append(port_info)
            
            return fingerprint
        except ET.ParseError as e:
            logging.error(f"Failed to parse Nmap fingerprint XML: {e}")
            return None


import re

def is_valid_mac(mac):
    """Checks if a string is a valid MAC address."""
    return re.match(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$", mac)

def parse_edgemax_arp(arp_data):
    """Parses the output of 'show arp' from an EdgeMax router."""
    devices = []
    lines = arp_data.strip().split('\n')[1:]  # Skip header
    for line in lines:
        parts = line.split()
        if len(parts) >= 4:
            ip = parts[0]
            mac = parts[3] if parts[3] != '<incomplete>' else None
            if mac and is_valid_mac(mac):
                devices.append({'ip': ip, 'mac': mac, 'vendor': None}) # Vendor info not in arp table
    return devices

def parse_edgemax_leases(leases_data):
    """Parses the output of 'show dhcp leases' from an EdgeMax router."""
    devices = []
    lines = leases_data.strip().split('\n')[1:]  # Skip header
    for line in lines:
        parts = line.split()
        if len(parts) >= 5:
            ip = parts[0]
            mac = parts[1]
            subnet = parts[4]
            if is_valid_mac(mac):
                # The client name can be '?' or contain spaces.
                hostname = ' '.join(parts[5:]) if parts[5] != '?' else None
                
                devices.append({'ip': ip, 'mac': mac, 'hostname': hostname, 'subnet': subnet, 'vendor': None})
    return devices


def scan_network(config):
    """
    Performs a network scan using the primary (EdgeMax) or fallback (Nmap) method.

    Args:
        config: The application configuration dictionary.

    Returns:
        A list of discovered devices.
    """
    try:
        logging.info("Attempting primary scan method (EdgeMax SSH)...")
        em_config = config['edgemax']
        scanner = EdgeMaxScanner(
            host=em_config['host'],
            port=em_config['port'],
            username=em_config['username'],
            password=em_config['password']
        )
        return scanner.scan()

    except Exception as e:
        logging.warning(f"Primary scan method (EdgeMax) failed: {e}. Falling back to Nmap.")
        nmap_scanner = NmapScanner(subnets=config['subnets'])
        return nmap_scanner.scan()


class EdgeMaxScanner:
    """
    A scanner for Ubiquiti EdgeMax routers using SSH.
    """
    def scan(self):
        """
        Performs a scan using the EdgeMax router and returns the parsed results.
        """
        arp_data = self.get_arp_table()
        leases_data = self.get_dhcp_leases()
        self.close()

        # Combine and deduplicate results
        devices_by_mac = {}
        parsed_arp = parse_edgemax_arp(arp_data)
        parsed_leases = parse_edgemax_leases(leases_data)

        for device in parsed_arp + parsed_leases:
            if device['mac']:
                mac_upper = device['mac'].upper()
                if mac_upper not in devices_by_mac:
                    devices_by_mac[mac_upper] = device
        
        logging.info(f"EdgeMax scan successful. Found {len(devices_by_mac)} unique devices.")
        return list(devices_by_mac.values())
    def __init__(self, host, port, username, password):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.ssh_client = None

    def _connect(self):
        """Establishes an SSH connection."""
        if self.ssh_client is None:
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                logging.info(f"Connecting to EdgeMax router at {self.host}...")
                client.connect(self.host, port=self.port, username=self.username, password=self.password, timeout=10)
                self.ssh_client = client
            except Exception as e:
                logging.error(f"SSH connection failed: {e}")
                raise

    def _execute_command(self, command):
        """Executes a command on the remote device."""
        self._connect()
        # Use the vyatta-op-cmd-wrapper to execute operational commands.
        wrapper = "/opt/vyatta/bin/vyatta-op-cmd-wrapper"
        full_command = f"{wrapper} {command}"
        logging.info(f"Executing remote command: {full_command}")
        stdin, stdout, stderr = self.ssh_client.exec_command(full_command)
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            error_message = stderr.read().decode().strip()
            raise IOError(f"Command '{full_command}' failed with exit status {exit_status}: {error_message}")
        return stdout.read().decode().strip()

    def get_dhcp_leases(self):
        """Retrieves DHCP lease information."""
        logging.info("Fetching DHCP leases from EdgeMax router...")
        return self._execute_command("show dhcp leases")

    def get_arp_table(self):
        """Retrieves the ARP table."""
        logging.info("Fetching ARP table from EdgeMax router...")
        return self._execute_command("show arp")

    def close(self):
        """Closes the SSH connection."""
        if self.ssh_client:
            self.ssh_client.close()
            self.ssh_client = None
            logging.info("SSH connection closed.")

# Example of how to use it:
if __name__ == '__main__':
    import os
    from dotenv import load_dotenv

    logging.basicConfig(level=logging.INFO)

    # --- Test Nmap Scanner ---
    print("--- Testing Nmap Scanner ---")
    nmap_scanner = NmapScanner(subnets=["10.10.0.1/24"]) # Replace with a subnet on your network for a live test
    try:
        nmap_results = nmap_scanner.scan()
        print(f"Nmap found {len(nmap_results)} hosts.")
        for h in nmap_results:
            print(f"  - IP: {h['ip']}, MAC: {h['mac']}, Vendor: {h['vendor']}")
    except Exception as e:
        print(f"Nmap scan failed: {e}")


    # --- Test EdgeMax Scanner ---
    print("\n--- Testing EdgeMax Scanner ---")
    # This is for demonstration purposes. In the actual app, credentials will come from the config file.
    load_dotenv()
    EDGEMAX_HOST = os.getenv("EDGEMAX_HOST")
    EDGEMAX_PORT = int(os.getenv("EDGEMAX_PORT", 22))
    EDGEMAX_USER = os.getenv("EDGEMAX_USER")
    EDGEMAX_PASS = os.getenv("EDGEMAX_PASS")

    if not all([EDGEMAX_HOST, EDGEMAX_USER, EDGEMAX_PASS]):
        print("\nSkipping EdgeMax test. Please set EDGEMAX_HOST, EDGEMAX_USER, and EDGEMAX_PASS environment variables for testing.")
    else:
        edgemax_scanner = None
        try:
            edgemax_scanner = EdgeMaxScanner(EDGEMAX_HOST, EDGEMAX_PORT, EDGEMAX_USER, EDGEMAX_PASS)
            leases = edgemax_scanner.get_dhcp_leases()
            print("\n--- DHCP Leases ---")
            print(leases)

            arp_table = edgemax_scanner.get_arp_table()
            print("\n--- ARP Table ---")
            print(arp_table)
        except Exception as e:
            print(f"\nAn error occurred during EdgeMax scan: {e}")
        finally:
            if edgemax_scanner:
                edgemax_scanner.close()
