#!/usr/bin/env python3
"""
hierarchy_analyzer.py - System Hierarchy & Dominance Analysis

Calculates hierarchical relationships and dominance across:
- Process tree (root → stems → leaves)
- File system operations
- Code structure (imports → classes → functions)
- Network connections
- Command lineage
"""

import psutil
import os
from pathlib import Path
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple
import logging

try:
    import pyview
except ImportError:
    pyview = None

@dataclass
class ProcessNode:
    """Represents a process in the hierarchy"""
    pid: int
    name: str
    cmdline: List[str]
    category: str
    parent_pid: Optional[int]
    children_pids: List[int] = field(default_factory=list)

    # Dominance metrics
    depth: int = 0  # Distance from root
    descendant_count: int = 0  # Total children recursively
    cpu_aggregate: float = 0.0  # Total CPU of this + descendants
    mem_aggregate: float = 0.0  # Total memory

    # Behavioral traits
    network_connections: int = 0
    open_files: int = 0
    open_file_paths: List[str] = field(default_factory=list)
    threads: int = 1

    # Code context (if source file detected)
    source_file: Optional[str] = None
    imports: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)

    # Communication
    connected_to: Set[int] = field(default_factory=set)  # PIDs this talks to

    def dominance_score(self) -> float:
        """Calculate overall dominance score"""
        # Weight different factors
        score = 0.0
        score += self.descendant_count * 10  # Children count heavily
        score += self.depth * -2  # Prefer higher in tree (lower depth)
        score += self.cpu_aggregate * 1  # Resource usage
        score += self.network_connections * 5  # Network activity
        score += len(self.connected_to) * 8  # Communication breadth
        return score


@dataclass
class HierarchySnapshot:
    """Complete system hierarchy snapshot"""
    timestamp: str
    root_processes: List[ProcessNode]  # Top-level (no parent)
    all_nodes: Dict[int, ProcessNode]  # PID → Node
    stem_processes: List[ProcessNode]  # Key intermediate nodes
    dominant_processes: List[ProcessNode]  # Ranked by dominance

    # System-wide stats
    total_processes: int = 0
    total_threads: int = 0
    total_connections: int = 0

    # File system context
    active_directories: Set[str] = field(default_factory=set)
    active_files: Set[str] = field(default_factory=set)


class HierarchyAnalyzer:
    """Analyzes system process hierarchy and dominance"""

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)

    def capture_snapshot(self, resource_level: int = 50) -> HierarchySnapshot:
        """Capture complete system hierarchy snapshot with resource control"""
        from datetime import datetime

        # Resource level effects:
        # < 30: Skip code analysis, skip deep children iteration
        # < 70: Basic code analysis, standard depth
        # > 70: Full analysis
        do_code_analysis = resource_level >= 30
        deep_scan = resource_level >= 70

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        all_nodes = {}

        # 0. Get listening ports once for communication mapping
        listeners = self._get_listening_ports()

        # 1. Build process tree
        self.logger.info(f"Capturing process hierarchy snapshot (Level: {resource_level})...")

        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent',
                                         'memory_percent', 'num_threads']):
            try:
                pid = proc.info['pid']

                # Create node
                node = ProcessNode(
                    pid=pid,
                    name=proc.info['name'],
                    cmdline=proc.info['cmdline'] or [],
                    category="",  # Will be set later
                    parent_pid=None,
                    threads=proc.info['num_threads'],
                    cpu_aggregate=proc.info['cpu_percent'],
                    mem_aggregate=proc.info['memory_percent']
                )

                # Get parent
                try:
                    parent = proc.parent()
                    node.parent_pid = parent.pid if parent else None
                except:
                    pass

                # Get children (Only if not minimal level or if it's a known script)
                if deep_scan or node.parent_pid is None or "python" in node.name.lower():
                    try:
                        children = proc.children()
                        node.children_pids = [c.pid for c in children]
                    except:
                        pass

                # Get network connections and detect communication
                try:
                    conns = proc.net_connections(kind='inet')
                    node.network_connections = len(conns)
                    
                    # Detect process-to-process communication
                    for conn in conns:
                        if conn.raddr and conn.raddr.port in listeners:
                            target_pid = listeners[conn.raddr.port]
                            if target_pid != pid:
                                node.connected_to.add(target_pid)
                except:
                    node.network_connections = 0

                # Skip expensive ops if level is very low
                if resource_level > 20:
                    # Get open files
                    try:
                        files = proc.open_files()
                        node.open_files = len(files)
                        # Behavioral Capture: Store paths of logs and scripts
                        for f in files:
                            if f.path.endswith(('.log', '.txt', '.py', '.sh', '.js', '.json')):
                                node.open_file_paths.append(f.path)
                    except:
                        pass

                    # Detect source file
                    node.source_file = self._detect_source_file(node.cmdline)

                    # Analyze source if Python file and allowed by resource level
                    if do_code_analysis and node.source_file and node.source_file.endswith('.py') and pyview:
                        self._analyze_source_code(node)

                all_nodes[pid] = node

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # 2. Calculate hierarchy metrics
        self._calculate_hierarchy_metrics(all_nodes)

        # 3. Identify root processes
        root_processes = [node for node in all_nodes.values() if node.parent_pid is None or node.parent_pid not in all_nodes]

        # 4. Identify stem processes (high child count, mid-depth)
        stem_processes = self._identify_stems(all_nodes)

        # 5. Rank by dominance
        dominant_processes = sorted(all_nodes.values(),
                                   key=lambda n: n.dominance_score(),
                                   reverse=True)[:20]

        # 6. Gather file system context
        active_dirs, active_files = self._gather_filesystem_context(all_nodes)

        # 7. System stats
        total_threads = sum(node.threads for node in all_nodes.values())
        total_connections = sum(node.network_connections for node in all_nodes.values())

        snapshot = HierarchySnapshot(
            timestamp=timestamp,
            root_processes=root_processes,
            all_nodes=all_nodes,
            stem_processes=stem_processes,
            dominant_processes=dominant_processes,
            total_processes=len(all_nodes),
            total_threads=total_threads,
            total_connections=total_connections,
            active_directories=active_dirs,
            active_files=active_files
        )

        self.logger.info(f"Snapshot captured: {len(all_nodes)} processes, {len(root_processes)} roots, {len(stem_processes)} stems")

        return snapshot

    def _get_listening_ports(self) -> Dict[int, int]:
        """Get map of listening port → PID"""
        listeners = {}
        for proc in psutil.process_iter():
            try:
                for conn in proc.connections():
                    if conn.status == 'LISTEN' and conn.laddr:
                        listeners[conn.laddr.port] = proc.pid
            except:
                pass
        return listeners

    def _detect_source_file(self, cmdline: List[str]) -> Optional[str]:
        """Detect source file from command line"""
        for arg in cmdline:
            if arg.endswith(('.py', '.rs', '.cpp', '.c', '.go', '.js', '.sh')):
                if os.path.exists(arg):
                    return os.path.abspath(arg)
        return None

    def _analyze_source_code(self, node: ProcessNode):
        """Analyze Python source code for imports, classes, functions"""
        if not pyview or not node.source_file:
            return

        try:
            pf = pyview.analyze_file(Path(node.source_file))
            node.imports = [imp.name for imp in pf.imports]

            for elem in pf.elements:
                if elem.kind == 'class':
                    node.classes.append(elem.name)
                elif elem.kind == 'function':
                    node.functions.append(elem.name)
        except Exception as e:
            self.logger.debug(f"Failed to analyze {node.source_file}: {e}")

    def _calculate_hierarchy_metrics(self, all_nodes: Dict[int, ProcessNode]):
        """Calculate depth and aggregate metrics for all nodes"""
        # BFS to calculate depth from roots
        visited = set()
        queue = deque()

        # Find roots and start BFS
        for pid, node in all_nodes.items():
            if node.parent_pid is None or node.parent_pid not in all_nodes:
                node.depth = 0
                queue.append(node)
                visited.add(pid)

        while queue:
            node = queue.popleft()

            for child_pid in node.children_pids:
                if child_pid in all_nodes and child_pid not in visited:
                    child = all_nodes[child_pid]
                    child.depth = node.depth + 1
                    queue.append(child)
                    visited.add(child_pid)

        # Calculate descendant counts (bottom-up)
        def count_descendants(node: ProcessNode) -> int:
            count = len(node.children_pids)
            for child_pid in node.children_pids:
                if child_pid in all_nodes:
                    count += count_descendants(all_nodes[child_pid])
            node.descendant_count = count
            return count

        for node in all_nodes.values():
            if not node.children_pids:  # Leaf nodes first
                count_descendants(node)

    def _identify_stems(self, all_nodes: Dict[int, ProcessNode]) -> List[ProcessNode]:
        """Identify stem processes (key intermediate nodes)"""
        stems = []

        for node in all_nodes.values():
            # Stems are:
            # - Not roots (depth > 0)
            # - Have multiple children
            # - Mid-depth (1-5)
            if node.depth > 0 and node.depth <= 5 and node.descendant_count >= 2:
                stems.append(node)

        # Sort by descendant count
        stems.sort(key=lambda n: n.descendant_count, reverse=True)

        return stems[:10]  # Top 10 stems

    def _gather_filesystem_context(self, all_nodes: Dict[int, ProcessNode]) -> Tuple[Set[str], Set[str]]:
        """Gather active directories and files from processes"""
        active_dirs = set()
        active_files = set()

        for node in all_nodes.values():
            if node.source_file:
                active_files.add(node.source_file)
                active_dirs.add(os.path.dirname(node.source_file))

            # Get working directory
            try:
                proc = psutil.Process(node.pid)
                cwd = proc.cwd()
                active_dirs.add(cwd)
            except:
                pass

        return active_dirs, active_files

    def build_hierarchy_text(self, snapshot: HierarchySnapshot, max_depth: int = 3) -> str:
        """Build text representation of hierarchy"""
        lines = []
        lines.append(f"=== System Hierarchy @ {snapshot.timestamp} ===")
        lines.append(f"Processes: {snapshot.total_processes} | Threads: {snapshot.total_threads} | Connections: {snapshot.total_connections}\n")

        # Top 10 dominant processes
        lines.append("🏆 Most Dominant Processes:")
        for i, node in enumerate(snapshot.dominant_processes[:10], 1):
            score = node.dominance_score()
            lines.append(f"  {i}. [{node.pid}] {node.name} (score: {score:.0f}, depth: {node.depth}, children: {node.descendant_count})")

        lines.append("\n🌱 Stem Processes (Key Intermediates):")
        for node in snapshot.stem_processes[:5]:
            lines.append(f"  • [{node.pid}] {node.name} → {node.descendant_count} descendants at depth {node.depth}")

        lines.append("\n🌳 Root → Stem → Lineage:")

        # Show tree structure for top roots
        def print_tree(node: ProcessNode, prefix: str, depth: int):
            if depth > max_depth:
                return

            icon = "🔴" if node.pid in [n.pid for n in snapshot.dominant_processes[:3]] else "•"
            info = f"{node.name} ({node.pid})"

            if node.source_file:
                info += f" 📄 {os.path.basename(node.source_file)}"
            if node.network_connections > 0:
                info += f" 🌐 {node.network_connections}"

            lines.append(f"{prefix}{icon} {info}")

            children = [snapshot.all_nodes[cpid] for cpid in node.children_pids if cpid in snapshot.all_nodes]
            children.sort(key=lambda n: n.dominance_score(), reverse=True)

            for i, child in enumerate(children[:5]):  # Show top 5 children
                is_last = i == len(children[:5]) - 1
                new_prefix = prefix + ("    " if is_last else "│   ")
                print_tree(child, new_prefix, depth + 1)

        for root in sorted(snapshot.root_processes, key=lambda n: n.dominance_score(), reverse=True)[:3]:
            print_tree(root, "", 0)
            lines.append("")

        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Testing
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    analyzer = HierarchyAnalyzer()
    snapshot = analyzer.capture_snapshot()

    hierarchy_text = analyzer.build_hierarchy_text(snapshot)
    print(hierarchy_text)

    print("\n📊 Top Process by Dominance:")
    top = snapshot.dominant_processes[0]
    print(f"  PID: {top.pid}")
    print(f"  Name: {top.name}")
    print(f"  Descendants: {top.descendant_count}")
    print(f"  Depth: {top.depth}")
    print(f"  Source: {top.source_file or 'N/A'}")
    if top.imports:
        print(f"  Imports: {', '.join(top.imports[:5])}")
