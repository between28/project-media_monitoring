# Windows 데스크톱 배포 계획

## 목표

Python 설치 없이 Windows PC에서 바로 실행되는 폴더형 배포본을 제공합니다.

- 실행 파일: `MediaMonitor.exe`
- 배포 형태: `dist/MediaMonitor/`
- 입력: `HWPX` 보도자료 파일
- 출력: 세션 폴더, 기사목록 CSV, 브리핑 Markdown

## 사용 흐름

1. `MediaMonitor.exe` 실행
2. `HWPX 선택` 버튼으로 보도자료 첨부
3. 자동 추출된 검색 규칙 확인
4. `Google News 질의`, `일반 키워드`, `구문 키워드`를 필요 시 수정
5. `실행` 클릭
6. 결과 확인

생성 결과:

- `sessions/<session_id>/outputs/references/*_기사목록.csv`
- `sessions/<session_id>/outputs/briefings/*.md`
- `sessions/<session_id>/outputs/latest_reference_articles.csv`
- `sessions/<session_id>/outputs/latest_briefing.md`

## GUI 기능

현재 데스크톱 앱은 아래 기능을 제공합니다.

- 보도자료 `HWPX` 선택
- 자동 추출된 질의/키워드 표시
- 현재 화면 값 기준으로 검색 규칙 전체 교체 저장
- 기사 수집/분석/브리핑 실행
- 최신 CSV, 브리핑, 세션 폴더 열기
- 실행 로그 표시

## 빌드 방법

개발 PC에서만 Python이 필요합니다.

1. `PyInstaller` 설치

```bash
python -m pip install pyinstaller
```

2. 루트에서 빌드

```bash
build_windows.bat
```

3. 생성물 확인

```text
dist/
  MediaMonitor/
    MediaMonitor.exe
```

## 운영 파일 구조

배포본 실행 폴더 기준으로 아래 디렉터리가 생성됩니다.

```text
MediaMonitor/
  MediaMonitor.exe
  sessions/
  logs/
```

세션별 결과는 `sessions/<session_id>/...` 아래에 저장됩니다.

## 현재 제한

- `PDF` 파싱은 아직 지원하지 않습니다.
- 결과 CSV는 현재 표준 컬럼 4개만 출력합니다.
  - `순번`
  - `언론사`
  - `기사 제목`
  - `보도일시`
- GUI는 현재 `analysis_reference_time = now` 기준으로 동작합니다.
- Windows 외 운영체제는 파일 열기 버튼 동작을 보장하지 않습니다.
