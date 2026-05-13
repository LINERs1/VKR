<script setup>
import { ref, nextTick, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

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

const pageContext = computed(() => ({
  current_page: currentPage.value,
  current_course_id:   courseId.value !== 'default' ? courseId.value : null,
  current_course_name: courseId.value !== 'default' ? courseName.value : null,
  available_courses: allCourses.value.map(c => ({
    id: c.id, title: c.title, icon: c.icon || '', description: c.description || ''
  }))
}))

watch(() => route.params.id, async (newId) => {
  if (newId) {
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
  } else {
    currentPage.value = 'home'
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

// ─── Voice Mode State ──────────────────────────────────────────────────────
const voiceMode          = ref(false)
const voiceState         = ref('IDLE')
const voiceTranscript    = ref('')
const voiceAssistantText = ref('')
const isHearingSpeech    = ref(false)
const voiceError         = ref('')        // UX #4
const micVolume          = ref(0)         // UX #1: 0–100
const lastAssistantText  = ref('')        // UX #5

// Siri-режим
const waitingForSpeech = ref(false)
let waitingTimer = null
const WAITING_TIMEOUT_MS = 12000

let audioQueue     = []
let isAudioPlaying = false
let streamDone     = false
let currentAudio   = null

// UX #1: AudioContext для визуализации громкости микрофона
let audioCtx    = null
let analyser    = null
let micStream   = null
let volumeRafId = null

function startVolumeAnalyser() {
  if (audioCtx) return
  navigator.mediaDevices.getUserMedia({ audio: true, video: false })
    .then(stream => {
      micStream = stream
      audioCtx  = new (window.AudioContext || window.webkitAudioContext)()
      analyser  = audioCtx.createAnalyser()
      analyser.fftSize = 256
      audioCtx.createMediaStreamSource(stream).connect(analyser)
      const data = new Uint8Array(analyser.frequencyBinCount)
      function tick() {
        analyser.getByteFrequencyData(data)
        const avg = data.reduce((s, v) => s + v, 0) / data.length
        micVolume.value = Math.min(100, Math.round((avg / 128) * 200))
        volumeRafId = requestAnimationFrame(tick)
      }
      tick()
    })
    .catch(err => {
      // UX #4: понятные сообщения вместо тихого провала
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        voiceError.value = 'Нет доступа к микрофону. Разрешите доступ в настройках браузера и обновите страницу.'
      } else if (err.name === 'NotFoundError') {
        voiceError.value = 'Микрофон не найден. Подключите микрофон и попробуйте снова.'
      } else {
        voiceError.value = `Ошибка микрофона: ${err.message}`
      }
    })
}

function stopVolumeAnalyser() {
  if (volumeRafId) { cancelAnimationFrame(volumeRafId); volumeRafId = null }
  if (micStream)   { micStream.getTracks().forEach(t => t.stop()); micStream = null }
  if (audioCtx)    { audioCtx.close(); audioCtx = null }
  analyser = null
  micVolume.value = 0
}

// ─── Speech Recognition ────────────────────────────────────────────────────
let recognition       = null
let recognitionActive = false
let shouldRestart     = false
let voiceModeInternal = false
let wakeWordTriggered = false

const WAKE_WORDS = ['кортана', 'кортан', 'эдуай', 'edu ai', 'ассистент', 'помоги мне']

function initRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SR) { return }

  recognition = new SR()
  recognition.lang            = 'ru-RU'
  recognition.interimResults  = true
  recognition.continuous      = false
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

  recognition.onspeechend = () => { isHearingSpeech.value = false }

  recognition.onresult = (e) => {
    let finalText = '', interimText = ''
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const t = e.results[i][0].transcript
      if (e.results[i].isFinal) finalText += t
      else interimText += t
    }
    const currentText = (finalText || interimText).trim()

    if (!voiceModeInternal) {
      const lower = currentText.toLowerCase()
      const wakeWord = WAKE_WORDS.find(w => lower.includes(w))
      if (wakeWord) {
        if (wakeWordTriggered) return
        wakeWordTriggered = true
        setTimeout(() => { wakeWordTriggered = false }, 3000)
        const afterWake = lower.split(wakeWord).slice(1).join(' ').trim()
        startVoiceMode(afterWake)
      }
    } else {
      if (voiceState.value === 'LISTENING') {
        voiceTranscript.value = currentText
        if (finalText.trim()) {
          clearWaitingMode()
          handleUserVoice(finalText.trim())
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
    if (shouldRestart) setTimeout(() => startRecognitionIfNeeded(), 200)
  }
}

function startRecognitionIfNeeded() {
  if (recognitionActive || !recognition) return
  if (isOpen.value && !voiceModeInternal) return
  // UX #8: не запускаем пока ИИ говорит — не поймаем собственный голос
  if (voiceModeInternal && (voiceState.value === 'THINKING' || voiceState.value === 'SPEAKING')) return
  try { shouldRestart = true; recognition.start() } catch (e) {}
}

function stopRecognition() {
  shouldRestart = false
  if (recognition && recognitionActive) try { recognition.stop() } catch (e) {}
}

function interruptSpeaking() {
  stopAudioQueue()
  voiceState.value = 'LISTENING'
  voiceAssistantText.value = ''
  stopRecognition()
  setTimeout(() => startRecognitionIfNeeded(), 100)
}

onMounted(() => {
  loadAllCourses()
  initRecognition()
  const startOnInteraction = () => { shouldRestart = true; startRecognitionIfNeeded() }
  document.addEventListener('click',   startOnInteraction, { once: true })
  document.addEventListener('keydown', startOnInteraction, { once: true })
})

onUnmounted(() => {
  clearWaitingMode()
  stopRecognition()
  stopAudioQueue()
  stopVolumeAnalyser()
})

// ─── Siri waiting mode ─────────────────────────────────────────────────────
function enterWaitingMode() {
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

// ─── Voice Mode ────────────────────────────────────────────────────────────
function startVoiceMode(initialPrompt = '') {
  isOpen.value = false
  voiceMode.value      = true
  voiceModeInternal    = true
  voiceError.value     = ''
  voiceTranscript.value    = ''
  voiceAssistantText.value = ''
  lastAssistantText.value  = ''

  startVolumeAnalyser()  // UX #1

  if (initialPrompt.trim()) {
    clearWaitingMode()
    voiceTranscript.value = initialPrompt
    handleUserVoice(initialPrompt.trim())
  } else {
    enterWaitingMode()
  }
}

function stopVoiceMode() {
  clearWaitingMode()
  voiceMode.value      = false
  voiceModeInternal    = false
  voiceState.value     = 'IDLE'
  voiceError.value     = ''
  stopAudioQueue()
  stopRecognition()
  stopVolumeAnalyser()

  // UX #3: открываем текстовый чат с историей после голосового режима
  if (history.value.length > 0) {
    nextTick(() => { isOpen.value = true })
  }

  voiceTranscript.value    = ''
  voiceAssistantText.value = ''
  shouldRestart = true
  setTimeout(() => startRecognitionIfNeeded(), 300)
}

// UX #2: остановить TTS и вернуться к слушанию
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
  if (!text.trim()) { voiceState.value = 'LISTENING'; return }

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
    const res = await fetch('/api/chat/voice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text, history: apiHistory,
        course_id: courseId.value, course_name: courseName.value,
        page_context: pageContext.value
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
      const dur = currentAudio?.duration || 10
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
  // UX #8: задержка — даём тихо затихнуть аудио перед включением микрофона
  setTimeout(() => {
    if (voiceModeInternal && voiceState.value === 'LISTENING') startRecognitionIfNeeded()
  }, 700)
}

// ─── Text Chat SSE ─────────────────────────────────────────────────────────
async function sendStream() {
  if (!canSend.value) return
  const userText  = message.value.trim()
  message.value   = ''
  errorText.value = ''

  history.value.push({ role: 'user',      content: userText, sources: [] })
  history.value.push({ role: 'assistant', content: '',        sources: [] })
  const assistantIdx = history.value.length - 1

  isBusy.value = true
  await scrollBottom()

  const apiHistory = history.value.slice(0, -2).map(({ role, content }) => ({ role, content }))

  try {
    const res = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: userText, history: apiHistory,
        course_id: courseId.value, course_name: courseName.value,
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

const quickSuggestions = computed(() => {
  if (currentPage.value === 'course')
    return ['О чём этот курс?', 'Объясни основные понятия', 'Какие есть ещё курсы?']
  return ['Какие есть курсы?', 'Что ты умеешь?', 'С чего начать обучение?']
})
function sendSuggestion(text) { message.value = text; sendStream() }

function executeAction(evt) {
  if (evt.action === 'navigate' && evt.path) {
    const delay = voiceModeInternal ? 2000 : 1000
    setTimeout(() => {
      if (voiceModeInternal) stopVoiceMode()
      router.push(evt.path)
    }, delay)
  }
}

// ─── Computed ──────────────────────────────────────────────────────────────
const voiceStatusText = computed(() => {
  if (voiceState.value === 'LISTENING') {
    if (waitingForSpeech.value) return 'Слушаю вас...'
    if (isHearingSpeech.value)  return 'Слышу вас...'
    return 'Говорите...'
  }
  if (voiceState.value === 'THINKING') return 'Думаю...'
  if (voiceState.value === 'SPEAKING') return 'Отвечаю...'
  return 'Ожидание...'
})

// UX #1: масштаб орба от громкости микрофона
const orbScale = computed(() => {
  if (voiceState.value !== 'LISTENING') return 1
  return 1 + (micVolume.value / 100) * 0.15
})
</script>

<template>
  <div class="widget-wrap">

    <!-- ══════════════════════ VOICE PANEL -->
    <Transition name="fade-up">
      <div v-if="voiceMode" class="voice-panel glass">

        <div class="vp-header">
          <div class="vp-title">
            <span class="vp-icon">{{ courseIcon }}</span>
            <div>
              <div class="vp-name">EduAI</div>
              <div class="vp-course">{{ courseName }}</div>
            </div>
          </div>
          <!-- UX #7: кнопка включения/выключения TTS -->
          <button
            class="vp-tts-toggle"
            :class="{ active: ttsEnabled }"
            :title="ttsEnabled ? 'Выключить озвучку' : 'Включить озвучку'"
            @click="ttsEnabled = !ttsEnabled"
          >{{ ttsEnabled ? '🔊' : '🔇' }}</button>
          <button class="vp-close-btn" @click="stopVoiceMode" title="Завершить">✕</button>
        </div>

        <div class="vp-orb-wrap">
          <div
            class="vp-orb"
            :class="[voiceState.toLowerCase(), { 'orb-waiting': waitingForSpeech }]"
            :style="{ transform: `scale(${orbScale})` }"
          >
            <div class="vp-orb-ring"></div>

            <!-- UX #1: кольцо реагирует на громкость микрофона -->
            <div
              v-if="voiceState === 'LISTENING' && micVolume > 8"
              class="vp-volume-ring"
              :style="{
                opacity: micVolume / 120,
                transform: `scale(${1 + micVolume / 180})`
              }"
            ></div>

            <div class="vp-orb-inner">
              <span class="vp-orb-emoji">
                <span v-if="voiceState === 'LISTENING'">🎙️</span>
                <span v-else-if="voiceState === 'THINKING'">✨</span>
                <span v-else-if="voiceState === 'SPEAKING'">🔊</span>
                <span v-else>💬</span>
              </span>
            </div>

            <!-- Countdown ring -->
            <svg v-if="waitingForSpeech" class="vp-countdown-ring" viewBox="0 0 140 140">
              <circle cx="70" cy="70" r="65" fill="none"
                stroke="rgba(99,102,241,0.15)" stroke-width="3"/>
              <circle cx="70" cy="70" r="65" fill="none"
                class="vp-countdown-progress"
                stroke="rgba(99,102,241,0.6)" stroke-width="3" stroke-linecap="round"
                :style="{ animationDuration: WAITING_TIMEOUT_MS + 'ms' }"/>
            </svg>
          </div>

          <div class="vp-status">{{ voiceStatusText }}</div>
          <div v-if="waitingForSpeech" class="vp-waiting-hint">Жду вашего вопроса...</div>
        </div>

        <div class="vp-transcript">
          <!-- UX #4: чёткие сообщения об ошибке микрофона -->
          <div v-if="voiceError" class="vp-error">
            <span>⚠️</span>
            <span class="vp-error-text">{{ voiceError }}</span>
            <button class="vp-error-retry" @click="voiceError = ''; startVolumeAnalyser()">
              Попробовать снова
            </button>
          </div>
          <div v-if="voiceTranscript && voiceState !== 'LISTENING'" class="vp-user-text">
            {{ voiceTranscript }}
          </div>
          <div v-if="voiceAssistantText" class="vp-ai-text">{{ voiceAssistantText }}</div>
          <div v-if="voiceState === 'LISTENING' && !voiceTranscript && !voiceError" class="vp-hint">
            <span v-if="waitingForSpeech">Говорите в любой момент — я слушаю</span>
            <span v-else>Говорите — я слушаю</span>
          </div>
        </div>

        <div class="vp-controls">
          <!-- UX #2: стоп во время ответа -->
          <button
            v-if="voiceState === 'SPEAKING'"
            class="vp-btn vp-btn--stop"
            @click="stopSpeakingAndListen"
          >⏹ Стоп</button>

          <!-- UX #5: повторить последний ответ -->
          <button
            v-if="lastAssistantText && voiceState === 'LISTENING' && ttsEnabled"
            class="vp-btn vp-btn--repeat"
            @click="repeatLastAnswer"
          >🔁 Повторить</button>

          <button class="vp-btn vp-btn--end" @click="stopVoiceMode">
            📵 Завершить
          </button>
        </div>
      </div>
    </Transition>

    <!-- ══════════════════════ TEXT CHAT PANEL -->
    <Transition name="widget-slide">
      <div v-if="isOpen && !voiceMode" class="widget-panel glass">

        <div class="wp-header">
          <div class="wp-avatar">{{ courseIcon }}</div>
          <div class="wp-info">
            <div class="wp-name">EduAI</div>
            <div class="wp-course">{{ courseName }}</div>
          </div>
          <div class="wp-actions">
            <!-- UX #7: TTS toggle в текстовом чате -->
            <button
              class="wp-icon-btn"
              :title="ttsEnabled ? 'Выключить озвучку' : 'Включить озвучку'"
              @click="ttsEnabled = !ttsEnabled"
            >{{ ttsEnabled ? '🔊' : '🔇' }}</button>
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
            <p v-else>Привет! Я ассистент <strong>EduAI</strong>. Помогу выбрать курс!</p>
            <p class="wp-wake-hint">🎙️ Скажите «Кортана» для голосового режима</p>
            <div class="wp-suggestions">
              <button
                v-for="s in quickSuggestions" :key="s"
                class="wp-chip" :disabled="isBusy"
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

        <div v-if="errorText" class="wp-error-bar">{{ errorText }}</div>

        <div class="wp-input-row">
          <div class="wp-input-container">
            <input
              class="wp-input" v-model="message" :disabled="isBusy"
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

    <!-- ══════════════════════ FAB -->
    <button
      class="widget-fab"
      :class="{
        'fab-open':      isOpen && !voiceMode,
        'fab-voice':     voiceMode,
        'fab-listening': voiceMode && voiceState === 'LISTENING',
        'fab-thinking':  voiceMode && voiceState === 'THINKING',
        'fab-speaking':  voiceMode && voiceState === 'SPEAKING',
        'fab-hearing':   isHearingSpeech && !voiceMode && !isOpen,
      }"
      @click="togglePanel"
      :title="voiceMode ? 'Завершить' : (isOpen ? 'Закрыть' : 'Открыть EduAI')"
    >
      <span class="fab-pulse" v-if="!isOpen && !voiceMode"></span>
      <span class="fab-pulse fab-pulse--hear"   v-if="isHearingSpeech && !voiceMode && !isOpen"></span>
      <span class="fab-pulse fab-pulse--listen" v-if="voiceMode && voiceState === 'LISTENING'"></span>
      <span class="fab-pulse fab-pulse--speak"  v-if="voiceMode && voiceState === 'SPEAKING'"></span>

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

.glass {
  background: rgba(23, 23, 35, 0.72);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid rgba(255,255,255,0.08);
  box-shadow: 0 24px 50px -12px rgba(0,0,0,0.5);
}

/* ─── Voice Panel ─────────────────────────────── */
.voice-panel {
  position: absolute;
  bottom: 84px;
  right: 0;
  width: min(400px, calc(100vw - 24px));   /* UX #6 */
  border-radius: 32px;
  padding: 28px;
  display: flex;
  flex-direction: column;
  gap: 22px;
  z-index: 9000;
}

.vp-header { display: flex; align-items: center; gap: 10px; }
.vp-title  { flex: 1; display: flex; align-items: center; gap: 14px; }
.vp-icon   {
  font-size: 26px;
  background: linear-gradient(135deg, rgba(99,102,241,0.2), rgba(16,185,129,0.1));
  width: 50px; height: 50px; border-radius: 18px;
  display: flex; align-items: center; justify-content: center;
  border: 1px solid rgba(255,255,255,0.1); flex-shrink: 0;
}
.vp-name   { font-weight: 800; font-size: 16px; color: #fff; }
.vp-course { font-size: 12px; color: #a1a1aa; margin-top: 2px; }

/* UX #7 */
.vp-tts-toggle {
  background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.1);
  color: #52525b; width: 36px; height: 36px; border-radius: 12px;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  font-size: 15px; transition: all 0.2s; flex-shrink: 0;
}
.vp-tts-toggle.active {
  color: #fff; border-color: rgba(99,102,241,0.4);
  background: rgba(99,102,241,0.15);
}

.vp-close-btn {
  background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1);
  color: #71717a; width: 36px; height: 36px; border-radius: 12px;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  transition: all 0.3s; flex-shrink: 0;
}
.vp-close-btn:hover {
  background: rgba(239,68,68,0.1); color: #ef4444;
  border-color: rgba(239,68,68,0.2); transform: rotate(90deg);
}

/* ─── Orb ─────────────────────────────────────── */
.vp-orb-wrap {
  display: flex; flex-direction: column; align-items: center; gap: 14px; padding: 6px 0;
}

.vp-orb {
  width: 128px; height: 128px; border-radius: 50%; position: relative;
  display: flex; align-items: center; justify-content: center;
  transition: transform 0.1s ease-out;  /* UX #1: плавно меняется от громкости */
}
.vp-orb::before {
  content: ''; position: absolute; inset: -8px; border-radius: 50%;
  background: conic-gradient(from 0deg, #6366f1, #a855f7, #ec4899, #6366f1);
  opacity: 0.3; filter: blur(12px); animation: orb-spin 4s linear infinite;
}
.vp-orb.listening::before { opacity: 0.7; filter: blur(16px); animation-duration: 2s; }
.vp-orb.speaking::before  { opacity: 0.9; filter: blur(20px); animation-duration: 1s; }
.vp-orb.thinking::before  { opacity: 0.4; filter: blur(10px); animation-duration: 6s; }
.vp-orb.orb-waiting::before { opacity: 0.5; filter: blur(14px); animation-duration: 3s; }
@keyframes orb-spin { to { transform: rotate(360deg); } }

.vp-orb-ring {
  position: absolute; inset: 2px; border-radius: 50%;
  background: #0f172a; z-index: 1;
}

/* UX #1: кольцо громкости */
.vp-volume-ring {
  position: absolute; inset: -4px; border-radius: 50%;
  border: 2px solid rgba(99,102,241,0.7);
  z-index: 2; pointer-events: none;
  transition: transform 0.08s ease-out, opacity 0.08s ease-out;
}

.vp-orb-inner {
  position: relative; z-index: 3;
  width: 92px; height: 92px; border-radius: 50%;
  background: radial-gradient(circle at 30% 30%, rgba(99,102,241,0.4), transparent 70%);
  display: flex; align-items: center; justify-content: center;
  box-shadow: inset 0 0 20px rgba(99,102,241,0.2);
}
.vp-orb.listening  .vp-orb-inner { animation: orb-glow-blue  2s infinite alternate ease-in-out; }
.vp-orb.speaking   .vp-orb-inner { animation: orb-glow-green 0.8s infinite alternate ease-in-out; }
.vp-orb.orb-waiting .vp-orb-inner { animation: orb-glow-wait 2.5s infinite alternate ease-in-out; }
@keyframes orb-glow-blue  {
  from { box-shadow: inset 0 0 20px rgba(99,102,241,0.3), 0 0 30px rgba(99,102,241,0.2); }
  to   { box-shadow: inset 0 0 40px rgba(99,102,241,0.6), 0 0 50px rgba(99,102,241,0.4); }
}
@keyframes orb-glow-green {
  from { box-shadow: inset 0 0 20px rgba(16,185,129,0.3), 0 0 30px rgba(16,185,129,0.2); }
  to   { box-shadow: inset 0 0 40px rgba(16,185,129,0.6), 0 0 50px rgba(16,185,129,0.4); transform: scale(1.08); }
}
@keyframes orb-glow-wait  {
  from { box-shadow: inset 0 0 15px rgba(99,102,241,0.2); }
  to   { box-shadow: inset 0 0 30px rgba(99,102,241,0.45), 0 0 40px rgba(99,102,241,0.25); transform: scale(1.03); }
}
.vp-orb-emoji { font-size: 32px; filter: drop-shadow(0 0 10px rgba(255,255,255,0.3)); }

.vp-countdown-ring {
  position: absolute; inset: -6px;
  width: calc(100% + 12px); height: calc(100% + 12px);
  z-index: 4; pointer-events: none; transform: rotate(-90deg);
}
.vp-countdown-progress {
  stroke-dasharray: 408; stroke-dashoffset: 0;
  animation: countdown-shrink linear forwards;
}
@keyframes countdown-shrink { to { stroke-dashoffset: 408; } }

.vp-status {
  font-size: 12px; font-weight: 700; color: #fff;
  text-transform: uppercase; letter-spacing: 0.15em;
  background: rgba(255,255,255,0.05);
  padding: 5px 14px; border-radius: 100px;
  border: 1px solid rgba(255,255,255,0.1);
}
.vp-waiting-hint {
  font-size: 12px; color: #6366f1; font-weight: 500;
  animation: hint-fade 1.5s infinite alternate ease-in-out;
}
@keyframes hint-fade { from { opacity: 0.5; } to { opacity: 1; } }

/* ─── Transcript ──────────────────────────────── */
.vp-transcript {
  min-height: 80px; max-height: 170px; overflow-y: auto;
  background: rgba(0,0,0,0.28); border-radius: 20px; padding: 16px;
  display: flex; flex-direction: column; gap: 10px;
  border: 1px solid rgba(255,255,255,0.05);
}

/* UX #4: ошибка микрофона */
.vp-error {
  display: flex; align-items: flex-start; flex-wrap: wrap; gap: 6px;
  background: rgba(248,113,113,0.08); border: 1px solid rgba(248,113,113,0.2);
  border-radius: 12px; padding: 10px 12px;
}
.vp-error-text { color: #f87171; font-size: 13px; flex: 1; }
.vp-error-retry {
  background: none; border: 1px solid rgba(248,113,113,0.4);
  color: #f87171; border-radius: 8px; padding: 3px 10px;
  font-size: 12px; cursor: pointer; width: 100%; margin-top: 4px;
  transition: background 0.2s;
}
.vp-error-retry:hover { background: rgba(248,113,113,0.1); }

.vp-user-text { font-size: 14px; color: #a1a1aa; font-style: italic; text-align: right; }
.vp-ai-text   { font-size: 15px; color: #fff; line-height: 1.6; }
.vp-hint      { font-size: 14px; color: #52525b; text-align: center; margin: auto; }

/* ─── Controls ────────────────────────────────── */
.vp-controls { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; }

.vp-btn {
  display: flex; align-items: center; gap: 7px;
  padding: 10px 20px; border-radius: 100px;
  font-size: 13px; font-weight: 700; cursor: pointer;
  transition: all 0.25s; border: 1px solid transparent;
}
/* UX #2 */
.vp-btn--stop   { background: rgba(245,158,11,0.1); border-color: rgba(245,158,11,0.25); color: #f59e0b; }
.vp-btn--stop:hover { background: #f59e0b; color: #000; }
/* UX #5 */
.vp-btn--repeat { background: rgba(99,102,241,0.1); border-color: rgba(99,102,241,0.25); color: #818cf8; }
.vp-btn--repeat:hover { background: #6366f1; color: #fff; }

.vp-btn--end { background: rgba(239,68,68,0.1); border-color: rgba(239,68,68,0.2); color: #ef4444; }
.vp-btn--end:hover { background: #ef4444; color: #fff; transform: translateY(-2px); box-shadow: 0 8px 20px rgba(239,68,68,0.3); }

/* ─── Text Chat Panel ─────────────────────────── */
.widget-panel {
  position: absolute; bottom: 84px; right: 0;
  width: min(420px, calc(100vw - 24px));     /* UX #6 */
  height: min(640px, calc(100vh - 140px));   /* UX #6 */
  border-radius: 32px;
  display: flex; flex-direction: column;
  overflow: hidden; z-index: 9000;
}

.wp-header {
  display: flex; align-items: center; gap: 10px;
  padding: 20px 22px;
  background: rgba(255,255,255,0.02);
  border-bottom: 1px solid rgba(255,255,255,0.08);
}
.wp-avatar {
  font-size: 24px; background: rgba(255,255,255,0.05);
  width: 44px; height: 44px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  border-radius: 16px; border: 1px solid rgba(255,255,255,0.1);
}
.wp-info   { flex: 1; min-width: 0; }
.wp-name   { font-weight: 800; font-size: 16px; color: #fff; }
.wp-course { font-size: 12px; color: #6366f1; font-weight: 600; margin-top: 2px; }
.wp-actions { display: flex; gap: 6px; flex-shrink: 0; }

.wp-icon-btn {
  background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08);
  color: #a1a1aa; cursor: pointer; font-size: 15px;
  width: 33px; height: 33px; border-radius: 11px;
  display: flex; align-items: center; justify-content: center; transition: all 0.2s;
}
.wp-icon-btn:hover { background: rgba(255,255,255,0.1); color: #fff; transform: translateY(-1px); }

.wp-thread {
  flex: 1; overflow-y: auto; padding: 22px;
  display: flex; flex-direction: column; gap: 16px;
  scrollbar-width: none;
}
.wp-thread::-webkit-scrollbar { display: none; }

.wp-welcome { text-align: center; margin: 28px 0; }
.wp-welcome-icon { font-size: 42px; margin-bottom: 12px; animation: bounce 2s infinite; }
@keyframes bounce { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
.wp-welcome p  { font-size: 15px; color: #fff; font-weight: 500; line-height: 1.5; }
.wp-wake-hint  { font-size: 12px; color: #71717a !important; margin: 6px 0 18px !important; }

.wp-msg-row { display: flex; width: 100%; animation: slideIn 0.35s ease; }
@keyframes slideIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; } }
.wp-msg-row.user { justify-content: flex-end; }

.wp-bubble { max-width: 85%; padding: 13px 17px; border-radius: 20px; font-size: 14px; line-height: 1.6; }
.wp-bubble.user {
  background: linear-gradient(135deg, #6366f1, #4f46e5); color: #fff;
  border-bottom-right-radius: 4px;
  box-shadow: 0 6px 14px -3px rgba(99,102,241,0.4);
}
.wp-bubble.assistant {
  background: rgba(255,255,255,0.05); color: #fff;
  border: 1px solid rgba(255,255,255,0.1); border-bottom-left-radius: 4px;
}
.wp-role { font-size: 10px; font-weight: 900; margin-bottom: 5px; opacity: 0.5; text-transform: uppercase; letter-spacing: 0.1em; }
.wp-text { white-space: pre-wrap; word-break: break-word; }
.wp-sources { margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.05); display: flex; flex-wrap: wrap; gap: 6px; }
.src-pill { font-size: 11px; font-weight: 600; padding: 3px 9px; background: rgba(99,102,241,0.1); border: 1px solid rgba(99,102,241,0.2); border-radius: 7px; color: #818cf8; }

.wp-typing { display: flex; gap: 5px; padding: 10px 16px; background: rgba(255,255,255,0.03); border-radius: 17px; border-bottom-left-radius: 4px; width: fit-content; }
.wp-typing span { width: 7px; height: 7px; background: #6366f1; border-radius: 50%; animation: typing 1.4s infinite; }
.wp-typing span:nth-child(2) { animation-delay: 0.2s; }
.wp-typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing { 0%,100% { opacity: 0.3; transform: scale(0.8); } 50% { opacity: 1; transform: scale(1.2); } }

.wp-error-bar { color: #f87171; padding: 8px 22px; font-size: 13px; }

.wp-input-row {
  display: flex; align-items: center; padding: 14px 22px 26px; gap: 12px;
  background: linear-gradient(to top, rgba(0,0,0,0.4), transparent);
}
.wp-input-container {
  flex: 1; min-width: 0; background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.1); border-radius: 17px;
  padding: 11px 17px; transition: all 0.3s;
}
.wp-input-container:focus-within {
  border-color: rgba(99,102,241,0.5); background: rgba(255,255,255,0.08);
  box-shadow: 0 0 0 3px rgba(99,102,241,0.1);
}
.wp-input { width: 100%; background: transparent; border: none; color: #fff; font-size: 14px; outline: none; }
.wp-input::placeholder { color: #52525b; }

.wp-send-btn {
  width: 44px; height: 44px; flex-shrink: 0; border-radius: 14px; border: none;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; transition: all 0.3s; background: #6366f1; color: #fff; font-size: 18px;
  box-shadow: 0 6px 14px rgba(99,102,241,0.3);
}
.wp-send-btn:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 10px 20px rgba(99,102,241,0.4); background: #4f46e5; }
.wp-send-btn:disabled { background: rgba(255,255,255,0.05); color: #3f3f46; box-shadow: none; cursor: not-allowed; }
.wp-spinner { width: 15px; height: 15px; border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff; border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.wp-suggestions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; justify-content: center; }
.wp-chip {
  background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08);
  color: #a1a1aa; padding: 7px 15px; border-radius: 100px;
  font-size: 13px; font-weight: 500; cursor: pointer; transition: all 0.2s;
}
.wp-chip:hover:not(:disabled) { background: rgba(99,102,241,0.1); border-color: rgba(99,102,241,0.3); color: #fff; transform: translateY(-2px); }

/* ─── FAB ─────────────────────────────────────── */
.widget-fab {
  width: 66px; height: 66px; border-radius: 22px;
  background: #6366f1; color: #fff; border: none;
  display: flex; align-items: center; justify-content: center;
  font-size: 28px; cursor: pointer;
  box-shadow: 0 10px 28px rgba(99,102,241,0.4);
  transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  position: relative;
}
.widget-fab:hover { transform: scale(1.1) rotate(5deg); }
.widget-fab.fab-open      { background: #18181b; border: 1px solid rgba(255,255,255,0.1); }
.widget-fab.fab-hearing   { background: #f43f5e; box-shadow: 0 0 36px rgba(244,63,94,0.6); }
.widget-fab.fab-listening { background: #3b82f6; box-shadow: 0 0 28px rgba(59,130,246,0.6); }
.widget-fab.fab-thinking  { background: #f59e0b; }
.widget-fab.fab-speaking  { background: #10b981; box-shadow: 0 0 36px rgba(16,185,129,0.6); }

.fab-pulse {
  position: absolute; inset: -8px; border-radius: 28px;
  background: inherit; opacity: 0.4; z-index: -1;
  animation: fab-pulse 2s infinite;
}
@keyframes fab-pulse { 0% { transform: scale(1); opacity: 0.4; } 100% { transform: scale(1.6); opacity: 0; } }

.fab-label {
  position: absolute; right: 82px;
  background: #18181b; color: #fff;
  padding: 7px 13px; border-radius: 11px;
  font-size: 13px; font-weight: 700;
  border: 1px solid rgba(255,255,255,0.1);
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  pointer-events: none; white-space: nowrap;
  opacity: 0; transform: translateX(10px); transition: all 0.3s;
}
.widget-fab:hover .fab-label { opacity: 1; transform: translateX(0); }

/* ─── Transitions ─────────────────────────────── */
.widget-slide-enter-active, .widget-slide-leave-active,
.fade-up-enter-active,      .fade-up-leave-active {
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
.widget-slide-enter-from, .widget-slide-leave-to,
.fade-up-enter-from,      .fade-up-leave-to {
  opacity: 0; transform: translateY(40px) scale(0.9); filter: blur(10px);
}

/* ─── Mobile UX #6 ────────────────────────────── */
@media (max-width: 480px) {
  .widget-wrap  { bottom: 16px; right: 16px; }
  .voice-panel,
  .widget-panel { border-radius: 24px; }
  .vp-orb       { width: 108px; height: 108px; }
  .vp-orb-inner { width: 76px; height: 76px; }
  .vp-btn       { padding: 9px 15px; font-size: 12px; }
  .widget-fab   { width: 56px; height: 56px; font-size: 24px; border-radius: 18px; }
  .fab-label    { display: none; }
}
</style>
