"""
=============================================================================
  ARENA-STYLE GUI — Kidney Transplant Simulation
=============================================================================
  Tkinter-based graphical interface that mimics the Arena Simulation
  Software look-and-feel:
    - Toolbar with Run / Pause / Reset / Speed controls
    - Model flowchart canvas (Arena workspace)
    - Tabbed output viewer (Reports, Plots, Live Stats)
    - Run Setup dialog for parameters
    - Status bar with simulation clock and progress
=============================================================================

  Usage:
    python gui.py

=============================================================================
"""

import os
import sys
import time
import random
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from PIL import Image, ImageTk
import simpy

# ── Project imports ──
from config import (
    SIM_DURATION, NUM_REPLICATIONS, RANDOM_SEED_BASE, WARM_UP_PERIOD,
    KIDNEY_ARRIVAL_RATE, PATIENT_ARRIVAL_RATE, LIVING_DONOR_RATE,
    MAX_COLD_ISCHEMIA_TIME, QUALITY_DECAY_RATE,
    NUM_OPERATING_ROOMS, NUM_SURGICAL_TEAMS,
    NUM_TRANSPORT_VEHICLES, NUM_CROSSMATCH_LABS,
)
from simulation import KidneyTransplantSimulation
from statistics_collector import StatisticsCollector, ReplicationCollector
from visualization import generate_all_plots, plot_replication_comparison

# ─── Color Scheme (Arena-inspired) ──────────────────────────────────────
ARENA_BG          = "#E8EAF0"
ARENA_DARK        = "#2C3E50"
ARENA_TOOLBAR_BG  = "#34495E"
ARENA_ACCENT      = "#2980B9"
ARENA_SUCCESS     = "#27AE60"
ARENA_DANGER      = "#E74C3C"
ARENA_WARNING     = "#F39C12"
ARENA_TEXT        = "#ECF0F1"
ARENA_CANVAS_BG   = "#FFFFFF"
ARENA_SIDEBAR_BG  = "#F0F2F5"
ARENA_BORDER      = "#BDC3C7"
FLOWCHART_GREEN   = "#A8E6A3"
FLOWCHART_BLUE    = "#90CAF9"
FLOWCHART_ORANGE  = "#FFE0B2"
FLOWCHART_PURPLE  = "#CE93D8"
FLOWCHART_YELLOW  = "#FFF9C4"
FLOWCHART_RED     = "#EF9A9A"


class ArenaGUI(tk.Tk):
    """Main Arena-style simulation GUI window."""

    def __init__(self):
        super().__init__()

        self.title("Arena Simulation - Kidney Transplant Logistics & Perishable Queueing")
        self.state("zoomed")               # full-screen on Windows
        self.configure(bg=ARENA_BG)
        self.minsize(1200, 750)

        # ── State ──
        self.sim_thread = None
        self.is_running = False
        self.is_paused  = False
        self.current_stats: StatisticsCollector | None = None
        self.rep_collector = ReplicationCollector()
        self.all_stats: list[StatisticsCollector] = []
        self.output_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(self.output_dir, exist_ok=True)

        # ── Simulation parameters (Arena Run > Setup) ──
        self.param_reps      = tk.IntVar(value=NUM_REPLICATIONS)
        self.param_duration  = tk.DoubleVar(value=SIM_DURATION)
        self.param_warmup    = tk.DoubleVar(value=WARM_UP_PERIOD)
        self.param_seed      = tk.IntVar(value=RANDOM_SEED_BASE)
        self.param_verbose   = tk.BooleanVar(value=False)
        self.param_speed     = tk.DoubleVar(value=1.0)

        # Resource params
        self.param_num_or    = tk.IntVar(value=NUM_OPERATING_ROOMS)
        self.param_num_teams = tk.IntVar(value=NUM_SURGICAL_TEAMS)
        self.param_num_transport = tk.IntVar(value=NUM_TRANSPORT_VEHICLES)
        self.param_num_labs  = tk.IntVar(value=NUM_CROSSMATCH_LABS)

        # Arrival rate params
        self.param_kidney_rate  = tk.DoubleVar(value=KIDNEY_ARRIVAL_RATE)
        self.param_patient_rate = tk.DoubleVar(value=PATIENT_ARRIVAL_RATE)
        self.param_living_rate  = tk.DoubleVar(value=LIVING_DONOR_RATE)

        # Perishability
        self.param_max_ischemia = tk.DoubleVar(value=MAX_COLD_ISCHEMIA_TIME)
        self.param_decay_rate   = tk.DoubleVar(value=QUALITY_DECAY_RATE)

        # ── Build GUI ──
        self._build_menu_bar()
        self._build_toolbar()
        self._build_main_content()
        self._build_status_bar()

        # Draw the initial flowchart
        self.after(100, self._draw_flowchart)

    # ===================================================================
    #  MENU BAR
    # ===================================================================

    def _build_menu_bar(self):
        menubar = tk.Menu(self, bg=ARENA_TOOLBAR_BG, fg=ARENA_TEXT)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Output Folder", command=self._open_output_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Export Report...", command=self._export_report)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # Run menu
        run_menu = tk.Menu(menubar, tearoff=0)
        run_menu.add_command(label="Start Simulation", command=self._start_simulation,
                            accelerator="F5")
        run_menu.add_command(label="Reset", command=self._reset_simulation,
                            accelerator="F6")
        run_menu.add_separator()
        run_menu.add_command(label="Run Setup...", command=self._show_run_setup,
                            accelerator="Ctrl+Shift+S")
        menubar.add_cascade(label="Run", menu=run_menu)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Dashboard", command=lambda: self._show_plot_tab("Dashboard"))
        view_menu.add_command(label="Flowchart", command=lambda: self.output_tabs.select(0))
        view_menu.add_command(label="Reports", command=lambda: self.output_tabs.select(1))
        view_menu.add_command(label="Plots", command=lambda: self.output_tabs.select(2))
        menubar.add_cascade(label="View", menu=view_menu)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

        # Keyboard bindings
        self.bind("<F5>", lambda e: self._start_simulation())
        self.bind("<F6>", lambda e: self._reset_simulation())

    # ===================================================================
    #  TOOLBAR (Arena-style Run ribbon)
    # ===================================================================

    def _build_toolbar(self):
        toolbar = tk.Frame(self, bg=ARENA_TOOLBAR_BG, height=56, relief=tk.FLAT)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        toolbar.pack_propagate(False)

        # ── Left: Simulation controls ──
        ctrl_frame = tk.Frame(toolbar, bg=ARENA_TOOLBAR_BG)
        ctrl_frame.pack(side=tk.LEFT, padx=10)

        btn_style = {"font": ("Segoe UI", 10, "bold"), "relief": tk.FLAT,
                     "bd": 0, "padx": 14, "pady": 6, "cursor": "hand2"}

        self.btn_start = tk.Button(
            ctrl_frame, text="\u25B6  Run", bg=ARENA_SUCCESS, fg="white",
            command=self._start_simulation,
            activebackground="#2ECC71", **btn_style
        )
        self.btn_start.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_reset = tk.Button(
            ctrl_frame, text="\u21BB  Reset", bg=ARENA_DANGER, fg="white",
            command=self._reset_simulation,
            activebackground="#E74C3C", **btn_style
        )
        self.btn_reset.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_setup = tk.Button(
            ctrl_frame, text="\u2699  Setup", bg=ARENA_ACCENT, fg="white",
            command=self._show_run_setup,
            activebackground="#3498DB", **btn_style
        )
        self.btn_setup.pack(side=tk.LEFT, padx=(0, 4))

        # ── Separator ──
        sep = tk.Frame(toolbar, bg=ARENA_BORDER, width=2, height=36)
        sep.pack(side=tk.LEFT, padx=12, pady=8)

        # ── Middle: Quick config ──
        quick_frame = tk.Frame(toolbar, bg=ARENA_TOOLBAR_BG)
        quick_frame.pack(side=tk.LEFT, padx=6)

        tk.Label(quick_frame, text="Replications:", bg=ARENA_TOOLBAR_BG,
                 fg=ARENA_TEXT, font=("Segoe UI", 9)).pack(side=tk.LEFT)
        spin_reps = tk.Spinbox(quick_frame, from_=1, to=100, width=4,
                               textvariable=self.param_reps,
                               font=("Segoe UI", 10), justify=tk.CENTER)
        spin_reps.pack(side=tk.LEFT, padx=(2, 12))

        tk.Label(quick_frame, text="Duration (days):", bg=ARENA_TOOLBAR_BG,
                 fg=ARENA_TEXT, font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.duration_days_var = tk.DoubleVar(value=SIM_DURATION / 24.0)
        spin_dur = tk.Spinbox(quick_frame, from_=1, to=3650, width=5,
                              textvariable=self.duration_days_var,
                              font=("Segoe UI", 10), justify=tk.CENTER,
                              command=self._sync_duration)
        spin_dur.pack(side=tk.LEFT, padx=(2, 12))

        tk.Label(quick_frame, text="Seed:", bg=ARENA_TOOLBAR_BG,
                 fg=ARENA_TEXT, font=("Segoe UI", 9)).pack(side=tk.LEFT)
        spin_seed = tk.Spinbox(quick_frame, from_=1, to=99999, width=6,
                               textvariable=self.param_seed,
                               font=("Segoe UI", 10), justify=tk.CENTER)
        spin_seed.pack(side=tk.LEFT, padx=(2, 0))

        # ── Right: Title / Logo ──
        title_frame = tk.Frame(toolbar, bg=ARENA_TOOLBAR_BG)
        title_frame.pack(side=tk.RIGHT, padx=14)
        tk.Label(title_frame, text="Kidney Transplant Logistics",
                 bg=ARENA_TOOLBAR_BG, fg=ARENA_TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor=tk.E)
        tk.Label(title_frame, text="Perishable Queueing Simulation  |  Arena-Style DES",
                 bg=ARENA_TOOLBAR_BG, fg="#95A5A6",
                 font=("Segoe UI", 8)).pack(anchor=tk.E)

    # ===================================================================
    #  MAIN CONTENT — Sidebar + Tabbed Center
    # ===================================================================

    def _build_main_content(self):
        main_pane = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=ARENA_BG,
                                   sashwidth=4, sashrelief=tk.FLAT)
        main_pane.pack(fill=tk.BOTH, expand=True)

        # ── Left sidebar: Live counters ──
        sidebar = tk.Frame(main_pane, bg=ARENA_SIDEBAR_BG, width=270)
        main_pane.add(sidebar, minsize=250)
        self._build_sidebar(sidebar)

        # ── Center: Tabbed output area ──
        center = tk.Frame(main_pane, bg=ARENA_BG)
        main_pane.add(center, minsize=700)
        self._build_tabs(center)

    def _build_sidebar(self, parent):
        """Build the left panel with live counters and entity snapshot."""
        # Header
        header = tk.Frame(parent, bg=ARENA_DARK, height=36)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="  LIVE STATISTICS", bg=ARENA_DARK, fg=ARENA_TEXT,
                 font=("Segoe UI", 10, "bold"), anchor=tk.W).pack(fill=tk.X, pady=6, padx=8)

        # Scrollable counters
        canvas = tk.Canvas(parent, bg=ARENA_SIDEBAR_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        self.sidebar_inner = tk.Frame(canvas, bg=ARENA_SIDEBAR_BG)

        self.sidebar_inner.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.sidebar_inner, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # ── Counter labels ──
        self.counter_labels = {}
        self._add_sidebar_section("Entity Counters")
        counter_defs = [
            ("kidneys_arrived",   "Kidneys Arrived",       "0"),
            ("patients_arrived",  "Patients Arrived",      "0"),
            ("transplants",       "Successful Transplants", "0"),
            ("failed",            "Failed (Rejection)",     "0"),
            ("expired",           "Organs Expired",         "0"),
            ("no_match",          "No Compatible Match",    "0"),
            ("died_waiting",      "Died on Waitlist",       "0"),
            ("transferred",       "Transferred Out",        "0"),
        ]
        for key, label, default in counter_defs:
            self._add_sidebar_counter(key, label, default)

        self._add_sidebar_section("Queue Lengths")
        queue_defs = [
            ("waitlist_len", "Waitlist Length",    "0"),
            ("organ_pool",   "Organ Pool Size",    "0"),
        ]
        for key, label, default in queue_defs:
            self._add_sidebar_counter(key, label, default)

        self._add_sidebar_section("Resource Utilization")
        res_defs = [
            ("or_util",       "Operating Rooms",   "0.0%"),
            ("team_util",     "Surgical Teams",    "0.0%"),
            ("transport_util","Transport Vehicles", "0.0%"),
            ("lab_util",      "Crossmatch Labs",   "0.0%"),
        ]
        for key, label, default in res_defs:
            self._add_sidebar_counter(key, label, default)

        self._add_sidebar_section("Key Performance")
        kpi_defs = [
            ("util_rate",     "Organ Utilization %", "--"),
            ("waste_rate",    "Organ Waste %",       "--"),
            ("avg_wait",      "Avg Wait (days)",     "--"),
            ("avg_cit",       "Avg CIT (hrs)",       "--"),
            ("avg_quality",   "Avg Quality",         "--"),
        ]
        for key, label, default in kpi_defs:
            self._add_sidebar_counter(key, label, default)

    def _add_sidebar_section(self, title):
        frm = tk.Frame(self.sidebar_inner, bg=ARENA_SIDEBAR_BG)
        frm.pack(fill=tk.X, padx=8, pady=(12, 2))
        tk.Label(frm, text=title.upper(), bg=ARENA_SIDEBAR_BG,
                 fg=ARENA_DARK, font=("Segoe UI", 8, "bold")).pack(anchor=tk.W)
        ttk.Separator(frm, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=2)

    def _add_sidebar_counter(self, key, label, default):
        frm = tk.Frame(self.sidebar_inner, bg=ARENA_SIDEBAR_BG)
        frm.pack(fill=tk.X, padx=12, pady=1)
        tk.Label(frm, text=label, bg=ARENA_SIDEBAR_BG, fg="#555",
                 font=("Segoe UI", 9), anchor=tk.W).pack(side=tk.LEFT)
        val_lbl = tk.Label(frm, text=default, bg=ARENA_SIDEBAR_BG, fg=ARENA_DARK,
                           font=("Segoe UI", 10, "bold"), anchor=tk.E)
        val_lbl.pack(side=tk.RIGHT)
        self.counter_labels[key] = val_lbl

    # ===================================================================
    #  OUTPUT TABS
    # ===================================================================

    def _build_tabs(self, parent):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Arena.TNotebook", background=ARENA_BG)
        style.configure("Arena.TNotebook.Tab", font=("Segoe UI", 10, "bold"),
                        padding=[14, 6], background=ARENA_SIDEBAR_BG)
        style.map("Arena.TNotebook.Tab",
                  background=[("selected", ARENA_ACCENT)],
                  foreground=[("selected", "white")])

        self.output_tabs = ttk.Notebook(parent, style="Arena.TNotebook")
        self.output_tabs.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Tab 0: Flowchart / Model View
        self.flowchart_frame = tk.Frame(self.output_tabs, bg=ARENA_CANVAS_BG)
        self.output_tabs.add(self.flowchart_frame, text="  Model Flowchart  ")
        self._build_flowchart_tab()

        # Tab 1: Reports
        self.report_frame = tk.Frame(self.output_tabs, bg=ARENA_BG)
        self.output_tabs.add(self.report_frame, text="  Reports  ")
        self._build_report_tab()

        # Tab 2: Plots Gallery
        self.plots_frame = tk.Frame(self.output_tabs, bg=ARENA_BG)
        self.output_tabs.add(self.plots_frame, text="  Plots / Charts  ")
        self._build_plots_tab()

        # Tab 3: Console Log
        self.console_frame = tk.Frame(self.output_tabs, bg="#1E1E1E")
        self.output_tabs.add(self.console_frame, text="  Console Log  ")
        self._build_console_tab()

    # ── Tab 0: Flowchart ──

    def _build_flowchart_tab(self):
        # Top bar
        top = tk.Frame(self.flowchart_frame, bg=ARENA_SIDEBAR_BG, height=32)
        top.pack(fill=tk.X)
        top.pack_propagate(False)
        tk.Label(top, text="  Arena-Style Model Flowchart", bg=ARENA_SIDEBAR_BG,
                 fg=ARENA_DARK, font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, pady=4)

        # Canvas with scrollbars
        h_scroll = ttk.Scrollbar(self.flowchart_frame, orient=tk.HORIZONTAL)
        v_scroll = ttk.Scrollbar(self.flowchart_frame, orient=tk.VERTICAL)
        self.fc_canvas = tk.Canvas(
            self.flowchart_frame, bg=ARENA_CANVAS_BG,
            xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set,
            highlightthickness=0
        )
        h_scroll.config(command=self.fc_canvas.xview)
        v_scroll.config(command=self.fc_canvas.yview)

        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.fc_canvas.pack(fill=tk.BOTH, expand=True)

    # ── Tab 1: Reports ──

    def _build_report_tab(self):
        top = tk.Frame(self.report_frame, bg=ARENA_SIDEBAR_BG, height=40)
        top.pack(fill=tk.X)
        top.pack_propagate(False)
        tk.Label(top, text="  Simulation Report Output (Arena-Style)",
                 bg=ARENA_SIDEBAR_BG, fg=ARENA_DARK,
                 font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, pady=6)

        self.report_selector = ttk.Combobox(top, state="readonly", width=40,
                                            font=("Segoe UI", 9))
        self.report_selector.pack(side=tk.RIGHT, padx=10, pady=6)
        self.report_selector.bind("<<ComboboxSelected>>", self._on_report_selected)

        self.report_text = scrolledtext.ScrolledText(
            self.report_frame, font=("Consolas", 10), bg="#1E1E1E", fg="#D4D4D4",
            insertbackground="white", wrap=tk.NONE, padx=10, pady=10
        )
        self.report_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

    # ── Tab 2: Plots Gallery ──

    def _build_plots_tab(self):
        top = tk.Frame(self.plots_frame, bg=ARENA_SIDEBAR_BG, height=40)
        top.pack(fill=tk.X)
        top.pack_propagate(False)
        tk.Label(top, text="  Visualization Gallery (click to enlarge)",
                 bg=ARENA_SIDEBAR_BG, fg=ARENA_DARK,
                 font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, pady=6)

        self.plot_selector = ttk.Combobox(top, state="readonly", width=40,
                                          font=("Segoe UI", 9))
        self.plot_selector.pack(side=tk.RIGHT, padx=10, pady=6)
        self.plot_selector.bind("<<ComboboxSelected>>", self._on_plot_selected)

        # Image display area
        self.plot_canvas = tk.Canvas(self.plots_frame, bg=ARENA_CANVAS_BG,
                                     highlightthickness=0)
        self.plot_canvas.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
        self._current_photo = None  # prevent GC

    # ── Tab 3: Console Log ──

    def _build_console_tab(self):
        self.console_text = scrolledtext.ScrolledText(
            self.console_frame, font=("Consolas", 9), bg="#1E1E1E", fg="#00FF00",
            insertbackground="#00FF00", wrap=tk.WORD, padx=10, pady=10
        )
        self.console_text.pack(fill=tk.BOTH, expand=True)
        self._console_log("Arena Simulation Engine initialized.")
        self._console_log("Press [Run] or F5 to start the simulation.")

    # ===================================================================
    #  STATUS BAR
    # ===================================================================

    def _build_status_bar(self):
        status_bar = tk.Frame(self, bg=ARENA_DARK, height=28)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        status_bar.pack_propagate(False)

        self.status_label = tk.Label(status_bar, text="  Ready", bg=ARENA_DARK,
                                     fg=ARENA_TEXT, font=("Segoe UI", 9),
                                     anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, padx=8)

        self.clock_label = tk.Label(status_bar, text="Sim Clock: 0.0 hrs (Day 0)",
                                    bg=ARENA_DARK, fg="#95A5A6",
                                    font=("Segoe UI", 9))
        self.clock_label.pack(side=tk.RIGHT, padx=14)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            status_bar, variable=self.progress_var, maximum=100, length=220,
            mode="determinate"
        )
        self.progress_bar.pack(side=tk.RIGHT, padx=8, pady=4)

        self.rep_label = tk.Label(status_bar, text="Rep: --/--", bg=ARENA_DARK,
                                  fg="#95A5A6", font=("Segoe UI", 9))
        self.rep_label.pack(side=tk.RIGHT, padx=8)

    # ===================================================================
    #  FLOWCHART DRAWING (Arena Workspace Canvas)
    # ===================================================================

    def _draw_flowchart(self):
        c = self.fc_canvas
        c.delete("all")

        # Grid settings
        bw, bh = 130, 55          # box size
        dw = 70                    # diamond size
        gap_x, gap_y = 50, 30     # spacing
        x0, y0 = 40, 40           # origin

        def box(x, y, text, color, tag=""):
            c.create_rectangle(x, y, x + bw, y + bh, fill=color,
                               outline="#555", width=2, tags=tag)
            c.create_text(x + bw/2, y + bh/2, text=text,
                          font=("Segoe UI", 8, "bold"), width=bw - 10, tags=tag)

        def diamond(x, y, text, tag=""):
            cx, cy = x + dw/2, y + dw/2
            pts = [cx, y, x + dw, cy, cx, y + dw, x, cy]
            c.create_polygon(pts, fill=FLOWCHART_YELLOW, outline="#555", width=2, tags=tag)
            c.create_text(cx, cy, text=text, font=("Segoe UI", 7, "bold"),
                          width=dw - 8, tags=tag)

        def arrow(x1, y1, x2, y2, label="", color="black"):
            c.create_line(x1, y1, x2, y2, arrow=tk.LAST, fill=color, width=2)
            if label:
                mx, my = (x1 + x2)/2, (y1 + y2)/2
                c.create_text(mx, my - 8, text=label,
                              font=("Segoe UI", 7, "bold"), fill=ARENA_DANGER)

        # ─────────── ROW 1: KIDNEY PATH ──────────────
        row1_y = y0
        title_y = row1_y - 5
        c.create_text(x0, title_y, text="KIDNEY ORGAN PATH", anchor=tk.NW,
                      font=("Segoe UI", 11, "bold"), fill=ARENA_DARK)
        row1_y += 25

        col = x0
        box(col, row1_y, "CREATE\nKidney\nArrivals", FLOWCHART_GREEN, "k_create")
        k1_r = col + bw
        col += bw + gap_x

        box(col, row1_y, "ASSIGN\nBlood Type\nHLA / Zone", FLOWCHART_BLUE, "k_assign")
        k2_r = col + bw
        col += bw + gap_x

        dx = col
        diamond(col, row1_y - 8, "Match\nFound?", "k_decide_match")
        k3_r = col + dw
        col += dw + gap_x

        box(col, row1_y, "PROCESS\nCrossmatch\nLab", FLOWCHART_ORANGE, "k_crossmatch")
        k4_r = col + bw
        col += bw + gap_x

        dx2 = col
        diamond(col, row1_y - 8, "XMatch\nPass?", "k_decide_xm")
        k5_r = col + dw
        col += dw + gap_x

        box(col, row1_y, "PROCESS\nTransport\nVehicle", FLOWCHART_ORANGE, "k_transport")
        k6_r = col + bw
        col += bw + gap_x

        dx3 = col
        diamond(col, row1_y - 8, "Still\nViable?", "k_decide_viable")
        k7_r = col + dw
        col += dw + gap_x

        box(col, row1_y, "PROCESS\nSurgery\n(OR + Team)", FLOWCHART_ORANGE, "k_surgery")
        k8_r = col + bw
        col += bw + gap_x

        dx4 = col
        diamond(col, row1_y - 8, "Graft\nSuccess?", "k_decide_graft")
        k9_r = col + dw
        col += dw + gap_x

        box(col, row1_y, "DISPOSE\nSuccessful\nTransplant!", FLOWCHART_GREEN, "k_dispose_ok")

        # Arrows along kidney path
        arrow(k1_r, row1_y + bh/2, k1_r + gap_x, row1_y + bh/2)
        arrow(k2_r, row1_y + bh/2, k2_r + gap_x, row1_y + bh/2)
        arrow(k3_r, row1_y + bh/2 - 8, k3_r + gap_x, row1_y + bh/2, "Yes")
        arrow(k4_r, row1_y + bh/2, k4_r + gap_x, row1_y + bh/2)
        arrow(k5_r, row1_y + bh/2 - 8, k5_r + gap_x, row1_y + bh/2, "Yes")
        arrow(k6_r, row1_y + bh/2, k6_r + gap_x, row1_y + bh/2)
        arrow(k7_r, row1_y + bh/2 - 8, k7_r + gap_x, row1_y + bh/2, "Yes")
        arrow(k8_r, row1_y + bh/2, k8_r + gap_x, row1_y + bh/2)
        arrow(k9_r, row1_y + bh/2 - 8, k9_r + gap_x, row1_y + bh/2, "Yes")

        # ─────────── ROW 2: REJECT / DISPOSE OUTPUTS ──────────────
        row2_y = row1_y + bh + gap_y + 30

        # No Match → Organ Pool
        pool_x = dx
        box(pool_x, row2_y, "HOLD\nOrgan Pool\n(Wait)", FLOWCHART_PURPLE)
        arrow(dx + dw/2, row1_y + dw - 8, pool_x + bw/2, row2_y, "No")

        # XMatch Fail → Dispose
        xm_fail_x = dx2
        box(xm_fail_x, row2_y, "DISPOSE\nCrossmatch\nFailed", FLOWCHART_RED)
        arrow(dx2 + dw/2, row1_y + dw - 8, xm_fail_x + bw/2, row2_y, "No")

        # Not Viable → Expired
        exp_x = dx3
        box(exp_x, row2_y, "DISPOSE\nOrgan\nExpired", FLOWCHART_RED)
        arrow(dx3 + dw/2, row1_y + dw - 8, exp_x + bw/2, row2_y, "No")

        # Graft Fail → Rejection
        rej_x = dx4
        box(rej_x, row2_y, "DISPOSE\nGraft\nRejection", FLOWCHART_RED)
        arrow(dx4 + dw/2, row1_y + dw - 8, rej_x + bw/2, row2_y, "No")

        # ─────────── ROW 3: PATIENT PATH ──────────────
        row3_y = row2_y + bh + gap_y + 40
        c.create_text(x0, row3_y - 25, text="PATIENT PATH", anchor=tk.NW,
                      font=("Segoe UI", 11, "bold"), fill=ARENA_DARK)

        col = x0
        box(col, row3_y, "CREATE\nPatient\nArrivals", FLOWCHART_GREEN)
        p1_r = col + bw
        col += bw + gap_x

        box(col, row3_y, "ASSIGN\nBlood Type\nHLA / Urgency", FLOWCHART_BLUE)
        p2_r = col + bw
        col += bw + gap_x

        box(col, row3_y, "QUEUE\nWaitlist\n(Priority)", FLOWCHART_PURPLE)
        p3_r = col + bw
        p3_x = col
        col += bw + gap_x

        pdx = col
        diamond(col, row3_y - 8, "Attrition\n?")
        p4_r = col + dw
        col += dw + gap_x

        box(col, row3_y, "DISPOSE\nDied /\nTransferred", FLOWCHART_RED)

        # Arrows
        arrow(p1_r, row3_y + bh/2, p1_r + gap_x, row3_y + bh/2)
        arrow(p2_r, row3_y + bh/2, p2_r + gap_x, row3_y + bh/2)
        arrow(p3_r, row3_y + bh/2, p3_r + gap_x, row3_y + bh/2)
        arrow(p4_r, row3_y + bh/2 - 8, p4_r + gap_x, row3_y + bh/2, "Yes")

        # Dashed line: Patient waitlist → kidney matching
        c.create_line(p3_x + bw/2, row3_y, dx + bw/2, row2_y + bh,
                      dash=(6, 4), fill=ARENA_ACCENT, width=2, arrow=tk.LAST)
        c.create_text((p3_x + bw/2 + dx + bw/2) / 2,
                      (row3_y + row2_y + bh) / 2 - 10,
                      text="Match\nAttempt", font=("Segoe UI", 7, "bold"),
                      fill=ARENA_ACCENT)

        # ─────────── ROW 4: LIVING DONOR PATH ──────────────
        row4_y = row3_y + bh + gap_y + 40
        c.create_text(x0, row4_y - 25, text="LIVING DONOR PATH (PRE-SCHEDULED)",
                      anchor=tk.NW, font=("Segoe UI", 11, "bold"), fill=ARENA_DARK)

        col = x0
        box(col, row4_y, "CREATE\nLiving Donor\nKidney", FLOWCHART_GREEN)
        l1_r = col + bw
        col += bw + gap_x

        box(col, row4_y, "ASSIGN\n(Guaranteed\nCompatible)", FLOWCHART_BLUE)
        l2_r = col + bw
        col += bw + gap_x

        box(col, row4_y, "PROCESS\nCrossmatch\nLab", FLOWCHART_ORANGE)
        l3_r = col + bw
        col += bw + gap_x

        box(col, row4_y, "PROCESS\nSurgery\n(OR + Team)", FLOWCHART_ORANGE)
        l4_r = col + bw
        col += bw + gap_x

        box(col, row4_y, "DISPOSE\nSuccessful\nTransplant!", FLOWCHART_GREEN)

        arrow(l1_r, row4_y + bh/2, l1_r + gap_x, row4_y + bh/2)
        arrow(l2_r, row4_y + bh/2, l2_r + gap_x, row4_y + bh/2)
        arrow(l3_r, row4_y + bh/2, l3_r + gap_x, row4_y + bh/2)
        arrow(l4_r, row4_y + bh/2, l4_r + gap_x, row4_y + bh/2)

        # ─────────── LEGEND ──────────────
        leg_y = row4_y + bh + gap_y + 30
        c.create_text(x0, leg_y, text="LEGEND:", anchor=tk.NW,
                      font=("Segoe UI", 9, "bold"), fill=ARENA_DARK)
        legend_items = [
            (FLOWCHART_GREEN,  "Create / Dispose (Success)"),
            (FLOWCHART_BLUE,   "Assign Module"),
            (FLOWCHART_ORANGE, "Process Module (Seize-Delay-Release)"),
            (FLOWCHART_PURPLE, "Queue / Hold Module"),
            (FLOWCHART_YELLOW, "Decide Module"),
            (FLOWCHART_RED,    "Dispose (Failure / Expiry)"),
        ]
        lx = x0 + 80
        for i, (color, text) in enumerate(legend_items):
            ly = leg_y + i * 22
            c.create_rectangle(lx, ly, lx + 18, ly + 14, fill=color, outline="#555")
            c.create_text(lx + 26, ly + 7, text=text, anchor=tk.W,
                          font=("Segoe UI", 8), fill="#444")

        # Set scroll region
        c.configure(scrollregion=c.bbox("all"))

    # ===================================================================
    #  RUN SETUP DIALOG (Arena Run > Setup)
    # ===================================================================

    def _show_run_setup(self):
        """Open the Arena-style Run Setup dialog."""
        dlg = tk.Toplevel(self)
        dlg.title("Run Setup - Simulation Parameters")
        dlg.geometry("520x620")
        dlg.resizable(False, False)
        dlg.configure(bg=ARENA_BG)
        dlg.transient(self)
        dlg.grab_set()

        # Title
        tk.Label(dlg, text="Run > Setup", bg=ARENA_DARK, fg=ARENA_TEXT,
                 font=("Segoe UI", 12, "bold"), padx=12, pady=8).pack(fill=tk.X)

        nb = ttk.Notebook(dlg)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # ── Tab 1: Replication Parameters ──
        rep_tab = tk.Frame(nb, bg=ARENA_BG)
        nb.add(rep_tab, text="  Replication  ")
        params1 = [
            ("Number of Replications:", self.param_reps, 1, 100, int),
            ("Simulation Duration (hrs):", self.param_duration, 24, 87600, float),
            ("Warm-Up Period (hrs):", self.param_warmup, 0, 43800, float),
            ("Base Random Seed:", self.param_seed, 1, 99999, int),
        ]
        for i, (label, var, lo, hi, dtype) in enumerate(params1):
            frm = tk.Frame(rep_tab, bg=ARENA_BG)
            frm.pack(fill=tk.X, padx=20, pady=6)
            tk.Label(frm, text=label, bg=ARENA_BG, font=("Segoe UI", 10),
                     width=28, anchor=tk.W).pack(side=tk.LEFT)
            tk.Spinbox(frm, from_=lo, to=hi, textvariable=var, width=10,
                       font=("Segoe UI", 10), justify=tk.CENTER).pack(side=tk.RIGHT)

        # ── Tab 2: Resources ──
        res_tab = tk.Frame(nb, bg=ARENA_BG)
        nb.add(res_tab, text="  Resources  ")
        params2 = [
            ("Operating Rooms:", self.param_num_or, 1, 20),
            ("Surgical Teams:", self.param_num_teams, 1, 20),
            ("Transport Vehicles:", self.param_num_transport, 1, 20),
            ("Crossmatch Labs:", self.param_num_labs, 1, 10),
        ]
        for label, var, lo, hi in params2:
            frm = tk.Frame(res_tab, bg=ARENA_BG)
            frm.pack(fill=tk.X, padx=20, pady=6)
            tk.Label(frm, text=label, bg=ARENA_BG, font=("Segoe UI", 10),
                     width=28, anchor=tk.W).pack(side=tk.LEFT)
            tk.Spinbox(frm, from_=lo, to=hi, textvariable=var, width=10,
                       font=("Segoe UI", 10), justify=tk.CENTER).pack(side=tk.RIGHT)

        # ── Tab 3: Arrivals ──
        arr_tab = tk.Frame(nb, bg=ARENA_BG)
        nb.add(arr_tab, text="  Arrivals  ")

        tk.Label(arr_tab, text="Arrival rates are expressed as entities per hour.\n"
                 "E.g., 0.125 = ~3 per day, 0.25 = ~6 per day.",
                 bg=ARENA_BG, fg="#666", font=("Segoe UI", 9),
                 justify=tk.LEFT).pack(padx=20, pady=(10, 4), anchor=tk.W)

        params3 = [
            ("Kidney Arrival Rate (per hr):", self.param_kidney_rate),
            ("Patient Arrival Rate (per hr):", self.param_patient_rate),
            ("Living Donor Rate (per hr):", self.param_living_rate),
            ("Max Cold Ischemia Time (hrs):", self.param_max_ischemia),
            ("Quality Decay Rate:", self.param_decay_rate),
        ]
        for label, var in params3:
            frm = tk.Frame(arr_tab, bg=ARENA_BG)
            frm.pack(fill=tk.X, padx=20, pady=6)
            tk.Label(frm, text=label, bg=ARENA_BG, font=("Segoe UI", 10),
                     width=28, anchor=tk.W).pack(side=tk.LEFT)
            tk.Entry(frm, textvariable=var, width=12,
                     font=("Segoe UI", 10), justify=tk.CENTER).pack(side=tk.RIGHT)

        # ── Buttons ──
        btn_frame = tk.Frame(dlg, bg=ARENA_BG)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        tk.Button(btn_frame, text="OK", bg=ARENA_SUCCESS, fg="white",
                  font=("Segoe UI", 10, "bold"), width=10,
                  command=dlg.destroy).pack(side=tk.RIGHT, padx=4)
        tk.Button(btn_frame, text="Cancel", bg="#999", fg="white",
                  font=("Segoe UI", 10, "bold"), width=10,
                  command=dlg.destroy).pack(side=tk.RIGHT, padx=4)

    # ===================================================================
    #  SIMULATION EXECUTION
    # ===================================================================

    def _start_simulation(self):
        if self.is_running:
            messagebox.showinfo("Running", "Simulation is already running.")
            return

        self.is_running = True
        self.btn_start.config(state=tk.DISABLED, bg="#999")
        self.btn_setup.config(state=tk.DISABLED)
        self._console_log("=" * 60)
        self._console_log("  STARTING SIMULATION")
        self._console_log("=" * 60)

        self.sim_thread = threading.Thread(target=self._run_simulation_thread,
                                           daemon=True)
        self.sim_thread.start()

    def _run_simulation_thread(self):
        """Run simulation in background thread."""
        import config as cfg

        # Apply current GUI parameters to config
        cfg.SIM_DURATION = self.param_duration.get()
        cfg.WARM_UP_PERIOD = self.param_warmup.get()
        cfg.RANDOM_SEED_BASE = self.param_seed.get()
        cfg.NUM_OPERATING_ROOMS = self.param_num_or.get()
        cfg.NUM_SURGICAL_TEAMS = self.param_num_teams.get()
        cfg.NUM_TRANSPORT_VEHICLES = self.param_num_transport.get()
        cfg.NUM_CROSSMATCH_LABS = self.param_num_labs.get()
        cfg.KIDNEY_ARRIVAL_RATE = self.param_kidney_rate.get()
        cfg.PATIENT_ARRIVAL_RATE = self.param_patient_rate.get()
        cfg.LIVING_DONOR_RATE = self.param_living_rate.get()
        cfg.MAX_COLD_ISCHEMIA_TIME = self.param_max_ischemia.get()
        cfg.QUALITY_DECAY_RATE = self.param_decay_rate.get()

        sim_duration = cfg.SIM_DURATION
        num_reps = self.param_reps.get()

        self.rep_collector = ReplicationCollector()
        self.all_stats = []

        try:
            for rep in range(1, num_reps + 1):
                seed = cfg.RANDOM_SEED_BASE + rep * 1000

                self.after(0, lambda r=rep, n=num_reps: [
                    self.rep_label.config(text=f"Rep: {r}/{n}"),
                    self.status_label.config(text=f"  Running replication {r} of {n}..."),
                    self._console_log(f"\n--- Replication {r}/{n}  |  Seed: {seed} ---"),
                ])

                env = simpy.Environment()
                rng = random.Random(seed)
                stats = StatisticsCollector()

                model = KidneyTransplantSimulation(
                    env=env, rng=rng, stats=stats, run_id=rep, verbose=False
                )

                # Run in increments for progress updates
                step = sim_duration / 100.0
                for pct in range(1, 101):
                    env.run(until=min(pct * step, sim_duration))
                    progress = ((rep - 1) / num_reps + pct / 100.0 / num_reps) * 100
                    sim_time = env.now
                    self.after(0, lambda p=progress, t=sim_time: [
                        self.progress_var.set(p),
                        self.clock_label.config(
                            text=f"Sim Clock: {t:.0f} hrs (Day {t/24:.0f})"
                        ),
                    ])

                self.all_stats.append(stats)
                self.rep_collector.add_replication(stats, sim_duration)
                self.current_stats = stats

                # Update sidebar counters
                self.after(0, lambda s=stats, d=sim_duration: self._update_sidebar(s, d))

                # Save report
                report = stats.generate_report(sim_duration)
                report_path = os.path.join(self.output_dir, f"report_run{rep}.txt")
                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(report)

                self.after(0, lambda r=rep: self._console_log(
                    f"  Replication {r} complete. Report saved."
                ))

                # Generate plots
                self.after(0, lambda r=rep: self._console_log(
                    f"  Generating plots for replication {r}..."
                ))
                generate_all_plots(stats, self.output_dir, sim_duration, run_id=rep)

            # Cross-replication report
            if num_reps > 1:
                cross_report = self.rep_collector.across_replications_report()
                cross_path = os.path.join(self.output_dir, "across_replications_report.txt")
                with open(cross_path, "w", encoding="utf-8") as f:
                    f.write(cross_report)
                plot_replication_comparison(self.rep_collector.rep_results, self.output_dir)

            # Finalize
            self.after(0, self._on_simulation_complete)

        except Exception as e:
            self.after(0, lambda: [
                self._console_log(f"\n  ERROR: {e}"),
                self.status_label.config(text=f"  Error: {e}"),
                messagebox.showerror("Simulation Error", str(e)),
            ])
        finally:
            self.after(0, lambda: [
                self.btn_start.config(state=tk.NORMAL, bg=ARENA_SUCCESS),
                self.btn_setup.config(state=tk.NORMAL),
            ])
            self.is_running = False

    def _on_simulation_complete(self):
        """Called on main thread when simulation finishes."""
        self.progress_var.set(100)
        self.status_label.config(text="  Simulation complete!")
        self._console_log("\n" + "=" * 60)
        self._console_log("  SIMULATION COMPLETE")
        self._console_log(f"  Output saved to: {self.output_dir}")
        self._console_log("=" * 60)

        # Populate report selector
        report_files = sorted([f for f in os.listdir(self.output_dir)
                               if f.endswith(".txt")])
        self.report_selector["values"] = report_files
        if report_files:
            self.report_selector.current(0)
            self._load_report(report_files[0])

        # Populate plot selector
        plot_files = sorted([f for f in os.listdir(self.output_dir)
                             if f.endswith(".png")])
        self.plot_selector["values"] = plot_files
        if plot_files:
            self.plot_selector.current(0)
            self._load_plot(plot_files[0])

        # Switch to Reports tab
        self.output_tabs.select(1)

    # ===================================================================
    #  RESET
    # ===================================================================

    def _reset_simulation(self):
        if self.is_running:
            messagebox.showwarning("Running", "Cannot reset while simulation is running.")
            return

        self.current_stats = None
        self.rep_collector = ReplicationCollector()
        self.all_stats = []
        self.progress_var.set(0)
        self.status_label.config(text="  Ready")
        self.clock_label.config(text="Sim Clock: 0.0 hrs (Day 0)")
        self.rep_label.config(text="Rep: --/--")

        # Reset sidebar
        for key, lbl in self.counter_labels.items():
            lbl.config(text="0" if key not in (
                "util_rate", "waste_rate", "avg_wait", "avg_cit", "avg_quality",
                "or_util", "team_util", "transport_util", "lab_util"
            ) else "--")

        # Clear reports & plots
        self.report_text.delete("1.0", tk.END)
        self.report_selector["values"] = []
        self.plot_selector["values"] = []
        self.plot_canvas.delete("all")
        self._current_photo = None

        # Clear console
        self.console_text.delete("1.0", tk.END)
        self._console_log("Simulation reset. Ready for new run.")
        self._console_log("Press [Run] or F5 to start.")

        self._console_log("Output files from previous runs remain in output/ folder.")

    # ===================================================================
    #  UPDATE HELPERS
    # ===================================================================

    def _update_sidebar(self, stats: StatisticsCollector, sim_duration: float):
        """Refresh sidebar counter labels from stats."""
        self.counter_labels["kidneys_arrived"].config(
            text=str(stats.total_kidneys_arrived.value))
        self.counter_labels["patients_arrived"].config(
            text=str(stats.total_patients_arrived.value))
        self.counter_labels["transplants"].config(
            text=str(stats.successful_transplants.value))
        self.counter_labels["failed"].config(
            text=str(stats.failed_transplants.value))
        self.counter_labels["expired"].config(
            text=str(stats.organs_expired.value))
        self.counter_labels["no_match"].config(
            text=str(stats.organs_no_match.value))
        self.counter_labels["died_waiting"].config(
            text=str(stats.patients_died_waiting.value))
        self.counter_labels["transferred"].config(
            text=str(stats.patients_transferred.value))

        # Queues (last snapshot)
        if stats.snapshots:
            last = stats.snapshots[-1]
            self.counter_labels["waitlist_len"].config(
                text=str(last["waitlist_length"]))
            self.counter_labels["organ_pool"].config(
                text=str(last["organ_pool_size"]))

        # Resource utilization
        or_u = stats.or_utilization.time_weighted_average(sim_duration)
        tm_u = stats.surgical_team_utilization.time_weighted_average(sim_duration)
        tr_u = stats.transport_utilization.time_weighted_average(sim_duration)
        lb_u = stats.crossmatch_lab_utilization.time_weighted_average(sim_duration)
        self.counter_labels["or_util"].config(text=f"{or_u*100:.1f}%")
        self.counter_labels["team_util"].config(text=f"{tm_u*100:.1f}%")
        self.counter_labels["transport_util"].config(text=f"{tr_u*100:.1f}%")
        self.counter_labels["lab_util"].config(text=f"{lb_u*100:.1f}%")

        # KPIs
        total_k = stats.total_kidneys_arrived.value or 1
        util_rate = stats.successful_transplants.value / total_k * 100
        waste_rate = stats.organs_expired.value / total_k * 100
        self.counter_labels["util_rate"].config(text=f"{util_rate:.1f}%")
        self.counter_labels["waste_rate"].config(text=f"{waste_rate:.1f}%")
        self.counter_labels["avg_wait"].config(
            text=f"{stats.patient_wait_time_days.mean:.1f}")
        self.counter_labels["avg_cit"].config(
            text=f"{stats.organ_cold_ischemia_time.mean:.1f}")
        self.counter_labels["avg_quality"].config(
            text=f"{stats.organ_quality_at_transplant.mean:.3f}")

    def _load_report(self, filename):
        """Load a report text file into the report viewer."""
        path = os.path.join(self.output_dir, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.report_text.delete("1.0", tk.END)
            self.report_text.insert(tk.END, content)
        except Exception as e:
            self.report_text.delete("1.0", tk.END)
            self.report_text.insert(tk.END, f"Error loading {filename}: {e}")

    def _load_plot(self, filename):
        """Load a plot image into the plot viewer canvas."""
        path = os.path.join(self.output_dir, filename)
        try:
            img = Image.open(path)
            # Scale to fit canvas
            cw = self.plot_canvas.winfo_width() or 900
            ch = self.plot_canvas.winfo_height() or 600
            ratio = min(cw / img.width, ch / img.height, 1.0)
            new_w = int(img.width * ratio)
            new_h = int(img.height * ratio)
            img = img.resize((new_w, new_h), Image.LANCZOS)

            photo = ImageTk.PhotoImage(img)
            self.plot_canvas.delete("all")
            self.plot_canvas.create_image(cw // 2, ch // 2, image=photo)
            self._current_photo = photo  # prevent GC
        except Exception as e:
            self.plot_canvas.delete("all")
            self.plot_canvas.create_text(
                self.plot_canvas.winfo_width() // 2,
                self.plot_canvas.winfo_height() // 2,
                text=f"Error loading image:\n{e}",
                font=("Segoe UI", 12), fill="red"
            )

    def _on_report_selected(self, event):
        sel = self.report_selector.get()
        if sel:
            self._load_report(sel)

    def _on_plot_selected(self, event):
        sel = self.plot_selector.get()
        if sel:
            self._load_plot(sel)

    def _show_plot_tab(self, name):
        self.output_tabs.select(2)

    def _console_log(self, msg):
        self.console_text.insert(tk.END, msg + "\n")
        self.console_text.see(tk.END)

    def _sync_duration(self):
        """Keep duration hours in sync with the days spinbox."""
        try:
            days = self.duration_days_var.get()
            self.param_duration.set(days * 24.0)
        except tk.TclError:
            pass

    # ===================================================================
    #  FILE / UTILITY
    # ===================================================================

    def _open_output_folder(self):
        os.startfile(self.output_dir)

    def _export_report(self):
        if not self.current_stats:
            messagebox.showinfo("No Data", "Run simulation first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Export Report"
        )
        if path:
            report = self.current_stats.generate_report(self.param_duration.get())
            with open(path, "w", encoding="utf-8") as f:
                f.write(report)
            messagebox.showinfo("Exported", f"Report saved to:\n{path}")

    def _show_about(self):
        messagebox.showinfo(
            "About",
            "Kidney Transplant Logistics &\n"
            "Perishable Queueing Simulation\n\n"
            "Arena-Style Discrete-Event Simulation\n"
            "Built with Python, SimPy, Tkinter\n\n"
            "Course: Simulation\n"
        )


# ─── Entry Point ────────────────────────────────────────────────────────

def main():
    app = ArenaGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
