<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { apiFetch, hwApi } from '../api'
import { useAuth } from '../composables/useAuth'

const router = useRouter()
const { fetchUser } = useAuth()

const homeworks = ref([])
const courses = ref([])
const loading = ref(true)

onMounted(async () => {
  const user = await fetchUser()
  if (!user || user.role !== 'teacher') {
    router.push('/homeworks')
    return
  }
  try {
    const [hw, crs] = await Promise.all([hwApi.getHomeworks(), apiFetch('/courses')])
    homeworks.value = hw
    courses.value = crs
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
})

const courseTitleMap = computed(() => {
  const m = {}
  for (const c of courses.value) m[c.id] = c.title
  return m
})

const students = computed(() => {
  const map = new Map()
  for (const hw of homeworks.value) {
    for (const a of hw.assignments || []) {
      if (!map.has(a.student_id)) {
        map.set(a.student_id, { id: a.student_id, name: a.student_name || `Ученик #${a.student_id}` })
      }
    }
  }
  return [...map.values()].sort((a, b) => a.name.localeCompare(b.name, 'ru'))
})

const courseGroups = computed(() => {
  const byCourse = new Map()
  for (const hw of homeworks.value) {
    if (!byCourse.has(hw.course_id)) byCourse.set(hw.course_id, [])
    byCourse.get(hw.course_id).push(hw)
  }
  return [...byCourse.entries()]
    .map(([courseId, items]) => ({
      courseId,
      courseTitle: courseTitleMap.value[courseId] || courseId,
      homeworks: [...items].sort((a, b) => b.id - a.id),
    }))
    .sort((a, b) => a.courseTitle.localeCompare(b.courseTitle, 'ru'))
})

const stats = computed(() => {
  let totalGrades = 0
  let gradeCount = 0
  let pending = 0
  let assigned = 0

  for (const hw of homeworks.value) {
    for (const a of hw.assignments || []) {
      assigned++
      if (a.status === 'graded' && a.grade) {
        totalGrades += a.grade
        gradeCount++
      }
      if (a.status === 'submitted') pending++
    }
  }

  return {
    avg: gradeCount > 0 ? (totalGrades / gradeCount).toFixed(1) : '—',
    pending,
    assigned,
  }
})

function assignmentFor(hw, studentId) {
  return (hw.assignments || []).find((a) => a.student_id === studentId) || null
}

function goToStudent(studentId) {
  router.push(`/students/${studentId}`)
}

function goToWork(hw, studentId) {
  const a = assignmentFor(hw, studentId)
  if (!a) return
  if (a.status === 'graded' || a.status === 'submitted') {
    router.push({ path: `/homeworks/${hw.id}`, query: { student: studentId } })
  }
}

function cellLabel(a) {
  if (!a) return '—'
  if (a.status === 'graded' && a.grade != null) return String(a.grade)
  if (a.status === 'submitted') return 'Сдано'
  return 'Ожидает'
}

function cellClass(a) {
  if (!a) return 'empty'
  if (a.status === 'graded' && a.grade != null) {
    if (a.grade >= 4) return 'grade grade-good'
    if (a.grade <= 3) return 'grade grade-bad'
    return 'grade'
  }
  if (a.status === 'submitted') return 'status submitted'
  return 'status pending'
}

function isClickable(a) {
  return a && (a.status === 'graded' || a.status === 'submitted')
}
</script>

<template>
  <div class="journal-page">
    <header class="journal-header">
      <router-link to="/" class="btn-back">← На главную</router-link>
      <h1>Журнал успеваемости</h1>
      <p class="subtitle">Строки — домашние задания по курсам, столбцы — ученики</p>
    </header>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Загрузка журнала…</p>
    </div>

    <template v-else>
      <div v-if="homeworks.length" class="stats-row">
        <div class="stat-card">
          <div class="stat-value">{{ stats.avg }}</div>
          <div class="stat-label">Средний балл</div>
        </div>
        <div class="stat-card">
          <div class="stat-value pending">{{ stats.pending }}</div>
          <div class="stat-label">Ожидают проверки</div>
        </div>
        <div class="stat-card">
          <div class="stat-value accent">{{ stats.assigned }}</div>
          <div class="stat-label">Назначений</div>
        </div>
      </div>

      <div v-if="!students.length || !homeworks.length" class="empty-state">
        <div class="empty-icon">📊</div>
        <h2>Нет данных</h2>
        <p>Назначьте домашние задания ученикам — они появятся в журнале.</p>
      </div>

      <div v-else class="journal-container">
        <table class="journal-table">
          <thead>
            <tr>
              <th class="hw-col sticky-col">Домашнее задание</th>
              <th
                v-for="st in students"
                :key="st.id"
                class="student-col"
                @click="goToStudent(st.id)"
              >
                <div class="student-head">
                  <span class="avatar">{{ st.name.charAt(0).toUpperCase() }}</span>
                  <span class="student-name">{{ st.name }}</span>
                </div>
              </th>
            </tr>
          </thead>
          <tbody>
            <template v-for="group in courseGroups" :key="group.courseId">
              <tr class="course-row">
                <td :colspan="students.length + 1">
                  <span class="course-label">{{ group.courseTitle }}</span>
                  <span class="course-id">{{ group.courseId }}</span>
                </td>
              </tr>
              <tr v-for="hw in group.homeworks" :key="hw.id" class="hw-row">
                <td class="hw-title-cell sticky-col">
                  <span class="hw-title">{{ hw.title }}</span>
                  <span v-if="hw.is_demo" class="demo-tag">Пример</span>
                </td>
                <td
                  v-for="st in students"
                  :key="`${hw.id}-${st.id}`"
                  class="grade-cell"
                  :class="{ clickable: isClickable(assignmentFor(hw, st.id)) }"
                  @click="goToWork(hw, st.id)"
                >
                  <span :class="cellClass(assignmentFor(hw, st.id))">
                    {{ cellLabel(assignmentFor(hw, st.id)) }}
                  </span>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<style scoped>
.journal-page {
  padding: 32px 24px 48px;
  max-width: 1400px;
  margin: 0 auto;
  font-family: 'Inter', system-ui, sans-serif;
  color: #e4e4e7;
}

.journal-header {
  margin-bottom: 28px;
}

.btn-back {
  display: inline-block;
  color: #9ca3af;
  text-decoration: none;
  margin-bottom: 12px;
  font-size: 14px;
  transition: color 0.2s;
}

.btn-back:hover {
  color: #fff;
}

h1 {
  font-size: 28px;
  font-weight: 700;
  margin: 0 0 6px;
  background: linear-gradient(135deg, #fff 0%, #a5b4fc 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.subtitle {
  color: #71717a;
  margin: 0;
  font-size: 14px;
}

.loading-state,
.empty-state {
  text-align: center;
  padding: 64px 20px;
  background: #18181b;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.spinner {
  width: 36px;
  height: 36px;
  border: 3px solid rgba(99, 102, 241, 0.25);
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 16px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.empty-icon {
  font-size: 40px;
  margin-bottom: 12px;
  opacity: 0.6;
}

.stats-row {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  flex: 1;
  background: #18181b;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 14px;
  padding: 18px;
  text-align: center;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 4px;
}

.stat-value.pending {
  color: #fbbf24;
}

.stat-value.accent {
  color: #818cf8;
}

.stat-label {
  color: #71717a;
  font-size: 13px;
}

.journal-container {
  background: #18181b;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  overflow-x: auto;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
}

.journal-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 640px;
}

.journal-table th,
.journal-table td {
  padding: 12px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  vertical-align: middle;
}

.sticky-col {
  position: sticky;
  left: 0;
  z-index: 2;
  background: #18181b;
  min-width: 220px;
  max-width: 280px;
}

.journal-table thead th {
  background: #111113;
  font-weight: 500;
  top: 0;
  z-index: 3;
}

.journal-table thead .sticky-col {
  background: #111113;
  z-index: 4;
}

.student-col {
  min-width: 120px;
  text-align: center;
  cursor: pointer;
  transition: background 0.15s;
}

.student-col:hover {
  background: rgba(99, 102, 241, 0.12);
}

.student-head {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #a855f7);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
}

.student-name {
  font-size: 13px;
  color: #e4e4e7;
  line-height: 1.2;
}

.hw-col {
  text-align: left;
  color: #a1a1aa;
  font-size: 13px;
}

.course-row td {
  background: rgba(99, 102, 241, 0.08);
  border-bottom: 1px solid rgba(99, 102, 241, 0.2);
  padding: 10px 14px;
}

.course-label {
  font-weight: 600;
  color: #c4b5fd;
  margin-right: 10px;
}

.course-id {
  font-size: 12px;
  color: #71717a;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.hw-row:hover .sticky-col {
  background: #1f1f23;
}

.hw-title-cell {
  border-right: 1px solid rgba(255, 255, 255, 0.06);
}

.hw-title {
  display: block;
  font-size: 14px;
  color: #f4f4f5;
  line-height: 1.35;
}

.demo-tag {
  display: inline-block;
  margin-top: 4px;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(99, 102, 241, 0.2);
  color: #a5b4fc;
}

.grade-cell {
  text-align: center;
}

.grade-cell.clickable {
  cursor: pointer;
}

.grade-cell.clickable:hover {
  background: rgba(255, 255, 255, 0.04);
}

.grade,
.status,
.empty {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 36px;
  padding: 4px 8px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
}

.grade {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.grade-good {
  background: rgba(16, 185, 129, 0.18);
  color: #34d399;
}

.grade-bad {
  background: rgba(239, 68, 68, 0.18);
  color: #f87171;
}

.status.submitted {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
  font-size: 12px;
  font-weight: 500;
}

.status.pending {
  color: #71717a;
  font-size: 12px;
  font-weight: 500;
}

.empty {
  color: #52525b;
  font-weight: 400;
}
</style>
