"""
Projects Manager - simple project storage for conversations
"""

from pathlib import Path
from datetime import datetime
import json
from typing import Optional, Dict, Any, List

PROJECTS_ROOT = Path("Data/projects")
PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)


def ensure_project(name: str) -> Path:
    p = PROJECTS_ROOT / safe_name(name)
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_name(n: str) -> str:
    return "".join(c for c in (n or "") if c.isalnum() or c in ('_', '-', ' ')).replace(' ', '_')


def list_projects() -> List[str]:
    return sorted([d.name for d in PROJECTS_ROOT.iterdir() if d.is_dir()])


def list_conversations(project: str) -> List[Dict[str, Any]]:
    root = ensure_project(project)
    out = []
    for f in root.glob("*.json"):
        try:
            rec = json.loads(f.read_text())
            out.append({
                "session_id": rec.get("session_id", f.stem),
                "model_name": rec.get("model_name", "unknown"),
                "message_count": rec.get("message_count", 0),
                "saved_at": rec.get("saved_at", ""),
                "metadata": rec.get("metadata", {}),
            })
        except Exception:
            pass
    out.sort(key=lambda x: x.get("saved_at",""), reverse=True)
    return out


def save_conversation(project: str, model_name: str, chat_history: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None, session_name: Optional[str] = None) -> str:
    root = ensure_project(project)
    if not session_name:
        session_name = f"{safe_name(model_name)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    rec = {
        "session_id": session_name,
        "model_name": model_name,
        "chat_history": chat_history,
        "message_count": len(chat_history),
        "saved_at": datetime.now().isoformat(),
        "metadata": metadata or {},
    }
    (root / f"{session_name}.json").write_text(json.dumps(rec, indent=2))
    return session_name

