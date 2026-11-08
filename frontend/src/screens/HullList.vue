<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api } from '../api/client.js'
import PageHeader from '../components/PageHeader.vue'
import ProgressBar from '../components/ProgressBar.vue'
import HullDetailModal from '../components/HullDetailModal.vue'
import { canWrite, codeName, loadCodes } from '../stores/session.js'
import { toast } from '../stores/toast.js'

const props = defineProps({ token: { type: String, required: true } })

const codes = ref({})
const filter = reactive({ status: '', ship_type: '', q: '' })
const rows = ref([])
const selected = ref(null)
// undefined: 닫힘, null: 신규, 문자열: 해당 호선
const detail = ref(undefined)
let seq = 0

async function search() {
  const mine = ++seq
  const params = Object.fromEntries(Object.entries(filter).filter(([, v]) => v))
  try {
    const data = await api('/api/hulls', { params })
    if (mine === seq) rows.value = data
  } catch (e) {
    if (mine === seq) toast.error(e.message)
  }
}

function reset() {
  Object.assign(filter, { status: '', ship_type: '', q: '' })
  search()
}

onMounted(async () => {
  search()
  codes.value = await loadCodes().catch(() => ({}))
})
</script>

<template>
  <PageHeader :token="token" desc="행을 더블클릭하거나 [상세]를 누르면 호선 상세 팝업이 열립니다." />
  <div class="bar">
    <select v-model="filter.status" aria-label="상태">
      <option value="">상태 전체</option>
      <option v-for="c in codes.HULLSTAT" :key="c.code" :value="c.code">{{ c.name }}</option>
    </select>
    <select v-model="filter.ship_type" aria-label="선종">
      <option value="">선종 전체</option>
      <option v-for="c in codes.SHIPTYPE" :key="c.code" :value="c.code">{{ c.name }}</option>
    </select>
    <input v-model="filter.q" class="q" placeholder="호선번호/호선명/선주" @keyup.enter="search" />
    <button type="button" class="btn pri" @click="search">조회</button>
    <button type="button" class="btn" @click="reset">초기화</button>
    <button v-if="canWrite(props.token)" type="button" class="btn pri add" @click="detail = null">+ 호선 등록</button>
  </div>
  <div class="tw">
    <table class="table">
      <thead>
        <tr>
          <th>호선번호</th><th>호선명</th><th>선종</th><th>상태</th><th>선주</th><th>선급</th><th>도크</th>
          <th>계약일</th><th>인도예정</th><th>진척률</th><th class="num">지연</th><th></th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="h in rows"
          :key="h.hull_no"
          :class="{ sel: selected === h.hull_no }"
          @click="selected = h.hull_no"
          @dblclick="detail = h.hull_no"
        >
          <td><b>{{ h.hull_no }}</b></td>
          <td>{{ h.hull_nm }}</td>
          <td>{{ codeName(codes, 'SHIPTYPE', h.ship_type) }}</td>
          <td><span class="badge info">{{ codeName(codes, 'HULLSTAT', h.hull_status) }}</span></td>
          <td>{{ h.owner_nm }}</td>
          <td>{{ h.class_society }}</td>
          <td>{{ h.dock_no || '-' }}</td>
          <td>{{ h.contract_dt }}</td>
          <td>{{ h.delivery_dt }}</td>
          <td class="prog">
            <ProgressBar v-if="h.progress !== null" :value="h.progress" />
            <span v-else class="muted">계획 없음</span>
          </td>
          <td class="num">{{ h.delay_count || '-' }}</td>
          <td><button type="button" class="btn sm" @click.stop="detail = h.hull_no">상세</button></td>
        </tr>
      </tbody>
    </table>
  </div>
  <p class="count muted">총 {{ rows.length }}척</p>
  <HullDetailModal
    v-if="detail !== undefined"
    :hull-no="detail"
    :codes="codes"
    :writable="canWrite(props.token)"
    @changed="search"
    @close="detail = undefined"
  />
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
.q {
  width: 148px;
}
.add {
  margin-left: auto;
}
.prog {
  width: 150px;
}
.count {
  margin: 6px 0 0;
  font-size: 12px;
}
</style>
