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
from datetime import datetime
from functools import wraps
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, jsonify, render_template, request, g, Response

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

# --- 2. Application and Database Initialization ---
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

# --- 3. Custom Error Handling ---
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
        # Allow API key from header (for standard API calls) 
        # or query param (for browser resources like <img> tags).
        api_key = request.headers.get('X-API-Key') or request.args.get('apiKey')
        
        if not api_key or not secrets.compare_digest(api_key, app.config['SECRET_API_KEY']):
            logging.warning(f"Failed API Key auth attempt from IP: {request.remote_addr}")
            raise AppError("Unauthorized: Invalid or missing API Key", 401)
        
        g.api_key_identifier = api_key[:8]
        logging.info(f"API Key '{g.api_key_identifier}' accessed endpoint: {request.path}")
        return f(*args, **kwargs)
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

def run_hydra_in_background(job_id, ip, protocol, user_wl, pass_wl, timeout=None):
    result_dict = {}
    proc = None
    db_conn = None
    
    # Use timeout parameter or default
    if timeout is None:
        timeout = app.config['HYDRA_TIMEOUT_SECONDS']
        
    try:
        # Use full path to hydra binary to avoid PATH issues
        hydra_cmd = '/usr/bin/hydra'
        if not os.path.exists(hydra_cmd):
            # Try common locations
            for path in ['/usr/local/bin/hydra', '/opt/hydra/hydra', 'hydra']:
                if os.path.exists(path) or path == 'hydra':
                    hydra_cmd = path
                    break
        
        command = [hydra_cmd, '-L', '-', '-P', '-', f'{protocol}://{ip}']
        proc = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
            text=True, preexec_fn=set_resource_limits,
            env=dict(os.environ, PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin')
        )
        
        # Update job status and PID with proper error handling
        try:
            with app.app_context():
                db_conn = sqlite3.connect(app.config['DATABASE_PATH'])
                db_conn.execute("UPDATE jobs SET status = ?, pid = ? WHERE id = ?", ('running', proc.pid, job_id))
                db_conn.commit()
                db_conn.close()
                db_conn = None
        except Exception as db_error:
            logging.error(f"Failed to update job {job_id} status: {db_error}")

        stdout, stderr = proc.communicate(input=f"{user_wl}\n{pass_wl}", timeout=timeout)
        
        if stderr: 
            result_dict = {"status": "error", "message": f"Hydra Error: {stderr}"}
        else: 
            result_dict = {"status": "success", "data": stdout or "No credentials found."}
            
    except subprocess.TimeoutExpired:
        logging.warning(f"Job {job_id} timed out. Terminating PID {proc.pid if proc else 'N/A'}.")
        if proc: 
            proc.kill()
            proc.wait()  # Wait for process to actually terminate
        result_dict = {"status": "error", "message": "Process timed out."}
    except FileNotFoundError as e:
        result_dict = {"status": "error", "message": f"Hydra binary not found. Please ensure hydra is installed. Error: {e}"}
        logging.error(f"Hydra binary not found for job {job_id}: {e}")
    except Exception as e:
        result_dict = {"status": "error", "message": f"An unexpected error occurred: {e}"}
        logging.error(f"Unexpected error in job {job_id}: {e}")
    finally:
        # Ensure database connection is properly closed
        if db_conn:
            try:
                db_conn.close()
            except:
                pass
                
        # Final job status update
        try:
            with app.app_context():
                db_conn = sqlite3.connect(app.config['DATABASE_PATH'])
                db_conn.execute("UPDATE jobs SET status = ?, result = ?, updated_at = ? WHERE id = ?", 
                               ("done", json.dumps(result_dict), datetime.utcnow().isoformat(), job_id))
                db_conn.commit()
                db_conn.close()
        except Exception as db_error:
            logging.error(f"Failed to update final job {job_id} status: {db_error}")

def run_exploit_in_background(job_id, ip, module):
    result = scanner.execute_exploit(ip, module, app.config['MSF_PASSWORD'], timeout=app.config['MSF_SESSION_TIMEOUT_SECONDS'])
    with app.app_context():
        db = sqlite3.connect(app.config['DATABASE_PATH'])
        db.execute("UPDATE jobs SET status = ?, result = ?, updated_at = ? WHERE id = ?", ("done", json.dumps(result), datetime.utcnow().isoformat(), job_id))
        db.commit()
        db.close()

def run_camera_scan_in_background(job_id, network_cidr):
    discovered_cameras = camera_scanner.find_cameras(network_cidr)
    result_dict = {"status": "success", "data": discovered_cameras}
    with app.app_context():
        db = sqlite3.connect(app.config['DATABASE_PATH'])
        db.execute("UPDATE jobs SET status = ?, result = ?, updated_at = ? WHERE id = ?", ("done", json.dumps(result_dict), datetime.utcnow().isoformat(), job_id))
        db.commit()
        db.close()

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
    
    # Validate that we have wordlists
    if not user_wl.strip():
        raise AppError("Username wordlist is required")
    if not pass_wl.strip():
        raise AppError("Password wordlist is required")
    
    job_id = secrets.token_hex(16)
    db = get_db()
    db.execute("INSERT INTO jobs (id, owner_key, type, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)", 
               (job_id, g.api_key_identifier, 'hydra', 'queued', datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))
    db.commit()
    executor.submit(run_hydra_in_background, job_id, ip, protocol, user_wl, pass_wl, timeout)
    return jsonify({"job_id": job_id}), 202

@app.route('/api/execute_exploit', methods=['POST'])
@require_api_key
def api_execute_exploit():
    data = request.get_json(); ip = validate_scope(validate_ip(data.get('ip'))); module = validate_module(data.get('module'))
    job_id = secrets.token_hex(16); db = get_db()
    db.execute("INSERT INTO jobs (id, owner_key, type, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)", (job_id, g.api_key_identifier, 'metasploit', 'queued', datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))
    db.commit()
    executor.submit(run_exploit_in_background, job_id, ip, module)
    return jsonify({"job_id": job_id}), 202

@app.route('/api/scan_cameras', methods=['POST'])
@require_api_key
def api_scan_cameras():
    data = request.get_json(); network_cidr = validate_cidr(data.get('network_cidr'))
    job_id = secrets.token_hex(16); db = get_db()
    db.execute("INSERT INTO jobs (id, owner_key, type, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)", (job_id, g.api_key_identifier, 'camera_scan', 'queued', datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))
    db.commit()
    executor.submit(run_camera_scan_in_background, job_id, network_cidr)
    return jsonify({"job_id": job_id}), 202

@app.route('/api/job_status/<job_id>', methods=['GET'])
@require_api_key
def get_job_status(job_id):
    job = get_db().execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not job: raise AppError("Job not found", 404)
    if job['owner_key'] != g.api_key_identifier: raise AppError("Forbidden", 403)
    return jsonify(dict(job))

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

# --- 8. Main Execution Block ---
if __name__ == '__main__':
    if not os.path.exists(app.config['DATABASE_PATH']): init_db()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] (WebServer) %(message)s')
    print("--- NEONHACK // Secure Backend // HARDENED v5.2 ---")
    print(f"--- API Key: {app.config['SECRET_API_KEY']} ---")
    app.run(host='0.0.0.0', port=5000, debug=False)