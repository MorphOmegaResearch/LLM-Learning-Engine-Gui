#!/usr/bin/env python3
"""
AI Research Tool — Queue Runner (standalone)

Manages a filesystem-backed queue for research jobs without modifying
the core runner (ai_search.py). Supports add/list/process/delete.

Notes
- Processing calls ai_search.py and will still prompt for TUI confirmation
  until the core supports a non-interactive confirm flag. This keeps the
  baseline safe and testable. Later we can add an --assume-yes flag to the core.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import string
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any


# Paths (mirror core tool conventions)
HOME = Path.home()
CONFIG_DIR = HOME / '.config' / 'ai_research_tool'
QUEUE_DIR = CONFIG_DIR / 'queue'
PROCESSED_DIR = QUEUE_DIR / 'processed'
FAILED_DIR = QUEUE_DIR / 'failed'
LOCK_FILE = CONFIG_DIR / 'profile.lock'
SETTINGS_FILE = CONFIG_DIR / 'config.json'
PROFILES_FILE = CONFIG_DIR / 'agent_profiles.json'

# Project paths
THIS_FILE = Path(__file__).resolve()
CORE_DIR = THIS_FILE.parent
CORE_RUNNER = CORE_DIR / 'ai_search.py'


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def acquire_lock() -> bool:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        try:
            data = LOCK_FILE.read_text().strip()
            parts = data.split(',')
            pid = int(parts[0]) if parts and parts[0].isdigit() else 0
            ts = float(parts[1]) if len(parts) > 1 else 0.0
        except Exception:
            pid, ts = 0, 0.0
        # Stale if PID gone or older than 2 hours
        if pid and _pid_alive(pid):
            return False
        # Stale lock, clear it
        try:
            LOCK_FILE.unlink()
        except Exception:
            return False
    try:
        LOCK_FILE.write_text(f"{os.getpid()},{time.time()}")
        return True
    except Exception:
        return False


def release_lock() -> None:
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except Exception:
        pass


def is_profile_busy() -> bool:
    if not LOCK_FILE.exists():
        return False
    try:
        data = LOCK_FILE.read_text().strip()
        parts = data.split(',')
        pid = int(parts[0]) if parts and parts[0].isdigit() else 0
        return pid > 0 and _pid_alive(pid)
    except Exception:
        return True


def load_settings() -> Dict[str, Any]:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        return json.load(open(SETTINGS_FILE)) or {}
    except Exception:
        return {}


def load_profiles() -> Dict[str, Any]:
    if not PROFILES_FILE.exists():
        return {}
    try:
        return json.load(open(PROFILES_FILE)) or {}
    except Exception:
        return {}


def _rand_hex(n: int = 8) -> str:
    return ''.join(random.choice('0123456789abcdef') for _ in range(n))


def _job_path() -> Path:
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    return QUEUE_DIR / f"{ts}_{_rand_hex()}.json"


def ensure_dirs():
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    FAILED_DIR.mkdir(parents=True, exist_ok=True)


def add_job(query: str, agent: str, headless: bool, source: str = 'CLI', note: str = '', return_to: str = 'ai_tool_menu', job_type: str = 'web_search', notify_to: str = '') -> Path:
    ensure_dirs()
    job = {
        "type": job_type or "web_search",
        "query": query,
        "agent": agent or 'duckduckgo',
        "headless": bool(headless),
        "source": source,
        "note": note,
        "created_at": datetime.now().isoformat(timespec='seconds'),
        "return_to": return_to,
        "notify_to": notify_to,
    }
    path = _job_path()
    tmp = Path(str(path) + '.tmp')
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(job, f, indent=2)
        tmp.rename(path)
    except Exception:
        # Fallback: try writing directly to final path
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(job, f, indent=2)
    return path


def list_jobs() -> List[Path]:
    ensure_dirs()
    return sorted(QUEUE_DIR.glob('*.json'))


def _load_job(p: Path) -> Dict[str, Any]:
    try:
        j = json.load(open(p)) or {}
    except Exception:
        j = {}
    j.setdefault('type', 'web_search')
    j.setdefault('agent', 'duckduckgo')
    j.setdefault('headless', True)
    j.setdefault('source', '?')
    j.setdefault('note', '')
    j.setdefault('notify_to', '')
    return j


def _group_by_type(paths: List[Path]) -> Dict[str, List[Path]]:
    groups: Dict[str, List[Path]] = {}
    for p in paths:
        jt = _load_job(p).get('type', 'web_search')
        groups.setdefault(jt, []).append(p)
    return groups


def _type_label(t: str) -> str:
    mapping = {
        'web_search': 'Web Research',
    }
    base = mapping.get(t, t.replace('_', ' ').title())
    return f"<{base}>"


def delete_job(idx: int) -> bool:
    jobs = list_jobs()
    if not (0 <= idx < len(jobs)):
        return False
    try:
        jobs[idx].unlink()
        return True
    except Exception:
        return False

def delete_job_path(p: Path) -> bool:
    try:
        p.unlink()
        return True
    except Exception:
        return False


def _snippet(text: str, words: int = 10) -> str:
    w = text.split()
    return ' '.join(w[:words]) + ('' if len(w) <= words else ' …')


def _eta_seconds(jobs: List[Path]) -> int:
    profiles = load_profiles()
    total = 0.0
    for j in jobs:
        try:
            job = json.load(open(j))
            agent = job.get('agent', 'duckduckgo')
            avg = float((profiles.get(agent) or {}).get('avg_response_time', 0.0))
            total += max(avg, 10.0)  # assume at least 10s if unknown
        except Exception:
            total += 10.0
    return int(total)


def print_list(type_filter: str | None = None):
    jobs = list_jobs()
    if not jobs:
        print("\nQueue is empty.")
        return
    groups = _group_by_type(jobs)
    total = len(jobs)
    print(f"\nQueued jobs: {total}")
    print("Types:")
    for t, plist in groups.items():
        print(f" - {_type_label(t)}: {len(plist)}")
    print("(New type? Press [H] Help for wiring instructions.)")

    # Apply optional filter
    if type_filter is not None:
        jobs = [p for p in jobs if _load_job(p).get('type','web_search') == type_filter]
        print(f"\nShowing: {_type_label(type_filter)} ({len(jobs)})")
    else:
        print("\nShowing: All items")

    print("\nItems:")
    for i, p in enumerate(jobs, 1):
        try:
            j = _load_job(p)
            sn = _snippet(j.get('query', ''))
            note = j.get('note')
            note_part = f" | note={note}" if note else ''
            mode = 'Headless' if j.get('headless', True) else 'Visible'
            jtype = j.get('type','web_search')
            notify = j.get('notify_to')
            notify_part = f" | notify={notify}" if notify else ''
            print(f" {i:2d}. {p.name} :: {sn} | type={jtype} | agent={j.get('agent','duckduckgo')} | mode={mode} | source={j.get('source','?')}{note_part}{notify_part}")
        except Exception:
            print(f" {i:2d}. {p.name}")
    eta = _eta_seconds(jobs)
    if eta > 0:
        mins = eta // 60
        secs = eta % 60
        print(f"\nEstimated time to process all: ~{mins}m {secs}s")


def _run_core(query: str, agent: str, headless: bool) -> int:
    """Invoke the core runner; returns exit code. Confirmation remains in place."""
    if not CORE_RUNNER.exists():
        print(f"Core runner not found: {CORE_RUNNER}")
        return 2
    cmd = ['python3', str(CORE_RUNNER)]
    if headless:
        cmd.append('--headless')
    else:
        cmd.append('--visible')
    if agent:
        cmd.extend(['--agent', agent])
    # Process queued jobs unattended (skip TUI confirm) and avoid double-locking
    cmd.append('--assume-yes')
    cmd.append('--no-lock')
    cmd.append(query)
    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        return 130
    except Exception:
        return 1


def process_one(idx: int) -> bool:
    jobs = list_jobs()
    if not (0 <= idx < len(jobs)):
        print("Invalid job number")
        return False
    p = jobs[idx]
    return process_path(p)


def process_path(p: Path) -> bool:
    try:
        job = json.load(open(p))
        query = job.get('query', '')
        if not query:
            raise ValueError('Empty query')
        agent = job.get('agent', 'duckduckgo')
        headless = bool(job.get('headless', True))
        jtype = job.get('type', 'web_search')

        if not acquire_lock():
            print("Profile is busy. Try again later.")
            return False
        try:
            print(f"\n▶ Processing job: {p.name} → {query}")
            if jtype == 'web_search':
                rc = _run_core(query, agent, headless)
            elif jtype == 'bait_task':
                print("This is a demo 'bait_task' type. No driver is configured; marking as failed.")
                rc = 1
            else:
                print(f"Unsupported job type: {jtype}. Move to failed and consult help.")
                rc = 1
            dest_dir = PROCESSED_DIR if rc == 0 else FAILED_DIR
            dest = dest_dir / p.name
            p.rename(dest)
            print("✓ Done" if rc == 0 else f"✗ Failed (exit {rc})")
            return rc == 0
        finally:
            release_lock()
    except Exception as e:
        print(f"Error processing {p.name}: {e}")
        try:
            dest = FAILED_DIR / p.name
            p.rename(dest)
        except Exception:
            pass
        return False


def process_all() -> int:
    jobs = list_jobs()
    if not jobs:
        print("\nQueue is empty.")
        return 0
    ok = 0
    for i in range(len(jobs)):
        # list_jobs() updates as we rename; always process first file
        current = list_jobs()
        if not current:
            break
        if process_one(0):
            ok += 1
    print(f"\n✓ Queue processing complete. Jobs succeeded: {ok}")
    return ok


def _help_types():
    print("\nTask Types (extensible)")
    print("- web_search: Uses ai_search.py to run a query against an agent (duckduckgo by default).")
    print("- custom types: You can define other types (e.g., 'code_task', 'data_fetch').")
    print("  To support them, extend queue_runner.py to route by job['type'] and call a driver script.")
    print("  Example stub: if type == 'code_task': call scripts/YourTool/code_task.py with job payload.")
    print("\nJob schema (JSON)")
    print("{")
    print("  'type': 'web_search',     # required")
    print("  'query': '...',           # required for web_search")
    print("  'agent': 'duckduckgo',    # optional (defaults)")
    print("  'headless': true,         # optional")
    print("  'note': '...',            # optional")
    print("  'notify_to': 'userX',     # optional (for notifications later)")
    print("  'source': 'CLI',          # optional (provenance)")
    print("  'created_at': 'ISO8601',  # set by queue_runner")
    print("  'return_to': 'ai_tool_menu' # optional (where to route after)")
    print("}")
    print("\nWhere to wire:")
    print(f"- Queue runner: {THIS_FILE}")
    print("- Core web search script: scripts/Web_tools/ai_search.py")
    print("- Config directory: ~/.config/ai_research_tool (queue/, processed/, failed/, profiles)")
    print("\nHow to add a new type")
    print("1) Add a routing branch in process_path() for your type.")
    print("2) Implement a driver script that reads the job payload and performs the task.")
    print("3) Add an option in 'Add Job → Select type' to capture type‑specific fields.")
    print("4) Extend list/inspect displays if your type has notable fields.")
    print("\nTips:")
    print("- Keep drivers isolated to avoid breaking the web search flow.")
    print("- Use notify_to/return_to for routing and future notifications.")
    print("\nQueue Commands (View Queue)")
    print("- Enter numbers/ranges to run selected jobs: e.g., '3,5,7' or '2-4'")
    print("- [S] Batch Sequence: run all jobs in the current type scope")
    print("- [C] Cycle Types: switch between known task types")
    print("- [V] View All: show the full queue across types")
    print("- [I] Integrations: detect placeholder types and show wiring help")
    print("- Inspect supports [T] Promote to top")
    print("\nSafety & Locks")
    print("- Queue runner holds a single profile lock while calling the core.")
    print("- Core runner is invoked with --assume-yes --no-lock to avoid deadlocks.")


def interactive_menu():
    ensure_dirs()
    settings = load_settings()
    default_agent = settings.get('default_agent', 'duckduckgo')
    default_headless = settings.get('default_headless', True)
    while True:
        print("\n" + "="*70)
        print("  RESEARCH QUEUE")
        print("="*70)
        if is_profile_busy():
            print("[RUNNING] Profile in use. Sequencer/runner currently active.")
        print("[1] Add job (enqueue)")
        print("[2] View queue (inspect/process)")
        # [3] and [4] moved into View Queue UX
        print("[5] Delete queued tasks")
        print("[H] Help (types/how to extend)")
        print("[W] Web Research (open tool menu)")
        print("[X] Exit")
        sel = input("Select: ").strip().upper()
        if sel == '1':
            # Choose task type first
            while True:
                print("\nAdd Job → Select type")
                print("[1] Web Research")
                print("[2] Bait Task (demo, unsupported)")
                print("[B] Back")
                tsel = input("Select: ").strip().upper()
                if tsel == 'B':
                    break
                if tsel == '1':
                    q = input("Enter research query: ").strip()
                    if not q:
                        continue
                    words = len(q.split())
                    if words > 10:
                        print("\nLong task detected (>10 words). Preview:")
                        print("-"*60)
                        print(q)
                        print("-"*60)
                        ans = input("[C]onfirm enqueue | [E]dit | [X]Cancel: ").strip().upper()
                        if ans == 'X':
                            continue
                        if ans == 'E':
                            q2 = input("Edit query: ").strip()
                            if q2:
                                q = q2
                    note = input("Note (optional): ").strip()
                    notify = input("Notify to (optional, e.g., email/user): ").strip()
                    path = add_job(q, default_agent, default_headless, source='QUEUE_MENU', note=note, job_type='web_search', notify_to=notify)
                    print(f"\n✓ Enqueued: {path}")
                    input("Press ENTER to continue...")
                    break
                if tsel == '2':
                    payload = input("Enter any text payload for bait task: ").strip()
                    note = input("Note (optional): ").strip()
                    path = add_job(payload or '(empty)', default_agent, default_headless, source='QUEUE_MENU', note=note, job_type='bait_task', notify_to='')
                    print(f"\n✓ Enqueued bait task: {path}")
                    input("Press ENTER to continue...")
                    break
        elif sel == '2':
            view_and_inspect_queue()
        elif sel == '3' or sel == '4':
            print("\nThese actions moved into [2] View queue → Inspect/Run.\n")
            input("Press ENTER to continue...")
        elif sel == '5':
            delete_menu()
        elif sel == 'H':
            _help_types()
            input("\nPress ENTER to continue...")
        elif sel == 'W':
            # Open the web research tool main menu
            try:
                if CORE_RUNNER.exists():
                    subprocess.run(['python3', str(CORE_RUNNER)])
                else:
                    print(f"\nWeb research tool not found at: {CORE_RUNNER}")
                input("\nPress ENTER to return to queue menu...")
            except Exception as e:
                print(f"\nError launching web research tool: {e}")
                input("\nPress ENTER to continue...")
        elif sel == 'X':
            break
        else:
            print("Invalid option")


def main():
    ensure_dirs()
    ap = argparse.ArgumentParser(description='AI Research Queue Runner', add_help=True)
    ap.add_argument('--add', metavar='QUERY', help='Add a job with the given query')
    ap.add_argument('--type', default='web_search', help='Job type (default: web_search)')
    ap.add_argument('--agent', default=None, help='Agent for added job (default from settings)')
    ap.add_argument('--headless', action='store_true', help='Headless for added job')
    ap.add_argument('--visible', action='store_true', help='Visible for added job')
    ap.add_argument('--note', default='', help='Optional note for added job')
    ap.add_argument('--notify-to', default='', help='Optional notify target (user/email/etc)')
    ap.add_argument('--source', default='CLI', help='Source tag for added job')
    ap.add_argument('--list', action='store_true', help='List queued jobs')
    ap.add_argument('--process-one', type=int, metavar='N', help='Process job by number (1-based)')
    ap.add_argument('--process-all', action='store_true', help='Process all jobs')
    ap.add_argument('--delete', type=int, metavar='N', help='Delete job by number (1-based)')
    args = ap.parse_args()

    if args.add is None and not (args.list or args.process_one or args.process_all or args.delete):
        # Interactive mode
        interactive_menu()
        return

    settings = load_settings()
    if args.add is not None:
        agent = args.agent or settings.get('default_agent', 'duckduckgo')
        headless = settings.get('default_headless', True)
        if args.visible:
            headless = False
        if args.headless:
            headless = True
        p = add_job(args.add, agent, headless, source=args.source, note=args.note, job_type=args.type, notify_to=args.notify_to)
        print(p)
        return

    if args.list:
        print_list()
        return

    if args.delete is not None:
        jobs = list_jobs()
        if not (1 <= args.delete <= len(jobs)):
            print("Invalid job number")
            sys.exit(2)
        p = jobs[args.delete - 1]
        confirm = input(f"Delete {p.name}? [y/N]: ").strip().lower()
        if confirm == 'y':
            ok = delete_job(args.delete - 1)
            sys.exit(0 if ok else 2)
        else:
            print("Cancelled")
            sys.exit(1)

    if args.process_one is not None:
        ok = process_one(args.process_one - 1)
        sys.exit(0 if ok else 1)

    if args.process_all:
        ok = process_all()
        sys.exit(0 if ok > 0 else 1)


def _print_job_details(p: Path, job: Dict[str, Any]):
    print("\n" + "-"*70)
    print(f"Job: {p.name}")
    print(f"Path: {p}")
    print(f"Type: {job.get('type','web_search')}")
    print(f"Created: {job.get('created_at','')}")
    print(f"Source: {job.get('source','')}")
    print(f"Return To: {job.get('return_to','')}")
    print("-"*70)
    print(f"Query: {job.get('query','')}")
    print(f"Agent: {job.get('agent','duckduckgo')}")
    print(f"Mode: {'Headless' if job.get('headless', True) else 'Visible'}")
    print(f"Note: {job.get('note','')}")
    print(f"Notify To: {job.get('notify_to','')}")
    print("-"*70)


def edit_job(p: Path) -> bool:
    try:
        job = json.load(open(p))
    except Exception as e:
        print(f"Cannot load job: {e}")
        return False
    print("\nEdit fields (leave blank to keep current)")
    new_agent = input(f"Agent [{job.get('agent','duckduckgo')}]: ").strip()
    new_mode = input(f"Mode H=headless / V=visible [{'H' if job.get('headless', True) else 'V'}]: ").strip().upper()
    new_note = input(f"Note [{job.get('note','')}]: ").strip()
    new_notify = input(f"Notify To [{job.get('notify_to','')}]: ").strip()
    new_return = input(f"Return To [{job.get('return_to','ai_tool_menu')}]: ").strip()
    if new_agent:
        job['agent'] = new_agent
    if new_mode in ('H','V'):
        job['headless'] = (new_mode == 'H')
    if new_note != '':
        job['note'] = new_note
    if new_notify != '':
        job['notify_to'] = new_notify
    if new_return != '':
        job['return_to'] = new_return
    # atomic write
    tmp = Path(str(p) + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(job, f, indent=2)
    tmp.rename(p)
    print("\n✓ Job updated")
    return True


def inspect_job(p: Path):
    try:
        job = json.load(open(p))
    except Exception as e:
        print(f"Cannot open job: {e}")
        input("\nPress ENTER to continue...")
        return
    while True:
        _print_job_details(p, job)
        sel = input("[P]rocess now  [E]dit  [T] Promote to top  [D]elete  [B]ack: ").strip().upper()
        if sel == 'P':
            process_path(p)
            break
        elif sel == 'E':
            if edit_job(p):
                try:
                    job = json.load(open(p))
                except Exception:
                    pass
        elif sel == 'T':
            if promote_job(p):
                print("\n✓ Promoted to top of queue")
            else:
                print("\n✗ Promote failed")
            input("\nPress ENTER to continue...")
            break
        elif sel == 'D':
            if delete_job_path(p):
                print("\n✓ Job deleted")
            else:
                print("\n✗ Delete failed")
            break
        elif sel == 'B':
            break
        else:
            print("Invalid option")


def view_and_inspect_queue():
    # Determine default filter: latest job type if any
    current_filter = None
    jobs = list_jobs()
    if jobs:
        latest = max(jobs)  # filenames are timestamped
        current_filter = _load_job(latest).get('type', 'web_search')
    while True:
        jobs = list_jobs()
        groups = _group_by_type(jobs)
        types = list(groups.keys())
        print_list(current_filter)
        if not jobs:
            input("\nPress ENTER to return...")
            return
        # New UX: numbers run, commands control view
        print("\nCommands: [V] View All  [C] Cycle Types  [S] Batch Sequence  [I] Integrations  [X] Back")
        entry = input("Enter numbers to run (e.g., 3,5,7 or 2-4), or command: ").strip().upper()
        if entry == 'X':
            return
        if entry == 'V':
            current_filter = None
            continue
        if entry == 'C':
            if not types or len(types) <= 1:
                print("\nNo other types to cycle. Showing integrations help and all items.")
                integrations_check()
                current_filter = None
                input("\nPress ENTER to continue...")
                continue
            if current_filter is None:
                # Move to first type
                current_filter = types[0]
            else:
                try:
                    idx = types.index(current_filter)
                    current_filter = types[(idx + 1) % len(types)]
                except ValueError:
                    current_filter = types[0]
            continue
        if entry == 'S':
            # Run all in current filter scope
            scope = list_jobs()
            if current_filter is not None:
                scope = [p for p in scope if _load_job(p).get('type','web_search') == current_filter]
            if not scope:
                print("\nNo items in this scope.")
                input("\nPress ENTER to continue...")
                continue
            confirm = input(f"Run all {len(scope)} job(s) in this scope? [y/N]: ").strip().lower()
            if confirm == 'y':
                ok = 0
                for p in scope:
                    if process_path(p):
                        ok += 1
                print(f"\n✓ Done. Succeeded: {ok}/{len(scope)}")
                input("\nPress ENTER to continue...")
            continue
        if entry == 'I':
            integrations_check()
            input("\nPress ENTER to continue...")
            continue
        # Treat as selection list
        nums = _parse_selection_list(entry, 9999)
        if not nums:
            print("Invalid selection or command.")
            continue
        scope = list_jobs()
        if current_filter is not None:
            scope = [p for p in scope if _load_job(p).get('type','web_search') == current_filter]
        # Ensure consistent ordering
        succeeded = 0
        for n in nums:
            idx = n - 1
            if 0 <= idx < len(scope):
                if process_path(scope[idx]):
                    succeeded += 1
        print(f"\n✓ Ran {succeeded}/{len(nums)} selected job(s)")
        input("\nPress ENTER to continue...")


def promote_job(p: Path) -> bool:
    try:
        ts = "00000000_000000"
        new_name = f"{ts}_{_rand_hex()}.json"
        dest = p.parent / new_name
        p.rename(dest)
        return True
    except Exception:
        return False


def integrations_check():
    jobs = list_jobs()
    groups = _group_by_type(jobs)
    interesting = ['code_task', 'plan_task', 'calendar_task']
    found = {t: len([p for p in jobs if _load_job(p).get('type') == t]) for t in interesting}
    print("\nIntegrations status:")
    for t in interesting:
        label = _type_label(t)
        count = found[t]
        print(f"- {label}: {count} queued")
    if all(count == 0 for count in found.values()):
        print("\nNo tasks of the above types detected.")
        print("Launching Help with wiring instructions…")
        _help_types()


def _parse_selection_list(s: str, max_n: int) -> List[int]:
    s = s.strip()
    out: List[int] = []
    if not s:
        return out
    parts = [p.strip() for p in s.split(',') if p.strip()]
    for part in parts:
        if '-' in part:
            try:
                a, b = part.split('-', 1)
                a = int(a)
                b = int(b)
                if a > b:
                    a, b = b, a
                for n in range(a, b + 1):
                    if 1 <= n <= max_n:
                        out.append(n)
            except ValueError:
                continue
        else:
            try:
                n = int(part)
                if 1 <= n <= max_n:
                    out.append(n)
            except ValueError:
                continue
    # deduplicate preserve order
    seen = set()
    res = []
    for n in out:
        if n not in seen:
            seen.add(n)
            res.append(n)
    return res


def delete_menu():
    while True:
        jobs = list_jobs()
        groups = _group_by_type(jobs)
        types = list(groups.keys())
        print_list()
        if not jobs:
            input("\nPress ENTER to return...")
            return
        print("\nChoose a filter for deletion:")
        line = ["[A] All items"]
        for idx, t in enumerate(types, 1):
            line.append(f"[{idx}] {_type_label(t)} ({len(groups[t])})")
        line.append("[B] Back")
        print("  " + "  ".join(line))
        fsel = input("Select filter [A/1..N/B]: ").strip().upper()
        type_filter = None
        if fsel == 'B':
            return
        if fsel != 'A':
            try:
                fi = int(fsel) - 1
                if 0 <= fi < len(types):
                    type_filter = types[fi]
                else:
                    print("Invalid filter; showing All")
            except ValueError:
                print("Invalid filter; showing All")
        # List scope
        scope = list_jobs()
        if type_filter is not None:
            scope = [p for p in scope if _load_job(p).get('type','web_search') == type_filter]
        print_list(type_filter)
        sel = input("\nEnter numbers to delete (e.g., 1,3-5) or 'ALL', [B]ack: ").strip().upper()
        if sel == 'B':
            return
        if sel == 'ALL':
            nums = list(range(1, len(scope) + 1))
        else:
            nums = _parse_selection_list(sel, len(scope))
        if not nums:
            print("Nothing selected.")
            input("\nPress ENTER to continue...")
            continue
        confirm = input(f"Delete {len(nums)} job(s)? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("Cancelled")
            input("\nPress ENTER to continue...")
            continue
        deleted = 0
        # Recompute scope before deletion to keep numbers aligned
        scope = list_jobs()
        if type_filter is not None:
            scope = [p for p in scope if _load_job(p).get('type','web_search') == type_filter]
        for n in nums:
            idx = n - 1
            if 0 <= idx < len(scope):
                if delete_job_path(scope[idx]):
                    deleted += 1
        print(f"\n✓ Deleted {deleted} job(s)")
        input("\nPress ENTER to continue...")


if __name__ == '__main__':
    main()
