<script setup>
import { computed, reactive } from 'vue'
import { session } from '../stores/session.js'
import { navigate, tabs } from '../stores/tabs.js'

const collapsed = reactive({})
const roots = computed(() => session.menu.filter((m) => !m.parent_id))
const childrenOf = (id) => session.menu.filter((m) => m.parent_id === id)
const activeToken = computed(() => tabs.list.find((t) => t.key === tabs.active)?.token)
</script>

<template>
  <nav class="side" aria-label="메뉴">
    <div class="side-title">MENU</div>
    <template v-for="m in roots" :key="m.menu_id">
      <button
        v-if="m.token"
        type="button"
        class="side-item"
        :class="{ on: m.token === activeToken }"
        @click="navigate(m.token)"
      >
        <span class="mark">·</span>{{ m.title }}
      </button>
      <template v-else>
        <button
          type="button"
          class="side-item"
          :aria-expanded="!collapsed[m.menu_id]"
          @click="collapsed[m.menu_id] = !collapsed[m.menu_id]"
        >
          <span class="mark group">{{ collapsed[m.menu_id] ? '▶' : '▼' }}</span>{{ m.title }}
        </button>
        <template v-if="!collapsed[m.menu_id]">
          <button
            v-for="c in childrenOf(m.menu_id)"
            :key="c.menu_id"
            type="button"
            class="side-item child"
            :class="{ on: c.token === activeToken }"
            @click="navigate(c.token)"
          >
            <span class="mark">·</span>{{ c.title }}
          </button>
        </template>
      </template>
    </template>
  </nav>
</template>
