import psutil
import os
import sys
import time
import getpass
import argparse
import re
import socket
import logging
import json
import hashlib
import pyview
import traceback
from unified_logger import get_logger, setup_exception_handler
from pathlib import Path
from datetime import datetime

# Initialize unified logger
global logging
logging = get_logger("organizer")

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.error("Uncaught exception in Organizer", exc_info=(exc_type, exc_value, exc_traceback))
    traceback.print_exception(exc_type, exc_value, exc_traceback)

sys.excepthook = handle_exception
REFRESH_RATE = 2
USER_NAME = getpass.getuser()
HOME_DIR = os.path.expanduser("~")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
CONFIG_FILE = os.path.join(SCRIPT_DIR, "monitor_config.json")

# --- Colors ---
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    MY_STUFF = "\033[92m"   # Green
    WEB = "\033[94m"        # Blue
    GPU = "\033[95m"        # Purple
    DEV = "\033[93m"        # Yellow
    SYSTEM = "\033[90m"     # Gray
    ALERT = "\033[91m"      # Red
    WARN = "\033[33m"       # Orange/Gold
    HEADER = "\033[97m\033[1m" 

# --- Config & Integrity Manager ---
class ConfigManager:
    def __init__(self):
        self.config = self.load_config()
        # Ensure security keys exist
        if 'security' not in self.config:
            self.config['security'] = {}
        for key in ['known_apis', 'suspicious_keywords', 'allow', 'alias', 'server']:
            if key not in self.config['security']:
                self.config['security'][key] = []
        
        if 'user_prefs' not in self.config:
            self.config['user_prefs'] = {
                "theme": "dark",
                "show_line_numbers": True,
                "refresh_rate": 2000,
                "priorities": []
            }
        
        self.known_apis = self.config['security']['known_apis']
        self.suspicious_keywords = self.config['security']['suspicious_keywords']

    def load_config(self):
        if not os.path.exists(CONFIG_FILE):
            logging.error("Config file not found! Falling back to defaults.")
            return {
                "integrity": {"verified_hash": "", "last_verified": "", "file_hashes": {}, "config_baseline": {}},
                "security": {"known_apis": [], "suspicious_keywords": [], "allow": [], "alias": [], "server": []}
            }
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)

    def save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)

    def update_manifest(self, scan_results):
        """Updates manifest.json with a hierarchical summary of scans."""
        manifest_path = os.path.join(SCRIPT_DIR, "manifest.json")
        manifest = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "project_root": SCRIPT_DIR,
            "scan_summary": []
        }
        
        for r in scan_results:
            py_analysis = {}
            if r['path'].endswith('.py'):
                try:
                    pf = pyview.analyze_file(Path(r['path']))
                    py_analysis = {
                        "imports": pf.imports,
                        "elements": [{"name": e.name, "kind": e.kind} for e in pf.elements]
                    }
                except Exception: pass

            entry = {
                "file": r['file'],
                "score": r['score'],
                "issues": r['issues'],
                "network_activity": r['active'],
                "code_structure": py_analysis,
                "path": r['path']
            }
            manifest["scan_summary"].append(entry)
            
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=4)
        logging.info(f"Manifest updated with {len(scan_results)} files.")

    def add_trust(self, domain):
        if domain not in self.known_apis:
            self.known_apis.append(domain)
            self.config['security']['known_apis'] = self.known_apis
            self.save_config()
            print(f"{C.MY_STUFF}✓ Added '{domain}' to trusted list.{C.RESET}")
            logging.info(f"User added '{domain}' to trusted APIs.")
        else:
            print(f"{C.WARN}Domain '{domain}' is already trusted.{C.RESET}")

    def verify_integrity(self):
        """Checks if files have been modified since last verification."""
        stored_hashes = self.config['integrity'].get('file_hashes', {})
        if not stored_hashes:
            # Fallback to single file check for backward compatibility
            with open(__file__, 'rb') as f:
                current_hash = hashlib.sha256(f.read()).hexdigest()
            stored_hash = self.config['integrity'].get('verified_hash', "")
            if current_hash == stored_hash:
                return True, "Legacy hash OK"
            return False, "Legacy hash MISMATCH"

        mismatches = []
        # Check tracked files
        for filename, stored_hash in stored_hashes.items():
            path = os.path.join(SCRIPT_DIR, filename)
            if not os.path.exists(path):
                mismatches.append(f"Missing: {filename}")
                continue
            with open(path, 'rb') as f:
                current_hash = hashlib.sha256(f.read()).hexdigest()
            if current_hash != stored_hash:
                mismatches.append(f"Modified: {filename}")
        
        # Check for NEW scripts that aren't tracked
        current_scripts = [f for f in os.listdir(SCRIPT_DIR) if f.endswith(('.py', '.sh', '.js'))]
        for f in current_scripts:
            if f not in stored_hashes:
                mismatches.append(f"Untracked: {f}")

        if not mismatches:
            logging.info("Integrity Check: PASSED")
            return True, "All scripts verified"
        else:
            logging.critical(f"INTEGRITY MISMATCH: {', '.join(mismatches)}")
            return False, ", ".join(mismatches)

    def update_integrity(self):
        """Updates the stored hashes and config baseline with a gate."""
        print(f"\n{C.HEADER}=== 🛡️  INTEGRITY UPDATE GATE ==={C.RESET}")
        
        # 0. Syntax Baseline (py_compile)
        print(f"{C.BOLD}Validating scripts for syntax errors...{C.RESET}")
        import py_compile
        scripts = [f for f in os.listdir(SCRIPT_DIR) if f.endswith('.py')]
        failed_validation = []
        for script in scripts:
            try:
                py_compile.compile(os.path.join(SCRIPT_DIR, script), doraise=True)
            except py_compile.PyCompileError as e:
                failed_validation.append(script)
                print(f"  {C.ALERT}✖ Syntax Error in {script}{C.RESET}")
        
        if failed_validation:
            print(f"\n{C.ALERT}⚠️  SECURITY BLOCKED: Syntax errors detected in: {', '.join(failed_validation)}{C.RESET}")
            print(f"{C.WARN}Fix the scripts before updating the integrity baseline.{C.RESET}")
            confirm = input(f"{C.BOLD}Continue anyway? (y/N): {C.RESET}").strip().lower()
            if confirm != 'y': return

        # 1. Summarize Config Property Differences
        baseline = self.config['integrity'].get('config_baseline', {})
        current_sec = self.config['security']
        
        diffs_found = False
        print(f"\n{C.BOLD}Checking property differences (known/allow/alias/server):{C.RESET}")
        for key in ['known_apis', 'allow', 'alias', 'server']:
            old = set(baseline.get(key, []))
            cur = set(current_sec.get(key, []))
            added = cur - old
            removed = old - cur
            
            if added or removed:
                diffs_found = True
                print(f"  {C.WARN}Property '{key}' changed:{C.RESET}")
                for item in added: print(f"    {C.MY_STUFF}[+] {item}{C.RESET}")
                for item in removed: print(f"    {C.ALERT}[-] {item}{C.RESET}")
        
        if not diffs_found:
            print(f"  {C.MY_STUFF}✓ No security property changes detected.{C.RESET}")
        else:
            print(f"\n{C.ALERT}⚠️  WARNING: Changes detected in security lists. Verify these were intentional!{C.RESET}")

        # 2. Hash Scripts in Base Directory
        print(f"\n{C.BOLD}Scanning scripts in {SCRIPT_DIR}...{C.RESET}")
        scripts = [f for f in os.listdir(SCRIPT_DIR) if f.endswith(('.py', '.sh', '.js'))]
        new_hashes = {}
        for script in scripts:
            path = os.path.join(SCRIPT_DIR, script)
            with open(path, 'rb') as f:
                new_hashes[script] = hashlib.sha256(f.read()).hexdigest()
            print(f"  {C.DIM}• {script}{C.RESET}")

        # 3. Log Check (Socratic Suggestion: monitor count and presence)
        logs = os.listdir(LOG_DIR)
        print(f"  {C.DIM}• Found {len(logs)} log files in /logs{C.RESET}")

        # 4. Confirmation Gate
        confirm = input(f"\n{C.BOLD}Do you want to update the integrity baseline? (y/N): {C.RESET}").strip().lower()
        if confirm != 'y':
            print(f"\n{C.ALERT}✖ Update cancelled.{C.RESET}")
            return

        # Update Config
        self.config['integrity']['file_hashes'] = new_hashes
        self.config['integrity']['verified_hash'] = new_hashes.get(os.path.basename(__file__), "")
        self.config['integrity']['last_verified'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Update baseline for next comparison
        self.config['integrity']['config_baseline'] = {
            k: list(current_sec.get(k, [])) for k in ['known_apis', 'allow', 'alias', 'server']
        }
        
        self.save_config()
        print(f"\n{C.MY_STUFF}✓ Integrity baseline updated with datetime stamp: {self.config['integrity']['last_verified']}{C.RESET}")
        logging.info(f"Integrity baseline updated by user at {self.config['integrity']['last_verified']}")

    def get(self, key_path, default=None):
        """
        Get config value by dot notation path.

        Example:
            CM.get('user_prefs.process_monitor.filters.hide_system_idle', True)
        """
        from config_schema import get_config_value
        return get_config_value(self.config, key_path, default)

    def set(self, key_path, value):
        """
        Set config value by dot notation path.

        Example:
            CM.set('user_prefs.theme', 'light')
        """
        from config_schema import set_config_value
        self.config = set_config_value(self.config, key_path, value)
        return self.config

    def apply_defaults(self):
        """Apply default values for missing config keys."""
        from config_schema import apply_defaults
        self.config = apply_defaults(self.config)
        return self.config

    def validate(self):
        """
        Validate config against schema.

        Returns:
            Tuple of (is_valid, error_messages)
        """
        from config_schema import validate_config
        return validate_config(self.config)

# Initialize Config Global
CM = ConfigManager()

# --- Scanner Logic ---
def analyze_file(filepath):
    score = 100
    issues = []
    
    try:
        with open(filepath, 'r', errors='ignore') as f:
            content = f.read()
            
        for word in CM.suspicious_keywords:
            if word in content:
                score -= 10
                issues.append(f"Found suspicious keyword: '{word}'")

        ips = re.findall(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', content)
        for ip in ips:
            if not ip.startswith("127.0.") and not ip.startswith("192.168.") and not ip.startswith("10."):
                score -= 15
                issues.append(f"Hardcoded Public IP found: {ip}")

        if "import socket" in content or "import requests" in content or "urllib" in content:
            safe_api_found = any(api in content for api in CM.known_apis)
            if not safe_api_found:
                score -= 5
                issues.append("Network imports found without explicit reference to Known APIs")

    except Exception as e:
        return 0, [f"Error reading file: {str(e)}"]

    return max(0, score), issues

def check_active_connections(filename):
    connections = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = " ".join(proc.info['cmdline'] or [])
            if filename in cmd:
                try:
                    p = psutil.Process(proc.info['pid'])
                    conns = p.net_connections()
                    for c in conns:
                        state = c.status
                        laddr = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "unknown"
                        raddr = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "none"
                        connections.append(f"{state} | {laddr} -> {raddr}")
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return connections

def scanner_main(target_dir, recursive=False, view_mode="standard"):
    print(f"{C.HEADER}=== 🕵️  SECURITY SCANNER: {target_dir} ==={C.RESET}\n")
    logging.info(f"Starting scan on: {target_dir} (Recursive: {recursive})")
    
    files_to_scan = []
    if os.path.isfile(target_dir):
        files_to_scan.append(target_dir)
    else:
        for root, dirs, files in os.walk(target_dir):
            for file in files:
                if file.endswith('.py') or file.endswith('.sh') or file.endswith('.js'):
                    files_to_scan.append(os.path.join(root, file))
            if not recursive:
                break

    results = []
    for filepath in files_to_scan:
        filename = os.path.basename(filepath)
        score, issues = analyze_file(filepath)
        active_conns = check_active_connections(filename)
        results.append({
            "file": filename,
            "path": filepath,
            "score": score,
            "issues": issues,
            "active": active_conns
        })
        logging.info(f"Scanned {filename}: Score={score}, Active={bool(active_conns)}")

    # Update Manifest
    CM.update_manifest(results)

    if view_mode == "checklist":
        # Summary View
        high_risk = [r for r in results if r['score'] < 50]
        medium_risk = [r for r in results if 50 <= r['score'] < 80]
        secure = [r for r in results if r['score'] >= 80]
        
        print(f"{C.BOLD}--- CHECKLIST SUMMARY ---{C.RESET}")
        print(f"✅ Secure Files:      {len(secure)}")
        print(f"⚠️  Warnings:          {len(medium_risk)}")
        print(f"🚨 High Risk:         {len(high_risk)}")
        
        if high_risk or medium_risk:
            print(f"\n{C.ALERT}--- TOP RISKS ---{C.RESET}")
            for r in (high_risk + medium_risk):
                color = C.ALERT if r['score'] < 50 else C.WARN
                print(f"{color}[{r['score']}] {r['file']}{C.RESET}")
                for i in r['issues']:
                    print(f"    ↳ {i}")

    elif view_mode == "view":
        # Grouped View (Known vs Unknown/Risky)
        print(f"{C.BOLD}--- DETAILED GROUPED VIEW ---{C.RESET}\n")
        
        risky = [r for r in results if r['score'] < 100 or r['active']]
        if risky:
            print(f"{C.ALERT}>>> ATTENTION REQUIRED (Risks or Active Network){C.RESET}")
            print(f"{C.BOLD}{'SCORE':<8} {'FILE':<40}{C.RESET}")
            print("-" * 60)
            for r in risky:
                color = C.ALERT if r['score'] < 80 else C.WEB
                print(f"{color}{r['score']:<8} {r['file']:<40}{C.RESET}")
                for i in r['issues']:
                    print(f"   {C.DIM}↳ {i}{C.RESET}")
                for c in r['active']:
                    print(f"   {C.WEB}↳ ACTIVE: {c}{C.RESET}")
            print("\n")
            
        safe = [r for r in results if r['score'] == 100 and not r['active']]
        if safe:
            print(f"{C.MY_STUFF}>>> KNOWN GOOD (Clean & Passive){C.RESET}")
            for r in safe:
                print(f"{C.DIM}✓ {r['file']}{C.RESET}")

    else:
        print(f"{C.DIM}Scanning {len(files_to_scan)} files...{C.RESET}\n")
        print(f"{C.BOLD}{'SCORE':<8} {'STATUS':<10} {'FILE':<40}{C.RESET}")
        print("-" * 80)
        
        for r in results:
            score = r['score']
            active_conns = r['active']
            filename = r['file']
            issues = r['issues']
            score_color = C.MY_STUFF
            status = "SECURE"
            
            if score < 80: 
                score_color = C.WARN
                status = "WARN"
            if score < 50: 
                score_color = C.ALERT
                status = "RISK"
            if active_conns and score < 100:
                 status += "*"

            print(f"{score_color}{score:<8} {status:<10} {filename:<40}{C.RESET}")
            if issues or active_conns:
                for issue in issues:
                    print(f"   {C.DIM}↳ {issue}{C.RESET}")
                for conn in active_conns:
                    print(f"   {C.WEB}↳ ACTIVE NET: {conn}{C.RESET}")
                print("\n")

# --- Monitor Logic ---
def get_category(proc):
    """
    Determine process category based on name and command line.
    Handles psutil.Process, ProcessNode (dataclass), or raw string.
    """
    try:
        if isinstance(proc, str):
            name = proc.lower()
            cmdline = ""
        elif hasattr(proc, 'name') and callable(getattr(proc, 'name')):
            # psutil.Process
            name = proc.name().lower()
            cmdline = " ".join(proc.cmdline()).lower()
        elif hasattr(proc, 'name'):
            # ProcessNode or similar dataclass
            name = proc.name.lower()
            cmdline = " ".join(getattr(proc, 'cmdline', [])).lower()
        else:
            return ("Unknown", C.DIM, 99)
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, Exception):
        return ("Ghost", C.DIM, 99)

    if "custom_applications" in cmdline or ("python" in name and "scripts" in cmdline):
        return (" 🧠 MY SCRIPTS", C.MY_STUFF, 1)
    if any(x in name for x in ['radeontop', 'nvidia', 'xorg', 'kwin', 'steam', 'vlc', 'mpv', 'obs', 'discord']):
        return (" 🎨 GPU & MEDIA", C.GPU, 2)
    if any(x in name for x in ['firefox', 'chrome', 'brave', 'edge', 'chromium', 'thunderbird']):
        return (" 🌐 WEB & COMMS", C.WEB, 3)
    if any(x in name for x in ['code', 'vim', 'nvim', 'git', 'node', 'python', 'java', 'gcc', 'make', 'docker']):
        return (" 🛠️  DEV TOOLS", C.DEV, 4)
    if any(x in name for x in ['bash', 'zsh', 'fish', 'gnome-terminal', 'kitty', 'alacritty']):
        return (" 🐚 TERMINALS", C.DEV, 5)
    return (" ⚙️  SYSTEM / BACKGROUND", C.SYSTEM, 99)

def monitor_main(snapshot=False):
    logging.info("Starting Process Monitor")
    try:
        while True:
            procs = []
            for p in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'cmdline', 'exe']):
                try:
                    cat, color, priority = get_category(p)
                    p.info['category'] = cat
                    p.info['color'] = color
                    p.info['priority'] = priority
                    procs.append(p)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            procs.sort(key=lambda p: (p.info['priority'], -p.info['cpu_percent']))
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"{C.BOLD}=== 🐵 MONKEY BRAIN PROCESS MONITOR ==={C.RESET}")
            print(f"Time: {datetime.now().strftime('%H:%M:%S')} | Total Processes: {len(procs)}\n")
            
            # Show Integrity Status in Monitor
            is_valid, status_msg = CM.verify_integrity()
            integrity_icon = f"{C.MY_STUFF}🔒 SECURE{C.RESET}" if is_valid else f"{C.ALERT}🔓 {status_msg}{C.RESET}"
            print(f"System Integrity: {integrity_icon}")

            current_cat = None
            print(f"{C.BOLD}{'PID':<8} {'CPU%':<8} {'MEM%':<8} {'NAME':<25} {'COMMAND/DETAILS'}{C.RESET}")
            print("-" * 80)

            for p in procs:
                if p.info['category'] != current_cat:
                    current_cat = p.info['category']
                    print(f"\n{p.info['color']}{C.BOLD}{current_cat}{C.RESET}")
                    print(f"{p.info['color']}{'-'*30}{C.RESET}")

                pid = p.info['pid']
                cpu = p.info['cpu_percent']
                mem = p.info['memory_percent']
                name = p.info['name']
                cmd = " ".join(p.info['cmdline'] or [])
                if name.startswith("python") or name.startswith("node"):
                    for arg in p.info['cmdline'][1:]:
                        if os.path.exists(arg) or arg.endswith('.py') or arg.endswith('.js'):
                            name = f"{name} ({os.path.basename(arg)})"
                            break
                details = cmd[:50] + "..." if len(cmd) > 50 else cmd
                row_color = p.info['color']
                if cpu > 20: row_color = C.ALERT
                if "SYSTEM" in current_cat and cpu < 1.0 and len(procs) > 50:
                    continue
                print(f"{row_color}{pid:<8} {cpu:<8.1f} {mem:<8.1f} {name:<25} {details}{C.RESET}")

            print(f"\n{C.DIM}(Press Ctrl+C to Exit){C.RESET}")
            if snapshot: break
            time.sleep(REFRESH_RATE)
    except KeyboardInterrupt:
        print(f"\n{C.MY_STUFF}Exiting...{C.RESET}")
        sys.exit(0)

# --- Entry Point ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process Organizer & Security Scanner")
    parser.add_argument("--scan", help="Target directory or file to scan for security risks", type=str)
    parser.add_argument("--recursive", "-r", help="Scan directories recursively", action="store_true")
    parser.add_argument("--snapshot", help="Run monitor once and exit", action="store_true")
    parser.add_argument("--checklist", help="Show a summary checklist of risks", action="store_true")
    parser.add_argument("--view", help="Show grouped view (Known vs Unknown)", action="store_true")
    
    # New Arguments
    parser.add_argument("--known", help="List all trusted APIs and Domains", action="store_true")
    parser.add_argument("--trust", help="Add a new domain to the trusted list", type=str)
    parser.add_argument("--update-integrity", help="Update the known-good hash of this script (Run after editing)", action="store_true")
    parser.add_argument("--session-log", help="Path to an existing session log to attach to", type=str)
    parser.add_argument("--export-state", help="Export full system state and exit", action="store_true")

    args = parser.parse_args()

    # Attach to existing session if requested
    if args.session_log:
        from unified_logger import _current_log_file, _session_initialized
        import unified_logger
        unified_logger._current_log_file = args.session_log
        unified_logger._session_initialized = True
        # Re-initialize organizer logger to use the new file
        logging = get_logger("organizer")

    # Pre-Flight Integrity Check
    is_valid, msg = CM.verify_integrity()
    if not is_valid and not args.update_integrity:
        print(f"\n{C.ALERT}⚠️  SECURITY WARNING: Integrity Check Failed!{C.RESET}")
        print(f"{C.WARN}Reason: {msg}{C.RESET}")
        print(f"{C.WARN}If you made these changes, run: python3 process_organizer.py --update-integrity{C.RESET}\n")
        logging.critical(f"Startup Integrity Check Failed: {msg}")

    if args.update_integrity:
        CM.update_integrity()
    elif args.known:
        print(f"\n{C.HEADER}=== 🛡️  TRUSTED DOMAINS ==={C.RESET}")
        for domain in CM.known_apis:
            print(f"{C.MY_STUFF}✓ {domain}{C.RESET}")
    elif args.trust:
        CM.add_trust(args.trust)
    elif args.scan:
        view_mode = "standard"
        if args.checklist: view_mode = "checklist"
        if args.view: view_mode = "view"
        
        scanner_main(args.scan, args.recursive, view_mode)
    else:
        monitor_main(args.snapshot)