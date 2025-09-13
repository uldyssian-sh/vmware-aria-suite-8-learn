#!/usr/bin/env python3
"""
VMware Aria Operations API Integration Library
Simple Python SDK for Aria Operations
"""

import json
import logging
import requests
from datetime import datetime
from typing import Dict, List, Optional

# Disable SSL warnings for lab environments
requests.packages.urllib3.disable_warnings()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AriaOperationsAPI:
    """Simple Aria Operations API client"""
    
    def __init__(self, hostname: str, username: str, password: str):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.base_url = f"https://{hostname}"
        self.auth_token = None
        
    def authenticate(self) -> bool:
        """Authenticate with Aria Operations"""
        auth_url = f"{self.base_url}/suite-api/api/auth/token/acquire"
        auth_data = {
            "username": self.username,
            "password": self.password
        }
        
        try:
            response = requests.post(
                auth_url, 
                json=auth_data,
                verify=False,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            self.auth_token = result.get('token')
            
            if self.auth_token:
                logger.info("Authentication successful")
                return True
            else:
                logger.error("Authentication failed - no token received")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    def get_resources(self, resource_kind: Optional[str] = None) -> List[Dict]:
        """Retrieve resources from Aria Operations"""
        if not self.auth_token:
            if not self.authenticate():
                return []
        
        resources_url = f"{self.base_url}/suite-api/api/resources"
        headers = {
            'Authorization': f'vRealizeOpsToken {self.auth_token}',
            'Content-Type': 'application/json'
        }
        
        params = {}
        if resource_kind:
            params['resourceKind'] = resource_kind
            
        try:
            response = requests.get(
                resources_url,
                headers=headers,
                params=params,
                verify=False,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            resources = data.get('resourceList', [])
            
            logger.info(f"Retrieved {len(resources)} resources")
            return resources
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to retrieve resources: {e}")
            return []
    
    def get_alerts(self) -> List[Dict]:
        """Retrieve active alerts"""
        if not self.auth_token:
            if not self.authenticate():
                return []
        
        alerts_url = f"{self.base_url}/suite-api/api/alerts"
        headers = {
            'Authorization': f'vRealizeOpsToken {self.auth_token}',
            'Content-Type': 'application/json'
        }
        
        params = {'activeOnly': 'true'}
        
        try:
            response = requests.get(
                alerts_url,
                headers=headers,
                params=params,
                verify=False,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            alerts = data.get('alerts', [])
            
            logger.info(f"Retrieved {len(alerts)} alerts")
            return alerts
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to retrieve alerts: {e}")
            return []
    
    def generate_health_report(self) -> Dict:
        """Generate a simple health report"""
        logger.info("Generating health report...")
        
        # Get resources
        resources = self.get_resources("VirtualMachine")
        
        # Get alerts
        alerts = self.get_alerts()
        
        # Generate report
        report = {
            "generated_at": datetime.now().isoformat(),
            "total_resources": len(resources),
            "active_alerts": len(alerts),
            "status": "healthy" if len(alerts) == 0 else "warning"
        }
        
        logger.info("Health report generated successfully")
        return report
    
    def export_report(self, report: Dict, filename: str) -> bool:
        """Export report to JSON file"""
        try:
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2)
            
            logger.info(f"Report exported to: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export report: {e}")
            return False


def main():
    """Example usage"""
    client = AriaOperationsAPI(
        hostname="aria-ops.lab.local",
        username="admin",
        password="VMware123!"
    )
    
    try:
        # Generate health report
        report = client.generate_health_report()
        
        # Export report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"aria_health_report_{timestamp}.json"
        client.export_report(report, filename)
        
        print(f"Health report generated: {filename}")
        
    except Exception as e:
        logger.error(f"Error: {e}")


if __name__ == "__main__":
    main()