# MOLIT Media Monitoring

국토교통부 대변인실용 무료 언론 모니터링 도구입니다. 현재 저장소의 주 실행 경로는 `Python + SQLite + Windows 데스크톱 앱`이며, 보도자료 `HWPX`를 입력받아 검색 규칙 초안을 만들고, 사용자가 이를 보완한 뒤 `D+3` 범위의 관련 기사와 브리핑 초안을 생성합니다.

## 현재 운영 방식

1. 보도자료 `HWPX`를 선택합니다.
2. 앱이 `검색 쿼리` 초안을 자동 추출합니다.
3. 사용자가 `검색 쿼리`, `핵심 키워드`를 수정합니다.
4. `기사 검색`을 실행합니다.
5. `sessions/<session_id>/` 아래에 기사 목록 CSV와 브리핑 Markdown이 저장됩니다.

핵심 원칙:
- 자동 추출은 `초안`입니다.
- 최종 검색 규칙은 사람이 확정합니다.
- 핵심 키워드가 입력된 경우, 제목/요약에 모든 핵심 키워드가 포함된 기사만 최종 수집합니다.

## 폴더 구조

```text
project-media_monitoring/
├─ README.md
├─ AGENTS.md
├─ TASK.md
├─ config.example.json
├─ desktop_main.py
├─ build_windows.bat
├─ packaging/
│  └─ MediaMonitor.spec
├─ inputs/
│  └─ press_releases/
│     └─ README.md
├─ docs/
│  ├─ architecture.md
│  ├─ briefing_template.md
│  ├─ operations.md
│  ├─ python_pipeline.md
│  └─ windows_desktop.md
└─ python_pipeline/
   ├─ __main__.py
   ├─ cli.py
   ├─ config.py
   ├─ db.py
   ├─ collector.py
   ├─ analysis.py
   ├─ briefing.py
   ├─ press_release.py
   ├─ session_outputs.py
   ├─ desktop_app.py
   └─ utils.py
```

## 빠른 시작

### 1. 데스크톱 앱 사용

개발 PC에서는 아래 명령으로 배포본을 만들 수 있습니다.

```powershell
python -m pip install pyinstaller
.\build_windows.bat
```

빌드 후 실행 파일:

```text
dist/MediaMonitor/MediaMonitor.exe
```

배포 시에는 `MediaMonitor.exe` 파일 하나가 아니라 `dist/MediaMonitor/` 폴더 전체를 전달해야 합니다.

### 2. CLI 사용

SQLite 초기화:

```bash
python -m python_pipeline init-db
```

보도자료 기반 세션 생성:

```bash
python -m python_pipeline derive-press-release --press-release inputs/press_releases
```

통합 실행:

```bash
python -m python_pipeline run --press-release inputs/press_releases --analysis-reference-time now
```

## 세션 산출물

각 실행은 `sessions/<session_id>/` 아래에 저장됩니다.

주요 파일:
- `config/queries.auto.json`
- `config/queries.manual.ini`
- `config/config.auto.json`
- `config/config.effective.json`
- `outputs/briefings/D+0_YYYY-MM-DD.md` ~ `D+3_YYYY-MM-DD.md`
- `outputs/references/D+N_YYYY-MM-DD_기사목록.csv`
- `outputs/references/D+N_YYYY-MM-DD_기사목록.md`

기사 목록 기본 컬럼:
- `순번`
- `언론사`
- `기사 제목`
- `보도일시`
- `기사 링크`

## 설정 기본값

기본 설정은 `python_pipeline/defaults.py`에 있고, `config.example.json`은 JSON 오버라이드 예시입니다.

현재 기본 방향:
- 직접 `RSS/sitemap` 소스 유지
- 정책별 고정 Google News 쿼리 제거
- 프레임 분류용 일반 사전만 유지
- 보도자료 세션 실행 시 검색 쿼리와 핵심 키워드는 세션별로 생성 또는 수동 입력

## 관련 문서

- [아키텍처](/c:/Chae/GitHub/project-media_monitoring/docs/architecture.md)
- [운영 가이드](/c:/Chae/GitHub/project-media_monitoring/docs/operations.md)
- [CLI 가이드](/c:/Chae/GitHub/project-media_monitoring/docs/python_pipeline.md)
- [데스크톱 배포 가이드](/c:/Chae/GitHub/project-media_monitoring/docs/windows_desktop.md)
- [브리핑 템플릿](/c:/Chae/GitHub/project-media_monitoring/docs/briefing_template.md)

## 현재 제한

- `HWPX` 중심 입력입니다. `PDF-only` 입력은 아직 미지원입니다.
- 기사 본문은 일부 상위 후보에 대해서만 추가 수집합니다.
- Google News 결과는 경우에 따라 원문 링크가 아니라 래퍼 링크일 수 있습니다.
- 검색 규칙 품질은 보도자료 문장 구조에 영향을 받으므로, 사용자의 최종 수정이 중요합니다.
