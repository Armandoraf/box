output "runner_external_ips" {
  description = "Static external IPs for runner VMs"
  value       = [for ip in google_compute_address.runner_ips : ip.address]
}

output "router_external_ip" {
  description = "External IP for router VM (SSH/admin)"
  value       = google_compute_address.router_ip.address
}

output "load_balancer_ip" {
  description = "Global HTTP load balancer IP"
  value       = google_compute_global_address.lb_ip.address
}

output "runner_internal_urls" {
  description = "Internal runner URLs used by router"
  value       = local.runner_urls
}
