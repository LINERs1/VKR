<script setup>
import { useRoute } from 'vue-router'
import GlobalAssistant from './components/GlobalAssistant.vue'

const route = useRoute()
</script>

<template>
  <router-view />
  <GlobalAssistant v-if="route.path !== '/login'" />
</template>
