<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'
import { analyticsApi } from '../api'

const router = useRouter()
const { fetchUser } = useAuth()
const summary = ref(null)
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  const user = await fetchUser()
  if (!user || user.role !== 'teacher') return router.push('/homeworks')
  try {
    summary.value = await analyticsApi.getSummary(7)
  } catch (e) {
    error.value = e.message
  }
  loading.value = false
})

function fmt(ms) {
  if (ms == null) return '—'
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)} с`
  return `${Math.round(ms)} мс`
}
</script>

<template>
  <div class="analytics-view">
    <header class="header">
      <button class="back-btn" @click="router.push('/journal')">← Журнал</button>
      <h1>Метрики ассистента</h1>
      <p class="sub">За последние {{ summary?.period_days ?? 7 }} дней (для главы «Тестирование»)</p>
    </header>

    <p v-if="loading" class="muted">Загрузка…</p>
    <p v-else-if="error" class="error">{{ error }}</p>

    <div v-else-if="summary" class="grid">
      <div class="card">
        <h3>Всего событий</h3>
        <p class="big">{{ summary.total_events }}</p>
      </div>

      <div class="card">
        <h3>RAG (поиск в материалах)</h3>
        <p>Запросов: {{ summary.chat_rag.count }}</p>
        <p>Среднее: {{ fmt(summary.chat_rag.avg_ms) }}</p>
      </div>

      <div class="card">
        <h3>Ответ LLM (чат)</h3>
        <p>Запросов: {{ summary.chat_llm.count }}</p>
        <p>Среднее: {{ fmt(summary.chat_llm.avg_ms) }}</p>
      </div>

      <div class="card">
        <h3>ИИ-проверка ДЗ</h3>
        <p>Проверок: {{ summary.ai_homework_review.count }}</p>
        <p>Среднее: {{ fmt(summary.ai_homework_review.avg_ms) }}</p>
      </div>

      <div class="card wide">
        <h3>Голосовая навигация</h3>
        <p>
          Успешно: {{ summary.voice_navigation.success ?? 0 }},
          сбоев: {{ summary.voice_navigation.failed ?? 0 }}
        </p>
        <p v-if="summary.voice_navigation.success_rate != null">
          Доля успеха: {{ Math.round(summary.voice_navigation.success_rate * 100) }}%
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.analytics-view {
  max-width: 960px;
  margin: 0 auto;
  padding: 32px 24px 80px;
}
.header {
  margin-bottom: 28px;
}
.back-btn {
  background: none;
  border: none;
  color: #a5b4fc;
  cursor: pointer;
  margin-bottom: 12px;
}
h1 {
  font-size: 28px;
  margin: 0 0 8px;
}
.sub {
  color: #94a3b8;
  margin: 0;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}
.card {
  background: #18181b;
  border: 1px solid #3f3f46;
  border-radius: 12px;
  padding: 18px;
}
.card.wide {
  grid-column: 1 / -1;
}
.card h3 {
  margin: 0 0 12px;
  font-size: 15px;
  color: #a5b4fc;
}
.card p {
  margin: 4px 0;
  color: #e4e4e7;
}
.big {
  font-size: 32px;
  font-weight: 700;
}
.muted,
.error {
  color: #94a3b8;
}
.error {
  color: #f87171;
}
</style>
