<script setup>
defineProps({ value: { type: Number, required: true } })
</script>

<template>
  <div class="pbar">
    <i :style="{ width: `${value}%` }" />
    <span>{{ value }}%</span>
  </div>
</template>
