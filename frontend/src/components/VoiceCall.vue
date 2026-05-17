<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'

const props = defineProps({
  courseId: { type: String, required: true },
  courseName: { type: String, required: true },
  initialHistory: { type: Array, default: () => [] },
  initialPrompt: { type: String, default: '' }
})

const emit = defineEmits(['close', 'history-update'])

// State
const state = ref('IDLE') // IDLE, LISTENING, THINKING, SPEAKING
const transcript = ref('')
const assistantText = ref('')
const errorMsg = ref('')
const isMuted = ref(false)

// History
const history = ref([...props.initialHistory])

// Web Speech API
let recognition = null
// Audio queue
let audioQueue = []
let currentAudio = null
let isAudioPlaying = false
let streamDone = false

onMounted(() => {
  initRecognition()
  if (props.initialPrompt) {
    handleUserVoice(props.initialPrompt)
  } else {
    startListening()
  }
})

onUnmounted(() => {
  stopAll()
  emit('history-update', history.value)
})

const statusText = computed(() => {
  switch (state.value) {
    case 'LISTENING': return 'Слушаю...'
    case 'THINKING': return 'Думаю...'
    case 'SPEAKING': return 'Говорю...'
    default: return 'Ожидание...'
  }
})

function initRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SpeechRecognition) {
    errorMsg.value = 'Голосовой ввод не поддерживается в этом браузере'
    return
  }
  
  recognition = new SpeechRecognition()
  recognition.lang = 'ru-RU'
  recognition.interimResults = true
  recognition.continuous = false

  recognition.onstart = () => {
    state.value = 'LISTENING'
    transcript.value = ''
    errorMsg.value = ''
  }

  recognition.onresult = (e) => {
    const text = Array.from(e.results).map(r => r[0].transcript).join('')
    transcript.value = text
    
    if (e.results[e.results.length - 1].isFinal) {
      recognition.stop()
      handleUserVoice(text)
    }
  }

  recognition.onend = () => {
    // If we are still in listening state and not muted, restart (e.g. silence timeout)
    if (state.value === 'LISTENING' && !isMuted.value) {
      try { recognition.start() } catch (e) {}
    }
  }
  
  recognition.onerror = (e) => {
    if (e.error === 'no-speech' || e.error === 'network' || e.error === 'aborted') return
    errorMsg.value = `Ошибка: ${e.error}`
  }

  // Barge-in (перебивание)
  recognition.onspeechstart = () => {
    if (state.value === 'SPEAKING') {
      interruptAssistant()
    }
  }
}

function startListening() {
  if (isMuted.value || !recognition) return
  stopAudio()
  state.value = 'LISTENING'
  try { recognition.start() } catch (e) {}
}

function stopListening() {
  if (recognition) {
    recognition.stop()
  }
}

function interruptAssistant() {
    stopAudio()
    state.value = 'LISTENING'
    assistantText.value = '' // clear current speech text
}

function toggleMute() {
  isMuted.value = !isMuted.value
  if (isMuted.value) {
    stopListening()
    state.value = 'IDLE'
  } else {
    startListening()
  }
}

async function handleUserVoice(text) {
  if (!text.trim()) {
    startListening()
    return
  }
  
  state.value = 'THINKING'
  transcript.value = text
  assistantText.value = ''
  
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
      body: JSON.stringify({ message: text, history: apiHistory, course_id: props.courseId, course_name: props.courseName }),
    })
    
    if (!res.ok) throw new Error(await res.text())

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
        
        const evt = JSON.parse(jsonText)
        if (evt.type === 'sources') {
           history.value[assistantIdx].sources = Array.isArray(evt.content) ? evt.content : []
        } else if (evt.type === 'token') {
           history.value[assistantIdx].content += String(evt.content ?? '')
           // Update UI text instantly for visual feedback
           assistantText.value += String(evt.content ?? '')
        } else if (evt.type === 'sentence') {
           // Queue audio
           if (evt.audio_b64) {
               audioQueue.push(evt.audio_b64)
               playNextAudio()
           }
        } else if (evt.type === 'error') {
           errorMsg.value = String(evt.content ?? 'Ошибка')
        }
      }
    }
    
    streamDone = true
    // If audio queue is empty, and stream is done, go back to listening
    if (!isAudioPlaying && audioQueue.length === 0) {
        startListening()
    }

  } catch (e) {
    errorMsg.value = e.message
    startListening()
  }
}

async function playNextAudio() {
  if (isAudioPlaying || audioQueue.length === 0 || state.value === 'LISTENING') return
  
  isAudioPlaying = true
  state.value = 'SPEAKING'
  
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
          
          if (audioQueue.length > 0) {
              playNextAudio()
          } else if (streamDone) {
              startListening()
          }
      }
      
      currentAudio.onerror = () => {
          isAudioPlaying = false
          if (audioQueue.length > 0) playNextAudio()
          else if (streamDone) startListening()
      }

      await currentAudio.play()
  } catch(e) {
      console.error('Audio play error', e)
      isAudioPlaying = false
      if (audioQueue.length > 0) playNextAudio()
      else if (streamDone) startListening()
  }
}

function stopAudio() {
  audioQueue = []
  streamDone = true
  if (currentAudio) {
      currentAudio.pause()
      currentAudio = null
  }
  isAudioPlaying = false
}

function stopAll() {
  stopAudio()
  stopListening()
}

function endCall() {
  stopAll()
  emit('close')
}

</script>

<template>
  <div class="vc-overlay">
    <div class="vc-modal">
      <!-- Header -->
      <div class="vc-header">
        <div class="vc-course">{{ courseName }}</div>
        <button class="vc-icon-btn" @click="endCall">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      <!-- Orb Visualization -->
      <div class="vc-orb-container">
        <div class="vc-orb" :class="state.toLowerCase()">
          <div class="vc-orb-inner"></div>
        </div>
        <div class="vc-status">{{ statusText }}</div>
      </div>

      <!-- Text Transcripts -->
      <div class="vc-transcript-area">
        <div v-if="errorMsg" class="vc-error">{{ errorMsg }}</div>
        <div v-if="state === 'SPEAKING' || state === 'THINKING'" class="vc-text assistant">
          {{ assistantText }}
          <span v-if="state === 'THINKING'" class="vc-cursor"></span>
        </div>
        <div v-if="state === 'LISTENING' && transcript" class="vc-text user">
          {{ transcript }}
        </div>
      </div>

      <!-- Controls -->
      <div class="vc-controls">
        <button class="vc-btn-mute" :class="{ muted: isMuted }" @click="toggleMute">
          {{ isMuted ? '🔇 Включить микрофон' : '🎤 Выключить микрофон' }}
        </button>
        <button class="vc-btn-end" @click="endCall">
          Завершить
        </button>
      </div>
    </div>
  </div>
</template>
