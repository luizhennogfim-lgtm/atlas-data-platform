"""Command line entry point: python -m pipeline.cli <command>."""
from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from ingestion.config import get_settings
from ingestion.db import connect
from ingestion.generate_data import generate
from quality.report import write_report

from . import steps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="atlas")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="apply sql/init scripts (idempotent, never drops data)")
    gen = sub.add_parser("generate-data", help="write synthetic CSV files")
    gen.add_argument("--out", type=Path, default=None)
    gen.add_argument("--seed", type=int, default=42)
    run = sub.add_parser("run", help="run the full pipeline once")
    run.add_argument("--label", default=None, help="run label (default: UTC timestamp)")
    sub.add_parser("report", help="write reports/quality_report.md for the latest run")
    args = parser.parse_args(argv)
    settings = get_settings()

    if args.command == "init-db":
        print("applied:", steps.init_database(settings) or "nothing new")
    elif args.command == "generate-data":
        print(generate(args.out or settings.source_dir, seed=args.seed))
    elif args.command == "report":
        with connect(settings.dsn) as conn:
            print(write_report(conn, settings.reports_dir))
    elif args.command == "run":
        label = args.label or datetime.now(UTC).strftime("cli__%Y%m%dT%H%M%S")
        try:
            print("report:", steps.run_all(label, settings))
        except Exception as exc:
            print(f"PIPELINE FAILED: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
