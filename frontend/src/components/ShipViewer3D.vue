<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import ProgressBar from './ProgressBar.vue'
import { firstLine, startViewer } from '../shipViewer.js'

const VIEWS = [
  ['front', '정면'],
  ['side', '측면'],
  ['top', '상단'],
  ['reset', '초기화'],
]
const GUIDE = [
  ['왼쪽 드래그', '회전'],
  ['휠', '확대·축소'],
  ['오른쪽 드래그', '화면 이동'],
]

const key = ref(0)
const canvas = ref(null)
const state = ref('loading')
const progress = ref(0)
const error = ref('')
let session = null

async function start() {
  state.value = 'loading'
  progress.value = 0
  await nextTick()
  if (!canvas.value) return
  const s = (session = startViewer(canvas.value, (p) => s === session && (progress.value = Math.round(p * 100))))
  try {
    await s.ready
    if (s === session) state.value = 'ready'
  } catch (e) {
    if (s !== session) return
    state.value = 'error'
    error.value = firstLine(e)
  }
}

function stop() {
  session?.close()
  session = null
}

// 재시도는 새 canvas로 시작한다.
function retry() {
  stop()
  key.value++
  start()
}

onMounted(start)
onBeforeUnmount(stop)
</script>

<template>
  <div class="v3d">
    <div class="viewer" @contextmenu.prevent>
      <canvas :id="`ship-viewer-${key}`" :key="key" ref="canvas" tabindex="-1" />
      <div v-if="state === 'loading'" class="cover">
        <p>3D 뷰어 불러오는 중…</p>
        <ProgressBar :value="progress" />
      </div>
      <div v-else-if="state === 'error'" class="cover" role="alert">
        <b>3D 뷰어를 불러오지 못했습니다.</b>
        <p class="muted">{{ error }}</p>
        <button type="button" class="btn" @click="retry">재시도</button>
      </div>
    </div>
    <aside>
      <section class="card">
        <h3>샘플 호선 3D 뷰어</h3>
        <p class="name">Demo Ship 01</p>
        <p class="note warn">예시 모델 — 실제 호선 형상과 다름</p>
      </section>
      <section class="card">
        <h3>시점</h3>
        <div class="views">
          <button v-for="[v, label] in VIEWS" :key="v" type="button" class="btn" :disabled="state !== 'ready'" @click="session?.setView(v)">
            {{ label }}
          </button>
        </div>
      </section>
      <section class="card">
        <h3>조작 안내</h3>
        <dl>
          <template v-for="[k, v] in GUIDE" :key="k"><dt>{{ k }}</dt><dd>{{ v }}</dd></template>
        </dl>
      </section>
    </aside>
  </div>
</template>

<style scoped>
.v3d {
  display: grid;
  grid-template-columns: 1fr 260px;
  gap: 12px;
  height: calc(94vh - 148px);
  min-height: 360px;
}
.viewer {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #dde4ee;
}
canvas {
  display: block;
  width: 100%;
  height: 100%;
  outline: none;
}
.cover {
  position: absolute;
  inset: 0;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 10px;
  min-width: 0;
  padding: 16px;
  background: #dde4ee;
  text-align: center;
}
.cover p {
  margin: 0;
}
.cover .pbar {
  width: 240px;
}
.name {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 700;
}
.note {
  margin: 0;
}
.views {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
dl {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 6px 28px;
  margin: 0;
  font-size: 12.5px;
}
dd {
  margin: 0;
}
@media (max-width: 760px) {
  .v3d {
    grid-template-columns: 1fr;
    grid-template-rows: minmax(260px, 1fr) auto;
    height: auto;
  }
  .viewer {
    min-height: 260px;
  }
  aside {
    max-height: 40vh;
    overflow: auto;
  }
}
</style>
