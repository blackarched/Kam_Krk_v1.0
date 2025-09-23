# camera_scanner.py
import requests
import re
from scapy.all import srp, Ether, ARP
import logging
from concurrent.futures import ThreadPoolExecutor

# Configurable settings
CAMERA_MODELS = {
    "Wyze Cam": re.compile(r"WYZE", re.IGNORECASE),
    "Foscam": re.compile(r"Foscam", re.IGNORECASE),
    "Dahua": re.compile(r"Dahua", re.IGNORECASE),
    "Amcrest": re.compile(r"Amcrest", re.IGNORECASE),
    "Hikvision": re.compile(r"Hikvision", re.IGNORECASE),
}
PROBE_PORTS = [80, 8080, 88, 554] # Common web interface and RTSP ports

def network_scan(network_cidr):
    """
    Performs a more reliable ARP scan using Scapy's srp function.
    NOTE: This function requires root privileges to craft raw packets.
    """
    logging.info(f"Initiating ARP scan for WiFi cameras on {network_cidr}...")
    try:
        ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst=network_cidr), timeout=3, verbose=0)
        devices = [{'ip': rcv.psrc, 'mac': rcv.hwsrc} for snd, rcv in ans]
        logging.info(f"ARP scan found {len(devices)} devices.")
        return devices
    except Exception as e:
        logging.error(f"ARP scan failed. This part of the script likely needs to be run with root privileges. Error: {e}")
        return []

def detect_camera_model(device_ip):
    """
    Probes a device on common ports to identify if it's a known camera model.
    """
    for port in PROBE_PORTS:
        try:
            # Check for HTTP headers first, as they are very revealing
            with requests.get(f"http://{device_ip}:{port}", timeout=2, stream=True) as r:
                # Check server header
                server_header = r.headers.get('Server', '')
                for model, pattern in CAMERA_MODELS.items():
                    if pattern.search(server_header):
                        logging.info(f"Found {model} camera at {device_ip}:{port} via Server header.")
                        return {"ip": device_ip, "model": model, "port": port}
                
                # Check body content if header is not conclusive
                content_sample = r.text[:512] # Read a small sample
                for model, pattern in CAMERA_MODELS.items():
                    if pattern.search(content_sample):
                        logging.info(f"Found {model} camera at {device_ip}:{port} via page content.")
                        return {"ip": device_ip, "model": model, "port": port}
                        
        except requests.RequestException:
            continue # Port is not open or not an HTTP server
    return None

def find_cameras(network_cidr):
    """
    Orchestrates the network scan and detection process.
    Returns a list of discovered camera dictionaries.
    """
    devices = network_scan(network_cidr)
    if not devices:
        return []

    discovered_cameras = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_ip = {executor.submit(detect_camera_model, device['ip']): device['ip'] for device in devices}
        for future in future_to_ip:
            result = future.result()
            if result:
                discovered_cameras.append(result)
    
    return discovered_cameras