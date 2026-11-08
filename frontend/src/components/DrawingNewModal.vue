<script setup>
import { reactive, ref } from 'vue'
import { api } from '../api/client.js'
import BaseModal from './BaseModal.vue'
import DrawingFields from './DrawingFields.vue'
import { checkPdf, uploadPdf } from '../drawing.js'
import { session } from '../stores/session.js'
import { toast } from '../stores/toast.js'

const props = defineProps({
  hulls: { type: Array, default: () => [] },
  users: { type: Array, default: () => [] },
  codes: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['close', 'created'])

const form = reactive({
  drawing_no: '', discipline: props.codes.DWGDISC?.[0]?.code ?? null, drawing_nm: '',
  hull_no: props.hulls[0]?.hull_no ?? null, block_id: null, designer_emp_no: session.me?.emp_no ?? null,
})
const file = ref(null)
const busy = ref(false)

function pick(e) {
  const f = e.target.files[0] ?? null
  const error = f && checkPdf(f)
  if (error) {
    toast.error(error)
    e.target.value = ''
  }
  file.value = error ? null : f
}

async function save() {
  busy.value = true
  try {
    const d = await api('/api/drawings', { method: 'POST', body: { ...form } })
    let note = ''
    if (file.value) {
      try {
        await uploadPdf(d.drawing_id, 0, file.value)
        note = ' PDF 첨부됨.'
      } catch (e) {
        note = ` (PDF 저장 실패: ${e.message})`
      }
    }
    toast.success(`도면이 등록되었습니다. (Rev0 작성중)${note}`)
    emit('created', d.drawing_id)
  } catch (e) {
    toast.error(e.message)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <BaseModal title="도면 등록" size="large" @close="emit('close')">
    <p class="sub muted">신규 도면은 Rev0(작성중)으로 생성됩니다. PDF는 지금 첨부하거나 등록 후 뷰어에서 업로드할 수 있습니다.</p>
    <form class="card" novalidate @submit.prevent="save">
      <div class="form c2">
        <DrawingFields :form="form" :hulls="hulls" :users="users" :codes="codes" />
        <label class="field s2">도면 파일 (PDF, 선택)<input type="file" accept=".pdf,application/pdf" @change="pick" /></label>
      </div>
      <div class="actions"><button type="submit" class="btn pri" :disabled="busy">저장</button></div>
    </form>
  </BaseModal>
</template>

<style scoped>
.sub {
  margin: 0 0 10px;
  font-size: 12px;
}
.s2 {
  grid-column: span 2;
}
</style>
