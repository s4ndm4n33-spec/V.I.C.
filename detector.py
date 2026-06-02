# core/detector.py
from __future__ import annotations

import zipfile
from pathlib import Path

from core.config import VICConfig, Session
from parsers.gemini import parse_gemini_takeout
from parsers.chatgpt import parse_chatgpt_export
from parsers.claude import parse_claude_export
from parsers.generic import parse_generic_json


def detect_and_parse(input_path: Path, cfg: VICConfig) -> list[Session]:
    """Auto-detect provider and parse all conversations.

    Handles:
      - Google Takeout ZIP (Gemini history)
      - ChatGPT export ZIP
      - Folder of Claude JSON exports
      - Single JSON file
      - Mixed folder (multiple formats)
    """
    sessions: list[Session] = []

    if input_path.is_file():
        if input_path.suffix.lower() == ".zip":
            sessions.extend(_parse_zip(input_path, cfg))
        elif input_path.suffix.lower() == ".json":
            sessions.extend(_parse_single_json(input_path, cfg))
        else:
            print(f"[VIC] Unsupported file type: {input_path.suffix}")

    elif input_path.is_dir():
        sessions.extend(_parse_directory(input_path, cfg))

    # Filter by minimum length
    sessions = [s for s in sessions
                if len(s.full_text) >= cfg.min_length]

    # Sort chronologically
    sessions.sort(key=lambda s: s.date)

    return sessions


def _parse_zip(zip_path: Path, cfg: VICConfig) -> list[Session]:
    """Detect ZIP type and route to correct parser."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()

    # Google Takeout structure contains "Takeout/" prefix
    if any("Takeout/" in n for n in names):
        if cfg.verbose:
            print(f"[VIC] Detected: Google Takeout ZIP")
        return parse_gemini_takeout(zip_path, cfg)

    # ChatGPT export contains conversations.json at root
    if any(n == "conversations.json" for n in names):
        if cfg.verbose:
            print(f"[VIC] Detected: ChatGPT export ZIP")
        return parse_chatgpt_export(zip_path, cfg)

    # Unknown ZIP — try generic parsing
    if cfg.verbose:
        print(f"[VIC] Unknown ZIP format — attempting generic parse")
    return _try_generic_zip(zip_path, cfg)


def _try_generic_zip(zip_path: Path, cfg: VICConfig) -> list[Session]:
    """Try to extract JSON files from unknown ZIP and parse generically."""
    import json
    import io

    sessions = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            if not name.endswith(".json"):
                continue
            try:
                data = json.loads(zf.read(name).decode("utf-8", errors="replace"))
                found = parse_generic_json(data, source=name, cfg=cfg)
                sessions.extend(found)
            except Exception:
                continue
    return sessions


def _parse_single_json(json_path: Path, cfg: VICConfig) -> list[Session]:
    """Parse a single JSON file — detect format."""
    import json

    try:
        data = json.loads(json_path.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        print(f"[VIC] Could not parse {json_path.name}: {e}")
        return []

    # Claude export is a list of messages with "uuid" field
    if isinstance(data, dict) and "uuid" in data:
        return parse_claude_export(data, source=str(json_path), cfg=cfg)

    # ChatGPT single conversation
    if isinstance(data, dict) and "mapping" in data:
        from parsers.chatgpt import parse_chatgpt_conversation
        s = parse_chatgpt_conversation(data)
        return [s] if s else []

    return parse_generic_json(data, source=str(json_path), cfg=cfg)


def _parse_directory(dir_path: Path, cfg: VICConfig) -> list[Session]:
    """Parse a directory — handle mixed formats."""
    sessions = []

    for item in sorted(dir_path.iterdir()):
        if item.is_file():
            if item.suffix.lower() == ".zip":
                sessions.extend(_parse_zip(item, cfg))
            elif item.suffix.lower() == ".json":
                sessions.extend(_parse_single_json(item, cfg))
        elif item.is_dir():
            # Recurse one level
            sessions.extend(_parse_directory(item, cfg))

    return sessions
