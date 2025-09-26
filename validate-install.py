#!/usr/bin/env python3
"""
NeonHack v5.2 - Installation Validation & Health Check Tool
Comprehensive validation of the NeonHack installation
"""

import os
import sys
import json
import sqlite3
import subprocess
import socket
import requests
from pathlib import Path
from typing import Dict, List, Tuple, Any

# Color codes
class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'

class InstallationValidator:
    def __init__(self):
        self.install_dir = Path("/opt/neonhack")
        self.config_file = self.install_dir / ".env"
        self.db_file = self.install_dir / "jobs.db"
        self.schema_file = self.install_dir / "schema.sql"
        self.app_file = self.install_dir / "app.py"
        
        self.results = {
            'passed': 0,
            'failed': 0,
            'warnings': 0,
            'tests': []
        }
        
        self.config = {}
        self.load_config()

    def log(self, message: str, color: str = Colors.NC):
        """Print colored message"""
        print(f"{color}{message}{Colors.NC}")

    def success(self, test_name: str, details: str = ""):
        """Record a successful test"""
        self.results['passed'] += 1
        self.results['tests'].append({'name': test_name, 'status': 'PASS', 'details': details})
        self.log(f"✅ {test_name}", Colors.GREEN)
        if details:
            self.log(f"   {details}", Colors.BLUE)

    def failure(self, test_name: str, details: str = ""):
        """Record a failed test"""
        self.results['failed'] += 1
        self.results['tests'].append({'name': test_name, 'status': 'FAIL', 'details': details})
        self.log(f"❌ {test_name}", Colors.RED)
        if details:
            self.log(f"   {details}", Colors.RED)

    def warning(self, test_name: str, details: str = ""):
        """Record a warning"""
        self.results['warnings'] += 1
        self.results['tests'].append({'name': test_name, 'status': 'WARN', 'details': details})
        self.log(f"⚠️  {test_name}", Colors.YELLOW)
        if details:
            self.log(f"   {details}", Colors.YELLOW)

    def info(self, message: str):
        """Print info message"""
        self.log(f"ℹ️  {message}", Colors.CYAN)

    def load_config(self):
        """Load configuration from .env file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            self.config[key.strip()] = value.strip()
            except Exception as e:
                self.failure("Configuration Loading", f"Failed to load .env file: {e}")

    def run_command(self, command: List[str], capture_output: bool = True) -> Tuple[int, str, str]:
        """Run a command and return exit code, stdout, stderr"""
        try:
            result = subprocess.run(command, capture_output=capture_output, text=True, timeout=30)
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -2, "", str(e)

    def check_system_requirements(self):
        """Check system requirements and dependencies"""
        self.info("Checking system requirements...")
        
        # Check if running as root (needed for some checks)
        if os.geteuid() == 0:
            self.success("Root Access", "Running with root privileges")
        else:
            self.warning("Root Access", "Not running as root - some checks may be limited")
        
        # Check Python version
        python_version = sys.version_info
        if python_version >= (3, 7):
            self.success("Python Version", f"Python {python_version.major}.{python_version.minor}.{python_version.micro}")
        else:
            self.failure("Python Version", f"Python {python_version.major}.{python_version.minor} is too old (3.7+ required)")
        
        # Check essential system commands
        essential_commands = ['systemctl', 'netstat', 'curl', 'git']
        for cmd in essential_commands:
            exit_code, _, _ = self.run_command(['which', cmd])
            if exit_code == 0:
                self.success(f"Command: {cmd}", "Available")
            else:
                self.failure(f"Command: {cmd}", "Not found")
        
        # Check optional security tools
        optional_tools = ['nmap', 'hydra', 'msfconsole', 'nikto', 'dirb']
        for tool in optional_tools:
            exit_code, _, _ = self.run_command(['which', tool])
            if exit_code == 0:
                self.success(f"Tool: {tool}", "Available")
            else:
                self.warning(f"Tool: {tool}", "Not found (optional)")

    def check_installation_files(self):
        """Check if all required files are present"""
        self.info("Checking installation files...")
        
        # Check installation directory
        if self.install_dir.exists() and self.install_dir.is_dir():
            self.success("Installation Directory", str(self.install_dir))
        else:
            self.failure("Installation Directory", f"{self.install_dir} not found")
            return
        
        # Check essential files
        essential_files = [
            ('app.py', 'Main application file'),
            ('requirements.txt', 'Python dependencies'),
            ('schema.sql', 'Database schema'),
            ('.env', 'Configuration file'),
            ('jobs.db', 'SQLite database'),
        ]
        
        for filename, description in essential_files:
            file_path = self.install_dir / filename
            if file_path.exists():
                size = file_path.stat().st_size
                self.success(f"File: {filename}", f"{description} ({size} bytes)")
            else:
                self.failure(f"File: {filename}", f"{description} not found")
        
        # Check Python virtual environment
        venv_path = self.install_dir / "venv"
        if venv_path.exists():
            python_exe = venv_path / "bin" / "python"
            if python_exe.exists():
                self.success("Virtual Environment", "Python venv found")
            else:
                self.failure("Virtual Environment", "Python executable not found in venv")
        else:
            self.failure("Virtual Environment", "Virtual environment not found")

    def check_file_permissions(self):
        """Check file permissions and ownership"""
        self.info("Checking file permissions...")
        
        # Check .env file permissions (should be 600)
        if self.config_file.exists():
            stat = self.config_file.stat()
            mode = stat.st_mode & 0o777
            if mode == 0o600:
                self.success("Config Permissions", "Secure (600)")
            else:
                self.failure("Config Permissions", f"Insecure ({oct(mode)}) - should be 600")
        
        # Check ownership
        try:
            import pwd
            stat = self.install_dir.stat()
            owner = pwd.getpwuid(stat.st_uid).pw_name
            if owner == "neonhack":
                self.success("File Ownership", "Owned by neonhack user")
            else:
                self.warning("File Ownership", f"Owned by {owner} (expected: neonhack)")
        except Exception as e:
            self.warning("File Ownership", f"Could not check ownership: {e}")

    def check_database(self):
        """Check database integrity and schema"""
        self.info("Checking database...")
        
        if not self.db_file.exists():
            self.failure("Database File", "jobs.db not found")
            return
        
        try:
            # Connect to database
            conn = sqlite3.connect(str(self.db_file))
            cursor = conn.cursor()
            
            # Check if jobs table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'")
            if cursor.fetchone():
                self.success("Database Schema", "Jobs table exists")
            else:
                self.failure("Database Schema", "Jobs table not found")
            
            # Check table structure
            cursor.execute("PRAGMA table_info(jobs)")
            columns = cursor.fetchall()
            expected_columns = ['id', 'owner_key', 'type', 'status', 'pid', 'result', 'created_at', 'updated_at']
            found_columns = [col[1] for col in columns]
            
            missing_columns = set(expected_columns) - set(found_columns)
            if not missing_columns:
                self.success("Database Columns", f"{len(found_columns)} columns found")
            else:
                self.failure("Database Columns", f"Missing columns: {missing_columns}")
            
            # Test database write
            cursor.execute("INSERT OR REPLACE INTO jobs (id, owner_key, type, status, created_at, updated_at) VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))", 
                          ('test-validation', 'test-key', 'validation', 'completed'))
            conn.commit()
            
            # Test database read
            cursor.execute("SELECT * FROM jobs WHERE id = ?", ('test-validation',))
            if cursor.fetchone():
                self.success("Database Operations", "Read/write operations working")
                # Clean up test record
                cursor.execute("DELETE FROM jobs WHERE id = ?", ('test-validation',))
                conn.commit()
            else:
                self.failure("Database Operations", "Failed to read test record")
            
            conn.close()
            
        except Exception as e:
            self.failure("Database Connection", str(e))

    def check_python_dependencies(self):
        """Check Python dependencies"""
        self.info("Checking Python dependencies...")
        
        venv_python = self.install_dir / "venv" / "bin" / "python"
        if not venv_python.exists():
            self.failure("Python Environment", "Virtual environment not found")
            return
        
        # Check critical dependencies
        critical_deps = [
            ('flask', 'Web framework'),
            ('sqlite3', 'Database support'),
            ('json', 'JSON support'),
            ('subprocess', 'Process management'),
            ('socket', 'Network communication'),
        ]
        
        for module, description in critical_deps:
            exit_code, _, stderr = self.run_command([str(venv_python), '-c', f'import {module}'])
            if exit_code == 0:
                self.success(f"Python Module: {module}", description)
            else:
                self.failure(f"Python Module: {module}", f"{description} - {stderr}")
        
        # Check optional dependencies
        optional_deps = [
            ('cv2', 'OpenCV for camera integration'),
            ('scapy', 'Network packet manipulation'),
            ('requests', 'HTTP client'),
            ('psutil', 'System monitoring'),
        ]
        
        for module, description in optional_deps:
            exit_code, _, stderr = self.run_command([str(venv_python), '-c', f'import {module}'])
            if exit_code == 0:
                self.success(f"Optional Module: {module}", description)
            else:
                self.warning(f"Optional Module: {module}", f"{description} - may limit functionality")

    def check_systemd_services(self):
        """Check systemd services"""
        self.info("Checking systemd services...")
        
        services = [
            ('neonhack.service', 'Main NeonHack service'),
            ('priv_scanner.service', 'Privileged scanner service'),
            ('priv_scanner.socket', 'Privileged scanner socket'),
        ]
        
        for service, description in services:
            # Check if service file exists
            service_file = Path(f"/etc/systemd/system/{service}")
            if service_file.exists():
                self.success(f"Service File: {service}", "Found")
                
                # Check service status
                exit_code, stdout, stderr = self.run_command(['systemctl', 'is-active', service])
                if exit_code == 0 and 'active' in stdout:
                    self.success(f"Service Status: {service}", "Active")
                else:
                    self.failure(f"Service Status: {service}", f"Not active - {stdout.strip()}")
                
                # Check if enabled
                exit_code, stdout, stderr = self.run_command(['systemctl', 'is-enabled', service])
                if exit_code == 0 and 'enabled' in stdout:
                    self.success(f"Service Enabled: {service}", "Enabled")
                else:
                    self.warning(f"Service Enabled: {service}", "Not enabled for auto-start")
            else:
                self.failure(f"Service File: {service}", "Not found")

    def check_network_connectivity(self):
        """Check network connectivity and web interface"""
        self.info("Checking network connectivity...")
        
        # Get port from config
        port = self.config.get('FLASK_PORT', '5000')
        host = self.config.get('FLASK_HOST', 'localhost')
        
        # Check if port is listening
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)
                result = s.connect_ex((host if host != '0.0.0.0' else 'localhost', int(port)))
                if result == 0:
                    self.success("Port Listening", f"Port {port} is open")
                else:
                    self.failure("Port Listening", f"Port {port} is not accessible")
        except Exception as e:
            self.failure("Port Check", str(e))
        
        # Test HTTP connectivity
        try:
            response = requests.get(f"http://localhost:{port}", timeout=10)
            if response.status_code == 200:
                self.success("Web Interface", f"HTTP 200 OK (port {port})")
            else:
                self.warning("Web Interface", f"HTTP {response.status_code} (port {port})")
        except requests.exceptions.ConnectionError:
            self.failure("Web Interface", f"Connection refused (port {port})")
        except Exception as e:
            self.failure("Web Interface", str(e))

    def check_socket_communication(self):
        """Check privileged scanner socket"""
        self.info("Checking socket communication...")
        
        socket_path = self.config.get('PRIV_SOCKET_PATH', '/tmp/priv_scanner.sock')
        
        # Check if socket file exists
        if os.path.exists(socket_path):
            if os.path.stat(socket_path).st_mode & 0o060000:  # Check if it's a socket
                self.success("Scanner Socket", f"Socket file exists at {socket_path}")
                
                # Test socket communication
                try:
                    import json
                    test_request = {
                        'target_cidr': '127.0.0.1/32',
                        'interface': 'lo'
                    }
                    
                    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    client.settimeout(5)
                    client.connect(socket_path)
                    client.sendall(json.dumps(test_request).encode('utf-8'))
                    response = client.recv(4096).decode('utf-8')
                    client.close()
                    
                    if response:
                        self.success("Socket Communication", "Test request successful")
                    else:
                        self.failure("Socket Communication", "No response received")
                        
                except Exception as e:
                    self.failure("Socket Communication", str(e))
            else:
                self.failure("Scanner Socket", f"{socket_path} exists but is not a socket")
        else:
            self.failure("Scanner Socket", f"Socket file not found at {socket_path}")

    def check_configuration(self):
        """Check configuration values"""
        self.info("Checking configuration...")
        
        # Check API key
        api_key = self.config.get('NEONHACK_API_KEY', '')
        if api_key and len(api_key) >= 20:
            self.success("API Key", f"Valid key configured ({len(api_key)} characters)")
        else:
            self.failure("API Key", "Invalid or missing API key")
        
        # Check database path
        db_path = self.config.get('DATABASE_PATH', '')
        if db_path and os.path.exists(db_path):
            self.success("Database Path", f"Valid path: {db_path}")
        else:
            self.failure("Database Path", f"Invalid path: {db_path}")
        
        # Check MSF password
        msf_pass = self.config.get('MSF_PASSWORD', '')
        if msf_pass:
            self.success("MSF Password", "Configured")
        else:
            self.warning("MSF Password", "Not configured (Metasploit features may not work)")

    def check_firewall(self):
        """Check firewall configuration"""
        self.info("Checking firewall configuration...")
        
        port = self.config.get('FLASK_PORT', '5000')
        
        # Check UFW (Ubuntu/Debian)
        exit_code, stdout, _ = self.run_command(['ufw', 'status'])
        if exit_code == 0:
            if 'inactive' in stdout.lower():
                self.warning("UFW Firewall", "Inactive")
            elif port in stdout:
                self.success("UFW Firewall", f"Port {port} allowed")
            else:
                self.warning("UFW Firewall", f"Port {port} may not be allowed")
        
        # Check firewalld (CentOS/RHEL/Fedora)
        exit_code, stdout, _ = self.run_command(['firewall-cmd', '--list-ports'])
        if exit_code == 0:
            if f"{port}/tcp" in stdout:
                self.success("Firewalld", f"Port {port}/tcp allowed")
            else:
                self.warning("Firewalld", f"Port {port}/tcp may not be allowed")

    def generate_report(self):
        """Generate validation report"""
        print("\n" + "=" * 70)
        self.log("🎯 NEONHACK INSTALLATION VALIDATION REPORT", Colors.BOLD + Colors.PURPLE)
        print("=" * 70)
        
        # Summary
        total_tests = len(self.results['tests'])
        self.log(f"\n📊 Summary:", Colors.CYAN)
        self.log(f"   Total Tests: {total_tests}", Colors.BLUE)
        self.log(f"   ✅ Passed: {self.results['passed']}", Colors.GREEN)
        self.log(f"   ❌ Failed: {self.results['failed']}", Colors.RED)
        self.log(f"   ⚠️  Warnings: {self.results['warnings']}", Colors.YELLOW)
        
        # Overall status
        if self.results['failed'] == 0:
            if self.results['warnings'] == 0:
                self.log(f"\n🎉 INSTALLATION STATUS: EXCELLENT", Colors.GREEN + Colors.BOLD)
                self.log("   All tests passed! NeonHack is fully operational.", Colors.GREEN)
            else:
                self.log(f"\n✅ INSTALLATION STATUS: GOOD", Colors.YELLOW + Colors.BOLD)
                self.log("   Installation successful with minor warnings.", Colors.YELLOW)
        elif self.results['failed'] <= 2:
            self.log(f"\n⚠️  INSTALLATION STATUS: NEEDS ATTENTION", Colors.YELLOW + Colors.BOLD)
            self.log("   Some issues found. Review failed tests below.", Colors.YELLOW)
        else:
            self.log(f"\n❌ INSTALLATION STATUS: CRITICAL ISSUES", Colors.RED + Colors.BOLD)
            self.log("   Multiple critical issues found. Installation may not work properly.", Colors.RED)
        
        # Failed tests details
        if self.results['failed'] > 0:
            self.log(f"\n🔍 Failed Tests:", Colors.RED)
            for test in self.results['tests']:
                if test['status'] == 'FAIL':
                    self.log(f"   • {test['name']}: {test['details']}", Colors.RED)
        
        # Warnings
        if self.results['warnings'] > 0:
            self.log(f"\n⚠️  Warnings:", Colors.YELLOW)
            for test in self.results['tests']:
                if test['status'] == 'WARN':
                    self.log(f"   • {test['name']}: {test['details']}", Colors.YELLOW)
        
        # Quick fixes
        self.log(f"\n🔧 Quick Fixes:", Colors.CYAN)
        self.log("   • Restart services: sudo systemctl restart neonhack priv_scanner.socket", Colors.BLUE)
        self.log("   • Check logs: sudo journalctl -u neonhack -n 20", Colors.BLUE)
        self.log("   • Validate again: sudo python3 /opt/neonhack/validate-install.py", Colors.BLUE)
        self.log("   • Get help: neonhack --help", Colors.BLUE)
        
        print("\n" + "=" * 70)
        
        # Return exit code based on results
        return 0 if self.results['failed'] == 0 else 1

    def run_validation(self):
        """Run all validation checks"""
        self.log("🔍 NeonHack v5.2 - Installation Validator", Colors.PURPLE + Colors.BOLD)
        print()
        
        try:
            self.check_system_requirements()
            self.check_installation_files()
            self.check_file_permissions()
            self.check_database()
            self.check_python_dependencies()
            self.check_systemd_services()
            self.check_network_connectivity()
            self.check_socket_communication()
            self.check_configuration()
            self.check_firewall()
            
            return self.generate_report()
            
        except KeyboardInterrupt:
            print()
            self.log("Validation interrupted by user", Colors.YELLOW)
            return 1
        except Exception as e:
            self.log(f"Validation failed with error: {e}", Colors.RED)
            return 1

if __name__ == "__main__":
    validator = InstallationValidator()
    exit_code = validator.run_validation()
    sys.exit(exit_code)