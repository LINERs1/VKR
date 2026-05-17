<script setup>
import { ref, nextTick, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { UltravoxSession } from 'ultravox-client'

const route = useRoute()
const router = useRouter()

// ─── Page & Course Context ────────────────────────────────────────────────
const courseId   = ref('default')
const courseName = ref('EduAI')
const courseIcon = ref('🤖')
const currentPage = ref('home')
const allCourses  = ref([])

async function loadAllCourses() {
  try {
    const res = await fetch('/api/courses')
    if (res.ok) allCourses.value = await res.json()
  } catch (e) {}
}

function getPageText() {
  try {
    const mainEl = document.querySelector('main') || document.querySelector('#app') || document.body
    return (mainEl.innerText || '').slice(0, 1500)
  } catch (e) { return '' }
}

const pageContext = computed(() => ({
  current_path: route.path,
  current_page: currentPage.value,
  current_course_id:   courseId.value !== 'default' ? courseId.value : null,
  current_course_name: courseId.value !== 'default' ? courseName.value : null,
  available_courses: allCourses.value.map(c => ({
    id: c.id, title: c.title, icon: c.icon || '', description: c.description || ''
  }))
}))

watch(() => [route.path, route.params.id], async ([newPath, newId]) => {
  if (newPath.startsWith('/homeworks/') && newId) {
    currentPage.value = 'homework'
    courseId.value    = window.currentHomeworkContext?.courseId || 'default'
    courseName.value  = window.currentHomeworkContext?.title || 'Домашнее задание'
    courseIcon.value  = '📝'
    return
  }
  
  if (newPath.startsWith('/courses/') && newId) {
    currentPage.value = 'course'
    try {
      const res = await fetch(`/api/courses/${newId}`)
      if (res.ok) {
        const data = await res.json()
        courseId.value   = data.id
        courseName.value = data.title
        courseIcon.value = data.icon
      }
    } catch (e) {}
  } else if (newPath.startsWith('/journal')) {
    currentPage.value = 'Журнал успеваемости'
    courseId.value    = 'default'
    courseName.value  = 'Журнал'
    courseIcon.value  = '📊'
  } else if (newPath.startsWith('/profile')) {
    currentPage.value = 'Профиль пользователя'
    courseId.value    = 'default'
    courseName.value  = 'Профиль'
    courseIcon.value  = '👤'
  } else if (newPath === '/') {
    currentPage.value = 'Главная страница'
    courseId.value    = 'default'
    courseName.value  = 'EduAI'
    courseIcon.value  = '🤖'
  } else {
    currentPage.value = 'Неизвестная страница'
    courseId.value    = 'default'
    courseName.value  = 'EduAI'
    courseIcon.value  = '🤖'
  }
}, { immediate: true })

// ─── Text Chat State ───────────────────────────────────────────────────────
const isOpen    = ref(false)
const history   = ref([])
const message   = ref('')
const isBusy    = ref(false)
const errorText = ref('')
const threadEl  = ref(null)

// UX #7: переключатель TTS
const ttsEnabled = ref(true)

const canSend = computed(() => message.value.trim().length > 0 && !isBusy.value)

function togglePanel() {
  if (voiceMode.value) { stopVoiceMode(); return }
  isOpen.value = !isOpen.value
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
let lastVoiceNavPath = null
let voiceUserHasSpoken = false
let pendingNavPath = null

const STATIC_NAV_PATHS = ['/', '/profile', '/journal', '/homeworks']
const VOICE_YES_RE = /\b(да|давай|ок|окей|конечно|переводи|открывай|хорошо|ага|угу)\b/ui

function stripNavFromSpeech(text) {
  if (!text) return ''
  return String(text)
    .replace(/\[NAVIGATE:[^\]]+\]/gi, '')
    .replace(/\bNAVIGATE\s*:?\s*\/?\s*[^\s\],.]*/gi, '')
    .replace(/\bnavigate\s+(?:to\s+)?\/?\s*[^\s\],.]*/gi, '')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

function extractNavPathFromText(raw) {
  if (!raw) return null
  const patterns = [
    /\[NAVIGATE:\s*([^\]]+)\]/i,
    /\bNAVIGATE\s*:?\s*(\/[^\s\],.]+)/i,
    /\bnavigate\s+(?:to\s+)?(\/courses\/[^\s\],.]+)/i,
    /\bnavigate\s+(?:to\s+)?courses\/([a-z0-9_-]+)/i,
  ]
  for (const re of patterns) {
    const m = raw.match(re)
    if (!m) continue
    let p = m[1].trim()
    if (!p.startsWith('/')) p = `/courses/${p}`
    return p
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
    { id: 'python', keys: ['python', 'питон', 'пайтон'] },
    { id: 'ml', keys: ['машинн', 'machine learning', 'ml '] },
    { id: 'webdev', keys: ['веб-разработ', 'веб разработ', 'webdev', 'frontend'] },
    { id: 'sql', keys: ['sql', 'баз данных', 'postgresql'] },
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
  if (!rawPath) return null
  let path = String(rawPath).trim()
  if (!path.startsWith('/')) path = `/${path}`
  path = path.replace(/\/+$/, '') || '/'

  if (STATIC_NAV_PATHS.includes(path)) return path

  const m = path.match(/^\/courses\/(.+)$/i)
  if (!m) return null

  const slug = decodeURIComponent(m[1]).toLowerCase().trim()
  const courses = allCourses.value || []
  if (!courses.length) return null

  let found = courses.find(c => c.id?.toLowerCase() === slug)
  if (found) return `/courses/${found.id}`

  const keywords = [
    { id: 'python', keys: ['python', 'питон', 'пайтон'] },
    { id: 'ml', keys: ['ml', 'машинн', 'machine', 'learning'] },
    { id: 'webdev', keys: ['web', 'веб', 'frontend', 'html'] },
    { id: 'sql', keys: ['sql', 'баз данных', 'postgres'] },
  ]
  for (const { id, keys } of keywords) {
    if (keys.some(k => slug.includes(k))) {
      found = courses.find(c => c.id === id)
      if (found) return `/courses/${found.id}`
    }
  }

  found = courses.find(c => {
    const t = (c.title || '').toLowerCase()
    return t.includes(slug) || slug.includes((c.id || '').toLowerCase())
  })
  if (found) return `/courses/${found.id}`

  return null
}

function tryVoiceNavigate(rawPath) {
  const path = resolveNavigatePath(rawPath)
  if (!path) {
    console.warn('[nav] неизвестный путь:', rawPath)
    return false
  }

  // Не навигировать на главную из приветствия (до реплики пользователя)
  if (!voiceUserHasSpoken && path === '/') return false

  const current = (route.path || '/').replace(/\/+$/, '') || '/'
  const target = path.replace(/\/+$/, '') || '/'
  if (current === target) {
    pendingNavPath = null
    return true
  }

  if (path === lastVoiceNavPath) return true
  lastVoiceNavPath = path
  pendingNavPath = null
  router.push(path)
  return true
}

// ─── Ultravox helpers ─────────────────────────────────────────────────────
async function startUltravoxSession() {
  try {
    voiceError.value = ''
    voiceState.value = 'THINKING'
    lastVoiceNavPath = null
    voiceUserHasSpoken = false
    pendingNavPath = null

    if (!allCourses.value.length) await loadAllCourses()

    const token = localStorage.getItem('token')
    const headers = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`

    const res = await fetch('/api/ultravox/call', {
      method: 'POST',
      headers,
      body: JSON.stringify({
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
    const { joinUrl } = await res.json()

    uvSession = new UltravoxSession()
    await uvSession.joinCall(joinUrl)

    // Слушаем статус сессии
    uvSession.addEventListener('status', (e) => {
      const status = uvSession.status
      if (status === 'idle' || status === 'disconnected') {
        voiceState.value = 'IDLE'
      } else if (status === 'listening') {
        voiceState.value = 'LISTENING'
        isHearingSpeech.value = true
      } else if (status === 'thinking') {
        voiceState.value = 'THINKING'
        isHearingSpeech.value = false
      } else if (status === 'speaking') {
        voiceState.value = 'SPEAKING'
        isHearingSpeech.value = false
      }
    })

    // Слушаем транскрипт пользователя
    uvSession.addEventListener('transcripts', (e) => {
      const transcripts = uvSession.transcripts
      if (!transcripts || !transcripts.length) return
      const last = transcripts[transcripts.length - 1]
      if (last.speaker === 'user') {
        voiceUserHasSpoken = true
        voiceTranscript.value = last.text
        const userText = (last.text || '').trim()
        if (VOICE_YES_RE.test(userText) && pendingNavPath) {
          tryVoiceNavigate(pendingNavPath)
        }
      } else if (last.speaker === 'agent') {
        const raw = last.text || ''
        const display = stripNavFromSpeech(raw)
        voiceAssistantText.value = display
        lastAssistantText.value = display

        const navPath = extractNavPathFromText(raw)
        if (navPath) {
          tryVoiceNavigate(navPath)
        } else {
          const offer = detectCourseOfferInText(display)
          if (offer) pendingNavPath = offer
        }
      }
    })

    // Слушаем data-сообщения (навигация через [NAVIGATE:/...])
    uvSession.addEventListener('experimental_message', (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data?.type === 'navigate' && data?.path) {
          router.push(data.path)
        }
      } catch {}
    })

    voiceState.value = 'LISTENING'

  } catch (err) {
    console.error('[Ultravox] start error:', err)
    voiceError.value = `Ошибка подключения: ${err.message}`
    voiceState.value = 'IDLE'
    voiceMode.value = false
  }
}

async function stopUltravoxSession() {
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
const WAKE_WORDS = ['кортана', 'кортан', 'эдуай', 'edu ai', 'ассистент', 'помоги мне']

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

const WAKE_WORDS = ['кортана', 'кортан', 'эдуай', 'edu ai', 'ассистент', 'помоги мне']

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
      // не отрезать «ассистент» из «ассистентский», «кортан» из «кортанка»
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

onMounted(() => {
  loadAllCourses()
  window.addEventListener('beforeunload', forceCleanup)
})

onUnmounted(() => {
  forceCleanup()
  window.removeEventListener('beforeunload', forceCleanup)
})

// ─── Voice Mode (Ultravox) ─────────────────────────────────────────────────
function startVoiceMode() {
  isOpen.value = false
  voiceMode.value = true
  voiceError.value = ''
  voiceTranscript.value = ''
  voiceAssistantText.value = ''
  lastAssistantText.value = ''
  lastVoiceNavPath = null
  voiceUserHasSpoken = false
  pendingNavPath = null
  startUltravoxSession()
}

function stopVoiceMode() {
  voiceMode.value = false
  voiceState.value = 'IDLE'
  voiceError.value = ''
  voiceTranscript.value = ''
  voiceAssistantText.value = ''
  stopUltravoxSession()
}

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
  const clean = stripNavFromSpeech(text)
  return clean
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
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
          history.value[assistantIdx].sources = Array.isArray(evt.content) ? evt.content : []
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
    errorText.value = e?.message ?? String(e)
    if (!history.value[assistantIdx]?.content) history.value.pop()
  } finally {
    isBusy.value = false
  }
}

// ─── Dynamic Island ─────────────────────────────────────────────────────────
function onIslandClick() { voiceMode.value ? stopVoiceMode() : startVoiceMode() }

function clearHistory() { history.value = []; errorText.value = '' }

const quickSuggestions = computed(() => {
  if (currentPage.value === 'course')
    return ['О чём этот курс?', 'Объясни основные понятия', 'Какие есть ещё курсы?']
  return ['Какие есть курсы?', 'Что ты умеешь?', 'С чего начать обучение?']
})
function sendSuggestion(text) { message.value = text; sendStream() }

function executeAction(evt) {
  if (evt.action !== 'navigate' || !evt.path) return
  const path = resolveNavigatePath(evt.path)
  if (!path) return
  const delay = voiceMode.value ? 500 : 300
  setTimeout(() => {
    if (voiceMode.value) stopVoiceMode()
    router.push(path)
  }, delay)
}

// ─── Computed ──────────────────────────────────────────────────────────────
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
      {{ isOpen ? '✕' : '💬' }}
    </button>

    <!-- Panels anchor (text chat) in bottom right -->
    <div class="panels-anchor" ref="panelsAnchorRef" :class="{'panels-open': isOpen}">
      <transition name="panel-fade">
        <div v-if="isOpen && !voiceMode" class="widget-panel">
          <div class="wp-header">
            <div class="wp-header-left">
              <span class="wp-icon">🤖</span>
              <div>
                <div class="wp-title">EduAI</div>
                <div class="wp-status">Online</div>
              </div>
            </div>
            <button class="icon-btn" @click="togglePanel">✕</button>
          </div>
          <!-- Messages -->
          <div class="wp-thread" ref="threadEl">
            <div class="msg-row bot-row">
              <div class="msg-bubble bot-bubble">
                <div class="msg-md">Привет! Я твой персональный ИИ-ассистент <b>{{ courseName }}</b>.<br>Чем могу помочь сегодня?</div>
              </div>
            </div>
            
            <div class="msg-row" v-for="(msg, i) in history" :key="i" :class="msg.role === 'user' ? 'user-row' : 'bot-row'">
              <div class="msg-bubble" :class="msg.role === 'user' ? 'user-bubble' : 'bot-bubble'">
                <div class="msg-md" v-html="renderMarkdown(msg.content)"></div>
                <div v-if="msg.sources && msg.sources.length" class="bubble-sources">
                  <span class="source-chip" v-for="(src, idx) in msg.sources" :key="idx" :title="src.title">
                    <span class="src-icon">📄</span>
                    <span class="src-name">{{ src.title || src.file_name }}</span>
                    <span class="src-page" v-if="src.page_number">стр. {{ src.page_number }}</span>
                  </span>
                </div>
                <button v-if="msg.role === 'assistant'" class="icon-btn" @click="speakText(msg.content)" title="Озвучить">🔊</button>
              </div>
            </div>

            <div class="msg-row bot-row" v-if="isLoading">
              <div class="msg-bubble bot-bubble">
                <div class="typing-indicator"><span></span><span></span><span></span></div>
              </div>
            </div>
            
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
            <input 
              v-model="message" 
              type="text" 
              placeholder="Спроси что-нибудь..." 
              @keydown.enter="handleSend()"
              :disabled="isLoading"
            />
            <button class="send-btn" @click="handleSend()" :disabled="isLoading || !message.trim()">➤</button>
          </div>
        </div>
      </transition>
    </div>

    <!-- ══════════════════════ DYNAMIC ISLAND SYSTEM -->
    <div class="island-system-container">
      <!-- Main Island -->
      <div
        class="dynamic-island"
        :class="{
          'island-voice': voiceMode,
          'island-listening': voiceMode && voiceState === 'LISTENING',
          'island-thinking': voiceMode && voiceState === 'THINKING',
          'island-speaking': voiceMode && voiceState === 'SPEAKING'
        }"
        @click="onIslandClick"
        :title="voiceMode ? 'Завершить' : 'Ассистент'"
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
        <span v-if="!voiceMode" class="island-label">EduAI</span>
      </div>

      <!-- Drop Bridge (Gooey Connection) -->
      <transition name="bridge-fade">
        <div class="drop-bridge" v-if="voiceMode && (voiceTranscript || voiceAssistantText)"></div>
      </transition>

      <!-- Transcript Sub-Island (Drop Down) -->
      <transition name="sub-island-slide">
        <div class="sub-island-transcript" v-if="voiceMode && (voiceTranscript || voiceAssistantText)">
          <div class="transcript-content" v-if="voiceState === 'LISTENING'">
            <span class="user-label">Вы:</span> {{ voiceTranscript || 'Слушаю...' }}
          </div>
          <div class="transcript-content bot" v-else-if="voiceAssistantText">
            <span class="bot-label">EduAI:</span> <span v-html="renderMarkdown(voiceAssistantText)"></span>
          </div>
          <div class="transcript-content" v-else>
            ...
          </div>
        </div>
      </transition>
    </div>

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
  background: var(--accent-hover, #3b82f6);
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
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 24px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 20px 40px rgba(0,0,0,0.3);
  height: 550px;
  max-height: calc(100vh - 120px);
}

.panel-fade-enter-active, .panel-fade-leave-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  transform-origin: bottom right;
}
.panel-fade-enter-from, .panel-fade-leave-to {
  opacity: 0;
  transform: scale(0.9) translateY(20px);
}

/* ─── Dynamic Island System ────────────────────────────── */
.island-system-container {
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%) translateZ(0); /* Hardware Accel */
  z-index: 9999;
  display: flex;
  flex-direction: column;
  align-items: center;
  pointer-events: none; /* Let clicks pass through container */
}

.dynamic-island {
  background: #000;
  color: #fff;
  border-radius: 99px;
  height: 44px;
  min-width: 120px;
  padding: 0 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  pointer-events: auto;
  box-shadow: 0 10px 30px rgba(0,0,0,0.3);
  transition: all 0.4s cubic-bezier(0.3, 1, 0.2, 1);
  will-change: width, height, transform, background;
  user-select: none;
  position: relative;
  z-index: 2; /* Main island is on top */
}

.island-voice {
  min-width: 200px;
  background: var(--accent);
}

.island-thinking {
  background: var(--accent2);
}

.island-speaking {
  background: #000;
}

.island-icon, .island-label, .island-status-text {
  font-family: 'Inter', sans-serif;
  font-weight: 600;
  font-size: 14px;
  white-space: nowrap;
}

/* Voice Waves */
.island-voice-wave {
  display: flex;
  align-items: center;
  gap: 3px;
  height: 20px;
}
.wave-bar {
  width: 3px;
  background: #fff;
  border-radius: 2px;
  transition: height 0.1s ease;
}
.island-voice-wave.speaking .wave-bar { animation: wavePulse 1s infinite alternate; }
.island-voice-wave.speaking .wave-bar:nth-child(1) { animation-delay: 0.1s; }
.island-voice-wave.speaking .wave-bar:nth-child(2) { animation-delay: 0.3s; }
.island-voice-wave.speaking .wave-bar:nth-child(3) { animation-delay: 0.0s; }
.island-voice-wave.speaking .wave-bar:nth-child(4) { animation-delay: 0.4s; }
.island-voice-wave.speaking .wave-bar:nth-child(5) { animation-delay: 0.2s; }

@keyframes wavePulse {
  0% { height: 4px; }
  100% { height: 20px; }
}

.island-voice-thinking { display: flex; align-items: center; gap: 4px; }
.island-voice-thinking .dot { width: 6px; height: 6px; background: #fff; border-radius: 50%; animation: dotPulse 1.4s infinite; }
.island-voice-thinking .dot:nth-child(2) { animation-delay: 0.2s; }
.island-voice-thinking .dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes dotPulse {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1.2); }
}

/* Sub-Island Transcript Drop */
.sub-island-transcript {
  background: #000;
  color: #fff;
  border-radius: 24px;
  padding: 12px 20px;
  margin-top: 12px; /* Gap below main island */
  min-width: 280px;
  max-width: 400px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.3);
  font-family: 'Inter', sans-serif;
  font-size: 14px;
  line-height: 1.5;
  pointer-events: auto;
  z-index: 1; /* Slides from behind the main island slightly, conceptually */
  border: 1px solid rgba(255,255,255,0.05);
  will-change: transform, opacity;
  position: relative;
}

/* The visual 'bridge' connecting the two islands */
.drop-bridge {
  position: absolute;
  top: 40px; /* Overlaps bottom of main island */
  width: 80px;
  height: 24px;
  background: #000;
  border-radius: 0 0 16px 16px;
  z-index: 1; /* Between main island and sub island */
  pointer-events: none;
}

.bridge-fade-enter-active, .bridge-fade-leave-active {
  transition: all 0.3s cubic-bezier(0.3, 1.5, 0.5, 1);
}
.bridge-fade-enter-from, .bridge-fade-leave-to {
  opacity: 0;
  transform: scaleY(0.5) scaleX(0.5) translateY(-10px);
}

.transcript-content {
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.user-label { color: #9ca3af; font-weight: 600; margin-right: 4px; }
.bot-label { color: var(--accent2); font-weight: 600; margin-right: 4px; }

/* Sub Island Slide Animation */
.sub-island-slide-enter-active, .sub-island-slide-leave-active {
  transition: all 0.4s cubic-bezier(0.3, 1.5, 0.5, 1);
}
.sub-island-slide-enter-from, .sub-island-slide-leave-to {
  opacity: 0;
  transform: translateY(-20px) scale(0.95);
}

/* ─── Chat Internal Styles ────────────────────────────────── */
.wp-header { padding: 16px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.02); }
.wp-header-left { display: flex; align-items: center; gap: 12px; }
.wp-icon { font-size: 24px; background: rgba(255,255,255,0.05); width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; border-radius: 12px; }
.wp-title { font-weight: 600; font-size: 15px; }
.wp-status { font-size: 12px; color: #10b981; display: flex; align-items: center; gap: 4px; }
.wp-status::before { content: ''; width: 6px; height: 6px; background: #10b981; border-radius: 50%; box-shadow: 0 0 8px rgba(16,185,129,0.5); }

.wp-thread { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 16px; scroll-behavior: smooth; }
.msg-row { display: flex; width: 100%; }
.user-row { justify-content: flex-end; }
.bot-row { justify-content: flex-start; }
.msg-bubble { max-width: 85%; padding: 12px 16px; border-radius: 18px; font-size: 14px; line-height: 1.5; position: relative; }
.user-bubble { background: var(--accent); color: white; border-bottom-right-radius: 4px; }
.bot-bubble { background: rgba(255,255,255,0.05); border: 1px solid var(--border); border-bottom-left-radius: 4px; }
.error-bubble { background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3); color: #fca5a5; }

.wp-input { padding: 12px 16px; border-top: 1px solid var(--border); display: flex; gap: 8px; align-items: center; background: rgba(0,0,0,0.2); }
.wp-input input { flex: 1; background: transparent; border: none; color: var(--text); font-size: 14px; outline: none; }
.icon-btn { background: none; border: none; cursor: pointer; color: var(--text); opacity: 0.7; transition: opacity 0.2s; display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 8px; }
.icon-btn:hover { opacity: 1; background: rgba(255,255,255,0.05); }
.send-btn { background: var(--accent); color: white; border: none; border-radius: 10px; width: 36px; height: 36px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 16px; transition: transform 0.1s; }
.send-btn:active { transform: scale(0.95); }
.send-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.bubble-sources { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.1); }
.source-chip { font-size: 11px; padding: 4px 8px; background: rgba(255,255,255,0.1); border-radius: 6px; display: flex; align-items: center; gap: 4px; cursor: default; }
.src-page { opacity: 0.7; font-size: 10px; }
</style>
