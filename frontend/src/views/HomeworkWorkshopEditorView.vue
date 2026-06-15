<template>
  <div class="workshop-editor" v-if="loaded">
    <GlassHeader>
      <div style="display: flex; align-items: center; gap: 16px;">
        <button type="button" class="glass-back-btn" @click="$router.push('/homeworks/workshop')">
          ← Хранилище
        </button>
      </div>
      <div style="display: flex; align-items: center; gap: 12px;">
        <span v-if="saving" class="save-hint">Сохранение…</span>
        <span v-else-if="savedAt" class="save-hint ok">Сохранено</span>
        <button type="button" class="glass-btn" @click="save" :disabled="saving">Сохранить</button>
        <button type="button" class="glass-btn glass-btn-primary" @click="showAssign = true">Назначить ученикам</button>
      </div>
    </GlassHeader>

    <div class="meta-row">
      <div class="field">
        <label>Название</label>
        <input v-model="form.title" type="text" placeholder="Тема ДЗ" @input="scheduleSave" />
      </div>
      <div class="field">
        <label>Курс</label>
        <select v-model="form.course_id" @change="scheduleSave">
          <option v-for="c in courses" :key="c.id" :value="c.id">{{ c.icon }} {{ c.title }}</option>
        </select>
      </div>
    </div>

    <div class="editor-layout">
      <nav class="section-nav">
        <button
          v-for="s in sections"
          :key="s.id"
          type="button"
          :class="{ active: activeSection === s.id }"
          @click="activeSection = s.id"
        >
          <span class="nav-icon">{{ s.icon }}</span>
          {{ s.label }}
        </button>
      </nav>

      <main class="section-panel">
        <section v-show="activeSection === 'intro'" class="block">
          <h2>Описание задания</h2>
          <p class="hint">Что должен сделать ученик, критерии, сроки.</p>
          <textarea
            v-model="form.content.intro"
            rows="8"
            class="prose-input"
            @input="scheduleSave"
          />
        </section>

        <section v-show="activeSection === 'code'" class="block">
          <h2>Код</h2>
          <p class="hint">Шаблон, который ученик дополняет (моноширинный шрифт).</p>
          <label class="mini-label">Имя файла</label>
          <input
            v-model="form.content.code_filename"
            type="text"
            class="filename-input"
            @input="scheduleSave"
          />
          <textarea
            v-model="form.content.code_template"
            rows="14"
            class="code-input"
            spellcheck="false"
            @input="scheduleSave"
          />
        </section>

        <section v-show="activeSection === 'tests'" class="block">
          <h2>Тесты</h2>
          <p class="hint">Задания с вариантами ответов — отметьте один верный вариант на каждый вопрос.</p>
          <div v-for="(q, qi) in form.content.quiz_items" :key="qi" class="quiz-edit-card">
            <div class="quiz-card-head">
              <span>Вопрос {{ qi + 1 }}</span>
              <button type="button" class="danger-link" @click="removeQuiz(qi)">Удалить</button>
            </div>
            <label class="mini-label">Формулировка</label>
            <textarea
              v-model="q.question"
              rows="2"
              class="prose-input"
              placeholder="Текст вопроса…"
              @input="scheduleSave"
            />
            <div class="quiz-meta-row">
              <div class="quiz-meta-field">
                <label class="mini-label">Тема (для адаптивности)</label>
                <input
                  v-model="q.topic"
                  type="text"
                  class="opt-input"
                  placeholder="Например: циклы, функции…"
                  @input="scheduleSave"
                />
              </div>
              <div class="quiz-meta-field">
                <label class="mini-label">Урок курса</label>
                <select v-model="q.lesson_id" class="opt-input" @change="scheduleSave">
                  <option :value="null">— не привязан —</option>
                  <option v-for="l in lessonOptions" :key="l.id" :value="l.id">{{ l.title }}</option>
                </select>
              </div>
            </div>
            <label class="mini-label">Варианты ответа</label>
            <div v-for="(opt, oi) in q.options" :key="oi" class="opt-row">
              <span class="opt-letter">{{ letter(oi) }}</span>
              <input
                v-model="q.options[oi]"
                type="text"
                class="opt-input"
                :placeholder="'Вариант ' + letter(oi)"
                @input="scheduleSave"
              />
              <label class="correct-pick" title="Верный ответ">
                <input type="radio" :name="'corr-' + qi" :value="oi" v-model.number="q.correct_index" @change="scheduleSave" />
                верный
              </label>
              <button
                v-if="q.options.length > 2"
                type="button"
                class="mini-remove"
                @click="removeOption(qi, oi)"
              >
                ×
              </button>
            </div>
            <button type="button" class="ghost-btn small-btn" @click="addOption(qi)">+ Вариант</button>
          </div>
          <button type="button" class="ghost-btn" @click="addQuiz">+ Вопрос</button>

          <h3 class="pytest-head">Автотесты pytest (по желанию)</h3>
          <p class="hint">Необязательный код для самопроверки; в задании ученику показывается отдельным блоком.</p>
          <textarea
            v-model="form.content.tests_code"
            rows="8"
            class="code-input"
            spellcheck="false"
            @input="scheduleSave"
          />
        </section>

        <section v-show="activeSection === 'written'" class="block">
          <h2>Письменная часть</h2>
          <p class="hint">Вопросы теории, объяснения своими словами.</p>
          <textarea
            v-model="form.content.written_part"
            rows="10"
            class="prose-input"
            @input="scheduleSave"
          />
        </section>

        <section v-show="activeSection === 'reference'" class="block">
          <h2>Эталон (только для вас)</h2>
          <p class="hint">Не показывается ученику. Помогает ИИ при проверке.</p>
          <textarea
            v-model="form.content.reference_code"
            rows="14"
            class="code-input"
            spellcheck="false"
            @input="scheduleSave"
          />
        </section>

        <section v-show="activeSection === 'preview'" class="block preview-block">
          <h2>Предпросмотр для ученика</h2>
          <div class="preview-box" v-html="previewHtml"></div>
        </section>
      </main>
    </div>

    <div v-if="showAssign" class="modal-overlay" @click.self="showAssign = false">
      <div class="modal">
        <h3>Назначить: {{ form.title }}</h3>
        <p class="modal-hint">Выберите учеников — будет создано активное ДЗ из этого шаблона.</p>
        <div class="students-box">
          <label v-for="st in students" :key="st.id" class="st-row">
            <input type="checkbox" :value="st.id" v-model="assignIds" />
            {{ st.username }}
          </label>
        </div>
        <div class="modal-actions">
          <button type="button" class="ghost-btn" @click="showAssign = false">Отмена</button>
          <button type="button" class="primary-btn" :disabled="assigning" @click="assign">
            {{ assigning ? 'Назначаем…' : 'Назначить' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'
import { workshopApi, hwApi, apiFetch } from '../api'
import GlassHeader from '../components/GlassHeader.vue'

const route = useRoute()
const router = useRouter()
const { fetchUser, hasAccess } = useAuth()

const loaded = ref(false)
const saving = ref(false)
const savedAt = ref(false)
const showAssign = ref(false)
const assigning = ref(false)
const assignIds = ref([])
const students = ref([])
const courses = ref([])
const activeSection = ref('intro')
let saveTimer = null

const sections = [
  { id: 'intro', label: 'Описание', icon: '📋' },
  { id: 'code', label: 'Код', icon: '⌨️' },
  { id: 'tests', label: 'Тесты', icon: '✅' },
  { id: 'written', label: 'Письменная', icon: '✍️' },
  { id: 'reference', label: 'Эталон', icon: '🔒' },
  { id: 'preview', label: 'Просмотр', icon: '👁' },
]

const form = ref({
  course_id: 'python',
  title: '',
  content: {
    intro: '',
    code_filename: 'solution.py',
    code_template: '',
    tests_code: '',
    quiz_items: [],
    written_part: '',
    reference_code: '',
  },
})

const previewHtml = computed(() => buildPreview(form.value))

const lessonOptions = computed(() => {
  const c = courses.value.find((x) => x.id === form.value.course_id)
  return Array.isArray(c?.lessons) ? c.lessons : []
})

onMounted(async () => {
  const user = await fetchUser()
  if (!user || !hasAccess('/homeworks/workshop', { adminOrTeacherOnly: true })) return router.push('/homeworks')
  try {
    courses.value = await apiFetch('/courses')
    students.value = await hwApi.getStudents()
    const t = await workshopApi.getTemplate(route.params.id)
    const qi = Array.isArray(t.content?.quiz_items) ? t.content.quiz_items : []
    form.value = {
      course_id: t.course_id,
      title: t.title,
      content: {
        ...form.value.content,
        ...t.content,
        quiz_items: qi.length ? qi.map(normalizeQuiz) : [],
      },
    }
    loaded.value = true
  } catch (e) {
    alert(e.message)
    router.push('/homeworks/workshop')
  }
  window.addEventListener('eduai-fill-homework', onAiFillHomework)
})

onUnmounted(() => {
  if (saveTimer) clearTimeout(saveTimer)
  window.removeEventListener('eduai-fill-homework', onAiFillHomework)
})

function onAiFillHomework(e) {
  const data = e.detail || {}
  let changed = false
  if (data.title) {
    form.value.title = data.title
    changed = true
  }
  if (data.intro) {
    form.value.content.intro = data.intro
    activeSection.value = 'intro'
    changed = true
  }
  if (data.code_template) {
    form.value.content.code_template = data.code_template
    if (!data.intro) activeSection.value = 'code'
    changed = true
  }
  if (data.written_part) {
    form.value.content.written_part = data.written_part
    if (!data.intro && !data.code_template) activeSection.value = 'written'
    changed = true
  }
  if (data.quiz_items && Array.isArray(data.quiz_items) && data.quiz_items.length > 0) {
    form.value.content.quiz_items = data.quiz_items.map(normalizeQuiz)
    if (!data.intro && !data.code_template && !data.written_part) activeSection.value = 'tests'
    changed = true
  }
  if (changed) scheduleSave()
}

function scheduleSave() {
  savedAt.value = false
  clearTimeout(saveTimer)
  saveTimer = setTimeout(save, 800)
}

async function save() {
  saving.value = true
  try {
    await workshopApi.updateTemplate(route.params.id, {
      course_id: form.value.course_id,
      title: form.value.title,
      content: form.value.content,
    })
    savedAt.value = true
  } catch (e) {
    alert('Ошибка сохранения: ' + e.message)
  }
  saving.value = false
}

async function assign() {
  if (!assignIds.value.length) return alert('Выберите учеников')
  assigning.value = true
  try {
    await save()
    const hw = await workshopApi.assignTemplate(route.params.id, assignIds.value)
    showAssign.value = false
    router.push(`/homeworks/${hw.id}`)
  } catch (e) {
    alert(e.message)
  }
  assigning.value = false
}

function esc(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function letter(i) {
  return String.fromCharCode(65 + i)
}

function normalizeQuiz(q) {
  const opts = Array.isArray(q?.options) ? q.options.map((o) => String(o || '').trim()).filter(Boolean) : []
  const options = opts.length >= 2 ? opts : ['', '']
  let ci = Number(q?.correct_index)
  if (Number.isNaN(ci)) ci = 0
  if (ci < 0 || ci >= options.length) ci = 0
  let lessonId = q?.lesson_id
  if (lessonId === '' || lessonId === undefined) lessonId = null
  else lessonId = Number(lessonId)
  if (lessonId != null && Number.isNaN(lessonId)) lessonId = null
  return {
    question: String(q?.question || ''),
    options,
    correct_index: ci,
    topic: String(q?.topic || '').trim(),
    lesson_id: lessonId,
  }
}

function addQuiz() {
  form.value.content.quiz_items.push({
    question: '',
    options: ['', ''],
    correct_index: 0,
    topic: '',
    lesson_id: null,
  })
  scheduleSave()
}

function removeQuiz(qi) {
  form.value.content.quiz_items.splice(qi, 1)
  scheduleSave()
}

function addOption(qi) {
  form.value.content.quiz_items[qi].options.push('')
  scheduleSave()
}

function removeOption(qi, oi) {
  const q = form.value.content.quiz_items[qi]
  if (q.options.length <= 2) return
  q.options.splice(oi, 1)
  if (q.correct_index >= q.options.length) q.correct_index = q.options.length - 1
  scheduleSave()
}

function buildPreview(f) {
  const c = f.content
  let quizHtml = ''
  const items = (c.quiz_items || []).filter((q) => q?.question?.trim() || (q?.options || []).some((o) => String(o).trim()))
  if (items.length) {
    quizHtml = '<h4>Часть 2. Тесты</h4>'
    items.forEach((q, qi) => {
      quizHtml += `<p><strong>Вопрос ${qi + 1}.</strong> ${esc(q.question)}</p><ul>`
      ;(q.options || []).forEach((opt, oi) => {
        const mark = oi === q.correct_index ? ' <em>(верный)</em>' : ''
        quizHtml += `<li>${letter(oi)}) ${esc(opt)}${mark}</li>`
      })
      quizHtml += '</ul>'
    })
  } else {
    quizHtml = '<h4>Часть 2. Тесты</h4><p class="pv-muted">Пока без вопросов.</p>'
  }
  const pytest = (c.tests_code || '').trim()
    ? `<h4>Дополнительно: pytest</h4><pre class="pv-code">${esc(c.tests_code)}</pre>`
    : ''
  return `
    <p>${esc(c.intro).replace(/\n/g, '<br>')}</p>
    <h4>Часть 1. Код — <code>${esc(c.code_filename)}</code></h4>
    <pre class="pv-code">${esc(c.code_template)}</pre>
    ${quizHtml}
    ${pytest}
    <h4>Часть 3. Письменная часть</h4>
    <p>${esc(c.written_part).replace(/\n/g, '<br>')}</p>
  `
}
</script>

<style scoped>
.workshop-editor {
  min-height: 100vh;
  background: #09090b;
  color: #e4e4e7;
  padding: 20px 24px 48px;
  font-family: 'Inter', system-ui, sans-serif;
}
.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 12px;
}
.top-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.back-btn,
.ghost-btn {
  background: none;
  border: 1px solid #3f3f46;
  color: #e4e4e7;
  padding: 8px 14px;
  border-radius: 8px;
  cursor: pointer;
}
.ghost-btn:hover {
  background: #27272a;
}
.primary-btn {
  background: #6366f1;
  color: #fff;
  border: none;
  padding: 10px 18px;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
}
.primary-btn:disabled {
  opacity: 0.6;
}
.save-hint {
  font-size: 13px;
  color: #71717a;
}
.save-hint.ok {
  color: #34d399;
}
.meta-row {
  display: grid;
  grid-template-columns: 1fr 220px;
  gap: 16px;
  margin-bottom: 20px;
}
.field label,
.mini-label {
  display: block;
  font-size: 13px;
  color: #a1a1aa;
  margin-bottom: 6px;
}
.field input,
.field select,
.filename-input {
  width: 100%;
  background: #18181b;
  border: 1px solid #3f3f46;
  color: #fff;
  padding: 10px 12px;
  border-radius: 8px;
  font: inherit;
}
.editor-layout {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 20px;
  min-height: 60vh;
}
.section-nav {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.section-nav button {
  display: flex;
  align-items: center;
  gap: 10px;
  text-align: left;
  background: #18181b;
  border: 1px solid #27272a;
  color: #a1a1aa;
  padding: 12px 14px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 14px;
}
.section-nav button.active {
  border-color: #6366f1;
  color: #fff;
  background: rgba(99, 102, 241, 0.12);
}
.nav-icon {
  font-size: 18px;
}
.section-panel {
  background: #18181b;
  border: 1px solid #27272a;
  border-radius: 16px;
  padding: 24px;
}
.block h2 {
  margin: 0 0 8px;
  font-size: 20px;
}
.hint {
  margin: 0 0 16px;
  color: #71717a;
  font-size: 14px;
}
.prose-input {
  width: 100%;
  background: #09090b;
  border: 1px solid #3f3f46;
  color: #e4e4e7;
  padding: 14px;
  border-radius: 10px;
  font: inherit;
  line-height: 1.6;
  resize: vertical;
}
.code-input {
  width: 100%;
  background: #0c0c0f;
  border: 1px solid #3f3f46;
  color: #c4b5fd;
  padding: 16px;
  border-radius: 10px;
  font-family: 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
  font-size: 14px;
  line-height: 1.55;
  tab-size: 4;
  resize: vertical;
}
.filename-input {
  max-width: 280px;
  margin-bottom: 12px;
  font-family: 'Fira Code', monospace;
}
.preview-box {
  background: #09090b;
  border-radius: 10px;
  padding: 16px;
  font-size: 14px;
  line-height: 1.6;
}
.preview-box :deep(.pv-code) {
  background: #0c0c0f;
  border: 1px solid #27272a;
  border-radius: 8px;
  padding: 12px;
  overflow-x: auto;
  font-family: 'Fira Code', monospace;
  color: #a5b4fc;
  white-space: pre-wrap;
}
.preview-box :deep(code) {
  font-family: 'Fira Code', monospace;
  color: #a5b4fc;
}
.preview-box :deep(.pv-muted) {
  color: #71717a;
  font-size: 14px;
}
.quiz-edit-card {
  background: #09090b;
  border: 1px solid #27272a;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
}
.quiz-meta-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin: 10px 0 12px;
}
@media (max-width: 720px) {
  .quiz-meta-row {
    grid-template-columns: 1fr;
  }
}
.quiz-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  font-size: 13px;
  color: #a1a1aa;
}
.opt-row {
  display: grid;
  grid-template-columns: 28px 1fr auto auto;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
.opt-letter {
  font-weight: 600;
  color: #818cf8;
  text-align: center;
}
.opt-input {
  width: 100%;
  background: #18181b;
  border: 1px solid #3f3f46;
  color: #fff;
  padding: 8px 10px;
  border-radius: 8px;
  font: inherit;
}
.correct-pick {
  font-size: 12px;
  color: #a1a1aa;
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
  cursor: pointer;
}
.mini-remove {
  background: none;
  border: none;
  color: #f87171;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
  padding: 0 4px;
}
.small-btn {
  margin-top: 8px;
  font-size: 13px;
}
.pytest-head {
  margin: 28px 0 0;
  font-size: 16px;
  color: #e4e4e7;
}
.danger-link {
  background: none;
  border: none;
  color: #f87171;
  cursor: pointer;
  font-size: 13px;
}
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}
.modal {
  background: #18181b;
  border: 1px solid #3f3f46;
  border-radius: 16px;
  padding: 24px;
  width: min(420px, 92vw);
}
.modal h3 {
  margin: 0 0 8px;
}
.modal-hint {
  color: #71717a;
  font-size: 14px;
  margin: 0 0 16px;
}
.students-box {
  max-height: 200px;
  overflow-y: auto;
  background: #09090b;
  border: 1px solid #3f3f46;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 20px;
}
.st-row {
  display: flex;
  gap: 8px;
  padding: 6px 0;
  cursor: pointer;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
@media (max-width: 768px) {
  .editor-layout {
    grid-template-columns: 1fr;
  }
  .section-nav {
    flex-direction: row;
    flex-wrap: wrap;
  }
  .meta-row {
    grid-template-columns: 1fr;
  }
}
</style>
