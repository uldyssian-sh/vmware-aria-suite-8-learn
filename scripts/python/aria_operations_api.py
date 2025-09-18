#!/usr/bin/env python3
"""
Simple Aria Operations client
"""

import json
import logging
import os
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AriaOperationsAPI:
    """Simple Aria Operations API client"""
    
    def __init__(self, hostname, username, password):
        self.hostname = hostname
        self.username = username
        # Don't store password in memory after authentication
        self.auth_token = None
        self._authenticate_with_password(password)
        
    def _authenticate_with_password(self, password):
        """Authenticate with password (called once during init)"""
        logger.info("Authenticating...")
        # Use secure token generation in production
        self.auth_token = "mock-token"  # TODO: Replace with actual authentication
        return True
        
    def authenticate(self):
        """Re-authenticate if token expired"""
        if not self.auth_token:
            logger.error("Authentication token missing. Please create new instance.")
            return False
        return True
    
    def get_resources(self, resource_kind=None):
        """Retrieve resources"""
        if not self.auth_token:
            if not self.authenticate():
                return []
        
        logger.info("Getting resources...")
        return [{"id": "vm-001", "name": "test-vm"}]
    
    def get_alerts(self):
        """Retrieve active alerts"""
        if not self.auth_token:
            if not self.authenticate():
                return []
        
        logger.info("Getting alerts...")
        return []
    
    def generate_health_report(self):
        """Generate a simple health report"""
        logger.info("Generating health report...")
        
        resources = self.get_resources("VirtualMachine")
        alerts = self.get_alerts()
        
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_resources": len(resources),
            "active_alerts": len(alerts),
            "status": "healthy"
        }
        
        return report
    
    def export_report(self, report, filename):
        """Export report to JSON file"""
        # Validate filename to prevent path traversal
        import os.path
        if os.path.isabs(filename) or '..' in filename:
            logger.error("Invalid filename: absolute paths and '..' not allowed")
            return False
            
        # Ensure filename is in current directory
        safe_filename = os.path.basename(filename)
        
        try:
            with open(safe_filename, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Report exported to: {safe_filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to export report: {e}")
            return False


def main():
    """Example usage"""
    hostname = os.getenv('ARIA_HOSTNAME', 'aria-ops.lab.local')
    username = os.getenv('ARIA_USERNAME', 'admin')
    password = os.getenv('ARIA_PASSWORD')
    
    if not password:
        raise ValueError("ARIA_PASSWORD environment variable must be set")
    
    client = AriaOperationsAPI(hostname, username, password)
    
    report = client.generate_health_report()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"report_{timestamp}.json"
    client.export_report(report, filename)
    
    print(f"Report generated: {filename}")


if __name__ == "__main__":
    main()