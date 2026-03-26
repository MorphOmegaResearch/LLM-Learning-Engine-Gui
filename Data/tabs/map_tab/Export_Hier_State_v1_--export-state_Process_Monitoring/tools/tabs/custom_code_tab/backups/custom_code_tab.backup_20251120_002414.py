"""
Custom Code Tab - Main tab for OpenCode integration
Provides chat interface and tooling features
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from pathlib import Path
import sys
import json
from datetime import datetime

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tabs.base_tab import BaseTab
from logger_util import get_tab_logger

log_message, log_error, log_exception = get_tab_logger('custom_code')

# Phase 1.5E: Conformer & Trust-Gating System Integration
try:
    from conformer_ui_integration import TrustLevelIndicator
    from conformer_gate import get_conformer_gate
    CONFORMER_AVAILABLE = True
except ImportError as e:
    log_message(f"CUSTOM_CODE_TAB: Conformer UI not available: {e}")
    CONFORMER_AVAILABLE = False

try:
    from config import (
        list_todo_files,
        list_project_todo_files,
        read_todo_file,
        update_todo_file,
        get_project_working_dir,
    )
    TODO_APIS_AVAILABLE = True
except ImportError as exc:
    log_message(f"CUSTOM_CODE_TAB: Todo APIs unavailable: {exc}")
    TODO_APIS_AVAILABLE = False

try:
    from living_projects.living_project_manager import get_manager as get_living_project_manager
    LIVING_PROJECTS_AVAILABLE = True
except ImportError:
    get_living_project_manager = None
    LIVING_PROJECTS_AVAILABLE = False

try:
    # Import from parent Data directory (custom_code_tab is in Data/tabs/custom_code_tab/)
    import sys
    from pathlib import Path
    data_dir = Path(__file__).parent.parent.parent
    if str(data_dir) not in sys.path:
        sys.path.insert(0, str(data_dir))
    from agent_task_queue import AgentTaskQueue
    AGENT_QUEUE_AVAILABLE = True
    log_message(f"CUSTOM_CODE_TAB: AgentTaskQueue imported successfully")
except ImportError as e:
    log_message(f"CUSTOM_CODE_TAB: AgentTaskQueue not available: {e}")
    AGENT_QUEUE_AVAILABLE = False
    AgentTaskQueue = None

# BT-004: Register feature flags with bug tracker for monitoring
try:
    from bug_tracker import get_bug_tracker_instance
    tracker = get_bug_tracker_instance()
    if tracker and hasattr(tracker, 'flag_monitor') and tracker.flag_monitor:
        tracker.flag_monitor.register_flag(
            name='AGENT_QUEUE_AVAILABLE',
            check_func=lambda: AGENT_QUEUE_AVAILABLE,
            impact_description='Queue tab missing from Tasks popup - cannot queue tasks for agents',
            related_feature='Agent Task Queue'
        )
        tracker.flag_monitor.register_flag(
            name='LIVING_PROJECTS_AVAILABLE',
            check_func=lambda: LIVING_PROJECTS_AVAILABLE,
            impact_description='Living Projects features disabled - cannot manage living projects',
            related_feature='Living Projects'
        )
        log_message("CUSTOM_CODE_TAB: Feature flags registered with bug tracker")
except Exception as e:
    # Graceful degradation if bug tracker not available
    pass



# Phase Sub-Zero-A.3: Debug logging integration
try:
    from debug_logger import get_logger, debug_ui_event as _debug_ui_event
    _custom_code_logger = get_logger("CustomCodeTab")
except ImportError:
    _debug_ui_event = None
    _custom_code_logger = None


class CustomCodeTab(BaseTab):
    """Custom Code tab with sub-tabs for chat, tools, and project management"""

    def __init__(self, parent, root, style):
        super().__init__(parent, root, style)
        self.tab_instances = None  # Will be set by main GUI

        # Set up close handler for auto-saving chat history
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Backend settings (shared file with Chat)
        from pathlib import Path
        import json
        self._settings_path = Path(__file__).parent / 'custom_code_settings.json'
        try:
            self._backend_settings = json.loads(self._settings_path.read_text()) if self._settings_path.exists() else {}
        except Exception:
            self._backend_settings = {}
        # Use last saved width, and default to locked on launch
        self._right_panel_width = int(self._backend_settings.get('right_panel_width', 340))
        self._right_panel_locked = True
        self._backend_settings['right_panel_locked'] = True

        # Click handling for single/double-click differentiation
        self._click_timer = None
        self._last_click_data = None

        # Shared data for popup event (workaround for Tkinter event.data limitations)
        self._pending_popup_data = None

        # Feature toggle for model popup preview window (S7)
        # Load from backend settings; default disabled
        # When enabled: single-click shows popup, double-click sets active
        # When disabled: single-click sets active, double-click mounts
        self._popup_feature_enabled = bool(self._backend_settings.get('model_popup_enabled', False))

        # Initialize notification manager (Phase 2B)
        try:
            from ui_components.notifications import get_notification_manager
            self.notification_manager = get_notification_manager(root)
            log_message("CUSTOM_CODE_TAB: Notification manager initialized")
        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Failed to initialize notifications: {e}")
            self.notification_manager = None

        # Register for profile update notifications
        try:
            import config as C
            C.register_profile_update_callback(self._on_profile_updated)
        except Exception:
            pass

    def _on_profile_updated(self, variant_name: str):
        """Callback when a model profile is updated."""
        # Refresh model list panel to show updated stats
        try:
            self.root.after(100, self._refresh_model_list_panel)
        except Exception:
            pass

        # Close Model Preview popup if showing the updated variant (forces fresh data on reopen)
        try:
            if hasattr(self, '_current_model_popup') and self._current_model_popup:
                popup = self._current_model_popup
                if popup.winfo_exists():
                    # Check if popup is showing the variant that was updated
                    popup_variant = getattr(popup, '_variant_id', None)
                    if popup_variant == variant_name:
                        log_message(f"CUSTOM_CODE_TAB: Closing popup for updated variant: {variant_name}")
                        popup.destroy()
                        self._current_model_popup = None
        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error closing popup after profile update: {e}")

    def _refresh_model_list_panel(self):
        """Refresh the model list panel to show updated profile data."""
        try:
            # Refresh the model list panel if it exists
            if hasattr(self, 'model_list_panel') and self.model_list_panel:
                self.model_list_panel.refresh_models_list()
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Agent Tasks Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _normalize_plan_key(value: str | None) -> str:
        if not value:
            return ''
        cleaned = str(value).strip()
        if cleaned.lower().startswith('plan:'):
            cleaned = cleaned.split(':', 1)[1].strip()
        return cleaned

    def _extract_plan_keys_from_todo(self, todo_data: dict | None) -> list[str]:
        if not isinstance(todo_data, dict):
            return []
        plan_keys = []
        linked = todo_data.get('linked_plans') or []
        for entry in linked:
            key = self._normalize_plan_key(entry)
            if key and key not in plan_keys:
                plan_keys.append(key)
        if not plan_keys:
            legacy = self._normalize_plan_key(todo_data.get('linked_plan'))
            if legacy:
                plan_keys.append(legacy)
        return plan_keys

    def _get_current_project_context(self) -> str | None:
        settings_tab = getattr(self.root, 'settings_tab', None)
        return getattr(settings_tab, 'current_project_context', None) if settings_tab else None

    def _get_agent_role_for_name(self, agent_name: str) -> str:
        role = ''
        for entry in self._collect_known_agents():
            if entry.get('name') == agent_name:
                role = entry.get('role')
                break
        if not role:
            role = 'general'
        return role

    @staticmethod
    def _task_matches_agent(record: dict, agent_role: str) -> bool:
        roles = [str(r).strip().lower() for r in record.get('agent_roles') or [] if r]
        if not roles:
            return True
        if not agent_role or agent_role == 'general':
            return True
        return agent_role in roles

    def _get_agent_role_availability(self) -> dict:
        """Return mapping of agent role → availability based on roster."""
        availability: dict[str, bool] = {'general': True}
        for entry in self._collect_known_agents():
            role = entry.get('role')
            if role:
                availability[role] = True
        return availability

    def _collect_known_agents(self) -> list[dict]:
        """Aggregate roster information from active session + saved defaults."""
        agents: list[dict] = []
        seen: set[str] = set()
        agents_tab = getattr(self, 'agents_tab', None)
        source_counts: dict[str, int] = {}

        def _resolve_role(name: str, entry: dict | None) -> str:
            role_value = ''
            if entry:
                role_value = entry.get('assigned_type') or entry.get('agent_type') or entry.get('type') or entry.get('role')
            if not role_value and agents_tab and hasattr(agents_tab, 'get_agent_base_type'):
                role_value = agents_tab.get_agent_base_type(name)
            if not role_value and name:
                lower = name.lower()
                if lower.endswith('_agent'):
                    role_value = lower[:-7]
                elif '_' in lower:
                    role_value = lower.split('_', 1)[0]
            if not role_value and entry:
                variant = (entry.get('variant') or '').lower()
                for candidate in ('coder', 'debugger', 'research', 'planner'):
                    if candidate in variant:
                        role_value = candidate
                        break
            role_value = role_value or 'general'
            return str(role_value).strip().lower()

        def _add_entries(entries, label):
            added = 0
            for entry in entries or []:
                name = entry.get('name')
                if not name:
                    continue
                if name in seen:
                    continue
                seen.add(name)
                agents.append({'name': name, 'role': _resolve_role(name, entry)})
                added += 1
            source_counts[label] = source_counts.get(label, 0) + added

        try:
            if hasattr(self.root, 'get_active_agents') and callable(getattr(self.root, 'get_active_agents')):
                _add_entries(self.root.get_active_agents(), 'active')
        except Exception:
            pass
        if hasattr(self, 'agents_tab') and hasattr(self.agents_tab, '_current_roster'):
            try:
                _add_entries(self.agents_tab._current_roster(), 'agents_tab')
            except Exception:
                pass
        # Runtime snapshot
        try:
            runtime_path = Path('Data')/'user_prefs'/'agents_roster.runtime.json'
            if runtime_path.exists():
                data = json.loads(runtime_path.read_text() or '[]')
                _add_entries(data, 'runtime')
        except Exception:
            pass
        # Project / global defaults
        def _load_defaults(path: Path, label: str):
            try:
                if path.exists():
                    data = json.loads(path.read_text() or '[]')
                    _add_entries(data, label)
            except Exception:
                pass
        project_name = None
        try:
            if hasattr(self.root, 'settings_tab'):
                project_name = getattr(self.root.settings_tab, 'current_project_context', None)
        except Exception:
            project_name = None
        if project_name:
            _load_defaults(Path('Data')/'projects'/project_name/'agents_default.json', 'project_defaults')
        _load_defaults(Path('Data')/'user_prefs'/'agents_default.json', 'global_defaults')
        try:
            log_message(f"ROSTER_DEBUG: collected_agents={len(agents)} sources={source_counts}")
        except Exception:
            pass
        return agents

    def _resolve_living_project_id(self, identifier: str | None) -> str | None:
        """Resolve a Living Project ID from id/name."""
        if not identifier or not LIVING_PROJECTS_AVAILABLE or not get_living_project_manager:
            return None
        try:
            manager = get_living_project_manager()
            if not manager:
                return None
            project = manager.load_project(identifier)
            if project:
                return getattr(project, 'id', identifier)
            for entry in manager.list_all_projects():
                if identifier in (entry.get('id'), entry.get('name')):
                    return entry.get('id')
        except Exception as exc:
            log_message(f"CUSTOM_CODE_TAB: Unable to resolve Living Project '{identifier}': {exc}")
        return None

    @staticmethod
    def _task_requires_explicit_directory(record: dict) -> bool:
        roles = [str(r).strip().lower() for r in record.get('agent_roles') or [] if r]
        return any(role in ('coder', 'debugger') for role in roles)

    def _get_default_working_directory(self) -> str:
        """Best-effort lookup of the current session working directory."""
        try:
            chat = getattr(self, 'chat_interface', None)
            tool_executor = getattr(chat, 'tool_executor', None) if chat else None
            if tool_executor and hasattr(tool_executor, 'get_working_directory'):
                current_dir = tool_executor.get_working_directory()
                if current_dir:
                    return str(current_dir)
        except Exception as exc:
            log_message(f"CUSTOM_CODE_TAB: Failed to read current working dir: {exc}")
        try:
            return str(Path.cwd())
        except Exception:
            return '.'

    def _guess_task_working_directory(self, record: dict) -> tuple[str, str]:
        """Return (path, reason) best suited for the given task."""
        project_label = record.get('project_label')
        living_project = record.get('living_project_name')
        filepath = record.get('filepath')
        if project_label and str(project_label).lower() != 'system':
            try:
                directory = str(get_project_working_dir(str(project_label)))
                return directory, f"Project '{project_label}' working directory"
            except Exception as exc:
                log_message(f"CUSTOM_CODE_TAB: Unable to resolve working dir for {project_label}: {exc}")
        hinted_dir = (record.get('working_dir_hint') or '').strip()
        if hinted_dir:
            return hinted_dir, "Todo working_dir_hint"
        if living_project and str(living_project).lower() != 'system':
            try:
                directory = str(get_project_working_dir(str(living_project)))
                return directory, f"Living Project '{living_project}' working directory"
            except Exception as exc:
                log_message(f"CUSTOM_CODE_TAB: Unable to resolve living project dir {living_project}: {exc}")
        if filepath:
            try:
                return str(Path(filepath).parent), "Todo file directory"
            except Exception:
                pass
        return self._get_default_working_directory(), "Current session working directory"

    def _prompt_for_working_directory_choice(
        self,
        record: dict,
        suggested_dir: str,
        reason: str,
        *,
        force_prompt: bool
    ) -> str | None:
        """Confirm or override the working directory for a dispatch."""
        directory = suggested_dir or self._get_default_working_directory()
        reason_text = reason or "Current session working directory"
        if not force_prompt:
            return directory

        message = (
            f"Task: {record.get('title', 'Untitled')}\n\n"
            f"Recommended working directory ({reason_text}):\n{directory}\n\n"
            "Use this directory for the assigned agent?"
        )
        use_recommended = messagebox.askyesno(
            "Confirm Working Directory",
            message,
            parent=self.root
        )
        if use_recommended:
            return directory
        new_dir = filedialog.askdirectory(
            parent=self.root,
            title="Select Working Directory for Task"
        )
        if not new_dir:
            return None
        return new_dir

    def _require_conformer_for_task_assignment(self, agent_name: str, record: dict, working_dir: str) -> bool:
        """Gate task assignments through the conformer queue when available."""
        if not CONFORMER_AVAILABLE:
            return True
        try:
            from conformer_ui_integration import check_operation_with_ui
        except ImportError:
            return True
        operation_details = {
            'agent_name': agent_name,
            'agent_role': self._get_agent_role_for_name(agent_name),
            'required_roles': record.get('agent_roles') or ['general'],
            'task_title': record.get('title'),
            'category': record.get('category'),
            'priority': record.get('priority'),
            'project': record.get('project_label'),
            'plans': record.get('plan_keys'),
            'working_directory': working_dir,
            'filepath': record.get('filepath'),
            'living_project': record.get('living_project_name'),
            'missing_roles': record.get('missing_roles'),
        }
        try:
            allowed = check_operation_with_ui(
                parent_window=self.root,
                variant_id=f"agent::{agent_name}",
                operation_type="assign_agent_task",
                operation_details=operation_details,
                model_class="Skilled",
                on_approved=None
            )
            return bool(allowed)
        except Exception as exc:
            log_message(f"CUSTOM_CODE_TAB: Conformer approval failed for task assignment: {exc}")
            messagebox.showerror(
                "Conformer Error",
                "Unable to dispatch the task because conformer approval failed. Please review the conformer queue.",
                parent=self.root
            )
            return False

    def _log_assignment_to_living_project(
        self,
        record: dict,
        agent_name: str,
        agent_role: str,
        working_dir: str
    ):
        """Record task assignment in the linked Living Project (if any)."""
        if not LIVING_PROJECTS_AVAILABLE or not get_living_project_manager:
            return
        project_identifier = (
            record.get('living_project_id')
            or record.get('living_project_name')
            or record.get('project_label')
        )
        if not project_identifier or str(project_identifier).lower() in ('system', 'none'):
            return
        try:
            manager = get_living_project_manager()
            if not manager:
                return
            project_id = self._resolve_living_project_id(str(project_identifier))
            if not project_id:
                return
            project = manager.load_project(project_id)
            if not project:
                return
            description = (
                f"Assigned todo '{record.get('title')}' "
                f"(Plans: {', '.join(record.get('plan_keys') or ['None'])}) "
                f"to agent {agent_name} (role: {agent_role or 'general'}). "
                f"Working dir: {working_dir}"
            )
            role_label = agent_role or (record.get('agent_roles') or ['general'])[0]
            project.start_agent_activity(role_label or 'general', description, agent_id=agent_name)
            manager.save_project(project)
        except Exception as exc:
            log_message(f"CUSTOM_CODE_TAB: Failed to log assignment to Living Project: {exc}")

    def _collect_agent_tasks(
        self,
        project_name: str | None,
        role_availability: dict | None = None
    ) -> tuple[dict[str, list[dict]], str]:
        scope_label = f"Project: {project_name}" if project_name else "System Todos"
        results: dict[str, list[dict]] = {'build': [], 'bugs': []}
        if not TODO_APIS_AVAILABLE:
            return results, "Unavailable"
        category_map = (
            ('tasks', 'build'),
            ('work_orders', 'build'),
            ('notes', 'build'),
            ('tests', 'build'),
            ('bugs', 'bugs'),
        )
        priority_order = {'high': 0, 'medium': 1, 'low': 2}

        for category, bucket in category_map:
            try:
                if project_name:
                    files = list_project_todo_files(project_name, category)
                else:
                    files = list_todo_files(category)
            except Exception as exc:
                log_message(f"CUSTOM_CODE_TAB: Unable to list {category} todos: {exc}")
                continue
            for path in files:
                try:
                    data = read_todo_file(path)
                except Exception as exc:
                    log_message(f"CUSTOM_CODE_TAB: Failed to read todo {path}: {exc}")
                    continue
                if data.get('completed'):
                    continue
                roles = [str(r).strip().lower() for r in (data.get('agent_roles') or []) if str(r).strip()]
                assigned_agent = str(data.get('assigned_agent') or '').strip()
                assigned_role = str(data.get('assigned_agent_role') or '').strip().lower()
                record = {
                    'title': data.get('title', path.stem),
                    'priority': (data.get('priority') or 'low').lower(),
                    'category': category,
                    'details': data.get('details', ''),
                    'plan_keys': self._extract_plan_keys_from_todo(data),
                    'filepath': data.get('filepath', str(path)),
                    'project_label': project_name or 'System',
                    'project_name': project_name,
                    'linked_plan': data.get('linked_plan'),
                    'agent_roles': roles,
                    'living_project_name': data.get('living_project_name') or data.get('project'),
                    'living_project_id': data.get('living_project_id'),
                    'working_dir_hint': data.get('working_dir_hint'),
                    'assigned_agent': assigned_agent or None,
                    'assigned_agent_role': assigned_role or None,
                    'assigned_at': data.get('assigned_at'),
                }
                if role_availability and roles:
                    missing_roles = [r for r in roles if not role_availability.get(r, False)]
                else:
                    missing_roles = []
                record['missing_roles'] = missing_roles
                record['sort_key'] = (
                    priority_order.get(record['priority'], 3),
                    record['title'].lower(),
                )
                results[bucket].append(record)

        for bucket in results:
            results[bucket].sort(key=lambda rec: rec['sort_key'])
        return results, scope_label

    def _assign_task_to_agent(self, agent_name: str, record: dict, role_availability: dict | None = None, queue_mode: str | None = None) -> bool:
        if not record:
            return False
        agent_role = self._get_agent_role_for_name(agent_name)
        normalized_role = (agent_role or 'general').strip().lower() or 'general'

        required_roles = record.get('agent_roles') or []
        if not self._task_matches_agent(record, agent_role) and required_roles:
            required = ', '.join(r.title() for r in required_roles)
            if not messagebox.askyesno(
                "Role Mismatch",
                f"This task is marked for: {required}.\n"
                f"{agent_name} is configured as '{agent_role or 'general'}'.\n"
                "Assign anyway?",
                parent=self.root
            ):
                return False

        if required_roles and agent_role == 'general':
            required = ', '.join(r.title() for r in required_roles)
            if not messagebox.askyesno(
                "Agent Type Recommended",
                f"This task is tagged for: {required}.\n"
                "No matching agent type is configured for this agent.\n"
                "Proceed with a general agent?",
                parent=self.root
            ):
                return False

        missing_roles = record.get('missing_roles') or []
        if not missing_roles and role_availability and required_roles:
            missing_roles = [r for r in required_roles if not role_availability.get(r, False)]
        if missing_roles:
            missing_label = ', '.join(r.title() for r in missing_roles)
            warn_text = (
                f"No agents are currently configured for: {missing_label}.\n"
                "Tasks remain queued until a matching agent type is set in the Agents tab.\n\n"
                "Assign this task anyway?"
            )
            if not messagebox.askyesno("Missing Agent Type", warn_text, parent=self.root):
                return False

        filepath_value = record.get('filepath')
        todo_path = Path(filepath_value) if filepath_value else None
        if not todo_path or not todo_path.exists():
            messagebox.showerror(
                "Missing Todo File",
                "Unable to locate the todo file for this task. Please refresh the Tasks panel.",
                parent=self.root
            )
            return False

        suggested_dir, reason = self._guess_task_working_directory(record)
        require_prompt = self._task_requires_explicit_directory(record)
        chosen_dir = self._prompt_for_working_directory_choice(
            record,
            suggested_dir,
            reason,
            force_prompt=require_prompt
        )
        if not chosen_dir:
            messagebox.showinfo("Assignment Cancelled", "Task was not assigned.", parent=self.root)
            return False

        if not self._require_conformer_for_task_assignment(agent_name, record, chosen_dir):
            return False

        # Handle queue_mode: if 'queued', add to agent's queue instead of immediate assignment
        if queue_mode == 'queued':
            if AGENT_QUEUE_AVAILABLE:
                try:
                    # Create queue for agent
                    from agent_task_queue import AgentTaskQueue
                    queue = AgentTaskQueue(agent_name)
                    # Prepare task data including working directory context
                    queued_record = record.copy()
                    queued_record['working_dir_hint'] = chosen_dir
                    success = queue.add_task(queued_record)
                    if success:
                        messagebox.showinfo("Task Queued", f"The task has been added to {agent_name}'s queue.", parent=self.root)
                        return True
                    else:
                        messagebox.showerror("Queue Failed", "Failed to add task to queue.", parent=self.root)
                        return False
                except Exception as exc:
                    log_message(f"CUSTOM_CODE_TAB: Failed to queue task: {exc}")
                    messagebox.showerror("Queue Error", f"Failed to queue task: {exc}", parent=self.root)
                    return False
            else:
                # Fallback to immediate assignment if queue not available
                log_message(f"CUSTOM_CODE_TAB: Queue mode requested but AgentTaskQueue not available, falling back to immediate assignment")
                queue_mode = 'immediate'  # Reset to fallback mode

        try:
            existing_roles = record.get('agent_roles') or []
            if normalized_role != 'general' or not existing_roles:
                new_roles = [normalized_role]
            else:
                new_roles = existing_roles or ['general']
            assigned_timestamp = datetime.now().isoformat()
            updated_path = update_todo_file(
                todo_path,
                agent_roles=new_roles,
                assigned_agent=agent_name,
                assigned_agent_role=normalized_role,
                assigned_at=assigned_timestamp,
            )
            record['agent_roles'] = new_roles
            record['missing_roles'] = []
            record['filepath'] = str(updated_path)
            record['assigned_agent'] = agent_name
            record['assigned_agent_role'] = normalized_role
            record['assigned_at'] = assigned_timestamp
        except Exception as exc:
            log_message(f"CUSTOM_CODE_TAB: Failed to update todo assignment for {agent_name}: {exc}")
            messagebox.showerror(
                "Assignment Failed",
                "Unable to update the todo file with the new assignment. Please check logs and try again.",
                parent=self.root
            )
            return False

        self._log_assignment_to_living_project(record, agent_name, agent_role or 'general', chosen_dir)

        summary = (
            f"[Task Assignment]\n"
            f"Title: {record.get('title')}\n"
            f"Category: {record.get('category').title()}  Priority: {record.get('priority').title()}\n"
            f"Project: {record.get('project_label')}\n"
            f"Plans: {', '.join(record.get('plan_keys') or ['None'])}\n"
            f"Agent Type: {', '.join(r.title() for r in (record.get('agent_roles') or ['General']))}\n"
            f"Working Dir: {chosen_dir}\n\n"
            f"{record.get('details')}"
        )
        delivered = False
        try:
            if hasattr(self, 'chat_interface') and hasattr(self.chat_interface, 'send_agent_message'):
                self.chat_interface.send_agent_message(agent_name, summary)
                delivered = True
        except Exception as exc:
            log_message(f"CUSTOM_CODE_TAB: Failed to send task assignment to {agent_name}: {exc}")
        if delivered:
            messagebox.showinfo("Task Assigned", f"The task has been sent to {agent_name}.", parent=self.root)
        else:
            messagebox.showinfo("Task Assignment", summary, parent=self.root)
        return True

    def _open_agent_tasks_popup(self, agent_name: str):
        project_name = self._get_current_project_context()
        role_availability = self._get_agent_role_availability()
        records_map, scope_label = self._collect_agent_tasks(project_name, role_availability)
        if scope_label == "Unavailable":
            messagebox.showwarning("Unavailable", "Todo APIs are not available in this environment.", parent=self.root)
            return
        agent_role = self._get_agent_role_for_name(agent_name)

        popup = tk.Toplevel(self.root)
        popup.title(f"{agent_name} – Tasks")
        popup.geometry("760x560")
        popup.transient(self.root)
        popup.grab_set()

        scope_var = tk.StringVar(value=f"Scope: {scope_label}")
        ttk.Label(popup, textvariable=scope_var, style='CategoryPanel.TLabel').pack(anchor=tk.W, padx=8, pady=(8,4))
        role_label_text = f"Agent Role: {agent_role.title() if agent_role and agent_role != 'general' else 'General / Unspecified'}"
        ttk.Label(popup, text=role_label_text, style='CategoryPanel.TLabel').pack(anchor=tk.W, padx=8, pady=(0,4))
        if agent_role == 'general':
            ttk.Label(
                popup,
                text="Tip: Assign a type in the Agents tab to prioritize relevant tasks automatically.",
                foreground="#ffcc66"
            ).pack(anchor=tk.W, padx=8, pady=(0,6))

        records_state = {'map': records_map}
        columns = ('title', 'role', 'assignee', 'priority', 'project', 'plans')
        column_headings = {
            'title': 'Title',
            'role': 'Role',
            'assignee': 'Assigned To',
            'priority': 'Priority',
            'project': 'Project',
            'plans': 'Plans',
        }

        missing_role_var = tk.StringVar(value='')
        missing_role_label = ttk.Label(
            popup,
            textvariable=missing_role_var,
            foreground="#ff6666",
            style='CategoryPanel.TLabel',
            wraplength=600,
            justify=tk.LEFT,
        )
        missing_role_label._is_packed = False

        notebook = ttk.Notebook(popup)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0,8))

        tree_refs: dict[str, ttk.Treeview] = {}
        tree_records: dict[str, dict[str, dict]] = {}
        section_tabs: dict[str, ttk.Frame] = {}
        selected_record = {'value': None}
        last_selected_path = {'value': None}

        def _format_role_display(record: dict) -> str:
            roles = [str(r).strip() for r in record.get('agent_roles') or [] if r]
            return ', '.join(r.title() for r in roles) if roles else 'General'

        def _format_assignee_display(record: dict) -> str:
            agent = (record.get('assigned_agent') or '').strip()
            if not agent:
                return '—'
            role_value = (record.get('assigned_agent_role') or '').strip()
            return f"{agent} ({role_value.title()})" if role_value else agent

        def _format_assignment_detail(record: dict) -> str:
            agent = (record.get('assigned_agent') or '').strip()
            if not agent:
                return "Assigned to: —"
            role_value = (record.get('assigned_agent_role') or '').strip()
            assigned_at = record.get('assigned_at')
            detail = f"Assigned to: {agent}"
            if role_value:
                detail += f" ({role_value.title()})"
            if assigned_at:
                detail += f" at {assigned_at}"
            return detail

        details_frame = ttk.LabelFrame(popup, text="Details", padding=6)
        details_frame.pack(fill=tk.BOTH, expand=False, padx=8, pady=(0,8))
        details_text = tk.Text(details_frame, height=6, wrap=tk.WORD, bg='#1e1e1e', fg='#dcdcdc')
        details_text.pack(fill=tk.BOTH, expand=True)

        def _update_details_text(record: dict | None):
            details_text.configure(state=tk.NORMAL)
            details_text.delete('1.0', tk.END)
            if record:
                summary_lines = [_format_assignment_detail(record)]
                working_dir = record.get('working_dir_hint')
                if working_dir:
                    summary_lines.append(f"Working Dir Hint: {working_dir}")
                details_text.insert(tk.END, '\n'.join(summary_lines) + '\n\n')
                details_text.insert(tk.END, record.get('details') or '(No details)')
            else:
                details_text.insert(tk.END, 'Select a task to view details.')
            details_text.configure(state=tk.DISABLED)

        def _sort_key(record: dict):
            assigned_agent = (record.get('assigned_agent') or '').strip().lower()
            my_name = (agent_name or '').strip().lower()
            if assigned_agent and assigned_agent == my_name:
                bucket_rank = 0
            elif self._task_matches_agent(record, agent_role):
                bucket_rank = 1
            else:
                bucket_rank = 2
            return (bucket_rank, record['sort_key'])

        def _update_missing_role_warning():
            missing_roles = set()
            for bucket_records in records_state['map'].values():
                for rec in bucket_records:
                    for role in rec.get('missing_roles') or []:
                        if role:
                            missing_roles.add(role)
            if missing_roles:
                missing_text = ', '.join(sorted(r.title() for r in missing_roles))
                missing_role_var.set(f"⚠ No agents configured for: {missing_text}. Tasks stay queued until configured.")
                if not missing_role_label._is_packed:
                    missing_role_label.pack(anchor=tk.W, padx=8, pady=(0,6))
                    missing_role_label._is_packed = True
            else:
                missing_role_var.set('')
                if missing_role_label._is_packed:
                    missing_role_label.pack_forget()
                    missing_role_label._is_packed = False

        def _clear_selection():
            selected_record['value'] = None
            last_selected_path['value'] = None
            _update_details_text(None)

        def _restore_selection() -> bool:
            target = (last_selected_path['value'] or '').strip()
            if not target:
                return False
            for bucket, tree in tree_refs.items():
                for iid, record in tree_records[bucket].items():
                    if record.get('filepath') == target:
                        notebook.select(section_tabs[bucket])
                        tree.selection_set(iid)
                        tree.focus(iid)
                        tree.see(iid)
                        return True
            return False

        def _populate_bucket(bucket: str):
            tree = tree_refs[bucket]
            tree_records[bucket].clear()
            for child in tree.get_children():
                tree.delete(child)
            records = records_state['map'].get(bucket, [])
            if not records:
                tree.configure(selectmode='none')
                tree.insert('', 'end', values=('No tasks available', '', '', '', '', ''))
                return
            tree.configure(selectmode='browse')
            sorted_records = sorted(records, key=_sort_key)
            for record in sorted_records:
                role_display = _format_role_display(record)
                values = (
                    record.get('title'),
                    role_display,
                    _format_assignee_display(record),
                    record.get('priority', '').title(),
                    record.get('project_label'),
                    ', '.join(record.get('plan_keys') or ['None'])
                )
                tags = []
                if not self._task_matches_agent(record, agent_role):
                    tags.append('mismatch')
                assigned_agent = (record.get('assigned_agent') or '').strip().lower()
                if assigned_agent:
                    if assigned_agent == (agent_name or '').strip().lower():
                        tags.append('assigned_me')
                    else:
                        tags.append('assigned_other')
                elif record.get('missing_roles'):
                    tags.append('unassigned')
                iid = tree.insert('', 'end', values=values, tags=tuple(tags) if tags else ())
                tree_records[bucket][iid] = record

        def _refresh_records_from_disk(preserve_selection: bool = True):
            new_map, new_scope = self._collect_agent_tasks(project_name, role_availability)
            records_state['map'] = new_map
            scope_var.set(f"Scope: {new_scope}")
            for bucket in tree_refs:
                _populate_bucket(bucket)
            _update_missing_role_warning()
            if preserve_selection and _restore_selection():
                return
            _clear_selection()

        # Button row - define buttons first so _on_select can reference them
        btn_row = ttk.Frame(popup)
        btn_row.pack(fill=tk.X, padx=8, pady=(0,10))
        # Configure columns: action buttons left-aligned, close button right-aligned
        if AGENT_QUEUE_AVAILABLE:
            btn_row.columnconfigure(3, weight=1)  # Column 3 (close) expands to push right
        else:
            btn_row.columnconfigure(2, weight=1)  # Column 2 (close) expands to push right

        def _assign_current(queue_mode=None):
            if not selected_record['value']:
                return
            last_selected_path['value'] = selected_record['value'].get('filepath')
            success = self._assign_task_to_agent(agent_name, selected_record['value'], role_availability, queue_mode=queue_mode)
            if success:
                _refresh_records_from_disk(preserve_selection=True)

        def _send_to_agent():
            if not selected_record['value']:
                return
            record = selected_record['value']

            # Check if agent is mounted in the agent dock
            is_mounted = False
            try:
                if hasattr(self, 'chat_interface') and hasattr(self.chat_interface, '_agents_mounted_set'):
                    mounted_agents = set(self.chat_interface._agents_mounted_set or set())
                    is_mounted = agent_name in mounted_agents
                    log_message(f"CUSTOM_CODE_TAB: Agent mount check - {agent_name} mounted: {is_mounted}, all mounted: {mounted_agents}")
            except Exception as exc:
                log_message(f"CUSTOM_CODE_TAB: Error checking agent mount status: {exc}")

            if not is_mounted:
                messagebox.showerror(
                    "Agent Not Mounted",
                    f"ERROR: Agent Not Mounted\n\n"
                    f"Please mount '{agent_name}' in the agent dock and re-try.\n\n"
                    f"To mount: Click the agent dock card → Click 'Mount' button",
                    parent=popup
                )
                return

            # Prepare task summary for agent
            summary = (
                f"[Task from Plan]\n"
                f"Title: {record.get('title')}\n"
                f"Category: {record.get('category', '').title()}  Priority: {record.get('priority', '').title()}\n"
                f"Project: {record.get('project_label', 'System')}\n"
                f"Linked Plan: {record.get('linked_plan') or 'None'}\n"
                f"Plans: {', '.join(record.get('plan_keys') or ['None'])}\n"
                f"Working Dir: {record.get('working_dir_hint') or 'Not specified'}\n\n"
                f"{record.get('details', '(No details)')}"
            )

            # Send to agent via chat interface
            delivered = False
            try:
                if hasattr(self, 'chat_interface') and hasattr(self.chat_interface, 'send_agent_message'):
                    self.chat_interface.send_agent_message(agent_name, summary)
                    delivered = True
                    log_message(f"CUSTOM_CODE_TAB: Sent task '{record.get('title')}' to agent {agent_name}")
            except Exception as exc:
                log_message(f"CUSTOM_CODE_TAB: Failed to send task to {agent_name}: {exc}")
                messagebox.showerror(
                    "Send Failed",
                    f"Failed to send task to {agent_name}:\n{exc}",
                    parent=popup
                )
                return

            if delivered:
                messagebox.showinfo(
                    "Task Sent",
                    f"Task '{record.get('title')}' has been sent to {agent_name} for inference.",
                    parent=popup
                )
                # Optionally close the popup after sending
                # popup.grab_release()
                # popup.destroy()
            else:
                messagebox.showwarning(
                    "Delivery Issue",
                    "Task summary prepared but could not be delivered to the agent chat.",
                    parent=popup
                )

        assign_btn = ttk.Button(btn_row, text=f"Assign to {agent_name}", style='Action.TButton', command=_assign_current)
        assign_btn.grid(row=0, column=0, sticky=tk.W)
        assign_btn.state(['disabled'])

        # Add "Add to Queue" button - uses same assign logic but with queue_mode='queued'
        if AGENT_QUEUE_AVAILABLE:
            queue_btn = ttk.Button(btn_row, text="➕ Add to Queue", style='Action.TButton', command=lambda: _assign_current(queue_mode='queued'))
            queue_btn.grid(row=0, column=1, sticky=tk.W, padx=(8,0))
            queue_btn.state(['disabled'])
        else:
            queue_btn = None

        send_btn = ttk.Button(btn_row, text=f"📤 Send to Agent", style='Action.TButton', command=_send_to_agent)
        send_btn.grid(row=0, column=2, sticky=tk.W, padx=(8,0) if AGENT_QUEUE_AVAILABLE else (8,0))
        send_btn.state(['disabled'])

        ttk.Button(
            btn_row,
            text="Close",
            style='Select.TButton',
            command=lambda: (popup.grab_release(), popup.destroy())
        ).grid(row=0, column=3 if AGENT_QUEUE_AVAILABLE else 2, sticky=tk.E, padx=(8,0))

        # Now define _on_select after buttons are created
        def _on_select(event, bucket):
            tree = tree_refs[bucket]
            iid = tree.selection()
            if not iid:
                _clear_selection()
                assign_btn.state(['disabled'])
                send_btn.state(['disabled'])
                if queue_btn:
                    queue_btn.state(['disabled'])
                return
            selected_record['value'] = tree_records[bucket].get(iid[0])
            if selected_record['value']:
                last_selected_path['value'] = selected_record['value'].get('filepath')
            has_selection = bool(selected_record['value'])
            assign_btn.state(['!disabled'] if has_selection else ['disabled'])
            send_btn.state(['!disabled'] if has_selection else ['disabled'])
            if queue_btn:
                queue_btn.state(['!disabled'] if has_selection else ['disabled'])
            _update_details_text(selected_record['value'])

        sections = [
            ('build', 'Tasks', "General tasks, work-orders, notes, and tests."),
            ('bugs', 'Bugs', "Open bugs for debugging agents."),
        ]

        for bucket, label, desc in sections:
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=label)
            section_tabs[bucket] = frame
            ttk.Label(frame, text=desc, style='CategoryPanel.TLabel').pack(anchor=tk.W, padx=6, pady=(6,4))
            tree = ttk.Treeview(frame, columns=columns, show='headings', height=10)
            tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0,6))
            tree.tag_configure('mismatch', foreground='#777777')
            tree.tag_configure('unassigned', foreground='#ff6666')
            tree.tag_configure('assigned_me', foreground='#8de0ff')
            tree.tag_configure('assigned_other', foreground='#888888')
            for col in columns:
                tree.heading(col, text=column_headings[col])
                if col == 'title':
                    tree.column(col, width=260, anchor=tk.W)
                elif col == 'plans':
                    tree.column(col, width=150, anchor=tk.W)
                elif col == 'assignee':
                    tree.column(col, width=160, anchor=tk.W)
                elif col == 'role':
                    tree.column(col, width=120, anchor=tk.W)
                else:
                    tree.column(col, width=100, anchor=tk.W)
            tree.bind('<<TreeviewSelect>>', lambda e, b=bucket: _on_select(e, b))
            tree_refs[bucket] = tree
            tree_records[bucket] = {}
            _populate_bucket(bucket)

            if agent_role != 'general' and not any(self._task_matches_agent(rec, agent_role) for rec in records_state['map'].get(bucket, [])):
                ttk.Label(
                    frame,
                    text=f"No tasks currently tagged for {agent_role.title()} agents.",
                    foreground="#ffcc66",
                    style='CategoryPanel.TLabel'
                ).pack(anchor=tk.W, padx=6, pady=(0,4))

        # Add Queue tab if agent task queuing is available
        log_message(f"CUSTOM_CODE_TAB: Checking AGENT_QUEUE_AVAILABLE = {AGENT_QUEUE_AVAILABLE}")
        if AGENT_QUEUE_AVAILABLE:
            log_message(f"CUSTOM_CODE_TAB: Calling _show_queue_tab for agent '{agent_name}'...")
            self._show_queue_tab(agent_name, popup, records_state, notebook, btn_row)
            log_message(f"CUSTOM_CODE_TAB: _show_queue_tab returned successfully")

        _update_missing_role_warning()
        assign_btn.state(['disabled'])
        send_btn.state(['disabled'])
        _update_details_text(None)

    def create_ui(self):
        """Create the custom code tab UI"""
        log_message("CUSTOM_CODE_TAB: Creating UI...")

        # Main layout: Paned window with resizable left (content) and right (models)
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)
        outer_pw = ttk.Panedwindow(self.parent, orient=tk.HORIZONTAL)
        outer_pw.grid(row=0, column=0, sticky=tk.NSEW)
        self._outer_pw = outer_pw

        # Left side pane: main content with sub-tabs
        content_frame = ttk.Frame(outer_pw, style='Category.TFrame')
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(1, weight=1)

        # Header with title and refresh button
        header_frame = ttk.Frame(content_frame, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, pady=5)

        ttk.Label(
            header_frame,
            text="🤖 Custom Code",
            font=("Arial", 14, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            header_frame,
            text="🔄 Refresh",
            command=self.refresh_tab,
            style='Select.TButton'
        ).pack(side=tk.RIGHT, padx=5)

        # Sub-tabs notebook
        self.sub_notebook = ttk.Notebook(content_frame)
        self.sub_notebook.grid(row=1, column=0, sticky=tk.NSEW, padx=5, pady=5)

        # Chat Interface Sub-tab
        self.chat_tab_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(self.chat_tab_frame, text="💬 Chat")
        self.create_chat_tab(self.chat_tab_frame)
        # When user navigates to Chat tab, refresh conversations (bind once)
        try:
            def _on_subtab_changed(event=None):
                try:
                    current = self.sub_notebook.select()
                    if current == str(self.chat_tab_frame) and hasattr(self, 'chat_interface'):
                        if hasattr(self.chat_interface, '_refresh_conversations_list'):
                            self.chat_interface._refresh_conversations_list()
                except Exception:
                    pass
            self.sub_notebook.bind('<<NotebookTabChanged>>', _on_subtab_changed)
        except Exception:
            pass

        # History sub-tab removed (handled via Chat sidebar quick views)

        # Tools Sub-tab
        self.tools_tab_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(self.tools_tab_frame, text="🔧 Tools")
        self.create_tools_tab(self.tools_tab_frame)

        # Projects Sub-tab (project-aware chat interface)
        self.projects_tab_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(self.projects_tab_frame, text="📁 Projects")
        self.create_projects_tab(self.projects_tab_frame)

        # Agents Sub-tab (Phase 1.5F)
        self.agents_tab_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(self.agents_tab_frame, text="🤖 Agents")
        self.create_agents_tab(self.agents_tab_frame)

        # Browser Sub-tab (Phase 1.6E)
        self.browser_tab_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(self.browser_tab_frame, text="🌐 Browser")
        self.create_browser_tab(self.browser_tab_frame)

        # Settings Sub-tab
        self.settings_tab_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(self.settings_tab_frame, text="⚙️ Settings")
        self.create_settings_tab(self.settings_tab_frame)


        # Right side pane: Model selector
        right_pane = ttk.Frame(outer_pw, style='Category.TFrame')
        right_pane.columnconfigure(0, weight=1)
        right_pane.rowconfigure(0, weight=1)
        self.create_right_panel(right_pane)

        outer_pw.add(content_frame, weight=1)
        outer_pw.add(right_pane, weight=0)
        try:
            # Enforce sensible minimum sizes so panes don't disappear
            outer_pw.paneconfigure(content_frame, minsize=500)
            outer_pw.paneconfigure(right_pane, minsize=260)
        except Exception:
            pass

        # Listen for Agents roster changes to refresh indicators/panels live
        try:
            def _on_agents_roster_changed(event=None):
                try:
                    # Refresh right panel (collections + dock)
                    self.refresh_model_list()
                    self._refresh_agent_dock()
                    # Refresh chat quick indicators if available
                    if hasattr(self, 'chat_interface') and hasattr(self.chat_interface, '_update_quick_indicators'):
                        self.chat_interface._update_quick_indicators()
                except Exception:
                    pass
            self.root.bind('<<AgentsRosterChanged>>', _on_agents_roster_changed)
        except Exception:
            pass

        # Set default sash position after layout: leave ~360px for right pane
        try:
            def _set_outer_sash():
                try:
                    self.parent.update_idletasks()
                    pw_w = max(self._outer_pw.winfo_width(), 1000)
                    target_right = int(self._backend_settings.get('right_panel_width', self._right_panel_width or 340))
                    target_right = max(260, target_right)
                    # Compute sash position from desired right width, clamp to min sizes
                    pos = pw_w - target_right
                    pos = max(600, min(pos, pw_w - 260))
                    self._outer_pw.sashpos(0, pos)
                except Exception:
                    pass
            self.parent.after(150, _set_outer_sash)
        except Exception:
            pass

        # Enforce locked width on resize
        def _enforce_right_width(event=None):
            if not getattr(self, '_right_panel_locked', False):
                return
            try:
                pw_w = max(self._outer_pw.winfo_width(), 800)
                width = max(260, int(getattr(self, '_right_panel_width', 340)))
                pos = pw_w - width
                self._outer_pw.sashpos(0, max(500, min(pos, pw_w - 260)))
            except Exception:
                pass
        self._outer_pw.bind('<Configure>', _enforce_right_width)

        # Apply initial lock behavior (disable drag + arrow when locked)
        self._apply_right_lock_state()

        log_message("CUSTOM_CODE_TAB: UI created successfully")

        # Load and apply Agents default roster on launch (project wins over global)
        try:
            import json
            proj = None
            try:
                if hasattr(self.root, 'settings_tab') and getattr(self.root.settings_tab, 'current_project_context', None):
                    proj = self.root.settings_tab.current_project_context
            except Exception:
                proj = None
            path = None
            if proj:
                p = Path('Data')/'projects'/proj/'agents_default.json'
                if p.exists():
                    path = p
            if not path:
                g = Path('Data')/'user_prefs'/'agents_default.json'
                if g.exists():
                    path = g
            if path:
                roster = json.loads(path.read_text()) or []
                if hasattr(self.root, 'set_active_agents'):
                    self.root.set_active_agents(roster)
                    log_message(f"CUSTOM_CODE_TAB: Applied default agents roster from {path}")
                    # Ensure right-side Collections highlights reflect roster
                    try:
                        self.refresh_model_list()
                    except Exception:
                        pass
        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Failed to apply agents default on launch: {e}")

    def select_subtab(self, label: str):
        """Select a subtab in this Custom Code tab by its visible text (best-effort)."""
        try:
            for tid in self.sub_notebook.tabs():
                text = str(self.sub_notebook.tab(tid, 'text'))
                if label.lower() in text.lower():
                    self.sub_notebook.select(tid)
                    return True
        except Exception:
            pass
        return False

    def create_chat_tab(self, parent):
        """Create the chat interface sub-tab"""
        try:
            # Import here to avoid circular dependencies
            from .sub_tabs.chat_interface_tab import ChatInterfaceTab

            self.chat_interface = ChatInterfaceTab(parent, self.root, self.style, self)
            self.chat_interface.safe_create()
            try:
                self._maybe_reconcile_training_state()
            except Exception:
                pass
        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Failed to create chat tab: {e}")
            self._show_tab_error(parent, "Chat Interface", str(e))

    def create_tools_tab(self, parent):
        """Create the tools configuration sub-tab"""
        try:
            from .sub_tabs.tools_tab import ToolsTab

            self.tools_interface = ToolsTab(parent, self.root, self.style, self)
            self.tools_interface.safe_create()
        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Failed to create tools tab: {e}")
            self._show_tab_error(parent, "Tools", str(e))

    def create_settings_tab(self, parent):
        """Create the settings configuration sub-tab"""
        try:
            from .sub_tabs.settings_tab import SettingsTab

            self.settings_interface = SettingsTab(parent, self.root, self.style, self)
            self.settings_interface.safe_create()
            try:
                self._maybe_reconcile_training_state()
            except Exception:
                pass
        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Failed to create settings tab: {e}")
            self._show_tab_error(parent, "Settings", str(e))

    def _maybe_reconcile_training_state(self):
        """Apply backend defaults to chat and sync UI once after both Chat and Settings exist."""
        try:
            if getattr(self, '_reconciled_training_state', False):
                return
            if not (hasattr(self, 'chat_interface') and self.chat_interface and hasattr(self, 'settings_interface') and self.settings_interface):
                return
            # Load defaults from backend settings file
            from pathlib import Path
            import json as _json
            backend_path = Path(__file__).parent / 'custom_code_settings.json'
            tm_default = False; ts_default = False
            if backend_path.exists():
                try:
                    data = _json.loads(backend_path.read_text()) or {}
                    tm_default = bool(data.get('training_mode_enabled', False))
                    ts_default = bool(data.get('training_support_enabled', False))
                except Exception:
                    pass
            # Apply Support first, then Training
            try:
                self.set_training_support(ts_default)
            except Exception:
                pass
            try:
                self.chat_interface.set_training_mode(tm_default)
            except Exception:
                pass
            # Emit events for UI sync
            try:
                payload = _json.dumps({"enabled": bool(tm_default)})
                self.root.event_generate("<<TrainingModeChanged>>", data=payload, when='tail')
            except Exception:
                pass
            try:
                spayload = _json.dumps({"enabled": bool(ts_default)})
                self.root.event_generate("<<TrainingSupportChanged>>", data=spayload, when='tail')
            except Exception:
                pass
            # Refresh Advanced UI
            try:
                if hasattr(self.settings_interface, 'advanced_settings_interface') and self.settings_interface.advanced_settings_interface:
                    self.settings_interface.advanced_settings_interface.refresh()
            except Exception:
                pass
            self._reconciled_training_state = True
        except Exception:
            pass

    def create_projects_tab(self, parent):
        """Create the projects management sub-tab (project-aware chat)."""
        try:
            from .sub_tabs.projects_interface_tab import ProjectsInterfaceTab
            self.projects_interface = ProjectsInterfaceTab(parent, self.root, self.style, self)
            self.projects_interface.safe_create()
        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Failed to create projects tab: {e}")
            self._show_tab_error(parent, "Projects", str(e))

    def create_agents_tab(self, parent):
        """Create the agents configuration sub-tab (Phase 1.5F)."""
        try:
            from .sub_tabs.agents_tab import AgentsTab
            self.agents_tab = AgentsTab(parent, self.root, self.style, parent_tab=self)
            self.agents_tab.pack(fill=tk.BOTH, expand=True)
            log_message("CUSTOM_CODE_TAB: Agents tab created successfully")
        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Failed to create agents tab: {e}")
            self._show_tab_error(parent, "Agents", str(e))

    def create_browser_tab(self, parent):
        """Create the browser automation sub-tab (Phase 1.6E)."""
        try:
            from .sub_tabs.browser_tab import BrowserTab
            self.browser_tab = BrowserTab(parent, self.root, self.style, parent_tab=self)
            self.browser_tab.create_ui()
            log_message("CUSTOM_CODE_TAB: Browser tab created successfully")
        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Failed to create browser tab: {e}")
            self._show_tab_error(parent, "Browser", str(e))

    def _show_tab_error(self, parent, tab_name, error_msg):
        """Display an error message when a sub-tab fails to load"""
        error_frame = ttk.Frame(parent)
        error_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ttk.Label(
            error_frame,
            text=f"❌ Error Loading {tab_name} Tab",
            font=("Arial", 14, "bold"),
            foreground="red"
        ).pack(pady=10)

        ttk.Label(
            error_frame,
            text=error_msg,
            wraplength=400
        ).pack(pady=5)

    def create_history_tab(self, parent):
        """Create the conversation history sub-tab"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Header
        header_frame = ttk.Frame(parent, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)

        ttk.Label(
            header_frame,
            text="📚 Conversation History",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            header_frame,
            text="🔄 Refresh",
            command=self.refresh_history,
            style='Select.TButton'
        ).pack(side=tk.RIGHT)

        # History list frame with scrollbar
        list_container = ttk.Frame(parent, style='Category.TFrame')
        list_container.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=(0, 10))
        list_container.columnconfigure(0, weight=1)
        list_container.rowconfigure(0, weight=1)

        # Canvas for scrolling
        self.history_canvas = tk.Canvas(
            list_container,
            bg='#2b2b2b',
            highlightthickness=0
        )
        self.history_scrollbar = ttk.Scrollbar(
            list_container,
            orient="vertical",
            command=self.history_canvas.yview
        )
        self.history_scroll_frame = ttk.Frame(self.history_canvas, style='Category.TFrame')

        self.history_scroll_frame.bind(
            "<Configure>",
            lambda e: self.history_canvas.configure(scrollregion=self.history_canvas.bbox("all"))
        )

        self.history_canvas_window = self.history_canvas.create_window(
            (0, 0),
            window=self.history_scroll_frame,
            anchor="nw"
        )
        self.history_canvas.configure(yscrollcommand=self.history_scrollbar.set)

        self.history_canvas.bind(
            "<Configure>",
            lambda e: self.history_canvas.itemconfig(self.history_canvas_window, width=e.width)
        )

        self.history_canvas.grid(row=0, column=0, sticky=tk.NSEW)
        self.history_scrollbar.grid(row=0, column=1, sticky=tk.NS)

        # Enable mousewheel scrolling for history list
        self.bind_mousewheel_to_canvas(self.history_canvas)

        # Load history
        self.refresh_history()

    def refresh_history(self):
        """Refresh the conversation history list from persistent storage"""
        log_message("CUSTOM_CODE_TAB: Refreshing history from storage...")

        if not hasattr(self, 'history_scroll_frame'):
            log_message("CUSTOM_CODE_TAB: history_scroll_frame not initialized; deferring refresh")
            return

        # Clear existing
        for widget in self.history_scroll_frame.winfo_children():
            widget.destroy()

        if not hasattr(self, 'chat_interface') or not self.chat_interface or not self.chat_interface.chat_history_manager:
            ttk.Label(
                self.history_scroll_frame,
                text="Chat history manager not initialized.",
                style='Config.TLabel'
            ).pack(pady=20, padx=10)
            return

        # Get conversation histories from ChatHistoryManager
        histories = self.chat_interface.chat_history_manager.list_conversations()

        if not histories:
            ttk.Label(
                self.history_scroll_frame,
                text="No saved conversation history found.",
                style='Config.TLabel'
            ).pack(pady=20, padx=10)
            return

        def show_config(cfg):
            import json
            config_win = tk.Toplevel(self.root)
            config_win.title("Session Configuration")
            config_win.geometry("600x400")
            text = tk.Text(config_win, wrap=tk.WORD, font=("Courier", 10))
            text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            text.insert(tk.END, json.dumps(cfg, indent=2))
            text.config(state=tk.DISABLED)

        # Display each conversation
        for conv_summary in histories:
            session_id = conv_summary.get("session_id")
            model_name = conv_summary.get("model_name")
            msg_count = conv_summary.get("message_count")
            saved_at = conv_summary.get("saved_at")
            preview = conv_summary.get("preview")
            metadata = conv_summary.get("metadata", {})

            # Create frame for this session
            session_frame = ttk.LabelFrame(
                self.history_scroll_frame,
                text=f"📄 {session_id}",
                style='TLabelframe'
            )
            session_frame.pack(fill=tk.X, padx=5, pady=5)

            # Display info
            info_text = f"Model: {model_name} | Messages: {msg_count} | Saved: {saved_at}"
            ttk.Label(
                session_frame,
                text=info_text,
                style='Config.TLabel'
            ).pack(anchor=tk.W, padx=10, pady=(5, 2))

            ttk.Label(
                session_frame,
                text=f"Preview: {preview}",
                style='Config.TLabel'
            ).pack(anchor=tk.W, padx=10, pady=(0, 5))

            # Buttons
            btn_frame = ttk.Frame(session_frame, style='Category.TFrame')
            btn_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

            ttk.Button(
                btn_frame,
                text="Load Conversation",
                command=lambda s=session_id: self.load_conversation(s),
                style='Action.TButton'
            ).pack(side=tk.LEFT, padx=(0, 5))

            ttk.Button(
                btn_frame,
                text="View Config",
                command=lambda m=metadata: show_config(m),
                style='Action.TButton'
            ).pack(side=tk.LEFT, padx=(0, 5))

            ttk.Button(
                btn_frame,
                text="Delete",
                command=lambda s=session_id: self.delete_conversation(s),
                style='Select.TButton'
            ).pack(side=tk.LEFT)

    def load_conversation(self, session_id):
        """Load a conversation from history by session_id"""
        log_message(f"CUSTOM_CODE_TAB: Loading conversation {session_id}")

        if not hasattr(self, 'chat_interface') or not self.chat_interface or not self.chat_interface.chat_history_manager:
            return

        conversation = self.chat_interface.chat_history_manager.load_conversation(session_id)
        if not conversation:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Failed to load conversation: {session_id}")
            return

        # Switch to chat tab
        self.sub_notebook.select(self.chat_tab_frame)

        # Load the conversation into the chat interface
        self.chat_interface.chat_history = conversation.get("chat_history", [])
        self.chat_interface.current_model = conversation.get("model_name")
        self.chat_interface.current_session_id = session_id
        self.chat_interface.model_label.config(text=self.chat_interface.current_model)
        self.chat_interface.redisplay_conversation()
        self.chat_interface.add_message("system", f"✓ Loaded conversation: {session_id}")

    def delete_conversation(self, session_id):
        """Delete a conversation from history by session_id"""
        from tkinter import messagebox

        if not hasattr(self, 'chat_interface') or not self.chat_interface or not self.chat_interface.chat_history_manager:
            return

        if messagebox.askyesno(
            "Delete Conversation",
            f"Are you sure you want to delete this conversation?\n\n{session_id}"
        ):
            if self.chat_interface.chat_history_manager.delete_conversation(session_id):
                messagebox.showinfo("Deleted", "Conversation deleted successfully")
                self.refresh_history()
            else:
                messagebox.showerror("Error", "Failed to delete conversation")

    def create_placeholder_tab(self, parent, title):
        """Create a placeholder tab for future features"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        container = ttk.Frame(parent, style='Category.TFrame')
        container.grid(row=0, column=0, sticky=tk.NSEW, padx=20, pady=20)

        ttk.Label(
            container,
            text=f"🚧 {title}",
            font=("Arial", 16, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(pady=20)

        ttk.Label(
            container,
            text="This feature is planned for future development.",
            font=("Arial", 10),
            style='Config.TLabel'
        ).pack(pady=10)

    def create_right_panel(self, parent):
        """Create right side panel with model selector"""
        right_panel = ttk.Frame(parent, width=360, style='Category.TFrame')
        right_panel.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)
        # Maintain internal width to keep scrollbar visible
        right_panel.grid_propagate(False)
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)
        right_panel.rowconfigure(2, weight=0)
        right_panel.rowconfigure(3, weight=0, minsize=0)
        # Keep a handle for width measurement when locking
        self._right_pane_widget = right_panel

        # Header
        header = ttk.Frame(right_panel, style='Category.TFrame')
        header.grid(row=0, column=0, sticky=tk.EW, pady=(0, 10))

        ttk.Label(
            header,
            text="🤖 Ollama Models",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(side=tk.LEFT)

        ttk.Button(
            header,
            text="🔄",
            command=self.refresh_model_list,
            style='Select.TButton',
            width=3
        ).pack(side=tk.RIGHT)
        # Lock width toggle
        self._right_lock_btn = ttk.Button(
            header,
            text=("🔒" if self._right_panel_locked else "🔓"),
            command=self._toggle_right_panel_lock,
            style='Select.TButton',
            width=3
        )
        self._right_lock_btn.pack(side=tk.RIGHT, padx=(4,0))

        # Model list frame with scrollbar
        list_container = ttk.Frame(right_panel, style='Category.TFrame')
        list_container.grid(row=1, column=0, sticky=tk.NSEW)
        list_container.columnconfigure(0, weight=1)
        list_container.rowconfigure(0, weight=1)

        # Canvas for scrolling
        self.model_canvas = tk.Canvas(
            list_container,
            bg='#2b2b2b',
            highlightthickness=0
        )
        self.model_scrollbar = ttk.Scrollbar(
            list_container,
            orient="vertical",
            command=self.model_canvas.yview
        )
        self.model_scroll_frame = ttk.Frame(self.model_canvas, style='Category.TFrame')

        self.model_scroll_frame.bind(
            "<Configure>",
            lambda e: self.model_canvas.configure(scrollregion=self.model_canvas.bbox("all"))
        )

        self.model_canvas_window = self.model_canvas.create_window(
            (0, 0),
            window=self.model_scroll_frame,
            anchor="nw"
        )
        self.model_canvas.configure(yscrollcommand=self.model_scrollbar.set)

        # Bind resize to adjust canvas window width
        self.model_canvas.bind(
            "<Configure>",
            lambda e: self.model_canvas.itemconfig(self.model_canvas_window, width=e.width)
        )

        self.model_canvas.grid(row=0, column=0, sticky=tk.NSEW)
        self.model_scrollbar.grid(row=0, column=1, sticky=tk.NS)

        # Enable mousewheel scrolling for model list
        self.bind_mousewheel_to_canvas(self.model_canvas)

        # UI state for expand/collapse
        # Default collapsed on launch
        self.cc_collections_expanded = False
        self.cc_unassigned_expanded = False
        self.cc_variant_expanded = {}
        # Variants currently forced-open because they are used by agents
        self.cc_variant_forced = set()
        # Agent Dock (collapsible section below the model list; replaces inline panel)
        try:
            dock_header = ttk.Frame(right_panel, style='Category.TFrame')
            dock_header.grid(row=2, column=0, sticky=tk.EW, pady=(8,0))
            ttk.Label(dock_header, text="Active Agents", style='CategoryPanel.TLabel').pack(side=tk.LEFT)
            # Start collapsed by default to avoid initial flicker/glitch
            self._agent_dock_open = False
            def _dock_toggle():
                # Toggle open state cleanly
                cur = bool(getattr(self, '_agent_dock_open', False))
                self._agent_dock_open = not cur
                _dock_btn.config(text=('▴' if self._agent_dock_open else '▾'))
                self._render_or_hide_agent_dock()
            _dock_btn = ttk.Button(dock_header, text='▾', width=2, style='Select.TButton', command=_dock_toggle)
            _dock_btn.pack(side=tk.RIGHT)
            self._agent_dock_body = ttk.Frame(right_panel, style='Category.TFrame')
            # Dock occupies row 3; remember index for dynamic minsize
            self._dock_row_index = 3
            self._agent_dock_body.grid(row=self._dock_row_index, column=0, sticky=tk.EW)
            # Ensure initial state (collapsed) is applied immediately
            self._render_or_hide_agent_dock()
            # Start periodic conformer flash check
            self._start_conformer_flash_timer()
        except Exception:
            self._agent_dock_body = None

        # Load models
        self.refresh_model_list()

    @_debug_ui_event(_custom_code_logger)
    def _render_or_hide_agent_dock(self):
        try:
            if not hasattr(self, '_agent_dock_body') or not self._agent_dock_body:
                return
            if not bool(getattr(self, '_agent_dock_open', False)):
                # Hide the dock frame entirely
                try:
                    self._agent_dock_body.grid_remove()
                except Exception:
                    pass
                # Reset reserved height
                try:
                    if hasattr(self, '_right_pane_widget'):
                        self._right_pane_widget.rowconfigure(getattr(self, '_dock_row_index', 3), minsize=0)
                except Exception:
                    pass
                # Also clear any lingering children
                for w in self._agent_dock_body.winfo_children():
                    try:
                        w.destroy()
                    except Exception:
                        pass
                return
            # Ensure frame is visible when opening
            try:
                self._agent_dock_body.grid()
            except Exception:
                pass
            # Reserve comfortable vertical space so controls are visible
            try:
                host = self._right_pane_widget
                host.update_idletasks()
                # Stretch higher on first open so output, chatline and buttons are all visible
                desired = max(320, int(host.winfo_height() * 0.50))
                host.rowconfigure(getattr(self, '_dock_row_index', 3), minsize=desired)
            except Exception:
                pass
            # Clear and rebuild content
            for w in self._agent_dock_body.winfo_children():
                try:
                    w.destroy()
                except Exception:
                    pass
            self._render_agent_dock_content()
        except Exception:
            pass

    @_debug_ui_event(_custom_code_logger)
    def _render_agent_dock_content(self):
        try:
            if not hasattr(self, '_agent_dock_body') or not self._agent_dock_body:
                return
            for w in self._agent_dock_body.winfo_children():
                w.destroy()
            # Header row inside overlay with a close arrow
            import tkinter as tk
            from tkinter import ttk
            hdr = ttk.Frame(self._agent_dock_body, style='Category.TFrame')
            hdr.pack(fill=tk.X)

            # Build tabs per active agent
            nb = ttk.Notebook(self._agent_dock_body)
            nb.pack(fill=tk.BOTH, expand=True)
            roster = []
            try:
                if hasattr(self.root, 'get_active_agents') and callable(getattr(self.root, 'get_active_agents')):
                    roster = [r for r in (self.root.get_active_agents() or []) if r.get('active', True)]
            except Exception:
                roster = []
            # Fallback to Agents tab live roster if root has none
            if not roster:
                try:
                    if hasattr(self, 'agents_tab') and hasattr(self.agents_tab, '_current_roster'):
                        roster = [r for r in (self.agents_tab._current_roster() or []) if r.get('active', True)]
                except Exception:
                    pass
            if not roster:
                ttk.Label(self._agent_dock_body, text='No active agents', style='Config.TLabel').pack(fill=tk.X)
                return
            # Pull logs from ChatInterfaceTab
            sessions = {}
            try:
                if hasattr(self, 'chat_interface') and self.chat_interface and hasattr(self.chat_interface, '_agents_sessions'):
                    sessions = dict(self.chat_interface._agents_sessions or {})
            except Exception:
                sessions = {}

            # Mounted badges
            mounted = set()
            try:
                if hasattr(self, 'chat_interface') and hasattr(self.chat_interface, '_agents_mounted_set'):
                    mounted = set(self.chat_interface._agents_mounted_set or set())
            except Exception:
                mounted = set()
            agents_tab = getattr(self, 'agents_tab', None)
            if agents_tab:
                names = {r.get('name', 'agent') for r in roster}
                for bucket in ('chat', 'tool'):
                    for key in list(agents_tab._route_buttons[bucket].keys()):
                        if key not in names:
                            agents_tab._route_buttons[bucket].pop(key, None)
                    for key in list(agents_tab._routing_vars[bucket].keys()):
                        if key not in names:
                            agents_tab._routing_vars[bucket].pop(key, None)
            for r in roster:
                name = r.get('name','agent')

                # PHASE SUB-ZERO-D: Planner agent has dedicated dock in TODO Manager
                if r.get('assigned_type') == 'planner':
                    continue  # Skip planner - it appears in TODO Manager instead

                tab = ttk.Frame(nb)
                label = (f"● {name}" if name in mounted else name)
                nb.add(tab, text=label)
                # Output area (scrolling)
                out = tk.Text(tab, height=10, wrap=tk.WORD, bg='#2b2b2b', fg='#d0d0d0')
                out.pack(fill=tk.BOTH, padx=6, pady=(4,2), expand=True)
                out.configure(state=tk.NORMAL)
                lines = []
                try:
                    log = (sessions.get(name, {}) or {}).get('log', [])
                    for rec in log[-100:]:
                        if not rec.get('panel_visible', True):
                            continue
                        ts = rec.get('ts', 0)
                        role = rec.get('role','sys')
                        text = rec.get('text','')
                        lines.append(f"[{role}] {text}")
                except Exception:
                    pass
                out.insert('end', "\n".join(lines) or 'No messages yet')
                out.configure(state=tk.DISABLED)
                # Chat line row: [Entry grows] | Send fixed on right
                chat_row = ttk.Frame(tab, style='Category.TFrame')
                chat_row.pack(fill=tk.X, padx=6, pady=(2,2))
                chat_row.columnconfigure(0, weight=1)
                var = tk.StringVar()
                ent = ttk.Entry(chat_row, textvariable=var)
                ent.grid(row=0, column=0, sticky=tk.EW)
                def _send(nm=name, v=var):
                    try:
                        text = (v.get() or '').strip()
                        if not text:
                            return
                        if hasattr(self.chat_interface, 'send_agent_message'):
                            self.chat_interface.send_agent_message(nm, text)
                        # Kick off per-agent inference best-effort
                        try:
                            if hasattr(self.chat_interface, 'run_agent_inference'):
                                self.chat_interface.run_agent_inference(nm, text)
                        except Exception:
                            pass
                        v.set('')
                        self._refresh_agent_dock()
                    except Exception:
                        pass
                ttk.Button(chat_row, text='Send', width=6, style='Select.TButton', command=_send).grid(row=0, column=1, padx=(6,0))

                agents_tab = getattr(self, 'agents_tab', None)
                cfg = {}
                if agents_tab:
                    try:
                        cfg = agents_tab._ensure_agent_config(name)
                    except Exception:
                        cfg = agents_tab.agent_configs.get(name, {}) if hasattr(agents_tab, 'agent_configs') else {}

                # Quick controls row (buttons align under chat line)
                controls_row = ttk.Frame(tab, style='Category.TFrame')
                controls_row.pack(fill=tk.X, padx=6, pady=(0,4))
                controls_row.columnconfigure(0, weight=1)
                controls_row.columnconfigure(1, weight=0)

                cluster = ttk.Frame(controls_row, style='Category.TFrame')
                cluster.grid(row=0, column=0, sticky=tk.W)

                def _open_conformers(n=name):
                    try:
                        if hasattr(self, 'chat_interface') and hasattr(self.chat_interface, 'show_conformers_popup'):
                            self.chat_interface.show_conformers_popup(n)
                    except Exception:
                        pass

                conf_label = 'Conformers'
                conf_style = 'Select.TButton'
                try:
                    pending_count = 0
                    if hasattr(self, 'chat_interface') and hasattr(self.chat_interface, '_conformer_events'):
                        events = self.chat_interface._conformer_events.get(name, [])
                        pending_count = len(events)
                    if pending_count > 0:
                        conf_label = f'Conformers ({pending_count})'
                        conf_style = 'Action.TButton'
                except Exception:
                    pass
                ttk.Button(cluster, text=conf_label, width=10, style=conf_style, command=_open_conformers).pack(side=tk.LEFT, padx=(0,4))
                ttk.Button(
                    cluster,
                    text='Tasks',
                    width=10,
                    style='Select.TButton',
                    command=lambda n=name: self._open_agent_tasks_popup(n)
                ).pack(side=tk.LEFT, padx=(0,4))

                def _open_agent_tools(n=name):
                    if agents_tab:
                        agents_tab._open_agent_tools_popup(n)

                ttk.Button(cluster, text='Tools…', width=10, style='Select.TButton', command=lambda nm=name: _open_agent_tools(nm)).pack(side=tk.LEFT, padx=(0,4))

                def _stop_agent(n=name):
                    try:
                        if hasattr(self.chat_interface, '_unmount_agents_all'):
                            self.chat_interface._unmount_agents_all()
                    except Exception:
                        pass
                ttk.Button(controls_row, text='Stop', width=8, style='Select.TButton', command=lambda nm=name: _stop_agent(nm)).grid(row=0, column=1, padx=(6,0), sticky=tk.E)

                # Routing + management row (routes, config, mount controls)
                route_row = ttk.Frame(tab, style='Category.TFrame')
                route_row.pack(fill=tk.X, padx=6, pady=(0,6))
                route_row.columnconfigure(0, weight=1)
                route_row.columnconfigure(1, weight=0)

                route_cluster = ttk.Frame(route_row, style='Category.TFrame')
                route_cluster.grid(row=0, column=0, sticky=tk.W)

                chat_label = 'Chat → Panel'
                tool_label = 'Tools → Panel'
                if agents_tab:
                    chat_label = agents_tab._route_button_label('chat', cfg.get('chat_route', 'panel'))
                    tool_label = agents_tab._route_button_label('tool', cfg.get('tool_route', 'panel'))

                def _cycle_chat_route(nm=name):
                    if agents_tab:
                        agents_tab._cycle_route(nm, 'chat_route')

                def _cycle_tool_route(nm=name):
                    if agents_tab:
                        agents_tab._cycle_route(nm, 'tool_route')

                chat_route_btn = ttk.Button(
                    route_cluster,
                    text=chat_label,
                    style='Select.TButton',
                    width=10,
                    command=lambda nm=name: _cycle_chat_route(nm)
                )
                chat_route_btn.pack(side=tk.LEFT, padx=(0,4))

                tool_route_btn = ttk.Button(
                    route_cluster,
                    text=tool_label,
                    style='Select.TButton',
                    width=10,
                    command=lambda nm=name: _cycle_tool_route(nm)
                )
                tool_route_btn.pack(side=tk.LEFT, padx=(0,4))

                def _mount_agent_popup(nm=name):
                    if agents_tab:
                        agents_tab._mount_agent_from_card(nm)

                ttk.Button(
                    route_cluster,
                    text='⚡ Mount',
                    style='Select.TButton',
                    width=8,
                    command=lambda nm=name: _mount_agent_popup(nm)
                ).pack(side=tk.LEFT, padx=(0,4))

                def _open_agent_config(n=name):
                    try:
                        self._open_agent_config_popup(n)
                    except Exception as e:
                        log_message(f"CUSTOM_CODE_TAB: Error opening agent config: {e}")

                ttk.Button(route_cluster, text='⚙️ Config', width=10, style='Select.TButton', command=lambda nm=name: _open_agent_config(nm)).pack(side=tk.LEFT, padx=(0,4))

                def _unmount_one(n=name):
                    try:
                        if hasattr(self, 'chat_interface') and hasattr(self.chat_interface, '_unmount_agent'):
                            self.chat_interface._unmount_agent(n)
                        self._refresh_agent_dock()
                    except Exception:
                        pass

                manage_cluster = ttk.Frame(route_row, style='Category.TFrame')
                manage_cluster.grid(row=0, column=1, sticky=tk.E)
                ttk.Button(manage_cluster, text='Unmount', width=9, style='Select.TButton', command=lambda nm=name: _unmount_one(nm)).pack(side=tk.LEFT, padx=(0,0))

                if agents_tab:
                    agents_tab._route_buttons['chat'].pop(name, None)
                    agents_tab._route_buttons['tool'].pop(name, None)
                    agents_tab._route_buttons['chat'][name] = chat_route_btn
                    agents_tab._route_buttons['tool'][name] = tool_route_btn
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Agent Tasks Queue Management
    # ------------------------------------------------------------------ #

    def _show_queue_tab(self, agent_name: str, tasks_popup, records_state, notebook, btn_row):
        """Add and populate the Queue tab in the Tasks popup"""
        log_message(f"CUSTOM_CODE_TAB: _show_queue_tab called for agent '{agent_name}'")
        try:
            # Create Queue tab
            log_message(f"CUSTOM_CODE_TAB: Creating Queue tab frame...")
            queue_frame = ttk.Frame(notebook, style='Category.TFrame')
            notebook.add(queue_frame, text="Queue")
            log_message(f"CUSTOM_CODE_TAB: Queue tab added to notebook, total tabs: {len(notebook.tabs())}")
            # Don't auto-select Queue tab - let user choose
            # notebook.select(queue_frame)  # Commented out - was forcing Queue tab to be active

            # Header with agent name and queue status
            ttk.Label(
                queue_frame,
                text=f"Task Queue: {agent_name}",
                font=("Arial", 12, "bold"),
                style='CategoryPanel.TLabel'
            ).pack(anchor=tk.W, pady=(10, 5))

            # Queue status info
            queue_info_frame = ttk.LabelFrame(queue_frame, text="Queue Status", padding=10)
            queue_info_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

            # Get current queue status
            try:
                log_message(f"CUSTOM_CODE_TAB: Importing AgentTaskQueue...")
                from agent_task_queue import AgentTaskQueue
                log_message(f"CUSTOM_CODE_TAB: Creating queue for {agent_name}...")
                queue = AgentTaskQueue(agent_name)
                queued_tasks = queue.get_queue()
                queue_length = len(queued_tasks)
                next_task = queued_tasks[0] if queued_tasks else None
                log_message(f"CUSTOM_CODE_TAB: Queue loaded - {queue_length} tasks")
            except Exception as e:
                log_message(f"CUSTOM_CODE_TAB: ERROR loading queue: {e}")
                queue_length = 0
                queued_tasks = []
                next_task = None

            # Display queue status
            status_text = f"Queued Tasks: {queue_length}"
            if next_task:
                status_text += f" | Next: {next_task.get('title', 'Unknown')}"

            ttk.Label(
                queue_info_frame,
                text=status_text,
                font=("Arial", 10),
                style='Config.TLabel'
            ).pack(anchor=tk.W)

            # Queue controls
            controls_frame = ttk.Frame(queue_frame, style='Category.TFrame')
            controls_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

            # Process Next Task button
            def process_next():
                try:
                    from agent_task_queue import AgentTaskQueue
                    queue = AgentTaskQueue(agent_name)
                    task = queue.get_next_task()
                    if task:
                        # Convert queue task back to record format
                        record = {
                            'title': task.get('title', ''),
                            'category': task.get('category', ''),
                            'priority': task.get('priority', ''),
                            'details': task.get('details', ''),
                            'plan_keys': task.get('plan_keys', []),
                            'filepath': task.get('filepath', ''),
                            'project_label': task.get('project_label', ''),
                            'agent_roles': task.get('agent_roles', ['general']),
                            'assigned_agent': agent_name,
                            'assigned_agent_role': task.get('assigned_agent_role', 'general'),
                            'working_dir_hint': task.get('working_dir_hint', ''),
                        }
                        # Assign the task normally (immediate mode)
                        success = self._assign_task_to_agent(agent_name, record, role_availability=None, queue_mode=None)
                        if success:
                            # Refresh queue status
                            self._show_queue_tab(agent_name, tasks_popup, records_state, notebook, btn_row)
                            messagebox.showinfo("Task Processed", f"Processed: {task.get('title', 'Unknown')}", parent=tasks_popup)
                    else:
                        messagebox.showinfo("Queue Empty", f"No tasks in queue for {agent_name}", parent=tasks_popup)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to process next task: {e}", parent=tasks_popup)

            ttk.Button(
                controls_frame,
                text="🚀 Process Next Task",
                style='Action.TButton',
                command=process_next,
                state=tk.NORMAL if queue_length > 0 else tk.DISABLED
            ).pack(side=tk.LEFT, padx=(0, 10))

            # Clear Queue button
            def clear_queue():
                try:
                    from agent_task_queue import AgentTaskQueue
                    queue = AgentTaskQueue(agent_name)
                    confirmed = messagebox.askyesno(
                        "Clear Queue",
                        f"Are you sure you want to clear the entire queue for {agent_name}?\n\nThis action cannot be undone.",
                        parent=tasks_popup
                    )
                    if confirmed:
                        queue.clear_queue()
                        self._show_queue_tab(agent_name, tasks_popup, records_state, notebook, btn_row)
                        messagebox.showinfo("Queue Cleared", f"Cleared queue for {agent_name}", parent=tasks_popup)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to clear queue: {e}", parent=tasks_popup)

            ttk.Button(
                controls_frame,
                text="🗑️ Clear Queue",
                style='Select.TButton',
                command=clear_queue,
                state=tk.NORMAL if queue_length > 0 else tk.DISABLED
            ).pack(side=tk.LEFT)

            # Queued tasks list
            list_frame = ttk.LabelFrame(queue_frame, text="Queued Tasks", padding=10)
            list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

            # Treeview for queued tasks
            tree = ttk.Treeview(
                list_frame,
                columns=('title', 'priority', 'category', 'status'),
                show='headings',
                height=8
            )

            tree.heading('title', text='Task Title')
            tree.heading('priority', text='Priority')
            tree.heading('category', text='Category')
            tree.heading('status', text='Status')

            tree.column('title', width=200, anchor=tk.W)
            tree.column('priority', width=80, anchor=tk.CENTER)
            tree.column('category', width=80, anchor=tk.W)
            tree.column('status', width=80, anchor=tk.W)

            # Scrollbar
            scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Populate queue list
            for i, task in enumerate(queued_tasks):
                title = task.get('title', 'Untitled')
                priority = task.get('priority', 'medium').title()
                category = task.get('category', 'unknown').title()
                status = "Queued" if i > 0 else "Next"
                tree.insert('', 'end', values=(title, priority, category, status))

                # Highlight next task
                if i == 0:
                    tree.item(tree.get_children()[0], tags=('next_task',))
                    tree.tag_configure('next_task', background='#4CAF50', foreground='white')

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error creating queue tab: {e}")
            # Fallback: just show error message
            fallback_frame = ttk.Frame(notebook, style='Category.TFrame')
            notebook.add(fallback_frame, text="Queue")
            ttk.Label(
                fallback_frame,
                text=f"Error loading queue tab: {e}",
                style='Config.TLabel',
                foreground='red'
            ).pack(pady=20)

    @_debug_ui_event(_custom_code_logger)
    def _refresh_agent_dock(self):
        try:
            self._render_or_hide_agent_dock()
        except Exception:
            pass

    def _start_conformer_flash_timer(self):
        """Start periodic check for pending conformer events to trigger flash"""
        try:
            self._conformer_flash_state = {}  # {agent_name: True/False} for toggle
            self._check_conformer_flash()
        except Exception:
            pass

    def _check_conformer_flash(self):
        """Periodic check for pending conformers - refreshes dock if events exist"""
        try:
            if hasattr(self, 'chat_interface') and hasattr(self.chat_interface, '_conformer_events'):
                events = self.chat_interface._conformer_events or {}
                has_pending = any(len(evt_list) > 0 for evt_list in events.values())

                if has_pending and self._agent_dock_open:
                    # Refresh dock to update conformer button counts/styles
                    self._refresh_agent_dock()

            # Schedule next check in 1000ms (1 second)
            self.parent.after(1000, self._check_conformer_flash)
        except Exception:
            pass

    def refresh_model_list(self):
        """Refresh the Ollama model list"""
        log_message("CUSTOM_CODE_TAB: Refreshing model list...")

        # Clear existing
        for widget in self.model_scroll_frame.winfo_children():
            widget.destroy()

        # Import config to get models and collections
        try:
            from config import (
                get_ollama_models,
                list_model_profiles,
                get_lineage_id,
                get_assigned_tags_by_lineage,
                load_ollama_assignments,
            )
            models = get_ollama_models() or []
            profiles = list_model_profiles() or []
            assignments = load_ollama_assignments() or {}
            tag_index = assignments.get('tag_index') or {}

            # Build assigned tags per variant using both v2 and legacy formats
            assigned_by_variant = {}
            for k, v in assignments.items():
                if k == 'tag_index':
                    continue
                if isinstance(v, dict):
                    tags = v.get('tags') or []
                else:
                    tags = v or []
                assigned_by_variant[k] = list(tags)
        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB ERROR: Failed to get model/collection info: {e}")
            models, profiles, tag_index, assigned_by_variant = [], [], {}, {}

        # Build active roster map for highlighting (variants/tags that are set for agents)
        active_variant_to_agents = {}
        active_tag_to_agents = {}
        def _accumulate_from_roster(roster_list):
            for r in roster_list or []:
                try:
                    if r.get('active') is False:
                        continue
                    nm = r.get('name','agent')
                    vid = (r.get('variant') or '').strip()
                    if vid:
                        active_variant_to_agents.setdefault(vid, []).append(nm)
                    tg = (r.get('ollama_tag') or r.get('ollama_tag_override') or '').strip()
                    if tg:
                        active_tag_to_agents.setdefault(tg, []).append(nm)
                    # Local GGUFs are handled as file buttons; variant row still highlights via vid
                except Exception:
                    continue
        try:
            roster = []
            # Highest priority: live config from Agents tab (what user currently set in UI)
            try:
                if hasattr(self, 'agents_tab') and hasattr(self.agents_tab, '_current_roster'):
                    roster = self.agents_tab._current_roster() or []
                    _accumulate_from_roster(roster)
            except Exception:
                pass
            # Next: active roster published to root (source for all other panels)
            try:
                roster = []
                if hasattr(self.root, 'get_active_agents') and callable(getattr(self.root, 'get_active_agents')):
                    roster = self.root.get_active_agents() or []
                _accumulate_from_roster(roster)
            except Exception:
                pass
            # Also read runtime roster snapshot for immediate cross-panel sync
            try:
                import json as _J
                from pathlib import Path as _P
                rt = _P('Data')/'user_prefs'/'agents_roster.runtime.json'
                if rt.exists():
                    runtime = _J.loads(rt.read_text()) or []
                    _accumulate_from_roster(runtime)
            except Exception:
                pass
            # If still nothing mapped, use saved defaults
            if not (active_variant_to_agents or active_tag_to_agents):
                import json as _J
                from pathlib import Path as _P
                proj = None
                try:
                    if hasattr(self.root, 'settings_tab') and getattr(self.root.settings_tab, 'current_project_context', None):
                        proj = self.root.settings_tab.current_project_context
                except Exception:
                    proj = None
                path = None
                if proj and (_P('Data')/'projects'/proj/'agents_default.json').exists():
                    path = _P('Data')/'projects'/proj/'agents_default.json'
                elif (_P('Data')/'user_prefs'/'agents_default.json').exists():
                    path = _P('Data')/'user_prefs'/'agents_default.json'
                if path:
                    try:
                        defaults = _J.loads(path.read_text()) or []
                        _accumulate_from_roster(defaults)
                    except Exception:
                        pass
        except Exception:
            pass

        # Collections section
        col_header = ttk.Frame(self.model_scroll_frame, style='Category.TFrame')
        col_header.pack(fill=tk.X, pady=(0,4))
        col_btn = ttk.Button(col_header, text=("▼" if self.cc_collections_expanded else "▶"), width=2, style='Select.TButton', command=self._toggle_cc_collections)
        col_btn.pack(side=tk.LEFT, padx=(0,5))
        ttk.Label(col_header, text="📚 Collections", font=("Arial", 11, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT)

        # Auto-expand Collections if any agents are set
        if (active_variant_to_agents or active_tag_to_agents):
            self.cc_collections_expanded = True

        if self.cc_collections_expanded:
            # Sync forced-open state with current roster: open for active, close for removed
            try:
                # Close previously forced ones no longer active
                for v in list(getattr(self, 'cc_variant_forced', set())):
                    if v not in active_variant_to_agents:
                        self.cc_variant_expanded[v] = False
                        self.cc_variant_forced.discard(v)
                # Open all active variants
                for v in active_variant_to_agents.keys():
                    self.cc_variant_expanded[v] = True
                    self.cc_variant_forced.add(v)
            except Exception:
                pass
            # List variants with per-variant expand
            variants = sorted([it.get('variant_id') for it in profiles if it.get('variant_id')])
            if not variants:
                ttk.Label(self.model_scroll_frame, text="No variants found", style='Config.TLabel').pack(fill=tk.X, padx=10, pady=(0,6))
            for vid in variants:
                row = ttk.Frame(self.model_scroll_frame, style='Category.TFrame')
                row.pack(fill=tk.X)
                # Auto-expand if variant belongs to an agent roster
                if vid in active_variant_to_agents:
                    self.cc_variant_expanded[vid] = True
                exp = self.cc_variant_expanded.get(vid, False)
                btn = ttk.Button(row, text=("▼" if exp else "▶"), width=2, style='Select.TButton', command=lambda v=vid: self._toggle_cc_variant(v))
                btn.pack(side=tk.LEFT, padx=(10,4))
                # Variant label colored by class level
                try:
                    from config import get_variant_class
                    cls = get_variant_class(vid)
                    color = {
                        'novice': '#51cf66', 'skilled': '#61dafb', 'expert': '#9b59b6', 'master': '#ffa94d', 'artifact': '#c92a2a'
                    }.get((cls or '').lower(), '#bbbbbb')
                    # If this variant is set for an agent, highlight and add agent/mounted badges
                    if vid in active_variant_to_agents:
                        agents_str = ", ".join(active_variant_to_agents.get(vid, []))
                        mounted_agents = set()
                        try:
                            if hasattr(self, 'chat_interface') and hasattr(self.chat_interface, '_agents_mounted_set'):
                                mounted_agents = set(self.chat_interface._agents_mounted_set or set())
                        except Exception:
                            mounted_agents = set()
                        mounted_flag = any(a in mounted_agents for a in active_variant_to_agents.get(vid, []))
                        label_text = f"{vid}  [agents: {agents_str}]" + ("  ● Mounted" if mounted_flag else "")
                        ttk.Label(row, text=label_text, style='Config.TLabel', foreground='#00e676').pack(side=tk.LEFT)
                    else:
                        ttk.Label(row, text=vid, style='Config.TLabel', foreground=color).pack(side=tk.LEFT)
                except Exception:
                    ttk.Label(row, text=vid, style='Config.TLabel').pack(side=tk.LEFT)
                if exp:
                    # Assigned artifacts under this variant (Ollama tags + Local GGUFs)
                    tags = []
                    local_artifacts = []
                    # v2/legacy by-variant mapping for Ollama tags
                    tags = list(assigned_by_variant.get(vid) or [])
                    if not tags:
                        try:
                            lid = get_lineage_id(vid)
                            if lid:
                                tags = get_assigned_tags_by_lineage(lid) or []
                        except Exception:
                            tags = []
                    # Get Local GGUF artifacts
                    try:
                        from config import get_local_artifacts_by_variant
                        local_artifacts = get_local_artifacts_by_variant(vid) or []
                    except Exception:
                        local_artifacts = []

                    # Display Ollama tags
                    if tags:
                        for tg in tags:
                            trow = ttk.Frame(self.model_scroll_frame, style='Category.TFrame')
                            trow.pack(fill=tk.X)
                            label_txt = "🔶 Assigned:"
                            ttk.Label(trow, text=label_txt, style='Config.TLabel', foreground='#bbbbbb').pack(side=tk.LEFT, padx=(32,6))
                            # Color tag button by owning variant class color
                            try:
                                from tkinter import ttk as _ttk
                                st = _ttk.Style()
                                style_name = f"CCColorBtn_{color.replace('#','')}\.TButton"
                                try:
                                    st.lookup(style_name, 'foreground')
                                except Exception:
                                    st.configure(style_name, foreground=color)
                                btn_style = style_name
                            except Exception:
                                btn_style = 'Select.TButton'
                            # Highlight tag if set for an agent and add Mounted badge when applicable
                            if tg in active_tag_to_agents:
                                btn_style = 'QA.Green.TButton'
                                mounted_agents = set()
                                try:
                                    if hasattr(self, 'chat_interface') and hasattr(self.chat_interface, '_agents_mounted_set'):
                                        mounted_agents = set(self.chat_interface._agents_mounted_set or set())
                                except Exception:
                                    mounted_agents = set()
                                users = active_tag_to_agents.get(tg, [])
                                mounted_flag = any(a in mounted_agents for a in users)
                                suffix = "  ● Mounted" if mounted_flag else ""
                                tg_text = f"{tg}  [agents: {', '.join(users)}]{suffix}"
                            else:
                                tg_text = tg
                            btn = ttk.Button(trow, text=tg_text, style=btn_style)
                            btn.pack(side=tk.LEFT)
                            # Use bind instead of command to support single/double-click
                            btn.bind('<Button-1>', lambda e, tag=tg, vid=vid: self._handle_cc_model_click(e, 'ollama_tag', {'variant_id': vid, 'tag': tag, 'backend': 'ollama', 'kind': 'tag', 'id': tag}))

                    # Display Local GGUFs
                    if local_artifacts:
                        for art in local_artifacts:
                            gguf_path = art.get('gguf', '')
                            quant = art.get('quant', '')
                            if gguf_path:
                                from pathlib import Path
                                grow = ttk.Frame(self.model_scroll_frame, style='Category.TFrame')
                                grow.pack(fill=tk.X)
                                ttk.Label(grow, text="🟩 Assigned:", style='Config.TLabel', foreground='#bbbbbb').pack(side=tk.LEFT, padx=(32,6))
                                gguf_name = Path(gguf_path).name
                                # Use bind instead of command to support single/double-click
                                btn = ttk.Button(grow, text=f"{gguf_name} ({quant})", style='Select.TButton')
                                btn.pack(side=tk.LEFT)
                                btn.bind('<Button-1>', lambda e, gp=gguf_path: self._handle_cc_model_click(e, 'local_gguf', {'gguf_path': gp, 'model_name': Path(gp).name, 'model_type': 'local_gguf', 'is_local_gguf': True, 'path': gp}))

                    # Show "None" only if no artifacts at all
                    if not tags and not local_artifacts:
                        ttk.Label(self.model_scroll_frame, text="Assigned: None", style='Config.TLabel', foreground='#bbbbbb').pack(fill=tk.X, padx=32)

        # Separator for clarity
        sep = ttk.Frame(self.model_scroll_frame, height=2, style='Category.TFrame')
        try:
            sep.configure()
        except Exception:
            pass
        sep.pack(fill=tk.X, pady=(10,2))

        # Unassigned section (Ollama/GGUF not assigned to any variant)
        un_header = ttk.Frame(self.model_scroll_frame, style='Category.TFrame')
        un_header.pack(fill=tk.X, pady=(10,4))
        un_btn = ttk.Button(un_header, text=("▼" if self.cc_unassigned_expanded else "▶"), width=2, style='Select.TButton', command=self._toggle_cc_unassigned)
        un_btn.pack(side=tk.LEFT, padx=(0,5))
        ttk.Label(un_header, text="🗂️ Unassigned (not linked to any variant)", font=("Arial", 11, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT)

        # Auto-expand unassigned if any rostered tag or gguf exists
        try:
            for t in active_tag_to_agents.keys():
                if t:
                    self.cc_unassigned_expanded = True
                    break
        except Exception:
            pass

        if self.cc_unassigned_expanded:
            # Normalize helper (strip trailing :suffix variations)
            def _base_tag(name: str) -> str:
                try:
                    name = (name or '').strip()
                    return name.rsplit(':', 1)[0] if ':' in name else name
                except Exception:
                    return name
            # Any model not assigned in tag_index, assignments map, or lineage-based map is unassigned (by base name)
            assigned_tags = set()
            for t in (tag_index or {}).keys():
                if t:
                    assigned_tags.add(_base_tag(t))
            for tags in assigned_by_variant.values():
                for t in (tags or []):
                    assigned_tags.add(_base_tag(t))
            # Include lineage-based assigned tags for robustness
            try:
                from config import get_lineage_id, get_assigned_tags_by_lineage
                variant_lineages = {}
                for rec in (profiles or []):
                    vid = rec.get('variant_id')
                    if not vid:
                        continue
                    try:
                        lid = get_lineage_id(vid)
                    except Exception:
                        lid = None
                    if lid:
                        variant_lineages[vid] = lid
                for lid in set(variant_lineages.values()):
                    try:
                        for t in (get_assigned_tags_by_lineage(lid) or []):
                            assigned_tags.add(_base_tag(t))
                    except Exception:
                        pass
            except Exception:
                pass
            all_unassigned = sorted([m for m in models if _base_tag(m) not in assigned_tags])
            used_tags = [m for m in all_unassigned if m in active_tag_to_agents]
            unused_tags = [m for m in all_unassigned if m not in active_tag_to_agents]
            if used_tags:
                ttk.Label(self.model_scroll_frame, text="In Use by Agents (Ollama):", style='Config.TLabel', foreground='#8be9fd').pack(fill=tk.X, padx=10)
                for m in used_tags:
                    label = f"{m}  [agents: {', '.join(active_tag_to_agents.get(m, []))}]"
                    btn = ttk.Button(self.model_scroll_frame, text=label, style='QA.Green.TButton')
                    btn.pack(fill=tk.X, padx=20, pady=1)
                    btn.bind('<Button-1>', lambda e, tag=m: self._handle_cc_model_click(e, 'ollama_tag', {'variant_id': '(unassigned)', 'tag': tag, 'backend': 'ollama', 'kind': 'tag', 'id': tag}))
            if unused_tags:
                ttk.Label(self.model_scroll_frame, text="Unassigned Ollama (unused):", style='Config.TLabel').pack(fill=tk.X, padx=10, pady=(6,2))
                for m in unused_tags:
                    btn = ttk.Button(self.model_scroll_frame, text=m, style='Category.TButton')
                    btn.pack(fill=tk.X, padx=20, pady=1)
                    btn.bind('<Button-1>', lambda e, tag=m: self._handle_cc_model_click(e, 'ollama_tag', {'variant_id': '(unassigned)', 'tag': tag, 'backend': 'ollama', 'kind': 'tag', 'id': tag}))

            # Also list local GGUF artifacts not assigned to any variant and highlight if used by agents
            try:
                from pathlib import Path as _P
                gguf_dir = _P('Data')/'exports'/'gguf'
                ggufs = []
                if gguf_dir.exists():
                    ggufs = [str(p) for p in gguf_dir.rglob('*.gguf')]
                if ggufs:
                    # Subtract GGUFs already assigned to any variant to avoid duplicates
                    assigned_paths = set()
                    try:
                        from config import get_local_artifacts_by_variant
                        for rec in (profiles or []):
                            vid = rec.get('variant_id')
                            if not vid:
                                continue
                            arts = get_local_artifacts_by_variant(vid) or []
                            for a in arts:
                                gp = a.get('gguf')
                                if gp:
                                    try:
                                        from pathlib import Path as _Path
                                        assigned_paths.add(str(_Path(gp).resolve()))
                                    except Exception:
                                        assigned_paths.add(gp)
                    except Exception:
                        assigned_paths = assigned_paths
                    try:
                        from pathlib import Path as _Path
                        ggufs = [g for g in ggufs if (str(_Path(g).resolve()) not in assigned_paths and g not in assigned_paths)]
                    except Exception:
                        ggufs = [g for g in ggufs if g not in assigned_paths]

                    # Split into used/unused by agent overrides
                    from pathlib import Path
                    used = []
                    unused = []
                    agents_roster = []
                    try:
                        if hasattr(self.root, 'get_active_agents') and callable(getattr(self.root, 'get_active_agents')):
                            agents_roster = self.root.get_active_agents() or []
                    except Exception:
                        agents_roster = []
                    for gp in sorted(ggufs):
                        agents_using = [r.get('name','agent') for r in agents_roster if (r.get('gguf_override') or '').strip() == gp]
                        if agents_using:
                            used.append((gp, agents_using))
                        else:
                            unused.append(gp)
                    if used:
                        ttk.Label(self.model_scroll_frame, text="In Use by Agents (GGUF):", style='Config.TLabel', foreground='#8be9fd').pack(fill=tk.X, padx=10, pady=(6,2))
                        for gp, users in used:
                            name = Path(gp).name
                            row = ttk.Frame(self.model_scroll_frame, style='Category.TFrame')
                            row.pack(fill=tk.X)
                            ttk.Label(row, text="🟪", style='Config.TLabel').pack(side=tk.LEFT, padx=(20,6))
                            b = ttk.Button(row, text=f"{name}  [agents: {', '.join(users)}]", style='QA.Green.TButton')
                            b.pack(side=tk.LEFT)
                            b.bind('<Button-1>', lambda e, path=gp: self._handle_cc_model_click(e, 'local_gguf', {'gguf_path': path, 'is_local_gguf': True}))
                    if unused:
                        ttk.Label(self.model_scroll_frame, text="Unassigned GGUF (unused):", style='Config.TLabel').pack(fill=tk.X, padx=10, pady=(6,2))
                        for gp in unused:
                            name = Path(gp).name
                            row = ttk.Frame(self.model_scroll_frame, style='Category.TFrame')
                            row.pack(fill=tk.X)
                            ttk.Label(row, text="🟪", style='Config.TLabel').pack(side=tk.LEFT, padx=(20,6))
                            b = ttk.Button(row, text=name, style='Select.TButton')
                            b.pack(side=tk.LEFT)
                            b.bind('<Button-1>', lambda e, path=gp: self._handle_cc_model_click(e, 'local_gguf', {'gguf_path': path, 'is_local_gguf': True}))
            except Exception:
                pass

        # Active Agents inline panel removed; replaced by the Agents Dock section below.

    def _toggle_cc_collections(self):
        self.cc_collections_expanded = not self.cc_collections_expanded
        self.refresh_model_list()

    def _toggle_right_panel_lock(self):
        try:
            self._right_panel_locked = not getattr(self, '_right_panel_locked', False)
            # Measure current width of the right pane area
            # Measure current right pane width reliably
            try:
                width = int(self._right_pane_widget.winfo_width()) if hasattr(self, '_right_pane_widget') else None
            except Exception:
                width = None
            if not width:
                try:
                    # Fallback: compute from total width minus sash position
                    pw_w = max(self._outer_pw.winfo_width(), 1)
                    sash = int(self._outer_pw.sashpos(0))
                    width = max(260, pw_w - sash)
                except Exception:
                    width = 340
            self._right_panel_width = int(width)
            if hasattr(self, '_right_lock_btn'):
                self._right_lock_btn.config(text=("🔒" if self._right_panel_locked else "🔓"))
            # Persist to backend settings
            self._backend_settings['right_panel_locked'] = bool(self._right_panel_locked)
            self._backend_settings['right_panel_width'] = int(self._right_panel_width)
            try:
                import json
                self._settings_path.write_text(json.dumps(self._backend_settings, indent=2))
            except Exception:
                pass
            # Apply behavior
            self._apply_right_lock_state()
        except Exception:
            pass

    def _apply_right_lock_state(self):
        try:
            if getattr(self, '_right_panel_locked', False):
                # Disable drag interactions and sash cursor
                try:
                    self._outer_pw.configure(cursor='arrow')
                except Exception:
                    pass
                def _block(event):
                    return 'break'
                # Bind block handlers
                for seq in ('<ButtonPress-1>', '<B1-Motion>', '<ButtonRelease-1>'):
                    self._outer_pw.bind(seq, _block)
                # Enforce current width immediately
                try:
                    pw_w = max(self._outer_pw.winfo_width(), 800)
                    width = max(260, int(getattr(self, '_right_panel_width', 340)))
                    pos = pw_w - width
                    self._outer_pw.sashpos(0, max(500, min(pos, pw_w - 260)))
                except Exception:
                    pass
            else:
                # Re-enable default behavior
                try:
                    self._outer_pw.configure(cursor='')
                except Exception:
                    pass
                for seq in ('<ButtonPress-1>', '<B1-Motion>', '<ButtonRelease-1>'):
                    try:
                        self._outer_pw.unbind(seq)
                    except Exception:
                        pass
        except Exception:
            pass

    def _toggle_cc_unassigned(self):
        self.cc_unassigned_expanded = not self.cc_unassigned_expanded
        self.refresh_model_list()

    @_debug_ui_event(_custom_code_logger)
    def _toggle_agents_panel(self):
        self.agents_panel_expanded = not getattr(self, 'agents_panel_expanded', True)
        self.refresh_model_list()

    def _render_agents_panel(self):
        try:
            # When overlay dock is open, suppress inline rendering to avoid duplication
            if getattr(self, '_agent_dock_open', False):
                return
            # Clear rows
            for w in list(self._agents_tabs_row.winfo_children()):
                w.destroy()
            for w in list(self._agents_view.winfo_children()):
                w.destroy()
            # Get current roster
            roster = []
            try:
                if hasattr(self.root, 'get_active_agents') and callable(getattr(self.root, 'get_active_agents')):
                    roster = self.root.get_active_agents() or []
            except Exception:
                roster = []
            names = [a.get('name','agent') for a in roster]
            if not names:
                ttk.Label(self._agents_view, text='No active agents', style='Config.TLabel').pack(anchor=tk.W, padx=10)
                return
            # Active tab state
            if not hasattr(self, '_agents_active_tab') or self._agents_active_tab not in names:
                self._agents_active_tab = names[0]
            def _set_tab(n):
                self._agents_active_tab = n
                self._render_agents_panel()
            mounted_set = set()
            try:
                mounted_set = set(self.chat_interface._agents_mounted_set or set())
            except Exception:
                mounted_set = set()
            for n in names:
                style = 'Select.TButton'
                label = f"{n}"
                if n in mounted_set:
                    label = f"● {n}"
                    style = 'QA.Green.TButton'
                ttk.Button(self._agents_tabs_row, text=label, style=style, command=lambda x=n: _set_tab(x)).pack(side=tk.LEFT, padx=2)
            # View: mini log + input
            from tkinter import scrolledtext as _st
            box = _st.ScrolledText(self._agents_view, height=8, wrap=tk.WORD)
            box.pack(fill=tk.BOTH, expand=True, padx=6)
            # Load log from chat interface if available
            logs = []
            try:
                sess = getattr(self.chat_interface, '_agents_sessions', {}) or {}
                logs = sess.get(self._agents_active_tab, {}).get('log', [])
            except Exception:
                logs = []
            for item in (logs or [])[-200:]:
                ts = item.get('ts')
                role = item.get('role','')
                txt = item.get('text','')
                box.insert('end', f"[{role}] {txt}\n")
            box.configure(state=tk.DISABLED)
            # Input row
            row = ttk.Frame(self._agents_view); row.pack(fill=tk.X, pady=(4,2))
            msg_var = tk.StringVar()
            def _send():
                txt = msg_var.get().strip()
                if not txt:
                    return
                msg_var.set('')
                try:
                    if hasattr(self.chat_interface, 'send_agent_message'):
                        self.chat_interface.send_agent_message(self._agents_active_tab, txt)
                except Exception:
                    pass
                # Re-render quickly to reflect new log
                self._render_agents_panel()
            ttk.Entry(row, textvariable=msg_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6,4))
            ttk.Button(row, text='Send', style='Select.TButton', command=_send).pack(side=tk.LEFT)
        except Exception:
            pass

    def _toggle_cc_variant(self, vid: str):
        self.cc_variant_expanded[vid] = not self.cc_variant_expanded.get(vid, False)
        self.refresh_model_list()

    def select_model(self, model_data):
        """Handle model selection - accepts model_data dict to determine backend"""
        # Extract model name from various possible fields
        from pathlib import Path
        if isinstance(model_data, str):
            # Legacy support: if called with just a string, use it directly
            model_name = model_data
            is_local = False
            log_message(f"CUSTOM_CODE_TAB: select_model called with string (legacy): {model_name}")
        else:
            # Modern usage: extract from dict
            model_name = model_data.get('model_name') or model_data.get('tag') or model_data.get('id') or Path(model_data.get('gguf_path', '') or model_data.get('path', 'Unknown')).name
            is_local = bool(model_data.get('is_local_gguf'))
            log_message(f"CUSTOM_CODE_TAB: Model selected: {model_name} (is_local={is_local})")

        # Update chat interface with selected model
        if hasattr(self, 'chat_interface') and self.chat_interface:
            try:
                # CRITICAL: Set backend BEFORE calling set_model()
                if is_local:
                    log_message(f"CUSTOM_CODE_TAB: Setting backend to llama_server for GGUF file")
                    self.chat_interface._set_chat_backend('llama_server')
                else:
                    log_message(f"CUSTOM_CODE_TAB: Setting backend to ollama for Ollama tag")
                    self.chat_interface._set_chat_backend('ollama')

                self.chat_interface.set_model(model_name)
                # Ensure UI reflects selection even if inner flow was bypassed
                if hasattr(self.chat_interface, '_set_model_label_with_class_color'):
                    self.chat_interface._set_model_label_with_class_color(model_name)
                if hasattr(self.chat_interface, '_update_mount_button_style'):
                    self.chat_interface._update_mount_button_style(mounted=False)
                if hasattr(self.chat_interface, 'mount_btn'):
                    self.chat_interface.mount_btn.config(state=tk.NORMAL)
            except Exception as e:
                log_message(f"CUSTOM_CODE_TAB ERROR: set_model failed: {e}")

    def _handle_cc_model_click(self, event, model_type, model_data):
        """
        Handle single/double-click on model buttons in Custom Code tab sidebar.

        Behavior depends on self._popup_feature_enabled flag:

        When DISABLED (current):
          - Single-click: Set active model (<<ModelSelected>>)
          - Double-click: Mount model (<<ModelMount>>)

        When ENABLED (future):
          - Single-click: Show popup preview (<<ModelSelectedPopup>>)
          - Double-click: Set active model (<<ModelSelected>>)
        """
        log_message(f"CUSTOM_CODE_TAB: _handle_cc_model_click called - type={model_type}, data={model_data}")
        import time
        import json as _json
        current_time = time.time()

        # Check if this is a double-click (within 250ms of last click with same data)
        is_double_click = False
        if self._last_click_data is not None:
            last_time, last_type, last_data = self._last_click_data
            if (current_time - last_time) < 0.25 and last_type == model_type and last_data == model_data:
                is_double_click = True

        # Cancel any pending single-click timer
        if self._click_timer is not None:
            self.root.after_cancel(self._click_timer)
            self._click_timer = None

        # Store data in shared attribute for event handlers
        self._pending_popup_data = model_data

        if self._popup_feature_enabled:
            # POPUP MODE: Single-click shows popup, double-click sets active
            if is_double_click:
                self._last_click_data = None
                log_message(f"CUSTOM_CODE_TAB: Double-click detected (popup mode), setting active")
                try:
                    # Pass full model_data to set active (includes is_local_gguf for backend selection)
                    self.select_model(model_data)
                except Exception as e:
                    log_message(f"CUSTOM_CODE_TAB: Error setting active: {e}")
            else:
                # Potential single-click: Schedule popup after delay
                self._last_click_data = (current_time, model_type, model_data)

                def _show_popup():
                    """Show popup after delay if not cancelled by double-click"""
                    try:
                        log_message(f"CUSTOM_CODE_TAB: Single-click confirmed (popup mode), showing popup")
                        # DIRECT CALL to our _show_model_popup method - no events!
                        self._show_model_popup(model_data)
                    except Exception as e:
                        log_message(f"CUSTOM_CODE_TAB: Error showing popup: {e}")

                self._click_timer = self.root.after(250, _show_popup)
        else:
            # DIRECT MODE: Single-click sets active, double-click mounts
            # Use direct method calls to avoid multi-instance event routing issues
            if is_double_click:
                self._last_click_data = None
                log_message(f"CUSTOM_CODE_TAB: Double-click detected (direct mode), mounting model")
                try:
                    # Pass full model_data to set active (includes is_local_gguf for backend selection)
                    self.select_model(model_data)
                    if hasattr(self, 'chat_interface') and self.chat_interface:
                        self.root.after(50, self.chat_interface.mount_model)
                except Exception as e:
                    log_message(f"CUSTOM_CODE_TAB: Error mounting model: {e}")
            else:
                # Potential single-click: Set active after delay
                self._last_click_data = (current_time, model_type, model_data)

                def _set_active():
                    """Set active after delay if not cancelled by double-click"""
                    try:
                        log_message(f"CUSTOM_CODE_TAB: Single-click confirmed (direct mode), setting active")
                        # Pass full model_data to set active (includes is_local_gguf for backend selection)
                        self.select_model(model_data)
                    except Exception as e:
                        log_message(f"CUSTOM_CODE_TAB: Error setting active: {e}")

                self._click_timer = self.root.after(250, _set_active)

    def _enrich_model_data(self, model_data: dict) -> dict:
        """
        Enrich basic model_data with profile, bundle, and lineage information.

        Takes minimal model_data (just paths) and adds:
        - variant_name (extracted from GGUF filename or Ollama tag)
        - profile data (base_model, class, skills, etc.)
        - bundle data (if available)
        """
        from pathlib import Path
        enriched = model_data.copy()

        try:
            # Extract variant name from GGUF filename or use Ollama tag
            if enriched.get('is_local_gguf'):
                gguf_path = enriched.get('gguf_path') or enriched.get('path', '')
                filename = Path(gguf_path).name
                # Remove quantization suffix (e.g., .q4_k_m.gguf, .f16.gguf)
                variant_name = filename
                for quant in ['.q4_k_m', '.q4_k_s', '.q5_k_m', '.q5_k_s', '.q8_0', '.f16', '.f32']:
                    if quant in variant_name.lower():
                        variant_name = variant_name[:variant_name.lower().index(quant)]
                        break
                enriched['variant_name'] = variant_name
                log_message(f"CUSTOM_CODE_TAB: Extracted variant_name: {variant_name}")
            else:
                # For Ollama tags, use tag as variant name
                enriched['variant_name'] = enriched.get('tag') or enriched.get('id', 'Unknown')

            # Load model profile (always fresh from disk - no caching)
            from config import load_model_profile, MODEL_PROFILES_DIR
            variant_name = enriched.get('variant_name', 'Unknown')
            try:
                # Debug: Log which file we're loading
                profile_path = MODEL_PROFILES_DIR / f"{variant_name.strip().replace('/', '_')}.json"
                log_message(f"CUSTOM_CODE_TAB: Loading profile from: {profile_path}")
                log_message(f"CUSTOM_CODE_TAB: Profile file exists: {profile_path.exists()}")

                # Force fresh load from disk (load_model_profile reads directly from file)
                profile = load_model_profile(variant_name)
                enriched['profile'] = profile

                # Debug: Log what we loaded
                log_message(f"CUSTOM_CODE_TAB: Loaded profile keys: {list(profile.keys())}")

                # Handle potentially empty/reset profiles gracefully
                enriched['base_model'] = profile.get('base_model', 'N/A')
                enriched['class'] = profile.get('assigned_type', 'unassigned')
                enriched['class_level'] = profile.get('class_level', 'novice')
                enriched['lineage_id'] = profile.get('lineage_id', '')

                # Log if profile appears to be freshly reset (no stats/xp)
                from config import get_xp_value
                has_stats = bool(profile.get('stats'))
                xp_total = get_xp_value(profile)
                has_xp = xp_total > 0

                if not has_stats and not has_xp:
                    log_message(f"CUSTOM_CODE_TAB: Loaded profile for {variant_name} (appears to be reset/new - no stats/xp): base={enriched['base_model']}, class={enriched['class']}")
                else:
                    log_message(f"CUSTOM_CODE_TAB: Loaded profile for {variant_name}: base={enriched['base_model']}, class={enriched['class']}, has_data=True")
            except Exception as e:
                log_message(f"CUSTOM_CODE_TAB: Could not load profile for {variant_name}: {e}")
                enriched['base_model'] = 'N/A'
                enriched['class'] = 'unassigned'
                enriched['class_level'] = 'novice'
                enriched['profile'] = {}

            # Try to load bundle metadata
            from registry.bundle_loader import find_bundle_by_gguf, find_bundle_by_tag, find_bundle_by_variant_id, get_variant_metadata

            bundle = None
            variant_name = enriched.get('variant_name', '')

            # Try method 1: Search by variant_id (most reliable after Reset-Lineage)
            if variant_name:
                bundle = find_bundle_by_variant_id(variant_name)
                if bundle:
                    log_message(f"CUSTOM_CODE_TAB: Found bundle for variant_id {variant_name}: {bundle.get('bundle_ulid', 'unknown')}")

            # Try method 2: Search by GGUF path
            if not bundle and enriched.get('is_local_gguf'):
                bundle = find_bundle_by_gguf(enriched.get('gguf_path', ''))
                if bundle:
                    log_message(f"CUSTOM_CODE_TAB: Found bundle for GGUF: {bundle.get('bundle_ulid', 'unknown')}")

            # Try method 3: Search by Ollama tag
            if not bundle:
                tag = enriched.get('tag') or enriched.get('id', '')
                bundle = find_bundle_by_tag(tag)
                if bundle:
                    log_message(f"CUSTOM_CODE_TAB: Found bundle for Ollama tag {tag}: {bundle.get('bundle_ulid', 'unknown')}")

            if bundle:
                enriched['bundle'] = bundle
                # Also load full metadata for this variant via bundle
                variant_id = enriched.get('variant_name', '')
                if variant_id:
                    full_metadata = get_variant_metadata(bundle, variant_id)
                    if full_metadata:
                        enriched['bundle_metadata'] = full_metadata
                        log_message(f"CUSTOM_CODE_TAB: Loaded bundle metadata for {variant_id}")

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error enriching model data: {e}")

        return enriched

    def _show_model_popup(self, model_data: dict):
        """
        Show model preview popup window with tabbed interface.

        Popup is created and owned by custom_code_tab (not chat_interface_tab).
        Buttons call methods directly on self - guaranteed correct instance.
        """
        try:
            log_message(f"CUSTOM_CODE_TAB: Creating popup for model: {model_data.get('variant_name', 'Unknown')}")
            log_message(f"CUSTOM_CODE_TAB: Initial model_data: {model_data}")

            # Enrich data first
            enriched_data = self._enrich_model_data(model_data)
            log_message(f"CUSTOM_CODE_TAB: Enriched data profile keys: {list(enriched_data.get('profile', {}).keys())}")

            # Debug: Check what we actually loaded
            profile = enriched_data.get('profile', {})
            stats = profile.get('stats', {})
            metadata = profile.get('metadata', {})
            log_message(f"CUSTOM_CODE_TAB: Profile stats keys: {list(stats.keys())}")
            log_message(f"CUSTOM_CODE_TAB: Profile metadata keys: {list(metadata.keys())}")

            # Extract token speed from nested stats structure
            performance = stats.get('performance', {})
            speed_data = performance.get('speed', {})
            token_speed = speed_data.get('value') if isinstance(speed_data, dict) else None
            log_message(f"CUSTOM_CODE_TAB: Token speed from profile: {token_speed}")

            log_message(f"CUSTOM_CODE_TAB: Context limit from profile: {metadata.get('context_length', metadata.get('context_limit'))}")
            from config import get_xp_value
            xp_total = get_xp_value(profile)
            log_message(f"CUSTOM_CODE_TAB: XP from profile: {xp_total}")

            # Create popup window
            popup = tk.Toplevel(self.root)
            # Store reference so child dialogs (Skills tests) attach above this popup
            self._current_model_popup = popup
            # Store variant_id on popup for update tracking
            popup._variant_id = model_data.get('variant_id', '')
            popup.title("Model Preview")
            popup.configure(bg='#2b2b2b')

            # Load saved position/size or use defaults
            popup_settings = self._load_popup_settings()
            geometry = popup_settings.get('geometry', '450x500+100+100')
            popup.geometry(geometry)

            # Main frame
            main_frame = ttk.Frame(popup, style='Category.TFrame')
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Header frame with title, trust indicator, and lock button
            header_frame = ttk.Frame(main_frame, style='Category.TFrame')
            header_frame.pack(fill=tk.X, pady=(0, 10))

            # Title
            title_label = ttk.Label(
                header_frame,
                text=f"📋 {enriched_data.get('variant_name', 'Unknown')}",
                font=("Arial", 14, "bold"),
                style='CategoryPanel.TLabel'
            )
            title_label.pack(side=tk.LEFT)

            # Phase 1.5E: Trust Level Indicator (if conformer available)
            if CONFORMER_AVAILABLE:
                try:
                    variant_id = enriched_data.get('variant_name', '')
                    model_class = enriched_data.get('class_level', 'Skilled').capitalize()
                    trust_indicator = TrustLevelIndicator(header_frame, variant_id=variant_id)
                    trust_indicator.pack(side=tk.LEFT, padx=(15, 0))
                    log_message(f"CUSTOM_CODE_TAB: Added trust indicator for {variant_id}")
                except Exception as e:
                    log_message(f"CUSTOM_CODE_TAB: Failed to add trust indicator: {e}")

            # Lock button
            is_locked = popup_settings.get('locked', False)
            lock_icon = "🔒" if is_locked else "🔓"
            lock_btn = ttk.Button(
                header_frame,
                text=lock_icon,
                width=3,
                command=lambda: self._toggle_popup_lock(popup, lock_btn),
                style='Select.TButton'
            )
            lock_btn.pack(side=tk.RIGHT, padx=(10, 0))
            popup.lock_btn = lock_btn
            popup.is_locked = is_locked

            # Bind window close to save position if locked
            popup.protocol("WM_DELETE_WINDOW", lambda: self._close_popup_with_save(popup))

            # Create notebook for tabs
            notebook = ttk.Notebook(main_frame)
            notebook.pack(fill=tk.BOTH, expand=True, pady=10)

            # === OVERVIEW TAB ===
            overview_frame = ttk.Frame(notebook, style='Category.TFrame')
            notebook.add(overview_frame, text="Overview")

            # Get bundle info if available
            bundle = enriched_data.get('bundle')
            bundle_metadata = enriched_data.get('bundle_metadata', {})

            # Build info text with bundle data
            name = enriched_data.get('variant_name', 'Unknown')
            base_model = enriched_data.get('base_model', 'N/A')

            # Use profile data (always fresh), fallback to bundle metadata
            class_type = enriched_data.get('class', 'unassigned') or bundle_metadata.get('assigned_type')
            class_level = enriched_data.get('class_level', 'novice') or bundle_metadata.get('class_level')
            lineage_id = enriched_data.get('lineage_id', 'N/A') or bundle_metadata.get('lineage_id')

            # Show ULID if bundle exists
            bundle_ulid = bundle.get('bundle_ulid', 'N/A') if bundle else 'N/A'
            ulid_display = bundle_ulid[:16] + '...' if bundle_ulid != 'N/A' else 'N/A (not in bundle registry)'

            # Get performance metrics
            perf_metrics = self._get_performance_metrics(enriched_data)

            # Format available backends display
            backends_info = "N/A (not in bundle registry)"
            if bundle_metadata and bundle_metadata.get('available_backends'):
                backends = bundle_metadata['available_backends']
                backend_lines = []

                # Ollama
                ollama = backends.get('ollama', {})
                if ollama.get('available'):
                    gpu_status = ""
                    if ollama.get('gpu_compatible') == True:
                        gpu_status = " (GPU-capable)"
                    elif ollama.get('gpu_compatible') == False:
                        gpu_status = " (CPU-only)"
                    backend_lines.append(f"  ✅ Ollama{gpu_status}")
                else:
                    status = ollama.get('status', 'not_found')
                    backend_lines.append(f"  ❌ Ollama ({status})")

                # GGUF
                gguf = backends.get('gguf', {})
                if gguf.get('available'):
                    quant = gguf.get('quant', 'unknown')
                    size_mb = gguf.get('size_mb', 0)
                    backend_lines.append(f"  ✅ llama-server (GGUF: {quant}, {size_mb}MB)")
                else:
                    backend_lines.append(f"  ❌ llama-server (no GGUF export)")

                # PyTorch
                pytorch = backends.get('pytorch', {})
                if pytorch.get('available'):
                    backend_lines.append(f"  ✅ PyTorch (base model)")
                else:
                    backend_lines.append(f"  ❌ PyTorch (base model only)")

                backends_info = "\n".join(backend_lines)

            # Phase 2E: Determine schema capability
            schema_status = "REQUIRED"
            schema_color = "#FF6B6B"  # Red
            class_lower = class_level.lower()

            if class_lower in ['novice', 'skilled']:
                schema_status = "REQUIRED"
                schema_color = "#FF6B6B"  # Red
            elif class_lower == 'adept':
                schema_status = "OPTIONAL"
                schema_color = "#FFD93D"  # Yellow/Gold
            elif class_lower in ['expert', 'master', 'grand_master']:
                schema_status = "NOT NEEDED"
                schema_color = "#6BCF7F"  # Green

            # Get XP/Experience info
            xp_display = "N/A"
            next_class_display = "N/A"
            try:
                from xp_calculator import get_xp_to_next_class
                variant_name = enriched_data.get('variant_name', '')
                log_message(f"CUSTOM_CODE_TAB: Getting XP for variant: {variant_name}")
                xp_info = get_xp_to_next_class(variant_name)
                log_message(f"CUSTOM_CODE_TAB: XP info received: {xp_info}")

                if xp_info.get('next_class') is None:
                    xp_display = "100% (Max Level)"
                    next_class_display = "Max Level Reached"
                else:
                    progress = xp_info.get('progress_percent', 0.0)
                    xp_display = f"{progress:.1f}%"
                    xp_remaining = xp_info.get('xp_remaining', 0)
                    next_class_display = f"{xp_info.get('next_class')} ({xp_remaining:,} XP needed)"
            except Exception as e:
                log_message(f"CUSTOM_CODE_TAB: Error getting XP info: {e}")

            info_text = f"""
Name: {name}

ULID: {ulid_display}

Parent: {base_model}

Lineage ID: {lineage_id[:32] + '...' if len(lineage_id) > 32 else lineage_id}

Type: {class_type}

Class: {class_level}

Experience: {xp_display}

Next Class: {next_class_display}

Schema Status: {schema_status}

Available Backends:
{backends_info}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Performance Metrics:
Token Speed: {perf_metrics['token_speed']}
Context Limit: {perf_metrics['context_limit']}
Memory Usage: {perf_metrics['memory_usage']}
"""

            # If bundle exists, show variant count
            if bundle:
                variant_count = len(bundle.get('variants', []))
                info_text += f"\nVariants in Bundle: {variant_count}"

            info_label = ttk.Label(
                overview_frame,
                text=info_text,
                justify=tk.LEFT,
                style='Config.TLabel',
                font=("Arial", 10)
            )
            info_label.pack(anchor=tk.W, padx=10, pady=10)

            # Show variant count in bundle (removed confusing list)
            # The "Available Backends" section above already shows what we need
            if bundle and bundle.get('variants'):
                variant_count = len(bundle.get('variants', []))
                # Only show if there are multiple variants (interesting info)
                if variant_count > 1:
                    ttk.Label(
                        overview_frame,
                        text=f"Variants in Bundle: {variant_count}",
                        font=("Arial", 9),
                        style='Config.TLabel',
                        foreground='#888888'
                    ).pack(anchor=tk.W, padx=10, pady=(10, 2))

            # Phase 1.5E: Promotion Requirements Panel
            try:
                promotion_panel = self._create_promotion_requirements_panel(
                    overview_frame,
                    enriched_data
                )
                if promotion_panel:
                    promotion_panel.pack(fill=tk.X, padx=10, pady=(15, 10))
            except Exception as e:
                log_message(f"CUSTOM_CODE_TAB: Failed to create promotion panel: {e}")

            # Phase 1.5E: Conformer Level Controls
            if CONFORMER_AVAILABLE:
                try:
                    conformer_frame = self._create_conformer_controls(
                        overview_frame,
                        enriched_data
                    )
                    if conformer_frame:
                        conformer_frame.pack(fill=tk.X, padx=10, pady=(10, 10))
                except Exception as e:
                    log_message(f"CUSTOM_CODE_TAB: Failed to create conformer controls: {e}")

            # === SKILLS TAB ===
            skills_frame = ttk.Frame(notebook, style='Category.TFrame')
            notebook.add(skills_frame, text="Skills")

            # Bottom-anchored Test-Tools launcher (tests root-level tool execution)
            bottom_row = ttk.Frame(skills_frame, style='Category.TFrame')
            bottom_row.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(6, 10))
            ttk.Button(
                bottom_row,
                text="Test-Tools",
                style='Action.TButton',
                command=lambda: self._open_skills_test_launcher(enriched_data),
                width=16
            ).pack()

            # Get skills data from multiple sources
            skills_data = bundle_metadata.get('skills', {})

            # Load comprehensive variant data using unified loader
            skills_map = {}
            runtime_skills = {}
            tool_prof = {}
            try:
                import config as C
                vid = enriched_data.get('variant_name') if isinstance(enriched_data, dict) else None
                if vid:
                    # Use unified data loader for consistency across all UI
                    variant_data = C.load_complete_variant_data(vid)
                    skills_map = variant_data["skills"]["evaluation"]  # Evaluation skills
                    runtime_skills = variant_data["skills"]["runtime"]  # Runtime usage
                    tool_prof = variant_data["tool_proficiency"]  # F-AAA grades
                    log_message(f"CUSTOM_CODE_TAB: Loaded complete data - Runtime: {len(runtime_skills)}, Eval: {len(skills_map)}, Prof: {len(tool_prof)}")
            except Exception as e:
                log_message(f"CUSTOM_CODE_TAB: Error loading skills from config: {e}")

            # Create scrollable skills area
            skills_canvas = tk.Canvas(skills_frame, bg="#2b2b2b", highlightthickness=0)
            skills_scrollbar = ttk.Scrollbar(skills_frame, orient="vertical", command=skills_canvas.yview)
            skills_content = ttk.Frame(skills_canvas, style='Category.TFrame')

            skills_content.bind(
                "<Configure>",
                lambda e: skills_canvas.configure(scrollregion=skills_canvas.bbox("all"))
            )

            skills_canvas.create_window((0, 0), window=skills_content, anchor="nw")
            skills_canvas.configure(yscrollcommand=skills_scrollbar.set)

            skills_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))
            skills_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Evaluation Skills Section (from config.get_model_skills)
            if skills_map or skills_data:
                ttk.Label(
                    skills_content,
                    text="📋 Evaluation Skills",
                    font=("Arial", 11, "bold"),
                    foreground="#61dafb",
                    style='CategoryPanel.TLabel'
                ).pack(anchor=tk.W, pady=(5, 10))

                # Skills from config (priority source)
                if skills_map:
                    for skill, data in sorted(skills_map.items()):
                        if skill == '__meta__':
                            continue

                        skill_row = ttk.Frame(skills_content, style='Category.TFrame')
                        skill_row.pack(fill=tk.X, padx=10, pady=2)

                        status = (data or {}).get('status', 'Unknown')
                        # Set icon and color based on actual status
                        if status == "Verified":
                            icon = "✅"
                            color = "#00ff00"  # Green
                        elif status == "Partial":
                            icon = "⚠️"
                            color = "#ffff00"  # Yellow
                        elif status == "Failed":
                            icon = "❌"
                            color = "#ff6b6b"  # Red
                        else:  # Unknown
                            icon = "○"
                            color = "#888888"  # Gray

                        ttk.Label(
                            skill_row,
                            text=f"{icon} {skill}",
                            font=("Arial", 10),
                            foreground=color,
                            style='Config.TLabel'
                        ).pack(side=tk.LEFT)

                        # Show explicit status label
                        ttk.Label(
                            skill_row,
                            text=f"({status})",
                            font=("Arial", 9),
                            foreground="#888888",
                            style='Config.TLabel'
                        ).pack(side=tk.LEFT, padx=(5, 0))

                        if status == "Verified":
                            verified_at = (data or {}).get('verified_at', '')
                            if verified_at:
                                ttk.Label(
                                    skill_row,
                                    text=f"[{verified_at[:10]}]",
                                    font=("Arial", 9),
                                    foreground="#888888",
                                    style='Config.TLabel'
                                ).pack(side=tk.RIGHT)
                elif not skills_map and skills_data:
                    # Fallback to bundle metadata if no config data
                    for skill_name, skill_info in sorted(skills_data.items()):
                        if skill_info.get('xp', 0) >= 80:
                            skill_row = ttk.Frame(skills_content, style='Category.TFrame')
                            skill_row.pack(fill=tk.X, padx=10, pady=2)

                            ttk.Label(
                                skill_row,
                                text=f"✅ {skill_name}",
                                font=("Arial", 10),
                                foreground="#00ff00",
                                style='Config.TLabel'
                            ).pack(side=tk.LEFT)

                            ttk.Label(
                                skill_row,
                                text=f"XP: {skill_info.get('xp', 0)}",
                                font=("Arial", 9),
                                foreground="#888888",
                                style='Config.TLabel'
                            ).pack(side=tk.RIGHT)
            else:
                ttk.Label(
                    skills_content,
                    text="No verified skills yet",
                    style='Config.TLabel',
                    foreground="#888888"
                ).pack(anchor=tk.W, pady=(5, 10), padx=10)

            # Runtime Skills Section (actual usage data)
            if runtime_skills:
                ttk.Separator(skills_content, orient='horizontal').pack(fill=tk.X, pady=10)

                ttk.Label(
                    skills_content,
                    text="📊 Runtime Usage Statistics",
                    font=("Arial", 11, "bold"),
                    foreground="#61dafb",
                    style='CategoryPanel.TLabel'
                ).pack(anchor=tk.W, pady=(5, 10))

                for skill, data in sorted(runtime_skills.items()):
                    skill_row = ttk.Frame(skills_content, style='Category.TFrame')
                    skill_row.pack(fill=tk.X, padx=10, pady=2)

                    success_rate = data.get('success_rate', 0)
                    total_calls = data.get('total_calls', 0)

                    # Color based on success rate
                    if success_rate >= 80:
                        color = "#00ff00"  # Green
                        icon = "✅"
                    elif success_rate >= 50:
                        color = "#ffff00"  # Yellow
                        icon = "⚠️"
                    else:
                        color = "#ff6b6b"  # Red
                        icon = "❌"

                    ttk.Label(
                        skill_row,
                        text=f"{icon} {skill}",
                        font=("Arial", 10),
                        foreground=color,
                        style='Config.TLabel'
                    ).pack(side=tk.LEFT)

                    ttk.Label(
                        skill_row,
                        text=f"({success_rate:.0f}% success, {total_calls} calls)",
                        font=("Arial", 9),
                        foreground="#888888",
                        style='Config.TLabel'
                    ).pack(side=tk.LEFT, padx=(10, 0))

            # Tool-Use Grades Section (F-AAA Performance)
            ttk.Separator(skills_content, orient='horizontal').pack(fill=tk.X, pady=10)

            ttk.Label(
                skills_content,
                text="🔧 Tool-Use Grades (F-AAA Performance)",
                font=("Arial", 11, "bold"),
                foreground="#61dafb",
                style='CategoryPanel.TLabel'
            ).pack(anchor=tk.W, pady=(5, 5))

            ttk.Label(
                skills_content,
                text="Grades based on tool execution success in real usage",
                font=("Arial", 9, "italic"),
                foreground="#888888",
                style='Config.TLabel'
            ).pack(anchor=tk.W, pady=(0, 10))

            if tool_prof:
                # Helper to get grade color
                def grade_color(grade: str) -> str:
                    colors = {
                        'AAA': '#00ff00',  # Green
                        'AA': '#7fff00',   # Yellow-green
                        'A': '#ffff00',    # Yellow
                        'B': '#ffa500',    # Orange
                        'C': '#ff6347',    # Red-orange
                        'F': '#ff0000'     # Red
                    }
                    return colors.get(grade, '#888888')

                for tool, data in sorted(tool_prof.items()):
                    prof_row = ttk.Frame(skills_content, style='Category.TFrame')
                    prof_row.pack(fill=tk.X, padx=10, pady=2)

                    grade = (data or {}).get('grade', 'F')
                    score = (data or {}).get('score', 0.0)
                    attempts = (data or {}).get('attempts', 0)

                    # Tool name
                    ttk.Label(
                        prof_row,
                        text=f"{tool}:",
                        font=("Arial", 10),
                        style='Config.TLabel',
                        width=18
                    ).pack(side=tk.LEFT)

                    # Grade badge
                    tk.Label(
                        prof_row,
                        text=f"[{grade}]",
                        font=("Arial", 10, "bold"),
                        foreground=grade_color(grade),
                        bg="#2b2b2b"
                    ).pack(side=tk.LEFT, padx=5)

                    # Score and attempts
                    ttk.Label(
                        prof_row,
                        text=f"{score:.1%} ({attempts} tests)",
                        font=("Arial", 9),
                        foreground="#888888",
                        style='Config.TLabel'
                    ).pack(side=tk.LEFT)
            else:
                ttk.Label(
                    skills_content,
                    text="No tool proficiency data yet.\n\nUse Test-Skills button below to assess tools.",
                    justify=tk.CENTER,
                    style='Config.TLabel',
                    foreground="#888888"
                ).pack(pady=10, padx=10)

                # (Button added at bottom row after canvas)

            # (Bottom-anchored button created earlier so it always reserves space)

            # === CLASS TAB ===
            class_frame = ttk.Frame(notebook, style='Category.TFrame')
            notebook.add(class_frame, text="Class")

            # Check if model has any training/evaluation data (promotion eligibility)
            from config import get_xp_value
            profile = enriched_data.get('profile', {})
            has_stats = bool(profile.get('stats'))
            xp_total = get_xp_value(profile)
            has_xp = xp_total > 0

            # Show warning if model has no training data
            if not has_stats and not has_xp:
                warning_frame = ttk.LabelFrame(class_frame, text="⚠️ Promotion Status", style='TLabelframe')
                warning_frame.pack(fill=tk.X, padx=20, pady=(15, 10))

                ttk.Label(
                    warning_frame,
                    text="Not Eligible - No training or evaluation data",
                    font=("Arial", 11, "bold"),
                    foreground="#ff6b6b",
                    style='Config.TLabel'
                ).pack(pady=(10, 5))

                ttk.Label(
                    warning_frame,
                    text="Complete training sessions and evaluations to become eligible for promotion.",
                    wraplength=380,
                    font=("Arial", 9),
                    style='Config.TLabel'
                ).pack(pady=(5, 10), padx=10)

            # Normalize level naming: internal gates use 'skilled', UI uses 'adept'
            def _ui_level_name(s: str) -> str:
                return 'adept' if s == 'skilled' else s

            # Class progression info
            ttk.Label(
                class_frame,
                text=f"Current Class: {class_level}",
                font=("Arial", 12, "bold"),
                style='CategoryPanel.TLabel'
            ).pack(pady=(20, 10))

            ttk.Label(
                class_frame,
                text=f"Type: {class_type}",
                font=("Arial", 10),
                style='Config.TLabel'
            ).pack(pady=5)

            # Load classes gates from type catalog
            gates = {}
            try:
                import json as _json
                tpath = Path(__file__).parent.parent.parent / "type_catalog_v2.json"
                if tpath.exists():
                    cat = _json.loads(tpath.read_text())
                    for t in (cat.get('types') or []):
                        if t.get('id') == class_type:
                            gates = t.get('classes') or {}
                            break
            except Exception:
                gates = {}

            # Load latest eval pass rate and verified skills
            eval_rate = 0.0
            verified_skills = set()
            try:
                import config as C
                vid = enriched_data.get('variant_name') if isinstance(enriched_data, dict) else None
                if vid:
                    skills_map = C.get_model_skills(vid) or {}
                    meta = skills_map.get('__meta__') or {}
                    pr = meta.get('pass_rate_percent') or '0%'
                    try:
                        eval_rate = float(str(pr).replace('%','')) / 100.0
                    except Exception:
                        eval_rate = 0.0
                    for sk, entry in skills_map.items():
                        if sk == '__meta__':
                            continue
                        if (entry or {}).get('status') == 'Verified':
                            verified_skills.add(sk)
            except Exception:
                pass

            # Progress section
            ttk.Label(
                class_frame,
                text="Class Progression:",
                font=("Arial", 11, "bold"),
                style='CategoryPanel.TLabel'
            ).pack(pady=(20, 10))

            class_levels_ui = ["novice", "adept", "expert", "master"]
            # Map current class to index; accept both 'skilled' and 'adept'
            cur = class_level
            if cur == 'skilled':
                cur = 'adept'
            current_idx = class_levels_ui.index(cur) if cur in class_levels_ui else 0

            for idx, level in enumerate(class_levels_ui):
                level_frame = ttk.Frame(class_frame, style='Category.TFrame')
                level_frame.pack(fill=tk.X, padx=20, pady=3)

                if idx < current_idx:
                    icon = "✅"; color = "#00ff00"
                elif idx == current_idx:
                    icon = "➤"; color = "#61dafb"
                else:
                    icon = "○"; color = "#888888"

                ttk.Label(level_frame, text=f"{icon} {level.capitalize()}", font=("Arial", 10), foreground=color, style='CategoryPanel.TLabel').pack(side=tk.LEFT)

            # Gate summary for next level
            req_label = ttk.Label(class_frame, text="", style='Config.TLabel')
            req_label.pack(pady=(12, 4))
            prog_label = ttk.Label(class_frame, text="", style='Config.TLabel')
            prog_label.pack(pady=(0, 12))

            # Compute next level gates and eligibility (including tool proficiency)
            level_order_model = ["novice", "skilled", "expert", "master"]
            # Map UI -> model key
            ui_to_model = {"novice":"novice", "adept":"skilled", "expert":"expert", "master":"master"}
            cur_model_key = ui_to_model.get(cur, 'novice')
            next_key = None
            try:
                idx = level_order_model.index(cur_model_key)
                next_key = level_order_model[idx+1] if idx+1 < len(level_order_model) else None
            except Exception:
                next_key = None

            eligible = False
            reasons = []
            prof_reqs_str = ''
            prof_ok = True
            # Load current tool proficiency grades from profile
            cur_prof = {}
            try:
                import config as C
                vid = enriched_data.get('variant_name') if isinstance(enriched_data, dict) else None
                if vid:
                    mp = C.load_model_profile(vid) or {}
                    cur_prof = mp.get('tool_proficiency') or {}
            except Exception:
                cur_prof = {}
            if next_key and isinstance(gates, dict):
                g = gates.get(next_key) or {}
                min_eval = float(g.get('min_eval', 0.0))
                req_skills = list(g.get('required_skills') or [])
                req_label.config(text=f"Next: {_ui_level_name(next_key).capitalize()} • Requires eval ≥ {int(min_eval*100)}% and skills: {', '.join(req_skills) or '—'}")
                met_skills = [s for s in req_skills if s in verified_skills]
                prog_label.config(text=f"Current eval {eval_rate*100:.0f}% • Skills verified {len(met_skills)}/{len(req_skills)}")
                # Tool proficiency requirements
                req_prof = g.get('tool_proficiency') or {}
                if req_prof:
                    # Build comparison function
                    rank = { 'F':0,'C':1,'B':2,'A':3,'AA':4,'AAA':5 }
                    unmet = []
                    for tool, req in req_prof.items():
                        want_grade = None
                        if isinstance(req, str):
                            want_grade = req
                        elif isinstance(req, dict):
                            want_grade = req.get('min_grade')
                        # fallback: numeric score
                        want_score = None
                        if isinstance(req, (int, float)):
                            want_score = float(req)
                        else:
                            try:
                                want_score = float(req.get('min_score')) if isinstance(req, dict) and req.get('min_score') is not None else None
                            except Exception:
                                want_score = None
                        got = cur_prof.get(tool) or {}
                        # IMPORTANT: Only gate on proficiency if model-derived data exists.
                        # If no record present for this tool, skip gating for it.
                        if not got:
                            continue
                        got_grade = got.get('grade') or 'F'
                        got_score = float(got.get('score') or 0.0)
                        ok_grade = (want_grade is None) or (rank.get(got_grade,0) >= rank.get(want_grade,0))
                        ok_score = (want_score is None) or (got_score >= want_score)
                        if not (ok_grade and ok_score):
                            unmet.append((tool, want_grade or (f"{want_score}")))
                    prof_ok = (len(unmet) == 0)
                    if unmet:
                        parts = []
                        for tool, w in unmet:
                            gcur = (cur_prof.get(tool) or {}).get('grade') or 'F'
                            parts.append(f"{tool} ({gcur}<{w})")
                        prof_reqs_str = "; ".join(parts)
                # Eligibility
                eligible = (eval_rate >= min_eval) and (len(met_skills) == len(req_skills)) and prof_ok
                if eval_rate < min_eval:
                    reasons.append(f"Eval below threshold ({eval_rate*100:.0f}%<{int(min_eval*100)}%)")
                if len(met_skills) != len(req_skills):
                    missing = [s for s in req_skills if s not in met_skills]
                    if missing:
                        reasons.append(f"Skill(s) not verified: {', '.join(missing)}")
                if not prof_ok and prof_reqs_str:
                    reasons.append(f"Tool proficiency unmet: {prof_reqs_str}")
            else:
                req_label.config(text="Next: — • Gates unavailable for this type")
                prog_label.config(text=f"Current eval {eval_rate*100:.0f}% • Skills verified —")
                eligible = False

            # Actions
            ttk.Label(
                class_frame,
                text="Class Actions:",
                font=("Arial", 11, "bold"),
                style='CategoryPanel.TLabel'
            ).pack(pady=(10, 6))

            # Why-Locked hint
            if not eligible and reasons:
                why = ttk.Label(class_frame, text=f"Why locked: {'; '.join(reasons)}", style='Config.TLabel', foreground='#ffaa00')
                why.pack(pady=(0,6))

            action_frame = ttk.Frame(class_frame, style='Category.TFrame')
            action_frame.pack(pady=6)

            ttk.Button(action_frame, text="Train", style='Action.TButton', command=lambda: self._show_train_dialog(enriched_data), width=11).pack(side=tk.LEFT, padx=3)
            ttk.Button(action_frame, text="Test-Skills", style='Action.TButton', command=lambda: self._show_class_skill_eval_dialog(enriched_data), width=11).pack(side=tk.LEFT, padx=3)
            ttk.Button(action_frame, text="Eval", style='Action.TButton', command=lambda: self._show_eval_dialog(enriched_data), width=11).pack(side=tk.LEFT, padx=3)
            # Phase 4: Training session button
            ttk.Button(action_frame, text="Training Session", style='Action.TButton', command=lambda: self._show_training_session_dialog(enriched_data), width=15).pack(side=tk.LEFT, padx=3)
            # CTA: Open Tools for enabling or reruns
            def _open_tools_tab():
                try:
                    self.sub_notebook.select(self.tools_tab_frame)
                except Exception:
                    pass
            ttk.Button(action_frame, text="Open Tools", style='Select.TButton', command=_open_tools_tab, width=11).pack(side=tk.LEFT, padx=3)

            levelup_btn = ttk.Button(action_frame, text="Level-Up", style='Action.TButton', command=lambda: self._show_levelup_dialog(enriched_data), width=11)
            try:
                if not eligible:
                    levelup_btn.state(["disabled"])  # gate by requirements
                else:
                    # Store button reference for flash animation (Phase 2B)
                    variant_id = enriched_data.get('variant_id') or enriched_data.get('trainee_name')
                    if variant_id:
                        if not hasattr(self, '_levelup_buttons'):
                            self._levelup_buttons = {}
                        self._levelup_buttons[variant_id] = levelup_btn
            except Exception:
                pass
            levelup_btn.pack(side=tk.LEFT, padx=3)

            # === QUICK SETTINGS TAB ===
            quick_settings_frame = ttk.Frame(notebook, style='Category.TFrame')
            notebook.add(quick_settings_frame, text="Quick-Settings")

            # Backend selection label
            backend_label = ttk.Label(
                quick_settings_frame,
                text="Backend Selection:",
                font=("Arial", 11, "bold"),
                style='Config.TLabel'
            )
            backend_label.pack(pady=(20, 10))

            # Get current backend
            current_backend = self.chat_interface._get_chat_backend() if hasattr(self, 'chat_interface') and self.chat_interface else 'ollama'

            # Backend button frame
            backend_btn_frame = ttk.Frame(quick_settings_frame, style='Category.TFrame')
            backend_btn_frame.pack(pady=10)

            # Store reference for indicator updates
            popup.backend_buttons = {}

            # Get available backends from bundle metadata
            available_backends = {}
            if bundle_metadata and bundle_metadata.get('available_backends'):
                available_backends = bundle_metadata['available_backends']

            # Ollama button
            ollama_available = available_backends.get('ollama', {}).get('available', False)
            ollama_gpu_compatible = available_backends.get('ollama', {}).get('gpu_compatible', None)

            ollama_label = "Ollama"
            if ollama_available:
                if ollama_gpu_compatible == True:
                    ollama_label = "Ollama (GPU)"
                elif ollama_gpu_compatible == False:
                    ollama_label = "Ollama (CPU)"

            ollama_btn = ttk.Button(
                backend_btn_frame,
                text=ollama_label,
                command=lambda: self._set_backend_from_popup('ollama', popup, enriched_data) if ollama_available else None,
                style='Action.TButton' if current_backend == 'ollama' else 'Select.TButton',
                width=14,
                state=tk.NORMAL if ollama_available else tk.DISABLED
            )
            ollama_btn.pack(side=tk.LEFT, padx=5)
            popup.backend_buttons['ollama'] = ollama_btn

            # Add tooltip for disabled Ollama button
            if not ollama_available:
                status = available_backends.get('ollama', {}).get('status', 'not_found')
                self._create_tooltip(ollama_btn, f"Ollama unavailable: {status}")

            # llama-server button
            gguf_available = available_backends.get('gguf', {}).get('available', False)
            gguf_quant = available_backends.get('gguf', {}).get('quant', '')

            llama_label = "llama-server"
            if gguf_available and gguf_quant:
                llama_label = f"llama-server ({gguf_quant})"

            llama_btn = ttk.Button(
                backend_btn_frame,
                text=llama_label,
                command=lambda: self._set_backend_from_popup('llama_server', popup, enriched_data) if gguf_available else None,
                style='Action.TButton' if current_backend == 'llama_server' else 'Select.TButton',
                width=14,
                state=tk.NORMAL if gguf_available else tk.DISABLED
            )
            llama_btn.pack(side=tk.LEFT, padx=5)
            popup.backend_buttons['llama_server'] = llama_btn

            # Add tooltip for disabled llama-server button
            if not gguf_available:
                self._create_tooltip(llama_btn, "No GGUF export available for this model")

            # AUTO button (always enabled, uses router logic)
            auto_btn = ttk.Button(
                backend_btn_frame,
                text="Auto-Select",
                command=lambda: self._set_backend_auto_from_popup(enriched_data, popup),
                style='Select.TButton',
                width=14
            )
            auto_btn.pack(side=tk.LEFT, padx=5)
            popup.auto_select_btn = auto_btn  # Store reference for style updates
            popup.auto_select_active = False  # Track auto-select state

            # Backend indicator
            backend_indicator = ttk.Label(
                quick_settings_frame,
                text=f"Current: {current_backend.replace('_', '-').upper()}",
                font=("Arial", 9),
                style='Config.TLabel',
                foreground='#888888'
            )
            backend_indicator.pack(pady=(5, 0))
            popup.backend_indicator = backend_indicator

            # === Hardware Control Section ===
            ttk.Frame(quick_settings_frame, height=20).pack()  # Spacer

            hardware_control_label = ttk.Label(
                quick_settings_frame,
                text="Hardware Control:",
                font=("Arial", 11, "bold"),
                style='Config.TLabel'
            )
            hardware_control_label.pack(pady=(5, 5))

            hardware_control_btn_frame = ttk.Frame(quick_settings_frame)
            hardware_control_btn_frame.pack(pady=5)

            # Store reference for indicator updates
            popup.hardware_control_buttons = {}

            # Detect current hardware mode from backend settings
            current_hw_mode = 'auto'  # Default
            if hasattr(self, 'chat_interface') and self.chat_interface:
                n_gpu_layers = self.chat_interface.backend_settings.get('llama_server_gpu_layers', 0)
                cpu_threads = self.chat_interface.backend_settings.get('cpu_threads', 0)

                # Determine mode from current settings
                if n_gpu_layers > 0 and cpu_threads > 0:
                    current_hw_mode = 'hybrid'
                elif n_gpu_layers > 0:
                    current_hw_mode = 'gpu'
                elif cpu_threads > 0:
                    current_hw_mode = 'cpu'

            # GPU button
            gpu_hw_btn = ttk.Button(
                hardware_control_btn_frame,
                text="GPU",
                command=lambda: self._set_hardware_mode_from_popup('gpu', popup, enriched_data),
                style='Action.TButton' if current_hw_mode == 'gpu' else 'Select.TButton',
                width=12
            )
            gpu_hw_btn.pack(side=tk.LEFT, padx=5)
            popup.hardware_control_buttons['gpu'] = gpu_hw_btn

            # CPU button
            cpu_hw_btn = ttk.Button(
                hardware_control_btn_frame,
                text="CPU",
                command=lambda: self._set_hardware_mode_from_popup('cpu', popup, enriched_data),
                style='Action.TButton' if current_hw_mode == 'cpu' else 'Select.TButton',
                width=12
            )
            cpu_hw_btn.pack(side=tk.LEFT, padx=5)
            popup.hardware_control_buttons['cpu'] = cpu_hw_btn

            # GPU & CPU button (hybrid)
            hybrid_hw_btn = ttk.Button(
                hardware_control_btn_frame,
                text="GPU & CPU",
                command=lambda: self._set_hardware_mode_from_popup('hybrid', popup, enriched_data),
                style='Action.TButton' if current_hw_mode == 'hybrid' else 'Select.TButton',
                width=12
            )
            hybrid_hw_btn.pack(side=tk.LEFT, padx=5)
            popup.hardware_control_buttons['hybrid'] = hybrid_hw_btn

            # Auto button (let mode decide)
            auto_hw_btn = ttk.Button(
                hardware_control_btn_frame,
                text="Auto",
                command=lambda: self._set_hardware_mode_from_popup('auto', popup, enriched_data),
                style='Action.TButton' if current_hw_mode == 'auto' else 'Select.TButton',
                width=12
            )
            auto_hw_btn.pack(side=tk.LEFT, padx=5)
            popup.hardware_control_buttons['auto'] = auto_hw_btn

            # Hardware mode indicator
            hw_mode_indicator = ttk.Label(
                quick_settings_frame,
                text=f"Hardware Mode: {current_hw_mode.upper()}",
                font=("Arial", 9),
                style='Config.TLabel',
                foreground='#888888'
            )
            hw_mode_indicator.pack(pady=(5, 0))
            popup.hw_mode_indicator = hw_mode_indicator

            # === Mode Detection and Soft Suggestion ===
            import json
            current_mode = 'standard'  # Default
            mode_settings_path = Path(__file__).parent / 'mode_settings.json'

            if mode_settings_path.exists():
                try:
                    with open(mode_settings_path, 'r') as f:
                        mode_data = json.load(f)
                        current_mode = mode_data.get('current_mode', 'standard').lower()
                except Exception as e:
                    log_message(f"CUSTOM_CODE_TAB: Error reading mode settings: {e}")

            # Show soft suggestion for non-standard modes
            if current_mode != 'standard':
                ttk.Frame(quick_settings_frame, height=15).pack()  # Spacer

                mode_banner = ttk.Frame(quick_settings_frame, style='Category.TFrame', relief=tk.RIDGE, borderwidth=1)
                mode_banner.pack(pady=10, padx=20, fill=tk.X)

                mode_text = {
                    'fast': 'Fast mode recommends AUTO for quick responses',
                    'smart': 'Smart mode recommends AUTO for optimal balance',
                    'think': 'Think mode recommends AUTO for thorough analysis'
                }.get(current_mode, 'AUTO mode recommended')

                suggestion_icon = ttk.Label(mode_banner, text="💡", font=("Arial", 14))
                suggestion_icon.pack(side=tk.LEFT, padx=(5, 10), pady=5)

                suggestion_label = ttk.Label(
                    mode_banner,
                    text=f"{mode_text} (you can override)",
                    font=("Arial", 9, "italic"),
                    style='Config.TLabel'
                )
                suggestion_label.pack(side=tk.LEFT, pady=5)

                # Store suggestion for resource button highlighting
                popup.suggested_resource = 'auto'
            else:
                popup.suggested_resource = None

            # === Hardware Status Section ===
            ttk.Frame(quick_settings_frame, height=20).pack()  # Spacer

            hardware_header = ttk.Label(
                quick_settings_frame,
                text="Hardware Status:",
                font=("Arial", 11, "bold"),
                style='Config.TLabel'
            )
            hardware_header.pack(pady=(10, 5))

            # Hardware info frame
            hw_frame = ttk.Frame(quick_settings_frame, style='Category.TFrame')
            hw_frame.pack(pady=5, padx=10, fill=tk.X)

            # Detect capabilities on popup open
            from .capabilities import detect_capabilities
            caps = detect_capabilities()

            # GPU info
            gpus = caps.get('gpus', [])
            if gpus:
                gpu = gpus[0]
                gpu_name = gpu.get('name', 'Unknown')
                vram_free_mb = gpu.get('vram_free_mb', 0)
                vram_total_mb = gpu.get('vram_total_mb', 0)
                vram_text = f"{gpu_name} - {vram_free_mb/1024:.1f}GB free / {vram_total_mb/1024:.1f}GB total"
            else:
                vram_text = "No GPU detected"

            gpu_label = ttk.Label(hw_frame, text=f"GPU: {vram_text}", style='Config.TLabel', font=("Arial", 9))
            gpu_label.pack(anchor=tk.W, padx=5, pady=2)

            # CPU info
            cpu_info = caps.get('cpu', {})
            cpu_count = cpu_info.get('cores', 0)
            cpu_model = cpu_info.get('model', 'Unknown CPU')
            # Truncate CPU model if too long
            if len(cpu_model) > 50:
                cpu_model = cpu_model[:47] + "..."
            cpu_label = ttk.Label(hw_frame, text=f"CPU: {cpu_count} cores - {cpu_model}", style='Config.TLabel', font=("Arial", 9))
            cpu_label.pack(anchor=tk.W, padx=5, pady=2)

            # RAM info
            ram = caps.get('ram', {})
            ram_available_gb = ram.get('available_gb', 0)
            ram_total_gb = ram.get('total_gb', 0)
            ram_label = ttk.Label(hw_frame, text=f"RAM: {ram_available_gb:.1f}GB free / {ram_total_gb:.1f}GB total", style='Config.TLabel', font=("Arial", 9))
            ram_label.pack(anchor=tk.W, padx=5, pady=2)

            # Refresh button
            refresh_btn = ttk.Button(
                hw_frame,
                text="Refresh",
                command=lambda: self._refresh_hardware_status(popup),
                style='Select.TButton',
                width=10
            )
            refresh_btn.pack(pady=(5, 0))

            # Store labels for updates
            popup.hw_gpu_label = gpu_label
            popup.hw_cpu_label = cpu_label
            popup.hw_ram_label = ram_label

            # === Resource Allocation Section ===
            ttk.Frame(quick_settings_frame, height=15).pack()  # Spacer

            # Calculate resource values based on backend and hardware
            has_gpu = len(caps.get('gpus', [])) > 0
            vram_free_gb = (gpus[0].get('vram_free_mb', 0) / 1024) if gpus else 0
            cpu_count = caps.get('cpu', {}).get('cores', 8)

            # Determine resource type and values
            if current_backend == 'llama_server':
                resource_type_label = "GPU Layers" if has_gpu else "CPU Threads"

                if has_gpu:
                    # GPU mode: calculate layers based on VRAM
                    if vram_free_gb >= 6:
                        max_val, med_val, min_val = 35, 25, 15
                    elif vram_free_gb >= 4:
                        max_val, med_val, min_val = 30, 20, 10
                    else:
                        max_val, med_val, min_val = 20, 15, 5
                else:
                    # CPU mode: use thread counts
                    max_val = cpu_count
                    med_val = max(cpu_count // 2, 4)
                    min_val = max(cpu_count // 4, 2)
            else:
                # Ollama backend: CPU threads
                resource_type_label = "CPU Threads"
                max_val = cpu_count
                med_val = max(cpu_count // 2, 4)
                min_val = max(cpu_count // 4, 2)

            resource_label = ttk.Label(
                quick_settings_frame,
                text=f"Resource Allocation ({resource_type_label}):",
                font=("Arial", 11, "bold"),
                style='Config.TLabel'
            )
            resource_label.pack(pady=(10, 10))
            popup.resource_label = resource_label  # Store for updates

            # Resource button frame
            resource_btn_frame = ttk.Frame(quick_settings_frame, style='Category.TFrame')
            resource_btn_frame.pack(pady=10)

            # Store reference for indicator updates
            popup.resource_buttons = {}

            # Get current setting
            if current_backend == 'llama_server':
                if has_gpu:
                    current_val = self.chat_interface.backend_settings.get('llama_server_gpu_layers', 25) if hasattr(self, 'chat_interface') else 25
                else:
                    current_val = self.chat_interface.backend_settings.get('cpu_threads', 8) if hasattr(self, 'chat_interface') else 8
            else:
                current_val = self.chat_interface.backend_settings.get('cpu_threads', 8) if hasattr(self, 'chat_interface') else 8

            # Determine active button
            active_resource = 'auto'
            if current_val == max_val:
                active_resource = 'max'
            elif current_val == med_val:
                active_resource = 'med'
            elif current_val == min_val:
                active_resource = 'min'

            # Detect current hardware mode (for hybrid resource allocation)
            current_n_gpu = self.chat_interface.backend_settings.get('llama_server_gpu_layers', 0) if hasattr(self, 'chat_interface') else 0
            current_cpu = self.chat_interface.backend_settings.get('cpu_threads', 0) if hasattr(self, 'chat_interface') else 0
            is_hybrid_mode = (current_n_gpu > 0 and current_cpu > 0)

            # Max button - sets BOTH GPU + CPU in hybrid mode
            max_btn = ttk.Button(
                resource_btn_frame,
                text=f"Max ({max_val})",
                command=lambda: self._set_resource_from_popup('max', max_val, popup, current_backend, has_gpu, cpu_count, is_hybrid_mode),
                style='Action.TButton' if active_resource == 'max' else 'Select.TButton',
                width=12
            )
            max_btn.pack(side=tk.LEFT, padx=5)
            popup.resource_buttons['max'] = max_btn

            # Med button - sets BOTH GPU + CPU in hybrid mode
            med_btn = ttk.Button(
                resource_btn_frame,
                text=f"Med ({med_val})",
                command=lambda: self._set_resource_from_popup('med', med_val, popup, current_backend, has_gpu, cpu_count, is_hybrid_mode),
                style='Action.TButton' if active_resource == 'med' else 'Select.TButton',
                width=12
            )
            med_btn.pack(side=tk.LEFT, padx=5)
            popup.resource_buttons['med'] = med_btn

            # Min button - sets BOTH GPU + CPU in hybrid mode
            min_btn = ttk.Button(
                resource_btn_frame,
                text=f"Min ({min_val})",
                command=lambda: self._set_resource_from_popup('min', min_val, popup, current_backend, has_gpu, cpu_count, is_hybrid_mode),
                style='Action.TButton' if active_resource == 'min' else 'Select.TButton',
                width=12
            )
            min_btn.pack(side=tk.LEFT, padx=5)
            popup.resource_buttons['min'] = min_btn

            # Auto button (mode-aware)
            auto_highlighted = (active_resource == 'auto' or
                              (hasattr(popup, 'suggested_resource') and popup.suggested_resource == 'auto'))
            auto_res_btn = ttk.Button(
                resource_btn_frame,
                text="Auto",
                command=lambda: self._set_resource_auto_from_popup(popup, current_mode, current_backend, has_gpu, vram_free_gb, cpu_count),
                style='Action.TButton' if auto_highlighted else 'Select.TButton',
                width=12
            )
            auto_res_btn.pack(side=tk.LEFT, padx=5)
            popup.resource_buttons['auto'] = auto_res_btn

            # === Comprehensive Status Indicators ===
            ttk.Frame(quick_settings_frame, height=10).pack()  # Spacer

            status_frame = ttk.Frame(quick_settings_frame, style='Category.TFrame')
            status_frame.pack(pady=5, padx=10, fill=tk.X)

            # Get current settings
            current_n_gpu_layers = 0
            current_cpu_threads = 0
            if hasattr(self, 'chat_interface') and self.chat_interface:
                current_n_gpu_layers = self.chat_interface.backend_settings.get('llama_server_gpu_layers', 0)
                current_cpu_threads = self.chat_interface.backend_settings.get('cpu_threads', 0)

            # Determine hardware mode display
            if current_n_gpu_layers > 0 and current_cpu_threads > 0:
                hw_mode_display = "GPU & CPU (Hybrid)"
            elif current_n_gpu_layers > 0:
                hw_mode_display = "GPU"
            elif current_cpu_threads > 0:
                hw_mode_display = "CPU"
            else:
                hw_mode_display = "Auto"

            # Mode indicator
            mode_indicator = ttk.Label(
                status_frame,
                text=f"Mode: {current_mode.capitalize()}",
                font=("Arial", 9, "bold"),
                style='Config.TLabel',
                foreground='#4CAF50'
            )
            mode_indicator.pack(anchor=tk.W, padx=5, pady=1)
            popup.mode_indicator = mode_indicator

            # Hardware mode indicator (existing one, will be updated)
            hw_status_indicator = ttk.Label(
                status_frame,
                text=f"Hardware: {hw_mode_display}",
                font=("Arial", 9),
                style='Config.TLabel',
                foreground='#888888'
            )
            hw_status_indicator.pack(anchor=tk.W, padx=5, pady=1)
            popup.hw_status_indicator = hw_status_indicator

            # GPU layers indicator
            gpu_layers_indicator = ttk.Label(
                status_frame,
                text=f"GPU Layers: {current_n_gpu_layers}",
                font=("Arial", 9),
                style='Config.TLabel',
                foreground='#888888'
            )
            gpu_layers_indicator.pack(anchor=tk.W, padx=5, pady=1)
            popup.gpu_layers_indicator = gpu_layers_indicator

            # CPU threads indicator
            cpu_threads_indicator = ttk.Label(
                status_frame,
                text=f"CPU Threads: {current_cpu_threads}",
                font=("Arial", 9),
                style='Config.TLabel',
                foreground='#888888'
            )
            cpu_threads_indicator.pack(anchor=tk.W, padx=5, pady=1)
            popup.cpu_threads_indicator = cpu_threads_indicator

            # Keep backward compatibility with resource_indicator reference
            # Point to gpu_layers_indicator for legacy code
            popup.resource_indicator = gpu_layers_indicator

            # Button frame at bottom
            button_frame = ttk.Frame(main_frame, style='Category.TFrame')
            button_frame.pack(fill=tk.X, pady=(10, 0))

            # Set-Active button - DIRECT CALL to self.select_model()
            ttk.Button(
                button_frame,
                text="Set-Active",
                command=lambda: self._set_active_from_popup(enriched_data, popup),
                style='Action.TButton'
            ).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

            # Quick-Mount button - DIRECT CALL to self.select_model() + mount
            ttk.Button(
                button_frame,
                text="Quick-Mount",
                command=lambda: self._quick_mount_from_popup(enriched_data, popup),
                style='Action.TButton'
            ).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

            # Close button
            ttk.Button(
                button_frame,
                text="Close",
                command=popup.destroy,
                style='Select.TButton'
            ).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

            log_message("CUSTOM_CODE_TAB: Popup created successfully")

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error creating popup: {e}")

    def _create_promotion_requirements_panel(self, parent, model_data: dict):
        """
        Phase 1.5E: Create promotion requirements panel showing gates and progress.

        Returns ttk.Frame with promotion checklist, or None if not applicable.
        """
        try:
            variant_id = model_data.get('variant_name', '')
            class_level = model_data.get('class_level', 'novice').lower()

            # Only show for models that can be promoted (novice through master)
            if class_level == 'grand_master':
                return None  # Grand Master models can't promote further

            # Define next class (matches type_catalog_v2.json structure)
            class_progression = {
                'novice': 'Skilled',
                'skilled': 'Adept',
                'adept': 'Expert',
                'expert': 'Master',
                'master': 'Grand Master'
            }
            next_class = class_progression.get(class_level, 'Unknown')

            # Create panel frame
            panel = ttk.LabelFrame(
                parent,
                text=f"🎯 Promotion to {next_class.upper()}",
                style='Category.TFrame',
                padding=10
            )

            # Load requirements (stubbed for now - will integrate with training system)
            # TODO: Integrate with actual training/eval system
            requirements = self._get_promotion_requirements(variant_id, class_level)

            # Requirements list
            for req in requirements:
                req_frame = ttk.Frame(panel, style='Category.TFrame')
                req_frame.pack(fill=tk.X, pady=2)

                # Status icon
                icon = "✓" if req['met'] else "✗"
                color = "#00ff00" if req['met'] else "#ff4444"
                status_label = ttk.Label(
                    req_frame,
                    text=icon,
                    foreground=color,
                    font=("Arial", 12, "bold"),
                    style='CategoryPanel.TLabel'
                )
                status_label.pack(side=tk.LEFT, padx=(0, 8))

                # Requirement text
                req_text = f"{req['name']}: {req['current']} / {req['target']} ({req['status']})"
                req_label = ttk.Label(
                    req_frame,
                    text=req_text,
                    style='Config.TLabel',
                    font=("Arial", 9)
                )
                req_label.pack(side=tk.LEFT)

            # Next steps section
            if not all(r['met'] for r in requirements):
                ttk.Separator(panel, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(10, 8))

                ttk.Label(
                    panel,
                    text="Next Steps:",
                    font=("Arial", 10, "bold"),
                    style='CategoryPanel.TLabel'
                ).pack(anchor=tk.W, pady=(0, 5))

                unmet = [r for r in requirements if not r['met']]
                for i, req in enumerate(unmet[:3], 1):  # Show top 3 unmet
                    step_text = f"{i}. {req['action']}"
                    ttk.Label(
                        panel,
                        text=step_text,
                        style='Config.TLabel',
                        font=("Arial", 9),
                        foreground='#888888'
                    ).pack(anchor=tk.W, padx=(10, 0))
            else:
                # Ready to promote!
                ttk.Separator(panel, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(10, 8))

                ready_label = ttk.Label(
                    panel,
                    text="✅ Ready to Promote!",
                    font=("Arial", 11, "bold"),
                    foreground="#00ff00",
                    style='CategoryPanel.TLabel'
                )
                ready_label.pack(anchor=tk.W, pady=(0, 5))

                ttk.Button(
                    panel,
                    text="🚀 Promote to " + next_class,
                    style='Action.TButton',
                    command=lambda: self._handle_promotion(variant_id, next_class)
                ).pack(anchor=tk.W, pady=(5, 0))

            return panel

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error creating promotion panel: {e}")
            return None

    def _get_promotion_requirements(self, variant_id: str, current_class: str) -> list:
        """
        Get promotion requirements for a variant.

        Returns list of dicts with: name, current, target, met, status, action
        """
        requirements = []

        try:
            # Phase 2: Use real check_promotion_readiness from config
            import config
            readiness = config.check_promotion_readiness(variant_id, notify=False)

            if readiness.get('error'):
                return []  # Can't check requirements

            # XP Requirement
            xp_check = readiness.get('xp_check', {})
            requirements.append({
                'name': 'XP',
                'current': xp_check.get('current', 0),
                'target': xp_check.get('required', 0),
                'met': xp_check.get('passed', False),
                'status': 'COMPLETE' if xp_check.get('passed') else 'INCOMPLETE',
                'action': f"Gain {xp_check.get('deficit', 0)} more XP through tool feedback"
            })

            # Eval Score
            eval_check = readiness.get('eval_check', {})
            requirements.append({
                'name': 'Eval Score',
                'current': f"{eval_check.get('current', 0.0) * 100:.0f}%",
                'target': f"{eval_check.get('required', 0.0) * 100:.0f}%",
                'met': eval_check.get('passed', False),
                'status': 'COMPLETE' if eval_check.get('passed') else 'INCOMPLETE',
                'action': f"Run evaluation and achieve {eval_check.get('required', 0.0) * 100:.0f}%+ score"
            })

            # Skills
            skills_check = readiness.get('skills_check', {})
            missing = skills_check.get('missing', [])
            requirements.append({
                'name': 'Skills',
                'current': len(skills_check.get('verified', [])),
                'target': len(skills_check.get('required', [])),
                'met': skills_check.get('passed', False),
                'status': 'COMPLETE' if skills_check.get('passed') else 'INCOMPLETE',
                'action': f"Verify missing skills: {', '.join(missing)}" if missing else "All skills verified"
            })

            # Phase 2E: Schema-free check (only for Skilled → Adept)
            schema_free = readiness.get('schema_free_check', {})
            if schema_free.get('tested'):
                requirements.append({
                    'name': 'Schema-Free Capability',
                    'current': schema_free.get('current', 0),
                    'target': schema_free.get('required', 10),
                    'met': schema_free.get('passed', False),
                    'status': 'COMPLETE' if schema_free.get('passed') else 'INCOMPLETE',
                    'action': schema_free.get('message', 'Test schema-free tool execution')
                })

            # Stat Gates
            stat_gates = readiness.get('stat_gates', {})
            if not stat_gates.get('passed', True):
                failed_gates = [g for g in stat_gates.get('failed_gates', []) if g.get('status') == 'failed']
                if failed_gates:
                    gate_names = ', '.join([g.get('stat_name', 'unknown') for g in failed_gates[:3]])
                    requirements.append({
                        'name': 'Stat Gates',
                        'current': f"{len(stat_gates.get('failed_gates', []))} failed",
                        'target': 'All passed',
                        'met': False,
                        'status': 'INCOMPLETE',
                        'action': f"Improve stats: {gate_names}"
                    })

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error getting promotion requirements: {e}")
            # Return empty list on error
            return []

        return requirements

    def _handle_promotion(self, variant_id: str, next_class: str):
        """Handle promotion button click"""
        from tkinter import messagebox

        # TODO: Integrate with actual promotion system
        result = messagebox.askyesno(
            "Promote Model",
            f"Promote {variant_id} to {next_class} class?\n\n"
            f"This will create a new variant with upgraded capabilities."
        )

        if result:
            log_message(f"CUSTOM_CODE_TAB: User confirmed promotion of {variant_id} to {next_class}")
            # TODO: Call actual promotion logic from models_tab or training system
            messagebox.showinfo("Promotion", f"Promotion feature coming soon!\n\nWill promote {variant_id} to {next_class}.")

    def _create_conformer_controls(self, parent, model_data: dict):
        """
        Phase 1.5E: Create conformer level controls.

        Shows current trust level with dropdown to manually adjust.
        """
        try:
            variant_id = model_data.get('variant_name', '')
            if not variant_id:
                return None

            gate = get_conformer_gate()
            model_class = model_data.get('class_level', 'Skilled').capitalize()
            current_level = gate.get_conformer_level(variant_id, model_class)

            # Create frame
            frame = ttk.LabelFrame(
                parent,
                text="🛡️ Trust & Conformer Settings",
                style='Category.TFrame',
                padding=10
            )

            # Description
            from config import CONFORMER_PRIORITIES
            level_desc = CONFORMER_PRIORITIES.get(current_level, {}).get('description', 'Unknown')

            ttk.Label(
                frame,
                text=f"Current Level: {current_level.capitalize()}",
                font=("Arial", 10, "bold"),
                style='CategoryPanel.TLabel'
            ).pack(anchor=tk.W, pady=(0, 5))

            ttk.Label(
                frame,
                text=level_desc,
                style='Config.TLabel',
                font=("Arial", 9),
                foreground='#888888',
                wraplength=400
            ).pack(anchor=tk.W, pady=(0, 10))

            # Controls row
            controls_row = ttk.Frame(frame, style='Category.TFrame')
            controls_row.pack(fill=tk.X)

            ttk.Label(
                controls_row,
                text="Adjust Trust Level:",
                style='Config.TLabel',
                font=("Arial", 9)
            ).pack(side=tk.LEFT, padx=(0, 10))

            # Dropdown
            level_var = tk.StringVar(value=current_level)
            level_combo = ttk.Combobox(
                controls_row,
                textvariable=level_var,
                values=['strict', 'high', 'medium', 'low', 'minimal'],
                state='readonly',
                width=12
            )
            level_combo.pack(side=tk.LEFT, padx=(0, 10))

            def on_level_change(event=None):
                new_level = level_var.get()
                if new_level != current_level:
                    success = gate.set_conformer_level(variant_id, new_level)
                    if success:
                        log_message(f"CUSTOM_CODE_TAB: Changed {variant_id} conformer to {new_level}")
                        # Update description
                        new_desc = CONFORMER_PRIORITIES.get(new_level, {}).get('description', 'Unknown')
                        desc_label.config(text=new_desc)
                        from tkinter import messagebox
                        messagebox.showinfo(
                            "Trust Level Updated",
                            f"Conformer level for {variant_id} updated to {new_level}.\n\n"
                            f"This change takes effect immediately for all operations."
                        )
                    else:
                        log_message(f"CUSTOM_CODE_TAB: Failed to change {variant_id} conformer level")

            level_combo.bind('<<ComboboxSelected>>', on_level_change)

            # Store reference to description label for updates
            desc_label = [w for w in frame.winfo_children() if isinstance(w, ttk.Label) and w.cget('foreground') == '#888888'][0]

            # Help text
            ttk.Label(
                frame,
                text="💡 Lower trust levels require more approvals for file operations.",
                style='Config.TLabel',
                font=("Arial", 8),
                foreground='#666666'
            ).pack(anchor=tk.W, pady=(10, 0))

            return frame

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error creating conformer controls: {e}")
            return None

    def _create_tooltip(self, widget, text):
        """Create a simple tooltip for a widget"""
        def show_tooltip(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")

            label = ttk.Label(
                tooltip,
                text=text,
                background="#ffffe0",
                foreground="#000000",
                relief=tk.SOLID,
                borderwidth=1,
                padding=5
            )
            label.pack()

            widget._tooltip = tooltip

        def hide_tooltip(event):
            if hasattr(widget, '_tooltip'):
                widget._tooltip.destroy()
                delattr(widget, '_tooltip')

        widget.bind('<Enter>', show_tooltip)
        widget.bind('<Leave>', hide_tooltip)

    def _set_active_in_interface(self, target_iface, model_data: dict):
        """Apply Set-Active to a specific ChatInterfaceTab instance (Chat or Projects)."""
        try:
            from pathlib import Path as _Path
            if isinstance(model_data, str):
                model_name = model_data
                is_local = False
            else:
                model_name = model_data.get('model_name') or model_data.get('tag') or model_data.get('id') or _Path(model_data.get('gguf_path', '') or model_data.get('path', 'Unknown')).name
                is_local = bool(model_data.get('is_local_gguf'))
            # Set backend on target
            if is_local:
                target_iface._set_chat_backend('llama_server')
            else:
                target_iface._set_chat_backend('ollama')
            # Set model on target
            target_iface.set_model(model_name)
            # Update mount state if UI available
            try:
                if hasattr(target_iface, '_set_model_label_with_class_color'):
                    target_iface._set_model_label_with_class_color(model_name)
                if hasattr(target_iface, 'mount_btn'):
                    target_iface.mount_btn.config(state=tk.NORMAL)
            except Exception:
                pass
        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: _set_active_in_interface error: {e}")

    def _set_active_from_popup(self, model_data: dict, popup):
        """Set model as active from popup - DIRECT call to select_model()"""
        try:
            log_message(f"CUSTOM_CODE_TAB: Set-Active clicked in popup")

            # Choose target interface based on current sub-tab selection (Projects vs Chat)
            target_iface = None
            try:
                current_tab = self.sub_notebook.select() if hasattr(self, 'sub_notebook') else None
                if current_tab and hasattr(self, 'projects_tab_frame') and str(current_tab) == str(self.projects_tab_frame):
                    target_iface = getattr(self, 'projects_interface', None)
                else:
                    target_iface = getattr(self, 'chat_interface', None)
            except Exception:
                target_iface = getattr(self, 'chat_interface', None)
            if target_iface is not None:
                self._set_active_in_interface(target_iface, model_data)
            else:
                self.select_model(model_data)

            popup.destroy()
            log_message("CUSTOM_CODE_TAB: Set-Active completed successfully")

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error in _set_active_from_popup: {e}")

    def _quick_mount_from_popup(self, model_data: dict, popup):
        """Quick mount model from popup - DIRECT calls to select_model() + mount_model()"""
        try:
            log_message(f"CUSTOM_CODE_TAB: Quick-Mount clicked in popup")

            # Choose target interface based on current sub-tab selection
            target_iface = None
            try:
                current_tab = self.sub_notebook.select() if hasattr(self, 'sub_notebook') else None
                if current_tab and hasattr(self, 'projects_tab_frame') and str(current_tab) == str(self.projects_tab_frame):
                    target_iface = getattr(self, 'projects_interface', None)
                else:
                    target_iface = getattr(self, 'chat_interface', None)
            except Exception:
                target_iface = getattr(self, 'chat_interface', None)
            if target_iface is not None:
                self._set_active_in_interface(target_iface, model_data)
                if hasattr(target_iface, 'mount_model'):
                    self.root.after(50, target_iface.mount_model)
            else:
                self.select_model(model_data)
                if hasattr(self, 'chat_interface') and self.chat_interface:
                    self.root.after(50, self.chat_interface.mount_model)

            popup.destroy()
            log_message("CUSTOM_CODE_TAB: Quick-Mount completed successfully")

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error in _quick_mount_from_popup: {e}")

    def _set_backend_from_popup(self, backend: str, popup, model_data: dict = None, from_auto_select: bool = False):
        """Set backend from popup Quick-Settings tab"""
        try:
            log_message(f"CUSTOM_CODE_TAB: Setting backend to {backend}")

            # Mark auto-select as inactive ONLY if this is a manual override (not from auto-select)
            if not from_auto_select and hasattr(popup, 'auto_select_active') and popup.auto_select_active:
                popup.auto_select_active = False
                if hasattr(popup, 'auto_select_btn'):
                    popup.auto_select_btn.config(style='Select.TButton')  # Back to gray
                    log_message(f"CUSTOM_CODE_TAB: Auto-Select deactivated (manual override)")

            if hasattr(self, 'chat_interface') and self.chat_interface:
                # Set the backend
                self.chat_interface._set_chat_backend(backend)

                # Update button styles
                for backend_name, btn in popup.backend_buttons.items():
                    if backend_name == backend:
                        btn.config(style='Action.TButton')
                    else:
                        btn.config(style='Select.TButton')

                # Update indicator
                display_name = backend.replace('_', '-').upper()
                popup.backend_indicator.config(text=f"Current: {display_name}")

                # Update resource controls based on backend
                if hasattr(popup, 'resource_buttons'):
                    if backend == 'ollama':
                        # Switch to CPU thread control for Ollama
                        popup.resource_label.config(text="Resource Allocation (CPU Threads):")
                        current_cpu_threads = self.chat_interface.backend_settings.get('cpu_threads', 8)
                        popup.resource_indicator.config(text=f"CPU Threads: {current_cpu_threads}")
                    else:
                        # Switch to GPU layers control for llama-server
                        popup.resource_label.config(text="Resource Allocation (GPU Layers):")
                        current_n_gpu_layers = self.chat_interface.backend_settings.get('llama_server_gpu_layers', 25)
                        popup.resource_indicator.config(text=f"GPU Layers: {current_n_gpu_layers}")

                log_message(f"CUSTOM_CODE_TAB: Backend set to {backend} successfully")

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error setting backend: {e}")

    def _set_backend_auto_from_popup(self, model_data: dict, popup):
        """Set backend automatically based on model type (toggle on/off)"""
        try:
            # Toggle behavior: if already active, deactivate
            if hasattr(popup, 'auto_select_active') and popup.auto_select_active:
                log_message(f"CUSTOM_CODE_TAB: Deactivating AUTO (toggle off)")

                # Mark as inactive
                popup.auto_select_active = False

                # Turn button back to gray
                if hasattr(popup, 'auto_select_btn'):
                    popup.auto_select_btn.config(style='Select.TButton')

                log_message(f"CUSTOM_CODE_TAB: Auto-Select deactivated, backend remains as set")
                return  # Don't change backend, leave it as is

            # Activate auto-select
            log_message(f"CUSTOM_CODE_TAB: Setting backend to AUTO")

            # Mark auto-select as active
            popup.auto_select_active = True

            # Determine backend from model type
            is_local = bool(model_data.get('is_local_gguf'))
            backend = 'llama_server' if is_local else 'ollama'

            log_message(f"CUSTOM_CODE_TAB: AUTO selected {backend} (is_local={is_local})")

            # Use the same method to set backend (with from_auto_select=True to prevent deactivation)
            self._set_backend_from_popup(backend, popup, model_data, from_auto_select=True)

            # Set Auto-Select button to green (Action.TButton style)
            if hasattr(popup, 'auto_select_btn'):
                popup.auto_select_btn.config(style='Action.TButton')

            # CASCADE: Auto-Select also sets Hardware Control to Auto
            log_message(f"CUSTOM_CODE_TAB: Auto-Select cascading to Hardware Control Auto")
            self._set_hardware_mode_from_popup('auto', popup, model_data)

            log_message(f"CUSTOM_CODE_TAB: Auto-Select complete (backend + hardware set to auto)")

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error in AUTO backend selection: {e}")

    def _set_resource_from_popup(self, level: str, value: int, popup, backend: str, has_gpu: bool, cpu_count: int = 8, is_hybrid: bool = False):
        """Set resource allocation level from popup Quick-Settings tab

        Args:
            level: 'max', 'med', or 'min'
            value: Primary value (GPU layers or CPU threads)
            is_hybrid: If True, set BOTH GPU + CPU (user requirement for Standard mode)
        """
        try:
            if is_hybrid and has_gpu:
                # HYBRID MODE: Set BOTH GPU + CPU
                # User requirement: "set both gpu/cpu if available"

                n_gpu_layers = value  # Use the provided value for GPU

                # Calculate corresponding CPU threads based on level
                if level == 'max':
                    cpu_threads = cpu_count  # All cores
                elif level == 'med':
                    cpu_threads = max(cpu_count // 2, 4)  # Half cores
                else:  # min
                    cpu_threads = max(cpu_count // 4, 2)  # Quarter cores

                log_message(f"CUSTOM_CODE_TAB: HYBRID {level} - GPU: {n_gpu_layers}, CPU: {cpu_threads}")

                # Set both values
                self.chat_interface.backend_settings['llama_server_gpu_layers'] = n_gpu_layers
                self.chat_interface.backend_settings['cpu_threads'] = cpu_threads
                self.chat_interface._save_backend_setting('llama_server_gpu_layers', n_gpu_layers)
                self.chat_interface._save_backend_setting('cpu_threads', cpu_threads)

                # Update indicators
                indicator_text = f"GPU Layers: {n_gpu_layers}"
                if hasattr(popup, 'gpu_layers_indicator'):
                    popup.gpu_layers_indicator.config(text=f"GPU Layers: {n_gpu_layers}")
                if hasattr(popup, 'cpu_threads_indicator'):
                    popup.cpu_threads_indicator.config(text=f"CPU Threads: {cpu_threads}")
                if hasattr(popup, 'hw_status_indicator'):
                    popup.hw_status_indicator.config(text=f"Hardware: GPU & CPU (Hybrid)")

            else:
                # SINGLE MODE: Set either GPU OR CPU (original behavior)
                if backend == 'llama_server':
                    if has_gpu:
                        # Setting GPU layers only
                        log_message(f"CUSTOM_CODE_TAB: Setting resource level to {level} ({value} GPU layers)")
                        setting_key = 'llama_server_gpu_layers'
                        indicator_text = f"GPU Layers: {value}"
                    else:
                        # CPU mode for llama-server
                        log_message(f"CUSTOM_CODE_TAB: Setting resource level to {level} ({value} CPU threads)")
                        setting_key = 'cpu_threads'
                        indicator_text = f"CPU Threads: {value}"
                else:
                    # Setting CPU threads for Ollama
                    log_message(f"CUSTOM_CODE_TAB: Setting resource level to {level} ({value} CPU threads)")
                    setting_key = 'cpu_threads'
                    indicator_text = f"CPU Threads: {value}"

                # Update backend setting
                if hasattr(self, 'chat_interface') and self.chat_interface:
                    # Store in backend settings for persistence
                    self.chat_interface.backend_settings[setting_key] = value
                    self.chat_interface._save_backend_setting(setting_key, value)

                    # Update comprehensive status indicators
                    if setting_key == 'llama_server_gpu_layers':
                        if hasattr(popup, 'gpu_layers_indicator'):
                            popup.gpu_layers_indicator.config(text=f"GPU Layers: {value}")
                    elif setting_key == 'cpu_threads':
                        if hasattr(popup, 'cpu_threads_indicator'):
                            popup.cpu_threads_indicator.config(text=f"CPU Threads: {value}")

            # Update button styles
            if hasattr(self, 'chat_interface') and self.chat_interface:
                for level_name, btn in popup.resource_buttons.items():
                    if level_name == level:
                        btn.config(style='Action.TButton')
                    else:
                        btn.config(style='Select.TButton')

                # Update legacy indicator
                popup.resource_indicator.config(text=indicator_text)

                log_message(f"CUSTOM_CODE_TAB: Resource level set to {level} successfully")

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error setting resource level: {e}")

    def _set_resource_auto_from_popup(self, popup, mode: str, backend: str, has_gpu: bool, vram_free_gb: float, cpu_count: int):
        """Set resource allocation to AUTO (mode-aware smart detection)"""
        try:
            log_message(f"CUSTOM_CODE_TAB: AUTO resource allocation - mode={mode}, backend={backend}, has_gpu={has_gpu}")

            # Calculate auto value based on mode and hardware
            if mode == 'fast':
                # Fast mode: low resources for quick responses
                if backend == 'llama_server' and has_gpu:
                    auto_value = 10  # Low GPU layers
                    setting_key = 'llama_server_gpu_layers'
                    indicator_text = f"GPU Layers: {auto_value}"
                else:
                    auto_value = max(cpu_count // 4, 2)  # Min CPU threads
                    setting_key = 'cpu_threads'
                    indicator_text = f"CPU Threads: {auto_value}"

            elif mode == 'smart':
                # Smart mode: VRAM-aware allocation
                if backend == 'llama_server' and has_gpu:
                    if vram_free_gb >= 4:
                        auto_value = 35  # High GPU usage
                    elif vram_free_gb >= 2:
                        auto_value = 20  # Medium GPU usage
                    else:
                        auto_value = 10  # Low GPU usage
                    setting_key = 'llama_server_gpu_layers'
                    indicator_text = f"GPU Layers: {auto_value}"
                else:
                    auto_value = max(cpu_count // 2, 4)  # Half CPU threads
                    setting_key = 'cpu_threads'
                    indicator_text = f"CPU Threads: {auto_value}"

            elif mode == 'think':
                # Think mode: maximum resources
                if backend == 'llama_server' and has_gpu:
                    auto_value = 35  # Max GPU layers
                    setting_key = 'llama_server_gpu_layers'
                    indicator_text = f"GPU Layers: {auto_value}"
                else:
                    auto_value = cpu_count  # All CPU cores
                    setting_key = 'cpu_threads'
                    indicator_text = f"CPU Threads: {auto_value}"

            else:  # standard mode
                # Standard mode: balanced allocation
                if backend == 'llama_server' and has_gpu:
                    auto_value = 25  # Balanced GPU usage
                    setting_key = 'llama_server_gpu_layers'
                    indicator_text = f"GPU Layers: {auto_value}"
                else:
                    auto_value = max(cpu_count // 2, 4)  # Half CPU threads
                    setting_key = 'cpu_threads'
                    indicator_text = f"CPU Threads: {auto_value}"

            log_message(f"CUSTOM_CODE_TAB: Auto selected {auto_value} for {setting_key}")

            # Apply the setting
            if hasattr(self, 'chat_interface') and self.chat_interface:
                self.chat_interface.backend_settings[setting_key] = auto_value
                self.chat_interface._save_backend_setting(setting_key, auto_value)

                # Update button styles
                for level_name, btn in popup.resource_buttons.items():
                    if level_name == 'auto':
                        btn.config(style='Action.TButton')
                    else:
                        btn.config(style='Select.TButton')

                # Update indicators (both legacy and new)
                popup.resource_indicator.config(text=indicator_text)

                # Update comprehensive status indicators
                if setting_key == 'llama_server_gpu_layers':
                    if hasattr(popup, 'gpu_layers_indicator'):
                        popup.gpu_layers_indicator.config(text=f"GPU Layers: {auto_value}")
                elif setting_key == 'cpu_threads':
                    if hasattr(popup, 'cpu_threads_indicator'):
                        popup.cpu_threads_indicator.config(text=f"CPU Threads: {auto_value}")

                log_message(f"CUSTOM_CODE_TAB: Resource AUTO set successfully")

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error in AUTO resource selection: {e}")

    def _set_hardware_mode_from_popup(self, mode: str, popup, model_data: dict):
        """
        Set hardware usage mode from popup.

        Modes:
        - 'gpu': GPU layers only, CPU threads = 0 (GPU-only mode)
        - 'cpu': CPU threads only, GPU layers = 0 (CPU-only mode)
        - 'hybrid': Both GPU layers + CPU threads active (maximum performance)
        - 'auto': Let current mode decide (delegates to router logic)
        """
        try:
            log_message(f"CUSTOM_CODE_TAB: Setting hardware mode to {mode}")

            if not hasattr(self, 'chat_interface') or not self.chat_interface:
                log_message(f"CUSTOM_CODE_TAB: No chat_interface available")
                return

            # Get hardware capabilities
            from .capabilities import detect_capabilities
            caps = detect_capabilities()
            gpus = caps.get('gpus', [])
            has_gpu = len(gpus) > 0
            vram_free_gb = (gpus[0].get('vram_free_mb', 0) / 1024) if gpus else 0
            cpu_count = caps.get('cpu', {}).get('cores', 8)

            # Get current mode for Auto
            import json
            current_mode = 'standard'
            mode_settings_path = Path(__file__).parent / 'mode_settings.json'
            if mode_settings_path.exists():
                try:
                    with open(mode_settings_path, 'r') as f:
                        mode_data = json.load(f)
                        current_mode = mode_data.get('current_mode', 'standard').lower()
                except:
                    pass

            # Apply hardware mode
            if mode == 'gpu':
                # GPU-only mode
                if has_gpu:
                    if vram_free_gb >= 6:
                        n_gpu_layers = 35
                    elif vram_free_gb >= 4:
                        n_gpu_layers = 30
                    else:
                        n_gpu_layers = 20
                else:
                    n_gpu_layers = 0  # No GPU available

                cpu_threads = 0  # Disable CPU threads
                hw_mode_display = "GPU"

                self.chat_interface.backend_settings['llama_server_gpu_layers'] = n_gpu_layers
                self.chat_interface.backend_settings['cpu_threads'] = cpu_threads
                self.chat_interface._save_backend_setting('llama_server_gpu_layers', n_gpu_layers)
                self.chat_interface._save_backend_setting('cpu_threads', cpu_threads)

            elif mode == 'cpu':
                # CPU-only mode
                n_gpu_layers = 0  # Disable GPU
                cpu_threads = max(cpu_count // 2, 4)  # Use half CPU cores
                hw_mode_display = "CPU"

                self.chat_interface.backend_settings['llama_server_gpu_layers'] = n_gpu_layers
                self.chat_interface.backend_settings['cpu_threads'] = cpu_threads
                self.chat_interface._save_backend_setting('llama_server_gpu_layers', n_gpu_layers)
                self.chat_interface._save_backend_setting('cpu_threads', cpu_threads)

            elif mode == 'hybrid':
                # Hybrid mode: both GPU and CPU
                if has_gpu:
                    if vram_free_gb >= 6:
                        n_gpu_layers = 35
                    elif vram_free_gb >= 4:
                        n_gpu_layers = 30
                    else:
                        n_gpu_layers = 20
                else:
                    n_gpu_layers = 0

                cpu_threads = max(cpu_count // 2, 4)  # Use half CPU cores
                hw_mode_display = "GPU & CPU"

                self.chat_interface.backend_settings['llama_server_gpu_layers'] = n_gpu_layers
                self.chat_interface.backend_settings['cpu_threads'] = cpu_threads
                self.chat_interface._save_backend_setting('llama_server_gpu_layers', n_gpu_layers)
                self.chat_interface._save_backend_setting('cpu_threads', cpu_threads)

            elif mode == 'auto':
                # Auto mode: Use BOTH GPU + CPU when available (hybrid mode)
                # User requirement: "should if available set both" in Standard mode

                if current_mode == 'fast':
                    # Fast mode: minimal resources
                    n_gpu_layers = 10 if has_gpu else 0
                    cpu_threads = max(cpu_count // 4, 2)

                elif current_mode == 'smart':
                    # Smart mode: VRAM-aware, prefer GPU-only for efficiency
                    if has_gpu and vram_free_gb >= 4:
                        n_gpu_layers = 35
                        cpu_threads = 0  # GPU-only for efficiency
                    elif has_gpu:
                        n_gpu_layers = 20
                        cpu_threads = 0
                    else:
                        n_gpu_layers = 0
                        cpu_threads = max(cpu_count // 2, 4)

                elif current_mode == 'think':
                    # Think mode: maximum performance, use both if available
                    n_gpu_layers = 35 if has_gpu else 0
                    cpu_threads = cpu_count if not has_gpu else max(cpu_count // 2, 4)

                else:  # standard
                    # Standard mode: HYBRID - use BOTH GPU + CPU when available
                    # User requirement: "set both gpu/cpu if available"
                    if has_gpu:
                        # VRAM-scaled GPU allocation
                        if vram_free_gb >= 6:
                            n_gpu_layers = 25
                        elif vram_free_gb >= 4:
                            n_gpu_layers = 20
                        else:
                            n_gpu_layers = 15
                        # Also use half CPU cores for parallel processing
                        cpu_threads = max(cpu_count // 2, 4)
                    else:
                        # No GPU: CPU-only
                        n_gpu_layers = 0
                        cpu_threads = max(cpu_count // 2, 4)

                hw_mode_display = "Auto"

                self.chat_interface.backend_settings['llama_server_gpu_layers'] = n_gpu_layers
                self.chat_interface.backend_settings['cpu_threads'] = cpu_threads
                self.chat_interface._save_backend_setting('llama_server_gpu_layers', n_gpu_layers)
                self.chat_interface._save_backend_setting('cpu_threads', cpu_threads)

            # Update button styles
            for hw_mode_name, btn in popup.hardware_control_buttons.items():
                if hw_mode_name == mode:
                    btn.config(style='Action.TButton')
                else:
                    btn.config(style='Select.TButton')

            # Update hardware mode indicator (button section)
            popup.hw_mode_indicator.config(text=f"Hardware Mode: {hw_mode_display}")

            # Update comprehensive status indicators
            if hasattr(popup, 'hw_status_indicator'):
                popup.hw_status_indicator.config(text=f"Hardware: {hw_mode_display}")
            if hasattr(popup, 'gpu_layers_indicator'):
                popup.gpu_layers_indicator.config(text=f"GPU Layers: {n_gpu_layers}")
            if hasattr(popup, 'cpu_threads_indicator'):
                popup.cpu_threads_indicator.config(text=f"CPU Threads: {cpu_threads}")

            log_message(f"CUSTOM_CODE_TAB: Hardware mode set to {mode}: GPU={n_gpu_layers}, CPU={cpu_threads}")

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error setting hardware mode: {e}")

    def _refresh_hardware_status(self, popup):
        """Refresh hardware detection and update display"""
        try:
            from .capabilities import detect_capabilities
            caps = detect_capabilities(force_refresh=True)  # Force fresh detection

            # Update GPU
            gpus = caps.get('gpus', [])
            if gpus:
                gpu = gpus[0]
                vram_free_mb = gpu.get('vram_free_mb', 0)
                vram_total_mb = gpu.get('vram_total_mb', 0)
                vram_text = f"{gpu.get('name', 'Unknown')} - {vram_free_mb/1024:.1f}GB free / {vram_total_mb/1024:.1f}GB total"
            else:
                vram_text = "No GPU detected"
            popup.hw_gpu_label.config(text=f"GPU: {vram_text}")

            # Update CPU
            cpu_info = caps.get('cpu', {})
            cpu_count = cpu_info.get('cores', 0)
            cpu_model = cpu_info.get('model', 'Unknown CPU')
            if len(cpu_model) > 50:
                cpu_model = cpu_model[:47] + "..."
            popup.hw_cpu_label.config(text=f"CPU: {cpu_count} cores - {cpu_model}")

            # Update RAM
            ram = caps.get('ram', {})
            popup.hw_ram_label.config(text=f"RAM: {ram.get('available_gb', 0):.1f}GB free / {ram.get('total_gb', 0):.1f}GB total")

            log_message("CUSTOM_CODE_TAB: Hardware status refreshed")
        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error refreshing hardware status: {e}")

    def _load_popup_settings(self) -> dict:
        """Load popup window position/size settings from file"""
        import json
        settings_file = Path(__file__).parent / 'popup_settings.json'

        if settings_file.exists():
            try:
                with open(settings_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                log_message(f"CUSTOM_CODE_TAB: Error loading popup settings: {e}")

        return {}

    def _save_popup_settings(self, popup):
        """Save popup window position/size to file"""
        import json
        settings_file = Path(__file__).parent / 'popup_settings.json'

        try:
            # Get current geometry
            geometry = popup.geometry()
            is_locked = popup.is_locked

            settings = {
                'geometry': geometry,
                'locked': is_locked
            }

            with open(settings_file, 'w') as f:
                json.dump(settings, f, indent=2)

            log_message(f"CUSTOM_CODE_TAB: Popup settings saved - geometry: {geometry}, locked: {is_locked}")
        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error saving popup settings: {e}")

    def _toggle_popup_lock(self, popup, lock_btn):
        """Toggle popup lock state and save settings"""
        try:
            # Toggle lock state
            popup.is_locked = not popup.is_locked

            # Update button icon
            lock_icon = "🔒" if popup.is_locked else "🔓"
            lock_btn.config(text=lock_icon)

            # Save current position/size immediately when locking
            if popup.is_locked:
                self._save_popup_settings(popup)
                log_message("CUSTOM_CODE_TAB: Popup locked - position/size saved")
            else:
                log_message("CUSTOM_CODE_TAB: Popup unlocked - position/size will not be saved on close")

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error toggling popup lock: {e}")

    def _close_popup_with_save(self, popup):
        """Close popup window, saving position/size if locked"""
        try:
            # Save settings if locked
            if hasattr(popup, 'is_locked') and popup.is_locked:
                self._save_popup_settings(popup)

            # Close popup
            popup.destroy()
        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error closing popup: {e}")
            popup.destroy()  # Ensure it closes even if save fails

    def get_chat_interface_scores(self):
        """Get the real-time evaluation scores from the chat interface"""
        if hasattr(self, 'chat_interface') and self.chat_interface:
            return self.chat_interface.get_realtime_eval_scores()
        return {}

    def set_training_mode(self, enabled):
        """Set the training mode for the chat interface"""
        if hasattr(self, 'chat_interface') and self.chat_interface:
            self.chat_interface.set_training_mode(enabled)

    def set_training_support(self, enabled: bool):
        """Enable/disable Training Support (auto pipeline + extractive verification)."""
        try:
            if not hasattr(self, '_backend_settings'):
                self._backend_settings = {}
            self._backend_settings['training_support_enabled'] = bool(enabled)
        except Exception:
            pass
        try:
            if hasattr(self, 'chat_interface') and self.chat_interface:
                self.chat_interface.backend_settings['training_support_enabled'] = bool(enabled)
                # Unconditionally reflect explicit Advanced flags to match Support state
                try:
                    adv_path = Path(__file__).parent / 'advanced_settings.json'
                    import json as _json
                    adv = {}
                    if adv_path.exists():
                        with open(adv_path, 'r') as f:
                            adv = _json.load(f) or {}
                    adv.setdefault('verification', {})['enabled'] = bool(enabled)
                    adv.setdefault('quality_assurance', {})['enabled'] = bool(enabled)
                    with open(adv_path, 'w') as f:
                        _json.dump(adv, f, indent=2)
                except Exception:
                    pass
                # Emit Support-changed event for Settings/Advanced consumers
                try:
                    import json as _json
                    payload = _json.dumps({"enabled": bool(enabled)})
                    self.root.event_generate("<<TrainingSupportChanged>>", data=payload, when='tail')
                except Exception:
                    pass
                # If Training Mode is already ON, apply/remove runtime guidance immediately
                try:
                    if getattr(self.chat_interface, 'training_mode_enabled', False) and enabled:
                        if 'verification' not in self.chat_interface.advanced_settings:
                            self.chat_interface.advanced_settings['verification'] = {}
                        self.chat_interface.advanced_settings['verification']['post_tool_extractive'] = True
                        self.chat_interface.backend_settings['auto_start_training_on_runtime_dataset'] = True
                        self.chat_interface.add_message('system', '🔧 Training Support enabled: extractive verification + auto pipeline (live)')
                    else:
                        self.chat_interface.backend_settings['auto_start_training_on_runtime_dataset'] = False
                        try:
                            if 'verification' in self.chat_interface.advanced_settings:
                                self.chat_interface.advanced_settings['verification']['post_tool_extractive'] = False
                        except Exception:
                            pass
                        if enabled is False:
                            self.chat_interface.add_message('system', '🔧 Training Support disabled: runtime guidance off (Training Mode unchanged)')
                    # Refresh Chat indicators
                    try:
                        self.chat_interface._update_quick_indicators()
                    except Exception:
                        pass
                except Exception:
                    pass
                # Always refresh Advanced header/indicators if present
                try:
                    if hasattr(self, 'settings_interface') and self.settings_interface and hasattr(self.settings_interface, 'advanced_settings_interface'):
                        self.settings_interface.advanced_settings_interface.refresh()
                except Exception:
                    pass
                # Always refresh Advanced header/indicators if present
                try:
                    if hasattr(self, 'settings_interface') and self.settings_interface and hasattr(self.settings_interface, 'advanced_settings_interface'):
                        self.settings_interface.advanced_settings_interface.refresh()
                except Exception:
                    pass
        except Exception:
            pass

    def on_mode_changed(self, mode, params):
        """Handle mode changes from the settings tab"""
        if hasattr(self, 'chat_interface') and self.chat_interface:
            self.chat_interface.set_mode_parameters(mode, params)

    def on_closing(self):
        """Handle application close - save chat history"""
        log_message("CUSTOM_CODE_TAB: Application closing, saving chat history...")

        # Save chat history before closing
        if hasattr(self, 'chat_interface') and self.chat_interface:
            self.chat_interface.save_on_exit()

        # Persist pane lock/width
        try:
            self._backend_settings['right_panel_locked'] = bool(self._right_panel_locked)
            self._backend_settings['right_panel_width'] = int(getattr(self, '_right_panel_width', 340))
            import json
            self._settings_path.write_text(json.dumps(self._backend_settings, indent=2))
        except Exception:
            pass

        # Close the application
        self.root.destroy()

    def _get_performance_metrics(self, model_data: dict) -> dict:
        """Get performance metrics for Overview tab display"""
        metrics = {
            'token_speed': 'N/A',
            'context_limit': 'N/A',
            'memory_usage': 'N/A'
        }

        try:
            # Token Speed - Use modern stats structure: performance.speed
            profile = model_data.get('profile', {})
            stats = profile.get('stats', {})

            log_message(f"CUSTOM_CODE_TAB: _get_performance_metrics - profile exists: {bool(profile)}")
            log_message(f"CUSTOM_CODE_TAB: _get_performance_metrics - stats keys: {list(stats.keys())}")

            # Modern structure: stats.performance.speed.value
            performance = stats.get('performance', {})
            speed_data = performance.get('speed', {})
            speed_value = speed_data.get('value') if isinstance(speed_data, dict) else None

            log_message(f"CUSTOM_CODE_TAB: _get_performance_metrics - speed value: {speed_value}")

            if speed_value is not None and speed_value > 0:
                # Speed metric is normalized 0.0-1.0, display as rating
                metrics['token_speed'] = f"Speed: {speed_value:.2f} ({speed_data.get('grade', 'F')})"
            elif hasattr(self, 'chat_interface') and self.chat_interface:
                # Fallback to live benchmark (only valid for currently active model)
                if hasattr(self.chat_interface, 'performance_benchmark') and self.chat_interface.performance_benchmark:
                    bench = self.chat_interface.performance_benchmark
                    if hasattr(bench, 'get_latest_metrics'):
                        latest = bench.get_latest_metrics()
                        if latest and 'tokens_per_second' in latest:
                            metrics['token_speed'] = f"{latest['tokens_per_second']:.1f} tok/s (live)"

            # Context Limit - Use modern metadata structure
            metadata = profile.get('metadata', {})
            context_length = metadata.get('context_length', metadata.get('context_limit'))

            log_message(f"CUSTOM_CODE_TAB: _get_performance_metrics - context_length: {context_length}")

            if context_length and context_length > 0:
                # Use profile metadata (most accurate)
                metrics['context_limit'] = f"{context_length:,} tokens"
            else:
                # Fallback to base model config
                base_model = model_data.get('base_model', '')
                if base_model:
                    config_path = Path(f"Models/{base_model}/config.json")
                    if config_path.exists():
                        import json
                        config = json.loads(config_path.read_text())
                        max_position = config.get('max_position_embeddings', config.get('n_positions', None))
                        if max_position:
                            metrics['context_limit'] = f"{max_position:,} tokens"

            # Memory Usage - from capabilities
            from .capabilities import detect_capabilities
            caps = detect_capabilities(force_refresh=False)

            # Check if GPU or CPU
            gpus = caps.get('gpus', [])
            if gpus:
                vram_used = gpus[0].get('vram_used_mb', 0)
                vram_total = gpus[0].get('vram_total_mb', 0)
                if vram_total > 0:
                    usage_pct = (vram_used / vram_total) * 100
                    metrics['memory_usage'] = f"{vram_used/1024:.1f}GB / {vram_total/1024:.1f}GB ({usage_pct:.0f}%)"
            else:
                # CPU mode - show RAM
                ram = caps.get('ram', {})
                if 'used_percent' in ram and 'total_gb' in ram:
                    used_gb = (ram['total_gb'] * ram['used_percent']) / 100
                    metrics['memory_usage'] = f"{used_gb:.1f}GB / {ram['total_gb']:.1f}GB RAM ({ram['used_percent']:.0f}%)"

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error getting performance metrics: {e}")

        return metrics

    def _show_train_dialog(self, model_data: dict):
        """Show training configuration dialog with backend/trainer selection"""
        try:
            variant_name = model_data.get('variant_name', 'Unknown')
            log_message(f"CUSTOM_CODE_TAB: Opening training dialog for {variant_name}")

            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Train {variant_name}")
            dialog.configure(bg='#2b2b2b')
            dialog.geometry('500x400')

            # Center dialog
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, style='Category.TFrame')
            main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            # Header
            ttk.Label(
                main_frame,
                text=f"Training Configuration",
                font=("Arial", 14, "bold"),
                style='CategoryPanel.TLabel'
            ).pack(pady=(0, 20))

            ttk.Label(
                main_frame,
                text=f"Model: {variant_name}",
                font=("Arial", 10),
                style='Config.TLabel'
            ).pack(pady=(0, 20))

            # Backend selection
            ttk.Label(
                main_frame,
                text="Training Backend:",
                font=("Arial", 11, "bold"),
                style='Config.TLabel'
            ).pack(anchor=tk.W, pady=(10, 5))

            backend_var = tk.StringVar(value='auto')
            backend_frame = ttk.Frame(main_frame, style='Category.TFrame')
            backend_frame.pack(fill=tk.X, pady=5)

            ttk.Radiobutton(
                backend_frame,
                text="🔧 AUTO (System decides based on available hardware)",
                variable=backend_var,
                value='auto',
                style='Category.TRadiobutton'
            ).pack(anchor=tk.W, pady=2)

            ttk.Radiobutton(
                backend_frame,
                text="🖥️  GPU Training (Requires CUDA/ROCm)",
                variable=backend_var,
                value='gpu',
                style='Category.TRadiobutton'
            ).pack(anchor=tk.W, pady=2)

            ttk.Radiobutton(
                backend_frame,
                text="💻 CPU Training (Slower, always available)",
                variable=backend_var,
                value='cpu',
                style='Category.TRadiobutton'
            ).pack(anchor=tk.W, pady=2)

            # Trainer selection
            ttk.Label(
                main_frame,
                text="Trainer:",
                font=("Arial", 11, "bold"),
                style='Config.TLabel'
            ).pack(anchor=tk.W, pady=(20, 5))

            trainer_var = tk.StringVar(value='unsloth')
            trainer_frame = ttk.Frame(main_frame, style='Category.TFrame')
            trainer_frame.pack(fill=tk.X, pady=5)

            ttk.Radiobutton(
                trainer_frame,
                text="⚡ Unsloth (Recommended - 2x faster, lower memory)",
                variable=trainer_var,
                value='unsloth',
                style='Category.TRadiobutton'
            ).pack(anchor=tk.W, pady=2)

            ttk.Radiobutton(
                trainer_frame,
                text="🔥 Standard PyTorch (Fallback)",
                variable=trainer_var,
                value='pytorch',
                style='Category.TRadiobutton'
            ).pack(anchor=tk.W, pady=2)

            # Action buttons
            button_frame = ttk.Frame(main_frame, style='Category.TFrame')
            button_frame.pack(side=tk.BOTTOM, pady=(20, 0))

            def start_training():
                backend = backend_var.get()
                trainer = trainer_var.get()
                log_message(f"CUSTOM_CODE_TAB: Starting training - backend={backend}, trainer={trainer}")
                dialog.destroy()
                self._start_training(model_data, backend, trainer)

            ttk.Button(
                button_frame,
                text="Start Training",
                command=start_training,
                style='Action.TButton',
                width=15
            ).pack(side=tk.LEFT, padx=5)

            ttk.Button(
                button_frame,
                text="Cancel",
                command=dialog.destroy,
                style='Select.TButton',
                width=15
            ).pack(side=tk.LEFT, padx=5)

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error in _show_train_dialog: {e}")

    def _show_eval_dialog(self, model_data: dict):
        """Show evaluation configuration dialog with test suite selection"""
        try:
            variant_name = model_data.get('variant_name', 'Unknown')
            log_message(f"CUSTOM_CODE_TAB: Opening eval dialog for {variant_name}")

            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Evaluate {variant_name}")
            dialog.configure(bg='#2b2b2b')
            dialog.geometry('450x350')

            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, style='Category.TFrame')
            main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            # Header
            ttk.Label(
                main_frame,
                text=f"Evaluation Configuration",
                font=("Arial", 14, "bold"),
                style='CategoryPanel.TLabel'
            ).pack(pady=(0, 20))

            ttk.Label(
                main_frame,
                text=f"Model: {variant_name}",
                font=("Arial", 10),
                style='Config.TLabel'
            ).pack(pady=(0, 20))

            # Test suite selection
            ttk.Label(
                main_frame,
                text="Select Test Suite:",
                font=("Arial", 11, "bold"),
                style='Config.TLabel'
            ).pack(anchor=tk.W, pady=(10, 5))

            suite_var = tk.StringVar(value='all')
            suite_frame = ttk.Frame(main_frame, style='Category.TFrame')
            suite_frame.pack(fill=tk.X, pady=5)

            ttk.Radiobutton(
                suite_frame,
                text="🎯 All Suites (Comprehensive evaluation)",
                variable=suite_var,
                value='all',
                style='Category.TRadiobutton'
            ).pack(anchor=tk.W, pady=2)

            ttk.Radiobutton(
                suite_frame,
                text="⚡ Quick Smoke Test (Fast validation)",
                variable=suite_var,
                value='smoke',
                style='Category.TRadiobutton'
            ).pack(anchor=tk.W, pady=2)

            ttk.Radiobutton(
                suite_frame,
                text="🔍 Regression Test (Verify no skill loss)",
                variable=suite_var,
                value='regression',
                style='Category.TRadiobutton'
            ).pack(anchor=tk.W, pady=2)

            # Eval type
            ttk.Label(
                main_frame,
                text="Evaluation Type:",
                font=("Arial", 11, "bold"),
                style='Config.TLabel'
            ).pack(anchor=tk.W, pady=(20, 5))

            eval_type_var = tk.StringVar(value='post')
            eval_type_frame = ttk.Frame(main_frame, style='Category.TFrame')
            eval_type_frame.pack(fill=tk.X, pady=5)

            ttk.Radiobutton(
                eval_type_frame,
                text="📊 Post-Training Eval (Current state)",
                variable=eval_type_var,
                value='post',
                style='Category.TRadiobutton'
            ).pack(anchor=tk.W, pady=2)

            ttk.Radiobutton(
                eval_type_frame,
                text="📝 Baseline Eval (Reference for comparison)",
                variable=eval_type_var,
                value='baseline',
                style='Category.TRadiobutton'
            ).pack(anchor=tk.W, pady=2)

            # Action buttons
            button_frame = ttk.Frame(main_frame, style='Category.TFrame')
            button_frame.pack(side=tk.BOTTOM, pady=(20, 0))

            def start_eval():
                suite = suite_var.get()
                eval_type = eval_type_var.get()
                log_message(f"CUSTOM_CODE_TAB: Starting eval - suite={suite}, type={eval_type}")
                dialog.destroy()
                self._start_evaluation(model_data, suite, eval_type)

            ttk.Button(
                button_frame,
                text="Run Evaluation",
                command=start_eval,
                style='Action.TButton',
                width=15
            ).pack(side=tk.LEFT, padx=5)

            ttk.Button(
                button_frame,
                text="Cancel",
                command=dialog.destroy,
                style='Select.TButton',
                width=15
            ).pack(side=tk.LEFT, padx=5)

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error in _show_eval_dialog: {e}")

    def _show_training_session_dialog(self, model_data: dict):
        """
        Show training session dialog and switch to Training tab (Phase 4)

        Args:
            model_data: Model/variant data including variant_id/variant_name
        """
        try:
            variant_id = model_data.get('variant_id') or model_data.get('trainee_name') or model_data.get('variant_name', 'Unknown')
            log_message(f"CUSTOM_CODE_TAB: Opening training session for {variant_id}")

            # Create simple dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Start Training Session - {variant_id}")
            dialog.configure(bg='#2b2b2b')
            dialog.geometry('450x300')

            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, style='Category.TFrame')
            main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            # Header
            ttk.Label(
                main_frame,
                text=f"Training Session",
                font=("Arial", 14, "bold"),
                style='CategoryPanel.TLabel'
            ).pack(pady=(0, 10))

            ttk.Label(
                main_frame,
                text=f"Variant: {variant_id}",
                font=("Arial", 11),
                style='Config.TLabel'
            ).pack(pady=(0, 20))

            # Info text
            info_text = (
                "This will switch to the Training tab and pre-select\n"
                "this variant for training.\n\n"
                "You'll be able to configure training parameters\n"
                "and start the training session from there."
            )
            ttk.Label(
                main_frame,
                text=info_text,
                font=("Arial", 10),
                style='Config.TLabel',
                justify=tk.CENTER
            ).pack(pady=20)

            # Button frame
            button_frame = ttk.Frame(main_frame, style='Category.TFrame')
            button_frame.pack(pady=(20, 0))

            def _start_session():
                """Switch to training tab and pre-select variant"""
                try:
                    dialog.destroy()

                    # Generate event for training tab to handle
                    # The training tab should bind to this event and pre-select the variant
                    self.root.event_generate(
                        "<<SelectVariantForTraining>>",
                        data=json.dumps({'variant_id': variant_id}),
                        when="tail"
                    )

                    log_message(f"CUSTOM_CODE_TAB: Generated SelectVariantForTraining event for {variant_id}")

                except Exception as e:
                    log_message(f"CUSTOM_CODE_TAB: Error starting training session: {e}")

            ttk.Button(
                button_frame,
                text="Open Training Tab",
                style='Action.TButton',
                command=_start_session,
                width=18
            ).pack(side=tk.LEFT, padx=5)

            ttk.Button(
                button_frame,
                text="Cancel",
                style='Select.TButton',
                command=dialog.destroy,
                width=12
            ).pack(side=tk.LEFT, padx=5)

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error in _show_training_session_dialog: {e}")

    def flash_levelup_button(self, variant_id: str):
        """
        Flash Level-Up button to indicate promotion readiness (Phase 2B)

        Args:
            variant_id: Variant identifier
        """
        try:
            if not hasattr(self, '_levelup_buttons'):
                return

            button = self._levelup_buttons.get(variant_id)
            if not button or not button.winfo_exists():
                return

            # Start flash animation
            if not hasattr(self, '_flashing_buttons'):
                self._flashing_buttons = {}

            if variant_id in self._flashing_buttons:
                # Already flashing
                return

            self._flashing_buttons[variant_id] = {
                'button': button,
                'original_style': 'Action.TButton',
                'flash_count': 0,
                'flash_state': False
            }

            self._animate_flash(variant_id)

            log_message(f"CUSTOM_CODE_TAB: Started Level-Up button flash for {variant_id}")

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Failed to flash Level-Up button: {e}")

    def _animate_flash(self, variant_id: str):
        """Animate button flashing"""
        try:
            if not hasattr(self, '_flashing_buttons'):
                return

            flash_data = self._flashing_buttons.get(variant_id)
            if not flash_data:
                return

            button = flash_data['button']
            if not button.winfo_exists():
                # Button destroyed, stop flashing
                del self._flashing_buttons[variant_id]
                return

            # Toggle flash state
            flash_data['flash_state'] = not flash_data['flash_state']
            flash_data['flash_count'] += 1

            # Alternate between highlight and normal
            if flash_data['flash_state']:
                button.configure(style='Highlight.TButton')  # Bright style
            else:
                button.configure(style='Action.TButton')  # Normal style

            # Continue flashing (pulse indefinitely until user clicks or variant changes)
            if flash_data['flash_count'] < 100:  # Limit to prevent infinite loop bugs
                self.root.after(500, lambda: self._animate_flash(variant_id))
            else:
                # Reset after 100 flashes (50 seconds)
                button.configure(style='Action.TButton')
                del self._flashing_buttons[variant_id]

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Flash animation error: {e}")

    def stop_levelup_flash(self, variant_id: str):
        """Stop flashing Level-Up button"""
        try:
            if hasattr(self, '_flashing_buttons') and variant_id in self._flashing_buttons:
                flash_data = self._flashing_buttons[variant_id]
                button = flash_data['button']
                if button.winfo_exists():
                    button.configure(style='Action.TButton')
                del self._flashing_buttons[variant_id]
        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Failed to stop flash: {e}")

    def _show_levelup_dialog(self, model_data: dict):
        """Show level-up confirmation dialog with requirements check"""
        try:
            variant_name = model_data.get('variant_name', 'Unknown')
            bundle_metadata = model_data.get('bundle_metadata', {})
            current_level = bundle_metadata.get('class_level', 'novice')

            log_message(f"CUSTOM_CODE_TAB: Opening level-up dialog for {variant_name}")

            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Level Up {variant_name}")
            dialog.configure(bg='#2b2b2b')
            dialog.geometry('400x300')

            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, style='Category.TFrame')
            main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            # Header
            ttk.Label(
                main_frame,
                text=f"Level-Up Confirmation",
                font=("Arial", 14, "bold"),
                style='CategoryPanel.TLabel'
            ).pack(pady=(0, 20))

            # Current state
            ttk.Label(
                main_frame,
                text=f"Model: {variant_name}",
                font=("Arial", 10),
                style='Config.TLabel'
            ).pack(pady=5)

            ttk.Label(
                main_frame,
                text=f"Current Level: {current_level.capitalize()}",
                font=("Arial", 10),
                style='Config.TLabel'
            ).pack(pady=5)

            # Next level
            level_map = {'novice': 'adept', 'adept': 'expert', 'expert': 'master', 'master': 'master'}
            next_level = level_map.get(current_level, 'adept')

            if current_level == 'master':
                ttk.Label(
                    main_frame,
                    text="✨ Already at maximum level!",
                    font=("Arial", 11, "bold"),
                    foreground="#ffd700",
                    style='CategoryPanel.TLabel'
                ).pack(pady=20)

                ttk.Button(
                    main_frame,
                    text="Close",
                    command=dialog.destroy,
                    style='Select.TButton',
                    width=15
                ).pack(pady=20)
            else:
                ttk.Label(
                    main_frame,
                    text=f"Next Level: {next_level.capitalize()}",
                    font=("Arial", 11, "bold"),
                    foreground="#61dafb",
                    style='CategoryPanel.TLabel'
                ).pack(pady=10)

                # Requirements (placeholder - will check skills/XP in full implementation)
                ttk.Label(
                    main_frame,
                    text="Requirements:",
                    font=("Arial", 10, "bold"),
                    style='Config.TLabel'
                ).pack(anchor=tk.W, pady=(20, 5))

                ttk.Label(
                    main_frame,
                    text="• Minimum verified skills: TBD\n• Training evaluations: TBD\n• No regressions detected",
                    justify=tk.LEFT,
                    style='Config.TLabel',
                    font=("Arial", 9)
                ).pack(anchor=tk.W, padx=10)

                # Action buttons
                button_frame = ttk.Frame(main_frame, style='Category.TFrame')
                button_frame.pack(side=tk.BOTTOM, pady=(20, 0))

                def confirm_levelup():
                    log_message(f"CUSTOM_CODE_TAB: Level-up confirmed for {variant_name}")
                    dialog.destroy()
                    self._perform_levelup(model_data, next_level)

                ttk.Button(
                    button_frame,
                    text="Level Up",
                    command=confirm_levelup,
                    style='Action.TButton',
                    width=12
                ).pack(side=tk.LEFT, padx=5)

                ttk.Button(
                    button_frame,
                    text="Cancel",
                    command=dialog.destroy,
                    style='Select.TButton',
                    width=12
                ).pack(side=tk.LEFT, padx=5)

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error in _show_levelup_dialog: {e}")

    def _start_training(self, model_data: dict, backend: str, trainer: str):
        """Start training workflow with selected configuration"""
        try:
            variant_name = model_data.get('variant_name', 'Unknown')
            log_message(f"CUSTOM_CODE_TAB: Starting training for {variant_name} (backend={backend}, trainer={trainer})")

            # Get training tab reference
            try:
                # Find training tab in main notebook
                main_notebook = None
                for widget in self.root.winfo_children():
                    if isinstance(widget, ttk.Notebook):
                        main_notebook = widget
                        break

                if not main_notebook:
                    messagebox.showerror("Error", "Could not find main notebook")
                    return

                # Find training tab
                training_tab = None
                for tab_id in main_notebook.tabs():
                    tab_text = main_notebook.tab(tab_id, "text")
                    if "Training" in tab_text or "⚙️" in tab_text:
                        # Get the actual tab widget
                        tab_widget = main_notebook.nametowidget(tab_id)
                        # The TrainingTab instance should be in the widget's children
                        for child in tab_widget.winfo_children():
                            if hasattr(child, 'apply_plan'):
                                training_tab = child
                                break
                        break

                if not training_tab:
                    messagebox.showerror("Error", "Could not find Training tab")
                    return

                # Apply training plan for this variant
                training_tab.apply_plan(variant_id=variant_name)

                # Switch to training tab
                main_notebook.select(tab_id)

                # Focus runner sub-tab
                if hasattr(training_tab, 'training_notebook'):
                    training_tab.training_notebook.select(0)  # Runner is tab 0

                messagebox.showinfo(
                    "Training Started",
                    f"Training configuration loaded for {variant_name}.\n\nBackend: {backend}\nTrainer: {trainer}\n\nClick 'Start Training' in the Training tab to begin."
                )

            except Exception as e:
                log_message(f"CUSTOM_CODE_TAB: Error navigating to training tab: {e}")
                messagebox.showerror("Error", f"Failed to open Training tab: {e}")

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error in _start_training: {e}")
            messagebox.showerror("Error", f"Training setup failed: {e}")

    def _start_evaluation(self, model_data: dict, suite: str, eval_type: str):
        """Start evaluation workflow with selected test suite"""
        try:
            variant_name = model_data.get('variant_name', 'Unknown')
            log_message(f"CUSTOM_CODE_TAB: Starting eval for {variant_name} (suite={suite}, type={eval_type})")

            messagebox.showinfo(
                "Evaluation",
                f"Evaluation workflow will be implemented in next phase.\n\nModel: {variant_name}\nSuite: {suite}\nType: {eval_type}"
            )

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error in _start_evaluation: {e}")

    def _show_test_skills_dialog(self, model_data: dict):
        """Show Test-Skills validation dialog with tool checks"""
        try:
            variant_name = model_data.get('variant_name', 'Unknown')
            bundle_metadata = model_data.get('bundle_metadata', {})
            model_type = bundle_metadata.get('assigned_type', 'unknown')
            class_level = bundle_metadata.get('class_level', 'novice')

            log_message(f"CUSTOM_CODE_TAB: Opening Test-Skills dialog for {variant_name} (type={model_type})")

            # Load type catalog
            type_catalog_path = Path(__file__).parent.parent.parent / "type_catalog_v2.json"
            type_def = None
            if type_catalog_path.exists():
                import json
                catalog = json.loads(type_catalog_path.read_text())
                for t in catalog.get('types', []):
                    if t['id'] == model_type:
                        type_def = t
                        break

            if not type_def:
                messagebox.showwarning("Test-Skills", f"No tool requirements defined for type '{model_type}'")
                return

            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Test-Skills: {variant_name}")
            dialog.configure(bg='#2b2b2b')
            dialog.geometry('600x500')

            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, style='Category.TFrame')
            main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            # Header
            ttk.Label(
                main_frame,
                text=f"Tool Validation: {model_type.capitalize()}",
                font=("Arial", 14, "bold"),
                style='CategoryPanel.TLabel'
            ).pack(pady=(0, 10))

            ttk.Label(
                main_frame,
                text=f"Model: {variant_name} ({class_level.capitalize()})",
                font=("Arial", 10),
                style='Config.TLabel'
            ).pack(pady=(0, 20))

            # Get enabled tools from Tools tab
            enabled_tools = self._get_enabled_tools()

            # Check required tools
            required_tools = type_def.get('required_tools', [])
            recommended_tools = type_def.get('recommended_tools', [])
            critical_tools = type_def.get('critical_tools', [])

            # Scrollable results area
            results_canvas = tk.Canvas(main_frame, bg="#2b2b2b", highlightthickness=0, height=300)
            results_scroll = ttk.Scrollbar(main_frame, orient="vertical", command=results_canvas.yview)
            results_content = ttk.Frame(results_canvas, style='Category.TFrame')

            results_content.bind(
                "<Configure>",
                lambda e: results_canvas.configure(scrollregion=results_canvas.bbox("all"))
            )

            results_canvas.create_window((0, 0), window=results_content, anchor="nw")
            results_canvas.configure(yscrollcommand=results_scroll.set)

            results_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            results_scroll.pack(side=tk.RIGHT, fill=tk.Y)

            # Display tool status
            all_passed = True

            ttk.Label(
                results_content,
                text="Required Tools:",
                font=("Arial", 11, "bold"),
                style='Config.TLabel'
            ).pack(anchor=tk.W, pady=(5, 10))

            for tool in required_tools:
                tool_row = ttk.Frame(results_content, style='Category.TFrame')
                tool_row.pack(fill=tk.X, padx=10, pady=3)

                # Check if enabled
                is_enabled = tool in enabled_tools and enabled_tools[tool]

                # Test actual execution (Phase 1.6D fix)
                exec_test = self._test_tool_execution(tool)

                # Determine status based on both enabled state and execution test
                if is_enabled and exec_test['available'] and exec_test['executable']:
                    icon = "✅"
                    color = "#00ff00"
                    status = "Ready"
                elif is_enabled and exec_test['available']:
                    icon = "⚠️"
                    color = "#ffaa00"
                    status = "Available (not tested)"
                    all_passed = False
                elif is_enabled and not exec_test['available']:
                    icon = "❌"
                    color = "#ff6b6b"
                    status = f"MISSING ({exec_test['error'] or 'Not in executor'})"
                    all_passed = False
                else:
                    icon = "❌"
                    color = "#ff6b6b"
                    status = "DISABLED"
                    all_passed = False

                ttk.Label(
                    tool_row,
                    text=f"{icon} {tool}",
                    font=("Arial", 10),
                    foreground=color,
                    style='CategoryPanel.TLabel'
                ).pack(side=tk.LEFT)

                ttk.Label(
                    tool_row,
                    text=status,
                    font=("Arial", 9),
                    foreground="#888888",
                    style='Config.TLabel'
                ).pack(side=tk.RIGHT)

            if recommended_tools:
                ttk.Label(
                    results_content,
                    text="Recommended Tools:",
                    font=("Arial", 11, "bold"),
                    style='Config.TLabel'
                ).pack(anchor=tk.W, pady=(15, 10))

                for tool in recommended_tools:
                    tool_row = ttk.Frame(results_content, style='Category.TFrame')
                    tool_row.pack(fill=tk.X, padx=10, pady=3)

                    if tool in enabled_tools and enabled_tools[tool]:
                        icon = "✅"
                        color = "#00ff00"
                        status = "Enabled"
                    else:
                        icon = "⚠️"
                        color = "#ffff00"
                        status = "Disabled (optional)"

                    ttk.Label(
                        tool_row,
                        text=f"{icon} {tool}",
                        font=("Arial", 10),
                        foreground=color,
                        style='CategoryPanel.TLabel'
                    ).pack(side=tk.LEFT)

                    ttk.Label(
                        tool_row,
                        text=status,
                        font=("Arial", 9),
                        foreground="#888888",
                        style='Config.TLabel'
                    ).pack(side=tk.RIGHT)

            # Safety warning for novice + critical tools
            if class_level == 'novice' and critical_tools:
                critical_enabled = [t for t in critical_tools if enabled_tools.get(t, False)]
                if critical_enabled:
                    ttk.Label(
                        results_content,
                        text="⚠️ Safety Warning:",
                        font=("Arial", 11, "bold"),
                        foreground="#ff6b6b",
                        style='CategoryPanel.TLabel'
                    ).pack(anchor=tk.W, pady=(15, 10))

                    warning_text = type_def.get('critical_tool_warning', 'Critical tools enabled')
                    ttk.Label(
                        results_content,
                        text=f"This is a NOVICE model with critical tools enabled:\n{', '.join(critical_enabled)}\n\n{warning_text}\n\nRecommendation: Disable until model reaches 'adept' level.",
                        justify=tk.LEFT,
                        wraplength=500,
                        style='Config.TLabel',
                        font=("Arial", 9)
                    ).pack(anchor=tk.W, padx=10)

            # Action buttons
            button_frame = ttk.Frame(main_frame, style='Category.TFrame')
            button_frame.pack(side=tk.BOTTOM, pady=(20, 0))

            def open_tools_settings():
                dialog.destroy()
                # Switch to Settings tab, Tools sub-tab
                messagebox.showinfo("Tools Settings", "Navigate to Settings → Tools tab to enable/disable tools")

            def run_quick_eval():
                dialog.destroy()
                if all_passed:
                    self._run_quick_skill_eval(model_data)
                else:
                    messagebox.showwarning("Validation Failed", "Please enable all required tools before running evaluation")

            if all_passed:
                ttk.Button(
                    button_frame,
                    text="✓ Run Quick Eval",
                    command=run_quick_eval,
                    style='Action.TButton',
                    width=18
                ).pack(side=tk.LEFT, padx=5)
            else:
                ttk.Button(
                    button_frame,
                    text="Enable Tools",
                    command=open_tools_settings,
                    style='Action.TButton',
                    width=18
                ).pack(side=tk.LEFT, padx=5)

            ttk.Button(
                button_frame,
                text="Close",
                command=dialog.destroy,
                style='Select.TButton',
                width=18
            ).pack(side=tk.LEFT, padx=5)

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error in _show_test_skills_dialog: {e}")
            messagebox.showerror("Error", f"Test-Skills dialog failed: {e}")

    def _get_enabled_tools(self) -> dict:
        """Get currently enabled tools from Tools tab"""
        try:
            # Find Tools tab
            if hasattr(self, 'sub_notebook'):
                for tab_id in self.sub_notebook.tabs():
                    tab_text = self.sub_notebook.tab(tab_id, "text")
                    if "Tools" in tab_text or "🔧" in tab_text:
                        tab_widget = self.sub_notebook.nametowidget(tab_id)
                        for child in tab_widget.winfo_children():
                            if hasattr(child, 'get_enabled_tools'):
                                return child.get_enabled_tools()
        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error getting enabled tools: {e}")

        return {}

    def _test_tool_execution(self, tool_name: str) -> dict:
        """
        Test if a tool can actually execute at interface level (Phase 1.6D).

        Args:
            tool_name: Name of tool to test

        Returns:
            Dict with 'available', 'executable', 'error' keys
        """
        result = {
            'available': False,
            'executable': False,
            'error': None
        }

        try:
            # Try to import and instantiate the tool
            from pathlib import Path
            import sys

            # Add tool_executor path
            tool_exec_path = Path(__file__).parent
            if str(tool_exec_path) not in sys.path:
                sys.path.insert(0, str(tool_exec_path))

            # Try to create tool executor and check if tool exists
            from tool_executor import ToolExecutor

            executor = ToolExecutor()

            # Check if tool is in tool_instances
            if tool_name in executor.tool_instances:
                result['available'] = True

                # Try a safe test execution for specific tools
                if tool_name == 'system_info':
                    # Test system_info (safe, no side effects)
                    test_result = executor.execute_tool_sync(tool_name, {})
                    if test_result.get('success'):
                        result['executable'] = True
                    else:
                        result['error'] = test_result.get('error', 'Execution failed')
                elif tool_name in ['get_mouse_position', 'wait']:
                    # Browser tools - just check instantiation
                    result['executable'] = True
                elif tool_name.startswith('browser_') or tool_name in ['element_detect', 'get_pixel_color']:
                    # Browser tools - mark as executable if instantiated
                    result['executable'] = True
                else:
                    # For other tools, assume executable if available
                    result['executable'] = True
            else:
                result['error'] = 'Tool not found in executor'

        except Exception as e:
            result['error'] = str(e)
            log_message(f"CUSTOM_CODE_TAB: Tool test error for {tool_name}: {e}")

        return result

    def _run_quick_skill_eval(self, model_data: dict):
        """Run quick evaluation to test skills and update profile"""
        try:
            variant_name = model_data.get('variant_name', 'Unknown')
            model_type = model_data.get('bundle_metadata', {}).get('assigned_type', 'unknown')

            # Confirm with user
            if not messagebox.askyesno(
                "Quick Evaluation",
                f"Run quick Type-Tools test for {variant_name}?\n\nThis will:\n• Test required/recommended tools for type '{model_type}'\n• Save a tools test report\n\nEstimated time: ~1 minute"
            ):
                return

            # Build tool list from type catalog
            from pathlib import Path
            import json
            type_catalog_path = Path(__file__).parent.parent.parent / "type_catalog_v2.json"
            required: list[str] = []
            recommended: list[str] = []
            if type_catalog_path.exists():
                catalog = json.loads(type_catalog_path.read_text())
                for t in catalog.get('types', []):
                    if t.get('id') == model_type:
                        required = t.get('required_tools', []) or []
                        recommended = t.get('recommended_tools', []) or []
                        break

            tool_list = [t for t in (required + recommended) if t in (getattr(self.tools_interface, 'tool_vars', {}) or {})]
            if not tool_list:
                messagebox.showwarning("Quick Eval", f"No tools found for type '{model_type}'. Check type catalog and Tools tab.")
                return

            # Run via ToolsTestRunner (function-call conformer for safety)
            from tools.tools_test_runner import ToolsTestRunner
            runner = ToolsTestRunner(self.chat_interface)
            report_path = runner.run_and_save(
                tool_list,
                as_json_args=False,
                variant_id=variant_name,
                type_id=model_type,
                scope='type'
            )

            # Summarize
            import json as _json
            data = _json.loads(Path(report_path).read_text())
            total = len(data.get('results', []))
            passed = sum(1 for r in data.get('results', []) if r.get('success'))
            failed = total - passed
            messagebox.showinfo("Quick Eval", f"Type-Tools test complete.\n\nPassed: {passed}\nFailed: {failed}\nSaved: {report_path}")

            log_message(f"CUSTOM_CODE_TAB: Quick Type-Tools test for {variant_name} saved to {report_path}")

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error in _run_quick_skill_eval: {e}")
            messagebox.showerror("Error", f"Quick eval failed: {e}")

    def _get_tools_status_map(self) -> dict:
        """Return {tool_name: enabled_bool} from Tools tab."""
        try:
            if getattr(self, 'tools_interface', None) and hasattr(self.tools_interface, 'tool_vars'):
                return {k: bool(v.get()) for k, v in (self.tools_interface.tool_vars or {}).items()}
        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error building tools status map: {e}")
        return {}

    def _show_class_skill_eval_dialog(self, model_data: dict):
        """Placeholder dialog for future model skill evaluation (not tool tests)."""
        try:
            variant_name = model_data.get('variant_name', 'Unknown')
            messagebox.showinfo(
                "Skills Evaluation",
                f"Class-tab Test-Skills is reserved for model skill evaluation.\n\nModel: {variant_name}\nStatus: Coming soon"
            )
        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error in _show_class_skill_eval_dialog: {e}")

    def _show_test_tools_dialog(self, model_data: dict, preset_scope: str | None = None):
        """Prompt for Type-Tools vs All-Tools and run conformance tests.

        preset_scope: optionally 'type' or 'all' to preselect scope.
        """
        try:
            from pathlib import Path
            import json
            from .sub_tabs.tools_tab import ToolsTab
            from tools.tools_test_runner import ToolsTestRunner

            variant_name = model_data.get('variant_name', 'Unknown')
            bundle_md = model_data.get('bundle_metadata', {})
            model_type = bundle_md.get('assigned_type', 'unknown')
            class_level = bundle_md.get('class_level', 'novice')

            # Load type catalog for required/recommended/critical
            type_catalog_path = Path(__file__).parent.parent.parent / "type_catalog_v2.json"
            type_def = None
            type_required: list[str] = []
            type_recommended: list[str] = []
            type_critical: list[str] = []
            if type_catalog_path.exists():
                catalog = json.loads(type_catalog_path.read_text())
                for t in catalog.get('types', []):
                    if t['id'] == model_type:
                        type_def = t
                        type_required = t.get('required_tools', []) or []
                        type_recommended = t.get('recommended_tools', []) or []
                        type_critical = t.get('critical_tools', []) or []
                        break

            # Dialog
            parent = getattr(self, '_current_model_popup', self.root)
            dlg = tk.Toplevel(parent)
            dlg.title(f"Test Tools: {variant_name}")
            dlg.configure(bg='#2b2b2b')
            dlg.geometry('560x480')
            try:
                dlg.minsize(560, 420)
            except Exception:
                pass
            dlg.transient(parent)
            dlg.grab_set()
            try:
                dlg.lift(); dlg.focus_set(); dlg.attributes('-topmost', True); dlg.after(200, lambda: dlg.attributes('-topmost', False))
            except Exception:
                pass

            frm = ttk.Frame(dlg, style='Category.TFrame')
            frm.pack(fill=tk.BOTH, expand=True, padx=16, pady=14)

            ttk.Label(frm, text=f"Select scope and formats", style='CategoryPanel.TLabel', font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))

            scope_var = tk.StringVar(value=(preset_scope or 'type'))  # 'type' or 'all'
            # Multiple format selection: default test both function + json
            fmt_fn_var = tk.BooleanVar(value=True)
            fmt_json_var = tk.BooleanVar(value=True)
            include_crit = tk.BooleanVar(value=False)
            sel_tools_override = {
                'active': False,
                'tools': []
            }

            # Determine globally critical tools from Tools tab metadata (HIGH/CRITICAL risk)
            critical_registry = set()
            try:
                from .sub_tabs.tools_tab import ToolsTab as _TT
                for section in _TT.AVAILABLE_TOOLS.values():
                    for key, meta in section.items():
                        risk = (meta or {}).get('risk', '').upper()
                        if risk in ('CRITICAL', 'HIGH'):
                            critical_registry.add(key)
            except Exception:
                pass

            scope_row = ttk.Frame(frm, style='Category.TFrame'); scope_row.pack(anchor=tk.W, pady=4, fill=tk.X)
            ttk.Radiobutton(scope_row, text='Type-Tools', variable=scope_var, value='type').pack(side=tk.LEFT)
            ttk.Radiobutton(scope_row, text='All-Tools (enabled)', variable=scope_var, value='all').pack(side=tk.LEFT, padx=(12,8))

            # Formats row placed below scope selections
            fmt_row = ttk.Frame(frm, style='Category.TFrame'); fmt_row.pack(anchor=tk.W, pady=4, fill=tk.X)
            ttk.Checkbutton(fmt_row, text='OpenAI Function Calls', variable=fmt_fn_var).pack(side=tk.LEFT, padx=(0,8))
            ttk.Checkbutton(fmt_row, text='Arguments as JSON string', variable=fmt_json_var).pack(side=tk.LEFT, padx=(0,12))
            test_conformers_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(fmt_row, text='Test all conformers', variable=test_conformers_var).pack(side=tk.LEFT, padx=(0,12))
            interactive_conf_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(fmt_row, text='Interactive confirmations (popups)', variable=interactive_conf_var).pack(side=tk.LEFT)
            # Set Tools button (manual selection)
            def _open_set_tools_dialog():
                try:
                    tools_map = (getattr(self.tools_interface, 'tool_vars', {}) or {})
                    all_tool_names = sorted(list(tools_map.keys()))
                    dlg2 = tk.Toplevel(dlg)
                    dlg2.title("Set Tools")
                    dlg2.configure(bg='#2b2b2b')
                    dlg2.geometry('420x460'); dlg2.transient(dlg); dlg2.grab_set()
                    try:
                        dlg2.lift(); dlg2.focus_set(); dlg2.attributes('-topmost', True); dlg2.after(200, lambda: dlg2.attributes('-topmost', False))
                    except Exception:
                        pass
                    body = ttk.Frame(dlg2, style='Category.TFrame'); body.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                    ttk.Label(body, text="Select tools to test", style='CategoryPanel.TLabel').pack(anchor=tk.W)
                    list_frame = ttk.Frame(body, style='Category.TFrame'); list_frame.pack(fill=tk.BOTH, expand=True, pady=(8,8))
                    canvas = tk.Canvas(list_frame, bg='#2b2b2b', highlightthickness=0)
                    vbar = ttk.Scrollbar(list_frame, orient='vertical', command=canvas.yview)
                    inner = ttk.Frame(canvas, style='Category.TFrame')
                    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
                    canvas.create_window((0,0), window=inner, anchor='nw'); canvas.configure(yscrollcommand=vbar.set)
                    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); vbar.pack(side=tk.RIGHT, fill=tk.Y)
                    chk_vars = {}
                    # Preselect current override or computed selection
                    current = set(sel_tools_override['tools']) if sel_tools_override['active'] else set([k for k,v in tools_map.items() if v.get()])
                    for name in all_tool_names:
                        var = tk.BooleanVar(value=(name in current))
                        chk_vars[name] = var
                        ttk.Checkbutton(inner, text=name, variable=var).pack(anchor=tk.W)
                    btns2 = ttk.Frame(body, style='Category.TFrame'); btns2.pack(fill=tk.X)
                    def _select_all():
                        for v in chk_vars.values(): v.set(True)
                    def _clear_all():
                        for v in chk_vars.values(): v.set(False)
                    ttk.Button(btns2, text='Select All', style='Select.TButton', command=_select_all).pack(side=tk.LEFT)
                    ttk.Button(btns2, text='Clear', style='Select.TButton', command=_clear_all).pack(side=tk.LEFT, padx=(6,0))
                    def _apply_tools():
                        sel = [n for n,v in chk_vars.items() if v.get()]
                        sel_tools_override['active'] = True
                        sel_tools_override['tools'] = sel
                        dlg2.destroy()
                    ttk.Button(btns2, text='Apply', style='Action.TButton', command=_apply_tools).pack(side=tk.RIGHT)
                    ttk.Button(btns2, text='Close', style='Select.TButton', command=dlg2.destroy).pack(side=tk.RIGHT, padx=(6,0))
                except Exception as e:
                    append_status(f"Set Tools dialog error: {e}")
            ttk.Button(scope_row, text='Set Tools', style='Select.TButton', command=_open_set_tools_dialog).pack(side=tk.RIGHT)

            if (class_level.lower() == 'novice' and type_critical) or critical_registry:
                crit_list = list(type_critical or []) or sorted(list(critical_registry))
                ttk.Checkbutton(frm, text=f"Include critical tools ({', '.join(crit_list)})", variable=include_crit).pack(anchor=tk.W, pady=(8,0))

            # Helpers: type→tool key mapping
            def _map_type_tool_names(names: list[str]) -> list[str]:
                if not names:
                    return []
                mapped = []
                mapping = {
                    'read': ['file_read'],
                    'write': ['file_write'],
                    'edit': ['file_edit'],
                    'glob': ['file_search'],
                    'grep': ['grep_search'],
                    'bash': ['bash_execute'],
                    'system': ['system_info'],
                    'dir': ['directory_list'],
                }
                for n in names:
                    k = n.strip().lower()
                    if k in mapping:
                        mapped.extend(mapping[k])
                    else:
                        mapped.append(k)  # assume already a tool key
                return mapped

            # Status area
            status_txt = tk.Text(frm, height=8, bg='#1e1e1e', fg='#cfcfcf', relief='flat')
            status_txt.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

            def append_status(line: str):
                try:
                    status_txt.insert(tk.END, line + "\n"); status_txt.see(tk.END)
                except Exception:
                    pass

            # Store last summary's Not Enabled tools for Enable & Retry
            last_fail_not_enabled: set[str] = set()

            def _compute_tool_selection():
                # Resolve tools selection based on scope, overrides and critical gating
                tools_status = self._get_tools_status_map()
                enabled_list = [k for k, v in tools_status.items() if v]
                if scope_var.get() == 'type':
                    # Map catalog names (read/write/edit/glob/grep/bash) to tool keys
                    base = _map_type_tool_names(list(type_required or []) + list(type_recommended or []))
                    if include_crit.get():
                        base += _map_type_tool_names(list(type_critical or []))
                    base = [t for t in base if t in (self.tools_interface.tool_vars or {})]
                else:
                    base = enabled_list
                    if not include_crit.get():
                        base = [t for t in base if t not in critical_registry]
                if sel_tools_override['active']:
                    base = [t for t in sel_tools_override['tools'] if t in (self.tools_interface.tool_vars or {})]
                return base, tools_status

            def do_run_tests():
                try:
                    sel_tools, tools_status = _compute_tool_selection()

                    if not sel_tools:
                        messagebox.showwarning("Test Tools", "No tools selected to test")
                        return

                    if test_conformers_var.get():
                        formats = [('function', False), ('json', True)]
                    else:
                        formats = []
                        if fmt_fn_var.get():
                            formats.append(('function', False))
                        if fmt_json_var.get():
                            formats.append(('json', True))
                        if not formats:
                            formats = [('function', False), ('json', True)]

                    append_status(f"Testing Tool Formats: {', '.join([f[0] for f in formats])}")
                    append_status(f"Testing Tools: {len(sel_tools)} selected")

                    runner = ToolsTestRunner(self.chat_interface)
                    runner.set_interactive_confirmations(bool(interactive_conf_var.get()), parent=dlg)
                    # Ensure executor readiness and show diagnostic
                    try:
                        runner._ensure_executor_ready()
                        te = getattr(self.chat_interface, 'tool_executor', None)
                        ntools = len(getattr(te, 'tool_instances', {}) or {}) if te else 0
                        append_status(f"Executor: ready with {ntools} tools")
                    except Exception:
                        pass
                    import json as _json
                    all_results: list[dict] = []
                    # Track per-tool per-format outcomes
                    per_tool_formats: dict[str, dict] = {}
                    for label, as_json in formats:
                        # Additional gating for critical tools + JSON conformer
                        if as_json and include_crit.get():
                            if not messagebox.askyesno("Confirm Critical Tests",
                                "You are about to run critical tests with JSON conformer. Proceed?"):
                                continue
                        append_status("")
                        append_status(f"— Running format: {label} —")
                        report_path = runner.run_and_save(
                            sel_tools,
                            as_json_args=as_json,
                            variant_id=variant_name,
                            type_id=model_type,
                            scope=scope_var.get()
                        )
                        data = _json.loads(Path(report_path).read_text())
                        results = data.get('results', [])
                        all_results.extend([dict(r) for r in results])
                        # Chains summary (if present)
                        try:
                            chains = data.get('chains_results') or []
                            if chains:
                                okc = sum(1 for c in chains if c.get('success'))
                                totc = len(chains)
                                append_status(f"Chains: {totc} (✓ {okc} ✗ {totc-okc})")
                                for c in chains:
                                    if c.get('success'):
                                        append_status(f"  ✓ {c.get('name')}")
                                    else:
                                        append_status(f"  ✗ {c.get('name')}: {c.get('reason')}")
                        except Exception:
                            pass
                        # Per-tool result lines
                        for r in results:
                            tname = r.get('tool_name')
                            if tname:
                                fm = per_tool_formats.setdefault(tname, {'function': None, 'json': None})
                                fm['json' if as_json else 'function'] = bool(r.get('success'))
                            if r.get('success'):
                                append_status(f"  ✓ {r.get('tool_name')} [{label}]")
                            else:
                                append_status(f"  ✗ {r.get('tool_name')} [{label}]: {r.get('error')}")
                        passed = sum(1 for r in results if r.get('success'))
                        failed = len(results) - passed
                        append_status(f"Summary [{label}]: ✓ {passed}  ✗ {failed}")
                        append_status(f"📄 Saved report → {report_path}")
                        # Enable the report opener
                        try:
                            def _open_report(path=str(Path(report_path).with_suffix('.txt'))):
                                try:
                                    import os, sys, subprocess
                                    rp = Path(path)
                                    folder = str(rp.parent)
                                    # Open folder
                                    if sys.platform.startswith('win'):
                                        os.startfile(folder)  # type: ignore
                                    elif sys.platform == 'darwin':
                                        subprocess.Popen(['open', folder])
                                    else:
                                        subprocess.Popen(['xdg-open', folder])
                                    # Open file
                                    if sys.platform.startswith('win'):
                                        os.startfile(str(rp))  # type: ignore
                                    elif sys.platform == 'darwin':
                                        subprocess.Popen(['open', str(rp)])
                                    else:
                                        subprocess.Popen(['xdg-open', str(rp)])
                                except Exception as _e:
                                    append_status(f"Open report error: {_e}")
                            btn_report.config(command=_open_report)
                            btn_report.state(["!disabled"])  # enable
                        except Exception:
                            pass

                    # Final summary across formats for selected tools
                    try:
                        # Use the target set (selection) instead of entire registry
                        alias_exclude = {'read_text'}
                        available_all = [t for t in sel_tools if t not in alias_exclude]
                        # Track critical-excluded tools for visibility
                        excluded_crit = []
                        if not include_crit.get():
                            for t in available_all:
                                if t in critical_registry and t not in alias_exclude:
                                    excluded_crit.append(t)
                        # The actually tested set (after critical gating)
                        available = sorted([t for t in available_all if (include_crit.get() or t not in critical_registry)])
                        append_status("")
                        append_status(f"=== Final Summary: {len(available)} Tools Tested ===")
                        # Index results by tool
                        by_tool: dict[str, dict] = {}
                        for r in all_results:
                            name = r.get('tool_name') or ''
                            if not name:
                                continue
                            entry = by_tool.setdefault(name, {'success': False, 'errors': []})
                            if r.get('success'):
                                entry['success'] = True
                            else:
                                if r.get('error'):
                                    entry['errors'].append(str(r.get('error')))
                        # Build success/fail groups
                        success_items: list[str] = []
                        fail_items: list[tuple[str, str]] = []
                        last_fail_not_enabled.clear()
                        for name in available:
                            entry = by_tool.get(name)
                            if entry and entry.get('success'):
                                success_items.append(name)
                            else:
                                # Derive reason
                                if not tools_status.get(name, True):
                                    reason = 'Not Enabled'
                                    last_fail_not_enabled.add(name)
                                else:
                                    errs = (entry or {}).get('errors') or []
                                    reason = errs[0] if errs else 'Not Tested'
                                fail_items.append((name, reason))

                        # Add critical-excluded tools as Fail with reason
                        for name in sorted(excluded_crit):
                            if name not in available:
                                fail_items.append((name, 'Excluded by policy (critical)'))

                        # Print grouped summary with counts
                        append_status(f"Pass: {len(success_items)} tool(s)")
                        for n in success_items:
                            fm = per_tool_formats.get(n, {})
                            f_flag = 'Y' if fm.get('function') is True else ('N' if fm.get('function') is False else '-')
                            j_flag = 'Y' if fm.get('json') is True else ('N' if fm.get('json') is False else '-')
                            append_status(f"  ✓ {n}: Success | Formats: [Function]{f_flag} [JSON]{j_flag}")
                        append_status(f"Fail: {len(fail_items)} tool(s)")
                        for n, reason in fail_items:
                            fm = per_tool_formats.get(n, {})
                            f_flag = 'Y' if fm.get('function') is True else ('N' if fm.get('function') is False else '-')
                            j_flag = 'Y' if fm.get('json') is True else ('N' if fm.get('json') is False else '-')
                            append_status(f"  ✗ {n}: Fail | Reason: {reason} | Formats: [Function]{f_flag} [JSON]{j_flag}")
                        if last_fail_not_enabled:
                            append_status("")
                            append_status(f"Enable & Retry will enable: {', '.join(sorted(last_fail_not_enabled))}")

                        # Also append the same grouped summary to the latest text report for unified output
                        try:
                            last_txt = Path(report_path).with_suffix('.txt') if 'report_path' in locals() else None
                            if last_txt and last_txt.exists():
                                lines = []
                                lines.append("")
                                lines.append(f"=== Final Summary: {len(available)} Tools Tested ===")
                                lines.append(f"Pass: {len(success_items)} tool(s)")
                                for n in success_items:
                                    lines.append(f"  ✓ {n}: Success")
                                lines.append(f"Fail: {len(fail_items)} tool(s)")
                                for n, reason in fail_items:
                                    lines.append(f"  ✗ {n}: Fail | Reason: {reason}")
                                if last_fail_not_enabled:
                                    lines.append("")
                                    lines.append(f"Enable & Retry will enable: {', '.join(sorted(last_fail_not_enabled))}")
                                with open(last_txt, 'a') as f:
                                    f.write("\n".join(lines) + "\n")
                        except Exception:
                            pass
                    except Exception as e:
                        append_status(f"Final summary error: {e}")

                    # Suggestions for disabled required tools (map names to keys)
                    missing_required = []
                    if type_required:
                        req_keys = _map_type_tool_names(type_required)
                        for t in req_keys:
                            if not tools_status.get(t, False):
                                missing_required.append(t)
                    if missing_required:
                        append_status("")
                        append_status(f"Suggestion: Enable required tools: {', '.join(sorted(set(missing_required)))}")
                except Exception as e:
                    append_status(f"Error: {e}")

            def do_enable_and_retry():
                try:
                    tools_status = self._get_tools_status_map()
                    to_enable = []
                    # Prefer enabling from last summary's Not Enabled set; fallback to current selection
                    target_tools = list(last_fail_not_enabled)
                    if not target_tools:
                        target_tools, _ = _compute_tool_selection()
                    # Enable target tools in Tools tab
                    for t in target_tools:
                        if t in (self.tools_interface.tool_vars or {}) and not tools_status.get(t, False):
                            self.tools_interface.tool_vars[t].set(True)
                            to_enable.append(t)
                    if to_enable:
                        # Persist
                        if hasattr(self.tools_interface, 'save_tool_settings'):
                            self.tools_interface.save_tool_settings()
                        append_status(f"Enabled tools: {', '.join(to_enable)}")
                    else:
                        append_status("No additional tools to enable.")
                    # Re-run
                    do_run_tests()
                except Exception as e:
                    append_status(f"Enable/Retry error: {e}")

            # Buttons
            btns = ttk.Frame(frm, style='Category.TFrame'); btns.pack(side=tk.BOTTOM, pady=(10,6), fill=tk.X)
            # Report opener (enabled after first run)
            btn_report = ttk.Button(btns, text="📄", style='Select.TButton', width=3)
            try:
                btn_report.state(["disabled"])  # start disabled
            except Exception:
                pass
            btn_report.pack(side=tk.LEFT, padx=(0,6))

            ttk.Button(btns, text="Run", style='Action.TButton', command=do_run_tests, width=12).pack(side=tk.LEFT)
            ttk.Button(btns, text="Enable & Retry", style='Select.TButton', command=do_enable_and_retry, width=16).pack(side=tk.LEFT, padx=(8,0))
            ttk.Button(btns, text="Close", style='Select.TButton', command=dlg.destroy, width=10).pack(side=tk.RIGHT)

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error in _show_test_tools_dialog: {e}")
            messagebox.showerror("Error", f"Test-Tools dialog failed: {e}")

    def _open_skills_test_launcher(self, model_data: dict):
        """Small launcher with two buttons: [Type-Test] [Test-All]"""
        try:
            parent = getattr(self, '_current_model_popup', self.root)
            dlg = tk.Toplevel(parent)
            dlg.title("Test-Skills")
            dlg.configure(bg='#2b2b2b')
            dlg.geometry('360x160')
            dlg.transient(parent)
            dlg.grab_set()
            try:
                dlg.lift(); dlg.focus_set(); dlg.attributes('-topmost', True); dlg.after(200, lambda: dlg.attributes('-topmost', False))
            except Exception:
                pass

            frm = ttk.Frame(dlg, style='Category.TFrame')
            frm.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            ttk.Label(frm, text="Select Test Scope", style='CategoryPanel.TLabel', font=("Arial", 12, "bold")).pack(pady=(0, 12))

            btns = ttk.Frame(frm, style='Category.TFrame')
            btns.pack(pady=4)

            ttk.Button(btns, text="Type-Test", style='Action.TButton', width=14,
                       command=lambda: (dlg.destroy(), self._show_test_tools_dialog(model_data, preset_scope='type'))).pack(side=tk.LEFT, padx=6)
            ttk.Button(btns, text="Test-All", style='Select.TButton', width=14,
                       command=lambda: (dlg.destroy(), self._show_test_tools_dialog(model_data, preset_scope='all'))).pack(side=tk.LEFT, padx=6)
        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error opening skills test launcher: {e}")

    def _perform_levelup(self, model_data: dict, next_level: str):
        """Perform level-up and sync bundles"""
        try:
            variant_name = model_data.get('variant_name', 'Unknown')
            log_message(f"CUSTOM_CODE_TAB: Performing level-up for {variant_name} to {next_level}")

            # Update model profile
            import config
            profile = config.load_model_profile(variant_name)
            if profile:
                from_class = profile.get('class_level', 'novice')

                # Update class level
                profile['class_level'] = next_level
                config.save_model_profile(variant_name, profile)

                # Phase 2F: Log promotion event to LineageTracker
                try:
                    from tabs.custom_code_tab.lineage_tracker import get_tracker
                    from config import get_xp_value
                    tracker = get_tracker()

                    promotion_details = {
                        'xp': get_xp_value(profile),
                        'eval_score': profile.get('latest_eval_score', 0.0),
                        'tool_proficiency': profile.get('tool_proficiency', {}),
                        'skills': list(profile.get('skills', {}).keys()),
                        'base_model': profile.get('base_model'),
                        'assigned_type': profile.get('assigned_type')
                    }

                    tracker.record_promotion(
                        variant_id=variant_name,
                        from_class=from_class,
                        to_class=next_level,
                        promotion_reason="user_approved",
                        promotion_details=promotion_details
                    )
                except Exception as e:
                    log_message(f"CUSTOM_CODE_TAB: Failed to log promotion to lineage: {e}")

                # Sync bundles
                from registry.bundle_loader import sync_bundles_from_profiles
                sync_bundles_from_profiles(verbose=False)

                messagebox.showinfo(
                    "Level-Up Complete",
                    f"{variant_name} has been promoted to {next_level.capitalize()}!\n\nBundles synced successfully."
                )
            else:
                messagebox.showerror("Error", f"Could not load profile for {variant_name}")

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error in _perform_levelup: {e}")
            messagebox.showerror("Error", f"Level-up failed: {e}")


    def _open_agent_config_popup(self, agent_name):
        """Open agent configuration popup for schema/prompt settings"""
        try:
            import tkinter.scrolledtext as scrolledtext

            # Get agent config from roster (mounted agents)
            agent_config = None
            roster = []
            if hasattr(self.root, 'get_active_agents'):
                roster = self.root.get_active_agents() or []
            for r in roster:
                if r.get('name') == agent_name:
                    agent_config = r
                    break

            # If not in active roster, try getting from Agents tab config
            if not agent_config:
                try:
                    if hasattr(self, 'agents_tab') and hasattr(self.agents_tab, 'agent_configs'):
                        agent_config = self.agents_tab.agent_configs.get(agent_name)
                        if agent_config:
                            # Convert agents_tab config format to roster format
                            agent_config = {
                                'name': agent_name,
                                'variant': agent_config.get('variant'),
                                'system_prompt': agent_config.get('system_prompt'),
                                'tool_schema': agent_config.get('tool_schema'),
                                'system_prompt_override': agent_config.get('system_prompt_override'),
                                'tool_schema_override': agent_config.get('tool_schema_override')
                            }
                except Exception as e:
                    log_message(f"CUSTOM_CODE_TAB: Error fetching agent config from agents_tab: {e}")

            if not agent_config:
                messagebox.showwarning("Agent Not Found", f"Agent '{agent_name}' not found in roster or Agents tab.\n\nPlease configure the agent in the Agents tab first.")
                return

            # Create popup
            popup = tk.Toplevel(self.root)
            popup.title(f"Agent Config: {agent_name}")
            popup.geometry("900x650")
            popup.configure(bg='#2b2b2b')
            try:
                popup.transient(self.root)
                popup.lift()
            except Exception:
                pass

            # Top tab selector
            header = ttk.Frame(popup)
            header.pack(fill=tk.X, padx=10, pady=(10, 0))
            body = ttk.Frame(popup)
            body.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            active = {'tab': 'prompt'}

            def show_prompt_tab():
                active['tab'] = 'prompt'
                for w in body.winfo_children():
                    w.destroy()
                self._build_agent_prompt_ui(body, agent_name, agent_config, popup)
                try:
                    btn_prompt.configure(style='Action.TButton')
                    btn_schema.configure(style='Select.TButton')
                except Exception:
                    pass

            def show_schema_tab():
                active['tab'] = 'schema'
                for w in body.winfo_children():
                    w.destroy()
                self._build_agent_schema_ui(body, agent_name, agent_config, popup)
                try:
                    btn_prompt.configure(style='Select.TButton')
                    btn_schema.configure(style='Action.TButton')
                except Exception:
                    pass

            btn_prompt = ttk.Button(header, text='System Prompt', style='Action.TButton', command=show_prompt_tab)
            btn_schema = ttk.Button(header, text='Tool Schema', style='Select.TButton', command=show_schema_tab)
            btn_prompt.pack(side=tk.LEFT, padx=(0, 6))
            btn_schema.pack(side=tk.LEFT)

            # Default to prompt tab
            show_prompt_tab()

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error opening agent config popup: {e}")
            messagebox.showerror("Error", f"Failed to open agent config: {e}")

    def _build_agent_prompt_ui(self, parent, agent_name, agent_config, popup):
        """Build system prompt UI for agent config"""
        try:
            import tkinter.scrolledtext as scrolledtext
            from pathlib import Path

            parent.columnconfigure(0, weight=0)
            parent.columnconfigure(1, weight=1)
            parent.rowconfigure(0, weight=1)

            # Get agent type and class for filtering
            agent_type = None
            class_level = None
            try:
                variant = agent_config.get('variant')
                if variant:
                    import sys
                    cfg_path = Path(__file__).parent.parent.parent.parent
                    if str(cfg_path) not in sys.path:
                        sys.path.insert(0, str(cfg_path))
                    import config as C
                    mp = C.load_model_profile(variant) or {}
                    agent_type = mp.get('assigned_type')
                    class_level = mp.get('class_level')
            except Exception:
                pass

            # Left: prompt list
            left = ttk.Frame(parent, style='Category.TFrame')
            left.grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 6))

            # Header with agent type/class info
            header_text = 'Available Prompts'
            if agent_type and class_level:
                header_text = f'Prompts for {agent_type} ({class_level})'
            ttk.Label(left, text=header_text, font=("Arial", 11, 'bold'), style='CategoryPanel.TLabel').pack(anchor=tk.W, pady=(0, 6))

            lf = ttk.Frame(left)
            lf.pack(fill=tk.BOTH, expand=True)
            sb = ttk.Scrollbar(lf)
            sb.pack(side=tk.RIGHT, fill=tk.Y)
            lst = tk.Listbox(lf, yscrollcommand=sb.set, bg='#1e1e1e', fg='#ffffff', selectbackground='#61dafb', width=30)
            lst.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb.config(command=lst.yview)

            # Load available prompts
            prompts_dir = Path(__file__).parent / "system_prompts"
            all_prompts = sorted([f.stem for f in prompts_dir.glob('*.txt')]) if prompts_dir.exists() else []

            current_prompt = agent_config.get('system_prompt_override') or agent_config.get('system_prompt', 'default')

            # Organize prompts: type-specific first, then others
            type_prompts = []
            other_prompts = []

            if agent_type:
                for name in all_prompts:
                    if agent_type in name.lower():
                        type_prompts.append(name)
                    else:
                        other_prompts.append(name)
            else:
                other_prompts = all_prompts

            # Add type-specific prompts with marker
            idx = 0
            if type_prompts:
                lst.insert(tk.END, f"━━━ {agent_type.upper()} PROMPTS ━━━")
                lst.itemconfig(idx, {'bg': '#2d2d2d', 'fg': '#61dafb', 'selectbackground': '#2d2d2d'})
                idx += 1
                for name in type_prompts:
                    display_name = f"✓ {name}" if name == current_prompt else f"  {name}"
                    if class_level and class_level in name.lower():
                        display_name += f"  [default for {class_level}]"
                    lst.insert(tk.END, display_name)
                    if name == current_prompt:
                        lst.selection_set(idx)
                    idx += 1

            # Add other prompts
            if other_prompts:
                if type_prompts:
                    lst.insert(tk.END, "━━━ OTHER PROMPTS ━━━")
                    lst.itemconfig(idx, {'bg': '#2d2d2d', 'fg': '#bbbbbb', 'selectbackground': '#2d2d2d'})
                    idx += 1
                for name in other_prompts:
                    display_name = f"✓ {name}" if name == current_prompt else f"  {name}"
                    lst.insert(tk.END, display_name)
                    if name == current_prompt:
                        lst.selection_set(idx)
                    idx += 1

            # Right: editor
            right = ttk.Frame(parent, style='Category.TFrame')
            right.grid(row=0, column=1, sticky=tk.NSEW)
            right.columnconfigure(0, weight=1)
            right.rowconfigure(1, weight=1)

            title = ttk.Label(right, text=f'Current: {current_prompt}', font=("Arial", 11, 'bold'), style='CategoryPanel.TLabel')
            title.grid(row=0, column=0, sticky=tk.W, pady=(0, 6))

            ed = scrolledtext.ScrolledText(right, wrap=tk.WORD, font=("Courier", 10), bg='#1e1e1e', fg='#ffffff', insertbackground='#61dafb')
            ed.grid(row=1, column=0, sticky=tk.NSEW)

            current = {'name': current_prompt, 'modified': False}

            def load_selected(_e=None):
                if not lst.curselection():
                    return
                raw_name = lst.get(lst.curselection()[0])

                # Skip separator rows
                if '━━━' in raw_name:
                    return

                # Strip display markers (✓, spaces, [default] suffix)
                name = raw_name.strip()
                if name.startswith('✓'):
                    name = name[1:].strip()
                elif name.startswith(' '):
                    name = name.strip()

                # Remove [default for X] suffix
                if '[default for' in name:
                    name = name.split('[default for')[0].strip()

                current['name'] = name
                try:
                    content = (prompts_dir / f"{name}.txt").read_text()
                except Exception:
                    content = f"# Prompt file not found: {name}.txt"
                ed.delete(1.0, tk.END)
                ed.insert(tk.END, content)
                current['modified'] = False
                title.config(text=f"Editing: {name}")

            load_selected()
            lst.bind('<<ListboxSelect>>', load_selected)

            # Bottom buttons
            btns = ttk.Frame(parent)
            btns.grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=(6, 0))

            def apply_cb():
                name = current.get('name')
                if not name:
                    return
                try:
                    # Update agent config in roster
                    if hasattr(self.root, 'get_active_agents'):
                        roster = self.root.get_active_agents() or []
                        for r in roster:
                            if r.get('name') == agent_name:
                                r['system_prompt_override'] = name
                                break
                        self.root.set_active_agents(roster)

                    # ALSO update agents_tab.agent_configs so chat_interface can read it
                    if hasattr(self, 'agents_tab') and hasattr(self.agents_tab, 'agent_configs'):
                        agent_cfg = self.agents_tab.agent_configs.get(agent_name)
                        if not agent_cfg:
                            # Create config if it doesn't exist
                            agent_cfg = {}
                            self.agents_tab.agent_configs[agent_name] = agent_cfg
                        agent_cfg['system_prompt'] = name
                        agent_cfg['system_prompt_override'] = name
                        log_message(f"CUSTOM_CODE_TAB: Updated agents_tab config for {agent_name}: system_prompt={name}")

                    messagebox.showinfo("Success", f"System prompt set to '{name}' for {agent_name}")
                    popup.destroy()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to apply prompt: {e}")

            ttk.Button(btns, text='✓ Apply', style='Action.TButton', command=apply_cb).pack(side=tk.LEFT, padx=4)
            ttk.Button(btns, text='Cancel', style='Select.TButton', command=popup.destroy).pack(side=tk.LEFT, padx=4)

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error building prompt UI: {e}")

    def _build_agent_schema_ui(self, parent, agent_name, agent_config, popup):
        """Build tool schema UI for agent config"""
        try:
            import tkinter.scrolledtext as scrolledtext
            from pathlib import Path

            parent.columnconfigure(0, weight=0)
            parent.columnconfigure(1, weight=1)
            parent.rowconfigure(0, weight=1)

            # Left: schema list
            left = ttk.Frame(parent, style='Category.TFrame')
            left.grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 6))
            ttk.Label(left, text='Available Schemas', font=("Arial", 11, 'bold'), style='CategoryPanel.TLabel').pack(anchor=tk.W, pady=(0, 6))

            lf = ttk.Frame(left)
            lf.pack(fill=tk.BOTH, expand=True)
            sb = ttk.Scrollbar(lf)
            sb.pack(side=tk.RIGHT, fill=tk.Y)
            lst = tk.Listbox(lf, yscrollcommand=sb.set, bg='#1e1e1e', fg='#ffffff', selectbackground='#61dafb', width=24)
            lst.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb.config(command=lst.yview)

            # Load available schemas using config functions
            import config as C
            schemas = list(C.list_tool_schemas())  # Now includes variant schemas from tool_schemas_configs/

            current_schema = agent_config.get('tool_schema_override') or agent_config.get('tool_schema', 'default')

            for i, name in enumerate(schemas):
                lst.insert(tk.END, name)
                if name == current_schema:
                    lst.selection_set(i)

            # Right: preview
            right = ttk.Frame(parent, style='Category.TFrame')
            right.grid(row=0, column=1, sticky=tk.NSEW)
            right.columnconfigure(0, weight=1)
            right.rowconfigure(1, weight=1)

            title = ttk.Label(right, text=f'Current: {current_schema}', font=("Arial", 11, 'bold'), style='CategoryPanel.TLabel')
            title.grid(row=0, column=0, sticky=tk.W, pady=(0, 6))

            ed = scrolledtext.ScrolledText(right, wrap=tk.WORD, font=("Courier", 10), bg='#1e1e1e', fg='#ffffff', insertbackground='#61dafb')
            ed.grid(row=1, column=0, sticky=tk.NSEW)

            current = {'name': current_schema}

            def load_selected(_e=None):
                if not lst.curselection():
                    return
                name = lst.get(lst.curselection()[0])
                current['name'] = name
                try:
                    import json
                    content_obj = C.load_tool_schema(name)  # Use config function for smart path resolution
                    content = json.dumps(content_obj, indent=2)
                except Exception as e:
                    content = f"{{\n  \"error\": \"Schema file not found: {name}.json\",\n  \"details\": \"{str(e)}\"\n}}"
                ed.delete(1.0, tk.END)
                ed.insert(tk.END, content)
                title.config(text=f"Preview: {name}")

            load_selected()
            lst.bind('<<ListboxSelect>>', load_selected)

            # Bottom buttons
            btns = ttk.Frame(parent)
            btns.grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=(6, 0))

            def apply_cb():
                name = current.get('name')
                if not name:
                    return
                try:
                    # Update agent config in roster
                    if hasattr(self.root, 'get_active_agents'):
                        roster = self.root.get_active_agents() or []
                        for r in roster:
                            if r.get('name') == agent_name:
                                r['tool_schema_override'] = name
                                break
                        self.root.set_active_agents(roster)

                    # ALSO update agents_tab.agent_configs so chat_interface can read it
                    if hasattr(self, 'agents_tab') and hasattr(self.agents_tab, 'agent_configs'):
                        agent_cfg = self.agents_tab.agent_configs.get(agent_name)
                        if not agent_cfg:
                            # Create config if it doesn't exist
                            agent_cfg = {}
                            self.agents_tab.agent_configs[agent_name] = agent_cfg
                        agent_cfg['tool_schema'] = name
                        agent_cfg['tool_schema_override'] = name
                        log_message(f"CUSTOM_CODE_TAB: Updated agents_tab config for {agent_name}: tool_schema={name}")

                    messagebox.showinfo("Success", f"Tool schema set to '{name}' for {agent_name}")
                    popup.destroy()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to apply schema: {e}")

            ttk.Button(btns, text='✓ Apply', style='Action.TButton', command=apply_cb).pack(side=tk.LEFT, padx=4)
            ttk.Button(btns, text='Cancel', style='Select.TButton', command=popup.destroy).pack(side=tk.LEFT, padx=4)

        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB: Error building schema UI: {e}")

    def refresh_tab(self):
        """Refresh the entire tab"""
        log_message("CUSTOM_CODE_TAB: Refreshing tab...")
        self.refresh_model_list()
        if hasattr(self, 'chat_interface') and self.chat_interface:
            self.chat_interface.refresh()
