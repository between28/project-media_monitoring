from __future__ import annotations

import configparser
import json
import re
import shutil
import zipfile
from collections import Counter
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .defaults import clone_default_config
from .utils import collapse_whitespace, normalize_text_lower


PRESS_RELEASE_SOURCE_NAME_PREFIX = "Google News - 자동"

GENERIC_STOPWORDS = {
    "국토교통부",
    "보도자료",
    "동정자료",
    "장관",
    "위원장",
    "관계자",
    "국민",
    "정부",
    "사업",
    "현장",
    "추진",
    "기대",
    "향상",
    "점검",
    "격려",
    "당부",
    "배포",
    "보도",
    "가능",
    "즉시",
    "담당",
    "부서",
    "책임자",
    "과장",
}

PHRASE_NOISE_MARKERS = {
    "당부",
    "강조",
    "기대된다",
    "격려",
    "25분만에",
    "37분",
    "총사업비",
    "총연장",
    "현재",
    "필요",
    "이동 시",
    "으로의",
    "총 8개",
    "총 7개",
}

DOMAIN_SINGLE_TERMS = {
    "주택",
    "공급",
    "신속화",
    "철도",
    "경전철",
    "도시철도",
    "GTX",
    "도로",
    "교통",
    "환승",
    "개통",
    "착공",
    "공사",
    "노선",
    "역",
    "공항",
    "주거",
    "택지",
    "정비",
    "재개발",
    "재건축",
    "부동산",
    "인프라",
    "광역교통",
}

DOMAIN_PHRASE_MARKERS = (
    "경전철",
    "도시철도",
    "광역교통",
    "주택공급",
    "교통편의",
    "교통 접근성",
    "역",
    "노선",
    "공항",
    "택지",
    "재개발",
    "재건축",
    "사업",
    "공사",
)

TITLE_PREFIX_PATTERN = re.compile(r"^[가-힣]{2,10}(?:\s*[가-힣]{1,6})?\s*(장관|위원장|차관|본부장|실장),?\s*")
MANUAL_OVERRIDE_TEMPLATE = {
    "google_queries_add": [],
    "google_queries_disable": [],
    "google_queries_replace": [],
    "topic_keywords_add": [],
    "topic_keywords_disable": [],
    "topic_keywords_replace": [],
    "phrases_add": [],
    "phrases_disable": [],
    "phrases_replace": [],
    "notes": "Use *_replace for full replacement. Use *_add and *_disable for incremental query tuning per session.",
}


def resolve_press_release_input(input_path: str | Path) -> Path:
    path = Path(input_path)
    if path.is_file():
        return path
    if not path.exists():
        raise FileNotFoundError(f"Press release path not found: {path}")

    hwpx_files = sorted(path.glob("*.hwpx"), key=lambda item: item.stat().st_mtime, reverse=True)
    if hwpx_files:
        return hwpx_files[0]

    pdf_files = sorted(path.glob("*.pdf"), key=lambda item: item.stat().st_mtime, reverse=True)
    if pdf_files:
        raise ValueError("PDF-only input is not supported yet. Prefer HWPX input when available.")

    raise FileNotFoundError(f"No HWPX or PDF files found in {path}")


def load_press_release_profile(input_path: str | Path) -> dict[str, Any]:
    path = resolve_press_release_input(input_path)
    suffix = path.suffix.lower()

    if suffix == ".hwpx":
        profile = parse_hwpx_press_release(path)
    elif suffix == ".pdf":
        raise ValueError("PDF parsing is not implemented yet. Prefer HWPX input.")
    else:
        raise ValueError(f"Unsupported press release format: {path.suffix}")

    profile["input_path"] = str(path)
    profile["input_format"] = suffix.lstrip(".")
    return profile


def parse_hwpx_press_release(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        text = extract_hwpx_text(archive)

    lines = normalize_press_release_lines(text)
    if not lines:
        raise ValueError(f"No readable text found in {path}")

    title = extract_press_release_title(lines, path)
    release_info = extract_release_info(lines, path)
    phrases = derive_candidate_phrases(lines, title)
    topic_keywords = derive_topic_keywords(phrases, title)
    queries = build_google_queries(title, phrases, topic_keywords)
    entities = extract_named_entities(lines)

    return {
        "title": title,
        "release_date": release_info["release_date"],
        "release_datetime": release_info["release_datetime"],
        "release_label": release_info["release_label"],
        "department": release_info["department"],
        "summary_lines": lines[:12],
        "phrases": phrases[:8],
        "topic_keywords": topic_keywords[:8],
        "entities": entities,
        "google_queries": queries[:6],
        "body_text": "\n".join(lines),
    }


def extract_hwpx_text(archive: zipfile.ZipFile) -> str:
    candidate_names = ["Preview/PrvText.txt", "Contents/section0.xml"]
    for name in candidate_names:
        if name not in archive.namelist():
            continue
        data = archive.read(name)
        if name.endswith(".txt"):
            for encoding in ("utf-8", "utf-16", "cp949", "euc-kr"):
                try:
                    return data.decode(encoding)
                except UnicodeDecodeError:
                    continue
        else:
            return data.decode("utf-8", errors="replace")
    return ""


def normalize_press_release_lines(text: str) -> list[str]:
    normalized = []
    for raw_line in str(text).splitlines():
        line = collapse_whitespace(raw_line.replace("<>", " ").replace("�", " "))
        line = line.strip("<> ").strip()
        if not line:
            continue
        normalized.append(line)
    return normalized


def extract_press_release_title(lines: list[str], path: Path) -> str:
    candidates = []
    for line in lines[:10]:
        if any(marker in line for marker in ("보도시점", "배포 :", "담당 부서", "책임자")):
            continue
        if line.startswith(("□", "ㅇ", "*")):
            continue
        candidates.append(line)

    if candidates:
        title = max(candidates, key=len)
        title = re.sub(r"^(동정자료|보도자료)\s*", "", title).strip()
        title = clean_phrase(TITLE_PREFIX_PATTERN.sub("", title))
        return collapse_whitespace(title)

    stem = path.stem
    stem = re.sub(r"^\d+\s*", "", stem)
    return collapse_whitespace(stem)


def extract_release_info(lines: list[str], path: Path) -> dict[str, str]:
    text = "\n".join(lines[:10])
    date_match = re.search(r"배포\s*:\s*(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})", text)
    release_date = ""
    release_datetime = ""
    if date_match:
        year, month, day = (int(value) for value in date_match.groups())
        release_date = f"{year:04d}-{month:02d}-{day:02d}"
        release_datetime = datetime(year, month, day, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul")).isoformat()

    release_label_match = re.search(r"보도시점\s*:\s*([^/]+)", text)
    release_label = collapse_whitespace(release_label_match.group(1) if release_label_match else "")

    department = ""
    filename_dept_match = re.search(r"\(([^()]+)\)$", path.stem)
    if filename_dept_match:
        department = collapse_whitespace(filename_dept_match.group(1))

    if not department:
        dept_line = next((line for line in lines if "담당 부서" in line), "")
        dept_tokens = re.findall(r"[가-힣A-Za-z0-9]+과", dept_line)
        if dept_tokens:
            department = dept_tokens[-1]

    return {
        "release_date": release_date,
        "release_datetime": release_datetime,
        "release_label": release_label,
        "department": department,
    }


def derive_candidate_phrases(lines: list[str], title: str) -> list[str]:
    scores: Counter[str] = Counter()

    quoted_phrases = re.findall(r"[“\"]([^”\"]{4,80})[”\"]", title)
    for phrase in quoted_phrases:
        cleaned = clean_phrase(phrase)
        if is_valid_phrase(cleaned) and has_domain_signal(cleaned):
            scores[cleaned] += 8

    title_core = clean_phrase(title)
    if is_valid_phrase(title_core) and has_domain_signal(title_core):
        scores[title_core] += 9

    title_fragments = re.split(r"[,·/()]| 및 ", title_core)
    for fragment in title_fragments:
        cleaned = clean_phrase(fragment)
        if is_valid_phrase(cleaned) and has_domain_signal(cleaned):
            scores[cleaned] += 5

    for line in lines[:20]:
        if len(line) > 100:
            continue
        for phrase in extract_phrases_from_line(line):
            scores[phrase] += 2

    for line in lines:
        for phrase in extract_phrases_from_line(line):
            scores[phrase] += 1

    ordered = []
    seen = set()
    for phrase, _score in scores.most_common():
        if phrase in seen:
            continue
        seen.add(phrase)
        ordered.append(phrase)
    return ordered


def extract_phrases_from_line(line: str) -> list[str]:
    phrases = []
    for match in re.findall(r"[가-힣A-Za-z0-9·\- ]{3,40}", line):
        cleaned = clean_phrase(match)
        if is_valid_phrase(cleaned) and has_domain_signal(cleaned):
            phrases.append(cleaned)
    return phrases


def clean_phrase(text: str) -> str:
    value = collapse_whitespace(text)
    value = (
        value.replace("“", " ")
        .replace("”", " ")
        .replace('"', " ")
        .replace("‘", " ")
        .replace("’", " ")
        .replace("'", " ")
    )
    value = re.sub(r"^[,\-–—:/\s]+|[,\-–—:/\s]+$", "", value)
    value = TITLE_PREFIX_PATTERN.sub("", value)
    value = re.sub(r"^(김용석|김윤덕)\s*", "", value)
    value = re.sub(r"\b(총사업비|총연장|정거장|차량기지|차량)\b.*$", "", value).strip()
    return collapse_whitespace(value)


def is_valid_phrase(phrase: str) -> bool:
    if len(phrase) < 3:
        return False
    if phrase in GENERIC_STOPWORDS:
        return False
    if re.fullmatch(r"[0-9.\- ]+", phrase):
        return False
    if phrase.count(" ") > 8:
        return False
    if phrase.startswith(("보도시점", "배포", "담당", "책임자")):
        return False
    if re.search(r"\d{4,}", phrase):
        return False
    if any(marker in phrase for marker in PHRASE_NOISE_MARKERS):
        return False
    return True


def has_domain_signal(text: str) -> bool:
    if any(marker in text for marker in DOMAIN_PHRASE_MARKERS):
        return True
    return any(term in text for term in DOMAIN_SINGLE_TERMS)


def derive_topic_keywords(phrases: list[str], title: str) -> list[str]:
    scores: Counter[str] = Counter()

    for phrase in phrases[:12]:
        tokens = re.findall(r"[가-힣A-Za-z0-9]{2,12}", phrase)
        for token in tokens:
            if token in GENERIC_STOPWORDS:
                continue
            if re.search(r"^\d+년$", token):
                continue
            if token in DOMAIN_SINGLE_TERMS:
                scores[token] += 4
            elif len(token) >= 3:
                scores[token] += 1

    for token in re.findall(r"[가-힣A-Za-z0-9]{2,12}", title):
        if token in GENERIC_STOPWORDS:
            continue
        if re.search(r"^\d+년$", token):
            continue
        if token in DOMAIN_SINGLE_TERMS:
            scores[token] += 6
        elif len(token) >= 3:
            scores[token] += 2

    ordered = []
    seen = set()
    for keyword, _score in scores.most_common():
        normalized = normalize_text_lower(keyword)
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(keyword)
    return ordered


def build_google_queries(title: str, phrases: list[str], topic_keywords: list[str]) -> list[str]:
    queries = []
    anchor = next(
        (keyword for keyword in topic_keywords if keyword not in DOMAIN_SINGLE_TERMS and keyword not in GENERIC_STOPWORDS),
        "",
    )
    entities = extract_named_entities_from_text(title + "\n" + "\n".join(phrases[:6]))

    core_title = clean_phrase(title)
    if core_title and has_domain_signal(core_title):
        queries.append(core_title)

    for phrase in phrases[:6]:
        if phrase in queries or " " not in phrase:
            continue
        if anchor and anchor not in phrase and phrase.count(" ") < 2:
            continue
        if phrase.startswith(tuple(str(number) for number in range(10))):
            continue
        if any(marker in phrase for marker in PHRASE_NOISE_MARKERS):
            continue
        if phrase not in queries:
            queries.append(phrase)

    if anchor:
        if "경전철" in topic_keywords and f"{anchor} 경전철" not in queries:
            queries.append(f"{anchor} 경전철")
        if "개통" in topic_keywords and f"{anchor} 개통" not in queries:
            queries.append(f"{anchor} 개통")
        for entity in entities[:3]:
            if entity == anchor:
                continue
            query = f"{anchor} {entity}"
            if query not in queries:
                queries.append(query)

    cleaned_queries = []
    seen = set()
    for query in queries:
        normalized = normalize_text_lower(query)
        if not normalized or normalized in seen:
            continue
        if len(query) < 4:
            continue
        seen.add(normalized)
        cleaned_queries.append(query)
    return cleaned_queries[:6]


def extract_named_entities(lines: list[str]) -> list[str]:
    return extract_named_entities_from_text("\n".join(lines))


def extract_named_entities_from_text(text: str) -> list[str]:
    candidates = []
    patterns = [
        r"[가-힣A-Za-z0-9]{2,12}역",
        r"[가-힣]{2,10}(?:구|동|권)",
        r"[가-힣A-Za-z0-9]{2,12}선",
    ]
    for pattern in patterns:
        candidates.extend(re.findall(pattern, text))

    ordered = []
    seen = set()
    for candidate in candidates:
        cleaned = clean_phrase(candidate)
        normalized = normalize_text_lower(cleaned)
        if not cleaned or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(cleaned)
    return ordered


def build_config_from_press_release(profile: dict[str, Any], manual_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    effective_profile = apply_manual_overrides_to_profile(profile, manual_overrides)
    base_config = clone_default_config()
    non_google_sources = [source for source in base_config["sources"] if source["source_type"] != "google_news"]
    generic_keyword_rules = [
        rule
        for rule in base_config["keywordRules"]
        if rule["bucket"] not in {"topic", "phrase"}
    ]

    derived_sources = []
    for query in effective_profile.get("google_queries", []):
        derived_sources.append(
            {
                "enabled": True,
                "source_name": f"{PRESS_RELEASE_SOURCE_NAME_PREFIX} - {limit_query_label(query)}",
                "source_type": "google_news",
                "category_group": "press_release_keyword",
                "feed_url": "",
                "keyword": query,
                "notes": "derived from press release",
            }
        )

    derived_keyword_rules = []
    for keyword in effective_profile.get("topic_keywords", [])[:8]:
        derived_keyword_rules.append(
            {
                "enabled": True,
                "bucket": "topic",
                "keyword": keyword,
                "weight": 3 if len(keyword) >= 3 else 2,
                "notes": "derived from press release",
            }
        )
    for phrase in effective_profile.get("phrases", [])[:8]:
        derived_keyword_rules.append(
            {
                "enabled": True,
                "bucket": "phrase",
                "keyword": phrase,
                "weight": 5 if " " in phrase or len(phrase) >= 8 else 4,
                "notes": "derived from press release",
            }
        )

    derived_core_keywords = []
    seen_core_keywords = set()
    for keyword in effective_profile.get("topic_keywords", []):
        normalized = normalize_text_lower(keyword)
        if not normalized or normalized in seen_core_keywords:
            continue
        seen_core_keywords.add(normalized)
        derived_core_keywords.append(keyword)
        if len(derived_core_keywords) >= 6:
            break

    topic_name = effective_profile.get("title") or base_config["topic"]["name"]
    release_date = effective_profile.get("release_date") or base_config["topic"]["announcementDate"]
    release_datetime = effective_profile.get("release_datetime") or base_config["topic"]["announcementDateTime"]

    base_config["topic"] = {
        "name": topic_name,
        "announcementDate": release_date,
        "announcementDateTime": release_datetime,
    }
    base_config["analysis"] = {
        "referenceTime": "",
        "windowStartTime": release_datetime,
    }
    base_config.setdefault("collection", {})["rawCoreKeywords"] = derived_core_keywords or base_config.get("collection", {}).get("rawCoreKeywords", [])
    base_config.setdefault("collection", {})["rawMinimumKeywordHits"] = 1
    base_config.setdefault("collection", {})["maxItemsPerFeed"] = max(
        int(base_config.get("collection", {}).get("maxItemsPerFeed", 10)),
        30,
    )
    base_config.setdefault("collection", {})["maxItemsPerGoogleNewsFeed"] = max(
        int(base_config.get("collection", {}).get("maxItemsPerGoogleNewsFeed", 8)),
        20,
    )
    base_config["genericThemeKeywords"] = derived_core_keywords[:]
    base_config["sources"] = derived_sources + non_google_sources
    base_config["keywordRules"] = generic_keyword_rules + dedupe_keyword_rules(derived_keyword_rules)
    return base_config


def limit_query_label(query: str) -> str:
    query = collapse_whitespace(query)
    return query if len(query) <= 40 else query[:37] + "..."


def dedupe_keyword_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped = []
    seen = set()
    for rule in rules:
        key = (rule["bucket"], normalize_text_lower(rule["keyword"]))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rule)
    return deduped


def save_press_release_outputs(profile: dict[str, Any], config: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    profile_path = output_path / "press_release_profile.json"
    config_path = output_path / "press_release_config.json"
    markdown_path = output_path / "press_release_profile.md"

    profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(build_press_release_markdown(profile), encoding="utf-8")

    return {
        "profile_json": str(profile_path),
        "config_json": str(config_path),
        "profile_markdown": str(markdown_path),
    }


def build_press_release_markdown(profile: dict[str, Any]) -> str:
    lines = [
        "# 보도자료 자동 추출 결과",
        "",
        f"- 제목: {profile.get('title', '')}",
        f"- 배포일: {profile.get('release_date', '')}",
        f"- 담당부서: {profile.get('department', '')}",
        "",
        "## 추천 구문 키워드",
    ]
    for phrase in profile.get("phrases", [])[:8]:
        lines.append(f"- {phrase}")

    lines.extend(["", "## 추천 일반 키워드"])
    for keyword in profile.get("topic_keywords", [])[:8]:
        lines.append(f"- {keyword}")

    lines.extend(["", "## 추천 Google News 질의"])
    for query in profile.get("google_queries", [])[:6]:
        lines.append(f"- {query}")
    return "\n".join(lines) + "\n"


def build_press_session_paths(profile: dict[str, Any], session_root: str | Path) -> dict[str, str]:
    root = Path(session_root)
    session_id = build_press_session_id(profile)
    session_dir = root / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    inputs_dir = session_dir / "inputs"
    config_dir = session_dir / "config"
    data_dir = session_dir / "data"
    outputs_dir = session_dir / "outputs"
    briefings_dir = outputs_dir / "briefings"
    references_dir = outputs_dir / "references"
    logs_dir = session_dir / "logs"

    for directory in (inputs_dir, config_dir, data_dir, outputs_dir, briefings_dir, references_dir, logs_dir):
        directory.mkdir(parents=True, exist_ok=True)

    return {
        "session_id": session_id,
        "session_dir": str(session_dir),
        "inputs_dir": str(inputs_dir),
        "config_dir": str(config_dir),
        "data_dir": str(data_dir),
        "outputs_dir": str(outputs_dir),
        "logs_dir": str(logs_dir),
        "db_path": str(data_dir / "session.sqlite3"),
        "profile_json": str(config_dir / "press_release_profile.json"),
        "profile_markdown": str(config_dir / "press_release_profile.md"),
        "queries_auto_json": str(config_dir / "queries.auto.json"),
        "queries_manual_path": str(config_dir / "queries.manual.ini"),
        "config_auto_json": str(config_dir / "config.auto.json"),
        "config_effective_json": str(config_dir / "config.effective.json"),
        "metadata_json": str(session_dir / "session_metadata.json"),
        "briefings_dir": str(briefings_dir),
        "references_dir": str(references_dir),
        "latest_briefing": str(outputs_dir / "latest_briefing.md"),
        "latest_reference_markdown": str(outputs_dir / "latest_reference_articles.md"),
        "latest_reference_csv": str(outputs_dir / "latest_reference_articles.csv"),
        "daily_outputs_json": str(outputs_dir / "daily_outputs.json"),
    }


def build_press_session_id(profile: dict[str, Any]) -> str:
    release_date = profile.get("release_date") or "undated"
    title = profile.get("title") or "press_release"
    slug = sanitize_session_slug(title)
    return f"{release_date.replace('-', '')}_{slug}"


def sanitize_session_slug(text: str) -> str:
    value = collapse_whitespace(text)
    value = re.sub(r"[^\w가-힣]+", "-", value, flags=re.UNICODE)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    if len(value) > 50:
        value = value[:50].rstrip("-")
    return value or "press_release"


def save_press_session_metadata(
    profile: dict[str, Any],
    config: dict[str, Any],
    session_paths: dict[str, str],
    manual_overrides: dict[str, Any] | None = None,
) -> dict[str, str]:
    auto_config = build_config_from_press_release(profile)
    queries_auto = build_query_payload(profile)
    effective_profile = apply_manual_overrides_to_profile(profile, manual_overrides)
    ensure_manual_override_file(session_paths["queries_manual_path"], manual_overrides)
    copy_press_release_inputs(profile, session_paths)

    Path(session_paths["profile_json"]).write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(session_paths["profile_markdown"]).write_text(build_press_release_markdown(profile), encoding="utf-8")
    Path(session_paths["queries_auto_json"]).write_text(json.dumps(queries_auto, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(session_paths["config_auto_json"]).write_text(json.dumps(auto_config, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(session_paths["config_effective_json"]).write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    metadata = {
        "session_id": session_paths["session_id"],
        "session_dir": session_paths["session_dir"],
        "inputs_dir": session_paths["inputs_dir"],
        "config_dir": session_paths["config_dir"],
        "data_dir": session_paths["data_dir"],
        "outputs_dir": session_paths["outputs_dir"],
        "db_path": session_paths["db_path"],
        "topic_name": config.get("topic", {}).get("name", ""),
        "announcement_date": config.get("topic", {}).get("announcementDate", ""),
        "announcement_datetime": config.get("topic", {}).get("announcementDateTime", ""),
        "press_release_input_path": profile.get("input_path", ""),
        "press_release_format": profile.get("input_format", ""),
        "auto_queries_path": session_paths["queries_auto_json"],
        "manual_queries_path": session_paths["queries_manual_path"],
        "effective_config_path": session_paths["config_effective_json"],
        "active_google_queries": effective_profile.get("google_queries", []),
    }
    Path(session_paths["metadata_json"]).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "session_dir": session_paths["session_dir"],
        "profile_json": session_paths["profile_json"],
        "profile_markdown": session_paths["profile_markdown"],
        "queries_auto_json": session_paths["queries_auto_json"],
        "queries_manual_path": session_paths["queries_manual_path"],
        "config_auto_json": session_paths["config_auto_json"],
        "config_effective_json": session_paths["config_effective_json"],
        "metadata_json": session_paths["metadata_json"],
    }


def build_query_payload(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": profile.get("title", ""),
        "release_date": profile.get("release_date", ""),
        "release_datetime": profile.get("release_datetime", ""),
        "phrases": list(profile.get("phrases", [])),
        "topic_keywords": list(profile.get("topic_keywords", [])),
        "google_queries": list(profile.get("google_queries", [])),
    }


def ensure_manual_override_file(path: str | Path, manual_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    override_path = Path(path)
    if manual_overrides is None:
        if override_path.exists():
            manual_overrides = parse_manual_override_file(override_path)
        else:
            legacy_json_path = override_path.with_suffix(".json")
            if legacy_json_path.exists():
                manual_overrides = json.loads(legacy_json_path.read_text(encoding="utf-8"))
            else:
                manual_overrides = deepcopy(MANUAL_OVERRIDE_TEMPLATE)
    else:
        manual_overrides = normalize_manual_overrides(manual_overrides)

    normalized = normalize_manual_overrides(manual_overrides)
    serialized = build_manual_override_file_text(normalized)
    if not override_path.exists() or override_path.read_text(encoding="utf-8") != serialized:
        override_path.write_text(serialized, encoding="utf-8")
    return normalized


def load_session_manual_overrides(session_paths: dict[str, str]) -> dict[str, Any]:
    return ensure_manual_override_file(session_paths["queries_manual_path"])


def normalize_manual_overrides(overrides: dict[str, Any] | None) -> dict[str, Any]:
    normalized = deepcopy(MANUAL_OVERRIDE_TEMPLATE)
    if not overrides:
        return normalized
    for key in MANUAL_OVERRIDE_TEMPLATE:
        if key == "notes":
            normalized[key] = collapse_whitespace(overrides.get(key)) or MANUAL_OVERRIDE_TEMPLATE["notes"]
            continue
        value = overrides.get(key, [])
        if not isinstance(value, list):
            value = []
        normalized[key] = dedupe_text_values(value)
    return normalized


def apply_manual_overrides_to_profile(profile: dict[str, Any], manual_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    effective = deepcopy(profile)
    overrides = normalize_manual_overrides(manual_overrides)
    effective["google_queries"] = apply_list_override(
        effective.get("google_queries", []),
        overrides["google_queries_add"],
        overrides["google_queries_disable"],
        overrides["google_queries_replace"],
    )
    effective["topic_keywords"] = apply_list_override(
        effective.get("topic_keywords", []),
        overrides["topic_keywords_add"],
        overrides["topic_keywords_disable"],
        overrides["topic_keywords_replace"],
    )
    effective["phrases"] = apply_list_override(
        effective.get("phrases", []),
        overrides["phrases_add"],
        overrides["phrases_disable"],
        overrides["phrases_replace"],
    )
    return effective


def apply_list_override(base_values: list[str], add_values: list[str], disable_values: list[str], replace_values: list[str]) -> list[str]:
    if replace_values:
        working = dedupe_text_values(replace_values)
    else:
        working = dedupe_text_values(base_values)

    disabled = {normalize_text_lower(value) for value in disable_values if collapse_whitespace(value)}
    filtered = [value for value in working if normalize_text_lower(value) not in disabled]
    for value in dedupe_text_values(add_values):
        normalized = normalize_text_lower(value)
        if normalized and all(normalize_text_lower(existing) != normalized for existing in filtered):
            filtered.append(value)
    return filtered


def dedupe_text_values(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        cleaned = collapse_whitespace(value)
        normalized = normalize_text_lower(cleaned)
        if not cleaned or normalized in seen:
            continue
        seen.add(normalized)
        result.append(cleaned)
    return result


def parse_manual_override_file(path: Path) -> dict[str, Any]:
    parser = configparser.ConfigParser(
        interpolation=None,
        comment_prefixes=("#", ";"),
        inline_comment_prefixes=("#", ";"),
        strict=False,
    )
    parser.optionxform = str
    parser.read(path, encoding="utf-8")

    overrides = {}
    for section_name in ("google_queries", "topic_keywords", "phrases"):
        section = parser[section_name] if parser.has_section(section_name) else {}
        overrides[f"{section_name}_add"] = split_override_lines(section.get("add", ""))
        overrides[f"{section_name}_disable"] = split_override_lines(section.get("disable", ""))
        overrides[f"{section_name}_replace"] = split_override_lines(section.get("replace", ""))
    return normalize_manual_overrides(overrides)


def split_override_lines(value: str) -> list[str]:
    lines = []
    for raw_line in str(value or "").splitlines():
        cleaned = collapse_whitespace(raw_line)
        if not cleaned:
            continue
        lines.append(cleaned)
    return dedupe_text_values(lines)


def build_manual_override_file_text(overrides: dict[str, Any]) -> str:
    lines = [
        "# 세션별 수동 쿼리 보완 파일입니다.",
        "# 값은 한 줄에 하나씩 입력합니다. 각 항목은 아래처럼 공백 4칸 들여써서 적습니다.",
        "# 쉼표(,)로 여러 값을 한 줄에 적지 않습니다.",
        "# 띄어쓰기는 검색에 쓰고 싶은 문구 그대로 유지합니다.",
        "# 값을 비워두고 싶으면 `add =` 또는 `disable =` 아래를 빈 상태로 둡니다.",
        "# 예시:",
        "# add =",
        "#     동북선 경전철 개통",
        "#     서울 동북권 경전철",
        "# disable =",
        "#     동북선 왕십리역",
        "# replace =",
        "#     동북선 경전철 개통",
        "#     서울 동북권 교통편의 향상",
        "#",
        "# add: 자동 추출 결과에 추가",
        "# disable: 자동 추출 결과 중 제외",
        "# replace: 자동 추출 결과 대신 이 목록을 기본값으로 사용",
        "",
    ]
    lines.extend(
        build_manual_override_section(
            "google_queries",
            "Google News 질의",
            "언론 검색에 직접 사용할 질의입니다.",
            overrides["google_queries_add"],
            overrides["google_queries_disable"],
            overrides["google_queries_replace"],
        )
    )
    lines.append("")
    lines.extend(
        build_manual_override_section(
            "topic_keywords",
            "일반 키워드",
            "정책 관련도 점수 계산에 쓰는 일반 키워드입니다.",
            overrides["topic_keywords_add"],
            overrides["topic_keywords_disable"],
            overrides["topic_keywords_replace"],
        )
    )
    lines.append("")
    lines.extend(
        build_manual_override_section(
            "phrases",
            "구문 키워드",
            "정책명·사업명·고유 표현처럼 강한 신호로 보는 구문입니다.",
            overrides["phrases_add"],
            overrides["phrases_disable"],
            overrides["phrases_replace"],
        )
    )
    lines.append("")
    return "\n".join(lines)


def build_manual_override_section(
    section_name: str,
    section_label: str,
    section_description: str,
    add_values: list[str],
    disable_values: list[str],
    replace_values: list[str],
) -> list[str]:
    lines = [
        f"[{section_name}]",
        f"# {section_label}: {section_description}",
        "# 입력 규칙: 한 줄에 하나씩, 쉼표 없이 입력합니다.",
        "# add: 여기에 적은 값은 자동 추출 결과에 추가됩니다.",
        "add =",
    ]
    lines.extend(f"    {value}" for value in add_values)
    lines.extend(
        [
            "",
            "# disable: 자동 추출된 값 중 제외할 문구를 정확히 적습니다.",
            "# 자동 추출값과 띄어쓰기까지 가능한 한 동일하게 적는 편이 안전합니다.",
            "disable =",
        ]
    )
    lines.extend(f"    {value}" for value in disable_values)
    lines.extend(
        [
            "",
            "# replace: 자동 추출값 대신 아래 목록을 기본값으로 사용합니다.",
            "# 비워두면 auto + add/disable 규칙을 사용합니다.",
            "replace =",
        ]
    )
    lines.extend(f"    {value}" for value in replace_values)
    return lines


def copy_press_release_inputs(profile: dict[str, Any], session_paths: dict[str, str]) -> None:
    input_path = Path(profile.get("input_path", ""))
    if not input_path.exists():
        return

    copy_file_if_needed(input_path, Path(session_paths["inputs_dir"]) / input_path.name)

    counterpart_suffix = ".pdf" if input_path.suffix.lower() == ".hwpx" else ".hwpx"
    counterpart_path = input_path.with_suffix(counterpart_suffix)
    if counterpart_path.exists():
        copy_file_if_needed(counterpart_path, Path(session_paths["inputs_dir"]) / counterpart_path.name)


def copy_file_if_needed(source: Path, destination: Path) -> None:
    if destination.exists():
        try:
            if destination.read_bytes() == source.read_bytes():
                return
        except OSError:
            pass
    shutil.copy2(source, destination)
