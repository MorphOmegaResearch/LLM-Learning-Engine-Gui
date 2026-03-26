#!/usr/bin/env python3
"""
Adaptive Tool Onboarder with Multi-Option Configuration System
==============================================================
Non-invasive, configurable onboarding with multiple setup paths,
optional integrations, and adaptive workflow selection.
"""

import os
import sys
import json
import argparse
import subprocess
import shutil
import hashlib
import datetime
import tempfile
import threading
import re
import inspect
import textwrap
import webbrowser
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional, Union, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import ast
import yaml

# #[EVENT] Setup adaptive logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(
            f"/tmp/adaptive_onboarder_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# CORE DATA STRUCTURES
# =============================================================================

class SetupMode(Enum):
    """Different setup modes available."""
    MINIMAL = "minimal"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"
    CUSTOM = "custom"
    PORTABLE = "portable"
    ENTERPRISE = "enterprise"


class IntegrationLevel(Enum):
    """Level of integration with existing tools."""
    NONE = "none"
    LIGHT = "light"
    MODERATE = "moderate"
    DEEP = "deep"
    FULL = "full"


class ToolDiscoveryMethod(Enum):
    """Methods for discovering tools."""
    AUTO = "auto"
    MANUAL = "manual"
    PATTERN = "pattern"
    RECURSIVE = "recursive"
    INDEXED = "indexed"
    HYBRID = "hybrid"


class ConfigurationStyle(Enum):
    """Configuration style preferences."""
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    INI = "ini"
    ENV = "env"
    MIXED = "mixed"


@dataclass
class SetupOption:
    """A single setup option with dependencies and conditions."""
    id: str
    name: str
    description: str
    category: str
    enabled_by_default: bool = True
    requires: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    validation_rules: List[Dict[str, Any]] = field(default_factory=list)
    config_template: Optional[Dict[str, Any]] = None
    weight: float = 1.0  # Importance weight (0.0-1.0)
    complexity: str = "low"  # low, medium, high
    estimated_time: int = 5  # minutes
    tags: List[str] = field(default_factory=list)


@dataclass
class SetupProfile:
    """A complete setup profile with multiple options."""
    name: str
    description: str
    mode: SetupMode
    options: Dict[str, bool]  # option_id -> enabled
    integration_level: IntegrationLevel
    discovery_method: ToolDiscoveryMethod
    config_style: ConfigurationStyle
    variables: Dict[str, Any] = field(default_factory=dict)
    constraints: List[Dict[str, Any]] = field(default_factory=list)
    validation_checks: List[Dict[str, Any]] = field(default_factory=list)
    post_setup_actions: List[str] = field(default_factory=list)


@dataclass
class SetupEnvironment:
    """Current environment for setup."""
    base_dir: Path
    temp_dir: Path
    config_dir: Path
    tools_dir: Path
    backups_dir: Path
    logs_dir: Path
    profiles_dir: Path
    detected_os: str
    python_version: str
    available_memory: int
    disk_space: int
    user_id: int
    permissions: Dict[str, bool]
    constraints: Dict[str, Any]


# =============================================================================
# SETUP OPTIONS REGISTRY
# =============================================================================

class SetupOptionsRegistry:
    """Registry of all available setup options."""
    
    def __init__(self):
        self.options: Dict[str, SetupOption] = {}
        self.categories: Dict[str, List[str]] = {}
        self._register_default_options()
    
    def _register_default_options(self):
        """Register all default setup options."""
        
        # Core Setup Options
        self.register(SetupOption(
            id="core_directory_structure",
            name="Core Directory Structure",
            description="Create standard directory structure for tools and configurations",
            category="infrastructure",
            enabled_by_default=True,
            weight=1.0,
            complexity="low",
            estimated_time=2,
            config_template={
                "directories": {
                    "tools": "org_tools",
                    "configs": ".config",
                    "backups": "backups",
                    "logs": "logs",
                    "profiles": "profiles",
                    "cache": ".cache"
                }
            },
            tags=["essential", "infrastructure", "filesystem"]
        ))
        
        self.register(SetupOption(
            id="tool_discovery_auto",
            name="Automatic Tool Discovery",
            description="Automatically discover Python tools in directory",
            category="discovery",
            enabled_by_default=True,
            weight=0.9,
            complexity="medium",
            estimated_time=3,
            config_template={
                "discovery": {
                    "methods": ["auto", "recursive"],
                    "depth": 3,
                    "patterns": ["*.py", "tool_*.py", "*_tool.py"],
                    "exclude": ["__pycache__", ".git", "test_*"]
                }
            },
            tags=["discovery", "automation", "tools"]
        ))
        
        self.register(SetupOption(
            id="metadata_extraction",
            name="Tool Metadata Extraction",
            description="Extract metadata from discovered tools (argparse, imports, etc.)",
            category="analysis",
            enabled_by_default=True,
            weight=0.8,
            complexity="medium",
            estimated_time=5,
            config_template={
                "metadata": {
                    "extract_argparse": True,
                    "extract_imports": True,
                    "extract_functions": True,
                    "extract_docstrings": True,
                    "extract_dependencies": True
                }
            },
            tags=["analysis", "metadata", "extraction"]
        ))
        
        # Integration Options
        self.register(SetupOption(
            id="integrate_pathfixer",
            name="PathFixer Integration",
            description="Integrate with PathFixer for path consolidation",
            category="integration",
            enabled_by_default=False,
            requires=["core_directory_structure"],
            weight=0.7,
            complexity="high",
            estimated_time=8,
            config_template={
                "pathfixer": {
                    "enabled": True,
                    "auto_detect": True,
                    "scan_on_discovery": True,
                    "create_snapshots": True,
                    "fix_level": "moderate"
                }
            },
            tags=["integration", "pathfixer", "consolidation"]
        ))
        
        self.register(SetupOption(
            id="integrate_analyzer",
            name="Analyzer Integration",
            description="Integrate with Code Analyzer for efficiency scoring",
            category="integration",
            enabled_by_default=False,
            weight=0.6,
            complexity="medium",
            estimated_time=6,
            config_template={
                "analyzer": {
                    "enabled": True,
                    "score_tools": True,
                    "suggest_optimizations": True,
                    "generate_reports": True
                }
            },
            tags=["integration", "analyzer", "optimization"]
        ))
        
        self.register(SetupOption(
            id="integrate_organizer",
            name="Organizer Integration",
            description="Integrate with Project Organizer for workflow management",
            category="integration",
            enabled_by_default=False,
            weight=0.5,
            complexity="medium",
            estimated_time=7,
            config_template={
                "organizer": {
                    "enabled": True,
                    "manage_workflows": True,
                    "session_tracking": True,
                    "generate_checklists": True
                }
            },
            tags=["integration", "organizer", "workflow"]
        ))
        
        # UI/UX Options
        self.register(SetupOption(
            id="gui_interface",
            name="GUI Interface",
            description="Enable graphical user interface with treeview",
            category="interface",
            enabled_by_default=True,
            weight=0.8,
            complexity="medium",
            estimated_time=5,
            config_template={
                "gui": {
                    "enabled": True,
                    "theme": "default",
                    "treeview": True,
                    "context_menu": True,
                    "shortcuts": True
                }
            },
            tags=["interface", "gui", "treeview"]
        ))
        
        self.register(SetupOption(
            id="cli_interface",
            name="CLI Interface",
            description="Enable command-line interface with rich features",
            category="interface",
            enabled_by_default=True,
            weight=0.9,
            complexity="low",
            estimated_time=3,
            config_template={
                "cli": {
                    "enabled": True,
                    "rich_output": True,
                    "auto_complete": True,
                    "help_system": True,
                    "color_scheme": "auto"
                }
            },
            tags=["interface", "cli", "command-line"]
        ))
        
        self.register(SetupOption(
            id="web_interface",
            name="Web Interface",
            description="Enable web-based interface (requires Flask/Django)",
            category="interface",
            enabled_by_default=False,
            weight=0.4,
            complexity="high",
            estimated_time=15,
            dependencies=["flask"],
            config_template={
                "web": {
                    "enabled": False,
                    "port": 8080,
                    "host": "localhost",
                    "auth_required": False
                }
            },
            tags=["interface", "web", "browser"]
        ))
        
        # Advanced Features
        self.register(SetupOption(
            id="tool_chaining",
            name="Tool Chaining",
            description="Enable chaining multiple tools together in workflows",
            category="advanced",
            enabled_by_default=False,
            weight=0.6,
            complexity="high",
            estimated_time=10,
            config_template={
                "chaining": {
                    "enabled": True,
                    "max_chain_length": 5,
                    "output_piping": True,
                    "error_handling": "continue",
                    "parallel_execution": True
                }
            },
            tags=["advanced", "workflow", "automation"]
        ))
        
        self.register(SetupOption(
            id="ai_suggestions",
            name="AI-Powered Suggestions",
            description="Use AI to suggest tool configurations and optimizations",
            category="advanced",
            enabled_by_default=False,
            weight=0.3,
            complexity="very_high",
            estimated_time=12,
            dependencies=["openai"],
            config_template={
                "ai": {
                    "enabled": False,
                    "provider": "openai",
                    "model": "gpt-3.5-turbo",
                    "suggest_configs": True,
                    "optimize_workflows": True
                }
            },
            tags=["advanced", "ai", "ml", "suggestions"]
        ))
        
        self.register(SetupOption(
            id="version_control",
            name="Version Control Integration",
            description="Integrate with Git for configuration versioning",
            category="advanced",
            enabled_by_default=False,
            weight=0.5,
            complexity="medium",
            estimated_time=8,
            config_template={
                "version_control": {
                    "enabled": True,
                    "auto_commit": False,
                    "branch_strategy": "feature",
                    "remote_backup": False
                }
            },
            tags=["advanced", "git", "version", "backup"]
        ))
        
        # Performance Options
        self.register(SetupOption(
            id="caching_system",
            name="Caching System",
            description="Enable disk and memory caching for faster operations",
            category="performance",
            enabled_by_default=True,
            weight=0.7,
            complexity="medium",
            estimated_time=4,
            config_template={
                "caching": {
                    "enabled": True,
                    "disk_cache": True,
                    "memory_cache": True,
                    "cache_ttl": 3600,
                    "max_cache_size": 100
                }
            },
            tags=["performance", "caching", "speed"]
        ))
        
        self.register(SetupOption(
            id="parallel_processing",
            name="Parallel Processing",
            description="Enable parallel tool discovery and processing",
            category="performance",
            enabled_by_default=False,
            weight=0.6,
            complexity="high",
            estimated_time=7,
            config_template={
                "parallel": {
                    "enabled": True,
                    "max_workers": 4,
                    "process_pool": True,
                    "thread_pool": True
                }
            },
            tags=["performance", "parallel", "multiprocessing"]
        ))
        
        # Security Options
        self.register(SetupOption(
            id="encryption",
            name="Configuration Encryption",
            description="Encrypt sensitive configuration data",
            category="security",
            enabled_by_default=False,
            weight=0.4,
            complexity="high",
            estimated_time=6,
            config_template={
                "encryption": {
                    "enabled": False,
                    "algorithm": "AES",
                    "key_storage": "file",
                    "encrypt_sensitive": True
                }
            },
            tags=["security", "encryption", "privacy"]
        ))
        
        self.register(SetupOption(
            id="audit_logging",
            name="Audit Logging",
            description="Comprehensive audit logging for all operations",
            category="security",
            enabled_by_default=False,
            weight=0.3,
            complexity="medium",
            estimated_time=5,
            config_template={
                "audit": {
                    "enabled": True,
                    "log_all_operations": True,
                    "retention_days": 30,
                    "alert_on_anomalies": False
                }
            },
            tags=["security", "audit", "logging"]
        ))
        
        # Export/Import Options
        self.register(SetupOption(
            id="export_profiles",
            name="Export/Import Profiles",
            description="Export and import setup profiles for sharing",
            category="portability",
            enabled_by_default=True,
            weight=0.8,
            complexity="low",
            estimated_time=3,
            config_template={
                "profiles": {
                    "export_enabled": True,
                    "import_enabled": True,
                    "format": "json",
                    "include_configs": True
                }
            },
            tags=["portability", "export", "import", "profiles"]
        ))
        
        self.register(SetupOption(
            id="docker_support",
            name="Docker Containerization",
            description="Generate Dockerfiles for portable deployment",
            category="portability",
            enabled_by_default=False,
            weight=0.5,
            complexity="high",
            estimated_time=15,
            dependencies=["docker"],
            config_template={
                "docker": {
                    "enabled": False,
                    "generate_dockerfile": True,
                    "generate_compose": True,
                    "base_image": "python:3.9-slim"
                }
            },
            tags=["portability", "docker", "container"]
        ))
    
    def register(self, option: SetupOption):
        """Register a setup option."""
        self.options[option.id] = option
        
        # Update categories
        if option.category not in self.categories:
            self.categories[option.category] = []
        self.categories[option.category].append(option.id)
    
    def get_option(self, option_id: str) -> Optional[SetupOption]:
        """Get an option by ID."""
        return self.options.get(option_id)
    
    def get_options_by_category(self, category: str) -> List[SetupOption]:
        """Get all options in a category."""
        option_ids = self.categories.get(category, [])
        return [self.options[oid] for oid in option_ids]
    
    def validate_selection(self, selected: Dict[str, bool]) -> Tuple[bool, List[str], List[str]]:
        """Validate a selection of options."""
        errors = []
        warnings = []
        
        # Check requirements
        for option_id, enabled in selected.items():
            if enabled and option_id in self.options:
                option = self.options[option_id]
                
                # Check requirements
                for req in option.requires:
                    if req not in selected or not selected[req]:
                        errors.append(f"Option '{option.name}' requires '{self.options[req].name}'")
                
                # Check conflicts
                for conflict in option.conflicts:
                    if conflict in selected and selected[conflict]:
                        errors.append(f"Option '{option.name}' conflicts with '{self.options[conflict].name}'")
        
        # Check dependencies
        for option_id, enabled in selected.items():
            if enabled and option_id in self.options:
                option = self.options[option_id]
                for dep in option.dependencies:
                    warnings.append(f"Option '{option.name}' may require external dependency: {dep}")
        
        return len(errors) == 0, errors, warnings
    
    def generate_profile(self, name: str, description: str, mode: SetupMode,
                        selected: Dict[str, bool]) -> SetupProfile:
        """Generate a setup profile from selected options."""
        # Determine integration level based on selected integration options
        integration_options = [
            opt for opt_id, enabled in selected.items() 
            if enabled and opt_id in self.options and 
            self.options[opt_id].category == "integration"
        ]
        
        if len(integration_options) >= 3:
            integration_level = IntegrationLevel.FULL
        elif len(integration_options) >= 2:
            integration_level = IntegrationLevel.DEEP
        elif len(integration_options) >= 1:
            integration_level = IntegrationLevel.MODERATE
        else:
            integration_level = IntegrationLevel.LIGHT
        
        # Determine discovery method
        if selected.get("tool_discovery_auto", False):
            discovery_method = ToolDiscoveryMethod.AUTO
        else:
            discovery_method = ToolDiscoveryMethod.MANUAL
        
        # Determine config style (default to JSON)
        config_style = ConfigurationStyle.JSON
        
        return SetupProfile(
            name=name,
            description=description,
            mode=mode,
            options=selected,
            integration_level=integration_level,
            discovery_method=discovery_method,
            config_style=config_style
        )


# =============================================================================
# ENVIRONMENT DETECTION
# =============================================================================

class EnvironmentDetector:
    """Detects and analyzes the setup environment."""
    
    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or Path.cwd()
        self.detected_tools = {}
        self.system_info = {}
        self.constraints = {}
        
    def detect_all(self) -> SetupEnvironment:
        """Detect all environment aspects."""
        logger.info("[EVENT] Starting environment detection")
        
        # Detect OS
        os_info = self._detect_os()
        
        # Detect Python environment
        python_info = self._detect_python()
        
        # Detect system resources
        resources = self._detect_resources()
        
        # Detect existing tools
        tools = self._detect_existing_tools()
        
        # Detect permissions
        permissions = self._detect_permissions()
        
        # Create environment
        temp_dir = Path(tempfile.gettempdir()) / f"onboarder_{hashlib.md5(str(self.base_dir).encode()).hexdigest()[:8]}"
        temp_dir.mkdir(exist_ok=True)
        
        env = SetupEnvironment(
            base_dir=self.base_dir,
            temp_dir=temp_dir,
            config_dir=self.base_dir / ".config",
            tools_dir=self.base_dir / "org_tools",
            backups_dir=self.base_dir / "backups",
            logs_dir=self.base_dir / "logs",
            profiles_dir=self.base_dir / "profiles",
            detected_os=os_info["name"],
            python_version=python_info["version"],
            available_memory=resources["memory"],
            disk_space=resources["disk"],
            user_id=os.getuid() if hasattr(os, "getuid") else 0,
            permissions=permissions,
            constraints=self.constraints
        )
        
        logger.info(f"[EVENT] Environment detected: OS={os_info['name']}, Python={python_info['version']}")
        return env
    
    def _detect_os(self) -> Dict[str, Any]:
        """Detect operating system."""
        import platform
        
        os_name = platform.system()
        os_version = platform.version()
        os_release = platform.release()
        
        # Check for specific constraints
        if os_name == "Windows":
            self.constraints["path_separator"] = "\\"
            self.constraints["case_sensitive"] = False
        else:
            self.constraints["path_separator"] = "/"
            self.constraints["case_sensitive"] = True
        
        return {
            "name": os_name,
            "version": os_version,
            "release": os_release,
            "full": platform.platform()
        }
    
    def _detect_python(self) -> Dict[str, Any]:
        """Detect Python environment."""
        import platform
        
        version = platform.python_version()
        implementation = platform.python_implementation()
        compiler = platform.python_compiler()
        
        # Check for required modules
        required_modules = ["argparse", "json", "pathlib", "tkinter", "subprocess"]
        available_modules = []
        missing_modules = []
        
        for module in required_modules:
            try:
                __import__(module)
                available_modules.append(module)
            except ImportError:
                missing_modules.append(module)
        
        if missing_modules:
            self.constraints["missing_modules"] = missing_modules
            logger.warning(f"[EVENT] Missing modules: {missing_modules}")
        
        # Check Python version compatibility
        version_tuple = tuple(map(int, version.split('.')))
        if version_tuple < (3, 7):
            self.constraints["python_version"] = "incompatible"
            logger.warning(f"[EVENT] Python version {version} may be incompatible")
        
        return {
            "version": version,
            "implementation": implementation,
            "compiler": compiler,
            "available_modules": available_modules,
            "missing_modules": missing_modules
        }
    
    def _detect_resources(self) -> Dict[str, Any]:
        """Detect system resources."""
        import psutil
        
        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage(self.base_dir)
            
            return {
                "memory": memory.available,
                "memory_total": memory.total,
                "memory_percent": memory.percent,
                "disk": disk.free,
                "disk_total": disk.total,
                "disk_percent": disk.percent
            }
        except ImportError:
            # psutil not available, use fallback
            logger.warning("[EVENT] psutil not available, using resource fallback")
            return {
                "memory": 1024 * 1024 * 1024,  # 1GB fallback
                "memory_total": 1024 * 1024 * 1024 * 8,  # 8GB fallback
                "memory_percent": 50,
                "disk": 1024 * 1024 * 1024 * 10,  # 10GB fallback
                "disk_total": 1024 * 1024 * 1024 * 100,  # 100GB fallback
                "disk_percent": 50
            }
    
    def _detect_existing_tools(self) -> Dict[str, Dict[str, Any]]:
        """Detect existing analysis tools in directory."""
        tools = {}
        
        # Look for known tools
        known_tools = {
            "pathfixer.py": "PathFixer",
            "analyzer.py": "CodeAnalyzer",
            "organizer.py": "ProjectOrganizer",
            "import_organizer.py": "ImportOrganizer",
            "onboarder.py": "Onboarder"
        }
        
        for filename, tool_name in known_tools.items():
            tool_path = self.base_dir / filename
            if tool_path.exists():
                try:
                    # Try to get version/description
                    with open(tool_path, 'r') as f:
                        content = f.read(2000)  # Read first 2000 chars
                    
                    # Extract version
                    version_match = re.search(r'version\s*[=:]\s*["\']([^"\']+)["\']', content, re.IGNORECASE)
                    version = version_match.group(1) if version_match else "1.0.0"
                    
                    # Extract description
                    desc_match = re.search(r'["\']{3}(.*?)["\']{3}', content, re.DOTALL)
                    description = desc_match.group(1).split('\n')[0] if desc_match else f"{tool_name} tool"
                    
                    tools[filename] = {
                        "name": tool_name,
                        "path": str(tool_path),
                        "version": version,
                        "description": description[:100],
                        "size": tool_path.stat().st_size,
                        "modified": datetime.datetime.fromtimestamp(tool_path.stat().st_mtime).isoformat()
                    }
                except Exception as e:
                    logger.error(f"[EVENT] Failed to analyze {filename}: {e}")
        
        self.detected_tools = tools
        return tools
    
    def _detect_permissions(self) -> Dict[str, bool]:
        """Detect file system permissions."""
        permissions = {}
        
        test_paths = [
            self.base_dir,
            self.base_dir / "test_write.txt",
            Path.home() / ".config",
            Path("/tmp") if self.constraints.get("path_separator") == "/" else Path("C:\\Windows\\Temp")
        ]
        
        for path in test_paths:
            key = f"write_{path.name}" if path.name else f"write_{path.parent.name}"
            try:
                if path.is_dir():
                    # Test directory write
                    test_file = path / f".permission_test_{os.getpid()}.tmp"
                    try:
                        test_file.write_text("test")
                        test_file.unlink()
                        permissions[key] = True
                    except:
                        permissions[key] = False
                else:
                    # Test file write (create if doesn't exist)
                    if not path.exists():
                        try:
                            path.write_text("test")
                            path.unlink()
                            permissions[key] = True
                        except:
                            permissions[key] = False
            except:
                permissions[key] = False
        
        return permissions


# =============================================================================
# ADAPTIVE SETUP ENGINE
# =============================================================================

class AdaptiveSetupEngine:
    """Main engine for adaptive setup."""
    
    def __init__(self, env: SetupEnvironment, registry: SetupOptionsRegistry):
        self.env = env
        self.registry = registry
        self.selected_options: Dict[str, bool] = {}
        self.current_profile: Optional[SetupProfile] = None
        self.setup_steps: List[Dict[str, Any]] = []
        
    def suggest_options(self) -> Dict[str, float]:
        """Suggest options based on environment analysis."""
        suggestions = {}
        
        # Always suggest core infrastructure
        for opt_id in ["core_directory_structure", "tool_discovery_auto", "cli_interface"]:
            suggestions[opt_id] = 1.0
        
        # Suggest based on detected tools
        if self.env.constraints.get("detected_tools", {}):
            if "pathfixer.py" in self.env.constraints.get("detected_tools", {}):
                suggestions["integrate_pathfixer"] = 0.9
            if "analyzer.py" in self.env.constraints.get("detected_tools", {}):
                suggestions["integrate_analyzer"] = 0.8
            if "organizer.py" in self.env.constraints.get("detected_tools", {}):
                suggestions["integrate_organizer"] = 0.8
        
        # Suggest based on resources
        if self.env.available_memory > 2 * 1024 * 1024 * 1024:  # > 2GB
            suggestions["parallel_processing"] = 0.7
            suggestions["caching_system"] = 0.9
        
        # Suggest based on Python version
        if tuple(map(int, self.env.python_version.split('.'))) >= (3, 8):
            suggestions["metadata_extraction"] = 0.9
        
        # Suggest GUI if tkinter is available
        try:
            import tkinter
            suggestions["gui_interface"] = 0.8
        except ImportError:
            pass
        
        # Penalize complex options for low resources
        if self.env.available_memory < 512 * 1024 * 1024:  # < 512MB
            for opt_id, option in self.registry.options.items():
                if option.complexity == "high" or option.complexity == "very_high":
                    suggestions[opt_id] = suggestions.get(opt_id, 0.5) * 0.5
        
        return suggestions
    
    def generate_setup_plan(self, profile: SetupProfile) -> Dict[str, Any]:
        """Generate a detailed setup plan from profile."""
        plan = {
            "profile": asdict(profile),
            "environment": {
                "base_dir": str(self.env.base_dir),
                "os": self.env.detected_os,
                "python_version": self.env.python_version
            },
            "phases": [],
            "estimated_time": 0,
            "complexity": "low",
            "validation_steps": [],
            "rollback_steps": []
        }
        
        phases = [
            {"id": "preparation", "name": "Preparation", "steps": []},
            {"id": "infrastructure", "name": "Infrastructure", "steps": []},
            {"id": "core_setup", "name": "Core Setup", "steps": []},
            {"id": "integration", "name": "Integration", "steps": []},
            {"id": "advanced", "name": "Advanced Features", "steps": []},
            {"id": "validation", "name": "Validation", "steps": []},
            {"id": "finalization", "name": "Finalization", "steps": []},
        ]
        
        total_time = 0
        max_complexity = "low"
        
        # Map options to phases
        for opt_id, enabled in profile.options.items():
            if not enabled:
                continue
            
            option = self.registry.get_option(opt_id)
            if not option:
                continue
            
            total_time += option.estimated_time
            
            # Update complexity
            complexity_map = {"low": 1, "medium": 2, "high": 3, "very_high": 4}
            if complexity_map.get(option.complexity, 0) > complexity_map.get(max_complexity, 0):
                max_complexity = option.complexity
            
            # Determine phase
            phase_id = "core_setup"  # default
            if option.category == "infrastructure":
                phase_id = "infrastructure"
            elif option.category == "integration":
                phase_id = "integration"
            elif option.category == "advanced":
                phase_id = "advanced"
            elif option.category in ["security", "performance"]:
                phase_id = "advanced"
            
            # Find phase
            phase = next((p for p in phases if p["id"] == phase_id), phases[2])
            
            # Add step
            step = {
                "option_id": opt_id,
                "name": option.name,
                "description": option.description,
                "estimated_time": option.estimated_time,
                "complexity": option.complexity,
                "dependencies": option.dependencies,
                "validation": option.validation_rules
            }
            
            phase["steps"].append(step)
        
        # Remove empty phases
        phases = [p for p in phases if p["steps"]]
        
        # Add validation steps
        validation_steps = [
            {"id": "check_directories", "name": "Check directory creation", "description": "Verify all directories were created"},
            {"id": "check_configs", "name": "Check configuration files", "description": "Verify configuration files are valid"},
            {"id": "check_tools", "name": "Check tool discovery", "description": "Verify tools were discovered correctly"},
            {"id": "test_interfaces", "name": "Test interfaces", "description": "Test CLI and GUI interfaces"}
        ]
        
        # Add rollback steps
        rollback_steps = [
            {"id": "backup_configs", "name": "Backup configurations", "description": "Create backup of all configuration files"},
            {"id": "remove_directories", "name": "Remove created directories", "description": "Remove directories if setup fails"},
            {"id": "restore_originals", "name": "Restore original files", "description": "Restore any modified original files"}
        ]
        
        plan["phases"] = phases
        plan["estimated_time"] = total_time
        plan["complexity"] = max_complexity
        plan["validation_steps"] = validation_steps
        plan["rollback_steps"] = rollback_steps
        
        return plan
    
    def execute_setup(self, profile: SetupProfile, dry_run: bool = False) -> Dict[str, Any]:
        """Execute the setup based on profile."""
        results = {
            "success": False,
            "steps_completed": 0,
            "steps_failed": 0,
            "total_steps": 0,
            "details": [],
            "warnings": [],
            "errors": [],
            "generated_files": [],
            "setup_time": 0
        }
        
        start_time = datetime.datetime.now()
        
        try:
            # Generate plan
            plan = self.generate_setup_plan(profile)
            results["total_steps"] = sum(len(phase["steps"]) for phase in plan["phases"])
            
            # Create base directories
            if not dry_run:
                self._create_base_directories()
            
            # Execute each phase
            for phase in plan["phases"]:
                phase_result = self._execute_phase(phase, dry_run)
                results["details"].append(phase_result)
                
                if phase_result["success"]:
                    results["steps_completed"] += phase_result["steps_completed"]
                else:
                    results["steps_failed"] += phase_result["steps_failed"]
                    results["errors"].extend(phase_result["errors"])
            
            # Generate configuration
            if not dry_run:
                config_result = self._generate_configuration(profile)
                results["generated_files"].extend(config_result["files"])
                if not config_result["success"]:
                    results["errors"].extend(config_result["errors"])
            
            # Validate setup
            if not dry_run:
                validation_result = self._validate_setup(profile)
                results["warnings"].extend(validation_result["warnings"])
                if not validation_result["success"]:
                    results["errors"].extend(validation_result["errors"])
            
            results["success"] = results["steps_failed"] == 0 and len(results["errors"]) == 0
            
        except Exception as e:
            results["errors"].append(f"Setup execution failed: {str(e)}")
            results["success"] = False
        
        end_time = datetime.datetime.now()
        results["setup_time"] = (end_time - start_time).total_seconds()
        
        return results
    
    def _create_base_directories(self):
        """Create base directory structure."""
        directories = [
            self.env.tools_dir,
            self.env.config_dir,
            self.env.backups_dir,
            self.env.logs_dir,
            self.env.profiles_dir
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"[EVENT] Created directory: {directory}")
    
    def _execute_phase(self, phase: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
        """Execute a single phase."""
        phase_result = {
            "phase": phase["id"],
            "name": phase["name"],
            "steps_completed": 0,
            "steps_failed": 0,
            "success": True,
            "errors": []
        }
        
        for step in phase["steps"]:
            try:
                if dry_run:
                    logger.info(f"[DRY RUN] Would execute: {step['name']}")
                    phase_result["steps_completed"] += 1
                else:
                    # Execute the step based on option ID
                    success = self._execute_option_step(step["option_id"])
                    if success:
                        phase_result["steps_completed"] += 1
                    else:
                        phase_result["steps_failed"] += 1
                        phase_result["errors"].append(f"Failed: {step['name']}")
                        phase_result["success"] = False
            except Exception as e:
                phase_result["steps_failed"] += 1
                phase_result["errors"].append(f"Error in {step['name']}: {str(e)}")
                phase_result["success"] = False
        
        return phase_result
    
    def _execute_option_step(self, option_id: str) -> bool:
        """Execute setup for a specific option."""
        option = self.registry.get_option(option_id)
        if not option:
            return False
        
        try:
            # Map option IDs to execution methods
            execution_map = {
                "core_directory_structure": self._setup_directory_structure,
                "tool_discovery_auto": self._setup_tool_discovery,
                "metadata_extraction": self._setup_metadata_extraction,
                "integrate_pathfixer": self._setup_pathfixer_integration,
                "integrate_analyzer": self._setup_analyzer_integration,
                "integrate_organizer": self._setup_organizer_integration,
                "gui_interface": self._setup_gui_interface,
                "cli_interface": self._setup_cli_interface,
                "caching_system": self._setup_caching,
                "parallel_processing": self._setup_parallel_processing,
                "export_profiles": self._setup_profile_export,
            }
            
            if option_id in execution_map:
                return execution_map[option_id]()
            else:
                # Generic option setup
                logger.info(f"[EVENT] Setting up: {option.name}")
                return True
                
        except Exception as e:
            logger.error(f"[EVENT] Failed to setup {option_id}: {e}")
            return False
    
    def _setup_directory_structure(self) -> bool:
        """Setup directory structure."""
        try:
            # Create subdirectories
            subdirs = ["scripts", "configs", "templates", "workflows", "plugins"]
            for subdir in subdirs:
                (self.env.tools_dir / subdir).mkdir(exist_ok=True)
            
            # Create README
            readme = self.env.tools_dir / "README.md"
            readme_content = """# Organization Tools Directory

This directory contains organized tools and configurations created by the Adaptive Onboarder.

## Structure
- `scripts/`: Tool scripts and launchers
- `configs/`: Configuration files
- `templates/`: Setup templates
- `workflows/`: Tool workflow definitions
- `plugins/`: Optional plugins and extensions

## Usage
Run the launcher to access organized tools:
```bash
python launcher.py --help
```

## Maintenance
- Add new tools to the appropriate directory
- Update configurations in `configs/`
- Export profiles for sharing setups
"""
            readme.write_text(readme_content)
            
            return True
        except Exception as e:
            logger.error(f"[EVENT] Failed to setup directory structure: {e}")
            return False
    
    def _setup_tool_discovery(self) -> bool:
        """Setup automatic tool discovery."""
        try:
            # Create discovery configuration
            config = {
                "discovery": {
                    "enabled": True,
                    "methods": ["auto", "recursive"],
                    "depth": 3,
                    "patterns": ["*.py", "tool_*.py", "*_tool.py", "*analyzer*.py", "*organizer*.py"],
                    "exclude": ["__pycache__", ".git", ".venv", "venv", "env", "test_*", "*_test.py"],
                    "scan_interval": 3600,
                    "cache_results": True
                }
            }
            
            config_file = self.env.config_dir / "discovery_config.json"
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Create discovery script
            discovery_script = self.env.tools_dir / "scripts" / "discover_tools.py"
            discovery_content = """#!/usr/bin/env python3
"""
            # ... (discovery script content would go here)
            
            discovery_script.write_text(discovery_content)
            discovery_script.chmod(0o755)
            
            return True
        except Exception as e:
            logger.error(f"[EVENT] Failed to setup tool discovery: {e}")
            return False
    
    def _setup_metadata_extraction(self) -> bool:
        """Setup metadata extraction."""
        try:
            # Create metadata extraction configuration
            config = {
                "metadata": {
                    "extract_argparse": True,
                    "extract_imports": True,
                    "extract_functions": True,
                    "extract_classes": True,
                    "extract_docstrings": True,
                    "extract_dependencies": True,
                    "extract_usage_patterns": True,
                    "cache_metadata": True,
                    "metadata_file": "tools_metadata.json"
                }
            }
            
            config_file = self.env.config_dir / "metadata_config.json"
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"[EVENT] Failed to setup metadata extraction: {e}")
            return False
    
    def _setup_pathfixer_integration(self) -> bool:
        """Setup PathFixer integration."""
        try:
            # Check if pathfixer exists
            pathfixer_path = self.env.base_dir / "pathfixer.py"
            if not pathfixer_path.exists():
                logger.warning("[EVENT] PathFixer not found, integration will be limited")
                # Create minimal integration
                integration_config = {
                    "pathfixer": {
                        "enabled": False,
                        "available": False,
                        "note": "PathFixer not found in base directory"
                    }
                }
            else:
                # Create full integration
                integration_config = {
                    "pathfixer": {
                        "enabled": True,
                        "available": True,
                        "path": str(pathfixer_path),
                        "scan_on_discovery": True,
                        "fix_level": "moderate",
                        "create_snapshots": True,
                        "backup_before_fix": True
                    }
                }
            
            config_file = self.env.config_dir / "integrations" / "pathfixer.json"
            config_file.parent.mkdir(exist_ok=True)
            
            with open(config_file, 'w') as f:
                json.dump(integration_config, f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"[EVENT] Failed to setup PathFixer integration: {e}")
            return False
    
    def _setup_analyzer_integration(self) -> bool:
        """Setup Analyzer integration."""
        # Similar to pathfixer integration
        return self._create_integration_config("analyzer", "analyzer.py")
    
    def _setup_organizer_integration(self) -> bool:
        """Setup Organizer integration."""
        return self._create_integration_config("organizer", "organizer.py")
    
    def _create_integration_config(self, tool_name: str, filename: str) -> bool:
        """Create integration configuration for a tool."""
        try:
            tool_path = self.env.base_dir / filename
            available = tool_path.exists()
            
            config = {
                tool_name: {
                    "enabled": available,
                    "available": available,
                    "path": str(tool_path) if available else None,
                    "integration_level": "full" if available else "none"
                }
            }
            
            config_file = self.env.config_dir / "integrations" / f"{tool_name}.json"
            config_file.parent.mkdir(exist_ok=True)
            
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"[EVENT] Failed to setup {tool_name} integration: {e}")
            return False
    
    def _setup_gui_interface(self) -> bool:
        """Setup GUI interface."""
        try:
            # Create GUI launcher
            gui_launcher = self.env.tools_dir / "gui_launcher.py"
            gui_content = """#!/usr/bin/env python3
"""
            # ... (GUI launcher content would go here)
            
            gui_launcher.write_text(gui_content)
            gui_launcher.chmod(0o755)
            
            # Create GUI configuration
            gui_config = {
                "gui": {
                    "enabled": True,
                    "theme": "default",
                    "window_size": "1200x800",
                    "treeview": True,
                    "context_menu": True,
                    "shortcuts": True,
                    "icons": True,
                    "dark_mode": False
                }
            }
            
            config_file = self.env.config_dir / "gui_config.json"
            with open(config_file, 'w') as f:
                json.dump(gui_config, f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"[EVENT] Failed to setup GUI interface: {e}")
            return False
    
    def _setup_cli_interface(self) -> bool:
        """Setup CLI interface."""
        try:
            # Create main launcher
            launcher = self.env.tools_dir / "launcher.py"
            launcher_content = """#!/usr/bin/env python3
"""
            # ... (CLI launcher content would go here)
            
            launcher.write_text(launcher_content)
            launcher.chmod(0o755)
            
            # Create CLI configuration
            cli_config = {
                "cli": {
                    "enabled": True,
                    "rich_output": True,
                    "color_scheme": "auto",
                    "auto_complete": True,
                    "help_system": True,
                    "progress_bars": True,
                    "logging_level": "INFO"
                }
            }
            
            config_file = self.env.config_dir / "cli_config.json"
            with open(config_file, 'w') as f:
                json.dump(cli_config, f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"[EVENT] Failed to setup CLI interface: {e}")
            return False
    
    def _setup_caching(self) -> bool:
        """Setup caching system."""
        try:
            cache_config = {
                "caching": {
                    "enabled": True,
                    "disk_cache": True,
                    "memory_cache": True,
                    "cache_dir": str(self.env.tools_dir / "cache"),
                    "max_disk_cache_mb": 100,
                    "max_memory_cache_mb": 50,
                    "cache_ttl": 3600,
                    "compression": True
                }
            }
            
            config_file = self.env.config_dir / "cache_config.json"
            with open(config_file, 'w') as f:
                json.dump(cache_config, f, indent=2)
            
            # Create cache directory
            cache_dir = self.env.tools_dir / "cache"
            cache_dir.mkdir(exist_ok=True)
            
            return True
        except Exception as e:
            logger.error(f"[EVENT] Failed to setup caching: {e}")
            return False
    
    def _setup_parallel_processing(self) -> bool:
        """Setup parallel processing."""
        try:
            parallel_config = {
                "parallel": {
                    "enabled": True,
                    "max_workers": 4,
                    "process_pool": True,
                    "thread_pool": True,
                    "timeout": 300,
                    "retry_failed": True,
                    "queue_size": 100
                }
            }
            
            config_file = self.env.config_dir / "parallel_config.json"
            with open(config_file, 'w') as f:
                json.dump(parallel_config, f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"[EVENT] Failed to setup parallel processing: {e}")
            return False
    
    def _setup_profile_export(self) -> bool:
        """Setup profile export/import."""
        try:
            export_config = {
                "profiles": {
                    "export_enabled": True,
                    "import_enabled": True,
                    "format": "json",
                    "include_configs": True,
                    "include_metadata": True,
                    "encryption": False,
                    "compression": True
                }
            }
            
            config_file = self.env.config_dir / "export_config.json"
            with open(config_file, 'w') as f:
                json.dump(export_config, f, indent=2)
            
            # Create example profile
            example_profile = {
                "name": "Example Minimal Setup",
                "description": "Example profile with minimal configuration",
                "options": {
                    "core_directory_structure": True,
                    "cli_interface": True,
                    "tool_discovery_auto": True
                }
            }
            
            profile_file = self.env.profiles_dir / "example_minimal.json"
            with open(profile_file, 'w') as f:
                json.dump(example_profile, f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"[EVENT] Failed to setup profile export: {e}")
            return False
    
    def _generate_configuration(self, profile: SetupProfile) -> Dict[str, Any]:
        """Generate consolidated configuration."""
        result = {
            "success": True,
            "files": [],
            "errors": []
        }
        
        try:
            # Create master configuration
            master_config = {
                "version": "1.0.0",
                "generated": datetime.datetime.now().isoformat(),
                "profile": profile.name,
                "environment": {
                    "base_dir": str(self.env.base_dir),
                    "os": self.env.detected_os,
                    "python_version": self.env.python_version
                },
                "options": profile.options,
                "integration_level": profile.integration_level.value,
                "discovery_method": profile.discovery_method.value,
                "config_style": profile.config_style.value
            }
            
            # Add option-specific configurations
            for opt_id, enabled in profile.options.items():
                if enabled and opt_id in self.registry.options:
                    option = self.registry.options[opt_id]
                    if option.config_template:
                        master_config[f"config_{opt_id}"] = option.config_template
            
            # Save configuration based on style
            if profile.config_style == ConfigurationStyle.JSON:
                config_file = self.env.config_dir / "master_config.json"
                with open(config_file, 'w') as f:
                    json.dump(master_config, f, indent=2)
                result["files"].append(str(config_file))
            
            elif profile.config_style == ConfigurationStyle.YAML:
                config_file = self.env.config_dir / "master_config.yaml"
                with open(config_file, 'w') as f:
                    yaml.dump(master_config, f, default_flow_style=False)
                result["files"].append(str(config_file))
            
            # Create environment file
            env_content = f"""# Adaptive Onboarder Environment
BASE_DIR={self.env.base_dir}
TOOLS_DIR={self.env.tools_dir}
CONFIG_DIR={self.env.config_dir}
PYTHON_VERSION={self.env.python_version}
OS={self.env.detected_os}
PROFILE={profile.name}
"""
            
            env_file = self.env.tools_dir / ".env"
            env_file.write_text(env_content)
            result["files"].append(str(env_file))
            
            # Create startup script
            startup_script = self.env.tools_dir / "startup.sh"
            startup_content = f"""#!/bin/bash
# Adaptive Onboarder Startup Script
# Generated: {datetime.datetime.now().isoformat()}

export ONBOARDER_BASE="{self.env.base_dir}"
export ONBOARDER_TOOLS="{self.env.tools_dir}"
export PYTHONPATH="${{PYTHONPATH}}:{self.env.tools_dir}"

echo "Onboarder environment loaded"
echo "Tools directory: {self.env.tools_dir}"
echo "Run: python {self.env.tools_dir}/launcher.py --help"
"""
            
            startup_script.write_text(startup_content)
            startup_script.chmod(0o755)
            result["files"].append(str(startup_script))
            
        except Exception as e:
            result["success"] = False
            result["errors"].append(f"Configuration generation failed: {e}")
        
        return result
    
    def _validate_setup(self, profile: SetupProfile) -> Dict[str, Any]:
        """Validate the setup."""
        validation = {
            "success": True,
            "warnings": [],
            "errors": [],
            "checks_passed": 0,
            "checks_failed": 0
        }
        
        checks = [
            ("Directory structure", self._validate_directories),
            ("Configuration files", self._validate_configs),
            ("Tool launcher", self._validate_launcher),
            ("Permissions", self._validate_permissions)
        ]
        
        for check_name, check_func in checks:
            try:
                check_result = check_func()
                if check_result["success"]:
                    validation["checks_passed"] += 1
                else:
                    validation["checks_failed"] += 1
                    validation["errors"].extend(check_result.get("errors", []))
            except Exception as e:
                validation["checks_failed"] += 1
                validation["errors"].append(f"Validation check '{check_name}' failed: {e}")
        
        if validation["checks_failed"] > 0:
            validation["success"] = False
        
        return validation
    
    def _validate_directories(self) -> Dict[str, Any]:
        """Validate directory structure."""
        result = {"success": True, "errors": []}
        
        required_dirs = [
            self.env.tools_dir,
            self.env.config_dir,
            self.env.logs_dir
        ]
        
        for directory in required_dirs:
            if not directory.exists() or not directory.is_dir():
                result["success"] = False
                result["errors"].append(f"Missing directory: {directory}")
        
        return result
    
    def _validate_configs(self) -> Dict[str, Any]:
        """Validate configuration files."""
        result = {"success": True, "errors": []}
        
        # Check for master config
        config_files = [
            self.env.config_dir / "master_config.json",
            self.env.config_dir / "master_config.yaml",
            self.env.config_dir / "master_config.toml"
        ]
        
        config_exists = any(f.exists() for f in config_files)
        if not config_exists:
            result["success"] = False
            result["errors"].append("No master configuration file found")
        
        return result
    
    def _validate_launcher(self) -> Dict[str, Any]:
        """Validate launcher script."""
        result = {"success": True, "errors": []}
        
        launcher = self.env.tools_dir / "launcher.py"
        if not launcher.exists():
            result["success"] = False
            result["errors"].append("Launcher script not found")
        elif not os.access(launcher, os.X_OK):
            result["success"] = False
            result["errors"].append("Launcher script not executable")
        
        return result
    
    def _validate_permissions(self) -> Dict[str, Any]:
        """Validate permissions."""
        result = {"success": True, "errors": []}
        
        # Test write permissions in tools directory
        test_file = self.env.tools_dir / ".permission_test.tmp"
        try:
            test_file.write_text("test")
            test_file.unlink()
        except Exception as e:
            result["success"] = False
            result["errors"].append(f"Cannot write to tools directory: {e}")
        
        return result


# =============================================================================
# INTERACTIVE SETUP WIZARD
# =============================================================================

class InteractiveSetupWizard:
    """Interactive wizard for setup configuration."""
    
    def __init__(self, registry: SetupOptionsRegistry, env: SetupEnvironment):
        self.registry = registry
        self.env = env
        self.root = None
        self.selected_options = {}
        self.current_page = 0
        self.pages = []
        
    def run(self) -> Optional[SetupProfile]:
        """Run the interactive wizard."""
        self.root = tk.Tk()
        self.root.title("Adaptive Onboarder - Setup Wizard")
        self.root.geometry("1000x700")
        
        # Initialize with default selections
        self.selected_options = {
            opt_id: option.enabled_by_default 
            for opt_id, option in self.registry.options.items()
        }
        
        # Create pages
        self._create_pages()
        
        # Show first page
        self._show_page(0)
        
        self.root.mainloop()
        
        # Return profile if wizard completed successfully
        if hasattr(self, 'final_profile'):
            return self.final_profile
        return None
    
    def _create_pages(self):
        """Create wizard pages."""
        self.pages = [
            self._create_welcome_page,
            self._create_mode_selection_page,
            self._create_category_selection_page("infrastructure", "Infrastructure Setup"),
            self._create_category_selection_page("discovery", "Tool Discovery"),
            self._create_category_selection_page("interface", "User Interface"),
            self._create_category_selection_page("integration", "Tool Integration"),
            self._create_category_selection_page("advanced", "Advanced Features"),
            self._create_category_selection_page("performance", "Performance"),
            self._create_category_selection_page("security", "Security"),
            self._create_category_selection_page("portability", "Portability"),
            self._create_review_page,
            self._create_final_page
        ]
    
    def _show_page(self, page_index: int):
        """Show a specific page."""
        # Clear current content
        for widget in self.root.winfo_children():
            widget.destroy()
        
        # Update current page
        self.current_page = page_index
        
        # Create page content
        if page_index < len(self.pages):
            self.pages[page_index]()
        else:
            self._create_final_page()
    
    def _create_welcome_page(self):
        """Create welcome page."""
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Welcome text
        welcome_text = """Welcome to the Adaptive Onboarder Setup Wizard

This wizard will help you configure a personalized tool organization system.
The onboarder can adapt to your environment and offer multiple setup options.

Features:
• Multiple setup modes (Minimal, Standard, Comprehensive, Custom)
• Intelligent option suggestions based on your environment
• Integration with existing tools (PathFixer, Analyzer, Organizer)
• Configurable interfaces (CLI, GUI, Web)
• Performance and security options
• Portable and enterprise-ready configurations

Click 'Next' to begin configuration.
"""
        
        ttk.Label(frame, text=welcome_text, justify=tk.LEFT).pack(pady=20)
        
        # Environment info
        env_info = f"""
Environment Detected:
• Operating System: {self.env.detected_os}
• Python Version: {self.env.python_version}
• Base Directory: {self.env.base_dir}
• Available Tools: {len(self.env.constraints.get('detected_tools', {}))}
"""
        
        env_frame = ttk.LabelFrame(frame, text="Environment Information", padding=10)
        env_frame.pack(fill=tk.X, pady=10)
        ttk.Label(env_frame, text=env_info, justify=tk.LEFT).pack()
        
        # Navigation buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Exit", command=self.root.quit).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Next →", 
                  command=lambda: self._show_page(1)).pack(side=tk.RIGHT)
    
    def _create_mode_selection_page(self):
        """Create mode selection page."""
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Select Setup Mode", 
                 font=("Arial", 16, "bold")).pack(pady=10)
        
        modes = [
            ("Minimal", "Basic directory structure and CLI only", SetupMode.MINIMAL),
            ("Standard", "Recommended setup with core features", SetupMode.STANDARD),
            ("Comprehensive", "Full feature set with all integrations", SetupMode.COMPREHENSIVE),
            ("Custom", "Choose every option manually", SetupMode.CUSTOM),
            ("Portable", "Lightweight setup for sharing/moving", SetupMode.PORTABLE),
            ("Enterprise", "Advanced features for team/organization use", SetupMode.ENTERPRISE)
        ]
        
        self.selected_mode = tk.StringVar(value=SetupMode.STANDARD.value)
        
        for name, description, mode in modes:
            mode_frame = ttk.Frame(frame)
            mode_frame.pack(fill=tk.X, pady=5, padx=20)
            
            rb = ttk.Radiobutton(mode_frame, text=name, value=mode.value, 
                               variable=self.selected_mode)
            rb.pack(side=tk.LEFT)
            
            ttk.Label(mode_frame, text=description, 
                     foreground="gray").pack(side=tk.LEFT, padx=10)
        
        # Mode descriptions
        desc_frame = ttk.LabelFrame(frame, text="Mode Details", padding=10)
        desc_frame.pack(fill=tk.X, pady=20)
        
        descriptions = {
            SetupMode.MINIMAL: "Fast setup, minimal dependencies, basic functionality",
            SetupMode.STANDARD: "Balanced setup with recommended features, good for most users",
            SetupMode.COMPREHENSIVE: "Complete setup with all features, may require additional dependencies",
            SetupMode.CUSTOM: "Full control over every option, for advanced users",
            SetupMode.PORTABLE: "Self-contained setup, easy to share or move between systems",
            SetupMode.ENTERPRISE: "Team-ready with security, auditing, and collaboration features"
        }
        
        current_desc = tk.StringVar()
        current_desc.set(descriptions[SetupMode.STANDARD])
        
        def update_description(*args):
            mode = SetupMode(self.selected_mode.get())
            current_desc.set(descriptions.get(mode, ""))
        
        self.selected_mode.trace("w", update_description)
        
        ttk.Label(desc_frame, textvariable=current_desc, 
                 wraplength=800).pack()
        
        # Navigation
        button_frame = ttk.Frame(frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="← Back", 
                  command=lambda: self._show_page(0)).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Next →", 
                  command=lambda: self._apply_mode_and_continue()).pack(side=tk.RIGHT)
    
    def _apply_mode_and_continue(self):
        """Apply mode selection and continue to next page."""
        mode = SetupMode(self.selected_mode.get())
        
        # Apply mode-specific defaults
        mode_defaults = {
            SetupMode.MINIMAL: ["core_directory_structure", "cli_interface"],
            SetupMode.STANDARD: [
                "core_directory_structure", "tool_discovery_auto", "metadata_extraction",
                "cli_interface", "gui_interface", "caching_system", "export_profiles"
            ],
            SetupMode.COMPREHENSIVE: list(self.registry.options.keys()),
            SetupMode.PORTABLE: [
                "core_directory_structure", "cli_interface", "tool_discovery_auto",
                "export_profiles"
            ],
            SetupMode.ENTERPRISE: [
                "core_directory_structure", "tool_discovery_auto", "metadata_extraction",
                "cli_interface", "gui_interface", "caching_system", "parallel_processing",
                "audit_logging", "version_control", "export_profiles"
            ]
        }
        
        if mode != SetupMode.CUSTOM:
            # Reset to mode defaults
            for opt_id in self.registry.options.keys():
                self.selected_options[opt_id] = opt_id in mode_defaults.get(mode, [])
        
        # Skip to appropriate page
        if mode == SetupMode.MINIMAL:
            self._show_page(len(self.pages) - 2)  # Skip to review
        elif mode == SetupMode.STANDARD:
            self._show_page(5)  # Skip to review after basic pages
        else:
            self._show_page(2)  # Continue with category pages
    
    def _create_category_selection_page(self, category: str, title: str):
        """Create a page for selecting options in a category."""
        def page_func():
            frame = ttk.Frame(self.root, padding=20)
            frame.pack(fill=tk.BOTH, expand=True)
            
            ttk.Label(frame, text=title, 
                     font=("Arial", 16, "bold")).pack(pady=10)
            
            # Get options in this category
            options = self.registry.get_options_by_category(category)
            
            if not options:
                ttk.Label(frame, text=f"No options in category: {category}").pack()
            else:
                # Create checkboxes for each option
                options_frame = ttk.Frame(frame)
                options_frame.pack(fill=tk.BOTH, expand=True, pady=10)
                
                canvas = tk.Canvas(options_frame)
                scrollbar = ttk.Scrollbar(options_frame, orient="vertical", command=canvas.yview)
                scrollable_frame = ttk.Frame(canvas)
                
                scrollable_frame.bind(
                    "<Configure>",
                    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
                )
                
                canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
                canvas.configure(yscrollcommand=scrollbar.set)
                
                for i, option in enumerate(options):
                    opt_frame = ttk.Frame(scrollable_frame)
                    opt_frame.pack(fill=tk.X, pady=5, padx=10)
                    
                    # Checkbox
                    var = tk.BooleanVar(value=self.selected_options.get(option.id, False))
                    
                    def make_callback(opt_id, v):
                        return lambda: self._update_option(opt_id, v.get())
                    
                    cb = ttk.Checkbutton(opt_frame, text=option.name, 
                                       variable=var,
                                       command=make_callback(option.id, var))
                    cb.pack(side=tk.LEFT, anchor="w")
                    
                    # Description
                    desc_text = f"{option.description}\n"
                    desc_text += f"Complexity: {option.complexity.title()} • "
                    desc_text += f"Time: {option.estimated_time} min • "
                    desc_text += f"Weight: {option.weight:.1f}"
                    
                    if option.dependencies:
                        desc_text += f"\nDependencies: {', '.join(option.dependencies)}"
                    
                    if option.requires:
                        desc_text += f"\nRequires: {', '.join(option.requires)}"
                    
                    ttk.Label(opt_frame, text=desc_text, 
                             foreground="gray", wraplength=700).pack(side=tk.LEFT, padx=20)
                
                canvas.pack(side="left", fill="both", expand=True)
                scrollbar.pack(side="right", fill="y")
            
            # Navigation
            button_frame = ttk.Frame(frame)
            button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)
            
            ttk.Button(button_frame, text="← Back", 
                      command=lambda: self._show_page(self.current_page - 1)).pack(side=tk.LEFT)
            
            next_text = "Next →" if self.current_page < len(self.pages) - 2 else "Review"
            ttk.Button(button_frame, text=next_text, 
                      command=lambda: self._show_page(self.current_page + 1)).pack(side=tk.RIGHT)
            
            # Quick navigation
            nav_frame = ttk.Frame(frame)
            nav_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)
            
            categories = list(self.registry.categories.keys())
            current_index = categories.index(category) if category in categories else 0
            
            for i, cat in enumerate(categories):
                btn = ttk.Button(nav_frame, text=cat.title(), 
                               command=lambda idx=i: self._show_page(2 + idx))
                btn.pack(side=tk.LEFT, padx=2)
                if i == current_index:
                    btn.state(['pressed', 'disabled'])
        
        return page_func
    
    def _update_option(self, option_id: str, enabled: bool):
        """Update an option selection."""
        self.selected_options[option_id] = enabled
        
        # Handle dependencies and conflicts
        option = self.registry.get_option(option_id)
        if option:
            if enabled:
                # Enable requirements
                for req in option.requires:
                    if req in self.registry.options:
                        self.selected_options[req] = True
                
                # Disable conflicts
                for conflict in option.conflicts:
                    if conflict in self.selected_options:
                        self.selected_options[conflict] = False
            else:
                # Check if any other options require this
                for opt_id, opt in self.registry.options.items():
                    if opt_id != option_id and self.selected_options.get(opt_id, False):
                        if option_id in opt.requires:
                            # This option is required by another enabled option
                            self.selected_options[option_id] = True
                            break
    
    def _create_review_page(self):
        """Create review and summary page."""
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Setup Review", 
                 font=("Arial", 16, "bold")).pack(pady=10)
        
        # Calculate statistics
        enabled_count = sum(1 for v in self.selected_options.values() if v)
        total_count = len(self.selected_options)
        
        # Time and complexity estimates
        total_time = 0
        max_complexity = "low"
        complexity_map = {"low": 1, "medium": 2, "high": 3, "very_high": 4}
        
        for opt_id, enabled in self.selected_options.items():
            if enabled and opt_id in self.registry.options:
                option = self.registry.options[opt_id]
                total_time += option.estimated_time
                
                if complexity_map.get(option.complexity, 0) > complexity_map.get(max_complexity, 0):
                    max_complexity = option.complexity
        
        # Summary
        summary_text = f"""
Setup Summary:
• Options Selected: {enabled_count} of {total_count}
• Estimated Setup Time: {total_time} minutes
• Maximum Complexity: {max_complexity.title()}
• Integration Level: {self._calculate_integration_level().value.title()}

Configuration will be saved to: {self.env.tools_dir}
"""
        
        ttk.Label(frame, text=summary_text, justify=tk.LEFT).pack(pady=10)
        
        # Detailed breakdown
        notebook = ttk.Notebook(frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # By category
        for category, option_ids in self.registry.categories.items():
            cat_frame = ttk.Frame(notebook)
            notebook.add(cat_frame, text=category.title())
            
            enabled_in_cat = 0
            for opt_id in option_ids:
                if self.selected_options.get(opt_id, False):
                    enabled_in_cat += 1
                    option = self.registry.options[opt_id]
                    ttk.Label(cat_frame, 
                             text=f"✓ {option.name} ({option.estimated_time} min)").pack(anchor="w")
            
            if enabled_in_cat == 0:
                ttk.Label(cat_frame, text="No options selected in this category").pack()
        
        # Validation
        valid, errors, warnings = self.registry.validate_selection(self.selected_options)
        
        if errors:
            error_frame = ttk.LabelFrame(frame, text="Validation Errors", padding=10)
            error_frame.pack(fill=tk.X, pady=10)
            
            for error in errors:
                ttk.Label(error_frame, text=f"• {error}", 
                         foreground="red").pack(anchor="w")
        
        if warnings:
            warn_frame = ttk.LabelFrame(frame, text="Warnings", padding=10)
            warn_frame.pack(fill=tk.X, pady=10)
            
            for warning in warnings:
                ttk.Label(warn_frame, text=f"• {warning}", 
                         foreground="orange").pack(anchor="w")
        
        # Navigation
        button_frame = ttk.Frame(frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="← Back", 
                  command=lambda: self._show_page(self.current_page - 1)).pack(side=tk.LEFT)
        
        if valid:
            ttk.Button(button_frame, text="Finish Setup", 
                      command=self._create_profile_and_finish).pack(side=tk.RIGHT)
        else:
            ttk.Label(button_frame, text="Please fix validation errors",
                     foreground="red").pack(side=tk.RIGHT)
    
    def _calculate_integration_level(self) -> IntegrationLevel:
        """Calculate integration level based on selected options."""
        integration_options = [
            opt_id for opt_id, enabled in self.selected_options.items() 
            if enabled and opt_id in self.registry.options and 
            self.registry.options[opt_id].category == "integration"
        ]
        
        if len(integration_options) >= 3:
            return IntegrationLevel.FULL
        elif len(integration_options) >= 2:
            return IntegrationLevel.DEEP
        elif len(integration_options) >= 1:
            return IntegrationLevel.MODERATE
        else:
            return IntegrationLevel.LIGHT
    
    def _create_profile_and_finish(self):
        """Create profile from selections and finish."""
        # Get profile name
        profile_name = simpledialog.askstring(
            "Profile Name",
            "Enter a name for this setup profile:",
            parent=self.root
        )
        
        if not profile_name:
            profile_name = f"Profile_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Get mode (use selected mode or custom)
        mode = getattr(self, 'selected_mode', SetupMode.CUSTOM)
        if isinstance(mode, tk.StringVar):
            mode = SetupMode(mode.get())
        
        # Create profile
        profile = self.registry.generate_profile(
            name=profile_name,
            description=f"Profile created via wizard on {datetime.datetime.now().isoformat()}",
            mode=mode,
            selected=self.selected_options
        )
        
        # Save profile
        profile_file = self.env.profiles_dir / f"{profile_name.lower().replace(' ', '_')}.json"
        with open(profile_file, 'w') as f:
            json.dump(asdict(profile), f, indent=2, default=str)
        
        self.final_profile = profile
        
        # Show final page
        self._show_page(len(self.pages) - 1)
    
    def _create_final_page(self):
        """Create final page with completion options."""
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Setup Configuration Complete!", 
                 font=("Arial", 16, "bold")).pack(pady=10)
        
        if hasattr(self, 'final_profile'):
            profile = self.final_profile
            
            completion_text = f"""
Profile '{profile.name}' has been created.

Next Steps:
1. Review the setup plan
2. Execute the setup
3. Validate the installation
4. Start using your organized tools

Profile saved to: {self.env.profiles_dir}
"""
            
            ttk.Label(frame, text=completion_text, justify=tk.LEFT).pack(pady=10)
            
            # Action buttons
            button_frame = ttk.Frame(frame)
            button_frame.pack(pady=20)
            
            ttk.Button(button_frame, text="View Profile", 
                      command=lambda: self._view_profile(profile)).pack(side=tk.LEFT, padx=5)
            
            ttk.Button(button_frame, text="Generate Setup Plan", 
                      command=lambda: self._generate_plan(profile)).pack(side=tk.LEFT, padx=5)
            
            ttk.Button(button_frame, text="Execute Setup", 
                      command=lambda: self._execute_setup(profile)).pack(side=tk.LEFT, padx=5)
            
            ttk.Button(button_frame, text="Export Profile", 
                      command=lambda: self._export_profile(profile)).pack(side=tk.LEFT, padx=5)
        
        else:
            ttk.Label(frame, text="No profile was created.").pack()
        
        ttk.Button(frame, text="Close Wizard", 
                  command=self.root.quit).pack(side=tk.BOTTOM, pady=10)
    
    def _view_profile(self, profile: SetupProfile):
        """View profile details."""
        view_window = tk.Toplevel(self.root)
        view_window.title(f"Profile: {profile.name}")
        view_window.geometry("800x600")
        
        text = scrolledtext.ScrolledText(view_window, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        profile_dict = asdict(profile)
        text.insert(tk.END, json.dumps(profile_dict, indent=2, default=str))
        text.config(state=tk.DISABLED)
    
    def _generate_plan(self, profile: SetupProfile):
        """Generate setup plan."""
        engine = AdaptiveSetupEngine(self.env, self.registry)
        plan = engine.generate_setup_plan(profile)
        
        plan_window = tk.Toplevel(self.root)
        plan_window.title(f"Setup Plan: {profile.name}")
        plan_window.geometry("1000x700")
        
        notebook = ttk.Notebook(plan_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Summary tab
        summary_frame = ttk.Frame(notebook)
        notebook.add(summary_frame, text="Summary")
        
        summary_text = f"""
Setup Plan: {profile.name}

Estimated Time: {plan['estimated_time']} minutes
Complexity: {plan['complexity']}
Phases: {len(plan['phases'])}

Environment:
• Base Directory: {plan['environment']['base_dir']}
• OS: {plan['environment']['os']}
• Python: {plan['environment']['python_version']}
"""
        
        ttk.Label(summary_frame, text=summary_text, justify=tk.LEFT).pack(pady=10)
        
        # Phases tab
        phases_frame = ttk.Frame(notebook)
        notebook.add(phases_frame, text="Phases")
        
        phases_text = ""
        for phase in plan['phases']:
            phases_text += f"\n{phase['name']} ({len(phase['steps'])} steps):\n"
            for step in phase['steps']:
                phases_text += f"  • {step['name']} ({step['estimated_time']} min)\n"
        
        text = scrolledtext.ScrolledText(phases_frame, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert(tk.END, phases_text)
        text.config(state=tk.DISABLED)
        
        # Save plan button
        def save_plan():
            file_path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            if file_path:
                with open(file_path, 'w') as f:
                    json.dump(plan, f, indent=2, default=str)
                messagebox.showinfo("Saved", f"Plan saved to {file_path}")
        
        ttk.Button(plan_window, text="Save Plan", command=save_plan).pack(pady=10)
    
    def _execute_setup(self, profile: SetupProfile):
        """Execute the setup."""
        # Ask for confirmation
        confirm = messagebox.askyesno(
            "Confirm Setup",
            f"Execute setup for profile '{profile.name}'?\n\n"
            f"This will create directories and configuration files in:\n"
            f"{self.env.base_dir}"
        )
        
        if not confirm:
            return
        
        # Create setup engine
        engine = AdaptiveSetupEngine(self.env, self.registry)
        
        # Ask for dry run option
        dry_run = messagebox.askyesno(
            "Dry Run",
            "Perform a dry run first to see what will be created?\n\n"
            "Dry run shows actions without making changes."
        )
        
        # Execute setup
        result = engine.execute_setup(profile, dry_run=dry_run)
        
        # Show results
        result_window = tk.Toplevel(self.root)
        result_window.title("Setup Results")
        result_window.geometry("800x600")
        
        result_text = f"""
Setup {'Dry Run' if dry_run else 'Execution'} Results:

Success: {result['success']}
Steps Completed: {result['steps_completed']}/{result['total_steps']}
Steps Failed: {result['steps_failed']}
Setup Time: {result['setup_time']:.1f} seconds

Generated Files: {len(result['generated_files'])}
"""
        
        if result['errors']:
            result_text += "\nErrors:\n"
            for error in result['errors'][:5]:  # Show first 5
                result_text += f"• {error}\n"
        
        if result['warnings']:
            result_text += "\nWarnings:\n"
            for warning in result['warnings'][:5]:
                result_text += f"• {warning}\n"
        
        text = scrolledtext.ScrolledText(result_window, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert(tk.END, result_text)
        text.config(state=tk.DISABLED)
        
        if result['success'] and not dry_run:
            messagebox.showinfo(
                "Setup Complete",
                f"Setup completed successfully!\n\n"
                f"Your organized tools are ready in:\n"
                f"{self.env.tools_dir}\n\n"
                f"Run: python {self.env.tools_dir}/launcher.py --help"
            )
    
    def _export_profile(self, profile: SetupProfile):
        """Export profile to file."""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("YAML files", "*.yaml"), ("All files", "*.*")],
            initialfile=f"{profile.name.lower().replace(' ', '_')}_profile"
        )
        
        if file_path:
            profile_dict = asdict(profile)
            
            if file_path.endswith('.yaml'):
                with open(file_path, 'w') as f:
                    yaml.dump(profile_dict, f, default_flow_style=False)
            else:
                with open(file_path, 'w') as f:
                    json.dump(profile_dict, f, indent=2, default=str)
            
            messagebox.showinfo("Exported", f"Profile exported to {file_path}")


# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Adaptive Tool Onboarder with Multi-Option Configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive wizard (GUI)
  adaptive_onboarder.py wizard
  
  # Quick setup with suggested options
  adaptive_onboarder.py quick-setup
  
  # Custom setup with specific options
  adaptive_onboarder.py setup --option gui_interface --option caching_system
  
  # Generate setup plan only
  adaptive_onboarder.py plan --profile standard
  
  # Execute existing profile
  adaptive_onboarder.py execute --profile my_profile
  
  # List available options
  adaptive_onboarder.py list-options
  
  # Validate configuration
  adaptive_onboarder.py validate --config config.json
  
  # Export/import profiles
  adaptive_onboarder.py export-profile --profile standard --output standard.json
  adaptive_onboarder.py import-profile --file custom_profile.json

Setup Modes:
  minimal       - Basic directory structure and CLI only
  standard      - Recommended setup with core features (default)
  comprehensive - Full feature set with all integrations
  custom        - Choose every option manually
  portable      - Lightweight setup for sharing/moving
  enterprise    - Advanced features for team/organization use

Integration Levels:
  none      - No integration with existing tools
  light     - Basic discovery only
  moderate  - Metadata extraction and basic integration
  deep      - Full integration with available tools
  full      - Complete ecosystem integration

Discovery Methods:
  auto       - Automatic discovery based on patterns
  manual     - Manual tool specification
  pattern    - Pattern-based discovery
  recursive  - Recursive directory scanning
  indexed    - Use pre-built index
  hybrid     - Combination of methods
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Wizard command
    wizard_parser = subparsers.add_parser('wizard', help='Interactive setup wizard (GUI)')
    wizard_parser.add_argument('--dir', '-d', help='Base directory for setup')
    
    # Quick setup command
    quick_parser = subparsers.add_parser('quick-setup', help='Quick setup with suggestions')
    quick_parser.add_argument('--mode', '-m', 
                            choices=[m.value for m in SetupMode],
                            default=SetupMode.STANDARD.value,
                            help='Setup mode')
    quick_parser.add_argument('--dir', '-d', help='Base directory')
    quick_parser.add_argument('--dry-run', action='store_true',
                            help='Show what would be created without making changes')
    quick_parser.add_argument('--yes', '-y', action='store_true',
                            help='Skip confirmation prompts')
    
    # Custom setup command
    setup_parser = subparsers.add_parser('setup', help='Custom setup with specific options')
    setup_parser.add_argument('--option', '-o', action='append',
                            help='Enable specific option (can be used multiple times)')
    setup_parser.add_argument('--disable', action='append',
                            help='Disable specific option')
    setup_parser.add_argument('--mode', '-m',
                            choices=[m.value for m in SetupMode],
                            default=SetupMode.CUSTOM.value,
                            help='Setup mode')
    setup_parser.add_argument('--dir', '-d', help='Base directory')
    setup_parser.add_argument('--dry-run', action='store_true',
                            help='Dry run without making changes')
    setup_parser.add_argument('--profile-name', help='Name for the setup profile')
    
    # Plan command
    plan_parser = subparsers.add_parser('plan', help='Generate setup plan')
    plan_parser.add_argument('--profile', '-p', help='Profile name or file')
    plan_parser.add_argument('--mode', '-m',
                           choices=[m.value for m in SetupMode],
                           help='Setup mode for new profile')
    plan_parser.add_argument('--output', '-o', help='Output file for plan')
    
    # Execute command
    execute_parser = subparsers.add_parser('execute', help='Execute setup from profile')
    execute_parser.add_argument('--profile', '-p', required=True,
                              help='Profile name or file')
    execute_parser.add_argument('--dir', '-d', help='Base directory')
    execute_parser.add_argument('--dry-run', action='store_true',
                              help='Dry run without making changes')
    
    # List options command
    list_parser = subparsers.add_parser('list-options', help='List available setup options')
    list_parser.add_argument('--category', '-c', help='Filter by category')
    list_parser.add_argument('--detailed', '-d', action='store_true',
                           help='Detailed output')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate configuration')
    validate_parser.add_argument('--config', '-c', help='Configuration file to validate')
    validate_parser.add_argument('--profile', '-p', help='Profile to validate')
    
    # Export profile command
    export_parser = subparsers.add_parser('export-profile', help='Export setup profile')
    export_parser.add_argument('--profile', '-p', required=True,
                             help='Profile name to export')
    export_parser.add_argument('--output', '-o', required=True,
                             help='Output file')
    export_parser.add_argument('--format', '-f',
                             choices=['json', 'yaml', 'toml'],
                             default='json',
                             help='Output format')
    
    # Import profile command
    import_parser = subparsers.add_parser('import-profile', help='Import setup profile')
    import_parser.add_argument('--file', '-f', required=True,
                             help='Profile file to import')
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Show system information')
    info_parser.add_argument('--dir', '-d', help='Directory to analyze')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Setup base directory
    base_dir = Path(args.dir) if hasattr(args, 'dir') and args.dir else Path.cwd()
    
    # Initialize registry and detector
    registry = SetupOptionsRegistry()
    detector = EnvironmentDetector(base_dir)
    
    # Execute command
    if args.command == 'wizard':
        handle_wizard(args, detector, registry)
    elif args.command == 'quick-setup':
        handle_quick_setup(args, detector, registry)
    elif args.command == 'setup':
        handle_custom_setup(args, detector, registry)
    elif args.command == 'plan':
        handle_plan(args, detector, registry)
    elif args.command == 'execute':
        handle_execute(args, detector, registry)
    elif args.command == 'list-options':
        handle_list_options(args, registry)
    elif args.command == 'validate':
        handle_validate(args, detector, registry)
    elif args.command == 'export-profile':
        handle_export_profile(args, detector, registry)
    elif args.command == 'import-profile':
        handle_import_profile(args, detector, registry)
    elif args.command == 'info':
        handle_info(args, detector)

def handle_wizard(args, detector: EnvironmentDetector, registry: SetupOptionsRegistry):
    """Handle wizard command."""
    # Detect environment
    env = detector.detect_all()
    
    # Run wizard
    wizard = InteractiveSetupWizard(registry, env)
    profile = wizard.run()
    
    if profile:
        print(f"\nProfile created: {profile.name}")
        print(f"Profile saved to: {env.profiles_dir}")
        
        # Ask if user wants to execute
        execute = input("\nExecute setup now? (y/n): ").lower().strip()
        if execute == 'y':
            engine = AdaptiveSetupEngine(env, registry)
            result = engine.execute_setup(profile)
            
            print(f"\nSetup {'succeeded' if result['success'] else 'failed'}")
            print(f"Steps completed: {result['steps_completed']}/{result['total_steps']}")
            
            if result['generated_files']:
                print(f"\nGenerated files:")
                for file in result['generated_files'][:5]:
                    print(f"  {file}")

def handle_quick_setup(args, detector: EnvironmentDetector, registry: SetupOptionsRegistry):
    """Handle quick-setup command."""
    print(f"\n{'='*60}")
    print("QUICK SETUP")
    print(f"{'='*60}")
    
    # Detect environment
    env = detector.detect_all()
    print(f"Base directory: {env.base_dir}")
    print(f"OS: {env.detected_os}")
    print(f"Python: {env.python_version}")
    
    # Create engine
    engine = AdaptiveSetupEngine(env, registry)
    
    # Get suggestions
    suggestions = engine.suggest_options()
    
    # Select options based on mode
    mode = SetupMode(args.mode)
    print(f"\nMode: {mode.value.title()}")
    
    if mode == SetupMode.MINIMAL:
        selected = {opt_id: opt_id in ["core_directory_structure", "cli_interface"] 
                   for opt_id in registry.options.keys()}
    elif mode == SetupMode.STANDARD:
        selected = {opt_id: suggestions.get(opt_id, 0) > 0.5 
                   for opt_id in registry.options.keys()}
    elif mode == SetupMode.COMPREHENSIVE:
        selected = {opt_id: True for opt_id in registry.options.keys()}
    elif mode == SetupMode.PORTABLE:
        selected = {opt_id: opt_id in ["core_directory_structure", "cli_interface", 
                                      "tool_discovery_auto", "export_profiles"]
                   for opt_id in registry.options.keys()}
    elif mode == SetupMode.ENTERPRISE:
        selected = {opt_id: opt_id in ["core_directory_structure", "tool_discovery_auto",
                                      "metadata_extraction", "cli_interface", "gui_interface",
                                      "caching_system", "parallel_processing", "audit_logging",
                                      "version_control", "export_profiles"]
                   for opt_id in registry.options.keys()}
    else:
        selected = {}
    
    # Create profile
    profile_name = f"quick_{mode.value}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    profile = registry.generate_profile(
        name=profile_name,
        description=f"Quick setup profile ({mode.value})",
        mode=mode,
        selected=selected
    )
    
    # Show summary
    enabled_count = sum(1 for v in selected.values() if v)
    print(f"Options selected: {enabled_count} of {len(selected)}")
    
    if not args.yes:
        confirm = input("\nProceed with setup? (y/n): ").lower().strip()
        if confirm != 'y':
            print("Setup cancelled.")
            return
    
    # Execute
    print(f"\nExecuting {'dry run' if args.dry_run else 'setup'}...")
    result = engine.execute_setup(profile, dry_run=args.dry_run)
    
    # Show results
    print(f"\n{'='*60}")
    print("SETUP RESULTS")
    print(f"{'='*60}")
    
    print(f"Success: {result['success']}")
    print(f"Steps completed: {result['steps_completed']}/{result['total_steps']}")
    print(f"Setup time: {result['setup_time']:.1f}s")
    
    if result['errors']:
        print(f"\nErrors ({len(result['errors'])}):")
        for error in result['errors'][:3]:
            print(f"  • {error}")
    
    if result['generated_files'] and not args.dry_run:
        print(f"\nGenerated files ({len(result['generated_files'])}):")
        for file in result['generated_files'][:5]:
            print(f"  • {file}")
    
    print(f"\nProfile saved to: {env.profiles_dir}/{profile_name}.json")

def handle_custom_setup(args, detector: EnvironmentDetector, registry: SetupOptionsRegistry):
    """Handle custom setup command."""
    print(f"\n{'='*60}")
    print("CUSTOM SETUP")
    print(f"{'='*60}")
    
    # Detect environment
    env = detector.detect_all()
    
    # Build selection
    selected = {}
    for opt_id in registry.options.keys():
        option = registry.options[opt_id]
        selected[opt_id] = option.enabled_by_default
    
    # Apply command line selections
    if args.option:
        for opt_id in args.option:
            if opt_id in registry.options:
                selected[opt_id] = True
            else:
                print(f"Warning: Unknown option '{opt_id}'")
    
    if args.disable:
        for opt_id in args.disable:
            if opt_id in registry.options:
                selected[opt_id] = False
            else:
                print(f"Warning: Unknown option '{opt_id}'")
    
    # Validate
    valid, errors, warnings = registry.validate_selection(selected)
    
    if errors:
        print("\nValidation errors:")
        for error in errors:
            print(f"  • {error}")
    
    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"  • {warning}")
    
    if not valid:
        print("\nSetup cannot proceed with validation errors.")
        return
    
    # Create profile
    profile_name = args.profile_name or f"custom_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    mode = SetupMode(args.mode)
    
    profile = registry.generate_profile(
        name=profile_name,
        description=f"Custom setup profile",
        mode=mode,
        selected=selected
    )
    
    # Show summary
    enabled_count = sum(1 for v in selected.values() if v)
    print(f"\nProfile: {profile_name}")
    print(f"Mode: {mode.value}")
    print(f"Options selected: {enabled_count} of {len(selected)}")
    
    # Generate and show plan
    engine = AdaptiveSetupEngine(env, registry)
    plan = engine.generate_setup_plan(profile)
    
    print(f"\nSetup Plan:")
    print(f"  Estimated time: {plan['estimated_time']} minutes")
    print(f"  Complexity: {plan['complexity']}")
    print(f"  Phases: {len(plan['phases'])}")
    
    if not args.dry_run:
        confirm = input("\nExecute setup? (y/n): ").lower().strip()
        if confirm != 'y':
            print("Setup cancelled.")
            return
    
    # Execute
    print(f"\nExecuting {'dry run' if args.dry_run else 'setup'}...")
    result = engine.execute_setup(profile, dry_run=args.dry_run)
    
    # Show results
    print(f"\nResults:")
    print(f"  Success: {result['success']}")
    print(f"  Steps: {result['steps_completed']}/{result['total_steps']} completed")
    
    if result['success'] and not args.dry_run:
        print(f"\nSetup complete! Tools directory: {env.tools_dir}")

def handle_plan(args, detector: EnvironmentDetector, registry: SetupOptionsRegistry):
    """Handle plan command."""
    env = detector.detect_all()
    engine = AdaptiveSetupEngine(env, registry)
    
    # Load or create profile
    if args.profile:
        # Try to load existing profile
        profile_file = env.profiles_dir / f"{args.profile}.json"
        if profile_file.exists():
            with open(profile_file, 'r') as f:
                profile_data = json.load(f)
            
            # Convert back to SetupProfile
            # (simplified - in reality would need proper deserialization)
            print(f"Loaded profile: {args.profile}")
            # For now, create a minimal profile
            profile = SetupProfile(
                name=profile_data.get('name', args.profile),
                description=profile_data.get('description', ''),
                mode=SetupMode(profile_data.get('mode', 'standard')),
                options=profile_data.get('options', {}),
                integration_level=IntegrationLevel(profile_data.get('integration_level', 'light')),
                discovery_method=ToolDiscoveryMethod(profile_data.get('discovery_method', 'auto')),
                config_style=ConfigurationStyle(profile_data.get('config_style', 'json'))
            )
        else:
            # Create new profile with specified mode
            mode = SetupMode(args.mode) if args.mode else SetupMode.STANDARD
            print(f"Creating new profile with mode: {mode.value}")
            
            # Select options based on mode
            if mode == SetupMode.MINIMAL:
                selected = {opt_id: opt_id in ["core_directory_structure", "cli_interface"] 
                           for opt_id in registry.options.keys()}
            elif mode == SetupMode.STANDARD:
                suggestions = engine.suggest_options()
                selected = {opt_id: suggestions.get(opt_id, 0) > 0.5 
                           for opt_id in registry.options.keys()}
            elif mode == SetupMode.COMPREHENSIVE:
                selected = {opt_id: True for opt_id in registry.options.keys()}
            else:
                selected = {}
            
            profile = registry.generate_profile(
                name=args.profile,
                description=f"Profile created via plan command",
                mode=mode,
                selected=selected
            )
    else:
        print("Error: Profile name required")
        return
    
    # Generate plan
    plan = engine.generate_setup_plan(profile)
    
    # Output plan
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(plan, f, indent=2, default=str)
        print(f"Plan saved to: {args.output}")
    else:
        print(f"\n{'='*60}")
        print(f"SETUP PLAN: {profile.name}")
        print(f"{'='*60}")
        
        print(f"\nSummary:")
        print(f"  Estimated time: {plan['estimated_time']} minutes")
        print(f"  Complexity: {plan['complexity']}")
        print(f"  Environment: {plan['environment']['os']}, Python {plan['environment']['python_version']}")
        
        print(f"\nPhases ({len(plan['phases'])}):")
        for phase in plan['phases']:
            print(f"  • {phase['name']}: {len(phase['steps'])} steps")
        
        print(f"\nValidation steps: {len(plan['validation_steps'])}")
        print(f"Rollback steps: {len(plan['rollback_steps'])}")

def handle_execute(args, detector: EnvironmentDetector, registry: SetupOptionsRegistry):
    """Handle execute command."""
    env = detector.detect_all()
    
    # Load profile
    profile_path = Path(args.profile)
    if not profile_path.exists():
        # Check in profiles directory
        profile_path = env.profiles_dir / f"{args.profile}.json"
    
    if not profile_path.exists():
        print(f"Error: Profile not found: {args.profile}")
        return
    
    with open(profile_path, 'r') as f:
        profile_data = json.load(f)
    
    # Create profile object (simplified)
    profile = SetupProfile(
        name=profile_data.get('name', args.profile),
        description=profile_data.get('description', ''),
        mode=SetupMode(profile_data.get('mode', 'standard')),
        options=profile_data.get('options', {}),
        integration_level=IntegrationLevel(profile_data.get('integration_level', 'light')),
        discovery_method=ToolDiscoveryMethod(profile_data.get('discovery_method', 'auto')),
        config_style=ConfigurationStyle(profile_data.get('config_style', 'json'))
    )
    
    print(f"\nExecuting profile: {profile.name}")
    print(f"Mode: {profile.mode.value}")
    print(f"Options: {sum(1 for v in profile.options.values() if v)} enabled")
    
    if not args.dry_run:
        confirm = input("\nProceed with execution? (y/n): ").lower().strip()
        if confirm != 'y':
            print("Execution cancelled.")
            return
    
    # Execute
    engine = AdaptiveSetupEngine(env, registry)
    result = engine.execute_setup(profile, dry_run=args.dry_run)
    
    print(f"\nExecution {'dry run' if args.dry_run else 'complete'}:")
    print(f"  Success: {result['success']}")
    print(f"  Steps: {result['steps_completed']}/{result['total_steps']}")
    print(f"  Time: {result['setup_time']:.1f}s")
    
    if result['errors']:
        print(f"\nErrors:")
        for error in result['errors'][:3]:
            print(f"  • {error}")
    
    if result['success'] and not args.dry_run:
        print(f"\nSetup complete! Access your tools at: {env.tools_dir}")

def handle_list_options(args, registry: SetupOptionsRegistry):
    """Handle list-options command."""
    categories = args.category.split(',') if args.category else registry.categories.keys()
    
    print(f"\n{'='*60}")
    print("AVAILABLE SETUP OPTIONS")
    print(f"{'='*60}")
    
    for category in categories:
        if category not in registry.categories:
            print(f"\nWarning: Unknown category '{category}'")
            continue
        
        print(f"\n{category.upper()}:")
        print("-" * len(category))
        
        options = registry.get_options_by_category(category)
        for option in options:
            enabled = "✓" if option.enabled_by_default else " "
            complexity = option.complexity[0].upper()
            
            if args.detailed:
                print(f"\n  [{enabled}] {option.name}")
                print(f"      ID: {option.id}")
                print(f"      Description: {option.description}")
                print(f"      Complexity: {option.complexity} ({option.estimated_time} min)")
                print(f"      Weight: {option.weight:.1f}")
                
                if option.requires:
                    print(f"      Requires: {', '.join(option.requires)}")
                if option.conflicts:
                    print(f"      Conflicts: {', '.join(option.conflicts)}")
                if option.dependencies:
                    print(f"      Dependencies: {', '.join(option.dependencies)}")
                if option.tags:
                    print(f"      Tags: {', '.join(option.tags)}")
            else:
                print(f"  [{enabled}] {option.name} ({complexity}, {option.estimated_time} min)")
        
        print(f"\n  Total: {len(options)} options")
    
    print(f"\n{'='*60}")
    print("Use '--detailed' for more information on each option")

def handle_validate(args, detector: EnvironmentDetector, registry: SetupOptionsRegistry):
    """Handle validate command."""
    if args.config:
        # Validate configuration file
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"Error: Config file not found: {args.config}")
            return
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            print(f"\nValidating configuration: {args.config}")
            
            # Check for required sections
            required = ["version", "options", "environment"]
            missing = [r for r in required if r not in config]
            
            if missing:
                print(f"  ✗ Missing sections: {', '.join(missing)}")
            else:
                print(f"  ✓ All required sections present")
            
            # Validate options if present
            if "options" in config:
                options = config["options"]
                valid, errors, warnings = registry.validate_selection(options)
                
                if valid:
                    print(f"  ✓ Options configuration is valid")
                else:
                    print(f"  ✗ Options configuration has errors:")
                    for error in errors:
                        print(f"    • {error}")
                
                if warnings:
                    print(f"  ⚠ Warnings:")
                    for warning in warnings:
                        print(f"    • {warning}")
            
            print("\nValidation complete.")
            
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in config file: {e}")
        except Exception as e:
            print(f"Error during validation: {e}")
    
    elif args.profile:
        # Validate profile
        env = detector.detect_all()
        profile_path = env.profiles_dir / f"{args.profile}.json"
        
        if not profile_path.exists():
            print(f"Error: Profile not found: {args.profile}")
            return
        
        with open(profile_path, 'r') as f:
            profile_data = json.load(f)
        
        print(f"\nValidating profile: {args.profile}")
        
        # Check profile structure
        required = ["name", "options", "mode"]
        missing = [r for r in required if r not in profile_data]
        
        if missing:
            print(f"  ✗ Missing fields: {', '.join(missing)}")
        else:
            print(f"  ✓ Profile structure is valid")
        
        # Validate options
        options = profile_data.get("options", {})
        valid, errors, warnings = registry.validate_selection(options)
        
        if valid:
            print(f"  ✓ Options selection is valid")
        else:
            print(f"  ✗ Options selection has errors:")
            for error in errors:
                print(f"    • {error}")
        
        if warnings:
            print(f"  ⚠ Warnings:")
            for warning in warnings:
                print(f"    • {warning}")
        
        print("\nProfile validation complete.")

def handle_export_profile(args, detector: EnvironmentDetector, registry: SetupOptionsRegistry):
    """Handle export-profile command."""
    env = detector.detect_all()
    
    # Find profile
    profile_path = env.profiles_dir / f"{args.profile}.json"
    if not profile_path.exists():
        print(f"Error: Profile not found: {args.profile}")
        return
    
    with open(profile_path, 'r') as f:
        profile_data = json.load(f)
    
    # Export
    output_path = Path(args.output)
    
    try:
        if args.format == 'yaml':
            with open(output_path, 'w') as f:
                yaml.dump(profile_data, f, default_flow_style=False)
        elif args.format == 'toml':
            # TOML would require additional library
            print("TOML export not implemented (requires 'toml' library)")
            return
        else:  # json
            with open(output_path, 'w') as f:
                json.dump(profile_data, f, indent=2)
        
        print(f"Profile exported to: {output_path}")
        
    except Exception as e:
        print(f"Error exporting profile: {e}")

def handle_import_profile(args, detector: EnvironmentDetector, registry: SetupOptionsRegistry):
    """Handle import-profile command."""
    env = detector.detect_all()
    
    # Load profile file
    profile_path = Path(args.file)
    if not profile_path.exists():
        print(f"Error: File not found: {args.file}")
        return
    
    try:
        if profile_path.suffix.lower() == '.yaml':
            with open(profile_path, 'r') as f:
                profile_data = yaml.safe_load(f)
        else:  # assume json
            with open(profile_path, 'r') as f:
                profile_data = json.load(f)
        
        # Extract profile name
        profile_name = profile_data.get('name', profile_path.stem)
        
        # Save to profiles directory
        output_path = env.profiles_dir / f"{profile_name}.json"
        with open(output_path, 'w') as f:
            json.dump(profile_data, f, indent=2)
        
        print(f"Profile imported as: {profile_name}")
        print(f"Saved to: {output_path}")
        
        # Validate
        valid, errors, warnings = registry.validate_selection(profile_data.get('options', {}))
        
        if valid:
            print("Profile validation: ✓ Valid")
        else:
            print("Profile validation: ✗ Has errors")
            for error in errors[:3]:
                print(f"  • {error}")
        
    except Exception as e:
        print(f"Error importing profile: {e}")

def handle_info(args, detector: EnvironmentDetector):
    """Handle info command."""
    env = detector.detect_all()
    
    print(f"\n{'='*60}")
    print("SYSTEM INFORMATION")
    print(f"{'='*60}")
    
    print(f"\nEnvironment:")
    print(f"  Base Directory: {env.base_dir}")
    print(f"  OS: {env.detected_os}")
    print(f"  Python Version: {env.python_version}")
    print(f"  User ID: {env.user_id}")
    
    print(f"\nResources:")
    print(f"  Available Memory: {env.available_memory / (1024**3):.1f} GB")
    print(f"  Disk Space: {env.disk_space / (1024**3):.1f} GB free")
    
    print(f"\nPermissions:")
    for perm, allowed in env.permissions.items():
        status = "✓" if allowed else "✗"
        print(f"  {status} {perm}")
    
    print(f"\nDetected Tools:")
    for tool_name, tool_info in detector.detected_tools.items():
        print(f"  • {tool_info['name']} ({tool_info['version']})")
    
    print(f"\nConstraints:")
    for key, value in env.constraints.items():
        print(f"  {key}: {value}")
    
    print(f"\nDirectories (will be created):")
    print(f"  Tools: {env.tools_dir}")
    print(f"  Configs: {env.config_dir}")
    print(f"  Backups: {env.backups_dir}")
    print(f"  Logs: {env.logs_dir}")
    print(f"  Profiles: {env.profiles_dir}")
    
    print(f"\n{'='*60}")

if __name__ == "__main__":
    main()
