# In-memory session history.
#   - last MAX_HISTORY messages per session
#   - at most MAX_SESSIONS sessions; the least-recently-used is evicted first
#   - a plain OrderedDict (NOT defaultdict): reading an unknown id must not
#     create it, otherwise a client sending random session_ids grows memory
#     without bound.
# At scale this is the piece to replace with Redis for persistence + sharing.

import uuid
from collections import OrderedDict

from config import MAX_HISTORY, MAX_SESSIONS

_sessions: "OrderedDict[str, list[dict]]" = OrderedDict()


def create_session() -> str:
    """Return a fresh session id. The entry is created lazily on first add_message."""
    return str(uuid.uuid4())


def get_history(session_id: str) -> list[dict]:
    """Return a COPY of the session's history, or [] if the session is unknown.
    Does not create the session."""
    return list(_sessions.get(session_id, []))


def add_message(session_id: str, role: str, content: str) -> None:
    """Append a message, creating the session if needed, evicting the oldest
    session when over capacity, and trimming history to MAX_HISTORY."""
    history = _sessions.get(session_id)
    if history is None:
        while len(_sessions) >= MAX_SESSIONS:
            _sessions.popitem(last=False)  # evict least-recently-used
        history = []
        _sessions[session_id] = history

    history.append({"role": role, "content": content})
    if len(history) > MAX_HISTORY:
        del history[:-MAX_HISTORY]

    _sessions.move_to_end(session_id)  # mark as most-recently-used


def session_exists(session_id: str) -> bool:
    return session_id in _sessions


def clear_session(session_id: str) -> None:
    """Drop a session's history. Idempotent. Used by DELETE /session/{id}."""
    _sessions.pop(session_id, None)
