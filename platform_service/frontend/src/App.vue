<script setup>
import { useRoute } from 'vue-router'
import GlobalAssistant from './components/GlobalAssistant.vue'
import ToastContainer from './components/ToastContainer.vue'

const route = useRoute()
</script>

<template>
  <router-view />
  <GlobalAssistant v-if="route.path !== '/login'" />
  <ToastContainer />
</template>
