import { ref, reactive, computed } from 'vue'

const toasts = ref([])
let nextId = 1

import { notificationsApi } from '../api'

const dbNotifications = ref([])
const unreadCount = computed(() => dbNotifications.value.filter(n => !n.is_read).length)

export function useNotifications() {
  function addToast(message, type = 'info', onClickPath = null) {
    const id = nextId++
    toasts.value.push({ id, message, type, onClickPath })
    setTimeout(() => removeToast(id), 5000)
  }

  function removeToast(id) {
    const index = toasts.value.findIndex(t => t.id === id)
    if (index !== -1) toasts.value.splice(index, 1)
  }

  let maxSeenId = 0
  
  async function fetchNotifications() {
    try {
      const data = await notificationsApi.get()
      if (data && data.length > 0) {
        // Find if there are any new unread notifications
        const newNotifs = data.filter(n => !n.is_read && n.id > maxSeenId)
        if (newNotifs.length > 0) {
          // Dispatch event for GlobalAssistant
          newNotifs.forEach(n => {
            window.dispatchEvent(new CustomEvent('eduai-new-notification', { detail: n }))
          })
          const currentMax = Math.max(...data.map(n => n.id))
          maxSeenId = Math.max(maxSeenId, currentMax)
        } else if (maxSeenId === 0) {
          // Initial load
          maxSeenId = Math.max(0, ...data.map(n => n.id))
        }
      }
      dbNotifications.value = data
    } catch (e) {
      console.error('Failed to fetch notifications', e)
    }
  }

  async function markAsRead(id) {
    try {
      await notificationsApi.markRead(id)
      const n = dbNotifications.value.find(x => x.id === id)
      if (n) n.is_read = true
    } catch (e) {
      console.error(e)
    }
  }

  async function clearNotifications() {
    try {
      await notificationsApi.clear()
      dbNotifications.value = []
    } catch (e) {
      console.error(e)
    }
  }

  return {
    toasts,
    addToast,
    removeToast,
    dbNotifications,
    unreadCount,
    fetchNotifications,
    markAsRead,
    clearNotifications
  }
}

// Глобальное состояние проверяющихся сейчас заданий (чтобы кнопка оставалась заблокированной при переходах)
export const checkingAssignments = reactive(new Set())

// Глобальный кеш проверок ИИ, чтобы они не сбрасывались при переходах между страницами
export const aiReviewCache = new Map()
