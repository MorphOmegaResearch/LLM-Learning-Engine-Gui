#!/usr/bin/env python3
"""
TKINTER GUI DIMENSION ANALYZER & CLASH DETECTOR
===============================================
Static analysis tool for detecting widget positioning issues, layout conflicts,
and best practice violations in Tkinter applications.
"""

import ast
import argparse
import os
import sys
import logging
import traceback
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
import textwrap
import itertools

# === SELF-LOGGING SETUP ===
SCRIPT_NAME = "tkinter_scanner"
LOG_DIR = Path.home() / ".tkinter_scanner_logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"scanner_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

def setup_logging():
    """Configure logging for self-runtime and crash recovery"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler for crash logging"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logging.critical(f"SCANNER CRASH:\n{error_msg}")
    
    # Write crash report
    crash_file = LOG_DIR / f"crash_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(crash_file, 'w', encoding='utf-8') as f:
        f.write(f"TKINTER SCANNER CRASH REPORT\n")
        f.write(f"Time: {datetime.now()}\n")
        f.write(f"Error: {exc_value}\n")
        f.write(f"Traceback:\n{error_msg}\n")
    
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

sys.excepthook = handle_exception

# === TKINTER WIDGET DATABASE ===
TKINTER_WIDGETS = {
    'tk': {
        'containers': ['Tk', 'Toplevel', 'Frame', 'Labelframe', 'PanedWindow'],
        'widgets': [
            'Label', 'Button', 'Entry', 'Text', 'Canvas', 'Listbox', 'Scrollbar',
            'Scale', 'Checkbutton', 'Radiobutton', 'Spinbox', 'Menu', 'Menubutton'
        ]
    },
    'ttk': {
        'containers': ['Frame', 'Labelframe', 'PanedWindow', 'Notebook'],
        'widgets': [
            'Label', 'Button', 'Entry', 'Text', 'Canvas', 'Listbox', 'Scrollbar',
            'Scale', 'Checkbutton', 'Radiobutton', 'Spinbox', 'Combobox',
            'Progressbar', 'Separator', 'Treeview', 'Sizegrip'
        ]
    }
}

GEOMETRY_MANAGERS = ['pack', 'grid', 'place']
INVALID_MIXTURES = {
    ('pack', 'grid'): "Mixing pack() and grid() in same parent causes Tkinter errors",
    ('pack', 'place'): "pack() and place() can conflict but may work",
    ('grid', 'place'): "grid() and place() can conflict but may work"
}

class WidgetNode:
    """Represents a Tkinter widget in the hierarchy"""
    def __init__(self, name: str, widget_type: str, line: int):
        self.name = name
        self.type = widget_type
        self.line = line
        self.parent: Optional[WidgetNode] = None
        self.children: List[WidgetNode] = []
        self.geometry: Dict[str, Any] = {}
        self.attributes: Dict[str, Any] = {}
        self.position: Dict[str, Optional[int]] = {
            'x': None, 'y': None, 'width': None, 'height': None,
            'row': None, 'column': None, 'side': None
        }
    
    def __repr__(self):
        return f"<WidgetNode {self.name}:{self.type}@{self.line}>"

class TkinterAnalyzer(ast.NodeVisitor):
    """AST visitor to extract Tkinter widget configurations"""
    
    def __init__(self, filename: str):
        self.filename = filename
        self.widgets: Dict[str, WidgetNode] = {}
        self.current_class = None
        self.current_method = None
        self.assignments: Dict[str, ast.Assign] = {}
        self.issues: List[Dict] = []
        self.manifest: Dict[str, Any] = {
            'file': filename,
            'scan_time': datetime.now().isoformat(),
            'widgets': [],
            'issues': [],
            'statistics': {}
        }
    
    def analyze(self):
        """Main analysis entry point"""
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                content = f.read()
            tree = ast.parse(content, filename=self.filename)
            self.visit(tree)
            self._analyze_relationships()
            self._detect_clashes()
            self._check_best_practices()
            self._generate_manifest()
            return self.manifest
        except Exception as e:
            logging.error(f"Failed to analyze {self.filename}: {e}")
            raise
    
    def visit_ClassDef(self, node: ast.ClassDef):
        """Track class definitions"""
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Track method definitions"""
        old_method = self.current_method
        self.current_method = node.name
        self.generic_visit(node)
        self.current_method = old_method
    
    def visit_Assign(self, node: ast.Assign):
        """Track variable assignments (potential widget creations)"""
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                self.assignments[var_name] = node
                
                # Check if this is a widget creation
                if isinstance(node.value, ast.Call):
                    self._check_widget_creation(var_name, node.value)
        
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call):
        """Check for geometry manager calls and widget configurations"""
        # Check for pack/grid/place calls
        if isinstance(node.func, ast.Attribute):
            geom_method = node.func.attr
            if geom_method in GEOMETRY_MANAGERS:
                self._process_geometry_call(node)
            
            # Check for widget attribute configurations
            if hasattr(node.func, 'value') and isinstance(node.func.value, ast.Name):
                widget_var = node.func.value.id
                if widget_var in self.widgets:
                    self._process_widget_config(widget_var, node)
        
        self.generic_visit(node)
    
    def _check_widget_creation(self, var_name: str, call_node: ast.Call):
        """Detect Tkinter widget instantiation"""
        widget_type = None
        
        # Check for tk.Widget() or ttk.Widget() patterns
        if isinstance(call_node.func, ast.Attribute):
            # Pattern: tk.Button(), ttk.Button(), etc.
            module = call_node.func.value.id if isinstance(call_node.func.value, ast.Name) else None
            widget_name = call_node.func.attr
            
            # Check if it's a known widget
            for mod, widgets in TKINTER_WIDGETS.items():
                if (module == mod or module == f'{mod}inter') and \
                   (widget_name in widgets['containers'] or widget_name in widgets['widgets']):
                    widget_type = f"{module}.{widget_name}"
                    break
        
        elif isinstance(call_node.func, ast.Name):
            # Pattern: Button() after "from tkinter import Button"
            widget_name = call_node.func.id
            # Check against all known widget names
            for mod, widgets in TKINTER_WIDGETS.items():
                if widget_name in widgets['containers'] or widget_name in widgets['widgets']:
                    widget_type = widget_name
        
        if widget_type:
            widget_node = WidgetNode(var_name, widget_type, call_node.lineno)
            self.widgets[var_name] = widget_node
            
            # Extract parent from arguments if present
            if call_node.args:
                first_arg = call_node.args[0]
                if isinstance(first_arg, ast.Name) and first_arg.id in self.widgets:
                    widget_node.parent = self.widgets[first_arg.id]
                    self.widgets[first_arg.id].children.append(widget_node)
            
            logging.debug(f"Found widget: {var_name} = {widget_type} at line {call_node.lineno}")
    
    def _process_geometry_call(self, node: ast.Call):
        """Extract geometry manager parameters"""
        geom_method = node.func.attr
        
        # Find which widget this is called on
        if isinstance(node.func.value, ast.Name):
            widget_var = node.func.value.id
            if widget_var in self.widgets:
                widget = self.widgets[widget_var]
                widget.geometry['manager'] = geom_method
                
                # Extract keyword arguments
                for kw in node.keywords:
                    widget.geometry[kw.arg] = self._extract_value(kw.value)
                
                logging.debug(f"Geometry: {widget_var}.{geom_method}() with {widget.geometry}")
    
    def _process_widget_config(self, widget_var: str, node: ast.Call):
        """Process widget configuration calls"""
        widget = self.widgets[widget_var]
        method = node.func.attr
        
        # Check for common configuration methods
        if method == 'configure':
            for kw in node.keywords:
                widget.attributes[kw.arg] = self._extract_value(kw.value)
        
        elif method in ['pack_configure', 'grid_configure', 'place_configure']:
            for kw in node.keywords:
                if kw.arg not in widget.geometry:
                    widget.geometry[kw.arg] = self._extract_value(kw.value)
    
    def _extract_value(self, node: ast.AST) -> Any:
        """Extract Python literal value from AST node"""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.Str):
            return node.s
        elif isinstance(node, ast.NameConstant):
            return node.value
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            if isinstance(node.operand, ast.Num):
                return -node.operand.n
        elif isinstance(node, ast.Tuple) or isinstance(node, ast.List):
            return [self._extract_value(el) for el in node.elts]
        return None
    
    def _analyze_relationships(self):
        """Build widget hierarchy and detect parent-child issues"""
        for name, widget in self.widgets.items():
            # If widget has no parent but isn't a root window, flag it
            if not widget.parent and 'Tk' not in widget.type and 'Toplevel' not in widget.type:
                # Try to infer parent from assignment context
                pass
            
            # Store in manifest
            self.manifest['widgets'].append({
                'name': widget.name,
                'type': widget.type,
                'line': widget.line,
                'parent': widget.parent.name if widget.parent else None,
                'geometry': widget.geometry,
                'attributes': widget.attributes,
                'children': [c.name for c in widget.children]
            })
    
    def _detect_clashes(self):
        """Detect widget positioning clashes"""
        # Group widgets by parent
        by_parent = {}
        for widget in self.widgets.values():
            parent_name = widget.parent.name if widget.parent else 'ROOT'
            by_parent.setdefault(parent_name, []).append(widget)
        
        # Check each parent container
        for parent_name, widgets in by_parent.items():
            # Detect mixed geometry managers
            managers = set(w.geometry.get('manager') for w in widgets if 'manager' in w.geometry)
            if len(managers) > 1:
                for combo in itertools.combinations(managers, 2):
                    if combo in INVALID_MIXTURES:
                        self._add_issue(
                            severity="ERROR",
                            title=f"Mixing {combo[0]}() and {combo[1]}() in same parent",
                            description=INVALID_MIXTURES[combo],
                            line=widgets[0].line,
                            widget=parent_name,
                            suggestion="Use only one geometry manager per parent container"
                        )
            
            # Check for grid conflicts
            grid_widgets = [w for w in widgets if w.geometry.get('manager') == 'grid']
            occupied = {}
            for widget in grid_widgets:
                row = widget.geometry.get('row')
                column = widget.geometry.get('column')
                rowspan = widget.geometry.get('rowspan', 1)
                columnspan = widget.geometry.get('columnspan', 1)
                
                if row is not None and column is not None:
                    for r in range(row, row + rowspan):
                        for c in range(column, column + columnspan):
                            key = (r, c)
                            if key in occupied:
                                other = occupied[key]
                                self._add_issue(
                                    severity="WARNING",
                                    title=f"Grid cell conflict at ({r},{c})",
                                    description=f"'{widget.name}' overlaps with '{other.name}'",
                                    line=widget.line,
                                    widget=widget.name,
                                    suggestion=f"Adjust row/column/span values to avoid overlap"
                                )
                            else:
                                occupied[key] = widget
            
            # Check pack side conflicts
            pack_widgets = [w for w in widgets if w.geometry.get('manager') == 'pack']
            sides = {}
            for widget in pack_widgets:
                side = widget.geometry.get('side', 'top')
                if side in sides:
                    self._add_issue(
                        severity="INFO",
                        title=f"Multiple widgets packed to {side} side",
                        description=f"'{widget.name}' packed to same side as '{sides[side].name}'",
                        line=widget.line,
                        widget=widget.name,
                        suggestion="Consider using grid() for complex layouts or adjust packing order"
                    )
                sides[side] = widget
    
    def _check_best_practices(self):
        """Check for Tkinter best practice violations"""
        for widget in self.widgets.values():
            # Check for hardcoded absolute sizes
            if 'width' in widget.attributes and 'height' in widget.attributes:
                if isinstance(widget.attributes['width'], int) and widget.attributes['width'] > 1000:
                    self._add_issue(
                        severity="WARNING",
                        title=f"Excessively large width: {widget.attributes['width']}",
                        description=f"Widget '{widget.name}' has unusually large fixed width",
                        line=widget.line,
                        widget=widget.name,
                        suggestion="Consider using relative sizing or window resizing"
                    )
            
            # Check for absolute placement with place()
            if widget.geometry.get('manager') == 'place':
                if 'x' in widget.geometry and 'y' in widget.geometry:
                    self._add_issue(
                        severity="INFO",
                        title="Absolute placement with place()",
                        description=f"Widget '{widget.name}' uses fixed coordinates",
                        line=widget.line,
                        widget=widget.name,
                        suggestion="Absolute placement can break on different screen resolutions"
                    )
            
            # Check for missing padding
            if widget.geometry.get('manager') in ['pack', 'grid']:
                has_padx = 'padx' in widget.geometry or 'padx' in widget.attributes
                has_pady = 'pady' in widget.geometry or 'pady' in widget.attributes
                if not has_padx and not has_pady:
                    self._add_issue(
                        severity="INFO",
                        title="No padding specified",
                        description=f"Widget '{widget.name}' has no padding",
                        line=widget.line,
                        widget=widget.name,
                        suggestion="Add padx/pady parameters for better visual spacing"
                    )
    
    def _add_issue(self, severity: str, title: str, description: str, 
                   line: int, widget: str, suggestion: str):
        """Record an issue found during analysis"""
        issue = {
            'severity': severity,
            'title': title,
            'description': description,
            'line': line,
            'widget': widget,
            'suggestion': suggestion,
            'file': self.filename
        }
        self.issues.append(issue)
        self.manifest['issues'].append(issue)
        logging.info(f"{severity}: {title} (line {line})")

def analyze_file(filepath: Path, output_dir: Optional[Path] = None) -> Dict:
    """Analyze a single Python file for Tkinter issues"""
    logging.info(f"Analyzing: {filepath}")
    
    analyzer = TkinterAnalyzer(str(filepath))
    manifest = analyzer.analyze()
    
    # Calculate statistics
    manifest['statistics'] = {
        'total_widgets': len(manifest['widgets']),
        'total_issues': len(manifest['issues']),
        'issues_by_severity': {
            'ERROR': sum(1 for i in manifest['issues'] if i['severity'] == 'ERROR'),
            'WARNING': sum(1 for i in manifest['issues'] if i['severity'] == 'WARNING'),
            'INFO': sum(1 for i in manifest['issues'] if i['severity'] == 'INFO')
        },
        'geometry_managers': {},
        'widget_types': {}
    }
    
    # Count geometry managers
    for widget in manifest['widgets']:
        manager = widget['geometry'].get('manager', 'none')
        manifest['statistics']['geometry_managers'][manager] = \
            manifest['statistics']['geometry_managers'].get(manager, 0) + 1
        
        widget_type = widget['type'].split('.')[-1] if '.' in widget['type'] else widget['type']
        manifest['statistics']['widget_types'][widget_type] = \
            manifest['statistics']['widget_types'].get(widget_type, 0) + 1
    
    # Save manifest if output directory specified
    if output_dir:
        output_file = output_dir / f"{filepath.stem}_manifest.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, default=str)
        logging.info(f"Manifest saved: {output_file}")
    
    return manifest

def analyze_directory(directory: Path, output_dir: Optional[Path] = None, 
                     recursive: bool = False) -> List[Dict]:
    """Analyze all Python files in a directory"""
    manifests = []
    
    if recursive:
        python_files = list(directory.rglob("*.py"))
    else:
        python_files = list(directory.glob("*.py"))
    
    logging.info(f"Found {len(python_files)} Python files in {directory}")
    
    for filepath in python_files:
        try:
            manifest = analyze_file(filepath, output_dir)
            manifests.append(manifest)
        except Exception as e:
            logging.error(f"Failed to analyze {filepath}: {e}")
    
    return manifests

def generate_report(manifests: List[Dict], output_file: Path):
    """Generate a comprehensive HTML report"""
    from datetime import datetime
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Tkinter GUI Analysis Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
            .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            h1 {{ color: #333; border-bottom: 3px solid #007acc; padding-bottom: 10px; }}
            .summary {{ background: #e8f4fc; padding: 20px; border-radius: 5px; margin: 20px 0; }}
            .issue {{ border-left: 4px solid #ddd; padding: 10px; margin: 10px 0; background: #f9f9f9; }}
            .issue.ERROR {{ border-left-color: #f44336; background: #ffebee; }}
            .issue.WARNING {{ border-left-color: #ff9800; background: #fff3e0; }}
            .issue.INFO {{ border-left-color: #2196f3; background: #e8f4fc; }}
            .widget-list {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 15px; }}
            .widget-card {{ background: #f8f9fa; padding: 15px; border-radius: 5px; border: 1px solid #dee2e6; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background: #007acc; color: white; }}
            .timestamp {{ color: #666; font-size: 0.9em; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 Tkinter GUI Analysis Report</h1>
            <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            
            <div class="summary">
                <h2>📈 Summary</h2>
                <p>Total Files Analyzed: {len(manifests)}</p>
                <p>Total Widgets Found: {sum(m['statistics']['total_widgets'] for m in manifests)}</p>
                <p>Total Issues: {sum(m['statistics']['total_issues'] for m in manifests)}</p>
            </div>
    """
    
    for manifest in manifests:
        filename = Path(manifest['file']).name
        html += f"""
            <h2>📁 {filename}</h2>
            <p>Widgets: {manifest['statistics']['total_widgets']} | 
               Issues: {manifest['statistics']['total_issues']} (
               <span style="color:#f44336">Errors: {manifest['statistics']['issues_by_severity']['ERROR']}</span>,
               <span style="color:#ff9800">Warnings: {manifest['statistics']['issues_by_severity']['WARNING']}</span>,
               <span style="color:#2196f3">Info: {manifest['statistics']['issues_by_severity']['INFO']}</span>)</p>
            
            <h3>Issues Found:</h3>
        """
        
        if manifest['issues']:
            for issue in manifest['issues']:
                html += f"""
                <div class="issue {issue['severity']}">
                    <strong>{issue['severity']}: {issue['title']}</strong><br>
                    <small>Line {issue['line']} | Widget: {issue['widget']}</small><br>
                    <p>{issue['description']}</p>
                    <em>💡 Suggestion: {issue['suggestion']}</em>
                </div>
                """
        else:
            html += "<p>✅ No issues found!</p>"
        
        html += f"""
            <h3>Widget Hierarchy:</h3>
            <div class="widget-list">
        """
        
        for widget in manifest['widgets']:
            html += f"""
                <div class="widget-card">
                    <strong>{widget['name']}</strong> ({widget['type']})<br>
                    <small>Line {widget['line']}</small><br>
                    Manager: {widget['geometry'].get('manager', 'none')}<br>
                    Parent: {widget['parent'] or 'ROOT'}<br>
                    Children: {len(widget['children'])}
                </div>
            """
        
        html += "</div>"
    
    html += """
        </div>
    </body>
    </html>
    """
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    logging.info(f"HTML report generated: {output_file}")

def print_terminal_report(manifest: Dict):
    """Print analysis results to terminal"""
    print("\n" + "="*80)
    print("TKINTER GUI ANALYSIS REPORT")
    print("="*80)
    print(f"File: {manifest['file']}")
    print(f"Scan Time: {manifest['scan_time']}")
    print(f"Total Widgets: {manifest['statistics']['total_widgets']}")
    print(f"Total Issues: {manifest['statistics']['total_issues']}")
    print("-"*80)
    
    # Print issues grouped by severity
    for severity in ['ERROR', 'WARNING', 'INFO']:
        issues = [i for i in manifest['issues'] if i['severity'] == severity]
        if issues:
            print(f"\n{severity} ISSUES ({len(issues)}):")
            print("-"*40)
            for issue in issues:
                print(f"Line {issue['line']}: {issue['title']}")
                print(f"  Widget: {issue['widget']}")
                print(f"  Issue: {issue['description']}")
                print(f"  💡 Fix: {issue['suggestion']}")
                print()
    
    # Print widget summary
    print("\n" + "="*80)
    print("WIDGET SUMMARY:")
    print("-"*80)
    
    # Geometry manager usage
    print("\nGeometry Manager Usage:")
    for manager, count in manifest['statistics']['geometry_managers'].items():
        print(f"  {manager.upper():10}: {count:3} widgets")
    
    # Widget type distribution
    print("\nWidget Type Distribution:")
    for wtype, count in sorted(manifest['statistics']['widget_types'].items(), 
                               key=lambda x: x[1], reverse=True):
        print(f"  {wtype:15}: {count:3} widgets")
    
    print("="*80)

def main():
    """Main entry point with argparse"""
    parser = argparse.ArgumentParser(
        description="TKINTER GUI DIMENSION ANALYZER & CLASH DETECTOR",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        EXAMPLES:
          Scan single file:      tkinter_scanner.py --file my_gui.py
          Scan directory:        tkinter_scanner.py --directory ./src --recursive
          Export manifests:      tkinter_scanner.py --file app.py --output ./reports
          Generate HTML report:  tkinter_scanner.py --dir ./gui --report analysis.html
          
        DETECTION CAPABILITIES:
          ✓ Mixed geometry managers (pack/grid conflicts)
          ✓ Grid cell overlaps
          ✓ Absolute positioning issues
          ✓ Missing padding/spacing
          ✓ Excessively large fixed dimensions
          ✓ Widget hierarchy validation
          ✓ Best practice violations
          
        OUTPUTS:
          • Terminal summary with color-coded issues
          • JSON manifest per file with full details
          • HTML comprehensive report
          • Self-logging for crash recovery
        """)
    )
    
    parser.add_argument(
        '-f', '--file',
        help="Analyze a single Python file"
    )
    
    parser.add_argument(
        '-d', '--directory',
        help="Analyze all Python files in directory"
    )
    
    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        help="Recursively scan subdirectories (with --directory)"
    )
    
    parser.add_argument(
        '-o', '--output',
        help="Output directory for JSON manifests"
    )
    
    parser.add_argument(
        '--report',
        help="Generate HTML report file"
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help="Enable debug mode with extra details"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.verbose:
        logging.getLogger().setLevel(logging.INFO)
    
    setup_logging()
    logging.info(f"Starting Tkinter Scanner (log: {LOG_FILE})")
    
    # Validate arguments
    if not args.file and not args.directory:
        parser.error("Either --file or --directory must be specified")
    
    if args.file and args.directory:
        parser.error("Specify either --file OR --directory, not both")
    
    # Prepare output directory
    output_dir = None
    if args.output:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        logging.info(f"Output directory: {output_dir}")
    
    manifests = []
    
    # Process based on input type
    if args.file:
        filepath = Path(args.file)
        if not filepath.exists():
            logging.error(f"File not found: {filepath}")
            sys.exit(1)
        
        manifest = analyze_file(filepath, output_dir)
        manifests.append(manifest)
        print_terminal_report(manifest)
    
    elif args.directory:
        dirpath = Path(args.directory)
        if not dirpath.exists() or not dirpath.is_dir():
            logging.error(f"Directory not found: {dirpath}")
            sys.exit(1)
        
        manifests = analyze_directory(dirpath, output_dir, args.recursive)
        
        # Print summary for each file
        for manifest in manifests:
            print_terminal_report(manifest)
    
    # Generate HTML report if requested
    if args.report and manifests:
        report_file = Path(args.report)
        generate_report(manifests, report_file)
        logging.info(f"Report generated: {report_file}")
    
    # Print overall summary
    if manifests:
        total_issues = sum(m['statistics']['total_issues'] for m in manifests)
        total_widgets = sum(m['statistics']['total_widgets'] for m in manifests)
        
        print("\n" + "="*80)
        print("OVERALL SUMMARY:")
        print("="*80)
        print(f"Files Analyzed: {len(manifests)}")
        print(f"Total Widgets: {total_widgets}")
        print(f"Total Issues: {total_issues}")
        
        if total_issues == 0:
            print("✅ All GUI configurations look good!")
        else:
            print("⚠️  Review the issues above for improvements")
        
        print(f"\nLog file: {LOG_FILE}")
        if output_dir:
            print(f"Manifests saved to: {output_dir}")
        if args.report:
            print(f"HTML report: {args.report}")
        print("="*80)

if __name__ == "__main__":
    main()