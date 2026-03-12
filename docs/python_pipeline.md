# Python 파이프라인

## 개요

`python_pipeline/`은 Apps Script 없이도 수집, 저장, 재분석, 브리핑 생성을 한 번에 처리하는 SQLite 기반 실행 경로입니다.

권장 상황:
- Google Sheets/Apps Script 수동 작업이 번거로울 때
- 주기 수집과 아침 브리핑 생성을 외부 스케줄러로 분리하고 싶을 때
- 과거 누적 데이터를 기준으로 재분석하고 싶을 때
- 로컬 개발과 테스트를 더 편하게 하고 싶을 때

## 기본 명령

DB 초기화:

```bash
python -m python_pipeline init-db
```

현재 시점 기준 수집:

```bash
python -m python_pipeline collect --analysis-reference-time now
```

재분석:

```bash
python -m python_pipeline analyze --analysis-reference-time now
```

브리핑 생성:

```bash
python -m python_pipeline brief --analysis-reference-time now --output-file outputs/latest_briefing.md
```

통합 실행:

```bash
python -m python_pipeline run --analysis-reference-time now --output-file outputs/latest_briefing.md
```

## 주요 파일

- `python_pipeline/defaults.py`
  - 기본 소스, 키워드, 런타임 설정
- `python_pipeline/db.py`
  - SQLite 스키마와 입출력
- `python_pipeline/collector.py`
  - RSS, Google News RSS, sitemap 수집
- `python_pipeline/analysis.py`
  - 중복 제거, 정책 점수화, 본문 보강, 프레임 분류, 랭킹
- `python_pipeline/briefing.py`
  - 한국어 브리핑 초안 생성
- `python_pipeline/cli.py`
  - 명령행 실행 진입점

## 설정 덮어쓰기

기본값 일부만 바꾸고 싶으면 JSON 파일을 만들어 `--config`로 넘기면 됩니다.

예:

```bash
python -m python_pipeline run --config config.local.json --analysis-reference-time now
```

기존 `config.example.json`을 복사해 일부 값만 수정해도 됩니다.

## 운영 메모

- 기본 DB 경로는 `data/media_monitoring.sqlite3`입니다.
- `collect`는 누적 적재, `analyze`는 누적 기사 재평가, `brief`는 최신 `processed_articles` 기준 초안 생성입니다.
- `--analysis-reference-time 2026-02-01T10:00:00+09:00`처럼 고정 시점을 줄 수 있습니다.
- `Google News` 링크는 기본적으로 본문 추가 수집 대상에서 제외됩니다.
