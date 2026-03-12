from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .db import read_config_keywords, read_config_sources, read_runtime_settings
from .defaults import clone_default_config
from .utils import collapse_whitespace, parse_datetime


def deep_merge(base: dict, override: dict) -> dict:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def load_json_override(config_path: str | Path | None) -> dict:
    if not config_path:
        return {}
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if "keyword_rules" in data and "keywordRules" not in data:
        data["keywordRules"] = data.pop("keyword_rules")
    return data


def apply_runtime_settings(config: dict, rows: list[dict]) -> None:
    for row in rows:
        if row.get("key") == "analysis_reference_time":
            config.setdefault("analysis", {})["referenceTime"] = row.get("value", "")


def load_runtime_config(connection, config_path: str | Path | None = None, analysis_reference_time: str | None = None) -> dict:
    config = clone_default_config()

    if connection is not None:
        source_rows = read_config_sources(connection)
        keyword_rows = read_config_keywords(connection)
        runtime_rows = read_runtime_settings(connection)
        if source_rows:
            config["sources"] = [{**row, "enabled": bool(row["enabled"])} for row in source_rows]
        if keyword_rows:
            config["keywordRules"] = [{**row, "enabled": bool(row["enabled"])} for row in keyword_rows]
        if runtime_rows:
            apply_runtime_settings(config, runtime_rows)

    override = load_json_override(config_path)
    if override:
        deep_merge(config, override)

    if analysis_reference_time is not None:
        config.setdefault("analysis", {})["referenceTime"] = "" if analysis_reference_time == "now" else analysis_reference_time

    return config


def build_google_news_rss_url(query: str) -> str:
    from urllib.parse import quote

    return f"https://news.google.com/rss/search?q={quote(query)}&hl=ko&gl=KR&ceid=KR:ko"


def resolve_feed_url(source: dict) -> str:
    if source.get("feed_url"):
        return source["feed_url"]
    if source.get("source_type") == "google_news" and source.get("keyword"):
        return build_google_news_rss_url(source["keyword"])
    return ""


def get_keyword_rules_by_buckets(config: dict, buckets: list[str]) -> list[dict]:
    bucket_lookup = set(buckets)
    return [rule for rule in config.get("keywordRules", []) if rule.get("enabled", True) and rule.get("bucket") in bucket_lookup]


def get_source_priority(source_name: str, config: dict) -> int:
    priority_map = config.get("sourcePriority", {})
    exact = int(priority_map.get(source_name, 0) or 0)
    if exact:
        return exact
    if source_name and " - " not in source_name and "-" in source_name:
        base_name = source_name.split("-", 1)[0].strip()
        return int(priority_map.get(base_name, 0) or 0)
    return 0


def get_analysis_now(config: dict) -> datetime:
    reference = collapse_whitespace(config.get("analysis", {}).get("referenceTime"))
    return parse_datetime(reference, config.get("timezone", "Asia/Seoul")) or datetime.now(
        tz=ZoneInfo(config.get("timezone", "Asia/Seoul"))
    )


def get_lookback_start(config: dict, analysis_now: datetime) -> datetime:
    from datetime import timedelta

    return analysis_now - timedelta(hours=float(config.get("collection", {}).get("reportLookbackHours", 36)))


def get_record_time(record: dict, default_timezone: str) -> datetime | None:
    return parse_datetime(record.get("publish_time") or record.get("collected_time"), default_timezone)
