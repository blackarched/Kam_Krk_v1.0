Kam Krk v1.0 // The only offensive tool you need.
!(https://i.imgur.com/8Yv6Z8R.png)

Kam_Krk is a web-based, multi-function network security and reconnaissance suite. Designed with a high-tech cyberpunk aesthetic, this tool provides a powerful, all-in-one interface for local network analysis, penetration testing, and live surveillance from your browser.

✨ Core Capabilities
Kam_Krk consolidates several powerful security tools into a single, intuitive dashboard.

📡 Reconnaissance & Discovery
This is the tool's ability to map out and identify what's on your network.

Network Device Discovery: It effectively discovers and lists all active devices on your local network segment (e.g., 192.168.1.0/24). This reveals the IP and MAC address of every connected computer, phone, and IoT device, giving you a complete picture of your network.

WiFi Camera Scanner: The tool can specifically hunt for discoverable WiFi cameras. It scans devices, probes them on common ports, and intelligently identifies known camera models, revealing potential surveillance points on the network.

Port Connectivity Testing: You can perform a quick port check on any target IP to see if basic services like SSH (22), FTP (21), and HTTP (80) are running and accessible before launching a more complex operation.

⚔️ Penetration Testing
Once a target is identified, the tool provides capabilities to test its security.

Hydra Brute-Force Attacks: Launch a high-speed dictionary attack against login forms. You can provide lists of common usernames and passwords to automatically test them against a target's SSH, FTP, or web login service to find weak credentials.

Metasploit Exploit Execution: The tool can execute specific, whitelisted Metasploit modules against a target. This allows you to run a known exploit, such as the vsftpd_234_backdoor, to test if a service is vulnerable.

👁️ Live Surveillance
The tool integrates two distinct live video features for monitoring.

Network Camera Streaming: After discovering a WiFi camera, you can view its live video feed directly in your browser. The server securely connects to the camera's stream and proxies it to a modal window in the interface.

Local Webcam Feed: The interface includes a "Biometric Scanner" that can activate your own local webcam. The feed is entirely local to your browser and is not transmitted, allowing you to monitor your immediate surroundings.

🛡️ System & Security
The entire suite is built on a secure and robust foundation.

Secure Job Management: All long-running tasks are handled as background jobs. You can queue multiple operations, monitor their real-time status, and cancel any job directly from the interface.

Authorization Control: Access to the entire tool is protected by a server-side API key. All scanning and attack functions are restricted to an authorized IP whitelist you configure, preventing accidental or malicious use against out-of-scope targets.

⚙️ How It Works: The Technology Behind the Tool
Kam_Krk uses a secure two-part architecture to separate tasks that require elevated permissions from the main web interface.

app.py (The Flask Web Server): This is the brain of the operation. It runs as a standard user, serves the web interface, handles all your requests, manages the job database, and executes unprivileged tools like Hydra and Metasploit.

privileged_scanner_service.py (The Privileged Service): This is a small, dedicated script that runs with sudo. Its only job is to perform the ARP scan, which requires root privileges. It listens on a secure local socket for requests from app.py, ensuring that elevated permissions are used for the shortest possible time and for a single, specific task.

scanner_final.py & camera_scanner.py: These are the library files containing the logic for interacting with external tools and identifying cameras.

kam_grbs5.html: The all-in-one frontend you interact with in your browser.

🚀 Installation and Setup
Follow these steps precisely to ensure a smooth setup.

Step 1: Prerequisites
Make sure you have the following installed on your Linux-based system (Debian/Ubuntu/Kali recommended):

Python 3.8+ and Pip

Git

Hydra: sudo apt-get install hydra -y

Metasploit Framework: Follow the official installation guide from Rapid7.

Step 2: Clone the Repository
Open your terminal and clone this project.

Bash

git clone <repository_url>
cd <repository_folder>
Step 3: Install Python Dependencies
Create a requirements.txt file with the content below, then install the dependencies.

# requirements.txt
Flask
Flask-Limiter
scapy
requests
opencv-python
pymetasploit3
Now, run the installation command:

Bash

pip install -r requirements.txt
Step 4: Configure the Environment
The tool uses environment variables for security. Set them in your terminal.

Bash

# Generate a secure, random key for the API
export Kam_Krk_API_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')

# Set a password for the Metasploit RPC service (msfrpcd)
export MSF_PASSWORD="your_strong_msf_password"

# Echo the API key so you can copy it for later use
echo "Your API Key is: $Kam_Krk_API_KEY"
Remember to save the API key! You'll need it to use the tool.

Step 5: Run the Metasploit RPC Service
Metasploit must be running in the background for the exploit module to work. Open a new terminal and run:

Bash

msfrpcd -P "$MSF_PASSWORD" -n -f
Leave this terminal running.

Step 6: Run the Privileged Scanner Service
The ARP and camera scans require root privileges. Open another new terminal and run:

Bash

sudo python3 privileged_scanner_service.py --socket /tmp/priv_scanner.sock
This script will listen for scan requests. Leave this terminal running.

Step 7: Run the Main Application
Finally, in your original terminal (where you set the environment variables), run the main Flask application:

Bash

python3 app.py
Step 8: Access the Interface
Open your web browser and navigate to:
http://127.0.0.1:5000

Enter the API key you saved from Step 4 into the "AUTHORIZATION" card, and you're ready to go!

🚨 Troubleshooting
If you run into issues, check these common solutions.

Problem: "Network Scan" or "Camera Scan" fails or finds nothing.

Solution: This is almost always a permissions issue. Ensure you are running privileged_scanner_service.py with sudo as shown in Step 6. Also, check that your system's firewall is not blocking the packets.

Problem: "Hydra attack" or "Exploit Execution" fails immediately.

Solution: Make sure you have installed hydra and metasploit-framework correctly and that they are in your system's PATH. For exploits, double-check that the msfrpcd service is running in its own terminal (Step 5) and that the MSF_PASSWORD environment variable matches.

Problem: "Video stream doesn't work" for a discovered camera.

Solution: The tool tries a few common stream URLs for camera models. Some cameras use non-standard URLs. This may require manually editing the stream_urls list in the generate_camera_frames function within app.py for that specific model.

Problem: pip install opencv-python fails with an error.

Solution: OpenCV can have system-level dependencies. On a headless server or minimal Linux install, you may need to install them first. For Debian/Ubuntu, try:

Bash

sudo apt-get install libgl1-mesa-glx -y
Disclaimer: This tool is intended for educational purposes and for use in authorized security testing environments only. Do not use this tool for any illegal activities.