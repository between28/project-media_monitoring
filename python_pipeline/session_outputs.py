from __future__ import annotations

import csv
import json
from copy import deepcopy
from datetime import datetime, time, timedelta
from pathlib import Path

from .analysis import (
    build_processed_snapshot,
    is_output_eligible_record,
    is_reference_relevant_record,
    is_representative_record,
    is_within_lookback,
)
from .briefing import build_briefing_overview_counts, build_briefing_package, build_reference_candidates
from .config import get_record_time
from .db import fetch_raw_articles
from .press_release import build_press_session_paths, save_press_session_metadata
from .utils import clean_display_title, format_readable_datetime, infer_display_source_name, parse_datetime


def initialize_press_session(profile: dict, config: dict, session_root: str | Path) -> dict[str, str]:
    session_paths = build_press_session_paths(profile, session_root)
    save_press_session_metadata(profile, config, session_paths)
    return session_paths


def build_session_daily_outputs(
    connection,
    profile: dict,
    config: dict,
    session_paths: dict[str, str],
    analysis_now: datetime,
    progress_callback=None,
    cancel_callback=None,
) -> dict:
    raw_records = fetch_raw_articles(connection)
    if not raw_records:
        return {"generated_days": [], "latest_briefing_path": "", "latest_reference_csv": "", "latest_reference_markdown": ""}

    release_time = parse_datetime(profile.get("release_datetime") or profile.get("release_date"), config["timezone"])
    if release_time is None:
        raise ValueError("Press release profile is missing release date/time")

    max_end_time = min(analysis_now, release_time + timedelta(days=3, hours=23, minutes=59, seconds=59))
    max_offset = max(0, min(3, (max_end_time.date() - release_time.date()).days))

    generated_days = []
    latest_briefing_path = ""
    latest_reference_csv = ""
    latest_reference_markdown = ""

    total_days = max_offset + 1
    if progress_callback:
        progress_callback(0, total_days, "")

    for offset in range(0, max_offset + 1):
        if cancel_callback:
            cancel_callback()
        snapshot_time = build_daily_snapshot_time(release_time, offset, max_end_time)
        snapshot_config = deepcopy(config)
        snapshot_config.setdefault("analysis", {})["referenceTime"] = snapshot_time.isoformat()
        snapshot_config["analysis"]["windowStartTime"] = release_time.isoformat()

        snapshot_raw, processed_records = build_processed_snapshot(raw_records, snapshot_config, fetch_bodies=False)
        reference_records = build_reference_candidates(snapshot_raw, snapshot_config, snapshot_time)
        overview_counts = build_briefing_overview_counts(
            snapshot_raw,
            snapshot_config,
            snapshot_time,
            reference_records=reference_records,
        )
        briefing_rows, briefing_text = build_briefing_package(
            processed_records,
            snapshot_config,
            snapshot_time,
            overview_counts=overview_counts,
            reference_records=reference_records,
        )
        reference_rows = build_reference_article_rows(snapshot_raw, snapshot_config)

        date_label = snapshot_time.astimezone(release_time.tzinfo).strftime("%Y-%m-%d")
        day_label = f"D+{offset}"

        briefing_path = Path(session_paths["briefings_dir"]) / f"{day_label}_{date_label}.md"
        briefing_path.write_text(briefing_text + "\n", encoding="utf-8")

        reference_markdown_path = Path(session_paths["references_dir"]) / f"{day_label}_{date_label}_기사목록.md"
        reference_csv_path = Path(session_paths["references_dir"]) / f"{day_label}_{date_label}_기사목록.csv"
        reference_markdown_path.write_text(render_reference_markdown(reference_rows, profile, snapshot_time), encoding="utf-8")
        write_reference_csv(reference_csv_path, reference_rows)

        latest_briefing_path = str(briefing_path)
        latest_reference_csv = str(reference_csv_path)
        latest_reference_markdown = str(reference_markdown_path)

        generated_days.append(
            {
                "day_label": day_label,
                "date_label": date_label,
                "analysis_reference_time": snapshot_time.isoformat(),
                "briefing_path": str(briefing_path),
                "reference_markdown_path": str(reference_markdown_path),
                "reference_csv_path": str(reference_csv_path),
                "article_count": len(reference_rows),
                "briefing_section_count": len(briefing_rows),
            }
        )
        if progress_callback:
            progress_callback(offset + 1, total_days, day_label)

    if cancel_callback:
        cancel_callback()
    if latest_briefing_path:
        Path(session_paths["latest_briefing"]).write_text(Path(latest_briefing_path).read_text(encoding="utf-8"), encoding="utf-8")
    if latest_reference_markdown:
        Path(session_paths["latest_reference_markdown"]).write_text(
            Path(latest_reference_markdown).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    if latest_reference_csv:
        Path(session_paths["latest_reference_csv"]).write_text(Path(latest_reference_csv).read_text(encoding="utf-8-sig"), encoding="utf-8-sig")

    summary_path = Path(session_paths["daily_outputs_json"])
    summary_path.write_text(
        json.dumps(
            {
                "session_id": session_paths["session_id"],
                "generated_at": analysis_now.isoformat(),
                "days": generated_days,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "generated_days": generated_days,
        "latest_briefing_path": latest_briefing_path,
        "latest_reference_csv": latest_reference_csv,
        "latest_reference_markdown": latest_reference_markdown,
        "summary_path": str(summary_path),
    }


def build_daily_snapshot_time(release_time: datetime, offset: int, max_end_time: datetime) -> datetime:
    snapshot_date = release_time.date() + timedelta(days=offset)
    end_of_day = datetime.combine(snapshot_date, time(23, 59, 59), tzinfo=release_time.tzinfo)
    return min(end_of_day, max_end_time)


def build_reference_article_rows(raw_records: list[dict], config: dict) -> list[dict]:
    analysis_now = parse_datetime(config.get("analysis", {}).get("referenceTime"), config["timezone"])
    lookback_start = parse_datetime(config.get("analysis", {}).get("windowStartTime"), config["timezone"])
    if analysis_now is None or lookback_start is None:
        return []

    candidates = []
    for record in raw_records:
        if not is_representative_record(record):
            continue
        if not is_output_eligible_record(record):
            continue
        if not is_within_lookback(record, lookback_start, analysis_now, config["timezone"]):
            continue
        if not is_reference_relevant_record(record, config):
            continue
        candidates.append(record)

    candidates.sort(
        key=lambda record: (
            get_record_time(record, config["timezone"]).timestamp() if get_record_time(record, config["timezone"]) else 0,
            float(record.get("importance_score", 0) or 0),
        ),
        reverse=True,
    )

    rows = []
    for index, record in enumerate(candidates, start=1):
        timestamp = get_record_time(record, config["timezone"])
        rows.append(
            {
                "순번": index,
                "언론사": infer_display_source_name(record.get("source_name", ""), record.get("title", ""), record.get("summary", "")),
                "기사 제목": clean_display_title(record.get("title", ""), record.get("source_name", ""), record.get("summary", "")),
                "보도일시": format_readable_datetime(timestamp, config["timezone"]) if timestamp else "",
                "기사 링크": record.get("link", "") or "",
            }
        )
    return rows


def render_reference_markdown(rows: list[dict], profile: dict, snapshot_time: datetime) -> str:
    lines = [
        "# 참고자료 기사 목록",
        "",
        f"- 보도자료 제목: {profile.get('title', '')}",
        f"- 기준 시점: {snapshot_time.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        f"- 기사 수: {len(rows)}",
        "",
        "| 순번 | 언론사 | 기사 제목 | 보도일시 | 기사 링크 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        link_cell = f"<{row['기사 링크']}>" if row.get("기사 링크") else ""
        lines.append(
            f"| {row['순번']} | {escape_markdown(row['언론사'])} | {escape_markdown(row['기사 제목'])} | {row['보도일시']} | {link_cell} |"
        )
    return "\n".join(lines) + "\n"


def escape_markdown(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def write_reference_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["순번", "언론사", "기사 제목", "보도일시", "기사 링크"])
        writer.writeheader()
        writer.writerows(rows)
