<script setup>
import { ref, nextTick, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { UltravoxSession, AgentReaction } from 'ultravox-client'
import { useAuth } from '../composables/useAuth'
import { hwApi, chatApi, analyticsApi, notificationsApi } from '../api'
import { checkingAssignments } from '../composables/useNotifications.js'

const route = useRoute()
const router = useRouter()
const { user, fetchUser } = useAuth()

// ─── Page & Course Context ────────────────────────────────────────────────
const courseId   = ref('default')
const courseName = ref('EduAI')
const courseIcon = ref('🤖')
const currentPage = ref('home')
const allCourses  = ref([])
const homeworkReminder = ref('')

async function loadHomeworkReminders() {
  try {
    const u = user.value || (await fetchUser())
    if (!u) return
    const r = await hwApi.getReminders()
    const active =
      u.role === 'teacher'
        ? (r.pending_review_count || r.not_submitted_count)
        : (r.pending_count || r.waiting_count)
    if (active && r.message) homeworkReminder.value = r.message
  } catch (_) {}
}

async function loadAllCourses() {
  try {
    const res = await fetch('/api/courses')
    if (res.ok) allCourses.value = await res.json()
  } catch (e) {}
}

function getActiveLessonContext() {
  const ctx = window.currentCourseLessonContext
  if (!ctx || !courseId.value || ctx.courseId !== courseId.value) return null
  return ctx
}

function quizLetterForVoice(oi) {
  return String.fromCharCode(65 + oi)
}

function formatHomeworkPageText(hw) {
  const lines = [`Домашнее задание: ${hw.title}`]
  if (hw.intro) {
    lines.push('', 'УСЛОВИЕ:', hw.intro)
  }
  if (hw.codeTemplate) {
    lines.push('', `ШАБЛОН КОДА (${hw.codeFilename || 'solution.py'}):`, hw.codeTemplate)
  }
  const items = hw.quizItems || []
  if (items.length) {
    lines.push('', 'ТЕСТОВАЯ ЧАСТЬ (вопросы с вариантами):')
    items.forEach((q, qi) => {
      lines.push(`${qi + 1}. ${q.question}`)
      ;(q.options || []).forEach((opt, oi) => {
        lines.push(`   ${quizLetterForVoice(oi)}) ${opt}`)
      })
      if (q.correct_index != null && q.options?.[q.correct_index] != null) {
        lines.push(`   Верный вариант: ${quizLetterForVoice(q.correct_index)}) ${q.options[q.correct_index]}`)
      }
    })
  }
  if (hw.writtenPart) {
    lines.push('', 'ПИСЬМЕННАЯ ЧАСТЬ ЗАДАНИЯ:', hw.writtenPart)
  }
  const a = hw.assignment
  if (a) {
    lines.push('', `--- Ответ ученика (${a.student}, статус: ${a.status}) ---`)
    if (a.status === 'graded' && a.grade != null) {
      lines.push(`ОЦЕНКА: ${a.grade} из 5`)
      const fb = a.teacher_feedback
        ? stripHtmlForSpeech(a.teacher_feedback).slice(0, 600)
        : ''
      if (fb) lines.push('ОТЗЫВ ПРЕПОДАВАТЕЛЯ:', fb)
    }
    lines.push('', 'КОД УЧЕНИКА:', a.code || '(нет)')
    if (items.length) {
      lines.push('', 'ОТВЕТЫ УЧЕНИКА НА ТЕСТЫ:')
      items.forEach((q, qi) => {
        const picked = a.quiz?.[String(qi)] ?? a.quiz?.[qi]
        const pickStr =
          picked != null && q.options?.[picked] != null
            ? `${quizLetterForVoice(picked)}) ${q.options[picked]}`
            : '(не выбрано)'
        lines.push(`${qi + 1}. ${pickStr}`)
      })
    }
    lines.push('', 'ПИСЬМЕННАЯ ЧАСТЬ УЧЕНИКА:', a.text || '(нет)')
  }
  return lines.join('\n')
}

function getPageText() {
  try {
    const hw = window.currentHomeworkContext
    if (hw && route.path.startsWith('/homeworks/')) {
      return formatHomeworkPageText(hw).slice(0, 2200)
    }

    const lessonEl =
      document.querySelector('.course-content .content-wrapper') ||
      document.querySelector('.course-content') ||
      document.querySelector('main')
    const el = lessonEl || document.querySelector('#app') || document.body
    return (el.innerText || '').slice(0, 1500)
  } catch (e) { return '' }
}

function lessonContextFields() {
  const lesson = getActiveLessonContext()
  if (!lesson) return {}
  return {
    lesson_id: lesson.lessonId != null ? String(lesson.lessonId) : null,
    lesson_title: lesson.lessonTitle || null,
    lesson_index: lesson.lessonIndex != null ? Number(lesson.lessonIndex) : null,
    total_lessons: lesson.totalLessons != null ? Number(lesson.totalLessons) : null,
  }
}

function homeworkContextFields() {
  const hw = window.currentHomeworkContext
  if (!hw?.assignment || !route.path.startsWith('/homeworks/')) return {}
  const a = hw.assignment
  return {
    homework_id: hw.homeworkId ?? null,
    assignment_id: a.id,
    assignment_student: a.student,
    assignment_status: a.status,
    assignment_grade: a.grade ?? null,
  }
}

const pageContext = computed(() => ({
  current_path: route.path,
  current_page: currentPage.value,
  current_course_id:   courseId.value !== 'default' ? courseId.value : null,
  current_course_name: courseId.value !== 'default' ? courseName.value : null,
  ...lessonContextFields(),
  available_courses: allCourses.value.map(c => ({
    id: c.id, title: c.title, icon: c.icon || '', description: c.description || ''
  }))
}))

/** Синхронизирует currentPage/courseId с фактическим URL (в т.ч. после навигации без активного ассистента). */
async function refreshPageContextFromRoute() {
  const path = route.path
  const id = route.params.id

  if (path.startsWith('/homeworks/workshop')) {
    currentPage.value = id ? 'Редактор шаблона ДЗ' : 'Мастерская домашних заданий'
    courseId.value = 'default'
    courseName.value = 'Мастерская ДЗ'
    courseIcon.value = '🛠️'
    return
  }

  if (/^\/homeworks\/\d+/.test(path)) {
    currentPage.value = 'Домашнее задание'
    const hw = window.currentHomeworkContext
    courseId.value = hw?.courseId || 'default'
    courseName.value = hw?.title || 'Домашнее задание'
    courseIcon.value = '📝'
    return
  }

  if (path === '/homeworks' || path.startsWith('/homeworks')) {
    currentPage.value = 'Список домашних заданий'
    courseId.value = 'default'
    courseName.value = 'Домашние задания'
    courseIcon.value = '📝'
    return
  }

  if (path.startsWith('/courses/') && id) {
    currentPage.value = 'Курс'
    try {
      const token = localStorage.getItem('token')
      const headers = token ? { Authorization: `Bearer ${token}` } : {}
      const res = await fetch(`/api/courses/${id}`, { headers })
      if (res.ok) {
        const data = await res.json()
        courseId.value = data.id
        courseName.value = data.title
        courseIcon.value = data.icon || '📚'
      }
    } catch (e) {
      console.warn('[page context] course fetch failed', e)
    }
    return
  }

  if (path.startsWith('/journal')) {
    currentPage.value = 'Журнал успеваемости'
    courseId.value = 'default'
    courseName.value = 'Журнал'
    courseIcon.value = '📊'
    window.currentCourseLessonContext = null
    return
  }

  if (path.startsWith('/students/') && id) {
    currentPage.value = 'Профиль ученика'
    courseId.value = 'default'
    courseName.value = 'Профиль ученика'
    courseIcon.value = '👤'
    window.currentCourseLessonContext = null
    return
  }

  if (path.startsWith('/profile')) {
    currentPage.value = 'Профиль пользователя'
    courseId.value = 'default'
    courseName.value = 'Профиль'
    courseIcon.value = '👤'
    window.currentCourseLessonContext = null
    return
  }

  if (path === '/') {
    currentPage.value = 'Главная страница'
    courseId.value = 'default'
    courseName.value = 'EduAI'
    courseIcon.value = '🤖'
    window.currentCourseLessonContext = null
    return
  }

  if (!path.startsWith('/courses/')) {
    window.currentCourseLessonContext = null
  }
  currentPage.value = 'Страница приложения'
  courseId.value = 'default'
  courseName.value = 'EduAI'
  courseIcon.value = '🤖'
}

watch(
  () => [route.path, route.params.id, route.fullPath],
  async () => {
    await refreshPageContextFromRoute()
    await loadChatHistory()
    if (voiceMode.value) {
      if (skipNextRouteContextPush) {
        skipNextRouteContextPush = false
      } else {
        scheduleVoicePageContextPush(200, true)
      }
    }
  },
  { immediate: true },
)

if (typeof window !== 'undefined') {
  window.addEventListener('eduai-homework-context', () => {
    if (route.path.startsWith('/homeworks/')) {
      void refreshPageContextFromRoute().then(() => {
        if (voiceMode.value) scheduleVoicePageContextPush(200, true)
      })
    }
  })
}

// ─── Text Chat State ───────────────────────────────────────────────────────
const isOpen    = ref(false)
const history   = ref([])
const message   = ref('')

async function loadChatHistory() {
  const cid = courseId.value
  if (!cid || cid === 'default') {
    history.value = []
    return
  }
  try {
    const u = user.value || (await fetchUser())
    if (!u) return
    const rows = await chatApi.getHistory(cid, 12)
    if (courseId.value !== cid) return
    history.value = (rows || []).map((r) => ({ role: r.role, content: r.content, sources: [] }))
  } catch (_) {}
}

function recordNavMetric(success, path) {
  analyticsApi
    .postEvent({
      event_type: 'voice_navigation',
      course_id: courseId.value !== 'default' ? courseId.value : null,
      success: !!success,
      meta: { path: String(path || '').slice(0, 200) },
    })
    .catch(() => {})
}

const isBusy    = ref(false)
const errorText = ref('')
const threadEl  = ref(null)

// UX #7: переключатель TTS
const ttsEnabled = ref(true)

const canSend = computed(() => message.value.trim().length > 0 && !isBusy.value)

function togglePanel() {
  if (voiceMode.value) { stopVoiceMode(); return }
  const opening = !isOpen.value
  isOpen.value = opening
  if (opening) void refreshPageContextFromRoute()
}
function closePanel() { isOpen.value = false }

async function scrollBottom() {
  await nextTick()
  if (threadEl.value) threadEl.value.scrollTop = threadEl.value.scrollHeight
}

// ─── Voice Mode State (Ultravox) ──────────────────────────────────────────
const voiceMode          = ref(false)
const voiceState         = ref('IDLE')  // IDLE | LISTENING | THINKING | SPEAKING
const voiceTranscript    = ref('')
const voiceAssistantText = ref('')
const voiceError         = ref('')
const micVolume          = ref(0)
const lastAssistantText  = ref('')
const wakeFlash          = ref(false)
const isHearingSpeech    = ref(false)

// Ultravox session
let uvSession = null
let uvStatusCleanup = null
let voiceSessionId = null
let voiceContextTimer = null
let lastPushedVoiceContextKey = ''
let voiceHistorySyncedOrdinals = new Set()
const VOICE_VOLUME_KEY = 'eduai_voice_volume'
const voiceVolume = ref(parseFloat(localStorage.getItem(VOICE_VOLUME_KEY) || '0.45'))
const voiceVolumePct = computed({
  get: () => Math.round(voiceVolume.value * 100),
  set: (v) => { voiceVolume.value = Math.max(0, Math.min(1, Number(v) / 100)) },
})
let lastVoiceNavPath = null
let voiceUserHasSpoken = false
const VOICE_IDLE_MS = 30_000
let voiceIdleTimer = null
let pendingNavPath = null
let skipNextRouteContextPush = false
let voiceNavHandledAt = 0

function markVoiceNavHandled() {
  voiceNavHandledAt = Date.now()
}

function isRecentVoiceNav() {
  return Date.now() - voiceNavHandledAt < 3500
}

const STATIC_NAV_PATHS = ['/', '/profile', '/journal', '/homeworks', '/analytics', '/homeworks/workshop']
const VOICE_YES_RE = /\b(да|давай|ок|окей|конечно|переводи|открывай|хорошо|ага|угу)\b/ui
const HIDDEN_VOICE_CTX_RE = /^\[СИСТЕМА:\s*обновление контекста/i

/** Служебные sendText при смене страницы/урока — не показывать в sub-island */
function isHiddenVoiceContextMessage(text) {
  const t = (text || '').trim()
  if (!t) return false
  if (HIDDEN_VOICE_CTX_RE.test(t)) return true
  if (t.startsWith('Пользователь сейчас здесь:') && t.includes('Содержимое экрана')) return true
  return false
}

function isAutoContextTranscript(entry) {
  if (!entry || entry.speaker !== 'user') return false
  if (entry.medium === 'text' && isHiddenVoiceContextMessage(entry.text)) return true
  return isHiddenVoiceContextMessage(entry.text)
}

function lastVisibleUserTranscript(transcripts) {
  for (let i = transcripts.length - 1; i >= 0; i--) {
    const entry = transcripts[i]
    if (entry.speaker === 'user' && !isAutoContextTranscript(entry)) {
      return (entry.text || '').trim()
    }
  }
  return ''
}

function stripNavFromSpeech(text) {
  if (!text) return ''
  return String(text)
    .replace(/\[NAVIGATE:[^\]]*\]?/gi, '')
    .replace(/\bNAVIGATE\s*:?\s*\/?\s*[\w/.?=&-]*/gi, '')
    .replace(/\bnavigate\s*(?:to|:)?\s*\/?\s*[\w/.?=&-]*/gi, '')
    .replace(/\bnavigate\s+page\b/gi, '')
    .replace(/\b(?:вызов|вызови|вызываю)\s+navigate\w*/gi, '')
    .replace(/\s{2,}/g, ' ')
    .replace(/^[\s,.:;—-]+|[\s,.:;—-]+$/g, '')
    .trim()
}

function runVoiceNavigate(params) {
  let raw = String(params?.path || params?.route || params?.url || '').trim()
  const highlight = String(params?.highlight_text || '').trim()
  
  if (raw) {
    history.value.push({
      role: 'assistant',
      content: `*[Система: ИИ осуществляет переход по маршруту ${raw}${highlight ? ` и подсвечивает фрагмент "${highlight}"` : ''}]*`,
      sources: []
    })
    if (isOpen.value) scrollBottom()
  }
  
  if (!raw) {
    return {
      result: 'Ошибка: не указан путь. Выбери путь из списка.',
      responseType: 'tool-response',
      agentReaction: AgentReaction.SPEAKS,
    }
  }
  
  if (highlight) {
    window.pendingHighlightText = highlight
  }
  
  // LOGGING TOOL PARAMS TO DEBUG NAV FAILURES
  fetch('/api/analytics/event', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      event_type: 'DEBUG_NAV_TOOL', 
      user_id: 1, 
      meta: params 
    })
  }).catch(() => {})
  
  const ok = tryVoiceNavigate(raw)
  if (ok) {
    return {
      result:
        'Переход выполнен. Страница уже открыта. Не повторяй вслух переход и не комментируй смену экрана.',
      responseType: 'tool-response',
      agentReaction: AgentReaction.LISTENS,
    }
  }
  return {
    result: 'Переход не выполнен: путь не распознан. Уточни у пользователя или выбери путь из списка.',
    responseType: 'tool-response',
    agentReaction: AgentReaction.SPEAKS,
  }
}

function lastVisibleAgentTranscript(transcripts) {
  for (let i = transcripts.length - 1; i >= 0; i--) {
    const entry = transcripts[i]
    if (entry.speaker === 'agent' && entry.text && !isHiddenVoiceContextMessage(entry.text)) {
      return stripNavFromSpeech(entry.text)
    }
  }
  return ''
}

function normalizeNavPath(rawPath) {
  if (rawPath === undefined || rawPath === null) return null
  let path = String(rawPath).trim()
  
  // Extract query if present to append it back later
  let queryPart = ''
  if (path.includes('?')) {
    const parts = path.split('?')
    path = parts[0]
    queryPart = '?' + parts.slice(1).join('?')
  }
  
  if (!path || /^(home|главная|главную|main)$/i.test(path)) return '/' + queryPart
  if (!path.startsWith('/')) path = `/${path}`
  return (path.replace(/\/+$/, '') || '/') + queryPart
}

function parseNavTarget(rawPath) {
  const raw = String(rawPath || '').trim()
  if (!raw) return null

  // Legacy vpath://page/ support (just in case old sessions still use it)
  if (raw.startsWith('vpath://page/')) {
    return { path: raw.replace('vpath://page', '') }
  }

  // Real path (with optional ?lesson=X query)
  let pathname = raw
  let query = {}
  if (raw.includes('?')) {
    const idx = raw.indexOf('?')
    pathname = raw.slice(0, idx)
    query = Object.fromEntries(new URLSearchParams(raw.slice(idx + 1)))
  }
  const path = resolveNavigatePath(pathname)
  if (!path) return null
  return Object.keys(query).length ? { path, query } : { path }
}

function extractNavPathFromText(raw) {
  if (!raw) return null
  const tag = raw.match(/\[NAVIGATE:\s*([^\]]*)\]/i)
  if (tag) return normalizeNavPath(tag[1])

  if (/\bnavigate\s+(?:to\s+)?home\b/i.test(raw)) return '/'

  const patterns = [
    /\bNAVIGATE\s*:?\s*(\/[^\s\],.]*)/i,
    /\bnavigate\s+(?:to\s+)?(\/(?:courses\/[^\s\],.]+|profile|journal|homeworks|analytics|homeworks\/workshop)?)/i,
    /\bnavigate\s+(?:to\s+)?courses\/([a-z0-9_-]+)/i,
  ]
  for (const re of patterns) {
    const m = raw.match(re)
    if (!m) continue
    let p = (m[1] || '').trim()
    if (!p) return '/'
    if (!p.startsWith('/')) p = `/courses/${p}`
    return normalizeNavPath(p)
  }
  return null
}

/** Явная просьба перейти на статическую страницу (без тега от модели). */
function detectStaticNavInText(text) {
  if (!text) return null
  const lower = text.toLowerCase()
  const wantsNav = /перейд|перевед|открой|покаж|выведи|верни|направь|хочу на|можно на|давай на/i.test(lower)
  if (!wantsNav) return null
  if (/главн|домой|\bhome\b/i.test(lower)) return '/'
  if (/профил/i.test(lower)) return '/profile'
  if (/журнал/i.test(lower)) {
    if (user.value?.role === 'student') return null
    return '/journal'
  }
  if (/аналитик|статистик|дашборд/i.test(lower)) {
    if (user.value?.role === 'student') return null
    return '/analytics'
  }
  if (/мастерск|конструктор/i.test(lower)) {
    if (user.value?.role === 'student') return null
    return '/homeworks/workshop'
  }
  if (/домашн|задани/i.test(lower)) return '/homeworks'
  return null
}

function detectLessonPathInText(text) {
  if (!text) return null
  const lower = text.toLowerCase()
  const courses = allCourses.value || []

  const onCourse = route.path.match(/^\/courses\/([^/?#]+)/)
  if (onCourse) {
    const c = courses.find((x) => x.id === onCourse[1])
    for (const l of c?.lessons || []) {
      const lt = (l.title || '').toLowerCase()
      if (lt.length > 4 && lower.includes(lt)) {
        return `/courses/${c.id}?lesson=${l.id}`
      }
    }
  }

  for (const c of courses) {
    for (const l of c.lessons || []) {
      const lt = (l.title || '').toLowerCase()
      if (lt.length > 4 && lower.includes(lt)) {
        return `/courses/${c.id}?lesson=${l.id}`
      }
    }
  }
  return null
}

function detectCoursePathInText(text) {
  const courses = allCourses.value || []
  if (!courses.length || !text) return null
  const lower = text.toLowerCase()

  for (const c of courses) {
    const title = (c.title || '').toLowerCase()
    const id = (c.id || '').toLowerCase()
    if (title && lower.includes(title)) return `/courses/${c.id}`
    if (id && (lower.includes(id) || lower.includes(`курс ${id}`) || lower.includes(`курса ${id}`))) {
      return `/courses/${c.id}`
    }
  }

  const aliases = [
    { id: 'react-30-days-ru', keys: ['react', 'реакт'] },
    { id: 'js-30-days-ru', keys: ['javascript', 'js', 'джаваскрипт', '30 days'] },
    { id: 'python-100-days-ru', keys: ['python', 'питон', 'пайтон', '100 дн', 'сто дн'] },
    { id: 'ml', keys: ['машинн', 'machine learning', 'ml '] },
    { id: 'webdev', keys: ['веб-разработ', 'веб разработ', 'webdev', 'frontend'] },
    { id: 'sql', keys: ['sql', 'баз данных', 'postgresql'] },
    { id: 'algorithms', keys: ['алгоритм', 'алгоритмизации', 'программировани'] },
  ]
  for (const { id, keys } of aliases) {
    if (keys.some(k => lower.includes(k))) {
      const c = courses.find(x => x.id === id)
      if (c) return `/courses/${c.id}`
    }
  }
  return null
}

function detectCourseOfferInText(text) {
  if (!text || !/перевест|перейти|открыть|подходит|хотите|готов|найден|нашёл|нашла/i.test(text)) return null
  return detectCoursePathInText(text)
}

function resolveNavigatePath(rawPath) {
  const path = normalizeNavPath(rawPath)
  if (!path) return null

  if (STATIC_NAV_PATHS.includes(path)) return path
  
  if (path.startsWith('/homeworks/')) return path
  if (path.startsWith('/journal/')) return path

  const m = path.match(/^\/courses\/(.+)$/i)
  let slug = ''
  if (m) {
    slug = decodeURIComponent(m[1]).toLowerCase().trim()
    // If it looks like a direct course path, just trust the AI and return it!
    // This prevents caching issues where the frontend has an old course list.
    if (slug) return `/courses/${slug}`
  } else {
    slug = decodeURIComponent(path.replace(/^\//, '')).toLowerCase().trim()
  }

  const courses = allCourses.value || []
  if (!courses.length) return `/courses/${slug}` // Fallback

  let found = courses.find(c => c.id?.toLowerCase() === slug)
  if (found) return `/courses/${found.id}`

  const keywords = [
    { id: 'react-30-days-ru', keys: ['react', 'реакт'] },
    { id: 'js-30-days-ru', keys: ['javascript', 'js', 'джаваскрипт', '30 days'] },
    { id: 'python-100-days-ru', keys: ['python', 'питон', 'пайтон'] },
    { id: 'ml', keys: ['ml', 'машинн', 'machine', 'learning'] },
    { id: 'webdev', keys: ['web', 'веб', 'frontend', 'html'] },
    { id: 'sql', keys: ['sql', 'баз данных', 'postgres'] },
  ]
  for (const { id, keys } of keywords) {
    if (keys.some(k => slug.includes(k))) {
      return `/courses/${id}`
    }
  }

  found = courses.find(c => {
    const t = (c.title || '').toLowerCase()
    return t.includes(slug) || slug.includes((c.id || '').toLowerCase())
  })
  if (found) return `/courses/${found.id}`
  
  return `/courses/${slug}`
}

function runOpenLesson(params) {
  const cid = params.course_id
  const idx = params.lesson_number
  const highlight = String(params?.highlight_text || '').trim()
  
  if (!cid || !idx) {
    return {
      result: 'Ошибка: Не передан course_id или lesson_number',
      responseType: 'tool-response',
      agentReaction: AgentReaction.SPEAKS,
    }
  }

  if (highlight) {
    window.pendingHighlightText = highlight
  }

  const target = { path: `/courses/${cid}`, query: { lesson_idx: idx } }
  router.push(target)
  
  return {
    result: `Переход на урок ${idx} выполнен. Урок уже открыт на экране. Не комментируй смену экрана и ничего не говори об этом.`,
    responseType: 'tool-response',
    agentReaction: AgentReaction.LISTENS,
  }
}

const showCourseSelectionModal = ref(false)
const courseSelectionList = ref([])

function runShowCourseSelection(params) {
  const query = String(params?.query || '').toLowerCase().trim()
  if (!query) {
    return 'Ошибка: запрос пуст.'
  }
  
  const courses = allCourses.value || []
  let matches = courses.filter(c => 
    (c.title || '').toLowerCase().includes(query) || 
    (c.id || '').toLowerCase().includes(query) ||
    (c.description || '').toLowerCase().includes(query)
  )
  
  if (matches.length === 0) {
    matches = courses // Fallback to all courses if no exact match
  }
  
  courseSelectionList.value = matches
  showCourseSelectionModal.value = true
  
  return 'Окно выбора курса открыто на экране. Пользователь сейчас сделает выбор.'
}

function navigateToCourse(courseId) {
  router.push(`/courses/${courseId}`)
}

function tryVoiceNavigate(rawPath) {
  const target = parseNavTarget(rawPath)
  if (!target) {
    console.warn('[nav] неизвестный путь:', rawPath)
    recordNavMetric(false, rawPath)
    return false
  }

  const targetPath = (target.path || '/').replace(/\/+$/, '') || '/'
  const current = (route.path || '/').replace(/\/+$/, '') || '/'
  const samePath = current === targetPath
  const sameLesson =
    !target.query?.lesson || String(route.query.lesson || '') === String(target.query.lesson)

  if (samePath && sameLesson) {
    pendingNavPath = null
    if (window.pendingHighlightText) {
      window.dispatchEvent(new CustomEvent('eduai-highlight-text'))
    }
    if (!isRecentVoiceNav()) scheduleVoicePageContextPush(300, true)
    return true
  }

  if (String(rawPath) === lastVoiceNavPath) return true
  lastVoiceNavPath = String(rawPath)
  pendingNavPath = null
  markVoiceNavHandled()
  skipNextRouteContextPush = true
  recordNavMetric(true, targetPath)
  router.push(target)
  scheduleVoicePageContextPush(900, true)
  // Capture highlight text NOW before watch clears it
  const pendingHL = window.pendingHighlightText || ''
  if (pendingHL) {
    setTimeout(() => {
      // Pass text in event detail so it works even if pendingHighlightText was cleared
      window.dispatchEvent(new CustomEvent('eduai-highlight-text', { detail: { text: pendingHL } }))
    }, 1200)
  }
  return true
}

function voiceContextKey() {
  const lesson = getActiveLessonContext()
  const lessonPart = lesson ? `|lesson:${lesson.lessonId}` : ''
  return `${route.path}|${courseId.value}|${currentPage.value}${lessonPart}`
}

function buildVoiceContextMessage() {
  const pageText = getPageText()
  const cid = courseId.value || 'default'
  const cname = courseName.value || 'EduAI'
  const lesson = getActiveLessonContext()
  const lessonBlock = lesson
    ? `- Текущий урок: «${lesson.lessonTitle}» (${lesson.lessonIndex} из ${lesson.totalLessons})\n`
    : ''
  const lessonsList = window.currentCourseLessons || []
  const lessonsBlock =
    lessonsList.length && route.path.startsWith('/courses/')
      ? `- Уроки курса: ${lessonsList.map((l, i) => `Урок ${i + 1}: «${l.title}»`).join('; ')}\n`
      : ''
  const hw = window.currentHomeworkContext
  const quizCount = hw?.quizItems?.length || 0
  const st = hw?.assignment?.status
  const gradeHint =
    st === 'graded' && hw.assignment.grade != null
      ? `, оценка: ${hw.assignment.grade} из 5`
      : ''
  const reviewRule =
    st === 'graded'
      ? `- Работа УЖЕ ОЦЕНЕНА${hw.assignment.grade != null ? ` (${hw.assignment.grade} из 5)` : ''}. НЕ вызывай reviewHomework — повторная ИИ-проверка не нужна. Отвечай по оценке и отзыву из контекста ниже.\n`
      : st === 'submitted'
        ? `- Работа сдана, ждёт проверки. Для ИИ-проверки вызови reviewHomework один раз; проверка на сервере может занять до нескольких минут — попроси пользователя подождать, не говори про зависание.\n`
        : `- Работа не в статусе «на проверке»; reviewHomework не вызывай.\n`
  const hwBlock =
    hw?.assignment && route.path.startsWith('/homeworks/')
      ? `- Домашнее задание: «${hw.title}», ученик: ${hw.assignment.student}, assignment_id: ${hw.assignment.id}, статус: ${hw.assignment.status}${gradeHint}${quizCount ? `, тестов: ${quizCount}` : ''}\n- На экране есть код, тестовая часть (MCQ) и письменный ответ — см. содержимое ниже.\n${reviewRule}`
      : hw && route.path.startsWith('/homeworks/') && !hw.assignment
        ? `- Домашнее задание: «${hw.title}»${quizCount ? `, тестов: ${quizCount}` : ''}. Для подсказки без готового решения — getHomeworkHint.\n`
        : hw && route.path.startsWith('/homeworks/')
          ? `- Домашнее задание: «${hw.title}»${quizCount ? `, тестов: ${quizCount}` : ''}. Выберите ученика или откройте форму ответа.\n`
          : ''
  return `[СИСТЕМА: обновление контекста страницы]
ВАЖНО: это тихое обновление. Не отвечай вслух, не повторяй «открываю», «перехожу» и т.п. Жди реплику пользователя.

Пользователь сейчас здесь:
- Страница: ${currentPage.value}
- URL: ${route.path}
- Курс: ${cname} (course_id: ${cid})
${lessonBlock}${lessonsBlock}${hwBlock}- Для queryKnowledgeBase используй course_id: ${cid}
- Для списка несданных ДЗ — getHomeworkReminders

Содержимое экрана (активный урок):
"""
${pageText}
"""`
}

function stripHtmlForSpeech(html) {
  return String(html || '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

async function runVoiceRagQuery(params) {
  const query =
    (typeof params === 'string' ? params : null) ??
    params?.query ??
    params?.parameters?.query ??
    params?.args?.query
    
  if (query) {
    history.value.push({
      role: 'assistant',
      content: `*[Система: ИИ выполняет поиск по материалам курса по запросу "${query}"]*`,
      sources: []
    })
    if (isOpen.value) scrollBottom()
  }

  if (!query?.trim()) return 'Нужен поисковый запрос по материалам курса.'
  try {
    const token = localStorage.getItem('token')
    const headers = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`
    const res = await fetch('/api/ultravox/rag', {
      method: 'POST',
      headers,
      body: JSON.stringify({
        query: query.trim(),
        course_id: courseId.value,
        session_id: voiceSessionId,
      }),
    })
    if (!res.ok) throw new Error(await res.text())
    const data = await res.json()
    return data.results || 'Информация по запросу не найдена в материалах курса.'
  } catch (e) {
    return `Ошибка поиска в материалах: ${e.message || e}.`
  }
}

async function runVoiceHomeworkReview() {
  const u = user.value || (await fetchUser())
  if (u?.role !== 'teacher') {
    return 'Проверка домашних заданий доступна только преподавателю.'
  }
  const hw = window.currentHomeworkContext
  const assignmentId = hw?.assignment?.id
  if (!assignmentId || !route.path.startsWith('/homeworks/')) {
    return 'Откройте страницу домашнего задания и выберите ученика в списке слева, затем попросите проверить снова.'
  }
  const status = hw.assignment.status
  if (status === 'graded') {
    const g = hw.assignment.grade
    return (
      `Работа ученика ${hw.assignment.student} уже оценена${g != null ? ` на ${g} из 5` : ''}. ` +
      `Повторную ИИ-проверку не запускаю — оценка и отзыв уже на экране. ` +
      `Чтобы пересчитать отзыв ИИ, нажмите на странице кнопку «Проверить с ИИ (Голосовой помощник)».`
    )
  }
  if (status !== 'submitted') {
    return `У ученика ${hw.assignment.student} ещё нет сданной работы для проверки.`
  }

  const studentName = hw.assignment.student
  voiceState.value = 'THINKING'

  void (async () => {
    // Block the button in HomeworkDetailView by adding to the global set
    checkingAssignments.add(assignmentId)
    try {
      const result = await hwApi.aiReviewHomework(assignmentId)
      window.dispatchEvent(
        new CustomEvent('eduai-homework-reviewed', {
          detail: {
            assignmentId,
            teacher_feedback: result.teacher_feedback,
            suggested_grade: result.suggested_grade,
            error_fragments: result.error_fragments || [],
          },
        })
      )
      const gradeLine =
        result.suggested_grade != null ? `Предлагаемая оценка: ${result.suggested_grade} из 5. ` : ''
      const spoken = stripHtmlForSpeech(result.teacher_feedback).slice(0, 500)
      if (uvSession) {
        try {
          uvSession.sendText(
            `[СИСТЕМА: ИИ-проверка для ученика ${studentName} завершена. ${gradeLine}` +
              `На экране обновлены отзыв и подсветка ошибок. Озвучь пользователю кратко по-русски (1–3 предложения), без HTML. Текст отзыва: ${spoken}]`,
            true
          )
        } catch (_) {}
      }
    } catch (e) {
      const msg = e?.message || String(e)
      if (uvSession) {
        try {
          uvSession.sendText(
            `[СИСТЕМА: ИИ-проверка не выполнена: ${msg}. Скажи пользователю по-русски коротко: проверка не удалась, можно повторить позже или нажать «Проверить с ИИ» на странице. Упомяни при необходимости запуск Ollama.]`,
            true
          )
        } catch (_) {}
      }
    } finally {
      // Always unblock the button
      checkingAssignments.delete(assignmentId)
    }
  })()

  return (
    'Проверка ДЗ только что запущена в фоне (ответ инструмента приходит сразу, а сама нейросеть считает дольше). ' +
    'Скажи пользователю по-русски одной-двумя фразами: сейчас идёт автоматическая проверка ответа ученика, обычно это занимает от 30 секунд до двух–трёх минут — попроси спокойно подождать и не завершать голосовой разговор. ' +
    'Категорически не говори, что приложение или система зависли, пропала связь или произошёл сбой — это нормальное ожидание тяжёлого запроса. ' +
    'Когда проверка закончится, ты получишь отдельное служебное сообщение с результатом для озвучки.'
  )
}

async function runVoiceMassHomeworkReview() {
  const u = user.value || (await fetchUser())
  if (u?.role !== 'teacher') {
    return 'Массовая проверка домашних заданий доступна только преподавателю.'
  }
  
  voiceState.value = 'THINKING'
  
  try {
    const res = await hwApi.aiReviewAllHomeworks()
    if (!res || res.started === 0) {
      return 'Все сданные учениками работы уже проверены или нет новых работ для проверки.'
    }
    return (
      `Запущена массовая фоновая проверка для ${res.started} заданий. ` +
      'Скажи пользователю по-русски одной фразой: запущена автоматическая проверка всех несданных заданий, она пройдет в фоне, результаты придут в уведомлениях.'
    )
  } catch (e) {
    const msg = e?.message || String(e)
    return `Сбой при массовой проверке. Скажи пользователю коротко: произошла ошибка при запуске массовой проверки (${msg}).`
  }
}

async function runTeacherSummary() {
  const u = user.value || (await fetchUser())
  if (u?.role !== 'teacher') return 'Сводка журнала доступна только преподавателю.'
  try {
    const s = await hwApi.getJournalSummary()
    const courseLines = (s.courses || [])
      .filter((c) => c.avg_grade != null || c.pending_review || c.not_submitted)
      .slice(0, 5)
      .map(
        (c) =>
          `${c.course_title}: средний ${c.avg_grade ?? '—'}, не сдано ${c.not_submitted}, на проверке ${c.pending_review}`
      )
    const notSubmitted = (s.not_submitted || [])
      .slice(0, 5)
      .map((x) => `${x.student_name} — «${x.homework_title}»`)
    const pending = (s.pending_review || [])
      .slice(0, 5)
      .map((x) => `${x.student_name} — «${x.homework_title}»`)

    let out = `Средний балл по журналу: ${s.overall_avg ?? 'нет оценок'}. `
    out += `На проверке ${s.pending_review_count}, не сдано ${s.not_submitted_count}. `
    if (courseLines.length) out += `По курсам: ${courseLines.join('; ')}. `
    if (notSubmitted.length) out += `Не сдали: ${notSubmitted.join(', ')}. `
    if (pending.length) out += `Ждут проверки: ${pending.join(', ')}. `
    return out.trim()
  } catch (e) {
    return `Не удалось получить сводку: ${e.message || e}.`
  }
}

async function runVoiceReminders() {
  try {
    const r = await hwApi.getReminders()
    if (r.role === 'teacher') {
      const pending = (r.pending_review || [])
        .slice(0, 5)
        .map((x) => `${x.student_name}, «${x.title}»`)
      const ns = (r.not_submitted || [])
        .slice(0, 5)
        .map((x) => `${x.student_name}, «${x.title}»`)
      let msg = r.message || ''
      if (pending.length) msg += ` На проверке: ${pending.join('; ')}.`
      if (ns.length) msg += ` Не сдано: ${ns.join('; ')}.`
      return msg.trim() || 'Все задания в порядке.'
    }
    const pending = (r.pending || []).map((x) => `«${x.title}» (${x.course_title})`)
    const waiting = (r.waiting || []).map((x) => `«${x.title}»`)
    let msg = r.message || ''
    if (pending.length) msg += ` Не сдано: ${pending.join(', ')}.`
    if (waiting.length) msg += ` На проверке: ${waiting.join(', ')}.`
    return msg.trim() || 'Все домашние задания сданы.'
  } catch (e) {
    return `Не удалось загрузить напоминания: ${e.message || e}.`
  }
}

async function runVoiceHomeworkHint() {
  const u = user.value || (await fetchUser())
  if (u?.role !== 'student') return 'Подсказки по ДЗ доступны ученику на странице задания.'
  const my = window.currentHomeworkContext?.assignment
  if (!my?.id || !route.path.startsWith('/homeworks/')) {
    return 'Откройте домашнее задание, которое ещё не сдали, и попросите подсказку снова.'
  }
  if (my.status !== 'pending') {
    return 'Подсказки доступны только до отправки работы на проверку.'
  }
  try {
    voiceState.value = 'THINKING'
    const res = await hwApi.getHomeworkHint(my.id, {
      student_code: my.code ?? window.currentHomeworkContext?.assignment?.code,
      student_text: my.text ?? window.currentHomeworkContext?.assignment?.text,
      student_quiz: my.quiz ?? window.currentHomeworkContext?.assignment?.quiz,
    })
    window.dispatchEvent(
      new CustomEvent('eduai-homework-hint', { detail: { assignmentId: my.id, hint: res.hint } })
    )
    return res.hint
  } catch (e) {
    return `Не удалось получить подсказку: ${e.message || e}.`
  }
}

async function syncVoicePageContext() {
  if (!voiceSessionId) return
  const token = localStorage.getItem('token')
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const body = {
    session_id: voiceSessionId,
    course_id: courseId.value,
    course_name: courseName.value,
    current_page: currentPage.value,
    current_path: route.path,
    page_content: getPageText(),
    ...lessonContextFields(),
    ...homeworkContextFields(),
  }
  try {
    const resp = await fetch('/api/ultravox/context', {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    })
    if (!resp.ok) {
      const text = await resp.text()
      console.error('[voice context] 422 body sent:', JSON.stringify(body))
      console.error('[voice context] 422 response:', text)
    }
  } catch (e) {
    console.warn('[voice context] sync failed', e)
  }
}

function applyVoiceVolumeOnce() {
  const vol = Math.max(0, Math.min(1, voiceVolume.value))
  localStorage.setItem(VOICE_VOLUME_KEY, String(vol))

  const el = uvSession?.audioElement
  if (el) {
    el.volume = vol
    el.muted = vol < 0.02
  }

  try {
    document.querySelectorAll('audio').forEach((a) => {
      a.volume = vol
      a.muted = vol < 0.02
    })
  } catch {}

  try {
    uvSession?.room?.remoteParticipants?.forEach((p) => {
      p.audioTrackPublications?.forEach((pub) => {
        const t = pub.track || pub.audioTrack
        if (t && typeof t.setVolume === 'function') t.setVolume(vol)
      })
    })
  } catch {}
}

function applyVoiceVolume() {
  applyVoiceVolumeOnce()
}

function burstApplyVoiceVolume() {
  applyVoiceVolumeOnce()
  for (const ms of [400, 1000, 2000]) setTimeout(applyVoiceVolumeOnce, ms)
}

function normalizeSources(sources) {
  if (!Array.isArray(sources)) return []
  return sources.map(s => (typeof s === 'string' ? s : (s?.title || s?.file_name || String(s))))
}

function syncVoiceTranscriptsToHistory() {
  const transcripts = (uvSession?.transcripts || []).filter(Boolean)
  let added = false
  for (const t of transcripts) {
    if (t.ordinal == null || voiceHistorySyncedOrdinals.has(t.ordinal)) continue
    if (!t.isFinal) continue
    if (t.speaker === 'user' && isAutoContextTranscript(t)) continue
    const raw = t.text || ''
    if (t.speaker === 'agent' && isHiddenVoiceContextMessage(raw)) continue

    const role = t.speaker === 'user' ? 'user' : 'assistant'
    const content = role === 'assistant' ? stripNavFromSpeech(raw).trim() : raw.trim()
    if (!content) continue

    voiceHistorySyncedOrdinals.add(t.ordinal)
    history.value.push({ role, content, sources: [] })
    added = true
  }
  if (added && isOpen.value) scrollBottom()
}

function clearVoiceIdleTimer() {
  if (voiceIdleTimer) {
    clearTimeout(voiceIdleTimer)
    voiceIdleTimer = null
  }
}

function resetVoiceIdleTimer() {
  clearVoiceIdleTimer()
  if (!voiceMode.value || voiceState.value !== 'LISTENING') return
  
  let autoDisconnect = false
  if (user.value && user.value.settings_json) {
    try {
      autoDisconnect = !!JSON.parse(user.value.settings_json).ai_auto_disconnect
    } catch (e) {}
  }
  if (!autoDisconnect) return
  
  voiceIdleTimer = setTimeout(() => {
    if (!voiceMode.value || voiceState.value !== 'LISTENING') return
    voiceError.value = 'Звонок завершён из‑за тишины. Нажмите 🎤, чтобы снова поговорить с ИИ Ассистентом.'
    stopVoiceMode({ preserveError: true })
  }, 120_000) // 2 minutes
}

function scheduleVoicePageContextPush(delay = 450, force = false) {
  if (!voiceMode.value) return
  clearTimeout(voiceContextTimer)
  voiceContextTimer = setTimeout(async () => {
    await syncVoicePageContext()
    const key = voiceContextKey()
    if (!force && key === lastPushedVoiceContextKey) return
    lastPushedVoiceContextKey = key
    try {
      if (uvSession) uvSession.sendText(buildVoiceContextMessage(), true)
    } catch (e) {
      console.warn('[voice context] sendText failed', e)
    }
  }, delay)
}

// ─── Ultravox helpers ─────────────────────────────────────────────────────
async function startUltravoxSession() {
  try {
    voiceError.value = ''
    voiceState.value = 'THINKING'
    lastVoiceNavPath = null
    voiceUserHasSpoken = false
    pendingNavPath = null

    await refreshPageContextFromRoute()
    if (!allCourses.value.length) await loadAllCourses()

    voiceSessionId = crypto.randomUUID()
    lastPushedVoiceContextKey = ''

    const token = localStorage.getItem('token')
    const headers = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`

    const res = await fetch('/api/ultravox/call', {
      method: 'POST',
      headers,
      body: JSON.stringify({
        session_id: voiceSessionId,
        course_id: courseId.value,
        course_name: courseName.value,
        current_page: currentPage.value,
        current_path: route.path,
        page_content: getPageText(),
        voice_id: null,
        available_courses: allCourses.value.map(c => ({
          id: c.id,
          title: c.title,
          description: c.description || '',
          icon: c.icon || '',
        })),
      })
    })
    if (!res.ok) throw new Error(await res.text())
    const data = await res.json()
    const joinUrl = data.joinUrl
    if (data.sessionId) voiceSessionId = data.sessionId

    voiceHistorySyncedOrdinals = new Set()

    uvSession = new UltravoxSession()
    uvSession.registerToolImplementation('getPageContext', async () => {
      await refreshPageContextFromRoute()
      return buildVoiceContextMessage()
    })
    uvSession.registerToolImplementation('navigatePage', (params) => runVoiceNavigate(params))
    uvSession.registerToolImplementation('openLesson', (params) => runOpenLesson(params))
    uvSession.registerToolImplementation('queryKnowledgeBase', (params) => runVoiceRagQuery(params))
    uvSession.registerToolImplementation('reviewHomework', () => runVoiceHomeworkReview())
    uvSession.registerToolImplementation('reviewAllHomeworks', () => runVoiceMassHomeworkReview())
    uvSession.registerToolImplementation('getTeacherSummary', () => runTeacherSummary())
    uvSession.registerToolImplementation('getHomeworkReminders', () => runVoiceReminders())
    uvSession.registerToolImplementation('getHomeworkHint', () => runVoiceHomeworkHint())
    uvSession.registerToolImplementation('showCourseSelection', (params) => runShowCourseSelection(params))
    uvSession.registerToolImplementation('getNotifications', async () => {
      try {
        const notifs = await notificationsApi.get()
        if (!notifs || notifs.length === 0) return 'У пользователя нет непрочитанных оповещений.'
        const list = notifs.map(n => `- [ID: ${n.id}] ${n.title}: ${n.message} (Ссылка для перехода: ${n.link})`).join('\n')
        return `Непрочитанные оповещения:\n${list}`
      } catch(e) {
        return 'Не удалось загрузить оповещения.'
      }
    })
    uvSession.registerToolImplementation('clearNotifications', async () => {
      try {
        await notificationsApi.clear()
        return 'Все оповещения успешно очищены.'
      } catch(e) {
        return 'Не удалось очистить оповещения.'
      }
    })
    uvSession.registerToolImplementation('fillHomeworkForm', (params) => {
      try {
        const data = {}
        if (params?.title)       data.title = String(params.title)
        if (params?.intro)       data.intro = String(params.intro)
        if (params?.code_template) data.code_template = String(params.code_template)
        if (params?.written_part)  data.written_part = String(params.written_part)
        if (params?.quiz_items) {
          // quiz_items comes as JSON string or array
          try {
            data.quiz_items = typeof params.quiz_items === 'string'
              ? JSON.parse(params.quiz_items)
              : params.quiz_items
          } catch { data.quiz_items = [] }
        }
        // Dispatch event to HomeworkWorkshopEditorView
        window.dispatchEvent(new CustomEvent('eduai-fill-homework', { detail: data }))
        const filled = Object.keys(data).join(', ')
        return `Форма заполнена. Заполнены поля: ${filled}. Сохранение произошло автоматически.`
      } catch (e) {
        return `Ошибка заполнения формы: ${e.message}`
      }
    })
    await uvSession.joinCall(joinUrl)
    burstApplyVoiceVolume()

    // Слушаем статус сессии
    uvSession.addEventListener('status', (e) => {
      const status = uvSession.status
      if (status === 'idle' || status === 'disconnected') {
        voiceState.value = 'IDLE'
        clearVoiceIdleTimer()
      } else if (status === 'listening') {
        voiceState.value = 'LISTENING'
        isHearingSpeech.value = true
        resetVoiceIdleTimer()
      } else if (status === 'thinking') {
        voiceState.value = 'THINKING'
        isHearingSpeech.value = false
        clearVoiceIdleTimer()
      } else if (status === 'speaking') {
        voiceState.value = 'SPEAKING'
        isHearingSpeech.value = false
        clearVoiceIdleTimer()
      }
      burstApplyVoiceVolume()
    })

    // Слушаем транскрипт (служебные sendText при навигации в UI не показываем)
    uvSession.addEventListener('transcripts', (e) => {
      const transcripts = uvSession.transcripts
      if (!transcripts || !transcripts.length) return
      const last = transcripts[transcripts.length - 1]

      if (last.speaker === 'user') {
        if (isAutoContextTranscript(last)) {
          const visible = lastVisibleUserTranscript(transcripts)
          if (visible) voiceTranscript.value = visible
          syncVoiceTranscriptsToHistory()
          return
        }
        voiceUserHasSpoken = true
        resetVoiceIdleTimer()
        voiceTranscript.value = last.text
        const userText = (last.text || '').trim()
        if (VOICE_YES_RE.test(userText) && pendingNavPath) {
          tryVoiceNavigate(pendingNavPath)
      } else {
          const userNav = detectStaticNavInText(userText)
          if (userNav) tryVoiceNavigate(userNav)
        }
      } else if (last.speaker === 'agent') {
        const raw = last.text || ''
        if (isHiddenVoiceContextMessage(raw)) return
        const display = stripNavFromSpeech(raw)
        voiceAssistantText.value = display
        lastAssistantText.value = display

        let navPath = extractNavPathFromText(raw)
        if (!navPath) navPath = detectLessonPathInText(display) || detectLessonPathInText(raw)
        if (!navPath) navPath = detectStaticNavInText(display)
        if (navPath && !isRecentVoiceNav()) {
          tryVoiceNavigate(navPath)
        } else if (!navPath) {
          const offer = detectCourseOfferInText(display) || detectLessonPathInText(display)
          if (offer) pendingNavPath = offer
        }
      }

      // Если последняя реплика скрыта — подтянуть последний видимый ответ ассистента
      if (isAutoContextTranscript(last) || isHiddenVoiceContextMessage(last.text)) {
        const agentVisible = lastVisibleAgentTranscript(transcripts)
        if (agentVisible) voiceAssistantText.value = agentVisible
      }

      syncVoiceTranscriptsToHistory()
    })

    // Слушаем data-сообщения (навигация через [NAVIGATE:/...])
    uvSession.addEventListener('experimental_message', (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data?.type === 'navigate' && data?.path) {
          router.push(data.path)
          scheduleVoicePageContextPush(700, true)
        }
      } catch {}
    })

    voiceState.value = 'LISTENING'
    resetVoiceIdleTimer()
    scheduleVoicePageContextPush(600, true)

  } catch (err) {
    console.error('[Ultravox] start error:', err)
    voiceError.value = `Ошибка подключения: ${err.message}`
    voiceState.value = 'IDLE'
    voiceMode.value = false
  }
}

async function stopUltravoxSession() {
  syncVoiceTranscriptsToHistory()
  clearVoiceIdleTimer()
  clearTimeout(voiceContextTimer)
  voiceContextTimer = null
  voiceSessionId = null
  lastPushedVoiceContextKey = ''
  voiceHistorySyncedOrdinals = new Set()
  if (uvSession) {
    try { await uvSession.leaveCall() } catch {}
    uvSession = null
  }
}

// ─── Volume analyser stub (микрофон управляется Ultravox) ─────────────────
function startVolumeAnalyser() {}
function stopVolumeAnalyser() { micVolume.value = 0 }

// (old volume analyser removed — Ultravox manages microphone directly)

// Для текстового чата (вейк-слова в поле ввода)
const WAKE_WORDS = ['ассистент', 'ассистент', 'эдуай', 'edu ai', 'ассистент', 'помоги мне']

function stripWakePrefix(text) {
  let t = (text || '').trim()
  if (!t) return t
  const sorted = [...WAKE_WORDS].sort((a, b) => b.length - a.length)
  let lower = t.toLowerCase()
  let changed = true
  while (changed) {
    changed = false
    for (const w of sorted) {
      if (!lower.startsWith(w)) continue
      const rest = t.slice(w.length)
      const next = rest[0]
      if (next && /[A-Za-zА-Яа-яЁё]/.test(next)) continue
      t = rest.replace(/^[\s,.;:!?\-—]+/u, '').trim()
      lower = t.toLowerCase()
      changed = true
      break
    }
  }
  return t.length ? t : ''
}

/* ═══ LEGACY: браузерный микрофон (Web Speech + MediaRecorder + /api/chat/voice) — отключено, голос через Ultravox ═══

// ─── MediaRecorder STT fallback (Firefox/Safari) ───────────────────────────
function stopMediaRecorder() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    try { mediaRecorder.stop() } catch (e) {}
  }
  if (mediaStream) { mediaStream.getTracks().forEach(t => t.stop()); mediaStream = null }
  mediaRecorder = null
  mediaChunks = []
}

async function startMediaRecorderListening() {
  stopMediaRecorder()
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
  } catch (err) {
    voiceError.value = 'Нет доступа к микрофону.'
    return
  }

  const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
    ? 'audio/webm;codecs=opus'
    : MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')
      ? 'audio/ogg;codecs=opus'
      : 'audio/webm'

  mediaRecorder = new MediaRecorder(mediaStream, { mimeType })
  mediaChunks = []

  mediaRecorder.ondataavailable = e => { if (e.data.size > 0) mediaChunks.push(e.data) }

  mediaRecorder.onstop = async () => {
    if (!voiceModeInternal || voiceState.value !== 'LISTENING') return
    const blob = new Blob(mediaChunks, { type: mimeType })
    mediaChunks = []
    if (blob.size < 1000) { startMediaRecorderListening(); return }

    voiceState.value = 'THINKING'
    try {
      const form = new FormData()
      form.append('audio', blob, 'recording.' + mimeType.split('/')[1].split(';')[0])
      const res = await fetch('/api/stt', { method: 'POST', body: form })
      if (!res.ok) throw new Error('STT failed')
      const data = await res.json()
      const t = (data.transcript || '').trim()
      if (t && t.length > 1) {
        voiceTranscript.value = t
        lastVoiceCommitted = t
        handleUserVoice(t)
      } else {
        voiceState.value = 'LISTENING'
        startMediaRecorderListening()
      }
    } catch (e) {
      voiceState.value = 'LISTENING'
      startMediaRecorderListening()
    }
  }

  // Записываем сегменты по 2 секунды тишины (timeslice не используем — пишем цельно)
  mediaRecorder.start()
  voiceState.value = 'LISTENING'

  // Автостоп через 8 секунд макс — затем перезапуск
  setTimeout(() => {
    if (mediaRecorder && mediaRecorder.state === 'recording' && voiceModeInternal && voiceState.value === 'LISTENING') {
      mediaRecorder.stop()
    }
  }, 8000)
}

// ─── Speech Recognition ────────────────────────────────────────────────────
let recognition       = null
let recognitionActive = false
let shouldRestart     = false
let voiceModeInternal = false
let wakeWordTriggered = false
// После паузы в речи отправляем текст (иначе при continuous=true финалы от Chrome часто не приходят).
let voiceSilenceTimer = null
let lastVoiceCommitted = ''
const VOICE_SILENCE_MS = 1200

const WAKE_WORDS = ['ассистент', 'ассистент', 'эдуай', 'edu ai', 'ассистент', 'помоги мне']

// Текущая сессия распознавания: подтвержденный текст (финальные isFinal результаты)
let committedTranscript = ''

// Убирает кодовые слова вызова в начале фразы (не имя пользователя).
function stripWakePrefix(text) {
  let t = (text || '').trim()
  if (!t) return t
  const sorted = [...WAKE_WORDS].sort((a, b) => b.length - a.length)
  let lower = t.toLowerCase()
  let changed = true
  while (changed) {
    changed = false
    for (const w of sorted) {
      if (!lower.startsWith(w)) continue
      const rest = t.slice(w.length)
      const next = rest[0]
      // не отрезать «ассистент» из «ассистентский», «ассистент» из «ассистентка»
      if (next && /[A-Za-zА-Яа-яЁё]/.test(next)) continue
      t = rest.replace(/^[\s,.;:!?\-—]+/u, '').trim()
      lower = t.toLowerCase()
      changed = true
      break
    }
  }
  return t.length ? t : ''
}

function initRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SR) {
    speechRecognitionSupported.value = false
    usingMediaRecorderFallback = true
    return
  }

  recognition = new SR()
  recognition.lang            = 'ru-RU'
  recognition.interimResults  = true
  recognition.continuous      = true
  recognition.maxAlternatives = 1

  recognition.onstart = () => {
    recognitionActive = true
    isHearingSpeech.value = false
  }

  recognition.onspeechstart = () => {
    isHearingSpeech.value = true
    // Как только человек начал говорить — сбрасываем таймер ожидания
    if (waitingForSpeech.value) clearWaitingMode()
    // UX #2: barge-in — прерываем ответ если заговорили
    if (voiceModeInternal && voiceState.value === 'SPEAKING') interruptSpeaking()
  }

  recognition.onspeechend = () => {
    isHearingSpeech.value = false
    // После окончания речи — запускаем короткий таймер ожидания финального результата
    if (voiceModeInternal && voiceState.value === 'LISTENING') {
      clearSilenceCommit()
      voiceSilenceTimer = setTimeout(() => {
        voiceSilenceTimer = null
        if (!voiceModeInternal || voiceState.value !== 'LISTENING') return
        const txt = voiceTranscript.value.trim()
        if (txt && txt.length > 1 && txt !== lastVoiceCommitted) {
          lastVoiceCommitted = txt
          handleUserVoice(txt)
        }
      }, 600)
    }
  }

  recognition.onresult = (e) => {
    let finalText = '', interimText = ''
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const t = e.results[i][0].transcript
      if (e.results[i].isFinal) finalText += t
      else interimText += t
    }

    if (!voiceModeInternal) {
      // Режим ожидания вейк-слова
      const line = (finalText || interimText).trim()
      const lower = line.toLowerCase()
      const wakeWord = WAKE_WORDS.find(w => lower.includes(w))
      if (wakeWord) {
        if (wakeWordTriggered) return
        wakeWordTriggered = true
        setTimeout(() => { wakeWordTriggered = false }, 3000)
        wakeFlash.value = true
        setTimeout(() => { wakeFlash.value = false }, 800)
        const idx = lower.indexOf(wakeWord)
        const afterWake = (idx >= 0 ? line.slice(idx + wakeWord.length) : line)
          .replace(/^[\s,.;:!?\-—]+/u, '').trim()
        startVoiceMode(afterWake || '')
      }
    } else {
      if (voiceState.value === 'LISTENING') {
          clearWaitingMode()

        if (finalText) {
          // isFinal — добавляем в подтверждённый (не заменяем!)
          committedTranscript = (committedTranscript + ' ' + finalText.trim()).trim()
          voiceTranscript.value = committedTranscript
          clearSilenceCommit()
          voiceSilenceTimer = setTimeout(() => {
            voiceSilenceTimer = null
            if (!voiceModeInternal || voiceState.value !== 'LISTENING') return
            const txt = committedTranscript.trim()
            if (txt && txt.length > 1 && txt !== lastVoiceCommitted) {
              lastVoiceCommitted = txt
              handleUserVoice(txt)
            }
          }, 500)
        } else {
          // interim — НЕ аккумулируем! Показываем: [финальное] + [текущее interim]
          voiceTranscript.value = (committedTranscript + ' ' + interimText).trim()
          scheduleSilenceCommit()
        }
      }
    }
  }


  recognition.onerror = (e) => {
    recognitionActive = false
    if (e.error === 'no-speech') {
      // В режиме ожидания — перезапускаем, не закрываем
      if (waitingForSpeech.value && voiceModeInternal) {
        setTimeout(() => startRecognitionIfNeeded(), 150); return
      }
      if (voiceModeInternal && voiceState.value === 'LISTENING') {
        setTimeout(() => startRecognitionIfNeeded(), 150)
      }
    } else if (e.error === 'aborted') {
      return
    } else if (e.error === 'network') {
      // Chromium: облачный STT иногда кратко рвётся — не показываем вспышку «network», тихо перезапуск
      if (waitingForSpeech.value && voiceModeInternal) {
        setTimeout(() => startRecognitionIfNeeded(), 350)
        return
      }
      if (voiceModeInternal && voiceState.value === 'LISTENING') {
        setTimeout(() => startRecognitionIfNeeded(), 350)
      } else if (!voiceModeInternal) {
        setTimeout(() => startRecognitionIfNeeded(), 350)
      }
    } else if (e.error === 'not-allowed') {
      // UX #4
      voiceError.value = 'Доступ к микрофону запрещён. Разрешите доступ в настройках браузера.'
      if (voiceModeInternal) stopVoiceMode()
    } else {
      if (voiceModeInternal) voiceError.value = `Ошибка распознавания: ${e.error}`
    }
  }

  recognition.onend = () => {
    recognitionActive = false
    isHearingSpeech.value = false
    // Защита от бесконечного цикла перезапуска
    if (!shouldRestart) return
    if (voiceModeInternal && (voiceState.value === 'THINKING' || voiceState.value === 'SPEAKING')) return
    setTimeout(() => startRecognitionIfNeeded(), 300)
  }
}

function startRecognitionIfNeeded() {
  if (recognitionActive || !recognition) return
  if (isOpen.value && !voiceModeInternal) return
  if (voiceModeInternal && (voiceState.value === 'THINKING' || voiceState.value === 'SPEAKING')) return
  try {
    shouldRestart = true
    recognition.start()
  } catch (e) {
    // InvalidStateError = уже запущен
    if (e.name !== 'InvalidStateError') console.warn('[recognition.start]', e.name)
  }
}

function stopRecognition() {
  shouldRestart = false
  if (recognition) try { recognition.abort() } catch (e) {}
}

function clearSilenceCommit() {
  if (voiceSilenceTimer) {
    clearTimeout(voiceSilenceTimer)
    voiceSilenceTimer = null
  }
}

function scheduleSilenceCommit() {
  if (!voiceModeInternal || voiceState.value !== 'LISTENING') return
  clearSilenceCommit()
  voiceSilenceTimer = setTimeout(() => {
    voiceSilenceTimer = null
    if (!voiceModeInternal || voiceState.value !== 'LISTENING') return
    // Не проверяем isHearingSpeech — доверяем таймауту
    const t = voiceTranscript.value.trim()
    if (t.length < 2) return
    if (t === lastVoiceCommitted) return
    lastVoiceCommitted = t
    handleUserVoice(t)
  }, 1500)
}

function commitVoiceManually() {
  const t = voiceTranscript.value.trim()
  if (!t || voiceState.value !== 'LISTENING') return
  clearSilenceCommit()
  lastVoiceCommitted = t
  clearWaitingMode()
  handleUserVoice(t)
}

function interruptSpeaking() {
  stopAudioQueue()
  voiceState.value = 'LISTENING'
  voiceAssistantText.value = ''
  stopRecognition()
  setTimeout(() => startRecognitionIfNeeded(), 100)
}

*/

// ─── LEGACY (часть 2): wake / waiting mode — отключено
/*
// ─── Siri waiting mode ─────────────────────────────────────────────────────
function enterWaitingMode() {
  committedTranscript = ''  // Сбрасываем накопленный текст при новом сеансе
  waitingForSpeech.value = true
  voiceState.value = 'LISTENING'
  voiceTranscript.value = ''
  startRecognitionIfNeeded()
  clearTimeout(waitingTimer)
  waitingTimer = setTimeout(() => {
    if (waitingForSpeech.value && voiceModeInternal) stopVoiceMode()
  }, WAITING_TIMEOUT_MS)
}

function clearWaitingMode() {
  waitingForSpeech.value = false
  clearTimeout(waitingTimer)
  waitingTimer = null
}
*/

// ─── Lifecycle ─────────────────────────────────────────────────────────────
function forceCleanup() {
  stopUltravoxSession()
}

function onLessonChanged() {
  if (voiceMode.value) scheduleVoicePageContextPush(350, true)
}

onMounted(() => {
  loadIslandPosition()
  loadAllCourses()
  fetchUser().then(() => loadHomeworkReminders())
  window.addEventListener('beforeunload', forceCleanup)
  window.addEventListener('eduai-lesson-changed', onLessonChanged)
  window.addEventListener('eduai-new-notification', onNewNotification)
})

onUnmounted(() => {
  window.removeEventListener('pointermove', onIslandWindowPointerMove)
  window.removeEventListener('pointerup', onIslandWindowPointerUp)
  window.removeEventListener('pointercancel', onIslandWindowPointerUp)
  if (islandClickTimer) clearTimeout(islandClickTimer)
  document.documentElement.classList.remove('eduai-voice-active', 'island-expanded-page')
  forceCleanup()
  window.removeEventListener('beforeunload', forceCleanup)
  window.removeEventListener('eduai-lesson-changed', onLessonChanged)
  window.removeEventListener('eduai-new-notification', onNewNotification)
})

function onNewNotification(e) {
  const notif = e.detail
  if (!notif) return
  
  let autoRead = false
  if (user.value && user.value.settings_json) {
    try {
      autoRead = !!JSON.parse(user.value.settings_json).ai_auto_read_notifs
    } catch(err) {}
  }
  
  if (autoRead && voiceMode.value && uvSession && (voiceState.value === 'LISTENING' || voiceState.value === 'SPEAKING' || voiceState.value === 'THINKING')) {
    try {
      uvSession.sendText(`[СИСТЕМА: Пришло новое оповещение: "${notif.title} - ${notif.message}". Озвучь его пользователю кратко.]`, true)
    } catch(err) {}
  }
}

// ─── Voice Mode (Ultravox) ─────────────────────────────────────────────────
async function startVoiceMode() {
  isOpen.value = false
  voiceMode.value = true
  voiceError.value = ''
  voiceTranscript.value = ''
  voiceAssistantText.value = ''
  lastAssistantText.value = ''
  lastVoiceNavPath = null
  lastPushedVoiceContextKey = ''
  voiceUserHasSpoken = false
  pendingNavPath = null
  await refreshPageContextFromRoute()
  startUltravoxSession()
}

function stopVoiceMode(opts = {}) {
  const preserveError = opts.preserveError === true
  clearVoiceIdleTimer()
  voiceMode.value = false
  voiceState.value = 'IDLE'
  if (!preserveError) voiceError.value = ''
  voiceTranscript.value = ''
  voiceAssistantText.value = ''
  stopUltravoxSession()
}

watch(
  () => [voiceMode.value, route.path, courseId.value, currentPage.value],
  ([active]) => {
    if (!active) return
    scheduleVoicePageContextPush()
  },
)

// Stubs для шаблона (Ultravox)
function commitVoiceManually() {}
function interruptSpeaking() { stopVoiceMode() }
function stopSpeakingAndListen() { stopVoiceMode() }
async function repeatLastAnswer() {}

async function speakText(text) {
  if (!text?.trim() || !ttsEnabled.value) return
  try {
    const res = await fetch('/api/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, voice: true }),
    })
    if (res.status === 204 || !res.ok) return
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const audio = new Audio(url)
    audio.volume = voiceVolume.value
    audio.onended = () => URL.revokeObjectURL(url)
    await audio.play()
  } catch (e) {
    console.warn('[speakText]', e)
  }
}

/* LEGACY (часть 3): TTS-очередь + /api/chat/voice
function stopSpeakingAndListen() {
  stopAudioQueue()
  voiceState.value = 'LISTENING'
  voiceAssistantText.value = ''
  setTimeout(() => startRecognitionIfNeeded(), 400)
}

// UX #5: повторить последний ответ
async function repeatLastAnswer() {
  if (!lastAssistantText.value || !ttsEnabled.value) return
  try {
    const res = await fetch('/api/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: lastAssistantText.value, voice: true }),
    })
    if (res.status === 204 || !res.ok) return
    const blob = await res.blob()
    const url  = URL.createObjectURL(blob)
    const audio = new Audio(url)
    voiceState.value = 'SPEAKING'
    audio.onended = () => {
      URL.revokeObjectURL(url)
      voiceState.value = 'LISTENING'
      startRecognitionIfNeeded()
    }
    audio.play()
  } catch (e) { console.error('[Repeat]', e) }
}

async function handleUserVoice(text) {
  const raw = text.trim()
  if (!raw) { voiceState.value = 'LISTENING'; return }
  const cleaned = stripWakePrefix(raw)
  text = cleaned.length ? cleaned : 'Привет!'
  if (voiceState.value === 'THINKING' || voiceState.value === 'SPEAKING') return

  clearSilenceCommit()

  // UX #8: останавливаем recognition — не поймаем собственный голос ИИ
  stopRecognition()

  voiceState.value         = 'THINKING'
  voiceTranscript.value    = text
  voiceAssistantText.value = ''
  voiceError.value         = ''

  history.value.push({ role: 'user',      content: text, sources: [] })
  history.value.push({ role: 'assistant', content: '',   sources: [] })
  const assistantIdx = history.value.length - 1

  const apiHistory = history.value.slice(0, -2).map(({ role, content }) => ({ role, content }))
  audioQueue = []; isAudioPlaying = false; streamDone = false

  try {
    const headers = { 'Content-Type': 'application/json' }
    const token = localStorage.getItem('token')
    if (token) headers['Authorization'] = `Bearer ${token}`

    const res = await fetch('/api/chat/voice', {
      method: 'POST',
      headers,
      body: JSON.stringify({
        message: text, history: apiHistory,
        course_id: courseId.value, course_name: courseName.value,
        page_context: { ...pageContext.value, page_content: getPageText() }
      }),
    })
    if (!res.ok) throw new Error(await res.text())

    const reader  = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      if (!voiceModeInternal) break
      const { value, done } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() ?? ''

      for (const part of parts) {
        const line = part.split('\n').map(l => l.trim()).find(l => l.startsWith('data:'))
        if (!line) continue
        const jsonText = line.slice('data:'.length).trim()
        if (!jsonText) continue
        let evt
        try { evt = JSON.parse(jsonText) } catch { continue }

        if (evt.type === 'token') {
          history.value[assistantIdx].content += String(evt.content ?? '')
          voiceAssistantText.value += String(evt.content ?? '')
        } else if (evt.type === 'sentence') {
          // UX #7: воспроизводим только если TTS включён
          if (evt.audio_b64 && ttsEnabled.value) {
            audioQueue.push(evt.audio_b64)
            playNextAudio()
          }
        } else if (evt.type === 'action' && evt.action === 'navigate') {
          executeAction(evt)
        } else if (evt.type === 'sources') {
          history.value[assistantIdx].sources = Array.isArray(evt.content) ? evt.content : []
        } else if (evt.type === 'error') {
          voiceError.value = String(evt.content ?? 'Ошибка')
        }
      }
    }

    // UX #5: сохраняем полный текст для кнопки «Повторить»
    lastAssistantText.value = history.value[assistantIdx]?.content ?? ''

    streamDone = true
    if (!isAudioPlaying && audioQueue.length === 0 && voiceModeInternal) resumeListening()

  } catch (e) {
    voiceError.value = 'Не удалось получить ответ. Попробуйте ещё раз.'
    if (voiceModeInternal) resumeListening()
  }
}

async function playNextAudio() {
  if (isAudioPlaying || audioQueue.length === 0 || !voiceModeInternal) return
  isAudioPlaying = true
  voiceState.value = 'SPEAKING'

  const b64 = audioQueue.shift()
  let safetyTimer = null

  function onAudioDone() {
    clearTimeout(safetyTimer)
    // UX: исправлена утечка — сохраняем src ДО обнуления currentAudio
    const urlToRevoke = currentAudio?.src
    isAudioPlaying = false
    currentAudio   = null
    if (urlToRevoke) try { URL.revokeObjectURL(urlToRevoke) } catch (e) {}
    if (!voiceModeInternal) return
    if (audioQueue.length > 0) playNextAudio()
    else if (streamDone) resumeListening()
  }

  try {
    const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0))
    const blob  = new Blob([bytes], { type: 'audio/mpeg' })
    const url   = URL.createObjectURL(blob)
    currentAudio = new Audio(url)
    currentAudio.onended = onAudioDone
    currentAudio.onerror = onAudioDone
    currentAudio.onloadedmetadata = () => {
      let dur = currentAudio?.duration
      if (!dur || dur === Infinity) dur = 10
      safetyTimer = setTimeout(onAudioDone, (dur + 3) * 1000)
    }
    safetyTimer = setTimeout(onAudioDone, 15000)
    await currentAudio.play()
  } catch (e) {
    clearTimeout(safetyTimer)
    isAudioPlaying = false; currentAudio = null
    if (audioQueue.length > 0) playNextAudio()
    else if (streamDone) resumeListening()
  }
}

function stopAudioQueue() {
  audioQueue = []; streamDone = true
  if (currentAudio) { currentAudio.pause(); currentAudio = null }
  isAudioPlaying = false
}

function resumeListening() {
  if (!voiceModeInternal) return
  voiceState.value = 'LISTENING'
  voiceTranscript.value = ''
  voiceAssistantText.value = ''
  lastVoiceCommitted = ''
  committedTranscript = ''  // Сбрасываем для следующей фразы
  clearSilenceCommit()
  // Задержка — даём аудио затихнуть
  setTimeout(() => {
    if (!voiceModeInternal || voiceState.value !== 'LISTENING') return
    if (usingMediaRecorderFallback) {
      startMediaRecorderListening()
    } else {
      startRecognitionIfNeeded()
    }
  }, 700)
}
*/

// ─── Text Chat SSE ─────────────────────────────────────────────────────────
const isLoading = computed(() => isBusy.value)

function renderMarkdown(text) {
  if (!text) return ''
  let clean = stripNavFromSpeech(text)
  const preserved = []
  const stashSpan = (inner) => {
    const esc = String(inner)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
    preserved.push(`<span class="hw-error">${esc}</span>`)
    return `__HW_ERR_${preserved.length - 1}__`
  }
  clean = clean.replace(
    /<span\s+(?:class=["']hw-error["']|style=["'][^"']*#ef4444[^"']*["'])[^>]*>([\s\S]*?)<\/span>/gi,
    (_, inner) => stashSpan(inner)
  )
  clean = clean.replace(/\*\*([^*\n]+)\*\*/g, (_, inner) => stashSpan(inner))
  clean = clean
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
  preserved.forEach((span, i) => {
    clean = clean.replace(`__HW_ERR_${i}__`, span)
  })
  return clean
}

function handleSend(suggestion) {
  const text = typeof suggestion === 'string' ? suggestion : message.value
  if (!text?.trim() || isBusy.value) return
  message.value = text.trim()
  sendStream()
}

async function sendStream() {
  if (!canSend.value) return
  const raw = message.value.trim()
  message.value   = ''
  errorText.value = ''

  await refreshPageContextFromRoute()

  const stripped = stripWakePrefix(raw)
  const userText = stripped.length ? stripped : (raw ? 'Привет!' : '')

  history.value.push({ role: 'user',      content: userText, sources: [] })
  history.value.push({ role: 'assistant', content: '',        sources: [] })
  const assistantIdx = history.value.length - 1

  isBusy.value = true
  await scrollBottom()

  const apiHistory = history.value.slice(0, -2).map(({ role, content }) => ({ role, content }))

  try {
    const headers = { 'Content-Type': 'application/json' }
    const token = localStorage.getItem('token')
    if (token) headers['Authorization'] = `Bearer ${token}`

    const res = await fetch('/api/chat/stream', {
      method: 'POST',
      headers,
      body: JSON.stringify({
        message: userText, history: apiHistory,
        course_id: courseId.value, course_name: courseName.value,
        page_context: { ...pageContext.value, page_content: getPageText() }
      }),
    })
    if (!res.ok || !res.body) throw new Error(await res.text())

    const reader  = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() ?? ''

      for (const part of parts) {
        const line = part.split('\n').map(l => l.trim()).find(l => l.startsWith('data:'))
        if (!line) continue
        const jsonText = line.slice('data:'.length).trim()
        if (!jsonText) continue
        let evt
        try { evt = JSON.parse(jsonText) } catch { continue }

        if (evt.type === 'sources') {
          history.value[assistantIdx].sources = normalizeSources(evt.content)
        } else if (evt.type === 'token') {
          history.value[assistantIdx].content += String(evt.content ?? '')
          await scrollBottom()
        } else if (evt.type === 'action') {
          executeAction(evt)
        } else if (evt.type === 'error') {
          errorText.value = String(evt.content ?? 'Неизвестная ошибка')
        }
      }
    }
  } catch (e) {
    const errMsg = e?.message ?? String(e)
    errorText.value = errMsg.includes('503')
      ? 'Ollama недоступна. Запустите Ollama и перезапустите бэкенд.'
      : errMsg
    if (!history.value[assistantIdx]?.content) {
      history.value.pop()
      if (history.value[assistantIdx - 1]?.role === 'user') history.value.pop()
    }
  } finally {
    isBusy.value = false
    await scrollBottom()
  }
}

// ─── Dynamic Island ─────────────────────────────────────────────────────────
const ISLAND_POS_KEY = 'eduai-island-position'
const islandContainerRef = ref(null)
const islandPos = ref(null)
const islandDragging = ref(false)
let islandDragStart = null
let islandDragMoved = false
let islandClickTimer = null

function islandAnchorFromRect(rect) {
  return { left: rect.left + rect.width / 2, top: rect.top }
}

function loadIslandPosition() {
  try {
    const raw = localStorage.getItem(ISLAND_POS_KEY)
    if (!raw) return
    const p = JSON.parse(raw)
    if (typeof p?.left === 'number' && typeof p?.top === 'number') {
      islandPos.value = { left: p.left, top: p.top }
    }
  } catch (_) {}
}

function saveIslandPosition() {
  if (!islandPos.value) return
  localStorage.setItem(ISLAND_POS_KEY, JSON.stringify(islandPos.value))
}

function clampIslandPosition(left, top) {
  const margin = 12
  const w = 220
  const h = 80
  return {
    left: Math.min(window.innerWidth - margin, Math.max(margin + w / 2, left)),
    top: Math.min(window.innerHeight - margin, Math.max(margin, top)),
  }
}

function onIslandPointerDown(e) {
  if (e.button !== 0) return
  e.stopPropagation()
  const container = islandContainerRef.value
  if (!container) return
  const rect = container.getBoundingClientRect()
  const anchor = islandPos.value ?? islandAnchorFromRect(rect)
  islandDragStart = {
    pointerId: e.pointerId,
    x: e.clientX,
    y: e.clientY,
    left: anchor.left,
    top: anchor.top,
  }
  islandDragMoved = false
  window.addEventListener('pointermove', onIslandWindowPointerMove)
  window.addEventListener('pointerup', onIslandWindowPointerUp)
  window.addEventListener('pointercancel', onIslandWindowPointerUp)
}

function onIslandWindowPointerMove(e) {
  if (!islandDragStart || islandDragStart.pointerId !== e.pointerId) return
  const dx = e.clientX - islandDragStart.x
  const dy = e.clientY - islandDragStart.y
  if (!islandDragMoved && Math.hypot(dx, dy) < 8) return
  if (!islandDragMoved) {
    islandDragMoved = true
    islandDragging.value = true
  }
  islandPos.value = clampIslandPosition(
    islandDragStart.left + dx,
    islandDragStart.top + dy,
  )
}

function onIslandWindowPointerUp(e) {
  if (!islandDragStart || islandDragStart.pointerId !== e.pointerId) return
  window.removeEventListener('pointermove', onIslandWindowPointerMove)
  window.removeEventListener('pointerup', onIslandWindowPointerUp)
  window.removeEventListener('pointercancel', onIslandWindowPointerUp)

  if (islandDragMoved) {
    saveIslandPosition()
  } else {
    if (islandClickTimer) clearTimeout(islandClickTimer)
    islandClickTimer = setTimeout(() => {
      islandClickTimer = null
      onIslandClick()
    }, 220)
  }

  islandDragStart = null
  islandDragging.value = false
}

function resetIslandPosition() {
  if (islandClickTimer) {
    clearTimeout(islandClickTimer)
    islandClickTimer = null
  }
  islandPos.value = null
  localStorage.removeItem(ISLAND_POS_KEY)
}

function onIslandClick() {
  voiceMode.value ? stopVoiceMode() : startVoiceMode()
}

const islandContainerStyle = computed(() => {
  if (!islandPos.value) return null
  return {
    left: `${islandPos.value.left}px`,
    top: `${islandPos.value.top}px`,
    transform: 'translate(-50%, 0)',
  }
})

function clearHistory() {
  history.value = []
  errorText.value = ''
  voiceHistorySyncedOrdinals = new Set()
}

const quickSuggestions = computed(() => {
  if (currentPage.value === 'course')
    return ['О чём этот курс?', 'Объясни основные понятия', 'Какие есть ещё курсы?']
  return ['Какие есть курсы?', 'Что ты умеешь?', 'С чего начать обучение?']
})
function sendSuggestion(text) { message.value = text; sendStream() }

function executeAction(evt) {
  if (evt.action === 'show_courses') {
    runShowCourseSelection({ query: evt.query })
    return
  }
  if (evt.action !== 'navigate' || evt.path === undefined || evt.path === null) return
  const path = resolveNavigatePath(evt.path)
  if (!path) {
    recordNavMetric(false, evt.path)
    return
  }
  recordNavMetric(true, path)
  const delay = voiceMode.value ? 500 : 300
  setTimeout(() => {
    if (voiceMode.value) stopVoiceMode()
    router.push(path)
  }, delay)
}

// ─── Computed ──────────────────────────────────────────────────────────────
const islandExpanded = computed(() =>
  voiceMode.value && !!(voiceTranscript.value || voiceAssistantText.value),
)

watch(voiceMode, (active) => {
  document.documentElement.classList.toggle('eduai-voice-active', !!active)
}, { immediate: true })

watch(islandExpanded, (expanded) => {
  document.documentElement.classList.toggle('island-expanded-page', !!expanded)
}, { immediate: true })

const voiceStatusText = computed(() => {
  if (voiceState.value === 'LISTENING') {
    if (isHearingSpeech.value) return 'Слышу вас...'
    return 'Говорите...'
  }
  if (voiceState.value === 'THINKING') return 'Думаю...'
  if (voiceState.value === 'SPEAKING') return 'Отвечаю...'
  return 'Ожидание...'
})

// UX #1: масштаб орба от громкости микрофона
const orbScale = computed(() => {
  if (voiceState.value === 'SPEAKING') return 1 + 0.12
  if (voiceState.value !== 'LISTENING') return 1
  return 1 + (micVolume.value / 100) * 0.25
})

// ─── Draggable Orb ─────────────────────────────────────────────────────────
const orbX = ref(window.innerWidth  - 96)
const orbY = ref(window.innerHeight - 96)
const panelsAnchorRef = ref(null)
const orbWrapRef = ref(null)

let dragActive = false
let dragOffsetX = 0
let dragOffsetY = 0
let dragMoved   = false
const ORB_SIZE  = 68

function onOrbPointerDown(e) {
  dragActive  = true
  dragMoved   = false
  dragOffsetX = e.clientX - orbX.value
  dragOffsetY = e.clientY - orbY.value
  e.currentTarget.setPointerCapture(e.pointerId)
  e.preventDefault()
}

function onOrbPointerMove(e) {
  if (!dragActive) return
  const nx = e.clientX - dragOffsetX
  const ny = e.clientY - dragOffsetY
  if (Math.abs(nx - orbX.value) > 3 || Math.abs(ny - orbY.value) > 3) dragMoved = true
  
  // Вычисляем новые границы
  const finalX = Math.max(0, Math.min(window.innerWidth  - ORB_SIZE, nx))
  const finalY = Math.max(0, Math.min(window.innerHeight - ORB_SIZE, ny))
  
  orbX.value = finalX
  orbY.value = finalY

  // Прямая мутация DOM для 144Hz без фризов Vue
  if (orbWrapRef.value) {
    orbWrapRef.value.style.left = finalX + 'px'
    orbWrapRef.value.style.top  = finalY + 'px'
  }
  if (panelsAnchorRef.value) {
    panelsAnchorRef.value.style.left = finalX + 'px'
    panelsAnchorRef.value.style.top  = finalY + 'px'
  }
}

function onOrbPointerUp(e) {
  dragActive = false
  if (!dragMoved) togglePanel()
}
</script>
<template>
  <div>
    <!-- Chat FAB -->
    <button class="chat-fab" @click="togglePanel" :title="isOpen ? 'Закрыть чат' : 'Открыть чат EduAI'">
      <svg v-if="isOpen" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
        <line x1="18" y1="6" x2="6" y2="18"/>
        <line x1="6" y1="6" x2="18" y2="18"/>
      </svg>
      <svg v-else width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
        <path d="M12 8v4" />
        <path d="M12 16h.01" />
      </svg>
    </button>

    <!-- Panels anchor (text chat) in bottom right -->
    <div class="panels-anchor" ref="panelsAnchorRef" :class="{'panels-open': isOpen}">
      <transition name="panel-fade">
        <div v-if="isOpen && !voiceMode" class="widget-panel">
          <div class="wp-header">
            <div class="wp-header-left">
              <span class="wp-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                  <path d="M12 2L2 7l10 5 10-5-10-5z" fill="currentColor" opacity="0.8"/>
                  <path d="M2 17l10 5 10-5" />
                  <path d="M2 12l10 5 10-5" />
                </svg>
              </span>
              <div>
                <div class="wp-title">EduAI</div>
                <div class="wp-status">Online</div>
              </div>
            </div>
            <button class="icon-btn" @click="togglePanel">✕</button>
          </div>
          <div v-if="homeworkReminder && !history.length" class="wp-reminder">
            <span>📋 {{ homeworkReminder }}</span>
            <button type="button" class="icon-btn" @click="homeworkReminder = ''" title="Скрыть">✕</button>
          </div>
          <!-- Messages -->
          <div class="wp-thread" ref="threadEl">
            <!-- Greeting -->
            <div class="msg-row bot-row">
              <div class="msg-bubble bot-bubble">
                <div class="msg-md">Привет! Я твой персональный ИИ-ассистент <b>{{ courseName }}</b>.<br>Чем могу помочь сегодня?</div>
              </div>
            </div>

            <!-- History -->
            <div class="msg-row" v-for="(msg, i) in history" :key="i" :class="msg.role === 'user' ? 'user-row' : 'bot-row'">
              <div class="msg-bubble" :class="msg.role === 'user' ? 'user-bubble' : 'bot-bubble'">
                <div class="msg-md" v-html="renderMarkdown(msg.content)"></div>
                <div v-if="msg.sources && msg.sources.length" class="bubble-sources">
                  <span class="source-chip" v-for="(src, idx) in msg.sources" :key="idx" :title="typeof src === 'string' ? src : src.title">
                    <span class="src-icon">📄</span>
                    <span class="src-name">{{ typeof src === 'string' ? src : (src.title || src.file_name) }}</span>
                  </span>
                </div>
                <button v-if="msg.role === 'assistant'" class="icon-btn" @click="speakText(msg.content)" title="Озвучить">🔊</button>
              </div>
            </div>

            <!-- Loading indicator -->
            <div class="msg-row bot-row" v-if="isLoading">
              <div class="msg-bubble bot-bubble">
                <div class="typing-indicator"><span></span><span></span><span></span></div>
              </div>
            </div>

            <!-- Error message -->
            <div class="msg-row bot-row" v-if="errorText">
              <div class="msg-bubble error-bubble">
                {{ errorText }}
              </div>
            </div>
          </div>

          <!-- Quick Suggestions -->
          <div class="wp-suggestions" v-if="quickSuggestions.length && !isLoading && !history.length">
            <button v-for="(sug, idx) in quickSuggestions" :key="idx" class="sug-btn" @click="handleSend(sug)">
              {{ sug }}
            </button>
        </div>

          <!-- Input -->
          <div class="wp-input">
            <button class="icon-btn voice-trigger-btn" @click="startVoiceMode('')" title="Голосовой режим">🎤</button>
            <div class="wp-input-wrap">
              <input
                v-model="message"
                type="text"
                placeholder="Спроси что-нибудь..."
                @keydown.enter="handleSend()"
                :disabled="isLoading"
                maxlength="1500"
              />
              <span class="char-counter" :class="{ 'char-warn': message.length > 1200 }">
                {{ message.length }}/1500
              </span>
            </div>
            <button class="send-btn" @click="handleSend()" :disabled="isLoading || !message.trim()">➤</button>
          </div>
        </div>
      </transition>
      </div>

    <!-- Громкость и действия во время звонка -->
    <div class="voice-dock" v-if="voiceMode" @click.stop>
      <span class="voice-dock-vol-icon" aria-hidden="true">🔈</span>
      <input
        type="range"
        class="voice-dock-slider"
        min="0"
        max="100"
        v-model.number="voiceVolumePct"
        @input="applyVoiceVolume"
        @change="applyVoiceVolume"
        title="Громкость ИИ Ассистента"
      />
      <button type="button" class="voice-dock-btn" @click="isOpen = true" title="Открыть чат">💬</button>
      <button type="button" class="voice-dock-btn voice-dock-end" @click="stopVoiceMode" title="Завершить">✕</button>
    </div>

    <!-- ══════════════════════ DYNAMIC ISLAND (iPhone-style) -->
    <div
      ref="islandContainerRef"
      class="island-system-container"
      :class="{
        'is-expanded': islandExpanded,
        'is-voice': voiceMode,
        'is-custom-pos': !!islandPos,
        'is-dragging': islandDragging,
      }"
      :style="islandContainerStyle"
      @dblclick.stop.prevent="resetIslandPosition"
    >
      <div
        class="island-rgb-shell"
        :class="[
          { active: voiceMode, expanded: islandExpanded },
          voiceMode ? voiceState.toLowerCase() : ''
        ]"
      >
      <div class="island-stack" :class="{ expanded: islandExpanded }">
      <!-- Main Island -->
      <div
        class="dynamic-island"
        :class="{
          'island-voice': voiceMode,
          'island-listening': voiceMode && voiceState === 'LISTENING',
          'island-thinking': voiceMode && voiceState === 'THINKING',
          'island-speaking': voiceMode && voiceState === 'SPEAKING',
          'island-compact': !islandExpanded,
        }"
        @pointerdown="onIslandPointerDown"
        :title="voiceMode ? 'Завершить звонок (перетащите капсулу, чтобы переместить)' : 'Голосовой ассистент (перетащите капсулу, чтобы переместить)'"
      >
        <!-- Иконка/Волна -->
        <span class="island-icon" v-if="!voiceMode">
          <!-- Small Microphone Icon when idle -->
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" fill="currentColor" stroke="none" opacity="0.9"/>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
            <line x1="12" y1="19" x2="12" y2="23"/>
            <line x1="8" y1="23" x2="16" y2="23"/>
          </svg>
        </span>

        <div class="island-voice-wave" v-if="voiceMode && voiceState === 'LISTENING'">
          <span v-for="i in 5" :key="i" class="wave-bar" 
            :style="{ height: (4 + (micVolume / 100) * 16) + 'px', animationDelay: (i * 0.1) + 's' }">
      </span>
        </div>
        
        <div class="island-voice-thinking" v-if="voiceMode && voiceState === 'THINKING'">
          <span class="dot"></span><span class="dot"></span><span class="dot"></span>
        </div>

        <div class="island-voice-wave speaking" v-if="voiceMode && voiceState === 'SPEAKING'">
          <span v-for="i in 5" :key="i" class="wave-bar"></span>
        </div>

        <!-- Текст состояния -->
        <span v-if="voiceMode" class="island-status-text">
          {{ voiceStatusText }}
        </span>
        <span v-if="!voiceMode" class="island-label">Голосовой помощник</span>
      </div>

      <transition name="island-expand">
        <div v-if="islandExpanded" class="island-transcript-pane">
          <div class="island-transcript-divider"></div>
          <div class="transcript-content" v-if="voiceState === 'LISTENING'">
            <span class="user-label">Вы</span>
            <span class="transcript-text">{{ voiceTranscript || 'Слушаю…' }}</span>
          </div>
          <div class="transcript-content bot" v-else-if="voiceAssistantText">
            <span class="bot-label">Голосовой помощник</span>
            <span class="transcript-text" v-html="renderMarkdown(voiceAssistantText)"></span>
          </div>
          <div class="transcript-content muted" v-else>
            <span class="transcript-text">…</span>
          </div>
        </div>
      </transition>
      </div>
      </div>
    </div>
    <!-- Course Selection Modal -->
    <transition name="fade">
      <div v-if="showCourseSelectionModal" class="course-selection-overlay" @click.self="showCourseSelectionModal = false">
        <div class="course-selection-modal glass-panel">
          <h3>Выберите курс</h3>
          <p class="modal-subtitle">По вашему запросу найдено несколько вариантов:</p>
          <div class="course-list">
            <button
              v-for="c in courseSelectionList"
              :key="c.id"
              class="course-btn glass-btn"
              @click="showCourseSelectionModal = false; navigateToCourse(c.id)"
            >
              <span class="course-icon">{{ c.icon || '📚' }}</span>
              <div class="course-info">
                <div class="course-title">{{ c.title }}</div>
                <div class="course-desc" v-if="c.description">{{ c.description.slice(0, 50) }}...</div>
              </div>
            </button>
          </div>
          <button class="close-modal-btn glass-btn" @click="showCourseSelectionModal = false">Отмена</button>
        </div>
      </div>
    </transition>

  </div>
</template>
<style scoped>
/* ─── Chat FAB (Floating Action Button) ──────────────────── */
.chat-fab {
  position: fixed;
  bottom: 24px;
  right: 24px;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
  border: none;
  font-size: 24px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 24px rgba(0,0,0,0.3);
  z-index: 9999;
  transition: transform 0.2s cubic-bezier(0.3, 1.5, 0.5, 1), background 0.2s;
  will-change: transform;
}
.chat-fab:hover {
  transform: scale(1.08);
  background: var(--accent-hover);
}
.chat-fab:active {
  transform: scale(0.95);
}

/* ─── Text Chat Panel ──────────────────────── */
.panels-anchor {
  position: fixed;
  bottom: 90px;
  right: 24px;
  z-index: 9998;
  pointer-events: none;
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}
.panels-anchor > * { pointer-events: auto; }

.widget-panel {
  width: 380px;
  max-width: calc(100vw - 32px);
  background: rgba(18, 18, 22, 0.85);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 24px 48px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.05) inset;
  height: 550px;
  max-height: calc(100vh - 120px);
}

/* ─── Course Selection Modal ──────────────────────── */
.course-selection-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.course-selection-modal {
  width: 400px;
  max-width: 90vw;
  background: rgba(30, 30, 36, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 24px;
  padding: 24px;
  box-shadow: 0 32px 64px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.05) inset;
  display: flex;
  flex-direction: column;
  gap: 16px;
  font-family: 'Inter', sans-serif;
  color: white;
}

.course-selection-modal h3 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.course-selection-modal .modal-subtitle {
  margin: 0;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 8px;
}

.course-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 50vh;
  overflow-y: auto;
}

.course-btn {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  cursor: pointer;
  transition: background 0.2s, transform 0.1s;
  text-align: left;
  color: white;
}

.course-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  transform: translateY(-2px);
}

.course-btn:active {
  transform: translateY(0);
}

.course-icon {
  font-size: 24px;
}

.course-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.course-title {
  font-weight: 600;
  font-size: 15px;
}

.course-desc {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  line-height: 1.3;
}

.close-modal-btn {
  margin-top: 8px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.08);
  border: none;
  border-radius: 16px;
  color: white;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.close-modal-btn:hover {
  background: rgba(255, 255, 255, 0.12);
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

.panel-fade-enter-active, .panel-fade-leave-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  transform-origin: bottom right;
}
.panel-fade-enter-from, .panel-fade-leave-to {
  opacity: 0;
  transform: scale(0.9) translateY(20px);
}

/* ─── Dynamic Island (iPhone-style) ─────────────────── */
@property --island-rgb-angle {
  syntax: '<angle>';
  initial-value: 0deg;
  inherits: false;
}

/* ─── Suggestions ────────────────────────── */
.wp-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 0 16px 12px;
}
.sug-btn {
  background: var(--bg-raised);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 6px 12px;
  font-size: 13px;
  color: var(--text);
  cursor: pointer;
  transition: all 0.2s;
  font-family: inherit;
}
.sug-btn:hover {
  background: var(--accent-subtle);
  border-color: rgba(99, 102, 241, 0.3);
  color: #fff;
}

@keyframes islandRgbSpin {
  to {
    --island-rgb-angle: 360deg;
  }
}

@media (prefers-reduced-motion: reduce) {
  .island-rgb-shell.active {
    animation: none;
    background: linear-gradient(120deg, #6366f1, #22d3ee, #c084fc, #fb7185);
  }
}

.island-system-container {
  position: fixed;
  top: max(10px, env(safe-area-inset-top, 0px));
  left: 50%;
  transform: translateX(-50%) translateZ(0);
  z-index: 9990;
  display: flex;
  flex-direction: column;
  align-items: center;
  pointer-events: none;
  transition:
    top 0.45s cubic-bezier(0.32, 0.72, 0, 1),
    left 0.35s cubic-bezier(0.32, 0.72, 0, 1),
    transform 0.35s cubic-bezier(0.32, 0.72, 0, 1);
  touch-action: manipulation;
}

.island-system-container.is-custom-pos {
  left: auto;
}

.island-system-container.is-dragging {
  touch-action: none;
  transition: none !important;
}

.island-system-container.is-voice.is-expanded:not(.is-custom-pos) {
  top: max(76px, calc(env(safe-area-inset-top, 0px) + 64px));
}

.island-rgb-shell {
  position: relative;
  border-radius: 999px;
  pointer-events: auto;
}

.island-rgb-shell.active {
  padding: 2px;
  border-radius: 999px;
  background: conic-gradient(
    from var(--island-rgb-angle),
    var(--glow-1, #6366f1),
    var(--glow-2, #22d3ee),
    var(--glow-3, #c084fc),
    var(--glow-4, #fb7185),
    var(--glow-5, #fbbf24),
    var(--glow-1, #6366f1)
  );
  animation: islandRgbSpin 3.2s linear infinite;
  box-shadow:
    0 0 18px rgba(99, 102, 241, 0.45),
    0 0 36px rgba(34, 211, 238, 0.2),
    0 8px 28px rgba(0, 0, 0, 0.45);
  transition: all 0.5s ease;
}

.island-rgb-shell.active.listening {
  --glow-1: #3b82f6; --glow-2: #10b981; --glow-3: #0ea5e9; --glow-4: #3b82f6; --glow-5: #6366f1;
  animation-duration: 2.5s;
  box-shadow: 0 0 24px rgba(59, 130, 246, 0.5);
}

.island-rgb-shell.active.thinking {
  --glow-1: #f59e0b; --glow-2: #f43f5e; --glow-3: #8b5cf6; --glow-4: #ec4899; --glow-5: #f59e0b;
  animation-duration: 1.2s;
  box-shadow: 0 0 32px rgba(244, 63, 94, 0.6);
}

.island-rgb-shell.active.speaking {
  --glow-1: #10b981; --glow-2: #84cc16; --glow-3: #14b8a6; --glow-4: #22c55e; --glow-5: #10b981;
  animation-duration: 1.5s;
  box-shadow: 0 0 32px rgba(16, 185, 129, 0.6);
}

.island-rgb-shell.active.expanded {
  border-radius: 30px;
}

.island-rgb-shell.active::after {
  content: '';
  position: absolute;
  inset: 3px;
  border-radius: inherit;
  background: radial-gradient(ellipse at 50% 0%, rgba(255, 255, 255, 0.06), transparent 55%);
  pointer-events: none;
  z-index: 0;
}

.island-stack {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  position: relative;
  z-index: 1;
  filter: drop-shadow(0 4px 16px rgba(0, 0, 0, 0.35));
  transition: transform 0.45s cubic-bezier(0.32, 0.72, 0, 1);
}

.island-rgb-shell:not(.active) .island-stack {
  filter: drop-shadow(0 8px 28px rgba(0, 0, 0, 0.45));
}

.island-stack.expanded {
  background: rgba(25, 25, 28, 0.85);
  backdrop-filter: blur(24px);
  border-radius: 28px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  overflow: hidden;
  min-width: 300px;
  max-width: min(420px, calc(100vw - 32px));
  box-shadow: 
    0 16px 40px rgba(0, 0, 0, 0.6),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.island-rgb-shell.active .island-stack.expanded {
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 28px;
}

.dynamic-island {
  background: rgba(25, 25, 28, 0.85);
  backdrop-filter: blur(24px);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #fff;
  border-radius: 999px;
  height: 40px;
  min-width: 110px;
  padding: 0 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  box-shadow: 
    0 8px 24px rgba(0, 0, 0, 0.5),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
  transition: all 0.35s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  user-select: none;
  position: relative;
  z-index: 2;
}

.island-stack:not(.expanded) .dynamic-island:hover {
  background: rgba(35, 35, 40, 0.9);
  border-color: rgba(255, 255, 255, 0.18);
  transform: scale(1.02);
}

.island-system-container.is-dragging .dynamic-island {
  cursor: grabbing;
}

.island-stack.expanded .dynamic-island {
  border-radius: 0;
  background: transparent;
  backdrop-filter: none;
  border: none;
  min-width: 0;
  width: 100%;
  box-shadow: none;
}

.island-voice { min-width: 168px; }
.island-listening, .island-thinking, .island-speaking { background: rgba(255, 255, 255, 0.03); }

.island-rgb-shell.active .island-listening,
.island-rgb-shell.active .island-thinking,
.island-rgb-shell.active .island-speaking {
  background: transparent;
}

.island-icon svg {
  color: #e4e4e7;
  transition: color 0.2s;
}
.island-stack:not(.expanded) .dynamic-island:hover .island-icon svg {
  color: #fff;
}

.island-icon, .island-label, .island-status-text {
  font-family: -apple-system, BlinkMacSystemFont, 'Inter', system-ui, sans-serif;
  font-weight: 600;
  font-size: 13px;
  letter-spacing: -0.01em;
  white-space: nowrap;
}

.island-status-text { font-size: 12px; opacity: 0.92; }

.island-voice-wave {
  display: flex;
  align-items: center;
  gap: 2px;
  height: 18px;
}
.wave-bar {
  width: 2px;
  background: #fff;
  border-radius: 2px;
  transition: height 0.1s ease;
}
.island-voice-wave.speaking .wave-bar { animation: wavePulse 0.9s infinite alternate; }
.island-voice-wave.speaking .wave-bar:nth-child(1) { animation-delay: 0.1s; }
.island-voice-wave.speaking .wave-bar:nth-child(2) { animation-delay: 0.25s; }
.island-voice-wave.speaking .wave-bar:nth-child(3) { animation-delay: 0s; }
.island-voice-wave.speaking .wave-bar:nth-child(4) { animation-delay: 0.3s; }
.island-voice-wave.speaking .wave-bar:nth-child(5) { animation-delay: 0.15s; }

@keyframes wavePulse {
  0% { height: 4px; }
  100% { height: 16px; }
}

.island-voice-thinking { display: flex; align-items: center; gap: 4px; }
.island-voice-thinking .dot {
  width: 5px;
  height: 5px;
  background: #fff;
  border-radius: 50%;
  animation: dotPulse 1.4s infinite;
}
.island-voice-thinking .dot:nth-child(2) { animation-delay: 0.2s; }
.island-voice-thinking .dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes dotPulse {
  0%, 80%, 100% { opacity: 0.35; transform: scale(0.85); }
  40% { opacity: 1; transform: scale(1.1); }
}

.island-transcript-pane {
  padding: 0 16px 14px;
  font-family: -apple-system, BlinkMacSystemFont, 'Inter', system-ui, sans-serif;
  font-size: 13px;
  line-height: 1.45;
  color: #f5f5f7;
  pointer-events: auto;
}

.island-transcript-divider {
  height: 1px;
  margin: 0 0 10px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.14) 20%,
    rgba(255, 255, 255, 0.14) 80%,
    transparent
  );
}

.transcript-content {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 8px;
  align-items: baseline;
  max-height: 4.5em;
  overflow: hidden;
}

.transcript-content.muted { opacity: 0.5; }

.transcript-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.user-label, .bot-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  flex-shrink: 0;
}
.user-label { color: #8e8e93; }
.bot-label { color: #64d2ff; }

.island-expand-enter-active,
.island-expand-leave-active {
  transition: opacity 0.28s ease, max-height 0.38s cubic-bezier(0.32, 0.72, 0, 1);
  overflow: hidden;
}
.island-expand-enter-from,
.island-expand-leave-to {
  opacity: 0;
  max-height: 0;
}
.island-expand-enter-to,
.island-expand-leave-from {
  opacity: 1;
  max-height: 120px;
}

/* Voice dock — громкость справа внизу */
.voice-dock {
  position: fixed;
  bottom: 92px;
  right: 24px;
  z-index: 10000;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(12, 12, 14, 0.92);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 999px;
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.35);
  pointer-events: auto;
}

.voice-dock-vol-icon {
  font-size: 14px;
  line-height: 1;
  opacity: 0.85;
}

.voice-dock-slider {
  width: 88px;
  height: 4px;
  accent-color: #6366f1;
  cursor: pointer;
}

.voice-dock-btn {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}
.voice-dock-btn:hover { background: rgba(255, 255, 255, 0.16); }
.voice-dock-end { background: rgba(239, 68, 68, 0.25); }
.voice-dock-end:hover { background: rgba(239, 68, 68, 0.45); }

/* ─── Chat Internal Styles ────────────────────────────────── */
.wp-header { padding: 18px 20px; border-bottom: 1px solid rgba(255,255,255,0.08); display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.02); }
.wp-reminder {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 14px;
  font-size: 13px;
  line-height: 1.4;
  color: #fcd34d;
  background: rgba(251, 191, 36, 0.08);
  border-bottom: 1px solid rgba(251, 191, 36, 0.2);
}
.wp-header-left { display: flex; align-items: center; gap: 12px; }
.wp-icon { color: #fff; background: linear-gradient(135deg, var(--accent) 0%, #818cf8 100%); width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; border-radius: 12px; box-shadow: 0 4px 12px rgba(99,102,241,0.3); }
.wp-title { font-weight: 700; font-size: 16px; letter-spacing: -0.01em; }
.wp-status { font-size: 12px; color: #10b981; display: flex; align-items: center; gap: 6px; margin-top: 2px; }
.wp-status::before { content: ''; width: 6px; height: 6px; background: #10b981; border-radius: 50%; box-shadow: 0 0 8px rgba(16,185,129,0.5); }

.wp-thread { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 16px; scroll-behavior: smooth; }
.msg-row { display: flex; width: 100%; }
.user-row { justify-content: flex-end; }
.bot-row { justify-content: flex-start; }
.msg-bubble { max-width: 85%; padding: 12px 16px; border-radius: 16px; font-size: 14px; line-height: 1.5; position: relative; }
.user-bubble { background: linear-gradient(135deg, var(--accent) 0%, #5254cc 100%); color: white; border-bottom-right-radius: 4px; box-shadow: 0 4px 12px rgba(99,102,241,0.2); }
.bot-bubble { background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08); border-bottom-left-radius: 4px; color: #f0f0f5; }
.error-bubble { background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3); color: #fca5a5; }
.msg-md :deep(.hw-error) { color: #ef4444; font-weight: 700; }

.wp-input { padding: 12px 16px; border-top: 1px solid var(--border); display: flex; gap: 8px; align-items: center; background: rgba(0,0,0,0.2); }
.wp-input-wrap { flex: 1; display: flex; flex-direction: column; gap: 2px; }
.wp-input input { flex: 1; background: transparent; border: none; color: var(--text); font-size: 14px; outline: none; width: 100%; }
.char-counter { font-size: 10px; color: rgba(255,255,255,0.3); text-align: right; line-height: 1; }
.char-counter.char-warn { color: #f59e0b; }
.icon-btn { background: none; border: none; cursor: pointer; color: var(--text); opacity: 0.7; transition: opacity 0.2s; display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 8px; }
.icon-btn:hover { opacity: 1; background: rgba(255,255,255,0.05); }
.send-btn { background: var(--accent); color: white; border: none; border-radius: 10px; width: 36px; height: 36px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 16px; transition: transform 0.1s; }
.send-btn:active { transform: scale(0.95); }
.send-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.bubble-sources { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.1); }
.source-chip { font-size: 11px; padding: 4px 8px; background: rgba(255,255,255,0.1); border-radius: 6px; display: flex; align-items: center; gap: 4px; cursor: default; }
.src-page { opacity: 0.7; font-size: 10px; }
</style>
