from __future__ import annotations

import logging
import re
import urllib.error
import urllib.request
from copy import deepcopy

from .config import get_analysis_now, get_keyword_rules_by_buckets, get_lookback_start, get_record_time, get_source_priority
from .db import fetch_raw_articles, replace_processed_articles, update_raw_articles
from .utils import (
    DEFAULT_HTTP_HEADERS,
    add_note,
    collapse_whitespace,
    format_datetime,
    infer_display_source_name,
    is_portal_source_name,
    limit_text,
    looks_like_html,
    normalize_link,
    normalize_text_lower,
    normalize_title,
    split_keywords,
    strip_article_chrome,
    strip_html,
    title_similarity,
    upsert_tagged_note,
)


LOGGER = logging.getLogger(__name__)

WEAK_POSITIVE_FRAME_KEYWORDS = {"기대", "활성화"}
OFFICIAL_ROLE_MARKERS = ("장관", "위원장", "차관", "본부장", "실장", "청장", "정부", "국토부")
OFFICIAL_STATEMENT_MARKERS = ("밝혔", "말했", "강조", "설명", "점검", "언급", "당부")
QUOTE_MARKERS = ('"', "“", "”", "‘", "’")


def calculate_policy_score(record: dict, rules: list[dict], config: dict) -> dict:
    title_text = normalize_text_lower(record.get("title", ""))
    summary_text = normalize_text_lower(record.get("summary", ""))
    body_text = normalize_text_lower(record.get("body_text", ""))
    matched_keywords: list[str] = []
    matched_lookup: set[str] = set()
    score = 0.0

    for rule in rules:
        if not rule.get("enabled", True):
            continue
        keyword = normalize_text_lower(rule.get("keyword", ""))
        if not keyword:
            continue

        in_title = keyword in title_text
        in_summary = keyword in summary_text
        in_body = keyword in body_text
        if not (in_title or in_summary or in_body):
            continue

        original_keyword = rule["keyword"]
        if original_keyword not in matched_lookup:
            matched_lookup.add(original_keyword)
            matched_keywords.append(original_keyword)

        weight = float(rule.get("weight", 1))
        if in_title:
            score += weight * float(config.get("scoring", {}).get("titleWeight", 3))
        elif in_summary:
            score += weight * float(config.get("scoring", {}).get("summaryWeight", 1))
        elif in_body:
            score += weight * float(config.get("scoring", {}).get("bodyWeight", 0.75))

        if rule.get("bucket") == "phrase":
            score += float(config.get("scoring", {}).get("phraseBonus", 0))

    if score > 0:
        score += get_source_priority(record.get("source_name", ""), config)

    return {"score": round(score, 1), "keywords": matched_keywords}


def get_policy_hit_stats_from_keywords(keywords: list[str], config: dict) -> dict:
    phrase_lookup = {
        rule["keyword"]
        for rule in get_keyword_rules_by_buckets(config, ["phrase"])
        if rule.get("enabled", True) and rule.get("keyword")
    }
    total_hits = 0
    phrase_hits = 0
    for keyword in keywords:
        if not keyword:
            continue
        total_hits += 1
        if keyword in phrase_lookup:
            phrase_hits += 1
    return {"totalHits": total_hits, "phraseHits": phrase_hits}


def is_high_relevance_record(record: dict, config: dict) -> bool:
    if float(record.get("policy_score", 0) or 0) < float(config.get("scoring", {}).get("highRelevanceThreshold", 8)):
        return False
    hit_stats = get_policy_hit_stats_from_keywords(split_keywords(record.get("keyword", "")), config)
    if hit_stats["phraseHits"] > 0:
        return True
    return hit_stats["totalHits"] >= int(config.get("scoring", {}).get("minimumKeywordHits", 2))


def is_reference_relevant_record(record: dict, config: dict) -> bool:
    if float(record.get("policy_score", 0) or 0) <= 0:
        return False
    if is_high_relevance_record(record, config):
        return True

    anchor_keywords = get_reference_anchor_keywords(config)
    if not anchor_keywords:
        return False

    matched_keywords = {
        normalize_text_lower(keyword)
        for keyword in split_keywords(record.get("keyword", ""))
        if collapse_whitespace(keyword)
    }
    return bool(matched_keywords & anchor_keywords)


def is_output_eligible_record(record: dict) -> bool:
    display_source = infer_display_source_name(
        record.get("source_name", ""),
        record.get("title", ""),
        record.get("summary", ""),
    )
    return not is_portal_source_name(display_source)


def get_reference_anchor_keywords(config: dict) -> set[str]:
    anchors: set[str] = set()
    for keyword in config.get("collection", {}).get("rawCoreKeywords", []):
        normalized = normalize_text_lower(keyword)
        if normalized:
            anchors.add(normalized)
    for rule in get_keyword_rules_by_buckets(config, ["phrase"]):
        normalized = normalize_text_lower(rule.get("keyword", ""))
        if normalized:
            anchors.add(normalized)
    return anchors


def run_analysis(connection, config: dict, fetch_bodies: bool = True, progress_callback=None, cancel_callback=None) -> list[dict]:
    raw_records = fetch_raw_articles(connection)
    if not raw_records:
        replace_processed_articles(connection, format_datetime(get_analysis_now(config), config["timezone"]), [])
        return []

    raw_records, processed_records = build_processed_snapshot(
        raw_records,
        config,
        fetch_bodies=fetch_bodies,
        progress_callback=progress_callback,
        cancel_callback=cancel_callback,
    )

    update_raw_articles(connection, raw_records)
    replace_processed_articles(connection, format_datetime(get_analysis_now(config), config["timezone"]), processed_records)
    return processed_records


def build_processed_snapshot(
    raw_records: list[dict],
    config: dict,
    fetch_bodies: bool = True,
    progress_callback=None,
    cancel_callback=None,
) -> tuple[list[dict], list[dict]]:
    snapshot_records = deepcopy(raw_records)
    total_stages = 6 if fetch_bodies else 4
    completed_stages = 0

    if cancel_callback:
        cancel_callback()
    if progress_callback:
        progress_callback("stage", completed_stages, total_stages, "중복 제거 중")
    deduplicate_news(snapshot_records, config)
    completed_stages += 1

    if cancel_callback:
        cancel_callback()
    if progress_callback:
        progress_callback("stage", completed_stages, total_stages, "관련도 점수 계산 중")
    score_policy_relevance(snapshot_records, config)
    completed_stages += 1
    if fetch_bodies:
        if cancel_callback:
            cancel_callback()
        if progress_callback:
            progress_callback("stage", completed_stages, total_stages, "본문 수집 중")
        fetch_article_bodies(
            snapshot_records,
            config,
            progress_callback=lambda current, total, source_name: progress_callback(
                "body_fetch",
                current,
                total,
                source_name,
            )
            if progress_callback
            else None,
            cancel_callback=cancel_callback,
        )
        completed_stages += 1

        if cancel_callback:
            cancel_callback()
        if progress_callback:
            progress_callback("stage", completed_stages, total_stages, "본문 반영 점수 재계산 중")
        score_policy_relevance(snapshot_records, config)
        completed_stages += 1
    if cancel_callback:
        cancel_callback()
    if progress_callback:
        progress_callback("stage", completed_stages, total_stages, "프레임 분류 중")
    classify_frames(snapshot_records, config)
    completed_stages += 1
    if cancel_callback:
        cancel_callback()
    if progress_callback:
        progress_callback("stage", completed_stages, total_stages, "중요도 랭킹 중")
    processed_records = rank_articles(snapshot_records, config)
    completed_stages += 1
    if cancel_callback:
        cancel_callback()
    if progress_callback:
        progress_callback("stage", completed_stages, total_stages, "분석 완료")
    return snapshot_records, processed_records


def deduplicate_news(raw_records: list[dict], config: dict) -> None:
    articles = []
    for record in raw_records:
        display_source = infer_display_source_name(
            record.get("source_name", ""),
            record.get("title", ""),
            record.get("summary", ""),
        )
        articles.append(
            {
                "record": record,
                "clean_link": normalize_link(record.get("link", "")),
                "exact_title": normalize_text_lower(record.get("title", "")),
                "normalized_title": normalize_title(record.get("title", "")),
                "display_source": display_source,
                "source_key": normalize_text_lower(display_source or record.get("source_name", "")),
                "representative_priority": get_representative_priority(record, config),
                "time_value": get_record_time(record, config["timezone"]),
            }
        )

    articles.sort(
        key=lambda item: (
            item["representative_priority"],
            item["time_value"].timestamp() if item["time_value"] else 0,
        ),
        reverse=True,
    )

    seen_links: dict[str, int] = {}
    seen_titles: dict[tuple[str, str], int] = {}
    seen_normalized_titles: dict[tuple[str, str], int] = {}
    representatives: list[dict] = []
    representative_stats: dict[int, dict] = {}

    for article in articles:
        record = article["record"]
        duplicate_info = None
        record["normalized_title"] = article["normalized_title"]
        record["duplicate_flag"] = "representative"

        if article["clean_link"] and article["clean_link"] in seen_links:
            duplicate_info = {"rep_id": seen_links[article["clean_link"]], "reason": "duplicate_link"}
        elif (
            article["source_key"]
            and article["exact_title"]
            and (article["source_key"], article["exact_title"]) in seen_titles
        ):
            duplicate_info = {
                "rep_id": seen_titles[(article["source_key"], article["exact_title"])],
                "reason": "duplicate_exact_title",
            }
        elif (
            article["source_key"]
            and article["normalized_title"]
            and (article["source_key"], article["normalized_title"]) in seen_normalized_titles
        ):
            duplicate_info = {
                "rep_id": seen_normalized_titles[(article["source_key"], article["normalized_title"])],
                "reason": "duplicate_normalized_title",
            }
        else:
            duplicate_info = find_fuzzy_duplicate(article, representatives, float(config.get("dedup", {}).get("fuzzyThreshold", 0.84)))

        if duplicate_info:
            representative_record = next(item["record"] for item in representatives if item["record"]["id"] == duplicate_info["rep_id"])
            record["duplicate_flag"] = duplicate_info["reason"]
            record["notes"] = add_note(
                record.get("notes", ""),
                f"representative={representative_record['source_name']}:{limit_text(representative_record['title'], 80)}",
            )
            representative_stats.setdefault(duplicate_info["rep_id"], {"sources": set(), "count": 1})
            representative_stats[duplicate_info["rep_id"]]["count"] += 1
            representative_stats[duplicate_info["rep_id"]]["sources"].add(record["source_name"])
            continue

        representative_stats.setdefault(record["id"], {"sources": set(), "count": 1})
        representative_stats[record["id"]]["sources"].add(record["source_name"])
        representatives.append(article)

        if article["clean_link"]:
            seen_links[article["clean_link"]] = record["id"]
        if article["source_key"] and article["exact_title"]:
            seen_titles[(article["source_key"], article["exact_title"])] = record["id"]
        if article["source_key"] and article["normalized_title"]:
            seen_normalized_titles[(article["source_key"], article["normalized_title"])] = record["id"]

    for record in raw_records:
        stat = representative_stats.get(record["id"])
        if not stat:
            continue
        record["notes"] = upsert_tagged_note(record.get("notes", ""), "duplicate_count", str(stat["count"] - 1))
        source_names = sorted(stat["sources"])
        if len(source_names) > 1:
            record["notes"] = upsert_tagged_note(record.get("notes", ""), "duplicate_sources", ", ".join(source_names))


def get_representative_priority(record: dict, config: dict) -> int:
    priority = get_source_priority(record.get("source_name", ""), config)
    source_type = str(record.get("source_type", "")).lower()
    display_source = infer_display_source_name(
        record.get("source_name", ""),
        record.get("title", ""),
        record.get("summary", ""),
    )
    if source_type == "rss":
        priority += 10
    if source_type == "google_news":
        priority += 2
    if display_source:
        priority += get_source_priority(display_source, config)
    if is_portal_source_name(display_source):
        priority -= 6
    return priority


def find_fuzzy_duplicate(article: dict, representatives: list[dict], threshold: float) -> dict | None:
    if not article["normalized_title"]:
        return None
    for representative in representatives:
        if article.get("source_key") != representative.get("source_key"):
            continue
        similarity = title_similarity(article["normalized_title"], representative["normalized_title"])
        effective_threshold = threshold
        current_is_portal = is_portal_source_name(article.get("display_source", ""))
        representative_is_portal = is_portal_source_name(representative.get("display_source", ""))
        if current_is_portal != representative_is_portal:
            effective_threshold = min(effective_threshold, 0.70)
        if similarity >= effective_threshold:
            return {"rep_id": representative["record"]["id"], "reason": f"duplicate_fuzzy_title_{similarity:.2f}"}
    return None


def score_policy_relevance(raw_records: list[dict], config: dict) -> None:
    rules = get_keyword_rules_by_buckets(config, ["topic", "phrase"])
    for record in raw_records:
        score_result = calculate_policy_score(record, rules, config)
        record["policy_score"] = score_result["score"]
        record["keyword"] = ", ".join(score_result["keywords"])
        record["notes"] = upsert_tagged_note(record.get("notes", ""), "policy_hits", "|".join(score_result["keywords"]))
        record["notes"] = upsert_tagged_note(record.get("notes", ""), "policy_hit_count", str(len(score_result["keywords"])))
        record["notes"] = upsert_tagged_note(
            record.get("notes", ""),
            "policy_high_relevance",
            str(is_high_relevance_record(record, config)).lower(),
        )


def fetch_article_bodies(raw_records: list[dict], config: dict, progress_callback=None, cancel_callback=None) -> int:
    analysis_now = get_analysis_now(config)
    lookback_start = get_lookback_start(config, analysis_now)
    candidates = [
        {
            "record": record,
            "record_time": get_record_time(record, config["timezone"]),
            "source_priority": get_source_priority(record.get("source_name", ""), config),
        }
        for record in raw_records
        if is_body_fetch_candidate(record, config, lookback_start, analysis_now)
    ]
    candidates.sort(
        key=lambda item: (
            float(item["record"].get("policy_score", 0) or 0),
            item["source_priority"],
            item["record_time"].timestamp() if item["record_time"] else 0,
        ),
        reverse=True,
    )

    updated_count = 0
    limit = int(config.get("collection", {}).get("maxBodyFetchCandidates", 12))
    total_candidates = min(limit, len(candidates))
    if progress_callback:
        progress_callback(0, total_candidates, "")
    for index, candidate in enumerate(candidates[:limit], start=1):
        if cancel_callback:
            cancel_callback()
        record = candidate["record"]
        try:
            body_text = fetch_article_body_text(record, config)
            if not body_text:
                continue
            record["body_text"] = body_text
            record["notes"] = upsert_tagged_note(record.get("notes", ""), "body_fetched", "true")
            updated_count += 1
        except (ValueError, urllib.error.URLError, TimeoutError) as error:
            record["notes"] = upsert_tagged_note(record.get("notes", ""), "body_fetch_error", limit_text(str(error), 80))
            LOGGER.warning("Body fetch failed for %s: %s", record.get("source_name"), error)
        if progress_callback:
            progress_callback(index, total_candidates, record.get("source_name", ""))

    if cancel_callback:
        cancel_callback()
    LOGGER.info("Body fetch updated %s of %s candidate articles.", updated_count, min(limit, len(candidates)))
    return updated_count


def is_body_fetch_candidate(record: dict, config: dict, lookback_start, analysis_now) -> bool:
    if not is_representative_record(record):
        return False
    if not record.get("link") or not is_within_lookback(record, lookback_start, analysis_now, config["timezone"]):
        return False
    if record.get("body_text"):
        return False
    if str(record.get("source_type", "")).lower() == "google_news" and not bool(
        config.get("collection", {}).get("fetchBodyFromGoogleNews", False)
    ):
        return False
    return float(record.get("policy_score", 0) or 0) >= float(config.get("collection", {}).get("bodyFetchMinimumPolicyScore", 4))


def fetch_article_body_text(record: dict, config: dict) -> str:
    request = urllib.request.Request(
        record["link"],
        headers=DEFAULT_HTTP_HEADERS,
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        data = response.read()
        encodings = []
        content_type = response.headers.get_content_charset()
        if content_type:
            encodings.append(content_type)
        encodings.extend(["utf-8", "cp949", "euc-kr"])
        html = None
        for encoding in encodings:
            try:
                html = data.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if html is None:
            html = data.decode("utf-8", errors="replace")
    if not looks_like_html(html):
        raise ValueError("Article URL returned non-HTML response")
    return extract_article_body_text(html, config)


def extract_article_body_text(html: str, config: dict) -> str:
    candidates = []
    candidates.extend(re.findall(r"<article\b[\s\S]*?</article>", html, flags=re.IGNORECASE))
    candidates.extend(re.findall(r"<main\b[\s\S]*?</main>", html, flags=re.IGNORECASE))
    if not candidates:
        body_matches = re.findall(r"<body\b[\s\S]*?</body>", html, flags=re.IGNORECASE)
        if body_matches:
            candidates.append(body_matches[0])
    if not candidates:
        candidates.append(html)

    best_text = ""
    for candidate in candidates:
        plain_text = strip_html(strip_article_chrome(candidate))
        if len(plain_text) > len(best_text):
            best_text = plain_text
    best_text = collapse_whitespace(best_text)
    if not best_text:
        return ""
    return limit_text(best_text, int(config.get("collection", {}).get("bodyTextMaxLength", 4000)))


def classify_frames(raw_records: list[dict], config: dict) -> None:
    frame_definitions = [
        ("frame_policy", "정책 설명"),
        ("frame_positive", "긍정 평가"),
        ("frame_critical", "비판 / 우려"),
        ("frame_political", "정치 / 기관 이슈"),
    ]
    rules_by_bucket = {bucket: get_keyword_rules_by_buckets(config, [bucket]) for bucket, _ in frame_definitions}

    for record in raw_records:
        text = normalize_text_lower(
            f"{record.get('title', '')} {record.get('summary', '')} {limit_text(record.get('body_text', ''), 1500)}"
        )
        scores = {"정책 설명": 0, "긍정 평가": 0, "비판 / 우려": 0, "정치 / 기관 이슈": 0}
        hits = []
        bucket_hits = {bucket: [] for bucket, _ in frame_definitions}

        for bucket, category in frame_definitions:
            for rule in rules_by_bucket[bucket]:
                keyword = normalize_text_lower(rule.get("keyword", ""))
                if keyword and keyword in text:
                    scores[category] += float(rule.get("weight", 1))
                    hits.append(f"{bucket}:{rule['keyword']}")
                    bucket_hits[bucket].append(rule["keyword"])

        if should_suppress_positive_frame(record, bucket_hits["frame_positive"]):
            scores["긍정 평가"] = 0
            hits = [hit for hit in hits if not hit.startswith("frame_positive:")]
            record["notes"] = upsert_tagged_note(record.get("notes", ""), "frame_positive_suppressed", "true")

        selected_category = "기타"
        selected_score = 0.0
        for category in ["비판 / 우려", "정치 / 기관 이슈", "긍정 평가", "정책 설명"]:
            if scores[category] > selected_score:
                selected_category = category
                selected_score = scores[category]

        if selected_score == 0 and is_high_relevance_record(record, config):
            selected_category = "정책 설명"

        record["frame_category"] = selected_category
        record["notes"] = upsert_tagged_note(record.get("notes", ""), "frame_hits", "|".join(hits))


def should_suppress_positive_frame(record: dict, positive_hits: list[str]) -> bool:
    normalized_hits = {normalize_text_lower(keyword) for keyword in positive_hits if keyword}
    if not normalized_hits:
        return False
    if not normalized_hits.issubset(WEAK_POSITIVE_FRAME_KEYWORDS):
        return False

    raw_text = collapse_whitespace(f"{record.get('title', '')} {record.get('summary', '')}")
    lowered_text = normalize_text_lower(raw_text)
    has_official_role = any(marker in lowered_text for marker in OFFICIAL_ROLE_MARKERS)
    has_statement_context = any(marker in raw_text for marker in QUOTE_MARKERS) or any(
        marker in lowered_text for marker in OFFICIAL_STATEMENT_MARKERS
    )
    return has_official_role and has_statement_context


def rank_articles(raw_records: list[dict], config: dict) -> list[dict]:
    analysis_now = get_analysis_now(config)
    lookback_start = get_lookback_start(config, analysis_now)
    representative_records = [record for record in raw_records if is_representative_record(record)]
    lookback_records = [
        record
        for record in representative_records
        if is_within_lookback(record, lookback_start, analysis_now, config["timezone"])
    ]
    theme_stats = build_theme_stats(lookback_records, config)

    for record in raw_records:
        if not is_representative_record(record):
            record["importance_score"] = 0
            continue

        theme_key = derive_theme_key(record, config)
        theme_stat = theme_stats.get(theme_key, {"count": 1, "sourceCount": 1})
        score = float(record.get("policy_score", 0) or 0)
        score += get_source_priority(record.get("source_name", ""), config)
        score += get_freshness_boost(record, analysis_now, config["timezone"])

        if record.get("frame_category") == "비판 / 우려":
            score += float(config.get("ranking", {}).get("criticalFrameBoost", 2))
        if has_negative_signal(record, config):
            score += 1
        if is_opinion_item(record, config):
            score += float(config.get("ranking", {}).get("opinionBoost", 3))

        score += min(max(theme_stat["count"] - 1, 0), 3) * float(config.get("ranking", {}).get("repeatedNarrativeBonus", 1))
        score += min(max(theme_stat["sourceCount"] - 1, 0), 2)
        record["importance_score"] = round(score, 1)
        record["notes"] = upsert_tagged_note(record.get("notes", ""), "theme", theme_key)

    processed = [
        deepcopy(record)
        for record in raw_records
        if is_representative_record(record)
        and is_output_eligible_record(record)
        and is_high_relevance_record(record, config)
        and is_within_lookback(record, lookback_start, analysis_now, config["timezone"])
    ]
    processed.sort(key=lambda record: compare_processed_record_key(record, config), reverse=True)

    max_rows = int(config.get("collection", {}).get("maxProcessedRows", 50))
    ranked_rows = []
    for index, record in enumerate(processed[:max_rows], start=1):
        record["rank"] = index
        ranked_rows.append(record)
    return ranked_rows


def compare_processed_record_key(record: dict, config: dict):
    timestamp = get_record_time(record, config["timezone"])
    return (
        float(record.get("importance_score", 0) or 0),
        timestamp.timestamp() if timestamp else 0,
    )


def build_theme_stats(records: list[dict], config: dict) -> dict:
    stats: dict[str, dict] = {}
    for record in records:
        theme_key = derive_theme_key(record, config)
        stats.setdefault(theme_key, {"count": 0, "sources": set()})
        stats[theme_key]["count"] += 1
        stats[theme_key]["sources"].add(record.get("source_name", ""))

    for value in stats.values():
        value["sourceCount"] = len(value["sources"])
    return stats


def derive_theme_key(record: dict, config: dict) -> str:
    keywords = split_keywords(record.get("keyword", ""))
    generic_lookup = set(config.get("genericThemeKeywords", []))
    specific_keywords = [keyword for keyword in keywords if keyword not in generic_lookup]
    theme_keywords = specific_keywords or keywords

    if not theme_keywords:
        title = str(record.get("title", ""))
        for keyword in ("용산", "태릉", "과천"):
            if keyword in title:
                theme_keywords.append(keyword)

    if not theme_keywords:
        return "정책 전반"
    return "·".join(theme_keywords[:2])


def build_theme_label_from_key(theme_key: str) -> str:
    return "정책 전반" if theme_key == "정책 전반" else f"{theme_key} 관련 보도"


def get_freshness_boost(record: dict, analysis_now, timezone_name: str) -> int:
    timestamp = get_record_time(record, timezone_name)
    if not timestamp:
        return 0
    age_hours = (analysis_now - timestamp).total_seconds() / 3600
    if age_hours <= 6:
        return 4
    if age_hours <= 24:
        return 2
    if age_hours <= 36:
        return 1
    return 0


def has_negative_signal(record: dict, config: dict) -> bool:
    text = normalize_text_lower(f"{record.get('title', '')} {record.get('summary', '')}")
    for rule in get_keyword_rules_by_buckets(config, ["negative_signal"]):
        if rule.get("keyword") and normalize_text_lower(rule["keyword"]) in text:
            return True
    return False


def is_opinion_item(record: dict, config: dict) -> bool:
    text = normalize_text_lower(record.get("title", ""))
    for rule in get_keyword_rules_by_buckets(config, ["opinion_signal"]):
        if rule.get("keyword") and normalize_text_lower(rule["keyword"]) in text:
            return True
    return False


def is_within_lookback(record: dict, lookback_start, analysis_now, timezone_name: str) -> bool:
    timestamp = get_record_time(record, timezone_name)
    if not timestamp:
        return True
    return lookback_start <= timestamp <= analysis_now


def is_representative_record(record: dict) -> bool:
    duplicate_flag = record.get("duplicate_flag", "")
    return not duplicate_flag or duplicate_flag == "representative"
