from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .analysis import run_analysis
from .briefing import generate_briefing
from .collector import collect_articles
from .config import deep_merge, load_json_override, load_runtime_config
from .db import connect, ensure_schema, seed_config_tables
from .defaults import clone_default_config


DEFAULT_DB_PATH = "data/media_monitoring.sqlite3"


def add_common_options(parser: argparse.ArgumentParser, use_defaults: bool) -> None:
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH if use_defaults else argparse.SUPPRESS, help="SQLite database path")
    parser.add_argument("--config", default=None if use_defaults else argparse.SUPPRESS, help="Optional JSON override config")
    parser.add_argument(
        "--analysis-reference-time",
        default=None if use_defaults else argparse.SUPPRESS,
        help="Override analysis reference time. Use 'now' for current time.",
    )
    parser.add_argument("--log-level", default="INFO" if use_defaults else argparse.SUPPRESS, help="Logging level")


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    add_common_options(common, use_defaults=True)
    command_common = argparse.ArgumentParser(add_help=False)
    add_common_options(command_common, use_defaults=False)

    parser = argparse.ArgumentParser(description="MOLIT media monitoring Python pipeline", parents=[common])

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-db", help="Create SQLite schema and seed config tables", parents=[command_common])
    init_parser.add_argument("--reset-config", action="store_true", help="Reset config tables to defaults or override file")

    collect_parser = subparsers.add_parser("collect", help="Collect RSS/news items into SQLite", parents=[command_common])
    collect_parser.add_argument("--source-limit", type=int, help="Only use the first N enabled sources")

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Run dedup, scoring, body fetch, frame classification, ranking",
        parents=[command_common],
    )
    analyze_parser.add_argument("--skip-body-fetch", action="store_true", help="Skip article body fetch stage")

    brief_parser = subparsers.add_parser("brief", help="Generate briefing text from processed articles", parents=[command_common])
    brief_parser.add_argument("--output-file", help="Optional markdown/text output path")

    run_parser = subparsers.add_parser("run", help="Collect, analyze, and generate briefing in one run", parents=[command_common])
    run_parser.add_argument("--source-limit", type=int, help="Only use the first N enabled sources")
    run_parser.add_argument("--skip-body-fetch", action="store_true", help="Skip article body fetch stage")
    run_parser.add_argument("--output-file", help="Optional markdown/text output path")

    return parser


def configure_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), format="%(levelname)s %(message)s")


def build_seed_config(config_path: str | None) -> dict:
    config = clone_default_config()
    override = load_json_override(config_path)
    if override:
        deep_merge(config, override)
    return config


def ensure_runtime(connection, config_path: str | None, reset_config: bool = False) -> None:
    seed_config_tables(connection, build_seed_config(config_path), reset=reset_config)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)

    connection = connect(args.db_path)
    ensure_schema(connection)

    if args.command == "init-db":
        ensure_runtime(connection, args.config, reset_config=args.reset_config)
        print(f"Initialized SQLite database at {Path(args.db_path)}")
        return 0

    ensure_runtime(connection, args.config, reset_config=False)
    config = load_runtime_config(connection, args.config, args.analysis_reference_time)

    if args.command == "collect":
        result = collect_articles(connection, config, source_limit=args.source_limit)
        print(
            f"Collected {result['prepared_count']} candidate rows and inserted {result['inserted_count']} new rows into {Path(args.db_path)}"
        )
        return 0

    if args.command == "analyze":
        processed = run_analysis(connection, config, fetch_bodies=not args.skip_body_fetch)
        print(f"Processed {len(processed)} ranked articles")
        return 0

    if args.command == "brief":
        output_path = prepare_output_path(args.output_file)
        briefing_text = generate_briefing(connection, config, output_path)
        print(briefing_text)
        return 0

    if args.command == "run":
        collect_result = collect_articles(connection, config, source_limit=args.source_limit)
        processed = run_analysis(connection, config, fetch_bodies=not args.skip_body_fetch)
        output_path = prepare_output_path(args.output_file)
        briefing_text = generate_briefing(connection, config, output_path)
        print(
            f"Collected {collect_result['prepared_count']} candidate rows, inserted {collect_result['inserted_count']} new rows, ranked {len(processed)} articles.\n"
        )
        print(briefing_text)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


def prepare_output_path(output_file: str | None) -> str | None:
    if not output_file:
        return None
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)
