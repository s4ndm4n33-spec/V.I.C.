# core/pipeline.py
from __future__ import annotations

import traceback
from pathlib import Path

from core.config import VICConfig, PipelineResult, Session
from core.detector import detect_and_parse
from core.extractor import extract_all
from core.project import build_project_summary
from output.jsonl_writer import write_jsonl
from output.pdf_writer import write_pdf


class Pipeline:
    """Orchestrates the full V.I.C. processing run.

    Stages:
      1. DETECT   — identify provider from input file/folder structure
      2. PARSE    — extract raw sessions into normalized Session objects
      3. EXTRACT  — pull decisions, bugs, fixes, questions from each session
      4. PROJECT  — build cross-session project summary
      5. OUTPUT   — write PDF and/or JSONL
    """

    def __init__(self, config: VICConfig) -> None:
        self.config = config

    def run(self) -> PipelineResult:
        cfg = self.config
        cfg.output_path.mkdir(parents=True, exist_ok=True)

        try:
            # ── Stage 1 + 2: Detect and Parse ──────────────────
            if cfg.verbose:
                print(f"[VIC] Scanning: {cfg.input_path}")

            sessions: list[Session] = detect_and_parse(cfg.input_path, cfg)

            if not sessions:
                return PipelineResult(
                    success=False,
                    error="No conversations found in input. Check the file format."
                )

            if cfg.verbose:
                print(f"[VIC] Found {len(sessions)} sessions across "
                      f"{len(set(s.provider for s in sessions))} provider(s)")

            # ── Stage 3: Extract ────────────────────────────────
            sessions = extract_all(sessions, cfg)

            # ── Stage 4: Project Summary ────────────────────────
            project = build_project_summary(sessions, cfg)

            # ── Stage 5: Output ─────────────────────────────────
            pdf_path = None
            jsonl_path = None

            if cfg.generate_jsonl:
                jsonl_path = write_jsonl(sessions, project, cfg)
                if cfg.verbose:
                    print(f"[VIC] JSONL written: {jsonl_path}")

            if cfg.generate_pdf:
                pdf_path = write_pdf(sessions, project, cfg)
                if cfg.verbose:
                    print(f"[VIC] PDF written: {pdf_path}")

            return PipelineResult(
                success=True,
                sessions_processed=len(sessions),
                pdf_path=str(pdf_path) if pdf_path else None,
                jsonl_path=str(jsonl_path) if jsonl_path else None,
            )

        except Exception as exc:
            if cfg.verbose:
                traceback.print_exc()
            return PipelineResult(success=False, error=str(exc))
