<template>
  <div class="workshop-list" v-if="user">
    <GlassHeader>
      <div style="display: flex; align-items: center; gap: 16px;">
        <button class="glass-back-btn" @click="$router.push('/homeworks')">← К заданиям</button>
        <div style="width:1px; height:24px; background:rgba(255,255,255,0.1);"></div>
        <div style="display: flex; align-items: center; gap: 12px;">
          <h1 class="glass-title">Мастерская ДЗ</h1>
          <p style="margin: 0; font-size: 13px; color: var(--text-secondary);">Код, тесты, письменная часть</p>
        </div>
      </div>
      <button class="glass-btn glass-btn-primary" @click="createNew">+ Новый шаблон</button>
    </GlassHeader>

    <div v-if="loading" class="loading">Загрузка хранилища…</div>
    <div v-else-if="!templates.length" class="empty">
      <p>Пока пусто. Создайте первый шаблон в мастерской.</p>
      <button class="primary-btn" @click="createNew">Создать шаблон</button>
    </div>
    <div v-else class="grid">
      <article
        v-for="t in templates"
        :key="t.id"
        class="card"
        @click="$router.push(`/homeworks/workshop/${t.id}`)"
      >
        <span class="course">{{ t.course_id }}</span>
        <h3>{{ t.title }}</h3>
        <time v-if="t.updated_at">{{ formatDate(t.updated_at) }}</time>
        <div class="card-actions" @click.stop>
          <button type="button" class="link-btn" @click="$router.push(`/homeworks/workshop/${t.id}`)">
            Редактировать
          </button>
          <button type="button" class="danger-link" @click="remove(t)">Удалить</button>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'
import { workshopApi } from '../api'
import { apiFetch } from '../api'
import GlassHeader from '../components/GlassHeader.vue'

const router = useRouter()
const { fetchUser } = useAuth()
const user = ref(null)
const templates = ref([])
const loading = ref(true)

onMounted(async () => {
  user.value = await fetchUser()
  if (!user.value) return router.push('/login')
  if (user.value.role !== 'teacher') return router.push('/homeworks')
  await load()
})

async function load() {
  loading.value = true
  try {
    templates.value = await workshopApi.listTemplates()
  } catch (e) {
    console.error(e)
  }
  loading.value = false
}

async function createNew() {
  try {
    const courses = await apiFetch('/courses')
    const courseId = courses[0]?.id || 'python'
    const t = await workshopApi.createTemplate({
      course_id: courseId,
      title: 'Новое домашнее задание',
      content: {
        intro: 'Цель задания…',
        code_filename: 'solution.py',
        code_template: 'def solve():\n    pass\n',
        tests_code: '',
        quiz_items: [
          {
            question: 'Что вернёт len([]) в Python?',
            options: ['0', '1', 'Ошибка'],
            correct_index: 0,
          },
        ],
        written_part: '1. Ответьте своими словами…',
        reference_code: '',
      },
    })
    router.push(`/homeworks/workshop/${t.id}`)
  } catch (e) {
    alert(e.message)
  }
}

async function remove(t) {
  if (!confirm(`Удалить шаблон «${t.title}»?`)) return
  try {
    await workshopApi.deleteTemplate(t.id)
    templates.value = templates.value.filter((x) => x.id !== t.id)
  } catch (e) {
    alert(e.message)
  }
}

function formatDate(iso) {
  try {
    return new Date(iso).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return ''
  }
}
</script>

<style scoped>
.workshop-list {
  min-height: 100vh;
  background: #09090b;
  color: #e4e4e7;
  padding: 24px;
  font-family: 'Inter', system-ui, sans-serif;
}
.header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 32px;
}
.header h1 {
  margin: 0 0 4px;
  font-size: 28px;
}
.subtitle {
  margin: 0;
  color: #71717a;
  font-size: 14px;
  max-width: 520px;
}
.back-btn {
  background: none;
  border: none;
  color: #a1a1aa;
  cursor: pointer;
  padding: 8px 0;
}
.back-btn:hover {
  color: #fff;
}
.primary-btn {
  margin-left: auto;
  background: #6366f1;
  color: #fff;
  border: none;
  padding: 12px 20px;
  border-radius: 10px;
  font-weight: 600;
  cursor: pointer;
}
.primary-btn:hover {
  background: #4f46e5;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.card {
  background: #18181b;
  border: 1px solid #27272a;
  border-radius: 16px;
  padding: 20px;
  cursor: pointer;
  transition: border-color 0.2s, transform 0.2s;
}
.card:hover {
  border-color: #6366f1;
  transform: translateY(-2px);
}
.course {
  font-size: 12px;
  color: #818cf8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.card h3 {
  margin: 8px 0;
  font-size: 18px;
}
.card time {
  font-size: 12px;
  color: #71717a;
}
.card-actions {
  margin-top: 16px;
  display: flex;
  gap: 12px;
}
.link-btn,
.danger-link {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 13px;
  padding: 0;
}
.link-btn {
  color: #a5b4fc;
}
.danger-link {
  color: #f87171;
}
.empty,
.loading {
  text-align: center;
  color: #71717a;
  padding: 48px;
}
</style>
