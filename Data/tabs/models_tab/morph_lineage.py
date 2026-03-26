"""
morph_lineage.py — Alpha Lineage Panel for Models Tab
=====================================================
Reads brain_map_*.jsonl files from pymanifest/variants/ and renders an
inline collapsible lineage tree inside the Morph Specialists panel.

Layout:
  ▶ 🧬 Alpha Lineage                          ← Level 1: section toggle
      [ Gen 0: alpha_wide ✓ 0.797 ] →  ...    ← Level 2: gen strip
        [Treeview: alpha grid]                 ← Level 3: per-gen alpha grid
          [Architecture | Domain | Hooks]      ← Level 4: inline detail blocks
"""

import json
import tkinter as tk
from tkinter import ttk
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────

def load_brain_maps(variants_dir: Path) -> dict:
    """
    Load all brain_map_*.jsonl files from variants_dir.
    Returns {"alpha_events": [...], "hook_events": [...], "files": [str, ...]}
    """
    alpha_events = []
    hook_events  = []
    files_loaded = []

    for bmf in sorted(variants_dir.glob("brain_map_*.jsonl"), key=lambda p: p.stat().st_mtime):
        try:
            for line in bmf.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if ev.get("event_type") == "brain_pollination":
                    hook_events.append(ev)
                elif "gen" in ev and "alpha_id" in ev and "blend_avg" in ev:
                    alpha_events.append(ev)
            files_loaded.append(bmf.name)
        except Exception:
            pass

    return {"alpha_events": alpha_events, "hook_events": hook_events, "files": files_loaded}


def build_lineage_tree(data: dict) -> dict:
    """
    Structure alpha_events + hook_events into per-generation groups.
    Returns:
      {
        "gens": {
          0: {"alphas": [alpha_ev, ...], "winner_id": int, "hooks": [hook_ev, ...]},
          1: {...},
          ...
        },
        "n_gens": int,
        "all_gens": [int, ...]
      }
    Deduplicates by (gen, alpha_id) — keeps highest blend_avg.
    """
    # Deduplicate: keep best blend per (gen, alpha_id)
    best: dict = {}
    for ev in data["alpha_events"]:
        key = (int(ev.get("gen", 0)), int(ev.get("alpha_id", 0)))
        prev = best.get(key)
        if prev is None or ev.get("blend_avg", 0) > prev.get("blend_avg", 0):
            best[key] = ev

    # Group by gen
    gens: dict = {}
    for (gen, _), ev in best.items():
        gens.setdefault(gen, {"alphas": [], "winner_id": -1, "hooks": []})
        gens[gen]["alphas"].append(ev)

    # Sort alphas within each gen and find winner
    for gen, gdata in gens.items():
        gdata["alphas"].sort(key=lambda e: e.get("alpha_id", 0))
        survived = [a for a in gdata["alphas"] if a.get("survived", False)]
        if survived:
            winner = max(survived, key=lambda a: a.get("blend_avg", 0))
            gdata["winner_id"] = int(winner.get("alpha_id", -1))

    # Attach hook events to their generation
    for hev in data["hook_events"]:
        gen = int(hev.get("gen", 0))
        if gen in gens:
            gens[gen]["hooks"].append(hev)

    all_gens = sorted(gens.keys())
    return {"gens": gens, "n_gens": len(all_gens), "all_gens": all_gens}


# ─────────────────────────────────────────────────────────────────────────────
# Widget
# ─────────────────────────────────────────────────────────────────────────────

_GRADE_COLORS = {"A": "#4ec9b0", "B": "#569cd6", "C": "#dcdcaa", "D": "#f44747", "F": "#808080"}
_DOMAIN_SHORT  = {
    "Astronomy": "Astr", "Biology": "Biol", "Chemistry": "Chem",
    "Computer Science": "Comp", "Economics": "Econ", "History": "Hist",
    "Literature": "Lite", "Mathematics": "Math", "Philosophy": "Phil",
    "Physics": "Phys",
}
_DOMAINS = list(_DOMAIN_SHORT.keys())


class MorphLineagePanel(ttk.Frame):
    """
    Inline collapsible Alpha Lineage panel.
    Embed inside the Morph Specialists scrollable frame.
    The outer arrow-toggle wrapper is created by the caller (models_tab.py)
    using the standard pattern; this frame is the 'cont' child.
    """

    def __init__(self, parent, variants_dir: Path, style_label="Config.TLabel", **kwargs):
        super().__init__(parent, **kwargs)
        self._vdir   = variants_dir
        self._slabel = style_label
        self._gen_expanded: dict = {}   # gen → bool
        self._gen_frames:   dict = {}   # gen → (cont_frame, arrow_btn)
        self._tree_refs:    dict = {}   # gen → ttk.Treeview
        self._detail_frame: tk.Widget | None = None
        self._build()

    def _build(self):
        data = load_brain_maps(self._vdir)
        if not data["alpha_events"]:
            ttk.Label(self, text="  No brain_map data found.",
                      style=self._slabel).pack(anchor=tk.W, padx=12, pady=4)
            return

        tree = build_lineage_tree(data)
        n_files = len(data["files"])
        n_alpha = len(data["alpha_events"])

        # Summary line
        ttk.Label(
            self,
            text=f"  {n_files} brain_map file(s)  •  {n_alpha} alpha records  •  {tree['n_gens']} generations",
            style=self._slabel,
            font=("Arial", 8),
            foreground="#858585",
        ).pack(anchor=tk.W, padx=12, pady=(2, 4))

        # One collapsible row per generation
        for gen in tree["all_gens"]:
            gdata   = tree["gens"][gen]
            winner  = next((a for a in gdata["alphas"] if a.get("alpha_id") == gdata["winner_id"]), None)
            w_arch  = winner.get("arch", "?").replace("alpha_", "").replace(f"_g{gen}_", "/") if winner else "?"
            w_blend = f"{winner.get('blend_avg', 0):.4f}" if winner else "?"
            n_surv  = sum(1 for a in gdata["alphas"] if a.get("survived", False))

            wrapper = ttk.Frame(self)
            wrapper.pack(fill=tk.X, padx=4, pady=1)

            row = ttk.Frame(wrapper)
            row.pack(fill=tk.X)

            expanded = self._gen_expanded.get(gen, False)
            arrow_btn = ttk.Button(row, text=("▼" if expanded else "▶"), width=2,
                                   command=lambda g=gen: self._toggle_gen(g),
                                   style="Select.TButton")
            arrow_btn.pack(side=tk.LEFT, padx=(0, 4))

            label_txt = f"Gen {gen}:  {w_arch}  ✓ {w_blend}  ({n_surv}/{len(gdata['alphas'])} survived)"
            ttk.Label(row, text=label_txt, style=self._slabel,
                      font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=4)

            cont = ttk.Frame(wrapper)
            self._gen_frames[gen] = (cont, arrow_btn)
            self._build_gen_content(cont, gen, gdata)

            if expanded:
                cont.pack(fill=tk.X, pady=(2, 0))

    def _toggle_gen(self, gen: int):
        if gen not in self._gen_frames:
            return
        cont, arrow_btn = self._gen_frames[gen]
        expanded = self._gen_expanded.get(gen, False)
        if expanded:
            cont.pack_forget()
            arrow_btn.config(text="▶")
        else:
            cont.pack(fill=tk.X, pady=(2, 0))
            arrow_btn.config(text="▼")
        self._gen_expanded[gen] = not expanded

    def _build_gen_content(self, parent: ttk.Frame, gen: int, gdata: dict):
        """Build the alpha Treeview + detail area for one generation."""
        # Treeview for alpha grid
        cols = ("arch", "embd_l", "ffn", "blend") + tuple(_DOMAIN_SHORT.values()) + ("surv",)
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=min(6, len(gdata["alphas"])))

        tv.heading("arch",   text="Architecture")
        tv.heading("embd_l", text="embd×L")
        tv.heading("ffn",    text="FFN")
        tv.heading("blend",  text="blend")
        for dlong, dshort in _DOMAIN_SHORT.items():
            tv.heading(dshort, text=dshort)
        tv.heading("surv", text="✓")

        tv.column("arch",   width=160, stretch=False)
        tv.column("embd_l", width=60,  stretch=False)
        tv.column("ffn",    width=55,  stretch=False)
        tv.column("blend",  width=55,  stretch=False)
        for dshort in _DOMAIN_SHORT.values():
            tv.column(dshort, width=32, stretch=False)
        tv.column("surv", width=22, stretch=False)

        # Grade colour tags
        for letter, color in _GRADE_COLORS.items():
            tv.tag_configure(f"grade_{letter}", foreground=color)
        tv.tag_configure("winner", font=("Arial", 9, "bold"))
        tv.tag_configure("dead",   foreground="#555555")

        # Insert rows
        for alpha in gdata["alphas"]:
            aid    = int(alpha.get("alpha_id", 0))
            arch   = alpha.get("arch", "?")
            embd   = alpha.get("embd", 0)
            nl     = alpha.get("n_layers", 0)
            ffn    = alpha.get("ffn", 0)
            blend  = alpha.get("blend_avg", 0)
            grades = alpha.get("grades", {})
            surv   = "✓" if alpha.get("survived") else "✗"

            grade_vals = [grades.get(d, "?") for d in _DOMAINS]
            row_vals   = (arch, f"{embd}×{nl}", str(ffn), f"{blend:.4f}") + tuple(grade_vals) + (surv,)

            # Pick tag: winner > survived > dead
            if aid == gdata["winner_id"]:
                tag = ("winner",)
            elif alpha.get("survived"):
                tag = ()
            else:
                tag = ("dead",)

            tv.insert("", tk.END, iid=f"g{gen}_a{aid}", values=row_vals, tags=tag)

        tv.pack(fill=tk.X, padx=12, pady=(4, 2))
        self._tree_refs[gen] = tv

        # Detail area (shown on row click)
        detail_wrapper = ttk.Frame(parent)
        detail_wrapper.pack(fill=tk.X, padx=12, pady=(0, 4))

        def _on_select(event, g=gen, gd=gdata, dw=detail_wrapper):
            sel = tv.selection()
            if not sel:
                return
            iid = sel[0]
            # parse alpha_id from iid "gG_aA"
            try:
                aid = int(iid.split("_a")[1])
            except Exception:
                return
            alpha = next((a for a in gd["alphas"] if int(a.get("alpha_id", -1)) == aid), None)
            if alpha:
                self._show_alpha_detail(dw, alpha, gd["hooks"])

        tv.bind("<<TreeviewSelect>>", _on_select)

    def _show_alpha_detail(self, parent: ttk.Frame, alpha: dict, hooks: list):
        """Render 3 inline LabelFrame blocks for the selected alpha."""
        for w in parent.winfo_children():
            w.destroy()

        arch = alpha.get("arch", "?")

        # ── Block 1: Architecture ──────────────────────────────────────────
        arch_frame = ttk.LabelFrame(parent, text="Architecture", padding=4)
        arch_frame.pack(fill=tk.X, pady=(4, 2))

        fields = [
            ("arch",        arch),
            ("embd",        alpha.get("embd", "?")),
            ("n_layers",    alpha.get("n_layers", "?")),
            ("ffn",         alpha.get("ffn", "?")),
            ("n_heads",     alpha.get("n_heads", alpha.get("arch", "?"))),
            ("size_mb_est", f"{alpha.get('size_mb_est', 0):.1f} MB"),
            ("blend_avg",   f"{alpha.get('blend_avg', 0):.4f}"),
            ("survived",    str(alpha.get("survived", False))),
        ]
        # n_heads may not be stored; fall back from arch name if needed
        n_heads = "?"
        ffn_val = alpha.get("ffn", 0)
        embd    = alpha.get("embd", 0)
        for fname, fval in fields:
            row = ttk.Frame(arch_frame)
            row.pack(fill=tk.X, pady=1)
            ttk.Label(row, text=f"{fname}:", width=12, anchor=tk.E,
                      style=self._slabel, font=("Arial", 8)).pack(side=tk.LEFT)
            ttk.Label(row, text=str(fval), style=self._slabel,
                      font=("Arial", 8, "bold")).pack(side=tk.LEFT, padx=4)

        # ── Block 2: Domain Scores ─────────────────────────────────────────
        dom_frame = ttk.LabelFrame(parent, text="Domain Scores", padding=4)
        dom_frame.pack(fill=tk.X, pady=2)

        detail = alpha.get("survival_detail", {}).get("domains", {})
        grades = alpha.get("grades", {})

        hdr = ttk.Frame(dom_frame)
        hdr.pack(fill=tk.X)
        for col, w in [("Domain", 120), ("Grade", 40), ("Alpha", 60), ("Cousin", 60), ("Gap", 60), ("Pass", 40)]:
            ttk.Label(hdr, text=col, width=w // 8, style=self._slabel,
                      font=("Arial", 8, "bold")).pack(side=tk.LEFT, padx=2)

        for dname in _DOMAINS:
            ddata = detail.get(dname, {})
            grade = grades.get(dname, "?")
            color = _GRADE_COLORS.get(grade, "#cccccc")

            drow = ttk.Frame(dom_frame)
            drow.pack(fill=tk.X, pady=1)
            ttk.Label(drow, text=dname[:14], width=15, style=self._slabel,
                      font=("Arial", 8)).pack(side=tk.LEFT, padx=2)
            ttk.Label(drow, text=grade, width=4, style=self._slabel,
                      font=("Arial", 8, "bold"), foreground=color).pack(side=tk.LEFT)
            ttk.Label(drow, text=f"{ddata.get('alpha', 0):.4f}", width=7,
                      style=self._slabel, font=("Arial", 8)).pack(side=tk.LEFT)
            ttk.Label(drow, text=f"{ddata.get('cousin', 0):.4f}", width=7,
                      style=self._slabel, font=("Arial", 8),
                      foreground="#858585").pack(side=tk.LEFT)
            ttk.Label(drow, text=f"{ddata.get('gap', 0):.4f}", width=7,
                      style=self._slabel, font=("Arial", 8)).pack(side=tk.LEFT)
            passed = "✓" if ddata.get("passed", False) else "✗"
            ttk.Label(drow, text=passed, style=self._slabel,
                      font=("Arial", 8),
                      foreground="#4ec9b0" if ddata.get("passed") else "#f44747").pack(side=tk.LEFT)

        # ── Block 3: Hooks → Mutations ─────────────────────────────────────
        hooks_targeting = [h for h in hooks
                           if h.get("hook", {}).get("to_alpha") == arch]

        if hooks_targeting:
            hook_frame = ttk.LabelFrame(parent, text="Hooks → Mutations", padding=4)
            hook_frame.pack(fill=tk.X, pady=2)

            for hev in hooks_targeting:
                hdata = hev.get("hook", {})
                from_arch = hdata.get("from_alpha", "?")
                obs       = hdata.get("observations", [])
                mut_hint  = hdata.get("mutation_hint", {})
                best_dom  = hdata.get("best_domain", "?")
                arch_diff = hdata.get("arch_diff", {})

                hrow = ttk.Frame(hook_frame)
                hrow.pack(fill=tk.X, pady=(4, 0))
                ttk.Label(hrow, text=f"← {from_arch}  (best: {best_dom})",
                          style=self._slabel, font=("Arial", 8, "italic"),
                          foreground="#9cdcfe").pack(anchor=tk.W)

                if arch_diff:
                    diff_parts = []
                    for k, v in arch_diff.items():
                        diff_parts.append(f"{k}: {v.get('winner','?')}→{v.get('loser','?')}")
                    ttk.Label(hrow, text="  arch diff: " + ", ".join(diff_parts),
                              style=self._slabel, font=("Arial", 8),
                              foreground="#858585").pack(anchor=tk.W)

                for ob in obs:
                    ttk.Label(hrow, text=f"  • {ob}", style=self._slabel,
                              font=("Arial", 8)).pack(anchor=tk.W)

                if mut_hint:
                    hint_txt = ", ".join(f"{k}={v}" for k, v in mut_hint.items())
                    ttk.Label(hrow, text=f"  ↳ hint: {hint_txt}",
                              style=self._slabel, font=("Arial", 8, "italic"),
                              foreground="#dcdcaa").pack(anchor=tk.W)

    def populate_overview_frame(self, target_frame: tk.Widget,
                                 alpha_event: dict = None) -> None:
        """
        Public method: render alpha lineage overview into an arbitrary frame
        (e.g., the LEFT models_tab Overview sub-tab).

        If alpha_event is given, highlights that specific alpha in the tree.
        If None, shows the latest generation's winner summary.
        """
        # Clear target
        for w in target_frame.winfo_children():
            w.destroy()

        data = load_brain_maps(self._vdir)
        tree = build_lineage_tree(data)
        alpha_events = data.get("alpha_events", [])
        hook_events  = data.get("hook_events", [])

        if not alpha_events:
            ttk.Label(target_frame, text="No brain_map data available.",
                      style=self._slabel, foreground="#858585").pack(padx=10, pady=10)
            return

        # Pick the target alpha: given event or latest gen winner
        if alpha_event is not None:
            target = alpha_event
        else:
            all_gens = tree.get("all_gens", [])
            if all_gens:
                gd = tree.get("gens", {}).get(max(all_gens), {})
                target = gd.get("winner") or (gd.get("alphas") or [None])[0]
            else:
                target = alpha_events[-1] if alpha_events else None

        if target is None:
            ttk.Label(target_frame, text="No alpha data to display.",
                      style=self._slabel, foreground="#858585").pack(padx=10, pady=10)
            return

        # Render the standard detail blocks into target_frame
        hooks_for_target = [h for h in hook_events
                             if h.get("hook", {}).get("to_alpha") == target.get("arch")]
        self._show_alpha_detail(target_frame, target, hooks_for_target)
