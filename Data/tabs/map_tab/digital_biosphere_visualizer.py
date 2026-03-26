#!/usr/bin/env python3
"""
DIGITAL BIOSPHERE VISUALIZER: 3D Ecosystem Map
Interactive 3D visualization of the digital ecosystem as a spatial network.
#{ Test_Passed:[Live_Change_Attribution]: = True | 13.FEB.04.22AM] }
#{ Test_Grade:[Live_Change_Attribution]: = '5/10' | Note:Attribute_Fields_Missing_Cxt '-5' }
"""

"""
Cleaned and hardened imports.
Tracks availability of each optional dependency and provides clear error messages.
"""
import os
import sys
import json
import math
import threading
import queue
import time
import platform
import socket
import uuid
import subprocess
import re
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional, Union
from dataclasses import dataclass, field, asdict
from enum import Enum, auto

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext

# ----------------------------------------------------------------------
# Logging setup – prints to stderr; your app can redirect this
# ----------------------------------------------------------------------
def _log_import_error(lib: str, error: Exception) -> None:
    """Write a clean error message to stderr (capturable by logging)."""
    msg = f"[ImportError] {lib}: {type(error).__name__}: {error}"
    print(msg, file=sys.stderr)

# ----------------------------------------------------------------------
# Dependency status (backward‑compatible globals)
# ----------------------------------------------------------------------
HAS_DEPENDENCIES = True      # becomes False if any critical dep is missing
MISSING_LIB = None           # name of the first missing critical dependency
MODULAR_SUPPORT = False      # set by optional BaseTab/logger_util import

# ----------------------------------------------------------------------
# 1. NumPy – critical
# ----------------------------------------------------------------------
try:
    import numpy as np
except Exception as e:       # catches ImportError AND everything else
    _log_import_error('numpy', e)
    HAS_DEPENDENCIES = False
    MISSING_LIB = "numpy"
    np = None                # prevent NameError later

# ----------------------------------------------------------------------
# 2. Matplotlib (with TkAgg backend) – critical
# ----------------------------------------------------------------------
Figure = None
FigureCanvasTkAgg = None
NavigationToolbar2Tk = None
Circle = None
FancyArrowPatch = None
art3d = None
Axes3D = None
proj3d = None
Poly3DCollection = None
cm = None
mcolors = None
Button = None

if HAS_DEPENDENCIES:         # only try if numpy succeeded
    try:
        import matplotlib
        matplotlib.use('TkAgg')          # may raise if Tk not available
        from matplotlib.backends.backend_tkagg import (
            FigureCanvasTkAgg, NavigationToolbar2Tk
        )
        from matplotlib.figure import Figure
        from matplotlib.patches import Circle, FancyArrowPatch
        import mpl_toolkits.mplot3d.art3d as art3d
        from mpl_toolkits.mplot3d import Axes3D, proj3d
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        import matplotlib.cm as cm
        import matplotlib.colors as mcolors
        from matplotlib.widgets import Button
    except Exception as e:
        _log_import_error('matplotlib', e)
        HAS_DEPENDENCIES = False
        MISSING_LIB = "matplotlib"
        # Reset any partially-assigned module-level vars so callers can't use them
        Figure = None
        FigureCanvasTkAgg = None
        NavigationToolbar2Tk = None
        art3d = None
        Axes3D = None
else:
    # If numpy is already missing, mark matplotlib as the missing lib?
    # Original code does: if HAS_DEPENDENCIES still True, set to False.
    # Since HAS_DEPENDENCIES is already False, we should set MISSING_LIB
    # only if it hasn't been set yet.
    if MISSING_LIB is None:
        MISSING_LIB = "matplotlib (numpy missing)"

# ----------------------------------------------------------------------
# 3. psutil – critical
# ----------------------------------------------------------------------
if HAS_DEPENDENCIES:         # only try if previous critical deps succeeded
    try:
        import psutil
    except Exception as e:
        _log_import_error('psutil', e)
        HAS_DEPENDENCIES = False
        MISSING_LIB = "psutil"
else:
    if MISSING_LIB is None:
        MISSING_LIB = "psutil (previous deps missing)"

# ----------------------------------------------------------------------
# 4. Optional modular support – does NOT affect HAS_DEPENDENCIES
# ----------------------------------------------------------------------
try:
    from ..base_tab import BaseTab
    from logger_util import log_message
    MODULAR_SUPPORT = True
except Exception as e:
    _log_import_error('modular_support', e)
    MODULAR_SUPPORT = False
# ============================================================================
# DATA STRUCTURES
# ============================================================================

class NodeType(Enum):
    """Types of nodes in the visualization."""
    KERNEL = auto()
    CPU_CORE = auto()
    RAM_BANK = auto()
    STORAGE = auto()
    NETWORK = auto()
    GPU = auto()
    USB = auto()
    PCI = auto()
    BIOS = auto()
    FILE = auto()
    DIRECTORY = auto()
    PROCESS = auto()
    ENTITY = auto()
    SCRIPT = auto()
    LIBRARY = auto()
    SERVICE = auto()
    CONTAINER = auto()
    VIRTUAL_MACHINE = auto()

class Layer(Enum):
    """Visualization layers."""
    HARDWARE = auto()
    KERNEL = auto()
    PROCESSES = auto()
    FILESYSTEM = auto()
    NETWORK = auto()
    ENTITIES = auto()

@dataclass
class Node3D:
    """A 3D node in the visualization."""
    id: str
    name: str
    node_type: NodeType
    layer: Layer
    
    # 3D position
    x: float
    y: float
    z: float
    
    # Visual properties
    size: float = 1.0
    color: str = "#3498db"
    alpha: float = 0.8
    edge_width: float = 1.0
    edge_color: str = "#2c3e50"
    
    # Data properties
    data: Dict[str, Any] = field(default_factory=dict)
    connections: List[str] = field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    tooltip: str = ""
    
    def distance_to(self, other: 'Node3D') -> float:
        """Calculate Euclidean distance to another node."""
        return math.sqrt(
            (self.x - other.x) ** 2 +
            (self.y - other.y) ** 2 +
            (self.z - other.z) ** 2
        )

@dataclass
class Connection3D:
    """A connection between 3D nodes."""
    source_id: str
    target_id: str
    strength: float = 1.0
    color: str = "#7f8c8d"
    width: float = 1.0
    style: str = '-'  # '-', '--', '-.', ':'
    alpha: float = 0.6
    
    # Animation properties
    animated: bool = False
    pulse_speed: float = 0.0
    
    # Data properties
    data_type: str = ""
    bandwidth: float = 0.0
    latency: float = 0.0

@dataclass 
class HardwareComponent:
    """Hardware component information."""
    component_type: str
    name: str
    manufacturer: str
    model: str
    serial: str = ""
    firmware: str = ""
    driver: str = ""
    bios_path: Optional[str] = None
    system_files: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    
    def get_bios_info(self) -> Dict[str, Any]:
        """Get BIOS/UEFI information if available."""
        info = {
            'component': self.name,
            'type': self.component_type,
            'manufacturer': self.manufacturer,
            'model': self.model
        }
        
        if self.bios_path and Path(self.bios_path).exists():
            try:
                stat = Path(self.bios_path).stat()
                info['bios'] = {
                    'path': self.bios_path,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'exists': True
                }
            except:
                info['bios'] = {'path': self.bios_path, 'exists': False}
        
        return info

@dataclass
class FileNode:
    """File system node information."""
    path: str
    name: str
    size: int
    is_dir: bool
    file_type: str
    permissions: str
    modified: datetime
    accessed: datetime
    created: datetime
    
    # Classification
    kingdom: Optional[str] = None
    territories: List[str] = field(default_factory=list)
    influence: str = "low"
    
    # Content analysis
    content_preview: str = ""
    hash_dna: str = ""
    entities: List[str] = field(default_factory=list)
    
    def get_properties(self) -> Dict[str, Any]:
        """Get file properties for display."""
        return {
            'path': self.path,
            'name': self.name,
            'size': self.size,
            'type': self.file_type,
            'permissions': self.permissions,
            'modified': self.modified.isoformat(),
            'kingdom': self.kingdom,
            'territories': self.territories,
            'influence': self.influence,
            'hash': self.hash_dna[:16] if self.hash_dna else None
        }

# ============================================================================
# HARDWARE DISCOVERY ENGINE
# ============================================================================

class HardwareDiscovery:
    """Discover and map hardware components."""
    
    def __init__(self):
        self.components: List[HardwareComponent] = []
        self.bios_paths = self._find_bios_paths()
        self.system_files = self._find_system_files()
        
    def _find_bios_paths(self) -> Dict[str, str]:
        """Find BIOS/UEFI file paths."""
        paths = {}
        
        # Linux BIOS paths
        if platform.system() == "Linux":
            bios_paths = [
                "/sys/firmware/efi/",
                "/proc/device-tree/",
                "/sys/class/dmi/id/",
                "/sys/firmware/acpi/tables/",
                "/usr/share/edk2/",
                "/boot/efi/EFI/",
            ]
            
            for base_path in bios_paths:
                try:
                    if Path(base_path).exists():
                        for path in Path(base_path).rglob("*"):
                            try:
                                if path.is_file():
                                    rel_path = str(path.relative_to(base_path))
                                    paths[rel_path] = str(path)
                            except PermissionError:
                                pass
                except PermissionError:
                    pass  # Skip paths requiring elevated access
        
        # Windows BIOS paths (approximate)
        elif platform.system() == "Windows":
            windows_paths = [
                "C:\\Windows\\System32\\drivers\\",
                "C:\\Windows\\System32\\",
                "C:\\Windows\\Boot\\",
            ]
            
            for base_path in windows_paths:
                if Path(base_path).exists():
                    for path in Path(base_path).rglob("*.efi"):
                        paths[path.name] = str(path)
                    for path in Path(base_path).rglob("*.sys"):
                        paths[path.name] = str(path)
        
        return paths
    
    def _find_system_files(self) -> List[str]:
        """Find important system files."""
        system_files = []
        
        # Linux system files
        if platform.system() == "Linux":
            linux_files = [
                "/etc/passwd",
                "/etc/group",
                "/etc/hosts",
                "/etc/fstab",
                "/proc/cpuinfo",
                "/proc/meminfo",
                "/proc/version",
                "/proc/modules",
                "/var/log/syslog",
                "/var/log/kern.log",
                "/boot/vmlinuz-*",
                "/boot/initrd-*",
                "/lib/modules/*/",
                "/usr/lib/modules/*/",
            ]
            
            for pattern in linux_files:
                try:
                    for path in Path("/").glob(pattern.lstrip("/")):
                        try:
                            if path.exists():
                                system_files.append(str(path))
                        except PermissionError:
                            pass
                except PermissionError:
                    pass
        
        # Windows system files
        elif platform.system() == "Windows":
            windows_files = [
                "C:\\Windows\\System32\\config\\",
                "C:\\Windows\\System32\\drivers\\etc\\hosts",
                "C:\\Windows\\System32\\drivers\\etc\\services",
                "C:\\Windows\\System32\\kernel32.dll",
                "C:\\Windows\\System32\\ntdll.dll",
                "C:\\Windows\\System32\\win32k.sys",
                "C:\\Windows\\System32\\config\\SYSTEM",
                "C:\\Windows\\System32\\config\\SOFTWARE",
                "C:\\Windows\\System32\\config\\SECURITY",
                "C:\\Windows\\System32\\config\\SAM",
            ]
            
            for pattern in windows_files:
                for path in Path("C:\\").glob(pattern.lstrip("C:\\")):
                    if path.exists():
                        system_files.append(str(path))
        
        return system_files
    
    def discover_all(self) -> List[HardwareComponent]:
        """Discover all hardware components."""
        self.components = []
        
        # CPU Discovery
        self._discover_cpu()
        
        # Memory Discovery
        self._discover_memory()
        
        # Storage Discovery
        self._discover_storage()
        
        # Network Discovery
        self._discover_network()
        
        # GPU Discovery
        self._discover_gpu()
        
        # USB Discovery
        self._discover_usb()
        
        # PCI Discovery
        self._discover_pci()
        
        # BIOS/UEFI
        self._discover_bios()
        
        return self.components
    
    def _discover_cpu(self):
        """Discover CPU information."""
        try:
            if platform.system() == "Linux":
                with open("/proc/cpuinfo", "r") as f:
                    cpuinfo = f.read()
                
                # Parse CPU info
                model_match = re.search(r"model name\s*:\s*(.+)", cpuinfo)
                cores_match = re.search(r"cpu cores\s*:\s*(\d+)", cpuinfo)
                
                cpu = HardwareComponent(
                    component_type="CPU",
                    name="Central Processing Unit",
                    manufacturer=self._guess_manufacturer(cpuinfo),
                    model=model_match.group(1) if model_match else "Unknown CPU",
                    serial="",  # CPU serial usually not exposed
                    capabilities=self._get_cpu_capabilities()
                )
                
                self.components.append(cpu)
                
        except Exception as e:
            print(f"CPU discovery error: {e}")
    
    def _discover_memory(self):
        """Discover memory information."""
        try:
            if platform.system() == "Linux":
                with open("/proc/meminfo", "r") as f:
                    meminfo = f.read()
                
                total_match = re.search(r"MemTotal:\s*(\d+)", meminfo)
                
                ram = HardwareComponent(
                    component_type="RAM",
                    name="Random Access Memory",
                    manufacturer="System",
                    model=f"{int(total_match.group(1)) // 1024}MB RAM" if total_match else "Unknown RAM",
                    capabilities=["volatile_storage", "fast_access"]
                )
                
                self.components.append(ram)
                
        except Exception as e:
            print(f"Memory discovery error: {e}")
    
    def _discover_storage(self):
        """Discover storage devices."""
        try:
            if hasattr(psutil, 'disk_partitions'):
                for partition in psutil.disk_partitions():
                    try:
                        usage = psutil.disk_usage(partition.mountpoint)
                        
                        storage = HardwareComponent(
                            component_type="STORAGE",
                            name=f"Storage: {partition.device}",
                            manufacturer="Storage Manufacturer",
                            model=partition.fstype or "Unknown FS",
                            properties={
                                'mountpoint': partition.mountpoint,
                                'total_gb': usage.total / (1024**3),
                                'used_gb': usage.used / (1024**3),
                                'free_gb': usage.free / (1024**3)
                            }
                        )
                        
                        self.components.append(storage)
                        
                    except:
                        continue
                        
        except Exception as e:
            print(f"Storage discovery error: {e}")
    
    def _discover_network(self):
        """Discover network interfaces."""
        try:
            if hasattr(psutil, 'net_if_addrs'):
                interfaces = psutil.net_if_addrs()
                
                for iface, addrs in interfaces.items():
                    # Skip loopback
                    if iface == "lo":
                        continue
                    
                    network = HardwareComponent(
                        component_type="NETWORK",
                        name=f"Network: {iface}",
                        manufacturer="Network Manufacturer",
                        model="Ethernet/Wireless Adapter",
                        properties={
                            'interface': iface,
                            'addresses': [str(addr.address) for addr in addrs],
                            'is_wireless': 'wireless' in iface.lower() or 'wifi' in iface.lower()
                        }
                    )
                    
                    self.components.append(network)
                    
        except Exception as e:
            print(f"Network discovery error: {e}")
    
    def _discover_gpu(self):
        """Discover GPU information."""
        try:
            # Try to detect NVIDIA
            nvidia_path = Path("/proc/driver/nvidia/gpus/")
            if nvidia_path.exists():
                for gpu_dir in nvidia_path.iterdir():
                    gpu = HardwareComponent(
                        component_type="GPU",
                        name="Graphics Processing Unit",
                        manufacturer="NVIDIA",
                        model="NVIDIA GPU",
                        properties={'vendor': 'nvidia'}
                    )
                    self.components.append(gpu)
            
            # Try to detect AMD
            amd_path = Path("/sys/class/drm/card0/device/")
            if amd_path.exists():
                vendor_file = amd_path / "vendor"
                if vendor_file.exists():
                    vendor = vendor_file.read_text().strip()
                    if "1002" in vendor:  # AMD vendor ID
                        gpu = HardwareComponent(
                            component_type="GPU",
                            name="Graphics Processing Unit",
                            manufacturer="AMD",
                            model="AMD GPU",
                            properties={'vendor': 'amd'}
                        )
                        self.components.append(gpu)
            
            # Intel integrated graphics
            intel_path = Path("/sys/class/drm/card0/device/vendor")
            if intel_path.exists():
                vendor = intel_path.read_text().strip()
                if "8086" in vendor:  # Intel vendor ID
                    gpu = HardwareComponent(
                        component_type="GPU",
                        name="Graphics Processing Unit",
                        manufacturer="Intel",
                        model="Intel Integrated Graphics",
                        properties={'vendor': 'intel'}
                    )
                    self.components.append(gpu)
                    
        except Exception as e:
            print(f"GPU discovery error: {e}")
    
    def _discover_usb(self):
        """Discover USB devices."""
        try:
            if platform.system() == "Linux":
                usb_path = Path("/sys/bus/usb/devices/")
                if usb_path.exists():
                    for device in usb_path.iterdir():
                        if device.name.startswith("usb"):
                            try:
                                product_file = device / "product"
                                manufacturer_file = device / "manufacturer"
                                
                                product = product_file.read_text().strip() if product_file.exists() else "USB Device"
                                manufacturer = manufacturer_file.read_text().strip() if manufacturer_file.exists() else "Unknown"
                                
                                usb = HardwareComponent(
                                    component_type="USB",
                                    name=f"USB: {product}",
                                    manufacturer=manufacturer,
                                    model=product,
                                    properties={'bus_id': device.name}
                                )
                                
                                self.components.append(usb)
                                
                            except:
                                continue
                                
        except Exception as e:
            print(f"USB discovery error: {e}")
    
    def _discover_pci(self):
        """Discover PCI devices."""
        try:
            if platform.system() == "Linux":
                pci_path = Path("/sys/bus/pci/devices/")
                if pci_path.exists():
                    for device in pci_path.iterdir():
                        try:
                            vendor_file = device / "vendor"
                            device_file = device / "device"
                            
                            if vendor_file.exists() and device_file.exists():
                                vendor = vendor_file.read_text().strip()
                                device_id = device_file.read_text().strip()
                                
                                pci = HardwareComponent(
                                    component_type="PCI",
                                    name=f"PCI Device: {device.name}",
                                    manufacturer=f"Vendor: {vendor}",
                                    model=f"Device: {device_id}",
                                    properties={
                                        'slot': device.name,
                                        'vendor_id': vendor,
                                        'device_id': device_id
                                    }
                                )
                                
                                self.components.append(pci)
                                
                        except:
                            continue
                            
        except Exception as e:
            print(f"PCI discovery error: {e}")
    
    def _discover_bios(self):
        """Discover BIOS/UEFI."""
        try:
            bios = HardwareComponent(
                component_type="BIOS",
                name="System BIOS/UEFI",
                manufacturer="System Manufacturer",
                model="Firmware",
                bios_path=self._get_bios_path(),
                system_files=self.system_files[:10]  # First 10 system files
            )
            
            self.components.append(bios)
            
        except Exception as e:
            print(f"BIOS discovery error: {e}")
    
    def _guess_manufacturer(self, cpuinfo: str) -> str:
        """Guess CPU manufacturer from CPU info."""
        cpuinfo_lower = cpuinfo.lower()
        if "intel" in cpuinfo_lower:
            return "Intel"
        elif "amd" in cpuinfo_lower:
            return "AMD"
        elif "arm" in cpuinfo_lower:
            return "ARM"
        else:
            return "Unknown"
    
    def _get_cpu_capabilities(self) -> List[str]:
        """Get CPU capabilities."""
        capabilities = []
        
        try:
            if platform.system() == "Linux":
                with open("/proc/cpuinfo", "r") as f:
                    cpuinfo = f.read()
                
                # Check for specific flags
                flags_section = re.search(r"flags\s*:\s*(.+)", cpuinfo, re.MULTILINE)
                if flags_section:
                    flags = flags_section.group(1).lower()
                    if "vmx" in flags or "svm" in flags:
                        capabilities.append("virtualization")
                    if "aes" in flags:
                        capabilities.append("aes_encryption")
                    if "avx" in flags:
                        capabilities.append("avx")
                    if "avx2" in flags:
                        capabilities.append("avx2")
                        
        except:
            pass
        
        return capabilities
    
    def _get_bios_path(self) -> Optional[str]:
        """Get BIOS/UEFI file path."""
        # Look for common BIOS files
        bios_candidates = [
            "/sys/firmware/efi/",
            "/proc/device-tree/",
            "/boot/efi/",
        ]
        
        for path in bios_candidates:
            if Path(path).exists():
                return path
        
        return None

# ============================================================================
# 3D VISUALIZATION ENGINE
# ============================================================================

class DigitalBiosphereVisualizer:
    """Main 3D visualization engine."""
    
    def __init__(self, root: tk.Tk):
        # Check for missing dependencies first
        self.import_error = None
        if not globals().get('HAS_DEPENDENCIES', True):
            self.import_error = globals().get('MISSING_LIB', 'unknown')

        self.root = root
        if isinstance(root, (tk.Tk, tk.Toplevel)):
            self.root.title("Digital Biosphere 3D Visualizer")
            self.root.geometry("1400x900")
        
        # State
        self.components: List[HardwareComponent] = []
        self.nodes: Dict[str, Node3D] = {}
        self.connections: List[Connection3D] = []
        self.selected_node: Optional[Node3D] = None
        self.view_mode = "hardware"  # hardware, filesystem, network, processes
        
        # Camera state
        self.camera_elevation = 30
        self.camera_azimuth = 45
        self.camera_distance = 10
        self.camera_target = (0, 0, 0)
        
        # Animation
        self.animation_running = False
        self.animation_thread = None
        self.pulse_phase = 0.0
        
        # UI elements
        self.setup_ui()
        
        # Initial scan (only if dependencies are present)
        if not self.import_error:
            self.hardware_discovery = HardwareDiscovery()
            self.scan_hardware()
            self.start_animation()
        else:
            self.update_status(f"⚠️ Limited Mode: Missing {self.import_error}")
    
    def setup_ui(self):
        """Setup the Tkinter UI."""
        # Main container
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Bottom panel MUST be packed before left/right so tkinter gives it space first
        bottom_panel = ttk.Frame(self.main_container)
        bottom_panel.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))

        # Left panel - Controls (fixed width)
        left_panel = ttk.Frame(self.main_container, width=280)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left_panel.pack_propagate(False)

        # Right panel - Visualization (takes remaining space)
        right_panel = ttk.Frame(self.main_container)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Setup panels
        self.setup_left_panel(left_panel)
        self.setup_visualization_panel(right_panel)
        self.setup_bottom_panel(bottom_panel)
    
    def setup_left_panel(self, parent):
        """Setup left control panel."""
        # Title
        title_label = ttk.Label(parent, text="Digital Biosphere",
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(10, 20))

        # View mode selector
        ttk.Label(parent, text="View Mode:").pack(anchor=tk.W, padx=10)
        self.view_mode_var = tk.StringVar(value="hardware")

        view_modes = [
            ("Hardware Map", "hardware"),
            ("File System", "filesystem"),
            ("Network", "network"),
            ("Processes", "processes"),
            ("Entities", "entities")
        ]

        for text, mode in view_modes:
            ttk.Radiobutton(parent, text=text, variable=self.view_mode_var,
                          value=mode, command=self.on_view_mode_changed).pack(anchor=tk.W, padx=30)

        # Separator
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=20)

        # Node info panel
        ttk.Label(parent, text="Selected Node:",
                 font=("Arial", 11, "bold")).pack(anchor=tk.W, padx=10, pady=(0, 10))

        self.node_info_frame = ttk.Frame(parent)
        self.node_info_frame.pack(fill=tk.BOTH, expand=True, padx=10)

        # Node info text
        self.node_info_text = tk.Text(self.node_info_frame, height=15,
                                     width=35, wrap=tk.WORD)
        node_scrollbar = ttk.Scrollbar(self.node_info_frame,
                                      command=self.node_info_text.yview)
        self.node_info_text.configure(yscrollcommand=node_scrollbar.set)

        self.node_info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        node_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Clear selection button
        ttk.Button(parent, text="Clear Selection",
                  command=self.clear_selection).pack(pady=10)

        # Refresh button
        ttk.Button(parent, text="Refresh Hardware",
                  command=self.refresh_hardware).pack(pady=5)

        # Scan files button
        ttk.Button(parent, text="Scan System Files",
                  command=self.scan_system_files).pack(pady=5)

    def setup_visualization_panel(self, parent):
        """Setup right visualization panel with matplotlib 3D canvas.
        Canvas and toolbar live here, not in the left panel.
        #[Mark:MAP_TAB_VIZ_PANEL]
        """
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        parent.rowconfigure(1, weight=0)  # toolbar row

        if Figure is not None:
            # Dark-themed figure to match the app's dark UI
            self.figure = Figure(figsize=(8, 6), dpi=100)
            self.figure.patch.set_facecolor('#1e1e2e')

            self.ax = self.figure.add_subplot(111, projection='3d')
            self.ax.set_facecolor('#1e1e2e')
            self.ax.tick_params(colors='#cdd6f4', labelsize=7)
            self.ax.xaxis.label.set_color('#cdd6f4')
            self.ax.yaxis.label.set_color('#cdd6f4')
            self.ax.zaxis.label.set_color('#cdd6f4')
            self.ax.title.set_color('#cdd6f4')
            for pane in (self.ax.xaxis.pane, self.ax.yaxis.pane, self.ax.zaxis.pane):
                pane.fill = False
                pane.set_edgecolor('#313244')

            self.ax.set_xlabel('X')
            self.ax.set_ylabel('Y')
            self.ax.set_zlabel('Z')
            self.ax.set_title('Digital Biosphere 3D Map')
            self.ax.view_init(elev=self.camera_elevation, azim=self.camera_azimuth)

            # Canvas embedded directly in the right panel frame
            self.canvas = FigureCanvasTkAgg(self.figure, parent)
            canvas_widget = self.canvas.get_tk_widget()
            canvas_widget.grid(row=0, column=0, sticky='nsew')

            # Toolbar below canvas (row 1)
            toolbar_frame = ttk.Frame(parent)
            toolbar_frame.grid(row=1, column=0, sticky='ew')
            toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
            toolbar.update()

            # Mouse events
            self.canvas.mpl_connect('button_press_event', self.on_click)
            self.canvas.mpl_connect('motion_notify_event', self.on_motion)
            self.canvas.mpl_connect('scroll_event', self.on_scroll)

            self.canvas.draw()
        else:
            # matplotlib not available — show dependency message
            msg_frame = ttk.Frame(parent)
            msg_frame.grid(row=0, column=0, sticky='nsew')
            ttk.Label(
                msg_frame,
                text="3D Visualization requires matplotlib + numpy\n\npip install matplotlib numpy",
                font=("Arial", 11),
                justify='center'
            ).pack(expand=True, pady=40)

    def setup_bottom_panel(self, parent):
        """Setup bottom configuration panel."""
        # Speed controls
        ttk.Label(parent, text="Animation Speed:").pack(side=tk.LEFT, padx=10)
        
        self.speed_var = tk.DoubleVar(value=1.0)
        speed_scale = ttk.Scale(parent, from_=0.1, to=5.0, 
                               variable=self.speed_var, orient=tk.HORIZONTAL,
                               length=150)
        speed_scale.pack(side=tk.LEFT, padx=5)
        
        # Sensitivity controls
        ttk.Label(parent, text="Sensitivity:").pack(side=tk.LEFT, padx=10)
        
        self.sensitivity_var = tk.DoubleVar(value=1.0)
        sensitivity_scale = ttk.Scale(parent, from_=0.1, to=3.0,
                                     variable=self.sensitivity_var, 
                                     orient=tk.HORIZONTAL, length=150)
        sensitivity_scale.pack(side=tk.LEFT, padx=5)
        
        # Node size controls
        ttk.Label(parent, text="Node Size:").pack(side=tk.LEFT, padx=10)
        
        self.node_size_var = tk.DoubleVar(value=1.0)
        node_size_scale = ttk.Scale(parent, from_=0.5, to=3.0,
                                   variable=self.node_size_var,
                                   orient=tk.HORIZONTAL, length=150)
        node_size_scale.pack(side=tk.LEFT, padx=5)
        
        # Color scheme selector
        ttk.Label(parent, text="Color:").pack(side=tk.LEFT, padx=10)
        
        self.color_scheme_var = tk.StringVar(value="viridis")
        color_combo = ttk.Combobox(parent, textvariable=self.color_scheme_var,
                                  values=["viridis", "plasma", "cool", "wistia", 
                                         "Set1", "Set2", "tab10"],
                                  width=10, state="readonly")
        color_combo.pack(side=tk.LEFT, padx=5)
        color_combo.bind('<<ComboboxSelected>>', self.on_color_scheme_changed)
        
        # Status label
        self.status_label = ttk.Label(parent, text="Ready")
        self.status_label.pack(side=tk.RIGHT, padx=10)
    
    def scan_hardware(self):
        """Scan and map hardware components."""
        self.components = self.hardware_discovery.discover_all()
        self.create_3d_scene()
        self.update_status(f"Found {len(self.components)} hardware components")
    
    def refresh_hardware(self):
        """Refresh hardware scan."""
        self.scan_hardware()
        self.redraw_scene()
    
    def scan_system_files(self):
        """Scan system files."""
        self.update_status("Scanning system files...")
        # In a real implementation, this would scan files
        # For now, just update status
        self.root.after(1000, lambda: self.update_status("System files scanned"))
    
    def create_3d_scene(self):
        """Create the 3D scene from hardware components."""
        if not hasattr(self, 'ax') or self.ax is None:
            return

        self.nodes = {}
        self.connections = []

        # Clear existing artists
        self.ax.clear()
        
        # Create cube frame (8 corners for major hardware)
        cube_size = 5
        cube_corners = [
            (-cube_size, -cube_size, -cube_size),  # 0: BIOS
            (cube_size, -cube_size, -cube_size),   # 1: CPU
            (cube_size, cube_size, -cube_size),    # 2: RAM
            (-cube_size, cube_size, -cube_size),   # 3: Storage
            (-cube_size, -cube_size, cube_size),   # 4: GPU
            (cube_size, -cube_size, cube_size),    # 5: Network
            (cube_size, cube_size, cube_size),     # 6: USB
            (-cube_size, cube_size, cube_size),    # 7: PCI
        ]
        
        corner_labels = ["BIOS", "CPU", "RAM", "STORAGE", "GPU", "NETWORK", "USB", "PCI"]
        
        # Create corner nodes
        for i, (pos, label) in enumerate(zip(cube_corners, corner_labels)):
            node = Node3D(
                id=f"corner_{i}",
                name=label,
                node_type=self._label_to_node_type(label),
                layer=Layer.HARDWARE,
                x=pos[0],
                y=pos[1],
                z=pos[2],
                size=2.0,
                color=self._get_node_color(label),
                alpha=0.9,
                tooltip=f"Hardware Node: {label}"
            )
            self.nodes[node.id] = node
        
        # Create inner circle for system components
        circle_radius = 2.5
        num_circle_nodes = min(len(self.components), 12)
        
        for i in range(num_circle_nodes):
            if i < len(self.components):
                comp = self.components[i]
                angle = 2 * math.pi * i / num_circle_nodes
                
                node = Node3D(
                    id=f"component_{i}",
                    name=comp.name,
                    node_type=self._component_to_node_type(comp.component_type),
                    layer=Layer.HARDWARE,
                    x=circle_radius * math.cos(angle),
                    y=circle_radius * math.sin(angle),
                    z=0,
                    size=1.5,
                    color=self._get_component_color(comp.component_type),
                    alpha=0.8,
                    data=asdict(comp),
                    tooltip=f"{comp.component_type}: {comp.name}"
                )
                self.nodes[node.id] = node
        
        # Create kernel node at center
        kernel_node = Node3D(
            id="kernel",
            name="System Kernel",
            node_type=NodeType.KERNEL,
            layer=Layer.KERNEL,
            x=0, y=0, z=0,
            size=3.0,
            color="#e74c3c",
            alpha=1.0,
            edge_width=2.0,
            edge_color="#c0392b",
            tooltip="System Kernel - Core OS Component"
        )
        self.nodes[kernel_node.id] = kernel_node
        
        # Create connections
        self._create_connections()
        
        # Configure axes
        self.ax.set_xlim([-cube_size*1.2, cube_size*1.2])
        self.ax.set_ylim([-cube_size*1.2, cube_size*1.2])
        self.ax.set_zlim([-cube_size*1.2, cube_size*1.2])
        
        self.ax.set_xlabel('X Axis')
        self.ax.set_ylabel('Y Axis')
        self.ax.set_zlabel('Z Axis')
        self.ax.set_title('Digital Biosphere 3D Map')
        
        # Set view
        self.ax.view_init(elev=self.camera_elevation, azim=self.camera_azimuth)
    
    def _create_connections(self):
        """Create connections between nodes."""
        # Connect corners to form cube
        corner_edges = [
            (0, 1), (1, 2), (2, 3), (3, 0),  # Bottom square
            (4, 5), (5, 6), (6, 7), (7, 4),  # Top square
            (0, 4), (1, 5), (2, 6), (3, 7)   # Vertical edges
        ]
        
        for i, j in corner_edges:
            source_id = f"corner_{i}"
            target_id = f"corner_{j}"
            
            if source_id in self.nodes and target_id in self.nodes:
                conn = Connection3D(
                    source_id=source_id,
                    target_id=target_id,
                    strength=1.0,
                    color="#34495e",
                    width=1.5,
                    alpha=0.4
                )
                self.connections.append(conn)
        
        # Connect kernel to all corners
        for i in range(8):
            corner_id = f"corner_{i}"
            if corner_id in self.nodes:
                conn = Connection3D(
                    source_id="kernel",
                    target_id=corner_id,
                    strength=0.7,
                    color="#e74c3c",
                    width=1.0,
                    style=":",
                    alpha=0.3,
                    animated=True,
                    pulse_speed=0.5
                )
                self.connections.append(conn)
        
        # Connect components to kernel
        for node_id, node in self.nodes.items():
            if node_id.startswith("component_"):
                conn = Connection3D(
                    source_id="kernel",
                    target_id=node_id,
                    strength=0.5,
                    color="#3498db",
                    width=0.8,
                    style="--",
                    alpha=0.2
                )
                self.connections.append(conn)
    
    def _label_to_node_type(self, label: str) -> NodeType:
        """Convert label to NodeType."""
        label_upper = label.upper()
        if "CPU" in label_upper:
            return NodeType.CPU_CORE
        elif "RAM" in label_upper:
            return NodeType.RAM_BANK
        elif "STORAGE" in label_upper or "HDD" in label_upper or "SSD" in label_upper:
            return NodeType.STORAGE
        elif "NETWORK" in label_upper:
            return NodeType.NETWORK
        elif "GPU" in label_upper:
            return NodeType.GPU
        elif "USB" in label_upper:
            return NodeType.USB
        elif "PCI" in label_upper:
            return NodeType.PCI
        elif "BIOS" in label_upper:
            return NodeType.BIOS
        else:
            return NodeType.HARDWARE
    
    def _component_to_node_type(self, component_type: str) -> NodeType:
        """Convert component type to NodeType."""
        comp_type = component_type.upper()
        if "CPU" in comp_type:
            return NodeType.CPU_CORE
        elif "RAM" in comp_type:
            return NodeType.RAM_BANK
        elif "STORAGE" in comp_type:
            return NodeType.STORAGE
        elif "NETWORK" in comp_type:
            return NodeType.NETWORK
        elif "GPU" in comp_type:
            return NodeType.GPU
        elif "USB" in comp_type:
            return NodeType.USB
        elif "PCI" in comp_type:
            return NodeType.PCI
        elif "BIOS" in comp_type:
            return NodeType.BIOS
        else:
            return NodeType.HARDWARE
    
    def _get_node_color(self, label: str) -> str:
        """Get color for node based on label."""
        color_map = {
            "BIOS": "#8e44ad",      # Purple
            "CPU": "#e74c3c",       # Red
            "RAM": "#3498db",       # Blue
            "STORAGE": "#f39c12",   # Orange
            "GPU": "#2ecc71",       # Green
            "NETWORK": "#1abc9c",   # Teal
            "USB": "#9b59b6",       # Light Purple
            "PCI": "#34495e",       # Dark Blue
        }
        return color_map.get(label, "#95a5a6")  # Default gray
    
    def _get_component_color(self, component_type: str) -> str:
        """Get color for component."""
        color_map = {
            "CPU": "#e74c3c",       # Red
            "RAM": "#3498db",       # Blue
            "STORAGE": "#f39c12",   # Orange
            "NETWORK": "#1abc9c",   # Teal
            "GPU": "#2ecc71",       # Green
            "USB": "#9b59b6",       # Light Purple
            "PCI": "#34495e",       # Dark Blue
            "BIOS": "#8e44ad",      # Purple
        }
        return color_map.get(component_type.upper(), "#95a5a6")
    
    def redraw_scene(self):
        """Redraw the 3D scene."""
        if self.import_error or not hasattr(self, 'ax'):
            return
            
        self.ax.clear()
        
        # Draw nodes
        for node in self.nodes.values():
            size = node.size * self.node_size_var.get()
            
            # Create scatter point
            scatter = self.ax.scatter(
                node.x, node.y, node.z,
                s=size * 100,  # Scale size
                c=node.color,
                alpha=node.alpha,
                edgecolors=node.edge_color,
                linewidth=node.edge_width,
                marker='o',
                picker=True,  # Enable picking for this artist
                pickradius=5   # Pick radius in points
            )
            
            # Store reference to node
            scatter.node_id = node.id
            
            # Add label for important nodes
            if node.node_type in [NodeType.KERNEL, NodeType.CPU_CORE, NodeType.BIOS]:
                self.ax.text(node.x, node.y, node.z + 0.3, 
                           node.name[:15], fontsize=8, ha='center')
        
        # Draw connections
        for conn in self.connections:
            source = self.nodes.get(conn.source_id)
            target = self.nodes.get(conn.target_id)
            
            if source and target:
                # Calculate line width
                width = conn.width
                if conn.animated:
                    width = width * (1 + 0.3 * math.sin(self.pulse_phase * conn.pulse_speed))
                
                # Draw line
                line = self.ax.plot(
                    [source.x, target.x],
                    [source.y, target.y],
                    [source.z, target.z],
                    color=conn.color,
                    linewidth=width,
                    linestyle=conn.style,
                    alpha=conn.alpha
                )
        
        # Configure axes
        cube_size = 5
        self.ax.set_xlim([-cube_size*1.2, cube_size*1.2])
        self.ax.set_ylim([-cube_size*1.2, cube_size*1.2])
        self.ax.set_zlim([-cube_size*1.2, cube_size*1.2])
        
        self.ax.set_xlabel('X Axis')
        self.ax.set_ylabel('Y Axis')
        self.ax.set_zlabel('Z Axis')
        
        title = {
            "hardware": "Hardware Map",
            "filesystem": "File System",
            "network": "Network Map",
            "processes": "Process Tree",
            "entities": "Digital Entities"
        }.get(self.view_mode, "Digital Biosphere 3D Map")
        
        self.ax.set_title(title)
        
        # Set view
        self.ax.view_init(elev=self.camera_elevation, azim=self.camera_azimuth)
        
        # Redraw canvas
        self.canvas.draw()
    
    def on_click(self, event):
        """Handle mouse clicks."""
        # event.inaxes is often None for 3D axes even when visually inside the canvas;
        # only reject if canvas widget itself isn't ready
        if not hasattr(self, 'ax') or not hasattr(self, 'canvas'):
            return
            
        # Get click coordinates
        x, y = event.xdata, event.ydata
        
        if event.button == 1:  # Left click
            # Find closest node
            closest_node = None
            min_distance = float('inf')
            
            for node in self.nodes.values():
                # Project 3D point to 2D screen coordinates
                x2d, y2d, _ = proj3d.proj_transform(node.x, node.y, node.z, self.ax.get_proj())
                
                # Calculate distance in screen coordinates
                distance = math.sqrt((x2d - x) ** 2 + (y2d - y) ** 2)
                
                if distance < min_distance and distance < 0.05:  # Threshold
                    min_distance = distance
                    closest_node = node
            
            if closest_node:
                self.select_node(closest_node)
            else:
                # If no node clicked, rotate view
                self.rotate_view(event)
        
        elif event.button == 3:  # Right click
            # Pan view
            self.pan_view(event)
    
    def rotate_view(self, event):
        """Rotate view based on mouse drag."""
        # Store initial position
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
        self._biosphere_drag_ts = 0.0  # frame-rate throttle timestamp

        def on_motion(event):
            if not hasattr(self, 'last_mouse_x'):
                return

            dx = event.x - self.last_mouse_x
            dy = event.y - self.last_mouse_y

            # Update camera angles
            sensitivity = self.sensitivity_var.get()
            self.camera_azimuth += dx * 0.5 * sensitivity
            self.camera_elevation += dy * 0.5 * sensitivity

            # Clamp elevation
            self.camera_elevation = max(-90, min(90, self.camera_elevation))

            # Update view angle without full scene rebuild
            self.ax.view_init(elev=self.camera_elevation, azim=self.camera_azimuth)

            # Throttle redraws to ~30fps so UI stays responsive
            import time as _t
            now = _t.time()
            if now - self._biosphere_drag_ts >= 0.033:
                self.canvas.draw_idle()
                self._biosphere_drag_ts = now

            # Update stored position
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y

        def on_release(event):
            self.canvas.mpl_disconnect(motion_id)
            self.canvas.mpl_disconnect(release_id)
            # Final draw on release to settle view
            self.canvas.draw_idle()

        # Connect motion and release events
        motion_id = self.canvas.mpl_connect('motion_notify_event', on_motion)
        release_id = self.canvas.mpl_connect('button_release_event', on_release)
    
    def pan_view(self, event):
        """Pan view based on mouse drag."""
        # Store initial position
        self.last_pan_x = event.x
        self.last_pan_y = event.y
        self._biosphere_pan_ts = 0.0

        def on_motion(event):
            if not hasattr(self, 'last_pan_x'):
                return

            dx = event.x - self.last_pan_x
            dy = event.y - self.last_pan_y

            # Get current limits
            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()

            # Calculate pan amount
            pan_factor = 0.01 * self.camera_distance
            x_pan = dx * pan_factor
            y_pan = dy * pan_factor

            # Update camera target
            self.camera_target = (
                self.camera_target[0] - x_pan,
                self.camera_target[1] + y_pan,
                self.camera_target[2]
            )

            # Update limits
            self.ax.set_xlim([xlim[0] - x_pan, xlim[1] - x_pan])
            self.ax.set_ylim([ylim[0] + y_pan, ylim[1] + y_pan])

            # Throttle to ~30fps
            import time as _t
            now = _t.time()
            if now - self._biosphere_pan_ts >= 0.033:
                self.canvas.draw_idle()
                self._biosphere_pan_ts = now

            # Update stored position
            self.last_pan_x = event.x
            self.last_pan_y = event.y

        def on_release(event):
            self.canvas.mpl_disconnect(motion_id)
            self.canvas.mpl_disconnect(release_id)
            self.canvas.draw_idle()

        # Connect motion and release events
        motion_id = self.canvas.mpl_connect('motion_notify_event', on_motion)
        release_id = self.canvas.mpl_connect('button_release_event', on_release)
    
    def on_motion(self, event):
        """Handle mouse motion."""
        # Update status with coordinates
        if hasattr(self, 'ax') and event.inaxes == self.ax:
            x, y, z = self._get_3d_coordinates(event.xdata, event.ydata)
            self.update_status(f"Position: ({x:.2f}, {y:.2f}, {z:.2f})")
    
    def on_scroll(self, event):
        """Handle mouse scroll for zoom."""
        if not hasattr(self, 'ax') or not hasattr(self, 'canvas'):
            return
        
        # Adjust camera distance
        zoom_factor = 1.1
        if event.button == 'up':
            self.camera_distance /= zoom_factor
        elif event.button == 'down':
            self.camera_distance *= zoom_factor
        
        # Clamp distance
        self.camera_distance = max(1, min(50, self.camera_distance))
        
        # Update view (simplified zoom)
        self.ax.set_xlim([-5*self.camera_distance/10, 5*self.camera_distance/10])
        self.ax.set_ylim([-5*self.camera_distance/10, 5*self.camera_distance/10])
        self.ax.set_zlim([-5*self.camera_distance/10, 5*self.camera_distance/10])

        self.canvas.draw_idle()

        self.update_status(f"Zoom: {self.camera_distance:.1f}x")
    
    def _get_3d_coordinates(self, x2d, y2d):
        """Convert 2D screen coordinates to approximate 3D coordinates."""
        # This is a simplified approximation
        # In a real app, you'd use proper inverse projection
        return x2d, y2d, 0
    
    def select_node(self, node: Node3D):
        """Select a node and show its details."""
        self.selected_node = node
        
        # Highlight the selected node
        self.redraw_scene()
        
        # Show node info in panel
        self.show_node_info(node)
        
        # Open detail popup
        self.show_node_popup(node)
        
        self.update_status(f"Selected: {node.name}")
    
    def clear_selection(self):
        """Clear current selection."""
        self.selected_node = None
        self.node_info_text.delete(1.0, tk.END)
        self.redraw_scene()
        self.update_status("Selection cleared")
    
    def show_node_info(self, node: Node3D):
        """Show node information in left panel."""
        self.node_info_text.delete(1.0, tk.END)
        
        info = f"┌─ {node.name} ─┐\n"
        info += f"Type: {node.node_type.name}\n"
        info += f"Layer: {node.layer.name}\n"
        info += f"Position: ({node.x:.2f}, {node.y:.2f}, {node.z:.2f})\n"
        info += f"ID: {node.id}\n\n"
        
        if node.data:
            info += "─ Hardware Info ─\n"
            for key, value in node.data.items():
                if isinstance(value, (str, int, float, bool)):
                    info += f"{key}: {value}\n"
                elif isinstance(value, list):
                    info += f"{key}: {len(value)} items\n"
        
        if node.metadata:
            info += "\n─ Metadata ─\n"
            for key, value in node.metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    info += f"{key}: {value}\n"
        
        if node.connections:
            info += f"\n─ Connections: {len(node.connections)} ─\n"
            for conn_id in node.connections[:5]:  # Show first 5
                info += f"• {conn_id}\n"
            if len(node.connections) > 5:
                info += f"... and {len(node.connections) - 5} more\n"
        
        if node.tooltip:
            info += f"\n─ Description ─\n{node.tooltip}\n"
        
        self.node_info_text.insert(1.0, info)
    
    def show_node_popup(self, node: Node3D):
        """Show detailed popup for node."""
        popup = tk.Toplevel(self.root)
        popup.title(f"Node Details: {node.name}")
        popup.geometry("600x500")
        
        # Make popup modal
        popup.transient(self.root)
        popup.grab_set()
        
        # Configure grid
        popup.columnconfigure(0, weight=1)
        popup.rowconfigure(1, weight=1)
        
        # Header
        header_frame = ttk.Frame(popup)
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        ttk.Label(header_frame, text=node.name, 
                 font=("Arial", 14, "bold")).pack(side=tk.LEFT)
        
        ttk.Label(header_frame, text=f"({node.node_type.name})",
                 font=("Arial", 10)).pack(side=tk.LEFT, padx=(10, 0))
        
        # Notebook for tabs
        notebook = ttk.Notebook(popup)
        notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        # Properties tab
        properties_frame = ttk.Frame(notebook)
        notebook.add(properties_frame, text="Properties")
        
        # Create scrollable text area
        text_scroll = scrolledtext.ScrolledText(properties_frame, wrap=tk.WORD)
        text_scroll.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Format and insert properties
        properties_text = self._format_node_properties(node)
        text_scroll.insert(1.0, properties_text)
        text_scroll.configure(state='disabled')
        
        # Hardware Details tab (if applicable)
        if node.data and 'component_type' in node.data:
            hardware_frame = ttk.Frame(notebook)
            notebook.add(hardware_frame, text="Hardware Details")
            
            hardware_text = scrolledtext.ScrolledText(hardware_frame, wrap=tk.WORD)
            hardware_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            hardware_info = self._format_hardware_info(node.data)
            hardware_text.insert(1.0, hardware_info)
            hardware_text.configure(state='disabled')
        
        # Files tab (for storage/bios nodes)
        if node.node_type in [NodeType.STORAGE, NodeType.BIOS]:
            files_frame = ttk.Frame(notebook)
            notebook.add(files_frame, text="System Files")
            
            files_text = scrolledtext.ScrolledText(files_frame, wrap=tk.WORD)
            files_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            files_info = self._get_system_files_info(node)
            files_text.insert(1.0, files_info)
            files_text.configure(state='disabled')
        
        # Close button
        button_frame = ttk.Frame(popup)
        button_frame.grid(row=2, column=0, pady=(0, 10))
        
        ttk.Button(button_frame, text="Close", 
                  command=popup.destroy).pack()
    
    def _format_node_properties(self, node: Node3D) -> str:
        """Format node properties for display."""
        props = []
        props.append(f"=== {node.name} ===")
        props.append(f"Type: {node.node_type.name}")
        props.append(f"Layer: {node.layer.name}")
        props.append(f"Position: X={node.x:.2f}, Y={node.y:.2f}, Z={node.z:.2f}")
        props.append(f"ID: {node.id}")
        props.append("")
        
        if node.metadata:
            props.append("=== Metadata ===")
            for key, value in node.metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    props.append(f"{key}: {value}")
                elif isinstance(value, dict):
                    props.append(f"{key}: [Dictionary with {len(value)} keys]")
                elif isinstance(value, list):
                    props.append(f"{key}: [List with {len(value)} items]")
            props.append("")
        
        if node.connections:
            props.append(f"=== Connections ({len(node.connections)}) ===")
            for i, conn_id in enumerate(node.connections[:20], 1):
                target_node = self.nodes.get(conn_id)
                if target_node:
                    props.append(f"{i:2d}. {target_node.name} ({conn_id})")
                else:
                    props.append(f"{i:2d}. {conn_id}")
            
            if len(node.connections) > 20:
                props.append(f"... and {len(node.connections) - 20} more")
            props.append("")
        
        if node.tooltip:
            props.append("=== Description ===")
            props.append(node.tooltip)
        
        return "\n".join(props)
    
    def _format_hardware_info(self, data: Dict) -> str:
        """Format hardware information for display."""
        if not data:
            return "No hardware data available."
        
        info = []
        info.append("=== Hardware Information ===")
        
        # Basic info
        basic_keys = ['component_type', 'name', 'manufacturer', 'model', 'serial', 'firmware', 'driver']
        for key in basic_keys:
            if key in data and data[key]:
                info.append(f"{key.replace('_', ' ').title()}: {data[key]}")
        
        # Properties
        if 'properties' in data and data['properties']:
            info.append("\n=== Properties ===")
            for key, value in data['properties'].items():
                if isinstance(value, (str, int, float, bool)):
                    info.append(f"{key}: {value}")
        
        # Capabilities
        if 'capabilities' in data and data['capabilities']:
            info.append("\n=== Capabilities ===")
            for cap in data['capabilities']:
                info.append(f"• {cap}")
        
        # BIOS info
        if 'bios_path' in data and data['bios_path']:
            info.append("\n=== BIOS/UEFI ===")
            info.append(f"Path: {data['bios_path']}")
            
            path = Path(data['bios_path'])
            if path.exists():
                try:
                    stat = path.stat()
                    info.append(f"Size: {stat.st_size:,} bytes")
                    info.append(f"Modified: {datetime.fromtimestamp(stat.st_mtime)}")
                except:
                    info.append("Size: Unknown (access error)")
            else:
                info.append("Status: File not found")
        
        return "\n".join(info)
    
    def _get_system_files_info(self, node: Node3D) -> str:
        """Get system files information for node."""
        info = []
        info.append("=== System Files ===")
        
        # Get files from hardware discovery
        files = []
        if node.data and 'system_files' in node.data:
            files = node.data['system_files']
        elif node.node_type == NodeType.BIOS:
            files = self.hardware_discovery.system_files[:50]  # First 50 files
        
        if not files:
            info.append("No system files found for this component.")
            return "\n".join(info)
        
        info.append(f"Found {len(files)} system files:")
        info.append("")
        
        for i, file_path in enumerate(files[:100], 1):  # Show first 100
            try:
                path = Path(file_path)
                if path.exists():
                    size = path.stat().st_size
                    modified = datetime.fromtimestamp(path.stat().st_mtime)
                    info.append(f"{i:3d}. {path.name}")
                    info.append(f"     Path: {path}")
                    info.append(f"     Size: {size:,} bytes")
                    info.append(f"     Modified: {modified}")
                    info.append("")
            except:
                info.append(f"{i:3d}. {file_path} [Access error]")
                info.append("")
        
        if len(files) > 100:
            info.append(f"... and {len(files) - 100} more files")
        
        return "\n".join(info)
    
    def on_view_mode_changed(self):
        """Handle view mode change."""
        self.view_mode = self.view_mode_var.get()
        self.redraw_scene()
        self.update_status(f"View mode: {self.view_mode}")
    
    def on_color_scheme_changed(self, event=None):
        """Handle color scheme change."""
        scheme = self.color_scheme_var.get()
        # Apply color scheme to nodes
        # This is simplified - in a real app you'd map colors properly
        self.redraw_scene()
        self.update_status(f"Color scheme: {scheme}")
    
    def start_animation(self):
        """Start the animation loop."""
        self.animation_running = True
        self.animation_thread = threading.Thread(target=self._animation_loop, daemon=True)
        self.animation_thread.start()
    
    def stop_animation(self):
        """Stop the animation loop."""
        self.animation_running = False
        if self.animation_thread:
            self.animation_thread.join(timeout=1)
    
    def _animation_loop(self):
        """Animation loop for pulsing connections."""
        while self.animation_running:
            try:
                # Update pulse phase
                speed = self.speed_var.get()
                self.pulse_phase += 0.05 * speed
                
                # Redraw if needed
                if any(conn.animated for conn in self.connections):
                    self.root.after(0, self.redraw_scene)
                
                # Sleep
                time.sleep(0.033)  # ~30 FPS
                
            except Exception as e:
                print(f"Animation error: {e}")
                break
    
    def update_status(self, message: str):
        """Update status label."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_label.config(text=f"[{timestamp}] {message}")
    
    def on_closing(self):
        """Handle window closing."""
        self.stop_animation()
        self.root.destroy()

# ============================================================================
# FILE EXPLORER INTEGRATION
# ============================================================================

class FileExplorerPopup:
    """Popup for exploring and analyzing files."""
    
    def __init__(self, parent, visualizer):
        self.parent = parent
        self.visualizer = visualizer
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the file explorer UI."""
        self.popup = tk.Toplevel(self.parent)
        self.popup.title("File Explorer & Analyzer")
        self.popup.geometry("800x600")
        
        # Configure grid
        self.popup.columnconfigure(0, weight=1)
        self.popup.rowconfigure(1, weight=1)
        
        # Top controls
        control_frame = ttk.Frame(self.popup)
        control_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        ttk.Label(control_frame, text="Path:").pack(side=tk.LEFT)
        
        self.path_var = tk.StringVar(value=str(Path.home()))
        path_entry = ttk.Entry(control_frame, textvariable=self.path_var, width=50)
        path_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="Browse", 
                  command=self.browse_directory).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="Analyze", 
                  command=self.analyze_selected).pack(side=tk.LEFT, padx=5)
        
        # Main content area
        content_frame = ttk.Frame(self.popup)
        content_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(0, weight=1)
        
        # File list
        file_frame = ttk.Frame(content_frame)
        file_frame.grid(row=0, column=0, sticky="nsew")
        
        # Treeview for files
        columns = ("name", "size", "type", "modified", "kingdom")
        self.tree = ttk.Treeview(file_frame, columns=columns, show="headings")
        
        # Define headings
        self.tree.heading("name", text="Name")
        self.tree.heading("size", text="Size")
        self.tree.heading("type", text="Type")
        self.tree.heading("modified", text="Modified")
        self.tree.heading("kingdom", text="Kingdom")
        
        # Define columns
        self.tree.column("name", width=200)
        self.tree.column("size", width=100)
        self.tree.column("type", width=100)
        self.tree.column("modified", width=150)
        self.tree.column("kingdom", width=100)
        
        # Scrollbars
        vsb = ttk.Scrollbar(file_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(file_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Grid layout
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        file_frame.rowconfigure(0, weight=1)
        file_frame.columnconfigure(0, weight=1)
        
        # Bottom buttons
        button_frame = ttk.Frame(self.popup)
        button_frame.grid(row=2, column=0, pady=(0, 10))
        
        ttk.Button(button_frame, text="Visualize in 3D", 
                  command=self.visualize_in_3d).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Close", 
                  command=self.popup.destroy).pack(side=tk.LEFT, padx=5)
        
        # Load initial directory
        self.load_directory(Path.home())
    
    def browse_directory(self):
        """Browse for directory."""
        directory = filedialog.askdirectory(
            initialdir=self.path_var.get(),
            title="Select Directory"
        )
        if directory:
            self.path_var.set(directory)
            self.load_directory(Path(directory))
    
    def load_directory(self, directory: Path):
        """Load directory contents into treeview."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add parent directory entry
        if directory.parent != directory:
            self.tree.insert("", "end", text="..", values=("..", "", "Directory", "", ""),
                           tags=("directory",))
        
        # List directory contents
        try:
            for item in directory.iterdir():
                try:
                    stat = item.stat()
                    size = stat.st_size
                    modified = datetime.fromtimestamp(stat.st_mtime)
                    
                    if item.is_dir():
                        file_type = "Directory"
                        kingdom = "Filesystem"
                        tags = ("directory",)
                    else:
                        file_type = self._get_file_type(item)
                        kingdom = self._guess_kingdom(item)
                        tags = ("file",)
                    
                    self.tree.insert("", "end", text=str(item),
                                   values=(item.name, self._format_size(size),
                                          file_type, modified.strftime("%Y-%m-%d %H:%M"),
                                          kingdom),
                                   tags=tags)
                except:
                    continue
                    
        except PermissionError:
            messagebox.showerror("Permission Denied", 
                                f"Cannot access directory: {directory}")
    
    def _get_file_type(self, path: Path) -> str:
        """Get file type from extension."""
        suffixes = path.suffixes
        if suffixes:
            return suffixes[-1].lstrip('.') + " file"
        return "File"
    
    def _guess_kingdom(self, path: Path) -> str:
        """Guess the kingdom based on file properties."""
        name = path.name.lower()
        suffix = path.suffix.lower()
        
        # Python files
        if suffix == '.py':
            # Try to guess from content
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(4096)
                    if 'import tkinter' in content or 'import PyQt' in content:
                        return "GUI"
                    elif 'import argparse' in content or 'sys.argv' in content:
                        return "CLI"
                    elif 'import flask' in content or 'import django' in content:
                        return "Web"
                    elif 'import pandas' in content or 'import numpy' in content:
                        return "Data"
                    else:
                        return "Script"
            except:
                return "Python"
        
        # Executables
        elif suffix in ['.exe', '.app', '.bin', '.so', '.dll']:
            return "Executable"
        
        # Configuration files
        elif suffix in ['.conf', '.config', '.ini', '.yml', '.yaml', '.json', '.toml']:
            return "Configuration"
        
        # Data files
        elif suffix in ['.csv', '.xlsx', '.db', '.sqlite', '.h5']:
            return "Data"
        
        # Document files
        elif suffix in ['.txt', '.md', '.pdf', '.doc', '.docx']:
            return "Document"
        
        # System files
        elif 'system' in name or 'sys' in name or path.parts[0] in ['/etc', '/var', '/proc']:
            return "System"
        
        return "Unknown"
    
    def _format_size(self, size: int) -> str:
        """Format file size."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
    
    def analyze_selected(self):
        """Analyze selected file."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a file to analyze.")
            return
        
        item = self.tree.item(selection[0])
        path = Path(self.path_var.get()) / item['text']
        
        if not path.exists():
            messagebox.showerror("File Not Found", f"File not found: {path}")
            return
        
        # Show analysis popup
        self.show_analysis_popup(path)
    
    def show_analysis_popup(self, path: Path):
        """Show detailed analysis popup for file."""
        popup = tk.Toplevel(self.popup)
        popup.title(f"Analysis: {path.name}")
        popup.geometry("700x500")
        
        # Configure grid
        popup.columnconfigure(0, weight=1)
        popup.rowconfigure(0, weight=1)
        
        # Create notebook
        notebook = ttk.Notebook(popup)
        notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # Properties tab
        props_frame = ttk.Frame(notebook)
        notebook.add(props_frame, text="Properties")
        
        props_text = scrolledtext.ScrolledText(props_frame, wrap=tk.WORD)
        props_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        props_info = self._get_file_properties(path)
        props_text.insert(1.0, props_info)
        props_text.configure(state='disabled')
        
        # Content tab (for text files)
        if path.suffix.lower() in ['.txt', '.py', '.md', '.json', '.xml', '.html', '.css', '.js']:
            content_frame = ttk.Frame(notebook)
            notebook.add(content_frame, text="Content")
            
            content_text = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD)
            content_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(50000)  # First 50KB
                    content_text.insert(1.0, content)
            except:
                content_text.insert(1.0, "Cannot read file content.")
            
            content_text.configure(state='disabled')
        
        # Analysis tab
        analysis_frame = ttk.Frame(notebook)
        notebook.add(analysis_frame, text="Taxonomic Analysis")
        
        analysis_text = scrolledtext.ScrolledText(analysis_frame, wrap=tk.WORD)
        analysis_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        analysis_info = self._analyze_file_taxonomy(path)
        analysis_text.insert(1.0, analysis_info)
        analysis_text.configure(state='disabled')
        
        # Close button
        ttk.Button(popup, text="Close", 
                  command=popup.destroy).grid(row=1, column=0, pady=(0, 10))
    
    def _get_file_properties(self, path: Path) -> str:
        """Get detailed file properties."""
        try:
            stat = path.stat()
            
            props = []
            props.append(f"=== File Properties ===")
            props.append(f"Name: {path.name}")
            props.append(f"Path: {path}")
            props.append(f"Size: {stat.st_size:,} bytes ({self._format_size(stat.st_size)})")
            props.append(f"Created: {datetime.fromtimestamp(stat.st_ctime)}")
            props.append(f"Modified: {datetime.fromtimestamp(stat.st_mtime)}")
            props.append(f"Accessed: {datetime.fromtimestamp(stat.st_atime)}")
            props.append(f"Type: {self._get_file_type(path)}")
            props.append(f"Extension: {path.suffix}")
            
            # Permissions (simplified)
            try:
                import os
                mode = stat.st_mode
                props.append(f"Permissions: {oct(mode)[-3:]}")
            except:
                pass
            
            # Hash
            try:
                import hashlib
                with open(path, 'rb') as f:
                    hash_md5 = hashlib.md5()
                    for chunk in iter(lambda: f.read(4096), b""):
                        hash_md5.update(chunk)
                    props.append(f"MD5: {hash_md5.hexdigest()}")
            except:
                props.append("MD5: Cannot compute")
            
            return "\n".join(props)
            
        except Exception as e:
            return f"Error getting properties: {e}"
    
    def _analyze_file_taxonomy(self, path: Path) -> str:
        """Analyze file for taxonomic classification."""
        analysis = []
        analysis.append(f"=== Taxonomic Analysis ===")
        analysis.append(f"File: {path.name}")
        analysis.append("")
        
        # Basic classification
        kingdom = self._guess_kingdom(path)
        analysis.append(f"Primary Kingdom: {kingdom}")
        
        # Size-based influence
        try:
            size = path.stat().st_size
            if size > 100 * 1024 * 1024:  # > 100MB
                influence = "HIGH"
            elif size > 10 * 1024 * 1024:  # > 10MB
                influence = "MEDIUM"
            else:
                influence = "LOW"
            analysis.append(f"Influence Level: {influence} (based on size)")
        except:
            analysis.append("Influence Level: UNKNOWN")
        
        # Location-based territories
        territories = []
        path_str = str(path)
        
        if '/etc/' in path_str or '\\Windows\\System32\\' in path_str:
            territories.append("System Configuration")
        if '/var/log/' in path_str or '\\Windows\\Logs\\' in path_str:
            territories.append("Logging")
        if '/usr/bin/' in path_str or '\\Windows\\' in path_str:
            territories.append("Executable Space")
        if '/home/' in path_str or '\\Users\\' in path_str:
            territories.append("User Space")
        if '/proc/' in path_str:
            territories.append("Process Information")
        
        if territories:
            analysis.append(f"Territories: {', '.join(territories)}")
        else:
            analysis.append("Territories: General Filesystem")
        
        # Content-based analysis for text files
        if path.suffix.lower() in ['.py', '.txt', '.md', '.sh', '.bat']:
            analysis.append("")
            analysis.append("=== Content Analysis ===")
            
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(10000)  # First 10KB
                    
                    # Count lines
                    lines = content.count('\n') + 1
                    analysis.append(f"Lines (sample): {lines}")
                    
                    # Look for patterns
                    patterns = {
                        'Network Operations': ['socket', 'http', 'requests', 'urllib'],
                        'File Operations': ['open(', 'read(', 'write(', 'os.path'],
                        'Process Operations': ['subprocess', 'Popen', 'os.system'],
                        'GUI Operations': ['tkinter', 'PyQt', 'wx', 'kivy'],
                        'Data Processing': ['pandas', 'numpy', 'json.', 'csv.'],
                        'Security Operations': ['hashlib', 'crypto', 'ssl', 'auth']
                    }
                    
                    for pattern_name, keywords in patterns.items():
                        count = sum(content.lower().count(kw.lower()) for kw in keywords)
                        if count > 0:
                            analysis.append(f"  {pattern_name}: {count} occurrences")
                            
            except:
                analysis.append("Cannot analyze content")
        
        analysis.append("")
        analysis.append("=== Recommended Actions ===")
        
        if kingdom == "System":
            analysis.append("• Handle with caution (system file)")
            analysis.append("• Backup before modification")
        elif kingdom == "Executable":
            analysis.append("• Verify source and integrity")
            analysis.append("• Scan for malware")
        elif kingdom in ["GUI", "Web", "Script"]:
            analysis.append("• Review code for security issues")
            analysis.append("• Test in isolated environment")
        else:
            analysis.append("• Standard file handling procedures")
        
        return "\n".join(analysis)
    
    def visualize_in_3d(self):
        """Visualize selected file in 3D space."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a file to visualize.")
            return
        
        item = self.tree.item(selection[0])
        path = Path(self.path_var.get()) / item['text']
        
        if not path.exists():
            messagebox.showerror("File Not Found", f"File not found: {path}")
            return
        
        # Create a file node in the 3D visualization
        self._add_file_to_visualization(path)
    
    def _add_file_to_visualization(self, path: Path):
        """Add file as a node to the 3D visualization."""
        try:
            stat = path.stat()
            size = stat.st_size
            
            # Create a unique ID for the file
            file_id = f"file_{hash(path) & 0xFFFFFFFF:08x}"
            
            # Position in the filesystem layer (z = 2 for filesystem layer)
            import random
            x = random.uniform(-3, 3)
            y = random.uniform(-3, 3)
            z = 2.0
            
            # Determine node type and color
            if path.is_dir():
                node_type = NodeType.DIRECTORY
                color = "#f39c12"  # Orange
            else:
                node_type = NodeType.FILE
                color = "#3498db"  # Blue
            
            # Determine size scaling
            node_size = 1.0 + math.log10(max(size, 1024)) / 2
            
            # Create node
            node = Node3D(
                id=file_id,
                name=path.name,
                node_type=node_type,
                layer=Layer.FILESYSTEM,
                x=x,
                y=y,
                z=z,
                size=node_size,
                color=color,
                alpha=0.8,
                data={
                    'path': str(path),
                    'size': size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'type': 'directory' if path.is_dir() else 'file'
                },
                tooltip=f"File: {path.name}\nSize: {self._format_size(size)}\nPath: {path}"
            )
            
            # Add to visualization
            self.visualizer.nodes[file_id] = node
            
            # Connect to kernel (center)
            conn = Connection3D(
                source_id="kernel",
                target_id=file_id,
                strength=0.3,
                color="#95a5a6",
                width=0.5,
                style=":",
                alpha=0.2
            )
            self.visualizer.connections.append(conn)
            
            # Redraw
            self.visualizer.redraw_scene()
            
            # Select the new node
            self.visualizer.select_node(node)
            
            self.visualizer.update_status(f"Added file to visualization: {path.name}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Cannot visualize file: {e}")

# ============================================================================
# MAIN APPLICATION
# ============================================================================

class DigitalBiosphereApp:
    """Main application class."""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the main application UI."""
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("Digital Biosphere Explorer")
            self.root.geometry("1200x800")
            # Create menu bar only if it's a top-level window
            self.create_menu_bar()
        
        # Configure grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Create main notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Create tabs — Context tab first so it's visible on open
        self.setup_debug_context_tab()   # index 0: debug/profile view
        self.setup_visualization_tab()   # index 1
        self.setup_explorer_tab()        # index 2 (fixed)
        self.setup_analysis_tab()        # index 3
        self.setup_system_tab()          # index 4
        self.setup_brain_map_tab()       # index 5: brain map (lazy, off by default)

        # Refresh context tree when user switches to it
        self.notebook.bind('<<NotebookTabChanged>>', self._on_notebook_tab_changed)
        
        # Status bar
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 5))
    
    def create_menu_bar(self):
        """Create menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open File...", command=self.open_file)
        file_menu.add_command(label="Open Directory...", command=self.open_directory)
        file_menu.add_separator()
        file_menu.add_command(label="Export Visualization...", command=self.export_visualization)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Reset View", command=self.reset_view)
        view_menu.add_command(label="Toggle Fullscreen", command=self.toggle_fullscreen)
        view_menu.add_separator()
        view_menu.add_command(label="Show Hardware Only", command=self.show_hardware_only)
        view_menu.add_command(label="Show All Layers", command=self.show_all_layers)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Scan Hardware", command=self.scan_hardware)
        tools_menu.add_command(label="Analyze System", command=self.analyze_system)
        tools_menu.add_command(label="Network Monitor", command=self.network_monitor)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Documentation", command=self.show_documentation)
        help_menu.add_command(label="About", command=self.show_about)
    
    def _on_notebook_tab_changed(self, event=None):
        """Refresh context tree when Context tab is selected."""
        try:
            selected = self.notebook.index(self.notebook.select())
            if selected == 0:  # Context tab
                self.refresh_context_tree()
        except Exception:
            pass

    def setup_debug_context_tab(self):
        """Setup the Debug Context tab as the first tab in the notebook.
        Shows a hierarchical profile tree: file → UI domain → UX events → diffs.
        Data sourced from logger_util.TAB_REGISTRY, UX_EVENT_LOG, and version_manifest.
        #[Mark:DEBUG_CONTEXT_TAB]
        """
        ctx_frame = ttk.Frame(self.notebook)
        self.notebook.add(ctx_frame, text="🔧 Context")
        ctx_frame.columnconfigure(0, weight=1)
        ctx_frame.rowconfigure(0, weight=1)

        # Toolbar
        toolbar = ttk.Frame(ctx_frame)
        toolbar.grid(row=1, column=0, sticky='ew', padx=5, pady=(0, 5))
        ttk.Button(toolbar, text="🔄 Refresh", command=self.refresh_context_tree, width=10).pack(side=tk.LEFT, padx=5)
        self.ctx_status_label = ttk.Label(toolbar, text="Click Refresh to load context", font=('Arial', 8))
        self.ctx_status_label.pack(side=tk.LEFT)

        # PanedWindow: left=tree, right=detail
        pane = ttk.PanedWindow(ctx_frame, orient=tk.HORIZONTAL)
        pane.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)

        # Left: Profile Treeview
        tree_frame = ttk.Frame(pane)
        pane.add(tree_frame, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self.ctx_tree = ttk.Treeview(tree_frame, show='tree', selectmode='browse')
        ctx_vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.ctx_tree.yview)
        self.ctx_tree.configure(yscrollcommand=ctx_vsb.set)
        self.ctx_tree.grid(row=0, column=0, sticky='nsew')
        ctx_vsb.grid(row=0, column=1, sticky='ns')

        # Tag styling
        self.ctx_tree.tag_configure('file_root', foreground='#61dafb', font=('Courier', 10, 'bold'))
        self.ctx_tree.tag_configure('domain_node', foreground='#ffcc66')
        self.ctx_tree.tag_configure('probe_node', foreground='#99ff99')
        self.ctx_tree.tag_configure('ux_node', foreground='#ff9966')
        self.ctx_tree.tag_configure('ux_error', foreground='#ff4444')
        self.ctx_tree.tag_configure('diff_node', foreground='#cc99ff')
        self.ctx_tree.tag_configure('history_node', foreground='#888888')
        self.ctx_tree.tag_configure('issue_node', foreground='#ffaa44')
        self.ctx_tree.tag_configure('static_node', foreground='#56d4e8')
        self.ctx_tree.tag_configure('import_node', foreground='#aaddff')
        self.ctx_tree.tag_configure('class_node', foreground='#ffdd88')
        self.ctx_tree.tag_configure('method_node', foreground='#cccccc')

        # Right: Detail panel
        detail_frame = ttk.Frame(pane)
        pane.add(detail_frame, weight=1)
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(0, weight=1)

        self.ctx_detail = tk.Text(
            detail_frame, bg='#1a1a2e', fg='#e0e0e0', font=('Courier', 9),
            relief=tk.FLAT, wrap=tk.WORD, state=tk.DISABLED
        )
        detail_vsb = ttk.Scrollbar(detail_frame, orient='vertical', command=self.ctx_detail.yview)
        self.ctx_detail.configure(yscrollcommand=detail_vsb.set)
        self.ctx_detail.grid(row=0, column=0, sticky='nsew')
        detail_vsb.grid(row=0, column=1, sticky='ns')

        # Bind selection → update detail; expand → lazy AST load
        self.ctx_tree.bind('<<TreeviewSelect>>', self._on_ctx_tree_select)
        self.ctx_tree.bind('<<TreeviewOpen>>', self._ctx_on_expand)

        # Store node detail data: iid → text string
        self._ctx_node_data = {}

        # Initial populate
        self.refresh_context_tree()

    def refresh_context_tree(self):
        """Populate the context tree with ALL files from manifest + TAB_REGISTRY + history.
        Files sorted by most recent change event (newest first).
        History branches read real timestamps from backup/history/{safe_key}/.
        #[Mark:DEBUG_CONTEXT_TAB]
        """
        try:
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            import logger_util
            import recovery_util
        except ImportError as e:
            self._ctx_set_detail(f"Cannot load context data: {e}")
            return

        for item in self.ctx_tree.get_children():
            self.ctx_tree.delete(item)
        self._ctx_node_data = {}

        manifest = {}
        try:
            manifest = recovery_util.load_version_manifest()
        except Exception:
            pass
        enriched = manifest.get('enriched_changes', {})
        registry = logger_util.TAB_REGISTRY

        # --- Build file list: all unique files from enriched_changes ---
        # file_path -> list of (event_id, change_dict)
        file_events_map = {}
        for eid, ch in enriched.items():
            fpath = ch.get('file', '')
            if not fpath:
                continue
            file_events_map.setdefault(fpath, []).append((eid, ch))

        # Also add any registry files not yet in enriched_changes
        for tname, treg in registry.items():
            src = treg.get('source_file', '') or ''
            if src and src not in file_events_map:
                file_events_map[src] = []

        if not file_events_map:
            no_data = self.ctx_tree.insert('', 'end', text='(No context data yet — launch tabs first)',
                                           tags=('history_node',))
            self._ctx_node_data[no_data] = (
                'No enriched_changes or TAB_REGISTRY entries found.\n\n'
                'Tabs populate TAB_REGISTRY on init.\n'
                'Changes are recorded by the live watcher after file saves.'
            )
            self.ctx_status_label.config(text="No data available")
            return

        # Sort files by most recent event timestamp (newest first)
        def _most_recent_ts(events):
            if not events:
                return ''
            return max(ch.get('timestamp', '') for _, ch in events)

        sorted_files = sorted(
            file_events_map.items(),
            key=lambda x: _most_recent_ts(x[1]),
            reverse=True
        )

        # Build reverse map: source_file basename → TAB_REGISTRY entry
        reg_by_basename = {}
        for tname, treg in registry.items():
            src = treg.get('source_file', '') or ''
            if src:
                bname = src.split('/')[-1]
                reg_by_basename[bname] = (tname, treg)

        # Locate backup/history root
        _here = os.path.dirname(os.path.abspath(__file__))
        _data_root = os.path.dirname(os.path.dirname(_here))
        history_root = os.path.join(_data_root, 'backup', 'history')

        shown_files = 0
        for fpath, fevents in sorted_files:
            fbasename = fpath.split('/')[-1]
            fevents_sorted = sorted(fevents, key=lambda x: x[1].get('timestamp', ''), reverse=True)

            # Look up TAB_REGISTRY entry for this file
            tname, treg = reg_by_basename.get(fbasename, (None, None))
            if treg is None:
                # Try partial match on path segment
                for bname, (tn, tr) in reg_by_basename.items():
                    if bname == fbasename:
                        tname, treg = tn, tr
                        break
            treg = treg or {}

            status = treg.get('status', 'UNKNOWN')
            status_icon = {'SUCCESS': '✓', 'FAILED': '✗', 'UNKNOWN': '?'}.get(status, '?')
            latest_ts = _most_recent_ts(fevents)
            ts_short = latest_ts[11:19] if latest_ts else 'N/A'
            tab_label = f"  [{tname}]" if tname else ''

            # Root: file node
            root_text = f"📄 {fbasename}  {ts_short}{tab_label}  [{status_icon}]"
            root_detail = (
                f"File Path:   {fpath}\n"
                f"Tab Name:    {tname or '(not registered)'}\n"
                f"Status:      {status}\n"
                f"Last Change: {latest_ts or 'N/A'}\n"
                f"Events:      {len(fevents)}\n"
            )
            if treg.get('timestamp'):
                root_detail += f"Init Time:   {treg['timestamp']}\n"
            root_iid = self.ctx_tree.insert('', 'end', text=root_text, tags=('file_root',),
                                            open=(shown_files == 0))
            self._ctx_node_data[root_iid] = root_detail
            shown_files += 1

            probe = treg.get('execution_probe') or {}

            # --- UI Domain branch ---
            domain = probe.get('domain', 'unknown')
            known_issues = probe.get('domain_known_issues', [])
            ws = treg.get('widget_profile') or {}
            counts = ws.get('widget_counts', {}) if isinstance(ws, dict) else {}
            domain_text = f"🏷 UI Domain: {domain}"
            domain_detail = (
                f"Domain:       {domain}\n"
                f"Known Issues: {', '.join(known_issues) if known_issues else 'none'}\n"
                f"Signals:      {', '.join(probe.get('domain_signal_checks', [])) or 'none'}\n\n"
                f"Widget Inventory:\n"
            )
            if counts:
                sorted_c = sorted(counts.items(), key=lambda x: -x[1])
                domain_detail += '\n'.join(f"  {k}: {v}" for k, v in sorted_c[:12])
            else:
                domain_detail += '  (none recorded)'
            domain_iid = self.ctx_tree.insert(root_iid, 'end', text=domain_text, tags=('domain_node',))
            self._ctx_node_data[domain_iid] = domain_detail
            for issue in known_issues:
                iss_iid = self.ctx_tree.insert(domain_iid, 'end', text=f"  ⚠ {issue}", tags=('issue_node',))
                self._ctx_node_data[iss_iid] = f"Known Issue: {issue}\nDomain: {domain}"

            # Domain history — read backup/history/ for this file
            safe_key = fpath.replace('/', '_')
            hist_dir = os.path.join(history_root, safe_key)
            hist_dom_iid = self.ctx_tree.insert(domain_iid, 'end', text='─ history ─', tags=('history_node',))
            if os.path.isdir(hist_dir):
                snapshots = sorted(
                    [f for f in os.listdir(hist_dir) if f.endswith('.py')],
                    reverse=True
                )
                hist_detail = f"Snapshots in backup/history/{safe_key}/\n({len(snapshots)} total):\n\n"
                hist_detail += '\n'.join(f"  {s[:-3]}" for s in snapshots[:30])
                if len(snapshots) > 30:
                    hist_detail += f"\n  ... ({len(snapshots)-30} more)"
                self._ctx_node_data[hist_dom_iid] = hist_detail
                # Show latest 5 snapshot timestamps as children
                for snap in snapshots[:5]:
                    snap_iid = self.ctx_tree.insert(hist_dom_iid, 'end',
                                                    text=f"  📋 {snap[:-3]}", tags=('history_node',))
                    snap_path = os.path.join(hist_dir, snap)
                    snap_size = os.path.getsize(snap_path) if os.path.exists(snap_path) else 0
                    self._ctx_node_data[snap_iid] = (
                        f"Snapshot: {snap}\n"
                        f"Path: {snap_path}\n"
                        f"Size: {snap_size:,} bytes\n"
                    )
                if len(snapshots) > 5:
                    more_iid = self.ctx_tree.insert(hist_dom_iid, 'end',
                                                    text=f"  … {len(snapshots)-5} more snapshots",
                                                    tags=('history_node',))
                    self._ctx_node_data[more_iid] = hist_detail
            else:
                self._ctx_node_data[hist_dom_iid] = (
                    f"No backup/history directory found for:\n{safe_key}\n\n"
                    f"Expected path:\n{hist_dir}"
                )

            # --- Exec Probe branch ---
            p_status = probe.get('probe_status', 'N/A')
            ok = len(probe.get('methods_ok', []))
            total = ok + len(probe.get('methods_missing', []))
            probe_icon = {'PASS': '✓', 'WARN': '⚠', 'FAIL': '✗'}.get(p_status, '?')
            probe_text = f"🔧 Exec Probe: {probe_icon} {p_status} ({ok}/{total} methods)"
            probe_detail = (
                f"Probe Status:  {p_status}\n"
                f"Methods OK:    {ok}/{total}\n"
            )
            missing = probe.get('methods_missing', [])
            if missing:
                probe_detail += f"Missing ({len(missing)}):\n" + '\n'.join(f"  {m}" for m in missing)
            blank = probe.get('blank_panels', [])
            if blank:
                probe_detail += f"\nBlank panels ({len(blank)}):\n" + '\n'.join(f"  {b}" for b in blank[:10])
            unbound = probe.get('callbacks_unbound', [])
            if unbound:
                probe_detail += f"\nUnbound callbacks ({len(unbound)}):\n" + '\n'.join(f"  {u}" for u in unbound[:10])
            probe_iid = self.ctx_tree.insert(root_iid, 'end', text=probe_text, tags=('probe_node',))
            self._ctx_node_data[probe_iid] = probe_detail
            # Show up to 6 missing methods as children
            for m in missing[:6]:
                m_iid = self.ctx_tree.insert(probe_iid, 'end', text=f"  ✗ {m}", tags=('ux_error',))
                self._ctx_node_data[m_iid] = (
                    f"Missing method: {m}\n"
                    f"Not found on instance of: {tname or fbasename}\n"
                    f"Probe status: {p_status}"
                )
            # Probe history (snapshot count from disk)
            hist_probe_iid = self.ctx_tree.insert(probe_iid, 'end', text='─ history ─', tags=('history_node',))
            if os.path.isdir(hist_dir):
                snapshots = sorted([f for f in os.listdir(hist_dir) if f.endswith('.py')], reverse=True)
                self._ctx_node_data[hist_probe_iid] = (
                    f"Probe is re-run each launch.\n"
                    f"Source snapshots available: {len(snapshots)}\n"
                    f"Most recent: {snapshots[0][:-3] if snapshots else 'none'}\n\n"
                    f"Probe results are stored per-session in TAB_REGISTRY."
                )
            else:
                self._ctx_node_data[hist_probe_iid] = 'No backup snapshots found for this file.'

            # --- UX Events branch ---
            ux_events = [e for e in logger_util.UX_EVENT_LOG if e.get('tab') == tname] if tname else []
            ux_errors = [e for e in ux_events if e.get('outcome') == 'error']
            ux_text = f"⚡ UX Events ({len(ux_events)} fired, {len(ux_errors)} errors)"
            ux_detail = f"Tab: {tname or '(not registered)'}\nTotal fired: {len(ux_events)}\nErrors: {len(ux_errors)}\n\nAll events (newest first):\n"
            for ev in reversed(ux_events[-50:]):
                icon = '✓' if ev.get('outcome') == 'fired' else '✗'
                ux_detail += f"  {ev.get('timestamp','')}  {icon} {ev.get('widget','?')} → {ev.get('outcome','?')}"
                if ev.get('detail'):
                    ux_detail += f": {ev['detail']}"
                ux_detail += '\n'
            ux_iid = self.ctx_tree.insert(root_iid, 'end', text=ux_text, tags=('ux_node',))
            self._ctx_node_data[ux_iid] = ux_detail
            for ev in reversed(ux_events[-8:]):
                icon = '✓' if ev.get('outcome') == 'fired' else '✗'
                tag = 'ux_error' if ev.get('outcome') == 'error' else 'history_node'
                ev_text = f"  {ev.get('timestamp','')}  {icon} {ev.get('widget','?')} → {ev.get('outcome','?')}"
                ev_detail = '\n'.join(f"{k}: {v}" for k, v in ev.items())
                ev_iid = self.ctx_tree.insert(ux_iid, 'end', text=ev_text, tags=(tag,))
                self._ctx_node_data[ev_iid] = ev_detail
            hist_ux_iid = self.ctx_tree.insert(ux_iid, 'end', text='─ history ─ (all)', tags=('history_node',))
            self._ctx_node_data[hist_ux_iid] = ux_detail

            # --- Static Analysis branch (imports + classes + verbs via StaticAnalyzer) ---
            # Insert a placeholder child so the node shows an expand arrow.
            # Actual AST parse runs lazily on <<TreeviewOpen>> via _ctx_on_expand().
            static_iid = self.ctx_tree.insert(root_iid, 'end',
                                              text='🔬 Static Analysis  (expand to load)',
                                              tags=('static_node',))
            self._ctx_node_data[static_iid] = (
                f"Static analysis of {fbasename}.\n"
                f"Expand to run StaticAnalyzer (imports / classes / methods / verbs)."
            )
            # Store the real file path in the tag so expand handler can find it
            self.ctx_tree.item(static_iid, tags=('static_node', f'_fpath:{fpath}'))
            # Placeholder child — triggers the tree expand arrow
            _ph = self.ctx_tree.insert(static_iid, 'end', text='…', tags=('history_node',))
            self._ctx_node_data[_ph] = 'Loading…'

            # --- Diffs branch (all enriched_changes for this file) ---
            diff_text = f"📑 Diffs ({len(fevents_sorted)} events)"
            diff_detail = f"Change events for {fbasename}:\n\n"
            for eid, ch in fevents_sorted:
                diff_detail += (
                    f"{eid}: {ch.get('verb','?')} +{ch.get('additions',0)}/-{ch.get('deletions',0)} "
                    f"[{ch.get('risk_level','?')}] {ch.get('timestamp','')}\n"
                )
            diff_iid = self.ctx_tree.insert(root_iid, 'end', text=diff_text, tags=('diff_node',))
            self._ctx_node_data[diff_iid] = diff_detail
            for eid, ch in fevents_sorted[:8]:
                risk = ch.get('risk_level', 'UNKNOWN')
                risk_sym = {'CRITICAL': '🔴', 'HIGH': '🟠', 'MEDIUM': '🟡', 'LOW': '🟢'}.get(risk, '⚪')
                additions = ch.get('additions', 0)
                deletions = ch.get('deletions', 0)
                ts = ch.get('timestamp', '')
                ts_short2 = ts[11:19] if ts else ''
                diff_entry_text = f"  {risk_sym} {eid}  {ts_short2}  {ch.get('verb','?')} +{additions}/-{deletions}"
                diff_entry_detail = '\n'.join(f"{k}: {v}" for k, v in ch.items() if k != 'diff_text')
                diff_entry_iid = self.ctx_tree.insert(diff_iid, 'end', text=diff_entry_text, tags=('diff_node',))
                self._ctx_node_data[diff_entry_iid] = diff_entry_detail

        total_files = shown_files
        ux_total = len(logger_util.UX_EVENT_LOG)
        total_events = sum(len(v) for v in file_events_map.values())
        self.ctx_status_label.config(
            text=f"{total_files} files | {total_events} diffs | {ux_total} UX events | sorted newest first"
        )

    def _on_ctx_tree_select(self, event=None):
        """Update detail panel when a context tree node is selected."""
        selection = self.ctx_tree.selection()
        if not selection:
            return
        iid = selection[0]
        detail = self._ctx_node_data.get(iid, '')
        self._ctx_set_detail(detail)

    def _ctx_set_detail(self, text):
        """Set the context detail text widget content."""
        self.ctx_detail.config(state=tk.NORMAL)
        self.ctx_detail.delete('1.0', tk.END)
        self.ctx_detail.insert(tk.END, text)
        self.ctx_detail.config(state=tk.DISABLED)

    def _ctx_on_expand(self, event=None):
        """Lazy-load StaticAnalyzer branches when a static_node is expanded.
        #[Mark:STATIC_ANALYSIS_LAZY]
        """
        iid = self.ctx_tree.focus()
        if not iid:
            return
        tags = self.ctx_tree.item(iid, 'tags')
        # Find the _fpath tag
        fpath = None
        for t in tags:
            if t.startswith('_fpath:'):
                fpath = t[len('_fpath:'):]
                break
        if fpath is None:
            return
        # Check if already loaded (placeholder child removed)
        children = self.ctx_tree.get_children(iid)
        if not children:
            return
        first_child_text = self.ctx_tree.item(children[0], 'text')
        if first_child_text != '…':
            return  # already expanded
        # Remove placeholder and run analysis
        self.ctx_tree.delete(children[0])
        self._ctx_load_static_analysis(iid, fpath)

    def _ctx_load_static_analysis(self, parent_iid, fpath):
        """Run StaticAnalyzer on fpath and populate imports/classes/methods branches.
        #[Mark:STATIC_ANALYSIS_LAZY]
        """
        import os
        try:
            import sys as _sys
            _here = os.path.dirname(os.path.abspath(__file__))
            if _here not in _sys.path:
                _sys.path.insert(0, _here)
            from py_manifest_augmented import StaticAnalyzer
        except ImportError as e:
            err_iid = self.ctx_tree.insert(parent_iid, 'end',
                                           text=f'  ⚠ StaticAnalyzer unavailable: {e}',
                                           tags=('ux_error',))
            self._ctx_node_data[err_iid] = str(e)
            return

        # Resolve absolute path.
        # _here = .../Trainer/Data/tabs/map_tab
        # enriched_changes paths look like: "Data/tabs/map_tab/foo.py" or "/abs/path"
        abs_fpath = fpath
        if not os.path.isabs(fpath):
            # Parent of Data/ is /Trainer — join directly with relative path
            _trainer_root = os.path.dirname(os.path.dirname(os.path.dirname(_here)))
            abs_fpath = os.path.join(_trainer_root, fpath)
            # If that still doesn't exist, try treating path as relative to Data/
            if not os.path.isfile(abs_fpath):
                _data_root = os.path.dirname(os.path.dirname(_here))
                abs_fpath = os.path.join(_data_root, os.path.basename(fpath))

        if not os.path.isfile(abs_fpath):
            err_iid = self.ctx_tree.insert(parent_iid, 'end',
                                           text=f'  ⚠ File not found: {fpath}',
                                           tags=('ux_error',))
            self._ctx_node_data[err_iid] = f'Could not locate: {abs_fpath}'
            return

        try:
            src = open(abs_fpath, encoding='utf-8', errors='replace').read()
        except Exception as e:
            err_iid = self.ctx_tree.insert(parent_iid, 'end',
                                           text=f'  ⚠ Read error: {e}', tags=('ux_error',))
            self._ctx_node_data[err_iid] = str(e)
            return

        analyzer = StaticAnalyzer(abs_fpath, src)
        imports, classes, funcs, attrs, cfs, errs = analyzer.analyze()

        # Verb colour map
        _verb_color = {
            'CREATE': '🟢', 'READ': '🔵', 'UPDATE': '🟡',
            'DELETE': '🔴', 'VALIDATE': '🟣', 'CALCULATE': '🩵', 'OTHER': '⚪'
        }

        # --- Imports branch ---
        ext_imps = [i for i in imports if not i.resolved_local]
        loc_imps = [i for i in imports if i.resolved_local]
        imp_text = f"📦 Imports ({len(imports)}: {len(loc_imps)} local, {len(ext_imps)} external)"
        imp_detail = f"Total imports: {len(imports)}\nLocal: {len(loc_imps)}\nExternal: {len(ext_imps)}\n\n"
        imp_detail += '\n'.join(
            f"  {'←' if i.resolved_local else '↗'} {i.module}{'.' + i.name if i.is_from and i.name != i.module else ''}  (line {i.line})"
            for i in imports[:60]
        )
        imp_iid = self.ctx_tree.insert(parent_iid, 'end', text=imp_text, tags=('import_node',))
        self._ctx_node_data[imp_iid] = imp_detail
        for imp in imports[:20]:
            arrow = '←' if imp.resolved_local else '↗'
            mod_label = imp.module
            if imp.is_from and imp.name and imp.name != imp.module:
                mod_label = f"{imp.module}.{imp.name}"
            alias = f" as {imp.alias}" if imp.alias else ''
            i_iid = self.ctx_tree.insert(imp_iid, 'end',
                                         text=f"  {arrow} {mod_label}{alias}  L{imp.line}",
                                         tags=('import_node',))
            self._ctx_node_data[i_iid] = (
                f"Module:   {imp.module}\n"
                f"Name:     {imp.name}\n"
                f"Alias:    {imp.alias or '—'}\n"
                f"Line:     {imp.line}\n"
                f"Local:    {imp.resolved_local or '(external)'}\n"
                f"from:     {imp.is_from}"
            )
        if len(imports) > 20:
            more_iid = self.ctx_tree.insert(imp_iid, 'end',
                                            text=f"  … {len(imports)-20} more",
                                            tags=('history_node',))
            self._ctx_node_data[more_iid] = imp_detail

        # --- Classes branch ---
        cls_text = f"🏛 Classes ({len(classes)})"
        cls_detail = f"Classes in {os.path.basename(abs_fpath)}:\n\n"
        for c in classes:
            bases = ', '.join(c.bases) if c.bases else 'object'
            cls_detail += f"  {c.name}({bases})  L{c.line}-{c.end_line}  [{len(c.methods)} methods]\n"
        cls_iid = self.ctx_tree.insert(parent_iid, 'end', text=cls_text, tags=('class_node',))
        self._ctx_node_data[cls_iid] = cls_detail if classes else 'No classes defined (module-level code only).'

        for cls in classes:
            bases_str = ', '.join(cls.bases) if cls.bases else 'object'
            verb_counts = {}
            for m in cls.methods:
                v = m.verb_category.name if hasattr(m.verb_category, 'name') else str(m.verb_category)
                verb_counts[v] = verb_counts.get(v, 0) + 1
            verb_summary = ' '.join(f"{_verb_color.get(v,'⚪')}{n}" for v, n in verb_counts.items())
            c_iid = self.ctx_tree.insert(cls_iid, 'end',
                                         text=f"  {cls.name}({bases_str})  {verb_summary}",
                                         tags=('class_node',))
            self._ctx_node_data[c_iid] = (
                f"Class:    {cls.name}\n"
                f"Bases:    {bases_str}\n"
                f"Lines:    {cls.line}–{cls.end_line}\n"
                f"Methods:  {len(cls.methods)}\n"
                f"Attrs:    {len(cls.attributes)}\n"
                f"Complexity: {cls.complexity}\n\n"
                f"Verb breakdown:\n" +
                '\n'.join(f"  {_verb_color.get(v,'⚪')} {v}: {n}" for v, n in verb_counts.items())
            )
            for method in cls.methods[:30]:
                v = method.verb_category.name if hasattr(method.verb_category, 'name') else str(method.verb_category)
                async_mark = 'async ' if method.is_async else ''
                prop_mark = '@prop ' if method.is_property else ''
                m_iid = self.ctx_tree.insert(c_iid, 'end',
                                             text=f"    {_verb_color.get(v,'⚪')} {prop_mark}{async_mark}{method.name}()  L{method.line}",
                                             tags=('method_node',))
                self._ctx_node_data[m_iid] = (
                    f"Method:  {method.qualname}\n"
                    f"Verb:    {v}\n"
                    f"Args:    {', '.join(method.args)}\n"
                    f"Lines:   {method.line}–{method.end_line}\n"
                    f"Returns: {method.returns or '—'}\n"
                    f"Async:   {method.is_async}\n"
                    f"Property:{method.is_property}\n"
                    f"Decorators: {', '.join(method.decorators) or '—'}\n"
                )
            if len(cls.methods) > 30:
                rest_iid = self.ctx_tree.insert(c_iid, 'end',
                                                text=f"    … {len(cls.methods)-30} more methods",
                                                tags=('history_node',))
                self._ctx_node_data[rest_iid] = f"Total methods: {len(cls.methods)}"

        # --- Module-level functions branch (if any) ---
        if funcs:
            mf_text = f"⚙ Module Functions ({len(funcs)})"
            mf_detail = '\n'.join(
                f"  {_verb_color.get(f.verb_category.name if hasattr(f.verb_category,'name') else str(f.verb_category),'⚪')} "
                f"{f.name}()  L{f.line}"
                for f in funcs
            )
            mf_iid = self.ctx_tree.insert(parent_iid, 'end', text=mf_text, tags=('class_node',))
            self._ctx_node_data[mf_iid] = mf_detail
            for f in funcs[:20]:
                v = f.verb_category.name if hasattr(f.verb_category, 'name') else str(f.verb_category)
                f_iid = self.ctx_tree.insert(mf_iid, 'end',
                                             text=f"  {_verb_color.get(v,'⚪')} {f.name}()  L{f.line}",
                                             tags=('method_node',))
                self._ctx_node_data[f_iid] = (
                    f"Function: {f.name}\n"
                    f"Verb:     {v}\n"
                    f"Args:     {', '.join(f.args)}\n"
                    f"Lines:    {f.line}–{f.end_line}\n"
                    f"Returns:  {f.returns or '—'}\n"
                )

        # Update static node label now that it's loaded
        fname = os.path.basename(abs_fpath)
        self.ctx_tree.item(parent_iid, text=(
            f"🔬 Static Analysis  {len(imports)} imports | {len(classes)} classes | {len(funcs)} module fns"
        ))
        self._ctx_node_data[parent_iid] = (
            f"StaticAnalyzer results for {fname}:\n\n"
            f"  Imports:  {len(imports)} ({len(loc_imps)} local, {len(ext_imps)} external)\n"
            f"  Classes:  {len(classes)}\n"
            f"  Methods:  {sum(len(c.methods) for c in classes)}\n"
            f"  Mod fns:  {len(funcs)}\n"
            f"  Attrs:    {len(attrs)}\n"
            f"  Errors:   {len(errs)}\n"
        )
        if errs:
            for e in errs[:3]:
                err_iid = self.ctx_tree.insert(parent_iid, 'end',
                                               text=f'  ⚠ Parse error: {e[:60]}',
                                               tags=('ux_error',))
                self._ctx_node_data[err_iid] = e

    def setup_visualization_tab(self):
        """Setup the 3D visualization tab."""
        self.viz_frame = ttk.Frame(self.notebook)
        self.viz_frame.columnconfigure(0, weight=1)
        self.viz_frame.rowconfigure(0, weight=1)
        self.notebook.add(self.viz_frame, text="3D Visualization")

        # DigitalBiosphereVisualizer.__init__ calls setup_ui() which packs
        # main_container into self.root (= self.viz_frame). No second pack needed.
        self.visualizer = DigitalBiosphereVisualizer(self.viz_frame)
    
    def setup_explorer_tab(self):
        """Setup the file explorer tab — builds directly into frame (no Toplevel).
        #[Mark:EXPLORER_FIX] Previous implementation used FileExplorerPopup which always
        created a tk.Toplevel, making widgets invisible inside the notebook tab.
        """
        self.explorer_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.explorer_frame, text="File Explorer")
        self._build_explorer_content(self.explorer_frame)

    def _build_explorer_content(self, parent):
        """Build file explorer widgets directly into parent frame."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Top controls
        control_frame = ttk.Frame(parent)
        control_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        ttk.Label(control_frame, text="Path:").pack(side=tk.LEFT)
        self.explorer_path_var = tk.StringVar(value=str(Path.home()))
        path_entry = ttk.Entry(control_frame, textvariable=self.explorer_path_var, width=50)
        path_entry.pack(side=tk.LEFT, padx=5)
        path_entry.bind('<Return>', lambda e: self._explorer_load_dir(Path(self.explorer_path_var.get())))
        ttk.Button(control_frame, text="Browse", command=self._explorer_browse).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Analyze", command=self._explorer_analyze).pack(side=tk.LEFT, padx=5)

        # Treeview + scrollbars
        content_frame = ttk.Frame(parent)
        content_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(0, weight=1)

        columns = ("size", "type", "modified", "kingdom")
        self.explorer_tree = ttk.Treeview(content_frame, columns=columns, show="tree headings")
        self.explorer_tree.heading("#0", text="Name", anchor='w')
        self.explorer_tree.heading("size", text="Size", anchor='e')
        self.explorer_tree.heading("type", text="Type", anchor='w')
        self.explorer_tree.heading("modified", text="Modified", anchor='w')
        self.explorer_tree.heading("kingdom", text="Kingdom", anchor='w')
        self.explorer_tree.column("#0", width=220, anchor='w')
        self.explorer_tree.column("size", width=80, anchor='e')
        self.explorer_tree.column("type", width=80, anchor='w')
        self.explorer_tree.column("modified", width=140, anchor='w')
        self.explorer_tree.column("kingdom", width=100, anchor='w')

        vsb = ttk.Scrollbar(content_frame, orient="vertical", command=self.explorer_tree.yview)
        hsb = ttk.Scrollbar(content_frame, orient="horizontal", command=self.explorer_tree.xview)
        self.explorer_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.explorer_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        # Lazy expand on open
        self.explorer_tree.bind('<<TreeviewOpen>>', self._explorer_on_expand)

        # Bottom buttons
        btn_frame = ttk.Frame(parent)
        btn_frame.grid(row=2, column=0, pady=(0, 10))
        ttk.Button(btn_frame, text="Visualize in 3D", command=self._explorer_visualize_3d).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🔄 Refresh", command=self._explorer_refresh).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="📌 Pinned", command=self._explorer_load_pinned).pack(side=tk.LEFT, padx=5)

        # Load pinned root view (Trainer + Home + /)
        self._explorer_load_pinned()

    def _explorer_load_dir(self, path):
        """Load a directory into explorer_tree with lazy expansion."""
        for item in self.explorer_tree.get_children():
            self.explorer_tree.delete(item)
        try:
            path = Path(path)
            self.explorer_path_var.set(str(path))
            self._explorer_insert_dir(path, '')
        except Exception as e:
            self.explorer_tree.insert('', 'end', text=f"Error: {e}", values=('', '', '', ''))

    def _explorer_insert_dir(self, path, parent_iid):
        """Insert directory contents into explorer_tree under parent_iid."""
        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            self.explorer_tree.insert(parent_iid, 'end', text="(permission denied)", values=('', '', '', ''))
            return
        except Exception:
            return
        for entry in entries[:200]:  # Cap at 200 entries per dir
            try:
                stat = entry.stat()
                size_str = f"{stat.st_size:,}" if entry.is_file() else ''
                ftype = 'dir' if entry.is_dir() else entry.suffix.lstrip('.') or 'file'
                from datetime import datetime as _dt
                modified = _dt.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                kingdom = self._explorer_classify(entry)
                iid = self.explorer_tree.insert(
                    parent_iid, 'end',
                    text=('📁 ' if entry.is_dir() else '📄 ') + entry.name,
                    values=(size_str, ftype, modified, kingdom),
                    tags=('dir_node',) if entry.is_dir() else ('file_node',)
                )
                # Insert placeholder child for lazy expansion of dirs
                if entry.is_dir():
                    try:
                        has_children = any(True for _ in entry.iterdir())
                    except Exception:
                        has_children = False
                    if has_children:
                        self.explorer_tree.insert(iid, 'end', text='...', values=('', '', '', ''),
                                                  tags=('placeholder',))
                        self.explorer_tree.item(iid, open=False)
                        # Store path in item tags for lazy load
                        self.explorer_tree.item(iid, tags=('dir_node', str(entry)))
            except Exception:
                continue

    def _explorer_on_expand(self, event):
        """Lazy-load directory children when a dir/pinned node is opened."""
        item = self.explorer_tree.focus()
        tags = self.explorer_tree.item(item, 'tags')
        children = self.explorer_tree.get_children(item)
        # Check if first child is a placeholder
        if not children:
            return
        first_tags = self.explorer_tree.item(children[0], 'tags')
        if 'placeholder' not in first_tags:
            return
        # Get path from second tag (stored as string in both dir_node and pinned_root)
        path_str = tags[1] if len(tags) > 1 else None
        if path_str:
            self.explorer_tree.delete(children[0])
            self._explorer_insert_dir(Path(path_str), item)
            # Update path entry to show expanded directory
            self.explorer_path_var.set(path_str)

    def _explorer_classify(self, path):
        """Classify a file into biosphere kingdom for the kingdom column."""
        if path.is_dir():
            return 'directory'
        ext = path.suffix.lower()
        if ext in ('.py', '.js', '.ts', '.go', '.rs', '.c', '.cpp', '.java'):
            return 'script'
        elif ext in ('.json', '.yaml', '.toml', '.ini', '.cfg', '.conf'):
            return 'config'
        elif ext in ('.so', '.dll', '.dylib'):
            return 'library'
        elif ext in ('.txt', '.md', '.rst'):
            return 'document'
        elif ext in ('.png', '.jpg', '.svg', '.gif'):
            return 'media'
        return 'entity'

    def _explorer_load_pinned(self):
        """Load pinned root locations: /Trainer project, Home, and filesystem root.
        #[Mark:EXPLORER_PINNED_ROOTS]
        """
        for item in self.explorer_tree.get_children():
            self.explorer_tree.delete(item)

        import os as _os
        # Resolve /Trainer root from this file's location
        _here = Path(_os.path.abspath(__file__)).parent   # map_tab/
        _data = _here.parent.parent                        # Data/
        _trainer = _data.parent                            # Trainer/

        pinned = [
            ('📌 /Trainer  (project root)', _trainer),
            ('🏠 Home  (~)', Path.home()),
            ('💾 Filesystem  (/)', Path('/')),
        ]

        for label, root_path in pinned:
            try:
                pin_iid = self.explorer_tree.insert(
                    '', 'end',
                    text=label,
                    values=('', 'pinned', '', ''),
                    tags=('pinned_root', str(root_path)),
                    open=False
                )
                # Insert placeholder so expand arrow shows
                try:
                    has_children = any(True for _ in root_path.iterdir())
                except Exception:
                    has_children = True
                if has_children:
                    self.explorer_tree.insert(pin_iid, 'end', text='...', values=('', '', '', ''),
                                              tags=('placeholder',))
            except Exception as e:
                self.explorer_tree.insert('', 'end', text=f"⚠ {label}: {e}", values=('', '', '', ''))

        self.explorer_path_var.set('(pinned roots)')

    def _explorer_refresh(self):
        """Refresh current explorer view."""
        current = self.explorer_path_var.get()
        if current in ('(pinned roots)', ''):
            self._explorer_load_pinned()
        else:
            try:
                self._explorer_load_dir(Path(current))
            except Exception:
                self._explorer_load_pinned()

    def _explorer_browse(self):
        """Open browse dialog to change explorer directory."""
        try:
            from tkinter import filedialog
            directory = filedialog.askdirectory(title="Browse Directory",
                                                initialdir=self.explorer_path_var.get())
            if directory:
                self._explorer_load_dir(Path(directory))
        except Exception as e:
            pass

    def _explorer_analyze(self):
        """Analyze selected file/directory in the explorer."""
        selection = self.explorer_tree.selection()
        if not selection:
            return
        item = selection[0]
        name = self.explorer_tree.item(item, 'text').lstrip('📁 📄 ')
        tags = self.explorer_tree.item(item, 'tags')
        path_str = tags[1] if len(tags) > 1 else None
        try:
            from tkinter import messagebox
            if path_str:
                p = Path(path_str)
                messagebox.showinfo("Analysis", f"Path: {p}\nSize: {p.stat().st_size if p.is_file() else 'dir'}")
        except Exception:
            pass

    def _explorer_visualize_3d(self):
        """Switch to 3D viz tab with selected item loaded."""
        self.notebook.select(1)  # 3D Visualization tab
    
    def setup_analysis_tab(self):
        """Setup the analysis tab."""
        analysis_frame = ttk.Frame(self.notebook)
        self.notebook.add(analysis_frame, text="Analysis")
        
        # Analysis content
        ttk.Label(analysis_frame, text="System Analysis Dashboard", 
                 font=("Arial", 14, "bold")).pack(pady=20)
        
        # Create analysis widgets
        self.setup_analysis_widgets(analysis_frame)
    
    def setup_analysis_widgets(self, parent):
        """Setup analysis widgets."""
        # Create notebook for different analyses
        analysis_notebook = ttk.Notebook(parent)
        analysis_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # System info tab
        sysinfo_frame = ttk.Frame(analysis_notebook)
        analysis_notebook.add(sysinfo_frame, text="System Info")
        
        sysinfo_text = scrolledtext.ScrolledText(sysinfo_frame, wrap=tk.WORD)
        sysinfo_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        sysinfo = self.get_system_info()
        sysinfo_text.insert(1.0, sysinfo)
        sysinfo_text.configure(state='disabled')
        
        # Process monitor tab
        process_frame = ttk.Frame(analysis_notebook)
        analysis_notebook.add(process_frame, text="Processes")
        
        # Add process list
        self.setup_process_monitor(process_frame)
        
        # Network tab
        network_frame = ttk.Frame(analysis_notebook)
        analysis_notebook.add(network_frame, text="Network")
        
        network_text = scrolledtext.ScrolledText(network_frame, wrap=tk.WORD)
        network_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        network_info = self.get_network_info()
        network_text.insert(1.0, network_info)
        network_text.configure(state='disabled')
    
    def setup_process_monitor(self, parent):
        """Setup process monitor."""
        # Toolbar
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text="Refresh", 
                  command=self.refresh_processes).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Kill Process", 
                  command=self.kill_process).pack(side=tk.LEFT, padx=2)
        
        # Process list
        process_frame = ttk.Frame(parent)
        process_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        
        columns = ("pid", "name", "cpu", "memory", "status")
        self.process_tree = ttk.Treeview(process_frame, columns=columns, show="headings")
        
        # Define headings
        self.process_tree.heading("pid", text="PID")
        self.process_tree.heading("name", text="Name")
        self.process_tree.heading("cpu", text="CPU %")
        self.process_tree.heading("memory", text="Memory %")
        self.process_tree.heading("status", text="Status")
        
        # Define columns
        self.process_tree.column("pid", width=80)
        self.process_tree.column("name", width=200)
        self.process_tree.column("cpu", width=80)
        self.process_tree.column("memory", width=80)
        self.process_tree.column("status", width=100)
        
        # Scrollbars
        vsb = ttk.Scrollbar(process_frame, orient="vertical", command=self.process_tree.yview)
        hsb = ttk.Scrollbar(process_frame, orient="horizontal", command=self.process_tree.xview)
        self.process_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Grid layout
        self.process_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        process_frame.rowconfigure(0, weight=1)
        process_frame.columnconfigure(0, weight=1)
        
        # Load initial processes
        self.refresh_processes()
    
    def setup_system_tab(self):
        """Setup the system tab."""
        system_frame = ttk.Frame(self.notebook)
        self.notebook.add(system_frame, text="System")
        
        # System information
        ttk.Label(system_frame, text="Digital Biosphere Configuration", 
                 font=("Arial", 14, "bold")).pack(pady=20)
        
        # Configuration options
        self.setup_system_config(system_frame)
    
    def setup_system_config(self, parent):
        """Setup system configuration."""
        config_frame = ttk.LabelFrame(parent, text="Configuration", padding=10)
        config_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Auto-scan interval
        ttk.Label(config_frame, text="Auto-scan interval (seconds):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.scan_interval_var = tk.IntVar(value=60)
        ttk.Spinbox(config_frame, from_=10, to=3600, textvariable=self.scan_interval_var, width=10).grid(row=0, column=1, sticky=tk.W, pady=5)
        
        # Default view
        ttk.Label(config_frame, text="Default view:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.default_view_var = tk.StringVar(value="hardware")
        view_combo = ttk.Combobox(config_frame, textvariable=self.default_view_var,
                                 values=["hardware", "filesystem", "network", "processes", "entities"],
                                 width=15, state="readonly")
        view_combo.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # Save configuration button
        ttk.Button(config_frame, text="Save Configuration", 
                  command=self.save_configuration).grid(row=2, column=0, columnspan=2, pady=10)
        
        # System status
        status_frame = ttk.LabelFrame(parent, text="System Status", padding=10)
        status_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.status_text = scrolledtext.ScrolledText(status_frame, height=8, wrap=tk.WORD)
        self.status_text.pack(fill=tk.BOTH, expand=True)
        
        # Update status
        self.update_system_status()
    
    # -------------------------------------------------------------------------
    # BRAIN MAP TAB (embedded Brain3DVisualization, lazy init)
    # -------------------------------------------------------------------------

    def setup_brain_map_tab(self):
        """Setup the Brain Map sub-tab with embedded Brain3DVisualization.

        Lazy: the heavy 3D widget is NOT created until the user clicks Enable.
        Auto-rotate and animation are off by default to conserve resources.
        """
        self._brain_viz_instance = None  # Brain3DVisualization once enabled

        brain_frame = ttk.Frame(self.notebook)
        self.notebook.add(brain_frame, text="🧠 Brain Map")
        brain_frame.columnconfigure(0, weight=1)
        brain_frame.rowconfigure(1, weight=1)  # placeholder / viz row expands

        # ── Top control bar ──────────────────────────────────────────────────
        bar = ttk.Frame(brain_frame)
        bar.grid(row=0, column=0, sticky='ew', padx=8, pady=(6, 2))

        ttk.Label(bar, text="🧠 3D Brain Map", font=('Arial', 11, 'bold')).pack(side=tk.LEFT, padx=(0, 12))

        self._brain_map_enable_btn = ttk.Button(
            bar,
            text="▶ Enable Brain Map",
            command=self._brain_map_enable,
            style='Action.TButton'
        )
        self._brain_map_enable_btn.pack(side=tk.LEFT, padx=4)

        self._brain_map_disable_btn = ttk.Button(
            bar,
            text="⏹ Unload",
            command=self._brain_map_disable,
            state='disabled'
        )
        self._brain_map_disable_btn.pack(side=tk.LEFT, padx=4)

        self._brain_map_status_lbl = ttk.Label(
            bar, text="Not loaded  (click Enable to initialise)",
            foreground='#888888', font=('Arial', 9)
        )
        self._brain_map_status_lbl.pack(side=tk.LEFT, padx=10)

        ttk.Label(
            bar,
            text="Auto-rotate / animation controls are inside the panel below",
            foreground='#555555', font=('Arial', 8)
        ).pack(side=tk.RIGHT, padx=6)

        # ── Placeholder shown while not loaded ───────────────────────────────
        self._brain_map_placeholder = ttk.Frame(brain_frame)
        self._brain_map_placeholder.grid(row=1, column=0, sticky='nsew')
        ttk.Label(
            self._brain_map_placeholder,
            text=(
                "🧠  3D Interactive Brain Visualization\n\n"
                "Maps the training system onto anatomical brain regions.\n"
                "Each model type activates different lobes — frontal (planner),\n"
                "temporal (memory/RAG), motor cortex (code execution), etc.\n\n"
                "Click  ▶ Enable Brain Map  above to load.\n"
                "Auto-rotate and animation are off by default."
            ),
            font=('Arial', 11),
            foreground='#555555',
            justify='center'
        ).place(relx=0.5, rely=0.45, anchor='center')

        # ── Container for the embedded viz (hidden until enabled) ─────────────
        self._brain_map_container = ttk.Frame(brain_frame)
        # Not gridded yet — shown by _brain_map_enable()

        # Pause animation when user switches away from this tab
        self.notebook.bind('<<NotebookTabChanged>>', self._brain_map_on_tab_change, add='+')

    def _brain_map_enable(self):
        """Lazily create and embed Brain3DVisualization."""
        if self._brain_viz_instance is not None:
            return  # already loaded

        from logger_util import log_message
        log_message("BRAIN_MAP: Enabling Brain3DVisualization — loading...")
        self._brain_map_status_lbl.config(text="Loading…", foreground='#ffcc55')
        self._brain_map_enable_btn.config(state='disabled')
        self.root.update_idletasks()

        try:
            import sys, os as _os
            _here = _os.path.dirname(_os.path.abspath(__file__))
            if _here not in sys.path:
                sys.path.insert(0, _here)
            from brain_viz_3d import Brain3DVisualization, _DEPS_OK
        except ImportError as e:
            from tkinter import messagebox
            messagebox.showerror("Import Error", f"brain_viz_3d.py not found:\n{e}")
            self._brain_map_enable_btn.config(state='normal')
            self._brain_map_status_lbl.config(text=f"Import failed: {e}", foreground='#ff6b6b')
            log_message(f"BRAIN_MAP ERROR: import failed — {e}")
            return

        if not _DEPS_OK:
            self._brain_map_status_lbl.config(
                text="Missing deps (numpy/matplotlib) — see log", foreground='#ff6b6b'
            )
            self._brain_map_enable_btn.config(state='normal')
            log_message("BRAIN_MAP ERROR: _DEPS_OK=False — check log for missing packages")
            return

        try:
            self._brain_map_placeholder.grid_remove()
            self._brain_map_container.grid(row=1, column=0, sticky='nsew')
            self._brain_map_container.columnconfigure(0, weight=1)
            self._brain_map_container.rowconfigure(0, weight=1)

            self._brain_viz_instance = Brain3DVisualization(self._brain_map_container, style=None)
            self._brain_viz_instance.grid(row=0, column=0, sticky='nsew')

            self._brain_map_status_lbl.config(
                text=f"Loaded  nodes={len(self._brain_viz_instance.nodes)}  "
                     f"regions={len(self._brain_viz_instance.regions)}  "
                     f"— auto-rotate OFF by default",
                foreground='#55ff55'
            )
            self._brain_map_disable_btn.config(state='normal')
            log_message(
                f"BRAIN_MAP: Brain3DVisualization embedded OK  "
                f"nodes={len(self._brain_viz_instance.nodes)}  "
                f"regions={len(self._brain_viz_instance.regions)}"
            )
        except Exception as e:
            import traceback as _tb
            log_message(f"BRAIN_MAP ERROR: creation failed — {e}")
            log_message(f"BRAIN_MAP TRACEBACK: {_tb.format_exc()}")
            self._brain_map_status_lbl.config(text=f"Error: {e}", foreground='#ff6b6b')
            self._brain_map_enable_btn.config(state='normal')
            # Restore placeholder
            self._brain_map_container.grid_remove()
            self._brain_map_placeholder.grid(row=1, column=0, sticky='nsew')

    def _brain_map_disable(self):
        """Destroy the Brain3DVisualization to free resources."""
        from logger_util import log_message
        if self._brain_viz_instance is not None:
            try:
                # Stop any running animation/auto-rotate timers
                if hasattr(self._brain_viz_instance, 'auto_rotate_enabled'):
                    self._brain_viz_instance.auto_rotate_enabled.set(False)
                if hasattr(self._brain_viz_instance, '_auto_rotate_after') and \
                        self._brain_viz_instance._auto_rotate_after:
                    self.root.after_cancel(self._brain_viz_instance._auto_rotate_after)
                self._brain_viz_instance.destroy()
            except Exception as e:
                log_message(f"BRAIN_MAP WARN: cleanup error on unload — {e}")
            self._brain_viz_instance = None

        self._brain_map_container.grid_remove()
        self._brain_map_placeholder.grid(row=1, column=0, sticky='nsew')
        self._brain_map_enable_btn.config(state='normal')
        self._brain_map_disable_btn.config(state='disabled')
        self._brain_map_status_lbl.config(text="Unloaded", foreground='#888888')
        log_message("BRAIN_MAP: Brain3DVisualization unloaded — resources freed")

    def _brain_map_on_tab_change(self, event=None):
        """Pause auto-rotate when user switches away from Brain Map tab."""
        if self._brain_viz_instance is None:
            return
        try:
            current_tab = self.notebook.index(self.notebook.select())
            brain_tab_index = 5  # Brain Map is tab index 5
            if current_tab != brain_tab_index:
                if self._brain_viz_instance.auto_rotate_enabled.get():
                    self._brain_viz_instance.auto_rotate_enabled.set(False)
                    self._brain_viz_instance._update_auto_timers()
        except Exception:
            pass

    def open_file(self):
        """Open file dialog."""
        filename = filedialog.askopenfilename(
            title="Select File",
            filetypes=[("All files", "*.*"),
                      ("Python files", "*.py"),
                      ("Text files", "*.txt"),
                      ("Executables", "*.exe;*.bin;*.so;*.dll")]
        )
        if filename:
            self.status_bar.config(text=f"Opened: {filename}")
            # Switch to explorer tab and select file
            self.notebook.select(2)  # Explorer tab (index 2 after Debug Context added at 0)
    
    def open_directory(self):
        """Open directory dialog."""
        directory = filedialog.askdirectory(title="Select Directory")
        if directory:
            self.status_bar.config(text=f"Opened directory: {directory}")
            # Switch to explorer tab and load directory
            self.notebook.select(2)  # Explorer tab (index 2 after Debug Context added at 0)
    
    def export_visualization(self):
        """Export visualization to file."""
        filename = filedialog.asksaveasfilename(
            title="Export Visualization",
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"),
                      ("PDF files", "*.pdf"),
                      ("SVG files", "*.svg")]
        )
        if filename:
            try:
                self.visualizer.figure.savefig(filename, dpi=150, bbox_inches='tight')
                self.status_bar.config(text=f"Exported to: {filename}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Cannot export: {e}")
    
    def reset_view(self):
        """Reset 3D view to default."""
        self.visualizer.camera_elevation = 30
        self.visualizer.camera_azimuth = 45
        self.visualizer.camera_distance = 10
        self.visualizer.redraw_scene()
        self.status_bar.config(text="View reset")
    
    def toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        is_fullscreen = self.root.attributes('-fullscreen')
        self.root.attributes('-fullscreen', not is_fullscreen)
    
    def show_hardware_only(self):
        """Show only hardware layer."""
        self.visualizer.view_mode_var.set("hardware")
        self.visualizer.on_view_mode_changed()
    
    def show_all_layers(self):
        """Show all layers."""
        self.visualizer.view_mode_var.set("entities")
        self.visualizer.on_view_mode_changed()
    
    def scan_hardware(self):
        """Scan hardware."""
        self.visualizer.scan_hardware()
        self.status_bar.config(text="Hardware scan complete")
    
    def analyze_system(self):
        """Analyze system."""
        messagebox.showinfo("Analysis", "System analysis would run here.")
        self.status_bar.config(text="System analysis started")
    
    def network_monitor(self):
        """Open network monitor."""
        messagebox.showinfo("Network Monitor", "Network monitor would open here.")
    
    def show_documentation(self):
        """Show documentation."""
        doc_text = """Digital Biosphere Explorer

This tool provides a 3D visualization of your digital ecosystem:

1. 3D Visualization Tab:
   - Interactive 3D map of hardware, files, and processes
   - Click nodes for detailed information
   - Rotate view with left-click drag
   - Pan view with right-click drag
   - Zoom with mouse wheel

2. File Explorer Tab:
   - Browse and analyze files
   - Taxonomic classification of files
   - Add files to 3D visualization

3. Analysis Tab:
   - System information
   - Process monitoring
   - Network status

4. System Tab:
   - Configuration settings
   - System status

Keyboard Shortcuts:
   F11 - Toggle fullscreen
   Ctrl+O - Open file
   Ctrl+D - Open directory
   Ctrl+E - Export visualization
   ESC - Reset view
"""
        
        popup = tk.Toplevel(self.root)
        popup.title("Documentation")
        popup.geometry("600x500")
        
        text = scrolledtext.ScrolledText(popup, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert(1.0, doc_text)
        text.configure(state='disabled')
        
        ttk.Button(popup, text="Close", command=popup.destroy).pack(pady=10)
    
    def show_about(self):
        """Show about dialog."""
        about_text = """Digital Biosphere Explorer v1.0

A 3D visualization tool for mapping digital ecosystems.

Features:
• 3D hardware visualization
• File system exploration
• Taxonomic classification
• Process monitoring
• Network mapping

Author: Digital Biosphere Project
License: MIT

This tool treats your computer as a digital ecosystem,
with components as organisms in a complex environment.
"""
        
        messagebox.showinfo("About Digital Biosphere", about_text)
    
    def get_system_info(self) -> str:
        """Get system information."""
        info = []
        info.append("=== System Information ===")
        info.append(f"Platform: {platform.platform()}")
        info.append(f"System: {platform.system()} {platform.release()}")
        info.append(f"Processor: {platform.processor()}")
        info.append(f"Machine: {platform.machine()}")
        info.append(f"Python: {platform.python_version()}")
        info.append("")
        
        # Memory info
        try:
            import psutil
            memory = psutil.virtual_memory()
            info.append("=== Memory ===")
            info.append(f"Total: {memory.total // (1024**3)} GB")
            info.append(f"Available: {memory.available // (1024**3)} GB")
            info.append(f"Used: {memory.percent}%")
            info.append("")
        except:
            pass
        
        # Disk info
        try:
            info.append("=== Storage ===")
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    info.append(f"{partition.device}: {partition.mountpoint}")
                    info.append(f"  Total: {usage.total // (1024**3)} GB")
                    info.append(f"  Used: {usage.percent}%")
                except:
                    continue
            info.append("")
        except:
            pass
        
        # Network info
        try:
            info.append("=== Network ===")
            interfaces = psutil.net_if_addrs()
            for iface, addrs in interfaces.items():
                info.append(f"{iface}:")
                for addr in addrs:
                    info.append(f"  {addr.family.name}: {addr.address}")
            info.append("")
        except:
            pass
        
        return "\n".join(info)
    
    def get_network_info(self) -> str:
        """Get network information."""
        info = []
        info.append("=== Network Information ===")
        
        try:
            import psutil
            
            # Connections
            info.append("\n=== Active Connections ===")
            connections = psutil.net_connections()
            
            conn_by_state = {}
            for conn in connections:
                state = conn.status if hasattr(conn, 'status') else 'UNKNOWN'
                conn_by_state[state] = conn_by_state.get(state, 0) + 1
            
            for state, count in conn_by_state.items():
                info.append(f"{state}: {count}")
            
            # Interfaces stats
            info.append("\n=== Interface Statistics ===")
            io_counters = psutil.net_io_counters(pernic=True)
            
            for iface, counters in io_counters.items():
                info.append(f"\n{iface}:")
                info.append(f"  Bytes Sent: {counters.bytes_sent:,}")
                info.append(f"  Bytes Received: {counters.bytes_recv:,}")
                info.append(f"  Packets Sent: {counters.packets_sent:,}")
                info.append(f"  Packets Received: {counters.packets_recv:,}")
                
        except Exception as e:
            info.append(f"\nError getting network info: {e}")
        
        return "\n".join(info)
    
    def refresh_processes(self):
        """Refresh process list."""
        # Clear existing items
        for item in self.process_tree.get_children():
            self.process_tree.delete(item)
        
        try:
            import psutil
            
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
                try:
                    info = proc.info
                    self.process_tree.insert("", "end", values=(
                        info['pid'],
                        info['name'],
                        f"{info['cpu_percent']:.1f}",
                        f"{info['memory_percent']:.1f}",
                        info['status']
                    ))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
        except Exception as e:
            print(f"Error refreshing processes: {e}")
    
    def kill_process(self):
        """Kill selected process."""
        selection = self.process_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a process to kill.")
            return
        
        item = self.process_tree.item(selection[0])
        pid = int(item['values'][0])
        name = item['values'][1]
        
        if messagebox.askyesno("Confirm Kill", f"Kill process {name} (PID: {pid})?"):
            try:
                import psutil
                process = psutil.Process(pid)
                process.terminate()
                self.status_bar.config(text=f"Terminated process: {name}")
                self.refresh_processes()
            except Exception as e:
                messagebox.showerror("Error", f"Cannot kill process: {e}")
    
    def save_configuration(self):
        """Save configuration."""
        config = {
            'scan_interval': self.scan_interval_var.get(),
            'default_view': self.default_view_var.get(),
            'saved_at': datetime.now().isoformat()
        }
        
        # Save to file
        config_path = Path.home() / '.digital_biosphere_config.json'
        try:
            config_path.write_text(json.dumps(config, indent=2))
            self.status_bar.config(text="Configuration saved")
        except Exception as e:
            messagebox.showerror("Save Error", f"Cannot save configuration: {e}")
    
    def update_system_status(self):
        """Update system status display."""
        try:
            import psutil
            
            status = []
            status.append("=== Live System Status ===")
            status.append(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # CPU
            cpu_percent = psutil.cpu_percent(interval=0.1)
            status.append(f"CPU Usage: {cpu_percent}%")
            
            # Memory
            memory = psutil.virtual_memory()
            status.append(f"Memory Usage: {memory.percent}%")
            
            # Disk
            disk = psutil.disk_usage('/')
            status.append(f"Disk Usage: {disk.percent}%")
            
            # Processes
            status.append(f"Running Processes: {len(psutil.pids())}")
            
            self.status_text.delete(1.0, tk.END)
            self.status_text.insert(1.0, "\n".join(status))
            self.status_text.configure(state='disabled')
            
            # Update every 5 seconds
            self.root.after(5000, self.update_system_status)
            
        except Exception as e:
            self.status_text.delete(1.0, tk.END)
            self.status_text.insert(1.0, f"Error getting status: {e}")
            self.status_text.configure(state='disabled')
            
            # Retry after 10 seconds
            self.root.after(10000, self.update_system_status)

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point."""
    root = tk.Tk()
    app = DigitalBiosphereApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()

# ============================================================================
# MODULAR GUI INTEGRATION
# ============================================================================

if 'MODULAR_SUPPORT' in globals() and MODULAR_SUPPORT:
    class MapTab(BaseTab):
        """Wrapper for DigitalBiosphereApp to be used as a modular tab."""
        def create_ui(self):
            log_message("MAP_TAB: Initializing DigitalBiosphereApp...")
            try:
                # DigitalBiosphereApp creates its own notebook and tabs inside self.parent
                self.app = DigitalBiosphereApp(self.parent)
                log_message("MAP_TAB: DigitalBiosphereApp initialized successfully.")
            except Exception as e:
                log_message(f"MAP_TAB ERROR: Failed to initialize app: {e}")
                import traceback
                log_message(traceback.format_exc())
                
                error_label = ttk.Label(self.parent, text=f"Critical Error: {e}", foreground="red")
                error_label.grid(row=0, column=0, pady=20)