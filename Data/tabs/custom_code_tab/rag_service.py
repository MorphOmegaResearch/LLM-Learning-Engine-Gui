"""
RagService - lightweight retrieval service for rag-enabled conversations.

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

    # --------------------------- Indexing ---------------------------------
    def refresh_index_global(self):
        if not self.chat_history_manager:
            self._global_index = []
            self._global_df = {}
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
            return
        docs: List[RagDoc] = []
        df: Dict[str, int] = {}
        for f in root.glob('*.json'):
            try:
                data = json.loads(f.read_text())
            except Exception:
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
            return []

        if scope:
            docs = self._project_indexes.get(scope) or []
            df = self._project_df.get(scope) or {}
        else:
            docs = self._global_index
            df = self._global_df
        n_docs = max(1, len(docs))

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
        out = scored[:top_k]

        # Optional rerank with context scorer
        if self.context_scorer and out:
            try:
                # Build candidate texts
                cand = [doc.text for doc, _ in out]
                # Use scorer to get quality; if available, reorder
                # Assume scorer.score_context returns dict with 'final_score'
                pairs = []
                for (doc, score), text in zip(out, cand):
                    sres = self.context_scorer.score_context([{"role":"system","content":text}])
                    q = float(sres.get('final_score', 0.0))
                    pairs.append((doc, score * (0.7 + 0.3 * (q/100.0))))
                pairs.sort(key=lambda x: x[1], reverse=True)
                out = pairs
            except Exception:
                pass
        return out

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
