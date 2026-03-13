# Windows 데스크톱 배포 가이드

## 목표

Python이 설치되지 않은 Windows PC에서도 폴더형 배포본으로 실행할 수 있게 합니다.

배포 단위:

```text
MediaMonitor/
  MediaMonitor.exe
  _internal/
```

## 사용 흐름

1. `MediaMonitor.exe` 실행
2. `HWPX 선택`
3. `검색 쿼리` 확인 및 수정
4. 필요 시 `핵심 키워드(수동 입력)` 입력
5. `기사 검색`
6. `기사 목록 열기`, `브리핑 열기`, `세션 폴더 열기`

## 현재 UI 용어

- `자동값 복원(쿼리, 키워드)`
- `저장값 불러오기(직전 실행값)`
- `검색 쿼리`
- `핵심 키워드(수동 입력)`
- `기사 검색`
- `기사 목록 열기`
- `브리핑 열기`

## 진행률과 중단

- 실행 중에는 단계별 진행률과 예상 남은 시간이 표시됩니다.
- `중단` 버튼을 누르면 협조적 취소가 걸립니다.
- 취소 후 `기사 검색`을 다시 누르면 처음부터 재실행합니다.

## 빌드

개발 PC에서:

```powershell
python -m pip install pyinstaller
.\build_windows.bat
```

생성 위치:

```text
dist/MediaMonitor/MediaMonitor.exe
```

## 배포 전 정리

지워도 되는 항목:
- `logs/`
- `sessions/`
- `app.log`
- 테스트용 입력 파일

남겨야 하는 항목:
- `MediaMonitor.exe`
- `_internal/`

압축해서 전달할 때는 `MediaMonitor/` 폴더 전체를 zip으로 묶습니다.
