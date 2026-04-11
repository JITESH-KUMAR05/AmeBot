# session management 
# last 10 messages 
# keeping in in memory right now 
# later at scale we can go with Redis for persistance amd sharing across multiple servers

import uuid
from collections import defaultdict
from config import MAX_HISTORY

_sessions: dict[str, list[dict]] = defaultdict(list)

def create_session() -> str:
    """
    creates a new session id 
    """
    return str(uuid.uuid4())

def get_history(session_id: str) -> list[dict]:
    """
    returns the full chat history for a session
    returns  an empty list if the session is not started yet
    Format : [{"role":"user", "content":"..."}, {"role":"assistant", "content":"..."}]
    """
    return list(_sessions[session_id]) ## returning a copy not the reference 

def add_message(session_id: str, role:str, content:str) -> None:
    """
    Append a message to the session history
    """

    _sessions[session_id].append({"role": role, "content": content})

    # trim history to max_history
    if len(_sessions[session_id]) > MAX_HISTORY:
        _sessions[session_id] = _sessions[session_id][-MAX_HISTORY:]

def session_exists(session_id: str) -> bool:
    """
    check if session id is already in use
    """
    return session_id in _sessions

def clear_session(session_id: str) -> None:
    """
    clears the session history used for logout or reset functions
    """
    if session_id in _sessions:
        del _sessions[session_id]