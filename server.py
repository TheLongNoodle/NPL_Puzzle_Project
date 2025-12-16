import tkinter as tk
from tkinter import messagebox, scrolledtext
import socket
import threading
import json
import time
import logging
import sys

# --- CLIENT IMPORTS ---
try:
    from client_Human import SlidingPuzzle as HumanPuzzle
    from client_Computer import SlidingPuzzle as ComputerPuzzle
except ImportError as e:
    logging.critical(f"CRITICAL ERROR: Could not import client files. {e}")


    # Dummy classes to prevent immediate crash if files are missing
    class HumanPuzzle:
        def __init__(self, parent): logging.info("Human Client Missing")


    class ComputerPuzzle:
        def __init__(self, parent): logging.info("Computer Client Missing")

# Configuration
HOST = '127.0.0.1'
PORT = 8080
MAX_BYTES = 4096


# --- Logging Setup ---
class TkinterLogHandler(logging.Handler):
    """Routes Python log messages safely to the Tkinter GUI from various threads."""

    def __init__(self, view_instance):
        super().__init__()
        self.view = view_instance
        self.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))

    def emit(self, record):
        msg = self.format(record)
        # Using 'after' for safe, asynchronous GUI updates.
        self.view.log_gui(msg)


# Set up the basic logging configuration
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(threadName)s - %(levelname)s: %(message)s')


class ServerModel:
    """
    Model: Manages the data (statistics, client states).
    """

    def __init__(self):
        self.stats = {
            'human': {'games': 0, 'moves': [], 'time': []},
            'computer': {'games': 0, 'moves': [], 'time': []}
        }
        # Singleton flags to track active clients
        self.active_clients = {
            'human': False,
            'computer': False
        }
        self.lock = threading.Lock()

    def update_stats(self, client_type, moves, time_taken, solved):
        if not solved:
            return

        with self.lock:
            if client_type in self.stats:
                self.stats[client_type]['games'] += 1
                self.stats[client_type]['moves'].append(moves)
                self.stats[client_type]['time'].append(time_taken)

    def get_formatted_stats(self):
        with self.lock:
            report = ""
            for p_type, data in self.stats.items():
                count = data['games']
                if count > 0:
                    avg_moves = sum(data['moves']) / count
                    avg_time = sum(data['time']) / count
                else:
                    avg_moves = 0
                    avg_time = 0

                report += f"--- {p_type.upper()} PLAYER ---\n"
                report += f"Total Games Solved: {count}\n"
                report += f"Avg Moves: {avg_moves:.2f}\n"
                report += f"Avg Time: {avg_time:.2f}s\n\n"
            return report

    def set_client_active(self, client_type, status):
        with self.lock:
            self.active_clients[client_type] = status

    def is_client_active(self, client_type):
        with self.lock:
            return self.active_clients.get(client_type, False)


class ServerView:
    """
    View: The GUI of the Server.
    """

    def __init__(self, root, controller):
        self.controller = controller
        self.root = root
        self.root.title("N-Puzzle Server Hub")
        self.root.geometry("500x400")

        # --- Header ---
        lbl_title = tk.Label(root, text="N-Puzzle Game Server", font=("Arial", 16, "bold"))
        lbl_title.pack(pady=10)

        # --- Control Buttons ---
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)

        self.btn_human = tk.Button(btn_frame, text="New Human Player", width=20,
                                   command=lambda: controller.launch_client('human'))
        self.btn_human.pack(pady=5)

        self.btn_comp = tk.Button(btn_frame, text="New Computer Player", width=20,
                                  command=lambda: controller.launch_client('computer'))
        self.btn_comp.pack(pady=5)

        self.btn_stats = tk.Button(btn_frame, text="Show Statistics", width=20,
                                   command=controller.show_statistics)
        self.btn_stats.pack(pady=5)

        # --- Log Area ---
        tk.Label(root, text="Server Log:", anchor="w").pack(fill="x", padx=10)
        self.log_area = scrolledtext.ScrolledText(root, height=10, state='disabled')
        self.log_area.pack(padx=10, pady=5, fill="both", expand=True)

        # Add the custom handler to the root logger
        self.log_handler = TkinterLogHandler(self)
        logging.getLogger().addHandler(self.log_handler)

    def log_gui(self, message):
        """Thread-safe logging to the GUI."""
        self.root.after(0, self._update_log_area, message)

    def _update_log_area(self, message):
        """Internal function run by the main thread."""
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def show_alert(self, title, message):
        messagebox.showinfo(title, message)

    def show_error(self, title, message):
        messagebox.showerror(title, message)


class ServerController:
    """
    Controller: Handles logic, socket server, and thread management.
    """

    def __init__(self, root):
        self.model = ServerModel()
        self.view = ServerView(root, self)
        self.root = root
        self.running = True

        # Start Socket Server in a separate thread
        self.server_thread = threading.Thread(target=self.start_socket_server, daemon=True)
        self.server_thread.start()

    def start_socket_server(self):
        """Main loop to accept incoming client connections."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind((HOST, PORT))
            self.server_socket.listen(5)
            logging.info(f"Server listening on {HOST}:{PORT}")

            while self.running:
                try:
                    conn, addr = self.server_socket.accept()
                    client_handler = threading.Thread(target=self.handle_client_connection, args=(conn, addr))
                    client_handler.start()
                except OSError:
                    # Expected error when closing the socket server
                    break
        except Exception as e:
            logging.error(f"Socket Server failed: {e}")

    def handle_client_connection(self, conn, addr):
        """
        Communicates with a connected client using a newline-separated JSON stream.
        """
        client_type = None
        buffer = ""  # Buffer for accumulating incoming data stream.

        try:
            with conn:
                logging.info(f"Connection established with {addr}")

                while True:
                    data = conn.recv(MAX_BYTES)
                    if not data:
                        break

                    try:
                        buffer += data.decode('utf-8')
                    except UnicodeDecodeError:
                        logging.error(f"Failed to decode data from {addr}")
                        continue

                    # Processes buffer, splitting messages by newline.
                    while '\n' in buffer:
                        message_str, buffer = buffer.split('\n', 1)

                        if not message_str.strip():
                            continue

                        try:
                            msg = json.loads(message_str)

                            # Client log message
                            if 'level' in msg and 'message' in msg:
                                msg_level = msg.get('level', 'UNKNOWN').upper()
                                msg_source = msg.get('source', 'Client')
                                msg_message = msg.get('message', 'No message content.')

                                # Routes the log to the server's logging facility.
                                log_func = getattr(logging, msg_level.lower(), logging.info)

                                # Adds client type prefix if known.
                                prefix = f"[{client_type.upper()} LOG]" if client_type else f"[{msg_source}]"
                                log_func(f"{prefix} {msg_message}")

                                continue

                                # Original protocol messages (Connect, Stats, Disconnect)
                            msg_type = msg.get('type')

                            if msg_type == 'connect':
                                client_type = msg.get('client_type')
                                logging.info(f"{client_type.capitalize()} Client connected.")
                                self.model.set_client_active(client_type, True)

                            elif msg_type == 'stats':
                                # Ensure client_type is set before updating stats.
                                if not client_type:
                                    logging.warning("Stats received before client_type was set.")
                                    continue

                                self.model.update_stats(
                                    client_type,
                                    msg.get('moves'),
                                    msg.get('time'),
                                    msg.get('solved')
                                )
                                logging.info(f"Stats received from {client_type}")

                            elif msg_type == 'disconnect':
                                logging.info(f"{client_type.capitalize()} Client disconnected.")
                                if client_type:
                                    self.model.set_client_active(client_type, False)
                                break

                            else:
                                logging.warning(f"Unknown message type received: {msg_type} from {addr}")

                        except json.JSONDecodeError:
                            logging.warning(f"Invalid JSON received from {addr}: {message_str[:50]}...")

        except Exception as e:
            logging.error(f"Connection error with {addr}: {e}")
        finally:
            if client_type:
                self.model.set_client_active(client_type, False)
                logging.info(f"Connection closed with {client_type} at {addr}")
            else:
                logging.info(f"Connection closed with {addr}")

    def launch_client(self, client_type):
        """
        Launches the specific client code in a thread, enforcing Singleton pattern.
        """
        # 1. Singleton Check
        if self.model.is_client_active(client_type):
            self.view.show_error("Action Denied", f"A {client_type} game is already running!")
            return

        # 2. Set Active Flag
        self.model.set_client_active(client_type, True)
        logging.info(f"Starting {client_type} client...")

        # 3. Define wrapper to create a new Root for the thread
        def run_client_wrapper(c_type):
            try:
                # Create a NEW tkinter root for this specific client thread
                client_root = tk.Tk()
                client_root.title(f"{c_type.capitalize()} Game Client")

                # Instantiate the client class
                if c_type == 'human':
                    app = HumanPuzzle(client_root)
                elif c_type == 'computer':
                    app = ComputerPuzzle(client_root)

                client_root.mainloop()

            except Exception as e:
                logging.error(f"Failed to launch {c_type}: {e}")
            finally:
                # Ensure flag is reset if it crashes or closes unexpectedly
                self.model.set_client_active(c_type, False)
                logging.info(f"{c_type.capitalize()} client process terminated.")

        # 4. Start the Thread
        t = threading.Thread(target=run_client_wrapper, args=(client_type,), daemon=True)
        t.start()

    def show_statistics(self):
        stats_text = self.model.get_formatted_stats()
        self.view.show_alert("Game Statistics", stats_text)

    def on_close(self):
        logging.info("Shutting down server.")
        self.running = False
        try:
            # To unblock server_socket.accept().
            self.server_socket.close()
        except:
            pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ServerController(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()