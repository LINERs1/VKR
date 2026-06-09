<template>
  <div class="builder-view fade-in">
    <!-- Header with Breadcrumb -->
    <div class="builder-header">
      <router-link :to="`/builder/courses/${courseId}`" class="icon-btn back-btn">
        <span class="material-icons">arrow_back</span>
      </router-link>
      <div class="header-titles">
        <div class="breadcrumb">
          <router-link to="/builder/courses" class="breadcrumb-link">Конструктор</router-link>
          <span class="material-icons breadcrumb-icon">chevron_right</span>
          <router-link :to="`/builder/courses/${courseId}`" class="breadcrumb-link">{{ courseId }}</router-link>
          <span class="material-icons breadcrumb-icon">chevron_right</span>
          <span>Урок {{ isNew ? 'создание' : lessonId }}</span>
        </div>
        <h1 class="glass-title course-title-main">
          {{ isNew ? 'Новый урок' : 'Редактирование урока' }}
        </h1>
      </div>
      
      <div class="header-actions">
        <button
          @click="saveLesson"
          :disabled="saving || !lesson.title || !lesson.content"
          class="glass-btn glass-btn-primary"
        >
          <span v-if="saving" class="spinner-small"></span>
          <span v-else class="material-icons" style="font-size: 18px; margin-right: 6px;">save</span>
          Сохранить
        </button>
      </div>
    </div>

    <!-- Main Editor -->
    <div class="editor-container">
      <!-- Top Settings Bar -->
      <div class="editor-settings">
        <div class="form-group flex-grow">
          <label class="uppercase-label">Название урока</label>
          <input
            v-model="lesson.title"
            type="text"
            class="glass-input"
            placeholder="Введение в Python"
          />
        </div>
        <div class="form-group w-48">
          <label class="uppercase-label">Длительность</label>
          <input
            v-model="lesson.duration"
            type="text"
            class="glass-input"
            placeholder="15 минут"
          />
        </div>
      </div>

      <!-- Editor Content (WYSIWYG) -->
      <div class="editor-content-wrapper">
        <QuillEditor
          v-if="isEditorReady"
          v-model:content="lesson.content"
          contentType="html"
          theme="snow"
          toolbar="full"
          class="quill-editor"
        />
      </div>
    </div>
    <p class="editor-hint">Контент автоматически сохраняется в формате HTML для красивого отображения.</p>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { coursesApi } from '../../api.js'
import { QuillEditor } from '@vueup/vue-quill'
import '@vueup/vue-quill/dist/vue-quill.snow.css'

const route = useRoute()
const router = useRouter()
const courseId = route.params.id
const lessonId = route.params.lesson_id

const isNew = computed(() => lessonId === 'new')
const saving = ref(false)
const isEditorReady = ref(false)

const lesson = ref({
  title: '',
  duration: '10 минут',
  content: ''
})

async function fetchLesson() {
  if (!isNew.value) {
    try {
      const course = await coursesApi.getCourse(courseId)
      const found = course.lessons.find(l => l.id == lessonId)
      if (found) {
        lesson.value = { ...found }
      } else {
        throw new Error('Lesson not found')
      }
    } catch (err) {
      alert('Ошибка загрузки: ' + err.message)
      router.push(`/builder/courses/${courseId}`)
    }
  }
  // Delay editor mount slightly so it picks up initial content
  nextTick(() => {
    isEditorReady.value = true
  })
}

async function saveLesson() {
  try {
    saving.value = true
    const payload = {
      title: lesson.value.title,
      duration: lesson.value.duration,
      content: lesson.value.content
    }
    
    if (isNew.value) {
      await coursesApi.createLesson(courseId, payload)
    } else {
      await coursesApi.updateLesson(courseId, lessonId, payload)
    }
    
    router.push(`/builder/courses/${courseId}`)
  } catch (err) {
    alert('Ошибка при сохранении урока: ' + err.message)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  fetchLesson()
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
  font-size: 28px;
  margin: 0;
}
.header-actions {
  margin-left: auto;
}
.editor-container {
  background: var(--bg-surface, #18181b);
  border: 1px solid var(--border, #27272a);
  border-radius: 16px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 600px;
}
.editor-settings {
  background: var(--bg-panel, #09090b);
  border-bottom: 1px solid var(--border, #27272a);
  padding: 16px;
  display: flex;
  gap: 16px;
}
.flex-grow {
  flex-grow: 1;
}
.w-48 {
  width: 192px;
}
.form-group {
  display: flex;
  flex-direction: column;
}
.uppercase-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted, #a1a1aa);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 4px;
}
.glass-input {
  width: 100%;
  background: var(--bg-surface, #18181b);
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
.editor-content-wrapper {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
}
/* Quill Dark Theme Overrides */
:deep(.ql-toolbar.ql-snow) {
  background: var(--bg-surface, #18181b);
  border: none;
  border-bottom: 1px solid var(--border, #27272a);
  font-family: inherit;
  padding: 12px;
}
:deep(.ql-container.ql-snow) {
  background: rgba(9, 9, 11, 0.5);
  border: none;
  color: #fff;
  font-family: 'Inter', sans-serif;
  font-size: 15px;
  line-height: 1.6;
  min-height: 500px;
}
:deep(.ql-editor) {
  padding: 24px 32px;
}
:deep(.ql-editor.ql-blank::before) {
  color: var(--text-muted, #a1a1aa);
  font-style: normal;
}
:deep(.ql-snow .ql-stroke) {
  stroke: #a1a1aa;
}
:deep(.ql-snow .ql-fill) {
  fill: #a1a1aa;
}
:deep(.ql-snow .ql-picker) {
  color: #a1a1aa;
}
:deep(.ql-snow .ql-picker-options) {
  background: var(--bg-surface, #18181b);
  border: 1px solid var(--border, #3f3f46);
  color: #fff;
}
:deep(.ql-snow .ql-picker-item:hover) {
  color: var(--primary, #4f46e5);
}
:deep(.ql-snow .ql-picker-label:hover .ql-stroke) {
  stroke: var(--primary, #4f46e5);
}
:deep(.ql-snow .ql-picker-label:hover .ql-fill) {
  fill: var(--primary, #4f46e5);
}
:deep(.ql-snow .ql-picker-label:hover) {
  color: var(--primary, #4f46e5);
}
:deep(.ql-snow button:hover .ql-stroke),
:deep(.ql-snow button.ql-active .ql-stroke) {
  stroke: var(--primary, #4f46e5);
}
:deep(.ql-snow button:hover .ql-fill),
:deep(.ql-snow button.ql-active .ql-fill) {
  fill: var(--primary, #4f46e5);
}
:deep(.ql-editor h1) { font-size: 2em; margin-bottom: 0.5em; }
:deep(.ql-editor h2) { font-size: 1.5em; margin-bottom: 0.5em; }
:deep(.ql-editor pre) { 
  background: rgba(0,0,0,0.3); 
  padding: 16px; 
  border-radius: 8px; 
  color: #a1a1aa; 
}
:deep(.ql-editor blockquote) {
  border-left: 4px solid var(--primary, #4f46e5);
  padding-left: 16px;
  color: #a1a1aa;
}
.editor-hint {
  font-size: 12px;
  color: var(--text-muted, #a1a1aa);
  text-align: center;
  margin-top: 16px;
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
.glass-btn:hover:not(:disabled) {
  background: var(--border, #52525b);
}
.glass-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.glass-btn-primary {
  background: var(--primary, #4f46e5);
  border-color: var(--primary, #4f46e5);
}
.glass-btn-primary:hover:not(:disabled) {
  background: var(--primary-hover, #4338ca);
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
.icon-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-muted, #a1a1aa);
  transition: all 0.2s;
}
.icon-btn:hover {
  color: #fff;
}
</style>
