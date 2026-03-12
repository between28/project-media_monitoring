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

## 보도자료 기반 자동 키워드 모드

`HWPX` 보도자료를 넣으면 제목, 배포일, 핵심 구문, 일반 키워드, Google News 질의를 자동 추출할 수 있습니다.

입력 위치 예시:
- `inputs/press_releases/`

프로파일 추출:

```bash
python -m python_pipeline derive-press-release --press-release inputs/press_releases --output-dir outputs/press_release
```

생성 파일:
- `outputs/press_release/press_release_profile.json`
- `outputs/press_release/press_release_config.json`
- `outputs/press_release/press_release_profile.md`

바로 모니터링 실행:

```bash
python -m python_pipeline run --press-release inputs/press_releases --analysis-reference-time now
```

운영 메모:
- `HWPX`를 우선 입력으로 사용합니다.
- 동일 문서의 `PDF`는 보조 비교용으로만 두는 편이 좋습니다.
- 현재는 `PDF-only` 입력은 지원하지 않습니다.

## 세션 산출물

`--press-release` 모드로 실행하면 `sessions/<session_id>/` 아래에 보도자료별 세션 폴더가 생성됩니다.

주요 산출물:
- `inputs/`
  - 원본 `HWPX`와 가능한 경우 같은 이름의 `PDF`를 함께 복사해 보관
- `config/queries.auto.json`
  - 보도자료에서 자동 추출된 구문, 키워드, Google News 질의
- `config/queries.manual.ini`
  - 세션별 수동 보완 파일
  - `#` 주석과 함께 사람이 직접 읽고 수정할 수 있는 형식
  - `add`, `disable`, `replace` 항목으로 자동 질의를 보정

예시:

```ini
[google_queries]
# 한 줄에 하나씩 입력합니다. 쉼표로 여러 개를 한 줄에 적지 않습니다.
add =
    동북선 경전철 개통
    서울 동북권 경전철

disable =
    동북선 왕십리역

replace =
```

입력 규칙:
- 각 값은 `add =` 아래에 `공백 4칸 + 문구` 형태로 한 줄씩 넣습니다.
- `,`로 여러 값을 한 줄에 나열하지 않습니다.
- 띄어쓰기는 검색에 쓰고 싶은 표현 그대로 적습니다.
- `disable`은 자동 추출된 값과 최대한 같은 문구로 적는 편이 안전합니다.
- `replace`를 쓰면 자동 추출값 대신 그 목록을 기본값으로 사용합니다.
- `config/config.auto.json`
  - 자동 추출 결과만 반영한 실행 설정
- `config/config.effective.json`
  - 수동 보완까지 반영한 실제 실행 설정
- `data/session.sqlite3`
  - 해당 보도자료 세션의 누적 기사 DB
- `config/press_release_profile.json`
  - 보도자료에서 추출한 제목, 배포일, 구문/키워드/질의
- `outputs/briefings/D+0_YYYY-MM-DD.md` ~ `outputs/briefings/D+3_YYYY-MM-DD.md`
  - 배포일 기준 일자별 언론동향 초안
- `outputs/references/D+0_YYYY-MM-DD_기사목록.csv`
- `outputs/references/D+0_YYYY-MM-DD_기사목록.md`
  - 참고자료용 기사 목록

참고자료 기사표 기본 컬럼:
- `순번`
- `언론사`
- `기사 제목`
- `보도일시`

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
