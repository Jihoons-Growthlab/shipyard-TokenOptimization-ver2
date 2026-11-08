"""F03 대시보드 집계. 대상 호선은 UseYN=1."""
import sqlite3

from ..config import settings
from . import plans, rules

ACTIVE = ("DESIGN", "BUILD", "LAUNCH", "TRIAL")
DWG_STATUSES = ("ISSUED", "APPROVED", "REVIEW", "DRAFT")
LIST_MAX = 6


def _gantt(hull_no: str) -> dict:
    return {"screen": "plan-gantt", "param": hull_no}


def _plan_item(p: dict) -> dict:
    keys = ("plan_id", "hull_no", "label", "plan_status", "progress_rate", "plan_start_dt", "plan_end_dt")
    return {**{k: p[k] for k in keys}, "blockers": [b["drawing_no"] for b in p["blockers"]], "link": _gantt(p["hull_no"])}


def _top(items: list) -> dict:
    return {"count": len(items), "items": items[:LIST_MAX]}


def summary(conn: sqlite3.Connection) -> dict:
    hulls = conn.execute("SELECT HullNo, HullNm, HullStatus, DeliveryDt FROM TB_MST_Hull WHERE UseYN = 1 ORDER BY HullNo").fetchall()
    hull_nos = {h["HullNo"] for h in hulls}
    all_plans = [p for h in hulls for p in plans.query(conn, h["HullNo"])]

    hull_progress = []
    for h in hulls:
        rows = [{"PlanStartDt": p["plan_start_dt"], "PlanEndDt": p["plan_end_dt"], "ProgressRate": p["progress_rate"]}
                for p in all_plans if p["hull_no"] == h["HullNo"]]
        hull_progress.append({"hull_no": h["HullNo"], "hull_nm": h["HullNm"],
                              "progress": rules.weighted_progress(rows) or 0, "link": _gantt(h["HullNo"])})

    delay = sorted((p for p in all_plans if p["plan_status"] == "DELAY"), key=lambda p: (p["plan_end_dt"], p["plan_id"]))
    waiting = sorted((p for p in all_plans if p["drawing_wait"]), key=lambda p: (p["plan_start_dt"], p["plan_id"]))
    impacts = [i for i in rules.impacts(conn) if i["hull_no"] in hull_nos]

    marks = ",".join("?" * len(hull_nos)) or "NULL"
    counts: dict[str, dict[str, int]] = {}
    for r in conn.execute(
        f"SELECT Discipline, DwgStatus, count(*) FROM TB_DWG_Drawing WHERE HullNo IN ({marks}) GROUP BY Discipline, DwgStatus",
        tuple(hull_nos),
    ):
        counts.setdefault(r[0], {})[r[1]] = r[2]
    disciplines = []
    for c in conn.execute("SELECT Code, CodeName FROM TB_SYS_Code WHERE CodeGroup = 'DWGDISC' ORDER BY Seq, Code"):
        by_status = {s: counts.get(c[0], {}).get(s, 0) for s in DWG_STATUSES}
        if sum(by_status.values()):
            disciplines.append({"discipline": c[0], "name": c[1], "total": sum(by_status.values()), "counts": by_status})
    pending_drawings = sum(v.get("APPROVED", 0) + v.get("REVIEW", 0) for v in counts.values())

    months: dict[str, list[str]] = {}
    for h in hulls:
        if h["DeliveryDt"]:
            months.setdefault(h["DeliveryDt"][:7], []).append(h["HullNo"])

    def kpi(value: int, screen: str, items: list | None = None) -> dict:
        link = {"screen": screen}
        if items:
            link["param"] = items[0]["hull_no"]
        return {"value": value, "link": link}

    return {
        "today": settings.today,
        "kpi": {
            "active_hulls": kpi(sum(h["HullStatus"] in ACTIVE for h in hulls), "hull-list"),
            "delay_plans": kpi(len(delay), "plan-gantt", delay),
            "waiting_plans": kpi(len(waiting), "plan-gantt", waiting),
            "pending_drawings": kpi(pending_drawings, "dwg-approval"),
        },
        "hull_progress": hull_progress,
        "plan_status": [{"status": s, "count": sum(p["plan_status"] == s for p in all_plans)} for s in rules.PLAN_STATUSES],
        "drawing_disciplines": disciplines,
        "deliveries": [{"month": m, "count": len(n), "hull_nos": n} for m, n in sorted(months.items())],
        "delay_list": _top([_plan_item(p) for p in delay]),
        "waiting_list": _top([_plan_item(p) for p in waiting]),
        "impact_list": _top(impacts),
    }
