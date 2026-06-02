#!/usr/bin/env python3
# V.I.C. — Value In Conversation
# Cross-provider AI chat archive processor
# Author: Reed Richards (s4ndm4n33)
# License: BSL 1.1
#
# Usage:
#   python vic.py --input path/to/takeout.zip --output ./archive
#   python vic.py --input path/to/chatgpt_export.zip --output ./archive
#   python vic.py --input path/to/claude_exports/ --output ./archive
#   python vic.py --input path/to/mixed_folder/ --output ./archive --project "Sovereign Shards"

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core.pipeline import Pipeline
from core.config import VICConfig


def main() -> int:
    parser = argparse.ArgumentParser(
        description="V.I.C. — Value In Conversation. Turn AI chat history into project documentation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python vic.py --input ~/Downloads/takeout.zip --output ./my_project
  python vic.py --input ~/Downloads/chatgpt.zip --output ./my_project --project "My App"
  python vic.py --input ~/claude_exports/ --output ./my_project
  python vic.py --input ~/mixed/ --output ./my_project --project "Sovereign Shards" --pdf --jsonl
        """
    )
    parser.add_argument("--input", "-i", required=True,
                        help="Path to ZIP export, folder of exports, or single JSON file")
    parser.add_argument("--output", "-o", default="./vic_output",
                        help="Output directory (default: ./vic_output)")
    parser.add_argument("--project", "-p", default=None,
                        help="Project name for the archive (auto-detected if not set)")
    parser.add_argument("--pdf", action="store_true", default=True,
                        help="Generate PDF report (default: True)")
    parser.add_argument("--jsonl", action="store_true", default=True,
                        help="Generate JSONL archive (default: True)")
    parser.add_argument("--no-pdf", action="store_true",
                        help="Skip PDF generation")
    parser.add_argument("--no-jsonl", action="store_true",
                        help="Skip JSONL generation")
    parser.add_argument("--min-length", type=int, default=100,
                        help="Minimum conversation length in characters to include (default: 100)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    config = VICConfig(
        input_path=Path(args.input),
        output_path=Path(args.output),
        project_name=args.project,
        generate_pdf=args.pdf and not args.no_pdf,
        generate_jsonl=args.jsonl and not args.no_jsonl,
        min_length=args.min_length,
        verbose=args.verbose,
    )

    if not config.input_path.exists():
        print(f"[VIC ERROR] Input not found: {config.input_path}")
        return 1

    pipeline = Pipeline(config)
    result = pipeline.run()

    if result.success:
        print(f"\n[VIC] Done. {result.sessions_processed} sessions processed.")
        if result.pdf_path:
            print(f"[VIC] PDF:  {result.pdf_path}")
        if result.jsonl_path:
            print(f"[VIC] JSONL: {result.jsonl_path}")
        return 0
    else:
        print(f"\n[VIC ERROR] {result.error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
