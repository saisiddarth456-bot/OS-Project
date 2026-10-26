# Smart Laptop Optimizer ⚡

A modern, accessible, consumer-friendly **Laptop Health & Control Center** desktop application built with Python and CustomTkinter.

Designed for everyday users: monitors your laptop's real-time operating system metrics, explains everything in simple human language, and provides safe, actionable optimization advice.

---

## 🌟 Key Features

- **🏠 Home Health Dashboard**:
  - **Overall System Status**: Instant high-level health card (**🟢 Good**, **🟡 Needs Attention**, **🔴 High Load**).
  - **4 Resource Cards**: Real-time stats for **Processor (CPU)**, **Memory (RAM)**, **Battery**, and **Storage** with human-friendly explanations and hover tooltips.
  - **🧠 Smart Insight**: Structured *What's happening?*, *Why?*, and *What can you do?* recommendations based on real OS telemetry.
  - **Top Applications**: Displays resource-heavy apps with recognizable icons and status badges.

- **📊 Detailed System Monitor**:
  - Comprehensive hardware breakdown (cores, clock speed, used/total RAM, disk capacity, battery state).
  - Live active process count, system uptime, and machine architecture.
  - Side-by-side lists for highest CPU and highest memory consumers.

- **🚀 Optimize Page**:
  - Non-destructive recommendations to improve speed and responsiveness.
  - **Operating System Task Prioritization**: Visual analysis of FCFS, Shortest Job First (SJF), and Priority scheduling algorithms.
  - **Safe Background Priority Tuning**: Lower process scheduling priority (`nice` value) without terminating or losing work.
  - Everyday laptop health tips.

- **🧠 Insights Page**:
  - Data-driven analysis of historical trends (CPU spikes, memory headroom, battery discharge speed).

- **📜 History Page**:
  - Continuous telemetry graph tracking CPU, RAM, battery, and disk over time.
  - Timeframe selector (**Last 15 min**, **Last 30 min**, **Last 1 hour**, **All recorded**).

- **⚙️ Settings Page**:
  - Customizable refresh rate (1s, 2s, 3s, 5s).
  - Appearance mode toggle (Dark / Light theme).
  - Background monitoring controls.
  - Local SQLite history management.

---

## 🛠️ Architecture

- `main.py` — Application entry point.
- `gui.py` — Responsive CustomTkinter UI with accessibility badges, tooltips, and navigation history.
- `system_monitor.py` — Single source of truth for raw OS telemetry via `psutil`.
- `recommendation.py` — Plain-language reasoning engine translating metrics into human advice.
- `scheduler.py` — Operating Systems scheduling simulations (FCFS, SJF, Priority) and priority adjustments.
- `database.py` — Local SQLite storage for historical measurements and app settings.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- macOS, Windows, or Linux

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/dhruvsnair777-dot/smart-laptop-optimizer.git
   cd smart-laptop-optimizer
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Launch the application:
   ```bash
   python main.py
   ```

---

## 🔒 Privacy & Safety Guarantee

All performance measurements are analyzed locally and stored on your device. No analytics, telemetry, or personal data is transmitted externally.
