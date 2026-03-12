from __future__ import annotations

from .analysis import build_theme_label_from_key, derive_theme_key
from .config import get_analysis_now
from .db import fetch_processed_articles, replace_briefing_sections
from .utils import clean_display_title, format_datetime, format_readable_datetime, infer_display_source_name, limit_text


def generate_briefing(connection, config: dict, output_path: str | None = None) -> str:
    candidates = fetch_processed_articles(connection)
    analysis_now = get_analysis_now(config)
    rows, full_text = build_briefing_package(candidates, config, analysis_now)
    replace_briefing_sections(connection, rows)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(full_text + "\n")
    return full_text


def build_briefing_package(candidates: list[dict], config: dict, analysis_now) -> tuple[list[dict], str]:
    generated_time = format_datetime(analysis_now, config["timezone"])

    if not candidates:
        rows = [
            {
                "section_order": 1,
                "generated_time": generated_time,
                "topic_name": config["topic"]["name"],
                "section_name": "전체본",
                "content": "선별된 고관련 기사가 없어 브리핑 초안을 생성하지 않았습니다. RSS 설정과 키워드 기준을 확인하십시오.",
                "supporting_articles": "",
                "notes": "no_candidates=true",
            }
        ]
        return rows, "No briefing candidates."

    top_candidates = candidates[: int(config.get("collection", {}).get("maxBriefingArticles", 12))]
    frame_counts = count_frames(candidates)
    theme_groups = build_theme_groups_for_briefing(top_candidates, config)

    section_payloads = [
        ("총평", build_overall_summary(candidates, frame_counts, theme_groups, config, analysis_now)),
        ("주요 보도 내용", build_main_coverage_section(theme_groups)),
        ("주요 논점", build_issue_section(frame_counts, theme_groups)),
        ("영향력 기사", build_impact_section(top_candidates)),
        ("대응 참고", build_response_points(frame_counts, theme_groups)),
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
                "notes": f"frame_counts={serialize_frame_counts(frame_counts)}",
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
            "notes": f"frame_counts={serialize_frame_counts(frame_counts)}",
        }
    )
    return rows, full_text


def build_overall_summary(candidates: list[dict], frame_counts: dict, theme_groups: list[dict], config: dict, analysis_now) -> str:
    source_count = get_unique_source_count(candidates)
    dominant_frames = get_dominant_frames(frame_counts)
    dominant_themes = [group["label"] for group in theme_groups[:2]]
    lines = []
    analysis_label = format_readable_datetime(analysis_now, config["timezone"])

    lines.append(
        f"기준 시점({analysis_label}) 기준, {config['topic']['name']} 관련 고관련 기사 {len(candidates)}건이 선별되었고 {source_count}개 매체에서 유사 서사가 확인되었습니다."
    )
    if len(dominant_frames) > 1:
        lines.append(f"보도 흐름은 {dominant_frames[0]} 중심이며 {dominant_frames[1]} 성격 보도가 함께 관찰되었습니다.")
    else:
        lines.append(f"보도 흐름은 {(dominant_frames[0] if dominant_frames else '정책 설명')} 중심으로 형성되었습니다.")

    if dominant_themes:
        lines.append(f"반복적으로 등장한 주제는 {', '.join(dominant_themes)}입니다.")
    else:
        lines.append("주요 보도는 정책 전반의 공급 계획과 후속 일정 설명에 집중되었습니다.")

    if frame_counts.get("비판 / 우려", 0) > 0:
        lines.append("브리핑 시에는 실효성, 추진 속도, 관계기관 협의와 관련한 우려 지점에 대한 보완 설명이 필요합니다.")
    else:
        lines.append("브리핑 시에는 정책 핵심 내용, 후속 일정, 집행 절차를 일관된 메시지로 제시하는 것이 적절합니다.")
    return "\n".join(lines)


def build_main_coverage_section(theme_groups: list[dict]) -> str:
    if not theme_groups:
        return "- 정책 전반 기사 위주로 분포되어 별도 테마 군집이 뚜렷하지 않았습니다."
    return "\n".join(
        (
            f"- {group['label']}: {group['sourceSummary']} 등 {group['count']}건. "
            f"대표 기사: [{get_record_source_label(group['lead'])}] {limit_text(get_record_display_title(group['lead']), 90)}"
        )
        for group in theme_groups
    )


def build_issue_section(frame_counts: dict, theme_groups: list[dict]) -> str:
    lines = []
    if frame_counts.get("비판 / 우려", 0) > 0:
        lines.append("- 정책 실행 가능성, 추진 속도, 현장 수용성과 관련한 우려 신호가 반복적으로 나타났습니다.")
    if frame_counts.get("정치 / 기관 이슈", 0) > 0:
        lines.append("- 관계기관 협의, 지자체 조율, 정치권 반응 등 제도 외부 변수에 대한 관심이 확인되었습니다.")
    if frame_counts.get("정책 설명", 0) > 0:
        lines.append("- 핵심 내용, 대상 범위, 추진 일정, 후속 절차 등 정책 세부 설명 수요가 여전히 높습니다.")
    if frame_counts.get("긍정 평가", 0) > 0:
        lines.append("- 일부 보도는 정책 효과와 기대 편익을 긍정적으로 평가했습니다.")
    for group in theme_groups[:2]:
        lines.append(f"- {group['label']}에서 세부 실행계획과 후속 일정 관리가 핵심 논점으로 반복되었습니다.")
    if not lines:
        lines.append("- 뚜렷한 비판 프레임보다 정책 설명과 기본 사실 전달 보도가 우세했습니다.")
    return "\n".join(lines[:5])


def build_impact_section(candidates: list[dict]) -> str:
    return "\n".join(
        (
            f"{index}. [{get_record_source_label(record)}] {get_record_display_title(record)} "
            f"(중요도 {record['importance_score']}, 프레임 {record.get('frame_category') or '기타'})"
        )
        for index, record in enumerate(candidates[:5], start=1)
    )


def build_response_points(frame_counts: dict, theme_groups: list[dict]) -> str:
    lines = [
        "- 정책 핵심 내용, 대상 범위, 일정은 확정 사항과 후속 검토 사항을 구분해 설명합니다.",
        "- 후속 절차, 관계기관 협의, 현장 이행관리 계획은 가능한 범위에서 구체 일정과 함께 제시합니다.",
    ]
    if frame_counts.get("비판 / 우려", 0) > 0:
        lines.append("- 실효성 및 속도 우려에는 단계별 추진계획과 관리지표를 중심으로 대응 포인트를 준비합니다.")
    if frame_counts.get("정치 / 기관 이슈", 0) > 0:
        lines.append("- 지자체 및 관계기관 협의 상황은 단일 메시지로 정리해 기관 간 해석 차이를 줄입니다.")
    if theme_groups:
        lines.append(f"- 반복 노출되는 주제인 {', '.join(group['label'] for group in theme_groups[:2])} 관련 예상 질의를 사전 정리합니다.")
    return "\n".join(lines[:4])


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


def count_frames(records: list[dict]) -> dict:
    counts = {}
    for record in records:
        frame = record.get("frame_category") or "기타"
        counts[frame] = counts.get(frame, 0) + 1
    return counts


def get_dominant_frames(frame_counts: dict) -> list[str]:
    return sorted(frame_counts, key=lambda frame: frame_counts[frame], reverse=True)[:2]


def get_unique_source_count(records: list[dict]) -> int:
    return len({get_record_source_label(record) for record in records})


def build_supporting_articles(records: list[dict]) -> str:
    return "\n".join(
        f"[{get_record_source_label(record)}] {limit_text(get_record_display_title(record), 70)}"
        for record in records[:5]
    )


def serialize_frame_counts(frame_counts: dict) -> str:
    return ", ".join(f"{frame}:{count}" for frame, count in frame_counts.items())


def get_record_source_label(record: dict) -> str:
    return infer_display_source_name(record.get("source_name", ""), record.get("title", ""), record.get("summary", ""))


def get_record_display_title(record: dict) -> str:
    return clean_display_title(record.get("title", ""), record.get("source_name", ""), record.get("summary", ""))
