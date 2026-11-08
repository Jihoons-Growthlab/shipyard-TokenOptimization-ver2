<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { api } from '../api/client.js'
import PageHeader from '../components/PageHeader.vue'
import PlanPanel from '../components/PlanPanel.vue'
import DrawingDetailModal from '../components/DrawingDetailModal.vue'
import ProgressBar from '../components/ProgressBar.vue'
import { HEAD, ROW, SCALES, STATUS_COLOR, depPath, layout } from '../gantt.js'
import { canWrite, codeName, loadCodes } from '../stores/session.js'
import { toast } from '../stores/toast.js'

const props = defineProps({
  token: { type: String, required: true },
  param: { type: String, default: null },
  nonce: { type: Number, default: 0 },
})

const codes = ref({})
const hulls = ref([])
const procs = ref([])
const users = ref([])
const hullNo = ref('')
const blockId = ref(null)
const scale = ref(4)
const blocks = ref([])
const data = ref(null)
// undefined: 패널 닫힘, null: 신규, 숫자: 선택한 공정
const selectedId = ref(undefined)
const drawingId = ref(null)
const scroller = ref(null)
let seq = 0

const writable = computed(() => canWrite(props.token))
const plans = computed(() => data.value?.plans ?? [])
const shown = computed(() => (blockId.value ? plans.value.filter((p) => p.block_id === blockId.value) : plans.value))
const geo = computed(() => data.value && layout(shown.value, data.value.today, scale.value))
const selected = computed(() => plans.value.find((p) => p.plan_id === selectedId.value) ?? null)
const lines = computed(() => {
  const row = new Map(shown.value.map((p, i) => [p.plan_id, i]))
  return (data.value?.deps ?? [])
    .filter((d) => row.has(d.plan_id) && row.has(d.pred_plan_id))
    .map((d) => {
      const pred = shown.value[row.get(d.pred_plan_id)]
      const succ = shown.value[row.get(d.plan_id)]
      return depPath(geo.value, pred, row.get(d.pred_plan_id), succ, row.get(d.plan_id))
    })
})

const statusName = (s) => codeName(codes.value, 'PLANSTAT', s)
const barTitle = (p) =>
  `${p.label}\n${p.plan_start_dt} ~ ${p.plan_end_dt}\n진척 ${p.progress_rate}% · ${statusName(p.plan_status)}` +
  (p.drawing_wait ? '\n📐 도면 대기' : '')
const barStyle = (p) => {
  const g = geo.value
  const color = STATUS_COLOR[p.plan_status]
  const left = g.x(p.plan_start_dt)
  return {
    left: `${left}px`,
    width: `${g.x(p.plan_end_dt) + scale.value - left}px`,
    background: `color-mix(in srgb, ${color} 35%, white)`,
    '--fill': color,
  }
}

async function load({ resetScroll = false } = {}) {
  if (!hullNo.value) return
  const mine = ++seq
  const keep = scroller.value?.scrollLeft ?? 0
  try {
    const [body, blockRows] = await Promise.all([
      api(`/api/hulls/${encodeURIComponent(hullNo.value)}/plans`),
      api(`/api/hulls/${encodeURIComponent(hullNo.value)}/blocks`),
    ])
    if (mine !== seq) return
    data.value = body
    blocks.value = blockRows
    await nextTick()
    if (!scroller.value) return
    scroller.value.scrollLeft = resetScroll ? geo.value.todayX - scroller.value.clientWidth * 0.4 : keep
  } catch (e) {
    if (mine === seq) toast.error(e.message)
  }
}

function changeHull() {
  blockId.value = null
  selectedId.value = undefined
  data.value = null
  load({ resetScroll: true })
}

function applyParam() {
  const target = (props.param && hulls.value.find((h) => h.hull_no === props.param)) || hulls.value.find((h) => h.plan_count > 0)
  hullNo.value = target?.hull_no ?? hulls.value[0]?.hull_no ?? ''
  changeHull()
}

function onSaved(planId) {
  selectedId.value = planId
  load()
}

function onDeleted() {
  selectedId.value = undefined
  load()
}

watch(() => props.nonce, applyParam)
watch(blockId, () => {
  if (selected.value && blockId.value && selected.value.block_id !== blockId.value) selectedId.value = undefined
})

onMounted(async () => {
  try {
    ;[hulls.value, procs.value, users.value, codes.value] = await Promise.all([
      api('/api/plan-hulls'),
      api('/api/procs'),
      api('/api/users/options'),
      loadCodes(),
    ])
  } catch (e) {
    toast.error(e.message)
    return
  }
  applyParam()
})
</script>

<template>
  <div class="screen">
    <PageHeader :token="token" desc="막대 또는 좌측 공정명을 클릭하면 아래에 상세·수정 패널이 열립니다." />
    <div class="bar">
      <select v-model="hullNo" aria-label="호선" @change="changeHull">
        <option v-for="h in hulls" :key="h.hull_no" :value="h.hull_no">{{ h.hull_no }} {{ h.hull_nm }}</option>
      </select>
      <select v-model="blockId" aria-label="블록">
        <option :value="null">블록 전체</option>
        <option v-for="b in blocks" :key="b.block_id" :value="b.block_id">{{ b.block_cd }} {{ b.block_nm ?? '' }}</option>
      </select>
      <select v-model.number="scale" aria-label="배율">
        <option v-for="[v, label] in SCALES" :key="v" :value="v">{{ label }}</option>
      </select>
      <span>호선 진척</span>
      <div class="hp"><ProgressBar :value="data?.hull_progress ?? 0" /></div>
      <button v-if="writable" type="button" class="btn pri add" :disabled="!data" @click="selectedId = null">+ 공정 추가</button>
    </div>
    <div class="legend">
      <span v-for="(color, s) in STATUS_COLOR" :key="s"><i :style="{ background: color }" />{{ statusName(s) }}</span>
      <span>📐 도면 대기</span>
      <span class="muted">— 선후행 연결선 / 빨간선 = 오늘({{ data?.today }})</span>
    </div>

    <div ref="scroller" class="gantt">
      <p v-if="data && !shown.length" class="empty muted">표시할 공정이 없습니다.</p>
      <div v-else-if="geo" class="canvas" :style="{ width: `${geo.width}px` }">
        <div class="ghead" :style="{ height: `${HEAD}px` }">
          <div class="corner">블록 / 공정</div>
          <span v-for="m in geo.months" :key="m.label" class="month" :style="{ left: `${m.x}px` }">{{ m.label }}</span>
        </div>
        <div class="gbody" :style="{ height: `${shown.length * ROW}px` }">
          <div v-for="m in geo.months" :key="m.label" class="mline" :style="{ left: `${m.x}px` }" />
          <svg class="deps" :width="geo.width" :height="shown.length * ROW">
            <polyline v-for="(pts, i) in lines" :key="i" :points="pts" />
          </svg>
          <div class="today" :style="{ left: `${geo.todayX}px` }"><span>오늘</span></div>
          <div
            v-for="p in shown"
            :key="p.plan_id"
            class="grow"
            :class="{ sel: p.plan_id === selectedId }"
            :style="{ height: `${ROW}px` }"
          >
            <div class="name" @click="selectedId = p.plan_id">
              <span class="muted">{{ p.block_cd ?? '호선' }}</span>{{ p.proc_nm }}<template v-if="p.drawing_wait"> 📐</template>
            </div>
            <div class="gbar" :style="barStyle(p)" :title="barTitle(p)" @click="selectedId = p.plan_id">
              <i :style="{ width: `${p.progress_rate}%` }" />
            </div>
          </div>
        </div>
      </div>
    </div>

    <PlanPanel
      v-if="selectedId !== undefined && data"
      :hull-no="hullNo"
      :plan="selected"
      :plans="plans"
      :blocks="blocks"
      :procs="procs"
      :users="users"
      :codes="codes"
      :default-block-id="blockId"
      :today="data.today"
      :writable="writable"
      @saved="onSaved"
      @deleted="onDeleted"
      @changed="load"
      @close="selectedId = undefined"
      @open-drawing="(id) => (drawingId = id)"
    />
    <DrawingDetailModal v-if="drawingId" :key="drawingId" :drawing-id="drawingId" @changed="load" @close="drawingId = null" />
  </div>
</template>

<style scoped>
.screen {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.bar select {
  width: 110px;
}
.bar select:nth-child(2) {
  width: 128px;
}
.bar select:first-child {
  width: auto;
}
.hp {
  width: 170px;
}
.add {
  margin-left: auto;
}
.legend {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 8px;
  font-size: 12px;
}
.legend span {
  display: flex;
  align-items: center;
  gap: 4px;
}
.legend i {
  width: 12px;
  height: 10px;
  border-radius: 2px;
}
.gantt {
  position: relative;
  flex: 1;
  min-height: 140px;
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--panel);
}
.empty {
  margin: 0;
  padding: 16px;
}
.canvas {
  position: relative;
}
.ghead {
  position: sticky;
  top: 0;
  z-index: 4;
  border-bottom: 1px solid var(--line);
  background: var(--head);
}
.corner {
  position: sticky;
  left: 0;
  z-index: 1;
  width: 230px;
  height: 100%;
  padding: 0 9px;
  border-right: 1px solid var(--line);
  background: var(--head);
  font-weight: 600;
  line-height: 34px;
}
.month {
  position: absolute;
  top: 0;
  padding: 3px 6px;
  border-left: 1px solid var(--line);
  font-size: 11px;
  line-height: 28px;
  height: 100%;
}
.gbody {
  position: relative;
}
.mline {
  position: absolute;
  top: 0;
  bottom: 0;
  border-left: 1px dashed var(--line);
}
.deps {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
}
.deps polyline {
  fill: none;
  stroke: #64748b;
  stroke-opacity: 0.55;
  stroke-width: 1;
}
.today {
  position: absolute;
  top: 0;
  bottom: 0;
  z-index: 2;
  width: 2px;
  background: var(--err);
  pointer-events: none;
}
.today span {
  position: absolute;
  top: 2px;
  left: 5px;
  color: var(--err);
  font-size: 10px;
  white-space: nowrap;
}
.name > .muted {
  width: 26px;
  margin-right: -6px;
}
.grow {
  position: relative;
  border-bottom: 1px solid var(--line2);
}
.grow.sel {
  background: var(--sel);
}
.name {
  position: sticky;
  left: 0;
  z-index: 3;
  display: flex;
  align-items: center;
  gap: 16px;
  width: 230px;
  height: 100%;
  padding: 0 9px;
  border-right: 1px solid var(--line);
  background: inherit;
  cursor: pointer;
  white-space: nowrap;
}
.grow:not(.sel) .name {
  background: var(--panel);
}
.gbar {
  position: absolute;
  top: 6px;
  z-index: 2;
  height: 16px;
  overflow: hidden;
  border-radius: 3px;
  cursor: pointer;
}
.gbar i {
  display: block;
  height: 100%;
  background: var(--fill);
}
</style>
