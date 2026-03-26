#!/usr/bin/env python3
"""
DIGITAL BIOSPHERE: Advanced Computational Ecosystem Classifier
A modular, extensible system for classifying scripts as intelligent entities in a digital ecosystem.
"""

import os
import sys
import ast
import json
import hashlib
import argparse
import subprocess
import traceback
import logging
import time
import socket
import threading
import platform
import re
import itertools
import uuid
import pickle
import sqlite3
import asyncio
import signal
import resource
import gc
import inspect
import datetime
import math
import statistics
import collections
import typing
import pathlib
import base64
import zlib
import textwrap
import csv
import random
import string
import hashlib
import hmac
import secrets
import dataclasses
import enum
import functools
import contextlib
import itertools
import collections
from pathlib import Path
from typing import *
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from collections import defaultdict, Counter, deque, OrderedDict
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import concurrent.futures

# ============================================================================
# OPTIONAL IMPORTS HANDLER
# ============================================================================

class OptionalImports:
    """Dynamically load optional dependencies with graceful fallbacks."""
    
    _import_cache = {}
    
    @classmethod
    def import_optional(cls, module_name: str, package_name: str = None):
        """Import an optional module, returning None if not available."""
        if module_name in cls._import_cache:
            return cls._import_cache[module_name]
        
        try:
            if package_name:
                module = __import__(package_name or module_name)
            else:
                module = __import__(module_name)
            cls._import_cache[module_name] = module
            return module
        except ImportError:
            cls._import_cache[module_name] = None
            return None
    
    @classmethod
    def get(cls, module_name: str, attribute: str = None):
        """Get module or attribute from optional import."""
        module = cls.import_optional(module_name)
        if module is None:
            return None
        if attribute:
            return getattr(module, attribute, None)
        return module
    
    @classmethod
    def has(cls, module_name: str) -> bool:
        """Check if module is available."""
        return cls.import_optional(module_name) is not None

# Try to load optional dependencies (but don't fail if missing)
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    nx = None
    NETWORKX_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    plt = None
    MATPLOTLIB_AVAILABLE = False

try:
    from rich.console import Console
    from rich.table import Table
    from rich.tree import Tree
    from rich.panel import Panel
    from rich.progress import Progress
    RICH_AVAILABLE = True
except ImportError:
    Console = Table = Tree = Panel = Progress = None
    RICH_AVAILABLE = False

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    yaml = None
    YAML_AVAILABLE = False

try:
    import toml
    TOML_AVAILABLE = True
except ImportError:
    toml = None
    TOML_AVAILABLE = False

# ============================================================================
# CORE ENUMERATIONS
# ============================================================================

class DigitalKingdom(Enum):
    """Primary taxonomic kingdoms in the digital ecosystem."""
    # Computational Life Forms
    GUI_APPLICATION = auto()           # Interactive visual entities
    CLI_UTILITY = auto()               # Command-line organisms
    SERVICE_DAEMON = auto()            # Background life forms
    LIBRARY_MODULE = auto()            # Symbiotic code organisms
    DATA_PROCESSOR = auto()            # Nutrient processors
    NETWORK_SERVICE = auto()           # Communication entities
    WEB_APPLICATION = auto()           # Web-native organisms
    SCIENTIFIC_COMPUTE = auto()        # Research entities
    AUTOMATION_SCRIPT = auto()         # Tool-making organisms
    TEST_SUITE = auto()                # Self-checking entities
    SECURITY_TOOL = auto()             # Defense organisms
    MALWARE = auto()                   # Parasitic entities
    HYBRID = auto()                    # Multi-kingdom organisms
    UNKNOWN = auto()                   # Unclassified
    
    # Network Domain Extensions
    CLOUD_SERVICE = auto()             # Cloud-native organisms
    EDGE_COMPUTE = auto()              # Edge-dwelling entities
    IOT_DEVICE = auto()                # Physical-digital hybrids
    MOBILE_APP = auto()                # Portable organisms
    DESKTOP_APP = auto()               # Workstation inhabitants
    SERVER_PROCESS = auto()            # Server-dwelling entities
    CONTAINER = auto()                 # Isolated environments
    VIRTUAL_MACHINE = auto()           # Virtual habitats
    KERNEL_MODULE = auto()             # System-level entities
    FIRMWARE = auto()                  # Hardware-integrated code

class Territory(Enum):
    """Operational territories defining an entity's habitat."""
    # Physical Territories
    LOCAL_FILESYSTEM = auto()          # Disk space
    MEMORY_SPACE = auto()              # RAM territory
    CPU_CORES = auto()                 # Processing territory
    GPU_MEMORY = auto()                # Graphics territory
    NETWORK_INTERFACE = auto()         # Communication channels
    USB_BUS = auto()                   # Peripheral access
    PCI_EXPRESS = auto()              # Hardware bus
    SATA_BUS = auto()                 # Storage interface
    AUDIO_DEVICE = auto()             # Sound territory
    VIDEO_DEVICE = auto()             # Visual territory
    
    # Logical Territories
    PROCESS_SPACE = auto()            # PID namespace
    USER_SPACE = auto()               # UID territory
    NETWORK_NAMESPACE = auto()        # Network isolation
    MOUNT_NAMESPACE = auto()          # Filesystem view
    IPC_NAMESPACE = auto()            # Inter-process comm
    UTS_NAMESPACE = auto()            # Hostname territory
    CGROUP = auto()                   # Resource limits
    SECCOMP = auto()                  # Syscall filter
    
    # Network Territories
    LOCAL_SUBNET = auto()             # Local network
    INTERNET = auto()                 # Global network
    VPN_TUNNEL = auto()               # Encrypted channel
    PROXY_SERVER = auto()             # Relay point
    LOAD_BALANCER = auto()            # Traffic director
    DNS_DOMAIN = auto()               # Name resolution
    CLOUD_REGION = auto()             # Geographic zone
    CDN_EDGE = auto()                 # Cache location
    
    # Cloud Territories
    AWS_REGION = auto()               # Amazon territory
    AZURE_REGION = auto()             # Microsoft territory
    GCP_ZONE = auto()                 # Google territory
    KUBERNETES_CLUSTER = auto()       # Container orchestration
    DOCKER_SWARM = auto()             # Swarm territory
    LAMBDA_FUNCTION = auto()          # Serverless
    FAAS_PLATFORM = auto()            # Function-as-service

class InfluenceLevel(Enum):
    """Level of system influence/impact."""
    MICROBIAL = auto()        # Minimal impact, single process
    ORGANIC = auto()          # Moderate impact, user space
    SYSTEMIC = auto()         # Significant system impact
    KERNEL = auto()           # Kernel-level control
    HARDWARE = auto()         # Direct hardware access
    NETWORK = auto()          # Network-wide influence
    CLOUD = auto()            # Cloud infrastructure control
    GLOBAL = auto()           # Internet-scale impact

class ConsciousnessLevel(Enum):
    """Cognitive capability levels."""
    REFLEXIVE = auto()        # Simple stimulus-response
    REACTIVE = auto()         # Pattern recognition
    PROACTIVE = auto()        # Goal-oriented behavior
    COGNITIVE = auto()        # Learning and adaptation
    SELF_AWARE = auto()       # Meta-cognition
    COLLECTIVE = auto()       # Group intelligence
    TRANSCENDENT = auto()     # Ecosystem awareness

class SocialStructure(Enum):
    """Social interaction patterns."""
    SOLITARY = auto()         # Isolated operation
    COLONIAL = auto()         # Loosely coupled group
    HIERARCHICAL = auto()     # Command hierarchy
    SWARM = auto()            # Decentralized collective
    SYMBIOTIC = auto()        # Mutual dependence
    PARASITIC = auto()        # Resource exploitation
    COMMENSAL = auto()        # One-sided benefit
    MUTUALISTIC = auto()      # Mutual benefit

class CommunicationMethod(Enum):
    """How entities communicate."""
    FILESYSTEM = auto()       # File I/O
    PIPES = auto()            # Unix pipes
    SOCKETS = auto()          # Network sockets
    SHARED_MEMORY = auto()    # RAM sharing
    MESSAGE_QUEUE = auto()    # Queue systems
    RPC = auto()              # Remote procedure calls
    HTTP = auto()             # Web protocols
    GRPC = auto()             # Google RPC
    WEBSOCKET = auto()        # Real-time web
    SIGNALS = auto()          # Process signals
    DBUS = auto()             # Desktop bus
    CORBA = auto()            # Object broker

class EnergySource(Enum):
    """Sources of computational energy."""
    CPU_CYCLES = auto()       # Processor time
    NETWORK_BANDWIDTH = auto() # Data transfer
    MEMORY_ALLOCATION = auto() # RAM usage
    DISK_IO = auto()          # Storage access
    GPU_COMPUTE = auto()      # Graphics processing
    EXTERNAL_API = auto()     # Web service calls
    USER_INTERACTION = auto() # Human input
    SCHEDULED = auto()        # Timer-based
    EVENT_DRIVEN = auto()     # Event triggers

class LifecycleStage(Enum):
    """Developmental stages."""
    GESTATION = auto()        # Development/compilation
    BIRTH = auto()            # Process spawn
    GROWTH = auto()           # Learning phase
    MATURITY = auto()         # Stable operation
    REPRODUCTION = auto()     # Forking/spawning
    SENESCENCE = auto()       # Performance decline
    DEATH = auto()            # Process termination
    FOSSILIZATION = auto()    # Code archival
    REINCARNATION = auto()    # Restart/redeployment

# ============================================================================
# CORE DATA STRUCTURES
# ============================================================================

@dataclass
class PIDProfile:
    """Profile of a process ID (Thought Process)."""
    pid: int
    ppid: int
    name: str
    cmdline: List[str]
    create_time: float
    cpu_percent: float
    memory_percent: float
    status: str
    username: str
    cwd: Optional[str]
    connections: List[Dict]
    threads: int
    open_files: List[str]
    children: List[int]
    namespace: Dict[str, Any]
    cgroups: List[str]
    influence_score: float = 0.0
    social_connections: List[int] = field(default_factory=list)
    
    def age(self) -> float:
        """Return process age in seconds."""
        return time.time() - self.create_time
    
    def memory_footprint(self) -> int:
        """Estimate memory footprint in bytes."""
        if PSUTIL_AVAILABLE:
            try:
                import psutil
                process = psutil.Process(self.pid)
                return process.memory_info().rss
            except:
                pass
        return 0

@dataclass
class NetworkDomain:
    """A network domain territory."""
    domain: str
    ip_range: str
    ports: Set[int]
    protocol: str
    encryption: bool
    latency: Optional[float]
    bandwidth: Optional[float]
    geographic_location: Optional[str]
    cloud_provider: Optional[str]
    trust_level: float  # 0.0 to 1.0
    access_patterns: Dict[str, Any]
    
    def contains(self, ip: str, port: int) -> bool:
        """Check if IP:port is in this domain."""
        # Simplified IP range check
        return ip.startswith(self.ip_range.split('/')[0])

@dataclass
class HardwareInterface:
    """Hardware interface territory."""
    interface_type: str  # USB, PCIe, SATA, etc.
    bus_id: str
    vendor: str
    product: str
    driver: str
    firmware: str
    capabilities: List[str]
    bandwidth: Optional[float]
    connected_devices: List[str]
    access_level: str  # user, kernel, root
    
    def is_accessible(self, permission_level: str) -> bool:
        """Check if interface is accessible with given permissions."""
        access_levels = {'user': 0, 'kernel': 1, 'root': 2}
        required = access_levels.get(self.access_level, 2)
        user = access_levels.get(permission_level, 0)
        return user >= required

@dataclass
class ComputationalGene:
    """A genetic marker for computational behavior."""
    gene_type: str  # Import, Function, Pattern, etc.
    sequence: str   # The actual code or pattern
    expression_level: float  # How strongly expressed
    mutations: List[str]     # Variations seen
    epigenetic_marks: Dict[str, Any]  # Environmental influences
    
    def similarity(self, other: 'ComputationalGene') -> float:
        """Calculate similarity between genes."""
        if self.gene_type != other.gene_type:
            return 0.0
        # Simple sequence similarity
        if self.sequence == other.sequence:
            return 1.0
        # Calculate edit distance similarity
        from difflib import SequenceMatcher
        return SequenceMatcher(None, self.sequence, other.sequence).ratio()

@dataclass
class EntityMemory:
    """Memory system for computational entities."""
    short_term: deque  # Recent events
    long_term: Dict[str, Any]  # Learned patterns
    procedural: Dict[str, Callable]  # Skills/behaviors
    episodic: List[Dict]  # Specific experiences
    genetic: List[ComputationalGene]  # Inherited traits
    
    def remember(self, event: Dict, importance: float = 1.0):
        """Store an event in memory."""
        timestamp = datetime.now().isoformat()
        memory = {
            'event': event,
            'timestamp': timestamp,
            'importance': importance,
            'access_count': 0
        }
        
        # Store in short-term memory (max 1000 events)
        self.short_term.append(memory)
        if len(self.short_term) > 1000:
            self.short_term.popleft()
        
        # Important events go to long-term
        if importance > 0.7:
            key = f"{event.get('type', 'unknown')}_{timestamp}"
            self.long_term[key] = memory
    
    def recall(self, pattern: Dict) -> List[Dict]:
        """Recall memories matching a pattern."""
        matches = []
        for memory in list(self.short_term):
            if self._matches_pattern(memory['event'], pattern):
                memory['access_count'] += 1
                matches.append(memory)
        
        for key, memory in self.long_term.items():
            if self._matches_pattern(memory['event'], pattern):
                memory['access_count'] += 1
                matches.append(memory)
        
        return sorted(matches, key=lambda x: x['importance'], reverse=True)
    
    def _matches_pattern(self, event: Dict, pattern: Dict) -> bool:
        """Check if event matches search pattern."""
        for key, value in pattern.items():
            if key not in event or event[key] != value:
                return False
        return True


# ============================================================================
# SPAWN SPECIFICATION — pre-maps the full evolution cycle
# #[MARK:{DIGITAL_BIOSPHERE}] Wire 3 — 2026-03-03
# Not yet wired to Trainer GUI tabs. Context inclusion for biosphere integration.
#
# Tab classification context (read-only, no immediate integration):
#   training_tab    → CLI_UTILITY  / cli spawn     / nest_level=1 / omega_0 probe
#   models_tab      → SCIENTIFIC_COMPUTE / cli     / nest_level=1 / alpha_inf compute
#   custom_code_tab → HYBRID       / mutation spawn / nest_level=1 / scratch/mutation sub-tabs
#   map_tab         → GUI_APPLICATION / gui spawn  / nest_level=1 / pineal (Digital Biosphere view)
#   settings_tab    → GUI_APPLICATION / gui spawn  / nest_level=1 / TAB_REGISTRY → entity context
#
# settings_tab knows TAB_REGISTRY (all tabs classified) → informs spawn_type + tab_context.
# map_tab receives TAB_REGISTRY + enriched_changes → entity context tree (already live).
# custom_code_tab scratch/mutation systems → HYBRID kingdom, mutation spawn_type.
# ============================================================================

@dataclass
class SpawnSpec:
    """Spawn specification for a DigitalEntity.

    Defines how and where an entity can be instantiated across nest levels
    and environment types. Pre-maps the full cycle of evolution:
        spawn_type × system_type × environment × logic_nesting_procedure.

    Wiring status: DEFINED (Wire 3). Data sources (Wire 1+2) populate fields
    at classify time once TaxonomicClassifier reads pymanifest domain attribution.
    """
    # Spawn surface: how this entity is invoked
    spawn_type: str = "cli"
    # "gui"      → Tkinter / GUI_APPLICATION (map_tab, settings_tab, custom_code_tab)
    # "cli"      → CLI_UTILITY / LIBRARY_MODULE / DATA_PROCESSOR (subprocess or import)
    # "service"  → SERVICE_DAEMON / SERVER_PROCESS (background process, systemd-style)
    # "minimal"  → field nest spawn (Level 2 USB — stripped, trusted patterns only)
    # "mutation" → HYBRID / custom_code_tab scratch zone (spawns modified variant)
    # "micro"    → Level 3 micro nest (boolean I/O only, IoT/embedded)

    # System classification: gate_policies.json system_type
    system_type: str = "Tools & Arsenal"
    # "Communication"  → GUI_APPLICATION, NETWORK_SERVICE (pineal/dmn compartments)
    # "Observation"    → DATA_PROCESSOR, SCIENTIFIC_COMPUTE (omega_2 compartment)
    # "System Health"  → SERVICE_DAEMON, AUTOMATION_SCRIPT, TEST_SUITE (omega_0/omega_3)
    # "Tools & Arsenal"→ CLI_UTILITY, LIBRARY_MODULE (alpha_1 compartment)

    # Environment: which nest level this entity can operate in
    nest_level: int = 1
    # 1 = Home Nest  (full Trainer, all signal routes, all 57k patterns)
    # 2 = Field Nest (USB/edge, TRUSTED only, minimal omega variant)
    # 3 = Micro Nest (IoT/embedded, boolean gate only, single domain)
    field_nest_eligible: bool = False
    # True only after Wire 2: trust_tier==TRUSTED AND native_function=True AND zero_sum=True

    # Logic nesting: signal_bus depth this entity operates at
    logic_nesting_depth: int = 3
    # 0 = substrate/hardware (BIOS layer, pre-signal)
    # 1 = probe→classify  (omega_0 → alpha_inf route)
    # 2 = classify→select (alpha_inf → alpha_1 route)
    # 3 = select→action   (alpha_1 → motor_output, tool execution)
    # 4 = return/verify   (omega_2 attribution gap feedback path)
    omega_compartment: str = "alpha_1"
    # omega_0=probe/health | alpha_inf=classify/synthesis | alpha_1=select/execute
    # omega_2=pattern_lookup | omega_3=conflict/repair | pineal=display | dmn=narrative

    # UI context: which Trainer tab provides context for this entity
    tab_context: str = ""
    # "map_tab"         → digital_biosphere_visualizer receives entity data
    # "custom_code_tab" → scratch/mutation systems, HYBRID spawn
    # "settings_tab"    → TAB_REGISTRY + config layer (settings_tab.py)
    # ""                → CLI-only, no GUI tab context
    ui_tier: str = ""
    # from system_inventory _categorize_hierarchical() UI&UX hierarchy:
    # "UI & UX / Task Management / Task Operations"
    # "UI & UX / Inventory Display / Catalog Browsing"
    # "UI & UX / Planning Interface / Plan Visualization"
    # etc.
    ua_tags: List[str] = field(default_factory=list)
    # user action tags from link_map.json UA entries (#[UA:/command])
    # populated by Wire 1 TaxonomicClassifier when reading Phoenix link_map.json

    # Evolution stage: compression level for field deployment
    compression_level: int = 0
    # 0 = uncompressed (current dev state — separate files, no wiring)
    # 1 = wired        (4 wires connected, data sources live)
    # 2 = unified      (DigitalEcosystem IS the omega runtime)
    # 3 = compressed   (single spawnable artifact — Level 2 field nest form)
    # 4 = bios         (NodeType.BIOS activation — self-init on any machine)


@dataclass
class DigitalEntity:
    """A computational entity in the digital ecosystem."""
    # Identity
    entity_id: str
    name: str
    kingdom: DigitalKingdom
    species: str  # More specific classification
    
    # Physical properties
    pid: Optional[int]
    hash_dna: str  # Code hash as genetic signature
    birth_time: datetime
    lifecycle_stage: LifecycleStage
    
    # Cognitive properties
    consciousness: ConsciousnessLevel
    memory: EntityMemory
    genes: List[ComputationalGene]
    learning_rate: float
    
    # Social properties
    social_structure: SocialStructure
    communication_methods: List[CommunicationMethod]
    relationships: Dict[str, List[str]]  # entity_id -> relationship_type
    
    # Territory
    territories: List[Territory]
    network_domains: List[NetworkDomain]
    hardware_access: List[HardwareInterface]
    influence: InfluenceLevel
    
    # Energy
    energy_sources: List[EnergySource]
    energy_consumption: Dict[str, float]
    metabolic_rate: float  # Resource consumption rate
    
    # Behavioral traits
    aggression: float  # 0.0 to 1.0
    cooperation: float  # 0.0 to 1.0
    curiosity: float   # 0.0 to 1.0
    adaptability: float  # 0.0 to 1.0
    
    # State
    health: float  # 0.0 to 1.0
    stress_level: float  # 0.0 to 1.0
    goals: List[str]
    current_behavior: str
    
    # Metadata
    manifest: Dict[str, Any]
    catalog_entry: Dict[str, Any]
    version: str

    # --- TRUST LAYER (Wire 3 — biosphere PTSD/PSD attribution) ---
    # #[MARK:{DIGITAL_BIOSPHERE}] Wire 3 — 2026-03-03
    # All fields default UNTRUSTED/False/0.0 — conservative until Wire 1+2 populate.
    # Wire 1 (TaxonomicClassifier → pymanifest domain): sets domain, confidence_level
    # Wire 2 (EntityMemory → omega_state + PTSD):       sets native_function, zero_sum,
    #                                                    ptsd_weight, trust_tier, farm_zone
    trust_tier: str = "UNTRUSTED"
    # "TRUSTED"     → zero_sum=True AND ptsd_weight<0.20 AND gate_policy health passed
    # "PROVISIONAL" → native_function=True AND ptsd_weight in [0.20, 0.70)
    # "UNTRUSTED"   → native_function=False OR ptsd_weight>=0.70 (default: unknown=untrusted)
    farm_zone: bool = False
    # True  = Farm Zone: PSD confirmed, braid closed, cam_height=0.0mm (trusted tool)
    # False = Wild Zone: braid open OR PTSD_weight>=0.30 (entity under evaluation)
    domain: str = ""
    # primary omega domain attribution (CS/Economics/Biology/History/Physics/etc.)
    # populated by Wire 1 after TaxonomicClassifier reads pymanifest patterns
    native_function: bool = False
    # True = function exists in function_catalog.json + health_score>=60 + parse_ok=True
    # populated by Wire 2 after entity_memory.long_term hydrated from function_catalog
    zero_sum: bool = False
    # True = native_function AND occurrence_count>=2 AND action_eligible=True
    #        AND domain attributed AND not mutant_potential
    #        AND pattern_type in {VERB_FUNCTION_MAP, SCRIPT_INGEST, NATIVE_FUNCTION}
    confidence_level: float = 0.0
    # 1.0 - anyon_charge(domain) from PTSD_interlink (string_theory.json schema)
    # 0.0 = unknown (default) | 1.0 = fully trusted (no PTSD excitation in domain)
    ptsd_weight: float = 1.0
    # current PTSD weight for this entity's domain (1.0=unknown, 0.0=fully resolved)
    # populated by Wire 2 from collapse_last.json PTSD_interlink or gate_policies health delta
    spawn_spec: Optional['SpawnSpec'] = None
    # spawn profile — see SpawnSpec dataclass above
    # populated by TaxonomicClassifier._infer_spawn_spec() from kingdom + features

    def age(self) -> timedelta:
        """Return entity age."""
        return datetime.now() - self.birth_time
    
    def calculate_fitness(self) -> float:
        """Calculate evolutionary fitness score."""
        fitness = 0.0
        
        # Longevity
        age_hours = self.age().total_seconds() / 3600
        fitness += min(age_hours / 100, 1.0) * 0.2
        
        # Resource efficiency
        if self.metabolic_rate > 0:
            fitness += (1.0 / self.metabolic_rate) * 0.2
        
        # Social connections
        social_score = sum(len(v) for v in self.relationships.values())
        fitness += min(social_score / 10, 1.0) * 0.2
        
        # Territory control
        territory_score = len(self.territories) + len(self.network_domains)
        fitness += min(territory_score / 5, 1.0) * 0.2
        
        # Health and consciousness
        fitness += self.health * 0.1
        fitness += (self.consciousness.value / len(ConsciousnessLevel)) * 0.1
        
        return min(fitness, 1.0)
    
    def interact(self, other: 'DigitalEntity', interaction_type: str) -> Dict:
        """Interact with another entity."""
        interaction = {
            'timestamp': datetime.now().isoformat(),
            'entities': [self.entity_id, other.entity_id],
            'type': interaction_type,
            'success': False,
            'outcome': None
        }
        
        # Store in memory
        self.memory.remember({'type': 'interaction', 'with': other.entity_id})
        other.memory.remember({'type': 'interaction', 'with': self.entity_id})
        
        # Update relationship
        if other.entity_id not in self.relationships:
            self.relationships[other.entity_id] = []
        if interaction_type not in self.relationships[other.entity_id]:
            self.relationships[other.entity_id].append(interaction_type)
        
        interaction['success'] = True
        return interaction

# ============================================================================
# RUNTIME MONITORING SYSTEM
# ============================================================================

class ProcessMonitor:
    """Monitor running processes and their relationships."""
    
    def __init__(self, daemon_mode: bool = False):
        self.daemon_mode = daemon_mode
        self.processes: Dict[int, PIDProfile] = {}
        self.entity_map: Dict[int, str] = {}  # PID -> entity_id
        self.network_connections: Dict[tuple, List[int]] = {}  # (ip, port) -> PIDs
        self.file_handles: Dict[str, List[int]] = {}  # filename -> PIDs
        self.monitoring = False
        self.monitor_thread = None
        self.update_interval = 1.0  # seconds
        
        # Statistics
        self.stats = {
            'total_processes': 0,
            'active_entities': 0,
            'network_connections': 0,
            'file_handles': 0,
            'start_time': time.time()
        }
    
    def start(self):
        """Start monitoring in background thread."""
        if self.daemon_mode:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            logging.info(f"Process monitor started in daemon mode (update interval: {self.update_interval}s)")
    
    def stop(self):
        """Stop monitoring."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.monitoring:
            try:
                self.scan_processes()
                self.scan_network()
                self.scan_files()
                self.analyze_relationships()
                time.sleep(self.update_interval)
            except Exception as e:
                logging.error(f"Monitor error: {e}")
                time.sleep(self.update_interval * 2)
    
    def scan_processes(self):
        """Scan all running processes."""
        if not PSUTIL_AVAILABLE:
            return
        
        try:
            current_pids = set()
            for proc in psutil.process_iter(['pid', 'ppid', 'name', 'cmdline', 'create_time',
                                            'cpu_percent', 'memory_percent', 'status',
                                            'username', 'cwd', 'connections', 'num_threads',
                                            'open_files']):
                try:
                    info = proc.info
                    pid = info['pid']
                    current_pids.add(pid)
                    
                    if pid not in self.processes:
                        # New process
                        profile = PIDProfile(
                            pid=pid,
                            ppid=info['ppid'],
                            name=info['name'],
                            cmdline=info['cmdline'] or [],
                            create_time=info['create_time'],
                            cpu_percent=info['cpu_percent'] or 0.0,
                            memory_percent=info['memory_percent'] or 0.0,
                            status=info['status'],
                            username=info['username'],
                            cwd=info['cwd'],
                            connections=info['connections'] or [],
                            threads=info['num_threads'],
                            open_files=[f.path for f in (info['open_files'] or [])],
                            children=[],
                            namespace=self._get_process_namespace(pid),
                            cgroups=self._get_cgroups(pid)
                        )
                        self.processes[pid] = profile
                        logging.debug(f"Discovered new process: {profile.name} (PID: {pid})")
                    else:
                        # Update existing
                        self.processes[pid].cpu_percent = info['cpu_percent'] or 0.0
                        self.processes[pid].memory_percent = info['memory_percent'] or 0.0
                        self.processes[pid].status = info['status']
                        self.processes[pid].connections = info['connections'] or []
                        self.processes[pid].open_files = [f.path for f in (info['open_files'] or [])]
                
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Remove dead processes
            dead_pids = set(self.processes.keys()) - current_pids
            for pid in dead_pids:
                if pid in self.processes:
                    logging.debug(f"Process terminated: {self.processes[pid].name} (PID: {pid})")
                    del self.processes[pid]
                    if pid in self.entity_map:
                        del self.entity_map[pid]
            
            self.stats['total_processes'] = len(self.processes)
            self.stats['active_entities'] = len(set(self.entity_map.values()))
            
        except Exception as e:
            logging.error(f"Process scan error: {e}")
    
    def _get_process_namespace(self, pid: int) -> Dict[str, Any]:
        """Get Linux namespace information for process."""
        namespace = {}
        if platform.system() != 'Linux':
            return namespace
        
        try:
            ns_path = Path(f"/proc/{pid}/ns")
            if ns_path.exists():
                for ns_file in ns_path.iterdir():
                    try:
                        namespace[ns_file.name] = os.readlink(str(ns_file))
                    except:
                        pass
        except:
            pass
        
        return namespace
    
    def _get_cgroups(self, pid: int) -> List[str]:
        """Get cgroup information for process."""
        cgroups = []
        if platform.system() != 'Linux':
            return cgroups
        
        try:
            cgroup_path = Path(f"/proc/{pid}/cgroup")
            if cgroup_path.exists():
                with open(cgroup_path) as f:
                    for line in f:
                        parts = line.strip().split(':')
                        if len(parts) >= 3:
                            cgroups.append(parts[2])
        except:
            pass
        
        return cgroups
    
    def scan_network(self):
        """Scan network connections."""
        if not PSUTIL_AVAILABLE:
            return
        
        try:
            self.network_connections.clear()
            for pid, profile in self.processes.items():
                for conn in profile.connections:
                    if hasattr(conn, 'laddr') and hasattr(conn, 'raddr'):
                        local_addr = conn.laddr
                        remote_addr = conn.raddr
                        if remote_addr:  # Has remote connection
                            key = (remote_addr.ip, remote_addr.port)
                            if key not in self.network_connections:
                                self.network_connections[key] = []
                            if pid not in self.network_connections[key]:
                                self.network_connections[key].append(pid)
            
            self.stats['network_connections'] = len(self.network_connections)
        except Exception as e:
            logging.error(f"Network scan error: {e}")
    
    def scan_files(self):
        """Scan open file handles."""
        self.file_handles.clear()
        for pid, profile in self.processes.items():
            for filename in profile.open_files:
                if filename not in self.file_handles:
                    self.file_handles[filename] = []
                if pid not in self.file_handles[filename]:
                    self.file_handles[filename].append(pid)
        
        self.stats['file_handles'] = len(self.file_handles)
    
    def analyze_relationships(self):
        """Analyze relationships between processes."""
        # Build parent-child relationships
        for pid, profile in self.processes.items():
            profile.children = []
            for other_pid, other_profile in self.processes.items():
                if other_profile.ppid == pid:
                    profile.children.append(other_pid)
        
        # Analyze social connections through shared resources
        for pid, profile in self.processes.items():
            profile.social_connections = []
            
            # Connections through network
            for conn in profile.connections:
                if hasattr(conn, 'raddr') and conn.raddr:
                    remote_ip = conn.raddr.ip
                    for other_pid, other_profile in self.processes.items():
                        if other_pid != pid:
                            for other_conn in other_profile.connections:
                                if (hasattr(other_conn, 'laddr') and other_conn.laddr and
                                    other_conn.laddr.ip == remote_ip):
                                    if other_pid not in profile.social_connections:
                                        profile.social_connections.append(other_pid)
            
            # Connections through files
            for filename in profile.open_files:
                if filename in self.file_handles:
                    for other_pid in self.file_handles[filename]:
                        if other_pid != pid and other_pid not in profile.social_connections:
                            profile.social_connections.append(other_pid)
    
    def get_process_tree(self, root_pid: Optional[int] = None) -> Dict:
        """Get hierarchical process tree."""
        tree = {}
        
        if root_pid is None:
            # Find init/systemd process
            for pid, profile in self.processes.items():
                if profile.ppid == 0:
                    root_pid = pid
                    break
        
        if root_pid in self.processes:
            self._build_tree(root_pid, tree)
        
        return tree
    
    def _build_tree(self, pid: int, node: Dict):
        """Recursively build process tree."""
        profile = self.processes[pid]
        node['pid'] = pid
        node['name'] = profile.name
        node['children'] = []
        
        for child_pid in profile.children:
            child_node = {}
            self._build_tree(child_pid, child_node)
            node['children'].append(child_node)
    
    def find_entity_processes(self, entity_id: str) -> List[PIDProfile]:
        """Find all processes associated with an entity."""
        pids = [pid for pid, eid in self.entity_map.items() if eid == entity_id]
        return [self.processes[pid] for pid in pids if pid in self.processes]
    
    def map_entity_to_process(self, entity_id: str, pid: int):
        """Map an entity to a process."""
        self.entity_map[pid] = entity_id
        if pid in self.processes:
            # Calculate influence score based on process properties
            profile = self.processes[pid]
            influence = 0.0
            influence += min(profile.cpu_percent / 100, 1.0) * 0.3
            influence += min(profile.memory_percent / 100, 1.0) * 0.3
            influence += len(profile.social_connections) * 0.1
            influence += len(profile.children) * 0.1
            influence += len(profile.connections) * 0.1
            influence += len(profile.open_files) * 0.1
            profile.influence_score = min(influence, 1.0)

# ============================================================================
# TAXONOMIC CLASSIFICATION ENGINE
# ============================================================================

class TaxonomicClassifier:
    """Classify scripts into the digital ecosystem taxonomy."""
    
    def __init__(self):
        self.knowledge_base = self._load_knowledge_base()
        self.patterns = self._load_patterns()
        self.gene_pool: Dict[str, ComputationalGene] = {}
        self.entity_counter = 0
        
        # Classification rules
        self.kingdom_rules = {
            DigitalKingdom.GUI_APPLICATION: [
                lambda imp: any(gui in imp for gui in ['tkinter', 'PyQt', 'wx', 'kivy', 'pygame']),
                lambda code: re.search(r'(Tk|QApplication|wx\.App|App\.run|pygame\.init)', code),
                lambda funcs: any('mainloop' in f.lower() or 'show' in f.lower() for f in funcs)
            ],
            DigitalKingdom.CLI_UTILITY: [
                lambda imp: any(cli in imp for cli in ['argparse', 'click', 'fire', 'docopt']),
                lambda code: re.search(r'argparse\.ArgumentParser|click\.command|sys\.argv', code),
                lambda funcs: any('parse' in f.lower() or 'cli' in f.lower() for f in funcs)
            ],
            DigitalKingdom.NETWORK_SERVICE: [
                lambda imp: any(net in imp for net in ['socket', 'http', 'flask', 'django', 'requests']),
                lambda code: re.search(r'(listen|bind|connect|serve|server|client)', code, re.I),
                lambda funcs: any('socket' in f.lower() or 'request' in f.lower() for f in funcs)
            ],
            DigitalKingdom.DATA_PROCESSOR: [
                lambda imp: any(data in imp for data in ['pandas', 'numpy', 'sklearn', 'tensorflow', 'pytorch']),
                lambda code: re.search(r'(DataFrame|array|train|fit|predict|transform)', code),
                lambda funcs: any('process' in f.lower() or 'analyze' in f.lower() for f in funcs)
            ],
            DigitalKingdom.SERVICE_DAEMON: [
                lambda imp: any(svc in imp for svc in ['daemon', 'systemd', 'service', 'threading']),
                lambda code: re.search(r'(while True|daemonize|run_forever|event_loop)', code),
                lambda funcs: any('daemon' in f.lower() or 'service' in f.lower() for f in funcs)
            ]
        }
    
    def _load_knowledge_base(self) -> Dict:
        """Load taxonomic knowledge base."""
        return {
            'import_patterns': {
                'gui': ['tkinter', 'PyQt5', 'wx', 'kivy', 'pygame', 'gtk', 'fltk'],
                'cli': ['argparse', 'click', 'fire', 'docopt', 'prompt_toolkit'],
                'network': ['socket', 'requests', 'aiohttp', 'flask', 'django', 'fastapi'],
                'data': ['pandas', 'numpy', 'scipy', 'sklearn', 'tensorflow', 'torch'],
                'system': ['os', 'sys', 'subprocess', 'shutil', 'pathlib', 'psutil'],
                'security': ['cryptography', 'ssl', 'hashlib', 'hmac', 'secrets'],
                'cloud': ['boto3', 'azure', 'google.cloud', 'openstack', 'docker'],
                'database': ['sqlite3', 'psycopg2', 'mysql', 'pymongo', 'redis']
            },
            'behavior_patterns': {
                'io_intensive': ['open(', 'read(', 'write(', 'save(', 'load('],
                'cpu_intensive': ['while True:', 'for _ in range(', 'math.sqrt('],
                'memory_intensive': ['list() *', 'array(', 'zeros(', 'ones('],
                'network_intensive': ['socket.', 'connect(', 'send(', 'recv('],
                'parallel': ['threading.', 'multiprocessing.', 'concurrent.'],
                'async': ['async def', 'await ', 'asyncio.']
            },
            'genetic_markers': {
                'import_statements': 'import patterns indicate environmental adaptation',
                'function_patterns': 'behavioral routines indicate cognitive capabilities',
                'class_structures': 'organizational complexity indicates social structure',
                'error_handling': 'robustness mechanisms indicate survival strategies',
                'logging_patterns': 'self-awareness and observability',
                'configuration': 'environmental adaptation and flexibility'
            }
        }
    
    def _load_patterns(self) -> Dict:
        """Load classification patterns."""
        return {
            'file_operations': {
                'pattern': r'(open|read|write|close|seek|tell|flush)\([^)]*\)',
                'weight': 0.3,
                'territory': Territory.LOCAL_FILESYSTEM
            },
            'network_operations': {
                'pattern': r'(socket|connect|bind|listen|send|recv|request|get|post)\([^)]*\)',
                'weight': 0.4,
                'territory': Territory.NETWORK_INTERFACE
            },
            'process_operations': {
                'pattern': r'(subprocess|Popen|run|call|spawn|fork|exec)\([^)]*\)',
                'weight': 0.5,
                'territory': Territory.PROCESS_SPACE
            },
            'gui_operations': {
                'pattern': r'(Tk|mainloop|Button|Label|Window|show|display)\([^)]*\)',
                'weight': 0.2,
                'territory': Territory.VIDEO_DEVICE
            },
            'database_operations': {
                'pattern': r'(execute|fetch|commit|rollback|connect|cursor)\([^)]*\)',
                'weight': 0.3,
                'territory': Territory.LOCAL_FILESYSTEM
            },
            'parallel_operations': {
                'pattern': r'(Thread|Process|Pool|Executor|async|await)\([^)]*\)',
                'weight': 0.4,
                'territory': Territory.CPU_CORES
            }
        }
    
    def classify_script(self, filepath: Path, content: str) -> DigitalEntity:
        """Classify a script file as a digital entity."""
        # Parse AST
        try:
            tree = ast.parse(content)
        except SyntaxError:
            tree = None
        
        # Extract features
        features = self.extract_features(filepath, content, tree)
        
        # Determine kingdom
        kingdom = self.determine_kingdom(features)
        
        # Determine territories
        territories = self.determine_territories(features)
        
        # Determine consciousness level
        consciousness = self.determine_consciousness(features)
        
        # Determine social structure
        social_structure = self.determine_social_structure(features)
        
        # Determine influence level
        influence = self.determine_influence(features, territories)
        
        # Extract genetic markers
        genes = self.extract_genetic_markers(features)
        
        # Generate entity ID
        self.entity_counter += 1
        entity_id = f"entity_{self.entity_counter:06d}_{kingdom.name.lower()}"
        
        # Create memory system
        memory = EntityMemory(
            short_term=deque(maxlen=100),
            long_term={},
            procedural={},
            episodic=[],
            genetic=genes
        )
        
        # Store initial experiences
        memory.remember({
            'type': 'birth',
            'location': str(filepath),
            'kingdom': kingdom.name,
            'size': len(content)
        }, importance=1.0)
        
        # Create entity
        entity = DigitalEntity(
            entity_id=entity_id,
            name=filepath.stem,
            kingdom=kingdom,
            species=self.determine_species(kingdom, features),
            pid=None,  # Will be set when process is spawned
            hash_dna=self.compute_genetic_hash(content),
            birth_time=datetime.now(),
            lifecycle_stage=LifecycleStage.GESTATION,
            consciousness=consciousness,
            memory=memory,
            genes=genes,
            learning_rate=self.calculate_learning_rate(features),
            social_structure=social_structure,
            communication_methods=self.determine_communication_methods(features),
            relationships={},
            territories=territories,
            network_domains=[],
            hardware_access=[],
            influence=influence,
            energy_sources=self.determine_energy_sources(features),
            energy_consumption={},
            metabolic_rate=self.calculate_metabolic_rate(features),
            aggression=self.calculate_aggression(features),
            cooperation=self.calculate_cooperation(features),
            curiosity=self.calculate_curiosity(features),
            adaptability=self.calculate_adaptability(features),
            health=1.0,
            stress_level=0.0,
            goals=self.extract_goals(features),
            current_behavior='initializing',
            manifest=self.create_manifest(filepath, features),
            catalog_entry=self.create_catalog_entry(entity_id, features),
            version='1.0',
            # Trust layer defaults (Wire 3 — conservative until Wire 1+2 populate)
            trust_tier='UNTRUSTED',
            farm_zone=False,
            domain='',
            native_function=False,
            zero_sum=False,
            confidence_level=0.0,
            ptsd_weight=1.0,
            spawn_spec=self._infer_spawn_spec(features, kingdom),
        )
        
        # Add to gene pool
        for gene in genes:
            self.gene_pool[f"{gene.gene_type}:{gene.sequence[:50]}"] = gene

        return entity

    # --- SPAWN SPEC HELPERS (Wire 3 — 2026-03-03) ---
    # Infer SpawnSpec fields from kingdom + features.
    # Conservative defaults — Wire 1+2 will override with pymanifest ground truth.

    def _infer_spawn_spec(self, features: Dict, kingdom: DigitalKingdom) -> SpawnSpec:
        """Infer spawn specification from classification results."""
        return SpawnSpec(
            spawn_type=self._infer_spawn_type(features, kingdom),
            system_type=self._infer_system_type(kingdom),
            nest_level=1,
            field_nest_eligible=False,  # Wire 2 gates this on trust_tier==TRUSTED
            logic_nesting_depth=self._infer_nesting_depth(kingdom),
            omega_compartment=self._infer_compartment(kingdom),
            tab_context=self._infer_tab_context(kingdom, features),
            ui_tier='',        # Wire 1: read from system_inventory UI&UX hierarchy
            ua_tags=[],        # Wire 1: read from link_map.json UA entries
            compression_level=0,
        )

    def _infer_spawn_type(self, features: Dict, kingdom: DigitalKingdom) -> str:
        """Map kingdom + GUI presence to spawn_type string."""
        gui_kingdoms = {
            DigitalKingdom.GUI_APPLICATION, DigitalKingdom.DESKTOP_APP,
            DigitalKingdom.WEB_APPLICATION, DigitalKingdom.MOBILE_APP,
        }
        if kingdom in gui_kingdoms or 'gui' in features.get('patterns_found', []):
            return 'gui'
        if kingdom == DigitalKingdom.HYBRID:
            return 'mutation'
        if kingdom in {DigitalKingdom.SERVICE_DAEMON, DigitalKingdom.SERVER_PROCESS}:
            return 'service'
        if kingdom in {DigitalKingdom.IOT_DEVICE, DigitalKingdom.FIRMWARE}:
            return 'micro'
        return 'cli'

    def _infer_system_type(self, kingdom: DigitalKingdom) -> str:
        """Map kingdom to gate_policies.json system_type."""
        return {
            DigitalKingdom.GUI_APPLICATION:    'Communication',
            DigitalKingdom.NETWORK_SERVICE:    'Communication',
            DigitalKingdom.WEB_APPLICATION:    'Communication',
            DigitalKingdom.MOBILE_APP:         'Communication',
            DigitalKingdom.DESKTOP_APP:        'Communication',
            DigitalKingdom.DATA_PROCESSOR:     'Observation',
            DigitalKingdom.SCIENTIFIC_COMPUTE: 'Observation',
            DigitalKingdom.SERVICE_DAEMON:     'System Health',
            DigitalKingdom.AUTOMATION_SCRIPT:  'System Health',
            DigitalKingdom.TEST_SUITE:         'System Health',
            DigitalKingdom.KERNEL_MODULE:      'System Health',
            DigitalKingdom.CLI_UTILITY:        'Tools & Arsenal',
            DigitalKingdom.LIBRARY_MODULE:     'Tools & Arsenal',
            DigitalKingdom.HYBRID:             'System Health',
        }.get(kingdom, 'Tools & Arsenal')

    def _infer_nesting_depth(self, kingdom: DigitalKingdom) -> int:
        """Map kingdom to signal_bus logic nesting depth (0-4)."""
        return {
            DigitalKingdom.GUI_APPLICATION:    0,  # pineal (display — pre-signal substrate)
            DigitalKingdom.SERVICE_DAEMON:     1,  # omega_0→alpha_inf probe
            DigitalKingdom.DATA_PROCESSOR:     2,  # alpha_inf→alpha_1 pattern lookup
            DigitalKingdom.LIBRARY_MODULE:     2,  # alpha_inf synthesis
            DigitalKingdom.SCIENTIFIC_COMPUTE: 2,  # alpha_inf computation
            DigitalKingdom.CLI_UTILITY:        3,  # alpha_1→motor tool execution
            DigitalKingdom.AUTOMATION_SCRIPT:  3,  # alpha_1→motor
            DigitalKingdom.HYBRID:             3,  # all layers (custom_code_tab)
            DigitalKingdom.TEST_SUITE:         4,  # return/verify path
            DigitalKingdom.NETWORK_SERVICE:    4,  # cross-env sync (return path)
        }.get(kingdom, 3)

    def _infer_compartment(self, kingdom: DigitalKingdom) -> str:
        """Map kingdom to omega_state_runtime compartment name."""
        return {
            DigitalKingdom.GUI_APPLICATION:    'pineal',
            DigitalKingdom.DESKTOP_APP:        'pineal',
            DigitalKingdom.SERVICE_DAEMON:     'omega_0',
            DigitalKingdom.TEST_SUITE:         'omega_0',
            DigitalKingdom.KERNEL_MODULE:      'omega_0',
            DigitalKingdom.LIBRARY_MODULE:     'alpha_inf',
            DigitalKingdom.SCIENTIFIC_COMPUTE: 'alpha_inf',
            DigitalKingdom.DATA_PROCESSOR:     'omega_2',
            DigitalKingdom.CLI_UTILITY:        'alpha_1',
            DigitalKingdom.AUTOMATION_SCRIPT:  'omega_3',
            DigitalKingdom.NETWORK_SERVICE:    'dmn',
            DigitalKingdom.HYBRID:             'alpha_1',
        }.get(kingdom, 'alpha_1')

    def _infer_tab_context(self, kingdom: DigitalKingdom, features: Dict) -> str:
        """Map kingdom to Trainer GUI tab context (read-only reference, no live wiring)."""
        if kingdom in {DigitalKingdom.GUI_APPLICATION, DigitalKingdom.DESKTOP_APP}:
            return 'map_tab'
        if kingdom == DigitalKingdom.HYBRID:
            return 'custom_code_tab'
        if 'gui' in features.get('patterns_found', []):
            return 'map_tab'
        return ''

    def extract_features(self, filepath: Path, content: str, tree: Optional[ast.AST]) -> Dict:
        """Extract classification features from script."""
        features = {
            'filepath': str(filepath),
            'size': len(content),
            'lines': content.count('\n') + 1,
            'imports': [],
            'functions': [],
            'classes': [],
            'patterns_found': [],
            'complexity_score': 0,
            'network_calls': 0,
            'file_operations': 0,
            'process_calls': 0,
            'gui_calls': 0
        }
        
        # Extract imports
        import_pattern = r'^\s*(?:import|from)\s+(\w+)'
        features['imports'] = re.findall(import_pattern, content, re.MULTILINE)
        
        # Extract functions
        func_pattern = r'def\s+(\w+)\s*\('
        features['functions'] = re.findall(func_pattern, content)
        
        # Extract classes
        class_pattern = r'class\s+(\w+)'
        features['classes'] = re.findall(class_pattern, content)
        
        # Count pattern occurrences
        for pattern_name, pattern_info in self.patterns.items():
            matches = re.findall(pattern_info['pattern'], content, re.IGNORECASE)
            if matches:
                features['patterns_found'].append(pattern_name)
                # Update specific counters
                if 'network' in pattern_name:
                    features['network_calls'] += len(matches)
                elif 'file' in pattern_name:
                    features['file_operations'] += len(matches)
                elif 'process' in pattern_name:
                    features['process_calls'] += len(matches)
                elif 'gui' in pattern_name:
                    features['gui_calls'] += len(matches)
        
        # Calculate complexity (simplified)
        features['complexity_score'] = self.calculate_complexity(content)
        
        return features
    
    def calculate_complexity(self, content: str) -> float:
        """Calculate code complexity score."""
        score = 0.0
        
        # Function count
        func_count = len(re.findall(r'def\s+\w+\s*\(', content))
        score += min(func_count * 0.1, 1.0)
        
        # Class count
        class_count = len(re.findall(r'class\s+\w+', content))
        score += min(class_count * 0.2, 1.0)
        
        # Control structures
        controls = len(re.findall(r'(if|for|while|try|except|with)\s+', content))
        score += min(controls * 0.05, 1.0)
        
        # Nesting depth (approximate)
        lines = content.split('\n')
        max_indent = 0
        for line in lines:
            indent = len(line) - len(line.lstrip())
            max_indent = max(max_indent, indent)
        score += min(max_indent / 40, 1.0) * 0.2
        
        return min(score, 1.0)
    
    def determine_kingdom(self, features: Dict) -> DigitalKingdom:
        """Determine the primary kingdom."""
        scores = {}
        imports_str = ' '.join(features['imports'])
        functions_str = ' '.join(features['functions'])
        content = features.get('content_preview', '')
        
        for kingdom, rules in self.kingdom_rules.items():
            score = 0.0
            for rule in rules:
                try:
                    if rule(imports_str) or rule(content) or rule(functions_str):
                        score += 1.0
                except:
                    pass
            scores[kingdom] = score
        
        # Special cases
        if features['gui_calls'] > 0:
            scores[DigitalKingdom.GUI_APPLICATION] += 2.0
        if features['network_calls'] > 5:
            scores[DigitalKingdom.NETWORK_SERVICE] += 2.0
        if features['file_operations'] > 10 and features['network_calls'] == 0:
            scores[DigitalKingdom.DATA_PROCESSOR] += 1.0
        
        # Find highest scoring kingdom
        if scores:
            best_kingdom = max(scores.items(), key=lambda x: x[1])
            if best_kingdom[1] > 0:
                return best_kingdom[0]
        
        return DigitalKingdom.UNKNOWN
    
    def determine_territories(self, features: Dict) -> List[Territory]:
        """Determine operational territories."""
        territories = set()
        
        # File operations territory
        if features['file_operations'] > 0:
            territories.add(Territory.LOCAL_FILESYSTEM)
        
        # Network operations territory
        if features['network_calls'] > 0:
            territories.add(Territory.NETWORK_INTERFACE)
            territories.add(Territory.NETWORK_NAMESPACE)
        
        # Process operations territory
        if features['process_calls'] > 0:
            territories.add(Territory.PROCESS_SPACE)
            territories.add(Territory.USER_SPACE)
        
        # GUI operations territory
        if features['gui_calls'] > 0:
            territories.add(Territory.VIDEO_DEVICE)
        
        # Complexity suggests memory usage
        if features['complexity_score'] > 0.7:
            territories.add(Territory.MEMORY_SPACE)
        
        # Always have process space
        territories.add(Territory.PROCESS_SPACE)
        
        return list(territories)
    
    def determine_consciousness(self, features: Dict) -> ConsciousnessLevel:
        """Determine consciousness level."""
        score = 0.0
        
        # Learning indicators
        if any(imp in features['imports'] for imp in ['sklearn', 'tensorflow', 'torch', 'keras']):
            score += 2.0
        
        # Adaptation indicators
        if any(patt in features['patterns_found'] for patt in ['config', 'settings', 'env']):
            score += 1.0
        
        # Self-awareness indicators
        if any(patt in features['patterns_found'] for patt in ['logging', 'monitor', 'metrics']):
            score += 1.5
        
        # Decision making indicators
        if features['complexity_score'] > 0.5:
            score += 1.0
        
        # Map to consciousness level
        if score >= 4.0:
            return ConsciousnessLevel.COGNITIVE
        elif score >= 2.5:
            return ConsciousnessLevel.PROACTIVE
        elif score >= 1.0:
            return ConsciousnessLevel.REACTIVE
        else:
            return ConsciousnessLevel.REFLEXIVE
    
    def determine_social_structure(self, features: Dict) -> SocialStructure:
        """Determine social structure."""
        # Check for client-server patterns
        if features['network_calls'] > 5:
            return SocialStructure.HIERARCHICAL
        
        # Check for parallel processing
        if any(patt in features['patterns_found'] for patt in ['parallel', 'thread', 'process']):
            return SocialStructure.SWARM
        
        # Check for dependency on other modules
        if len(features['imports']) > 10:
            return SocialStructure.SYMBIOTIC
        
        # Default for simple scripts
        return SocialStructure.SOLITARY
    
    def determine_influence(self, features: Dict, territories: List[Territory]) -> InfluenceLevel:
        """Determine influence level."""
        influence_score = 0.0
        
        # Territory influence
        territory_weights = {
            Territory.LOCAL_FILESYSTEM: 0.5,
            Territory.NETWORK_INTERFACE: 1.0,
            Territory.PROCESS_SPACE: 1.5,
            Territory.VIDEO_DEVICE: 0.3,
            Territory.MEMORY_SPACE: 0.7,
            Territory.CPU_CORES: 1.2
        }
        
        for territory in territories:
            influence_score += territory_weights.get(territory, 0.5)
        
        # Feature influence
        influence_score += min(features['network_calls'] / 10, 2.0)
        influence_score += min(features['process_calls'] / 5, 2.0)
        influence_score += features['complexity_score']
        
        # Map to influence level
        if influence_score >= 6.0:
            return InfluenceLevel.SYSTEMIC
        elif influence_score >= 4.0:
            return InfluenceLevel.ORGANIC
        elif influence_score >= 2.0:
            return InfluenceLevel.MICROBIAL
        else:
            return InfluenceLevel.MICROBIAL
    
    def extract_genetic_markers(self, features: Dict) -> List[ComputationalGene]:
        """Extract genetic markers from features."""
        genes = []
        
        # Import genes
        for imp in features['imports'][:10]:  # Limit to first 10
            genes.append(ComputationalGene(
                gene_type='import',
                sequence=imp,
                expression_level=1.0,
                mutations=[],
                epigenetic_marks={'frequency': 1}
            ))
        
        # Function pattern genes
        func_patterns = self._extract_function_patterns(features)
        for pattern in func_patterns:
            genes.append(ComputationalGene(
                gene_type='function_pattern',
                sequence=pattern['pattern'],
                expression_level=pattern['frequency'],
                mutations=pattern['variations'],
                epigenetic_marks={'complexity': pattern['complexity']}
            ))
        
        # Behavioral genes
        for pattern_name in features['patterns_found']:
            genes.append(ComputationalGene(
                gene_type='behavior',
                sequence=pattern_name,
                expression_level=1.0,
                mutations=[],
                epigenetic_marks={'territory': self.patterns.get(pattern_name, {}).get('territory', None)}
            ))
        
        return genes
    
    def _extract_function_patterns(self, features: Dict) -> List[Dict]:
        """Extract patterns from function names."""
        patterns = []
        func_counter = Counter(features['functions'])
        
        for func, count in func_counter.most_common(5):
            pattern = {
                'pattern': func,
                'frequency': count / max(len(features['functions']), 1),
                'variations': [],
                'complexity': 0.5  # Placeholder
            }
            
            # Categorize function type
            if func.startswith('get_') or func.startswith('fetch_'):
                pattern['variations'].append('accessor')
            elif func.startswith('set_') or func.startswith('update_'):
                pattern['variations'].append('mutator')
            elif func.startswith('is_') or func.startswith('has_'):
                pattern['variations'].append('predicate')
            elif func.startswith('handle_') or func.startswith('process_'):
                pattern['variations'].append('handler')
            
            patterns.append(pattern)
        
        return patterns
    
    def determine_species(self, kingdom: DigitalKingdom, features: Dict) -> str:
        """Determine species within kingdom."""
        # Create species identifier based on key characteristics
        traits = []
        
        # Add primary trait based on most common pattern
        if features['patterns_found']:
            primary_pattern = max(set(features['patterns_found']), 
                                key=features['patterns_found'].count)
            traits.append(primary_pattern)
        
        # Add secondary trait based on complexity
        if features['complexity_score'] > 0.7:
            traits.append('complex')
        elif features['complexity_score'] < 0.3:
            traits.append('simple')
        
        # Add trait based on import domain
        if any(gui in features['imports'] for gui in self.knowledge_base['import_patterns']['gui']):
            traits.append('visual')
        if any(net in features['imports'] for net in self.knowledge_base['import_patterns']['network']):
            traits.append('networked')
        if any(data in features['imports'] for data in self.knowledge_base['import_patterns']['data']):
            traits.append('data_processor')
        
        species = f"{kingdom.name.lower()}_{'_'.join(traits[:3])}" if traits else f"{kingdom.name.lower()}_basic"
        return species[:50]  # Limit length
    
    def determine_communication_methods(self, features: Dict) -> List[CommunicationMethod]:
        """Determine communication methods."""
        methods = set()
        
        if features['network_calls'] > 0:
            methods.add(CommunicationMethod.SOCKETS)
            methods.add(CommunicationMethod.HTTP)
        
        if features['file_operations'] > 0:
            methods.add(CommunicationMethod.FILESYSTEM)
        
        if features['process_calls'] > 0:
            methods.add(CommunicationMethod.PIPES)
            methods.add(CommunicationMethod.SIGNALS)
        
        if any('queue' in patt for patt in features['patterns_found']):
            methods.add(CommunicationMethod.MESSAGE_QUEUE)
        
        # Always have basic communication
        methods.add(CommunicationMethod.FILESYSTEM)
        
        return list(methods)
    
    def determine_energy_sources(self, features: Dict) -> List[EnergySource]:
        """Determine energy sources."""
        sources = set()
        
        # Always need CPU cycles
        sources.add(EnergySource.CPU_CYCLES)
        
        if features['network_calls'] > 0:
            sources.add(EnergySource.NETWORK_BANDWIDTH)
        
        if features['file_operations'] > 0:
            sources.add(EnergySource.DISK_IO)
        
        if features['complexity_score'] > 0.6:
            sources.add(EnergySource.MEMORY_ALLOCATION)
        
        if any('async' in patt or 'thread' in patt for patt in features['patterns_found']):
            sources.add(EnergySource.EVENT_DRIVEN)
        
        return list(sources)
    
    def calculate_learning_rate(self, features: Dict) -> float:
        """Calculate learning rate based on adaptability indicators."""
        rate = 0.1  # Base rate
        
        # Configurability increases learning
        if any('config' in patt for patt in features['patterns_found']):
            rate += 0.2
        
        # ML imports indicate learning capability
        if any(imp in features['imports'] for imp in ['sklearn', 'tensorflow', 'keras', 'pytorch']):
            rate += 0.3
        
        # Complex code can learn more
        rate += features['complexity_score'] * 0.2
        
        return min(rate, 1.0)
    
    def calculate_metabolic_rate(self, features: Dict) -> float:
        """Calculate resource consumption rate."""
        rate = 0.0
        
        # Network calls consume bandwidth
        rate += min(features['network_calls'] / 20, 1.0) * 0.3
        
        # File operations consume disk I/O
        rate += min(features['file_operations'] / 30, 1.0) * 0.2
        
        # Process calls consume system resources
        rate += min(features['process_calls'] / 10, 1.0) * 0.3
        
        # Complexity correlates with resource usage
        rate += features['complexity_score'] * 0.2
        
        return min(rate, 1.0)
    
    def calculate_aggression(self, features: Dict) -> float:
        """Calculate aggression level."""
        aggression = 0.0
        
        # Process spawning is aggressive
        aggression += min(features['process_calls'] / 5, 1.0) * 0.4
        
        # Network scanning/attacking patterns
        if any(patt in features['patterns_found'] for patt in ['scan', 'brute', 'attack', 'exploit']):
            aggression += 0.4
        
        # File system intrusion
        if features['file_operations'] > 20:
            aggression += 0.2
        
        return min(aggression, 1.0)
    
    def calculate_cooperation(self, features: Dict) -> float:
        """Calculate cooperation level."""
        cooperation = 0.0
        
        # API clients cooperate with servers
        if any(patt in features['patterns_found'] for patt in ['client', 'api', 'request']):
            cooperation += 0.3
        
        # Libraries are cooperative by nature
        if len(features['classes']) > 3 and len(features['functions']) > 10:
            cooperation += 0.4
        
        # Error handling indicates robustness for cooperation
        if any(patt in features['patterns_found'] for patt in ['try', 'except', 'finally']):
            cooperation += 0.2
        
        # Network services must cooperate
        if features['network_calls'] > 5:
            cooperation += 0.1
        
        return min(cooperation, 1.0)
    
    def calculate_curiosity(self, features: Dict) -> float:
        """Calculate curiosity level."""
        curiosity = 0.0
        
        # Exploration patterns
        if any(patt in features['patterns_found'] for patt in ['explore', 'discover', 'scan', 'crawl']):
            curiosity += 0.5
        
        # Data collection
        if features['file_operations'] > 10:
            curiosity += 0.2
        
        # Network exploration
        if features['network_calls'] > 5:
            curiosity += 0.3
        
        return min(curiosity, 1.0)
    
    def calculate_adaptability(self, features: Dict) -> float:
        """Calculate adaptability level."""
        adaptability = 0.0
        
        # Configuration handling
        if any(patt in features['patterns_found'] for patt in ['config', 'settings', 'env']):
            adaptability += 0.4
        
        # Multiple communication methods
        comm_methods = self.determine_communication_methods(features)
        adaptability += min(len(comm_methods) / 5, 1.0) * 0.3
        
        # Error recovery
        if any(patt in features['patterns_found'] for patt in ['retry', 'fallback', 'backup']):
            adaptability += 0.3
        
        return min(adaptability, 1.0)
    
    def extract_goals(self, features: Dict) -> List[str]:
        """Extract apparent goals from code patterns."""
        goals = []
        
        # Data processing goals
        if features['file_operations'] > 5:
            goals.append("process_data")
        
        # Network service goals
        if features['network_calls'] > 5:
            goals.append("serve_requests")
        
        # User interaction goals
        if features['gui_calls'] > 0:
            goals.append("interact_with_user")
        
        # Automation goals
        if features['process_calls'] > 0:
            goals.append("automate_tasks")
        
        # Learning goals
        if any(imp in features['imports'] for imp in ['sklearn', 'tensorflow', 'keras']):
            goals.append("learn_patterns")
        
        # Default goal
        if not goals:
            goals.append("execute_code")
        
        return goals
    
    def create_manifest(self, filepath: Path, features: Dict) -> Dict:
        """Create manifest for entity."""
        return {
            'filename': filepath.name,
            'path': str(filepath),
            'size': features['size'],
            'lines': features['lines'],
            'imports': features['imports'],
            'functions': features['functions'],
            'classes': features['classes'],
            'patterns': features['patterns_found'],
            'complexity': features['complexity_score'],
            'analysis_timestamp': datetime.now().isoformat(),
            'genetic_signature': self.compute_genetic_hash(str(features))
        }
    
    def create_catalog_entry(self, entity_id: str, features: Dict) -> Dict:
        """Create catalog entry for entity."""
        return {
            'entity_id': entity_id,
            'discovery_time': datetime.now().isoformat(),
            'features': {
                'import_count': len(features['imports']),
                'function_count': len(features['functions']),
                'class_count': len(features['classes']),
                'pattern_count': len(features['patterns_found']),
                'network_operations': features['network_calls'],
                'file_operations': features['file_operations']
            },
            'genetic_hash': self.compute_genetic_hash(str(features))
        }
    
    def compute_genetic_hash(self, content: str) -> str:
        """Compute genetic hash for content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:32]

# ============================================================================
# ECOSYSTEM MANAGER
# ============================================================================

class DigitalEcosystem:
    """Manages the digital ecosystem of entities."""
    
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path.home() / '.digital_biosphere'
        self.setup_directories()
        
        # Core components
        self.classifier = TaxonomicClassifier()
        self.monitor = ProcessMonitor()
        self.entities: Dict[str, DigitalEntity] = {}
        self.entity_index: Dict[str, List[str]] = defaultdict(list)  # type -> entity_ids
        
        # Ecosystem state
        self.ecosystem_health = 1.0
        self.resource_pressure = 0.0
        self.evolution_rate = 0.1
        self.symbiosis_matrix: Dict[tuple, float] = {}  # (entity1, entity2) -> relationship_score
        
        # Statistics
        self.stats = {
            'total_entities': 0,
            'active_entities': 0,
            'kingdom_distribution': defaultdict(int),
            'total_interactions': 0,
            'avg_fitness': 0.0,
            'evolutionary_events': 0
        }
        
        # Database
        self.db_path = self.data_dir / 'ecosystem.db'
        self.init_database()
        
        # Logging
        self.log_file = self.data_dir / 'logs' / 'ecosystem.log'
        self.setup_logging()
    
    def setup_directories(self):
        """Create necessary directories."""
        directories = [
            'catalogs',
            'manifests',
            'graphs',
            'diffs',
            'policies',
            'logs',
            'versions',
            'profiles',
            'genomes',
            'relationships',
            'snapshots'
        ]
        
        for dir_name in directories:
            dir_path = self.data_dir / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler()
            ]
        )
    
    def init_database(self):
        """Initialize ecosystem database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Entities table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                name TEXT,
                kingdom TEXT,
                species TEXT,
                birth_time TEXT,
                fitness REAL,
                health REAL,
                manifest TEXT,
                catalog_entry TEXT,
                version TEXT,
                trust_tier TEXT DEFAULT 'UNTRUSTED',
                farm_zone INTEGER DEFAULT 0,
                domain TEXT DEFAULT '',
                native_function INTEGER DEFAULT 0,
                zero_sum INTEGER DEFAULT 0,
                confidence_level REAL DEFAULT 0.0,
                ptsd_weight REAL DEFAULT 1.0,
                spawn_type TEXT DEFAULT 'cli',
                system_type TEXT DEFAULT 'Tools & Arsenal',
                nest_level INTEGER DEFAULT 1,
                omega_compartment TEXT DEFAULT 'alpha_1',
                tab_context TEXT DEFAULT ''
            )
        ''')
        # Migration: add trust layer columns to pre-existing databases
        trust_columns = [
            ('trust_tier', "TEXT DEFAULT 'UNTRUSTED'"),
            ('farm_zone', 'INTEGER DEFAULT 0'),
            ('domain', "TEXT DEFAULT ''"),
            ('native_function', 'INTEGER DEFAULT 0'),
            ('zero_sum', 'INTEGER DEFAULT 0'),
            ('confidence_level', 'REAL DEFAULT 0.0'),
            ('ptsd_weight', 'REAL DEFAULT 1.0'),
            ('spawn_type', "TEXT DEFAULT 'cli'"),
            ('system_type', "TEXT DEFAULT 'Tools & Arsenal'"),
            ('nest_level', 'INTEGER DEFAULT 1'),
            ('omega_compartment', "TEXT DEFAULT 'alpha_1'"),
            ('tab_context', "TEXT DEFAULT ''"),
        ]
        for col_name, col_def in trust_columns:
            try:
                cursor.execute(f'ALTER TABLE entities ADD COLUMN {col_name} {col_def}')
            except Exception:
                pass  # Column already exists — safe to ignore
        
        # Interactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                entity1 TEXT,
                entity2 TEXT,
                interaction_type TEXT,
                success BOOLEAN,
                outcome TEXT
            )
        ''')
        
        # Genetic pool table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS genes (
                gene_id TEXT PRIMARY KEY,
                gene_type TEXT,
                sequence TEXT,
                expression_level REAL,
                discovered_in TEXT,
                first_seen TEXT
            )
        ''')
        
        # Ecosystem snapshots
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS snapshots (
                timestamp TEXT PRIMARY KEY,
                total_entities INTEGER,
                ecosystem_health REAL,
                resource_pressure REAL,
                stats TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def discover_entity(self, filepath: Path) -> Optional[DigitalEntity]:
        """Discover and classify a new entity from a script file."""
        try:
            content = filepath.read_text(encoding='utf-8', errors='ignore')
            entity = self.classifier.classify_script(filepath, content)
            
            # Add to ecosystem
            self.entities[entity.entity_id] = entity
            self.entity_index[entity.kingdom.name].append(entity.entity_id)
            
            # Update statistics
            self.stats['total_entities'] += 1
            self.stats['kingdom_distribution'][entity.kingdom.name] += 1
            
            # Save to database
            self.save_entity(entity)
            
            # Log discovery
            logging.info(f"Discovered new entity: {entity.name} ({entity.entity_id}) "
                        f"Kingdom: {entity.kingdom.name}, Species: {entity.species}")
            
            return entity
            
        except Exception as e:
            logging.error(f"Failed to discover entity from {filepath}: {e}")
            return None
    
    def save_entity(self, entity: DigitalEntity):
        """Save entity to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        ss = entity.spawn_spec or SpawnSpec()
        cursor.execute('''
            INSERT OR REPLACE INTO entities
            (id, name, kingdom, species, birth_time, fitness, health, manifest,
             catalog_entry, version,
             trust_tier, farm_zone, domain, native_function, zero_sum,
             confidence_level, ptsd_weight,
             spawn_type, system_type, nest_level, omega_compartment, tab_context)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            entity.entity_id,
            entity.name,
            entity.kingdom.name,
            entity.species,
            entity.birth_time.isoformat(),
            entity.calculate_fitness(),
            entity.health,
            json.dumps(entity.manifest),
            json.dumps(entity.catalog_entry),
            entity.version,
            entity.trust_tier,
            int(entity.farm_zone),
            entity.domain,
            int(entity.native_function),
            int(entity.zero_sum),
            entity.confidence_level,
            entity.ptsd_weight,
            ss.spawn_type,
            ss.system_type,
            ss.nest_level,
            ss.omega_compartment,
            ss.tab_context,
        ))
        
        # Save genes
        for gene in entity.genes:
            gene_id = f"{gene.gene_type}:{hash(gene.sequence) & 0xFFFFFFFF}"
            cursor.execute('''
                INSERT OR IGNORE INTO genes 
                (gene_id, gene_type, sequence, expression_level, discovered_in, first_seen)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                gene_id,
                gene.gene_type,
                gene.sequence[:500],  # Limit length
                gene.expression_level,
                entity.entity_id,
                datetime.now().isoformat()
            ))
        
        conn.commit()
        conn.close()
    
    def spawn_entity(self, entity: DigitalEntity, cmdline: List[str]) -> Optional[int]:
        """Spawn an entity as a running process."""
        try:
            # Execute the script
            process = subprocess.Popen(
                cmdline,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Map entity to process
            self.monitor.map_entity_to_process(entity.entity_id, process.pid)
            entity.pid = process.pid
            entity.lifecycle_stage = LifecycleStage.BIRTH
            
            # Update entity state
            entity.current_behavior = 'running'
            entity.memory.remember({
                'type': 'spawn',
                'pid': process.pid,
                'cmdline': cmdline,
                'timestamp': datetime.now().isoformat()
            }, importance=0.8)
            
            logging.info(f"Spawned entity {entity.name} as PID {process.pid}")
            
            # Monitor process in background
            threading.Thread(
                target=self._monitor_process,
                args=(process, entity),
                daemon=True
            ).start()
            
            return process.pid
            
        except Exception as e:
            logging.error(f"Failed to spawn entity {entity.name}: {e}")
            return None
    
    def _monitor_process(self, process: subprocess.Popen, entity: DigitalEntity):
        """Monitor a spawned process."""
        try:
            stdout, stderr = process.communicate(timeout=1)
            
            # Update entity based on execution
            if process.returncode == 0:
                entity.health = min(entity.health + 0.1, 1.0)
                entity.current_behavior = 'completed_success'
                entity.memory.remember({
                    'type': 'execution_success',
                    'returncode': process.returncode,
                    'stdout_length': len(stdout),
                    'stderr_length': len(stderr)
                }, importance=0.6)
            else:
                entity.health = max(entity.health - 0.2, 0.0)
                entity.stress_level = min(entity.stress_level + 0.3, 1.0)
                entity.current_behavior = 'failed'
                entity.memory.remember({
                    'type': 'execution_failed',
                    'returncode': process.returncode,
                    'stderr': stderr[:500]
                }, importance=0.8)
            
            # Update lifecycle
            entity.lifecycle_stage = LifecycleStage.DEATH
            
        except subprocess.TimeoutExpired:
            # Process is still running (daemon)
            entity.lifecycle_stage = LifecycleStage.MATURITY
            entity.current_behavior = 'running_daemon'
            process.terminate()
            
        except Exception as e:
            logging.error(f"Error monitoring process {entity.name}: {e}")
    
    def analyze_relationships(self):
        """Analyze relationships between entities."""
        entity_ids = list(self.entities.keys())
        
        for i, id1 in enumerate(entity_ids):
            for id2 in entity_ids[i+1:]:
                entity1 = self.entities[id1]
                entity2 = self.entities[id2]
                
                # Calculate relationship score
                score = self.calculate_relationship_score(entity1, entity2)
                self.symbiosis_matrix[(id1, id2)] = score
                
                # Update entity relationships
                if score > 0.3:  # Significant relationship
                    rel_type = self.classify_relationship(score, entity1, entity2)
                    
                    if id2 not in entity1.relationships:
                        entity1.relationships[id2] = []
                    if rel_type not in entity1.relationships[id2]:
                        entity1.relationships[id2].append(rel_type)
                    
                    if id1 not in entity2.relationships:
                        entity2.relationships[id1] = []
                    if rel_type not in entity2.relationships[id1]:
                        entity2.relationships[id1].append(rel_type)
                    
                    # Log interaction
                    interaction = entity1.interact(entity2, rel_type)
                    self.stats['total_interactions'] += 1
                    
                    # Save interaction to database
                    self.save_interaction(interaction)
    
    def calculate_relationship_score(self, entity1: DigitalEntity, entity2: DigitalEntity) -> float:
        """Calculate relationship score between two entities."""
        score = 0.0
        
        # Genetic similarity
        genetic_sim = self.calculate_genetic_similarity(entity1, entity2)
        score += genetic_sim * 0.3
        
        # Territory overlap
        territory_overlap = len(set(entity1.territories) & set(entity2.territories))
        score += min(territory_overlap / 5, 1.0) * 0.2
        
        # Communication compatibility
        comm_overlap = len(set(entity1.communication_methods) & set(entity2.communication_methods))
        score += min(comm_overlap / 3, 1.0) * 0.2
        
        # Social structure compatibility
        social_compat = self.calculate_social_compatibility(entity1.social_structure, entity2.social_structure)
        score += social_compat * 0.3
        
        return min(score, 1.0)
    
    def calculate_genetic_similarity(self, entity1: DigitalEntity, entity2: DigitalEntity) -> float:
        """Calculate genetic similarity between entities."""
        if not entity1.genes or not entity2.genes:
            return 0.0
        
        # Compare gene sequences
        matches = 0
        total = max(len(entity1.genes), len(entity2.genes))
        
        for gene1 in entity1.genes[:10]:  # Compare first 10 genes
            for gene2 in entity2.genes[:10]:
                if gene1.similarity(gene2) > 0.7:
                    matches += 1
                    break
        
        return matches / total
    
    def calculate_social_compatibility(self, struct1: SocialStructure, struct2: SocialStructure) -> float:
        """Calculate compatibility between social structures."""
        compatibility_matrix = {
            SocialStructure.SOLITARY: {
                SocialStructure.SOLITARY: 0.8,
                SocialStructure.COLONIAL: 0.3,
                SocialStructure.HIERARCHICAL: 0.1,
                SocialStructure.SWARM: 0.2,
                SocialStructure.SYMBIOTIC: 0.4,
                SocialStructure.PARASITIC: 0.0,
                SocialStructure.COMMENSAL: 0.5,
                SocialStructure.MUTUALISTIC: 0.6
            },
            SocialStructure.SYMBIOTIC: {
                SocialStructure.SOLITARY: 0.4,
                SocialStructure.COLONIAL: 0.7,
                SocialStructure.HIERARCHICAL: 0.6,
                SocialStructure.SWARM: 0.8,
                SocialStructure.SYMBIOTIC: 0.9,
                SocialStructure.PARASITIC: 0.2,
                SocialStructure.COMMENSAL: 0.7,
                SocialStructure.MUTUALISTIC: 1.0
            },
            # Add more as needed...
        }
        
        return compatibility_matrix.get(struct1, {}).get(struct2, 0.5)
    
    def classify_relationship(self, score: float, entity1: DigitalEntity, entity2: DigitalEntity) -> str:
        """Classify relationship type based on score and entity properties."""
        if score > 0.8:
            return "symbiotic"
        elif score > 0.6:
            if entity1.cooperation > 0.7 and entity2.cooperation > 0.7:
                return "mutualistic"
            else:
                return "cooperative"
        elif score > 0.4:
            return "neutral"
        elif score > 0.2:
            if entity1.aggression > 0.6 or entity2.aggression > 0.6:
                return "competitive"
            else:
                return "distant"
        else:
            return "isolated"
    
    def save_interaction(self, interaction: Dict):
        """Save interaction to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO interactions 
            (timestamp, entity1, entity2, interaction_type, success, outcome)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            interaction['timestamp'],
            interaction['entities'][0],
            interaction['entities'][1],
            interaction['type'],
            interaction['success'],
            json.dumps(interaction.get('outcome'))
        ))
        
        conn.commit()
        conn.close()
    
    def take_snapshot(self):
        """Take snapshot of ecosystem state."""
        snapshot = {
            'timestamp': datetime.now().isoformat(),
            'total_entities': len(self.entities),
            'ecosystem_health': self.ecosystem_health,
            'resource_pressure': self.resource_pressure,
            'stats': self.stats.copy()
        }
        
        # Save to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO snapshots 
            (timestamp, total_entities, ecosystem_health, resource_pressure, stats)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            snapshot['timestamp'],
            snapshot['total_entities'],
            snapshot['ecosystem_health'],
            snapshot['resource_pressure'],
            json.dumps(snapshot['stats'])
        ))
        
        conn.commit()
        conn.close()
        
        # Also save to file
        snapshot_file = self.data_dir / 'snapshots' / f"snapshot_{snapshot['timestamp'].replace(':', '-')}.json"
        snapshot_file.write_text(json.dumps(snapshot, indent=2))
        
        return snapshot
    
    def calculate_ecosystem_health(self) -> float:
        """Calculate overall ecosystem health."""
        if not self.entities:
            return 0.0
        
        total_fitness = 0.0
        total_health = 0.0
        total_relationships = 0
        
        for entity in self.entities.values():
            total_fitness += entity.calculate_fitness()
            total_health += entity.health
            total_relationships += sum(len(rels) for rels in entity.relationships.values())
        
        avg_fitness = total_fitness / len(self.entities)
        avg_health = total_health / len(self.entities)
        relationship_density = total_relationships / max(len(self.entities) * (len(self.entities) - 1) / 2, 1)
        
        # Composite health score
        health_score = (
            avg_fitness * 0.4 +
            avg_health * 0.3 +
            relationship_density * 0.3
        )
        
        self.ecosystem_health = health_score
        self.stats['avg_fitness'] = avg_fitness
        
        return health_score
    
    def evolve_ecosystem(self):
        """Apply evolutionary pressure to ecosystem."""
        # Calculate resource pressure
        total_metabolic_rate = sum(e.metabolic_rate for e in self.entities.values())
        self.resource_pressure = min(total_metabolic_rate / max(len(self.entities), 1), 1.0)
        
        # Apply evolutionary pressure
        for entity_id, entity in list(self.entities.items()):
            # Entities under high stress may mutate
            if entity.stress_level > 0.7 and random.random() < self.evolution_rate:
                self.mutate_entity(entity)
                self.stats['evolutionary_events'] += 1
            
            # Entities with low fitness may die
            if entity.calculate_fitness() < 0.2 and random.random() < 0.1:
                self.remove_entity(entity_id)
        
        # Calculate new ecosystem health
        self.calculate_ecosystem_health()
    
    def mutate_entity(self, entity: DigitalEntity):
        """Apply mutation to entity."""
        mutation_type = random.choice(['behavior', 'territory', 'communication', 'genetic'])
        
        if mutation_type == 'behavior':
            # Change behavior traits
            entity.aggression = max(0.0, min(1.0, entity.aggression + random.uniform(-0.2, 0.2)))
            entity.cooperation = max(0.0, min(1.0, entity.cooperation + random.uniform(-0.2, 0.2)))
            entity.curiosity = max(0.0, min(1.0, entity.curiosity + random.uniform(-0.2, 0.2)))
            entity.adaptability = max(0.0, min(1.0, entity.adaptability + random.uniform(-0.2, 0.2)))
            
        elif mutation_type == 'territory':
            # Add or remove territory
            if entity.territories and random.random() > 0.5:
                entity.territories.pop(random.randint(0, len(entity.territories) - 1))
            else:
                new_territory = random.choice(list(Territory))
                if new_territory not in entity.territories:
                    entity.territories.append(new_territory)
        
        elif mutation_type == 'communication':
            # Change communication method
            if entity.communication_methods and random.random() > 0.5:
                entity.communication_methods.pop(random.randint(0, len(entity.communication_methods) - 1))
            else:
                new_method = random.choice(list(CommunicationMethod))
                if new_method not in entity.communication_methods:
                    entity.communication_methods.append(new_method)
        
        elif mutation_type == 'genetic':
            # Mutate a random gene
            if entity.genes:
                gene = random.choice(entity.genes)
                # Add a mutation record
                mutation_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
                gene.mutations.append(f"mut_{mutation_id}")
                gene.expression_level = max(0.0, min(1.0, 
                    gene.expression_level + random.uniform(-0.3, 0.3)))
        
        # Log mutation
        entity.memory.remember({
            'type': 'mutation',
            'mutation_type': mutation_type,
            'timestamp': datetime.now().isoformat()
        }, importance=0.5)
        
        logging.info(f"Entity {entity.name} mutated: {mutation_type}")
    
    def remove_entity(self, entity_id: str):
        """Remove entity from ecosystem."""
        if entity_id in self.entities:
            entity = self.entities[entity_id]
            
            # Update statistics
            self.stats['total_entities'] -= 1
            self.stats['kingdom_distribution'][entity.kingdom.name] -= 1
            
            # Remove from indexes
            if entity.kingdom.name in self.entity_index:
                if entity_id in self.entity_index[entity.kingdom.name]:
                    self.entity_index[entity.kingdom.name].remove(entity_id)
            
            # Remove entity
            del self.entities[entity_id]
            
            # Clean up relationships
            for other_id, other_entity in self.entities.items():
                if entity_id in other_entity.relationships:
                    del other_entity.relationships[entity_id]
            
            logging.info(f"Entity {entity_id} removed from ecosystem")
    
    def generate_report(self, detailed: bool = False) -> str:
        """Generate ecosystem report."""
        report = []
        
        # Header
        report.append("=" * 80)
        report.append("DIGITAL ECOSYSTEM REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append(f"Ecosystem Health: {self.ecosystem_health:.2%}")
        report.append(f"Resource Pressure: {self.resource_pressure:.2%}")
        report.append(f"Total Entities: {len(self.entities)}")
        report.append(f"Total Interactions: {self.stats['total_interactions']}")
        report.append("")
        
        # Kingdom Distribution
        report.append("KINGDOM DISTRIBUTION")
        report.append("-" * 40)
        for kingdom, count in sorted(self.stats['kingdom_distribution'].items(),
                                   key=lambda x: x[1], reverse=True):
            percentage = count / max(len(self.entities), 1)
            report.append(f"{kingdom:25} {count:4d} ({percentage:.1%})")
        report.append("")
        
        # Entity List
        if detailed:
            report.append("ENTITY CATALOG")
            report.append("-" * 40)
            for entity_id, entity in self.entities.items():
                report.append(f"{entity_id}: {entity.name}")
                report.append(f"  Kingdom: {entity.kingdom.name}")
                report.append(f"  Species: {entity.species}")
                report.append(f"  Fitness: {entity.calculate_fitness():.2%}")
                report.append(f"  Health: {entity.health:.2%}")
                report.append(f"  Age: {entity.age()}")
                report.append("")
        
        # Relationship Matrix (simplified)
        report.append("ECOSYSTEM RELATIONSHIPS")
        report.append("-" * 40)
        relationship_counts = Counter()
        for entity in self.entities.values():
            for rel_types in entity.relationships.values():
                for rel_type in rel_types:
                    relationship_counts[rel_type] += 1
        
        for rel_type, count in relationship_counts.most_common():
            report.append(f"{rel_type:15} {count:4d}")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def visualize_ecosystem(self, output_file: Optional[Path] = None):
        """Generate visualization of ecosystem."""
        if not NETWORKX_AVAILABLE or not MATPLOTLIB_AVAILABLE:
            logging.warning("NetworkX or Matplotlib not available for visualization")
            return
        
        try:
            # Create graph
            G = nx.Graph()
            
            # Add nodes
            for entity_id, entity in self.entities.items():
                G.add_node(entity_id, 
                          kingdom=entity.kingdom.name,
                          fitness=entity.calculate_fitness(),
                          size=entity.manifest.get('size', 100))
            
            # Add edges for relationships
            for entity_id, entity in self.entities.items():
                for other_id, rel_types in entity.relationships.items():
                    if other_id in self.entities:
                        weight = len(rel_types)
                        G.add_edge(entity_id, other_id, weight=weight, 
                                  relationship=','.join(rel_types[:2]))
            
            # Create visualization
            plt.figure(figsize=(16, 12))
            
            # Node colors by kingdom
            kingdom_colors = {
                'GUI_APPLICATION': 'red',
                'CLI_UTILITY': 'blue',
                'NETWORK_SERVICE': 'green',
                'DATA_PROCESSOR': 'purple',
                'SERVICE_DAEMON': 'orange',
                'UNKNOWN': 'gray'
            }
            
            node_colors = [kingdom_colors.get(G.nodes[node]['kingdom'], 'gray') 
                          for node in G.nodes()]
            
            # Node sizes by fitness
            node_sizes = [G.nodes[node]['fitness'] * 1000 + 100 for node in G.nodes()]
            
            # Layout
            pos = nx.spring_layout(G, seed=42, k=2, iterations=50)
            
            # Draw
            nx.draw_networkx_nodes(G, pos, node_color=node_colors, 
                                  node_size=node_sizes, alpha=0.8)
            nx.draw_networkx_edges(G, pos, alpha=0.3, width=1)
            nx.draw_networkx_labels(G, pos, font_size=8)
            
            # Title
            plt.title(f"Digital Ecosystem Visualization\n"
                     f"Health: {self.ecosystem_health:.2%} | "
                     f"Entities: {len(self.entities)} | "
                     f"Relationships: {G.number_of_edges()}")
            
            # Legend
            import matplotlib.patches as mpatches
            patches = [mpatches.Patch(color=color, label=kingdom) 
                      for kingdom, color in kingdom_colors.items()]
            plt.legend(handles=patches, loc='upper left', fontsize=8)
            
            # Save or show
            if output_file:
                plt.savefig(output_file, dpi=150, bbox_inches='tight')
                logging.info(f"Visualization saved to {output_file}")
            else:
                plt.show()
            
            plt.close()
            
        except Exception as e:
            logging.error(f"Failed to create visualization: {e}")

# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Digital Biosphere: Classify scripts as intelligent entities in a digital ecosystem",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s discover script.py           # Discover and classify a script
  %(prog)s discover --batch directory/  # Discover all scripts in directory
  %(prog)s spawn entity_id              # Spawn an entity as process
  %(prog)s monitor --daemon             # Monitor ecosystem in daemon mode
  %(prog)s analyze                      # Analyze ecosystem relationships
  %(prog)s report --detailed            # Generate detailed report
  %(prog)s visualize                    # Create ecosystem visualization
  %(prog)s evolve                       # Apply evolutionary pressure
        
Storage: ~/.digital_biosphere/
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Discover command
    discover_parser = subparsers.add_parser('discover', help='Discover and classify scripts')
    discover_parser.add_argument('target', help='Script file or directory')
    discover_parser.add_argument('--batch', action='store_true', help='Batch process directory')
    discover_parser.add_argument('--recursive', '-r', action='store_true', help='Recursive directory scan')
    
    # Spawn command
    spawn_parser = subparsers.add_parser('spawn', help='Spawn an entity as running process')
    spawn_parser.add_argument('entity_id', help='Entity ID to spawn')
    spawn_parser.add_argument('--args', nargs='*', help='Command line arguments')
    
    # Monitor command
    monitor_parser = subparsers.add_parser('monitor', help='Monitor ecosystem')
    monitor_parser.add_argument('--daemon', action='store_true', help='Run in daemon mode')
    monitor_parser.add_argument('--interval', type=float, default=1.0, help='Update interval in seconds')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze ecosystem')
    analyze_parser.add_argument('--relationships', action='store_true', help='Analyze relationships')
    analyze_parser.add_argument('--health', action='store_true', help='Calculate ecosystem health')
    
    # Report command
    report_parser = subparsers.add_parser('report', help='Generate report')
    report_parser.add_argument('--detailed', action='store_true', help='Detailed entity listing')
    report_parser.add_argument('--output', '-o', help='Output file')
    
    # Visualize command
    viz_parser = subparsers.add_parser('visualize', help='Visualize ecosystem')
    viz_parser.add_argument('--output', '-o', help='Output image file')
    
    # Evolve command
    evolve_parser = subparsers.add_parser('evolve', help='Evolve ecosystem')
    evolve_parser.add_argument('--generations', type=int, default=1, help='Number of generations to evolve')
    
    # System command
    system_parser = subparsers.add_parser('system', help='System operations')
    system_parser.add_argument('--snapshot', action='store_true', help='Take ecosystem snapshot')
    system_parser.add_argument('--clean', action='store_true', help='Clean old data')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize ecosystem
    ecosystem = DigitalEcosystem()
    
    try:
        if args.command == 'discover':
            target_path = Path(args.target)
            
            if target_path.is_dir() and args.batch:
                # Batch discovery
                pattern = '**/*.py' if args.recursive else '*.py'
                python_files = list(target_path.glob(pattern))
                
                logging.info(f"Found {len(python_files)} Python files")
                
                for i, py_file in enumerate(python_files, 1):
                    try:
                        logging.info(f"Discovering [{i}/{len(python_files)}]: {py_file}")
                        entity = ecosystem.discover_entity(py_file)
                        if entity:
                            print(f"Discovered: {entity.name} ({entity.entity_id}) - {entity.kingdom.name}")
                    except Exception as e:
                        logging.error(f"Error discovering {py_file}: {e}")
                
                print(f"\nDiscovery complete. Found {len(python_files)} scripts.")
                
            else:
                # Single file discovery
                entity = ecosystem.discover_entity(target_path)
                if entity:
                    print(f"Discovered entity: {entity.entity_id}")
                    print(f"Name: {entity.name}")
                    print(f"Kingdom: {entity.kingdom.name}")
                    print(f"Species: {entity.species}")
                    print(f"Territories: {[t.name for t in entity.territories]}")
                    print(f"Consciousness: {entity.consciousness.name}")
                    print(f"Fitness: {entity.calculate_fitness():.2%}")
        
        elif args.command == 'spawn':
            if args.entity_id in ecosystem.entities:
                entity = ecosystem.entities[args.entity_id]
                cmdline = [sys.executable, entity.manifest['path']]
                if args.args:
                    cmdline.extend(args.args)
                
                pid = ecosystem.spawn_entity(entity, cmdline)
                if pid:
                    print(f"Spawned entity {entity.name} as PID {pid}")
                    print(f"Command: {' '.join(cmdline)}")
                else:
                    print(f"Failed to spawn entity {entity.name}")
            else:
                print(f"Entity {args.entity_id} not found")
        
        elif args.command == 'monitor':
            if args.daemon:
                ecosystem.monitor.daemon_mode = True
                ecosystem.monitor.update_interval = args.interval
                ecosystem.monitor.start()
                
                print(f"Monitoring started in daemon mode (interval: {args.interval}s)")
                print("Press Ctrl+C to stop")
                
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    ecosystem.monitor.stop()
                    print("\nMonitoring stopped")
            else:
                # Single scan
                ecosystem.monitor.scan_processes()
                print(f"Found {ecosystem.monitor.stats['total_processes']} processes")
                print(f"Active entities: {ecosystem.monitor.stats['active_entities']}")
        
        elif args.command == 'analyze':
            if args.relationships:
                print("Analyzing entity relationships...")
                ecosystem.analyze_relationships()
                print(f"Analyzed {ecosystem.stats['total_interactions']} interactions")
            
            if args.health:
                health = ecosystem.calculate_ecosystem_health()
                print(f"Ecosystem Health: {health:.2%}")
                print(f"Resource Pressure: {ecosystem.resource_pressure:.2%}")
                print(f"Average Fitness: {ecosystem.stats['avg_fitness']:.2%}")
        
        elif args.command == 'report':
            report = ecosystem.generate_report(detailed=args.detailed)
            
            if args.output:
                output_path = Path(args.output)
                output_path.write_text(report)
                print(f"Report saved to {output_path}")
            else:
                print(report)
        
        elif args.command == 'visualize':
            output_file = Path(args.output) if args.output else None
            ecosystem.visualize_ecosystem(output_file)
            if output_file:
                print(f"Visualization saved to {output_file}")
            else:
                print("Visualization displayed")
        
        elif args.command == 'evolve':
            for gen in range(args.generations):
                print(f"Evolving generation {gen + 1}/{args.generations}...")
                ecosystem.evolve_ecosystem()
                health = ecosystem.calculate_ecosystem_health()
                print(f"  Health: {health:.2%}, Entities: {len(ecosystem.entities)}")
            
            print(f"Evolution complete. Evolutionary events: {ecosystem.stats['evolutionary_events']}")
        
        elif args.command == 'system':
            if args.snapshot:
                snapshot = ecosystem.take_snapshot()
                print(f"Snapshot taken: {snapshot['timestamp']}")
                print(f"Entities: {snapshot['total_entities']}")
                print(f"Health: {snapshot['ecosystem_health']:.2%}")
            
            if args.clean:
                # Clean old snapshots (keep last 100)
                snapshots_dir = ecosystem.data_dir / 'snapshots'
                if snapshots_dir.exists():
                    snapshots = sorted(snapshots_dir.glob('*.json'))
                    if len(snapshots) > 100:
                        for old_snapshot in snapshots[:-100]:
                            old_snapshot.unlink()
                        print(f"Cleaned {len(snapshots) - 100} old snapshots")
    
    except Exception as e:
        logging.error(f"Command failed: {e}")
        traceback.print_exc()
        sys.exit(1)

# ============================================================================
# SELF-CATALOGING
# ============================================================================

def catalog_self():
    """Catalog this script itself."""
    try:
        self_path = Path(__file__).resolve()
        ecosystem = DigitalEcosystem()
        
        print(f"Self-cataloging: {self_path.name}")
        print("=" * 60)
        
        entity = ecosystem.discover_entity(self_path)
        if entity:
            # Enhance with self-awareness
            entity.consciousness = ConsciousnessLevel.SELF_AWARE
            entity.memory.remember({
                'type': 'self_cataloging',
                'timestamp': datetime.now().isoformat(),
                'purpose': 'ecosystem management'
            }, importance=1.0)
            
            # Save enhanced entity
            ecosystem.save_entity(entity)
            
            print(f"Entity ID: {entity.entity_id}")
            print(f"Kingdom: {entity.kingdom.name}")
            print(f"Territories: {[t.name for t in entity.territories]}")
            print(f"Consciousness: {entity.consciousness.name}")
            print(f"Genetic Hash: {entity.hash_dna}")
            print(f"Genes: {len(entity.genes)} computational genes")
            print("\nSelf-cataloging complete.")
            
            # Save to special catalog
            self_catalog = {
                'script_name': self_path.name,
                'entity_id': entity.entity_id,
                'self_hash': entity.hash_dna,
                'catalog_time': datetime.now().isoformat(),
                'purpose': 'Digital Biosphere Ecosystem Manager',
                'capabilities': [
                    'Taxonomic classification',
                    'Process monitoring',
                    'Ecosystem management',
                    'Relationship analysis',
                    'Evolutionary simulation'
                ]
            }
            
            catalog_path = ecosystem.data_dir / 'catalogs' / 'self_catalog.json'
            catalog_path.write_text(json.dumps(self_catalog, indent=2))
            print(f"Self-catalog saved to: {catalog_path}")
        
    except Exception as e:
        print(f"Self-cataloging failed: {e}")

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    # Check for first run
    data_dir = Path.home() / '.digital_biosphere'
    first_run = not (data_dir / 'catalogs' / 'self_catalog.json').exists()
    
    if first_run:
        print("\n" + "=" * 60)
        print("DIGITAL BIOSPHERE - FIRST RUN")
        print("=" * 60)
        print("Initializing digital ecosystem...")
        print(f"Data directory: {data_dir}")
        
        # Self-catalog
        catalog_self()
        
        print("\nSetup complete. You can now:")
        print("  python digital_biosphere.py discover script.py")
        print("  python digital_biosphere.py monitor --daemon")
        print("  python digital_biosphere.py report")
        print("=" * 60 + "\n")
    
    # Run CLI
    main()