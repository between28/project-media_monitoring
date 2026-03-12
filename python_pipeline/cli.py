from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .analysis import run_analysis
from .briefing import generate_briefing
from .collector import collect_articles
from .config import deep_merge, load_json_override, load_runtime_config
from .db import connect, ensure_schema, seed_config_tables
from .defaults import clone_default_config
from .press_release import (
    build_config_from_press_release,
    build_press_session_paths,
    load_session_manual_overrides,
    load_press_release_profile,
    save_press_release_outputs,
    save_press_session_metadata,
)
from .session_outputs import build_session_daily_outputs
from .utils import parse_datetime


DEFAULT_DB_PATH = "data/media_monitoring.sqlite3"
DEFAULT_SESSION_ROOT = "sessions"


def add_common_options(parser: argparse.ArgumentParser, use_defaults: bool) -> None:
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH if use_defaults else argparse.SUPPRESS, help="SQLite database path")
    parser.add_argument("--config", default=None if use_defaults else argparse.SUPPRESS, help="Optional JSON override config")
    parser.add_argument(
        "--analysis-reference-time",
        default=None if use_defaults else argparse.SUPPRESS,
        help="Override analysis reference time. Use 'now' for current time.",
    )
    parser.add_argument("--log-level", default="INFO" if use_defaults else argparse.SUPPRESS, help="Logging level")
    parser.add_argument(
        "--press-release",
        default=None if use_defaults else argparse.SUPPRESS,
        help="HWPX press release file or folder path. When set, topic-specific queries/keywords are derived from the press release.",
    )
    parser.add_argument(
        "--session-root",
        default=DEFAULT_SESSION_ROOT if use_defaults else argparse.SUPPRESS,
        help="Root directory for press-release session outputs",
    )


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

    derive_parser = subparsers.add_parser(
        "derive-press-release",
        help="Extract title/date/keywords/queries from an HWPX press release and write JSON outputs",
        parents=[command_common],
    )
    derive_parser.add_argument("--output-dir", default=None, help="Directory for derived JSON/markdown outputs")

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

    press_release_profile = None
    session_paths = None
    manual_overrides = None
    db_path = Path(args.db_path)

    if args.press_release:
        press_release_profile = load_press_release_profile(args.press_release)
        session_paths = build_press_session_paths(press_release_profile, args.session_root)
        if args.command != "derive-press-release":
            db_path = Path(session_paths["db_path"])

    if args.command == "derive-press-release":
        if not press_release_profile:
            parser.error("--press-release is required for derive-press-release")

        if not args.output_dir:
            manual_overrides = load_session_manual_overrides(session_paths)
        derived_config = build_config_from_press_release(press_release_profile, manual_overrides)
        if args.output_dir:
            output_paths = save_press_release_outputs(press_release_profile, derived_config, args.output_dir)
        else:
            output_paths = save_press_session_metadata(press_release_profile, derived_config, session_paths, manual_overrides)
            output_paths["session_dir"] = session_paths["session_dir"]

        print("Derived press release profile:")
        for key, value in output_paths.items():
            print(f"- {key}: {value}")
        return 0

    connection = connect(db_path)
    ensure_schema(connection)

    if args.command == "init-db":
        ensure_runtime(connection, args.config, reset_config=args.reset_config)
        print(f"Initialized SQLite database at {db_path}")
        return 0

    if press_release_profile:
        manual_overrides = load_session_manual_overrides(session_paths)
        config = build_config_from_press_release(press_release_profile, manual_overrides)
        if args.analysis_reference_time is not None:
            config.setdefault("analysis", {})["referenceTime"] = "" if args.analysis_reference_time == "now" else args.analysis_reference_time
        seed_config_tables(connection, config, reset=True)
        save_press_session_metadata(press_release_profile, config, session_paths, manual_overrides)
    else:
        ensure_runtime(connection, args.config, reset_config=False)
        config = load_runtime_config(connection, args.config, args.analysis_reference_time)

    analysis_now = resolve_analysis_now(config)

    if args.command == "collect":
        result = collect_articles(connection, config, source_limit=args.source_limit)
        print(f"Collected {result['prepared_count']} candidate rows and inserted {result['inserted_count']} new rows into {db_path}")
        return 0

    if args.command == "analyze":
        processed = run_analysis(connection, config, fetch_bodies=not args.skip_body_fetch)
        print(f"Processed {len(processed)} ranked articles")
        return 0

    if args.command == "brief":
        output_path = prepare_output_path(args.output_file)
        briefing_text = generate_briefing(connection, config, output_path)
        session_summary = maybe_build_session_outputs(connection, press_release_profile, config, session_paths, analysis_now)
        print(briefing_text)
        if session_summary:
            print_session_summary(session_paths, session_summary)
        return 0

    if args.command == "run":
        collect_result = collect_articles(connection, config, source_limit=args.source_limit)
        processed = run_analysis(connection, config, fetch_bodies=not args.skip_body_fetch)
        output_path = prepare_output_path(args.output_file)
        briefing_text = generate_briefing(connection, config, output_path)
        session_summary = maybe_build_session_outputs(connection, press_release_profile, config, session_paths, analysis_now)

        print(
            f"Collected {collect_result['prepared_count']} candidate rows, inserted {collect_result['inserted_count']} new rows, ranked {len(processed)} articles.\n"
        )
        print(briefing_text)
        if session_summary:
            print_session_summary(session_paths, session_summary)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


def maybe_build_session_outputs(connection, press_release_profile, config: dict, session_paths: dict | None, analysis_now: datetime):
    if not press_release_profile or not session_paths:
        return None
    return build_session_daily_outputs(connection, press_release_profile, config, session_paths, analysis_now)


def print_session_summary(session_paths: dict[str, str], session_summary: dict) -> None:
    print("\nSession outputs:")
    print(f"- session_dir: {session_paths['session_dir']}")
    print(f"- manual_queries: {session_paths['queries_manual_json']}")
    print(f"- effective_config: {session_paths['config_effective_json']}")
    print(f"- latest_briefing: {session_summary['latest_briefing_path']}")
    print(f"- latest_reference_csv: {session_summary['latest_reference_csv']}")
    print(f"- latest_reference_markdown: {session_summary['latest_reference_markdown']}")


def prepare_output_path(output_file: str | None) -> str | None:
    if not output_file:
        return None
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


def resolve_analysis_now(config: dict) -> datetime:
    reference = config.get("analysis", {}).get("referenceTime")
    if reference:
        parsed = parse_datetime(reference, config.get("timezone", "Asia/Seoul"))
        if parsed:
            return parsed
    return datetime.now(tz=ZoneInfo(config.get("timezone", "Asia/Seoul")))
