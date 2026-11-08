// 간트 좌표 계산(F05). 날짜는 'YYYY-MM-DD' 문자열, 내부는 UTC 일 번호.
export const LEFT = 230
export const ROW = 28
export const HEAD = 34
export const SCALES = [
  [2.5, '축소'],
  [4, '보통'],
  [6, '확대'],
]
export const STATUS_COLOR = { PLAN: '#94a3b8', READY: '#0ea5e9', WORK: '#2563eb', DONE: '#16a34a', DELAY: '#dc2626' }

const DAY = 86400000
export const dayNo = (s) => Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10)) / DAY
export const dateOf = (n) => new Date(n * DAY).toISOString().slice(0, 10)
export const addDays = (s, n) => dateOf(dayNo(s) + n)

export function layout(plans, today, scale) {
  const t = dayNo(today)
  const first = Math.min(t - 5, ...plans.map((p) => dayNo(p.plan_start_dt)))
  const fd = new Date(first * DAY)
  const start = Date.UTC(fd.getUTCFullYear(), fd.getUTCMonth(), 1) / DAY
  const end = Math.max(t + 5, ...plans.map((p) => dayNo(p.plan_end_dt)))
  const total = end - start + 8
  const x = (s) => LEFT + (dayNo(s) - start) * scale
  const months = []
  for (let d = new Date(start * DAY); d.getTime() / DAY < start + total; d.setUTCMonth(d.getUTCMonth() + 1)) {
    const iso = d.toISOString().slice(0, 10)
    months.push({ label: `${iso.slice(0, 4)}.${iso.slice(5, 7)}`, x: x(iso) })
  }
  return { start, total, width: LEFT + Math.ceil(total * scale), x, todayX: x(today), months }
}

// 선행 종료+1일 지점(행 중앙) → 4px 오른쪽 → 수직 → 후행 시작.
export function depPath(geo, pred, predRow, succ, succRow) {
  const x0 = geo.x(addDays(pred.plan_end_dt, 1))
  const y0 = predRow * ROW + ROW / 2
  const y1 = succRow * ROW + ROW / 2
  return `${x0},${y0} ${x0 + 4},${y0} ${x0 + 4},${y1} ${geo.x(succ.plan_start_dt)},${y1}`
}
