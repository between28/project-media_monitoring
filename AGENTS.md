# AGENTS.md

## Project
Free media-monitoring automation pipeline for the Ministry of Land, Infrastructure and Transport (MOLIT) spokesperson office in South Korea.

## Mission
Build a practical, maintainable, free MVP that automatically monitors media coverage related to a MOLIT policy issue and generates a concise one-page ministerial briefing.

Immediate policy topic:
- `도심 주택공급 확대 및 신속화 방안`
- announcement date: `2026-01-29`

The design must later be reusable for other MOLIT policy topics.

---

## Core goals
The system should automate as much of the following as possible:

1. early-morning daily execution
2. news collection
3. storage
4. de-duplication
5. policy relevance scoring
6. reporting-frame classification
7. importance ranking
8. one-page draft briefing generation

The output is for a **government spokesperson office workflow**, not for a consumer news product.

---

## Constraints
- Use **free tools only**
- Do **not** use paid news APIs
- Prefer **Google Apps Script + Google Sheets** for the MVP
- RSS-based collection is the primary collection method
- Google News RSS should be supported
- Human review at the final stage is acceptable
- The system should be simple, robust, readable, and maintainable
- Avoid over-engineering

---

## Preferred MVP architecture
Primary stack:
- Google Sheets
- Google Apps Script
- RSS feeds
- Google News RSS

Future extension points:
- GDELT
- Python
- GitHub Actions

The first working version should focus on Apps Script + Google Sheets because it is easiest to operate for free.

---

## Operational target
Target workflow:

- `05:30` automatic execution
- collect news from RSS sources
- store results in Google Sheets
- remove duplicates
- score policy relevance
- classify articles into reporting frames
- rank important articles
- generate a one-page Korean draft briefing
- export or write the result into Google Docs or a structured text output for review

---

## Coverage requirements
The system should try to capture:
- same-day morning newspaper coverage
- Korean media
- foreign media where feasible
- general daily newspapers
- economic / business newspapers
- broadcasters
- wire services
- major online outlets
- policy-relevant sector outlets

Realistic target:
- very high practical coverage, not perfect recall

---

## Korean media source categories
At minimum, support configurable feed lists for these categories.

### 1. National general newspapers
- 조선일보
- 중앙일보
- 동아일보
- 한겨레
- 경향신문
- 서울신문
- 세계일보

### 2. Economic / business media
- 매일경제
- 한국경제
- 서울경제
- 이데일리
- 아시아경제
- 머니투데이

### 3. Wire services
- 연합뉴스
- 뉴스1
- 뉴시스

### 4. Broadcasters
- KBS
- MBC
- SBS
- YTN
- JTBC
- Channel A if available

### 5. Major online media
- 노컷뉴스
- 헤럴드경제
- 파이낸셜뉴스
- 오마이뉴스
- 프레시안
- 데일리안

### 6. Sector-specific / policy-relevant outlets
- 국토일보
- 건설경제
- housing / real estate / construction / infrastructure outlets with RSS if available

---

## Policy-topic example keywords
The system must support configurable keyword sets by policy topic.

Initial keyword examples:
- 도심
- 주택
- 공급
- 신속화
- 국토부
- 용산
- 태릉
- 과천
- 1.29 공급대책
- 용산 국제업무지구 공급
- 태릉CC 공급
- 과천 경마장 공급

---

## Google News RSS support
Support keyword-based Google News RSS queries for topic expansion and broader recall.

Examples:
- `도심 주택공급 확대`
- `도심 주택공급 신속화`
- `1.29 공급대책`
- `국토부 주택공급 확대`
- `용산 국제업무지구 공급`
- `태릉CC 공급`
- `과천 경마장 공급`

---

## Required data model
Use Google Sheets as the operational datastore for the MVP.

Suggested raw sheet name:
- `news_raw`

Suggested columns:
- `collected_time`
- `publish_time`
- `source_type`
- `source_name`
- `category_group`
- `title`
- `link`
- `summary`
- `keyword`
- `duplicate_flag`
- `normalized_title`
- `policy_score`
- `frame_category`
- `importance_score`
- `language`
- `notes`

You may add processed sheets if useful, such as:
- `news_processed`
- `briefing_output`
- `config_keywords`
- ``

---

## Core algorithm requirements

### A. De-duplication
This is critical.

Implement practical de-duplication logic appropriate for news monitoring:
- exact link duplicate removal
- exact title duplicate removal
- normalized title matching
- fuzzy title similarity for redistributed wire copy and syndicated stories
- configurable threshold
- preserve representative article and, if possible, source diversity metadata

### B. Policy relevance scoring
Implement a configurable keyword-based scoring system first.

Scoring should consider:
- title matches
- summary matches
- optional source boosts for high-priority outlets
- optional phrase matches for policy-specific terms

The system should output:
- `policy_score`
- a thresholded set of high-relevance candidate articles for briefing generation

### C. Frame classification
Implement a first-pass rule-based classifier for:
- `정책 설명`
- `긍정 평가`
- `비판 / 우려`
- `정치 / 기관 이슈`

Use configurable keyword dictionaries and simple heuristics.

### D. Importance ranking
Implement a simple but practical ranking model using factors such as:
- policy relevance score
- major outlet priority
- freshness
- evaluative / critical language
- repeated narrative frequency across sources
- source diversity
- whether the article appears to be an editorial / opinion / high-impact item, if detectable

This ranking should determine which items are used in the briefing draft.

---

## Ministerial briefing format
The output briefing must be concise and structured in Korean.

Required sections:
1. `총평`
   - 3–4 sentences on overall tone and dominant narratives
2. `주요 보도 내용`
   - grouped by main themes
3. `주요 논점`
   - 3–5 major issues or frames
4. `영향력 기사`
   - major or agenda-setting items if identifiable
5. `대응 참고`
   - possible spokesperson response points

---

## Reporting philosophy
Prioritize:
- narrative extraction
- risk signals
- implementation concerns
- institutional conflict
- media tone

Do **not** simply produce article-by-article summaries.

Distinguish between:
- policy explanation
- positive evaluation
- criticism / concerns
- political / institutional issues

For ministerial reporting, frame extraction matters more than raw article count.

---

## MVP drafting approach
Do not rely on a paid LLM API for the MVP.

The first version may use:
- deterministic extraction
- template-based drafting
- repeated theme detection
- ranked article selection
- frame counts
- keyword clustering
- source diversity checks

The generated draft should still read like a concise government morning briefing.

---

## Deliverables
Generate a working MVP with code and documentation.

Preferred deliverables:

- `README.md`
- `config.example.json`
- `apps_script/main.gs`
- `apps_script/config.gs`
- `apps_script/rss.gs`
- `apps_script/dedup.gs`
- `apps_script/classify.gs`
- `apps_script/report.gs`
- `docs/sheet_schema.md`
- `docs/briefing_template.md`
- `docs/operations.md`

If you believe a slightly different structure is better, propose it first and explain the reason briefly.

---

## Coding expectations
- Write clean, maintainable code
- Add comments where they genuinely help
- Prefer simple logic over abstract architecture
- Assume the operator is not an advanced developer
- The Apps Script code must be copy-paste deployable into a Google Apps Script project attached to a Google Sheet
- Include setup instructions
- Include trigger setup instructions for daily execution at `05:30`
- Include practical notes on quotas and limitations
- Include clear TODO markers for future extension

---

## Documentation requirements
Use Korean where appropriate in operational documents and briefing templates.
Code comments may be in English or Korean, but should remain clear and readable.

Documentation should explain:
- how to configure feeds
- how to configure keywords
- how the de-duplication works
- how the scoring works
- how the frame classifier works
- how to run the script manually
- how to set the daily trigger
- what the current limitations are

---

## Expected workflow from you
When executing this task, proceed in this order:

1. Propose the folder structure
2. Write a short architecture note explaining:
   - why Apps Script + Google Sheets is the MVP
   - what is automated
   - what remains for human review
   - how later expansion to Python / GitHub Actions / GDELT could work
3. Generate the actual MVP files
4. Make reasonable assumptions where needed and proceed without blocking on uncertainty

---

## Non-goals for the MVP
Do not spend time on:
- UI polish
- advanced NLP
- multi-user permissions systems
- paid API integration
- perfect article-body extraction
- enterprise-scale architecture

---

## Quality bar
The result should be:
- practical
- readable
- operationally plausible
- easy to extend
- suitable for a spokesperson office morning workflow

This is a real working prototype task, not just an advisory exercise.

Do not stop at high-level advice.
Actually generate the folder structure, code, and docs.