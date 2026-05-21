<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiFetch, hwApi } from '../api'
import { useAuth } from '../composables/useAuth'

const route = useRoute()
const router = useRouter()
const { fetchUser } = useAuth()

const student = ref(null)
const homeworks = ref([])
const courses = ref([])
const loading = ref(true)

const studentId = computed(() => Number(route.params.id))

const courseTitleMap = computed(() => {
  const m = {}
  for (const c of courses.value) m[c.id] = c.title
  return m
})

const studentHomeworks = computed(() => {
  const rows = []
  for (const hw of homeworks.value) {
    const a = (hw.assignments || []).find((x) => x.student_id === studentId.value)
    if (a) {
      rows.push({ hw, assignment: a })
    }
  }
  return rows.sort((a, b) => b.hw.id - a.hw.id)
})

const stats = computed(() => {
  let sum = 0
  let count = 0
  let pending = 0
  let submitted = 0

  for (const { assignment: a } of studentHomeworks.value) {
    if (a.status === 'graded' && a.grade != null) {
      sum += a.grade
      count++
    } else if (a.status === 'submitted') submitted++
    else if (a.status === 'pending') pending++
  }

  return {
    avg: count > 0 ? (sum / count).toFixed(1) : '—',
    total: studentHomeworks.value.length,
    pending,
    submitted,
    graded: count,
  }
})

onMounted(async () => {
  const user = await fetchUser()
  if (!user || user.role !== 'teacher') {
    router.push('/homeworks')
    return
  }

  try {
    const [students, hw, crs] = await Promise.all([
      hwApi.getStudents(),
      hwApi.getHomeworks(),
      apiFetch('/courses'),
    ])
    student.value = students.find((s) => s.id === studentId.value) || null
    homeworks.value = hw
    courses.value = crs
    if (!student.value) router.push('/journal')
  } catch (e) {
    console.error(e)
    router.push('/journal')
  } finally {
    loading.value = false
  }
})

function goToWork(hwId, status) {
  if (status === 'graded' || status === 'submitted') {
    router.push({ path: `/homeworks/${hwId}`, query: { student: studentId.value } })
  }
}

function formatStatus(status) {
  if (status === 'pending') return 'Ожидает'
  if (status === 'submitted') return 'На проверке'
  if (status === 'graded') return 'Оценено'
  return status
}
</script>

<template>
  <div class="student-profile" v-if="!loading && student">
    <header class="header">
      <button type="button" class="back-btn" @click="router.push('/journal')">← Журнал</button>
      <div class="user-block">
        <div class="avatar">{{ student.username.charAt(0).toUpperCase() }}</div>
        <div>
          <h1>{{ student.username }}</h1>
          <span class="role">Ученик</span>
        </div>
      </div>
    </header>

    <div class="stats-row">
      <div class="stat">
        <div class="num">{{ stats.avg }}</div>
        <div class="lbl">Средний балл</div>
      </div>
      <div class="stat">
        <div class="num">{{ stats.total }}</div>
        <div class="lbl">Домашних заданий</div>
      </div>
      <div class="stat">
        <div class="num warn">{{ stats.pending }}</div>
        <div class="lbl">Не сдано</div>
      </div>
      <div class="stat">
        <div class="num ok">{{ stats.graded }}</div>
        <div class="lbl">Оценено</div>
      </div>
    </div>

    <section class="panel">
      <h2>Домашние задания</h2>
      <div v-if="!studentHomeworks.length" class="empty-state">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--text-muted); margin-bottom: 12px;">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
          <line x1="16" y1="13" x2="8" y2="13"></line>
          <line x1="16" y1="17" x2="8" y2="17"></line>
          <polyline points="10 9 9 9 8 9"></polyline>
        </svg>
        <div style="font-size: 16px; font-weight: 500; color: var(--text);">Нет назначенных заданий</div>
      </div>
      <div v-else class="hw-list">
        <div
          v-for="{ hw, assignment: a } in studentHomeworks"
          :key="hw.id"
          class="hw-item"
          :class="{ clickable: a.status === 'graded' || a.status === 'submitted' }"
          @click="goToWork(hw.id, a.status)"
        >
          <div class="hw-info">
            <div class="hw-name">{{ hw.title }}</div>
            <div class="hw-course">{{ courseTitleMap[hw.course_id] || hw.course_id }}</div>
          </div>
          <div class="hw-meta">
            <span class="status" :class="a.status">{{ formatStatus(a.status) }}</span>
            <span v-if="a.status === 'graded' && a.grade != null" class="grade">{{ a.grade }}</span>
          </div>
        </div>
      </div>
    </section>
  </div>

  <div v-else-if="loading" class="loading">Загрузка…</div>
</template>

<style scoped>
.student-profile {
  min-height: 100vh;
  background: #09090b;
  color: #e4e4e7;
  padding: 24px;
  font-family: 'Inter', system-ui, sans-serif;
  max-width: 800px;
  margin: 0 auto;
}

.header {
  margin-bottom: 28px;
}

.back-btn {
  background: none;
  border: none;
  color: #a1a1aa;
  cursor: pointer;
  padding: 0;
  margin-bottom: 16px;
  font-size: 14px;
}

.back-btn:hover {
  color: #fff;
}

.user-block {
  display: flex;
  align-items: center;
  gap: 16px;
}

.avatar {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #3b82f6);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 700;
  color: #fff;
}

h1 {
  margin: 0 0 4px;
  font-size: 24px;
}

.role {
  font-size: 13px;
  color: #818cf8;
  background: rgba(99, 102, 241, 0.15);
  padding: 2px 8px;
  border-radius: 999px;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}

.stat {
  background: #18181b;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  padding: 16px;
  text-align: center;
}

.num {
  font-size: 28px;
  font-weight: 700;
  margin-bottom: 4px;
}

.num.warn {
  color: #fbbf24;
}

.num.ok {
  color: #34d399;
}

.lbl {
  font-size: 12px;
  color: #71717a;
}

.panel {
  background: #18181b;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  padding: 20px;
}

.panel h2 {
  margin: 0 0 16px;
  font-size: 18px;
}

.hw-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.hw-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 14px 16px;
  border-radius: 10px;
  background: #09090b;
  border: 1px solid #27272a;
}

.hw-item.clickable {
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.hw-item.clickable:hover {
  border-color: rgba(99, 102, 241, 0.45);
  background: rgba(99, 102, 241, 0.06);
}

.hw-name {
  font-weight: 500;
  margin-bottom: 4px;
}

.hw-course {
  font-size: 12px;
  color: #71717a;
}

.hw-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.status {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 6px;
  font-weight: 500;
}

.status.pending {
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
}

.status.submitted {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
}

.status.graded {
  background: rgba(16, 185, 129, 0.15);
  color: #34d399;
}

.grade {
  font-size: 20px;
  font-weight: 700;
  color: #34d399;
  min-width: 28px;
  text-align: center;
}

.loading {
  text-align: center;
  color: #71717a;
  padding: 32px;
}

.empty-state {
  text-align: center;
  padding: 40px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

@media (max-width: 640px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
