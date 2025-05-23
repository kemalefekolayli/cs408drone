import socket
import json
from logger import setup_logger

central_logger = setup_logger('central_server', 'logs/server/central_server.log')

HOST, PORT = '0.0.0.0', 1000

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen()
    central_logger.info(f"Central server listening on {HOST}:{PORT}")
    print(f"Central server listening on {HOST}:{PORT}")

    while True:
        conn, addr = srv.accept()
        central_logger.info(f"Connection from {addr}")
        print(f"Connection from {addr}")
        with conn:
            buffer = ""
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                buffer += data.decode('utf-8', errors='replace')
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        try:
                            summary = json.loads(line)
                            central_logger.info(f"Received summary: {json.dumps(summary)}")
                            print("Received summary:", summary)
                        except json.JSONDecodeError:
                            central_logger.warning(f"Invalid JSON from {addr}: {line}")
            central_logger.info(f"Connection closed from {addr}")
            print(f"Connection closed from {addr}")
