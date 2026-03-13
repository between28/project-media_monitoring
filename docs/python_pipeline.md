# Python 파이프라인

## 개요

`python_pipeline/`은 현재 저장소의 주 실행 엔진입니다.

주요 기능:
- RSS / sitemap / Google News 수집
- SQLite 저장
- 중복 제거
- 관련도 점수화
- 프레임 분류
- 브리핑 생성
- 세션별 기사 목록 출력

## 기본 CLI 명령

DB 초기화:

```bash
python -m python_pipeline init-db
```

보도자료 프로파일 생성:

```bash
python -m python_pipeline derive-press-release --press-release inputs/press_releases
```

통합 실행:

```bash
python -m python_pipeline run --press-release inputs/press_releases --analysis-reference-time now
```

단계별 실행:

```bash
python -m python_pipeline collect --press-release inputs/press_releases --analysis-reference-time now
python -m python_pipeline analyze --press-release inputs/press_releases --analysis-reference-time now
python -m python_pipeline brief --press-release inputs/press_releases --analysis-reference-time now
```

## 세션 방식

`--press-release` 모드에서는 `sessions/<session_id>/`가 생성됩니다.

세션 파일:
- `config/queries.auto.json`
- `config/queries.manual.ini`
- `config/config.auto.json`
- `config/config.effective.json`
- `data/session.sqlite3`
- `outputs/briefings/*.md`
- `outputs/references/*.csv`

## 검색 규칙 구조

현재 보도자료 세션은 두 가지 입력만 씁니다.

### 1. 검색 쿼리

- 보도자료 제목 중심으로 자동 생성됩니다.
- 사용자가 최종 수정합니다.
- 후필터는 `띄어쓰기 기준 AND` 매칭입니다.

### 2. 핵심 키워드

- 수동 입력입니다.
- 비어 있으면 적용하지 않습니다.
- 입력되면 제목/요약에 모든 핵심 키워드가 있어야 최종 수집합니다.

## config.example.json

`config.example.json`은 중립적인 JSON 오버라이드 예시입니다.

용도:
- 보도자료 모드 없이 CLI 테스트
- 기본 수집 한도 변경
- 기준 시점 강제 지정

사용 예:

```bash
python -m python_pipeline run --config config.local.json --analysis-reference-time now
```

## 기본값 정책

`python_pipeline/defaults.py`에는 아래만 남겨 둡니다.

- 직접 RSS / sitemap 소스
- 매체 우선순위
- 프레임 분류용 일반 사전

정책별 고정 쿼리나 샘플 키워드는 기본값에서 제거했습니다.

## 현재 제한

- `HWPX` 중심 입력입니다.
- `PDF-only` 입력은 아직 미지원입니다.
- 일부 기사 본문은 상위 후보에 대해서만 추가 수집합니다.
- 포털 래퍼 링크는 원문 URL로 완전히 치환되지 않을 수 있습니다.
