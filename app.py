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
    PRIV_SOCKET_PATH = "/run/priv_scanner.sock"
    
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
    if not re.match(r'^[a-zA-Z0-9._:-]{1,16}$', if_str): raise AppError("Invalid network interface name")
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

def run_hydra_in_background(job_id, ip, protocol, user_wl, pass_wl):
    """Run Hydra using the hardened wrapper in scanner_final (temp files), not stdin pipes."""
    try:
        with app.app_context():
            db = sqlite3.connect(app.config['DATABASE_PATH'])
            db.execute("UPDATE jobs SET status = 'running', pid = NULL WHERE id = ?", (job_id,))
            db.commit()

        result_dict = scanner.hydra_attack(
            ip=ip,
            protocol=protocol,
            username_wordlist=user_wl,
            password_wordlist=pass_wl,
            timeout=app.config['HYDRA_TIMEOUT_SECONDS']
        )
    except Exception as e:
        logging.exception("Hydra background task failed")
        result_dict = {"status": "error", "message": f"An unexpected error occurred: {e}"}
    finally:
        with app.app_context():
            db = sqlite3.connect(app.config['DATABASE_PATH'])
            db.execute("UPDATE jobs SET status = ?, result = ?, updated_at = ? WHERE id = ?", ("done", json.dumps(result_dict), datetime.utcnow().isoformat(), job_id))
            db.commit()
            db.close()

def run_exploit_in_background(job_id, ip, module):
    result = scanner.execute_exploit(ip, module, app.config['MSF_PASSWORD'], timeout=app.config['MSF_SESSION_TIMEOUT_SECONDS'])
    with app.app_context():
        db = sqlite3.connect(app.config['DATABASE_PATH'])
        db.execute("UPDATE jobs SET status = ?, result = ?, updated_at = ? WHERE id = ?", ("done", json.dumps(result), datetime.utcnow().isoformat(), job_id))
        db.commit()
        db.close()

def run_camera_scan_in_background(job_id, network_cidr, interface):
    """Use the privileged socket for ARP discovery, then probe cameras from this process."""
    try:
        with app.app_context():
            db = sqlite3.connect(app.config['DATABASE_PATH'])
            db.execute("UPDATE jobs SET status = 'running', pid = NULL WHERE id = ?", (job_id,))
            db.commit()

        # Discover devices via privileged service
        devices = []
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.connect(app.config['PRIV_SOCKET_PATH'])
                s.sendall(json.dumps({"target_cidr": network_cidr, "interface": interface}).encode('utf-8'))
                s.shutdown(socket.SHUT_WR)
                raw = b"".join(iter(lambda: s.recv(4096), b''))
                devices = json.loads(raw.decode('utf-8'))
        except Exception as e:
            logging.exception("Camera scan ARP discovery via privileged service failed")
            result_dict = {"status": "error", "message": f"Privileged service error: {e}"}
            with app.app_context():
                db = sqlite3.connect(app.config['DATABASE_PATH'])
                db.execute("UPDATE jobs SET status = ?, result = ?, updated_at = ? WHERE id = ?", ("done", json.dumps(result_dict), datetime.utcnow().isoformat(), job_id))
                db.commit()
                db.close()
            return

        # Probe each discovered IP for camera fingerprints
        ips = [d.get('ip') for d in devices if isinstance(d, dict) and d.get('ip')]
        discovered = []
        with ThreadPoolExecutor(max_workers=10) as local_exec:
            futures = {local_exec.submit(camera_scanner.detect_camera_model, ip): ip for ip in ips}
            for fut in futures:
                try:
                    res = fut.result()
                    if res:
                        discovered.append(res)
                except Exception:
                    continue

        result_dict = {"status": "success", "data": discovered}
    except Exception as e:
        logging.exception("Camera scan background task failed")
        result_dict = {"status": "error", "message": f"Unexpected error: {e}"}
    finally:
        with app.app_context():
            db = sqlite3.connect(app.config['DATABASE_PATH'])
            db.execute("UPDATE jobs SET status = ?, result = ?, updated_at = ? WHERE id = ?", ("done", json.dumps(result_dict), datetime.utcnow().isoformat(), job_id))
            db.commit()
            db.close()

# --- 7. API Endpoints ---
@app.route('/')
def index(): return render_template('kam_grbs.html')

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
    data = request.get_json(); ip = validate_scope(validate_ip(data.get('ip'))); protocol = data.get('protocol')
    if protocol not in ['ssh', 'ftp', 'http-get']: raise AppError("Invalid protocol")
    user_wl, pass_wl = data.get('username_wordlist', ''), data.get('password_wordlist', '')
    job_id = secrets.token_hex(16); db = get_db()
    db.execute("INSERT INTO jobs (id, owner_key, type, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)", (job_id, g.api_key_identifier, 'hydra', 'queued', datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))
    db.commit()
    executor.submit(run_hydra_in_background, job_id, ip, protocol, user_wl, pass_wl)
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
    data = request.get_json(); network_cidr = validate_cidr(data.get('network_cidr')); interface = validate_interface(data.get('interface'))
    job_id = secrets.token_hex(16); db = get_db()
    db.execute("INSERT INTO jobs (id, owner_key, type, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)", (job_id, g.api_key_identifier, 'camera_scan', 'queued', datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))
    db.commit()
    executor.submit(run_camera_scan_in_background, job_id, network_cidr, interface)
    return jsonify({"job_id": job_id}), 202

@app.route('/api/job_status/<job_id>', methods=['GET'])
@require_api_key
def get_job_status(job_id):
    job = get_db().execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not job: raise AppError("Job not found", 404)
    if job['owner_key'] != g.api_key_identifier: raise AppError("Forbidden", 403)
    return jsonify(dict(job))

@app.route('/api/job/<job_id>/cancel', methods=['POST'])
@require_api_key
def cancel_job(job_id):
    db = get_db(); job = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not job: raise AppError("Job not found", 404)
    if job['owner_key'] != g.api_key_identifier: raise AppError("Forbidden", 403)
    if job['status'] not in ['queued', 'running']: raise AppError(f"Job in state '{job['status']}' cannot be cancelled", 409)
    
    if job['status'] == 'running' and job['pid']:
        try: os.kill(job['pid'], signal.SIGTERM)
        except ProcessLookupError: logging.warning(f"Process PID {job['pid']} for job {job_id} already gone.")
    
    db.execute("UPDATE jobs SET status = 'cancelled' WHERE id = ?", (job_id,)); db.commit()
    return jsonify({"status": "cancellation_requested", "job_id": job_id})

def generate_camera_frames(ip, port):
    stream_urls = [f"rtsp://{ip}:{port}/live/ch00_1", f"http://{ip}:{port}/video.cgi"]
    cap = None
    for url in stream_urls:
        try:
            trial = cv2.VideoCapture(url)
            if trial.isOpened():
                cap = trial
                break
            trial.release()
        except Exception:
            try:
                trial.release()
            except Exception:
                pass
    if not cap:
        logging.error(f"Could not open any known video stream for {ip}:{port}")
        return
    logging.info(f"Successfully connected to camera stream for {ip}:{port}")

    while True:
        success, frame = cap.read()
        if not success:
            break
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    cap.release()

@app.route('/api/camera_stream/<ip>/<int:port>')
@require_api_key
def camera_stream(ip, port):
    return Response(generate_camera_frames(validate_ip(ip), port), mimetype='multipart/x-mixed-replace; boundary=frame')

# --- 8. Main Execution Block ---
if __name__ == '__main__':
    if not os.path.exists(app.config['DATABASE_PATH']): init_db()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] (WebServer) %(message)s')
    print("--- NEONHACK // Secure Backend // HARDENED v5.2 ---")
    app.run(host='0.0.0.0', port=5000, debug=False)