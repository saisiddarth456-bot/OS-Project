"""
recommendation.py

Turns real system measurements into plain, friendly language that a
non-technical person can understand immediately.

Everything here is derived from actual data. No made-up numbers, and
nothing claims to have optimized a process it did not.
"""

import system_monitor as sm

# ----------------------------------------------------------------------
# Friendly status vocabulary
# ----------------------------------------------------------------------

LEVEL_META = {
    "good": {"color": "healthy", "word": "GOOD"},
    "attention": {"color": "warning", "word": "ATTENTION"},
    "high": {"color": "critical", "word": "HIGH"},
    "neutral": {"color": "muted", "word": "CHECKING"},
}

THRESHOLDS = {
    "cpu": {"attention": 70, "high": 90},
    "ram": {"attention": 70, "high": 85},
    "disk": {"attention": 75, "high": 90},
    "battery": {"attention": 50, "high": 25},  # lower is worse for battery
}

WORDS = {
    "cpu": {"good": "Normal", "attention": "Moderate", "high": "High"},
    "ram": {"good": "Normal", "attention": "Elevated", "high": "High"},
    "disk": {"good": "Healthy", "attention": "Moderate", "high": "Full"},
    "battery": {"good": "Good", "attention": "Low", "high": "Very low"},
}

EXPLANATIONS = {
    "cpu": {
        "good": "Your processor is handling the current workload comfortably.",
        "attention": "Your processor is working noticeably harder than usual.",
        "high": "Your processor is very busy. Consider closing heavy applications.",
    },
    "ram": {
        "good": "There is plenty of memory available for your applications.",
        "attention": "Several applications are using a large amount of memory.",
        "high": "Your laptop is using most of its available memory. Closing some applications would help.",
    },
    "battery": {
        "good": "Your battery is in good shape.",
        "attention": "Your battery is getting low. Consider connecting your charger.",
        "high": "Your battery is very low. Please connect your charger soon.",
    },
    "disk": {
        "good": "Your storage has sufficient free space.",
        "attention": "Your storage is getting fairly full. Freeing space would help.",
        "high": "Your storage is almost full. Consider removing large files.",
    },
}


class RecommendationEngine:
    """Friendly analysis of real system data."""

    # ------------------------------------------------------------------
    # SINGLE RESOURCE STATUS
    # ------------------------------------------------------------------

    @staticmethod
    def resource_state(kind, percent, plugged=None):
        """Describe one resource with (level, word, explanation)."""
        if percent is None:
            if kind == "battery":
                return {
                    "level": "neutral",
                    "word": "Unavailable",
                    "message": "This device does not provide battery information (e.g. desktop Mac or direct power).",
                }
            return {
                "level": "neutral",
                "word": "Unavailable",
                "message": "No information is currently available for this resource.",
            }

        thresholds = THRESHOLDS[kind]
        if kind == "battery":
            if percent <= thresholds["high"]:
                level = "high"
            elif percent <= thresholds["attention"]:
                level = "attention"
            else:
                level = "good"
        else:
            if percent >= thresholds["high"]:
                level = "high"
            elif percent >= thresholds["attention"]:
                level = "attention"
            else:
                level = "good"

        message = EXPLANATIONS[kind][level]
        if kind == "battery" and plugged:
            message = (
                "Your battery is charging."
                if level == "good"
                else "Your battery is charging, but it is still low."
            )

        return {
            "level": level,
            "word": WORDS[kind][level],
            "message": message,
        }

    # ------------------------------------------------------------------
    # OVERALL SYSTEM STATUS
    # ------------------------------------------------------------------

    @staticmethod
    def overall_status(cpu, ram):
        """Return (level, title, message) for the whole system."""
        if cpu >= 90 or ram >= 85:
            return (
                "high",
                "High Load",
                "Your laptop is working very hard right now. Closing heavy "
                "applications would help it run smoothly.",
            )
        if cpu >= 70 or ram >= 70:
            return (
                "attention",
                "Needs Attention",
                "Your laptop is under a fair amount of strain. Consider "
                "closing applications you are not using.",
            )
        return (
            "good",
            "Good",
            "Your laptop is currently running normally.",
        )

    # ------------------------------------------------------------------
    # SMART INSIGHT (WHAT / WHY / ACTION)
    # ------------------------------------------------------------------

    @staticmethod
    def smart_insight(cpu, ram, battery, processes):
        highest = max(processes, key=lambda p: p["cpu"]) if processes else None
        name = sm.friendly_name(highest["name"]) if highest else "an application"
        top_cpu = round(highest["cpu"]) if highest else 0

        if cpu >= 90:
            return {
                "level": "high",
                "happening": "Your laptop is working very hard right now.",
                "why": (
                    f"{name} is using the most processor power ({top_cpu}% of CPU)."
                ),
                "action": "Close unused tabs or applications to give your laptop a break.",
            }
        if ram >= 85:
            return {
                "level": "high",
                "happening": "Your laptop is running low on available memory.",
                "why": f"Your applications together are using {round(ram)}% of memory.",
                "action": "Close applications you are not actively using.",
            }
        if battery is not None and battery["percent"] <= 30 and not battery["plugged"]:
            return {
                "level": "attention",
                "happening": "Your battery is running low.",
                "why": f"Only {round(battery['percent'])}% battery remains.",
                "action": "Connect your charger or enable power-saving mode.",
            }
        if highest is not None and highest["cpu"] >= 40:
            return {
                "level": "attention",
                "happening": "One application is using a lot of processor power.",
                "why": f"{name} is using {top_cpu}% of your CPU right now.",
                "action": (
                    f"Close tabs or windows in {name}, or quit it if you are done."
                ),
            }
        if cpu >= 70 or ram >= 70:
            return {
                "level": "attention",
                "happening": "Your laptop is working harder than usual.",
                "why": f"CPU is at {round(cpu)}% and memory is at {round(ram)}%.",
                "action": "Close a few applications and see if things settle down.",
            }
        return {
            "level": "good",
            "happening": "Your laptop is running smoothly.",
            "why": "Everything is comfortably below normal limits.",
            "action": "Keep doing what you are doing — just close apps you are not using now and then.",
        }

    @staticmethod
    def analyze(cpu, ram, battery, processes):
        """Kept for compatibility: returns the smart insight as a list."""
        return [RecommendationEngine.smart_insight(cpu, ram, battery, processes)]

    # ------------------------------------------------------------------
    # OPTIMIZE PAGE: ACTION CARDS + GOOD HABITS
    # ------------------------------------------------------------------

    @staticmethod
    def suggestions(cpu, ram, battery, processes):
        """Return (cards, tips) for the Optimize page."""
        highest = max(processes, key=lambda p: p["cpu"]) if processes else None
        peak_name = sm.friendly_name(highest["name"]) if highest else "an application"

        cards = []

        if cpu >= 70 or ram >= 70:
            if highest is not None and highest["cpu"] >= 30:
                why = f"{peak_name} is currently using the most processor power."
            elif ram >= 70:
                why = "Several applications are using a large amount of memory right now."
            else:
                why = "Your laptop is under a heavier workload than usual."
            cards.append(
                {
                    "level": "attention",
                    "icon": "🚀",
                    "title": "Improve Performance",
                    "what": "Close applications you are not using.",
                    "why": why,
                    "action": "View Applications",
                    "goto": "monitor",
                }
            )

        if battery is not None and battery["percent"] <= 50 and not battery["plugged"]:
            cards.append(
                {
                    "level": "attention",
                    "icon": "🔋",
                    "title": "Save Battery",
                    "what": "Reduce background activity.",
                    "why": f"Your battery is at {round(battery['percent'])}%.",
                    "action": "View Insights",
                    "goto": "insights",
                }
            )

        if not cards:
            cards.append(
                {
                    "level": "good",
                    "icon": "🌿",
                    "title": "Running Smoothly",
                    "what": "Your laptop looks healthy right now.",
                    "why": "All resource usage is within comfortable limits.",
                    "action": "View Details",
                    "goto": "monitor",
                }
            )

        tips = [
            {"icon": "🪟", "text": "Close applications you have finished using."},
            {"icon": "🧹", "text": "Reduce background applications you don't need."},
            {"icon": "🔌", "text": "Keep your charger handy when possible."},
            {"icon": "🛡", "text": "Never force-quit System applications."},
        ]

        return cards, tips

    # ------------------------------------------------------------------
    # PROCESS STATUS
    # ------------------------------------------------------------------

    @staticmethod
    def process_status(process):
        """Return (word, level) describing one application's load."""
        cpu = process.get("cpu", 0)
        memory = process.get("memory", 0)
        if cpu >= 20 or memory >= 15:
            return "HIGH USAGE", "attention"
        return "NORMAL", "good"

    # ------------------------------------------------------------------
    # INSIGHTS PAGE (DATA-DRIVEN, FRIENDLY)
    # ------------------------------------------------------------------

    @staticmethod
    def insights(history):
        rows = [
            row
            for row in history
            if row.get("cpu") is not None and row.get("ram") is not None
        ]

        if len(rows) < 2:
            return [
                {
                    "level": "neutral",
                    "icon": "🕒",
                    "title": "Collecting data",
                    "text": (
                        "Your laptop is still getting to know itself. Insights "
                        "will appear once a little history has been recorded."
                    ),
                }
            ]

        def average(items, key):
            values = [item[key] for item in items if item.get(key) is not None]
            return sum(values) / len(values) if values else 0.0

        midpoint = len(rows) // 2
        cpu_before = average(rows[:midpoint], "cpu")
        cpu_now = average(rows[midpoint:], "cpu")
        cpu_delta = cpu_now - cpu_before
        ram_average = average(rows, "ram")
        disk_average = average(rows, "disk")

        insights_out = []

        if cpu_delta >= 8:
            insights_out.append(
                {
                    "level": "attention",
                    "icon": "📈",
                    "title": "CPU Insight",
                    "text": (
                        f"Your CPU usage has risen over the last few minutes "
                        f"({cpu_before:.0f}% → {cpu_now:.0f}%). Closing heavy "
                        "applications would help."
                    ),
                }
            )
        elif cpu_delta <= -8:
            insights_out.append(
                {
                    "level": "good",
                    "icon": "📉",
                    "title": "CPU Insight",
                    "text": "Your CPU usage has eased off recently. Things are calming down.",
                }
            )
        else:
            insights_out.append(
                {
                    "level": "good",
                    "icon": "⚖️",
                    "title": "CPU Insight",
                    "text": f"Your CPU usage has stayed fairly steady around {cpu_now:.0f}%.",
                }
            )

        if ram_average >= 75:
            insights_out.append(
                {
                    "level": "attention",
                    "icon": "🧠",
                    "title": "Memory Insight",
                    "text": (
                        f"Memory usage has stayed high around {ram_average:.0f}%. "
                        "Closing unused applications would give your laptop more "
                        "room to breathe."
                    ),
                }
            )
        else:
            insights_out.append(
                {
                    "level": "good",
                    "icon": "📦",
                    "title": "Memory Insight",
                    "text": f"Memory usage has been comfortable at {ram_average:.0f}%.",
                }
            )

        battery_rows = [row for row in rows if row.get("battery") is not None]
        if battery_rows:
            first = battery_rows[0]
            last = battery_rows[-1]
            elapsed_minutes = (last["timestamp"] - first["timestamp"]) / 60.0
            drop = first["battery"] - last["battery"]
            if elapsed_minutes >= 2:
                rate = drop / elapsed_minutes
                if rate >= 1.0:
                    insights_out.append(
                        {
                            "level": "attention",
                            "icon": "🔋",
                            "title": "Battery Insight",
                            "text": (
                                "Your battery is draining fairly quickly. Lowering "
                                "screen brightness or closing background apps could help."
                            ),
                        }
                    )
                else:
                    insights_out.append(
                        {
                            "level": "good",
                            "icon": "🔋",
                            "title": "Battery Insight",
                            "text": f"Your battery looks healthy at {round(last['battery'])}%.",
                        }
                    )
            else:
                insights_out.append(
                    {
                        "level": "neutral",
                        "icon": "🔋",
                        "title": "Battery Insight",
                        "text": f"Your battery is currently at {round(last['battery'])}%.",
                    }
                )

        if disk_average >= 85:
            insights_out.append(
                {
                    "level": "attention",
                    "icon": "💾",
                    "title": "Storage Insight",
                    "text": (
                        f"Your storage is nearly full ({disk_average:.0f}%). "
                        "Removing large files would help your laptop stay fast."
                    ),
                }
            )
        else:
            insights_out.append(
                {
                    "level": "good",
                    "icon": "💾",
                    "title": "Storage Insight",
                    "text": "Your storage has plenty of free space.",
                }
            )

        overall = (cpu_now * 0.6) + (ram_average * 0.4)
        if overall >= 75:
            insights_out.append(
                {
                    "level": "attention",
                    "icon": "🎛️",
                    "title": "Overview",
                    "text": "Overall, your laptop has been working hard lately.",
                }
            )
        else:
            insights_out.append(
                {
                    "level": "good",
                    "icon": "🎛️",
                    "title": "Overview",
                    "text": "Overall, your laptop has been running smoothly.",
                }
            )

        return insights_out