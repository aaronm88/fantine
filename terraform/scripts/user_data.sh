#!/bin/bash

# Fantine Droplet Initialization Script
# This script runs when the droplet is first created

set -e

# Configure non-interactive mode to prevent SSH configuration prompts
export DEBIAN_FRONTEND=noninteractive
export DEBCONF_NONINTERACTIVE_SEEN=true

# Pre-configure SSH to avoid interactive prompts
echo 'openssh-server openssh-server/use_old_init_script boolean false' | debconf-set-selections
echo 'openssh-server openssh-server/permit_root_login boolean true' | debconf-set-selections

# Update system
apt-get update
apt-get upgrade -y

# Install essential packages with non-interactive mode
apt-get install -y \
    curl \
    wget \
    git \
    python3 \
    python3-pip \
    python3-venv \
    nodejs \
    npm \
    htop \
    unzip \
    jq \
    cron \
    logrotate \
    openssh-server

# Ensure SSH service is properly configured and running
systemctl enable ssh
systemctl start ssh

# Create project directory
mkdir -p /opt/fantine
cd /opt/fantine

# Clone the repository
# Using GH_TOKEN for authentication
git clone https://${github_token}@github.com/aaronm88/fantine . || { echo "Failed to clone repository"; exit 1; }

# Set up Python environment
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip

# Install Python dependencies if requirements.txt exists
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
fi

# Install Node.js dependencies if package.json exists
if [ -f package.json ]; then
    npm install
fi

# Create systemd service for the scraper
cat > /etc/systemd/system/fantine-scraper.service << EOF
[Unit]
Description=Fantine Ohio Water Scraper
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/fantine
Environment=PATH=/opt/fantine/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=DO_SPACES_KEY=DO801PDT7VMHU4TUK8QY
Environment=DO_SPACES_SECRET=GlXR28EAyw1HhW0rbqTPO2rSzDxSzMbRpcf65PePNU8
Environment=DO_SPACES_BUCKET=fantine-bucket
Environment=DO_SPACES_ENDPOINT=https://nyc3.digitaloceanspaces.com
ExecStart=/opt/fantine/venv/bin/python scraper.py --scraper-type ohio-water
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Create cleanup script
cat > /opt/fantine/cleanup.sh << 'EOF'
#!/bin/bash
# Cleanup script to run before droplet termination

echo "Starting cleanup process..."

# Stop the scraper service
systemctl stop fantine-scraper || true

# Upload results to cloud storage (implement based on your needs)
# aws s3 cp /opt/fantine/results/ s3://your-bucket/results/ --recursive

# Clean up temporary files
rm -rf /tmp/*
rm -rf /opt/fantine/temp/*

# Log completion
echo "Cleanup completed at $(date)" >> /var/log/fantine-cleanup.log

# Signal completion (this could trigger the teardown)
curl -X POST "https://api.github.com/repos/your-org/fantine/dispatches" \
  -H "Authorization: token ${github_token}" \
  -H "Accept: application/vnd.github.v3+json" \
  -d '{"event_type": "cleanup_completed"}'
EOF

chmod +x /opt/fantine/cleanup.sh

# Create cron job for automatic cleanup after max lifetime
cat > /etc/cron.d/fantine-cleanup << EOF
# Run cleanup after ${max_lifetime_hours} hours
0 */${max_lifetime_hours} * * * root /opt/fantine/cleanup.sh
EOF

# Set up logging
mkdir -p /var/log/fantine
cat > /etc/logrotate.d/fantine << EOF
/var/log/fantine/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 root root
}
EOF

# Create status endpoint
cat > /opt/fantine/status.py << 'EOF'
#!/usr/bin/env python3
import json
import subprocess
import sys
from datetime import datetime

def get_status():
    try:
        # Check if scraper is running
        result = subprocess.run(['systemctl', 'is-active', 'fantine-scraper'], 
                              capture_output=True, text=True)
        scraper_active = result.stdout.strip() == 'active'
        
        # Get system info
        uptime = subprocess.run(['uptime'], capture_output=True, text=True).stdout.strip()
        
        status = {
            'timestamp': datetime.now().isoformat(),
            'scraper_active': scraper_active,
            'uptime': uptime,
            'status': 'healthy' if scraper_active else 'stopped'
        }
        
        return status
    except Exception as e:
        return {'error': str(e), 'status': 'error'}

if __name__ == '__main__':
    status = get_status()
    print(json.dumps(status, indent=2))
EOF

chmod +x /opt/fantine/status.py

# Start the scraper service
systemctl daemon-reload
systemctl enable fantine-scraper
systemctl start fantine-scraper

# Log initialization completion
echo "Fantine droplet initialized successfully at $(date)" >> /var/log/fantine-init.log

# Create initialization completion marker
touch /var/log/fantine-init-complete

# Create a simple web server for status checks
cat > /opt/fantine/status_server.py << 'EOF'
#!/usr/bin/env python3
import http.server
import socketserver
import json
import subprocess
import os
from datetime import datetime

class StatusHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/status':
            try:
                # Check if initialization is complete
                init_complete = os.path.exists('/var/log/fantine-init-complete')
                
                if init_complete:
                    result = subprocess.run(['/opt/fantine/status.py'], 
                                          capture_output=True, text=True)
                    status_data = json.loads(result.stdout)
                    status_data['initialization_complete'] = True
                else:
                    status_data = {
                        'status': 'initializing',
                        'initialization_complete': False,
                        'message': 'Droplet is still initializing...'
                    }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(status_data).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    PORT = 8080
    with socketserver.TCPServer(("", PORT), StatusHandler) as httpd:
        print(f"Status server running on port {PORT}")
        httpd.serve_forever()
EOF

chmod +x /opt/fantine/status_server.py

# Start status server
nohup python3 /opt/fantine/status_server.py > /var/log/fantine-status.log 2>&1 &

echo "Initialization completed successfully!"
