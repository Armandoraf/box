terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  required_version = ">= 1.5.0"
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

locals {
  runner_urls = join(",", [
    for r in google_compute_instance.runner : "http://${r.network_interface[0].network_ip}:8000"
  ])
}

resource "google_compute_network" "vpc" {
  name                    = var.network_name
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  name          = var.subnet_name
  ip_cidr_range = var.subnet_cidr
  region        = var.region
  network       = google_compute_network.vpc.id
}

resource "google_compute_firewall" "allow_ssh" {
  name    = "box-allow-ssh"
  network = google_compute_network.vpc.name
  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
  source_ranges = var.allowed_ssh_cidrs
}

resource "google_compute_firewall" "allow_internal" {
  name    = "box-allow-internal"
  network = google_compute_network.vpc.name
  allow {
    protocol = "tcp"
    ports    = ["8000", "8080"]
  }
  source_ranges = [var.subnet_cidr]
  target_tags   = [var.runner_tag, var.router_tag]
}

resource "google_compute_firewall" "allow_lb_health" {
  name    = "box-allow-lb-health"
  network = google_compute_network.vpc.name
  allow {
    protocol = "tcp"
    ports    = ["8080"]
  }
  source_ranges = ["130.211.0.0/22", "35.191.0.0/16"]
  target_tags   = [var.router_tag]
}

resource "google_compute_address" "runner_ips" {
  count  = var.runner_count
  name   = "box-runner-ip-${count.index}"
  region = var.region
}

resource "google_compute_address" "router_ip" {
  name   = "box-router-ip"
  region = var.region
}

resource "google_compute_instance" "runner" {
  count        = var.runner_count
  name         = "box-runner-${count.index}"
  machine_type = var.runner_machine_type
  zone         = var.zone
  tags         = [var.runner_tag]

  boot_disk {
    initialize_params {
      image = var.base_image
      size  = var.runner_disk_gb
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.subnet.id
    access_config {
      nat_ip = google_compute_address.runner_ips[count.index].address
    }
  }

  metadata_startup_script = templatefile(
    "${path.module}/templates/runner_startup.sh.tpl",
    {
      image             = var.runner_image
      chrome_debug_port = var.chrome_debug_port
    }
  )
}

resource "google_compute_instance" "router" {
  name         = "box-router"
  machine_type = var.router_machine_type
  zone         = var.zone
  tags         = [var.router_tag]

  boot_disk {
    initialize_params {
      image = var.base_image
      size  = var.router_disk_gb
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.subnet.id
    access_config {
      nat_ip = google_compute_address.router_ip.address
    }
  }

  metadata_startup_script = templatefile(
    "${path.module}/templates/router_startup.sh.tpl",
    {
      image       = var.router_image
      runner_urls = local.runner_urls
    }
  )
}

resource "google_compute_instance_group" "router_group" {
  name      = "box-router-group"
  zone      = var.zone
  instances = [google_compute_instance.router.self_link]

  named_port {
    name = "http"
    port = 8080
  }
}

resource "google_compute_health_check" "router" {
  name               = "box-router-hc"
  check_interval_sec = 5
  timeout_sec        = 2

  http_health_check {
    port         = 8080
    request_path = "/health"
  }
}

resource "google_compute_security_policy" "router_policy" {
  name = "box-router-policy"

  dynamic "rule" {
    for_each = var.enable_rate_limit ? [1] : []
    content {
      priority = 900
      action   = "throttle"
      match {
        versioned_expr = "SRC_IPS_V1"
        config {
          src_ip_ranges = ["*"]
        }
      }
      rate_limit_options {
        rate_limit_threshold {
          count        = var.rate_limit_count
          interval_sec = var.rate_limit_interval_sec
        }
        conform_action = "allow"
        exceed_action  = "deny(429)"
      }
    }
  }

  rule {
    priority = 1000
    action   = "allow"
    match {
      expr {
        expression = "request.headers['${var.api_key_header}'] == '${var.api_key}'"
      }
    }
  }

  rule {
    priority = 2147483647
    action   = "deny(403)"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
  }
}

resource "google_compute_backend_service" "router" {
  name                  = "box-router-backend"
  protocol              = "HTTP"
  port_name             = "http"
  timeout_sec           = 30
  load_balancing_scheme = "EXTERNAL"
  health_checks         = [google_compute_health_check.router.id]
  security_policy       = google_compute_security_policy.router_policy.id

  backend {
    group = google_compute_instance_group.router_group.self_link
  }
}

resource "google_compute_url_map" "router" {
  name            = "box-router-url-map"
  default_service = google_compute_backend_service.router.id
}

resource "google_compute_target_http_proxy" "router" {
  name    = "box-router-http-proxy"
  url_map = google_compute_url_map.router.id
}

resource "google_compute_global_address" "lb_ip" {
  name = "box-router-lb-ip"
}

resource "google_compute_global_forwarding_rule" "router_http" {
  name       = "box-router-http-fw"
  ip_address = google_compute_global_address.lb_ip.address
  port_range = "80"
  target     = google_compute_target_http_proxy.router.id
}
