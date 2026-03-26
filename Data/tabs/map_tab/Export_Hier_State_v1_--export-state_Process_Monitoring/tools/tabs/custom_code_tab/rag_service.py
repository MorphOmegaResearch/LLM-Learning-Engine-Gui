"""
RagService - lightweight retrieval service for rag-enabled conversations.
Enhanced with Phase Sub-Zero-A debug logging

Features:
- Global and per-project indices built from saved conversations
- Pure-Python lexical scoring with TF-IDF-like weighting + simple time decay
- Optional rerank hook via provided context_scorer (if available)
- Returns capped snippets with provenance for safe injection
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import math
import re
import time

# Phase Sub-Zero-A: Import debug logger
try:
    import sys
    from pathlib import Path as _Path
    _data_dir = _Path(__file__).resolve().parent.parent.parent
    if str(_data_dir) not in sys.path:
        sys.path.insert(0, str(_data_dir))
    from debug_logger import get_logger, debug_method
    _debug_logger = get_logger("RAGService")
except ImportError:
    _debug_logger = None
    def debug_method(logger):
        return lambda f: f

try:
    from logger_util import log_message as _rag_log
except Exception:
    def _rag_log(msg: str):
        try:
            print(msg)
        except Exception:
            pass

try:
    from tabs.custom_code_tab.vector_backends import (
        HCodexVectorClient,
        VectorSearchError,
        VectorSearchResult,
    )
except Exception:  # pragma: no cover - optional dependency
    HCodexVectorClient = None  # type: ignore[assignment]
    VectorSearchError = Exception  # type: ignore[assignment]
    VectorSearchResult = None  # type: ignore[assignment]

try:
    from bug_tracker import get_bug_tracker
except Exception:  # pragma: no cover - optional dependency
    get_bug_tracker = None  # type: ignore[assignment]

_WORD_RE = re.compile(r"[A-Za-z0-9_]{3,}")


@dataclass
class RagDoc:
    session_id: str
    saved_at: str
    meta: Dict[str, Any]
    text: str
    role: str = "context"
    index: int = -1


class RagService:
    def __init__(self, chat_history_manager=None, context_scorer=None):
        self.chat_history_manager = chat_history_manager
        self.context_scorer = context_scorer
        self._global_index: List[RagDoc] = []
        self._project_indexes: Dict[str, List[RagDoc]] = {}
        self._global_df: Dict[str, int] = {}
        self._project_df: Dict[str, Dict[str, int]] = {}
        # Index storage paths
        self._global_index_path = Path('Data') / 'rag_index.json'
        self._project_index_dir = Path('Data') / 'projects'
        # Retrieval parameters (overridable)
        self.k1: float = 1.2
        self.b: float = 0.75
        self.decay_days: float = 3.0
        # Vector backend configuration
        self._vector_client: Optional[HCodexVectorClient] = None
        self._vector_enabled: bool = False
        self._vector_limit: int = 3
        self._vector_weight: float = 1.0
        self._vector_error_cache: Dict[str, float] = {}

    def set_params(self, k1: Optional[float] = None, b: Optional[float] = None, decay_days: Optional[float] = None):
        try:
            if k1 is not None:
                self.k1 = float(k1)
        except Exception:
            pass
        try:
            if b is not None:
                self.b = max(0.0, min(1.0, float(b)))
        except Exception:
            pass
        try:
            if decay_days is not None and float(decay_days) > 0:
                self.decay_days = float(decay_days)
        except Exception:
            pass

    def set_history_manager(self, hm):
        self.chat_history_manager = hm

    def set_context_scorer(self, scorer):
        self.context_scorer = scorer

    # --------------------------- Vector backend -------------------------
    def set_vector_backend(
        self,
        client: Optional[HCodexVectorClient],
        *,
        weight: Optional[float] = None,
        limit: Optional[int] = None,
    ):
        self._vector_client = client
        if weight is not None:
            try:
                self._vector_weight = max(0.0, float(weight))
            except Exception:
                pass
        if limit is not None:
            try:
                self._vector_limit = max(1, int(limit))
            except Exception:
                pass

    def enable_vector_search(self, enabled: bool):
        self._vector_enabled = bool(enabled)

    def set_vector_params(self, *, weight: Optional[float] = None, limit: Optional[int] = None):
        if weight is not None:
            try:
                self._vector_weight = max(0.0, float(weight))
            except Exception:
                pass
        if limit is not None:
            try:
                self._vector_limit = max(1, int(limit))
            except Exception:
                pass

    def get_vector_health(self) -> Optional[Dict[str, Any]]:
        """Get health status of vector backend if available."""
        if self._vector_client is None:
            return None
        try:
            return self._vector_client.health_check()
        except Exception as exc:
            return {
                "embedding_ok": False,
                "postgres_ok": False,
                "overall_ok": False,
                "errors": [f"Health check failed: {exc}"]
            }

    # --------------------------- Indexing ---------------------------------
    def refresh_index_global(self):
        if not self.chat_history_manager:
            self._global_index = []
            self._global_df = {}
            _rag_log("RAG_IDX: global index refresh skipped (no ChatHistoryManager)")
            return
        docs: List[RagDoc] = []
        df: Dict[str, int] = {}

        summaries = self.chat_history_manager.list_conversations()
        for rec in summaries:
            sid = rec.get('session_id', '')
            data = self.chat_history_manager.load_conversation(sid) or {}
            meta = data.get('metadata') or {}
            if not bool(meta.get('rag_enabled', False)):
                continue
            chat = data.get('chat_history') or []
            chunks = self._extract_chunks(chat)
            for idx, (role, text) in enumerate(chunks):
                if not text:
                    continue
                docs.append(RagDoc(session_id=sid, saved_at=data.get('saved_at', ''), meta=meta, text=text, role=role, index=idx))
                terms = set(self._tokenize(text))
                for t in terms:
                    df[t] = df.get(t, 0) + 1

        self._global_index = docs
        self._global_df = df
        _rag_log(f"RAG_IDX: global index built docs={len(docs)} df_terms={len(df)}")
        # Persist to disk
        try:
            self._save_global_index()
        except Exception:
            pass

    def refresh_index_project(self, project_name: str):
        root = Path('Data/projects') / (project_name or '')
        if not root.exists():
            self._project_indexes[project_name] = []
            self._project_df[project_name] = {}
            _rag_log(f"RAG_IDX: project index missing root path project={project_name}")
            return
        docs: List[RagDoc] = []
        df: Dict[str, int] = {}
        for f in root.glob('*.json'):
            try:
                data = json.loads(f.read_text())
            except Exception:
                _rag_log(f"RAG_IDX: project record load failed file={f}")
                continue
            meta = data.get('metadata') or {}
            if not bool(meta.get('rag_enabled', False)):
                continue
            chat = data.get('chat_history') or []
            chunks = self._extract_chunks(chat)
            for idx, (role, text) in enumerate(chunks):
                if not text:
                    continue
                docs.append(RagDoc(session_id=data.get('session_id', f.stem), saved_at=data.get('saved_at',''), meta=meta, text=text, role=role, index=idx))
                terms = set(self._tokenize(text))
                for t in terms:
                    df[t] = df.get(t, 0) + 1
        self._project_indexes[project_name] = docs
        self._project_df[project_name] = df
        _rag_log(f"RAG_IDX: project index built project={project_name} docs={len(docs)} df_terms={len(df)}")
        # Persist to disk
        try:
            self._save_project_index(project_name)
        except Exception:
            pass

    # --------------------------- Query ------------------------------------
    def query(self, user_message: str, top_k: int = 3, scope: Optional[str] = None) -> List[Tuple[RagDoc, float]]:
        """Query RAG index.
        scope=None → global index; scope='<project>' → per-project index
        Returns list of (doc, score)
        """
        text = (user_message or '').lower().strip()
        qterms = self._tokenize(text)
        if not qterms:
            _rag_log(f"RAG_Q: empty query terms scope={scope} top_k={top_k}")
            return []

        if scope:
            docs = self._project_indexes.get(scope) or []
            df = self._project_df.get(scope) or {}
        else:
            docs = self._global_index
            df = self._global_df
        n_docs = max(1, len(docs))
        _rag_log(f"RAG_Q: start scope={scope or 'global'} docs={len(docs)} qterms={len(qterms)} top_k={top_k}")

        # Precompute average document length for BM25
        dl_list = [len(self._tokenize(d.text)) for d in docs] or [1]
        avgdl = sum(dl_list) / max(1, len(dl_list))
        k1 = float(self.k1)
        b = float(self.b)

        # Score each doc with BM25 + time decay
        scored: List[Tuple[RagDoc, float]] = []
        for d in docs:
            tokens = self._tokenize(d.text)
            if not tokens:
                continue
            tf = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            score = 0.0
            dl = len(tokens)
            for t in set(qterms):
                tf_t = tf.get(t, 0)
                if tf_t == 0:
                    continue
                # BM25 IDF
                idf = math.log(1 + (n_docs - df.get(t, 0) + 0.5) / (df.get(t, 0) + 0.5))
                denom = tf_t + k1 * (1 - b + b * (dl / max(1.0, avgdl)))
                score += idf * ((tf_t * (k1 + 1)) / max(1e-6, denom))

            # Time decay factor (newer gets slight boost)
            try:
                dt = (datetime.now() - datetime.fromisoformat((d.saved_at or '').replace('Z',''))).total_seconds()
                decay = 1.0 / (1.0 + dt / (max(0.1, self.decay_days) * 24 * 3600))
            except Exception:
                decay = 1.0
            score *= (0.85 + 0.15 * decay)
            scored.append((d, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        lexical_out = scored[:top_k]

        # Optional rerank with context scorer
        if self.context_scorer and lexical_out:
            try:
                # Build candidate texts
                cand = [doc.text for doc, _ in lexical_out]
                # Use scorer to get quality; if available, reorder
                # Assume scorer.score_context returns dict with 'final_score'
                pairs = []
                for (doc, score), text in zip(lexical_out, cand):
                    sres = self.context_scorer.score_context([{"role":"system","content":text}])
                    q = float(sres.get('final_score', 0.0))
                    pairs.append((doc, score * (0.7 + 0.3 * (q/100.0))))
                pairs.sort(key=lambda x: x[1], reverse=True)
                lexical_out = pairs
            except Exception:
                pass

        # Vector augmentation
        vector_results: List[Tuple[RagDoc, float]] = []
        if self._vector_enabled and self._vector_client and VectorSearchResult:
            try:
                v_hits = self._vector_client.search(
                    user_message,
                    project=scope,
                    limit=min(self._vector_limit, max(1, top_k or self._vector_limit)),
                )
                for hit in v_hits:
                    doc = RagDoc(
                        session_id=hit.file_path,
                        saved_at=datetime.utcnow().isoformat(),
                        meta={
                            "vector": True,
                            "file_path": hit.file_path,
                            "start_line": hit.start_line,
                            "end_line": hit.end_line,
                            "project_id": hit.project_id,
                            "similarity": hit.similarity,
                            "language": hit.language,
                        },
                        text=hit.content,
                        role="vector",
                        index=0,
                    )
                    vector_results.append((doc, float(hit.similarity) * float(self._vector_weight or 1.0)))
            except VectorSearchError as exc:
                self._report_vector_issue("VectorSearchError", str(exc), scope, query=user_message)
            except Exception as exc:
                self._report_vector_issue("VectorSearchFailure", str(exc), scope, query=user_message)

        if not vector_results:
            _rag_log(f"RAG_Q: done scope={scope or 'global'} returned={len(lexical_out)} (lexical only)")
            return lexical_out

        combined = lexical_out + vector_results
        combined.sort(key=lambda x: x[1], reverse=True)

        deduped: List[Tuple[RagDoc, float]] = []
        seen: set[tuple[str, int]] = set()
        for doc, score in combined:
            key = (doc.session_id, hash(doc.text))
            if key in seen:
                continue
            seen.add(key)
            deduped.append((doc, score))
            if top_k and len(deduped) >= top_k:
                break

        _rag_log(
            f"RAG_Q: done scope={scope or 'global'} lexical={len(lexical_out)} vector={len(vector_results)} returned={len(deduped)}"
        )
        return deduped

    def _report_vector_issue(
        self,
        error_type: str,
        error_message: str,
        scope: Optional[str],
        query: Optional[str] = None,
    ) -> None:
        try:
            signature = f"{error_type}:{scope}:{error_message}"
            now = time.time()
            last = self._vector_error_cache.get(signature)
            if last and now - last < 60:
                return
            self._vector_error_cache[signature] = now
        except Exception:
            pass

        _rag_log(f"RAG_VEC: {error_type} scope={scope}: {error_message}")

        if get_bug_tracker is None:
            return

        try:
            tracker = get_bug_tracker()
            context = {
                "scope": scope or "global",
                "query": query or "",
                "vector_limit": self._vector_limit,
                "vector_weight": self._vector_weight,
            }
            tracker.capture_log_event(
                error_type=error_type,
                error_message=error_message,
                file_path="vector_backends/hcodex_client.py",
                function_name="HCodexVectorClient.search",
                context_excerpt=[json.dumps(context)],
                lineage_hint={"subsystem": "vector_rag"},
            )
        except Exception:
            pass

    # --------------------------- Utils ------------------------------------
    def _extract_chunks(self, chat: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
        """Return per-message chunks: list of (role, text) from last N messages."""
        if not chat:
            return []
        chunks: List[Tuple[str, str]] = []
        # Limit to last 64 messages for indexing to control size
        for msg in chat[-64:]:
            role = (msg.get('role') or '').strip()
            if role not in ('assistant', 'user', 'system'):
                continue
            content = (msg.get('content') or '').strip()
            if not content:
                continue
            # Keep each message as a chunk with provenance tags
            chunks.append((role, f"[{role}] {content}"))
        return chunks

    def _tokenize(self, text: str) -> List[str]:
        return _WORD_RE.findall((text or '').lower())

    # --------------------------- Persistence ------------------------------
    def _save_global_index(self):
        try:
            data = {
                'docs': [
                    {
                        'session_id': d.session_id,
                        'saved_at': d.saved_at,
                        'meta': d.meta,
                        'text': d.text,
                        'role': d.role,
                        'index': d.index,
                    }
                    for d in self._global_index
                ],
                'df': self._global_df,
            }
            self._global_index_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._global_index_path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception:
            pass

    def load_global_index(self):
        try:
            if not self._global_index_path.exists():
                return False
            with open(self._global_index_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._global_index = [
                RagDoc(
                    session_id=rec.get('session_id',''),
                    saved_at=rec.get('saved_at',''),
                    meta=rec.get('meta') or {},
                    text=rec.get('text') or '',
                    role=rec.get('role','context'),
                    index=int(rec.get('index', -1)),
                ) for rec in data.get('docs', [])
            ]
            self._global_df = data.get('df', {})
            return True
        except Exception:
            return False

    def _save_project_index(self, project_name: str):
        try:
            proj_dir = self._project_index_dir / (project_name or '')
            proj_dir.mkdir(parents=True, exist_ok=True)
            path = proj_dir / 'rag_index.json'
            data = {
                'docs': [
                    {
                        'session_id': d.session_id,
                        'saved_at': d.saved_at,
                        'meta': d.meta,
                        'text': d.text,
                        'role': d.role,
                        'index': d.index,
                    }
                    for d in self._project_indexes.get(project_name) or []
                ],
                'df': self._project_df.get(project_name) or {},
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception:
            pass

    def load_project_index(self, project_name: str) -> bool:
        try:
            path = self._project_index_dir / (project_name or '') / 'rag_index.json'
            if not path.exists():
                return False
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            docs = [
                RagDoc(
                    session_id=rec.get('session_id',''),
                    saved_at=rec.get('saved_at',''),
                    meta=rec.get('meta') or {},
                    text=rec.get('text') or '',
                    role=rec.get('role','context'),
                    index=int(rec.get('index', -1)),
                ) for rec in data.get('docs', [])
            ]
            self._project_indexes[project_name] = docs
            self._project_df[project_name] = data.get('df', {})
            return True
        except Exception:
            return False
