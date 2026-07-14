import json
import time
from pathlib import Path

# Use a relative path from the project root
SESSIONS_DIR = Path("data/chat_sessions")

def _ensure_dir():
    if not SESSIONS_DIR.exists():
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

def save_session(session_id: str, title: str, messages: list):
    """Saves a chat session to disk as a JSON file, keeping only the 5 most recent."""
    _ensure_dir()
    filepath = SESSIONS_DIR / f"{session_id}.json"
    
    data = {
        "session_id": session_id,
        "title": title,
        "updated_at": time.time(),
        "messages": messages
    }
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        
    # Enforce FIFO limit of 5 sessions
    _enforce_limit(5)

def _enforce_limit(limit: int):
    """Deletes oldest sessions to keep the total count <= limit."""
    files = list(SESSIONS_DIR.glob("*.json"))
    if len(files) <= limit:
        return
        
    # Sort files by modification time (oldest first)
    files.sort(key=lambda x: x.stat().st_mtime)
    
    # Delete the oldest files until we are at the limit
    files_to_delete = len(files) - limit
    for i in range(files_to_delete):
        try:
            files[i].unlink()
        except OSError:
            pass

def load_session(session_id: str) -> dict | None:
    """Loads a chat session by ID."""
    filepath = SESSIONS_DIR / f"{session_id}.json"
    if not filepath.exists():
        return None
        
    try:
        with open(filepath, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def get_recent_sessions(limit: int = 5) -> list[dict]:
    """Returns metadata for the most recent sessions."""
    _ensure_dir()
    files = list(SESSIONS_DIR.glob("*.json"))
    sessions = []
    
    for file in files:
        try:
            with open(file, encoding="utf-8") as f:
                data = json.load(f)
                sessions.append({
                    "session_id": data["session_id"],
                    "title": data.get("title", "Untitled Chat"),
                    "updated_at": data.get("updated_at", file.stat().st_mtime),
                })
        except Exception:
            continue
            
    # Sort by updated_at descending (newest first)
    sessions.sort(key=lambda x: x["updated_at"], reverse=True)
    return sessions[:limit]

def delete_session(session_id: str):
    """Deletes a specific chat session."""
    filepath = SESSIONS_DIR / f"{session_id}.json"
    if filepath.exists():
        try:
            filepath.unlink()
        except OSError:
            pass
