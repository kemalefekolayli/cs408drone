import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import subprocess
import os
import uuid
import time
import json
from datetime import datetime
from collections import deque

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
ANOMALY_LOG = os.path.join(LOG_DIR, 'anomalies.log')

running_sensors = {}
running_drones = {}
running_processes = {}
log_windows = {}


class DroneStatus:
    def __init__(self, drone_id):
        self.drone_id = drone_id
        self.battery_level = 100.0
        self.last_update = None
        self.is_returning = False
        self.anomaly_count = 0
        self.sensor_count = 0
        self.status = "Active"


def launch_server():
    try:
        if 'central_server' not in running_processes:
            proc = subprocess.Popen(['python', 'central_server.py'])
            running_processes['central_server'] = proc
            update_status_bar("Central Server started.")
        else:
            messagebox.showinfo("Server", "Central Server is already running.")
    except Exception as e:
        messagebox.showerror("Error", str(e))


def launch_drone_server():
    try:
        if 'drone_server' not in running_processes:
            proc = subprocess.Popen(['python', '-m', 'comm.server'])
            running_processes['drone_server'] = proc
            update_status_bar("Drone Server started.")
        else:
            messagebox.showinfo("Drone Server", "Drone Server is already running.")
    except Exception as e:
        messagebox.showerror("Error", str(e))


def stop_all_processes():
    for name, proc in running_processes.items():
        try:
            proc.terminate()
        except:
            pass
    for sensor_id, proc in running_sensors.items():
        try:
            proc.terminate()
        except:
            pass
    update_status_bar("All processes stopped.")


def launch_sensor(drone_id, sensor_frame):
    sensor_id = f"{drone_id}_s{uuid.uuid4().hex[:4]}"
    port = 5000
    host = "127.0.0.1"
    cmd = ['python', '-m', 'comm.sensor', '--host', host, '--port', str(port), '--sensor-id', sensor_id]
    proc = subprocess.Popen(cmd)
    running_sensors[sensor_id] = proc

    row = tk.Frame(sensor_frame)
    row.pack(fill='x', pady=2)
    
    # Sensor info with status indicator
    info_frame = tk.Frame(row)
    info_frame.pack(side='left', fill='x', expand=True)
    
    status_indicator = tk.Label(info_frame, text="●", fg="green", font=("Arial", 10))
    status_indicator.pack(side='left', padx=5)
    
    tk.Label(info_frame, text=sensor_id, width=25, anchor='w').pack(side='left')
    
    # Buttons
    button_frame = tk.Frame(row)
    button_frame.pack(side='right')
    
    tk.Button(button_frame, text="View Log", 
              command=lambda sid=sensor_id: view_log(f'sensors/{sid}.log', auto_refresh=True), 
              width=10).pack(side='left', padx=2)
    
    tk.Button(button_frame, text="Stop", 
              command=lambda sid=sensor_id, r=row: stop_sensor(sid, r), 
              width=8, fg="red").pack(side='left', padx=2)
    
    # Update drone status
    if drone_id in running_drones:
        status = running_drones[drone_id]['status']
        status.sensor_count += 1
        update_drone_display(drone_id)


def stop_sensor(sensor_id, row_widget):
    if sensor_id in running_sensors:
        try:
            running_sensors[sensor_id].terminate()
            del running_sensors[sensor_id]
            row_widget.destroy()
            
            # Update drone sensor count
            drone_id = '_'.join(sensor_id.split('_')[:2])
            if drone_id in running_drones:
                status = running_drones[drone_id]['status']
                status.sensor_count -= 1
                update_drone_display(drone_id)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to stop sensor: {e}")


def view_log(log_relative_path, auto_refresh=False):
    full_path = os.path.join(LOG_DIR, log_relative_path)
    if not os.path.exists(full_path):
        messagebox.showinfo("Log", f"Log file not found: {log_relative_path}")
        return

    log_window = tk.Toplevel()
    log_window.title(f"Log - {log_relative_path}")
    log_window.geometry("1000x600")
    
    # Control frame
    control_frame = tk.Frame(log_window)
    control_frame.pack(fill='x', padx=5, pady=5)
    
    auto_scroll_var = tk.BooleanVar(value=True)
    tk.Checkbutton(control_frame, text="Auto-scroll", variable=auto_scroll_var).pack(side='left')
    
    if auto_refresh:
        refresh_var = tk.BooleanVar(value=True)
        tk.Checkbutton(control_frame, text="Auto-refresh", variable=refresh_var).pack(side='left', padx=10)
    
    # Search frame
    search_frame = tk.Frame(log_window)
    search_frame.pack(fill='x', padx=5)
    tk.Label(search_frame, text="Search:").pack(side='left')
    search_entry = tk.Entry(search_frame, width=30)
    search_entry.pack(side='left', padx=5)
    
    # Text area with scrollbar
    text_frame = tk.Frame(log_window)
    text_frame.pack(expand=True, fill='both', padx=5, pady=5)
    
    text_area = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, width=120, height=35)
    text_area.pack(expand=True, fill='both')
    
    # Syntax highlighting tags
    text_area.tag_config("INFO", foreground="black")
    text_area.tag_config("WARNING", foreground="orange", font=("Courier", 10, "bold"))
    text_area.tag_config("ERROR", foreground="red", font=("Courier", 10, "bold"))
    text_area.tag_config("timestamp", foreground="blue")
    text_area.tag_config("highlight", background="yellow")
    
    def load_and_highlight():
        try:
            with open(full_path, 'r') as f:
                content = f.read()
            
            text_area.config(state='normal')
            text_area.delete(1.0, tk.END)
            
            # Process line by line for syntax highlighting
            for line in content.split('\n'):
                if 'ERROR' in line:
                    text_area.insert(tk.END, line + '\n', "ERROR")
                elif 'WARNING' in line:
                    text_area.insert(tk.END, line + '\n', "WARNING")
                elif 'INFO' in line:
                    text_area.insert(tk.END, line + '\n', "INFO")
                else:
                    text_area.insert(tk.END, line + '\n')
            
            if auto_scroll_var.get():
                text_area.see(tk.END)
            
            text_area.config(state='disabled')
        except Exception as e:
            text_area.config(state='normal')
            text_area.insert(tk.END, f"Error reading log: {e}")
            text_area.config(state='disabled')
    
    def search_log(*args):
        search_term = search_entry.get()
        if not search_term:
            return
        
        text_area.tag_remove("highlight", "1.0", tk.END)
        
        start_pos = "1.0"
        while True:
            pos = text_area.search(search_term, start_pos, stopindex=tk.END, nocase=True)
            if not pos:
                break
            end_pos = f"{pos}+{len(search_term)}c"
            text_area.tag_add("highlight", pos, end_pos)
            start_pos = end_pos
    
    search_entry.bind('<KeyRelease>', search_log)
    
    # Initial load
    load_and_highlight()
    
    # Auto-refresh logic
    if auto_refresh:
        def refresh_loop():
            if log_window.winfo_exists() and refresh_var.get():
                load_and_highlight()
                log_window.after(1000, refresh_loop)
        
        log_window.after(1000, refresh_loop)
    
    # Store reference to prevent garbage collection
    log_windows[log_relative_path] = log_window


def create_drone_tab(notebook):
    drone_id = f"drone_{uuid.uuid4().hex[:4]}"
    drone_frame = tk.Frame(notebook)
    notebook.add(drone_frame, text=drone_id)
    
    # Create status object
    status = DroneStatus(drone_id)
    
    # Status panel
    status_panel = tk.LabelFrame(drone_frame, text="Drone Status", font=("Arial", 10, "bold"))
    status_panel.pack(fill='x', padx=10, pady=5)
    
    status_grid = tk.Frame(status_panel)
    status_grid.pack(padx=10, pady=10)
    
    # Status displays
    tk.Label(status_grid, text="Drone ID:").grid(row=0, column=0, sticky='w', padx=5)
    id_label = tk.Label(status_grid, text=drone_id, font=("Arial", 10, "bold"))
    id_label.grid(row=0, column=1, sticky='w', padx=5)
    
    tk.Label(status_grid, text="Battery:").grid(row=0, column=2, sticky='w', padx=5)
    battery_label = tk.Label(status_grid, text="100.0%", fg="green", font=("Arial", 10, "bold"))
    battery_label.grid(row=0, column=3, sticky='w', padx=5)
    
    tk.Label(status_grid, text="Status:").grid(row=1, column=0, sticky='w', padx=5)
    status_label = tk.Label(status_grid, text="Active", fg="green", font=("Arial", 10, "bold"))
    status_label.grid(row=1, column=1, sticky='w', padx=5)
    
    tk.Label(status_grid, text="Sensors:").grid(row=1, column=2, sticky='w', padx=5)
    sensor_count_label = tk.Label(status_grid, text="0", font=("Arial", 10, "bold"))
    sensor_count_label.grid(row=1, column=3, sticky='w', padx=5)
    
    tk.Label(status_grid, text="Anomalies:").grid(row=2, column=0, sticky='w', padx=5)
    anomaly_label = tk.Label(status_grid, text="0", font=("Arial", 10, "bold"))
    anomaly_label.grid(row=2, column=1, sticky='w', padx=5)
    
    tk.Label(status_grid, text="Last Update:").grid(row=2, column=2, sticky='w', padx=5)
    update_label = tk.Label(status_grid, text="Never", font=("Arial", 10))
    update_label.grid(row=2, column=3, sticky='w', padx=5)
    
    # Control buttons
    control_bar = tk.Frame(drone_frame)
    control_bar.pack(fill='x', padx=10, pady=5)
    
    tk.Button(control_bar, text="Add Sensor", 
              command=lambda: launch_sensor(drone_id, sensor_list), 
              bg="green", fg="white").pack(side='left', padx=5)
    
    tk.Button(control_bar, text="View Drone Log", 
              command=lambda: view_log(f'drones/{drone_id}.log', auto_refresh=True)).pack(side='left', padx=5)
    
    tk.Button(control_bar, text="Simulate Low Battery", 
              command=lambda: simulate_low_battery(drone_id), 
              bg="orange").pack(side='left', padx=5)
    
    # Sensor list
    sensor_list = tk.LabelFrame(drone_frame, text="Active Sensors")
    sensor_list.pack(fill='both', expand=True, padx=10, pady=10)
    
    # Store references
    running_drones[drone_id] = {
        'frame': drone_frame,
        'sensor_list': sensor_list,
        'status': status,
        'labels': {
            'battery': battery_label,
            'status': status_label,
            'sensor_count': sensor_count_label,
            'anomaly': anomaly_label,
            'update': update_label
        }
    }


def update_drone_display(drone_id):
    if drone_id not in running_drones:
        return
    
    drone_info = running_drones[drone_id]
    status = drone_info['status']
    labels = drone_info['labels']
    
    # Update battery color
    battery_color = "green" if status.battery_level > 50 else "orange" if status.battery_level > 20 else "red"
    labels['battery'].config(text=f"{status.battery_level:.1f}%", fg=battery_color)
    
    # Update status
    status_text = "Returning to Base" if status.is_returning else status.status
    status_color = "red" if status.is_returning else "green"
    labels['status'].config(text=status_text, fg=status_color)
    
    # Update counts
    labels['sensor_count'].config(text=str(status.sensor_count))
    labels['anomaly'].config(text=str(status.anomaly_count))
    
    # Update timestamp
    if status.last_update:
        labels['update'].config(text=status.last_update.strftime("%H:%M:%S"))


def simulate_low_battery(drone_id):
    if drone_id in running_drones:
        status = running_drones[drone_id]['status']
        status.battery_level = 15.0
        status.is_returning = True
        status.last_update = datetime.now()
        update_drone_display(drone_id)
        update_status_bar(f"Simulated low battery for {drone_id}")


def view_server_logs():
    log_window = tk.Toplevel()
    log_window.title("Server Logs")
    log_window.geometry("400x300")
    
    files = ["server/main.log", "server/central_server.log", "server/test_client.log"]
    
    for fname in files:
        full_path = os.path.join(LOG_DIR, fname)
        frame = tk.Frame(log_window)
        frame.pack(fill='x', padx=10, pady=5)
        
        exists = os.path.exists(full_path)
        color = "green" if exists else "red"
        status = "Found" if exists else "Not Found"
        
        tk.Label(frame, text=fname, width=30, anchor='w').pack(side='left')
        tk.Label(frame, text=status, fg=color, width=10).pack(side='left')
        
        if exists:
            tk.Button(frame, text="View", 
                     command=lambda f=fname: view_log(f, auto_refresh=True), 
                     width=10).pack(side='right')


def view_anomaly_log():
    if os.path.exists(ANOMALY_LOG):
        view_log("anomalies.log", auto_refresh=True)
    else:
        messagebox.showinfo("Log", "Anomaly log file not found.")


def update_status_bar(message):
    status_label.config(text=f"[{datetime.now().strftime('%H:%M:%S')}] {message}")


def main():
    global status_label
    
    root = tk.Tk()
    root.title("CS408 Drone System Control Center")
    root.geometry("1200x800")
    
    # Menu bar
    menubar = tk.Menu(root)
    root.config(menu=menubar)
    
    file_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="File", menu=file_menu)
    file_menu.add_command(label="Exit", command=lambda: [stop_all_processes(), root.quit()])
    
    view_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="View", menu=view_menu)
    view_menu.add_command(label="Server Logs", command=view_server_logs)
    view_menu.add_command(label="Anomaly Log", command=view_anomaly_log)
    
    # Main control panel
    control_frame = tk.LabelFrame(root, text="System Control", font=("Arial", 12, "bold"))
    control_frame.pack(fill='x', pady=10, padx=10)
    
    control_grid = tk.Frame(control_frame)
    control_grid.pack(pady=10)
    
    tk.Button(control_grid, text="Start Central Server", command=launch_server, 
              width=20, height=2, bg="blue", fg="white").grid(row=0, column=0, padx=5, pady=5)
    tk.Button(control_grid, text="Start Drone Server", command=launch_drone_server, 
              width=20, height=2, bg="blue", fg="white").grid(row=0, column=1, padx=5, pady=5)
    tk.Button(control_grid, text="Add Drone", command=lambda: create_drone_tab(drone_tabs), 
              width=20, height=2, bg="green", fg="white").grid(row=0, column=2, padx=5, pady=5)
    tk.Button(control_grid, text="Stop All", command=stop_all_processes, 
              width=20, height=2, bg="red", fg="white").grid(row=0, column=3, padx=5, pady=5)
    
    # Quick access buttons
    quick_frame = tk.Frame(control_frame)
    quick_frame.pack(fill='x', padx=10, pady=5)
    
    tk.Label(quick_frame, text="Quick Access:", font=("Arial", 10, "bold")).pack(side='left', padx=5)
    tk.Button(quick_frame, text="Server Logs", command=view_server_logs, width=12).pack(side='left', padx=2)
    tk.Button(quick_frame, text="Anomaly Log", command=view_anomaly_log, width=12).pack(side='left', padx=2)
    
    # Drone tabs
    drone_tabs = ttk.Notebook(root)
    drone_tabs.pack(fill='both', expand=True, padx=10, pady=10)
    
    # Status bar
    status_frame = tk.Frame(root, bd=1, relief=tk.SUNKEN)
    status_frame.pack(fill='x', side='bottom')
    status_label = tk.Label(status_frame, text="Ready", anchor='w')
    status_label.pack(fill='x', padx=5)
    
    # Handle window close
    root.protocol("WM_DELETE_WINDOW", lambda: [stop_all_processes(), root.destroy()])
    
    update_status_bar("System initialized. Start servers to begin operation.")
    
    root.mainloop()


if __name__ == '__main__':
    main()