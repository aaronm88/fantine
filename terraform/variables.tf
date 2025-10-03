variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "fantine"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "enabled" {
  description = "Whether to create the droplet"
  type        = bool
  default     = true
}

variable "droplet_image" {
  description = "DigitalOcean droplet image/snapshot"
  type        = string
  default     = "ubuntu-22-04-x64"
}

variable "droplet_size" {
  description = "DigitalOcean droplet size"
  type        = string
  default     = "s-1vcpu-1gb"
}

variable "droplet_region" {
  description = "DigitalOcean region"
  type        = string
  default     = "nyc1"
}

variable "ssh_key_name" {
  description = "Name of the SSH key in DigitalOcean"
  type        = string
}

variable "gh_token" {
  description = "GitHub token for repository access"
  type        = string
  sensitive   = true
}

variable "repo_url" {
  description = "GitHub repository URL for the scraping code"
  type        = string
}

variable "allowed_ssh_ips" {
  description = "List of IP addresses allowed to SSH"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "alert_email" {
  description = "Email address for monitoring alerts"
  type        = string
}

variable "max_lifetime_hours" {
  description = "Maximum lifetime of the droplet in hours"
  type        = number
  default     = 24
}

variable "scraping_config" {
  description = "Configuration for the scraping job"
  type = object({
    target_urls    = list(string)
    output_format  = string
    max_pages      = number
    delay_seconds  = number
  })
  default = {
    target_urls   = []
    output_format = "json"
    max_pages     = 100
    delay_seconds = 1
  }
}
