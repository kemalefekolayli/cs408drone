import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import subprocess
import os
import uuid

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
ANOMALY_LOG = os.path.join(LOG_DIR, 'anomalies.log')

running_sensors = {}
running_drones = {}


def launch_server():
    try:
        subprocess.Popen(['python', 'central_server.py'])
        messagebox.showinfo("Server", "Central Server started.")
    except Exception as e:
        messagebox.showerror("Error", str(e))


def launch_drone_server():
    try:
        subprocess.Popen(['python', '-m', 'comm.server'])
        messagebox.showinfo("Drone Server", "Drone Server started.")
    except Exception as e:
        messagebox.showerror("Error", str(e))


def launch_sensor(drone_id, sensor_frame):
    sensor_id = f"{drone_id}_s{uuid.uuid4().hex[:4]}"
    port = 5000
    host = "127.0.0.1"
    cmd = ['python', '-m', 'comm.sensor', '--host', host, '--port', str(port), '--sensor-id', sensor_id]
    proc = subprocess.Popen(cmd)
    running_sensors[sensor_id] = proc

    row = tk.Frame(sensor_frame)
    row.pack(fill='x', pady=1)
    tk.Label(row, text=sensor_id, width=25, anchor='w').pack(side='left')
    tk.Button(row, text="View Log", command=lambda sid=sensor_id: view_log(f'sensors/{sid}.log'), width=10).pack(side='right')


def view_log(log_relative_path):
    full_path = os.path.join(LOG_DIR, log_relative_path)
    if not os.path.exists(full_path):
        messagebox.showinfo("Log", f"Log file not found: {log_relative_path}")
        return

    log_window = tk.Toplevel()
    log_window.title(f"Log - {log_relative_path}")
    text_area = scrolledtext.ScrolledText(log_window, wrap=tk.WORD, width=100, height=30)
    text_area.pack(expand=True, fill='both')
    with open(full_path, 'r') as f:
        text_area.insert(tk.END, f.read())
    text_area.config(state='disabled')


def create_drone_tab(notebook):
    drone_id = f"drone_{uuid.uuid4().hex[:4]}"
    drone_frame = tk.Frame(notebook)
    notebook.add(drone_frame, text=drone_id)

    top_bar = tk.Frame(drone_frame)
    top_bar.pack(fill='x')
    tk.Label(top_bar, text=f"Drone ID: {drone_id}", font=("Arial", 10, "bold")).pack(side='left', padx=10)
    tk.Button(top_bar, text="Add Sensor", command=lambda: launch_sensor(drone_id, sensor_list)).pack(side='right', padx=10)
    tk.Button(top_bar, text="View Drone Log", command=lambda: view_log(f'/drones/{drone_id}.log')).pack(side='right', padx=10)

    sensor_list = tk.LabelFrame(drone_frame, text="Sensors")
    sensor_list.pack(fill='both', expand=True, padx=10, pady=10)
    running_drones[drone_id] = sensor_list


def view_server_logs():
    files = ["main.log", "central_server.log", "test_client.log"]
    for fname in files:
        full_path = os.path.join(LOG_DIR, "server", fname)
        if os.path.exists(full_path):
            view_log(f"server/{fname}")


def view_anomaly_log():
    if os.path.exists(ANOMALY_LOG):
        view_log("anomalies.log")
    else:
        messagebox.showinfo("Log", "Anomaly log file not found.")


def main():
    root = tk.Tk()
    root.title("CS408 Drone System GUI")
    root.geometry("1000x700")

    control_frame = tk.Frame(root)
    control_frame.pack(fill='x', pady=10, padx=10)

    tk.Button(control_frame, text="Start Central Server", command=launch_server, width=20).pack(side='left', padx=5)
    tk.Button(control_frame, text="Start Drone Server", command=launch_drone_server, width=20).pack(side='left', padx=5)
    tk.Button(control_frame, text="Add Drone", command=lambda: create_drone_tab(drone_tabs), width=20).pack(side='left', padx=5)
    tk.Button(control_frame, text="View Server Logs", command=view_server_logs, width=20).pack(side='left', padx=5)
    tk.Button(control_frame, text="View Anomaly Log", command=view_anomaly_log, width=20).pack(side='left', padx=5)

    drone_tabs = ttk.Notebook(root)
    drone_tabs.pack(fill='both', expand=True, padx=10, pady=10)

    root.mainloop()


if __name__ == '__main__':
    main()