<template>
  <div class="homeworks-view" v-if="user">
    <GlassHeader>
      <div style="display: flex; align-items: center; gap: 16px;">
        <button class="glass-back-btn" @click="$router.push('/profile')">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 12H5M12 19l-7-7 7-7" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          В профиль
        </button>
        <h2 class="glass-title">Домашние задания</h2>
      </div>
      <div class="header-actions">
        <NotificationsBell />
        <button v-if="isTeacher" class="glass-btn" @click="$router.push('/homeworks/workshop')">
          Мастерская
        </button>
        <button v-if="isTeacher" class="glass-btn glass-btn-primary" @click="showModal = true">+ Создать ДЗ</button>
      </div>
    </GlassHeader>

    <main class="list-container">
      <div v-if="loading" class="loading">Загрузка...</div>
      <div v-else-if="homeworks.length === 0" class="empty-state">
        <svg width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--text-muted); margin-bottom: 16px;">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
          <line x1="16" y1="13" x2="8" y2="13"></line>
          <line x1="16" y1="17" x2="8" y2="17"></line>
          <polyline points="10 9 9 9 8 9"></polyline>
        </svg>
        <div class="empty-title">Заданий пока нет</div>
        <div class="empty-subtitle">Здесь будут отображаться домашние работы</div>
      </div>
      <div v-else class="hw-grid">
        <div 
          v-for="hw in homeworks" 
          :key="hw.id" 
          class="hw-card"
          @click="$router.push(`/homeworks/${hw.id}`)"
        >
          <div class="hw-top">
            <span class="course-badge">{{ hw.course_id }}</span>
            <span v-if="hw.is_demo" class="demo-badge">Пример</span>
            <span v-if="!isTeacher" class="status-badge" :class="getMyStatus(hw)">
              {{ formatStatus(getMyStatus(hw)) }}
            </span>
          </div>
          <h3 class="hw-title">{{ hw.title }}</h3>
          <p class="hw-desc">{{ excerpt(hw.description) }}</p>
          <div v-if="isTeacher" class="hw-stats">
            Назначено ученикам: {{ hw.assignments?.length || 0 }}
          </div>
        </div>
      </div>
    </main>

    <!-- Create Modal (Teacher Only) -->
    <div v-if="showModal && isTeacher" class="modal-overlay" @click.self="showModal = false">
      <div class="modal-content">
        <h3>Новое домашнее задание</h3>
        <form @submit.prevent="handleCreate">
          <div class="form-group">
            <label>Курс</label>
            <select v-model="newHw.course_id" required class="course-select">
              <option disabled value="">Выберите курс...</option>
              <option v-for="course in availableCourses" :key="course.id" :value="course.id">
                {{ course.icon }} {{ course.title }}
              </option>
            </select>
          </div>
          <div class="form-group">
            <label>Название</label>
            <input v-model="newHw.title" required placeholder="Тема ДЗ" />
          </div>
          <div class="form-group">
            <label>Описание / Задание</label>
            <textarea v-model="newHw.description" required rows="4" placeholder="Что нужно сделать..."></textarea>
          </div>
          <div class="form-group">
            <label>Скрытые критерии проверки для ИИ (опционально)</label>
            <textarea v-model="newHw.ai_criteria" rows="2" placeholder="Например: Снимай 2 балла за отсутствие комментариев..."></textarea>
          </div>
          <div class="form-group">
            <label>Выберите учеников:</label>
            <div class="students-list">
              <label v-for="st in availableStudents" :key="st.id" class="student-checkbox">
                <input type="checkbox" :value="st.id" v-model="newHw.student_ids" />
                {{ st.username }}
              </label>
            </div>
          </div>
          <div class="modal-actions">
            <button type="button" class="cancel-btn" @click="showModal = false">Отмена</button>
            <button type="submit" class="submit-btn" :disabled="creating">
              {{ creating ? 'Создание...' : 'Создать' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'
import { hwApi } from '../api'
import NotificationsBell from '../components/NotificationsBell.vue'
import GlassHeader from '../components/GlassHeader.vue'

const router = useRouter()
const { fetchUser } = useAuth()
const user = ref(null)
const homeworks = ref([])
const loading = ref(true)

const isTeacher = computed(() => user.value?.role === 'teacher')

// Modal state
const showModal = ref(false)
const creating = ref(false)
const availableStudents = ref([])
const availableCourses = ref([])
const newHw = ref({
  course_id: '',
  title: '',
  description: '',
  ai_criteria: '',
  student_ids: []
})

onMounted(async () => {
  user.value = await fetchUser()
  if (!user.value) return router.push('/login')

  await loadHomeworks()
  if (isTeacher.value) {
    const stData = await hwApi.getStudents()
    availableStudents.value = stData
    try {
      const { apiFetch } = await import('../api')
      availableCourses.value = await apiFetch('/courses')
    } catch(e) { console.error('Failed to load courses', e) }
  }
})

async function loadHomeworks() {
  loading.value = true
  try {
    homeworks.value = await hwApi.getHomeworks()
  } catch(e) {
    console.error(e)
  }
  loading.value = false
}

function getMyStatus(hw) {
  if (isTeacher.value) return null
  const assignment = hw.assignments?.find(a => a.student_id === user.value.id)
  return assignment ? assignment.status : 'pending'
}

function formatStatus(status) {
  if (status === 'pending') return 'Ожидает'
  if (status === 'submitted') return 'На проверке'
  if (status === 'graded') return 'Оценено'
  return status
}

function excerpt(text) {
  const t = (text || '').replace(/\s+/g, ' ').trim()
  if (!t) return '—'
  return t.length > 72 ? t.slice(0, 72) + '…' : t
}

async function handleCreate() {
  if (!newHw.value.student_ids.length) return alert('Выберите хотя бы одного ученика!')
  creating.value = true
  try {
    await hwApi.createHomework(newHw.value)
    showModal.value = false
    newHw.value = { course_id: '', title: '', description: '', ai_criteria: '', student_ids: [] }
    await loadHomeworks()
  } catch(e) {
    alert(e.message)
  }
  creating.value = false
}
</script>

<style scoped>
.homeworks-view {
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
  margin-bottom: 32px;
}
.back-btn {
  display: flex; align-items: center; gap: 8px;
  background: none; border: none; color: #a1a1aa; cursor: pointer;
}
.back-btn:hover { color: #fff; }
.header-actions { display: flex; gap: 10px; align-items: center; }
.workshop-btn {
  background: #27272a; color: #e4e4e7; border: 1px solid #3f3f46;
  padding: 10px 16px; border-radius: 8px; cursor: pointer; font-weight: 500;
}
.workshop-btn:hover { border-color: #6366f1; color: #fff; }
.create-btn {
  background: #4f46e5; color: white; border: none; padding: 10px 16px;
  border-radius: 8px; cursor: pointer; font-weight: 500;
}
.create-btn:hover { background: #4338ca; }

.hw-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}
.hw-card {
  background: #18181b;
  border: 1px solid rgba(255,255,255,0.05);
  border-radius: 16px;
  padding: 20px;
  cursor: pointer;
  transition: transform 0.2s, border-color 0.2s;
}
.hw-card:hover {
  transform: translateY(-2px);
  border-color: rgba(99,102,241,0.5);
}
.hw-top {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;
  flex-wrap: wrap; gap: 8px;
}
.course-badge {
  background: #27272a; padding: 4px 8px; border-radius: 6px; font-size: 12px; color: #a1a1aa;
}
.demo-badge {
  background: rgba(99, 102, 241, 0.2);
  color: #a5b4fc;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
}
.status-badge {
  padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: 600;
}
.status-badge.pending { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
.status-badge.submitted { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.status-badge.graded { background: rgba(16, 185, 129, 0.15); color: #34d399; }

.hw-title { margin: 0 0 8px; font-size: 18px; }
.loading {
  text-align: center; color: var(--text-secondary); margin-top: 40px;
}
.empty-state {
  text-align: center;
  padding: 64px 24px;
  color: var(--text-muted);
  display: flex;
  flex-direction: column;
  align-items: center;
}
.empty-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 8px;
}
.empty-subtitle {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.5;
}
.hw-desc { margin: 0; color: #a1a1aa; font-size: 14px; line-height: 1.5; }
.hw-stats { margin-top: 16px; font-size: 13px; color: #818cf8; }

/* Modal */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.7);
  display: flex; align-items: center; justify-content: center; z-index: 100;
}
.modal-content {
  background: #18181b; padding: 24px; border-radius: 16px; width: 400px;
  border: 1px solid rgba(255,255,255,0.1);
}
.form-group { margin-bottom: 16px; }
.form-group label { display: block; margin-bottom: 6px; font-size: 14px; color: #a1a1aa; }
.form-group input, .form-group textarea, .course-select {
  width: 100%; background: #27272a; border: 1px solid #3f3f46;
  color: white; padding: 10px; border-radius: 8px; font-family: inherit;
}
.students-list {
  display: flex; flex-direction: column; gap: 8px; max-height: 150px; overflow-y: auto;
  background: #27272a; padding: 10px; border-radius: 8px; border: 1px solid #3f3f46;
}
.student-checkbox { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.modal-actions { display: flex; justify-content: flex-end; gap: 12px; margin-top: 24px; }
.cancel-btn { background: none; border: none; color: #a1a1aa; cursor: pointer; }
.submit-btn { background: #4f46e5; color: white; border: none; padding: 8px 16px; border-radius: 8px; cursor: pointer; }

@media (max-width: 640px) {
  .hw-grid { grid-template-columns: 1fr; }
  .modal-content { width: 90%; max-width: none; padding: 20px; }
  .header { flex-direction: column; align-items: flex-start; gap: 16px; }
}
</style>
