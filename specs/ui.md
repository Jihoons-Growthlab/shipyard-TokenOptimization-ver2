# 디자인 시스템

조밀한 업무용 화면이다. 값은 완성본 기준이며, 공통 스타일은 전역 CSS 한 파일에 두고 화면 전용 배치만 scoped로 둔다. 비교 기준 해상도는 1440x900이다.

## 토큰

| 토큰 | 값 | 토큰 | 값 |
| --- | --- | --- | --- |
| navy / navy2 | #12294a / #1b3a66 | pri / pri-d | #2563eb / #1d4ed8 |
| bg / panel | #f2f4f8 / #fff | line / line2 | #d9dee8 / #edf0f5 |
| ink / muted | #1f2937 / #6b7280 | err / ok / warn | #dc2626 / #16a34a / #d97706 |
| sel / hover / head | #dbeafe / #f4f8ff / #eef1f6 | tabs bg / tab off | #e4e8f0 / #cfd6e4 |

본문 13px, 글꼴 `'Malgun Gothic','Apple SD Gothic Neo','Noto Sans KR',system-ui,sans-serif`, line-height는 지정하지 않는다(normal). h2 16px, 카드 h3 13.5px.

## 셸

- 헤더 50px, navy, 좌우 16px, 항목 간격 14px. 브랜드 `⚓ SWP 조선소 통합관리` 15px 700, 뒤에 `호선 / 공정 / 도면` 11px opacity .65. 오른쪽에 날씨 알약, 사용자(이름 700·`그룹 · 기준일` 11px, 왼쪽 정렬), 로그아웃. 헤더 버튼 높이 26px, 테두리 #3b5a8c.
- 날씨 알약: navy2, radius 18px, padding 4px 12px, 12px, 간격 8px, 온도 14px bold. 샘플 배지 #f59e0b/#3b2600, LIVE 배지 #22c55e/#052e16.
- 메뉴 230px, 흰 배경, 오른쪽 테두리. `MENU` 11px letter-spacing 1px. 항목 padding 7px 14px, 간격 6px, 앞에 12px 폭 표식(그룹 ▼/▶ 9px, 말단 `·`). 하위 항목 padding-left 34px. 선택은 sel 배경 + pri-d 700, 호버 #eef3fb.
- 탭바 높이 36px, 배경 tabs bg, padding 6px 8px 0, 간격 2px. 탭 30px, radius 6px 6px 0 0, 12.5px, 비활성 tab off, 활성 흰색 + navy 700. × 버튼은 18px 원형, 호버 시 err. `다른 탭 닫기`는 탭 2개 이상일 때 오른쪽 끝.
- 작업 영역 padding 14px 18px 24px, bg 배경, 스크롤은 이 영역만.

## 요소

- 제목줄 `.ph`: h2 + 12px muted 설명을 baseline 정렬, 아래 12px. 조회 전용이면 `조회 전용` 배지(#fef3c7/#92400e, 11px).
- 버튼 30px, padding 0 13px, radius 5px, 흰 배경 + line 테두리. 주 버튼 pri, 성공 ok, 위험은 err 글자 + #fecaca 테두리, 작은 버튼 24px·12px. disabled opacity .45.
- 입력 30px, padding 4px 8px, radius 5px, line 테두리. 포커스 pri 테두리 + 2px #bfdbfe 외곽선. readonly/disabled 배경 #f3f4f6, muted 글자. 라벨은 위쪽 12px muted, 간격 3px.
- 폼 그리드: gap 10px 12px, align-items end, 2·4·6열.
- 카드: 흰 배경, line 테두리, radius 8px, padding 12px 14px, 아래 12px. h3은 제목과 배지를 양 끝 정렬.
- 표: 전체 폭, 테두리 + radius 6px. th는 head 배경 7px 9px, 600, sticky. td 6px 9px, 아래 line2, nowrap(긴 글은 wrap). 호버 hover, 선택 sel. 숫자 오른쪽 정렬.
- 표 래퍼 `.tw`: 스크롤 + 테두리. 고정형 `r3`는 높이 140px.
- 배지: 11.5px, radius 10px, padding 1px 8px.

| 의미 | 배경/글자 |
| --- | --- |
| 공정 PLAN / READY / WORK / DONE / DELAY | #e2e8f0/#475569, #e0f2fe/#0369a1, #dbeafe/#1d4ed8, #dcfce7/#15803d, #fee2e2/#b91c1c |
| 도면 DRAFT / REVIEW / APPROVED / ISSUED | #e2e8f0/#475569, #fef3c7/#92400e, #e0f2fe/#0369a1, #dcfce7/#15803d |
| 도면 OBSOLETE | #f3f4f6/#9ca3af, 취소선 |
| warn / bad / ok / info | #fef3c7/#92400e, #fee2e2/#b91c1c, #dcfce7/#15803d, #dbeafe/#1d4ed8 |

- 진척 바: 높이 16px, radius 8px, 트랙 #e5e7eb, 채움 pri, 가운데 10.5px bold `N%`, min-width 90px. 공통 컴포넌트 하나로 쓴다.
- 안내 박스: warn #fffbeb/#fde68a/#92400e, ok #f0fdf4/#bbf7d0/#166534, 12.5px.
- 토스트: 오른쪽 아래 20px, 기본 #111827, 오류 #b91c1c, 성공 #15803d.

## 모달

- 배경 rgba(15,23,42,.55), 패널 bg 배경, radius 10px, 큰 그림자, max-height 94vh.
- 헤더 navy, padding 10px 16px, 제목 14px, 오른쪽 `닫기 ✕` 버튼.
- 크기: 기본 760px, large 1100px(96vw 이내), xl `min(1640px,97vw)`·높이 94vh. 본문 padding 14px 18px 20px, 내부 스크롤.
- 닫기: 버튼, 배경 클릭, Esc. 하나의 공통 컴포넌트로 만든다.
- 서브탭: 아래 2px line, 활성은 흰 배경 + pri 700.

## 반응형

720px 이하에서 메뉴 160px, 폼은 2열, 헤더 부가 문구 숨김. 그 외 화면별 규칙은 해당 명세를 따른다.
