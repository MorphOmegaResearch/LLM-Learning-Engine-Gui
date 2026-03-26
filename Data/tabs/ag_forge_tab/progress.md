#[PFL:Plan_Ag_Forge_v1]
# Ag Forge v1: Progress Report & Roadmap

**Date:** 2026-01-13
**Status:** Alpha Prototype (Functional, Secure, Portable)

## 1. Milestones Achieved

### 🏗️ Architecture & Core
- **Unified Launcher:** Created `launch_ag_forge.py` (and `.sh`/`.desktop` wrappers). It detects screen geometry and launches the suite in a split-screen dashboard layout.
- **Portability:** Re-engineered the system to be completely self-contained. All data lives in `knowledge_forge_data/` within the project folder. No more polluting `~/home`.
- **Modularization:** Codebase refactored into `modules/` (Meta Learn, AI Orchestrator, Quick Clip) for better organization.

### 🔒 Security & Onboarding
- **First-Run Experience:** Implemented `onboarding.py`. Users must set a Username/Password on first launch.
- **Encryption (Basic):** User config and keys are hashed/salted.
- **Session Management:** A unique `session_token` is generated on login and passed securely to sub-modules.
- **Directory Locking:** The launcher physically locks (read-only) the data directory when the app closes, preventing external tampering.
- **Jail:** The AI Orchestrator is restricted from accessing files outside the project root.

### 🚜 Seasonal Intelligence
- **Logic Module:** `modules/seasonal_logic.py` maps dates to NZ Seasons.
- **Task Registry:** Implemented a database of validated agricultural practices (Spring Calving, Summer Water Checks) sourced from DairyNZ/PrimaryITO.
- **Schedule UI:** Added a "Seasonal Schedule" tab to the main application with clickable validated links.

### 🛠️ Production-Grade Debugging
- **Diagnostics:** Launcher runs environment checks (DISPLAY, Tkinter) before starting.
- **Crash Reporting:** Launcher captures subprocess crashes and logs stderr to `logs/`.
- **Static Analysis:** Created `tkinter_analyzer.py` tool to scan code for bugs and formatting issues.

---

## 2. Review of Web Dev Scripts (`web_programming/`)

We reviewed the scripts found in your collection (e.g., `crawl_google_results.py`, `open_google_results.py`).

**Findings:**
- **Method:** They rely on HTML scraping using `BeautifulSoup` and `fake-useragent`.
- **Status:** **Fragile & Risky**.
    - Google frequently changes CSS classes (e.g., `.eZt8xd`), breaking these scripts.
    - Automated scraping of Google Search violates their ToS and can result in your IP being CAPTCHA-blocked.
- **Recommendation:** Do **not** integrate these directly into Ag Forge's core loop.
- **Alternative:**
    1.  **Google Custom Search JSON API:** 100 free queries/day. Reliable, legal, structured JSON return.
    2.  **DuckDuckGo (DDG):** Often has more permissive HTML structures for lightweight "quick answers".
    3.  **Direct Site Access:** Use the `ai_orchestrator`'s `tool_fetch_webpage` (which we upgraded to respect `robots.txt`) to read *specific* URLs (like DairyNZ pages) rather than scraping Search Results.

---

## 3. Roadmap & Future Enhancements

### 🛡️ Security
- **Encryption at Rest:** Currently, file permissions stop *other users*, but the files are plain text. Future: Encrypt `entities.json` using the user's password key.
- **Clipboard Sanitization:** "Copy/Paste" bypasses security. We need a "Secure Clipboard" mode in Quick Clip that clears system clipboard after internal paste.

### 🖥️ UI/UX
- **Theme Engine:** Unify the look of Tkinter (Meta Learn) and Quick Clip (Custom Theme).
- **Dashboard Widgets:** Move "Seasonal Tasks" to the main landing page of the application.

### 📅 Tasking & Scheduling
- **TaskWarrior Integration:**
    - Bi-directional sync: Ag Forge "Suggested Tasks" -> TaskWarrior.
    - CLI command: `task add project:AgForge priority:H "Check Water Lines"` directly from the UI.
- **Calendar Visualization:** A proper monthly view grid for tasks.

### 📧 Notifications
- **Email Service:**
    - Simple SMTP client (Gmail/Outlook) to send "Daily Briefing".
    - Trigger: On app launch or via a cron job (using the `session_token` generated via a headless login script).

## 4. Next Immediate Steps
1.  **Refine "Review & Add":** Allow clicking a Seasonal Task to add it to the user's local `tasks.json`.
2.  **Connect Bridges:** Ensure `Quick Clip` can read the `Seasonal Schedule` to help draft plans.
