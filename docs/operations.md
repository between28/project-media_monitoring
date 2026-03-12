# 운영 가이드

## 1. 배포 방법

1. Google Sheet를 새로 생성합니다.
2. `확장 프로그램 > Apps Script`로 이동합니다.
3. 기본 `Code.gs` 내용을 지우고, 이 저장소의 `apps_script/*.gs` 내용을 파일별로 복사합니다.
4. Apps Script 프로젝트의 시간대를 `Asia/Seoul`로 설정합니다.
5. `initializeProject()`를 실행합니다.

`initializeProject()`를 실행하면 다음 시트가 자동 생성됩니다.
- `news_raw`
- `news_processed`
- `briefing_output`
- `config_sources`
- `config_keywords`
- `config_runtime`

## 2. Google Sheets 연결 방식

이 MVP는 "Google Sheet에 연결된(bound) Apps Script"를 전제로 합니다. 따라서 별도 Spreadsheet ID 입력 없이 `SpreadsheetApp.getActiveSpreadsheet()`를 사용합니다. 시트에 붙여넣기만 하면 바로 운영할 수 있는 것이 장점입니다.

Python 중심 운영을 원하면 Google Sheets 없이도 `python_pipeline/`만으로 수집, 저장, 재분석, 브리핑 생성이 가능합니다. 이 경우 저장소는 SQLite로 바뀌고, Google Sheets는 선택적 검토 도구가 됩니다.

## 3. RSS 소스 설정

`config_sources`에서 다음 항목을 관리합니다.

- `enabled`
- `source_name`
- `source_type`
- `category_group`
- `feed_url`
- `keyword`
- `notes`

운영 규칙:
- `source_type = google_news`이고 `feed_url`이 비어 있으면 `keyword`로 Google News RSS URL을 자동 생성합니다.
- `source_type = rss`이면 `feed_url`에 실제 RSS 주소를 넣어야 합니다.
- `source_type = sitemap`이면 `feed_url`에 뉴스 sitemap URL을 넣고, 제목/발행시각 중심으로 수집합니다.
- 실제 운영 설정의 기준은 `config_sources`, `config_keywords` 시트이며 로컬 JSON 설정 파일은 사용하지 않습니다.
- 기본 시트에는 Google News 키워드 질의가 활성화되어 있고, 직접 RSS 또는 sitemap 행 일부는 상태 확인에 따라 비활성일 수 있습니다.
- 수집 직후 1차 관련도 필터와 분석 기간 필터를 적용하므로, `news_raw`에도 정책과 무관한 일반 기사나 기준 기간 밖 기사는 원칙적으로 남기지 않습니다.
- 이후 대표 기사 중 점수가 어느 정도 나온 소수 기사에 한해 본문 HTML을 추가 수집합니다.

## 4. 키워드 설정

`config_keywords`에서 점수와 프레임 규칙을 조정합니다.

주요 `bucket`:
- `topic`: 일반 정책 키워드
- `phrase`: 정책 특화 구문
- `frame_policy`: 정책 설명 프레임
- `frame_positive`: 긍정 평가 프레임
- `frame_critical`: 비판/우려 프레임
- `frame_political`: 정치/기관 이슈 프레임
- `negative_signal`: 위험 신호 단어
- `opinion_signal`: 사설/칼럼 등 영향력 신호

가중치 조정 예:
- 핵심 정책어는 `weight = 2`
- 특정 구문은 `weight = 4`
- 강한 비판 신호는 `weight = 2~3`

현재 기본 로직은 단일 일반어 1개만 제목에 잡힌 경우를 고관련 기사로 보지 않도록 설계되어 있습니다. 기본적으로 `policy_score >= 8`이면서, `phrase`가 1개 이상 있거나 전체 키워드 hit가 2개 이상이어야 `news_processed`에 남습니다.
또한 수집 단계에서는 `phrase` 1개가 있거나, 전체 키워드 hit 2개 이상이면서 `공급/신속화/국토부/용산/태릉/과천` 중 하나를 포함한 기사만 `news_raw`에 남깁니다.
본문 보강 단계에서는 대표 기사 중 선별 점수가 일정 기준 이상인 소수 기사만 추가 fetch합니다. 기본적으로 `Google News` 링크는 제외합니다.

## 5. 기준 시점 설정

`config_runtime` 시트의 `analysis_reference_time` 값을 비워두면 현재 실행 시점을 기준으로 분석합니다.

예:
- 비움: 현재 시점 기준
- `2026-03-12T05:30:00+09:00`: 해당 시점을 기준으로 `36시간` lookback, freshness, 브리핑 생성 시각을 계산

현재 기본값:
- `2026-02-01T10:00:00+09:00`
- 의미: `2026-01-29 10:00 KST` 기준 `D+3`

권장 사용 방식:
- 새 기사만 누적 수집하려면 `runCollectionOnly()`
- 이미 쌓인 `news_raw`를 다시 평가하고 브리핑을 만들려면 `runAnalysisAndBriefing()` 또는 `runAnalysisOnly()`
- 통합 실행이 필요할 때만 `runDailyMonitoring()`을 사용합니다

## 6. 수동 실행

순차 실행:

1. `initializeProject()`
2. `resetConfigSourcesSheet()`
3. `runCollectionOnly()`
4. `runAnalysisAndBriefing()`

개별 점검용 함수:
- `clearMonitoringData()`
- `collectRSS()`
- `fetchArticleBodies()`
- `resetConfigKeywordsSheet()`
- `resetConfigRuntimeSheet()`
- `resetConfigSourcesSheet()`
- `runCollectionOnly()`
- `runAnalysisAndBriefing()`
- `runAnalysisOnly()`
- `deduplicateNews()`
- `scorePolicyRelevance()`
- `classifyFrames()`
- `rankArticles()`
- `generateBriefing()`

## 6-1. Python 수동 실행

SQLite 초기화:

```bash
python -m python_pipeline init-db
```

현재 시점 기준 수집:

```bash
python -m python_pipeline collect --analysis-reference-time now
```

누적된 기사 재분석:

```bash
python -m python_pipeline analyze --analysis-reference-time now
```

브리핑 파일 생성:

```bash
python -m python_pipeline brief --analysis-reference-time now --output-file outputs/latest_briefing.md
```

통합 실행:

```bash
python -m python_pipeline run --analysis-reference-time now --output-file outputs/latest_briefing.md
```

보도자료 입력 기반 실행:

```bash
python -m python_pipeline derive-press-release --press-release inputs/press_releases --output-dir outputs/press_release
python -m python_pipeline run --press-release inputs/press_releases --analysis-reference-time now
```

운영 팁:
- `--analysis-reference-time now`를 주면 실행 시점 기준으로 평가합니다.
- `--analysis-reference-time 2026-02-01T10:00:00+09:00`처럼 주면 특정 시점 기준 재분석이 가능합니다.
- `--config config.local.json`으로 일부 설정만 덮어쓸 수 있습니다.
- `config.example.json`은 Python 경로의 부분 오버라이드 예시로도 사용할 수 있습니다.
- `--press-release`를 주면 기본 주제 대신 보도자료에서 추출한 키워드와 Google News 질의를 사용합니다.
- `--press-release` 실행 후에는 `sessions/<session_id>/outputs/briefings/`와 `sessions/<session_id>/outputs/references/` 아래에 일자별 결과물이 생성됩니다.
- 세션별 수동 쿼리 보완은 `sessions/<session_id>/config/queries.manual.ini`에서 관리합니다.
- 자동 추출본은 `queries.auto.json`, 실제 적용본은 `config.effective.json`으로 별도 보관됩니다.
- 참고자료 기사표 기본 컬럼은 `순번`, `언론사`, `기사 제목`, `보도일시`입니다.
- `queries.manual.ini`는 한 줄에 하나씩 입력합니다. 쉼표로 여러 값을 한 줄에 적지 않습니다.

## 7. 트리거 설정

분리 운영 권장:

1. Apps Script에서 `setupCollectionTriggers()`를 실행합니다.
2. 이어서 `setupBriefingTrigger()`를 실행합니다.
3. 기존 `runDailyMonitoring` 트리거가 있으면 함께 정리됩니다.

기본 생성 시간:
- `runCollectionOnly()`: `00:15`, `03:15`, `05:00`, `12:15`, `18:15`, `21:15`
- `runAnalysisAndBriefing()`: `05:30`

주의:
- Apps Script 시간 기반 트리거는 정확히 `05:30:00`에 실행된다고 보장되지는 않습니다.
- 실제 실행 시각은 수 분 범위에서 흔들릴 수 있습니다.

권장 운영:
- 수집은 `runCollectionOnly()`를 하루 여러 차례 실행해 누적합니다.
- 아침 보고는 `runAnalysisAndBriefing()`를 `05:30` 전후에 실행합니다.
- `setupSeparatedTriggers()`는 위 두 트리거를 한 번에 설치하는 편의 함수입니다.
- `setupDailyTrigger()`는 호환용 래퍼로 `setupSeparatedTriggers()`를 호출합니다.

## 8. Apps Script 쿼터와 현실적 볼륨

MVP 기준 권장 운영 범위:
- 활성 피드 수: 10~30개
- 피드당 수집 상한: 10~20건
- 1회 수집량: 대략 100~300건

주의할 쿼터:
- `UrlFetchApp` 호출 횟수
- 스프레드시트 읽기/쓰기 횟수
- 시간 기반 트리거 총 실행 시간

현재 구현은 단순성과 유지보수를 우선해 시트 전체를 다시 읽고 쓰는 방식입니다. 초기 운영에는 충분하지만, 피드 수가 크게 늘어나면 Python 외부 수집기로 분리하는 것이 더 적합합니다.

## 9. 현재 한계

- 기사 본문 전체를 읽지 않습니다.
- Google News RSS는 링크 구조가 바뀔 수 있습니다.
- 직접 RSS URL은 매체 정책 변경에 따라 수시 점검이 필요합니다.
- 프레임 분류는 규칙 기반이므로 완전하지 않습니다.
- 브리핑 초안은 최종 배포본이 아니라 검토용 초안입니다.
- Python 파이프라인도 기본적으로 Apps Script와 같은 규칙을 따르므로 고급 NLP나 완전한 기사 본문 파싱을 제공하지는 않습니다.

## 10. 운영 팁

- `news_processed` 상위 기사만 보지 말고 `news_raw`의 `duplicate_flag`, `policy_score`, `frame_category`를 함께 확인합니다.
- 특정 매체가 자주 누락되면 `config_sources`에 직접 RSS를 추가합니다.
- 정책 주제가 바뀌면 `config_keywords`만 먼저 교체해도 기본 구조는 재사용할 수 있습니다.
- Python 중심 운영에서는 `data/media_monitoring.sqlite3`를 정기 백업하면 과거 시점 재분석이 쉬워집니다.
