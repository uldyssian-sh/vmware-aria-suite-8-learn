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
  "configuration": {
    "cluster_mode": true,
    "high_availability": true,
    "backup_enabled": true
  }
}# Updated Sun Nov  9 12:52:21 CET 2025
# Updated Sun Nov  9 12:56:35 CET 2025
