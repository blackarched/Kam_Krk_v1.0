"""
Secure Flask Web Server for NeonHack (v5.2 - Camera Integration)

This application serves the frontend and provides a secure API for scanning tasks.
It features API key authentication, persistent job management via SQLite,
server-side secrets, and strict input validation.
"""
import os
import re
import ipaddress
import sqlite3
import logging
import socket
import secrets
import json
import time
import subprocess
import signal
import resource 
import cv2
from datetime import datetime, timedelta
from functools import wraps
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, jsonify, render_template, request, g, Response
import random

# Import custom modules
import scanner_final as scanner
import camera_scanner

# --- 1. Configuration ---
class Config:
    SECRET_API_KEY = os.environ.get("NEONHACK_API_KEY", "change-this-insecure-default-key")
    MSF_PASSWORD = os.environ.get("MSF_PASSWORD", "msf_rpc_password")
    DATABASE_PATH = "jobs.db"
    PRIV_SOCKET_PATH = "/tmp/priv_scanner.sock"
    
    ALLOWED_SCAN_SUBNETS = [
        ipaddress.ip_network("192.168.1.0/24"),
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("127.0.0.1/32"),
    ]
    
    WHITELISTED_MODULES = {
        "exploit/unix/ftp/vsftpd_234_backdoor",
        "auxiliary/scanner/portscan/tcp",
    }
    
    HYDRA_TIMEOUT_SECONDS = 300
    MSF_SESSION_TIMEOUT_SECONDS = 60

# --- 2. Enhanced Logging System ---
class ContextualLogger:
    """Enhanced logging system with user-friendly messages and context"""
    
    def __init__(self, logger_name='NeonHack'):
        self.logger = logging.getLogger(logger_name)
        
    def log_operation_start(self, operation, user_context, details=None):
        """Log the start of an operation with context"""
        context_info = f"User: {user_context.get('api_key_id', 'Unknown')}"
        if details:
            context_info += f" | Details: {details}"
        self.logger.info(f"🚀 STARTING: {operation} | {context_info}")
        
    def log_operation_success(self, operation, user_context, result_summary=None):
        """Log successful completion of an operation"""
        context_info = f"User: {user_context.get('api_key_id', 'Unknown')}"
        if result_summary:
            context_info += f" | Result: {result_summary}"
        self.logger.info(f"✅ SUCCESS: {operation} | {context_info}")
        
    def log_operation_failure(self, operation, user_context, error_msg, technical_details=None):
        """Log operation failure with user-friendly message and technical details"""
        context_info = f"User: {user_context.get('api_key_id', 'Unknown')}"
        self.logger.error(f"❌ FAILED: {operation} | {context_info} | Error: {error_msg}")
        if technical_details:
            self.logger.debug(f"Technical details for {operation}: {technical_details}")
            
    def log_security_event(self, event_type, details, severity='WARNING'):
        """Log security-related events"""
        log_func = getattr(self.logger, severity.lower())
        log_func(f"🔒 SECURITY: {event_type} | {details}")
        
    def log_performance_metric(self, operation, duration, details=None):
        """Log performance metrics"""
        perf_info = f"Duration: {duration:.2f}s"
        if details:
            perf_info += f" | {details}"
        self.logger.info(f"⏱️  PERFORMANCE: {operation} | {perf_info}")
        
    def log_job_status_change(self, job_id, old_status, new_status, user_context, details=None):
        """Log job status changes with context"""
        context_info = f"Job: {job_id} | User: {user_context.get('api_key_id', 'Unknown')}"
        if details:
            context_info += f" | Details: {details}"
        self.logger.info(f"🔄 JOB STATUS: {old_status} → {new_status} | {context_info}")

# Initialize enhanced logger
enhanced_logger = ContextualLogger()

# --- 3. Retry Mechanism System ---
class RetryConfig:
    """Configuration for retry mechanisms"""
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BASE_DELAY = 1.0  # Base delay in seconds
    DEFAULT_MAX_DELAY = 30.0  # Maximum delay in seconds
    EXPONENTIAL_BACKOFF_MULTIPLIER = 2.0
    JITTER_RANGE = 0.1  # 10% jitter

class RetryableError(Exception):
    """Base class for errors that should be retried"""
    pass

class NetworkRetryableError(RetryableError):
    """Network-related errors that can be retried"""
    pass

class TimeoutRetryableError(RetryableError):
    """Timeout errors that can be retried"""
    pass

def with_retry(max_retries=None, base_delay=None, max_delay=None, retryable_exceptions=None):
    """
    Decorator that implements retry logic with exponential backoff and jitter
    """
    max_retries = max_retries or RetryConfig.DEFAULT_MAX_RETRIES
    base_delay = base_delay or RetryConfig.DEFAULT_BASE_DELAY
    max_delay = max_delay or RetryConfig.DEFAULT_MAX_DELAY
    retryable_exceptions = retryable_exceptions or (RetryableError, NetworkRetryableError, TimeoutRetryableError)
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            user_context = getattr(g, 'user_context', {'api_key_id': 'System'})
            
            for attempt in range(max_retries + 1):
                try:
                    if attempt > 0:
                        enhanced_logger.log_operation_start(
                            f"Retry Attempt {attempt}",
                            user_context,
                            f"Function: {func.__name__}"
                        )
                    
                    result = func(*args, **kwargs)
                    
                    if attempt > 0:
                        enhanced_logger.log_operation_success(
                            f"Retry Success on Attempt {attempt}",
                            user_context,
                            f"Function: {func.__name__}"
                        )
                    
                    return result
                    
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        # Calculate delay with exponential backoff and jitter
                        delay = min(
                            base_delay * (RetryConfig.EXPONENTIAL_BACKOFF_MULTIPLIER ** attempt),
                            max_delay
                        )
                        
                        # Add jitter to prevent thundering herd
                        jitter = delay * RetryConfig.JITTER_RANGE * (2 * random.random() - 1)
                        final_delay = max(0, delay + jitter)
                        
                        enhanced_logger.log_operation_failure(
                            f"Retry Attempt {attempt + 1} Failed",
                            user_context,
                            f"Will retry in {final_delay:.2f}s",
                            f"Function: {func.__name__} | Error: {str(e)}"
                        )
                        
                        time.sleep(final_delay)
                    else:
                        enhanced_logger.log_operation_failure(
                            f"All Retry Attempts Exhausted",
                            user_context,
                            f"Function failed after {max_retries + 1} attempts",
                            f"Function: {func.__name__} | Final error: {str(e)}"
                        )
                        
                except Exception as e:
                    # Non-retryable exception, fail immediately
                    enhanced_logger.log_operation_failure(
                        f"Non-Retryable Error",
                        user_context,
                        f"Function failed with non-retryable error",
                        f"Function: {func.__name__} | Error: {str(e)}"
                    )
                    raise
            
            # If we get here, all retries were exhausted
            raise last_exception
            
        return wrapper
    return decorator

# --- 4. Application and Database Initialization ---
app = Flask(__name__, template_folder='.')
app.config.from_object(Config)

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE_PATH'])
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

# --- 5. Job Management and Progress Tracking ---
class JobManager:
    """Manages job lifecycle, progress tracking, and cleanup"""
    
    @staticmethod
    def create_job(job_id, owner_key, job_type, priority=5, expires_hours=24):
        """Create a new job with progress tracking"""
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=expires_hours)
        
        db = get_db()
        db.execute("""
            INSERT INTO jobs (id, owner_key, type, status, progress, progress_message, 
                            created_at, updated_at, expires_at, priority, max_retries) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (job_id, owner_key, job_type, 'queued', 0, 'Job created and queued', 
              now.isoformat(), now.isoformat(), expires_at.isoformat(), priority, 3))
        db.commit()
        
        user_context = {'api_key_id': owner_key}
        enhanced_logger.log_job_status_change(job_id, 'none', 'queued', user_context, 
                                            f"Job type: {job_type} | Priority: {priority}")
    
    @staticmethod
    def update_job_progress(job_id, progress, message=None, status=None):
        """Update job progress and status"""
        db = get_db()
        
        # Get current job info
        current_job = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not current_job:
            return False
            
        old_status = current_job['status']
        new_status = status or old_status
        
        update_fields = ["progress = ?", "updated_at = ?"]
        update_values = [progress, datetime.utcnow().isoformat()]
        
        if message:
            update_fields.append("progress_message = ?")
            update_values.append(message)
            
        if status:
            update_fields.append("status = ?")
            update_values.append(status)
        
        update_values.append(job_id)
        
        db.execute(f"UPDATE jobs SET {', '.join(update_fields)} WHERE id = ?", update_values)
        db.commit()
        
        user_context = {'api_key_id': current_job['owner_key']}
        if status and status != old_status:
            enhanced_logger.log_job_status_change(job_id, old_status, new_status, user_context, 
                                                f"Progress: {progress}% | Message: {message}")
        
        return True
    
    @staticmethod
    def increment_error_count(job_id):
        """Increment error count for retry tracking"""
        db = get_db()
        db.execute("UPDATE jobs SET error_count = error_count + 1, updated_at = ? WHERE id = ?", 
                  (datetime.utcnow().isoformat(), job_id))
        db.commit()
    
    @staticmethod
    def cleanup_expired_jobs():
        """Clean up expired jobs from the database"""
        now = datetime.utcnow().isoformat()
        db = get_db()
        
        # Get jobs to be cleaned up for logging
        expired_jobs = db.execute("""
            SELECT id, owner_key, type, status FROM jobs 
            WHERE expires_at < ? OR (status IN ('done', 'error', 'cancelled') AND created_at < ?)
        """, (now, (datetime.utcnow() - timedelta(hours=24)).isoformat())).fetchall()
        
        if expired_jobs:
            job_ids = [job['id'] for job in expired_jobs]
            placeholders = ','.join(['?'] * len(job_ids))
            
            deleted_count = db.execute(f"""
                DELETE FROM jobs 
                WHERE id IN ({placeholders})
            """, job_ids).rowcount
            
            db.commit()
            
            enhanced_logger.log_operation_success(
                "Job Cleanup",
                {'api_key_id': 'System'},
                f"Cleaned up {deleted_count} expired jobs"
            )
            
            return deleted_count
        
        return 0
    
    @staticmethod
    def get_job_statistics(owner_key=None):
        """Get job statistics for monitoring"""
        db = get_db()
        
        if owner_key:
            stats = db.execute("""
                SELECT status, COUNT(*) as count FROM jobs 
                WHERE owner_key = ? 
                GROUP BY status
            """, (owner_key,)).fetchall()
        else:
            stats = db.execute("""
                SELECT status, COUNT(*) as count FROM jobs 
                GROUP BY status
            """).fetchall()
        
        return {row['status']: row['count'] for row in stats}

# --- 6. Modular Attack Framework ---
class AttackModule:
    """Base class for attack modules"""
    
    def __init__(self, name, description, required_params=None, optional_params=None):
        self.name = name
        self.description = description
        self.required_params = required_params or []
        self.optional_params = optional_params or {}
        
    def validate_params(self, params):
        """Validate attack parameters"""
        missing_params = [p for p in self.required_params if p not in params]
        if missing_params:
            raise AppError(f"Missing required parameters: {', '.join(missing_params)}")
        return True
    
    def execute(self, job_id, params):
        """Execute the attack - to be implemented by subclasses"""
        raise NotImplementedError("Attack modules must implement execute method")

class HydraAttackModule(AttackModule):
    """Hydra brute force attack module"""
    
    def __init__(self):
        super().__init__(
            name="hydra_attack",
            description="Brute force authentication using Hydra",
            required_params=["target_ip", "protocol", "username_wordlist", "password_wordlist"],
            optional_params={"timeout": 300, "threads": 16}
        )
    
    def execute(self, job_id, params):
        """Execute Hydra attack with progress tracking"""
        self.validate_params(params)
        
        ip = validate_scope(validate_ip(params['target_ip']))
        protocol = params['protocol']
        if protocol not in ['ssh', 'ftp', 'http-get']:
            raise AppError("Invalid protocol for Hydra attack")
        
        user_wl = params['username_wordlist']
        pass_wl = params['password_wordlist']
        timeout = params.get('timeout', 300)
        
        JobManager.update_job_progress(job_id, 10, "Initializing Hydra attack")
        
        return run_hydra_with_progress(job_id, ip, protocol, user_wl, pass_wl, timeout)

class MetasploitAttackModule(AttackModule):
    """Metasploit exploit module"""
    
    def __init__(self):
        super().__init__(
            name="metasploit_exploit",
            description="Execute Metasploit exploits",
            required_params=["target_ip", "module"],
            optional_params={"timeout": 60, "payload": None}
        )
    
    def execute(self, job_id, params):
        """Execute Metasploit exploit with progress tracking"""
        self.validate_params(params)
        
        ip = validate_scope(validate_ip(params['target_ip']))
        module = validate_module(params['module'])
        timeout = params.get('timeout', 60)
        
        JobManager.update_job_progress(job_id, 10, "Initializing Metasploit exploit")
        
        return run_exploit_with_progress(job_id, ip, module, timeout)

class CameraScanModule(AttackModule):
    """Camera scanning module"""
    
    def __init__(self):
        super().__init__(
            name="camera_scan",
            description="Scan network for cameras",
            required_params=["network_cidr"],
            optional_params={"timeout": 300}
        )
    
    def execute(self, job_id, params):
        """Execute camera scan with progress tracking"""
        self.validate_params(params)
        
        network_cidr = validate_cidr(params['network_cidr'])
        
        JobManager.update_job_progress(job_id, 10, "Starting camera network scan")
        
        return run_camera_scan_with_progress(job_id, network_cidr)

class NetworkScanModule(AttackModule):
    """Network scanning module"""
    
    def __init__(self):
        super().__init__(
            name="network_scan",
            description="ARP scan for network discovery",
            required_params=["target_cidr", "interface"],
            optional_params={"timeout": 30}
        )
    
    def execute(self, job_id, params):
        """Execute network scan with progress tracking"""
        self.validate_params(params)
        
        target_cidr = validate_scope(validate_cidr(params['target_cidr']))
        interface = validate_interface(params['interface'])
        
        JobManager.update_job_progress(job_id, 10, "Starting network ARP scan")
        
        return run_network_scan_with_progress(job_id, target_cidr, interface)

class AttackFramework:
    """Central attack framework manager"""
    
    def __init__(self):
        self.modules = {}
        self._register_default_modules()
    
    def _register_default_modules(self):
        """Register default attack modules"""
        modules = [
            HydraAttackModule(),
            MetasploitAttackModule(),
            CameraScanModule(),
            NetworkScanModule()
        ]
        
        for module in modules:
            self.modules[module.name] = module
    
    def register_module(self, module):
        """Register a custom attack module"""
        if not isinstance(module, AttackModule):
            raise ValueError("Module must inherit from AttackModule")
        self.modules[module.name] = module
    
    def get_available_modules(self):
        """Get list of available attack modules"""
        return {
            name: {
                "description": module.description,
                "required_params": module.required_params,
                "optional_params": module.optional_params
            }
            for name, module in self.modules.items()
        }
    
    def execute_attack(self, module_name, job_id, params):
        """Execute an attack using the specified module"""
        if module_name not in self.modules:
            raise AppError(f"Unknown attack module: {module_name}")
        
        module = self.modules[module_name]
        user_context = getattr(g, 'user_context', {'api_key_id': 'System'})
        
        enhanced_logger.log_operation_start(
            f"Attack Execution: {module_name}",
            user_context,
            f"Job ID: {job_id} | Target: {params.get('target_ip', params.get('target_cidr', 'N/A'))}"
        )
        
        try:
            result = module.execute(job_id, params)
            
            enhanced_logger.log_operation_success(
                f"Attack Execution: {module_name}",
                user_context,
                f"Job ID: {job_id} completed successfully"
            )
            
            return result
        except Exception as e:
            enhanced_logger.log_operation_failure(
                f"Attack Execution: {module_name}",
                user_context,
                str(e),
                f"Job ID: {job_id}"
            )
            raise

# Initialize attack framework
attack_framework = AttackFramework()

# --- 7. Custom Error Handling ---
class AppError(Exception):
    def __init__(self, message, status_code=400, details=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details

@app.errorhandler(AppError)
def handle_app_error(error):
    response = {"error": error.message}
    if error.details: response["details"] = error.details
    return jsonify(response), error.status_code

# --- 4. Authentication Decorator ---
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        # Allow API key from header (for standard API calls) 
        # or query param (for browser resources like <img> tags).
        api_key = request.headers.get('X-API-Key') or request.args.get('apiKey')
        
        if not api_key or not secrets.compare_digest(api_key, app.config['SECRET_API_KEY']):
            enhanced_logger.log_security_event(
                "Authentication Failure", 
                f"Invalid API key attempt from IP: {request.remote_addr} | Endpoint: {request.path}",
                'WARNING'
            )
            raise AppError("Unauthorized: Invalid or missing API Key", 401)
        
        g.api_key_identifier = api_key[:8]
        g.user_context = {'api_key_id': g.api_key_identifier, 'ip': request.remote_addr}
        
        enhanced_logger.log_operation_start(
            f"API Access: {request.method} {request.path}",
            g.user_context,
            f"Request from IP: {request.remote_addr}"
        )
        
        try:
            result = f(*args, **kwargs)
            duration = time.time() - start_time
            enhanced_logger.log_performance_metric(
                f"API Call: {request.method} {request.path}",
                duration,
                f"Status: Success | User: {g.api_key_identifier}"
            )
            return result
        except Exception as e:
            duration = time.time() - start_time
            enhanced_logger.log_operation_failure(
                f"API Call: {request.method} {request.path}",
                g.user_context,
                str(e),
                f"Duration: {duration:.2f}s"
            )
            raise
    return decorated_function

# --- 5. Input Validation ---
def validate_ip(ip_str):
    try: ipaddress.ip_address(ip_str); return ip_str
    except ValueError: raise AppError("Invalid IP address format")

def validate_cidr(cidr_str):
    try: ipaddress.ip_network(cidr_str, strict=False); return cidr_str
    except ValueError: raise AppError("Invalid CIDR network format")

def validate_interface(if_str):
    if not re.match(r'^[a-zA-Z0-9]{1,16}$', if_str): raise AppError("Invalid network interface name")
    return if_str

def validate_module(mod_str):
    if mod_str not in app.config['WHITELISTED_MODULES']: raise AppError(f"Disallowed or unknown module.")
    return mod_str

def validate_scope(ip_or_cidr_str):
    try:
        net = ipaddress.ip_network(ip_or_cidr_str, strict=False) if '/' in ip_or_cidr_str else ipaddress.ip_address(ip_or_cidr_str)
        is_authorized = any(net.subnet_of(allowed) if isinstance(net, (ipaddress.IPv4Network, ipaddress.IPv6Network)) else net in allowed for allowed in app.config['ALLOWED_SCAN_SUBNETS'])
        if not is_authorized: raise AppError("Target is outside of authorized scan scope.")
        return ip_or_cidr_str
    except ValueError: raise AppError("Invalid IP or CIDR for scope validation.")

# --- 6. Background Task Execution ---
executor = ThreadPoolExecutor(max_workers=5)

def set_resource_limits():
    """Sets CPU and memory limits for child processes (Unix-only)."""
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (600, 600))
        resource.setrlimit(resource.RLIMIT_AS, (500 * 1024 * 1024, 500 * 1024 * 1024))
    except (ImportError, ValueError, AttributeError):
        logging.warning("Could not set resource limits. 'resource' module may not be available on this OS.")

@with_retry(max_retries=2, retryable_exceptions=(NetworkRetryableError, TimeoutRetryableError))
def run_hydra_with_progress(job_id, ip, protocol, user_wl, pass_wl, timeout=None):
    """Enhanced Hydra execution with progress tracking and retry mechanism"""
    result_dict = {}
    proc = None
    
    # Use timeout parameter or default
    if timeout is None:
        timeout = app.config['HYDRA_TIMEOUT_SECONDS']
    
    try:
        JobManager.update_job_progress(job_id, 20, "Locating Hydra binary")
        
        # Use full path to hydra binary to avoid PATH issues
        hydra_cmd = '/usr/bin/hydra'
        if not os.path.exists(hydra_cmd):
            # Try common locations
            for path in ['/usr/local/bin/hydra', '/opt/hydra/hydra', 'hydra']:
                if os.path.exists(path) or path == 'hydra':
                    hydra_cmd = path
                    break
        
        JobManager.update_job_progress(job_id, 30, "Starting Hydra attack process")
        
        command = [hydra_cmd, '-L', '-', '-P', '-', f'{protocol}://{ip}']
        proc = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
            text=True, preexec_fn=set_resource_limits,
            env=dict(os.environ, PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin')
        )
        
        # Update job status and PID
        JobManager.update_job_progress(job_id, 40, f"Hydra process started (PID: {proc.pid})", "running")
        
        # Update PID in database
        with app.app_context():
            db = sqlite3.connect(app.config['DATABASE_PATH'])
            db.execute("UPDATE jobs SET pid = ? WHERE id = ?", (proc.pid, job_id))
            db.commit()
            db.close()

        JobManager.update_job_progress(job_id, 60, "Hydra attack in progress...")
        
        stdout, stderr = proc.communicate(input=f"{user_wl}\n{pass_wl}", timeout=timeout)
        
        JobManager.update_job_progress(job_id, 90, "Processing Hydra results")
        
        if stderr and "error" in stderr.lower():
            result_dict = {"status": "error", "message": f"Hydra Error: {stderr}"}
        else: 
            credentials_found = "login:" in stdout.lower() if stdout else False
            if credentials_found:
                result_dict = {"status": "success", "data": stdout, "credentials_found": True}
                JobManager.update_job_progress(job_id, 100, "Credentials found!", "done")
            else:
                result_dict = {"status": "success", "data": "No credentials found.", "credentials_found": False}
                JobManager.update_job_progress(job_id, 100, "Attack completed - no credentials found", "done")
            
    except subprocess.TimeoutExpired:
        enhanced_logger.log_operation_failure(
            "Hydra Attack",
            getattr(g, 'user_context', {'api_key_id': 'System'}),
            f"Process timed out after {timeout}s",
            f"Job ID: {job_id} | PID: {proc.pid if proc else 'N/A'}"
        )
        if proc: 
            proc.kill()
            proc.wait()
        result_dict = {"status": "error", "message": f"Hydra process timed out after {timeout} seconds."}
        JobManager.update_job_progress(job_id, 100, "Attack timed out", "error")
        raise TimeoutRetryableError(f"Hydra process timed out after {timeout} seconds")
        
    except FileNotFoundError as e:
        result_dict = {"status": "error", "message": f"Hydra binary not found. Please ensure hydra is installed."}
        JobManager.update_job_progress(job_id, 100, "Hydra binary not found", "error")
        enhanced_logger.log_operation_failure(
            "Hydra Attack",
            getattr(g, 'user_context', {'api_key_id': 'System'}),
            "Hydra binary not found",
            f"Job ID: {job_id} | Error: {e}"
        )
        raise AppError(result_dict["message"])
        
    except Exception as e:
        result_dict = {"status": "error", "message": f"An unexpected error occurred: {e}"}
        JobManager.update_job_progress(job_id, 100, f"Unexpected error: {str(e)[:50]}...", "error")
        enhanced_logger.log_operation_failure(
            "Hydra Attack",
            getattr(g, 'user_context', {'api_key_id': 'System'}),
            str(e),
            f"Job ID: {job_id}"
        )
        raise NetworkRetryableError(str(e)) if "network" in str(e).lower() else AppError(str(e))
    
    finally:
        # Final job result update
        try:
            with app.app_context():
                db = sqlite3.connect(app.config['DATABASE_PATH'])
                db.execute("UPDATE jobs SET result = ?, updated_at = ? WHERE id = ?", 
                          (json.dumps(result_dict), datetime.utcnow().isoformat(), job_id))
                db.commit()
                db.close()
        except Exception as db_error:
            enhanced_logger.log_operation_failure(
                "Database Update",
                getattr(g, 'user_context', {'api_key_id': 'System'}),
                f"Failed to update job result",
                f"Job ID: {job_id} | Error: {db_error}"
            )
    
    return result_dict

# Legacy wrapper for backward compatibility
def run_hydra_in_background(job_id, ip, protocol, user_wl, pass_wl, timeout=None):
    """Legacy wrapper for Hydra execution"""
    return run_hydra_with_progress(job_id, ip, protocol, user_wl, pass_wl, timeout)

@with_retry(max_retries=2, retryable_exceptions=(NetworkRetryableError, TimeoutRetryableError))
def run_exploit_with_progress(job_id, ip, module, timeout=None):
    """Enhanced Metasploit execution with progress tracking"""
    if timeout is None:
        timeout = app.config['MSF_SESSION_TIMEOUT_SECONDS']
    
    try:
        JobManager.update_job_progress(job_id, 20, "Connecting to Metasploit RPC")
        result = scanner.execute_exploit(ip, module, app.config['MSF_PASSWORD'], timeout=timeout)
        
        if result.get('status') == 'success':
            JobManager.update_job_progress(job_id, 100, "Exploit executed successfully", "done")
        elif result.get('status') == 'timeout':
            JobManager.update_job_progress(job_id, 100, "Exploit timed out", "done")
        else:
            JobManager.update_job_progress(job_id, 100, "Exploit failed", "error")
            
    except Exception as e:
        result = {"status": "error", "message": f"Exploit execution failed: {e}"}
        JobManager.update_job_progress(job_id, 100, f"Error: {str(e)[:50]}...", "error")
        enhanced_logger.log_operation_failure(
            "Metasploit Exploit",
            getattr(g, 'user_context', {'api_key_id': 'System'}),
            str(e),
            f"Job ID: {job_id} | Module: {module}"
        )
        
        if "network" in str(e).lower() or "connection" in str(e).lower():
            raise NetworkRetryableError(str(e))
        raise
    
    finally:
        # Update job result
        try:
            with app.app_context():
                db = sqlite3.connect(app.config['DATABASE_PATH'])
                db.execute("UPDATE jobs SET result = ?, updated_at = ? WHERE id = ?", 
                          (json.dumps(result), datetime.utcnow().isoformat(), job_id))
                db.commit()
                db.close()
        except Exception as db_error:
            enhanced_logger.log_operation_failure(
                "Database Update",
                getattr(g, 'user_context', {'api_key_id': 'System'}),
                f"Failed to update job result",
                f"Job ID: {job_id} | Error: {db_error}"
            )
    
    return result

@with_retry(max_retries=1, retryable_exceptions=(NetworkRetryableError,))
def run_camera_scan_with_progress(job_id, network_cidr):
    """Enhanced camera scan with progress tracking"""
    try:
        JobManager.update_job_progress(job_id, 20, "Starting network discovery")
        discovered_cameras = camera_scanner.find_cameras(network_cidr)
        
        camera_count = len(discovered_cameras)
        if camera_count > 0:
            JobManager.update_job_progress(job_id, 100, f"Found {camera_count} cameras", "done")
        else:
            JobManager.update_job_progress(job_id, 100, "No cameras found", "done")
            
        result_dict = {"status": "success", "data": discovered_cameras, "camera_count": camera_count}
        
    except Exception as e:
        result_dict = {"status": "error", "message": f"Camera scan failed: {e}"}
        JobManager.update_job_progress(job_id, 100, f"Scan failed: {str(e)[:50]}...", "error")
        enhanced_logger.log_operation_failure(
            "Camera Scan",
            getattr(g, 'user_context', {'api_key_id': 'System'}),
            str(e),
            f"Job ID: {job_id} | Network: {network_cidr}"
        )
        
        if "network" in str(e).lower():
            raise NetworkRetryableError(str(e))
        raise
    
    finally:
        # Update job result
        try:
            with app.app_context():
                db = sqlite3.connect(app.config['DATABASE_PATH'])
                db.execute("UPDATE jobs SET result = ?, updated_at = ? WHERE id = ?", 
                          (json.dumps(result_dict), datetime.utcnow().isoformat(), job_id))
                db.commit()
                db.close()
        except Exception as db_error:
            enhanced_logger.log_operation_failure(
                "Database Update",
                getattr(g, 'user_context', {'api_key_id': 'System'}),
                f"Failed to update job result",
                f"Job ID: {job_id} | Error: {db_error}"
            )
    
    return result_dict

@with_retry(max_retries=1, retryable_exceptions=(NetworkRetryableError,))
def run_network_scan_with_progress(job_id, target_cidr, interface):
    """Enhanced network scan with progress tracking"""
    try:
        JobManager.update_job_progress(job_id, 20, f"Starting ARP scan on {interface}")
        
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(app.config['PRIV_SOCKET_PATH'])
            s.sendall(json.dumps({"target_cidr": target_cidr, "interface": interface}).encode('utf-8'))
            s.shutdown(socket.SHUT_WR)
            
            JobManager.update_job_progress(job_id, 60, "Receiving scan results")
            
            response = b"".join(iter(lambda: s.recv(4096), b''))
            scan_results = json.loads(response.decode('utf-8'))
            
            device_count = len(scan_results) if isinstance(scan_results, list) else 0
            if device_count > 0:
                JobManager.update_job_progress(job_id, 100, f"Found {device_count} devices", "done")
            else:
                JobManager.update_job_progress(job_id, 100, "No devices found", "done")
            
            result_dict = {"status": "success", "data": scan_results, "device_count": device_count}
            
    except Exception as e:
        result_dict = {"status": "error", "message": f"Network scan failed: {e}"}
        JobManager.update_job_progress(job_id, 100, f"Scan failed: {str(e)[:50]}...", "error")
        enhanced_logger.log_operation_failure(
            "Network Scan",
            getattr(g, 'user_context', {'api_key_id': 'System'}),
            str(e),
            f"Job ID: {job_id} | Target: {target_cidr}"
        )
        
        if "network" in str(e).lower() or "connection" in str(e).lower():
            raise NetworkRetryableError(str(e))
        raise
    
    finally:
        # Update job result
        try:
            with app.app_context():
                db = sqlite3.connect(app.config['DATABASE_PATH'])
                db.execute("UPDATE jobs SET result = ?, updated_at = ? WHERE id = ?", 
                          (json.dumps(result_dict), datetime.utcnow().isoformat(), job_id))
                db.commit()
                db.close()
        except Exception as db_error:
            enhanced_logger.log_operation_failure(
                "Database Update",
                getattr(g, 'user_context', {'api_key_id': 'System'}),
                f"Failed to update job result",
                f"Job ID: {job_id} | Error: {db_error}"
            )
    
    return result_dict

# Legacy wrappers for backward compatibility
def run_exploit_in_background(job_id, ip, module):
    """Legacy wrapper for exploit execution"""
    return run_exploit_with_progress(job_id, ip, module)

def run_camera_scan_in_background(job_id, network_cidr):
    """Legacy wrapper for camera scan"""
    return run_camera_scan_with_progress(job_id, network_cidr)

# --- 7. API Endpoints ---
@app.route('/')
def index(): return render_template('kam_grbs5.html')

@app.route('/api/scan_network', methods=['POST'])
@require_api_key
def api_scan_network():
    data = request.get_json(); target_cidr = validate_scope(validate_cidr(data.get('target_cidr'))); interface = validate_interface(data.get('interface'))
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(app.config['PRIV_SOCKET_PATH']); s.sendall(json.dumps({"target_cidr": target_cidr, "interface": interface}).encode('utf-8')); s.shutdown(socket.SHUT_WR)
            response = b"".join(iter(lambda: s.recv(4096), b''))
            return jsonify(json.loads(response.decode('utf-8')))
    except Exception as e: raise AppError(f"Privileged service communication error: {e}", 500)

@app.route('/api/test_credentials', methods=['POST'])
@require_api_key
def api_test_credentials():
    data = request.get_json(); ip = validate_scope(validate_ip(data.get('ip'))); protocol = data.get('protocol')
    if protocol not in ['ssh', 'ftp', 'http']: raise AppError("Invalid protocol")
    return jsonify(scanner.test_connectivity(ip, protocol))

@app.route('/api/hydra_attack', methods=['POST'])
@require_api_key
def api_hydra_attack():
    data = request.get_json()
    ip = validate_scope(validate_ip(data.get('ip')))
    protocol = data.get('protocol')
    if protocol not in ['ssh', 'ftp', 'http-get']: 
        raise AppError("Invalid protocol")
    
    user_wl = data.get('username_wordlist', '')
    pass_wl = data.get('password_wordlist', '')
    timeout = data.get('timeout', app.config['HYDRA_TIMEOUT_SECONDS'])
    priority = data.get('priority', 5)
    
    # Validate that we have wordlists
    if not user_wl.strip():
        raise AppError("Username wordlist is required")
    if not pass_wl.strip():
        raise AppError("Password wordlist is required")
    
    job_id = secrets.token_hex(16)
    JobManager.create_job(job_id, g.api_key_identifier, 'hydra_attack', priority)
    
    enhanced_logger.log_operation_start(
        "Hydra Attack Job",
        g.user_context,
        f"Target: {ip} | Protocol: {protocol} | Timeout: {timeout}s"
    )
    
    executor.submit(run_hydra_with_progress, job_id, ip, protocol, user_wl, pass_wl, timeout)
    return jsonify({"job_id": job_id, "status": "queued", "message": "Hydra attack job created successfully"}), 202

@app.route('/api/execute_exploit', methods=['POST'])
@require_api_key
def api_execute_exploit():
    data = request.get_json()
    ip = validate_scope(validate_ip(data.get('ip')))
    module = validate_module(data.get('module'))
    timeout = data.get('timeout', app.config['MSF_SESSION_TIMEOUT_SECONDS'])
    priority = data.get('priority', 5)
    
    job_id = secrets.token_hex(16)
    JobManager.create_job(job_id, g.api_key_identifier, 'metasploit_exploit', priority)
    
    enhanced_logger.log_operation_start(
        "Metasploit Exploit Job",
        g.user_context,
        f"Target: {ip} | Module: {module} | Timeout: {timeout}s"
    )
    
    executor.submit(run_exploit_with_progress, job_id, ip, module, timeout)
    return jsonify({"job_id": job_id, "status": "queued", "message": "Metasploit exploit job created successfully"}), 202

@app.route('/api/scan_cameras', methods=['POST'])
@require_api_key
def api_scan_cameras():
    data = request.get_json()
    network_cidr = validate_cidr(data.get('network_cidr'))
    priority = data.get('priority', 5)
    
    job_id = secrets.token_hex(16)
    JobManager.create_job(job_id, g.api_key_identifier, 'camera_scan', priority)
    
    enhanced_logger.log_operation_start(
        "Camera Scan Job",
        g.user_context,
        f"Network: {network_cidr}"
    )
    
    executor.submit(run_camera_scan_with_progress, job_id, network_cidr)
    return jsonify({"job_id": job_id, "status": "queued", "message": "Camera scan job created successfully"}), 202

@app.route('/api/job_status/<job_id>', methods=['GET'])
@require_api_key
def get_job_status(job_id):
    job = get_db().execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not job: raise AppError("Job not found", 404)
    if job['owner_key'] != g.api_key_identifier: raise AppError("Forbidden", 403)
    
    job_dict = dict(job)
    # Parse result if it exists
    if job_dict.get('result'):
        try:
            job_dict['result'] = json.loads(job_dict['result'])
        except (json.JSONDecodeError, TypeError):
            pass  # Keep as string if not valid JSON
    
    return jsonify(job_dict)

@app.route('/api/jobs', methods=['GET'])
@require_api_key
def list_jobs():
    """List jobs for the current user with optional filtering"""
    status_filter = request.args.get('status')
    job_type_filter = request.args.get('type')
    limit = min(int(request.args.get('limit', 50)), 100)  # Cap at 100
    offset = int(request.args.get('offset', 0))
    
    query = "SELECT * FROM jobs WHERE owner_key = ?"
    params = [g.api_key_identifier]
    
    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)
    
    if job_type_filter:
        query += " AND type = ?"
        params.append(job_type_filter)
    
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    jobs = get_db().execute(query, params).fetchall()
    
    job_list = []
    for job in jobs:
        job_dict = dict(job)
        # Parse result if it exists
        if job_dict.get('result'):
            try:
                job_dict['result'] = json.loads(job_dict['result'])
            except (json.JSONDecodeError, TypeError):
                pass
        job_list.append(job_dict)
    
    return jsonify({
        "jobs": job_list,
        "total": len(job_list),
        "limit": limit,
        "offset": offset
    })

@app.route('/api/jobs/statistics', methods=['GET'])
@require_api_key
def get_job_statistics():
    """Get job statistics for the current user"""
    stats = JobManager.get_job_statistics(g.api_key_identifier)
    return jsonify({
        "statistics": stats,
        "user": g.api_key_identifier
    })

@app.route('/api/jobs/cleanup', methods=['POST'])
@require_api_key
def cleanup_jobs():
    """Manually trigger job cleanup (admin-like function)"""
    try:
        deleted_count = JobManager.cleanup_expired_jobs()
        return jsonify({
            "message": f"Cleanup completed successfully",
            "deleted_jobs": deleted_count
        })
    except Exception as e:
        enhanced_logger.log_operation_failure(
            "Manual Job Cleanup",
            g.user_context,
            str(e)
        )
        raise AppError(f"Cleanup failed: {e}")

@app.route('/api/attack', methods=['POST'])
@require_api_key
def unified_attack_endpoint():
    """Unified endpoint for executing various types of attacks"""
    data = request.get_json()
    
    if not data:
        raise AppError("Request body is required")
    
    attack_type = data.get('attack_type')
    if not attack_type:
        raise AppError("attack_type is required")
    
    parameters = data.get('parameters', {})
    priority = data.get('priority', 5)
    
    # Validate priority
    if not isinstance(priority, int) or priority < 1 or priority > 10:
        raise AppError("Priority must be an integer between 1 and 10")
    
    try:
        job_id = secrets.token_hex(16)
        JobManager.create_job(job_id, g.api_key_identifier, attack_type, priority)
        
        enhanced_logger.log_operation_start(
            f"Unified Attack: {attack_type}",
            g.user_context,
            f"Job ID: {job_id} | Priority: {priority}"
        )
        
        # Execute attack using the framework
        executor.submit(attack_framework.execute_attack, attack_type, job_id, parameters)
        
        return jsonify({
            "job_id": job_id,
            "attack_type": attack_type,
            "status": "queued",
            "message": f"{attack_type} attack job created successfully",
            "priority": priority
        }), 202
        
    except Exception as e:
        enhanced_logger.log_operation_failure(
            f"Unified Attack Creation: {attack_type}",
            g.user_context,
            str(e)
        )
        raise

@app.route('/api/attack/modules', methods=['GET'])
@require_api_key
def list_attack_modules():
    """List available attack modules and their parameters"""
    return jsonify({
        "available_modules": attack_framework.get_available_modules(),
        "total_modules": len(attack_framework.modules)
    })

def kill_process_tree(pid):
    """Kill a process and all its children."""
    import psutil
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        
        # First, try to terminate gracefully
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        
        try:
            parent.terminate()
        except psutil.NoSuchProcess:
            return True  # Process already gone
        
        # Wait up to 5 seconds for graceful termination
        gone, alive = psutil.wait_procs(children + [parent], timeout=5)
        
        # Force kill any remaining processes
        for p in alive:
            try:
                p.kill()
                logging.warning(f"Force killed process {p.pid}")
            except psutil.NoSuchProcess:
                pass
        
        return True
        
    except psutil.NoSuchProcess:
        return True  # Process already gone
    except Exception as e:
        logging.error(f"Error killing process tree for PID {pid}: {e}")
        return False

def simple_kill_process(pid):
    """Fallback process killing without psutil."""
    try:
        # Try SIGTERM first
        os.kill(pid, signal.SIGTERM)
        
        # Wait a bit for graceful termination
        import time
        for _ in range(10):
            try:
                # Check if process still exists
                os.kill(pid, 0)  # This doesn't kill, just checks existence
                time.sleep(0.5)
            except ProcessLookupError:
                return True  # Process terminated
        
        # If still running, force kill
        try:
            os.kill(pid, signal.SIGKILL)
            logging.warning(f"Force killed process {pid} with SIGKILL")
            return True
        except ProcessLookupError:
            return True  # Process already gone
            
    except ProcessLookupError:
        return True  # Process already gone
    except Exception as e:
        logging.error(f"Error killing process {pid}: {e}")
        return False

@app.route('/api/job/<job_id>/cancel', methods=['POST'])
@require_api_key
def cancel_job(job_id):
    db = get_db()
    job = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not job: 
        raise AppError("Job not found", 404)
    if job['owner_key'] != g.api_key_identifier: 
        raise AppError("Forbidden", 403)
    if job['status'] not in ['queued', 'running']: 
        raise AppError(f"Job in state '{job['status']}' cannot be cancelled", 409)
    
    cancellation_success = True
    
    if job['status'] == 'running' and job['pid']:
        logging.info(f"Attempting to cancel job {job_id} with PID {job['pid']}")
        
        # Try advanced process killing first
        try:
            cancellation_success = kill_process_tree(job['pid'])
        except ImportError:
            # Fallback if psutil not available
            logging.warning("psutil not available, using simple process killing")
            cancellation_success = simple_kill_process(job['pid'])
        
        if not cancellation_success:
            logging.error(f"Failed to kill process {job['pid']} for job {job_id}")
    
    # Update job status regardless of kill success
    db.execute("UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?", 
               ('cancelled', datetime.utcnow().isoformat(), job_id))
    db.commit()
    
    response_data = {
        "status": "cancellation_requested", 
        "job_id": job_id,
        "process_killed": cancellation_success if job.get('pid') else None
    }
    
    return jsonify(response_data)

def generate_camera_frames(ip, port):
    """Generate camera frames for streaming with proper error handling."""
    # Common camera stream URLs to try
    stream_urls = [
        f"rtsp://{ip}:{port}/live/ch00_1",
        f"http://{ip}:{port}/video.cgi",
        f"rtsp://{ip}:{port}/stream",
        f"http://{ip}:{port}/mjpeg",
        f"rtsp://{ip}:{port}/",
        f"http://{ip}:{port}/"
    ]
    
    cap = None
    successful_url = None
    
    # Try each URL until one works
    for url in stream_urls:
        try:
            test_cap = cv2.VideoCapture(url)
            if test_cap.isOpened():
                # Test if we can actually read a frame
                ret, frame = test_cap.read()
                if ret and frame is not None:
                    cap = test_cap
                    successful_url = url
                    break
                else:
                    test_cap.release()
            else:
                test_cap.release()
        except Exception as e:
            logging.warning(f"Failed to test camera URL {url}: {e}")
            if test_cap:
                test_cap.release()
    
    if not cap or successful_url is None:
        logging.error(f"Could not open any video stream for {ip}:{port}")
        # Return a single error frame
        error_frame = b'--frame\r\nContent-Type: text/plain\r\n\r\nNo camera stream available\r\n'
        yield error_frame
        return
    
    logging.info(f"Successfully connected to camera stream: {successful_url}")
    
    frame_count = 0
    max_frames = 3600  # Limit streaming to prevent resource exhaustion
    
    try:
        while frame_count < max_frames:
            success, frame = cap.read()
            if not success:
                logging.warning(f"Failed to read frame {frame_count} from {successful_url}")
                break
                
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ret:
                logging.warning(f"Failed to encode frame {frame_count}")
                continue
                
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            frame_count += 1
            
    except Exception as e:
        logging.error(f"Error during camera streaming: {e}")
    finally:
        if cap:
            cap.release()
            logging.info(f"Released camera stream for {ip}:{port}")

@app.route('/api/camera_stream/<ip>/<int:port>')
@require_api_key
def camera_stream(ip, port):
    return Response(generate_camera_frames(validate_ip(ip), port), mimetype='multipart/x-mixed-replace; boundary=frame')

# --- 8. Scheduled Tasks ---
import threading
import atexit

def schedule_job_cleanup():
    """Schedule periodic job cleanup"""
    def cleanup_worker():
        while True:
            try:
                with app.app_context():
                    deleted_count = JobManager.cleanup_expired_jobs()
                    if deleted_count > 0:
                        enhanced_logger.log_operation_success(
                            "Scheduled Job Cleanup",
                            {'api_key_id': 'System'},
                            f"Cleaned up {deleted_count} expired jobs"
                        )
            except Exception as e:
                enhanced_logger.log_operation_failure(
                    "Scheduled Job Cleanup",
                    {'api_key_id': 'System'},
                    str(e)
                )
            
            # Wait 1 hour before next cleanup
            time.sleep(3600)
    
    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()
    return cleanup_thread

# --- 9. Main Execution Block ---
if __name__ == '__main__':
    # Initialize or migrate database
    if not os.path.exists(app.config['DATABASE_PATH']): 
        init_db()
    else:
        # Check if we need to migrate the database schema
        try:
            with app.app_context():
                db = get_db()
                # Check if new columns exist
                cursor = db.execute("PRAGMA table_info(jobs)")
                columns = [row[1] for row in cursor.fetchall()]
                
                if 'progress' not in columns:
                    enhanced_logger.log_operation_start(
                        "Database Migration",
                        {'api_key_id': 'System'},
                        "Updating database schema"
                    )
                    
                    # Add new columns
                    db.execute("ALTER TABLE jobs ADD COLUMN progress INTEGER DEFAULT 0")
                    db.execute("ALTER TABLE jobs ADD COLUMN progress_message TEXT")
                    db.execute("ALTER TABLE jobs ADD COLUMN error_count INTEGER DEFAULT 0")
                    db.execute("ALTER TABLE jobs ADD COLUMN max_retries INTEGER DEFAULT 3")
                    db.execute("ALTER TABLE jobs ADD COLUMN expires_at TEXT")
                    db.execute("ALTER TABLE jobs ADD COLUMN priority INTEGER DEFAULT 5")
                    
                    # Create indexes
                    db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_expires_at ON jobs(expires_at)")
                    db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status_created_at ON jobs(status, created_at)")
                    db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_owner_status ON jobs(owner_key, status)")
                    
                    db.commit()
                    
                    enhanced_logger.log_operation_success(
                        "Database Migration",
                        {'api_key_id': 'System'},
                        "Database schema updated successfully"
                    )
                    
        except Exception as e:
            enhanced_logger.log_operation_failure(
                "Database Migration",
                {'api_key_id': 'System'},
                str(e)
            )
            print(f"Warning: Database migration failed: {e}")
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s [%(levelname)s] (WebServer) %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('neonhack.log') if os.access('.', os.W_OK) else logging.StreamHandler()
        ]
    )
    
    # Start scheduled cleanup
    cleanup_thread = schedule_job_cleanup()
    
    # Register cleanup on exit
    def cleanup_on_exit():
        enhanced_logger.log_operation_success(
            "Server Shutdown",
            {'api_key_id': 'System'},
            "NeonHack server shutting down gracefully"
        )
    
    atexit.register(cleanup_on_exit)
    
    print("--- NEONHACK // Secure Backend // ENHANCED v6.0 ---")
    print(f"--- API Key: {app.config['SECRET_API_KEY']} ---")
    print("--- Enhanced Features: Logging, Progress Tracking, Retry Mechanisms, Modular Attacks ---")
    
    enhanced_logger.log_operation_success(
        "Server Startup",
        {'api_key_id': 'System'},
        "NeonHack server started with enhanced features"
    )
    
    app.run(host='0.0.0.0', port=5000, debug=False)