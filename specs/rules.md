# 교차 업무 규칙

각 규칙은 서버 서비스 한 곳에만 구현하고 재사용한다.

- **BR-01 가중 진척률**: `round(Σ(ProgressRate × 기간일수) / Σ기간일수)`. 기간은 시작·종료 포함, 반올림은 0.5 올림. 대시보드는 공정 없으면 0, 호선·블록 목록은 null(`계획 없음`, `-`).
- **BR-02 도면 게이트**: 필수(`RequiredYN=1`) 연계 도면 중 `DwgStatus≠OBSOLETE`이고 ISSUED 리비전이 하나도 없는 도면이 blocker다. 도면번호순. APPROVED만으로는 통과하지 못한다.
- **BR-03 공정 상태**: 호선의 모든 공정을 재계산한다.
  1. 진척 ≥100 → DONE
  2. 진척 >0 또는 실제착수 있음 → 종료일 < 오늘이면 DELAY, 아니면 WORK
  3. 미착수이고 종료일 < 오늘 → DELAY
  4. 그 외: 모든 선행의 진척 ≥100이고 blocker 없음 → READY, 아니면 PLAN

  호선 자동 전이: DESIGN이고 WORK 공정 있음 → BUILD, 그 결과 BUILD이고 LAUNCH 공정 DONE → LAUNCH. 다른 전이는 없다.
  재계산 시점: 공정 생성·수정·삭제, 선행 변경, 도면 연계·해제, 실적 저장·삭제, 블록·도면 삭제, 신규 Rev, 배포, 결재 처리.
- **BR-04 선행 공정**: 같은 호선만 가능하다. 자기 참조는 400 `PLAN_DEPENDENCY_SELF`, 순환은 400 `PLAN_DEPENDENCY_CYCLE`. 선행 종료일 > 시작일이면 409 `PRED_LATE_CONFIRM_REQUIRED`(`details.late_pred_plan_ids`), `confirm_late_preds=true`로 다시 보내면 저장한다. 저장은 전체 교체이고 `LagDays=0`. 일정 자동 조정은 없다.
- **BR-05 실적**: 같은 공정·작업일은 수정한다. 작업일 오름차순에서 마지막 행의 누적률이 공정 진척, 첫 작업일이 실제착수, 마지막 누적률 ≥100이면 그 날이 실제종료, 이력이 없으면 0/null/null. 합산하지 않는다.
- **BR-06 리비전 상태**
  - 신규 도면: Rev0 DRAFT, `ChangeDesc='최초 작성'`, `CurrentRevNo=0`.
  - 신규 Rev: 최신이 ISSUED/OBSOLETE일 때만 N+1 DRAFT. 기존 ISSUED는 유지하고 도면 상태는 DRAFT.
  - 결재 요청: 최신 DRAFT만. 해당 Rev 결재행을 지우고 1단계(검토)·2단계(승인) WAIT 생성, Rev·도면 REVIEW.
  - 전체 승인 시 Rev·도면 APPROVED. 반려 시 Rev·도면 DRAFT, WAIT 행만 삭제, 반려 행은 이력으로 남는다.
  - 배포: Rev APPROVED이고 결재행이 모두 APPROVE. 기존 ISSUED → OBSOLETE, 대상 ISSUED·`IssueDt=오늘`, `CurrentRevNo` 갱신, 도면 ISSUED.
  - 파일 변경은 DRAFT Rev만 가능하다.
- **BR-07 개정 영향**: 도면별 Rev≥1, ISSUED, `IssueDt`가 [오늘-30일, 오늘]인 최대 Rev의 연계 공정 중 WORK/DONE/DELAY. 경고만 표시한다.
- **BR-08 삭제**: 호선은 하위 전체와 PDF, 블록은 공정·연계(도면은 `BlockId=NULL`로 유지), 공정은 실적·선후행·연계, 도면은 리비전·결재·연계·PDF. DB 커밋 후 파일을 지운다. 새 파일은 커밋 전에 쓰고 실패하면 제거한다.
- **BR-09 권한**

| 메뉴 | ADMIN | PROC | DWG | VIEW |
| --- | --- | --- | --- | --- |
| M00 대시보드 | Admin | View | View | View |
| M10·M11 호선 | Admin | Write | View | View |
| M20·M21 공정 계획 | Admin | Write | View | View |
| M22 공정 실적 | Admin | Write | 없음 | View |
| M30·M31 도면 | Admin | View | Write | View |
| M33 결재함 | Admin | 없음 | Write | View |
| M90·M91 회원관리 | Admin | 없음 | 없음 | 없음 |

호선 상세는 M11, 도면 상세는 M31을 따른다. 데이터는 시드에 있다.
