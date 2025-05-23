import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import threading
import time
import json
from collections import defaultdict, deque
from datetime import datetime
from comm.central_client import send_to_central
from comm.battery_manager import (
    update_time_drain,
    drain_on_read,
    drain_on_send,
    get_level,
    check_return_to_base,
    should_enqueue
)
from logger import setup_logger

WINDOW = 2.0
BATCH_INTERVAL = 2.0

buffers = defaultdict(lambda: deque())
summary_buffers = defaultdict(list)
drone_loggers = {}
anomaly_logger = setup_logger('anomalies', 'logs/anomalies.log')

def get_drone_logger(drone_id):
    if not drone_id.startswith("drone"):
        print("⚠️ Invalid drone_id:", drone_id)

    if drone_id not in drone_loggers:
        print("🔍 Creating logger for:", drone_id)
        drone_loggers[drone_id] = setup_logger(drone_id, f'logs/drones/{drone_id}.log')
    return drone_loggers[drone_id]

def parse_timestamp(ts_str):
    try:
        return datetime.fromisoformat(ts_str.replace('Z', '+00:00')).timestamp()
    except Exception:
        return time.time()

def detect_threshold_anomalies(r):
    anomalies = []

    t = r.get('temperature')
    if t is not None and (t < -10 or t > 60):
        anomalies.append({'type': 'temperature', 'value': t})

    p = r.get('pressure')
    if p is not None and (p < 300 or p > 1100):
        anomalies.append({'type': 'pressure', 'value': p})

    alt = r.get('altitude')
    if alt is not None and (alt < 0 or alt > 500):
        anomalies.append({'type': 'altitude', 'value': alt})

    motors = r.get('motor_energies')
    if motors:
        for idx, m in enumerate(motors):
            if m < 0 or m > 100:
                anomalies.append({'type': f'motor_{idx}', 'value': m})

    return anomalies

def detect_discrepancy_anomalies(drone_id, ts):
    buf = buffers[drone_id]
    while buf and buf[0][0] < ts - WINDOW:
        buf.popleft()

    anomalies = []
    if len(buf) >= 4:
        temps = [r['temperature'] for _, r in buf if 'temperature' in r]
        alts  = [r['altitude']    for _, r in buf if 'altitude'    in r]
        if temps and (max(temps) - min(temps) > 5):
            anomalies.append({'type': 'temperature_discrepancy', 'range': max(temps) - min(temps)})
        if alts and (max(alts) - min(alts) > 1):
            anomalies.append({'type': 'altitude_discrepancy', 'range': max(alts) - min(alts)})
    return anomalies

def handle_reading(r: dict):
    ts = parse_timestamp(r.get('timestamp', ''))
    sensor_id = r.get('sensor_id', '')
    drone_id = r.get('drone_id') or '_'.join(sensor_id.split('_')[:2])

    print("🔍 LOGGING FOR DRONE ID:", drone_id)
    logger = get_drone_logger(drone_id)

    update_time_drain(drone_id, ts)

    if not should_enqueue(drone_id):
        logger.warning(f"Battery critical ({get_level(drone_id):.1f}%), dropping reading")
        return

    level_after_read = drain_on_read(drone_id)
    if level_after_read < 10:
        r['motor_energies'] = [0] * len(r.get('motor_energies', []))

    buffers[drone_id].append((ts, r))
    summary_buffers[drone_id].append(r)

    threshold_anoms = detect_threshold_anomalies(r)
    discrepancy_anoms = detect_discrepancy_anomalies(drone_id, ts)
    all_anoms = threshold_anoms + discrepancy_anoms

    if all_anoms:
        logger.warning(f"Anomalies detected: {json.dumps(all_anoms)}")
        anomaly_logger.warning(f"{sensor_id} @ {r['timestamp']} → {json.dumps(all_anoms)}")
    else:
        logger.info(f"Reading accepted from {sensor_id} at {r.get('timestamp')}")

def start_aggregator():
    def agg_loop():
        while True:
            time.sleep(BATCH_INTERVAL)
            now = time.time()
            for drone_id, readings in list(summary_buffers.items()):
                logger = get_drone_logger(drone_id)

                if not readings:
                    continue

                avg_temperature = sum(r['temperature'] for r in readings) / len(readings)
                avg_pressure    = sum(r['pressure']    for r in readings) / len(readings)
                avg_altitude    = sum(r['altitude']    for r in readings) / len(readings)
                avg_motors      = [
                    sum(r['motor_energies'][i] for r in readings) / len(readings)
                    for i in range(len(readings[0]['motor_energies']))
                ]

                return_evt, lvl = check_return_to_base(drone_id)
                if return_evt:
                    logger.warning(f"Return-to-base triggered at {lvl:.1f}%")

                if lvl < 20:
                    logger.warning(f"Battery low ({lvl:.1f}%), skipping summary")
                else:
                    new_lvl = drain_on_send(drone_id, sum(avg_motors) / len(avg_motors))
                    payload = {
                        "drone_id": drone_id,
                        "avg_temperature": avg_temperature,
                        "avg_pressure": avg_pressure,
                        "avg_altitude": avg_altitude,
                        "avg_motor_energies": avg_motors,
                        "timestamp": datetime.utcfromtimestamp(now).strftime('%Y-%m-%dT%H:%M:%SZ')
                    }
                    try:
                        send_to_central(payload)
                        logger.info(f"Summary sent to central: {json.dumps(payload)}; battery: {new_lvl:.1f}%")
                    except Exception as e:
                        logger.error(f"Error sending to central: {e}")

                summary_buffers[drone_id].clear()

    t = threading.Thread(target=agg_loop, daemon=True)
    t.start()

def start_consumer(queue):
    start_aggregator()
    print("Aggregator thread started")

    def worker():
        while True:
            reading = queue.get()
            handle_reading(reading)
            queue.task_done()

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    print("Consumer thread started")
