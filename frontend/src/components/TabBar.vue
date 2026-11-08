<script setup>
import { activate, closeOthers, closeTab, tabs } from '../stores/tabs.js'
</script>

<template>
  <div class="tabbar">
    <div
      v-for="t in tabs.list"
      :key="t.key"
      class="tab"
      :class="{ on: t.key === tabs.active }"
      @click="activate(t.key)"
    >
      <span>{{ t.title }}</span>
      <button type="button" class="tab-x" :aria-label="`${t.title} 닫기`" @click.stop="closeTab(t.key)">×</button>
    </div>
    <button v-if="tabs.list.length >= 2" type="button" class="btn sm tab-others" @click="closeOthers">
      다른 탭 닫기
    </button>
  </div>
</template>
