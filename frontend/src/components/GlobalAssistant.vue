<script setup>
import { ref, nextTick, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

// ─── Page & Course Context ─────────────────────────────────────────────────
const courseId = ref('default')
const courseName = ref('EduAI')
const courseIcon = ref('🤖')
const currentPage = ref('home')  // 'home' | 'course'
const allCourses = ref([])  // список всех курсов платформы

// Загружаем список курсов один раз при монтировании
async function loadAllCourses() {
  try {
    const res = await fetch('/api/courses')
    if (res.ok) allCourses.value = await res.json()
  } catch (e) {}
}

// page_context — передаётся в каждый запрос к API
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
    // If voice mode is active, clicking FAB stops voice mode
    stopVoiceMode()
    return
  }
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    stopWakeWord()
  } else {
    startWakeWord()
  }
}

function closePanel() {
  isOpen.value = false
  startWakeWord()
}

function handleHistoryUpdate(newHistory) {
  history.value = [...newHistory]
  scrollBottom()
}

async function scrollBottom() {
  await nextTick()
  if (threadEl.value) threadEl.value.scrollTop = threadEl.value.scrollHeight
}

// ─── Voice Mode State ────────────────────────────────────────────────────────
const voiceMode = ref(false)
// voiceState: 'IDLE', 'LISTENING', 'THINKING', 'SPEAKING'
const voiceState = ref('IDLE')
const voiceTranscript = ref('')
const voiceAssistantText = ref('')
const isHearingSpeech = ref(false)

let audioQueue = []
let isAudioPlaying = false
let streamDone = false
let currentAudio = null
let wakeWordStopped = false

// ─── Wake Word & Continuous Recognition ──────────────────────────────────────
const wakeWordRecognition = ref(null)

function initWakeWord() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SpeechRecognition) {
    console.error('[WakeWord] SpeechRecognition not supported')
    return
  }
  
  const rec = new SpeechRecognition()
  rec.lang = 'ru-RU'
  rec.interimResults = true
  rec.continuous = true
  rec.maxAlternatives = 1
  
  rec.onstart = () => {
    console.log('[WakeWord] ✅ Started listening')
    if (voiceMode.value && voiceState.value === 'IDLE') {
      voiceState.value = 'LISTENING'
    }
  }
  
  rec.onspeechstart = () => {
    isHearingSpeech.value = true
    if (voiceMode.value && (voiceState.value === 'LISTENING' || voiceState.value === 'IDLE')) {
      // Barge-in: if speaking, interrupt and go to listening
      if (voiceState.value === 'SPEAKING') {
         stopAudioQueue()
         voiceState.value = 'LISTENING'
      }
    }
  }
  
  rec.onspeechend = () => {
    isHearingSpeech.value = false
  }
  
  rec.onerror = (e) => {
    console.warn('[WakeWord] Error:', e.error)
  }
  
  rec.onend = () => {
    isHearingSpeech.value = false
    if (!wakeWordStopped && !isOpen.value) {
      // restart recognition unless manually stopped or text chat is open
      setTimeout(() => {
        try { rec.start() } catch (err) {}
      }, 300)
    }
  }
  
  rec.onresult = (e) => {
    let finalTranscript = ''
    let interimTranscript = ''
    
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const text = e.results[i][0].transcript.toLowerCase()
      if (e.results[i].isFinal) {
        finalTranscript += text + ' '
      } else {
        interimTranscript += text + ' '
      }
    }
    
    const currentText = (finalTranscript || interimTranscript).trim()

    if (!voiceMode.value) {
      // --- WAKE WORD MODE ---
      if (currentText.includes('кортан') || currentText.includes('картон') || currentText.includes('картан') || currentText.includes('помог')) {
        console.log('[WakeWord] 🚀 DETECTED')
        const match = currentText.match(/(кортан[а-я]*|картон[а-я]*|картан[а-я]*|помог[а-я]*)[,!.?\s]*(.*)/)
        let prompt = ''
        if (match && match[2]) prompt = match[2].trim()
        
        startVoiceMode(prompt)
      }
    } else {
      // --- ACTIVE CONVERSATION MODE ---
      if (voiceState.value === 'LISTENING' || voiceState.value === 'IDLE') {
         voiceTranscript.value = currentText
         if (finalTranscript.trim()) {
            handleUserVoice(finalTranscript.trim())
         }
      }
    }
  }
  
  wakeWordRecognition.value = rec
}

function startWakeWord() {
  if (!wakeWordRecognition.value) return
  wakeWordStopped = false
  try { wakeWordRecognition.value.start() } catch (e) {}
}

function stopWakeWord() {
  wakeWordStopped = true
  if (wakeWordRecognition.value) {
    try { wakeWordRecognition.value.stop() } catch(e) {}
  }
}

onMounted(() => {
  loadAllCourses()
  initWakeWord()
  const startOnInteraction = () => {
    startWakeWord()
  }
  document.addEventListener('click', startOnInteraction, { once: true })
  document.addEventListener('keydown', startOnInteraction, { once: true })
})

onUnmounted(() => {
  stopWakeWord()
  stopAudioQueue()
})

// ─── Voice Conversation Logic ────────────────────────────────────────────────
function startVoiceMode(initialPrompt = '') {
  isOpen.value = false // close text chat if open
  voiceMode.value = true
  voiceTranscript.value = initialPrompt || 'Слушаю вас...'
  voiceAssistantText.value = ''
  
  if (initialPrompt.trim()) {
    handleUserVoice(initialPrompt.trim())
  } else {
    voiceState.value = 'LISTENING'
  }
}

function stopVoiceMode() {
  voiceMode.value = false
  voiceState.value = 'IDLE'
  stopAudioQueue()
  voiceTranscript.value = ''
  voiceAssistantText.value = ''
  
  // Restart background wake word listener
  startWakeWord()
}

async function handleUserVoice(text) {
  if (!text.trim()) return
  
  // Stop recognition temporarily while thinking to avoid hearing its own speech or echoing
  stopWakeWord()
  
  voiceState.value = 'THINKING'
  voiceTranscript.value = text
  voiceAssistantText.value = ''
  
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
      if (!voiceMode.value) break // abort if user closed voice mode

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
        
                const evt = JSON.parse(jsonText)
                if (evt.type === 'token') {
                   history.value[assistantIdx].content += String(evt.content ?? '')
                   voiceAssistantText.value += String(evt.content ?? '')
                } else if (evt.type === 'sentence') {
                   if (evt.audio_b64) {
                       audioQueue.push(evt.audio_b64)
                       playNextAudio()
                   }
                } else if (evt.type === 'action') {
                   // Выполняем действие от ИИ (например, навигация)
                   executeAction(evt)
                } else if (evt.type === 'sources') {
                   history.value[assistantIdx].sources = Array.isArray(evt.content) ? evt.content : []
                }
      }
    }
    
    streamDone = true
    if (!isAudioPlaying && audioQueue.length === 0 && voiceMode.value) {
        resumeListening()
    }

  } catch (e) {
    console.error(e)
    if (voiceMode.value) resumeListening()
  }
}

async function playNextAudio() {
  if (isAudioPlaying || audioQueue.length === 0 || !voiceMode.value) return
  
  isAudioPlaying = true
  voiceState.value = 'SPEAKING'
  
  const b64 = audioQueue.shift()
  try {
      const byteCharacters = atob(b64)
      const byteNumbers = new Array(byteCharacters.length)
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i)
      }
      const byteArray = new Uint8Array(byteNumbers)
      const blob = new Blob([byteArray], {type: 'audio/mpeg'})
      const url = URL.createObjectURL(blob)
      
      currentAudio = new Audio(url)
      
      currentAudio.onended = () => {
          URL.revokeObjectURL(url)
          isAudioPlaying = false
          
          if (!voiceMode.value) return
          if (audioQueue.length > 0) {
              playNextAudio()
          } else if (streamDone) {
              resumeListening()
          }
      }
      
      currentAudio.onerror = () => {
          isAudioPlaying = false
          if (audioQueue.length > 0) playNextAudio()
          else if (streamDone) resumeListening()
      }

      await currentAudio.play()
  } catch(e) {
      console.error('Audio play error', e)
      isAudioPlaying = false
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
  if (!voiceMode.value) return
  voiceState.value = 'LISTENING'
  voiceTranscript.value = ''
  voiceAssistantText.value = ''
  startWakeWord()
}


// ─── Text Chat SSE streaming ───────────────────────────────────────────────
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
          const evt = JSON.parse(jsonText)
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

// ─── Quick-reply suggestions ──────────────────────────────────────────────
const quickSuggestions = computed(() => {
  if (currentPage.value === 'home') {
    return [
      'Какие есть курсы?',
      'Что ты умеешь?',
      'С чего начать обучение?',
    ]
  }
  return [
    'О чём этот курс?',
    'Что я узнаю на курсе?',
    'Какие ещё есть курсы?',
  ]
})

function sendSuggestion(text) {
  message.value = text
  sendStream()
}

// ─── Actions & Navigation ──────────────────────────────────────────────────
function executeAction(evt) {
  if (evt.action === 'navigate') {
    console.log('[Action] Navigating to:', evt.path)
    // Небольшая задержка, чтобы пользователь успел осознать ответ
    setTimeout(() => {
      router.push(evt.path)
    }, 1500)
  }
}

</script>

<template>
  <div class="widget-wrap">
    
    <!-- Voice Mode Tooltip (shows recognized text or AI response) -->
    <Transition name="fade-up">
      <div v-if="voiceMode && (voiceTranscript || voiceAssistantText)" class="voice-tooltip">
        <div v-if="voiceTranscript" class="vt-user">{{ voiceTranscript }}</div>
        <div v-if="voiceAssistantText" class="vt-ai">{{ voiceAssistantText }}</div>
      </div>
    </Transition>

    <!-- Text Chat Panel -->
    <Transition name="widget-slide">
      <div v-if="isOpen && !voiceMode" class="widget-panel">
        <div class="wp-header">
          <div class="wp-avatar">{{ courseIcon }}</div>
          <div class="wp-info">
            <div class="wp-name">EduAI</div>
            <div class="wp-course">{{ courseName }}</div>
          </div>
          <div class="wp-actions">
            <button class="wp-icon-btn" title="Включить голосовой режим" @click="startVoiceMode('')">🎙️</button>
            <button v-if="history.length" class="wp-icon-btn" title="Очистить" @click="clearHistory">🗑</button>
            <button class="wp-icon-btn" @click="closePanel">✕</button>
          </div>
        </div>

        <div class="wp-thread" ref="threadEl">
          <div v-if="history.length === 0" class="wp-welcome">
            <div class="wp-welcome-icon">{{ currentPage === 'course' ? courseIcon : '🤖' }}</div>
            <p v-if="currentPage === 'course'">
              Привет! Я ваш ИИ-ассистент по курсу <strong>{{ courseName }}</strong>.
              Задайте вопрос голосом или текстом!
            </p>
            <p v-else>
              Привет! Я ассистент <strong>EduAI</strong>.
              Помогу выбрать курс или отвечу на вопросы о платформе!
            </p>
            <p class="wp-wake-hint">🎤 Скажите «Кортана, помоги» для голосового режима</p>
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
          <input
            class="wp-input"
            v-model="message"
            :disabled="isBusy"
            placeholder="Задайте вопрос…"
            @keydown.enter.prevent="sendStream"
          />
          <button class="wp-send-btn" :disabled="!canSend" @click="sendStream">
            <span v-if="!isBusy">↑</span>
            <span v-else class="wp-spinner"></span>
          </button>
        </div>
      </div>
    </Transition>

    <!-- Trigger button (FAB) -->
    <button 
      class="widget-fab" 
      :class="{ 
        open: isOpen && !voiceMode,
        'voice-mode': voiceMode,
        'vm-listening': voiceMode && voiceState === 'LISTENING',
        'vm-thinking': voiceMode && voiceState === 'THINKING',
        'vm-speaking': voiceMode && voiceState === 'SPEAKING',
        'hearing': isHearingSpeech && !isOpen
      }" 
      @click="togglePanel" 
      :title="voiceMode ? 'Завершить голосовой режим' : 'Открыть чат'"
    >
      <!-- Base pulse for wake word listening (idle) -->
      <span class="fab-pulse" v-if="!isOpen && !voiceMode && !isHearingSpeech"></span>
      <!-- Wake word hearing pulse -->
      <span class="fab-pulse hearing-pulse" v-if="!isOpen && !voiceMode && isHearingSpeech"></span>
      
      <!-- Voice Mode Pulses -->
      <span class="fab-pulse vm-pulse-listen" v-if="voiceMode && voiceState === 'LISTENING'"></span>
      <span class="fab-pulse vm-pulse-think" v-if="voiceMode && voiceState === 'THINKING'"></span>
      <span class="fab-pulse vm-pulse-speak" v-if="voiceMode && voiceState === 'SPEAKING'"></span>

      <span class="fab-icon">
        <template v-if="voiceMode">
          <span v-if="voiceState === 'LISTENING'">🎙️</span>
          <span v-else-if="voiceState === 'THINKING'">⏳</span>
          <span v-else-if="voiceState === 'SPEAKING'">🔊</span>
        </template>
        <template v-else>
          {{ isOpen ? '✕' : '🤖' }}
        </template>
      </span>
      
      <span v-if="!isOpen && !voiceMode" class="fab-label">EduAI</span>
      <span v-if="voiceMode" class="fab-label">Завершить звонок</span>
    </button>
  </div>
</template>

<style scoped>
.widget-wrap {
  position: fixed;
  bottom: 20px;
  right: 20px;
  z-index: 9999;
}

/* ─── Voice Mode Tooltip ───────────────────────────── */
.voice-tooltip {
  position: absolute;
  bottom: 80px;
  right: 0;
  width: 320px;
  max-width: calc(100vw - 40px);
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 16px;
  box-shadow: 0 10px 40px -10px rgba(0,0,0,0.5);
  display: flex;
  flex-direction: column;
  gap: 12px;
  backdrop-filter: blur(10px);
  z-index: 9000;
}

.vt-user {
  background: rgba(255,255,255,0.05);
  padding: 10px 14px;
  border-radius: 14px;
  border-bottom-right-radius: 4px;
  font-size: 14px;
  color: var(--muted);
  align-self: flex-end;
  max-width: 90%;
  font-style: italic;
}

.vt-ai {
  background: var(--accent);
  color: white;
  padding: 12px 16px;
  border-radius: 14px;
  border-bottom-left-radius: 4px;
  font-size: 15px;
  line-height: 1.5;
  align-self: flex-start;
  max-width: 95%;
  box-shadow: 0 4px 15px rgba(124, 92, 255, 0.3);
}

.fade-up-enter-active, .fade-up-leave-active {
  transition: all 0.3s ease;
}
.fade-up-enter-from, .fade-up-leave-to {
  opacity: 0;
  transform: translateY(10px) scale(0.95);
}

/* ─── Widget Panel (Text Chat) ───────────────────────────── */
.widget-panel {
  position: absolute;
  bottom: 80px;
  right: 0;
  width: 380px;
  max-width: calc(100vw - 40px);
  height: 600px;
  max-height: calc(100vh - 120px);
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 20px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 10px 40px -10px rgba(0,0,0,0.5);
  overflow: hidden;
  z-index: 9000;
  backdrop-filter: blur(10px);
}

.widget-slide-enter-active, .widget-slide-leave-active {
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
  transform-origin: bottom right;
}
.widget-slide-enter-from, .widget-slide-leave-to {
  opacity: 0;
  transform: scale(0.9) translateY(20px);
}

.wp-header {
  display: flex;
  align-items: center;
  padding: 16px 20px;
  background: rgba(255, 255, 255, 0.03);
  border-bottom: 1px solid var(--border);
}
.wp-avatar {
  font-size: 28px; margin-right: 12px;
  background: rgba(255, 255, 255, 0.05); width: 44px; height: 44px;
  display: flex; align-items: center; justify-content: center; border-radius: 50%;
}
.wp-info { flex: 1; }
.wp-name { font-weight: 600; font-size: 16px; color: var(--text); }
.wp-course { font-size: 12px; color: var(--accent2); margin-top: 2px; }
.wp-actions { display: flex; gap: 8px; }
.wp-icon-btn { background: none; border: none; color: var(--muted); cursor: pointer; font-size: 18px; padding: 4px; border-radius: 6px; transition: all 0.2s; }
.wp-icon-btn:hover { background: rgba(255, 255, 255, 0.1); color: var(--text); }

.wp-thread { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 16px; scrollbar-width: thin; scrollbar-color: rgba(255,255,255,0.1) transparent; }
.wp-welcome { text-align: center; color: var(--muted); font-size: 14px; margin: 20px 0; }
.wp-welcome-icon { font-size: 40px; margin-bottom: 10px; }
.wp-msg-row { display: flex; width: 100%; }
.wp-msg-row.user { justify-content: flex-end; }
.wp-msg-row.assistant { justify-content: flex-start; }
.wp-bubble { max-width: 85%; padding: 12px 16px; border-radius: 16px; font-size: 14px; line-height: 1.5; }
.wp-bubble.user { background: var(--accent); color: white; border-bottom-right-radius: 4px; }
.wp-bubble.assistant { background: rgba(255, 255, 255, 0.05); color: var(--text); border: 1px solid var(--border); border-bottom-left-radius: 4px; }
.wp-role { font-size: 11px; font-weight: 600; margin-bottom: 4px; opacity: 0.7; text-transform: uppercase; }
.wp-msg-row.user .wp-role { text-align: right; }
.wp-text { white-space: pre-wrap; word-break: break-word; }
.wp-sources { margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.1); display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.src-label { font-size: 12px; color: var(--muted); }
.src-pill { font-size: 11px; padding: 2px 8px; background: rgba(255,255,255,0.1); border-radius: 10px; color: var(--text); }

.wp-typing { display: flex; gap: 4px; padding: 12px 16px; background: rgba(255, 255, 255, 0.05); border-radius: 16px; border-bottom-left-radius: 4px; width: fit-content; }
.wp-typing span { width: 6px; height: 6px; background: var(--muted); border-radius: 50%; animation: typing 1s infinite alternate; }
.wp-typing span:nth-child(2) { animation-delay: 0.2s; }
.wp-typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing { from { opacity: 0.3; transform: translateY(0); } to { opacity: 1; transform: translateY(-4px); } }

.wp-error { color: var(--danger); padding: 10px 20px; font-size: 13px; background: rgba(251, 113, 133, 0.1); border-top: 1px solid rgba(251, 113, 133, 0.2); }

.wp-input-row { display: flex; align-items: center; padding: 16px 20px; gap: 10px; background: rgba(0, 0, 0, 0.2); border-top: 1px solid var(--border); }
.wp-input { flex: 1; background: transparent; border: none; color: var(--text); font-size: 14px; outline: none; font-family: inherit; }
.wp-input::placeholder { color: var(--muted); }
.wp-send-btn { width: 36px; height: 36px; border-radius: 50%; border: none; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s; background: var(--accent); color: white; font-size: 18px; }
.wp-send-btn:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 4px 10px rgba(124, 92, 255, 0.4); }
.wp-send-btn:disabled { background: rgba(255, 255, 255, 0.1); color: var(--muted); cursor: not-allowed; }
.wp-spinner { width: 16px; height: 16px; border: 2px solid transparent; border-top-color: white; border-radius: 50%; animation: wp-spin 0.8s linear infinite; }
@keyframes wp-spin { to { transform: rotate(360deg); } }

/* ─── FAB Button ──────────────── */
.widget-fab {
  width: 60px;
  height: 60px;
  border-radius: 30px;
  background: var(--accent);
  color: white;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  cursor: pointer;
  box-shadow: 0 10px 25px rgba(124, 92, 255, 0.5);
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
  position: relative;
}

.widget-fab:hover {
  transform: translateY(-4px) scale(1.05);
  box-shadow: 0 14px 30px rgba(124, 92, 255, 0.6);
}

.widget-fab.open {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid var(--border);
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
  transform: rotate(90deg);
}

.widget-fab.hearing {
  transform: scale(1.1);
  box-shadow: 0 0 30px rgba(251, 113, 133, 0.8);
  background: #fb7185;
}

/* Voice Mode Colors */
.widget-fab.voice-mode.vm-listening {
  background: #3b82f6; /* Blue for listening */
  box-shadow: 0 0 25px rgba(59, 130, 246, 0.6);
}
.widget-fab.voice-mode.vm-thinking {
  background: #f59e0b; /* Yellow for thinking */
  box-shadow: 0 0 25px rgba(245, 158, 11, 0.6);
}
.widget-fab.voice-mode.vm-speaking {
  background: #10b981; /* Green for speaking */
  box-shadow: 0 0 35px rgba(16, 185, 129, 0.8);
}

.fab-icon {
  position: relative;
  z-index: 2;
  transition: transform 0.3s;
}

.widget-fab.open .fab-icon {
  transform: rotate(-90deg);
  font-size: 24px;
}

/* Pulses */
.fab-pulse {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  border-radius: 50%;
  background: var(--accent);
  z-index: 1;
  animation: fab-pulse 2s infinite;
}
.fab-pulse.hearing-pulse { background: #fb7185; animation: hearing-pulse 0.8s infinite alternate; }
.fab-pulse.vm-pulse-listen { background: #3b82f6; animation: vm-pulse-listen 1.5s infinite; }
.fab-pulse.vm-pulse-think { background: #f59e0b; animation: vm-pulse-think 1s infinite alternate; }
.fab-pulse.vm-pulse-speak { background: #10b981; animation: vm-pulse-speak 1s infinite cubic-bezier(0.4, 0, 0.2, 1); }

@keyframes hearing-pulse { 0% { transform: scale(1); opacity: 0.8; } 100% { transform: scale(1.4); opacity: 0.2; } }
@keyframes vm-pulse-listen { 0% { transform: scale(1); opacity: 0.6; } 100% { transform: scale(1.8); opacity: 0; } }
@keyframes vm-pulse-think { 0% { transform: scale(1) rotate(0deg); opacity: 0.8; } 100% { transform: scale(1.2) rotate(180deg); opacity: 0.2; } }
@keyframes vm-pulse-speak { 0% { transform: scale(1); opacity: 0.8; } 50% { transform: scale(1.5); opacity: 0.4; } 100% { transform: scale(1); opacity: 0.8; } }

@keyframes fab-pulse { 0% { transform: scale(1); opacity: 0.6; } 100% { transform: scale(1.6); opacity: 0; } }

.fab-label {
  position: absolute;
  right: 75px;
  background: var(--card);
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  border: 1px solid var(--border);
  opacity: 0;
  visibility: hidden;
  transition: all 0.2s;
  white-space: nowrap;
}

.widget-fab:hover .fab-label {
  opacity: 1;
  visibility: visible;
  right: 80px;
}

/* ─── Quick Suggestions ──────────────────────── */
.wp-wake-hint {
  font-size: 12px;
  color: var(--muted);
  margin: 4px 0 12px;
  opacity: 0.7;
}

.wp-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
  justify-content: center;
}

.wp-chip {
  background: rgba(124, 92, 255, 0.1);
  border: 1px solid rgba(124, 92, 255, 0.3);
  color: var(--accent);
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  font-family: inherit;
}

.wp-chip:hover:not(:disabled) {
  background: rgba(124, 92, 255, 0.25);
  border-color: var(--accent);
  transform: translateY(-1px);
}

.wp-chip:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
