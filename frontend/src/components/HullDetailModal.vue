<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../api/client.js'
import BaseModal from './BaseModal.vue'
import ProgressBar from './ProgressBar.vue'
import ShipViewer3D from './ShipViewer3D.vue'
import { codeName } from '../stores/session.js'
import { navigate } from '../stores/tabs.js'
import { toast } from '../stores/toast.js'

const props = defineProps({
  hullNo: { type: String, default: null },
  codes: { type: Object, default: () => ({}) },
  writable: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'changed'])

const TABS = [
  ['info', '기본정보'],
  ['milestones', '주요일정'],
  ['blocks', '블록 구성'],
  ['summary', '연계 현황'],
  ['3d', '3D 보기'],
]
const EMPTY = {
  hull_no: '', hull_nm: '', ship_type: '', hull_status: 'PLAN', owner_nm: '', class_society: '',
  length_m: null, breadth_m: null, depth_m: null, dead_weight: null, dock_no: '', contract_dt: '',
  delivery_dt: '', remark: '', use_yn: true,
}
const NUMS = ['length_m', 'breadth_m', 'depth_m', 'dead_weight']

const no = ref(props.hullNo)
const tab = ref('info')
const loading = ref(false)
const busy = ref(false)
const status = ref(null)
const form = reactive({ ...EMPTY })
const milestones = ref([])
const blocks = ref([])
const blockForm = reactive({ block_cd: '', block_nm: '', block_type: '', weight_ton: null })
const summary = ref(null)
let seq = 0

const title = computed(() => (no.value ? `호선 ${no.value}` : '호선 등록'))
const subtitle = computed(() => (no.value ? codeName(props.codes, 'HULLSTAT', status.value) : '신규 호선을 등록합니다.'))
const base = () => `/api/hulls/${encodeURIComponent(no.value)}`
const blank = (v) => (v === '' || v === undefined ? null : v)

async function load() {
  if (!no.value) return
  const mine = ++seq
  loading.value = true
  try {
    // 기본정보 외 탭도 제목 아래 상태명이 필요하므로 호선은 항상 읽는다.
    const [hull, data] = await Promise.all([
      api(base()),
      tab.value === 'info' ? null : api(`${base()}/${tab.value}`),
    ])
    if (mine !== seq) return
    status.value = hull.hull_status
    if (tab.value === 'info') Object.assign(form, Object.fromEntries(Object.keys(EMPTY).map((k) => [k, hull[k] ?? EMPTY[k]])))
    if (tab.value === 'milestones') milestones.value = data
    if (tab.value === 'blocks') blocks.value = data
    if (tab.value === 'summary') summary.value = data
  } catch (e) {
    if (mine === seq) toast.error(e.message)
  } finally {
    if (mine === seq) loading.value = false
  }
}

// 3D 탭에서 들어오기 전 탭으로 돌아가면 다시 읽지 않아 작성 내용을 유지한다.
let before3d = null
function select(key) {
  if (key === '3d' && tab.value === '3d') return
  const back = tab.value === '3d' && key === before3d
  if (key === '3d') before3d = tab.value
  tab.value = key
  if (key !== '3d' && !back) load()
}

async function run(action) {
  busy.value = true
  try {
    await action()
  } catch (e) {
    toast.error(e.message)
  } finally {
    busy.value = false
  }
}

const saveInfo = () =>
  run(async () => {
    const body = { ...form }
    for (const k of ['ship_type', 'contract_dt', 'delivery_dt', ...NUMS]) body[k] = blank(body[k])
    if (no.value) {
      delete body.hull_no
      await api(base(), { method: 'PATCH', body })
      toast.success('저장되었습니다.')
    } else {
      const hull = await api('/api/hulls', { method: 'POST', body })
      no.value = hull.hull_no
      toast.success('호선이 등록되었습니다.')
    }
    emit('changed')
    await load()
  })

const removeHull = () => {
  if (!confirm(`호선 ${no.value} 및 하위 데이터(블록·공정·도면)를 모두 삭제합니다. 계속할까요?`)) return
  run(async () => {
    await api(base(), { method: 'DELETE' })
    toast.success('삭제되었습니다.')
    emit('changed')
    emit('close')
  })
}

const saveMilestones = () =>
  run(async () => {
    const items = milestones.value.map((m) => ({ milestone_cd: m.milestone_cd, plan_dt: blank(m.plan_dt), actual_dt: blank(m.actual_dt) }))
    milestones.value = await api(`${base()}/milestones`, { method: 'PUT', body: { items } })
    toast.success('주요일정이 저장되었습니다.')
  })

const addBlock = () =>
  run(async () => {
    const body = { ...blockForm, block_type: blank(blockForm.block_type), weight_ton: blank(blockForm.weight_ton) }
    await api(`${base()}/blocks`, { method: 'POST', body })
    Object.assign(blockForm, { block_cd: '', block_nm: '', block_type: '', weight_ton: null })
    toast.success('블록이 추가되었습니다.')
    await load()
  })

const removeBlock = (b) => {
  if (!confirm('블록과 해당 블록의 공정을 삭제합니다. (도면의 블록 연결은 해제)')) return
  run(async () => {
    await api(`/api/blocks/${b.block_id}`, { method: 'DELETE' })
    toast.success('삭제되었습니다.')
    emit('changed')
    await load()
  })
}

const STATUS_ROWS = (group, keys) => keys.map((k) => [k, codeName(props.codes, group, k)])

onMounted(load)
</script>

<template>
  <BaseModal :title="title" :size="tab === '3d' ? 'xl' : 'large'" @close="emit('close')">
    <p class="sub muted">{{ subtitle }}</p>
    <nav v-if="no" class="subtabs">
      <button v-for="[key, label] in TABS" :key="key" type="button" class="subtab" :class="{ on: tab === key }" @click="select(key)">
        {{ label }}
      </button>
    </nav>

    <form v-if="tab === 'info'" class="card" novalidate @submit.prevent="saveInfo">
      <fieldset :disabled="loading" class="form c4">
        <label class="field">호선번호 *<input v-model.trim="form.hull_no" :readonly="!!no" /></label>
        <label class="field s2">호선명<input v-model="form.hull_nm" /></label>
        <label class="field">선종
          <select v-model="form.ship_type">
            <option value="">선택</option>
            <option v-for="c in codes.SHIPTYPE" :key="c.code" :value="c.code">{{ c.name }}</option>
          </select>
        </label>
        <label class="field">상태
          <select v-model="form.hull_status">
            <option v-for="c in codes.HULLSTAT" :key="c.code" :value="c.code">{{ c.name }}</option>
          </select>
        </label>
        <label class="field s2">선주<input v-model="form.owner_nm" /></label>
        <label class="field">선급<input v-model="form.class_society" /></label>
        <label class="field">전장(m)<input v-model.number="form.length_m" type="number" min="0" step="any" /></label>
        <label class="field">선폭(m)<input v-model.number="form.breadth_m" type="number" min="0" step="any" /></label>
        <label class="field">선심(m)<input v-model.number="form.depth_m" type="number" min="0" step="any" /></label>
        <label class="field">재화중량(DWT)<input v-model.number="form.dead_weight" type="number" min="0" step="any" /></label>
        <label class="field">도크/건조장소<input v-model="form.dock_no" /></label>
        <label class="field">계약일<input v-model="form.contract_dt" type="date" /></label>
        <label class="field">인도 예정일<input v-model="form.delivery_dt" type="date" /></label>
        <div class="field">사용여부<label class="check"><input v-model="form.use_yn" type="checkbox" /> 사용</label></div>
        <label class="field s4">비고<input v-model="form.remark" maxlength="500" /></label>
      </fieldset>
      <div class="actions">
        <button type="submit" class="btn pri" :disabled="!writable || loading || busy">저장</button>
        <button v-if="no" type="button" class="btn danger" :disabled="!writable || loading || busy" @click="removeHull">삭제</button>
        <span class="muted">삭제 시 블록·공정·도면이 함께 삭제됩니다(FK CASCADE).</span>
      </div>
    </form>

    <div v-else-if="tab === 'milestones'" class="card">
      <div class="tw">
        <table class="table">
          <thead><tr><th>일정</th><th>계획일</th><th>실적일</th><th class="num">차이(일)</th></tr></thead>
          <tbody>
            <tr v-for="m in milestones" :key="m.milestone_cd">
              <td>{{ m.name }}</td>
              <td><input v-model="m.plan_dt" type="date" :disabled="loading" :aria-label="`${m.name} 계획일`" /></td>
              <td><input v-model="m.actual_dt" type="date" :disabled="loading" :aria-label="`${m.name} 실적일`" /></td>
              <td class="num">{{ m.diff_days ?? '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="actions">
        <button type="button" class="btn pri" :disabled="!writable || loading || busy" @click="saveMilestones">일정 저장</button>
      </div>
    </div>

    <div v-else-if="tab === 'blocks'" class="card">
      <div class="tw">
        <table class="table">
          <thead>
            <tr><th>블록코드</th><th>블록명</th><th>유형</th><th class="num">중량(ton)</th><th>진척</th><th class="num">공정</th><th class="num">도면</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="b in blocks" :key="b.block_id">
              <td><b>{{ b.block_cd }}</b></td>
              <td>{{ b.block_nm }}</td>
              <td>{{ codeName(codes, 'BLOCKTYPE', b.block_type) }}</td>
              <td class="num">{{ b.weight_ton ?? '' }}</td>
              <td class="prog"><ProgressBar v-if="b.progress !== null" :value="b.progress" /><span v-else>-</span></td>
              <td class="num">{{ b.plan_count }}</td>
              <td class="num">{{ b.drawing_count }}</td>
              <td><button type="button" class="btn sm danger" :disabled="!writable || busy" @click="removeBlock(b)">삭제</button></td>
            </tr>
            <tr v-if="!blocks.length && !loading"><td colspan="8" class="muted">블록이 없습니다.</td></tr>
          </tbody>
        </table>
      </div>
      <form class="block-add" novalidate @submit.prevent="addBlock">
        <input v-model.trim="blockForm.block_cd" placeholder="블록코드 *" aria-label="블록코드" />
        <input v-model="blockForm.block_nm" placeholder="블록명" aria-label="블록명" />
        <select v-model="blockForm.block_type" aria-label="유형">
          <option value="">유형 선택</option>
          <option v-for="c in codes.BLOCKTYPE" :key="c.code" :value="c.code">{{ c.name }}</option>
        </select>
        <input v-model.number="blockForm.weight_ton" type="number" min="0" step="any" placeholder="중량(ton)" aria-label="중량" />
        <button type="submit" class="btn pri" :disabled="!writable || loading || busy">+ 블록 추가</button>
      </form>
    </div>

    <ShipViewer3D v-else-if="tab === '3d'" />

    <div v-else-if="tab === 'summary' && summary" class="sum">
      <section class="card">
        <h3><span>공정 <button type="button" class="btn sm" @click="navigate('plan-gantt', no)">간트 보기</button></span></h3>
        <template v-if="summary.plan_count">
          <p>전체 진척 {{ summary.progress }}%</p>
          <ul>
            <li v-for="[k, label] in STATUS_ROWS('PLANSTAT', ['PLAN', 'READY', 'WORK', 'DONE', 'DELAY'])" :key="k">{{ label }}: {{ summary.plan_status[k] }}</li>
          </ul>
        </template>
        <p v-else class="muted">공정 계획이 없습니다.</p>
      </section>
      <section class="card">
        <h3><span>도면 <button type="button" class="btn sm" @click="navigate('dwg-list', no)">목록 보기</button></span></h3>
        <ul v-if="summary.drawing_count">
          <li v-for="[k, label] in STATUS_ROWS('DWGSTAT', ['ISSUED', 'APPROVED', 'REVIEW', 'DRAFT'])" :key="k">{{ label }}: {{ summary.drawing_status[k] }}</li>
        </ul>
        <p v-else class="muted">도면이 없습니다.</p>
      </section>
    </div>
  </BaseModal>
</template>

<style scoped>
.sub {
  margin: 0 0 10px;
  font-size: 12px;
}
fieldset {
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}
.s2 {
  grid-column: span 2;
}
.s4 {
  grid-column: 1 / -1;
}
.check {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 30px;
  color: var(--ink);
  font-size: 13px;
}
.actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}
.actions .muted {
  font-size: 12px;
}
.prog {
  width: 200px;
}
.block-add {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}
.block-add input,
.block-add select {
  width: 148px;
}
.block-add select {
  width: 110px;
}
.sum {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.sum .card {
  min-height: 205px;
}
.sum h3 > span {
  display: flex;
  align-items: center;
  gap: 6px;
}
.sum ul {
  margin: 0;
  padding-left: 40px;
}
</style>
