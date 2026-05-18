<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { marked } from 'marked'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const course = ref(null)
const currentLesson = ref(null)
const loading = ref(true)
const uploadStatus = ref('')
const uploadBusy = ref(false)
const fileInput = ref(null)
const selectedFiles = ref(null)

async function loadCourse(id) {
  loading.value = true
  try {
    const res = await fetch(`/api/courses/${id}`)
    if (!res.ok) { router.push('/'); return }
    course.value = await res.json()
    currentLesson.value = course.value.lessons[0]
    publishLessonContext()
  } catch (e) {
    router.push('/')
  } finally {
    loading.value = false
  }
}

onMounted(() => loadCourse(route.params.id))

watch(() => route.params.id, (newId) => {
  if (newId) loadCourse(newId)
})

watch(
  () => route.query.lesson,
  (lessonId) => {
    if (!course.value || lessonId == null || lessonId === '') return
    const id = Number(lessonId)
    const lesson = course.value.lessons?.find((l) => l.id === id)
    if (lesson) currentLesson.value = lesson
  },
)

const currentIdx = computed(() =>
  course.value ? course.value.lessons.findIndex(l => l.id === currentLesson.value?.id) : -1
)
const hasPrev = computed(() => currentIdx.value > 0)
const hasNext = computed(() => currentIdx.value < (course.value?.lessons.length ?? 0) - 1)

function publishLessonContext() {
  if (!course.value || !currentLesson.value) return
  const idx = currentIdx.value >= 0 ? currentIdx.value : 0
  window.currentCourseLessonContext = {
    courseId: course.value.id,
    lessonId: currentLesson.value.id,
    lessonTitle: currentLesson.value.title,
    lessonIndex: idx + 1,
    totalLessons: course.value.lessons.length,
  }
  window.currentCourseLessons = (course.value.lessons || []).map((l) => ({
    id: l.id,
    title: l.title,
    courseId: course.value.id,
  }))
  window.dispatchEvent(new CustomEvent('eduai-lesson-changed'))
}

function selectLesson(lesson) { currentLesson.value = lesson }
function prevLesson() { if (hasPrev.value) currentLesson.value = course.value.lessons[currentIdx.value - 1] }
function nextLesson() { if (hasNext.value) currentLesson.value = course.value.lessons[currentIdx.value + 1] }

watch(currentLesson, () => publishLessonContext(), { flush: 'post' })

function onFilesChange(e) { selectedFiles.value = e.target.files }

async function uploadFiles() {
  if (!selectedFiles.value?.length) return
  uploadBusy.value = true
  uploadStatus.value = 'Загружаю…'
  try {
    const fd = new FormData()
    for (const f of Array.from(selectedFiles.value)) fd.append('files', f)
    const res = await fetch(`/api/ingest/upload?course_id=${course.value.id}`, { method: 'POST', body: fd })
    if (!res.ok) throw new Error(await res.text())
    const data = await res.json()
    uploadStatus.value = `✅ Готово: ${data.chunks ?? '?'} чанков проиндексировано`
  } catch (e) {
    uploadStatus.value = `❌ Ошибка: ${e.message}`
  } finally {
    uploadBusy.value = false
  }
}

async function indexServerDir() {
  uploadBusy.value = true
  uploadStatus.value = 'Индексирую…'
  try {
    const res = await fetch(`/api/ingest/directory?course_id=${course.value.id}`, { method: 'POST' })
    const data = await res.json()
    uploadStatus.value = `✅ Готово: ${data.chunks ?? '?'} чанков`
  } catch (e) {
    uploadStatus.value = `❌ Ошибка: ${e.message}`
  } finally {
    uploadBusy.value = false
  }
}

// Use marked for safe and fast markdown rendering
function renderContent(text) {
  if (!text) return ''
  return marked.parse(text)
}
</script>

<template>
  <div class="course-page" v-if="!loading && course">
    <!-- TOP NAVIGATION BAR -->
    <header class="course-header">
      <div class="header-left">
        <button class="back-btn" @click="router.push('/')">
          <span class="icon">←</span> Назад
        </button>
        <div class="header-divider"></div>
        <div class="current-course-info">
          <span class="course-emoji">{{ course.icon }}</span>
          <h1 class="course-name">{{ course.title }}</h1>
        </div>
      </div>
      <div class="header-right">
        <div class="ai-status">
          <span class="status-dot"></span>
          <span class="status-text">EduAI активен</span>
        </div>
      </div>
    </header>

    <div class="course-container">
      <!-- SIDEBAR -->
      <aside class="course-sidebar">
        <div class="sidebar-section">
          <h3 class="section-title">Программа курса</h3>
          <div class="lessons-list">
            <div
              v-for="lesson in course.lessons"
              :key="lesson.id"
              class="lesson-card"
              :class="{ active: currentLesson?.id === lesson.id }"
              @click="selectLesson(lesson)"
            >
              <div class="lesson-id">{{ lesson.id }}</div>
              <div class="lesson-details">
                <div class="lesson-card-title">{{ lesson.title }}</div>
                <div class="lesson-card-meta">⏱ {{ lesson.duration }}</div>
              </div>
            </div>
          </div>
        </div>

        <div class="sidebar-section materials-section">
          <h3 class="section-title">Материалы</h3>
          <div class="upload-box">
            <p class="upload-hint">Загрузите PDF или TXT для ИИ-анализа</p>
            <input
              ref="fileInput"
              type="file"
              multiple
              accept=".pdf,.docx,.txt,.md"
              style="display:none"
              @change="onFilesChange"
            />
            <button class="action-btn outline" :disabled="uploadBusy" @click="fileInput.click()">
              📁 Выбрать файлы
            </button>
            <button
              v-if="selectedFiles?.length"
              class="action-btn primary"
              :disabled="uploadBusy"
              @click="uploadFiles"
            >
              ⬆️ Загрузить ({{ selectedFiles.length }})
            </button>
            <button class="action-btn text-link" :disabled="uploadBusy" @click="indexServerDir">
              🔄 Обновить индекс
            </button>
            <div v-if="uploadStatus" class="status-msg">{{ uploadStatus }}</div>
          </div>
        </div>
      </aside>

      <!-- MAIN CONTENT -->
      <main class="course-content">
        <div class="content-wrapper" v-if="currentLesson">
          <div class="lesson-header">
            <div class="lesson-meta">УРОК {{ currentLesson.id }} ИЗ {{ course.lessons.length }}</div>
            <h2 class="lesson-main-title">{{ currentLesson.title }}</h2>
            <div class="lesson-badges">
              <span class="badge">⏱ {{ currentLesson.duration }}</span>
              <span class="badge instructor">👤 {{ course.instructor }}</span>
            </div>
          </div>

          <div class="lesson-article" v-if="currentLesson?.content" v-html="renderContent(currentLesson.content)"></div>

          <div class="lesson-navigation">
            <button class="nav-btn prev" :disabled="!hasPrev" @click="prevLesson">
              ← Назад
            </button>
            <button class="nav-btn next" :disabled="!hasNext" @click="nextLesson">
              Следующий урок →
            </button>
          </div>
        </div>
      </main>
    </div>
  </div>

  <div v-else-if="loading" class="page-loader">
    <div class="loader-spinner"></div>
    <div class="loader-text">Синхронизируем материалы…</div>
  </div>
</template>

<style scoped>
.course-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #0a0f1d;
  color: #e2e8f0;
  overflow: hidden;
}

/* ─── Header ─────────────────────────────────── */
.course-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  height: 64px;
  background: rgba(15, 23, 42, 0.95);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-btn {
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: color 0.2s;
}

.back-btn:hover { color: #fff; }

.header-divider {
  width: 1px;
  height: 24px;
  background: rgba(255, 255, 255, 0.1);
}

.current-course-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.course-emoji { font-size: 20px; }
.course-name { font-size: 16px; font-weight: 700; margin: 0; }

.ai-status {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(16, 185, 129, 0.1);
  padding: 6px 12px;
  border-radius: 20px;
  border: 1px solid rgba(16, 185, 129, 0.2);
}

.status-dot {
  width: 8px;
  height: 8px;
  background: #10b981;
  border-radius: 50%;
  box-shadow: 0 0 10px #10b981;
}

.status-text {
  font-size: 12px;
  font-weight: 600;
  color: #10b981;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* ─── Layout ─────────────────────────────────── */
.course-container {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* ─── Sidebar ────────────────────────────────── */
.course-sidebar {
  width: 320px;
  background: rgba(15, 23, 42, 0.4);
  border-right: 1px solid rgba(255, 255, 255, 0.05);
  display: flex;
  flex-direction: column;
  padding: 24px;
  overflow-y: auto;
}

.sidebar-section { margin-bottom: 32px; }
.section-title {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: #64748b;
  margin-bottom: 16px;
  font-weight: 700;
}

.lessons-list { display: flex; flex-direction: column; gap: 8px; }

.lesson-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.lesson-card:hover { background: rgba(255, 255, 255, 0.03); }
.lesson-card.active {
  background: rgba(99, 102, 241, 0.1);
  border-color: rgba(99, 102, 241, 0.3);
}

.lesson-id {
  width: 28px;
  height: 28px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: #94a3b8;
}

.active .lesson-id { background: #6366f1; color: white; }

.lesson-card-title { font-size: 14px; font-weight: 600; margin-bottom: 2px; }
.lesson-card-meta { font-size: 12px; color: #64748b; }

.upload-box {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 16px;
  padding: 16px;
  border: 1px dashed rgba(255, 255, 255, 0.1);
}

.upload-hint { font-size: 12px; color: #64748b; margin-bottom: 12px; line-height: 1.4; }

.action-btn {
  width: 100%;
  padding: 10px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  margin-bottom: 8px;
  transition: all 0.2s;
}

.action-btn.outline {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #e2e8f0;
}

.action-btn.primary {
  background: #6366f1;
  border: none;
  color: white;
}

.action-btn.text-link {
  background: transparent;
  border: none;
  color: #6366f1;
  font-size: 12px;
}

/* ─── Main Content ───────────────────────────── */
.course-content {
  flex: 1;
  overflow-y: auto;
  padding: 40px;
  display: flex;
  justify-content: center;
}

.content-wrapper {
  max-width: 800px;
  width: 100%;
}

.lesson-header { margin-bottom: 40px; }
.lesson-meta {
  font-size: 12px;
  font-weight: 800;
  color: #6366f1;
  letter-spacing: 0.1em;
  margin-bottom: 12px;
}

.lesson-main-title {
  font-size: 48px;
  font-weight: 800;
  margin: 0 0 24px;
  line-height: 1.1;
}

.lesson-badges { display: flex; gap: 12px; }
.badge {
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 20px;
  font-size: 12px;
  color: #94a3b8;
}

.badge.instructor { background: rgba(99, 102, 241, 0.1); color: #818cf8; }

.lesson-article {
  font-size: 18px;
  line-height: 1.8;
  color: #cbd5e1;
}

.lesson-article :deep(h2) { font-size: 32px; color: #fff; margin: 48px 0 24px; }
.lesson-article :deep(p) { margin-bottom: 24px; }
.lesson-article :deep(pre) {
  background: #0f172a;
  padding: 24px;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.05);
  overflow-x: auto;
  margin: 32px 0;
}

.lesson-navigation {
  display: flex;
  justify-content: space-between;
  margin-top: 64px;
  padding-top: 32px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.nav-btn {
  padding: 12px 24px;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.nav-btn.prev { background: transparent; border: 1px solid rgba(255, 255, 255, 0.1); color: #fff; }
.nav-btn.next { background: #6366f1; border: none; color: white; }
.nav-btn:disabled { opacity: 0.3; cursor: not-allowed; }

/* ─── Loader ─────────────────────────────────── */
.page-loader {
  height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #0a0f1d;
}

.loader-spinner {
  width: 48px;
  height: 48px;
  border: 4px solid rgba(99, 102, 241, 0.1);
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 24px;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>
