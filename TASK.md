# TASK.md

## Task
Build the first working MVP of the MOLIT media-monitoring automation system described in `AGENTS.md`.

The goal of this task is to create a **functional prototype** that can:

1. collect news from RSS feeds
2. store results in Google Sheets
3. remove duplicates
4. score policy relevance
5. classify articles into reporting frames
6. rank important articles
7. generate a one-page draft briefing

The MVP should run inside **Google Apps Script attached to a Google Sheet**.

---

# Step 1 — Project folder structure

First propose a project folder structure suitable for:

- Apps Script code
- documentation
- configuration files
- future Python expansion

Suggested starting point:


project-media_monitoring/
│
├─ README.md
├─ AGENTS.md
├─ TASK.md
├─ config.example.json
│
├─ apps_script/
│ ├─ main.gs
│ ├─ config.gs
│ ├─ rss.gs
│ ├─ dedup.gs
│ ├─ classify.gs
│ ├─ scoring.gs
│ ├─ ranking.gs
│ ├─ report.gs
│
├─ docs/
│ ├─ architecture.md
│ ├─ sheet_schema.md
│ ├─ briefing_template.md
│ ├─ operations.md
│
└─ future_python/
└─ placeholder.md


If you believe a better structure exists, propose and explain it briefly.

---

# Step 2 — Architecture note

Create `docs/architecture.md`.

Explain:

- why **Google Apps Script + Google Sheets** is the MVP architecture
- what parts of the pipeline are automated
- what parts still require human review
- how the system can later expand to:

  - Python
  - GitHub Actions
  - GDELT integration

Keep the architecture explanation practical and concise.

---

# Step 3 — Google Sheet schema

Create `docs/sheet_schema.md`.

Define the schema for the Google Sheet.

Required sheet:

`news_raw`

Suggested columns:


collected_time
publish_time
source_type
source_name
category_group
title
link
summary
keyword
duplicate_flag
normalized_title
policy_score
frame_category
importance_score
language
notes


Optional additional sheets:



config_keywords
news_processed
briefing_output


Explain the role of each sheet.

---

# Step 4 — RSS collection module

Create:


apps_script/rss.gs


Responsibilities:

- fetch RSS feeds
- parse XML
- extract:
  - title
  - link
  - pubDate
  - summary
- write rows into `news_raw`

Include support for:

- multiple RSS sources
- Google News RSS keyword feeds
- source tagging

Add comments explaining the code.

---

# Step 5 — De-duplication module

Create:


apps_script/dedup.gs


Implement:

1. duplicate by link
2. duplicate by exact title
3. duplicate by normalized title

Add a helper function:


normalizeTitle()


Which removes:

- punctuation
- redundant whitespace
- brackets
- common suffix patterns

The function should help identify syndicated wire articles.

---

# Step 6 — Policy scoring module

Create:


apps_script/scoring.gs


Implement a keyword scoring system.

Keywords example:


도심
주택
공급
신속화
국토부
용산
태릉
과천


Rules:

- title match = higher weight
- summary match = lower weight
- configurable keyword list

Output:


policy_score


---

# Step 7 — Frame classification

Create:


apps_script/classify.gs


Implement rule-based classification:

Frame categories:


정책 설명
긍정 평가
비판 / 우려
정치 / 기관 이슈
기타


Use keyword dictionaries for classification.

---

# Step 8 — Importance ranking

Create:


apps_script/ranking.gs


Compute:


importance_score


Factors:

- policy_score
- major outlet boost
- freshness
- critical language

Return ranked candidate articles for briefing.

---

# Step 9 — Briefing generation

Create:


apps_script/report.gs


Generate a Korean draft briefing with sections:


총평
주요 보도 내용
주요 논점
영향력 기사
대응 참고


Use template logic:

- top-ranked articles
- frame counts
- repeated keywords

The output should be concise and structured.

---

# Step 10 — Main workflow

Create:


apps_script/main.gs


Main pipeline:


collectRSS()
↓
deduplicateNews()
↓
scorePolicyRelevance()
↓
classifyFrames()
↓
rankArticles()
↓
generateBriefing()


---

# Step 11 — Operations documentation

Create:


docs/operations.md


Explain:

- how to deploy Apps Script
- how to connect it to Google Sheets
- how to configure RSS sources
- how to configure keywords
- how to run the script manually
- how to set the **daily trigger at 05:30**

Also document:

- Apps Script quota limits
- realistic data volume
- known limitations

---

# Step 12 — README

Create `README.md`.

It should explain:

- project purpose
- quick setup guide
- system overview
- current MVP scope
- future roadmap

---

# Coding rules

- Write clean and readable code
- Comment important logic
- Avoid unnecessary abstraction
- Assume the operator is not a professional developer
- Focus on reliability

---

# Expected outcome

After completing this task, the project should contain:

- a working Apps Script codebase
- documentation
- a reproducible setup

The system should be able to generate a **draft ministerial media briefing** from RSS-collected news.

Proceed step-by-step and generate all files required for the MVP.