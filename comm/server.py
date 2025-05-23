import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import socket
import threading
import json
from queue import Queue
from anomaly.consumer import start_consumer
from logger import setup_logger

main_logger = setup_logger('main_server', 'logs/server/main.log')

sensor_queue = Queue()
HOST = '0.0.0.0'
PORT = 5000

def handle_client(conn, addr):
    main_logger.info(f"Connection established from {addr}")
    buffer = ''
    with conn:
        while True:
            try:
                data = conn.recv(1024)
                if not data:
                    break
                buffer += data.decode('utf-8', errors='replace')
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if not line.strip():
                        continue
                    try:
                        reading = json.loads(line)
                        sensor_queue.put(reading)
                        main_logger.info(f"Enqueued reading from {reading.get('sensor_id')}")
                    except json.JSONDecodeError as e:
                        main_logger.warning(f"JSON decode error: {e} | line: {line}")
            except (ConnectionResetError, OSError) as e:
                main_logger.warning(f"Connection lost from {addr}: {e}")
                break
    main_logger.info(f"Connection closed from {addr}")

def serve():
    start_consumer(sensor_queue)
    main_logger.info("Anomaly and aggregator threads started")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((HOST, PORT))
        sock.listen()
        main_logger.info(f"Main server listening on {HOST}:{PORT}")

        while True:
            conn, addr = sock.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == '__main__':
    serve()
