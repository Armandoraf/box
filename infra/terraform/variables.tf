variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type        = string
  description = "GCP region"
  default     = "us-central1"
}

variable "zone" {
  type        = string
  description = "GCP zone"
  default     = "us-central1-a"
}

variable "network_name" {
  type        = string
  description = "VPC network name"
  default     = "box-vpc"
}

variable "subnet_name" {
  type        = string
  description = "Subnetwork name"
  default     = "box-subnet"
}

variable "subnet_cidr" {
  type        = string
  description = "Subnetwork CIDR range"
  default     = "10.0.0.0/24"
}

variable "allowed_ssh_cidrs" {
  type        = list(string)
  description = "CIDR ranges allowed to SSH"
  default     = ["0.0.0.0/0"]
}

variable "runner_count" {
  type        = number
  description = "Number of runner VMs"
  default     = 5
}

variable "runner_machine_type" {
  type        = string
  description = "Machine type for runners"
  default     = "e2-small"
}

variable "router_machine_type" {
  type        = string
  description = "Machine type for router"
  default     = "e2-small"
}

variable "runner_disk_gb" {
  type        = number
  description = "Runner boot disk size"
  default     = 20
}

variable "router_disk_gb" {
  type        = number
  description = "Router boot disk size"
  default     = 20
}

variable "base_image" {
  type        = string
  description = "Base OS image"
  default     = "debian-cloud/debian-12"
}

variable "runner_image" {
  type        = string
  description = "Container image for runner"
  default     = "ghcr.io/armandoraf/box:latest"
}

variable "router_image" {
  type        = string
  description = "Container image for router"
  default     = "ghcr.io/armandoraf/box-router:latest"
}

variable "chrome_debug_port" {
  type        = number
  description = "Chrome debug port for runners"
  default     = 9225
}

variable "runner_tag" {
  type        = string
  description = "Network tag for runner instances"
  default     = "box-runner"
}

variable "router_tag" {
  type        = string
  description = "Network tag for router instances"
  default     = "box-router"
}

variable "api_key" {
  type        = string
  description = "API key required by Cloud Armor"
  default     = "changeme"
}

variable "api_key_header" {
  type        = string
  description = "Header name for API key"
  default     = "x-api-key"
}

variable "enable_rate_limit" {
  type        = bool
  description = "Enable Cloud Armor rate limiting"
  default     = true
}

variable "rate_limit_count" {
  type        = number
  description = "Requests allowed per interval"
  default     = 60
}

variable "rate_limit_interval_sec" {
  type        = number
  description = "Rate limit interval seconds"
  default     = 60
}
