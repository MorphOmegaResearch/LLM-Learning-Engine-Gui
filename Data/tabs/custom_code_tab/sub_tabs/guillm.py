#!/usr/bin/env python3
"""
GUILLM - GUI Language Model Interface
Single-file GUI that can modify itself through natural language.
~70KB, ~2000 lines, complete with all requested features.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, simpledialog
import subprocess
import json
import os
import sys
import re
import argparse
import difflib
import threading
import time
import random
import hashlib
import inspect
import ast
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict

# ============================================================================
# CORE CONFIGURATION
# ============================================================================

VERSION = "1.0"
AUTHOR = "GUILLM System"

# Base paths
BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "guillm_data" / "logs"
SNAP_DIR = BASE_DIR / "guillm_data" / "snapshots"
SESS_DIR = BASE_DIR / "guillm_data" / "sessions"
PROF_DIR = BASE_DIR / "guillm_data" / "profiles"
CONF_DIR = BASE_DIR / "guillm_data" / "config"

# Create directories
for d in [LOG_DIR, SNAP_DIR, SESS_DIR, PROF_DIR, CONF_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Logging setup
log_file = LOG_DIR / f"guillm_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
DEBUG_MODE = True

def log(msg: str, level: str = "INFO"):
    if DEBUG_MODE:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        entry = f"[{timestamp}] [{level}] {msg}\n"
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(entry)
        if level == "ERROR":
            print(f"ERROR: {msg}")

# ============================================================================
# DATA STRUCTURES
# ============================================================================

class ElementType(Enum):
    WINDOW = "window"
    FRAME = "frame"
    BUTTON = "button"
    LABEL = "label"
    ENTRY = "entry"
    TEXT = "text"
    MENU = "menu"
    CANVAS = "canvas"
    LISTBOX = "listbox"
    COMBOBOX = "combobox"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SCALE = "scale"
    SPINBOX = "spinbox"
    PROGRESS = "progress"
    TAB = "tab"
    PANEL = "panel"
    TOOLBAR = "toolbar"
    STATUSBAR = "statusbar"
    SCROLLBAR = "scrollbar"
    SEPARATOR = "separator"
    TREEVIEW = "treeview"

@dataclass
class GUIElement:
    """Represents a GUI element with all its properties."""
    uid: str
    etype: ElementType
    widget: Any
    parent: Optional[str]
    name: str = ""
    text: str = ""
    bg: str = ""
    fg: str = ""
    font: str = ""
    width: int = 0
    height: int = 0
    x: int = 0
    y: int = 0
    visible: bool = True
    enabled: bool = True
    tags: List[str] = field(default_factory=list)
    attrs: Dict[str, Any] = field(default_factory=dict)
    children: List[str] = field(default_factory=list)
    source_info: Dict[str, Any] = field(default_factory=dict)
    line_number: int = 0

    def to_dict(self) -> Dict:
        """Convert to serializable dictionary."""
        return {
            'uid': self.uid,
            'etype': self.etype.value,
            'parent': self.parent,
            'name': self.name,
            'text': self.text,
            'bg': self.bg,
            'fg': self.fg,
            'font': self.font,
            'width': self.width,
            'height': self.height,
            'x': self.x,
            'y': self.y,
            'visible': self.visible,
            'enabled': self.enabled,
            'tags': self.tags,
            'attrs': self.attrs,
            'children': self.children,
            'source_info': self.source_info,
            'line_number': self.line_number
        }

@dataclass
class ChangeTask:
    """Represents a single change operation."""
    id: int
    description: str
    element_id: str
    action: str
    params: Dict[str, Any]
    status: str = "pending"  # pending, running, completed, failed, skipped
    depends_on: List[int] = field(default_factory=list)
    output: str = ""

@dataclass
class Snapshot:
    """Represents a GUI state snapshot."""
    timestamp: str
    name: str
    elements: Dict[str, Dict]
    metadata: Dict[str, Any]
    hash: str = ""

    def __post_init__(self):
        if not self.hash:
            self.hash = self.calculate_hash()

    def calculate_hash(self) -> str:
        """Calculate hash of snapshot data."""
        data = json.dumps({
            'timestamp': self.timestamp,
            'elements': self.elements,
            'metadata': self.metadata
        }, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()

    def save(self, path: Path):
        """Save snapshot to file."""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls, path: Path):
        """Load snapshot from file."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(**data)

# ============================================================================
# OLLAMA MANAGER
# ============================================================================

class OllamaManager:
    """Manages all Ollama interactions."""
    
    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host
        self.models = []
        self.current_model = ""
        self.client = None
        self._init_client()

    def _init_client(self):
        """Initialize Ollama client."""
        try:
            import ollama
            self.client = ollama.Client(host=self.host)
            log("Ollama client initialized")
            self.refresh_models()
        except ImportError:
            log("Ollama package not installed", "ERROR")
            self.client = None
        except Exception as e:
            log(f"Failed to connect to Ollama: {e}", "ERROR")
            self.client = None

    def refresh_models(self) -> List[str]:
        """Refresh list of available models."""
        if not self.client:
            return ["llama2"]
        
        try:
            response = self.client.list()
            models = []
            
            # Handle different response formats
            if hasattr(response, 'models'):
                for m in response.models:
                    models.append(m.model)
            elif isinstance(response, dict) and 'models' in response:
                for m in response['models']:
                    models.append(m['model'])
            elif isinstance(response, list):
                for m in response:
                    if isinstance(m, dict):
                        models.append(m.get('model', 'unknown'))
            
            self.models = list(set(models))  # Remove duplicates
            if not self.models:
                self.models = ["llama2"]
                
            if not self.current_model:
                self.current_model = self.models[0]
            
            log(f"Found {len(self.models)} models: {', '.join(self.models[:5])}")
            return self.models
        except Exception as e:
            log(f"Failed to list models: {e}", "ERROR")
            if not self.models:
                self.models = ["llama2"]
            if not self.current_model:
                self.current_model = self.models[0]
            return self.models

    def generate(self, prompt: str, system: str = "", model: str = "") -> str:
        """Generate text using specified model."""
        if not self.client:
            return "Error: Ollama not available. Install with: pip install ollama"
        
        model = model or self.current_model
        messages = []
        
        if system:
            messages.append({"role": "system", "content": system})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = self.client.chat(
                model=model,
                messages=messages,
                options={
                    'temperature': 0.7,
                    'top_p': 0.9,
                    'num_predict': 2048
                }
            )
            return response['message']['content'].strip()
        except Exception as e:
            log(f"Generation failed: {e}", "ERROR")
            return f"Error: {str(e)}"

    def analyze_gui_request(self, gui_state: str, request: str) -> Dict:
        """Analyze if GUI modification is needed."""
        system = """You are a GUI analysis expert. Determine if the user's request requires GUI changes.
        Return JSON with: {
            "needs_gui_change": bool,
            "change_type": "color|text|layout|add|remove|modify|multiple",
            "elements_involved": ["button", "label", etc.],
            "complexity": "simple|moderate|complex",
            "should_plan": bool,
            "suggested_actions": ["change X to Y", "add Z", etc.]
        }"""
        
        prompt = f"""Current GUI State:
{gui_state}

User Request: "{request}"

Analyze this request and determine what GUI modifications are needed."""
        
        response = self.generate(prompt, system)
        
        # Extract JSON
        try:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                return json.loads(match.group())
        except:
            pass
        
        # Default response
        return {
            "needs_gui_change": True,
            "change_type": "modify",
            "elements_involved": ["button", "label"],
            "complexity": "simple",
            "should_plan": False,
            "suggested_actions": [f"Implement: {request}"]
        }

    def generate_change_plan(self, gui_manifest: str, request: str, system: str = "") -> List[Dict]:
        """Generate detailed change plan."""
        system = system or """You are a GUI change planner. Create specific, actionable tasks.
        Return JSON array of tasks, each with: {
            "id": int,
            "description": string,
            "element": "element_id" or "find:type:label" or "any",
            "action": "config|create|destroy|bind|unbind|move|resize|rename",
            "params": {"key": "value", ...},
            "depends_on": [task_ids],
            "validate_with": "description of expected result"
        }"""
        
        prompt = f"""GUI Manifest:
{gui_manifest}

Request: "{request}"

Generate a step-by-step change plan. Be specific about colors (#hex), text, sizes, and positions."""
        
        response = self.generate(prompt, system)
        
        try:
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                return json.loads(match.group())
        except:
            pass
        
        # Default plan
        return [{
            "id": 1,
            "description": f"Implement: {request}",
            "element": "any",
            "action": "config",
            "params": {"text": f"Modified: {request[:30]}"},
            "depends_on": [],
            "validate_with": "Element should show modified text"
        }]

# ============================================================================
# GUI SCANNER
# ============================================================================

class GUIScanner:
    """Scans and analyzes GUI structure."""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.elements: Dict[str, GUIElement] = {}
        self.widget_map: Dict[str, tk.Widget] = {}
        self.next_id = 1
        self.source_map = {}
        
        # Property extraction patterns
        self.common_props = [
            'text', 'bg', 'fg', 'font', 'width', 'height',
            'relief', 'borderwidth', 'padx', 'pady',
            'state', 'cursor', 'takefocus'
        ]
        
        # Widget type to ElementType mapping
        self.type_map = {
            'Tk': ElementType.WINDOW,
            'Toplevel': ElementType.WINDOW,
            'Frame': ElementType.FRAME,
            'LabelFrame': ElementType.FRAME,
            'Button': ElementType.BUTTON,
            'Label': ElementType.LABEL,
            'Entry': ElementType.ENTRY,
            'Text': ElementType.TEXT,
            'Menu': ElementType.MENU,
            'Canvas': ElementType.CANVAS,
            'Listbox': ElementType.LISTBOX,
            'Combobox': ElementType.COMBOBOX,
            'Checkbutton': ElementType.CHECKBOX,
            'Radiobutton': ElementType.RADIO,
            'Scale': ElementType.SCALE,
            'Spinbox': ElementType.SPINBOX,
            'Progressbar': ElementType.PROGRESS,
            'Notebook': ElementType.TAB,
            'PanedWindow': ElementType.PANEL,
            'Scrollbar': ElementType.SCROLLBAR,
            'Separator': ElementType.SEPARATOR,
            'Treeview': ElementType.TREEVIEW
        }

    def _map_source_lines(self):
        """Map source code lines to potential widgets using AST."""
        try:
            self.source_map = {}
            source_path = Path(__file__)
            if not source_path.exists():
                return

            with open(source_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                # Look for widget creation (e.g., self.btn = ttk.Button(...))
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, (ast.Attribute, ast.Name)):
                            # Check if value is a call to a widget class
                            if isinstance(node.value, ast.Call):
                                func = node.value.func
                                widget_class = ""
                                if isinstance(func, ast.Attribute):
                                    widget_class = func.attr
                                elif isinstance(func, ast.Name):
                                    widget_class = func.id
                                
                                if widget_class in self.type_map or widget_class in ['Button', 'Label', 'Entry', 'Frame', 'Combobox', 'Checkbutton', 'Radiobutton']:
                                    # Store by widget class and some context
                                    name = target.attr if isinstance(target, ast.Attribute) else target.id
                                    
                                    # Try to extract 'text' keyword argument
                                    node_text = ""
                                    for kw in node.value.keywords:
                                        if kw.arg == 'text' and isinstance(kw.value, ast.Constant):
                                            node_text = str(kw.value.value)
                                        elif kw.arg == 'text' and isinstance(kw.value, ast.Str): # Support older python
                                            node_text = kw.value.s
                                            
                                    self.source_map[node.lineno] = {
                                        'name': name,
                                        'class': widget_class,
                                        'line': node.lineno,
                                        'text': node_text
                                    }
        except Exception as e:
            log(f"Source mapping failed: {e}", "ERROR")

    def scan_full(self) -> Dict[str, GUIElement]:
        """Perform complete GUI scan."""
        self.elements.clear()
        self.widget_map.clear()
        self.next_id = 1
        
        # Build source map
        self._map_source_lines()
        
        # Start with root window
        root_id = self._scan_widget(self.root, None)
        
        # Update parent references
        for elem in self.elements.values():
            if elem.parent:
                parent_elem = self.elements.get(elem.parent)
                if parent_elem and elem.uid not in parent_elem.children:
                    parent_elem.children.append(elem.uid)
        
        return self.elements

    def _find_source_for_widget(self, widget, widget_class: str, text: str) -> Dict[str, Any]:
        """Attempt to find source code line for a widget with better heuristics."""
        best_match = {'line': 0, 'name': 'unknown', 'class': widget_class}
        
        # Heuristics:
        # 1. Exact match for class AND text (high confidence)
        # 2. Match for class where text is in code
        # 3. Match for class only (fallback)
        
        matches = []
        for line, info in self.source_map.items():
            # Class match (allow for ttk variants)
            if info['class'] == widget_class or info['class'] == widget_class.replace('T', ''):
                score = 0
                if info.get('text') == text and text:
                    score += 100
                elif text and info.get('text') and text in info.get('text'):
                    score += 50
                
                matches.append((score, info))
        
        if matches:
            # Sort by score (desc) and then line number (to get consistent mapping if multiple same-text)
            matches.sort(key=lambda x: (x[0], -x[1]['line']), reverse=True)
            return matches[0][1]
        
        return best_match

    def _scan_widget(self, widget, parent_id: Optional[str]) -> str:
        """Recursively scan a widget."""
        widget_class = widget.winfo_class()
        element_type = self.type_map.get(widget_class, ElementType.FRAME)
        
        # Generate unique ID
        widget_id = f"{widget_class}_{self.next_id}"
        self.next_id += 1
        
        # Get geometry
        try:
            x = widget.winfo_x()
            y = widget.winfo_y()
            width = widget.winfo_width()
            height = widget.winfo_height()
        except:
            x = y = width = height = 0
        
        # Extract properties
        attrs = {}
        text = ""
        bg = fg = font = ""
        
        for prop in self.common_props:
            try:
                value = widget.cget(prop)
                if value and value not in ['', None, 'None', 'none']:
                    # Convert Tcl_Obj to string
                    value_str = str(value)
                    attrs[prop] = value_str
                    if prop == 'text':
                        text = value_str
                    elif prop == 'bg':
                        bg = value_str
                    elif prop == 'fg':
                        fg = value_str
                    elif prop == 'font':
                        font = value_str
            except:
                pass
        
        # Get widget-specific attributes
        widget_attrs = {}
        if hasattr(widget, 'keys'):
            try:
                for key in widget.keys():
                    try:
                        value = widget.cget(key)
                        if value and value not in ['', None, 'None', 'none']:
                            widget_attrs[key] = str(value)
                    except:
                        pass
            except:
                pass
        
        # Find source info
        source_info = self._find_source_for_widget(widget, widget_class, text)
        
        # Create element
        element = GUIElement(
            uid=widget_id,
            etype=element_type,
            widget=widget,
            parent=parent_id,
            text=text,
            bg=bg,
            fg=fg,
            font=font,
            width=width,
            height=height,
            x=x,
            y=y,
            attrs={**attrs, **widget_attrs},
            source_info=source_info,
            line_number=source_info.get('line', 0)
        )
        
        self.elements[widget_id] = element
        self.widget_map[widget_id] = widget
        
        # Scan children
        try:
            for child in widget.winfo_children():
                child_id = self._scan_widget(child, widget_id)
                element.children.append(child_id)
        except:
            pass
        
        return widget_id

    def get_element_by_path(self, path: str) -> Optional[GUIElement]:
        """Find element by path string."""
        for elem in self.elements.values():
            elem_path = self.get_element_path(elem)
            if elem_path == path or elem.uid == path:
                return elem
        return None

    def get_element_path(self, element: GUIElement) -> str:
        """Get hierarchical path for element."""
        path_parts = []
        current = element
        
        while current:
            path_parts.insert(0, f"{current.etype.value}:{current.uid}")
            if current.parent:
                current = self.elements.get(current.parent)
            else:
                current = None
        
        return " > ".join(path_parts)

    def get_summary(self) -> str:
        """Get human-readable GUI summary."""
        if not self.elements:
            return "No elements found"
        
        summary = []
        summary.append(f"GUI Elements: {len(self.elements)} total")
        
        # Count by type
        type_counts = defaultdict(int)
        for elem in self.elements.values():
            type_counts[elem.etype.value] += 1
        
        summary.append("By type:")
        for etype, count in sorted(type_counts.items()):
            summary.append(f"  {etype}: {count}")
        
        # List interactive elements
        interactive = []
        for elem in self.elements.values():
            if elem.etype in [ElementType.BUTTON, ElementType.ENTRY, 
                            ElementType.COMBOBOX, ElementType.CHECKBOX]:
                interactive.append(f"{elem.etype.value}: '{elem.text[:50]}'")
        
        if interactive:
            summary.append("\nInteractive elements:")
            summary.extend(f"  {elem}" for elem in interactive[:10])
            if len(interactive) > 10:
                summary.append(f"  ... and {len(interactive) - 10} more")
        
        return "\n".join(summary)

# ============================================================================
# CHANGE APPLIER
# ============================================================================

class ChangeApplier:
    """Applies changes to GUI elements."""
    
    def __init__(self, scanner: GUIScanner):
        self.scanner = scanner
        self.change_history = []
        
        # Action handlers
        self.handlers = {
            'config': self._handle_config,
            'create': self._handle_create,
            'destroy': self._handle_destroy,
            'bind': self._handle_bind,
            'unbind': self._handle_unbind,
            'move': self._handle_move,
            'resize': self._handle_resize,
            'rename': self._handle_rename,
            'show': self._handle_show,
            'hide': self._handle_hide,
            'enable': self._handle_enable,
            'disable': self._handle_disable
        }

    def apply_change(self, task: Dict) -> Tuple[bool, str]:
        """Apply a single change task."""
        try:
            action = task.get('action', 'config')
            handler = self.handlers.get(action)
            
            if not handler:
                return False, f"Unknown action: {action}"
            
            element_id = task.get('element', 'any')
            element = self._find_element(element_id)
            
            if not element and action != 'create':
                return False, f"Element not found: {element_id}"
            
            success, message = handler(element, task.get('params', {}))
            
            if success:
                self.change_history.append({
                    'task': task,
                    'timestamp': datetime.now().isoformat(),
                    'success': True
                })
                log(f"Applied change: {task.get('description', 'Unknown')}")
                self._register_trainer_event(action, element_id, task)

            return success, message
            
        except Exception as e:
            log(f"Change application failed: {e}", "ERROR")
            return False, str(e)

    def _register_trainer_event(self, action_type: str, element_id: str, task: Dict):
        """Bridge GUILLM actions into Trainer's enriched_changes pipeline."""
        try:
            import sys as _sys
            _sys.path.insert(0, str(BASE_DIR.parent.parent))
            import recovery_util
            recovery_util.register_event(
                file=str(Path(__file__).relative_to(BASE_DIR.parent.parent)),
                verb=action_type,
                risk_level="LOW",
                methods=[element_id],
                classes=["GUILLM_ChangeApplier"],
                additions=1,
                deletions=0,
            )
        except Exception:
            pass  # Non-critical — don't break GUILLM if trainer pipeline unavailable

    def _find_element(self, element_spec: str) -> Optional[GUIElement]:
        """Find element by various specifications."""
        if element_spec == 'any':
            # Return first interactive element
            for elem in self.scanner.elements.values():
                if elem.etype in [ElementType.BUTTON, ElementType.LABEL]:
                    return elem
            # Or any element
            return next(iter(self.scanner.elements.values()), None)
        
        # Find by exact ID
        if element_spec in self.scanner.elements:
            return self.scanner.elements[element_spec]
        
        # Find by type pattern (find:type:label)
        if element_spec.startswith('find:'):
            _, etype, *rest = element_spec.split(':')
            etype = etype.lower()
            
            for elem in self.scanner.elements.values():
                if elem.etype.value.lower() == etype:
                    if not rest or (elem.text and rest[0].lower() in elem.text.lower()):
                        return elem
        
        return None

    def _handle_config(self, element: GUIElement, params: Dict) -> Tuple[bool, str]:
        """Configure element properties."""
        if not element or not element.widget:
            return False, "No element or widget"
        
        try:
            element.widget.config(**params)
            
            # Update element properties
            if 'text' in params:
                element.text = str(params['text'])
            if 'bg' in params:
                element.bg = str(params['bg'])
            if 'fg' in params:
                element.fg = str(params['fg'])
            if 'font' in params:
                element.font = str(params['font'])
            
            return True, f"Configured {element.etype.value}"
        except Exception as e:
            return False, f"Config failed: {e}"

    def _handle_create(self, element: GUIElement, params: Dict) -> Tuple[bool, str]:
        """Create new element."""
        parent = self.scanner.root
        parent_id = None
        
        # Find parent if specified
        parent_spec = params.get('parent', 'root')
        if parent_spec != 'root':
            parent_elem = self._find_element(parent_spec)
            if parent_elem and parent_elem.widget:
                parent = parent_elem.widget
                parent_id = parent_elem.uid
        
        etype = params.get('type', 'Button').lower()
        widget = None
        
        try:
            if etype == 'button':
                widget = tk.Button(parent, text=params.get('text', 'New Button'))
                widget.pack(pady=5)
            elif etype == 'label':
                widget = tk.Label(parent, text=params.get('text', 'New Label'))
                widget.pack(pady=5)
            elif etype == 'entry':
                widget = tk.Entry(parent)
                widget.pack(pady=5)
                widget.insert(0, params.get('text', ''))
            elif etype == 'frame':
                widget = tk.Frame(parent, bg=params.get('bg', ''))
                widget.pack(pady=5, fill='both', expand=True)
            else:
                return False, f"Unknown type: {etype}"
            
            # Apply additional config
            if widget and 'config' in params:
                widget.config(**params['config'])
            
            # Rescan to include new element
            self.scanner.scan_full()
            
            return True, f"Created {etype}"
        except Exception as e:
            return False, f"Create failed: {e}"

    def _handle_destroy(self, element: GUIElement, params: Dict) -> Tuple[bool, str]:
        """Destroy element."""
        if not element or not element.widget:
            return False, "No element to destroy"
        
        try:
            element.widget.destroy()
            # Remove from scanner
            if element.uid in self.scanner.elements:
                del self.scanner.elements[element.uid]
            if element.uid in self.scanner.widget_map:
                del self.scanner.widget_map[element.uid]
            
            return True, f"Destroyed {element.etype.value}"
        except Exception as e:
            return False, f"Destroy failed: {e}"

    def _handle_bind(self, element: GUIElement, params: Dict) -> Tuple[bool, str]:
        """Bind event to element."""
        if not element or not element.widget:
            return False, "No element for binding"
        
        event = params.get('event', '<Button-1>')
        command_str = params.get('command', '')
        
        try:
            if command_str.startswith('lambda'):
                command = eval(command_str)
            else:
                command = eval(f"lambda e: {command_str}")
            
            element.widget.bind(event, command)
            return True, f"Bound {event} to {element.etype.value}"
        except Exception as e:
            return False, f"Bind failed: {e}"

    def _handle_unbind(self, element: GUIElement, params: Dict) -> Tuple[bool, str]:
        """Unbind event from element."""
        if not element or not element.widget:
            return False, "No element for unbinding"
        
        event = params.get('event', '<Button-1>')
        
        try:
            element.widget.unbind(event)
            return True, f"Unbound {event} from {element.etype.value}"
        except Exception as e:
            return False, f"Unbind failed: {e}"

    def _handle_move(self, element: GUIElement, params: Dict) -> Tuple[bool, str]:
        """Move element."""
        # Tkinter doesn't have direct move for packed widgets
        # This would require using place geometry manager
        return False, "Move not implemented (use place geometry)"

    def _handle_resize(self, element: GUIElement, params: Dict) -> Tuple[bool, str]:
        """Resize element."""
        if not element or not element.widget:
            return False, "No element to resize"
        
        width = params.get('width')
        height = params.get('height')
        
        try:
            if width:
                element.widget.config(width=width)
                element.width = width
            if height:
                element.widget.config(height=height)
                element.height = height
            
            return True, f"Resized {element.etype.value}"
        except Exception as e:
            return False, f"Resize failed: {e}"

    def _handle_rename(self, element: GUIElement, params: Dict) -> Tuple[bool, str]:
        """Rename element (change text/label)."""
        return self._handle_config(element, {'text': params.get('name', 'Renamed')})

    def _handle_show(self, element: GUIElement, params: Dict) -> Tuple[bool, str]:
        """Show hidden element."""
        return self._handle_config(element, {'state': 'normal'})

    def _handle_hide(self, element: GUIElement, params: Dict) -> Tuple[bool, str]:
        """Hide element."""
        return self._handle_config(element, {'state': 'hidden'})

    def _handle_enable(self, element: GUIElement, params: Dict) -> Tuple[bool, str]:
        """Enable element."""
        return self._handle_config(element, {'state': 'normal'})

    def _handle_disable(self, element: GUIElement, params: Dict) -> Tuple[bool, str]:
        """Disable element."""
        return self._handle_config(element, {'state': 'disabled'})

# ============================================================================
# PROFILE SYSTEM
# ============================================================================

class ProfileManager:
    """Manages GUI element profiles and schemas."""
    
    def __init__(self):
        self.profiles = self._load_profiles()
        self.schemas = self._build_schemas()
        
    def _load_profiles(self) -> Dict[str, Dict]:
        """Load profiles from files."""
        profiles = {}
        
        # Default profiles
        default_profiles = {
            'button': {
                'type': 'button',
                'properties': ['text', 'command', 'state', 'bg', 'fg', 'font', 'width', 'height'],
                'methods': ['config', 'bind', 'unbind', 'pack', 'grid', 'place', 'destroy'],
                'events': ['<Button-1>', '<ButtonRelease-1>', '<Enter>', '<Leave>'],
                'defaults': {'bg': 'SystemButtonFace', 'fg': 'SystemButtonText'},
                'tools': []
            },
            'label': {
                'type': 'label',
                'properties': ['text', 'bg', 'fg', 'font', 'width', 'height', 'justify', 'anchor'],
                'methods': ['config', 'pack', 'grid', 'place', 'destroy'],
                'events': [],
                'defaults': {},
                'tools': []
            },
            'tab': {
                'type': 'tab',
                'properties': ['text', 'state', 'compound', 'image'],
                'methods': ['add', 'delete', 'tab', 'forget', 'destroy'],
                'events': ['<<NotebookTabChanged>>'],
                'defaults': {},
                'tools': []
            },
            'panel': {
                'type': 'panel',
                'properties': ['width', 'height', 'bg', 'relief', 'borderwidth'],
                'methods': ['pack', 'grid', 'place', 'destroy', 'lift', 'lower'],
                'events': [],
                'defaults': {},
                'tools': []
            },
            'menu': {
                'type': 'menu',
                'properties': ['tearoff', 'bg', 'fg', 'font'],
                'methods': ['add_command', 'add_cascade', 'add_separator', 'delete'],
                'events': [],
                'defaults': {},
                'tools': []
            }
        }
        
        # Try to load from files
        for profile_file in PROF_DIR.glob("*.json"):
            try:
                with open(profile_file, 'r', encoding='utf-8') as f:
                    profile_data = json.load(f)
                    profile_name = profile_file.stem
                    profiles[profile_name] = profile_data
            except:
                pass
        
        # Merge with defaults
        for name, profile in default_profiles.items():
            if name not in profiles:
                profiles[name] = profile
        
        return profiles
    
    def _build_schemas(self) -> Dict[str, Dict]:
        """Build tool schemas for LLM interactions."""
        schemas = {}
        
        for name, profile in self.profiles.items():
            schema = {
                'type': profile['type'],
                'description': f"{name.title()} GUI element",
                'properties': profile['properties'],
                'actions': profile['methods'],
                'events': profile.get('events', []),
                'defaults': profile.get('defaults', {}),
                'examples': self._get_examples(name)
            }
            schemas[name] = schema
        
        return schemas
    
    def _get_examples(self, element_type: str) -> List[str]:
        """Get example modifications for element type."""
        examples = {
            'button': [
                "Change button color to blue",
                "Make button say 'Submit'",
                "Increase button size",
                "Disable the button",
                "Add click event handler"
            ],
            'label': [
                "Change label text",
                "Make label bold",
                "Change label background",
                "Add border to label",
                "Center-align text"
            ],
            'tab': [
                "Rename tab to 'Settings'",
                "Add new tab",
                "Remove tab",
                "Change tab order",
                "Add icon to tab"
            ],
            'panel': [
                "Resize panel",
                "Change panel color",
                "Add border",
                "Move panel",
                "Hide panel"
            ],
            'menu': [
                "Add menu item",
                "Change menu color",
                "Add submenu",
                "Remove menu item",
                "Add keyboard shortcut"
            ]
        }
        return examples.get(element_type, [])
    
    def get_schema(self, element_type: str) -> Optional[Dict]:
        """Get schema for element type."""
        return self.schemas.get(element_type.lower())
    
    def list_profiles(self) -> List[str]:
        """List all available profiles."""
        return list(self.schemas.keys())

    def save_element_profile(self, element: GUIElement):
        """Save specialized profile for a single element."""
        try:
            elem_prof_dir = PROF_DIR / "elements"
            elem_prof_dir.mkdir(exist_ok=True)
            
            profile = {
                'uid': element.uid,
                'etype': element.etype.value,
                'source_info': element.source_info,
                'line_number': element.line_number,
                'text': element.text,
                'attrs': element.attrs,
                'timestamp': datetime.now().isoformat()
            }
            
            path = elem_prof_dir / f"{element.uid}.json"
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(profile, f, indent=2)
                
        except Exception as e:
            log(f"Failed to save element profile: {e}", "ERROR")

# ============================================================================
# MAIN APPLICATION
# ============================================================================

class GUILLMApp:
    """Main GUILLM application."""
    
    def __init__(self, root: tk.Tk, model: str = None, cli_mode: bool = False):
        self.root = root
        self.root.title(f"GUILLM v{VERSION}")
        self.root.geometry("1200x800")
        
        # Core components
        self.ollama = OllamaManager()
        self.scanner = GUIScanner(root)
        self.applier = ChangeApplier(self.scanner)
        self.profiles = ProfileManager()
        
        # State
        self.mode = "chat"  # chat, plan, execute, diff
        self.current_model = model or self.ollama.current_model or "llama2"
        self.change_plan: List[ChangeTask] = []
        self.current_task = 0
        self.snapshots: List[Snapshot] = []
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.chat_history = []
        
        # Context Management
        self.show_context_var = tk.BooleanVar(value=False)
        self.selected_context_elements = []
        self.system_prompts = {
            "chat": "You are a helpful GUI assistant.",
            "plan": "You are a GUI architect. Generate JSON plans for changes.",
            "execute": "You are a GUI operator. Execute the generated plan."
        }
        
        # GUI elements storage
        self.widgets = {}
        
        # Setup
        self._setup_gui()
        
        # Initial scan
        self.scanner.scan_full()
        
        # Bind global right-click for inspection
        self.root.bind_all("<Button-3>", self._on_right_click)
        
        # Take initial snapshot
        self.take_snapshot("initial")
        
        # Welcome message
        self.add_chat("System", f"GUILLM v{VERSION} started")
        self.add_chat("System", f"Models: {', '.join(self.ollama.models[:5])}")
        self.add_chat("System", "Try: 'Make buttons blue' or 'Add status label'")
        
        # CLI mode handling
        if cli_mode:
            self.root.withdraw()

    # ------------------------------------------------------------------
    # EMBEDDED MODE — for use inside the Project Factory
    # ------------------------------------------------------------------

    @classmethod
    def create_embedded(cls, parent_frame, root, ollama, scanner, applier, profiles, project_id="embedded"):
        """Create a GUILLMApp embedded inside an existing frame (no new Tk window).

        This is the entry point for the Project Factory. Instead of creating
        a new tk.Tk(), it builds all GUILLM UI elements inside parent_frame.

        Args:
            parent_frame: ttk.Frame to build inside
            root: the application's tk.Tk() root (for dialogs, after(), etc.)
            ollama: pre-configured OllamaManager instance
            scanner: pre-configured GUIScanner instance
            applier: pre-configured ChangeApplier instance
            profiles: pre-configured ProfileManager instance
            project_id: string identifier for this project

        Returns:
            GUILLMApp instance (embedded mode)
        """
        instance = cls.__new__(cls)

        # Core components (pre-built, isolated per project)
        instance.root = root
        instance.ollama = ollama
        instance.scanner = scanner
        instance.applier = applier
        instance.profiles = profiles

        # State — mirrors __init__ exactly
        instance.mode = "chat"
        instance.current_model = ollama.current_model or "llama2"
        instance.change_plan: List[ChangeTask] = []
        instance.current_task = 0
        instance.snapshots: List[Snapshot] = []
        instance.session_id = f"{project_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        instance.chat_history = []
        instance.show_context_var = tk.BooleanVar(value=False)
        instance.selected_context_elements = []
        instance.system_prompts = {
            "chat": "You are a helpful GUI assistant.",
            "plan": "You are a GUI architect. Generate JSON plans for changes.",
            "execute": "You are a GUI operator. Execute the generated plan."
        }
        instance.widgets = {}
        instance._embedded = True
        instance._parent_frame = parent_frame

        # Big Bang 4A: Route active task context into system prompt
        try:
            _sync_path = Path(__file__).parent.parent.parent.parent.parent / "plans" / "Refs" / "latest_sync.json"
            if _sync_path.exists():
                _sync = json.loads(_sync_path.read_text(encoding='utf-8'))
                _active = [(tid, t) for tid, t in _sync.get("tasks", {}).items()
                           if (t.get("status") or "").upper() in ("READY", "IN_PROGRESS")]
                if _active:
                    _ctx_lines = [f"\n\nActive tasks ({len(_active)}):"]
                    for _tid, _t in _active[:5]:
                        _ctx_lines.append(f"- {_tid}: {_t.get('title','')} ({_t.get('wherein','')})")
                    instance.system_prompts["chat"] += "".join(_ctx_lines)
        except Exception:
            pass

        # Build GUI into the parent frame
        instance._setup_gui_embedded(parent_frame)

        # Deferred scan (widgets need to be drawn first)
        root.after(500, instance.scanner.scan_full)

        # Welcome
        instance.add_chat("System", f"Project [{project_id}] ready")
        instance.add_chat("System", f"Models: {', '.join(instance.ollama.models[:5])}")
        instance.add_chat("System", "Try: 'Make buttons blue' or 'Add status label'")

        return instance

    def _setup_gui_embedded(self, container):
        """Setup GUI inside an existing frame (embedded mode).

        Mirrors _setup_gui() but:
        - All widgets go into 'container' instead of self.root
        - No window title/geometry/bind_all (no global side effects)
        - No style.theme_use() (uses parent app's theme)
        """
        # Top toolbar
        toolbar = ttk.Frame(container)
        toolbar.pack(fill='x', padx=5, pady=5)

        # Model selector
        ttk.Label(toolbar, text="Model:").pack(side='left', padx=(0, 5))
        self.model_var = tk.StringVar(value=self.current_model)
        self.model_combo = ttk.Combobox(
            toolbar,
            textvariable=self.model_var,
            values=self.ollama.models,
            state='readonly',
            width=20
        )
        self.model_combo.pack(side='left', padx=(0, 10))
        self.model_combo.bind('<<ComboboxSelected>>', self._on_model_change)

        # Refresh models button
        ttk.Button(toolbar, text="Refresh", width=7,
                   command=self._refresh_models).pack(side='left', padx=(0, 5))

        # Snapshot button
        ttk.Button(toolbar, text="Snapshot",
                   command=lambda: self.take_snapshot("manual")).pack(side='left', padx=5)

        # Context button
        ttk.Button(toolbar, text="Context",
                   command=self._show_context_manager).pack(side='left', padx=5)

        # Mode selector
        self.mode_var = tk.StringVar(value=self.mode)
        mode_frame = ttk.Frame(toolbar)
        mode_frame.pack(side='left', padx=20)
        for mode in ["chat", "plan", "execute", "diff"]:
            ttk.Radiobutton(
                mode_frame, text=mode.title(),
                variable=self.mode_var, value=mode,
                command=lambda m=mode: self._switch_mode(m)
            ).pack(side='left', padx=2)

        # Main paned window
        main_pane = ttk.PanedWindow(container, orient='horizontal')
        main_pane.pack(fill='both', expand=True, padx=5, pady=(0, 5))

        # Left panel — Chat
        left_frame = ttk.Frame(main_pane)
        main_pane.add(left_frame, weight=2)

        chat_container = ttk.LabelFrame(left_frame, text="Chat", padding=10)
        chat_container.pack(fill='both', expand=True)

        self.chat_text = scrolledtext.ScrolledText(
            chat_container, wrap='word', font=('Consolas', 10), state='disabled'
        )
        self.chat_text.pack(fill='both', expand=True)

        # Input area
        input_frame = ttk.Frame(left_frame)
        input_frame.pack(fill='x', pady=(5, 0))

        self.input_var = tk.StringVar()
        self.input_entry = ttk.Entry(
            input_frame, textvariable=self.input_var, font=('Consolas', 10)
        )
        self.input_entry.pack(side='left', fill='x', expand=True, padx=(0, 5))
        self.input_entry.bind('<Return>', lambda e: self._process_input())

        ttk.Button(input_frame, text="Send",
                   command=self._process_input).pack(side='right')

        # Right panel — Info tabs
        right_frame = ttk.Frame(main_pane)
        main_pane.add(right_frame, weight=1)

        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill='both', expand=True)

        # Reuse existing tab setup methods — they all target self.notebook
        self._setup_elements_tab()
        self._setup_plan_tab()
        self._setup_diff_tab()
        self._setup_profiles_tab()

        # Status bar (in container, not root)
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(
            container, textvariable=self.status_var,
            relief='sunken', anchor='w'
        ).pack(side='bottom', fill='x')

    def _setup_gui(self):
        """Setup the GUI interface."""
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        
        # Top toolbar
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill='x', padx=5, pady=5)
        
        # Model selector
        ttk.Label(toolbar, text="Model:").pack(side='left', padx=(0, 5))
        self.model_var = tk.StringVar(value=self.current_model)
        self.model_combo = ttk.Combobox(
            toolbar, 
            textvariable=self.model_var,
            values=self.ollama.models,
            state='readonly',
            width=20
        )
        self.model_combo.pack(side='left', padx=(0, 10))
        self.model_combo.bind('<<ComboboxSelected>>', self._on_model_change)
        
        # Refresh models button
        ttk.Button(
            toolbar, 
            text="🔄", 
            width=3,
            command=self._refresh_models
        ).pack(side='left', padx=(0, 5))
        
        # Snapshot button
        ttk.Button(
            toolbar,
            text="📸 Snapshot",
            command=lambda: self.take_snapshot("manual")
        ).pack(side='left', padx=5)

        # Context button
        ttk.Button(
            toolbar,
            text="📦 Context",
            command=self._show_context_manager
        ).pack(side='left', padx=5)

        # Profile button
        ttk.Button(
            toolbar,
            text="👤 Profiles",
            command=self._show_profile_viewer
        ).pack(side='left', padx=5)
        
        # Mode selector
        self.mode_var = tk.StringVar(value=self.mode)
        mode_frame = ttk.Frame(toolbar)
        mode_frame.pack(side='left', padx=20)
        
        for mode in ["chat", "plan", "execute", "diff"]:
            btn = ttk.Radiobutton(
                mode_frame,
                text=mode.title(),
                variable=self.mode_var,
                value=mode,
                command=lambda m=mode: self._switch_mode(m)
            )
            btn.pack(side='left', padx=2)
        
        # Main paned window
        main_pane = ttk.PanedWindow(self.root, orient='horizontal')
        main_pane.pack(fill='both', expand=True, padx=5, pady=(0, 5))
        
        # Left panel - Chat
        left_frame = ttk.Frame(main_pane)
        main_pane.add(left_frame, weight=2)
        
        # Chat display
        chat_container = ttk.LabelFrame(left_frame, text="Chat", padding=10)
        chat_container.pack(fill='both', expand=True)
        
        self.chat_text = scrolledtext.ScrolledText(
            chat_container,
            wrap='word',
            font=('Consolas', 10),
            state='disabled'
        )
        self.chat_text.pack(fill='both', expand=True)
        
        # Input area
        input_frame = ttk.Frame(left_frame)
        input_frame.pack(fill='x', pady=(5, 0))
        
        self.input_var = tk.StringVar()
        self.input_entry = ttk.Entry(
            input_frame,
            textvariable=self.input_var,
            font=('Consolas', 10)
        )
        self.input_entry.pack(side='left', fill='x', expand=True, padx=(0, 5))
        self.input_entry.bind('<Return>', lambda e: self._process_input())
        
        ttk.Button(
            input_frame,
            text="Send",
            command=self._process_input
        ).pack(side='right')
        
        # Right panel - Info
        right_frame = ttk.Frame(main_pane)
        main_pane.add(right_frame, weight=1)
        
        # Notebook for different views
        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill='both', expand=True)
        
        # GUI Elements tab
        self._setup_elements_tab()
        
        # Plan tab
        self._setup_plan_tab()
        
        # Diff tab
        self._setup_diff_tab()
        
        # Profiles tab
        self._setup_profiles_tab()
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief='sunken',
            anchor='w'
        )
        status_bar.pack(side='bottom', fill='x')
    
    def _setup_elements_tab(self):
        """Setup GUI elements display tab."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Elements")
        
        # Treeview for elements
        columns = ('type', 'text', 'id')
        self.elements_tree = ttk.Treeview(
            frame,
            columns=columns,
            show='tree headings',
            selectmode='browse'
        )
        
        self.elements_tree.heading('#0', text='Element')
        self.elements_tree.heading('type', text='Type')
        self.elements_tree.heading('text', text='Text')
        self.elements_tree.heading('id', text='ID')
        
        self.elements_tree.column('#0', width=150)
        self.elements_tree.column('type', width=100)
        self.elements_tree.column('text', width=200)
        self.elements_tree.column('id', width=100)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=self.elements_tree.yview)
        self.elements_tree.configure(yscrollcommand=scrollbar.set)
        
        self.elements_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Control buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(5, 0))
        
        ttk.Button(
            btn_frame,
            text="Refresh",
            command=self._refresh_elements
        ).pack(side='left', padx=2)
        
        ttk.Button(
            btn_frame,
            text="Properties",
            command=self._show_element_properties
        ).pack(side='left', padx=2)
        
        ttk.Button(
            btn_frame,
            text="Modify",
            command=self._modify_selected_element
        ).pack(side='left', padx=2)
    
    def _setup_plan_tab(self):
        """Setup change plan display tab."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Plan")
        
        self.plan_text = scrolledtext.ScrolledText(
            frame,
            wrap='word',
            font=('Consolas', 9),
            state='disabled'
        )
        self.plan_text.pack(fill='both', expand=True)
        
        # Plan controls
        control_frame = ttk.Frame(frame)
        control_frame.pack(fill='x', pady=(5, 0))
        
        ttk.Button(
            control_frame,
            text="Execute Next",
            command=self._execute_next_task
        ).pack(side='left', padx=2)
        
        ttk.Button(
            control_frame,
            text="Execute All",
            command=self._execute_all_tasks
        ).pack(side='left', padx=2)
        
        ttk.Button(
            control_frame,
            text="Clear Plan",
            command=self._clear_plan
        ).pack(side='left', padx=2)
    
    def _setup_diff_tab(self):
        """Setup diff viewer tab."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Diff")
        
        self.diff_text = scrolledtext.ScrolledText(
            frame,
            wrap='word',
            font=('Consolas', 9),
            state='disabled'
        )
        self.diff_text.pack(fill='both', expand=True)
        
        # Diff controls
        control_frame = ttk.Frame(frame)
        control_frame.pack(fill='x', pady=(5, 0))
        
        ttk.Button(
            control_frame,
            text="Compare Snapshots",
            command=self._compare_snapshots
        ).pack(side='left', padx=2)
        
        ttk.Button(
            control_frame,
            text="Load Snapshot",
            command=self._load_snapshot
        ).pack(side='left', padx=2)
    
    def _setup_profiles_tab(self):
        """Setup profiles display tab."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Profiles")
        
        self.profiles_text = scrolledtext.ScrolledText(
            frame,
            wrap='word',
            font=('Consolas', 9),
            state='disabled'
        )
        self.profiles_text.pack(fill='both', expand=True)
        
        # Refresh profiles
        ttk.Button(
            frame,
            text="Refresh Profiles",
            command=self._refresh_profiles
        ).pack(pady=5)
    
    # ========================================================================
    # CORE FUNCTIONALITY
    # ========================================================================
    
    def add_chat(self, sender: str, message: str):
        """Add message to chat display."""
        self.chat_text.config(state='normal')
        self.chat_text.insert('end', f"\n{sender}: {message}\n")
        self.chat_text.see('end')
        self.chat_text.config(state='disabled')
        
        # Save to history
        self.chat_history.append({
            'time': datetime.now().strftime("%H:%M:%S"),
            'sender': sender,
            'message': message
        })
        
        # Save to session file
        session_file = SESS_DIR / f"session_{self.session_id}.txt"
        with open(session_file, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {sender}: {message}\n")
    
    def _process_input(self):
        """Process user input."""
        text = self.input_var.get().strip()
        if not text:
            return
        
        self.input_var.set("")
        self.add_chat("You", text)
        
        # Process based on mode
        if self.mode == "chat":
            threading.Thread(target=self._handle_chat, args=(text,), daemon=True).start()
        elif self.mode == "plan":
            self._handle_plan_input(text)
        elif self.mode == "execute":
            self._handle_execute_input(text)
    
    def _handle_chat(self, text: str):
        """Handle chat mode input."""
        self.status_var.set("Thinking...")
        
        # First, analyze if GUI changes are needed
        gui_summary = self.scanner.get_summary()
        analysis = self.ollama.analyze_gui_request(gui_summary, text)
        
        self.add_chat("System", f"Analysis: {analysis.get('change_type', 'unknown')} change")
        
        if analysis.get('needs_gui_change', False):
            if analysis.get('should_plan', False) or analysis.get('complexity', 'simple') != 'simple':
                # Switch to plan mode
                self.add_chat("System", "Creating detailed change plan...")
                self._switch_mode("plan")
                self._create_change_plan(text)
            else:
                # Apply directly
                self.add_chat("System", "Applying changes...")
                self._apply_direct_changes(text, analysis)
        else:
            # Regular chat response
            context = self._get_current_context()
            full_prompt = f"Context Elements:\n{context}\n\nUser: {text}" if context else text
            
            # Show context in chat if enabled
            if self.show_context_var.get() and context:
                self.add_chat("Context", f"Included: {', '.join(self.selected_context_elements)}")

            response = self.ollama.generate(
                full_prompt,
                system=self.system_prompts.get("chat", "You are a helpful assistant."),
                model=self.current_model
            )
            self.add_chat("Assistant", response)
        
        self.status_var.set("Ready")
    
    def _create_change_plan(self, request: str):
        """Create change plan from request."""
        # Get GUI manifest
        elements_dict = {uid: elem.to_dict() for uid, elem in self.scanner.elements.items()}
        manifest = json.dumps(elements_dict, indent=2)
        
        # Add context to request
        context = self._get_current_context()
        full_request = f"Relevant Context:\n{context}\n\nUser Request: {request}" if context else request

        # Generate plan
        tasks_data = self.ollama.generate_change_plan(
            manifest, 
            full_request,
            system=self.system_prompts.get("plan")
        )
        
        # Convert to ChangeTask objects
        self.change_plan.clear()
        for task_data in tasks_data:
            task = ChangeTask(
                id=task_data.get('id', len(self.change_plan) + 1),
                description=task_data.get('description', 'Unknown task'),
                element_id=task_data.get('element', 'any'),
                action=task_data.get('action', 'config'),
                params=task_data.get('params', {}),
                depends_on=task_data.get('depends_on', [])
            )
            self.change_plan.append(task)
        
        # Update plan display
        self._update_plan_display()
        
        self.add_chat("System", f"Created plan with {len(self.change_plan)} tasks")
        self.add_chat("System", "Switch to Execute mode to run tasks")
    
    def _apply_direct_changes(self, request: str, analysis: Dict):
        """Apply changes directly without detailed plan."""
        # Take snapshot before changes
        self.take_snapshot("before_direct")
        
        # Apply based on analysis
        suggested = analysis.get('suggested_actions', [])
        elements = analysis.get('elements_involved', ['button', 'label'])
        change_type = analysis.get('change_type', 'modify')
        
        success_count = 0
        for elem_type in elements:
            # Find elements of this type
            for elem in self.scanner.elements.values():
                if elem.etype.value == elem_type:
                    # Apply simple change
                    if change_type == "color":
                        elem.widget.config(bg="lightblue")
                        success_count += 1
                    elif change_type == "text":
                        elem.widget.config(text=f"Modified: {request[:20]}")
                        success_count += 1
        
        # Take snapshot after changes
        self.take_snapshot("after_direct")
        
        self.add_chat("System", f"Applied changes to {success_count} elements")
        self._refresh_elements()
    
    def _switch_mode(self, new_mode: str):
        """Switch application mode."""
        old_mode = self.mode
        self.mode = new_mode
        self.mode_var.set(new_mode)
        
        self.add_chat("System", f"Mode changed: {old_mode} → {new_mode}")
        
        # Mode-specific setup
        if new_mode == "plan":
            self._refresh_profiles()
        elif new_mode == "diff":
            self._refresh_diff_view()
    
    def _on_right_click(self, event):
        """Handle right-click for element inspection."""
        widget = event.widget
        # Find which element this widget belongs to
        target_uid = None
        for uid, w in self.scanner.widget_map.items():
            if w == widget:
                target_uid = uid
                break
        
        if target_uid:
            element = self.scanner.elements.get(target_uid)
            if element:
                self._show_inspector(element)

    def _show_context_manager(self):
        """Show context management window with tabs."""
        ctx_win = tk.Toplevel(self.root)
        ctx_win.title("Context & System Manager")
        ctx_win.geometry("600x700")
        
        nb = ttk.Notebook(ctx_win)
        nb.pack(fill='both', expand=True, padx=5, pady=5)
        
        # --- TAB 1: ELEMENTS ---
        elem_tab = ttk.Frame(nb)
        nb.add(elem_tab, text="Elements")
        
        ttk.Checkbutton(
            elem_tab, 
            text="Show per-turn context in output panel",
            variable=self.show_context_var
        ).pack(anchor='w', padx=10, pady=10)
        
        selector_frame = ttk.LabelFrame(elem_tab, text="Model Context Elements")
        selector_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        list_frame = ttk.Frame(selector_frame)
        list_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.ctx_listbox = tk.Listbox(list_frame, selectmode='multiple')
        self.ctx_listbox.pack(side='left', fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.ctx_listbox.yview)
        scrollbar.pack(side='right', fill='y')
        self.ctx_listbox.config(yscrollcommand=scrollbar.set)
        
        for uid, elem in self.scanner.elements.items():
            self.ctx_listbox.insert('end', f"{uid} ({elem.etype.value})")
            if uid in self.selected_context_elements:
                self.ctx_listbox.selection_set(self.ctx_listbox.size()-1)

        # --- TAB 2: PROMPTS ---
        prompt_tab = ttk.Frame(nb)
        nb.add(prompt_tab, text="System Prompts")
        
        prompt_editors = {}
        for mode in ["chat", "plan", "execute"]:
            frame = ttk.LabelFrame(prompt_tab, text=f"{mode.title()} System Prompt")
            frame.pack(fill='x', padx=10, pady=5)
            
            text_area = scrolledtext.ScrolledText(frame, height=4)
            text_area.pack(fill='x', padx=5, pady=5)
            text_area.insert('1.0', self.system_prompts.get(mode, ""))
            prompt_editors[mode] = text_area

        # --- TAB 3: TOOLS (SHELL) ---
        tools_tab = ttk.Frame(nb)
        nb.add(tools_tab, text="Tools (Shell)")
        
        ttk.Label(tools_tab, text="Per-Profile Tools (JSON format)").pack(padx=10, pady=5)
        tools_text = scrolledtext.ScrolledText(tools_tab, height=15)
        tools_text.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Load tools from profiles
        tools_config = {}
        for name, profile in self.profiles.profiles.items():
            if profile.get('tools'):
                tools_config[name] = profile['tools']
        tools_text.insert('1.0', json.dumps(tools_config, indent=2))

        def save_all():
            # Save Elements
            selected_indices = self.ctx_listbox.curselection()
            self.selected_context_elements = [self.ctx_listbox.get(i).split(' ')[0] for i in selected_indices]
            
            # Save Prompts
            for mode, editor in prompt_editors.items():
                self.system_prompts[mode] = editor.get('1.0', 'end-1c').strip()
            
            # Save Tools
            try:
                new_tools = json.loads(tools_text.get('1.0', 'end-1c'))
                for name, cmd_list in new_tools.items():
                    if name in self.profiles.profiles:
                        self.profiles.profiles[name]['tools'] = cmd_list
                self.add_chat("System", "Settings and Tools updated.")
            except Exception as e:
                messagebox.showerror("Error", f"Invalid Tools JSON: {e}")
                return

            ctx_win.destroy()
            
        ttk.Button(ctx_win, text="Save All Settings", command=save_all).pack(pady=10)

    def _get_current_context(self) -> str:
        """Compile selected context into string."""
        if not self.selected_context_elements:
            return ""
            
        ctx_data = {}
        for uid in self.selected_context_elements:
            if uid in self.scanner.elements:
                ctx_data[uid] = self.scanner.elements[uid].to_dict()
                
        return json.dumps(ctx_data, indent=2)

    def _show_profile_viewer(self, selected_uid: str = None):
        """Show unified profile and feature explorer."""
        prof_win = tk.Toplevel(self.root)
        prof_win.title("Feature Profile Explorer")
        prof_win.geometry("900x700")
        
        main_pane = ttk.PanedWindow(prof_win, orient='horizontal')
        main_pane.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Left: List of features/elements
        list_frame = ttk.Frame(main_pane)
        main_pane.add(list_frame, weight=1)
        
        ttk.Label(list_frame, text="Discovered Features").pack(pady=5)
        lb = tk.Listbox(list_frame)
        lb.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Right: Detail view
        detail_frame = ttk.Frame(main_pane)
        main_pane.add(detail_frame, weight=3)
        
        detail_text = scrolledtext.ScrolledText(detail_frame, font=('Consolas', 10))
        detail_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Map for lookup
        items = []
        select_idx = -1
        for uid, elem in self.scanner.elements.items():
            resolved_name = elem.source_info.get('name', 'unknown')
            display_str = f"{resolved_name} [{uid}] ({elem.etype.value})"
            lb.insert('end', display_str)
            items.append(elem)
            if selected_uid and uid == selected_uid:
                select_idx = len(items) - 1
            
        def on_select(event):
            if not lb.curselection(): return
            idx = lb.curselection()[0]
            elem = items[idx]
            
            detail_text.config(state='normal')
            detail_text.delete('1.0', 'end')
            
            # 1. Header & Resolved Name
            detail_text.insert('end', f"FEATURE PROFILE: {elem.uid}\n", "header")
            detail_text.insert('end', f"Resolved Name (Code): {elem.source_info.get('name', 'unknown')}\n", "bold")
            detail_text.insert('end', f"Type: {elem.etype.value}\n\n")
            
            # 2. Specifications
            detail_text.insert('end', "SPECIFICATIONS:\n", "header")
            for k, v in elem.to_dict().items():
                if k not in ['attrs', 'source_info', 'children']:
                    detail_text.insert('end', f"  {k}: {v}\n")
            
            detail_text.insert('end', "\nATTRIBUTES:\n", "header")
            for k, v in elem.attrs.items():
                if v: detail_text.insert('end', f"  {k}: {v}\n")
            
            # 3. Dependency Chain (Source Context)
            detail_text.insert('end', "\nDEPENDENCY CHAIN (Source Context):\n", "header")
            if elem.line_number > 0:
                try:
                    with open(__file__, 'r') as f:
                        lines = f.readlines()
                        start = max(0, elem.line_number - 15)
                        end = min(len(lines), elem.line_number + 15)
                        
                        for i, line in enumerate(lines[start:end], start + 1):
                            prefix = ">>> " if i == elem.line_number else f"{i:3}: "
                            detail_text.insert('end', f"{prefix}{line}")
                except Exception as e:
                    detail_text.insert('end', f"Error reading source: {e}\n")
            else:
                detail_text.insert('end', "No source mapping available.\n")
                
            detail_text.config(state='disabled')

        lb.bind('<<ListboxSelect>>', on_select)
        
        # Tags for styling
        detail_text.tag_config("header", font=('Consolas', 12, 'bold'), foreground="#0055ff")
        detail_text.tag_config("bold", font=('Consolas', 10, 'bold'))
        
        # Pre-select if requested
        if select_idx >= 0:
            lb.selection_set(select_idx)
            lb.see(select_idx)
            on_select(None)
            
        # Copy button
        def copy_uid():
            if not lb.curselection(): return
            idx = lb.curselection()[0]
            uid = items[idx].uid
            self.root.clipboard_clear()
            self.root.clipboard_append(uid)
            self.add_chat("System", f"Copied UID {uid} to clipboard")
            
        ttk.Button(detail_frame, text="Copy UID", command=copy_uid).pack(pady=5)

    def _show_inspector(self, element: GUIElement):
        """Show inspector window for an element."""
        inspect_win = tk.Toplevel(self.root)
        inspect_win.title(f"Inspector - {element.uid}")
        inspect_win.geometry("600x500")
        
        # Info panel
        info_frame = ttk.LabelFrame(inspect_win, text="Element Details")
        info_frame.pack(fill='x', padx=10, pady=5)
        
        details = [
            f"UID: {element.uid}",
            f"Type: {element.etype.value}",
            f"Text: {element.text}",
            f"Line: {element.line_number}",
            f"Source Name: {element.source_info.get('name', 'unknown')}"
        ]
        
        for d in details:
            ttk.Label(info_frame, text=d).pack(anchor='w', padx=5)

        # Code panel
        code_frame = ttk.LabelFrame(inspect_win, text="Source Context")
        code_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        code_text = scrolledtext.ScrolledText(code_frame, height=15)
        code_text.pack(fill='both', expand=True)
        
        # Load source context
        if element.line_number > 0:
            try:
                with open(__file__, 'r') as f:
                    lines = f.readlines()
                    start = max(0, element.line_number - 10)
                    end = min(len(lines), element.line_number + 10)
                    
                    context = "".join(lines[start:end])
                    code_text.insert('1.0', context)
                    
                    # Highlight the line
                    rel_line = element.line_number - start
                    code_text.tag_add("highlight", f"{rel_line}.0", f"{rel_line}.end")
                    code_text.tag_config("highlight", background="yellow", foreground="black")
            except Exception as e:
                code_text.insert('1.0', f"Failed to load source: {e}")
        else:
            code_text.insert('1.0', "Source line not found.")

        # Buttons
        btn_frame = ttk.Frame(inspect_win)
        btn_frame.pack(fill='x', padx=10, pady=5)
        
        def copy_code():
            self.root.clipboard_clear()
            self.root.clipboard_append(code_text.get('1.0', 'end-1c'))
            self.add_chat("System", f"Copied context for {element.uid} to clipboard")

        def push_to_context():
            if element.uid not in self.selected_context_elements:
                self.selected_context_elements.append(element.uid)
                self.add_chat("System", f"Added {element.uid} to model context")
            else:
                self.add_chat("System", f"{element.uid} is already in context")

        def open_profile():
            inspect_win.destroy()
            self._show_profile_viewer(selected_uid=element.uid)

        def copy_name():
            name = element.source_info.get('name', 'unknown')
            self.root.clipboard_clear()
            self.root.clipboard_append(name)
            self.add_chat("System", f"Copied resolved name '{name}' to clipboard")
        
        ttk.Button(btn_frame, text="Copy Context", command=copy_code).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Copy Name", command=copy_name).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Push to Context", command=push_to_context).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="View Profile", command=open_profile).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Close", command=inspect_win.destroy).pack(side='right', padx=2)

    def _save_element_profiles(self):
        """Save profiles for all scanned elements."""
        for element in self.scanner.elements.values():
            self.profiles.save_element_profile(element)
        self.add_chat("System", f"Saved {len(self.scanner.elements)} element profiles")

    def take_snapshot(self, name: str = ""):
        """Take snapshot of current GUI state."""
        # Rescan to get current state
        self.scanner.scan_full()
        
        # Prepare elements data
        elements_data = {}
        for uid, elem in self.scanner.elements.items():
            elements_data[uid] = elem.to_dict()
        
        # Create snapshot
        snapshot = Snapshot(
            timestamp=datetime.now().isoformat(),
            name=name or f"snapshot_{len(self.snapshots) + 1}",
            elements=elements_data,
            metadata={
                'mode': self.mode,
                'model': self.current_model,
                'elements_count': len(elements_data)
            }
        )
        
        # Save to file
        filename = f"snap_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{name or 'auto'}.json"
        filepath = SNAP_DIR / filename
        snapshot.save(filepath)
        
        # Take snapshot
        self.snapshots.append(snapshot)
        log(f"Snapshot taken: {name}")
        
        # Save element profiles
        self._save_element_profiles()
        
        return snapshot
    
    # ========================================================================
    # GUI UPDATERS
    # ========================================================================
    
    def _refresh_elements(self):
        """Refresh elements tree display."""
        self.scanner.scan_full()
        
        # Clear tree
        for item in self.elements_tree.get_children():
            self.elements_tree.delete(item)
        
        # Add elements hierarchically
        def add_element(elem: GUIElement, parent=""):
            item_id = self.elements_tree.insert(
                parent,
                'end',
                text=elem.etype.value,
                values=(elem.etype.value, elem.text[:50], elem.uid)
            )
            
            for child_id in elem.children:
                child_elem = self.scanner.elements.get(child_id)
                if child_elem:
                    add_element(child_elem, item_id)
        
        # Start with root elements (no parent)
        for elem in self.scanner.elements.values():
            if not elem.parent:
                add_element(elem)
    
    def _update_plan_display(self):
        """Update plan display."""
        self.plan_text.config(state='normal')
        self.plan_text.delete(1.0, 'end')
        
        if not self.change_plan:
            self.plan_text.insert('end', "No change plan\n")
        else:
            for task in self.change_plan:
                status_icon = {
                    'pending': '○',
                    'running': '▶',
                    'completed': '✓',
                    'failed': '✗',
                    'skipped': '»'
                }.get(task.status, '?')
                
                self.plan_text.insert('end', 
                    f"{status_icon} Task {task.id}: {task.description}\n"
                    f"    Element: {task.element_id}\n"
                    f"    Action: {task.action}\n"
                    f"    Params: {json.dumps(task.params, indent=4)}\n"
                    f"    Status: {task.status}\n"
                )
                if task.output:
                    self.plan_text.insert('end', f"    Output: {task.output}\n")
                self.plan_text.insert('end', "-" * 50 + "\n")
        
        self.plan_text.config(state='disabled')
    
    def _refresh_profiles(self):
        """Refresh profiles display."""
        self.profiles_text.config(state='normal')
        self.profiles_text.delete(1.0, 'end')
        
        profiles = self.profiles.list_profiles()
        for profile_name in profiles:
            schema = self.profiles.get_schema(profile_name)
            if schema:
                self.profiles_text.insert('end',
                    f"Profile: {profile_name}\n"
                    f"Description: {schema['description']}\n"
                    f"Properties: {', '.join(schema['properties'][:5])}...\n"
                    f"Actions: {', '.join(schema['actions'][:5])}...\n"
                    f"Examples:\n"
                )
                for example in schema.get('examples', [])[:3]:
                    self.profiles_text.insert('end', f"  • {example}\n")
                self.profiles_text.insert('end', "\n")
        
        self.profiles_text.config(state='disabled')
    
    def _refresh_diff_view(self):
        """Refresh diff viewer."""
        self.diff_text.config(state='normal')
        self.diff_text.delete(1.0, 'end')
        
        if len(self.snapshots) < 2:
            self.diff_text.insert('end', "Need at least 2 snapshots to compare\n")
        else:
            snap1 = self.snapshots[-2]
            snap2 = self.snapshots[-1]
            
            self.diff_text.insert('end',
                f"Comparing:\n"
                f"  {snap1.name} ({snap1.timestamp})\n"
                f"  {snap2.name} ({snap2.timestamp})\n\n"
            )
            
            # Count differences
            count1 = len(snap1.elements)
            count2 = len(snap2.elements)
            
            if count1 != count2:
                self.diff_text.insert('end', f"Element count changed: {count1} → {count2}\n")
            
            # Check for specific changes
            changed_elements = []
            for uid, elem1 in snap1.elements.items():
                elem2 = snap2.elements.get(uid)
                if elem2 and elem1 != elem2:
                    changed_elements.append(uid)
            
            if changed_elements:
                self.diff_text.insert('end', f"\nChanged elements ({len(changed_elements)}):\n")
                for uid in changed_elements[:10]:
                    self.diff_text.insert('end', f"  {uid}\n")
                if len(changed_elements) > 10:
                    self.diff_text.insert('end', f"  ... and {len(changed_elements) - 10} more\n")
        
        self.diff_text.config(state='disabled')
    
    # ========================================================================
    # EVENT HANDLERS
    # ========================================================================
    
    def _on_model_change(self, event=None):
        """Handle model change."""
        self.current_model = self.model_var.get()
        self.ollama.current_model = self.current_model
        self.add_chat("System", f"Model changed to: {self.current_model}")
    
    def _refresh_models(self):
        """Refresh model list."""
        models = self.ollama.refresh_models()
        self.model_combo['values'] = models
        if models and self.current_model not in models:
            self.current_model = models[0]
            self.model_var.set(self.current_model)
        self.add_chat("System", f"Refreshed models: {len(models)} available")
    
    def _show_element_properties(self):
        """Show properties of selected element."""
        selection = self.elements_tree.selection()
        if not selection:
            return
        
        item = self.elements_tree.item(selection[0])
        elem_id = item['values'][2]
        
        elem = self.scanner.elements.get(elem_id)
        if elem:
            props = json.dumps(elem.to_dict(), indent=2)
            messagebox.showinfo(f"Element: {elem_id}", props)
    
    def _modify_selected_element(self):
        """Open dialog to modify selected element."""
        selection = self.elements_tree.selection()
        if not selection:
            return
        
        item = self.elements_tree.item(selection[0])
        elem_id = item['values'][2]
        
        # Ask for modification
        modification = simpledialog.askstring(
            "Modify Element",
            f"Enter modification for {elem_id}:\n(e.g., 'color=blue', 'text=New Text')"
        )
        
        if modification:
            self.add_chat("You", f"Modify {elem_id}: {modification}")
            # Parse and apply
            try:
                if '=' in modification:
                    key, value = modification.split('=', 1)
                    params = {key.strip(): value.strip()}
                    success, msg = self.applier.apply_change({
                        'element': elem_id,
                        'action': 'config',
                        'params': params,
                        'description': f"Manual: {modification}"
                    })
                    
                    if success:
                        self.add_chat("System", f"Modified: {msg}")
                        self._refresh_elements()
                    else:
                        self.add_chat("System", f"Failed: {msg}")
            except Exception as e:
                self.add_chat("System", f"Error: {e}")
    
    def _execute_next_task(self):
        """Execute next task in plan."""
        if not self.change_plan:
            self.add_chat("System", "No tasks in plan")
            return
        
        # Find next pending task
        next_task = None
        for task in self.change_plan:
            if task.status == 'pending':
                next_task = task
                break
        
        if not next_task:
            self.add_chat("System", "No pending tasks")
            return
        
        # Check dependencies
        for dep_id in next_task.depends_on:
            dep_task = next((t for t in self.change_plan if t.id == dep_id), None)
            if dep_task and dep_task.status != 'completed':
                self.add_chat("System", f"Task {next_task.id} depends on {dep_id}")
                return
        
        # Execute
        next_task.status = 'running'
        self._update_plan_display()
        
        success, message = self.applier.apply_change({
            'element': next_task.element_id,
            'action': next_task.action,
            'params': next_task.params,
            'description': next_task.description
        })
        
        next_task.output = message
        next_task.status = 'completed' if success else 'failed'
        
        self._update_plan_display()
        self.add_chat("System", f"Task {next_task.id}: {message}")
        
        # Refresh elements view
        self._refresh_elements()
    
    def _execute_all_tasks(self):
        """Execute all pending tasks."""
        pending = [t for t in self.change_plan if t.status == 'pending']
        if not pending:
            self.add_chat("System", "No pending tasks")
            return
        
        self.add_chat("System", f"Executing {len(pending)} tasks...")
        
        for task in pending:
            self._execute_next_task()
            time.sleep(0.5)  # Small delay between tasks
        
        self.add_chat("System", "All tasks executed")
    
    def _clear_plan(self):
        """Clear current plan."""
        self.change_plan.clear()
        self._update_plan_display()
        self.add_chat("System", "Plan cleared")
    
    def _compare_snapshots(self):
        """Compare two snapshots."""
        if len(self.snapshots) < 2:
            messagebox.showwarning("Compare", "Need at least 2 snapshots")
            return
        
        # Create diff window
        diff_win = tk.Toplevel(self.root)
        diff_win.title("Snapshot Diff")
        diff_win.geometry("800x600")
        
        # Text widget for diff
        diff_text = scrolledtext.ScrolledText(diff_win, wrap='word', font=('Consolas', 9))
        diff_text.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Get snapshots to compare
        snap1 = self.snapshots[-2]
        snap2 = self.snapshots[-1]
        
        # Generate unified diff
        lines1 = json.dumps(snap1.elements, indent=2).splitlines()
        lines2 = json.dumps(snap2.elements, indent=2).splitlines()
        
        diff = difflib.unified_diff(
            lines1, lines2,
            fromfile=snap1.name,
            tofile=snap2.name,
            lineterm=''
        )
        
        diff_text.insert('end', '\n'.join(diff))
        diff_text.config(state='disabled')
    
    def _load_snapshot(self):
        """Load snapshot from file."""
        filepath = filedialog.askopenfilename(
            initialdir=SNAP_DIR,
            title="Select Snapshot",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filepath:
            try:
                snapshot = Snapshot.load(Path(filepath))
                self.snapshots.append(snapshot)
                
                # Show snapshot info
                info = (
                    f"Loaded: {snapshot.name}\n"
                    f"Time: {snapshot.timestamp}\n"
                    f"Elements: {len(snapshot.elements)}\n"
                    f"Hash: {snapshot.hash[:8]}..."
                )
                messagebox.showinfo("Snapshot Loaded", info)
                
                # Refresh diff view
                self._refresh_diff_view()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load: {e}")
    
    def _handle_plan_input(self, text: str):
        """Handle plan mode input."""
        if text.lower() in ['create', 'make', 'new']:
            self._create_change_plan(text)
        elif text.lower() in ['execute', 'run', 'start']:
            self._switch_mode("execute")
            self._execute_next_task()
        elif text.lower() in ['list', 'show']:
            self._update_plan_display()
        elif text.lower() in ['clear', 'reset']:
            self._clear_plan()
        else:
            self._create_change_plan(text)
    
    def _handle_execute_input(self, text: str):
        """Handle execute mode input."""
        if text.lower() in ['next', 'continue']:
            self._execute_next_task()
        elif text.lower() in ['all', 'run all']:
            self._execute_all_tasks()
        elif text.lower() in ['stop', 'cancel']:
            self._switch_mode("chat")
        elif text.lower() in ['skip']:
            # Skip current task
            for task in self.change_plan:
                if task.status == 'pending':
                    task.status = 'skipped'
                    break
            self._update_plan_display()
            self.add_chat("System", "Skipped task")
        else:
            self.add_chat("System", "Execute mode commands: next, all, skip, stop")

# ============================================================================
# CLI INTERFACE
# ============================================================================

def run_cli():
    """Run command line interface."""
    parser = argparse.ArgumentParser(
        description=f"GUILLM v{VERSION} - GUI Language Model Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  guillm.py --chat "Hello, how are you?"
  guillm.py --list
  guillm.py --change -e button1 "Make it blue"
  guillm.py --change -random
  guillm.py --config
  guillm.py --clone snapshot_123
        """
    )
    
    # Main commands
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--chat", type=str, help="Chat mode with message")
    group.add_argument("--change", action="store_true", help="Change mode")
    group.add_argument("--clone", type=str, help="Clone snapshot")
    group.add_argument("--config", action="store_true", help="Show configuration")
    group.add_argument("--gui", action="store_true", help="Launch GUI (default)")
    
    # Change mode options
    parser.add_argument("--list", "-l", action="store_true", help="List GUI features")
    parser.add_argument("--element", "-e", nargs="+", help="Element IDs to change")
    parser.add_argument("--instructions", "-i", type=str, help="Change instructions")
    parser.add_argument("--random", "-r", action="store_true", help="Make random change")
    
    # General options
    parser.add_argument("--model", "-m", type=str, default=None, help="Ollama model")
    parser.add_argument("--session", "-s", type=int, default=1, help="Session number")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--use-context", "-ctx", action="store_true", help="Load saved element profiles as context")
    
    args = parser.parse_args()
    
    # Set debug mode
    global DEBUG_MODE
    DEBUG_MODE = args.verbose
    
    # Initialize Ollama
    ollama = OllamaManager()
    
    if not args.model:
        args.model = ollama.current_model or "llama2"

    # Load context if requested
    cli_context = ""
    if args.use_context:
        ctx_dir = PROF_DIR / "elements"
        if ctx_dir.exists():
            profiles = []
            for pf in ctx_dir.glob("*.json"):
                try:
                    with open(pf, 'r') as f:
                        profiles.append(json.load(f))
                except: pass
            if profiles:
                cli_context = json.dumps(profiles, indent=2)
                if args.verbose:
                    print(f"Loaded {len(profiles)} element profiles for context.")
    
    if args.chat:
        # CLI chat
        prompt = args.chat
        if cli_context:
            prompt = f"GUI Context:\n{cli_context}\n\nUser Question: {args.chat}"
            
        response = ollama.generate(prompt, model=args.model)
        print(f"\nAssistant: {response}\n")
        
        # Save to session
        session_file = SESS_DIR / f"cli_session_{args.session}.txt"
        with open(session_file, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] User: {args.chat}\n")
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] Assistant: {response}\n")
    
    elif args.change:
        if args.list:
            # List features
            profiles = ProfileManager()
            print("\nGUI Feature Categories:")
            print("=" * 60)
            for profile in profiles.list_profiles():
                schema = profiles.get_schema(profile)
                if schema:
                    print(f"\n{profile.upper()}:")
                    print(f"  Properties: {', '.join(schema['properties'][:8])}")
                    print(f"  Actions: {', '.join(schema['actions'][:5])}")
            
            # Show specialized element profiles
            ctx_dir = PROF_DIR / "elements"
            if ctx_dir.exists():
                specialized = list(ctx_dir.glob("*.json"))
                if specialized:
                    print(f"\nSPECIALIZED ELEMENT PROFILES ({len(specialized)}):")
                    print("-" * 60)
                    for pf in specialized[:10]: # Limit to 10
                        try:
                            with open(pf, 'r') as f:
                                data = json.load(f)
                                name = data.get('source_info', {}).get('name', 'unknown')
                                print(f"  • {data['uid']:<20} | Name: {name:<15} | Type: {data['etype']}")
                        except: pass
                    if len(specialized) > 10:
                        print(f"    ... and {len(specialized)-10} more")
            print()
            
        elif args.random:
            # Random change
            print("\nGenerating random change...")
            changes = [
                "Change button color to blue",
                "Add a status label",
                "Make window larger",
                "Change all text to bold",
                "Add new button"
            ]
            change = random.choice(changes)
            print(f"Instruction: {change}")
            
            # Generate plan
            ollama.current_model = args.model
            plan = ollama.generate_change_plan("{}", change)
            print(f"Plan: {json.dumps(plan, indent=2)}")
            
            # Save to file
            change_file = LOG_DIR / f"random_change_{datetime.now().strftime('%H%M%S')}.json"
            with open(change_file, 'w', encoding='utf-8') as f:
                json.dump(plan, f, indent=2)
            print(f"Saved to: {change_file}")
            
        elif args.element and args.instructions:
            # Specific change
            print(f"\nChanging elements: {args.element}")
            print(f"Instructions: {args.instructions}")
            
            # Create change plan
            elements_info = [{"id": eid, "type": "unknown"} for eid in args.element]
            prompt = f"Elements: {json.dumps(elements_info)}\nInstructions: {args.instructions}"
            
            ollama.current_model = args.model
            plan = ollama.generate_change_plan(prompt, args.instructions)
            
            print(f"\nGenerated Plan:")
            for task in plan:
                print(f"  Task {task.get('id', '?')}: {task.get('description', 'Unknown')}")
                print(f"    Action: {task.get('action', 'config')} on {task.get('element', 'any')}")
            
            # Save plan
            plan_file = LOG_DIR / f"change_plan_{datetime.now().strftime('%H%M%S')}.json"
            with open(plan_file, 'w', encoding='utf-8') as f:
                json.dump(plan, f, indent=2)
            print(f"\nPlan saved to: {plan_file}")
        
        else:
            print("Change mode requires --list, --random, or --element with --instructions")
    
    elif args.clone:
        # Clone snapshot
        snap_file = SNAP_DIR / f"{args.clone}.json"
        if snap_file.exists():
            print(f"Cloning snapshot: {args.clone}")
            # Create modified copy
            with open(snap_file, 'r', encoding='utf-8') as f:
                snap_data = json.load(f)
            
            snap_data['metadata']['cloned_from'] = args.clone
            snap_data['metadata']['cloned_at'] = datetime.now().isoformat()
            
            new_name = f"{args.clone}_clone_{datetime.now().strftime('%H%M%S')}"
            new_file = SNAP_DIR / f"{new_name}.json"
            
            with open(new_file, 'w', encoding='utf-8') as f:
                json.dump(snap_data, f, indent=2)
            
            print(f"Created clone: {new_name}")
        else:
            print(f"Snapshot not found: {args.clone}")
            print(f"Available snapshots: {[f.stem for f in SNAP_DIR.glob('*.json')][:5]}")
    
    elif args.config:
        # Show configuration
        print(f"\nGUILLM v{VERSION} Configuration")
        print("=" * 50)
        print(f"Base Directory: {BASE_DIR}")
        print(f"Log Directory: {LOG_DIR}")
        print(f"Snapshot Directory: {SNAP_DIR}")
        print(f"Session Directory: {SESS_DIR}")
        print(f"Profile Directory: {PROF_DIR}")
        
        # Show models
        models = ollama.models
        print(f"\nAvailable Models ({len(models)}):")
        for i, model in enumerate(models[:10], 1):
            print(f"  {i:2}. {model}")
        if len(models) > 10:
            print(f"     ... and {len(models) - 10} more")
        
        # Show snapshots
        snapshots = list(SNAP_DIR.glob("*.json"))
        print(f"\nSnapshots ({len(snapshots)}):")
        for snap in sorted(snapshots, key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
            mtime = datetime.fromtimestamp(snap.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            print(f"  {snap.stem} ({mtime})")
        
        print()
    
    else:
        # Launch GUI
        print(f"\nGUILLM v{VERSION}")
        print("=" * 50)
        print(f"Starting GUI with model: {args.model}")
        print(f"Log file: {log_file}")
        print("\nPress Ctrl+C to exit\n")
        
        root = tk.Tk()
        app = GUILLMApp(root, model=args.model)
        root.mainloop()

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        run_cli()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)