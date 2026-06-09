<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { marked } from 'marked'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'
import { useNotifications } from '../composables/useNotifications.js'
import { highlightSearchKey } from '../utils/highlightUtils.js'
import { adaptiveApi } from '../api'
import { getApiBaseUrl } from '../api'
import GlassHeader from '../components/GlassHeader.vue'

const route = useRoute()
const router = useRouter()
const { fetchUser } = useAuth()
const { addToast } = useNotifications()

const course = ref(null)
const weakBanner = ref(null)
const currentLesson = ref(null)
const loading = ref(true)
const notFound = ref(false)
const loadError = ref('')
const uploadStatus = ref('')
const uploadBusy = ref(false)
const fileInput = ref(null)
const selectedFiles = ref(null)

async function loadCourse(id) {
  loading.value = true
  notFound.value = false
  loadError.value = ''
  try {
    const res = await fetch(`/api/courses/${id}`)
    if (!res.ok) {
      notFound.value = true
      course.value = null
      loadError.value = res.status === 404
        ? `Курс «${id}» не найден на платформе.`
        : `Не удалось загрузить курс (ошибка ${res.status}).`
      return
    }
    course.value = await res.json()
    
    // Подхватываем урок из URL, если есть
    let targetLesson = course.value.lessons[0]
    if (route.query.lesson) {
      const id = Number(route.query.lesson)
      const found = course.value.lessons?.find((l) => l.id === id)
      if (found) targetLesson = found
    } else if (route.query.lesson_idx) {
      const idx = Number(route.query.lesson_idx)
      if (idx > 0 && idx <= (course.value.lessons?.length || 0)) {
        targetLesson = course.value.lessons[idx - 1]
        // Optionally update the URL to have the real lesson ID instead of idx
        router.replace({ query: { lesson: targetLesson.id } })
      }
    }
    currentLesson.value = targetLesson
    
    publishLessonContext()
    await loadWeakTopics()
  } catch (e) {
    notFound.value = true
    course.value = null
    loadError.value = 'Не удалось загрузить курс. Проверьте подключение к серверу.'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadCourse(route.params.id)
  if (typeof window !== 'undefined') {
    window.addEventListener('eduai-highlight-text', (e) => {
      const textToFind = e?.detail?.text || window.pendingHighlightText
      if (textToFind) {
        window.pendingHighlightText = null
        setTimeout(() => highlightAndScrollToText(textToFind), 600)
        setTimeout(() => highlightAndScrollToText(textToFind), 1400)
      }
    })
  }
})

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

watch(
  () => route.query.lesson_idx,
  (idxStr) => {
    if (!course.value || idxStr == null || idxStr === '') return
    const idx = Number(idxStr)
    if (idx > 0 && idx <= (course.value.lessons?.length || 0)) {
      const targetLesson = course.value.lessons[idx - 1]
      currentLesson.value = targetLesson
      router.replace({ query: { lesson: targetLesson.id } })
    }
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

async function loadWeakTopics() {
  try {
    const u = await fetchUser()
    if (!u || u.role !== 'student' || !course.value) {
      weakBanner.value = null
      return
    }
    weakBanner.value = await adaptiveApi.getWeakTopics(course.value.id)
  } catch {
    weakBanner.value = null
  }
}

function goToWeakLesson(item) {
  if (!item?.lesson_id || !course.value) return
  const lesson = course.value.lessons?.find((l) => l.id === item.lesson_id)
  if (lesson) {
    selectLesson(lesson)
    router.replace({ path: route.path, query: { ...route.query, lesson: item.lesson_id } })
  }
}

function selectLesson(lesson) {
  currentLesson.value = lesson
  router.replace({ query: { ...route.query, lesson: lesson.id } })
}
function prevLesson() { 
  if (hasPrev.value) selectLesson(course.value.lessons[currentIdx.value - 1]) 
}
function nextLesson() { 
  if (hasNext.value) selectLesson(course.value.lessons[currentIdx.value + 1]) 
}

watch(currentLesson, () => {
  publishLessonContext()
  
  if (window.pendingHighlightText) {
    const textToFind = window.pendingHighlightText;
    window.pendingHighlightText = null;
    
    setTimeout(() => highlightAndScrollToText(textToFind), 800);
    setTimeout(() => highlightAndScrollToText(textToFind), 1600);
  }
}, { flush: 'post' })

function highlightAndScrollToText(text) {
  if (!text) return false;
  console.log('[highlight] trying to highlight:', text);

  const tryKey = (wordLimit) => {
    const searchStr = highlightSearchKey(text, wordLimit);
    if (!searchStr) return null;
    return searchStr;
  };

  const normalize = (s) => String(s || '')
    .toLowerCase()
    .replace(/[.,/#!$%^&*;:{}=\-_`~()«»""''\n\r\t]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  const selectors = [
    'p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5',
    'td', 'blockquote', 'pre', 'code',
    'div', 'span'
  ];

  for (const wordLimit of [5, 4, 3, 2]) {
    const searchStr = tryKey(wordLimit);
    if (!searchStr) continue;
    console.log('[highlight] searching for:', searchStr);

    for (const sel of selectors) {
      const elements = document.querySelectorAll('.lesson-article ' + sel + ', .course-content ' + sel);
      for (const el of elements) {
        if (sel === 'div' || sel === 'span') {
          const hasBlock = el.querySelector('p, h1, h2, h3, h4, h5, li');
          if (hasBlock) continue;
        }
        const elNorm = normalize(el.innerText || el.textContent || '');
        if (elNorm.includes(searchStr)) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          el.classList.remove('ai-highlight-block');
          void el.offsetWidth;
          el.classList.add('ai-highlight-block');
          setTimeout(() => el.classList.remove('ai-highlight-block'), 5000);
          return true;
        }
      }
    }
  }

  console.warn('[highlight] text not found on page:', text);
  addToast('Фрагмент не найден на странице урока', 'warning');
  return false;
}

function onFilesChange(e) { selectedFiles.value = e.target.files }

async function uploadFiles() {
  if (!selectedFiles.value?.length) return
  uploadBusy.value = true
  uploadStatus.value = 'Загружаю…'
  try {
    const token = localStorage.getItem('token') || localStorage.getItem('eduai_token')
    let successCount = 0
    for (const f of Array.from(selectedFiles.value)) {
      const fd = new FormData()
      fd.append('file', f)
      fd.append('course_id', course.value.id)
      fd.append('source_type', 'methodology')
      const res = await fetch('/api/materials', { 
        method: 'POST', 
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
        body: fd 
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(errText || 'Ошибка загрузки')
      }
      successCount++
    }
    uploadStatus.value = `✅ Готово: загружено ${successCount} файлов. Они появятся у ИИ.`
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

// ── AI Tools (Lesson Summary + Quiz Generator) ──────────────────────────────
const aiPanel = ref(null) // null | 'summary' | 'quiz'
const aiResult = ref('')
const aiBusy = ref(false)
const aiError = ref('')

async function runAiTool(tool) {
  if (!currentLesson.value || !course.value) return
  aiPanel.value = tool
  aiResult.value = ''
  aiError.value = ''
  aiBusy.value = true

  const ctx = {
    courseId: course.value.id,
    lessonTitle: currentLesson.value.title,
    lessonContent: currentLesson.value.content || '',
  }

  let prompt = ''
  if (tool === 'summary') {
    prompt = `Сделай краткое резюме (3-5 ключевых пунктов) урока "${ctx.lessonTitle}" из курса "${course.value.title}". Используй только материалы этого урока. Отвечай на русском языке. Формат: маркированный список.`
  } else if (tool === 'quiz') {
    prompt = `Составь 4 вопроса с вариантами ответов (A, B, C, D) по уроку "${ctx.lessonTitle}" из курса "${course.value.title}". Для каждого вопроса укажи правильный ответ. Отвечай на русском языке.`
  }

  try {
    const token = localStorage.getItem('token')
    const baseUrl = getApiBaseUrl('/chat/stream')
    const res = await fetch(`${baseUrl}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        message: prompt,
        course_id: ctx.courseId,
        lesson_id: currentLesson.value.id,
        context: {},
      }),
    })

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop()
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const parsed = JSON.parse(line.slice(6))
          if (parsed.type === 'token' && parsed.content) {
            aiResult.value += parsed.content
          }
        } catch {}
      }
    }
  } catch (e) {
    aiError.value = `Ошибка: ${e.message}`
  } finally {
    aiBusy.value = false
  }
}

function closeAiPanel() {
  aiPanel.value = null
  aiResult.value = ''
  aiError.value = ''
}
</script>

<template>
  <div class="course-page" v-if="!loading && course">
    <!-- TOP NAVIGATION BAR -->
    <GlassHeader>
      <div style="display: flex; align-items: center; gap: 16px;">
        <button class="glass-back-btn" @click="router.push('/')">
          <span class="icon">←</span> Назад
        </button>
        <div class="header-divider" style="width:1px; height:24px; background:rgba(255,255,255,0.1);"></div>
        <div class="current-course-info" style="display:flex; align-items:center; gap:8px;">
          <span class="course-emoji">{{ course.icon }}</span>
          <h1 class="glass-title">{{ course.title }}</h1>
        </div>
      </div>
      <div class="header-right">
        <div class="ai-status" style="display:flex; align-items:center; gap:8px; font-size:13px; color:var(--text-secondary);">
          <span class="status-dot-sm"></span>
          <span class="status-text">EduAI активен</span>
        </div>
      </div>
    </GlassHeader>

    <div v-if="weakBanner?.items?.length" class="weak-topics-banner">
      <p class="weak-msg">{{ weakBanner.message }}</p>
      <ul class="weak-list">
        <li v-for="(w, wi) in weakBanner.items" :key="wi">
          <span>{{ w.topic }} — ошибок: {{ w.wrong_count }}</span>
          <button v-if="w.lesson_id" type="button" class="weak-btn" @click="goToWeakLesson(w)">
            Открыть урок
          </button>
        </li>
      </ul>
    </div>

    <div class="course-container">
      <!-- SIDEBAR -->
      <aside class="course-sidebar">
        <div class="sidebar-section">
          <h3 class="section-title">Программа курса</h3>
          <div class="lessons-list">
            <div
              v-for="(lesson, index) in course.lessons"
              :key="lesson.id"
              class="lesson-card"
              :class="{ active: currentLesson?.id === lesson.id }"
              @click="selectLesson(lesson)"
            >
              <div class="lesson-id">{{ index + 1 }}</div>
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
            <div class="lesson-meta">УРОК {{ currentIdx + 1 }} ИЗ {{ course.lessons.length }}</div>
            <h2 class="lesson-main-title">{{ currentLesson.title }}</h2>
            <div class="lesson-badges">
              <span class="badge">⏱ {{ currentLesson.duration }}</span>
              <span class="badge instructor">👤 {{ course.instructor }}</span>
            </div>

            <!-- AI Tools row -->
            <div class="ai-tools-row">
              <button
                class="ai-tool-btn"
                :class="{ active: aiPanel === 'summary' }"
                @click="aiPanel === 'summary' ? closeAiPanel() : runAiTool('summary')"
                :disabled="aiBusy"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                  <line x1="21" y1="10" x2="3" y2="10"/>
                  <line x1="21" y1="6" x2="3" y2="6"/>
                  <line x1="21" y1="14" x2="3" y2="14"/>
                  <line x1="21" y1="18" x2="10" y2="18"/>
                </svg>
                Резюме урока
              </button>
              <button
                class="ai-tool-btn"
                :class="{ active: aiPanel === 'quiz' }"
                @click="aiPanel === 'quiz' ? closeAiPanel() : runAiTool('quiz')"
                :disabled="aiBusy"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                  <circle cx="12" cy="12" r="10"/>
                  <path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/>
                  <line x1="12" y1="17" x2="12.01" y2="17"/>
                </svg>
                Проверь знания
              </button>
            </div>

            <!-- AI result panel -->
            <div v-if="aiPanel" class="ai-result-panel">
              <div class="arp-header">
                <span class="arp-title">
                  {{ aiPanel === 'summary' ? '✦ Резюме урока' : '✦ Вопросы по уроку' }}
                </span>
                <button class="arp-close" @click="closeAiPanel">✕</button>
              </div>
              <div v-if="aiBusy && !aiResult" class="arp-loading">
                <div class="arp-dots"><span></span><span></span><span></span></div>
                <span>{{ aiPanel === 'summary' ? 'Генерирую резюме...' : 'Составляю вопросы...' }}</span>
              </div>
              <div v-if="aiError" class="arp-error">{{ aiError }}</div>
              <div v-if="aiResult" class="arp-content" v-html="renderContent(aiResult)"></div>
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

  <div v-else-if="notFound" class="page-loader course-not-found">
    <div class="not-found-icon">📭</div>
    <h2 class="not-found-title">Курс не найден</h2>
    <p class="not-found-text">{{ loadError }}</p>
    <button type="button" class="not-found-btn" @click="router.push('/')">
      Вернуться на главную
    </button>
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

.weak-topics-banner {
  margin: 12px 24px 0;
  padding: 14px 18px;
  background: rgba(99, 102, 241, 0.12);
  border: 1px solid rgba(129, 140, 248, 0.35);
  border-radius: 10px;
}
.weak-msg {
  margin: 0 0 10px;
  color: #c7d2fe;
  font-size: 14px;
}
.weak-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.weak-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 0;
  font-size: 14px;
}
.weak-btn {
  background: #4f46e5;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 13px;
}
.weak-btn:hover {
  background: #6366f1;
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
  flex-shrink: 0;
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

@keyframes aiHighlightAnim {
  0% { background-color: rgba(234, 179, 8, 0.5); box-shadow: 0 0 15px rgba(234, 179, 8, 0.5); transform: scale(1.02); }
  100% { background-color: transparent; box-shadow: none; transform: scale(1); }
}

:deep(.ai-highlight-block),
.ai-highlight-block {
  animation: aiHighlightAnim 4s ease-out forwards;
  border-radius: 8px;
  padding: 4px;
  margin: -4px;
  display: inline-block;
}

.lesson-navigation {
  display: flex;
  justify-content: space-between;
  margin-top: 64px;
  padding-top: 32px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  margin-bottom: 80px;
}

.nav-btn {
  padding: 14px 28px;
  border-radius: 16px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  display: flex;
  align-items: center;
  gap: 12px;
}

.nav-btn.prev {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #a1a1aa;
}
.nav-btn.prev:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  transform: translateX(-4px);
}

.nav-btn.next {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  border: none;
  color: white;
  box-shadow: 0 8px 20px rgba(99, 102, 241, 0.3);
}
.nav-btn.next:hover:not(:disabled) {
  transform: translateX(4px);
  box-shadow: 0 12px 28px rgba(99, 102, 241, 0.5);
}
.nav-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
  transform: none !important;
  box-shadow: none !important;
}

/* ─── Loader ─────────────────────────────────── */
.course-not-found .not-found-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.course-not-found .not-found-title {
  margin: 0 0 8px;
  font-size: 22px;
  color: #f1f5f9;
}
.course-not-found .not-found-text {
  margin: 0 0 20px;
  color: #94a3b8;
  max-width: 420px;
  text-align: center;
  line-height: 1.5;
}
.not-found-btn {
  padding: 10px 20px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.06);
  color: #e2e8f0;
  cursor: pointer;
}
.not-found-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

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

/* ─── AI Tools ─────────────────────────────── */
.ai-tools-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 20px;
}

.ai-tool-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 8px 14px;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 8px;
  color: #a5b4fc;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s;
}
.ai-tool-btn:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.15);
  border-color: rgba(99, 102, 241, 0.4);
  color: #c7d2fe;
}
.ai-tool-btn.active {
  background: rgba(99, 102, 241, 0.18);
  border-color: rgba(99, 102, 241, 0.5);
  color: #e0e7ff;
}
.ai-tool-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.ai-result-panel {
  margin-top: 20px;
  background: rgba(99, 102, 241, 0.06);
  border: 1px solid rgba(99, 102, 241, 0.18);
  border-radius: 14px;
  overflow: hidden;
}

.arp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(99, 102, 241, 0.12);
}

.arp-title {
  font-size: 13px;
  font-weight: 700;
  color: #a5b4fc;
  letter-spacing: 0.01em;
}

.arp-close {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  font-size: 14px;
  padding: 2px 6px;
  border-radius: 5px;
  transition: all 0.15s;
}
.arp-close:hover { color: #e2e8f0; background: rgba(255,255,255,0.06); }

.arp-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px;
  color: #64748b;
  font-size: 14px;
}

.arp-dots {
  display: flex;
  gap: 4px;
}
.arp-dots span {
  width: 6px; height: 6px;
  background: #6366f1;
  border-radius: 50%;
  animation: dot-bounce 1.4s infinite;
}
.arp-dots span:nth-child(2) { animation-delay: 0.2s; }
.arp-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes dot-bounce {
  0%, 80%, 100% { transform: scale(0.7); opacity: 0.4; }
  40% { transform: scale(1.1); opacity: 1; }
}

.arp-error {
  padding: 14px 16px;
  color: #fca5a5;
  font-size: 14px;
}

.arp-content {
  padding: 16px;
  font-size: 15px;
  line-height: 1.7;
  color: #cbd5e1;
}

.arp-content :deep(ul) { padding-left: 20px; margin: 0 0 12px; }
.arp-content :deep(li) { margin-bottom: 6px; }
.arp-content :deep(strong) { color: #e2e8f0; }
.arp-content :deep(p) { margin: 0 0 10px; }
.arp-content :deep(h3) { font-size: 15px; color: #e2e8f0; margin: 14px 0 8px; }

/* ─── Responsive Design ──────────────────────── */
@media (max-width: 900px) {
  .course-container {
    flex-direction: column;
    overflow-y: auto;
  }
  .course-sidebar {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    padding: 20px;
    overflow-y: visible;
  }
  .lessons-list {
    flex-direction: row;
    overflow-x: auto;
    padding-bottom: 12px;
    gap: 12px;
    -webkit-overflow-scrolling: touch;
  }
  .lesson-card {
    min-width: 240px;
    flex: 0 0 auto;
  }
  .course-content {
    padding: 24px 16px 80px;
    overflow-y: visible;
  }
  .lesson-main-title {
    font-size: 32px;
  }
  .lesson-navigation {
    flex-direction: column;
    gap: 16px;
  }
  .nav-btn {
    width: 100%;
    justify-content: center;
  }
}
</style>
