# 🔐 Credentials Setup Guide

This guide walks you through setting up all the required credentials and environment variables for Fantine.

## 📋 Required Credentials Overview

You'll need to set up credentials for:
1. **DigitalOcean** (API token, Spaces, SSH keys)
2. **GitHub** (Personal access token)
3. **Environment Variables** (Local and GitHub Secrets)

---

## 🌊 DigitalOcean Setup

### 1. DigitalOcean API Token

**Purpose**: Authenticate Terraform and doctl with DigitalOcean API

**Steps**:
1. Go to [DigitalOcean API Tokens](https://cloud.digitalocean.com/account/api/tokens)
2. Click "Generate New Token"
3. Give it a name like "Fantine-Terraform"
4. Select "Full Access" or "Custom" with these permissions:
   - `Droplets: Read, Write`
   - `Firewalls: Read, Write`
   - `Monitoring: Read, Write`
   - `SSH Keys: Read`
5. Copy the token (you won't see it again!)

**Environment Variable**: `DIGITALOCEAN_TOKEN`

### 2. DigitalOcean Spaces (for Terraform State)

**Purpose**: Store Terraform state files remotely

**Steps**:
1. Go to [DigitalOcean Spaces](https://cloud.digitalocean.com/spaces)
2. Create a new Space (bucket) for storing Terraform state
3. Go to [Spaces Keys](https://cloud.digitalocean.com/account/api/spaces)
4. Generate a new Spaces Key with Read/Write permissions
5. Note down:
   - Access Key
   - Secret Key
   - Space name
   - Endpoint URL

**Environment Variables**:
- `DO_SPACES_ACCESS_KEY`
- `DO_SPACES_SECRET_KEY`
- `DO_SPACES_BUCKET`
- `DO_SPACES_ENDPOINT`

### 3. SSH Key Setup

**Purpose**: Access droplets securely

**Steps**:
1. Generate SSH key pair (if you don't have one):
   ```bash
   ssh-keygen -t ed25519 -C "your-email@example.com" -f ~/.ssh/fantine_key
   ```
2. Go to [DigitalOcean SSH Keys](https://cloud.digitalocean.com/account/security)
3. Click "Add SSH Key"
4. Paste your public key content
5. Give it a memorable name (e.g., "fantine-key")

**Environment Variable**: `DO_SSH_KEY_NAME`

---

## 🐙 GitHub Setup

### GitHub Personal Access Token

**Purpose**: Allow GitHub Actions to access repositories and trigger workflows

**Steps**:
1. Go to [GitHub Settings > Developer Settings > Personal Access Tokens](https://github.com/settings/tokens)
2. Click "Generate new token (classic)"
3. Give it a name like "Fantine-Actions"
4. Select these scopes:
   - `repo` (Full control of private repositories)
   - `workflow` (Update GitHub Action workflows)
   - `admin:org` (if using organization repositories)
5. Set expiration (recommend 1 year)
6. Copy the token

**Environment Variable**: `GH_TOKEN`

---

## 🔧 Environment Variables Setup

### Local Development (.env file)

1. Copy the example file:
   ```bash
   cp env.example .env
   ```

2. Edit `.env` with your actual values:
   ```bash
   nano .env  # or use your preferred editor
   ```

3. Fill in all the required values (see `env.example` for reference)

### GitHub Secrets (for GitHub Actions)

You need to add these secrets to your GitHub repository:

1. Go to your repository on GitHub
2. Click "Settings" → "Secrets and variables" → "Actions"
3. Click "New repository secret" for each:

**Required GitHub Secrets**:
- `DIGITALOCEAN_TOKEN`
- `DO_SPACES_ACCESS_KEY`
- `DO_SPACES_SECRET_KEY`
- `DO_SPACES_BUCKET`
- `DO_SPACES_ENDPOINT`
- `DO_SSH_KEY_NAME`
- `GH_TOKEN`
- `ALERT_EMAIL`

---

## ✅ Verification Steps

### 1. Test DigitalOcean Connection
```bash
# Install doctl if not already installed
# macOS: brew install doctl
# Linux: https://docs.digitalocean.com/reference/doctl/how-to/install/

# Authenticate
doctl auth init

# Test connection
doctl account get
```

### 2. Test Terraform Setup
```bash
# Load environment variables
source .env

# Initialize Terraform
cd terraform
terraform init

# Verify configuration
terraform validate
```

### 3. Test GitHub Actions
```bash
# Install GitHub CLI if not already installed
# macOS: brew install gh
# Linux: https://cli.github.com/

# Authenticate
gh auth login

# Test workflow
gh workflow list
```

---

## 🚨 Security Best Practices

### 1. Never Commit Secrets
- ✅ Add `.env` to `.gitignore`
- ✅ Use GitHub Secrets for CI/CD
- ❌ Never put secrets in code or config files

### 2. Use Least Privilege
- Only grant necessary permissions to tokens
- Use separate tokens for different purposes
- Rotate tokens regularly

### 3. Monitor Usage
- Check DigitalOcean billing regularly
- Monitor GitHub Actions usage
- Set up alerts for unusual activity

---

## 🔍 Troubleshooting

### Common Issues

**"Invalid DigitalOcean token"**
- Verify token has correct permissions
- Check token hasn't expired
- Ensure token is copied correctly (no extra spaces)

**"SSH key not found"**
- Verify SSH key name matches exactly
- Check SSH key is uploaded to DigitalOcean
- Ensure you're using the public key name, not the filename

**"Terraform state backend error"**
- Verify Spaces credentials are correct
- Check Spaces bucket exists
- Ensure Spaces endpoint URL is correct

**"GitHub Actions failing"**
- Verify all secrets are set in GitHub
- Check GitHub token has required scopes
- Ensure repository has Actions enabled

### Getting Help

1. Check the logs in GitHub Actions
2. Verify all environment variables are set
3. Test individual components (doctl, terraform, gh)
4. Check DigitalOcean and GitHub documentation

---

## 📝 Quick Reference

### Required Environment Variables
```bash
# DigitalOcean
DIGITALOCEAN_TOKEN=your_token_here
DO_SPACES_ACCESS_KEY=your_access_key
DO_SPACES_SECRET_KEY=your_secret_key
DO_SPACES_BUCKET=your-bucket-name
DO_SPACES_ENDPOINT=https://region.digitaloceanspaces.com

# SSH
DO_SSH_KEY_NAME=your-ssh-key-name

# GitHub
GH_TOKEN=your_github_token
REPO_URL=https://github.com/username/repo

# Monitoring
ALERT_EMAIL=your-email@example.com
```

### Quick Commands
```bash
# Setup environment
cp env.example .env
# Edit .env with your values

# Test DigitalOcean
doctl auth init
doctl account get

# Test Terraform
cd terraform
terraform init
terraform validate

# Deploy
./scripts/deploy.sh dev 24 "https://example.com"
```
