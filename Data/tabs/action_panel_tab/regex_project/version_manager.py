import os
import shutil
import json
import difflib
import time
import sys
from datetime import datetime

# Optional Imports Handler
try:
    from taskw import TaskWarrior
    HAS_TASKW = True
except ImportError:
    HAS_TASKW = False

class BackupManager:
    """Handles script snapshots and file-size monitoring."""
    def __init__(self, base_dir, backup_dir):
        self.base_dir = base_dir
        self.backup_dir = backup_dir
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

    def create_snapshot(self, filename):
        src = os.path.join(self.base_dir, filename)
        if not os.path.exists(src): return False
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = os.path.join(self.backup_dir, f"{filename}.{timestamp}.bak")
        
        shutil.copy2(src, dst)
        return dst

    def get_latest_backup(self, filename):
        backups = sorted([f for f in os.listdir(self.backup_dir) if f.startswith(filename)])
        return os.path.join(self.backup_dir, backups[-1]) if backups else None

    def check_size_delta(self, filename):
        src = os.path.join(self.base_dir, filename)
        latest = self.get_latest_backup(filename)
        if not latest: return 0
        return os.path.getsize(src) - os.path.getsize(latest)

class JournalSystem:
    """Manages daily activity logs and narrative retrieval."""
    def __init__(self, journal_dir):
        self.journal_dir = journal_dir
        if not os.path.exists(journal_dir):
            os.makedirs(journal_dir)
        self.current_file = os.path.join(self.journal_dir, f"{datetime.now().strftime('%Y-%m-%d')}.json")
        self.entries = self._load_today()

    def _load_today(self):
        if os.path.exists(self.current_file):
            with open(self.current_file, 'r') as f:
                return json.load(f)
        return []

    def add_entry(self, activity, tasks_planned=[]):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "activity": activity,
            "tasks_planned": tasks_planned
        }
        self.entries.append(entry)
        with open(self.current_file, 'w') as f:
            json.dump(self.entries, f, indent=2)

    def search_narrative(self, keyword, limit=5):
        matches = []
        # Scan all journal files
        files = sorted(os.listdir(self.journal_dir), reverse=True)
        for filename in files:
            if filename.endswith(".json"):
                with open(os.path.join(self.journal_dir, filename), 'r') as f:
                    day_entries = json.load(f)
                    for e in day_entries:
                        if keyword.lower() in e.get("activity", "").lower():
                            matches.append(e)
                            if len(matches) >= limit: return matches
        return matches

class DiffEngine:
    """Uses marks to generate targeted diffs between current and backups."""
    def __init__(self, index_path):
        self.index_path = index_path

    def generate_mark_diff(self, filename, current_content, backup_content, mark_id):
        # Find the mark line in both
        def find_line(content, mid):
            for i, line in enumerate(content):
                if f"#[Mark:{mid}]" in line: return i
            return -1

        curr_lines = current_content.splitlines()
        back_lines = backup_content.splitlines()
        
        c_idx = find_line(curr_lines, mark_id)
        b_idx = find_line(back_lines, mark_id)
        
        if c_idx == -1 or b_idx == -1: return "Mark not found in one of the files."

        # Take a window around the mark (5 lines)
        c_window = curr_lines[max(0, c_idx-5):min(len(curr_lines), c_idx+5)]
        b_window = back_lines[max(0, b_idx-5):min(len(back_lines), b_idx+5)]
        
        diff = difflib.unified_diff(b_window, c_window, fromfile="Backup", tofile="Current")
        return "\n".join(list(diff))

class ResolutionAdvisor:
    """Suggests fixes for common syntactic/indentation issues."""
    def check_syntax(self, filename):
        path = os.path.abspath(filename)
        suggestions = []
        with open(path, 'r') as f:
            lines = f.readlines()
            for i, line in enumerate(lines, 1):
                if "\t" in line:
                    suggestions.append(f"Line {i}: Tab detected. Use 4 spaces for Python consistency.")
                if line.rstrip() != line and not line.endswith("\n"):
                    suggestions.append(f"Line {i}: Trailing whitespace detected.")
        return suggestions

class BackgroundWatcher:
    """Monitors file sizes and triggers backups/diffs automatically."""
    def __init__(self, manager, files_to_watch, interval_mins=5):
        self.manager = manager
        self.files = files_to_watch
        self.interval = interval_mins * 60
        self.active = False

    def start(self):
        self.active = True
        print(f"[Watcher] Started. Monitoring {self.files} every {self.interval/60} mins.")
        try:
            while self.active:
                for f in self.files:
                    delta = self.manager.check_size_delta(f)
                    if abs(delta) > 100: # 0.1kb
                        print(f"[Watcher] Change detected in {f}: {delta} bytes. Creating backup...")
                        self.manager.create_snapshot(f)
                time.sleep(self.interval)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.active = False
        print("[Watcher] Stopped.")

class CodeMarker:
    """Handles #[Mark:] tags for bi-directional referencing."""
    def __init__(self, project_dir):
        self.project_dir = project_dir

    def fetch_marked_lines(self, filename):
        path = os.path.join(self.project_dir, filename)
        if not os.path.exists(path): return {}
        
        marks = {}
        with open(path, 'r') as f:
            for i, line in enumerate(f, 1):
                if "#[Mark:" in line and not line.strip().startswith('if "#[Mark:"') and not 'line.split("#[Mark:")' in line:
                    try:
                        parts = line.split("#[Mark:")
                        mark_id = parts[1].split("]")[0]
                        marks[mark_id] = {"line": i, "content": line.strip()}
                    except IndexError:
                        continue
        return marks

class IndexBuilder:
    """Generates a centralized library of all code marks."""
    def __init__(self, project_dir, index_path):
        self.project_dir = project_dir
        self.index_path = index_path
        self.marker = CodeMarker(project_dir)

    def rebuild_index(self):
        full_index = {}
        for root, _, files in os.walk(self.project_dir):
            for file in files:
                if file.endswith(".py"):
                    rel_path = os.path.relpath(os.path.join(root, file), self.project_dir)
                    marks = self.marker.fetch_marked_lines(os.path.join(root, file))
                    if marks:
                        for mid, data in marks.items():
                            full_index[mid] = {
                                "file": rel_path,
                                "line": data["line"],
                                "snippet": data["content"]
                            }
        
        with open(self.index_path, 'w') as f:
            json.dump(full_index, f, indent=2)
        return full_index

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-watch", choices=["on", "off"])
    parser.add_argument("-time", type=int, default=5)
    parser.add_argument("--rebuild", action="store_true")
    
    args = parser.parse_args()
    
    manager = BackupManager(".", "backups")
    builder = IndexBuilder(".", "marks_index.json")
    
    if args.rebuild:
        builder.rebuild_index()
        print("Index rebuilt.")

    if args.watch == "on":
        watcher = BackgroundWatcher(manager, ["orchestrator.py", "interaction_resolver.py", "realization_engine.py"], args.time)
        watcher.start()