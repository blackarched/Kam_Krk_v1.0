#!/bin/bash

# NeonHack Auto-Installation Script
# This script automatically installs and configures NeonHack with all dependencies
# Run with: sudo bash install.sh

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ASCII Art Header
echo -e "${PURPLE}"
cat << "EOF"
███╗   ███╗███████╗ ██████╗ ███╗   ██╗██╗  ██╗ █████╗  ██████╗██╗  ██╗
████╗ ████║██╔════╝██╔═══██╗████╗  ██║██║  ██║██╔══██╗██╔════╝██║ ██╔╝
██╔████╔██║█████╗  ██║   ██║██╔██╗ ██║███████║███████║██║     █████╔╝ 
██║╚██╔╝██║██╔══╝  ██║   ██║██║╚██╗██║██╔══██║██╔══██║██║     ██╔═██╗ 
██║ ╚═╝ ██║███████╗╚██████╔╝██║ ╚████║██║  ██║██║  ██║╚██████╗██║  ██╗
╚═╝     ╚═╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝
EOF
echo -e "${NC}"
echo -e "${CYAN}🚀 NEONHACK AUTOMATED INSTALLER${NC}"
echo -e "${YELLOW}⚡ Installing cyberpunk penetration testing suite...${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Please run as root: sudo bash install.sh${NC}"
    exit 1
fi

# Get the actual user (not root) for later use
ACTUAL_USER=${SUDO_USER:-$USER}
ACTUAL_HOME=$(eval echo ~$ACTUAL_USER)

echo -e "${BLUE}👤 Installing for user: $ACTUAL_USER${NC}"
echo -e "${BLUE}🏠 User home directory: $ACTUAL_HOME${NC}"
echo ""

# Function to print status
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to detect OS
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
    elif type lsb_release >/dev/null 2>&1; then
        OS=$(lsb_release -si)
        VER=$(lsb_release -sr)
    else
        OS=$(uname -s)
        VER=$(uname -r)
    fi
    echo -e "${BLUE}🖥️  Detected OS: $OS $VER${NC}"
}

# Detect operating system
detect_os

# Update system packages
print_info "Updating system packages..."
if command_exists apt; then
    export DEBIAN_FRONTEND=noninteractive
    apt update -y >/dev/null 2>&1
    apt upgrade -y >/dev/null 2>&1
    print_status "System packages updated (APT)"
elif command_exists dnf; then
    dnf update -y >/dev/null 2>&1
    print_status "System packages updated (DNF)"
elif command_exists yum; then
    yum update -y >/dev/null 2>&1
    print_status "System packages updated (YUM)"
else
    print_warning "Could not detect package manager, continuing..."
fi

# Install system dependencies
print_info "Installing system dependencies..."
if command_exists apt; then
    # Ubuntu/Debian
    apt install -y \
        python3 python3-pip python3-venv python3-dev \
        git curl wget unzip \
        nmap hydra metasploit-framework \
        ffmpeg libopencv-dev python3-opencv \
        build-essential libssl-dev libffi-dev \
        sqlite3 libsqlite3-dev \
        net-tools iproute2 iputils-ping \
        systemd >/dev/null 2>&1
    
    # Try to install additional tools (non-critical)
    apt install -y masscan nikto dirb gobuster 2>/dev/null || true
    
elif command_exists dnf; then
    # Fedora/CentOS 8+
    dnf install -y \
        python3 python3-pip python3-devel \
        git curl wget unzip \
        nmap hydra \
        ffmpeg opencv opencv-python3 \
        gcc openssl-devel libffi-devel \
        sqlite sqlite-devel \
        net-tools iproute iputils \
        systemd >/dev/null 2>&1
    
    # Install EPEL for additional tools
    dnf install -y epel-release 2>/dev/null || true
    dnf install -y masscan nikto 2>/dev/null || true
    
elif command_exists yum; then
    # CentOS 7/RHEL 7
    yum install -y epel-release >/dev/null 2>&1
    yum groupinstall -y "Development Tools" >/dev/null 2>&1
    yum install -y \
        python3 python3-pip python3-devel \
        git curl wget unzip \
        nmap hydra \
        ffmpeg opencv opencv-python3 \
        openssl-devel libffi-devel \
        sqlite sqlite-devel \
        net-tools iproute iputils \
        systemd >/dev/null 2>&1
fi

print_status "System dependencies installed"

# Install Metasploit if not present
if ! command_exists msfconsole; then
    print_info "Installing Metasploit Framework..."
    if command_exists apt; then
        # Add Metasploit repository
        curl -fsSL https://apt.metasploit.com/metasploit-framework.gpg.key | apt-key add - 2>/dev/null || true
        echo "deb https://apt.metasploit.com/ lucid main" > /etc/apt/sources.list.d/metasploit-framework.list 2>/dev/null || true
        apt update >/dev/null 2>&1
        apt install -y metasploit-framework >/dev/null 2>&1 || true
    fi
    
    # Alternative: Download and install manually if repository fails
    if ! command_exists msfconsole; then
        print_warning "Repository installation failed, trying manual installation..."
        cd /tmp
        wget -q https://downloads.metasploit.com/data/releases/metasploit-latest-linux-x64-installer.run 2>/dev/null || true
        if [ -f metasploit-latest-linux-x64-installer.run ]; then
            chmod +x metasploit-latest-linux-x64-installer.run
            ./metasploit-latest-linux-x64-installer.run --mode unattended --prefix /opt/metasploit >/dev/null 2>&1 || true
            ln -sf /opt/metasploit/msfconsole /usr/local/bin/msfconsole 2>/dev/null || true
        fi
    fi
fi

if command_exists msfconsole; then
    print_status "Metasploit Framework installed"
else
    print_warning "Metasploit installation failed, continuing without it"
fi

# Create neonhack user
print_info "Creating neonhack user..."
if id "neonhack" &>/dev/null; then
    print_info "User 'neonhack' already exists"
else
    useradd -r -m -s /bin/bash neonhack
    print_status "Created user 'neonhack'"
fi

# Create installation directory
INSTALL_DIR="/opt/neonhack"
print_info "Creating installation directory: $INSTALL_DIR"
mkdir -p $INSTALL_DIR
cd $INSTALL_DIR

# Copy files from current directory to installation directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
print_info "Copying NeonHack files from $SCRIPT_DIR to $INSTALL_DIR..."

# Copy all necessary files
cp "$SCRIPT_DIR"/*.py $INSTALL_DIR/ 2>/dev/null || true
cp "$SCRIPT_DIR"/*.html $INSTALL_DIR/ 2>/dev/null || true
cp "$SCRIPT_DIR"/*.sql $INSTALL_DIR/ 2>/dev/null || true
cp "$SCRIPT_DIR"/*.md $INSTALL_DIR/ 2>/dev/null || true
cp "$SCRIPT_DIR"/LICENSE $INSTALL_DIR/ 2>/dev/null || true
cp "$SCRIPT_DIR"/*.png $INSTALL_DIR/ 2>/dev/null || true

# Copy service files
if [ -d "$SCRIPT_DIR/priv_scan_srvc" ]; then
    cp -r "$SCRIPT_DIR/priv_scan_srvc" $INSTALL_DIR/
fi

print_status "Files copied to installation directory"

# Create Python virtual environment
print_info "Creating Python virtual environment..."
python3 -m venv $INSTALL_DIR/neonhack-env
source $INSTALL_DIR/neonhack-env/bin/activate

# Upgrade pip
pip install --upgrade pip >/dev/null 2>&1

# Install Python dependencies
print_info "Installing Python dependencies..."
cat > $INSTALL_DIR/requirements.txt << EOF
flask>=2.0.0
opencv-python>=4.5.0
scapy>=2.4.5
pymetasploit3>=1.0.3
psutil>=5.8.0
requests>=2.25.0
pillow>=8.0.0
numpy>=1.20.0
EOF

pip install -r $INSTALL_DIR/requirements.txt >/dev/null 2>&1
print_status "Python dependencies installed"

# Create database schema if not exists
if [ ! -f "$INSTALL_DIR/schema.sql" ]; then
    print_info "Creating database schema..."
    cat > $INSTALL_DIR/schema.sql << 'EOF'
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    owner_key TEXT NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL, -- e.g., queued, running, done, error, cancelled
    pid INTEGER,         -- To store the process ID of the task
    result TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
EOF
fi

# Initialize database
print_info "Initializing database..."
python3 -c "
import sqlite3
conn = sqlite3.connect('$INSTALL_DIR/jobs.db')
with open('$INSTALL_DIR/schema.sql', 'r') as f:
    conn.executescript(f.read())
conn.close()
print('Database initialized')
" 2>/dev/null || true
print_status "Database initialized"

# Generate secure API key
print_info "Generating secure API key..."
API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

# Create environment configuration
print_info "Creating environment configuration..."
cat > $INSTALL_DIR/.env << EOF
# NeonHack Configuration
NEONHACK_API_KEY=$API_KEY
MSF_PASSWORD=neonhack_msf_$(date +%s)
DATABASE_PATH=$INSTALL_DIR/jobs.db
PRIV_SOCKET_PATH=/tmp/priv_scanner.sock
EOF

print_status "Environment configuration created"

# Set up privileged scanner service
print_info "Setting up privileged scanner service..."

# Create privileged scanner script if not exists
if [ ! -f "$INSTALL_DIR/privileged_scanner_service.py" ]; then
    cat > $INSTALL_DIR/privileged_scanner_service.py << 'EOF'
#!/usr/bin/env python3
import socket
import json
import subprocess
import sys
import os
from scapy.all import srp, Ether, ARP
import ipaddress

def scan_network(target_cidr, interface):
    """Perform ARP scan using Scapy"""
    try:
        network = ipaddress.ip_network(target_cidr, strict=False)
        arp_request = ARP(pdst=str(network))
        broadcast = Ether(dst="ff:ff:ff:ff:ff:ff")
        arp_request_broadcast = broadcast / arp_request
        answered_list = srp(arp_request_broadcast, timeout=2, verbose=False, iface=interface)[0]
        
        devices = []
        for element in answered_list:
            device = {
                "ip": element[1].psrc,
                "mac": element[1].hwsrc
            }
            devices.append(device)
        
        return {"status": "success", "devices": devices}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def main():
    socket_path = "/tmp/priv_scanner.sock"
    
    # Remove existing socket
    try:
        os.unlink(socket_path)
    except OSError:
        pass
    
    # Create socket
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(socket_path)
    os.chmod(socket_path, 0o666)
    server.listen(5)
    
    print("Privileged scanner service listening on", socket_path)
    
    while True:
        try:
            connection, client_address = server.accept()
            data = connection.recv(4096).decode('utf-8')
            
            if data:
                request = json.loads(data)
                result = scan_network(request.get('target_cidr'), request.get('interface'))
                connection.sendall(json.dumps(result).encode('utf-8'))
            
            connection.close()
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
EOF
fi

chmod +x $INSTALL_DIR/privileged_scanner_service.py

# Copy privileged scanner to system location
cp $INSTALL_DIR/privileged_scanner_service.py /usr/local/bin/
chmod +x /usr/local/bin/privileged_scanner_service.py

# Create systemd service files
print_info "Creating systemd service files..."

# Privileged scanner socket
cat > /etc/systemd/system/priv_scanner.socket << EOF
[Unit]
Description=NeonHack Privileged Scanner Socket

[Socket]
ListenStream=/tmp/priv_scanner.sock
SocketUser=root
SocketGroup=root
SocketMode=0666

[Install]
WantedBy=sockets.target
EOF

# Privileged scanner service
cat > /etc/systemd/system/priv_scanner.service << EOF
[Unit]
Description=NeonHack Privileged Scanner Service
Requires=priv_scanner.socket

[Service]
Type=simple
ExecStart=/usr/local/bin/privileged_scanner_service.py
User=root
Group=root
StandardInput=socket
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Main NeonHack service
cat > /etc/systemd/system/neonhack.service << EOF
[Unit]
Description=NeonHack Security Testing Platform
After=network.target priv_scanner.socket
Wants=priv_scanner.socket

[Service]
Type=simple
User=neonhack
Group=neonhack
WorkingDirectory=$INSTALL_DIR
Environment=NEONHACK_API_KEY=$API_KEY
Environment=MSF_PASSWORD=neonhack_msf_$(date +%s)
Environment=PYTHONPATH=$INSTALL_DIR
ExecStart=$INSTALL_DIR/neonhack-env/bin/python $INSTALL_DIR/app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

print_status "Systemd service files created"

# Set correct ownership
print_info "Setting file permissions..."
chown -R neonhack:neonhack $INSTALL_DIR
chmod -R 755 $INSTALL_DIR
chmod 600 $INSTALL_DIR/.env
chmod +x $INSTALL_DIR/*.py 2>/dev/null || true

print_status "File permissions set"

# Initialize Metasploit database
print_info "Initializing Metasploit database..."
if command_exists msfdb; then
    msfdb init >/dev/null 2>&1 || true
    print_status "Metasploit database initialized"
else
    print_warning "Metasploit database initialization skipped (msfdb not found)"
fi

# Enable and start services
print_info "Enabling and starting services..."
systemctl daemon-reload

# Start privileged scanner
systemctl enable priv_scanner.socket >/dev/null 2>&1
systemctl start priv_scanner.socket
print_status "Privileged scanner socket started"

# Start main service
systemctl enable neonhack >/dev/null 2>&1
systemctl start neonhack
print_status "NeonHack service started"

# Configure firewall (if ufw is available)
if command_exists ufw; then
    print_info "Configuring firewall..."
    ufw allow 5000/tcp >/dev/null 2>&1 || true
    print_status "Firewall configured to allow port 5000"
fi

# Create desktop shortcut for the actual user
if [ -n "$ACTUAL_USER" ] && [ "$ACTUAL_USER" != "root" ]; then
    print_info "Creating desktop shortcut..."
    DESKTOP_DIR="$ACTUAL_HOME/Desktop"
    if [ -d "$DESKTOP_DIR" ]; then
        cat > "$DESKTOP_DIR/NeonHack.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=NeonHack
Comment=Cyberpunk Penetration Testing Suite
Exec=/usr/bin/firefox http://localhost:5000
Icon=applications-internet
Terminal=false
Categories=Network;Security;
EOF
        chown $ACTUAL_USER:$ACTUAL_USER "$DESKTOP_DIR/NeonHack.desktop"
        chmod +x "$DESKTOP_DIR/NeonHack.desktop"
        print_status "Desktop shortcut created"
    fi
fi

# Wait for service to start
print_info "Waiting for services to initialize..."
sleep 3

# Check service status
print_info "Checking service status..."
if systemctl is-active --quiet neonhack; then
    print_status "NeonHack service is running"
else
    print_warning "NeonHack service may have issues, checking logs..."
    journalctl -u neonhack --no-pager -n 5
fi

if systemctl is-active --quiet priv_scanner.socket; then
    print_status "Privileged scanner socket is active"
else
    print_warning "Privileged scanner socket may have issues"
fi

# Final status check
print_info "Performing final system check..."
ISSUES=0

# Check if port 5000 is listening
if netstat -tlnp 2>/dev/null | grep -q ":5000 "; then
    print_status "NeonHack web interface is listening on port 5000"
else
    print_error "Port 5000 is not listening"
    ISSUES=$((ISSUES + 1))
fi

# Check if socket exists
if [ -S "/tmp/priv_scanner.sock" ]; then
    print_status "Privileged scanner socket is available"
else
    print_error "Privileged scanner socket not found"
    ISSUES=$((ISSUES + 1))
fi

# Check database
if [ -f "$INSTALL_DIR/jobs.db" ]; then
    print_status "Database file exists"
else
    print_error "Database file not found"
    ISSUES=$((ISSUES + 1))
fi

# Installation complete
echo ""
echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}🎉 NEONHACK INSTALLATION COMPLETE! 🎉${NC}"
echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

if [ $ISSUES -eq 0 ]; then
    echo -e "${GREEN}✅ All systems operational!${NC}"
else
    echo -e "${YELLOW}⚠️  Installation completed with $ISSUES minor issues${NC}"
fi

echo ""
echo -e "${CYAN}🌐 Access Information:${NC}"
echo -e "   ${BLUE}Web Interface:${NC} http://localhost:5000"
echo -e "   ${BLUE}API Key:${NC}       $API_KEY"
echo ""
echo -e "${CYAN}🔧 Service Management:${NC}"
echo -e "   ${BLUE}Start:${NC}    sudo systemctl start neonhack"
echo -e "   ${BLUE}Stop:${NC}     sudo systemctl stop neonhack"
echo -e "   ${BLUE}Restart:${NC}  sudo systemctl restart neonhack"
echo -e "   ${BLUE}Status:${NC}   sudo systemctl status neonhack"
echo -e "   ${BLUE}Logs:${NC}     sudo journalctl -u neonhack -f"
echo ""
echo -e "${CYAN}📁 Installation Directory:${NC} $INSTALL_DIR"
echo -e "${CYAN}📋 Configuration File:${NC}    $INSTALL_DIR/.env"
echo -e "${CYAN}📖 Documentation:${NC}         $INSTALL_DIR/INSTALL_AND_USAGE_GUIDE.md"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT SECURITY NOTES:${NC}"
echo -e "   • Only scan networks you own or have permission to test"
echo -e "   • Change the default API key in production environments"
echo -e "   • Review firewall settings for your security requirements"
echo ""
echo -e "${GREEN}🚀 Ready to launch! Open your browser and navigate to:${NC}"
echo -e "${BLUE}   http://localhost:5000${NC}"
echo ""
echo -e "${PURPLE}Happy Hacking! 🏴‍☠️${NC}"
echo ""