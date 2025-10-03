terraform {
  required_version = ">= 1.0"
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
}

provider "digitalocean" {
  # Token will be provided via environment variable DIGITALOCEAN_TOKEN
}

# Data sources
data "digitalocean_ssh_key" "main" {
  name = var.ssh_key_name
}

# Main droplet for web scraping
resource "digitalocean_droplet" "scraper" {
  count    = var.enabled ? 1 : 0
  image    = var.droplet_image
  name     = "${var.project_name}-scraper-${random_id.instance_id[0].hex}"
  region   = var.droplet_region
  size     = var.droplet_size
  ssh_keys = [data.digitalocean_ssh_key.main.id]
  
  # User data script for initial setup
  user_data = templatefile("${path.module}/scripts/user_data.sh", {
    project_name = var.project_name
    github_token = var.gh_token
    repo_url     = var.repo_url
    max_lifetime_hours = var.max_lifetime_hours
  })
  
  # Tags for identification
  tags = [
    "project:${var.project_name}",
    "environment:${var.environment}",
    "purpose:webscraping"
  ]
  
  # Lifecycle management
  lifecycle {
    create_before_destroy = true
  }
}

# Random ID for unique naming
resource "random_id" "instance_id" {
  count       = var.enabled ? 1 : 0
  byte_length = 4
}

# Firewall rules
resource "digitalocean_firewall" "scraper_firewall" {
  count = var.enabled ? 1 : 0
  name  = "${var.project_name}-scraper-firewall"
  
  droplet_ids = [digitalocean_droplet.scraper[0].id]
  
  # SSH access
  inbound_rule {
    protocol         = "tcp"
    port_range       = "22"
    source_addresses = var.allowed_ssh_ips
  }
  
  # HTTP/HTTPS for web scraping
  inbound_rule {
    protocol         = "tcp"
    port_range       = "80"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }
  
  inbound_rule {
    protocol         = "tcp"
    port_range       = "443"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }
  
  # Outbound rules
  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
  
  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
  
  outbound_rule {
    protocol              = "icmp"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}

# Note: Monitoring alerts are not supported in the current DigitalOcean provider
# You can set up monitoring manually in the DigitalOcean dashboard
