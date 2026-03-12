from __future__ import annotations

import sqlite3
from pathlib import Path

from .defaults import DEFAULT_RUNTIME_SETTINGS, RAW_COLUMNS
from .utils import build_fingerprint


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS config_sources (
            sort_order INTEGER NOT NULL,
            enabled INTEGER NOT NULL,
            source_name TEXT PRIMARY KEY,
            source_type TEXT NOT NULL,
            category_group TEXT NOT NULL,
            feed_url TEXT NOT NULL,
            keyword TEXT NOT NULL,
            notes TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS config_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sort_order INTEGER NOT NULL,
            enabled INTEGER NOT NULL,
            bucket TEXT NOT NULL,
            keyword TEXT NOT NULL,
            weight REAL NOT NULL,
            notes TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS config_runtime (
            sort_order INTEGER NOT NULL,
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            notes TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS raw_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fingerprint TEXT NOT NULL UNIQUE,
            collected_time TEXT NOT NULL,
            publish_time TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_name TEXT NOT NULL,
            category_group TEXT NOT NULL,
            title TEXT NOT NULL,
            link TEXT NOT NULL,
            summary TEXT NOT NULL,
            keyword TEXT NOT NULL,
            duplicate_flag TEXT NOT NULL,
            normalized_title TEXT NOT NULL,
            policy_score REAL NOT NULL,
            frame_category TEXT NOT NULL,
            importance_score REAL NOT NULL,
            language TEXT NOT NULL,
            notes TEXT NOT NULL,
            body_text TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_raw_publish_time ON raw_articles(publish_time);
        CREATE INDEX IF NOT EXISTS idx_raw_source_name ON raw_articles(source_name);

        CREATE TABLE IF NOT EXISTS processed_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_time TEXT NOT NULL,
            rank INTEGER NOT NULL,
            raw_article_id INTEGER,
            collected_time TEXT NOT NULL,
            publish_time TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_name TEXT NOT NULL,
            category_group TEXT NOT NULL,
            title TEXT NOT NULL,
            link TEXT NOT NULL,
            summary TEXT NOT NULL,
            keyword TEXT NOT NULL,
            duplicate_flag TEXT NOT NULL,
            normalized_title TEXT NOT NULL,
            policy_score REAL NOT NULL,
            frame_category TEXT NOT NULL,
            importance_score REAL NOT NULL,
            language TEXT NOT NULL,
            notes TEXT NOT NULL,
            body_text TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS briefing_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section_order INTEGER NOT NULL,
            generated_time TEXT NOT NULL,
            topic_name TEXT NOT NULL,
            section_name TEXT NOT NULL,
            content TEXT NOT NULL,
            supporting_articles TEXT NOT NULL,
            notes TEXT NOT NULL
        );
        """
    )
    connection.commit()


def seed_config_tables(connection: sqlite3.Connection, config: dict, reset: bool = False) -> None:
    ensure_schema(connection)
    if reset:
        connection.execute("DELETE FROM config_sources")
        connection.execute("DELETE FROM config_keywords")
        connection.execute("DELETE FROM config_runtime")

    source_count = connection.execute("SELECT COUNT(*) FROM config_sources").fetchone()[0]
    if not source_count:
        connection.executemany(
            """
            INSERT INTO config_sources (
                sort_order, enabled, source_name, source_type, category_group, feed_url, keyword, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    index,
                    int(bool(record["enabled"])),
                    record["source_name"],
                    record["source_type"],
                    record["category_group"],
                    record["feed_url"],
                    record["keyword"],
                    record["notes"],
                )
                for index, record in enumerate(config.get("sources", []), start=1)
            ],
        )

    keyword_count = connection.execute("SELECT COUNT(*) FROM config_keywords").fetchone()[0]
    if not keyword_count:
        connection.executemany(
            """
            INSERT INTO config_keywords (
                sort_order, enabled, bucket, keyword, weight, notes
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    index,
                    int(bool(record["enabled"])),
                    record["bucket"],
                    record["keyword"],
                    float(record["weight"]),
                    record["notes"],
                )
                for index, record in enumerate(config.get("keywordRules", []), start=1)
            ],
        )

    runtime_count = connection.execute("SELECT COUNT(*) FROM config_runtime").fetchone()[0]
    if not runtime_count:
        connection.executemany(
            """
            INSERT INTO config_runtime (sort_order, key, value, notes) VALUES (?, ?, ?, ?)
            """,
            [
                (index, record["key"], record["value"], record["notes"])
                for index, record in enumerate(DEFAULT_RUNTIME_SETTINGS, start=1)
            ],
        )

    connection.commit()


def read_config_sources(connection: sqlite3.Connection) -> list[dict]:
    return [
        dict(row)
        for row in connection.execute(
            """
            SELECT enabled, source_name, source_type, category_group, feed_url, keyword, notes
            FROM config_sources
            ORDER BY sort_order
            """
        )
    ]


def read_config_keywords(connection: sqlite3.Connection) -> list[dict]:
    return [
        dict(row)
        for row in connection.execute(
            """
            SELECT enabled, bucket, keyword, weight, notes
            FROM config_keywords
            ORDER BY sort_order, id
            """
        )
    ]


def read_runtime_settings(connection: sqlite3.Connection) -> list[dict]:
    return [
        dict(row)
        for row in connection.execute(
            """
            SELECT key, value, notes
            FROM config_runtime
            ORDER BY sort_order
            """
        )
    ]


def insert_raw_articles(connection: sqlite3.Connection, articles: list[dict]) -> int:
    inserted = 0
    for article in articles:
        article = dict(article)
        article["fingerprint"] = article.get("fingerprint") or build_fingerprint(
            article.get("source_name", ""),
            article.get("link", ""),
            article.get("title", ""),
            article.get("publish_time", ""),
        )
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO raw_articles (
                fingerprint, collected_time, publish_time, source_type, source_name, category_group,
                title, link, summary, keyword, duplicate_flag, normalized_title, policy_score,
                frame_category, importance_score, language, notes, body_text
            ) VALUES (
                :fingerprint, :collected_time, :publish_time, :source_type, :source_name, :category_group,
                :title, :link, :summary, :keyword, :duplicate_flag, :normalized_title, :policy_score,
                :frame_category, :importance_score, :language, :notes, :body_text
            )
            """,
            article,
        )
        inserted += cursor.rowcount
    connection.commit()
    return inserted


def fetch_raw_articles(connection: sqlite3.Connection) -> list[dict]:
    return [dict(row) for row in connection.execute("SELECT * FROM raw_articles ORDER BY id")]


def update_raw_articles(connection: sqlite3.Connection, articles: list[dict]) -> None:
    connection.executemany(
        """
        UPDATE raw_articles
        SET collected_time = :collected_time,
            publish_time = :publish_time,
            source_type = :source_type,
            source_name = :source_name,
            category_group = :category_group,
            title = :title,
            link = :link,
            summary = :summary,
            keyword = :keyword,
            duplicate_flag = :duplicate_flag,
            normalized_title = :normalized_title,
            policy_score = :policy_score,
            frame_category = :frame_category,
            importance_score = :importance_score,
            language = :language,
            notes = :notes,
            body_text = :body_text
        WHERE id = :id
        """,
        articles,
    )
    connection.commit()


def replace_processed_articles(connection: sqlite3.Connection, analysis_time: str, articles: list[dict]) -> None:
    connection.execute("DELETE FROM processed_articles")
    connection.executemany(
        """
        INSERT INTO processed_articles (
            analysis_time, rank, raw_article_id, collected_time, publish_time, source_type,
            source_name, category_group, title, link, summary, keyword, duplicate_flag,
            normalized_title, policy_score, frame_category, importance_score, language,
            notes, body_text
        ) VALUES (
            :analysis_time, :rank, :raw_article_id, :collected_time, :publish_time, :source_type,
            :source_name, :category_group, :title, :link, :summary, :keyword, :duplicate_flag,
            :normalized_title, :policy_score, :frame_category, :importance_score, :language,
            :notes, :body_text
        )
        """,
        [
            {
                "analysis_time": analysis_time,
                "rank": article["rank"],
                "raw_article_id": article.get("id"),
                **{column: article.get(column, "") for column in RAW_COLUMNS},
            }
            for article in articles
        ],
    )
    connection.commit()


def fetch_processed_articles(connection: sqlite3.Connection) -> list[dict]:
    return [
        dict(row)
        for row in connection.execute(
            """
            SELECT raw_article_id, analysis_time, rank, collected_time, publish_time, source_type,
                   source_name, category_group, title, link, summary, keyword, duplicate_flag,
                   normalized_title, policy_score, frame_category, importance_score, language,
                   notes, body_text
            FROM processed_articles
            ORDER BY rank
            """
        )
    ]


def replace_briefing_sections(connection: sqlite3.Connection, sections: list[dict]) -> None:
    connection.execute("DELETE FROM briefing_sections")
    connection.executemany(
        """
        INSERT INTO briefing_sections (
            section_order, generated_time, topic_name, section_name, content, supporting_articles, notes
        ) VALUES (
            :section_order, :generated_time, :topic_name, :section_name, :content, :supporting_articles, :notes
        )
        """,
        sections,
    )
    connection.commit()
