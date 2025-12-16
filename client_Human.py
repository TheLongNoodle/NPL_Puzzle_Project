import tkinter as tk
from tkinter import ttk
import random
import logging
from copy import deepcopy
# Removed threading, heapq, and deque as they were unused in the original code's final implementation
# and are not required for the basic MVC separation of the Sliding Puzzle.

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# ==============================================================================
# I. MODEL: Manages the state and core logic of the puzzle.
# ==============================================================================
class SlidingPuzzleModel:
    """Manages the state (board) and core game logic (solvability, moves)."""

    def __init__(self, width=4, height=4):
        self.width = width
        self.height = height
        self.board = []
        self.move_count = 0
        self.memento_stack = []
        self.redo_stack = []

    def set_size(self, width, height):
        """Sets the new dimensions for the puzzle."""
        self.width = width
        self.height = height

    def generate_solvable_board(self):
        """Generates a random, solvable board for the current dimensions."""
        
        # 1. Generate numbers
        total_tiles = self.width * self.height
        nums = list(range(1, total_tiles)) + [0]

        # 2. Shuffle until solvable
        while True:
            random.shuffle(nums)
            if self._is_solvable(nums):
                break
        
        # 3. Create the 2D board
        self.board = [nums[i * self.width:(i + 1) * self.width] for i in range(self.height)]
        self.move_count = 0
        self.save_state()
        logging.info("Solvable puzzle generated (width=%d, height=%d)", self.width, self.height)
        
    def generate_random_board(self):
        """Generates a random board (may not be solvable)."""
        total_tiles = self.width * self.height
        nums = list(range(1, total_tiles)) + [0]
        random.shuffle(nums)
        
        self.board = [nums[i * self.width:(i + 1) * self.width] for i in range(self.height)]
        self.move_count = 0
        self.save_state()
        logging.info("Random puzzle generated (width=%d, height=%d)", self.width, self.height)

    def is_solved(self):
        """Checks if the current board is in the solved state."""
        target = [[(i * self.width + j + 1) % (self.width * self.height) 
                   for j in range(self.width)] for i in range(self.height)]
        return self.board == target

    def get_solvability_status(self):
        """Returns True if the current board state is mathematically solvable."""
        flat = [x for row in self.board for x in row]
        return self._is_solvable(flat)

    def _is_solvable(self, nums):
        """
        Determines solvability based on inversions and the blank tile's position.
        The algorithm applies to both odd and even width/height puzzles.
        """
        inv = 0
        nums_no_zero = [x for x in nums if x != 0]
        for i in range(len(nums_no_zero)):
            for j in range(i + 1, len(nums_no_zero)):
                if nums_no_zero[i] > nums_no_zero[j]:
                    inv += 1

        # Find the row of the blank tile (0) from the bottom
        zero_index = nums.index(0)
        empty_row_from_bottom = self.height - (zero_index // self.width)
        
        # Odd width: Solvable if inversions is even
        if self.width % 2 == 1:
            return inv % 2 == 0
        
        # Even width:
        # If empty row is even (from bottom), solvable if inversions is odd.
        # If empty row is odd (from bottom), solvable if inversions is even.
        if self.width % 2 == 0:
            return (empty_row_from_bottom % 2 == 0) != (inv % 2 == 0)
        
        return True # Should not be reached in a typical sliding puzzle

    def attempt_move(self, r, c):
        """
        Attempts to move the tile at (r, c) to the empty spot.
        Returns True if a move was successful, False otherwise.
        """
        # 1. Find the empty spot (0)
        empty_pos = next(((i, j) for i in range(self.height) for j in range(self.width) if self.board[i][j] == 0), None)
        if not empty_pos:
            logging.error("No empty spot (0) found on the board.")
            return False
            
        er, ec = empty_pos

        # 2. Check if the tile is adjacent to the empty spot
        if abs(er - r) + abs(ec - c) == 1:
            self.save_state()
            
            # 3. Swap the tile and the empty spot
            self.board[er][ec], self.board[r][c] = self.board[r][c], self.board[er][ec]
            self.move_count += 1
            logging.debug("Tile moved: (%d, %d) -> (%d, %d)", r, c, er, ec)
            return True, (er, ec, r, c) # Return True and the coordinates of the swap
        else:
            logging.debug("Illegal move attempted: (%d, %d)", r, c)
            return False, None
            
    # Memento Pattern Implementation (Undo/Redo)
    def save_state(self):
        """Saves the current board state to the undo stack (memento stack)."""
        self.memento_stack.append(deepcopy(self.board))
        self.redo_stack.clear() # A new move invalidates the redo stack
        logging.debug("State saved. Stack size: %d", len(self.memento_stack))

    def undo(self):
        """Restores the previous board state."""
        if self.memento_stack:
            self.redo_stack.append(deepcopy(self.board))
            self.board = self.memento_stack.pop()
            self.move_count = max(0, self.move_count - 1)
            logging.debug("Undo performed. Remaining states: %d", len(self.memento_stack))
            return True
        logging.debug("Undo attempted but undo stack is empty")
        return False

    def redo(self):
        """Restores the board state after an undo."""
        if self.redo_stack:
            self.memento_stack.append(deepcopy(self.board))
            self.board = self.redo_stack.pop()
            self.move_count += 1
            logging.debug("Redo performed. Remaining redo states: %d", len(self.redo_stack))
            return True
        logging.debug("Redo attempted but redo stack is empty")
        return False
        
    # Helper for generating color based on position in a special traversal
    def _get_traversal(self):
        """
        Generates a specific spiral-like traversal order used for tile coloring.
        The coloring is complex and specific to the original code's view logic,
        so it remains in the Model/Controller to serve the View.
        """
        width, height = self.width, self.height
        matrix = [[r * width + c + 1 for c in range(width)] for r in range(height)]
        result = []
        top, left = 0, 0
        bottom, right = height - 1, width - 1

        while (bottom - top) != (right - left):
            if (bottom - top) > (right - left):
                for c in range(left, right + 1):
                    result.append(matrix[top][c])
                top += 1
            else:
                for r in range(top, bottom + 1):
                    result.append(matrix[r][left])
                left += 1

        while top <= bottom and left <= right:
            for c in range(left, right + 1):
                result.append(matrix[top][c])
            top += 1

            if top > bottom: break
            for r in range(top, bottom + 1):
                result.append(matrix[r][left])
            left += 1

            if left > right: break
            for c in range(right, left - 1, -1):
                result.append(matrix[bottom][c])
            bottom -= 1

            if top > bottom: break
            for r in range(bottom, top - 1, -1):
                result.append(matrix[r][right])
            right -= 1
            
        return result
        

# ==============================================================================
# II. VIEW: Renders the GUI elements and displays the Model's state.
# ==============================================================================
class SlidingPuzzleView:
    """Renders the GUI, including the board and controls."""

    def __init__(self, parent, controller):
        self.controller = controller
        self.parent = parent
        self.buttons = []
        
        # Styling parameters (to be updated on board size change)
        self.button_width = 4
        self.button_height = 2
        self.font_size = 12

        self._setup_ui()
        
    def _setup_ui(self):
        """Initial setup of all tkinter widgets."""
        
        main_frame = tk.Frame(self.parent)
        main_frame.pack(pady=10)

        # --- Controls Frame (Top) ---
        control_frame = tk.Frame(main_frame)
        control_frame.pack()

        # Size Sliders
        tk.Label(control_frame, text="Size").grid(row=0, column=0, pady=5)
        # We only use one slider for simplicity (width/height are the same in the Model initialization)
        self.size_slider = tk.Scale(control_frame, from_=3, to=15, orient=tk.HORIZONTAL, length=300)
        self.size_slider.set(4) # Initial size is set here
        self.size_slider.grid(row=0, column=1, pady=5)
        
        # Generate Buttons
        btn_frame = tk.Frame(control_frame)
        btn_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)
        
        tk.Button(btn_frame, text="Generate Solvable", 
                  command=self.controller.handle_generate_solvable).pack(side=tk.LEFT, expand=True, fill='x', padx=2)
        tk.Button(btn_frame, text="Generate Random", 
                  command=self.controller.handle_generate_random).pack(side=tk.RIGHT, expand=True, fill='x', padx=2)

        ttk.Separator(control_frame, orient=tk.HORIZONTAL).grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)

        # --- Board Frame (Middle) ---
        self.board_frame = tk.Frame(main_frame)
        self.board_frame.pack()

        # --- Bottom Frame (Undo/Redo/Status) ---
        bottom_frame = tk.Frame(main_frame)
        bottom_frame.pack(pady=10)

        self.undo_button = tk.Button(bottom_frame, text="Undo", command=self.controller.handle_undo)
        self.undo_button.pack(side=tk.LEFT, padx=10)

        self.solvable_label = tk.Label(bottom_frame, text="Ready", font=("Arial", 12, "bold"))
        self.solvable_label.pack(side=tk.LEFT, padx=20)

        self.redo_button = tk.Button(bottom_frame, text="Redo", command=self.controller.handle_redo)
        self.redo_button.pack(side=tk.LEFT, padx=10)

        self.move_label = tk.Label(bottom_frame, text="Moves: 0", font=("Arial", 12))
        self.move_label.pack(side=tk.LEFT, padx=20)
        
    def _calculate_button_style(self, width, height):
        """Calculates button dimensions and font size based on board size."""
        self.button_width = min(8, max(3, 30 // width))
        self.button_height = min(4, max(2, 20 // height))
        self.font_size = max(8, 14 - (width + height - 8) // 2)

    def _get_tile_color(self, val, traversal_order, max_pos):
        """Generates an HSV-based color for a tile based on its solved position."""
        import colorsys
        if val == 0:
            return "#FFFFFF"  # White for the empty tile
        
        val_to_pos = {v: i for i, v in enumerate(traversal_order)}
        
        # Normalize the tile's position in the traversal to a value [0, 1]
        t = val_to_pos.get(val, 0) / max_pos if max_pos > 0 else 0
        
        # Map to a color (e.g., Hue from 0.0 to 0.75)
        h = 0.0 + 0.75 * t
        r, g, b = colorsys.hsv_to_rgb(h, 0.4, 0.95)
        
        return f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'

    def draw_board(self, board, width, height, is_solvable, is_solved, move_count, traversal_order):
        """
        Main rendering method. Redraws the entire board or updates existing buttons.
        """
        
        # 1. Recalculate and update size/font
        self._calculate_button_style(width, height)
        
        max_pos = len(traversal_order) - 1
        
        # 2. Check if the grid needs rebuilding (size changed)
        if (not self.buttons or len(self.buttons) != height or len(self.buttons[0]) != width):
            for w in self.board_frame.winfo_children():
                w.destroy()
            self.buttons.clear()

            for r in range(height):
                row_buttons = []
                for c in range(width):
                    val = board[r][c]
                    text = "" if val == 0 else str(val)
                    color = self._get_tile_color(val, traversal_order, max_pos)
                    
                    # Bind the command to the Controller's handler
                    cmd = lambda rr=r, cc=c: self.controller.handle_tile_click(rr, cc)

                    btn = tk.Button(
                        self.board_frame, text=text, 
                        width=self.button_width, height=self.button_height, 
                        font=("Arial", self.font_size, "bold"), 
                        command=cmd, bg=color, activebackground=color
                    )
                    btn.grid(row=r, column=c)
                    row_buttons.append(btn)
                self.buttons.append(row_buttons)

        # 3. Update existing buttons and status labels
        self.update_board_state(board, traversal_order, max_pos)
        self.update_status(is_solvable, is_solved, move_count)

    def update_board_state(self, board, traversal_order, max_pos):
        """Updates the text and color of all existing buttons."""
        for r in range(len(board)):
            for c in range(len(board[r])):
                val = board[r][c]
                text = "" if val == 0 else str(val)
                color = self._get_tile_color(val, traversal_order, max_pos)
                
                # Check if button exists before trying to configure it
                if self.buttons and len(self.buttons) > r and len(self.buttons[r]) > c:
                    self.buttons[r][c].config(text=text, bg=color, activebackground=color)

    def update_status(self, is_solvable, is_solved, move_count):
        """Updates the status and move counter labels."""
        self.move_label.config(text=f"Moves: {move_count}")
        
        if is_solved:
            self.solvable_label.config(text="Solved ✔", fg="blue")
            self.lock_board()
        else:
            if is_solvable:
                self.solvable_label.config(text="Solvable ✔", fg="green")
            else:
                self.solvable_label.config(text="Not Solvable ✘", fg="red")
            self.unlock_board()
            
    def lock_board(self):
        """Disables all puzzle interaction buttons."""
        for row in self.buttons:
            for btn in row:
                btn.config(state=tk.DISABLED)
        self.undo_button.config(state=tk.DISABLED)
        self.redo_button.config(state=tk.DISABLED)

    def unlock_board(self):
        """Enables all puzzle interaction buttons."""
        for row in self.buttons:
            for btn in row:
                btn.config(state=tk.NORMAL)
        self.undo_button.config(state=tk.NORMAL)
        self.redo_button.config(state=tk.NORMAL)
        
    def get_requested_size(self):
        """Retrieves the size from the slider."""
        return self.size_slider.get()


# ==============================================================================
# III. CONTROLLER: Handles user input, manipulates the Model, and updates the View.
# ==============================================================================
class SlidingPuzzleController:
    """Handles user interaction, communicates with Model and View."""

    def __init__(self, parent):
        # 1. Create Model and View instances
        initial_size = 4
        self.model = SlidingPuzzleModel(width=initial_size, height=initial_size)
        self.view = SlidingPuzzleView(parent, self)
        
        # 2. Initial board setup
        self.handle_generate_solvable()

    def _sync_view(self):
        """A utility to pull all necessary data from the Model and update the View."""
        traversal = self.model._get_traversal() # Getting color info from Model
        
        self.view.draw_board(
            board=self.model.board,
            width=self.model.width,
            height=self.model.height,
            is_solvable=self.model.get_solvability_status(),
            is_solved=self.model.is_solved(),
            move_count=self.model.move_count,
            traversal_order=traversal
        )

    # --- Controller Handlers for View Events ---

    def handle_generate_solvable(self):
        """Handles the 'Generate Solvable' button click."""
        size = self.view.get_requested_size()
        self.model.set_size(size, size)
        self.model.generate_solvable_board()
        self._sync_view()

    def handle_generate_random(self):
        """Handles the 'Generate Random' button click."""
        size = self.view.get_requested_size()
        self.model.set_size(size, size)
        self.model.generate_random_board()
        self._sync_view()

    def handle_tile_click(self, r, c):
        """Handles a click on a puzzle tile."""
        success, _ = self.model.attempt_move(r, c)
        if success:
            # We only need to redraw if the model state changed
            self._sync_view() 
    
    def handle_undo(self):
        """Handles the 'Undo' button click."""
        if self.model.undo():
            self._sync_view()

    def handle_redo(self):
        """Handles the 'Redo' button click."""
        if self.model.redo():
            self._sync_view()


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Sliding Puzzle (MVC)")
    root.geometry("800x900")
    
    # Instantiate the Controller, which sets up the Model and View
    controller = SlidingPuzzleController(root)
    
    root.mainloop()