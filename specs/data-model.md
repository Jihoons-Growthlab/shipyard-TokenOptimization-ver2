# 데이터 모델

SQLite. 아래 스키마와 시드가 완성본 기준이다. 번호 붙은 SQL 마이그레이션으로 구현하고 `schema_migrations`로 한 번씩만 적용한다.

- API는 snake_case, DB는 PascalCase이며 매핑은 도메인별 한 곳에서 처리한다.
- 불리언은 INTEGER 0/1, 날짜는 `YYYY-MM-DD` TEXT.
- 연결마다 `PRAGMA foreign_keys=ON`, `busy_timeout=5000`. 쓰기는 `BEGIN IMMEDIATE` 트랜잭션.
- 추가 인덱스: `users(replace(phone,'-',''))` UNIQUE, `TB_SYS_LogAccess(UserId)`.
- 연쇄 삭제는 아래 FK에 맡긴다.
- 시드는 `reference/seed/seed.json`을 PK 값 그대로 적재한다. `demo_password`는 Argon2로 해시해 `password_hash`에 넣고, 파일의 상태값은 재계산하지 않는다.

### schema_migrations

| 컬럼 | 타입 | 제약 |
| --- | --- | --- |
| version | TEXT | PK |
| applied_at | TEXT | NOT NULL · DEFAULT CURRENT_TIMESTAMP |

### users

| 컬럼 | 타입 | 제약 |
| --- | --- | --- |
| id | TEXT | PK |
| email | TEXT | NOT NULL |
| password_hash | TEXT | NOT NULL |
| display_name | TEXT | NOT NULL |
| emp_no | TEXT | NOT NULL |
| status | TEXT | NOT NULL · DEFAULT 'pending' |
| auth_provider | TEXT | NOT NULL · DEFAULT 'local' |
| last_name | TEXT | NOT NULL |
| first_name | TEXT | NOT NULL |
| birth_date | TEXT | NOT NULL |
| phone | TEXT | NOT NULL |
| totp_enabled | INTEGER | NOT NULL · DEFAULT 0 |
| totp_secret | TEXT |  |
| created_at | TEXT | NOT NULL |

제약: CHECK status IN ('pending','approved','rejected','disabled'); UNIQUE(email); UNIQUE(emp_no)

### TB_SYS_CodeGroup

| 컬럼 | 타입 | 제약 |
| --- | --- | --- |
| CodeGroup | TEXT | PK |
| CodeGroupName | TEXT | NOT NULL |
| Seq | INTEGER | NOT NULL · DEFAULT 0 |
| UseYN | INTEGER | NOT NULL · DEFAULT 1 |

### TB_SYS_Code

| 컬럼 | 타입 | 제약 |
| --- | --- | --- |
| CodeGroup | TEXT | PK#1 · → TB_SYS_CodeGroup.CodeGroup CASCADE |
| Code | TEXT | PK#2 |
| CodeName | TEXT | NOT NULL |
| Seq | INTEGER | NOT NULL · DEFAULT 0 |
| UseYN | INTEGER | NOT NULL · DEFAULT 1 |

### TB_SYS_AuthGroup

| 컬럼 | 타입 | 제약 |
| --- | --- | --- |
| AuthCd | TEXT | PK |
| AuthNm | TEXT | NOT NULL |

### TB_SYS_AuthUser

| 컬럼 | 타입 | 제약 |
| --- | --- | --- |
| AuthCd | TEXT | PK#1 · → TB_SYS_AuthGroup.AuthCd CASCADE |
| EmpNo | TEXT | PK#2 · → users.emp_no CASCADE |

### TB_SYS_MenuInfo

| 컬럼 | 타입 | 제약 |
| --- | --- | --- |
| MenuId | TEXT | PK |
| SystemId | TEXT | NOT NULL · DEFAULT 'SHIP' |
| ParentId | TEXT | → TB_SYS_MenuInfo.MenuId CASCADE |
| Title | TEXT | NOT NULL |
| TokenUrl | TEXT |  |
| Seq | INTEGER | NOT NULL · DEFAULT 0 |
| UseYN | INTEGER | NOT NULL · DEFAULT 1 |

제약: UNIQUE(TokenUrl)

### TB_SYS_AuthMenu

| 컬럼 | 타입 | 제약 |
| --- | --- | --- |
| MenuId | TEXT | PK#1 · → TB_SYS_MenuInfo.MenuId CASCADE |
| AuthCd | TEXT | PK#2 · → TB_SYS_AuthGroup.AuthCd CASCADE |
| AuthGbn | TEXT | NOT NULL |

제약: CHECK AuthGbn IN ('View','Write','Admin')

### TB_SYS_LogAccess

| 컬럼 | 타입 | 제약 |
| --- | --- | --- |
| LogId | INTEGER | PK |
| UserId | TEXT | → users.emp_no SET NULL |
| LoginDt | TEXT | NOT NULL |
| LogoutDt | TEXT |  |
| IpAddress | TEXT |  |
| ComputerNm | TEXT |  |
| WindowAccount | TEXT |  |

제약: AUTOINCREMENT

### TB_SYS_LogMenuAccess

| 컬럼 | 타입 | 제약 |
| --- | --- | --- |
| AccIndex | INTEGER | PK |
| MenuId | TEXT | NOT NULL · → TB_SYS_MenuInfo.MenuId CASCADE |
| LogId | INTEGER | NOT NULL · → TB_SYS_LogAccess.LogId CASCADE |
| InDt | TEXT | NOT NULL |

제약: AUTOINCREMENT

### TB_MST_Hull

| 컬럼 | 타입 | 제약 |
| --- | --- | --- |
| HullNo | TEXT | PK |
| HullNm | TEXT | NOT NULL |
| ShipType | TEXT |  |
| HullStatus | TEXT |  |
| OwnerNm | TEXT |  |
| ClassSociety | TEXT |  |
| LengthM | REAL |  |
| BreadthM | REAL |  |
| DepthM | REAL |  |
| DeadWeight | REAL |  |
| DockNo | TEXT |  |
| ContractDt | TEXT |  |
| DeliveryDt | TEXT |  |
| Remark | TEXT |  |
| UseYN | INTEGER | NOT NULL · DEFAULT 1 |
| CreateUserId | TEXT |  |
| CreateDt | TEXT |  |
| ModifyUserId | TEXT |  |
| ModifyDt | TEXT |  |

### TB_MST_HullMilestone

| 컬럼 | 타입 | 제약 |
| --- | --- | --- |
| HullNo | TEXT | PK#1 · → TB_MST_Hull.HullNo CASCADE |
| MilestoneCd | TEXT | PK#2 |
| PlanDt | TEXT |  |
| ActualDt | TEXT |  |
| Remark | TEXT |  |

### TB_MST_Block

| 컬럼 | 타입 | 제약 |
| --- | --- | --- |
| BlockId | INTEGER | PK |
| HullNo | TEXT | NOT NULL · → TB_MST_Hull.HullNo CASCADE |
| BlockCd | TEXT | NOT NULL |
| BlockNm | TEXT |  |
| BlockType | TEXT |  |
| ParentBlockId | INTEGER | → TB_MST_Block.BlockId SET NULL |
| WeightTon | REAL |  |
| UseYN | INTEGER | NOT NULL · DEFAULT 1 |

제약: AUTOINCREMENT; UNIQUE(HullNo, BlockCd)

### TB_PRC_Proc

| 컬럼 | 타입 | 제약 |
| --- | --- | --- |
| ProcCd | TEXT | PK |
| ProcNm | TEXT | NOT NULL |
| ProcGroup | TEXT |  |
| StdDays | INTEGER |  |
| Seq | INTEGER | NOT NULL · DEFAULT 0 |
| UseYN | INTEGER | NOT NULL · DEFAULT 1 |

### TB_PRC_Plan

| 컬럼 | 타입 | 제약 |
| --- | --- | --- |
| PlanId | INTEGER | PK |
| HullNo | TEXT | NOT NULL · → TB_MST_Hull.HullNo CASCADE |
| BlockId | INTEGER | → TB_MST_Block.BlockId CASCADE |
| ProcCd | TEXT | NOT NULL · → TB_PRC_Proc.ProcCd |
| PlanStartDt | TEXT | NOT NULL |
| PlanEndDt | TEXT | NOT NULL |
| ActualStartDt | TEXT |  |
| ActualEndDt | TEXT |  |
| ProgressRate | REAL | NOT NULL · DEFAULT 0 |
| PlanStatus | TEXT | NOT NULL · DEFAULT 'PLAN' |
| ManagerEmpNo | TEXT | → users.emp_no SET NULL |
| Remark | TEXT |  |
| CreateUserId | TEXT |  |
| CreateDt | TEXT |  |

제약: AUTOINCREMENT; CHECK ProgressRate BETWEEN 0 AND 100; CHECK PlanStartDt <= PlanEndDt

### TB_PRC_PlanDep

| 컬럼 | 타입 | 제약 |
| --- | --- | --- |
| PlanId | INTEGER | PK#1 · → TB_PRC_Plan.PlanId CASCADE |
| PredPlanId | INTEGER | PK#2 · → TB_PRC_Plan.PlanId CASCADE |
| LagDays | INTEGER | NOT NULL · DEFAULT 0 |

제약: CHECK PlanId <> PredPlanId

### TB_PRC_Progress

| 컬럼 | 타입 | 제약 |
| --- | --- | --- |
| ProgressId | INTEGER | PK |
| PlanId | INTEGER | NOT NULL · → TB_PRC_Plan.PlanId CASCADE |
| WorkDt | TEXT | NOT NULL |
| ProgressRate | REAL | NOT NULL |
| ManHour | REAL |  |
| WorkerCnt | INTEGER |  |
| WorkerEmpNo | TEXT | → users.emp_no SET NULL |
| Remark | TEXT |  |
| CreateDt | TEXT |  |

제약: AUTOINCREMENT; CHECK ProgressRate BETWEEN 0 AND 100; UNIQUE(PlanId, WorkDt)

### TB_DWG_Drawing

| 컬럼 | 타입 | 제약 |
| --- | --- | --- |
| DrawingId | INTEGER | PK |
| DrawingNo | TEXT | NOT NULL |
| DrawingNm | TEXT | NOT NULL |
| HullNo | TEXT | NOT NULL · → TB_MST_Hull.HullNo CASCADE |
| BlockId | INTEGER | → TB_MST_Block.BlockId SET NULL |
| Discipline | TEXT |  |
| DwgStatus | TEXT | NOT NULL · DEFAULT 'DRAFT' |
| CurrentRevNo | INTEGER | NOT NULL · DEFAULT 0 |
| DesignerEmpNo | TEXT | → users.emp_no SET NULL |
| UseYN | INTEGER | NOT NULL · DEFAULT 1 |
| CreateUserId | TEXT |  |
| CreateDt | TEXT |  |
| ModifyUserId | TEXT |  |
| ModifyDt | TEXT |  |

제약: AUTOINCREMENT; UNIQUE(DrawingNo)

### TB_DWG_Revision

| 컬럼 | 타입 | 제약 |
| --- | --- | --- |
| DrawingId | INTEGER | PK#1 · → TB_DWG_Drawing.DrawingId CASCADE |
| RevNo | INTEGER | PK#2 |
| RevStatus | TEXT | NOT NULL · DEFAULT 'DRAFT' |
| ChangeDesc | TEXT |  |
| FileId | TEXT |  |
| FileNm | TEXT |  |
| AuthorEmpNo | TEXT | → users.emp_no SET NULL |
| IssueDt | TEXT |  |
| CreateDt | TEXT |  |

### TB_DWG_Approval

| 컬럼 | 타입 | 제약 |
| --- | --- | --- |
| ApprovalId | INTEGER | PK |
| DrawingId | INTEGER | NOT NULL · → TB_DWG_Revision.DrawingId CASCADE (복합 FK) |
| RevNo | INTEGER | NOT NULL · → TB_DWG_Revision.RevNo CASCADE (복합 FK) |
| StepNo | INTEGER | NOT NULL |
| ApproverEmpNo | TEXT | → users.emp_no SET NULL |
| Result | TEXT | NOT NULL · DEFAULT 'WAIT' |
| Comment | TEXT |  |
| ActDt | TEXT |  |

제약: AUTOINCREMENT; CHECK Result IN ('WAIT','APPROVE','REJECT'); UNIQUE(DrawingId, RevNo, StepNo)

### TB_DWG_PlanLink

| 컬럼 | 타입 | 제약 |
| --- | --- | --- |
| DrawingId | INTEGER | PK#1 · → TB_DWG_Drawing.DrawingId CASCADE |
| PlanId | INTEGER | PK#2 · → TB_PRC_Plan.PlanId CASCADE |
| RequiredYN | INTEGER | NOT NULL · DEFAULT 1 |
| NeedDt | TEXT |  |
