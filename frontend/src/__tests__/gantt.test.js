import { describe, expect, it } from 'vitest'
import { LEFT, ROW, depPath, layout } from '../gantt.js'

const plan = (s, e) => ({ plan_start_dt: s, plan_end_dt: e })

describe('PLAN-T01 간트 계산', () => {
  it('시작은 min(오늘-5, 공정 시작)이 속한 달 1일, 끝은 max(오늘+5, 공정 종료), 총 일수 +8', () => {
    const g = layout([plan('2026-11-10', '2027-01-20')], '2026-10-19', 4)
    expect(g.x('2026-10-01')).toBe(LEFT)
    expect(g.total).toBe(111 + 8) // 끝(01-20) - 시작(10-01) = 111일
    expect(g.width).toBe(LEFT + Math.ceil(g.total * 4))
    expect(g.todayX).toBe(LEFT + 18 * 4)
    expect(g.months.map((m) => m.label)).toEqual(['2026.10', '2026.11', '2026.12', '2027.01'])
  })

  it('오늘-5가 이전 달이면 그 달부터, 공정이 없으면 오늘 기준', () => {
    const g = layout([], '2026-10-03', 2.5)
    expect(g.x('2026-09-01')).toBe(LEFT)
    expect(g.width).toBe(LEFT + Math.ceil(g.total * 2.5))
  })

  it('선후행선은 선행 종료+1일 → 4px → 수직 → 후행 시작', () => {
    const g = layout([plan('2026-10-01', '2026-10-10')], '2026-10-19', 4)
    const pts = depPath(g, plan('2026-10-01', '2026-10-10'), 0, plan('2026-10-12', '2026-10-20'), 2)
    const x0 = g.x('2026-10-11')
    expect(pts).toBe(`${x0},${ROW / 2} ${x0 + 4},${ROW / 2} ${x0 + 4},${ROW * 2.5} ${g.x('2026-10-12')},${ROW * 2.5}`)
  })
})
