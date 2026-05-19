<template>
  <div class="hw-detail-view" v-if="hw && user">
    <header class="header">
      <button class="back-btn" @click="$router.push('/homeworks')">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M19 12H5M12 19l-7-7 7-7" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        Назад к списку
      </button>
      <div class="course-badge">{{ hw.course_id }}</div>
    </header>

    <div class="layout">
      <aside class="hw-info panel">
        <h2>{{ hw.title }}</h2>
        <div v-if="hw.content" class="structured-desc">
          <p class="intro-block">{{ hw.content.intro }}</p>
          <div class="part-block">
            <h4>Код · {{ hw.content.code_filename }}</h4>
            <pre class="code-preview">{{ hw.content.code_template }}</pre>
          </div>
          <div v-if="quizItems.length" class="part-block">
            <h4>Тесты (варианты ответов)</h4>
            <div v-for="(q, qi) in quizItems" :key="qi" class="quiz-q">
              <p class="quiz-qtext"><strong>{{ qi + 1 }}.</strong> {{ q.question }}</p>
              <ul class="quiz-opts">
                <li v-for="(opt, oi) in q.options" :key="oi">{{ quizLetter(oi) }}) {{ opt }}</li>
              </ul>
            </div>
          </div>
          <div v-if="hw.content.tests_code?.trim()" class="part-block">
            <h4>Доп. автотесты (pytest)</h4>
            <pre class="code-preview">{{ hw.content.tests_code }}</pre>
          </div>
          <div class="part-block">
            <h4>Письменная часть</h4>
            <p class="written-preview">{{ hw.content.written_part }}</p>
          </div>
        </div>
        <div v-else class="desc-box">{{ hw.description }}</div>

        <div v-if="!isTeacher && myAssignment" class="my-status">
          <div class="status-badge" :class="myAssignment.status">
            {{ formatStatus(myAssignment.status) }}
          </div>
          <div v-if="myAssignment.grade" class="grade-box">
            Оценка: <strong>{{ myAssignment.grade }} / 5</strong>
          </div>
          <div v-if="myAssignment.teacher_feedback" class="feedback-box">
            <h4>Отзыв преподавателя:</h4>
            <div class="feedback-html" v-html="renderFeedback(myAssignment.teacher_feedback)"></div>
          </div>
        </div>

        <div v-if="isTeacher" class="students-list">
          <h3>Ученики:</h3>
          <div
            v-for="a in hw.assignments"
            :key="a.id"
            class="student-item"
            :class="{ active: selectedAssignment?.id === a.id }"
            @click="selectAssignment(a)"
          >
            <div>{{ a.student_name }}</div>
            <div class="status-badge small" :class="a.status">{{ formatStatus(a.status) }}</div>
          </div>
        </div>
      </aside>

      <main class="workspace panel">
        <div v-if="!isTeacher && myAssignment">
          <div v-if="myAssignment.status === 'pending'">
            <h3>Ваше решение</h3>
            <div class="form-group">
              <label>Код ({{ hw.content?.code_filename || 'solution.py' }})</label>
              <textarea v-model="submitData.student_code" rows="12" class="code-font" placeholder="def solve(): ..."></textarea>
            </div>
            <div v-if="quizItems.length" class="form-group quiz-form">
              <label>Тесты</label>
              <div v-for="(q, qi) in quizItems" :key="qi" class="quiz-answer-block">
                <p class="quiz-qtext">{{ qi + 1 }}. {{ q.question }}</p>
                <label v-for="(opt, oi) in q.options" :key="oi" class="quiz-radio">
                  <input type="radio" :name="'sq-' + qi" :value="oi" v-model.number="submitData.student_quiz[qi]" />
                  <span>{{ quizLetter(oi) }}) {{ opt }}</span>
                </label>
              </div>
            </div>
            <div class="form-group">
              <label>Письменная часть</label>
              <textarea v-model="submitData.student_text" rows="6" placeholder="Ответы на вопросы из задания..."></textarea>
            </div>
            <div v-if="hintText" class="hint-box">
              <h4>Подсказка от Кортаны</h4>
              <p>{{ hintText }}</p>
            </div>
            <div class="submit-actions">
              <button type="button" class="action-btn secondary" @click="handleHint" :disabled="hintLoading || submitting">
                {{ hintLoading ? 'Думаю…' : 'Подсказка' }}
              </button>
              <button class="action-btn" @click="handleSubmit" :disabled="submitting || hintLoading">
                {{ submitting ? 'Отправка...' : 'Отправить на проверку' }}
              </button>
            </div>
          </div>
          <div v-else>
            <h3>Ваш отправленный ответ</h3>
            <div v-if="quizItems.length" class="readonly-box quiz-readonly">
              <h4>Тесты</h4>
              <div v-for="(q, qi) in quizItems" :key="qi" class="quiz-q">
                <p class="quiz-qtext"><strong>{{ qi + 1 }}.</strong> {{ q.question }}</p>
                <p class="quiz-picked">
                  Ваш выбор:
                  <strong>{{ formatStudentQuizPick(qi, myAssignment.student_quiz) }}</strong>
                </p>
              </div>
            </div>
            <div class="readonly-box submission-view">
              <pre class="submission-code"><code v-html="studentHighlightedCode"></code></pre>
            </div>
            <div class="readonly-box text-box submission-view" v-html="studentHighlightedText"></div>
          </div>
        </div>

        <div v-if="isTeacher">
          <div v-if="!selectedAssignment" class="empty-state">
            Выберите ученика слева для проверки задания
          </div>
          <div v-else>
            <h3>Ответ ученика: {{ selectedAssignment.student_name }}</h3>
            <p v-if="activeFragments.length" class="submission-hint">Красным — фрагменты с ошибками в ответе ученика</p>
            <div class="readonly-box submission-view">
              <h4>Код:</h4>
              <pre class="submission-code"><code v-html="teacherHighlightedCode"></code></pre>
            </div>
            <div class="readonly-box text-box submission-view">
              <h4>Письменная часть:</h4>
              <div class="submission-text" v-html="teacherHighlightedText"></div>
            </div>

            <div v-if="quizItems.length" class="readonly-box quiz-teacher-review">
              <h4>Тесты (ответ ученика)</h4>
              <div v-for="(q, qi) in quizItems" :key="qi" class="quiz-q">
                <p class="quiz-qtext"><strong>{{ qi + 1 }}.</strong> {{ q.question }}</p>
                <p :class="['quiz-result', quizResultClass(qi, selectedAssignment)]">
                  Ответ: {{ formatStudentQuizPick(qi, selectedAssignment.student_quiz) }}
                  · Верно:
                  {{ quizCorrectLetter(qi, q) }}
                  ·
                  {{ isQuizCorrect(qi, q, selectedAssignment) ? 'верно' : 'ошибка' }}
                </p>
              </div>
            </div>

            <div class="grading-section" v-if="selectedAssignment.status === 'submitted'">
              <h3>Оценка и отзыв</h3>
              <div class="form-group">
                <label>Оценка (1–5)</label>
                <select v-model="gradeData.grade">
                  <option :value="5">5 — отлично</option>
                  <option :value="4">4 — хорошо</option>
                  <option :value="3">3 — удовлетворительно</option>
                  <option :value="2">2 — неудовлетворительно</option>
                  <option :value="1">1 — неудовлетворительно</option>
                </select>
              </div>
              <div class="form-group">
                <label>Отзыв</label>
                <p class="feedback-hint">Красная подсветка — в сером блоке. Ниже — текст отзыва для правок.</p>
                <div
                  v-if="gradeData.teacher_feedback"
                  class="feedback-preview feedback-html"
                  v-html="renderFeedback(gradeData.teacher_feedback)"
                ></div>
                <textarea
                  v-model="gradeData.teacher_feedback"
                  rows="8"
                  placeholder="Нажмите «Проверить с ИИ»…"
                ></textarea>
              </div>
              <div class="grading-actions">
                <button
                  type="button"
                  class="action-btn secondary"
                  @click="handleAiReview"
                  :disabled="aiReviewing || grading"
                >
                  {{ aiReviewing ? 'ИИ проверяет…' : 'Проверить с ИИ (Кортана)' }}
                </button>
                <button class="action-btn" @click="handleGrade" :disabled="grading || aiReviewing">
                  {{ grading ? 'Сохранение…' : 'Сохранить оценку' }}
                </button>
              </div>
            </div>
            <div v-else-if="selectedAssignment.status === 'graded'" class="already-graded">
              <h4>Оценено: {{ selectedAssignment.grade }} / 5</h4>
              <div class="feedback-html" v-html="renderFeedback(selectedAssignment.teacher_feedback)"></div>
            </div>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'
import { hwApi } from '../api'
import {
  extractErrorFragments,
  highlightSubmission,
  renderFeedbackHtml,
} from '../utils/homeworkHighlight'

const route = useRoute()
const router = useRouter()
const { fetchUser } = useAuth()

const user = ref(null)
const hw = ref(null)
const selectedAssignment = ref(null)

const isTeacher = computed(() => user.value?.role === 'teacher')
const myAssignment = computed(() => {
  if (isTeacher.value) return null
  return hw.value?.assignments?.find(a => a.student_id === user.value.id)
})

const quizItems = computed(() => {
  const items = hw.value?.content?.quiz_items
  if (!Array.isArray(items)) return []
  return items.filter((q) => q && (q.question?.trim() || (q.options || []).length))
})

function buildEmptyQuizSlots(items) {
  const o = {}
  if (!Array.isArray(items)) return o
  items.forEach((q, i) => {
    if (q?.options?.length) o[i] = null
  })
  return o
}

function quizLetter(oi) {
  return String.fromCharCode(65 + oi)
}

function formatStudentQuizPick(qi, studentQuiz) {
  const sq = studentQuiz || {}
  const key = String(qi)
  const picked = sq[key] ?? sq[qi]
  if (picked === undefined || picked === null) return '—'
  const q = quizItems.value[qi]
  const opt = q?.options?.[picked]
  return opt ? `${quizLetter(picked)}) ${opt}` : `${quizLetter(picked)})`
}

function quizCorrectLetter(qi, q) {
  const ci = q?.correct_index ?? 0
  const letter = quizLetter(ci)
  const opt = q?.options?.[ci]
  return opt ? `${letter}) ${opt}` : letter
}

function isQuizCorrect(qi, q, assignment) {
  const sq = assignment?.student_quiz || {}
  const picked = sq[String(qi)] ?? sq[qi]
  const correct = q?.correct_index ?? 0
  if (picked === undefined || picked === null) return false
  return Number(picked) === Number(correct)
}

function quizResultClass(qi, assignment) {
  const q = quizItems.value[qi]
  return isQuizCorrect(qi, q, assignment) ? 'ok' : 'bad'
}

const submitData = ref({ student_code: '', student_text: '', student_quiz: {} })
const submitting = ref(false)
const hintText = ref('')
const hintLoading = ref(false)

const gradeData = ref({ grade: 3, teacher_feedback: '' })
const grading = ref(false)
const aiReviewing = ref(false)
/** Фрагменты для подсветки в ответе ученика (с API после ИИ-проверки). */
const errorFragments = ref([])

const activeFragments = computed(() => {
  if (errorFragments.value.length) return errorFragments.value
  const fb =
    gradeData.value.teacher_feedback ||
    selectedAssignment.value?.teacher_feedback ||
    myAssignment.value?.teacher_feedback
  return extractErrorFragments(fb)
})

const teacherHighlightedCode = computed(() =>
  highlightSubmission(selectedAssignment.value?.student_code || 'Нет кода', activeFragments.value)
)

const teacherHighlightedText = computed(() =>
  highlightSubmission(selectedAssignment.value?.student_text || 'Нет текста', activeFragments.value)
)

const studentHighlightedCode = computed(() =>
  highlightSubmission(myAssignment.value?.student_code, activeFragments.value)
)

const studentHighlightedText = computed(() =>
  highlightSubmission(myAssignment.value?.student_text, activeFragments.value)
)

const renderFeedback = renderFeedbackHtml

function syncHomeworkContext() {
  const a = isTeacher.value ? selectedAssignment.value : myAssignment.value
  const draft = !isTeacher.value && a?.status === 'pending' ? submitData.value : null
  const items = quizItems.value.map((q) => ({
    question: q.question,
    options: q.options || [],
    ...(isTeacher.value && q.correct_index != null ? { correct_index: q.correct_index } : {}),
  }))
  window.currentHomeworkContext = {
    courseId: hw.value?.course_id,
    homeworkId: hw.value?.id,
    title: hw.value?.title,
    desc: hw.value?.description,
    intro: hw.value?.content?.intro || hw.value?.description || '',
    codeTemplate: hw.value?.content?.code_template || '',
    codeFilename: hw.value?.content?.code_filename || 'solution.py',
    writtenPart: hw.value?.content?.written_part || '',
    quizItems: items,
    assignment: a
      ? {
          id: a.id,
          student: a.student_name,
          code: draft?.student_code ?? a.student_code,
          text: draft?.student_text ?? a.student_text,
          quiz: draft?.student_quiz ?? a.student_quiz,
          status: a.status,
          grade: a.grade ?? null,
          teacher_feedback: a.teacher_feedback || '',
        }
      : null,
  }
  window.dispatchEvent(new CustomEvent('eduai-homework-context'))
}

watch(selectedAssignment, (a) => {
  if (!a) return
  gradeData.value = {
    grade: a.grade ?? 3,
    teacher_feedback: a.teacher_feedback || '',
  }
  errorFragments.value = extractErrorFragments(a.teacher_feedback || '')
  syncHomeworkContext()
})

watch(myAssignment, () => syncHomeworkContext(), { deep: true })

watch(submitData, () => {
  if (!isTeacher.value && myAssignment.value?.status === 'pending') syncHomeworkContext()
}, { deep: true })

function onVoiceHomeworkReviewed(e) {
  const { assignmentId, teacher_feedback, suggested_grade, error_fragments } = e.detail || {}
  if (!assignmentId || selectedAssignment.value?.id !== assignmentId) return
  gradeData.value.teacher_feedback = teacher_feedback || ''
  errorFragments.value = error_fragments?.length
    ? error_fragments
    : extractErrorFragments(teacher_feedback)
  if (suggested_grade) gradeData.value.grade = suggested_grade
}

onMounted(async () => {
  user.value = await fetchUser()
  if (!user.value) return router.push('/login')
  window.addEventListener('eduai-homework-reviewed', onVoiceHomeworkReviewed)
  window.addEventListener('eduai-homework-hint', onVoiceHomeworkHint)
  await loadHomework()
})

onUnmounted(() => {
  window.removeEventListener('eduai-homework-reviewed', onVoiceHomeworkReviewed)
  window.removeEventListener('eduai-homework-hint', onVoiceHomeworkHint)
})

function onVoiceHomeworkHint(e) {
  const { assignmentId, hint } = e.detail || {}
  if (assignmentId && myAssignment.value?.id === assignmentId) {
    hintText.value = hint || ''
  }
}

async function loadHomework() {
  try {
    hw.value = await hwApi.getHomework(route.params.id)
    syncHomeworkContext()

    if (isTeacher.value) {
      const qStudent = route.query.student ? Number(route.query.student) : null
      if (qStudent) {
        const picked = hw.value.assignments.find((a) => a.student_id === qStudent)
        if (picked) selectAssignment(picked)
      } else {
        const submitted = hw.value.assignments.find((a) => a.status === 'submitted')
        if (submitted) selectAssignment(submitted)
      }
    } else if (myAssignment.value?.status === 'pending') {
      const items = hw.value.content?.quiz_items || []
      submitData.value = {
        student_code: hw.value.content?.code_template || '',
        student_text: '',
        student_quiz: buildEmptyQuizSlots(items),
      }
    }
  } catch (e) {
    alert('Не удалось загрузить ДЗ: ' + e.message)
    router.push('/homeworks')
  }
}

function selectAssignment(a) {
  selectedAssignment.value = a
}

function formatStatus(status) {
  if (status === 'pending') return 'Ожидает'
  if (status === 'submitted') return 'На проверке'
  if (status === 'graded') return 'Оценено'
  return status
}

async function handleSubmit() {
  const needQuiz = quizItems.value.filter((q) => (q.options || []).length > 0)
  if (needQuiz.length) {
    for (let i = 0; i < quizItems.value.length; i++) {
      const q = quizItems.value[i]
      if (!(q.options || []).length) continue
      const v = submitData.value.student_quiz[i]
      if (v === undefined || v === null) {
        alert(`Выберите вариант в тесте ${i + 1}`)
        return
      }
    }
  }
  const payload = {
    student_code: submitData.value.student_code,
    student_text: submitData.value.student_text,
  }
  if (needQuiz.length) {
    const sq = {}
    quizItems.value.forEach((q, i) => {
      if (!(q.options || []).length) return
      sq[String(i)] = submitData.value.student_quiz[i]
    })
    payload.student_quiz = sq
  }
  submitting.value = true
  try {
    const updated = await hwApi.submitHomework(myAssignment.value.id, payload)
    const idx = hw.value.assignments.findIndex(a => a.id === updated.id)
    if (idx !== -1) hw.value.assignments[idx] = updated
  } catch (e) {
    alert(e.message)
  }
  submitting.value = false
}

async function handleHint() {
  if (!myAssignment.value?.id || myAssignment.value.status !== 'pending') return
  hintLoading.value = true
  try {
    const res = await hwApi.getHomeworkHint(myAssignment.value.id, {
      student_code: submitData.value.student_code,
      student_text: submitData.value.student_text,
      student_quiz: submitData.value.student_quiz,
    })
    hintText.value = res.hint || ''
  } catch (e) {
    alert(e.message || 'Не удалось получить подсказку')
  }
  hintLoading.value = false
}

async function handleAiReview() {
  if (!selectedAssignment.value) return
  aiReviewing.value = true
  try {
    const result = await hwApi.aiReviewHomework(selectedAssignment.value.id)
    gradeData.value.teacher_feedback = result.teacher_feedback
    errorFragments.value =
      result.error_fragments?.length
        ? result.error_fragments
        : extractErrorFragments(result.teacher_feedback)
    if (result.suggested_grade) {
      gradeData.value.grade = result.suggested_grade
    }
  } catch (e) {
    alert(e.message)
  }
  aiReviewing.value = false
}

async function handleGrade() {
  grading.value = true
  try {
    const updated = await hwApi.gradeHomework(selectedAssignment.value.id, gradeData.value)
    const idx = hw.value.assignments.findIndex(a => a.id === updated.id)
    if (idx !== -1) hw.value.assignments[idx] = updated
    selectedAssignment.value = updated
  } catch (e) {
    alert(e.message)
  }
  grading.value = false
}
</script>

<style scoped>
.hw-detail-view {
  min-height: 100vh;
  background: #09090b;
  color: #e4e4e7;
  font-family: 'Inter', system-ui, sans-serif;
  padding: 24px;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}
.back-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  background: none;
  border: none;
  color: #a1a1aa;
  cursor: pointer;
}
.back-btn:hover {
  color: #fff;
}
.course-badge {
  background: #27272a;
  padding: 6px 12px;
  border-radius: 8px;
  color: #a1a1aa;
  font-size: 14px;
}

.layout {
  display: flex;
  gap: 24px;
  align-items: flex-start;
}
.panel {
  background: #18181b;
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 16px;
  padding: 24px;
}
.hw-info {
  width: 350px;
  flex-shrink: 0;
}
.workspace {
  flex-grow: 1;
  min-height: 500px;
}

.hw-info h2 {
  margin-top: 0;
}
.desc-box,
.structured-desc {
  color: #a1a1aa;
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 24px;
  max-height: 360px;
  overflow-y: auto;
}
.structured-desc .intro-block {
  margin: 0 0 16px;
  white-space: pre-wrap;
}
.part-block {
  margin-bottom: 16px;
}
.part-block h4 {
  margin: 0 0 8px;
  font-size: 13px;
  color: #818cf8;
}
.code-preview {
  margin: 0;
  padding: 12px;
  background: #09090b;
  border: 1px solid #27272a;
  border-radius: 8px;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  color: #c4b5fd;
  white-space: pre-wrap;
  overflow-x: auto;
}
.written-preview {
  margin: 0;
  white-space: pre-wrap;
}

.status-badge {
  display: inline-block;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
}
.status-badge.small {
  padding: 4px 8px;
  font-size: 12px;
}
.status-badge.pending {
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
}
.status-badge.submitted {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
}
.status-badge.graded {
  background: rgba(16, 185, 129, 0.15);
  color: #34d399;
}

.grade-box {
  margin-top: 16px;
  font-size: 18px;
  color: #34d399;
}
.feedback-box {
  margin-top: 16px;
  background: #27272a;
  padding: 16px;
  border-radius: 8px;
}

.students-list {
  margin-top: 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  padding-top: 16px;
}
.student-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}
.student-item:hover {
  background: rgba(255, 255, 255, 0.05);
}
.student-item.active {
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid rgba(99, 102, 241, 0.3);
}

.form-group {
  margin-bottom: 20px;
}
.form-group label {
  display: block;
  margin-bottom: 8px;
  color: #a1a1aa;
}
.form-group textarea,
.form-group select {
  width: 100%;
  background: #09090b;
  border: 1px solid #3f3f46;
  color: white;
  padding: 12px;
  border-radius: 8px;
  font-family: inherit;
  resize: vertical;
}
.code-font {
  font-family: 'Fira Code', 'Courier New', Courier, monospace;
  color: #a5b4fc;
}

.action-btn {
  background: #4f46e5;
  color: white;
  border: none;
  padding: 12px 24px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 16px;
  font-weight: 500;
}
.action-btn.secondary {
  background: #27272a;
  border: 1px solid #3f3f46;
}
.action-btn.secondary:hover:not(:disabled) {
  background: #3f3f46;
}
.action-btn:hover:not(:disabled) {
  background: #4338ca;
}
.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.submit-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 8px;
}

.hint-box {
  margin: 16px 0;
  padding: 14px 16px;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.35);
  border-radius: 8px;
}
.hint-box h4 {
  margin: 0 0 8px;
  font-size: 14px;
  color: #a5b4fc;
}
.hint-box p {
  margin: 0;
  line-height: 1.5;
  color: #e4e4e7;
}

.grading-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.readonly-box {
  background: #09090b;
  border: 1px solid #27272a;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 20px;
}
.readonly-box pre {
  margin: 0;
  white-space: pre-wrap;
  font-family: 'Fira Code', monospace;
  color: #a5b4fc;
}
.submission-view :deep(.hw-error) {
  color: #ef4444 !important;
  font-weight: 700;
  background: rgba(239, 68, 68, 0.12);
  border-radius: 3px;
  padding: 0 2px;
}
.submission-text {
  white-space: pre-wrap;
  line-height: 1.6;
}
.submission-hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: #f87171;
}
.text-box {
  color: #e4e4e7;
  white-space: pre-wrap;
  line-height: 1.5;
}

.grading-section {
  margin-top: 40px;
  padding-top: 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}
.already-graded {
  margin-top: 24px;
  padding: 20px;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 8px;
  color: #e4e4e7;
}
.empty-state {
  text-align: center;
  color: #a1a1aa;
  margin-top: 100px;
  font-size: 18px;
}

.feedback-html :deep(.hw-error),
.feedback-html :deep(span.hw-error) {
  color: #ef4444 !important;
  font-weight: 700;
}
.feedback-hint {
  margin: 0 0 8px;
  font-size: 13px;
  color: #71717a;
}
.feedback-preview {
  margin-bottom: 12px;
  padding: 12px;
  background: #27272a;
  border: 1px solid #3f3f46;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.6;
}

.quiz-opts {
  margin: 0;
  padding-left: 18px;
  color: #d4d4d8;
}
.quiz-q {
  margin-bottom: 12px;
}
.quiz-qtext {
  margin: 0 0 6px;
}
.quiz-form .quiz-answer-block {
  margin-bottom: 16px;
  padding: 12px;
  background: #09090b;
  border-radius: 8px;
  border: 1px solid #27272a;
}
.quiz-radio {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 6px 0;
  cursor: pointer;
  color: #e4e4e7;
}
.quiz-radio input {
  margin-top: 3px;
}
.quiz-picked,
.quiz-result {
  margin: 4px 0 0;
  font-size: 14px;
  color: #a1a1aa;
}
.quiz-result.ok {
  color: #34d399;
}
.quiz-result.bad {
  color: #f87171;
}
.quiz-readonly,
.quiz-teacher-review {
  margin-bottom: 16px;
}

@media (max-width: 768px) {
  .layout {
    flex-direction: column;
  }
  .hw-info {
    width: 100%;
  }
}
</style>
