<script>
// 겹친 모달에서 Esc는 맨 위 하나만 닫는다.
const stack = []
</script>

<script setup>
import { onBeforeUnmount, onMounted, watch } from 'vue'
import { tabs } from '../stores/tabs.js'

defineProps({ title: { type: String, required: true }, size: { type: String, default: '' } })
const emit = defineEmits(['close'])

const self = {}
const close = () => emit('close')
const onKey = (e) => {
  if (e.key === 'Escape' && stack.at(-1) === self) close()
}

watch(() => tabs.navCount, close)
onMounted(() => {
  stack.push(self)
  document.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  stack.splice(stack.indexOf(self), 1)
  document.removeEventListener('keydown', onKey)
})
</script>

<template>
  <Teleport to="body">
    <div class="modal-back" @click.self="close">
      <div class="modal" :class="size" role="dialog" aria-modal="true" :aria-label="title">
        <header class="modal-head">
          <span>{{ title }}</span>
          <button type="button" class="btn sm" @click="close">닫기 ✕</button>
        </header>
        <div class="modal-body"><slot /></div>
      </div>
    </div>
  </Teleport>
</template>
