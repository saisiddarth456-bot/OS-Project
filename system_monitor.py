"""
system_monitor.py

Collects real system and process information using psutil.

This module is the single source of truth for raw operating-system data.
The GUI never talks to psutil directly; it requests data from this layer.
"""

import os
import platform
import time

import psutil

CPU_SMOOTHING = 0.6  # weight given to a new CPU sample when smoothing


class SystemMonitor:
    """Thin, defensive wrapper around psutil."""

    def __init__(self):
        # Cache of per-PID smoothed CPU values. psutil's process CPU
        # percentage is 0 on the first sample per process, so smoothing
        # gives stable, meaningful numbers after a few refreshes.
        self._process_cpu = {}

    # ------------------------------------------------------------------
    # CPU
    # ------------------------------------------------------------------

    @staticmethod
    def cpu_percent():
        try:
            return float(psutil.cpu_percent(interval=None) or 0.0)
        except Exception:
            return 0.0

    @staticmethod
    def cpu_count():
        try:
            return psutil.cpu_count(logical=True) or 1
        except Exception:
            return 1

    @staticmethod
    def cpu_frequency():
        try:
            freq = psutil.cpu_freq()
            if freq:
                return freq.current
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # RAM
    # ------------------------------------------------------------------

    @staticmethod
    def ram_info():
        try:
            memory = psutil.virtual_memory()
            return {
                "percent": float(memory.percent or 0.0),
                "used": memory.used,
                "total": memory.total,
            }
        except Exception:
            return {"percent": 0.0, "used": 0, "total": 0}

    # ------------------------------------------------------------------
    # DISK
    # ------------------------------------------------------------------

    @staticmethod
    def disk_info():
        try:
            disk = psutil.disk_usage("/")
            return {
                "percent": float(disk.percent or 0.0),
                "used": disk.used,
                "total": disk.total,
            }
        except Exception:
            return {"percent": 0.0, "used": 0, "total": 0}

    # ------------------------------------------------------------------
    # BATTERY
    # ------------------------------------------------------------------

    @staticmethod
    def battery_info():
        """Returns a dict or None if the machine has no battery."""
        try:
            battery = psutil.sensors_battery()
        except (AttributeError, NotImplementedError):
            return None
        if battery is None:
            return None
        plugged = battery.power_plugged
        if plugged is None:
            plugged = False
        
        secsleft = battery.secsleft
        # psutil uses negative values (-1, -2) for POWER_TIME_UNKNOWN / POWER_TIME_UNLIMITED
        if secsleft is not None and secsleft < 0:
            secsleft = None

        return {
            "percent": float(battery.percent or 0.0),
            "plugged": bool(plugged),
            "seconds_left": secsleft,
        }

    # ------------------------------------------------------------------
    # PROCESSES
    # ------------------------------------------------------------------

    def processes(self):
        """Return all running processes with smoothed CPU percentages.

        Disappearing / inaccessible processes are skipped safely.
        """
        found = {}

        try:
            iterator = psutil.process_iter(
                ["pid", "name", "cpu_percent", "memory_percent", "status"]
            )
            for process in iterator:
                try:
                    info = process.info
                    pid = info.get("pid")
                    if pid is None:
                        continue
                    name = info.get("name") or f"PID {pid}"
                    cpu = float(info.get("cpu_percent") or 0.0)
                    memory = float(info.get("memory_percent") or 0.0)
                    status = info.get("status") or "unknown"

                    previous = self._process_cpu.get(pid)
                    if previous is None:
                        cpu = 0.0
                    else:
                        cpu = CPU_SMOOTHING * cpu + (1 - CPU_SMOOTHING) * previous
                    self._process_cpu[pid] = cpu

                    found[str(pid)] = {
                        "pid": pid,
                        "name": name,
                        "cpu": cpu,
                        "memory": memory,
                        "status": status,
                    }
                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):
                    continue
                except Exception:
                    continue
        except (psutil.Error, Exception):
            pass

        # Prune cache entries for processes that no longer exist
        live = set(found)
        for key in [k for k in self._process_cpu if k not in live]:
            self._process_cpu.pop(key, None)

        return list(found.values())

    @staticmethod
    def process_count():
        try:
            return len(psutil.pids())
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # SYSTEM METADATA
    # ------------------------------------------------------------------

    @staticmethod
    def uptime():
        try:
            return max(0.0, time.time() - psutil.boot_time())
        except Exception:
            return 0.0

    @staticmethod
    def platform_name():
        try:
            return f"{platform.system()} {platform.release()}"
        except Exception:
            return platform.system() or "Unknown"

    @staticmethod
    def machine():
        return platform.machine() or ""

    # ------------------------------------------------------------------
    # CONVENIENCE
    # ------------------------------------------------------------------

    def snapshot(self):
        """Collect everything the UI needs in one inexpensive pass."""
        now = time.time()
        if not hasattr(self, "_last_proc_time") or (now - self._last_proc_time) >= 1.5:
            self._last_processes = self.processes()
            self._last_proc_time = now
            self._last_proc_count = self.process_count()

        processes = getattr(self, "_last_processes", [])
        proc_count = getattr(self, "_last_proc_count", 0)

        cpu = self.cpu_percent()
        ram = self.ram_info()
        disk = self.disk_info()
        battery = self.battery_info()

        return {
            "cpu": cpu,
            "cpu_freq": self.cpu_frequency(),
            "cpu_cores": self.cpu_count(),
            "ram": ram,
            "disk": disk,
            "battery": battery,
            "processes": processes,
            "process_count": proc_count,
            "uptime": self.uptime(),
            "platform": self.platform_name(),
            "machine": self.machine(),
        }


# ======================================================================
# HELPERS (pure formatting functions)
# ======================================================================


def usage_status(percent, kind):
    """Return a friendly label for a resource usage percentage."""
    if kind == "cpu":
        if percent >= 90:
            return "Critical"
        if percent >= 70:
            return "High"
        if percent >= 40:
            return "Moderate"
        return "Normal"
    if kind == "ram":
        if percent >= 90:
            return "Critical"
        if percent >= 75:
            return "High"
        if percent >= 60:
            return "Moderate"
        return "Normal"
    if kind == "disk":
        if percent >= 85:
            return "High"
        if percent >= 70:
            return "Moderate"
        return "Healthy"
    if kind == "battery":
        if percent <= 20:
            return "Critical"
        if percent <= 50:
            return "Low"
        if percent <= 80:
            return "Moderate"
        return "Good"
    return "Normal"


def format_bytes(size):
    """Format a byte count into a human readable string."""
    size = float(size or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def format_duration(seconds):
    """Format seconds as [[N d] HH:MM:SS or MM:SS]."""
    seconds = int(seconds or 0)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days:
        return f"{days}d {hours:02d}h {minutes:02d}m"
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


# ======================================================================
# FRIENDLY APPLICATION NAMES
#
# Process names from the operating system are technical. Map common
# names to names people actually recognise.
# ======================================================================

_FRIENDLY_NAME_RULES = [
    ("Google Chrome", "Google Chrome"),
    ("Chrome", "Google Chrome"),
    ("Code Helper", "VS Code"),
    ("Code", "VS Code"),
    ("Cursor", "Cursor Editor"),
    ("Electron", "Desktop App"),
    ("Microsoft Teams", "Microsoft Teams"),
    ("Teams", "Microsoft Teams"),
    ("Microsoft Word", "Microsoft Word"),
    ("Word", "Microsoft Word"),
    ("Microsoft Excel", "Microsoft Excel"),
    ("Excel", "Microsoft Excel"),
    ("Microsoft PowerPoint", "PowerPoint"),
    ("Microsoft Outlook", "Outlook"),
    ("Safari", "Safari"),
    ("Firefox", "Firefox"),
    ("Brave", "Brave Browser"),
    ("Arc", "Arc Browser"),
    ("Opera", "Opera"),
    ("Spotify Helper", "Spotify"),
    ("Spotify", "Spotify"),
    ("Slack", "Slack"),
    ("Discord", "Discord"),
    ("Zoom", "Zoom Meeting"),
    ("iTerm2", "iTerm"),
    ("Terminal", "Terminal"),
    ("Finder", "Finder"),
    ("WindowServer", "Display System"),
    ("kernel_task", "macOS Kernel"),
    ("launchd", "System Services"),
    ("loginwindow", "Login Manager"),
    ("plugin_host", "System Plugin"),
    ("coreaudiod", "Audio Engine"),
    ("nsurlsessiond", "Network Transfer"),
    ("distnoted", "System Notification"),
    ("cfprefsd", "System Preferences"),
    ("notifyd", "Notification Service"),
    ("trustd", "Security Verification"),
    ("SkyLight", "Window Compositor"),
    ("ControlCenter", "Control Center"),
    ("Docker", "Docker Desktop"),
    ("Notion", "Notion"),
    ("Obsidian", "Obsidian"),
    ("Python", "Python Environment"),
    ("tailspind", "System Telemetry"),
    ("symptomsd", "System Diagnostics"),
    ("assetd", "Media Services"),
]


def friendly_name(name):
    """Convert a technical process name into an easy-to-read label."""
    name = str(name or "").strip()
    if not name:
        return "Unknown application"

    lowered = name.lower()
    for technical, display in _FRIENDLY_NAME_RULES:
        rule = technical.lower()
        if lowered == rule or lowered.startswith(rule):
            return display

    cleaned = name
    for suffix in (" (Renderer)", " (GPU)", " Helper", ".app", ".bin"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
    cleaned = cleaned.replace("_", " ").strip()
    if not cleaned:
        return name[:24]
    return cleaned[:24].title()


def app_icon(name):
    """Return an appropriate emoji icon for a process or application name."""
    name_str = str(name or "").lower()
    if any(k in name_str for k in ("chrome", "safari", "firefox", "brave", "arc", "opera", "edge", "browser")):
        return "🌐"
    if any(k in name_str for k in ("code", "cursor", "xcode", "pycharm", "sublime", "iterm", "terminal", "python", "node", "git", "docker")):
        return "💻"
    if any(k in name_str for k in ("slack", "teams", "discord", "zoom", "whatsapp", "telegram", "messages", "skype", "mail", "outlook")):
        return "💬"
    if any(k in name_str for k in ("spotify", "music", "audio", "sound", "vlc", "media", "coreaudiod", "podcast")):
        return "🎵"
    if any(k in name_str for k in ("word", "excel", "powerpoint", "notion", "obsidian", "pages", "numbers", "notes", "acrobat", "preview")):
        return "📝"
    if any(k in name_str for k in ("finder", "cloud", "dropbox", "drive", "onedrive", "box")):
        return "📁"
    if any(k in name_str for k in ("kernel", "windowserver", "launchd", "system", "login", "trustd", "skylight", "security")):
        return "⚙️"
    return "📱"
