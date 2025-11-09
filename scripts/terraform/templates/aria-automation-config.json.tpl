{
  "deployment": {
    "hostname": "${hostname}",
    "ip_address": "${ip_address}",
    "admin_password": "${admin_password}",
    "deployment_size": "medium",
    "ntp_servers": ["pool.ntp.org"],
    "dns_servers": ["8.8.8.8", "1.1.1.1"]
  },
  "ssl": {
    "ca_certificate": "${ca_cert}"
  },
  "integrations": {
    "aria_operations_endpoint": "${operations_endpoint}",
    "vcenter_integration": true,
    "nsx_integration": false
  },
  "configuration": {
    "cluster_mode": true,
    "high_availability": true,
    "backup_enabled": true
  }
