output "droplet_id" {
  description = "ID of the created droplet"
  value       = var.enabled ? digitalocean_droplet.scraper[0].id : null
}

output "droplet_ip" {
  description = "Public IP address of the droplet"
  value       = var.enabled ? digitalocean_droplet.scraper[0].ipv4_address : null
}

output "droplet_name" {
  description = "Name of the created droplet"
  value       = var.enabled ? digitalocean_droplet.scraper[0].name : null
}

output "droplet_status" {
  description = "Status of the droplet"
  value       = var.enabled ? digitalocean_droplet.scraper[0].status : null
}

output "ssh_command" {
  description = "SSH command to connect to the droplet"
  value       = var.enabled ? "ssh root@${digitalocean_droplet.scraper[0].ipv4_address}" : null
}

output "firewall_id" {
  description = "ID of the created firewall"
  value       = var.enabled ? digitalocean_firewall.scraper_firewall[0].id : null
}
