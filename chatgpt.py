# parsers/chatgpt.py
from __future__ import annotations

import json
import zipfile
from pathlib import Path
from datetime import datetime

from core.config import VICConfig, Session


def parse_chatgpt_export(zip_path: Path, cfg: VICConfig) -> list[Session]:
    """Parse ChatGPT export ZIP.

    ChatGPT export structure:
      conversations.json   ← list of all conversations
      message_feedback.json
      model_comparisons.json
      user.json
    """
    sessions = []

    with zipfile.ZipFile(zip_path, "r") as zf:
        if "conversations.json" not in zf.namelist():
            if cfg.verbose:
                print("[VIC] conversations.json not found in ChatGPT ZIP")
            return []

        raw = zf.read("conversations.json").decode("utf-8", errors="replace")
        conversations = json.loads(raw)

    if cfg.verbose:
        print(f"[VIC] ChatGPT: found {len(conversations)} conversations")

    for i, convo in enumerate(conversations):
        session = parse_chatgpt_conversation(convo, index=i)
        if session:
            sessions.append(session)

    return sessions


def parse_chatgpt_conversation(convo: dict, index: int = 0) -> Session | None:
    """Parse one ChatGPT conversation object."""
    if not isinstance(convo, dict):
        return None

    # Extract metadata
    title = convo.get("title") or f"ChatGPT Session {index + 1}"
    create_time = convo.get("create_time") or convo.get("update_time") or 0

    try:
        date = datetime.fromtimestamp(float(create_time)).strftime("%Y-%m-%d")
    except Exception:
        date = "0000-00-00"

    # ChatGPT stores messages in a "mapping" dict — a tree structure
    # We need to walk the tree to get ordered messages
    mapping = convo.get("mapping", {})
    turns = _extract_turns_from_mapping(mapping)

    if not turns:
        return None

    conv_id = convo.get("id") or f"chatgpt_{index:04d}"

    return Session(
        session_id=f"chatgpt_{conv_id[:20]}",
        provider="chatgpt",
        date=date,
        title=str(title)[:200],
        raw_turns=turns,
    )


def _extract_turns_from_mapping(mapping: dict) -> list[dict]:
    """Walk ChatGPT's tree mapping to extract ordered message turns."""
    if not mapping:
        return []

    # Find root node (no parent)
    root_id = None
    for node_id, node in mapping.items():
        if node.get("parent") is None:
            root_id = node_id
            break

    if not root_id:
        # Fallback: just grab all messages in insertion order
        return _extract_turns_flat(mapping)

    # Walk tree depth-first following children
    turns = []
    visited = set()

    def walk(node_id: str) -> None:
        if node_id in visited or node_id not in mapping:
            return
        visited.add(node_id)
        node = mapping[node_id]
        msg = node.get("message")
        if msg:
            turn = _extract_message_turn(msg)
            if turn:
                turns.append(turn)
        # Follow first child (linear conversation)
        children = node.get("children", [])
        for child_id in children:
            walk(child_id)

    walk(root_id)
    return turns


def _extract_turns_flat(mapping: dict) -> list[dict]:
    """Fallback: extract all messages without tree ordering."""
    turns = []
    for node in mapping.values():
        msg = node.get("message")
        if msg:
            turn = _extract_message_turn(msg)
            if turn:
                turns.append(turn)
    return turns


def _extract_message_turn(msg: dict) -> dict | None:
    """Extract role and content from a ChatGPT message object."""
    if not isinstance(msg, dict):
        return None

    author = msg.get("author", {})
    role = author.get("role", "unknown") if isinstance(author, dict) else "unknown"

    # Skip system messages
    if role == "system":
        return None

    content_obj = msg.get("content", {})
    content = ""

    if isinstance(content_obj, str):
        content = content_obj
    elif isinstance(content_obj, dict):
        parts = content_obj.get("parts", [])
        texts = []
        for part in parts:
            if isinstance(part, str):
                texts.append(part)
            elif isinstance(part, dict):
                t = part.get("text") or ""
                if t:
                    texts.append(str(t))
        content = " ".join(texts)

    content = content.strip()
    if not content:
        return None

    # Normalize role
    if role in ("user", "human"):
        role = "user"
    elif role in ("assistant", "gpt", "chatgpt"):
        role = "assistant"

    return {"role": role, "content": content}
