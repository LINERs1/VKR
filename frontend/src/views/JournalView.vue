<script setup>
import { ref, onMounted, computed } from 'vue'
import { apiFetch } from '../api'
import { useRouter } from 'vue-router'

const router = useRouter()
const homeworks = ref([])
const loading = ref(true)

onMounted(async () => {
  try {
    homeworks.value = await apiFetch('/homework/')
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
})

const stats = computed(() => {
  let totalGrades = 0;
  let gradeCount = 0;
  let pending = 0;
  
  homeworks.value.forEach(hw => {
    hw.assignments.forEach(a => {
      if (a.status === 'graded' && a.grade) {
        totalGrades += a.grade;
        gradeCount++;
      }
      if (a.status === 'submitted') {
        pending++;
      }
    });
  });
  
  return {
    avg: gradeCount > 0 ? (totalGrades / gradeCount).toFixed(1) : '-',
    pending: pending,
    totalAssigned: homeworks.value.reduce((acc, hw) => acc + hw.assignments.length, 0)
  }
})

// Transform data into a matrix: rows are students, columns are homeworks
const tableData = computed(() => {
  const studentsMap = {}
  
  homeworks.value.forEach(hw => {
    hw.assignments.forEach(a => {
      if (!studentsMap[a.student_id]) {
        studentsMap[a.student_id] = {
          id: a.student_id,
          name: a.student_name,
          assignments: {}
        }
      }
      studentsMap[a.student_id].assignments[hw.id] = a
    })
  })
  
  return Object.values(studentsMap)
})

function getStatusColor(status) {
  switch (status) {
    case 'graded': return '#10b981'
    case 'submitted': return '#f59e0b'
    default: return '#6b7280'
  }
}

function getStatusLabel(status) {
  switch (status) {
    case 'graded': return 'Оценено'
    case 'submitted': return 'Сдано'
    default: return 'Ожидает'
  }
}

function goToHomework(hwId) {
  router.push(`/homeworks/${hwId}`)
}
</script>

<template>
  <div class="journal-page">
    <header class="journal-header">
      <router-link to="/" class="btn-back">← Назад</router-link>
      <h1>Журнал успеваемости</h1>
      <p class="subtitle">Отслеживайте прогресс студентов и проверяйте задания</p>
    </header>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Загрузка журнала...</p>
    </div>

    <div v-if="!loading && homeworks.length > 0" class="stats-row">
      <div class="stat-card">
        <div class="stat-value">{{ stats.avg }}</div>
        <div class="stat-label">Средний балл</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: #f59e0b;">{{ stats.pending }}</div>
        <div class="stat-label">Ожидают проверки</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: #6366f1;">{{ stats.totalAssigned }}</div>
        <div class="stat-label">Всего выдано</div>
      </div>
    </div>

    <div v-else-if="tableData.length === 0" class="empty-state">
      <div class="empty-icon">📊</div>
      <h2>Нет данных</h2>
      <p>Вы еще не выдавали домашних заданий.</p>
    </div>

    <div v-else class="journal-container">
      <table class="journal-table">
        <thead>
          <tr>
            <th class="student-col">Студент</th>
            <th v-for="hw in homeworks" :key="hw.id" class="hw-col" @click="goToHomework(hw.id)" title="Перейти к заданию">
              <div class="hw-title">{{ hw.title }}</div>
              <div class="hw-course">{{ hw.course?.title || 'Курс' }}</div>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="student in tableData" :key="student.id">
            <td class="student-name">
              <div class="avatar">{{ student.name.charAt(0).toUpperCase() }}</div>
              {{ student.name }}
            </td>
            <td v-for="hw in homeworks" :key="hw.id" class="grade-cell" @click="goToHomework(hw.id)">
              <div class="assignment-wrapper" v-if="student.assignments[hw.id]">
                <div 
                  class="grade-badge" 
                  v-if="student.assignments[hw.id].status === 'graded'"
                  :class="{'grade-good': student.assignments[hw.id].grade >= 4, 'grade-bad': student.assignments[hw.id].grade <= 3}"
                >
                  {{ student.assignments[hw.id].grade }}
                </div>
                <div v-else class="status-badge" :style="{ color: getStatusColor(student.assignments[hw.id].status) }">
                  {{ getStatusLabel(student.assignments[hw.id].status) }}
                </div>
              </div>
              <div v-else class="no-assignment">-</div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.journal-page {
  padding: 40px;
  max-width: 1200px;
  margin: 0 auto;
  font-family: 'Inter', sans-serif;
  color: #fff;
}

.journal-header {
  margin-bottom: 30px;
}

.btn-back {
  display: inline-block;
  color: #9ca3af;
  text-decoration: none;
  margin-bottom: 16px;
  font-size: 14px;
  transition: color 0.2s;
}

.btn-back:hover {
  color: #fff;
}

h1 {
  font-size: 32px;
  font-weight: 700;
  margin: 0 0 8px 0;
  background: linear-gradient(135deg, #fff 0%, #a5b4fc 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.subtitle {
  color: #9ca3af;
  margin: 0;
  font-size: 15px;
}

.loading-state, .empty-state {
  text-align: center;
  padding: 80px 20px;
  background: #111;
  border-radius: 24px;
  border: 1px solid rgba(255,255,255,0.05);
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(99,102,241,0.3);
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 20px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.journal-container {
  background: #111;
  border-radius: 20px;
  border: 1px solid rgba(255,255,255,0.05);
  overflow-x: auto;
  box-shadow: 0 10px 30px rgba(0,0,0,0.5);
}

.journal-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

.journal-table th, .journal-table td {
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
}

.journal-table th {
  background: rgba(255,255,255,0.02);
  font-weight: 500;
  color: #9ca3af;
  cursor: pointer;
  transition: background 0.2s;
  white-space: nowrap;
}

.journal-table th:hover {
  background: rgba(255,255,255,0.05);
}

.student-col {
  width: 250px;
  border-right: 1px solid rgba(255,255,255,0.05);
}

.hw-col {
  min-width: 150px;
  text-align: center;
}

.hw-title {
  color: #e5e7eb;
  font-size: 14px;
  margin-bottom: 4px;
}

.hw-course {
  font-size: 12px;
  color: #6b7280;
}

.journal-table tbody tr:hover {
  background: rgba(255,255,255,0.02);
}

.student-name {
  display: flex;
  align-items: center;
  gap: 12px;
  font-weight: 500;
  color: #f3f4f6;
  border-right: 1px solid rgba(255,255,255,0.05);
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #a855f7);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}

.grade-cell {
  text-align: center;
  cursor: pointer;
  transition: background 0.2s;
}

.grade-cell:hover {
  background: rgba(255,255,255,0.05);
}

.assignment-wrapper {
  display: flex;
  justify-content: center;
}

.grade-badge {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 15px;
  background: rgba(255,255,255,0.1);
  color: #fff;
}

.grade-good {
  background: rgba(16, 185, 129, 0.2);
  color: #34d399;
}

.grade-bad {
  background: rgba(239, 68, 68, 0.2);
  color: #f87171;
}

.status-badge {
  font-size: 13px;
  font-weight: 500;
}

.no-assignment {
  color: #374151;
}
.stats-row {
  display: flex;
  gap: 20px;
  margin-bottom: 24px;
}

.stat-card {
  background: #111;
  border-radius: 16px;
  padding: 20px;
  flex: 1;
  border: 1px solid rgba(255,255,255,0.05);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.stat-value {
  font-size: 36px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 8px;
}

.stat-label {
  color: #9ca3af;
  font-size: 14px;
}
</style>
