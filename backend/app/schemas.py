from typing import Annotated

from pydantic import BaseModel, Field

# 형식 규칙은 서비스가 필드별 메시지로 검사하므로 여기서는 상한만 둔다.
Text = Annotated[str, Field(max_length=200)]
Name = Annotated[str, Field(max_length=50)]


class LoginIn(BaseModel):
    emp_no: Text
    password: Text


class OtpIn(BaseModel):
    code: Text


class RegisterIn(BaseModel):
    last_name: Name = ""
    first_name: Name = ""
    birth_date: Text = ""
    phone: Text = ""
    email: Text = ""
    emp_no: Text = ""
    password: Text = ""
    password_confirm: Text = ""


class MenuAccessIn(BaseModel):
    menu_id: Text

Remark = Annotated[str, Field(max_length=1000)]
Short = Annotated[str, Field(max_length=100)]


class HullIn(BaseModel):
    hull_no: Annotated[str, Field(max_length=50)] | None = None
    hull_nm: Short | None = None
    ship_type: Short | None = None
    hull_status: Short | None = None
    owner_nm: Short | None = None
    class_society: Short | None = None
    length_m: float | None = None
    breadth_m: float | None = None
    depth_m: float | None = None
    dead_weight: float | None = None
    dock_no: Short | None = None
    contract_dt: Short | None = None
    delivery_dt: Short | None = None
    remark: Annotated[str, Field(max_length=500)] | None = None
    use_yn: bool = True


class MilestoneItem(BaseModel):
    milestone_cd: Short
    plan_dt: Short | None = None
    actual_dt: Short | None = None


class MilestonesIn(BaseModel):
    items: list[MilestoneItem]


class BlockIn(BaseModel):
    block_cd: Annotated[str, Field(max_length=30)] | None = None
    block_nm: Short | None = None
    block_type: Short | None = None
    weight_ton: float | None = None


class PlanIn(BaseModel):
    block_id: int | None = None
    proc_cd: Short | None = None
    plan_start_dt: Short | None = None
    plan_end_dt: Short | None = None
    manager_emp_no: Short | None = None
    remark: Remark | None = None
    pred_plan_ids: list[int] | None = None
    confirm_late_preds: bool = False


class PredecessorsIn(BaseModel):
    pred_plan_ids: list[int] = []
    confirm_late_preds: bool = False


class PlanLinkIn(BaseModel):
    drawing_id: int
    required: bool = True


class ProgressIn(BaseModel):
    progress_rate: float | None = None
    man_hour: float | None = None
    worker_cnt: int | None = None
    worker_emp_no: Short | None = None
    remark: Remark | None = None


class DrawingIn(BaseModel):
    drawing_no: Short | None = None
    drawing_nm: Text | None = None
    hull_no: Short | None = None
    block_id: int | None = None
    discipline: Short | None = None
    designer_emp_no: Short | None = None


class RevisionIn(BaseModel):
    change_desc: Remark | None = None


class ApprovalRequestIn(BaseModel):
    reviewer_emp_no: Short | None = None
    approver_emp_no: Short | None = None


class DrawingPlanIn(BaseModel):
    plan_id: int | None = None
    required: bool = True


class DecisionIn(BaseModel):
    result: Short | None = None
    comment: Remark | None = None


class UserIn(BaseModel):
    emp_no: Text | None = None
    last_name: Name | None = None
    first_name: Name | None = None
    birth_date: Text | None = None
    phone: Text | None = None
    email: Text | None = None
    password: Text | None = None
    status: Short | None = None
    groups: list[Short] | None = None
    totp_enabled: bool | None = None


class ApproveIn(BaseModel):
    groups: list[Short] = []
