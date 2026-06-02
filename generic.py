# parsers/generic.py
from __future__ import annotations

from core.config import VICConfig, Session


def parse_generic_json(data: dict | list, source: str, cfg: VICConfig) -> list[Session]:
    """Best-effort parser for unknown JSON conversation formats.

    Tries to find message arrays with role/content pairs.
    """
    sessions = []

    if isinstance(data, list):
        # Could be a list of conversations or a list of messages
        # Heuristic: if first item has "role"/"content" it's a message list
        if data and isinstance(data[0], dict):
            if "role" in data[0] or "content" in data[0] or "text" in data[0]:
                # It's a flat message list — treat as one session
                session = _messages_to_session(data, source, index=0)
                if session:
                    sessions.append(session)
                return sessions
            else:
                # List of conversation objects
                for i, item in enumerate(data):
                    session = _try_extract_conversation(item, source, index=i)
                    if session:
                        sessions.append(session)

    elif isinstance(data, dict):
        # Try common wrapper keys
        for key in ("messages", "conversation", "turns", "history", "chats"):
            val = data.get(key)
            if isinstance(val, list) and val:
                session = _messages_to_session(val, source, index=0,
                                               title=data.get("title") or key)
                if session:
                    sessions.append(session)
                return sessions

        # Single conversation object
        session = _try_extract_conversation(data, source, index=0)
        if session:
            sessions.append(session)

    return sessions


def _try_extract_conversation(obj: dict, source: str, index: int) -> Session | None:
    if not isinstance(obj, dict):
        return None

    title = (obj.get("title") or obj.get("name")
             or obj.get("subject") or f"Session {index + 1}")

    # Find message list
    messages = None
    for key in ("messages", "turns", "conversation", "history", "content"):
        val = obj.get(key)
        if isinstance(val, list) and val:
            messages = val
            break

    if not messages:
        return None

    return _messages_to_session(messages, source, index=index, title=str(title))


def _messages_to_session(messages: list, source: str,
                         index: int, title: str = "") -> Session | None:
    turns = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role") or msg.get("sender") or msg.get("author") or "unknown"
        role = "user" if str(role).lower() in ("user", "human", "you") else "assistant"
        content = (msg.get("content") or msg.get("text")
                   or msg.get("message") or "")
        if isinstance(content, list):
            content = " ".join(
                p if isinstance(p, str)
                else (p.get("text") or "") if isinstance(p, dict)
                else ""
                for p in content
            )
        content = str(content).strip()
        if content:
            turns.append({"role": role, "content": content})

    if not turns:
        return None

    return Session(
        session_id=f"unknown_{index:04d}",
        provider="unknown",
        date="0000-00-00",
        title=title or f"Session {index + 1}",
        raw_turns=turns,
    )
