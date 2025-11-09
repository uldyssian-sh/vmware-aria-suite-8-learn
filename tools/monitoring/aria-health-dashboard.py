#!/usr/bin/env python3
"""
VMware Aria Suite Health Dashboard
Simple monitoring dashboard
"""

import json
import logging
from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class HealthMetric:
    """Simple health metric"""
    name: str
    value: float
    status: str


class SimpleMonitor:
    """Simple monitoring class"""
    
    def __init__(self):
        self.metrics = []
    
    def add_metric(self, metric: HealthMetric):
        """Add a metric"""
        self.metrics.append(metric)
    
    def get_status(self) -> str:
        """Get overall status"""
        if not self.metrics:
            return "unknown"
        
        statuses = [m.status for m in self.metrics]
        if "critical" in statuses:
            return "critical"
        elif "warning" in statuses:
            return "warning"
        return "healthy"


def generate_sample_metrics() -> List[HealthMetric]:
    """Generate sample metrics for demo"""
    return [
        HealthMetric("cpu_usage", 45.5, "healthy"),
        HealthMetric("memory_usage", 67.2, "warning"),
        HealthMetric("disk_usage", 23.1, "healthy")
    ]


def check_alerts(metrics: List[HealthMetric]) -> List[str]:
    """Simple alert checking"""
    alerts = []
    for metric in metrics:
        if metric.status == "critical":
            alerts.append(f"CRITICAL: {metric.name} = {metric.value}")
        elif metric.status == "warning":
            alerts.append(f"WARNING: {metric.name} = {metric.value}")
    return alerts


def generate_report(monitor: SimpleMonitor) -> Dict:
    """Generate simple monitoring report"""
    return {
        "timestamp": datetime.now().isoformat(),
        "status": monitor.get_status(),
        "metrics_count": len(monitor.metrics),
        "alerts": check_alerts(monitor.metrics)
    }


def main():
    """Simple main function"""
    monitor = SimpleMonitor()
    
    # Add sample metrics
    for metric in generate_sample_metrics():
        monitor.add_metric(metric)
    
    # Generate report
    report = generate_report(monitor)
    
    # Print report
    print(json.dumps(report, indent=2))
    logger.info(f"System status: {report['status']}")


if __name__ == "__main__":
    main()# Updated 20251109_123808
# Updated Sun Nov  9 12:50:01 CET 2025
# Updated Sun Nov  9 12:52:21 CET 2025
