'''
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import socket
import time
import json
from datetime import datetime
import argparse
from logger import setup_logger  # Make sure logger.py is in root

# Set up logger for this test client
logger = setup_logger('test_client', 'logs/server/test_client.log')

def send_reading(host, port, payload):
    backoff = 1
    MAX_BACKOFF = 16

    while True:
        try:
            with socket.create_connection((host, port), timeout=5) as sock:
                sock.sendall((json.dumps(payload) + '\n').encode('utf-8'))
                logger.info(f"Sent payload to {host}:{port} → {json.dumps(payload)}")
                print(f"✅ Sent: {payload}")
                return
        except Exception as e:
            logger.warning(f"Retrying ({backoff}s): {e}")
            print(f"⚠️  Error: {e}, retrying in {backoff} seconds...")
            time.sleep(backoff)
            backoff = min(MAX_BACKOFF, backoff * 2)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Send test sensor data to the drone server.")
    parser.add_argument('--host', default='127.0.0.1', help='Drone server IP address')
    parser.add_argument('--port', type=int, default=5000, help='Drone server port')
    parser.add_argument('--sensor-id', default='drone1_s1', help='Sensor ID to use in payload')
    args = parser.parse_args()

    payload = {
        "sensor_id": args.sensor_id,
        "temperature": 20.0,
        "pressure": 1013.0,
        "altitude": 100.0,
        "motor_energies": [10, 20, 30, 40],
        "timestamp": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    }

    send_reading(args.host, args.port, payload)
'''