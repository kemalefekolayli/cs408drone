import socket
import json

HOST, PORT = '127.0.0.1', 4000

def send_to_central(payload: dict):
    data = json.dumps(payload) + '\n'
    with socket.create_connection((HOST, PORT)) as sock:
        sock.sendall(data.encode('utf-8'))
