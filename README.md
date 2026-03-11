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
│  ├─ dedup.gs
│  ├─ scoring.gs
│  ├─ classify.gs
│  ├─ ranking.gs
│  └─ report.gs
├─ docs/
│  ├─ architecture.md
│  ├─ sheet_schema.md
│  ├─ briefing_template.md
│  └─ operations.md
└─ future_python/
   └─ placeholder.md
```

현재 구조는 Apps Script 배포를 단순하게 유지하기 위해 `apps_script/`를 평평한 구조로 두고, 문서와 향후 Python 확장 공간을 분리했습니다. Apps Script에 그대로 복사하기 쉽고, 이후 `future_python/`에 수집기나 후처리기를 옮겨도 충돌이 적습니다.

## MVP 범위

자동화되는 항목:
- RSS, Google News RSS, 뉴스 sitemap 수집
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
5. `config_sources`, `config_keywords`를 운영 환경에 맞게 수정합니다.
6. `runDailyMonitoring()`을 수동 실행해 첫 결과를 확인합니다.
7. `setupDailyTrigger()`를 실행해 일일 자동 트리거를 생성합니다.

상세 절차는 [docs/operations.md](/c:/Chae/GitHub/project-media_monitoring/docs/operations.md)에 정리되어 있습니다.

## 시스템 개요

수집 계층:
- Google News RSS 키워드 질의를 기본값으로 활성화
- 직접 RSS 또는 뉴스 sitemap URL은 `config_sources`에서 추가 가능

처리 계층:
- `news_raw` 전체 로그 보관
- 대표 기사만 남긴 뒤 `news_processed`에 정렬 결과 저장
- `briefing_output`에 섹션별 브리핑 초안 기록

## 현재 한계

- 기사 본문 전체를 읽지 않고 RSS 제목/요약 중심으로 판단합니다.
- sitemap 소스는 제목과 발행시각은 안정적으로 들어오지만 요약이 비어 있거나 키워드 수준일 수 있습니다.
- Google News RSS는 링크가 원문 직링크가 아닌 경우가 있습니다.
- 프레임 분류와 브리핑 문안은 규칙 기반이므로 표현이 다소 보수적입니다.
- 일부 국내 매체는 RSS 정책이 자주 바뀌므로 초기 설정 검증이 필요합니다.

## 향후 로드맵

- 직접 매체 RSS 목록 고도화
- Google Docs 자동 출력
- Python 수집기 및 정교한 유사도 판정 추가
- GitHub Actions 또는 외부 스케줄러 연동
- GDELT 기반 해외 보도 확장
