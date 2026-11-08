<script setup>
import { ref, watch } from 'vue'
import { api } from '../api/client.js'
import { toast } from '../stores/toast.js'

// form: drawing_no, discipline, drawing_nm, hull_no, block_id, designer_emp_no
const props = defineProps({
  form: { type: Object, required: true },
  hulls: { type: Array, default: () => [] },
  users: { type: Array, default: () => [] },
  codes: { type: Object, default: () => ({}) },
  existing: { type: Boolean, default: false },
})
const blocks = ref([])

watch(
  () => props.form.hull_no,
  async (hullNo, before) => {
    if (before !== undefined && !props.existing) props.form.block_id = null
    blocks.value = []
    if (!hullNo) return
    try {
      const data = await api(`/api/hulls/${encodeURIComponent(hullNo)}/blocks`)
      if (props.form.hull_no === hullNo) blocks.value = data
    } catch (e) {
      toast.error(e.message)
    }
  },
  { immediate: true },
)
</script>

<template>
  <label class="field">도면번호 *<input v-model.trim="form.drawing_no" :readonly="existing" /></label>
  <label class="field">분야
    <select v-model="form.discipline">
      <option v-for="c in codes.DWGDISC" :key="c.code" :value="c.code">{{ c.name }}</option>
    </select>
  </label>
  <label class="field s2">도면명 *<input v-model="form.drawing_nm" maxlength="200" /></label>
  <label class="field">호선
    <select v-model="form.hull_no" :disabled="existing">
      <option v-for="h in hulls" :key="h.hull_no" :value="h.hull_no">{{ h.hull_no }} {{ h.hull_nm }}</option>
    </select>
  </label>
  <label class="field">블록
    <select v-model="form.block_id">
      <option :value="null">블록 없음</option>
      <option v-for="b in blocks" :key="b.block_id" :value="b.block_id">{{ b.block_cd }} {{ b.block_nm }}</option>
    </select>
  </label>
  <label class="field s2">설계자
    <select v-model="form.designer_emp_no">
      <option :value="null">미지정</option>
      <option v-for="u in users" :key="u.emp_no" :value="u.emp_no">{{ u.display_name }} ({{ u.emp_no }})</option>
    </select>
  </label>
</template>

<style scoped>
.s2 {
  grid-column: span 2;
}
</style>
