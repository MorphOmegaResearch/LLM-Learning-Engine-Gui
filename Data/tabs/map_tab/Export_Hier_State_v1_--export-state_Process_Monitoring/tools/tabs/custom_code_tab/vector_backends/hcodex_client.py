from __future__ import annotations

import json
import os
import re
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request

import psycopg
from psycopg.rows import dict_row


@dataclass
class VectorSearchResult:
    project_id: Optional[str]
    file_path: str
    start_line: int
    end_line: int
    content: str
    similarity: float
    language: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class VectorSearchError(Exception):
    """Raised when vector search fails."""


class HCodexVectorClient:
    """Lightweight client for querying h-codex embeddings directly from Postgres."""

    def __init__(
        self,
        config_path: Optional[Path] = None,
        logger: Optional[Any] = None,
    ):
        self._logger = logger or (lambda msg: None)
        self._config = self._load_config(config_path)

        if not self._config.get("dbConnectionString"):
            raise VectorSearchError("HCodexVectorClient: Missing DB connection string.")
        try:
            self._conn = psycopg.connect(
                self._config["dbConnectionString"],
                row_factory=dict_row,
                autocommit=True,
                connect_timeout=5  # 5 second timeout to prevent GUI hangs
            )
        except Exception as exc:
            raise VectorSearchError(f"Failed to connect to h-codex database: {exc}") from exc
        self._model = self._config.get("model", "text-embedding-3-small")
        self._timeout = float(os.getenv("H_CODEX_EMBED_TIMEOUT", "45"))
        self._api_key = self._config.get("apiKey", "")
        base_url = (self._config.get("baseURL") or "http://127.0.0.1:8081/v1").rstrip("/")
        self._embeddings_url = f"{base_url}/embeddings"

    # ------------------------------------------------------------------ public API
    def close(self):
        try:
            if getattr(self, "_conn", None) is not None:
                self._conn.close()
        except Exception:
            pass

    def health_check(self) -> Dict[str, Any]:
        """Check health of both embedding endpoint and Postgres connection.

        Returns:
            Dict with keys: 'embedding_ok', 'postgres_ok', 'overall_ok', 'errors'
        """
        result = {
            "embedding_ok": False,
            "postgres_ok": False,
            "overall_ok": False,
            "errors": []
        }

        # Test embedding endpoint
        try:
            test_embedding = self._create_embedding("health check")
            if test_embedding and len(test_embedding) > 0:
                result["embedding_ok"] = True
            else:
                result["errors"].append("Embedding endpoint returned empty response")
        except Exception as exc:
            result["errors"].append(f"Embedding endpoint error: {exc}")

        # Test Postgres connection
        try:
            with self._conn.cursor() as cur:
                cur.execute("SELECT 1")
                row = cur.fetchone()
                if row:
                    result["postgres_ok"] = True
                else:
                    result["errors"].append("Postgres query returned no result")
        except Exception as exc:
            result["errors"].append(f"Postgres error: {exc}")

        result["overall_ok"] = result["embedding_ok"] and result["postgres_ok"]
        return result

    def search(
        self,
        query: str,
        project: Optional[str] = None,
        limit: int = 6,
    ) -> List[VectorSearchResult]:
        if not query:
            return []

        embedding = self._create_embedding(query)
        if not embedding:
            return []

        vector_literal = self._format_vector_literal(embedding)
        params: List[Any] = [vector_literal]
        where_clause = ""

        project_id: Optional[str] = None
        if project:
            project_id = self._resolve_project_id(project)
            if project_id:
                where_clause = "WHERE c.project_id = %s"
                params.append(uuid.UUID(project_id))
            else:
                self._logger(
                    f"HCODEX_VEC: project '{project}' not registered with h-codex; "
                    "falling back to global search."
                )

        params.append(int(max(1, limit)))

        sql = f"""
            WITH query_embedding AS (
                SELECT %s::vector AS embedding
            )
            SELECT
                c.project_id,
                c.file_path,
                c.start_line,
                c.end_line,
                c.language,
                c.content,
                1 - (e.embedding <=> query_embedding.embedding) AS similarity
            FROM embeddings e
            JOIN code_chunks c ON c.id = e.chunk_id
            JOIN query_embedding ON TRUE
            {where_clause}
            ORDER BY e.embedding <=> query_embedding.embedding
            LIMIT %s
        """

        try:
            with self._conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        except Exception as exc:
            raise VectorSearchError(f"Failed to execute vector query: {exc}") from exc

        results: List[VectorSearchResult] = []
        for row in rows or []:
            results.append(
                VectorSearchResult(
                    project_id=row.get("project_id"),
                    file_path=row.get("file_path", ""),
                    start_line=row.get("start_line") or 0,
                    end_line=row.get("end_line") or 0,
                    content=row.get("content") or "",
                    similarity=float(row.get("similarity") or 0.0),
                    language=row.get("language"),
                    metadata={
                        "source": "h-codex",
                        "node_type": row.get("node_type"),
                    },
                )
            )

        return results

    def index(self, path: str) -> None:
        """Trigger an index refresh for a given path using the h-codex CLI script."""
        script = Path(__file__).resolve().parents[4] / "scripts" / "index-cli.sh"
        if not script.exists():
            self._logger("HCODEX_VEC: index script not found; skipping auto-index.")
            return
        import subprocess

        try:
            subprocess.Popen([str(script), path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:  # pragma: no cover - best effort helper
            self._logger(f"HCODEX_VEC: failed to launch index script: {exc}")

    # ------------------------------------------------------------------ helpers
    def _create_embedding(self, text: str) -> List[float]:
        payload = json.dumps({"model": self._model, "input": text}).encode("utf-8")
        request = urllib.request.Request(
            self._embeddings_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if self._api_key:
            request.add_header("Authorization", f"Bearer {self._api_key}")

        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as resp:
                body = resp.read().decode("utf-8")
            data = json.loads(body)
            if not isinstance(data, dict):
                return []
            entries = data.get("data")
            if not entries:
                return []
            embedding = entries[0].get("embedding")
            if isinstance(embedding, list):
                return [float(v) for v in embedding]
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8")
            except Exception:
                detail = ""
            self._logger(f"HCODEX_VEC: embedding HTTP error {exc.code}: {detail[:200]}")
        except Exception as exc:
            self._logger(f"HCODEX_VEC: embedding failure: {exc}")
        return []

    def _resolve_project_id(self, name: str) -> Optional[str]:
        candidates = [
            name,
            str(Path(name).resolve()) if Path(name).exists() else None,
            self._slug(name),
        ]
        candidates = [c for c in candidates if c]

        try:
            with self._conn.cursor() as cur:
                for candidate in candidates:
                    cur.execute(
                        "SELECT id FROM projects WHERE name = %s OR path = %s LIMIT 1",
                        (candidate, candidate),
                    )
                    row = cur.fetchone()
                    if row and row.get("id"):
                        return str(row["id"])
        except Exception as exc:
            self._logger(f"HCODEX_VEC: project lookup failed: {exc}")
        return None

    def _format_vector_literal(self, embedding: List[float]) -> str:
        return "[" + ",".join(f"{value:.8f}" for value in embedding) + "]"

    def _load_config(self, config_path: Optional[Path]) -> Dict[str, Any]:
        cfg_path = (
            Path(config_path)
            if config_path
            else Path(os.getenv("H_CODEX_CONFIG_PATH", "~/.config/h-codex/config.json")).expanduser()
        )

        data: Dict[str, Any] = {}
        if cfg_path.exists():
            try:
                data = json.loads(cfg_path.read_text())
            except Exception:
                data = {}

        data.setdefault("apiKey", os.getenv("LLM_API_KEY") or "")
        data.setdefault("baseURL", os.getenv("LLM_BASE_URL") or "http://127.0.0.1:8081/v1")
        data.setdefault("model", os.getenv("EMBEDDING_MODEL") or data.get("model") or "text-embedding-3-small")
        data.setdefault("dbConnectionString", os.getenv("DB_CONNECTION_STRING") or data.get("dbConnectionString") or "")

        return data

    def _slug(self, value: str) -> str:
        text = unicodedata.normalize("NFD", value or "")
        text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
        text = text.lower()
        text = re.sub(r"[^a-z0-9.]+", "-", text)
        text = re.sub(r"\.{2,}", ".", text)
        text = text.strip(".-")
        text = text[:100]
        return text or "untitled-project"
