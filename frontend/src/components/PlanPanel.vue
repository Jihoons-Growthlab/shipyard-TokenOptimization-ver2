<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { api } from '../api/client.js'
import { addDays } from '../gantt.js'
import { codeName } from '../stores/session.js'
import { toast } from '../stores/toast.js'

const props = defineProps({
  hullNo: { type: String, required: true },
  plan: { type: Object, default: null }, // null이면 신규
  plans: { type: Array, default: () => [] },
  blocks: { type: Array, default: () => [] },
  procs: { type: Array, default: () => [] },
  users: { type: Array, default: () => [] },
  codes: { type: Object, default: () => ({}) },
  defaultBlockId: { type: Number, default: null },
  today: { type: String, required: true },
  writable: { type: Boolean, default: false },
})
const emit = defineEmits(['saved', 'deleted', 'changed', 'close', 'open-drawing'])

const form = reactive({})
const linkInfo = ref(null)
const link = reactive({ drawing_id: '', required: true })
const busy = ref(false)
let seq = 0

const predOptions = computed(() => props.plans.filter((p) => p.plan_id !== props.plan?.plan_id))
const dash = (v) => v ?? '-'

function reset() {
  const p = props.plan
  Object.assign(form, {
    block_id: p ? p.block_id : props.defaultBlockId,
    proc_cd: p ? p.proc_cd : 'CUT',
    plan_start_dt: p ? p.plan_start_dt : props.today,
    plan_end_dt: p ? p.plan_end_dt : addDays(props.today, 13),
    manager_emp_no: p?.manager_emp_no ?? '',
    remark: p?.remark ?? '',
    pred_plan_ids: p ? [...p.pred_plan_ids] : [],
  })
  Object.assign(link, { drawing_id: '', required: true })
  loadLinks()
}

async function loadLinks() {
  const mine = ++seq
  linkInfo.value = null
  if (!props.plan) return
  try {
    const data = await api(`/api/plans/${props.plan.plan_id}/drawings`)
    if (mine === seq) linkInfo.value = data
  } catch (e) {
    if (mine === seq) toast.error(e.message)
  }
}

// 다른 공정을 고르거나 저장 후 재조회로 같은 공정이 새 객체가 되면 폼을 다시 채운다.
watch(() => props.plan, reset, { immediate: true })

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

async function send(body) {
  return props.plan
    ? api(`/api/plans/${props.plan.plan_id}`, { method: 'PATCH', body })
    : api(`/api/hulls/${encodeURIComponent(props.hullNo)}/plans`, { method: 'POST', body })
}

const save = () =>
  run(async () => {
    const body = { ...form, block_id: form.block_id || null, manager_emp_no: form.manager_emp_no || null }
    let saved
    try {
      saved = await send(body)
    } catch (e) {
      if (e.code !== 'PRED_LATE_CONFIRM_REQUIRED') throw e
      if (!confirm(e.message)) return
      saved = await send({ ...body, confirm_late_preds: true })
    }
    toast.success('저장되었습니다.')
    emit('saved', saved.plan_id)
  })

const remove = () => {
  if (!confirm('공정을 삭제합니다. (실적·선후행·도면 연계 함께 삭제)')) return
  run(async () => {
    await api(`/api/plans/${props.plan.plan_id}`, { method: 'DELETE' })
    toast.success('삭제되었습니다.')
    emit('deleted')
  })
}

const addLink = () => {
  if (!link.drawing_id) {
    toast.error('도면을 선택하세요.')
    return
  }
  run(async () => {
    await api(`/api/plans/${props.plan.plan_id}/drawings`, { method: 'POST', body: { ...link } })
    toast.success('도면이 연계되었습니다.')
    emit('changed')
  })
}

const removeLink = (l) =>
  run(async () => {
    await api(`/api/plans/${props.plan.plan_id}/drawings/${l.drawing_id}`, { method: 'DELETE' })
    toast.success('연계가 해제되었습니다.')
    emit('changed')
  })
</script>

<template>
  <section class="card panel">
    <h3>
      <span v-if="plan" class="head">
        {{ plan.label }}
        <span class="badge" :class="plan.plan_status">{{ codeName(codes, 'PLANSTAT', plan.plan_status) }}</span>
        <span class="meta">진척 {{ plan.progress_rate }}% · 실제 {{ dash(plan.actual_start_dt) }} ~ {{ dash(plan.actual_end_dt) }}</span>
      </span>
      <span v-else>공정 추가</span>
    </h3>
    <div class="body">
      <form novalidate @submit.prevent="save">
        <div class="form pf">
          <label class="field b">블록
            <select v-model="form.block_id">
              <option :value="null">호선 전체(블록 없음)</option>
              <option v-for="b in blocks" :key="b.block_id" :value="b.block_id">{{ b.block_cd }} {{ b.block_nm ?? '' }}</option>
            </select>
          </label>
          <label class="field p">공정
            <select v-model="form.proc_cd">
              <option v-for="p in procs" :key="p.proc_cd" :value="p.proc_cd">{{ p.proc_nm }}</option>
            </select>
          </label>
          <label class="field">계획 시작<input v-model="form.plan_start_dt" type="date" /></label>
          <label class="field">계획 종료<input v-model="form.plan_end_dt" type="date" /></label>
          <label class="field m">담당자
            <select v-model="form.manager_emp_no">
              <option value="">미지정</option>
              <option v-for="u in users" :key="u.emp_no" :value="u.emp_no">{{ u.display_name }} ({{ u.emp_no }})</option>
            </select>
          </label>
          <label class="field w">선행 공정 (Ctrl 다중선택)
            <select v-model="form.pred_plan_ids" multiple class="tall">
              <option v-for="p in predOptions" :key="p.plan_id" :value="p.plan_id">{{ p.label }}</option>
            </select>
          </label>
          <label class="field w">비고<textarea v-model="form.remark" class="tall" maxlength="1000" /></label>
        </div>
        <div class="actions">
          <button type="submit" class="btn pri" :disabled="!writable || busy">저장</button>
          <button v-if="plan" type="button" class="btn danger" :disabled="!writable || busy" @click="remove">삭제</button>
          <button type="button" class="btn" @click="emit('close')">닫기</button>
        </div>
      </form>

      <div v-if="!plan" class="muted links">저장한 뒤 이 공정에 도면을 연계할 수 있습니다.</div>
      <div v-else class="links">
        <div v-if="linkInfo?.blockers.length" class="note warn">
          📐 도면 대기: 필수 도면 <b>{{ linkInfo.blockers.map((b) => `${b.drawing_no}(${codeName(codes, 'DWGSTAT', b.dwg_status)})`).join(', ') }}</b> 미배포 → 착수 불가
        </div>
        <div class="ltitle"><b>연계 도면</b> (필수 도면은 배포 전 착수 불가)</div>
        <div class="tw r3">
          <table class="table">
            <thead><tr><th>도면번호</th><th>상태</th><th>필수</th><th></th></tr></thead>
            <tbody>
              <tr v-for="l in linkInfo?.links ?? []" :key="l.drawing_id">
                <td><a href="#" class="link" @click.prevent="emit('open-drawing', l.drawing_id)">{{ l.drawing_no }}</a></td>
                <td>
                  <span class="badge" :class="l.dwg_status">{{ codeName(codes, 'DWGSTAT', l.dwg_status) }}</span>
                  <span v-if="!l.has_issued" class="badge warn">미배포</span>
                </td>
                <td>{{ l.required ? '필수' : '참고' }}</td>
                <td><button type="button" class="btn sm danger" :disabled="!writable || busy" @click="removeLink(l)">해제</button></td>
              </tr>
              <tr v-if="linkInfo && !linkInfo.links.length"><td colspan="4" class="muted">연계된 도면이 없습니다.</td></tr>
            </tbody>
          </table>
        </div>
        <div class="linkadd">
          <select v-model="link.drawing_id" aria-label="도면 선택">
            <option value="">도면 선택</option>
            <option v-for="d in linkInfo?.available ?? []" :key="d.drawing_id" :value="d.drawing_id">{{ d.drawing_no }} {{ d.drawing_nm }}</option>
          </select>
          <label class="chk"><input v-model="link.required" type="checkbox" /> 필수</label>
          <button type="button" class="btn" :disabled="!writable || busy" @click="addLink">+ 연계</button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.panel {
  flex: none;
  margin: 10px 0 0;
}
.head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.meta {
  color: var(--muted);
  font-weight: 400;
  font-size: 13px;
}
.body {
  display: grid;
  grid-template-columns: 1fr 430px;
  gap: 16px;
}
.pf {
  grid-template-columns: repeat(6, 1fr);
}
.b {
  grid-column: span 2;
}
.w {
  grid-column: span 3;
}
.tall {
  height: 66px;
  resize: vertical;
}
.links {
  min-width: 0;
}
.links .note {
  margin-bottom: 6px;
}
.ltitle {
  margin-bottom: 6px;
  color: var(--muted);
}
.ltitle b {
  color: var(--ink);
}
.linkadd {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}
.linkadd select {
  flex: 1;
  min-width: 0;
}
.chk {
  display: flex;
  align-items: center;
  gap: 4px;
}
@media (max-width: 1560px) {
  .pf {
    grid-template-columns: repeat(4, 1fr);
  }
  .p,
  .m,
  .w {
    grid-column: span 2;
  }
}
@media (max-width: 720px) {
  .body,
  .pf {
    grid-template-columns: 1fr 1fr;
  }
  .body {
    grid-template-columns: 1fr;
  }
}
</style>
