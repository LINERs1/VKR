<script setup>
import { ref, nextTick, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

// ─── Page & Course Context ─────────────────────────────────────────────────
const courseId = ref('default')
const courseName = ref('EduAI')
const courseIcon = ref('🤖')
const currentPage = ref('home')
const allCourses = ref([])

async function loadAllCourses() {
  try {
    const res = await fetch('/api/courses')
    if (res.ok) allCourses.value = await res.json()
  } catch (e) {}
}

const pageContext = computed(() => ({
  current_page: currentPage.value,
  current_course_id: courseId.value !== 'default' ? courseId.value : null,
  current_course_name: courseId.value !== 'default' ? courseName.value : null,
  available_courses: allCourses.value.map(c => ({
    id: c.id,
    title: c.title,
    icon: c.icon || '',
    description: c.description || ''
  }))
}))

watch(() => route.params.id, async (newId) => {
  if (newId) {
    currentPage.value = 'course'
    try {
      const res = await fetch(`/api/courses/${newId}`)
      if (res.ok) {
        const data = await res.json()
        courseId.value = data.id
        courseName.value = data.title
        courseIcon.value = data.icon
      }
    } catch(e) {}
  } else {
    currentPage.value = 'home'
    courseId.value = 'default'
    courseName.value = 'EduAI'
    courseIcon.value = '🤖'
  }
}, { immediate: true })

// ─── Text Chat State ─────────────────────────────────────────────────────────
const isOpen = ref(false)
const history = ref([])
const message = ref('')
const isBusy = ref(false)
const isSpeaking = ref(false)
const errorText = ref('')
const threadEl = ref(null)

const canSend = computed(() => message.value.trim().length > 0 && !isBusy.value)

function togglePanel() {
  if (voiceMode.value) {
    stopVoiceMode()
    return
  }
  isOpen.value = !isOpen.value
}

function closePanel() {
  isOpen.value = false
}

async function scrollBottom() {
  await nextTick()
  if (threadEl.value) threadEl.value.scrollTop = threadEl.value.scrollHeight
}

// ─── Voice Mode State ────────────────────────────────────────────────────────
const voiceMode = ref(false)
const voiceState = ref('IDLE') // IDLE | LISTENING | THINKING | SPEAKING
const voiceTranscript = ref('')
const voiceAssistantText = ref('')
const isHearingSpeech = ref(false)
const voiceError = ref('')

let audioQueue = []
let isAudioPlaying = false
let streamDone = false
let currentAudio = null

// ─── Speech Recognition ───────────────────────────────────────────────────
// Два режима: фоновый (wake word) и активный (диалог)
let recognition = null
let recognitionActive = false  // работает ли recognition прямо сейчас
let shouldRestart = false      // нужно ли перезапускать после onend
let voiceModeInternal = false  // синхронная копия voiceMode для onresult
let wakeWordTriggered = false  // debounce для wake word

const WAKE_WORDS = ['кортана', 'кортан', 'эдуай', 'edu ai', 'ассистент', 'помоги мне']

function initRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SpeechRecognition) {
    console.warn('[Voice] SpeechRecognition не поддерживается')
    return
  }

  recognition = new SpeechRecognition()
  recognition.lang = 'ru-RU'
  recognition.interimResults = true
  recognition.continuous = false  // continuous = false надёжнее; перезапускаем вручную
  recognition.maxAlternatives = 1

  recognition.onstart = () => {
    recognitionActive = true
    isHearingSpeech.value = false
  }

  recognition.onspeechstart = () => {
    isHearingSpeech.value = true
    // Barge-in: если ИИ говорит — прерываем и переходим к слушанию
    if (voiceModeInternal && voiceState.value === 'SPEAKING') {
      interruptSpeaking()
    }
  }

  recognition.onspeechend = () => {
    isHearingSpeech.value = false
  }

  recognition.onresult = (e) => {
    let finalText = ''
    let interimText = ''

    for (let i = e.resultIndex; i < e.results.length; i++) {
      const t = e.results[i][0].transcript
      if (e.results[i].isFinal) finalText += t
      else interimText += t
    }

    const currentText = (finalText || interimText).trim()

    if (!voiceModeInternal) {
      // Режим wake word — проверяем и interim, и final
      const lower = currentText.toLowerCase()
      const wakeWord = WAKE_WORDS.find(w => lower.includes(w))
      if (wakeWord) {
        // Debounce: не активируем дважды
        if (wakeWordTriggered) return
        wakeWordTriggered = true
        setTimeout(() => { wakeWordTriggered = false }, 3000)
        const afterWake = lower.split(wakeWord).slice(1).join(' ').trim()
        startVoiceMode(afterWake)
      }
    } else {
      // Активный диалог
      if (voiceState.value === 'LISTENING') {
        voiceTranscript.value = currentText
        if (finalText.trim()) {
          handleUserVoice(finalText.trim())
        }
      }
    }
  }

  recognition.onerror = (e) => {
    recognitionActive = false
    if (e.error === 'no-speech') {
      // Нормальный тайм-аут — перезапускаем если нужно
    } else if (e.error === 'aborted') {
      // Намеренно остановлено — не перезапускаем
      return
    } else {
      console.warn('[Voice] Ошибка:', e.error)
      if (voiceModeInternal) {
        voiceError.value = `Ошибка микрофона: ${e.error}`
      }
    }
  }

  recognition.onend = () => {
    recognitionActive = false
    isHearingSpeech.value = false
    if (shouldRestart) {
      setTimeout(() => startRecognitionIfNeeded(), 200)
    }
  }
}

function startRecognitionIfNeeded() {
  if (recognitionActive || !recognition) return
  // Не запускаем когда: чат открыт (без голосового режима) или ИИ думает/говорит
  if (isOpen.value && !voiceModeInternal) return
  if (voiceModeInternal && (voiceState.value === 'THINKING')) return

  try {
    shouldRestart = true
    recognition.start()
  } catch (e) {
    // уже запущен или другая ошибка
  }
}

function stopRecognition() {
  shouldRestart = false
  if (recognition && recognitionActive) {
    try { recognition.stop() } catch (e) {}
  }
}

function interruptSpeaking() {
  stopAudioQueue()
  voiceState.value = 'LISTENING'
  voiceAssistantText.value = ''
  // Перезапускаем распознавание для нового ввода
  stopRecognition()
  setTimeout(() => startRecognitionIfNeeded(), 100)
}

onMounted(() => {
  loadAllCourses()
  initRecognition()
  // Запускаем после первого взаимодействия (требование браузера)
  const startOnInteraction = () => {
    shouldRestart = true
    startRecognitionIfNeeded()
  }
  document.addEventListener('click', startOnInteraction, { once: true })
  document.addEventListener('keydown', startOnInteraction, { once: true })
})

onUnmounted(() => {
  stopRecognition()
  stopAudioQueue()
})

// ─── Voice Mode ──────────────────────────────────────────────────────────────
function startVoiceMode(initialPrompt = '') {
  isOpen.value = false
  voiceMode.value = true
  voiceModeInternal = true
  voiceError.value = ''
  voiceTranscript.value = ''
  voiceAssistantText.value = ''

  if (initialPrompt.trim()) {
    voiceTranscript.value = initialPrompt
    handleUserVoice(initialPrompt.trim())
  } else {
    voiceState.value = 'LISTENING'
    startRecognitionIfNeeded()
  }
}

function stopVoiceMode() {
  voiceMode.value = false
  voiceModeInternal = false
  voiceState.value = 'IDLE'
  voiceError.value = ''
  stopAudioQueue()
  stopRecognition()
  voiceTranscript.value = ''
  voiceAssistantText.value = ''
  // Возобновляем фоновый wake word
  shouldRestart = true
  setTimeout(() => startRecognitionIfNeeded(), 300)
}

async function handleUserVoice(text) {
  if (!text.trim()) {
    voiceState.value = 'LISTENING'
    return
  }

  // Останавливаем распознавание на время ответа ИИ
  stopRecognition()

  voiceState.value = 'THINKING'
  voiceTranscript.value = text
  voiceAssistantText.value = ''
  voiceError.value = ''

  history.value.push({ role: 'user', content: text, sources: [] })
  history.value.push({ role: 'assistant', content: '', sources: [] })
  const assistantIdx = history.value.length - 1

  const apiHistory = history.value.slice(0, -2).map(({ role, content }) => ({ role, content }))

  audioQueue = []
  isAudioPlaying = false
  streamDone = false

  try {
    const res = await fetch('/api/chat/voice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        history: apiHistory,
        course_id: courseId.value,
        course_name: courseName.value,
        page_context: pageContext.value
      }),
    })

    if (!res.ok) throw new Error(await res.text())

    const reader = res.body.getReader()
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
          if (evt.audio_b64) {
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

    streamDone = true
    if (!isAudioPlaying && audioQueue.length === 0 && voiceModeInternal) {
      resumeListening()
    }

  } catch (e) {
    console.error('[Voice] Ошибка запроса:', e)
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
    if (currentAudio) {
      try { URL.revokeObjectURL(currentAudio.src) } catch(e) {}
    }
    isAudioPlaying = false
    currentAudio = null
    if (!voiceModeInternal) return
    if (audioQueue.length > 0) {
      playNextAudio()
    } else if (streamDone) {
      resumeListening()
    }
  }

  try {
    const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0))
    const blob = new Blob([bytes], { type: 'audio/mpeg' })
    const url = URL.createObjectURL(blob)

    currentAudio = new Audio(url)
    currentAudio.onended = onAudioDone
    currentAudio.onerror = onAudioDone

    // Safety timeout: если onended не сработает, продолжаем через duration+3s
    currentAudio.onloadedmetadata = () => {
      const dur = currentAudio?.duration || 10
      safetyTimer = setTimeout(onAudioDone, (dur + 3) * 1000)
    }
    // Fallback если metadata не загрузится
    safetyTimer = setTimeout(onAudioDone, 15000)

    await currentAudio.play()
  } catch(e) {
    console.error('[Audio] Ошибка воспроизведения:', e)
    clearTimeout(safetyTimer)
    isAudioPlaying = false
    currentAudio = null
    if (audioQueue.length > 0) playNextAudio()
    else if (streamDone) resumeListening()
  }
}

function stopAudioQueue() {
  audioQueue = []
  streamDone = true
  if (currentAudio) {
    currentAudio.pause()
    currentAudio = null
  }
  isAudioPlaying = false
}

function resumeListening() {
  if (!voiceModeInternal) return
  voiceState.value = 'LISTENING'
  voiceTranscript.value = ''
  voiceAssistantText.value = ''
  // Небольшая задержка чтобы не поймать эхо
  setTimeout(() => {
    if (voiceModeInternal && voiceState.value === 'LISTENING') {
      startRecognitionIfNeeded()
    }
  }, 500)
}

// ─── Text Chat SSE ────────────────────────────────────────────────────────────
async function sendStream() {
  if (!canSend.value) return
  const userText = message.value.trim()
  message.value = ''
  errorText.value = ''

  history.value.push({ role: 'user', content: userText, sources: [] })
  history.value.push({ role: 'assistant', content: '', sources: [] })
  const assistantIdx = history.value.length - 1

  isBusy.value = true
  await scrollBottom()

  const apiHistory = history.value.slice(0, -2).map(({ role, content }) => ({ role, content }))

  try {
    const res = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: userText,
        history: apiHistory,
        course_id: courseId.value,
        course_name: courseName.value,
        page_context: pageContext.value
      }),
    })
    if (!res.ok || !res.body) throw new Error(await res.text())

    const reader = res.body.getReader()
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

function clearHistory() { history.value = []; errorText.value = '' }

// ─── Quick suggestions ────────────────────────────────────────────────────────
const quickSuggestions = computed(() => {
  if (currentPage.value === 'course') {
    return ['О чём этот курс?', 'Объясни основные понятия', 'Какие есть ещё курсы?']
  }
  return ['Какие есть курсы?', 'Что ты умеешь?', 'С чего начать обучение?']
})

function sendSuggestion(text) {
  message.value = text
  sendStream()
}

// ─── Navigation ───────────────────────────────────────────────────────────────
function executeAction(evt) {
  if (evt.action === 'navigate' && evt.path) {
    const delay = voiceModeInternal ? 2000 : 1000
    setTimeout(() => {
      if (voiceModeInternal) stopVoiceMode()
      router.push(evt.path)
    }, delay)
  }
}

// Статусный текст для голосового режима
const voiceStatusText = computed(() => {
  switch (voiceState.value) {
    case 'LISTENING': return isHearingSpeech.value ? 'Слышу вас...' : 'Говорите...'
    case 'THINKING': return 'Думаю...'
    case 'SPEAKING': return 'Отвечаю...'
    default: return 'Ожидание...'
  }
})
</script>

<template>
  <div class="widget-wrap">

    <!-- Voice Mode Panel -->
    <Transition name="fade-up">
      <div v-if="voiceMode" class="voice-panel glass">
        <!-- Header -->
        <div class="vp-header">
          <div class="vp-title">
            <span class="vp-icon">{{ courseIcon }}</span>
            <div>
              <div class="vp-name">EduAI</div>
              <div class="vp-course">{{ courseName }}</div>
            </div>
          </div>
          <button class="vp-close-btn" @click="stopVoiceMode" title="Завершить">✕</button>
        </div>

        <!-- Orb -->
        <div class="vp-orb-wrap">
          <div class="vp-orb" :class="voiceState.toLowerCase()">
            <div class="vp-orb-ring"></div>
            <div class="vp-orb-inner">
              <span class="vp-orb-emoji">
                <span v-if="voiceState === 'LISTENING'">🎙️</span>
                <span v-else-if="voiceState === 'THINKING'">✨</span>
                <span v-else-if="voiceState === 'SPEAKING'">🔊</span>
                <span v-else>💬</span>
              </span>
            </div>
          </div>
          <div class="vp-status">{{ voiceStatusText }}</div>
        </div>

        <!-- Transcript area -->
        <div class="vp-transcript">
          <div v-if="voiceError" class="vp-error">{{ voiceError }}</div>
          <div v-if="voiceTranscript && voiceState !== 'LISTENING'" class="vp-user-text">
            {{ voiceTranscript }}
          </div>
          <div v-if="voiceAssistantText" class="vp-ai-text">
            {{ voiceAssistantText }}
          </div>
          <div v-if="voiceState === 'LISTENING' && !voiceTranscript" class="vp-hint">
            Говорите — я слушаю
          </div>
        </div>

        <!-- Controls -->
        <div class="vp-controls">
          <button class="vp-btn-end" @click="stopVoiceMode">
            <span class="vp-btn-icon">📵</span>
            Завершить разговор
          </button>
        </div>
      </div>
    </Transition>

    <!-- Text Chat Panel -->
    <Transition name="widget-slide">
      <div v-if="isOpen && !voiceMode" class="widget-panel glass">
        <div class="wp-header">
          <div class="wp-avatar">{{ courseIcon }}</div>
          <div class="wp-info">
            <div class="wp-name">EduAI</div>
            <div class="wp-course">{{ courseName }}</div>
          </div>
          <div class="wp-actions">
            <button class="wp-icon-btn" title="Голосовой режим" @click="startVoiceMode('')">🎙️</button>
            <button v-if="history.length" class="wp-icon-btn" title="Очистить" @click="clearHistory">🗑</button>
            <button class="wp-icon-btn" @click="closePanel">✕</button>
          </div>
        </div>

        <div class="wp-thread" ref="threadEl">
          <div v-if="history.length === 0" class="wp-welcome">
            <div class="wp-welcome-icon">{{ currentPage === 'course' ? courseIcon : '🤖' }}</div>
            <p v-if="currentPage === 'course'">
              Привет! Я ваш ИИ-ассистент по курсу <strong>{{ courseName }}</strong>.
            </p>
            <p v-else>
              Привет! Я ассистент <strong>EduAI</strong>. Помогу выбрать курс!
            </p>
            <p class="wp-wake-hint">🎙️ Скажите «Кортана» для голосового режима</p>
            <div class="wp-suggestions">
              <button
                v-for="s in quickSuggestions"
                :key="s"
                class="wp-chip"
                :disabled="isBusy"
                @click="sendSuggestion(s)"
              >{{ s }}</button>
            </div>
          </div>

          <div v-for="(msg, i) in history" :key="i" class="wp-msg-row" :class="msg.role">
            <div class="wp-bubble" :class="msg.role">
              <div class="wp-role">{{ msg.role === 'user' ? 'Вы' : 'EduAI' }}</div>
              <div class="wp-text">{{ msg.content || '…' }}</div>
              <template v-if="msg.role === 'assistant' && msg.content">
                <div v-if="msg.sources?.length" class="wp-sources">
                  <span class="src-label">📄 Источники:</span>
                  <span v-for="s in msg.sources" :key="s" class="src-pill">{{ s }}</span>
                </div>
              </template>
            </div>
          </div>

          <div v-if="isBusy" class="wp-typing">
            <span></span><span></span><span></span>
          </div>
        </div>

        <div v-if="errorText" class="wp-error">{{ errorText }}</div>

        <div class="wp-input-row">
          <div class="wp-input-container">
            <input
              class="wp-input"
              v-model="message"
              :disabled="isBusy"
              placeholder="Задайте вопрос…"
              @keydown.enter.prevent="sendStream"
            />
          </div>
          <button class="wp-send-btn" :disabled="!canSend" @click="sendStream">
            <span v-if="!isBusy">↑</span>
            <span v-else class="wp-spinner"></span>
          </button>
        </div>
      </div>
    </Transition>

    <!-- FAB Button -->
    <button
      class="widget-fab"
      :class="{
        'fab-open': isOpen && !voiceMode,
        'fab-voice': voiceMode,
        'fab-listening': voiceMode && voiceState === 'LISTENING',
        'fab-thinking': voiceMode && voiceState === 'THINKING',
        'fab-speaking': voiceMode && voiceState === 'SPEAKING',
        'fab-hearing': isHearingSpeech && !voiceMode && !isOpen,
      }"
      @click="togglePanel"
      :title="voiceMode ? 'Завершить голосовой режим' : (isOpen ? 'Закрыть' : 'Открыть EduAI')"
    >
      <span class="fab-pulse" v-if="!isOpen && !voiceMode"></span>
      <span class="fab-pulse fab-pulse--hear" v-if="isHearingSpeech && !voiceMode && !isOpen"></span>
      <span class="fab-pulse fab-pulse--listen" v-if="voiceMode && voiceState === 'LISTENING'"></span>
      <span class="fab-pulse fab-pulse--speak" v-if="voiceMode && voiceState === 'SPEAKING'"></span>

      <span class="fab-icon">
        <template v-if="voiceMode">
          <span v-if="voiceState === 'LISTENING'">🎙️</span>
          <span v-else-if="voiceState === 'THINKING'">⏳</span>
          <span v-else-if="voiceState === 'SPEAKING'">🔊</span>
          <span v-else>🎙️</span>
        </template>
        <span v-else-if="isOpen">✕</span>
        <span v-else>🤖</span>
      </span>

      <span v-if="!isOpen && !voiceMode" class="fab-label">EduAI</span>
      <span v-if="voiceMode" class="fab-label fab-label--voice">Завершить</span>
    </button>
  </div>
</template>

<style scoped>
.widget-wrap {
  position: fixed;
  bottom: 32px;
  right: 32px;
  z-index: 9999;
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
}

/* ─── Premium Glassmorphism Utility ─── */
.glass {
  background: rgba(23, 23, 35, 0.7);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 24px 50px -12px rgba(0, 0, 0, 0.5);
}

/* ─── Voice Panel ─────────────────────────────── */
.voice-panel {
  position: absolute;
  bottom: 84px;
  right: 0;
  width: 400px;
  max-width: calc(100vw - 64px);
  border-radius: 32px;
  padding: 32px;
  display: flex;
  flex-direction: column;
  gap: 28px;
  z-index: 9000;
}

.vp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.vp-title {
  display: flex;
  align-items: center;
  gap: 16px;
}

.vp-icon {
  font-size: 32px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(16, 185, 129, 0.1));
  width: 56px;
  height: 56px;
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.vp-name { font-weight: 800; font-size: 18px; letter-spacing: -0.02em; color: #fff; }
.vp-course { font-size: 13px; color: #a1a1aa; margin-top: 2px; }

.vp-close-btn {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #71717a;
  width: 36px; height: 36px;
  border-radius: 12px;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.vp-close-btn:hover { background: rgba(239, 68, 68, 0.1); color: #ef4444; border-color: rgba(239, 68, 68, 0.2); transform: rotate(90deg); }

/* ─── Organic Orb ─────────────────────────────── */
.vp-orb-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  padding: 10px 0;
}

.vp-orb {
  width: 140px;
  height: 140px;
  border-radius: 50%;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.vp-orb::before {
  content: '';
  position: absolute;
  inset: -8px;
  border-radius: 50%;
  background: conic-gradient(from 0deg, #6366f1, #a855f7, #ec4899, #6366f1);
  opacity: 0.3;
  filter: blur(12px);
  animation: orb-spin 4s linear infinite;
}

.vp-orb.listening::before { opacity: 0.7; filter: blur(16px); animation-duration: 2s; }
.vp-orb.speaking::before { opacity: 0.9; filter: blur(20px); animation-duration: 1s; }
.vp-orb.thinking::before { opacity: 0.4; filter: blur(10px); animation-duration: 6s; }

@keyframes orb-spin { to { transform: rotate(360deg); } }

.vp-orb-ring {
  position: absolute;
  inset: 2px;
  border-radius: 50%;
  background: #0f172a;
  z-index: 1;
}

.vp-orb-inner {
  position: relative;
  z-index: 2;
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background: radial-gradient(circle at 30% 30%, rgba(99, 102, 241, 0.4), transparent 70%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: inset 0 0 20px rgba(99, 102, 241, 0.2);
}

.vp-orb.listening .vp-orb-inner {
  animation: orb-glow-blue 2s infinite alternate ease-in-out;
}
.vp-orb.speaking .vp-orb-inner {
  animation: orb-glow-green 0.8s infinite alternate ease-in-out;
}

@keyframes orb-glow-blue { from { box-shadow: inset 0 0 20px rgba(99, 102, 241, 0.3), 0 0 30px rgba(99, 102, 241, 0.2); } to { box-shadow: inset 0 0 40px rgba(99, 102, 241, 0.6), 0 0 50px rgba(99, 102, 241, 0.4); transform: scale(1.05); } }
@keyframes orb-glow-green { from { box-shadow: inset 0 0 20px rgba(16, 185, 129, 0.3), 0 0 30px rgba(16, 185, 129, 0.2); } to { box-shadow: inset 0 0 40px rgba(16, 185, 129, 0.6), 0 0 50px rgba(16, 185, 129, 0.4); transform: scale(1.1); } }

.vp-orb-emoji { font-size: 36px; filter: drop-shadow(0 0 10px rgba(255,255,255,0.3)); }

.vp-status {
  font-size: 14px;
  font-weight: 700;
  color: #fff;
  text-transform: uppercase;
  letter-spacing: 0.15em;
  background: rgba(255,255,255,0.05);
  padding: 6px 16px;
  border-radius: 100px;
  border: 1px solid rgba(255,255,255,0.1);
}

/* ─── Transcript ──────────────────────────────── */
.vp-transcript {
  min-height: 120px;
  max-height: 200px;
  overflow-y: auto;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 24px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.vp-error { color: #f87171; font-size: 14px; text-align: center; font-weight: 500; }

.vp-user-text {
  font-size: 15px;
  color: #a1a1aa;
  font-style: italic;
  text-align: right;
  padding-left: 20px;
}

.vp-ai-text {
  font-size: 17px;
  color: #fff;
  line-height: 1.6;
  font-weight: 400;
}

.vp-hint {
  font-size: 15px;
  color: #52525b;
  text-align: center;
  margin: auto;
}

/* ─── Controls ────────────────────────────────── */
.vp-controls { display: flex; justify-content: center; }

.vp-btn-end {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 32px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.2);
  color: #ef4444;
  border-radius: 100px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s ease;
}
.vp-btn-end:hover { background: #ef4444; color: #fff; transform: translateY(-2px); box-shadow: 0 8px 20px rgba(239, 68, 68, 0.3); }

/* ─── Text Chat Panel ─────────────────────────── */
.widget-panel {
  position: absolute;
  bottom: 84px;
  right: 0;
  width: 420px;
  max-width: calc(100vw - 64px);
  height: 640px;
  max-height: calc(100vh - 140px);
  border-radius: 32px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  z-index: 9000;
}

.wp-header {
  display: flex;
  align-items: center;
  padding: 24px 28px;
  background: rgba(255, 255, 255, 0.02);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.wp-avatar { font-size: 28px; margin-right: 16px; background: rgba(255, 255, 255, 0.05); width: 50px; height: 50px; display: flex; align-items: center; justify-content: center; border-radius: 18px; border: 1px solid rgba(255,255,255,0.1); }
.wp-info { flex: 1; }
.wp-name { font-weight: 800; font-size: 18px; color: #fff; letter-spacing: -0.01em; }
.wp-course { font-size: 13px; color: #6366f1; font-weight: 600; margin-top: 2px; }

.wp-icon-btn { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); color: #a1a1aa; cursor: pointer; font-size: 18px; width: 36px; height: 36px; border-radius: 12px; display: flex; align-items: center; justify-content: center; transition: all 0.2s; }
.wp-icon-btn:hover { background: rgba(255, 255, 255, 0.1); color: #fff; transform: translateY(-1px); }

.wp-thread { 
  flex: 1; 
  overflow-y: auto; 
  padding: 28px; 
  display: flex; 
  flex-direction: column; 
  gap: 20px; 
  scrollbar-width: none;
}
.wp-thread::-webkit-scrollbar { display: none; }

.wp-welcome { text-align: center; margin: 40px 0; }
.wp-welcome-icon { font-size: 48px; margin-bottom: 16px; animation: bounce 2s infinite; }
@keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }

.wp-welcome p { font-size: 16px; color: #fff; font-weight: 500; line-height: 1.5; }
.wp-wake-hint { font-size: 13px; color: #71717a !important; margin: 8px 0 24px !important; }

.wp-msg-row { display: flex; width: 100%; animation: slideIn 0.4s cubic-bezier(0, 1, 0, 1); }
@keyframes slideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

.wp-msg-row.user { justify-content: flex-end; }
.wp-bubble { 
  max-width: 85%; 
  padding: 16px 20px; 
  border-radius: 24px; 
  font-size: 15px; 
  line-height: 1.6; 
  position: relative;
}

.wp-bubble.user { 
  background: linear-gradient(135deg, #6366f1, #4f46e5); 
  color: #fff; 
  border-bottom-right-radius: 4px;
  box-shadow: 0 10px 20px -5px rgba(99, 102, 241, 0.4);
}

.wp-bubble.assistant { 
  background: rgba(255, 255, 255, 0.05); 
  color: #fff; 
  border: 1px solid rgba(255, 255, 255, 0.1); 
  border-bottom-left-radius: 4px; 
}

.wp-role { font-size: 10px; font-weight: 900; margin-bottom: 6px; opacity: 0.5; text-transform: uppercase; letter-spacing: 0.1em; }
.wp-text { white-space: pre-wrap; word-break: break-word; }

.wp-sources { margin-top: 12px; padding-top: 12px; border-top: 1px solid rgba(255, 255, 255, 0.05); display: flex; flex-wrap: wrap; gap: 8px; }
.src-pill { font-size: 11px; font-weight: 600; padding: 4px 10px; background: rgba(99, 102, 241, 0.1); border: 1px solid rgba(99, 102, 241, 0.2); border-radius: 8px; color: #818cf8; }

.wp-typing { display: flex; gap: 6px; padding: 12px 20px; background: rgba(255,255,255,0.03); border-radius: 20px; border-bottom-left-radius: 4px; width: fit-content; }
.wp-typing span { width: 8px; height: 8px; background: #6366f1; border-radius: 50%; animation: typing 1.4s infinite; }
.wp-typing span:nth-child(2) { animation-delay: 0.2s; }
.wp-typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing { 0%, 100% { opacity: 0.3; transform: scale(0.8); } 50% { opacity: 1; transform: scale(1.2); } }

.wp-input-row { 
  display: flex; 
  align-items: center; 
  padding: 20px 28px 32px; 
  gap: 16px; 
  background: linear-gradient(to top, rgba(0,0,0,0.4), transparent);
}

.wp-input-container {
  flex: 1;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  padding: 12px 20px;
  display: flex;
  align-items: center;
  transition: all 0.3s;
}
.wp-input-container:focus-within { border-color: rgba(99, 102, 241, 0.5); background: rgba(255, 255, 255, 0.08); box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.1); }

.wp-input { flex: 1; background: transparent; border: none; color: #fff; font-size: 15px; outline: none; }
.wp-input::placeholder { color: #52525b; }

.wp-send-btn { 
  width: 48px; 
  height: 48px; 
  border-radius: 16px; 
  border: none; 
  display: flex; 
  align-items: center; 
  justify-content: center; 
  cursor: pointer; 
  transition: all 0.3s; 
  background: #6366f1; 
  color: #fff; 
  font-size: 20px; 
  box-shadow: 0 8px 16px rgba(99, 102, 241, 0.3);
}
.wp-send-btn:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 12px 24px rgba(99, 102, 241, 0.4); background: #4f46e5; }
.wp-send-btn:disabled { background: rgba(255,255,255,0.05); color: #3f3f46; box-shadow: none; cursor: not-allowed; }

.wp-suggestions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 12px; justify-content: center; }
.wp-chip { 
  background: rgba(255, 255, 255, 0.03); 
  border: 1px solid rgba(255, 255, 255, 0.08); 
  color: #a1a1aa; 
  padding: 8px 18px; 
  border-radius: 100px; 
  font-size: 14px; 
  font-weight: 500;
  cursor: pointer; 
  transition: all 0.2s; 
}
.wp-chip:hover:not(:disabled) { background: rgba(99, 102, 241, 0.1); border-color: rgba(99, 102, 241, 0.3); color: #fff; transform: translateY(-2px); }

/* ─── FAB Button ──────────────────────────────── */
.widget-fab {
  width: 72px;
  height: 72px;
  border-radius: 24px;
  background: #6366f1;
  color: #fff;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  cursor: pointer;
  box-shadow: 0 12px 32px rgba(99, 102, 241, 0.4);
  transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  position: relative;
}
.widget-fab:hover { transform: scale(1.1) rotate(5deg); }

.widget-fab.fab-open { background: #18181b; border: 1px solid rgba(255,255,255,0.1); transform: rotate(0); }

.widget-fab.fab-hearing { background: #f43f5e; box-shadow: 0 0 40px rgba(244, 63, 94, 0.6); }
.widget-fab.fab-listening { background: #3b82f6; box-shadow: 0 0 32px rgba(59, 130, 246, 0.6); }
.widget-fab.fab-thinking { background: #f59e0b; }
.widget-fab.fab-speaking { background: #10b981; box-shadow: 0 0 40px rgba(16, 185, 129, 0.6); }

.fab-pulse {
  position: absolute;
  inset: -8px;
  border-radius: 30px;
  background: inherit;
  opacity: 0.4;
  z-index: -1;
  animation: fab-pulse 2s infinite;
}
@keyframes fab-pulse { 0% { transform: scale(1); opacity: 0.4; } 100% { transform: scale(1.6); opacity: 0; } }

.fab-label {
  position: absolute;
  right: 88px;
  background: #18181b;
  color: #fff;
  padding: 8px 16px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 700;
  border: 1px solid rgba(255,255,255,0.1);
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  pointer-events: none;
  opacity: 0;
  transform: translateX(10px);
  transition: all 0.3s;
}
.widget-fab:hover .fab-label { opacity: 1; transform: translateX(0); }

/* ─── Transitions ─────────────────────────────── */
.widget-slide-enter-active, .widget-slide-leave-active,
.fade-up-enter-active, .fade-up-leave-active {
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
.widget-slide-enter-from, .widget-slide-leave-to,
.fade-up-enter-from, .fade-up-leave-to {
  opacity: 0;
  transform: translateY(40px) scale(0.9);
  filter: blur(10px);
}
</style>
