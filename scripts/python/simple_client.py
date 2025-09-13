#!/usr/bin/env python3
"""Simple Aria client"""

import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimpleClient:
    """Simple client class"""
    
    def __init__(self, hostname):
        self.hostname = hostname
        self.connected = False
    
    def connect(self):
        """Connect to service"""
        logger.info(f"Connecting to {self.hostname}")
        self.connected = True
        return True
    
    def get_status(self):
        """Get status"""
        if not self.connected:
            self.connect()
        return {"status": "healthy", "hostname": self.hostname}
    
    def generate_report(self):
        """Generate report"""
        status = self.get_status()
        report = {
            "timestamp": "2024-01-01T00:00:00Z",
            "data": status
        }
        return report


def main():
    """Main function"""
    client = SimpleClient("test.local")
    report = client.generate_report()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()