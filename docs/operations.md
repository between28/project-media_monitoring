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

## 2. Google Sheets 연결 방식

이 MVP는 "Google Sheet에 연결된(bound) Apps Script"를 전제로 합니다. 따라서 별도 Spreadsheet ID 입력 없이 `SpreadsheetApp.getActiveSpreadsheet()`를 사용합니다. 시트에 붙여넣기만 하면 바로 운영할 수 있는 것이 장점입니다.

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
- 기본 시트에는 Google News 키워드 질의가 활성화되어 있고, 직접 RSS 행 일부는 placeholder로 비활성 상태입니다.

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

## 5. 수동 실행

순차 실행:

1. `initializeProject()`
2. `resetConfigSourcesSheet()`
3. `runDailyMonitoring()`

개별 점검용 함수:
- `collectRSS()`
- `resetConfigSourcesSheet()`
- `deduplicateNews()`
- `scorePolicyRelevance()`
- `classifyFrames()`
- `rankArticles()`
- `generateBriefing()`

## 6. 매일 05:30 트리거 설정

1. Apps Script에서 `setupDailyTrigger()`를 실행합니다.
2. 기존 `runDailyMonitoring` 트리거가 있으면 삭제 후 다시 생성합니다.
3. 생성되는 트리거는 `매일`, `05시`, `nearMinute(30)` 기준입니다.

주의:
- Apps Script 시간 기반 트리거는 정확히 `05:30:00`에 실행된다고 보장되지는 않습니다.
- 실제 실행 시각은 수 분 범위에서 흔들릴 수 있습니다.

## 7. Apps Script 쿼터와 현실적 볼륨

MVP 기준 권장 운영 범위:
- 활성 피드 수: 10~30개
- 피드당 수집 상한: 10~20건
- 1회 수집량: 대략 100~300건

주의할 쿼터:
- `UrlFetchApp` 호출 횟수
- 스프레드시트 읽기/쓰기 횟수
- 시간 기반 트리거 총 실행 시간

현재 구현은 단순성과 유지보수를 우선해 시트 전체를 다시 읽고 쓰는 방식입니다. 초기 운영에는 충분하지만, 피드 수가 크게 늘어나면 Python 외부 수집기로 분리하는 것이 더 적합합니다.

## 8. 현재 한계

- 기사 본문 전체를 읽지 않습니다.
- Google News RSS는 링크 구조가 바뀔 수 있습니다.
- 직접 RSS URL은 매체 정책 변경에 따라 수시 점검이 필요합니다.
- 프레임 분류는 규칙 기반이므로 완전하지 않습니다.
- 브리핑 초안은 최종 배포본이 아니라 검토용 초안입니다.

## 9. 운영 팁

- `news_processed` 상위 기사만 보지 말고 `news_raw`의 `duplicate_flag`, `policy_score`, `frame_category`를 함께 확인합니다.
- 특정 매체가 자주 누락되면 `config_sources`에 직접 RSS를 추가합니다.
- 정책 주제가 바뀌면 `config_keywords`만 먼저 교체해도 기본 구조는 재사용할 수 있습니다.
