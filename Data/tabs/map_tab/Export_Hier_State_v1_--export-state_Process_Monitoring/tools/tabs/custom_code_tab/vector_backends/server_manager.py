"""
Vector Backend Server Manager
Manages llama.cpp embedding server lifecycle for vector RAG.
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, Any
import psutil


class EmbeddingServerManager:
    """Manages llama.cpp embedding server for vector search."""

    def __init__(self, logger=None):
        self._logger = logger or (lambda msg: None)
        self._process: Optional[subprocess.Popen] = None
        self._server_pid: Optional[int] = None
        self._default_port = 8081
        self._default_host = "127.0.0.1"

    def is_running(self) -> bool:
        """Check if embedding server is running."""
        # Check if our managed process is alive
        if self._process and self._process.poll() is None:
            return True

        # Check if any process is listening on the port
        try:
            import urllib.request
            url = f"http://{self._default_host}:{self._default_port}/health"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except Exception:
            pass

        return False

    def start(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Start the embedding server.

        Args:
            config: Optional configuration dict with:
                - model_path: Path to embedding model
                - port: Server port (default 8081)
                - host: Server host (default 127.0.0.1)
                - n_ctx: Context size (default 512)
                - n_gpu_layers: GPU layers to offload (default -1 for all)

        Returns:
            True if server started successfully, False otherwise
        """
        if self.is_running():
            self._logger("VECTOR_SERVER: Already running")
            return True

        config = config or {}
        model_path = config.get("model_path")
        port = config.get("port", self._default_port)
        host = config.get("host", self._default_host)
        n_ctx = config.get("n_ctx", 512)
        n_gpu_layers = config.get("n_gpu_layers", -1)

        # Find llama-server or llama.cpp server binary
        server_binary = self._find_server_binary()
        if not server_binary:
            self._logger("VECTOR_SERVER: llama-server binary not found")
            return False

        # Find embedding model if not specified
        if not model_path:
            model_path = self._find_embedding_model()

        if not model_path or not Path(model_path).exists():
            self._logger(f"VECTOR_SERVER: Embedding model not found at {model_path}")
            return False

        # Build command
        cmd = [
            str(server_binary),
            "-m", str(model_path),
            "--host", host,
            "--port", str(port),
            "-c", str(n_ctx),
            "--embedding",  # Enable embedding mode
        ]

        if n_gpu_layers >= 0:
            cmd.extend(["-ngl", str(n_gpu_layers)])

        try:
            self._logger(f"VECTOR_SERVER: Starting with command: {' '.join(cmd)}")
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            self._server_pid = self._process.pid

            # Wait for server to be ready
            for _ in range(30):  # 15 second timeout
                time.sleep(0.5)
                if self.is_running():
                    self._logger(f"VECTOR_SERVER: Started successfully (PID {self._server_pid})")
                    return True

            self._logger("VECTOR_SERVER: Timeout waiting for server to start")
            self.stop()
            return False

        except Exception as exc:
            self._logger(f"VECTOR_SERVER: Failed to start: {exc}")
            return False

    def stop(self) -> bool:
        """Stop the embedding server.

        Returns:
            True if stopped successfully, False otherwise
        """
        if not self._process:
            return True

        try:
            self._logger(f"VECTOR_SERVER: Stopping (PID {self._server_pid})")
            self._process.terminate()

            # Wait for graceful shutdown
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._logger("VECTOR_SERVER: Force killing")
                self._process.kill()
                self._process.wait(timeout=2)

            self._process = None
            self._server_pid = None
            self._logger("VECTOR_SERVER: Stopped")
            return True

        except Exception as exc:
            self._logger(f"VECTOR_SERVER: Failed to stop: {exc}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get current server status.

        Returns:
            Dict with keys: running, pid, port, host
        """
        return {
            "running": self.is_running(),
            "pid": self._server_pid,
            "port": self._default_port,
            "host": self._default_host
        }

    def _find_server_binary(self) -> Optional[Path]:
        """Find llama-server binary."""
        candidates = [
            # Check common installation paths
            Path.home() / ".local/bin/llama-server",
            Path("/usr/local/bin/llama-server"),
            Path("/usr/bin/llama-server"),
            # Check in project directory
            Path(__file__).resolve().parents[5] / "llama.cpp/build/bin/llama-server",
            Path(__file__).resolve().parents[5] / "llama.cpp/llama-server",
        ]

        # Also check PATH
        import shutil
        path_binary = shutil.which("llama-server")
        if path_binary:
            candidates.insert(0, Path(path_binary))

        for candidate in candidates:
            if candidate and candidate.exists() and os.access(candidate, os.X_OK):
                return candidate

        return None

    def _find_embedding_model(self) -> Optional[str]:
        """Find a suitable embedding model."""
        # Check environment variable first
        if os.getenv("EMBEDDING_MODEL_PATH"):
            return os.getenv("EMBEDDING_MODEL_PATH")

        # Check common model locations
        project_root = Path(__file__).resolve().parents[5]
        candidates = [
            project_root / "Models/<#>
        ]

        for candidate in candidates:
            # Handle glob patterns
            if "*" in str(candidate):
                import glob
                matches = glob.glob(str(candidate))
                if matches:
                    return matches[0]
            elif candidate.exists():
                return str(candidate)

        return None
