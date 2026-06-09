<template>
  <div class="builder-view fade-in" v-if="course">
    <!-- Header with Breadcrumb -->
    <div class="builder-header">
      <router-link to="/builder/courses" class="icon-btn back-btn">
        <span class="material-icons">arrow_back</span>
      </router-link>
      <div class="header-titles">
        <div class="breadcrumb">
          <router-link to="/builder/courses" class="breadcrumb-link">Конструктор</router-link>
          <span class="material-icons breadcrumb-icon">chevron_right</span>
          <span>{{ course.id }}</span>
        </div>
        <h1 class="glass-title course-title-main">
          <span class="material-icons course-title-icon" :style="{ color: course.color }">{{ course.icon || 'school' }}</span>
          {{ course.title }}
        </h1>
      </div>
      
      <div class="header-actions">
        <button @click="deleteCourse" class="glass-btn btn-danger">
          Удалить курс
        </button>
      </div>
    </div>

    <div class="builder-grid">
      <!-- Course Settings Sidebar -->
      <div class="sidebar">
        <div class="panel">
          <h2 class="panel-title">Настройки курса</h2>
          
          <div class="form-group">
            <label>Название</label>
            <input v-model="course.title" type="text" class="glass-input" />
          </div>

          <div class="form-group">
            <label>Описание</label>
            <textarea v-model="course.description" rows="4" class="glass-input"></textarea>
          </div>

          <div class="form-row">
            <div class="form-group half">
              <label>Иконка (Material)</label>
              <input v-model="course.icon" type="text" class="glass-input" />
            </div>
            <div class="form-group half">
              <label>Цвет (HEX)</label>
              <div class="color-input-wrapper">
                <input v-model="course.color" type="color" class="color-picker" />
                <input v-model="course.color" type="text" class="glass-input color-text" />
              </div>
            </div>
          </div>

          <div class="form-group">
            <label>Теги (через запятую)</label>
            <input v-model="tagsString" type="text" class="glass-input" placeholder="python, web, data" />
          </div>

          <button @click="saveCourse" :disabled="saving" class="glass-btn glass-btn-primary full-width-btn mt-4">
            <span v-if="saving" class="spinner-small"></span>
            {{ saving ? 'Сохранение...' : 'Сохранить изменения' }}
          </button>
        </div>
      </div>

      <!-- Lessons List -->
      <div class="main-content">
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">Уроки</h2>
              <p class="panel-subtitle">Учебные материалы курса</p>
            </div>
            <button @click="createLesson" class="glass-btn">
              <span class="material-icons" style="font-size: 18px; margin-right: 6px;">add</span> Добавить урок
            </button>
          </div>

          <div v-if="!course.lessons || course.lessons.length === 0" class="empty-lessons">
            <span class="material-icons empty-lessons-icon">article</span>
            <p>В этом курсе пока нет уроков</p>
            <button @click="createLesson" class="btn-link">Создать первый урок</button>
          </div>

          <div v-else class="lessons-list">
            <div
              v-for="(lesson, index) in course.lessons"
              :key="lesson.id"
              class="lesson-item"
              @click="editLesson(lesson.id)"
            >
              <div class="lesson-number">{{ index + 1 }}</div>
              <div class="lesson-info">
                <h3>{{ lesson.title }}</h3>
                <p>{{ lesson.duration || 'Время не указано' }}</p>
              </div>
              
              <div class="lesson-actions">
                <button @click.stop="deleteLesson(lesson.id)" class="icon-btn btn-danger-icon" title="Удалить">
                  <span class="material-icons" style="font-size: 18px;">delete</span>
                </button>
                <span class="material-icons chevron-icon">chevron_right</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  
  <div v-else class="loading-state">
    <div class="spinner"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { coursesApi } from '../../api.js'

const route = useRoute()
const router = useRouter()
const courseId = route.params.id

const course = ref(null)
const saving = ref(false)

const tagsString = computed({
  get: () => {
    if (!course.value || !course.value.tags) return ''
    if (typeof course.value.tags === 'string') {
      try {
        const parsed = JSON.parse(course.value.tags)
        if (Array.isArray(parsed)) return parsed.join(', ')
      } catch (e) {
        return course.value.tags
      }
    }
    if (Array.isArray(course.value.tags)) return course.value.tags.join(', ')
    return ''
  },
  set: (val) => {
    if (course.value) {
      course.value.tags = val.split(',').map(t => t.trim()).filter(Boolean)
    }
  }
})

async function fetchCourse() {
  try {
    course.value = await coursesApi.getCourse(courseId)
  } catch (err) {
    alert('Ошибка загрузки курса: ' + err.message)
    router.push('/builder/courses')
  }
}

async function saveCourse() {
  try {
    saving.value = true
    let tagsToSave = course.value.tags
    if (Array.isArray(tagsToSave)) {
      tagsToSave = JSON.stringify(tagsToSave)
    }
    
    const updateData = {
      title: course.value.title,
      description: course.value.description,
      icon: course.value.icon,
      color: course.value.color,
      tags: tagsToSave,
      duration: course.value.duration,
      instructor: course.value.instructor
    }
    const updated = await coursesApi.updateCourse(courseId, updateData)
    course.value = updated
  } catch (err) {
    alert('Ошибка сохранения: ' + err.message)
  } finally {
    saving.value = false
  }
}

async function deleteCourse() {
  if (!confirm('Вы уверены, что хотите удалить этот курс? Все уроки будут удалены. Действие необратимо!')) return
  try {
    await coursesApi.deleteCourse(courseId)
    router.push('/builder/courses')
  } catch (err) {
    alert('Ошибка удаления: ' + err.message)
  }
}

function createLesson() {
  router.push(`/builder/courses/${courseId}/lessons/new`)
}

function editLesson(lessonId) {
  router.push(`/builder/courses/${courseId}/lessons/${lessonId}`)
}

async function deleteLesson(lessonId) {
  if (!confirm('Удалить этот урок?')) return
  try {
    await coursesApi.deleteLesson(courseId, lessonId)
    await fetchCourse() // refresh list
  } catch (err) {
    alert('Ошибка при удалении: ' + err.message)
  }
}

onMounted(() => {
  fetchCourse()
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
  align-items: center;
  gap: 16px;
  margin-bottom: 32px;
}
.back-btn {
  background: var(--bg-surface-hover, #27272a);
  padding: 8px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
}
.header-titles {
  flex-grow: 1;
}
.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--text-muted, #a1a1aa);
  margin-bottom: 4px;
}
.breadcrumb-link {
  color: inherit;
  text-decoration: none;
}
.breadcrumb-link:hover {
  color: #fff;
}
.breadcrumb-icon {
  font-size: 14px;
}
.course-title-main {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 28px;
  margin: 0;
}
.course-title-icon {
  font-size: 28px;
}
.header-actions {
  margin-left: auto;
}
.btn-danger {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.3);
  color: #f87171;
}
.btn-danger:hover {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.5);
}
.builder-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 32px;
}
@media (min-width: 1024px) {
  .builder-grid {
    grid-template-columns: 1fr 2fr;
  }
}
.panel {
  background: var(--bg-surface, #18181b);
  border: 1px solid var(--border, #27272a);
  border-radius: 16px;
  padding: 24px;
}
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}
.panel-title {
  font-size: 20px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 8px;
}
.panel-subtitle {
  font-size: 14px;
  color: var(--text-muted, #a1a1aa);
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
.form-row {
  display: flex;
  gap: 16px;
}
.half {
  flex: 1;
}
.glass-input {
  width: 100%;
  background: var(--bg-panel, #09090b);
  border: 1px solid var(--border, #3f3f46);
  padding: 10px 16px;
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
.color-input-wrapper {
  display: flex;
  gap: 8px;
}
.color-picker {
  width: 40px;
  height: 40px;
  padding: 0;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  background: transparent;
}
.color-text {
  flex: 1;
}
.full-width-btn {
  width: 100%;
  justify-content: center;
}
.mt-4 {
  margin-top: 16px;
}
.empty-lessons {
  text-align: center;
  padding: 48px 20px;
  background: var(--bg-panel, #09090b);
  border: 1px dashed var(--border, #3f3f46);
  border-radius: 12px;
}
.empty-lessons-icon {
  font-size: 36px;
  color: var(--text-muted, #a1a1aa);
  margin-bottom: 8px;
}
.empty-lessons p {
  color: var(--text-muted, #a1a1aa);
  margin-bottom: 16px;
}
.btn-link {
  background: none;
  border: none;
  color: var(--primary, #4f46e5);
  cursor: pointer;
  font-weight: 500;
}
.btn-link:hover {
  color: var(--primary-hover, #4338ca);
}
.lessons-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.lesson-item {
  display: flex;
  align-items: center;
  background: var(--bg-panel, #09090b);
  border: 1px solid var(--border, #27272a);
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
}
.lesson-item:hover {
  border-color: var(--border-hover, #52525b);
}
.lesson-number {
  width: 32px;
  height: 32px;
  background: var(--bg-surface, #18181b);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted, #a1a1aa);
  font-weight: 500;
  margin-right: 16px;
  flex-shrink: 0;
}
.lesson-info {
  flex-grow: 1;
  min-width: 0;
}
.lesson-info h3 {
  color: #fff;
  font-size: 15px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
  transition: color 0.2s;
}
.lesson-item:hover .lesson-info h3 {
  color: var(--primary, #4f46e5);
}
.lesson-info p {
  color: var(--text-muted, #a1a1aa);
  font-size: 12px;
}
.lesson-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: 16px;
  opacity: 0;
  transition: opacity 0.2s;
}
.lesson-item:hover .lesson-actions {
  opacity: 1;
}
.btn-danger-icon {
  color: var(--text-muted, #a1a1aa);
}
.btn-danger-icon:hover {
  color: #f87171;
  background: rgba(239, 68, 68, 0.1);
}
.chevron-icon {
  color: var(--text-muted, #a1a1aa);
}
.loading-state {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 100px 0;
}
.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid var(--border, #3f3f46);
  border-top-color: var(--primary, #4f46e5);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
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
@keyframes spin { 100% { transform: rotate(360deg); } }
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
  background: var(--border, #52525b);
}
.glass-btn-primary {
  background: var(--primary, #4f46e5);
  border-color: var(--primary, #4f46e5);
}
.glass-btn-primary:hover {
  background: var(--primary-hover, #4338ca);
}
.icon-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 8px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
</style>
