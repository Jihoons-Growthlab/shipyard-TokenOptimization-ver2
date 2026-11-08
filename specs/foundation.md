# 기반 구성

## 구조

```text
backend/    FastAPI (app/routers, app/services, app/schemas.py, tests/)
frontend/   Vue 3 + Vite (src/api, src/stores, src/components, src/views, src/screens)
database/   migrations/NNNN_*.sql, shipyard.db (gitignore)
storage/    업로드 PDF (gitignore)
unity/      Unity 프로젝트 (단계 11)
```

아키텍처 원칙은 라우터(입출력·권한) → 서비스(규칙) → DB다. HTTP 호출은 단일 API 클라이언트, 공통 코드와 세션은 스토어로 둔다.

## 기준 버전

| 구성 | 버전 |
| --- | --- |
| Python | 3.10 이상 |
| fastapi / uvicorn / pyjwt / argon2-cffi | 0.162 / 0.54 / 2.15 / 25.1 |
| pytest / httpx | 9.2 / 0.28 |
| vue / vue-router | 3.5 / 4.6 |
| vite / @vitejs/plugin-vue | 6.4 / 5.2 |
| vitest / @vue/test-utils / jsdom | 2.1 / 2.5 / 25 |

차트·드래그·UI 프레임워크 라이브러리를 추가하지 않는다. 차트는 SVG·CSS로 직접 그린다.

## 실행

- 백엔드 `127.0.0.1:8000`, 프론트 `127.0.0.1:5173`. Vite가 `/api`를 백엔드로 프록시한다.
- `init-db --seed` CLI: 마이그레이션 적용 후 시드 적재. 반복 실행해도 안전해야 한다.

| 환경 변수 | 기본 | 용도 |
| --- | --- | --- |
| `SHIPYARD_DB_PATH` | `database/shipyard.db` | DB 경로 |
| `APP_SECRET` | 프로세스별 난수 | JWT 서명. 커밋된 기본값을 두지 않는다 |
| `TOKEN_TTL` | 28800 | 접근 토큰 수명(초) |
| `OTP_TOKEN_TTL` | 300 | OTP 대기 토큰 수명(초) |
| `SHIPYARD_FILE_DIR` | `storage/drawings` | PDF 저장 위치 |
| `WEATHER_PROVIDER` | 빈 값 | 날씨 공급자 이름 |

`backend/.env.example`을 두고 실제 비밀값은 커밋하지 않는다.

## 공통 계약

- 기준일은 설정값 `2026-10-19`로 고정한다. 모든 "오늘"은 이 값을 쓴다.
- 오류 본문: `{"code","message","details"}`. message는 화면에 그대로 표시되는 한국어다.
- 상태: 400 `VALIDATION_ERROR`(details.field), 401 `UNAUTHORIZED`, 403 `FORBIDDEN`(details.menu_id), 404 `*_NOT_FOUND`, 409 `DUPLICATE`·상태 충돌, 413 `FILE_TOO_LARGE`, 422 `INVALID_FORMAT`, 429 `OTP_LOCKED`.
- 형식 검증 실패(Pydantic)도 같은 본문이며 message는 `요청 형식이 올바르지 않습니다.`
- 입력 길이는 DB 컬럼 의미에 맞게 스키마에서 제한한다(이름 50, 비고 1000, 호선 비고 500 등).
- `GET /api/health` → `{"status":"ok"}`.
- `GET /api/codes`(로그인 사용자) → `{그룹: [{code,name}]}`. 프론트는 세션당 한 번 불러와 재사용한다.
- 공정 라벨은 `[블록코드] 공정명`, 블록 없는 공정은 `[호선] 공정명`.

## 권한

의존성 하나로 구현한다: 메뉴 ID와 최소 등급을 받아 미달이면 403. 등급은 View=1, Write=2, Admin=3이며 여러 그룹이면 최고값이다. 권한은 요청마다 DB에서 읽어 변경이 즉시 반영된다.

## 시드 기준 수치

| 항목 | 값 |
| --- | --- |
| users / 호선 / 블록 | 6 / 5 / 17 |
| 공정 / 의존 / 실적 | 83 / 79 / 60 |
| 도면 / 리비전 / 결재 / 연계 | 47 / 79 / 72 / 45 |
| 공정 상태 | PLAN 39, READY 0, WORK 7, DONE 36, DELAY 1 |
| KPI | 진행 호선 4, 지연 1, 도면 대기 8, 결재·배포 대기 6 |
| 호선 진척 8001~8005 | 65, 17, 0, 0, 94 |

## 데모 계정

`reference/seed/seed.json`의 `users`에 있다. admin, lee.dwg는 OTP 사용이며 코드는 `totp_secret`으로 계산한다(±1 step, 같은 step 재사용 불가).

## 테스트

- 백엔드: 임시 DB fixture로 pytest. 각 명세의 AC를 테스트 ID로 구현한다.
- 프론트: vitest + jsdom. 로딩 경쟁, 상태 분기, 권한 UI처럼 회귀 위험이 큰 곳에 집중한다.
- jsdom은 canvas·레이아웃을 검증하지 못한다. 화면은 실제 브라우저로 확인한다.
