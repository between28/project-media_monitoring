from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Iterable
from zoneinfo import ZoneInfo


SOURCE_SUFFIX_PATTERN = re.compile(
    r"(?:\||-|–|—|/)\s*(연합뉴스|뉴스1|뉴시스|매일경제|한국경제|서울경제|이데일리|머니투데이)\s*$"
)
NORMALIZE_TITLE_PUNCTUATION = re.compile(r"""[!"#$%&'*+,./:;<=>?@\\^_`{|}~·…ㆍ]""")
TAGGED_NOTE_PATTERN_TEMPLATE = r"(?:^|\s\|\s){tag}=[^|]*"


def collapse_whitespace(text: str | None) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def normalize_text_lower(text: str | None) -> str:
    return collapse_whitespace(str(text or "").lower())


def strip_html(text: str | None) -> str:
    value = str(text or "")
    value = re.sub(r"<script[\s\S]*?</script>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"<style[\s\S]*?</style>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return collapse_whitespace(value)


def limit_text(text: str | None, max_length: int) -> str:
    value = str(text or "")
    if len(value) <= max_length:
        return value
    return value[: max(0, max_length - 3)] + "..."


def add_note(existing_note: str | None, fragment: str | None) -> str:
    current = collapse_whitespace(existing_note)
    addition = collapse_whitespace(fragment)
    if not addition:
        return current
    if not current:
        return addition
    if addition in current:
        return current
    return f"{current} | {addition}"


def upsert_tagged_note(existing_note: str | None, tag: str, value: str) -> str:
    current = collapse_whitespace(existing_note)
    pattern = re.compile(TAGGED_NOTE_PATTERN_TEMPLATE.format(tag=re.escape(tag)))
    cleaned = collapse_whitespace(pattern.sub("", current))
    cleaned = re.sub(r"\s+\|\s+\|", " | ", cleaned).strip("| ").strip()
    return add_note(cleaned, f"{tag}={value}")


def split_keywords(value: str | None) -> list[str]:
    return [item for item in (collapse_whitespace(part) for part in re.split(r"[|,]", str(value or ""))) if item]


def detect_language(text: str | None) -> str:
    value = str(text or "")
    if re.search(r"[가-힣]", value):
        return "ko"
    if re.search(r"[A-Za-z]", value):
        return "en"
    return "unknown"


def get_timezone(timezone_name: str) -> ZoneInfo:
    return ZoneInfo(timezone_name)


def format_datetime(value: datetime, timezone_name: str) -> str:
    tz = get_timezone(timezone_name)
    if value.tzinfo is None:
        value = value.replace(tzinfo=tz)
    return value.astimezone(tz).strftime("%Y-%m-%dT%H:%M:%S%z")


def format_readable_datetime(value: datetime, timezone_name: str) -> str:
    tz = get_timezone(timezone_name)
    if value.tzinfo is None:
        value = value.replace(tzinfo=tz)
    return value.astimezone(tz).strftime("%Y-%m-%d %H:%M")


def parse_datetime(value: str | datetime | None, default_timezone: str = "Asia/Seoul") -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=get_timezone(default_timezone))
        return value

    text = str(value).strip()
    if not text:
        return None

    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        parsed = None

    if parsed is None:
        for pattern in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
            try:
                parsed = datetime.strptime(text, pattern)
                break
            except ValueError:
                continue

    if parsed is None:
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError):
            parsed = None

    if parsed is None:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=get_timezone(default_timezone))
    return parsed


def normalize_link(link: str | None) -> str:
    value = str(link or "").strip()
    if not value:
        return ""
    value = value.split("#", 1)[0]
    value = value.split("?", 1)[0]
    value = re.sub(r"/+$", "", value)
    return value.lower()


def normalize_title(title: str | None) -> str:
    text = str(title or "").lower()
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = re.sub(r"\([^)]+\)", " ", text)
    text = re.sub(r"【[^】]*】", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = SOURCE_SUFFIX_PATTERN.sub(" ", text)
    text = re.sub(r"\b(종합|속보|단독|사진|영상|인터뷰)\b", " ", text)
    text = NORMALIZE_TITLE_PUNCTUATION.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def title_similarity(left_title: str | None, right_title: str | None) -> float:
    left = normalize_title(left_title)
    right = normalize_title(right_title)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    if (len(left) > 12 and right in left) or (len(right) > 12 and left in right):
        return 0.92

    left_tokens = [token for token in left.split(" ") if token]
    right_tokens = [token for token in right.split(" ") if token]
    if not left_tokens or not right_tokens:
        return 0.0

    left_set = set(left_tokens)
    right_set = set(right_tokens)
    union = len(left_set | right_set)
    if not union:
        return 0.0
    return len(left_set & right_set) / union


def looks_like_feed_xml(text: str | None) -> bool:
    lowered = str(text or "").lstrip("\ufeff").strip().lower()
    return any(marker in lowered for marker in ("<rss", "<feed", "<rdf:rdf", "<urlset", "<sitemapindex"))


def looks_like_html(text: str | None) -> bool:
    lowered = str(text or "").lstrip("\ufeff").strip().lower()
    return any(marker in lowered for marker in ("<html", "<body", "<article"))


def strip_article_chrome(html_text: str | None) -> str:
    value = str(html_text or "")
    patterns = [
        r"<script[\s\S]*?</script>",
        r"<style[\s\S]*?</style>",
        r"<noscript[\s\S]*?</noscript>",
        r"<svg[\s\S]*?</svg>",
        r"<form[\s\S]*?</form>",
        r"<header[\s\S]*?</header>",
        r"<footer[\s\S]*?</footer>",
        r"<nav[\s\S]*?</nav>",
        r"<aside[\s\S]*?</aside>",
        r"<button[\s\S]*?</button>",
        r"<!--[\s\S]*?-->",
    ]
    for pattern in patterns:
        value = re.sub(pattern, " ", value, flags=re.IGNORECASE)
    return value


def local_name(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def iter_children_by_name(elements: Iterable, name: str):
    for element in elements:
        if local_name(element.tag) == name:
            yield element


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def build_fingerprint(source_name: str, link: str, title: str, publish_time: str) -> str:
    payload = "|".join([source_name or "", normalize_link(link), title or "", publish_time or ""])
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()

