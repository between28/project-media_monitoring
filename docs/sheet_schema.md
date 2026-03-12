# Google Sheet 스키마

MVP는 Google Sheets를 운영 저장소로 사용합니다. 기본 시트는 `news_raw`이고, 운영 편의성을 위해 설정/처리/출력 시트를 함께 둡니다.

## 1. `news_raw`

수집 직후 1차 관련도 필터와 분석 기간 필터를 통과한 기사 로그입니다. 중복 기사도 일단 저장한 뒤 후처리 결과를 같은 행에 기록합니다.

| 컬럼 | 설명 |
| --- | --- |
| `collected_time` | 수집 시각 |
| `publish_time` | RSS가 제공한 기사 발행 시각 |
| `source_type` | `rss`, `google_news` 등 입력원 유형 |
| `source_name` | 매체명 또는 질의명 |
| `category_group` | 종합지, 경제지, 통신, 방송, 정책키워드 등 |
| `title` | 기사 제목 |
| `link` | 기사 링크 |
| `summary` | RSS 요약 또는 설명 |
| `keyword` | 관련도 산정 시 잡힌 키워드 목록 |
| `duplicate_flag` | 대표기사 여부 또는 중복 사유 |
| `normalized_title` | 중복 판정용 정규화 제목 |
| `policy_score` | 정책 관련도 점수 |
| `frame_category` | 프레임 분류 결과 |
| `importance_score` | 중요도 점수 |
| `language` | `ko`, `en`, `unknown` 등 |
| `notes` | 쿼리, 중복 메모, 군집 메모 등 보조 정보 |
| `body_text` | 선택적으로 추가 수집한 기사 본문 텍스트 |

## 2. `config_sources`

수집 소스 설정 시트입니다.

권장 컬럼:

| 컬럼 | 설명 |
| --- | --- |
| `enabled` | `TRUE`면 수집 대상 |
| `source_name` | 표시 이름 |
| `source_type` | `rss`, `google_news`, `sitemap` |
| `category_group` | 매체군 구분 |
| `feed_url` | 직접 RSS 또는 뉴스 sitemap URL. Google News 키워드형이면 비워둘 수 있음 |
| `keyword` | Google News RSS 질의어 또는 운영 메모용 키워드 |
| `notes` | 운영 메모 |

기본값은 Google News 키워드 질의를 활성화하고, 일부 직접 RSS/sitemap 행은 상태 검증 결과에 따라 비활성으로 둘 수 있습니다.

## 3. `config_keywords`

점수화 및 프레임 분류 규칙 시트입니다.

| 컬럼 | 설명 |
| --- | --- |
| `enabled` | `TRUE`면 규칙 사용 |
| `bucket` | 규칙 그룹 |
| `keyword` | 키워드 또는 구문 |
| `weight` | 가중치 |
| `notes` | 운영 메모 |

주요 `bucket` 예:
- `topic`
- `phrase`
- `frame_policy`
- `frame_positive`
- `frame_critical`
- `frame_political`
- `negative_signal`
- `opinion_signal`

## 4. `config_runtime`

운영 시점 설정 시트입니다.

| 컬럼 | 설명 |
| --- | --- |
| `key` | 설정 키 |
| `value` | 설정 값 |
| `notes` | 운영 메모 |

현재 지원 키:
- `analysis_reference_time`
  - 비우면 현재 실행 시점 기준
  - 값을 넣으면 해당 시점을 기준으로 `lookback`, `freshness`, `briefing_output.generated_time` 계산

## 5. `news_processed`

중복 제거 후 브리핑 후보로 추린 작업 시트입니다. `policy_score`와 `importance_score` 기준으로 정렬하며, 대표 기사만 남깁니다.

추가 컬럼:

| 컬럼 | 설명 |
| --- | --- |
| `rank` | 중요도 순위 |

나머지 컬럼은 `news_raw`와 동일합니다.

## 6. `briefing_output`

생성된 브리핑 결과를 섹션별 행으로 저장합니다.

| 컬럼 | 설명 |
| --- | --- |
| `generated_time` | 브리핑 생성 시각 |
| `topic_name` | 정책 주제명 |
| `section_name` | `총평`, `주요 보도 내용`, `주요 논점`, `영향력 기사`, `대응 참고`, `전체본` |
| `content` | 섹션별 내용 |
| `supporting_articles` | 근거 기사 요약 목록 |
| `notes` | 프레임 집계 등 메모 |

## 운영 원칙

- `news_raw`는 로그 보관
- `news_processed`는 매일 브리핑 후보 정렬 결과
- `briefing_output`은 브리핑 초안 결과물
- 설정은 시트에서 바로 수정 가능
