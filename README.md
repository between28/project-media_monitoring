# MOLIT Media Monitoring MVP

국토교통부 대변인실용 무료 미디어 모니터링 자동화 MVP입니다. Google Sheets에 연결된 Google Apps Script를 기준으로, RSS 수집부터 중복 제거, 정책 관련도 점수화, 프레임 분류, 중요도 랭킹, 브리핑 초안 생성까지 한 번에 수행하도록 설계했습니다.

기준 정책 이슈:
- `도심 주택공급 확대 및 신속화 방안`
- 발표일: `2026-01-29`

## 폴더 구조

```text
project-media_monitoring/
├─ README.md
├─ AGENTS.md
├─ TASK.md
├─ config.example.json
├─ apps_script/
│  ├─ main.gs
│  ├─ config.gs
│  ├─ rss.gs
│  ├─ body_fetch.gs
│  ├─ dedup.gs
│  ├─ scoring.gs
│  ├─ classify.gs
│  ├─ ranking.gs
│  └─ report.gs
├─ docs/
│  ├─ architecture.md
│  ├─ sheet_schema.md
│  ├─ briefing_template.md
│  ├─ python_pipeline.md
│  └─ operations.md
└─ python_pipeline/
   ├─ __main__.py
   ├─ cli.py
   ├─ defaults.py
   ├─ config.py
   ├─ db.py
   ├─ collector.py
   ├─ analysis.py
   ├─ briefing.py
   └─ utils.py
```

현재 구조는 Apps Script 배포를 단순하게 유지하면서도, 실제 운영 자동화는 `python_pipeline/`으로 옮길 수 있게 이중 경로를 둔 형태입니다. Apps Script는 Google Sheets 중심 운영에 맞고, Python은 SQLite 누적 저장과 재분석, 외부 스케줄러 연동에 더 적합합니다.

## MVP 범위

자동화되는 항목:
- RSS, Google News RSS, 뉴스 sitemap 수집
- 수집 직후 1차 관련도 필터링
- 상위 후보 기사 본문 2차 수집
- `news_raw` 저장
- 링크, 제목, 정규화 제목, 유사 제목 기반 중복 판정
- 정책 키워드 기반 관련도 점수 산정
- 규칙 기반 프레임 분류
- 중요도 점수 계산 및 후보 기사 정렬
- 한국어 브리핑 초안 생성 및 `briefing_output` 기록

사람이 최종 검토해야 하는 항목:
- 실제 브리핑 문안 확정
- 민감 표현 조정
- 빠진 매체 RSS 추가
- 기사 원문 맥락 확인

## 빠른 시작

1. Google Sheet를 하나 만든 뒤 Apps Script를 연결합니다.
2. `apps_script/*.gs` 파일 내용을 Apps Script 프로젝트에 복사합니다.
3. `initializeProject()`를 1회 실행해 기본 시트와 설정 시트를 생성합니다.
4. `resetConfigSourcesSheet()`를 실행해 검증된 기본 RSS/Google News 목록을 `config_sources`에 채웁니다.
5. `config_sources`, `config_keywords`, `config_runtime`을 운영 환경에 맞게 수정합니다.
   현재 기본 `analysis_reference_time`은 `2026-02-01T10:00:00+09:00`으로, `2026-01-29 10:00 KST` 기준 `D+3`입니다.
6. `runCollectionOnly()`로 기사 수집을 먼저 수행합니다.
7. `runAnalysisAndBriefing()`로 누적된 `news_raw` 기준 브리핑을 생성합니다.
8. 필요하면 `runDailyMonitoring()`을 통합 실행용으로 사용합니다.
9. `setupCollectionTriggers()`와 `setupBriefingTrigger()`를 실행해 분리 트리거를 생성합니다.
10. 기존 함수명을 유지하고 싶으면 `setupDailyTrigger()` 또는 `setupSeparatedTriggers()`를 실행해도 됩니다.

상세 절차는 [docs/operations.md](/c:/Chae/GitHub/project-media_monitoring/docs/operations.md)에 정리되어 있습니다.

## 시스템 개요

수집 계층:
- Google News RSS 키워드 질의를 기본값으로 활성화
- 직접 RSS 또는 뉴스 sitemap URL은 `config_sources`에서 추가 가능

처리 계층:
- `news_raw` 누적 로그 보관
- 대표 기사만 남긴 뒤 `news_processed`에 정렬 결과 저장
- `briefing_output`에 섹션별 브리핑 초안 기록

권장 운영 방식:
- `runCollectionOnly()`: 주기적 누적 수집
- `runAnalysisAndBriefing()`: 누적된 `news_raw`를 기준으로 재분석 및 브리핑 재작성
- `runDailyMonitoring()`: 테스트용 통합 실행

Python 중심 운영 방식:
- `python -m python_pipeline init-db`
- `python -m python_pipeline collect --analysis-reference-time now`
- `python -m python_pipeline analyze --analysis-reference-time now`
- `python -m python_pipeline brief --analysis-reference-time now --output-file outputs/latest_briefing.md`
- 또는 한 번에 `python -m python_pipeline run --analysis-reference-time now --output-file outputs/latest_briefing.md`

기본 트리거 시간:
- 수집: `00:15`, `03:15`, `05:00`, `12:15`, `18:15`, `21:15`
- 브리핑: `05:30`

## Python 파이프라인

`python_pipeline/`은 Apps Script와 동일한 규칙 기반 로직을 SQLite 기반으로 옮긴 초안입니다.

- 저장소: `SQLite`
- 실행 방식: `CLI`
- 수집원: `RSS`, `Google News RSS`, `sitemap`
- 출력: DB 적재 + 텍스트 브리핑 파일

기본 명령:

```bash
python -m python_pipeline init-db
python -m python_pipeline collect --analysis-reference-time now
python -m python_pipeline analyze --analysis-reference-time now
python -m python_pipeline brief --analysis-reference-time now --output-file outputs/latest_briefing.md
```

부분 설정 덮어쓰기가 필요하면 루트의 `config.example.json`을 복사해 `--config`로 넘기면 됩니다.

```bash
python -m python_pipeline run --config config.local.json --analysis-reference-time now
```

Python 경로의 장점:
- Google Sheets/Apps Script 편집기 없이 로컬에서 바로 개발·재실행 가능
- `news_raw` 누적 저장 후 특정 기준 시점으로 재분석 가능
- Windows 작업 스케줄러, GitHub Actions, 서버 cron으로 옮기기 쉬움

세부 명령과 구조는 [docs/python_pipeline.md](/c:/Chae/GitHub/project-media_monitoring/docs/python_pipeline.md)를 보면 됩니다.

## 현재 한계

- 기사 본문을 전량 수집하지 않고 RSS 제목/요약 중심으로 1차 판단합니다.
- 일부 상위 후보 기사에 한해 본문 HTML을 추가 수집해 관련도와 프레임 분류를 보강합니다.
- `news_raw`는 피드 원문 전체가 아니라, 1차 관련도 필터를 통과한 기사 로그입니다.
- sitemap 소스는 제목과 발행시각은 안정적으로 들어오지만 요약이 비어 있거나 키워드 수준일 수 있습니다.
- `Google News` 링크는 기본적으로 본문 추가 수집 대상에서 제외합니다.
- Google News RSS는 링크가 원문 직링크가 아닌 경우가 있습니다.
- 프레임 분류와 브리핑 문안은 규칙 기반이므로 표현이 다소 보수적입니다.
- 일부 국내 매체는 RSS 정책이 자주 바뀌므로 초기 설정 검증이 필요합니다.
- `config_runtime.analysis_reference_time`을 채우면 현재 시점 대신 지정 시점을 기준으로 랭킹/브리핑을 재생성할 수 있습니다.

## 향후 로드맵

- 직접 매체 RSS 목록 고도화
- Google Docs 자동 출력
- Python 수집기 및 정교한 유사도 판정 추가
- GitHub Actions 또는 외부 스케줄러 연동
- GDELT 기반 해외 보도 확장
