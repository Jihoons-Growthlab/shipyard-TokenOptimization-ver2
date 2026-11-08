<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import SideMenu from '../components/SideMenu.vue'
import TabBar from '../components/TabBar.vue'
import WeatherWidget from '../components/WeatherWidget.vue'
import { screens } from '../screens/index.js'
import { loadSession, logout, session } from '../stores/session.js'
import { restoreTabs, tabs } from '../stores/tabs.js'

const router = useRouter()
const ready = ref(false)
const error = ref('')

const groups = computed(() => session.me?.groups.map((g) => g.name).join(', '))

onMounted(async () => {
  try {
    await loadSession()
    restoreTabs()
    ready.value = true
  } catch (e) {
    error.value = e.message
  }
})

function onLogout() {
  logout()
  router.replace('/login')
}
</script>

<template>
  <div v-if="ready && session.me" class="shell">
    <header class="top">
      <div class="brand">⚓ SWP 조선소 통합관리</div>
      <span class="brand-sub">호선 / 공정 / 도면</span>
      <div class="top-right">
        <WeatherWidget />
        <div class="who">
          <b>{{ session.me.display_name }} 님</b>
          <small>{{ groups }} · {{ session.me.today }}</small>
        </div>
        <button type="button" class="top-btn" @click="onLogout">로그아웃</button>
      </div>
    </header>
    <div class="shell-body">
      <SideMenu />
      <main class="shell-main">
        <TabBar />
        <div class="work">
          <div v-for="t in tabs.list" v-show="t.key === tabs.active" :key="t.key" class="pane">
            <component :is="screens[t.token]" :token="t.token" :param="t.param" :nonce="t.nonce" />
          </div>
        </div>
      </main>
    </div>
  </div>
  <p v-else-if="error" class="shell-error">{{ error }}</p>
</template>
