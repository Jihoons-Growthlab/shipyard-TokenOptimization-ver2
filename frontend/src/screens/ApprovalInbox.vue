<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api/client.js'
import PageHeader from '../components/PageHeader.vue'
import DrawingDetailModal from '../components/DrawingDetailModal.vue'
import { RESULT, STEP_NAME } from '../drawing.js'
import { canWrite, session } from '../stores/session.js'
import { toast } from '../stores/toast.js'

const props = defineProps({ token: { type: String, required: true }, nonce: { type: Number, default: 0 } })

const inbox = ref({ waiting: [], ready: [], can_issue: false })
const history = ref([])
const comments = reactive({})
const busy = ref(false)
const detail = ref(null)

async function load() {
  try {
    const [box, hist] = await Promise.all([api('/api/approvals/inbox'), api('/api/approvals/history')])
    inbox.value = box
    history.value = hist
  } catch (e) {
    toast.error(e.message)
  }
}

async function run(action) {
  busy.value = true
  try {
    await action()
  } catch (e) {
    toast.error(e.message)
  } finally {
    busy.value = false
    await load() // 실패해도 다시 불러온다
  }
}

function decide(w, result) {
  const comment = (comments[w.approval_id] ?? '').trim()
  if (result === 'REJECT' && !comment) return toast.error('반려 시 의견을 입력하세요.')
  run(async () => {
    await api(`/api/approvals/${w.approval_id}/decision`, { method: 'POST', body: { result, comment } })
    delete comments[w.approval_id]
    toast.success(result === 'APPROVE' ? '승인했습니다.' : '반려했습니다. 도면은 작성중으로 되돌려집니다.')
  })
}

const issue = (r) =>
  run(async () => {
    await api(`/api/drawings/${r.drawing_id}/revisions/${r.rev_no}/issue`, { method: 'POST' })
    toast.success('도면이 배포되었습니다. 연계 공정 상태가 갱신됩니다.')
  })

watch(() => props.nonce, load)
onMounted(load)
</script>

<template>
  <PageHeader :token="token" title="도면 결재함" :desc="`${session.me?.display_name ?? ''} 님의 결재 대기와 배포 대기 도면입니다.`" />

  <section class="card">
    <h3>내 결재 대기 <span class="badge warn">{{ inbox.waiting.length }}</span></h3>
    <div class="tw">
      <table class="table">
        <thead><tr><th>도면번호</th><th>도면명</th><th>Rev</th><th>단계</th><th>변경사유</th><th>의견</th><th></th></tr></thead>
        <tbody>
          <tr v-for="w in inbox.waiting" :key="w.approval_id">
            <td><a href="#" class="link" @click.prevent="detail = w.drawing_id">{{ w.drawing_no }}</a></td>
            <td>{{ w.drawing_nm }}</td>
            <td>Rev{{ w.rev_no }}</td>
            <td>{{ STEP_NAME[w.step_no] }}</td>
            <td class="wrap">{{ w.change_desc }}</td>
            <td><input v-model="comments[w.approval_id]" class="cmt" placeholder="의견 (반려 시 필수)" aria-label="의견" maxlength="1000" /></td>
            <td class="btns">
              <template v-if="canWrite(props.token)">
                <button type="button" class="btn sm ok" :disabled="busy" @click="decide(w, 'APPROVE')">승인</button>
                <button type="button" class="btn sm danger" :disabled="busy" @click="decide(w, 'REJECT')">반려</button>
              </template>
            </td>
          </tr>
          <tr v-if="!inbox.waiting.length"><td colspan="7" class="empty muted">결재 대기 건이 없습니다.</td></tr>
        </tbody>
      </table>
    </div>
  </section>

  <section class="card">
    <h3>배포 대기 (승인 완료) <span class="badge info">{{ inbox.ready.length }}</span></h3>
    <div class="tw">
      <table class="table">
        <thead><tr><th>도면번호</th><th>도면명</th><th>Rev</th><th>배포 시 착수 가능해질 수 있는 공정</th><th></th></tr></thead>
        <tbody>
          <tr v-for="r in inbox.ready" :key="r.drawing_id">
            <td><a href="#" class="link" @click.prevent="detail = r.drawing_id">{{ r.drawing_no }}</a></td>
            <td>{{ r.drawing_nm }}</td>
            <td>Rev{{ r.rev_no }}</td>
            <td class="wrap">{{ r.effect_plans.join(', ') || '-' }}</td>
            <td class="btns">
              <button v-if="inbox.can_issue" type="button" class="btn sm ok" :disabled="busy" @click="issue(r)">배포</button>
            </td>
          </tr>
          <tr v-if="!inbox.ready.length"><td colspan="5" class="empty muted">배포 대기 도면이 없습니다.</td></tr>
        </tbody>
      </table>
    </div>
  </section>

  <section class="card">
    <h3>최근 결재 이력</h3>
    <div class="tw">
      <table class="table">
        <thead><tr><th>일시</th><th>도면번호</th><th>Rev</th><th>단계</th><th>결재자</th><th>결과</th><th>의견</th></tr></thead>
        <tbody>
          <tr v-for="h in history" :key="h.approval_id">
            <td>{{ h.act_dt }}</td>
            <td>{{ h.drawing_no }}</td>
            <td>Rev{{ h.rev_no }}</td>
            <td>{{ STEP_NAME[h.step_no] }}</td>
            <td>{{ h.approver_nm }}</td>
            <td><span class="badge" :class="RESULT[h.result][1]">{{ RESULT[h.result][0] }}</span></td>
            <td class="wrap">{{ h.comment }}</td>
          </tr>
          <tr v-if="!history.length"><td colspan="7" class="empty muted">결재 이력이 없습니다.</td></tr>
        </tbody>
      </table>
    </div>
  </section>
  <DrawingDetailModal v-if="detail" :key="detail" :drawing-id="detail" @changed="load" @close="detail = null" />
</template>

<style scoped>
.cmt {
  width: 148px;
}
.btns {
  width: 1%;
  text-align: right;
}
.btns .btn + .btn {
  margin-left: 4px;
}
.empty {
  text-align: center;
}
</style>
