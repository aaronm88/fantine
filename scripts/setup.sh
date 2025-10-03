#!/bin/bash

# Fantine Project Setup Script
# This script sets up the development environment and initial configuration

set -e

echo "🚀 Setting up Fantine project..."

# Check if required tools are installed
check_dependency() {
    if ! command -v $1 &> /dev/null; then
        echo "❌ $1 is not installed. Please install it first."
        exit 1
    fi
}

echo "📋 Checking dependencies..."
check_dependency "terraform"
check_dependency "doctl"
check_dependency "gh"

# Create necessary directories
echo "📁 Creating project directories..."
mkdir -p terraform/scripts
mkdir -p .github/workflows
mkdir -p scripts
mkdir -p docs

# Set up Terraform backend configuration
echo "🔧 Setting up Terraform backend..."
cat > terraform/backend.tf << 'EOF'
terraform {
  backend "s3" {
    # Configure via environment variables:
    # DO_SPACES_ENDPOINT, DO_SPACES_BUCKET, DO_SPACES_KEY, DO_SPACES_SECRET
  }
}
EOF

# Create terraform.tfvars.example
echo "📝 Creating example configuration..."
cat > terraform/terraform.tfvars.example << 'EOF'
# DigitalOcean Configuration
project_name = "fantine"
environment = "dev"
droplet_image = "ubuntu-22-04-x64"
droplet_size = "s-1vcpu-1gb"
droplet_region = "nyc1"
ssh_key_name = "your-ssh-key-name"

# Scraping Configuration
scraping_config = {
  target_urls   = ["https://example.com", "https://another-site.com"]
  output_format = "json"
  max_pages     = 100
  delay_seconds = 1
}

# Monitoring
alert_email = "your-email@example.com"
max_lifetime_hours = 24
EOF

# Create environment setup script
echo "🌍 Creating environment setup script..."
cat > scripts/setup-env.sh << 'EOF'
#!/bin/bash
# Environment setup script

echo "Setting up Fantine environment variables..."

# DigitalOcean API Token
if [ -z "$DIGITALOCEAN_TOKEN" ]; then
    echo "Please set DIGITALOCEAN_TOKEN environment variable"
    echo "You can get it from: https://cloud.digitalocean.com/account/api/tokens"
    exit 1
fi

# DigitalOcean Spaces (for Terraform state)
if [ -z "$DO_SPACES_ACCESS_KEY" ]; then
    echo "Please set DO_SPACES_ACCESS_KEY environment variable"
    exit 1
fi

if [ -z "$DO_SPACES_SECRET_KEY" ]; then
    echo "Please set DO_SPACES_SECRET_KEY environment variable"
    exit 1
fi

if [ -z "$DO_SPACES_BUCKET" ]; then
    echo "Please set DO_SPACES_BUCKET environment variable"
    exit 1
fi

if [ -z "$DO_SPACES_ENDPOINT" ]; then
    echo "Please set DO_SPACES_ENDPOINT environment variable (e.g., https://nyc3.digitaloceanspaces.com)"
    exit 1
fi

echo "✅ Environment variables validated"

# Initialize Terraform
cd terraform
terraform init

echo "🎉 Setup complete! You can now:"
echo "1. Copy terraform/terraform.tfvars.example to terraform/terraform.tfvars"
echo "2. Edit terraform/terraform.tfvars with your configuration"
echo "3. Run 'terraform plan' to see what will be created"
echo "4. Run 'terraform apply' to create the infrastructure"
EOF

chmod +x scripts/setup-env.sh

# Create deployment script
echo "🚀 Creating deployment script..."
cat > scripts/deploy.sh << 'EOF'
#!/bin/bash
# Deployment script for Fantine

set -e

ENVIRONMENT=${1:-dev}
MAX_LIFETIME=${2:-24}
TARGET_URLS=${3:-"https://example.com"}

echo "🚀 Deploying Fantine scraper..."
echo "Environment: $ENVIRONMENT"
echo "Max Lifetime: $MAX_LIFETIME hours"
echo "Target URLs: $TARGET_URLS"

# Trigger GitHub Actions workflow
gh workflow run deploy.yml \
  --ref main \
  -f environment=$ENVIRONMENT \
  -f max_lifetime_hours=$MAX_LIFETIME \
  -f target_urls="$TARGET_URLS" \
  -f max_pages=100

echo "✅ Deployment triggered! Check GitHub Actions for progress."
EOF

chmod +x scripts/deploy.sh

# Create cleanup script
echo "🧹 Creating cleanup script..."
cat > scripts/cleanup.sh << 'EOF'
#!/bin/bash
# Cleanup script for Fantine

set -e

ENVIRONMENT=${1:-dev}

echo "🧹 Cleaning up Fantine resources..."

# Trigger cleanup workflow
gh workflow run deploy.yml \
  --ref main \
  -f environment=$ENVIRONMENT

echo "✅ Cleanup triggered! Check GitHub Actions for progress."
EOF

chmod +x scripts/cleanup.sh

# Create monitoring script
echo "📊 Creating monitoring script..."
cat > scripts/monitor.sh << 'EOF'
#!/bin/bash
# Monitoring script for Fantine

set -e

ENVIRONMENT=${1:-dev}

echo "📊 Monitoring Fantine resources..."

# Get droplet information
doctl compute droplet list --format "ID,Name,Status,PublicIPv4" --tag-name "project:fantine,environment:$ENVIRONMENT"

echo ""
echo "To get detailed status of a specific droplet:"
echo "curl http://DROPLET_IP:8080/status"
EOF

chmod +x scripts/monitor.sh

# Create documentation
echo "📚 Creating documentation..."
cat > docs/README.md << 'EOF'
# Fantine Documentation

## Overview
Fantine is an automated Infrastructure-as-Code project for spinning up DigitalOcean droplets for web scraping.

## Quick Start

1. **Setup Environment**
   ```bash
   ./scripts/setup-env.sh
   ```

2. **Configure Variables**
   ```bash
   cp terraform/terraform.tfvars.example terraform/terraform.tfvars
   # Edit terraform/terraform.tfvars with your settings
   ```

3. **Deploy**
   ```bash
   ./scripts/deploy.sh dev 24 "https://example.com,https://another-site.com"
   ```

4. **Monitor**
   ```bash
   ./scripts/monitor.sh dev
   ```

5. **Cleanup**
   ```bash
   ./scripts/cleanup.sh dev
   ```

## Architecture

- **Terraform**: Infrastructure as Code
- **GitHub Actions**: Workflow orchestration
- **DigitalOcean**: Cloud provider
- **Python**: Scraping application
- **Monitoring**: Built-in DigitalOcean monitoring + custom status endpoints

## Configuration

### Required Environment Variables
- `DIGITALOCEAN_TOKEN`: DigitalOcean API token
- `DO_SPACES_ACCESS_KEY`: DigitalOcean Spaces access key
- `DO_SPACES_SECRET_KEY`: DigitalOcean Spaces secret key
- `DO_SPACES_BUCKET`: DigitalOcean Spaces bucket name
- `DO_SPACES_ENDPOINT`: DigitalOcean Spaces endpoint URL

### Terraform Variables
See `terraform/terraform.tfvars.example` for all available configuration options.

## Security

- SSH keys are managed through DigitalOcean
- Secrets are stored in GitHub Secrets
- Firewall rules restrict access
- Automatic cleanup prevents resource leaks

## Monitoring

- DigitalOcean built-in monitoring
- Custom status endpoint at `http://DROPLET_IP:8080/status`
- Logs stored in `/var/log/fantine/`
- Email alerts for high resource usage

## Troubleshooting

### Common Issues

1. **Droplet not starting**: Check SSH key configuration
2. **Scraper not running**: Check logs in `/var/log/fantine/scraper.log`
3. **Cleanup not working**: Verify GitHub token permissions

### Logs
- Scraper logs: `/var/log/fantine/scraper.log`
- System logs: `/var/log/fantine-init.log`
- Status server: `/var/log/fantine-status.log`
EOF

# Make scripts executable
chmod +x scripts/*.sh

echo "✅ Fantine project setup complete!"
echo ""
echo "Next steps:"
echo "1. Run './scripts/setup-env.sh' to validate your environment"
echo "2. Copy and edit terraform/terraform.tfvars.example"
echo "3. Use './scripts/deploy.sh' to deploy your scraper"
echo ""
echo "📚 See docs/README.md for detailed documentation"
