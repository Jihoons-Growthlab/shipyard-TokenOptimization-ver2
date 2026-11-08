<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api/client.js'
import BaseModal from './BaseModal.vue'
import DrawingFields from './DrawingFields.vue'
import { RESULT, STEP_NAME, checkPdf, uploadPdf } from '../drawing.js'
import { canWrite, codeName, loadCodes } from '../stores/session.js'
import { navigate } from '../stores/tabs.js'
import { toast } from '../stores/toast.js'

const props = defineProps({ drawingId: { type: Number, required: true } })
const emit = defineEmits(['close', 'changed'])

const writable = canWrite('dwg-list')
const codes = ref({})
const hulls = ref([])
const users = ref([])
const d = ref(null)
const form = reactive({ drawing_no: '', discipline: null, drawing_nm: '', hull_no: null, block_id: null, designer_emp_no: null })
const viewRev = ref(null)
const blobUrl = ref(null)
const busy = ref(false)
const newRev = reactive({ change_desc: '', file: null })
const approval = reactive({ reviewer_emp_no: '', approver_emp_no: '' })
const link = reactive({ plan_id: '', required: true })
const viewerInput = ref(null)
const newRevInput = ref(null)
let pdfSeq = 0

const base = () => `/api/drawings/${props.drawingId}`
const latest = computed(() => d.value?.revisions[0] ?? null)
const shown = computed(() => d.value?.revisions.find((r) => r.rev_no === viewRev.value) ?? null)
const dwgName = (code) => codeName(codes.value, 'DWGSTAT', code)
const impact = computed(() => {
  const items = d.value?.impacts ?? []
  return items.length ? { rev: items[0].rev_no, date: items[0].issue_dt, labels: items.map((i) => i.plan_label) } : null
})

async function load() {
  try {
    const data = await api(base())
    d.value = data
    Object.assign(form, Object.fromEntries(Object.keys(form).map((k) => [k, data[k]])))
    if (!data.revisions.some((r) => r.rev_no === viewRev.value)) viewRev.value = data.revisions[0]?.rev_no ?? null
  } catch (e) {
    toast.error(e.message)
    if (e.status === 404) emit('close')
  }
}

function setBlob(url) {
  if (blobUrl.value) URL.revokeObjectURL(blobUrl.value)
  blobUrl.value = url
}

// 인증 헤더가 필요하므로 iframe에 API 주소를 직접 넣지 않고 blob으로 받는다.
async function loadPdf() {
  const mine = ++pdfSeq
  const rev = shown.value
  if (!rev?.has_file) return setBlob(null)
  try {
    const blob = await api(`${base()}/revisions/${rev.rev_no}/pdf`, { blob: true })
    if (mine === pdfSeq) setBlob(URL.createObjectURL(blob))
  } catch (e) {
    if (mine === pdfSeq) setBlob(null)
    toast.error(e.message)
  }
}
watch(shown, loadPdf)

function openWindow() {
  if (!blobUrl.value) return toast.error('표시 중인 PDF가 없습니다.')
  window.open(blobUrl.value, '_blank')
}

async function run(action, after = load) {
  busy.value = true
  try {
    await action()
    emit('changed')
    await after()
  } catch (e) {
    toast.error(e.message)
    await load()
  } finally {
    busy.value = false
  }
}

function pickedPdf(input) {
  const file = input.files[0] ?? null
  const error = file && checkPdf(file)
  if (error) {
    toast.error(error)
    input.value = ''
    return null
  }
  return file
}

function uploadShown(e) {
  const file = pickedPdf(e.target)
  e.target.value = ''
  if (!file) return
  const rev = shown.value.rev_no
  run(async () => {
    await uploadPdf(props.drawingId, rev, file)
    toast.success(`Rev${rev}에 PDF를 업로드했습니다.`)
  })
}

const deleteFile = () =>
  run(async () => {
    await api(`${base()}/revisions/${shown.value.rev_no}/pdf`, { method: 'DELETE' })
    toast.success('파일을 삭제했습니다.')
  })

const save = () =>
  run(async () => {
    const { drawing_nm, discipline, block_id, designer_emp_no } = form
    await api(base(), { method: 'PATCH', body: { drawing_nm, discipline, block_id, designer_emp_no } })
    toast.success('저장되었습니다.')
  })

function remove() {
  if (!confirm('도면과 리비전·결재·공정 연계를 삭제합니다.')) return
  run(
    async () => {
      await api(base(), { method: 'DELETE' })
      toast.success('삭제되었습니다.')
    },
    async () => emit('close'),
  )
}

const createRev = () =>
  run(async () => {
    const data = await api(`${base()}/revisions`, { method: 'POST', body: { change_desc: newRev.change_desc } })
    const rev = data.revisions[0].rev_no
    viewRev.value = rev
    toast.success(`Rev${rev} 작성중으로 생성되었습니다.`)
    if (newRev.file) await uploadPdf(props.drawingId, rev, newRev.file).catch((e) => toast.error(`PDF 저장 실패: ${e.message}`))
    Object.assign(newRev, { change_desc: '', file: null })
    if (newRevInput.value) newRevInput.value.value = ''
  })

const requestApproval = () =>
  run(async () => {
    await api(`${base()}/revisions/${latest.value.rev_no}/request-approval`, { method: 'POST', body: { ...approval } })
    toast.success('결재가 요청되었습니다.')
  })

const issue = () =>
  run(async () => {
    await api(`${base()}/revisions/${latest.value.rev_no}/issue`, { method: 'POST' })
    toast.success('도면이 배포되었습니다. 연계 공정 상태가 갱신됩니다.')
  })

function addLink() {
  if (!link.plan_id) return toast.error('공정을 선택하세요.')
  run(async () => {
    await api(`${base()}/plans`, { method: 'POST', body: { ...link } })
    Object.assign(link, { plan_id: '', required: true })
    toast.success('공정이 연계되었습니다.')
  })
}

const removeLink = (p) =>
  run(async () => {
    await api(`${base()}/plans/${p.plan_id}`, { method: 'DELETE' })
    toast.success('연계가 해제되었습니다.')
  })

onMounted(async () => {
  load()
  const [c, h, u] = await Promise.all([
    loadCodes().catch(() => ({})),
    api('/api/hulls').catch(() => []),
    api('/api/users/options').catch(() => []),
  ])
  codes.value = c
  hulls.value = h
  users.value = u
  const has = (emp) => (u.some((x) => x.emp_no === emp) ? emp : '')
  Object.assign(approval, { reviewer_emp_no: has('lee.dwg'), approver_emp_no: has('admin') })
})
onBeforeUnmount(() => {
  pdfSeq++
  setBlob(null)
})
</script>

<template>
  <BaseModal :title="`도면 ${d?.drawing_no ?? ''}`" size="xl" @close="emit('close')">
    <div v-if="d" class="dd">
      <section class="card viewer">
        <h3>도면 뷰어 (PDF) <small class="muted">작성중(DRAFT) 리비전만 업로드·교체·삭제할 수 있습니다.</small></h3>
        <div class="tools">
          <select v-model="viewRev" aria-label="리비전" class="revsel">
            <option v-for="r in d.revisions" :key="r.rev_no" :value="r.rev_no">Rev{{ r.rev_no }} ({{ dwgName(r.rev_status) }})</option>
          </select>
          <span class="fname">{{ shown?.file_nm || '파일 없음' }}</span>
          <span v-if="shown?.has_file" class="badge ok">업로드 파일</span>
          <span v-else class="badge warn">샘플 PDF (미업로드)</span>
          <span class="grow" />
          <template v-if="writable">
            <input ref="viewerInput" type="file" class="finput" accept=".pdf,application/pdf" aria-label="PDF 업로드"
                   :disabled="busy || shown?.rev_status !== 'DRAFT'" @change="uploadShown" />
            <button type="button" class="btn" :disabled="busy || shown?.rev_status !== 'DRAFT' || !shown?.has_file" @click="deleteFile">파일 삭제</button>
          </template>
          <button type="button" class="btn" @click="openWindow">새 창으로 열기</button>
        </div>
        <div class="vbody">
          <iframe v-if="blobUrl" :src="`${blobUrl}#view=FitH`" title="도면 PDF" />
          <div v-else-if="shown" class="sample">
            <b>샘플 PDF (미업로드)</b>
            <span>{{ d.drawing_no }} · Rev{{ shown.rev_no }} · {{ dwgName(shown.rev_status) }}</span>
            <small>이 리비전에는 업로드된 도면 파일이 없습니다.</small>
          </div>
        </div>
      </section>

      <div class="rcol">
        <p class="meta muted">{{ d.hull_no }} · {{ codeName(codes, 'DWGDISC', d.discipline) }} · {{ d.drawing_nm }}</p>

        <form class="card" novalidate @submit.prevent="save">
          <h3>도면 정보</h3>
          <fieldset class="form c2" :disabled="!writable">
            <DrawingFields :form="form" :hulls="hulls" :users="users" :codes="codes" existing />
          </fieldset>
          <div v-if="writable" class="actions">
            <button type="submit" class="btn pri" :disabled="busy">저장</button>
            <button type="button" class="btn danger" :disabled="busy" @click="remove">삭제</button>
          </div>
        </form>

        <section class="card">
          <h3>리비전 이력 <span class="badge">{{ d.revisions.length }}</span></h3>
          <div class="tw revs">
            <table class="table fixed">
              <colgroup><col style="width: 92px" /><col style="width: 62px" /><col /><col style="width: 92px" /></colgroup>
              <thead><tr><th>Rev</th><th>상태</th><th>변경사유</th><th>배포일</th></tr></thead>
              <tbody>
                <tr v-for="r in d.revisions" :key="r.rev_no" :class="{ sel: r.rev_no === viewRev }">
                  <td><b>Rev{{ r.rev_no }}</b> <a href="#" class="link" @click.prevent="viewRev = r.rev_no">보기</a></td>
                  <td><span class="badge" :class="r.rev_status">{{ dwgName(r.rev_status) }}</span></td>
                  <td class="cut">
                    <div class="cut">{{ r.change_desc }}</div>
                    <small class="muted cut" :title="r.file_nm || ''">{{ r.file_nm || '파일 없음' }}{{ r.file_nm && !r.has_file ? ' (미업로드)' : '' }}</small>
                  </td>
                  <td>{{ r.issue_dt || '미배포' }}<br /><small class="muted">{{ r.author_nm }}</small></td>
                </tr>
              </tbody>
            </table>
          </div>

          <template v-if="writable && latest">
            <form v-if="['ISSUED', 'OBSOLETE'].includes(latest.rev_status)" class="op" novalidate @submit.prevent="createRev">
              <label class="field">신규 Rev{{ latest.rev_no + 1 }} 개정 사유<input v-model="newRev.change_desc" maxlength="1000" /></label>
              <div class="row">
                <label class="field grow">도면 파일 (PDF, 선택)
                  <input ref="newRevInput" type="file" accept=".pdf,application/pdf" @change="newRev.file = pickedPdf($event.target)" />
                </label>
                <button type="submit" class="btn pri" :disabled="busy">신규 Rev 작성</button>
              </div>
            </form>
            <form v-else-if="latest.rev_status === 'DRAFT'" class="op" novalidate @submit.prevent="requestApproval">
              <div class="note warn">Rev{{ latest.rev_no }} 작성중입니다. 검토자/승인자를 지정해 결재를 요청하세요.</div>
              <div class="form c2">
                <label class="field">1단계 검토자
                  <select v-model="approval.reviewer_emp_no">
                    <option value="">선택</option>
                    <option v-for="u in users" :key="u.emp_no" :value="u.emp_no">{{ u.display_name }} ({{ u.emp_no }})</option>
                  </select>
                </label>
                <label class="field">2단계 승인자
                  <select v-model="approval.approver_emp_no">
                    <option value="">선택</option>
                    <option v-for="u in users" :key="u.emp_no" :value="u.emp_no">{{ u.display_name }} ({{ u.emp_no }})</option>
                  </select>
                </label>
              </div>
              <div><button type="submit" class="btn pri" :disabled="busy">결재 요청</button></div>
            </form>
            <div v-else-if="latest.rev_status === 'REVIEW'" class="op note warn">
              Rev{{ latest.rev_no }} 결재 진행중입니다. 결재자는 [결재함]에서 처리합니다.
            </div>
            <div v-else-if="latest.rev_status === 'APPROVED'" class="op">
              <div class="note ok">Rev{{ latest.rev_no }} 승인 완료 — 배포하면 연계 공정의 도면 게이트가 열립니다.</div>
              <div><button type="button" class="btn ok" :disabled="busy" @click="issue">Rev{{ latest.rev_no }} 배포</button></div>
            </div>
          </template>
        </section>

        <section class="card">
          <h3>결재 이력</h3>
          <div class="tw">
            <table class="table">
              <thead><tr><th>Rev</th><th>단계</th><th>결재자</th><th>결과</th></tr></thead>
              <tbody>
                <tr v-for="a in d.approvals" :key="a.approval_id" :title="`의견: ${a.comment ?? '-'}\n일시: ${a.act_dt ?? '-'}`">
                  <td>Rev{{ a.rev_no }}</td>
                  <td>{{ STEP_NAME[a.step_no] }}</td>
                  <td>{{ a.approver_nm }}</td>
                  <td><span class="badge" :class="RESULT[a.result][1]">{{ RESULT[a.result][0] }}</span></td>
                </tr>
                <tr v-if="!d.approvals.length"><td colspan="4" class="empty muted">결재 이력이 없습니다.</td></tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="card">
          <h3>연계 공정 <span class="badge">{{ d.plans.length }}</span></h3>
          <div v-if="impact" class="note warn imp">
            ⚠ 최근 개정(Rev{{ impact.rev }}, {{ impact.date }})으로 이미 착수·완료된 공정 {{ impact.labels.length }}건이 영향을 받습니다: {{ impact.labels.join(', ') }}
          </div>
          <div class="tw">
            <table class="table">
              <thead><tr><th>공정</th><th>상태</th><th>필수</th><th>필요일</th><th v-if="writable"></th></tr></thead>
              <tbody>
                <tr v-for="p in d.plans" :key="p.plan_id">
                  <td><a href="#" class="link" @click.prevent="navigate('plan-gantt', d.hull_no)">{{ p.label }}</a></td>
                  <td><span class="badge" :class="p.plan_status">{{ codeName(codes, 'PLANSTAT', p.plan_status) }}</span></td>
                  <td>{{ p.required ? '필수' : '참고' }}</td>
                  <td>{{ p.need_dt || '-' }}</td>
                  <td v-if="writable"><button type="button" class="btn sm danger" :disabled="busy" @click="removeLink(p)">해제</button></td>
                </tr>
                <tr v-if="!d.plans.length"><td :colspan="writable ? 5 : 4" class="empty muted">연계된 공정이 없습니다.</td></tr>
              </tbody>
            </table>
          </div>
          <div v-if="writable" class="row linkadd">
            <select v-model="link.plan_id" class="grow" aria-label="공정 선택">
              <option value="">공정 선택</option>
              <option v-for="p in d.available_plans" :key="p.plan_id" :value="p.plan_id">{{ p.label }}</option>
            </select>
            <label class="chk"><input v-model="link.required" type="checkbox" /> 필수</label>
            <button type="button" class="btn" :disabled="busy" @click="addLink">+ 공정 연계</button>
          </div>
        </section>
      </div>
    </div>
  </BaseModal>
</template>

<style scoped>
.dd {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 440px;
  gap: 12px;
  height: 100%;
  min-height: 0;
}
.viewer {
  display: flex;
  flex-direction: column;
  min-height: 0;
  margin: 0;
}
.viewer h3 small {
  font-size: 12px;
  font-weight: 400;
}
.tools,
.row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.tools {
  margin-bottom: 10px;
}
.revsel {
  width: 110px;
}
.fname {
  white-space: nowrap;
}
.grow {
  flex: 1;
  min-width: 0;
}
.finput {
  width: 230px;
}
.vbody {
  display: flex;
  flex: 1;
  align-items: center;
  justify-content: center;
  min-height: 0;
  border-radius: 6px;
  background: #525659;
  overflow: hidden;
}
.vbody iframe {
  width: 100%;
  height: 100%;
  border: 0;
}
.sample {
  display: grid;
  gap: 8px;
  color: #fff;
  text-align: center;
}
.rcol {
  min-height: 0;
  overflow: auto;
}
.meta {
  margin: 0 0 8px;
  font-size: 12px;
}
fieldset {
  margin: 0;
  padding: 0;
  border: 0;
  min-width: 0;
}
.fixed {
  table-layout: fixed;
}
.revs {
  max-height: 190px;
}
.cut {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
small.cut {
  display: block;
  font-size: 11.5px;
}
.op {
  display: grid;
  gap: 10px;
  margin-top: 10px;
}
.row {
  align-items: end;
}
.empty {
  text-align: center;
}
.imp {
  margin-bottom: 8px;
}
.linkadd {
  align-items: center;
  margin-top: 8px;
}
.chk {
  display: flex;
  gap: 4px;
  white-space: nowrap;
}
@media (max-width: 1100px) {
  .dd {
    grid-template-columns: 1fr;
    height: auto;
  }
  .viewer {
    height: 60vh;
  }
  .rcol {
    overflow: visible;
  }
}
</style>
