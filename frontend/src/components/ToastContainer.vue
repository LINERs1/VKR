<script setup>
import { useNotifications } from '../composables/useNotifications.js'
import { useRouter } from 'vue-router'

const { toasts, removeToast } = useNotifications()
const router = useRouter()

function handleClick(toast) {
  if (toast.onClickPath) {
    router.push(toast.onClickPath)
  }
  removeToast(toast.id)
}
</script>

<template>
  <div class="toast-container">
    <TransitionGroup name="toast">
      <div 
        v-for="toast in toasts" 
        :key="toast.id"
        class="toast glass-panel"
        :class="[toast.type, { 'clickable': !!toast.onClickPath }]"
        @click="handleClick(toast)"
      >
        <span v-if="toast.type === 'success'" class="toast-icon">✅</span>
        <span v-else-if="toast.type === 'error'" class="toast-icon">❌</span>
        <span v-else class="toast-icon">ℹ️</span>
        <div class="toast-content">{{ toast.message }}</div>
        <button class="toast-close" @click.stop="removeToast(toast.id)">×</button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-container {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 10100;
  display: flex;
  flex-direction: column;
  gap: 12px;
  pointer-events: none;
}

.toast {
  pointer-events: auto;
  min-width: 250px;
  max-width: 350px;
  padding: 14px 16px;
  border-radius: 12px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  color: var(--text);
  font-size: 14px;
  transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.toast-icon {
  font-size: 18px;
  line-height: 1;
  margin-top: 2px;
}

.toast.info { border-left: 4px solid var(--accent); }
.toast.success { border-left: 4px solid #10b981; }
.toast.error { border-left: 4px solid #ef4444; }

.toast.clickable {
  cursor: pointer;
}
.toast.clickable:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.25);
}

.toast-content {
  flex: 1;
}

.toast-close {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 18px;
  cursor: pointer;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.toast-close:hover {
  color: var(--text);
}

/* Transitions */
.toast-enter-from {
  opacity: 0;
  transform: translateX(100%) scale(0.95);
}
.toast-enter-to {
  opacity: 1;
  transform: translateX(0) scale(1);
}
.toast-leave-from {
  opacity: 1;
  transform: translateX(0) scale(1);
}
.toast-leave-to {
  opacity: 0;
  transform: translateY(20px) scale(0.95);
}
.toast-leave-active {
  position: absolute;
}
</style>
