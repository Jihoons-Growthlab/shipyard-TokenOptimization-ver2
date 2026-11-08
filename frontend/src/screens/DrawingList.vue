<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api/client.js'
import PageHeader from '../components/PageHeader.vue'
import DrawingDetailModal from '../components/DrawingDetailModal.vue'
import DrawingNewModal from '../components/DrawingNewModal.vue'
import { canWrite, codeName, loadCodes } from '../stores/session.js'
import { toast } from '../stores/toast.js'

const props = defineProps({
  token: { type: String, required: true },
  param: { type: String, default: null },
  nonce: { type: Number, default: 0 },
})

const EMPTY = { hull_no: '', discipline: '', status: '', q: '' }
const codes = ref({})
const hulls = ref([])
const users = ref([])
const filter = reactive({ ...EMPTY })
const rows = ref([])
const selected = ref(null)
const detail = ref(null)
const creating = ref(false)
let seq = 0

async function search() {
  const mine = ++seq
  const params = Object.fromEntries(Object.entries(filter).filter(([, v]) => v))
  try {
    const data = await api('/api/drawings', { params })
    if (mine === seq) rows.value = data
  } catch (e) {
    if (mine === seq) toast.error(e.message)
  }
}

function reset() {
  Object.assign(filter, EMPTY)
  search()
}

function applyParam() {
  if (props.param) Object.assign(filter, { ...EMPTY, hull_no: props.param })
  search()
}

function created(id) {
  creating.value = false
  search()
  detail.value = id
}

watch(() => props.nonce, applyParam)
onMounted(async () => {
  applyParam()
  const [c, h, u] = await Promise.all([
    loadCodes().catch(() => ({})),
    api('/api/hulls').catch(() => []),
    api('/api/users/options').catch(() => []),
  ])
  codes.value = c
  hulls.value = h
  users.value = u
})
</script>

<template>
  <PageHeader
    :token="token"
    desc="행 더블클릭 또는 [상세]로 도면 상세·PDF 뷰어·리비전·결재 팝업을 엽니다. Rev는 현재 배포(유효) 리비전입니다."
  />
  <div class="bar">
    <select v-model="filter.hull_no" class="hull" aria-label="호선">
      <option value="">호선 전체</option>
      <option v-for="h in hulls" :key="h.hull_no" :value="h.hull_no">{{ h.hull_no }} {{ h.hull_nm }}</option>
    </select>
    <select v-model="filter.discipline" aria-label="분야">
      <option value="">분야 전체</option>
      <option v-for="c in codes.DWGDISC" :key="c.code" :value="c.code">{{ c.name }}</option>
    </select>
    <select v-model="filter.status" aria-label="상태">
      <option value="">상태 전체</option>
      <option v-for="c in codes.DWGSTAT" :key="c.code" :value="c.code">{{ c.name }}</option>
    </select>
    <input v-model="filter.q" class="q" placeholder="도면번호/도면명" @keyup.enter="search" />
    <button type="button" class="btn pri" @click="search">조회</button>
    <button type="button" class="btn" @click="reset">초기화</button>
    <button v-if="canWrite(token)" type="button" class="btn pri add" @click="creating = true">+ 도면 등록</button>
  </div>
  <div class="tw">
    <table class="table">
      <thead>
        <tr><th>도면번호</th><th>도면명</th><th>호선</th><th>블록</th><th>분야</th><th>Rev</th><th>상태</th><th>설계자</th><th>연계공정</th><th></th></tr>
      </thead>
      <tbody>
        <tr
          v-for="r in rows"
          :key="r.drawing_id"
          :class="{ sel: selected === r.drawing_id }"
          @click="selected = r.drawing_id"
          @dblclick="detail = r.drawing_id"
        >
          <td><b>{{ r.drawing_no }}</b></td>
          <td>{{ r.drawing_nm }}</td>
          <td>{{ r.hull_no }}</td>
          <td>{{ r.block_cd || '-' }}</td>
          <td>{{ codeName(codes, 'DWGDISC', r.discipline) }}</td>
          <td>
            Rev{{ r.current_rev_no }}<span v-if="r.latest_rev_no !== r.current_rev_no" class="muted"> (최신 Rev{{ r.latest_rev_no }})</span>
          </td>
          <td><span class="badge" :class="r.dwg_status">{{ codeName(codes, 'DWGSTAT', r.dwg_status) }}</span></td>
          <td>{{ r.designer_nm || '-' }}</td>
          <td class="num">{{ r.link_count || '-' }}</td>
          <td><button type="button" class="btn sm" @click.stop="detail = r.drawing_id">상세</button></td>
        </tr>
        <tr v-if="!rows.length"><td colspan="10" class="muted">조회된 도면이 없습니다.</td></tr>
      </tbody>
    </table>
  </div>
  <p class="count muted">총 {{ rows.length }}건</p>
  <DrawingNewModal v-if="creating" :hulls="hulls" :users="users" :codes="codes" @created="created" @close="creating = false" />
  <DrawingDetailModal v-if="detail" :key="detail" :drawing-id="detail" @changed="search" @close="detail = null" />
</template>

<style scoped>
.bar {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}
.bar select {
  width: 110px;
}
.bar .hull {
  width: 166px;
}
.q {
  width: 148px;
}
.add {
  margin-left: auto;
}
.count {
  margin: 6px 0 0;
  font-size: 12px;
}
</style>
