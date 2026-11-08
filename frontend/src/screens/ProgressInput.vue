<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../api/client.js'
import PageHeader from '../components/PageHeader.vue'
import ProgressBar from '../components/ProgressBar.vue'
import { canWrite, codeName, loadCodes, session } from '../stores/session.js'
import { toast } from '../stores/toast.js'

const props = defineProps({ token: { type: String, required: true } })

const codes = ref({})
const hulls = ref([])
const users = ref([])
const hullNo = ref('')
const includeDone = ref(false)
const today = ref('')
const rows = ref([])
const selectedId = ref(null)
const detail = ref(null)
const form = reactive({})
const busy = ref(false)
let listSeq = 0
let detailSeq = 0

const writable = computed(() => canWrite(props.token))
const statusName = (s) => codeName(codes.value, 'PLANSTAT', s)
const dash = (v) => v ?? '-'

function resetForm(plan) {
  Object.assign(form, {
    work_dt: today.value,
    progress_rate: plan?.progress_rate ?? 0,
    man_hour: null,
    worker_cnt: null,
    worker_emp_no: session.me?.emp_no ?? '',
    remark: '',
  })
}

async function loadList() {
  if (!hullNo.value) return
  const mine = ++listSeq
  try {
    const data = await api(`/api/hulls/${encodeURIComponent(hullNo.value)}/progress-targets`, {
      params: { include_done: includeDone.value },
    })
    if (mine !== listSeq) return
    today.value = data.today
    rows.value = data.plans
  } catch (e) {
    if (mine === listSeq) toast.error(e.message)
  }
}

async function loadDetail() {
  const mine = ++detailSeq
  try {
    const data = await api(`/api/plans/${selectedId.value}/progress`)
    if (mine !== detailSeq) return
    detail.value = data
    resetForm(data.plan)
  } catch (e) {
    if (mine === detailSeq) toast.error(e.message)
  }
}

function select(planId) {
  selectedId.value = planId
  detail.value = null
  loadDetail()
}

function changeHull() {
  selectedId.value = null
  detail.value = null
  ++detailSeq
  loadList()
}

const blank = (v) => (v === '' || v === undefined ? null : v)

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

const save = () =>
  run(async () => {
    const body = {
      progress_rate: blank(form.progress_rate),
      man_hour: blank(form.man_hour),
      worker_cnt: blank(form.worker_cnt),
      worker_emp_no: form.worker_emp_no || null,
      remark: form.remark,
    }
    const data = await api(`/api/plans/${selectedId.value}/progress/${form.work_dt || '-'}`, { method: 'PUT', body })
    toast.success(data.plan.progress_rate >= 100 ? '실적 저장 — 공정이 완료 처리되었습니다.' : '실적이 저장되었습니다.')
    ++detailSeq
    detail.value = data
    resetForm(data.plan)
    await loadList()
  })

const remove = (h) => {
  if (!confirm('실적을 삭제합니다.')) return
  run(async () => {
    const data = await api(`/api/progress/${h.progress_id}`, { method: 'DELETE' })
    toast.success('실적이 삭제되었습니다.')
    ++detailSeq
    detail.value = data
    resetForm(data.plan)
    await loadList()
  })
}

onMounted(async () => {
  try {
    const [data, userRows, codeMap] = await Promise.all([api('/api/progress-hulls'), api('/api/users/options'), loadCodes()])
    hulls.value = data.hulls
    users.value = userRows
    codes.value = codeMap
    hullNo.value = data.default_hull_no ?? ''
  } catch (e) {
    toast.error(e.message)
    return
  }
  loadList()
})
</script>

<template>
  <PageHeader
    :token="token"
    title="공정 실적 입력"
    desc="착수 가능/진행/지연 공정의 일별 진척률·공수를 입력하면 공정 진척과 상태가 갱신됩니다."
  />
  <div class="bar">
    <select v-model="hullNo" aria-label="호선" @change="changeHull">
      <option v-for="h in hulls" :key="h.hull_no" :value="h.hull_no">{{ h.hull_no }} {{ h.hull_nm }}</option>
    </select>
    <label class="chk"><input v-model="includeDone" type="checkbox" @change="loadList" /> 완료 공정 포함</label>
  </div>
  <div class="tw">
    <table class="table">
      <thead>
        <tr><th>공정</th><th>계획기간</th><th>실제착수</th><th>진척</th><th>상태</th><th>담당</th></tr>
      </thead>
      <tbody>
        <tr v-for="p in rows" :key="p.plan_id" :class="{ sel: p.plan_id === selectedId }" @click="select(p.plan_id)">
          <td>{{ p.label }}</td>
          <td>{{ p.plan_start_dt }} ~ {{ p.plan_end_dt }}</td>
          <td>{{ p.actual_start_dt }}</td>
          <td class="prog"><ProgressBar :value="p.progress_rate" /></td>
          <td><span class="badge" :class="p.plan_status">{{ statusName(p.plan_status) }}</span></td>
          <td>{{ p.manager_nm }}</td>
        </tr>
        <tr v-if="!rows.length"><td colspan="6" class="muted">대상 공정이 없습니다.</td></tr>
      </tbody>
    </table>
  </div>

  <p v-if="!selectedId" class="muted hint">위 목록에서 공정을 선택하세요.</p>
  <section v-else-if="detail" class="card detail">
    <h3>
      <span>{{ detail.plan.label }}</span>
      <span class="badge" :class="detail.plan.plan_status">{{ statusName(detail.plan.plan_status) }}</span>
    </h3>
    <form v-if="writable" class="form c6" novalidate @submit.prevent="save">
      <label class="field">작업일<input v-model="form.work_dt" type="date" :max="today" /></label>
      <label class="field">누적 진척률(%)<input v-model.number="form.progress_rate" type="number" min="0" max="100" step="1" /></label>
      <label class="field">투입 공수(MH)<input v-model.number="form.man_hour" type="number" step=".5" /></label>
      <label class="field">투입 인원<input v-model.number="form.worker_cnt" type="number" step="1" /></label>
      <label class="field">작업자
        <select v-model="form.worker_emp_no">
          <option value="">-</option>
          <option v-for="u in users" :key="u.emp_no" :value="u.emp_no">{{ u.display_name }} ({{ u.emp_no }})</option>
        </select>
      </label>
      <div><button type="submit" class="btn pri" :disabled="busy">실적 저장</button></div>
      <label class="field">비고<input v-model="form.remark" maxlength="1000" /></label>
    </form>
    <h3 class="htitle">실적 이력</h3>
    <div class="tw">
      <table class="table">
        <thead>
          <tr><th>작업일</th><th>누적 진척률</th><th class="num">공수</th><th class="num">인원</th><th>작업자</th><th>비고</th><th v-if="writable"></th></tr>
        </thead>
        <tbody>
          <tr v-for="h in detail.history" :key="h.progress_id">
            <td>{{ h.work_dt }}</td>
            <td>{{ h.progress_rate }}%</td>
            <td class="num">{{ dash(h.man_hour) }}</td>
            <td class="num">{{ dash(h.worker_cnt) }}</td>
            <td>{{ h.worker_nm ?? '-' }}</td>
            <td class="wrap">{{ h.remark }}</td>
            <td v-if="writable"><button type="button" class="btn sm danger" :disabled="busy" @click="remove(h)">삭제</button></td>
          </tr>
          <tr v-if="!detail.history.length"><td :colspan="writable ? 7 : 6" class="muted">실적 이력이 없습니다.</td></tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.chk {
  display: flex;
  align-items: center;
  gap: 6px;
}
.prog {
  width: 250px;
}
.hint {
  margin: 12px 0;
}
.detail {
  margin-top: 12px;
}
.htitle {
  margin-top: 14px !important;
}
</style>
