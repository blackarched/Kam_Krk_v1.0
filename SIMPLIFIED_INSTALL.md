# NeonHack v5.2 - Simplified Installation Guide

🚀 **Ultra-simplified installation with complete automation**

## 🎯 One-Command Installation

### Option 1: Quick Install (Recommended)
```bash
curl -fsSL https://raw.githubusercontent.com/blackarched/Kam_Krk_v1.0/main/quick-install.sh | sudo bash
```

### Option 2: Full Automated Install
```bash
curl -fsSL https://raw.githubusercontent.com/blackarched/Kam_Krk_v1.0/main/auto-install.sh | sudo bash
```

### Option 3: Manual Download + Install
```bash
git clone -b cursor/enhance-dashboard-gui-and-background-display-d831 https://github.com/blackarched/Kam_Krk_v1.0
cd Kam_Krk_v1.0
sudo bash auto-install.sh
```

## ✅ What Gets Automated

### 🔧 System Setup
- ✅ **Auto-detects OS** (Ubuntu, Debian, CentOS, Fedora, Arch)
- ✅ **Installs all dependencies** (Python, Nmap, Hydra, Metasploit, OpenCV)
- ✅ **Creates system user** (`neonhack`)
- ✅ **Sets up Python environment** with all required packages
- ✅ **Configures firewall** (UFW/Firewalld)

### 🗄️ Database & Configuration  
- ✅ **Auto-initializes SQLite database** with proper schema
- ✅ **Generates secure API key** (32-character random)
- ✅ **Creates environment configuration** (.env file)
- ✅ **Auto-detects network interfaces** for scanning

### 🔐 Security & Services
- ✅ **Creates systemd services** (neonhack + privileged scanner)
- ✅ **Sets proper file permissions** (600 for configs, 755 for directories)
- ✅ **Enables security hardening** (ProtectSystem, PrivateTmp)
- ✅ **Configures socket communication** for privileged operations

### 🎨 User Experience
- ✅ **Creates desktop shortcut** (if GUI available)
- ✅ **Installs command-line launcher** (`neonhack` command)
- ✅ **Auto-starts web interface** on port 5000
- ✅ **Validates installation** with health checks

## 🚀 Post-Installation

### Immediate Access
```bash
# Open web interface
neonhack open

# Show API key
neonhack key

# Check status
neonhack status
```

### Service Management
```bash
# Start services
neonhack start

# Stop services  
neonhack stop

# Restart services
neonhack restart

# View live logs
neonhack logs
```

## 🔧 Advanced Configuration (Optional)

### Interactive Configuration Wizard
```bash
sudo python3 /opt/neonhack/config-wizard.py
```

### Manual Environment Configuration
```bash
sudo nano /opt/neonhack/.env
```

### Custom Network Configuration
Edit `/opt/neonhack/app.py` and modify:
```python
ALLOWED_SCAN_SUBNETS = [
    ipaddress.ip_network("192.168.1.0/24"),    # Your home network
    ipaddress.ip_network("10.0.0.0/8"),       # Corporate network
    ipaddress.ip_network("172.16.0.0/12"),    # Private range
    # Add your networks here
]
```

## 🌐 Access Information

| Component | Details |
|-----------|---------|
| **Web Interface** | http://localhost:5000 |
| **Installation Directory** | `/opt/neonhack` |
| **Configuration File** | `/opt/neonhack/.env` |
| **Database** | `/opt/neonhack/jobs.db` |
| **Logs** | `/opt/neonhack/neonhack.log` |
| **Service User** | `neonhack` |

## 🛠️ Troubleshooting

### Common Issues & Solutions

#### Service Not Starting
```bash
# Check service status
sudo systemctl status neonhack

# View detailed logs
sudo journalctl -u neonhack -f

# Restart services
sudo systemctl restart neonhack priv_scanner.socket
```

#### Port 5000 Already in Use
```bash
# Find what's using port 5000
sudo netstat -tlnp | grep 5000

# Change port in configuration
sudo nano /opt/neonhack/.env
# Edit: FLASK_PORT=5001

# Restart service
sudo systemctl restart neonhack
```

#### Permission Issues
```bash
# Fix ownership
sudo chown -R neonhack:neonhack /opt/neonhack

# Fix permissions
sudo chmod 600 /opt/neonhack/.env
sudo chmod +x /opt/neonhack/*.py
```

#### Database Issues
```bash
# Reinitialize database
cd /opt/neonhack
sudo -u neonhack python3 -c "
import sqlite3
conn = sqlite3.connect('jobs.db')
with open('schema.sql', 'r') as f:
    conn.executescript(f.read())
conn.close()
print('Database reinitialized')
"
```

### Validation Commands
```bash
# Check all components
sudo systemctl status neonhack priv_scanner.socket
sudo netstat -tlnp | grep 5000
ls -la /opt/neonhack/
sudo -u neonhack python3 -c "import flask, cv2, scapy; print('Dependencies OK')"
```

## 🔒 Security Best Practices

### Default Security Features
- ✅ **Secure API key generation** (cryptographically random)
- ✅ **Restricted file permissions** (600 for sensitive files)
- ✅ **Service isolation** (dedicated user account)
- ✅ **Socket-based privilege separation** (minimal root exposure)
- ✅ **Firewall configuration** (only necessary ports)

### Additional Hardening (Optional)
```bash
# Enable fail2ban (if available)
sudo systemctl enable --now fail2ban

# Configure stricter firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 5000/tcp
sudo ufw --force enable

# Regular updates
sudo apt update && sudo apt upgrade -y  # Ubuntu/Debian
sudo dnf update -y                      # Fedora/CentOS
```

## 📋 System Requirements

### Minimum Requirements
- **OS**: Ubuntu 18.04+, Debian 9+, CentOS 7+, Fedora 30+, Arch Linux
- **RAM**: 1GB available memory
- **Disk**: 2GB free space
- **Network**: Internet connection for installation
- **Privileges**: Root access (sudo)

### Recommended Requirements  
- **RAM**: 2GB+ for optimal performance
- **Disk**: 5GB+ for logs and additional tools
- **CPU**: 2+ cores for concurrent operations

### Supported Architectures
- ✅ x86_64 (Intel/AMD 64-bit)
- ✅ ARM64 (Raspberry Pi 4, Apple M1/M2)
- ⚠️ ARM32 (limited support)

## 🆘 Support & Documentation

### Getting Help
- 📖 **Full Documentation**: `/opt/neonhack/INSTALL_AND_USAGE_GUIDE.md`
- 🐛 **Issue Tracker**: [GitHub Issues](https://github.com/blackarched/Kam_Krk_v1.0/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/blackarched/Kam_Krk_v1.0/discussions)

### Logs & Debugging
```bash
# Installation log
cat /tmp/neonhack-install.log

# Service logs
sudo journalctl -u neonhack --no-pager -n 50

# Application logs  
tail -f /opt/neonhack/neonhack.log
```

## 🔄 Updates & Maintenance

### Updating NeonHack
```bash
# Stop services
sudo systemctl stop neonhack priv_scanner.socket

# Backup configuration
sudo cp /opt/neonhack/.env /opt/neonhack/.env.backup

# Update from repository
cd /opt/neonhack
sudo git pull origin cursor/enhance-dashboard-gui-and-background-display-d831

# Update Python dependencies
sudo -u neonhack /opt/neonhack/venv/bin/pip install -r requirements.txt

# Restart services
sudo systemctl start neonhack priv_scanner.socket
```

### Uninstallation
```bash
# Stop and disable services
sudo systemctl stop neonhack priv_scanner.socket
sudo systemctl disable neonhack priv_scanner.socket

# Remove service files
sudo rm /etc/systemd/system/neonhack.service
sudo rm /etc/systemd/system/priv_scanner.service
sudo rm /etc/systemd/system/priv_scanner.socket

# Remove installation directory
sudo rm -rf /opt/neonhack

# Remove user (optional)
sudo userdel -r neonhack

# Remove launcher
sudo rm /usr/local/bin/neonhack

# Reload systemd
sudo systemctl daemon-reload
```

---

## 🎉 Ready to Hack!

After installation, simply run:
```bash
neonhack open
```

Your cyberpunk penetration testing suite is ready! 🏴‍☠️

**Default Access:**
- 🌐 **URL**: http://localhost:5000
- 🔑 **API Key**: Displayed during installation (also: `neonhack key`)

Happy Hacking! 🚀