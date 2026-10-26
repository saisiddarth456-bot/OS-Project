"""
database.py

Handles all SQLite storage and retrieval for the application:

    - periodic system measurements (timestamp, cpu, ram, battery, disk)
    - persistent application settings
"""

import sqlite3
import time


class Database:
    """SQLite storage backend for measurements and settings."""

    def __init__(self, path):
        self._conn = sqlite3.connect(path)
        self._init_tables()

    def _init_tables(self):
        cursor = self._conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS system_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                cpu REAL,
                ram REAL,
                battery REAL,
                disk REAL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # MEASUREMENT HISTORY
    # ------------------------------------------------------------------

    def record(self, cpu, ram, battery, disk):
        """Insert one measurement snapshot. battery may be None."""
        cursor = self._conn.cursor()
        cursor.execute(
            "INSERT INTO system_history (timestamp, cpu, ram, battery, disk) "
            "VALUES (?, ?, ?, ?, ?)",
            (time.time(), cpu, ram, battery, disk),
        )
        self._conn.commit()

    def recent(self, limit=200):
        """Return the most recent N measurements, oldest first."""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT timestamp, cpu, ram, battery, disk "
            "FROM system_history ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        rows.reverse()
        return [
            {
                "timestamp": row[0],
                "cpu": row[1],
                "ram": row[2],
                "battery": row[3],
                "disk": row[4],
            }
            for row in rows
        ]

    def count(self):
        cursor = self._conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM system_history")
        return cursor.fetchone()[0]

    def range_since(self, seconds, limit=2000):
        """Return measurements recorded within the last `seconds` seconds.

        Oldest measurement first, most recent last.
        """
        cutoff = time.time() - seconds
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT timestamp, cpu, ram, battery, disk "
            "FROM system_history WHERE timestamp >= ? ORDER BY id ASC LIMIT ?",
            (cutoff, limit),
        )
        rows = cursor.fetchall()
        return [
            {
                "timestamp": row[0],
                "cpu": row[1],
                "ram": row[2],
                "battery": row[3],
                "disk": row[4],
            }
            for row in rows
        ]

    def get_history(self, timeframe="30m"):
        """Fetch history based on timeframe string ('15m', '30m', '1h', 'today', 'all').
        Oldest measurement first, most recent last.
        """
        mapping = {
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "today": 86400,
            "week": 604800,
        }
        if timeframe in mapping:
            rows = self.range_since(mapping[timeframe])
            if len(rows) >= 2:
                return rows
            # If fewer than 2 in selected window, fall back to recent samples
            return self.recent(200)
        return self.recent(400)

    def clear(self):
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM system_history")
        self._conn.commit()

    # ------------------------------------------------------------------
    # SETTINGS
    # ------------------------------------------------------------------

    def get_setting(self, key, default=None):
        cursor = self._conn.cursor()
        cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        cursor = self._conn.cursor()
        cursor.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # CLEANUP
    # ------------------------------------------------------------------

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass