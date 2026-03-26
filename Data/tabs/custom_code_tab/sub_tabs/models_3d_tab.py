"""
3D Models Sub-Tab — Tetrahedron Explorer, Audio Manifold, and Workshop.
Provides 3D visualization, geometry exploration, and shape creation with
slicer-compatible export (STL/3MF) for 3D printing.

Puppeteer integration: get_3d_context() exposes current state for GUILLM.
"""

import tkinter as tk
from tkinter import ttk, colorchooser, filedialog, messagebox
from pathlib import Path
import json
import sys
import random
import math
import threading
import time as _time
import os
import difflib
import ast
import hashlib

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from tabs.base_tab import BaseTab
from logger_util import log_message

# ---------------------------------------------------------------------------
# Dependency audit (graceful fallback if missing)
# ---------------------------------------------------------------------------
_DEPS_OK = True
_NP_OK = True
_MPL_OK = True
_STL_OK = False
_TRIMESH_OK = False

try:
    import numpy as np
except ImportError:
    _NP_OK = False
    _DEPS_OK = False
    np = None

try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
except ImportError:
    _MPL_OK = False
    _DEPS_OK = False

try:
    from stl import mesh as stl_mesh
    _STL_OK = True
except ImportError:
    pass

try:
    import trimesh
    _TRIMESH_OK = True
except ImportError:
    pass

# Audio Manifold optional deps
_LIBROSA_OK = False
_SKLEARN_OK = False
_SKIMAGE_OK = False

try:
    import librosa
    import librosa.display
    _LIBROSA_OK = True
except ImportError:
    pass

try:
    from sklearn.manifold import TSNE
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics.pairwise import cosine_similarity
    _SKLEARN_OK = True
except ImportError:
    pass

try:
    from skimage.segmentation import slic
    from skimage.color import rgb2lab
    from skimage import io as skimage_io
    _SKIMAGE_OK = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Audio Manifold data classes
# ---------------------------------------------------------------------------
class _Node:
    """A node in the manifold network."""
    __slots__ = ('id', 'pos', 'time', 'features', 'label')
    def __init__(self, node_id, pos, time_idx, features=None, label=""):
        self.id = node_id
        self.pos = np.array(pos) if np is not None else pos
        self.time = time_idx
        self.features = features if features is not None else (np.array([]) if np else [])
        self.label = label

class _Edge:
    """An edge between two nodes."""
    __slots__ = ('source', 'target', 'weight', 'type')
    def __init__(self, source, target, weight=1.0, edge_type="temporal"):
        self.source = source
        self.target = target
        self.weight = weight
        self.type = edge_type

class _ManifoldModel:
    """Container for a model (audio or image) with nodes and edges."""
    def __init__(self, name, modality):
        self.name = name
        self.modality = modality
        self.nodes = []
        self.edges = []
        self.timeline_max = 0
        self.params = {}

    def add_node(self, node):
        self.nodes.append(node)
        self.timeline_max = max(self.timeline_max, node.time)

    def filter_by_time(self, max_time):
        return [i for i, n in enumerate(self.nodes) if n.time <= max_time]


# ---------------------------------------------------------------------------
# Geometry: 64 Tetrahedron Vector Equilibrium
# ---------------------------------------------------------------------------
def generate_64_tetra_grid():
    """Create 64 tetrahedra by subdividing the 8 tetrahedra that form
    the vector equilibrium (cuboctahedron + centre)."""
    vertices = []
    for x in (-1, 1):
        for y in (-1, 1):
            vertices.append((x, y, 0))
    for x in (-1, 1):
        for z in (-1, 1):
            vertices.append((x, 0, z))
    for y in (-1, 1):
        for z in (-1, 1):
            vertices.append((0, y, z))
    vertices = list(set(vertices))
    centre = (0, 0, 0)

    cube_corners = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
    triangles = [(( cx, cy, 0), (cx, 0, cz), (0, cy, cz)) for cx, cy, cz in cube_corners]
    base_tets = [(centre, t[0], t[1], t[2]) for t in triangles]

    all_tets = []
    for tet in base_tets:
        v0, v1, v2, v3 = [np.array(v) for v in tet]
        m01 = tuple((v0 + v1) / 2)
        m02 = tuple((v0 + v2) / 2)
        m03 = tuple((v0 + v3) / 2)
        m12 = tuple((v1 + v2) / 2)
        m13 = tuple((v1 + v3) / 2)
        m23 = tuple((v2 + v3) / 2)
        v0, v1, v2, v3 = tuple(v0), tuple(v1), tuple(v2), tuple(v3)
        all_tets.extend([
            (v0, m01, m02, m03), (v1, m01, m12, m13),
            (v2, m02, m12, m23), (v3, m03, m13, m23),
            (m01, m02, m03, m23), (m01, m02, m12, m23),
            (m01, m12, m13, m23), (m01, m03, m13, m23),
        ])
    return all_tets


# ---------------------------------------------------------------------------
# Geometry: Workshop primitives
# ---------------------------------------------------------------------------
def make_cube(size=1.0):
    """Return (vertices Nx3, faces Mx3) for a cube."""
    s = size / 2
    verts = np.array([
        [-s, -s, -s], [s, -s, -s], [s, s, -s], [-s, s, -s],
        [-s, -s, s], [s, -s, s], [s, s, s], [-s, s, s],
    ])
    faces = np.array([
        [0,1,2], [0,2,3], [4,6,5], [4,7,6],
        [0,5,1], [0,4,5], [2,7,3], [2,6,7],
        [0,3,7], [0,7,4], [1,5,6], [1,6,2],
    ])
    return verts, faces


def make_sphere(radius=0.5, res=16):
    """UV sphere."""
    verts = []
    for i in range(res + 1):
        lat = math.pi * i / res
        for j in range(res + 1):
            lon = 2 * math.pi * j / res
            x = radius * math.sin(lat) * math.cos(lon)
            y = radius * math.sin(lat) * math.sin(lon)
            z = radius * math.cos(lat)
            verts.append([x, y, z])
    verts = np.array(verts)
    faces = []
    for i in range(res):
        for j in range(res):
            p1 = i * (res + 1) + j
            p2 = p1 + (res + 1)
            faces.append([p1, p2, p1 + 1])
            faces.append([p1 + 1, p2, p2 + 1])
    return verts, np.array(faces)


def make_cylinder(radius=0.5, height=1.0, res=24):
    """Cylinder with caps."""
    verts = []
    faces = []
    h2 = height / 2
    # Side vertices
    for i in range(res):
        a = 2 * math.pi * i / res
        x, y = radius * math.cos(a), radius * math.sin(a)
        verts.append([x, y, -h2])
        verts.append([x, y, h2])
    # Center caps
    bot_c = len(verts)
    verts.append([0, 0, -h2])
    top_c = len(verts)
    verts.append([0, 0, h2])
    verts = np.array(verts)
    for i in range(res):
        n = (i + 1) % res
        b, t, nb, nt = i * 2, i * 2 + 1, n * 2, n * 2 + 1
        faces.extend([[b, nb, t], [t, nb, nt]])
        faces.extend([[b, bot_c, nb], [t, nt, top_c]])
    return verts, np.array(faces)


def make_cone(radius=0.5, height=1.0, res=24):
    """Cone with base cap."""
    verts = []
    faces = []
    h2 = height / 2
    for i in range(res):
        a = 2 * math.pi * i / res
        verts.append([radius * math.cos(a), radius * math.sin(a), -h2])
    apex = len(verts)
    verts.append([0, 0, h2])
    base_c = len(verts)
    verts.append([0, 0, -h2])
    verts = np.array(verts)
    for i in range(res):
        n = (i + 1) % res
        faces.append([i, n, apex])
        faces.append([i, base_c, n])
    return verts, np.array(faces)


def make_torus(R=0.7, r=0.25, res_u=24, res_v=12):
    """Torus (R = major, r = minor)."""
    verts = []
    for i in range(res_u):
        u = 2 * math.pi * i / res_u
        for j in range(res_v):
            v = 2 * math.pi * j / res_v
            x = (R + r * math.cos(v)) * math.cos(u)
            y = (R + r * math.cos(v)) * math.sin(u)
            z = r * math.sin(v)
            verts.append([x, y, z])
    verts = np.array(verts)
    faces = []
    for i in range(res_u):
        ni = (i + 1) % res_u
        for j in range(res_v):
            nj = (j + 1) % res_v
            p1 = i * res_v + j
            p2 = ni * res_v + j
            p3 = ni * res_v + nj
            p4 = i * res_v + nj
            faces.extend([[p1, p2, p3], [p1, p3, p4]])
    return verts, np.array(faces)


SHAPE_GENERATORS = {
    "Cube": make_cube,
    "Sphere": make_sphere,
    "Cylinder": make_cylinder,
    "Cone": make_cone,
    "Torus": make_torus,
}

# Default library root — Documents/Models if present, else this file's project root
_DEFAULT_LIB_ROOT = Path.home() / "Documents" / "Models"
if not _DEFAULT_LIB_ROOT.exists():
    _DEFAULT_LIB_ROOT = Path(__file__).parent.parent.parent.parent / "3D_Models"


def _parse_stl(filepath):
    """
    Pure-Python binary STL parser — no external deps beyond numpy.
    Returns (verts ndarray shape (N,3), faces ndarray shape (M,3)).
    Handles both binary and ASCII STL.
    """
    import struct
    data = Path(filepath).read_bytes()

    # --- ASCII STL (starts with 'solid ' and not big enough for binary) ---
    try:
        text = data.decode('utf-8', errors='ignore')
        if text.lstrip().startswith('solid') and 'facet normal' in text:
            verts = []
            for line in text.splitlines():
                line = line.strip()
                if line.startswith('vertex '):
                    parts = line.split()
                    verts.append([float(parts[1]), float(parts[2]), float(parts[3])])
            if verts:
                v = np.array(verts, dtype=np.float64)
                f = np.arange(len(v), dtype=np.int32).reshape(-1, 3)
                return v, f
    except Exception:
        pass

    # --- Binary STL ---
    if len(data) < 84:
        raise ValueError("File too small to be a valid STL")
    n_tri = struct.unpack_from('<I', data, 80)[0]
    expected = 84 + n_tri * 50
    if len(data) < expected:
        raise ValueError(f"Binary STL truncated: expected {expected} bytes, got {len(data)}")

    # Vectorised read: each triangle = 12 bytes normal + 36 bytes verts + 2 bytes attr = 50 bytes
    # Build a structured dtype and use frombuffer
    tri_dtype = np.dtype([
        ('normal', '<3f4'),
        ('v0', '<3f4'),
        ('v1', '<3f4'),
        ('v2', '<3f4'),
        ('attr', '<u2'),
    ])
    triangles = np.frombuffer(data, dtype=tri_dtype, count=n_tri, offset=84)
    # Stack into (n_tri, 3, 3) then flatten to (n_tri*3, 3)
    verts = np.column_stack([
        triangles['v0'], triangles['v1'], triangles['v2']
    ]).reshape(-1, 3).astype(np.float64)
    # BUG-guard: column_stack gives shape (n,9) — need stack along axis 1 differently
    verts = np.stack([triangles['v0'], triangles['v1'], triangles['v2']], axis=1).reshape(-1, 3).astype(np.float64)
    faces = np.arange(len(verts), dtype=np.int32).reshape(-1, 3)
    return verts, faces


# ===========================================================================
# Models3DTab
# ===========================================================================
class Models3DTab(BaseTab):
    """3D Models sub-tab with Tetrahedron Explorer, Audio Manifold, Workshop."""

    def __init__(self, parent, root, style, parent_tab=None):
        super().__init__(parent, root, style)
        self.parent_tab = parent_tab
        self.config_dir = Path(__file__).parent.parent / "models_3d_data"

    def create_ui(self):
        log_message("MODELS_3D: Creating UI...")

        if not _DEPS_OK:
            self._show_missing_deps()
            return

        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)

        self.notebook = ttk.Notebook(self.parent)
        self.notebook.grid(row=0, column=0, sticky=tk.NSEW)
        self.bind_sub_notebook(self.notebook, label='3D Models')

        # Sub-view 1: Tetrahedron Explorer
        self.tetra_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tetra_frame, text="Tetrahedron Explorer")
        self._build_tetrahedron_view(self.tetra_frame)

        # Sub-view 2: Audio Manifold
        self.manifold_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.manifold_frame, text="Audio Manifold")
        self._build_manifold_view(self.manifold_frame)

        # Sub-view 3: Workshop
        self.workshop_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.workshop_frame, text="Workshop")
        self._build_workshop_view(self.workshop_frame)

        # Sub-view 4: Model Library
        self.library_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.library_frame, text="Model Library")
        self._build_library_view(self.library_frame)

        # Sub-view 5: ScratchPad Lab
        self.scratchpad_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.scratchpad_frame, text="ScratchPad Lab")
        self._build_scratchpad_lab(self.scratchpad_frame)

        # Sub-view 6: Ω Lens
        self.omega_lens_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.omega_lens_frame, text="\u03a9 Lens")
        self._build_omega_lens(self.omega_lens_frame)

        self.register_feature("models_3d_tab", status="active")
        log_message("MODELS_3D: UI created successfully")

    def _show_missing_deps(self):
        """Show error if numpy/matplotlib not available."""
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)
        msg = "Missing required dependencies:\n"
        if not _NP_OK:
            msg += "  - numpy (pip install numpy)\n"
        if not _MPL_OK:
            msg += "  - matplotlib (pip install matplotlib)\n"
        lbl = ttk.Label(self.parent, text=msg, font=("Arial", 12),
                         justify=tk.CENTER)
        lbl.grid(row=0, column=0, padx=20, pady=40)

    # ===================================================================
    # Context Feed (Puppeteer integration)
    # ===================================================================
    def get_3d_context(self) -> dict:
        """Return current 3D state for GUILLM context manager."""
        ctx = {
            "active_view": None,
            "workshop_shapes": [],
            "tetra_count": 0,
        }
        if hasattr(self, 'notebook'):
            try:
                ctx["active_view"] = self.notebook.tab(self.notebook.select(), "text")
            except Exception:
                pass
        if hasattr(self, '_tetrahedra'):
            ctx["tetra_count"] = len(self._tetrahedra)
        if hasattr(self, '_ws_shapes'):
            for sid, s in self._ws_shapes.items():
                ctx["workshop_shapes"].append({
                    "id": sid, "type": s["type"],
                    "translate": s["translate"], "color": s["color"],
                })
        return ctx

    # ===================================================================
    # TETRAHEDRON EXPLORER
    # ===================================================================
    def _build_tetrahedron_view(self, parent):
        parent.columnconfigure(0, weight=3)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)

        # --- Left: matplotlib canvas ---
        plot_frame = ttk.Frame(parent)
        plot_frame.grid(row=0, column=0, sticky=tk.NSEW)
        plot_frame.rowconfigure(0, weight=1)
        plot_frame.columnconfigure(0, weight=1)

        self._t_fig = Figure(figsize=(8, 8), facecolor='black')
        self._t_ax = self._t_fig.add_subplot(111, projection='3d', facecolor='black')
        self._t_ax.axis('off')

        self._t_canvas = FigureCanvasTkAgg(self._t_fig, master=plot_frame)
        self._t_canvas.get_tk_widget().grid(row=0, column=0, sticky=tk.NSEW)

        tb_frame = ttk.Frame(plot_frame)
        tb_frame.grid(row=1, column=0, sticky=tk.EW)
        tb = NavigationToolbar2Tk(self._t_canvas, tb_frame)
        tb.update()

        # Mouse wheel zoom
        widget = self._t_canvas.get_tk_widget()
        widget.bind("<Button-4>", self._tetra_scroll)
        widget.bind("<Button-5>", self._tetra_scroll)
        widget.bind("<MouseWheel>", self._tetra_scroll)

        # --- Right: controls ---
        ctrl = ttk.Frame(parent, padding=10)
        ctrl.grid(row=0, column=1, sticky=tk.NSEW)

        ttk.Label(ctrl, text="Tetrahedron Controls", font=("Arial", 12, "bold")).pack(pady=(0, 10))

        # Color
        ttk.Label(ctrl, text="Appearance", font=("Arial", 10, "underline")).pack(anchor=tk.W, pady=(5, 5))
        color_f = ttk.Frame(ctrl)
        color_f.pack(fill=tk.X, pady=2)
        ttk.Label(color_f, text="Color:").pack(side=tk.LEFT)
        self._t_color = tk.StringVar(value="#ffaa00")
        self._t_color_lbl = ttk.Label(color_f, text="#ffaa00", width=10)
        self._t_color_lbl.pack(side=tk.RIGHT, padx=5)
        ttk.Button(color_f, text="Pick", command=self._tetra_pick_color).pack(side=tk.RIGHT)

        self._t_random = tk.BooleanVar(value=False)
        ttk.Checkbutton(ctrl, text="Random colors", variable=self._t_random).pack(anchor=tk.W, pady=2)

        # Line width
        lw_f = ttk.Frame(ctrl)
        lw_f.pack(fill=tk.X, pady=2)
        ttk.Label(lw_f, text="Line Width:").pack(side=tk.LEFT)
        self._t_lw = tk.DoubleVar(value=1.0)
        ttk.Scale(lw_f, from_=0.5, to=3.0, variable=self._t_lw, orient=tk.HORIZONTAL).pack(
            side=tk.RIGHT, fill=tk.X, expand=True)

        # Opacity
        op_f = ttk.Frame(ctrl)
        op_f.pack(fill=tk.X, pady=2)
        ttk.Label(op_f, text="Opacity:").pack(side=tk.LEFT)
        self._t_alpha = tk.DoubleVar(value=0.8)
        ttk.Scale(op_f, from_=0.1, to=1.0, variable=self._t_alpha, orient=tk.HORIZONTAL).pack(
            side=tk.RIGHT, fill=tk.X, expand=True)

        # View
        ttk.Label(ctrl, text="View", font=("Arial", 10, "underline")).pack(anchor=tk.W, pady=(10, 5))
        el_f = ttk.Frame(ctrl)
        el_f.pack(fill=tk.X, pady=2)
        ttk.Label(el_f, text="Elevation:").pack(side=tk.LEFT)
        self._t_elev = tk.DoubleVar(value=30)
        ttk.Scale(el_f, from_=0, to=90, variable=self._t_elev, orient=tk.HORIZONTAL).pack(
            side=tk.RIGHT, fill=tk.X, expand=True)
        az_f = ttk.Frame(ctrl)
        az_f.pack(fill=tk.X, pady=2)
        ttk.Label(az_f, text="Azimuth:").pack(side=tk.LEFT)
        self._t_azim = tk.DoubleVar(value=45)
        ttk.Scale(az_f, from_=0, to=360, variable=self._t_azim, orient=tk.HORIZONTAL).pack(
            side=tk.RIGHT, fill=tk.X, expand=True)

        self._t_axes = tk.BooleanVar(value=False)
        ttk.Checkbutton(ctrl, text="Show Axes", variable=self._t_axes,
                         command=self._tetra_toggle_axes).pack(anchor=tk.W, pady=2)
        self._t_grid = tk.BooleanVar(value=False)
        ttk.Checkbutton(ctrl, text="Show Grid", variable=self._t_grid,
                         command=self._tetra_toggle_grid).pack(anchor=tk.W, pady=2)

        ttk.Button(ctrl, text="Reset View", command=self._tetra_reset).pack(pady=5)
        ttk.Button(ctrl, text="Update Plot", command=self._tetra_redraw).pack(pady=5)

        # File ops
        ttk.Label(ctrl, text="File", font=("Arial", 10, "underline")).pack(anchor=tk.W, pady=(10, 5))
        fb = ttk.Frame(ctrl)
        fb.pack(fill=tk.X, pady=2)
        ttk.Button(fb, text="Save Config", command=self._tetra_save).pack(side=tk.LEFT, padx=2)
        ttk.Button(fb, text="Load Config", command=self._tetra_load).pack(side=tk.LEFT, padx=2)
        ttk.Button(fb, text="Save PNG", command=self._tetra_export_png).pack(side=tk.LEFT, padx=2)

        # Generate and draw
        self._tetrahedra = generate_64_tetra_grid()
        self._t_lines = []
        self._tetra_redraw()

    def _tetra_redraw(self):
        ax = self._t_ax
        ax.clear()
        ax.set_facecolor('black')
        if not self._t_axes.get():
            ax.axis('off')
        ax.grid(self._t_grid.get())
        self._t_lines = []

        use_random = self._t_random.get()
        if use_random:
            colors = plt.cm.tab20(np.linspace(0, 1, len(self._tetrahedra)))
        else:
            gc = self._t_color.get()

        lw = self._t_lw.get()
        alpha = self._t_alpha.get()

        for i, tet in enumerate(self._tetrahedra):
            c = colors[i] if use_random else gc
            edges = [(tet[a], tet[b]) for a, b in
                     [(0,1),(0,2),(0,3),(1,2),(1,3),(2,3)]]
            for e in edges:
                xs = [e[0][0], e[1][0]]
                ys = [e[0][1], e[1][1]]
                zs = [e[0][2], e[1][2]]
                line, = ax.plot(xs, ys, zs, color=c, linewidth=lw, alpha=alpha)
                self._t_lines.append(line)

        ax.view_init(elev=self._t_elev.get(), azim=self._t_azim.get())
        r = 1.2
        ax.set_xlim(-r, r)
        ax.set_ylim(-r, r)
        ax.set_zlim(-r, r)
        self._t_canvas.draw_idle()

    def _tetra_scroll(self, event):
        scale = 1.1 if (getattr(event, 'delta', 0) > 0 or getattr(event, 'num', 0) == 4) else 0.9
        for getter, setter in [(self._t_ax.get_xlim, self._t_ax.set_xlim),
                                (self._t_ax.get_ylim, self._t_ax.set_ylim),
                                (self._t_ax.get_zlim, self._t_ax.set_zlim)]:
            lo, hi = getter()
            mid = (lo + hi) / 2
            half = (hi - lo) / 2 * scale
            setter([mid - half, mid + half])
        self._t_canvas.draw_idle()

    def _tetra_pick_color(self):
        result = colorchooser.askcolor(initialcolor=self._t_color.get())
        if result[1]:
            self._t_color.set(result[1])
            self._t_color_lbl.config(text=result[1])

    def _tetra_toggle_axes(self):
        self._t_ax.axis('on' if self._t_axes.get() else 'off')
        self._t_canvas.draw_idle()

    def _tetra_toggle_grid(self):
        self._t_ax.grid(self._t_grid.get())
        self._t_canvas.draw_idle()

    def _tetra_reset(self):
        self._t_elev.set(30)
        self._t_azim.set(45)
        self._tetra_redraw()

    def _tetra_save(self):
        fp = filedialog.asksaveasfilename(defaultextension=".json",
                                           filetypes=[("JSON", "*.json")])
        if not fp:
            return
        data = {
            "ui_settings": {
                "global_color": self._t_color.get(),
                "random_colors": self._t_random.get(),
                "line_width": self._t_lw.get(),
                "opacity": self._t_alpha.get(),
                "elev": self._t_elev.get(),
                "azim": self._t_azim.get(),
            }
        }
        Path(fp).write_text(json.dumps(data, indent=2), encoding='utf-8')
        messagebox.showinfo("Saved", f"Config saved to {fp}")

    def _tetra_load(self):
        fp = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not fp:
            return
        try:
            data = json.loads(Path(fp).read_text(encoding='utf-8'))
            s = data.get("ui_settings", {})
            self._t_color.set(s.get("global_color", "#ffaa00"))
            self._t_color_lbl.config(text=self._t_color.get())
            self._t_random.set(s.get("random_colors", False))
            self._t_lw.set(s.get("line_width", 1.0))
            self._t_alpha.set(s.get("opacity", 0.8))
            self._t_elev.set(s.get("elev", 30))
            self._t_azim.set(s.get("azim", 45))
            self._tetra_redraw()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _tetra_export_png(self):
        fp = filedialog.asksaveasfilename(defaultextension=".png",
                                           filetypes=[("PNG", "*.png")])
        if fp:
            self._t_fig.savefig(fp, dpi=300, bbox_inches='tight', facecolor='black')
            messagebox.showinfo("Saved", f"Image saved to {fp}")

    # ===================================================================
    # AUDIO MANIFOLD — Multimodal Network Visualizer
    # ===================================================================
    def _build_manifold_view(self, parent):
        """Build the full audio manifold visualizer (ported from v1.2 prototype)."""
        # Check deps
        if not _SKLEARN_OK:
            self._manifold_show_missing(parent, "scikit-learn (pip install scikit-learn)")
            return

        parent.columnconfigure(1, weight=3)
        parent.columnconfigure(0, weight=0)
        parent.columnconfigure(2, weight=1)
        parent.rowconfigure(0, weight=1)

        # State
        self._mf_models = {}
        self._mf_current = None
        self._mf_anim_running = False
        self._mf_anim_speed = 1.0
        self._mf_current_time = 0
        self._mf_saved_baseline = ""
        self._mf_params = {
            'audio_hop_length': 512, 'audio_n_mfcc': 13,
            'audio_onset_threshold': 0.5,
            'image_n_segments': 100, 'image_compactness': 10,
            'edge_temporal_window': 10, 'edge_similarity_thresh': 0.8,
            'manifold_method': 'tsne', 'manifold_perplexity': 30,
        }

        # --- Left panel: model tree + buttons ---
        left = ttk.Frame(parent, width=240)
        left.grid(row=0, column=0, sticky=tk.NSEW, padx=(5, 0), pady=5)
        left.grid_propagate(False)

        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self._mf_tree = ttk.Treeview(tree_frame, columns=('type', 'info'), selectmode='browse')
        self._mf_tree.heading('#0', text='Models')
        self._mf_tree.column('#0', width=120)
        self._mf_tree.heading('type', text='Type')
        self._mf_tree.column('type', width=50)
        self._mf_tree.heading('info', text='Status')
        self._mf_tree.column('info', width=60)
        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._mf_tree.yview)
        self._mf_tree.configure(yscrollcommand=vsb.set)
        self._mf_tree.grid(row=0, column=0, sticky=tk.NSEW)
        vsb.grid(row=0, column=1, sticky=tk.NS)
        self._mf_tree.bind('<<TreeviewSelect>>', self._mf_on_tree_select)

        btn_f = ttk.Frame(left)
        btn_f.pack(fill=tk.X, padx=2, pady=5)
        ttk.Button(btn_f, text="Load Audio", command=self._mf_load_audio).pack(side=tk.LEFT, padx=1)
        ttk.Button(btn_f, text="Load Image", command=self._mf_load_image).pack(side=tk.LEFT, padx=1)
        ttk.Button(btn_f, text="Process", command=self._mf_process).pack(side=tk.LEFT, padx=1)
        ttk.Button(btn_f, text="Delete", command=self._mf_delete).pack(side=tk.LEFT, padx=1)

        # --- Centre: 3D canvas ---
        centre = ttk.Frame(parent)
        centre.grid(row=0, column=1, sticky=tk.NSEW, padx=5, pady=5)
        centre.rowconfigure(0, weight=1)
        centre.columnconfigure(0, weight=1)

        self._mf_fig = Figure(figsize=(7, 7), dpi=100, facecolor='#0d1117')
        self._mf_ax = self._mf_fig.add_subplot(111, projection='3d', facecolor='#0d1117')
        self._mf_canvas = FigureCanvasTkAgg(self._mf_fig, master=centre)
        self._mf_canvas.get_tk_widget().grid(row=0, column=0, sticky=tk.NSEW)
        self._mf_canvas.mpl_connect('pick_event', self._mf_on_pick)

        # Status bar
        self._mf_status = ttk.Label(parent, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self._mf_status.grid(row=1, column=0, columnspan=3, sticky=tk.EW, padx=5, pady=(0, 2))

        # --- Right: control notebook ---
        right = ttk.Frame(parent)
        right.grid(row=0, column=2, sticky=tk.NSEW, padx=(0, 5), pady=5)
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        rnb = ttk.Notebook(right)
        rnb.grid(row=0, column=0, sticky=tk.NSEW)

        # Timeline tab
        tl_frame = ttk.Frame(rnb)
        rnb.add(tl_frame, text="Timeline")
        self._mf_build_timeline(tl_frame)

        # Parameters tab
        pm_frame = ttk.Frame(rnb)
        rnb.add(pm_frame, text="Parameters")
        self._mf_build_params(pm_frame)

        # Edit tab
        ed_frame = ttk.Frame(rnb)
        rnb.add(ed_frame, text="Edit")
        self._mf_edit_text = tk.Text(ed_frame, wrap=tk.WORD, font=('Courier', 10))
        self._mf_edit_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self._mf_edit_text.insert(tk.END, "# Model notes\n")

        # Diffs tab
        df_frame = ttk.Frame(rnb)
        rnb.add(df_frame, text="Diffs")
        df_tb = ttk.Frame(df_frame)
        df_tb.pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(df_tb, text="Compute Diff", command=self._mf_compute_diff).pack(side=tk.LEFT)
        ttk.Button(df_tb, text="Set Baseline", command=self._mf_set_baseline).pack(side=tk.LEFT, padx=5)
        self._mf_diff_text = tk.Text(df_frame, wrap=tk.NONE, font=('Courier', 10), state=tk.DISABLED)
        self._mf_diff_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _manifold_show_missing(self, parent, pkg):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        ttk.Label(parent, text=f"Missing: {pkg}", font=("Arial", 14)).grid(
            row=0, column=0, padx=20, pady=40)

    # --- Timeline controls ---
    def _mf_build_timeline(self, parent):
        btn_f = ttk.Frame(parent)
        btn_f.pack(fill=tk.X, padx=5, pady=5)
        self._mf_play_btn = ttk.Button(btn_f, text="Play", command=self._mf_toggle_anim)
        self._mf_play_btn.pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_f, text="Stop", command=self._mf_stop_anim).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_f, text="Reset", command=self._mf_reset_timeline).pack(side=tk.LEFT, padx=2)

        ttk.Label(btn_f, text="Speed:").pack(side=tk.LEFT, padx=(10, 2))
        self._mf_speed_var = tk.DoubleVar(value=1.0)
        ttk.Spinbox(btn_f, from_=0.1, to=10.0, increment=0.1,
                     textvariable=self._mf_speed_var, width=5).pack(side=tk.LEFT)

        sl_f = ttk.Frame(parent)
        sl_f.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(sl_f, text="Time:").pack(side=tk.LEFT)
        self._mf_time_slider = ttk.Scale(sl_f, from_=0, to=100, orient=tk.HORIZONTAL,
                                           command=self._mf_slider_changed)
        self._mf_time_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self._mf_time_label = ttk.Label(sl_f, text="0/0")
        self._mf_time_label.pack(side=tk.LEFT)

        # Edge controls
        ef = ttk.LabelFrame(parent, text="Edge Display")
        ef.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(ef, text="Temporal window:").grid(row=0, column=0, sticky=tk.W)
        self._mf_temp_win = tk.IntVar(value=self._mf_params['edge_temporal_window'])
        ttk.Spinbox(ef, from_=1, to=100, textvariable=self._mf_temp_win,
                     width=5, command=self._mf_recompute_edges).grid(row=0, column=1)
        ttk.Label(ef, text="Similarity thresh:").grid(row=1, column=0, sticky=tk.W)
        self._mf_sim_thresh = tk.DoubleVar(value=self._mf_params['edge_similarity_thresh'])
        ttk.Scale(ef, from_=0.0, to=1.0, variable=self._mf_sim_thresh,
                   orient=tk.HORIZONTAL,
                   command=lambda v: self._mf_recompute_edges()).grid(row=1, column=1, sticky=tk.EW)
        ef.columnconfigure(1, weight=1)

        self._mf_show_temp = tk.BooleanVar(value=True)
        self._mf_show_sim = tk.BooleanVar(value=True)
        ttk.Checkbutton(ef, text="Temporal", variable=self._mf_show_temp,
                         command=self._mf_update_plot).grid(row=2, column=0)
        ttk.Checkbutton(ef, text="Similarity", variable=self._mf_show_sim,
                         command=self._mf_update_plot).grid(row=2, column=1)

    # --- Parameter controls ---
    def _mf_build_params(self, parent):
        canvas = tk.Canvas(parent, borderwidth=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        scrollable = ttk.Frame(canvas)
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        row = 0
        ttk.Label(scrollable, text="Audio", font=('TkDefaultFont', 10, 'bold')).grid(
            row=row, column=0, columnspan=2, pady=5); row += 1
        ttk.Label(scrollable, text="Hop length:").grid(row=row, column=0, sticky=tk.W)
        self._mf_hop = tk.IntVar(value=self._mf_params['audio_hop_length'])
        ttk.Entry(scrollable, textvariable=self._mf_hop, width=10).grid(row=row, column=1); row += 1
        ttk.Label(scrollable, text="N MFCC:").grid(row=row, column=0, sticky=tk.W)
        self._mf_nmfcc = tk.IntVar(value=self._mf_params['audio_n_mfcc'])
        ttk.Entry(scrollable, textvariable=self._mf_nmfcc, width=10).grid(row=row, column=1); row += 1
        ttk.Label(scrollable, text="Onset threshold:").grid(row=row, column=0, sticky=tk.W)
        self._mf_onset = tk.DoubleVar(value=self._mf_params['audio_onset_threshold'])
        ttk.Scale(scrollable, from_=0.0, to=1.0, variable=self._mf_onset,
                   orient=tk.HORIZONTAL).grid(row=row, column=1, sticky=tk.EW); row += 1

        ttk.Label(scrollable, text="Image", font=('TkDefaultFont', 10, 'bold')).grid(
            row=row, column=0, columnspan=2, pady=5); row += 1
        ttk.Label(scrollable, text="N segments:").grid(row=row, column=0, sticky=tk.W)
        self._mf_nseg = tk.IntVar(value=self._mf_params['image_n_segments'])
        ttk.Entry(scrollable, textvariable=self._mf_nseg, width=10).grid(row=row, column=1); row += 1
        ttk.Label(scrollable, text="Compactness:").grid(row=row, column=0, sticky=tk.W)
        self._mf_compact = tk.IntVar(value=self._mf_params['image_compactness'])
        ttk.Scale(scrollable, from_=1, to=100, variable=self._mf_compact,
                   orient=tk.HORIZONTAL).grid(row=row, column=1, sticky=tk.EW); row += 1

        ttk.Label(scrollable, text="Manifold", font=('TkDefaultFont', 10, 'bold')).grid(
            row=row, column=0, columnspan=2, pady=5); row += 1
        ttk.Label(scrollable, text="Method:").grid(row=row, column=0, sticky=tk.W)
        self._mf_method = tk.StringVar(value='tsne')
        ttk.Combobox(scrollable, textvariable=self._mf_method,
                      values=['tsne', 'pca'], width=8).grid(row=row, column=1); row += 1
        ttk.Label(scrollable, text="Perplexity:").grid(row=row, column=0, sticky=tk.W)
        self._mf_perp = tk.IntVar(value=30)
        ttk.Entry(scrollable, textvariable=self._mf_perp, width=10).grid(row=row, column=1); row += 1

        ttk.Button(scrollable, text="Apply Parameters", command=self._mf_apply_params).grid(
            row=row, column=0, columnspan=2, pady=10)

    # --- Tree / File loading ---
    def _mf_on_tree_select(self, event):
        sel = self._mf_tree.selection()
        if not sel:
            return
        name = self._mf_tree.item(sel[0], 'text')
        if name in self._mf_models:
            self._mf_current = self._mf_models[name]
            self._mf_update_timeline_range()
            self._mf_update_plot()
            self._mf_status.config(text=f"Selected: {name}")

    def _mf_load_audio(self):
        if not _LIBROSA_OK:
            messagebox.showinfo("Missing", "librosa not installed.\npip install librosa")
            return
        path = filedialog.askopenfilename(filetypes=[("Audio", "*.wav *.mp3 *.flac *.m4a")])
        if not path:
            return
        name = os.path.basename(path)
        m = _ManifoldModel(name, 'audio')
        m.params['path'] = path
        m.params['status'] = 'loaded'
        self._mf_models[name] = m
        self._mf_refresh_tree()
        self._mf_status.config(text=f"Loaded: {name}")

    def _mf_load_image(self):
        if not _SKIMAGE_OK:
            messagebox.showinfo("Missing", "scikit-image not installed.\npip install scikit-image")
            return
        path = filedialog.askopenfilename(filetypes=[("Image", "*.png *.jpg *.jpeg *.bmp")])
        if not path:
            return
        name = os.path.basename(path)
        m = _ManifoldModel(name, 'image')
        m.params['path'] = path
        m.params['status'] = 'loaded'
        self._mf_models[name] = m
        self._mf_refresh_tree()
        self._mf_status.config(text=f"Loaded: {name}")

    def _mf_delete(self):
        sel = self._mf_tree.selection()
        if not sel:
            return
        name = self._mf_tree.item(sel[0], 'text')
        if name in self._mf_models:
            del self._mf_models[name]
            if self._mf_current and self._mf_current.name == name:
                self._mf_current = None
                self._mf_ax.clear()
                self._mf_canvas.draw()
            self._mf_refresh_tree()

    def _mf_refresh_tree(self):
        for item in self._mf_tree.get_children():
            self._mf_tree.delete(item)
        for name, m in self._mf_models.items():
            self._mf_tree.insert('', tk.END, text=name,
                                  values=(m.modality, m.params.get('status', '?')))

    # --- Processing ---
    def _mf_process(self):
        if not self._mf_current:
            messagebox.showwarning("No model", "Select a model first.")
            return
        self._mf_status.config(text="Processing...")
        threading.Thread(target=self._mf_do_process, args=(self._mf_current,), daemon=True).start()

    def _mf_do_process(self, model):
        try:
            if model.modality == 'audio':
                self._mf_process_audio(model)
            elif model.modality == 'image':
                self._mf_process_image(model)
            self.root.after(0, self._mf_processing_done, model)
        except Exception as e:
            log_message(f"MANIFOLD: Processing failed: {e}")
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            self.root.after(0, lambda: self._mf_status.config(text="Processing failed"))

    def _mf_process_audio(self, model):
        if not _LIBROSA_OK:
            raise ImportError("librosa not installed")
        path = model.params['path']
        y, sr = librosa.load(path, sr=None, mono=True)

        hop = self._mf_hop.get()
        n_mfcc = self._mf_nmfcc.get()
        onset_thresh = self._mf_onset.get()

        onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
        onset_frames = librosa.onset.onset_detect(
            onset_envelope=onset_env, sr=sr, hop_length=hop, threshold=onset_thresh)

        if len(onset_frames) == 0:
            n_frames = (len(y) // hop) + 1
            frames = np.arange(0, n_frames * hop, hop)
        else:
            frames = onset_frames * hop

        features, times = [], []
        for i, start in enumerate(frames):
            end = min(start + hop * 4, len(y))
            seg = y[start:end]
            if len(seg) < hop:
                continue
            mfcc = librosa.feature.mfcc(y=seg, sr=sr, n_mfcc=n_mfcc, hop_length=hop)
            features.append(np.mean(mfcc, axis=1))
            times.append(i)

        features = np.array(features)
        if features.shape[0] < 2:
            raise ValueError("Not enough frames extracted")

        scaler = StandardScaler()
        scaled = scaler.fit_transform(features)

        method = self._mf_method.get()
        if method == 'tsne':
            perp = min(self._mf_perp.get(), scaled.shape[0] - 1)
            pos_3d = TSNE(n_components=3, perplexity=max(perp, 2), random_state=42).fit_transform(scaled)
        else:
            pos_3d = PCA(n_components=min(3, scaled.shape[1])).fit_transform(scaled)

        model.nodes = []
        for i, (pos, t) in enumerate(zip(pos_3d, times)):
            model.add_node(_Node(i, pos, t, features=features[i]))

        self._mf_compute_edges(model)
        model.params['status'] = 'processed'
        log_message(f"MANIFOLD: Audio processed — {len(model.nodes)} nodes")

    def _mf_process_image(self, model):
        if not _SKIMAGE_OK:
            raise ImportError("scikit-image not installed")
        path = model.params['path']
        img = skimage_io.imread(path)
        if img.ndim == 2:
            img = np.stack([img] * 3, axis=-1)
        elif img.shape[2] == 4:
            img = img[:, :, :3]

        segments = slic(img, n_segments=self._mf_nseg.get(),
                         compactness=self._mf_compact.get(), start_label=0)
        h, w, _ = img.shape
        lab = rgb2lab(img)

        features = []
        for seg_id in np.unique(segments):
            mask = segments == seg_id
            mean_color = np.mean(lab[mask], axis=0)
            ys, xs = np.where(mask)
            nx, ny = np.mean(xs) / w, np.mean(ys) / h
            features.append(np.concatenate([mean_color, [nx, ny]]))

        features = np.array(features)
        if features.shape[0] < 2:
            raise ValueError("Not enough segments")

        scaler = StandardScaler()
        scaled = scaler.fit_transform(features)

        method = self._mf_method.get()
        if method == 'tsne':
            perp = min(self._mf_perp.get(), scaled.shape[0] - 1)
            pos_3d = TSNE(n_components=3, perplexity=max(perp, 2), random_state=42).fit_transform(scaled)
        else:
            pos_3d = PCA(n_components=min(3, scaled.shape[1])).fit_transform(scaled)

        model.nodes = []
        for i, (pos, feat) in enumerate(zip(pos_3d, features)):
            model.add_node(_Node(i, pos, i, features=feat, label=f"seg{i}"))

        self._mf_compute_edges(model)
        model.params['status'] = 'processed'
        log_message(f"MANIFOLD: Image processed — {len(model.nodes)} nodes")

    def _mf_compute_edges(self, model):
        model.edges = []
        n = len(model.nodes)
        if n == 0:
            return
        temp_win = self._mf_temp_win.get()
        sim_thresh = self._mf_sim_thresh.get()
        feat_mat = np.array([nd.features for nd in model.nodes])
        sim_mat = cosine_similarity(feat_mat) if feat_mat.shape[0] > 1 else None

        for i in range(n):
            for j in range(i + 1, n):
                if abs(model.nodes[i].time - model.nodes[j].time) <= temp_win:
                    model.edges.append(_Edge(i, j, 1.0, 'temporal'))
                if sim_mat is not None and sim_mat[i, j] > sim_thresh:
                    model.edges.append(_Edge(i, j, sim_mat[i, j], 'similarity'))

    def _mf_processing_done(self, model):
        self._mf_refresh_tree()
        self._mf_current = model
        self._mf_update_timeline_range()
        self._mf_update_plot()
        self._mf_status.config(text=f"Done: {model.name} ({len(model.nodes)} nodes)")

    # --- Plot ---
    def _mf_update_timeline_range(self):
        if self._mf_current:
            mx = self._mf_current.timeline_max
            self._mf_time_slider.config(to=max(mx, 1))
            self._mf_time_label.config(text=f"0/{mx}")
            self._mf_current_time = 0
            self._mf_time_slider.set(0)

    def _mf_update_plot(self):
        if not self._mf_current:
            return
        model = self._mf_current
        ax = self._mf_ax
        ax.clear()
        ax.set_facecolor('#0d1117')

        visible = model.filter_by_time(int(self._mf_current_time))
        if not visible:
            self._mf_canvas.draw()
            return

        positions = np.array([model.nodes[i].pos for i in visible])
        times = np.array([model.nodes[i].time for i in visible])
        visible_set = set(visible)

        ax.scatter(positions[:, 0], positions[:, 1], positions[:, 2],
                    c=times, cmap='plasma', s=20, picker=True)

        show_t = self._mf_show_temp.get()
        show_s = self._mf_show_sim.get()
        for edge in model.edges:
            if edge.source in visible_set and edge.target in visible_set:
                if (edge.type == 'temporal' and show_t) or (edge.type == 'similarity' and show_s):
                    p1, p2 = model.nodes[edge.source].pos, model.nodes[edge.target].pos
                    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], [p1[2], p2[2]],
                             color='gray', alpha=0.3, linewidth=0.5)

        ax.set_title(f"{model.name} (t={int(self._mf_current_time)}/{model.timeline_max})",
                      color='white', fontsize=10)
        ax.set_xlabel('X', color='#888')
        ax.set_ylabel('Y', color='#888')
        ax.set_zlabel('Z', color='#888')
        self._mf_canvas.draw()

    def _mf_slider_changed(self, val):
        self._mf_current_time = int(float(val))
        mx = self._mf_current.timeline_max if self._mf_current else 0
        self._mf_time_label.config(text=f"{int(self._mf_current_time)}/{mx}")
        self._mf_update_plot()

    def _mf_on_pick(self, event):
        if not self._mf_current:
            return
        try:
            idx = event.ind[0]
            n = self._mf_current.nodes[idx]
            self._mf_status.config(text=f"Node {n.id} t={n.time} label={n.label}")
        except Exception:
            pass

    # --- Animation ---
    def _mf_toggle_anim(self):
        if self._mf_anim_running:
            self._mf_stop_anim()
        else:
            self._mf_start_anim()

    def _mf_start_anim(self):
        if not self._mf_current:
            return
        self._mf_anim_running = True
        self._mf_play_btn.config(text="Pause")
        threading.Thread(target=self._mf_anim_loop, daemon=True).start()

    def _mf_stop_anim(self):
        self._mf_anim_running = False
        if hasattr(self, '_mf_play_btn'):
            self._mf_play_btn.config(text="Play")

    def _mf_reset_timeline(self):
        self._mf_current_time = 0
        self._mf_time_slider.set(0)
        self._mf_update_plot()

    def _mf_anim_loop(self):
        last = _time.time()
        while self._mf_anim_running and self._mf_current:
            now = _time.time()
            dt = now - last
            last = now
            self._mf_current_time += dt * self._mf_speed_var.get()
            if self._mf_current_time >= self._mf_current.timeline_max:
                self._mf_current_time = self._mf_current.timeline_max
                self.root.after(0, self._mf_stop_anim)
                break
            self.root.after(0, self._mf_anim_ui_tick)
            _time.sleep(0.05)

    def _mf_anim_ui_tick(self):
        if self._mf_current:
            self._mf_time_slider.set(self._mf_current_time)
            mx = self._mf_current.timeline_max
            self._mf_time_label.config(text=f"{int(self._mf_current_time)}/{mx}")
            self._mf_update_plot()

    def _mf_recompute_edges(self):
        if self._mf_current:
            threading.Thread(target=self._mf_do_recompute, daemon=True).start()

    def _mf_do_recompute(self):
        self._mf_compute_edges(self._mf_current)
        self.root.after(0, self._mf_update_plot)

    def _mf_apply_params(self):
        log_message("MANIFOLD: Parameters applied")

    # --- Diff ---
    def _mf_compute_diff(self):
        current = self._mf_edit_text.get("1.0", tk.END).splitlines()
        baseline = self._mf_saved_baseline.splitlines()
        diff = list(difflib.unified_diff(baseline, current, fromfile='Baseline',
                                          tofile='Current', lineterm=''))
        self._mf_diff_text.config(state=tk.NORMAL)
        self._mf_diff_text.delete("1.0", tk.END)
        if diff:
            for line in diff:
                tag = 'add' if line.startswith('+') else ('remove' if line.startswith('-') else None)
                self._mf_diff_text.insert(tk.END, line + '\n', tag)
            self._mf_diff_text.tag_config('add', foreground='green')
            self._mf_diff_text.tag_config('remove', foreground='red')
        else:
            self._mf_diff_text.insert(tk.END, "No differences.")
        self._mf_diff_text.config(state=tk.DISABLED)

    def _mf_set_baseline(self):
        self._mf_saved_baseline = self._mf_edit_text.get("1.0", tk.END)

    # ===================================================================
    # WORKSHOP — 3D Shape Creation + Slicer Export
    # ===================================================================
    def _build_workshop_view(self, parent):
        parent.columnconfigure(1, weight=3)
        parent.columnconfigure(0, weight=0)
        parent.columnconfigure(2, weight=1)
        parent.rowconfigure(0, weight=1)

        # --- Left: shape list ---
        list_frame = ttk.LabelFrame(parent, text="Shapes", padding=5, width=180)
        list_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=(5, 0), pady=5)
        list_frame.grid_propagate(False)

        self._ws_listbox = tk.Listbox(list_frame, bg='#2b2b2b', fg='white',
                                       selectbackground='#555', width=20)
        self._ws_listbox.pack(fill=tk.BOTH, expand=True)
        self._ws_listbox.bind('<<ListboxSelect>>', self._ws_on_select)

        add_frame = ttk.Frame(list_frame)
        add_frame.pack(fill=tk.X, pady=(5, 0))
        self._ws_type_var = tk.StringVar(value="Cube")
        ttk.Combobox(add_frame, textvariable=self._ws_type_var,
                      values=list(SHAPE_GENERATORS.keys()),
                      state='readonly', width=10).pack(side=tk.LEFT)
        ttk.Button(add_frame, text="Add", command=self._ws_add_shape, width=5).pack(side=tk.LEFT, padx=2)

        ttk.Button(list_frame, text="Delete Selected", command=self._ws_delete_shape).pack(
            fill=tk.X, pady=(5, 0))
        ttk.Button(list_frame, text="Import STL…", command=self._ws_import_stl).pack(
            fill=tk.X, pady=(3, 0))

        # --- Centre: 3D viewport ---
        plot_frame = ttk.Frame(parent)
        plot_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=5, pady=5)
        plot_frame.rowconfigure(0, weight=1)
        plot_frame.columnconfigure(0, weight=1)

        self._ws_fig = Figure(figsize=(8, 8), facecolor='#1a1a2e')
        self._ws_ax = self._ws_fig.add_subplot(111, projection='3d', facecolor='#1a1a2e')
        self._ws_canvas = FigureCanvasTkAgg(self._ws_fig, master=plot_frame)
        self._ws_canvas.get_tk_widget().grid(row=0, column=0, sticky=tk.NSEW)

        ws_tb_frame = ttk.Frame(plot_frame)
        ws_tb_frame.grid(row=1, column=0, sticky=tk.EW)
        ws_tb = NavigationToolbar2Tk(self._ws_canvas, ws_tb_frame)
        ws_tb.update()

        # --- Right: controls ---
        ctrl = ttk.Frame(parent, padding=10)
        ctrl.grid(row=0, column=2, sticky=tk.NSEW, padx=(0, 5), pady=5)

        ttk.Label(ctrl, text="Transform", font=("Arial", 11, "bold")).pack(pady=(0, 5))

        # Translate
        ttk.Label(ctrl, text="Translate", font=("Arial", 9, "underline")).pack(anchor=tk.W, pady=(5, 2))
        self._ws_tx = tk.DoubleVar(value=0)
        self._ws_ty = tk.DoubleVar(value=0)
        self._ws_tz = tk.DoubleVar(value=0)
        for label, var in [("X:", self._ws_tx), ("Y:", self._ws_ty), ("Z:", self._ws_tz)]:
            f = ttk.Frame(ctrl)
            f.pack(fill=tk.X, pady=1)
            ttk.Label(f, text=label, width=3).pack(side=tk.LEFT)
            ttk.Scale(f, from_=-3, to=3, variable=var, orient=tk.HORIZONTAL).pack(
                side=tk.RIGHT, fill=tk.X, expand=True)

        # Rotate
        ttk.Label(ctrl, text="Rotate (deg)", font=("Arial", 9, "underline")).pack(anchor=tk.W, pady=(8, 2))
        self._ws_rx = tk.DoubleVar(value=0)
        self._ws_ry = tk.DoubleVar(value=0)
        self._ws_rz = tk.DoubleVar(value=0)
        for label, var in [("X:", self._ws_rx), ("Y:", self._ws_ry), ("Z:", self._ws_rz)]:
            f = ttk.Frame(ctrl)
            f.pack(fill=tk.X, pady=1)
            ttk.Label(f, text=label, width=3).pack(side=tk.LEFT)
            ttk.Scale(f, from_=0, to=360, variable=var, orient=tk.HORIZONTAL).pack(
                side=tk.RIGHT, fill=tk.X, expand=True)

        # Scale
        ttk.Label(ctrl, text="Scale", font=("Arial", 9, "underline")).pack(anchor=tk.W, pady=(8, 2))
        self._ws_scale = tk.DoubleVar(value=1.0)
        sf = ttk.Frame(ctrl)
        sf.pack(fill=tk.X, pady=1)
        ttk.Label(sf, text="S:", width=3).pack(side=tk.LEFT)
        ttk.Scale(sf, from_=0.1, to=5.0, variable=self._ws_scale, orient=tk.HORIZONTAL).pack(
            side=tk.RIGHT, fill=tk.X, expand=True)

        ttk.Button(ctrl, text="Apply Transform", command=self._ws_apply_transform).pack(pady=8)
        ttk.Button(ctrl, text="Refresh View", command=self._ws_redraw).pack(pady=2)

        # Color
        ttk.Label(ctrl, text="Color", font=("Arial", 9, "underline")).pack(anchor=tk.W, pady=(8, 2))
        self._ws_color = tk.StringVar(value="#4488ff")
        col_f = ttk.Frame(ctrl)
        col_f.pack(fill=tk.X, pady=2)
        self._ws_color_lbl = ttk.Label(col_f, text="#4488ff", width=10)
        self._ws_color_lbl.pack(side=tk.RIGHT, padx=5)
        ttk.Button(col_f, text="Pick", command=self._ws_pick_color).pack(side=tk.RIGHT)

        # Export
        ttk.Label(ctrl, text="Export", font=("Arial", 11, "bold")).pack(pady=(15, 5))
        ttk.Button(ctrl, text="Export STL", command=self._ws_export_stl).pack(fill=tk.X, pady=2)
        ttk.Button(ctrl, text="Export 3MF", command=self._ws_export_3mf).pack(fill=tk.X, pady=2)

        # Scene save/load
        ttk.Label(ctrl, text="Scene", font=("Arial", 9, "underline")).pack(anchor=tk.W, pady=(10, 2))
        ttk.Button(ctrl, text="Save Scene", command=self._ws_save_scene).pack(fill=tk.X, pady=2)
        ttk.Button(ctrl, text="Load Scene", command=self._ws_load_scene).pack(fill=tk.X, pady=2)

        # State
        self._ws_shapes = {}  # {id: {type, verts, faces, translate, rotate, scale, color}}
        self._ws_seq = 0
        self._ws_selected = None

        self._ws_redraw()

    def _ws_add_shape(self):
        stype = self._ws_type_var.get()
        gen = SHAPE_GENERATORS.get(stype)
        if not gen:
            return
        verts, faces = gen()
        self._ws_seq += 1
        sid = f"{stype}_{self._ws_seq}"
        self._ws_shapes[sid] = {
            "type": stype,
            "verts_base": verts.copy(),
            "faces": faces,
            "translate": [0.0, 0.0, 0.0],
            "rotate": [0.0, 0.0, 0.0],
            "scale": 1.0,
            "color": self._ws_color.get(),
        }
        self._ws_listbox.insert(tk.END, sid)
        self._ws_redraw()
        log_message(f"WORKSHOP: Added {sid}")

    def _ws_delete_shape(self):
        sel = self._ws_listbox.curselection()
        if not sel:
            return
        sid = self._ws_listbox.get(sel[0])
        self._ws_shapes.pop(sid, None)
        self._ws_listbox.delete(sel[0])
        self._ws_selected = None
        self._ws_redraw()

    def _ws_on_select(self, event):
        sel = self._ws_listbox.curselection()
        if not sel:
            return
        sid = self._ws_listbox.get(sel[0])
        self._ws_selected = sid
        s = self._ws_shapes.get(sid)
        if s:
            self._ws_tx.set(s["translate"][0])
            self._ws_ty.set(s["translate"][1])
            self._ws_tz.set(s["translate"][2])
            self._ws_rx.set(s["rotate"][0])
            self._ws_ry.set(s["rotate"][1])
            self._ws_rz.set(s["rotate"][2])
            self._ws_scale.set(s["scale"])
            self._ws_color.set(s["color"])
            self._ws_color_lbl.config(text=s["color"])

    def _ws_apply_transform(self):
        if not self._ws_selected or self._ws_selected not in self._ws_shapes:
            return
        s = self._ws_shapes[self._ws_selected]
        s["translate"] = [self._ws_tx.get(), self._ws_ty.get(), self._ws_tz.get()]
        s["rotate"] = [self._ws_rx.get(), self._ws_ry.get(), self._ws_rz.get()]
        s["scale"] = self._ws_scale.get()
        s["color"] = self._ws_color.get()
        self._ws_redraw()

    def _ws_pick_color(self):
        result = colorchooser.askcolor(initialcolor=self._ws_color.get())
        if result[1]:
            self._ws_color.set(result[1])
            self._ws_color_lbl.config(text=result[1])

    def _ws_transform_verts(self, shape):
        """Apply translate/rotate/scale to base vertices, return transformed."""
        verts = shape["verts_base"].copy() * shape["scale"]
        # Rotation (Euler XYZ in degrees)
        rx, ry, rz = [math.radians(a) for a in shape["rotate"]]
        # Rx
        if rx:
            c, s = math.cos(rx), math.sin(rx)
            R = np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
            verts = verts @ R.T
        if ry:
            c, s = math.cos(ry), math.sin(ry)
            R = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
            verts = verts @ R.T
        if rz:
            c, s = math.cos(rz), math.sin(rz)
            R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
            verts = verts @ R.T
        # Translate
        verts += np.array(shape["translate"])
        return verts

    def _ws_redraw(self):
        ax = self._ws_ax
        ax.clear()
        ax.set_facecolor('#1a1a2e')
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')

        if not self._ws_shapes:
            ax.set_xlim(-2, 2)
            ax.set_ylim(-2, 2)
            ax.set_zlim(-2, 2)
            ax.text(0, 0, 0, "Add a shape\nto begin", ha='center', va='center',
                    color='#666', fontsize=14)
            self._ws_canvas.draw_idle()
            return

        for sid, shape in self._ws_shapes.items():
            verts = self._ws_transform_verts(shape)
            faces = shape["faces"]
            color = shape["color"]
            alpha = 0.9 if sid == self._ws_selected else 0.6

            from mpl_toolkits.mplot3d.art3d import Poly3DCollection
            tri_verts = verts[faces]
            poly = Poly3DCollection(tri_verts, alpha=alpha, facecolor=color,
                                     edgecolor='#ffffff30', linewidth=0.3)
            ax.add_collection3d(poly)

        # Auto-fit
        all_v = np.concatenate([self._ws_transform_verts(s) for s in self._ws_shapes.values()])
        margin = 0.5
        for setter, idx in [(ax.set_xlim, 0), (ax.set_ylim, 1), (ax.set_zlim, 2)]:
            lo, hi = all_v[:, idx].min() - margin, all_v[:, idx].max() + margin
            setter([lo, hi])

        self._ws_canvas.draw_idle()

    # --- Export ---
    def _ws_export_stl(self):
        if not self._ws_shapes:
            messagebox.showinfo("Empty", "No shapes to export.")
            return
        if not _STL_OK:
            messagebox.showinfo("Missing Package",
                                "numpy-stl not installed.\npip install numpy-stl")
            return
        fp = filedialog.asksaveasfilename(defaultextension=".stl",
                                           filetypes=[("STL", "*.stl")])
        if not fp:
            return
        all_faces = []
        for shape in self._ws_shapes.values():
            verts = self._ws_transform_verts(shape)
            for f in shape["faces"]:
                all_faces.append(verts[f])
        all_faces = np.array(all_faces)
        m = stl_mesh.Mesh(np.zeros(len(all_faces), dtype=stl_mesh.Mesh.dtype))
        for i, tri in enumerate(all_faces):
            m.vectors[i] = tri
        m.save(fp)
        messagebox.showinfo("Exported", f"STL saved to {fp}")
        log_message(f"WORKSHOP: Exported STL → {fp}")

    def _ws_export_3mf(self):
        if not self._ws_shapes:
            messagebox.showinfo("Empty", "No shapes to export.")
            return
        if not _TRIMESH_OK:
            messagebox.showinfo("Missing Package",
                                "trimesh not installed.\npip install trimesh")
            return
        fp = filedialog.asksaveasfilename(defaultextension=".3mf",
                                           filetypes=[("3MF", "*.3mf")])
        if not fp:
            return
        meshes = []
        for shape in self._ws_shapes.values():
            verts = self._ws_transform_verts(shape)
            m = trimesh.Trimesh(vertices=verts, faces=shape["faces"])
            meshes.append(m)
        combined = trimesh.util.concatenate(meshes)
        combined.export(fp, file_type='3mf')
        messagebox.showinfo("Exported", f"3MF saved to {fp}")
        log_message(f"WORKSHOP: Exported 3MF → {fp}")

    # --- Scene persistence ---
    def _ws_save_scene(self):
        fp = filedialog.asksaveasfilename(defaultextension=".json",
                                           filetypes=[("JSON", "*.json")])
        if not fp:
            return
        scene = {}
        for sid, s in self._ws_shapes.items():
            scene[sid] = {
                "type": s["type"],
                "translate": s["translate"],
                "rotate": s["rotate"],
                "scale": s["scale"],
                "color": s["color"],
            }
        Path(fp).write_text(json.dumps(scene, indent=2), encoding='utf-8')
        messagebox.showinfo("Saved", f"Scene saved to {fp}")

    def _ws_load_scene(self):
        fp = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not fp:
            return
        try:
            scene = json.loads(Path(fp).read_text(encoding='utf-8'))
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        self._ws_shapes.clear()
        self._ws_listbox.delete(0, tk.END)
        self._ws_seq = 0
        for sid, s in scene.items():
            gen = SHAPE_GENERATORS.get(s["type"])
            if not gen:
                continue
            verts, faces = gen()
            self._ws_shapes[sid] = {
                "type": s["type"],
                "verts_base": verts,
                "faces": faces,
                "translate": s.get("translate", [0, 0, 0]),
                "rotate": s.get("rotate", [0, 0, 0]),
                "scale": s.get("scale", 1.0),
                "color": s.get("color", "#4488ff"),
            }
            self._ws_listbox.insert(tk.END, sid)
            self._ws_seq += 1
        self._ws_redraw()
        messagebox.showinfo("Loaded", f"Scene loaded from {fp}")

    # -----------------------------------------------------------------------
    # Workshop — STL import (pure Python/numpy, no external deps)
    # -----------------------------------------------------------------------
    def _ws_import_stl(self, filepath=None):
        """Load a binary or ASCII STL file into the Workshop shape list."""
        if filepath is None:
            filepath = filedialog.askopenfilename(
                title="Import STL",
                filetypes=[("STL files", "*.stl"), ("All files", "*.*")])
        if not filepath:
            return
        try:
            verts, faces = _parse_stl(filepath)
        except Exception as e:
            messagebox.showerror("STL Load Error", str(e))
            log_message(f"WORKSHOP: STL load failed: {e}")
            return

        name = Path(filepath).stem
        self._ws_seq += 1
        sid = f"STL:{name}_{self._ws_seq}"

        # Centre at origin and normalise to 2-unit bounding box
        centroid = verts.mean(axis=0)
        verts = verts - centroid
        extent = (verts.max(axis=0) - verts.min(axis=0)).max()
        if extent > 0:
            verts = verts / extent * 2.0

        # Subsample very large meshes for responsive preview (keep ≤ 20k tris)
        MAX_TRIS = 20_000
        if len(faces) > MAX_TRIS:
            step = max(1, len(faces) // MAX_TRIS)
            faces = faces[::step]
            # Remap face indices to contiguous vertex subset
            used = np.unique(faces)
            remap = np.zeros(len(verts), dtype=np.int32)
            remap[used] = np.arange(len(used), dtype=np.int32)
            verts = verts[used]
            faces = remap[faces]
            log_message(f"WORKSHOP: Subsampled to {len(faces)} tris for preview")

        self._ws_shapes[sid] = {
            "type": "STL",
            "verts_base": verts,
            "faces": faces,
            "translate": [0.0, 0.0, 0.0],
            "rotate": [0.0, 0.0, 0.0],
            "scale": 1.0,
            "color": "#44aaff",
        }
        self._ws_listbox.insert(tk.END, sid)
        self._ws_redraw()
        log_message(f"WORKSHOP: Loaded STL '{name}' ({len(faces)} triangles)")

    # ===========================================================================
    # MODEL LIBRARY — scans a directory tree for .stl/.obj files
    # ===========================================================================
    def _build_library_view(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # --- Top bar: path selector ---
        top = ttk.Frame(parent, padding=(5, 4))
        top.grid(row=0, column=0, sticky=tk.EW)
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Library root:").grid(row=0, column=0, padx=(0, 4))
        self._lib_path_var = tk.StringVar(value=str(_DEFAULT_LIB_ROOT))
        path_entry = ttk.Entry(top, textvariable=self._lib_path_var)
        path_entry.grid(row=0, column=1, sticky=tk.EW)
        ttk.Button(top, text="Browse…", command=self._lib_browse).grid(row=0, column=2, padx=(4, 0))
        ttk.Button(top, text="Scan", command=self._lib_scan).grid(row=0, column=3, padx=(4, 0))

        # --- Main: treeview of models ---
        tree_frame = ttk.Frame(parent)
        tree_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=5, pady=5)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self._lib_tree = ttk.Treeview(
            tree_frame,
            columns=("size", "tris"),
            selectmode="browse",
        )
        self._lib_tree.heading("#0", text="Model")
        self._lib_tree.heading("size", text="Size")
        self._lib_tree.heading("tris", text="Triangles")
        self._lib_tree.column("#0", stretch=True, width=260)
        self._lib_tree.column("size", width=70, anchor=tk.E)
        self._lib_tree.column("tris", width=80, anchor=tk.E)
        self._lib_tree.grid(row=0, column=0, sticky=tk.NSEW)

        sb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._lib_tree.yview)
        sb.grid(row=0, column=1, sticky=tk.NS)
        self._lib_tree.configure(yscrollcommand=sb.set)

        self._lib_tree.bind("<Double-1>", self._lib_load_selected)
        self._lib_path_map = {}  # tree item id → file path

        # --- Bottom bar ---
        bot = ttk.Frame(parent, padding=(5, 4))
        bot.grid(row=2, column=0, sticky=tk.EW)
        self._lib_status = ttk.Label(bot, text="Click Scan to list models.")
        self._lib_status.pack(side=tk.LEFT)
        ttk.Button(bot, text="Load into Workshop",
                   command=self._lib_load_selected).pack(side=tk.RIGHT)

        # Auto-scan on open if default path exists
        if _DEFAULT_LIB_ROOT.exists():
            self.root.after(300, self._lib_scan)

    def _lib_browse(self):
        d = filedialog.askdirectory(title="Select model library root",
                                     initialdir=self._lib_path_var.get())
        if d:
            self._lib_path_var.set(d)
            self._lib_scan()

    def _lib_scan(self):
        """Scan library root for .stl files and populate the treeview."""
        root_path = Path(self._lib_path_var.get())
        if not root_path.exists():
            self._lib_status.config(text=f"Path not found: {root_path}")
            return

        # Clear tree
        for item in self._lib_tree.get_children():
            self._lib_tree.delete(item)
        self._lib_path_map.clear()

        # Collect .stl files, group by parent folder
        stl_files = sorted(root_path.rglob("*.stl"))
        if not stl_files:
            self._lib_status.config(text="No .stl files found.")
            return

        folder_nodes = {}
        for fp in stl_files:
            folder = fp.parent
            rel_folder = folder.relative_to(root_path) if folder != root_path else Path(".")
            folder_key = str(rel_folder)

            if folder_key not in folder_nodes:
                label = folder_key if folder_key != "." else root_path.name
                node = self._lib_tree.insert("", tk.END, text=f"📁 {label}", open=True)
                folder_nodes[folder_key] = node

            size_kb = fp.stat().st_size / 1024
            size_str = f"{size_kb:.0f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"

            # Quick triangle count from binary STL header (4 bytes at offset 80) — no full parse
            tris_str = "?"
            try:
                import struct
                with open(fp, 'rb') as fh:
                    fh.seek(80)
                    raw = fh.read(4)
                    if len(raw) == 4:
                        tris_str = str(struct.unpack('<I', raw)[0])
            except Exception:
                pass

            item = self._lib_tree.insert(
                folder_nodes[folder_key], tk.END,
                text=fp.stem,
                values=(size_str, tris_str),
            )
            self._lib_path_map[item] = str(fp)

        self._lib_status.config(
            text=f"{len(stl_files)} models found in {root_path.name}")

    def _lib_load_selected(self, event=None):
        """Load selected model into the Workshop for viewing."""
        sel = self._lib_tree.selection()
        if not sel:
            return
        item = sel[0]
        fp = self._lib_path_map.get(item)
        if not fp:
            return  # folder row, not a file

        # Switch to Workshop tab
        try:
            self.notebook.select(self.workshop_frame)
        except Exception:
            pass

        # Load into workshop
        self._ws_import_stl(filepath=fp)
        self._lib_status.config(text=f"Loaded: {Path(fp).name}")

    # ═══════════════════════════════════════════════════════════════════════════
    # SUB-VIEW 5 — ScratchPad Lab
    # Omega/alpha blind-retry mutation engine.
    # Loads Python source patterns from pattern_master domains or variants builds,
    # mutates them via AST transforms, checks structural novelty, and logs
    # successful novel patterns and blocked fkdupmutants.
    # ═══════════════════════════════════════════════════════════════════════════

    # ── Path constants ─────────────────────────────────────────────────────────
    _SP_PYMANIFEST   = Path.home() / "Trainer" / "Data" / "pymanifest"
    _SP_PM_ROOT      = _SP_PYMANIFEST / "pattern_master"
    _SP_VARIANTS_ROOT = _SP_PYMANIFEST / "variants"
    _SP_SCRATCH_JSON = _SP_PYMANIFEST / "variants" / "scratch_pad.json"

    # ── Status colours (match workshop dark palette) ───────────────────────────
    _SP_COL = {
        "SUCCESS":       "#4ec9b0",   # teal  — novel pattern
        "BLOCKED_COPY":  "#f44747",   # red   — exact duplicate
        "BLOCKED_SIM":   "#d7ba7d",   # amber — too similar
        "FAIL_SYNTAX":   "#858585",   # grey  — mutation broke syntax
        "PROMOTED":      "#e68aff",   # violet — saved to scratch_pad
        "RUNNING":       "#569cd6",   # blue  — in progress
    }

    def _build_scratchpad_lab(self, parent):
        """Build the ScratchPad Lab sub-tab UI."""
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)

        # ── Initialise state ───────────────────────────────────────────────────
        self._sp_stop_flag   = threading.Event()
        self._sp_results     = []       # [{attempt, src_name, status, grade, sha, code, sim}]
        self._sp_known_hashes = set()   # for copy-paste blocking
        self._sp_ast_corpus  = []       # AST dump strings for similarity

        # ── LEFT: controls panel ───────────────────────────────────────────────
        left = tk.Frame(parent, bg='#1a1a2e', width=230)
        left.grid(row=0, column=0, sticky=tk.NSEW, padx=(5, 3), pady=5)
        left.grid_propagate(False)

        # Source type
        src_lf = tk.LabelFrame(left, text="Source Type", bg='#1a1a2e', fg='#d4d4d4',
                                font=('Consolas', 9, 'bold'))
        src_lf.pack(fill=tk.X, padx=4, pady=(4, 2))
        self._sp_src_type = tk.StringVar(value="pattern_master")
        for val, lbl in [("pattern_master", "pattern_master/"),
                         ("variants",        "variants/ builds"),
                         ("scratch_pad",     "scratch_pad.json")]:
            tk.Radiobutton(src_lf, text=lbl, variable=self._sp_src_type, value=val,
                           bg='#1a1a2e', fg='#d4d4d4', selectcolor='#2b2b2b',
                           activebackground='#1a1a2e', activeforeground='#4488ff',
                           command=self._sp_refresh_sources).pack(anchor=tk.W, padx=4)

        # Domain / source listbox
        dom_lf = tk.LabelFrame(left, text="Domain / Source", bg='#1a1a2e', fg='#d4d4d4',
                                font=('Consolas', 9, 'bold'))
        dom_lf.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        self._sp_src_lb = tk.Listbox(dom_lf, bg='#2b2b2b', fg='white',
                                      selectbackground='#4488ff',
                                      selectforeground='white',
                                      activestyle='dotbox',
                                      font=('Consolas', 8), exportselection=False)
        sp_sb = ttk.Scrollbar(dom_lf, orient=tk.VERTICAL, command=self._sp_src_lb.yview)
        self._sp_src_lb.configure(yscrollcommand=sp_sb.set)
        self._sp_src_lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sp_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._sp_src_lb.bind('<<ListboxSelect>>', self._sp_on_source_select)

        # Settings
        cfg_lf = tk.LabelFrame(left, text="Settings", bg='#1a1a2e', fg='#d4d4d4',
                                font=('Consolas', 9, 'bold'))
        cfg_lf.pack(fill=tk.X, padx=4, pady=2)

        def _lbl_slider(frame, label, var, from_, to, resolution):
            row = tk.Frame(frame, bg='#1a1a2e')
            row.pack(fill=tk.X, padx=3, pady=1)
            tk.Label(row, text=label, bg='#1a1a2e', fg='#d4d4d4',
                     font=('Consolas', 8), width=12, anchor='w').pack(side=tk.LEFT)
            val_lbl = tk.Label(row, bg='#1a1a2e', fg='#4488ff',
                               font=('Consolas', 8), width=5, anchor='e')
            val_lbl.pack(side=tk.RIGHT)
            def _update_lbl(v, lbl=val_lbl, vr=var):
                lbl.config(text=f"{float(v):.2f}")
            s = tk.Scale(frame, variable=var, from_=from_, to=to, resolution=resolution,
                         orient=tk.HORIZONTAL, bg='#1a1a2e', fg='#d4d4d4',
                         troughcolor='#2b2b2b', highlightthickness=0,
                         showvalue=False, command=_update_lbl)
            s.pack(fill=tk.X, padx=4)
            _update_lbl(var.get())
            return s

        self._sp_iters_var  = tk.IntVar(value=10)
        self._sp_mutrate_var = tk.DoubleVar(value=0.7)
        self._sp_simthr_var  = tk.DoubleVar(value=0.995)

        # iterations as spinbox
        irow = tk.Frame(cfg_lf, bg='#1a1a2e')
        irow.pack(fill=tk.X, padx=3, pady=2)
        tk.Label(irow, text="Iterations", bg='#1a1a2e', fg='#d4d4d4',
                 font=('Consolas', 8), width=12, anchor='w').pack(side=tk.LEFT)
        ttk.Spinbox(irow, from_=1, to=200, textvariable=self._sp_iters_var,
                    width=6).pack(side=tk.RIGHT)

        _lbl_slider(cfg_lf, "Mutation rate", self._sp_mutrate_var, 0.1, 1.0, 0.05)
        _lbl_slider(cfg_lf, "Block sim ≥",   self._sp_simthr_var,  0.5, 1.0, 0.05)

        # Buttons
        btn_lf = tk.Frame(left, bg='#1a1a2e')
        btn_lf.pack(fill=tk.X, padx=4, pady=(4, 2))
        btn_cfg = dict(font=('Consolas', 9, 'bold'), relief=tk.FLAT,
                       cursor='hand2', pady=3)
        self._sp_run_btn = tk.Button(btn_lf, text="▶  Run",
                                      bg='#1a5522', fg='#4ec9b0',
                                      command=self._sp_run, **btn_cfg)
        self._sp_run_btn.pack(fill=tk.X, pady=1)
        tk.Button(btn_lf, text="■  Stop",
                  bg='#551a1a', fg='#f44747',
                  command=self._sp_stop, **btn_cfg).pack(fill=tk.X, pady=1)
        tk.Button(btn_lf, text="↑  Promote to DB",
                  bg='#2d1a4d', fg='#e68aff',
                  command=self._sp_promote, **btn_cfg).pack(fill=tk.X, pady=1)
        tk.Button(btn_lf, text="✕  Clear log",
                  bg='#2b2b2b', fg='#858585',
                  command=self._sp_clear, **btn_cfg).pack(fill=tk.X, pady=1)

        # ── RIGHT: results + preview ───────────────────────────────────────────
        right = tk.Frame(parent, bg='#1a1a2e')
        right.grid(row=0, column=1, sticky=tk.NSEW, padx=(0, 5), pady=5)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=2)
        right.rowconfigure(1, weight=3)
        right.rowconfigure(2, weight=0)

        # Results treeview
        res_lf = tk.LabelFrame(right, text="Mutation Log", bg='#1a1a2e', fg='#d4d4d4',
                                font=('Consolas', 9, 'bold'))
        res_lf.grid(row=0, column=0, sticky=tk.NSEW, pady=(0, 3))
        res_lf.columnconfigure(0, weight=1)
        res_lf.rowconfigure(0, weight=1)

        cols = ("#", "Source", "Status", "Grade", "SHA", "Sim%")
        self._sp_tree = ttk.Treeview(res_lf, columns=cols, show='headings',
                                      height=8, selectmode='browse')
        for col, width in zip(cols, [40, 160, 110, 50, 80, 55]):
            self._sp_tree.heading(col, text=col)
            self._sp_tree.column(col, width=width, anchor='center')
        self._sp_tree.column("Source", anchor='w')

        # colour tags
        for tag, colour in self._SP_COL.items():
            self._sp_tree.tag_configure(tag, foreground=colour)

        tree_sb = ttk.Scrollbar(res_lf, orient=tk.VERTICAL, command=self._sp_tree.yview)
        self._sp_tree.configure(yscrollcommand=tree_sb.set)
        self._sp_tree.grid(row=0, column=0, sticky=tk.NSEW)
        tree_sb.grid(row=0, column=1, sticky=tk.NS)
        self._sp_tree.bind('<<TreeviewSelect>>', self._sp_on_select)

        # Code preview
        prev_lf = tk.LabelFrame(right, text="Mutant Code Preview",
                                 bg='#1a1a2e', fg='#d4d4d4',
                                 font=('Consolas', 9, 'bold'))
        prev_lf.grid(row=1, column=0, sticky=tk.NSEW, pady=(0, 3))
        prev_lf.columnconfigure(0, weight=1)
        prev_lf.rowconfigure(0, weight=1)
        self._sp_preview = tk.Text(prev_lf, bg='#2b2b2b', fg='#d4d4d4',
                                    insertbackground='white',
                                    font=('Consolas', 9), wrap=tk.NONE,
                                    state=tk.DISABLED)
        prev_xsb = ttk.Scrollbar(prev_lf, orient=tk.HORIZONTAL,
                                  command=self._sp_preview.xview)
        prev_ysb = ttk.Scrollbar(prev_lf, orient=tk.VERTICAL,
                                  command=self._sp_preview.yview)
        self._sp_preview.configure(xscrollcommand=prev_xsb.set,
                                    yscrollcommand=prev_ysb.set)
        self._sp_preview.grid(row=0, column=0, sticky=tk.NSEW)
        prev_ysb.grid(row=0, column=1, sticky=tk.NS)
        prev_xsb.grid(row=1, column=0, sticky=tk.EW)

        # Status bar
        stat_frame = tk.Frame(right, bg='#0d0d1a', height=24)
        stat_frame.grid(row=2, column=0, sticky=tk.EW)
        stat_frame.columnconfigure(1, weight=1)
        self._sp_status_var = tk.StringVar(value="Ready")
        tk.Label(stat_frame, textvariable=self._sp_status_var,
                 bg='#0d0d1a', fg='#569cd6', font=('Consolas', 8),
                 anchor='w').grid(row=0, column=0, sticky=tk.W, padx=6)
        self._sp_prog = ttk.Progressbar(stat_frame, mode='determinate', length=180)
        self._sp_prog.grid(row=0, column=1, sticky=tk.E, padx=6)

        # Seed source list immediately
        self._sp_refresh_sources()

    # ── Source management ──────────────────────────────────────────────────────

    def _sp_refresh_sources(self):
        """Populate the domain listbox based on selected source type."""
        self._sp_src_lb.delete(0, tk.END)
        src_type = self._sp_src_type.get()

        if src_type == "pattern_master":
            if self._SP_PM_ROOT.exists():
                items = sorted(
                    d.name for d in self._SP_PM_ROOT.iterdir()
                    if d.is_dir() and d.name not in ('Archive', '__pycache__', 'docs')
                    and any(d.rglob('*.py'))
                )
                for item in items:
                    self._sp_src_lb.insert(tk.END, item)

        elif src_type == "variants":
            if self._SP_VARIANTS_ROOT.exists():
                # Only the .py build files (omega_*.py, alpha_*.py, specialist_*.py)
                items = sorted(
                    f.name for f in self._SP_VARIANTS_ROOT.iterdir()
                    if f.suffix == '.py' and not f.name.startswith('v0')
                )
                for item in items:
                    self._sp_src_lb.insert(tk.END, item)

        elif src_type == "scratch_pad":
            if self._SP_SCRATCH_JSON.exists():
                with self._SP_SCRATCH_JSON.open() as f:
                    sp = json.load(f)
                for key in sorted(k for k in sp if not k.startswith('_')):
                    count = len(sp[key]) if isinstance(sp[key], list) else 1
                    self._sp_src_lb.insert(tk.END, f"{key}  ({count})")

    def _sp_on_source_select(self, _event=None):
        """Show item count in status when a source is selected."""
        sel = self._sp_src_lb.curselection()
        if not sel:
            return
        name = self._sp_src_lb.get(sel[0])
        self._sp_status_var.set(f"Selected: {name.split()[0]}")

    def _sp_load_source_files(self, source_name):
        """Return list of (name, code) tuples for the selected source."""
        src_type = self._sp_src_type.get()
        results = []

        if src_type == "pattern_master":
            domain_dir = self._SP_PM_ROOT / source_name
            if domain_dir.exists():
                for py in sorted(domain_dir.rglob('*.py'))[:80]:
                    if py.name.startswith('__'):
                        continue
                    try:
                        code = py.read_text(encoding='utf-8', errors='ignore')
                        if len(code.strip()) > 50:
                            results.append((py.stem, code))
                    except OSError:
                        pass

        elif src_type == "variants":
            py_path = self._SP_VARIANTS_ROOT / source_name
            if py_path.exists():
                try:
                    code = py_path.read_text(encoding='utf-8', errors='ignore')
                    results.append((source_name[:-3], code))
                except OSError:
                    pass

        elif src_type == "scratch_pad":
            domain = source_name.split()[0]
            if self._SP_SCRATCH_JSON.exists():
                with self._SP_SCRATCH_JSON.open() as f:
                    sp = json.load(f)
                for item in sp.get(domain, []):
                    if isinstance(item, dict) and item.get('content'):
                        content = str(item['content'])
                        # Wrap bare tokens as a stub function
                        code = (
                            f"def pattern_{item.get('id','x')[:8]}():\n"
                            f"    \"\"\"{domain}: {content}\"\"\"\n"
                            f"    return '{content}'\n"
                        )
                        results.append((f"{domain}_{item.get('id','?')[:6]}", code))
        return results

    # ── Mutation engine ────────────────────────────────────────────────────────

    # ── Mutation strategies ────────────────────────────────────────────────────

    def _sp_mutate(self, source_code, mutation_rate):
        """
        Apply multi-strategy AST mutations to source_code.
        Chooses 1–3 strategies randomly, weighted by mutation_rate.
        Returns mutated source string, or None on unrecoverable failure.

        Strategies:
          AST_RENAME   — rename functions, args; shuffle imports
          AST_OPS      — swap binary/comparison operators, tweak constants
          FOR_TO_WHILE — convert for-range loops → while loops
          DEADVAR      — inject an unused variable at the top of each function
          EXTRACT_FUNC — isolate one random top-level function as a standalone snippet
          SLICE_TOP    — keep only the first N top-level defs (partial extraction)
        """
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return None

        rng = random.Random()

        # Pick strategies based on mutation_rate
        all_strategies = ['AST_RENAME', 'AST_OPS', 'FOR_TO_WHILE', 'DEADVAR',
                          'EXTRACT_FUNC', 'SLICE_TOP']
        n_strats = 1 + int(mutation_rate * 2.5)
        strategies = set(rng.choices(all_strategies, k=n_strats))

        # ── Strategy: AST_RENAME ──────────────────────────────────────────
        if 'AST_RENAME' in strategies:
            class _Renamer(ast.NodeTransformer):
                def visit_FunctionDef(self, node):
                    if rng.random() < mutation_rate and not node.name.startswith('_'):
                        node.name = node.name + rng.choice(['_v2','_mut','_alt','_morph','_derived'])
                    for arg in node.args.args:
                        if rng.random() < mutation_rate * 0.5 and arg.arg not in ('self','cls'):
                            arg.arg = arg.arg + '_m'
                    self.generic_visit(node)
                    return node
                def visit_Constant(self, node):
                    if isinstance(node.value, str) and len(node.value) > 2:
                        if rng.random() < mutation_rate * 0.3:
                            node.value = node.value + '_m'
                    return node
            try:
                tree = _Renamer().visit(tree)
                ast.fix_missing_locations(tree)
            except Exception:
                pass
            # Shuffle imports
            if mutation_rate > 0.5:
                top    = tree.body
                imps   = [n for n in top if isinstance(n, (ast.Import, ast.ImportFrom))]
                rest   = [n for n in top if not isinstance(n, (ast.Import, ast.ImportFrom))]
                rng.shuffle(imps)
                tree.body = imps + rest

        # ── Strategy: AST_OPS ─────────────────────────────────────────────
        if 'AST_OPS' in strategies:
            class _OpMutator(ast.NodeTransformer):
                def visit_BinOp(self, node):
                    swaps = {ast.Add: ast.Sub, ast.Sub: ast.Add,
                             ast.Mult: ast.Div, ast.Div: ast.Mult}
                    if rng.random() < mutation_rate * 0.5 and type(node.op) in swaps:
                        node.op = swaps[type(node.op)]()
                    self.generic_visit(node)
                    return node
                def visit_Constant(self, node):
                    if isinstance(node.value, (int, float)) and node.value not in (0, 1, -1):
                        if rng.random() < mutation_rate * 0.6:
                            node.value = type(node.value)(node.value * rng.uniform(0.8, 1.25))
                    return node
                def visit_Compare(self, node):
                    flips = {ast.Lt: ast.Gt, ast.Gt: ast.Lt,
                             ast.LtE: ast.GtE, ast.GtE: ast.LtE}
                    node.ops = [
                        flips[type(op)]() if rng.random() < mutation_rate * 0.4
                        and type(op) in flips else op
                        for op in node.ops
                    ]
                    self.generic_visit(node)
                    return node
            try:
                tree = _OpMutator().visit(tree)
                ast.fix_missing_locations(tree)
            except Exception:
                pass

        # ── Strategy: FOR_TO_WHILE — convert for-range → while ────────────
        if 'FOR_TO_WHILE' in strategies:
            class _ForToWhile(ast.NodeTransformer):
                def visit_For(self, node):
                    self.generic_visit(node)
                    # Only convert  for VAR in range(N):  patterns
                    if (rng.random() < mutation_rate * 0.6
                            and isinstance(node.target, ast.Name)
                            and isinstance(node.iter, ast.Call)
                            and isinstance(node.iter.func, ast.Name)
                            and node.iter.func.id == 'range'
                            and len(node.iter.args) == 1):
                        v = node.target.id
                        limit_node = node.iter.args[0]
                        # while v < N: ... v += 1
                        new_body = list(node.body) + [
                            ast.AugAssign(
                                target=ast.Name(id=v, ctx=ast.Store()),
                                op=ast.Add(),
                                value=ast.Constant(value=1),
                            )
                        ]
                        while_node = ast.While(
                            test=ast.Compare(
                                left=ast.Name(id=v, ctx=ast.Load()),
                                ops=[ast.Lt()],
                                comparators=[limit_node],
                            ),
                            body=new_body,
                            orelse=node.orelse,
                        )
                        # Prepend  v = 0
                        assign = ast.Assign(
                            targets=[ast.Name(id=v, ctx=ast.Store())],
                            value=ast.Constant(value=0),
                        )
                        return [assign, while_node]
                    return node
            try:
                new_body = []
                for stmt in tree.body:
                    result = _ForToWhile().visit(stmt)
                    if isinstance(result, list):
                        new_body.extend(result)
                    else:
                        new_body.append(result)
                tree.body = new_body
                ast.fix_missing_locations(tree)
            except Exception:
                pass

        # ── Strategy: DEADVAR — inject unused vars in function bodies ──────
        if 'DEADVAR' in strategies:
            deadvar_names = ['_unused', '_tmp_morph', '_dead', '_noop', '_sentinel']
            class _DeadVarInjector(ast.NodeTransformer):
                def visit_FunctionDef(self, node):
                    self.generic_visit(node)
                    if rng.random() < mutation_rate * 0.7 and node.body:
                        varname = rng.choice(deadvar_names)
                        inject = ast.Assign(
                            targets=[ast.Name(id=varname, ctx=ast.Store())],
                            value=ast.Constant(value=rng.randint(0, 255)),
                        )
                        node.body.insert(1, inject)
                    return node
            try:
                tree = _DeadVarInjector().visit(tree)
                ast.fix_missing_locations(tree)
            except Exception:
                pass

        # ── Strategy: EXTRACT_FUNC — isolate one function ─────────────────
        if 'EXTRACT_FUNC' in strategies:
            funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
            if funcs and rng.random() < mutation_rate:
                chosen = rng.choice(funcs)
                imports = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
                tree.body = imports + [chosen]

        # ── Strategy: SLICE_TOP — keep first N top-level items ─────────────
        elif 'SLICE_TOP' in strategies:
            if len(tree.body) > 4 and rng.random() < mutation_rate * 0.5:
                keep = rng.randint(max(2, len(tree.body) // 3), len(tree.body))
                tree.body = tree.body[:keep]

        try:
            ast.fix_missing_locations(tree)
            return ast.unparse(tree)
        except Exception:
            return None

    def _sp_hash(self, code):
        return hashlib.sha256(code.encode('utf-8', errors='ignore')).hexdigest()[:12]

    def _sp_similarity(self, code_a, code_b):
        """
        Blended similarity: 60% normalised-source text ratio
        + 40% identifier-set Jaccard distance.
        Normalised source (via ast.unparse) strips formatting noise so
        renames and constant swaps register as real differences.
        """
        def _idents(code):
            try:
                return {n.id for n in ast.walk(ast.parse(code))
                        if isinstance(n, ast.Name)}
            except SyntaxError:
                return set()

        try:
            a_norm = ast.unparse(ast.parse(code_a))
        except SyntaxError:
            a_norm = code_a[:3000]
        try:
            b_norm = ast.unparse(ast.parse(code_b))
        except SyntaxError:
            b_norm = code_b[:3000]

        text_sim = difflib.SequenceMatcher(None, a_norm, b_norm,
                                           autojunk=False).ratio()
        ids_a, ids_b = _idents(code_a), _idents(code_b)
        union = ids_a | ids_b
        jaccard = len(ids_a & ids_b) / len(union) if union else 1.0

        return 0.60 * text_sim + 0.40 * jaccard

    def _sp_grade(self, code, sim):
        """
        Grade by novelty (lower sim = more novel).
        Calibrated for multi-strategy mutations (range 0.60–0.995 observed).
          A: sim < 0.80   — major structural divergence (EXTRACT / FOR→WHILE)
          B: sim < 0.88   — significant mutations across multiple strategies
          C: sim < 0.93   — meaningful mutations, identifiable novelty
          D: sim < 0.995  — minor mutations, passes copy-paste gate
          F: syntax fail
        """
        try:
            ast.parse(code)
        except SyntaxError:
            return 'F'
        if sim < 0.80:   return 'A'
        if sim < 0.88:   return 'B'
        if sim < 0.93:   return 'C'
        return 'D'

    # ── Run loop ───────────────────────────────────────────────────────────────

    def _sp_run(self):
        sel = self._sp_src_lb.curselection()
        if not sel:
            self._sp_status_var.set("Select a source first.")
            return
        source_name = self._sp_src_lb.get(sel[0]).split()[0]
        n_iters     = self._sp_iters_var.get()
        mut_rate    = self._sp_mutrate_var.get()
        sim_thr     = self._sp_simthr_var.get()

        self._sp_stop_flag.clear()
        self._sp_run_btn.config(state=tk.DISABLED)

        t = threading.Thread(
            target=self._sp_worker,
            args=(source_name, n_iters, mut_rate, sim_thr),
            daemon=True,
        )
        t.start()

    def _sp_stop(self):
        self._sp_stop_flag.set()
        self._sp_status_var.set("Stopping…")

    def _sp_worker(self, source_name, n_iters, mut_rate, sim_thr):
        """Background mutation loop."""
        def _ui(fn):
            try:
                self.parent.after(0, fn)
            except Exception:
                pass

        _ui(lambda: self._sp_prog.config(value=0, maximum=n_iters))

        source_files = self._sp_load_source_files(source_name)
        if not source_files:
            _ui(lambda: self._sp_status_var.set(f"No Python files found in '{source_name}'."))
            _ui(lambda: self._sp_run_btn.config(state=tk.NORMAL))
            return

        # Pre-load corpus hashes from source files
        existing_hashes = set(self._sp_hash(code) for _, code in source_files)
        existing_hashes.update(self._sp_known_hashes)

        attempt = len(self._sp_results)
        n_success = n_blocked_copy = n_blocked_sim = n_fail = 0

        for i in range(n_iters):
            if self._sp_stop_flag.is_set():
                break

            # Pick a random source
            src_name, src_code = random.choice(source_files)

            # Generate mutant
            mutant = self._sp_mutate(src_code, mut_rate)

            attempt += 1

            if mutant is None:
                status = "FAIL_SYNTAX"
                grade  = "F"
                sha    = "—"
                sim    = 0.0
                n_fail += 1
            else:
                sha = self._sp_hash(mutant)

                # Gate 1: copy-paste detection
                if sha in existing_hashes:
                    status = "BLOCKED_COPY"
                    grade  = "F"
                    sim    = 1.0
                    n_blocked_copy += 1
                else:
                    # Gate 2: AST structural similarity vs corpus
                    max_sim = max(
                        (self._sp_similarity(mutant, c) for _, c in source_files),
                        default=0.0,
                    )
                    # Also check against previously generated mutants (last 20)
                    recent = [r['code'] for r in self._sp_results[-20:]
                              if r.get('code') and r['status'] == 'SUCCESS']
                    for rc in recent:
                        max_sim = max(max_sim, self._sp_similarity(mutant, rc))

                    sim = round(max_sim, 3)
                    if sim >= sim_thr:
                        status = "BLOCKED_SIM"
                        grade  = "F"
                        n_blocked_sim += 1
                    else:
                        # Gate 3: syntax validation
                        try:
                            ast.parse(mutant)
                            status = "SUCCESS"
                            grade  = self._sp_grade(mutant, sim)
                            existing_hashes.add(sha)
                            self._sp_known_hashes.add(sha)
                            self._sp_ast_corpus.append(ast.dump(ast.parse(mutant)))
                            n_success += 1
                        except SyntaxError:
                            status = "FAIL_SYNTAX"
                            grade  = "F"
                            n_fail += 1

            record = {
                'attempt':  attempt,
                'src_name': src_name,
                'status':   status,
                'grade':    grade,
                'sha':      sha,
                'sim':      sim,
                'code':     mutant or '',
            }
            self._sp_results.append(record)

            # Update UI (capture record in closure)
            def _add_row(r=record, idx=i + 1):
                sim_pct = f"{r['sim']*100:.0f}%" if r['sim'] else "—"
                self._sp_tree.insert(
                    '', tk.END,
                    values=(r['attempt'], r['src_name'][:22],
                            r['status'], r['grade'], r['sha'], sim_pct),
                    tags=(r['status'],),
                )
                self._sp_tree.yview_moveto(1.0)
                self._sp_prog.config(value=idx)
                ns   = sum(1 for x in self._sp_results if x['status'] == 'SUCCESS')
                nb   = sum(1 for x in self._sp_results
                           if x['status'].startswith('BLOCKED'))
                nf   = sum(1 for x in self._sp_results if x['status'] == 'FAIL_SYNTAX')
                tot  = len(self._sp_results)
                self._sp_status_var.set(
                    f"{tot} attempts  |  {ns} novel  |  {nb} fkdupmutants  |  {nf} broken"
                )
            _ui(_add_row)

            _time.sleep(0.01)   # yield to UI thread

        def _done():
            self._sp_run_btn.config(state=tk.NORMAL)
            ns = sum(1 for r in self._sp_results if r['status'] == 'SUCCESS')
            nb = sum(1 for r in self._sp_results if r['status'].startswith('BLOCKED'))
            self._sp_status_var.set(
                f"Done — {ns} novel patterns  |  {nb} fkdupmutants blocked"
            )
        _ui(_done)

    # ── Result interaction ─────────────────────────────────────────────────────

    def _sp_on_select(self, _event=None):
        """Show selected mutant code in the preview pane."""
        sel = self._sp_tree.selection()
        if not sel:
            return
        vals = self._sp_tree.item(sel[0], 'values')
        if not vals:
            return
        try:
            attempt_no = int(vals[0])
        except (ValueError, IndexError):
            return
        record = next((r for r in self._sp_results if r['attempt'] == attempt_no), None)
        if not record:
            return
        code = record.get('code', '')
        self._sp_preview.config(state=tk.NORMAL)
        self._sp_preview.delete('1.0', tk.END)
        if code:
            header = (
                f"# attempt {record['attempt']}  "
                f"source={record['src_name']}  "
                f"status={record['status']}  "
                f"grade={record['grade']}  "
                f"sim={record['sim']:.3f}  "
                f"sha={record['sha']}\n"
                f"# {'─' * 60}\n"
            )
            self._sp_preview.insert(tk.END, header + code)
        else:
            self._sp_preview.insert(tk.END, "# (no code — syntax failure or blocked before generation)")
        self._sp_preview.config(state=tk.DISABLED)

    def _sp_promote(self):
        """Save selected SUCCESS pattern to scratch_pad.json under its source domain."""
        sel = self._sp_tree.selection()
        if not sel:
            self._sp_status_var.set("Select a result row to promote.")
            return
        vals = self._sp_tree.item(sel[0], 'values')
        try:
            attempt_no = int(vals[0])
        except (ValueError, IndexError):
            return
        record = next((r for r in self._sp_results if r['attempt'] == attempt_no), None)
        if not record or record['status'] != 'SUCCESS':
            self._sp_status_var.set("Only SUCCESS patterns can be promoted.")
            return

        domain = self._sp_src_type.get()
        entry = {
            "id":      record['sha'],
            "type":    "mutant_pattern",
            "content": record['code'][:400],
            "origin":  f"scratchpad_lab/{record['src_name']}",
            "weight":  {"A": 1.0, "B": 0.75, "C": 0.5, "D": 0.25}.get(record['grade'], 0.1),
            "ttl":     10,
            "meta":    {"grade": record['grade'], "sim": record['sim']},
        }

        try:
            if self._SP_SCRATCH_JSON.exists():
                with self._SP_SCRATCH_JSON.open() as f:
                    sp = json.load(f)
            else:
                sp = {}
            sp.setdefault(domain, [])
            if not any(e.get('id') == entry['id'] for e in sp[domain]):
                sp[domain].append(entry)
                with self._SP_SCRATCH_JSON.open('w') as f:
                    json.dump(sp, f, indent=2)
                # Update treeview row tag
                self._sp_tree.item(sel[0], tags=('PROMOTED',))
                self._sp_status_var.set(
                    f"Promoted SHA {record['sha']} → scratch_pad[{domain}]"
                )
            else:
                self._sp_status_var.set("Already in scratch_pad (SHA match).")
        except Exception as e:
            self._sp_status_var.set(f"Promote failed: {e}")

    def _sp_clear(self):
        """Clear the mutation log and reset counters."""
        self._sp_results.clear()
        self._sp_known_hashes.clear()
        self._sp_ast_corpus.clear()
        for row in self._sp_tree.get_children():
            self._sp_tree.delete(row)
        self._sp_preview.config(state=tk.NORMAL)
        self._sp_preview.delete('1.0', tk.END)
        self._sp_preview.config(state=tk.DISABLED)
        self._sp_prog.config(value=0)
        self._sp_status_var.set("Cleared.")

    # ═══════════════════════════════════════════════════════════════════════════
    # Ω Lens — Sub-tab 6: Omega/Alpha Pattern Inspector
    # ═══════════════════════════════════════════════════════════════════════════

    # Tier badge colours
    _OL_TIER_COL = {
        "omega":    "#569cd6",   # blue
        "alpha":    "#4ec9b0",   # teal
        "fix":      "#d7ba7d",   # amber
        "mutant":   "#e68aff",   # violet
        "ancestor": "#858585",   # grey
    }

    def _build_omega_lens(self, parent):
        """Build the Ω Lens sub-tab: lineage tree (left) + 4-tab inspector (right)."""
        parent.columnconfigure(0, minsize=260)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)

        # ── Initialise state ───────────────────────────────────────────────────
        self._ol_active_variant  = None   # currently selected variant name
        self._ol_patterns_cache  = {}     # {variant_name: [row_dict, ...]}
        self._ol_patterns_all    = []     # flat list for current variant (for filtering)

        # ── LEFT: lineage pane ─────────────────────────────────────────────────
        left = ttk.LabelFrame(parent, text="Lineage", padding=4)
        left.grid(row=0, column=0, sticky=tk.NSEW, padx=(6, 2), pady=6)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        cols = ('tier', 'gen', 'patterns')
        self._ol_lineage_tree = ttk.Treeview(left, columns=cols, show='tree headings',
                                              selectmode='browse', height=28)
        self._ol_lineage_tree.heading('#0',       text='Name')
        self._ol_lineage_tree.heading('tier',     text='Tier')
        self._ol_lineage_tree.heading('gen',      text='Gen')
        self._ol_lineage_tree.heading('patterns', text='Patterns')
        self._ol_lineage_tree.column('#0',        width=110, stretch=True)
        self._ol_lineage_tree.column('tier',      width=56,  stretch=False)
        self._ol_lineage_tree.column('gen',       width=32,  stretch=False)
        self._ol_lineage_tree.column('patterns',  width=60,  stretch=False)

        vsb = ttk.Scrollbar(left, orient='vertical',   command=self._ol_lineage_tree.yview)
        self._ol_lineage_tree.configure(yscrollcommand=vsb.set)
        self._ol_lineage_tree.grid(row=0, column=0, sticky=tk.NSEW)
        vsb.grid(row=0, column=1, sticky=tk.NS)

        self._ol_info_var = tk.StringVar(value="Select a variant")
        ttk.Label(left, textvariable=self._ol_info_var, wraplength=240,
                  foreground='#cccccc').grid(row=1, column=0, columnspan=2,
                                             sticky=tk.EW, pady=(4, 0))

        self._ol_lineage_tree.bind('<<TreeviewSelect>>', self._ol_on_lineage_select)

        # ── RIGHT: 4-tab inspector ─────────────────────────────────────────────
        self._ol_right_nb = ttk.Notebook(parent)
        self._ol_right_nb.grid(row=0, column=1, sticky=tk.NSEW, padx=(2, 6), pady=6)

        # Tab 1 — Omega Patterns
        f_omega = ttk.Frame(self._ol_right_nb)
        self._ol_right_nb.add(f_omega, text="Omega Patterns")
        self._build_ol_patterns_tab(f_omega, alpha_mode=False)

        # Tab 2 — Alpha Patterns
        f_alpha = ttk.Frame(self._ol_right_nb)
        self._ol_right_nb.add(f_alpha, text="Alpha Patterns")
        self._build_ol_patterns_tab(f_alpha, alpha_mode=True)

        # Tab 3 — Scratch / Weights
        f_scratch = ttk.Frame(self._ol_right_nb)
        self._ol_right_nb.add(f_scratch, text="Scratch / Weights")
        self._build_ol_scratch_tab(f_scratch)

        # Tab 4 — Superposition
        f_super = ttk.Frame(self._ol_right_nb)
        self._ol_right_nb.add(f_super, text="Superposition")
        self._build_ol_superposition_tab(f_super)

        # Bind tab-selected refresh
        self.notebook.bind('<<NotebookTabChanged>>', self._ol_refresh)

        # Initial load
        self.parent.after(0, self._ol_load_lineage)

    def _build_ol_patterns_tab(self, parent, alpha_mode: bool):
        """Shared patterns viewer for both Omega Patterns and Alpha Patterns tabs."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Filter bar
        fbar = ttk.Frame(parent)
        fbar.grid(row=0, column=0, sticky=tk.EW, padx=4, pady=(4, 2))

        if alpha_mode:
            ttk.Label(fbar, text="Alpha:").pack(side=tk.LEFT, padx=(0, 2))
            self._ol_alpha_var = tk.StringVar(value="specialist_analysis")
            alpha_cb = ttk.Combobox(fbar, textvariable=self._ol_alpha_var, width=24,
                                    values=["specialist_analysis", "specialist_debug",
                                            "specialist_build", "specialist_semantic_systems",
                                            "specialist_neural_network", "specialist_planning"])
            alpha_cb.pack(side=tk.LEFT, padx=2)
            alpha_cb.bind('<<ComboboxSelected>>', lambda e: self._ol_load_alpha_patterns(
                self._ol_alpha_var.get()))
            self._ol_grade_var = tk.StringVar(value="")
            ttk.Label(fbar, textvariable=self._ol_grade_var,
                      foreground='#4ec9b0').pack(side=tk.LEFT, padx=8)
        else:
            ttk.Label(fbar, text="Type:").pack(side=tk.LEFT)
            self._ol_type_var = tk.StringVar(value="(all)")
            ttk.Combobox(fbar, textvariable=self._ol_type_var, width=20,
                         state='readonly').pack(side=tk.LEFT, padx=2)
            ttk.Label(fbar, text="Domain:").pack(side=tk.LEFT, padx=(6, 2))
            self._ol_domain_var = tk.StringVar(value="(all)")
            ttk.Combobox(fbar, textvariable=self._ol_domain_var, width=18,
                         state='readonly').pack(side=tk.LEFT, padx=2)
            ttk.Label(fbar, text="SHA:").pack(side=tk.LEFT, padx=(6, 2))
            self._ol_sha_var = tk.StringVar()
            sha_e = ttk.Entry(fbar, textvariable=self._ol_sha_var, width=12)
            sha_e.pack(side=tk.LEFT)
            for var in (self._ol_type_var, self._ol_domain_var):
                var.trace_add('write', lambda *_: self._ol_filter_patterns())
            self._ol_sha_var.trace_add('write', lambda *_: self._ol_filter_patterns())

        # Treeview
        cols = ('sha', 'type', 'domain', 'seen', 'count')
        tree = ttk.Treeview(parent, columns=cols, show='headings',
                             selectmode='browse', height=20)
        for col, w in zip(cols, (90, 120, 110, 55, 55)):
            tree.heading(col, text=col.title())
            tree.column(col, width=w, stretch=(col == 'type'))
        vsb2 = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb2.set)
        tree.grid(row=1, column=0, sticky=tk.NSEW, padx=(4, 0), pady=2)
        vsb2.grid(row=1, column=1, sticky=tk.NS)

        detail = tk.Text(parent, height=7, state=tk.DISABLED, wrap=tk.WORD,
                         background='#1e1e1e', foreground='#d4d4d4',
                         font=('Consolas', 9))
        detail.grid(row=2, column=0, columnspan=2, sticky=tk.EW, padx=4, pady=(0, 4))

        if alpha_mode:
            self._ol_alpha_tree   = tree
            self._ol_alpha_detail = detail
            tree.bind('<<TreeviewSelect>>', self._ol_on_alpha_pattern_select)
        else:
            self._ol_pat_tree   = tree
            self._ol_pat_detail = detail
            tree.bind('<<TreeviewSelect>>', self._ol_on_pattern_select)

    def _build_ol_scratch_tab(self, parent):
        """Scratch / Weights tab: matplotlib bar chart + item treeview."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=3)
        parent.rowconfigure(1, weight=1)

        if _MPL_OK:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            plot_frame = ttk.Frame(parent)
            plot_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=4, pady=4)
            plot_frame.columnconfigure(0, weight=1)
            plot_frame.rowconfigure(0, weight=1)
            self._ol_fig = Figure(figsize=(7, 3), facecolor='#1a1a2e')
            self._ol_ax  = self._ol_fig.add_subplot(111, facecolor='#1a1a2e')
            self._ol_canvas = FigureCanvasTkAgg(self._ol_fig, master=plot_frame)
            self._ol_canvas.get_tk_widget().grid(row=0, column=0, sticky=tk.NSEW)
        else:
            ttk.Label(parent, text="matplotlib not available — chart disabled").grid(
                row=0, column=0, pady=20)
            self._ol_fig = self._ol_ax = self._ol_canvas = None

        # Item treeview
        cols2 = ('id', 'type', 'weight', 'ttl', 'grade')
        self._ol_scratch_tree = ttk.Treeview(parent, columns=cols2, show='headings',
                                              height=8)
        for col, w in zip(cols2, (100, 90, 60, 40, 45)):
            self._ol_scratch_tree.heading(col, text=col.title())
            self._ol_scratch_tree.column(col, width=w, stretch=(col == 'id'))
        vsb3 = ttk.Scrollbar(parent, orient='vertical',
                              command=self._ol_scratch_tree.yview)
        self._ol_scratch_tree.configure(yscrollcommand=vsb3.set)
        self._ol_scratch_tree.grid(row=1, column=0, sticky=tk.NSEW, padx=(4, 0), pady=2)
        vsb3.grid(row=1, column=1, sticky=tk.NS)

    def _build_ol_superposition_tab(self, parent):
        """Superposition tab: turn selector + collapse chain treeview + summary."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        ctrl = ttk.Frame(parent)
        ctrl.grid(row=0, column=0, sticky=tk.EW, padx=4, pady=4)
        ttk.Label(ctrl, text="Turn:").pack(side=tk.LEFT)
        self._ol_turn_var = tk.IntVar(value=0)
        self._ol_turn_spin = ttk.Spinbox(ctrl, from_=0, to=50,
                                          textvariable=self._ol_turn_var, width=5,
                                          command=lambda: self._ol_show_superposition(
                                              self._ol_turn_var.get()))
        self._ol_turn_spin.pack(side=tk.LEFT, padx=4)
        self._ol_query_var = tk.StringVar(value="")
        ttk.Label(ctrl, textvariable=self._ol_query_var, foreground='#cccccc',
                  wraplength=500).pack(side=tk.LEFT, padx=8)

        cols3 = ('step', 'pid', 'type', 'domain', 'weight')
        self._ol_super_tree = ttk.Treeview(parent, columns=cols3, show='headings',
                                            height=16)
        for col, w in zip(cols3, (40, 110, 110, 100, 60)):
            self._ol_super_tree.heading(col, text=col.title() if col != 'pid' else 'Pattern ID')
            self._ol_super_tree.column(col, width=w, stretch=(col == 'pid'))
        vsb4 = ttk.Scrollbar(parent, orient='vertical',
                              command=self._ol_super_tree.yview)
        self._ol_super_tree.configure(yscrollcommand=vsb4.set)
        self._ol_super_tree.grid(row=1, column=0, sticky=tk.NSEW, padx=(4, 0), pady=2)
        vsb4.grid(row=1, column=1, sticky=tk.NS)

        self._ol_super_summary = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._ol_super_summary,
                  foreground='#4ec9b0').grid(row=2, column=0, sticky=tk.EW, padx=4, pady=4)

    # ── Data loading methods ────────────────────────────────────────────────────

    def _ol_load_lineage(self):
        """Load lineage_graph.json and populate the lineage treeview."""
        graph_path = self._SP_VARIANTS_ROOT / 'lineage_graph.json'
        if not graph_path.exists():
            return
        try:
            import json as _jl
            graph = _jl.loads(graph_path.read_text())
        except Exception:
            return

        # Load pattern counts from spawn_log for display
        pc_map = {}
        log_path = self._SP_VARIANTS_ROOT / 'spawn_log.jsonl'
        if log_path.exists():
            try:
                for line in log_path.read_text().splitlines():
                    if line.strip():
                        e = _jl.loads(line)
                        if e.get('name'):
                            pc_map[e['name']] = e.get('pattern_count', 0)
            except Exception:
                pass

        # Clear and repopulate
        for item in self._ol_lineage_tree.get_children():
            self._ol_lineage_tree.delete(item)

        # Group by tier for display order
        tier_order = ['omega', 'alpha', 'mutant', 'fix', 'ancestor']
        by_tier = {t: [] for t in tier_order}
        for name, node in graph.items():
            t = node.get('tier', 'ancestor')
            by_tier.setdefault(t, []).append((name, node))

        for tier in tier_order:
            for name, node in sorted(by_tier.get(tier, []),
                                     key=lambda x: x[1].get('ts') or '', reverse=True):
                pc   = pc_map.get(name, node.get('pattern_count', ''))
                gen  = node.get('generation', '')
                iid  = self._ol_lineage_tree.insert(
                    '', 'end', iid=name, text=name,
                    values=(tier[:6], gen, pc if pc else ''),
                    tags=(tier,),
                )
            col = self._OL_TIER_COL.get(tier, '#cccccc')
            try:
                self._ol_lineage_tree.tag_configure(tier, foreground=col)
            except Exception:
                pass

    def _ol_on_lineage_select(self, event=None):
        """Handle lineage tree selection — load patterns for selected variant."""
        sel = self._ol_lineage_tree.selection()
        if not sel:
            return
        name = sel[0]
        self._ol_active_variant = name
        vals = self._ol_lineage_tree.item(name, 'values')
        tier = vals[0] if vals else ''
        pc   = vals[2] if len(vals) > 2 else ''
        self._ol_info_var.set(f"{name}  |  tier={tier}  |  patterns={pc}")
        threading.Thread(target=self._ol_load_omega_patterns,
                         args=(name,), daemon=True).start()

    def _ol_load_omega_patterns(self, variant: str):
        """Load pattern records for *variant* from patterns_*.json — lazy, capped at 500."""
        import json as _jop
        import glob as _gop

        if variant in self._ol_patterns_cache:
            rows = self._ol_patterns_cache[variant]
            self.parent.after(0, lambda: self._ol_populate_pat_tree(rows))
            return

        pattern_globs = list(self._SP_VARIANTS_ROOT.glob(
            f"patterns*{variant}*.json"))
        if not pattern_globs:
            self.parent.after(0, lambda: self._ol_populate_pat_tree([]))
            return

        rows = []
        seen_types, seen_domains = set(), set()
        try:
            with open(pattern_globs[-1]) as f:
                data = _jop.load(f)
            if isinstance(data, dict):
                items = list(data.values())
            elif isinstance(data, list):
                items = data
            else:
                items = []

            for rec in items[:500]:
                if isinstance(rec, dict):
                    sha    = str(rec.get('context_hash', rec.get('sha', '')))[:8]
                    ptype  = str(rec.get('pattern_type', rec.get('type', '')))
                    domain = str(rec.get('domain', ''))
                    seen   = str(rec.get('first_seen', ''))[:10]
                    count  = str(rec.get('occurrence_count', rec.get('count', '')))
                    rows.append({'sha': sha, 'type': ptype, 'domain': domain,
                                 'seen': seen, 'count': count, '_raw': rec})
                    seen_types.add(ptype)
                    seen_domains.add(domain)
        except Exception:
            pass

        self._ol_patterns_cache[variant] = rows
        self._ol_patterns_all = rows

        type_vals   = ['(all)'] + sorted(seen_types)
        domain_vals = ['(all)'] + sorted(seen_domains)

        def _update():
            self._ol_populate_pat_tree(rows)
            try:
                # Update filter comboboxes
                for w in self._ol_pat_tree.master.winfo_children():
                    pass  # combobox update done via trace below
                self._ol_type_var.set('(all)')
                self._ol_domain_var.set('(all)')
            except Exception:
                pass

        self.parent.after(0, _update)

    def _ol_populate_pat_tree(self, rows):
        """Populate _ol_pat_tree with *rows* (list of dicts)."""
        for item in self._ol_pat_tree.get_children():
            self._ol_pat_tree.delete(item)
        for r in rows[:500]:
            self._ol_pat_tree.insert('', 'end',
                                      values=(r['sha'], r['type'], r['domain'],
                                              r['seen'], r['count']))

    def _ol_filter_patterns(self):
        """Filter _ol_pat_tree rows by type/domain/SHA search."""
        t_filter = self._ol_type_var.get()
        d_filter = self._ol_domain_var.get()
        s_filter = self._ol_sha_var.get().lower()
        filtered = [
            r for r in self._ol_patterns_all
            if (t_filter in ('(all)', '', r['type']))
            and (d_filter in ('(all)', '', r['domain']))
            and (not s_filter or s_filter in r['sha'].lower())
        ]
        self._ol_populate_pat_tree(filtered)

    def _ol_on_pattern_select(self, event=None):
        """Show full JSON record in _ol_pat_detail on row select."""
        sel = self._ol_pat_tree.selection()
        if not sel:
            return
        idx = self._ol_pat_tree.index(sel[0])
        rows = self._ol_patterns_all
        if idx < len(rows):
            import json as _jp
            raw = rows[idx].get('_raw', {})
            text = _jp.dumps(raw, indent=2)
            self._ol_pat_detail.config(state=tk.NORMAL)
            self._ol_pat_detail.delete('1.0', tk.END)
            self._ol_pat_detail.insert('1.0', text)
            self._ol_pat_detail.config(state=tk.DISABLED)

    def _ol_load_alpha_patterns(self, alpha_name: str):
        """Load alpha pattern metadata from build_{alpha_name}*.json."""
        import json as _jal
        rows, grade_label = [], ""
        build_files = list(self._SP_VARIANTS_ROOT.glob(f"build_{alpha_name}*.json"))
        if build_files:
            try:
                data = _jal.loads(build_files[-1].read_text())
                roadmap   = data.get('roadmap', {})
                sig_map   = data.get('signal_map', {})
                sp        = data.get('spawn_profile', {})
                grade_label = f"peak_grade: {sp.get('peak_grade', '?')}"
                for k, v in {**roadmap, **sig_map}.items():
                    rows.append({'sha': str(k)[:8], 'type': str(type(v).__name__),
                                 'domain': alpha_name.replace('specialist_', ''),
                                 'seen': '', 'count': '', '_raw': {k: v}})
            except Exception:
                pass
        self.parent.after(0, lambda: self._ol_populate_alpha_tree(rows, grade_label))

    def _ol_populate_alpha_tree(self, rows, grade_label: str):
        for item in self._ol_alpha_tree.get_children():
            self._ol_alpha_tree.delete(item)
        for r in rows[:500]:
            self._ol_alpha_tree.insert('', 'end',
                                        values=(r['sha'], r['type'], r['domain'],
                                                r['seen'], r['count']))
        self._ol_grade_var.set(grade_label)

    def _ol_on_alpha_pattern_select(self, event=None):
        sel = self._ol_alpha_tree.selection()
        if not sel:
            return
        idx = self._ol_alpha_tree.index(sel[0])
        # Alpha rows are stored separately; use a local cache
        self._ol_alpha_detail.config(state=tk.NORMAL)
        self._ol_alpha_detail.delete('1.0', tk.END)
        self._ol_alpha_detail.insert('1.0', f"Row {idx} selected.")
        self._ol_alpha_detail.config(state=tk.DISABLED)

    def _ol_show_scratch(self):
        """Load scratch_pad.json → bar chart + item treeview."""
        import json as _js
        if not self._SP_SCRATCH_JSON.exists():
            return
        try:
            data = _js.loads(self._SP_SCRATCH_JSON.read_text())
        except Exception:
            return

        # Compute weight sums per domain
        grade_map = {"A": 1.0, "B": 0.75, "C": 0.5, "D": 0.25, "F": 0.0}
        domain_sums = {}
        all_items = []
        for domain, items in data.items():
            if domain.startswith('_'):
                continue
            if isinstance(items, list):
                s = 0.0
                for item in items:
                    w = float(item.get('weight', 0))
                    g = str(item.get('meta', {}).get('grade', item.get('grade', 'D'))).upper()
                    s += w * grade_map.get(g, 0.5)
                    all_items.append((domain, item.get('id', '')[:10],
                                      item.get('type', ''), w,
                                      item.get('ttl', ''), g))
                domain_sums[domain] = s

        # Draw bar chart
        if self._ol_ax is not None and self._ol_canvas is not None:
            try:
                self._ol_ax.clear()
                domains = list(domain_sums.keys())
                sums    = [domain_sums[d] for d in domains]
                colours = ['#4ec9b0'] * len(domains)
                self._ol_ax.barh(domains, sums, color=colours)
                self._ol_ax.set_title('Scratchpad Weight Sums by Domain',
                                       color='#cccccc', fontsize=9)
                self._ol_ax.tick_params(colors='#cccccc', labelsize=8)
                self._ol_ax.spines['bottom'].set_color('#444')
                self._ol_ax.spines['left'].set_color('#444')
                self._ol_ax.set_facecolor('#1a1a2e')
                self._ol_fig.tight_layout(pad=0.5)
                self._ol_canvas.draw()
            except Exception:
                pass

        # Populate item treeview
        for item in self._ol_scratch_tree.get_children():
            self._ol_scratch_tree.delete(item)
        for dom, iid, itype, w, ttl, g in all_items[:300]:
            self._ol_scratch_tree.insert('', 'end', values=(iid, itype,
                                                              f"{w:.3f}", ttl, g))

    def _ol_show_superposition(self, turn_idx: int):
        """Load session_state turn → activated_pids → collapse chain view."""
        import json as _jss
        sess_path = self._SP_VARIANTS_ROOT / 'session_state.json'
        if not sess_path.exists():
            return
        try:
            ss     = _jss.loads(sess_path.read_text())
            turns  = ss.get('turn_history', [])
        except Exception:
            return

        if turn_idx >= len(turns):
            self._ol_super_summary.set(f"Turn {turn_idx} out of range (max {len(turns)-1})")
            return

        turn = turns[turn_idx]
        self._ol_query_var.set(str(turn.get('user', ''))[:120])

        pids    = turn.get('activated_pids', [])
        grade   = turn.get('grade', '?')
        gap     = turn.get('gap', '?')
        domain  = turn.get('domain', '?')

        # Clear and repopulate collapse chain
        for item in self._ol_super_tree.get_children():
            self._ol_super_tree.delete(item)

        # Look up pid details in omega patterns cache if available
        pid_lookup = {}
        if self._ol_active_variant and self._ol_active_variant in self._ol_patterns_cache:
            for row in self._ol_patterns_cache[self._ol_active_variant]:
                raw = row.get('_raw', {})
                pid = str(raw.get('pid', raw.get('id', '')))
                if pid:
                    pid_lookup[pid] = row

        for step, pid in enumerate(pids):
            row   = pid_lookup.get(str(pid), {})
            ptype = row.get('type', '')
            pdom  = row.get('domain', domain)
            w     = row.get('count', '')
            self._ol_super_tree.insert('', 'end',
                                        values=(step, str(pid)[:12], ptype, pdom, w))

        self._ol_super_summary.set(
            f"grade={grade}  |  gap={gap}  |  domain={domain}  "
            f"|  activated_pids={len(pids)}")
        self._ol_turn_spin.config(to=max(0, len(turns) - 1))

    def _ol_refresh(self, event=None):
        """Reload all Ω Lens data when the tab is selected."""
        try:
            tab_text = self.notebook.tab(self.notebook.select(), 'text')
        except Exception:
            return
        if '\u03a9' not in tab_text:
            return
        self._ol_load_lineage()
        self._ol_show_scratch()
        if self._ol_active_variant:
            threading.Thread(target=self._ol_load_omega_patterns,
                             args=(self._ol_active_variant,), daemon=True).start()
