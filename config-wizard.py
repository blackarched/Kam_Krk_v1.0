#!/usr/bin/env python3
"""
NeonHack v5.2 - Interactive Configuration Wizard
Simplifies and automates the configuration process with intelligent defaults
"""

import os
import sys
import json
import secrets
import ipaddress
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any

# Color codes for terminal output
class Colors:
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    BOLD = '\033[1m'
    NC = '\033[0m'  # No Color

class ConfigWizard:
    def __init__(self):
        self.install_dir = Path("/opt/neonhack")
        self.config_file = self.install_dir / ".env"
        self.app_config_file = self.install_dir / "app.py"
        self.config = {}
        self.networks = []
        
    def print_banner(self):
        """Display the NeonHack banner"""
        print(f"{Colors.PURPLE}")
        print("""
███╗   ██╗███████╗ ██████╗ ███╗   ██╗██╗  ██╗ █████╗  ██████╗██╗  ██╗
████╗  ██║██╔════╝██╔═══██╗████╗  ██║██║  ██║██╔══██╗██╔════╝██║ ██╔╝
██╔██╗ ██║█████╗  ██║   ██║██╔██╗ ██║███████║███████║██║     █████╔╝ 
██║╚██╗██║██╔══╝  ██║   ██║██║╚██╗██║██╔══██║██╔══██║██║     ██╔═██╗ 
██║ ╚████║███████╗╚██████╔╝██║ ╚████║██║  ██║██║  ██║╚██████╗██║  ██╗
╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝
        """)
        print(f"{Colors.NC}")
        print(f"{Colors.CYAN}🔧 NeonHack v5.2 - Configuration Wizard{Colors.NC}")
        print(f"{Colors.YELLOW}⚙️ Intelligent configuration with security best practices{Colors.NC}")
        print()

    def log(self, message: str, color: str = Colors.NC):
        """Print a colored log message"""
        print(f"{color}{message}{Colors.NC}")

    def success(self, message: str):
        """Print a success message"""
        self.log(f"✅ {message}", Colors.GREEN)

    def info(self, message: str):
        """Print an info message"""
        self.log(f"ℹ️  {message}", Colors.BLUE)

    def warning(self, message: str):
        """Print a warning message"""
        self.log(f"⚠️  {message}", Colors.YELLOW)

    def error(self, message: str):
        """Print an error message"""
        self.log(f"❌ {message}", Colors.RED)

    def prompt(self, question: str, default: str = "", validation_func=None) -> str:
        """Prompt user for input with validation"""
        while True:
            if default:
                response = input(f"{Colors.CYAN}{question} [{default}]: {Colors.NC}").strip()
                if not response:
                    response = default
            else:
                response = input(f"{Colors.CYAN}{question}: {Colors.NC}").strip()
            
            if validation_func:
                try:
                    validation_func(response)
                    break
                except ValueError as e:
                    self.error(str(e))
                    continue
            else:
                break
        
        return response

    def yes_no(self, question: str, default: bool = True) -> bool:
        """Prompt for yes/no with default"""
        default_str = "Y/n" if default else "y/N"
        response = input(f"{Colors.CYAN}{question} [{default_str}]: {Colors.NC}").strip().lower()
        
        if not response:
            return default
        
        return response.startswith('y')

    def detect_networks(self) -> List[str]:
        """Auto-detect local networks"""
        networks = []
        try:
            # Get network interfaces
            result = subprocess.run(['ip', 'route'], capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'dev' in line and '/' in line:
                        parts = line.split()
                        for part in parts:
                            if '/' in part and not part.startswith('169.254'):
                                try:
                                    network = ipaddress.ip_network(part, strict=False)
                                    if network.is_private:
                                        networks.append(str(network))
                                except:
                                    continue
        except:
            pass
        
        # Add common private networks if not detected
        common_networks = ["192.168.1.0/24", "192.168.0.0/24", "10.0.0.0/8", "172.16.0.0/12"]
        for net in common_networks:
            if net not in networks:
                networks.append(net)
        
        return list(set(networks))

    def validate_network(self, network_str: str):
        """Validate network CIDR notation"""
        try:
            ipaddress.ip_network(network_str, strict=False)
        except ValueError:
            raise ValueError(f"Invalid network format: {network_str}")

    def validate_port(self, port_str: str):
        """Validate port number"""
        try:
            port = int(port_str)
            if not (1 <= port <= 65535):
                raise ValueError("Port must be between 1 and 65535")
        except ValueError:
            raise ValueError(f"Invalid port number: {port_str}")

    def configure_authentication(self):
        """Configure authentication settings"""
        self.info("🔐 Configuring Authentication")
        print()
        
        # API Key
        current_key = os.environ.get('NEONHACK_API_KEY', '')
        if current_key and len(current_key) > 20:
            if self.yes_no(f"Keep existing API key ({current_key[:8]}...)?"):
                self.config['NEONHACK_API_KEY'] = current_key
            else:
                self.config['NEONHACK_API_KEY'] = secrets.token_urlsafe(32)
        else:
            self.config['NEONHACK_API_KEY'] = secrets.token_urlsafe(32)
        
        self.success(f"API Key: {self.config['NEONHACK_API_KEY'][:8]}...")
        
        # Metasploit password
        self.config['MSF_PASSWORD'] = f"neonhack_msf_{secrets.token_hex(8)}"
        self.success("Metasploit password generated")

    def configure_network_settings(self):
        """Configure network and scanning settings"""
        self.info("🌐 Configuring Network Settings")
        print()
        
        # Web interface settings
        self.config['FLASK_HOST'] = self.prompt("Web interface host", "0.0.0.0")
        self.config['FLASK_PORT'] = self.prompt("Web interface port", "5000", self.validate_port)
        
        # Detect local networks
        detected_networks = self.detect_networks()
        self.info(f"Detected networks: {', '.join(detected_networks[:3])}...")
        
        # Configure allowed scan networks
        self.networks = []
        if self.yes_no("Use detected networks for scanning?"):
            self.networks.extend(detected_networks[:5])  # Limit to first 5
        
        # Allow custom networks
        if self.yes_no("Add custom networks?", False):
            while True:
                network = self.prompt("Enter network (CIDR format, empty to finish)", "", 
                                    lambda x: self.validate_network(x) if x else None)
                if not network:
                    break
                self.networks.append(network)
        
        # Ensure at least one network is configured
        if not self.networks:
            self.networks = ["192.168.1.0/24", "10.0.0.0/8", "127.0.0.1/32"]
            self.warning("Using default networks for scanning")
        
        self.success(f"Configured {len(self.networks)} allowed networks")

    def configure_database(self):
        """Configure database settings"""
        self.info("🗄️ Configuring Database")
        print()
        
        self.config['DATABASE_PATH'] = str(self.install_dir / "jobs.db")
        
        # Initialize database if needed
        schema_file = self.install_dir / "schema.sql"
        if schema_file.exists():
            self.success("Database schema found")
        else:
            self.warning("Database schema not found, will use default")

    def configure_security(self):
        """Configure security settings"""
        self.info("🛡️ Configuring Security Settings")
        print()
        
        # Socket path
        self.config['PRIV_SOCKET_PATH'] = "/tmp/priv_scanner.sock"
        
        # Logging
        log_level = self.prompt("Log level (DEBUG/INFO/WARNING/ERROR)", "INFO")
        self.config['LOG_LEVEL'] = log_level.upper()
        self.config['LOG_FILE'] = str(self.install_dir / "neonhack.log")
        
        # Security options
        self.config['FLASK_DEBUG'] = "false"
        self.config['FLASK_ENV'] = "production"
        
        self.success("Security settings configured")

    def configure_optional_features(self):
        """Configure optional features"""
        self.info("🔧 Configuring Optional Features")
        print()
        
        # Metasploit integration
        if subprocess.run(['which', 'msfconsole'], capture_output=True).returncode == 0:
            self.config['MSF_ENABLED'] = "true"
            self.success("Metasploit integration enabled")
        else:
            self.config['MSF_ENABLED'] = "false"
            self.warning("Metasploit not found, integration disabled")
        
        # Hydra integration
        if subprocess.run(['which', 'hydra'], capture_output=True).returncode == 0:
            self.config['HYDRA_ENABLED'] = "true"
            self.success("Hydra integration enabled")
        else:
            self.config['HYDRA_ENABLED'] = "false"
            self.warning("Hydra not found, integration disabled")
        
        # Nmap integration
        if subprocess.run(['which', 'nmap'], capture_output=True).returncode == 0:
            self.config['NMAP_ENABLED'] = "true"
            self.success("Nmap integration enabled")
        else:
            self.config['NMAP_ENABLED'] = "false"
            self.warning("Nmap not found, integration disabled")

    def write_environment_file(self):
        """Write the .env configuration file"""
        self.info("💾 Writing configuration file")
        
        env_content = f"""# NeonHack v5.2 Configuration
# Generated by Configuration Wizard on {subprocess.run(['date'], capture_output=True, text=True).stdout.strip()}

# Authentication
NEONHACK_API_KEY={self.config['NEONHACK_API_KEY']}
MSF_PASSWORD={self.config['MSF_PASSWORD']}

# Database
DATABASE_PATH={self.config['DATABASE_PATH']}

# Network Configuration
FLASK_HOST={self.config['FLASK_HOST']}
FLASK_PORT={self.config['FLASK_PORT']}
PRIV_SOCKET_PATH={self.config['PRIV_SOCKET_PATH']}

# Security
FLASK_DEBUG={self.config['FLASK_DEBUG']}
FLASK_ENV={self.config['FLASK_ENV']}
LOG_LEVEL={self.config['LOG_LEVEL']}
LOG_FILE={self.config['LOG_FILE']}

# Feature Flags
MSF_ENABLED={self.config.get('MSF_ENABLED', 'false')}
HYDRA_ENABLED={self.config.get('HYDRA_ENABLED', 'false')}
NMAP_ENABLED={self.config.get('NMAP_ENABLED', 'false')}

# Performance
MAX_WORKERS=4
TIMEOUT_SECONDS=300
"""
        
        # Write the file
        self.config_file.write_text(env_content)
        os.chmod(self.config_file, 0o600)
        self.success(f"Configuration saved to {self.config_file}")

    def update_app_config(self):
        """Update app.py with network configurations"""
        if not self.app_config_file.exists():
            self.warning("app.py not found, skipping network configuration update")
            return
        
        self.info("📝 Updating application configuration")
        
        # Read the current app.py
        content = self.app_config_file.read_text()
        
        # Generate network configuration
        network_config = "ALLOWED_SCAN_SUBNETS = [\n"
        for network in self.networks:
            network_config += f'    ipaddress.ip_network("{network}"),\n'
        network_config += "]"
        
        # Try to replace existing configuration
        import re
        pattern = r'ALLOWED_SCAN_SUBNETS\s*=\s*\[.*?\]'
        if re.search(pattern, content, re.DOTALL):
            content = re.sub(pattern, network_config, content, flags=re.DOTALL)
            self.app_config_file.write_text(content)
            self.success("Updated allowed scan networks in app.py")
        else:
            self.warning("Could not update app.py automatically. Manual configuration may be needed.")

    def validate_configuration(self):
        """Validate the generated configuration"""
        self.info("✅ Validating configuration")
        
        issues = []
        
        # Check file permissions
        if self.config_file.exists():
            stat = self.config_file.stat()
            if stat.st_mode & 0o077:
                issues.append("Configuration file permissions too permissive")
        
        # Check network configurations
        for network in self.networks:
            try:
                net = ipaddress.ip_network(network)
                if not net.is_private and str(net) != "127.0.0.1/32":
                    issues.append(f"Public network configured: {network}")
            except:
                issues.append(f"Invalid network: {network}")
        
        # Check port availability
        try:
            port = int(self.config['FLASK_PORT'])
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                result = s.connect_ex(('localhost', port))
                if result == 0:
                    issues.append(f"Port {port} is already in use")
        except:
            pass
        
        if issues:
            self.warning(f"Configuration issues found:")
            for issue in issues:
                print(f"  • {issue}")
        else:
            self.success("Configuration validation passed")

    def show_summary(self):
        """Show configuration summary"""
        print()
        self.log("━" * 70, Colors.PURPLE)
        self.log("🎉 CONFIGURATION COMPLETE!", Colors.GREEN)
        self.log("━" * 70, Colors.PURPLE)
        print()
        
        self.log("📋 Configuration Summary:", Colors.CYAN)
        print(f"  🌐 Web Interface: http://{self.config['FLASK_HOST']}:{self.config['FLASK_PORT']}")
        print(f"  🔑 API Key: {self.config['NEONHACK_API_KEY'][:8]}...")
        print(f"  📁 Config File: {self.config_file}")
        print(f"  🗄️ Database: {self.config['DATABASE_PATH']}")
        print(f"  🌍 Allowed Networks: {len(self.networks)} configured")
        print()
        
        self.log("🚀 Next Steps:", Colors.YELLOW)
        print("  1. Restart NeonHack services: sudo systemctl restart neonhack")
        print("  2. Check service status: sudo systemctl status neonhack")
        print("  3. Open web interface: neonhack open")
        print("  4. View logs: neonhack logs")
        print()
        
        self.log("⚠️  Security Reminders:", Colors.YELLOW)
        print("  • Only scan networks you own or have permission to test")
        print("  • Keep your API key secure and don't share it")
        print("  • Regularly update the system and dependencies")
        print("  • Review firewall settings for your environment")
        print()

    def run(self):
        """Run the configuration wizard"""
        try:
            self.print_banner()
            
            # Check if running as root
            if os.geteuid() != 0:
                self.error("This wizard must be run as root")
                sys.exit(1)
            
            # Check if NeonHack is installed
            if not self.install_dir.exists():
                self.error(f"NeonHack not found at {self.install_dir}")
                self.info("Please install NeonHack first using the installation script")
                sys.exit(1)
            
            self.info(f"Configuring NeonHack installation at {self.install_dir}")
            print()
            
            # Run configuration steps
            self.configure_authentication()
            self.configure_network_settings()
            self.configure_database()
            self.configure_security()
            self.configure_optional_features()
            
            # Write configuration
            self.write_environment_file()
            self.update_app_config()
            
            # Validate and show summary
            self.validate_configuration()
            self.show_summary()
            
        except KeyboardInterrupt:
            print()
            self.warning("Configuration cancelled by user")
            sys.exit(1)
        except Exception as e:
            self.error(f"Configuration failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    wizard = ConfigWizard()
    wizard.run()