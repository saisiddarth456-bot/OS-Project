"""
gui.py

Modern, accessible, user-friendly desktop interface for the Smart Laptop Resource Optimizer.
Designed as a modern laptop health & control center for everyday users.

Architecture:
    - Left sidebar navigation (Home, Monitor, Optimize, Insights, History, Settings)
    - Fully responsive layouts using CustomTkinter scrollable containers
    - Real-time OS telemetry from system_monitor.py (psutil)
    - Plain-language analysis from recommendation.py
    - Safe scheduling & priority adjustments from scheduler.py
    - History & persistence via database.py
    - Non-blocking updates via Tkinter after()
"""

import os
import time
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import scheduler as schmod
import system_monitor as sm
from database import Database
from recommendation import RecommendationEngine

# ----------------------------------------------------------------------
# THEME CONFIGURATION
# ----------------------------------------------------------------------

THEMES = {
    "dark": {
        "bg": "#0d1117",
        "sidebar": "#161b22",
        "sidebar_hl": "#21262d",
        "card": "#1c2128",
        "card_alt": "#22272e",
        "border": "#30363d",
        "text": "#f0f6fc",
        "muted": "#8b949e",
        "subtle": "#6e7681",
        "accent": "#388bfd",
        "accent_hover": "#1f6feb",
        "accent_soft": "#13233a",
        "healthy": "#2ea043",
        "healthy_bg": "#132d1d",
        "warning": "#d29922",
        "warning_bg": "#362a12",
        "critical": "#f85149",
        "critical_bg": "#3e171b",
        "fig_bg": "#161b22",
        "grid": "#2d333b",
    },
    "light": {
        "bg": "#f6f8fa",
        "sidebar": "#ffffff",
        "sidebar_hl": "#f3f4f6",
        "card": "#ffffff",
        "card_alt": "#f6f8fa",
        "border": "#d0d7de",
        "text": "#1f2328",
        "muted": "#57606a",
        "subtle": "#656d76",
        "accent": "#0969da",
        "accent_hover": "#0550ae",
        "accent_soft": "#ddf4ff",
        "healthy": "#1a7f37",
        "healthy_bg": "#dafbe1",
        "warning": "#9a6700",
        "warning_bg": "#fff8c5",
        "critical": "#cf222e",
        "critical_bg": "#ffebe9",
        "fig_bg": "#ffffff",
        "grid": "#e1e4e8",
    },
}

NAV_ITEMS = [
    ("home", "🏠", "Home"),
    ("monitor", "📊", "Monitor"),
    ("optimize", "🚀", "Optimize"),
    ("insights", "🧠", "Insights"),
    ("history", "📜", "History"),
    ("settings", "⚙️", "Settings"),
]

DEFAULT_SETTINGS = {
    "refresh_ms": "1000",
    "autostart": "1",
    "theme": "dark",
}

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "smart_optimizer.db")
TOP_ROWS = 5


# ----------------------------------------------------------------------
# TOOLTIP HELPER
# ----------------------------------------------------------------------

class CToolTip:
    """Lightweight, accessible hover tooltip for CustomTkinter widgets."""

    def __init__(self, widget, text, delay_ms=350):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.tip_window = None
        self.after_id = None
        self.widget.bind("<Enter>", self._on_enter, add="+")
        self.widget.bind("<Leave>", self._on_leave, add="+")
        self.widget.bind("<ButtonPress>", self._on_leave, add="+")

    def _on_enter(self, _event=None):
        self._cancel()
        self.after_id = self.widget.after(self.delay_ms, self._show)

    def _on_leave(self, _event=None):
        self._cancel()
        self._hide()

    def _cancel(self):
        if self.after_id:
            try:
                self.widget.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None

    def _show(self):
        if self.tip_window or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 15
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        except Exception:
            return

        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        try:
            tw.attributes("-topmost", True)
        except Exception:
            pass

        mode = ctk.get_appearance_mode().lower()
        bg = "#1e293b" if mode == "dark" else "#ffffff"
        fg = "#f8fafc" if mode == "dark" else "#0f172a"
        border = "#334155" if mode == "dark" else "#cbd5e1"

        frame = tk.Frame(
            tw,
            background=bg,
            highlightbackground=border,
            highlightthickness=1,
            padx=10,
            pady=6,
        )
        frame.pack()
        label = tk.Label(
            frame,
            text=self.text,
            justify="left",
            background=bg,
            foreground=fg,
            font=("Helvetica Neue", 11),
            wraplength=280,
        )
        label.pack()

    def _hide(self):
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None

    def update_text(self, text):
        self.text = text


# ----------------------------------------------------------------------
# REUSABLE UI COMPONENT: STATUS BADGE
# ----------------------------------------------------------------------

class StatusBadge(ctk.CTkFrame):
    """Pill-shaped accessible badge displaying both icon and text."""

    def __init__(self, parent, text="GOOD", level="good", font_size=11, **kwargs):
        super().__init__(parent, corner_radius=12, **kwargs)
        self.text = text
        self.level = level
        self.label = ctk.CTkLabel(
            self,
            text=f"●  {text}",
            font=ctk.CTkFont(family="Helvetica Neue", size=font_size, weight="bold"),
            padx=10,
            pady=2,
        )
        self.label.pack()
        self.set_status(text, level)

    def set_status(self, text, level):
        self.text = text
        self.level = level
        mode = ctk.get_appearance_mode().lower()
        palette = THEMES.get(mode, THEMES["dark"])

        level_map = {
            "good": (palette["healthy"], palette["healthy_bg"]),
            "healthy": (palette["healthy"], palette["healthy_bg"]),
            "attention": (palette["warning"], palette["warning_bg"]),
            "warning": (palette["warning"], palette["warning_bg"]),
            "high": (palette["critical"], palette["critical_bg"]),
            "critical": (palette["critical"], palette["critical_bg"]),
            "neutral": (palette["muted"], palette["border"]),
        }
        fg_color, bg_color = level_map.get(level.lower(), (palette["muted"], palette["border"]))

        self.configure(fg_color=bg_color)
        self.label.configure(text=f"●  {text.upper()}", text_color=fg_color)


# ----------------------------------------------------------------------
# REUSABLE UI COMPONENT: RESOURCE CARD
# ----------------------------------------------------------------------

class ResourceCard(ctk.CTkFrame):
    """Large, visually distinct resource card for CPU, RAM, Battery, or Disk."""

    def __init__(
        self,
        parent,
        icon,
        title,
        tooltip_text="",
        palette=None,
        font_func=None,
        **kwargs,
    ):
        super().__init__(parent, corner_radius=16, **kwargs)
        self.palette = palette or THEMES["dark"]
        self._font = font_func or (lambda s, w="normal": ctk.CTkFont(family="Helvetica Neue", size=s, weight=w))
        self.configure(fg_color=self.palette["card"], border_width=1, border_color=self.palette["border"])

        # Top bar: Icon, Title, and Tooltip Hint
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(16, 4))

        self.icon_label = ctk.CTkLabel(top, text=icon, font=self._font(22))
        self.icon_label.pack(side="left")

        self.title_label = ctk.CTkLabel(
            top,
            text=title,
            font=self._font(14, "bold"),
            text_color=self.palette["muted"],
        )
        self.title_label.pack(side="left", padx=8)

        self.help_icon = ctk.CTkLabel(
            top,
            text="ⓘ",
            font=self._font(13),
            text_color=self.palette["subtle"],
            cursor="question_arrow",
        )
        self.help_icon.pack(side="right")
        self.tooltip = CToolTip(self.help_icon, tooltip_text)

        # Big percentage readout and status badge
        mid = ctk.CTkFrame(self, fg_color="transparent")
        mid.pack(fill="x", padx=18, pady=(2, 6))

        self.value_label = ctk.CTkLabel(
            mid,
            text="—",
            font=self._font(34, "bold"),
            text_color=self.palette["text"],
        )
        self.value_label.pack(side="left")

        self.badge = StatusBadge(mid, text="CHECKING", level="neutral")
        self.badge.pack(side="right", pady=4)

        # Visual progress bar
        self.progress = ctk.CTkProgressBar(
            self,
            height=8,
            corner_radius=4,
            fg_color=self.palette["border"],
            progress_color=self.palette["accent"],
        )
        self.progress.pack(fill="x", padx=18, pady=(4, 8))
        self.progress.set(0)

        # Short human explanation
        self.explanation_label = ctk.CTkLabel(
            self,
            text="Checking your laptop...",
            font=self._font(12),
            text_color=self.palette["text"],
            justify="left",
            anchor="w",
            wraplength=230,
        )
        self.explanation_label.pack(fill="x", padx=18, pady=(0, 4))

        # Secondary info sub-text
        self.sub_label = ctk.CTkLabel(
            self,
            text="",
            font=self._font(11),
            text_color=self.palette["muted"],
            justify="left",
            anchor="w",
        )
        self.sub_label.pack(fill="x", padx=18, pady=(0, 16))

    def update_data(self, percent, badge_text, badge_level, explanation, sub_text=""):
        palette = self.palette
        if percent is None:
            self.value_label.configure(text="—")
            self.progress.set(0)
            self.badge.set_status("UNAVAILABLE", "neutral")
            self.explanation_label.configure(text=explanation or "Information unavailable for this device.")
            self.sub_label.configure(text=sub_text)
            return

        clamped = max(0.0, min(float(percent), 100.0))
        self.value_label.configure(text=f"{clamped:.0f}%")
        self.progress.set(clamped / 100.0)

        # Pick color for progress bar
        level_clean = badge_level.lower()
        if level_clean in ("high", "critical"):
            bar_color = palette["critical"]
        elif level_clean in ("attention", "warning", "low"):
            bar_color = palette["warning"]
        else:
            bar_color = palette["healthy"]
        self.progress.configure(progress_color=bar_color)

        self.badge.set_status(badge_text, badge_level)
        self.explanation_label.configure(text=explanation)
        self.sub_label.configure(text=sub_text)

    def apply_theme(self, palette):
        self.palette = palette
        self.configure(fg_color=palette["card"], border_color=palette["border"])
        self.title_label.configure(text_color=palette["muted"])
        self.help_icon.configure(text_color=palette["subtle"])
        self.value_label.configure(text_color=palette["text"])
        self.explanation_label.configure(text_color=palette["text"])
        self.sub_label.configure(text=palette["muted"])
        self.progress.configure(fg_color=palette["border"])
        self.badge.set_status(self.badge.text, self.badge.level)


# ----------------------------------------------------------------------
# MAIN APPLICATION
# ----------------------------------------------------------------------

class SmartOptimizerApp(ctk.CTk):
    """Consumer-grade Smart Laptop Optimizer application."""

    def __init__(self):
        super().__init__()

        self.monitor = sm.SystemMonitor()
        self.engine = RecommendationEngine()
        self.db = Database(DB_PATH)

        self.settings = {}
        for key, default in DEFAULT_SETTINGS.items():
            self.settings[key] = self.db.get_setting(key, default)

        self.appearance_mode = self.settings.get("theme", "dark")
        self.palette = THEMES.get(self.appearance_mode, THEMES["dark"])

        self.after_id = None
        self.current_page = "home"
        self.closing = False
        self.snapshot = None
        self.has_initial_data = False
        self.history_timeframe = "30m"

        self.themed_widgets = []

        self._configure_window()
        ctk.set_appearance_mode(self.appearance_mode)

        # Main Layout Container: column 0 = sidebar, column 1 = page container
        self._container = ctk.CTkFrame(self, fg_color=self.palette["bg"], corner_radius=0)
        self._container.grid(row=0, column=1, sticky="nsew")
        self._container.grid_rowconfigure(0, weight=1)
        self._container.grid_columnconfigure(0, weight=1)

        self._pages = {}
        self._build_sidebar()
        self._build_pages()
        self._show_page("home")

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(150, self._bootstrap)

    def _configure_window(self):
        self.title("Smart Laptop Optimizer")
        self.geometry("1240x820")
        self.minsize(1080, 700)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

    def _font(self, size, weight="normal"):
        return ctk.CTkFont(family="Helvetica Neue", size=size, weight=weight)

    # ==================================================================
    # THEME MANAGEMENT
    # ==================================================================

    def _apply_theme(self):
        theme = self.settings.get("theme", "dark")
        self.palette = THEMES.get(theme, THEMES["dark"])
        ctk.set_appearance_mode(theme)

        self._container.configure(fg_color=self.palette["bg"])
        self.sidebar_frame.configure(fg_color=self.palette["sidebar"])
        self.brand_title.configure(text_color=self.palette["text"])
        self.brand_sub.configure(text_color=self.palette["muted"])

        for page in self._pages.values():
            page.configure(fg_color=self.palette["bg"])

        for card in getattr(self, "all_resource_cards", []):
            card.apply_theme(self.palette)

        self._style_nav(self.current_page)
        if self.current_page == "history":
            self._draw_history()

    # ==================================================================
    # SIDEBAR NAVIGATION
    # ==================================================================

    def _build_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, fg_color=self.palette["sidebar"], corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.configure(width=224)
        self.sidebar_frame.grid_propagate(False)

        # Brand header
        brand_block = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        brand_block.pack(fill="x", padx=18, pady=(24, 20))

        logo = ctk.CTkLabel(
            brand_block,
            text="⚡",
            font=self._font(28),
            text_color=self.palette["accent"],
        )
        logo.pack(side="left", padx=(0, 10))

        text_sub_block = ctk.CTkFrame(brand_block, fg_color="transparent")
        text_sub_block.pack(side="left")

        self.brand_title = ctk.CTkLabel(
            text_sub_block,
            text="Laptop Health",
            font=self._font(16, "bold"),
            text_color=self.palette["text"],
            anchor="w",
        )
        self.brand_title.pack(anchor="w")

        self.brand_sub = ctk.CTkLabel(
            text_sub_block,
            text="Smart Optimizer",
            font=self._font(12),
            text_color=self.palette["muted"],
            anchor="w",
        )
        self.brand_sub.pack(anchor="w")

        # Nav Buttons
        nav_container = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        nav_container.pack(fill="x", padx=12, pady=10)

        self.nav_buttons = {}
        for key, icon, label in NAV_ITEMS:
            btn = ctk.CTkButton(
                nav_container,
                text=f"  {icon}   {label}",
                anchor="w",
                height=44,
                corner_radius=10,
                font=self._font(13, "bold"),
                fg_color="transparent",
                text_color=self.palette["muted"],
                hover_color=self.palette["sidebar_hl"],
                command=lambda k=key: self._show_page(k),
            )
            btn.pack(fill="x", pady=3)
            self.nav_buttons[key] = btn

        # Footer info pill
        footer = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=16, pady=18)

        self.sidebar_platform_label = ctk.CTkLabel(
            footer,
            text=f"💻 {sm.SystemMonitor.platform_name()}",
            font=self._font(11),
            text_color=self.palette["subtle"],
            anchor="w",
        )
        self.sidebar_platform_label.pack(fill="x")

        status_live = ctk.CTkLabel(
            footer,
            text="● Live Protection Active",
            font=self._font(10, "bold"),
            text_color=self.palette["healthy"],
            anchor="w",
        )
        status_live.pack(fill="x", pady=(2, 0))

    def _style_nav(self, selected_key):
        palette = self.palette
        for nav_key, button in self.nav_buttons.items():
            if nav_key == selected_key:
                button.configure(
                    fg_color=palette["accent"],
                    text_color="#ffffff",
                    hover_color=palette["accent_hover"],
                )
            else:
                button.configure(
                    fg_color="transparent",
                    text_color=palette["muted"],
                    hover_color=palette["sidebar_hl"],
                )

    def _show_page(self, key, push_history=True):
        if push_history and getattr(self, "current_page", None) and self.current_page != key:
            if not hasattr(self, "page_history"):
                self.page_history = []
            self.page_history.append(self.current_page)

        self.current_page = key
        if key in self._pages:
            self._pages[key].tkraise()
        self._style_nav(key)

        # Immediately update the page when switched
        if self.snapshot:
            cpu = self.snapshot["cpu"]
            ram = self.snapshot["ram"]["percent"]
            battery = self.snapshot["battery"]
            processes = self.snapshot["processes"]
            if key == "home":
                self._update_home(self.snapshot)
            elif key == "monitor":
                self._update_monitor(self.snapshot)
            elif key == "optimize":
                self._update_optimize(cpu, ram, battery, processes)
            elif key == "insights":
                self._update_insights()
            elif key == "history":
                self._draw_history()

    def _go_back(self):
        if hasattr(self, "page_history") and self.page_history:
            prev = self.page_history.pop()
            self._show_page(prev, push_history=False)
        else:
            self._show_page("home", push_history=False)

    # ==================================================================
    # PAGE INITIALIZATION
    # ==================================================================

    def _new_page(self):
        page = ctk.CTkFrame(self._container, fg_color=self.palette["bg"], corner_radius=0)
        page.grid(row=0, column=0, sticky="nsew")
        page.grid_rowconfigure(0, weight=1)
        page.grid_columnconfigure(0, weight=1)
        return page

    def _build_pages(self):
        self.all_resource_cards = []
        self._build_home()
        self._build_monitor()
        self._build_optimize()
        self._build_insights()
        self._build_history()
        self._build_settings()

    def _page_header(self, parent, title, subtitle, show_back=False):
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", padx=32, pady=(24, 14))

        if show_back:
            back_btn = ctk.CTkButton(
                header,
                text="← Back",
                font=self._font(12, "bold"),
                width=80,
                height=32,
                corner_radius=8,
                fg_color=self.palette["card"],
                text_color=self.palette["text"],
                hover_color=self.palette["sidebar_hl"],
                command=self._go_back,
            )
            back_btn.pack(side="left", padx=(0, 14))

        text_block = ctk.CTkFrame(header, fg_color="transparent")
        text_block.pack(side="left", fill="x", expand=True)

        t_lbl = ctk.CTkLabel(
            text_block,
            text=title,
            font=self._font(26, "bold"),
            text_color=self.palette["text"],
            anchor="w",
        )
        t_lbl.pack(anchor="w")

        s_lbl = ctk.CTkLabel(
            text_block,
            text=subtitle,
            font=self._font(13),
            text_color=self.palette["muted"],
            anchor="w",
        )
        s_lbl.pack(anchor="w", pady=(2, 0))
        return header

    # ==================================================================
    # 1. HOME PAGE
    # ==================================================================

    def _build_home(self):
        page = self._new_page()
        self._pages["home"] = page

        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        # Header
        self._page_header(
            scroll,
            "Smart Laptop Optimizer",
            "Understand your laptop. Keep it running smoothly.",
        )

        # Big System Status Card
        status_card = ctk.CTkFrame(
            scroll,
            fg_color=self.palette["card"],
            corner_radius=18,
            border_width=1,
            border_color=self.palette["border"],
        )
        status_card.pack(fill="x", padx=32, pady=(0, 16))

        sc_inner = ctk.CTkFrame(status_card, fg_color="transparent")
        sc_inner.pack(fill="x", padx=24, pady=20)

        top_meta = ctk.CTkFrame(sc_inner, fg_color="transparent")
        top_meta.pack(fill="x", pady=(0, 6))

        sc_title = ctk.CTkLabel(
            top_meta,
            text="SYSTEM STATUS",
            font=self._font(12, "bold"),
            text_color=self.palette["muted"],
        )
        sc_title.pack(side="left")

        self.home_live_badge = ctk.CTkLabel(
            top_meta,
            text="● Live Monitoring",
            font=self._font(11, "bold"),
            text_color=self.palette["healthy"],
        )
        self.home_live_badge.pack(side="right")

        content_row = ctk.CTkFrame(sc_inner, fg_color="transparent")
        content_row.pack(fill="x")

        self.status_icon_label = ctk.CTkLabel(
            content_row,
            text="🟢",
            font=self._font(42),
        )
        self.status_icon_label.pack(side="left", padx=(0, 16))

        text_box = ctk.CTkFrame(content_row, fg_color="transparent")
        text_box.pack(side="left", fill="x", expand=True)

        self.status_headline = ctk.CTkLabel(
            text_box,
            text="Good",
            font=self._font(22, "bold"),
            text_color=self.palette["text"],
            anchor="w",
        )
        self.status_headline.pack(anchor="w")

        self.status_explanation = ctk.CTkLabel(
            text_box,
            text="Checking your laptop...",
            font=self._font(14),
            text_color=self.palette["muted"],
            anchor="w",
            wraplength=680,
            justify="left",
        )
        self.status_explanation.pack(anchor="w", pady=(3, 0))

        # 4 Large Resource Cards (CPU, Memory, Battery, Storage)
        cards_grid = ctk.CTkFrame(scroll, fg_color="transparent")
        cards_grid.pack(fill="x", padx=32, pady=(0, 16))
        for col in range(4):
            cards_grid.grid_columnconfigure(col, weight=1)

        self.home_cards = {}
        specs = [
            ("cpu", "🧠", "Processor (CPU)", "Processor shows how hard your laptop's brain is working."),
            ("ram", "🗃️", "Memory (RAM)", "Memory shows how much temporary workspace your open applications are using."),
            ("battery", "🔋", "Battery", "Battery shows how much power remains and charging status."),
            ("disk", "💾", "Storage", "Storage shows how much space is left on your laptop's hard drive."),
        ]

        for col, (key, icon, title, tooltip) in enumerate(specs):
            card = ResourceCard(
                cards_grid,
                icon=icon,
                title=title,
                tooltip_text=tooltip,
                palette=self.palette,
                font_func=self._font,
            )
            card.grid(row=0, column=col, sticky="nsew", padx=6)
            self.home_cards[key] = card
            self.all_resource_cards.append(card)

        # Smart Insight Card
        insight_card = ctk.CTkFrame(
            scroll,
            fg_color=self.palette["card"],
            corner_radius=18,
            border_width=1,
            border_color=self.palette["border"],
        )
        insight_card.pack(fill="x", padx=32, pady=(0, 16))

        ic_inner = ctk.CTkFrame(insight_card, fg_color="transparent")
        ic_inner.pack(fill="x", padx=24, pady=20)

        ic_head = ctk.CTkLabel(
            ic_inner,
            text="🧠  Smart Insight",
            font=self._font(16, "bold"),
            text_color=self.palette["text"],
            anchor="w",
        )
        ic_head.pack(anchor="w", pady=(0, 12))

        # Three distinct sections: What's happening, Why, What can you do
        sections_frame = ctk.CTkFrame(ic_inner, fg_color="transparent")
        sections_frame.pack(fill="x")
        sections_frame.grid_columnconfigure(0, weight=1)
        sections_frame.grid_columnconfigure(1, weight=1)
        sections_frame.grid_columnconfigure(2, weight=1)

        def make_insight_pill(parent, col, heading, default_text):
            box = ctk.CTkFrame(parent, fg_color=self.palette["card_alt"], corner_radius=12)
            box.grid(row=0, column=col, sticky="nsew", padx=6, pady=4)

            h = ctk.CTkLabel(
                box,
                text=heading,
                font=self._font(11, "bold"),
                text_color=self.palette["muted"],
                anchor="w",
            )
            h.pack(fill="x", padx=14, pady=(12, 4))

            b = ctk.CTkLabel(
                box,
                text=default_text,
                font=self._font(13),
                text_color=self.palette["text"],
                justify="left",
                anchor="w",
                wraplength=270,
            )
            b.pack(fill="both", expand=True, padx=14, pady=(0, 14))
            return b

        self.insight_happening = make_insight_pill(
            sections_frame, 0, "WHAT'S HAPPENING?", "Your laptop is running smoothly."
        )
        self.insight_why = make_insight_pill(
            sections_frame, 1, "WHY?", "Resource usage is within comfortable limits."
        )
        self.insight_action = make_insight_pill(
            sections_frame, 2, "WHAT CAN YOU DO?", "No action required right now."
        )

        # Top Applications Card
        apps_card = ctk.CTkFrame(
            scroll,
            fg_color=self.palette["card"],
            corner_radius=18,
            border_width=1,
            border_color=self.palette["border"],
        )
        apps_card.pack(fill="x", padx=32, pady=(0, 24))

        ac_inner = ctk.CTkFrame(apps_card, fg_color="transparent")
        ac_inner.pack(fill="x", padx=24, pady=20)

        ac_top = ctk.CTkFrame(ac_inner, fg_color="transparent")
        ac_top.pack(fill="x", pady=(0, 12))

        ac_title = ctk.CTkLabel(
            ac_top,
            text="Applications Using the Most Resources",
            font=self._font(16, "bold"),
            text_color=self.palette["text"],
        )
        ac_title.pack(side="left")

        ac_sub = ctk.CTkButton(
            ac_top,
            text="View All in Monitor →",
            font=self._font(12, "bold"),
            fg_color="transparent",
            text_color=self.palette["accent"],
            hover_color=self.palette["sidebar_hl"],
            command=lambda: self._show_page("monitor"),
        )
        ac_sub.pack(side="right")

        # Application rows container
        self.app_rows_container = ctk.CTkFrame(ac_inner, fg_color="transparent")
        self.app_rows_container.pack(fill="x")

        self.home_app_widgets = []
        for _ in range(TOP_ROWS):
            row = ctk.CTkFrame(self.app_rows_container, fg_color=self.palette["card_alt"], corner_radius=12)
            row.pack(fill="x", pady=4)

            icon_lbl = ctk.CTkLabel(row, text="📱", font=self._font(20))
            icon_lbl.pack(side="left", padx=(14, 8), pady=10)

            name_lbl = ctk.CTkLabel(
                row,
                text="—",
                font=self._font(14, "bold"),
                text_color=self.palette["text"],
                anchor="w",
            )
            name_lbl.pack(side="left", padx=6)

            badge = StatusBadge(row, text="NORMAL", level="good")
            badge.pack(side="right", padx=(12, 14), pady=8)

            ram_lbl = ctk.CTkLabel(
                row,
                text="Memory: —",
                font=self._font(13),
                text_color=self.palette["muted"],
            )
            ram_lbl.pack(side="right", padx=12)

            cpu_lbl = ctk.CTkLabel(
                row,
                text="CPU: —",
                font=self._font(13, "bold"),
                text_color=self.palette["text"],
            )
            cpu_lbl.pack(side="right", padx=12)

            self.home_app_widgets.append({
                "frame": row,
                "icon": icon_lbl,
                "name": name_lbl,
                "cpu": cpu_lbl,
                "ram": ram_lbl,
                "badge": badge,
            })

    def _update_home(self, snapshot):
        cpu = snapshot["cpu"]
        ram = snapshot["ram"]
        battery = snapshot["battery"]
        disk = snapshot["disk"]
        processes = snapshot["processes"]

        # 1. Overall Status
        level, word, explanation = self.engine.overall_status(cpu, ram["percent"])
        icon = "🟢" if level == "good" else ("🟡" if level == "attention" else "🔴")
        self.status_icon_label.configure(text=icon)
        self.status_headline.configure(text=word)
        self.status_explanation.configure(text=explanation)

        # 2. Resource Cards
        # CPU
        cpu_st = self.engine.resource_state("cpu", cpu)
        cores = snapshot.get("cpu_cores", 1)
        freq = snapshot.get("cpu_freq")
        cpu_sub = f"{cores} cores active" + (f" · {freq / 1000:.1f} GHz" if freq else "")
        self.home_cards["cpu"].update_data(
            cpu, cpu_st["word"], cpu_st["level"], cpu_st["message"], cpu_sub
        )

        # RAM
        ram_percent = ram["percent"]
        ram_st = self.engine.resource_state("ram", ram_percent)
        ram_sub = f"{sm.format_bytes(ram['used'])} of {sm.format_bytes(ram['total'])} in use"
        self.home_cards["ram"].update_data(
            ram_percent, ram_st["word"], ram_st["level"], ram_st["message"], ram_sub
        )

        # Battery
        if battery is not None:
            bat_percent = battery["percent"]
            bat_st = self.engine.resource_state("battery", bat_percent, battery["plugged"])
            secs = battery.get("seconds_left")
            if battery["plugged"]:
                bat_sub = "Connected to power (Charging)"
            elif secs and secs > 0:
                bat_sub = f"Estimated {sm.format_duration(secs)} remaining"
            else:
                bat_sub = "Running on battery"
            self.home_cards["battery"].update_data(
                bat_percent, bat_st["word"], bat_st["level"], bat_st["message"], bat_sub
            )
        else:
            self.home_cards["battery"].update_data(
                None,
                "UNAVAILABLE",
                "neutral",
                "This device does not provide battery information (e.g. desktop Mac or direct power).",
                "Desktop / Direct Power",
            )

        # Storage
        disk_percent = disk["percent"]
        disk_st = self.engine.resource_state("disk", disk_percent)
        disk_sub = f"{sm.format_bytes(disk['used'])} of {sm.format_bytes(disk['total'])} used"
        self.home_cards["disk"].update_data(
            disk_percent, disk_st["word"], disk_st["level"], disk_st["message"], disk_sub
        )

        # 3. Smart Insight
        insight = self.engine.smart_insight(cpu, ram["percent"], battery, processes)
        self.insight_happening.configure(text=insight.get("happening", ""))
        self.insight_why.configure(text=insight.get("why", ""))
        self.insight_action.configure(text=insight.get("action", ""))

        # 4. Top Applications
        top = sorted(processes, key=lambda p: p["cpu"], reverse=True)[:TOP_ROWS]
        for index, row in enumerate(self.home_app_widgets):
            if index < len(top):
                proc = top[index]
                clean_name = sm.friendly_name(proc["name"])
                icon = sm.app_icon(clean_name)
                badge_text, badge_level = self.engine.process_status(proc)

                row["icon"].configure(text=icon)
                row["name"].configure(text=clean_name)
                row["cpu"].configure(text=f"CPU: {proc['cpu']:.1f}%")
                row["ram"].configure(text=f"Memory: {proc['memory']:.1f}%")
                row["badge"].set_status(badge_text, badge_level)
                row["frame"].pack(fill="x", pady=4)
            else:
                row["frame"].pack_forget()

    # ==================================================================
    # 2. MONITOR PAGE
    # ==================================================================

    def _build_monitor(self):
        page = self._new_page()
        self._pages["monitor"] = page

        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        self._page_header(
            scroll,
            "Detailed System Monitor",
            "Comprehensive, live breakdown of your laptop hardware and running applications.",
            show_back=True,
        )

        # Section 1: System Hardware
        hw_label = ctk.CTkLabel(
            scroll, text="HARDWARE OVERVIEW", font=self._font(12, "bold"), text_color=self.palette["muted"]
        )
        hw_label.pack(anchor="w", padx=32, pady=(0, 8))

        cards_grid = ctk.CTkFrame(scroll, fg_color="transparent")
        cards_grid.pack(fill="x", padx=32, pady=(0, 16))
        for col in range(4):
            cards_grid.grid_columnconfigure(col, weight=1)

        self.monitor_cards = {}
        specs = [
            ("cpu", "🧠", "Processor (CPU)", "Real-time CPU workload."),
            ("ram", "🗃️", "Memory (RAM)", "Real-time virtual memory consumption."),
            ("battery", "🔋", "Battery", "Battery percentage and power state."),
            ("disk", "💾", "Storage", "Primary startup disk storage status."),
        ]

        for col, (key, icon, title, tooltip) in enumerate(specs):
            card = ResourceCard(
                cards_grid,
                icon=icon,
                title=title,
                tooltip_text=tooltip,
                palette=self.palette,
                font_func=self._font,
            )
            card.grid(row=0, column=col, sticky="nsew", padx=6)
            self.monitor_cards[key] = card
            self.all_resource_cards.append(card)

        # Section 2: System Activity & Metadata
        act_label = ctk.CTkLabel(
            scroll, text="SYSTEM ACTIVITY", font=self._font(12, "bold"), text_color=self.palette["muted"]
        )
        act_label.pack(anchor="w", padx=32, pady=(8, 8))

        meta_grid = ctk.CTkFrame(scroll, fg_color="transparent")
        meta_grid.pack(fill="x", padx=32, pady=(0, 16))
        for col in range(4):
            meta_grid.grid_columnconfigure(col, weight=1)

        self.monitor_meta_labels = {}
        meta_specs = [
            ("processes", "⚙️ Active Processes", "Total running background tasks"),
            ("uptime", "🕒 System Uptime", "Time elapsed since last laptop reboot"),
            ("cores", "🧮 CPU Hardware", "Processor physical cores and frequency"),
            ("platform", "💻 Platform & Architecture", "Operating system and kernel version"),
        ]

        for col, (key, title, subtitle) in enumerate(meta_specs):
            box = ctk.CTkFrame(meta_grid, fg_color=self.palette["card"], corner_radius=14, border_width=1, border_color=self.palette["border"])
            box.grid(row=0, column=col, sticky="nsew", padx=6)

            h = ctk.CTkLabel(box, text=title, font=self._font(12, "bold"), text_color=self.palette["muted"], anchor="w")
            h.pack(fill="x", padx=16, pady=(14, 2))

            v = ctk.CTkLabel(box, text="—", font=self._font(18, "bold"), text_color=self.palette["text"], anchor="w")
            v.pack(fill="x", padx=16, pady=(0, 2))
            self.monitor_meta_labels[key] = v

            s = ctk.CTkLabel(box, text=subtitle, font=self._font(11), text_color=self.palette["subtle"], anchor="w")
            s.pack(fill="x", padx=16, pady=(0, 14))

        # Section 3: Applications Side-by-Side (Top CPU vs Top RAM)
        app_label = ctk.CTkLabel(
            scroll, text="ACTIVE APPLICATIONS", font=self._font(12, "bold"), text_color=self.palette["muted"]
        )
        app_label.pack(anchor="w", padx=32, pady=(8, 8))

        tables_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        tables_frame.pack(fill="x", padx=32, pady=(0, 24))
        tables_frame.grid_columnconfigure(0, weight=1)
        tables_frame.grid_columnconfigure(1, weight=1)

        def make_monitor_table(parent, col, heading):
            card = ctk.CTkFrame(parent, fg_color=self.palette["card"], corner_radius=16, border_width=1, border_color=self.palette["border"])
            card.grid(row=0, column=col, sticky="nsew", padx=6)

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=20, pady=(16, 12))
            t = ctk.CTkLabel(top, text=heading, font=self._font(15, "bold"), text_color=self.palette["text"])
            t.pack(anchor="w")

            rows_box = ctk.CTkFrame(card, fg_color="transparent")
            rows_box.pack(fill="x", padx=14, pady=(0, 14))

            rows = []
            for _ in range(5):
                r = ctk.CTkFrame(rows_box, fg_color=self.palette["card_alt"], corner_radius=10)
                r.pack(fill="x", pady=3)

                ic = ctk.CTkLabel(r, text="📱", font=self._font(16))
                ic.pack(side="left", padx=(10, 6), pady=6)

                nm = ctk.CTkLabel(r, text="—", font=self._font(13, "bold"), text_color=self.palette["text"], anchor="w")
                nm.pack(side="left", padx=4)

                bd = StatusBadge(r, text="NORMAL", level="good", font_size=10)
                bd.pack(side="right", padx=(8, 10), pady=6)

                usage = ctk.CTkLabel(r, text="—", font=self._font(13), text_color=self.palette["muted"])
                usage.pack(side="right", padx=8)

                rows.append({"frame": r, "icon": ic, "name": nm, "usage": usage, "badge": bd})
            return rows

        self.monitor_cpu_rows = make_monitor_table(tables_frame, 0, "⚡ Highest Processor Load")
        self.monitor_ram_rows = make_monitor_table(tables_frame, 1, "📦 Highest Memory Usage")

    def _update_monitor(self, snapshot):
        cpu = snapshot["cpu"]
        ram = snapshot["ram"]
        disk = snapshot["disk"]
        battery = snapshot["battery"]
        processes = snapshot["processes"]

        # Hardware cards
        cpu_st = self.engine.resource_state("cpu", cpu)
        cores = snapshot.get("cpu_cores", 1)
        freq = snapshot.get("cpu_freq")
        cpu_sub = f"{cores} cores" + (f" · {freq / 1000:.1f} GHz" if freq else "")
        self.monitor_cards["cpu"].update_data(cpu, cpu_st["word"], cpu_st["level"], cpu_st["message"], cpu_sub)

        ram_percent = ram["percent"]
        ram_st = self.engine.resource_state("ram", ram_percent)
        ram_sub = f"{sm.format_bytes(ram['used'])} / {sm.format_bytes(ram['total'])}"
        self.monitor_cards["ram"].update_data(ram_percent, ram_st["word"], ram_st["level"], ram_st["message"], ram_sub)

        if battery is not None:
            bat_percent = battery["percent"]
            bat_st = self.engine.resource_state("battery", bat_percent, battery["plugged"])
            secs = battery.get("seconds_left")
            bat_sub = "Charging" if battery["plugged"] else (f"{sm.format_duration(secs)} left" if secs else "On battery")
            self.monitor_cards["battery"].update_data(bat_percent, bat_st["word"], bat_st["level"], bat_st["message"], bat_sub)
        else:
            self.monitor_cards["battery"].update_data(
                None, "UNAVAILABLE", "neutral", "Battery data unavailable.", "Desktop Mac / Direct Power"
            )

        disk_percent = disk["percent"]
        disk_st = self.engine.resource_state("disk", disk_percent)
        disk_sub = f"{sm.format_bytes(disk['used'])} / {sm.format_bytes(disk['total'])}"
        self.monitor_cards["disk"].update_data(disk_percent, disk_st["word"], disk_st["level"], disk_st["message"], disk_sub)

        # Meta labels
        self.monitor_meta_labels["processes"].configure(text=f"{snapshot.get('process_count', 0)} running")
        self.monitor_meta_labels["uptime"].configure(text=sm.format_duration(snapshot.get("uptime", 0)))
        self.monitor_meta_labels["cores"].configure(text=f"{cores} Physical Cores")
        self.monitor_meta_labels["platform"].configure(text=f"{snapshot.get('platform', '')} ({snapshot.get('machine', '')})")

        # Top CPU
        top_cpu = sorted(processes, key=lambda p: p["cpu"], reverse=True)[:5]
        for index, row in enumerate(self.monitor_cpu_rows):
            if index < len(top_cpu):
                p = top_cpu[index]
                name = sm.friendly_name(p["name"])
                row["icon"].configure(text=sm.app_icon(name))
                row["name"].configure(text=name)
                row["usage"].configure(text=f"{p['cpu']:.1f}% CPU")
                b_text, b_level = self.engine.process_status(p)
                row["badge"].set_status(b_text, b_level)
                row["frame"].pack(fill="x", pady=3)
            else:
                row["frame"].pack_forget()

        # Top RAM
        top_ram = sorted(processes, key=lambda p: p["memory"], reverse=True)[:5]
        for index, row in enumerate(self.monitor_ram_rows):
            if index < len(top_ram):
                p = top_ram[index]
                name = sm.friendly_name(p["name"])
                row["icon"].configure(text=sm.app_icon(name))
                row["name"].configure(text=name)
                row["usage"].configure(text=f"{p['memory']:.1f}% RAM")
                b_text, b_level = self.engine.process_status(p)
                row["badge"].set_status(b_text, b_level)
                row["frame"].pack(fill="x", pady=3)
            else:
                row["frame"].pack_forget()

    # ==================================================================
    # 3. OPTIMIZE PAGE
    # ==================================================================

    def _build_optimize(self):
        page = self._new_page()
        self._pages["optimize"] = page

        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        self._page_header(
            scroll,
            "How can I make my laptop run better?",
            "Safe, verified recommendations to improve speed, battery life, and system responsiveness.",
            show_back=True,
        )

        # Recommendation Cards Container
        self.opt_cards_container = ctk.CTkFrame(scroll, fg_color="transparent")
        self.opt_cards_container.pack(fill="x", padx=32, pady=(0, 16))

        # Operating Systems Smart Scheduler Card
        sched_card = ctk.CTkFrame(
            scroll,
            fg_color=self.palette["card"],
            corner_radius=18,
            border_width=1,
            border_color=self.palette["border"],
        )
        sched_card.pack(fill="x", padx=32, pady=(0, 16))

        sc_inner = ctk.CTkFrame(sched_card, fg_color="transparent")
        sc_inner.pack(fill="x", padx=24, pady=20)

        sc_head = ctk.CTkLabel(
            sc_inner,
            text="⚡  Operating System Task Prioritization",
            font=self._font(16, "bold"),
            text_color=self.palette["text"],
            anchor="w",
        )
        sc_head.pack(anchor="w")

        sc_desc = ctk.CTkLabel(
            sc_inner,
            text="Your laptop constantly chooses which application gets processor attention first using CPU scheduling algorithms.",
            font=self._font(13),
            text_color=self.palette["muted"],
            anchor="w",
            wraplength=800,
        )
        sc_desc.pack(anchor="w", pady=(2, 14))

        sched_info_box = ctk.CTkFrame(sc_inner, fg_color=self.palette["card_alt"], corner_radius=12)
        sched_info_box.pack(fill="x", pady=(0, 14))

        self.sched_recommendation_label = ctk.CTkLabel(
            sched_info_box,
            text="Recommended Strategy: Analyzing...",
            font=self._font(15, "bold"),
            text_color=self.palette["text"],
            anchor="w",
        )
        self.sched_recommendation_label.pack(fill="x", padx=16, pady=(12, 2))

        self.sched_reason_label = ctk.CTkLabel(
            sched_info_box,
            text="Analyzing your current active applications...",
            font=self._font(13),
            text_color=self.palette["muted"],
            anchor="w",
            wraplength=760,
        )
        self.sched_reason_label.pack(fill="x", padx=16, pady=(0, 12))

        sched_btn = ctk.CTkButton(
            sc_inner,
            text="📊 View Detailed Scheduler Analysis",
            font=self._font(13, "bold"),
            height=38,
            corner_radius=10,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            command=self._show_scheduler_dialog,
        )
        sched_btn.pack(anchor="w")

        # Safe Process Priority Adjustment Card
        priority_card = ctk.CTkFrame(
            scroll,
            fg_color=self.palette["card"],
            corner_radius=18,
            border_width=1,
            border_color=self.palette["border"],
        )
        priority_card.pack(fill="x", padx=32, pady=(0, 16))

        pc_inner = ctk.CTkFrame(priority_card, fg_color="transparent")
        pc_inner.pack(fill="x", padx=24, pady=20)

        pc_head = ctk.CTkLabel(
            pc_inner,
            text="🛡️  Safe Background Priority Tuning",
            font=self._font(16, "bold"),
            text_color=self.palette["text"],
            anchor="w",
        )
        pc_head.pack(anchor="w")

        pc_desc = ctk.CTkLabel(
            pc_inner,
            text="Lower the workload priority of a busy application so other tasks run smoothly. The application will NEVER be closed or lose data.",
            font=self._font(13),
            text_color=self.palette["muted"],
            anchor="w",
            wraplength=800,
        )
        pc_desc.pack(anchor="w", pady=(2, 14))

        controls_row = ctk.CTkFrame(pc_inner, fg_color="transparent")
        controls_row.pack(fill="x")

        self.opt_proc_values = ["No running processes"]
        self.opt_proc_pids = []
        self.opt_menu = ctk.CTkOptionMenu(
            controls_row,
            values=self.opt_proc_values,
            font=self._font(13),
            width=360,
            height=38,
            corner_radius=10,
            fg_color=self.palette["card_alt"],
            button_color=self.palette["accent"],
            button_hover_color=self.palette["accent_hover"],
            dropdown_font=self._font(13),
        )
        self.opt_menu.pack(side="left")

        opt_btn = ctk.CTkButton(
            controls_row,
            text="⚡ Lower Application Priority",
            font=self._font(13, "bold"),
            height=38,
            corner_radius=10,
            fg_color=self.palette["warning"],
            hover_color=self.palette["critical"],
            command=self._optimize_selected_process,
        )
        opt_btn.pack(side="left", padx=14)

        # Good Laptop Habits List
        habits_card = ctk.CTkFrame(
            scroll,
            fg_color=self.palette["card"],
            corner_radius=18,
            border_width=1,
            border_color=self.palette["border"],
        )
        habits_card.pack(fill="x", padx=32, pady=(0, 24))

        hc_inner = ctk.CTkFrame(habits_card, fg_color="transparent")
        hc_inner.pack(fill="x", padx=24, pady=20)

        hc_head = ctk.CTkLabel(
            hc_inner,
            text="💡  Everyday Laptop Health Tips",
            font=self._font(16, "bold"),
            text_color=self.palette["text"],
            anchor="w",
        )
        hc_head.pack(anchor="w", pady=(0, 8))

        tips = [
            ("🪟", "Close unused browser tabs", "Web browsers keep tabs loaded in memory even when you are not actively looking at them."),
            ("🔌", "Keep your charger handy", "Laptops often run power-saving throttling when the battery drops below 20%."),
            ("🧹", "Free up storage space", "Keep at least 15% of your storage free so the operating system has room to swap memory."),
            ("🛡️", "Never force-close system services", "Operating system processes like kernel and WindowServer keep your display and files safe."),
        ]

        for icon, title, desc in tips:
            row = ctk.CTkFrame(hc_inner, fg_color="transparent")
            row.pack(fill="x", pady=6)
            i_lbl = ctk.CTkLabel(row, text=icon, font=self._font(18))
            i_lbl.pack(side="left", anchor="nw", padx=(0, 10))
            t_box = ctk.CTkFrame(row, fg_color="transparent")
            t_box.pack(side="left", fill="x", expand=True)
            t_lbl = ctk.CTkLabel(t_box, text=title, font=self._font(13, "bold"), text_color=self.palette["text"], anchor="w")
            t_lbl.pack(anchor="w")
            d_lbl = ctk.CTkLabel(t_box, text=desc, font=self._font(12), text_color=self.palette["muted"], anchor="w")
            d_lbl.pack(anchor="w")

    def _update_optimize(self, cpu, ram, battery, processes):
        # 1. Action Cards (only rebuild if recommendations change)
        cards, _ = self.engine.suggestions(cpu, ram, battery, processes)
        card_hash = tuple((c.get("title"), c.get("what"), c.get("why")) for c in cards)

        if getattr(self, "_last_opt_hash", None) != card_hash:
            self._last_opt_hash = card_hash
            for widget in self.opt_cards_container.winfo_children():
                widget.destroy()

            for card in cards:
                c_frame = ctk.CTkFrame(
                    self.opt_cards_container,
                    fg_color=self.palette["card"],
                    corner_radius=16,
                    border_width=1,
                    border_color=self.palette["border"],
                )
                c_frame.pack(fill="x", pady=6)

                inner = ctk.CTkFrame(c_frame, fg_color="transparent")
                inner.pack(fill="x", padx=20, pady=16)

                left = ctk.CTkFrame(inner, fg_color="transparent")
                left.pack(side="left", fill="x", expand=True)

                title_row = ctk.CTkFrame(left, fg_color="transparent")
                title_row.pack(fill="x", pady=(0, 4))

                ic = ctk.CTkLabel(title_row, text=card.get("icon", "🚀"), font=self._font(20))
                ic.pack(side="left", padx=(0, 8))

                t = ctk.CTkLabel(title_row, text=card.get("title", ""), font=self._font(16, "bold"), text_color=self.palette["text"])
                t.pack(side="left")

                w = ctk.CTkLabel(left, text=f"Recommendation: {card.get('what', '')}", font=self._font(13, "bold"), text_color=self.palette["text"], anchor="w")
                w.pack(fill="x")

                y = ctk.CTkLabel(left, text=f"Why? {card.get('why', '')}", font=self._font(12), text_color=self.palette["muted"], anchor="w")
                y.pack(fill="x", pady=(2, 0))

                target = card.get("goto", "monitor")
                btn = ctk.CTkButton(
                    inner,
                    text=card.get("action", "View Details"),
                    font=self._font(13, "bold"),
                    height=36,
                    corner_radius=10,
                    fg_color=self.palette["accent"],
                    hover_color=self.palette["accent_hover"],
                    command=lambda t=target: self._show_page(t),
                )
                btn.pack(side="right", padx=(16, 0))

        # 2. Scheduler info
        top = sorted(processes, key=lambda p: p["cpu"], reverse=True)[:5]
        rec = schmod.recommend_scheduler(top)
        names = {
            "FCFS": "Sequential Scheduling (First-Come First-Served)",
            "SJF": "Shortest Task First (SJF)",
            "PRIORITY": "Resource-Based Priority Scheduling",
        }
        self.sched_recommendation_label.configure(text=f"Recommended Strategy: {names.get(rec, rec)}")
        self.sched_reason_label.configure(text=schmod.scheduler_reason(rec))

        # 3. Process priority candidates
        candidates = sorted(processes, key=lambda p: p["cpu"], reverse=True)[:15]
        self.opt_proc_values = [
            f"{sm.friendly_name(p['name'])} (PID {p['pid']}, CPU: {p['cpu']:.1f}%)" for p in candidates
        ] or ["No running processes"]
        self.opt_proc_pids = [p["pid"] for p in candidates]
        self.opt_menu.configure(values=self.opt_proc_values)
        if self.opt_proc_values:
            current = self.opt_menu.get()
            if current not in self.opt_proc_values:
                self.opt_menu.set(self.opt_proc_values[0])

    def _show_scheduler_dialog(self):
        if not self.snapshot or not self.snapshot.get("processes"):
            messagebox.showinfo("Scheduler Analysis", "System is still gathering workload data. Please try again in a moment.")
            return

        text = schmod.scheduler_analysis_text(self.snapshot["processes"])
        messagebox.showinfo("Operating System Task Scheduling Analysis", text)

    def _optimize_selected_process(self):
        if not self.opt_proc_pids:
            messagebox.showinfo("No Process Selected", "No application is currently available to adjust.")
            return

        selection = self.opt_menu.get()
        try:
            index = self.opt_proc_values.index(selection)
        except ValueError:
            return

        pid = self.opt_proc_pids[index]
        name = f"PID {pid}"
        if self.snapshot:
            for p in self.snapshot.get("processes", []):
                if p["pid"] == pid:
                    name = sm.friendly_name(p["name"])
                    break

        confirmed = messagebox.askyesno(
            "Confirm Workload Adjustment",
            f"Would you like to lower the priority of:\n\n{name} (PID: {pid})\n\n"
            "This gently frees up processor time for your active applications.\n"
            "The application will NOT be closed and no work will be lost.",
        )
        if not confirmed:
            return

        success, msg = schmod.optimize_process(pid)
        if success:
            messagebox.showinfo("Priority Adjusted", msg)
        else:
            messagebox.showwarning("Notice", msg)

    # ==================================================================
    # 4. INSIGHTS PAGE
    # ==================================================================

    def _build_insights(self):
        page = self._new_page()
        self._pages["insights"] = page

        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        self._page_header(
            scroll,
            "Smart Insights",
            "What your laptop has been doing recently, analyzed and explained in plain English.",
            show_back=True,
        )

        self.insights_container = ctk.CTkFrame(scroll, fg_color="transparent")
        self.insights_container.pack(fill="x", padx=32, pady=(0, 24))

    def _update_insights(self):
        history = self.db.recent(120)
        items = self.engine.insights(history)
        insight_hash = tuple((it.get("title"), it.get("text")) for it in items)

        if getattr(self, "_last_insight_hash", None) != insight_hash:
            self._last_insight_hash = insight_hash
            for widget in self.insights_container.winfo_children():
                widget.destroy()

            for item in items:
                card = ctk.CTkFrame(
                    self.insights_container,
                    fg_color=self.palette["card"],
                    corner_radius=16,
                    border_width=1,
                    border_color=self.palette["border"],
                )
                card.pack(fill="x", pady=6)

                inner = ctk.CTkFrame(card, fg_color="transparent")
                inner.pack(fill="x", padx=22, pady=18)

                top = ctk.CTkFrame(inner, fg_color="transparent")
                top.pack(fill="x", pady=(0, 6))

                ic = ctk.CTkLabel(top, text=item.get("icon", "💡"), font=self._font(20))
                ic.pack(side="left", padx=(0, 8))

                t = ctk.CTkLabel(top, text=item.get("title", "Insight"), font=self._font(16, "bold"), text_color=self.palette["text"])
                t.pack(side="left")

                lvl = item.get("level", "good")
                bd = StatusBadge(top, text=lvl.upper(), level=lvl, font_size=10)
                bd.pack(side="right")

                b = ctk.CTkLabel(
                    inner,
                    text=item.get("text", ""),
                    font=self._font(13),
                    text_color=self.palette["muted"],
                    anchor="w",
                    justify="left",
                    wraplength=800,
                )
                b.pack(fill="x")

    # ==================================================================
    # 5. HISTORY PAGE
    # ==================================================================

    def _build_history(self):
        page = self._new_page()
        self._pages["history"] = page

        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        self._page_header(
            scroll,
            "How your laptop has been performing",
            "Continuous historical trends of your processor, memory, battery, and storage.",
            show_back=True,
        )

        # Controls row: Timeframe buttons, Sample count, Clear history
        controls = ctk.CTkFrame(scroll, fg_color="transparent")
        controls.pack(fill="x", padx=32, pady=(0, 14))

        tf_label = ctk.CTkLabel(controls, text="View Range:", font=self._font(13, "bold"), text_color=self.palette["muted"])
        tf_label.pack(side="left", padx=(0, 8))

        self.timeframe_buttons = {}
        for key, label in [("15m", "Last 15 min"), ("30m", "Last 30 min"), ("1h", "Last 1 hour"), ("all", "All recorded")]:
            btn = ctk.CTkButton(
                controls,
                text=label,
                font=self._font(12, "bold"),
                height=32,
                corner_radius=8,
                fg_color=self.palette["accent"] if key == self.history_timeframe else self.palette["card"],
                text_color="#ffffff" if key == self.history_timeframe else self.palette["muted"],
                hover_color=self.palette["accent_hover"],
                command=lambda k=key: self._set_history_timeframe(k),
            )
            btn.pack(side="left", padx=4)
            self.timeframe_buttons[key] = btn

        clear_btn = ctk.CTkButton(
            controls,
            text="🗑 Clear History",
            font=self._font(12, "bold"),
            height=32,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color=self.palette["border"],
            text_color=self.palette["critical"],
            command=self._clear_history,
        )
        clear_btn.pack(side="right")

        refresh_btn = ctk.CTkButton(
            controls,
            text="🔄 Refresh",
            font=self._font(12, "bold"),
            height=32,
            corner_radius=8,
            fg_color=self.palette["sidebar_hl"],
            text_color=self.palette["text"],
            hover_color=self.palette["card"],
            command=self._draw_history,
        )
        refresh_btn.pack(side="right", padx=8)

        self.hist_count_label = ctk.CTkLabel(
            controls, text="", font=self._font(12), text_color=self.palette["muted"]
        )
        self.hist_count_label.pack(side="right", padx=12)

        # Charts Containers
        self.hist_card1 = ctk.CTkFrame(
            scroll, fg_color=self.palette["card"], corner_radius=16, border_width=1, border_color=self.palette["border"]
        )
        self.hist_card1.pack(fill="x", padx=32, pady=(0, 16))

        self.hist_card2 = ctk.CTkFrame(
            scroll, fg_color=self.palette["card"], corner_radius=16, border_width=1, border_color=self.palette["border"]
        )
        self.hist_card2.pack(fill="x", padx=32, pady=(0, 24))

        self.history_canvases = []

    def _set_history_timeframe(self, timeframe):
        self.history_timeframe = timeframe
        for key, btn in self.timeframe_buttons.items():
            if key == timeframe:
                btn.configure(fg_color=self.palette["accent"], text_color="#ffffff")
            else:
                btn.configure(fg_color=self.palette["card"], text_color=self.palette["muted"])
        self._draw_history()

    def _new_figure(self, width, height, title=""):
        fig = Figure(figsize=(width, height), dpi=100, facecolor=self.palette["fig_bg"])
        ax = fig.add_subplot(111)
        fig.subplots_adjust(left=0.07, right=0.97, top=0.88, bottom=0.18)

        ax.set_facecolor(self.palette["fig_bg"])
        for side in ax.spines:
            ax.spines[side].set_color(self.palette["grid"])
        ax.tick_params(colors=self.palette["muted"], labelsize=9)
        ax.xaxis.label.set_color(self.palette["muted"])
        ax.yaxis.label.set_color(self.palette["muted"])
        if title:
            ax.set_title(title, color=self.palette["text"], fontsize=12, fontweight="bold", pad=8, loc="left")
        ax.grid(True, color=self.palette["grid"], linewidth=0.6, alpha=0.6)
        return fig, ax

    def _draw_history(self):
        for widget in self.history_canvases:
            try:
                widget.destroy()
            except Exception:
                pass
        self.history_canvases = []

        rows = self.db.get_history(self.history_timeframe)
        total_count = self.db.count()
        self.hist_count_label.configure(text=f"Showing {len(rows)} of {total_count} recorded samples")

        if len(rows) < 2:
            lbl = ctk.CTkLabel(
                self.hist_card1,
                text="Not enough historical data recorded yet. Leave the app open to collect telemetry.",
                font=self._font(13),
                text_color=self.palette["muted"],
            )
            lbl.pack(padx=20, pady=30)
            self.history_canvases.append(lbl)
            return

        base_time = rows[0]["timestamp"]
        elapsed_min = [(r["timestamp"] - base_time) / 60.0 for r in rows]
        cpus = [r["cpu"] for r in rows]
        rams = [r["ram"] for r in rows]
        disks = [r["disk"] for r in rows]
        batteries = [r["battery"] for r in rows]

        # Chart 1: Processor & Memory
        fig1, ax1 = self._new_figure(8.0, 2.6, "Processor (CPU) & Memory (RAM) History")
        ax1.plot(elapsed_min, cpus, color=self.palette["healthy"], linewidth=2.0, label="Processor (CPU %)")
        ax1.plot(elapsed_min, rams, color=self.palette["accent"], linewidth=2.0, label="Memory (RAM %)")
        ax1.axhline(70, color=self.palette["warning"], linestyle="--", linewidth=0.8, alpha=0.5, label="Attention (70%)")
        ax1.axhline(90, color=self.palette["critical"], linestyle="--", linewidth=0.8, alpha=0.5, label="High Load (90%)")
        ax1.set_ylim(0, 105)
        ax1.set_xlabel("Elapsed Time (Minutes)")
        ax1.set_ylabel("Usage (%)")
        ax1.legend(loc="upper right", frameon=False, labelcolor=self.palette["muted"], fontsize=9)

        canv1 = FigureCanvasTkAgg(fig1, master=self.hist_card1)
        w1 = canv1.get_tk_widget()
        w1.configure(bg=self.palette["fig_bg"])
        w1.pack(fill="both", expand=True, padx=14, pady=14)
        self.history_canvases.append(w1)

        # Chart 2: Battery & Storage
        has_battery = any(b is not None for b in batteries)
        fig2, ax2 = self._new_figure(8.0, 2.6, "Battery Level & Storage Capacity History")
        ax2.plot(elapsed_min, disks, color=self.palette["warning"], linewidth=2.0, label="Storage Used (%)")
        if has_battery:
            plot_bat = [b if b is not None else float("nan") for b in batteries]
            ax2.plot(elapsed_min, plot_bat, color=self.palette["healthy"], linewidth=2.0, label="Battery (%)")
        ax2.set_ylim(0, 105)
        ax2.set_xlabel("Elapsed Time (Minutes)")
        ax2.set_ylabel("Percentage (%)")
        ax2.legend(loc="upper right", frameon=False, labelcolor=self.palette["muted"], fontsize=9)

        canv2 = FigureCanvasTkAgg(fig2, master=self.hist_card2)
        w2 = canv2.get_tk_widget()
        w2.configure(bg=self.palette["fig_bg"])
        w2.pack(fill="both", expand=True, padx=14, pady=14)
        self.history_canvases.append(w2)

    def _clear_history(self):
        confirmed = messagebox.askyesno(
            "Clear Performance History",
            "Are you sure you want to delete all recorded performance samples?\n\nThis action cannot be undone.",
        )
        if not confirmed:
            return
        self.db.clear()
        self._draw_history()

    # ==================================================================
    # 6. SETTINGS PAGE
    # ==================================================================

    def _build_settings(self):
        page = self._new_page()
        self._pages["settings"] = page

        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        self._page_header(
            scroll,
            "Settings",
            "Adjust monitoring speed, appearance, and application preferences.",
            show_back=True,
        )

        card = ctk.CTkFrame(
            scroll,
            fg_color=self.palette["card"],
            corner_radius=18,
            border_width=1,
            border_color=self.palette["border"],
        )
        card.pack(fill="x", padx=32, pady=(0, 24))

        block = ctk.CTkFrame(card, fg_color="transparent")
        block.pack(fill="x", padx=24, pady=20)
        block.grid_columnconfigure(0, weight=1)

        def add_setting_item(row, title, subtitle):
            row_frame = ctk.CTkFrame(block, fg_color="transparent")
            row_frame.grid(row=row, column=0, sticky="ew", pady=12)
            row_frame.grid_columnconfigure(0, weight=1)

            t_box = ctk.CTkFrame(row_frame, fg_color="transparent")
            t_box.grid(row=0, column=0, sticky="w")

            t = ctk.CTkLabel(t_box, text=title, font=self._font(14, "bold"), text_color=self.palette["text"], anchor="w")
            t.pack(anchor="w")

            s = ctk.CTkLabel(t_box, text=subtitle, font=self._font(12), text_color=self.palette["muted"], anchor="w")
            s.pack(anchor="w", pady=(1, 0))

            ctrl = ctk.CTkFrame(row_frame, fg_color="transparent")
            ctrl.grid(row=0, column=1, sticky="e")
            return ctrl

        # 1. Update frequency
        ctrl1 = add_setting_item(0, "How often should the app update?", "Faster updates use slightly more resources; slower updates save battery.")
        interval_ms = int(self.settings.get("refresh_ms", "1000"))
        self.interval_menu = ctk.CTkOptionMenu(
            ctrl1,
            values=["1 second", "2 seconds", "3 seconds", "5 seconds"],
            font=self._font(13),
            width=150,
            height=34,
            corner_radius=8,
            fg_color=self.palette["card_alt"],
            button_color=self.palette["accent"],
            button_hover_color=self.palette["accent_hover"],
            command=self._on_interval_changed,
        )
        cur_sec = max(1, interval_ms // 1000)
        self.interval_menu.set(f"{cur_sec} second" if cur_sec == 1 else f"{cur_sec} seconds")
        self.interval_menu.pack()

        # 2. Appearance
        ctrl2 = add_setting_item(1, "Appearance Mode", "Switch between sleek dark theme and crisp light theme.")
        self.theme_segment = ctk.CTkSegmentedButton(
            ctrl2,
            values=["Dark", "Light"],
            font=self._font(13),
            height=34,
            corner_radius=8,
            fg_color=self.palette["card_alt"],
            selected_color=self.palette["accent"],
            selected_hover_color=self.palette["accent_hover"],
            command=self._on_theme_changed,
        )
        self.theme_segment.set("Dark" if self.appearance_mode == "dark" else "Light")
        self.theme_segment.pack()

        # 3. Autostart monitoring
        ctrl3 = add_setting_item(2, "Monitor Continuously", "Automatically collect health metrics while this application is open.")
        self.autostart_switch = ctk.CTkSwitch(
            ctrl3,
            text="",
            progress_color=self.palette["accent"],
            button_color=self.palette["accent"],
            button_hover_color=self.palette["accent_hover"],
            command=self._on_autostart_changed,
        )
        if self.settings.get("autostart") == "1":
            self.autostart_switch.select()
        self.autostart_switch.pack()

        # 4. Clear data
        ctrl4 = add_setting_item(3, "Performance History Storage", "Erase all recorded telemetry stored locally on your laptop.")
        del_btn = ctk.CTkButton(
            ctrl4,
            text="Erase All Data",
            font=self._font(12, "bold"),
            height=34,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color=self.palette["border"],
            text_color=self.palette["critical"],
            command=self._clear_history,
        )
        del_btn.pack()

        # Privacy assurance note
        priv_card = ctk.CTkFrame(card, fg_color=self.palette["card_alt"], corner_radius=12)
        priv_card.pack(fill="x", padx=24, pady=(10, 20))

        priv_lbl = ctk.CTkLabel(
            priv_card,
            text="🔒 100% Private & Safe: All monitoring data is analyzed locally and stored on your laptop. No data is ever sent to the cloud.",
            font=self._font(12),
            text_color=self.palette["muted"],
            anchor="w",
            wraplength=760,
        )
        priv_lbl.pack(padx=16, pady=12)

    def _on_interval_changed(self, value):
        seconds = int(value.split()[0])
        ms = seconds * 1000
        self.settings["refresh_ms"] = str(ms)
        self.db.set_setting("refresh_ms", ms)
        self._schedule_loop()

    def _on_theme_changed(self, value):
        theme = value.lower()
        self.settings["theme"] = theme
        self.db.set_setting("theme", theme)
        self._apply_theme()

    def _on_autostart_changed(self):
        enabled = bool(self.autostart_switch.get())
        self.settings["autostart"] = "1" if enabled else "0"
        self.db.set_setting("autostart", self.settings["autostart"])
        if enabled:
            self._schedule_loop()
        else:
            if self.after_id is not None:
                self.after_cancel(self.after_id)
                self.after_id = None

    # ==================================================================
    # REFRESH & TICK CYCLE
    # ==================================================================

    def _bootstrap(self):
        if self.closing:
            return
        try:
            self.refresh()
        except Exception:
            pass
        self._schedule_loop()

    def _schedule_loop(self):
        if self.after_id is not None:
            try:
                self.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None

        if self.closing:
            return

        if self.settings.get("autostart") == "1":
            interval = int(self.settings.get("refresh_ms", "1000"))
            self.after_id = self.after(interval, self._tick)

    def _tick(self):
        self.after_id = None
        if self.closing:
            return
        try:
            self.refresh()
        except Exception:
            pass
        self._schedule_loop()

    def refresh(self):
        """Fetch fresh system telemetry and update pages."""
        snapshot = self.monitor.snapshot()
        self.snapshot = snapshot
        self.has_initial_data = True

        cpu = snapshot["cpu"]
        ram = snapshot["ram"]["percent"]
        disk = snapshot["disk"]["percent"]
        battery = snapshot["battery"]
        battery_percent = battery["percent"] if battery else None
        processes = snapshot["processes"]

        # Record snapshot in SQLite every 2 ticks to keep disk I/O light
        self.tick_counter = getattr(self, "tick_counter", 0) + 1
        if self.tick_counter % 2 == 0:
            try:
                self.db.record(cpu, ram, battery_percent, disk)
            except Exception:
                pass

        # Update ONLY the active page to keep performance silky smooth and responsive
        if self.current_page == "home":
            self._update_home(snapshot)
        elif self.current_page == "monitor":
            self._update_monitor(snapshot)
        elif self.current_page == "optimize":
            self._update_optimize(cpu, ram, battery, processes)
        elif self.current_page == "insights":
            self._update_insights()

    # ==================================================================
    # CLOSE
    # ==================================================================

    def _on_close(self):
        self.closing = True
        if self.after_id is not None:
            try:
                self.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None
        self.db.close()
        try:
            self.quit()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass


def main():
    app = SmartOptimizerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
