<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../api/client.js'
import DrawingDetailModal from '../components/DrawingDetailModal.vue'
import PageHeader from '../components/PageHeader.vue'
import { STATUS_COLOR } from '../gantt.js'
import { codeName, loadCodes } from '../stores/session.js'
import { navigate, tabs } from '../stores/tabs.js'
import { toast } from '../stores/toast.js'

defineOptions({ inheritAttrs: false })
const props = defineProps({ token: { type: String, required: true }, nonce: { type: Number, default: 0 } })

const DWG_COLOR = { ISSUED: '#16a34a', APPROVED: '#0ea5e9', REVIEW: '#f59e0b', DRAFT: '#94a3b8' }
const KPIS = [
  ['active_hulls', '진행 호선', ''],
  ['delay_plans', '지연 공정', 'err'],
  ['waiting_plans', '도면 대기 공정', 'warn'],
  ['pending_drawings', '결재·배포 대기 도면', 'warn'],
]
const R = 40
const CIRC = 2 * Math.PI * R

const d = ref(null)
const codes = ref({})
const drawingId = ref(null)
let seq = 0

async function load() {
  const mine = ++seq
  try {
    const [data, codeMap] = await Promise.all([api('/api/dashboard/summary'), loadCodes()])
    if (mine !== seq) return
    d.value = data
    codes.value = codeMap
  } catch (e) {
    if (mine === seq) toast.error(e.message)
  }
}

const go = (link) => (link.screen === 'drawing' ? (drawingId.value = link.param) : navigate(link.screen, link.param ?? null))
const planName = (s) => codeName(codes.value, 'PLANSTAT', s)
const dwgName = (s) => codeName(codes.value, 'DWGSTAT', s)
const kpiClass = (key, tone) => (tone && d.value.kpi[key].value ? tone : '')

const totalPlans = computed(() => d.value?.plan_status.reduce((n, s) => n + s.count, 0) ?? 0)
const arcs = computed(() => {
  let at = 0
  return (d.value?.plan_status ?? [])
    .filter((s) => s.count)
    .map((s) => {
      const len = (s.count / totalPlans.value) * CIRC
      const arc = { status: s.status, dash: `${len} ${CIRC - len}`, offset: -at }
      at += len
      return arc
    })
})
const maxDelivery = computed(() => Math.max(1, ...(d.value?.deliveries.map((m) => m.count) ?? [])))

onMounted(load)
watch(() => props.nonce, load)
// 다른 탭에서 데이터를 바꾼 뒤 돌아오면 다시 집계한다
watch(
  () => tabs.active,
  (key) => key?.startsWith(`${props.token}:`) && d.value && load(),
)
</script>

<template>
  <PageHeader :token="token" :desc="d ? `기준일 ${d.today} · 호선/공정/도면 현황` : ''" />
  <template v-if="d">
    <div class="kpis">
      <button v-for="[key, label, tone] in KPIS" :key="key" type="button" class="card kpi" @click="go(d.kpi[key].link)">
        <span class="kl">{{ label }}</span>
        <b class="kv" :class="kpiClass(key, tone)">{{ d.kpi[key].value }}</b>
      </button>
    </div>
    <div class="grid">
      <section class="card">
        <h3>호선별 진척률</h3>
        <div v-for="h in d.hull_progress" :key="h.hull_no" class="hrow" @click="go(h.link)">
          <span class="ell" :title="`${h.hull_no} ${h.hull_nm}`">{{ h.hull_no }} {{ h.hull_nm }}</span>
          <span class="hbar"><i :style="{ width: `${h.progress}%` }" /></span>
          <b>{{ h.progress }}%</b>
        </div>
      </section>
      <section class="card">
        <h3>공정 상태 분포</h3>
        <div class="donut">
          <svg width="120" height="120" viewBox="0 0 120 120" role="img" aria-label="공정 상태 분포">
            <circle cx="60" cy="60" :r="R" fill="none" stroke="#eef1f6" stroke-width="22" />
            <circle
              v-for="a in arcs"
              :key="a.status"
              cx="60"
              cy="60"
              :r="R"
              fill="none"
              :stroke="STATUS_COLOR[a.status]"
              stroke-width="22"
              :stroke-dasharray="a.dash"
              :stroke-dashoffset="a.offset"
              transform="rotate(-90 60 60)"
            />
            <text x="60" y="62" text-anchor="middle" class="dt">{{ totalPlans }}</text>
            <text x="60" y="78" text-anchor="middle" class="ds">전체</text>
          </svg>
          <ul class="legend col">
            <li v-for="s in d.plan_status" :key="s.status">
              <i :style="{ background: STATUS_COLOR[s.status] }" />{{ planName(s.status) }} <b>{{ s.count }}</b>
            </li>
          </ul>
        </div>
      </section>
      <section class="card">
        <h3>분야별 도면 상태</h3>
        <div v-for="x in d.drawing_disciplines" :key="x.discipline" class="disc">
          <span>{{ x.name }} <span class="muted">({{ x.total }})</span></span>
          <div class="stack">
            <template v-for="(color, s) in DWG_COLOR" :key="s">
              <i
                v-if="x.counts[s]"
                :style="{ flex: x.counts[s], background: color }"
                :title="`${dwgName(s)} ${x.counts[s]}`"
              />
            </template>
          </div>
        </div>
        <ul class="legend">
          <li v-for="(color, s) in DWG_COLOR" :key="s"><i :style="{ background: color }" />{{ dwgName(s) }}</li>
        </ul>
      </section>
      <section class="card">
        <h3>월별 인도 예정</h3>
        <div class="months">
          <div v-for="m in d.deliveries" :key="m.month" class="mcol">
            <span class="mv">{{ m.count }}</span>
            <i :style="{ height: `${(m.count / maxDelivery) * 80}px` }" />
            <span class="ml">{{ m.month.slice(2) }}</span>
            <span class="mh">{{ m.hull_nos.join(', ') }}</span>
          </div>
        </div>
      </section>
      <section class="card">
        <h3>지연 공정 <span class="badge bad">{{ d.delay_list.count }}</span></h3>
        <div v-for="p in d.delay_list.items" :key="p.plan_id" class="li" @click="go(p.link)">
          <span>{{ p.hull_no }} {{ p.label }}</span>
          <span class="muted">{{ p.progress_rate }}% · 계획종료 {{ p.plan_end_dt }}</span>
        </div>
        <p v-if="!d.delay_list.count" class="muted empty">지연 공정이 없습니다.</p>
      </section>
      <section class="card">
        <h3>도면 대기 공정 <span class="badge warn">{{ d.waiting_list.count }}</span></h3>
        <div v-for="p in d.waiting_list.items" :key="p.plan_id" class="li" @click="go(p.link)">
          <span>{{ p.hull_no }} {{ p.label }}</span>
          <span class="muted">착수 {{ p.plan_start_dt }} · {{ p.blockers.join(', ') }}</span>
        </div>
        <p v-if="!d.waiting_list.count" class="muted empty">대기 중인 공정이 없습니다.</p>
      </section>
      <section class="card wide">
        <h3>도면 개정 영향 공정 <span class="badge info">{{ d.impact_list.count }}</span></h3>
        <div v-for="i in d.impact_list.items" :key="`${i.drawing_id}-${i.plan_id}`" class="li" @click="go(i.link)">
          <span>
            {{ i.drawing_no }} Rev{{ i.rev_no }} → {{ i.plan_label }}
            <span class="badge" :class="i.plan_status">{{ planName(i.plan_status) }}</span>
          </span>
          <span class="muted">{{ i.change_desc }} · 배포 {{ i.issue_dt }}</span>
        </div>
        <p v-if="!d.impact_list.count" class="muted empty">최근 개정된 도면의 영향 공정이 없습니다.</p>
      </section>
    </div>
  </template>
  <DrawingDetailModal v-if="drawingId" :key="drawingId" :drawing-id="drawingId" @changed="load" @close="drawingId = null" />
</template>

<style scoped>
.kpis {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 12px;
}
.kpi {
  display: grid;
  gap: 2px;
  margin: 0;
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.kpi:hover {
  border-color: var(--pri);
}
.kl {
  font-size: 12px;
  color: var(--muted);
}
.kv {
  font-size: 26px;
  font-weight: 700;
  line-height: 1.2;
}
.kv.err {
  color: var(--err);
}
.kv.warn {
  color: var(--warn);
}
.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.grid .card {
  margin: 0;
  min-width: 0;
}
.wide {
  grid-column: 1 / -1;
}
.hrow {
  display: grid;
  grid-template-columns: 130px 1fr 44px;
  gap: 8px;
  align-items: center;
  padding: 3px 0;
  cursor: pointer;
}
.hrow:hover {
  background: var(--hover);
}
.ell {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hbar {
  height: 14px;
  overflow: hidden;
  border-radius: 7px;
  background: #e5e7eb;
}
.hbar i {
  display: block;
  height: 100%;
  background: var(--pri);
}
.donut {
  display: flex;
  align-items: center;
  gap: 24px;
}
.dt {
  font-size: 20px;
  font-weight: 700;
  fill: var(--ink);
}
.ds {
  font-size: 10px;
  fill: var(--muted);
}
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  margin: 6px 0 0;
  padding: 0;
  list-style: none;
}
.legend.col {
  flex-direction: column;
  gap: 8px;
}
.legend li {
  display: flex;
  align-items: center;
  gap: 6px;
}
.legend i {
  width: 10px;
  height: 10px;
  border-radius: 2px;
}
.disc {
  display: grid;
  gap: 4px;
  margin-bottom: 8px;
}
.stack {
  display: flex;
  height: 16px;
  overflow: hidden;
  border-radius: 3px;
}
.months {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  height: 130px;
  padding: 0 8px;
}
.mcol {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  min-width: 0;
  font-size: 11px;
}
.mcol i {
  width: 100%;
  max-width: 44px;
  background: var(--navy2);
}
.mv {
  font-size: 11px;
}
.mh {
  color: var(--muted);
  font-size: 10px;
}
.li {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 7px 4px;
  border-bottom: 1px solid var(--line2);
  cursor: pointer;
}
.li:last-of-type {
  border-bottom: 0;
}
.li:hover {
  background: var(--hover);
}
.li > span:last-child {
  font-size: 12px;
  text-align: right;
}
.empty {
  margin: 8px 0;
}
</style>
