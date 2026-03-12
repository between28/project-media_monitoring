from __future__ import annotations

import logging
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .analysis import calculate_policy_score, get_policy_hit_stats_from_keywords
from .config import get_analysis_now, get_keyword_rules_by_buckets, get_lookback_start, resolve_feed_url
from .db import insert_raw_articles
from .utils import (
    add_note,
    collapse_whitespace,
    detect_language,
    format_datetime,
    iter_children_by_name,
    limit_text,
    local_name,
    looks_like_feed_xml,
    normalize_text_lower,
    parse_datetime,
    strip_html,
)


LOGGER = logging.getLogger(__name__)


def fetch_url_text(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Python RSS Collector)",
            "Accept": "application/rss+xml, application/xml, text/xml, text/html;q=0.9, */*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
        encodings = []
        content_type = response.headers.get_content_charset()
        if content_type:
            encodings.append(content_type)
        encodings.extend(["utf-8", "cp949", "euc-kr"])
        for encoding in encodings:
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")


def collect_articles(connection, config: dict, source_limit: int | None = None) -> dict:
    policy_rules = get_keyword_rules_by_buckets(config, ["topic", "phrase"])
    analysis_now = get_analysis_now(config)
    lookback_start = get_lookback_start(config, analysis_now)
    collected_time = format_datetime(datetime.now(ZoneInfo(config["timezone"])), config["timezone"])
    sources = [source for source in config.get("sources", []) if source.get("enabled", True)]
    if source_limit:
        sources = sources[:source_limit]

    prepared_articles: list[dict] = []
    per_source_stats: list[dict] = []

    for source in sources:
        feed_url = resolve_feed_url(source)
        if not feed_url:
            continue

        kept_count = 0
        dropped_by_relevance = 0
        dropped_by_date = 0

        try:
            max_items = get_max_items_for_source(source, config)
            response_text = fetch_url_text(feed_url)
            if not looks_like_feed_xml(response_text):
                raise ValueError("Non-feed response returned by source URL")

            items = parse_source_items(response_text, source, max_items, config)
            for item in items:
                if not should_collect_item(item, source, policy_rules, config):
                    dropped_by_relevance += 1
                    continue
                if not should_keep_item_in_collection_window(item, collected_time, lookback_start, analysis_now, config):
                    dropped_by_date += 1
                    continue

                kept_count += 1
                prepared_articles.append(
                    {
                        "collected_time": collected_time,
                        "publish_time": item.get("publish_time") or collected_time,
                        "source_type": source["source_type"],
                        "source_name": source["source_name"],
                        "category_group": source["category_group"],
                        "title": item.get("title", ""),
                        "link": item.get("link", ""),
                        "summary": item.get("summary", ""),
                        "keyword": "",
                        "duplicate_flag": "",
                        "normalized_title": "",
                        "policy_score": 0,
                        "frame_category": "",
                        "importance_score": 0,
                        "language": item.get("language", "unknown"),
                        "notes": add_note(
                            add_note("", f"source_keyword={source['keyword']}" if source.get("keyword") else ""),
                            f"feed={limit_text(feed_url, 180)}",
                        ),
                        "body_text": "",
                    }
                )

            LOGGER.info(
                "Collected %s items from %s after prefilter/window; dropped %s by relevance and %s by date.",
                kept_count,
                source["source_name"],
                dropped_by_relevance,
                dropped_by_date,
            )
        except (ValueError, ET.ParseError, urllib.error.URLError, TimeoutError) as error:
            LOGGER.warning("RSS fetch failed for %s: %s", source["source_name"], error)

        per_source_stats.append(
            {
                "source_name": source["source_name"],
                "kept": kept_count,
                "dropped_by_relevance": dropped_by_relevance,
                "dropped_by_date": dropped_by_date,
            }
        )

    inserted_count = insert_raw_articles(connection, prepared_articles)
    return {
        "prepared_count": len(prepared_articles),
        "inserted_count": inserted_count,
        "per_source_stats": per_source_stats,
    }


def get_max_items_for_source(source: dict, config: dict) -> int:
    if source.get("source_type") == "google_news":
        collection = config.get("collection", {})
        return int(collection.get("maxItemsPerGoogleNewsFeed", collection.get("maxItemsPerFeed", 10)))
    return int(config.get("collection", {}).get("maxItemsPerFeed", 10))


def should_collect_item(item: dict, source: dict, policy_rules: list[dict], config: dict) -> bool:
    preview_record = {
        "title": item.get("title", ""),
        "summary": item.get("summary", ""),
        "body_text": "",
        "source_name": source["source_name"],
    }
    score_result = calculate_policy_score(preview_record, policy_rules, config)
    hit_stats = get_policy_hit_stats_from_keywords(score_result["keywords"], config)

    if hit_stats["phraseHits"] > 0:
        return True
    if hit_stats["totalHits"] < int(config.get("collection", {}).get("rawMinimumKeywordHits", 2)):
        return False
    return has_collection_core_keyword(score_result["keywords"], config)


def has_collection_core_keyword(keywords: list[str], config: dict) -> bool:
    lookup = {normalize_text_lower(keyword): True for keyword in config.get("collection", {}).get("rawCoreKeywords", [])}
    return any(lookup.get(normalize_text_lower(keyword), False) for keyword in keywords)


def should_keep_item_in_collection_window(item: dict, collected_time: str, lookback_start, analysis_now, config: dict) -> bool:
    timestamp = parse_datetime(item.get("publish_time") or collected_time, config["timezone"])
    if not timestamp:
        return False
    return lookback_start <= timestamp <= analysis_now


def parse_source_items(xml_text: str, source: dict, max_items: int, config: dict) -> list[dict]:
    root = ET.fromstring(xml_text)
    root_name = local_name(root.tag)
    if root_name in {"urlset", "sitemapindex"}:
        return parse_sitemap_items(root, source, max_items, config, remaining_depth=1)
    return parse_feed_items(root, max_items, config)


def parse_feed_items(root, max_items: int, config: dict) -> list[dict]:
    root_name = local_name(root.tag)
    items = []
    if root_name in {"rss", "RDF"}:
        channel = next(iter(iter_children_by_name(root, "channel")), root)
        items = [parse_rss_item(item, config) for item in list(iter_children_by_name(channel, "item"))[:max_items]]
    elif root_name == "feed":
        items = [parse_atom_entry(entry, config) for entry in list(iter_children_by_name(root, "entry"))[:max_items]]
    return [item for item in items if item.get("title") and item.get("link")][:max_items]


def parse_sitemap_items(root, source: dict, max_items: int, config: dict, remaining_depth: int) -> list[dict]:
    root_name = local_name(root.tag)
    if root_name == "sitemapindex":
        return parse_nested_sitemaps(root, source, max_items, config, remaining_depth)
    if root_name != "urlset":
        return []

    items = []
    for node in list(iter_children_by_name(root, "url"))[:max_items]:
        item = parse_sitemap_url(node, config)
        if item.get("title") and item.get("link"):
            items.append(item)
    return items[:max_items]


def parse_nested_sitemaps(root, source: dict, max_items: int, config: dict, remaining_depth: int) -> list[dict]:
    if remaining_depth <= 0:
        return []

    items: list[dict] = []
    for sitemap in iter_children_by_name(root, "sitemap"):
        nested_url = get_element_text_by_local_names(sitemap, ["loc"])
        if not nested_url:
            continue
        try:
            nested_text = fetch_url_text(nested_url)
            if not looks_like_feed_xml(nested_text):
                raise ValueError("Nested sitemap returned non-feed response")
            nested_root = ET.fromstring(nested_text)
            items.extend(parse_sitemap_items(nested_root, source, max_items - len(items), config, remaining_depth - 1))
        except (ValueError, ET.ParseError, urllib.error.URLError, TimeoutError) as error:
            LOGGER.warning("Nested sitemap fetch failed for %s: %s", source["source_name"], error)
        if len(items) >= max_items:
            break
    return items[:max_items]


def parse_sitemap_url(node, config: dict) -> dict:
    link = collapse_whitespace(get_element_text_by_local_names(node, ["loc"]))
    lastmod = get_element_text_by_local_names(node, ["lastmod"])
    news_node = next(iter(iter_children_by_name(node, "news")), None)
    title = get_element_text_by_local_names(news_node, ["title"]) if news_node is not None else ""
    keyword_summary = get_element_text_by_local_names(news_node, ["keywords"]) if news_node is not None else ""
    publish_text = get_element_text_by_local_names(news_node, ["publication_date"]) if news_node is not None else ""
    publish_time = parse_datetime(publish_text or lastmod, config["timezone"])
    normalized_title = collapse_whitespace(title or derive_title_from_url(link))
    summary = limit_text(strip_html(keyword_summary), 600)
    return {
        "title": normalized_title,
        "link": link,
        "publish_time": format_datetime(publish_time, config["timezone"]) if publish_time else "",
        "summary": summary,
        "language": detect_language(f"{normalized_title} {summary}"),
    }


def parse_rss_item(item, config: dict) -> dict:
    title = get_element_text_by_local_names(item, ["title"])
    link = extract_feed_link(item)
    publish_text = get_element_text_by_local_names(item, ["pubDate", "date", "published", "updated"])
    summary = strip_html(get_element_text_by_local_names(item, ["description", "summary", "encoded", "content"]))
    publish_time = parse_datetime(publish_text, config["timezone"])
    return {
        "title": collapse_whitespace(title),
        "link": collapse_whitespace(link),
        "publish_time": format_datetime(publish_time, config["timezone"]) if publish_time else "",
        "summary": limit_text(summary, 600),
        "language": detect_language(f"{title} {summary}"),
    }


def parse_atom_entry(entry, config: dict) -> dict:
    title = get_element_text_by_local_names(entry, ["title"])
    link = extract_feed_link(entry)
    publish_text = get_element_text_by_local_names(entry, ["published", "updated"])
    summary = strip_html(get_element_text_by_local_names(entry, ["summary", "content"]))
    publish_time = parse_datetime(publish_text, config["timezone"])
    return {
        "title": collapse_whitespace(title),
        "link": collapse_whitespace(link),
        "publish_time": format_datetime(publish_time, config["timezone"]) if publish_time else "",
        "summary": limit_text(summary, 600),
        "language": detect_language(f"{title} {summary}"),
    }


def extract_feed_link(element) -> str:
    for child in list(element):
        if local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href")
        if href:
            return href
        text = collapse_whitespace(child.text)
        if text:
            return text
    return ""


def get_element_text_by_local_names(element, names: list[str]) -> str:
    if element is None:
        return ""
    wanted = set(names)
    for child in list(element):
        if local_name(child.tag) in wanted and child.text:
            return child.text
    return ""


def derive_title_from_url(url: str) -> str:
    value = urllib.parse.urlsplit(url).path
    if not value:
        return ""
    segment = Path(value).name
    return urllib.parse.unquote(segment).replace("-", " ").replace("_", " ")
