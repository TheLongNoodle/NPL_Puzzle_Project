import tkinter as tk
from tkinter import ttk
import random
import socket
import json
from datetime import datetime
from copy import deepcopy
import threading
import heapq
from collections import deque
import sys


# --- Socket Logger Class ---
class SocketLogger:
    """The class handling connection and sending log messages to the server."""

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = None
        self.is_connected = False
        self.connect_to_server()

    def connect_to_server(self):
        """Attempts to establish connection with the log server."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(2)
            self.socket.connect((self.host, self.port))
            self.socket.settimeout(None)
            self.is_connected = True
            self._log_local("INFO", f"SocketLogger connected to {self.host}:{self.port}")
        except socket.error as e:
            self.is_connected = False
            self.socket = None
            self._log_local("ERROR", f"Failed to connect to log server {self.host}:{self.port}: {e}")

    def send_protocol_message(self, msg_type, **kwargs):
        """Sends structured protocol messages like 'connect' or 'stats'."""
        if not self.is_connected or not self.socket:
            return

        payload = {"type": msg_type}
        payload.update(kwargs)

        try:
            message = json.dumps(payload) + '\n'
            self.socket.sendall(message.encode('utf-8'))
        except socket.error as e:
            self.is_connected = False
            self._log_local("ERROR", f"Protocol send failed: {e}")

    def _log_local(self, level, message):
        """Local log function for internal use (on connection failure)."""
        print(f"[{level}] {message}", file=sys.stderr if level == "ERROR" else sys.stdout)

    def send_log(self, level, message):
        """Sends a log message to the server in JSON format."""
        if not self.is_connected or not self.socket:
            self._log_local(level, message)
            return

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "source": "HumanPuzzleClient"
        }

        try:
            log_message = json.dumps(log_entry).encode('utf-8') + b'\n'
            self.socket.sendall(log_message)
        except socket.error as e:
            self.is_connected = False
            self.socket.close()
            self.socket = None
            self._log_local("ERROR", f"Socket error while sending log: {e}. Connection lost.")


GLOBAL_LOGGER = None


def custom_log(level, message, *args):
    if GLOBAL_LOGGER:
        formatted_message = message % args if args else message
        GLOBAL_LOGGER.send_log(level, formatted_message)


def info(message, *args): custom_log("INFO", message, *args)


def debug(message, *args): custom_log("DEBUG", message, *args)


def error(message, *args): custom_log("ERROR", message, *args)


class SlidingPuzzle:

    # ==================== init (VIEW) ==================== #
    def __init__(self, parent):
        SERVER_HOST = '127.0.0.1'
        SERVER_PORT = 8080

        global GLOBAL_LOGGER
        GLOBAL_LOGGER = SocketLogger(SERVER_HOST, SERVER_PORT)
        GLOBAL_LOGGER.send_protocol_message("connect", client_type="human")

        self.move_count = 0
        self.parent = parent
        self.frame = tk.Frame(parent)
        self.frame.pack()

        self.memento_stack = []
        self.redo_stack = []

        self.width = 3
        self.height = 3
        self.board = []
        self.buttons = []

        self.solver_thread = None
        self.abort_solver = False

        # --- NEW VARIABLES INITIALIZED HERE ---
        self.is_locked = False
        self.start_time = datetime.now()

        # --- Controls ---
        control_frame = tk.Frame(self.frame)
        control_frame.pack()

        tk.Label(control_frame, text="Cols").grid(row=0, column=0)
        self.width_slider = tk.Scale(control_frame, from_=3, to=9, orient=tk.HORIZONTAL, length=300)
        self.width_slider.set(self.width)
        self.width_slider.grid(row=0, column=1)

        tk.Label(control_frame, text="Rows").grid(row=1, column=0)
        self.height_slider = tk.Scale(control_frame, from_=3, to=9, orient=tk.HORIZONTAL, length=300)
        self.height_slider.set(self.height)
        self.height_slider.grid(row=1, column=1)

        tk.Button(control_frame, text="Generate", command=self.generate_random).grid(row=2, column=0, columnspan=2,
                                                                                     sticky="ew", padx=5)
        ttk.Separator(control_frame, orient=tk.HORIZONTAL).grid(row=3, column=0, columnspan=2, sticky="ew", pady=5)

        bottom_frame = tk.Frame(self.frame)
        bottom_frame.pack(pady=10)

        self.moves_label = tk.Label(bottom_frame, text="Moves: 0", font=("Arial", 11))
        self.moves_label.pack(side=tk.LEFT, padx=15)

        self.solvable_label = tk.Label(bottom_frame, text="", font=("Arial", 12, "bold"))
        self.solvable_label.pack(side=tk.LEFT, padx=20)

        self.timer_label = tk.Label(bottom_frame, text="Time: 0.0s", font=("Arial", 11))
        self.timer_label.pack(side=tk.LEFT, padx=15)


        self.board_frame = tk.Frame(self.frame)
        self.board_frame.pack()


        undo_frame = tk.Frame(self.frame)
        undo_frame.pack(pady=10)

        self.undo_button = tk.Button(undo_frame, text="Undo", command=self.undo)
        self.undo_button.pack(side=tk.LEFT, padx=10)

        self.redo_button = tk.Button(undo_frame, text="Redo", command=self.redo)
        self.redo_button.pack(side=tk.LEFT, padx=10)

        self.update_timer()

        self.generate_solvable()

    # ==================== Undo/Redo logic (CONTROLLER) ==================== #
    def save_state(self):
        self.memento_stack.append(deepcopy(self.board))
        self.redo_stack.clear()

    def undo(self):
        if self.memento_stack:
            self.redo_stack.append(deepcopy(self.board))
            self.board = self.memento_stack.pop()
            if(self.move_count != 0):
                self.move_count -= 1
            self.moves_label.config(text=f"Moves: {self.move_count}")
            self.draw_board()

    def redo(self):
        if self.redo_stack:
            self.memento_stack.append(deepcopy(self.board))
            self.board = self.redo_stack.pop()
            self.move_count += 1
            self.moves_label.config(text=f"Moves: {self.move_count}")
            self.draw_board()

    # ==================== Puzzle Generation (CONTROLLER) ==================== #
    def generate_random(self):
        self.width = self.width_slider.get()
        self.height = self.height_slider.get()
        nums = list(range(1, self.width * self.height)) + [0]
        random.shuffle(nums)

        self.memento_stack.clear()
        self.redo_stack.clear()
        self.buttons.clear()
        self.undo_button.config(state=tk.NORMAL)
        self.redo_button.config(state=tk.NORMAL)

        # RESET FLAGS AND TIMER
        self.is_locked = False
        self.start_time = datetime.now()

        self.board = [nums[i * self.width:(i + 1) * self.width] for i in range(self.height)]
        self.save_state()
        self.draw_board()
        self.move_count = 0
        self.moves_label.config(text="Moves: 0")
        self.timer_label.config(text="Time: 0.0s")
        info("Puzzle generated (width=%d, height=%d)", self.width, self.height)

    def generate_solvable(self):
        self.width = self.width_slider.get()
        self.height = self.height_slider.get()
        nums = list(range(1, self.width * self.height)) + [0]

        while True:
            random.shuffle(nums)
            if self.is_solvable(nums):
                break

        self.memento_stack.clear()
        self.redo_stack.clear()
        self.buttons.clear()
        self.undo_button.config(state=tk.NORMAL)
        self.redo_button.config(state=tk.NORMAL)

        # RESET FLAGS AND TIMER
        self.is_locked = False
        self.start_time = datetime.now()

        self.board = [nums[i * self.width:(i + 1) * self.width] for i in range(self.height)]
        self.save_state()
        self.draw_board()
        self.move_count = 0
        self.moves_label.config(text="Moves: 0")
        self.timer_label.config(text="Time: 0.0s")
        info("Puzzle generated (width=%d, height=%d)", self.width, self.height)

    def is_solvable(self, nums):
        inv = 0
        nums_no_zero = [x for x in nums if x != 0]
        for i in range(len(nums_no_zero)):
            for j in range(i + 1, len(nums_no_zero)):
                if nums_no_zero[i] > nums_no_zero[j]:
                    inv += 1
        if self.width % 2 == 1:
            return inv % 2 == 0
        empty_row_from_bottom = (self.height - (nums.index(0) // self.width))
        if self.width % 2 == 0:
            return (empty_row_from_bottom % 2 == 0) != (inv % 2 == 0)
        return True

    # ==================== Moves (CONTROLLER) ==================== #
    def move(self, r, c):
        # Do not allow moves if board is locked
        if self.is_locked:
            return

        for i in range(self.height):
            for j in range(self.width):
                if self.board[i][j] == 0:
                    er, ec = i, j
        if abs(er - r) + abs(ec - c) == 1:
            self.save_state()
            self.board[er][ec], self.board[r][c] = self.board[r][c], self.board[er][ec]
            self.move_count += 1
            self.moves_label.config(text=f"Moves: {self.move_count}")
            self.update_two_buttons(er, ec, r, c)
            if self.is_solved_board(board=self.board):
                info("Puzzle solved in %d moves", self.move_count)
                self.draw_board()
                self.lock_board()

    def traversal(self, width, height):
        matrix = [[r * width + c + 1 for c in range(width)] for r in range(height)]
        result = []
        top, left = 0, 0
        bottom, right = height - 1, width - 1
        while (bottom - top) != (right - left):
            if (bottom - top) > (right - left):
                for c in range(left, right + 1): result.append((matrix[top][c], True))
                top += 1
            else:
                for r in range(top, bottom + 1): result.append((matrix[r][left], False))
                left += 1
        while top <= bottom and left <= right:
            for c in range(left, right + 1): result.append((matrix[top][c], True))
            top += 1
            for r in range(top, bottom + 1): result.append((matrix[r][left], False))
            left += 1
            if top <= bottom:
                for c in range(left, right + 1): result.append((matrix[top][c], True))
                top += 1
            if left <= right:
                for r in range(top, bottom + 1): result.append((matrix[r][left], False))
                left += 1
        return result

    # ==================== Drawing (VIEW) ==================== #
    def update_timer(self):
        if not self.is_locked:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            self.timer_label.config(text=f"Time: {elapsed:.1f}s")
        self.parent.after(100, self.update_timer)
    
    def draw_board(self):
        max_button_width = max(3, 30 // self.width)
        max_button_height = max(2, 20 // self.height)
        button_width = min(max_button_width, 8)
        button_height = min(max_button_height, 4)
        font_size = max(8, 14 - (self.width + self.height - 8) // 2)

        import colorsys
        traversal_order = self.traversal(self.width, self.height)
        val_to_pos = {val: i for i, (val, _) in enumerate(traversal_order)}
        max_pos = len(traversal_order) - 1

        def get_tile_color(val):
            if val == 0: return "#FFFFFF"
            t = val_to_pos[val] / max_pos if max_pos > 0 else 0
            h = 0.0 + 0.75 * t
            r, g, b = colorsys.hsv_to_rgb(h, 0.4, 0.95)
            return f'#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}'

        if not self.buttons or len(self.buttons) != self.height or len(self.buttons[0]) != self.width:
            for w in self.board_frame.winfo_children(): w.destroy()
            self.buttons.clear()
            for r in range(self.height):
                row_buttons = []
                for c in range(self.width):
                    val = self.board[r][c]
                    btn = tk.Button(self.board_frame, text="" if val == 0 else str(val),
                                    width=button_width, height=button_height, font=("Arial", font_size, "bold"),
                                    command=lambda rr=r, cc=c: self.move(rr, cc),
                                    bg=get_tile_color(val), activebackground=get_tile_color(val))
                    btn.grid(row=r, column=c)
                    row_buttons.append(btn)
                self.buttons.append(row_buttons)

        for r in range(self.height):
            for c in range(self.width):
                val = self.board[r][c]
                self.buttons[r][c].config(text="" if val == 0 else str(val),
                                          bg=get_tile_color(val), activebackground=get_tile_color(val),
                                          state=tk.NORMAL if not self.is_locked else tk.DISABLED)

        if self.is_solved_board(board=self.board):
            self.solvable_label.config(text="Solved ✔", fg="blue")
        else:
            flat = [x for row in self.board for x in row]
            if self.is_solvable(flat):
                self.solvable_label.config(text="Solvable ✔", fg="green")
            else:
                self.solvable_label.config(text="Not Solvable ✘", fg="red")

    def update_two_buttons(self, r1, c1, r2, c2):
        import colorsys
        traversal_order = self.traversal(self.width, self.height)
        val_to_pos = {val: i for i, (val, _) in enumerate(traversal_order)}
        max_pos = len(traversal_order) - 1

        def get_tile_color(val):
            if val == 0: return "#FFFFFF"
            t = val_to_pos[val] / max_pos if max_pos > 0 else 0
            h = 0.0 + 0.75 * t
            r, g, b = colorsys.hsv_to_rgb(h, 0.4, 0.95)
            return f'#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}'

        for r, c in [(r1, c1), (r2, c2)]:
            val = self.board[r][c]
            self.buttons[r][c].config(text="" if val == 0 else str(val),
                                      bg=get_tile_color(val), activebackground=get_tile_color(val))

    def is_solved_board(self, board=None):
        if board is None: board = self.board
        target = [[(i * self.width + j + 1) % (self.width * self.height) for j in range(self.width)] for i in
                  range(self.height)]
        return board == target

    def lock_board(self):
        if self.is_locked:
            return
        self.is_locked = True
        duration = (datetime.now() - self.start_time).total_seconds()

        for row in self.buttons:
            for btn in row:
                btn.config(state=tk.DISABLED)

        self.undo_button.config(state=tk.DISABLED)
        self.redo_button.config(state=tk.DISABLED)

        for child in self.frame.winfo_children():
            for widget in child.winfo_children():
                if isinstance(widget, tk.Button) and widget.cget("text") in ("Generate", "Generate Solvable"):
                    widget.config(state=tk.NORMAL)

        if GLOBAL_LOGGER:
            GLOBAL_LOGGER.send_protocol_message("stats", rows=self.height, cols=self.width, moves=self.move_count, time=round(duration, 2), solved=True)


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Sliding Puzzle")
    root.geometry("800x900")
    puzzle = SlidingPuzzle(root)


    def on_closing():
        global GLOBAL_LOGGER
        if GLOBAL_LOGGER and GLOBAL_LOGGER.is_connected:
            GLOBAL_LOGGER.send_log("INFO", "Client application closing.")
            GLOBAL_LOGGER.socket.close()
        root.destroy()


    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()