import math
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Dict, List, Tuple

BG_ROOT     = "#f3f5fa"
BG_PANEL    = "#ffffff"
BG_PANEL2   = "#eef1f8"
BG_FIELD    = "#ffffff"
BG_CANVAS   = "#fbfcfe"
BORDER      = "#dde3ef"
BORDER_SOFT = "#e8ecf5"

ACCENT_CYAN   = "#0891b2"
ACCENT_CYAN_D = "#0e7490"
ACCENT_AMBER  = "#d97706"
ACCENT_PINK   = "#db2777"
ACCENT_ORANGE = "#ea580c"
ACCENT_GREEN  = "#059669"
ACCENT_PURPLE = "#7c3aed"
ACCENT_RED    = "#dc2626"

TEXT_MAIN  = "#1c2330"
TEXT_DIM   = "#5b6477"
TEXT_FAINT = "#aab2c4"

F_TITLE   = ("Tahoma", 17, "bold")
F_SUBTLE  = ("Consolas", 9)
F_HEAD    = ("Tahoma", 10, "bold")
F_LABEL   = ("Tahoma", 10)
F_LABEL_B = ("Tahoma", 10, "bold")
F_MONO    = ("Consolas", 12, "bold")
F_MONO_SM = ("Consolas", 9)


def hex_to_rgb(value: str) -> Tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb: Tuple[float, float, float]) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(c))) for c in rgb)


def blend(color_a: str, color_b: str, t: float) -> str:
    """Linear-interpolate between two hex colors. t=0 -> a, t=1 -> b."""
    r1, g1, b1 = hex_to_rgb(color_a)
    r2, g2, b2 = hex_to_rgb(color_b)
    return rgb_to_hex((r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t))


# Technology node constants: (delay_scale, dyn_power_scale, leak_scale, complexity_scale)
TECH_NODES = {
    "CMOS 45nm (Base)":   (1.00, 1.00, 0.10, 1.00),
    "CMOS 28nm (Planar)": (0.65, 0.55, 0.25, 0.50),
    "FinFET 14nm":        (0.38, 0.30, 0.45, 0.25),
    "GAA 7nm":            (0.22, 0.14, 0.65, 0.12),
}

PHASE_LABELS = {1: "بارگذاری بیت‌ها", 2: "محاسبه G/P و حمل", 3: "تصحیح BCD و خروجی"}


class CLDASimulatorApp:
    """Main application window for the CLDA gate-level visual testbench."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("⚡ Professional CLDA Testbench & Multi-Phase Simulator")
        self.root.configure(bg=BG_ROOT)
        self.root.minsize(1180, 760)
        self._maximize_window()

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.ui_labels: Dict[str, ttk.Label] = {}
        self.current_results: Dict[str, Any] = None
        self.max_len: int = 0
        self.pad_num1: str = ""
        self.pad_num2: str = ""

        self.selected_tech = tk.StringVar(value="CMOS 45nm (Base)")
        self.anim_speed = tk.IntVar(value=400)  # ms per animation tick

        #Animation flow controls
        self.anim_active: bool = False
        self.anim_paused: bool = False
        self.current_canvas_idx: int = 0
        self.current_phase: int = 1
        self.current_bit_idx: int = 0
        self._after_id: Any = None
        self._glow_phase: float = 0.0

        self._setup_styles()
        self._build_ui()

        self.root.update()
        self.analyze_bcd(animate=False)
        self._pulse_loop()

    def _maximize_window(self):
        try:
            self.root.state("zoomed")
        except tk.TclError:
            try:
                self.root.attributes("-zoomed", True)
            except tk.TclError:
                pass

    def _setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", background=BG_PANEL, foreground=TEXT_MAIN)
        style.configure("TFrame", background=BG_ROOT)
        style.configure("Panel.TFrame", background=BG_PANEL)

        style.configure("TLabelframe", background=BG_PANEL, bordercolor=BORDER,
                         relief="flat", borderwidth=1)
        style.configure("TLabelframe.Label", font=F_HEAD, foreground=ACCENT_CYAN_D,
                         background=BG_PANEL, padding=(8, 4))

        style.configure("TLabel", font=F_LABEL, background=BG_PANEL, foreground=TEXT_MAIN)
        style.configure("Dim.TLabel", font=F_SUBTLE, background=BG_PANEL, foreground=TEXT_DIM)

        style.configure("TButton", font=F_LABEL_B, background=BG_PANEL2, foreground=TEXT_MAIN,
                         bordercolor=BORDER, padding=6)
        style.map("TButton",
                  background=[("active", BORDER_SOFT), ("disabled", "#f4f5f8")],
                  foreground=[("active", TEXT_MAIN), ("disabled", TEXT_FAINT)])

        style.configure("TEntry", fieldbackground=BG_FIELD, foreground=TEXT_MAIN,
                         bordercolor=BORDER, insertcolor=ACCENT_CYAN_D, padding=6)
        style.map("TEntry", bordercolor=[("focus", ACCENT_CYAN_D)])

        style.configure("TCombobox", fieldbackground=BG_FIELD, background=BG_PANEL2,
                         foreground=TEXT_MAIN, arrowcolor=ACCENT_CYAN_D, bordercolor=BORDER,
                         padding=5)
        style.map("TCombobox", fieldbackground=[("readonly", BG_FIELD)],
                  selectbackground=[("readonly", BG_FIELD)],
                  selectforeground=[("readonly", TEXT_MAIN)])

        style.configure("Treeview", font=F_MONO_SM, rowheight=28, background=BG_FIELD,
                         fieldbackground=BG_FIELD, foreground=TEXT_MAIN, borderwidth=0)
        style.configure("Treeview.Heading", font=("Tahoma", 9, "bold"), background=BG_PANEL2,
                         foreground=ACCENT_CYAN_D, relief="flat", borderwidth=0, padding=6)
        style.map("Treeview.Heading", background=[("active", BORDER_SOFT)])
        style.map("Treeview", background=[("selected", ACCENT_CYAN)],
                  foreground=[("selected", "#ffffff")])

        style.configure("Vertical.TScrollbar", background=BG_PANEL2, troughcolor=BG_ROOT,
                         bordercolor=BG_ROOT, arrowcolor=ACCENT_CYAN_D, relief="flat")
        style.configure("Horizontal.TScrollbar", background=BG_PANEL2, troughcolor=BG_ROOT,
                         bordercolor=BG_ROOT, arrowcolor=ACCENT_CYAN_D, relief="flat")

        style.configure("Speed.Horizontal.TScale", background=BG_PANEL, troughcolor=BG_FIELD)

    def _make_button(self, parent, text, command, accent=ACCENT_CYAN_D, state="normal", width=None):
        btn = tk.Button(
            parent, text=text, command=command,
            bg=BG_PANEL2, fg=TEXT_MAIN, activebackground=blend(BG_PANEL2, accent, 0.25),
            activeforeground="#ffffff", font=F_LABEL_B, borderwidth=0, relief="flat",
            padx=14, pady=8, cursor="hand2", state=state,
            highlightthickness=1, highlightbackground=BORDER, highlightcolor=accent,
        )
        if width:
            btn.config(width=width)

        def on_enter(_e):
            if btn["state"] != "disabled":
                btn.config(bg=blend(BG_PANEL2, accent, 0.18), highlightbackground=accent, fg="#ffffff")

        def on_leave(_e):
            if btn["state"] != "disabled":
                btn.config(bg=BG_PANEL2, highlightbackground=BORDER, fg=TEXT_MAIN)

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn
    
    def _build_ui(self):
        window_container = ttk.Frame(self.root)
        window_container.grid(row=0, column=0, sticky="nsew")
        window_container.columnconfigure(0, weight=1)
        window_container.rowconfigure(0, weight=1)

        self.main_canvas = tk.Canvas(window_container, bg=BG_ROOT, highlightthickness=0)
        self.main_canvas.grid(row=0, column=0, sticky="nsew")

        v_scrollbar = ttk.Scrollbar(window_container, orient=tk.VERTICAL, command=self.main_canvas.yview)
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.main_canvas.configure(yscrollcommand=v_scrollbar.set)

        main_frame = ttk.Frame(self.main_canvas, padding=18)
        self.main_canvas_window = self.main_canvas.create_window((0, 0), window=main_frame, anchor="nw")

        main_frame.bind("<Configure>",
                         lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all")))
        self.main_canvas.bind("<Configure>",
                               lambda e: self.main_canvas.itemconfig(self.main_canvas_window, width=e.width))

        def _on_wheel(event):
            self.main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.main_canvas.bind_all("<MouseWheel>", _on_wheel)

        self._build_header(main_frame)
        self._build_input_panel(main_frame)
        self._build_circuit_panel(main_frame)
        self._build_analysis_table(main_frame)
        self._build_hardware_panel(main_frame)
        self._build_waveform_panel(main_frame)
        self._build_output_dashboard(main_frame)

    def _build_header(self, parent):
        header = tk.Frame(parent, bg=BG_ROOT)
        header.pack(fill="x", pady=(0, 14))
        tk.Label(header, text="⚡", font=("Segoe UI Emoji", 22), bg=BG_ROOT, fg=ACCENT_AMBER).pack(
            side="right", padx=(10, 0))
        title_box = tk.Frame(header, bg=BG_ROOT)
        title_box.pack(side="right")
        tk.Label(title_box, text="محیط توسعه و شبیه‌ساز چندفازی مدار افزاینده پیش‌بین دهدهی",
                 font=F_TITLE, fg=ACCENT_CYAN_D, bg=BG_ROOT).pack(anchor="e")
        tk.Label(title_box, text="Carry Look-Ahead Decimal Adder  •  Gate-level Visual Testbench",
                 font=F_SUBTLE, fg=TEXT_DIM, bg=BG_ROOT).pack(anchor="e")

    def _build_input_panel(self, parent):
        frame_inputs = ttk.LabelFrame(parent, text="  ⚙  پنل کنترل شبیه‌سازی و ارقام ورودی  ")
        frame_inputs.pack(pady=6, fill="x")

        input_container = ttk.Frame(frame_inputs, style="Panel.TFrame")
        input_container.pack(pady=10, padx=8, fill="x")

        ttk.Label(input_container, text="عدد اول (A):").grid(row=0, column=0, padx=6, pady=6, sticky="e")
        self.entry_num1 = ttk.Entry(input_container, width=12, font=F_MONO, justify="center")
        self.entry_num1.grid(row=0, column=1, padx=6, pady=6)
        self.entry_num1.insert(0, "764")

        ttk.Label(input_container, text="عدد دوم (B):").grid(row=0, column=2, padx=6, pady=6, sticky="e")
        self.entry_num2 = ttk.Entry(input_container, width=12, font=F_MONO, justify="center")
        self.entry_num2.grid(row=0, column=3, padx=6, pady=6)
        self.entry_num2.insert(0, "459")

        for entry in (self.entry_num1, self.entry_num2):
            entry.bind("<Return>", lambda ev: self.analyze_bcd(animate=False))
            entry.bind("<KeyRelease>", self._live_validate)

        ttk.Label(input_container, text="تکنولوژی سیلیکون:").grid(row=0, column=4, padx=6, pady=6, sticky="e")
        self.combo_tech = ttk.Combobox(input_container, textvariable=self.selected_tech,
                                        values=list(TECH_NODES.keys()), width=20, state="readonly")
        self.combo_tech.grid(row=0, column=5, padx=6, pady=6)
        self.combo_tech.bind("<<ComboboxSelected>>", lambda e: self.update_hardware_metrics_only())

        ttk.Label(input_container, text="سرعت انیمیشن:").grid(row=0, column=6, padx=(18, 6), pady=6, sticky="e")
        self.scale_speed = ttk.Scale(input_container, from_=800, to=120, orient="horizontal",
                                      variable=self.anim_speed, length=120, style="Speed.Horizontal.TScale")
        self.scale_speed.grid(row=0, column=7, padx=6, pady=6)

        btn_row = ttk.Frame(input_container, style="Panel.TFrame")
        btn_row.grid(row=0, column=8, padx=(10, 0))
        self.btn_analyze = self._make_button(btn_row, "🔍 ارزیابی و رندر آنی",
                                              lambda: self.analyze_bcd(animate=False), accent=ACCENT_CYAN_D)
        self.btn_analyze.pack(side="right", padx=4)
        self.btn_animate = self._make_button(btn_row, "▶ شبیه‌سازی مالتی‌فاز",
                                              lambda: self.analyze_bcd(animate=True), accent=ACCENT_AMBER)
        self.btn_animate.pack(side="right", padx=4)

        self.input_status = tk.Label(frame_inputs, text="ورودی معتبر است ✓", font=F_SUBTLE,
                                      bg=BG_PANEL, fg=ACCENT_GREEN, anchor="e")
        self.input_status.pack(fill="x", padx=14, pady=(0, 8))

        anim_control_container = ttk.Frame(frame_inputs, style="Panel.TFrame")
        anim_control_container.pack(pady=(0, 12))

        self.btn_prev = self._make_button(anim_control_container, "⏮ گام قبلی", self.step_backward,
                                           accent=ACCENT_PURPLE, state="disabled")
        self.btn_prev.grid(row=0, column=0, padx=5)
        self.btn_pause = self._make_button(anim_control_container, "⏸ توقف", self.pause_animation,
                                            accent=ACCENT_ORANGE, state="disabled")
        self.btn_pause.grid(row=0, column=1, padx=5)
        self.btn_resume = self._make_button(anim_control_container, "▶ ادامه", self.resume_animation,
                                             accent=ACCENT_GREEN, state="disabled")
        self.btn_resume.grid(row=0, column=2, padx=5)
        self.btn_next = self._make_button(anim_control_container, "⏭ گام بعدی", self.step_forward,
                                           accent=ACCENT_PURPLE, state="disabled")
        self.btn_next.grid(row=0, column=3, padx=5)

        self.phase_label = tk.Label(frame_inputs, text="", font=F_SUBTLE, bg=BG_PANEL, fg=TEXT_DIM)
        self.phase_label.pack(pady=(0, 4))

        self.progress_canvas = tk.Canvas(frame_inputs, height=8, bg=BG_FIELD, highlightthickness=0)
        self.progress_canvas.pack(fill="x", padx=14, pady=(0, 10))
        self.progress_canvas.bind("<Configure>", lambda e: self._draw_progress())

    def _build_circuit_panel(self, parent):
        frame_canvas = ttk.LabelFrame(parent, text="  🔬  پایشگر پویای خطوط سیگنال و ساختار میکرو-لوژیک  ")
        frame_canvas.pack(pady=6, fill="x")

        canvas_grid_frame = ttk.Frame(frame_canvas, style="Panel.TFrame")
        canvas_grid_frame.pack(fill="x", padx=10, pady=10)
        canvas_grid_frame.columnconfigure(0, weight=1)

        self.canvas_circuit = tk.Canvas(canvas_grid_frame, bg=BG_CANVAS, height=320, relief=tk.FLAT,
                                         borderwidth=0, highlightthickness=1, highlightbackground=BORDER)
        self.canvas_circuit.grid(row=0, column=0, sticky="nsew")

        vbar_c = ttk.Scrollbar(canvas_grid_frame, orient=tk.VERTICAL, command=self.canvas_circuit.yview)
        vbar_c.grid(row=0, column=1, sticky="ns")
        hbar_c = ttk.Scrollbar(canvas_grid_frame, orient=tk.HORIZONTAL, command=self.canvas_circuit.xview)
        hbar_c.grid(row=1, column=0, sticky="ew")
        self.canvas_circuit.configure(xscrollcommand=hbar_c.set, yscrollcommand=vbar_c.set)
        self.canvas_circuit.bind("<Configure>", lambda e: self.trigger_redraw())

        legend = tk.Frame(frame_canvas, bg=BG_PANEL)
        legend.pack(fill="x", padx=14, pady=(0, 10))
        for color, text in [
            (ACCENT_ORANGE, "فاز ۱: بارگذاری بیت‌ها"),
            (ACCENT_PINK, "فاز ۲: محاسبه G/P و حمل"),
            (ACCENT_AMBER, "فاز ۳: تصحیح BCD و خروجی"),
            (ACCENT_GREEN, "بلوک تکمیل‌شده"),
        ]:
            chip = tk.Frame(legend, bg=BG_PANEL)
            chip.pack(side="right", padx=10)
            dot = tk.Canvas(chip, width=12, height=12, bg=BG_PANEL, highlightthickness=0)
            dot.pack(side="right")
            dot.create_oval(1, 1, 11, 11, fill=color, outline="")
            tk.Label(chip, text=text, font=F_SUBTLE, fg=TEXT_DIM, bg=BG_PANEL).pack(side="right", padx=4)
        tk.Label(legend, text="💡 روی هر بلوک کلیک کنید تا ساختار گیت‌ها را ببینید", font=F_SUBTLE,
                 fg=TEXT_FAINT, bg=BG_PANEL).pack(side="left")

    def _build_analysis_table(self, parent):
        frame_analysis = ttk.LabelFrame(
            parent, text="  📋  جدول ردگیری سیگنال‌های واسط، توابع منطقی و وضعیت تصحیح ارقام  ")
        frame_analysis.pack(pady=6, fill="x")

        table_wrap = ttk.Frame(frame_analysis, style="Panel.TFrame")
        table_wrap.pack(fill="x", padx=10, pady=10)

        columns = ("digit", "a_bcd", "b_bcd", "bin_sum", "correction", "cla_carry")
        self.tree_analysis = ttk.Treeview(table_wrap, columns=columns, show="headings", height=6)
        self.tree_analysis.pack(side="left", fill="x", expand=True)
        tree_scroll = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree_analysis.yview)
        tree_scroll.pack(side="right", fill="y")
        self.tree_analysis.configure(yscrollcommand=tree_scroll.set)

        headers = ["مرتبه رقم", "کد BCD اول (A)", "کد BCD دوم (B)", "مجموع باینری واسط",
                   "تحلیل تابع تصحیح (۶+)", "حمل خروجی پیش‌بین"]
        widths = [90, 130, 130, 150, 360, 150]
        for col, heading, w in zip(columns, headers, widths):
            self.tree_analysis.heading(col, text=heading)
            self.tree_analysis.column(col, width=w, anchor="center")

        self.tree_analysis.tag_configure("odd", background=BG_PANEL2)
        self.tree_analysis.tag_configure("even", background=BG_FIELD)
        self.tree_analysis.tag_configure("corrected", foreground=ACCENT_PINK)
        self.tree_analysis.tag_configure("clean", foreground=ACCENT_GREEN)

    def _build_hardware_panel(self, parent):
        frame_hardware = ttk.LabelFrame(parent, text="  🧪  ارزیابی پارامترهای فیزیکی سیلیکون در لایه متالیزاسیون  ")
        frame_hardware.pack(pady=6, fill="x")

        metrics_panel = ttk.Frame(frame_hardware, style="Panel.TFrame")
        metrics_panel.pack(fill="x", padx=12, pady=10)
        for c in range(3):
            metrics_panel.columnconfigure(c, weight=1)

        ttk.Label(metrics_panel, text="پارامتر سخت‌افزاری", font=F_HEAD,
                  foreground=ACCENT_CYAN_D).grid(row=0, column=0, padx=15, pady=8, sticky="w")
        ttk.Label(metrics_panel, text="⚡ معماری موازی حمل پیش‌بین (CLDA)", font=F_HEAD,
                  foreground=ACCENT_AMBER).grid(row=0, column=1, padx=15, pady=8, sticky="w")
        ttk.Label(metrics_panel, text="⛓ معماری ترتیبی زنجیره‌ای (RCA)", font=F_HEAD,
                  foreground=TEXT_DIM).grid(row=0, column=2, padx=15, pady=8, sticky="w")

        sep = tk.Frame(metrics_panel, bg=BORDER, height=1)
        sep.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(36, 0))

        metrics_config = [
            ("⏱  زمان تأخیر مسیر بحرانی (Critical Path Delay):", "lbl_hw_delay_clda", "lbl_hw_delay_rca"),
            ("🔋  مجموع توان مصرفی کل (Total Power = Dyn + Leak):", "lbl_hw_power_clda", "lbl_hw_power_rca"),
            ("📊  مجموع حاصل‌ضرب توان در تأخیر (PDP):", "lbl_hw_pdp_clda", "lbl_hw_pdp_rca"),
            ("🧩  پیچیدگی فیزیکی سیلیکون (Silicon Complexity):", "lbl_hw_tc_clda", "lbl_hw_tc_rca"),
        ]
        for i, (label_text, clda_var, rca_var) in enumerate(metrics_config, start=1):
            ttk.Label(metrics_panel, text=label_text).grid(row=i, column=0, padx=15, pady=8, sticky="w")
            self.ui_labels[clda_var] = ttk.Label(metrics_panel, text="-", font=F_LABEL_B, foreground=ACCENT_AMBER)
            self.ui_labels[clda_var].grid(row=i, column=1, padx=15, pady=8, sticky="w")
            self.ui_labels[rca_var] = ttk.Label(metrics_panel, text="-", font=F_LABEL_B, foreground=TEXT_DIM)
            self.ui_labels[rca_var].grid(row=i, column=2, padx=15, pady=8, sticky="w")

        self.gauge_canvas = tk.Canvas(frame_hardware, height=80, bg=BG_PANEL, highlightthickness=0)
        self.gauge_canvas.pack(fill="x", padx=14, pady=(0, 12))
        self.gauge_canvas.bind("<Configure>", lambda e: self.update_hardware_metrics_only())

    def _build_waveform_panel(self, parent):
        frame_waveform = ttk.LabelFrame(parent, text="  📈  نمودار زمانی سیگنال‌های حیاتی دیجیتال (Waveform Viewer)  ")
        frame_waveform.pack(pady=6, fill="x")

        wave_grid_frame = ttk.Frame(frame_waveform, style="Panel.TFrame")
        wave_grid_frame.pack(fill="x", padx=10, pady=10)
        wave_grid_frame.columnconfigure(0, weight=1)

        self.canvas_wave = tk.Canvas(wave_grid_frame, bg=BG_CANVAS, height=180, highlightthickness=1,
                                      highlightbackground=BORDER)
        self.canvas_wave.grid(row=0, column=0, sticky="nsew")

        vbar_w = ttk.Scrollbar(wave_grid_frame, orient=tk.VERTICAL, command=self.canvas_wave.yview)
        vbar_w.grid(row=0, column=1, sticky="ns")
        hbar_w = ttk.Scrollbar(wave_grid_frame, orient=tk.HORIZONTAL, command=self.canvas_wave.xview)
        hbar_w.grid(row=1, column=0, sticky="ew")
        self.canvas_wave.configure(xscrollcommand=hbar_w.set, yscrollcommand=vbar_w.set)
        self.canvas_wave.bind("<Configure>", lambda e: self.draw_waveforms())

    def _build_output_dashboard(self, parent):
        frame_output = ttk.LabelFrame(parent, text="  🖥  داشبورد نهایی وضعیت خروجی سیستم  ")
        frame_output.pack(pady=(6, 18), fill="x")

        out_grid = ttk.Frame(frame_output, style="Panel.TFrame")
        out_grid.pack(fill="x", padx=14, pady=12)
        out_grid.columnconfigure(1, weight=1)

        ttk.Label(out_grid, text="🔵 سیگنال وضعیت انیمیشن:").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        self.ui_labels["lbl_anim_status"] = ttk.Label(out_grid, text="Ready", font=F_LABEL_B,
                                                        foreground=ACCENT_CYAN_D)
        self.ui_labels["lbl_anim_status"].grid(row=0, column=1, padx=10, pady=8, sticky="w")

        ttk.Label(out_grid, text="🟡 کد نهایی موازی BCD:").grid(row=1, column=0, padx=10, pady=8, sticky="w")
        self.ui_labels["lbl_final_bcd"] = ttk.Label(out_grid, text="-", font=("Consolas", 15, "bold"),
                                                      foreground=ACCENT_AMBER)
        self.ui_labels["lbl_final_bcd"].grid(row=1, column=1, padx=10, pady=8, sticky="w")

        ttk.Label(out_grid, text="🟢 معادل خروجی عددی (Dec):").grid(row=2, column=0, padx=10, pady=8, sticky="w")
        self.ui_labels["lbl_final_dec"] = ttk.Label(out_grid, text="-", font=("Consolas", 15, "bold"),
                                                      foreground=ACCENT_GREEN)
        self.ui_labels["lbl_final_dec"].grid(row=2, column=1, padx=10, pady=8, sticky="w")

        ttk.Label(out_grid, text="🧮 صحت‌سنجی (Verification):").grid(row=3, column=0, padx=10, pady=8, sticky="w")
        self.ui_labels["lbl_verify"] = ttk.Label(out_grid, text="-", font=F_LABEL_B, foreground=ACCENT_GREEN)
        self.ui_labels["lbl_verify"].grid(row=3, column=1, padx=10, pady=8, sticky="w")

    
    def _live_validate(self, _event=None):
        a = self.entry_num1.get().strip()
        b = self.entry_num2.get().strip()
        if a == "" or b == "":
            self.input_status.config(text="⚠ لطفاً هر دو عدد را وارد کنید", fg=ACCENT_ORANGE)
        elif not a.isdigit() or not b.isdigit():
            self.input_status.config(text="✖ فقط ارقام دهدهی مثبت مجاز است", fg=ACCENT_RED)
        elif len(a) > 12 or len(b) > 12:
            self.input_status.config(text="⚠ برای وضوح بصری بهتر، اعداد کوتاه‌تر از ۱۲ رقم وارد کنید",
                                      fg=ACCENT_ORANGE)
        else:
            self.input_status.config(text="ورودی معتبر است ✓", fg=ACCENT_GREEN)

    def _pulse_loop(self):
        self._glow_phase = (self._glow_phase + 0.12) % (2 * math.pi)
        if self.anim_active and not self.anim_paused and self.current_results:
            self.draw_schematic(
                self.max_len, self.pad_num1, self.pad_num2,
                self.current_results["carries"], self.current_results["final_bcd"],
                self.current_canvas_idx, self.current_phase, self.current_bit_idx,
            )
        self.root.after(70, self._pulse_loop)

    @staticmethod
    def _round_rect(canvas, x1, y1, x2, y2, r=12, **kwargs):
        points = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    @staticmethod
    def generate_cla_carry(a_bits: str, b_bits: str, c_in: int) -> Tuple[int, int, int]:
        a = [int(x) for x in reversed(a_bits)]
        b = [int(x) for x in reversed(b_bits)]
        g_bits = [a[j] & b[j] for j in range(4)]
        p_bits = [a[j] ^ b[j] for j in range(4)]

        c1 = g_bits[0] | (p_bits[0] & c_in)
        c2 = g_bits[1] | (p_bits[1] & g_bits[0]) | (p_bits[1] & p_bits[0] & c_in)
        c3 = (g_bits[2] | (p_bits[2] & g_bits[1]) | (p_bits[2] & p_bits[1] & g_bits[0])
              | (p_bits[2] & p_bits[1] & p_bits[0] & c_in))
        c_out = (g_bits[3] | (p_bits[3] & c3) | (c2 & c1) | (g_bits[2] & p_bits[3])
                 | (g_bits[2] & g_bits[1]))

        digit_g = (g_bits[3] | (p_bits[3] & g_bits[2]) | (p_bits[3] & p_bits[2] & g_bits[1])
                   | (p_bits[3] & p_bits[2] & p_bits[1] & g_bits[0]))
        digit_p = p_bits[3] & p_bits[2] & p_bits[1] & p_bits[0]
        return c_out, digit_g, digit_p

    def calculate_hardware_metrics(self, length: int) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        node = self.selected_tech.get()
        d_scale, dp_scale, lp_scale, c_scale = TECH_NODES.get(node, (1.0, 1.0, 0.1, 1.0))

        clda_base_delay = 45.0 * (length ** 0.5) + 30.0
        rca_base_delay = 35.0 * length * 4 + 20.0

        clda_base_complexity = 140 * length + 80
        rca_base_complexity = 32 * length * 4

        clda_dyn_pwr = (0.015 * clda_base_complexity) * dp_scale
        rca_dyn_pwr = (0.008 * rca_base_complexity) * dp_scale

        clda_leak_pwr = (0.04 * clda_base_complexity) * lp_scale
        rca_leak_pwr = (0.04 * rca_base_complexity) * lp_scale

        clda_total_pwr = clda_dyn_pwr + clda_leak_pwr
        rca_total_pwr = rca_dyn_pwr + rca_leak_pwr

        clda_metrics = {
            "delay": clda_base_delay * d_scale,
            "power": clda_total_pwr,
            "pdp": (clda_base_delay * d_scale) * clda_total_pwr,
            "tc": int(clda_base_complexity * c_scale),
        }
        rca_metrics = {
            "delay": rca_base_delay * d_scale,
            "power": rca_total_pwr,
            "pdp": (rca_base_delay * d_scale) * rca_total_pwr,
            "tc": int(rca_base_complexity * c_scale),
        }
        return clda_metrics, rca_metrics

    def update_hardware_metrics_only(self):
        if self.max_len <= 0:
            return
        clda_m, rca_m = self.calculate_hardware_metrics(self.max_len)
        self.ui_labels["lbl_hw_delay_clda"].config(text=f"{clda_m['delay']:.1f} ps")
        self.ui_labels["lbl_hw_delay_rca"].config(text=f"{rca_m['delay']:.1f} ps")
        self.ui_labels["lbl_hw_power_clda"].config(text=f"{clda_m['power']:.2f} µW")
        self.ui_labels["lbl_hw_power_rca"].config(text=f"{rca_m['power']:.2f} µW")
        self.ui_labels["lbl_hw_pdp_clda"].config(text=f"{clda_m['pdp']:.1f} fJ")
        self.ui_labels["lbl_hw_pdp_rca"].config(text=f"{rca_m['pdp']:.1f} fJ")
        self.ui_labels["lbl_hw_tc_clda"].config(text=f"{clda_m['tc']:,} ترانزیستور")
        self.ui_labels["lbl_hw_tc_rca"].config(text=f"{rca_m['tc']:,} ترانزیستور")
        self._draw_gauges(clda_m, rca_m)

    def _draw_gauges(self, clda_m, rca_m):
        c = self.gauge_canvas
        c.delete("all")
        w = c.winfo_width()
        if w < 50:
            return
        h = 80
        rows = [
            ("Delay", clda_m["delay"], rca_m["delay"], ACCENT_AMBER),
            ("Power", clda_m["power"], rca_m["power"], ACCENT_PINK),
            ("PDP", clda_m["pdp"], rca_m["pdp"], ACCENT_PURPLE),
        ]
        col_w = w / 3
        max_bar_h = 42
        for i, (label, v1, v2, color) in enumerate(rows):
            cx = col_w * i + col_w / 2
            mx = max(v1, v2, 0.0001)
            h1 = (v1 / mx) * max_bar_h
            h2 = (v2 / mx) * max_bar_h
            base_y = h - 10
            bw = 22
            c.create_text(cx, base_y - max_bar_h - 14, text=label, font=("Tahoma", 8, "bold"), fill=TEXT_DIM)
            self._round_rect(c, cx - bw - 6, base_y - h1, cx - 6, base_y, r=4, fill=color, outline="")
            self._round_rect(c, cx + 6, base_y - h2, cx + 6 + bw, base_y, r=4, fill=TEXT_FAINT, outline="")
            c.create_line(cx - bw - 6, base_y, cx + 6 + bw, base_y, fill=BORDER, width=1)
            c.create_text(cx - bw / 2 - 6, base_y + 10, text="CLDA", font=("Tahoma", 7, "bold"), fill=color)
            c.create_text(cx + bw / 2 + 6, base_y + 10, text="RCA", font=("Tahoma", 7), fill=TEXT_DIM)

    def process_logic(self, pad_num1: str, pad_num2: str, max_len: int) -> Dict[str, Any]:
        carries = [0] * (max_len + 1)
        final_bcd = [""] * max_len
        table_rows: List[Tuple] = []
        row_tags: List[str] = []

        for i in reversed(range(max_len)):
            d1 = int(pad_num1[i])
            d2 = int(pad_num2[i])
            b1_str, b2_str = f"{d1:04b}", f"{d2:04b}"

            raw_sum = d1 + d2 + carries[i + 1]
            bin_sum_str = f"{raw_sum:04b}"

            if raw_sum > 9:
                corrected_val = (raw_sum + 6) & 0b1111
                carries[i] = 1
                correction_msg = f"{raw_sum} > 9  →  فعال شدن تابع تصحیح (+۶): {raw_sum}+۶={raw_sum + 6}"
                tag = "corrected"
            else:
                corrected_val = raw_sum & 0b1111
                carries[i] = 0
                correction_msg = f"{raw_sum} ≤ 9  →  بدون نیاز به تصحیح"
                tag = "clean"

            final_bcd[i] = f"{corrected_val:04b}"

            table_rows.append((
                f"رقم {max_len - 1 - i}",
                f"{d1} ({b1_str})",
                f"{d2} ({b2_str})",
                f"{raw_sum} ({bin_sum_str})",
                correction_msg,
                f"C_out = {carries[i]}",
            ))
            row_tags.append(tag)

        return {
            "carries": carries,
            "final_bcd": final_bcd,
            "table_rows": table_rows,
            "row_tags": row_tags,
        }

    def open_gate_level_popup(self, logic_idx: int):
        idx = self.max_len - 1 - logic_idx
        d1 = int(self.pad_num1[idx])
        d2 = int(self.pad_num2[idx])
        b1_str, b2_str = f"{d1:04b}", f"{d2:04b}"

        popup = tk.Toplevel(self.root)
        popup.title(f"🔬 Micro-Gate Logic Viewer — Digit {logic_idx}")
        popup.geometry("820x560")
        popup.minsize(640, 440)
        popup.configure(bg=BG_ROOT)

        bar = tk.Frame(popup, bg=BG_PANEL, height=4)
        bar.pack(fill="x")
        tk.Canvas(bar, height=4, bg=ACCENT_AMBER, highlightthickness=0).pack(fill="x")

        tk.Label(popup, text=f"ساختار داخلی گیت‌های منطقی بلوک رقم {logic_idx}",
                 font=("Tahoma", 12, "bold"), fg=ACCENT_CYAN_D, bg=BG_ROOT).pack(pady=12)

        container = ttk.Frame(popup)
        container.pack(fill="both", expand=True, padx=15, pady=5)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        p_canvas = tk.Canvas(container, bg=BG_CANVAS, highlightthickness=1, highlightbackground=BORDER)
        p_canvas.grid(row=0, column=0, sticky="nsew")

        v_scroll = ttk.Scrollbar(container, orient=tk.VERTICAL, command=p_canvas.yview)
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=p_canvas.xview)
        h_scroll.grid(row=1, column=0, sticky="ew")
        p_canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)

        content_width, content_height = 800, 440

        def center_content(_event=None):
            c_width = max(p_canvas.winfo_width(), content_width)
            c_height = max(p_canvas.winfo_height(), content_height)
            ox = max((c_width - content_width) // 2, 20)
            oy = max((c_height - content_height) // 2, 20)

            p_canvas.delete("all")

            p_canvas.create_text(ox + 90, oy + 25, text="ورودی‌های باینری رقم:",
                                  font=("Tahoma", 9, "bold"), fill=TEXT_DIM)
            p_canvas.create_text(ox + 90, oy + 50, text=f"A = {b1_str}   |   B = {b2_str}",
                                  font=("Consolas", 12, "bold"), fill=ACCENT_AMBER)

            self._round_rect(p_canvas, ox + 40, oy + 100, ox + 170, oy + 160,
                              r=10, fill=BG_PANEL2, outline=ACCENT_CYAN_D, width=1.5)
            p_canvas.create_text(ox + 105, oy + 130, text="XOR Network\n(Propagate)",
                                  font=("Tahoma", 8, "bold"), fill=TEXT_MAIN, justify="center")
            p_canvas.create_line(ox + 170, oy + 130, ox + 230, oy + 130,
                                  arrow=tk.LAST, fill=ACCENT_CYAN_D, width=2)

            self._round_rect(p_canvas, ox + 40, oy + 200, ox + 170, oy + 260,
                              r=10, fill=BG_PANEL2, outline=ACCENT_ORANGE, width=1.5)
            p_canvas.create_text(ox + 105, oy + 230, text="AND Network\n(Generate)",
                                  font=("Tahoma", 8, "bold"), fill=TEXT_MAIN, justify="center")
            p_canvas.create_line(ox + 170, oy + 230, ox + 230, oy + 230,
                                  arrow=tk.LAST, fill=ACCENT_ORANGE, width=2)

            self._round_rect(p_canvas, ox + 230, oy + 95, ox + 440, oy + 265,
                              r=14, fill="#fff4e0", outline=ACCENT_AMBER, width=2)
            p_canvas.create_text(ox + 335, oy + 180,
                                  text="Look-Ahead Carry Unit\n\nC_out = G + P·C_in",
                                  font=("Tahoma", 10, "bold"), fill="#92400e", justify="center")

            self._round_rect(p_canvas, ox + 490, oy + 125, ox + 670, oy + 235,
                              r=14, fill="#fce7f3", outline=ACCENT_PINK, width=1.5)
            p_canvas.create_text(ox + 580, oy + 180,
                                  text="BCD Correction\n(+6 Combinational\nAdder Line)",
                                  font=("Tahoma", 9, "bold"), fill="#9d174d", justify="center")

            p_canvas.create_line(ox + 440, oy + 180, ox + 490, oy + 180,
                                  arrow=tk.LAST, fill=ACCENT_AMBER, width=2)
            p_canvas.create_line(ox + 670, oy + 180, ox + 715, oy + 180,
                                  arrow=tk.LAST, fill=TEXT_MAIN, width=2)

            final_sum = self.current_results["final_bcd"][idx] if self.current_results else "????"
            dec_digit = int(final_sum, 2) if self.current_results else "?"
            p_canvas.create_text(ox + 580, oy + 280,
                                  text=f"خروجی تصحیح شده نهایی: {final_sum}  (={dec_digit})",
                                  font=("Consolas", 11, "bold"), fill=ACCENT_GREEN)

            raw_sum_local = d1 + d2
            note = "⚠ تصحیح +۶ فعال شد" if raw_sum_local > 9 else "✓ بدون نیاز به تصحیح"
            note_color = ACCENT_PINK if raw_sum_local > 9 else ACCENT_GREEN
            p_canvas.create_text(ox + 580, oy + 305, text=note, font=("Tahoma", 9, "bold"), fill=note_color)

            p_canvas.configure(scrollregion=(0, 0, max(c_width, content_width + ox + 40),
                                              max(c_height, content_height + oy + 40)))

        p_canvas.bind("<Configure>", center_content)
        center_content()

    def trigger_redraw(self):
        if self.current_results:
            self.draw_schematic(self.max_len, self.pad_num1, self.pad_num2,
                                 self.current_results["carries"], self.current_results["final_bcd"])
            self.draw_waveforms()
            self._draw_progress()

    def draw_schematic(self, num_digits, pad_num1, pad_num2, list_carries, list_final_bcd,
                        active_canvas_idx: int = -1, animation_phase: int = 0, active_bit_idx: int = -1):
        self.canvas_circuit.delete("all")
        canvas_width = max(self.canvas_circuit.winfo_width(), 400)

        start_y, block_width, block_height, gap_x = 80, 170, 130, 90
        total_circuit_width = num_digits * block_width + (num_digits - 1) * gap_x
        start_x = (canvas_width - total_circuit_width) // 2 if canvas_width > total_circuit_width + 100 else 50

        self.canvas_circuit.config(scrollregion=(0, 0, max(canvas_width, total_circuit_width + start_x + 100), 360))

        for gx in range(0, max(canvas_width, total_circuit_width + start_x + 100), 40):
            self.canvas_circuit.create_line(gx, 0, gx, 360, fill=BORDER_SOFT, width=1)

        cin_active = active_canvas_idx >= 0
        cin_color = ACCENT_CYAN_D if (cin_active and active_canvas_idx == 0 and animation_phase >= 2) else (
            ACCENT_AMBER if cin_active else TEXT_FAINT)
        self.canvas_circuit.create_line(start_x - 50, start_y + 65, start_x, start_y + 65,
                                         arrow=tk.LAST, fill=cin_color, width=2.5 if cin_active else 1.5)
        self.canvas_circuit.create_text(start_x - 28, start_y + 48, text="Cin (0)",
                                         font=("Tahoma", 8, "bold"), fill=cin_color)

        for idx in range(num_digits):
            logic_idx = num_digits - 1 - idx
            x = start_x + idx * (block_width + gap_x)

            if active_canvas_idx == -1:
                bg_color, border_color, border_w = BG_PANEL2, ACCENT_CYAN_D, 2
            elif idx == active_canvas_idx:
                if animation_phase == 1:
                    bg_color, border_color, border_w = "#fdecd8", ACCENT_ORANGE, 3
                elif animation_phase == 2:
                    bg_color, border_color, border_w = "#fbe1ee", ACCENT_PINK, 3
                else:
                    bg_color, border_color, border_w = "#fdf0d5", ACCENT_AMBER, 3
            elif idx < active_canvas_idx:
                bg_color, border_color, border_w = "#e6f7ef", ACCENT_GREEN, 1.5
            else:
                bg_color, border_color, border_w = "#f3f4f8", BORDER, 1

            self._round_rect(self.canvas_circuit, x + 3, start_y + 4, x + block_width + 3, start_y + block_height + 4,
                              r=16, fill="#d8dce6", outline="")

            rect_id = self._round_rect(self.canvas_circuit, x, start_y, x + block_width, start_y + block_height,
                                        r=16, fill=bg_color, outline=border_color, width=border_w)

            if idx == active_canvas_idx and active_canvas_idx != -1:
                glow_r = 3 + abs(math.sin(self._glow_phase)) * 2
                self._round_rect(self.canvas_circuit, x - glow_r, start_y - glow_r,
                                  x + block_width + glow_r, start_y + block_height + glow_r,
                                  r=18, fill="", outline=border_color, width=1)

            self.canvas_circuit.tag_bind(rect_id, "<Button-1>",
                                          lambda event, l_idx=logic_idx: self.open_gate_level_popup(l_idx))
            self.canvas_circuit.tag_bind(rect_id, "<Enter>", lambda e: self.canvas_circuit.config(cursor="hand2"))
            self.canvas_circuit.tag_bind(rect_id, "<Leave>", lambda e: self.canvas_circuit.config(cursor=""))

            text_id = self.canvas_circuit.create_text(x + block_width / 2, start_y + 18,
                                                        text=f"بلوک رقم {logic_idx}", font=("Tahoma", 9, "bold"),
                                                        fill=ACCENT_CYAN_D)
            self.canvas_circuit.tag_bind(text_id, "<Button-1>",
                                          lambda event, l_idx=logic_idx: self.open_gate_level_popup(l_idx))

            d1, d2 = int(pad_num1[idx]), int(pad_num2[idx])
            b1_str, b2_str = f"{d1:04b}", f"{d2:04b}"
            _, dg, dp = self.generate_cla_carry(b1_str, b2_str, 0)

            for b_i in range(4):
                bit_x_offset = x + 28 + (b_i * 37)
                is_bit_pulsing = (idx == active_canvas_idx and animation_phase == 1 and b_i == active_bit_idx)
                bit_color = ACCENT_PINK if is_bit_pulsing else (
                    ACCENT_CYAN_D if active_canvas_idx == -1 or idx <= active_canvas_idx else TEXT_FAINT)
                bit_font = ("Consolas", 9, "bold" if is_bit_pulsing else "normal")

                show_bits = (active_canvas_idx == -1 or idx < active_canvas_idx or
                             (idx == active_canvas_idx and b_i <= active_bit_idx))
                a_bit_val = b1_str[b_i] if show_bits else "?"
                b_bit_val = b2_str[b_i] if show_bits else "?"

                self.canvas_circuit.create_text(bit_x_offset, start_y + 45, text=f"a{3 - b_i}:{a_bit_val}",
                                                 font=bit_font, fill=bit_color)
                self.canvas_circuit.create_text(bit_x_offset, start_y + 61, text=f"b{3 - b_i}:{b_bit_val}",
                                                 font=bit_font, fill=bit_color)

                if is_bit_pulsing:
                    self.canvas_circuit.create_oval(bit_x_offset - 16, start_y + 33, bit_x_offset + 16,
                                                      start_y + 71, outline=ACCENT_ORANGE, width=1.5)

            if active_canvas_idx == -1 or idx <= active_canvas_idx:
                pg_color = ACCENT_ORANGE if (idx == active_canvas_idx and animation_phase == 2) else TEXT_DIM
                self.canvas_circuit.create_text(x + block_width / 2, start_y + 86, text=f"G={dg}  P={dp}",
                                                 font=("Consolas", 9, "bold"), fill=pg_color)

                needs_correction = d1 + d2 > 9
                show_corrected = (active_canvas_idx == -1 or idx < active_canvas_idx or
                                   (idx == active_canvas_idx and animation_phase == 3))
                core_status = "تصحیح +۶" if (needs_correction and show_corrected) else "بدون تغییر"
                status_color = ACCENT_PINK if core_status == "تصحیح +۶" else ACCENT_AMBER
                self.canvas_circuit.create_text(x + block_width / 2, start_y + 108, text=f"وضعیت: {core_status}",
                                                 font=("Tahoma", 8, "bold"), fill=status_color)

            self.canvas_circuit.create_line(x + 42, start_y - 38, x + 42, start_y, arrow=tk.LAST,
                                             fill=TEXT_DIM, width=1.5)
            self.canvas_circuit.create_text(x + 42, start_y - 50, text=f"A:{d1}", font=("Tahoma", 9, "bold"),
                                             fill=TEXT_MAIN)
            self.canvas_circuit.create_line(x + block_width - 42, start_y - 38, x + block_width - 42, start_y,
                                             arrow=tk.LAST, fill=TEXT_DIM, width=1.5)
            self.canvas_circuit.create_text(x + block_width - 42, start_y - 50, text=f"B:{d2}",
                                             font=("Tahoma", 9, "bold"), fill=TEXT_MAIN)

            if idx < num_digits - 1:
                next_x = x + block_width
                line_active = (active_canvas_idx >= 0 and (idx < active_canvas_idx or
                               (idx == active_canvas_idx and animation_phase >= 2)))
                line_color = ACCENT_ORANGE if (active_canvas_idx >= 0 and idx == active_canvas_idx and
                                                animation_phase == 2) else (ACCENT_AMBER if line_active else TEXT_FAINT)
                line_w = 3 if (active_canvas_idx >= 0 and idx == active_canvas_idx and animation_phase == 2) else (
                    2 if line_active else 1)

                carry_val = list_carries[num_digits - 1 - idx]
                self.canvas_circuit.create_line(next_x, start_y + 65, next_x + gap_x, start_y + 65,
                                                 arrow=tk.LAST, fill=line_color, width=line_w)
                self.canvas_circuit.create_text(next_x + gap_x / 2, start_y + 45, text=f"C{logic_idx}: {carry_val}",
                                                 font=("Consolas", 9, "bold"), fill=line_color)

            if active_canvas_idx == -1 or idx < active_canvas_idx or (idx == active_canvas_idx and animation_phase == 3):
                out_bcd = list_final_bcd[idx]
                self.canvas_circuit.create_line(x + block_width / 2, start_y + block_height,
                                                 x + block_width / 2, start_y + block_height + 28,
                                                 arrow=tk.LAST, fill=ACCENT_AMBER, width=2)
                self.canvas_circuit.create_text(x + block_width / 2, start_y + block_height + 42,
                                                 text=f"S: {out_bcd}", font=("Consolas", 10, "bold"), fill="#92400e")

        final_x = start_x + num_digits * (block_width + gap_x) - gap_x
        cout_color = ACCENT_AMBER if active_canvas_idx == num_digits - 1 and animation_phase == 3 else (
            ACCENT_CYAN_D if active_canvas_idx == -1 else TEXT_FAINT)
        self.canvas_circuit.create_line(final_x, start_y + 65, final_x + 48, start_y + 65, arrow=tk.LAST,
                                         fill=cout_color, width=2.5 if cout_color != TEXT_FAINT else 1)
        self.canvas_circuit.create_text(final_x + 30, start_y + 45, text=f"Cout\n({list_carries[num_digits]})",
                                         font=("Tahoma", 8, "bold"), fill=cout_color, justify="center")

    def draw_waveforms(self):
        self.canvas_wave.delete("all")
        w_width = self.canvas_wave.winfo_width()
        if w_width < 100:
            w_width = 900

        signals = [("G", "تولید حمل", ACCENT_ORANGE), ("P", "انتقال حمل", ACCENT_CYAN_D),
                   ("Cin", "ورودی", ACCENT_PURPLE), ("Cout", "خروجی", ACCENT_AMBER)]
        step_x = 150
        total_wave_width = 130 + (max(self.max_len, 1) * step_x)
        scroll_w = max(w_width, total_wave_width)

        self.canvas_wave.config(scrollregion=(0, 0, scroll_w, 190))

        for gx in range(120, scroll_w, step_x):
            self.canvas_wave.create_line(gx, 5, gx, 185, fill=BORDER_SOFT, width=1)

        for i, (short, sig, color) in enumerate(signals):
            y_base = 25 + i * 38
            self.canvas_wave.create_text(15, y_base + 10, text=f"{short} ({sig})", font=("Tahoma", 8, "bold"),
                                          fill=color, anchor="w")
            self.canvas_wave.create_line(115, y_base + 5, scroll_w - 20, y_base + 5, fill=BORDER, dash=(2, 3))
            self.canvas_wave.create_line(115, y_base + 22, scroll_w - 20, y_base + 22, fill=BORDER, dash=(2, 3))

        if not self.current_results:
            return

        for idx in range(self.max_len):
            logic_idx = self.max_len - 1 - idx
            x_start = 130 + idx * step_x
            x_end = x_start + step_x - 10

            d1, d2 = int(self.pad_num1[idx]), int(self.pad_num2[idx])
            _, dg, dp = self.generate_cla_carry(f"{d1:04b}", f"{d2:04b}", 0)

            cin_val = self.current_results["carries"][logic_idx]
            cout_val = self.current_results["carries"][logic_idx + 1]

            if self.anim_active and idx > self.current_canvas_idx:
                continue

            vals = [dg, dp, cin_val, cout_val]
            colors = [ACCENT_ORANGE, ACCENT_CYAN_D, ACCENT_PURPLE, ACCENT_AMBER]
            for i, val in enumerate(vals):
                y_base = 25 + i * 38
                y_val = y_base + 5 if val == 1 else y_base + 22
                seg_color = colors[i] if val == 1 else TEXT_FAINT

                self.canvas_wave.create_line(x_start, y_val, x_end, y_val, fill=seg_color, width=2.5)

                if idx > 0:
                    prev_d1, prev_d2 = int(self.pad_num1[idx - 1]), int(self.pad_num2[idx - 1])
                    _, pdg, pdp = self.generate_cla_carry(f"{prev_d1:04b}", f"{prev_d2:04b}", 0)
                    p_vals = [pdg, pdp, self.current_results["carries"][self.max_len - idx],
                              self.current_results["carries"][self.max_len - idx + 1]]
                    p_val = p_vals[i]
                    p_y = y_base + 5 if p_val == 1 else y_base + 22
                    edge_color = colors[i] if val != p_val else TEXT_FAINT
                    self.canvas_wave.create_line(x_start, p_y, x_start, y_val, fill=edge_color, width=2)

            highlight = self.anim_active and idx == self.current_canvas_idx
            label_color = ACCENT_AMBER if highlight else TEXT_DIM
            self.canvas_wave.create_text(x_start + (x_end - x_start) / 2, 12, text=f"رقم {logic_idx}",
                                          font=("Tahoma", 8, "bold"), fill=label_color)

    def _draw_progress(self):
        c = self.progress_canvas
        c.delete("all")
        w = c.winfo_width()
        if w < 10 or self.max_len == 0:
            return
        self._round_rect(c, 0, 0, w, 8, r=4, fill=BG_FIELD, outline=BORDER)

        total_steps = max(self.max_len * 6, 1)  # 4 bit-phases + phase2 + phase3 per digit
        mid_animation = self.current_canvas_idx > 0 or self.current_phase > 1 or self.current_bit_idx > 0
        if self.anim_active or mid_animation:
            step_done = (self.current_canvas_idx * 6
                         + (self.current_bit_idx if self.current_phase == 1 else 4)
                         + (self.current_phase - 1))
            frac = min(step_done / total_steps, 1.0)
        else:
            frac = 1.0 if self.current_results else 0.0

        if frac > 0:
            self._round_rect(c, 0, 0, max(w * frac, 8), 8, r=4, fill=ACCENT_AMBER, outline="")

        if self.anim_active or mid_animation:
            self.phase_label.config(
                text=f"رقم فعال: {self.max_len - 1 - self.current_canvas_idx}   •   "
                     f"فاز {self.current_phase}/3 — {PHASE_LABELS[self.current_phase]}")
        else:
            self.phase_label.config(text="")


    def analyze_bcd(self, animate: bool = False):
        if self._after_id:
            self.root.after_cancel(self._after_id)
            self._after_id = None

        str_a = self.entry_num1.get().strip()
        str_b = self.entry_num2.get().strip()

        if not str_a or not str_b:
            messagebox.showerror("ورودی ناقص", "لطفاً هر دو عدد را وارد کنید.")
            return
        if not str_a.isdigit() or not str_b.isdigit():
            messagebox.showerror("سیگنال ورودی نامعتبر",
                                  "لطفاً برای رشته ورودی‌ها صرفاً از ارقام مثبت دهدهی استفاده کنید.")
            return
        if len(str_a) > 18 or len(str_b) > 18:
            messagebox.showwarning("ورودی بسیار بزرگ",
                                    "اعداد بسیار بزرگ ممکن است نمایش گرافیکی را کند یا فشرده کنند. "
                                    "عددی کوتاه‌تر امتحان کنید.")

        self.max_len = max(len(str_a), len(str_b))
        self.pad_num1 = str_a.zfill(self.max_len)
        self.pad_num2 = str_b.zfill(self.max_len)

        self.current_results = self.process_logic(self.pad_num1, self.pad_num2, self.max_len)

        for row in self.tree_analysis.get_children():
            self.tree_analysis.delete(row)
        for i, (row_data, corr_tag) in enumerate(zip(self.current_results["table_rows"],
                                                       self.current_results["row_tags"])):
            stripe = "even" if i % 2 == 0 else "odd"
            self.tree_analysis.insert("", "end", values=row_data, tags=(stripe, corr_tag))

        self.update_hardware_metrics_only()

        dec_sum = int(str_a) + int(str_b)
        bcd_out_stream = "  ".join(self.current_results["final_bcd"])

        self.ui_labels["lbl_final_bcd"].config(text=bcd_out_stream)
        self.ui_labels["lbl_final_dec"].config(text=f"{dec_sum:,}")

        try:
            decoded = int("".join(str(int(chunk, 2)) for chunk in self.current_results["final_bcd"]))
            if self.current_results["carries"][0] == 1:
                decoded += 10 ** self.max_len
            ok = decoded == dec_sum
            self.ui_labels["lbl_verify"].config(
                text=("✓ مطابقت کامل با جمع مرجع پایتون" if ok else f"✖ عدم تطابق! decoded={decoded}"),
                foreground=(ACCENT_GREEN if ok else ACCENT_RED))
        except (ValueError, IndexError):
            self.ui_labels["lbl_verify"].config(text="—", foreground=TEXT_DIM)

        if animate:
            self.start_multi_phase_animation()
        else:
            self.anim_active = False
            self.current_canvas_idx = 0
            self.current_phase = 1
            self.current_bit_idx = 0
            self.ui_labels["lbl_anim_status"].config(text="✓ رندر استاتیک با موفقیت پایان یافت", foreground=ACCENT_GREEN)
            self._set_anim_controls(prev=False, pause=False, resume=False, nxt=False)
            self.trigger_redraw()

    def _set_anim_controls(self, prev: bool, pause: bool, resume: bool, nxt: bool):
        self.btn_prev.config(state="normal" if prev else "disabled")
        self.btn_pause.config(state="normal" if pause else "disabled")
        self.btn_resume.config(state="normal" if resume else "disabled")
        self.btn_next.config(state="normal" if nxt else "disabled")

    def start_multi_phase_animation(self):
        self.anim_active = True
        self.anim_paused = False
        self.current_canvas_idx = 0
        self.current_phase = 1
        self.current_bit_idx = 0

        self._set_anim_controls(prev=True, pause=True, resume=False, nxt=True)
        self.ui_labels["lbl_anim_status"].config(text="⏳ در حال اجرای شبیه‌سازی مالتی‌فاز چپ‌به‌راست...",
                                                   foreground=ACCENT_AMBER)
        self.run_animation_loop()

    def run_animation_loop(self):
        if not self.anim_active or self.anim_paused:
            return

        self.draw_schematic(
            self.max_len, self.pad_num1, self.pad_num2,
            self.current_results["carries"], self.current_results["final_bcd"],
            self.current_canvas_idx, self.current_phase, self.current_bit_idx,
        )
        self.draw_waveforms()
        self._draw_progress()

        if self.current_phase == 1:
            self.current_bit_idx += 1
            if self.current_bit_idx >= 4:
                self.current_phase = 2
        elif self.current_phase == 2:
            self.current_phase = 3
        elif self.current_phase == 3:
            self.current_canvas_idx += 1
            if self.current_canvas_idx >= self.max_len:
                self.anim_active = False
                self.ui_labels["lbl_anim_status"].config(text="✓ شبیه‌سازی انیمیشن با موفقیت خاتمه یافت.",
                                                           foreground=ACCENT_GREEN)
                self._set_anim_controls(prev=False, pause=False, resume=False, nxt=False)
                self.trigger_redraw()
                return
            self.current_phase = 1
            self.current_bit_idx = 0

        self._after_id = self.root.after(max(self.anim_speed.get(), 60), self.run_animation_loop)

    def pause_animation(self):
        if self._after_id:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        self.anim_paused = True
        self._set_anim_controls(prev=True, pause=False, resume=True, nxt=True)
        self.ui_labels["lbl_anim_status"].config(text="⏸ شبیه‌سازی متوقف شد", foreground=ACCENT_ORANGE)

    def resume_animation(self):
        self.anim_paused = False
        self._set_anim_controls(prev=True, pause=True, resume=False, nxt=True)
        self.ui_labels["lbl_anim_status"].config(text="⏳ در حال اجرای شبیه‌سازی مالتی‌فاز چپ‌به‌راست...",
                                                   foreground=ACCENT_AMBER)
        self.run_animation_loop()

    def _redraw_current_step(self):
        self.draw_schematic(
            self.max_len, self.pad_num1, self.pad_num2,
            self.current_results["carries"], self.current_results["final_bcd"],
            self.current_canvas_idx, self.current_phase, self.current_bit_idx,
        )
        self.draw_waveforms()
        self._draw_progress()

    def step_forward(self):
        self.pause_animation()
        if not self.current_results:
            return
        if self.current_phase == 1:
            self.current_bit_idx += 1
            if self.current_bit_idx >= 4:
                self.current_phase = 2
        elif self.current_phase == 2:
            self.current_phase = 3
        elif self.current_phase == 3:
            if self.current_canvas_idx >= self.max_len - 1:
                self.current_canvas_idx = self.max_len - 1
            else:
                self.current_canvas_idx += 1
                self.current_phase = 1
                self.current_bit_idx = 0
        self._redraw_current_step()

    def step_backward(self):
        self.pause_animation()
        if not self.current_results:
            return
        if self.current_phase == 3:
            self.current_phase = 2
        elif self.current_phase == 2:
            self.current_phase = 1
            self.current_bit_idx = 3
        elif self.current_phase == 1:
            self.current_bit_idx -= 1
            if self.current_bit_idx < 0:
                if self.current_canvas_idx <= 0:
                    self.current_canvas_idx = 0
                    self.current_phase = 1
                    self.current_bit_idx = 0
                else:
                    self.current_canvas_idx -= 1
                    self.current_phase = 3
                    self.current_bit_idx = 0
        self._redraw_current_step()


if __name__ == "__main__":
    app_root = tk.Tk()
    app = CLDASimulatorApp(app_root)
    app_root.mainloop()