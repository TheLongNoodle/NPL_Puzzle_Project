import tkinter as tk
from tkinter import ttk
import random
import logging
from copy import deepcopy
import threading
import heapq
from collections import deque


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class SlidingPuzzle:

    # ==================== init (VIEW) ==================== #
    def __init__(self, parent):

        # Initial setup
        self.move_count = 0
        self.parent = parent
        self.frame = tk.Frame(parent)
        self.frame.pack()

        self.memento_stack = []
        self.redo_stack = []

        self.width = 9
        self.height = 9
        self.board = []
        self.buttons = []

        self.solver_thread = None
        self.abort_solver = False

        # --- Controls ---
        control_frame = tk.Frame(self.frame)
        control_frame.pack()

        # width/height
        tk.Label(control_frame, text="Width").grid(row=0, column=0)
        self.width_slider = tk.Scale(control_frame, from_=3, to=25, orient=tk.HORIZONTAL, length=300)
        self.width_slider.set(self.width)
        self.width_slider.grid(row=0, column=1)

        #tk.Label(control_frame, text="Height").grid(row=1, column=0)
        tk.Label(control_frame, text="Size").grid(row=1, column=0)
        self.height_slider = tk.Scale(control_frame, from_=3, to=25, orient=tk.HORIZONTAL, length=300)
        self.height_slider.set(self.height)
        self.height_slider.grid(row=1, column=1)

        #generate buttons
        tk.Button(control_frame, text="Generate", command=self.generate_random).grid(row=2, column=0, columnspan=2, sticky="ew", padx=5)

        #DEBUG
        #tk.Button(control_frame, text="Generate Solvable", command=self.generate_solvable).grid(row=2, column=1, sticky="ew", padx=5)

        ttk.Separator(control_frame, orient=tk.HORIZONTAL).grid(row=3, column=0, columnspan=2, sticky="ew", pady=5)

        # Human/Computer specific controls
        self.board_frame = tk.Frame(self.frame)
        self.board_frame.pack()

        # Undo/Redo
        bottom_frame = tk.Frame(self.frame)
        bottom_frame.pack(pady=10)

        self.undo_button = tk.Button(bottom_frame, text="Undo", command=self.undo)
        self.undo_button.pack(side=tk.LEFT, padx=10)

        # Solvability label
        self.solvable_label = tk.Label(bottom_frame, text="", font=("Arial", 12, "bold"))
        self.solvable_label.pack(side=tk.LEFT, padx=20)

        self.redo_button = tk.Button(bottom_frame, text="Redo", command=self.redo)
        self.redo_button.pack(side=tk.LEFT, padx=10)

        self.generate_solvable()

    # ==================== Undo/Redo logic (CONTROLLER) ==================== #
    def save_state(self):
        self.memento_stack.append(deepcopy(self.board))
        self.redo_stack.clear()
        logging.debug("State saved. Stack size: %d", len(self.memento_stack))

    def undo(self):
        if self.memento_stack:
            self.redo_stack.append(deepcopy(self.board))
            self.board = self.memento_stack.pop()
            self.draw_board()
            logging.debug("Undo performed. Remaining states: %d", len(self.memento_stack))
        else:
            logging.debug("Undo attempted but undo stack is empty")

    def redo(self):
        if self.redo_stack:
            self.memento_stack.append(deepcopy(self.board))
            self.board = self.redo_stack.pop()
            self.draw_board()
            logging.debug("Redo performed. Remaining redo states: %d", len(self.redo_stack))
        else:
            logging.debug("Redo attempted but redo stack is empty")

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

        self.board = [nums[i*self.width:(i+1)*self.width] for i in range(self.height)]
        self.save_state()
        self.draw_board()
        logging.info("Puzzle generated (width=%d, height=%d)", self.width, self.height)

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

        self.board = [nums[i*self.width:(i+1)*self.width] for i in range(self.height)]
        self.save_state()
        self.draw_board()
        logging.info("Puzzle generated (width=%d, height=%d)", self.width, self.height)

    def is_solvable(self, nums):
        inv = 0
        nums_no_zero = [x for x in nums if x != 0]
        for i in range(len(nums_no_zero)):
            for j in range(i+1, len(nums_no_zero)):
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
            self.save_state()
            self.board[er][ec], self.board[r][c] = self.board[r][c], self.board[er][ec]
            self.move_count += 1
            self.update_two_buttons(er, ec, r, c)
            logging.debug("Tile moved: (%d, %d) -> (%d, %d)", r, c, er, ec)
            if self.is_solved_board(board=self.board):
                logging.info("Puzzle solved in %d moves", self.move_count)
                self.draw_board()
                self.lock_board()
        else:
            logging.debug("Illegal move attempted: (%d, %d)", r, c)

    def perform_move(self, move):
        er, ec = [(i, j) for i in range(self.height) for j in range(self.width) if self.board[i][j] == 0][0]
        if move == "DOWN" and er + 1 < self.height:
            self.move(er+1, ec)
        elif move == "UP" and er - 1 >= 0:
            self.move(er-1, ec)
        elif move == "RIGHT" and ec + 1 < self.width:
            self.move(er, ec+1)
        elif move == "LEFT" and ec - 1 >= 0:
            self.move(er, ec-1)

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

        # Now it's square; do row/column traversal (top to bottom rows, left to right columns)
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

    def draw_board(self):
        # Calculate button size
        max_button_width = max(3, 30 // self.width)
        max_button_height = max(2, 20 // self.height)
        button_width = min(max_button_width, 8)
        button_height = min(max_button_height, 4)
        font_size = max(8, 14 - (self.width + self.height - 8) // 2)

        import colorsys

        # Generate traversal order
        traversal_order = self.traversal(self.width, self.height)
        val_to_pos = {val: i for i, (val, _) in enumerate(traversal_order)}
        max_pos = len(traversal_order) - 1

        def get_tile_color(val):
            if val == 0:
                return "#FFFFFF"
            t = val_to_pos[val] / max_pos if max_pos > 0 else 0
            h = 0.0 + 0.75 * t
            r, g, b = colorsys.hsv_to_rgb(h, 0.4, 0.95)
            return f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'

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
        else:
            flat = [x for row in self.board for x in row]
            if self.is_solvable(flat):
                self.solvable_label.config(text="Solvable ✔", fg="green")
            else:
                self.solvable_label.config(text="Not Solvable ✘", fg="red")


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
            return f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'

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

    def is_solved_board(self, board = None):
        if board is None:
            board = self.board
        target = [[(i*self.width + j + 1) % (self.width*self.height) 
                   for j in range(self.width)] for i in range(self.height)]
        return board == target
    
    def lock_board(self):
        for row in self.buttons:
            for btn in row:
                btn.config(state=tk.DISABLED)
        self.undo_button.config(state=tk.DISABLED)
        self.redo_button.config(state=tk.DISABLED)
        # Re-enable control buttons and reset solve button
        for child in self.frame.winfo_children():
            for widget in child.winfo_children():
                if isinstance(widget, tk.Button) and widget.cget("text") in ("Generate", "Generate Solvable"):
                    widget.config(state=tk.NORMAL)


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Sliding Puzzle")
    root.geometry("800x900")
    puzzle = SlidingPuzzle(root)
    root.mainloop()
