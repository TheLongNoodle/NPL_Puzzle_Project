# N-Puzzle Game System 🧩

**Course:** Programming Languages Seminar  
**Instructor:** Dr. Itzik Aviv  
**Language:** Python 3.10+  
**Architecture:** Client-Server (MVC)

---

## 👥 Authors
* **Gavriel levit** (207612407)
* **Omer Aley-Raz** (326635406)

---

## 📖 Overview

This project is a comprehensive software implementation of the classic **Sliding Puzzle (N-Puzzle)** game. It is designed as a **Client-Server system** where the user interacts with a central Server GUI to launch game instances.

The system supports board sizes ranging from **3x3 to 7x7** and features two distinct game modes:
1.  **Human Mode:** A user plays manually with features like Undo/Redo.
2.  **Computer Mode:** An AI algorithm solves the puzzle automatically within a strict time limit (max 2 minutes).

The project emphasizes the use of advanced software engineering concepts, including **Design Patterns**, **Multi-threading**, and **Algorithmic Efficiency**.

---

## 🏗️ Architecture & Design Patterns

The system is built using the **Model-View-Controller (MVC)** architectural pattern to ensure separation of concerns.

### Design Patterns Implemented
* **MVC (Model-View-Controller):** Separates the game logic (Model), the GUI (View), and the user input handling (Controller).
* **Singleton:** Ensures that specific windows (like the game board) are unique instances. For example, a client cannot open multiple game boards simultaneously.
* **Memento:** Used in the "Human Mode" to implement **Undo** and **Redo** functionality, allowing the state of the board to be saved and restored.

### System Structure
* **Server:** The main entry point. It manages a GUI log, launches clients via threads, and aggregates statistics.
* **Client:** Operates as a child process/thread initiated by the Server. It handles the specific game logic for either a human or the computer.

---

## ✨ Features

### 1. The Server
* **Central Hub:** The user only executes the Server script.
* **Dashboard:** Contains buttons to launch a "Human Game", "Computer Game", or view "Statistics".
* **Logging:** A live GUI log tracking system events.

### 2. Human Game Client
* **Dynamic Board Sizes:** Supports 3x3, 4x4, 5x5, 6x6, and 7x7 (And more, even rectangles!).
* **Solvability Check:** Automatically detects if a shuffled board is unsolvable and notifies the user immediately.
* **Controls:** Click to move tiles.
* **Undo/Redo:** Traverse back and forth through your move history (implemented via Memento).
* **Session Report:** Upon completion (or closing), a report displays stats (Time, Moves, Solvability status).

### 3. Computer Game Client (AI Solver)
* **Automated Solving:** The computer attempts to solve the puzzle autonomously.
* **Time Constraint:** The algorithm is optimized to solve any solvable board (up to 7x7) in **under 2 minutes**.
* **Fail-Safe:** If the puzzle cannot be solved within the time limit or is mathematically unsolvable, the system alerts the user gracefully without crashing.
* *Note: Undo/Redo is disabled in this mode.*

### 4. Statistics
* A dedicated dashboard showing:
    * Total games played per board size.
    * Average moves to solution.
    * Average time to solution.
    * Separation between Human and Computer performance.

---

## 🧠 Algorithms

### Solvability Detection
Not all random arrangements of the N-Puzzle are solvable. The system implements an **Inversion Count Algorithm** (taking into account the row number of the empty tile for even-sized grids) to mathematically determine if a solution exists before the game begins.

### AI Solver
To meet the 2-minute deadline for complex boards (like 6x6 or 7x7), the Computer Client utilizes the **human algorithm** to find a possible path to the sorted state.
Since huristic and greedy algorithms (such as A*) take a long time for even a 4x4 pyzzle, we decided to sacrifice optimality for speed, the human algorithm solves the board using a very simple list of steps, and reduces a gient board to a 3x3, and then solves the last 3x3 using A*.
detail for the algorithm are in the credtis below.

---

## ⚙️ Prerequisites & Installation

### Requirements
* **OS:** Windows (Preferred for GUI compatibility).
* **Python:** Version 3.10 or higher.
* **IDE:** PyCharm (Recommended).

### Libraries
Standard Python libraries are used.

---

## 🚀 How to Run

1.  **Clone/Download** the repository.
2.  Open the project in **PyCharm**.
3.  Locate the `server.py` file.
4.  **Run `server.py`**.
    * *Note: Do not run client files directly. The Server manages the creation of client threads.*

### User Guide
1.  **Server Window:** Once the server is running, you will see three buttons:
    * `New Human Player`
    * `New Computer Player`
    * `Show Statistics`
2.  **Select a Game:** Click a button to open a client window.
3.  **Choose Size:** Inside the client, select the desired board dimension (e.g., 4x4).
4.  **Play:**
    * **Human:** Click tiles adjacent to the empty space to move them. Use "Undo" if you make a mistake.
    * **Computer:** Watch the algorithm solve the board in real-time.

---

## 📝 Credits

* **[jweilhammer](https://github.com/jweilhammer/sliding-puzzle-solver)**: for introducing us to the strategic human algorithm (they used JS and made a [test website](https://jweilhammer.github.io/sliding-puzzle-solver/) to show the algorithm).
* **[WikiHow](https://www.wikihow.com/Solve-Slide-Puzzles)**: for teaching us the simple steps for solving an N-puzzle of any size.

---

*This project was developed as part of the academic requirements for the Computer Science Seminar at Afeka College of Engineering.*