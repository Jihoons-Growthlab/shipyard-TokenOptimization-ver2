# UI 기준 자료

2026-11-04 완성본을 시드 직후 데이터로 Playwright에서 캡처했다. 뷰포트 1440x900(login-mobile은 390x844), `ship-*`는 canvas 영역만이다. 크레인 애니메이션은 촬영 시 멈췄다.

기존 사용자 제공 캡처는 현재 완성본과 달라 포함하지 않았다. 화면 값은 예시이며 하드코딩하지 않는다.

| 자산 | 출처 | 용도 |
| --- | --- | --- |
| `assets/auth-scene.svg` | 완성본용 자체 제작 SVG, 외부 이미지 없음 | 로그인 배경. 애니메이션과 동작 줄이기 대응을 포함 |
| `../seed/seed.json` | 완성본 시드를 새로 생성해 내보냄. 데모 값 | 초기 데이터. 비밀번호와 TOTP secret은 데모 전용 |

촬영한 상태: login-error는 틀린 비밀번호, otp는 admin, hull-*는 8001, plan-selected는 8001 [201] 탑재, plan-drawing-wait는 8003 [101] 강재절단, progress는 8001 [401] 도장, drawing-detail은 8001-PIPE-501, drawing-detail-draft는 8002-PIPE-401, users는 jung.new 선택, readonly-hull-list는 choi.qa.
