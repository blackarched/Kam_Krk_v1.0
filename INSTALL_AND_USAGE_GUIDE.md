# 🚀 NeonHack Installation & Usage Guide

## Table of Contents
1. [System Requirements](#system-requirements)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Starting the Application](#starting-the-application)
5. [Using the Interface](#using-the-interface)
6. [Feature Guide](#feature-guide)
7. [Troubleshooting](#troubleshooting)
8. [Security Considerations](#security-considerations)
9. [FAQ](#faq)

---

## System Requirements

### Minimum Requirements
- **Operating System**: Linux (Ubuntu 20.04+, Debian 10+, CentOS 8+, or similar)
- **Python**: 3.8 or higher
- **RAM**: 2GB minimum (4GB recommended)
- **Disk Space**: 1GB free space
- **Network**: Internet connection for initial setup

### Required Privileges
- **Root/sudo access** for privileged scanning operations
- **Network access** to target systems (for scanning)

---

## Installation

### Step 1: System Preparation

#### Ubuntu/Debian:
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install required system packages
sudo apt install -y python3 python3-pip python3-venv git nmap hydra metasploit-framework opencv-python ffmpeg
```

#### CentOS/RHEL/Fedora:
```bash
# Update system packages
sudo dnf update -y

# Install required packages
sudo dnf install -y python3 python3-pip git nmap hydra metasploit-framework opencv ffmpeg

# Install EPEL repository if needed (CentOS/RHEL)
sudo dnf install -y epel-release
```

### Step 2: Download NeonHack
```bash
# Clone or download the NeonHack files to your preferred directory
cd /opt
sudo mkdir neonhack
sudo chown $USER:$USER neonhack
cd neonhack

# Copy all NeonHack files to this directory
# (kam_grbs5.html, kam_grbs.html, app.py, etc.)
```

### Step 3: Python Environment Setup
```bash
# Create virtual environment
python3 -m venv neonhack-env

# Activate virtual environment
source neonhack-env/bin/activate

# Install Python dependencies
pip install flask sqlite3 opencv-python scapy pymetasploit3 psutil requests
```

### Step 4: Database Setup
```bash
# Create the SQLite database
python3 -c "
import sqlite3
conn = sqlite3.connect('jobs.db')
conn.executescript(open('schema.sql').read())
conn.close()
print('Database initialized successfully')
"
```

### Step 5: Privileged Scanner Service Setup
```bash
# Copy service files
sudo cp priv_scan_srvc/priv_scanner.service /etc/systemd/system/
sudo cp priv_scan_srvc/priv_scanner.socket /etc/systemd/system/

# Create privileged scanner script
sudo cp privileged_scanner_service.py /usr/local/bin/
sudo chmod +x /usr/local/bin/privileged_scanner_service.py

# Enable and start the privileged service
sudo systemctl daemon-reload
sudo systemctl enable priv_scanner.socket
sudo systemctl start priv_scanner.socket
```

---

## Configuration

### Step 1: Set Environment Variables
```bash
# Create environment file
cat > .env << EOF
# API Key for authentication (change this!)
NEONHACK_API_KEY=your-super-secure-api-key-here-change-me

# Metasploit RPC password (if using Metasploit features)
MSF_PASSWORD=your-msf-password-here
EOF

# Load environment variables
source .env
export NEONHACK_API_KEY
export MSF_PASSWORD
```

### Step 2: Configure Allowed Scan Targets
Edit `app.py` and modify the `ALLOWED_SCAN_SUBNETS` list:
```python
ALLOWED_SCAN_SUBNETS = [
    ipaddress.ip_network("192.168.1.0/24"),    # Your home network
    ipaddress.ip_network("10.0.0.0/8"),       # Private network range
    ipaddress.ip_network("172.16.0.0/12"),    # Private network range
    # Add your authorized networks here
]
```

### Step 3: Metasploit Setup (Optional)
If you want to use Metasploit features:
```bash
# Start Metasploit RPC daemon
sudo msfdb init
msfconsole -q -x "load msgrpc ServerHost=127.0.0.1 ServerPort=55553 User=msf Pass=$MSF_PASSWORD; exit"

# Or run it in background
nohup msfconsole -q -x "load msgrpc ServerHost=127.0.0.1 ServerPort=55553 User=msf Pass=$MSF_PASSWORD" > /dev/null 2>&1 &
```

---

## Starting the Application

### Method 1: Direct Python Execution
```bash
# Activate virtual environment
cd /opt/neonhack
source neonhack-env/bin/activate

# Set environment variables
export NEONHACK_API_KEY="your-api-key-here"
export MSF_PASSWORD="your-msf-password"

# Start the application
python3 app.py
```

### Method 2: Systemd Service (Recommended)
Create a systemd service file:
```bash
sudo tee /etc/systemd/system/neonhack.service << EOF
[Unit]
Description=NeonHack Security Tool
After=network.target

[Service]
Type=simple
User=neonhack
Group=neonhack
WorkingDirectory=/opt/neonhack
Environment=NEONHACK_API_KEY=your-api-key-here
Environment=MSF_PASSWORD=your-msf-password
ExecStart=/opt/neonhack/neonhack-env/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Create neonhack user
sudo useradd -r -s /bin/false neonhack
sudo chown -R neonhack:neonhack /opt/neonhack

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable neonhack
sudo systemctl start neonhack
```

### Access the Interface
1. Open your web browser
2. Navigate to: `http://localhost:5000` or `http://your-server-ip:5000`
3. You should see the NeonHack interface with Matrix rain background and holographic elements

---

## Using the Interface

### Initial Setup
1. **Enter API Key**: In the "🔑 AUTHORIZATION" section, enter your API key
2. **Verify Connection**: The interface will validate your key before allowing operations

### Navigation
- **Matrix Background**: Animated background with falling code
- **Holographic Header**: 3D globe with floating particles and code
- **Control Panels**: Each feature has its own holographic panel with scanning lines
- **Console**: Real-time output appears in the holographic console at the bottom

---

## Feature Guide

### 1. Network Scanner (◈ NETWORK SCANNER)
**Purpose**: Discover active devices on a network using ARP scanning

**Steps**:
1. Select network interface (eth0/wlan0)
2. Enter target network in CIDR format (e.g., `192.168.1.0/24`)
3. Click "INITIATE NETWORK SCAN"
4. View results in the console

**Example Input**:
- Interface: `eth0`
- IP Range: `192.168.1.0/24`

### 2. Port Connectivity Test (🛡 PORT CONNECTIVITY)
**Purpose**: Test if specific ports are open on target systems

**Steps**:
1. Enter target IP address
2. Select protocol (SSH/FTP/HTTP)
3. Click "RUN CONNECTIVITY TEST"
4. Check console for connection results

**Example Input**:
- Target IP: `192.168.1.100`
- Protocol: `SSH`

### 3. Hydra Password Attack (⚔️ HYDRA ATTACK)
**Purpose**: Perform dictionary attacks against login services

**Steps**:
1. Enter target IP address
2. Select protocol (SSH/FTP/HTTP-GET)
3. Enter usernames (one per line)
4. Enter passwords (one per line)
5. Click "BEGIN HYDRA ATTACK"
6. Monitor progress in console

**Example Input**:
- Target IP: `192.168.1.100`
- Protocol: `SSH`
- Usernames:
  ```
  root
  admin
  user
  ```
- Passwords:
  ```
  password
  123456
  admin
  ```

### 4. Metasploit Exploitation (💣 EXPLOIT EXECUTION)
**Purpose**: Execute Metasploit modules against targets

**Steps**:
1. Enter target IP address
2. Select exploit module from dropdown
3. Click "EXECUTE MODULE"
4. Monitor execution in console

**Available Modules**:
- `exploit/unix/ftp/vsftpd_234_backdoor`
- `auxiliary/scanner/portscan/tcp`

### 5. Camera Scanner (📷 WiFi Camera Scanner) - v5.2 Only
**Purpose**: Discover and stream from network cameras

**Steps**:
1. Enter network range in CIDR format
2. Click "SCAN FOR CAMERAS"
3. Wait for scan completion
4. Click "View Stream" on discovered cameras
5. Camera feed opens in modal window

**Example Input**:
- Network: `192.168.1.0/24`

---

## Troubleshooting

### Common Issues

#### 1. "API key is required" Error
**Symptoms**: All operations fail with API key error
**Solutions**:
- Ensure you've entered the API key in the authorization field
- Verify the API key matches the one set in your environment variables
- Check browser console for JavaScript errors

#### 2. Network Scan Returns Empty Results
**Symptoms**: ARP scan shows no devices found
**Possible Causes & Solutions**:
- **Permissions**: Ensure privileged scanner service is running
  ```bash
  sudo systemctl status priv_scanner.socket
  sudo systemctl restart priv_scanner.socket
  ```
- **Network Interface**: Verify correct interface selected
  ```bash
  ip addr show  # List available interfaces
  ```
- **Target Network**: Ensure target network is correct and accessible
- **Firewall**: Check if firewall is blocking ARP packets
  ```bash
  sudo ufw status
  sudo iptables -L
  ```

#### 3. Hydra Attack Fails Immediately
**Symptoms**: Hydra job starts but fails quickly
**Possible Causes & Solutions**:
- **Hydra Not Found**: Install hydra
  ```bash
  sudo apt install hydra  # Ubuntu/Debian
  sudo dnf install hydra  # CentOS/Fedora
  ```
- **PATH Issues**: Ensure hydra is in system PATH
  ```bash
  which hydra
  export PATH=$PATH:/usr/bin:/usr/local/bin
  ```
- **Target Unreachable**: Verify target IP is accessible
  ```bash
  ping target-ip
  telnet target-ip port
  ```
- **Service Not Running**: Ensure target service is running
  ```bash
  nmap -p 22,21,80 target-ip
  ```

#### 4. Metasploit Connection Failed
**Symptoms**: "Failed to connect to msfrpcd" error
**Solutions**:
- **Start Metasploit RPC**:
  ```bash
  msfconsole -q -x "load msgrpc ServerHost=127.0.0.1 ServerPort=55553 User=msf Pass=your-password; exit"
  ```
- **Check RPC Status**:
  ```bash
  netstat -tlnp | grep 55553
  ```
- **Verify Password**: Ensure MSF_PASSWORD environment variable is set correctly
- **Alternative Port**: Try port 55552 if 55553 is busy

#### 5. Camera Stream Not Loading
**Symptoms**: Camera discovered but stream shows error
**Possible Causes & Solutions**:
- **Camera Authentication**: Camera may require credentials
- **Network Access**: Verify camera is accessible
  ```bash
  ping camera-ip
  curl -I http://camera-ip:port
  ```
- **Stream Format**: Camera may use unsupported streaming format
- **Firewall**: Camera or server firewall may be blocking streams

#### 6. Permission Denied Errors
**Symptoms**: Operations fail with permission errors
**Solutions**:
- **Run as Root** (development only):
  ```bash
  sudo python3 app.py
  ```
- **Fix Service Permissions**:
  ```bash
  sudo chown -R neonhack:neonhack /opt/neonhack
  sudo chmod +x /usr/local/bin/privileged_scanner_service.py
  ```
- **Socket Permissions**:
  ```bash
  sudo chmod 666 /tmp/priv_scanner.sock
  ```

#### 7. Database Errors
**Symptoms**: Job tracking fails, database errors in console
**Solutions**:
- **Recreate Database**:
  ```bash
  rm jobs.db
  python3 -c "
  import sqlite3
  conn = sqlite3.connect('jobs.db')
  conn.executescript(open('schema.sql').read())
  conn.close()
  "
  ```
- **Fix Permissions**:
  ```bash
  chown neonhack:neonhack jobs.db
  chmod 644 jobs.db
  ```

#### 8. Interface Loading Issues
**Symptoms**: Blank page, missing animations, styling issues
**Solutions**:
- **Check Internet Connection**: Interface requires CDN resources
- **Browser Compatibility**: Use modern browser (Chrome, Firefox, Safari)
- **Clear Browser Cache**: Hard refresh with Ctrl+F5
- **Check Console**: Open browser developer tools for JavaScript errors

### Performance Issues

#### High CPU Usage
**Causes & Solutions**:
- **Matrix Animation**: Disable if needed by commenting out matrix CSS
- **Multiple Jobs**: Limit concurrent operations
- **Resource Limits**: Increase system resources

#### Memory Leaks
**Solutions**:
- **Restart Service**: `sudo systemctl restart neonhack`
- **Monitor Memory**: `htop` or `ps aux | grep python`
- **Job Cleanup**: Cancel long-running jobs

### Network Issues

#### Scanning Specific Networks
```bash
# Test network connectivity
ping -c 4 gateway-ip
traceroute target-network

# Check routing
ip route show
```

#### Firewall Configuration
```bash
# Allow NeonHack traffic (adjust as needed)
sudo ufw allow 5000/tcp
sudo ufw allow from 192.168.1.0/24

# Check iptables rules
sudo iptables -L -n -v
```

---

## Security Considerations

### 🔒 Important Security Notes

1. **Change Default API Key**: Always change the default API key before deployment
2. **Network Restrictions**: Only scan networks you own or have permission to test
3. **Firewall Configuration**: Restrict access to the web interface
4. **Regular Updates**: Keep all dependencies updated
5. **Secure Storage**: Protect configuration files and logs
6. **User Permissions**: Run with minimal required privileges
7. **Audit Logging**: Monitor all activities and access attempts

### Recommended Security Setup
```bash
# Create dedicated user
sudo useradd -r -m -s /bin/bash neonhack

# Set up firewall
sudo ufw enable
sudo ufw allow from 192.168.1.0/24 to any port 5000

# Secure file permissions
sudo chmod 700 /opt/neonhack
sudo chmod 600 /opt/neonhack/.env
```

---

## FAQ

### Q: Can I run NeonHack on Windows?
**A**: While possible with WSL (Windows Subsystem for Linux), it's recommended to use a Linux environment for full functionality.

### Q: How do I add new target networks?
**A**: Edit the `ALLOWED_SCAN_SUBNETS` list in `app.py` and restart the service.

### Q: Can multiple users access NeonHack simultaneously?
**A**: Yes, but they share the same API key and job queue. Consider implementing user authentication for production use.

### Q: How do I backup my data?
**A**: Backup the `jobs.db` file and configuration files:
```bash
cp jobs.db jobs.db.backup
tar -czf neonhack-backup.tar.gz jobs.db .env app.py
```

### Q: Can I customize the interface colors?
**A**: Yes, modify the CSS variables in the `<style>` section of the HTML files:
```css
:root {
    --primary-color: #c000ff;  /* Purple */
    --secondary-color: #ff00de; /* Pink */
}
```

### Q: How do I monitor system resources?
**A**: Use system monitoring tools:
```bash
# Monitor in real-time
htop
iotop
nethogs

# Check service status
systemctl status neonhack
journalctl -u neonhack -f
```

### Q: Can I run scans against cloud services?
**A**: Only scan cloud resources you own. Unauthorized scanning of cloud services may violate terms of service and laws.

### Q: How do I update NeonHack?
**A**: 
1. Stop the service: `sudo systemctl stop neonhack`
2. Backup your data: `cp jobs.db jobs.db.backup`
3. Replace files with new versions
4. Restart service: `sudo systemctl start neonhack`

---

## Support and Contributing

### Getting Help
- Check this troubleshooting guide first
- Review system logs: `journalctl -u neonhack`
- Check application logs in the console output
- Verify all dependencies are installed correctly

### Reporting Issues
When reporting issues, please include:
- Operating system and version
- Python version
- Complete error messages
- Steps to reproduce the problem
- System resource information (RAM, CPU)

---

## License and Legal Notice

⚠️ **IMPORTANT LEGAL DISCLAIMER**

NeonHack is intended for educational purposes and authorized penetration testing only. Users are responsible for:
- Obtaining proper authorization before scanning any networks
- Complying with all applicable laws and regulations
- Using the tool ethically and responsibly
- Understanding that unauthorized network scanning may be illegal

**USE AT YOUR OWN RISK**

---

*Last updated: 2024*
*NeonHack Version: 5.2*