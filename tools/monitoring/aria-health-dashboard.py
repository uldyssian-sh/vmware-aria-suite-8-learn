#!/usr/bin/env python3
"""
VMware Aria Suite Health Dashboard
Real-time monitoring dashboard with advanced analytics and alerting
"""

import asyncio
import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import aiohttp
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import streamlit as st
from dataclasses import dataclass, asdict
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('aria_dashboard.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class AriaEndpoint:
    """Aria Suite endpoint configuration"""
    name: str
    url: str
    username: str
    password: str
    type: str  # 'operations', 'automation', 'network-insight'
    enabled: bool = True

@dataclass
class HealthMetric:
    """Health metric data structure"""
    endpoint: str
    metric_name: str
    value: float
    unit: str
    timestamp: datetime
    status: str  # 'healthy', 'warning', 'critical'
    threshold_warning: float = 80.0
    threshold_critical: float = 90.0

@dataclass
class AlertRule:
    """Alert rule configuration"""
    name: str
    metric_pattern: str
    condition: str  # 'greater_than', 'less_than', 'equals'
    threshold: float
    severity: str  # 'info', 'warning', 'critical'
    enabled: bool = True

class DatabaseManager:
    """SQLite database manager for metrics storage"""

    def __init__(self, db_path: str = "aria_metrics.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    endpoint TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    value REAL NOT NULL,
                    unit TEXT,
                    timestamp DATETIME NOT NULL,
                    status TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_name TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    value REAL NOT NULL,
                    threshold REAL NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT,
                    timestamp DATETIME NOT NULL,
                    acknowledged BOOLEAN DEFAULT FALSE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_timestamp 
                ON metrics(timestamp)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_endpoint 
                ON metrics(endpoint)
            """)

    def store_metric(self, metric: HealthMetric):
        """Store a health metric"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO metrics (endpoint, metric_name, value, unit, timestamp, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                metric.endpoint,
                metric.metric_name,
                metric.value,
                metric.unit,
                metric.timestamp,
                metric.status
            ))

    def get_metrics(self, 
                   endpoint: Optional[str] = None,
                   metric_name: Optional[str] = None,
                   hours_back: int = 24) -> List[Dict]:
        """Retrieve metrics from database"""
        query = """
            SELECT endpoint, metric_name, value, unit, timestamp, status
            FROM metrics
            WHERE timestamp >= ?
        """
        params = [datetime.now() - timedelta(hours=hours_back)]

        if endpoint:
            query += " AND endpoint = ?"
            params.append(endpoint)

        if metric_name:
            query += " AND metric_name = ?"
            params.append(metric_name)

        query += " ORDER BY timestamp DESC"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def store_alert(
        self, rule_name: str, endpoint: str, metric_name: str,
        value: float, threshold: float, severity: str, message: str
    ):
        """Store an alert"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO alerts (rule_name, endpoint, metric_name, value, 
                                  threshold, severity, message, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rule_name, endpoint, metric_name, value,
                threshold, severity, message, datetime.now()
            ))

class AriaHealthCollector:
    """Health metrics collector for Aria Suite endpoints"""

    def __init__(self, endpoints: List[AriaEndpoint], db_manager: DatabaseManager):
        self.endpoints = endpoints
        self.db_manager = db_manager
        self.session = None
        self.running = False

    async def start_collection(self, interval_seconds: int = 300):
        """Start continuous health metrics collection"""
        self.running = True
        connector = aiohttp.TCPConnector(ssl=False)  # For lab environments
        self.session = aiohttp.ClientSession(connector=connector)

        logger.info(f"Starting health collection with {interval_seconds}s interval")

        try:
            while self.running:
                await self.collect_all_metrics()
                await asyncio.sleep(interval_seconds)
        finally:
            if self.session:
                await self.session.close()

    async def collect_all_metrics(self):
        """Collect metrics from all enabled endpoints"""
        tasks = []
        for endpoint in self.endpoints:
            if endpoint.enabled:
                if endpoint.type == 'operations':
                    tasks.append(self.collect_operations_metrics(endpoint))
                elif endpoint.type == 'automation':
                    tasks.append(self.collect_automation_metrics(endpoint))
                elif endpoint.type == 'network-insight':
                    tasks.append(self.collect_network_insight_metrics(endpoint))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def collect_operations_metrics(self, endpoint: AriaEndpoint):
        """Collect Aria Operations specific metrics"""
        try:
            # Authenticate
            auth_token = await self.authenticate_operations(endpoint)
            if not auth_token:
                return

            headers = {
                'Authorization': f'vRealizeOpsToken {auth_token}',
                'Content-Type': 'application/json'
            }

            # Collect cluster health metrics
            cluster_url = f"{endpoint.url}/suite-api/api/resources"
            params = {'resourceKind': 'ClusterComputeResource', 'pageSize': 100}

            async with self.session.get(
                cluster_url, headers=headers, params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    await self.process_operations_resources(
                        endpoint, data.get('resourceList', [])
                    )
                else:
                    logger.warning(
                        f"Failed to collect from {endpoint.name}: {response.status}"
                    )

        except Exception as e:
            logger.error(f"Error collecting from {endpoint.name}: {e}")

    async def authenticate_operations(self, endpoint: AriaEndpoint) -> Optional[str]:
        """Authenticate with Aria Operations"""
        try:
            auth_url = f"{endpoint.url}/suite-api/api/auth/token/acquire"
            auth_data = {
                'username': endpoint.username,
                'password': endpoint.password
            }

            async with self.session.post(auth_url, json=auth_data) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('token')
                else:
                    logger.error(
                        f"Authentication failed for {endpoint.name}: {response.status}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Authentication error for {endpoint.name}: {e}")
            return None

    async def process_operations_resources(
        self, endpoint: AriaEndpoint, resources: List[Dict]
    ):
        """Process Aria Operations resources and extract metrics"""
        for resource in resources:
            resource_id = resource.get('identifier')
            resource_name = resource.get('resourceKey', {}).get(
                'name', 'Unknown'
            )

            # Simulate health metrics (in real implementation, fetch actual)
            metrics = [
                HealthMetric(
                    endpoint=endpoint.name,
                    metric_name=f"cluster_health_{resource_name}",
                    value=95.0,  # Simulated health score
                    unit='percent',
                    timestamp=datetime.now(),
                    status='healthy'
                ),
                HealthMetric(
                    endpoint=endpoint.name,
                    metric_name=f"cluster_cpu_usage_{resource_name}",
                    value=65.5,  # Simulated CPU usage
                    unit='percent',
                    timestamp=datetime.now(),
                    status='healthy'
                )
            ]

            for metric in metrics:
                self.db_manager.store_metric(metric)

    async def collect_automation_metrics(self, endpoint: AriaEndpoint):
        """Collect Aria Automation specific metrics"""
        try:
            # Simulate Aria Automation metrics collection
            metrics = [
                HealthMetric(
                    endpoint=endpoint.name,
                    metric_name="deployment_success_rate",
                    value=98.5,
                    unit='percent',
                    timestamp=datetime.now(),
                    status='healthy'
                ),
                HealthMetric(
                    endpoint=endpoint.name,
                    metric_name="active_deployments",
                    value=45,
                    unit='count',
                    timestamp=datetime.now(),
                    status='healthy'
                )
            ]

            for metric in metrics:
                self.db_manager.store_metric(metric)

        except Exception as e:
            logger.error(
                f"Error collecting automation metrics from {endpoint.name}: {e}"
            )

    async def collect_network_insight_metrics(self, endpoint: AriaEndpoint):
        """Collect Aria Network Insight specific metrics"""
        try:
            # Simulate Network Insight metrics collection
            metrics = [
                HealthMetric(
                    endpoint=endpoint.name,
                    metric_name="network_flows_per_second",
                    value=15420,
                    unit='flows/sec',
                    timestamp=datetime.now(),
                    status='healthy'
                ),
                HealthMetric(
                    endpoint=endpoint.name,
                    metric_name="network_latency_avg",
                    value=2.3,
                    unit='ms',
                    timestamp=datetime.now(),
                    status='healthy'
                )
            ]

            for metric in metrics:
                self.db_manager.store_metric(metric)

        except Exception as e:
            logger.error(
                f"Error collecting network insight metrics from {endpoint.name}: {e}"
            )

    def stop_collection(self):
        """Stop metrics collection"""
        self.running = False
        logger.info("Health collection stopped")

class AlertManager:
    """Alert management and notification system"""

    def __init__(
        self, db_manager: DatabaseManager, alert_rules: List[AlertRule]
    ):
        self.db_manager = db_manager
        self.alert_rules = alert_rules
        self.email_config = self.load_email_config()

    def load_email_config(self) -> Dict:
        """Load email configuration from environment or config file"""
        return {
            'smtp_server': 'smtp.lab.local',
            'smtp_port': 587,
            'username': 'alerts@lab.local',
            'password': 'AlertPassword123!',
            'from_email': 'aria-alerts@lab.local',
            'to_emails': ['admin@lab.local']
        }

    def evaluate_alerts(self):
        """Evaluate alert rules against recent metrics"""
        recent_metrics = self.db_manager.get_metrics(hours_back=1)

        for rule in self.alert_rules:
            if not rule.enabled:
                continue

            matching_metrics = [
                m for m in recent_metrics 
                if rule.metric_pattern in m['metric_name']
            ]

            for metric in matching_metrics:
                if self.check_alert_condition(rule, metric['value']):
                    self.trigger_alert(rule, metric)

    def check_alert_condition(self, rule: AlertRule, value: float) -> bool:
        """Check if metric value triggers alert condition"""
        if rule.condition == 'greater_than':
            return value > rule.threshold
        elif rule.condition == 'less_than':
            return value < rule.threshold
        elif rule.condition == 'equals':
            return abs(value - rule.threshold) < 0.01
        return False

    def trigger_alert(self, rule: AlertRule, metric: Dict):
        """Trigger an alert and send notifications"""
        message = (
            f"Alert: {rule.name}\n"
            f"Metric: {metric['metric_name']}\n"
            f"Value: {metric['value']} {metric['unit']}\n"
            f"Threshold: {rule.threshold}\n"
            f"Severity: {rule.severity}\n"
            f"Endpoint: {metric['endpoint']}\n"
            f"Time: {metric['timestamp']}"
        )

        # Store alert in database
        self.db_manager.store_alert(
            rule.name,
            metric['endpoint'],
            metric['metric_name'],
            metric['value'],
            rule.threshold,
            rule.severity,
            message
        )

        # Send email notification
        if rule.severity in ['warning', 'critical']:
            self.send_email_alert(rule, message)

        logger.warning(f"Alert triggered: {rule.name} - {message}")

    def send_email_alert(self, rule: AlertRule, message: str):
        """Send email alert notification"""
        try:
            msg = MimeMultipart()
            msg['From'] = self.email_config['from_email']
            msg['To'] = ', '.join(self.email_config['to_emails'])
            msg['Subject'] = f"Aria Suite Alert: {rule.name} ({rule.severity.upper()})"

            msg.attach(MimeText(message, 'plain'))

            server = smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port'])
            server.starttls()
            server.login(self.email_config['username'], self.email_config['password'])

            text = msg.as_string()
            server.sendmail(
                self.email_config['from_email'],
                self.email_config['to_emails'],
                text
            )
            server.quit()

            logger.info(f"Email alert sent for: {rule.name}")

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")

class DashboardGenerator:
    """Generate interactive dashboard using Streamlit and Plotly"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def create_dashboard(self):
        """Create Streamlit dashboard"""
        st.set_page_config(
            page_title="Aria Suite Health Dashboard",
            page_icon="📊",
            layout="wide"
        )

        st.title("🔍 VMware Aria Suite Health Dashboard")
        st.markdown("Real-time monitoring and analytics for Aria Suite components")

        # Sidebar controls
        st.sidebar.header("Dashboard Controls")
        time_range = st.sidebar.selectbox(
            "Time Range",
            ["Last Hour", "Last 6 Hours", "Last 24 Hours", "Last 7 Days"]
        )

        hours_map = {
            "Last Hour": 1,
            "Last 6 Hours": 6,
            "Last 24 Hours": 24,
            "Last 7 Days": 168
        }
        hours_back = hours_map[time_range]

        # Auto-refresh
        auto_refresh = st.sidebar.checkbox("Auto Refresh (30s)", value=True)
        if auto_refresh:
            time.sleep(30)
            st.experimental_rerun()

        # Main dashboard content
        self.render_overview_metrics(hours_back)
        self.render_endpoint_health(hours_back)
        self.render_performance_charts(hours_back)
        self.render_alerts_section()

    def render_overview_metrics(self, hours_back: int):
        """Render overview metrics cards"""
        st.header("📈 Overview Metrics")

        metrics = self.db_manager.get_metrics(hours_back=hours_back)

        if not metrics:
            st.warning("No metrics data available")
            return

        # Calculate summary statistics
        total_metrics = len(metrics)
        healthy_count = len([m for m in metrics if m['status'] == 'healthy'])
        warning_count = len([m for m in metrics if m['status'] == 'warning'])
        critical_count = len([m for m in metrics if m['status'] == 'critical'])

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Metrics", total_metrics)

        with col2:
            st.metric("Healthy", healthy_count, delta=f"{(healthy_count/total_metrics*100):.1f}%")

        with col3:
            st.metric("Warnings", warning_count, delta=f"{(warning_count/total_metrics*100):.1f}%")

        with col4:
            st.metric("Critical", critical_count, delta=f"{(critical_count/total_metrics*100):.1f}%")

    def render_endpoint_health(self, hours_back: int):
        """Render endpoint health status"""
        st.header("🏥 Endpoint Health Status")

        metrics = self.db_manager.get_metrics(hours_back=hours_back)

        if not metrics:
            return

        # Group by endpoint
        df = pd.DataFrame(metrics)
        endpoint_health = df.groupby('endpoint')['status'].apply(
            lambda x: 'healthy' if all(s == 'healthy' for s in x) else
                     'critical' if any(s == 'critical' for s in x) else 'warning'
        ).reset_index()

        # Create status indicators
        for _, row in endpoint_health.iterrows():
            status_color = {
                'healthy': '🟢',
                'warning': '🟡',
                'critical': '🔴'
            }

            st.write(
                f"{status_color[row['status']]} **{row['endpoint']}** - {row['status'].title()}"
            )

    def render_performance_charts(self, hours_back: int):
        """Render performance charts"""
        st.header("📊 Performance Charts")

        metrics = self.db_manager.get_metrics(hours_back=hours_back)

        if not metrics:
            return

        df = pd.DataFrame(metrics)
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # CPU Usage Chart
        cpu_metrics = df[df['metric_name'].str.contains('cpu', case=False)]
        if not cpu_metrics.empty:
            fig_cpu = px.line(
                cpu_metrics,
                x='timestamp',
                y='value',
                color='endpoint',
                title='CPU Usage Over Time',
                labels={'value': 'CPU Usage (%)', 'timestamp': 'Time'}
            )
            st.plotly_chart(fig_cpu, use_container_width=True)

        # Health Score Chart
        health_metrics = df[df['metric_name'].str.contains('health', case=False)]
        if not health_metrics.empty:
            fig_health = px.line(
                health_metrics,
                x='timestamp',
                y='value',
                color='endpoint',
                title='Health Score Over Time',
                labels={'value': 'Health Score', 'timestamp': 'Time'}
            )
            st.plotly_chart(fig_health, use_container_width=True)

    def render_alerts_section(self):
        """Render alerts section"""
        st.header("🚨 Recent Alerts")

        # This would query alerts from database
        st.info("No recent alerts - system operating normally")


def main():
    """Main application entry point"""
    # Configuration
    endpoints = [
        AriaEndpoint(
            name="Aria Operations",
            url="https://aria-ops.lab.local",
            username="admin",
            password="VMware123!",
            type="operations"
        ),
        AriaEndpoint(
            name="Aria Automation",
            url="https://aria-automation.lab.local",
            username="admin",
            password="VMware123!",
            type="automation"
        )
    ]

    alert_rules = [
        AlertRule(
            name="High CPU Usage",
            metric_pattern="cpu_usage",
            condition="greater_than",
            threshold=85.0,
            severity="warning"
        ),
        AlertRule(
            name="Critical CPU Usage",
            metric_pattern="cpu_usage",
            condition="greater_than",
            threshold=95.0,
            severity="critical"
        )
    ]

    # Initialize components
    db_manager = DatabaseManager()
    collector = AriaHealthCollector(endpoints, db_manager)
    alert_manager = AlertManager(db_manager, alert_rules)
    dashboard = DashboardGenerator(db_manager)

    # Start background collection in separate thread
    def run_collector():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(collector.start_collection(interval_seconds=300))

    collector_thread = threading.Thread(target=run_collector, daemon=True)
    collector_thread.start()

    # Start alert evaluation in separate thread
    def run_alerts():
        while True:
            alert_manager.evaluate_alerts()
            time.sleep(60)  # Check every minute

    alert_thread = threading.Thread(target=run_alerts, daemon=True)
    alert_thread.start()

    # Run dashboard
    dashboard.create_dashboard()


if __name__ == "__main__":
    main()
