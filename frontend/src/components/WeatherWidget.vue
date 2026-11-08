<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { api } from '../api/client.js'

const REGIONS = ['울산', '거제', '목포']
const STORAGE_KEY = 'swp_region'
const REFRESH_MS = 10 * 60 * 1000
const ICONS = [['맑', '☀️'], ['구름', '⛅'], ['흐', '☁️'], ['눈', '❄️'], ['비', '🌧️']]

const stored = localStorage.getItem(STORAGE_KEY)
const region = ref(REGIONS.includes(stored) ? stored : REGIONS[0])
const weather = ref(null)
const failed = ref(false)
let latest = 0 // 지역 변경·해제 뒤 늦게 온 응답을 버린다

const icon = computed(() => ICONS.find(([word]) => weather.value?.condition.includes(word))?.[1] ?? '🌤️')

async function load() {
  const id = ++latest
  weather.value = null
  failed.value = false
  try {
    const data = await api('/api/weather', { params: { region: region.value } })
    if (id === latest) weather.value = data
  } catch {
    if (id === latest) failed.value = true
  }
}

function changeRegion() {
  localStorage.setItem(STORAGE_KEY, region.value)
  load()
}

load()
const timer = setInterval(load, REFRESH_MS)
onBeforeUnmount(() => {
  latest++
  clearInterval(timer)
})
</script>

<template>
  <div class="weather">
    <select v-model="region" aria-label="지역" @change="changeRegion">
      <option v-for="r in REGIONS" :key="r" :value="r">{{ r }}</option>
    </select>
    <template v-if="weather">
      <span>{{ icon }}</span>
      <b class="temp">{{ weather.tempC }}℃</b>
      <span>{{ weather.condition }}</span>
      <span>습도 {{ weather.humidity }}% · 바람 {{ weather.windMs }}m/s</span>
      <span class="wbadge" :class="weather.source">{{ weather.source === 'LIVE' ? 'LIVE' : '샘플' }}</span>
    </template>
    <span v-else>{{ failed ? '날씨 조회 실패' : '날씨 조회 중…' }}</span>
  </div>
</template>
