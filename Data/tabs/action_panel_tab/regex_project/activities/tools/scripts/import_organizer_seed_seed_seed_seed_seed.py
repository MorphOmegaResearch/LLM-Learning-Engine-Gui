#!/usr/bin/env python3  # [MARK:{ ID:N004 }]  # [MARK:{ ID:N004 }]  # [MARK:{ ID:N004 }]  # [MARK:{ ID:N004 }]  # [MARK:{ ID:N004 }]  # [MARK:{ ID:N004 }]
"""
Import Organization & Dependency Analysis Tool
Scans Python files to map import usage, suggests logical reorganizations,
and provides diff/snapshot/patch workflows with self-configuring backups.
"""

import os
import sys
import ast
import json
import argparse
import difflib
import shutil
import hashlib
import datetime
import inspect
import tempfile
import subprocess
import threading
import time
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional, Union
from collections import defaultdict, OrderedDict
import logging

# #[EVENT] Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(
            f"/tmp/import_organizer_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# #[EVENT] Configuration Manager with Versioning
class ConfigManager:
    """Manages tool configuration with versioning and backup"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or Path.home() / '.config' / 'import_organizer.json'
        # Tool version - must be set before _load_config() which references it
        self.version = "1.0.0"
        self.config = self._load_config()
        self.backup_dir = Path.home() / '.import_organizer_backups'
        self.backup_dir.mkdir(exist_ok=True)
        
    def _load_config(self) -> Dict:
        """Load or create configuration"""
        default_config = {
            'version': self.version,
            'created': datetime.datetime.now().isoformat(),
            'last_modified': datetime.datetime.now().isoformat(),
            'settings': {
                'auto_backup': True,
                'max_backups': 10,
                'snapshot_dir': 'import_snaps',
                'depth_limit': 3,
                'analyze_unused': True,
                'suggest_grouping': True,
                'preserve_comments': True,
                'sort_imports': True,
                'sort_order': ['stdlib', 'third_party', 'first_party', 'local'],
            },
            'history': [],
            'ignored_imports': ['pdb', 'ipdb', 'debugpy', '__future__'],
            'known_aliases': {
                'np': 'numpy',
                'pd': 'pandas',
                'plt': 'matplotlib.pyplot',
                'tf': 'tensorflow',
                'torch': 'torch',
            },
            'project_patterns': {},
        }
        
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                
                # Merge with defaults for any missing keys
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                
                return config
            else:
                return default_config
        except Exception as e:
            logger.error(f"[EVENT] Failed to load config: {e}")
            return default_config
    
    def save_config(self):
        """Save current configuration"""
        try:
            self.config['last_modified'] = datetime.datetime.now().isoformat()
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create backup of current config
            if self.config['settings']['auto_backup']:
                self._backup_config()
            
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            
            logger.info(f"[EVENT] Configuration saved to {self.config_path}")
        except Exception as e:
            logger.error(f"[EVENT] Failed to save config: {e}")
    
    def _backup_config(self):
        """Create timestamped backup of configuration"""
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = self.backup_dir / f"config_backup_{timestamp}.json"
        
        try:
            shutil.copy2(self.config_path, backup_file)
            
            # Clean old backups
            backups = sorted(self.backup_dir.glob('config_backup_*.json'))
            max_backups = self.config['settings']['max_backups']
            
            while len(backups) > max_backups:
                backups[0].unlink()
                backups = backups[1:]
            
            logger.info(f"[EVENT] Config backup created: {backup_file}")
        except Exception as e:
            logger.error(f"[EVENT] Failed to create config backup: {e}")
    
    def detect_changes(self) -> List[str]:
        """Detect if tool files have changed since last run"""
        changes = []
        
        # Get current script path
        current_script = Path(__file__).resolve()
        
        # Check if we have a backup
        seed_file = current_script.parent / f"{current_script.stem}_seed.py"
        
        if seed_file.exists():
            # Compare with current file
            current_hash = self._file_hash(current_script)
            seed_hash = self._file_hash(seed_file)
            
            if current_hash != seed_hash:
                changes.append(f"Main script changed (current: {current_hash[:8]}, seed: {seed_hash[:8]})")
        
        # Check for other important files
        expected_files = ['config.json', 'launch.sh', 'tools/']
        for file_pattern in expected_files:
            file_path = current_script.parent / file_pattern
            if file_pattern.endswith('/'):
                if not file_path.exists():
                    changes.append(f"Missing directory: {file_pattern}")
            else:
                if not file_path.exists():
                    changes.append(f"Missing file: {file_pattern}")
        
        return changes
    
    def _file_hash(self, filepath: Path) -> str:
        """Calculate file hash"""
        try:
            with open(filepath, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except:
            return "0" * 32
    
    def setup_tool_structure(self, tool_dir: Path = None):
        """Setup tool directory structure"""
        if tool_dir is None:
            tool_dir = Path(__file__).parent
        
        # Create necessary directories
        dirs = ['import_snaps', 'tools', 'backups', 'logs']
        for dir_name in dirs:
            (tool_dir / dir_name).mkdir(exist_ok=True)
        
        # Create launch script
        launch_script = tool_dir / 'launch.sh'
        launch_content = f'''#!/bin/bash
# Import Organizer Launch Script
# Generated: {datetime.datetime.now().isoformat()}

SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
cd "$SCRIPT_DIR"

# Check Python version
if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 7) else 1)"; then
    echo "Error: Python 3.7+ required"
    exit 1
fi

# Run the organizer
python3 "{Path(__file__).name}" "$@"

# Return exit code
exit $?
'''
        
        with open(launch_script, 'w') as f:
            f.write(launch_content)
        
        launch_script.chmod(0o755)
        
        # Create backup of current script as seed
        seed_file = tool_dir / f"{Path(__file__).stem}_seed.py"
        shutil.copy2(__file__, seed_file)
        
        logger.info(f"[EVENT] Tool structure setup in {tool_dir}")
        return tool_dir

# #[EVENT] Import Scanner & Usage Mapper
class ImportScanner:
    """Scans Python files to map import usage"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.imports_map = defaultdict(dict)
        self.usage_map = defaultdict(dict)
        self.file_imports = defaultdict(dict)
        
    def scan_file(self, file_path: Path, depth: int = 0) -> Dict:
        """Scan a single Python file for imports and their usage"""
        logger.info(f"[EVENT] Scanning file: {file_path} (depth: {depth})")
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            scanner = ImportUsageVisitor(file_path, content, depth)
            scanner.visit(tree)
            
            # Store results
            self.imports_map[str(file_path)] = scanner.imports
            self.usage_map[str(file_path)] = scanner.usage
            self.file_imports[str(file_path)] = {
                'imports': scanner.imports,
                'usage': scanner.usage,
                'unused': scanner.unused_imports,
                'total_lines': len(content.split('\n')),
                'scan_time': datetime.datetime.now().isoformat(),
                'depth': depth
            }
            
            # Scan imported files if within depth limit
            if depth < self.config.config['settings']['depth_limit']:
                self._scan_imported_files(scanner.imports, file_path.parent, depth + 1)
            
            return self.file_imports[str(file_path)]
            
        except SyntaxError as e:
            logger.error(f"[EVENT] Syntax error in {file_path}: {e}")
            return {'error': str(e), 'file': str(file_path)}
        except Exception as e:
            logger.error(f"[EVENT] Failed to scan {file_path}: {e}")
            return {'error': str(e), 'file': str(file_path)}
    
    def _scan_imported_files(self, imports: Dict, base_dir: Path, depth: int):
        """Recursively scan imported files"""
        for import_info in imports.get('imports', []) + imports.get('from_imports', []):
            module_name = import_info.get('module', '')
            if not module_name or module_name.startswith(('_', '.')) or module_name in ['sys', 'os']:
                continue
            
            # Try to find the module file
            module_file = self._find_module_file(module_name, base_dir)
            if module_file and module_file.exists() and str(module_file) not in self.imports_map:
                self.scan_file(module_file, depth)
    
    def _find_module_file(self, module_name: str, base_dir: Path) -> Optional[Path]:
        """Find the Python file for a module"""
        # Convert module name to file path
        module_path = module_name.replace('.', '/')
        
        # Check common locations
        search_paths = [
            base_dir / f"{module_path}.py",
            base_dir / module_path / "__init__.py",
            Path.cwd() / f"{module_path}.py",
            Path.cwd() / module_path / "__init__.py",
            Path(sys.executable).parent.parent / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages" / f"{module_path}.py",
            Path(sys.executable).parent.parent / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages" / module_path / "__init__.py",
        ]
        
        for path in search_paths:
            if path.exists():
                return path
        
        return None
    
    def scan_directory(self, dir_path: Path, depth: int = 0, max_depth: int = 3) -> Dict:
        """Scan all Python files in a directory recursively"""
        logger.info(f"[EVENT] Scanning directory: {dir_path} (max depth: {max_depth})")
        
        results = {
            'directory': str(dir_path),
            'scanned_files': [],
            'total_imports': 0,
            'unique_modules': set(),
            'scan_time': datetime.datetime.now().isoformat(),
            'depth': depth
        }
        
        if depth >= max_depth:
            return results
        
        # Scan all Python files
        for py_file in dir_path.rglob('*.py'):
            if py_file.is_file():
                file_result = self.scan_file(py_file, depth)
                results['scanned_files'].append(str(py_file.relative_to(dir_path)))
                
                if 'imports' in file_result:
                    results['total_imports'] += len(file_result['imports'].get('imports', [])) + len(file_result['imports'].get('from_imports', []))
                    for imp in file_result['imports'].get('imports', []):
                        results['unique_modules'].add(imp.get('module', ''))
                    for imp in file_result['imports'].get('from_imports', []):
                        results['unique_modules'].add(imp.get('module', ''))
        
        results['unique_modules'] = list(results['unique_modules'])
        return results

class ImportUsageVisitor(ast.NodeVisitor):
    """AST visitor to track import usage"""
    
    def __init__(self, file_path: Path, content: str, depth: int):
        self.file_path = file_path
        self.content = content
        self.depth = depth
        self.imports = {'imports': [], 'from_imports': []}
        self.usage = defaultdict(list)
        self.unused_imports = []
        self.defined_names = set()
        self.current_line = 0
        
    def visit_Import(self, node):
        """Process import statements"""
        for alias in node.names:
            self.imports['imports'].append({
                'module': alias.name,
                'alias': alias.asname,
                'line': node.lineno,
                'col': node.col_offset,
                'names': [alias.name]
            })
            
            # Track the imported name
            imported_name = alias.asname if alias.asname else alias.name.split('.')[0]
            self.defined_names.add(imported_name)
        
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        """Process from ... import statements"""
        module = node.module or ""
        
        imported_names = []
        for alias in node.names:
            imported_names.append({
                'name': alias.name,
                'alias': alias.asname
            })
            
            # Track the imported name
            imported_name = alias.asname if alias.asname else alias.name
            self.defined_names.add(imported_name)
        
        self.imports['from_imports'].append({
            'module': module,
            'names': imported_names,
            'line': node.lineno,
            'col': node.col_offset,
            'level': node.level
        })
        
        self.generic_visit(node)
    
    def visit_Name(self, node):
        """Track usage of names"""
        if isinstance(node.ctx, ast.Load):  # Only track when name is loaded (used)
            self.usage[node.id].append({
                'line': node.lineno,
                'col': node.col_offset,
                'context': self._get_context(node)
            })
        
        self.generic_visit(node)
    
    def visit_Attribute(self, node):
        """Track usage of attributes (module.attribute)"""
        # Try to get the base name (e.g., 'os' in 'os.path')
        try:
            # Walk up the attribute chain
            parts = []
            current = node
            while isinstance(current, ast.Attribute):
                parts.insert(0, current.attr)
                current = current.value
            
            if isinstance(current, ast.Name):
                base_name = current.id
                full_name = '.'.join([base_name] + parts)
                
                self.usage[base_name].append({
                    'line': node.lineno,
                    'col': node.col_offset,
                    'attribute': full_name,
                    'context': self._get_context(node)
                })
        except:
            pass
        
        self.generic_visit(node)
    
    def _get_context(self, node) -> str:
        """Get context around a node"""
        lines = self.content.split('\n')
        line_num = node.lineno - 1
        
        if 0 <= line_num < len(lines):
            line = lines[line_num]
            col = node.col_offset
            
            # Get surrounding context (50 chars before/after)
            start = max(0, col - 50)
            end = min(len(line), col + 50)
            
            context = line[start:end]
            if start > 0:
                context = '...' + context
            if end < len(line):
                context = context + '...'
            
            return context
        
        return ""
    
    def finalize(self):
        """Finalize analysis and identify unused imports"""
        # Check which imports are actually used
        used_imports = set()
        
        for import_info in self.imports['imports']:
            module = import_info['module']
            alias = import_info['alias']
            base_name = alias if alias else module.split('.')[0]
            
            if base_name in self.usage:
                used_imports.add(f"{module} as {alias}" if alias else module)
            else:
                self.unused_imports.append({
                    'type': 'import',
                    'module': module,
                    'alias': alias,
                    'line': import_info['line']
                })
        
        for import_info in self.imports['from_imports']:
            module = import_info['module']
            for name_info in import_info['names']:
                name = name_info['name']
                alias = name_info['alias']
                imported_name = alias if alias else name
                
                if imported_name in self.usage:
                    used_imports.add(f"{module}.{name} as {alias}" if alias else f"{module}.{name}")
                else:
                    self.unused_imports.append({
                        'type': 'from_import',
                        'module': module,
                        'name': name,
                        'alias': alias,
                        'line': import_info['line']
                    })

# #[EVENT] Import Organizer & Suggestion Engine
class ImportOrganizer:
    """Organizes imports and suggests improvements"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.suggestions = []
        self.import_categories = {
            'stdlib': set(),
            'third_party': set(),
            'first_party': set(),
            'local': set()
        }
    
    def analyze_imports(self, imports_map: Dict) -> List[Dict]:
        """Analyze imports and generate suggestions"""
        logger.info("[EVENT] Analyzing imports for organization suggestions")
        
        suggestions = []
        
        for file_path, file_data in imports_map.items():
            file_suggestions = self._analyze_file_imports(file_path, file_data)
            suggestions.extend(file_suggestions)
        
        # Generate global suggestions
        global_suggestions = self._generate_global_suggestions(imports_map)
        suggestions.extend(global_suggestions)
        
        self.suggestions = suggestions
        return suggestions
    
    def _analyze_file_imports(self, file_path: str, file_data: Dict) -> List[Dict]:
        """Analyze imports for a single file"""
        suggestions = []
        imports = file_data.get('imports', {})
        usage = file_data.get('usage', {})
        unused = file_data.get('unused', [])
        
        # Suggestion 1: Remove unused imports
        if unused and self.config.config['settings']['analyze_unused']:
            suggestions.append({
                'file': file_path,
                'type': 'remove_unused',
                'description': f"Found {len(unused)} unused import(s)",
                'items': unused,
                'priority': 'high',
                'action': 'Remove unused imports',
                'confidence': 0.9
            })
        
        # Suggestion 2: Group imports
        if self.config.config['settings']['suggest_grouping']:
            grouping_suggestions = self._suggest_import_grouping(imports)
            if grouping_suggestions:
                suggestions.append({
                    'file': file_path,
                    'type': 'group_imports',
                    'description': "Imports should be grouped by category",
                    'items': grouping_suggestions,
                    'priority': 'medium',
                    'action': 'Group imports into categories (stdlib, third_party, first_party, local)',
                    'confidence': 0.8
                })
        
        # Suggestion 3: Sort imports
        if self.config.config['settings']['sort_imports']:
            sort_suggestions = self._suggest_import_sorting(imports)
            if sort_suggestions:
                suggestions.append({
                    'file': file_path,
                    'type': 'sort_imports',
                    'description': "Imports should be sorted alphabetically",
                    'items': sort_suggestions,
                    'priority': 'low',
                    'action': 'Sort imports alphabetically within each group',
                    'confidence': 0.7
                })
        
        # Suggestion 4: Consolidate imports
        consolidate_suggestions = self._suggest_import_consolidation(imports)
        if consolidate_suggestions:
            suggestions.append({
                'file': file_path,
                'type': 'consolidate_imports',
                'description': "Multiple imports from same module can be consolidated",
                'items': consolidate_suggestions,
                'priority': 'medium',
                'action': 'Consolidate imports from the same module',
                'confidence': 0.8
            })
        
        # Suggestion 5: Replace wildcard imports
        wildcard_suggestions = self._find_wildcard_imports(imports)
        if wildcard_suggestions:
            suggestions.append({
                'file': file_path,
                'type': 'replace_wildcard',
                'description': "Wildcard imports should be replaced with explicit imports",
                'items': wildcard_suggestions,
                'priority': 'high',
                'action': 'Replace * imports with explicit imports',
                'confidence': 0.9
            })
        
        return suggestions
    
    def _suggest_import_grouping(self, imports: Dict) -> List[Dict]:
        """Suggest grouping imports by category"""
        categories = defaultdict(list)
        
        # Categorize each import
        for imp in imports.get('imports', []):
            module = imp.get('module', '')
            category = self._categorize_module(module)
            categories[category].append(imp)
        
        for imp in imports.get('from_imports', []):
            module = imp.get('module', '')
            category = self._categorize_module(module)
            categories[category].append(imp)
        
        return [{'category': cat, 'imports': imps} for cat, imps in categories.items()]
    
    def _categorize_module(self, module: str) -> str:
        """Categorize a module"""
        # Standard library
        if module in sys.builtin_module_names or self._is_stdlib_module(module):
            return 'stdlib'
        
        # Third party (common packages)
        third_party_modules = ['numpy', 'pandas', 'tensorflow', 'torch', 'django', 
                              'flask', 'requests', 'matplotlib', 'scipy', 'sklearn']
        
        if any(module.startswith(tp) for tp in third_party_modules):
            return 'third_party'
        
        # Local imports (relative)
        if module.startswith('.') or module.startswith('..'):
            return 'local'
        
        # First party (project modules)
        return 'first_party'
    
    def _is_stdlib_module(self, module: str) -> bool:
        """Check if module is in standard library"""
        try:
            __import__(module)
            # Check if it's in standard library paths
            module_path = sys.modules[module].__file__ if module in sys.modules else None
            if module_path:
                stdlib_paths = [
                    Path(sys.base_prefix) / 'lib',
                    Path(sys.executable).parent.parent / 'lib'
                ]
                return any(str(Path(module_path).parent).startswith(str(p)) for p in stdlib_paths)
        except:
            pass
        
        return False
    
    def _suggest_import_sorting(self, imports: Dict) -> List[Dict]:
        """Suggest alphabetical sorting of imports"""
        import_lines = []
        
        for imp in imports.get('imports', []):
            module = imp.get('module', '')
            alias = imp.get('alias', '')
            line = imp.get('line', 0)
            
            if alias:
                import_lines.append((line, f"import {module} as {alias}"))
            else:
                import_lines.append((line, f"import {module}"))
        
        for imp in imports.get('from_imports', []):
            module = imp.get('module', '')
            names = imp.get('names', [])
            line = imp.get('line', 0)
            
            name_list = []
            for name_info in names:
                name = name_info['name']
                alias = name_info.get('alias', '')
                if alias:
                    name_list.append(f"{name} as {alias}")
                else:
                    name_list.append(name)
            
            import_lines.append((line, f"from {module} import {', '.join(name_list)}"))
        
        # Sort by import statement
        sorted_imports = sorted(import_lines, key=lambda x: x[1].lower())
        
        # Check if already sorted
        current_order = [line for _, line in import_lines]
        suggested_order = [line for _, line in sorted_imports]
        
        if current_order != suggested_order:
            return [{'current': current_order, 'suggested': suggested_order}]
        
        return []
    
    def _suggest_import_consolidation(self, imports: Dict) -> List[Dict]:
        """Suggest consolidating imports from same module"""
        module_imports = defaultdict(list)
        
        for imp in imports.get('imports', []):
            module = imp.get('module', '')
            if module:
                module_imports[module].append(imp)
        
        for imp in imports.get('from_imports', []):
            module = imp.get('module', '')
            if module:
                module_imports[module].append(imp)
        
        consolidations = []
        for module, imps in module_imports.items():
            if len(imps) > 1:
                consolidations.append({
                    'module': module,
                    'imports': imps,
                    'count': len(imps)
                })
        
        return consolidations
    
    def _find_wildcard_imports(self, imports: Dict) -> List[Dict]:
        """Find wildcard (*) imports"""
        wildcards = []
        
        for imp in imports.get('from_imports', []):
            names = imp.get('names', [])
            for name_info in names:
                if name_info['name'] == '*':
                    wildcards.append({
                        'module': imp.get('module', ''),
                        'line': imp.get('line', 0)
                    })
        
        return wildcards
    
    def _generate_global_suggestions(self, imports_map: Dict) -> List[Dict]:
        """Generate suggestions across all files"""
        suggestions = []
        
        # Analyze import patterns across files
        module_usage = defaultdict(set)
        for file_path, file_data in imports_map.items():
            usage = file_data.get('usage', {})
            for name, usages in usage.items():
                module_usage[name].add(file_path)
        
        # Suggestion: Commonly used modules that should be imported at package level
        common_modules = {}
        for name, files in module_usage.items():
            if len(files) > 3:  # Used in more than 3 files
                common_modules[name] = files
        
        if common_modules:
            suggestions.append({
                'type': 'global_import',
                'description': f"Found {len(common_modules)} modules used across multiple files",
                'items': list(common_modules.items())[:10],  # Top 10
                'priority': 'medium',
                'action': 'Consider adding common imports to __init__.py or shared module',
                'confidence': 0.7
            })
        
        return suggestions

# #[EVENT] Diff & Patch Generator
class DiffPatchGenerator:
    """Generates diffs and patches for import reorganization"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.snapshots_dir = Path(config.config['settings']['snapshot_dir'])
        self.snapshots_dir.mkdir(exist_ok=True)
    
    def create_snapshot(self, file_path: Path, content: str, session_id: str) -> str:
        """Create a snapshot of file before changes"""
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        snapshot_name = f"{file_path.stem}_{timestamp}_{session_id}.py"
        snapshot_path = self.snapshots_dir / snapshot_name
        
        with open(snapshot_path, 'w') as f:
            f.write(content)
        
        logger.info(f"[EVENT] Snapshot created: {snapshot_path}")
        return str(snapshot_path)
    
    def generate_diff(self, original: str, modified: str, file_path: Path) -> str:
        """Generate unified diff between original and modified content"""
        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            original_lines, modified_lines,
            fromfile=f"a/{file_path.name}",
            tofile=f"b/{file_path.name}",
            lineterm=''
        )
        
        return '\n'.join(diff)
    
    def generate_patch(self, diffs: List[Dict], session_id: str) -> str:
        """Generate patch file from diffs"""
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        patch_file = self.snapshots_dir / f"patch_{session_id}_{timestamp}.diff"
        
        patch_content = [
            f"# Import Organization Patch",
            f"# Session: {session_id}",
            f"# Generated: {datetime.datetime.now().isoformat()}",
            f"# Files: {len(diffs)}",
            ""
        ]
        
        for diff in diffs:
            patch_content.append(f"# File: {diff['file']}")
            patch_content.append(diff['diff'])
            patch_content.append("")
        
        patch_text = '\n'.join(patch_content)
        
        with open(patch_file, 'w') as f:
            f.write(patch_text)
        
        logger.info(f"[EVENT] Patch generated: {patch_file}")
        return str(patch_file)
    
    def apply_patch(self, patch_file: Path, dry_run: bool = True) -> Dict:
        """Apply patch to files"""
        results = {'applied': [], 'failed': [], 'dry_run': dry_run}
        
        try:
            with open(patch_file, 'r') as f:
                patch_content = f.read()
            
            # Parse patch content (simplified - in production use patch command)
            # For now, we'll just simulate
            file_patterns = re.findall(r'# File: (.*)', patch_content)
            
            for file_pattern in file_patterns:
                file_path = Path(file_pattern)
                if file_path.exists():
                    if not dry_run:
                        # Actually apply patch
                        # This is a placeholder - in reality, use patch command
                        results['applied'].append(str(file_path))
                    else:
                        results['applied'].append(f"[DRY RUN] {file_path}")
                else:
                    results['failed'].append(str(file_path))
            
        except Exception as e:
            logger.error(f"[EVENT] Failed to apply patch: {e}")
            results['error'] = str(e)
        
        return results

# #[EVENT] File Processor with Backup Logic
class FileProcessor:
    """Processes files with backup and modification capabilities"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.backup_dir = Path('backups')
        self.backup_dir.mkdir(exist_ok=True)
    
    def backup_file(self, file_path: Path) -> str:
        """Create backup of file"""
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{file_path.stem}_{timestamp}_backup.py"
        backup_path = self.backup_dir / backup_name
        
        shutil.copy2(file_path, backup_path)
        logger.info(f"[EVENT] Backup created: {backup_path}")
        
        return str(backup_path)
    
    def modify_imports(self, file_path: Path, suggestions: List[Dict]) -> Tuple[str, List[Dict]]:
        """Modify file imports based on suggestions"""
        try:
            with open(file_path, 'r') as f:
                original_content = f.read()
            
            lines = original_content.split('\n')
            modifications = []
            
            # Process each suggestion
            for suggestion in suggestions:
                if suggestion['file'] != str(file_path):
                    continue
                
                if suggestion['type'] == 'remove_unused':
                    mods = self._remove_unused_imports(lines, suggestion['items'])
                    modifications.extend(mods)
                elif suggestion['type'] == 'group_imports':
                    mods = self._group_imports(lines, suggestion['items'])
                    modifications.extend(mods)
                elif suggestion['type'] == 'sort_imports':
                    mods = self._sort_imports(lines, suggestion['items'])
                    modifications.extend(mods)
                elif suggestion['type'] == 'consolidate_imports':
                    mods = self._consolidate_imports(lines, suggestion['items'])
                    modifications.extend(mods)
                elif suggestion['type'] == 'replace_wildcard':
                    mods = self._replace_wildcard_imports(lines, suggestion['items'])
                    modifications.extend(mods)
            
            # Apply modifications
            if modifications:
                lines = self._apply_modifications(lines, modifications)
            
            modified_content = '\n'.join(lines)
            
            return modified_content, modifications
            
        except Exception as e:
            logger.error(f"[EVENT] Failed to modify {file_path}: {e}")
            return original_content, []
    
    def _remove_unused_imports(self, lines: List[str], unused_items: List[Dict]) -> List[Dict]:
        """Remove unused imports from lines"""
        modifications = []
        
        for item in unused_items:
            line_num = item.get('line', 0) - 1  # Convert to 0-indexed
            
            if 0 <= line_num < len(lines):
                line = lines[line_num]
                
                # Mark for removal
                modifications.append({
                    'type': 'remove_line',
                    'line': line_num,
                    'original': line,
                    'reason': f"Unused import: {item}"
                })
        
        return modifications
    
    def _group_imports(self, lines: List[str], grouping_items: List[Dict]) -> List[Dict]:
        """Group imports by category"""
        modifications = []
        
        # Find all import lines
        import_lines = []
        for i, line in enumerate(lines):
            if line.strip().startswith(('import ', 'from ')):
                import_lines.append((i, line))
        
        if not import_lines:
            return modifications
        
        # Group by category
        categories = defaultdict(list)
        for line_num, line in import_lines:
            category = self._categorize_import_line(line)
            categories[category].append((line_num, line))
        
        # Check if already grouped
        current_order = []
        for line_num, line in import_lines:
            category = self._categorize_import_line(line)
            current_order.append(category)
        
        # Check if grouping needed
        unique_categories = []
        for cat in current_order:
            if cat not in unique_categories:
                unique_categories.append(cat)
        
        if len(unique_categories) <= 1:
            return modifications  # Already grouped
        
        # Generate new import order
        category_order = self.config.config['settings']['sort_order']
        new_imports = []
        
        for category in category_order:
            if category in categories:
                new_imports.extend(categories[category])
        
        # Create modification to replace imports
        modifications.append({
            'type': 'replace_imports',
            'lines': import_lines,
            'new_imports': new_imports,
            'reason': 'Group imports by category'
        })
        
        return modifications
    
    def _categorize_import_line(self, line: str) -> str:
        """Categorize an import line"""
        # Simple categorization based on common patterns
        if 'import ' in line:
            module = line.split('import ')[1].split()[0]
            
            # Check for standard library
            stdlib_modules = ['os', 'sys', 'json', 'datetime', 're', 'math', 'collections']
            if any(module.startswith(m) for m in stdlib_modules):
                return 'stdlib'
            
            # Check for third party
            third_party = ['numpy', 'pandas', 'tensorflow', 'torch', 'requests']
            if any(module.startswith(tp) for tp in third_party):
                return 'third_party'
            
            return 'first_party'
        
        return 'unknown'
    
    def _sort_imports(self, lines: List[str], sort_items: List[Dict]) -> List[Dict]:
        """Sort imports alphabetically"""
        # This would be implemented based on the sorting suggestions
        return []
    
    def _consolidate_imports(self, lines: List[str], consolidate_items: List[Dict]) -> List[Dict]:
        """Consolidate imports from same module"""
        return []
    
    def _replace_wildcard_imports(self, lines: List[str], wildcard_items: List[Dict]) -> List[Dict]:
        """Replace wildcard imports"""
        return []
    
    def _apply_modifications(self, lines: List[str], modifications: List[Dict]) -> List[str]:
        """Apply modifications to lines"""
        # Sort modifications by line number in reverse order (so deletions don't affect other line numbers)
        modifications.sort(key=lambda x: x.get('line', 0), reverse=True)
        
        for mod in modifications:
            if mod['type'] == 'remove_line':
                line_num = mod['line']
                if 0 <= line_num < len(lines):
                    del lines[line_num]
            
            elif mod['type'] == 'replace_imports':
                # Remove old imports
                for line_num, _ in sorted(mod['lines'], key=lambda x: x[0], reverse=True):
                    if 0 <= line_num < len(lines):
                        del lines[line_num]
                
                # Add new imports
                new_lines = [line for _, line in mod['new_imports']]
                
                # Find where to insert (after shebang and encoding, before other code)
                insert_pos = 0
                for i, line in enumerate(lines):
                    if not line.strip().startswith('#') and line.strip() != '':
                        insert_pos = i
                        break
                
                # Insert new imports
                for i, new_line in enumerate(new_lines):
                    lines.insert(insert_pos + i, new_line)
        
        return lines

# #[EVENT] Main Application
class ImportOrganizerTool:
    """Main import organization tool"""
    
    def __init__(self):
        self.config = ConfigManager()
        self.scanner = ImportScanner(self.config)
        self.organizer = ImportOrganizer(self.config)
        self.diff_gen = DiffPatchGenerator(self.config)
        self.processor = FileProcessor(self.config)
        self.session_id = self._generate_session_id()
        
        # Setup tool structure
        self.tool_dir = Path(__file__).parent
        self.config.setup_tool_structure(self.tool_dir)
        
    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        random_hash = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
        return f"{timestamp}_{random_hash}"
    
    def run(self):
        """Main entry point"""
        parser = self._create_argparse()
        args = parser.parse_args()
        
        # Check for tool changes
        changes = self.config.detect_changes()
        if changes:
            logger.warning(f"[EVENT] Tool changes detected: {changes}")
            if args.check:
                print("Tool changes detected:")
                for change in changes:
                    print(f"  - {change}")
                return
        
        # Set debug level
        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)
        
        # Execute command
        if hasattr(args, 'func'):
            args.func(args)
        else:
            parser.print_help()
    
    def _create_argparse(self):
        """Create command line argument parser"""
        parser = argparse.ArgumentParser(
            description='Import Organization Tool - Analyzes and reorganizes Python imports',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Scan a single file
  %(prog)s scan my_script.py
  
  # Scan directory with depth 2
  %(prog)s scan-dir /path/to/project --depth 2
  
  # Analyze imports and show suggestions
  %(prog)s analyze my_script.py --suggest
  
  # Generate diff between original and organized version
  %(prog)s diff my_script.py --session SESSION_ID
  
  # Create snapshot of current state
  %(prog)s snapshot my_script.py
  
  # Apply organization suggestions
  %(prog)s apply my_script.py --dry-run
  
  # Generate patch from suggestions
  %(prog)s patch --session SESSION_ID
  
Debugging:
  #[EVENT] markers show processing steps in logs
  Use --debug for verbose output
  Check /tmp/import_organizer_*.log for detailed logs
            """
        )
        
        subparsers = parser.add_subparsers(dest='command', help='Command')
        
        # Global arguments
        parser.add_argument('--debug', action='store_true', help='Enable debug output')
        parser.add_argument('--check', action='store_true', help='Check for tool changes')
        parser.add_argument('--version', action='version', 
                          version=f'Import Organizer {self.config.version}')
        
        # Scan command
        scan_parser = subparsers.add_parser('scan', help='Scan a Python file for imports')
        scan_parser.add_argument('file', help='Python file to scan')
        scan_parser.add_argument('--depth', type=int, default=1, 
                               help='Depth for scanning imported modules (default: 1)')
        scan_parser.add_argument('--output', help='Output scan results to file')
        scan_parser.set_defaults(func=self.handle_scan)
        
        # Scan directory command
        scan_dir_parser = subparsers.add_parser('scan-dir', help='Scan directory for imports')
        scan_dir_parser.add_argument('directory', help='Directory to scan')
        scan_dir_parser.add_argument('--depth', type=int, default=1,
                                   help='Depth for scanning (default: 1)')
        scan_dir_parser.add_argument('--max-depth', type=int, default=3,
                                   help='Maximum recursion depth (default: 3)')
        scan_dir_parser.add_argument('--output', help='Output scan results to file')
        scan_dir_parser.set_defaults(func=self.handle_scan_dir)
        
        # Analyze command
        analyze_parser = subparsers.add_parser('analyze', help='Analyze imports and suggest improvements')
        analyze_parser.add_argument('target', help='File or directory to analyze')
        analyze_parser.add_argument('--suggest', action='store_true',
                                  help='Show organization suggestions')
        analyze_parser.add_argument('--summary', action='store_true',
                                  help='Show summary only')
        analyze_parser.add_argument('--output', help='Output analysis to file')
        analyze_parser.set_defaults(func=self.handle_analyze)
        
        # Diff command
        diff_parser = subparsers.add_parser('diff', help='Generate diff between original and organized')
        diff_parser.add_argument('file', help='File to diff')
        diff_parser.add_argument('--session', help='Session ID for comparison')
        diff_parser.add_argument('--output', help='Output diff to file')
        diff_parser.set_defaults(func=self.handle_diff)
        
        # Snapshot command
        snapshot_parser = subparsers.add_parser('snapshot', help='Create snapshot of current state')
        snapshot_parser.add_argument('file', help='File to snapshot')
        snapshot_parser.add_argument('--name', help='Custom snapshot name')
        snapshot_parser.set_defaults(func=self.handle_snapshot)
        
        # Apply command
        apply_parser = subparsers.add_parser('apply', help='Apply organization suggestions')
        apply_parser.add_argument('file', help='File to organize')
        apply_parser.add_argument('--dry-run', action='store_true',
                                help='Show changes without applying')
        apply_parser.add_argument('--backup', action='store_true',
                                help='Create backup before applying')
        apply_parser.add_argument('--session', help='Use specific session suggestions')
        apply_parser.set_defaults(func=self.handle_apply)
        
        # Patch command
        patch_parser = subparsers.add_parser('patch', help='Generate or apply patch')
        patch_parser.add_argument('--session', help='Session ID for patch generation')
        patch_parser.add_argument('--apply', action='store_true',
                                help='Apply patch (use with caution)')
        patch_parser.add_argument('--patch-file', help='Patch file to apply')
        patch_parser.set_defaults(func=self.handle_patch)
        
        # View command
        view_parser = subparsers.add_parser('view', help='View scan/analysis results')
        view_parser.add_argument('--session', help='Session ID to view')
        view_parser.add_argument('--type', choices=['scan', 'analysis', 'diff', 'patch'],
                               default='scan', help='Type of data to view')
        view_parser.set_defaults(func=self.handle_view)
        
        # Config command
        config_parser = subparsers.add_parser('config', help='Manage configuration')
        config_parser.add_argument('--show', action='store_true',
                                 help='Show current configuration')
        config_parser.add_argument('--reset', action='store_true',
                                 help='Reset to default configuration')
        config_parser.add_argument('--set', nargs=2, metavar=('KEY', 'VALUE'),
                                 help='Set configuration value')
        config_parser.set_defaults(func=self.handle_config)
        
        return parser
    
    def handle_scan(self, args):
        """Handle scan command"""
        logger.info(f"[EVENT] Scanning file: {args.file}")
        
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: File not found: {args.file}")
            return
        
        result = self.scanner.scan_file(file_path, args.depth)
        
        # Save to file if requested
        if args.output:
            output_path = Path(args.output)
            with open(output_path, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"Scan results saved to: {output_path}")
        else:
            # Display summary
            self._display_scan_summary(result, file_path)
    
    def handle_scan_dir(self, args):
        """Handle scan-dir command"""
        logger.info(f"[EVENT] Scanning directory: {args.directory}")
        
        dir_path = Path(args.directory)
        if not dir_path.exists():
            print(f"Error: Directory not found: {args.directory}")
            return
        
        result = self.scanner.scan_directory(dir_path, depth=args.depth, max_depth=args.max_depth)
        
        # Save to file if requested
        if args.output:
            output_path = Path(args.output)
            with open(output_path, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"Directory scan saved to: {output_path}")
        else:
            # Display summary
            self._display_directory_summary(result)
    
    def handle_analyze(self, args):
        """Handle analyze command"""
        logger.info(f"[EVENT] Analyzing: {args.target}")
        
        target_path = Path(args.target)
        if not target_path.exists():
            print(f"Error: Target not found: {args.target}")
            return
        
        # Scan first
        if target_path.is_file():
            scan_result = self.scanner.scan_file(target_path)
            imports_map = {str(target_path): scan_result}
        else:
            scan_result = self.scanner.scan_directory(target_path)
            imports_map = self.scanner.file_imports
        
        # Analyze imports
        suggestions = self.organizer.analyze_imports(imports_map)
        
        # Save to file if requested
        if args.output:
            output_path = Path(args.output)
            analysis_data = {
                'session_id': self.session_id,
                'target': str(target_path),
                'scan_results': scan_result,
                'suggestions': suggestions,
                'timestamp': datetime.datetime.now().isoformat()
            }
            
            with open(output_path, 'w') as f:
                json.dump(analysis_data, f, indent=2)
            print(f"Analysis saved to: {output_path}")
        
        # Display results
        if args.summary:
            self._display_analysis_summary(scan_result, suggestions)
        elif args.suggest:
            self._display_suggestions(suggestions)
        else:
            self._display_analysis_summary(scan_result, suggestions)
    
    def handle_diff(self, args):
        """Handle diff command"""
        logger.info(f"[EVENT] Generating diff for: {args.file}")
        
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: File not found: {args.file}")
            return
        
        # Read original file
        with open(file_path, 'r') as f:
            original_content = f.read()
        
        # Scan and analyze to get suggestions
        scan_result = self.scanner.scan_file(file_path)
        suggestions = self.organizer.analyze_imports({str(file_path): scan_result})
        
        # Apply suggestions to generate modified content
        modified_content, modifications = self.processor.modify_imports(file_path, suggestions)
        
        # Generate diff
        diff = self.diff_gen.generate_diff(original_content, modified_content, file_path)
        
        # Save to file if requested
        if args.output:
            output_path = Path(args.output)
            with open(output_path, 'w') as f:
                f.write(diff)
            print(f"Diff saved to: {output_path}")
        else:
            print(diff)
    
    def handle_snapshot(self, args):
        """Handle snapshot command"""
        logger.info(f"[EVENT] Creating snapshot for: {args.file}")
        
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: File not found: {args.file}")
            return
        
        # Read file content
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Create snapshot
        snapshot_name = args.name or f"{file_path.stem}_snapshot"
        snapshot_path = self.diff_gen.create_snapshot(file_path, content, snapshot_name)
        
        print(f"Snapshot created: {snapshot_path}")
    
    def handle_apply(self, args):
        """Handle apply command"""
        logger.info(f"[EVENT] Applying suggestions to: {args.file}")
        
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: File not found: {args.file}")
            return
        
        # Create backup if requested
        if args.backup:
            backup_path = self.processor.backup_file(file_path)
            print(f"Backup created: {backup_path}")
        
        # Scan and analyze
        scan_result = self.scanner.scan_file(file_path)
        suggestions = self.organizer.analyze_imports({str(file_path): scan_result})
        
        # Read original
        with open(file_path, 'r') as f:
            original_content = f.read()
        
        # Apply modifications
        modified_content, modifications = self.processor.modify_imports(file_path, suggestions)
        
        if args.dry_run:
            # Show what would change
            print("DRY RUN - No changes will be applied")
            print(f"File: {file_path}")
            print(f"Modifications: {len(modifications)}")
            
            if modifications:
                print("\nChanges:")
                for mod in modifications:
                    print(f"  - {mod.get('type', 'unknown')}: {mod.get('reason', '')}")
            
            # Show diff
            diff = self.diff_gen.generate_diff(original_content, modified_content, file_path)
            print("\nDiff:")
            print(diff)
        else:
            # Apply changes
            with open(file_path, 'w') as f:
                f.write(modified_content)
            
            print(f"Applied {len(modifications)} modifications to {file_path}")
    
    def handle_patch(self, args):
        """Handle patch command"""
        if args.patch_file:
            # Apply existing patch
            patch_path = Path(args.patch_file)
            if not patch_path.exists():
                print(f"Error: Patch file not found: {args.patch_file}")
                return
            
            result = self.diff_gen.apply_patch(patch_path, dry_run=not args.apply)
            
            print(f"Patch {'applied' if args.apply else 'simulated'} for {len(result['applied'])} files")
            if result['applied']:
                print("Applied to:")
                for file in result['applied']:
                    print(f"  - {file}")
            if result.get('failed'):
                print("Failed:")
                for file in result['failed']:
                    print(f"  - {file}")
        elif args.session:
            # Generate patch from session
            # This would load session data and generate patch
            print(f"Generating patch for session: {args.session}")
            # Implementation would go here
        else:
            print("Error: Either --patch-file or --session required")
    
    def handle_view(self, args):
        """Handle view command"""
        # This would load and display saved session data
        print(f"Viewing {args.type} data for session: {args.session or 'latest'}")
        # Implementation would go here
    
    def handle_config(self, args):
        """Handle config command"""
        if args.show:
            print(json.dumps(self.config.config, indent=2))
        elif args.reset:
            self.config.config = self.config._load_config()  # Reload defaults
            self.config.save_config()
            print("Configuration reset to defaults")
        elif args.set:
            key, value = args.set
            # Parse value (could be JSON)
            try:
                value = json.loads(value)
            except:
                pass
            
            # Update config
            keys = key.split('.')
            config_ref = self.config.config
            for k in keys[:-1]:
                if k not in config_ref:
                    config_ref[k] = {}
                config_ref = config_ref[k]
            config_ref[keys[-1]] = value
            
            self.config.save_config()
            print(f"Set {key} = {value}")
    
    def _display_scan_summary(self, result: Dict, file_path: Path):
        """Display scan summary"""
        print(f"\n{'='*60}")
        print(f"IMPORT SCAN SUMMARY")
        print(f"{'='*60}")
        print(f"File: {file_path}")
        
        if 'error' in result:
            print(f"Error: {result['error']}")
            return
        
        imports = result.get('imports', {})
        usage = result.get('usage', {})
        unused = result.get('unused', [])
        
        print(f"\nImports: {len(imports.get('imports', []))} direct, {len(imports.get('from_imports', []))} from imports")
        print(f"Unique modules used: {len(usage)}")
        print(f"Unused imports: {len(unused)}")
        
        if unused:
            print(f"\nUnused imports:")
            for imp in unused[:5]:  # Show top 5
                if imp['type'] == 'import':
                    print(f"  import {imp['module']} (line {imp['line']})")
                else:
                    print(f"  from {imp['module']} import {imp['name']} (line {imp['line']})")
            
            if len(unused) > 5:
                print(f"  ... and {len(unused) - 5} more")
        
        print(f"\n{'='*60}")
    
    def _display_directory_summary(self, result: Dict):
        """Display directory scan summary"""
        print(f"\n{'='*60}")
        print(f"DIRECTORY SCAN SUMMARY")
        print(f"{'='*60}")
        print(f"Directory: {result['directory']}")
        print(f"Files scanned: {len(result['scanned_files'])}")
        print(f"Total imports: {result['total_imports']}")
        print(f"Unique modules: {len(result['unique_modules'])}")
        
        if result['unique_modules']:
            print(f"\nTop modules:")
            for module in sorted(result['unique_modules'])[:10]:
                print(f"  {module}")
        
        print(f"\n{'='*60}")
    
    def _display_analysis_summary(self, scan_result: Dict, suggestions: List[Dict]):
        """Display analysis summary"""
        print(f"\n{'='*60}")
        print(f"ANALYSIS SUMMARY")
        print(f"{'='*60}")
        print(f"Session ID: {self.session_id}")
        print(f"Total suggestions: {len(suggestions)}")
        
        # Group suggestions by type
        by_type = defaultdict(list)
        for suggestion in suggestions:
            by_type[suggestion['type']].append(suggestion)
        
        print(f"\nSuggestions by type:")
        for type_name, items in by_type.items():
            print(f"  {type_name}: {len(items)}")
        
        # Show high priority suggestions
        high_priority = [s for s in suggestions if s.get('priority') == 'high']
        if high_priority:
            print(f"\nHigh priority suggestions:")
            for suggestion in high_priority[:3]:
                print(f"  - {suggestion['description']}")
        
        print(f"\n{'='*60}")
    
    def _display_suggestions(self, suggestions: List[Dict]):
        """Display detailed suggestions"""
        print(f"\n{'='*60}")
        print(f"ORGANIZATION SUGGESTIONS")
        print(f"{'='*60}")
        
        if not suggestions:
            print("No suggestions found.")
            return
        
        # Group by file
        by_file = defaultdict(list)
        for suggestion in suggestions:
            by_file[suggestion['file']].append(suggestion)
        
        for file_path, file_suggestions in by_file.items():
            print(f"\nFile: {file_path}")
            print(f"Suggestions: {len(file_suggestions)}")
            
            for i, suggestion in enumerate(file_suggestions, 1):
                print(f"\n  {i}. [{suggestion['priority'].upper()}] {suggestion['type']}")
                print(f"     Description: {suggestion['description']}")
                print(f"     Action: {suggestion['action']}")
                print(f"     Confidence: {suggestion['confidence']:.0%}")
        
        print(f"\n{'='*60}")

# #[EVENT] Main execution
def main():
    """Main entry point"""
    logger.info("[EVENT] Starting Import Organization Tool")
    logger.info(f"[EVENT] Version: {ConfigManager().version}")
    
    try:
        tool = ImportOrganizerTool()
        tool.run()
        logger.info("[EVENT] Tool execution completed")
    except KeyboardInterrupt:
        logger.info("[EVENT] Interrupted by user")
        print("\nOperation cancelled by user.")
    except Exception as e:
        logger.error(f"[EVENT] Fatal error: {e}", exc_info=True)
        print(f"\nError: {e}")
        print("\nCheck log file for details.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
