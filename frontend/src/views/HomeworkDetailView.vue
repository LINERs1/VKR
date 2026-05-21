<template>
  <div class="hd-page" v-if="hw && user">
    <!-- TOPBAR -->
    <header class="hd-topbar">
      <button class="hd-back" @click="$router.push('/homeworks')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <line x1="19" y1="12" x2="5" y2="12"/>
          <polyline points="12 19 5 12 12 5"/>
        </svg>
        Задания
      </button>
      <div class="hd-breadcrumb">
        <span class="hd-course-chip">{{ hw.course_id }}</span>
        <span class="hd-slash">/</span>
        <span class="hd-hw-title-crumb">{{ hw.title }}</span>
      </div>
    </header>

    <div class="hd-layout">
      <!-- ═══ LEFT SIDEBAR ═══ -->
      <aside class="hd-sidebar">        <!-- Student status (student view) -->
        <div class="hd-card hd-status-card" v-if="!isTeacher && myAssignment">
          <div class="hd-status-row">
            <span class="hd-status-label">Статус</span>
            <span class="hd-badge" :class="myAssignment.status">{{ formatStatus(myAssignment.status) }}</span>
          </div>
          <div class="hd-status-row" v-if="myAssignment.grade">
            <span class="hd-status-label">Оценка</span>
            <span class="hd-grade-val" :class="gradeClass(myAssignment.grade)">{{ myAssignment.grade }} / 5</span>
          </div>
          <div v-if="myAssignment.teacher_feedback" class="hd-feedback">
            <div class="hd-feedback-title">Отзыв преподавателя</div>
            <div class="feedback-html" v-html="renderFeedback(myAssignment.teacher_feedback)"></div>
          </div>
        </div>

        <!-- Students list (teacher view) -->
        <div class="hd-card hd-students-card" v-if="isTeacher">
          <div class="hd-students-header">
            <span>Студенты</span>
            <span class="hd-students-count">{{ hw.assignments.length }}</span>
          </div>
          <div
            v-for="a in hw.assignments"
            :key="a.id"
            class="hd-student-row"
            :class="{ active: selectedAssignment?.id === a.id }"
            @click="selectAssignment(a)"
          >
            <div class="hd-student-info">
              <div class="hd-student-avatar">{{ (a.student_name || '?')[0].toUpperCase() }}</div>
              <div class="hd-student-name">{{ a.student_name || 'Студент #' + a.student_id }}</div>
            </div>
            <span class="hd-badge small" :class="a.status">{{ formatStatus(a.status) }}</span>
          </div>
        </div>
      </aside>

      <!-- ═══ MAIN WORKSPACE ═══ -->
      <main class="hd-workspace">
        <!-- HW Meta -->
        <div class="hd-card hd-meta-card">
          <div class="hd-meta-icon">📝</div>
          <h2 class="hd-hw-name">{{ hw.title }}</h2>
          <div class="hd-meta-row" v-if="hw.content?.intro || hw.description">
            <p class="hd-intro">{{ hw.content?.intro || hw.description }}</p>
          </div>

          <!-- Code template -->
          <div class="hd-section" v-if="hw.content?.code_template">
            <div class="hd-section-label">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
              {{ hw.content.code_filename || 'solution.py' }}
            </div>
            <pre class="hd-code-block">{{ hw.content.code_template }}</pre>
          </div>

          <!-- Quiz -->
          <div class="hd-section" v-if="quizItems.length">
            <div class="hd-section-label">Тесты</div>
            <div v-for="(q, qi) in quizItems" :key="qi" class="hd-quiz-q">
              <p class="hd-quiz-qtext"><span class="hd-qnum">{{ qi + 1 }}.</span> {{ q.question }}</p>
              <ul class="hd-quiz-opts">
                <li v-for="(opt, oi) in q.options" :key="oi">{{ quizLetter(oi) }}) {{ opt }}</li>
              </ul>
            </div>
          </div>

          <!-- Written -->
          <div class="hd-section" v-if="hw.content?.written_part">
            <div class="hd-section-label">Письменная часть</div>
            <p class="hd-written">{{ hw.content.written_part }}</p>
          </div>

          <!-- Pytest tests -->
          <div class="hd-section" v-if="hw.content?.tests_code?.trim()">
            <div class="hd-section-label">Автотесты (pytest)</div>
            <pre class="hd-code-block">{{ hw.content.tests_code }}</pre>
          </div>
        </div>

        <!-- ── Student workspace ── -->
        <div v-if="!isTeacher && myAssignment">
          <!-- Pending: submit form -->
          <div v-if="myAssignment.status === 'pending'" class="hd-card hd-submit-card">
            <div class="hd-workspace-title">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
              Ваше решение
            </div>

            <div class="hd-field">
              <label class="hd-field-label">Код — {{ hw.content?.code_filename || 'solution.py' }}</label>
              <textarea v-model="submitData.student_code" rows="12" class="hd-textarea code-font" placeholder="def solve(): ..."></textarea>
            </div>

            <div v-if="quizItems.length" class="hd-field">
              <label class="hd-field-label">Тесты с вариантами ответов</label>
              <div v-for="(q, qi) in quizItems" :key="qi" class="hd-quiz-answer">
                <p class="hd-quiz-qtext"><span class="hd-qnum">{{ qi + 1 }}.</span> {{ q.question }}</p>
                <label v-for="(opt, oi) in q.options" :key="oi" class="hd-radio">
                  <input type="radio" :name="'sq-' + qi" :value="oi" v-model.number="submitData.student_quiz[qi]" />
                  <span>{{ quizLetter(oi) }}) {{ opt }}</span>
                </label>
              </div>
            </div>

            <div class="hd-field">
              <label class="hd-field-label">Письменная часть</label>
              <textarea v-model="submitData.student_text" rows="6" class="hd-textarea" placeholder="Ответы на вопросы из задания..."></textarea>
            </div>

            <div v-if="hintText" class="hd-hint">
              <div class="hd-hint-icon">💡</div>
              <div>
                <div class="hd-hint-title">Подсказка от Кортаны</div>
                <p class="hd-hint-text">{{ hintText }}</p>
              </div>
            </div>

            <div class="hd-actions">
              <button class="hd-btn secondary" @click="handleHint" :disabled="hintLoading || submitting">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                {{ hintLoading ? 'Думаю…' : 'Подсказка' }}
              </button>
              <button class="hd-btn primary" @click="handleSubmit" :disabled="submitting || hintLoading">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                {{ submitting ? 'Отправляем…' : 'Отправить на проверку' }}
              </button>
            </div>
          </div>

          <!-- Submitted/graded: readonly view -->
          <div v-else class="hd-card">
            <div class="hd-workspace-title">Отправленный ответ</div>

            <div v-if="quizItems.length" class="hd-readonly-block">
              <div class="hd-readonly-label">Тесты</div>
              <div v-for="(q, qi) in quizItems" :key="qi" class="hd-quiz-q">
                <p class="hd-quiz-qtext"><span class="hd-qnum">{{ qi + 1 }}.</span> {{ q.question }}</p>
                <p class="hd-quiz-picked">Ваш ответ: <strong>{{ formatStudentQuizPick(qi, myAssignment.student_quiz) }}</strong></p>
              </div>
            </div>

            <div class="hd-readonly-block">
              <div class="hd-readonly-label">Код</div>
              <pre class="hd-submission-code"><code v-html="studentHighlightedCode"></code></pre>
            </div>

            <div class="hd-readonly-block">
              <div class="hd-readonly-label">Письменная часть</div>
              <div class="hd-submission-text" v-html="studentHighlightedText"></div>
            </div>
          </div>
        </div>

        <!-- ── Teacher workspace ── -->
        <div v-if="isTeacher">
          <div v-if="!selectedAssignment" class="hd-empty-state">
            <div class="hd-es-icon">👈</div>
            <div class="hd-es-title">Выберите студента слева</div>
            <div class="hd-es-desc">Нажмите на имя студента, чтобы открыть его работу</div>
          </div>

          <div v-else style="display: flex; flex-direction: column; gap: 16px;">
            <!-- Student submission -->
            <div class="hd-card hd-submission-card">
              <div class="hd-submission-header">
                <div class="hd-student-avatar lg">{{ (selectedAssignment.student_name || '?')[0].toUpperCase() }}</div>
                <div>
                  <div class="hd-submission-student">{{ selectedAssignment.student_name || 'Студент' }}</div>
                  <span class="hd-badge" :class="selectedAssignment.status">{{ formatStatus(selectedAssignment.status) }}</span>
                </div>
              </div>

              <p v-if="activeFragments.length" class="hd-error-hint">🔴 Красным выделены фрагменты с ошибками</p>

              <div class="hd-readonly-block">
                <div class="hd-readonly-label">Код</div>
                <pre class="hd-submission-code"><code v-html="teacherHighlightedCode"></code></pre>
              </div>

              <div class="hd-readonly-block">
                <div class="hd-readonly-label">Письменная часть</div>
                <div class="hd-submission-text" v-html="teacherHighlightedText"></div>
              </div>

              <div v-if="quizItems.length" class="hd-readonly-block">
                <div class="hd-readonly-label">Тесты (ответы студента)</div>
                <div v-for="(q, qi) in quizItems" :key="qi" class="hd-quiz-q">
                  <p class="hd-quiz-qtext"><span class="hd-qnum">{{ qi + 1 }}.</span> {{ q.question }}</p>
                  <p :class="['hd-quiz-result', quizResultClass(qi, selectedAssignment)]">
                    Ответ: {{ formatStudentQuizPick(qi, selectedAssignment.student_quiz) }}
                    · Верно: {{ quizCorrectLetter(qi, q) }}
                    · <strong>{{ isQuizCorrect(qi, q, selectedAssignment) ? '✓ верно' : '✗ ошибка' }}</strong>
                  </p>
                </div>
              </div>
            </div>

            <!-- Grading panel -->
            <div class="hd-card hd-grade-card" v-if="selectedAssignment.status === 'submitted'">
              <div class="hd-workspace-title">Проверка и оценка</div>

              <div class="hd-grade-row">
                <label class="hd-field-label">Оценка</label>
                <div class="hd-grade-pills">
                  <button
                    v-for="g in [1,2,3,4,5]"
                    :key="g"
                    class="hd-grade-pill"
                    :class="{ active: gradeData.grade === g, [`g${g}`]: true }"
                    @click="gradeData.grade = g"
                    type="button"
                  >{{ g }}</button>
                </div>
              </div>

              <div class="hd-field">
                <label class="hd-field-label">Отзыв</label>
                <div v-if="gradeData.teacher_feedback" class="hd-feedback-preview feedback-html" v-html="renderFeedback(gradeData.teacher_feedback)"></div>
                <textarea v-model="gradeData.teacher_feedback" rows="8" class="hd-textarea" placeholder="Нажмите «Проверить с ИИ»…"></textarea>
              </div>

              <div class="hd-actions">
                <button
                  class="hd-btn ai-btn"
                  @click="handleAiReview"
                  :disabled="aiReviewing || grading"
                >
                  <svg v-if="!aiReviewing" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 2L2 7l10 5 10-5-10-5z" fill="currentColor" opacity="0.8"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
                  <span v-if="aiReviewing" class="ai-spinner"></span>
                  {{ aiReviewing ? 'Проверка запущена…' : 'Проверить с ИИ' }}
                </button>
                <button class="hd-btn primary" @click="handleGrade" :disabled="grading || aiReviewing">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>
                  {{ grading ? 'Сохраняем…' : 'Сохранить оценку' }}
                </button>
              </div>

              <!-- AI checking banner -->
              <div v-if="aiReviewing" class="hd-ai-checking-banner">
                <span class="hd-ai-checking-dot"></span>
                ИИ проверяет работу… Вы можете перейти на другую страницу.
              </div>
            </div>

            <!-- Already graded -->
            <div class="hd-card hd-graded-card" v-else-if="selectedAssignment.status === 'graded'">
              <div class="hd-graded-header">
                <span class="hd-graded-title">Оценено</span>
                <span class="hd-grade-big" :class="gradeClass(selectedAssignment.grade)">{{ selectedAssignment.grade }} / 5</span>
              </div>
              <div class="feedback-html" v-html="renderFeedback(selectedAssignment.teacher_feedback)"></div>
            </div>
          </div>
        </div>
      </main>
    </div>
  </div>

  <!-- Loading -->
  <div class="hd-loading" v-else>
    <div class="hd-spinner"></div>
    <span>Загрузка задания…</span>
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
  items.forEach((q, i) => { if (q?.options?.length) o[i] = null })
  return o
}

function quizLetter(oi) { return String.fromCharCode(65 + oi) }

function formatStudentQuizPick(qi, studentQuiz) {
  const sq = studentQuiz || {}
  const picked = sq[String(qi)] ?? sq[qi]
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

function gradeClass(g) {
  if (!g) return ''
  if (g >= 4.5) return 'g5'
  if (g >= 3.5) return 'g4'
  if (g >= 2.5) return 'g3'
  return 'g2'
}

const submitData = ref({ student_code: '', student_text: '', student_quiz: {} })
const submitting = ref(false)
const hintText = ref('')
const hintLoading = ref(false)

const gradeData = ref({ grade: 3, teacher_feedback: '' })
const grading = ref(false)
const errorFragments = ref([])

import { useNotifications, checkingAssignments, aiReviewCache } from '../composables/useNotifications.js'
const { addToast } = useNotifications()

const aiReviewing = computed(() => {
  return selectedAssignment.value && checkingAssignments.has(selectedAssignment.value.id)
})

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
  // First load cached AI result if it exists
  const cached = aiReviewCache.get(a.id)
  if (cached) {
    gradeData.value = {
      grade: cached.suggested_grade ?? a.grade ?? 3,
      teacher_feedback: cached.teacher_feedback || a.teacher_feedback || '',
    }
    errorFragments.value = cached.error_fragments?.length
      ? cached.error_fragments
      : extractErrorFragments(cached.teacher_feedback || a.teacher_feedback || '')
  } else if (a.ai_review) {
    gradeData.value = {
      grade: a.ai_review.suggested_grade ?? a.grade ?? 3,
      teacher_feedback: a.ai_review.teacher_feedback || a.teacher_feedback || '',
    }
    errorFragments.value = a.ai_review.error_fragments?.length
      ? a.ai_review.error_fragments
      : extractErrorFragments(a.ai_review.teacher_feedback || a.teacher_feedback || '')
  } else {
    gradeData.value = {
      grade: a.grade ?? 3,
      teacher_feedback: a.teacher_feedback || '',
    }
    errorFragments.value = extractErrorFragments(a.teacher_feedback || '')
  }
  syncHomeworkContext()
})

watch(myAssignment, () => syncHomeworkContext(), { deep: true })
watch(submitData, () => {
  if (!isTeacher.value && myAssignment.value?.status === 'pending') syncHomeworkContext()
}, { deep: true })

// Bug fix #2 & #3: voice review handler also blocks the button + persists to selectedAssignment
function onVoiceHomeworkReviewed(e) {
  const { assignmentId, teacher_feedback, suggested_grade, error_fragments } = e.detail || {}
  if (!assignmentId || selectedAssignment.value?.id !== assignmentId) return
  checkingAssignments.add(assignmentId)  // block button while receiving
  gradeData.value.teacher_feedback = teacher_feedback || ''
  errorFragments.value = error_fragments?.length
    ? error_fragments
    : extractErrorFragments(teacher_feedback)
  if (suggested_grade) gradeData.value.grade = suggested_grade
  // Persist feedback so navigating away and back keeps it
  if (selectedAssignment.value) {
    selectedAssignment.value = {
      ...selectedAssignment.value,
      teacher_feedback: teacher_feedback || selectedAssignment.value.teacher_feedback,
      grade: suggested_grade ?? selectedAssignment.value.grade,
    }
    const idx = hw.value?.assignments?.findIndex(a => a.id === assignmentId)
    if (idx !== undefined && idx >= 0 && hw.value) {
      hw.value.assignments[idx] = { ...hw.value.assignments[idx], teacher_feedback: teacher_feedback || '' }
    }
  }
  checkingAssignments.delete(assignmentId)
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

function selectAssignment(a) { selectedAssignment.value = a }

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
      if (v === undefined || v === null) { alert(`Выберите вариант в тесте ${i + 1}`); return }
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

function handleAiReview() {
  if (!selectedAssignment.value || aiReviewing.value) return
  const assignmentId = selectedAssignment.value.id
  checkingAssignments.add(assignmentId)
  
  addToast('Проверка запущена. Вы можете перейти на другую страницу.', 'info')

  hwApi.aiReviewHomework(assignmentId)
    .then(result => {
      // Store in global cache so result persists across navigation
      aiReviewCache.set(assignmentId, result)

      addToast(`✅ ДЗ проверено! Оценка: ${result.suggested_grade || '?'}`, 'success', `/homeworks/${hw.value.id}`)
      
      // Update local state if we are still on the same assignment
      if (selectedAssignment.value && selectedAssignment.value.id === assignmentId) {
        gradeData.value.teacher_feedback = result.teacher_feedback
        errorFragments.value = result.error_fragments?.length
            ? result.error_fragments
            : extractErrorFragments(result.teacher_feedback)
        if (result.suggested_grade) gradeData.value.grade = result.suggested_grade
        
        selectedAssignment.value = { ...selectedAssignment.value, teacher_feedback: result.teacher_feedback }
      }
      
      // Update global assignments list
      const idx = hw.value?.assignments?.findIndex(a => a.id === assignmentId)
      if (idx !== undefined && idx >= 0) {
        hw.value.assignments[idx] = {
          ...hw.value.assignments[idx],
          teacher_feedback: result.teacher_feedback,
          grade: result.suggested_grade ?? hw.value.assignments[idx].grade,
        }
      }
    })
    .catch(e => {
      addToast(e.message || 'Ошибка проверки ДЗ', 'error')
    })
    .finally(() => {
      checkingAssignments.delete(assignmentId)
    })
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
/* ─── Page ─────────────────────────────────────────── */
.hd-page {
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font-family: 'Inter', system-ui, sans-serif;
  display: flex;
  flex-direction: column;
}

/* ─── Topbar ────────────────────────────────────────── */
.hd-topbar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 24px;
  height: 52px;
  background: rgba(12,12,15,0.85);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 50;
  flex-shrink: 0;
}
.hd-back {
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  font-family: inherit;
  padding: 5px 8px;
  border-radius: 6px;
  transition: all 0.15s;
  flex-shrink: 0;
}
.hd-back:hover { color: var(--text); background: var(--bg-elevated); }

.hd-breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  overflow: hidden;
}
.hd-course-chip {
  background: var(--accent-subtle);
  color: var(--accent);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 3px 9px;
  border-radius: 5px;
  white-space: nowrap;
}
.hd-slash { color: var(--text-muted); }
.hd-hw-title-crumb {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ─── Layout ────────────────────────────────────────── */
.hd-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 0;
  flex: 1;
  min-height: 0;
}

/* ─── Sidebar ───────────────────────────────────────── */
.hd-sidebar {
  border-right: 1px solid var(--border);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  max-height: calc(100vh - 52px);
  position: sticky;
  top: 52px;
}

/* ─── Card ──────────────────────────────────────────── */
.hd-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 20px;
}

/* ─── Meta card ─────────────────────────────────────── */
.hd-meta-icon { font-size: 28px; margin-bottom: 10px; }
.hd-hw-name {
  margin: 0 0 12px;
  font-size: 17px;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.2;
}
.hd-intro {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  white-space: pre-wrap;
}
.hd-section { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border); }
.hd-section-label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--accent);
  margin-bottom: 8px;
}
.hd-code-block {
  margin: 0;
  padding: 10px 12px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  font-family: 'Fira Code', 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #a5b4fc;
  white-space: pre-wrap;
  overflow-x: auto;
  line-height: 1.6;
}
.hd-written { margin: 0; font-size: 13px; color: var(--text-secondary); white-space: pre-wrap; }

/* ─── Quiz ──────────────────────────────────────────── */
.hd-quiz-q { margin-bottom: 10px; }
.hd-quiz-qtext { margin: 0 0 5px; font-size: 13px; }
.hd-qnum { color: var(--accent); font-weight: 700; margin-right: 3px; }
.hd-quiz-opts { margin: 0; padding-left: 14px; font-size: 12px; color: var(--text-secondary); }
.hd-quiz-opts li { margin: 3px 0; }

/* ─── Status card ───────────────────────────────────── */
.hd-status-card { display: flex; flex-direction: column; gap: 10px; }
.hd-status-row { display: flex; align-items: center; justify-content: space-between; }
.hd-status-label { font-size: 12px; color: var(--text-secondary); }
.hd-grade-val {
  font-size: 22px;
  font-weight: 800;
}
.hd-grade-val.g5, .g5 { color: #10b981; }
.hd-grade-val.g4, .g4 { color: #6366f1; }
.hd-grade-val.g3, .g3 { color: #f59e0b; }
.hd-grade-val.g2, .g2 { color: #ef4444; }

.hd-feedback { margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--border); }
.hd-feedback-title { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--text-muted); margin-bottom: 8px; }

/* ─── Students card ─────────────────────────────────── */
.hd-students-card { padding: 16px; }
.hd-students-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--text-muted);
  margin-bottom: 10px;
}
.hd-students-count {
  background: var(--bg-elevated);
  border-radius: 20px;
  padding: 1px 7px;
  font-size: 11px;
  color: var(--text-secondary);
}
.hd-student-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 9px 10px;
  border-radius: 9px;
  cursor: pointer;
  transition: all 0.15s;
  margin-bottom: 2px;
}
.hd-student-row:hover { background: var(--bg-elevated); }
.hd-student-row.active { background: var(--accent-subtle); border: 1px solid rgba(99,102,241,0.25); }
.hd-student-info { display: flex; align-items: center; gap: 8px; min-width: 0; }
.hd-student-avatar {
  width: 30px; height: 30px;
  background: linear-gradient(135deg, var(--accent) 0%, #818cf8 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  color: white;
  flex-shrink: 0;
}
.hd-student-avatar.lg { width: 42px; height: 42px; font-size: 18px; }
.hd-student-name { font-size: 13px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* ─── Badges ────────────────────────────────────────── */
.hd-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 9px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
  flex-shrink: 0;
}
.hd-badge.small { font-size: 10px; padding: 2px 7px; }
.hd-badge.pending { background: rgba(245,158,11,0.12); color: #fbbf24; }
.hd-badge.submitted { background: rgba(99,102,241,0.12); color: #818cf8; }
.hd-badge.graded { background: rgba(16,185,129,0.12); color: #10b981; }

/* ─── Workspace ─────────────────────────────────────── */
.hd-workspace {
  padding: 24px;
  overflow-y: auto;
  max-height: calc(100vh - 52px);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ─── Workspace titles ──────────────────────────────── */
.hd-workspace-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 800;
  letter-spacing: -0.01em;
  margin-bottom: 16px;
  color: var(--text);
}

/* ─── Fields ────────────────────────────────────────── */
.hd-field { display: flex; flex-direction: column; gap: 7px; margin-bottom: 16px; }
.hd-field-label { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-secondary); }
.hd-textarea {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px 14px;
  color: var(--text);
  font-size: 14px;
  font-family: inherit;
  resize: vertical;
  outline: none;
  transition: border-color 0.15s;
  width: 100%;
  box-sizing: border-box;
}
.hd-textarea:focus { border-color: var(--accent); }
.hd-textarea.code-font { font-family: 'Fira Code', 'JetBrains Mono', monospace; font-size: 13px; color: #a5b4fc; }

/* ─── Quiz Answer ───────────────────────────────────── */
.hd-quiz-answer {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 8px;
}
.hd-radio {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 6px 0;
  cursor: pointer;
  font-size: 13px;
  color: var(--text);
}

/* ─── Hint box ──────────────────────────────────────── */
.hd-hint {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 14px 16px;
  background: rgba(99,102,241,0.07);
  border: 1px solid rgba(99,102,241,0.3);
  border-radius: 10px;
  margin-bottom: 16px;
}
.hd-hint-icon { font-size: 20px; flex-shrink: 0; }
.hd-hint-title { font-size: 13px; font-weight: 700; color: #818cf8; margin-bottom: 4px; }
.hd-hint-text { margin: 0; font-size: 14px; color: var(--text); line-height: 1.5; }

/* ─── Actions bar ───────────────────────────────────── */
.hd-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 4px;
}

/* ─── Buttons ───────────────────────────────────────── */
.hd-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 10px 18px;
  border-radius: 9px;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  border: none;
  transition: all 0.15s;
}
.hd-btn:disabled,
.hd-btn[disabled] { opacity: 0.45; cursor: not-allowed; pointer-events: none; filter: none !important; transform: none !important; }

.hd-btn.primary {
  background: var(--accent);
  color: white;
  box-shadow: 0 4px 12px rgba(99,102,241,0.25);
}
.hd-btn.primary:hover:not(:disabled) { background: var(--accent-hover); transform: translateY(-1px); }
.hd-btn.secondary {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  color: var(--text-secondary);
}
.hd-btn.secondary:hover:not(:disabled) { color: var(--text); border-color: var(--border-light); }
.hd-btn.ai-btn {
  background: linear-gradient(135deg, #4f46e5, #7c3aed);
  color: white;
  box-shadow: 0 4px 12px rgba(124,58,237,0.3);
}
.hd-btn.ai-btn:hover:not(:disabled) { filter: brightness(1.1); transform: translateY(-1px); }

/* ─── Readonly blocks ───────────────────────────────── */
.hd-readonly-block {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 14px;
}
.hd-readonly-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--text-muted);
  margin-bottom: 10px;
}
.hd-submission-code {
  margin: 0;
  white-space: pre-wrap;
  font-family: 'Fira Code', 'JetBrains Mono', monospace;
  font-size: 13px;
  color: #a5b4fc;
  line-height: 1.6;
}
.hd-submission-text { white-space: pre-wrap; line-height: 1.6; font-size: 14px; }
.hd-quiz-picked { margin: 4px 0 0; font-size: 13px; color: var(--text-secondary); }

.hd-quiz-result { margin: 4px 0 0; font-size: 13px; }
.hd-quiz-result.ok { color: #10b981; }
.hd-quiz-result.bad { color: #ef4444; }

/* ─── Error hint ────────────────────────────────────── */
.hd-error-hint { margin: 0 0 12px; font-size: 13px; color: #f87171; }

/* ─── Submission card ───────────────────────────────── */
.hd-submission-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
}
.hd-submission-student { font-size: 15px; font-weight: 700; margin-bottom: 4px; }

/* ─── Grade card ─────────────────────────────────────── */
.hd-grade-row { margin-bottom: 16px; }
.hd-grade-pills { display: flex; gap: 8px; margin-top: 8px; }
.hd-grade-pill {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  border: 2px solid var(--border);
  background: var(--bg);
  color: var(--text-secondary);
  font-size: 18px;
  font-weight: 800;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
}
.hd-grade-pill:hover { border-color: var(--border-light); color: var(--text); }
.hd-grade-pill.active.g5 { background: rgba(16,185,129,0.15); border-color: #10b981; color: #10b981; }
.hd-grade-pill.active.g4 { background: rgba(99,102,241,0.15); border-color: #6366f1; color: #6366f1; }
.hd-grade-pill.active.g3 { background: rgba(245,158,11,0.15); border-color: #f59e0b; color: #f59e0b; }
.hd-grade-pill.active.g2 { background: rgba(239,68,68,0.12); border-color: #ef4444; color: #ef4444; }
.hd-grade-pill.active.g1 { background: rgba(239,68,68,0.2); border-color: #ef4444; color: #ef4444; }

.hd-feedback-preview {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 14px;
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 10px;
}

/* ─── Graded card ────────────────────────────────────── */
.hd-graded-card { background: rgba(16,185,129,0.05); border-color: rgba(16,185,129,0.2); }
.hd-graded-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.hd-graded-title { font-size: 13px; font-weight: 700; color: #10b981; }
.hd-grade-big { font-size: 28px; font-weight: 900; }

/* ─── Empty state ────────────────────────────────────── */
.hd-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 24px;
  text-align: center;
}
.hd-es-icon { font-size: 40px; margin-bottom: 12px; }
.hd-es-title { font-size: 16px; font-weight: 700; margin-bottom: 6px; }
.hd-es-desc { font-size: 14px; color: var(--text-secondary); }

/* ─── Feedback HTML errors ───────────────────────────── */
.feedback-html :deep(.hw-error),
.feedback-html :deep(span.hw-error) {
  color: #ef4444 !important;
  font-weight: 700;
  background: rgba(239,68,68,0.1);
  border-radius: 3px;
  padding: 0 3px;
}

/* ─── Loading ────────────────────────────────────────── */
.hd-loading {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  color: var(--text-muted);
  font-size: 14px;
}
.hd-spinner {
  width: 32px; height: 32px;
  border: 3px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ─── Submission view errors ─────────────────────────── */
.hd-readonly-block :deep(.hw-error) {
  color: #ef4444 !important;
  font-weight: 700;
  background: rgba(239,68,68,0.12);
  border-radius: 3px;
  padding: 0 2px;
}

/* ─── AI checking banner ─────────────────────────────── */
.hd-ai-checking-banner {
  margin-top: 14px;
  padding: 12px 16px;
  border-radius: 10px;
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.3);
  color: var(--accent);
  font-size: 13px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 10px;
  animation: pulse-border 2s ease-in-out infinite;
}
.hd-ai-checking-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
  flex-shrink: 0;
  animation: pulse-dot 1.2s ease-in-out infinite;
}
.ai-spinner {
  display: inline-block;
  width: 13px;
  height: 13px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}
@keyframes pulse-border {
  0%, 100% { box-shadow: 0 0 0 0 rgba(99,102,241,0.2); }
  50% { box-shadow: 0 0 0 4px rgba(99,102,241,0); }
}
@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.75); }
}

/* ─── Responsive ─────────────────────────────────────── */
@media (max-width: 900px) {
  .hd-layout { grid-template-columns: 1fr; }
  .hd-sidebar { position: static; max-height: none; border-right: none; border-bottom: 1px solid var(--border); }
  .hd-workspace { max-height: none; }
}
</style>
