import tkinter as tk
from tkinter import scrolledtext
import logging
import threading
from client_Human import SlidingPuzzle
from client_Computer import SlidingPuzzle

_human_window_instance = None
_computer_window_instance = None

# Redirect logging output to a Tkinter Text widget.
class TextHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        self.text_widget.after(0, lambda: self.text_widget.insert(tk.END, msg + "\n"))
        self.text_widget.see(tk.END)

# Main window
class MainWindow:
    def __init__(self, root):
        self.root = root
        root.title("Main Menu")

        # ------- Buttons -------
        frame = tk.Frame(root)
        frame.pack(pady=10)

        tk.Button(frame, text="Human Client", width=20,
                  command=self.open_human).pack(pady=3)
        tk.Button(frame, text="Computer Client", width=20,
                  command=self.open_computer).pack(pady=3)
        tk.Button(frame, text="Show Statistics", width=20,
                  command=self.open_stats).pack(pady=3)
        
        toggle_frame = tk.Frame(root)
        toggle_frame.pack(pady=5)
        self.debug_mode = tk.BooleanVar(value=False)
        tk.Checkbutton(toggle_frame, text="Debug Mode",
                       variable=self.debug_mode,
                       command=self.toggle_logging).pack()

        # ------- Logging -------
        self.log_box = scrolledtext.ScrolledText(root, width=70, height=18)
        self.log_box.pack(padx=10, pady=10)
        self.setup_logging()

    def setup_logging(self):
        handler = TextHandler(self.log_box)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
        logging.info("Main menu initialized.")

    def toggle_logging(self):
        if self.debug_mode.get():
            logging.getLogger().setLevel(logging.DEBUG)
            logging.info("Switched to DEBUG mode.")
        else:
            logging.getLogger().setLevel(logging.INFO)
            logging.info("Switched to INFO mode.")

    def open_human(self):
        global _human_window_instance
        if _human_window_instance is not None and tk.Toplevel.winfo_exists(_human_window_instance):
            logging.error("Human client window already open.")
            _human_window_instance.lift()
            return

        logging.info("Human Client opened succesfully!")

        win = tk.Toplevel()
        win.title("Human Client")
        _human_window_instance = win

        SlidingPuzzle(win, human_mode=True)

    def open_computer(self):
        global _computer_window_instance
        if _computer_window_instance is not None and tk.Toplevel.winfo_exists(_computer_window_instance):
            logging.error("Computer client window already open.")
            _computer_window_instance.lift()
            return

        logging.info("Computer Client opened succesfully!")

        win = tk.Toplevel()
        win.title("Computer Client")
        _computer_window_instance = win

        SlidingPuzzle(win, human_mode=False)

if __name__ == "__main__":
    root = tk.Tk()
    MainWindow(root)
    root.mainloop()
