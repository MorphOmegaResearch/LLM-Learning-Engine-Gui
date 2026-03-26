#!/usr/bin/env python3
"""
AI Search Tool - Phase 1: Anonymous Perplexity Search
Provides web research capability with isolated browser automation
"""

import asyncio
import sys
import os
import subprocess
import json
import time
import argparse
from playwright.async_api import async_playwright, TimeoutError
from pathlib import Path
from datetime import datetime

# Configuration
PROFILE_PATH = "/home/commander/snap/firefox/common/.mozilla/firefox/gmfcg3p3.Automation"
RESULTS_DIR = Path("/home/commander/Custom_Applications/Research_Results")
TIMEOUT = 60000  # 60 seconds

# Agent Profiling
PROFILE_CONFIG_DIR = Path.home() / '.config' / 'ai_research_tool'
PROFILE_FILE = PROFILE_CONFIG_DIR / 'agent_profiles.json'
SETTINGS_FILE = PROFILE_CONFIG_DIR / 'config.json'
AGENTS_FILE = PROFILE_CONFIG_DIR / 'agents.json'
SESSION_FILE = PROFILE_CONFIG_DIR / 'tui_session.json'
LOCK_FILE = PROFILE_CONFIG_DIR / 'profile.lock'
SETTINGS_FILE = PROFILE_CONFIG_DIR / 'config.json'
AGENTS_FILE = PROFILE_CONFIG_DIR / 'agents.json'

# Default settings (overridden by config.json and CLI flags)
DEFAULT_SETTINGS = {
    "default_headless": True,
    "on_captcha": "retry_visible",  # show_gui|fail|retry_visible
    "on_error": "retry_visible",    # retry_visible|stay_headless
    "debug": False,
    "default_format": "txt",       # txt|md|json (future)
    "save_both_text_and_md": False,
    "results_dir": str(RESULTS_DIR),
    "text_viewer": "mousepad",
    "session_root_dir": str(RESULTS_DIR / 'sessions'),
    "max_session_file_kb": 512,
    "max_messages_per_file": 100,
    "default_agent": "duckduckgo",
    "queue_on_tui_active": True,
    "queue_on_lock": True,
    "trusted_cli_user": False,
    "default_submit": "confirm",
    "trust_level": "low"
}

# Trust presets (do not disable queue_on_lock for safety)
TRUST_PRESETS = {
    "low": {
        "trusted_cli_user": False,
        "default_submit": "confirm",
        "queue_on_tui_active": True
    },
    "medium": {
        "trusted_cli_user": False,  # Shows review for visibility
        "default_submit": "queue",
        "queue_on_tui_active": True
    },
    "high": {
        "trusted_cli_user": True,
        "default_submit": "queue",
        "queue_on_tui_active": False
    }
}

def apply_trust_level(s: dict, level: str) -> dict:
    level = level.lower()
    if level not in TRUST_PRESETS:
        level = "low"
    preset = TRUST_PRESETS[level]
    s.update(preset)
    s["trust_level"] = level
    return s

DEFAULT_AGENTS = {
    "duckduckgo": {
        "name": "DuckDuckGo AI",
        "url": "https://duck.ai",
        "auth_required": False,
        "captcha_profile": "chill",
        "selectors": {
            "input": [
                'textarea[placeholder*="Ask"]',
                'textarea[name="user-prompt"]',
                'textarea',
                'input[type="text"]'
            ],
            "response": [
                'div[data-testid*="message"]',
                'div[data-testid*="response"]',
                'div[data-testid*="answer"]',
                'article',
                'div[role="article"]',
                'div[class*="message"]',
                'div[class*="response"]',
                'div[class*="answer"]',
                'div[class*="result"]',
                'main > div',
                'main'
            ]
        }
    }
}

def is_interactive():
    """Check if script is running in an interactive terminal"""
    return sys.stdin.isatty()

def spawn_in_terminal():
    """Spawn this script in a new terminal window for interactive use"""
    import shlex
    import subprocess

    # Create TUI marker BEFORE spawning to prevent race condition
    # Use a special "spawning" PID (negative) that will be updated by spawned process
    try:
        PROFILE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        json.dump({"pid": -1, "started_at": datetime.now().isoformat(), "status": "spawning"},
                  open(SESSION_FILE, 'w'))
    except Exception:
        pass

    # Reconstruct the command with all arguments
    cmd = [sys.executable] + sys.argv

    # Properly escape for shell
    cmd_str = ' '.join(shlex.quote(arg) for arg in cmd)

    # Try different terminal emulators (XFCE first, then fallbacks)
    terminals = [
        ['xfce4-terminal', '--hold', '-e', f'bash -c "{cmd_str}; exec bash"'],
        ['gnome-terminal', '--', 'bash', '-c', f'{cmd_str}; read -p "Press ENTER to close..."'],
        ['xterm', '-hold', '-e', 'bash', '-c', cmd_str],
    ]

    for term_cmd in terminals:
        try:
            subprocess.Popen(term_cmd)
            return True
        except FileNotFoundError:
            continue
        except Exception:
            continue

    # If spawn failed, remove marker
    try:
        if SESSION_FILE.exists():
            SESSION_FILE.unlink()
    except Exception:
        pass

    print("❌ Could not spawn terminal window. Please run manually.")
    return False

def print_tui_banner():
    """Display TUI confirmation interface"""
    print("\n" + "="*70)
    print("  AI RESEARCH TOOL - QUERY REVIEW")
    print("="*70)

def get_user_confirmation(query: str, agent: str = "duckduckgo") -> str:
    """Display query and get user decision via TUI.
    Returns: 'CONFIRM' | 'CANCEL' | 'QUEUE'
    """
    print_tui_banner()
    print(f"\nSearch Query:")
    print(f"  → {query}")

    agent_names = {
        "duckduckgo": "DuckDuckGo AI (duck.ai)",
        "perplexity": "Perplexity AI",
        "firefox": "Firefox AI Mode"
    }

    print(f"\nTarget Platform: {agent_names.get(agent, agent)} (Anonymous Mode)")
    settings = None
    try:
        settings = load_settings()
    except Exception:
        settings = None
    results_dir = settings.get("results_dir") if settings else str(RESULTS_DIR)
    mode = "Headless" if (settings and settings.get("default_headless", True)) else "Visible"
    print(f"Browser Profile: {PROFILE_PATH}")
    print(f"Results Directory: {results_dir}")
    print(f"Mode: {mode}")
    print("\n" + "-"*70)

    print("\nInline Options: [A]gent | [V]isibility (Headless/GUI) | [C]onfirm | [Q]ueue | [X]Cancel")
    while True:
        response = input("Select: ").strip().upper()
        if response == 'C':
            return 'CONFIRM'
        elif response == 'X':
            print("\n❌ Search cancelled by user.")
            return 'CANCEL'
        elif response == 'Q':
            return 'QUEUE'
        elif response == 'A':
            switch_agent_menu()
            # Refresh display with possibly changed agent/dir/mode
            return get_user_confirmation(query, load_settings().get('default_agent','duckduckgo'))
        elif response == 'V':
            toggle_headless()
            return get_user_confirmation(query, agent)
        else:
            print("Invalid input. Use A/V/C/X.")

def generate_filename(query: str) -> str:
    """Generate timestamped filename with query summary"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # Create short query summary (first few words, sanitized)
    query_words = query.split()[:5]  # First 5 words
    summary = "_".join(query_words).replace('"', '').replace("'", '')
    # Sanitize filename
    summary = "".join(c if c.isalnum() or c in "_- " else "" for c in summary)
    summary = summary.replace(" ", "_")[:50]  # Limit length
    return f"{timestamp}_{summary}.txt"

def clean_duckduckgo_response(raw_text):
    """Remove UI elements from DuckDuckGo AI response"""
    lines = raw_text.split('\n')

    # Find start of actual response (after query echo + model name)
    start_markers = ["GPT-4", "Claude", "Llama", "Mistral", "o3-mini"]
    response_start = 0

    for i, line in enumerate(lines):
        if any(marker in line for marker in start_markers):
            response_start = i + 2  # Skip model name line + blank line
            break

    # Find end (before footer/disclaimer)
    end_markers = ["AI may display inaccurate", "Share Feedback", "DuckDuckGo"]
    response_end = len(lines)

    for i in range(response_start, len(lines)):
        if any(marker in lines[i] for marker in end_markers):
            response_end = i
            break

    # Extract clean response
    clean_lines = lines[response_start:response_end]

    # Remove empty lines at start/end
    while clean_lines and not clean_lines[0].strip():
        clean_lines.pop(0)
    while clean_lines and not clean_lines[-1].strip():
        clean_lines.pop()

    return '\n'.join(clean_lines)

def sanitize_text(text: str) -> str:
    """Light sanitize: remove stray tag fragments and excess blank lines."""
    lines = text.split('\n')
    cleaned = []
    for ln in lines:
        s = ln.strip()
        if s in ("</", "<>", "/>"):
            continue
        cleaned.append(ln)
    # Collapse 3+ blank lines to max 1
    out = []
    blank = 0
    for ln in cleaned:
        if ln.strip() == "":
            blank += 1
            if blank > 1:
                continue
        else:
            blank = 0
        out.append(ln)
    return '\n'.join(out)

def load_settings() -> dict:
    PROFILE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(DEFAULT_SETTINGS, f, indent=2)
        return DEFAULT_SETTINGS.copy()
    try:
        with open(SETTINGS_FILE, 'r') as f:
            data = json.load(f)
            merged = DEFAULT_SETTINGS.copy()
            merged.update(data or {})
            return merged
    except Exception:
        return DEFAULT_SETTINGS.copy()

def save_settings(settings: dict) -> None:
    PROFILE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)

def load_agents() -> dict:
    PROFILE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not AGENTS_FILE.exists():
        with open(AGENTS_FILE, 'w') as f:
            json.dump(DEFAULT_AGENTS, f, indent=2)
        return DEFAULT_AGENTS.copy()
    try:
        with open(AGENTS_FILE, 'r') as f:
            data = json.load(f)
            merged = DEFAULT_AGENTS.copy()
            merged.update(data or {})
            return merged
    except Exception:
        return DEFAULT_AGENTS.copy()

async def run_search(query: str, agent: str = "duckduckgo", headless: bool = False, runtime_settings: dict | None = None):
    """Execute the search with Playwright"""

    # Track profiling metrics
    start_time = time.time()
    captcha_occurred = False
    success = False

    # Ensure results directory exists
    settings = runtime_settings or load_settings()
    results_dir = Path(settings.get("results_dir", str(RESULTS_DIR)))
    results_dir.mkdir(parents=True, exist_ok=True)

    print("\n🚀 Launching browser...")

    agents = load_agents()
    if agent not in agents:
        print(f"⚠️  Unknown agent '{agent}', falling back to duckduckgo")
        agent = "duckduckgo"
    aconf = agents[agent]
    config = {
        "url": aconf.get("url", "https://duck.ai"),
        "name": aconf.get("name", agent),
        "selectors": aconf.get("selectors", {}).get("input", [
            'textarea[placeholder*="Ask"]', 'textarea']
        )
    }
    answer_selectors = aconf.get("selectors", {}).get("response", [
        'article', 'main']
    )

    async with async_playwright() as p:
        # Launch Firefox with isolated profile
        browser = await p.firefox.launch_persistent_context(
            user_data_dir=PROFILE_PATH,
            headless=headless,
            args=['--no-remote']
        )

        try:
            # Use existing page from persistent context (avoids blank page)
            page = browser.pages[0] if browser.pages else await browser.new_page()

            # Navigate to target platform
            print(f"📡 Navigating to {config['name']}...")
            await page.goto(config['url'], timeout=TIMEOUT)
            await page.wait_for_load_state("networkidle")

            # Look for search input
            print("🔍 Locating search interface...")
            search_selectors = config['selectors']

            search_box = None
            for selector in search_selectors:
                try:
                    search_box = await page.wait_for_selector(selector, timeout=5000)
                    if search_box:
                        print(f"✓ Found search input: {selector}")
                        break
                except:
                    continue

            if not search_box:
                print("\n⚠️  Could not locate search input automatically.")
                print("⏸️  PAUSED: Please complete the search manually if needed.")
                input("Press ENTER when ready to extract results...")
            else:
                # Enter query
                print(f"⌨️  Entering query: {query}")
                await search_box.fill(query)

                # Submit (look for submit button or press Enter)
                try:
                    submit_button = await page.wait_for_selector('button[type="submit"]', timeout=2000)
                    await submit_button.click()
                except:
                    await search_box.press('Enter')

                print("⏳ Waiting for results...")

                # Check for CAPTCHA first
                await page.wait_for_timeout(2000)
                captcha_present = await page.query_selector('iframe[title*="captcha"], iframe[src*="hcaptcha"]')
                if captcha_present:
                    captcha_occurred = True
                    print("\n⚠️  CAPTCHA detected!")
                    if headless:
                        # Defer handling to caller policy (retry visible, etc.)
                        print("Headless mode: deferring to CAPTCHA policy (no GUI available).")
                        return {"success": False, "captcha": True, "results_file": ""}
                    print("⏸️  PAUSED: Please complete the CAPTCHA in the browser window.")
                    input("Press ENTER after completing CAPTCHA...")
                    print("⏳ Waiting for AI response to generate...")

                # Wait longer for AI response (increased from 5s to 15s)
                await page.wait_for_timeout(15000)

                # Additional wait for streaming to complete
                print("⏳ Ensuring response is complete...")
                await page.wait_for_timeout(3000)

            # Extract results
            print("📥 Extracting results...")

            # Try to get the main content area
            content = await page.content()

            # Generate proper filename
            filename = generate_filename(query)
            results_file = results_dir / filename

            # Save results
            with open(results_file, 'w', encoding='utf-8') as f:
                f.write(f"AI RESEARCH TOOL - SEARCH RESULTS\n")
                f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Query: {query}\n")
                f.write("="*70 + "\n\n")

                # Try to extract AI response with duck.ai-specific and general selectors
                try:
                    extracted = False
                    for selector in answer_selectors:
                        elements = await page.query_selector_all(selector)
                        if elements:
                            for elem in elements:
                                text = await elem.inner_text()
                                if len(text) > 50:  # Has substantial content
                                    # Clean the response before writing
                                    cleaned_text = sanitize_text(clean_duckduckgo_response(text))
                                    if cleaned_text:  # Only write if cleaning produced content
                                        f.write(f"[Extracted via selector: {selector}]\n\n")
                                        f.write(cleaned_text + "\n\n")
                                        extracted = True
                                        print(f"✓ Extracted and cleaned content using: {selector}")
                                        break
                            if extracted:
                                break

                    if not extracted:
                        # Ultimate fallback: get all visible text
                        print("⚠️  Using fallback: extracting all visible text")
                        body = await page.query_selector('body')
                        if body:
                            all_text = await body.inner_text()
                            f.write("[Fallback: Full page text]\n\n")
                            f.write(all_text)
                            extracted = True  # Fallback still counts as extraction
                        else:
                            f.write("ERROR: Could not extract any content\n")
                except Exception as e:
                    f.write(f"Error extracting content: {e}\n\n")
                    f.write("RAW HTML:\n")
                    f.write(content)

            # Mark success if extraction worked
            if extracted:
                success = True

            # Update agent profile with query results
            response_time = time.time() - start_time
            update_profile(agent, query, success, captcha_occurred, response_time)

            print(f"\n✅ Results saved to:")
            print(f"   {results_file}")
            if not headless:
                print("\n⏸️  Browser will remain open for review.")
                input("Press ENTER to close browser and exit...")

        except Exception as e:
            print(f"\n❌ Error during search: {e}")
            if not headless:
                print("⏸️  Browser will remain open for inspection.")
                input("Press ENTER to close browser and exit...")

        finally:
            await browser.close()

    return {
        "success": success,
        "captcha": captcha_occurred,
        "results_file": str(results_file)
    }

def _session_paths(settings: dict, title: str, fmt: str):
    from pathlib import Path as _P
    root = _P(settings.get("session_root_dir", str(RESULTS_DIR / 'sessions')))
    ts = datetime.now().strftime('%Y-%m-%d_%H-%M')
    slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in title) if title else "session"
    session_dir = root / f"{ts}_{slug}"
    session_dir.mkdir(parents=True, exist_ok=True)
    part = 1
    fname = lambda p: session_dir / f"{slug or 'session'}_part-{p:03d}.{fmt}"
    return session_dir, fname, part

def _append_session(session_dir, fname_fn, part, fmt, user_text, assistant_text, settings):
    import os
    import json
    path = fname_fn(part)
    try:
        if fmt == 'json':
            entry = {
                "timestamp": datetime.now().isoformat(),
                "user": user_text.strip(),
                "assistant": assistant_text.strip()
            }
            with open(path, 'a', encoding='utf-8') as f:
                json.dump(entry, f)
                f.write('\n')
        else:
            header_user = f"\n## User ({datetime.now().strftime('%H:%M:%S')})\n" if fmt == 'md' else f"\nUser ({datetime.now().strftime('%H:%M:%S')}):\n"
            header_assist = f"\n## Assistant ({datetime.now().strftime('%H:%M:%S')})\n" if fmt == 'md' else f"\nAssistant ({datetime.now().strftime('%H:%M:%S')}):\n"
            with open(path, 'a', encoding='utf-8') as f:
                f.write(header_user)
                f.write(user_text.strip() + "\n")
                f.write(header_assist)
                f.write(assistant_text.strip() + "\n")
    except Exception as e:
        print(f"❌ Error saving to session file: {e}")
        # Continue despite error

    # Rollover check (size and messages)
    max_kb = int(settings.get('max_session_file_kb', 512))
    max_messages = int(settings.get('max_messages_per_file', 100))
    if os.path.exists(path):
        if os.path.getsize(path) > max_kb * 1024 or sum(1 for _ in open(path)) > max_messages * 2:  # Rough message count
            part += 1
    return part, str(path)

async def chat_mode(agent: str, headless: bool, settings: dict):
    """Interactive chat loop; shows assistant output in TUI and saves session."""
    agents = load_agents()
    if agent not in agents:
        agent = settings.get('default_agent', 'duckduckgo')
    aconf = agents[agent]
    fmt = settings.get('default_format', 'txt')
    conversation_history = []

    # Session setup
    title = input("\nEnter session title (optional): ").strip()
    session_dir, fname_fn, part = _session_paths(settings, title, fmt)

    async with async_playwright() as p:
        browser = await p.firefox.launch_persistent_context(
            user_data_dir=PROFILE_PATH,
            headless=headless,
            args=['--no-remote']
        )
        try:
            page = browser.pages[0] if browser.pages else await browser.new_page()
            print(f"\n📡 Navigating to {aconf.get('name', agent)}...")
            await page.goto(aconf.get('url', 'https://duck.ai'), timeout=TIMEOUT)
            await page.wait_for_load_state("networkidle")

            # Attempt to find input once; reuse selector each turn
            input_selectors = aconf.get('selectors', {}).get('input', [
                'textarea[placeholder*="Ask"]', 'textarea'])
            search_box = None
            for sel in input_selectors:
                try:
                    search_box = await page.wait_for_selector(sel, timeout=5000)
                    if search_box:
                        break
                except:
                    continue

            if not search_box:
                print("⚠️  Could not locate chat input automatically.")
                if headless:
                    return {"success": False, "captcha": False}

            answer_selectors = aconf.get('selectors', {}).get('response', ['main'])

            print("\nEnter your message. Type /exit to finish.\n")
            while True:
                user_text = input("> ").strip()
                if user_text.lower() in ("/exit", ":q", "quit"):
                    break
                if not user_text:
                    continue
                if user_text.lower().startswith("/help"):
                    help_query = user_text[5:].strip() or "general usage"
                    user_text = f"Provide help on: {help_query}"

                # Build full message with history (last 3 turns)
                full_message = "\n".join(conversation_history[-3:]) + "\n" + user_text if conversation_history else user_text

                # Send message
                try:
                    await search_box.fill(full_message)
                    try:
                        submit_button = await page.wait_for_selector('button[type="submit"]', timeout=1500)
                        await submit_button.click()
                    except:
                        await search_box.press('Enter')

                    # CAPTCHA detection (headless)
                    await page.wait_for_timeout(1500)
                    captcha_present = await page.query_selector('iframe[title*="captcha"], iframe[src*="hcaptcha"]')
                    if captcha_present and headless:
                        print("\n⚠️  CAPTCHA detected during chat in headless mode.")
                        return {"success": False, "captcha": True}

                    # Wait for response with retry on timeout
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            await page.wait_for_timeout(15000)
                            await page.wait_for_timeout(3000)
                            break
                        except TimeoutError:
                            if attempt < max_retries - 1:
                                print(f"Timeout on attempt {attempt+1}, retrying...")
                            else:
                                print("Max retries exceeded for response wait.")
                                continue

                    # Extract latest assistant response
                    cleaned = None
                    for sel in answer_selectors:
                        elems = await page.query_selector_all(sel)
                        for elem in reversed(elems):
                            text = await elem.inner_text()
                            if len(text) > 50:
                                cleaned = sanitize_text(clean_duckduckgo_response(text))
                                if cleaned:
                                    break
                        if cleaned:
                            break
                    if not cleaned:
                        # Fallback
                        body = await page.query_selector('body')
                        cleaned = await body.inner_text() if body else "(no content)"

                    # Show in TUI
                    print("\nAssistant:\n" + cleaned + "\n")

                    # Update history
                    conversation_history.append(f"User: {user_text}\nAssistant: {cleaned}")

                    # Append to session file
                    part, last_path = _append_session(session_dir, fname_fn, part, fmt, user_text, cleaned, settings)
                except Exception as e:
                    print(f"\n❌ Error sending message: {e}")
                    continue
        finally:
            if not headless:
                input("\nPress ENTER to close browser...")
            try:
                await browser.close()
            except Exception as e:
                print(f"❌ Error closing browser: {e}")

    print(f"\nSession saved in: {session_dir}")
    input("\nPress ENTER to return to menu...")
    return {"success": True, "captcha": False}

def load_profiles():
    """Load agent profiles from config"""
    if not PROFILE_FILE.exists():
        return {}
    with open(PROFILE_FILE, 'r') as f:
        return json.load(f)

def save_profiles(profiles):
    """Save agent profiles to config"""
    PROFILE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROFILE_FILE, 'w') as f:
        json.dump(profiles, f, indent=2)

def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True

def is_tui_active() -> bool:
    try:
        if not SESSION_FILE.exists():
            return False
        data = json.load(open(SESSION_FILE))
        pid = int(data.get('pid', 0))
        # Special case: pid=-1 means "spawning" state (race condition prevention)
        if pid == -1:
            return True  # TUI is spawning, treat as active
        return pid > 0 and _pid_alive(pid)
    except Exception:
        return False

def mark_tui_active():
    try:
        PROFILE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        json.dump({"pid": os.getpid(), "started_at": datetime.now().isoformat()}, open(SESSION_FILE, 'w'))
    except Exception:
        pass

def clear_tui_active():
    try:
        if SESSION_FILE.exists():
            SESSION_FILE.unlink()
    except Exception:
        pass

# Profile lock helpers (prevent concurrent browser/profile access)
def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True

def acquire_lock() -> bool:
    PROFILE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        # Stale lock check
        try:
            data = LOCK_FILE.read_text().strip()
            parts = data.split(',')
            pid = int(parts[0]) if parts and parts[0].isdigit() else 0
        except Exception:
            pid = 0
        if pid and _pid_alive(pid):
            return False
        try:
            LOCK_FILE.unlink()
        except Exception:
            return False
    try:
        LOCK_FILE.write_text(f"{os.getpid()},{time.time()}")
        return True
    except Exception:
        return False

def release_lock():
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
        return pid and _pid_alive(pid)
    except Exception:
        return True

def cleanup_stale_lock():
    """Remove stale lock on startup if PID is dead"""
    if not LOCK_FILE.exists():
        return
    try:
        data = LOCK_FILE.read_text().strip()
        parts = data.split(',')
        pid = int(parts[0]) if parts and parts[0].isdigit() else 0
        if pid and not _pid_alive(pid):
            LOCK_FILE.unlink()
    except Exception:
        pass

def update_profile(agent, query, success, captcha_required, response_time):
    """Update agent profile with query result"""
    profiles = load_profiles()

    if agent not in profiles:
        profiles[agent] = {
            "last_used": "",
            "session_active": False,
            "captcha_count": 0,
            "query_count": 0,
            "avg_response_time": 0.0,
            "last_captcha": "",
            "success_rate": 100.0,
            "queries": []
        }

    profile = profiles[agent]

    # Update stats
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    profile["last_used"] = timestamp
    profile["query_count"] += 1

    if captcha_required:
        profile["captcha_count"] += 1
        profile["last_captcha"] = timestamp
        profile["session_active"] = True
    else:
        profile["session_active"] = True  # Session still active if no CAPTCHA needed

    # Update average response time
    old_avg = profile["avg_response_time"]
    count = profile["query_count"]
    profile["avg_response_time"] = ((old_avg * (count - 1)) + response_time) / count

    # Update success rate
    successes = sum(1 for q in profile["queries"] if q["success"]) + (1 if success else 0)
    profile["success_rate"] = (successes / count) * 100

    # Add query record
    profile["queries"].append({
        "timestamp": timestamp,
        "query": query[:50],  # Truncate long queries
        "success": success,
        "captcha_required": captcha_required,
        "response_time": response_time
    })

    # Keep only last 50 queries
    profile["queries"] = profile["queries"][-50:]

    save_profiles(profiles)

def display_agent_status():
    """Display agent status in menu"""
    profiles = load_profiles()
    agents = load_agents()

    print("\n" + "="*70)
    print("  AGENT STATUS")
    print("="*70)

    # Show all known agents, even if no usage yet
    def agent_script_path(name: str) -> str:
        mapping = {
            'duckduckgo': '/home/commander/Custom_Applications/scripts/Web_tools/duckduckgo_agent.py',
            'perplexity': '/home/commander/Custom_Applications/scripts/Web_tools/agents/perplexity_agent.py',
            'firefox_ai': '/home/commander/Custom_Applications/scripts/Web_tools/agents/firefox_ai_agent.py',
            'openai_chatgpt': '/home/commander/Custom_Applications/scripts/Web_tools/agents/openai_chatgpt_agent.py',
        }
        return mapping.get(name, '(n/a)')

    for agent_name, meta in agents.items():
        data = profiles.get(agent_name)
        print(f"\n{agent_name.upper()}:")
        print(f"  URL: {meta.get('url','')}")
        print(f"  Captcha Profile: {meta.get('captcha_profile','unknown')}  Auth Required: {meta.get('auth_required', False)}")
        print(f"  Config: ~/.config/ai_research_tool/agents.json")
        print(f"  Script: {agent_script_path(agent_name)}")
        if data:
            print(f"  Last Used: {data['last_used']}")
            print(f"  Session Active: {'Yes' if data['session_active'] else 'No'}")
            print(f"  Total Queries: {data['query_count']}")
            print(f"  CAPTCHA Count: {data['captcha_count']}")
            print(f"  Last CAPTCHA: {data['last_captcha'] or 'Never'}")
            print(f"  Avg Response Time: {data['avg_response_time']:.1f}s")
            print(f"  Success Rate: {data['success_rate']:.1f}%")
        else:
            print("  Usage: No queries yet.")

    input("\nPress ENTER to return to menu...")

def parse_filename(filename):
    """Extract timestamp and query from filename"""
    # Format: 2025-12-26_11-48-49_What_is_Python.txt
    parts = filename.replace('.txt', '').split('_')
    if len(parts) >= 3:
        date = parts[0]
        time = parts[1].replace('-', ':')
        # Everything after date and time is the query
        query = '_'.join(parts[2:]).replace('_', ' ')
        return f"{date} {time}", query
    return "Unknown", filename

def view_results():
    """List and open saved research results"""
    print("\n" + "="*70)
    print("  SAVED RESEARCH RESULTS")
    print("="*70)

    settings = load_settings()
    results_dir = Path(settings.get("results_dir", str(RESULTS_DIR)))
    files = sorted(results_dir.glob("*.txt"), reverse=True)

    if not files:
        print("\nNo results found.")
        input("\nPress ENTER to return to menu...")
        return

    # Display numbered list
    for i, file in enumerate(files, 1):
        timestamp, query = parse_filename(file.name)
        print(f"{i:2d}. {timestamp} - {query}")

    print("\n" + "-"*70)

    # Get user selection
    while True:
        choice = input("\nSelect [1-N] to open, [B]ack to menu, [X]Exit: ").strip().upper()

        if choice == 'B':
            return
        elif choice == 'X':
            sys.exit(0)

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(files):
                # Open in text viewer
                print(f"\nOpening: {files[idx].name}")
                viewer = load_settings().get('text_viewer', 'mousepad')
                subprocess.run([viewer, str(files[idx])])
                input("\nPress ENTER to continue...")
                return
            else:
                print(f"Please enter a number between 1 and {len(files)}")
        except ValueError:
            print("Invalid input. Enter a number, B, or X.")

def enqueue_job(query, agent, headless, source, notify=False):
    """Helper to enqueue a job via queue_runner"""
    try:
        runner = Path(__file__).parent / 'queue_runner.py'
        cmd = ['python3', str(runner), '--add', query, '--agent', agent]
        cmd.append('--headless' if headless else '--visible')
        cmd.extend(['--source', source])
        ret = subprocess.run(cmd, capture_output=True, text=True)

        # Write notification if requested
        if notify and ret.returncode == 0:
            queue_file = ret.stdout.strip()  # queue_runner returns path
            write_pending_notification(query, agent, source, queue_file)

        return ret.returncode == 0
    except Exception as e:
        print(f"\n✗ Failed to enqueue: {e}")
        return False

def write_pending_notification(query, agent, source, queue_file):
    """Write a pending review notification for auto-enqueued queries"""
    try:
        notification_file = PROFILE_CONFIG_DIR / 'pending_reviews.jsonl'
        notification = {
            'query': query,
            'agent': agent,
            'source': source,
            'enqueued_at': datetime.now().isoformat(),
            'queue_file': queue_file,
            'shown': False
        }
        with open(notification_file, 'a') as f:
            f.write(json.dumps(notification) + '\n')
    except Exception as e:
        # Silent fail - notification is nice-to-have
        pass

def get_pending_review_count():
    """Return count of pending web_search queue items"""
    queue_dir = PROFILE_CONFIG_DIR / 'queue'
    try:
        if not queue_dir.exists():
            return 0

        # Count web_search type queue entries
        count = 0
        for qf in queue_dir.glob('*.json'):
            try:
                with open(qf, 'r') as f:
                    entry = json.load(f)
                    if entry.get('type', 'web_search') == 'web_search':
                        count += 1
            except Exception:
                continue
        return count
    except Exception:
        return 0

def show_pending_reviews():
    """Show and manage pending web_search queue items"""
    queue_dir = PROFILE_CONFIG_DIR / 'queue'

    if not queue_dir.exists():
        print("\nNo queue directory found.")
        input("\nPress ENTER to return...")
        return

    # Read all web_search queue entries
    queue_files = sorted(queue_dir.glob('*.json'))
    web_search_items = []

    for qf in queue_files:
        try:
            with open(qf, 'r') as f:
                entry = json.load(f)
                if entry.get('type', 'web_search') == 'web_search':
                    web_search_items.append((qf, entry))
        except Exception:
            continue

    if not web_search_items:
        print("\nNo pending web search tasks in queue.")
        input("\nPress ENTER to return...")
        return

    while True:
        # Display queue items
        print("\n" + "="*70)
        print("  PENDING WEB SEARCH QUEUE")
        print("="*70)
        print(f"\nFound {len(web_search_items)} pending web search(es):\n")

        for i, (qf, entry) in enumerate(web_search_items, 1):
            query = entry.get('query', 'Unknown')
            source = entry.get('source', 'Unknown')
            created = entry.get('created_at', '')[:19]
            print(f"{i}. {query[:55]}")
            print(f"   Source: {source} | Created: {created}")

        print("\n" + "-"*70)
        print("[1-N] Select item | [1,2,3] Batch select | [A] Process All | [D] Delete All | [X] Return")
        choice = input("\nChoice: ").strip().upper()

        if choice == 'X':
            break
        elif ',' in choice:
            # Batch processing: parse comma-separated numbers
            try:
                indices = [int(x.strip()) - 1 for x in choice.split(',')]
                # Validate all indices
                invalid = [i+1 for i in indices if i < 0 or i >= len(web_search_items)]
                if invalid:
                    print(f"\n✗ Invalid selection(s): {invalid}")
                    input("\nPress ENTER to continue...")
                    continue

                # Show batch confirmation
                print(f"\n📋 Selected {len(indices)} item(s) for processing:")
                for idx in indices:
                    entry = web_search_items[idx][1]
                    print(f"  • {entry.get('query', 'Unknown')[:60]}")

                confirm = input("\n[P] Process batch | [C] Cancel: ").strip().upper()
                if confirm != 'P':
                    continue

                # Process batch in sequence
                processed_count = 0
                settings = load_settings()

                for batch_num, idx in enumerate(indices, 1):
                    qf, entry = web_search_items[idx]
                    query = entry.get('query')

                    print(f"\n{'='*70}")
                    print(f"BATCH ITEM {batch_num}/{len(indices)}: {query[:50]}")
                    print('='*70)

                    try:
                        agent = entry.get('agent', settings.get('default_agent', 'duckduckgo'))
                        headless = entry.get('headless', settings.get('default_headless', True))

                        # Acquire lock
                        if not acquire_lock():
                            print("⚠️  Profile busy. Skipping this item.")
                            continue

                        try:
                            # Run the search
                            asyncio.run(run_search(query, agent, headless, settings))

                            # Move to processed
                            processed_dir = qf.parent / 'processed'
                            processed_dir.mkdir(exist_ok=True)
                            qf.rename(processed_dir / qf.name)

                            print(f"✓ Item {batch_num}/{len(indices)} processed successfully.")
                            processed_count += 1
                        except KeyboardInterrupt:
                            print("\n⚠️  Batch processing interrupted by user")
                            release_lock()
                            break
                        finally:
                            release_lock()
                    except Exception as e:
                        print(f"✗ Error processing item: {e}")

                print(f"\n{'='*70}")
                print(f"✓ Batch complete: {processed_count}/{len(indices)} processed")
                print('='*70)
                input("\nPress ENTER to continue...")
                break

            except ValueError:
                print("\n✗ Invalid format. Use comma-separated numbers (e.g., 1,3,5)")
                input("\nPress ENTER to continue...")
                continue
        elif choice == 'A':
            # Process all via queue_runner
            print("\n🔄 Processing all web search tasks...")
            try:
                runner = Path(__file__).parent / 'queue_runner.py'
                if runner.exists():
                    subprocess.run(['python3', str(runner)])
                    print("\n✓ Queue processing complete.")
                    # Clear notifications
                    notif_file = PROFILE_CONFIG_DIR / 'pending_reviews.jsonl'
                    if notif_file.exists():
                        notif_file.unlink()
                else:
                    print(f"\n✗ Queue runner not found")
            except Exception as e:
                print(f"\n✗ Error: {e}")
            input("\nPress ENTER to continue...")
            break
        elif choice == 'D':
            # Delete all queue items
            confirm = input("\n⚠️  Delete ALL web search queue items? [y/N]: ").strip().upper()
            if confirm == 'Y':
                for qf, _ in web_search_items:
                    qf.unlink()
                print(f"\n✓ Deleted {len(web_search_items)} queue item(s).")
                # Clear notifications
                notif_file = PROFILE_CONFIG_DIR / 'pending_reviews.jsonl'
                if notif_file.exists():
                    notif_file.unlink()
            input("\nPress ENTER to continue...")
            break
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(web_search_items):
                qf, entry = web_search_items[idx]
                # Show item details and options
                print("\n" + "="*70)
                print(f"QUEUE ITEM #{choice}")
                print("="*70)
                print(f"Query: {entry.get('query', 'Unknown')}")
                print(f"Agent: {entry.get('agent', 'Unknown')}")
                print(f"Source: {entry.get('source', 'Unknown')}")
                print(f"Created: {entry.get('created_at', 'Unknown')[:19]}")
                print("\n[P] Process This | [D] Delete This | [B] Back")

                action = input("\nChoice: ").strip().upper()

                if action == 'P':
                    # Process just this item directly
                    print("\n🔄 Processing this item...")
                    try:
                        # Load settings and run the search
                        settings = load_settings()
                        query = entry.get('query')
                        agent = entry.get('agent', settings.get('default_agent', 'duckduckgo'))
                        headless = entry.get('headless', settings.get('default_headless', True))

                        # Acquire lock before processing
                        if not acquire_lock():
                            print("\n⚠️  Profile is busy. Cannot process now.")
                            input("\nPress ENTER to continue...")
                            continue

                        try:
                            # Run the search
                            asyncio.run(run_search(query, agent, headless, settings))

                            # Move to processed folder
                            processed_dir = qf.parent / 'processed'
                            processed_dir.mkdir(exist_ok=True)
                            qf.rename(processed_dir / qf.name)

                            print("\n✓ Item processed successfully.")
                            web_search_items.pop(idx)
                        except KeyboardInterrupt:
                            print("\n\n⚠️  Interrupted by user")
                        finally:
                            release_lock()
                    except Exception as e:
                        print(f"\n✗ Error: {e}")
                    input("\nPress ENTER to continue...")
                elif action == 'D':
                    # Delete this item
                    qf.unlink()
                    print(f"\n✓ Deleted queue item.")
                    web_search_items.pop(idx)
                    input("\nPress ENTER to continue...")
            else:
                print(f"\n✗ Invalid selection. Enter 1-{len(web_search_items)}")
                input("\nPress ENTER to continue...")
        else:
            print("\n✗ Invalid choice.")
            input("\nPress ENTER to continue...")

def new_query_interactive():
    """Get query from user interactively"""
    print("\n" + "="*70)
    print("  NEW QUERY")
    print("="*70)
    query = input("\nEnter your research question: ").strip()

    if not query:
        print("No query entered. Returning to menu.")
        return

    settings = load_settings()
    agent = settings.get("default_agent", "duckduckgo")
    headless = settings.get("default_headless", True)
    trust_level = settings.get('trust_level', 'low')

    # High Trust: Silent auto-run
    if trust_level == 'high':
        lock_acquired = acquire_lock()
        if lock_acquired:
            print(f"\n⚡ Running: {query[:50]}...")
            try:
                asyncio.run(run_search(query, agent, headless, settings))
            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted by user")
            finally:
                release_lock()
        else:
            # Busy: Auto-enqueue
            if enqueue_job(query, agent, headless, 'TUI_LOCK_BUSY'):
                print(f"\n🕒 Busy, enqueued: {query[:50]}")
            else:
                print(f"\n✗ Failed to enqueue")
        input("\nPress ENTER to return to menu...")
        return

    # Medium Trust: Show review with status, auto-process
    elif trust_level == 'medium':
        lock_acquired = acquire_lock()
        if lock_acquired:
            # Show review in "ready" mode
            decision = get_user_confirmation(query, agent)
            if decision == 'CONFIRM':
                try:
                    asyncio.run(run_search(query, agent, headless, settings))
                except KeyboardInterrupt:
                    print("\n\n⚠️  Interrupted by user")
                finally:
                    release_lock()
            elif decision == 'QUEUE':
                release_lock()  # Release before enqueueing
                if enqueue_job(query, agent, headless, 'TUI_CONFIRM'):
                    print("\n✓ Enqueued.")
                else:
                    print("\n✗ Failed to enqueue")
            else:  # CANCEL
                release_lock()
            input("\nPress ENTER to return to menu...")
            return
        else:
            # Busy: Auto-enqueue, no review
            if enqueue_job(query, agent, headless, 'TUI_LOCK_BUSY', notify=True):
                print(f"\n🕒 Busy, enqueued: {query[:50]}")
            else:
                print(f"\n✗ Failed to enqueue")
            input("\nPress ENTER to return to menu...")
            return

    # Low Trust: Always show review, lock check after Confirm
    else:
        decision = get_user_confirmation(query, agent)
        if decision == 'QUEUE':
            if enqueue_job(query, agent, headless, 'TUI_CONFIRM'):
                print("\n✓ Enqueued.")
            else:
                print("\n✗ Failed to enqueue")
            input("\nPress ENTER to return to menu...")
            return
        if decision == 'CONFIRM':
            # Try to acquire lock now
            lock_acquired = acquire_lock()
            if not lock_acquired:
                # Busy: Auto-enqueue with message
                if settings.get('queue_on_lock', True):
                    if enqueue_job(query, agent, headless, 'TUI_LOCK_BUSY', notify=True):
                        print("\n🕒 Profile busy. Enqueued instead.")
                    else:
                        print("\n✗ Failed to enqueue")
                else:
                    print("\nProfile busy. Try again later.")
                input("\nPress ENTER to return to menu...")
                return
            try:
                asyncio.run(run_search(query, agent, headless, settings))
            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted by user")
            finally:
                release_lock()
        input("\nPress ENTER to return to menu...")

def main_menu():
    """Display main menu and handle user selection"""
    # Mark TUI session active and ensure cleanup on exit
    try:
        import atexit, signal
        mark_tui_active()
        atexit.register(clear_tui_active)
        signal.signal(signal.SIGTERM, lambda s, f: (clear_tui_active(), sys.exit(0)))
        signal.signal(signal.SIGINT, lambda s, f: (clear_tui_active(), sys.exit(0)))
    except Exception:
        pass
    while True:
        print("\n" + "="*70)
        print("  AI RESEARCH TOOL - MAIN MENU")
        print("="*70)
        busy = is_profile_busy()
        if busy:
            print("[BUSY] Profile is currently in use. New runs will be queued unless you wait.")

        # Check for pending reviews
        pending_count = get_pending_review_count()
        if pending_count > 0:
            print(f"⚠️  {pending_count} pending review(s) - queries auto-enqueued while busy")

        print("\n[1] New Query           - Submit question to AI agent")
        print("[2] View Results        - Browse saved research results")
        print("[3] Settings            - Configure agents and preferences")
        print("[4] Agent Status        - View session/profile info")
        print("[5] Chat                - Interactive session (planned)")
        print("[6] Switch Agent        - Choose default agent")
        print("[7] Toggle Headless/GUI - Quick visibility toggle")
        print("[8] Research Queue      - Add/View/Process queued jobs")
        if pending_count > 0:
            print(f"[P] ⚠️  View Pending Reviews ({pending_count})")
        print("[A] Absorb Browser      - Access GameManager absorb pipeline")
        print("[X] Exit\n")

        choice = input("Select option [1-8, A, P, X]: ").strip().upper()

        if choice == '1':
            if is_profile_busy():
                print("\nProfile is busy. Options: [E]nqueue | [W]ait | [B]ack")
                act = input("Select: ").strip().upper()
                if act == 'E':
                    new_query_interactive()  # will offer [Q] in review; or we can fast-enqueue via prompt
                elif act == 'W':
                    print("\nWaiting for profile to be free (Ctrl+C to cancel)…")
                    try:
                        while is_profile_busy():
                            time.sleep(1)
                    except KeyboardInterrupt:
                        continue
                    new_query_interactive()
                else:
                    continue
            else:
                new_query_interactive()
        elif choice == '2':
            view_results()
        elif choice == '3':
            settings_menu()
        elif choice == '4':
            display_agent_status()
        elif choice == '5':
            s = load_settings()
            if is_profile_busy() and s.get('queue_on_lock', True):
                print("\nProfile busy; chat disabled while another task is running.")
                input("Press ENTER to continue...")
                continue
            agent = s.get('default_agent','duckduckgo')
            headless = s.get('default_headless', True)
            # Acquire lock for chat
            if not acquire_lock():
                print("\nCould not acquire profile lock. Try again later.")
                input("Press ENTER to continue...")
                continue
            result = asyncio.run(chat_mode(agent, headless, s))
            release_lock()
            if headless and result.get('captcha'):
                policy = s.get('on_captcha','retry_visible')
                if policy in ('retry_visible','show_gui'):
                    print("\n🔁 Retrying chat in visible mode due to CAPTCHA policy…")
                    asyncio.run(chat_mode(agent, False, s))
        elif choice == '6':
            switch_agent_menu()
        elif choice == '7':
            toggle_headless()
        elif choice == '8':
            # Launch the standalone queue runner (non-intrusive)
            try:
                runner = Path(__file__).parent / 'queue_runner.py'
                if runner.exists():
                    subprocess.run(['python3', str(runner)])
                else:
                    print("\nQueue runner not found. Expected at:")
                    print(f"  {runner}")
                    input("\nPress ENTER to continue...")
            except Exception as e:
                print(f"\nError launching queue runner: {e}")
                input("\nPress ENTER to continue...")
        elif choice == 'P' and pending_count > 0:
            show_pending_reviews()
        elif choice == 'A':
            # Launch GameManager absorb browser
            print("\n🚀 Launching GameManager Absorb Browser...")
            try:
                gm_launcher = "/home/commander/Phoenix_Link/GameManager/Launcher/start.py"
                if not os.path.exists(gm_launcher):
                    print(f"⚠️  GameManager not found at: {gm_launcher}")
                    input("\nPress ENTER to continue...")
                    continue
                # Launch with /absorb tui command
                subprocess.Popen(['xfce4-terminal', '--hold', '-e', f'python3 {gm_launcher}'],
                                 cwd='/home/commander/Phoenix_Link/GameManager')
                print("✓ GameManager launched (use /absorb tui once logged in)")
                input("\nPress ENTER to continue...")
            except Exception as e:
                print(f"⚠️  Failed to launch: {e}")
                input("\nPress ENTER to continue...")
        elif choice == 'X':
            print("\nGoodbye!")
            clear_tui_active()
            break
        else:
            print("Invalid option. Please try again.")

def settings_menu():
    """Basic settings editor for headless/agent."""
    while True:
        s = load_settings()
        print("\n" + "="*70)
        print("  SETTINGS")
        print("="*70)
        print(f"Default Agent    : {s.get('default_agent')}")
        print(f"Default Mode     : {'Headless' if s.get('default_headless', True) else 'Visible'}")
        print(f"On CAPTCHA       : {s.get('on_captcha')}")
        print(f"On Error         : {s.get('on_error')}")
        print(f"Results Directory: {s.get('results_dir')}")
        # Compose indicators
        trust_label = s.get('trust_level','low').title()
        q_tui = s.get('queue_on_tui_active', True)
        q_lock = s.get('queue_on_lock', True)
        trusted = s.get('trusted_cli_user', False)
        default_submit = s.get('default_submit','confirm')
        warn_tui = " <Warn: OFF due to Trust: High>" if (not q_tui and s.get('trust_level')=='high') else ""

        print(f"Queue on TUI Act.: {q_tui}{warn_tui}")
        print(f"Queue on Lock    : {q_lock}")
        print(f"CLI Trust Level  : {trust_label} ({'trusted' if trusted else 'untrusted'})")
        print(f"Default Submit   : {default_submit}")
        print("\n[A] Switch Agent  [M] Toggle Headless/GUI  [Q] Toggle Queue-on-TUI  [L] Toggle Queue-on-Lock  [T] Set Trust Level  [D] Toggle Default Submit  [H] Help  [B] Back")
        ch = input("Select: ").strip().upper()
        if ch == 'A':
            switch_agent_menu()
        elif ch == 'M':
            toggle_headless()
        elif ch == 'Q':
            s['queue_on_tui_active'] = not s.get('queue_on_tui_active', True)
            save_settings(s)
            print(f"\n✓ Queue-on-TUI is now: {s['queue_on_tui_active']}")
            input("Press ENTER to continue...")
        elif ch == 'L':
            s['queue_on_lock'] = not s.get('queue_on_lock', True)
            save_settings(s)
            print(f"\n✓ Queue-on-Lock is now: {s['queue_on_lock']}")
            input("Press ENTER to continue...")
        elif ch == 'T':
            print("\nSet CLI Trust Level:")
            print("[1] Low    - Review everywhere; queue when TUI active; confirm by default")
            print("[2] Medium - Skip CLI confirm; queue when TUI active; TUI New Query enqueues")
            print("[3] High   - Skip CLI confirm; allow direct runs while TUI open; TUI New Query enqueues")
            sel = input("Select [1-3] or [B]ack: ").strip().upper()
            if sel == 'B':
                pass
            else:
                level = {'1':'low','2':'medium','3':'high'}.get(sel)
                if not level:
                    print("Invalid selection")
                else:
                    s = apply_trust_level(s, level)
                    save_settings(s)
                    print(f"\n✓ Trust Level set to: {level.title()}")
                    input("Press ENTER to continue...")
        elif ch == 'D':
            s['default_submit'] = 'queue' if s.get('default_submit','confirm') == 'confirm' else 'confirm'
            save_settings(s)
            print(f"\n✓ Default Submit is now: {s['default_submit']}")
            input("Press ENTER to continue...")
        elif ch == 'H':
            try:
                readme = Path(__file__).parent / 'README_ai_search.md'
                if readme.exists():
                    subprocess.run(['mousepad', str(readme)])
                else:
                    print(f"\nHelp file not found at: {readme}")
            except Exception as e:
                print(f"\nUnable to open help: {e}")
            input("\nPress ENTER to continue...")
        elif ch == 'B':
            return
        else:
            print("Invalid option.")

def switch_agent_menu():
    agents = load_agents()
    names = list(agents.keys())
    print("\nAvailable agents:")
    for i, k in enumerate(names, 1):
        meta = agents[k]
        print(f" {i}. {k} - {meta.get('name','')} ({meta.get('url','')})")
    sel = input("Select agent number or [B]ack: ").strip().upper()
    if sel == 'B':
        return
    try:
        idx = int(sel) - 1
        if 0 <= idx < len(names):
            s = load_settings()
            s['default_agent'] = names[idx]
            save_settings(s)
            print(f"\n✓ Default agent set to: {names[idx]}")
            input("Press ENTER to continue...")
    except ValueError:
        print("Invalid selection")

def toggle_headless():
    s = load_settings()
    s['default_headless'] = not s.get('default_headless', True)
    save_settings(s)
    print(f"\n✓ Mode is now: {'Headless' if s['default_headless'] else 'Visible'}")
    input("Press ENTER to continue...")

def main():
    """Main entry point"""

    # Clear Python cache on launch to ensure latest code is loaded
    try:
        import shutil
        cache_dir = Path(__file__).parent / '__pycache__'
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
    except Exception:
        pass  # Silent fail - cache clearing is optional

    # Clean up any stale locks from crashed/interrupted runs
    cleanup_stale_lock()

    # If running non-interactively (e.g., from another tool), decide: enqueue vs run unattended vs spawn TUI
    if not is_interactive():
        # Parse minimal args to see if a query was provided
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument('--agent')
        parser.add_argument('--headless', action='store_true')
        parser.add_argument('--visible', action='store_true')
        parser.add_argument('query', nargs='*')
        try:
            known, unknown = parser.parse_known_args()
        except SystemExit:
            known = argparse.Namespace(agent=None, headless=False, visible=False, query=sys.argv[1:])

        q_words = known.query or [a for a in unknown if not a.startswith('-')]
        query = " ".join(q_words).strip()

        settings = load_settings()
        agent = known.agent or settings.get('default_agent','duckduckgo')
        headless = settings.get('default_headless', True)
        if known.visible:
            headless = False
        if known.headless:
            headless = True

        # Decide order: 1) Busy → enqueue (if policy), 2) TUI-active → enqueue (if policy), 3) Trusted → run unattended, 4) Spawn TUI
        if query:
            trust_level = settings.get('trust_level', 'low')
            # Determine if notifications should be sent (Medium/Low trust only)
            should_notify = trust_level in ('medium', 'low')

            # 1) Busy check first
            if is_profile_busy():
                if settings.get('queue_on_lock', True):
                    if enqueue_job(query, agent, headless, 'CLI_LOCK_BUSY', notify=should_notify):
                        print("Enqueued (busy).")
                    else:
                        print("Failed to enqueue (queue runner error).")
                    sys.exit(0)
                else:
                    print("Profile busy. Try again later.")
                    sys.exit(1)
            # 2) TUI-active policy
            if is_tui_active() and settings.get('queue_on_tui_active', True):
                if enqueue_job(query, agent, headless, 'CLI_TUI_ACTIVE', notify=should_notify):
                    print("Enqueued (TUI active).")
                else:
                    print("Failed to enqueue (queue runner error).")
                sys.exit(0)
            # 3) Trusted unattended direct run
            if settings.get('trusted_cli_user', False):
                if not acquire_lock():
                    if settings.get('queue_on_lock', True):
                        # High trust: no notification (silent)
                        if enqueue_job(query, agent, headless, 'CLI_TRUSTED_LOCK_BUSY', notify=False):
                            print("Enqueued (trusted, busy).")
                        else:
                            print("Failed to enqueue (queue runner error).")
                        sys.exit(0)
                    else:
                        print("Profile busy. Try again later.")
                        sys.exit(1)
                try:
                    asyncio.run(run_search(query, agent, headless, settings))
                except KeyboardInterrupt:
                    sys.exit(1)
                finally:
                    release_lock()
                sys.exit(0)

        # Otherwise, spawn interactive TUI as before
        print("🔄 Spawning in interactive terminal...")
        spawn_in_terminal()
        sys.exit(0)

    # CLI flags
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--agent', '-a', default=None)
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--visible', action='store_true')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--chat', action='store_true')
    parser.add_argument('--format', choices=['txt', 'md', 'json'])
    parser.add_argument('--session-title')
    parser.add_argument('--help', action='store_true')
    parser.add_argument('--assume-yes', action='store_true')
    parser.add_argument('--no-lock', action='store_true')
    known, unknown = parser.parse_known_args()

    if known.help:
        print("Usage: ai_search.py [--agent duckduckgo] [--headless|--visible] [--debug] [--format txt|md|json] [--chat] [--session-title '...'] [query]")
        sys.exit(0)

    settings = load_settings()

    # CLI Chat mode
    if known.chat:
        agent = known.agent or settings.get("default_agent","duckduckgo")
        headless = settings.get("default_headless", True)
        if known.visible:
            headless = False
        if known.headless:
            headless = True
        result = asyncio.run(chat_mode(agent, headless, settings))
        if headless and result.get('captcha'):
            policy = settings.get('on_captcha','retry_visible')
            if policy in ('retry_visible','show_gui'):
                print("\n🔁 Retrying chat in visible mode due to CAPTCHA policy…")
                asyncio.run(chat_mode(agent, False, settings))
        sys.exit(0)

    if len(sys.argv) < 2:
        # No arguments = launch menu
        main_menu()
    else:
        # Arguments provided = direct query mode (current behavior)
        positional = [a for a in unknown if not a.startswith('-')]
        query = " ".join(positional) if positional else " ".join(sys.argv[1:])
        agent = known.agent or settings.get("default_agent", "duckduckgo")

        # Determine headless/visible
        if known.headless and known.visible:
            print("⚠️  Both --headless and --visible provided. Using --visible.")
            headless = False
        elif known.visible:
            headless = False
        elif known.headless:
            headless = True
        else:
            headless = settings.get("default_headless", True)

        # TUI Confirmation (supports Queue)
        if known.assume_yes or settings.get('trusted_cli_user', False):
            decision = 'CONFIRM'
        else:
            decision = get_user_confirmation(query, agent)
        if decision == 'QUEUE':
            try:
                runner = Path(__file__).parent / 'queue_runner.py'
                cmd = ['python3', str(runner), '--add', query, '--agent', agent]
                cmd.append('--headless' if headless else '--visible')
                cmd.extend(['--source', 'CLI_CONFIRM'])
                subprocess.run(cmd)
                print("\n✓ Enqueued.")
            except Exception as e:
                print(f"\n✗ Failed to enqueue: {e}")
            finally:
                input("\nPress ENTER to return to menu...")
                main_menu()
                return
        if decision != 'CONFIRM':
            sys.exit(0)

        # Run search (with profile lock safety)
        try:
            skip_lock = getattr(known, 'no_lock', False)
            if not skip_lock and not acquire_lock():
                if settings.get('queue_on_lock', True):
                    runner = Path(__file__).parent / 'queue_runner.py'
                    cmd = ['python3', str(runner), '--add', query, '--agent', agent]
                    cmd.append('--headless' if headless else '--visible')
                    cmd.extend(['--source', 'CLI_LOCK_BUSY'])
                    ret = subprocess.run(cmd)
                    if ret.returncode == 0:
                        print("\n🕒 Profile busy. Enqueued instead.")
                    else:
                        print("\n✗ Failed to enqueue (queue runner error).")
                    if known.assume_yes or not is_interactive():
                        return
                    else:
                        input("\nPress ENTER to return to menu...")
                        main_menu()
                        return
                else:
                    print("\nProfile busy. Try again later.")
                    if known.assume_yes or not is_interactive():
                        return
                    else:
                        input("\nPress ENTER to return to menu...")
                        main_menu()
                        return
            result = asyncio.run(run_search(query, agent, headless, settings))
            if headless and result.get("captcha"):
                policy = settings.get("on_captcha", "retry_visible")
                if policy in ("retry_visible", "show_gui"):
                    print("\n🔁 Retrying in visible mode due to CAPTCHA policy…")
                    asyncio.run(run_search(query, agent, False, settings))
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            sys.exit(1)
        finally:
            if not skip_lock:
                release_lock()
            if known.assume_yes or not is_interactive():
                return
            else:
                input("\nPress ENTER to return to menu...")
                main_menu()
                return

if __name__ == "__main__":
    main()
