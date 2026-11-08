<script setup>
import { computed } from 'vue'
import { canWrite, menuOf } from '../stores/session.js'

const props = defineProps({ token: { type: String, required: true }, desc: { type: String, default: '' }, title: { type: String, default: '' } })
const heading = computed(() => props.title || menuOf(props.token)?.title)
</script>

<template>
  <div class="ph">
    <h2>{{ heading }}</h2>
    <span v-if="desc" class="ph-desc">{{ desc }}</span>
    <span v-if="!canWrite(token)" class="badge readonly">조회 전용</span>
    <slot />
  </div>
</template>
