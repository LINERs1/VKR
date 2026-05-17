<template>
  <div class="profile-view" v-if="user">
    <header class="header">
      <button class="back-btn" @click="$router.push('/')">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M19 12H5M12 19l-7-7 7-7" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        На главную
      </button>
      <div class="user-info">
        <div class="avatar">{{ user.username[0].toUpperCase() }}</div>
        <div>
          <h2 class="username">{{ user.username }}</h2>
          <span class="role-badge">{{ user.role === 'teacher' ? 'Преподаватель' : 'Ученик' }}</span>
        </div>
      </div>
      <button class="logout-btn" @click="handleLogout">Выйти</button>
    </header>

    <main class="content">
      <div v-if="loading" class="loading">Загрузка профиля...</div>
      <div v-else class="dashboard-grid">
        
        <!-- СТАТИСТИКА (ВИДЯТ ВСЕ) -->
        <div class="panel stats-panel">
          <h3>Аналитика успеваемости</h3>
          <div class="stats-cards">
            <div class="stat-box">
              <div class="stat-num" :style="{ color: roleColor }">{{ stats.avgGrade }}</div>
              <div class="stat-title">Средний балл</div>
            </div>
            <div class="stat-box" v-if="user.role === 'teacher'">
              <div class="stat-num">{{ stats.totalAssigned }}</div>
              <div class="stat-title">Выдано ДЗ</div>
            </div>
            <div class="stat-box" v-if="user.role === 'student'">
              <div class="stat-num">{{ stats.totalCompleted }}</div>
              <div class="stat-title">Сдано ДЗ</div>
            </div>
            <div class="stat-box">
              <div class="stat-num" style="color: #f59e0b;">{{ stats.pendingAction }}</div>
              <div class="stat-title">{{ user.role === 'teacher' ? 'Ждут проверки' : 'Ожидают выполнения' }}</div>
            </div>
          </div>
        </div>

        <!-- ГРАФИК УСПЕВАЕМОСТИ ПО КУРСАМ -->
        <div class="panel chart-panel">
          <h3>Успеваемость по курсам (Средний балл)</h3>
          <div v-if="Object.keys(stats.courseAverages).length === 0" class="empty-chart">
            Нет данных для построения графика
          </div>
          <div v-else class="css-bar-chart">
            <div class="bar-wrapper" v-for="(avg, courseId) in stats.courseAverages" :key="courseId">
              <div class="bar-track">
                <div class="bar-fill" :style="{ height: (avg / 5 * 100) + '%', background: roleColor }">
                  <span class="bar-value-tooltip">{{ avg }}</span>
                </div>
              </div>
              <div class="bar-label">{{ courseId }}</div>
            </div>
          </div>
        </div>

        <!-- ИСТОРИЯ ПОСЛЕДНИХ ОЦЕНОК (Только для студента) -->
        <div class="panel history-panel" v-if="user.role === 'student'">
          <h3>Последние оценки</h3>
          <div class="grades-list">
            <div v-for="hw in recentGraded" :key="hw.id" class="grade-item">
              <div class="grade-item-info">
                <div class="gi-title">{{ hw.title }}</div>
                <div class="gi-course">{{ hw.course_id }}</div>
              </div>
              <div class="gi-score">{{ hw.assignments[0].grade }}</div>
            </div>
            <div v-if="recentGraded.length === 0" class="empty-text">Пока нет оцененных заданий</div>
          </div>
        </div>
      </div>
      
      <div style="text-align: center; margin-top: 30px;">
        <button class="action-btn" @click="$router.push('/homeworks')">Перейти к Домашним заданиям</button>
      </div>
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'
import { hwApi } from '../api'

const router = useRouter()
const { fetchUser } = useAuth()
const user = ref(null)
const homeworks = ref([])
const loading = ref(true)

const roleColor = computed(() => user.value?.role === 'teacher' ? '#f59e0b' : '#3b82f6')

const stats = computed(() => {
  if (!user.value) return { avgGrade: 0, pendingAction: 0, totalAssigned: 0, totalCompleted: 0, courseAverages: {} }
  
  let totalGrades = 0
  let gradeCount = 0
  let pending = 0
  let completed = 0
  let courseGrades = {} // { course_id: { sum: 0, count: 0 } }
  
  homeworks.value.forEach(hw => {
    const courseId = hw.course_id
    if (!courseGrades[courseId]) courseGrades[courseId] = { sum: 0, count: 0 }
    
    hw.assignments.forEach(a => {
      // Для студента считаем только его ассайнменты
      if (user.value.role === 'student' && a.student_id !== user.value.id) return
      
      if (a.status === 'graded' && a.grade) {
        totalGrades += a.grade
        gradeCount++
        courseGrades[courseId].sum += a.grade
        courseGrades[courseId].count++
      }
      if (user.value.role === 'teacher' && a.status === 'submitted') pending++
      if (user.value.role === 'student' && a.status === 'pending') pending++
      if (user.value.role === 'student' && (a.status === 'submitted' || a.status === 'graded')) completed++
    })
  })
  
  const courseAverages = {}
  for (const cid in courseGrades) {
    if (courseGrades[cid].count > 0) {
      courseAverages[cid] = (courseGrades[cid].sum / courseGrades[cid].count).toFixed(1)
    }
  }
  
  return {
    avgGrade: gradeCount > 0 ? (totalGrades / gradeCount).toFixed(1) : '-',
    pendingAction: pending,
    totalAssigned: homeworks.value.length, // Для препода
    totalCompleted: completed, // Для студента
    courseAverages
  }
})

const recentGraded = computed(() => {
  if (user.value?.role !== 'student') return []
  return homeworks.value
    .filter(hw => hw.assignments.some(a => a.student_id === user.value.id && a.status === 'graded'))
    .sort((a, b) => b.id - a.id)
    .slice(0, 5)
})

onMounted(async () => {
  user.value = await fetchUser()
  if (!user.value) return router.push('/login')
  
  try {
    homeworks.value = await hwApi.getHomeworks()
  } catch (e) { console.error(e) }
  loading.value = false
})

function handleLogout() {
  localStorage.removeItem('token')
  router.push('/login')
}
</script>

<style scoped>
.profile-view {
  min-height: 100vh;
  background: #09090b;
  color: #e4e4e7;
  font-family: 'Inter', system-ui, sans-serif;
  padding: 24px;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 40px;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  background: none;
  border: none;
  color: #a1a1aa;
  cursor: pointer;
  font-size: 16px;
}
.back-btn:hover { color: #fff; }

.user-info {
  display: flex;
  align-items: center;
  gap: 16px;
}
.avatar {
  width: 48px; height: 48px;
  background: linear-gradient(135deg, #6366f1, #3b82f6);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; font-weight: bold; color: #fff;
}
.username { margin: 0; font-size: 20px; }
.role-badge {
  display: inline-block;
  background: rgba(99,102,241,0.15);
  color: #818cf8;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  margin-top: 4px;
}

.logout-btn {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.3);
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}
.logout-btn:hover { background: rgba(239, 68, 68, 0.25); }

.content {
  max-width: 900px;
  margin: 0 auto;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

.panel {
  background: #18181b;
  border: 1px solid rgba(255,255,255,0.05);
  border-radius: 16px;
  padding: 24px;
}

.panel h3 {
  margin-top: 0;
  margin-bottom: 20px;
  font-size: 18px;
  color: #f3f4f6;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  padding-bottom: 12px;
}

.stats-panel { grid-column: 1 / -1; }

.stats-cards {
  display: flex;
  gap: 20px;
  justify-content: space-around;
}

.stat-box {
  text-align: center;
}

.stat-num {
  font-size: 40px;
  font-weight: 700;
  margin-bottom: 8px;
}

.stat-title {
  color: #9ca3af;
  font-size: 14px;
}

.css-bar-chart {
  display: flex;
  justify-content: space-around;
  align-items: flex-end;
  height: 200px;
  padding-top: 20px;
}

.bar-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  width: 40px;
}

.bar-track {
  width: 100%;
  height: 150px;
  background: rgba(255,255,255,0.05);
  border-radius: 8px;
  position: relative;
  display: flex;
  align-items: flex-end;
}

.bar-fill {
  width: 100%;
  border-radius: 8px;
  position: relative;
  transition: height 0.5s ease-out;
}

.bar-value-tooltip {
  position: absolute;
  top: -24px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 12px;
  font-weight: bold;
  color: #fff;
}

.bar-label {
  font-size: 12px;
  color: #a1a1aa;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.grades-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.grade-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(255,255,255,0.02);
  padding: 12px 16px;
  border-radius: 8px;
}

.gi-title {
  font-weight: 500;
  color: #f3f4f6;
  margin-bottom: 4px;
}

.gi-course {
  font-size: 12px;
  color: #9ca3af;
}

.gi-score {
  font-size: 20px;
  font-weight: 700;
  color: #34d399;
}

.empty-text, .empty-chart {
  color: #6b7280;
  text-align: center;
  font-style: italic;
  padding: 20px 0;
}

.loading { text-align: center; color: #a1a1aa; padding: 40px; }

.action-btn {
  background: #4f46e5;
  color: white;
  border: none;
  padding: 12px 24px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 16px;
  font-weight: 500;
  transition: background 0.2s;
}
.action-btn:hover { background: #4338ca; }

@media (max-width: 768px) {
  .dashboard-grid { grid-template-columns: 1fr; }
}
</style>
