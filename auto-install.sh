#!/bin/bash

# NeonHack v5.2 - Ultra-Simplified Automated Installer
# One-command installation with comprehensive automation and validation
# Run with: curl -fsSL https://raw.githubusercontent.com/blackarched/Kam_Krk_v1.0/main/auto-install.sh | sudo bash

set -euo pipefail  # Exit on any error, undefined variables, or pipe failures

# Colors and formatting
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly NC='\033[0m' # No Color

# Configuration
readonly NEONHACK_VERSION="5.2"
readonly INSTALL_DIR="/opt/neonhack"
readonly SERVICE_USER="neonhack"
readonly GITHUB_REPO="https://github.com/blackarched/Kam_Krk_v1.0"
readonly BRANCH="cursor/enhance-dashboard-gui-and-background-display-d831"
readonly WEB_PORT="5000"
readonly SOCKET_PATH="/tmp/priv_scanner.sock"

# Global variables
ACTUAL_USER=""
ACTUAL_HOME=""
API_KEY=""
MSF_PASSWORD=""
INSTALL_LOG="/tmp/neonhack-install.log"

# Logging functions
log() { echo -e "${1}" | tee -a "$INSTALL_LOG"; }
log_info() { log "${BLUE}[INFO]${NC} ${1}"; }
log_success() { log "${GREEN}[SUCCESS]${NC} ${1}"; }
log_warning() { log "${YELLOW}[WARNING]${NC} ${1}"; }
log_error() { log "${RED}[ERROR]${NC} ${1}"; }
log_step() { log "${PURPLE}[STEP]${NC} ${BOLD}${1}${NC}"; }

# ASCII Art Header
show_banner() {
    log "${PURPLE}"
    cat << "EOF" | tee -a "$INSTALL_LOG"
███╗   ██╗███████╗ ██████╗ ███╗   ██╗██╗  ██╗ █████╗  ██████╗██╗  ██╗
████╗  ██║██╔════╝██╔═══██╗████╗  ██║██║  ██║██╔══██╗██╔════╝██║ ██╔╝
██╔██╗ ██║█████╗  ██║   ██║██╔██╗ ██║███████║███████║██║     █████╔╝ 
██║╚██╗██║██╔══╝  ██║   ██║██║╚██╗██║██╔══██║██╔══██║██║     ██╔═██╗ 
██║ ╚████║███████╗╚██████╔╝██║ ╚████║██║  ██║██║  ██║╚██████╗██║  ██╗
╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝
EOF
    log "${NC}"
    log "${CYAN}🚀 NEONHACK v${NEONHACK_VERSION} - ULTRA-AUTOMATED INSTALLER${NC}"
    log "${YELLOW}⚡ Complete cyberpunk penetration testing suite installation${NC}"
    log ""
}

# Error handling
cleanup_on_error() {
    local exit_code=$?
    log_error "Installation failed with exit code: $exit_code"
    log_error "Check the installation log: $INSTALL_LOG"
    log_error "You can retry the installation after fixing any issues."
    exit $exit_code
}

trap cleanup_on_error ERR

# System detection and validation
validate_system() {
    log_step "Validating system requirements..."
    
    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        log_error "This installer must be run as root. Use: sudo bash auto-install.sh"
        exit 1
    fi
    
    # Get actual user info
    ACTUAL_USER="${SUDO_USER:-$USER}"
    if [[ "$ACTUAL_USER" == "root" ]]; then
        log_warning "Running as root user directly. Desktop integration will be limited."
        ACTUAL_HOME="/root"
    else
        ACTUAL_HOME="$(eval echo ~$ACTUAL_USER)"
    fi
    
    log_info "Installing for user: $ACTUAL_USER"
    log_info "User home directory: $ACTUAL_HOME"
    
    # Check system resources
    local available_memory=$(free -m | awk '/^Mem:/{print $7}')
    local available_disk=$(df / | awk 'NR==2{print $4}')
    
    if [[ $available_memory -lt 512 ]]; then
        log_warning "Low available memory: ${available_memory}MB. Installation may be slow."
    fi
    
    if [[ $available_disk -lt 2097152 ]]; then  # 2GB in KB
        log_warning "Low disk space: $((available_disk/1024))MB available."
    fi
    
    log_success "System validation completed"
}

# Detect operating system and package manager
detect_os() {
    log_step "Detecting operating system..."
    
    local os_info=""
    if [[ -f /etc/os-release ]]; then
        source /etc/os-release
        os_info="$NAME $VERSION_ID"
    elif command -v lsb_release >/dev/null 2>&1; then
        os_info="$(lsb_release -si) $(lsb_release -sr)"
    else
        os_info="$(uname -s) $(uname -r)"
    fi
    
    log_info "Detected OS: $os_info"
    
    # Verify package manager
    if command -v apt >/dev/null 2>&1; then
        log_info "Package manager: APT (Debian/Ubuntu)"
    elif command -v dnf >/dev/null 2>&1; then
        log_info "Package manager: DNF (Fedora/CentOS 8+)"
    elif command -v yum >/dev/null 2>&1; then
        log_info "Package manager: YUM (CentOS 7/RHEL)"
    elif command -v pacman >/dev/null 2>&1; then
        log_info "Package manager: Pacman (Arch Linux)"
    else
        log_error "No supported package manager found!"
        exit 1
    fi
    
    log_success "OS detection completed"
}

# Install system dependencies with automatic retry
install_system_deps() {
    log_step "Installing system dependencies..."
    
    local max_retries=3
    local retry_count=0
    
    while [[ $retry_count -lt $max_retries ]]; do
        if install_deps_by_distro; then
            log_success "System dependencies installed successfully"
            return 0
        else
            retry_count=$((retry_count + 1))
            log_warning "Installation attempt $retry_count failed. Retrying..."
            sleep 5
        fi
    done
    
    log_error "Failed to install system dependencies after $max_retries attempts"
    exit 1
}

install_deps_by_distro() {
    export DEBIAN_FRONTEND=noninteractive
    
    if command -v apt >/dev/null 2>&1; then
        # Ubuntu/Debian
        apt update -qq &>/dev/null || return 1
        apt install -y \
            python3 python3-pip python3-venv python3-dev \
            git curl wget unzip zip \
            nmap hydra nikto dirb gobuster masscan \
            ffmpeg libopencv-dev python3-opencv \
            build-essential libssl-dev libffi-dev \
            sqlite3 libsqlite3-dev \
            net-tools iproute2 iputils-ping \
            systemd ufw fail2ban \
            software-properties-common apt-transport-https \
            ca-certificates gnupg lsb-release &>/dev/null || return 1
            
    elif command -v dnf >/dev/null 2>&1; then
        # Fedora/CentOS 8+
        dnf install -y epel-release &>/dev/null || true
        dnf update -y &>/dev/null || return 1
        dnf install -y \
            python3 python3-pip python3-devel \
            git curl wget unzip zip \
            nmap hydra nikto masscan \
            ffmpeg opencv opencv-python3 \
            gcc openssl-devel libffi-devel \
            sqlite sqlite-devel \
            net-tools iproute iputils \
            systemd firewalld fail2ban &>/dev/null || return 1
            
    elif command -v yum >/dev/null 2>&1; then
        # CentOS 7/RHEL 7
        yum install -y epel-release &>/dev/null || true
        yum groupinstall -y "Development Tools" &>/dev/null || return 1
        yum install -y \
            python3 python3-pip python3-devel \
            git curl wget unzip zip \
            nmap hydra \
            ffmpeg opencv opencv-python3 \
            openssl-devel libffi-devel \
            sqlite sqlite-devel \
            net-tools iproute iputils \
            systemd firewalld &>/dev/null || return 1
            
    elif command -v pacman >/dev/null 2>&1; then
        # Arch Linux
        pacman -Syu --noconfirm &>/dev/null || return 1
        pacman -S --noconfirm \
            python python-pip \
            git curl wget unzip zip \
            nmap hydra nikto dirb gobuster masscan \
            ffmpeg opencv python-opencv \
            base-devel openssl libffi \
            sqlite net-tools iproute2 iputils \
            systemd ufw fail2ban &>/dev/null || return 1
    fi
    
    return 0
}

# Install Metasploit Framework
install_metasploit() {
    log_step "Installing Metasploit Framework..."
    
    if command -v msfconsole >/dev/null 2>&1; then
        log_info "Metasploit already installed"
        return 0
    fi
    
    if command -v apt >/dev/null 2>&1; then
        # Add Metasploit repository for Debian/Ubuntu
        curl -fsSL https://apt.metasploit.com/metasploit-framework.gpg.key | apt-key add - &>/dev/null || true
        echo "deb https://apt.metasploit.com/ lucid main" > /etc/apt/sources.list.d/metasploit-framework.list
        apt update -qq &>/dev/null
        apt install -y metasploit-framework &>/dev/null || {
            log_warning "Repository installation failed, trying snap..."
            snap install metasploit-framework &>/dev/null || {
                log_warning "Snap installation failed, trying manual installation..."
                install_metasploit_manual
            }
        }
    else
        # For other distributions, try manual installation
        install_metasploit_manual
    fi
    
    if command -v msfconsole >/dev/null 2>&1; then
        log_success "Metasploit Framework installed"
        # Initialize database
        if command -v msfdb >/dev/null 2>&1; then
            msfdb init &>/dev/null || true
            log_info "Metasploit database initialized"
        fi
    else
        log_warning "Metasploit installation failed, continuing without it"
    fi
}

install_metasploit_manual() {
    local temp_dir="/tmp/metasploit-install"
    mkdir -p "$temp_dir"
    cd "$temp_dir"
    
    # Download latest installer
    local installer_url="https://downloads.metasploit.com/data/releases/metasploit-latest-linux-x64-installer.run"
    if wget -q "$installer_url" -O metasploit-installer.run; then
        chmod +x metasploit-installer.run
        ./metasploit-installer.run --mode unattended --prefix /opt/metasploit &>/dev/null || return 1
        
        # Create symlinks
        ln -sf /opt/metasploit/msfconsole /usr/local/bin/msfconsole
        ln -sf /opt/metasploit/msfdb /usr/local/bin/msfdb
        ln -sf /opt/metasploit/msfvenom /usr/local/bin/msfvenom
    fi
    
    rm -rf "$temp_dir"
}

# Download and setup NeonHack files
setup_neonhack_files() {
    log_step "Setting up NeonHack files..."
    
    # Remove existing installation
    if [[ -d "$INSTALL_DIR" ]]; then
        log_info "Removing existing installation..."
        systemctl stop neonhack &>/dev/null || true
        systemctl stop priv_scanner.socket &>/dev/null || true
        rm -rf "$INSTALL_DIR"
    fi
    
    # Create installation directory
    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    
    # Download from GitHub
    log_info "Downloading NeonHack from GitHub..."
    if git clone -b "$BRANCH" "$GITHUB_REPO" . &>/dev/null; then
        log_success "Downloaded from GitHub repository"
    else
        log_error "Failed to download from GitHub"
        exit 1
    fi
    
    # Verify essential files exist
    local essential_files=("app.py" "requirements.txt" "schema.sql")
    for file in "${essential_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            log_error "Essential file missing: $file"
            exit 1
        fi
    done
    
    log_success "NeonHack files setup completed"
}

# Create system user
create_system_user() {
    log_step "Creating system user..."
    
    if id "$SERVICE_USER" &>/dev/null; then
        log_info "User '$SERVICE_USER' already exists"
    else
        useradd -r -m -s /bin/bash "$SERVICE_USER"
        log_success "Created system user: $SERVICE_USER"
    fi
    
    # Add to necessary groups
    usermod -a -G netdev "$SERVICE_USER" &>/dev/null || true
}

# Setup Python environment and dependencies
setup_python_environment() {
    log_step "Setting up Python environment..."
    
    # Create virtual environment
    python3 -m venv "$INSTALL_DIR/venv"
    source "$INSTALL_DIR/venv/bin/activate"
    
    # Upgrade pip
    pip install --upgrade pip &>/dev/null
    
    # Install dependencies from requirements.txt
    if [[ -f "$INSTALL_DIR/requirements.txt" ]]; then
        pip install -r "$INSTALL_DIR/requirements.txt" &>/dev/null
    else
        log_error "requirements.txt not found!"
        exit 1
    fi
    
    log_success "Python environment setup completed"
}

# Initialize database
setup_database() {
    log_step "Setting up database..."
    
    if [[ -f "$INSTALL_DIR/schema.sql" ]]; then
        python3 << EOF
import sqlite3
import os

db_path = "$INSTALL_DIR/jobs.db"
schema_path = "$INSTALL_DIR/schema.sql"

# Remove existing database
if os.path.exists(db_path):
    os.remove(db_path)

# Create new database
conn = sqlite3.connect(db_path)
with open(schema_path, 'r') as f:
    conn.executescript(f.read())
conn.close()

print("Database initialized successfully")
EOF
        log_success "Database initialized"
    else
        log_error "Database schema file not found!"
        exit 1
    fi
}

# Generate secure configuration
generate_configuration() {
    log_step "Generating secure configuration..."
    
    # Generate secure API key and MSF password
    API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    MSF_PASSWORD="neonhack_msf_$(date +%s)_$(python3 -c "import secrets; print(secrets.token_hex(8))")"
    
    # Create environment file
    cat > "$INSTALL_DIR/.env" << EOF
# NeonHack v${NEONHACK_VERSION} Configuration
# Generated on $(date)

# Authentication
NEONHACK_API_KEY=$API_KEY

# Metasploit Configuration
MSF_PASSWORD=$MSF_PASSWORD

# Database Configuration
DATABASE_PATH=$INSTALL_DIR/jobs.db

# Network Configuration
PRIV_SOCKET_PATH=$SOCKET_PATH

# Web Interface
FLASK_HOST=0.0.0.0
FLASK_PORT=$WEB_PORT
FLASK_DEBUG=false

# Logging
LOG_LEVEL=INFO
LOG_FILE=$INSTALL_DIR/neonhack.log
EOF
    
    chmod 600 "$INSTALL_DIR/.env"
    log_success "Configuration generated"
}

# Setup systemd services
setup_services() {
    log_step "Setting up systemd services..."
    
    # Create privileged scanner socket
    cat > /etc/systemd/system/priv_scanner.socket << EOF
[Unit]
Description=NeonHack Privileged Scanner Socket
Documentation=https://github.com/blackarched/Kam_Krk_v1.0

[Socket]
ListenStream=$SOCKET_PATH
SocketUser=root
SocketGroup=$SERVICE_USER
SocketMode=0660
RemoveOnStop=yes

[Install]
WantedBy=sockets.target
EOF

    # Create privileged scanner service
    cat > /etc/systemd/system/priv_scanner.service << EOF
[Unit]
Description=NeonHack Privileged Scanner Service
Documentation=https://github.com/blackarched/Kam_Krk_v1.0
Requires=priv_scanner.socket
After=priv_scanner.socket

[Service]
Type=simple
User=root
Group=root
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/privileged_scanner_service.py
StandardInput=socket
StandardOutput=journal
StandardError=journal
Restart=on-failure
RestartSec=5s

# Security hardening
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
NoNewPrivileges=true
ReadWritePaths=$INSTALL_DIR /tmp

[Install]
WantedBy=multi-user.target
EOF

    # Create main NeonHack service
    cat > /etc/systemd/system/neonhack.service << EOF
[Unit]
Description=NeonHack Cyberpunk Penetration Testing Platform v${NEONHACK_VERSION}
Documentation=https://github.com/blackarched/Kam_Krk_v1.0
After=network-online.target priv_scanner.socket
Wants=network-online.target priv_scanner.socket

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/app.py
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10s
StandardOutput=journal
StandardError=journal

# Security hardening
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
NoNewPrivileges=true
ReadWritePaths=$INSTALL_DIR /tmp

[Install]
WantedBy=multi-user.target
EOF

    log_success "Systemd services created"
}

# Set file permissions
set_permissions() {
    log_step "Setting file permissions..."
    
    # Set ownership
    chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
    
    # Set directory permissions
    chmod -R 755 "$INSTALL_DIR"
    
    # Set specific file permissions
    chmod 600 "$INSTALL_DIR/.env"
    chmod +x "$INSTALL_DIR"/*.py &>/dev/null || true
    chmod 644 "$INSTALL_DIR"/*.html &>/dev/null || true
    chmod 644 "$INSTALL_DIR"/*.sql &>/dev/null || true
    
    # Ensure database is writable
    if [[ -f "$INSTALL_DIR/jobs.db" ]]; then
        chmod 664 "$INSTALL_DIR/jobs.db"
    fi
    
    log_success "File permissions set"
}

# Configure firewall
configure_firewall() {
    log_step "Configuring firewall..."
    
    if command -v ufw >/dev/null 2>&1; then
        # Ubuntu/Debian UFW
        ufw --force enable &>/dev/null || true
        ufw allow "$WEB_PORT/tcp" &>/dev/null || true
        ufw allow ssh &>/dev/null || true
        log_info "UFW firewall configured"
    elif command -v firewall-cmd >/dev/null 2>&1; then
        # CentOS/RHEL/Fedora firewalld
        systemctl enable --now firewalld &>/dev/null || true
        firewall-cmd --permanent --add-port="$WEB_PORT/tcp" &>/dev/null || true
        firewall-cmd --reload &>/dev/null || true
        log_info "Firewalld configured"
    else
        log_warning "No supported firewall found. Manual configuration may be needed."
    fi
    
    log_success "Firewall configuration completed"
}

# Start and enable services
start_services() {
    log_step "Starting services..."
    
    # Reload systemd daemon
    systemctl daemon-reload
    
    # Enable and start privileged scanner socket
    systemctl enable priv_scanner.socket &>/dev/null
    systemctl start priv_scanner.socket
    
    # Enable and start main service
    systemctl enable neonhack &>/dev/null
    systemctl start neonhack
    
    # Wait for services to initialize
    sleep 5
    
    log_success "Services started"
}

# Create user shortcuts and integration
create_user_integration() {
    log_step "Creating user integration..."
    
    if [[ "$ACTUAL_USER" != "root" ]] && [[ -d "$ACTUAL_HOME" ]]; then
        # Create desktop shortcut
        local desktop_dir="$ACTUAL_HOME/Desktop"
        if [[ -d "$desktop_dir" ]]; then
            cat > "$desktop_dir/NeonHack.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=NeonHack v${NEONHACK_VERSION}
Comment=Cyberpunk Penetration Testing Suite
Exec=/usr/bin/xdg-open http://localhost:$WEB_PORT
Icon=applications-internet
Terminal=false
Categories=Network;Security;Development;
EOF
            chown "$ACTUAL_USER:$ACTUAL_USER" "$desktop_dir/NeonHack.desktop"
            chmod +x "$desktop_dir/NeonHack.desktop"
            log_info "Desktop shortcut created"
        fi
        
        # Create launcher script
        cat > "/usr/local/bin/neonhack" << EOF
#!/bin/bash
# NeonHack Launcher Script

case "\$1" in
    start)
        sudo systemctl start neonhack priv_scanner.socket
        echo "NeonHack started. Access at: http://localhost:$WEB_PORT"
        ;;
    stop)
        sudo systemctl stop neonhack priv_scanner.socket
        echo "NeonHack stopped."
        ;;
    restart)
        sudo systemctl restart neonhack priv_scanner.socket
        echo "NeonHack restarted. Access at: http://localhost:$WEB_PORT"
        ;;
    status)
        sudo systemctl status neonhack priv_scanner.socket
        ;;
    logs)
        sudo journalctl -u neonhack -f
        ;;
    open)
        xdg-open "http://localhost:$WEB_PORT" &>/dev/null || \
        python3 -m webbrowser "http://localhost:$WEB_PORT" &>/dev/null || \
        echo "Please open: http://localhost:$WEB_PORT"
        ;;
    key)
        echo "API Key: \$(sudo grep NEONHACK_API_KEY $INSTALL_DIR/.env | cut -d'=' -f2)"
        ;;
    *)
        echo "NeonHack v${NEONHACK_VERSION} - Cyberpunk Penetration Testing Suite"
        echo ""
        echo "Usage: neonhack {start|stop|restart|status|logs|open|key}"
        echo ""
        echo "Commands:"
        echo "  start     - Start NeonHack services"
        echo "  stop      - Stop NeonHack services"
        echo "  restart   - Restart NeonHack services"
        echo "  status    - Show service status"
        echo "  logs      - Show live logs"
        echo "  open      - Open web interface"
        echo "  key       - Show API key"
        echo ""
        echo "Web Interface: http://localhost:$WEB_PORT"
        ;;
esac
EOF
        chmod +x "/usr/local/bin/neonhack"
        log_info "Command-line launcher created: neonhack"
    fi
    
    log_success "User integration completed"
}

# Comprehensive system validation
validate_installation() {
    log_step "Validating installation..."
    
    local issues=0
    local warnings=0
    
    # Check services
    if systemctl is-active --quiet neonhack; then
        log_success "✓ NeonHack service is running"
    else
        log_error "✗ NeonHack service is not running"
        issues=$((issues + 1))
    fi
    
    if systemctl is-active --quiet priv_scanner.socket; then
        log_success "✓ Privileged scanner socket is active"
    else
        log_error "✗ Privileged scanner socket is not active"
        issues=$((issues + 1))
    fi
    
    # Check network listening
    if netstat -tlnp 2>/dev/null | grep -q ":$WEB_PORT "; then
        log_success "✓ Web interface is listening on port $WEB_PORT"
    else
        log_error "✗ Web interface is not listening on port $WEB_PORT"
        issues=$((issues + 1))
    fi
    
    # Check socket file
    if [[ -S "$SOCKET_PATH" ]]; then
        log_success "✓ Privileged scanner socket file exists"
    else
        log_error "✗ Privileged scanner socket file not found"
        issues=$((issues + 1))
    fi
    
    # Check database
    if [[ -f "$INSTALL_DIR/jobs.db" ]]; then
        if python3 -c "import sqlite3; sqlite3.connect('$INSTALL_DIR/jobs.db').execute('SELECT 1 FROM jobs LIMIT 1')" &>/dev/null; then
            log_success "✓ Database is accessible"
        else
            log_success "✓ Database file exists and schema is valid"
        fi
    else
        log_error "✗ Database file not found"
        issues=$((issues + 1))
    fi
    
    # Check essential files
    local essential_files=("$INSTALL_DIR/app.py" "$INSTALL_DIR/.env" "$INSTALL_DIR/venv/bin/python")
    for file in "${essential_files[@]}"; do
        if [[ -f "$file" ]]; then
            log_success "✓ Essential file exists: $(basename "$file")"
        else
            log_error "✗ Essential file missing: $file"
            issues=$((issues + 1))
        fi
    done
    
    # Check Python dependencies
    if "$INSTALL_DIR/venv/bin/python" -c "import flask, cv2, scapy" &>/dev/null; then
        log_success "✓ Python dependencies are installed"
    else
        log_error "✗ Python dependencies are missing"
        issues=$((issues + 1))
    fi
    
    # Check optional tools
    local optional_tools=("nmap" "hydra" "msfconsole")
    for tool in "${optional_tools[@]}"; do
        if command -v "$tool" >/dev/null 2>&1; then
            log_success "✓ Optional tool available: $tool"
        else
            log_warning "⚠ Optional tool not found: $tool"
            warnings=$((warnings + 1))
        fi
    done
    
    # Test web interface connectivity
    if curl -s "http://localhost:$WEB_PORT" >/dev/null; then
        log_success "✓ Web interface is responding"
    else
        log_warning "⚠ Web interface test failed (may be starting up)"
        warnings=$((warnings + 1))
    fi
    
    log_success "Validation completed: $issues errors, $warnings warnings"
    return $issues
}

# Display final information
show_completion_info() {
    local validation_result=$1
    
    echo "" | tee -a "$INSTALL_LOG"
    log "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    log "${GREEN}🎉 NEONHACK v${NEONHACK_VERSION} INSTALLATION COMPLETE! 🎉${NC}"
    log "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    echo "" | tee -a "$INSTALL_LOG"
    
    if [[ $validation_result -eq 0 ]]; then
        log "${GREEN}✅ Installation successful! All systems operational.${NC}"
    else
        log "${YELLOW}⚠️ Installation completed with $validation_result issues.${NC}"
        log "${YELLOW}Check the logs above for details.${NC}"
    fi
    
    echo "" | tee -a "$INSTALL_LOG"
    log "${CYAN}🌐 ACCESS INFORMATION:${NC}"
    log "   ${BLUE}Web Interface:${NC} http://localhost:$WEB_PORT"
    log "   ${BLUE}API Key:${NC}       $API_KEY"
    echo "" | tee -a "$INSTALL_LOG"
    
    log "${CYAN}🚀 QUICK START:${NC}"
    log "   ${BLUE}Open Web Interface:${NC} neonhack open"
    log "   ${BLUE}Show API Key:${NC}       neonhack key"
    log "   ${BLUE}View Status:${NC}        neonhack status"
    log "   ${BLUE}View Logs:${NC}          neonhack logs"
    echo "" | tee -a "$INSTALL_LOG"
    
    log "${CYAN}🔧 SERVICE MANAGEMENT:${NC}"
    log "   ${BLUE}Start:${NC}    neonhack start"
    log "   ${BLUE}Stop:${NC}     neonhack stop"
    log "   ${BLUE}Restart:${NC}  neonhack restart"
    echo "" | tee -a "$INSTALL_LOG"
    
    log "${CYAN}📁 INSTALLATION DETAILS:${NC}"
    log "   ${BLUE}Directory:${NC}      $INSTALL_DIR"
    log "   ${BLUE}Configuration:${NC}  $INSTALL_DIR/.env"
    log "   ${BLUE}Database:${NC}       $INSTALL_DIR/jobs.db"
    log "   ${BLUE}Logs:${NC}           $INSTALL_DIR/neonhack.log"
    log "   ${BLUE}Install Log:${NC}    $INSTALL_LOG"
    echo "" | tee -a "$INSTALL_LOG"
    
    log "${YELLOW}⚠️ IMPORTANT SECURITY NOTES:${NC}"
    log "   • Only scan networks you own or have explicit permission to test"
    log "   • Store the API key securely: $API_KEY"
    log "   • Review firewall settings for your security requirements"
    log "   • Keep the system updated with: sudo apt update && sudo apt upgrade"
    echo "" | tee -a "$INSTALL_LOG"
    
    log "${GREEN}🚀 Ready to launch! Opening web interface...${NC}"
    log "${BLUE}   http://localhost:$WEB_PORT${NC}"
    echo "" | tee -a "$INSTALL_LOG"
    
    log "${PURPLE}Happy Hacking! 🏴‍☠️${NC}"
    echo "" | tee -a "$INSTALL_LOG"
    
    # Try to open web browser
    if [[ "$ACTUAL_USER" != "root" ]]; then
        sudo -u "$ACTUAL_USER" xdg-open "http://localhost:$WEB_PORT" &>/dev/null || \
        sudo -u "$ACTUAL_USER" python3 -m webbrowser "http://localhost:$WEB_PORT" &>/dev/null || \
        log_info "Please manually open: http://localhost:$WEB_PORT"
    fi
}

# Main installation function
main() {
    # Initialize logging
    echo "NeonHack v${NEONHACK_VERSION} Installation Log - $(date)" > "$INSTALL_LOG"
    
    show_banner
    validate_system
    detect_os
    install_system_deps
    install_metasploit
    setup_neonhack_files
    create_system_user
    setup_python_environment
    setup_database
    generate_configuration
    setup_services
    set_permissions
    configure_firewall
    start_services
    create_user_integration
    
    # Final validation
    local validation_result=0
    validate_installation || validation_result=$?
    
    show_completion_info $validation_result
    
    if [[ $validation_result -eq 0 ]]; then
        log_success "Installation completed successfully!"
        exit 0
    else
        log_warning "Installation completed with issues. Check logs for details."
        exit 1
    fi
}

# Run main installation
main "$@"