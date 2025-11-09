---
all:
  children:
    aria_operations:
      hosts:
        aria-ops-01:
          ansible_host: ${aria_operations_ip}
          ansible_user: root
          ansible_ssh_pass: ${admin_password}
          ansible_ssh_common_args: '-o StrictHostKeyChecking=no'
    
    aria_automation:
      hosts:
        aria-auto-01:
          ansible_host: ${aria_automation_ip}
          ansible_user: root
          ansible_ssh_pass: ${admin_password}
          ansible_ssh_common_args: '-o StrictHostKeyChecking=no'
    
    aria_suite:
      children:
        - aria_operations
        - aria_automation
      vars:
        ansible_python_interpreter: /usr/bin/python3# Updated Sun Nov  9 12:52:21 CET 2025
# Updated Sun Nov  9 12:56:35 CET 2025
