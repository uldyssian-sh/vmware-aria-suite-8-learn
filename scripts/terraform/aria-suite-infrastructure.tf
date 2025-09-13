# VMware Aria Suite 8 Infrastructure as Code
# Comprehensive Terraform configuration for Aria Suite deployment

terraform {
  required_version = ">= 1.6.0"
  
  required_providers {
    vsphere = {
      source  = "hashicorp/vsphere"
      version = "~> 2.5.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0.0"
    }
  }
  
  backend "local" {
    path = "terraform.tfstate"
  }
}

# Variables
variable "vsphere_server" {
  description = "vSphere server FQDN or IP"
  type        = string
  default     = "vcsa.lab.local"
}

variable "vsphere_user" {
  description = "vSphere username"
  type        = string
  default     = "administrator@vsphere.local"
}

variable "vsphere_password" {
  description = "vSphere password"
  type        = string
  sensitive   = true
}

variable "datacenter_name" {
  description = "vSphere datacenter name"
  type        = string
  default     = "Lab-Datacenter"
}

variable "cluster_name" {
  description = "vSphere cluster name"
  type        = string
  default     = "Lab-Cluster"
}

variable "datastore_name" {
  description = "vSphere datastore name"
  type        = string
  default     = "datastore1"
}

variable "network_name" {
  description = "vSphere network name"
  type        = string
  default     = "VM Network"
}

variable "aria_operations_config" {
  description = "Aria Operations configuration"
  type = object({
    vm_name     = string
    cpu_count   = number
    memory_mb   = number
    disk_size   = number
    ip_address  = string
    netmask     = string
    gateway     = string
    dns_servers = list(string)
  })
  default = {
    vm_name     = "aria-operations"
    cpu_count   = 8
    memory_mb   = 32768
    disk_size   = 500
    ip_address  = "192.168.1.100"
    netmask     = "255.255.255.0"
    gateway     = "192.168.1.1"
    dns_servers = ["192.168.1.10", "8.8.8.8"]
  }
}

variable "aria_automation_config" {
  description = "Aria Automation configuration"
  type = object({
    vm_name     = string
    cpu_count   = number
    memory_mb   = number
    disk_size   = number
    ip_address  = string
    netmask     = string
    gateway     = string
    dns_servers = list(string)
  })
  default = {
    vm_name     = "aria-automation"
    cpu_count   = 8
    memory_mb   = 24576
    disk_size   = 400
    ip_address  = "192.168.1.101"
    netmask     = "255.255.255.0"
    gateway     = "192.168.1.1"
    dns_servers = ["192.168.1.10", "8.8.8.8"]
  }
}

# Data sources
data "vsphere_datacenter" "dc" {
  name = var.datacenter_name
}

data "vsphere_compute_cluster" "cluster" {
  name          = var.cluster_name
  datacenter_id = data.vsphere_datacenter.dc.id
}

data "vsphere_datastore" "datastore" {
  name          = var.datastore_name
  datacenter_id = data.vsphere_datacenter.dc.id
}

data "vsphere_network" "network" {
  name          = var.network_name
  datacenter_id = data.vsphere_datacenter.dc.id
}

data "vsphere_content_library" "library" {
  name = "Aria-Suite-Library"
}

data "vsphere_content_library_item" "aria_operations_ova" {
  name       = "VMware-vRealize-Operations-Manager-Appliance"
  type       = "ovf"
  library_id = data.vsphere_content_library.library.id
}

data "vsphere_content_library_item" "aria_automation_ova" {
  name       = "VMware-vRealize-Automation-Appliance"
  type       = "ovf"
  library_id = data.vsphere_content_library.library.id
}

# Random password generation
resource "random_password" "aria_admin_password" {
  length  = 16
  special = true
  upper   = true
  lower   = true
  numeric = true
}

# TLS private key for certificates
resource "tls_private_key" "aria_ca_key" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "tls_self_signed_cert" "aria_ca_cert" {
  private_key_pem = tls_private_key.aria_ca_key.private_key_pem

  subject {
    common_name         = "Aria Suite CA"
    organization        = "Lab Environment"
    organizational_unit = "IT Department"
    country             = "US"
    locality           = "Lab City"
    province           = "Lab State"
  }

  validity_period_hours = 8760 # 1 year

  is_ca_certificate = true

  allowed_uses = [
    "key_encipherment",
    "digital_signature",
    "cert_signing",
    "crl_signing"
  ]
}

# Aria Operations VM
resource "vsphere_virtual_machine" "aria_operations" {
  name             = var.aria_operations_config.vm_name
  resource_pool_id = data.vsphere_compute_cluster.cluster.resource_pool_id
  datastore_id     = data.vsphere_datastore.datastore.id
  folder           = "Aria-Suite"

  num_cpus               = var.aria_operations_config.cpu_count
  memory                 = var.aria_operations_config.memory_mb
  guest_id               = "other3xLinux64Guest"
  firmware               = "efi"
  efi_secure_boot_enabled = true

  wait_for_guest_net_timeout = 15
  wait_for_guest_ip_timeout  = 15

  network_interface {
    network_id   = data.vsphere_network.network.id
    adapter_type = "vmxnet3"
  }

  disk {
    label            = "disk0"
    size             = var.aria_operations_config.disk_size
    thin_provisioned = true
    eagerly_scrub    = false
  }

  # Additional disk for data
  disk {
    label            = "disk1"
    size             = 200
    thin_provisioned = true
    eagerly_scrub    = false
    unit_number      = 1
  }

  clone {
    template_uuid = data.vsphere_content_library_item.aria_operations_ova.id
  }

  vapp {
    properties = {
      "vami.ip0.VMware-vRealize-Operations-Manager-Appliance" = var.aria_operations_config.ip_address
      "vami.netmask0.VMware-vRealize-Operations-Manager-Appliance" = var.aria_operations_config.netmask
      "vami.gateway.VMware-vRealize-Operations-Manager-Appliance" = var.aria_operations_config.gateway
      "vami.DNS.VMware-vRealize-Operations-Manager-Appliance" = join(",", var.aria_operations_config.dns_servers)
      "vami.domain.VMware-vRealize-Operations-Manager-Appliance" = "lab.local"
      "vami.searchpath.VMware-vRealize-Operations-Manager-Appliance" = "lab.local"
      "va-ssh-enabled" = "True"
      "vami.hostname" = var.aria_operations_config.vm_name
    }
  }

  lifecycle {
    ignore_changes = [
      annotation,
      vapp[0].properties,
    ]
  }

  tags = [
    vsphere_tag.environment.id,
    vsphere_tag.application.id,
    vsphere_tag.tier.id
  ]
}

# Aria Automation VM
resource "vsphere_virtual_machine" "aria_automation" {
  name             = var.aria_automation_config.vm_name
  resource_pool_id = data.vsphere_compute_cluster.cluster.resource_pool_id
  datastore_id     = data.vsphere_datastore.datastore.id
  folder           = "Aria-Suite"

  num_cpus               = var.aria_automation_config.cpu_count
  memory                 = var.aria_automation_config.memory_mb
  guest_id               = "other3xLinux64Guest"
  firmware               = "efi"
  efi_secure_boot_enabled = true

  wait_for_guest_net_timeout = 15
  wait_for_guest_ip_timeout  = 15

  network_interface {
    network_id   = data.vsphere_network.network.id
    adapter_type = "vmxnet3"
  }

  disk {
    label            = "disk0"
    size             = var.aria_automation_config.disk_size
    thin_provisioned = true
    eagerly_scrub    = false
  }

  clone {
    template_uuid = data.vsphere_content_library_item.aria_automation_ova.id
  }

  vapp {
    properties = {
      "vami.ip0.VMware-vRealize-Automation-Appliance" = var.aria_automation_config.ip_address
      "vami.netmask0.VMware-vRealize-Automation-Appliance" = var.aria_automation_config.netmask
      "vami.gateway.VMware-vRealize-Automation-Appliance" = var.aria_automation_config.gateway
      "vami.DNS.VMware-vRealize-Automation-Appliance" = join(",", var.aria_automation_config.dns_servers)
      "vami.domain.VMware-vRealize-Automation-Appliance" = "lab.local"
      "vami.searchpath.VMware-vRealize-Automation-Appliance" = "lab.local"
      "va-ssh-enabled" = "True"
      "vami.hostname" = var.aria_automation_config.vm_name
    }
  }

  depends_on = [vsphere_virtual_machine.aria_operations]

  lifecycle {
    ignore_changes = [
      annotation,
      vapp[0].properties,
    ]
  }

  tags = [
    vsphere_tag.environment.id,
    vsphere_tag.application.id,
    vsphere_tag.tier.id
  ]
}

# Tag categories and tags
resource "vsphere_tag_category" "environment" {
  name        = "Environment"
  description = "Environment classification"
  cardinality = "SINGLE"

  associable_types = [
    "VirtualMachine",
    "Datastore",
    "ClusterComputeResource"
  ]
}

resource "vsphere_tag" "environment" {
  name        = "Lab"
  category_id = vsphere_tag_category.environment.id
  description = "Lab environment resources"
}

resource "vsphere_tag_category" "application" {
  name        = "Application"
  description = "Application classification"
  cardinality = "SINGLE"

  associable_types = [
    "VirtualMachine"
  ]
}

resource "vsphere_tag" "application" {
  name        = "Aria-Suite"
  category_id = vsphere_tag_category.application.id
  description = "VMware Aria Suite components"
}

resource "vsphere_tag_category" "tier" {
  name        = "Tier"
  description = "Application tier classification"
  cardinality = "SINGLE"

  associable_types = [
    "VirtualMachine"
  ]
}

resource "vsphere_tag" "tier" {
  name        = "Management"
  category_id = vsphere_tag_category.tier.id
  description = "Management tier applications"
}

# VM folder for organization
resource "vsphere_folder" "aria_suite" {
  path          = "Aria-Suite"
  type          = "vm"
  datacenter_id = data.vsphere_datacenter.dc.id
}

# Local files for configuration
resource "local_file" "aria_operations_config" {
  content = templatefile("${path.module}/templates/aria-operations-config.json.tpl", {
    hostname     = var.aria_operations_config.vm_name
    ip_address   = var.aria_operations_config.ip_address
    admin_password = random_password.aria_admin_password.result
    ca_cert      = tls_self_signed_cert.aria_ca_cert.cert_pem
  })
  filename = "${path.module}/generated/aria-operations-config.json"
}

resource "local_file" "aria_automation_config" {
  content = templatefile("${path.module}/templates/aria-automation-config.json.tpl", {
    hostname     = var.aria_automation_config.vm_name
    ip_address   = var.aria_automation_config.ip_address
    admin_password = random_password.aria_admin_password.result
    ca_cert      = tls_self_signed_cert.aria_ca_cert.cert_pem
    operations_endpoint = "https://${var.aria_operations_config.ip_address}"
  })
  filename = "${path.module}/generated/aria-automation-config.json"
}

# Ansible inventory for post-deployment configuration
resource "local_file" "ansible_inventory" {
  content = templatefile("${path.module}/templates/inventory.yml.tpl", {
    aria_operations_ip = var.aria_operations_config.ip_address
    aria_automation_ip = var.aria_automation_config.ip_address
    admin_password     = random_password.aria_admin_password.result
  })
  filename = "${path.module}/generated/inventory.yml"
}

# Output values
output "aria_operations_ip" {
  description = "Aria Operations IP address"
  value       = var.aria_operations_config.ip_address
}

output "aria_automation_ip" {
  description = "Aria Automation IP address"
  value       = var.aria_automation_config.ip_address
}

output "admin_password" {
  description = "Generated admin password"
  value       = random_password.aria_admin_password.result
  sensitive   = true
}

output "ca_certificate" {
  description = "Generated CA certificate"
  value       = tls_self_signed_cert.aria_ca_cert.cert_pem
  sensitive   = true
}

output "deployment_summary" {
  description = "Deployment summary information"
  value = {
    aria_operations = {
      vm_name    = vsphere_virtual_machine.aria_operations.name
      ip_address = var.aria_operations_config.ip_address
      cpu_count  = var.aria_operations_config.cpu_count
      memory_gb  = var.aria_operations_config.memory_mb / 1024
      disk_gb    = var.aria_operations_config.disk_size
    }
    aria_automation = {
      vm_name    = vsphere_virtual_machine.aria_automation.name
      ip_address = var.aria_automation_config.ip_address
      cpu_count  = var.aria_automation_config.cpu_count
      memory_gb  = var.aria_automation_config.memory_mb / 1024
      disk_gb    = var.aria_automation_config.disk_size
    }
    access_urls = {
      aria_operations = "https://${var.aria_operations_config.ip_address}"
      aria_automation = "https://${var.aria_automation_config.ip_address}"
    }
  }
}