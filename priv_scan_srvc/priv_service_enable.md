 How to install and enable (summary)

1. Copy the files:

Save the Python script to /usr/local/bin/privileged_scanner_service.py. Make it executable and owned by root:

sudo chown root:root /usr/local/bin/privileged_scanner_service.py
sudo chmod 750 /usr/local/bin/privileged_scanner_service.py

Put priv_scanner.socket and priv_scanner.service into /etc/systemd/system/ (use the unit contents above).



2. Reload systemd and enable socket activation:

sudo systemctl daemon-reload
sudo systemctl enable --now priv_scanner.socket

This will create /run/priv_scanner.sock with the ownership/mode specified by the socket unit.


3. Verify the socket exists and permissions:

ls -l /run/priv_scanner.sock
# should be something like: srw-rw---- 1 root www-data ... /run/priv_scanner.sock


4. From the web application (Flask) side:

Instead of calling sudo python3 privileged_scanner_final.py ... use a small local client to speak the JSON request to /run/priv_scanner.sock.

Example simple client (in Python) to call the service:

import socket, json
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect('/run/priv_scanner.sock')
req = {'target_cidr': '192.168.1.0/24', 'interface': 'eth0'}
s.sendall(json.dumps(req).encode('utf-8'))
# read until EOF
data = b''
while True:
    chunk = s.recv(4096)
    if not chunk:
        break
    data += chunk
s.close()
print(json.loads(data.decode()))

Ensure your Flask process runs as the allowed UID (e.g., www-data) so the service will accept the connection.



5. Disable existing sudo invocation (recommended):

Once the socket service is in place and tested, remove or restrict any sudo rule that allowed the webserver to run arbitrary python3 commands. Prefer disabling sudo entirely for the webserver user for safety.