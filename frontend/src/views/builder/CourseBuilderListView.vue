<template>
  <div class="builder-view fade-in">
    <div class="builder-header">
      <div class="header-left">
        <router-link to="/" class="icon-btn back-btn" title="На главную">
          <span class="material-icons">arrow_back</span>
        </router-link>
        <div>
          <h1 class="glass-title">Конструктор Курсов</h1>
          <p class="builder-subtitle">Управляйте вашими курсами и учебными материалами</p>
        </div>
      </div>
      <button @click="showCreateModal = true" class="glass-btn glass-btn-primary">
        <span class="material-icons" style="font-size: 16px; margin-right: 6px;">add</span> Создать курс
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="error-state">
      {{ error }}
    </div>

    <!-- Empty State -->
    <div v-else-if="courses.length === 0" class="empty-state">
      <div class="empty-icon">
        <span class="material-icons">school</span>
      </div>
      <h3>Нет созданных курсов</h3>
      <p>Создайте свой первый курс, чтобы начать обучение студентов.</p>
    </div>

    <!-- Courses Grid -->
    <div v-else class="courses-grid">
      <div
        v-for="course in courses"
        :key="course.id"
        class="course-card"
        @click="goToCourse(course.id)"
      >
        <div class="course-card-header">
          <div class="course-icon" :style="{ backgroundColor: course.color + '20', color: course.color }">
            <span class="material-icons">{{ course.icon || 'school' }}</span>
          </div>
          <div class="course-title-wrapper">
            <h3 class="course-title">{{ course.title }}</h3>
            <p class="course-id">{{ course.id }}</p>
          </div>
        </div>
        
        <p class="course-desc">{{ course.description }}</p>
        
        <div class="course-card-footer">
          <div class="course-meta">
            <span class="material-icons" style="font-size: 16px;">menu_book</span>
            <span>{{ course.lessons_count || 0 }} уроков</span>
          </div>
          <div class="course-actions">
            <button @click.stop="editCourse(course.id)" class="icon-btn" title="Настроить">
              <span class="material-icons" style="font-size: 16px;">settings</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Create Course Modal -->
    <div v-if="showCreateModal" class="modal-overlay">
      <div class="modal-content">
        <h3 class="modal-title">Новый курс</h3>
        
        <div class="form-group">
          <label>ID курса (англ. без пробелов)</label>
          <input v-model="newCourse.id" type="text" class="glass-input" placeholder="например: python-basics" />
        </div>
        
        <div class="form-group">
          <label>Название курса</label>
          <input v-model="newCourse.title" type="text" class="glass-input" placeholder="Основы Python" />
        </div>

        <div class="form-group">
          <label>Краткое описание</label>
          <textarea v-model="newCourse.description" rows="3" class="glass-input" placeholder="Чему научатся студенты?"></textarea>
        </div>

        <div class="modal-actions">
          <button @click="showCreateModal = false" class="glass-btn">Отмена</button>
          <button @click="handleCreateCourse" :disabled="!newCourse.id || !newCourse.title || creating" class="glass-btn glass-btn-primary">
            <span v-if="creating" class="spinner-small"></span>
            Создать
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { coursesApi } from '../../api.js'

const router = useRouter()
const courses = ref([])
const loading = ref(true)
const error = ref(null)

const showCreateModal = ref(false)
const creating = ref(false)
const newCourse = ref({
  id: '',
  title: '',
  description: '',
  icon: 'school',
  color: '#3b82f6',
})

async function fetchCourses() {
  try {
    loading.value = true
    courses.value = await coursesApi.getCourses()
  } catch (err) {
    error.value = err.message || 'Ошибка загрузки курсов'
  } finally {
    loading.value = false
  }
}

async function handleCreateCourse() {
  try {
    creating.value = true
    const created = await coursesApi.createCourse(newCourse.value)
    courses.value.push(created)
    showCreateModal.value = false
    newCourse.value = { id: '', title: '', description: '', icon: 'school', color: '#3b82f6' }
    router.push(`/builder/courses/${created.id}`)
  } catch (err) {
    alert('Ошибка при создании курса: ' + (err.message || err))
  } finally {
    creating.value = false
  }
}

function goToCourse(id) {
  router.push(`/builder/courses/${id}`)
}

function editCourse(id) {
  router.push(`/builder/courses/${id}`)
}

onMounted(() => {
  fetchCourses()
})
</script>

<style scoped>
.builder-view {
  max-width: 1440px;
  margin: 0 auto;
  padding: 32px 24px;
}
.builder-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}
.back-btn {
  background: var(--bg-surface-hover, #27272a);
  padding: 8px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  border: 1px solid var(--border, #3f3f46);
  transition: all 0.2s;
}
.back-btn:hover {
  background: var(--primary, #4f46e5);
  border-color: var(--primary, #4f46e5);
  color: #fff;
}
.builder-subtitle {
  color: var(--text-muted, #a1a1aa);
  margin-top: 4px;
}
.loading-state, .error-state, .empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 64px 20px;
  text-align: center;
}
.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid var(--border, #3f3f46);
  border-top-color: var(--primary, #4f46e5);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin { 100% { transform: rotate(360deg); } }
.spinner-small {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  display: inline-block;
  margin-right: 8px;
}
.empty-icon {
  width: 64px;
  height: 64px;
  background: var(--bg-surface-hover, #27272a);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}
.empty-icon .material-icons {
  font-size: 32px;
  color: var(--text-muted, #a1a1aa);
}
.empty-state h3 {
  font-size: 20px;
  font-weight: 500;
  color: #fff;
  margin-bottom: 8px;
}
.empty-state p {
  color: var(--text-muted, #a1a1aa);
}
.courses-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 24px;
}
.course-card {
  background: linear-gradient(145deg, rgba(24, 24, 27, 0.7), rgba(9, 9, 11, 0.9));
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.05);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
  border-radius: 20px;
  padding: 24px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}
.course-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
}
.course-card:hover {
  transform: translateY(-4px);
  border-color: rgba(79, 70, 229, 0.4);
  box-shadow: 0 12px 40px rgba(79, 70, 229, 0.15);
}
.course-card-header {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}
.course-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  box-shadow: inset 0 2px 4px rgba(255,255,255,0.1);
  display: flex;
  align-items: center;
  justify-content: center;
}
.course-title {
  font-size: 18px;
  font-weight: 600;
  color: #fff;
}
.course-id {
  font-size: 13px;
  color: var(--text-muted, #a1a1aa);
}
.course-desc {
  color: var(--text-secondary, #d4d4d8);
  font-size: 14px;
  margin-bottom: 24px;
  flex-grow: 1;
}
.course-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid var(--border, #27272a);
  padding-top: 16px;
}
.course-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-muted, #a1a1aa);
  font-size: 14px;
}
.icon-btn {
  background: none;
  border: none;
  color: var(--text-muted, #a1a1aa);
  cursor: pointer;
  padding: 8px;
  border-radius: 8px;
  transition: all 0.2s;
}
.icon-btn:hover {
  background: var(--bg-surface-hover, #27272a);
  color: #fff;
}
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal-content {
  background: var(--bg-panel, #09090b);
  border: 1px solid var(--border, #27272a);
  border-radius: 16px;
  padding: 32px;
  width: 100%;
  max-width: 480px;
}
.modal-title {
  font-size: 24px;
  color: #fff;
  margin-bottom: 24px;
}
.form-group {
  margin-bottom: 16px;
}
.form-group label {
  display: block;
  font-size: 14px;
  color: var(--text-muted, #a1a1aa);
  margin-bottom: 8px;
}
.glass-input {
  width: 100%;
  background: var(--bg-surface, #18181b);
  border: 1px solid var(--border, #3f3f46);
  padding: 12px 16px;
  border-radius: 12px;
  color: #fff;
  font-family: inherit;
  font-size: 14px;
  transition: all 0.2s;
}
.glass-input:focus {
  outline: none;
  border-color: var(--primary, #4f46e5);
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 32px;
}
.glass-btn {
  background: var(--bg-surface-hover, #27272a);
  border: 1px solid var(--border, #3f3f46);
  color: #fff;
  padding: 10px 20px;
  border-radius: 12px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s;
  display: flex;
  align-items: center;
}
.glass-btn:hover {
  background: var(--border, #3f3f46);
}
.glass-btn-primary {
  background: var(--primary, #4f46e5);
  border-color: var(--primary, #4f46e5);
}
.glass-btn-primary:hover {
  background: var(--primary-hover, #4338ca);
}
</style>
