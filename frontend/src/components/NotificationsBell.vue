<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useNotifications } from '../composables/useNotifications'
import { useAuth } from '../composables/useAuth'

const { dbNotifications, unreadCount, fetchNotifications, markAsRead, clearNotifications } = useNotifications()
const { user } = useAuth()
const isOpen = ref(false)

let pollInterval = null

onMounted(() => {
  if (user.value) {
    fetchNotifications()
    pollInterval = setInterval(fetchNotifications, 10000)
  }
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})

function togglePanel() {
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    fetchNotifications()
  }
}

async function handleNotificationClick(n) {
  if (!n.is_read) {
    await markAsRead(n.id)
  }
  isOpen.value = false
}
</script>

<template>
  <div class="notif-wrapper" v-if="user">
    <!-- Bell Button -->
    <button class="notif-bell" @click="togglePanel" :class="{'has-unread': unreadCount > 0}">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
        <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
      </svg>
      <span v-if="unreadCount > 0" class="notif-badge">{{ unreadCount }}</span>
    </button>

    <!-- Panel via Teleport to escape backdrop-filter stacking context -->
    <Teleport to="body">
      <div v-if="isOpen" class="notif-overlay" @click.self="isOpen = false">
        <div class="notif-panel glass-panel">
          <div class="notif-header">
            <h3>Оповещения</h3>
            <button class="notif-clear" @click="clearNotifications" v-if="dbNotifications.length > 0">Очистить</button>
          </div>

          <div class="notif-list" v-if="dbNotifications.length > 0">
            <component
              :is="n.link ? 'router-link' : 'div'"
              :to="n.link"
              v-for="n in dbNotifications"
              :key="n.id"
              class="notif-item"
              :class="{ 'unread': !n.is_read }"
              @click="handleNotificationClick(n)"
            >
              <div class="notif-dot" v-if="!n.is_read"></div>
              <div class="notif-content">
                <div class="notif-title">{{ n.title }}</div>
                <div class="notif-msg">{{ n.message }}</div>
                <div class="notif-time">{{ new Date(n.created_at).toLocaleString() }}</div>
              </div>
            </component>
          </div>
          <div class="notif-empty" v-else>
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="color: var(--text-muted); margin-bottom: 12px;">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
              <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
              <line x1="18" y1="2" x2="22" y2="6"></line>
              <line x1="22" y1="2" x2="18" y2="6"></line>
            </svg>
            <div>Всё прочитано!</div>
            <div style="font-size: 13px; color: var(--text-secondary); margin-top: 4px;">Новых оповещений пока нет</div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.notif-wrapper {
  position: relative;
  display: inline-block;
  font-family: 'Inter', system-ui, sans-serif;
}

.notif-bell {
  background: var(--bg-elevated, #27272a);
  border: 1px solid var(--border, #3f3f46);
  color: var(--text, #e4e4e7);
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.notif-bell:hover {
  background: rgba(255,255,255,0.1);
  border-color: #6366f1;
  color: #a5b4fc;
}

.notif-bell.has-unread {
  border-color: rgba(99, 102, 241, 0.4);
  color: #a5b4fc;
}

.notif-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  background: var(--danger, #ef4444);
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 5px;
  border-radius: 10px;
  border: 2px solid var(--bg, #0f0f13);
}

.notif-overlay {
  position: fixed;
  inset: 0;
  z-index: 9998;
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
  padding-top: 70px;
  padding-right: 24px;
}

.notif-panel {
  width: 400px;
  max-height: 70vh;
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  z-index: 9999;
  text-align: left;
}

.notif-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
}

.notif-header h3 {
  margin: 0;
  font-size: 16px;
  color: #fff;
}

.notif-clear {
  background: none;
  border: none;
  color: var(--text-secondary, #9ca3af);
  font-size: 13px;
  cursor: pointer;
}
.notif-clear:hover {
  color: var(--danger, #ef4444);
}

.notif-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.notif-item {
  display: flex;
  padding: 16px;
  gap: 12px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  cursor: pointer;
  transition: background 0.2s;
  text-decoration: none;
  color: inherit;
}
.notif-item:hover {
  background: rgba(255,255,255,0.03);
}
.notif-item.unread {
  background: rgba(99, 102, 241, 0.05);
}

.notif-dot {
  width: 8px;
  height: 8px;
  background: var(--accent, #6366f1);
  border-radius: 50%;
  margin-top: 6px;
  flex-shrink: 0;
}

.notif-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.notif-title {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}

.notif-msg {
  font-size: 13px;
  color: var(--text-secondary, #9ca3af);
  line-height: 1.4;
}

.notif-time {
  font-size: 11px;
  color: rgba(255,255,255,0.3);
  margin-top: 4px;
}

.notif-empty {
  padding: 48px 24px;
  text-align: center;
  color: var(--text-muted, #6b7280);
  font-size: 15px;
  font-weight: 500;
  display: flex;
  flex-direction: column;
  align-items: center;
}
</style>
