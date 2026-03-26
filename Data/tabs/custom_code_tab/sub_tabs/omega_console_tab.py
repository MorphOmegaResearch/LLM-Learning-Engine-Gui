"""
Omega Console Tab — ThoughtMatrix Live Projector

A live matplotlib projection pane where you select an omega, fire domains
at its ThoughtMatrix, and watch the activation state manifest — including
a CLI bar to "chat" to the novel state it's building.

Layout:
  TOP RAIL:    omega/domain selectors, Activate / Reset / Mode toggle
  CENTER:      matplotlib canvas (polar radar + cam-height heatmap)
  BOTTOM HALF: response log (left) + pattern activation feed (right)
  CLI BAR:     text entry → chat subprocess → redraw
"""

import json
import sys
import subprocess
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from pathlib import Path
from datetime import datetime

from logger_util import log_message

def log_error(msg): log_message(f"ERROR: {msg}")
def log_exception(msg): log_message(f"EXCEPTION: {msg}")

# ---------------------------------------------------------------------------
# Optional matplotlib (graceful fallback if not installed)
# ---------------------------------------------------------------------------
try:
    import numpy as np
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    _MPL_OK = True
except ImportError:
    _MPL_OK = False

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
_HERE = Path(__file__).parent
_DATA_DIR = _HERE.parent.parent.parent

PY_MANIFEST = _DATA_DIR / "pymanifest" / "py_manifest_augmented.py"
VARIANTS_DIR = _DATA_DIR / "pymanifest" / "variants"
SPAWN_LOG = VARIANTS_DIR / "spawn_log.jsonl"
SCRATCH_PAD = VARIANTS_DIR / "scratch_pad.json"
CAM_GEN = _DATA_DIR / "pymanifest" / "pattern_master" / "3d_generation" / "cam_pattern_gen.py"

# Domain order (10 standard domains used in ThoughtMatrix)
DOMAIN_ORDER = [
    "astronomy", "biology", "chemistry", "computer_science",
    "economics", "history", "literature", "mathematics",
    "philosophy", "physics",
]

# Cam grid band grouping: 4 latitude bands × 8 lobes
# Each band maps 2-3 domains → 8 lobes distributed by score
_BAND_DOMAINS = [
    ["astronomy", "biology"],
    ["chemistry", "computer_science"],
    ["economics", "history"],
    ["literature", "mathematics", "philosophy", "physics"],
]

# Try to import BaseTab
try:
    from tabs.base_tab import BaseTab
except ImportError:
    class BaseTab:  # type: ignore
        def __init__(self, parent, root, style, *args, **kwargs):
            self.parent = parent
            self.root = root
            self.style = style

        def safe_create(self):
            self.create_ui()


class OmegaConsoleTab(BaseTab):
    """Live ThoughtMatrix projector: domain activation radar + cam-height heatmap."""

    def __init__(self, parent, root, style, parent_tab=None):
        super().__init__(parent, root, style)
        self.parent_tab = parent_tab
        self._omega_names: list = []
        self._domain_scores: dict = {d: 0.0 for d in DOMAIN_ORDER}
        self._mode_var: tk.StringVar = None  # set in create_ui
        self._fig = None
        self._canvas = None
        self._ax_radar = None
        self._ax_cam = None

    # ------------------------------------------------------------------
    def create_ui(self):
        log_message("OMEGA_CONSOLE_TAB: Creating UI")
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=0)  # top rail
        self.parent.rowconfigure(1, weight=2)  # center canvas
        self.parent.rowconfigure(2, weight=1)  # bottom halves
        self.parent.rowconfigure(3, weight=0)  # CLI bar

        self._build_top_rail(self.parent)
        self._build_center_canvas(self.parent)
        self._build_bottom_half(self.parent)
        self._build_cli_bar(self.parent)

        self._load_omega_list()
        self._load_domain_scores()
        self._redraw()
        log_message("OMEGA_CONSOLE_TAB: UI created")

    # ------------------------------------------------------------------
    # TOP RAIL
    # ------------------------------------------------------------------
    def _build_top_rail(self, parent):
        rail = ttk.Frame(parent)
        rail.grid(row=0, column=0, sticky=tk.EW, padx=8, pady=(8, 4))

        ttk.Label(rail, text="Omega:").pack(side=tk.LEFT, padx=(0, 3))
        self._omega_var = tk.StringVar(value="(loading…)")
        self._omega_cb = ttk.Combobox(rail, textvariable=self._omega_var,
                                      state='readonly', width=24)
        self._omega_cb.pack(side=tk.LEFT, padx=(0, 8))
        self._omega_cb.bind("<<ComboboxSelected>>", lambda e: self._on_omega_change())

        ttk.Label(rail, text="Domain:").pack(side=tk.LEFT, padx=(0, 3))
        self._domain_var = tk.StringVar(value="All")
        self._domain_cb = ttk.Combobox(rail, textvariable=self._domain_var,
                                       values=["All"] + DOMAIN_ORDER,
                                       state='readonly', width=16)
        self._domain_cb.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(rail, text="▶ Activate Domain", style='Select.TButton',
                   command=self._activate_domain).pack(side=tk.LEFT, padx=3)
        ttk.Button(rail, text="⟳ Reset State", style='Select.TButton',
                   command=self._reset_state).pack(side=tk.LEFT, padx=3)

        ttk.Label(rail, text="  Mode:").pack(side=tk.LEFT, padx=(8, 3))
        self._mode_var = tk.StringVar(value="Chat")
        ttk.Radiobutton(rail, text="Inspect", variable=self._mode_var,
                        value="Inspect").pack(side=tk.LEFT)
        ttk.Radiobutton(rail, text="Chat", variable=self._mode_var,
                        value="Chat").pack(side=tk.LEFT, padx=(4, 0))

    # ------------------------------------------------------------------
    # CENTER: matplotlib canvas
    # ------------------------------------------------------------------
    def _build_center_canvas(self, parent):
        frame = ttk.Frame(parent)
        frame.grid(row=1, column=0, sticky=tk.NSEW, padx=8, pady=4)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        if not _MPL_OK:
            ttk.Label(frame,
                      text="matplotlib / numpy not installed — canvas unavailable.\n"
                           "Install with:  pip install matplotlib numpy").pack(expand=True)
            return

        self._fig = Figure(figsize=(9, 3.5), facecolor="#1e1e1e")

        # Left subplot: polar radar
        self._ax_radar = self._fig.add_subplot(121, polar=True, facecolor="#1e1e1e")
        self._ax_radar.tick_params(colors="#cccccc")

        # Right subplot: cam-height heatmap
        self._ax_cam = self._fig.add_subplot(122, facecolor="#1e1e1e")
        self._ax_cam.tick_params(colors="#cccccc")

        self._canvas = FigureCanvasTkAgg(self._fig, master=frame)
        self._canvas.get_tk_widget().grid(row=0, column=0, sticky=tk.NSEW)

    def _redraw(self):
        if not _MPL_OK or self._canvas is None:
            return
        self._draw_radar()
        self._draw_cam_heatmap()
        self._canvas.draw()

    def _draw_radar(self):
        ax = self._ax_radar
        ax.clear()
        ax.set_facecolor("#1e1e1e")

        N = len(DOMAIN_ORDER)
        angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
        angles_closed = angles + angles[:1]

        scores = [self._domain_scores.get(d, 0.0) for d in DOMAIN_ORDER]
        max_score = max(scores) if any(scores) else 1.0
        norm_scores = [s / max_score for s in scores]
        norm_closed = norm_scores + norm_scores[:1]

        ax.set_theta_offset(np.pi / 2)
        ax.set_theta_direction(-1)
        ax.plot(angles_closed, norm_closed, color="#a78bfa", linewidth=1.5)
        ax.fill(angles_closed, norm_closed, color="#a78bfa", alpha=0.25)
        ax.set_xticks(angles)
        ax.set_xticklabels([d[:4].capitalize() for d in DOMAIN_ORDER],
                           color="#cccccc", size=7)
        ax.set_ylim(0, 1)
        ax.yaxis.set_tick_params(labelcolor="#555555", labelsize=6)
        ax.set_title("Domain Activation", color="#cccccc", size=8, pad=10)
        ax.spines['polar'].set_color("#444444")
        ax.grid(color="#333333", linewidth=0.5)

    def _draw_cam_heatmap(self):
        ax = self._ax_cam
        ax.clear()
        ax.set_facecolor("#1e1e1e")

        cam_grid = self._derive_cam_grid()
        im = ax.imshow(cam_grid, cmap='plasma', vmin=0.0, vmax=2.0, aspect='auto')
        ax.set_yticks([0, 1, 2, 3])
        ax.set_yticklabels(['20°', '40°', '60°', '75°'], color="#cccccc", size=7)
        ax.set_xticks(range(8))
        ax.set_xticklabels([f"L{i+1}" for i in range(8)], color="#cccccc", size=7)
        omega_name = self._omega_var.get() if self._omega_var else "—"
        ax.set_title(f"Physical Encoding: {omega_name}", color="#cccccc", size=8)
        ax.tick_params(colors="#cccccc")
        try:
            self._fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04).ax.yaxis.set_tick_params(
                labelcolor="#cccccc", labelsize=6)
        except Exception:
            pass

    def _derive_cam_grid(self) -> "np.ndarray":
        """Map 10 domain scores → 4×8 cam grid (latitude × lobe)."""
        grid = np.zeros((4, 8), dtype=float)
        for band_idx, band_domains in enumerate(_BAND_DOMAINS):
            band_scores = [self._domain_scores.get(d, 0.0) for d in band_domains]
            max_s = max(band_scores) if band_scores else 0.0
            norm = [s / max_s if max_s > 0 else 0.0 for s in band_scores]
            # Distribute scores across 8 lobes by tiling
            for lobe in range(8):
                grid[band_idx, lobe] = norm[lobe % len(norm)] * 2.0
        return grid

    # ------------------------------------------------------------------
    # BOTTOM HALF: response log (left) + pattern feed (right)
    # ------------------------------------------------------------------
    def _build_bottom_half(self, parent):
        half = ttk.Frame(parent)
        half.grid(row=2, column=0, sticky=tk.NSEW, padx=8, pady=4)
        half.columnconfigure(0, weight=1)
        half.columnconfigure(1, weight=1)
        half.rowconfigure(0, weight=1)

        # LEFT: response log
        resp_frame = ttk.LabelFrame(half, text="📟 Response / Manifest Log", padding=4)
        resp_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 4))
        resp_frame.rowconfigure(0, weight=1)
        resp_frame.columnconfigure(0, weight=1)

        self._resp_log = ScrolledText(resp_frame, height=8, bg="#0d1117", fg="#cccccc",
                                      font=("Courier", 8), state='disabled', wrap=tk.WORD)
        self._resp_log.grid(row=0, column=0, sticky=tk.NSEW)
        self._resp_log.tag_config("user", foreground="#61dafb")
        self._resp_log.tag_config("omega", foreground="#a8d8a8")
        self._resp_log.tag_config("grade", foreground="#e8b04b")
        self._resp_log.tag_config("meta", foreground="#888888")

        # RIGHT: pattern activation feed
        feed_frame = ttk.LabelFrame(half, text="⚡ Pattern Activation Feed", padding=4)
        feed_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=(4, 0))
        feed_frame.rowconfigure(0, weight=1)
        feed_frame.columnconfigure(0, weight=1)

        cols = ("sha", "type", "domain", "score")
        self._pat_tree = ttk.Treeview(feed_frame, columns=cols, show='headings', height=8)
        self._pat_tree.heading("sha", text="SHA")
        self._pat_tree.heading("type", text="Type")
        self._pat_tree.heading("domain", text="Domain")
        self._pat_tree.heading("score", text="Score")
        self._pat_tree.column("sha", width=90, stretch=False)
        self._pat_tree.column("type", width=110, stretch=True)
        self._pat_tree.column("domain", width=90, stretch=True)
        self._pat_tree.column("score", width=50, stretch=False, anchor=tk.E)

        vsb = ttk.Scrollbar(feed_frame, orient=tk.VERTICAL, command=self._pat_tree.yview)
        self._pat_tree.configure(yscrollcommand=vsb.set)
        self._pat_tree.grid(row=0, column=0, sticky=tk.NSEW)
        vsb.grid(row=0, column=1, sticky=tk.NS)

        self._refresh_pattern_feed()

    # ------------------------------------------------------------------
    # CLI BAR
    # ------------------------------------------------------------------
    def _build_cli_bar(self, parent):
        bar = ttk.Frame(parent, padding=(8, 4))
        bar.grid(row=3, column=0, sticky=tk.EW, padx=8, pady=(0, 8))
        bar.columnconfigure(1, weight=1)

        ttk.Label(bar, text="→").grid(row=0, column=0, padx=(0, 4))
        self._cli_var = tk.StringVar()
        self._cli_entry = ttk.Entry(bar, textvariable=self._cli_var)
        self._cli_entry.grid(row=0, column=1, sticky=tk.EW, padx=(0, 4))
        self._cli_entry.bind("<Return>", lambda e: self._cli_send())

        ttk.Button(bar, text="Send", style='Select.TButton',
                   command=self._cli_send).grid(row=0, column=2, padx=3)
        ttk.Button(bar, text="Cam Sim", style='Select.TButton',
                   command=self._run_cam_sim).grid(row=0, column=3, padx=3)

    # ------------------------------------------------------------------
    # Data loading & actions
    # ------------------------------------------------------------------
    def _load_omega_list(self):
        """Populate omega combobox from spawn_log.jsonl."""
        names = []
        if SPAWN_LOG.exists():
            try:
                entries = [json.loads(l) for l in SPAWN_LOG.read_text().splitlines() if l.strip()]
                seen = set()
                for e in reversed(entries):
                    n = e.get("name", "")
                    if n and n not in seen:
                        seen.add(n)
                        names.append(n)
            except Exception as e:
                log_error(f"OMEGA_CONSOLE: spawn_log read error: {e}")

        if not names:
            names = ["omega_v51_base"]
        self._omega_names = names
        self._omega_cb['values'] = names
        self._omega_var.set(names[0])

    def _load_domain_scores(self):
        """Derive domain scores from scratch_pad.json entry counts."""
        if not SCRATCH_PAD.exists():
            return
        try:
            data = json.loads(SCRATCH_PAD.read_text())
            for domain in DOMAIN_ORDER:
                val = data.get(domain, [])
                if isinstance(val, list):
                    self._domain_scores[domain] = float(len(val))
                elif isinstance(val, dict):
                    self._domain_scores[domain] = float(len(val))
                else:
                    self._domain_scores[domain] = 0.0
        except Exception as e:
            log_error(f"OMEGA_CONSOLE: scratch_pad read error: {e}")

    def _refresh_pattern_feed(self):
        """Populate pattern activation feed from latest context_pool."""
        for row in self._pat_tree.get_children():
            self._pat_tree.delete(row)

        pool_files = sorted(VARIANTS_DIR.glob("context_pool_*.json"),
                            key=lambda p: p.stat().st_mtime, reverse=True)
        if not pool_files:
            return
        try:
            data = json.loads(pool_files[0].read_text())
            dedicated = data.get("dedicated_patterns", {})
            rows = []
            for alpha_id, alpha_data in dedicated.items():
                if isinstance(alpha_data, dict):
                    domain_scores = alpha_data.get("domain_scores", {})
                    for domain, score in domain_scores.items():
                        rows.append((alpha_id[:12], "dedicated", domain, float(score or 0)))
                elif isinstance(alpha_data, list):
                    for pat in alpha_data[:5]:
                        if isinstance(pat, dict):
                            rows.append((
                                pat.get("id", "")[:12],
                                pat.get("type", ""),
                                pat.get("origin", "")[:12],
                                float(pat.get("w", 0)),
                            ))
            rows.sort(key=lambda r: r[3], reverse=True)
            for sha, ptype, domain, score in rows[:100]:
                self._pat_tree.insert("", tk.END, values=(sha, ptype, domain, f"{score:.2f}"))
        except Exception as e:
            log_error(f"OMEGA_CONSOLE: context_pool read error: {e}")

    def _on_omega_change(self):
        self._load_domain_scores()
        self._refresh_pattern_feed()
        self._redraw()

    def _activate_domain(self):
        domain = self._domain_var.get()
        if domain == "All":
            self._log_resp(f"[→ activating all domains]\n", "user")
        else:
            # Boost the selected domain score for display
            self._domain_scores[domain] = self._domain_scores.get(domain, 0.0) + 5.0
            self._log_resp(f"[→ domain:{domain} activated]\n", "user")

        self._redraw()

        # Run chat to get a response from the ThoughtMatrix
        if self._mode_var and self._mode_var.get() == "Chat":
            query = f"Tell me about the domain: {domain}"
            self._dispatch_chat(query, domain if domain != "All" else None)

    def _reset_state(self):
        self._domain_scores = {d: 0.0 for d in DOMAIN_ORDER}
        self._load_domain_scores()
        self._log_resp("[⟳ State reset — reloaded from scratch_pad]\n", "meta")
        self._redraw()

    def _cli_send(self):
        text = self._cli_var.get().strip()
        if not text:
            return
        self._cli_var.set("")
        domain = self._domain_var.get()
        if domain == "All":
            domain = None
        self._log_resp(f"[→ {text}]\n", "user")
        self._dispatch_chat(text, domain)

    def _dispatch_chat(self, text: str, domain=None):
        omega_name = self._omega_var.get()
        session = f"omega_console_{omega_name}"
        cmd = [sys.executable, str(PY_MANIFEST), "chat", text, "--session", session]
        if domain:
            cmd += ["--domain", domain]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                               cwd=str(PY_MANIFEST.parent))
            output = (r.stdout + r.stderr).strip()
            self._log_resp(f"[← {output[:600]}]\n", "omega")
            # After chat, reload scores and redraw
            self._load_domain_scores()
            self._refresh_pattern_feed()
            self._redraw()
        except subprocess.TimeoutExpired:
            self._log_resp("[⚠ chat timed out]\n", "grade")
        except Exception as e:
            self._log_resp(f"[✗ {e}]\n", "grade")

    def _run_cam_sim(self):
        """Run cam_pattern_gen.py --through using current domain scores as weights."""
        if not CAM_GEN.exists():
            self._log_resp(f"[⚠ cam_pattern_gen.py not found]\n", "grade")
            return
        weights_str = ",".join(
            f"{d}:{self._domain_scores.get(d, 0.0):.2f}" for d in DOMAIN_ORDER
        )
        cmd = [sys.executable, str(CAM_GEN), "--through", weights_str]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                               cwd=str(CAM_GEN.parent))
            output = (r.stdout + r.stderr).strip()
            self._log_resp(f"[Cam Sim]\n{output[:400]}\n", "grade")
            self._redraw()
        except subprocess.TimeoutExpired:
            self._log_resp("[⚠ cam sim timed out]\n", "grade")
        except Exception as e:
            self._log_resp(f"[✗ cam sim: {e}]\n", "grade")

    def _log_resp(self, text: str, tag: str = "omega"):
        self._resp_log.config(state='normal')
        self._resp_log.insert(tk.END, text, tag)
        self._resp_log.see(tk.END)
        self._resp_log.config(state='disabled')
