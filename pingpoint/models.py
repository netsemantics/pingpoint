from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List

@dataclass
class Fingerprint:
    """Stores device fingerprint information from an Nmap scan."""
    os_match: Optional[str] = None
    os_accuracy: Optional[str] = None
    ports: List[dict] = field(default_factory=list)
    hostname: Optional[str] = None

@dataclass
class Device:
    """Represents a single device on the network."""
    mac: str
    ip_addresses: List[str] = field(default_factory=list)
    vendor: Optional[str] = None
    hostname: Optional[str] = None
    friendly_name: Optional[str] = None
    subnet: Optional[str] = None
    status: str = "offline"
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    alert_on_offline: bool = False
    notes: Optional[str] = None
    fingerprint: Optional[Fingerprint] = None
    vulnerabilities: List[dict] = field(default_factory=list)

    def __post_init__(self):
        if self.friendly_name is None:
            self.friendly_name = self.hostname or self.mac

    def to_dict(self):
        """Converts the device object to a dictionary for JSON serialization."""
        data = asdict(self)
        data['first_seen'] = self.first_seen.isoformat()
        data['last_seen'] = self.last_seen.isoformat()
        return data

    @classmethod
    def from_dict(cls, data):
        """Creates a Device object from a dictionary."""
        data['first_seen'] = datetime.fromisoformat(data['first_seen'])
        data['last_seen'] = datetime.fromisoformat(data['last_seen'])
        if data.get('fingerprint'):
            data['fingerprint'] = Fingerprint(**data['fingerprint'])
        if 'vulnerabilities' not in data:
            data['vulnerabilities'] = []
        return cls(**data)
