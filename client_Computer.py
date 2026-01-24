import tkinter as tk
from tkinter import ttk
import random
from copy import deepcopy
import threading
import heapq
from collections import deque
import socket
import json
from datetime import datetime
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
            # Set a short timeout to prevent long blocking.
            self.socket.settimeout(2)
            self.socket.connect((self.host, self.port))
            # Remove timeout after successful connection.
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
            # We must add the \n because your server.py uses buffer.split('\n')
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

        # If disconnected, log locally instead of sending.
        if not self.is_connected or not self.socket:
            self._log_local(level, message)
            return

        # Create the log object.
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "source": "ComputerPuzzleClient"
        }

        # Convert to JSON, encode, and append newline separator.
        try:
            log_message = json.dumps(log_entry).encode('utf-8') + b'\n'
            self.socket.sendall(log_message)
        except socket.error as e:
            self.is_connected = False
            self.socket.close()
            self.socket = None
            self._log_local("ERROR", f"Socket error while sending log: {e}. Connection lost.")


# Define the global logger object.
GLOBAL_LOGGER = None


# Wrapper Functions for logging
def custom_log(level, message, *args):
    """Generic function to send logs via SocketLogger."""
    if GLOBAL_LOGGER:
        # Format message with args similar to the standard logging module.
        formatted_message = message % args if args else message
        GLOBAL_LOGGER.send_log(level, formatted_message)


def info(message, *args):
    custom_log("INFO", message, *args)


def debug(message, *args):
    custom_log("DEBUG", message, *args)


def error(message, *args):
    custom_log("ERROR", message, *args)


# --- End Socket Logger Class & Wrappers ---


class SlidingPuzzle:

    # ==================== init (VIEW) ==================== #
    def __init__(self, parent):

        # SocketLogger initialization
        SERVER_HOST = '127.0.0.1'
        SERVER_PORT = 8080

        global GLOBAL_LOGGER
        GLOBAL_LOGGER = SocketLogger(SERVER_HOST, SERVER_PORT)
        GLOBAL_LOGGER.send_protocol_message("connect", client_type="computer")

        # Initial setup
        self.move_count = 0
        self.parent = parent
        self.frame = tk.Frame(parent)
        self.frame.pack()

        # WATCHDOG: since the algorithm is very fast, If it takes more then 7 seconds we can
        # almost certainly assume it will take more then 120 seconds (got stuck)
        self.solver_timeout = 7  # seconds
        self.solver_start_time = None
        self.solver_watchdog_id = None

        self.memento_stack = []
        self.redo_stack = []

        self.width = 3
        self.height = 3
        self.board = []
        self.buttons = []

        self.solver_thread = None
        self.abort_solver = False

        self.speed_states = [
            ("0.1x", 1000),
            ("0.25x", 400),
            ("0.5x", 200),
            ("1x", 100),
            ("10x", 10),
            ("25x", 4),
            ("50x", 2),
            ("100x", 1),
        ]

        # --- Controls ---
        control_frame = tk.Frame(self.frame)
        control_frame.pack()

        # width/height sliders
        tk.Label(control_frame, text="Cols").grid(row=0, column=0)
        self.width_slider = tk.Scale(control_frame, from_=3, to=9, orient=tk.HORIZONTAL, length=300)
        self.width_slider.set(self.width)
        self.width_slider.grid(row=0, column=1)

        tk.Label(control_frame, text="Rows").grid(row=1, column=0)
        self.height_slider = tk.Scale(control_frame, from_=3, to=9, orient=tk.HORIZONTAL, length=300)
        self.height_slider.set(self.height)
        self.height_slider.grid(row=1, column=1)

        # generate button
        self.dimensions_changed = False  # Flag to track unsaved changes

        self.width_slider.config(command=self.on_dimensions_change)
        self.height_slider.config(command=self.on_dimensions_change)

        self.generate_button = tk.Button(control_frame, text="Generate", command=self.generate_random)
        self.generate_button.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5)

        ttk.Separator(control_frame, orient=tk.HORIZONTAL).grid(row=3, column=0, columnspan=2, sticky="ew", pady=5)

        # Computer specific controls
        self.speed_label = tk.Label(control_frame, text="Speed (1x)")
        self.speed_label.grid(row=4, column=0)

        self.speed_slider = tk.Scale(
            control_frame,
            from_=0,
            to=len(self.speed_states) - 1,
            orient=tk.HORIZONTAL,
            length=300,
            showvalue=False,
            command=self.on_speed_change
        )
        self.speed_slider.set(3)  # default = "1x"
        self.speed_slider.grid(row=4, column=1)

        self.solve_button = tk.Button(control_frame, text="Solve", command=self.toggle_solver, width=24)
        self.solve_button.grid(row=5, column=0, columnspan=2, pady=10)

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

        # --- Timer Logic Variables ---
        self.is_locked = False
        self.is_timer_running = False  # Track if solver is active
        self.elapsed_time = 0  # Cumulative seconds
        self.last_start_time = None  # Last time 'Solve' was pressed

        self.update_timer()

        self.generate_solvable()

    def on_speed_change(self, value):
        idx = int(value)
        label, real_value = self.speed_states[idx]
        self.current_speed = real_value
        self.speed_label.config(text=f"Speed: {label}")

    # ==================== Puzzle Generation (CONTROLLER) ==================== #
    def generate_random(self):
        # Reset timer and game state only for a new game
        self.elapsed_time = 0
        self.is_timer_running = False
        self.last_start_time = None
        self.is_locked = False  # This allows update_timer to start running again
        self.move_count = 0

        # IMPORTANT: Restart the timer loop because it was stopped in lock_board
        self.update_timer()

        self.width = self.width_slider.get()
        self.height = self.height_slider.get()
        nums = list(range(1, self.width * self.height)) + [0]
        random.shuffle(nums)

        self.memento_stack.clear()
        self.redo_stack.clear()
        self.buttons.clear()

        self.board = [nums[i * self.width:(i + 1) * self.width] for i in range(self.height)]
        self.draw_board()
        self.move_count = 0
        self.moves_label.config(text=f"Moves: {self.move_count}")
        self.enable_all_buttons()
        self.dimensions_changed = False
        self.generate_button.config(text="Generate")
        info("Puzzle generated (width=%d, height=%d)", self.width, self.height)
        self.is_locked = False  # Reset the lock for the new game
        self.start_time = datetime.now()  # Reset the timer for the new game
        self.draw_board()

    def on_dimensions_change(self, value):
        # Mark that dimensions changed
        self.dimensions_changed = True
        # Update Generate button text
        self.generate_button.config(text="Generate (CLICK TO UPDATE)")

    def generate_solvable(self):
        # Reset timer and game state only for a new game
        self.elapsed_time = 0
        self.is_timer_running = False
        self.last_start_time = None
        self.is_locked = False  # This allows update_timer to start running again
        self.move_count = 0

        # IMPORTANT: Restart the timer loop because it was stopped in lock_board
        self.update_timer()


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

        self.board = [nums[i * self.width:(i + 1) * self.width] for i in range(self.height)]
        self.draw_board()
        self.move_count = 0
        self.moves_label.config(text=f"Moves: {self.move_count}")
        self.enable_all_buttons()
        info("Puzzle generated (width=%d, height=%d)", self.width, self.height)
        self.is_locked = False  # Reset the lock for the new game
        self.start_time = datetime.now()  # Reset the timer for the new game
        self.draw_board()

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
        for i in range(self.height):
            for j in range(self.width):
                if self.board[i][j] == 0:
                    er, ec = i, j
        if abs(er - r) + abs(ec - c) == 1:
            self.board[er][ec], self.board[r][c] = self.board[r][c], self.board[er][ec]
            self.move_count += 1
            self.moves_label.config(text=f"Moves: {self.move_count}")
            self.update_two_buttons(er, ec, r, c)
            debug("Tile moved: (%d, %d) -> (%d, %d)", r, c, er, ec)
            if self.is_solved_board(board=self.board):
                info("Puzzle solved in %d moves", self.move_count)
                self.draw_board()
                self.lock_board()
        else:
            debug("Illegal move attempted: (%d, %d)", r, c)

    def perform_move(self, move):
        er, ec = [(i, j) for i in range(self.height) for j in range(self.width) if self.board[i][j] == 0][0]
        if move == "DOWN" and er + 1 < self.height:
            self.move(er + 1, ec)
        elif move == "UP" and er - 1 >= 0:
            self.move(er - 1, ec)
        elif move == "RIGHT" and ec + 1 < self.width:
            self.move(er, ec + 1)
        elif move == "LEFT" and ec - 1 >= 0:
            self.move(er, ec - 1)

    def traversal(self, width, height):
        # Initialize the matrix numbers sequentially
        matrix = [[r * width + c + 1 for c in range(width)] for r in range(height)]
        result = []

        top, left = 0, 0
        bottom, right = height - 1, width - 1

        # Shrink to square by removing from top rows or left columns
        while (bottom - top) != (right - left):
            if (bottom - top) > (right - left):
                # Remove top row
                for c in range(left, right + 1):
                    result.append((matrix[top][c], True))
                top += 1
            else:
                # Remove left column
                for r in range(top, bottom + 1):
                    result.append((matrix[r][left], False))
                left += 1

        # Now it's square; do row/column traversal
        while top <= bottom and left <= right:
            # Take top row
            for c in range(left, right + 1):
                result.append((matrix[top][c], True))
            top += 1

            # Take leftmost column
            for r in range(top, bottom + 1):
                result.append((matrix[r][left], False))
            left += 1

            # Take next row (if any)
            if top <= bottom:
                for c in range(left, right + 1):
                    result.append((matrix[top][c], True))
                top += 1

            # Take next column (if any)
            if left <= right:
                for r in range(top, bottom + 1):
                    result.append((matrix[r][left], False))
                left += 1

        return result

    # ==================== Drawing (VIEW) ==================== #
    def update_timer(self):
        """Updates the display. If locked, the loop terminates to freeze the time."""
        if self.is_locked:
            return

        display_time = self.elapsed_time
        if self.is_timer_running and self.last_start_time:
            session_seconds = (datetime.now() - self.last_start_time).total_seconds()
            display_time += session_seconds

        try:
            self.timer_label.config(text=f"Time: {display_time:.1f}s")
        except:
            return  # Stop if widget is destroyed

        # Clear any existing 'after' calls to prevent speed-up bugs
        if hasattr(self, '_timer_after_id'):
            self.parent.after_cancel(self._timer_after_id)

        # Schedule the next update and save its ID
        self._timer_after_id = self.parent.after(100, self.update_timer)

    def draw_board(self):
        # Calculate button size and font dynamically
        max_button_width = max(3, 30 // self.width)
        max_button_height = max(2, 20 // self.height)
        button_width = min(max_button_width, 8)
        button_height = min(max_button_height, 4)
        font_size = max(8, 14 - (self.width + self.height - 8) // 2)

        import colorsys

        # Generate traversal order for color mapping
        traversal_order = self.traversal(self.width, self.height)
        val_to_pos = {val: i for i, (val, _) in enumerate(traversal_order)}
        max_pos = len(traversal_order) - 1

        def get_tile_color(val):
            if val == 0:
                return "#FFFFFF"
            t = val_to_pos[val] / max_pos if max_pos > 0 else 0
            h = 0.0 + 0.75 * t
            r, g, b = colorsys.hsv_to_rgb(h, 0.4, 0.95)
            return f'#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}'

        # Rebuild button grid if needed
        if (
                not self.buttons
                or len(self.buttons) != self.height
                or len(self.buttons[0]) != self.width
        ):
            for w in self.board_frame.winfo_children():
                w.destroy()
            self.buttons.clear()

            for r in range(self.height):
                row_buttons = []
                for c in range(self.width):

                    if not self.solver_thread or not self.solver_thread.is_alive():
                        cmd = lambda rr=r, cc=c: self.move(rr, cc)
                    else:
                        cmd = None

                    val = self.board[r][c]
                    text = "" if val == 0 else str(val)
                    color = get_tile_color(val)

                    btn = tk.Button(
                        self.board_frame,
                        text=text,
                        width=button_width,
                        height=button_height,
                        font=("Arial", font_size, "bold"),
                        command=cmd,
                        bg=color,
                        activebackground=color
                    )
                    btn.grid(row=r, column=c)
                    row_buttons.append(btn)

                self.buttons.append(row_buttons)

        # Update existing buttons
        for r in range(self.height):
            for c in range(self.width):
                val = self.board[r][c]
                text = "" if val == 0 else str(val)
                color = get_tile_color(val)
                self.buttons[r][c].config(text=text, bg=color, activebackground=color)

        # Update solvable status
        if self.is_solved_board(board=self.board):
            self.solvable_label.config(text="Solved ✔", fg="blue")
            self.solve_button.config(state=tk.DISABLED)
        else:
            flat = [x for row in self.board for x in row]
            if self.is_solvable(flat):
                self.solvable_label.config(text="Solvable ✔", fg="green")
                self.solve_button.config(state=tk.NORMAL)
            else:
                self.solvable_label.config(text="Not Solvable ✘", fg="red")
                self.solve_button.config(state=tk.DISABLED)

    def update_two_buttons(self, r1, c1, r2, c2):
        v1 = self.board[r1][c1]
        v2 = self.board[r2][c2]

        import colorsys
        traversal_order = self.traversal(self.width, self.height)
        val_to_pos = {val: i for i, (val, _) in enumerate(traversal_order)}
        max_pos = len(traversal_order) - 1

        def get_tile_color(val):
            if val == 0:
                return "#FFFFFF"
            t = val_to_pos[val] / max_pos if max_pos > 0 else 0
            h = 0.0 + 0.75 * t
            r, g, b = colorsys.hsv_to_rgb(h, 0.4, 0.95)
            return f'#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}'

        self.buttons[r1][c1].config(
            text="" if v1 == 0 else str(v1),
            bg=get_tile_color(v1),
            activebackground=get_tile_color(v1)
        )
        self.buttons[r2][c2].config(
            text="" if v2 == 0 else str(v2),
            bg=get_tile_color(v2),
            activebackground=get_tile_color(v2)
        )

    # ==================== Solver (MODEL) ==================== #
    def toggle_solver(self):
        if self.solve_button.cget("text") == "Abort":
            # PAUSE TIMER ON ABORT
            info("Abort requested - Timer paused")
            self.abort_solver = True
            self.is_timer_running = False

            # Save the time gathered in this session
            if self.last_start_time:
                self.elapsed_time += (datetime.now() - self.last_start_time).total_seconds()

            # Cancel watchdog
            if self.solver_watchdog_id:
                self.parent.after_cancel(self.solver_watchdog_id)
                self.solver_watchdog_id = None
            return
        else:
            # START TIMER + SOLVER
            self.abort_solver = False
            self.is_timer_running = True
            self.last_start_time = datetime.now()
            self.solver_start_time = datetime.now()

            self.disable_buttons_for_solver()
            self.solve_button.config(text="Abort")

            # Start solver thread
            self.solver_thread = threading.Thread(target=self.solve_puzzle, daemon=True)
            self.solver_thread.start()

            # Start 15s watchdog
            self.start_solver_watchdog()


    def disable_buttons_for_solver(self):
        for row in self.buttons:
            for btn in row:
                btn.config(state=tk.DISABLED)
        # Keep only Solve/Abort button enabled
        for child in self.frame.winfo_children():
            for widget in child.winfo_children():
                if isinstance(widget, tk.Button) and widget != self.solve_button:
                    widget.config(state=tk.DISABLED)

    def enable_all_buttons(self):
        # Re-enable board buttons with move commands for non-human mode
        for r in range(self.height):
            for c in range(self.width):
                self.buttons[r][c].config(state=tk.NORMAL, command=lambda rr=r, cc=c: self.move(rr, cc))

        # Enable control buttons
        for child in self.frame.winfo_children():
            for widget in child.winfo_children():
                if isinstance(widget, tk.Button):
                    widget.config(state=tk.NORMAL)
        self.solve_button.config(text="Solve")

    def start_solver_watchdog(self):
        """Stops solver if it exceeds time limit."""
        def watchdog():
            if self.abort_solver:
                return

            elapsed = (datetime.now() - self.solver_start_time).total_seconds()
            if elapsed >= self.solver_timeout:
                # TIMEOUT
                self.abort_solver = True
                error("Solver Won't solve in the time specified")   # log message

                # Stop timer
                self.is_timer_running = False
                if self.last_start_time:
                    self.elapsed_time += (datetime.now() - self.last_start_time).total_seconds()

                # UI reset safely in main thread
                self.parent.after(0, self.on_solver_failed)
            else:
                # Re-check after 100ms
                self.solver_watchdog_id = self.parent.after(100, watchdog)

        self.solver_watchdog_id = self.parent.after(100, watchdog)

    def on_solver_failed(self):
        info("Aborting solver")
        self.solve_button.config(text="Solve")
        self.enable_all_buttons()

    def solve_puzzle_astar(self, board):
        width = len(board[0])
        height = len(board)
        start = tuple(sum(board, []))
        target = tuple(list(range(1, width * height)) + [0])

        def manhattan(state):
            dist = 0
            for idx, val in enumerate(state):
                if val == 0:
                    continue
                goal_r, goal_c = divmod(val - 1, width)
                r, c = divmod(idx, width)
                dist += abs(r - goal_r) + abs(c - goal_c)
            return dist

        visited = set()
        heap = [(manhattan(start), 0, start, [])]  # f, g, state, moves
        directions = [("DOWN", 1, 0), ("UP", -1, 0), ("RIGHT", 0, 1), ("LEFT", 0, -1)]

        while heap:
            # Check for abort signal
            if self.abort_solver:
                return None

            f, g, state, path = heapq.heappop(heap)
            if state == target:
                return path

            if state in visited:
                continue
            visited.add(state)

            zero_idx = state.index(0)
            r, c = divmod(zero_idx, width)
            for name, dr, dc in directions:
                nr, nc = r + dr, c + dc
                if 0 <= nr < height and 0 <= nc < width:
                    new_idx = nr * width + nc
                    new_state = list(state)
                    new_state[zero_idx], new_state[new_idx] = new_state[new_idx], new_state[zero_idx]
                    heapq.heappush(heap, (g + 1 + manhattan(new_state), g + 1, tuple(new_state), path + [name]))

    def solve_puzzle_human(self, board):
        # ---- init ---- #
        board_copy = deepcopy(board)
        prev = (-1, -1)
        repeat_count = 0

        # ---- helper functions ---- #

        def find_tile(value):
            for r in range(len(board_copy)):
                for c in range(len(board_copy[0])):
                    if board_copy[r][c] == value:
                        return r, c
            return None

        def move_copy(br, bc, move):
            if move == "UP":
                board_copy[br][bc], board_copy[br - 1][bc] = board_copy[br - 1][bc], board_copy[br][bc]
            elif move == "DOWN":
                board_copy[br][bc], board_copy[br + 1][bc] = board_copy[br + 1][bc], board_copy[br][bc]
            elif move == "LEFT":
                board_copy[br][bc], board_copy[br][bc - 1] = board_copy[br][bc - 1], board_copy[br][bc]
            elif move == "RIGHT":
                board_copy[br][bc], board_copy[br][bc + 1] = board_copy[br][bc + 1], board_copy[br][bc]

        def move_blank(target_r, target_c, tile_r, tile_c):
            nonlocal prev, repeat_count
            if prev == (tile_r, tile_c):
                repeat_count += 1
                if repeat_count >= 50:
                    error("Stuck in loop at tile %d,%d", tile_r, tile_c)
                    raise Exception(f"Stuck in loop at tile {tile_r},{tile_c}")
            else:
                prev = (tile_r, tile_c)
                repeat_count = 0
            start_r, start_c = find_tile(0)
            rows = len(board_copy)
            cols = len(board_copy[0])

            # Directions: (dr, dc, name)
            DIRS = [
                (-1, 0, "UP"),
                (1, 0, "DOWN"),
                (0, -1, "LEFT"),
                (0, 1, "RIGHT")
            ]

            debug(f"Targeting blank move to: {(target_r, target_c)}")

            # BFS queue: (r, c, path_so_far)
            q = deque()
            q.append((start_r, start_c, []))
            visited = set([(start_r, start_c)])

            while q:
                r, c, path = q.popleft()

                # Found target → apply moves to board_copy
                if (r, c) == (target_r, target_c):
                    # Execute moves on board_copy
                    for move in path:
                        # Determine the position of the tile that moves into the blank spot
                        if move == "UP":
                            nr, nc = r + 1, c
                        elif move == "DOWN":
                            nr, nc = r - 1, c
                        elif move == "LEFT":
                            nr, nc = r, c + 1
                        elif move == "RIGHT":
                            nr, nc = r, c - 1

                        # Actually swap (do forward-looking swap)
                        br, bc = find_tile(0)
                        move_copy(br, bc, move)

                    return path

                # Explore neighbors
                for dr, dc, name in DIRS:
                    nr, nc = r + dr, c + dc

                    if 0 <= nr < rows and 0 <= nc < cols:
                        # Avoid moving completed tiles, the tile being moved, and already visited positions
                        if (nr, nc) not in completed and (nr, nc) != (tile_r, tile_c) and (nr, nc) not in visited:
                            visited.add((nr, nc))
                            q.append((nr, nc, path + [name]))
            return []

        def move_tile_to(tile_value, target_r, target_c):
            blank_r, blank_c = find_tile(0)
            moves = []

            tile_r, tile_c = -1, -1

            while (tile_r != target_r or tile_c != target_c):

                tile_r, tile_c = find_tile(tile_value)
                # Move tile horizontally
                if tile_c > target_c:
                    moves += move_blank(tile_r, tile_c - 1, tile_r, tile_c)
                    blank_r, blank_c = find_tile(0)
                    moves.append("RIGHT")
                    move_copy(blank_r, blank_c, "RIGHT")
                if tile_c < target_c:
                    moves += move_blank(tile_r, tile_c + 1, tile_r, tile_c)
                    blank_r, blank_c = find_tile(0)
                    moves.append("LEFT")
                    move_copy(blank_r, blank_c, "LEFT")

                tile_r, tile_c = find_tile(tile_value)
                # Move tile vertically
                if tile_r > target_r:
                    moves += move_blank(tile_r - 1, tile_c, tile_r, tile_c)
                    blank_r, blank_c = find_tile(0)
                    moves.append("DOWN")
                    move_copy(blank_r, blank_c, "DOWN")
                if tile_r < target_r:
                    moves += move_blank(tile_r + 1, tile_c, tile_r, tile_c)
                    blank_r, blank_c = find_tile(0)
                    moves.append("UP")
                    move_copy(blank_r, blank_c, "UP")
            return moves

        def is_bottom_right_correct(board):
            h = self.height
            w = self.width

            if h < 3 or w < 3:
                error("Board must be at least 3x3 for a bottom-right subgrid check.")
                raise ValueError("Board must be at least 3x3 for a bottom-right subgrid check.")

            # Extract bottom-right 3×3 region
            subgrid = [row[w - 3:] for row in board[h - 3:]]

            # Flatten
            flat = [v for row in subgrid for v in row]

            # Compute expected numbers in that 3×3 region
            target_numbers = []
            for r in range(h - 3, h):
                for c in range(w - 3, w):
                    target_numbers.append((r * w + c + 1) % (w * h))

            return sorted(flat) == sorted(target_numbers)

        # ---- main logic ---- #
        self.draw_board()
        moves = []
        completed = []
        for num, isRow in self.traversal(self.width, self.height)[:-1]:
            target_r = (num - 1) // self.width
            target_c = (num - 1) % self.width
            debug(f"Completed list: {completed}")
            try:
                # Break condition for bottom-right 3x3
                if target_r == self.height - 3 and target_c == self.width - 3:
                    break

                # one before last in row
                if target_c == self.width - 2 and isRow:
                    target_c += 1
                    if board_copy[target_r][target_c] == num + 1:
                        moves += move_tile_to(num + 1, target_r + 2, target_c)
                    moves += move_tile_to(num, target_r, target_c)
                    if find_tile(0) == (target_r, target_c - 1):
                        blank_r, blank_c = find_tile(0)
                        moves.append("DOWN")
                        move_copy(blank_r, blank_c, "DOWN")
                    if find_tile(0) == (target_r + 1, target_c):
                        blank_r, blank_c = find_tile(0)
                        moves.append("RIGHT")
                        move_copy(blank_r, blank_c, "RIGHT")
                # last in row
                elif target_c == self.width - 1 and isRow:
                    target_r += 1
                    moves += move_tile_to(num, target_r, target_c)
                    moves += move_tile_to(num, target_r - 1, target_c)
                    completed.append((target_r - 1, target_c))
                    completed.append((target_r - 1, target_c - 1))
                    isRow = False
                # one before last in col
                elif target_r == self.height - 2 and not isRow:
                    target_r += 1
                    if board_copy[target_r][target_c] == target_r * self.width + target_c + 1:
                        moves += move_tile_to((target_r * self.width + target_c + 1), target_r, target_c + 2)
                    moves += move_tile_to(num, target_r, target_c)
                    if find_tile(0) == (target_r, target_c + 1):
                        blank_r, blank_c = find_tile(0)
                        moves.append("UP")
                        move_copy(blank_r, blank_c, "UP")
                    if find_tile(0) == (target_r - 1, target_c):
                        blank_r, blank_c = find_tile(0)
                        moves.append("RIGHT")
                        move_copy(blank_r, blank_c, "RIGHT")
                # last in col
                elif target_r == self.height - 1 and not isRow:
                    target_c += 1
                    moves += move_tile_to(num, target_r, target_c)
                    moves += move_tile_to(num, target_r, target_c - 1)
                    completed.append((target_r, target_c - 1))
                    completed.append((target_r - 1, target_c - 1))
                    isRow = True
                # everything else
                else:
                    moves += move_tile_to(num, target_r, target_c)
                    completed.append((target_r, target_c))
            except Exception as e:
                debug("Algorithm anomaly avoided")

        # Extract sub-board, normalize and send to A-star
        br_start, bc_start = self.width - 3, self.height - 3
        sub_board = [row[br_start:] for row in board_copy[bc_start:]]
        flat = [v for row in sub_board for v in row]
        unique_values = sorted(flat)
        mapping = {val: i for i, val in enumerate(unique_values)}
        normalized_sub_board = [[mapping[v] for v in row] for row in sub_board]
        normalized_sub_board_flat = [v for row in normalized_sub_board for v in row]
        if (self.is_solvable(normalized_sub_board_flat) and is_bottom_right_correct(board_copy)):
            sub_moves = self.solve_puzzle_astar(normalized_sub_board)
            if sub_moves is not None:
                for move in sub_moves:
                    blank_r, blank_c = find_tile(0)
                    move_copy(blank_r, blank_c, move)
                moves += sub_moves
        else:
            debug("Sub-board unsolvable, performing reshuffle...")
            completed = []
            fix_moves = self.solve_puzzle_human(board_copy)
            if fix_moves is not None:
                for move in fix_moves:
                    blank_r, blank_c = find_tile(0)
                    moves.append(move)
                    try:
                        move_copy(blank_r, blank_c, move)
                    except IndexError as e:
                        debug("Algorithm anomaly avoided")

        return moves

    def solve_puzzle(self):
        info("Solver started")
        self.abort_solver = False
        try:
            moves = self.solve_puzzle_human(self.board)

            # Cancel watchdog
            if self.solver_watchdog_id:
                self.parent.after_cancel(self.solver_watchdog_id)
                self.solver_watchdog_id = None

            # abort
            if self.abort_solver or moves is None:
                info("Solver aborted")
                self.parent.after(0, self.enable_all_buttons())
            else:
                info("Solver finished")
                self.parent.after(0, lambda: self.animate_solution(moves))
        except Exception as e:
            error("Solver crashed: %s", e)
            self.parent.after(0, self.enable_all_buttons())

    def animate_solution(self, moves):
        if not moves or self.abort_solver:
            info("Animation stopped")
            self.enable_all_buttons()
            return

        move = moves.pop(0)
        self.perform_move(move)

        # If this was the last move, lock the board after animation completes
        if not moves:
            delay = self.current_speed
            self.parent.after(delay, self.lock_board)
        else:
            delay = self.current_speed
            self.parent.after(delay, lambda: self.animate_solution(moves))

    def is_solved_board(self, board=None):
        if board is None:
            board = self.board
        target = [[(i * self.width + j + 1) % (self.width * self.height)
                   for j in range(self.width)] for i in range(self.height)]
        return board == target

    def lock_board(self):
        """
        Finalizes the puzzle session. Stops the timer, disables interaction,
        calculates total solving time, and reports stats to the server.
        """
        # 1. THE GUARD: Prevent duplicate execution
        if self.is_locked:
            return
        self.is_locked = True

        # --- Timer Management Addition ---
        # Stops the background timer logic from calculating further sessions
        self.is_timer_running = False

        # 2. THE TIMER: Calculate actual seconds elapsed
        # Computes total time: Time accumulated before previous Aborts + time from current session
        total_final_time = self.elapsed_time
        if self.last_start_time:
            total_final_time += (datetime.now() - self.last_start_time).total_seconds()

        # 3. THE UI: Disable the game grid
        for row in self.buttons:
            for btn in row:
                btn.config(state=tk.DISABLED)

        # 4. THE CONTROLS: Handle specific buttons
        if hasattr(self, 'solve_button'):
            self.solve_button.config(text="Solve", state=tk.DISABLED)

        # Re-enable the "Generate" buttons for the next game
        for child in self.frame.winfo_children():
            for widget in child.winfo_children():
                if isinstance(widget, tk.Button) and widget.cget("text") in ("Generate", "Generate Solvable"):
                    widget.config(state=tk.NORMAL)

        # 5. THE NETWORK: Send the finalized data to the Server
        if GLOBAL_LOGGER:
            # Using the new total_final_time variable instead of a single duration
            GLOBAL_LOGGER.send_protocol_message(
                "stats",
                rows=self.height,
                cols=self.width,
                moves=self.move_count,
                time=round(total_final_time, 2),
                solved=True
            )
    def log_board(self, board=None):
        if board is None:
            board = self.board
        board_str = "\n".join(["\t".join(f"{val:2}" for val in row) for row in board])
        info("Current board:\n%s", board_str)


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Sliding Puzzle (Computer)")
    root.geometry("800x900")
    puzzle = SlidingPuzzle(root)


    # Handle window close event to ensure socket cleanup.
    def on_closing():
        global GLOBAL_LOGGER
        if GLOBAL_LOGGER and GLOBAL_LOGGER.is_connected:
            GLOBAL_LOGGER.send_log("INFO", "Client application closing.")
            GLOBAL_LOGGER.socket.close()
        root.destroy()


    root.protocol("WM_DELETE_WINDOW", on_closing)

    root.mainloop()