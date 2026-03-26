# [SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]
"""
Chat Interface Tab - Interactive chat with Ollama models
Provides a simple chat interface to test and interact with models
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import re
import random
import json
import threading
import queue
from pathlib import Path
import sys
from datetime import datetime
import os
import socket
import time
from typing import Optional, Any, Dict, List, Tuple
import json

try:
    from bug_tracker import get_bug_tracker
except ImportError:  # pragma: no cover
    get_bug_tracker = None

# --- Debug helpers ---------------------------------------------------------

_SERVER_STATUS_CACHE = {}

def _debug_log(message: str):
    """Robust debug logging helper that never raises."""
    try:
        log_message(message)
    except Exception:
        try:
            print(message)
        except Exception:
            pass

def _install_thread_excepthook():
    """Ensure uncaught thread exceptions are logged."""
    try:
        def _hook(args):
            try:
                log_message(f"THREAD_EXC: thread={getattr(args, 'thread', None)} exc={args.exc_type}: {args.exc_value}")
            except Exception:
                pass
        threading.excepthook = _hook
    except Exception:
        pass

_install_thread_excepthook()

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Acquire custom-code tab logger
from logger_util import get_tab_logger
from feature_flags import is_enabled as feature_enabled

log_message, log_error, log_exception = get_tab_logger('custom_code')

# S4-S6 module imports
try:
    from .. import capabilities
    log_message("CHAT_INTERFACE: capabilities module imported successfully.")
except (ImportError, ModuleNotFoundError) as e:
    log_message(f"CHAT_INTERFACE: FAILED to import capabilities: {e}")
    capabilities = None
try:
    from registry import bundle_loader
    log_message("CHAT_INTERFACE: bundle_loader module imported successfully.")
except (ImportError, ModuleNotFoundError) as e:
    log_message(f"CHAT_INTERFACE: FAILED to import bundle_loader: {e}")
    bundle_loader = None
try:
    from .. import router
    log_message("CHAT_INTERFACE: router module imported successfully.")
except (ImportError, ModuleNotFoundError) as e:
    log_message(f"CHAT_INTERFACE: FAILED to import router: {e}")
    router = None

from tabs.base_tab import BaseTab
from tabs.custom_code_tab.rag_service import RagService

try:
    from tabs.custom_code_tab.vector_backends import HCodexVectorClient, VectorSearchError
except Exception:
    HCodexVectorClient = None  # type: ignore[assignment]
    VectorSearchError = Exception  # type: ignore[assignment]

# Skill rating integration (Phase 2.9)
try:
    from skill_rating_integration import add_skill_rating_to_chat_display, is_skill_rating_enabled
    log_message("CHAT_INTERFACE: Skill rating integration imported successfully.")
    SKILL_RATING_AVAILABLE = True
except (ImportError, ModuleNotFoundError) as e:
    log_message(f"CHAT_INTERFACE: Skill rating not available: {e}")
    SKILL_RATING_AVAILABLE = False


class ChatInterfaceTab(BaseTab):
    """Chat interface for interacting with Ollama models"""

    def __init__(self, parent, root, style, parent_tab):
        super().__init__(parent, root, style)
        self.parent_tab = parent_tab
        try:
            log_message(f"LIVE PROBE: ChatInterfaceTab __init__ called (instance_id={id(self)})")
        except Exception:
            pass
        # Ensure backend_settings exists before any debug helpers reference it
        self.backend_settings = {}
        try:
            self.backend_settings = self.load_backend_settings()
        except Exception:
            self.backend_settings = {}
        _debug_log(f"CHAT_DBG: __init__ start instance={id(self)}")
        _debug_log(f"CHAT_DBG: backend_settings reuse instance={id(self)}")
        _debug_log(f"CHAT_DBG: backend_settings loaded instance={id(self)} auto_start={self.backend_settings.get('llama_server_auto_start')} base_url={self.backend_settings.get('llama_server_base_url')}")
        self.backend_settings.setdefault('status_probes_enabled', True)
        self.backend_settings.setdefault('llama_server_probe_ttl', 3.0)

        self.current_model = None
        self.chat_history = []
        self.is_generating = False
        self.is_mounted = False
        self.is_standard_mode = False
        self.training_mode_enabled = False
        self._initialization_complete = False  # Guard to prevent callbacks during mainloop startup
        self.realtime_eval_scores = {}
        self.conversation_histories = {}  # {model_name: [chat_history]}
        self.last_user_message = ""  # Track for tool call validation
        self._tools_permission_granted = None
        self._suppress_quickview = False

        # Thread safety for agent sessions
        import threading
        import queue
        self._agents_sessions_lock = threading.Lock()
        self._agents_servers_lock = threading.Lock()

        # Bidirectional agent request serialization (prevents flooding, ensures ordered execution)
        # Using a semaphore with limit=1 to enforce sequential execution
        self._agent_request_semaphore = threading.Semaphore(1)  # Only 1 agent request at a time
        self._agent_request_lock = threading.Lock()  # For thread-safe state tracking

        # Global tool execution queue (prevents conflicts, ensures serialization)
        self._tool_execution_queue = queue.PriorityQueue()  # Priority queue: (priority, timestamp, item)
        self._tool_queue_lock = threading.Lock()
        self._tool_queue_active = True
        self._tool_queue_results = {}  # {request_id: result} for returning results
        self._tool_queue_events = {}  # {request_id: Event} for signaling completion

        # Per-tool-type locks for conflicting operations
        self._tool_locks = {
            'bash': threading.Lock(),
            'file_write': threading.Lock(),
            'directory': threading.Lock(),
        }

        # Start tool queue processor thread
        self._tool_queue_processor_thread = threading.Thread(
            target=self._process_tool_queue,
            daemon=True,
            name="ToolQueueProcessor"
        )
        self._tool_queue_processor_thread.start()
        log_message("TOOL_QUEUE: Global tool execution queue initialized")

        # LLM inference coordination semaphore (limits concurrent generations)
        max_concurrent_inferences = self.backend_settings.get('max_concurrent_llm_inferences', 2)
        self._llm_inference_semaphore = threading.Semaphore(max_concurrent_inferences)
        self._llm_inference_active_count = 0
        self._llm_inference_count_lock = threading.Lock()
        log_message(f"LLM_QUEUE: Inference semaphore initialized (max_concurrent={max_concurrent_inferences})")

        # Ephemeral ThinkTime for next input (seconds)
        self._think_next_min = None
        self._think_next_max = None
        # Quick indicators internal state
        self._qa_state_key = None
        self._tooltip_active = False
        # Log agent events in main chat (can be toggled in Quick Actions)
        self.agent_events_logging_enabled = True
        # Track last processed promotion event
        self._last_promotion_event_ts = None
        # Simple conformer events store per agent: {agent: [ {ts, kind, data} ]}
        self._conformer_events = {}
        # Show Thoughts (streaming preview) toggle
        self.show_thoughts = False
        # RAG per chat (default OFF) and save-per-session flag
        self.rag_enabled = False
        self.rag_save_session = False
        # Per-session Agentic Project override (None=use backend default, True/False=override)
        self.agentic_project_override = None
        # Track QA settings changes to prompt on exit/switch
        self._qa_settings_dirty = False
        # Track if chat content changed (unsaved)
        self._chat_dirty = False
        # Tracker window lock state
        self.tracker_window_locked = self.backend_settings.get('tracker_window_locked', False)
        self._locked_tracker_geometry = self.backend_settings.get('locked_tracker_geometry', None)
        self._unlocked_tracker_sash_position = self.backend_settings.get('tracker_sash_position', None)

        # Animation state
        self._core_animation_job = None
        self._core_pulse_direction = 1
        self._core_current_radius = 10
        self._core_pulse_speed = 150

        # Backend-specific runtime flags
        self._llama_server_stream_warned = False
        self._llama_server_proc = None
        self._llama_server_stdout_handle = None
        self._llama_server_stderr_handle = None
        # Per-agent llama.cpp servers (separate from main model server)
        # name -> {'proc': Popen, 'port': int, 'base_url': str, 'model': str}
        self._agent_servers = {}
        # llama-server stderr watcher
        self._stderr_watcher_thread = None
        self._stderr_watcher_stop = False
        self._stderr_watcher_path = None

        # Watchdog / diagnostics state
        self._gen_watchdog_timer = None
        self._gen_send_started = False
        self._pending_parallel_min_send = False
        self._parallel_min_send_token = None
        self._server_online_cached = None
        self._server_online_ts = 0
        try:
            self._probe_lock = threading.Lock()
        except Exception:
            self._probe_lock = None
        self._probe_job = None

        # Refresh quick indicators when Agents roster changes
        try:
            self.root.bind('<<AgentsRosterChanged>>', lambda e: self._update_quick_indicators())
        except Exception:
            pass

        # Track active generation process/thread for proper stopping
        self._current_proc = None
        self._gen_thread = None
        self._stop_event = threading.Event()
        try:
            self._proc_lock = threading.Lock()
        except Exception:
            self._proc_lock = None

        # Session temperature
        self.session_temperature = self.backend_settings.get('temperature', 0.8)
        # Temperature mode (manual/auto)
        try:
            self.temp_mode = str(self.backend_settings.get('temp_mode', 'manual')).lower()
            if self.temp_mode not in ('manual', 'auto'):
                self.temp_mode = 'manual'
        except Exception:
            self.temp_mode = 'manual'

        # RAG scoring method (standard, vcm, auto, manual)
        # Old panel_rag_level will be migrated in _migrate_rag_state()
        try:
            self.rag_scoring_method = self.backend_settings.get('rag_scoring_method', 'standard')
        except Exception:
            self.rag_scoring_method = 'standard'

        # Last known agents roster cache (used when TrainingGUI APIs are not
        # directly exposed on the Tk root). Updated whenever we emit a roster change.
        self._last_known_roster = []
        # Track mounted agent server ports locally so inference can continue even if roster metadata lags
        self._agent_server_ports: dict[str, int] = {}

        # Current mode (persisted in mode_settings.json)
        self.current_mode = 'smart'
        try:
            mode_settings_file = Path(__file__).parent.parent / "mode_settings.json"
            if mode_settings_file.exists():
                with open(mode_settings_file, 'r') as _f:
                    _m = json.load(_f)
                self.current_mode = _m.get('current_mode', 'smart')
        except Exception:
            self.current_mode = 'smart'

        # Tool execution
        self.tool_executor = None
        self.initialize_tool_executor()

        # Tool call logging and detection
        self.tool_call_logger = None
        self.tool_call_detector = None
        self.initialize_tool_logging()

        # Chat history management
        self.chat_history_manager = None
        self.current_session_id = None
        self.initialize_history_manager()
        # RAG service and debug
        try:
            self.rag_service = RagService(self.chat_history_manager, None)
            # Apply retrieval params from backend settings
            try:
                rk1 = float(self.backend_settings.get('rag_k1', 1.2))
                rb = float(self.backend_settings.get('rag_b', 0.75))
                rdd = float(self.backend_settings.get('rag_decay_days', 3.0))
                self.rag_service.set_params(k1=rk1, b=rb, decay_days=rdd)
            except Exception:
                pass
            # Try to load persisted global index (non-fatal)
            self.rag_service.load_global_index()
        except Exception:
            self.rag_service = RagService()
        # Vector backend integration
        self.vector_client = None
        self.embedding_server = None
        self._vector_backend_available = False
        self.rag_service.set_vector_backend(None)
        try:
            from tabs.custom_code_tab.vector_backends import EmbeddingServerManager
            self.embedding_server = EmbeddingServerManager(logger=log_message)
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Could not load EmbeddingServerManager: {e}")
        try:
            vec_weight = self.backend_settings.get('rag_vector_weight', None)
            vec_limit = self.backend_settings.get('rag_vector_limit', None)
            if HCodexVectorClient:
                cfg_path = Path.home() / ".config" / "h-codex" / "config.json"
                self.vector_client = HCodexVectorClient(config_path=cfg_path, logger=log_message)
                self._vector_backend_available = True
                self.rag_service.set_vector_backend(self.vector_client, weight=vec_weight, limit=vec_limit)
                log_message("CHAT_INTERFACE: h-codex vector backend initialized")
            else:
                log_message("CHAT_INTERFACE: h-codex vector backend unavailable (module not loaded)")
                self.rag_service.set_vector_backend(None)
        except VectorSearchError as e:
            log_message(f"CHAT_INTERFACE: Vector backend init failed: {e}")
            self.vector_client = None
            self.rag_service.set_vector_backend(None)
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Unexpected vector backend error: {e}")
            self.vector_client = None
            self.rag_service.set_vector_backend(None)
        try:
            self.rag_vector_enabled_default = bool(self.backend_settings.get('rag_scope_vector', False))
        except Exception:
            self.rag_vector_enabled_default = False
        self.rag_service.enable_vector_search(self.rag_vector_enabled_default and self._vector_backend_available)
        # Auto-training trigger state
        try:
            self.rag_autotrain_enabled = bool(self.backend_settings.get('rag_autotrain_enabled', False))
            self.rag_autotrain_window = int(self.backend_settings.get('rag_autotrain_window', 5))
            self.rag_autotrain_threshold = float(self.backend_settings.get('rag_autotrain_threshold', 0.7))
            self.rag_autotrain_require_promotion_gate = bool(self.backend_settings.get('rag_autotrain_require_promotion_gate', True))
            self.rag_autotrain_backend_override = bool(self.backend_settings.get('rag_autotrain_backend_override', False))
            self.class_promotion_earned = bool(self.backend_settings.get('class_promotion_earned', False))
            self.rag_project_adapters = list(self.backend_settings.get('rag_project_adapters', []))
        except Exception:
            self.rag_autotrain_enabled = False
            self.rag_autotrain_window = 5
            self.rag_autotrain_threshold = 0.7
            self.rag_autotrain_require_promotion_gate = True
            self.rag_autotrain_backend_override = False
            self.class_promotion_earned = False
            self.rag_project_adapters = []
        self._rag_recent_scores = []
        self._rag_last_trigger_ts = 0
        try:
            self.rag_debug_enabled = bool(self.backend_settings.get('rag_debug', False))
        except Exception:
            self.rag_debug_enabled = False
        self._last_rag_context: dict[str, Any] | None = None
        self._last_prompt_diagnostics: dict[str, Any] | None = None
        self._last_prompt_ready_state = {
            'has_tools': None,
            'has_roles': None,
            'ts': 0.0,
        }

        # Load advanced settings
        self.advanced_settings = self.load_advanced_settings()
        self._orchestrator_required = feature_enabled("FEATURE_ORCHESTRATOR_ENFORCE")
        self._verification_required = feature_enabled("FEATURE_VERIFICATION_ENGINE")

        # System Prompt and Tool Schema management
        # Load chat defaults from backend settings; allow None (off)
        try:
            dsp = self.backend_settings.get('default_system_prompt', 'default')
            dts = self.backend_settings.get('default_tool_schema', 'default')
        except Exception:
            dsp, dts = 'default', 'default'
        self.current_system_prompt = dsp if dsp not in ("None", None, "") else None
        self.current_tool_schema = dts if dts not in ("None", None, "") else None
        self._schema_source = None  # None | 'type-default' | 'user'
        self._type_default_applied = False
        # Type Schema for main model
        try:
            dmts = self.backend_settings.get('default_main_model_type_schema', None)
        except Exception:
            dmts = None
        self.current_main_model_type_schema = dmts if dmts not in ("None", None, "") else None
        self.system_prompts_dir = Path(__file__).parent.parent / "system_prompts"
        self.tool_schemas_dir = Path(__file__).parent.parent / "tool_schemas_configs"
        self._ensure_prompt_schema_dirs()

        # Initialize advanced components (all based on settings)
        self.initialize_advanced_components()
        # Wire optional context scorer to RAG service and prime index
        try:
            if hasattr(self, 'context_scorer') and self.context_scorer:
                self.rag_service.set_context_scorer(self.context_scorer)
            self.rag_service.refresh_index_global()
        except Exception:
            pass

        # Tracker state
        self.tracker_window = None
        self.is_tracker_active = False
        self._tracker_after_id = None

        # React to model selections from Models tab
        try:
            def _on_model_selected(event=None):
                """Handle double-click model selection - sets active model (no mount, no popup)"""
                log_message(f"CHAT_INTERFACE: _on_model_selected triggered on instance {id(self)}")
                try:
                    import json as _json

                    # Only process if this is the chat_interface in Custom Code tab
                    if hasattr(self.parent_tab, 'chat_interface') and self.parent_tab.chat_interface is not self:
                        log_message(f"CHAT_INTERFACE: Skipping - not the active chat interface (this={id(self)}, active={id(self.parent_tab.chat_interface)})")
                        return

                    # Try shared attribute first (same workaround as popup)
                    model_data = None
                    if hasattr(self.parent_tab, '_pending_popup_data') and self.parent_tab._pending_popup_data:
                        model_data = self.parent_tab._pending_popup_data
                        log_message(f"CHAT_INTERFACE: Retrieved model_data from shared attribute for double-click")
                    else:
                        # Fallback to event.data
                        model_data = _json.loads(getattr(event, 'data', '{}') or '{}')
                        log_message(f"CHAT_INTERFACE: Retrieved model_data from event.data for double-click")

                    if not model_data:
                        log_message(f"CHAT_INTERFACE: ERROR - No model_data available in _on_model_selected!")
                        return

                    log_message(f"CHAT_INTERFACE: Processing double-click model selection")

                    # Use the public API to set active model (no mounting)
                    success = self.set_active_model(model_data)
                    if success:
                        log_message(f"CHAT_INTERFACE: Double-click set-active completed successfully")
                    else:
                        log_message(f"CHAT_INTERFACE: Double-click set-active failed")
                except Exception as e:
                    log_message(f"CHAT_INTERFACE: Error in _on_model_selected: {e}")

            self.root.bind('<<ModelSelected>>', _on_model_selected)
        except Exception:
            pass

        # React to model mount requests (double-click in direct mode)
        try:
            def _on_model_mount(event=None):
                """Handle double-click model mount - sets active + mounts immediately"""
                log_message(f"CHAT_INTERFACE: _on_model_mount triggered on instance {id(self)}")
                try:
                    import json as _json

                    # Only process if this is the chat_interface in Custom Code tab
                    if hasattr(self.parent_tab, 'chat_interface') and self.parent_tab.chat_interface is not self:
                        log_message(f"CHAT_INTERFACE: Skipping - not the active chat interface (this={id(self)}, active={id(self.parent_tab.chat_interface)})")
                        return

                    # Try shared attribute first
                    model_data = None
                    if hasattr(self.parent_tab, '_pending_popup_data') and self.parent_tab._pending_popup_data:
                        model_data = self.parent_tab._pending_popup_data
                        log_message(f"CHAT_INTERFACE: Retrieved model_data from shared attribute for mount")
                    else:
                        # Fallback to event.data
                        model_data = _json.loads(getattr(event, 'data', '{}') or '{}')
                        log_message(f"CHAT_INTERFACE: Retrieved model_data from event.data for mount")

                    if not model_data:
                        log_message(f"CHAT_INTERFACE: ERROR - No model_data available in _on_model_mount!")
                        return

                    log_message(f"CHAT_INTERFACE: Processing double-click model mount")

                    # Use the public API to set active model
                    success = self.set_active_model(model_data)
                    if success:
                        # Mount after brief delay to allow UI to update
                        self.root.after(50, self.mount_model)
                        log_message(f"CHAT_INTERFACE: Double-click mount completed - model set and mounting")
                    else:
                        log_message(f"CHAT_INTERFACE: Double-click mount failed - could not set active model")
                except Exception as e:
                    log_message(f"CHAT_INTERFACE: Error in _on_model_mount: {e}")

            self.root.bind('<<ModelMount>>', _on_model_mount)
        except Exception:
            pass

        # React to model selection popup requests (single-click)
        try:
            def _on_model_selected_popup(event=None):
                log_message(f"CHAT_INTERFACE: <<ModelSelectedPopup>> event received on instance {id(self)}")
                try:
                    import json as _json

                    # CRITICAL: Only the Custom Code tab's chat_interface should show the popup
                    # The popup is triggered from Custom Code tab's model list sidebar
                    # Other tab instances (Projects, Chat) should ignore this event
                    parent_has_chat_interface = hasattr(self.parent_tab, 'chat_interface')

                    if parent_has_chat_interface:
                        # Check if THIS instance is the one referenced by parent_tab
                        if self.parent_tab.chat_interface is self:
                            log_message(f"CHAT_INTERFACE: This is the Custom Code tab's chat_interface - showing popup")
                        else:
                            log_message(f"CHAT_INTERFACE: Skipping - this instance ({id(self)}) is not parent_tab.chat_interface ({id(self.parent_tab.chat_interface)})")
                            return
                    else:
                        # Parent tab doesn't have chat_interface attribute (e.g., standalone Chat tab)
                        # These instances should NOT show the popup from Custom Code tab's sidebar
                        log_message(f"CHAT_INTERFACE: Skipping - parent_tab has no chat_interface attribute")
                        return

                    # Try shared attribute first (workaround for Tkinter event.data limitations)
                    model_data = None
                    if hasattr(self.parent_tab, '_pending_popup_data') and self.parent_tab._pending_popup_data:
                        model_data = self.parent_tab._pending_popup_data
                        log_message(f"CHAT_INTERFACE: Retrieved model_data from shared attribute: {model_data}")
                    else:
                        # Fallback to event.data for compatibility
                        model_data = _json.loads(getattr(event, 'data', '{}') or '{}')
                        log_message(f"CHAT_INTERFACE: Retrieved model_data from event.data: {model_data}")

                    if not model_data:
                        log_message(f"CHAT_INTERFACE: ERROR - No model_data available!")
                        return

                    log_message(f"CHAT_INTERFACE: Showing model popup")
                    self._show_model_popup(model_data, event)
                except Exception as e:
                    log_message(f"CHAT_INTERFACE: Error in _on_model_selected_popup: {e}")

            log_message("CHAT_INTERFACE: Binding <<ModelSelectedPopup>> to root window")
            self.root.bind('<<ModelSelectedPopup>>', _on_model_selected_popup)
            log_message("CHAT_INTERFACE: <<ModelSelectedPopup>> binding complete")
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Failed to bind popup event: {e}")


    def toggle_tracker_window(self):
        log_message("CHAT_INTERFACE: toggle_tracker_window called.")
        if self.is_tracker_active:
            log_message("CHAT_INTERFACE: Tracker window is active, calling _on_tracker_close.")
            self._on_tracker_close()
        else:
            log_message("CHAT_INTERFACE: Tracker window is inactive, calling create_tracker_window.")
            self.create_tracker_window()
        log_message("CHAT_INTERFACE: toggle_tracker_window finished.")

    def _enrich_model_data(self, model_data: dict) -> dict:
        """
        Enrich basic model_data with profile, bundle, and lineage information.

        Takes minimal model_data (just paths) and adds:
        - variant_name (extracted from GGUF filename)
        - profile data (base_model, class, skills, etc.)
        - bundle data (if available)
        """
        from pathlib import Path
        enriched = model_data.copy()

        try:
            # Extract variant name from GGUF filename
            # E.g., "Qwen2.5-0.5b_coder.q4_k_m.gguf" -> "Qwen2.5-0.5b_coder"
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
                log_message(f"CHAT_INTERFACE: Extracted variant_name: {variant_name}")
            else:
                # For Ollama tags, use tag as variant name
                enriched['variant_name'] = enriched.get('tag') or enriched.get('id', 'Unknown')

            # Load model profile (always fresh from disk - no caching)
            from config import load_model_profile
            variant_name = enriched.get('variant_name', 'Unknown')
            try:
                # Force fresh load from disk (load_model_profile reads directly from file)
                profile = load_model_profile(variant_name)
                enriched['profile'] = profile

                # Handle potentially empty/reset profiles gracefully
                enriched['base_model'] = profile.get('base_model', 'N/A')
                enriched['class'] = profile.get('assigned_type', 'unassigned')
                enriched['class_level'] = profile.get('class_level', 'novice')
                enriched['lineage_id'] = profile.get('lineage_id', '')

                # Log if profile appears to be freshly reset (no stats/xp)
                has_stats = bool(profile.get('stats'))
                xp = profile.get('xp', 0)
                has_xp = xp > 0 if isinstance(xp, int) else xp.get('total', 0) > 0 if isinstance(xp, dict) else False

                if not has_stats and not has_xp:
                    log_message(f"CHAT_INTERFACE: Loaded profile for {variant_name} (appears to be reset/new - no stats/xp): base={enriched['base_model']}, class={enriched['class']}")
                else:
                    log_message(f"CHAT_INTERFACE: Loaded profile for {variant_name}: base={enriched['base_model']}, class={enriched['class']}, has_data=True")
            except Exception as e:
                log_message(f"CHAT_INTERFACE: Could not load profile for {variant_name}: {e}")
                enriched['base_model'] = 'N/A'
                enriched['class'] = 'unassigned'
                enriched['profile'] = {}

            # Try to load bundle metadata
            if enriched.get('is_local_gguf'):
                from registry.bundle_loader import find_bundle_by_gguf
                bundle = find_bundle_by_gguf(enriched.get('gguf_path', ''))
                if bundle:
                    enriched['bundle'] = bundle
                    log_message(f"CHAT_INTERFACE: Found bundle for GGUF: {bundle.get('ulid', 'unknown')}")

        except Exception as e:
            log_message(f"CHAT_INTERFACE: Error enriching model data: {e}")

        return enriched

    def _show_model_popup(self, model_data: dict, event=None):
        """
        Show compact model popup window (400x500) near cursor.

        Per user spec in PopupLayout_chatTab_model_display.txt:
        - 4 tabs: Overview, Skills, Class, Quick-Settings
        - Overview: Name, Parent, Type, Class, Token-speed, Context-Limit, Skills preview, Experience %, Next-Class
        - Bottom buttons: Set-Active, Quick-Mount, Check-Status
        """
        try:
            # Create popup window
            popup = tk.Toplevel(self.root)
            popup.title("Model Preview")
            popup.geometry("400x500")

            # Position near cursor if event available
            try:
                if event and hasattr(event, 'x_root') and hasattr(event, 'y_root'):
                    popup.geometry(f"+{event.x_root + 10}+{event.y_root + 10}")
            except:
                # Center on screen as fallback
                popup.update_idletasks()
                x = (popup.winfo_screenwidth() // 2) - 200
                y = (popup.winfo_screenheight() // 2) - 250
                popup.geometry(f"+{x}+{y}")

            popup.transient(self.root)
            popup.grab_set()

            # Main container
            main_frame = ttk.Frame(popup)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            # Create notebook for tabs
            notebook = ttk.Notebook(main_frame)
            notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

            # Tab frames
            overview_tab = ttk.Frame(notebook)
            skills_tab = ttk.Frame(notebook)
            class_tab = ttk.Frame(notebook)
            settings_tab = ttk.Frame(notebook)

            notebook.add(overview_tab, text="Overview")
            notebook.add(skills_tab, text="Skills")
            notebook.add(class_tab, text="Class")
            notebook.add(settings_tab, text="Quick-Settings")

            # Enrich model data with profile/bundle/lineage information
            model_data = self._enrich_model_data(model_data)

            # Populate tabs with enriched data
            self._populate_overview_tab(overview_tab, model_data)
            self._populate_skills_tab(skills_tab, model_data)
            self._populate_class_tab(class_tab, model_data)
            self._populate_settings_tab(settings_tab, model_data)

            # Bottom action buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=(5, 0))

            ttk.Button(button_frame, text="Set-Active",
                      command=lambda: self._set_active_from_popup(model_data, popup),
                      style='Action.TButton').pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

            ttk.Button(button_frame, text="Quick-Mount",
                      command=lambda: self._quick_mount_from_popup(model_data, popup),
                      style='Action.TButton').pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

            ttk.Button(button_frame, text="Check-Status",
                      command=lambda: self._check_status_from_popup(model_data, popup),
                      style='Action.TButton').pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        except Exception as e:
            log_message(f"CHAT_INTERFACE: Error creating model popup: {e}")

    def _populate_overview_tab(self, parent, model_data: dict):
        """Populate Overview tab with enriched model information."""
        parent.columnconfigure(1, weight=1)

        row = 0
        # Name - Use variant_name (without .gguf extension)
        model_name = model_data.get('variant_name', 'Unknown')
        ttk.Label(parent, text="Name:", style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(parent, text=model_name, style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=10, pady=5)
        row += 1

        # Parent - Use base_model from enriched data
        parent_name = model_data.get('base_model', 'N/A')
        ttk.Label(parent, text="Parent:", style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(parent, text=parent_name, style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=10, pady=5)
        row += 1

        # Type (backend)
        model_type = model_data.get('backend', 'ollama' if model_data.get('tag') else 'llama_server')
        ttk.Label(parent, text="Type:", style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(parent, text=model_type, style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=10, pady=5)
        row += 1

        # Class - Use enriched class data
        class_type = model_data.get('class', 'unassigned')
        class_level = model_data.get('class_level', '')
        class_label = f"{class_type} ({class_level})" if class_level else class_type
        ttk.Label(parent, text="Class:", style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(parent, text=class_label, style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=10, pady=5)
        row += 1

        # Token-speed (from profile stats)
        ttk.Label(parent, text="Token-speed:", style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        try:
            profile = model_data.get('profile', {})
            stats = profile.get('stats', {})
            token_speed = stats.get('token_speed_ema_tok_per_s')
            speed_text = f"{token_speed:.2f} tok/s" if token_speed is not None else "No data yet"
        except:
            speed_text = "No data yet"
        ttk.Label(parent, text=speed_text, style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=10, pady=5)
        row += 1

        # Context-Limit (from profile metadata)
        ttk.Label(parent, text="Context-Limit:", style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        try:
            profile = model_data.get('profile', {})
            metadata = profile.get('metadata', {})
            context_limit = metadata.get('context_length', metadata.get('context_limit', 4096))
            context_text = f"{context_limit:,}" if context_limit else "4096"
        except:
            context_text = "4096"
        ttk.Label(parent, text=context_text, style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=10, pady=5)
        row += 1

        # Skills preview - Use enriched profile skills
        ttk.Label(parent, text="Skills:", style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        try:
            from config import get_model_skills
            variant_name = model_data.get('variant_name', 'Unknown')
            skills_data = get_model_skills(variant_name)
            # Get verified skills only for summary
            verified_skills = [skill for skill, info in skills_data.items() if info.get('status') == 'Verified']
            if verified_skills:
                skills_preview = ', '.join(verified_skills[:3])
                if len(verified_skills) > 3:
                    skills_preview += f'... (+{len(verified_skills) - 3} more)'
            else:
                skills_preview = "(No verified skills)"
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Error loading skills: {e}")
            skills_preview = "(See Skills tab)"
        ttk.Label(parent, text=skills_preview, style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=10, pady=5)
        row += 1

        # Experience % (from XP progression)
        ttk.Label(parent, text="Experience %:", style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        try:
            from xp_calculator import get_xp_to_next_class
            variant_name = model_data.get('variant_name', 'Unknown')
            xp_info = get_xp_to_next_class(variant_name)

            if xp_info.get('next_class') is None:
                # At max level
                exp_text = "100% (Max Level)"
            else:
                progress = xp_info.get('progress_percent', 0.0)
                exp_text = f"{progress:.1f}%"
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Error loading XP progress: {e}")
            exp_text = "No data yet"
        ttk.Label(parent, text=exp_text, style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=10, pady=5)
        row += 1

        # Next-Class (from XP progression)
        ttk.Label(parent, text="Next-Class:", style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        try:
            from xp_calculator import get_xp_to_next_class
            variant_name = model_data.get('variant_name', 'Unknown')
            xp_info = get_xp_to_next_class(variant_name)

            next_class = xp_info.get('next_class')
            if next_class:
                xp_remaining = xp_info.get('xp_remaining', 0)
                next_class_text = f"{next_class} ({xp_remaining:,} XP needed)"
            else:
                next_class_text = "Max Level Reached"
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Error loading next class: {e}")
            next_class_text = "No data yet"
        ttk.Label(parent, text=next_class_text, style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=10, pady=5)

    def _populate_skills_tab(self, parent, model_data: dict):
        """Populate Skills tab with actual skills from profile."""
        # Create scrollable frame
        canvas = tk.Canvas(parent, bg='#1e1e1e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load actual skills from profile
        try:
            from config import get_model_skills
            variant_name = model_data.get('variant_name', 'Unknown')
            skills_data = get_model_skills(variant_name)

            ttk.Label(scrollable_frame, text="Skills:", font=("Arial", 10, "bold"), style='Config.TLabel').pack(anchor=tk.W, padx=10, pady=5)

            if skills_data:
                for skill_name, skill_info in skills_data.items():
                    status = skill_info.get('status', 'Unverified')
                    marker = "✓" if status == "Verified" else "?" if status == "Unverified" else "✗"
                    color = "#51cf66" if status == "Verified" else "#ffd43b" if status == "Unverified" else "#ff6b6b"
                    row = ttk.Frame(scrollable_frame)
                    row.pack(fill=tk.X, padx=10, pady=2)
                    ttk.Label(row, text=f"{marker} {skill_name}", foreground=color, style='Config.TLabel').pack(side=tk.LEFT)
            else:
                ttk.Label(scrollable_frame, text="(No skills evaluated yet)", style='Config.TLabel').pack(anchor=tk.W, padx=10, pady=5)
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Error loading skills for Skills tab: {e}")
            ttk.Label(scrollable_frame, text="Skills:", font=("Arial", 10, "bold"), style='Config.TLabel').pack(anchor=tk.W, padx=10, pady=5)
            ttk.Label(scrollable_frame, text="(Error loading skills)", style='Config.TLabel').pack(anchor=tk.W, padx=10, pady=5)

    def _populate_class_tab(self, parent, model_data: dict):
        """Populate Class tab with training/evolution controls and promotion eligibility."""
        ttk.Label(parent, text="Class Progression", font=("Arial", 12, "bold"), style='Config.TLabel').pack(pady=10)

        # Check promotion eligibility
        variant_name = model_data.get('variant_name', 'Unknown')
        profile = model_data.get('profile', {})

        # Determine if model has any training/evaluation data
        has_stats = bool(profile.get('stats'))
        has_xp = profile.get('xp', 0) > 0 if isinstance(profile.get('xp'), int) else profile.get('xp', {}).get('total', 0) > 0
        class_level = profile.get('class_level', 'novice')

        # Show eligibility status
        eligibility_frame = ttk.LabelFrame(parent, text="Promotion Status", style='TLabelframe')
        eligibility_frame.pack(fill=tk.X, padx=10, pady=5)

        if not has_stats and not has_xp:
            status_text = "Not Eligible - No training or evaluation data"
            status_color = "#ff6b6b"  # Red
            ttk.Label(eligibility_frame, text=status_text, foreground=status_color, style='Config.TLabel').pack(pady=5)
            ttk.Label(eligibility_frame, text="Complete training sessions and evaluations to become eligible for promotion.",
                     wraplength=350, style='Config.TLabel').pack(pady=5)
        else:
            # Check actual eligibility using promotion system
            try:
                from xp_calculator import get_xp_to_next_class
                xp_info = get_xp_to_next_class(variant_name)

                if xp_info.get('next_class') is None:
                    status_text = f"Max Level ({class_level})"
                    status_color = "#ffd700"  # Gold
                else:
                    current_xp = xp_info.get('current_xp', 0)
                    xp_required = xp_info.get('xp_required', 0)
                    progress = xp_info.get('progress_percent', 0.0)

                    if progress >= 100.0:
                        status_text = f"Ready for Promotion to {xp_info.get('next_class')}"
                        status_color = "#51cf66"  # Green
                    else:
                        status_text = f"In Progress ({progress:.1f}%)"
                        status_color = "#ffa94d"  # Orange

                ttk.Label(eligibility_frame, text=status_text, foreground=status_color, style='Config.TLabel').pack(pady=5)
            except Exception as e:
                log_message(f"CHAT_INTERFACE: Error checking promotion eligibility: {e}")
                ttk.Label(eligibility_frame, text="Unable to determine eligibility", style='Config.TLabel').pack(pady=5)

        ttk.Label(parent, text="Training operations for this model:", style='Config.TLabel').pack(pady=5)

        # Disabled buttons with tooltips
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(pady=10)

        train_btn = ttk.Button(btn_frame, text="Train", state=tk.DISABLED, style='Action.TButton')
        train_btn.pack(pady=5, fill=tk.X)
        self._add_hover_tooltip(train_btn, "Training requires active session")

        levelup_btn = ttk.Button(btn_frame, text="Level Up", state=tk.DISABLED, style='Action.TButton')
        levelup_btn.pack(pady=5, fill=tk.X)
        self._add_hover_tooltip(levelup_btn, "Level up available after training")

        evolve_btn = ttk.Button(btn_frame, text="Evolve", state=tk.DISABLED, style='Action.TButton')
        evolve_btn.pack(pady=5, fill=tk.X)
        self._add_hover_tooltip(evolve_btn, "Evolution requires completion of class")

        revert_btn = ttk.Button(btn_frame, text="Revert", state=tk.DISABLED, style='Action.TButton')
        revert_btn.pack(pady=5, fill=tk.X)
        self._add_hover_tooltip(revert_btn, "Revert to previous checkpoint")

    def _populate_settings_tab(self, parent, model_data: dict):
        """Populate Quick-Settings tab with runtime parameters."""
        parent.columnconfigure(1, weight=1)

        row = 0

        # Store refs for callbacks
        _gpu_spinbox = None
        _layers_var = None

        # Device Selection (GPU/CPU/Auto)
        ttk.Label(parent, text="Device:", style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        device_frame = ttk.Frame(parent)
        device_frame.grid(row=row, column=1, sticky=tk.W, padx=10, pady=5)

        device_var = tk.StringVar(value="auto")
        ttk.Radiobutton(device_frame, text="GPU", variable=device_var, value="gpu", style='Config.TRadiobutton').pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(device_frame, text="CPU", variable=device_var, value="cpu", style='Config.TRadiobutton').pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(device_frame, text="Auto", variable=device_var, value="auto", style='Config.TRadiobutton').pack(side=tk.LEFT, padx=2)
        row += 1

        # Layer Allocation (Max/Med/Min/Auto)
        ttk.Label(parent, text="Layers:", style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        layers_frame = ttk.Frame(parent)
        layers_frame.grid(row=row, column=1, sticky=tk.W, padx=10, pady=5)

        layers_var = tk.StringVar(value="auto")
        _layers_var = layers_var
        ttk.Radiobutton(layers_frame, text="Max (35)", variable=layers_var, value="max", style='Config.TRadiobutton').pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(layers_frame, text="Med (25)", variable=layers_var, value="med", style='Config.TRadiobutton').pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(layers_frame, text="Min (10)", variable=layers_var, value="min", style='Config.TRadiobutton').pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(layers_frame, text="Auto", variable=layers_var, value="auto", style='Config.TRadiobutton').pack(side=tk.LEFT, padx=2)
        row += 1

        # GPU layers (manual control - only for llama_server)
        if model_data.get('is_local_gguf') or model_data.get('backend') == 'llama_server':
            ttk.Label(parent, text="GPU Layers:", style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
            gpu_spinbox = ttk.Spinbox(parent, from_=0, to=99, width=10)
            gpu_spinbox.grid(row=row, column=1, sticky=tk.W, padx=10, pady=5)
            gpu_spinbox.set("35")
            _gpu_spinbox = gpu_spinbox
            row += 1

        # Wire up device selection callbacks
        def _on_device_changed(*args):
            device = device_var.get()
            log_message(f"CHAT_INTERFACE: Device preference changed to: {device}")
            # CPU selection: force 0 layers
            if device == "cpu" and _gpu_spinbox:
                _gpu_spinbox.delete(0, tk.END)
                _gpu_spinbox.insert(0, "0")
                if _layers_var:
                    _layers_var.set("auto")
            # Note: GPU/Auto selections don't force backend - let router decide

        device_var.trace_add('write', _on_device_changed)

        # Wire up layer allocation callbacks
        def _on_layers_changed(*args):
            layers = layers_var.get()
            log_message(f"CHAT_INTERFACE: Layers preset changed to: {layers}")
            if _gpu_spinbox and device_var.get() != "cpu":
                if layers == "max":
                    _gpu_spinbox.delete(0, tk.END)
                    _gpu_spinbox.insert(0, "35")
                elif layers == "med":
                    _gpu_spinbox.delete(0, tk.END)
                    _gpu_spinbox.insert(0, "25")
                elif layers == "min":
                    _gpu_spinbox.delete(0, tk.END)
                    _gpu_spinbox.insert(0, "10")

        layers_var.trace_add('write', _on_layers_changed)

        # Context window
        ttk.Label(parent, text="Context:", style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        context_spinbox = ttk.Spinbox(parent, from_=512, to=32768, width=10, increment=512)
        context_spinbox.grid(row=row, column=1, sticky=tk.W, padx=10, pady=5)
        context_spinbox.set("4096")

    def _add_hover_tooltip(self, widget, text):
        """Add simple hover tooltip to widget."""
        def on_enter(e):
            widget.configure(cursor="hand2")
        def on_leave(e):
            widget.configure(cursor="")
        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)
        # Note: Full tooltip implementation would require a label overlay

    def set_active_model(self, model_data: dict):
        """
        Public API to set active model.
        Called directly from popup buttons or double-click handlers.

        Args:
            model_data: Dictionary containing model information
                - tag/id: Model identifier for Ollama tags
                - gguf_path/path: File path for local GGUF files
                - is_local_gguf/model_type: Boolean or string indicating local GGUF

        Returns:
            bool: True if model was set successfully, False otherwise
        """
        try:
            log_message(f"CHAT_INTERFACE: set_active_model called with: {model_data}")
            from pathlib import Path

            # Extract model name and path (if GGUF)
            gguf_path = model_data.get('gguf_path') or model_data.get('path') or ''
            model_name = model_data.get('model_name') or model_data.get('tag') or model_data.get('id') or Path(gguf_path or 'Unknown').name
            is_local = bool(model_data.get('is_local_gguf')) or str(model_data.get('model_type','')).lower() == 'local_gguf'

            log_message(f"CHAT_INTERFACE: Setting active model: {model_name} (local={is_local})")

            # Set backend based on explicit hint only; otherwise preserve current
            backend_hint = model_data.get('backend')
            if backend_hint in ('llama_server', 'ollama'):
                self._set_chat_backend(backend_hint)
                log_message(f"CHAT_INTERFACE: Backend set by hint → {backend_hint}")
            else:
                # If clearly a local GGUF selection or a name that contains 'gguf', prefer llama_server
                name_l = (model_name or '').lower()
                if is_local or name_l.endswith('.gguf') or 'gguf' in name_l:
                    self._set_chat_backend('llama_server')
                    log_message("CHAT_INTERFACE: Backend set to llama_server (heuristic for GGUF)")
                else:
                    # Preserve current backend to avoid surprising auto‑switches
                    try:
                        log_message(f"CHAT_INTERFACE: AUTO_BACKEND: preserved existing backend → {getattr(self, 'current_backend', 'unknown')}")
                    except Exception:
                        pass

            # Persist absolute GGUF path for mounting (never fall back)
            try:
                from pathlib import Path as _P
                p = _P(gguf_path) if gguf_path else None
                self.current_model_path = str(p.resolve()) if p and p.exists() else None
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"CHAT_INTERFACE: current_model_path -> {self.current_model_path}")
            except Exception:
                self.current_model_path = None

            # Use the existing set_model() method which handles all proper logic:
            # - Updates current_model
            # - Sets label with class color via _set_model_label_with_class_color()
            # - Updates mount button style
            # - Handles conversation history switching
            # - Disables send/dismount buttons
            self.set_model(model_name)
            log_message(f"CHAT_INTERFACE: Model '{model_name}' set as active via set_model()")

            return True
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Error in set_active_model: {e}")
            return False

    def _set_active_from_popup(self, model_data: dict, popup):
        """Set model as active from popup - calls public set_active_model() API."""
        try:
            log_message(f"CHAT_INTERFACE: _set_active_from_popup called")
            # Use the public API to set active model
            success = self.set_active_model(model_data)
            if success:
                popup.destroy()
                log_message(f"CHAT_INTERFACE: Set-Active completed successfully")
            else:
                log_message(f"CHAT_INTERFACE: Set-Active failed")
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Error in _set_active_from_popup: {e}")

    def _quick_mount_from_popup(self, model_data: dict, popup):
        """Quick mount model from popup - calls public set_active_model() then mounts."""
        try:
            log_message(f"CHAT_INTERFACE: _quick_mount_from_popup called")
            # Use the public API to set active model
            success = self.set_active_model(model_data)
            if success:
                popup.destroy()
                # Mount after brief delay to allow UI to update
                self.root.after(50, self.mount_model)
                log_message(f"CHAT_INTERFACE: Quick-Mount completed successfully, mounting...")
            else:
                log_message(f"CHAT_INTERFACE: Quick-Mount failed - could not set active model")
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Error in _quick_mount_from_popup: {e}")

    def _check_status_from_popup(self, model_data: dict, popup):
        """Check model status from popup - displays system capabilities and model info."""
        try:
            log_message(f"CHAT_INTERFACE: _check_status_from_popup called with: {model_data}")
            # Query router for status
            from tabs.custom_code_tab import router, capabilities
            caps = capabilities.detect_capabilities()

            # Build status message
            model_name = model_data.get('model_name') or model_data.get('tag') or model_data.get('id', 'Unknown')
            status_msg = f"Model: {model_name}\n"
            status_msg += f"Backend: {model_data.get('backend', 'N/A')}\n"
            status_msg += f"GPU Available: {len(caps.get('gpus', [])) > 0}\n"
            status_msg += f"Ollama: {caps.get('servers', {}).get('ollama', {}).get('available', False)}\n"
            status_msg += f"llama-server: {caps.get('servers', {}).get('llama_server', {}).get('available', False)}"

            log_message(f"CHAT_INTERFACE: Status check - {status_msg.replace(chr(10), ' | ')}")

            from tkinter import messagebox
            messagebox.showinfo("Model Status", status_msg, parent=popup)
            log_message(f"CHAT_INTERFACE: Check-Status completed successfully")
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Error in _check_status_from_popup: {e}")

    def _on_tracker_close(self):
        log_message("CHAT_INTERFACE: _on_tracker_close called.")
        if not self.is_tracker_active: # Prevent re-entry
            log_message("CHAT_INTERFACE: _on_tracker_close returning early (inactive).")
            return

        if self._tracker_after_id:
            log_message("CHAT_INTERFACE: Cancelling _tracker_after_id.")
            self.root.after_cancel(self._tracker_after_id)
            self._tracker_after_id = None
        
        self.is_tracker_active = False # Set state to inactive first
        log_message("CHAT_INTERFACE: Tracker window state set to inactive.")
        log_message(f"CHAT_INTERFACE: tracker_window exists: {self.tracker_window is not None and self.tracker_window.winfo_exists()}")
        log_message(f"CHAT_INTERFACE: main_pane exists: {hasattr(self, 'main_pane') and self.main_pane.winfo_exists()}")
        log_message(f"CHAT_INTERFACE: main_pane sash exists: {hasattr(self, 'main_pane') and self.main_pane.winfo_exists()}")

        # Save main_pane sash position
        if hasattr(self, 'main_pane') and self.main_pane.winfo_exists():
            sash_pos = self.main_pane.sashpos(0)
            self._save_backend_setting('tracker_sash_position', sash_pos)
            log_message(f"CHAT_INTERFACE: Saved tracker_sash_position: {sash_pos}")
        else:
            log_message("CHAT_INTERFACE: main_pane not found or sash not exists, skipping sash position save.")

        if self.tracker_window and self.tracker_window.winfo_exists():
            log_message(f"CHAT_INTERFACE: _on_tracker_close called for window ID: {self.tracker_window.winfo_id()}")
            log_message("CHAT_INTERFACE: Attempting to destroy tracker_window.")
            try:
                self.tracker_window.destroy()
                log_message("CHAT_INTERFACE: tracker_window.destroy() called successfully.")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to destroy tracker_window: {e}")
        else:
            log_message("CHAT_INTERFACE: tracker_window not found or not exists.")
        
        self.tracker_window = None
        self._update_quick_indicators()
        log_message("CHAT_INTERFACE: Tracker window closed.")

    def create_tracker_window(self):
        log_message("CHAT_INTERFACE: create_tracker_window called.")
        if self.is_tracker_active and self.tracker_window and self.tracker_window.winfo_exists():
            log_message("CHAT_INTERFACE: Tracker window already active, lifting it.")
            self.tracker_window.lift()
            return

        log_message("CHAT_INTERFACE: Creating Toplevel window.")
        win = tk.Toplevel(self.root)
        win.title("Tracker")
        # Apply saved geometry if locked
        if self.tracker_window_locked and self._locked_tracker_geometry:
            win.geometry(self._locked_tracker_geometry)
            log_message(f"CHAT_INTERFACE: Applying locked geometry: {self._locked_tracker_geometry}")
        else:
            win.geometry("400x600")
        win.transient(self.root)
        win.protocol("WM_DELETE_WINDOW", self._on_tracker_close)
        self.tracker_window = win
        log_message(f"CHAT_INTERFACE: Toplevel window created and configured. ID: {win.winfo_id()}")

        self.is_tracker_active = True
        self._update_quick_indicators()
        log_message("CHAT_INTERFACE: Tracker window opened.")

        log_message("CHAT_INTERFACE: Creating main_pane...")
        # Main layout with horizontal paned window
        main_pane = ttk.PanedWindow(win, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True)
        self.main_pane = main_pane # Store reference for sash manipulation
        log_message("CHAT_INTERFACE: main_pane created.")

        log_message("CHAT_INTERFACE: Creating left_frame and right_frame...")
        # Left frame for Nest and Files
        left_frame = ttk.Frame(main_pane, padding=5)
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(1, weight=1) # Give weight to the nest_labelframe
        left_frame.rowconfigure(2, weight=1) # Give weight to the files_frame

        # Right frame for Thoughts
        right_frame = ttk.Frame(main_pane, padding=5)
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)

        main_pane.add(left_frame, weight=2)
        main_pane.add(right_frame, weight=1)
        log_message("CHAT_INTERFACE: left_frame and right_frame added to main_pane.")

        log_message("CHAT_INTERFACE: Applying sash position...")
        # Load and apply sash position
        if self.tracker_window_locked:
            saved_sash_pos = self.backend_settings.get('tracker_sash_position_locked', None)
            log_message(f"CHAT_INTERFACE: Locked sash position found: {saved_sash_pos}. Applying...")
        else:
            saved_sash_pos = self.backend_settings.get('tracker_sash_position', None)
            log_message(f"CHAT_INTERFACE: Unlocked sash position found: {saved_sash_pos}. Applying...")

        if saved_sash_pos is not None:
            # Apply after window is drawn to ensure correct sizing
            win.after(100, lambda: main_pane.sashpos(0, saved_sash_pos))
        else:
            log_message("CHAT_INTERFACE: No saved sash position found. Applying default.")
            # Default split: 2/3 for left, 1/3 for right
            win.update_idletasks() # Ensure window geometry is updated
            win.after(100, lambda: main_pane.sashpos(0, int(win.winfo_width() * 0.66)))
        log_message("CHAT_INTERFACE: Sash position application scheduled.")

        log_message("CHAT_INTERFACE: Creating Left Pane Widgets...")
        # --- Left Pane Widgets ---

        # Top controls frame for features/functions
        top_controls_frame = ttk.Frame(left_frame, padding=2)
        top_controls_frame.grid(row=0, column=0, sticky="ew")
        top_controls_frame.columnconfigure(0, weight=1) # For potential future elements
        log_message("CHAT_INTERFACE: top_controls_frame created.")

        # Lock button for window size
        self.lock_button = ttk.Button(top_controls_frame, text="", command=self._toggle_tracker_window_lock, style='Toolbutton')
        self.lock_button.grid(row=0, column=1, sticky="e", padx=5)
        log_message("CHAT_INTERFACE: Lock button created.")

        # Store initial window geometry
        win.update_idletasks()
        self._initial_tracker_geometry = win.geometry()
        log_message(f"CHAT_INTERFACE: Initial tracker window geometry: {self._initial_tracker_geometry}")

        # Apply initial lock state
        self._update_lock_button_icon()
        if self.tracker_window_locked:
            win.resizable(False, False)
            log_message("CHAT_INTERFACE: Window set to not resizable.")
        else:
            win.resizable(True, True)
            log_message("CHAT_INTERFACE: Window set to resizable.")

        # Active Model Nest (Top)
        nest_labelframe = ttk.LabelFrame(left_frame, text="Active Model")
        nest_labelframe.grid(row=1, column=0, sticky="ew", pady=(0,5))
        nest_labelframe.columnconfigure(0, weight=1)
        self.tracker_nest_canvas = tk.Canvas(nest_labelframe, height=60, bg='#1e1e1e', highlightthickness=0)
        self.tracker_nest_canvas.grid(row=0, column=0, sticky="ew")
        log_message("CHAT_INTERFACE: nest_labelframe and canvas created.")

        # File Grid (Bottom)
        files_frame = ttk.Frame(left_frame)
        files_frame.grid(row=2, column=0, sticky="nsew")
        files_frame.columnconfigure(0, weight=1)
        files_frame.rowconfigure(1, weight=1)

        self.tracker_dir_label = ttk.Label(files_frame, text="Loading...", font=("Arial", 9, "italic"), anchor="w")
        self.tracker_dir_label.grid(row=0, column=0, sticky=tk.EW, pady=(0, 5))

        canvas = tk.Canvas(files_frame, bg='#1e1e1e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(files_frame, orient="vertical", command=canvas.yview)
        self.tracker_files_frame = ttk.Frame(canvas, style='Category.TFrame')

        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=1, column=0, sticky='nsew')
        scrollbar.grid(row=1, column=1, sticky='ns')
        canvas_window = canvas.create_window((0, 0), window=self.tracker_files_frame, anchor="nw")

        def on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        self.tracker_files_frame.bind("<Configure>", on_frame_configure)

        def on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", on_canvas_configure)
        log_message("CHAT_INTERFACE: files_frame and its components created.")

        log_message("CHAT_INTERFACE: Creating Right Pane Widgets...")
        # --- Right Pane Widgets ---

        # Thoughts Panel
        thoughts_labelframe = ttk.LabelFrame(right_frame, text="Thoughts")
        thoughts_labelframe.grid(row=0, column=0, sticky="nsew")
        thoughts_labelframe.columnconfigure(0, weight=1)
        thoughts_labelframe.rowconfigure(0, weight=1)
        self.tracker_thoughts_text = scrolledtext.ScrolledText(thoughts_labelframe, state=tk.DISABLED, wrap=tk.WORD, font=("Arial", 9), bg='#1e1e1e', fg='#dcdcdc')
        self.tracker_thoughts_text.grid(row=0, column=0, sticky="nsew")
        log_message("CHAT_INTERFACE: thoughts_labelframe and text widget created.")

        self.tracker_file_widgets = {}
        log_message("CHAT_INTERFACE: Calling refresh_tracker_display from create_tracker_window.")
        self.refresh_tracker_display()
        log_message("CHAT_INTERFACE: create_tracker_window finished.")

    def refresh_tracker_display(self):
        log_message("CHAT_INTERFACE: refresh_tracker_display called.")
        if not self.is_tracker_active or not self.tracker_window or not self.tracker_window.winfo_exists():
            if self._tracker_after_id:
                self.root.after_cancel(self._tracker_after_id)
                self._tracker_after_id = None
            log_message("CHAT_INTERFACE: refresh_tracker_display returning early (inactive or window not exists).")
            return

        try:
            if self.tool_executor:
                current_dir = self.tool_executor.get_working_directory()
            else:
                current_dir = self.backend_settings.get('working_directory', '.')
            log_message(f"CHAT_INTERFACE: Watching directory: {current_dir}")
            
            self.tracker_dir_label.config(text=f"Watching: {current_dir}")

            # Use `ls -lp --full-time` to get file details
            log_message("CHAT_INTERFACE: Calling subprocess.run for ls...")
            result = subprocess.run(['ls', '-lp', '--full-time', current_dir], capture_output=True, text=True, check=True)
            lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
            log_message("CHAT_INTERFACE: subprocess.run completed.")

            # Clear previous grid
            for widget in self.tracker_files_frame.winfo_children():
                widget.destroy()
            self.tracker_file_widgets.clear()

            # Grid configuration
            max_cols = 4
            col = 0
            row = 0

            # Loop to create a grid of icon-only frames
            if len(lines) > 1:
                for line in lines[1:]: # Skip total line
                    if not line: continue
                    parts = line.split()
                    if len(parts) < 9: continue

                    perms, _, owner, group, size, month, day, time, name = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], parts[6], parts[7], " ".join(parts[8:])
                    
                    is_dir = perms.startswith('d')
                    display_name = name.rstrip('/')
                    full_path = str(Path(current_dir) / display_name)

                    item_frame = ttk.Frame(self.tracker_files_frame, width=80, height=80)
                    item_frame.grid(row=row, column=col, padx=5, pady=5)
                    item_frame.pack_propagate(False)
                    self.tracker_file_widgets[full_path] = item_frame


                    icon = "📁" if is_dir else "📄"
                    icon_label = ttk.Label(item_frame, text=icon, font=("Arial", 24))
                    icon_label.pack(expand=True)

                    # Create tooltip text with name, size, date
                    details = f"Name: {display_name}\nSize: {size} bytes\nModified: {month} {day} {time}"

                    # Bind hover and double-click events
                    icon_label.bind("<Enter>", lambda e, t=details, w=item_frame: self._show_tooltip(w, t))
                    icon_label.bind("<Leave>", lambda e: self._hide_tooltip())
                    if not is_dir:
                        icon_label.bind("<Double-1>", lambda e, p=full_path: self.open_file_viewer(p))


                    col += 1
                    if col >= max_cols:
                        col = 0
                        row += 1
            log_message("CHAT_INTERFACE: File icons created.")

        except Exception as e:
            log_message(f"CHAT_INTERFACE ERROR in refresh_tracker_display: {e}")
            # Clear previous grid
            for widget in self.tracker_files_frame.winfo_children():
                widget.destroy()
            error_label = ttk.Label(self.tracker_files_frame, text=f"Error: {e}", foreground="red", wraplength=280)
            error_label.pack()

        self._tracker_after_id = self.root.after(2500, self.refresh_tracker_display)
        log_message("CHAT_INTERFACE: refresh_tracker_display scheduled next update.")

    def _show_tooltip(self, widget, text):
        if hasattr(self, '_tooltip_win') and self._tooltip_win:
            self._hide_tooltip()

        x, y, _, _ = widget.bbox("insert")
        x += widget.winfo_rootx() + 25
        y += widget.winfo_rooty() + 25

        self._tooltip_win = tw = tk.Toplevel(self.root)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        label = ttk.Label(tw, text=text, justify=tk.LEFT,
                         background="#333333", foreground="white", relief=tk.SOLID, borderwidth=1,
                         font=("Arial", 9, "normal"), padding=4)
        label.pack(ipadx=1)
        self._tooltip_active = True

    def _hide_tooltip(self):
        if hasattr(self, '_tooltip_win') and self._tooltip_win:
            self._tooltip_win.destroy()
        self._tooltip_win = None
        self._tooltip_active = False

    def _start_core_animation(self):
        if hasattr(self, '_core_animation_job') and self._core_animation_job:
            self.root.after_cancel(self._core_animation_job)

        self._core_current_radius = 10
        self._core_pulse_direction = 1
        # Introduce a small delay to allow the canvas to render and get its dimensions
        self.root.after(100, self._pulse_core)
    def _stop_core_animation(self):
        if hasattr(self, '_core_animation_job') and self._core_animation_job:
            self.root.after_cancel(self._core_animation_job)
            self._core_animation_job = None
        if hasattr(self, 'tracker_nest_canvas') and self.tracker_nest_canvas:
            self.tracker_nest_canvas.delete("core")

    def _pulse_core(self):
        if not hasattr(self, 'tracker_nest_canvas') or not self.tracker_nest_canvas or not self.tracker_nest_canvas.winfo_exists():
            return

        canvas = self.tracker_nest_canvas

        # Calculate radius for pulsing effect
        if self._core_current_radius > 20:
            self._core_pulse_direction = -1
        elif self._core_current_radius < 10:
            self._core_pulse_direction = 1
        self._core_current_radius += self._core_pulse_direction

        # Calculate color based on radius
        hue = 0.55  # Cyan
        saturation = 0.8
        value = self._core_current_radius / 25.0 + 0.2
        try:
            import colorsys
            r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
            color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
        except ImportError:
            color = "#00FFFF"  # Fallback color

        canvas.delete("core")
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width > 1 and height > 1:
            x0 = width/2 - self._core_current_radius
            y0 = height/2 - self._core_current_radius
            x1 = width/2 + self._core_current_radius
            y1 = height/2 + self._core_current_radius
            canvas.create_oval(x0, y0, x1, y1, fill=color, outline=color, tags="core")

        self._core_animation_job = self.root.after(self._core_pulse_speed, self._pulse_core)

    def _animate_energy_arc(self, target_file_path):
        if not self.is_tracker_active or not self.tracker_window or not self.tracker_window.winfo_exists():
            return
        
        target_widget = self.tracker_file_widgets.get(target_file_path)
        if not target_widget:
            return

        # 1. Flash the target widget
        try:
            original_style = target_widget.cget("style")
            flash_style = "Flash.TFrame"
            self.style.configure(flash_style, background="#61dafb")
            target_widget.configure(style=flash_style)
            self.root.after(500, lambda: target_widget.configure(style=original_style))
        except tk.TclError: # Style may already exist
            try:
                target_widget.configure(style=flash_style)
                self.root.after(500, lambda: target_widget.configure(style=original_style))
            except Exception: # Failsafe
                pass

        # 2. Draw a bolt on the nest canvas
        canvas = self.tracker_nest_canvas
        if not canvas or not canvas.winfo_exists():
            return
            
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        
        if width <= 1 or height <= 1:
            return

        x_start, y_start = width / 2, height / 2
        
        # Simplified bolt shooting upwards
        bolt_points = [
            x_start, y_start,
            x_start + random.randint(-5, 5), y_start - 10,
            x_start + random.randint(-5, 5), y_start - 20,
            x_start + random.randint(-5, 5), y_start - 30,
            x_start, y_start - 40
        ]
        
        bolt = canvas.create_line(bolt_points, fill="#61dafb", width=2, tags="bolt")
        
        def clear_bolt():
            if canvas.winfo_exists():
                canvas.delete(bolt)
        
        self.root.after(300, clear_bolt)

    def _update_lock_button_icon(self):
        if self.tracker_window_locked:
            self.lock_button.config(text="🔒")
        else:
            self.lock_button.config(text="🔓")

    def _toggle_tracker_window_lock(self):
        if not self.tracker_window or not self.tracker_window.winfo_exists():
            return

        self.tracker_window_locked = not self.tracker_window_locked
        self._update_lock_button_icon()

        if self.tracker_window_locked:
            # Save current (unlocked) geometry and sash position before locking
            self._unlocked_tracker_sash_position = self.main_pane.sashpos(0)
            self._save_backend_setting('tracker_sash_position', self._unlocked_tracker_sash_position)
            log_message(f"CHAT_INTERFACE: Saved unlocked sash position: {self._unlocked_tracker_sash_position}")

            # Apply locked state
            self._locked_tracker_geometry = self.tracker_window.geometry()
            self._save_backend_setting('locked_tracker_geometry', self._locked_tracker_geometry)
            self.tracker_window.resizable(False, False)
            # Adjust sash to give more space to thoughts pane when locked
            self.main_pane.sashpos(0, int(self.tracker_window.winfo_width() * 0.5))
            self._save_backend_setting('tracker_sash_position_locked', self.main_pane.sashpos(0))
            log_message(f"CHAT_INTERFACE: Saved locked tracker geometry: {self._locked_tracker_geometry}")
            log_message(f"CHAT_INTERFACE: Set locked sash position: {self.main_pane.sashpos(0)}")
        else:
            # Apply unlocked state
            self.tracker_window.resizable(True, True)
            # Restore unlocked sash position
            if self._unlocked_tracker_sash_position is not None:
                self.main_pane.sashpos(0, self._unlocked_tracker_sash_position)
                log_message(f"CHAT_INTERFACE: Restored unlocked sash position: {self._unlocked_tracker_sash_position}")
            # Restore geometry if it was previously locked
            if self._locked_tracker_geometry:
                self.tracker_window.geometry(self._locked_tracker_geometry)
                log_message(f"CHAT_INTERFACE: Restored locked geometry: {self._locked_tracker_geometry}")

        # Persist lock state
        self._save_backend_setting('tracker_window_locked', self.tracker_window_locked)

    def open_file_viewer(self, file_path):
        from default_api import read_file
        from tkinter import messagebox
        try:
            content_result = read_file(absolute_path=file_path)
            
            viewer_win = tk.Toplevel(self.root)
            viewer_win.title(f"View: {Path(file_path).name}")
            viewer_win.geometry("700x500")
            viewer_win.transient(self.root)

            txt = scrolledtext.ScrolledText(viewer_win, wrap=tk.WORD, font=("Courier", 10), bg='#1e1e1e', fg='#ffffff')
            txt.pack(fill=tk.BOTH, expand=True)
            
            file_content = content_result.get('read_file_response', {}).get('output', f"Could not read file: {file_path}")
            txt.insert(tk.END, file_content)
            txt.config(state=tk.DISABLED)

        except Exception as e:
            messagebox.showerror("Error", f"Could not open file viewer for {file_path}:\n{e}")

    def update_session_temp_label(self, value):
        self.session_temperature = round(float(value), 1)
        try:
            if getattr(self, 'session_temp_label', None):
                self.session_temp_label.config(text=f"Temp: {self.session_temperature:.1f}")
        except Exception:
            pass
        # Persist when manual mode
        if getattr(self, 'temp_mode', 'manual') == 'manual':
            try:
                self._save_backend_setting('temperature', float(self.session_temperature))
            except Exception:
                pass

    def create_ui(self):
        """Create the chat interface UI"""
        log_message("CHAT_INTERFACE: Creating UI...")

        # Use a PanedWindow to allow left conversations list and right chat area to be resizable
        pw = ttk.Panedwindow(self.parent, orient=tk.HORIZONTAL)
        pw.grid(row=0, column=0, sticky=tk.NSEW)
        self._chat_pane = pw
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)

        # Left: Conversations list sidebar
        self.conv_sidebar = ttk.Frame(pw, width=240, style='Category.TFrame')
        self.conv_sidebar.columnconfigure(0, weight=1)
        self.conv_sidebar.rowconfigure(1, weight=1)
        self._build_conversations_sidebar(self.conv_sidebar)

        # Right: Chat main container
        self.chat_container = ttk.Frame(pw, style='Category.TFrame')
        self.chat_container.columnconfigure(0, weight=1)
        self.chat_container.rowconfigure(1, weight=1)

        # Top controls in chat_container
        self.create_top_controls(self.chat_container)
        # Middle chat display
        self.create_chat_display(self.chat_container)

        # Simple text-based progress indicator at bottom of chat panel
        self.progress_frame = tk.Frame(self.chat_container, bg='#1e1e1e', height=20)
        self.progress_frame.grid(row=2, column=0, sticky=tk.EW, padx=0, pady=0)
        self.progress_frame.grid_remove()  # Start hidden

        self.progress_label = tk.Label(
            self.progress_frame,
            text="",
            bg='#1e1e1e',
            fg='#00ff00',
            font=('Courier New', 9),
            anchor='w',
            padx=10,
            pady=2
        )
        self.progress_label.pack(fill=tk.X)

        # Legacy compatibility
        self.progress_bar_widget = None
        log_message("CHAT_INTERFACE: Compact text progress indicator initialized")

        # Bottom input
        self.create_input_area(self.chat_container)

        pw.add(self.conv_sidebar, weight=0)
        pw.add(self.chat_container, weight=1)
        try:
            pw.paneconfigure(self.conv_sidebar, minsize=160)
            pw.paneconfigure(self.chat_container, minsize=400)
        except Exception:
            pass
        # Default sidebar width ~240px or last saved width
        try:
            def _set_inner_sash():
                try:
                    self.parent.update_idletasks()
                    try:
                        w = int(self.backend_settings.get('conv_width', 240))
                    except Exception:
                        w = 240
                    self._chat_pane.sashpos(0, max(160, min(360, w)))
                except Exception:
                    pass
            self.root.after(50, _set_inner_sash)
        except Exception:
            pass
        # Keep locked width on parent resizes
        pw.bind('<Configure>', self._enforce_conv_width)
        # Apply initial lock behavior (disable drag + arrow when locked)
        self._apply_conv_lock_state()

        log_message("CHAT_INTERFACE: UI created successfully")
        # Listen for training lifecycle to show simple status popups
        try:
            self.root.bind("<<TrainingSessionStarted>>", self._on_training_started)
            self.root.bind("<<TrainingSessionComplete>>", self._on_training_complete)
            self.root.bind("<<TrainingProgressUpdate>>", self._on_training_progress)
        except Exception:
            pass

        # Align initial Training Mode/Support state from backend defaults
        try:
            default_tm = bool(self.backend_settings.get('training_mode_enabled', False))
            self.set_training_mode(default_tm)
        except Exception:
            pass
        try:
            self._qa_update_training_btn()
            self._update_quick_indicators()
        except Exception:
            pass

    def create_top_controls(self, parent):
        """Create top control bar with model info and actions"""
        controls_frame = ttk.Frame(parent, style='Category.TFrame')
        controls_frame.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=(10, 5))
        controls_frame.columnconfigure(1, weight=1)

        # Model label
        ttk.Label(
            controls_frame,
            text="Active Model:",
            style='Config.TLabel',
            font=("Arial", 10, "bold")
        ).grid(row=0, column=0, sticky=tk.W, padx=(5, 10))

        # Model name display (with color indicator for mount status)
        self.model_label = tk.Label(
            controls_frame,
            text="No model selected",
            font=("Arial", 10),
            bg='#2b2b2b',
            fg='#ffffff'
        )
        self.model_label.grid(row=0, column=1, sticky=tk.W, padx=(0, 10))

        # Temperature controls moved to Quick Actions; header indicators removed.
        self.session_temp_label = None
        self.session_temperature_var = tk.DoubleVar(value=self.backend_settings.get('temperature', 0.8))
        self.session_temp_scale = None

        # (Prompt/Schema, Change Dir and Mode moved to Quick Actions gear)
        # Top action buttons (Mount/Dismount/New Chat/Delete Chat) + Quick Actions + indicators
        # Place inside the controls row so they're vertically centered between borders
        top_actions = ttk.Frame(controls_frame, style='Category.TFrame')
        top_actions.grid(row=0, column=4, sticky=tk.E, padx=(0, 10))
        self.mount_btn = ttk.Button(top_actions, text="📌 Mount", command=self.mount_model, style='Action.TButton', state=tk.DISABLED)
        self.mount_btn.pack(side=tk.LEFT, padx=(0,5))
        self.dismount_btn = ttk.Button(top_actions, text="📍 Dismount", command=self.dismount_model, style='Select.TButton', state=tk.DISABLED)
        self.dismount_btn.pack(side=tk.LEFT, padx=(0,5))
        ttk.Button(top_actions, text="🛑 Kill All", command=self.kill_all_servers, style='Select.TButton').pack(side=tk.LEFT, padx=(0,5))
        ttk.Button(top_actions, text="🆕 New Chat", command=self.new_chat, style='Action.TButton').pack(side=tk.LEFT, padx=(0,5))
        ttk.Button(top_actions, text="🗑 Delete Chat", command=self.delete_current_chat, style='Select.TButton').pack(side=tk.LEFT, padx=(0,5))

    def open_todo_list(self):
        """Open the Settings tab ToDo popup from Quick Actions.

        - If a project with existing per-project todos is selected (Projects panel),
          open the Project ToDo view by default with toggle buttons visible.
        - Otherwise, open the Main ToDo view.
        """
        try:
            # Access settings tab instance via parent_tab.tab_instances
            tab_map = getattr(self.parent_tab, 'tab_instances', None)
            if not tab_map and hasattr(self.parent_tab, 'parent'):
                tab_map = getattr(self.parent_tab.parent, 'tab_instances', None)
            settings_meta = None
            if isinstance(tab_map, dict):
                settings_meta = tab_map.get('settings_tab')
            settings_inst = settings_meta.get('instance') if settings_meta else None
            if not (settings_inst and hasattr(settings_inst, 'show_todo_popup')):
                from tkinter import messagebox
                messagebox.showinfo("ToDo List", "Settings tab is not available.")
                return

            # If a project is selected (Projects panel), open its Project ToDo first
            project_name = getattr(self, 'current_project', None)
            if project_name:
                settings_inst.show_project_todo_popup(project_name)
            else:
                settings_inst.show_todo_popup()
        except Exception:
            try:
                from tkinter import messagebox
                messagebox.showerror("ToDo Error", "Failed to open ToDo list.")
            except Exception:
                pass

    def open_temp_mode_selector(self):
        try:
            win = tk.Toplevel(self.root)
            win.title('Temperature Mode')
            win.resizable(False, False)
            container = ttk.Frame(win, padding=8)
            container.pack(fill=tk.BOTH, expand=True)

            body = ttk.Frame(container)
            body.pack(fill=tk.BOTH, expand=True)

            def show_select():
                for w in body.winfo_children():
                    w.destroy()
                ttk.Label(body, text='Select Temperature Mode', style='CategoryPanel.TLabel').grid(row=0, column=0, columnspan=2, pady=(0,6))
                ttk.Button(body, text='Manual', style='Action.TButton', command=show_manual).grid(row=1, column=0, padx=6, pady=6, sticky=tk.EW)
                def set_auto():
                    self.temp_mode = 'auto'
                    try:
                        self._save_backend_setting('temp_mode', 'auto')
                    except Exception:
                        pass
                    self._apply_temp_mode_visibility()
                    self._apply_auto_temperature_adjustment(source='mode_switch')
                    try:
                        self._update_quick_indicators()
                    except Exception:
                        pass
                    win.destroy()
                ttk.Button(body, text='Auto', style='Action.TButton', command=set_auto).grid(row=1, column=1, padx=6, pady=6, sticky=tk.EW)

            def show_manual():
                for w in body.winfo_children():
                    w.destroy()
                ttk.Label(body, text='Manual Temperature', style='CategoryPanel.TLabel').grid(row=0, column=0, columnspan=2, pady=(0,6))
                # Slider
                temp_var = tk.DoubleVar(value=float(self.session_temperature))
                scale = ttk.Scale(body, from_=0.0, to=2.0, orient=tk.HORIZONTAL, variable=temp_var, length=220)
                scale.grid(row=1, column=0, columnspan=2, sticky=tk.EW, padx=6, pady=6)
                val_lbl = ttk.Label(body, text=f"{float(self.session_temperature):.1f}", style='Config.TLabel')
                val_lbl.grid(row=2, column=0, sticky=tk.W, padx=6)
                def on_change(_=None):
                    try: val_lbl.config(text=f"{float(temp_var.get()):.1f}")
                    except Exception: pass
                try:
                    scale.configure(command=lambda v: on_change())
                except Exception:
                    pass
                # Buttons
                def apply_manual():
                    try:
                        self.temp_mode = 'manual'
                        self.session_temperature = round(float(temp_var.get()), 1)
                        self.session_temperature_var.set(self.session_temperature)
                        try:
                            label = getattr(self, 'session_temp_label', None)
                            if label:
                                label.config(text=f"Temp: {self.session_temperature:.1f}")
                        except Exception:
                            pass
                        self._save_backend_setting('temp_mode', 'manual')
                        self._save_backend_setting('temperature', float(self.session_temperature))
                        try:
                            self._update_quick_indicators()
                        except Exception:
                            pass
                    except Exception:
                        pass
                    win.destroy()
                ttk.Button(body, text='Set Temp', style='Action.TButton', command=apply_manual).grid(row=3, column=0, padx=6, pady=6, sticky=tk.W)
                ttk.Button(body, text='Back', style='Select.TButton', command=show_select).grid(row=3, column=1, padx=6, pady=6, sticky=tk.E)

            show_select()
            try:
                win.transient(self.root); win.lift(); win.attributes('-topmost', True); self.root.after(300, lambda: win.attributes('-topmost', False))
            except Exception:
                pass
        except Exception:
            pass

    def _apply_temp_mode_visibility(self):
        try:
            # Always hide header slider; we use popup for manual
            if hasattr(self, 'session_temp_scale') and self.session_temp_scale:
                try:
                    self.session_temp_scale.grid_remove()
                except Exception:
                    pass
        except Exception:
            pass

    def _apply_auto_temperature_adjustment(self, source='auto'):
        try:
            if getattr(self, 'temp_mode', 'manual') != 'auto':
                return
            model = (self.current_model or '').strip()
            success = 0; failure = 0
            stats = self.realtime_eval_scores.get(model, {}) if hasattr(self, 'realtime_eval_scores') else {}
            for s in stats.values():
                success += int(s.get('success', 0)); failure += int(s.get('failure', 0))
            total = success + failure
            rec = 0.8
            if total >= 5:
                ratio = success / max(1, total)
                if ratio < 0.5:
                    rec = 0.4
                elif ratio < 0.7:
                    rec = 0.6
                elif ratio > 0.85:
                    rec = 1.0
                else:
                    rec = 0.8
            self.session_temperature = round(rec, 1)
            try:
                self.session_temperature_var.set(self.session_temperature)
            except Exception:
                pass
            try:
                label = getattr(self, 'session_temp_label', None)
                if label:
                    label.config(text=f"Temp: {self.session_temperature:.1f}")
            except Exception:
                pass
            log_message(f"CHAT_INTERFACE: Auto temperature set to {self.session_temperature:.1f} (source={source}, stats={success}/{total})")
        except Exception:
            pass

    def create_chat_display(self, parent):
        """Create the chat message display area"""
        display_frame = ttk.Frame(parent, style='Category.TFrame')
        display_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=5)
        display_frame.columnconfigure(0, weight=1)
        display_frame.rowconfigure(0, weight=1)

        # Scrolled text widget for chat
        self.chat_display = scrolledtext.ScrolledText(
            display_frame,
            wrap=tk.WORD,
            font=("Arial", 10),
            state=tk.DISABLED,
            relief='flat',
            borderwidth=0,
            highlightthickness=1,
            highlightbackground='#454545',
            bg='#1e1e1e',
            fg='#ffffff',
            insertbackground='#61dafb'
        )
        self.chat_display.grid(row=0, column=0, sticky=tk.NSEW)
        # Thought tag for streaming preview
        try:
            self.chat_display.tag_config('thought', foreground='#bbbbbb', font=("Arial", 9, "italic"))
        except Exception:
            pass

    def _build_conversations_sidebar(self, parent):
        header = ttk.Frame(parent, style='Category.TFrame')
        header.grid(row=0, column=0, sticky=tk.EW, padx=8, pady=(8,4))
        ttk.Label(header, text='📚 Conversations', style='CategoryPanel.TLabel').pack(side=tk.LEFT)
        ttk.Button(header, text='↻', width=3, style='Select.TButton', command=self._refresh_conversations_list).pack(side=tk.RIGHT)
        self._conv_lock_btn = ttk.Button(header, text=('🔒' if self.backend_settings.get('conv_locked', False) else '🔓'), width=3, style='Select.TButton', command=self._toggle_conv_lock)
        self._conv_lock_btn.pack(side=tk.RIGHT, padx=(4,0))

        # Treeview + scrollbar (categorized by time)
        list_frame = ttk.Frame(parent, style='Category.TFrame')
        list_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=8, pady=(0,8))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        sb = ttk.Scrollbar(list_frame, orient='vertical')
        sb.grid(row=0, column=1, sticky=tk.NS)
        self.conv_tree = ttk.Treeview(list_frame, yscrollcommand=sb.set, selectmode='browse')
        self.conv_tree.grid(row=0, column=0, sticky=tk.NSEW)
        sb.config(command=self.conv_tree.yview)
        self.conv_tree.heading('#0', text='Structure')
        # Styling
        try:
            st = ttk.Style()
            st.configure('Treeview', background='#2b2b2b', fieldbackground='#2b2b2b', foreground='#ffffff')
            st.map('Treeview', background=[('selected','#3a3a3a')], foreground=[('selected','#61dafb')])
        except Exception:
            pass
        self.conv_tree.bind('<Double-Button-1>', self._on_open_selected_conversation)
        self.conv_tree.bind('<<TreeviewSelect>>', self._on_conv_selected)

        # Bottom action buttons
        actions = ttk.Frame(parent, style='Category.TFrame')
        actions.grid(row=2, column=0, sticky=tk.EW, padx=8, pady=(0,4))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        ttk.Button(actions, text='Open Chat', style='Action.TButton', command=self._open_selected_chat).grid(row=0, column=0, sticky=tk.EW, padx=(0,4))
        ttk.Button(actions, text='Delete Chat', style='Select.TButton', command=self._delete_selected_chat).grid(row=0, column=1, sticky=tk.EW, padx=(4,0))
        # New: Rename Chat button (prompts for new name for selected session)
        try:
            ttk.Button(actions, text='Rename Chat', style='Select.TButton', command=self._rename_selected_chat).grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=(4,0))
        except Exception:
            pass

        # Panel-wide RAG controls (4 methods + 3 scopes = 28 configurations)
        # Migrate old state if present
        self._migrate_rag_state()

        # Method buttons (radio behavior: choose ONE)
        method_label = ttk.Label(parent, text='Method:', style='Config.TLabel')
        method_label.grid(row=3, column=0, sticky=tk.W, padx=(8,0), pady=(0,2))

        method_bar = ttk.Frame(parent, style='Category.TFrame')
        method_bar.grid(row=3, column=0, sticky=tk.EW, padx=(65,8), pady=(0,4))
        method_bar.columnconfigure(0, weight=1)
        method_bar.columnconfigure(1, weight=1)
        method_bar.columnconfigure(2, weight=1)
        method_bar.columnconfigure(3, weight=1)

        def _btn_style(active: bool) -> str:
            return 'Action.TButton' if active else 'Select.TButton'

        def set_rag_method(method: str):
            """Set RAG scoring method (standard, vcm, auto, manual)."""
            self.rag_scoring_method = method
            self._save_backend_setting('rag_scoring_method', method)
            _update_rag_buttons()
            try:
                self._update_quick_indicators()
            except Exception:
                pass

        self._rag_btn_standard = ttk.Button(method_bar, text='🧠', style=_btn_style(False), command=lambda: set_rag_method('standard'))
        self._rag_btn_vcm = ttk.Button(method_bar, text='🧠+', style=_btn_style(False), command=lambda: set_rag_method('vcm'))
        self._rag_btn_auto = ttk.Button(method_bar, text='🧠++', style=_btn_style(False), command=lambda: set_rag_method('auto'))
        self._rag_btn_manual = ttk.Button(method_bar, text='🔧', style=_btn_style(False), command=lambda: set_rag_method('manual'))
        self._rag_btn_standard.grid(row=0, column=0, sticky=tk.EW, padx=(0,4))
        self._rag_btn_vcm.grid(row=0, column=1, sticky=tk.EW, padx=4)
        self._rag_btn_auto.grid(row=0, column=2, sticky=tk.EW, padx=4)
        self._rag_btn_manual.grid(row=0, column=3, sticky=tk.EW, padx=(4,0))

        # Scope checkboxes (combinable: check ANY)
        scope_label = ttk.Label(parent, text='Scope:', style='Config.TLabel')
        scope_label.grid(row=4, column=0, sticky=tk.W, padx=(8,0), pady=(0,2))

        scope_bar = ttk.Frame(parent, style='Category.TFrame')
        scope_bar.grid(row=4, column=0, sticky=tk.EW, padx=(60,8), pady=(0,4))

        # Initialize scope vars
        self._rag_scope_personal = tk.BooleanVar(value=self.backend_settings.get('rag_scope_personal', True))
        self._rag_scope_project = tk.BooleanVar(value=self.backend_settings.get('rag_scope_project', False))
        self._rag_scope_topics = tk.BooleanVar(value=self.backend_settings.get('rag_scope_topics', False))
        self._rag_scope_vector = tk.BooleanVar(
            value=(self.rag_vector_enabled_default and self._vector_backend_available)
        )

        def toggle_scope_personal():
            val = self._rag_scope_personal.get()
            self._save_backend_setting('rag_scope_personal', val)
            try:
                self._update_quick_indicators()
            except Exception:
                pass

        def toggle_scope_project():
            val = self._rag_scope_project.get()
            self._save_backend_setting('rag_scope_project', val)
            try:
                self._update_quick_indicators()
            except Exception:
                pass

        def toggle_scope_topics():
            val = self._rag_scope_topics.get()
            self._save_backend_setting('rag_scope_topics', val)
            try:
                self._update_quick_indicators()
            except Exception:
                pass

        def toggle_scope_vector():
            val = bool(self._rag_scope_vector.get())

            if val and self._vector_backend_available:
                # User wants to enable vector - ensure server is running
                if self.embedding_server:
                    if not self.embedding_server.is_running():
                        log_message("VECTOR_SERVER: Starting embedding server...")
                        self._update_vector_health_status("unavailable", "Starting embedding server...")

                        # Start server in background
                        def start_server():
                            try:
                                success = self.embedding_server.start()
                                if success:
                                    log_message("VECTOR_SERVER: Started successfully")
                                    # Re-check health after startup
                                    self.root.after(1000, self._check_vector_health)
                                else:
                                    log_message("VECTOR_SERVER: Failed to start")
                                    self.root.after(100, lambda: self._rag_scope_vector.set(False))
                                    self._update_vector_health_status("error", "Failed to start embedding server")
                            except Exception as e:
                                log_message(f"VECTOR_SERVER: Start error: {e}")
                                self.root.after(100, lambda: self._rag_scope_vector.set(False))
                                self._update_vector_health_status("error", str(e))

                        import threading
                        threading.Thread(target=start_server, daemon=True).start()

                # Save setting and enable
                self._save_backend_setting('rag_scope_vector', val)
                self.rag_service.enable_vector_search(val)
            else:
                # User wants to disable vector
                self._rag_scope_vector.set(False)
                self._save_backend_setting('rag_scope_vector', False)
                self.rag_service.enable_vector_search(False)

                # Optionally stop server when disabled
                # (commented out - keep server running for reuse)
                # if self.embedding_server and self.embedding_server.is_running():
                #     log_message("VECTOR_SERVER: Stopping embedding server...")
                #     self.embedding_server.stop()

            try:
                self._update_quick_indicators()
            except Exception:
                pass

        self._rag_cb_personal = ttk.Checkbutton(scope_bar, text='Personal', variable=self._rag_scope_personal, command=toggle_scope_personal, style='TCheckbutton')
        self._rag_cb_project = ttk.Checkbutton(scope_bar, text='Project', variable=self._rag_scope_project, command=toggle_scope_project, style='TCheckbutton')
        self._rag_cb_topics = ttk.Checkbutton(scope_bar, text='Topics', variable=self._rag_scope_topics, command=toggle_scope_topics, style='TCheckbutton')
        self._rag_cb_vector = ttk.Checkbutton(
            scope_bar,
            text='Vector',
            variable=self._rag_scope_vector,
            command=toggle_scope_vector,
            style='TCheckbutton'
        )
        self._rag_cb_personal.pack(side=tk.LEFT, padx=(0,12))
        self._rag_cb_project.pack(side=tk.LEFT, padx=12)
        self._rag_cb_topics.pack(side=tk.LEFT, padx=12)
        self._rag_cb_vector.pack(side=tk.LEFT, padx=12)

        # Vector health status indicator
        self._vector_health_label = ttk.Label(
            scope_bar,
            text='',
            style='Caption.TLabel'
        )
        self._vector_health_label.pack(side=tk.LEFT, padx=(4,0))

        # Context-aware: Disable Project checkbox in Chat tab (no project scope)
        # This will be updated dynamically based on current_project
        self._update_rag_scope_availability()

        # Hint label for hover
        self._rag_hint_label = ttk.Label(parent, text='', style='Config.TLabel')
        self._rag_hint_label.grid(row=5, column=0, sticky=tk.W, padx=12, pady=(0,6))

        def _set_hint(text:str=''):
            try:
                self._rag_hint_label.config(text=text)
            except Exception:
                pass

        def _update_rag_buttons():
            """Update button styles based on current method."""
            method = getattr(self, 'rag_scoring_method', 'standard')
            try:
                self._rag_btn_standard.configure(style=_btn_style(method == 'standard'))
                self._rag_btn_vcm.configure(style=_btn_style(method == 'vcm'))
                self._rag_btn_auto.configure(style=_btn_style(method == 'auto'))
                self._rag_btn_manual.configure(style=_btn_style(method == 'manual'))
            except Exception:
                pass

        _update_rag_buttons()

        # Hover descriptions for methods
        try:
            self._rag_btn_standard.bind('<Enter>', lambda e: _set_hint('Standard: Lexical keyword matching (fast, baseline)'))
            self._rag_btn_vcm.bind('<Enter>', lambda e: _set_hint('VCM: 8-component observable scoring (smarter relevance)'))
            self._rag_btn_auto.bind('<Enter>', lambda e: _set_hint('Auto: VCM + multi-topic branching (most sophisticated)'))
            self._rag_btn_manual.bind('<Enter>', lambda e: _set_hint('Manual: Custom VCM weights (advanced configuration)'))
            for b in (self._rag_btn_standard, self._rag_btn_vcm, self._rag_btn_auto, self._rag_btn_manual):
                b.bind('<Leave>', lambda e: _set_hint(''))
        except Exception:
            pass

        # Hover descriptions for scopes
        try:
            self._rag_cb_personal.bind('<Enter>', lambda e: _set_hint('Personal: Retrieve from this variant\'s Training Grounds'))
            self._rag_cb_project.bind('<Enter>', lambda e: _set_hint('Project: Retrieve from current project\'s knowledge bank'))
            self._rag_cb_topics.bind('<Enter>', lambda e: _set_hint('Topics: Retrieve from System Knowledge Bank (shared topic banks)'))
            self._rag_cb_vector.bind('<Enter>', lambda e: _set_hint('Vector: Semantic search using h-codex (requires llama.cpp embeddings + Postgres)'))
            for cb in (self._rag_cb_personal, self._rag_cb_project, self._rag_cb_topics, self._rag_cb_vector):
                cb.bind('<Leave>', lambda e: _set_hint(''))
        except Exception:
            pass

        # Optional quick toggle for RAG DEBUG
        try:
            cur_dbg = bool(getattr(self, 'rag_debug_enabled', False))
        except Exception:
            cur_dbg = False
        self._rag_debug_var = tk.BooleanVar(value=cur_dbg)
        def _toggle_rag_debug():
            try:
                self.rag_debug_enabled = bool(self._rag_debug_var.get())
                self._save_backend_setting('rag_debug', self.rag_debug_enabled)
            except Exception:
                pass
        dbg_row = ttk.Frame(parent, style='Category.TFrame')
        dbg_row.grid(row=6, column=0, sticky=tk.EW, padx=8, pady=(0,8))
        ttk.Checkbutton(dbg_row, text='RAG DEBUG', variable=self._rag_debug_var, command=_toggle_rag_debug, style='TCheckbutton').pack(side=tk.LEFT)
        # RAG Details button (opens preview dialog)
        ttk.Button(dbg_row, text='🔍 RAG Details', style='Select.TButton', command=self._open_rag_details).pack(side=tk.RIGHT)

    def _open_rag_details(self):
        try:
            dlg = tk.Toplevel(self.root)
            dlg.title('RAG Details')
            dlg.geometry('800x520')
            dlg.transient(self.root)
            container = ttk.Frame(dlg, padding=8)
            container.pack(fill=tk.BOTH, expand=True)

            top = ttk.Frame(container)
            top.pack(fill=tk.X)
            ttk.Label(top, text='Query:', style='Config.TLabel').pack(side=tk.LEFT)
            qvar = tk.StringVar(value=self.last_user_message or '')
            qent = ttk.Entry(top, textvariable=qvar, width=80)
            qent.pack(side=tk.LEFT, padx=6)
            scope_var = tk.BooleanVar(value=bool(getattr(self, 'current_project', None)))
            ttk.Checkbutton(top, text='Use Project Scope', variable=scope_var, style='TCheckbutton').pack(side=tk.LEFT, padx=6)
            out = scrolledtext.ScrolledText(container, wrap=tk.WORD, font=("Courier", 9), bg='#1e1e1e', fg='#ffffff')
            out.pack(fill=tk.BOTH, expand=True, pady=(8,0))

            def run_query():
                try:
                    query = qvar.get().strip()
                    out.config(state=tk.NORMAL)
                    out.delete(1.0, tk.END)
                    if not query:
                        out.insert(tk.END, 'Enter a query above.')
                        out.config(state=tk.DISABLED)
                        return
                    # Ensure indexes ready
                    vector_enabled = self._vector_scope_active()
                    self.rag_service.enable_vector_search(vector_enabled)
                    if scope_var.get() and getattr(self, 'current_project', None):
                        self.rag_service.refresh_index_project(self.current_project)
                        results = self.rag_service.query(query, top_k=6, scope=self.current_project)
                    else:
                        self.rag_service.refresh_index_global()
                        results = self.rag_service.query(query, top_k=6, scope=None)
                    if not results:
                        out.insert(tk.END, 'No results.')
                        out.config(state=tk.DISABLED)
                        return
                    for i, (doc, score) in enumerate(results, 1):
                        out.insert(tk.END, f"[{i}] session={doc.session_id} role={doc.role} idx={doc.index} score={score:.3f}\n")
                        out.insert(tk.END, (doc.text or '')[:600] + '\n\n')
                    out.config(state=tk.DISABLED)
                except Exception:
                    try:
                        out.insert(tk.END, 'Error during retrieval.')
                        out.config(state=tk.DISABLED)
                    except Exception:
                        pass
            btns = ttk.Frame(container)
            btns.pack(fill=tk.X, pady=(6,0))
            ttk.Button(btns, text='Run', style='Action.TButton', command=run_query).pack(side=tk.LEFT)
            ttk.Button(btns, text='Close', style='Select.TButton', command=dlg.destroy).pack(side=tk.RIGHT)
            # Autofocus and initial run
            qent.focus_set()
            run_query()
        except Exception:
            pass

        # Schedule a single refresh with delay after mainloop stabilizes to avoid X11 resource exhaustion
        try:
            self.root.after(2500, self._refresh_conversations_list)
        except Exception:
            pass

    def _refresh_conversations_list(self):
        try:
            if not self.chat_history_manager:
                log_message("CHAT_INTERFACE: No ChatHistoryManager; conversations cannot be listed.")
                return
            from datetime import datetime, timedelta
            items = self.chat_history_manager.list_conversations()
            self._conv_items = items
            try:
                hist_dir = getattr(self.chat_history_manager, 'history_dir', None)
                log_message(f"CHAT_INTERFACE: Loaded {len(items)} conversations from {hist_dir}")
                if getattr(self, 'rag_debug_enabled', False):
                    try:
                        self.add_message('system', f"🧠 RAG DEBUG: Conversations loaded = {len(items)}\nPath: {hist_dir}")
                    except Exception:
                        pass
            except Exception:
                pass
            # Clear tree
            for it in self.conv_tree.get_children():
                self.conv_tree.delete(it)
            now = datetime.now()
            def parse_dt(s):
                try:
                    return datetime.fromisoformat(s)
                except Exception:
                    return None
            # Buckets
            latest_today = []
            week = []
            month = []
            year = []
            for rec in items:
                dt = parse_dt(rec.get('saved_at',''))
                if not dt:
                    continue
                age = now - dt
                if dt.date() == now.date():
                    latest_today.append(rec)
                elif age <= timedelta(days=7):
                    week.append(rec)
                elif age <= timedelta(days=30):
                    month.append(rec)
                elif age <= timedelta(days=365):
                    year.append(rec)
            # Year
            year_node = self.conv_tree.insert('', 'end', text=f"Year ({len(year)})", open=False, values=('category','year'))
            for rec in year:
                self.conv_tree.insert(year_node, 'end', text=f"{rec.get('saved_at','')[:16]}  {rec.get('session_id','')}", values=('session',rec.get('session_id','')))
            # Month
            month_node = self.conv_tree.insert('', 'end', text=f"Month ({len(month)})", open=False, values=('category','month'))
            for rec in month:
                self.conv_tree.insert(month_node, 'end', text=f"{rec.get('saved_at','')[:16]}  {rec.get('session_id','')}", values=('session',rec.get('session_id','')))
            # Week
            week_node = self.conv_tree.insert('', 'end', text=f"Week ({len(week)})", open=False, values=('category','week'))
            for rec in week:
                self.conv_tree.insert(week_node, 'end', text=f"{rec.get('saved_at','')[:16]}  {rec.get('session_id','')}", values=('session',rec.get('session_id','')))
            # Latest (days of week)
            latest_node = self.conv_tree.insert('', 'end', text="Latest", open=True, values=('category','latest'))
            # Build days starting with today
            weekdays = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
            today_idx = now.weekday() # 0=Mon
            ordered = [weekdays[today_idx]] + [w for i,w in enumerate(weekdays) if i!=today_idx]
            # Map recs by weekday name
            def dow_name(dt):
                return weekdays[dt.weekday()]
            by_day = {w: [] for w in weekdays}
            for rec in latest_today:
                dt = parse_dt(rec.get('saved_at',''))
                if dt:
                    by_day[dow_name(dt)].append(rec)
            # Limit current day to latest 15
            for w in ordered:
                label = w + (' (Today)' if w == weekdays[today_idx] else '')
                recs = by_day.get(w, [])
                if w == weekdays[today_idx]:
                    recs = recs[:15]
                node = self.conv_tree.insert(latest_node, 'end', text=f"{label} ({len(recs)})", open=(w==weekdays[today_idx]), values=('subcategory','latest_day'))
                for rec in recs:
                    self.conv_tree.insert(node, 'end', text=f"{rec.get('saved_at','')[11:16]}  {rec.get('session_id','')}", values=('session',rec.get('session_id','')))
            if len(items) == 0:
                # Friendly placeholder when no history yet
                self.conv_tree.insert(latest_node, 'end', text="(No conversations found)", values=('info',))
            # Expand top categories by default
            self.conv_tree.item(latest_node, open=True)
            # Highlight current session if present
            if self.current_session_id:
                for cat in self.conv_tree.get_children(''):
                    for sub in self.conv_tree.get_children(cat):
                        for leaf in self.conv_tree.get_children(sub):
                            sid = self.conv_tree.item(leaf,'values')
                            if isinstance(sid, (list,tuple)) and len(sid)>1 and sid[1]==self.current_session_id:
                                self.conv_tree.selection_set(leaf)
                                self.conv_tree.see(leaf)
                                raise StopIteration
        except Exception as e:
            log_message(f"CHAT_INTERFACE ERROR: Failed to refresh conversations: {e}")
            try:
                if getattr(self, 'rag_debug_enabled', False):
                    self.add_message('error', f"Conversations refresh failed: {e}")
            except Exception:
                pass
        finally:
            # Mark initialization complete after first refresh (success or fail)
            if not self._initialization_complete:
                self._initialization_complete = True
                log_message("CHAT_INTERFACE: Initialization complete, future refreshes may schedule callbacks")

    def _open_selected_chat(self):
        try:
            sel = self.conv_tree.selection()
            if not sel:
                return
            vals = self.conv_tree.item(sel[0], 'values')
            if not vals or vals[0] != 'session':
                return
            session_id = vals[1]
            # simulate double-click open
            self._load_conversation_by_id(session_id)
        except Exception:
            pass

    def _rename_selected_chat(self):
        try:
            from tkinter import simpledialog, messagebox
            sel = self.conv_tree.selection()
            if not sel:
                messagebox.showinfo('Rename Chat', 'Select a conversation to rename.')
                return
            vals = self.conv_tree.item(sel[0], 'values')
            if not vals or vals[0] != 'session':
                messagebox.showinfo('Rename Chat', 'Select a conversation (not a category) to rename.')
                return
            session_id = vals[1]
            new_name = simpledialog.askstring('Rename Chat', f'Rename "{session_id}" to:')
            if not new_name or new_name.strip() == session_id:
                return
            ok = False
            try:
                ok = self.chat_history_manager.rename_conversation(session_id, new_name.strip())
            except Exception as e:
                messagebox.showerror('Rename Chat', f'Failed to rename: {e}')
                return
            if ok:
                # Update current session id if needed
                if getattr(self, 'current_session_id', None) == session_id:
                    self.current_session_id = new_name.strip()
                # Refresh list and notify
                try:
                    self._refresh_conversations_list()
                except Exception:
                    pass
                self.add_message('system', f'✓ Renamed chat to: {new_name.strip()}')
            else:
                messagebox.showerror('Rename Chat', 'Rename operation failed.')
        except Exception:
            pass

    def _load_conversation_by_id(self, session_id: str):
        """Load a conversation by id and update UI consistently."""
        try:
            if not self.chat_history_manager:
                return
            data = self.chat_history_manager.load_conversation(session_id)
            if not data:
                return
            # Restore per-session tool overrides if available
            try:
                meta = data.get('metadata') or {}
                sess = meta.get('session_tools')
                if isinstance(sess, dict):
                    self.session_enabled_tools = sess
                # Restore Training Mode / Support per session
                try:
                    tm = bool(meta.get('training_data_collection', False))
                    ts = bool(meta.get('training_support_enabled', False))
                    # Apply Support first to backend, then set Training Mode so pipeline wiring is correct
                    # If TM is OFF, force TS OFF to stay consistent
                    if not tm:
                        ts = False
                    try:
                        # Set Support backend flag
                        self.parent_tab.set_training_support(ts)
                    except Exception:
                        pass
                    try:
                        self.set_training_mode(tm)
                    except Exception:
                        pass
                except Exception:
                    pass
            except Exception:
                pass
            # Confirm/reflect model
            model = (data.get('model_name') or '').strip()
            switched = False
            if model and model != (self.current_model or ''):
                chosen = self._confirm_switch_model(model)
                if chosen:
                    try:
                        if hasattr(self.parent_tab, 'select_model'):
                            self.parent_tab.select_model(chosen)
                        else:
                            self.set_model(chosen)
                    except Exception:
                        self.set_model(chosen)
                    switched = True
            if not switched and model:
                try:
                    self.current_model = model
                    self._set_model_label_with_class_color(model)
                    self._update_mount_button_style(mounted=False)
                    self.mount_btn.config(state=tk.NORMAL)
                except Exception:
                    pass
            # Apply per-session agents default if present
            try:
                meta = data.get('metadata') or {}
                roster = meta.get('agents_default')
                if roster:
                    self._restore_session_roster(roster)
                # Restore per-session Agentic override if present
                try:
                    ap = meta.get('agentic_project_enabled', None)
                    if ap in (True, False):
                        self.agentic_project_override = bool(ap)
                        # Apply immediately so indicator/UI reflect it
                        self.initialize_advanced_components()
                        self._update_quick_indicators()
                except Exception:
                    pass
                # Restore agents mini sessions logs
                try:
                    sess = meta.get('agents_sessions')
                    if isinstance(sess, dict):
                        self._agents_sessions = sess
                except Exception:
                    pass
            except Exception:
                pass

            # Load chat history and update UI
            self.chat_history = data.get('chat_history') or []
            self.current_session_id = session_id
            self.redisplay_conversation()
            self.add_message('system', f"✓ Loaded conversation: {session_id}")
        except Exception:
            pass

    def _delete_selected_chat(self):
        from tkinter import messagebox
        try:
            sel = self.conv_tree.selection()
            if not sel:
                return
            vals = self.conv_tree.item(sel[0], 'values')
            if not vals or vals[0] != 'session':
                return
            session_id = vals[1]
            if not messagebox.askyesno('Confirm Delete', f'Delete conversation?\n\n{session_id}'):
                return
            ok = self.chat_history_manager.delete_conversation(session_id)
            if ok:
                messagebox.showinfo('Deleted', 'Conversation deleted successfully')
                self._refresh_conversations_list()
            else:
                messagebox.showerror('Error', 'Failed to delete conversation')
        except Exception:
            pass

    def _on_conv_selected(self, event=None):
        try:
            sel = self.conv_tree.selection()
            if self._suppress_quickview:
                return
            if event is not None and getattr(event, 'widget', None) is not self.conv_tree:
                return
            if not sel:
                return
            vals = self.conv_tree.item(sel[0], 'values')
            if not vals or vals[0] != 'session':
                return
            session_id = vals[1]
            self._show_conv_quickview(session_id)
        except Exception:
            pass

    def _show_conv_quickview(self, session_id: str):
        """Enhanced chat quickview with expandable sections for tools, agents, config, and conversation"""
        # Destroy previous quickview
        try:
            if hasattr(self, '_conv_quickview') and self._conv_quickview and self._conv_quickview.winfo_exists():
                self._conv_quickview.destroy()
        except Exception:
            pass

        try:
            data = self.chat_history_manager.load_conversation(session_id)
            if not data:
                return

            top = tk.Toplevel(self.root)
            self._conv_quickview = top
            top.title('Chat Quick View')
            top.resizable(True, True)

            # Position near tree with larger size for sections
            try:
                tx = self.conv_tree.winfo_rootx() + self.conv_tree.winfo_width() + 16
                ty = self.conv_tree.winfo_rooty() + 40
                top.geometry(f"520x600+{tx}+{ty}")
            except Exception:
                pass

            # Main scrollable container
            canvas = tk.Canvas(top, bg='#2b2b2b', highlightthickness=0)
            scrollbar = ttk.Scrollbar(top, orient="vertical", command=canvas.yview)
            frm = ttk.Frame(canvas, padding=8)

            frm.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=frm, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # Enable mousewheel scrolling
            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

            frm.columnconfigure(0, weight=1)
            row = 0

            # Header: Model color-coded and Parent Model line
            model = (data.get('model_name') or 'unknown').strip()
            model_for_lookup = model.replace('.gguf', '').replace('.q4_k_m', '').replace('.q8_0', '').replace('.q4_0', '').replace('.q5_0', '').replace('.q5_1', '').replace('.q6_k', '')
            parent_text, class_label, color = self._resolve_parent_and_class(model_for_lookup)
            header = f"{model}  <{class_label.capitalize()}>"
            ttk.Label(frm, text=header, font=('Arial', 11, 'bold'), foreground=color, style='CategoryPanel.TLabel').grid(row=row, column=0, sticky=tk.W)
            row += 1
            ttk.Label(frm, text=f"Parent Model: {parent_text}", style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, pady=(0,8))
            row += 1

            meta = data.get('metadata') or {}
            hist = data.get('chat_history') or []

            # === TOOLS USED SECTION (Collapsible) ===
            self._create_collapsible_section(frm, row, "🔧 Tools Used", lambda parent: self._render_tools_section(parent, meta, hist), collapsed=True)
            row += 1

            # === AGENTS SECTION (Collapsible, only if agents present) ===
            agents_data = meta.get('agents_roster') or meta.get('session_agents')
            if agents_data:
                self._create_collapsible_section(frm, row, "🤖 Agents", lambda parent: self._render_agents_section(parent, meta), collapsed=True)
                row += 1

            # === CONFIGURATION SECTION (Collapsible) ===
            self._create_collapsible_section(frm, row, "⚙️ Configuration", lambda parent: self._render_config_section(parent, meta), collapsed=True)
            row += 1

            # === CONVERSATION PREVIEW (Expanded by default) ===
            self._create_collapsible_section(frm, row, "💬 Conversation Preview", lambda parent: self._render_conversation_section(parent, hist), collapsed=False)
            row += 1

            # Auto-dismiss on click-away
            def _maybe_close(e=None):
                """Close quickview on focus-out but keep current selection intact so Open Chat works."""
                try:
                    f = self.root.focus_get()
                    if not f or not str(f).startswith(str(top)):
                        canvas.unbind_all("<MouseWheel>")
                        top.destroy()
                except Exception:
                    pass

            top.bind('<FocusOut>', _maybe_close)
            top.protocol("WM_DELETE_WINDOW", lambda: (canvas.unbind_all("<MouseWheel>"), top.destroy()))

        except Exception as e:
            log_message(f"CHAT_INTERFACE: Quickview error: {e}")

    def _create_collapsible_section(self, parent, row, title, render_func, collapsed=True):
        """Create a collapsible section with toggle button"""
        section_frame = ttk.Frame(parent)
        section_frame.grid(row=row, column=0, sticky=tk.EW, pady=2)
        section_frame.columnconfigure(0, weight=1)

        # Header with toggle
        header_frame = tk.Frame(section_frame, bg='#3a3a3a', height=28)
        header_frame.grid(row=0, column=0, sticky=tk.EW)
        header_frame.grid_propagate(False)

        expand_var = tk.BooleanVar(value=not collapsed)
        content_frame = ttk.Frame(section_frame)

        def toggle():
            is_expanded = expand_var.get()
            if is_expanded:
                # Collapse
                for widget in content_frame.winfo_children():
                    widget.destroy()
                content_frame.grid_forget()
                toggle_btn.config(text="▶")
            else:
                # Expand
                toggle_btn.config(text="▼")
                content_frame.grid(row=1, column=0, sticky=tk.EW, padx=8, pady=4)
                render_func(content_frame)
            expand_var.set(not is_expanded)

        toggle_btn = tk.Button(header_frame, text="▼" if not collapsed else "▶",
                               font=('Arial', 9), bg='#3a3a3a', fg='#dcdcdc',
                               bd=0, padx=8, command=toggle, cursor='hand2')
        toggle_btn.pack(side=tk.LEFT)

        tk.Label(header_frame, text=title, font=('Arial', 10, 'bold'),
                bg='#3a3a3a', fg='#dcdcdc').pack(side=tk.LEFT, padx=4)

        # Render if not collapsed
        if not collapsed:
            content_frame.grid(row=1, column=0, sticky=tk.EW, padx=8, pady=4)
            render_func(content_frame)

    def _render_tools_section(self, parent, meta, hist):
        """Render tools used section"""
        # Extract tools from session_tools or scan messages for tool calls
        tools_used = set()

        # Check metadata for session tools
        session_tools = meta.get('session_tools') or meta.get('tool_settings')
        if isinstance(session_tools, dict):
            for tool_name, enabled in session_tools.items():
                if enabled:
                    tools_used.add(tool_name)

        # Scan chat history for tool usage (messages with 'tool_calls' or 'tool_call_id')
        for msg in hist:
            if msg.get('tool_calls'):
                for tc in msg.get('tool_calls', []):
                    if isinstance(tc, dict):
                        tools_used.add(tc.get('function', {}).get('name', 'unknown'))

        if tools_used:
            tools_list = sorted(tools_used)
            text = '\n'.join(f"  • {tool}" for tool in tools_list)
            ttk.Label(parent, text=f"{len(tools_list)} tools used:\n{text}",
                     style='Config.TLabel', justify=tk.LEFT).pack(anchor=tk.W)
        else:
            ttk.Label(parent, text="No tools used in this conversation",
                     style='Config.TLabel', foreground='#888888').pack(anchor=tk.W)

    def _render_agents_section(self, parent, meta):
        """Render agents section"""
        agents_roster = meta.get('agents_roster') or meta.get('session_agents') or []
        if agents_roster:
            if isinstance(agents_roster, list):
                agents_text = '\n'.join(f"  • {agent}" for agent in agents_roster)
            else:
                agents_text = f"  • {agents_roster}"
            ttk.Label(parent, text=f"Active agents:\n{agents_text}",
                     style='Config.TLabel', justify=tk.LEFT).pack(anchor=tk.W)
        else:
            ttk.Label(parent, text="No agents active",
                     style='Config.TLabel', foreground='#888888').pack(anchor=tk.W)

    def _render_config_section(self, parent, meta):
        """Render configuration section"""
        cfg_lines = [
            f"Mode: {meta.get('mode','unknown')}",
            f"Temperature: {meta.get('temperature','?')}",
            f"Temp Mode: {meta.get('temp_mode','manual')}",
            f"System Prompt: {meta.get('system_prompt','default')}",
            f"Tool Schema: {meta.get('tool_schema','default')}",
            f"Working Directory: {meta.get('working_directory','unknown')}",
            f"Training Mode: {bool(meta.get('training_data_collection', False))}",
        ]
        ttk.Label(parent, text='\n'.join(cfg_lines), style='Config.TLabel', justify=tk.LEFT).pack(anchor=tk.W)

    def _render_conversation_section(self, parent, hist):
        """Render conversation preview section with agents indicator"""
        pairs = []
        cur_user = None

        # Process messages to create user/assistant pairs
        for msg in hist:
            role = msg.get('role')
            if role == 'user':
                cur_user = msg.get('content', '')
            elif role == 'assistant' and cur_user is not None:
                pairs.append((cur_user, msg.get('content', '')))
                cur_user = None

        # Show most recent pairs first
        MAX_PAIRS = 5
        pairs = list(reversed(pairs))[:MAX_PAIRS]

        if pairs:
            box = scrolledtext.ScrolledText(parent, height=12, wrap=tk.WORD,
                                           font=('Arial', 9), bg='#1e1e1e', fg='#dcdcdc')
            box.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

            try:
                box.tag_config('u', foreground='#61dafb')
                box.tag_config('a', foreground='#98c379')
            except Exception:
                pass

            for u, a in pairs:
                box.insert(tk.END, 'You: ', 'u')
                box.insert(tk.END, (u or '')[:200] + ('...' if len(u or '') > 200 else '') + '\n')
                box.insert(tk.END, 'Model: ', 'a')
                box.insert(tk.END, (a or '')[:200] + ('...' if len(a or '') > 200 else '') + '\n\n')

            box.configure(state='disabled')

            # === AGENTS PARTICIPATION INDICATOR ===
            self._render_agents_indicator(parent, hist)
        else:
            ttk.Label(parent, text="No conversation history available",
                     style='Config.TLabel', foreground='#888888').pack(anchor=tk.W)

    def _render_agents_indicator(self, parent, hist):
        """Render agents participation indicator showing which agents made outputs and their variants"""
        # Track agents that made at least one output
        agents_used = {}  # {agent_type: [variant1, variant2, ...]}

        # Scan chat history for agent outputs
        # Look for messages with metadata indicating agent/variant
        for msg in hist:
            if msg.get('role') == 'assistant':
                # Check for agent metadata in message
                msg_meta = msg.get('metadata') or {}
                agent_type = msg_meta.get('agent_type') or msg_meta.get('agent_name')
                variant = msg_meta.get('variant') or msg_meta.get('model')

                # If no metadata, try to infer from model field
                if not agent_type:
                    model = msg.get('model') or msg.get('name')
                    if model:
                        # Try to extract agent type from variant name
                        # e.g., "Qwen2.5-0.5b_coder" -> "coder"
                        if '_' in model:
                            parts = model.rsplit('_', 1)
                            if len(parts) == 2:
                                agent_type = parts[1]
                                variant = model

                if agent_type:
                    if agent_type not in agents_used:
                        agents_used[agent_type] = set()
                    if variant:
                        agents_used[agent_type].add(variant)

        # If no agent metadata found, check if there are any assistant messages at all
        # In that case, show the primary model
        if not agents_used:
            # Get main model from first assistant message
            for msg in hist:
                if msg.get('role') == 'assistant':
                    model = msg.get('model') or msg.get('name')
                    if model:
                        # Extract type if present
                        if '_' in model:
                            parts = model.rsplit('_', 1)
                            if len(parts) == 2:
                                agent_type = parts[1]
                                agents_used[agent_type] = {model}
                        else:
                            agents_used['primary'] = {model}
                        break

        # Render agents indicator
        if agents_used:
            separator = ttk.Separator(parent, orient='horizontal')
            separator.pack(fill=tk.X, pady=(8, 8))

            agents_frame = ttk.Frame(parent)
            agents_frame.pack(fill=tk.X, anchor=tk.W)

            # Header
            header_label = tk.Label(agents_frame, text="Agents:",
                                   font=('Arial', 9, 'bold'),
                                   bg='#2b2b2b', fg='#dcdcdc')
            header_label.pack(side=tk.LEFT, padx=(0, 8))

            # Agent badges and variants
            agent_container = ttk.Frame(agents_frame)
            agent_container.pack(side=tk.LEFT, fill=tk.X, expand=True)

            for idx, (agent_type, variants) in enumerate(sorted(agents_used.items())):
                if idx > 0:
                    # Separator between agents
                    tk.Label(agent_container, text="|",
                            font=('Arial', 9),
                            bg='#2b2b2b', fg='#666666').pack(side=tk.LEFT, padx=4)

                # Agent badge
                agent_frame = ttk.Frame(agent_container)
                agent_frame.pack(side=tk.LEFT, padx=2)

                # Agent type badge
                badge = tk.Label(agent_frame,
                               text=f"[{agent_type.capitalize()}]",
                               font=('Arial', 9, 'bold'),
                               bg='#3a3a3a', fg='#61dafb',
                               padx=6, pady=2, relief=tk.RAISED, bd=1)
                badge.pack(anchor=tk.W)

                # Variants list under the badge
                if variants:
                    variants_frame = ttk.Frame(agent_frame)
                    variants_frame.pack(anchor=tk.W, padx=(8, 0), pady=(2, 0))

                    for variant in sorted(variants):
                        # Check if variant is assigned or unassigned
                        try:
                            from config import load_model_profile
                            profile = load_model_profile(variant)
                            if profile and profile.get('assigned_type'):
                                variant_label = f"• {variant}"
                                variant_color = '#98c379'  # Green for assigned
                            else:
                                variant_label = f"• {variant} (Unassigned)"
                                variant_color = '#888888'  # Gray for unassigned
                        except Exception:
                            variant_label = f"• {variant}"
                            variant_color = '#dcdcdc'

                        tk.Label(variants_frame, text=variant_label,
                               font=('Arial', 8),
                               bg='#2b2b2b', fg=variant_color).pack(anchor=tk.W)

    def _get_model_class_color(self, model_tag: str) -> str:
        try:
            import config as C
            color = '#bbbbbb'
            try:
                lid = C.get_lineage_for_tag(model_tag)
            except Exception:
                lid = None
            if lid:
                try:
                    for rec in (C.list_model_profiles() or []):
                        if rec.get('lineage_id') == lid:
                            cls = rec.get('type') or rec.get('class') or ''
                            # Map common classes to colors
                            cmap = {'coder':'#c792ea','researcher':'#82aaff'}
                            color = cmap.get(cls, '#61dafb')
                            break
                except Exception:
                    pass
            return color
        except Exception:
            return '#bbbbbb'

    def _resolve_parent_and_class(self, model_tag: str) -> tuple[str,str,str]:
        """Return (parent_model, class_label, color) for a model tag or variant id."""
        try:
            import config as C
            # 1) Direct variant profile
            try:
                mp = C.load_model_profile(model_tag)
                parent = mp.get('base_model') or ''
                class_label = (mp.get('class_level') or mp.get('class') or 'unassigned')
                return (parent or 'unknown', class_label, self._get_model_class_color(model_tag))
            except Exception:
                pass
            # 2) If tag -> lineage -> find variant
            try:
                lid = C.get_lineage_for_tag(model_tag)
                if lid:
                    for rec in (C.list_model_profiles() or []):
                        vid = rec.get('variant_id') or ''
                        if C.get_lineage_id(vid) == lid:
                            parent = rec.get('base_model') or 'unknown'
                            class_label = C.get_variant_class(vid) or 'unassigned'
                            return (parent, class_label, self._get_model_class_color(vid))
            except Exception:
                pass
            # 3) GGUF-aware fallback: Strip extensions and retry
            if '.gguf' in model_tag or any(q in model_tag for q in ['.q4_', '.q5_', '.q6_', '.q8_']):
                clean_tag = model_tag
                for ext in ['.gguf', '.q4_k_m', '.q8_0', '.q4_0', '.q5_0', '.q5_1', '.q6_k']:
                    clean_tag = clean_tag.replace(ext, '')
                if clean_tag != model_tag:
                    # Retry with cleaned tag
                    try:
                        mp = C.load_model_profile(clean_tag)
                        parent = mp.get('base_model') or ''
                        class_label = (mp.get('class_level') or mp.get('class') or 'unassigned')
                        return (parent or 'unknown', class_label, self._get_model_class_color(clean_tag))
                    except Exception:
                        pass
        except Exception:
            pass
        return ('unknown', 'unassigned', '#bbbbbb')

    def _toggle_conv_lock(self):
        try:
            locked = bool(self.backend_settings.get('conv_locked', False))
            locked = not locked
            self.backend_settings['conv_locked'] = locked
            # Capture current width
            try:
                w = max(160, min(360, int(self.conv_sidebar.winfo_width())))
            except Exception:
                w = 240
            self.backend_settings['conv_width'] = w
            if hasattr(self, '_conv_lock_btn'):
                self._conv_lock_btn.config(text=('🔒' if locked else '🔓'))
            self._save_backend_settings()
            self._apply_conv_lock_state()
        except Exception:
            pass

    def _enforce_conv_width(self, event=None):
        try:
            if not bool(self.backend_settings.get('conv_locked', False)):
                return
            w = max(160, min(360, int(self.backend_settings.get('conv_width', 240))))
            try:
                # adjust sash to keep left pane at w
                self._chat_pane.sashpos(0, w)
            except Exception:
                pass
        except Exception:
            pass

    def _apply_conv_lock_state(self):
        try:
            if bool(self.backend_settings.get('conv_locked', False)):
                # Disable sash drag and cursor
                try:
                    self._chat_pane.configure(cursor='arrow')
                except Exception:
                    pass
                def _block(event):
                    return 'break'
                for seq in ('<ButtonPress-1>', '<B1-Motion>', '<ButtonRelease-1>'):
                    self._chat_pane.bind(seq, _block)
                # Enforce saved width
                self._enforce_conv_width()
            else:
                try:
                    self._chat_pane.configure(cursor='')
                except Exception:
                    pass
                for seq in ('<ButtonPress-1>', '<B1-Motion>', '<ButtonRelease-1>'):
                    try:
                        self._chat_pane.unbind(seq)
                    except Exception:
                        pass
        except Exception:
            pass

    def _save_backend_settings(self):
        try:
            from pathlib import Path
            import json
            settings_file = Path(__file__).parent.parent / 'custom_code_settings.json'
            existing = {}
            if settings_file.exists():
                try:
                    existing = json.loads(settings_file.read_text())
                except Exception:
                    existing = {}
            existing.update(self.backend_settings or {})
            settings_file.write_text(json.dumps(existing, indent=2))
        except Exception:
            pass

    def _on_open_selected_conversation(self, event=None):
        try:
            # Save QA settings per session if changed
            data = self.chat_history_manager.load_conversation(session_id)
            if not data:
                return

            meta = data.get('metadata') or {}
            log_message(f"CHAT_INTERFACE: Loading session {session_id} with metadata: {meta}")

            # Restore all per-session settings from metadata
            # Working Directory
            if 'working_directory' in meta and hasattr(self, 'tool_executor') and self.tool_executor:
                new_dir = meta['working_directory']
                if self.tool_executor.set_working_directory(new_dir):
                    self.backend_settings['working_directory'] = new_dir
                    log_message(f"CHAT_INTERFACE: Restored session working directory to {new_dir}")
                else:
                    log_message(f"CHAT_INTERFACE ERROR: Failed to restore session working directory to {new_dir}")

            # Mode
            if 'mode' in meta:
                new_mode = meta.get('mode', 'smart')
                self.current_mode = new_mode
                # Apply the mode's parameters
                if hasattr(self, 'set_mode_parameters'):
                    mode_params = self.get_mode_parameters(new_mode)
                    self.set_mode_parameters(new_mode, mode_params)
                log_message(f"CHAT_INTERFACE: Restored session mode to {new_mode}")

            # System Prompt & Tool Schema
            self.current_system_prompt = meta.get('system_prompt', self.backend_settings.get('default_system_prompt', 'default'))
            self.current_tool_schema = meta.get('tool_schema', self.backend_settings.get('default_tool_schema', 'default'))
            log_message(f"CHAT_INTERFACE: Restored prompt ({self.current_system_prompt}) and schema ({self.current_tool_schema})")

            # Temperature
            self.temp_mode = meta.get('temp_mode', 'manual')
            self.session_temperature = meta.get('temperature', self.backend_settings.get('temperature', 0.8))
            try:
                self.session_temperature_var.set(self.session_temperature)
                self.update_session_temp_label(self.session_temperature)
            except Exception: # UI might not be fully ready
                pass
            log_message(f"CHAT_INTERFACE: Restored temperature to {self.session_temperature} ({self.temp_mode})")

            # Show Thoughts
            self.show_thoughts = meta.get('show_thoughts', False)

            # RAG Enabled
            self.rag_enabled = meta.get('rag_enabled', False)

            # Tool Overrides
            sess = meta.get('session_tools')
            if isinstance(sess, dict):
                self.session_enabled_tools = sess
                log_message("CHAT_INTERFACE: Restored per-session tool overrides")
            else:
                self.session_enabled_tools = None

            # Finally, update all indicators
            self.root.after(100, self._update_quick_indicators)
            # Check model availability and confirm switch
            model = (data.get('model_name') or '').strip()
            switched = False
            if model and model != (self.current_model or ''):
                chosen = self._confirm_switch_model(model)
                if chosen:
                    # Route through parent to keep other panels in sync
                    try:
                        if hasattr(self.parent_tab, 'select_model'):
                            self.parent_tab.select_model(chosen)
                        else:
                            self.set_model(chosen)
                    except Exception:
                        self.set_model(chosen)
                    switched = True
            # If not switched (user cancelled or model unavailable), still reflect session model in UI
            if not switched and model:
                try:
                    self.current_model = model
                    self._set_model_label_with_class_color(model)
                    self._update_mount_button_style(mounted=False)
                    self.mount_btn.config(state=tk.NORMAL)
                except Exception:
                    pass
            # Load chat history
            self.chat_history = data.get('chat_history') or []
            self.redisplay_conversation()
            self.add_message('system', f"Loaded conversation: {session_id}")
        except Exception:
            pass

    def _confirm_switch_model(self, target_model: str) -> str | bool:
        from tkinter import messagebox
        try:
            def _base(name: str) -> str:
                name = (name or '').strip()
                # Split on last colon to remove tag (handles names with embedded colons)
                return name.rsplit(':', 1)[0] if ':' in name else name
            available = []
            try:
                from config import get_ollama_models
                available = get_ollama_models() or []
            except Exception:
                available = []
            # Try exact match, else match by base name
            if target_model in available:
                return target_model if messagebox.askyesno('Switch Model', f'Switching to "{target_model}" for the selected conversation. Continue?') else False
            base_target = _base(target_model)
            candidates = [m for m in available if _base(m) == base_target]
            if candidates:
                choice = candidates[0]
                return choice if messagebox.askyesno('Switch Model', f'Switching to "{choice}" for the selected conversation. Continue?') else False
            else:
                messagebox.showwarning('Model Not Available', f'Warning: "{target_model}" is no longer available.')
                return False
        except Exception:
            return target_model

        # Configure tags for styling
        self.chat_display.tag_config('user', foreground='#61dafb', font=("Arial", 10, "bold"))
        self.chat_display.tag_config('assistant', foreground='#98c379', font=("Arial", 10, "bold"))
        self.chat_display.tag_config('system', foreground='#e06c75', font=("Arial", 9, "italic"))
        self.chat_display.tag_config('error', foreground='#ff6b6b', font=("Arial", 9))

    def create_input_area(self, parent):
        """Create the message input area"""
        input_frame = ttk.Frame(parent, style='Category.TFrame')
        input_frame.grid(row=3, column=0, sticky=tk.EW, padx=10, pady=(5, 10))  # row=3 now (progress bar is at row=1)
        input_frame.columnconfigure(0, weight=1)

        # Quick Actions gear (replaces Load Chat) - placed later near top actions

        # Quick Actions and indicators bar (bottom-left between display and input)
        qa_bar = ttk.Frame(input_frame, style='Category.TFrame')
        qa_bar.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0,4))
        self.quick_actions_btn = ttk.Button(qa_bar, text="⚙️", command=self._open_quick_actions, style='Action.TButton', width=4)
        self.quick_actions_btn.pack(side=tk.LEFT)
        self.qa_indicators = ttk.Frame(qa_bar, style='Category.TFrame')
        self.qa_indicators.pack(side=tk.LEFT, padx=(8,0))
        self._tooltip_win = None
        self._update_quick_indicators()
        try:
            self._indicators_job = self.root.after(2000, self._poll_indicators)
        except Exception:
            self._indicators_job = None

        # Progress Bar Widget moved to chat_container (see __init__)

        # Text input
        self.input_text = tk.Text(
            input_frame,
            height=3,
            wrap=tk.WORD,
            font=("Arial", 10),
            relief='flat',
            borderwidth=1,
            highlightthickness=1,
            highlightbackground='#454545',
            bg='#1e1e1e',
            fg='#ffffff',
            insertbackground='#61dafb'
        )
        self.input_text.grid(row=1, column=0, sticky=tk.EW, padx=(0, 5))

        # Bind Enter key (Shift+Enter for new line)
        self.input_text.bind('<Return>', self.on_enter_key)
        try:
            log_message("WIRE: input_text bound <Return> -> on_enter_key")
        except Exception:
            pass

        # Button container (Send/Stop buttons on the right side of input)
        button_container = ttk.Frame(input_frame, style='Category.TFrame')
        button_container.grid(row=1, column=1, sticky=tk.NS)

        # Send button
        self.send_btn = ttk.Button(
            button_container,
            text="Send ➤",
            command=self.send_message,
            style='Action.TButton',
            state=tk.DISABLED
        )
        self.send_btn.pack(side=tk.TOP, fill=tk.X, pady=(0, 2))
        try:
            log_message("WIRE: send_btn command -> send_message()")
        except Exception:
            pass

        # Stop button (moved here)
        self.stop_btn = ttk.Button(
            button_container,
            text="⏹️ Stop",
            command=self.stop_generation,
            style='Select.TButton',
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.TOP, fill=tk.X)

        # Instructions
        ttk.Label(
            input_frame,
            text="Press Enter to send • Shift+Enter for new line",
            style='Config.TLabel',
            font=("Arial", 8)
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(2, 0))

        # Indicator strip moved to top actions; no duplicate setup here

    def on_enter_key(self, event):
        """Handle Enter key press"""
        try:
            log_message(f"KEY: Enter pressed (state={getattr(event,'state',None)})")
        except Exception:
            pass
        # If Shift is held, insert newline (default behavior)
        if event.state & 0x1:  # Shift key
            return None  # Allow default behavior
        else:
            # Otherwise, send message
            self.send_message()
            return "break"  # Prevent newline insertion

    def set_model(self, model_name):
        """Set the active model for chat"""
        # Auto-save current conversation if switching models
        if self.current_model and self.chat_history:
            self.conversation_histories[self.current_model] = self.chat_history.copy()
            # Auto-save to persistent storage if enabled
            if self.backend_settings.get('auto_save_history', True):
                self._auto_save_conversation()

            # Persist real-time scores for the previous model
            if self.training_mode_enabled and self.current_model in self.realtime_eval_scores:
                self.persist_realtime_scores(self.current_model)

        self.current_model = model_name
        self.is_mounted = False

        # Update label color based on variant class color
        self._set_model_label_with_class_color(model_name)

        # Enable mount button (style red for not mounted), disable send and dismount
        self._update_mount_button_style(mounted=False)
        self.dismount_btn.config(state=tk.DISABLED)
        self.send_btn.config(state=tk.DISABLED)

        log_message(f"CHAT_INTERFACE: Model set to {model_name}")

        # Load conversation history for this model if exists
        if model_name in self.conversation_histories:
            self.chat_history = self.conversation_histories[model_name].copy()
            # Redisplay the conversation
            self.redisplay_conversation()
            self.add_message("system", f"Model switched to: {model_name} (conversation restored)")
        else:
            self.chat_history = []
            self.clear_chat()
            self.add_message("system", f"Model switched to: {model_name} (new conversation)")

        # Auto-mount if enabled in settings
        if self.backend_settings.get('auto_mount_model', False):
            log_message(f"CHAT_INTERFACE: Auto-mounting {model_name}")
            self.mount_model()

        # Reset session temperature
        self.session_temperature = self.backend_settings.get('temperature', 0.8)
        self.session_temperature_var.set(self.session_temperature)
        self.update_session_temp_label(self.session_temperature)
        # Ensure mount button enabled after model selection
        try:
            self.mount_btn.config(state=tk.NORMAL)
        except Exception:
            pass

    def mount_model(self):
        """Mount the selected model using the active backend"""
        # Resolve active model: prefer internal state; fallback to label text
        model_name = (self.current_model or '').strip()
        if not model_name:
            try:
                lbl = str(self.model_label.cget('text') or '').strip()
            except Exception:
                lbl = ''
            if lbl and lbl.lower() != 'no model selected':
                model_name = lbl
                self.current_model = model_name
                try:
                    self.add_message('system', f"Using active model: {model_name}")
                except Exception:
                    pass
        if not model_name:
            try:
                self.add_message("error", "No model selected. Pick a model from the right panel.")
            except Exception:
                pass
            return

        log_message(f"CHAT_INTERFACE: Mounting model {model_name}...")
        try:
            self.add_message("system", f"Mounting {model_name}...")
        except Exception:
            pass

        backend = self._get_chat_backend()
        try:
            self.current_backend = backend
        except Exception:
            pass
        if backend == 'llama_server':
            # Force start on manual mount even if auto_start is disabled
            # Prefer absolute GGUF path if we have one
            selected = getattr(self, 'current_model_path', None) or model_name
            ok, info = self._ensure_llama_server_running(selected, force_start=True)
            if not ok:
                err = f"Llama Server not ready: {info}"
                log_message(f"CHAT_INTERFACE ERROR: {err}")
                self.root.after(0, lambda: self._on_mount_error(err))
                return

            # Port check logging before showing ready
            host = (self.backend_settings.get('llama_server_host') or '127.0.0.1').strip()
            port = int(self.backend_settings.get('llama_server_port') or 8001)
            try:
                self.add_message("system", f"✓ Port check: {host}:{port} is responding")
            except Exception:
                pass

            ok2, info2 = self._check_llama_server_connection()
            if not ok2:
                err = f"Server started but not responding properly: {info2}"
                log_message(f"CHAT_INTERFACE ERROR: {err}")
                try:
                    self.add_message("error", err)
                except Exception:
                    pass
                self.root.after(0, lambda: self._on_mount_error(err))
                return

            message = info2
            msg = f"🌐 Llama Server ready ({message})"
            log_message(f"CHAT_INTERFACE: {msg}")
            try:
                self.add_message("system", msg)
            except Exception:
                pass
            self._llama_server_stream_warned = False
            # Persist backend and notify UI
            try:
                self.current_backend = backend
                self._set_chat_backend(backend)
            except Exception:
                pass
            self.root.after(0, self._on_mount_success)
            return

        def mount_thread():
            try:
                # Basic preflight: ensure 'ollama' is available
                try:
                    import shutil
                    if not shutil.which('ollama'):
                        self.root.after(0, lambda: self._on_mount_error("Mount failed: 'ollama' command not found."))
                        return
                except Exception:
                    pass
                # Call Ollama to load the model
                result = subprocess.run(
                    ["ollama", "run", model_name, "--verbose"],
                    input="",  # Empty input to just load the model
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode == 0 or "success" in (result.stderr or '').lower():
                    try:
                        self.current_backend = backend
                        self._set_chat_backend(backend)
                    except Exception:
                        pass
                    self.root.after(0, self._on_mount_success)
                else:
                    err = (result.stderr or '').strip()
                    out = (result.stdout or '').strip()
                    error_msg = f"Mount failed: {err or out or 'unknown error'}"
                    self.root.after(0, lambda: self._on_mount_error(error_msg))

            except subprocess.TimeoutExpired:
                self.root.after(0, self._on_mount_success)  # Timeout often means it loaded
            except Exception as e:
                error_msg = f"Mount error: {str(e)}"
                self.root.after(0, lambda: self._on_mount_error(error_msg))

        threading.Thread(target=mount_thread, daemon=True).start()

    def _get_chat_backend(self) -> str:
        try:
            # Prefer an explicit current_backend set during mount/selection
            cb = getattr(self, 'current_backend', None)
            if cb in ('llama_server', 'ollama'):
                return cb
            value = self.backend_settings.get('chat_backend', 'ollama')
            backend = str(value).strip().lower() if value is not None else 'ollama'
            # Do not demote from llama_server here; HTTP layer will surface errors
            return backend or 'ollama'
        except Exception:
            return 'ollama'

    def _set_chat_backend(self, backend: str):
        try:
            backend = (backend or 'ollama').strip().lower()
        except Exception:
            backend = 'ollama'
        self.backend_settings['chat_backend'] = backend or 'ollama'
        self._save_backend_setting('chat_backend', self.backend_settings['chat_backend'])
        try:
            self.current_backend = backend
        except Exception:
            pass

    def _llama_server_base_url(self) -> str:
        try:
            base = self.backend_settings.get('llama_server_base_url') or 'http://127.0.0.1:8002'
            return str(base).rstrip('/') or 'http://127.0.0.1:8002'
        except Exception:
            return 'http://127.0.0.1:8002'

    def _llama_server_default_model(self) -> str:
        try:
            return str(self.backend_settings.get('llama_server_default_model') or '').strip()
        except Exception:
            return ''

    def _llama_server_timeouts(self):
        try:
            connect = float(self.backend_settings.get('llama_server_connect_timeout', 10.0))
        except Exception:
            connect = 10.0
        try:
            request = float(self.backend_settings.get('llama_server_request_timeout', 120.0))
        except Exception:
            request = 120.0
        return connect, request

    def _llama_server_headers(self):
        try:
            headers = self.backend_settings.get('llama_server_headers', {})
            return headers if isinstance(headers, dict) else {}
        except Exception:
            return {}

    # --- Agents roster helpers ------------------------------------------------
    def _emit_agents_roster_updated(self, roster: list) -> None:
        """Notify host about roster updates via Tk virtual event and cache locally.

        Uses <<AgentsRosterUpdated>> so TrainingGUI can persist/apply without
        requiring set_active_agents() on the Tk root. Falls back to direct call
        when available.
        """
        try:
            self._last_known_roster = list(roster or [])
        except Exception:
            self._last_known_roster = []
        # Write snapshot so other components can read updated roster
        try:
            snap_dir = Path('Data') / 'user_prefs'
            snap_dir.mkdir(parents=True, exist_ok=True)
            (snap_dir / 'agents_roster.runtime.json').write_text(json.dumps(self._last_known_roster, indent=2))
        except Exception:
            pass
        try:
            for entry in self._last_known_roster:
                name = (entry.get('name') or '').strip()
                port = entry.get('_server_port')
                if name and port:
                    self._agent_server_ports[name] = int(port)
        except Exception:
            pass
        try:
            payload = json.dumps(self._last_known_roster)
        except Exception:
            payload = '[]'
        try:
            self.root.event_generate('<<AgentsRosterUpdated>>', when='tail', data=payload)
            log_message(
                f"AGENT_MOUNT: operation=roster_apply_via_event size={len(self._last_known_roster)}",
                level='INFO'
            )
        except Exception as e:
            log_message(
                f"AGENT_MOUNT: operation=roster_event_emit_failed error='{e}'",
                level='ERROR'
            )
            # Best-effort fallback if host exposes the method directly
            try:
                if hasattr(self.root, 'set_active_agents') and callable(getattr(self.root, 'set_active_agents')):
                    self.root.set_active_agents(self._last_known_roster)
                    log_message(
                        f"AGENT_MOUNT: operation=roster_apply_fallback_call size={len(self._last_known_roster)}",
                        level='DEBUG'
                    )
            except Exception:
                pass

    def _get_live_roster(self) -> list:
        """Retrieve the current agents roster.

        Priority:
          1) TrainingGUI via root.get_active_agents()
          2) Snapshot file Data/user_prefs/agents_roster.runtime.json
          3) Last known cache from this tab
        """
        # 1) Host method
        try:
            if hasattr(self.root, 'get_active_agents') and callable(getattr(self.root, 'get_active_agents')):
                roster = self.root.get_active_agents() or []
                if isinstance(roster, list) and roster:
                    try:
                        for entry in roster:
                            name = (entry.get('name') or '').strip()
                            port = entry.get('_server_port')
                            if name and port:
                                self._agent_server_ports[name] = int(port)
                    except Exception:
                        pass
                    return roster
        except Exception:
            pass
        # 2) Snapshot file
        try:
            p = Path('Data') / 'user_prefs' / 'agents_roster.runtime.json'
            if p.exists():
                roster = json.loads(p.read_text()) or []
                if isinstance(roster, list):
                    return roster
        except Exception:
            pass
        # 3) Local cache
        try:
            return list(self._last_known_roster or [])
        except Exception:
            return []

    def _restore_session_roster(self, roster: list) -> None:
        """Best-effort restoration of a session's saved roster without clobbering live state.

        Newer Quick Actions store the roster for context; the existing Agents tab still
        owns authoritative mounts. Only apply the saved roster when the host has none
        so we avoid overwriting a project-specific selection that may already be active.
        """
        if not isinstance(roster, list) or not roster:
            return

        # Cache for quick indicators regardless of whether we apply to the host.
        try:
            self._last_known_roster = list(roster)
        except Exception:
            pass
        try:
            for entry in roster:
                name = (entry.get('name') or '').strip()
                port = entry.get('_server_port')
                if name and port:
                    self._agent_server_ports[name] = int(port)
        except Exception:
            pass

        # Skip if host already has an active roster (respect Agents tab state).
        try:
            if hasattr(self.root, 'get_active_agents') and callable(getattr(self.root, 'get_active_agents')):
                current = self.root.get_active_agents() or []
                if isinstance(current, list) and current:
                    log_message(
                        "CHAT_INTERFACE: Skipping session roster restore (active roster already present)",
                        level='DEBUG'
                    )
                    return
        except Exception:
            pass

        # Apply when host exposes setter and no active roster is present.
        try:
            if hasattr(self.root, 'set_active_agents') and callable(getattr(self.root, 'set_active_agents')):
                self.root.set_active_agents(roster)
                log_message("CHAT_INTERFACE: Applied saved session roster (host was empty)", level='INFO')
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Failed to apply saved session roster: {e}", level='ERROR')

    def _port_is_open(self, host: str, port: int, timeout: float = 0.5) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            return False

    def _guess_llama_server_binary(self) -> str:
        """Attempt to find the llama-server binary using settings and common build paths."""
        raw_path = (self.backend_settings.get('llama_server_binary_path') or '').strip()
        candidates = []
        if raw_path:
            candidates.append(Path(raw_path))
        # Common local build directories
        cwd = Path.cwd()
        working_dir = Path(self.backend_settings.get('working_directory') or cwd)
        candidates.extend([
            working_dir / "llama.cpp" / "build" / "bin" / "llama-server",
            cwd / "llama.cpp" / "build" / "bin" / "llama-server",
            Path.home() / "llama.cpp" / "build" / "bin" / "llama-server",
            # Common trainer extras path used on this project
            cwd / "extras" / "gpu-test" / "bin" / "server",
            (Path(__file__).resolve().parents[4] / "extras" / "gpu-test" / "bin" / "server"),
        ])
        # PATH lookup
        try:
            import shutil
            found = shutil.which('llama-server')
            if found:
                candidates.insert(0, Path(found))
        except Exception:
            pass
        for candidate in candidates:
            try:
                if candidate and candidate.exists() and os.access(str(candidate), os.X_OK):
                    return str(candidate)
            except Exception:
                continue
        return raw_path

    def _llama_server_available(self) -> bool:
        try:
            candidate = self._guess_llama_server_binary()
            if not candidate:
                return False
            p = Path(candidate)
            return p.exists() and os.access(str(p), os.X_OK)
        except Exception:
            return False

    def _resolve_llama_server_model_for_selection(self, selected: str) -> str:
        """Resolve the GGUF path to use based on the user's right-side selection.

        Rules (no fallback):
        - If the selected value is an absolute .gguf path and exists → use it.
        - Else, try to resolve by searching known export locations based on name.
        - Else → return empty string; caller must treat as error.
        """
        try:
            dbg = log_message
        except Exception:
            def dbg(_m):
                pass

        dbg(f"CHAT_MOUNT: _resolve_llama_server_model_for_selection called with selected={selected}")
        try:
            if selected and selected.endswith('.gguf'):
                p = Path(selected)
                exists = p.is_absolute() and p.exists()
                dbg(f"CHAT_MOUNT:   selected ends with .gguf, absolute={p.is_absolute()}, exists={exists}, path={selected}")
                if exists:
                    dbg(f"CHAT_MOUNT:   Returning selected path: {selected}")
                    return selected
        except Exception as e:
            dbg(f"CHAT_MOUNT:   Exception checking selected: {e}")
            pass
        # Fallback search in known export locations using the selected name
        try:
            if selected:
                found = self._search_known_gguf_locations(selected)
                if found:
                    dbg(f"CHAT_MOUNT:   Resolved via search: {found}")
                    return found
        except Exception:
            pass
        dbg(f"CHAT_MOUNT:   No valid GGUF found, returning empty string")
        return ''

    def _search_known_gguf_locations(self, name: str) -> str:
        """Search common export folders for a GGUF matching 'name'."""
        try:
            needle = Path(name).name
            here = Path(__file__).resolve()
            roots = []
            # Search upward for typical exports directories
            for p in [here.parents[i] for i in range(1, min(6, len(here.parents)))]:
                roots.append(p / 'Data' / 'exports' / 'gguf')
                roots.append(p / 'Models' / 'exports' / 'gguf')
            wd = self.backend_settings.get('working_directory')
            if wd:
                roots.append(Path(wd) / 'Data' / 'exports' / 'gguf')
                roots.append(Path(wd) / 'Models' / 'exports' / 'gguf')
            for root in roots:
                try:
                    if not root.exists():
                        continue
                    # Exact filename first
                    cand = root / needle
                    if cand.exists():
                        return str(cand.resolve())
                    # Fuzzy match by basename
                    base = needle.replace('.gguf', '')
                    for gg in root.glob('*.gguf'):
                        if base and base in gg.name:
                            return str(gg.resolve())
                except Exception:
                    continue
        except Exception:
            pass
        return ''

    def _kill_llama_server(self):
        """Kill the managed llama.cpp server process and clean up resources."""
        killed = False
        try:
            if self._llama_server_proc:
                pid = self._llama_server_proc.pid
                log_message(f"CHAT_INTERFACE: Terminating llama-server process (PID {pid})")
                try:
                    self._llama_server_proc.terminate()
                    self._llama_server_proc.wait(timeout=3)
                    killed = True
                except subprocess.TimeoutExpired:
                    log_message(f"CHAT_INTERFACE: Force killing llama-server (PID {pid})")
                    self._llama_server_proc.kill()
                    self._llama_server_proc.wait()
                    killed = True
                except Exception as e:
                    log_message(f"CHAT_INTERFACE: Error killing process: {e}")
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Exception during server kill: {e}")
        finally:
            self._llama_server_proc = None
            # Close log file handles
            try:
                if self._llama_server_stdout_handle:
                    self._llama_server_stdout_handle.close()
                    self._llama_server_stdout_handle = None
            except Exception:
                pass
            try:
                if self._llama_server_stderr_handle:
                    self._llama_server_stderr_handle.close()
                    self._llama_server_stderr_handle = None
            except Exception:
                pass
        return killed

    def kill_all_servers(self):
        """Kill all llama.cpp servers (main + agents) - emergency cleanup button."""
        try:
            self.add_message("system", "🛑 Killing all servers...")
        except Exception:
            pass

        killed_count = 0

        # Kill main chat server
        try:
            if self._kill_llama_server():
                killed_count += 1
                log_message("CHAT_INTERFACE: Killed main llama-server")
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Error killing main server: {e}")

        # Kill all agent servers
        try:
            from agent_server_manager import get_agent_server_manager
            manager = get_agent_server_manager()
            for agent_id in list(manager.active_servers.keys()):
                try:
                    if manager.destroy_server_for_agent(agent_id):
                        killed_count += 1
                except Exception as e:
                    log_message(f"CHAT_INTERFACE: Error killing agent server {agent_id}: {e}")
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Error accessing agent server manager: {e}")

        # Nuclear option: kill any process listening on our ports
        try:
            import subprocess
            port = int(self.backend_settings.get('llama_server_port') or 8002)
            # Use lsof to find process on port and kill it
            result = subprocess.run(['lsof', '-ti', f':{port}'],
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    try:
                        subprocess.run(['kill', '-9', pid], timeout=1)
                        killed_count += 1
                        log_message(f"CHAT_INTERFACE: Force killed process {pid} on port {port}")
                    except Exception:
                        pass
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Error in nuclear cleanup: {e}")

        # Final sweep: pkill any lingering llama-server processes (best-effort)
        try:
            import subprocess
            subprocess.run(['pkill', '-f', 'llama-server'], timeout=1)
            log_message("CHAT_INTERFACE: Issued pkill -f llama-server")
        except Exception:
            pass

        try:
            self.add_message("system", f"✓ Killed {killed_count} server(s)")
        except Exception:
            pass

        log_message(f"CHAT_INTERFACE: Kill all servers complete ({killed_count} killed)")
        # Stop stderr watcher
        try:
            self._stop_llama_stderr_watcher()
        except Exception:
            pass

    def _ensure_llama_server_running(self, selected_model: str, force_start: bool = False):
        """Ensure the llama.cpp server is available; start it if necessary.

        Args:
            selected_model: Model path to load
            force_start: If True, start server even if auto_start is disabled (for manual mount)
        """
        import subprocess
        import time

        host = (self.backend_settings.get('llama_server_host') or '127.0.0.1').strip() or '127.0.0.1'
        port = int(self.backend_settings.get('llama_server_port') or 8001)
        auto_start = bool(self.backend_settings.get('llama_server_auto_start', True))

        # ALWAYS kill any existing server process first to ensure clean state
        try:
            self._kill_llama_server()
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Error during server cleanup: {e}")

        # Check if port is still occupied (orphaned process or external server)
        if self._port_is_open(host, port):
            log_message(f"CHAT_INTERFACE: Port {port} is occupied, attempting cleanup...")
            # Try to kill the process using the port
            killed_any = False
            try:
                result = subprocess.run(['lsof', '-ti', f':{port}'],
                                      capture_output=True, text=True, timeout=2)
                log_message(f"CHAT_INTERFACE: lsof result: returncode={result.returncode}, stdout='{result.stdout.strip()}'")

                if result.returncode == 0 and result.stdout.strip():
                    pids = result.stdout.strip().split('\n')
                    log_message(f"CHAT_INTERFACE: Found {len(pids)} process(es) on port {port}: {pids}")

                    for pid in pids:
                        try:
                            log_message(f"CHAT_INTERFACE: Attempting to kill PID {pid} with SIGKILL...")
                            kill_result = subprocess.run(['kill', '-9', pid],
                                                        capture_output=True, text=True, timeout=2)
                            log_message(f"CHAT_INTERFACE: kill -9 {pid} result: returncode={kill_result.returncode}")

                            if kill_result.returncode == 0:
                                killed_any = True
                                log_message(f"CHAT_INTERFACE: Successfully killed orphaned process {pid}")
                                try:
                                    self.add_message("system", f"Killed orphaned server (PID {pid}) on port {port}")
                                except Exception:
                                    pass
                            else:
                                log_message(f"CHAT_INTERFACE: Failed to kill PID {pid}: {kill_result.stderr}")
                        except Exception as e:
                            log_message(f"CHAT_INTERFACE: Exception killing PID {pid}: {e}")

                    # Wait longer for port to fully release
                    if killed_any:
                        log_message(f"CHAT_INTERFACE: Waiting 2 seconds for port {port} to release...")
                        time.sleep(2)
                else:
                    log_message(f"CHAT_INTERFACE: lsof found no process on port {port}")
            except Exception as e:
                log_message(f"CHAT_INTERFACE: Error in orphaned process cleanup: {e}")

            # Check again after cleanup attempt
            if self._port_is_open(host, port):
                err_msg = f"Port {port} is still occupied after cleanup. Kill server manually with 'Kill All' button."
                log_message(f"CHAT_INTERFACE ERROR: {err_msg}")
                try:
                    self.add_message("error", err_msg)
                except Exception:
                    pass
                return False, f"port {port} still in use after cleanup attempt"
            else:
                log_message(f"CHAT_INTERFACE: Port {port} successfully freed")

        # Respect manual-only mode (unless force_start is True for manual mount)
        if not auto_start and not force_start:
            return False, "auto-start disabled; server not reachable"

        binary = self._guess_llama_server_binary()
        if not binary:
            return False, "llama-server binary not found; update backend settings"
        model = self._resolve_llama_server_model_for_selection(selected_model)
        if not model:
            return False, (
                "Selected model not found as a local .gguf file. "
                "Pick a local GGUF from Collections; no fallback is used."
            )

        # Update base URL to reflect host/port for consistency (always refresh)
        base_url = f"http://{host}:{port}/v1"
        try:
            self.backend_settings['llama_server_base_url'] = base_url
            self._save_backend_setting('llama_server_base_url', base_url)
            _debug_log(f"CHAT_DBG: ensure_server base_url set to {base_url}")
        except Exception:
            pass

        extra = (self.backend_settings.get('llama_server_extra_args') or '').strip()
        gpu_layers = str(self.backend_settings.get('llama_server_gpu_layers', '-1'))  # -1 = all layers on GPU
        threads = str(self.backend_settings.get('cpu_threads', '')).strip()
        cmd = [
            binary,
            "--host", host,
            "--port", str(port),
            "--n-gpu-layers", gpu_layers,
            "--parallel", "2",
            "--model", model,
        ]
        if threads and threads.isdigit():
            cmd.extend(["--threads", threads])
        if extra:
            import shlex
            try:
                cmd.extend(shlex.split(extra))
            except Exception:
                cmd.extend(extra.split())

        # Prepare log files in working directory
        work_dir = Path(self.backend_settings.get('working_directory') or Path.cwd())
        work_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = work_dir / "llama_server_stdout.log"
        stderr_path = work_dir / "llama_server_stderr.log"
        try:
            stdout_handle = open(stdout_path, "a")
            stderr_handle = open(stderr_path, "a")
        except Exception as e:
            return False, f"failed to open log files: {e}"

        try:
            # Set LD_LIBRARY_PATH for shared libraries (Vulkan support)
            import os
            env = os.environ.copy()
            binary_dir = Path(binary).parent
            lib_dir = binary_dir.parent / "lib"
            if lib_dir.exists():
                existing_ld = env.get('LD_LIBRARY_PATH', '')
                env['LD_LIBRARY_PATH'] = f"{lib_dir}:{existing_ld}" if existing_ld else str(lib_dir)

            self._llama_server_proc = subprocess.Popen(
                cmd,
                stdout=stdout_handle,
                stderr=stderr_handle,
                cwd=str(work_dir),
                env=env,
            )
            self._llama_server_stdout_handle = stdout_handle
            self._llama_server_stderr_handle = stderr_handle
            try:
                log_message(f"CHAT_INTERFACE: launching llama-server → {' '.join(cmd)}")
                log_message(f"CHAT_INTERFACE: main server PID {self._llama_server_proc.pid} on {host}:{port}")
            except Exception:
                pass
            # Start stderr watcher to pipe server errors into main debug log
            try:
                self._start_llama_stderr_watcher(str(stderr_path))
            except Exception:
                pass
        except Exception as e:
            try:
                stdout_handle.close()
                stderr_handle.close()
            except Exception:
                pass
            return False, f"failed to launch llama-server: {e}"

        # Wait for readiness (up to ~8 seconds)
        deadline = time.time() + 8.0
        while time.time() < deadline:
            time.sleep(0.3)
            if self._port_is_open(host, port):
                ok, info = self._check_llama_server_connection()
                if ok:
                    return True, f"started ({info})"

        return False, f"server launch timed out; check logs at {stdout_path}"

    def _check_llama_server_connection(self, base_url: Optional[str] = None):
        """Probe the llama.cpp server /v1/models endpoint for availability."""
        import json
        import urllib.request
        import urllib.error

        base = (base_url or self._llama_server_base_url()).rstrip('/')
        url = base + ("/models" if base.endswith("/v1") else "/v1/models")
        connect_timeout, _ = self._llama_server_timeouts()
        timeout = float(connect_timeout or 10.0)

        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
                data = json.loads(raw or "{}")
                models = []
                try:
                    models = [
                        m.get("id") for m in data.get("data", [])
                        if isinstance(m, dict) and m.get("id")
                    ]
                except Exception:
                    models = []
                info = f"{len(models)} model(s) visible" if models else "No models reported"
                return True, info
        except urllib.error.URLError as e:
            reason = getattr(e, 'reason', e)
            return False, f"{reason}"
        except Exception as e:
            return False, str(e)
    def _llm_messages_openai(self, messages_with_system):
        """Ensure chat messages are OpenAI-compatible dictionaries."""
        normalized = []
        try:
            for msg in messages_with_system or []:
                if not isinstance(msg, dict):
                    continue
                role = str(msg.get('role', '') or '').strip().lower()
                content = msg.get('content', '')
                # Support assistant tool messages that may have structured content
                message_obj = {'role': role or 'user'}
                if 'content' in msg:
                    message_obj['content'] = content
                if 'tool_calls' in msg and isinstance(msg['tool_calls'], list):
                    message_obj['tool_calls'] = msg['tool_calls']
                if 'name' in msg:
                    message_obj['name'] = msg['name']
                normalized.append(message_obj)
        except Exception:
            pass
        return normalized

    def _llama_server_chat(self, messages_with_system, tool_schemas, model_override=None, agent_name=None):
        """
        Perform a blocking request to llama.cpp server (OpenAI-compatible) with inference coordination.
        Returns (ok, response_dict, error_message, stopped_flag)

        This method wraps _llama_server_chat_impl with semaphore acquisition to limit
        concurrent LLM inferences and prevent overloading the model server.

        Args:
            messages_with_system: List of message dicts with roles/content
            tool_schemas: Optional tool definitions for function calling
            model_override: Optional model path to use (for agents), overrides current_model
            agent_name: Optional agent name to route to agent's dedicated server port
        """
        # Acquire semaphore to limit concurrent inferences
        if hasattr(self, '_llm_inference_semaphore'):
            acquired = self._llm_inference_semaphore.acquire(blocking=True, timeout=300)
            if not acquired:
                log_message("LLM_QUEUE: Timeout waiting for inference slot")
                return False, None, "Inference queue timeout (too many concurrent requests)", False

            # Track active count
            with self._llm_inference_count_lock:
                self._llm_inference_active_count += 1
                active_count = self._llm_inference_active_count

            log_message(f"LLM_QUEUE: Acquired inference slot (active={active_count}, agent={agent_name or 'main'})")

            try:
                # Call actual implementation
                result = self._llama_server_chat_impl(messages_with_system, tool_schemas, model_override, agent_name)
                return result
            finally:
                # Always release semaphore
                self._llm_inference_semaphore.release()
                with self._llm_inference_count_lock:
                    self._llm_inference_active_count -= 1
                    active_count = self._llm_inference_active_count
                log_message(f"LLM_QUEUE: Released inference slot (active={active_count})")
        else:
            # No semaphore (legacy mode), call directly
            return self._llama_server_chat_impl(messages_with_system, tool_schemas, model_override, agent_name)

    def _llama_server_chat_impl(self, messages_with_system, tool_schemas, model_override=None, agent_name=None):
        """
        Internal implementation of llama.cpp server request (OpenAI-compatible).
        Do not call directly - use _llama_server_chat which handles inference coordination.

        Returns (ok, response_dict, error_message, stopped_flag)

        Args:
            messages_with_system: List of message dicts with roles/content
            tool_schemas: Optional tool definitions for function calling
            model_override: Optional model path to use (for agents), overrides current_model
            agent_name: Optional agent name to route to agent's dedicated server port
        """
        import json
        import urllib.request
        import urllib.error

        # Respect stop request before sending
        try:
            if self._stop_event.is_set():
                return False, None, "Request cancelled", True
        except Exception:
            pass

        model_name = model_override or self._llama_server_default_model() or (self.current_model or '')
        if not model_name:
            return False, None, "No default model configured for Llama Server", False

        payload = {
            "model": model_name,
            "messages": self._llm_messages_openai(messages_with_system),
            "stream": False,
            "temperature": float(self.session_temperature or 0.6),
        }
        if tool_schemas:
            payload["tools"] = tool_schemas
            payload["tool_choice"] = "auto"

        # Debug: Log complete request payload
        try:
            log_message(f"MODEL_INPUT DEBUG: Request to {model_name} - {len(payload['messages'])} messages, {len(tool_schemas) if tool_schemas else 0} tools")
            for idx, msg in enumerate(payload['messages']):
                role = msg.get('role', 'unknown')
                content = str(msg.get('content', ''))[:300]
                tool_calls = msg.get('tool_calls', [])
                if tool_calls:
                    log_message(f"MODEL_INPUT DEBUG: Msg[{idx}] role={role}, tool_calls={len(tool_calls)}: {[tc.get('function', {}).get('name') for tc in tool_calls]}")
                else:
                    log_message(f"MODEL_INPUT DEBUG: Msg[{idx}] role={role}, content={content}")
        except Exception as e:
            log_message(f"MODEL_INPUT DEBUG: Failed to log payload: {e}")

        # Do NOT auto-start or relaunch servers here. Mount buttons manage server lifecycle.
        # Optionally, allow opt-in auto-prep if explicitly enabled by user.
        try:
            if bool(self.backend_settings.get('allow_llama_autostart_in_chat', False)):
                has_tools = bool(tool_schemas and isinstance(tool_schemas, list) and len(tool_schemas) > 0)
                has_roles = bool(payload.get('messages'))
                try:
                    model_name = self._llama_server_default_model() or (self.current_model or '')
                    self._ensure_llama_server_running(model_name)
                except Exception:
                    pass
        except Exception:
            pass

        data = json.dumps(payload).encode('utf-8')
        headers = {"Content-Type": "application/json"}
        try:
            headers.update(self._llama_server_headers())
        except Exception:
            pass

        connect_timeout, request_timeout = self._llama_server_timeouts()
        timeout = float(request_timeout or 120.0)

        # Route to agent's dedicated server if agent_name is provided
        base = self._llama_server_base_url()
        if agent_name:
            agent_port = self._get_agent_server_port(agent_name)
            if agent_port:
                base = f"http://127.0.0.1:{agent_port}"

        if base.endswith('/v1'):
            url = f"{base}/chat/completions"
        elif '/v1/' in base:
            url = f"{base.rstrip('/')}/chat/completions"
        else:
            url = f"{base.rstrip('/')}/v1/chat/completions"

        # Debug: log destination and payload size
        try:
            log_message(f"LLAMA_CHAT: POST {url} bytes={len(data or b'')}")
        except Exception:
            pass
        _debug_log(f"CHAT_DBG: llama_chat_request url={url} bytes={len(data or b'')} agent={agent_name}")

        # Cap overly long timeouts to keep UI responsive
        try:
            # Allow longer default timeouts for Llama Server responses (some models take >30s)
            max_to = float(self.backend_settings.get('max_request_timeout', 120.0))
            timeout = min(timeout, max_to)
        except Exception:
            pass
        # Extra debug: ensure we log that we're about to POST (helps diagnose silent failures)
        try:
            log_message(f"LLAMA_CHAT: POSTing to {url} with payload_messages={len(payload.get('messages',[]))} last_user_snippet='{(payload.get('messages') and payload.get('messages')[-1].get('content','')[:200])}'")
        except Exception:
            pass

        # LOG POINT 4: HTTP request sent (for agent tool calls)
        if agent_name:
            caller_agent = getattr(self, '_current_chat_agent', {}).get('name') if hasattr(self, '_current_chat_agent') and self._current_chat_agent else None
            log_message(
                f"AGENT_TOOL_CALL: operation=http_request_sent caller={caller_agent or 'orchestrator'} "
                f"target={agent_name} url={url} payload_size={len(data)} timeout={timeout}"
            )

        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode('utf-8', errors='ignore')
                if not raw:
                    return False, None, "Empty response from Llama Server", False
                try:
                    response_obj = json.loads(raw)
                except json.JSONDecodeError as e:
                    return False, None, f"Invalid JSON from Llama Server: {e}", False

            # Debug: Log model response details
            try:
                choices = response_obj.get('choices', [])
                if choices:
                    first_choice = choices[0]
                    message = first_choice.get('message', {})
                    role = message.get('role', 'unknown')
                    content = str(message.get('content', ''))[:500]
                    tool_calls = message.get('tool_calls', [])
                    finish_reason = first_choice.get('finish_reason', 'unknown')

                    log_message(f"MODEL_OUTPUT DEBUG: Response from {model_name} - role={role}, finish={finish_reason}, content_len={len(str(message.get('content', '')))}, tool_calls={len(tool_calls)}")
                    if tool_calls:
                        for tc in tool_calls[:3]:  # Log first 3 tool calls
                            func = tc.get('function', {})
                            log_message(f"MODEL_OUTPUT DEBUG: Tool call - name={func.get('name')}, args_preview={str(func.get('arguments', ''))[:200]}")
                    else:
                        log_message(f"MODEL_OUTPUT DEBUG: Content preview: {content}")
            except Exception as e:
                log_message(f"MODEL_OUTPUT DEBUG: Failed to log response: {e}")

            # LOG POINT 5: HTTP response received (for agent tool calls)
            if agent_name:
                caller_agent = getattr(self, '_current_chat_agent', {}).get('name') if hasattr(self, '_current_chat_agent') and self._current_chat_agent else None
                log_message(
                    f"AGENT_TOOL_CALL: operation=http_response_received caller={caller_agent or 'orchestrator'} "
                    f"target={agent_name} status=200 response_size={len(raw)}"
                )

            try:
                log_message(f"LLAMA_CHAT: OK len={len(raw)} preview={(raw[:200] if isinstance(raw, str) else str(raw)[:200])}")
            except Exception:
                pass
            _debug_log(f"CHAT_DBG: llama_chat_success url={url} len={len(raw)}")
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode('utf-8', errors='ignore')
            except Exception:
                detail = ''
            # Auto-recovery when tools require Jinja templates
            msg = f"{detail or e.reason}"
            try:
                log_message(f"LLAMA_CHAT: HTTPError {e.code} detail={msg[:240]}")
            except Exception:
                pass
            # Handle 503 "Loading model" - retry with exponential backoff
            if e.code == 503 and 'loading model' in msg.lower():
                import time
                max_retries = 5
                retry_delays = [2, 4, 6, 8, 10]  # Total wait time: up to 30 seconds

                for retry_num in range(max_retries):
                    delay = retry_delays[retry_num]
                    try:
                        log_message(f"LLAMA_CHAT: Model loading, retrying in {delay}s (attempt {retry_num + 1}/{max_retries})")
                    except Exception:
                        pass

                    time.sleep(delay)

                    # Retry the request
                    try:
                        req_retry = urllib.request.Request(url, data=data, headers=headers, method="POST")
                        with urllib.request.urlopen(req_retry, timeout=timeout) as resp_retry:
                            raw_retry = resp_retry.read().decode('utf-8', errors='ignore')
                            if not raw_retry:
                                continue  # Try next retry
                            try:
                                response_obj = json.loads(raw_retry)
                                try:
                                    log_message(f"LLAMA_CHAT: Model loaded successfully after {retry_num + 1} retries")
                                except Exception:
                                    pass
                                return True, response_obj, None, False
                            except json.JSONDecodeError:
                                continue  # Try next retry
                    except urllib.error.HTTPError as e_retry:
                        # Still loading or other error - continue retrying
                        if e_retry.code == 503:
                            continue  # Try next retry
                        else:
                            # Different error - break and report it
                            break
                    except Exception:
                        continue  # Try next retry

                # All retries exhausted
                return False, None, "Model is still loading after 30 seconds. Please wait and try again.", False

            # Handle context overflow with a helpful action
            if e.code == 400 and ('exceed_context_size' in (detail or '').lower() or 'exceeds the available context size' in (detail or '').lower()):
                try:
                    from tkinter import messagebox
                    self.root.after(0, lambda: messagebox.showinfo('Context Limit', "The request exceeded the model's context window. Prompt diagnostics have been logged in the Debug tab."))
                except Exception:
                    pass
                return False, None, self._handle_context_overflow("Context limit reached"), False
            if e.code == 500 and 'tools param requires --jinja' in (detail or '').lower() and bool(self.backend_settings.get('allow_llama_autostart_in_chat', False)):
                try:
                    # Ensure flags and relaunch on a free port to bypass external instance
                    self._force_relaunch_llama_server_for_tools()
                    # Recompute base URL and headers in case settings changed (e.g., new port)
                    try:
                        headers = {"Content-Type": "application/json"}
                        headers.update(self._llama_server_headers())
                    except Exception:
                        pass
                    base = self._llama_server_base_url()
                    if base.endswith('/v1'):
                        url2 = f"{base}/chat/completions"
                    elif '/v1/' in base:
                        url2 = f"{base.rstrip('/')}/chat/completions"
                    else:
                        url2 = f"{base.rstrip('/')}/v1/chat/completions"
                    # Retry once against the possibly-updated server
                    req2 = urllib.request.Request(url2, data=data, headers=headers, method="POST")
                    with urllib.request.urlopen(req2, timeout=timeout) as resp2:
                        raw2 = resp2.read().decode('utf-8', errors='ignore')
                        if not raw2:
                            return False, None, "Empty response from Llama Server", False
                        try:
                            response_obj = json.loads(raw2)
                        except json.JSONDecodeError as e2:
                            return False, None, f"Invalid JSON from Llama Server: {e2}", False
                        return True, response_obj, None, False
                except Exception:
                    # Offer to switch backend as a fallback
                    try:
                        from tkinter import messagebox
                        hint = self._build_llama_server_debug_hint()
                        msg = 'Llama Server requires Jinja for tools. Switch to Ollama instead?'
                        if hint:
                            msg = msg + "\n\nDetails:\n" + hint
                        if messagebox.askyesno('Switch Backend?', msg):
                            self._set_chat_backend('ollama')
                            # Inform user to resend
                            return False, None, "Switched to Ollama. Please resend.", False
                    except Exception:
                        pass
            return False, None, f"Llama Server HTTP error {e.code}: {msg}", False
        except urllib.error.URLError as e:
            reason = getattr(e, 'reason', e)
            try:
                log_message(f"LLAMA_CHAT: URLError {reason}")
            except Exception:
                pass
            return False, None, f"Llama Server connection failed: {reason}", False
        except Exception as e:
            return False, None, f"Llama Server request failed: {e}", False

        return True, response_obj, None, False

    def _start_llama_stderr_watcher(self, path: str):
        """Tail the llama-server stderr file and mirror lines into backend debug log with error highlighting."""
        try:
            # Stop any existing watcher first
            self._stop_llama_stderr_watcher()
        except Exception:
            pass
        self._stderr_watcher_stop = False
        self._stderr_watcher_path = path
        import threading, time
        def _run():
            try:
                local_log = log_message
                local_error = log_error
                import os
                # Open file and seek to end to avoid dumping historical noise
                with open(path, 'r', errors='ignore') as f:
                    try:
                        f.seek(0, os.SEEK_END)
                    except Exception:
                        pass
                    while not self._stderr_watcher_stop:
                        line = f.readline()
                        if not line:
                            time.sleep(0.2)
                            continue
                        msg = line.strip()
                        if not msg:
                            continue
                        low = msg.lower()
                        # Heuristic for error highlighting
                        if any(k in low for k in ('error', 'failed', 'fatal', 'exception', 'oom', 'panic')):
                            try:
                                local_error(f"LLAMA_STDERR: {msg}", auto_capture=False)
                            except Exception:
                                local_log(f"LLAMA_STDERR: {msg}")
                        else:
                            local_log(f"LLAMA_STDERR: {msg}")
            except Exception:
                # Silent exit on watcher failure
                pass
        self._stderr_watcher_thread = threading.Thread(target=_run, daemon=True)
        self._stderr_watcher_thread.start()

    def _stop_llama_stderr_watcher(self):
        try:
            self._stderr_watcher_stop = True
        except Exception:
            pass
        try:
            t = self._stderr_watcher_thread
            if t and t.is_alive():
                t.join(timeout=0.5)
        except Exception:
            pass

    def _ensure_llama_server_prompt_ready(self, has_tools: bool, has_roles: bool):
        """Ensure llama-server flags match the chat style (tools vs. role chat).

        If the server is already running externally without our process handle,
        we will move to a free port and launch our own instance with the
        required flags so that tool calls work without switching backends.
        """
        try:
            extra = (self.backend_settings.get('llama_server_extra_args') or '').strip()
            parts = extra.split()
            need_jinja = ('--jinja' not in parts)
            need_template = ('--chat-template' not in parts)
            # Select template based on type
            desired_template = ''
            if has_tools:
                desired_template = self._find_jinja_template_path(mode='functions')
            elif has_roles:
                desired_template = self._find_jinja_template_path(mode='chat')
            # Apply only if necessary
            changed = False
            if need_jinja:
                parts.append('--jinja'); changed = True
            if need_template and desired_template:
                parts.extend(['--chat-template', desired_template]); changed = True
            if changed:
                try:
                    log_message(f"AUTOJINJA: updating llama_server_extra_args → {' '.join(parts)}")
                except Exception:
                    pass
                # Always keep --jinja when tools/roles require Jinja even if we
                # cannot locate a template file; many GGUFs embed templates.
                self.backend_settings['llama_server_extra_args'] = ' '.join(parts).strip()
                try:
                    self._save_backend_setting('llama_server_extra_args', self.backend_settings['llama_server_extra_args'])
                except Exception:
                    pass
                # Restart server to take effect
                try:
                    if getattr(self, '_llama_server_proc', None) and self._llama_server_proc.poll() is None:
                        self._llama_server_proc.terminate()
                        import time as _t
                        _t.sleep(0.6)
                except Exception:
                    pass
                # If a server is running but not ours, relocate to a free port
                try:
                    host = (self.backend_settings.get('llama_server_host') or '127.0.0.1').strip() or '127.0.0.1'
                    port = int(self.backend_settings.get('llama_server_port') or 8001)
                    server_running = self._port_is_open(host, port)
                    have_handle = bool(getattr(self, '_llama_server_proc', None) and self._llama_server_proc.poll() is None)
                    if server_running and not have_handle:
                        new_port = None
                        for p in range(port + 1, port + 11):
                            if not self._port_is_open(host, p):
                                new_port = p
                                break
                        if new_port:
                            try:
                                log_message(f"AUTOJINJA: external llama-server detected on :{port}; relaunching our tool-ready instance on :{new_port}")
                            except Exception:
                                pass
                            self.backend_settings['llama_server_port'] = new_port
                            try:
                                self._save_backend_setting('llama_server_port', new_port)
                            except Exception:
                                pass
                            base_url = f"http://{host}:{new_port}"
                            self.backend_settings['llama_server_base_url'] = base_url
                            try:
                                self._save_backend_setting('llama_server_base_url', base_url)
                            except Exception:
                                pass
                except Exception:
                    pass
                model_name = self._llama_server_default_model() or (self.current_model or '')
                self._ensure_llama_server_running(model_name)
        except Exception:
            pass

    def _force_relaunch_llama_server_for_tools(self):
        """Force-launch our own llama-server instance with tool-ready flags on a free port.

        Used when the remote server responds with 'tools param requires --jinja'
        even though our settings already include Jinja; this indicates the live
        process was started externally without required flags.
        """
        try:
            # Ensure flags in settings
            extra = (self.backend_settings.get('llama_server_extra_args') or '').strip()
            parts = extra.split()
            if '--jinja' not in parts:
                parts.append('--jinja')
            # Prefer a functions/openai template if available
            tpl = self._find_jinja_template_path(mode='functions')
            if tpl and '--chat-template' not in parts:
                parts.extend(['--chat-template', tpl])
            self.backend_settings['llama_server_extra_args'] = ' '.join(parts).strip()
            try:
                self._save_backend_setting('llama_server_extra_args', self.backend_settings['llama_server_extra_args'])
            except Exception:
                pass

            # Move to a free port to avoid colliding with external server
            host = (self.backend_settings.get('llama_server_host') or '127.0.0.1').strip() or '127.0.0.1'
            port = int(self.backend_settings.get('llama_server_port') or 8001)
            new_port = None
            for p in range(port + 1, port + 16):
                if not self._port_is_open(host, p):
                    new_port = p
                    break
            if new_port:
                self.backend_settings['llama_server_port'] = new_port
                try:
                    self._save_backend_setting('llama_server_port', new_port)
                except Exception:
                    pass
                base_url = f"http://{host}:{new_port}"
                self.backend_settings['llama_server_base_url'] = base_url
                try:
                    self._save_backend_setting('llama_server_base_url', base_url)
                except Exception:
                    pass
                try:
                    log_message(f"AUTOJINJA: forcing relaunch on :{new_port} with args: {self.backend_settings['llama_server_extra_args']}")
                except Exception:
                    pass

            # Start our instance with current or default model
            model_name = self._llama_server_default_model() or (self.current_model or '')
            self._ensure_llama_server_running(model_name)
        except Exception:
            pass

    def _find_jinja_template_path(self, mode: str = 'auto') -> str:
        """Find a Jinja chat template suitable for the mode ('functions' or 'chat')."""
        try:
            base = Path(__file__).resolve().parents[3] / 'llama.cpp' / 'models' / 'templates'
            if base.exists():
                candidates = sorted(base.glob('*.jinja'))
                if not candidates:
                    return ''
                lower = [p for p in candidates]
                if mode == 'functions':
                    pri = [p for p in lower if any(k in p.name.lower() for k in ['function','openai'])]
                    return str((pri[0] if pri else candidates[0]).resolve())
                if mode == 'chat':
                    pri = [p for p in lower if any(k in p.name.lower() for k in ['chat', 'chatml', 'role'])]
                    return str((pri[0] if pri else candidates[0]).resolve())
                return str(candidates[0].resolve())
        except Exception:
            pass
        return ''

    def _build_llama_server_debug_hint(self) -> str:
        """Assemble helpful debug details for dialogs when tools fail."""
        try:
            host = (self.backend_settings.get('llama_server_host') or '127.0.0.1')
            port = int(self.backend_settings.get('llama_server_port') or 8001)
            base = self.backend_settings.get('llama_server_base_url', '')
            args = (self.backend_settings.get('llama_server_extra_args') or '').strip()
            tpl = 'yes' if '--chat-template' in args else 'no'
            jinja = 'yes' if '--jinja' in args else 'no'
            have_handle = bool(getattr(self, '_llama_server_proc', None) and self._llama_server_proc.poll() is None)
            lines = [
                f"Host/Port: {host}:{port}",
                f"Base URL: {base or '(unset)'}",
                f"Extra args: {args or '(none)'}",
                f"Flags → jinja:{jinja}, template_flag:{tpl}",
                f"Process handle: {'owned' if have_handle else 'external/unknown'}",
            ]
            return "\n".join(lines)
        except Exception:
            return ''

    def _process_model_response(self, response_data, user_message):
        """Process a unified model response, handling tools and regular replies."""
        if not isinstance(response_data, dict):
            log_message("CHAT_INTERFACE ERROR: Invalid response format (expected dict)")
            self.root.after(0, lambda: self.add_message("error", "Model returned unexpected response format"))
            return

        # Normalize message structure (support OpenAI-style choices arrays)
        message_data = response_data.get("message")
        if not isinstance(message_data, dict):
            try:
                choices = response_data.get("choices", [])
                if choices and isinstance(choices[0], dict):
                    message_data = choices[0].get("message", {})
            except Exception:
                message_data = {}

        if "error" in response_data:
            error_msg = response_data.get("error")
            log_message(f"CHAT_INTERFACE ERROR: Model API error: {error_msg}")
            self.root.after(0, lambda: self.add_message("error", f"Model error: {error_msg}"))
            return

        if not isinstance(message_data, dict):
            log_message("CHAT_INTERFACE ERROR: Missing message payload from model")
            self.root.after(0, lambda: self.add_message("error", "Model response missing message data"))
            return

        # Training mode: log RAG retrieval record for dataset generation
        try:
            if bool(getattr(self, 'training_mode_enabled', False)) and self._is_rag_active():
                self._log_rag_training_example(query=user_message)
                # Auto-training trigger
                self._maybe_trigger_auto_training()
        except Exception:
            pass

        # Apply Quality Assurance to response if enabled
        if self.quality_assurance:
            try:
                qa_result = self.quality_assurance.assess_quality(response_data)
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(
                        f"DEBUG: QA assessment score: {qa_result.get('score', 0.0)}, "
                        f"passed: {qa_result.get('passed', True)}"
                    )

                # Auto-recovery if enabled and QA failed
                if self.advanced_settings.get('quality_assurance', {}).get('auto_recovery', True):
                    if not qa_result.get('passed', True):
                        if self.backend_settings.get('enable_debug_logging', False):
                            log_message("DEBUG: QA auto-recovery triggered due to low quality")
                        # Future: add retry logic
            except Exception as e:
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Quality Assurance error: {e}")

        # Apply Format Translator if enabled and no standard tool_calls
        tool_calls = message_data.get("tool_calls", [])
        if not tool_calls and self.format_translator:
            try:
                response_content = message_data.get("content", "")
                translated = self.format_translator.translate(response_content)
                if translated:
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Format Translator detected tool call: {translated.get('name', 'unknown')}")
                    # Convert to tool_call format
                    tool_calls = [{
                        "function": {
                            "name": translated.get("name", ""),
                            "arguments": translated.get("args", {})
                        }
                    }]
            except Exception as e:
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Format Translator error: {e}")

        # Check for tool calls
        if tool_calls:
            log_message(f"CHAT_INTERFACE: Model requested {len(tool_calls)} tool calls")
            self.root.after(0, lambda: self.handle_tool_calls(tool_calls, message_data))
            return

        # Regular response
        response_content = message_data.get("content", "")

        if not response_content or response_content.strip() == "":
            log_message("CHAT_INTERFACE WARNING: Model returned empty response")
            log_message(f"CHAT_INTERFACE DEBUG: Full response data: {response_data}")
            response_content = "[Model returned empty response]"

        self.chat_history.append({"role": "assistant", "content": response_content})
        self._chat_dirty = True

        self.root.after(0, lambda: self.add_message("assistant", response_content))

        # Add skill rating integration
        self.root.after(0, lambda: self._add_skill_rating_for_response(response_content))

        log_message("CHAT_INTERFACE: Response generated successfully")
        try:
            self.root.after(0, self.reset_buttons)
        except Exception as e:
            _debug_log(f"CHAT_DBG: process_response reset error instance={id(self)} err={e}")

        if self.backend_settings.get('auto_save_history', True):
            self.root.after(0, self._auto_save_conversation)

    def _open_backend_selector(self):
        try:
            if hasattr(self, '_backend_selector_win') and self._backend_selector_win and self._backend_selector_win.winfo_exists():
                try:
                    self._backend_selector_win.lift()
                    self._backend_selector_win.focus_force()
                except Exception:
                    pass
                return
            win = tk.Toplevel(self.root)
            self._backend_selector_win = win
            win.title("Chat Backend")
            win.resizable(False, False)
            container = ttk.Frame(win, padding=10)
            container.pack(fill=tk.BOTH, expand=True)

            ttk.Label(container, text="Select chat backend:", style='CategoryPanel.TLabel').pack(anchor=tk.W)

            backend_var = tk.StringVar(value=self._get_chat_backend())
            options = [
                ('ollama', 'Ollama (default)'),
                ('llama_server', 'Llama.cpp Server (Vulkan/OpenAI API)'),
            ]
            btns = ttk.Frame(container)
            btns.pack(fill=tk.X, pady=(6, 8))
            llama_available = self._llama_server_available()
            if not llama_available and backend_var.get() == 'llama_server':
                backend_var.set('ollama')
            for value, label in options:
                state = tk.NORMAL
                text = label
                if value == 'llama_server' and not llama_available:
                    state = tk.DISABLED
                    text = label + " (binary not detected)"
                ttk.Radiobutton(btns, text=text, value=value, variable=backend_var, state=state).pack(anchor=tk.W, pady=2)

            if not llama_available:
                ttk.Label(
                    container,
                    text="Tip: configure 'llama_server_binary_path' in Custom Code settings once llama.cpp server is installed.",
                    style='Config.TLabel', wraplength=360
                ).pack(anchor=tk.W, pady=(0, 6))

            ttk.Separator(container, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)

            url_var = tk.StringVar(value=self.backend_settings.get('llama_server_base_url', 'http://127.0.0.1:8002'))
            model_var = tk.StringVar(value=self.backend_settings.get('llama_server_default_model', ''))
            bin_var = tk.StringVar(value=self.backend_settings.get('llama_server_binary_path', ''))
            xargs_var = tk.StringVar(value=self.backend_settings.get('llama_server_extra_args', ''))
            ttk.Label(container, text="Llama Server base URL:", style='Config.TLabel').pack(anchor=tk.W)
            url_entry = ttk.Entry(container, textvariable=url_var, width=38)
            url_entry.pack(fill=tk.X, pady=(2, 6))
            ttk.Label(container, text="Default model (optional):", style='Config.TLabel').pack(anchor=tk.W)
            model_entry = ttk.Entry(container, textvariable=model_var, width=38)
            model_entry.pack(fill=tk.X, pady=(2, 6))
            ttk.Label(container, text="Binary path (optional):", style='Config.TLabel').pack(anchor=tk.W)
            ttk.Entry(container, textvariable=bin_var, width=38).pack(fill=tk.X, pady=(2, 6))
            ttk.Label(container, text="Extra args (optional):", style='Config.TLabel').pack(anchor=tk.W)
            ttk.Entry(container, textvariable=xargs_var, width=38).pack(fill=tk.X, pady=(2, 6))

            def _apply_and_close():
                try:
                    selected_backend = backend_var.get().strip().lower() or 'ollama'
                except Exception:
                    selected_backend = 'ollama'
                self._set_chat_backend(selected_backend)
                base_url = url_var.get().strip() or 'http://127.0.0.1:8002'
                self.backend_settings['llama_server_base_url'] = base_url
                self.backend_settings['llama_server_default_model'] = model_var.get().strip()
                self._save_backend_setting('llama_server_base_url', self.backend_settings['llama_server_base_url'])
                self._save_backend_setting('llama_server_default_model', self.backend_settings['llama_server_default_model'])
                self.backend_settings['llama_server_binary_path'] = bin_var.get().strip()
                self._save_backend_setting('llama_server_binary_path', self.backend_settings['llama_server_binary_path'])
                self.backend_settings['llama_server_extra_args'] = xargs_var.get().strip()
                self._save_backend_setting('llama_server_extra_args', self.backend_settings['llama_server_extra_args'])
                self.add_message('system', f"Backend set to {selected_backend}")
                self._update_quick_indicators()
                if selected_backend == 'llama_server' and not llama_available:
                    try:
                        from tkinter import messagebox
                        messagebox.showinfo(
                            "Llama Server",
                            "llama-server binary was not detected. Configure the binary path or install llama.cpp before enabling auto-start.")
                    except Exception:
                        pass
                    try:
                        self.backend_settings['llama_server_auto_start'] = False
                        self._save_backend_setting('llama_server_auto_start', False)
                    except Exception:
                        pass
            def _close():
                try:
                    win.destroy()
                except Exception:
                    pass
                finally:
                    try:
                        self._backend_selector_win = None
                    except Exception:
                        pass

            action_row = ttk.Frame(container)
            action_row.pack(fill=tk.X, pady=(8, 0))
            ttk.Button(action_row, text="Apply", style='Select.TButton', command=lambda: (_apply_and_close(), _close())).pack(side=tk.LEFT)
            ttk.Button(action_row, text="Cancel", command=_close).pack(side=tk.LEFT, padx=6)

            try:
                win.transient(self.root)
                win.grab_set()
                win.focus_force()
            except Exception:
                pass
        except Exception:
            pass

    # --- Quick Actions gear popup ---------------------------------------
    def _open_quick_actions(self):
        try:
            # If already open, focus it
            if hasattr(self, '_qa_win') and self._qa_win and self._qa_win.winfo_exists():
                try:
                    self._qa_win.lift(); self._qa_win.focus_force()
                except Exception:
                    pass
                return
            win = tk.Toplevel(self.root)
            self._qa_win = win
            win.title('Quick Actions')
            win.resizable(True, True)
            try:
                # Compact dialog near the gear button (slightly larger for readability)
                w, h = 520, 300
                bx = self.quick_actions_btn.winfo_rootx()
                by = self.quick_actions_btn.winfo_rooty()
                ax = bx
                ay = max(0, by - h - 8)
                self._qa_anchor = (ax, ay)
                win.geometry(f"{w}x{h}+{ax}+{ay}")
            except Exception:
                pass
            container = ttk.Frame(win, padding=8)
            container.pack(fill=tk.BOTH, expand=True)
            # Header with close button
            hdr = ttk.Frame(container)
            hdr.pack(fill=tk.X)
            ttk.Label(hdr, text='Quick Actions', style='CategoryPanel.TLabel').pack(side=tk.LEFT)
            ttk.Button(hdr, text='✕', width=3, style='Select.TButton', command=win.destroy).pack(side=tk.RIGHT)
            # Description/tooltip area
            self._qa_desc = ttk.Label(container, text='', style='Config.TLabel')
            self._qa_desc.pack(fill=tk.X, padx=2)

            body_wrapper = ttk.Frame(container)
            body_wrapper.pack(fill=tk.BOTH, expand=True, pady=(6,0))
            self._qa_canvas = tk.Canvas(body_wrapper, highlightthickness=0)
            self._qa_scrollbar = ttk.Scrollbar(body_wrapper, orient=tk.VERTICAL, command=self._qa_canvas.yview)
            self._qa_body = ttk.Frame(self._qa_canvas)
            self._qa_body.bind(
                '<Configure>',
                lambda e: self._qa_canvas.configure(scrollregion=self._qa_canvas.bbox('all'))
            )
            self._qa_canvas.create_window((0, 0), window=self._qa_body, anchor='nw')
            self._qa_canvas.configure(yscrollcommand=self._qa_scrollbar.set)
            self._qa_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self._qa_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            def _on_wheel(event):
                try:
                    delta = event.delta
                    if delta == 0 and hasattr(event, 'num'):
                        delta = 120 if event.num == 4 else -120
                    self._qa_canvas.yview_scroll(int(-delta/120), 'units')
                except Exception:
                    pass
                return 'break'

            def _bind_wheel(_=None):
                try:
                    self._qa_canvas.bind_all('<MouseWheel>', _on_wheel)
                    self._qa_canvas.bind_all('<Button-4>', _on_wheel)
                    self._qa_canvas.bind_all('<Button-5>', _on_wheel)
                except Exception:
                    pass

            def _unbind_wheel(_=None):
                try:
                    self._qa_canvas.unbind_all('<MouseWheel>')
                    self._qa_canvas.unbind_all('<Button-4>')
                    self._qa_canvas.unbind_all('<Button-5>')
                except Exception:
                    pass

            self._qa_canvas.bind('<Enter>', _bind_wheel)
            self._qa_canvas.bind('<Leave>', _unbind_wheel)

            self._qa_show_main()

            # Auto-hide when clicking away if on main view
            def _maybe_hide(_e=None):
                try:
                    if getattr(self, '_qa_view', 'main') == 'main':
                        # Delay slightly to allow focusing internal widgets
                        def _check():
                            try:
                                f = self.root.focus_get()
                                if f is None or not str(f).startswith(str(self._qa_win)):
                                    if self._qa_win and self._qa_win.winfo_exists():
                                        self._qa_win.destroy()
                            except Exception:
                                pass
                        self.root.after(120, _check)
                except Exception:
                    pass
            try:
                win.bind('<FocusOut>', _maybe_hide)
            except Exception:
                pass
        except Exception:
            pass

    # --- Agentic Project toggles ---------------------------------------
    def _toggle_agentic_project_session(self):
        """Toggle Agentic Project ON/OFF for this chat session only.
        None -> True, True -> False, False -> None (cycle through states to allow reverting to default).
        """
        try:
            cur = getattr(self, 'agentic_project_override', None)
            if cur is None:
                self.agentic_project_override = True
            elif cur is True:
                self.agentic_project_override = False
            else:
                self.agentic_project_override = None
            # Re-initialize advanced components to apply change
            self.initialize_advanced_components()
            # Refresh indicators and QA UI if open
            self._update_quick_indicators()
            if hasattr(self, '_qa_win') and self._qa_win and self._qa_win.winfo_exists():
                self._qa_show_main()
            # Persist per-session override into conversation metadata on next autosave
            try:
                self._auto_save_conversation()
            except Exception:
                pass
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Agentic session toggle failed: {e}")

    def _toggle_agentic_project_default(self):
        """Toggle backend default Agentic Project in advanced_settings.json (global)."""
        try:
            settings_file = Path(__file__).parent.parent / "advanced_settings.json"
            data = {}
            if settings_file.exists():
                try:
                    data = json.loads(settings_file.read_text())
                except Exception:
                    data = {}
            if 'agentic_project' not in data or not isinstance(data['agentic_project'], dict):
                data['agentic_project'] = {}
            cur = bool(data['agentic_project'].get('enabled', False))
            data['agentic_project']['enabled'] = (not cur)
            settings_file.write_text(json.dumps(data, indent=2))
            # Reload in-memory settings and re-init
            self.advanced_settings = self.load_advanced_settings()
            self.initialize_advanced_components()
            self._update_quick_indicators()
            if hasattr(self, '_qa_win') and self._qa_win and self._qa_win.winfo_exists():
                self._qa_show_main()
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Agentic default toggle failed: {e}")

    def _qa_show_main(self):
        try:
            for w in self._qa_body.winfo_children():
                w.destroy()
            try:
                if hasattr(self, '_qa_win') and self._qa_win:
                    self._qa_win.resizable(True, True)
                    w, h = 420, 220
                    ax, ay = getattr(self, '_qa_anchor', (self._qa_win.winfo_x(), self._qa_win.winfo_y()))
                    self._qa_win.geometry(f"{w}x{h}+{ax}+{ay}")
            except Exception:
                pass
            # Grid of icon-only buttons (wrap to rows of 4)
            grid = ttk.Frame(self._qa_body)
            grid.pack(pady=8, fill=tk.BOTH, expand=True)
            for i in range(4):
                grid.columnconfigure(i, weight=1)

            def mk_at(index, btn_text, desc, cmd, style='Action.TButton'):
                r = index // 4
                c = index % 4
                b = ttk.Button(grid, text=btn_text, width=6, style=style, command=cmd)
                b.grid(row=r, column=c, padx=6, pady=6, sticky=tk.EW)
                b.bind('<Enter>', lambda e, t=desc: self._qa_desc.config(text=t))
                b.bind('<Leave>', lambda e: self._qa_desc.config(text=''))
                return b

            i = 0
            mk_at(i, '📂', 'Change Working Directory', self.change_working_directory); i += 1
            mk_at(i, '🔧', 'Manage Tools', self._qa_show_tools); i += 1
            mk_at(i, '⏱', 'Think Time (next input)', self.open_think_time_dialog); i += 1
            mk_at(i, '⚡', 'Select Mode', self.open_mode_selector); i += 1
            backend_desc = 'Select Backend (Ollama / Llama Server)'
            if not self._llama_server_available():
                backend_desc += ' [llama.cpp server not detected]'
            mk_at(i, '🌐', backend_desc, self._open_backend_selector); i += 1
            mk_at(i, '📝', 'System Prompt / Tool Schema', self.open_prompt_schema_manager); i += 1
            # Temperature mode selector
            mk_at(i, '🌡️', 'Temperature Mode (Auto/Manual)', self.open_temp_mode_selector); i += 1
            # Create Project (save current chat to a new project and switch panel)
            mk_at(i, '🗂', 'Create Project from this chat', self._qa_create_project); i += 1
            # Show Thoughts toggle (👁 preferred; fallback 🧠)
            def _toggle_thoughts():
                self.show_thoughts = not bool(self.show_thoughts)
                # If turning on, ensure tracker is open
                if self.show_thoughts and not self.is_tracker_active:
                    self.create_tracker_window()
                try:
                    self._update_quick_indicators()
                except Exception:
                    pass
                # Update style to reflect state
                try:
                    btn = self._qa_thoughts_btn
                    btn.configure(style=('QA.Green.TButton' if self.show_thoughts else 'Select.TButton'))
                except Exception:
                    pass
            self._qa_thoughts_btn = mk_at(i, '👁', 'Toggle Show Thoughts (preview during generation)', _toggle_thoughts, style='Select.TButton'); i += 1
            # RAG toggle (chat-only) — enabling disables is immediate and persisted if possible
            def _toggle_rag():
                self.rag_enabled = not bool(self.rag_enabled)
                try:
                    if getattr(self, 'current_session_id', None) and self.chat_history_manager:
                        self._auto_save_conversation()
                except Exception:
                    pass
                self._update_quick_indicators()
            mk_at(i, '🧠', 'Toggle RAG (per chat)', _toggle_rag); i += 1
            # Removed redundant "Save RAG" action; RAG setting persists via autosave when toggled
            mk_at(i, '🗒', 'ToDo List', self.open_todo_list); i += 1
            # Training toggle (🏋️) with colored state
            # Training toggle (🏋️) with colored state; keep a handle for live style updates
            self._qa_train_btn = mk_at(i, '🏋️', 'Training Mode', self._qa_toggle_training, style='Select.TButton')
            try:
                self._qa_update_training_btn()
            except Exception:
                pass
            # New: Tracker button
            mk_at(i + 1, '🔍', 'Open Live File Tracker', self.toggle_tracker_window)
            # MoE Broadcast button
            mk_at(i + 2, '📡', 'MoE Broadcast (send input to multiple agents)', self._open_moe_broadcast_dialog)

            # Navigation row (main tabs)
            try:
                row_nav = ttk.Frame(self._qa_body)
                row_nav.pack(fill=tk.X, pady=(0,4))
                def nav(lbl, tip, tab, subtab=None, session=None):
                    b = ttk.Button(row_nav, text=lbl, style='Select.TButton', width=10,
                                   command=lambda: self._qa_open_tab(tab, subtab=subtab, session=session))
                    b.pack(side=tk.LEFT, padx=4)
                    b.bind('<Enter>', lambda e, t=tip: self._qa_desc.config(text=t))
                    b.bind('<Leave>', lambda e: self._qa_desc.config(text=''))
                nav('Models', 'Open Models tab', 'Models')
                nav('Types', 'Open Types tab', 'Types')
                nav('Agents', 'Open Agents tab', 'Agents')
                nav('RAG', 'Open RAG visualizer', 'RAG')
            except Exception:
                pass
            # Agent Events toggle
            try:
                row_ev = ttk.Frame(self._qa_body)
                row_ev.pack(fill=tk.X, pady=(2,2))
                def _toggle_agent_events():
                    self.agent_events_logging_enabled = not bool(getattr(self, 'agent_events_logging_enabled', True))
                    try:
                        self._update_quick_indicators()
                    except Exception:
                        pass
                    try:
                        btn.configure(style=('QA.Green.TButton' if self.agent_events_logging_enabled else 'Select.TButton'))
                    except Exception:
                        pass
                btn = ttk.Button(row_ev, text='Agent Events', width=12, style=('QA.Green.TButton' if getattr(self, 'agent_events_logging_enabled', True) else 'Select.TButton'), command=_toggle_agent_events)
                btn.pack(side=tk.LEFT)
            except Exception:
                pass
            # Mark current QA view
            self._qa_view = 'main'
        except Exception:
            pass

    def _qa_show_agents(self):
        """Legacy placeholder – agent Quick Actions panel removed."""
        try:
            self.add_message('system', 'Agents Quick Actions panel has been removed. Use the Agents tab or popup controls.')
        except Exception:
            pass

    # --- MoE Broadcast Dialog and Execution ----------------------------------
    def _open_moe_broadcast_dialog(self):
        """Show MoE Broadcast dialog for sending input to multiple agents"""
        try:
            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("MoE Broadcast")
            dialog.geometry("600x500")
            dialog.transient(self.root)

            # Header
            header = ttk.Frame(dialog, style='Category.TFrame')
            header.pack(fill=tk.X, padx=10, pady=10)
            ttk.Label(header, text="📡 MoE Broadcast", font=("Arial", 12, "bold")).pack()
            ttk.Label(header, text="Send input to multiple agents simultaneously or sequentially").pack()

            # Input text area
            input_frame = ttk.LabelFrame(dialog, text="Broadcast Message", padding=10)
            input_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

            input_text = tk.Text(input_frame, height=5, wrap=tk.WORD, bg='#2d2d2d', fg='#ffffff', font=('Courier New', 10))
            input_text.pack(fill=tk.BOTH, expand=True)
            input_text.insert('1.0', "Enter your message to broadcast to agents...")
            input_text.bind('<FocusIn>', lambda e: input_text.delete('1.0', tk.END) if input_text.get('1.0', tk.END).strip().startswith("Enter your") else None)

            # Agent selection
            agent_frame = ttk.LabelFrame(dialog, text="Select Agents", padding=10)
            agent_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

            canvas = tk.Canvas(agent_frame, bg='#2d2d2d', highlightthickness=0, height=150)
            scrollbar = ttk.Scrollbar(agent_frame, orient=tk.VERTICAL, command=canvas.yview)
            agent_list = ttk.Frame(canvas)

            agent_list.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=agent_list, anchor=tk.NW)
            canvas.configure(yscrollcommand=scrollbar.set)

            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Get mounted agents
            agent_vars = {}
            try:
                roster = []
                if hasattr(self.root, 'get_active_agents'):
                    roster = self.root.get_active_agents() or []

                mounted_set = getattr(self, '_agents_mounted_set', set()) or set()

                for agent in roster:
                    agent_name = agent.get('name', '')
                    if agent_name in mounted_set:
                        var = tk.BooleanVar(value=False)
                        agent_vars[agent_name] = var

                        row = ttk.Frame(agent_list)
                        row.pack(fill=tk.X, pady=2)

                        ttk.Checkbutton(row, text=agent_name, variable=var).pack(side=tk.LEFT)

                        # Show agent type
                        assigned_type = agent.get('assigned_type', 'general')
                        ttk.Label(row, text=f"({assigned_type})", foreground="#888888").pack(side=tk.LEFT, padx=(5, 0))
            except Exception as e:
                log_message(f"MoE_BROADCAST: Error loading agents: {e}")

            # Execution mode
            mode_frame = ttk.Frame(dialog)
            mode_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

            ttk.Label(mode_frame, text="Execution Mode:").pack(side=tk.LEFT, padx=(0, 10))
            mode_var = tk.StringVar(value="sequential")
            ttk.Radiobutton(mode_frame, text="Sequential", variable=mode_var, value="sequential").pack(side=tk.LEFT, padx=5)
            ttk.Radiobutton(mode_frame, text="Simultaneous", variable=mode_var, value="simultaneous").pack(side=tk.LEFT, padx=5)

            # Buttons
            btn_frame = ttk.Frame(dialog)
            btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

            def execute_broadcast():
                message = input_text.get('1.0', tk.END).strip()
                if not message or message.startswith("Enter your"):
                    self.add_message('system', 'Please enter a message to broadcast')
                    return

                selected_agents = [name for name, var in agent_vars.items() if var.get()]
                if not selected_agents:
                    self.add_message('system', 'Please select at least one agent')
                    return

                mode = mode_var.get()
                dialog.destroy()

                # Execute broadcast
                self._execute_moe_broadcast(message, selected_agents, mode)

            ttk.Button(btn_frame, text="Send to All Selected", command=execute_broadcast, style='Action.TButton').pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="Cancel", command=dialog.destroy, style='Select.TButton').pack(side=tk.LEFT, padx=5)

        except Exception as e:
            log_message(f"MoE_BROADCAST: Error opening dialog: {e}")
            self.add_message('error', f'Failed to open MoE broadcast dialog: {e}')

    def _execute_moe_broadcast(self, message: str, agent_names: list, mode: str):
        """Execute MoE broadcast to multiple agents"""
        try:
            self.add_message('system', f'📡 MoE Broadcast: Sending to {len(agent_names)} agent(s) in {mode} mode...')

            if mode == "sequential":
                # Execute one by one
                for agent_name in agent_names:
                    try:
                        self.add_message('system', f'→ Broadcasting to {agent_name}...')
                        self.run_agent_inference(agent_name, message)

                        # Show response
                        try:
                            self._ensure_agents_sessions()
                            if agent_name in self._agents_sessions:
                                log = self._agents_sessions[agent_name].get('log', [])
                                if log:
                                    for entry in reversed(log):
                                        if entry.get('role') == 'assistant':
                                            response = entry.get('text', '(no content)')
                                            self.add_message('system', f'✓ {agent_name}: {response[:200]}{"..." if len(response) > 200 else ""}')
                                            break
                        except Exception:
                            pass
                    except Exception as e:
                        self.add_message('error', f'✗ {agent_name} failed: {e}')
                        log_message(f"MoE_BROADCAST: Agent {agent_name} failed: {e}")

            else:  # simultaneous
                # Execute in parallel using threads
                import threading
                results = {}
                threads = []

                def run_agent_thread(agent_name):
                    try:
                        self.run_agent_inference(agent_name, message)

                        # Get response
                        response = "(no response)"
                        try:
                            self._ensure_agents_sessions()
                            if agent_name in self._agents_sessions:
                                log = self._agents_sessions[agent_name].get('log', [])
                                if log:
                                    for entry in reversed(log):
                                        if entry.get('role') == 'assistant':
                                            response = entry.get('text', '(no content)')
                                            break
                        except Exception:
                            pass

                        results[agent_name] = {'success': True, 'response': response}
                    except Exception as e:
                        results[agent_name] = {'success': False, 'error': str(e)}
                        log_message(f"MoE_BROADCAST: Agent {agent_name} failed: {e}")

                # Start all threads
                for agent_name in agent_names:
                    thread = threading.Thread(target=run_agent_thread, args=(agent_name,), daemon=True)
                    thread.start()
                    threads.append(thread)

                # Wait for all to complete
                for thread in threads:
                    thread.join(timeout=120)  # 2 minute timeout per agent

                # Display results
                for agent_name, result in results.items():
                    if result.get('success'):
                        response = result.get('response', '')
                        self.add_message('system', f'✓ {agent_name}: {response[:200]}{"..." if len(response) > 200 else ""}')
                    else:
                        self.add_message('error', f'✗ {agent_name} failed: {result.get("error", "unknown error")}')

            self.add_message('system', f'📡 MoE Broadcast complete: {len(agent_names)} agent(s) processed')

        except Exception as e:
            log_message(f"MoE_BROADCAST: Execution failed: {e}")
            self.add_message('error', f'MoE broadcast failed: {e}')

    # --- Compact Progress Indicator Helpers ----------------------------------
    def _show_progress(self, state: str = "thinking", percentage: int = 0, speed: str = ""):
        """Show compact text progress bar at bottom of chat"""
        try:
            # Create ASCII progress bar: [=====>     ] 50% | thinking | 15 tok/s
            bar_width = 20
            filled = int((percentage / 100) * bar_width)
            bar = "[" + "=" * filled + (">" if filled < bar_width else "") + " " * (bar_width - filled - 1) + "]"

            text = f"{bar} {percentage}%"
            if state:
                text += f" | {state}"
            if speed:
                text += f" | {speed}"

            self.progress_label.config(text=text)
            self.progress_frame.grid()
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Error showing progress: {e}")

    def _update_progress(self, percentage: int, state: str = None, speed: str = ""):
        """Update progress percentage and optional state"""
        try:
            if not hasattr(self, 'progress_label'):
                return
            current_text = self.progress_label.cget('text')
            if not current_text:
                return

            # Parse current state if not provided
            if state is None and '|' in current_text:
                parts = current_text.split('|')
                if len(parts) > 1:
                    state = parts[1].strip()

            self._show_progress(state=state or "thinking", percentage=percentage, speed=speed)
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Error updating progress: {e}")

    def _hide_progress(self):
        """Hide progress indicator"""
        try:
            self.progress_frame.grid_remove()
            self.progress_label.config(text="")
        except Exception:
            pass

    # --- Agent event sinks + runtime control --------------------------------
    def _ensure_agents_sessions(self):
        if not hasattr(self, '_agents_sessions') or not isinstance(getattr(self, '_agents_sessions'), dict):
            self._agents_sessions = {}

    def _get_agent_routes(self, agent_name: str) -> tuple[str, str]:
        """Return (chat_route, tool_route) for the agent.

        Returns routing configuration from live agent configs (priority) or roster (fallback).
        Defaults to 'panel' (agent dock only) to match agent_configs defaults.

        Priority order:
        1. Live agent_configs from agents_tab (current session state)
        2. Roster (may be stale if user changed routing after mount)
        3. Default to 'panel'
        """
        # Default to 'panel' to match agents_tab.py defaults (lines 1702-1703)
        # This ensures agents are restricted to docks unless explicitly configured otherwise
        chat_route = 'panel'
        tool_route = 'panel'
        route_source = 'default'
        name_low = (agent_name or '').strip().lower()

        try:
            # PRIORITY 1: Check live agent_configs first (reflects current UI state)
            configs = {}
            try:
                if hasattr(self.parent_tab, 'agents_tab') and getattr(self.parent_tab.agents_tab, 'agent_configs', None):
                    configs = self.parent_tab.agents_tab.agent_configs
            except Exception:
                configs = {}

            cfg = configs.get(agent_name)
            if not cfg:
                for key, val in configs.items():
                    if (key or '').strip().lower() == name_low:
                        cfg = val
                        break

            if cfg:
                chat_route = str(cfg.get('chat_route', 'panel') or 'panel').lower()
                tool_route = str(cfg.get('tool_route', 'panel') or 'panel').lower()
                route_source = 'agents_tab_live'
            else:
                # PRIORITY 2: Fallback to roster if not in agent_configs
                roster = self._get_live_roster()
                for entry in roster or []:
                    if (entry.get('name') or '').strip().lower() == name_low:
                        chat_route = str(entry.get('chat_route', 'panel') or 'panel').lower()
                        tool_route = str(entry.get('tool_route', 'panel') or 'panel').lower()
                        route_source = 'roster_fallback'
                        break
        except Exception:
            pass

        try:
            log_message(
                f"AGENT_ROUTING: route_query agent={agent_name} chat_route={chat_route} tool_route={tool_route} source={route_source}",
                level='DEBUG'
            )
        except Exception:
            pass
        return chat_route, tool_route

    def _agent_should_echo_chat(self, agent_name: str) -> bool:
        chat_route, _ = self._get_agent_routes(agent_name)
        return chat_route in ('main', 'both')

    def _agent_should_echo_tools(self, agent_name: str) -> bool:
        _, tool_route = self._get_agent_routes(agent_name)
        return tool_route in ('main', 'both')

    def _wrap_agent_request_with_serialization(self, execution_func):
        """Wrapper to serialize agent_request executions using semaphore.

        Args:
            execution_func: Function to execute (contains the actual agent_request logic)

        Returns:
            Result from execution_func

        This ensures only ONE agent_request executes at a time across the entire system.
        """
        # Acquire semaphore (blocks if another agent request is active)
        self._agent_request_semaphore.acquire()
        try:
            log_message("AGENT_SERIAL: Acquired execution slot")
            result = execution_func()
            return result
        finally:
            self._agent_request_semaphore.release()
            log_message("AGENT_SERIAL: Released execution slot")

    def _process_tool_queue(self):
        """Process tool execution queue continuously.

        Runs in dedicated thread. Dequeues tool requests, executes with appropriate
        locks, stores results, and signals completion.
        """
        import time
        log_message("TOOL_QUEUE: Processor thread started")

        while self._tool_queue_active:
            try:
                # Wait for item with timeout to allow clean shutdown
                try:
                    priority, timestamp, request_id, tool_item = self._tool_execution_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                log_message(f"TOOL_QUEUE: Dequeued tool {tool_item['tool_name']} (priority={priority}, request_id={request_id})")

                # Determine which lock to use
                tool_name = tool_item['tool_name']
                lock_map = {
                    'bash_execute': self._tool_locks['bash'],
                    'file_write': self._tool_locks['file_write'],
                    'file_edit': self._tool_locks['file_write'],
                    'change_directory': self._tool_locks['directory'],
                }
                tool_lock = lock_map.get(tool_name)

                # Execute with appropriate lock
                result = None
                try:
                    if tool_lock:
                        log_message(f"TOOL_QUEUE: Acquiring lock for {tool_name}")
                        with tool_lock:
                            result = self._execute_single_tool(tool_item)
                    else:
                        # Safe tool, no lock needed
                        result = self._execute_single_tool(tool_item)

                    # Log based on actual result
                    if result.get('success', False):
                        log_message(f"TOOL_QUEUE: Completed {tool_name} successfully")
                    else:
                        error_msg = result.get('error', 'Unknown error')
                        log_message(f"TOOL_QUEUE: Tool {tool_name} failed: {error_msg}")
                except Exception as e:
                    log_message(f"TOOL_QUEUE ERROR: Tool {tool_name} failed: {e}")
                    result = {
                        'success': False,
                        'output': '',
                        'error': str(e),
                        'tool_name': tool_name
                    }

                # Store result
                with self._tool_queue_lock:
                    self._tool_queue_results[request_id] = result

                # Signal completion
                if request_id in self._tool_queue_events:
                    self._tool_queue_events[request_id].set()

                # Mark task done
                self._tool_execution_queue.task_done()

            except Exception as e:
                log_message(f"TOOL_QUEUE ERROR: Processor caught exception: {e}")
                import traceback
                log_message(f"TOOL_QUEUE TRACEBACK: {traceback.format_exc()}")

        log_message("TOOL_QUEUE: Processor thread stopped")

    def _execute_single_tool(self, tool_item):
        """Execute a single tool from the queue.

        Args:
            tool_item: Dict with tool_name, arguments, tool_call, context

        Returns:
            Result dict with success, output, error
        """
        tool_name = tool_item['tool_name']
        arguments = tool_item['arguments']
        tool_call = tool_item.get('tool_call', {})

        # Debug: Log tool execution input
        log_message(f"TOOL_EXEC DEBUG: Executing {tool_name} with args: {arguments}")

        try:
            # Use existing tool executor
            if not self.tool_executor:
                raise Exception("Tool executor not initialized")

            result = self.tool_executor.execute_tool_sync(tool_name, arguments)

            # Debug: Log tool execution result
            log_message(f"TOOL_EXEC DEBUG: {tool_name} returned success={result.get('success')}, output_len={len(str(result.get('output', '')))}")

            return {
                'success': result.get('success', True),
                'output': result.get('output', result.get('data', '')),
                'error': result.get('error', ''),
                'tool_name': tool_name,
                'data': result.get('data'),
                'openai_format': {
                    'role': 'tool',
                    'content': result.get('output', str(result.get('data', ''))),
                    'tool_call_id': tool_call.get('id', ''),
                    'name': tool_name
                }
            }
        except Exception as e:
            return {
                'success': False,
                'output': '',
                'error': str(e),
                'tool_name': tool_name,
                'openai_format': {
                    'role': 'tool',
                    'content': json.dumps({'error': str(e)}),
                    'tool_call_id': tool_call.get('id', ''),
                    'name': tool_name
                }
            }

    def _execute_tools_via_queue(self, tool_calls, agent_name=None, effective_enabled=None, route_func=None):
        """Execute tool calls via the global tool execution queue.

        This ensures:
        1. Serialized execution with priority ordering
        2. Per-tool locks to prevent conflicts
        3. Proper results formatting

        Args:
            tool_calls: List of tool call dicts
            agent_name: Name of calling agent (for priority)
            effective_enabled: Tool enablement map
            route_func: Function to route UI messages

        Returns:
            (structured_results, tool_results) tuple in same format as direct execution
        """
        import uuid
        import time

        # Determine priority
        if agent_name is None:
            priority = 0  # P0: User (main chat)
        elif agent_name and 'orchestrator' in agent_name.lower():
            priority = 1  # P1: Orchestrator
        else:
            priority = 2  # P2: Agents

        structured_results = []
        tool_results = []

        # Enqueue all tools and track request IDs
        request_ids = []
        for tool_call in tool_calls:
            function_data = tool_call.get("function", {})
            tool_name = function_data.get("name")
            arguments = function_data.get("arguments", {})

            # Parse arguments if they're a JSON string (same as direct execution path)
            if isinstance(arguments, str):
                try:
                    if self.json_fixer_enabled:
                        arguments = self.smart_json_parse(arguments)
                    else:
                        arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    log_message(f"TOOL_QUEUE ERROR: Failed to parse tool arguments for {tool_name}: {arguments}")
                    arguments = {}

            # Create unique request ID
            request_id = str(uuid.uuid4())
            request_ids.append(request_id)

            # Create completion event
            completion_event = threading.Event()
            self._tool_queue_events[request_id] = completion_event

            # Build tool item
            tool_item = {
                'tool_name': tool_name,
                'arguments': arguments,
                'tool_call': tool_call,
                'agent_name': agent_name,
                'effective_enabled': effective_enabled,
                'route_func': route_func
            }

            # Enqueue with priority
            timestamp = time.time()
            self._tool_execution_queue.put((priority, timestamp, request_id, tool_item))

            log_message(f"TOOL_QUEUE: Enqueued {tool_name} (priority={priority}, request_id={request_id})")

        # Wait for all tools to complete
        for request_id in request_ids:
            completion_event = self._tool_queue_events.get(request_id)
            if completion_event:
                # Wait with timeout (5 minutes per tool)
                if not completion_event.wait(timeout=300):
                    log_message(f"TOOL_QUEUE: Timeout waiting for request {request_id}")
                    # Create error result
                    structured_results.append({
                        'tool_name': 'unknown',
                        'success': False,
                        'output': '',
                        'error': 'Tool execution timeout'
                    })
                    tool_results.append({
                        'role': 'tool',
                        'content': json.dumps({'error': 'Tool execution timeout'}),
                        'tool_call_id': '',
                        'name': 'unknown'
                    })
                    continue

                # Get result
                result = self._tool_queue_results.get(request_id)
                if result:
                    # Debug: Log tool result details
                    log_message(f"TOOL_QUEUE DEBUG: Retrieved result for {result['tool_name']}: success={result['success']}, output_len={len(str(result.get('output', '')))}, error={result.get('error', 'none')[:100]}")

                    # Add to structured results
                    structured_results.append({
                        'tool_name': result['tool_name'],
                        'success': result['success'],
                        'output': result['output'],
                        'error': result.get('error', '')
                    })

                    # Add to tool results (OpenAI format)
                    tool_results.append(result['openai_format'])

                    # Debug: Log what's being sent to model
                    log_message(f"TOOL_QUEUE DEBUG: OpenAI format for model - role={result['openai_format']['role']}, name={result['openai_format']['name']}, content_preview={str(result['openai_format'].get('content', ''))[:200]}")

                    # Cleanup
                    del self._tool_queue_results[request_id]
                    del self._tool_queue_events[request_id]

        return structured_results, tool_results

    def _agent_allows_orchestrator_access(self, agent_name: str) -> bool:
        """Check if agent's routing allows orchestrator/tool-based calls.

        Returns True if tool_route is 'main' or 'both', False if 'panel' only.
        Agents with tool_route='panel' are restricted to agent dock only.
        """
        _, tool_route = self._get_agent_routes(agent_name)
        return tool_route in ('main', 'both')

    def _record_agent_panel_event(
        self,
        agent_name: str,
        text: str,
        role: str = 'system',
        *,
        use_tool_route: bool = False,
        deliver_main: bool | None = None,
    ) -> bool:
        """Append an agent event to session log and indicate if it should appear in the panel."""
        panel_visible = True
        try:
            with self._agents_sessions_lock:  # Thread-safe access
                self._ensure_agents_sessions()
                log_bucket = self._agents_sessions.setdefault(agent_name, {'log': []})
                chat_route, tool_route = self._get_agent_routes(agent_name)
                active_route = tool_route if use_tool_route else chat_route
                panel_visible = active_route in ('panel', 'both')
                log_bucket['log'].append({
                    'ts': time.time(),
                    'role': role,
                    'text': text,
                    'panel_visible': panel_visible,
                    'route': active_route,
                    'channel': 'tool' if use_tool_route else 'chat',
                    'main_echo': bool(deliver_main) if deliver_main is not None else None,
                })

                # Implement log rotation to prevent memory leak (keep last 100 messages)
                MAX_AGENT_LOG_SIZE = 100
                if len(log_bucket['log']) > MAX_AGENT_LOG_SIZE:
                    log_bucket['log'] = log_bucket['log'][-MAX_AGENT_LOG_SIZE:]
        except Exception:
            panel_visible = True  # fall back to showing in panel on errors
        return panel_visible

    def _emit_agent_status(self, agent_name: str, message: str, role: str = 'system', *, use_tool_route: bool = False):
        """Record an agent event and mirror it to the main chat if routing allows."""
        try:
            panel_role = role if role in {'user', 'assistant', 'system', 'result', 'error', 'tool'} else 'system'
            should_echo = self._agent_should_echo_tools(agent_name) if use_tool_route else self._agent_should_echo_chat(agent_name)
            panel_visible = self._record_agent_panel_event(
                agent_name,
                message,
                panel_role,
                use_tool_route=use_tool_route,
                deliver_main=should_echo,
            )
            try:
                log_message(
                    f"AGENT_ROUTING: deliver agent={agent_name} channel={'tool' if use_tool_route else 'chat'} "
                    f"panel_visible={panel_visible} main_echo={should_echo} role={role}",
                    level='DEBUG'
                )
            except Exception:
                pass
            if should_echo:
                channel = 'error' if role == 'error' else 'system'
                self.add_message(channel, message)
        except Exception:
            pass

    def send_agent_message(self, agent_name: str, text: str):
        try:
            should_echo = self._agent_should_echo_chat(agent_name)
            panel_visible = self._record_agent_panel_event(
                agent_name,
                text,
                'user',
                use_tool_route=False,
                deliver_main=should_echo,
            )
            try:
                log_message(
                    f"AGENT_ROUTING: user_input agent={agent_name} panel_visible={panel_visible} main_echo={should_echo}",
                    level='DEBUG'
                )
            except Exception:
                pass
            if getattr(self, 'agent_events_logging_enabled', True) and should_echo:
                self.add_message('system', f"[Agent:{agent_name}] ➜ {text}")
                try:
                    self._auto_save_conversation()
                except Exception:
                    pass
        except Exception:
            pass

    def on_agent_mounted(self, agent_name: str):
        try:
            if getattr(self, 'agent_events_logging_enabled', True):
                self._log_agent_event(agent_name, event='mounted')
            else:
                self._record_agent_panel_event(agent_name, 'mounted', 'system')
            # Track mounted set for UI badges
            try:
                if not hasattr(self, '_agents_mounted_set'):
                    self._agents_mounted_set = set()
                self._agents_mounted_set.add(agent_name)
            except Exception:
                pass
        except Exception:
            pass

    def on_agent_progress(self, agent_name: str, pct: int):
        try:
            self.add_message('system', f"Agent {agent_name} working: {int(pct)}%")
        except Exception:
            pass

    def on_agent_result(self, agent_name: str, summary: str):
        try:
            if getattr(self, 'agent_events_logging_enabled', True):
                message = f"[Agent:{agent_name}] ✔ result → {summary}"
                self._emit_agent_status(agent_name, message)
            should_echo = self._agent_should_echo_chat(agent_name)
            self._record_agent_panel_event(
                agent_name,
                summary,
                'result',
                deliver_main=should_echo,
            )
        except Exception:
            pass

    # Best-effort: unmount a single agent (UI feedback + badge update)
    def _unmount_agent(self, agent_name: str):
        try:
            # Remove mounted badge
            if hasattr(self, '_agents_mounted_set') and self._agents_mounted_set:
                try:
                    self._agents_mounted_set.discard(agent_name)
                except Exception:
                    pass
            try:
                self._agent_server_ports.pop(agent_name, None)
            except Exception:
                pass
            # UI message
            if getattr(self, 'agent_events_logging_enabled', True):
                self._log_agent_event(agent_name, event='unmounted')
            else:
                self._record_agent_panel_event(agent_name, 'unmounted', 'system')
        except Exception:
            pass

    def _log_agent_event(self, agent_name: str, event: str = 'mounted'):
        """Log a compact agent event line with class and tools info, and autosave."""
        try:
            # Resolve variant and enabled_tools from live roster
            variant = None
            tool_count = 0
            backend = None
            hardware = None
            roster = []
            try:
                if hasattr(self.root, 'get_active_agents') and callable(getattr(self.root, 'get_active_agents')):
                    roster = self.root.get_active_agents() or []
            except Exception:
                roster = []
            for r in roster:
                if (r.get('name') or '').strip().lower() == agent_name.strip().lower():
                    variant = (r.get('variant') or '').strip() or None
                    backend = (r.get('backend') or 'inherit')
                    hardware = (r.get('hardware') or 'inherit')
                    break
            # Fallback: read from Agents tab configs when variant missing
            if not variant and hasattr(self.parent_tab, 'agents_tab') and getattr(self.parent_tab.agents_tab, 'agent_configs', None):
                try:
                    cfg = self.parent_tab.agents_tab.agent_configs.get(agent_name) or {}
                    v = (cfg.get('variant') or '').strip()
                    if v:
                        variant = v
                except Exception:
                    pass
            cls = 'unassigned'
            if variant:
                try:
                    from config import load_model_profile
                    mp = load_model_profile(variant) or {}
                    cls = (mp.get('class_level') or 'unassigned')
                except Exception:
                    pass
            # Always recompute tool count from type/class when variant is known
            if variant:
                try:
                    mp = self._recompute_tools_for_variant(variant)
                    tool_count = sum(1 for _k, v in (mp or {}).items() if v)
                except Exception:
                    pass
            # Build a friendly model label when variant is unknown
            model_label = variant
            if not model_label:
                try:
                    # Prefer Ollama tag, then GGUF basename if present in roster
                    r = next((x for x in roster if (x.get('name') or '').strip().lower() == agent_name.strip().lower()), None)
                    tag = (r or {}).get('ollama_tag') or (r or {}).get('ollama_tag_override')
                    if tag:
                        model_label = f"tag:{tag}"
                    else:
                        gp = (r or {}).get('gguf_override')
                        if gp:
                            from pathlib import Path as _P
                            model_label = f"gguf:{_P(gp).name}"
                except Exception:
                    model_label = None
            if event == 'mounted':
                details = []
                details.append(model_label or 'variant:unknown')
                details.append(f'class:{cls}')
                details.append(f'tools:{tool_count}')
                if backend or hardware:
                    details.append(f'{backend}/{hardware}')
                msg = f"[Agent:{agent_name}] ◉ mounted | " + " | ".join(details)
            elif event == 'unmounted':
                msg = f"[Agent:{agent_name}] ◼ unmounted"
            else:
                msg = f"[Agent:{agent_name}] {event}"
            should_echo = self._agent_should_echo_chat(agent_name)
            self._record_agent_panel_event(agent_name, msg, 'system', deliver_main=should_echo)
            if should_echo:
                self.add_message('system', msg)
                try:
                    self._auto_save_conversation()
                except Exception:
                    pass
        except Exception:
            pass

    # Convenience wrapper: execute tool calls under a specific agent's enabled_tools map
    def handle_agent_tool_calls(self, agent_name: str, tool_calls, message_data,
                                return_results: bool = False,
                                suppress_ui: bool = False,
                                log_buffer: list | None = None):
        try:
            return self.handle_tool_calls(tool_calls, message_data,
                                          return_results=return_results,
                                          suppress_ui=suppress_ui,
                                          log_buffer=log_buffer,
                                          agent_name=agent_name)
        except Exception as e:
            try:
                self.add_message('error', f"Agent tool execution failed for {agent_name}: {e}")
            except Exception:
                pass
            return [] if return_results else None

    def add_conformer_event(self, agent_name: str, kind: str, data: dict | None = None):
        try:
            ev = {
                'ts': time.time(),
                'kind': kind,
                'data': (data or {})
            }
            lst = self._conformer_events.setdefault(agent_name, [])
            lst.append(ev)
        except Exception:
            pass

    def _get_agent_config(self, agent_name: str) -> dict:
        """Retrieve live agent config from agents_tab.agent_configs."""
        try:
            has_parent = hasattr(self, 'parent_tab')
            has_agents_tab = has_parent and hasattr(self.parent_tab, 'agents_tab')
            has_configs = has_agents_tab and hasattr(self.parent_tab.agents_tab, 'agent_configs')

            log_message(
                f"AGENT_CONFIG DEBUG: agent={agent_name} has_parent_tab={has_parent} "
                f"has_agents_tab={has_agents_tab} has_agent_configs={has_configs}"
            )

            if has_configs:
                configs = self.parent_tab.agents_tab.agent_configs
                log_message(f"AGENT_CONFIG DEBUG: agent_configs keys={list(configs.keys())}")

                # Try exact match first
                if agent_name in configs:
                    cfg = configs[agent_name]
                    log_message(f"AGENT_CONFIG DEBUG: Found exact match for {agent_name}: {cfg}")
                    return cfg
                # Try case-insensitive match
                name_lower = agent_name.strip().lower()
                for key, val in configs.items():
                    if key.strip().lower() == name_lower:
                        log_message(f"AGENT_CONFIG DEBUG: Found case-insensitive match {key} for {agent_name}")
                        return val

                log_message(f"AGENT_CONFIG: No config found for {agent_name} in agent_configs", level='WARNING')
        except Exception as e:
            log_message(f"AGENT_CONFIG: Error retrieving config for {agent_name}: {e}", level='WARNING')
        return {}

    def _load_agent_system_prompt(self, agent_config: dict) -> str:
        """Load system prompt content for agent from config."""
        try:
            prompt_name = agent_config.get('system_prompt') or agent_config.get('system_prompt_override')
            if not prompt_name or prompt_name == 'default':
                return ""

            # Load prompt file from system_prompts directory
            from pathlib import Path
            prompts_dir = Path(__file__).parent.parent / "system_prompts"
            prompt_file = prompts_dir / f"{prompt_name}.txt"

            if prompt_file.exists():
                content = prompt_file.read_text().strip()
                log_message(f"AGENT_CONFIG: Loaded system prompt '{prompt_name}' for agent ({len(content)} chars)")
                return content
            else:
                log_message(f"AGENT_CONFIG: System prompt file not found: {prompt_file}", level='WARNING')
                return ""
        except Exception as e:
            log_message(f"AGENT_CONFIG: Error loading system prompt: {e}", level='WARNING')
            return ""

    def _load_agent_tool_schemas(self, agent_config: dict) -> list:
        """Load tool schemas for agent from config."""
        try:
            schema_name = agent_config.get('tool_schema')
            if not schema_name or schema_name in ('none', 'default'):
                return None

            # Use existing schema loading logic
            if hasattr(self, '_get_tool_schemas'):
                schemas = self._get_tool_schemas(schema_name)
                if schemas:
                    log_message(f"AGENT_CONFIG: Loaded tool schema '{schema_name}' ({len(schemas)} tools)")
                    return schemas

            log_message(f"AGENT_CONFIG: Tool schema '{schema_name}' not found", level='WARNING')
            return None
        except Exception as e:
            log_message(f"AGENT_CONFIG: Error loading tool schema: {e}", level='WARNING')
            return None

    def run_agent_inference(self, agent_name: str, text: str):
        """Run a best‑effort, single‑turn inference for an agent and log output into its mini session and main chat.

        Resolves backend/model from roster. For llama_server, calls the HTTP chat path directly.
        For Ollama, logs a not‑yet‑wired notice unless an ollama direct client is available.
        """
        try:
            log_message(
                f"AGENT_INFER: operation=start target={agent_name} text_len={len(text)}",
                level='DEBUG'
            )
            # Resolve agent record
            agent = None
            roster = []
            if hasattr(self.root, 'get_active_agents') and callable(getattr(self.root, 'get_active_agents')):
                roster = self.root.get_active_agents() or []
            try:
                log_message(
                    f"AGENT_INFER: operation=roster_lookup source=active count={len(roster)}",
                    level='DEBUG'
                )
            except Exception:
                pass
            for r in roster:
                if (r.get('name') or '').strip().lower() == agent_name.strip().lower():
                    agent = r
                    break
            if not agent:
                # Fallback: try Agents tab current roster
                try:
                    if hasattr(self.parent_tab, 'agents_tab') and hasattr(self.parent_tab.agents_tab, '_current_roster'):
                        alt = self.parent_tab.agents_tab._current_roster() or []
                        for r in alt:
                            if (r.get('name') or '').strip().lower() == agent_name.strip().lower():
                                agent = r
                                # Promote to live roster to keep everything consistent
                                if hasattr(self.root, 'get_active_agents') and hasattr(self.root, 'set_active_agents'):
                                    current = self.root.get_active_agents() or []
                                    names = { (x.get('name') or '').strip().lower() for x in current }
                                    if agent_name.strip().lower() not in names:
                                        current.append(agent)
                                        self.root.set_active_agents(current)
                                log_message(
                                    f"AGENT_INFER: operation=roster_lookup source=agents_tab fallback_applied={bool(agent)}",
                                    level='DEBUG'
                                )
                                break
                except Exception:
                    agent = None
            if not agent:
                log_message(
                    f"AGENT_INFER: operation=skip reason=not_in_roster target={agent_name}",
                    level='DEBUG'
                )
                self._emit_agent_status(agent_name, f"[Agent:{agent_name}] inference skipped (not in roster)")
                return
            backend, model_hint = self._resolve_agent_backend_and_model(agent)
            log_message(
                f"AGENT_INFER: operation=resolved target={agent_name} backend={backend} model_hint={model_hint}",
                level='DEBUG'
            )
            if backend == 'llama_server' and model_hint:
                # Require a dedicated agent server; do not auto-start here
                agent_port = self._get_agent_server_port(agent_name)
                if not agent_port:
                    log_message(
                        f"AGENT_INFER: operation=skip reason=not_mounted target={agent_name}",
                        level='DEBUG'
                    )
                    self._emit_agent_status(agent_name, f"[Agent:{agent_name}] not mounted — use 'Mount All' or mount per-agent")
                    return

                # LOG POINT 3: Input dispatch to agent
                caller_agent = getattr(self, '_current_chat_agent', {}).get('name') if hasattr(self, '_current_chat_agent') and self._current_chat_agent else None
                log_message(
                    f"AGENT_TOOL_CALL: operation=dispatch_to_agent caller={caller_agent or 'orchestrator'} "
                    f"target={agent_name} backend={backend} port={agent_port} model={model_hint} "
                    f"message_len={len(text)}"
                )

                # Retrieve agent config for system prompt and tool schema
                agent_config = self._get_agent_config(agent_name)
                system_prompt_content = self._load_agent_system_prompt(agent_config)
                tool_schemas = self._load_agent_tool_schemas(agent_config)

                # Build message list with system prompt if available
                messages = []
                if system_prompt_content:
                    messages.append({"role": "system", "content": system_prompt_content})
                agent_rag_context = self._get_agent_rag_context(agent_name, text)
                messages.extend(self._agent_context_messages(agent_rag_context))
                messages.append({"role": "user", "content": text})

                log_message(
                    f"AGENT_INFER: operation=config_applied target={agent_name} "
                    f"has_system_prompt={bool(system_prompt_content)} tool_schemas={len(tool_schemas) if tool_schemas else 0}"
                )

                ok, resp, err, stopped = self._llama_server_chat(messages, tool_schemas, model_override=model_hint, agent_name=agent_name)
                log_message(
                    f"AGENT_INFER: operation=llama_server_response target={agent_name} success={ok} stopped={stopped} error={bool(err)}",
                    level='DEBUG'
                )
                if ok:
                    content = ''
                    try:
                        choices = (resp.get('choices') or [])
                        if choices:
                            content = choices[0].get('message', {}).get('content', '')
                    except Exception:
                        content = ''

                    # LOG POINT 6: Response extracted
                    log_message(
                        f"AGENT_TOOL_CALL: operation=response_extracted caller={caller_agent or 'orchestrator'} "
                        f"target={agent_name} success={ok} content_len={len(content)} preview='{content[:80]}...'"
                    )

                    # Log to mini-session and optionally main chat (compact)
                    should_echo = self._agent_should_echo_chat(agent_name)
                    panel_visible = self._record_agent_panel_event(
                        agent_name,
                        content,
                        'assistant',
                        deliver_main=should_echo,
                    )
                    try:
                        log_message(
                            f"AGENT_ROUTING: agent_response agent={agent_name} panel_visible={panel_visible} main_echo={should_echo}",
                            level='DEBUG'
                        )
                    except Exception:
                        pass
                    if getattr(self, 'agent_events_logging_enabled', True):
                        short = (content or '').strip().split('\n')[0][:140]
                        message = f"[Agent:{agent_name}] replied → {short}{'…' if len((content or ''))>140 else ''}"
                        self._emit_agent_status(agent_name, message)
                else:
                    log_message(
                        f"AGENT_INFER: operation=llama_server_failure target={agent_name} error='{err}'",
                        level='ERROR'
                    )
                    self._emit_agent_status(agent_name, f"[Agent:{agent_name}] llama-server chat failed: {err}", role='error')
            elif backend == 'ollama':
                # Best-effort direct call to local Ollama HTTP API
                log_message(
                    f"AGENT_INFER: operation=ollama_dispatch target={agent_name} model={model_hint or agent.get('ollama_tag') or agent.get('ollama_tag_override')}",
                    level='DEBUG'
                )
                try:
                    import json as _J, subprocess as _SP, tempfile as _TF, os as _OS
                    model = model_hint or (agent.get('ollama_tag') or agent.get('ollama_tag_override') or '')
                    if not model:
                        log_message(
                            f"AGENT_INFER: operation=skip reason=no_ollama_tag target={agent_name}",
                            level='DEBUG'
                        )
                        self._emit_agent_status(agent_name, f"[Agent:{agent_name}] inference skipped (no ollama tag)")
                        return
                    messages = [{"role": "user", "content": text}]
                    payload = {
                        "model": model,
                        "messages": messages,
                        "stream": False
                    }
                    with _TF.NamedTemporaryFile('w', delete=False) as tf:
                        tf.write(_J.dumps(payload))
                        tmp = tf.name
                    try:
                        cmd = [
                            "curl", "-s", "-X", "POST", "http://localhost:11434/api/chat",
                            "-H", "Content-Type: application/json",
                            "-d", f"@{tmp}"
                        ]
                        res = _SP.run(cmd, capture_output=True, text=True, timeout=30)
                        if res.returncode == 0 and res.stdout:
                            data = _J.loads(res.stdout)
                            content = ''
                            try:
                                content = (data.get('message') or {}).get('content') or ''
                            except Exception:
                                content = ''
                            should_echo = self._agent_should_echo_chat(agent_name)
                            panel_visible = self._record_agent_panel_event(
                                agent_name,
                                content or '(no content)',
                                'assistant',
                                deliver_main=should_echo,
                            )
                            try:
                                log_message(
                                    f"AGENT_ROUTING: agent_response agent={agent_name} panel_visible={panel_visible} main_echo={should_echo}",
                                    level='DEBUG'
                                )
                            except Exception:
                                pass
                            if getattr(self, 'agent_events_logging_enabled', True):
                                short = (content or '').strip().split('\n')[0][:140]
                                message = f"[Agent:{agent_name}] replied → {short}{'…' if len((content or ''))>140 else ''}"
                                self._emit_agent_status(agent_name, message)
                            log_message(
                                f"AGENT_INFER: operation=ollama_success target={agent_name} content_len={len(content or '')}",
                                level='DEBUG'
                            )
                        else:
                            log_message(
                                f"AGENT_INFER: operation=ollama_failure target={agent_name} returncode={res.returncode} stderr='{(res.stderr or '').strip()}'",
                                level='ERROR'
                            )
                            self._emit_agent_status(
                                agent_name,
                                f"[Agent:{agent_name}] ollama chat failed: {res.stderr.strip() or 'HTTP error'}",
                                role='error'
                            )
                    finally:
                        try:
                            _OS.unlink(tmp)
                        except Exception:
                            pass
                except Exception as e:
                    log_exception(
                        f"AGENT_INFER: operation=ollama_exception target={agent_name} error='{e}'"
                    )
                    self._emit_agent_status(agent_name, f"[Agent:{agent_name}] ollama chat error: {e}", role='error')
            else:
                log_message(
                    f"AGENT_INFER: operation=skip reason=unknown_backend target={agent_name} backend={backend}",
                    level='DEBUG'
                )
                self._emit_agent_status(agent_name, f"[Agent:{agent_name}] inference skipped (unknown backend)")
        except Exception as e:
            log_exception(
                f"AGENT_INFER: operation=exception target={agent_name} error='{e}'"
            )
            self._emit_agent_status(agent_name, f"[Agent:{agent_name}] inference error: {e}", role='error')

    def show_conformers_popup(self, agent_name: str):
        try:
            import tkinter as tk
            win = tk.Toplevel(self.root)
            win.title(f"Conformers — {agent_name}")
            win.geometry('520x340')
            import tkinter.scrolledtext as st
            box = st.ScrolledText(win, wrap=tk.WORD)
            box.pack(fill=tk.BOTH, expand=True)
            events = list(self._conformer_events.get(agent_name, []))[-200:]
            for ev in events:
                ts = ev.get('ts')
                kind = ev.get('kind')
                data = ev.get('data') or {}
                box.insert('end', f"[{time.strftime('%H:%M:%S', time.localtime(ts))}] {kind}: {json.dumps(data)}\n")
            box.configure(state=tk.DISABLED)
        except Exception:
            pass

    def _mount_agents_all(self, user_initiated: bool = False, target_names: list[str] | None = None):
        """Warm‑mount agents based on active roster.
        For llama_server: ensure server is running and a usable GGUF is set.
        For Ollama: pre‑load model via 'ollama run <tag>' best‑effort.
        """
        try:
            # Safety gate: block any implicit/auto calls unless explicitly initiated
            try:
                if not user_initiated and self.backend_settings.get('block_auto_agent_mounts', True):
                    self.add_message('system', 'Agent auto-mount blocked by settings (manual Mount All required)')
                    return
            except Exception:
                pass
            # Debug: capture caller when enabled
            try:
                if self.backend_settings.get('enable_debug_logging', False):
                    import traceback as _tb
                    log_message("CHAT_INTERFACE: _mount_agents_all invoked. Call stack:\n" + ''.join(_tb.format_stack(limit=6)))
            except Exception:
                pass
            roster = []
            if hasattr(self.root, 'get_active_agents') and callable(getattr(self.root, 'get_active_agents')):
                roster = self.root.get_active_agents() or []
            # Fallback: use Agents tab live roster if available
            if not roster:
                try:
                    if hasattr(self.parent_tab, 'agents_tab') and hasattr(self.parent_tab.agents_tab, '_current_roster'):
                        roster = self.parent_tab.agents_tab._current_roster() or []
                        # Promote to live roster for consistency
                        if roster and hasattr(self.root, 'set_active_agents'):
                            self.root.set_active_agents(roster)
                except Exception:
                    roster = roster
            # Fallback: use defaults (project over global)
            if not roster:
                try:
                    from pathlib import Path as _P
                    import json as _J
                    proj = None
                    try:
                        if hasattr(self.parent_tab, 'settings_interface') and getattr(self.parent_tab.settings_interface, 'current_project_context', None):
                            proj = self.parent_tab.settings_interface.current_project_context
                    except Exception:
                        proj = None
                    src = None
                    if proj and (_P('Data')/'projects'/proj/'agents_default.json').exists():
                        src = _P('Data')/'projects'/proj/'agents_default.json'
                    elif (_P('Data')/'user_prefs'/'agents_default.json').exists():
                        src = _P('Data')/'user_prefs'/'agents_default.json'
                    if src:
                        roster = _J.loads(src.read_text()) or []
                        if roster and hasattr(self.root, 'set_active_agents'):
                            self.root.set_active_agents(roster)
                except Exception:
                    pass
            if not roster:
                self.add_message('system', 'No agents in roster to mount. Set agents in Agents tab or defaults.')
                return

            target_set = {name.strip().lower() for name in (target_names or []) if name}
            if target_set:
                roster_to_mount = [
                    a for a in roster
                    if (a.get('name') or '').strip().lower() in target_set
                ]
            else:
                roster_to_mount = list(roster)

            if target_set and not roster_to_mount:
                self.add_message('system', f"No matching agents to mount for: {', '.join(sorted(target_names or []))}")
                return

            log_message(
                f"AGENT_MOUNT: operation=mount_all_start roster_size={len(roster)} "
                f"agents={[a.get('name', 'unnamed') for a in roster_to_mount]} user_initiated={user_initiated} "
                f"scope={'targeted' if target_set else 'all'}",
                level='INFO'
            )

            # Import agent server manager
            try:
                from agent_server_manager import get_agent_server_manager
                agent_server_mgr = get_agent_server_manager()
            except Exception as e:
                log_error(
                    f"AGENT_MOUNT: operation=mount_all_failed reason='agent_server_manager import failed' error='{e}'",
                    auto_capture=True
                )
                self.add_message('error', f"Failed to load agent server manager: {e}")
                return

            mounted_count = 0
            failed_count = 0
            successfully_mounted_agents = []  # Track agents that mount successfully

            for a in roster_to_mount:
                name = a.get('name','agent')
                eff_backend, eff_model = self._resolve_agent_backend_and_model(a)

                log_message(
                    f"AGENT_MOUNT: operation=mount_agent agent={name} backend={eff_backend} model={eff_model}",
                    level='INFO'
                )

                if eff_backend == 'llama_server' and eff_model:
                    # Spawn dedicated server for this agent
                    try:
                        n_gpu_layers = int(a.get('n_gpu_layers') or 0)
                        cpu_threads = int(a.get('cpu_threads') or 8)

                        log_message(
                            f"AGENT_MOUNT: operation=spawn_request agent={name} backend=llama_server "
                            f"model={eff_model} gpu_layers={n_gpu_layers} cpu_threads={cpu_threads}",
                            level='INFO'
                        )

                        port = agent_server_mgr.spawn_server_for_agent(
                            name, eff_model, n_gpu_layers, cpu_threads
                        )

                        if port:
                            # Store port in roster entry
                            a['_server_port'] = port
                            try:
                                self._agent_server_ports[name] = int(port)
                            except Exception:
                                pass
                            self.on_agent_mounted(name)

                            # Check agent config for system_prompt and tool_schema
                            agent_config = self._get_agent_config(name)
                            system_prompt = agent_config.get('system_prompt') or agent_config.get('system_prompt_override')
                            tool_schema = agent_config.get('tool_schema')

                            # Build mount message with config status
                            mount_msg = f"Agent {name}: spawned server on port {port}"
                            if system_prompt and system_prompt != 'default':
                                mount_msg += f" | System Prompt: {system_prompt}"
                            else:
                                mount_msg += " | ⚠️ No system prompt set"

                            if tool_schema and tool_schema not in ('none', 'default'):
                                mount_msg += f" | Tools: {tool_schema}"
                            else:
                                mount_msg += " | ⚠️ No tools configured"

                            self.add_message('system', mount_msg)
                            log_message(
                                f"AGENT_MOUNT: operation=mount_success agent={name} backend={eff_backend} "
                                f"port={port} model={eff_model} system_prompt={system_prompt or 'none'} tool_schema={tool_schema or 'none'}",
                                level='INFO'
                            )
                            mounted_count += 1
                            successfully_mounted_agents.append(a)  # Add to successful mounts
                        else:
                            self.add_message('error', f"Agent {name}: failed to spawn dedicated server")
                            log_error(
                                f"AGENT_MOUNT: operation=mount_failed agent={name} backend={eff_backend} "
                                f"reason='spawn returned None' model={eff_model}",
                                auto_capture=True
                            )
                            failed_count += 1
                            try:
                                self._agent_server_ports.pop(name, None)
                            except Exception:
                                pass
                    except Exception as e:
                        self.add_message('error', f"Agent {name}: spawn error: {e}")
                        log_exception(
                            f"AGENT_MOUNT: operation=mount_exception agent={name} backend={eff_backend} error='{e}'"
                        )
                        failed_count += 1
                elif eff_backend == 'ollama':
                    try:
                        import shutil, subprocess
                        tag = a.get('ollama_tag') or a.get('ollama_tag_override') or eff_model or ''
                        if not tag:
                            self.add_message('error', f"Agent {name}: no Ollama tag specified")
                            log_message(
                                f"AGENT_MOUNT: operation=mount_skip agent={name} backend=ollama reason='no tag specified'",
                                level='WARNING'
                            )
                            failed_count += 1
                        elif not shutil.which('ollama'):
                            self.add_message('error', f"Agent {name}: 'ollama' not found")
                            log_error(
                                f"AGENT_MOUNT: operation=mount_failed agent={name} backend=ollama reason='ollama binary not found'",
                                auto_capture=True
                            )
                            failed_count += 1
                        else:
                            subprocess.Popen(["ollama", "run", tag], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            self.on_agent_mounted(name)
                            log_message(
                                f"AGENT_MOUNT: operation=mount_success agent={name} backend=ollama tag={tag}",
                                level='INFO'
                            )
                            mounted_count += 1
                            successfully_mounted_agents.append(a)  # Add to successful mounts
                    except Exception as e:
                        self.add_message('error', f"Agent {name}: ollama run failed: {e}")
                        log_exception(
                            f"AGENT_MOUNT: operation=mount_exception agent={name} backend=ollama error='{e}'"
                        )
                        failed_count += 1
                else:
                    self.add_message('system', f"Agent {name}: backend {eff_backend} not recognized; skipping")
                    log_message(
                        f"AGENT_MOUNT: operation=mount_skip agent={name} backend={eff_backend} reason='backend not recognized'",
                        level='WARNING'
                )

            self._agents_mounted = True

            # Update roster with successfully mounted agents
            log_message(f"ROSTER_UPDATE: Post-mount processing - successfully_mounted_agents={len(successfully_mounted_agents)}")

            # Find the root GUI object with roster methods
            # Priority: gui_instance (direct ref) > parent_tab.gui_instance > self.root (fallback)
            gui_root = None

            if hasattr(self, 'gui_instance') and hasattr(self.gui_instance, 'get_active_agents'):
                gui_root = self.gui_instance
                log_message(f"ROSTER_UPDATE: Using self.gui_instance")
            elif hasattr(self, 'parent_tab') and hasattr(self.parent_tab, 'gui_instance') and hasattr(self.parent_tab.gui_instance, 'get_active_agents'):
                gui_root = self.parent_tab.gui_instance
                log_message(f"ROSTER_UPDATE: Using parent_tab.gui_instance")
            elif hasattr(self.root, 'get_active_agents') and hasattr(self.root, 'set_active_agents'):
                gui_root = self.root
                log_message(f"ROSTER_UPDATE: Using self.root (fallback)")

            if not gui_root:
                log_message(f"ROSTER_UPDATE ERROR: Could not find GUI instance with roster methods", level='ERROR')

            if successfully_mounted_agents and gui_root:
                # Get current roster or start with empty
                current_roster = gui_root.get_active_agents() or []
                log_message(f"ROSTER_UPDATE: Retrieved current roster size={len(current_roster)}")

                # Merge: add newly mounted agents that aren't already in roster
                current_names = {(r.get('name') or '').strip().lower() for r in current_roster}
                for agent in successfully_mounted_agents:
                    agent_name = (agent.get('name') or '').strip().lower()
                    if agent_name not in current_names:
                        current_roster.append(agent)
                        log_message(f"ROSTER_UPDATE: Added {agent.get('name')} to active roster")
                    else:
                        log_message(f"ROSTER_UPDATE: Skipped {agent.get('name')} (already in roster)")

                # Persist updated roster
                log_message(f"ROSTER_UPDATE: About to persist roster with {len(current_roster)} agents")
                gui_root.set_active_agents(current_roster)
                log_message(f"ROSTER_UPDATE: Persisted roster with {len(current_roster)} agents")
            elif roster and hasattr(self.root, 'set_active_agents'):
                # No new mounts, but persist original roster if it existed
                log_message(f"ROSTER_UPDATE: No new mounts, persisting original roster with {len(roster)} agents")
                self.root.set_active_agents(roster)
            else:
                log_message(f"ROSTER_UPDATE: No agents to persist (successfully_mounted={len(successfully_mounted_agents)}, roster={len(roster)})")

            log_message(
                f"AGENT_MOUNT: operation=mount_all_complete total={len(roster)} mounted={mounted_count} "
                f"failed={failed_count} status={'SUCCESS' if failed_count == 0 else 'PARTIAL'}",
                level='INFO'
            )

        except Exception as e:
            try:
                self.add_message('error', f"Mount agents error: {e}")
                log_exception(
                    f"AGENT_MOUNT: operation=mount_all_exception error='{e}'"
                )
            except Exception:
                pass

    def _unmount_agents_all(self):
        try:
            # Get roster and destroy all agent servers
            roster = []
            if hasattr(self.root, 'get_active_agents') and callable(getattr(self.root, 'get_active_agents')):
                roster = self.root.get_active_agents() or []

            # Import agent server manager
            try:
                from agent_server_manager import get_agent_server_manager
                agent_server_mgr = get_agent_server_manager()

                for a in roster:
                    name = a.get('name', 'agent')
                    try:
                        if agent_server_mgr.destroy_server_for_agent(name):
                            self.add_message('system', f"Agent {name}: server destroyed")
                            # Remove port from roster
                            a.pop('_server_port', None)
                    except Exception as e:
                        self.add_message('error', f"Agent {name}: destroy error: {e}")

            except Exception as e:
                self.add_message('error', f"Failed to access agent server manager: {e}")

            self._agents_mounted = False
            self.add_message('system', f"All agents unmounted")
            try:
                self._agents_mounted_set = set()
            except Exception:
                pass
            try:
                self._agent_server_ports.clear()
            except Exception:
                pass
        except Exception as e:
            self.add_message('error', f"Unmount error: {e}")

    def _resolve_agent_backend_and_model(self, agent: dict):
        """Return (backend, model_hint) for an agent with inheritance resolution.
        model_hint is .gguf path for llama_server or ollama tag for Ollama.
        """
        agent_name = agent.get('name', 'unknown')
        agent_backend_config = agent.get('backend')

        log_message(
            f"AGENT_ROUTING: operation=resolve_backend_start agent={agent_name} "
            f"agent_backend={agent_backend_config} variant={agent.get('variant')}",
            level='INFO'
        )

        try:
            backend = (agent.get('backend') or '').strip().lower() or self._get_chat_backend()
        except Exception:
            backend = self._get_chat_backend()

        global_backend = self._get_chat_backend()
        backend_source = 'agent_override' if agent_backend_config else 'global_default'

        log_message(
            f"AGENT_ROUTING: operation=backend_resolved agent={agent_name} backend={backend} "
            f"source={backend_source} global_backend={global_backend}",
            level='INFO'
        )

        model_hint = None
        model_source = None

        if backend == 'llama_server':
            # Prefer direct gguf override
            model_hint = agent.get('gguf_override')
            if model_hint:
                model_source = 'gguf_override'

            if not model_hint:
                # Try to resolve from assigned artifacts
                try:
                    from pathlib import Path
                    import sys
                    cfg_path = Path(__file__).parent.parent.parent.parent
                    if str(cfg_path) not in sys.path:
                        sys.path.insert(0, str(cfg_path))
                    from config import get_local_artifacts_by_variant
                    vid = agent.get('variant')
                    arts = get_local_artifacts_by_variant(vid) if vid else []
                    if arts:
                        model_hint = arts[0].get('gguf')
                        model_source = 'variant_artifacts'
                except Exception as e:
                    log_message(
                        f"AGENT_ROUTING: operation=model_resolve_variant_failed agent={agent_name} error='{e}'",
                        level='DEBUG'
                    )
                    model_hint = None

            if not model_hint:
                # Last resort: backend default .gguf (could be a path)
                model_hint = self._llama_server_default_model()
                model_source = 'backend_default'

        elif backend == 'ollama':
            model_hint = agent.get('ollama_tag')
            if model_hint:
                model_source = 'ollama_tag_override'

            if not model_hint:
                # Try any assigned tag via lineage
                try:
                    import sys
                    from pathlib import Path
                    cfg_path = Path(__file__).parent.parent.parent.parent
                    if str(cfg_path) not in sys.path:
                        sys.path.insert(0, str(cfg_path))
                    from config import get_assigned_tags_by_lineage, get_lineage_id
                    vid = agent.get('variant')
                    lid = get_lineage_id(vid) if vid else None
                    tags = get_assigned_tags_by_lineage(lid) if lid else []
                    if tags:
                        model_hint = tags[0]
                        model_source = 'lineage_tags'
                except Exception as e:
                    log_message(
                        f"AGENT_ROUTING: operation=model_resolve_lineage_failed agent={agent_name} error='{e}'",
                        level='DEBUG'
                    )
                    model_hint = None

        log_message(
            f"AGENT_ROUTING: operation=resolve_complete agent={agent_name} backend={backend} "
            f"model={model_hint} model_source={model_source}",
            level='INFO'
        )

        return backend, model_hint

    def _get_agent_server_port(self, agent_name: str) -> int | None:
        """Get the dedicated llama.cpp server port for an agent.

        Returns the port number if agent has a dedicated server spawned, None otherwise.
        """
        try:
            cached_port = None
            try:
                cached_port = self._agent_server_ports.get(agent_name)
            except Exception:
                cached_port = None
            if cached_port:
                log_message(
                    f"AGENT_ROUTING: operation=port_lookup_cached agent={agent_name} port={cached_port}",
                    level='DEBUG'
                )
                return int(cached_port)
            # Get agent from roster
            roster = []
            if hasattr(self.root, 'get_active_agents') and callable(getattr(self.root, 'get_active_agents')):
                roster = self.root.get_active_agents() or []

            log_message(
                f"AGENT_ROUTING: operation=port_lookup_start agent={agent_name} roster_size={len(roster)}",
                level='INFO'
            )

            for r in roster:
                if (r.get('name') or '').strip().lower() == agent_name.strip().lower():
                    # Check if agent has _server_port set by agents_tab
                    port = r.get('_server_port')
                    if port:
                        log_message(
                            f"AGENT_ROUTING: operation=port_lookup_found agent={agent_name} port={port} mounted=True",
                            level='INFO'
                        )
                        try:
                            self._agent_server_ports[agent_name] = int(port)
                        except Exception:
                            pass
                        return int(port)
                    else:
                        log_message(
                            f"AGENT_ROUTING: operation=port_lookup_found agent={agent_name} port=None mounted=False "
                            f"reason='agent exists but not mounted'",
                            level='WARNING'
                        )
                    break

            # Agent not found in roster
            available_agents = [r.get('name', 'unnamed') for r in roster]
            log_message(
                f"AGENT_ROUTING: operation=port_lookup_not_found agent={agent_name} "
                f"available_agents={available_agents}",
                level='WARNING'
            )

        except Exception as e:
            log_exception(
                f"AGENT_ROUTING: operation=port_lookup_exception agent={agent_name} error='{e}'"
            )

        return None

    def _qa_open_tab(self, tab, subtab=None, session=None):
        """Best-effort open of another tab from Quick Actions.
        Sends a payload to a root-level navigator if available; otherwise logs.
        """
        try:
            payload = {'tab': tab}
            if subtab:
                payload['subtab'] = subtab
            if session:
                payload['session'] = session
            # If root has a generic navigator, use it
            if hasattr(self.root, 'open_app_tab') and callable(getattr(self.root, 'open_app_tab')):
                self.root.open_app_tab(payload)
                return
            # Fallback: try to select a known notebook if exposed
            try:
                if hasattr(self.root, 'notebook'):
                    nb = self.root.notebook
                    # naive match by tab text
                    for i in range(nb.index('end')):
                        if tab.lower() in str(nb.tab(i, 'text')).lower():
                            nb.select(i)
                            break
            except Exception:
                pass
        except Exception:
            pass

    # --- Indicator helpers ---------------------------------------------
    def _poll_indicators(self):
        try:
            # Avoid refreshing while tooltip is shown to prevent flicker
            if not getattr(self, '_tooltip_active', False):
                self._update_quick_indicators()
        except Exception:
            pass
        try:
            self._indicators_job = self.root.after(2000, self._poll_indicators)
        except Exception:
            pass
        # Also poll promotion events best-effort
        try:
            self._poll_promotion_events()
        except Exception:
            pass

    def _poll_promotion_events(self):
        """Check for new promotion events and prompt to update agent permissions."""
        try:
            from pathlib import Path
            import json as _J
            p = Path('Data')/'user_prefs'/'promotion_events.json'
            if not p.exists():
                return
            events = _J.loads(p.read_text()) or []
            if not events:
                return
            # Find newest event beyond last seen
            for ev in reversed(events):  # newest first
                ts = ev.get('ts')
                if self._last_promotion_event_ts and ts <= self._last_promotion_event_ts:
                    break
                variant = ev.get('variant')
                to_class = ev.get('to_class')
                self._prompt_update_permissions(variant, to_class)
                self._last_promotion_event_ts = ts
                break
        except Exception:
            pass

    def _prompt_update_permissions(self, variant_id: str, to_class: str):
        try:
            from tkinter import messagebox
            msg = (f"Variant {variant_id} promoted to {to_class}.\n\n"
                   f"Update this agent's per-session tool permissions across chats/projects?\n\n"
                   f"Yes = apply now, No = keep current session, Later = don't change current session")
            res = messagebox.askyesnocancel('Promotion', msg)
        except Exception:
            res = None
        try:
            # Defaults update (for new sessions) always applied
            self._update_agent_defaults_for_variant(variant_id)
        except Exception:
            pass
        if res is True:
            try:
                self._apply_permissions_to_live_sessions(variant_id)
            except Exception:
                pass

    def _recompute_tools_for_variant(self, variant_id: str) -> dict:
        try:
            from config import load_model_profile, get_tools_for_type_class, get_unified_tool_profile
            mp = load_model_profile(variant_id) or {}
            type_id = mp.get('assigned_type') or 'unassigned'
            class_level = mp.get('class_level') or 'novice'
            allowed = get_tools_for_type_class(type_id, class_level) or []
            prof = get_unified_tool_profile('Default')
            tool_universe = list((prof.get('tools') or {}).get('enabled_tools', {}).keys())
            if allowed == ['*']:
                return {t: True for t in tool_universe}
            return {t: (t in allowed) for t in tool_universe}
        except Exception:
            return {}

    def _update_agent_defaults_for_variant(self, variant_id: str):
        try:
            from pathlib import Path
            import json as _J
            tools_map = self._recompute_tools_for_variant(variant_id)
            g = Path('Data')/'user_prefs'/'agents_default.json'
            for path in [g]:
                try:
                    if not path.exists():
                        continue
                    data = _J.loads(path.read_text()) or []
                    changed = False
                    for rec in data:
                        if (rec.get('variant') or '').strip() == variant_id:
                            rec['enabled_tools'] = tools_map
                            changed = True
                    if changed:
                        path.write_text(_J.dumps(data, indent=2))
                except Exception:
                    pass
        except Exception:
            pass

    def _apply_permissions_to_live_sessions(self, variant_id: str):
        try:
            tools_map = self._recompute_tools_for_variant(variant_id)
            roster = []
            if hasattr(self.root, 'get_active_agents') and callable(getattr(self.root, 'get_active_agents')):
                roster = self.root.get_active_agents() or []
            changed = False
            for rec in roster:
                if (rec.get('variant') or '').strip() == variant_id:
                    rec['enabled_tools'] = tools_map
                    changed = True
            if changed and hasattr(self.root, 'set_active_agents'):
                self.root.set_active_agents(roster)
        except Exception:
            pass

    def _update_quick_indicators(self, reason: str = "normal"):
        """Refresh quick indicators with aggressive logging and throttled probes."""
        inst = id(self)
        now = time.time()
        self._last_indicator_log_ts = getattr(self, '_last_indicator_log_ts', 0.0)
        self._last_indicator_state = getattr(self, '_last_indicator_state', None)

        def _maybe_log(msg: str, key: str | None = None, force: bool = False):
            try:
                if not force:
                    if key is not None and key == self._last_indicator_state and now - self._last_indicator_log_ts < 30:
                        return
                _debug_log(msg)
                self._last_indicator_log_ts = now
                if key is not None:
                    self._last_indicator_state = key
            except Exception:
                pass

        # Build a fingerprint of current indicator state; only rebuild when changed
        wd = None
        try:
            if self.tool_executor:
                wd = self.tool_executor.get_working_directory()
            if not wd:
                wd = self.backend_settings.get('working_directory')
        except Exception as e:
            _debug_log(f"CHAT_DBG: indicators wd error instance={inst} err={e}")
            wd = None

        # Roster signature so indicators refresh on agent add/remove without requiring relaunch/save
        try:
            roster = []
            if hasattr(self.root, 'get_active_agents') and callable(getattr(self.root, 'get_active_agents')):
                roster = self.root.get_active_agents() or []
            def _sig(r: dict) -> str:
                try:
                    name = (r.get('name') or 'agent').strip()
                    v = (r.get('variant') or '').strip()
                    t = (r.get('ollama_tag') or '').strip()
                    g = (r.get('gguf_override') or '').strip()
                    return f"{name}:{v}:{t}:{g}"
                except Exception as e:
                    _debug_log(f"CHAT_DBG: roster sig err instance={inst} err={e}")
                    return ''
            roster_sig = tuple(sorted([_sig(r) for r in roster if r and r.get('active', True)]))
        except Exception as e:
            _debug_log(f"CHAT_DBG: roster error instance={inst} err={e}")
            roster_sig = tuple()

        tool_status_map = {}
        try:
            if hasattr(self, 'session_enabled_tools') and isinstance(self.session_enabled_tools, dict) and self.session_enabled_tools:
                tool_status_map = dict(self.session_enabled_tools)
            elif hasattr(self.parent_tab, 'tools_interface') and self.parent_tab.tools_interface:
                ti = self.parent_tab.tools_interface
                tool_status_map = {k: bool(v.get()) for k, v in (getattr(ti, 'tool_vars', {}) or {}).items()}
            else:
                tool_status_map = self.load_enabled_tools() or {}
        except Exception as e:
            _debug_log(f"CHAT_DBG: tool map error instance={inst} err={e}")
            tool_status_map = {}

        enabled_tools = sorted([name for name, enabled in tool_status_map.items() if enabled])
        disabled_tools = sorted([name for name, enabled in tool_status_map.items() if not enabled])

        todo_active = False
        try:
            tab_map = getattr(self.parent_tab, 'tab_instances', None)
            settings_inst = tab_map.get('settings_tab', {}).get('instance') if isinstance(tab_map, dict) else None
            todo_active = bool(settings_inst is not None and getattr(settings_inst, 'todo_popup_active', False))
        except Exception as e:
            _debug_log(f"CHAT_DBG: todo flag error instance={inst} err={e}")
            todo_active = False

        backend = self._get_chat_backend()
        backend_url = self._llama_server_base_url() if backend == 'llama_server' else ''
        backend_url_key = backend_url.rstrip('/')
        if self.backend_settings.get('enable_debug_logging', False):
            _debug_log(f"CHAT_DBG: indicators state instance={inst} backend={backend} url={backend_url_key}")

        # Determine cached server status
        server_online = getattr(self, '_server_online_cached', None)
        last_probe_ts = float(getattr(self, '_server_online_ts', 0) or 0)
        now = time.time()
        ttl = float(self.backend_settings.get('llama_server_probe_ttl', 3.0) or 3.0)
        cache_entry = _SERVER_STATUS_CACHE.get(backend_url_key) if backend_url_key else None
        if cache_entry:
            server_online = cache_entry.get('online')
            last_probe_ts = cache_entry.get('ts', last_probe_ts)

        # Compose state key without forcing probes
        state_key = (
            int(self._think_next_min or 0),
            int(self._think_next_max or 0),
            str(wd or ''),
            tuple(enabled_tools),
            tuple(disabled_tools),
            todo_active,
            str(self.current_mode or ''),
            int(1 if self.show_thoughts else 0),
            int(1 if getattr(self, 'rag_enabled', False) else 0),
            int(1 if getattr(self, 'training_mode_enabled', False) else 0),
            int(1 if bool(self.backend_settings.get('training_support_enabled', False)) else 0),
            str(getattr(self, 'temp_mode', 'manual')),
            int(round(float(getattr(self, 'session_temperature', 0.8)) * 10)),
            str(self.current_system_prompt or 'OFF'),
            str(self.current_tool_schema or 'OFF'),
            backend,
            backend_url_key,
            str(server_online),
            str(getattr(self, 'agentic_project_override', 'None')),
            roster_sig,
            int(self.backend_settings.get('n_gpu_layers', 25)),
            int(self.backend_settings.get('cpu_threads', 8)),
        )

        if state_key == getattr(self, '_qa_state_key', None):
            return
        self._qa_state_key = state_key

        _maybe_log(
            f"CHAT_DBG: indicators start instance={inst} reason={reason} generating={getattr(self, 'is_generating', False)}",
            key=f"start:{reason}:{getattr(self, 'is_generating', False)}"
        )

        # Schedule background probe if needed
        probe_enabled = bool(self.backend_settings.get('status_probes_enabled', True))
        probe_allowed = (
            probe_enabled and backend == 'llama_server' and not getattr(self, 'is_generating', False)
        )
        probe_stale = (now - last_probe_ts) > ttl
        if probe_allowed and probe_stale and backend_url_key:
            self._schedule_server_probe(backend_url_key, reason)
        else:
            _debug_log(f"CHAT_DBG: indicators probe skip instance={inst} allowed={probe_allowed} stale={probe_stale} url={backend_url_key}")

        # Clear previous icons
        try:
            for w in self.qa_indicators.winfo_children():
                w.destroy()
        except Exception:
            return

        try:
            capability_messages = []
            if backend == 'llama_server':
                backend_line = f"Backend: llama.cpp server\nURL: {backend_url or 'http://127.0.0.1:8002'}"
                capability_messages.append(backend_line)
                # Live status using cached probe (avoid extra requests during frequent UI updates)
                try:
                    ok = bool(server_online)
                    info = 'cached'
                    status = f"Status: {'Online' if ok else 'Offline'} — {info}"
                    capability_messages.append(status)
                except Exception:
                    capability_messages.append('Status: Unknown')
                capability_messages.append('GPU: Vulkan (llama.cpp server)')
                capability_messages.append('Streaming: yes')
                capability_messages.append('JSON: partial support')
            else:
                capability_messages.append('Backend: Ollama')
                capability_messages.append('Streaming: yes')
                capability_messages.append('JSON: native (format=json)')

            if capability_messages:
                # Add an explicit route line for clarity
                try:
                    route_backend = getattr(self, 'current_backend', self._get_chat_backend())
                    if backend == 'llama_server':
                        capability_messages.append(f"Route: llama_server → {backend_url}")
                    else:
                        capability_messages.append(f"Route: {route_backend}")
                except Exception:
                    pass
                self._make_scroll_indicator(self.qa_indicators, 'ℹ️', capability_messages)

            # Resource allocation indicator (GPU layers or CPU threads)
            try:
                if backend == 'llama_server':
                    n_gpu_layers = self.backend_settings.get('n_gpu_layers', 25)
                    self._make_indicator(self.qa_indicators, '⚙️', lambda layers=n_gpu_layers: f"GPU Layers: {layers}")
                else:
                    cpu_threads = self.backend_settings.get('cpu_threads', 8)
                    self._make_indicator(self.qa_indicators, '⚙️', lambda threads=cpu_threads: f"CPU Threads: {threads}")
            except Exception:
                pass

            tool_messages = [self._tool_pipeline_tooltip()]
            tool_messages.extend(self._format_tool_scroll_entries("Active tools", enabled_tools))
            tool_messages.extend(self._format_tool_scroll_entries("Disabled tools", disabled_tools, disabled=True))
            tool_messages.append("End of list")
            self._make_scroll_indicator(self.qa_indicators, '🔧', tool_messages)
        except Exception:
            pass

        # System capacity indicator (CPU/RAM/VRAM best-effort)
        try:
            sys_lines = []
            # CPU cores and load
            try:
                import os as _os
                cores = _os.cpu_count() or 1
                # Load average if available
                try:
                    la1, la5, la15 = _os.getloadavg()
                    sys_lines.append(f"CPU: {cores} cores | load {la1:.2f}/{la5:.2f}/{la15:.2f}")
                except Exception:
                    sys_lines.append(f"CPU: {cores} cores")
            except Exception:
                pass
            # RAM
            try:
                with open('/proc/meminfo', 'r') as f:
                    meminfo = f.read()
                def _parse(k):
                    import re
                    m = re.search(rf'^{k}:\s+(\d+) kB', meminfo, re.M)
                    return int(m.group(1)) if m else 0
                total = _parse('MemTotal')
                free = _parse('MemAvailable') or _parse('MemFree')
                used = total - free
                t_gb = total/1024/1024
                u_gb = used/1024/1024
                sys_lines.append(f"RAM: {u_gb:.1f} / {t_gb:.1f} GB")
            except Exception:
                pass
            # VRAM via nvidia-smi (optional) or rocm-smi fallback
            try:
                import subprocess as _sp
                res = _sp.run(['nvidia-smi','--query-gpu=memory.used,memory.total,name','--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=1)
                if res.returncode == 0 and res.stdout.strip():
                    line = res.stdout.strip().splitlines()[0]
                    used, total, name = [x.strip() for x in line.split(',')]
                    sys_lines.append(f"VRAM: {used} / {total} MB ({name})")
                else:
                    raise RuntimeError('nvidia-smi not available')
            except Exception:
                try:
                    import subprocess as _sp
                    res = _sp.run(['rocm-smi','--showmemuse'], capture_output=True, text=True, timeout=1)
                    if res.returncode == 0 and res.stdout:
                        import re as _re
                        # Best-effort parse for first GPU line showing VRAM used/total
                        used_m = _re.search(r"VRAM.*?Used:\s*([0-9.]+)\s*MiB", res.stdout, _re.I)
                        tot_m = _re.search(r"VRAM.*?Total:\s*([0-9.]+)\s*MiB", res.stdout, _re.I)
                        if used_m and tot_m:
                            sys_lines.append(f"VRAM: {used_m.group(1)} / {tot_m.group(1)} MB (ROCm)")
                except Exception:
                    pass
            if sys_lines:
                self._make_scroll_indicator(self.qa_indicators, '🖥️', sys_lines)
        except Exception:
            pass

        # Agents indicator (best-effort): show whether agentic project is enabled (session override aware), and roster
        try:
            agent_lines = []
            try:
                ov = getattr(self, 'agentic_project_override', None)
            except Exception:
                ov = None
            base_on = bool(self.advanced_settings.get('agentic_project', {}).get('enabled', False))
            if ov is None:
                agent_lines.append(f"Agentic project: {'ENABLED' if base_on else 'DISABLED'} (default)")
            else:
                agent_lines.append(f"Agentic project: {'ENABLED' if ov else 'DISABLED'} (session)")
            # If a status provider exists, include active roster
            roster = []
            if hasattr(self.root, 'get_active_agents') and callable(getattr(self.root, 'get_active_agents')):
                try:
                    roster = self.root.get_active_agents() or []  # list of dicts: {'name','active','working','scope'}
                except Exception:
                    roster = []
            if roster:
                agent_lines.append('Active agents:')
                for a in roster[:8]:
                    name = a.get('name','Agent')
                    active = 'Y' if a.get('active') else 'N'
                    working = 'Y' if a.get('working') else 'N'
                    scope = a.get('scope','interface')
                    be = (a.get('backend') or 'inherit')
                    hw = (a.get('hardware') or 'inherit')
                    agent_lines.append(f"• {name} | Active:{active} | Working:{working} | {scope} | {be}/{hw}")
            else:
                agent_lines.append('Active agents: none detected')
            # Also show which agents are set by default (what will mount)
            try:
                from pathlib import Path as _P
                import json as _J
                proj = None
                if hasattr(self.parent_tab, 'settings_interface') and getattr(self.parent_tab.settings_interface, 'current_project_context', None):
                    proj = self.parent_tab.settings_interface.current_project_context
                src = None
                if proj and (_P('Data')/'projects'/proj/'agents_default.json').exists():
                    src = _P('Data')/'projects'/proj/'agents_default.json'
                elif (_P('Data')/'user_prefs'/'agents_default.json').exists():
                    src = _P('Data')/'user_prefs'/'agents_default.json'
                if src:
                    d = _J.loads(src.read_text()) or []
                    # Only show defaults when no live roster is set to avoid confusion
                    if not roster:
                        names = ", ".join([x.get('name','agent') for x in d])
                        agent_lines.append(f"Set agents (default): {len(d)} — {names}")
            except Exception:
                pass
            self._make_scroll_indicator(self.qa_indicators, '🤖', agent_lines)
        except Exception:
            pass

        # Agent event logging toggle indicator
        try:
            on = bool(getattr(self, 'agent_events_logging_enabled', True))
            self._make_indicator(self.qa_indicators, '🗒️', lambda: f"Agent events: {'ON' if on else 'OFF'}")
        except Exception:
            pass

        # ThinkTime pending
        if (self._think_next_min or self._think_next_max):
            self._make_indicator(self.qa_indicators, '⏱', lambda: f"ThinkTime pending: min={int(self._think_next_min or 0)}s, max={int(self._think_next_max or 0)}s")

        # Training status indicator (reflects per-chat Training Mode and backend Training Support)
        try:
            t_on = bool(getattr(self, 'training_mode_enabled', False))
            s_on = bool(self.backend_settings.get('training_support_enabled', False))
            self._make_indicator(self.qa_indicators, '🏋️', lambda: f"Training: {'ON' if t_on else 'OFF'} | Support: {'ON' if s_on else 'OFF'}")
        except Exception:
            pass

        # Working directory (allow child tabs to suppress)
        if wd and not getattr(self, '_suppress_base_workdir_indicator', False):
            self._make_indicator(self.qa_indicators, '📂', lambda wdir=wd: f"Working dir: {wdir}")

        # Combined Prompt/Schema indicator
        try:
            # An item is considered "active" if it's not explicitly turned off (i.e., not None or empty string)
            sp_active = self.current_system_prompt not in (None, '', 'None')
            # If no explicit schema selected, try applying a type-default once
            if not self._type_default_applied and (self.current_tool_schema in (None, '', 'None')):
                try:
                    import config as C
                    vid = (self.current_model or '').strip()
                    if vid:
                        try:
                            mp = C.load_model_profile(vid) or {}
                            at = mp.get('assigned_type')
                            assigned_type = at[0] if isinstance(at, list) else at
                        except Exception:
                            assigned_type = None
                        groups = C.list_type_schemas() if hasattr(C, 'list_type_schemas') else {}
                        if assigned_type and isinstance(groups, dict):
                            names = groups.get(assigned_type) or []
                            if names:
                                self.current_tool_schema = names[0]
                                self._schema_source = 'type-default'
                    self._type_default_applied = True
                except Exception:
                    self._type_default_applied = True
            ts_active = self.current_tool_schema not in (None, '', 'None')

            if sp_active or ts_active:
                tooltip_parts = []
                # Use the actual value, or 'default' if for some reason it's an empty string but not None
                sp_name = self.current_system_prompt or 'default'
                ts_name = self.current_tool_schema or 'default'

                if sp_active:
                    tooltip_parts.append(f"Prompt: {sp_name}")
                if ts_active:
                    if getattr(self, '_schema_source', None) == 'type-default':
                        tooltip_parts.append(f"Schema: type-default ({ts_name})")
                    else:
                        tooltip_parts.append(f"Schema: {ts_name}")
                
                tooltip_text = "\n".join(tooltip_parts)
                self._make_indicator(self.qa_indicators, '📝', lambda t=tooltip_text: t)
        except Exception:
            pass

        # ToDo popup active
        if todo_active:
            self._make_indicator(self.qa_indicators, '🗒', lambda: "ToDo popup is open")

        # Mode indicator
        try:
            mode_name = (self.current_mode or 'smart').capitalize()
            self._make_indicator(self.qa_indicators, '⚡', lambda m=mode_name: f"Mode: {m}")
        except Exception:
            pass
        # Show Thoughts indicator
        if bool(self.show_thoughts):
            self._make_indicator(self.qa_indicators, '👁', lambda: "Show Thoughts: ON (streaming preview)")

        # Tracker indicator
        if self.is_tracker_active:
            self._make_indicator(self.qa_indicators, '🔍', lambda: "Tracker window is open")

        # Temperature indicator
        try:
            tmode = (getattr(self, 'temp_mode', 'manual') or 'manual').capitalize()
            val = float(getattr(self, 'session_temperature', 0.8))
            self._make_indicator(self.qa_indicators, '🌡️', lambda tm=tmode, v=val: f"Temp: {v:.1f} ({tm})")
        except Exception:
            pass
        # RAG indicator with dynamic connected chat count and level
        if not getattr(self, '_suppress_base_rag_indicator', False) and self._is_rag_active():
            try:
                count = self._get_rag_connected_chat_count()
            except Exception:
                count = 0

            # Build method + scope indicator string
            method = getattr(self, 'rag_scoring_method', 'standard')
            method_icons = {'standard': '🧠', 'vcm': '🧠+', 'auto': '🧠++', 'manual': '🔧'}
            method_icon = method_icons.get(method, '🧠')

            # Build scope string
            scopes = []
            try:
                if getattr(self, '_rag_scope_personal', None) and self._rag_scope_personal.get():
                    scopes.append('P')
                if getattr(self, '_rag_scope_project', None) and self._rag_scope_project.get():
                    scopes.append('Proj')
                if getattr(self, '_rag_scope_topics', None) and self._rag_scope_topics.get():
                    scopes.append('T')
            except Exception:
                pass

            scope_str = '+'.join(scopes) if scopes else 'None'
            self._make_indicator(self.qa_indicators, method_icon, lambda c=count, s=scope_str: f"RAG: {s} — Connected: {c}")

    def _get_rag_connected_chat_count(self) -> int:
        """Count conversations contributing to unified RAG (rag_enabled=True).

        Includes persisted conversations marked rag_enabled and, if applicable,
        the current in-memory session if toggled but not yet saved.
        """
        count = 0
        try:
            if not self.chat_history_manager:
                return 1 if getattr(self, 'rag_enabled', False) else 0
            convs = self.chat_history_manager.list_conversations()
            for rec in convs:
                meta = rec.get('metadata') or {}
                if bool(meta.get('rag_enabled', False)):
                    count += 1
            # If current session is RAG-enabled but not yet reflected in storage, include it
            try:
                current_id = getattr(self, 'current_session_id', None)
                is_current_counted = False
                if current_id:
                    for rec in convs:
                        if rec.get('session_id') == current_id:
                            is_current_counted = bool((rec.get('metadata') or {}).get('rag_enabled', False))
                            break
                if getattr(self, 'rag_enabled', False) and not is_current_counted:
                    count += 1
            except Exception:
                pass
        except Exception:
            pass
        return count

    def _is_rag_active(self) -> bool:
        """True if per-chat RAG is on or any RAG scope is enabled."""
        try:
            # Check per-chat RAG flag
            if bool(getattr(self, 'rag_enabled', False)):
                return True

            # Check if any scope checkbox is enabled
            personal = getattr(self, '_rag_scope_personal', None)
            project = getattr(self, '_rag_scope_project', None)
            topics = getattr(self, '_rag_scope_topics', None)

            if personal and personal.get():
                return True
            if project and project.get():
                return True
            if topics and topics.get():
                return True

            return False
        except Exception:
            return bool(getattr(self, 'rag_enabled', False))

    def _rag_query_scope(self) -> str | None:
        """Override in Projects tab to return current project name for scoped retrieval."""
        return None

    def _vector_scope_active(self) -> bool:
        """Return True if vector retrieval should be used for current context."""
        if not getattr(self, '_vector_backend_available', False):
            return False
        try:
            return bool(self._rag_scope_vector.get())
        except Exception:
            return False

    def _get_agent_rag_context(self, agent_name: str, prompt: str, *, top_k: int = 3) -> Dict[str, str]:
        """Collect RAG/context snippets for agent inference."""
        context: Dict[str, str] = {}
        message = prompt or ""
        try:
            session_ctx = self._build_rag_context(message, max_chars=1200, per_snippet_max=400, top_k=top_k)
            if session_ctx:
                context['session_context'] = session_ctx
        except Exception:
            pass

        try:
            if getattr(self, '_rag_scope_project', None) and self._rag_scope_project.get() and getattr(self, 'current_project', None):
                project_ctx, _dbg, _score = self._retrieve_rag_l2_vcm(message, max_chars=1500, top_k=top_k, scope=self.current_project)
                if project_ctx:
                    context['project_context'] = project_ctx
        except Exception:
            pass

        try:
            if getattr(self, '_rag_scope_topics', None) and self._rag_scope_topics.get():
                kb_ctx, _dbg, _score = self._retrieve_rag_l2_vcm(message, max_chars=1500, top_k=top_k, scope=None)
                if kb_ctx:
                    context['knowledge_bank'] = kb_ctx
        except Exception:
            pass

        try:
            if self._vector_scope_active() and getattr(self, 'rag_service', None):
                hits = self.rag_service.query(message, top_k=top_k, scope=self.current_project if getattr(self, '_rag_scope_project', None) and self._rag_scope_project.get() else None)
                buf = []
                for idx, (doc, score) in enumerate(hits, 1):
                    snippet = (doc.text or '')[:400]
                    buf.append(f"[Vector {idx}] (session={doc.session_id}, score={score:.3f})\n{snippet}")
                if buf:
                    context['vector_context'] = "\n\n".join(buf)
        except Exception:
            pass

        return context

    def _agent_context_messages(self, context: Dict[str, str]) -> List[Dict[str, str]]:
        """Convert agent RAG context dict to prompt messages."""
        mapping = [
            ('session_context', "RAG Context (session snippets)"),
            ('project_context', "Project RAG Context"),
            ('knowledge_bank', "Knowledge Bank Context"),
            ('vector_context', "Vector RAG Context"),
        ]
        messages: List[Dict[str, str]] = []
        for key, label in mapping:
            text = context.get(key)
            if not text:
                continue
            messages.append({
                "role": "system",
                "content": f"{label}:\n{text}"
            })
        return messages

    # --- Prompt diagnostics -------------------------------------------------
    def _estimate_token_count(self, text: str) -> int:
        if not text:
            return 0
        tokens = re.findall(r"\S+", str(text))
        if tokens:
            return len(tokens)
        return max(1, len(text) // 4)

    def _messages_have_roles(self, messages: List[Dict[str, Any]]) -> bool:
        try:
            for msg in messages or []:
                role = (msg.get('role') or '').lower()
                if role not in {'user', ''}:
                    return True
        except Exception:
            pass
        return False

    def _get_model_context_limit(self, model_name: Optional[str] = None) -> int:
        model = model_name or self.current_model or ''
        limit_candidates = []
        try:
            per_model = self.backend_settings.get('model_context_limits')
            if isinstance(per_model, dict):
                if model in per_model:
                    limit_candidates.append(per_model[model])
                short = Path(model).name
                if short in per_model:
                    limit_candidates.append(per_model[short])
        except Exception:
            pass
        try:
            limit_candidates.append(self.backend_settings.get('llama_server_num_ctx'))
            limit_candidates.append(self.backend_settings.get('max_context_tokens'))
        except Exception:
            pass
        for candidate in limit_candidates:
            try:
                if candidate:
                    val = int(candidate)
                    if val > 0:
                        return val
            except Exception:
                continue
        # Fallback default
        return 4096

    def _collect_prompt_diagnostics(self, messages: List[Dict[str, Any]], tool_schemas) -> Dict[str, Any]:
        diag: Dict[str, Any] = {
            'timestamp': datetime.utcnow().isoformat(),
            'backend': self._get_chat_backend(),
            'model': self.current_model or '',
            'tool_count': len(tool_schemas or []),
            'flags': {
                'rag_enabled': bool(getattr(self, 'rag_enabled', False)),
                'rag_active': bool(self._is_rag_active()),
                'training_mode': bool(getattr(self, 'training_mode_enabled', False)),
                'show_thoughts': bool(getattr(self, 'show_thoughts', False)),
            },
            'messages': len(messages or []),
        }
        system_tokens = 0
        rag_tokens = 0
        history_tokens = 0
        rag_entries: List[Dict[str, Any]] = []

        try:
            for msg in messages or []:
                content = msg.get('content') or ''
                role = (msg.get('role') or '').lower()
                tokens = self._estimate_token_count(content)
                if role == 'system':
                    if isinstance(content, str) and content.startswith('RAG Context'):
                        rag_tokens += tokens
                    else:
                        system_tokens += tokens
                else:
                    history_tokens += tokens
        except Exception:
            pass

        rag_meta = self._last_rag_context or {}
        rag_entries = rag_meta.get('snippets', []) if isinstance(rag_meta, dict) else []
        diag['rag_context'] = rag_meta

        total_tokens = system_tokens + rag_tokens + history_tokens
        limit = self._get_model_context_limit()
        diag['tokens'] = {
            'system': system_tokens,
            'rag': rag_tokens,
            'history': history_tokens,
            'total': total_tokens,
        }
        diag['limit'] = limit
        diag['over_limit'] = max(0, total_tokens - limit)

        # Capture last user preview for context
        try:
            last_user = next((m for m in reversed(messages or []) if (m.get('role') or '').lower() == 'user'), None)
            if last_user:
                text = last_user.get('content', '')
                diag['last_user_preview'] = (text[:200] + ('…' if len(text) > 200 else ''))
        except Exception:
            pass

        return diag

    def _log_prompt_diagnostics(self, diag: Dict[str, Any]) -> None:
        try:
            tokens = diag.get('tokens', {})
            summary = (
                f"PROMPT_DIAG model={diag.get('model','?')} backend={diag.get('backend','?')} "
                f"total={tokens.get('total',0)} limit={diag.get('limit')} "
                f"rag={tokens.get('rag',0)} history={tokens.get('history',0)} system={tokens.get('system',0)} "
                f"tools={diag.get('tool_count',0)} rag_active={diag.get('flags',{}).get('rag_active')}"
            )
            log_message(summary)
        except Exception:
            pass

    def _ensure_context_within_limit(self, messages: List[Dict[str, Any]], tool_schemas) -> Dict[str, Any]:
        diag = self._collect_prompt_diagnostics(messages, tool_schemas)

        # If exceeding limit due to RAG, drop the RAG context before sending
        limit = diag.get('limit', 4096)
        total_tokens = diag.get('tokens', {}).get('total', 0)
        rag_tokens = diag.get('tokens', {}).get('rag', 0)
        if total_tokens > limit and rag_tokens > 0:
            removed = False
            try:
                before_len = len(messages)
                messages[:] = [
                    m for m in messages
                    if not ((m.get('role') or '').lower() == 'system' and str(m.get('content') or '').startswith('RAG Context'))
                ]
                if len(messages) != before_len:
                    removed = True
            except Exception:
                removed = False
            if removed:
                if self._last_rag_context is None:
                    self._last_rag_context = {}
                try:
                    self._last_rag_context['removed_due_to_limit'] = True
                    self._last_rag_context['limit'] = limit
                    self._last_rag_context['tokens_before_trim'] = total_tokens
                except Exception:
                    pass
                diag = self._collect_prompt_diagnostics(messages, tool_schemas)
                log_message(
                    f"PROMPT_DIAG: RAG context removed to respect limit {limit} (new_total={diag.get('tokens',{}).get('total',0)})"
                )
                # Capture as a RAGBudget event for bug tracker visibility
                try:
                    from bug_tracker import get_bug_tracker as _gbt
                    bt = _gbt() if _gbt else None
                    if bt:
                        bt.capture_log_event(
                            "RAGBudget",
                            f"RAG removed due to budget: limit={limit}, before={total_tokens}, after={diag.get('tokens',{}).get('total',0)}",
                            file_path=str(Path(__file__)),
                            line_number=0,
                            context_excerpt=[json.dumps(diag, default=str)[:2000]]
                        )
                except Exception:
                    pass

        self._last_prompt_diagnostics = diag
        self._log_prompt_diagnostics(diag)
        return diag

    def _ensure_llama_prompt_with_cache(self, has_tools: bool, has_roles: bool) -> None:
        try:
            state = self._last_prompt_ready_state or {'has_tools': None, 'has_roles': None, 'ts': 0.0}
        except Exception:
            state = {'has_tools': None, 'has_roles': None, 'ts': 0.0}
        now = time.time()
        if (
            state.get('has_tools') == has_tools
            and state.get('has_roles') == has_roles
            and (now - float(state.get('ts', 0))) < 5.0
        ):
            return
        try:
            self._ensure_llama_server_prompt_ready(has_tools, has_roles)
        except Exception:
            pass
        try:
            state['has_tools'] = has_tools
            state['has_roles'] = has_roles
            state['ts'] = now
            self._last_prompt_ready_state = state
        except Exception:
            pass

    def _summarize_context_overflow(self) -> str:
        diag = self._last_prompt_diagnostics or {}
        tokens = diag.get('tokens', {})
        limit = diag.get('limit', 0)
        total = tokens.get('total', 0)
        rag = tokens.get('rag', 0)
        history = tokens.get('history', 0)
        system = tokens.get('system', 0)
        parts = [f"payload {total} tokens", f"limit {limit}"]
        parts.append(f"history {history}")
        if rag:
            parts.append(f"rag {rag}")
        if system:
            parts.append(f"system {system}")
        return ', '.join(parts)

    def _handle_context_overflow(self, base_message: str) -> str:
        explanation = self._summarize_context_overflow()
        message = f"Context limit reached ({explanation}). Try trimming chat history or disabling extra context."
        diag = self._last_prompt_diagnostics or {}
        try:
            log_message(f"CONTEXT_DIAGNOSTICS: {json.dumps(diag, default=str)[:2000]}")
        except Exception:
            pass
        tracker = get_bug_tracker() if get_bug_tracker else None
        if tracker:
            try:
                tracker.capture_log_event(
                    "ContextLimit",
                    message,
                    file_path=str(Path(__file__)),
                    line_number=0,
                    function_name='_llama_server_chat',
                    context_excerpt=[json.dumps(diag, default=str)[:4000]],
                )
            except Exception:
                pass
        return message

    def _build_rag_context(self, user_message: str, max_chars: int = 1800, per_snippet_max: int = 600, top_k: int = 3) -> str:
        """Assemble retrieval context from rag-enabled chats.

        - Scores saved conversations by simple lexical overlap with the user message.
        - Pulls most relevant snippets and caps total characters for safety.
        - In Projects tab, prefers current project's rag-enabled chats.
        """
        try:
            um = (user_message or '').lower()
            if not um:
                return ''

            # Tokenize user message (very simple split)
            query_terms = [w for w in re.split(r"[^a-zA-Z0-9]+", um) if len(w) > 2]
            if not query_terms:
                query_terms = um.split()

            candidates = []  # list of (score, when, snippet)

            def summarize_chat(chat_history: list[dict]) -> str:
                # Prefer recent assistant outputs and user inputs
                texts = []
                for msg in chat_history[-12:]:  # last ~12 messages
                    role = msg.get('role'); content = (msg.get('content') or '').strip()
                    if not content:
                        continue
                    if role in ('assistant', 'user', 'system'):
                        texts.append(f"[{role}] {content}")
                return "\n".join(texts)

            def score_text(text: str) -> int:
                tl = text.lower()
                score = 0
                for t in query_terms:
                    if t and t in tl:
                        score += tl.count(t)
                return score

            # Helper to collect from a conversation record
            def consider_conv(record: dict, chat_history: list[dict]):
                meta = record.get('metadata') or {}
                if not bool(meta.get('rag_enabled', False)):
                    return
                summary = summarize_chat(chat_history)
                if not summary:
                    return
                s = score_text(summary)
                if s <= 0:
                    return
                when = record.get('saved_at') or ''
                snippet = summary[:per_snippet_max]
                candidates.append((s, when, snippet))

            import re, json as _json
            from datetime import datetime as _dt

            # If Projects tab with a current project: collect from project store
            try:
                if hasattr(self, 'current_project') and self.current_project:
                    from ..projects_manager import list_conversations as _plist
                    root = Path('Data/projects')/self.current_project
                    for rec in _plist(self.current_project):
                        sid = rec.get('session_id');
                        p = root / f"{sid}.json"
                        try:
                            data = _json.loads(p.read_text())
                            consider_conv(data, data.get('chat_history') or [])
                        except Exception:
                            continue
                else:
                    # Global: use ChatHistoryManager
                    if not self.chat_history_manager:
                        return ''
                    summaries = self.chat_history_manager.list_conversations()
                    for rec in summaries:
                        data = self.chat_history_manager.load_conversation(rec.get('session_id','')) or {}
                        consider_conv(data, data.get('chat_history') or [])
            except Exception:
                pass

            # Rank candidates by score desc then recency
            candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
            chosen = candidates[:top_k]
            buf = []
            total = 0
            for idx, (_score, _when, snip) in enumerate(chosen, 1):
                part = f"[Context {idx}]\n{snip}".strip()
                if total + len(part) + 2 > max_chars:
                    break
                buf.append(part)
                total += len(part) + 2
            return "\n\n".join(buf)
        except Exception:
            return ''

    def _retrieve_rag_l2_vcm(self, query: str, max_chars: int, top_k: int, scope: Optional[str] = None) -> tuple:
        """Level 2 RAG: VCM observable scoring (no model output needed).

        Uses two-tier knowledge architecture:
        - Tier 1: Personal Training Grounds (per-variant memories)
        - Tier 2: System Knowledge Bank (shared topic banks)
        - Project: Project-specific knowledge bank

        Returns:
            tuple: (rag_context_string, debug_info_list, top1_score)
        """
        from Data import config
        from Data.knowledge_bank_manager import KnowledgeBankManager
        import json
        from pathlib import Path

        try:
            kb = KnowledgeBankManager()

            # Get current variant ID for Tier 1 access
            variant_id = getattr(self, 'current_model', 'unknown')
            # Normalize variant ID (e.g., "Qwen2.5-0.5b_coder")
            if hasattr(self, 'current_type'):
                variant_id = f"{variant_id}_{self.current_type}"
            # Sanitize variant_id for filesystem safety (remove /, :, etc.)
            variant_id = config.sanitize_identifier(variant_id)

            # Get current project for locality scoring
            current_project = scope if scope else getattr(self, 'current_project', None)

            # Collect session files from appropriate tiers
            session_files = []

            # Tier 1: Personal Training Grounds (always include)
            session_files.extend(kb.get_personal_memories(variant_id))

            # Project: Project-specific knowledge (if in project scope)
            if current_project:
                session_files.extend(kb.get_project_memories(current_project))

            # Tier 2: System Knowledge Bank (extract topics from query, retrieve relevant)
            # Simple topic extraction from query
            query_lower = query.lower()
            query_topics = set()
            topic_keywords = {
                'auth': 'authentication', 'oauth': 'authentication', 'jwt': 'authentication',
                'async': 'async-programming', 'await': 'async-programming',
                'bug': 'debugging', 'error': 'debugging', 'debug': 'debugging',
                'test': 'testing', 'pytest': 'testing',
                'api': 'api-development', 'rest': 'api-development',
                'database': 'database', 'sql': 'database',
                'python': 'python', 'javascript': 'javascript'
            }
            for keyword, topic in topic_keywords.items():
                if keyword in query_lower:
                    query_topics.add(topic)

            # Add general topic if no specific topics found
            if not query_topics:
                query_topics.add('general')

            # Retrieve from Tier 2 topic banks
            for topic in query_topics:
                session_files.extend(kb.get_system_memories_by_topic(topic))

            # Deduplicate session files by session_id
            seen_ids = set()
            unique_files = []
            for sf in session_files:
                if sf.stem not in seen_ids:
                    unique_files.append(sf)
                    seen_ids.add(sf.stem)

            # Collect all RAG-enabled sessions with VCM scores
            candidates = []
            for session_file in unique_files:
                try:
                    with open(session_file, 'r', encoding='utf-8') as f:
                        session_data = json.load(f)

                    # Check if RAG enabled (should always be true for knowledge bank sessions)
                    if not session_data.get('metadata', {}).get('rag_enabled', False):
                        continue

                    # Compute VCM components
                    vcm_scores = config.compute_vcm_components(query, session_data, current_project)
                    unified_score = vcm_scores['unified_score']

                    # Apply tier-based boosting (from Section 0.7.10)
                    tier_boost = 1.0
                    if 'training_grounds' in str(session_file):
                        tier_boost = 1.25  # Tier 1: Personal (1.25×)
                    elif 'knowledge_bank' in str(session_file) and current_project:
                        tier_boost = 1.3   # Project: Highest priority (1.3×)
                    # Tier 2 (System): No boost (1.0×)

                    unified_score *= tier_boost

                    # Get session summary for snippet
                    messages = session_data.get('chat_history', [])
                    summary = '\n'.join(
                        f"{msg.get('role', 'unknown')}: {msg.get('content', '')[:300]}"
                        for msg in messages[-5:]  # Last 5 messages
                        if isinstance(msg, dict)
                    )

                    candidates.append({
                        'session_id': session_data.get('session_id', session_file.stem),
                        'score': unified_score,
                        'vcm_scores': vcm_scores,
                        'summary': summary,
                        'tier_boost': tier_boost
                    })
                except Exception:
                    continue

            if not candidates:
                return ('', [], None)

            # Sort by VCM unified score (descending)
            candidates.sort(key=lambda x: x['score'], reverse=True)
            top_candidates = candidates[:top_k]

            # Build context string
            buf = []
            dbg = []
            total = 0
            top1_score = top_candidates[0]['score'] if top_candidates else None

            for rank, cand in enumerate(top_candidates, 1):
                snippet = cand['summary'][:600]  # Max 600 chars per snippet
                part = (
                    f"[Context {rank}] (session={cand['session_id']}, "
                    f"VCM={cand['score']:.3f}, R={cand['vcm_scores']['R']}, "
                    f"F={cand['vcm_scores']['F']})\n{snippet}"
                )

                if total + len(part) + 2 > max_chars:
                    break

                buf.append(part)
                total += len(part) + 2

                # Debug info with tier information
                tier_str = "T2"  # Default: Tier 2 (System)
                if cand.get('tier_boost', 1.0) == 1.3:
                    tier_str = "Proj"
                elif cand.get('tier_boost', 1.0) == 1.25:
                    tier_str = "T1"

                dbg.append(
                    f"{rank}. [{tier_str}] {cand['session_id']} VCM={cand['score']:.3f} "
                    f"[R:{cand['vcm_scores']['R']} E:{cand['vcm_scores']['E']} "
                    f"F:{cand['vcm_scores']['F']} P:{cand['vcm_scores']['P']}]"
                )

            rag_context = "\n\n".join(buf)
            return (rag_context, dbg, top1_score)

        except Exception as e:
            log_message(f"CHAT_INTERFACE: L2 VCM retrieval failed: {e}")
            return ('', [], None)

    def _retrieve_rag_l3_vcm_auto(self, query: str, max_chars: int, top_k: int, scope: Optional[str] = None) -> tuple:
        """Level 3 RAG: Multi-topic VCM with automatic categorization.

        Falls back to L2 if model doesn't support RAG-MET or topic classification fails.

        Returns:
            tuple: (rag_context_string, debug_info_list, top1_score)
        """
        try:
            # TODO: Implement topic classification and multi-topic retrieval
            # For now, fallback to L2
            log_message("CHAT_INTERFACE: L3 not fully implemented, falling back to L2")
            return self._retrieve_rag_l2_vcm(query, max_chars, top_k, scope)
        except Exception as e:
            log_message(f"CHAT_INTERFACE: L3 retrieval failed, falling back to L2: {e}")
            return self._retrieve_rag_l2_vcm(query, max_chars, top_k, scope)

    def _save_backend_setting(self, key: str, value):
        """Persist a backend setting into custom_code_settings.json."""
        try:
            settings_file = Path(__file__).parent.parent / "custom_code_settings.json"
            data = {}
            if settings_file.exists():
                try:
                    with open(settings_file, 'r') as f:
                        data = json.load(f) or {}
                except Exception:
                    data = {}
            data[key] = value
            with open(settings_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Failed to save backend setting {key}: {e}")

    def _migrate_rag_state(self):
        """Migrate old panel_rag_level to new rag_scoring_method + scope schema."""
        try:
            # Check if old state exists
            old_level = self.backend_settings.get('panel_rag_level_chat', None)
            if old_level is None:
                return  # No migration needed

            # Check if already migrated
            if self.backend_settings.get('rag_scoring_method', None):
                return  # Already migrated

            # Map old level to new state
            old_level = int(old_level)
            if old_level == 0:
                # OFF state - no method selected
                self.rag_scoring_method = 'standard'
                self._save_backend_setting('rag_scoring_method', 'standard')
                self._save_backend_setting('rag_scope_personal', False)
                self._save_backend_setting('rag_scope_topics', False)
            elif old_level == 1:
                # L1: Standard + Personal
                self.rag_scoring_method = 'standard'
                self._save_backend_setting('rag_scoring_method', 'standard')
                self._save_backend_setting('rag_scope_personal', True)
                self._save_backend_setting('rag_scope_topics', False)
            elif old_level == 2:
                # L2: VCM + Personal
                self.rag_scoring_method = 'vcm'
                self._save_backend_setting('rag_scoring_method', 'vcm')
                self._save_backend_setting('rag_scope_personal', True)
                self._save_backend_setting('rag_scope_topics', False)
            elif old_level >= 3:
                # L3: Auto + Personal + Topics
                self.rag_scoring_method = 'auto'
                self._save_backend_setting('rag_scoring_method', 'auto')
                self._save_backend_setting('rag_scope_personal', True)
                self._save_backend_setting('rag_scope_topics', True)

            # Delete old key
            try:
                del self.backend_settings['panel_rag_level_chat']
                self._save_backend_setting('panel_rag_level_chat', None)
            except Exception:
                pass

            log_message(f"CHAT_INTERFACE: Migrated old RAG level {old_level} to new schema")

        except Exception as e:
            log_message(f"CHAT_INTERFACE: Failed to migrate RAG state: {e}")

    def _check_vector_health(self):
        """Check vector backend health and update UI indicators."""
        if not self._vector_backend_available:
            return

        try:
            health = self.rag_service.get_vector_health()
            if health is None:
                self._update_vector_health_status("unavailable", "Vector backend not initialized")
                return

            if health["overall_ok"]:
                self._update_vector_health_status("ok", "Vector services operational")
            else:
                errors = "; ".join(health.get("errors", []))[:100]
                self._update_vector_health_status("error", f"Vector health issues: {errors}")

                # Auto-disable if health check fails
                if hasattr(self, '_rag_cb_vector') and self._rag_scope_vector.get():
                    self._rag_scope_vector.set(False)
                    self._save_backend_setting('rag_scope_vector', False)
                    self.rag_service.enable_vector_search(False)
                    log_message(f"CHAT_INTERFACE: Auto-disabled vector search due to health check failure")
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Vector health check failed: {e}")
            self._update_vector_health_status("error", f"Health check error: {e}")

    def _update_vector_health_status(self, status: str, message: str):
        """Update vector health status label."""
        if not hasattr(self, '_vector_health_label'):
            return

        try:
            if status == "ok":
                self._vector_health_label.config(text="✓", foreground="green")
            elif status == "error":
                self._vector_health_label.config(text="✗", foreground="red")
            elif status == "unavailable":
                self._vector_health_label.config(text="○", foreground="gray")

            # Store full message for tooltip/hover
            if hasattr(self, '_vector_health_label'):
                # Create a tooltip binding
                def show_tooltip(event):
                    try:
                        import tkinter.messagebox as mb
                        mb.showinfo("Vector Health Status", message)
                    except Exception:
                        pass

                # Bind click event to show full message
                self._vector_health_label.bind("<Button-1>", show_tooltip)
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Failed to update vector health label: {e}")

    def _update_rag_scope_availability(self):
        """Enable/disable Project checkbox based on current project context."""
        try:
            # Check if we're in a project context
            has_project = bool(getattr(self, 'current_project', None))

            # Enable/disable Project checkbox
            if hasattr(self, '_rag_cb_project'):
                if has_project:
                    self._rag_cb_project.configure(state=tk.NORMAL)
                else:
                    self._rag_cb_project.configure(state=tk.DISABLED)
                    # Uncheck if disabled
                    self._rag_scope_project.set(False)
                    self._save_backend_setting('rag_scope_project', False)

            # Check vector health before enabling
            if hasattr(self, '_rag_cb_vector'):
                if self._vector_backend_available:
                    # Run health check
                    self._check_vector_health()

                    # Only enable if health is OK
                    health = self.rag_service.get_vector_health()
                    if health and health.get("overall_ok"):
                        self._rag_cb_vector.configure(state=tk.NORMAL)
                    else:
                        self._rag_cb_vector.configure(state=tk.DISABLED)
                        if self._rag_scope_vector.get():
                            self._rag_scope_vector.set(False)
                            self._save_backend_setting('rag_scope_vector', False)
                        self.rag_service.enable_vector_search(False)
                else:
                    self._rag_cb_vector.configure(state=tk.DISABLED)
                    if self._rag_scope_vector.get():
                        self._rag_scope_vector.set(False)
                        self._save_backend_setting('rag_scope_vector', False)
                    self.rag_service.enable_vector_search(False)
                    self._update_vector_health_status("unavailable", "Vector backend not configured")
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Failed to update RAG scope availability: {e}")

    def _log_rag_training_example(self, query: str):
        """Append a JSONL record with RAG retrieval details to training dataset when Training Mode is ON."""
        try:
            lvl = int(getattr(self, 'panel_rag_level', 0) or 0)
            if lvl <= 0 and getattr(self, 'rag_enabled', False):
                lvl = 1
            scope = None
            try:
                scope = self._rag_query_scope()
            except Exception:
                scope = None
            # Ensure index is ready
            try:
                if scope:
                    self.rag_service.refresh_index_project(scope)
                else:
                    self.rag_service.refresh_index_global()
            except Exception:
                pass
            # Use a fixed top_k for logging, independent of injection caps
            vector_enabled = self._vector_scope_active()
            self.rag_service.enable_vector_search(vector_enabled)
            results = self.rag_service.query(query, top_k=6, scope=scope)
            rec = {
                'timestamp': datetime.now().isoformat(),
                'session_id': getattr(self, 'current_session_id', ''),
                'model_name': getattr(self, 'current_model', ''),
                'project': getattr(self, 'current_project', None),
                'rag_level': lvl,
                'scope': (scope or 'global'),
                'query': query,
                'results': [
                    {
                        'session_id': doc.session_id,
                        'role': doc.role,
                        'index': doc.index,
                        'score': float(score),
                        'preview': (doc.text or '')[:240]
                    } for (doc, score) in results
                ]
            }
            out_dir = Path('Training_Data-Sets') / 'Tools'
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / 'rag_retrievals.jsonl'
            with open(out_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(rec) + '\n')
        except Exception:
            pass

    # --- Unified System Prompt / Tool Schema manager --------------------
    def open_prompt_schema_manager(self):
        """Open a combined manager with tabs for System Prompt and Tool Schema."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Prompt / Tool Schema Manager")
        dialog.geometry("1000x720")
        dialog.configure(bg='#2b2b2b')
        try:
            dialog.transient(self.root)
            dialog.lift(); dialog.attributes('-topmost', True); self.root.after(400, lambda: dialog.attributes('-topmost', False))
        except Exception:
            pass

        # Top toggle buttons
        header = ttk.Frame(dialog)
        header.pack(fill=tk.X, padx=10, pady=(10, 0))
        body = ttk.Frame(dialog)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Track which view is active
        active = {'tab': 'prompt'}

        def show_prompt():
            active['tab'] = 'prompt'
            for w in body.winfo_children():
                w.destroy()
            try:
                self._build_prompt_manager_ui(body, dialog)
            except Exception:
                pass
            try:
                btn_prompt.configure(style='Action.TButton')
                btn_schema.configure(style='Select.TButton')
            except Exception:
                pass

        def show_schema():
            active['tab'] = 'schema'
            for w in body.winfo_children():
                w.destroy()
            try:
                self._build_schema_manager_ui(body, dialog)
            except Exception:
                pass
            try:
                btn_prompt.configure(style='Select.TButton')
                btn_schema.configure(style='Action.TButton')
            except Exception:
                pass

        def show_type_schema():
            active['tab'] = 'type_schema'
            for w in body.winfo_children():
                w.destroy()
            try:
                self._build_type_schema_manager_ui(body, dialog)
            except Exception:
                pass
            try:
                btn_prompt.configure(style='Select.TButton')
                btn_schema.configure(style='Select.TButton')
                btn_type_schema.configure(style='Action.TButton')
            except Exception:
                pass

        btn_prompt = ttk.Button(header, text='System Prompt', style='Action.TButton', command=show_prompt)
        btn_schema = ttk.Button(header, text='Tool Schema', style='Select.TButton', command=show_schema)
        btn_type_schema = ttk.Button(header, text='Type Schema', style='Select.TButton', command=show_type_schema)
        btn_prompt.pack(side=tk.LEFT, padx=(0,6))
        btn_schema.pack(side=tk.LEFT, padx=(0,6))
        btn_type_schema.pack(side=tk.LEFT)

        # Default to prompt view
        show_prompt()

    def _build_prompt_manager_ui(self, parent, dialog):
        """Build the System Prompt manager UI into parent frame."""
        parent.columnconfigure(0, weight=0)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)

        # Left list
        left = ttk.Frame(parent, style='Category.TFrame')
        left.grid(row=0, column=0, sticky=tk.NSEW, padx=(0,6))
        ttk.Label(left, text='Available Prompts', font=("Arial", 12, 'bold'), style='CategoryPanel.TLabel').pack(anchor=tk.W, pady=(0,6))
        lf = ttk.Frame(left)
        lf.pack(fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(lf)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        lst = tk.Listbox(lf, yscrollcommand=sb.set, bg='#1e1e1e', fg='#ffffff', selectbackground='#61dafb', width=26)
        lst.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=lst.yview)
        try:
            import config as C
            prompts = list(C.list_system_prompts())
        except Exception:
            prompts = sorted([f.stem for f in self.system_prompts_dir.glob('*.txt')])
        for i, name in enumerate(prompts):
            lst.insert(tk.END, name)
            if name == (self.current_system_prompt or 'default'):
                lst.selection_set(i)

        # Right editor
        right = ttk.Frame(parent, style='Category.TFrame')
        right.grid(row=0, column=1, sticky=tk.NSEW)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        title = ttk.Label(right, text='Select a prompt to view/edit', font=("Arial", 12, 'bold'), style='CategoryPanel.TLabel')
        title.grid(row=0, column=0, sticky=tk.W, pady=(0,6))
        ed = scrolledtext.ScrolledText(right, wrap=tk.WORD, font=("Courier", 10), bg='#1e1e1e', fg='#ffffff', insertbackground='#61dafb')
        ed.grid(row=1, column=0, sticky=tk.NSEW)

        current = {'name': None, 'modified': False}

        def load_selected(_e=None):
            if not lst.curselection():
                return
            name = lst.get(lst.curselection()[0])
            current['name'] = name
            try:
                import config as C
                data = C.load_system_prompt(name)
                # Accept either {'prompt': '...'} or raw string-like
                if isinstance(data, dict) and 'prompt' in data:
                    content = str(data.get('prompt') or '')
                else:
                    content = str(data)
            except Exception:
                try:
                    content = (self.system_prompts_dir / f"{name}.txt").read_text()
                except Exception:
                    content = ''
            ed.delete(1.0, tk.END)
            ed.insert(tk.END, content)
            current['modified'] = False
            title.config(text=f"Editing: {name}")

        def on_modified(_e=None):
            current['modified'] = True

        ed.bind('<<Modified>>', on_modified)
        load_selected()
        lst.bind('<<ListboxSelect>>', load_selected)

        # Bottom buttons
        btns = ttk.Frame(parent)
        btns.grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=(6,0))
        for i in range(4):
            btns.columnconfigure(i, weight=1)

        # Helpers to resolve central file locations for prompts
        def _resolve_prompt_path(name: str):
            try:
                import config as C
                from pathlib import Path as _P
                # 1) Semantic_States JSON
                sp = C.SEMANTIC_DATA_DIR / f"system_prompt_{name}.json"
                if sp.exists():
                    return sp
                # 2) Prompts JSON (any nested)
                for p in C.PROMPTS_DIR.rglob('*.json'):
                    if p.stem == name:
                        return p
                # 3) PromptBox TXT
                pb = C.PROMPTBOX_DIR / f"{name}.txt"
                if pb.exists():
                    return pb
                # Default create path: PromptBox txt
                pb.parent.mkdir(parents=True, exist_ok=True)
                return pb
            except Exception:
                return self.system_prompts_dir / f"{name}.txt"

        def save_cb():
            name = current.get('name')
            if not name:
                return
            path = _resolve_prompt_path(name)
            try:
                path.write_text(ed.get(1.0, tk.END))
            except Exception:
                # Fallback to local
                (self.system_prompts_dir / f"{name}.txt").write_text(ed.get(1.0, tk.END))
            current['modified'] = False

        def new_cb():
            from tkinter import simpledialog, messagebox
            name = simpledialog.askstring('New Prompt', 'Enter prompt name:')
            if not name:
                return
            p = _resolve_prompt_path(name)
            if p.exists():
                messagebox.showerror('Exists', 'A prompt with that name already exists.')
                return
            p.write_text('')
            lst.insert(tk.END, name)
            lst.selection_clear(0, tk.END)
            lst.selection_set(tk.END)
            load_selected()

        def del_cb():
            from tkinter import messagebox
            name = current.get('name')
            if not name:
                return
            if name == 'default':
                messagebox.showerror('Cannot Delete', 'Cannot delete the default prompt')
                return
            if not messagebox.askyesno('Confirm', f"Delete prompt '{name}'?"):
                return
            try:
                _resolve_prompt_path(name).unlink(missing_ok=True)
            except Exception:
                (self.system_prompts_dir / f"{name}.txt").unlink(missing_ok=True)
            # refresh list
            sel = lst.curselection()
            if sel:
                lst.delete(sel[0])
            current['name'] = None
            ed.delete(1.0, tk.END)
            title.config(text='Select a prompt to view/edit')

        # Off toggle + Set Default button row
        ctl_row = ttk.Frame(parent)
        ctl_row.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(6,0))
        self._pm_off_var = tk.BooleanVar(value=(self.current_system_prompt in (None, '', 'None')))
        ttk.Checkbutton(ctl_row, text='Off (no system prompt)', variable=self._pm_off_var, style='TCheckbutton').pack(side=tk.LEFT)
        def _set_default_prompt():
            val = None if self._pm_off_var.get() else (current.get('name') or (lst.get(lst.curselection()[0]) if lst.curselection() else 'default'))
            try:
                self._save_backend_setting('default_system_prompt', val)
                self.backend_settings['default_system_prompt'] = val
                self.add_message('system', f"Default system prompt set to: {val or 'Off'}")
            except Exception:
                pass
        ttk.Button(ctl_row, text='Set as Default', style='Select.TButton', command=_set_default_prompt).pack(side=tk.RIGHT)

        def apply_cb():
            name = current.get('name')
            # If Off is checked, clear the prompt selection
            if bool(self._pm_off_var.get()):
                self.current_system_prompt = None
                try:
                    self.add_message('system', "✓ System prompt set to Off")
                except Exception:
                    pass
            else:
                if not name and lst.curselection():
                    name = lst.get(lst.curselection()[0])
                if not name:
                    return
                if current.get('modified'):
                    save_cb()
                self.current_system_prompt = name
                try:
                    self.add_message('system', f"✓ Loaded system prompt: {name}")
                except Exception:
                    pass
            try:
                self._update_quick_indicators()
            except Exception:
                pass
            if self.is_mounted:
                self.dismount_model(); self.root.after(500, self.mount_model)

        ttk.Button(btns, text='💾 Save', style='Action.TButton', command=save_cb).grid(row=0, column=0, padx=4, sticky=tk.EW)
        ttk.Button(btns, text='➕ New', style='Action.TButton', command=new_cb).grid(row=0, column=1, padx=4, sticky=tk.EW)
        ttk.Button(btns, text='🗑 Delete', style='Select.TButton', command=del_cb).grid(row=0, column=2, padx=4, sticky=tk.EW)
        ttk.Button(btns, text='✓ Select & Apply', style='Action.TButton', command=apply_cb).grid(row=0, column=3, padx=4, sticky=tk.EW)

    def _build_schema_manager_ui(self, parent, dialog):
        """Build the Tool Schema manager UI into parent frame."""
        parent.columnconfigure(0, weight=0)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)

        left = ttk.Frame(parent, style='Category.TFrame')
        left.grid(row=0, column=0, sticky=tk.NSEW, padx=(0,6))
        ttk.Label(left, text='Available Schemas', font=("Arial", 12, 'bold'), style='CategoryPanel.TLabel').pack(anchor=tk.W, pady=(0,6))
        lf = ttk.Frame(left)
        lf.pack(fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(lf)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        lst = tk.Listbox(lf, yscrollcommand=sb.set, bg='#1e1e1e', fg='#ffffff', selectbackground='#61dafb', width=26)
        lst.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=lst.yview)
        try:
            import config as C
            schemas = list(C.list_tool_schemas())
        except Exception:
            schemas = sorted([f.stem for f in self.tool_schemas_dir.glob('*.json')])
        for i, name in enumerate(schemas):
            lst.insert(tk.END, name)
            if name == (self.current_tool_schema or 'default'):
                lst.selection_set(i)

        right = ttk.Frame(parent, style='Category.TFrame')
        right.grid(row=0, column=1, sticky=tk.NSEW)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        title = ttk.Label(right, text='Select a schema to view/edit', font=("Arial", 12, 'bold'), style='CategoryPanel.TLabel')
        title.grid(row=0, column=0, sticky=tk.W, pady=(0,6))
        ed = scrolledtext.ScrolledText(right, wrap=tk.WORD, font=("Courier", 10), bg='#1e1e1e', fg='#ffffff', insertbackground='#61dafb')
        ed.grid(row=1, column=0, sticky=tk.NSEW)

        current = {'name': None, 'modified': False}

        def load_selected(_e=None):
            if not lst.curselection():
                return
            name = lst.get(lst.curselection()[0])
            current['name'] = name
            try:
                import config as C
                data = C.load_tool_schema(name)
                import json as _json
                content = _json.dumps(data, indent=2)
            except Exception:
                try:
                    content = (self.tool_schemas_dir / f"{name}.json").read_text()
                except Exception:
                    content = '{\n  "enabled_tools": "all"\n}'
            ed.delete(1.0, tk.END)
            ed.insert(tk.END, content)
            current['modified'] = False
            title.config(text=f"Editing: {name}")

        def on_modified(_e=None):
            current['modified'] = True
        ed.bind('<<Modified>>', on_modified)
        load_selected(); lst.bind('<<ListboxSelect>>', load_selected)

        btns = ttk.Frame(parent)
        btns.grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=(6,0))
        for i in range(4):
            btns.columnconfigure(i, weight=1)

        def save_cb():
            name = current.get('name')
            if not name:
                return
            content = ed.get(1.0, tk.END)
            try:
                import config as C
                C.save_tool_schema(name, content)
                current['modified'] = False
            except Exception as e:
                from tkinter import messagebox
                messagebox.showerror("Save Error", f"Failed to save schema: {e}")

        def new_cb():
            from tkinter import simpledialog, messagebox
            name = simpledialog.askstring('New Schema', 'Enter schema name:')
            if not name:
                return
            p = self.tool_schemas_dir / f"{name}.json"
            if p.exists():
                messagebox.showerror('Exists', 'A schema with that name already exists.')
                return
            p.write_text('{\n  "enabled_tools": "all",\n  "description": "Default"\n}')
            lst.insert(tk.END, name)
            lst.selection_clear(0, tk.END)
            lst.selection_set(tk.END)
            load_selected()

        def del_cb():
            from tkinter import messagebox
            name = current.get('name')
            if not name:
                return
            if name == 'default':
                messagebox.showerror('Cannot Delete', 'Cannot delete the default schema')
                return
            if not messagebox.askyesno('Confirm', f"Delete schema '{name}'?"):
                return
            try:
                import config as C
                deleted = C.delete_tool_schema(name)
                if deleted:
                    sel = lst.curselection()
                    if sel:
                        lst.delete(sel[0])
                    current['name'] = None
                else:
                    messagebox.showwarning("Not Found", f"Schema '{name}' not found in any location")
            except Exception as e:
                messagebox.showerror("Delete Error", f"Failed to delete schema: {e}")
            ed.delete(1.0, tk.END); title.config(text='Select a schema to view/edit')

        # Off toggle + Set Default (Quick Actions schema panel)
        ctl_row = ttk.Frame(parent)
        ctl_row.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(6,0))
        self._schema_off_var_qm = tk.BooleanVar(value=(self.current_tool_schema in (None, '', 'None')))
        ttk.Checkbutton(ctl_row, text='Off (no tool schema)', variable=self._schema_off_var_qm, style='TCheckbutton').pack(side=tk.LEFT)
        def _set_default_schema_qm():
            val = None if self._schema_off_var_qm.get() else (current.get('name') or (lst.get(lst.curselection()[0]) if lst.curselection() else 'default'))
            try:
                self._save_backend_setting('default_tool_schema', val)
                self.backend_settings['default_tool_schema'] = val
                self.add_message('system', f"Default tool schema set to: {val or 'Off'}")
            except Exception:
                pass
        ttk.Button(ctl_row, text='Set as Default', style='Select.TButton', command=_set_default_schema_qm).pack(side=tk.RIGHT)

        def apply_cb():
            name = current.get('name')
            # Respect Off toggle
            if bool(self._schema_off_var_qm.get()):
                self.current_tool_schema = None
                try:
                    self.add_message('system', "✓ Tool schema set to Off")
                except Exception:
                    pass
            else:
                if not name and lst.curselection():
                    name = lst.get(lst.curselection()[0])
                if not name:
                    return
                if current.get('modified'):
                    save_cb()
                self.current_tool_schema = name
                try:
                    self.add_message('system', f"✓ Loaded tool schema: {name}")
                except Exception:
                    pass
            try:
                self._update_quick_indicators()
            except Exception:
                pass
            if self.is_mounted:
                self.dismount_model(); self.root.after(500, self.mount_model)

        ttk.Button(btns, text='💾 Save', style='Action.TButton', command=save_cb).grid(row=0, column=0, padx=4, sticky=tk.EW)
        ttk.Button(btns, text='➕ New', style='Action.TButton', command=new_cb).grid(row=0, column=1, padx=4, sticky=tk.EW)
        ttk.Button(btns, text='🗑 Delete', style='Select.TButton', command=del_cb).grid(row=0, column=2, padx=4, sticky=tk.EW)
        ttk.Button(btns, text='✓ Select & Apply', style='Action.TButton', command=apply_cb).grid(row=0, column=3, padx=4, sticky=tk.EW)

    def _build_type_schema_manager_ui(self, parent, dialog):
        """Build the Type Schema manager UI into parent frame."""
        parent.columnconfigure(0, weight=0)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)

        left = ttk.Frame(parent, style='Category.TFrame')
        left.grid(row=0, column=0, sticky=tk.NSEW, padx=(0,6))
        ttk.Label(left, text='Available Type Schemas', font=("Arial", 12, 'bold'), style='CategoryPanel.TLabel').pack(anchor=tk.W, pady=(0,6))

        # Category filter
        cat_frame = ttk.Frame(left, style='Category.TFrame')
        cat_frame.pack(fill=tk.X, pady=(0,6))
        ttk.Label(cat_frame, text='Category:', style='CategoryPanel.TLabel').pack(side=tk.LEFT)
        cat_var = tk.StringVar(value='All')
        cat_combo = ttk.Combobox(cat_frame, textvariable=cat_var, state='readonly', width=15)
        cat_combo.pack(side=tk.LEFT, padx=(6,0))

        lf = ttk.Frame(left)
        lf.pack(fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(lf)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        lst = tk.Listbox(lf, yscrollcommand=sb.set, bg='#1e1e1e', fg='#ffffff', selectbackground='#61dafb', width=26)
        lst.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=lst.yview)

        # Load type schemas grouped by category
        try:
            import config as C
            groups = C.list_type_schemas()  # {category: [name, ...]}
        except Exception:
            groups = {}

        # Populate category combo
        categories = ['All'] + sorted(groups.keys())
        cat_combo['values'] = categories

        # Store all schemas with their categories
        all_schemas = []
        for cat, names in groups.items():
            for name in names:
                all_schemas.append({'category': cat, 'name': name})

        def refresh_list():
            """Refresh list based on selected category."""
            lst.delete(0, tk.END)
            selected_cat = cat_var.get()
            for schema in all_schemas:
                if selected_cat == 'All' or schema['category'] == selected_cat:
                    display_name = f"{schema['name']} ({schema['category']})"
                    lst.insert(tk.END, display_name)
                    # Select current if it matches
                    if self.current_main_model_type_schema == f"{schema['category']}/{schema['name']}":
                        lst.selection_set(tk.END)

        cat_combo.bind('<<ComboboxSelected>>', lambda e: refresh_list())
        refresh_list()

        right = ttk.Frame(parent, style='Category.TFrame')
        right.grid(row=0, column=1, sticky=tk.NSEW)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        title = ttk.Label(right, text='Select a type schema to view', font=("Arial", 12, 'bold'), style='CategoryPanel.TLabel')
        title.grid(row=0, column=0, sticky=tk.W, pady=(0,6))
        ed = scrolledtext.ScrolledText(right, wrap=tk.WORD, font=("Courier", 10), bg='#1e1e1e', fg='#ffffff', insertbackground='#61dafb')
        ed.grid(row=1, column=0, sticky=tk.NSEW)

        current = {'category': None, 'name': None}

        def load_selected(_e=None):
            if not lst.curselection():
                return
            idx = lst.curselection()[0]

            # Find the actual schema from filtered list
            selected_cat = cat_var.get()
            filtered = [s for s in all_schemas if selected_cat == 'All' or s['category'] == selected_cat]
            if idx >= len(filtered):
                return

            schema = filtered[idx]
            current['category'] = schema['category']
            current['name'] = schema['name']

            try:
                import config as C
                import json as _json
                data = C.load_type_schema(schema['name'], category=schema['category'])
                content = _json.dumps(data, indent=2)
            except Exception as e:
                content = f"# Error loading schema: {e}"
            ed.delete(1.0, tk.END)
            ed.insert(tk.END, content)
            title.config(text=f"Viewing: {schema['name']} ({schema['category']})")

        load_selected()
        lst.bind('<<ListboxSelect>>', load_selected)

        btns = ttk.Frame(parent)
        btns.grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=(6,0))
        for i in range(5):
            btns.columnconfigure(i, weight=1)

        def save_type_cb():
            cat = current.get('category')
            name = current.get('name')
            if not cat or not name:
                return
            content = ed.get(1.0, tk.END)
            try:
                import config as C
                C.save_type_schema(name, cat, content)
                current['modified'] = False
            except Exception as e:
                from tkinter import messagebox
                messagebox.showerror("Save Error", f"Failed to save type schema: {e}")

        def new_type_cb():
            from tkinter import simpledialog, messagebox
            cat = cat_combo.get()
            if not cat:
                messagebox.showerror('Category Required', 'Select a category first')
                return
            name = simpledialog.askstring('New Type Schema', 'Enter schema name:')
            if not name:
                return
            try:
                import config as C
                C.create_type_schema_file(name, cat)
                # Refresh the list
                groups = C.list_type_schemas()
                current['category'] = cat
                current['name'] = name
                # Reload the list
                _refresh_list()
                # Load the new schema
                load_selected()
            except FileExistsError:
                messagebox.showerror('Exists', 'A type schema with that name already exists in this category')
            except Exception as e:
                messagebox.showerror('Error', f'Failed to create type schema: {e}')

        def del_type_cb():
            from tkinter import messagebox
            cat = current.get('category')
            name = current.get('name')
            if not cat or not name:
                return
            if not messagebox.askyesno('Confirm', f"Delete type schema '{name}' from category '{cat}'?"):
                return
            try:
                import config as C
                deleted = C.delete_type_schema(name, cat)
                if deleted:
                    # Refresh the list
                    _refresh_list()
                    ed.delete(1.0, tk.END)
                    title.config(text='Select a type schema to view/edit')
                    current['category'] = None
                    current['name'] = None
                else:
                    messagebox.showwarning("Not Found", f"Type schema '{name}' not found in category '{cat}'")
            except Exception as e:
                messagebox.showerror("Delete Error", f"Failed to delete type schema: {e}")

        def _refresh_list():
            """Refresh the type schema list after add/delete operations"""
            try:
                import config as C
                groups = C.list_type_schemas()
                cat = cat_combo.get()
                lst.delete(0, tk.END)
                if cat and cat in groups:
                    for s in groups[cat]:
                        lst.insert(tk.END, s)
            except Exception:
                pass

        # Off toggle + Set Default
        ctl_row = ttk.Frame(parent)
        ctl_row.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(6,0))
        self._type_schema_off_var = tk.BooleanVar(value=(self.current_main_model_type_schema in (None, '', 'None')))
        ttk.Checkbutton(ctl_row, text='Off (no type schema)', variable=self._type_schema_off_var, style='TCheckbutton').pack(side=tk.LEFT)

        def _set_default_type_schema():
            if self._type_schema_off_var.get():
                val = None
            else:
                cat = current.get('category')
                name = current.get('name')
                if cat and name:
                    val = f"{cat}/{name}"
                else:
                    val = None
            try:
                self._save_backend_setting('default_main_model_type_schema', val)
                self.backend_settings['default_main_model_type_schema'] = val
                self.add_message('system', f"Default main model type schema set to: {val or 'Off'}")
            except Exception:
                pass
        ttk.Button(ctl_row, text='Set as Default', style='Select.TButton', command=_set_default_type_schema).pack(side=tk.RIGHT)

        def apply_cb():
            # Respect Off toggle
            if bool(self._type_schema_off_var.get()):
                self.current_main_model_type_schema = None
                try:
                    self.add_message('system', "✓ Main model type schema set to Off")
                except Exception:
                    pass
            else:
                cat = current.get('category')
                name = current.get('name')
                if not cat or not name:
                    return
                schema_id = f"{cat}/{name}"
                self.current_main_model_type_schema = schema_id
                try:
                    self.add_message('system', f"✓ Loaded main model type schema: {name} ({cat})")
                except Exception:
                    pass
            try:
                self._update_quick_indicators()
            except Exception:
                pass
            if self.is_mounted:
                self.dismount_model(); self.root.after(500, self.mount_model)

        ttk.Button(btns, text='Save', style='Select.TButton', command=save_type_cb).grid(row=0, column=0, padx=4, sticky=tk.EW)
        ttk.Button(btns, text='New', style='Select.TButton', command=new_type_cb).grid(row=0, column=1, padx=4, sticky=tk.EW)
        ttk.Button(btns, text='Delete', style='Select.TButton', command=del_type_cb).grid(row=0, column=2, padx=4, sticky=tk.EW)
        ttk.Button(btns, text='✓ Select & Apply', style='Action.TButton', command=apply_cb).grid(row=0, column=3, padx=4, sticky=tk.EW)
        ttk.Button(btns, text='Close', style='Select.TButton', command=dialog.destroy).grid(row=0, column=4, padx=4, sticky=tk.EW)

    def _make_indicator(self, parent, icon_text, tooltip_provider):
        lbl = ttk.Label(parent, text=icon_text, style='CategoryPanel.TLabel')
        lbl.pack(side=tk.LEFT, padx=4)
        def _enter(e):
            # Debounce tooltip to avoid flicker
            try:
                if hasattr(self, '_tooltip_after_id') and self._tooltip_after_id:
                    self.root.after_cancel(self._tooltip_after_id)
            except Exception:
                pass
            self._tooltip_after_id = self.root.after(200, lambda w=e.widget: self._show_tooltip(w, tooltip_provider()))
        def _leave(e):
            # Cancel pending tooltip and hide any visible one
            try:
                if hasattr(self, '_tooltip_after_id') and self._tooltip_after_id:
                    self.root.after_cancel(self._tooltip_after_id)
            except Exception:
                pass
            self._tooltip_after_id = None
            self._hide_tooltip()
        lbl.bind('<Enter>', _enter)
        lbl.bind('<Leave>', _leave)
        return lbl

    def _make_scroll_indicator(self, parent, icon_text, messages):
        if not messages:
            return None

        state = {'index': 0}

        def current_text():
            try:
                return messages[state['index']]
            except Exception:
                return ''

        lbl = self._make_indicator(parent, icon_text, current_text)

        def _cycle(delta):
            if not messages:
                return
            state['index'] = (state['index'] + delta) % len(messages)
            try:
                if hasattr(self, '_tooltip_win') and self._tooltip_win and self._tooltip_win.winfo_exists():
                    self._show_tooltip(lbl, current_text())
            except Exception:
                pass

        def _on_mousewheel(event):
            try:
                if getattr(event, 'num', None) == 4 or getattr(event, 'delta', 0) > 0:
                    _cycle(-1)
                else:
                    _cycle(1)
            except Exception:
                _cycle(1)
            return "break"

        lbl.bind('<MouseWheel>', _on_mousewheel)
        lbl.bind('<Button-4>', _on_mousewheel)
        lbl.bind('<Button-5>', _on_mousewheel)
        return lbl

    def _tool_pipeline_tooltip(self) -> str:
        parts = ["Tools: OpenCode (model-agnostic)"]

        granted_state = self._tools_permission_granted
        if granted_state is None and hasattr(self, 'backend_settings'):
            stored = self.backend_settings.get('tools_permission_granted')
            if stored is not None:
                granted_state = bool(stored)

        if granted_state is True:
            parts.append("Status: enabled")
        elif granted_state is False:
            parts.append("Status: blocked (permission denied)")
        else:
            parts.append("Status: ask on first tool use")

        active = []
        adv = getattr(self, 'advanced_settings', {}) or {}
        if adv.get('format_translation', {}).get('enabled', False):
            active.append('Format Translator')
        if adv.get('json_repair', {}).get('enabled', False):
            active.append('JSON Repair')
        if adv.get('schema_validation', {}).get('enabled', False):
            active.append('Schema Validator')
        if adv.get('tool_orchestrator', {}).get('enabled', False):
            active.append('Tool Orchestrator')
        if adv.get('intelligent_routing', {}).get('enabled', False):
            active.append('Router')
        if adv.get('verification', {}).get('enabled', False):
            active.append('Verification')
        if adv.get('quality_assurance', {}).get('enabled', False):
            active.append('Quality Assurance')

        if active:
            parts.append("Active systems: " + ", ".join(active))
        else:
            parts.append("Active systems: none")

        return "\n".join(parts)

    def _format_tool_scroll_entries(self, title, names, disabled=False):
        entries = []
        suffix = " <Disabled>" if disabled else ""
        count = len(names)
        entries.append(f"{title}: {count}")
        if count == 0:
            entries.append("—")
            return entries

        for i in range(0, count, 3):
            chunk = names[i:i+3]
            row = ", ".join(f"{name}{suffix}" for name in chunk)
            entries.append(row)
        return entries

    def _show_tooltip(self, widget, text):
        try:
            self._hide_tooltip()
            tip = tk.Toplevel(self.root)
            tip.wm_overrideredirect(True)
            # Place tooltip below and to the right to avoid overlapping the source widget
            x = widget.winfo_rootx() + int(widget.winfo_width() * 0.3)
            y = widget.winfo_rooty() + widget.winfo_height() + 8
            tip.wm_geometry(f"+{x}+{y}")
            frm = ttk.Frame(tip, padding=4, relief='solid', borderwidth=1)
            frm.pack()
            ttk.Label(frm, text=text, style='Config.TLabel').pack()
            self._tooltip_win = tip
            self._tooltip_active = True
            try:
                tip.attributes('-topmost', True)
            except Exception:
                pass
        except Exception:
            pass

    def _hide_tooltip(self):
        try:
            if self._tooltip_win and self._tooltip_win.winfo_exists():
                self._tooltip_win.destroy()
        except Exception:
            pass
        self._tooltip_win = None
        self._tooltip_active = False

    def _qa_create_project(self):
        """Create a new project from current chat and switch to Projects panel."""
        from tkinter import simpledialog, messagebox
        try:
            name = simpledialog.askstring('Create Project', 'Enter project name:')
            if not name:
                return
            if not messagebox.askyesno('Create Project', f"Create project '{name}' and save this chat to it?\nYou will be switched to the Projects panel."):
                return
            # Save current chat to project (if any)
            try:
                from ..projects_manager import ensure_project, save_conversation
                ensure_project(name)
                meta = {
                    'mode': getattr(self, 'current_mode', 'smart'),
                    'temperature': self.session_temperature,
                    'system_prompt': getattr(self, 'current_system_prompt', 'default'),
                    'tool_schema': getattr(self, 'current_tool_schema', 'default'),
                    'working_directory': self.tool_executor.get_working_directory() if hasattr(self, 'tool_executor') and self.tool_executor else 'unknown',
                    'rag_enabled': bool(getattr(self, 'rag_enabled', False)),
                }
                if self.chat_history:
                    sid = save_conversation(name, self.current_model or 'unknown', self.chat_history, meta, self.current_session_id)
                else:
                    sid = save_conversation(name, self.current_model or 'unknown', [], meta)
            except Exception as e:
                messagebox.showerror('Project Error', f'Failed to save to project: {e}')
                return
            # Switch to Projects tab and select project
            try:
                nb = getattr(self.parent_tab, 'sub_notebook', None)
                if nb and hasattr(self.parent_tab, 'projects_tab_frame'):
                    nb.select(self.parent_tab.projects_tab_frame)
                pif = getattr(self.parent_tab, 'projects_interface', None)
                if pif:
                    pif.current_project = name
                    pif._refresh_projects_tree()
            except Exception:
                pass
        except Exception:
            pass

    def _qa_update_training_btn(self):
        try:
            from tkinter import ttk as _ttk
            st = _ttk.Style()
            gstyle, rstyle = 'QA.Green.TButton', 'QA.Red.TButton'
            try:
                st.configure(gstyle, foreground='#51cf66')
                st.configure(rstyle, foreground='#ff6b6b')
            except Exception:
                pass
            if hasattr(self, '_qa_train_btn') and self._qa_train_btn:
                self._qa_train_btn.config(style=(gstyle if self.training_mode_enabled else rstyle))
        except Exception:
            pass

    def _qa_toggle_training(self):
        try:
            # Reuse central toggler to ensure backend persist + event emission
            self._toggle_training_mode()
            self._qa_update_training_btn()
            try:
                self._update_quick_indicators()
            except Exception:
                pass
        except Exception:
            pass

    def _qa_show_tools(self):
        try:
            for w in self._qa_body.winfo_children():
                w.destroy()
            try:
                if hasattr(self, '_qa_win') and self._qa_win:
                    self._qa_win.resizable(True, True)
                    self._qa_win.geometry('520x420')
            except Exception:
                pass
            top = ttk.Frame(self._qa_body)
            top.pack(fill=tk.X)
            # Back button
            ttk.Button(top, text='⬅', width=3, style='Select.TButton', command=self._qa_show_main).pack(side=tk.LEFT)
            ttk.Label(top, text='Tools', style='CategoryPanel.TLabel').pack(side=tk.LEFT, padx=6)
            # Scrollable tools list with checkboxes
            wrap = ttk.Frame(self._qa_body)
            wrap.pack(fill=tk.BOTH, expand=True, pady=(6,0))
            wrap.columnconfigure(0, weight=1)
            wrap.rowconfigure(0, weight=1)
            cv = tk.Canvas(wrap, bg='#2b2b2b', highlightthickness=0)
            sb = ttk.Scrollbar(wrap, orient='vertical', command=cv.yview)
            body = ttk.Frame(cv, style='Category.TFrame')
            body.bind('<Configure>', lambda e: cv.configure(scrollregion=cv.bbox('all')))
            win_id = cv.create_window((0,0), window=body, anchor='nw')
            cv.configure(yscrollcommand=sb.set)
            def _sync_width(event):
                try:
                    cv.itemconfigure(win_id, width=cv.winfo_width())
                except Exception:
                    pass
            cv.bind('<Configure>', _sync_width)
            cv.grid(row=0, column=0, sticky=tk.NSEW)
            sb.grid(row=0, column=1, sticky=tk.NS)
            # Mousewheel scrolling on hover
            cv.bind('<Enter>', lambda e: self._qa_bind_wheel(cv))
            cv.bind('<Leave>', lambda e: self._qa_unbind_wheel())
            # Mark subview so focus-out does not auto-hide
            self._qa_view = 'tools'
            # Build tools list from Tools tab state when available; else fallback
            tools = []
            enabled = {}
            try:
                if hasattr(self.parent_tab, 'tools_interface') and self.parent_tab.tools_interface:
                    ti = self.parent_tab.tools_interface
                    for _, mp in getattr(ti, 'AVAILABLE_TOOLS', {}).items():
                        tools.extend(list(mp.keys()))
                    enabled = {k: bool(v.get()) for k, v in (getattr(ti, 'tool_vars', {}) or {}).items()}
            except Exception:
                pass
            if not tools:
                tools = ['file_read','file_write','file_edit','file_search','directory_list','grep_search','bash_execute']
            if not enabled:
                enabled = self.load_enabled_tools() or {}

            # Per-type presets: if a mounted variant has an assigned_type, use lightweight defaults
            try:
                import config as C
                vid = None
                m = str(self.current_model or '')
                # If current_model looks like a variant id, try direct
                if m and ':' not in m and not m.endswith('.gguf'):
                    vid = m
                # Else attempt lineage/tag mapping
                if not vid:
                    try:
                        lid = C.get_lineage_for_tag(m)
                    except Exception:
                        lid = None
                    if lid:
                        for rec in (C.list_model_profiles() or []):
                            try:
                                mp = C.load_model_profile(rec.get('variant_id')) or {}
                            except Exception:
                                mp = {}
                            if mp.get('lineage_id') == lid:
                                vid = rec.get('variant_id'); break
                assigned_type = None
                if vid:
                    try:
                        mp = C.load_model_profile(vid) or {}
                        at = mp.get('assigned_type')
                        assigned_type = at[0] if isinstance(at, list) else at
                    except Exception:
                        assigned_type = None
                # Minimal per-type presets (only apply if no session overrides yet)
                if assigned_type and not getattr(self, 'session_enabled_tools', None):
                    t = assigned_type.lower()
                    presets = {}
                    if t == 'coder':
                        presets = {
                            'file_read': True, 'file_write': True, 'file_edit': True,
                            'file_search': True, 'directory_list': True, 'grep_search': True,
                            'bash_execute': False, 'git_operations': False
                        }
                    elif t == 'researcher':
                        presets = {
                            'file_read': True, 'file_search': True, 'grep_search': True,
                            'directory_list': True, 'web_search': False, 'web_fetch': False,
                        }
                    if presets:
                        # Merge onto current enabled map without removing known entries
                        for k in tools:
                            if k in presets:
                                enabled[k] = presets[k]
            except Exception:
                pass
            self._qa_tool_vars = {}
            for name in tools:
                var = tk.BooleanVar(value=bool(enabled.get(name, True)) if enabled else True)
                self._qa_tool_vars[name] = var
                ttk.Checkbutton(body, text=name, variable=var, style='Category.TCheckbutton').pack(anchor=tk.W)
            # Save row
            def save_tools():
                try:
                    # Build override map
                    session_map = {k: bool(v.get()) for k, v in self._qa_tool_vars.items()}
                    # Determine defaults to compare against
                    defaults = {}
                    try:
                        if hasattr(self.parent_tab, 'tools_interface') and self.parent_tab.tools_interface:
                            ti = self.parent_tab.tools_interface
                            defaults = {k: bool(v.get()) for k, v in (getattr(ti, 'tool_vars', {}) or {}).items()}
                    except Exception:
                        defaults = {}
                    if not defaults:
                        defaults = self.load_enabled_tools() or {}

                    # Compute diffs
                    enabled_now = sorted([k for k, v in session_map.items() if v])
                    disabled_now = sorted([k for k, v in session_map.items() if not v])
                    changed = sorted([k for k, v in session_map.items() if v != bool(defaults.get(k, True))])
                    plus = sorted([k for k in changed if session_map.get(k) is True])
                    minus = sorted([k for k in changed if session_map.get(k) is False])

                    # Persist per-chat override
                    self.session_enabled_tools = session_map
                    self._qa_desc.config(text='Saved tool settings for this chat (overrides defaults)')

                    # Announce summary in chat
                    try:
                        parts = []
                        if plus:
                            parts.append("+" + ", ".join(plus))
                        if minus:
                            parts.append("-" + ", ".join(minus))
                        diff_line = ("; Changes: " + " | ".join(parts)) if parts else "; No changes vs defaults"
                        msg = (
                            "Quick Tools: overrides saved.\n"
                            f"Enabled: {', '.join(enabled_now) or '—'}\n"
                            f"Disabled: {', '.join(disabled_now) or '—'}" + diff_line
                        )
                        self.add_message('system', msg)
                    except Exception:
                        pass
                except Exception as e:
                    try:
                        self._qa_desc.config(text=f"Error saving: {e}")
                    except Exception:
                        pass
            ttk.Button(self._qa_body, text='Save', style='Action.TButton', command=save_tools).pack(pady=6)
        except Exception:
            pass

    # Mousewheel helpers for Quick Actions scrollable views
    def _qa_bind_wheel(self, canvas: tk.Canvas):
        try:
            def _on_wheel(event):
                delta = 0
                try:
                    if event.num == 4 or event.delta > 0:
                        delta = -1
                    elif event.num == 5 or event.delta < 0:
                        delta = 1
                except Exception:
                    delta = 0
                canvas.yview_scroll(delta, 'units')
                return 'break'
            self._qa_wheel_handler = _on_wheel
            # Bind for Windows/Mac and Linux
            self.root.bind_all('<MouseWheel>', _on_wheel)
            self.root.bind_all('<Button-4>', _on_wheel)
            self.root.bind_all('<Button-5>', _on_wheel)
        except Exception:
            pass

    def _qa_unbind_wheel(self):
        try:
            self.root.unbind_all('<MouseWheel>')
            self.root.unbind_all('<Button-4>')
            self.root.unbind_all('<Button-5>')
        except Exception:
            pass

    def _on_mount_success(self):
        """Handle successful model mount"""
        self.is_mounted = True
        # Keep class color on label; mount button goes green
        self._update_mount_button_style(mounted=True)
        self.mount_btn.config(state=tk.DISABLED)
        self.dismount_btn.config(state=tk.NORMAL)
        self.send_btn.config(state=tk.NORMAL)
        self.add_message("system", f"{self.current_model} mounted successfully ✓")
        log_message(f"CHAT_INTERFACE: Model {self.current_model} mounted")
        self._start_core_animation()
        # Refresh indicators to show live server URL/status
        try:
            self._update_quick_indicators()
        except Exception:
            pass
    def _on_mount_error(self, error_msg):
        """Handle model mount error"""
        self.add_message("error", error_msg)
        log_message(f"CHAT_INTERFACE ERROR: {error_msg}")

    def dismount_model(self):
        """Dismount the current model"""
        if not self.current_model:
            return
        # Ensure any in-flight generation is terminated
        try:
            if self.is_generating:
                self.stop_generation()
        except Exception:
            pass

        log_message(f"CHAT_INTERFACE: Dismounting model {self.current_model}...")
        self.is_mounted = False

        # Update UI immediately
        self._update_mount_button_style(mounted=False)
        self.mount_btn.config(state=tk.NORMAL)
        self.dismount_btn.config(state=tk.DISABLED)
        self.send_btn.config(state=tk.DISABLED)

        self.add_message("system", f"{self.current_model} dismounted")
        log_message(f"CHAT_INTERFACE: Model {self.current_model} dismounted")
        self._stop_core_animation()
    def _set_model_label_with_class_color(self, model_tag: str):
        try:
            import config as C
            color = '#bbbbbb'
            vid = None
            model_tag = (model_tag or '').strip()
            try:
                lid = C.get_lineage_for_tag(model_tag)
            except Exception:
                lid = None
            if lid:
                try:
                    for rec in (C.list_model_profiles() or []):
                        if rec.get('lineage_id') == lid:
                            vid = rec.get('variant_id')
                            break
                except Exception:
                    pass
            if not vid:
                # Fallback: try variant id from tag prefix
                base_tag = (model_tag or '').split(':')[0]
                try:
                    for rec in (C.list_model_profiles() or []):
                        if rec.get('variant_id') == base_tag:
                            vid = base_tag
                            break
                except Exception:
                    pass
            if vid:
                try:
                    cls = C.get_variant_class(vid) or 'novice'
                    color = {
                        'novice': '#51cf66', 'skilled': '#61dafb', 'expert': '#9b59b6', 'master': '#ffa94d', 'artifact': '#c92a2a'
                    }.get(str(cls).lower(), '#bbbbbb')
                except Exception:
                    pass
            self.model_label.config(text=model_tag, fg=color)
        except Exception:
            self.model_label.config(text=model_tag, fg='#bbbbbb')

    def _update_mount_button_style(self, mounted: bool):
        try:
            from tkinter import ttk as _ttk
            st = _ttk.Style()
            gstyle = 'MountGreen.TButton'; rstyle = 'MountRed.TButton'
            try:
                st.configure(gstyle, foreground='#00c853')
                st.configure(rstyle, foreground='#ff6b6b')
            except Exception:
                pass
            self.mount_btn.config(style=(gstyle if mounted else rstyle))
        except Exception:
            pass

    def _toggle_training_mode(self):
        try:
            enabled = not bool(self.training_mode_enabled)
            self.set_training_mode(enabled)
            if hasattr(self, 'training_state_label'):
                self.training_state_label.config(text=('On' if enabled else 'Off'))
            # Emit event for Settings/Advanced to reflect the per‑chat toggle (no default persistence here)
            try:
                import json
                payload = json.dumps({"enabled": bool(enabled)})
                self.root.event_generate("<<TrainingModeChanged>>", data=payload, when='tail')
            except Exception:
                pass
            # Also directly sync Settings checkbox if available (fallback)
            try:
                if hasattr(self.parent_tab, 'settings_interface') and self.parent_tab.settings_interface:
                    si = self.parent_tab.settings_interface
                    if hasattr(si, 'training_mode_var'):
                        si.training_mode_var.set(bool(enabled))
                        if hasattr(si, 'update_training_status_label'):
                            si.update_training_status_label()
            except Exception:
                pass
            # Refresh indicators
            try:
                self._qa_update_training_btn()
                self._update_quick_indicators()
            except Exception:
                pass
        except Exception:
            pass

        # Note: Ollama doesn't have a specific "unload" command
        # Models are automatically unloaded after inactivity

    def change_working_directory(self):
        """Open dialog to change working directory for tool execution"""
        from tkinter import filedialog, messagebox

        # Get current working directory
        current_dir = str(Path.cwd())
        if self.tool_executor:
            current_dir = self.tool_executor.get_working_directory()

        # Open directory selection dialog
        new_dir = filedialog.askdirectory(
            title="Select Working Directory for Tool Execution",
            initialdir=current_dir
        )

        if new_dir:
            # Update tool executor
            if self.tool_executor:
                success = self.tool_executor.set_working_directory(new_dir)
                if success:
                    # Update backend settings FOR THE SESSION
                    self.backend_settings['working_directory'] = new_dir
                    log_message(f"CHAT_INTERFACE: Session working directory changed to {new_dir}")
                    self.add_message("system", f"Working directory for this session changed to: {new_dir}")
                    # This change will be persisted with the session history via auto-save.

                    # Refresh tracker if it's open
                    if self.is_tracker_active and self.tracker_window and self.tracker_window.winfo_exists():
                        self.refresh_tracker_display()
                else:
                    log_message(f"CHAT_INTERFACE ERROR: Failed to change working directory to {new_dir}")
                    messagebox.showerror("Directory Error", f"Failed to change working directory:\n{new_dir}\n\nDirectory may not exist or be inaccessible.")
            else:
                log_message("CHAT_INTERFACE ERROR: Tool executor not initialized")
                messagebox.showerror("Error", "Tool executor not initialized")

    def clear_chat(self):
        """Clear chat history and renews the session"""
        # Save the current conversation before clearing, if not empty
        if self.chat_history and self.backend_settings.get('auto_save_history', True) and not getattr(self, '_skip_autosave_once', False):
            self._auto_save_conversation()

        # Reset chat buffers and UI
        self.chat_history = []
        self.current_session_id = None  # New session begins only when user sends a message
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete(1.0, tk.END)
        self.chat_display.config(state=tk.DISABLED)
        # Clear active model and disable mount/send
        self.current_model = None
        self.is_mounted = False
        try:
            self.model_label.config(text="No model selected", fg='#ffffff')
            self.mount_btn.config(state=tk.DISABLED)
            self.dismount_btn.config(state=tk.DISABLED)
            self.send_btn.config(state=tk.DISABLED)
        except Exception:
            pass
        self.add_message("system", "Chat cleared. Select a model to begin a new session.")
        log_message("CHAT_INTERFACE: Chat cleared; model unset and session idle")

        # Reset session temperature
        self.session_temperature = self.backend_settings.get('temperature', 0.8)
        self.session_temperature_var.set(self.session_temperature)
        self.update_session_temp_label(self.session_temperature)

    def new_chat(self):
        """Start a new chat: save current if any, then clear and show summary."""
        from tkinter import messagebox
        # Offer to save QA settings per session if requested
        try:
            self._maybe_prompt_save_qa_settings('New Chat')
        except Exception:
            pass
        had_chat = bool(self.chat_history) and bool(self._chat_dirty)
        model = self.current_model or 'none'
        mode = getattr(self, 'current_mode', 'smart')
        prompt = getattr(self, 'current_system_prompt', 'default')
        schema = getattr(self, 'current_tool_schema', 'default')
        if had_chat and self.backend_settings.get('auto_save_history', True):
            self._auto_save_conversation()
            msg = f"Chat: Saved with model '{model}' and settings [mode={mode}, prompt={prompt}, schema={schema}]\n\nSettings cleared: Starting new chat with default settings."
        else:
            msg = "Settings cleared: Starting new chat with default settings."
        self._skip_autosave_once = True
        try:
            self.clear_chat()
            # Reset per-chat Quick Actions overrides to backend defaults
            self.session_enabled_tools = None
            # Reset schema and system prompt to configured defaults (allow Off)
            try:
                dsp = self.backend_settings.get('default_system_prompt', 'default')
                dts = self.backend_settings.get('default_tool_schema', 'default')
            except Exception:
                dsp, dts = 'default', 'default'
            self.current_system_prompt = dsp if dsp not in (None, 'None', '') else None
            self.current_tool_schema = dts if dts not in (None, 'None', '') else None
            try:
                self._update_quick_indicators()
            except Exception:
                pass
        finally:
            self._skip_autosave_once = False
        try:
            messagebox.showinfo("New Chat", msg)
        except Exception:
            log_message("CHAT_INTERFACE: New Chat — messagebox unavailable; continuing")
        # Apply default Training Mode state for new chats from backend settings
        try:
            default_tm = bool(self.backend_settings.get('training_mode_enabled', False))
            # Only toggle if different from current to avoid duplicate messages
            if bool(self.training_mode_enabled) != default_tm:
                self.set_training_mode(default_tm)
            else:
                # Still refresh Quick Actions styles/indicators if window is open
                try:
                    self._qa_update_training_btn()
                    self._update_quick_indicators()
                except Exception:
                    pass
        except Exception:
            pass

    def delete_current_chat(self):
        """Delete current chat from history if saved; or discard unsaved chat."""
        from tkinter import messagebox
        if not self.chat_history_manager:
            messagebox.showerror("Error", "Chat history manager not initialized")
            return
        sid = self.current_session_id
        if sid:
            if not messagebox.askyesno("Delete Chat", f"Delete current chat from history?\n\nID: {sid}"):
                return
            ok = self.chat_history_manager.delete_conversation(sid)
            if ok:
                messagebox.showinfo("Deleted", "Conversation deleted from history")
                self._skip_autosave_once = True
                try:
                    self.clear_chat()
                finally:
                    self._skip_autosave_once = False
                if hasattr(self.parent_tab, 'refresh_history'):
                    try:
                        self.parent_tab.refresh_history()
                    except Exception:
                        pass
            else:
                messagebox.showerror("Error", "Failed to delete conversation")
        else:
            if not self.chat_history:
                messagebox.showinfo("Delete Chat", "No chat to delete.")
                return
            if messagebox.askyesno("Discard Unsaved Chat", "This chat has not been saved. Discard it?"):
                self._skip_autosave_once = True
                try:
                    self.clear_chat()
                finally:
                    self._skip_autosave_once = False

    def get_mode_parameters(self, mode):
        """Get default parameters for a specific mode"""
        mode_configs = {
            'standard': {
                'Resource Usage': 'Default',
                'Max Context Tokens': '4096',
                'Generation Step': '24 tokens',
                'CPU Threads': 'Default',
                'Token Caps (Reasoning)': '300',
                'Token Caps (Standard)': '200',
                'Token Caps (Structured)': '150',
                'Quality Mode': 'Standard',
                'Description': 'Standard settings for general use, without resource profiles.'
            },
            'fast': {
                'Resource Usage': '25% (conservative)',
                'Max Context Tokens': '3072',
                'Generation Step': '16 tokens',
                'CPU Threads': 'Minimal (1-2)',
                'Token Caps (Reasoning)': '200',
                'Token Caps (Standard)': '120',
                'Token Caps (Structured)': '90',
                'Quality Mode': 'Fast',
                'Description': 'Quick responses, minimal processing'
            },
            'smart': {
                'Resource Usage': '50% (balanced)',
                'Max Context Tokens': '5120',
                'Generation Step': '32 tokens',
                'CPU Threads': 'Half of available',
                'Token Caps (Reasoning)': '450',
                'Token Caps (Standard)': '300',
                'Token Caps (Structured)': '220',
                'Quality Mode': 'Auto/Smart',
                'Description': 'Balanced speed and intelligence'
            },
            'think': {
                'Resource Usage': '75% (aggressive)',
                'Max Context Tokens': '8192',
                'Generation Step': '48 tokens',
                'CPU Threads': 'Most available (n-2)',
                'Token Caps (Reasoning)': '900',
                'Token Caps (Standard)': '600',
                'Token Caps (Structured)': '350',
                'Quality Mode': 'Think (with verification)',
                'Think Time': 'Dynamic (configurable)',
                'Description': 'Deep reasoning, thorough analysis'
            }
        }
        return mode_configs.get(mode, mode_configs['smart'])

    def open_mode_selector(self):
        """Open quick mode selector dialog"""
        from tkinter import messagebox

        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Quick Mode Selection")
        dialog.geometry("450x450")
        dialog.configure(bg='#2b2b2b')

        # Make modal
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (450 // 2)
        y = (dialog.winfo_screenheight() // 2) - (450 // 2)
        dialog.geometry(f"450x450+{x}+{y}")

        # Main content
        content_frame = ttk.Frame(dialog, style='Category.TFrame')
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Back bar and title
        backbar = ttk.Frame(content_frame)
        backbar.pack(fill=tk.X)
        ttk.Button(backbar, text='⬅', width=3, style='Select.TButton', command=dialog.destroy).pack(side=tk.LEFT)
        ttk.Label(backbar, text='⚡ Select Mode', font=("Arial", 14, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT, padx=6)
        ttk.Frame(content_frame, height=8).pack()  # small spacer

        # Load current mode from mode_settings.json (same as mode selector tab)
        mode_settings_file = Path(__file__).parent.parent / "mode_settings.json"
        try:
            with open(mode_settings_file, 'r') as f:
                settings = json.load(f)
            current_mode = settings.get('current_mode', 'smart')
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Failed to load mode settings: {e}")
            current_mode = 'smart'

        # Mode buttons
        modes = [
            ('standard', '🔹 Standard', 'Balanced performance and capability'),
            ('fast', '⚡ Fast', 'Optimized for speed'),
            ('smart', '🧠 Smart', 'Enhanced reasoning and tools'),
            ('think', '💭 Think', 'Maximum capability and depth')
        ]

        selected_mode = tk.StringVar(value=current_mode)

        for mode_id, mode_name, mode_desc in modes:
            mode_frame = ttk.Frame(content_frame, style='Category.TFrame')
            mode_frame.pack(fill=tk.X, pady=5)

            rb = ttk.Radiobutton(
                mode_frame,
                text=mode_name,
                variable=selected_mode,
                value=mode_id,
                style='TRadiobutton'
            )
            rb.pack(anchor=tk.W)

            ttk.Label(
                mode_frame,
                text=mode_desc,
                font=("Arial", 8),
                style='Config.TLabel'
            ).pack(anchor=tk.W, padx=(25, 0))

        # Button frame
        btn_frame = ttk.Frame(content_frame, style='Category.TFrame')
        btn_frame.pack(pady=(20, 0))

        def apply_mode():
            """Apply the selected mode FOR THE CURRENT SESSION"""
            new_mode = selected_mode.get()
            try:
                log_message(f"CHAT_INTERFACE: Session mode changed to {new_mode}")
                self.add_message("system", f"Mode for this session changed to: {new_mode.upper()}")
                
                self.current_mode = new_mode
                self._update_quick_indicators()

                # Get parameters for this mode
                mode_parameters = self.get_mode_parameters(new_mode)

                # Notify Advanced Settings tab about mode change
                if hasattr(self.parent_tab, 'settings_interface'):
                    if hasattr(self.parent_tab.settings_interface, 'on_mode_changed'):
                        self.parent_tab.settings_interface.on_mode_changed(new_mode)
                        log_message(f"CHAT_INTERFACE: Notified Advanced Settings of mode change to {new_mode}")

                # Apply mode to chat interface for the current session
                if hasattr(self, 'set_mode_parameters'):
                    self.set_mode_parameters(new_mode, mode_parameters)

                dialog.destroy()
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to apply session mode: {e}")
                messagebox.showerror("Error", f"Failed to apply mode:\n{str(e)}")

        ok_btn = ttk.Button(
            btn_frame,
            text="✓ OK",
            command=apply_mode,
            style='Action.TButton',
            width=12
        )
        ok_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="✕ Cancel",
            command=dialog.destroy,
            style='Select.TButton',
            width=12
        ).pack(side=tk.LEFT, padx=5)

        # Bind Enter key to apply
        dialog.bind('<Return>', lambda e: apply_mode())
        dialog.bind('<Escape>', lambda e: dialog.destroy())

        # Focus the OK button
        ok_btn.focus_set()

    def redisplay_conversation(self):
        """Redisplay the entire conversation history"""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete(1.0, tk.END)
        self.chat_display.config(state=tk.DISABLED)

        for msg in self.chat_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            self.add_message(role, content)

    def add_message(self, role, content):
        """Add a message to the chat display"""
        self.chat_display.config(state=tk.NORMAL)

        if role == "user":
            prefix = "You: "
            tag = "user"
        elif role == "assistant":
            prefix = f"{self.current_model}: "
            tag = "assistant"
        elif role == "system":
            prefix = "[System] "
            tag = "system"
        elif role == "error":
            prefix = "[Error] "
            tag = "error"
        else:
            prefix = ""
            tag = None

        # Add prefix with tag
        if tag:
            self.chat_display.insert(tk.END, prefix, tag)

        # Add content
        self.chat_display.insert(tk.END, content + "\n\n")

        # Auto-scroll to bottom
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)

    def _add_tool_feedback_ui(self, tool_name, arguments, result, detected_success):
        """
        Add feedback UI for tool execution (Phase 2A - Training Progression)

        Allows users to rate tool execution quality, providing ground truth
        for training data quality and stats updates.
        """
        try:
            # Only show feedback in training mode
            if not self.training_mode_enabled:
                return

            # Generate unique execution ID
            import uuid
            execution_id = f"tool_{uuid.uuid4().hex[:12]}"

            # Store for feedback submission
            if not hasattr(self, '_pending_tool_feedbacks'):
                self._pending_tool_feedbacks = {}

            self._pending_tool_feedbacks[execution_id] = {
                'tool_name': tool_name,
                'arguments': arguments,
                'result': result,
                'detected_success': detected_success,
                'variant_id': self.current_model or "unknown",
                'timestamp': datetime.now().isoformat()
            }

            # Create feedback frame embedded in chat display
            self.chat_display.config(state=tk.NORMAL)

            # Add feedback container frame
            feedback_frame = tk.Frame(self.chat_display, bg="#2B2B2B", relief=tk.RAISED, bd=1)
            self.chat_display.window_create(tk.END, window=feedback_frame)
            self.chat_display.insert(tk.END, "\n")

            # Header with tool name and detected status
            header_frame = tk.Frame(feedback_frame, bg="#2B2B2B")
            header_frame.pack(fill=tk.X, padx=5, pady=2)

            status_icon = "✓" if detected_success else "✗"
            status_color = "#4CAF50" if detected_success else "#F44336"

            header_label = tk.Label(
                header_frame,
                text=f"Rate Tool Execution: {tool_name}  |  System detected: {status_icon}",
                bg="#2B2B2B",
                fg=status_color,
                font=("Segoe UI", 9, "bold")
            )
            header_label.pack(side=tk.LEFT)

            # Feedback buttons frame
            buttons_frame = tk.Frame(feedback_frame, bg="#2B2B2B")
            buttons_frame.pack(fill=tk.X, padx=5, pady=3)

            # Feedback options
            feedback_options = [
                ("👍 Good", "good", "#4CAF50"),
                ("⚠️ Partial", "partial", "#FF9800"),
                ("👎 Bad", "bad", "#F44336")
            ]

            for label_text, feedback_value, color in feedback_options:
                btn = tk.Button(
                    buttons_frame,
                    text=label_text,
                    bg="#3C3C3C",
                    fg=color,
                    font=("Segoe UI", 9),
                    relief=tk.RAISED,
                    bd=1,
                    padx=10,
                    pady=2,
                    command=lambda eid=execution_id, fv=feedback_value, ff=feedback_frame:
                        self._submit_tool_feedback(eid, fv, ff)
                )
                btn.pack(side=tk.LEFT, padx=2)

            # Optional notes field
            notes_frame = tk.Frame(feedback_frame, bg="#2B2B2B")
            notes_frame.pack(fill=tk.X, padx=5, pady=2)

            tk.Label(
                notes_frame,
                text="Notes (optional):",
                bg="#2B2B2B",
                fg="#CCCCCC",
                font=("Segoe UI", 8)
            ).pack(side=tk.LEFT)

            notes_entry = tk.Entry(
                notes_frame,
                bg="#1E1E1E",
                fg="#FFFFFF",
                font=("Consolas", 9),
                width=40
            )
            notes_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

            # Store notes entry reference for submission
            self._pending_tool_feedbacks[execution_id]['notes_entry'] = notes_entry

            self.chat_display.config(state=tk.DISABLED)
            self.chat_display.see(tk.END)

            log_message(f"CHAT_INTERFACE: Tool feedback UI added for {tool_name} (execution_id={execution_id})")

        except Exception as e:
            log_message(f"CHAT_INTERFACE: Failed to add tool feedback UI: {e}")
            # Non-fatal - continue without feedback UI

    def _submit_tool_feedback(self, execution_id, feedback_value, feedback_frame):
        """Submit user feedback for tool execution"""
        try:
            if not hasattr(self, '_pending_tool_feedbacks'):
                return

            feedback_data = self._pending_tool_feedbacks.get(execution_id)
            if not feedback_data:
                return

            # Get notes if available
            notes_entry = feedback_data.get('notes_entry')
            notes = notes_entry.get().strip() if notes_entry else ""

            # Map feedback to quality score
            quality_map = {"good": 1.0, "partial": 0.5, "bad": 0.0}
            quality_score = quality_map.get(feedback_value, 0.5)

            # Check if feedback matches detection
            detected = feedback_data['detected_success']
            user_success = feedback_value in ["good", "partial"]
            feedback_match = detected == user_success

            # Store complete feedback
            complete_feedback = {
                'execution_id': execution_id,
                'tool_name': feedback_data['tool_name'],
                'arguments': feedback_data['arguments'],
                'result': feedback_data['result'],
                'variant_id': feedback_data['variant_id'],
                'timestamp': feedback_data['timestamp'],
                'user_feedback': {
                    'rating': feedback_value,
                    'quality_score': quality_score,
                    'notes': notes,
                    'feedback_time': datetime.now().isoformat()
                },
                'detected_success': detected,
                'feedback_match': feedback_match
            }

            # Log to training data
            try:
                from tool_call_logger import get_tool_logger
                logger = get_tool_logger()
                logger.log_tool_feedback(complete_feedback)
            except Exception as e:
                log_message(f"CHAT_INTERFACE: Failed to log tool feedback: {e}")

            # Update stats and XP (will implement in Phase 2C)
            try:
                import config
                if hasattr(config, 'award_xp_from_tool_feedback'):
                    config.award_xp_from_tool_feedback(
                        feedback_data['variant_id'],
                        feedback_data['tool_name'],
                        quality_score,
                        feedback_match
                    )
            except Exception as e:
                log_message(f"CHAT_INTERFACE: XP/stats not yet implemented: {e}")

            # Remove feedback UI and show confirmation
            try:
                self.chat_display.config(state=tk.NORMAL)
                feedback_frame.destroy()

                # Add confirmation message
                confirm_icon = {"good": "✓", "partial": "~", "bad": "✗"}[feedback_value]
                confirm_color = {"good": "#4CAF50", "partial": "#FF9800", "bad": "#F44336"}[feedback_value]

                self.chat_display.insert(tk.END, f"  {confirm_icon} Feedback recorded", "feedback_confirm")
                self.chat_display.tag_config("feedback_confirm", foreground=confirm_color, font=("Segoe UI", 8, "italic"))
                self.chat_display.insert(tk.END, "\n\n")

                self.chat_display.config(state=tk.DISABLED)
                self.chat_display.see(tk.END)
            except Exception as e:
                log_message(f"CHAT_INTERFACE: Failed to update UI after feedback: {e}")

            # Clean up
            del self._pending_tool_feedbacks[execution_id]

            log_message(f"CHAT_INTERFACE: Tool feedback submitted: {feedback_value} for {feedback_data['tool_name']}")

        except Exception as e:
            log_message(f"CHAT_INTERFACE: Failed to submit tool feedback: {e}")

    def _add_skill_rating_for_response(self, response_content):
        """
        Add skill rating widget for assistant response (Phase 2.9)

        Detects skills in the response and adds an interactive rating panel
        below the response in the chat display.
        """
        if not SKILL_RATING_AVAILABLE:
            return

        if not is_skill_rating_enabled():
            return

        try:
            # Generate unique response ID
            import uuid
            response_id = f"resp_{uuid.uuid4().hex[:12]}"

            # Get last user message for context
            task_context = None
            if self.chat_history and len(self.chat_history) >= 2:
                last_user_msg = next((msg for msg in reversed(self.chat_history[:-1])
                                    if msg.get('role') == 'user'), None)
                if last_user_msg:
                    task_context = last_user_msg.get('content', '')[:200]  # First 200 chars as context

            # Add skill rating UI to chat display
            add_skill_rating_to_chat_display(
                chat_display=self.chat_display,
                variant_id=self.current_model or "unknown",
                response_text=response_content,
                response_id=response_id,
                task_context=task_context
            )

            log_message(f"CHAT_INTERFACE: Skill rating added for response {response_id}")

        except Exception as e:
            log_message(f"CHAT_INTERFACE: Failed to add skill rating: {e}")
            # Non-fatal - continue without rating widget

    def send_message(self):
        """Send message to Ollama model"""
        try:
            log_message("SEND: handler entered")
        except Exception:
            pass
        if not self.current_model:
            self.add_message("error", "Please select a model from the right panel first")
            try:
                log_message("SEND: aborted — no current_model set")
            except Exception:
                pass
            return

        if self.is_generating:
            try:
                log_message("SEND: aborted — already generating")
            except Exception:
                pass
            return

        # Get message text
        message = self.input_text.get(1.0, tk.END).strip()
        try:
            log_message(f"SEND: raw text len={len(message)}")
        except Exception:
            pass
        if not message:
            try:
                log_message("SEND: aborted — empty message")
            except Exception:
                pass
            return

        # Log what we are about to send (truncate for safety)
        try:
            backend_hint = getattr(self, 'current_backend', None) or self._get_chat_backend()
            gguf = getattr(self, 'current_model_path', None)
            log_message(f"SEND: backend={backend_hint} model={self.current_model} gguf={gguf or 'None'} msg='{(message[:200] + ('…' if len(message) > 200 else ''))}'")
        except Exception:
            pass

        # Clear input
        self.input_text.delete(1.0, tk.END)

        # If ThinkTime is set for next input, delay generation non-blockingly
        delay_secs = 0
        try:
            mn = self._think_next_min if isinstance(self._think_next_min, (int, float)) else None
            mx = self._think_next_max if isinstance(self._think_next_max, (int, float)) else None
            if mn is not None and mn < 0:
                mn = 0
            if mx is not None and mx < 0:
                mx = 0
            if mn is not None and mx is not None:
                if mx < mn:
                    mn, mx = mx, mn
                delay_secs = int(random.randint(int(mn), int(mx)))
            elif mn is not None:
                delay_secs = int(mn)
            elif mx is not None:
                delay_secs = int(mx)
        except Exception:
            delay_secs = 0

        if delay_secs and delay_secs > 0:
            try:
                self.add_message('system', f"⏱ Applying ThinkTime: waiting {delay_secs}s before sending…")
            except Exception:
                pass
            # Schedule send after delay, without losing the typed message
            self.send_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.DISABLED)
            self.root.after(delay_secs * 1000, lambda m=message: self._start_generation(m))
        else:
            self._start_generation(message)

        # Clear one-shot ThinkTime
        self._think_next_min = None
        self._think_next_max = None
        try:
            self._update_quick_indicators()
        except Exception:
            pass

    def _start_generation(self, message: str):
        # Add user message to display
        self.add_message("user", message)

        # QUICK DEBUG: log the exact message we're starting generation for
        try:
            log_message(f"CHAT_INTERFACE: _start_generation called — msg_len={len(message or '')} msg_preview='{(message[:200] + ('…' if len(message) > 200 else ''))}'")
        except Exception:
            pass
        _debug_log(f"CHAT_DBG: start_generation instance={id(self)} msg_len={len(message or '')}")

        # Add to history
        self.chat_history.append({"role": "user", "content": message})
        self._chat_dirty = True

        # Track for tool call validation
        self.last_user_message = message

        # Ensure backend matches selected model type (safety) and log routing
        try:
            p = getattr(self, 'current_model_path', None)
            if p and str(p).lower().endswith('.gguf'):
                log_message(f"ROUTE: GGUF active, backend candidate=llama_server path={p}")
            else:
                log_message(f"ROUTE: Using backend={self._get_chat_backend()} model={self.current_model}")
        except Exception:
            pass

        # Disable send button and enable stop button
        self.send_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.is_generating = True
        self._core_pulse_speed = 50
        # Record start timestamp for token-speed metrics
        try:
            self._gen_start_ts = time.time()
        except Exception:
            self._gen_start_ts = None
        # Clear any previous stop request
        try:
            self._stop_event.clear()
        except Exception:
            pass

        # Start compact progress indicator
        try:
            self._show_progress(state="thinking", percentage=10)
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Error showing progress: {e}")

        # Mark that we haven't started the network send yet (watchdog may use this)
        try:
            self._gen_send_started = False
        except Exception:
            pass

        # Generate response in background thread and keep a handle
        self._gen_thread = threading.Thread(
            target=self.generate_response,
            args=(message,),
            daemon=True
        )
        self._gen_thread.start()
        try:
            log_message(f"CHAT_INTERFACE: gen thread started (id={id(self._gen_thread)}) backend={self._get_chat_backend()}")
        except Exception:
            pass

        # Start a one-shot watchdog to mitigate pre-processing hangs; it will attempt a minimal
        # fallback send if the main thread hasn't started network I/O within a grace period.
        try:
            def _watchdog(msg=message):
                try:
                    if not getattr(self, 'is_generating', False):
                        return
                    if bool(getattr(self, '_gen_send_started', False)):
                        return
                    log_message("CHAT_INTERFACE: Watchdog firing — attempting minimal fallback send")
                except Exception:
                    pass
                try:
                    self._fallback_minimal_send(msg)
                except Exception:
                    pass
            try:
                if getattr(self, '_gen_watchdog_timer', None):
                    self._gen_watchdog_timer.cancel()
            except Exception:
                pass
            import threading as _th
            self._gen_watchdog_timer = _th.Timer(3.0, _watchdog)
            self._gen_watchdog_timer.daemon = True
            self._gen_watchdog_timer.start()
        except Exception:
            pass

        # Schedule an early parallel minimal send if primary thread stalls before watchdog fires.
        try:
            token = object()
            self._parallel_min_send_token = token
            self._pending_parallel_min_send = True
            self.root.after(350, lambda m=message, t=token: self._parallel_min_send_check(m, t))
        except Exception as e:
            _debug_log(f"CHAT_DBG: parallel_min_send schedule failed instance={id(self)} err={e}")

    def _orchestrator_allowed(self) -> bool:
        """Expert+ class or Trust priority High allows orchestrator control tools."""
        try:
            from config import load_model_profile
            variant = (self.current_model or '').strip()
            class_level = None
            try:
                mp = load_model_profile(variant) or {}
                class_level = (mp.get('class_level') or '').lower()
            except Exception:
                class_level = None
            allowed_by_class = (class_level in ('expert', 'master')) if class_level else False
            prio = (self.advanced_settings.get('conformer', {}).get('priority', 'medium') if isinstance(self.advanced_settings, dict) else 'medium')
            allowed_by_trust = (str(prio).lower() in ('high','highest'))
            return bool(allowed_by_class or allowed_by_trust)
        except Exception:
            return False

    def open_think_time_dialog(self):
        """Popup to set ThinkTime min/max (seconds) for next input."""
        try:
            dlg = tk.Toplevel(self.root)
            dlg.title('Set Think Time (next input)')
            dlg.resizable(False, False)
            frm = ttk.Frame(dlg, padding=10)
            frm.pack(fill=tk.BOTH, expand=True)
            ttk.Label(frm, text='Min (seconds):', style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=(0,8), pady=4)
            min_var = tk.IntVar(value=int(self._think_next_min or 0))
            ttk.Spinbox(frm, from_=0, to=3600, textvariable=min_var, width=8).grid(row=0, column=1, sticky=tk.W, pady=4)
            ttk.Label(frm, text='Max (seconds):', style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, padx=(0,8), pady=4)
            max_var = tk.IntVar(value=int(self._think_next_max or 0))
            ttk.Spinbox(frm, from_=0, to=7200, textvariable=max_var, width=8).grid(row=1, column=1, sticky=tk.W, pady=4)
            tip = ttk.Label(frm, text='Applies once to the next message. If both set, a random value in [min, max] is used.', style='Config.TLabel')
            tip.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(4,8))
            btns = ttk.Frame(frm)
            btns.grid(row=3, column=0, columnspan=2, sticky=tk.EW)
            btns.columnconfigure(0, weight=1)
            btns.columnconfigure(1, weight=1)
            def _save():
                try:
                    a = int(min_var.get()); b = int(max_var.get())
                except Exception:
                    a, b = 0, 0
                self._think_next_min = max(0, a)
                self._think_next_max = max(0, b)
                try:
                    self.add_message('system', f"ThinkTime set for next input: min={self._think_next_min}s, max={self._think_next_max}s")
                except Exception:
                    pass
                try:
                    self._update_quick_indicators()
                except Exception:
                    pass
                dlg.destroy()
            ttk.Button(btns, text='Save', style='Action.TButton', command=_save).grid(row=0, column=0, padx=4, sticky=tk.EW)
            ttk.Button(btns, text='Cancel', style='Select.TButton', command=dlg.destroy).grid(row=0, column=1, padx=4, sticky=tk.EW)
            try:
                dlg.transient(self.root); dlg.lift(); dlg.attributes('-topmost', True); self.root.after(400, lambda: dlg.attributes('-topmost', False))
            except Exception:
                pass
        except Exception:
            pass

    # --- Training status popups (lightweight) ---------------------------
    def _on_training_started(self, event=None):
        try:
            import json as _json
            data = {}
            if event is not None and getattr(event, 'data', None):
                try:
                    data = _json.loads(event.data)
                except Exception:
                    data = {}
            vid = data.get('variant_id') or ''
            # Create popup
            self._training_popup = tk.Toplevel(self.root)
            self._training_popup.title('Training Progress')
            ttk.Label(self._training_popup, text=f"Variant: {vid or 'unknown'}", style='Config.TLabel').pack(padx=10, pady=(8,2))
            self._training_status_lbl = ttk.Label(self._training_popup, text="Training Status: Running…", style='Config.TLabel')
            self._training_status_lbl.pack(padx=10, pady=(0,8))
            # Progress bar
            self._training_progress = ttk.Progressbar(self._training_popup, mode='determinate', length=280)
            self._training_progress.pack(fill=tk.X, padx=10, pady=(0,8))
            btns = ttk.Frame(self._training_popup); btns.pack(fill=tk.X, padx=8, pady=(0,8))
            ttk.Button(btns, text='View Logs', style='Select.TButton', command=lambda: self.root.event_generate("<<FocusTrainingTab>>", when='tail')).pack(side=tk.LEFT)
            ttk.Button(btns, text='Hide', style='Select.TButton', command=self._training_popup.withdraw).pack(side=tk.RIGHT)
        except Exception:
            pass

    def _on_training_complete(self, event=None):
        try:
            if hasattr(self, '_training_status_lbl') and self._training_status_lbl:
                self._training_status_lbl.config(text='Training Status: Complete')
            if hasattr(self, '_training_progress') and self._training_progress:
                try:
                    self._training_progress['value'] = 100
                except Exception:
                    pass
            # Offer to Export + Re‑Eval (hands-free if enabled)
            import json as _json
            data = {}
            if event is not None and getattr(event, 'data', None):
                try:
                    data = _json.loads(event.data)
                except Exception:
                    data = {}
            vid = data.get('variant_id') or ''
            if self.backend_settings.get('auto_export_reeval_after_training', True):
                payload = _json.dumps({"variant_id": vid})
                self.root.event_generate("<<RequestAutoExportReEval>>", data=payload, when='tail')
        except Exception:
            pass

    def _on_training_progress(self, event=None):
        try:
            if not hasattr(self, '_training_progress') or self._training_progress is None:
                return
            import json as _json
            data = _json.loads(getattr(event, 'data', '{}') or '{}')
            cur = int(data.get('current', 0)); tot = int(data.get('total', 1) or 1)
            pct = max(0, min(100, int(cur * 100 / max(1, tot))))
            self._training_progress['value'] = pct
            if hasattr(self, '_training_status_lbl') and self._training_status_lbl:
                self._training_status_lbl.config(text=f'Training Status: Run {cur} of {tot} ({pct}%)')
        except Exception:
            pass

    def generate_response(self, message):
        """Generate response from the active backend with tool support (runs in background thread)

        Hardening: If any unexpected error occurs during pre-processing (router/RAG/scorers/etc),
        fall back to a minimal payload so the user's input is still sent to the model.
        """
        try:
            log_message(f"CHAT_INTERFACE: Generating response for: {message[:50]}...")
            inst = id(self)
            backend_snapshot = self._get_chat_backend()
            _debug_log(f"CHAT_DBG: generate_enter instance={inst} backend={backend_snapshot} msg_len={len(message or '')}")
            # Decide route backend; LOG ONLY (no logic manipulation here)
            try:
                p = getattr(self, 'current_model_path', None)
                is_gguf = bool(p and str(p).lower().endswith('.gguf')) or str(self.current_model or '').lower().endswith('.gguf')
                log_message(f"ROUTE: generate_response enter gguf={'Y' if is_gguf else 'N'} current_backend={getattr(self,'current_backend',None)} chat_backend={self._get_chat_backend()} model={self.current_model} gguf={p}")
            except Exception:
                pass
            backend = self._get_chat_backend()
            _debug_log(f"CHAT_DBG: generate_backend instance={inst} backend={backend}")
            if (
                backend == 'llama_server'
                and self.show_thoughts
                and not self._llama_server_stream_warned
            ):
                self._llama_server_stream_warned = True
                try:
                    self.root.after(0, lambda: self.add_message(
                        'system',
                        "ℹ️ Llama Server backend currently runs without live token streaming; thoughts preview disabled."
                    ))
                except Exception:
                    pass

            # Apply Intelligent Router (pre-process message)
            if self.router:
                try:
                    routing_result = self.router.route_intent(message)
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Router intent: {routing_result.get('intent', 'unknown')}, " +
                                   f"confidence: {routing_result.get('confidence', 0.0)}")
                    _debug_log(f"CHAT_DBG: router_ok instance={inst} intent={routing_result.get('intent', 'unknown')}")
                except Exception as e:
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Router error: {e}")
                    _debug_log(f"CHAT_DBG: router_err instance={inst} err={e}")
            else:
                _debug_log(f"CHAT_DBG: router_skip instance={inst}")

            # Apply Pre-RAG Optimizer (optimize chat history)
            chat_history_to_use = self.chat_history
            if self.pre_rag_optimizer:
                try:
                    # Combine chat history into single string for optimization
                    history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in self.chat_history])
                    optimized = self.pre_rag_optimizer.optimize_context(history_text)
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Pre-RAG compression ratio: {optimized.get('compression_ratio', 1.0)}")
                    _debug_log(f"CHAT_DBG: pre_rag_ok instance={inst}")
                    # Note: For now we still use original history, full integration would reconstruct from optimized
                except Exception as e:
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Pre-RAG Optimizer error: {e}")
                    _debug_log(f"CHAT_DBG: pre_rag_err instance={inst} err={e}")
            
            # Apply Context Scorer (score context quality)
            if self.context_scorer:
                try:
                    score_result = self.context_scorer.score_context(chat_history_to_use)
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Context score: {score_result.get('final_score', 0.0)}, " +
                                   f"target_met: {score_result.get('target_met', False)}")
                    _debug_log(f"CHAT_DBG: context_ok instance={inst}")
                except Exception as e:
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Context Scorer error: {e}")
                    _debug_log(f"CHAT_DBG: context_err instance={inst} err={e}")
            else:
                _debug_log(f"CHAT_DBG: context_skip instance={inst}")

            # Get enabled tool schemas (filtered by current schema config)
            _debug_log(f"CHAT_DBG: tool_schemas_start instance={inst}")
            tool_schemas = self.get_tool_schemas()
            schema_config = self.get_current_tool_schema_config()
            if schema_config.get("enabled_tools") != "all":
                enabled_list = schema_config.get("enabled_tools", [])
                tool_schemas = [t for t in tool_schemas if t['function']['name'] in enabled_list]
            _debug_log(f"CHAT_DBG: tool_schemas_done instance={inst} count={len(tool_schemas)}")

            # Inject system prompt and optional RAG context at the start of conversation
            system_prompt = self.get_current_system_prompt()
            messages_with_system = []
            if isinstance(system_prompt, str) and system_prompt.strip():
                messages_with_system.append({"role": "system", "content": system_prompt})
            try:
                self._last_rag_context = None
                if self._is_rag_active():
                    _debug_log(f"CHAT_DBG: rag_active instance={inst}")
                    # Get current scoring method
                    method = getattr(self, 'rag_scoring_method', 'standard')

                    # Set retrieval parameters based on method
                    if method == 'auto':
                        top_k, max_chars, per_snip = 6, 3600, 900
                    elif method == 'vcm' or method == 'manual':
                        top_k, max_chars, per_snip = 4, 2400, 800
                    else:  # standard
                        top_k, max_chars, per_snip = 2, 1200, 600

                    # Determine scope (project or global)
                    scope = None
                    try:
                        scope = self._rag_query_scope()
                    except Exception:
                        scope = None

                    # Choose retrieval method based on scoring method
                    rag_ctx = ""
                    dbg = []
                    top1_score = None
                    rag_details: List[Dict[str, Any]] = []
                    rag_truncated = False

                    if method == 'auto':
                        # Auto: VCM-Auto (multi-topic with fallback to L2)
                        rag_ctx, dbg, top1_score = self._retrieve_rag_l3_vcm_auto(message, max_chars, top_k, scope)
                        _debug_log(f"CHAT_DBG: rag_auto instance={inst} ctx_len={len(rag_ctx or '')}")
                    elif method == 'vcm' or method == 'manual':
                        # VCM/Manual: VCM Observable (no model output needed)
                        # Manual uses same retrieval but with custom weights (future: pass weights)
                        rag_ctx, dbg, top1_score = self._retrieve_rag_l2_vcm(message, max_chars, top_k, scope)
                        _debug_log(f"CHAT_DBG: rag_vcm instance={inst} ctx_len={len(rag_ctx or '')}")
                    else:
                        # Standard: Lexical keyword matching (use existing rag_service)
                        try:
                            if scope:
                                self.rag_service.refresh_index_project(scope)
                            else:
                                self.rag_service.refresh_index_global()
                        except Exception:
                            pass

                        vector_enabled = self._vector_scope_active()
                        self.rag_service.enable_vector_search(vector_enabled)
                        results = self.rag_service.query(message, top_k=top_k, scope=scope)
                        if not results:
                            try:
                                log_message(f"RAG_DIAG: no_results method={method} scope={scope} top_k={top_k}")
                                from bug_tracker import get_bug_tracker as _gbt
                                bt = _gbt() if _gbt else None
                                if bt:
                                    bt.capture_log_event(
                                        "RAGNoResults",
                                        f"RAG returned 0 candidates (method={method}, scope={scope}, top_k={top_k})",
                                        file_path=str(Path(__file__)),
                                        line_number=0,
                                        context_excerpt=[json.dumps({'method':method,'scope':scope,'top_k':top_k}, default=str)]
                                    )
                            except Exception:
                                pass

                        # If in Chat (no project scope) and adapters configured, merge adapter project results
                        if not scope and getattr(self, 'rag_project_adapters', []):
                            merged = list(results)
                            for pname in self.rag_project_adapters:
                                try:
                                    self.rag_service.refresh_index_project(pname)
                                    self.rag_service.enable_vector_search(vector_enabled)
                                    merged.extend(self.rag_service.query(message, top_k=top_k, scope=pname))
                                except Exception:
                                    continue
                            # Sort merged by score desc and unique by (session_id, index)
                            uniq = {}
                            for doc, score in merged:
                                key = (doc.session_id, int(getattr(doc, 'index', -1)))
                                if key not in uniq or score > uniq[key][1]:
                                    uniq[key] = (doc, score)
                            results = sorted(uniq.values(), key=lambda x: x[1], reverse=True)[:top_k]

                        # Build context from results (L1 format)
                        buf = []
                        total = 0
                        for rank, (doc, score) in enumerate(results, 1):
                            snip = (doc.text or '')[:per_snip]
                            part = f"[Context {rank}] (session={doc.session_id}, score={score:.3f})\n{snip}"
                            if total + len(part) + 2 > max_chars:
                                rag_truncated = True
                                break
                            buf.append(part)
                            total += len(part) + 2
                            if getattr(self, 'rag_debug_enabled', False):
                                dbg.append(f"{rank}. {doc.session_id} score={score:.3f}")
                            if top1_score is None:
                                top1_score = float(score)
                            try:
                                rag_details.append({
                                    'rank': rank,
                                    'session': getattr(doc, 'session_id', 'unknown'),
                                    'score': float(score),
                                    'chars': len(snip),
                                    'tokens': self._estimate_token_count(snip),
                                })
                            except Exception:
                                pass
                            rag_ctx = "\n\n".join(buf)
                            _debug_log(f"CHAT_DBG: rag_standard instance={inst} ctx_len={len(rag_ctx or '')}")
                    # Optional Pre-RAG optimization on context before injection
                    try:
                        if getattr(self, 'pre_rag_optimizer', None):
                            try:
                                # Prefer comprehensive optimizer if available
                                from opencode.pre_rag_optimizer import ContentType
                                maybe = self.pre_rag_optimizer.optimize_content_comprehensive(
                                    rag_ctx, ContentType.CONVERSATION, target_size=None, optimization_level="balanced"
                                )
                                # Handle coroutine or direct result
                                try:
                                    import asyncio
                                    if asyncio.iscoroutine(maybe):
                                        res = asyncio.get_event_loop().run_until_complete(maybe)
                                    else:
                                        res = maybe
                                    rag_ctx = getattr(res, 'optimized_content', rag_ctx) or rag_ctx
                                except Exception:
                                    pass
                            except Exception:
                                # Fallback: try a simple optimize_context if present
                                try:
                                    rag_ctx = self.pre_rag_optimizer.optimize_context(rag_ctx).get('optimized', rag_ctx)
                                except Exception:
                                    pass
                    except Exception:
                        pass
                    if rag_ctx:
                        messages_with_system.append({
                            "role": "system",
                            "content": f"RAG Context (from enabled chats):\n{rag_ctx}"
                        })
                        if getattr(self, 'rag_debug_enabled', False) and dbg:
                            try:
                                self.add_message('system', "🧠 RAG DEBUG:\n" + "\n".join(dbg))
                            except Exception:
                                pass
                        try:
                            self._last_rag_context = {
                                'method': method,
                                'scope': scope,
                                'snippets': rag_details,
                                'total_chars': len(rag_ctx or ''),
                                'total_tokens': sum(item.get('tokens', 0) for item in rag_details),
                                'truncated': rag_truncated,
                            }
                        except Exception:
                            pass
                    else:
                        # RAG was active but produced no context; surface diagnostics
                        try:
                            log_message(f"RAG_DIAG: empty_context method={method} scope={scope} top_k={top_k} max_chars={max_chars} per_snip={per_snip}")
                            from bug_tracker import get_bug_tracker as _gbt
                            bt = _gbt() if _gbt else None
                            if bt:
                                bt.capture_log_event(
                                    "RAGEmptyContext",
                                    f"RAG produced empty context (method={method}, scope={scope})",
                                    file_path=str(Path(__file__)),
                                    line_number=0,
                                    context_excerpt=[json.dumps({'method':method,'scope':scope,'top_k':top_k,'max_chars':max_chars,'per_snip':per_snip,'dbg':dbg[:6]}, default=str)[:2000]]
                                )
                        except Exception:
                            pass
                    # Update auto-training window with top1 score
                    try:
                        if top1_score is not None:
                            self._rag_recent_scores.append(float(top1_score))
                            if len(self._rag_recent_scores) > max(1, int(self.rag_autotrain_window)):
                                self._rag_recent_scores = self._rag_recent_scores[-int(self.rag_autotrain_window):]
                    except Exception:
                        pass
            except Exception as e:
                log_message(f"CHAT_INTERFACE: RAG context build failed: {e}")
                _debug_log(f"CHAT_DBG: rag_error instance={inst} err={e}")
            messages_with_system += chat_history_to_use
            _debug_log(f"CHAT_DBG: messages_prepared instance={inst} count={len(messages_with_system)}")

            # QUICK DEBUG: log a short preview of the payload we will send to the backend
            try:
                last_user = next((m for m in reversed(messages_with_system) if m.get('role') == 'user'), None)
                last_preview = (last_user.get('content')[:500] + ('…' if last_user and len(last_user.get('content','')) > 500 else '')) if last_user else ''
                log_message(f"CHAT_INTERFACE: Prepared payload preview → model={self.current_model or 'unknown'} msgs={len(messages_with_system)} tools={len(tool_schemas or [])} last_user_snippet='{last_preview}'")
                _debug_log(f"CHAT_DBG: payload_ready instance={inst} msgs={len(messages_with_system)} tools={len(tool_schemas or [])}")
            except Exception:
                pass

            diag = self._ensure_context_within_limit(messages_with_system, tool_schemas)

            if backend == 'llama_server':
                try:
                    log_message(f"CHAT_SEND: llama_server → url={self._llama_server_base_url()} msgs={len(messages_with_system)} tools={'Y' if tool_schemas else 'N'}")
                    try:
                        last_user = next((m for m in reversed(messages_with_system) if m.get('role')=='user'), None)
                        if last_user:
                            txt = (last_user.get('content') or '')
                            log_message(f"CHAT_SEND: user='{(txt[:200] + ('…' if len(txt)>200 else ''))}'")
                    except Exception:
                        pass
                except Exception:
                    pass
                try:
                    self._ensure_llama_prompt_with_cache(bool(tool_schemas), self._messages_have_roles(messages_with_system))
                except Exception:
                    pass
                try:
                    self._gen_send_started = True
                except Exception:
                    pass
                try:
                    self._pending_parallel_min_send = False
                except Exception:
                    pass
                _debug_log(f"CHAT_DBG: llama_send_begin instance={inst} msgs={len(messages_with_system)} tools={len(tool_schemas or [])}")
                ok, response_data, error_msg, stopped = self._llama_server_chat(messages_with_system, tool_schemas)
                if not ok:
                    # Ensure UI is reset in all failure paths
                    if stopped:
                        try:
                            self.root.after(0, self.reset_buttons)
                        except Exception:
                            pass
                        return
                    log_message(f"CHAT_INTERFACE ERROR: {error_msg}")
                    try:
                        self.root.after(0, lambda: self.add_message("error", error_msg))
                        self.root.after(0, self.reset_buttons)
                    except Exception:
                        pass
                    return
                log_message("CHAT_INTERFACE: Received response from Llama Server backend")
                self._process_model_response(response_data, message)
                return
        except Exception as e:
            # Unexpected failure in pre-processing. Attempt a safe fallback send so
            # the user's input still reaches the model. This keeps chat usable even
            # if auxiliary components (agents/RAG/router) malfunction.
            try:
                log_message(f"CHAT_INTERFACE: generate_response pre-processing failed ({e}); attempting minimal fallback send")
            except Exception:
                pass
            _debug_log(f"CHAT_DBG: generate_exception instance={id(self)} err={e}")

            try:
                backend = self._get_chat_backend()
            except Exception:
                backend = 'ollama'

            # Minimal messages payload: just the last user input
            fallback_messages = [{"role": "user", "content": message}]

            try:
                if backend == 'llama_server':
                    try:
                        self._gen_send_started = True
                    except Exception:
                        pass
                    ok, response_data, error_msg, stopped = self._llama_server_chat(fallback_messages, None)
                    if ok:
                        try:
                            self._process_model_response(response_data, message)
                        except Exception:
                            pass
                        return
                    # Surface error and reset
                    try:
                        self.root.after(0, lambda: self.add_message("error", error_msg or 'Llama Server request failed'))
                    except Exception:
                        pass
                else:
                    # Ollama fallback: reuse existing path below by letting function continue
                    # into the Ollama section (payload build + curl). We do this by not returning here.
                    pass
            except Exception:
                # If even fallback fails, reset UI
                try:
                    self.root.after(0, self.reset_buttons)
                except Exception:
                    pass
                _debug_log(f"CHAT_DBG: generate_exception fallback_failed instance={id(self)}")
            return

            # Prepare the chat payload
            payload = {
                "model": self.current_model,
                "messages": messages_with_system,
                "stream": False,
                "options": {
                    "temperature": self.session_temperature
                }
            }

            # NOTE: We do NOT add tools to the payload using Ollama's native API
            # Instead, tool schemas are embedded in the system prompt, and the model
            # learns to output tool calls in text format which are detected by Format Translator
            # This approach works with ANY model, not just those supporting Ollama's tools API
            if tool_schemas:
                log_message(f"CHAT_INTERFACE: {len(tool_schemas)} tool schemas available (embedded in system prompt)")

            # Call Ollama API via HTTP (using curl as subprocess)
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(payload, f)
                payload_file = f.name

            try:
                if self.show_thoughts:
                    # Streaming mode: read JSONL lines and preview partial content
                    import subprocess as sp
                    cmd = [
                        "curl", "-s", "-N", "-X", "POST", "http://localhost:11434/api/chat",
                        "-H", "Content-Type: application/json",
                        "-d", f"@{payload_file}"
                    ]
                    # Force stream=true in runtime by patching payload file (simple replace)
                    try:
                        payload = json.loads(Path(payload_file).read_text())
                        payload["stream"] = True
                        Path(payload_file).write_text(json.dumps(payload))
                    except Exception:
                        pass
                    proc = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE, text=True, bufsize=1)
                    # Track process for Stop button
                    try:
                        if self._proc_lock:
                            with self._proc_lock:
                                self._current_proc = proc
                        else:
                            self._current_proc = proc
                    except Exception:
                        self._current_proc = proc
                    final_text_chunks = []
                    def _append_thought(txt):
                        # If show_thoughts is on and tracker exists, append to it.
                        if self.show_thoughts and self.is_tracker_active and self.tracker_window.winfo_exists():
                            try:
                                self.tracker_thoughts_text.config(state=tk.NORMAL)
                                self.tracker_thoughts_text.insert(tk.END, txt)
                                self.tracker_thoughts_text.see(tk.END)
                                self.tracker_thoughts_text.config(state=tk.DISABLED)
                            except Exception:
                                pass
                        else:
                            try:
                                self.root.after(0, lambda t=txt: self.chat_display.config(state=tk.NORMAL) or self.chat_display.insert(tk.END, t, 'thought') or self.chat_display.see(tk.END) or self.chat_display.config(state=tk.DISABLED))
                            except Exception:
                                pass
                    stopped = False
                    token_count = 0
                    start_time = time.time()

                    for line in proc.stdout:
                        # Allow user requested stop mid-stream
                        try:
                            if self._stop_event.is_set():
                                stopped = True
                                break
                        except Exception:
                            pass
                        line = line.strip()
                        if not line:
                            continue
                        # Each line is JSON for stream event
                        try:
                            obj = json.loads(line)
                            msg = obj.get('message', {})
                            chunk = msg.get('content', '')
                            if chunk:
                                final_text_chunks.append(chunk)
                                _append_thought(chunk)

                                # Update progress bar with token count
                                token_count += len(chunk.split())  # Approximate token count by words
                                elapsed = time.time() - start_time

                                # Update compact progress indicator
                                try:
                                    # Estimate progress: use token speed to estimate completion
                                    # Assume ~150 tokens average response, scale percentage accordingly
                                    estimated_total = 150
                                    percentage = min(95, int((token_count / estimated_total) * 100))

                                    # Calculate token speed
                                    tok_per_sec = int(token_count / elapsed) if elapsed > 0 else 0
                                    speed_str = f"{tok_per_sec} tok/s" if tok_per_sec > 0 else ""

                                    self._update_progress(percentage=percentage, state="generating", speed=speed_str)
                                except Exception:
                                    pass

                            if obj.get('done', False):
                                break
                        except Exception:
                            # Fallback: append raw
                            final_text_chunks.append('')
                    if stopped:
                        try:
                            proc.terminate()
                        except Exception:
                            pass
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        self.root.after(0, lambda: self.add_message('system', '⏹ Generation stopped'))
                        return
                    stdout_full = "".join(final_text_chunks)
                    stderr_full = ''
                    class _Res:
                        returncode = 0
                        stdout = stdout_full
                        stderr = stderr_full
                    result = _Res()
                else:
                    # Non-streaming: use Popen so we can cancel
                    import subprocess as sp
                    cmd = [
                        "curl", "-s", "-X", "POST", "http://localhost:11434/api/chat",
                        "-H", "Content-Type: application/json",
                        "-d", f"@{payload_file}"
                    ]
                    proc = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE, text=True)
                    # Track process for Stop button
                    try:
                        if self._proc_lock:
                            with self._proc_lock:
                                self._current_proc = proc
                        else:
                            self._current_proc = proc
                    except Exception:
                        self._current_proc = proc

                    stopped = False
                    # Wait in small increments to react to stop
                    while True:
                        try:
                            proc.wait(timeout=0.2)
                            break
                        except subprocess.TimeoutExpired:
                            try:
                                if self._stop_event.is_set():
                                    stopped = True
                                    try:
                                        proc.terminate()
                                    except Exception:
                                        pass
                                    try:
                                        proc.kill()
                                    except Exception:
                                        pass
                                    break
                            except Exception:
                                pass
                    if stopped:
                        self.root.after(0, lambda: self.add_message('system', '⏹ Generation stopped'))
                        return
                    # Collect outputs
                    try:
                        _stdout, _stderr = proc.communicate(timeout=2)
                    except Exception:
                        _stdout, _stderr = proc.communicate()
                    class _Res:
                        returncode = proc.returncode
                        stdout = _stdout
                        stderr = _stderr
                    result = _Res()
            except subprocess.TimeoutExpired:
                error_msg = "Request timed out after 120 seconds"
                log_message(f"CHAT_INTERFACE ERROR: {error_msg}")
                self.root.after(0, lambda: self.add_message("error", error_msg))
            except Exception as e:
                error_msg = f"Error generating response: {str(e)}"
                log_message(f"CHAT_INTERFACE ERROR: {error_msg}")
                self.root.after(0, lambda: self.add_message("error", error_msg))
            finally:
                Path(payload_file).unlink(missing_ok=True)

            if result.returncode != 0:
                # If user requested stop, prefer a clean stopped message
                try:
                    if self._stop_event.is_set():
                        self.root.after(0, lambda: self.add_message('system', '⏹ Generation stopped'))
                        return
                except Exception:
                    pass
                err = (getattr(result, 'stderr', '') or '').strip()
                error_msg = f"Ollama error: {err or 'unknown error'}"
                log_message(f"CHAT_INTERFACE ERROR: {error_msg}")
                self.root.after(0, lambda: self.add_message("error", error_msg))
            else:
                # Log raw response for debugging
                log_message(f"CHAT_INTERFACE DEBUG: Raw Ollama response (first 1000 chars): {getattr(result,'stdout','')[:1000]}")

                # Parse response (with JSON Fixer if enabled)
                if self.json_fixer_enabled:
                    try:
                        response_data = self.smart_json_parse(getattr(result,'stdout',''))
                        if self.backend_settings.get('enable_debug_logging', False):
                            log_message("DEBUG: JSON Fixer used to parse response")
                    except Exception as e:
                        if self.backend_settings.get('enable_debug_logging', False):
                            log_message(f"DEBUG: JSON Fixer failed, falling back to standard JSON: {e}")
                        response_data = json.loads(getattr(result,'stdout',''))
                else:
                    response_data = json.loads(getattr(result,'stdout',''))

                self._process_model_response(response_data, message)
                return

        
        finally:
            # Token-speed metrics (best-effort)
            try:
                import config as C
                # Compute elapsed
                end_ts = time.time()
                start_ts = getattr(self, '_gen_start_ts', None)
                elapsed_ms = None
                if isinstance(start_ts, (int, float)):
                    elapsed_ms = max(1, int((end_ts - start_ts) * 1000.0))
                else:
                    elapsed_ms = None
                # Estimate tokens
                def _est_tokens(txt: str) -> int:
                    try:
                        return max(1, int(len(txt or '') / 4))
                    except Exception:
                        return 1
                input_tokens = _est_tokens(message)
                # Last assistant message content if present
                resp_txt = ''
                try:
                    if self.chat_history and self.chat_history[-1].get('role') == 'assistant':
                        resp_txt = self.chat_history[-1].get('content') or ''
                except Exception:
                    resp_txt = ''
                output_tokens = _est_tokens(resp_txt)
                # Variant id attribution: use mounted current_model string
                variant_id = (self.current_model or '').strip()
                if variant_id:
                    C.record_token_metrics(variant_id, input_tokens, output_tokens, elapsed_ms)
            except Exception:
                pass
            # Clear tracked process when done
            try:
                if self._proc_lock:
                    with self._proc_lock:
                        self._current_proc = None
                else:
                    self._current_proc = None
            except Exception:
                self._current_proc = None
            # Re-enable send button and disable stop button
            self.root.after(0, self.reset_buttons)

    def reset_buttons(self):
        """Reset button states after generation"""
        self.is_generating = False
        self._core_pulse_speed = 150
        self.stop_btn.config(state=tk.DISABLED)
        # Cancel any pending watchdog timer
        try:
            if getattr(self, '_gen_watchdog_timer', None):
                self._gen_watchdog_timer.cancel()
                self._gen_watchdog_timer = None
        except Exception:
            pass
        try:
            self._pending_parallel_min_send = False
            self._parallel_min_send_token = None
        except Exception:
            pass

        # Hide compact progress indicator
        try:
            self._hide_progress()
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Error hiding progress: {e}")

    def _parallel_min_send_check(self, message: str, token) -> None:
        inst = id(self)
        try:
            if token != getattr(self, '_parallel_min_send_token', None):
                _debug_log(f"CHAT_DBG: parallel_min_send token mismatch instance={inst}")
                return
        except Exception:
            pass
        if not getattr(self, 'is_generating', False):
            _debug_log(f"CHAT_DBG: parallel_min_send abort instance={inst} reason=not_generating")
            return
        if bool(getattr(self, '_gen_send_started', False)):
            _debug_log(f"CHAT_DBG: parallel_min_send abort instance={inst} reason=send_started")
            return
        if not bool(getattr(self, '_pending_parallel_min_send', False)):
            _debug_log(f"CHAT_DBG: parallel_min_send abort instance={inst} reason=flag_cleared")
            return
        _debug_log(f"CHAT_DBG: parallel_min_send firing instance={inst}")
        try:
            self._fallback_minimal_send(message)
        except Exception as e:
            _debug_log(f"CHAT_DBG: parallel_min_send error instance={inst} err={e}")
        finally:
            try:
                self._pending_parallel_min_send = False
            except Exception:
                pass

    def _schedule_server_probe(self, base_url: str, reason: str):
        """Launch a background thread to probe llama_server without blocking UI."""
        inst = id(self)
        if not base_url:
            return
        if not bool(self.backend_settings.get('status_probes_enabled', True)):
            _debug_log(f"CHAT_DBG: probe disabled instance={inst} url={base_url} reason={reason}")
            return
        lock = None
        try:
            lock = getattr(self, '_probe_lock', None)
        except Exception:
            lock = None
        if lock:
            acquired = lock.acquire(False)
            if not acquired:
                _debug_log(f"CHAT_DBG: probe lock busy instance={inst} url={base_url}")
                return
        try:
            if getattr(self, '_probe_job', None) is not None:
                _debug_log(f"CHAT_DBG: probe already running instance={inst} url={base_url}")
                return
            self._probe_job = 'pending'
        finally:
            if lock:
                lock.release()

        def _worker():
            try:
                _debug_log(f"CHAT_DBG: probe start instance={inst} url={base_url} reason={reason}")
                ok, info = self._check_llama_server_connection(base_url)
                status = {
                    'online': bool(ok),
                    'info': info,
                    'ts': time.time(),
                }
            except Exception as e:
                status = {
                    'online': False,
                    'info': str(e),
                    'ts': time.time(),
                }
            _SERVER_STATUS_CACHE[base_url] = status
            try:
                self._server_online_cached = status['online']
                self._server_online_ts = status['ts']
            except Exception:
                pass
            _debug_log(f"CHAT_DBG: probe complete instance={inst} url={base_url} status={status}")
            try:
                # Check if root exists and is in main loop before scheduling UI update
                if hasattr(self, 'root') and self.root:
                    try:
                        # Check if root window still exists and is valid
                        if not self.root.winfo_exists():
                            _debug_log(f"CHAT_DBG: probe skip UI update instance={inst} root destroyed")
                            return
                        # Try to schedule UI update on main thread
                        # Suppress "main thread is not in main loop" errors during initialization
                        self.root.after(0, lambda: self._update_quick_indicators(reason="probe_refresh"))
                    except RuntimeError as re:
                        # Root not in main loop yet - this is expected during initialization
                        error_msg = str(re).lower()
                        if "main thread is not in main loop" in error_msg:
                            # Expected during initialization - don't log as error
                            pass
                        else:
                            _debug_log(f"CHAT_DBG: probe after RuntimeError instance={inst} err={re}")
                    except Exception as e:
                        error_msg = str(e).lower()
                        if "main thread is not in main loop" in error_msg:
                            # Expected during initialization - don't log as error
                            pass
                        else:
                            _debug_log(f"CHAT_DBG: probe after error instance={inst} err={e}")
                else:
                    _debug_log(f"CHAT_DBG: probe skip UI update instance={inst} root not available")
            except Exception as e:
                error_msg = str(e).lower()
                if "main thread is not in main loop" not in error_msg:
                    _debug_log(f"CHAT_DBG: probe after error instance={inst} err={e}")
            finally:
                try:
                    self._probe_job = None
                except Exception:
                    pass

        try:
            job = threading.Thread(target=_worker, daemon=True)
            self._probe_job = job
            job.start()
        except Exception as e:
            _debug_log(f"CHAT_DBG: probe spawn error instance={inst} err={e}")
            try:
                self._probe_job = None
            except Exception:
                pass

    def _fallback_minimal_send(self, message: str):
        """Attempt a minimal, best-effort send of a single user message to the active backend.

        Used by the watchdog if normal generate_response did not start network I/O in time.
        """
        try:
            backend = self._get_chat_backend()
        except Exception:
            backend = 'llama_server'
        try:
            self._pending_parallel_min_send = False
        except Exception:
            pass
        msgs = [{"role": "user", "content": message}]
        if backend == 'llama_server':
            _debug_log(f"CHAT_DBG: fallback_send llama_server instance={id(self)} msg_len={len(message or '')}")
            try:
                self._gen_send_started = True
            except Exception:
                pass
            ok, response_data, error_msg, stopped = self._llama_server_chat(msgs, None)
            if ok:
                try:
                    self._process_model_response(response_data, message)
                except Exception as e:
                    _debug_log(f"CHAT_DBG: fallback_send process error instance={id(self)} err={e}")
            else:
                try:
                    self.root.after(0, lambda: self.add_message('error', error_msg or 'Llama Server failed'))
                except Exception:
                    pass
        else:
            # Ollama minimal path: reuse non-streaming curl logic quickly
            try:
                _debug_log(f"CHAT_DBG: fallback_send ollama instance={id(self)}")
                import tempfile, json, subprocess as sp
                payload = {"model": self.current_model, "messages": msgs, "stream": False, "options": {"temperature": self.session_temperature}}
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    json.dump(payload, f)
                    payload_file = f.name
                cmd = ["curl","-s","-X","POST","http://localhost:11434/api/chat","-H","Content-Type: application/json","-d", f"@{payload_file}"]
                proc = sp.run(cmd, capture_output=True, text=True, timeout=30)
                if proc.returncode == 0 and proc.stdout.strip():
                    try:
                        data = json.loads(proc.stdout)
                        self._process_model_response(data, message)
                    except Exception as e:
                        _debug_log(f"CHAT_DBG: fallback_send parse error instance={id(self)} err={e}")
            finally:
                try:
                    import os
                    if 'payload_file' in locals() and payload_file and os.path.exists(payload_file):
                        os.unlink(payload_file)
                except Exception as e:
                    _debug_log(f"CHAT_DBG: fallback_send cleanup error instance={id(self)} err={e}")

        try:
            self.root.after(0, self.reset_buttons)
        except Exception as e:
            _debug_log(f"CHAT_DBG: fallback_send reset error instance={id(self)} err={e}")

    def _maybe_trigger_auto_training(self):
        try:
            if not bool(getattr(self, 'training_mode_enabled', False)):
                return
            if not bool(getattr(self, 'rag_autotrain_enabled', False)):
                return
            # Gate by class promotion unless backend override
            if bool(getattr(self, 'rag_autotrain_require_promotion_gate', True)):
                if not (bool(getattr(self, 'class_promotion_earned', False)) or bool(getattr(self, 'rag_autotrain_backend_override', False))):
                    return
            if not self._rag_recent_scores:
                return
            import time, json as _json
            avg = sum(self._rag_recent_scores) / max(1, len(self._rag_recent_scores))
            if avg < float(self.rag_autotrain_threshold):
                return
            # cooldown: 5 minutes
            now = int(time.time())
            if now - int(self._rag_last_trigger_ts) < 300:
                return
            self._rag_last_trigger_ts = now
            payload = _json.dumps({
                'model_name': (self.current_model or ''),
                'avg_rag_score': avg,
                'window': int(self.rag_autotrain_window)
            })
            try:
                self.root.event_generate("<<StartVariantTraining>>", data=payload, when='tail')
                self.add_message('system', f"🤖 Auto-Training Triggered (avg={avg:.3f} over {len(self._rag_recent_scores)}).")
            except Exception:
                pass
        except Exception:
            pass

    def stop_generation(self):
        """Stop ongoing generation by signalling and terminating the subprocess if present."""
        # Signal stop to the background thread
        try:
            self._stop_event.set()
        except Exception:
            pass
        try:
            self._pending_parallel_min_send = False
            self._parallel_min_send_token = None
        except Exception:
            pass
        try:
            if getattr(self, '_gen_watchdog_timer', None):
                self._gen_watchdog_timer.cancel()
                self._gen_watchdog_timer = None
        except Exception:
            pass

        # Try to terminate any active subprocess
        proc = None
        try:
            if self._proc_lock:
                with self._proc_lock:
                    proc = self._current_proc
            else:
                proc = self._current_proc
        except Exception:
            proc = self._current_proc

        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass
            try:
                proc.wait(timeout=1.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        log_message("CHAT_INTERFACE: Stop requested → terminating active generation")
        try:
            self.add_message("system", "⏹ Generation stopped")
        except Exception:
            pass
        try:
            self.reset_buttons()
        except Exception:
            pass

    def _ensure_tools_permission(self) -> bool:
        """Prompt once to allow or deny tool execution when defaults allow all tools."""
        if self._tools_permission_granted is not None:
            return bool(self._tools_permission_granted)

        stored = self.backend_settings.get('tools_permission_granted')
        if stored is not None:
            self._tools_permission_granted = bool(stored)
            return self._tools_permission_granted

        try:
            from tkinter import messagebox
            prompt = (
                "Allow this chat to execute OpenCode tools?\n\n"
                "Tools may read or modify files, search directories, and run shell commands. "
                "Choose 'No' to block tool execution until re-enabled."
            )
            response = messagebox.askyesno("Enable Tool Execution", prompt)
        except Exception:
            response = False

        self._tools_permission_granted = bool(response)
        try:
            self._save_backend_setting('tools_permission_granted', self._tools_permission_granted)
        except Exception:
            pass

        if self._tools_permission_granted:
            log_message("CHAT_INTERFACE: Tool execution permission granted by user.")
        else:
            log_message("CHAT_INTERFACE: Tool execution permission denied by user.")
        return self._tools_permission_granted

    def _execute_via_orchestrator(self, tool_calls, agent_name=None, suppress_ui=False,
                                   log_buffer=None, route_func=None):
        """Execute tool calls via AdvancedToolOrchestrator with risk assessment.

        Args:
            tool_calls: List of OpenAI-style tool call dicts
            agent_name: Optional agent name for routing
            suppress_ui: Whether to suppress UI output
            log_buffer: Optional log buffer
            route_func: Function to route messages

        Returns:
            List of structured results or None if orchestrator declined
        """
        try:
            from opencode.tool_orchestrator import ToolOperation, ToolChain, ToolRiskLevel, ConfirmationGate
            import asyncio
            import uuid

            # Convert tool_calls to ToolOperation format
            operations = []
            for tool_call in tool_calls:
                function_data = tool_call.get("function", {})
                tool_name = function_data.get("name")
                arguments = function_data.get("arguments", {})

                # Map tool names to risk levels (can be configured later)
                risk_mapping = {
                    'file_read': ToolRiskLevel.SAFE,
                    'directory_list': ToolRiskLevel.SAFE,
                    'grep_search': ToolRiskLevel.SAFE,
                    'file_search': ToolRiskLevel.SAFE,
                    'file_write': ToolRiskLevel.MEDIUM,
                    'file_edit': ToolRiskLevel.MEDIUM,
                    'bash_execute': ToolRiskLevel.HIGH,
                    'file_delete': ToolRiskLevel.HIGH,
                    'change_directory': ToolRiskLevel.LOW,
                }
                risk_level = risk_mapping.get(tool_name, ToolRiskLevel.MEDIUM)

                # Map risk to confirmation gate
                gate_mapping = {
                    ToolRiskLevel.SAFE: ConfirmationGate.NONE,
                    ToolRiskLevel.LOW: ConfirmationGate.NONE,
                    ToolRiskLevel.MEDIUM: ConfirmationGate.IMPLICIT,
                    ToolRiskLevel.HIGH: ConfirmationGate.EXPLICIT,
                    ToolRiskLevel.CRITICAL: ConfirmationGate.MANDATORY,
                }
                confirmation_gate = gate_mapping.get(risk_level, ConfirmationGate.IMPLICIT)

                operation = ToolOperation(
                    tool_name=tool_name,
                    operation=tool_name,  # Operation type same as tool name
                    parameters=arguments if isinstance(arguments, dict) else {},
                    risk_level=risk_level,
                    confirmation_gate=confirmation_gate,
                    estimated_time=1.0,  # Default estimate
                    rollback_possible=tool_name not in ('bash_execute', 'file_delete'),
                    security_sensitive=tool_name == 'bash_execute'
                )
                operations.append(operation)

            # Create tool chain
            chain = ToolChain(
                chain_id=str(uuid.uuid4()),
                operations=operations,
                requires_confirmation=any(op.confirmation_gate != ConfirmationGate.NONE for op in operations),
                parallel_capable=False  # Sequential execution for safety
            )

            # Execute via orchestrator (synchronously wrap async call)
            loop = None
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            orchestration_result = loop.run_until_complete(
                self.tool_orchestrator.execute_tool_chain(chain)
            )

            # Convert orchestration results to structured format
            structured_results = []
            for i, result in enumerate(orchestration_result.results):
                tool_call = tool_calls[i] if i < len(tool_calls) else {}
                success = result.get('success', True)
                output = result.get('output', '')
                error = result.get('error', '')

                structured_results.append({
                    'tool_name': operations[i].tool_name,
                    'success': success,
                    'output': output,
                    'error': error,
                    'arguments': operations[i].parameters,
                    'openai_format': {
                        'role': 'tool',
                        'content': output if success else json.dumps({'error': error}),
                        'tool_call_id': tool_call.get('id', ''),
                        'name': operations[i].tool_name
                    }
                })

            return structured_results

        except Exception as e:
            log_message(f"TOOL_ORCHESTRATOR ERROR: Failed to execute via orchestrator: {e}")
            import traceback
            log_message(f"TOOL_ORCHESTRATOR TRACEBACK: {traceback.format_exc()}")
            return None

    def handle_tool_calls(self, tool_calls, message_data, return_results: bool = False,
                          suppress_ui: bool = False, log_buffer: list | None = None,
                          agent_name: str | None = None):
        """Handle tool calls from model response.

        Args:
            tool_calls: List of OpenAI-style function call dicts
            message_data: Assistant message dict to append to history
            return_results: When True, returns a structured list of per-tool results
            suppress_ui: When True, do not emit UI messages to chat; capture in log_buffer if provided
            log_buffer: Optional list to append log lines when suppressing UI

        Returns:
            Optional[List[dict]]: [{tool_name, success, output, error, arguments}] if return_results is True
        """
        log_message(f"CHAT_INTERFACE: Handling {len(tool_calls)} tool calls")
        if getattr(self, '_orchestrator_required', False) and not getattr(self, 'tool_orchestrator', None):
            log_message("CHAT_INTERFACE WARNING: Tool Orchestrator enforcement active but instance unavailable - proceeding without enforcement")
            # Don't crash - just log and continue without orchestrator enforcement
        # Ensure tool executor exists before proceeding
        try:
            if not getattr(self, 'tool_executor', None):
                self.initialize_tool_executor()
        except Exception:
            pass

        # Add assistant message with tool calls to history
        self.chat_history.append(message_data)

        # Build effective enabled tool map:
        # - Backend Tools tab provides defaults
        # - Quick Actions (per-chat) overrides those defaults
        # - If executing on behalf of an agent, overlay that agent's enabled_tools on top
        effective_enabled: dict | None = None
        try:
            base_map = None
            if hasattr(self.parent_tab, 'tools_interface') and self.parent_tab.tools_interface:
                # Expect a dict of {tool_name: BoolVar}
                ti = self.parent_tab.tools_interface
                base_map = {k: bool(v.get()) for k, v in (getattr(ti, 'tool_vars', {}) or {}).items()}
                log_message(f"CHAT_INTERFACE: Tools tab defaults loaded ({sum(1 for v in base_map.values() if v)} enabled)")
            # Overlay per-chat overrides if present
            overrides = getattr(self, 'session_enabled_tools', None)
            if overrides and isinstance(overrides, dict):
                eff = dict(base_map or {})
                for k, v in overrides.items():
                    eff[k] = bool(v)
                effective_enabled = eff
                log_message("CHAT_INTERFACE: Applied per-chat tool overrides from Quick Actions")
            else:
                effective_enabled = base_map  # may be None → allow all

            # Overlay agent-specific enabled_tools if provided
            if agent_name:
                try:
                    roster = []
                    if hasattr(self.root, 'get_active_agents') and callable(getattr(self.root, 'get_active_agents')):
                        roster = self.root.get_active_agents() or []
                    agent_rec = next((r for r in roster if (r.get('name') or '').strip().lower() == agent_name.strip().lower()), None)
                    if agent_rec is not None:
                        a_map = dict(agent_rec.get('enabled_tools') or {})
                        # If no base map yet, start from empty dict (restrictive default)
                        eff_map = dict(effective_enabled or {})
                        for k, v in a_map.items():
                            eff_map[k] = bool(v)
                        effective_enabled = eff_map
                        log_message(f"CHAT_INTERFACE: Applied agent override tool map for '{agent_name}' ({sum(1 for v in (a_map or {}).values() if v)} enabled)")
                except Exception as e:
                    log_message(f"CHAT_INTERFACE: Agent tool overlay error: {e}")
        except Exception:
            effective_enabled = None  # fail open (allow all)

        tool_echo_main = True
        if agent_name:
            tool_echo_main = self._agent_should_echo_tools(agent_name)

        # Require explicit permission when defaults allow all tools
        if effective_enabled is None:
            if not self._ensure_tools_permission():
                if suppress_ui:
                    if log_buffer is not None:
                        log_buffer.append("[System] Tool execution skipped (permission denied).")
                else:
                    _route_tool_message("Tool execution skipped (permission denied).")
                return [] if return_results else None

        def _route_tool_message(message: str, *, error: bool = False):
            if agent_name:
                self._emit_agent_status(
                    agent_name,
                    message,
                    role='error' if error else 'system',
                    use_tool_route=True,
                )
            else:
                channel = 'error' if error else 'system'
                self.add_message(channel, message)

        # Display tool execution message with tool names
        tool_names = [tc.get('function', {}).get('name', 'unknown') for tc in tool_calls]
        if len(tool_names) == 1:
            tool_msg = f"🔧 Executing {tool_names[0]}"
        elif len(tool_names) <= 3:
            tool_msg = f"🔧 Executing {', '.join(tool_names)}"
        else:
            tool_msg = f"🔧 Executing {len(tool_names)} tools: {', '.join(tool_names[:3])}..."

        if suppress_ui:
            if log_buffer is not None:
                log_buffer.append(f"[System] {tool_msg}")
        else:
            if agent_name and not tool_echo_main:
                self._record_agent_panel_event(
                    agent_name,
                    tool_msg,
                    'tool',
                    use_tool_route=True,
                    deliver_main=False,
                )
            else:
                self.add_message("system", tool_msg)

        # TOOL ORCHESTRATOR INTEGRATION (TO-001 fix)
        # If orchestrator is enabled, route ALL tool execution through it for risk assessment
        if getattr(self, 'tool_orchestrator', None):
            try:
                log_message("TOOL_ORCHESTRATOR: Intercepting tool calls for risk assessment")
                orchestrated_results = self._execute_via_orchestrator(
                    tool_calls,
                    agent_name=agent_name,
                    suppress_ui=suppress_ui,
                    log_buffer=log_buffer,
                    route_func=_route_tool_message
                )

                # If orchestrator handled it, return early
                if orchestrated_results is not None:
                    log_message(f"TOOL_ORCHESTRATOR: Completed execution of {len(tool_calls)} tools via orchestrator")
                    if return_results:
                        return orchestrated_results

                    # Continue with normal flow for history updates
                    tool_results = [r.get('openai_format') for r in orchestrated_results if r.get('openai_format')]
                    structured_results = orchestrated_results
                    # Skip to post-execution (jump past the normal execution loop)
                    # We'll handle this by setting a flag
                    _orchestrator_handled = True
                else:
                    _orchestrator_handled = False
            except Exception as e:
                log_message(f"TOOL_ORCHESTRATOR ERROR: Orchestrator failed, falling back to direct execution: {e}")
                _orchestrator_handled = False
        else:
            _orchestrator_handled = False

        # Normal execution path (only if orchestrator didn't handle it)
        if not _orchestrator_handled:
            # Split tools into built-in (agent/UI control) vs external (tool_executor)
            # Built-in tools must execute directly in UI, not via tool_executor
            BUILTIN_TOOLS = {
                "agents_mount_all", "agents_unmount_all", "agents_status",
                "agents_list_available", "agents_set_roster", "agents_route_task",
                "agents_open_tab", "agents_highlight_in_collections",
                "agents_focus_mounts", "agent_request"
            }

            builtin_calls = []
            external_calls = []
            for tc in tool_calls:
                tool_name = tc.get("function", {}).get("name")
                if tool_name in BUILTIN_TOOLS:
                    builtin_calls.append(tc)
                else:
                    external_calls.append(tc)

            log_message(f"TOOL_ROUTING: Split {len(tool_calls)} tools: {len(builtin_calls)} built-in, {len(external_calls)} external")

            # Check if tool queue is enabled (default: enabled)
            use_tool_queue = self.backend_settings.get('tool_queue_enabled', True)

            # Execute external tools via queue (if enabled) or direct
            external_structured = []
            external_tool_results = []

            if external_calls:
                if use_tool_queue and hasattr(self, '_tool_execution_queue'):
                    # Queue-based execution for external tools
                    log_message(f"TOOL_QUEUE: Enqueuing {len(external_calls)} external tools for execution")
                    external_structured, external_tool_results = self._execute_tools_via_queue(
                        external_calls,
                        agent_name=agent_name,
                        effective_enabled=effective_enabled,
                        route_func=_route_tool_message
                    )
                else:
                    # Direct execution for external tools (queue disabled fallback)
                    log_message(f"TOOL_QUEUE: Using direct execution for {len(external_calls)} external tools (queue disabled)")
                    # Will process external_calls in the direct execution loop below

            # Now handle ALL tools via direct execution path if queue was disabled
            # OR handle just built-in tools if queue was enabled
            if not use_tool_queue or not hasattr(self, '_tool_execution_queue'):
                # Queue disabled: process all tools directly
                tools_to_process = tool_calls
            else:
                # Queue enabled: only process built-in tools directly
                tools_to_process = builtin_calls

            if tools_to_process:
                # Direct execution loop
                log_message(f"TOOL_DIRECT: Processing {len(tools_to_process)} tools directly")
                direct_structured = []
                direct_tool_results = []
                for tool_call in tools_to_process:
                    function_data = tool_call.get("function", {})
                    tool_name = function_data.get("name")
                    arguments = function_data.get("arguments", {})

                    # Normalize legacy aliases to current executor keys
                    alias_map = {
                        'run_bash_command': 'bash_execute',
                        'grep': 'grep_search',
                        'list_directory': 'directory_list',
                        'cd': 'change_directory',
                    }
                    if tool_name in alias_map:
                        tool_name = alias_map[tool_name]

                    # Check if tool is enabled in Tools tab
                    if isinstance(effective_enabled, dict):
                        # Check normalized key and original name just in case
                        is_enabled = bool(effective_enabled.get(tool_name, False) or effective_enabled.get(function_data.get('name', ''), False))
                        if not is_enabled:
                            log_message(f"CHAT_INTERFACE: Tool '{tool_name}' disabled by effective settings; skipping")
                            disabled_msg = f"  ✗ {tool_name}: Tool is disabled for this chat"
                            _route_tool_message(disabled_msg)
                            direct_tool_results.append({
                                "role": "tool",
                                "content": json.dumps({"error": "Tool is disabled in settings"}),
                                "tool_call_id": tool_call.get("id", ""),
                                "name": tool_name
                            })
                            direct_structured.append({
                                "tool_name": tool_name,
                                "success": False,
                                "output": "",
                                "error": "Tool is disabled in settings"
                            })
                            continue

                    # Parse arguments if they're a JSON string (with JSON Fixer if enabled)
                    # MUST happen before any tool execution to prevent 'str'.get() errors
                    if isinstance(arguments, str):
                        try:
                            if self.json_fixer_enabled:
                                arguments = self.smart_json_parse(arguments)
                                if self.backend_settings.get('enable_debug_logging', False):
                                    log_message(f"DEBUG: JSON Fixer parsed tool arguments")
                            else:
                                arguments = json.loads(arguments)
                        except json.JSONDecodeError:
                            log_message(f"CHAT_INTERFACE ERROR: Failed to parse tool arguments: {arguments}")
                            arguments = {}

                    # Built-in agent orchestration/control tools (execute within UI, not external executor)
                    if tool_name in ("agents_mount_all", "agents_unmount_all", "agents_status", "agents_list_available",
                                  "agents_set_roster", "agents_route_task",
                                  "agents_open_tab", "agents_highlight_in_collections", "agents_focus_mounts",
                                  "agent_request"):
                        # Allowlist check if a map is present
                        if isinstance(effective_enabled, dict) and not effective_enabled.get(tool_name, False):
                            msg = "Tool is disabled for this session"
                            if suppress_ui:
                                if log_buffer is not None:
                                    log_buffer.append(f"[System]   ✗ {tool_name}: {msg}")
                            else:
                                formatted = f"  ✗ {tool_name}: {msg}"
                                _route_tool_message(formatted)
                            direct_tool_results.append({
                                "role": "tool",
                                "content": json.dumps({"error": msg}),
                                "tool_call_id": tool_call.get("id", ""),
                                "name": tool_name
                            })
                            direct_structured.append({
                                "tool_name": tool_name,
                                "success": False,
                                "output": "",
                                "error": msg,
                                "arguments": {}
                            })
                            continue
                        # Trust gate for control tools
                        if tool_name in ("agents_mount_all","agents_unmount_all","agents_set_roster") and not self._orchestrator_allowed():
                            msg = "Requires Expert+ class or Trust High"
                            if suppress_ui:
                                if log_buffer is not None:
                                    log_buffer.append(f"[System]   ✗ {tool_name}: {msg}")
                            else:
                                formatted = f"  ✗ {tool_name}: {msg}"
                                _route_tool_message(formatted)
                            direct_tool_results.append({
                                "role": "tool",
                                "content": json.dumps({"error": msg}),
                                "tool_call_id": tool_call.get("id", ""),
                                "name": tool_name
                            })
                            direct_structured.append({
                                "tool_name": tool_name,
                                "success": False,
                                "output": "",
                                "error": msg,
                                "arguments": {}
                            })
                            continue
                        try:
                            if tool_name == "agents_mount_all":
                                self._mount_agents_all(user_initiated=True)
                                msg = "Mounted all agents in current roster"
                            elif tool_name == "agents_unmount_all":
                                if hasattr(self, "_unmount_agents_all"):
                                    self._unmount_agents_all()
                                msg = "Unmounted all agents"
                            elif tool_name == "agents_status":
                                roster = []
                                try:
                                    if hasattr(self.root, 'get_active_agents') and callable(getattr(self.root, 'get_active_agents')):
                                        roster = self.root.get_active_agents() or []
                                except Exception:
                                    roster = []
                                mounted = set(getattr(self, '_agents_mounted_set', set()) or set())
                                items = []
                                for r in roster:
                                    nm = r.get('name','agent')
                                    items.append(f"{nm}: mounted={'Y' if nm in mounted else 'N'} active={'Y' if r.get('active') else 'N'}")
                                msg = "\n".join(items) if items else "No agents in roster"
                            elif tool_name == "agents_set_roster":
                                # Arguments can include a JSON roster
                                try:
                                    new_roster = []
                                    if isinstance(arguments, dict) and 'roster' in arguments:
                                        new_roster = arguments.get('roster') or []
                                    elif isinstance(arguments, str) and arguments.strip().startswith('['):
                                        new_roster = json.loads(arguments)
                                    if hasattr(self.root, 'set_active_agents'):
                                        self.root.set_active_agents(new_roster)
                                    msg = f"Roster set: {len(new_roster)} agents"
                                except Exception as e:
                                    msg = f"Failed to set roster: {e}"
                            elif tool_name == "agents_route_task":
                                # Send a text to a specific agent tab
                                tgt = arguments.get('agent') or arguments.get('agent_name') or 'agent'
                                txt = arguments.get('text') or arguments.get('message') or ''
                                if hasattr(self, 'send_agent_message') and txt:
                                    self.send_agent_message(tgt, txt)
                                msg = f"Routed to {tgt}"
                            elif tool_name == "agents_open_tab":
                                # Focus Agents tab
                                try:
                                    if hasattr(self.parent_tab, 'select_subtab'):
                                        self.parent_tab.select_subtab('Agents')
                                except Exception:
                                    pass
                                msg = "Opened Agents tab"
                            elif tool_name == "agents_highlight_in_collections":
                                # Trigger a refresh so highlights are visible
                                try:
                                    if hasattr(self.parent_tab, 'refresh_model_list'):
                                        self.parent_tab.refresh_model_list()
                                except Exception:
                                    pass
                                msg = "Collections refreshed"
                            elif tool_name == "agent_request":
                                # Execute agent_request: orchestrator requests assistance from expert agent
                                msg = "Error: agent_request execution failed"  # Default error message
                                target_agent = "unknown"  # Initialize to prevent reference errors in logging
                                try:
                                    target_agent = arguments.get('agent_name', '').strip()
                                    task = arguments.get('task', '').strip()
                                    context = arguments.get('context', '').strip()

                                    # LOG POINT 1: Tool call detected
                                    log_message(
                                        f"AGENT_TOOL_CALL: operation=agent_request_detected caller={agent_name or 'main'} "
                                        f"target={target_agent} task_preview='{task[:80]}...' has_context={bool(context)}"
                                    )

                                    if not target_agent:
                                        msg = "Error: agent_name is required"
                                    elif not task:
                                        msg = "Error: task is required"
                                    else:
                                        # NEW: Routing-based access control (replaces MoE panel validation)
                                        # All orchestrators and main model use same validation path

                                        caller_name = agent_name or 'main_model'

                                        # Validate target agent is mounted
                                        # Find the GUI instance with roster methods
                                        gui_root = None
                                        if hasattr(self, 'gui_instance') and hasattr(self.gui_instance, 'get_active_agents'):
                                            gui_root = self.gui_instance
                                        elif hasattr(self, 'parent_tab') and hasattr(self.parent_tab, 'gui_instance') and hasattr(self.parent_tab.gui_instance, 'get_active_agents'):
                                            gui_root = self.parent_tab.gui_instance
                                        elif hasattr(self.root, 'get_active_agents'):
                                            gui_root = self.root

                                        roster = []
                                        if gui_root:
                                            roster = gui_root.get_active_agents() or []

                                        # Try exact match first
                                        target_found = False
                                        matched_agent_name = None
                                        requested_lower = target_agent.strip().lower()

                                        for r in roster:
                                            agent_name_full = (r.get('name') or '').strip()
                                            if agent_name_full.lower() == requested_lower:
                                                target_found = True
                                                matched_agent_name = agent_name_full
                                                break

                                        # If exact match fails, try fuzzy matching
                                        if not target_found:
                                            for r in roster:
                                                agent_name_full = (r.get('name') or '').strip()
                                                agent_lower = agent_name_full.lower()
                                                # Check if requested name is substring of agent name or vice versa
                                                if requested_lower in agent_lower or agent_lower in requested_lower:
                                                    target_found = True
                                                    matched_agent_name = agent_name_full
                                                    log_message(
                                                        f"AGENT_FUZZY_MATCH: Matched '{target_agent}' → '{agent_name_full}'",
                                                        level='INFO'
                                                    )
                                                    break

                                        # Update target_agent with matched full name if fuzzy match succeeded
                                        if target_found and matched_agent_name and matched_agent_name != target_agent:
                                            target_agent = matched_agent_name

                                        # LOG POINT 2: Agent resolution
                                        log_message(
                                            f"AGENT_TOOL_CALL: operation=agent_resolution caller={caller_name} target={target_agent} "
                                            f"found={target_found} roster_size={len(roster)}",
                                            level='INFO' if target_found else 'WARNING'
                                        )

                                        if not target_found:
                                            msg = f"Error: {target_agent} is not currently mounted"
                                        else:
                                            # Check if target agent's routing allows orchestrator access
                                            if not self._agent_allows_orchestrator_access(target_agent):
                                                _, tool_route = self._get_agent_routes(target_agent)
                                                msg = f"Error: {target_agent} routing is '{tool_route}' (agent dock only). Change tool_route to 'main' or 'both' to allow orchestrator calls."
                                                log_message(f"AGENT_ACCESS_DENIED: caller={caller_name} target={target_agent} tool_route={tool_route}")
                                            else:
                                                # Build agent prompt with context
                                                agent_prompt = f"{context}\n\n{task}" if context else task

                                                # Execute on target agent with retry logic and track timing
                                                # Wrapped with serialization to prevent concurrent agent requests
                                                import time as _time
                                                max_retries = arguments.get('max_retries', 2) if isinstance(arguments, dict) else 2

                                                def _execute_agent_request():
                                                    """Inner function to execute agent request (wrapped by serialization)."""
                                                    retry_delay = 1.0
                                                    start_time = _time.time()
                                                    success = False
                                                    last_error = None

                                                    for attempt in range(max_retries + 1):
                                                        try:
                                                            if attempt > 0:
                                                                log_message(f"AGENT_RETRY: caller={caller_name} target={target_agent} attempt={attempt+1}/{max_retries+1} delay={retry_delay}s")
                                                                _time.sleep(retry_delay)
                                                                retry_delay *= 2  # Exponential backoff

                                                            self.run_agent_inference(target_agent, agent_prompt)
                                                            success = True
                                                            break
                                                        except Exception as e:
                                                            last_error = e
                                                            if attempt < max_retries:
                                                                log_message(f"AGENT_RETRY: attempt {attempt+1} failed: {e}")
                                                            else:
                                                                log_message(f"AGENT_RETRY: all attempts exhausted: {e}")
                                                                raise

                                                    return start_time

                                                # Execute with serialization (blocks if another agent request is active)
                                                start_time = self._wrap_agent_request_with_serialization(_execute_agent_request)

                                                duration_ms = int((_time.time() - start_time) * 1000)

                                                # Retrieve the agent's response from session log with metadata
                                                response = "(no response)"
                                                tokens_estimate = 0
                                                try:
                                                    with self._agents_sessions_lock:  # Thread-safe access
                                                        self._ensure_agents_sessions()
                                                        if target_agent in self._agents_sessions:
                                                            log = self._agents_sessions[target_agent].get('log', [])
                                                            if log:
                                                                # Get most recent assistant message
                                                                for entry in reversed(log):
                                                                    if entry.get('role') == 'assistant':
                                                                        response = entry.get('text', '(no content)')
                                                                        # Rough token estimate (words * 1.3)
                                                                        tokens_estimate = int(len(response.split()) * 1.3)
                                                                        break
                                                except Exception:
                                                    pass

                                                # Get agent metadata from roster
                                                agent_variant = ""
                                                agent_assigned_type = ""
                                                try:
                                                    for r in roster:
                                                        if (r.get('name') or '').strip().lower() == target_agent.strip().lower():
                                                            agent_variant = r.get('variant', '')
                                                            agent_assigned_type = r.get('assigned_type', '')
                                                            break
                                                except Exception:
                                                    pass

                                                # Log inter-agent communication
                                                log_message(f"AGENT_COMM: {caller_name} → {target_agent}: {task[:80]}...")
                                                log_message(f"AGENT_COMM: {target_agent} → {caller_name}: {response[:80]}...")

                                                # Debug: Log detailed agent interaction
                                                log_message(f"AGENT_REQUEST DEBUG: caller={caller_name}, target={target_agent}, task_len={len(task)}, response_len={len(response)}, duration={duration_ms}ms")
                                                log_message(f"AGENT_REQUEST DEBUG: Full task: {task}")
                                                log_message(f"AGENT_REQUEST DEBUG: Full response: {response}")

                                                # Build structured response with metadata
                                                msg = json.dumps({
                                                    "agent": target_agent,
                                                    "response": response,
                                                    "metadata": {
                                                        "variant": agent_variant,
                                                        "assigned_type": agent_assigned_type,
                                                        "tokens_estimate": tokens_estimate,
                                                        "duration_ms": duration_ms,
                                                        "success": bool(response and response != "(no response)")
                                                    }
                                                })

                                                # Debug: Log what gets returned to caller
                                                log_message(f"AGENT_REQUEST DEBUG: Returning to {caller_name}: {msg[:500]}")

                                                # LOG POINT 7: Result formatted
                                                log_message(
                                                    f"AGENT_TOOL_CALL: operation=result_formatted caller={caller_name} target={target_agent} "
                                                    f"response_len={len(response)} tokens_est={tokens_estimate} duration_ms={duration_ms} formatted_msg_len={len(msg)}"
                                                )
                                except Exception as e:
                                    msg = f"Error: agent_request failed: {e}"
                                    log_message(f"AGENT_REQUEST ERROR: {e}")
                            elif tool_name == "agents_list_available":
                                # Return list of all mounted agents with metadata
                                roster = []
                                try:
                                    if hasattr(self.root, 'get_active_agents') and callable(getattr(self.root, 'get_active_agents')):
                                        roster = self.root.get_active_agents() or []
                                except Exception:
                                    roster = []

                                agents_info = []
                                for r in roster:
                                    agent_name_var = r.get('name', 'unknown')
                                    variant = r.get('variant', '')
                                    assigned_type = r.get('assigned_type', 'general')

                                    # Check if mounted
                                    mounted_set = getattr(self, '_agents_mounted_set', set()) or set()
                                    is_mounted = agent_name_var in mounted_set

                                    # Check if callable by orchestrators
                                    can_call = self._agent_allows_orchestrator_access(agent_name_var) if is_mounted else False

                                    # Get routing info
                                    chat_route, tool_route = self._get_agent_routes(agent_name_var)

                                    # Get assigned type from variant if not in roster
                                    if not assigned_type or assigned_type == 'general':
                                        try:
                                            if hasattr(self.parent_tab, 'agents_tab') and variant:
                                                agent_type = self.parent_tab.agents_tab._get_variant_type(variant)
                                                if agent_type:
                                                    assigned_type = agent_type
                                        except Exception:
                                            pass

                                    agents_info.append({
                                        "name": agent_name_var,
                                        "variant": variant,
                                        "assigned_type": assigned_type,
                                        "mounted": is_mounted,
                                        "callable_by_orchestrators": can_call,
                                        "chat_route": chat_route,
                                        "tool_route": tool_route
                                    })

                                msg = json.dumps({"agents": agents_info, "count": len(agents_info)})
                            elif tool_name == "agents_focus_mounts":
                                msg = "Agents Quick Actions disabled; open the Agents tab to manage mounts."
                            # Emit as tool result without calling external executor
                            # LOG POINT 10: UI displayed (for agent_request only)
                            if tool_name == "agent_request":
                                log_message(
                                    f"AGENT_TOOL_CALL: operation=ui_displayed caller={agent_name or 'main'} "
                                    f"target={target_agent if tool_name == 'agent_request' else 'N/A'} suppressed={suppress_ui} msg_preview='{msg[:80]}...'"
                                )

                            if suppress_ui:
                                if log_buffer is not None:
                                    log_buffer.append(f"[System]   ✓ {tool_name}: {msg}")
                            else:
                                success_msg = f"  ✓ {tool_name}: {msg}"
                                _route_tool_message(success_msg)

                            direct_tool_results.append({
                                "role": "tool",
                                "content": json.dumps({"ok": True, "message": msg}),
                                "tool_call_id": tool_call.get("id", ""),
                                "name": tool_name
                            })

                            # LOG POINT 8: Tool result created (for agent_request)
                            if tool_name == "agent_request":
                                log_message(
                                    f"AGENT_TOOL_CALL: operation=tool_result_created caller={agent_name or 'main'} "
                                    f"target={target_agent if 'target_agent' in locals() else 'N/A'} "
                                    f"tool_call_id={tool_call.get('id', 'none')} success=True"
                                )

                            direct_structured.append({
                                "tool_name": tool_name,
                                "success": True,
                                "output": msg,
                                "error": "",
                                "arguments": {}
                            })
                            continue
                        except Exception as e:
                            err = f"orchestrator tool failed: {e}"
                            if suppress_ui:
                                if log_buffer is not None:
                                    log_buffer.append(f"[System]   ✗ {tool_name}: {err}")
                            else:
                                _route_tool_message(f"  ✗ {tool_name}: {err}", error=True)
                            direct_tool_results.append({
                                "role": "tool",
                                "content": json.dumps({"error": err}),
                                "tool_call_id": tool_call.get("id", ""),
                                "name": tool_name
                            })
                            direct_structured.append({
                                "tool_name": tool_name,
                                "success": False,
                                "output": "",
                                "error": err,
                                "arguments": {}
                            })
                            continue

                    # Normalize common aliases for known tools to reduce fragile failures
                    try:
                        norm = dict(arguments)
                        tn = (tool_name or '').strip().lower()
                        # file_move / file_copy support
                        if tn in ('file_move', 'file_copy'):
                            if 'source' not in norm:
                                for k in ('source_path', 'src', 'from'):
                                    if k in norm:
                                        norm['source'] = norm.pop(k)
                                        break
                            if 'destination' not in norm:
                                for k in ('dest_path', 'destination_path', 'dst', 'to'):
                                    if k in norm:
                                        norm['destination'] = norm.pop(k)
                                        break
                        # file_delete supports 'path'
                        if tn == 'file_delete':
                            if 'file_path' not in norm and 'path' in norm:
                                norm['file_path'] = norm.pop('path')
                        # file_read supports 'path' and start/end shorthand
                        if tn == 'file_read':
                            if 'file_path' not in norm and 'path' in norm:
                                norm['file_path'] = norm.pop('path')
                            if 'start' in norm and 'start_line' not in norm:
                                norm['start_line'] = norm.pop('start')
                            if 'end' in norm and 'end_line' not in norm:
                                norm['end_line'] = norm.pop('end')
                        arguments = norm
                    except Exception:
                        pass

                    # Apply Schema Validator if enabled
                    if self.schema_validator:
                        try:
                            validation_result = self.schema_validator.validate(tool_name, arguments)
                            if not validation_result.get('valid', True):
                                if self.backend_settings.get('enable_debug_logging', False):
                                    log_message(f"DEBUG: Schema validation failed for {tool_name}: {validation_result.get('errors', [])}")
                                # Optionally skip invalid tool calls based on mode
                                if self.advanced_settings.get('schema_validation', {}).get('mode') == 'strict':
                                    failure_msg = f"  ✗ {tool_name}: Schema validation failed"
                                    _route_tool_message(failure_msg, error=True)
                                    continue
                            else:
                                if self.backend_settings.get('enable_debug_logging', False):
                                    log_message(f"DEBUG: Schema validation passed for {tool_name}")
                        except Exception as e:
                            if self.backend_settings.get('enable_debug_logging', False):
                                log_message(f"DEBUG: Schema Validator error: {e}")

                    log_message(f"CHAT_INTERFACE: Executing tool: {tool_name} with args: {arguments}")

                    # Conformer Gate check for file operations (Phase 1.5D)
                    file_operation_tools = ['file_write', 'file_delete', 'file_move', 'file_copy', 'run_bash_command']
                    if tool_name in file_operation_tools:
                        try:
                            from conformer_ui_integration import check_operation_with_ui

                            operation_allowed = check_operation_with_ui(
                                parent_window=self.root,
                                variant_id=self.current_model or "unknown_model",
                                operation_type=tool_name,
                                operation_details=arguments,
                                model_class="Skilled",
                                on_approved=None
                            )

                            if not operation_allowed:
                                log_message(f"CONFORMER GATE: Blocked {tool_name} operation")
                            if suppress_ui:
                                if log_buffer is not None:
                                    log_buffer.append(f"[System]   🛡️ {tool_name}: Operation blocked by Conformer Gate")
                            else:
                                blocked_msg = f"  🛡️ {tool_name}: Operation blocked by Conformer Gate"
                                _route_tool_message(blocked_msg)
                                direct_tool_results.append({
                                    "role": "tool",
                                    "content": json.dumps({"error": "Operation blocked by Conformer Gate"}),
                                    "tool_call_id": tool_call.get("id", ""),
                                    "name": tool_name
                                })
                                direct_structured.append({
                                    "tool_name": tool_name,
                                    "success": False,
                                    "output": "",
                                    "error": "Operation blocked by Conformer Gate",
                                    "arguments": arguments
                                })
                                continue
                        except ImportError:
                            log_message("CONFORMER GATE: conformer_ui_integration not available, skipping gate")
                        except Exception as e:
                            log_message(f"CONFORMER GATE ERROR: {e}")

                    # Show detailed tool call info if enabled in settings
                    show_details = self.backend_settings.get('show_tool_call_details', True)
                    if show_details:
                        line = f"  → {tool_name}({', '.join(f'{k}={v}' for k, v in arguments.items())})"
                        if suppress_ui:
                            if log_buffer is not None:
                                log_buffer.append(f"[System] {line}")
                        else:
                            _route_tool_message(line)

                    # Record conformer event for agent tool calls
                    try:
                        if agent_name:
                            self.add_conformer_event(agent_name, 'tool_call', {'tool': tool_name, 'args': arguments})
                    except Exception:
                        pass
                        # Show working dir and absolute path when applicable (helps verify side effects)
                        try:
                            from pathlib import Path as _P
                            wd = str(self.tool_executor.working_dir) if self.tool_executor else ''
                            det = []
                            if wd:
                                det.append(f"WD: {wd}")
                            # Compute resolved paths for common args
                            def _res(p):
                                if not wd or not p:
                                    return None
                                p = str(p)
                                return str((_P(p) if _P(p).is_absolute() else (self.tool_executor.working_dir / p)).resolve())
                            if 'file_path' in arguments:
                                rp = _res(arguments.get('file_path'))
                                if rp:
                                    det.append(f"Path: {rp}")
                            if tool_name in ('file_move','file_copy'):
                                sp = _res(arguments.get('source'))
                                dp = _res(arguments.get('destination'))
                                if sp:
                                    det.append(f"Src: {sp}")
                                if dp:
                                    det.append(f"Dst: {dp}")
                            if det:
                                detail_msg = '     • ' + ' | '.join(det)
                                _route_tool_message(detail_msg)
                        except Exception:
                            pass

                    # Execute tool (via Orchestrator if enabled, otherwise direct)
                    if self.tool_orchestrator:
                        # Use Tool Orchestrator for intelligent execution
                        try:
                            if self.backend_settings.get('enable_debug_logging', False):
                                log_message(f"DEBUG: Using Tool Orchestrator for {tool_name}")

                            # Validate tool call with orchestrator (sync wrapper for async method)
                            import asyncio
                            validation = asyncio.run(self.tool_orchestrator.validate_tool_call(tool_name, arguments))

                            if not validation.get('valid', False):
                                # Tool call is invalid
                                warnings = validation.get('warnings', [])
                                suggested_fix = validation.get('suggested_fix')

                                if suggested_fix:
                                    # Try suggested fix
                                    if self.backend_settings.get('enable_debug_logging', False):
                                        log_message(f"DEBUG: Tool validation suggested fix: {suggested_fix}")
                                    result = self.tool_executor.execute_tool_sync(
                                        suggested_fix['tool_name'],
                                        suggested_fix['args']
                                    )
                                else:
                                    result = {
                                        'success': False,
                                        'output': '',
                                        'error': f"Tool validation failed: {'; '.join(warnings)}"
                                    }
                            else:
                                # Tool is valid, check if confirmation required
                                if validation.get('confirmation_required', False):
                                    warnings = validation.get('warnings', [])
                                    if self.backend_settings.get('enable_debug_logging', False):
                                        log_message(f"DEBUG: Tool requires confirmation: {'; '.join(warnings)}")
                                    # Note: In GUI context, we execute anyway (user already approved via chat)
                                    # In CLI context, orchestrator would prompt for confirmation

                                # Execute with potentially enhanced args
                                enhanced_args = validation.get('enhanced_args', arguments)
                                result = self.tool_executor.execute_tool_sync(tool_name, enhanced_args)

                        except Exception as e:
                            if self.backend_settings.get('enable_debug_logging', False):
                                log_message(f"DEBUG: Tool Orchestrator error, falling back to direct execution: {e}")
                            # Fallback to direct execution
                            result = self.tool_executor.execute_tool_sync(tool_name, arguments)
                    elif self.tool_executor:
                        # Direct execution
                        result = self.tool_executor.execute_tool_sync(tool_name, arguments)
                    else:
                        result = {'success': False, 'output': '', 'error': 'Tool executor not initialized'}

                    # Apply Verification Engine to result if enabled
                    if self.verification_engine and result['success']:
                        try:
                            verification_result = self.verification_engine.verify_output(
                                tool_name, result['output']
                            )
                            if self.backend_settings.get('enable_debug_logging', False):
                                log_message(f"DEBUG: Verification result for {tool_name}: " +
                                           f"passed={verification_result.get('passed', True)}")

                            # Auto-fix if enabled and verification suggests fixes
                            if self.advanced_settings.get('verification', {}).get('auto_fix', True):
                                if verification_result.get('fixed_output'):
                                    result['output'] = verification_result['fixed_output']
                                    if self.backend_settings.get('enable_debug_logging', False):
                                        log_message(f"DEBUG: Auto-fixed output for {tool_name}")
                        except Exception as e:
                            if self.backend_settings.get('enable_debug_logging', False):
                                log_message(f"DEBUG: Verification Engine error: {e}")

                    # Process result
                    if result.get('success'):
                        out_payload = result.get('output')
                        if isinstance(out_payload, str):
                            try:
                                parsed = json.loads(out_payload)
                                if isinstance(parsed, dict) and parsed.get('error'):
                                    result['success'] = False
                                    result['error'] = parsed.get('error')
                                    result['output'] = ""
                            except Exception:
                                pass
                        data_payload = result.get('data')
                        if isinstance(data_payload, dict) and data_payload.get('error'):
                            result['success'] = False
                            result['error'] = data_payload.get('error')

                    if result['success']:
                        if show_details:
                            output_preview = result['output'][:200] if len(result['output']) > 200 else result['output']
                            if suppress_ui:
                                if log_buffer is not None:
                                    log_buffer.append(f"[System]   ✓ {tool_name}: {output_preview}")
                            else:
                                success_msg = f"  ✓ {tool_name}: {output_preview}"
                                _route_tool_message(success_msg)

                        # Animate energy arc for successful file operations
                        file_path_arg = None
                        if 'file_path' in arguments:
                            file_path_arg = arguments['file_path']
                        elif 'absolute_path' in arguments:
                            file_path_arg = arguments['absolute_path']

                        if file_path_arg and not suppress_ui:
                            self._animate_energy_arc(file_path_arg)

                        tool_results.append({
                            "role": "tool",
                            "content": result['output'],
                            "name": tool_name,
                            "tool_call_id": tool_call.get("id", "")
                        })
                        # Apply temporary resource profile changes for resource_request tool
                        # FIXED RR-001: Now properly scoped - save, apply, restore immediately after this tool
                        if tool_name == 'resource_request':
                            try:
                                data_obj = result.get('data') if isinstance(result.get('data'), dict) else None
                                granted = None
                                if data_obj:
                                    granted = data_obj.get('granted')
                                if granted is None:
                                    granted = 50
                                import os
                                cpu_count = max(1, os.cpu_count() or 8)
                                pct = max(1, min(int(granted), 100))
                                threads = max(1, round(cpu_count * (pct/100.0)))

                                # Save original value ONLY ONCE (prevent nested overwrites)
                                if not hasattr(self, '_session_prev_cpu_threads'):
                                    self._session_prev_cpu_threads = self.backend_settings.get('cpu_threads')

                                # Apply temporary value
                                original_threads = self.backend_settings.get('cpu_threads')
                                self.backend_settings['cpu_threads'] = threads
                                message = f"⚙️ Applied ResourceRequest: cpu_threads set to {threads} (from {cpu_count} cores, was {original_threads}). Will restore after this tool."
                                _route_tool_message(message)

                                # IMMEDIATE RESTORATION (RR-001 fix): Restore after this specific tool completes
                                # The next tool in the batch will use original settings, not mutated ones
                                self.backend_settings['cpu_threads'] = original_threads
                                log_message(f"CHAT_INTERFACE: Restored cpu_threads to {original_threads} immediately after ResourceRequest (RR-001 fix)")
                            except Exception as e:
                                log_message(f"CHAT_INTERFACE ERROR: ResourceRequest handling failed: {e}")
                        # Sync executor WD on change_directory success
                        if tool_name == 'change_directory':
                            try:
                                newp = None
                                d = result.get('data') if isinstance(result.get('data'), dict) else {}
                                newp = d.get('new_path') or d.get('new_dir')
                                if newp and self.tool_executor:
                                    self.tool_executor.set_working_directory(newp)
                            except Exception:
                                pass

                        structured_results.append({
                            "tool_name": tool_name,
                            "success": True,
                            "output": result.get('output', ''),
                            "error": None,
                            "arguments": arguments
                        })

                        # Phase 2A: Add feedback UI for successful tool execution
                        # Only show when training_mode AND training_support both enabled
                        if not suppress_ui and self.training_mode_enabled and self.backend_settings.get('training_support_enabled', False):
                            self._add_tool_feedback_ui(tool_name, arguments, result, detected_success=True)

                        # Phase 2: Auto-update stats when training_mode ON but training_support OFF
                        elif self.training_mode_enabled and not self.backend_settings.get('training_support_enabled', False):
                            try:
                                import config

                                # Auto-detect: success gets quality 1.0
                                quality_score = 1.0
                                feedback_match = True  # System's own detection

                                # Award XP and update stats automatically
                                config.award_xp_from_tool_feedback(
                                    variant_id=self.current_model,
                                    tool_name=tool_name,
                                    quality_score=quality_score,
                                    feedback_match=feedback_match
                                )

                                config.update_stats_from_tool_feedback(
                                    variant_id=self.current_model,
                                    tool_name=tool_name,
                                    quality_score=quality_score,
                                    feedback_match=feedback_match
                                )
                            except Exception as e:
                                log_message(f"CHAT_INTERFACE: Auto-stats update failed for success: {e}")

                    else:
                        error_msg = result.get('error', 'Unknown error')
                        if suppress_ui:
                            if log_buffer is not None:
                                log_buffer.append(f"[Error]   ✗ {tool_name}: {error_msg}")
                        else:
                            message = f"  ✗ {tool_name}: {error_msg}"
                            if agent_name:
                                self._emit_agent_status(agent_name, message, role='error', use_tool_route=True)
                            else:
                                self.add_message("error", message)
                        tool_results.append({
                            "role": "tool",
                            "content": f"Error: {error_msg}",
                            "name": tool_name,
                            "tool_call_id": tool_call.get("id", "")
                        })
                        structured_results.append({
                            "tool_name": tool_name,
                            "success": False,
                            "output": "",
                            "error": error_msg,
                            "arguments": arguments
                        })

                        # Phase 2A: Add feedback UI for failed tool execution
                        # Only show when training_mode AND training_support both enabled
                        if not suppress_ui and self.training_mode_enabled and self.backend_settings.get('training_support_enabled', False):
                            self._add_tool_feedback_ui(tool_name, arguments, result, detected_success=False)

                        # Phase 2: Auto-update stats when training_mode ON but training_support OFF
                        elif self.training_mode_enabled and not self.backend_settings.get('training_support_enabled', False):
                            try:
                                import config

                                # Auto-detect: failure gets quality 0.0
                                quality_score = 0.0
                                feedback_match = True  # System's own detection

                                # Award XP and update stats automatically
                                config.award_xp_from_tool_feedback(
                                    variant_id=self.current_model,
                                    tool_name=tool_name,
                                    quality_score=quality_score,
                                    feedback_match=feedback_match
                                )

                                config.update_stats_from_tool_feedback(
                                    variant_id=self.current_model,
                                    tool_name=tool_name,
                                    quality_score=quality_score,
                                    feedback_match=feedback_match
                                )
                            except Exception as e:
                                log_message(f"CHAT_INTERFACE: Auto-stats update failed for failure: {e}")

        # Merge results from queue and direct execution paths
        if use_tool_queue and hasattr(self, '_tool_execution_queue') and external_calls:
            # Queue was enabled: merge external (queued) + built-in (direct) results
            structured_results = external_structured + direct_structured
            tool_results = external_tool_results + direct_tool_results
            log_message(f"TOOL_ROUTING: Merged results - {len(external_structured)} from queue, {len(direct_structured)} direct")
        elif tools_to_process:
            # Queue was disabled: all tools processed directly
            structured_results = direct_structured
            tool_results = direct_tool_results
            log_message(f"TOOL_ROUTING: Using {len(direct_structured)} direct execution results (queue disabled)")
        else:
            # No tools processed (shouldn't happen, but safety fallback)
            structured_results = []
            tool_results = []

        # Add tool results to history
        if not suppress_ui:
            self.chat_history.extend(tool_results)

            # LOG POINT 9: History updated (track agent_request tool calls)
            agent_request_count = sum(1 for tr in tool_results if tr.get('name') == 'agent_request')
            if agent_request_count > 0:
                log_message(
                    f"AGENT_TOOL_CALL: operation=history_updated caller={agent_name or 'main'} "
                    f"tool_results_added={len(tool_results)} agent_requests={agent_request_count} "
                    f"new_history_len={len(self.chat_history)}"
                )

        # Log for training and real-time evaluation if enabled
        if self.training_mode_enabled:
            try:
                model_name = self.current_model

                # Use ToolCallLogger for training data logging
                if self.tool_call_logger:
                    self.tool_call_logger.log_training_example(self.chat_history.copy(), model_name)
                    self.tool_call_logger.log_batch_tool_calls(tool_calls, tool_results, model_name)
                    log_message(f"CHAT_INTERFACE: Logged tool calls via ToolCallLogger")

                # Perform real-time evaluation scoring
                if model_name not in self.realtime_eval_scores:
                    self.realtime_eval_scores[model_name] = {}

                for tool_call, res in zip(tool_calls, tool_results):
                    tool_name = tool_call.get("function", {}).get("name")
                    if tool_name not in self.realtime_eval_scores[model_name]:
                        self.realtime_eval_scores[model_name][tool_name] = {"success": 0, "failure": 0, "errors": []}

                    # Enhanced success validation
                    is_success, failure_reason = self._validate_tool_call_success(
                        tool_call, res, self.last_user_message
                    )

                    if is_success:
                        self.realtime_eval_scores[model_name][tool_name]["success"] += 1
                    else:
                        self.realtime_eval_scores[model_name][tool_name]["failure"] += 1
                        error_msg = f"{failure_reason}: {res['content'][:200]}"
                        self.realtime_eval_scores[model_name][tool_name]["errors"].append(error_msg)

                log_message(f"CHAT_INTERFACE: Updated real-time scores for {model_name}: {self.realtime_eval_scores[model_name]}")
                if not suppress_ui:
                    score_msg = f"📈 Real-time score updated for {model_name}."
                    _route_tool_message(score_msg)

            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed during training mode operation: {e}")
                self.add_message("error", f"Failed to process training data: {e}")

            # MVP: Generate strict runtime JSONL for failed calls and notify Training tab
            try:
                import json as _json
                import config as C
                from ..runtime_to_training import RuntimeToTrainingConverter as _RT

                # Resolve variant from mounted model tag (lineage-aware)
                tag = self.current_model or ""
                vid = None
                assigned_type = None
                try:
                    lid = C.get_lineage_for_tag(tag)
                except Exception:
                    lid = None
                if lid:
                    # First try assignments map
                    try:
                        data = C.load_ollama_assignments() or {}
                        for k, v in data.items():
                            if k == 'tag_index':
                                continue
                            if isinstance(v, dict) and v.get('lineage_id') == lid:
                                vid = k
                                break
                    except Exception:
                        pass
                    # Fallback: scan model profiles
                    if not vid:
                        try:
                            for rec in (C.list_model_profiles() or []):
                                if rec.get('lineage_id') == lid:
                                    vid = rec.get('variant_id')
                                    break
                        except Exception:
                            pass
                # Load assigned_type when variant resolved
                if vid:
                    try:
                        mp = C.load_model_profile(vid) or {}
                        at = mp.get('assigned_type')
                        assigned_type = at[0] if isinstance(at, list) else at
                    except Exception:
                        assigned_type = None

                # Build strict JSONL for failed tool calls only; if none, synthesize from refusal
                synth_calls = []
                synth_results = []
                if not tool_calls:
                    # Check refusal patterns in last assistant message
                    if self.chat_history and self.chat_history[-1].get('role') == 'assistant':
                        atext = (self.chat_history[-1].get('content') or '').lower()
                        refusal = any(ph in atext for ph in ["i can't", "i cannot", "i won'", "not allowed", "refuse", "unable to"]) or ('no ' in atext and 'permission' in atext)
                        if refusal:
                            guess = self._guess_tool_from_prompt(self.last_user_message)
                            synth_calls = [{"function": {"name": guess, "arguments": {}}}]
                            synth_results = [{"content": "Error: refusal"}]
                tcalls = tool_calls or synth_calls
                tresults = tool_results or synth_results
                out_path, wrote = _RT.write_strict_runtime_jsonl(
                    model_tag=tag,
                    variant_id=vid or (self.current_model or 'unknown'),
                    assigned_type=assigned_type or 'Unknown',
                    user_input=self.last_user_message or '',
                    tool_calls=tcalls,
                    tool_results=tresults,
                    include_success=False
                )
                if wrote > 0 and out_path:
                    runtime_msg = f"📚 Generated runtime training set ({wrote}) → {out_path}"
                    _route_tool_message(runtime_msg)
                    # Notify Training tab to select and persist
                    try:
                        payload = _json.dumps({"variant_id": vid, "path": out_path})
                        self.root.event_generate("<<RuntimeTrainingDataReady>>", data=payload, when="tail")
                    except Exception:
                        pass
                    # Phase 1: Check if auto-pilot mode or auto_start toggle enabled
                    try:
                        # Auto-pilot mode = training_mode ON + training_support OFF (full automation)
                        auto_pilot_enabled = self.training_mode_enabled and not self.backend_settings.get('training_support_enabled', False)
                        auto_start_toggle = self.backend_settings.get('auto_start_training_on_runtime_dataset', False)

                        if auto_pilot_enabled or auto_start_toggle:
                            # Auto-start training with conformer safety check
                            self._start_training_with_safety_check(vid, out_path, auto_initiated=True)
                        else:
                            # Show user prompt for manual approval
                            self._prompt_train_now(vid)
                    except Exception as e:
                        log_message(f"CHAT_INTERFACE: Training initiation failed: {e}")
            except Exception as e:
                log_message(f"CHAT_INTERFACE: strict runtime JSONL generation skipped ({e})")

        # Optionally return structured per-tool results for callers (e.g., Test Tools dialog)
        if hasattr(self, '_session_prev_cpu_threads'):
            try:
                prev_threads = self._session_prev_cpu_threads
                self.backend_settings['cpu_threads'] = prev_threads
                log_message(f"CHAT_INTERFACE: Restored cpu_threads to {prev_threads} after ResourceRequest")
            except Exception as exc:
                log_message(f"CHAT_INTERFACE ERROR: Failed to restore cpu_threads: {exc}")
            finally:
                try:
                    del self._session_prev_cpu_threads
                except Exception:
                    pass

        if return_results:
            return structured_results

        # Continue generation with tool results (for main chat flow, not agents)
        if not suppress_ui and not agent_name and tool_results:
            try:
                log_message(f"CHAT_INTERFACE: Continuing generation after {len(tool_results)} tool results")
                # Generate follow-up response from model with tool results in history
                self.root.after(100, lambda: self.generate_response(""))  # Empty message, just continue with updated history
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to continue after tool execution: {e}")

    def _guess_tool_from_prompt(self, prompt: str) -> str:
        p = (prompt or '').lower()
        if any(k in p for k in ['read file', 'open file', 'view file', 'cat ', 'read ', 'contents of']):
            return 'file_read'
        if any(k in p for k in ['write file', 'save file', 'create file', 'append', 'overwrite']):
            return 'file_write'
        if any(k in p for k in ['search', 'find', 'grep', 'pattern']):
            return 'grep_search'
        if any(k in p for k in ['list files', 'ls', 'dir ']):
            return 'bash'
        if any(k in p for k in ['web', 'http', 'url', 'scrape']):
            return 'web_search'
        return 'file_read'

    def _start_training_with_safety_check(self, variant_id: str, dataset_path: str, auto_initiated: bool = False):
        """
        Start training with conformer safety check (Phase 2 - Safety Integration)

        Args:
            variant_id: Variant to train
            dataset_path: Path to training dataset
            auto_initiated: True if triggered by auto_start toggle or auto-pilot mode
        """
        try:
            import json as _json

            # Phase 2: Only check conformer for auto-initiated training
            if auto_initiated:
                try:
                    from conformer_ui_integration import check_operation_with_ui
                    import config

                    # Get variant class level
                    profile = config.load_model_profile(variant_id)
                    model_class = profile.get('class_level', 'novice') if profile else 'novice'

                    # Check with conformer gate
                    operation_allowed = check_operation_with_ui(
                        parent_window=self.root,
                        variant_id=variant_id,
                        operation_type='training_session',
                        operation_details={'dataset': dataset_path, 'auto_initiated': True},
                        model_class=model_class
                    )

                    if not operation_allowed:
                        log_message(f"CHAT_INTERFACE: Training blocked by conformer for {variant_id}")
                        self.add_message("system", f"⚠️ Auto-training requires approval for {variant_id}. Please review in Training Tab.")
                        return

                except Exception as e:
                    log_message(f"CHAT_INTERFACE: Conformer check failed, blocking auto-training: {e}")
                    self.add_message("error", f"Safety check failed. Please start training manually from Training Tab.")
                    return

            # Proceed with training
            payload = _json.dumps({"variant_id": variant_id})
            self.root.event_generate("<<StartVariantTraining>>", data=payload, when="tail")
            log_message(f"CHAT_INTERFACE: Training initiated for {variant_id}")

        except Exception as e:
            log_message(f"CHAT_INTERFACE: Training initiation failed: {e}")
            self.add_message("error", f"Failed to start training: {e}")

    def _prompt_train_now(self, variant_id: str | None):
        """Small confirm dialog to start training on the newly generated dataset."""
        from tkinter import messagebox
        try:
            if not variant_id:
                # Still allow user to go to Training tab manually
                if messagebox.askyesno("Training", "Training data created. Open Training tab?"):
                    # Fire a simple event that other parts can use to focus Training
                    self.root.event_generate("<<FocusTrainingTab>>", when="tail")
                return
            if messagebox.askyesno("Training", "Training data created. Start training now?"):
                import json as _json
                payload = _json.dumps({"variant_id": variant_id})
                # Ensure selection/persist happened before start
                # Phase 2: Manual training skips conformer check (user approved explicitly)
                self.root.event_generate("<<StartVariantTraining>>", data=payload, when="tail")
        except Exception:
            pass

        # Send tool results back to model for final response
        final_msg = "📨 Sending tool results to model..."
        _route_tool_message(final_msg)
        threading.Thread(
            target=self.generate_final_response_after_tools,
            daemon=True
        ).start()

    def generate_final_response_after_tools(self):
        """Generate final response after tool execution using active backend"""
        try:
            log_message("CHAT_INTERFACE: Generating final response after tool execution")

            backend = self._get_chat_backend()

            if backend == 'llama_server':
                # Include tool schemas so the model can continue calling tools
                schemas = []
                try:
                    schemas = self.get_tool_schemas() or []
                except Exception:
                    schemas = []
                ok, response_data, error_msg, stopped = self._llama_server_chat(self.chat_history, schemas)
                if not ok:
                    if stopped:
                        return
                    log_message(f"CHAT_INTERFACE ERROR: {error_msg}")
                    self.root.after(0, lambda: self.add_message("error", error_msg))
                    return
                # Route through the normal response processor so tool_calls can chain
                try:
                    self._process_model_response(response_data, self.last_user_message)
                except Exception as e:
                    log_message(f"CHAT_INTERFACE ERROR: Post-tools response processing failed: {e}")
                return

            # Prepare payload with tool results (Ollama backend)
            payload = {
                "model": self.current_model,
                "messages": self.chat_history,
                "stream": False,
                "options": {
                    "temperature": self.session_temperature
                }
            }

            # Call Ollama API
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(payload, f)
                payload_file = f.name

            try:
                result = subprocess.run(
                    ["curl", "-s", "-X", "POST", "http://localhost:11434/api/chat",
                     "-H", "Content-Type: application/json",
                     "-d", f"@{payload_file}"],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
            finally:
                Path(payload_file).unlink(missing_ok=True)

            if result.returncode != 0:
                # Respect stop request without showing an empty error
                try:
                    if self._stop_event.is_set():
                        self.root.after(0, lambda: self.add_message('system', '⏹ Generation stopped'))
                        return
                except Exception:
                    pass
                err = (getattr(result, 'stderr', '') or '').strip()
                error_msg = f"Ollama error: {err or 'unknown error'}"
                log_message(f"CHAT_INTERFACE ERROR: {error_msg}")
                self.root.after(0, lambda: self.add_message("error", error_msg))
            else:
                # Parse and route via the normal processor so tool_calls can chain
                response_data = json.loads(result.stdout)
                try:
                    self._process_model_response(response_data, self.last_user_message)
                except Exception as e:
                    log_message(f"CHAT_INTERFACE ERROR: Post-tools response processing failed: {e}")

        except Exception as e:
            error_msg = f"Error generating final response: {str(e)}"
            log_message(f"CHAT_INTERFACE ERROR: {error_msg}")
            self.root.after(0, lambda: self.add_message("error", error_msg))
        finally:
            self.root.after(0, self.reset_buttons)

    def initialize_tool_executor(self):
        """Initialize the tool executor"""
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from tool_executor import ToolExecutor

            # Get working directory from settings if available
            working_dir = None
            if hasattr(self, 'backend_settings'):
                working_dir_str = self.backend_settings.get('working_directory')
                if working_dir_str:
                    working_dir = Path(working_dir_str)

            self.tool_executor = ToolExecutor(working_dir=working_dir)
            log_message(f"CHAT_INTERFACE: Tool executor initialized with working dir: {self.tool_executor.working_dir}")
        except Exception as e:
            log_message(f"CHAT_INTERFACE ERROR: Failed to initialize tool executor: {e}")
            self.tool_executor = None

    def initialize_tool_logging(self):
        """Initialize tool call logger and detector"""
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from tool_call_logger import ToolCallLogger
            from tool_call_detector import ToolCallDetector

            self.tool_call_logger = ToolCallLogger()
            self.tool_call_detector = ToolCallDetector()
            log_message("CHAT_INTERFACE: Tool call logger and detector initialized")
        except Exception as e:
            log_message(f"CHAT_INTERFACE ERROR: Failed to initialize tool logging: {e}")
            self.tool_call_logger = None
            self.tool_call_detector = None

    def initialize_history_manager(self):
        """Initialize chat history manager and knowledge bank manager"""
        try:
            # Add Data directory to path for absolute imports
            data_dir = Path(__file__).parent.parent.parent.parent
            sys.path.insert(0, str(data_dir))

            from ..chat_history_manager import ChatHistoryManager
            from knowledge_bank_manager import KnowledgeBankManager

            self.chat_history_manager = ChatHistoryManager()
            try:
                log_message(f"CHAT_INTERFACE: Chat history dir = {self.chat_history_manager.history_dir}")
            except Exception:
                pass
            log_message("CHAT_INTERFACE: Chat history manager initialized")

            # Initialize knowledge bank manager for two-tier storage
            self.knowledge_bank_manager = KnowledgeBankManager()
            log_message("CHAT_INTERFACE: Knowledge bank manager initialized")
        except Exception as e:
            log_message(f"CHAT_INTERFACE ERROR: Failed to initialize history manager: {e}")
            self.chat_history_manager = None
            self.knowledge_bank_manager = None

    def load_enabled_tools(self):
        """Load enabled tools from unified tool profiles.

        Loads from Data/profiles/Tools/ instead of legacy tool_settings.json.
        Falls back to legacy file if unified profiles don't exist yet.
        """
        # Try unified profiles first (NEW - TE-003 fix)
        try:
            profiles_dir = Path(__file__).parent.parent.parent.parent / "profiles" / "Tools"
            if profiles_dir.exists():
                # Look for default profile or first available profile
                profile_files = list(profiles_dir.glob("*.json"))
                if profile_files:
                    # Try to find "default.json" first
                    default_profile = profiles_dir / "default.json"
                    profile_to_load = default_profile if default_profile.exists() else profile_files[0]

                    with open(profile_to_load, 'r') as f:
                        profile_data = json.load(f)
                        enabled_tools = profile_data.get('enabled_tools', {})
                        log_message(f"CHAT_INTERFACE: Loaded tool profile from {profile_to_load.name}")
                        return enabled_tools
        except Exception as e:
            log_message(f"CHAT_INTERFACE WARNING: Failed to load unified tool profile: {e}, falling back to legacy")

        # Fallback to legacy tool_settings.json
        tool_settings_file = Path(__file__).parent.parent / "tool_settings.json"
        if tool_settings_file.exists():
            try:
                with open(tool_settings_file, 'r') as f:
                    settings = json.load(f)
                    log_message("CHAT_INTERFACE: Using legacy tool_settings.json (consider migrating to unified profiles)")
                    return settings.get('enabled_tools', {})
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to load tool settings: {e}")

        # Default: all safe tools enabled
        log_message("CHAT_INTERFACE: No tool configuration found, using empty default")
        return {}

    def get_tool_schemas(self):
        """Return tool schemas based ONLY on the selected tool schema configuration.

        Quick Actions tool checkboxes control execution (what is allowed to run),
        not what schemas are sent to the model. This function therefore ignores
        per‑chat overrides and backend defaults and reflects the current
        schema selection exclusively.
        """
        # Off/None → no schemas
        if not self.current_tool_schema:
            return []
        try:
            from tool_schemas import TOOL_SCHEMAS
        except Exception as e:
            log_message(f"CHAT_INTERFACE ERROR: Failed to load TOOL_SCHEMAS: {e}")
            return []

        try:
            cfg = self.get_current_tool_schema_config() or {"enabled_tools": "all"}
        except Exception:
            cfg = {"enabled_tools": "all"}

        # Determine which tool names this schema allows
        if isinstance(cfg.get('enabled_tools'), list):
            allowed_names = [name for name in cfg.get('enabled_tools') if name in TOOL_SCHEMAS]
        else:
            # "all" or invalid → allow all known schemas (by selection policy only)
            allowed_names = list(TOOL_SCHEMAS.keys())

        schemas = [TOOL_SCHEMAS[name] for name in allowed_names]
        log_message(f"CHAT_INTERFACE: Selected schema '{self.current_tool_schema}' → {len(schemas)} tool schemas")
        return schemas

    def _list_all_tools(self):
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent / 'site-packages'))
            from opencode.tools import ToolManager
            from opencode.config import ToolsConfig
            cfg = ToolsConfig()
            tm = ToolManager(cfg)
            names = set()
            # Everything registered
            names.update(list(tm.tools.keys()))
            # Plus anything enabled in config defaults (some envs only register a subset)
            names.update(list(getattr(cfg, 'enabled', []) or []))
            # Ensure a representative superset in case registry is minimal
            if len(names) < 10:
                names.update([
                    'file_read','file_write','file_edit','file_copy','file_move','file_delete','file_create','file_fill',
                    'file_search','directory_list','grep_search','bash_execute','process_manage','git_operations',
                    'web_search','web_fetch','code_analyze','package_check','system_info','resource_request','change_directory'
                ])
            return sorted(list(names))
        except Exception:
            return sorted([
                'file_read','file_write','file_edit','file_copy','file_move','file_delete','file_create','file_fill',
                'file_search','directory_list','grep_search','bash_execute','process_manage','git_operations',
                'web_search','web_fetch','code_analyze','package_check','system_info','resource_request','change_directory'
            ])

    def load_backend_settings(self):
        """Load backend settings from custom_code_settings.json with sane defaults"""
        settings_file = Path(__file__).parent.parent / "custom_code_settings.json"
        defaults = {
            'working_directory': str(Path.cwd()),
            'auto_mount_model': False,
            'auto_save_history': True,
            'show_tool_call_details': True,
            'tool_timeout': 30,
            'training_mode_enabled': False,
            'training_support_enabled': False,
            'auto_start_training_on_runtime_dataset': False,
            'auto_export_reeval_after_training': True,
            'conv_locked': True,
            'conv_width': 240,
            'chat_backend': 'ollama',
            'llama_server_base_url': 'http://127.0.0.1:8002',
            'llama_server_default_model': '',
            'llama_server_connect_timeout': 10.0,
            'llama_server_request_timeout': 120.0,
            'llama_server_headers': {},
            'llama_server_auto_start': True,
            'llama_server_host': '127.0.0.1',
            'llama_server_port': 8001,
            'llama_server_binary_path': '',
            'llama_server_extra_args': '',
            'llama_server_keep_alive': True,
            'llama_server_gpu_layers': -1,  # -1 = all layers on GPU (default)
        }

        settings = defaults.copy()

        if settings_file.exists():
            try:
                loaded = json.loads(settings_file.read_text())
                if isinstance(loaded, dict):
                    settings.update(loaded)
                    # Migrate old n_gpu_layers key to llama_server_gpu_layers
                    if 'n_gpu_layers' in loaded and 'llama_server_gpu_layers' not in loaded:
                        settings['llama_server_gpu_layers'] = loaded['n_gpu_layers']
                        log_message(f"CHAT_INTERFACE: Migrated n_gpu_layers={loaded['n_gpu_layers']} to llama_server_gpu_layers")
                # Ensure left pane lock defaults to ON at launch
                settings['conv_locked'] = True
                log_message("CHAT_INTERFACE: Backend settings loaded")
                return settings
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to load backend settings: {e}")

        return settings

    def load_advanced_settings(self):
        """Load advanced settings from advanced_settings.json"""
        settings_file = Path(__file__).parent.parent / "advanced_settings.json"

        if settings_file.exists():
            try:
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    log_message("CHAT_INTERFACE: Advanced settings loaded")
                    return settings
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to load advanced settings: {e}")

        # Return defaults (all disabled)
        return {
            'format_translation': {'enabled': False},
            'json_repair': {'enabled': False},
            'schema_validation': {'enabled': False},
            'tool_orchestrator': {'enabled': False},
            'intelligent_routing': {'enabled': False},
            'resource_management': {'profile': 'balanced'},
            'time_slicing': {'enabled': False},
            'context_scoring': {'enabled': False},
            'pre_rag_optimizer': {'enabled': False},
            'verification': {'enabled': False},
            'quality_assurance': {'enabled': False}
        }

    def initialize_advanced_components(self):
        """Initialize advanced OpenCode components based on settings"""
        if self.is_standard_mode:
            log_message("CHAT_INTERFACE: Standard mode is active, bypassing advanced component initialization.")
            self.format_translator = None
            self.json_fixer_enabled = False
            self.schema_validator = None
            self.tool_orchestrator = None
            self.router = None
            self.time_slicer = None
            self.context_scorer = None
            self.pre_rag_optimizer = None
            self.verification_engine = None
            self.quality_assurance = None
            self.adaptive_workflow = None
            self.agentic_project = None
            self.workflow_optimizer = None
            self.project_store = None
            self.session_manager_adv = None
            self.master_quality = None
            self.quality_recovery = None
            self.performance_benchmark = None
            self.rag_feedback = None
            self.complexity_analyzer = None
            self.hardening_manager = None
            self.atomic_writer = None
            self.confirmation_gates_standalone = None
            self.model_optimizer = None
            self.model_selector = None
            self.quant_manager = None
            self.mvco_engine = None
            self.auto_policy = None
            self.command_policy = None
            self.mcp_integration = None
            self.mcp_server = None
            self.langchain_adapter = None
            self.instant_hooks = None
            self.version_manager = None
            self.ollama_direct = None
            return

        # Add path for OpenCode modules
        sys.path.insert(0, str(Path(__file__).parent.parent / "site-packages"))

        # Format Translator
        if self.advanced_settings.get('format_translation', {}).get('enabled', False):
            try:
                from opencode.format_translator import FormatTranslator
                self.format_translator = FormatTranslator()
                log_message("CHAT_INTERFACE: FormatTranslator initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: FormatTranslator enabled with settings: " +
                               json.dumps(self.advanced_settings.get('format_translation', {})))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize FormatTranslator: {e}")
                self.format_translator = None
        else:
            self.format_translator = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: FormatTranslator disabled")

        # JSON Fixer
        if self.advanced_settings.get('json_repair', {}).get('enabled', False):
            try:
                from opencode.json_fixer import smart_json_parse, parse_partial_json
                self.json_fixer_enabled = True
                self.smart_json_parse = smart_json_parse
                self.parse_partial_json = parse_partial_json
                log_message("CHAT_INTERFACE: JSON Fixer initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: JSON Fixer enabled with aggressiveness: " +
                               self.advanced_settings.get('json_repair', {}).get('aggressiveness', 'medium'))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize JSON Fixer: {e}")
                self.json_fixer_enabled = False
        else:
            self.json_fixer_enabled = False
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: JSON Fixer disabled")

        # Schema Validator
        if self.advanced_settings.get('schema_validation', {}).get('enabled', False):
            try:
                from opencode.tool_schema_validator import ToolSchemaValidator
                self.schema_validator = ToolSchemaValidator()
                log_message("CHAT_INTERFACE: Schema Validator initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: Schema Validator enabled with mode: " +
                               self.advanced_settings.get('schema_validation', {}).get('mode', 'permissive'))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Schema Validator: {e}")
                self.schema_validator = None
        else:
            self.schema_validator = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: Schema Validator disabled")

        # Tool Orchestrator
        if self.advanced_settings.get('tool_orchestrator', {}).get('enabled', False) or self._orchestrator_required:
            try:
                from opencode.tool_orchestrator import AdvancedToolOrchestrator
                from opencode.config import Config
                config = Config()
                # Tool manager will be the tool_executor
                self.tool_orchestrator = AdvancedToolOrchestrator(self.tool_executor, config)
                log_message("CHAT_INTERFACE: Tool Orchestrator initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: Tool Orchestrator enabled with risk_assessment: " +
                               str(self.advanced_settings.get('tool_orchestrator', {}).get('risk_assessment', True)))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Tool Orchestrator: {e}")
                self.tool_orchestrator = None
        else:
            self.tool_orchestrator = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: Tool Orchestrator disabled")

        if self._orchestrator_required and not self.tool_orchestrator:
            raise RuntimeError(
                "Tool Orchestrator enforcement active but initializer failed. "
                "Set FEATURE_ORCHESTRATOR_ENFORCE=0 to bypass."
            )

        # Intelligent Router
        if self.advanced_settings.get('intelligent_routing', {}).get('enabled', False):
            try:
                from opencode.router import Router
                self.router = Router()
                log_message("CHAT_INTERFACE: Intelligent Router initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: Router enabled with confidence threshold: " +
                               str(self.advanced_settings.get('intelligent_routing', {}).get('confidence_threshold', 0.7)))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Router: {e}")
                self.router = None
        else:
            self.router = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: Intelligent Router disabled")

        # Resource Management (applied to tool executor)
        resource_profile = self.advanced_settings.get('resource_management', {}).get('profile', 'balanced')
        try:
            from opencode.runtime_profiles import resource_manager
            profile = resource_manager.get_profile_by_name(resource_profile)

            # Apply profile constraints to tool executor if it exists
            if self.tool_executor and hasattr(self.tool_executor, 'set_resource_limits'):
                limits = {
                    'num_threads': profile.num_threads,
                    'max_tokens': profile.max_tokens,
                    'memory_limit_mb': profile.memory_limit_mb if hasattr(profile, 'memory_limit_mb') else None
                }
                self.tool_executor.set_resource_limits(limits)
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Applied resource profile '{resource_profile}' to tool executor: {limits}")
            else:
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Resource profile '{resource_profile}' loaded but not applied (tool executor doesn't support limits)")
        except Exception as e:
            if self.backend_settings.get('enable_debug_logging', False):
                log_message(f"DEBUG: Failed to apply resource profile: {e}")

        # Time Slicer
        if self.advanced_settings.get('time_slicing', {}).get('enabled', False):
            try:
                from opencode.time_slicer import TimeSlicedGenerator, TimeBudget
                from opencode.runtime_profiles import resource_manager
                profile = resource_manager.get_profile_by_name(resource_profile)
                self.time_slicer = TimeSlicedGenerator(profile)
                log_message("CHAT_INTERFACE: Time Slicer initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: Time Slicer enabled with tokens_per_slice: " +
                               str(self.advanced_settings.get('time_slicing', {}).get('tokens_per_slice', 32)))
                    log_message("DEBUG: Note - Time Slicer requires streaming mode (stream=True) to function")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Time Slicer: {e}")
                self.time_slicer = None
        else:
            self.time_slicer = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: Time Slicer disabled")

        # Context Scorer
        if self.advanced_settings.get('context_scoring', {}).get('enabled', False):
            try:
                from opencode.context_scorer import AdaptiveContextScorer
                from opencode.config import Config
                config = Config()
                self.context_scorer = AdaptiveContextScorer(config)
                log_message("CHAT_INTERFACE: Context Scorer initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: Context Scorer enabled with memory_threshold: " +
                               str(self.advanced_settings.get('context_scoring', {}).get('memory_threshold_percent', 85)))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Context Scorer: {e}")
                self.context_scorer = None
        else:
            self.context_scorer = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: Context Scorer disabled")

        # Pre-RAG Optimizer
        if self.advanced_settings.get('pre_rag_optimizer', {}).get('enabled', False):
            try:
                from opencode.pre_rag_optimizer import PreRAGOptimizer
                from opencode.config import Config
                config = Config()
                self.pre_rag_optimizer = PreRAGOptimizer(config)
                log_message("CHAT_INTERFACE: Pre-RAG Optimizer initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    optimizations = self.advanced_settings.get('pre_rag_optimizer', {}).get('optimizations', {})
                    log_message("DEBUG: Pre-RAG Optimizer enabled with optimizations: " + json.dumps(optimizations))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Pre-RAG Optimizer: {e}")
                self.pre_rag_optimizer = None
        else:
            self.pre_rag_optimizer = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: Pre-RAG Optimizer disabled")

        # Verification Engine
        verification_config = self.advanced_settings.get('verification', {}) or {}
        verification_enabled = bool(verification_config.get('enabled', False)) or self._verification_required
        if verification_enabled:
            try:
                from opencode.verification_engine import VerificationEngine
                self.verification_engine = VerificationEngine()
                log_message("CHAT_INTERFACE: Verification Engine initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: Verification Engine enabled with strictness: " +
                               verification_config.get('strictness', 'medium'))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Verification Engine: {e}")
                self.verification_engine = None
                if self._verification_required:
                    raise
        else:
            self.verification_engine = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: Verification Engine disabled")

        # Quality Assurance
        if self.advanced_settings.get('quality_assurance', {}).get('enabled', False):
            try:
                from opencode.quality_integration import QualityIntegration
                self.quality_assurance = QualityIntegration()
                log_message("CHAT_INTERFACE: Quality Assurance initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: Quality Assurance enabled with threshold: " +
                               str(self.advanced_settings.get('quality_assurance', {}).get('threshold', 0.8)))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Quality Assurance: {e}")
                self.quality_assurance = None
        else:
            self.quality_assurance = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: Quality Assurance disabled")

        # ========== Additional 26 Systems ==========

        # Adaptive Workflow Engine
        if self.advanced_settings.get('adaptive_workflow', {}).get('enabled', False):
            try:
                from opencode.adaptive_workflow_engine import AdaptiveWorkflowEngine
                self.adaptive_workflow = AdaptiveWorkflowEngine()
                log_message("CHAT_INTERFACE: Adaptive Workflow Engine initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Adaptive Workflow enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Adaptive Workflow: {e}")
                self.adaptive_workflow = None
        else:
            self.adaptive_workflow = None

        # Agentic Project System (respect per-session override if present)
        agentic_enabled = None
        try:
            ov = getattr(self, 'agentic_project_override', None)
            agentic_enabled = (ov if ov is not None else self.advanced_settings.get('agentic_project', {}).get('enabled', False))
        except Exception:
            agentic_enabled = self.advanced_settings.get('agentic_project', {}).get('enabled', False)
        if agentic_enabled:
            try:
                from opencode.agentic_project_system import AgenticProjectSystem
                self.agentic_project = AgenticProjectSystem()
                log_message("CHAT_INTERFACE: Agentic Project System initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Agentic Project enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Agentic Project: {e}")
                self.agentic_project = None
        else:
            self.agentic_project = None

        # Workflow Optimizer
        if self.advanced_settings.get('workflow_optimizer', {}).get('enabled', False):
            try:
                from opencode.workflow_optimizer import WorkflowOptimizer
                self.workflow_optimizer = WorkflowOptimizer()
                log_message("CHAT_INTERFACE: Workflow Optimizer initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Workflow Optimizer enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Workflow Optimizer: {e}")
                self.workflow_optimizer = None
        else:
            self.workflow_optimizer = None

        # Project Store
        if self.advanced_settings.get('project_store', {}).get('enabled', False):
            try:
                from opencode.project_store import ProjectStore
                self.project_store = ProjectStore()
                log_message("CHAT_INTERFACE: Project Store initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Project Store enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Project Store: {e}")
                self.project_store = None
        else:
            self.project_store = None

        # Session Manager
        if self.advanced_settings.get('session_manager', {}).get('enabled', False):
            try:
                from opencode.session_manager import SessionManager
                self.session_manager_adv = SessionManager()
                log_message("CHAT_INTERFACE: Session Manager initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Session Manager enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Session Manager: {e}")
                self.session_manager_adv = None
        else:
            self.session_manager_adv = None

        # Master Quality System
        if self.advanced_settings.get('master_quality', {}).get('enabled', False):
            try:
                from opencode.master_quality_system import MasterQualitySystem
                self.master_quality = MasterQualitySystem()
                log_message("CHAT_INTERFACE: Master Quality System initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Master Quality System enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Master Quality: {e}")
                self.master_quality = None
        else:
            self.master_quality = None

        # Quality Recovery Engine
        if self.advanced_settings.get('quality_recovery', {}).get('enabled', False):
            try:
                from opencode.quality_recovery_engine import QualityRecoveryEngine
                self.quality_recovery = QualityRecoveryEngine()
                log_message("CHAT_INTERFACE: Quality Recovery Engine initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Quality Recovery enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Quality Recovery: {e}")
                self.quality_recovery = None
        else:
            self.quality_recovery = None

        # Performance Benchmark
        if self.advanced_settings.get('performance_benchmark', {}).get('enabled', False):
            try:
                from opencode.performance_benchmark_system import PerformanceBenchmarkSystem
                self.performance_benchmark = PerformanceBenchmarkSystem()
                log_message("CHAT_INTERFACE: Performance Benchmark initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Performance Benchmark enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Performance Benchmark: {e}")
                self.performance_benchmark = None
        else:
            self.performance_benchmark = None

        # RAG Feedback Engine
        if self.advanced_settings.get('rag_feedback', {}).get('enabled', False):
            try:
                from opencode.rag_feedback_engine import RAGFeedbackEngine
                self.rag_feedback = RAGFeedbackEngine()
                log_message("CHAT_INTERFACE: RAG Feedback Engine initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: RAG Feedback enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize RAG Feedback: {e}")
                self.rag_feedback = None
        else:
            self.rag_feedback = None

        # Complexity Analyzer
        if self.advanced_settings.get('complexity_analyzer', {}).get('enabled', False):
            try:
                from opencode.complexity_analyzer import ComplexityAnalyzer
                self.complexity_analyzer = ComplexityAnalyzer()
                log_message("CHAT_INTERFACE: Complexity Analyzer initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Complexity Analyzer enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Complexity Analyzer: {e}")
                self.complexity_analyzer = None
        else:
            self.complexity_analyzer = None

        # Hardening Manager
        if self.advanced_settings.get('hardening_manager', {}).get('enabled', False):
            try:
                from opencode.hardening_manager import HardeningManager
                self.hardening_manager = HardeningManager()
                log_message("CHAT_INTERFACE: Hardening Manager initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Hardening Manager enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Hardening Manager: {e}")
                self.hardening_manager = None
        else:
            self.hardening_manager = None

        # Atomic Writer
        if self.advanced_settings.get('atomic_writer', {}).get('enabled', False):
            try:
                from opencode.atomic_writer import AtomicWriter
                self.atomic_writer = AtomicWriter()
                log_message("CHAT_INTERFACE: Atomic Writer initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Atomic Writer enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Atomic Writer: {e}")
                self.atomic_writer = None
        else:
            self.atomic_writer = None

        # Confirmation Gates (standalone)
        if self.advanced_settings.get('confirmation_gates', {}).get('enabled', False):
            try:
                from opencode.confirmation_gates import ConfirmationGates
                self.confirmation_gates_standalone = ConfirmationGates()
                log_message("CHAT_INTERFACE: Confirmation Gates initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Confirmation Gates enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Confirmation Gates: {e}")
                self.confirmation_gates_standalone = None
        else:
            self.confirmation_gates_standalone = None

        # Model Optimizer
        if self.advanced_settings.get('model_optimizer', {}).get('enabled', False):
            try:
                from opencode.model_optimizer import ModelOptimizer
                self.model_optimizer = ModelOptimizer()
                log_message("CHAT_INTERFACE: Model Optimizer initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Model Optimizer enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Model Optimizer: {e}")
                self.model_optimizer = None
        else:
            self.model_optimizer = None

        # Model Selector
        if self.advanced_settings.get('model_selector', {}).get('enabled', False):
            try:
                from opencode.model_selector import ModelSelector
                self.model_selector = ModelSelector()
                log_message("CHAT_INTERFACE: Model Selector initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Model Selector enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Model Selector: {e}")
                self.model_selector = None
        else:
            self.model_selector = None

        # Quant Manager
        if self.advanced_settings.get('quant_manager', {}).get('enabled', False):
            try:
                from opencode.quant_manager import QuantManager
                self.quant_manager = QuantManager()
                log_message("CHAT_INTERFACE: Quant Manager initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Quant Manager enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Quant Manager: {e}")
                self.quant_manager = None
        else:
            self.quant_manager = None

        # MVCO Engine
        if self.advanced_settings.get('mvco_engine', {}).get('enabled', False):
            try:
                from opencode.mvco_engine import MVCOEngine
                self.mvco_engine = MVCOEngine()
                log_message("CHAT_INTERFACE: MVCO Engine initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: MVCO Engine enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize MVCO Engine: {e}")
                self.mvco_engine = None
        else:
            self.mvco_engine = None

        # Auto Policy
        if self.advanced_settings.get('auto_policy', {}).get('enabled', False):
            try:
                from opencode.auto_policy import AutoPolicy
                self.auto_policy = AutoPolicy()
                log_message("CHAT_INTERFACE: Auto Policy initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Auto Policy enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Auto Policy: {e}")
                self.auto_policy = None
        else:
            self.auto_policy = None

        # Command Policy
        if self.advanced_settings.get('command_policy', {}).get('enabled', False):
            try:
                from opencode.command_policy import CommandPolicy
                self.command_policy = CommandPolicy()
                log_message("CHAT_INTERFACE: Command Policy initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Command Policy enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Command Policy: {e}")
                self.command_policy = None
        else:
            self.command_policy = None

        # MCP Integration
        if self.advanced_settings.get('mcp_integration', {}).get('enabled', False):
            try:
                from opencode.mcp_integration import MCPIntegration
                self.mcp_integration = MCPIntegration()
                log_message("CHAT_INTERFACE: MCP Integration initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: MCP Integration enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize MCP Integration: {e}")
                self.mcp_integration = None
        else:
            self.mcp_integration = None

        # MCP Server
        if self.advanced_settings.get('mcp_server', {}).get('enabled', False):
            try:
                from opencode.mcp_server_wrapper import MCPServerWrapper
                self.mcp_server = MCPServerWrapper()
                log_message("CHAT_INTERFACE: MCP Server initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: MCP Server enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize MCP Server: {e}")
                self.mcp_server = None
        else:
            self.mcp_server = None

        # LangChain Adapter
        if self.advanced_settings.get('langchain_adapter', {}).get('enabled', False):
            try:
                adapter_type = self.advanced_settings.get('langchain_adapter', {}).get('adapter_type', 'simple')
                if adapter_type == 'simple':
                    from opencode.langchain_adapter_simple import LangChainAdapterSimple
                    self.langchain_adapter = LangChainAdapterSimple()
                else:
                    from opencode.langchain_adapter import LangChainAdapter
                    self.langchain_adapter = LangChainAdapter()
                log_message(f"CHAT_INTERFACE: LangChain Adapter ({adapter_type}) initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: LangChain Adapter enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize LangChain Adapter: {e}")
                self.langchain_adapter = None
        else:
            self.langchain_adapter = None

        # Instant Hooks Engine
        if self.advanced_settings.get('instant_hooks', {}).get('enabled', False):
            try:
                from opencode.instant_hook_engine import InstantHookEngine
                self.instant_hooks = InstantHookEngine()
                log_message("CHAT_INTERFACE: Instant Hook Engine initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Instant Hooks enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Instant Hooks: {e}")
                self.instant_hooks = None
        else:
            self.instant_hooks = None

        # Version Manager
        if self.advanced_settings.get('version_manager', {}).get('enabled', False):
            try:
                from opencode.version_manager import VersionManager
                self.version_manager = VersionManager()
                log_message("CHAT_INTERFACE: Version Manager initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Version Manager enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Version Manager: {e}")
                self.version_manager = None
        else:
            self.version_manager = None

        # Ollama Direct Client
        if self.advanced_settings.get('ollama_direct', {}).get('enabled', False):
            try:
                from opencode.ollama_client import OllamaClient
                self.ollama_direct = OllamaClient()
                log_message("CHAT_INTERFACE: Ollama Direct Client initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Ollama Direct Client enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Ollama Direct: {e}")
                self.ollama_direct = None
        else:
            self.ollama_direct = None

    def _ensure_prompt_schema_dirs(self):
        """Ensure system_prompts and tool_schemas_configs directories exist"""
        self.system_prompts_dir.mkdir(exist_ok=True)
        self.tool_schemas_dir.mkdir(exist_ok=True)

        # Create default system prompt if doesn't exist
        default_prompt_file = self.system_prompts_dir / "default.txt"
        if not default_prompt_file.exists():
            with open(default_prompt_file, 'w') as f:
                f.write("You are a helpful AI assistant with access to various tools. Use them when appropriate to help the user.")

        # Create default tool schema config if doesn't exist
        default_schema_file = self.tool_schemas_dir / "default.json"
        if not default_schema_file.exists():
            with open(default_schema_file, 'w') as f:
                json.dump({"enabled_tools": "all", "description": "Default - All tools enabled"}, f, indent=2)

    def select_system_prompt(self):
        """Open dialog to select and edit system prompt"""
        from tkinter import messagebox

        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("System Prompt Manager")
        dialog.geometry("900x700")
        dialog.configure(bg='#2b2b2b')

        # Make modal
        dialog.transient(self.root)
        dialog.grab_set()

        # Main layout
        dialog.columnconfigure(0, weight=0)  # List on left
        dialog.columnconfigure(1, weight=1)  # Editor on right
        dialog.rowconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=0)

        # Left panel - Prompt list
        left_frame = ttk.Frame(dialog, style='Category.TFrame')
        left_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=(10, 5), pady=10)

        ttk.Label(
            left_frame,
            text="Available Prompts",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(pady=(0, 5))

        # Listbox for prompts
        list_frame = ttk.Frame(left_frame, style='Category.TFrame')
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        prompt_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            bg='#1e1e1e',
            fg='#ffffff',
            selectbackground='#61dafb',
            font=("Arial", 10),
            width=25
        )
        prompt_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=prompt_listbox.yview)

        # Load prompts (prefer central Training directories)
        try:
            import config as C
            prompts = list(C.list_system_prompts())
        except Exception:
            prompts = sorted([f.stem for f in self.system_prompts_dir.glob("*.txt")])
        for prompt in prompts:
            prompt_listbox.insert(tk.END, prompt)
            if prompt == self.current_system_prompt:
                prompt_listbox.selection_set(prompts.index(prompt))

        # Right panel - Editor
        right_frame = ttk.Frame(dialog, style='Category.TFrame')
        right_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=(5, 10), pady=10)
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)

        # Editor header
        header_frame = ttk.Frame(right_frame, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 5))
        header_frame.columnconfigure(0, weight=1)

        prompt_name_label = ttk.Label(
            header_frame,
            text="Select a prompt to view/edit",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        )
        prompt_name_label.grid(row=0, column=0, sticky=tk.W)

        # Text editor
        editor = scrolledtext.ScrolledText(
            right_frame,
            wrap=tk.WORD,
            font=("Courier", 10),
            bg='#1e1e1e',
            fg='#ffffff',
            insertbackground='#61dafb'
        )
        editor.grid(row=1, column=0, sticky=tk.NSEW)

        # Track current selection
        current_prompt_name = [None]
        modified = [False]

        def _resolve_prompt_path(name: str):
            try:
                import config as C
                sp = C.SEMANTIC_DATA_DIR / f"system_prompt_{name}.json"
                if sp.exists():
                    return sp
                for p in C.PROMPTS_DIR.rglob('*.json'):
                    if p.stem == name:
                        return p
                pb = C.PROMPTBOX_DIR / f"{name}.txt"
                if pb.exists():
                    return pb
                pb.parent.mkdir(parents=True, exist_ok=True)
                return pb
            except Exception:
                return self.system_prompts_dir / f"{name}.txt"

        def load_prompt(event=None):
            """Load selected prompt into editor"""
            selection = prompt_listbox.curselection()
            if not selection:
                return

            # Check if current prompt was modified
            if modified[0] and current_prompt_name[0]:
                if messagebox.askyesno(
                    "Unsaved Changes",
                    f"You have unsaved changes to '{current_prompt_name[0]}'.\n\nSave before switching?"
                ):
                    save_prompt()

            prompt_name = prompt_listbox.get(selection[0])
            current_prompt_name[0] = prompt_name
            modified[0] = False

            # Prefer central loader
            content = None
            try:
                import config as C
                data = C.load_system_prompt(prompt_name)
                if isinstance(data, dict) and 'prompt' in data:
                    content = str(data.get('prompt') or '')
                else:
                    content = str(data)
            except Exception:
                pass
            if content is None:
                prompt_file = self.system_prompts_dir / f"{prompt_name}.txt"
                if prompt_file.exists():
                    with open(prompt_file, 'r') as f:
                        content = f.read()
            if content is None:
                content = ''
            editor.delete(1.0, tk.END)
            editor.insert(1.0, content)
            prompt_name_label.config(text=f"📝 {prompt_name}")

        def on_text_change(event=None):
            """Mark as modified when text changes"""
            modified[0] = True
            if current_prompt_name[0]:
                prompt_name_label.config(text=f"📝 {current_prompt_name[0]} *")

        editor.bind('<KeyRelease>', on_text_change)
        prompt_listbox.bind('<<ListboxSelect>>', load_prompt)

        # Load initially selected prompt
        if prompt_listbox.curselection():
            load_prompt()

        # Bottom buttons
        button_frame = ttk.Frame(dialog, style='Category.TFrame')
        button_frame.grid(row=1, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=(0, 10))

        def save_prompt():
            """Save current prompt"""
            if not current_prompt_name[0]:
                messagebox.showwarning("No Selection", "Please select a prompt first")
                return

            content = editor.get(1.0, tk.END).strip()
            if not content:
                messagebox.showwarning("Empty Content", "Prompt content cannot be empty")
                return

            prompt_file = _resolve_prompt_path(current_prompt_name[0])
            try:
                with open(prompt_file, 'w') as f:
                    f.write(content)
            except Exception:
                with open(self.system_prompts_dir / f"{current_prompt_name[0]}.txt", 'w') as f:
                    f.write(content)

            modified[0] = False
            prompt_name_label.config(text=f"📝 {current_prompt_name[0]}")
            messagebox.showinfo("Saved", f"Prompt '{current_prompt_name[0]}' saved successfully")

        def new_prompt():
            """Create new prompt"""
            from tkinter import simpledialog
            name = simpledialog.askstring("New Prompt", "Enter prompt name:")
            if name:
                # Clean name
                name = "".join(c for c in name if c.isalnum() or c in ('_', '-'))
                if not name:
                    messagebox.showerror("Invalid Name", "Prompt name must contain alphanumeric characters")
                    return

                prompt_file = _resolve_prompt_path(name)
                if prompt_file.exists():
                    messagebox.showerror("Exists", f"Prompt '{name}' already exists")
                    return

                # Create empty prompt
                try:
                    with open(prompt_file, 'w') as f:
                        f.write("You are a helpful AI assistant.")
                except Exception:
                    with open(self.system_prompts_dir / f"{name}.txt", 'w') as f:
                        f.write("You are a helpful AI assistant.")

                # Reload list
                prompt_listbox.insert(tk.END, name)
                prompt_listbox.selection_clear(0, tk.END)
                prompt_listbox.selection_set(tk.END)
                load_prompt()

        def delete_prompt():
            """Delete selected prompt"""
            if not current_prompt_name[0]:
                messagebox.showwarning("No Selection", "Please select a prompt first")
                return

            if current_prompt_name[0] == "default":
                messagebox.showerror("Cannot Delete", "Cannot delete the default prompt")
                return

            if messagebox.askyesno(
                "Confirm Delete",
                f"Are you sure you want to delete '{current_prompt_name[0]}'?"
            ):
                try:
                    _resolve_prompt_path(current_prompt_name[0]).unlink(missing_ok=True)
                except Exception:
                    (self.system_prompts_dir / f"{current_prompt_name[0]}.txt").unlink(missing_ok=True)

                # Reload list
                selection = prompt_listbox.curselection()
                prompt_listbox.delete(selection[0])
                current_prompt_name[0] = None
                modified[0] = False
                editor.delete(1.0, tk.END)
                prompt_name_label.config(text="Select a prompt to view/edit")

        def select_and_apply():
            """Select prompt and apply it"""
            if bool(self._sp_off_var.get()):
                self.current_system_prompt = None
                self.add_message("system", "✓ System prompt set to Off")
            else:
                if not current_prompt_name[0]:
                    messagebox.showwarning("No Selection", "Please select a prompt first")
                    return
                # Save if modified
                if modified[0]:
                    save_prompt()
                self.current_system_prompt = current_prompt_name[0]
                self.add_message("system", f"✓ Loaded system prompt: {current_prompt_name[0]}")
                log_message(f"CHAT_INTERFACE: Loaded system prompt: {current_prompt_name[0]}")

            # Remount model to apply new prompt
            if self.is_mounted:
                self.dismount_model()
                self.root.after(500, self.mount_model)

            dialog.destroy()

        # Buttons
        ttk.Button(
            button_frame,
            text="💾 Save",
            command=save_prompt,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="➕ New",
            command=new_prompt,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="🗑️ Delete",
            command=delete_prompt,
            style='Select.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="✓ Select & Apply",
            command=select_and_apply,
            style='Action.TButton'
        ).pack(side=tk.RIGHT, padx=5)

        ttk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            style='Select.TButton'
        ).pack(side=tk.RIGHT, padx=5)

    def select_tool_schema(self):
        """Open dialog to select and edit tool schema configuration"""
        from tkinter import messagebox

        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Tool Schema Manager")
        dialog.geometry("900x700")
        dialog.configure(bg='#2b2b2b')

        # Make modal
        dialog.transient(self.root)
        dialog.grab_set()

        # Main layout
        dialog.columnconfigure(0, weight=0)  # List on left
        dialog.columnconfigure(1, weight=1)  # Editor on right
        dialog.rowconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=0)

        # Left panel - Schema list
        left_frame = ttk.Frame(dialog, style='Category.TFrame')
        left_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=(10, 5), pady=10)

        ttk.Label(
            left_frame,
            text="Available Schemas",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(pady=(0, 5))

        # Listbox for schemas
        list_frame = ttk.Frame(left_frame, style='Category.TFrame')
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        schema_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            bg='#1e1e1e',
            fg='#ffffff',
            selectbackground='#61dafb',
            font=("Arial", 10),
            width=25
        )
        schema_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=schema_listbox.yview)

        # Load schemas (prefer central Training directories)
        try:
            import config as C
            schemas = list(C.list_tool_schemas())
        except Exception:
            schemas = sorted([f.stem for f in self.tool_schemas_dir.glob("*.json")])
        for schema in schemas:
            schema_listbox.insert(tk.END, schema)
            if schema == self.current_tool_schema:
                schema_listbox.selection_set(schemas.index(schema))

        # Right panel - Editor
        right_frame = ttk.Frame(dialog, style='Category.TFrame')
        right_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=(5, 10), pady=10)
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)

        # Editor header
        header_frame = ttk.Frame(right_frame, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 5))
        header_frame.columnconfigure(0, weight=1)

        schema_name_label = ttk.Label(
            header_frame,
            text="Select a schema to view/edit",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        )
        schema_name_label.grid(row=0, column=0, sticky=tk.W)

        # Text editor
        editor = scrolledtext.ScrolledText(
            right_frame,
            wrap=tk.WORD,
            font=("Courier", 10),
            bg='#1e1e1e',
            fg='#ffffff',
            insertbackground='#61dafb'
        )
        editor.grid(row=1, column=0, sticky=tk.NSEW)

        # Track current selection
        current_schema_name = [None]
        modified = [False]

        def load_schema(event=None):
            """Load selected schema into editor"""
            selection = schema_listbox.curselection()
            if not selection:
                return

            # Check if current schema was modified
            if modified[0] and current_schema_name[0]:
                if messagebox.askyesno(
                    "Unsaved Changes",
                    f"You have unsaved changes to '{current_schema_name[0]}'.\n\nSave before switching?"
                ):
                    save_schema()

            schema_name = schema_listbox.get(selection[0])
            current_schema_name[0] = schema_name
            modified[0] = False

            # Prefer central loader
            content = None
            try:
                import config as C
                data = C.load_tool_schema(schema_name)
                content = json.dumps(data, indent=2)
            except Exception:
                pass
            if content is None:
                schema_file = self.tool_schemas_dir / f"{schema_name}.json"
                if schema_file.exists():
                    with open(schema_file, 'r') as f:
                        content = f.read()
            if content is None:
                content = '{\n  "enabled_tools": "all"\n}'
            editor.delete(1.0, tk.END)
            editor.insert(1.0, content)
            schema_name_label.config(text=f"🔧 {schema_name}")

        def on_text_change(event=None):
            """Mark as modified when text changes"""
            modified[0] = True
            if current_schema_name[0]:
                schema_name_label.config(text=f"🔧 {current_schema_name[0]} *")

        editor.bind('<KeyRelease>', on_text_change)
        schema_listbox.bind('<<ListboxSelect>>', load_schema)

        # Load initially selected schema
        if schema_listbox.curselection():
            load_schema()

        # Bottom buttons
        button_frame = ttk.Frame(dialog, style='Category.TFrame')
        button_frame.grid(row=1, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=(0, 10))

        # Helper to resolve central schema path
        def _resolve_schema_path(name: str):
            try:
                import config as C
                sp = C.SEMANTIC_DATA_DIR / f"tool_schema_{name}.json"
                if sp.exists():
                    return sp
                for p in C.SCHEMAS_DIR.rglob('*.json'):
                    if p.stem == name:
                        return p
                C.SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
                return C.SCHEMAS_DIR / f"{name}.json"
            except Exception:
                return self.tool_schemas_dir / f"{name}.json"

        def save_schema():
            """Save current schema"""
            if not current_schema_name[0]:
                messagebox.showwarning("No Selection", "Please select a schema first")
                return

            content = editor.get(1.0, tk.END).strip()
            if not content:
                messagebox.showwarning("Empty Content", "Schema content cannot be empty")
                return

            # Validate JSON
            try:
                schema_data = json.loads(content)
            except json.JSONDecodeError as e:
                messagebox.showerror("Invalid JSON", f"JSON validation failed:\n{str(e)}")
                return

            # Validate schema structure
            if "enabled_tools" not in schema_data:
                messagebox.showerror("Invalid Schema", "Schema must contain 'enabled_tools' field")
                return

            schema_file = _resolve_schema_path(current_schema_name[0])
            try:
                with open(schema_file, 'w') as f:
                    json.dump(schema_data, f, indent=2)
            except Exception:
                with open(self.tool_schemas_dir / f"{current_schema_name[0]}.json", 'w') as f:
                    json.dump(schema_data, f, indent=2)

            modified[0] = False
            schema_name_label.config(text=f"🔧 {current_schema_name[0]}")
            messagebox.showinfo("Saved", f"Schema '{current_schema_name[0]}' saved successfully")

        def new_schema():
            """Create new schema"""
            from tkinter import simpledialog
            name = simpledialog.askstring("New Schema", "Enter schema name:")
            if name:
                # Clean name
                name = "".join(c for c in name if c.isalnum() or c in ('_', '-'))
                if not name:
                    messagebox.showerror("Invalid Name", "Schema name must contain alphanumeric characters")
                    return

                schema_file = _resolve_schema_path(name)
                if schema_file.exists():
                    messagebox.showerror("Exists", f"Schema '{name}' already exists")
                    return

                # Create default schema (central)
                default_schema = {
                    "enabled_tools": "all",
                    "description": f"Custom schema: {name}"
                }
                try:
                    with open(schema_file, 'w') as f:
                        json.dump(default_schema, f, indent=2)
                except Exception:
                    with open(self.tool_schemas_dir / f"{name}.json", 'w') as f:
                        json.dump(default_schema, f, indent=2)

                # Reload list
                schema_listbox.insert(tk.END, name)
                schema_listbox.selection_clear(0, tk.END)
                schema_listbox.selection_set(tk.END)
                load_schema()

        def delete_schema():
            """Delete selected schema"""
            if not current_schema_name[0]:
                messagebox.showwarning("No Selection", "Please select a schema first")
                return

            if current_schema_name[0] == "default":
                messagebox.showerror("Cannot Delete", "Cannot delete the default schema")
                return

            if messagebox.askyesno(
                "Confirm Delete",
                f"Are you sure you want to delete '{current_schema_name[0]}'?"
            ):
                try:
                    _resolve_schema_path(current_schema_name[0]).unlink(missing_ok=True)
                except Exception:
                    (self.tool_schemas_dir / f"{current_schema_name[0]}.json").unlink(missing_ok=True)

                # Reload list
                selection = schema_listbox.curselection()
                schema_listbox.delete(selection[0])
                current_schema_name[0] = None
                modified[0] = False
                editor.delete(1.0, tk.END)
                schema_name_label.config(text="Select a schema to view/edit")

        # Off toggle + Default setter controls
        ctl_row = ttk.Frame(dialog, style='Category.TFrame')
        ctl_row.grid(row=1, column=0, columnspan=2, sticky=tk.EW, padx=10)
        self._schema_off_var = tk.BooleanVar(value=(self.current_tool_schema in (None, '', 'None')))
        ttk.Checkbutton(ctl_row, text='Off (no tool schema)', variable=self._schema_off_var, style='TCheckbutton').pack(side=tk.LEFT)
        def _set_default_schema():
            val = None if self._schema_off_var.get() else (current_schema_name[0] or (schema_listbox.get(schema_listbox.curselection()[0]) if schema_listbox.curselection() else 'default'))
            try:
                self._save_backend_setting('default_tool_schema', val)
                self.backend_settings['default_tool_schema'] = val
                self.add_message('system', f"Default tool schema set to: {val or 'Off'}")
            except Exception:
                pass
        ttk.Button(ctl_row, text='Set as Default', style='Select.TButton', command=_set_default_schema).pack(side=tk.RIGHT)

        def select_and_apply():
            """Select schema and apply it"""
            if bool(self._schema_off_var.get()):
                self.current_tool_schema = None
                self.add_message("system", "✓ Tool schema set to Off")
            else:
                if not current_schema_name[0]:
                    messagebox.showwarning("No Selection", "Please select a schema first")
                    return
                # Save if modified
                if modified[0]:
                    save_schema()
                self.current_tool_schema = current_schema_name[0]
                self.add_message("system", f"✓ Loaded tool schema: {current_schema_name[0]}")
                log_message(f"CHAT_INTERFACE: Loaded tool schema: {current_schema_name[0]}")

            # Reload tool schemas
            self.tool_executor.initialize_tools()

            # Remount model to apply new schema
            if self.is_mounted:
                self.dismount_model()
                self.root.after(500, self.mount_model)

            dialog.destroy()

        # Buttons
        ttk.Button(
            button_frame,
            text="💾 Save",
            command=save_schema,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="➕ New",
            command=new_schema,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="🗑️ Delete",
            command=delete_schema,
            style='Select.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="✓ Select & Apply",
            command=select_and_apply,
            style='Action.TButton'
        ).pack(side=tk.RIGHT, padx=5)

        ttk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            style='Select.TButton'
        ).pack(side=tk.RIGHT, padx=5)

    def get_current_system_prompt(self):
        """Get the current system prompt content.

        Prefer centrally managed prompts (Training tab locations) via config.
        Falls back to local custom_code_tab prompt files.
        """
        # Off/None → no system message
        if not self.current_system_prompt:
            return ""
        try:
            import config as C
            data = C.load_system_prompt(self.current_system_prompt)
            if isinstance(data, dict) and 'prompt' in data:
                return str(data.get('prompt') or '')
            return str(data)
        except Exception:
            prompt_file = self.system_prompts_dir / f"{self.current_system_prompt}.txt"
            if prompt_file.exists():
                try:
                    with open(prompt_file, 'r') as f:
                        return f.read()
                except Exception:
                    pass
            return "You are a helpful AI assistant."

    def get_current_tool_schema_config(self):
        """Get the current tool schema configuration.

        Prefer centrally managed schemas via config; fallback to local JSON.
        """
        # Off/None → treat as no schema selected
        if not self.current_tool_schema:
            return {"enabled_tools": "all"}
        try:
            import config as C
            return C.load_tool_schema(self.current_tool_schema)
        except Exception:
            schema_file = self.tool_schemas_dir / f"{self.current_tool_schema}.json"
            if schema_file.exists():
                try:
                    with open(schema_file, 'r') as f:
                        return json.load(f)
                except Exception:
                    pass
            return {"enabled_tools": "all"}

    def get_realtime_eval_scores(self):
        """Return the real-time evaluation scores"""
        return self.realtime_eval_scores

    def _validate_tool_call_success(self, tool_call, result, user_message):
        """
        Enhanced tool call validation beyond simple error string matching.

        Returns:
            Tuple[bool, str]: (is_success, failure_reason)
        """
        result_content = result.get('content', '')
        tool_name = tool_call.get('function', {}).get('name', 'unknown')

        # 1. Check for explicit error indicators
        error_indicators = ['Error:', 'error:', 'ERROR:', 'Exception:', 'Failed:', 'failed:']
        for indicator in error_indicators:
            if indicator in result_content:
                return False, "error_in_result"

        # 2. Check for empty or suspiciously short results for tools that should return data
        data_returning_tools = ['file_read', 'grep_search', 'list_directory', 'web_fetch', 'bash']
        if tool_name in data_returning_tools:
            if len(result_content.strip()) < 10:
                return False, "empty_result"

        # 3. Tool-specific validations
        if tool_name == 'file_read':
            # File read should not return "file not found" or similar
            if any(phrase in result_content.lower() for phrase in ['not found', 'does not exist', 'no such file']):
                return False, "file_not_found"

        elif tool_name == 'file_write':
            # File write should confirm success
            if not any(phrase in result_content.lower() for phrase in ['written', 'success', 'saved', 'created']):
                return False, "write_not_confirmed"

        elif tool_name == 'bash':
            # Bash commands with non-zero exit codes often indicate failure
            if 'exit code' in result_content.lower() and 'exit code 0' not in result_content.lower():
                return False, "non_zero_exit_code"

        elif tool_name == 'grep_search':
            # Grep with no matches might be valid, but if user asked for something specific, it's likely a failure
            if 'no matches found' in result_content.lower() or result_content.strip() == '':
                # Check if user was expecting specific content
                if user_message and any(word in user_message.lower() for word in ['find', 'search', 'where', 'show me']):
                    return False, "no_matches_found"

        # 4. Check result format makes sense (basic sanity check)
        # If result is just a stack trace or exception, it's likely a failure
        if result_content.count('\n') > 20 and 'Traceback' in result_content:
            return False, "exception_traceback"

        # If we got here, consider it a success
        return True, "success"

    def persist_realtime_scores(self, model_name=None):
        """Persist real-time scores to ToolCallLogger for permanent storage"""
        if not self.tool_call_logger:
            log_message("CHAT_INTERFACE: ToolCallLogger not available for persisting scores")
            return

        # If model_name not specified, persist all models' scores
        models_to_persist = [model_name] if model_name else list(self.realtime_eval_scores.keys())

        for model in models_to_persist:
            if model not in self.realtime_eval_scores:
                continue

            log_message(f"CHAT_INTERFACE: Persisting real-time scores for {model}")

            for tool_name, stats in self.realtime_eval_scores[model].items():
                success_count = stats.get('success', 0)
                failure_count = stats.get('failure', 0)

                # Log each success and failure to ToolCallLogger
                # This updates the persistent tool_realtime_data.jsonl file
                for _ in range(success_count):
                    self.tool_call_logger.log_tool_call(
                        tool_name=tool_name,
                        tool_args={},  # Args not tracked in realtime scores
                        result="Success (from realtime persistence)",
                        success=True,
                        model_name=model
                    )

                for error in stats.get('errors', [])[:failure_count]:
                    self.tool_call_logger.log_tool_call(
                        tool_name=tool_name,
                        tool_args={},
                        result=error,
                        success=False,
                        model_name=model
                    )

            log_message(f"CHAT_INTERFACE: ✓ Persisted real-time scores for {model}")

    def _auto_save_conversation(self):
        """Auto-save current conversation to persistent storage"""
        if not self.chat_history_manager or not self.current_model or not self.chat_history:
            log_message(
                "CHAT_INTERFACE: Auto-save skipped — manager=%s model=%s messages=%s" % (
                    'yes' if self.chat_history_manager else 'no',
                    self.current_model or 'None',
                    len(self.chat_history or [])
                )
            )
            return

        try:
            # Collect metadata
            current_mode = 'unknown'
            try:
                mode_settings_file = Path(__file__).parent.parent / "mode_settings.json"
                if mode_settings_file.exists():
                    with open(mode_settings_file, 'r') as f:
                        settings = json.load(f)
                    current_mode = settings.get('current_mode', 'unknown')
            except Exception:
                pass

            tool_settings = {}
            try:
                tool_settings_file = Path(__file__).parent.parent / "tool_settings.json"
                if tool_settings_file.exists():
                    with open(tool_settings_file, 'r') as f:
                        tool_settings = json.load(f)
            except Exception:
                pass

            # Determine variant_id and lineage_id for UID-aware saves
            # Try to use the global model context bundle first
            variant_id = None
            lineage_id = None
            try:
                from model_context_bundle import get_context
                bundle = get_context().get_bundle()
                if bundle:
                    variant_id = bundle.get('variant_id')
                    lineage_id = bundle.get('lineage_id')
                    print(f"[ChatInterface] Using global bundle: variant_id={variant_id}, lineage_id={lineage_id}")
            except Exception as e:
                print(f"[ChatInterface] No global bundle available, resolving from model: {e}")

            # Fallback: resolve from self.current_model if no bundle available
            if not variant_id:
                try:
                    import config as C
                    model_str = str(self.current_model or '')
                    if model_str.endswith('.gguf'):
                        try:
                            m = C.list_assigned_local_by_variant() or {}
                            for vid, ggufs in m.items():
                                if model_str in (ggufs or []):
                                    variant_id = vid; break
                        except Exception:
                            pass
                        if not variant_id:
                            # fallback to filename stem as heuristic
                            from pathlib import Path as _P
                            variant_id = _P(model_str).stem
                    else:
                        variant_id = model_str
                    if variant_id:
                        try:
                            lineage_id = C.get_lineage_id(variant_id)
                        except Exception:
                            lineage_id = None
                    print(f"[ChatInterface] Resolved from model: variant_id={variant_id}, lineage_id={lineage_id}")
                except Exception as e:
                    print(f"[ChatInterface] Error resolving variant_id: {e}")

            # Capture current agents roster (best-effort)
            agents_default = None
            try:
                if hasattr(self.root, 'get_active_agents') and callable(getattr(self.root, 'get_active_agents')):
                    agents_default = self.root.get_active_agents() or None
            except Exception:
                agents_default = None

            # Persist agents mini-sessions (small per-agent logs) if present
            try:
                agents_sessions = dict(getattr(self, '_agents_sessions', {}))
            except Exception:
                agents_sessions = {}

            metadata = {
                "mode": current_mode,
                "temperature": self.session_temperature,
                "temp_mode": getattr(self, 'temp_mode', 'manual'),
                "system_prompt": self.current_system_prompt,
                "tool_schema": self.current_tool_schema,
                "working_directory": self.tool_executor.get_working_directory() if self.tool_executor else 'unknown',
                "training_data_collection": self.training_mode_enabled,
                "training_support_enabled": bool(self.backend_settings.get('training_support_enabled', False)),
                "model": self.current_model,
                "variant_id": variant_id,
                "lineage_id": lineage_id,
                "tool_settings": tool_settings,
                # Persist per-session tool overrides (if any)
                "session_tools": getattr(self, 'session_enabled_tools', None),
                # RAG per chat (if toggled)
                "rag_enabled": bool(getattr(self, 'rag_enabled', False)),
                # Show Thoughts toggle
                "show_thoughts": bool(getattr(self, 'show_thoughts', False)),
                # Agents roster for this session (override project default)
                "agents_default": agents_default,
                # Persist per-session Agentic Project override if set (None means use backend default)
                "agentic_project_enabled": (self.agentic_project_override if getattr(self, 'agentic_project_override', None) is not None else None),
                # Per-agent mini chat logs
                "agents_sessions": agents_sessions,
            }

            # Save conversation
            log_message(
                "CHAT_INTERFACE: Auto-saving conversation (model=%s, messages=%s)" % (
                    self.current_model,
                    len(self.chat_history)
                )
            )

            session_id = self.chat_history_manager.save_conversation(
                model_name=self.current_model,
                chat_history=self.chat_history,
                session_name=self.current_session_id,
                metadata=metadata
            )

            # Route to knowledge banks (two-tier storage)
            if session_id and hasattr(self, 'knowledge_bank_manager') and self.knowledge_bank_manager:
                try:
                    session_data = {
                        "session_id": session_id,
                        "model_name": self.current_model,
                        "chat_history": self.chat_history,
                        "metadata": metadata
                    }
                    project_name = getattr(self, 'current_project', None)
                    rag_enabled = metadata.get('rag_enabled', False)
                    user_starred = metadata.get('user_starred', False)

                    self.knowledge_bank_manager.save_chat_with_knowledge_routing(
                        session_data=session_data,
                        session_id=session_id,
                        variant_id=variant_id,
                        project_name=project_name,
                        rag_enabled=rag_enabled,
                        user_starred=user_starred
                    )
                    log_message(f"CHAT_INTERFACE: Routed session to knowledge banks (variant={variant_id}, project={project_name})")
                except Exception as e:
                    log_message(f"CHAT_INTERFACE ERROR: Failed to route to knowledge banks: {e}")

            # Update current session ID
            if session_id:
                self.current_session_id = session_id
                log_message(f"CHAT_INTERFACE: Auto-saved conversation as {session_id}")
                self._chat_dirty = False

                # Emit event to notify other tabs (e.g., ModelsTab to refresh skills)
                try:
                    import json as _json
                    payload = _json.dumps({
                        "variant_id": variant_id,
                        "model_name": self.current_model,
                        "session_id": session_id,
                        "training_mode": bool(self.training_mode_enabled),
                        "training_support": bool(self.backend_settings.get('training_support_enabled', False)),
                        "message_count": len(self.chat_history)
                    })
                    self.root.event_generate("<<ConversationSaved>>", data=payload, when='tail')
                except Exception as e:
                    log_message(f"CHAT_INTERFACE: Failed to emit <<ConversationSaved>> event: {e}")

                # Refresh the history tab in the parent
                if hasattr(self.parent_tab, 'refresh_history'):
                    self.root.after(0, self.parent_tab.refresh_history)
                # Refresh conversation sidebar once and highlight current session
                try:
                    self._suppress_quickview = True
                    self.root.after(0, self._refresh_conversations_list)
                    self.root.after(250, lambda: setattr(self, '_suppress_quickview', False))
                except Exception:
                    self._suppress_quickview = False
                    pass
                # Update RAG index after save
                try:
                    self.rag_service.refresh_index_global()
                except Exception:
                    pass
        except Exception as e:
            log_message(f"CHAT_INTERFACE ERROR: Failed to auto-save conversation: {e}")

    def load_chat_history(self):
        """Open dialog to select and load a previous conversation"""
        from tkinter import messagebox

        if not self.chat_history_manager:
            messagebox.showerror("Error", "Chat history manager not initialized")
            return

        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Load Chat History")
        dialog.geometry("800x600")
        dialog.configure(bg='#2b2b2b')

        # Make modal
        dialog.transient(self.root)
        dialog.grab_set()

        # Main layout
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=0)  # Filter controls
        dialog.rowconfigure(1, weight=1)  # Chat list
        dialog.rowconfigure(2, weight=0)  # Buttons

        # Filter controls
        filter_frame = ttk.Frame(dialog, style='Category.TFrame')
        filter_frame.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)
        filter_frame.columnconfigure(1, weight=1)

        ttk.Label(
            filter_frame,
            text="Filter by Model:",
            font=("Arial", 10),
            style='Config.TLabel'
        ).grid(row=0, column=0, sticky=tk.W, padx=(0, 10))

        model_filter_var = tk.StringVar(value="All Models")
        model_filter = ttk.Combobox(
            filter_frame,
            textvariable=model_filter_var,
            state='readonly',
            font=("Arial", 10)
        )
        model_filter.grid(row=0, column=1, sticky=tk.EW, padx=(0, 10))

        # Get all unique model names
        all_conversations = self.chat_history_manager.list_conversations()
        model_names = sorted(list(set(conv["model_name"] for conv in all_conversations)))
        model_filter['values'] = ["All Models"] + model_names

        # Chat list frame
        list_frame = ttk.Frame(dialog, style='Category.TFrame')
        list_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=(0, 10))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        # Create Treeview for chat list
        tree_scroll = ttk.Scrollbar(list_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        chat_tree = ttk.Treeview(
            list_frame,
            columns=("Model", "Messages", "Date", "Preview"),
            show='headings',
            yscrollcommand=tree_scroll.set,
            style='Treeview'
        )
        chat_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=chat_tree.yview)

        # Configure columns
        chat_tree.heading("Model", text="Model")
        chat_tree.heading("Messages", text="Messages")
        chat_tree.heading("Date", text="Date")
        chat_tree.heading("Preview", text="Preview")

        chat_tree.column("Model", width=150, anchor=tk.W)
        chat_tree.column("Messages", width=80, anchor=tk.CENTER)
        chat_tree.column("Date", width=150, anchor=tk.W)
        chat_tree.column("Preview", width=300, anchor=tk.W)

        # Configure Treeview style
        style = ttk.Style()
        style.configure('Treeview', background='#1e1e1e', foreground='#ffffff', fieldbackground='#1e1e1e')
        style.map('Treeview', background=[('selected', '#61dafb')])

        def populate_tree(filter_model=None):
            """Populate tree with conversations"""
            chat_tree.delete(*chat_tree.get_children())

            conversations = self.chat_history_manager.list_conversations(
                model_name=filter_model if filter_model != "All Models" else None
            )

            for conv in conversations:
                # Format date
                date_str = conv.get("saved_at", "")
                if date_str:
                    try:
                        date_obj = datetime.fromisoformat(date_str)
                        date_formatted = date_obj.strftime("%Y-%m-%d %H:%M")
                    except:
                        date_formatted = date_str[:16]
                else:
                    date_formatted = "Unknown"

                chat_tree.insert(
                    "",
                    tk.END,
                    values=(
                        conv.get("model_name", "Unknown"),
                        conv.get("message_count", 0),
                        date_formatted,
                        conv.get("preview", "")
                    ),
                    tags=(conv.get("session_id", ""),)
                )

        # Initial population
        populate_tree()

        def on_filter_change(event=None):
            """Handle filter change"""
            populate_tree(model_filter_var.get())

        model_filter.bind('<<ComboboxSelected>>', on_filter_change)

        # Button frame
        button_frame = ttk.Frame(dialog, style='Category.TFrame')
        button_frame.grid(row=2, column=0, sticky=tk.EW, padx=10, pady=(0, 10))

        def load_selected():
            """Load the selected conversation"""
            selection = chat_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a conversation to load")
                return

            item = chat_tree.item(selection[0])
            session_id = item['tags'][0]

            # Load conversation
            conversation = self.chat_history_manager.load_conversation(session_id)
            if not conversation:
                messagebox.showerror("Error", f"Failed to load conversation: {session_id}")
                return

            # Check if we need to save current conversation
            if self.chat_history and self.backend_settings.get('auto_save_history', True):
                if messagebox.askyesno(
                    "Save Current Chat?",
                    "Do you want to save the current conversation before loading a new one?"
                ):
                    self._auto_save_conversation()

            # Load the conversation
            self.chat_history = conversation.get("chat_history", [])
            self.current_model = conversation.get("model_name")
            self.current_session_id = session_id

            # Update UI
            self.model_label.config(text=self.current_model)
            self.redisplay_conversation()
            self.add_message("system", f"✓ Loaded conversation: {session_id}")
            log_message(f"CHAT_INTERFACE: Loaded conversation {session_id}")

            dialog.destroy()

        def delete_selected():
            """Delete the selected conversation"""
            selection = chat_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a conversation to delete")
                return

            item = chat_tree.item(selection[0])
            session_id = item['tags'][0]

            if messagebox.askyesno(
                "Confirm Delete",
                f"Are you sure you want to delete this conversation?\n\n{session_id}"
            ):
                if self.chat_history_manager.delete_conversation(session_id):
                    messagebox.showinfo("Deleted", "Conversation deleted successfully")
                    populate_tree(model_filter_var.get())
                else:
                    messagebox.showerror("Error", "Failed to delete conversation")

        def export_selected():
            """Export the selected conversation"""
            from tkinter import filedialog

            selection = chat_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a conversation to export")
                return

            item = chat_tree.item(selection[0])
            session_id = item['tags'][0]

            # Ask for export format
            export_format = messagebox.askquestion(
                "Export Format",
                "Export as JSON?\n(No = Export as Text)",
                icon='question'
            )
            format_ext = "json" if export_format == "yes" else "txt"

            # Ask for save location
            export_path = filedialog.asksaveasfilename(
                title="Export Conversation",
                defaultextension=f".{format_ext}",
                filetypes=[(f"{format_ext.upper()} files", f"*.{format_ext}"), ("All files", "*.*")],
                initialfile=f"{session_id}.{format_ext}"
            )

            if export_path:
                if self.chat_history_manager.export_conversation(session_id, Path(export_path), format_ext):
                    messagebox.showinfo("Exported", f"Conversation exported to:\n{export_path}")
                else:
                    messagebox.showerror("Error", "Failed to export conversation")

        # Buttons
        ttk.Button(
            button_frame,
            text="✓ Load",
            command=load_selected,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="🗑️ Delete",
            command=delete_selected,
            style='Select.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="📤 Export",
            command=export_selected,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            style='Select.TButton'
        ).pack(side=tk.RIGHT, padx=5)

    def save_on_exit(self):
        """Save conversation when application is closing"""
        if self.chat_history and self.backend_settings.get('auto_save_history', True):
            self._auto_save_conversation()
            log_message("CHAT_INTERFACE: Saved conversation on exit")
        try:
            if getattr(self, "vector_client", None):
                self.vector_client.close()
                self.vector_client = None
        except Exception:
            pass
        try:
            if getattr(self, "embedding_server", None):
                if self.embedding_server.is_running():
                    log_message("VECTOR_SERVER: Stopping on exit")
                    self.embedding_server.stop()
        except Exception:
            pass

    def set_training_mode(self, enabled):
        """Enable or disable training mode"""
        # If disabling training mode, persist any accumulated scores
        if not enabled and self.training_mode_enabled and self.realtime_eval_scores:
            log_message("CHAT_INTERFACE: Training mode being disabled - persisting real-time scores")
            self.persist_realtime_scores()  # Persist all models
            self.add_message("system", "💾 Real-time scores persisted to permanent storage.")

        self.training_mode_enabled = enabled
        log_message(f"CHAT_INTERFACE: Training mode set to {enabled}")
        self.add_message("system", f"📚 Training mode has been {'enabled' if enabled else 'disabled'}.")
        # Apply/clear training support flags for this session
        try:
            ts = bool(self.backend_settings.get('training_support_enabled', False))
            if enabled and ts:
                # Turn on extractive verification/QA and auto‑pipeline for runtime datasets
                if 'verification' not in self.advanced_settings:
                    self.advanced_settings['verification'] = {}
                self.advanced_settings['verification']['post_tool_extractive'] = True
                self.backend_settings['auto_start_training_on_runtime_dataset'] = True
                self.add_message('system', '🔧 Training Support active: extractive verification + auto pipeline')
            else:
                # Do not write runtime datasets or auto‑train when training mode is OFF
                self.backend_settings['auto_start_training_on_runtime_dataset'] = False
        except Exception:
            pass
        # Reflect state in Quick Actions button if open
        try:
            self._qa_update_training_btn()
            self._update_quick_indicators()
        except Exception:
            pass

    def set_mode_parameters(self, mode, params):
        """Set mode-specific parameters from the mode selector FOR THE CURRENT SESSION"""
        log_message(f"CHAT_INTERFACE: Setting session mode to '{mode}' with params: {params}")

        if mode == 'standard':
            self.is_standard_mode = True
            self.add_message("system", "⚙️ Mode updated to Standard. Advanced systems bypassed.")
            self.initialize_advanced_components() # Re-initialize to disable components
            return

        self.is_standard_mode = False
        # Map mode to resource profile
        profile_map = {
            'fast': 'conservative',
            'smart': 'balanced',
            'think': 'aggressive'
        }
        profile = profile_map.get(mode, 'balanced')

        # Update advanced settings FOR THE SESSION
        if 'resource_management' not in self.advanced_settings:
            self.advanced_settings['resource_management'] = {}
        self.advanced_settings['resource_management']['profile'] = profile

        # Potentially map other parameters from params to self.advanced_settings here
        
        # Re-initialize advanced components to apply new session settings
        self.initialize_advanced_components()

        self.add_message("system", f"⚙️ Mode for this session updated to '{mode.capitalize()}' ({profile} profile).")

    def refresh(self):
        """Refresh the chat interface"""
        log_message("CHAT_INTERFACE: Refreshing...")
        # Reload backend settings
        self.backend_settings = self.load_backend_settings()

        # Reload advanced settings
        self.advanced_settings = self.load_advanced_settings()

        # Reinitialize advanced components
        self.initialize_advanced_components()

        # Update tool executor working directory if changed
        if self.tool_executor:
            working_dir = self.backend_settings.get('working_directory', str(Path.cwd()))
            self.tool_executor.set_working_directory(working_dir)
