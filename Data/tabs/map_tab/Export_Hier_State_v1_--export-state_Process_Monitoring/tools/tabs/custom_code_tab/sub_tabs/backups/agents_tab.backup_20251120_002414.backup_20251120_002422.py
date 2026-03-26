"""
Agents Tab (Phase 1.5F)

Stylish agent configuration panel with:
- Agent type catalog display
- Per-agent variant selection
- Temperature configuration
- Conformer priority settings
- Tools enable/disable
- Crew builder (multi-agent workflows)

Visual Design:
- Card-based layout with type colors
- Class-level border glow
- Icon badges
- Collapsible config sections
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
from logger_util import get_tab_logger

log_message, log_error, log_exception = get_tab_logger('custom_code')
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from agent_server_manager import get_agent_server_manager


class AgentsTab(ttk.Frame):
    """
    Main agents configuration panel.

    Layout:
    - Left: Agent catalog (scrollable card grid)
    - Right: Selected agent configuration panel
    """

    ROUTE_OPTIONS = ["panel", "main", "both"]
    CHAT_ROUTE_DISPLAY = {
        "panel": "Panel Popups",
        "main": "Main Chat",
        "both": "Main + Panel",
    }
    TOOL_ROUTE_DISPLAY = {
        "panel": "Panel Tools",
        "main": "Main Chat Tools",
        "both": "Mirror Tools",
    }
    CHAT_ROUTE_BUTTON = {
        "panel": "Chat → Panel",
        "main": "Chat → Main",
        "both": "Chat → Both",
    }
    TOOL_ROUTE_BUTTON = {
        "panel": "Tools → Panel",
        "main": "Tools → Main",
        "both": "Tools → Both",
    }

    def __init__(self, parent, root, style, parent_tab=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.root = root
        self.style = style
        self.parent_tab = parent_tab

        # Load catalogs
        self.type_catalog = self._load_type_catalog()
        self.class_colors = self._load_class_colors()
        self.agent_configs = {}  # {agent_id: config_dict}
        self.selected_agent = None

        # Agent server manager for dedicated llama.cpp instances
        self.agent_server_manager = get_agent_server_manager()

        # Per-card UI bookkeeping
        self._route_buttons = {'chat': {}, 'tool': {}}
        self._routing_vars = {'chat': {}, 'tool': {}}

        # Preload any existing roster/defaults so UI reflects saved state on launch
        try:
            self._preload_agents_defaults()
        except Exception:
            pass
        try:
            self._notify_roster_changed()
        except Exception:
            pass

        self._create_ui()

    def _load_type_catalog(self) -> Dict:
        """Load type catalog v2"""
        try:
            # Path: sub_tabs -> custom_code_tab -> tabs -> Data -> type_catalog_v2.json
            catalog_path = Path(__file__).parent.parent.parent.parent / "type_catalog_v2.json"
            with open(catalog_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            log_message(f"AGENTS_TAB: Error loading type catalog: {e}")
            return {"types": [], "agent_types": {"types": []}}

    def _load_class_colors(self) -> Dict:
        """Load class color scheme"""
        try:
            # Path: sub_tabs -> custom_code_tab -> tabs -> Data -> class_colors.json
            colors_path = Path(__file__).parent.parent.parent.parent / "class_colors.json"
            with open(colors_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            log_message(f"AGENTS_TAB: Error loading class colors: {e}")
            return {"type_colors": {}, "class_colors": {}}

    def _load_schema_prompt_defaults(self) -> Dict:
        """Load schema/prompt defaults for type/class combinations"""
        try:
            defaults_path = Path(__file__).parent.parent.parent.parent / "schema_prompt_defaults.json"
            with open(defaults_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            log_message(f"AGENTS_TAB: Error loading schema/prompt defaults: {e}")
            return {}

    def _get_schema_prompt_defaults(self, agent_type: str, class_level: str) -> Dict:
        """Get default prompt and schema for a given type/class combination"""
        try:
            defaults = self._load_schema_prompt_defaults()

            # Look up type-specific defaults
            if agent_type in defaults:
                type_defaults = defaults[agent_type]
                if class_level in type_defaults:
                    return type_defaults[class_level]

            # Fallback to _fallback section
            if "_fallback" in defaults and class_level in defaults["_fallback"]:
                log_message(f"AGENTS_TAB: Using fallback defaults for {agent_type}/{class_level}")
                return defaults["_fallback"][class_level]

            # Ultimate fallback
            return {
                "system_prompt": "default",
                "tool_schema": "read-only",
                "description": "Safe defaults"
            }
        except Exception as e:
            log_message(f"AGENTS_TAB: Error getting defaults for {agent_type}/{class_level}: {e}")
            return {"system_prompt": "default", "tool_schema": "read-only"}

    def _generate_prompt_from_type(self, agent_type: str, class_level: str) -> str:
        """Generate system prompt from type definition"""
        try:
            # Load type definition
            type_catalog_dir = Path(__file__).parent.parent.parent.parent / "type_catalog"
            type_file = type_catalog_dir / f"{agent_type}_type.json"

            if not type_file.exists():
                log_message(f"AGENTS_TAB: Type file not found: {type_file}")
                return f"You are a {class_level} {agent_type} agent."

            with open(type_file, 'r') as f:
                type_data = json.load(f)

            # Navigate to the actual type definition (skip _meta)
            type_key = None
            for key in type_data.keys():
                if not key.startswith('_'):
                    type_key = key
                    break

            if not type_key:
                return f"You are a {class_level} {agent_type} agent."

            type_def = type_data[type_key]

            # Extract system prompt template
            prompt_template = type_def.get('system_prompt_template', {})
            base_prompt = prompt_template.get('base', '')
            class_additions = prompt_template.get('class_specific_additions', {})

            # Build final prompt
            if base_prompt:
                final_prompt = base_prompt
                if class_level in class_additions:
                    final_prompt += f"\n\n{class_additions[class_level]}"
                return final_prompt
            else:
                # Fallback: use semantic identity and capabilities
                semantic = type_def.get('semantic_identity', {})
                role = semantic.get('role', f'{class_level.title()} {agent_type.title()}')
                principle = semantic.get('core_principle', '')

                classes = type_def.get('classes', {})
                capabilities = []
                if class_level in classes:
                    capabilities = classes[class_level].get('capabilities', [])

                prompt = f"You are a {role}.\n"
                if principle:
                    prompt += f"\nCore Principle: {principle}\n"
                if capabilities:
                    prompt += "\nCapabilities:\n"
                    for cap in capabilities:
                        prompt += f"- {cap}\n"

                return prompt
        except Exception as e:
            log_message(f"AGENTS_TAB: Error generating prompt for {agent_type}/{class_level}: {e}")
            return f"You are a {class_level} {agent_type} agent."

    def _ensure_prompt_exists(self, prompt_name: str, agent_type: str, class_level: str):
        """Ensure system prompt file exists, generate if missing"""
        try:
            prompts_dir = Path(__file__).parent.parent / "system_prompts"
            prompts_dir.mkdir(parents=True, exist_ok=True)

            prompt_file = prompts_dir / f"{prompt_name}.txt"

            if not prompt_file.exists():
                log_message(f"AGENTS_TAB: Generating missing prompt: {prompt_name}")
                prompt_content = self._generate_prompt_from_type(agent_type, class_level)
                prompt_file.write_text(prompt_content)
                log_message(f"AGENTS_TAB: Created prompt file: {prompt_file}")
        except Exception as e:
            log_message(f"AGENTS_TAB: Error ensuring prompt exists: {e}")

    def _create_ui(self):
        """Create main UI layout"""
        self.columnconfigure(0, weight=2)
        self.columnconfigure(1, weight=3)
        self.rowconfigure(0, weight=1)

        # Left panel: Agent catalog with MoE indicator
        catalog_frame = ttk.Frame(self)
        catalog_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=(10, 5), pady=10)
        catalog_frame.columnconfigure(0, weight=1)
        catalog_frame.rowconfigure(1, weight=1)

        # Header with MoE indicator
        catalog_header = ttk.Frame(catalog_frame, style='Category.TFrame')
        catalog_header.grid(row=0, column=0, sticky=tk.EW, pady=(0, 5))
        ttk.Label(catalog_header, text="🤖 Agent Catalog", font=("Arial", 10, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT)
        self._moe_indicator_label = ttk.Label(catalog_header, text="", style='Config.TLabel')
        self._moe_indicator_label.pack(side=tk.RIGHT, padx=(10, 0))
        self._update_moe_indicator()

        # Catalog content frame
        catalog_content = ttk.LabelFrame(catalog_frame, text="", padding=10)
        catalog_content.grid(row=1, column=0, sticky=tk.NSEW)
        catalog_content.columnconfigure(0, weight=1)
        catalog_content.rowconfigure(0, weight=1)

        # Scrollable canvas for agent cards
        canvas = tk.Canvas(catalog_content, bg='#2d2d2d', highlightthickness=0)
        scrollbar = ttk.Scrollbar(catalog_content, orient=tk.VERTICAL, command=canvas.yview)
        self.catalog_inner = ttk.Frame(canvas, style='Category.TFrame')

        self.catalog_inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.catalog_inner, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.grid(row=0, column=0, sticky=tk.NSEW)
        scrollbar.grid(row=0, column=1, sticky=tk.NS)

        # Right panel: Agent configuration
        config_frame = ttk.LabelFrame(self, text="⚙️ Agent Configuration", padding=10)
        config_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=(5, 10), pady=10)
        config_frame.columnconfigure(0, weight=1)
        config_frame.rowconfigure(0, weight=1)

        # Config scroll container
        config_canvas = tk.Canvas(config_frame, bg='#2d2d2d', highlightthickness=0)
        config_scrollbar = ttk.Scrollbar(config_frame, orient=tk.VERTICAL, command=config_canvas.yview)
        self.config_inner = ttk.Frame(config_canvas, style='Category.TFrame')

        self.config_inner.bind(
            "<Configure>",
            lambda e: config_canvas.configure(scrollregion=config_canvas.bbox("all"))
        )

        config_canvas.create_window((0, 0), window=self.config_inner, anchor=tk.NW)
        config_canvas.configure(yscrollcommand=config_scrollbar.set)

        config_canvas.grid(row=0, column=0, sticky=tk.NSEW)
        config_scrollbar.grid(row=0, column=1, sticky=tk.NS)

        # Populate catalog
        self._populate_catalog()

        # Show placeholder in config panel
        self._show_config_placeholder()

    # --- Defaults/Roster preload ---------------------------------------------
    def _preload_agents_defaults(self):
        """Populate self.agent_configs from (in order): active roster → project defaults → global defaults.
        Ensures dropdowns show saved variants on relaunch.
        """
        import json
        from pathlib import Path
        roster = []
        # 1) Active roster from host (already applied at app startup)
        try:
            if hasattr(self.root, 'get_active_agents') and callable(getattr(self.root, 'get_active_agents')):
                roster = self.root.get_active_agents() or []
        except Exception:
            roster = []
        # 2) Project default, if no active roster
        if not roster:
            try:
                proj = None
                if hasattr(self.root, 'settings_tab') and getattr(self.root.settings_tab, 'current_project_context', None):
                    proj = self.root.settings_tab.current_project_context
                if proj:
                    p = Path('Data')/'projects'/proj/'agents_default.json'
                    if p.exists():
                        roster = json.loads(p.read_text()) or []
            except Exception:
                pass
        # 3) Global default
        if not roster:
            try:
                g = Path('Data')/'user_prefs'/'agents_default.json'
                if g.exists():
                    roster = json.loads(g.read_text()) or []
            except Exception:
                pass

        if not roster:
            return
        # Normalize and map into agent_configs for UI
        try:
            for rec in roster:
                aid = rec.get('name')
                if not aid:
                    continue
                cfg = self.agent_configs.setdefault(aid, {
                    "variant": None,
                    "temperature": 0.7,
                    "conformer_priority": "auto",
                    "enabled_tools": {},
                    "max_tokens": 2048,
                    "enabled": True,
                    "backend": None,
                    "hardware": None,
                    "n_gpu_layers": None,
                    "cpu_threads": None,
                    "rag_level": 0,
                })
                # Fill from record
                for k in ("variant","gguf_override","ollama_tag","enabled_tools","backend","hardware","n_gpu_layers","cpu_threads"):
                    v = rec.get(k)
                    if v is not None and v != "":
                        # store 'ollama_tag' as 'ollama_tag_override' for UI consistency
                        if k == 'ollama_tag':
                            cfg['ollama_tag_override'] = v
                        else:
                            cfg[k] = v
                cfg['enabled'] = bool(rec.get('active', True))
                try:
                    cfg['rag_level'] = int(rec.get('rag_level', cfg.get('rag_level', 0)) or 0)
                except Exception:
                    cfg['rag_level'] = cfg.get('rag_level', 0)
                cfg['chat_route'] = rec.get('chat_route', cfg.get('chat_route', 'main') or 'main')
                cfg['tool_route'] = rec.get('tool_route', cfg.get('tool_route', 'main') or 'main')
        except Exception:
            pass

    def _populate_catalog(self):
        """Populate agent catalog with cards"""
        agent_types = self.type_catalog.get("agent_types", {}).get("types", [])

        if not agent_types:
            ttk.Label(
                self.catalog_inner,
                text="No agent types available",
                foreground="#888888"
            ).pack(pady=20)
            return

        # Create grid of agent cards (2 columns)
        for i, agent_type in enumerate(agent_types):
            row = i // 2
            col = i % 2

            card = self._create_agent_card(agent_type)
            card.grid(row=row, column=col, padx=5, pady=5, sticky=tk.EW)

        # Configure grid weights
        self.catalog_inner.columnconfigure(0, weight=1)
        self.catalog_inner.columnconfigure(1, weight=1)

    def _create_agent_card(self, agent_type: Dict) -> ttk.Frame:
        """Create a stylish card for an agent type"""
        agent_id = agent_type["id"]
        display_name = agent_type["display_name"]
        base_type = agent_type["base_type"]
        role = agent_type["role"]

        # Get type color
        type_colors = self.class_colors.get("type_colors", {})
        type_color_info = type_colors.get(base_type, {})
        type_color = type_color_info.get("primary", "#888888")
        type_icon = type_color_info.get("icon", "🤖")

        # Card frame with border
        card = tk.Frame(
            self.catalog_inner,
            bg='#3d3d3d',
            highlightthickness=2,
            highlightbackground=type_color,
            relief=tk.FLAT,
            cursor='hand2'
        )
        card.bind("<Button-1>", lambda e, aid=agent_id: self._on_agent_selected(aid))

        # Inner padding
        inner = tk.Frame(card, bg='#3d3d3d')
        inner.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Header with icon and name
        header = tk.Frame(inner, bg='#3d3d3d')
        header.pack(fill=tk.X, pady=(0, 5))

        icon_label = tk.Label(
            header,
            text=type_icon,
            font=("Arial", 20),
            bg='#3d3d3d',
            fg='#ffffff'
        )
        icon_label.pack(side=tk.LEFT, padx=(0, 5))
        icon_label.bind("<Button-1>", lambda e, aid=agent_id: self._on_agent_selected(aid))

        name_label = tk.Label(
            header,
            text=display_name,
            font=("Arial", 11, "bold"),
            bg='#3d3d3d',
            fg=type_color
        )
        name_label.pack(side=tk.LEFT)
        name_label.bind("<Button-1>", lambda e, aid=agent_id: self._on_agent_selected(aid))

        # Role description
        role_label = tk.Label(
            inner,
            text=role,
            font=("Arial", 9),
            bg='#3d3d3d',
            fg='#cccccc',
            wraplength=150,
            justify=tk.LEFT
        )
        role_label.pack(fill=tk.X, pady=(0, 5))
        role_label.bind("<Button-1>", lambda e, aid=agent_id: self._on_agent_selected(aid))

        # Type badge
        badge_label = tk.Label(
            inner,
            text=f"Type: {base_type}",
            font=("Arial", 8),
            bg='#2d2d2d',
            fg=type_color,
            padx=5,
            pady=2
        )
        badge_label.pack(anchor=tk.W)
        badge_label.bind("<Button-1>", lambda e, aid=agent_id: self._on_agent_selected(aid))

        # Hover effect
        def on_enter(e):
            card.config(highlightbackground='#ffffff')

        def on_leave(e):
            card.config(highlightbackground=type_color)

        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)

        return card

    def _on_agent_selected(self, agent_id: str):
        """Handle agent selection"""
        self.selected_agent = agent_id
        log_message(f"AGENTS_TAB: Selected agent {agent_id}")
        self._show_agent_config(agent_id)

    def _show_config_placeholder(self):
        """Show placeholder when no agent selected"""
        for widget in self.config_inner.winfo_children():
            widget.destroy()

        ttk.Label(
            self.config_inner,
            text="← Select an agent type to configure",
            font=("Arial", 11),
            foreground="#888888"
        ).pack(expand=True)

    def _ensure_agent_config(self, agent_id: str) -> Dict:
        """Ensure an agent config record exists with baseline defaults."""
        cfg = self.agent_configs.get(agent_id)
        if cfg is None:
            cfg = {
                "variant": None,
                "temperature": 0.7,
                "conformer_priority": "auto",
                "enabled_tools": {},
                "max_tokens": 2048,
                "enabled": True,
                "backend": None,
                "hardware": None,
                "n_gpu_layers": None,
                "cpu_threads": None,
                "gguf_override": None,
                "ollama_tag_override": None,
                "rag_level": 0,
                "chat_route": "main",
                "tool_route": "main",
            }
            self.agent_configs[agent_id] = cfg
        cfg.setdefault("assigned_type", self.get_agent_base_type(agent_id) or "general")
        # Ensure newer keys exist on older persisted configs
        cfg.setdefault("enabled_tools", {})
        cfg.setdefault("backend", None)
        cfg.setdefault("hardware", None)
        cfg.setdefault("n_gpu_layers", None)
        cfg.setdefault("cpu_threads", None)
        cfg.setdefault("gguf_override", None)
        cfg.setdefault("ollama_tag_override", None)
        cfg.setdefault("rag_level", 0)
        cfg.setdefault("chat_route", "main")
        cfg.setdefault("tool_route", "main")
        return cfg

    def get_agent_base_type(self, agent_id: str) -> str:
        """Return the base type (coder/debugger/etc.) for an agent id."""
        try:
            agent_types = self.type_catalog.get("agent_types", {}).get("types", [])
            entry = next((a for a in agent_types if a.get("id") == agent_id), None)
            if entry:
                base_type = entry.get("base_type") or entry.get("id")
                if base_type:
                    return base_type.strip().lower()
        except Exception:
            pass
        return "general"

    def _route_display_label(self, route_type: str, value: str) -> str:
        if route_type == "chat":
            return self.CHAT_ROUTE_DISPLAY.get(value, self.CHAT_ROUTE_DISPLAY["panel"])
        return self.TOOL_ROUTE_DISPLAY.get(value, self.TOOL_ROUTE_DISPLAY["panel"])

    def _route_button_label(self, route_type: str, value: str) -> str:
        if route_type == "chat":
            return self.CHAT_ROUTE_BUTTON.get(value, self.CHAT_ROUTE_BUTTON["panel"])
        return self.TOOL_ROUTE_BUTTON.get(value, self.TOOL_ROUTE_BUTTON["panel"])

    def _cycle_route(self, agent_id: str, field: str):
        cfg = self._ensure_agent_config(agent_id)
        current = cfg.get(field, "panel")
        try:
            idx = self.ROUTE_OPTIONS.index(current)
        except ValueError:
            idx = 0
        new_value = self.ROUTE_OPTIONS[(idx + 1) % len(self.ROUTE_OPTIONS)]
        cfg[field] = new_value
        self._refresh_route_buttons(agent_id)
        self._update_routing_control(agent_id, field, new_value)
        try:
            self._notify_roster_changed()
        except Exception:
            pass
        if self.parent_tab and hasattr(self.parent_tab, '_refresh_agent_dock'):
            try:
                self.parent_tab._refresh_agent_dock()
            except Exception:
                pass

    def _refresh_route_buttons(self, agent_id: str):
        cfg = self.agent_configs.get(agent_id) or {}
        chat_btn = self._route_buttons['chat'].get(agent_id)
        if chat_btn:
            chat_btn.config(text=self._route_button_label("chat", cfg.get("chat_route", "panel")))
        tool_btn = self._route_buttons['tool'].get(agent_id)
        if tool_btn:
            tool_btn.config(text=self._route_button_label("tool", cfg.get("tool_route", "panel")))

    def _update_routing_control(self, agent_id: str, field: str, value: str):
        route_type = "chat" if field == "chat_route" else "tool"
        display_label = self._route_display_label(route_type, value)
        storage = self._routing_vars.get(route_type, {})
        var = storage.get(agent_id)
        if var:
            var.set(display_label)

    def _set_route_from_display(self, agent_id: str, field: str, display: str):
        route_type = "chat" if field == "chat_route" else "tool"
        mapping = self.CHAT_ROUTE_DISPLAY if route_type == "chat" else self.TOOL_ROUTE_DISPLAY
        for code, label in mapping.items():
            if label == display:
                cfg = self._ensure_agent_config(agent_id)
                if cfg.get(field) != code:
                    cfg[field] = code
                    self._refresh_route_buttons(agent_id)
                    try:
                        self._notify_roster_changed()
                    except Exception:
                        pass
                    if self.parent_tab and hasattr(self.parent_tab, '_refresh_agent_dock'):
                        try:
                            self.parent_tab._refresh_agent_dock()
                        except Exception:
                            pass
                return

    def _mount_agent_from_card(self, agent_id: str):
        cfg = self._ensure_agent_config(agent_id)
        cfg['enabled'] = True
        try:
            if not (cfg.get('variant') or cfg.get('gguf_override') or cfg.get('ollama_tag_override')):
                messagebox.showinfo("Mount Agent", f"Select a variant or override for '{agent_id}' before mounting.")
                return
        except Exception:
            pass
        try:
            self._notify_roster_changed()
        except Exception as exc:
            log_message(f"AGENTS_TAB: Failed to apply roster before mount for {agent_id}: {exc}")
        try:
            if hasattr(self.parent_tab, 'sub_notebook') and hasattr(self.parent_tab, 'chat_tab_frame'):
                self.parent_tab.sub_notebook.select(self.parent_tab.chat_tab_frame)
        except Exception:
            pass
        try:
            chat = getattr(self.parent_tab, 'chat_interface', None)
            mounted = False
            if chat and hasattr(chat, 'mount_agent'):
                mounted = chat.mount_agent(agent_id, user_initiated=True)
            elif chat and hasattr(chat, '_mount_agents_all'):
                chat._mount_agents_all(user_initiated=True, target_names=[agent_id])
                mounted = True
            if mounted and hasattr(chat, 'add_message'):
                chat.add_message('system', f"[Agents] Mounted {agent_id} via Agents panel")
            if mounted and self.parent_tab and hasattr(self.parent_tab, '_refresh_agent_dock'):
                try:
                    self.parent_tab._refresh_agent_dock()
                except Exception:
                    pass
        except Exception as exc:
            log_message(f"AGENTS_TAB: Mount request failed for {agent_id}: {exc}")

    def _inherit_tools_from_profile(self, agent_id: str, profile_name: str = "Default"):
        cfg = self._ensure_agent_config(agent_id)
        try:
            import sys
            from pathlib import Path
            cfg_path = Path(__file__).parent.parent.parent.parent
            if str(cfg_path) not in sys.path:
                sys.path.insert(0, str(cfg_path))
            import config as C
            profile = C.get_unified_tool_profile(profile_name) or {}
            enabled = dict((profile.get('tools') or {}).get('enabled_tools', {}))
            cfg['enabled_tools'] = {k: bool(v) for k, v in enabled.items()}
        except Exception as exc:
            log_message(f"AGENTS_TAB: Failed to inherit tools from profile '{profile_name}' for {agent_id}: {exc}")

    def _open_agent_tools_popup(self, agent_id: str):
        cfg = self._ensure_agent_config(agent_id)
        popup = tk.Toplevel(self)
        popup.title(f"{agent_id} Tools")
        popup.geometry("420x420")
        popup.transient(self.winfo_toplevel())
        try:
            popup.grab_set()
        except Exception:
            pass

        container = ttk.Frame(popup, padding=10)
        container.pack(fill=tk.BOTH, expand=True)

        checklist_frame = ttk.LabelFrame(container, text="Allowed Tools", padding=8)
        checklist_frame.pack(fill=tk.BOTH, expand=True)

        list_container = ttk.Frame(checklist_frame)
        list_container.pack(fill=tk.BOTH, expand=True)

        tool_canvas = tk.Canvas(list_container, bg='#2d2d2d', highlightthickness=0)
        tool_scroll = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=tool_canvas.yview)
        tool_inner = ttk.Frame(tool_canvas, style='Category.TFrame')

        tool_inner.bind(
            "<Configure>",
            lambda e: tool_canvas.configure(scrollregion=tool_canvas.bbox("all"))
        )

        tool_canvas.create_window((0, 0), window=tool_inner, anchor="nw")
        tool_canvas.configure(yscrollcommand=tool_scroll.set)

        tool_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tool_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._build_tools_checklist(tool_inner, agent_id)

        footer = ttk.Frame(container)
        footer.pack(fill=tk.X, pady=(12, 0))

        def _apply_defaults():
            variant = cfg.get('variant')
            if variant:
                self._apply_agent_variant_defaults(agent_id, variant)
                self._build_tools_checklist(tool_inner, agent_id)
            else:
                messagebox.showinfo("Variant Required", "Select a variant before applying type defaults.")

        def _inherit():
            self._inherit_tools_from_profile(agent_id)
            self._build_tools_checklist(tool_inner, agent_id)

        def _close():
            try:
                self._notify_roster_changed()
            except Exception:
                pass
            if self.parent_tab and hasattr(self.parent_tab, '_refresh_agent_dock'):
                try:
                    self.parent_tab._refresh_agent_dock()
                except Exception:
                    pass
            popup.destroy()

        ttk.Button(footer, text="Apply Type Defaults", style='Select.TButton', command=_apply_defaults).pack(side=tk.LEFT, padx=4)
        ttk.Button(footer, text="Inherit Global Profile", style='Select.TButton', command=_inherit).pack(side=tk.LEFT, padx=4)
        ttk.Button(footer, text="Close", style='Select.TButton', command=_close).pack(side=tk.RIGHT)

        popup.protocol("WM_DELETE_WINDOW", _close)

    def _show_agent_config(self, agent_id: str):
        """Show configuration panel for selected agent"""
        # Clear existing config
        for widget in self.config_inner.winfo_children():
            widget.destroy()

        # Find agent type
        agent_types = self.type_catalog.get("agent_types", {}).get("types", [])
        agent_type = next((a for a in agent_types if a["id"] == agent_id), None)

        if not agent_type:
            ttk.Label(
                self.config_inner,
                text="Agent type not found",
                foreground="#ff4444"
            ).pack(pady=20)
            return

        # Get or create config for this agent
        config = self._ensure_agent_config(agent_id)
        config.setdefault("temperature", agent_type.get("recommended_temp", 0.7))
        config.setdefault("conformer_priority", agent_type.get("default_conformer_priority", "auto"))
        # If a variant exists and no tool map present, apply defaults once
        try:
            if config.get('variant') and not config.get('enabled_tools'):
                self._apply_agent_variant_defaults(agent_id, config.get('variant'))
        except Exception:
            pass

        # Header
        header_frame = ttk.Frame(self.config_inner, style='Category.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            header_frame,
            text=agent_type["display_name"],
            font=("Arial", 14, "bold")
        ).pack(side=tk.LEFT)

        # Enable/Disable toggle
        enabled_var = tk.BooleanVar(value=config["enabled"])

        def toggle_enabled():
            config["enabled"] = enabled_var.get()
            log_message(f"AGENTS_TAB: Agent {agent_id} {'enabled' if config['enabled'] else 'disabled'}")
            # Don't spawn servers here - only mark as enabled/disabled in roster

        ttk.Checkbutton(
            header_frame,
            text="Enabled",
            variable=enabled_var,
            command=toggle_enabled
        ).pack(side=tk.RIGHT)

        # Variant Selector
        variant_frame = ttk.LabelFrame(self.config_inner, text="Model Variant", padding=10)
        variant_frame.pack(fill=tk.X, pady=5)

        ttk.Label(variant_frame, text="Select variant:").pack(anchor=tk.W, pady=(0, 5))

        variant_var = tk.StringVar(value=config["variant"] or "Not selected")
        variant_combo = ttk.Combobox(
            variant_frame,
            textvariable=variant_var,
            state="readonly",
            width=30
        )
        variant_combo['values'] = self._get_available_variants(agent_type["base_type"]) or ["Not selected"]
        variant_combo.pack(fill=tk.X, pady=(0, 5))

        def on_variant_change(e):
            vid = variant_var.get()

            # Skip if separator selected
            if "───────" in vid:
                variant_combo.set(config.get('variant') or 'Not selected')
                return

            # Clear all assignment fields first
            config["variant"] = None
            config["gguf_override"] = None
            config["ollama_tag_override"] = None

            # Parse selection type
            if vid.startswith("[GGUF] "):
                # Unassigned GGUF selected
                gguf_name = vid.replace("[GGUF] ", "")
                # Find full path
                for path in self._get_unassigned_local_ggufs():
                    from pathlib import Path
                    if Path(path).name == gguf_name:
                        config["gguf_override"] = path
                        break
            elif vid.startswith("[Ollama] "):
                # Unassigned Ollama tag selected
                tag = vid.replace("[Ollama] ", "")
                config["ollama_tag_override"] = tag
                config["backend"] = "ollama"  # Force Ollama backend
            else:
                # Regular variant selected
                config["variant"] = vid
                # Apply default tools/resources based on type/class of this variant
                try:
                    self._apply_agent_variant_defaults(agent_id, vid)
                except Exception as _e:
                    log_message(f"AGENTS_TAB: _apply_agent_variant_defaults failed: {_e}")
                # Validate that a local GGUF exists for this variant (llama_server)
                try:
                    if not self._variant_has_local_gguf(vid):
                        from tkinter import messagebox
                        messagebox.showwarning(
                            "No GGUF Assigned",
                            f"Variant '{vid}' has no local GGUF assigned.\n"
                            f"Assign a GGUF in Models → Collections before using this agent."
                        )
                except Exception:
                    pass

            # Auto-enable this agent when a model is chosen
            try:
                config['enabled'] = True
            except Exception:
                pass

            # Notify active roster update
            try:
                self._notify_roster_changed()
            except Exception:
                pass

            log_message(f"AGENTS_TAB: Set {agent_id} to {vid}")

        variant_combo.bind("<<ComboboxSelected>>", on_variant_change)

        # Set‑Agent button: apply just this agent's config to the current session roster
        def _set_agent_now():
            try:
                # Validate an assignment exists
                has_variant = bool((config.get('variant') or '').strip())
                has_override = bool((config.get('gguf_override') or '').strip() or (config.get('ollama_tag_override') or '').strip())
                if not (has_variant or has_override):
                    from tkinter import messagebox
                    messagebox.showwarning('No Assignment', 'Please select a Variant or an Unassigned model (GGUF/Ollama) first.')
                    return
                # Mark enabled and publish roster
                config['enabled'] = True
                self._notify_roster_changed()
                try:
                    from tkinter import messagebox
                    messagebox.showinfo('Agent Set', f"Applied '{agent_id}' to the current session.")
                except Exception:
                    pass
            except Exception:
                pass

        # Remove‑Agent button: clears assignment and updates roster/indicators
        def _remove_agent():
            try:
                # Clear assignments
                config['variant'] = None
                config['gguf_override'] = None
                config['ollama_tag_override'] = None
                # Disable agent by default when unassigned
                config['enabled'] = False
                # Reflect in UI combobox
                try:
                    variant_combo.set('Not selected')
                except Exception:
                    pass
                # Notify roster change so Collections/indicators back off
                self._notify_roster_changed()
                # Gentle info
                try:
                    from tkinter import messagebox
                    messagebox.showinfo('Agent Removed', f"Cleared assignment for '{agent_id}'.\n\nTip: Click 'Save Agents Default' to persist across relaunches.")
                except Exception:
                    pass
            except Exception:
                pass

        btns_row = ttk.Frame(variant_frame)
        btns_row.pack(fill=tk.X, pady=(4,0))
        ttk.Button(btns_row, text="✓ Set Agent", style='Select.TButton', command=_set_agent_now).pack(side=tk.LEFT)
        ttk.Button(btns_row, text="✖ Remove Agent", command=_remove_agent).pack(side=tk.LEFT, padx=6)

        # MoE Assignment toggle
        def _assign_moe():
            self._show_moe_assignment_dialog(agent_id)
        ttk.Button(btns_row, text="🎯 Assign MoE", command=_assign_moe).pack(side=tk.LEFT, padx=6)

        def _mount_and_open():
            try:
                config['enabled'] = True
                self._notify_roster_changed()
            except Exception as exc:
                log_message(f"AGENTS_TAB: Mount+Chat roster update failed for {agent_id}: {exc}")

            mounted = False
            try:
                chat = getattr(self.parent_tab, 'chat_interface', None)
                if chat and hasattr(chat, 'mount_agent'):
                    mounted = chat.mount_agent(agent_id, user_initiated=True)
                elif chat and hasattr(chat, '_mount_agents_all'):
                    chat._mount_agents_all(user_initiated=True, target_names=[agent_id])
                    mounted = True
                if mounted and chat and hasattr(chat, 'add_message'):
                    chat.add_message('system', f"[Agents] Mounted {agent_id} via Agents panel")
            except Exception as exc:
                log_message(f"AGENTS_TAB: Mount+Chat execution failed for {agent_id}: {exc}")

            try:
                if hasattr(self.parent_tab, 'select_subtab'):
                    self.parent_tab.select_subtab('Chat')
            except Exception as exc:
                log_message(f"AGENTS_TAB: Mount+Chat tab select failed for {agent_id}: {exc}")

            if not mounted:
                try:
                    messagebox.showinfo('Mount Agent', f"Agent '{agent_id}' is queued for mounting. Ensure settings are correct and try again if required.")
                except Exception:
                    pass

        ttk.Button(btns_row, text="⚡ Mount + Chat", command=_mount_and_open).pack(side=tk.LEFT, padx=6)

        ttk.Button(
            variant_frame,
            text="🔄 Refresh Variants",
            command=lambda: self._refresh_variants(variant_combo, agent_type["base_type"])
        ).pack(anchor=tk.E)

        # Routing preferences
        routing_frame = ttk.LabelFrame(self.config_inner, text="Routing Preferences", padding=8)
        routing_frame.pack(fill=tk.X, pady=5)
        routing_frame.columnconfigure(1, weight=1)

        chat_route_var = tk.StringVar(value=self._route_display_label("chat", config.get("chat_route", "panel")))
        self._routing_vars['chat'][agent_id] = chat_route_var
        ttk.Label(routing_frame, text="Chat responses:").grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        chat_combo = ttk.Combobox(
            routing_frame,
            state='readonly',
            values=list(self.CHAT_ROUTE_DISPLAY.values()),
            textvariable=chat_route_var,
            width=24
        )
        chat_combo.grid(row=0, column=1, sticky=tk.W, pady=(0, 4))
        chat_combo.bind(
            '<<ComboboxSelected>>',
            lambda _e: self._set_route_from_display(agent_id, 'chat_route', chat_route_var.get())
        )

        tool_route_var = tk.StringVar(value=self._route_display_label("tool", config.get("tool_route", "panel")))
        self._routing_vars['tool'][agent_id] = tool_route_var
        ttk.Label(routing_frame, text="Tool results:").grid(row=1, column=0, sticky=tk.W, pady=(0, 4))
        tool_combo = ttk.Combobox(
            routing_frame,
            state='readonly',
            values=list(self.TOOL_ROUTE_DISPLAY.values()),
            textvariable=tool_route_var,
            width=24
        )
        tool_combo.grid(row=1, column=1, sticky=tk.W, pady=(0, 4))
        tool_combo.bind(
            '<<ComboboxSelected>>',
            lambda _e: self._set_route_from_display(agent_id, 'tool_route', tool_route_var.get())
        )

        ttk.Label(
            routing_frame,
            text="Controls where delegated chats and tool outputs appear.",
            font=("Arial", 8),
            foreground="#8b949e"
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(4, 0))

        # Backend / Hardware quick settings (per agent)
        bh = ttk.LabelFrame(self.config_inner, text="Backend & Hardware", padding=8)
        bh.pack(fill=tk.X, pady=5)
        # Backend radios
        ttk.Label(bh, text="Backend:").grid(row=0, column=0, sticky=tk.W)
        backend_var = tk.StringVar(value=(config.get('backend') or 'inherit'))
        def _set_backend(v):
            old_backend = config.get('backend')
            config['backend'] = (None if v == 'inherit' else v)
            log_message(
                f"AGENTS_TAB: operation=config_change agent={agent_id} field=backend "
                f"old_value={old_backend} new_value={config.get('backend')}"
            )
            self._notify_roster_changed()
            _refresh_agent_hw_controls()
        for i,(val,label) in enumerate((('inherit','Inherit'),('ollama','Ollama'),('llama_server','Llama‑server'))):
            ttk.Radiobutton(bh, text=label, value=val, variable=backend_var, command=lambda v=backend_var: _set_backend(v.get())).grid(row=0, column=i+1, padx=4, sticky=tk.W)
        # Hardware radios
        ttk.Label(bh, text="Hardware:").grid(row=1, column=0, sticky=tk.W, pady=(4,0))
        hw_var = tk.StringVar(value=(config.get('hardware') or 'inherit'))
        def _set_hw(v):
            old_hardware = config.get('hardware')
            config['hardware'] = (None if v == 'inherit' else v)
            log_message(
                f"AGENTS_TAB: operation=config_change agent={agent_id} field=hardware "
                f"old_value={old_hardware} new_value={config.get('hardware')}"
            )
            self._notify_roster_changed()
            _refresh_agent_hw_controls()
        hw_opts = [('inherit','Inherit'),('gpu','GPU'),('cpu','CPU'),('hybrid','GPU+CPU'),('auto','Auto')]
        for i,(val,label) in enumerate(hw_opts):
            ttk.Radiobutton(bh, text=label, value=val, variable=hw_var, command=lambda v=hw_var: _set_hw(v.get())).grid(row=1, column=i+1, padx=4, sticky=tk.W)
        # Resource controls
        ttk.Label(bh, text="GPU Layers:").grid(row=2, column=0, sticky=tk.W, pady=(4,0))
        lay_var = tk.IntVar(value=(config.get('n_gpu_layers') if isinstance(config.get('n_gpu_layers'), int) else 0))
        def _set_layers():
            old_layers = config.get('n_gpu_layers')
            v = int(lay_var.get() or 0)
            config['n_gpu_layers'] = (None if v <= 0 else v)
            log_message(
                f"AGENTS_TAB: operation=config_change agent={agent_id} field=n_gpu_layers "
                f"old_value={old_layers} new_value={config.get('n_gpu_layers')}"
            )
            self._notify_roster_changed()
        ttk.Entry(bh, textvariable=lay_var, width=6).grid(row=2, column=1, sticky=tk.W)
        ttk.Button(bh, text='Apply', command=_set_layers).grid(row=2, column=2, padx=4)
        ttk.Label(bh, text="CPU Threads:").grid(row=2, column=3, sticky=tk.W)
        thr_var = tk.IntVar(value=(config.get('cpu_threads') if isinstance(config.get('cpu_threads'), int) else 0))
        def _set_threads():
            old_threads = config.get('cpu_threads')
            v = int(thr_var.get() or 0)
            config['cpu_threads'] = (None if v <= 0 else v)
            log_message(
                f"AGENTS_TAB: operation=config_change agent={agent_id} field=cpu_threads "
                f"old_value={old_threads} new_value={config.get('cpu_threads')}"
            )
            self._notify_roster_changed()
        ttk.Entry(bh, textvariable=thr_var, width=6).grid(row=2, column=4, sticky=tk.W)
        ttk.Button(bh, text='Apply', command=_set_threads).grid(row=2, column=5, padx=4)

        # Effective inherit hint row
        eff_hint = ttk.Label(bh, text="", style='Config.TLabel', foreground='#8b949e')
        eff_hint.grid(row=3, column=0, columnspan=6, sticky=tk.W, pady=(4,0))

        # Gating: disable incompatible controls based on backend
        def _refresh_agent_hw_controls():
            try:
                b = backend_var.get()
            except Exception:
                b = 'inherit'
            # GPU layers only meaningful for llama_server
            # Disable layers when Ollama; also disable if llama_server chosen but no GGUF is present for selected variant
            try:
                sel_variant = config.get('variant') or ''
                has_gguf = (self._variant_has_local_gguf(sel_variant) if sel_variant else False)
            except Exception:
                has_gguf = False
            state_layers = tk.NORMAL if (b in ('inherit','llama_server') and (b != 'llama_server' or has_gguf or b == 'inherit')) else tk.DISABLED
            # CPU threads impacts both; keep enabled
            # Apply state to entries (grid returns widget; create references)
            try:
                for w in bh.grid_slaves(row=2, column=1):
                    w.configure(state=state_layers)
            except Exception:
                pass
            # Update effective hint
            _update_effective_hint()

        def _update_effective_hint():
            try:
                b = backend_var.get()
            except Exception:
                b = 'inherit'
            try:
                h = hw_var.get()
            except Exception:
                h = 'inherit'
            layers_txt = (str(lay_var.get()) if int(lay_var.get() or 0) > 0 else 'inherit')
            threads_txt = (str(thr_var.get()) if int(thr_var.get() or 0) > 0 else 'inherit')
            # If llama_server selected but no GGUF, add a gentle hint
            warn = ''
            try:
                sel_variant = config.get('variant') or ''
                if (b == 'llama_server') and (not sel_variant or not self._variant_has_local_gguf(sel_variant)):
                    warn = '  (no local GGUF for selected variant)'
            except Exception:
                pass
            eff_hint.config(text=f"Effective: backend={b}  hardware={h}  layers={layers_txt}  threads={threads_txt}{warn}")
        _refresh_agent_hw_controls()
        _update_effective_hint()

        # Retrieval preferences
        retrieval_frame = ttk.LabelFrame(self.config_inner, text="Retrieval Preferences", padding=10)
        retrieval_frame.pack(fill=tk.X, pady=5)
        ttk.Label(
            retrieval_frame,
            text="Default RAG level when this agent chats (overrides panel default):",
            font=("Arial", 9)
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 6))

        rag_options = [
            ("Inherit (Panel)", 0),
            ("L1 – Light (2 snippets)", 1),
            ("L2 – Balanced (4 snippets)", 2),
            ("L3 – Max (6 snippets)", 3),
        ]

        def _label_for_level(level: int) -> str:
            for label, value in rag_options:
                if value == level:
                    return label
            return rag_options[0][0]

        rag_var = tk.StringVar(value=_label_for_level(int(config.get('rag_level', 0) or 0)))

        rag_combo = ttk.Combobox(
            retrieval_frame,
            textvariable=rag_var,
            state='readonly',
            values=[label for label, _ in rag_options],
            width=28
        )
        rag_combo.grid(row=1, column=0, sticky=tk.W)

        def _on_rag_change(_event=None):
            selected = rag_var.get()
            for label, value in rag_options:
                if label == selected:
                    config['rag_level'] = value
                    log_message(
                        f"AGENTS_TAB: operation=config_change agent={agent_id} field=rag_level new_value={value}"
                    )
                    try:
                        self._notify_roster_changed()
                    except Exception:
                        pass
                    break

        rag_combo.bind('<<ComboboxSelected>>', _on_rag_change)

        ttk.Label(
            retrieval_frame,
            text="Used by agent chat popups and orchestrated runs.",
            font=("Arial", 8),
            foreground="#8b949e"
        ).grid(row=2, column=0, sticky=tk.W, pady=(4,0))

        # Tools section
        tools_frame = ttk.LabelFrame(self.config_inner, text="Allowed Tools (per agent)", padding=8)
        tools_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        tools_frame.columnconfigure(0, weight=1)
        self._build_tools_checklist(tools_frame, agent_id)

        # Actions row: Save Defaults (session setting happens via Set‑Agent above)
        actions = ttk.Frame(self.config_inner)
        actions.pack(fill=tk.X, pady=(8, 4))
        ttk.Button(actions, text="Save Agents Default", style='Select.TButton', command=self._save_agents_default).pack(side=tk.LEFT)

        # Note: Unassigned models (GGUF/Ollama) are now integrated into the variant dropdown above

        # Temperature Slider
        temp_frame = ttk.LabelFrame(self.config_inner, text="Temperature", padding=10)
        temp_frame.pack(fill=tk.X, pady=5)

        temp_var = tk.DoubleVar(value=config["temperature"])

        temp_display = ttk.Label(
            temp_frame,
            text=f"Current: {config['temperature']:.2f} (Recommended: {agent_type.get('recommended_temp', 0.7):.2f})",
            font=("Arial", 9),
            foreground="#888888"
        )
        temp_display.pack(anchor=tk.W, pady=(0, 5))

        def on_temp_change(val):
            temp = float(val)
            config["temperature"] = temp
            temp_display.config(text=f"Current: {temp:.2f} (Recommended: {agent_type.get('recommended_temp', 0.7):.2f})")

        temp_scale = ttk.Scale(
            temp_frame,
            from_=0.0,
            to=2.0,
            orient=tk.HORIZONTAL,
            variable=temp_var,
            command=on_temp_change
        )
        temp_scale.pack(fill=tk.X, pady=(0, 5))

        # Quick temp buttons
        temp_buttons = ttk.Frame(temp_frame, style='Category.TFrame')
        temp_buttons.pack(fill=tk.X)

        for label, val in [("Creative", 0.9), ("Balanced", 0.7), ("Precise", 0.5), ("Deterministic", 0.2)]:
            ttk.Button(
                temp_buttons,
                text=label,
                command=lambda v=val: temp_var.set(v),
                width=12
            ).pack(side=tk.LEFT, padx=2)

        # Conformer Priority
        conformer_frame = ttk.LabelFrame(self.config_inner, text="Conformer Priority", padding=10)
        conformer_frame.pack(fill=tk.X, pady=5)

        ttk.Label(
            conformer_frame,
            text="Operation approval requirements:",
            font=("Arial", 9)
        ).pack(anchor=tk.W, pady=(0, 5))

        conformer_var = tk.StringVar(value=config["conformer_priority"])

        priorities = [
            ("Auto (based on class)", "auto"),
            ("High (strict, require approval)", "high"),
            ("Medium (moderate)", "medium"),
            ("Low (relaxed, few approvals)", "low")
        ]

        for label, value in priorities:
            rb = ttk.Radiobutton(
                conformer_frame,
                text=label,
                variable=conformer_var,
                value=value,
                command=lambda: config.update({"conformer_priority": conformer_var.get()})
            )
            rb.pack(anchor=tk.W, pady=2)

        # Resource Allocation (Phase 1.6D)
        resource_frame = ttk.LabelFrame(self.config_inner, text="Resource Allocation", padding=10)
        resource_frame.pack(fill=tk.X, pady=5)

        # Get resource allocation settings from config
        try:
            import sys
            config_path = Path(__file__).parent.parent.parent.parent
            if str(config_path) not in sys.path:
                sys.path.insert(0, str(config_path))
            from config import get_resource_allocation

            # Get allocation for base type and class
            base_type = agent_type["base_type"]
            class_level = "skilled"  # Default, should be from model profile
            allocation = get_resource_allocation(base_type, class_level)

            # Initialize resource config if not present
            if "resource_allocation" not in config:
                config["resource_allocation"] = allocation["default"]

            resource_var = tk.IntVar(value=config.get("resource_allocation", allocation["default"]))

            # Resource info label
            resource_display = ttk.Label(
                resource_frame,
                text=f"Current: {config.get('resource_allocation', allocation['default'])}% (Range: {allocation['min']}-{allocation['max']}%)",
                font=("Arial", 9),
                foreground="#888888"
            )
            resource_display.pack(anchor=tk.W, pady=(0, 5))

            def on_resource_change(val):
                resources = int(float(val))
                config["resource_allocation"] = resources
                resource_display.config(text=f"Current: {resources}% (Range: {allocation['min']}-{allocation['max']}%)")

            resource_scale = ttk.Scale(
                resource_frame,
                from_=allocation["min"],
                to=allocation["max"],
                orient=tk.HORIZONTAL,
                variable=resource_var,
                command=on_resource_change
            )
            resource_scale.pack(fill=tk.X, pady=(0, 5))

            # Quick resource buttons
            resource_buttons = ttk.Frame(resource_frame, style='Category.TFrame')
            resource_buttons.pack(fill=tk.X)

            ttk.Button(
                resource_buttons,
                text="Min",
                command=lambda: resource_var.set(allocation["min"]),
                width=8
            ).pack(side=tk.LEFT, padx=2)

            ttk.Button(
                resource_buttons,
                text="Default",
                command=lambda: resource_var.set(allocation["default"]),
                width=8
            ).pack(side=tk.LEFT, padx=2)

            ttk.Button(
                resource_buttons,
                text="Max",
                command=lambda: resource_var.set(allocation["max"]),
                width=8
            ).pack(side=tk.LEFT, padx=2)

            # Resource usage indicator (simulated for now)
            usage_label = ttk.Label(
                resource_frame,
                text="Current usage: 0% (Not active)",
                font=("Arial", 8),
                foreground="#666666"
            )
            usage_label.pack(anchor=tk.W, pady=(5, 0))

        except Exception as e:
            log_message(f"AGENTS_TAB: Error loading resource config: {e}")
            ttk.Label(
                resource_frame,
                text="Resource configuration unavailable",
                foreground="#ff6b6b"
            ).pack()

        # Tools Configuration
        tools_frame = ttk.LabelFrame(self.config_inner, text="Tools", padding=10)
        tools_frame.pack(fill=tk.X, pady=5)

        base_type_info = next((t for t in self.type_catalog.get("types", []) if t["id"] == agent_type["base_type"]), None)

        if base_type_info:
            required_tools = base_type_info.get("required_tools", [])
            recommended_tools = base_type_info.get("recommended_tools", [])

            ttk.Label(
                tools_frame,
                text=f"Required: {', '.join(required_tools) if required_tools else 'None'}",
                font=("Arial", 9),
                foreground="#44ff44"
            ).pack(anchor=tk.W)

            ttk.Label(
                tools_frame,
                text=f"Recommended: {', '.join(recommended_tools) if recommended_tools else 'None'}",
                font=("Arial", 9),
                foreground="#ffaa00"
            ).pack(anchor=tk.W, pady=(0, 5))

            ttk.Button(
                tools_frame,
                text="⚙️ Auto‑enable from Type/Class",
                command=lambda aid=agent_id, vid=config.get('variant'): self._apply_agent_variant_defaults(aid, vid) if vid else None
            ).pack(anchor=tk.W)

        # Action Buttons
        actions_frame = ttk.Frame(self.config_inner, style='Category.TFrame')
        actions_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(
            actions_frame,
            text="✓ Save Configuration",
            command=lambda: self._save_agent_config(agent_id),
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            actions_frame,
            text="🧪 Test Agent",
            command=lambda: self._test_agent(agent_id)
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            actions_frame,
            text="Reset to Defaults",
            command=lambda: self._reset_agent_config(agent_id)
        ).pack(side=tk.RIGHT, padx=5)

    def _get_available_variants(self, type_id: str) -> List[str]:
        """Return variants for this agent type, including unassigned models.
        Format: [type-assigned variants, separator, unassigned GGUFs, unassigned Ollama tags]
        """
        try:
            import sys
            from pathlib import Path
            cfg_path = Path(__file__).parent.parent.parent.parent
            if str(cfg_path) not in sys.path:
                sys.path.insert(0, str(cfg_path))
            from config import list_model_profiles
            items = list_model_profiles() or []

            # Type-assigned variants
            vids = [rec.get('variant_id') for rec in items
                    if (rec.get('assigned_type') or '').lower() == (type_id or '').lower()]
            vids = [v for v in vids if v]
            result = sorted(vids)

            # Add separator and unassigned models if they exist
            unassigned_ggufs = self._get_unassigned_local_ggufs()
            unassigned_ollama = self._get_unassigned_ollama_tags()

            if unassigned_ggufs or unassigned_ollama:
                result.append("─────── Unassigned Models ───────")

                # Add GGUF files with [GGUF] prefix
                for gguf_path in unassigned_ggufs:
                    from pathlib import Path
                    name = Path(gguf_path).name
                    result.append(f"[GGUF] {name}")

                # Add Ollama tags with [Ollama] prefix
                for tag in unassigned_ollama:
                    result.append(f"[Ollama] {tag}")

            return result
        except Exception as e:
            log_message(f"AGENTS_TAB: _get_available_variants error: {e}")
            return []

    def _get_unassigned_variants(self) -> List[str]:
        """Return list of variant_ids that are currently unassigned to any type.
        Note: kept for compatibility; not used in UI (we show unassigned GGUFs instead).
        """
        try:
            import sys
            from pathlib import Path
            cfg_path = Path(__file__).parent.parent.parent.parent
            if str(cfg_path) not in sys.path:
                sys.path.insert(0, str(cfg_path))
            from config import list_model_profiles
            items = list_model_profiles() or []
            vids = [rec.get('variant_id') for rec in items if (rec.get('assigned_type') or 'unassigned') == 'unassigned']
            vids = [v for v in vids if v]
            return sorted(vids)
        except Exception as e:
            log_message(f"AGENTS_TAB: _get_unassigned_variants error: {e}")
            return []

    def _get_unassigned_local_ggufs(self) -> List[str]:
        """Return local GGUF artifact paths that are NOT assigned to any variant.
        Scans exports/gguf and subtracts those recorded in unified assignments (assignments.json).
        """
        try:
            import sys
            from pathlib import Path
            cfg_path = Path(__file__).parent.parent.parent.parent
            if str(cfg_path) not in sys.path:
                sys.path.insert(0, str(cfg_path))
            from config import list_assigned_local_by_variant
            from os.path import abspath
            assigned_paths = set()
            assigned_names = set()
            for paths in (list_assigned_local_by_variant() or {}).values():
                for p in paths or []:
                    try:
                        rp = str(Path(p))
                        assigned_paths.add(str(Path(rp).resolve()))
                        assigned_names.add(Path(rp).name)
                    except Exception:
                        assigned_paths.add(str(p))
                        try:
                            assigned_names.add(Path(str(p)).name)
                        except Exception:
                            pass
            # Typical exports folder used by Models → Exports
            gguf_dir = Path('Data')/'exports'/'gguf'
            out = []
            if gguf_dir.exists():
                # Search recursively to match right-side display behavior
                for p in gguf_dir.rglob('*.gguf'):
                    try:
                        rp = str(p.resolve())
                    except Exception:
                        rp = str(p)
                    # Exclude if exact path or basename is already assigned
                    if (rp in assigned_paths) or (p.name in assigned_names):
                        continue
                    out.append(str(p))
            return sorted(out)
        except Exception as e:
            log_message(f"AGENTS_TAB: _get_unassigned_local_ggufs error: {e}")
            return []

    def _get_unassigned_ollama_tags(self) -> List[str]:
        """Return Ollama tags not assigned to any variant (for quick selection)."""
        try:
            import sys
            from pathlib import Path
            cfg_path = Path(__file__).parent.parent.parent.parent
            if str(cfg_path) not in sys.path:
                sys.path.insert(0, str(cfg_path))
            from config import get_ollama_models, list_assigned_ollama_tags
            models = set(get_ollama_models() or [])
            assigned = set(list_assigned_ollama_tags() or [])
            return sorted([m for m in models if m not in assigned])
        except Exception as e:
            log_message(f"AGENTS_TAB: _get_unassigned_ollama_tags error: {e}")
            return []

    def _refresh_variants(self, combo: ttk.Combobox, type_id: str):
        """Refresh variant list"""
        variants = self._get_available_variants(type_id) or ["Not selected"]
        combo['values'] = variants
        log_message(f"AGENTS_TAB: Refreshed variants for {type_id}")

    def _variant_has_local_gguf(self, variant_id: str) -> bool:
        try:
            import sys
            from pathlib import Path
            cfg_path = Path(__file__).parent.parent.parent.parent
            if str(cfg_path) not in sys.path:
                sys.path.insert(0, str(cfg_path))
            from config import list_assigned_local_by_variant
            local = list_assigned_local_by_variant() or {}
            return bool(local.get(variant_id))
        except Exception:
            return False

    def _build_tools_checklist(self, parent: ttk.Frame, agent_id: str):
        """Build (or rebuild) the tools checklist for a given agent config."""
        # Clear existing rows
        for w in parent.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass
        cfg = self.agent_configs.get(agent_id, {})
        enabled_map = dict(cfg.get('enabled_tools') or {})
        # Load tool universe from unified profile + permissions catalog (union)
        try:
            import sys
            from pathlib import Path
            cfg_path = Path(__file__).parent.parent.parent.parent
            if str(cfg_path) not in sys.path:
                sys.path.insert(0, str(cfg_path))
            import config as C
            prof = C.get_unified_tool_profile('Default')
            prof_tools = set((prof.get('tools') or {}).get('enabled_tools', {}).keys())
            # Add tools referenced by permissions to ensure visibility for type/class defaults
            perm = C.load_tool_permissions()
            perm_tools = set()
            for entry in (perm.get('type_permissions') or {}).values():
                for lst in (entry or {}).values():
                    for t in (lst or []):
                        if t != '*':
                            perm_tools.add(t)
            # Add global tools
            for t in (perm.get('global_tools', {}).get('tools', []) or []):
                perm_tools.add(t)
            all_tools = sorted(prof_tools.union(perm_tools))
        except Exception:
            all_tools = sorted((enabled_map or {}).keys())
        # If empty, show hint
        if not all_tools:
            ttk.Label(parent, text='No tools profile found.', foreground='#888888').pack(anchor=tk.W)
            return
        # Two-column checklist
        cols = 2
        grid = ttk.Frame(parent); grid.pack(fill=tk.X)
        for c in range(cols):
            grid.columnconfigure(c, weight=1)
        self._tool_vars = getattr(self, '_tool_vars', {})
        for i, name in enumerate(all_tools):
            var = tk.BooleanVar(value=bool(enabled_map.get(name, False)))
            self._tool_vars[(agent_id, name)] = var
            cb = ttk.Checkbutton(grid, text=name, variable=var, command=lambda n=name, v=var: self._on_tool_toggled(agent_id, n, v.get()))
            cb.grid(row=i//cols, column=i%cols, sticky=tk.W, padx=4, pady=2)

    def _on_tool_toggled(self, agent_id: str, tool_name: str, state: bool):
        cfg = self.agent_configs.get(agent_id)
        if not cfg:
            return
        m = dict(cfg.get('enabled_tools') or {})
        m[tool_name] = bool(state)
        cfg['enabled_tools'] = m
        # Do not notify roster immediately on each click to avoid churn
        # User can press Set Active Roster to apply.

    def _apply_agent_variant_defaults(self, agent_id: str, variant_id: str):
        """Set default tools/resources for the agent based on variant's type/class."""
        cfg = self.agent_configs.get(agent_id)
        if not cfg:
            return
        try:
            import sys
            from pathlib import Path
            cfg_path = Path(__file__).parent.parent.parent.parent
            if str(cfg_path) not in sys.path:
                sys.path.insert(0, str(cfg_path))
            import config as C
            mp = C.load_model_profile(variant_id) or {}
            type_id = mp.get('assigned_type') or 'unassigned'
            class_level = mp.get('class_level') or 'novice'
            allowed = C.get_tools_for_type_class(type_id, class_level) or []
            # Resolve tool universe
            prof = C.get_unified_tool_profile('Default')
            tool_universe = list((prof.get('tools') or {}).get('enabled_tools', {}).keys())
            enable_all = (allowed == ['*'])
            enabled_map = {}
            for t in tool_universe:
                enabled_map[t] = True if enable_all or (t in allowed) else False
            cfg['enabled_tools'] = enabled_map
            # Resource allocation defaults if available
            try:
                cfg['resource_allocation'] = C.get_resource_allocation(type_id, class_level)
            except Exception:
                pass

            # NEW: Apply schema/prompt defaults based on type/class
            try:
                # Check if variant profile has custom overrides
                agent_config_overrides = mp.get('agent_config', {})
                system_prompt_override = agent_config_overrides.get('system_prompt_override')
                tool_schema_override = agent_config_overrides.get('tool_schema_override')

                if system_prompt_override:
                    # Use custom override from variant profile
                    cfg['system_prompt'] = system_prompt_override
                    log_message(f"AGENTS_TAB: Using custom system_prompt for {agent_id}: {system_prompt_override}")
                elif not cfg.get('system_prompt_override'):
                    # No custom override, apply type/class defaults
                    defaults = self._get_schema_prompt_defaults(type_id, class_level)
                    cfg['system_prompt'] = defaults.get('system_prompt', 'default')
                    # Ensure prompt file exists
                    self._ensure_prompt_exists(cfg['system_prompt'], type_id, class_level)
                    log_message(f"AGENTS_TAB: Auto-assigned system_prompt for {agent_id}: {cfg['system_prompt']}")

                if tool_schema_override:
                    # Use custom override from variant profile
                    cfg['tool_schema'] = tool_schema_override
                    log_message(f"AGENTS_TAB: Using custom tool_schema for {agent_id}: {tool_schema_override}")
                elif not cfg.get('tool_schema_override'):
                    # No custom override, apply type/class defaults
                    defaults = self._get_schema_prompt_defaults(type_id, class_level)
                    cfg['tool_schema'] = defaults.get('tool_schema', 'default')
                    log_message(f"AGENTS_TAB: Auto-assigned tool_schema for {agent_id}: {cfg['tool_schema']}")
            except Exception as e:
                log_message(f"AGENTS_TAB: Error applying schema/prompt defaults: {e}")

            # Rebuild checklist if visible
            try:
                # rebuild using the currently displayed container
                for w in self.config_inner.winfo_children():
                    if isinstance(w, ttk.LabelFrame) and str(w.cget('text')).lower().startswith('allowed tools'):
                        self._build_tools_checklist(w, agent_id)
                        break
            except Exception:
                pass
        except Exception as e:
            log_message(f"AGENTS_TAB: Failed to apply defaults for {agent_id}/{variant_id}: {e}")

    def _current_roster(self) -> list:
        """Build a roster list from current agent configs suitable for root.set_active_agents."""
        roster = []
        try:
            agent_types = self.type_catalog.get("agent_types", {}).get("types", [])
            for a in agent_types:
                aid = a.get('id')
                cfg = self.agent_configs.get(aid)
                # Consider 'Not selected' as empty
                vid = (cfg.get('variant') or '').strip() if cfg else ''
                if not cfg or (not vid or vid.lower() == 'not selected'):
                    # Allow direct overrides without variant selection
                    if not cfg or not (cfg.get('gguf_override') or cfg.get('ollama_tag_override')):
                        continue
                # Skip disabled agents completely
                if not bool(cfg.get('enabled', True)):
                    continue
                base_type = cfg.get('assigned_type') or self.get_agent_base_type(aid)
                roster.append({
                    'name': aid,
                    'variant': (cfg.get('variant') or '').strip() or None,
                    'gguf_override': cfg.get('gguf_override'),
                    'ollama_tag': cfg.get('ollama_tag_override'),
                    'enabled_tools': cfg.get('enabled_tools', {}),
                    'backend': cfg.get('backend'),
                    'hardware': cfg.get('hardware'),
                    'n_gpu_layers': cfg.get('n_gpu_layers'),
                    'cpu_threads': cfg.get('cpu_threads'),
                    'active': bool(cfg.get('enabled', True)),
                    'working': False,
                    'scope': 'interface',
                    'system_prompt': cfg.get('system_prompt'),
                    'tool_schema': cfg.get('tool_schema'),
                    'system_prompt_override': cfg.get('system_prompt_override'),
                    'tool_schema_override': cfg.get('tool_schema_override'),
                    'moe_enabled': cfg.get('moe_enabled', False),
                    'moe_expert_panel': cfg.get('moe_expert_panel', []),
                    'rag_level': int(cfg.get('rag_level', 0) or 0),
                    'chat_route': cfg.get('chat_route', 'panel'),
                    'tool_route': cfg.get('tool_route', 'panel'),
                    'assigned_type': base_type or 'general',
                    '_server_port': cfg.get('_server_port'),
                })
        except Exception:
            pass
        return roster

    def _notify_roster_changed(self):
        """Send current roster to root so Chat/Projects indicators pick it up."""
        try:
            roster = self._current_roster()
            if hasattr(self.root, 'set_active_agents') and callable(getattr(self.root, 'set_active_agents')):
                self.root.set_active_agents(roster)
                # Detailed debug log of roster contents
                try:
                    details = []
                    for r in roster:
                        details.append(
                            f"{r.get('name','agent')} | variant={r.get('variant') or 'None'} | gguf={bool(r.get('gguf_override'))} | tag={r.get('ollama_tag') or 'None'} | be={r.get('backend') or 'inherit'} | gpu_layers={r.get('n_gpu_layers')} | threads={r.get('cpu_threads')}"
                        )
                    log_message(f"AGENTS_TAB: Active roster set ({len(roster)} agents)\n  - " + "\n  - ".join(details))
                except Exception:
                    log_message(f"AGENTS_TAB: Active roster set ({len(roster)} agents)")
                try:
                    if hasattr(self.root, 'get_active_agents'):
                        active = self.root.get_active_agents() or []
                        log_message(f"ROSTER_DEBUG: root.get_active_agents() -> {len(active)} entries")
                except Exception:
                    pass
            # Emit a Tk virtual event so other panels can refresh immediately
            try:
                self.root.event_generate('<<AgentsRosterChanged>>', when='tail')
            except Exception:
                pass
        except Exception as e:
            log_message(f"AGENTS_TAB: Failed to set active roster: {e}")

    def _save_agents_default(self):
        """Persist current roster as default. Saves to project if available, else global user prefs."""
        try:
            import json
            from pathlib import Path
            roster = self._current_roster()
            saved_path = None
            # Prefer current project context if accessible
            proj = None
            try:
                # Settings tab often stores the project context
                if hasattr(self.root, 'settings_tab') and getattr(self.root.settings_tab, 'current_project_context', None):
                    proj = self.root.settings_tab.current_project_context
            except Exception:
                proj = None
            if proj:
                p = Path('Data')/'projects'/proj
                p.mkdir(parents=True, exist_ok=True)
                saved_path = p/'agents_default.json'
                saved_path.write_text(json.dumps(roster, indent=2))
                log_message(f"AGENTS_TAB: Saved project default agents for '{proj}' ({len(roster)} agents)")
            else:
                d = Path('Data')/'user_prefs'
                d.mkdir(parents=True, exist_ok=True)
                saved_path = d/'agents_default.json'
                saved_path.write_text(json.dumps(roster, indent=2))
                log_message(f"AGENTS_TAB: Saved global default agents ({len(roster)} agents)")
            try:
                messagebox.showinfo('Saved', f'Saved {len(roster)} agents to default:\n{saved_path}')
            except Exception:
                pass
        except Exception as e:
            log_message(f"AGENTS_TAB: Failed to save agents default: {e}")
        # Apply immediately to current session
        try:
            roster = self._current_roster()
            if hasattr(self.root, 'set_active_agents') and callable(getattr(self.root, 'set_active_agents')):
                self.root.set_active_agents(roster)
                log_message("AGENTS_TAB: Applied saved agents default to active session")
            try:
                self.root.event_generate('<<AgentsRosterChanged>>', when='tail')
            except Exception:
                pass
        except Exception:
            pass

    def _save_agent_config(self, agent_id: str):
        """Save agent configuration"""
        config = self.agent_configs.get(agent_id)
        if not config:
            return

        # TODO: Persist to file
        log_message(f"AGENTS_TAB: Saved config for {agent_id}: {config}")
        messagebox.showinfo("Configuration Saved", f"Configuration for {agent_id} saved successfully!")

    def _test_agent(self, agent_id: str):
        """Test agent configuration"""
        config = self.agent_configs.get(agent_id)
        if not config:
            messagebox.showerror("Error", "No configuration found")
            return

        if not config.get("variant"):
            messagebox.showwarning("Warning", "Please select a variant first")
            return

        # TODO: Implement agent testing
        messagebox.showinfo(
            "Agent Test",
            f"Testing {agent_id}\n\n"
            f"Variant: {config['variant']}\n"
            f"Temperature: {config['temperature']}\n"
            f"Conformer: {config['conformer_priority']}\n\n"
            "Agent testing coming soon!"
        )

    def _reset_agent_config(self, agent_id: str):
        """Reset agent to default configuration"""
        result = messagebox.askyesno(
            "Reset Configuration",
            f"Reset {agent_id} to default settings?",
            icon=messagebox.WARNING
        )

        if result:
            if agent_id in self.agent_configs:
                del self.agent_configs[agent_id]
            self._show_agent_config(agent_id)
            log_message(f"AGENTS_TAB: Reset {agent_id} to defaults")

    def _show_moe_assignment_dialog(self, orchestrator_id: str):
        """Show MoE expert assignment dialog"""
        import tkinter as tk
        from tkinter import ttk

        config = self.agent_configs.get(orchestrator_id, {})
        current_experts = config.get('moe_expert_panel', [])

        # Check orchestrator's class level
        variant = config.get('variant')
        is_below_expert = False
        if variant:
            try:
                import sys
                from pathlib import Path
                cfg_path = Path(__file__).parent.parent.parent
                if str(cfg_path) not in sys.path:
                    sys.path.insert(0, str(cfg_path))
                from config import load_model_profile
                mp = load_model_profile(variant)
                class_level = mp.get('class_level', 'novice')
                is_below_expert = class_level not in ['expert', 'master']
            except Exception:
                pass

        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("MoE Broadcast Panel")
        dialog.geometry("500x650")
        dialog.transient(self.root)
        dialog.grab_set()

        # Header
        header = ttk.Frame(dialog, style='Category.TFrame')
        header.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header, text=f"📡 MoE Broadcast Panel: {orchestrator_id}",
                  font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').pack()

        # Explanation
        info_frame = ttk.Frame(dialog, style='Category.TFrame')
        info_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Label(info_frame,
                  text="Select which agents will receive broadcasts when using the MoE Broadcast feature.\n"
                       "This does NOT control which agents orchestrators can call via agent_request.\n"
                       "Agent access is controlled by the agent's tool_route setting (main/both = accessible).",
                  wraplength=460, justify=tk.LEFT, style='Config.TLabel', foreground="#aaaaaa").pack()

        # Warning if below expert
        if is_below_expert:
            warn_frame = ttk.Frame(dialog, style='Category.TFrame')
            warn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
            ttk.Label(warn_frame, text="⚠️ Warning", foreground="#ff6600",
                      font=("Arial", 10, "bold")).pack()
            ttk.Label(warn_frame,
                      text=f"The variant assigned to this agent has class level below 'expert'.\n"
                           f"MoE broadcast works best with expert or master class agents.",
                      wraplength=460, justify=tk.LEFT, style='Config.TLabel').pack()

        # Expert selection
        experts_frame = ttk.LabelFrame(dialog, text="Select Agents for MoE Broadcast", padding=10)
        experts_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Scrollable list
        canvas = tk.Canvas(experts_frame, bg='#2d2d2d', highlightthickness=0)
        scrollbar = ttk.Scrollbar(experts_frame, orient=tk.VERTICAL, command=canvas.yview)
        expert_list = ttk.Frame(canvas, style='Category.TFrame')

        expert_list.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=expert_list, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Get all agents except orchestrator
        agent_types = self.type_catalog.get("agent_types", {}).get("types", [])
        expert_vars = {}

        for agent_type in agent_types:
            agent_id = agent_type["id"]
            if agent_id == orchestrator_id:
                continue  # Can't assign self as expert

            var = tk.BooleanVar(value=(agent_id in current_experts))
            expert_vars[agent_id] = var

            row = ttk.Frame(expert_list, style='Category.TFrame')
            row.pack(fill=tk.X, pady=2)

            ttk.Checkbutton(row, text=f"{agent_type['display_name']}",
                            variable=var, style='Config.TCheckbutton').pack(side=tk.LEFT)

            # Show if assigned
            cfg = self.agent_configs.get(agent_id, {})
            if cfg.get('variant') or cfg.get('gguf_override') or cfg.get('ollama_tag_override'):
                ttk.Label(row, text="✓", foreground="#00ff00", style='Config.TLabel').pack(side=tk.RIGHT)

        # Count label
        count_label = ttk.Label(dialog, text="", style='Config.TLabel')
        count_label.pack(pady=(0, 10))

        def _update_count():
            selected = sum(1 for var in expert_vars.values() if var.get())
            count_label.config(text=f"{selected}/8 Agents Selected for Broadcast")

        _update_count()
        for var in expert_vars.values():
            var.trace_add('write', lambda *args: _update_count())

        # Buttons
        btn_frame = ttk.Frame(dialog, style='Category.TFrame')
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        def _save():
            selected = [agent_id for agent_id, var in expert_vars.items() if var.get()]
            config['moe_expert_panel'] = selected
            config['moe_enabled'] = bool(selected)
            self._update_moe_indicator()
            dialog.destroy()

        def _cancel():
            dialog.destroy()

        ttk.Button(btn_frame, text="Save", style='Action.TButton', command=_save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=_cancel).pack(side=tk.LEFT, padx=5)

    def _update_moe_indicator(self):
        """Update MoE indicator in Agent Catalog header"""
        try:
            total_assigned = 0
            total_experts = 0

            for agent_id, config in self.agent_configs.items():
                if config.get('moe_enabled'):
                    total_assigned += 1
                    total_experts += len(config.get('moe_expert_panel', []))

            if total_assigned > 0:
                text = f"MoE: {total_experts}/8 | {total_assigned} Assigned"
                self._moe_indicator_label.config(text=text, foreground="#00ff00")
            else:
                self._moe_indicator_label.config(text="", foreground="")
        except Exception:
            pass

    def _spawn_agent_server(self, agent_id: str, config: Dict):
        """Spawn dedicated llama.cpp server for agent using llama_server backend"""
        try:
            # Get model path
            model_path = self._get_agent_model_path(agent_id, config)
            if not model_path:
                log_message(f"AGENTS_TAB ERROR: Cannot spawn server for {agent_id} - no model path")
                return

            # Get hardware settings
            n_gpu_layers = config.get("n_gpu_layers") or 0
            cpu_threads = config.get("cpu_threads") or 8

            # Spawn server (debug log with parameters)
            try:
                log_message(
                    f"AGENTS_TAB: Spawning agent server | id={agent_id} | gguf={model_path} | n_gpu_layers={n_gpu_layers} | cpu_threads={cpu_threads}"
                )
            except Exception:
                pass
            port = self.agent_server_manager.spawn_server_for_agent(
                agent_id, model_path, n_gpu_layers, cpu_threads
            )

            if port:
                # Store port in config
                config["_server_port"] = port
                log_message(f"AGENTS_TAB: Agent {agent_id} server spawned on port {port}")
            else:
                log_message(f"AGENTS_TAB ERROR: Failed to spawn server for {agent_id}")
                # Disable agent since server spawn failed
                config["enabled"] = False

        except Exception as e:
            log_message(f"AGENTS_TAB ERROR: Exception spawning server for {agent_id}: {e}")
            config["enabled"] = False

    def _destroy_agent_server(self, agent_id: str):
        """Destroy dedicated llama.cpp server for agent"""
        try:
            if self.agent_server_manager.destroy_server_for_agent(agent_id):
                log_message(f"AGENTS_TAB: Agent {agent_id} server destroyed")
                # Remove port from config
                if agent_id in self.agent_configs:
                    self.agent_configs[agent_id].pop("_server_port", None)
        except Exception as e:
            log_message(f"AGENTS_TAB ERROR: Exception destroying server for {agent_id}: {e}")

    def _get_agent_model_path(self, agent_id: str, config: Dict) -> Optional[str]:
        """Get GGUF model path for agent"""
        try:
            # Check for GGUF override
            if config.get("gguf_override"):
                return config["gguf_override"]

            variant = (config.get("variant") or "").strip()

            # 1) Prefer config API for local artifacts by variant
            try:
                import sys
                from pathlib import Path as _P
                cfg_path = _P(__file__).parent.parent.parent.parent
                if str(cfg_path) not in sys.path:
                    sys.path.insert(0, str(cfg_path))
                from config import get_local_artifacts_by_variant
                if variant:
                    arts = get_local_artifacts_by_variant(variant) or []
                    for a in arts:
                        gg = a.get('gguf')
                        if gg and Path(gg).exists():
                            return gg
            except Exception:
                pass

            # 2) Fallback to assignments file if present
            try:
                from config import DATA_DIR
                assignments_file = DATA_DIR / "assignments.json"
                if assignments_file.exists():
                    with open(assignments_file, "r") as f:
                        assignments = json.load(f)
                    if variant and variant in assignments.get("variants", {}):
                        gguf_path = assignments["variants"][variant].get("gguf_path")
                        if gguf_path and Path(gguf_path).exists():
                            return gguf_path
            except Exception:
                pass

            # 3) Last resort: scan exports/gguf for a matching filename hint
            try:
                from pathlib import Path as _P
                ggdir = _P('Data')/'exports'/'gguf'
                if ggdir.exists() and variant:
                    cand = list(ggdir.rglob('*.gguf'))
                    variant_l = variant.lower()
                    for p in cand:
                        name = p.name.lower()
                        if variant_l in name and p.exists():
                            return str(p)
            except Exception:
                pass

            return None

        except Exception as e:
            log_message(f"AGENTS_TAB ERROR: Failed to get model path for {agent_id}: {e}")
            return None
