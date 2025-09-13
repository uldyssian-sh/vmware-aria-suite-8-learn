#!/usr/bin/env python3
"""
VMware Aria Operations API Integration Library
Comprehensive Python SDK for Aria Operations automation and monitoring
"""

import json
import logging
import requests
import urllib3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from urllib.parse import urljoin
import concurrent.futures
import time

# Disable SSL warnings for lab environments
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

@dataclass
class AriaCredentials:
    """Credentials for Aria Operations authentication"""
    hostname: str
    username: str
    password: str
    port: int = 443
    verify_ssl: bool = False

@dataclass
class MetricData:
    """Metric data structure"""
    resource_id: str
    metric_key: str
    timestamp: datetime
    value: float
    unit: str = ""

@dataclass
class AlertDefinition:
    """Alert definition structure"""
    name: str
    description: str
    resource_kind: str
    metric_key: str
    operator: str
    threshold: float
    severity: str = "WARNING"

class AriaOperationsAPI:
    """
    Comprehensive Aria Operations API client with advanced features
    """
    
    def __init__(self, credentials: AriaCredentials):
        self.credentials = credentials
        self.base_url = f"https://{credentials.hostname}:{credentials.port}"
        self.session = requests.Session()
        self.session.verify = credentials.verify_ssl
        self.auth_token = None
        self.logger = self._setup_logging()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup structured logging"""
        logger = logging.getLogger('aria_operations')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def authenticate(self) -> bool:
        """
        Authenticate with Aria Operations and obtain auth token
        """
        auth_url = urljoin(self.base_url, "/suite-api/api/auth/token/acquire")
        
        auth_data = {
            "username": self.credentials.username,
            "password": self.credentials.password
        }
        
        try:
            response = self.session.post(
                auth_url, 
                json=auth_data,
                timeout=30
            )
            response.raise_for_status()
            
            auth_response = response.json()
            self.auth_token = auth_response.get('token')
            
            if self.auth_token:
                self.session.headers.update({
                    'Authorization': f'vRealizeOpsToken {self.auth_token}',
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                })
                self.logger.info("Successfully authenticated with Aria Operations")
                return True
            else:
                self.logger.error("Authentication failed - no token received")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Authentication failed: {e}")
            return False
    
    def get_resources(self, 
                     resource_kind: Optional[str] = None,
                     name_filter: Optional[str] = None,
                     page_size: int = 1000) -> List[Dict[str, Any]]:
        """
        Retrieve resources with filtering and pagination
        """
        if not self.auth_token:
            if not self.authenticate():
                return []
        
        resources_url = urljoin(self.base_url, "/suite-api/api/resources")
        
        params = {
            'pageSize': page_size,
            'page': 0
        }
        
        if resource_kind:
            params['resourceKind'] = resource_kind
        if name_filter:
            params['name'] = name_filter
            
        all_resources = []
        
        try:
            while True:
                response = self.session.get(
                    resources_url,
                    params=params,
                    timeout=30
                )
                response.raise_for_status()
                
                data = response.json()
                resources = data.get('resourceList', [])
                
                if not resources:
                    break
                    
                all_resources.extend(resources)
                
                # Check if there are more pages
                if len(resources) < page_size:
                    break
                    
                params['page'] += 1
                
            self.logger.info(f"Retrieved {len(all_resources)} resources")
            return all_resources
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to retrieve resources: {e}")
            return []
    
    def get_metrics(self, 
                   resource_id: str,
                   metric_keys: List[str],
                   start_time: Optional[datetime] = None,
                   end_time: Optional[datetime] = None) -> List[MetricData]:
        """
        Retrieve metrics for a resource with time range filtering
        """
        if not self.auth_token:
            if not self.authenticate():
                return []
        
        if not start_time:
            start_time = datetime.now() - timedelta(hours=1)
        if not end_time:
            end_time = datetime.now()
            
        metrics_url = urljoin(
            self.base_url, 
            f"/suite-api/api/resources/{resource_id}/stats"
        )
        
        params = {
            'statKey': metric_keys,
            'begin': int(start_time.timestamp() * 1000),
            'end': int(end_time.timestamp() * 1000),
            'rollUpType': 'AVG',
            'intervalType': 'MINUTES',
            'intervalQuantifier': 5
        }
        
        try:
            response = self.session.get(
                metrics_url,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            metrics = []
            
            for stat in data.get('values', []):
                stat_key = stat.get('statKey', {}).get('key', '')
                for timestamp_data in stat.get('data', []):
                    timestamp = datetime.fromtimestamp(
                        timestamp_data[0] / 1000
                    )
                    value = timestamp_data[1]
                    
                    metrics.append(MetricData(
                        resource_id=resource_id,
                        metric_key=stat_key,
                        timestamp=timestamp,
                        value=value
                    ))
            
            self.logger.info(f"Retrieved {len(metrics)} metric data points")
            return metrics
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to retrieve metrics: {e}")
            return []
    
    def create_alert_definition(self, alert_def: AlertDefinition) -> bool:
        """
        Create a new alert definition
        """
        if not self.auth_token:
            if not self.authenticate():
                return False
        
        alerts_url = urljoin(
            self.base_url, 
            "/suite-api/api/alertdefinitions"
        )
        
        alert_data = {
            "name": alert_def.name,
            "description": alert_def.description,
            "adapterKindKey": "VMWARE",
            "resourceKindKey": alert_def.resource_kind,
            "waitCycles": 1,
            "cancelCycles": 1,
            "states": [
                {
                    "severity": alert_def.severity,
                    "condition": {
                        "type": "CONDITION_HT",
                        "key": alert_def.metric_key,
                        "operator": alert_def.operator,
                        "value": alert_def.threshold,
                        "valueType": "NUMERIC"
                    }
                }
            ]
        }
        
        try:
            response = self.session.post(
                alerts_url,
                json=alert_data,
                timeout=30
            )
            response.raise_for_status()
            
            self.logger.info(f"Created alert definition: {alert_def.name}")
            return True
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to create alert definition: {e}")
            return False
    
    def get_active_alerts(self, 
                         severity_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve active alerts with optional severity filtering
        """
        if not self.auth_token:
            if not self.authenticate():
                return []
        
        alerts_url = urljoin(self.base_url, "/suite-api/api/alerts")
        
        params = {'activeOnly': 'true'}
        if severity_filter:
            params['alertCriticality'] = severity_filter
            
        try:
            response = self.session.get(
                alerts_url,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            alerts = data.get('alerts', [])
            
            self.logger.info(f"Retrieved {len(alerts)} active alerts")
            return alerts
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to retrieve alerts: {e}")
            return []
    
    def bulk_metric_collection(self, 
                              resource_ids: List[str],
                              metric_keys: List[str],
                              max_workers: int = 5) -> Dict[str, List[MetricData]]:
        """
        Collect metrics from multiple resources concurrently
        """
        results = {}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_resource = {
                executor.submit(
                    self.get_metrics, 
                    resource_id, 
                    metric_keys
                ): resource_id 
                for resource_id in resource_ids
            }
            
            for future in concurrent.futures.as_completed(future_to_resource):
                resource_id = future_to_resource[future]
                try:
                    metrics = future.result()
                    results[resource_id] = metrics
                except Exception as e:
                    self.logger.error(
                        f"Failed to collect metrics for {resource_id}: {e}"
                    )
                    results[resource_id] = []
        
        return results
    
    def generate_health_report(self, 
                              resource_kind: str = "VirtualMachine") -> Dict[str, Any]:
        """
        Generate comprehensive health report for resource type
        """
        self.logger.info(f"Generating health report for {resource_kind}")
        
        # Get all resources of specified kind
        resources = self.get_resources(resource_kind=resource_kind)
        
        if not resources:
            return {"error": "No resources found"}
        
        # Define key metrics to collect
        key_metrics = [
            "cpu|usage_average",
            "mem|usage_average", 
            "disk|usage_average",
            "net|usage_average"
        ]
        
        # Collect metrics for all resources
        resource_ids = [r['identifier'] for r in resources[:10]]  # Limit for demo
        metrics_data = self.bulk_metric_collection(resource_ids, key_metrics)
        
        # Get active alerts
        alerts = self.get_active_alerts()
        
        # Generate report
        report = {
            "generated_at": datetime.now().isoformat(),
            "resource_kind": resource_kind,
            "total_resources": len(resources),
            "resources_analyzed": len(resource_ids),
            "active_alerts": len(alerts),
            "metrics_summary": self._analyze_metrics(metrics_data),
            "top_alerts": alerts[:5],  # Top 5 alerts
            "recommendations": self._generate_recommendations(metrics_data, alerts)
        }
        
        return report
    
    def _analyze_metrics(self, 
                        metrics_data: Dict[str, List[MetricData]]) -> Dict[str, Any]:
        """
        Analyze collected metrics and generate summary statistics
        """
        summary = {
            "cpu_utilization": {"avg": 0, "max": 0, "resources_over_80": 0},
            "memory_utilization": {"avg": 0, "max": 0, "resources_over_80": 0},
            "disk_utilization": {"avg": 0, "max": 0, "resources_over_80": 0}
        }
        
        cpu_values = []
        mem_values = []
        disk_values = []
        
        for resource_id, metrics in metrics_data.items():
            for metric in metrics:
                if "cpu|usage" in metric.metric_key:
                    cpu_values.append(metric.value)
                elif "mem|usage" in metric.metric_key:
                    mem_values.append(metric.value)
                elif "disk|usage" in metric.metric_key:
                    disk_values.append(metric.value)
        
        if cpu_values:
            summary["cpu_utilization"]["avg"] = sum(cpu_values) / len(cpu_values)
            summary["cpu_utilization"]["max"] = max(cpu_values)
            summary["cpu_utilization"]["resources_over_80"] = len([v for v in cpu_values if v > 80])
        
        if mem_values:
            summary["memory_utilization"]["avg"] = sum(mem_values) / len(mem_values)
            summary["memory_utilization"]["max"] = max(mem_values)
            summary["memory_utilization"]["resources_over_80"] = len([v for v in mem_values if v > 80])
        
        if disk_values:
            summary["disk_utilization"]["avg"] = sum(disk_values) / len(disk_values)
            summary["disk_utilization"]["max"] = max(disk_values)
            summary["disk_utilization"]["resources_over_80"] = len([v for v in disk_values if v > 80])
        
        return summary
    
    def _generate_recommendations(self, 
                                 metrics_data: Dict[str, List[MetricData]],
                                 alerts: List[Dict[str, Any]]) -> List[str]:
        """
        Generate actionable recommendations based on metrics and alerts
        """
        recommendations = []
        
        # Analyze high resource utilization
        high_cpu_resources = 0
        high_mem_resources = 0
        
        for resource_id, metrics in metrics_data.items():
            cpu_high = any(m.value > 80 for m in metrics if "cpu|usage" in m.metric_key)
            mem_high = any(m.value > 80 for m in metrics if "mem|usage" in m.metric_key)
            
            if cpu_high:
                high_cpu_resources += 1
            if mem_high:
                high_mem_resources += 1
        
        if high_cpu_resources > 0:
            recommendations.append(
                f"Consider CPU optimization for {high_cpu_resources} resources with high utilization"
            )
        
        if high_mem_resources > 0:
            recommendations.append(
                f"Review memory allocation for {high_mem_resources} resources"
            )
        
        # Analyze alerts
        critical_alerts = len([a for a in alerts if a.get('alertLevel') == 'CRITICAL'])
        if critical_alerts > 0:
            recommendations.append(
                f"Immediate attention required for {critical_alerts} critical alerts"
            )
        
        if not recommendations:
            recommendations.append("System appears to be operating within normal parameters")
        
        return recommendations
    
    def export_data(self, 
                   data: Dict[str, Any], 
                   filename: str,
                   format: str = "json") -> bool:
        """
        Export data to various formats
        """
        try:
            if format.lower() == "json":
                with open(filename, 'w') as f:
                    json.dump(data, f, indent=2, default=str)
            else:
                raise ValueError(f"Unsupported format: {format}")
            
            self.logger.info(f"Data exported to {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to export data: {e}")
            return False
    
    def close(self):
        """
        Clean up resources and close session
        """
        if self.session:
            self.session.close()
        self.logger.info("Aria Operations API client closed")

# Example usage and utility functions
def main():
    """
    Example usage of the Aria Operations API client
    """
    # Initialize credentials
    credentials = AriaCredentials(
        hostname="aria-ops.lab.local",
        username="admin",
        password="VMware123!"
    )
    
    # Create API client
    client = AriaOperationsAPI(credentials)
    
    try:
        # Authenticate
        if not client.authenticate():
            print("Authentication failed")
            return
        
        # Generate health report
        report = client.generate_health_report("VirtualMachine")
        
        # Export report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"aria_health_report_{timestamp}.json"
        client.export_data(report, filename)
        
        print(f"Health report generated and saved to {filename}")
        
    finally:
        client.close()

if __name__ == "__main__":
    main()