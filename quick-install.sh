#!/bin/bash

# NeonHack v5.2 - One-Line Quick Installer
# Ultra-simplified installation with zero user interaction required
# Usage: curl -fsSL https://raw.githubusercontent.com/blackarched/Kam_Krk_v1.0/main/quick-install.sh | sudo bash

set -euo pipefail

# Colors
readonly G='\033[0;32m' Y='\033[1;33m' R='\033[0;31m' B='\033[0;34m' NC='\033[0m'

# Configuration
readonly REPO="https://github.com/blackarched/Kam_Krk_v1.0"
readonly BRANCH="cursor/enhance-dashboard-gui-and-background-display-d831"
readonly INSTALL_DIR="/opt/neonhack"
readonly USER="neonhack"
readonly PORT="5000"

# Logging
log() { echo -e "${1}"; }
info() { log "${B}[INFO]${NC} ${1}"; }
ok() { log "${G}[OK]${NC} ${1}"; }
warn() { log "${Y}[WARN]${NC} ${1}"; }
err() { log "${R}[ERROR]${NC} ${1}"; exit 1; }

# Header
echo -e "${G}"
cat << 'EOF'
 ███╗   ██╗███████╗ ██████╗ ███╗   ██╗██╗  ██╗ █████╗  ██████╗██╗  ██╗
 ████╗  ██║██╔════╝██╔═══██╗████╗  ██║██║  ██║██╔══██╗██╔════╝██║ ██╔╝
 ██╔██╗ ██║█████╗  ██║   ██║██╔██╗ ██║███████║███████║██║     █████╔╝ 
 ██║╚██╗██║██╔══╝  ██║   ██║██║╚██╗██║██╔══██║██╔══██║██║     ██╔═██╗ 
 ██║ ╚████║███████╗╚██████╔╝██║ ╚████║██║  ██║██║  ██║╚██████╗██║  ██╗
 ╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝
EOF
echo -e "${NC}"
info "🚀 NeonHack v5.2 - Quick Install Starting..."

# Check root
[[ $EUID -eq 0 ]] || err "Run as root: sudo bash quick-install.sh"

# Get actual user
ACTUAL_USER="${SUDO_USER:-$USER}"
info "Installing for user: $ACTUAL_USER"

# Stop existing services
systemctl stop neonhack priv_scanner.socket &>/dev/null || true

# Install system packages
info "📦 Installing system dependencies..."
export DEBIAN_FRONTEND=noninteractive
if command -v apt >/dev/null; then
    apt update -qq &>/dev/null
    apt install -y python3 python3-pip python3-venv git curl wget nmap hydra sqlite3 \
        build-essential libssl-dev libffi-dev libopencv-dev systemd net-tools &>/dev/null
elif command -v dnf >/dev/null; then
    dnf install -y python3 python3-pip git curl wget nmap hydra sqlite \
        gcc openssl-devel libffi-devel opencv systemd net-tools &>/dev/null
else
    warn "Unsupported package manager, continuing..."
fi

# Create user
id "$USER" &>/dev/null || useradd -r -m -s /bin/bash "$USER"

# Setup installation directory
info "📁 Setting up installation directory..."
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Download NeonHack
info "⬇️ Downloading NeonHack..."
git clone -b "$BRANCH" "$REPO" . &>/dev/null || err "Failed to download NeonHack"

# Setup Python environment
info "🐍 Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip &>/dev/null
pip install -r requirements.txt &>/dev/null

# Generate secure API key
API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

# Create configuration
info "⚙️ Creating configuration..."
cat > .env << EOF
NEONHACK_API_KEY=$API_KEY
MSF_PASSWORD=msf_$(date +%s)
DATABASE_PATH=$INSTALL_DIR/jobs.db
PRIV_SOCKET_PATH=/tmp/priv_scanner.sock
FLASK_HOST=0.0.0.0
FLASK_PORT=$PORT
EOF

# Initialize database
info "🗄️ Initializing database..."
python3 << EOF
import sqlite3
conn = sqlite3.connect('jobs.db')
with open('schema.sql', 'r') as f:
    conn.executescript(f.read())
conn.close()
EOF

# Create systemd services
info "🔧 Creating systemd services..."

# Privileged scanner socket
cat > /etc/systemd/system/priv_scanner.socket << EOF
[Unit]
Description=NeonHack Privileged Scanner Socket

[Socket]
ListenStream=/tmp/priv_scanner.sock
SocketUser=root
SocketGroup=$USER
SocketMode=0660

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
User=root
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/privileged_scanner_service.py
StandardInput=socket
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# Main NeonHack service
cat > /etc/systemd/system/neonhack.service << EOF
[Unit]
Description=NeonHack Cyberpunk Penetration Testing Platform
After=network.target priv_scanner.socket

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Set permissions
chown -R "$USER:$USER" "$INSTALL_DIR"
chmod 600 .env
chmod +x *.py &>/dev/null || true

# Start services
info "🚀 Starting services..."
systemctl daemon-reload
systemctl enable --now priv_scanner.socket neonhack &>/dev/null

# Configure firewall
if command -v ufw >/dev/null; then
    ufw allow "$PORT/tcp" &>/dev/null || true
fi

# Create launcher
cat > /usr/local/bin/neonhack << EOF
#!/bin/bash
case "\$1" in
    start) systemctl start neonhack priv_scanner.socket; echo "Started: http://localhost:$PORT" ;;
    stop) systemctl stop neonhack priv_scanner.socket; echo "Stopped" ;;
    restart) systemctl restart neonhack priv_scanner.socket; echo "Restarted: http://localhost:$PORT" ;;
    status) systemctl status neonhack ;;
    logs) journalctl -u neonhack -f ;;
    key) grep NEONHACK_API_KEY $INSTALL_DIR/.env | cut -d'=' -f2 ;;
    open) python3 -m webbrowser http://localhost:$PORT &>/dev/null || echo "Open: http://localhost:$PORT" ;;
    *) echo "Usage: neonhack {start|stop|restart|status|logs|key|open}"; echo "Web: http://localhost:$PORT" ;;
esac
EOF
chmod +x /usr/local/bin/neonhack

# Wait for startup
sleep 3

# Validation
info "✅ Validating installation..."
ISSUES=0
systemctl is-active --quiet neonhack || { warn "NeonHack service not running"; ISSUES=$((ISSUES+1)); }
systemctl is-active --quiet priv_scanner.socket || { warn "Scanner socket not active"; ISSUES=$((ISSUES+1)); }
[[ -f "$INSTALL_DIR/jobs.db" ]] || { warn "Database not found"; ISSUES=$((ISSUES+1)); }

# Completion
echo
if [[ $ISSUES -eq 0 ]]; then
    ok "🎉 Installation completed successfully!"
else
    warn "⚠️ Installation completed with $ISSUES issues"
fi

echo -e "${G}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${B}🌐 Web Interface: ${G}http://localhost:$PORT${NC}"
echo -e "${B}🔑 API Key: ${Y}$API_KEY${NC}"
echo -e "${B}🚀 Quick Commands:${NC}"
echo -e "   ${Y}neonhack open${NC}    - Open web interface"
echo -e "   ${Y}neonhack status${NC}  - Check status"
echo -e "   ${Y}neonhack logs${NC}    - View logs"
echo -e "${G}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Try to open browser
if [[ "$ACTUAL_USER" != "root" ]]; then
    sudo -u "$ACTUAL_USER" python3 -m webbrowser "http://localhost:$PORT" &>/dev/null || true
fi

ok "🏴‍☠️ Happy Hacking!"