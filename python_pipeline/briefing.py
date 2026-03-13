from __future__ import annotations

from .analysis import (
    build_theme_label_from_key,
    derive_theme_key,
    is_output_eligible_record,
    is_reference_relevant_record,
    is_representative_record,
    is_within_lookback,
)
from .config import get_analysis_now, get_lookback_start
from .db import fetch_processed_articles, fetch_raw_articles, replace_briefing_sections
from .utils import clean_display_title, format_datetime, infer_display_source_name, limit_text


def generate_briefing(connection, config: dict, output_path: str | None = None) -> str:
    candidates = fetch_processed_articles(connection)
    raw_records = fetch_raw_articles(connection)
    analysis_now = get_analysis_now(config)
    reference_records = build_reference_candidates(raw_records, config, analysis_now)
    overview_counts = build_briefing_overview_counts(raw_records, config, analysis_now, reference_records=reference_records)
    rows, full_text = build_briefing_package(
        candidates,
        config,
        analysis_now,
        overview_counts=overview_counts,
        reference_records=reference_records,
    )
    replace_briefing_sections(connection, rows)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(full_text + "\n")
    return full_text


def build_briefing_package(
    candidates: list[dict],
    config: dict,
    analysis_now,
    overview_counts: dict | None = None,
    reference_records: list[dict] | None = None,
) -> tuple[list[dict], str]:
    generated_time = format_datetime(analysis_now, config["timezone"])
    top_candidates = candidates[: int(config.get("collection", {}).get("maxBriefingArticles", 12))]
    media_records = list(reference_records or [])
    theme_groups = build_theme_groups_for_briefing(media_records, config)

    section_payloads = [
        ("우리부 보도자료", build_press_release_summary_section(config)),
        ("언론보도 현황", build_media_status_section(media_records, top_candidates, analysis_now)),
    ]

    rows = []
    for index, (section_name, content) in enumerate(section_payloads, start=1):
        rows.append(
            {
                "section_order": index,
                "generated_time": generated_time,
                "topic_name": config["topic"]["name"],
                "section_name": section_name,
                "content": content,
                "supporting_articles": build_supporting_articles(top_candidates),
                "notes": build_briefing_notes(overview_counts, theme_groups),
            }
        )

    full_text = "\n\n".join(f"[{row['section_name']}]\n{row['content']}" for row in rows)
    rows.append(
        {
            "section_order": len(rows) + 1,
            "generated_time": generated_time,
            "topic_name": config["topic"]["name"],
            "section_name": "전체본",
            "content": full_text,
            "supporting_articles": build_supporting_articles(top_candidates),
            "notes": build_briefing_notes(overview_counts, theme_groups),
        }
    )
    return rows, full_text


def build_press_release_summary_section(config: dict) -> str:
    summary_sentences = [
        str(sentence).strip()
        for sentence in config.get("pressRelease", {}).get("summarySentences", [])
        if str(sentence).strip()
    ]
    if summary_sentences:
        return "\n".join(summary_sentences[:2])

    topic_title = str(config.get("pressRelease", {}).get("title") or config.get("topic", {}).get("name", "")).strip()
    if topic_title:
        return topic_title
    return "보도자료 요약을 생성하지 못했습니다."


def build_media_status_section(reference_records: list[dict], processed_candidates: list[dict], analysis_now) -> str:
    analysis_label = format_korean_briefing_time(analysis_now)
    if not reference_records:
        return f"{analysis_label} 현재, 관련 언론보도는 확인되지 않았습니다."

    source_summary = ", ".join(get_top_source_labels(reference_records, limit=3))
    lead_record = get_media_status_lead_record(processed_candidates)
    lines = [f"{analysis_label} 현재, 관련 보도: {source_summary} 등 {len(reference_records)}건*"]
    if lead_record:
        lines.append(
            f"   * [{get_record_source_label(lead_record)}] "
            f"{limit_text(get_record_display_title(lead_record), 90)} 등"
        )
    return "\n".join(lines)


def build_theme_groups_for_briefing(records: list[dict], config: dict) -> list[dict]:
    groups = {}
    for record in records:
        theme_key = derive_theme_key(record, config)
        source_label = get_record_source_label(record)
        groups.setdefault(
            theme_key,
            {
                "key": theme_key,
                "label": build_theme_label_from_key(theme_key),
                "count": 0,
                "sources": set(),
                "lead": record,
            },
        )
        groups[theme_key]["count"] += 1
        groups[theme_key]["sources"].add(source_label)

    result = []
    for group in groups.values():
        result.append(
            {
                **group,
                "sourceSummary": ", ".join(sorted(group["sources"])[:3]),
            }
        )
    result.sort(key=lambda group: group["count"], reverse=True)
    return result[: int(config.get("collection", {}).get("maxThemes", 3))]


def build_reference_candidates(raw_records: list[dict], config: dict, analysis_now=None) -> list[dict]:
    if analysis_now is None:
        analysis_now = get_analysis_now(config)
    lookback_start = get_lookback_start(config, analysis_now)

    relevant_records = []
    for record in raw_records:
        if not is_representative_record(record):
            continue
        if not is_output_eligible_record(record):
            continue
        if not is_within_lookback(record, lookback_start, analysis_now, config["timezone"]):
            continue
        if not is_reference_relevant_record(record, config):
            continue
        relevant_records.append(record)

    relevant_records.sort(
        key=lambda record: (
            get_record_sort_timestamp(record, config),
            float(record.get("importance_score", 0) or 0),
        ),
        reverse=True,
    )
    return relevant_records


def build_briefing_overview_counts(
    raw_records: list[dict],
    config: dict,
    analysis_now=None,
    reference_records: list[dict] | None = None,
) -> dict:
    relevant_records = list(reference_records or build_reference_candidates(raw_records, config, analysis_now))
    return {
        "article_count": len(relevant_records),
        "source_count": get_unique_source_count(relevant_records),
    }


def build_supporting_articles(records: list[dict]) -> str:
    return "\n".join(
        f"[{get_record_source_label(record)}] {limit_text(get_record_display_title(record), 70)}"
        for record in records[:5]
    )


def build_briefing_notes(overview_counts: dict | None, theme_groups: list[dict]) -> str:
    counts = overview_counts or {}
    return (
        f"article_count={counts.get('article_count', 0)}, "
        f"source_count={counts.get('source_count', 0)}, "
        f"theme_count={len(theme_groups)}"
    )


def get_unique_source_count(records: list[dict]) -> int:
    return len({get_record_source_label(record) for record in records})


def get_record_source_label(record: dict) -> str:
    return infer_display_source_name(record.get("source_name", ""), record.get("title", ""), record.get("summary", ""))


def get_record_display_title(record: dict) -> str:
    return clean_display_title(record.get("title", ""), record.get("source_name", ""), record.get("summary", ""))


def format_korean_briefing_time(value) -> str:
    return f"{value.year}년 {value.month}월 {value.day}일 {value.hour:02d}:{value.minute:02d}"


def get_record_sort_timestamp(record: dict, config: dict) -> float:
    from .config import get_record_time

    timestamp = get_record_time(record, config["timezone"])
    return timestamp.timestamp() if timestamp else 0


def get_top_source_labels(records: list[dict], limit: int = 3) -> list[str]:
    counts: dict[str, int] = {}
    for record in records:
        source_label = get_record_source_label(record)
        counts[source_label] = counts.get(source_label, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [label for label, _count in ordered[:limit]]


def get_media_status_lead_record(processed_candidates: list[dict]) -> dict | None:
    if processed_candidates:
        return processed_candidates[0]
    return None
