# UI Refactor Update — 2025-10-15

Scope: Custom Code → Chat, Settings → Tab Manager, Settings → Help & Guide

## Completed

- Quick Actions (⚙) in Chat with compact icon grid (4/row), auto-hide on click-away.
- Indicator strip (⏱ 📂 🔧 🗒 ⚡ 📝 👁 🧠 💾) with debounced updates and hover tooltips.
- One‑shot Think Time dialog; unified System Prompt / Tool Schema manager.
- Chat top-right actions: 📌 Mount, 📍 Dismount, 🆕 New Chat, 🗑 Delete Chat.
- ToDo list under Help & Guide with Tasks/Bugs/Completed and show-on-launch.
- Tab Manager: panel headers in Structure, arrow reordering for tabs and panels, Save Tab Order persists main/panels.
- Conversations sidebar: categorized Treeview (Latest/Week/Month/Year), Quick View popup with model header + <Class>/<Parent>, last 2 pairs, and configuration.
- Show Thoughts: streaming preview in chat while generating.
- RAG controls: Chat per‑chat 🧠 RAG (default OFF) + 💾 Save RAG per session; Projects default RAG ON.
- Create Project (Chat quick action): prompts for name, saves chat to Data/projects/<name>, switches to Projects tab and selects it.
- Projects tab: Projects → conversations tree, Open/Delete Chat, Rename Project; per‑project indicators appended.
- History sub‑tab removed; conversations managed through sidebar and quick view.

## Next

1) Help Menu Audit (Automation vs Manual)
- Create clear sections:
  - Automation Guide: Quick Actions, Indicators, Save Tab Order, Show ToDo on Launch.
  - Manual Guide: Prompt/Schema manager, Think Time semantics, Chat sessions (New/Delete), Projects workflows.
- Remove/mark legacy items superseded by Quick Actions (e.g., top-bar prompt/schema).

2) Blueprint Sync
- Append v1.9f “UI Improvements Summary” with Quick Actions + indicators, ToDo, and Tab Manager notes.
- Capture Chat layout changes (top-right actions; bottom-left QA), Conversations categories, Quick View, Show Thoughts, RAG and Create Project.

3) Keyboard Shortcuts (Planned)
- Settings panel for configurable accelerators.
- Bindings: open Quick Actions, open ToDo, open Think Time, open Mode.

4) QA/Polish
- Indicator hover content length caps + wrapping.
- Optional countdown label for ThinkTime pending.
- Optional badge count for enabled tools in indicator.
- Quick View: make placement configurable (left/right of tree), show more pairs.
