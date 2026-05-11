<script setup>
import { ref, nextTick, computed } from 'vue'
import VoiceCall from './VoiceCall.vue'

const props = defineProps({
  courseId:   { type: String, required: true },
  courseName: { type: String, required: true },
  courseIcon: { type: String, default: '🤖' },
})

const isOpen    = ref(false)
const isCallOpen = ref(false)
const history   = ref([])
const message   = ref('')
const isBusy    = ref(false)
const isSpeaking= ref(false)
const isListening = ref(false)
const errorText = ref('')
const threadEl  = ref(null)

const canSend = computed(() => message.value.trim().length > 0 && !isBusy.value)

function toggle() {
  isOpen.value = !isOpen.value
}

function openVoiceCall() {
  isOpen.value = false
  isCallOpen.value = true
}

function handleVoiceCallClose() {
  isCallOpen.value = false
  isOpen.value = true
}

function handleHistoryUpdate(newHistory) {
  history.value = [...newHistory]
  scrollBottom()
}

async function scrollBottom() {
  await nextTick()
  if (threadEl.value) threadEl.value.scrollTop = threadEl.value.scrollHeight
}

// ─── Voice input (Web Speech API) ─────────────────────────────────────────
let recognition = null

function startListening() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SpeechRecognition) {
    errorText.value = 'Голосовой ввод не поддерживается в этом браузере'
    return
  }
  if (isListening.value) {
    recognition?.stop()
    isListening.value = false
    return
  }
  recognition = new SpeechRecognition()
  recognition.lang = 'ru-RU'
  recognition.interimResults = true
  recognition.continuous = false

  recognition.onstart = () => { isListening.value = true; errorText.value = '' }
  recognition.onend   = () => { isListening.value = false }
  recognition.onerror = (e) => {
    isListening.value = false
    if (e.error !== 'no-speech') errorText.value = `Ошибка распознавания: ${e.error}`
  }
  recognition.onresult = (e) => {
    const transcript = Array.from(e.results)
      .map(r => r[0].transcript).join('')
    message.value = transcript
    if (e.results[e.results.length - 1].isFinal) {
      recognition.stop()
      sendStream()
    }
  }
  recognition.start()
}

// ─── SSE streaming ─────────────────────────────────────────────────────────
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

  const apiHistory = history.value
    .slice(0, -2)
    .map(({ role, content }) => ({ role, content }))

  try {
    const res = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: userText, history: apiHistory, course_id: props.courseId, course_name: props.courseName }),
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
        } else if (evt.type === 'error') {
          errorText.value = String(evt.content ?? 'Неизвестная ошибка')
        }
      }
    }

    // Auto TTS after full response
    const fullText = history.value[assistantIdx]?.content
    if (fullText) speak(fullText)

  } catch (e) {
    errorText.value = e?.message ?? String(e)
    if (!history.value[assistantIdx]?.content) history.value.pop()
  } finally {
    isBusy.value = false
  }
}

// ─── TTS ───────────────────────────────────────────────────────────────────
async function speak(text) {
  if (!text?.trim() || isSpeaking.value) return
  isSpeaking.value = true
  try {
    const res = await fetch('/api/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, voice: true }),
    })
    if (res.status === 204) {
      // Browser TTS fallback
      window.speechSynthesis.cancel()
      const voices = await new Promise(resolve => {
        const v = window.speechSynthesis.getVoices()
        if (v.length) return resolve(v)
        window.speechSynthesis.onvoiceschanged = () => resolve(window.speechSynthesis.getVoices())
      })
      const u = new SpeechSynthesisUtterance(text)
      const ruVoice = voices.find(v => v.lang.startsWith('ru'))
      if (ruVoice) u.voice = ruVoice
      u.lang = 'ru-RU'; u.rate = 0.95
      u.onend = () => { isSpeaking.value = false }
      window.speechSynthesis.speak(u)
      return
    }
    if (!res.ok) throw new Error(await res.text())
    const blob = await res.blob()
    const url  = URL.createObjectURL(blob)
    const audio = new Audio(url)
    audio.onended = () => { isSpeaking.value = false; URL.revokeObjectURL(url) }
    await audio.play()
  } catch {
    isSpeaking.value = false
  }
}

function stopSpeaking() {
  window.speechSynthesis.cancel()
  isSpeaking.value = false
}

function clearHistory() { history.value = []; errorText.value = '' }
</script>

<template>
  <!-- Floating toggle -->
  <div class="widget-wrap">
    <Transition name="widget-slide">
      <div v-if="isOpen" class="widget-panel">
        <!-- Header -->
        <div class="wp-header">
          <div class="wp-avatar">{{ courseIcon }}</div>
          <div class="wp-info">
            <div class="wp-name">EduAI</div>
            <div class="wp-course">{{ courseName }}</div>
          </div>
          <div class="wp-actions">
            <button class="wp-icon-btn" title="📞 Голосовой звонок" @click="openVoiceCall">📞</button>
            <button v-if="history.length" class="wp-icon-btn" title="Очистить" @click="clearHistory">🗑</button>
            <button class="wp-icon-btn" @click="toggle">✕</button>
          </div>
        </div>

        <!-- Thread -->
        <div class="wp-thread" ref="threadEl">
          <div v-if="history.length === 0" class="wp-welcome">
            <div class="wp-welcome-icon">👋</div>
            <p>Привет! Я ваш ИИ-ассистент по курсу <strong>{{ courseName }}</strong>.</p>
            <p>Задайте вопрос голосом 🎤 или текстом — отвечу по материалам курса.</p>
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
                <div class="wp-msg-actions">
                  <button class="wp-tts-btn" @click="isSpeaking ? stopSpeaking() : speak(msg.content)">
                    {{ isSpeaking ? '⏹ Стоп' : '🔊 Озвучить' }}
                  </button>
                </div>
              </template>
            </div>
          </div>

          <div v-if="isBusy" class="wp-typing">
            <span></span><span></span><span></span>
          </div>
        </div>

        <div v-if="errorText" class="wp-error">{{ errorText }}</div>

        <!-- Input row -->
        <div class="wp-input-row">
          <input
            class="wp-input"
            v-model="message"
            :disabled="isBusy"
            placeholder="Задайте вопрос…"
            @keydown.enter.prevent="sendStream"
          />
          <button
            class="wp-mic-btn"
            :class="{ listening: isListening }"
            :title="isListening ? 'Остановить запись' : 'Голосовой ввод'"
            @click="startListening"
          >
            {{ isListening ? '⏹' : '🎤' }}
          </button>
          <button class="wp-send-btn" :disabled="!canSend" @click="sendStream">
            <span v-if="!isBusy">↑</span>
            <span v-else class="wp-spinner"></span>
          </button>
        </div>
      </div>
    </Transition>

    <!-- Trigger button -->
    <button class="widget-fab" :class="{ open: isOpen }" @click="toggle" title="Открыть EduAI">
      <span class="fab-pulse" v-if="!isOpen"></span>
      <span class="fab-icon">{{ isOpen ? '✕' : '🤖' }}</span>
      <span v-if="!isOpen" class="fab-label">EduAI</span>
    </button>

    <!-- Voice Call Modal -->
    <VoiceCall
      v-if="isCallOpen"
      :courseId="courseId"
      :courseName="courseName"
      :initialHistory="history"
      @close="handleVoiceCallClose"
      @history-update="handleHistoryUpdate"
    />
  </div>
</template>

<style scoped>
/* ─── Widget Panel ───────────────────────────── */
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

.widget-slide-enter-active,
.widget-slide-leave-active {
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
  transform-origin: bottom right;
}
.widget-slide-enter-from,
.widget-slide-leave-to {
  opacity: 0;
  transform: scale(0.9) translateY(20px);
}

/* ─── Header ─────────────────────────────────── */
.wp-header {
  display: flex;
  align-items: center;
  padding: 16px 20px;
  background: rgba(255, 255, 255, 0.03);
  border-bottom: 1px solid var(--border);
}

.wp-avatar {
  font-size: 28px;
  margin-right: 12px;
  background: rgba(255, 255, 255, 0.05);
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.wp-info {
  flex: 1;
}

.wp-name {
  font-weight: 600;
  font-size: 16px;
  color: var(--text);
}

.wp-course {
  font-size: 12px;
  color: var(--accent2);
  margin-top: 2px;
}

.wp-actions {
  display: flex;
  gap: 8px;
}

.wp-icon-btn {
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
  font-size: 18px;
  padding: 4px;
  border-radius: 6px;
  transition: all 0.2s;
}

.wp-icon-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text);
}

/* ─── Thread ─────────────────────────────────── */
.wp-thread {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  scrollbar-width: thin;
  scrollbar-color: rgba(255,255,255,0.1) transparent;
}

.wp-welcome {
  text-align: center;
  color: var(--muted);
  font-size: 14px;
  margin: 20px 0;
}

.wp-welcome-icon {
  font-size: 40px;
  margin-bottom: 10px;
}

/* ─── Messages ───────────────────────────────── */
.wp-msg-row {
  display: flex;
  width: 100%;
}

.wp-msg-row.user {
  justify-content: flex-end;
}

.wp-msg-row.assistant {
  justify-content: flex-start;
}

.wp-bubble {
  max-width: 85%;
  padding: 12px 16px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.5;
}

.wp-bubble.user {
  background: var(--accent);
  color: white;
  border-bottom-right-radius: 4px;
}

.wp-bubble.assistant {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text);
  border: 1px solid var(--border);
  border-bottom-left-radius: 4px;
}

.wp-role {
  font-size: 11px;
  font-weight: 600;
  margin-bottom: 4px;
  opacity: 0.7;
  text-transform: uppercase;
}

.wp-msg-row.user .wp-role {
  text-align: right;
}

.wp-text {
  white-space: pre-wrap;
  word-break: break-word;
}

/* ─── Sources & Actions ──────────────────────── */
.wp-sources {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid rgba(255,255,255,0.1);
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.src-label {
  font-size: 12px;
  color: var(--muted);
}

.src-pill {
  font-size: 11px;
  padding: 2px 8px;
  background: rgba(255,255,255,0.1);
  border-radius: 10px;
  color: var(--text);
}

.wp-msg-actions {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
}

.wp-tts-btn {
  background: none;
  border: 1px solid var(--border);
  color: var(--muted);
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.wp-tts-btn:hover {
  background: rgba(255,255,255,0.1);
  color: var(--text);
}

/* ─── Typing Indicator ───────────────────────── */
.wp-typing {
  display: flex;
  gap: 4px;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 16px;
  border-bottom-left-radius: 4px;
  width: fit-content;
}

.wp-typing span {
  width: 6px;
  height: 6px;
  background: var(--muted);
  border-radius: 50%;
  animation: typing 1s infinite alternate;
}

.wp-typing span:nth-child(2) { animation-delay: 0.2s; }
.wp-typing span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  from { opacity: 0.3; transform: translateY(0); }
  to { opacity: 1; transform: translateY(-4px); }
}

.wp-error {
  color: var(--danger);
  padding: 10px 20px;
  font-size: 13px;
  background: rgba(251, 113, 133, 0.1);
  border-top: 1px solid rgba(251, 113, 133, 0.2);
}

/* ─── Input Area ─────────────────────────────── */
.wp-input-row {
  display: flex;
  align-items: center;
  padding: 16px 20px;
  gap: 10px;
  background: rgba(0, 0, 0, 0.2);
  border-top: 1px solid var(--border);
}

.wp-input {
  flex: 1;
  background: transparent;
  border: none;
  color: var(--text);
  font-size: 14px;
  outline: none;
  font-family: inherit;
}

.wp-input::placeholder {
  color: var(--muted);
}

.wp-mic-btn, .wp-send-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
}

.wp-mic-btn {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text);
  font-size: 16px;
}

.wp-mic-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.wp-mic-btn.listening {
  background: rgba(251, 113, 133, 0.2);
  color: var(--danger);
  animation: pulse-mic 1.5s infinite;
}

@keyframes pulse-mic {
  0% { box-shadow: 0 0 0 0 rgba(251, 113, 133, 0.4); }
  70% { box-shadow: 0 0 0 10px rgba(251, 113, 133, 0); }
  100% { box-shadow: 0 0 0 0 rgba(251, 113, 133, 0); }
}

.wp-send-btn {
  background: var(--accent);
  color: white;
  font-size: 18px;
}

.wp-send-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 10px rgba(124, 92, 255, 0.4);
}

.wp-send-btn:disabled {
  background: rgba(255, 255, 255, 0.1);
  color: var(--muted);
  cursor: not-allowed;
}

.wp-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid transparent;
  border-top-color: white;
  border-radius: 50%;
  animation: wp-spin 0.8s linear infinite;
}

@keyframes wp-spin {
  to { transform: rotate(360deg); }
}
</style>
