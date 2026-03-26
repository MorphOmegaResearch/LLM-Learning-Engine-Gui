#!/usr/bin/env python3
"""
Agent Server Manager - Manages dedicated llama.cpp server instances for agents

Each agent using llama_server backend gets its own temporary server instance
on a unique port, allowing multiple agents + main model to coexist.
"""

import subprocess
import socket
import random
import time
import requests
import threading
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
import logger_util
from config import DATA_DIR, sanitize_identifier
from logger_util import get_tab_logger
from bug_tracker import get_bug_tracker

# Setup logging for agent server operations
log_message, log_error, log_exception = get_tab_logger('agent_server')
tracker = get_bug_tracker()


class AgentServerManager:
    """Manages dedicated llama.cpp server instances for agents"""

    def __init__(self):
        self.active_servers: Dict[str, Dict] = {}  # agent_id -> {port, process, model_path}
        self.port_range = (8003, 8999)  # Range for agent servers (main uses 8002)
        self.health_monitor_thread = None
        self.health_monitor_running = False
        self.health_check_interval = 30  # seconds

        log_message(
            f"AGENT_SERVER_MGR: Initialized | port_range={self.port_range} health_check_interval={self.health_check_interval}s",
            level='INFO'
        )

    def spawn_server_for_agent(self, agent_id: str, model_path: str,
                               n_gpu_layers: int = 0, cpu_threads: int = 8,
                               extra_args: str = "") -> Optional[int]:
        """Spawn dedicated llama.cpp server for agent on random port

        Args:
            agent_id: Unique agent identifier
            model_path: Path to GGUF model file
            n_gpu_layers: Number of layers to offload to GPU
            cpu_threads: Number of CPU threads to use
            extra_args: Additional llama-server arguments

        Returns:
            Port number if successful, None if failed
        """
        log_message(
            f"AGENT_SERVER_MGR: operation=spawn_request agent={agent_id} model={model_path} "
            f"gpu_layers={n_gpu_layers} threads={cpu_threads} extra_args='{extra_args}'",
            level='INFO'
        )

        # Check if agent already has a server
        if agent_id in self.active_servers:
            existing_port = self.active_servers[agent_id]['port']
            log_message(
                f"AGENT_SERVER_MGR: operation=spawn_skip agent={agent_id} port={existing_port} "
                f"reason='server already exists'",
                level='INFO'
            )
            return existing_port

        # Check if model exists
        model_file = Path(model_path)
        if not model_file.exists():
            log_error(
                f"AGENT_SERVER_MGR: operation=spawn_failed agent={agent_id} reason='model not found' "
                f"model_path={model_path}",
                auto_capture=True
            )
            return None

        log_message(
            f"AGENT_SERVER_MGR: operation=model_validated agent={agent_id} model_path={model_path} "
            f"model_size={model_file.stat().st_size} bytes",
            level='INFO'
        )

        # Find available port
        port = self._find_available_port(agent_id)
        if port is None:
            log_error(
                f"AGENT_SERVER_MGR: operation=spawn_failed agent={agent_id} reason='no available ports' "
                f"port_range={self.port_range} active_servers={len(self.active_servers)}",
                auto_capture=True
            )
            return None

        # Find llama-server binary
        llama_server_binary = self._find_llama_server_binary()
        if not llama_server_binary:
            log_error(
                f"AGENT_SERVER_MGR: operation=spawn_failed agent={agent_id} reason='llama-server binary not found'",
                auto_capture=True
            )
            return None

        log_message(
            f"AGENT_SERVER_MGR: operation=binary_found agent={agent_id} binary={llama_server_binary}",
            level='INFO'
        )

        # Build command
        cmd = [
            llama_server_binary,
            "--model", str(model_path),
            "--port", str(port),
            "--n-gpu-layers", str(n_gpu_layers),
            "--threads", str(cpu_threads),
            "--host", "127.0.0.1"
        ]

        # Add extra args if provided
        if extra_args:
            cmd.extend(extra_args.split())

        # Add default jinja support
        if "--jinja" not in cmd:
            cmd.append("--jinja")

        log_message(
            f"AGENT_SERVER_MGR: operation=command_built agent={agent_id} port={port} "
            f"command='{' '.join(cmd)}'",
            level='INFO'
        )

        try:
            # Create log files for capturing stdout/stderr
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_dir = DATA_DIR / "DeBug"
            log_dir.mkdir(parents=True, exist_ok=True)

            safe_agent_id = sanitize_identifier(agent_id, add_hash=True)
            stdout_log = log_dir / f"agent_server_{safe_agent_id}_{timestamp}_stdout.log"
            stderr_log = log_dir / f"agent_server_{safe_agent_id}_{timestamp}_stderr.log"

            log_message(
                f"AGENT_SERVER_MGR: operation=spawn_starting agent={agent_id} port={port} "
                f"stdout_log={stdout_log} stderr_log={stderr_log}",
                level='INFO'
            )

            # Spawn server process with output capture
            stdout_file = open(stdout_log, 'w')
            stderr_file = open(stderr_log, 'w')

            process = subprocess.Popen(
                cmd,
                stdout=stdout_file,
                stderr=stderr_file,
                text=True
            )

            log_message(
                f"AGENT_SERVER_MGR: operation=process_spawned agent={agent_id} pid={process.pid} "
                f"port={port} status=RUNNING",
                level='INFO'
            )

            # Store server info
            self.active_servers[agent_id] = {
                "port": port,
                "process": process,
                "model_path": model_path,
                "n_gpu_layers": n_gpu_layers,
                "cpu_threads": cpu_threads,
                "stdout_log": stdout_log,
                "stderr_log": stderr_log,
                "stdout_file": stdout_file,
                "stderr_file": stderr_file,
                "spawn_time": time.time()
            }

            # Wait for server to be ready
            start_wait = time.time()
            if self._wait_for_server_ready(agent_id, port, timeout=30):
                elapsed = time.time() - start_wait
                log_message(
                    f"AGENT_SERVER_MGR: operation=spawn_success agent={agent_id} port={port} "
                    f"pid={process.pid} startup_time={elapsed:.2f}s status=READY",
                    level='INFO'
                )

                # Start health monitoring if not already running
                self._ensure_health_monitor_running()

                return port
            else:
                elapsed = time.time() - start_wait

                # Read error logs
                stderr_content = ""
                try:
                    stderr_file.flush()
                    with open(stderr_log, 'r') as f:
                        stderr_content = f.read()[-500:]  # Last 500 chars
                except Exception:
                    pass

                log_error(
                    f"AGENT_SERVER_MGR: operation=spawn_failed agent={agent_id} port={port} "
                    f"reason='health check timeout' timeout={elapsed:.2f}s stderr_excerpt='{stderr_content}'",
                    auto_capture=True
                )

                self.destroy_server_for_agent(agent_id)
                return None

        except Exception as e:
            log_exception(
                f"AGENT_SERVER_MGR: operation=spawn_exception agent={agent_id} error='{e}'"
            )
            return None

    def destroy_server_for_agent(self, agent_id: str) -> bool:
        """Kill the agent's dedicated server

        Args:
            agent_id: Unique agent identifier

        Returns:
            True if successful, False otherwise
        """
        if agent_id not in self.active_servers:
            log_message(
                f"AGENT_SERVER_MGR: operation=destroy_skip agent={agent_id} reason='server not found'",
                level='WARNING'
            )
            return False

        try:
            server_info = self.active_servers[agent_id]
            port = server_info['port']
            process = server_info['process']
            pid = process.pid

            log_message(
                f"AGENT_SERVER_MGR: operation=destroy_request agent={agent_id} port={port} pid={pid}",
                level='INFO'
            )

            # Try graceful termination first
            process.terminate()
            try:
                process.wait(timeout=5)
                log_message(
                    f"AGENT_SERVER_MGR: operation=destroy_success agent={agent_id} port={port} "
                    f"pid={pid} method=graceful",
                    level='INFO'
                )
            except subprocess.TimeoutExpired:
                # Force kill if graceful termination fails
                log_message(
                    f"AGENT_SERVER_MGR: operation=destroy_force_kill agent={agent_id} port={port} pid={pid}",
                    level='WARNING'
                )
                process.kill()
                process.wait()
                log_message(
                    f"AGENT_SERVER_MGR: operation=destroy_success agent={agent_id} port={port} "
                    f"pid={pid} method=force_kill",
                    level='INFO'
                )

            # Close log files
            try:
                if 'stdout_file' in server_info:
                    server_info['stdout_file'].close()
                if 'stderr_file' in server_info:
                    server_info['stderr_file'].close()
            except Exception:
                pass

            del self.active_servers[agent_id]
            return True

        except Exception as e:
            log_exception(
                f"AGENT_SERVER_MGR: operation=destroy_exception agent={agent_id} error='{e}'"
            )
            return False

    def get_server_port(self, agent_id: str) -> Optional[int]:
        """Get the port number for an agent's server

        Args:
            agent_id: Unique agent identifier

        Returns:
            Port number if server exists, None otherwise
        """
        if agent_id in self.active_servers:
            return self.active_servers[agent_id]['port']
        return None

    def is_server_active(self, agent_id: str) -> bool:
        """Check if an agent's server is active

        Args:
            agent_id: Unique agent identifier

        Returns:
            True if server is active, False otherwise
        """
        if agent_id not in self.active_servers:
            return False

        process = self.active_servers[agent_id]['process']
        return process.poll() is None

    def cleanup_all_servers(self):
        """Terminate all active agent servers"""
        agent_ids = list(self.active_servers.keys())
        log_message(
            f"AGENT_SERVER_MGR: operation=cleanup_all count={len(agent_ids)} agents={agent_ids}",
            level='INFO'
        )

        # Stop health monitor
        self.health_monitor_running = False
        if self.health_monitor_thread:
            self.health_monitor_thread.join(timeout=5)

        for agent_id in agent_ids:
            self.destroy_server_for_agent(agent_id)

        log_message(
            f"AGENT_SERVER_MGR: operation=cleanup_complete",
            level='INFO'
        )

    def _find_available_port(self, agent_id: str) -> Optional[int]:
        """Find random available port in configured range

        Args:
            agent_id: Agent requesting the port (for logging)

        Returns:
            Available port number or None if none found
        """
        attempts = 0
        max_attempts = 100
        occupied_ports = [s['port'] for s in self.active_servers.values()]

        log_message(
            f"AGENT_SERVER_MGR: operation=port_search_start agent={agent_id} "
            f"range={self.port_range} occupied_ports={occupied_ports}",
            level='DEBUG'
        )

        # Try 100 random ports
        for attempt in range(max_attempts):
            attempts += 1
            port = random.randint(self.port_range[0], self.port_range[1])

            # Check if port is in use by existing servers
            if port in occupied_ports:
                continue

            # Check if port is available on system
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    result = s.connect_ex(('127.0.0.1', port))
                    if result != 0:  # Port not in use
                        log_message(
                            f"AGENT_SERVER_MGR: operation=port_assigned agent={agent_id} port={port} "
                            f"attempts={attempts}",
                            level='INFO'
                        )
                        return port
            except Exception:
                continue

        log_message(
            f"AGENT_SERVER_MGR: operation=port_search_failed agent={agent_id} attempts={attempts} "
            f"occupied_ports={occupied_ports}",
            level='ERROR'
        )
        return None

    def _find_llama_server_binary(self) -> Optional[str]:
        """Find llama-server binary path using comprehensive search

        Matches the search logic from chat_interface_tab.py for consistency.

        Returns:
            Path to llama-server binary or None if not found
        """
        import os
        import json
        import shutil

        log_message(
            f"AGENT_SERVER_MGR: operation=binary_search_start",
            level='DEBUG'
        )

        # 1) Read configured path from Custom Code settings
        raw_path = None
        try:
            settings_path = Path('LLM-Learning-Engine-Gui-dev')/'Data'/'tabs'/'custom_code_tab'/'custom_code_settings.json'
            if settings_path.exists():
                data = json.loads(settings_path.read_text())
                raw_path = (data.get('llama_server_binary_path') or '').strip()
                if raw_path:
                    log_message(
                        f"AGENT_SERVER_MGR: operation=binary_search_try source=settings_file path={raw_path}",
                        level='DEBUG'
                    )
        except Exception as e:
            log_message(
                f"AGENT_SERVER_MGR: operation=binary_search_settings_error error='{e}'",
                level='DEBUG'
            )

        # Build candidate list
        candidates = []
        if raw_path:
            candidates.append(Path(raw_path))

        # 2) Check working directory paths (matches chat_interface logic)
        cwd = Path.cwd()
        try:
            # Try to get working_directory from settings
            settings_path = Path('LLM-Learning-Engine-Gui-dev')/'Data'/'tabs'/'custom_code_tab'/'custom_code_settings.json'
            if settings_path.exists():
                data = json.loads(settings_path.read_text())
                working_dir = Path(data.get('working_directory') or cwd)
            else:
                working_dir = cwd
        except Exception:
            working_dir = cwd

        # Add all candidate paths (same as chat_interface_tab.py)
        candidates.extend([
            working_dir / "llama.cpp" / "build" / "bin" / "llama-server",
            cwd / "llama.cpp" / "build" / "bin" / "llama-server",
            Path.home() / "llama.cpp" / "build" / "bin" / "llama-server",
            # Common trainer extras path
            cwd / "extras" / "gpu-test" / "bin" / "server",
            (Path(__file__).resolve().parents[2] / "extras" / "gpu-test" / "bin" / "server"),
            # Fallback common system paths
            Path("/usr/local/bin/llama-server"),
            Path("/usr/bin/llama-server"),
            Path.home() / ".local" / "bin" / "llama-server",
            Path("./llama-server"),
            Path("../llama.cpp/build/bin/llama-server"),
        ])

        # 3) Try shutil.which for PATH lookup (matches chat_interface)
        try:
            found = shutil.which('llama-server')
            if found:
                candidates.insert(0, Path(found))
                log_message(
                    f"AGENT_SERVER_MGR: operation=binary_search_try source=PATH path={found}",
                    level='DEBUG'
                )
        except Exception as e:
            log_message(
                f"AGENT_SERVER_MGR: operation=binary_search_which_error error='{e}'",
                level='DEBUG'
            )

        # 4) Check each candidate
        for idx, candidate in enumerate(candidates):
            try:
                if candidate and candidate.exists() and os.access(str(candidate), os.X_OK):
                    log_message(
                        f"AGENT_SERVER_MGR: operation=binary_search_found path={candidate} candidate_index={idx}",
                        level='INFO'
                    )
                    return str(candidate)
            except Exception as e:
                log_message(
                    f"AGENT_SERVER_MGR: operation=binary_search_candidate_error path={candidate} error='{e}'",
                    level='DEBUG'
                )
                continue

        # 5) Not found
        log_message(
            f"AGENT_SERVER_MGR: operation=binary_search_not_found candidates_tried={len(candidates)}",
            level='ERROR'
        )
        return None

    def _wait_for_server_ready(self, agent_id: str, port: int, timeout: int = 30) -> bool:
        """Wait for server to be ready by checking health endpoint

        Args:
            agent_id: Agent identifier (for logging)
            port: Server port to check
            timeout: Maximum time to wait in seconds

        Returns:
            True if server becomes ready, False if timeout
        """
        url = f"http://127.0.0.1:{port}/health"
        start_time = time.time()
        attempt = 0

        log_message(
            f"AGENT_SERVER_MGR: operation=health_check_start agent={agent_id} port={port} "
            f"timeout={timeout}s url={url}",
            level='INFO'
        )

        while time.time() - start_time < timeout:
            attempt += 1
            try:
                response = requests.get(url, timeout=2)
                if response.status_code == 200:
                    elapsed = time.time() - start_time
                    log_message(
                        f"AGENT_SERVER_MGR: operation=health_check_success agent={agent_id} port={port} "
                        f"elapsed={elapsed:.2f}s attempts={attempt}",
                        level='INFO'
                    )
                    return True
                else:
                    log_message(
                        f"AGENT_SERVER_MGR: operation=health_check_retry agent={agent_id} port={port} "
                        f"attempt={attempt} status_code={response.status_code}",
                        level='DEBUG'
                    )
            except requests.exceptions.RequestException as e:
                log_message(
                    f"AGENT_SERVER_MGR: operation=health_check_retry agent={agent_id} port={port} "
                    f"attempt={attempt} error='{e}'",
                    level='DEBUG'
                )

            time.sleep(0.5)

        elapsed = time.time() - start_time
        log_message(
            f"AGENT_SERVER_MGR: operation=health_check_timeout agent={agent_id} port={port} "
            f"elapsed={elapsed:.2f}s attempts={attempt}",
            level='ERROR'
        )
        return False

    def _ensure_health_monitor_running(self):
        """Ensure health monitoring thread is running"""
        if not self.health_monitor_running:
            self.health_monitor_running = True
            self.health_monitor_thread = threading.Thread(
                target=self._health_monitor_loop,
                daemon=True
            )
            self.health_monitor_thread.start()
            log_message(
                f"AGENT_SERVER_MGR: operation=health_monitor_started interval={self.health_check_interval}s",
                level='INFO'
            )

    def _health_monitor_loop(self):
        """Background thread that monitors health of all agent servers"""
        log_message(
            f"AGENT_SERVER_MGR: operation=health_monitor_loop_started",
            level='INFO'
        )

        while self.health_monitor_running:
            try:
                # Check each active server
                for agent_id in list(self.active_servers.keys()):
                    if not self.health_monitor_running:
                        break

                    self._check_server_health(agent_id)

                # Wait for next check interval
                time.sleep(self.health_check_interval)

            except Exception as e:
                log_exception(
                    f"AGENT_SERVER_MGR: operation=health_monitor_exception error='{e}'"
                )
                time.sleep(5)  # Wait a bit before retrying

        log_message(
            f"AGENT_SERVER_MGR: operation=health_monitor_stopped",
            level='INFO'
        )

    def _check_server_health(self, agent_id: str):
        """Check health of a single agent server"""
        if agent_id not in self.active_servers:
            return

        server_info = self.active_servers[agent_id]
        port = server_info['port']
        process = server_info['process']

        # Check if process is still running
        if process.poll() is not None:
            # Process has died
            exit_code = process.poll()
            uptime = time.time() - server_info.get('spawn_time', 0)

            # Read stderr for crash info
            stderr_content = ""
            try:
                stderr_log = server_info.get('stderr_log')
                if stderr_log and Path(stderr_log).exists():
                    with open(stderr_log, 'r') as f:
                        stderr_content = f.read()[-500:]  # Last 500 chars
            except Exception:
                pass

            log_error(
                f"AGENT_SERVER_MGR: operation=health_check_failed agent={agent_id} port={port} "
                f"reason='process died' exit_code={exit_code} uptime={uptime:.2f}s "
                f"stderr_excerpt='{stderr_content}'",
                auto_capture=True
            )
            return

        # Check HTTP health endpoint
        url = f"http://127.0.0.1:{port}/health"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                uptime = time.time() - server_info.get('spawn_time', 0)
                log_message(
                    f"AGENT_SERVER_MGR: operation=health_check_ok agent={agent_id} port={port} "
                    f"uptime={uptime:.0f}s",
                    level='DEBUG'
                )
            else:
                log_message(
                    f"AGENT_SERVER_MGR: operation=health_check_degraded agent={agent_id} port={port} "
                    f"status_code={response.status_code}",
                    level='WARNING'
                )
        except requests.exceptions.RequestException as e:
            log_message(
                f"AGENT_SERVER_MGR: operation=health_check_unreachable agent={agent_id} port={port} "
                f"error='{e}'",
                level='WARNING'
            )


# Global singleton instance
_agent_server_manager = None

def get_agent_server_manager() -> AgentServerManager:
    """Get global AgentServerManager instance"""
    global _agent_server_manager
    if _agent_server_manager is None:
        _agent_server_manager = AgentServerManager()
    return _agent_server_manager
