<script setup>
import { computed, ref } from 'vue'

const ingestFiles = ref(/** @type {FileList | null} */ (null))
const ingestBusy = ref(false)
const ingestStatusBusy = ref(false)
const ingestResult = ref('')
const docs = ref(/** @type {string[]} */ ([]))

const message = ref('')
const chatBusy = ref(false)
const answer = ref('')
const sources = ref(/** @type {string[]} */ ([]))
const errorText = ref('')

const canSend = computed(() => message.value.trim().length > 0 && !chatBusy.value)

async function refreshIngestStatus() {
  ingestStatusBusy.value = true
  ingestResult.value = ''
  try {
    const res = await fetch('/api/ingest/status')
    if (!res.ok) throw new Error(await res.text())
    const data = await res.json()
    docs.value = Array.isArray(data.files) ? data.files : []
  } catch (e) {
    ingestResult.value = `Ошибка статуса: ${e?.message ?? String(e)}`
  } finally {
    ingestStatusBusy.value = false
  }
}

async function uploadAndIngest() {
  errorText.value = ''
  ingestResult.value = ''
  if (!ingestFiles.value || ingestFiles.value.length === 0) {
    ingestResult.value = 'Выберите файлы (.pdf/.docx/.txt/.md).'
    return
  }

  ingestBusy.value = true
  try {
    const fd = new FormData()
    for (const f of Array.from(ingestFiles.value)) fd.append('files', f)

    const res = await fetch('/api/ingest/upload', { method: 'POST', body: fd })
    if (!res.ok) throw new Error(await res.text())
    const data = await res.json()
    ingestResult.value = `Готово: ${data.status ?? 'ok'}; chunks=${data.chunks ?? '?'}`
    await refreshIngestStatus()
  } catch (e) {
    ingestResult.value = `Ошибка загрузки: ${e?.message ?? String(e)}`
  } finally {
    ingestBusy.value = false
  }
}

async function ingestServerDirectory() {
  ingestBusy.value = true
  ingestResult.value = ''
  try {
    const res = await fetch('/api/ingest/directory', { method: 'POST' })
    if (!res.ok) throw new Error(await res.text())
    const data = await res.json()
    ingestResult.value = `Готово: ${data.status ?? 'ok'}; chunks=${data.chunks ?? '?'}`
    await refreshIngestStatus()
  } catch (e) {
    ingestResult.value = `Ошибка индексации: ${e?.message ?? String(e)}`
  } finally {
    ingestBusy.value = false
  }
}

function appendAnswerToken(token) {
  answer.value += token
}

async function sendStream() {
  if (!canSend.value) return
  chatBusy.value = true
  errorText.value = ''
  answer.value = ''
  sources.value = []

  const body = JSON.stringify({ message: message.value, voice: false })

  try {
    const res = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
    })
    if (!res.ok) throw new Error(await res.text())
    if (!res.body) throw new Error('Нет тела ответа (stream).')

    const reader = res.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      // SSE events are separated by double newlines
      const parts = buffer.split('\n\n')
      buffer = parts.pop() ?? ''

      for (const part of parts) {
        const line = part
          .split('\n')
          .map((l) => l.trim())
          .find((l) => l.startsWith('data:'))
        if (!line) continue

        const jsonText = line.slice('data:'.length).trim()
        if (!jsonText) continue

        const evt = JSON.parse(jsonText)
        if (evt.type === 'sources') {
          sources.value = Array.isArray(evt.content) ? evt.content : []
        } else if (evt.type === 'token') {
          appendAnswerToken(String(evt.content ?? ''))
        } else if (evt.type === 'error') {
          errorText.value = String(evt.content ?? 'Unknown error')
        } else if (evt.type === 'done') {
          // no-op
        }
      }
    }
  } catch (e) {
    errorText.value = e?.message ?? String(e)
  } finally {
    chatBusy.value = false
  }
}

async function speak(text) {
  if (!text?.trim()) return
  try {
    const res = await fetch('/api/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, voice: true }),
    })
    if (res.status === 204) {
      const u = new SpeechSynthesisUtterance(text)
      u.lang = 'ru-RU'
      window.speechSynthesis.cancel()
      window.speechSynthesis.speak(u)
      return
    }
    if (!res.ok) throw new Error(await res.text())
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const audio = new Audio(url)
    audio.onended = () => URL.revokeObjectURL(url)
    await audio.play()
  } catch (e) {
    errorText.value = `TTS ошибка: ${e?.message ?? String(e)}`
  }
}

refreshIngestStatus()
</script>

<template>
  <div class="page">
    <header class="header">
      <div>
        <div class="title">EduAI</div>
        <div class="subtitle">Минимальный запуск: загрузка документов → RAG-чат</div>
      </div>
      <a class="health" href="/api/health" target="_blank" rel="noreferrer">/api/health</a>
    </header>

    <section class="card">
      <h2>1) Документы</h2>
      <div class="row">
        <input
          class="file"
          type="file"
          multiple
          accept=".pdf,.docx,.txt,.md"
          :disabled="ingestBusy"
          @change="(e) => (ingestFiles = e.target.files)"
        />
        <button class="btn" :disabled="ingestBusy" @click="uploadAndIngest">
          {{ ingestBusy ? 'Загружаю…' : 'Загрузить и проиндексировать' }}
        </button>
        <button class="btn secondary" :disabled="ingestBusy" @click="ingestServerDirectory">
          Индексировать папку сервера
        </button>
        <button class="btn secondary" :disabled="ingestStatusBusy" @click="refreshIngestStatus">
          Обновить список
        </button>
      </div>
      <div v-if="ingestResult" class="note">{{ ingestResult }}</div>
      <div class="docs">
        <div class="docs-title">Файлы ({{ docs.length }}):</div>
        <div class="docs-list">
          <span v-for="d in docs" :key="d" class="pill">{{ d }}</span>
          <span v-if="docs.length === 0" class="muted">Пока пусто. Загрузите материалы.</span>
        </div>
      </div>
    </section>

    <section class="card">
      <h2>2) Чат</h2>
      <div class="row">
        <input
          class="input"
          v-model="message"
          :disabled="chatBusy"
          placeholder="Задай вопрос по материалам курса…"
          @keydown.enter.prevent="sendStream"
        />
        <button class="btn" :disabled="!canSend" @click="sendStream">
          {{ chatBusy ? 'Думаю…' : 'Спросить (stream)' }}
        </button>
        <button class="btn secondary" :disabled="!answer || chatBusy" @click="speak(answer)">
          Озвучить
        </button>
      </div>

      <div v-if="errorText" class="error">{{ errorText }}</div>

      <div class="answer">
        <div class="answer-title">Ответ:</div>
        <pre class="answer-body">{{ answer || '—' }}</pre>
      </div>

      <div class="sources">
        <div class="sources-title">Источники:</div>
        <div class="docs-list">
          <span v-for="s in sources" :key="s" class="pill">{{ s }}</span>
          <span v-if="sources.length === 0" class="muted">—</span>
        </div>
      </div>
    </section>
  </div>
</template>
