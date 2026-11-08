# 인계
- 완료: S1~S6 (단계 1~12 전체) / 다음: 없음
- 환경: node 24.16, npm 11.13, uv 0.13.7, Chrome, Unity 6000.5.10f1 + WebGLSupport(라이선스 OK). 실행: `cd backend && uv run init-db --seed && uv run uvicorn app.main:app --port 8000`, `cd frontend && npx vite`(또는 `npx vite build && npx vite preview`). 임시 DB는 `SHIPYARD_DB_PATH=<임시>.db SHIPYARD_FILE_DIR=<임시>`. OTP 계정 토큰은 `security.totp_code('JBSWY3DPEHPK3PXP', totp_step())`로 API 로그인 후 sessionStorage `swp_token`.
- Unity 빌드(출력은 gitignore, 없으면 재생성): `/Applications/Unity/Hub/Editor/6000.5.10f1/Unity.app/Contents/MacOS/Unity -batchmode -quit -buildTarget WebGL -projectPath unity/ShipyardViewer -executeMethod ShipBuilder.Build -logFile logs/s5-unity-build.log` → `frontend/public/unity/ship-viewer/Build/`(build.json 포함, 약 15MB). 6000.3 Editor가 다른 프로젝트를 열고 있으니 건드리지 않는다.

## 결정·인터페이스
- 백엔드 공통: `app/errors.py`(`ApiError`, `validation`), `app/db.py`(`tx`), `app/deps.py`(`require(menu_id, level)`), `settings.today`, `services/rules.py`(BR-01~07), `services/plans.query`.
- 프론트: `api(path, {params, body, blob})`, `stores/session.js`, `stores/tabs.js` `navigate(token, param)`.
- 공유 컴포넌트: `BaseModal`, `PageHeader`, `ProgressBar`, `HullDetailModal`(3D 탭에서 size xl, 3D 탭 왕복 시 재조회 안 함), `ShipViewer3D`, `PlanPanel`, `DrawingDetailModal`, `DrawingNewModal`, `DrawingFields`.
- 뷰어 수명주기: `frontend/src/shipViewer.js` `startViewer(canvas, onProgress)` → `{ready, close, setView}`; 모듈 전역 tail로 단일 인스턴스 보장.
- Unity: `Assets/Scripts/ShipViewer.cs`(모델·카메라·SetView), `Assets/Editor/ShipBuilder.cs`(씬·재질·설정·빌드·build.json), `Assets/Plugins/WebGL/ShipViewer.jslib`.
- 테스트 픽스처: `tests/conftest.py`의 `client, conn, session_headers, login`.

## 관련 파일
`specs/index.md`(최종 수용 검증 절), `logs/s6-*.log`

## 검증
- 통과(S6): pytest 123건, vitest 52건, vite build. 시드 수치 foundation 기준과 일치(6/5/17, 83/79/60, 47/79/72/45, 상태·KPI·호선 진척).
- 통과(S6 계정): admin·lee.dwg OTP(오답 400), park.pm, choi.qa(쓰기 403), jung.new(ACCOUNT_PENDING 403).
- 통과(S6 브라우저, 임시 DB): 가입→승인 대기 로그인 거부→승인→로그인 / 호선 등록·삭제 / 공정 추가·필수 도면 연계·선행 연계 / 결재 요청(검토자=승인자 400 확인)→2단계 승인→배포→공정 착수가능 / 실적 100%→완료·후행 착수가능, 40%→진행 / 신규 Rev1 작성 / 3D 탭.
- 통과(S6 1440x900 이미지 비교, 신규 시드): dashboard, plan-gantt, approvals, drawing-list. 나머지 화면은 S1~S5에서 비교.
- 통과(S5): 3D 뷰어 T01~T07(시점 이미지, reset 픽셀 동일, 재진입 누수 없음, 실패·재시도, preview wasm MIME).
- 미실행: 1100px 이하 일반 화면 배치(로그인 모바일·3D 760px 제외), 원본 DB는 변경하지 않아 시드 복원 불필요.

## 미해결
- 프래그먼트 루트 화면(ProgressInput 등)에서 param/nonce 속성 Vue 경고. 동작 영향 없음.

## 다음 세션 첫 작업
없음(전 단계 완료). 필요 시 미실행 항목 확인.
