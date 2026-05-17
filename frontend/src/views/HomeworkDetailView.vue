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
      <!-- Информация о задании -->
      <aside class="hw-info panel">
        <h2>{{ hw.title }}</h2>
        <div class="desc-box">{{ hw.description }}</div>
        
        <!-- Если студент, показываем статус и фидбэк -->
        <div v-if="!isTeacher && myAssignment" class="my-status">
          <div class="status-badge" :class="myAssignment.status">
            {{ formatStatus(myAssignment.status) }}
          </div>
          <div v-if="myAssignment.grade" class="grade-box">
            Оценка: <strong>{{ myAssignment.grade }} / 5</strong>
          </div>
          <div v-if="myAssignment.teacher_feedback" class="feedback-box">
            <h4>Отзыв преподавателя:</h4>
            <p>{{ myAssignment.teacher_feedback }}</p>
          </div>
        </div>

        <!-- Если препод, показываем список студентов слева -->
        <div v-if="isTeacher" class="students-list">
          <h3>Сдавшие ученики:</h3>
          <div 
            v-for="a in hw.assignments" 
            :key="a.id"
            class="student-item"
            :class="{ active: selectedAssignment?.id === a.id }"
            @click="selectedAssignment = a"
          >
            <div>{{ a.student_name }}</div>
            <div class="status-badge small" :class="a.status">{{ formatStatus(a.status) }}</div>
          </div>
        </div>
      </aside>

      <!-- Рабочая область -->
      <main class="workspace panel">
        <!-- ВЬЮ ДЛЯ СТУДЕНТА -->
        <div v-if="!isTeacher && myAssignment">
          <div v-if="myAssignment.status === 'pending'">
            <h3>Ваше решение</h3>
            <div class="form-group">
              <label>Напишите код (если требуется)</label>
              <textarea v-model="submitData.student_code" rows="10" class="code-font" placeholder="def hello():..."></textarea>
            </div>
            <div class="form-group">
              <label>Текстовый ответ / определение</label>
              <textarea v-model="submitData.student_text" rows="5" placeholder="Ответ на теоретический вопрос..."></textarea>
            </div>
            <button class="action-btn" @click="handleSubmit" :disabled="submitting">
              {{ submitting ? 'Отправка...' : 'Отправить на проверку' }}
            </button>
          </div>
          <div v-else>
            <h3>Ваш отправленный ответ</h3>
            <div class="readonly-box">
              <pre><code>{{ myAssignment.student_code }}</code></pre>
            </div>
            <div class="readonly-box text-box">
              {{ myAssignment.student_text }}
            </div>
          </div>
        </div>

        <!-- ВЬЮ ДЛЯ ПРЕПОДАВАТЕЛЯ -->
        <div v-if="isTeacher">
          <div v-if="!selectedAssignment" class="empty-state">
            Выберите ученика слева для проверки задания
          </div>
          <div v-else>
            <h3>Ответ ученика: {{ selectedAssignment.student_name }}</h3>
            <div class="readonly-box">
              <h4>Код:</h4>
              <pre><code>{{ selectedAssignment.student_code || 'Нет кода' }}</code></pre>
            </div>
            <div class="readonly-box text-box">
              <h4>Текст:</h4>
              <p>{{ selectedAssignment.student_text || 'Нет текста' }}</p>
            </div>

            <div class="grading-section" v-if="selectedAssignment.status === 'submitted'">
              <h3>Оценка и отзыв</h3>
              <div class="form-group">
                <label>Оценка (1-5)</label>
                <select v-model="gradeData.grade">
                  <option :value="5">5 - Отлично</option>
                  <option :value="4">4 - Хорошо</option>
                  <option :value="3">3 - Удовлетворительно</option>
                  <option :value="2">2 - Неудовлетворительно</option>
                  <option :value="1">1 - Ужасно</option>
                </select>
              </div>
              <div class="form-group">
                <label>Отзыв</label>
                <textarea v-model="gradeData.teacher_feedback" rows="4" placeholder="Напишите комментарий... (можете спросить ИИ в чате)"></textarea>
              </div>
              <button class="action-btn" @click="handleGrade" :disabled="grading">
                Оценить
              </button>
            </div>
            <div v-else-if="selectedAssignment.status === 'graded'" class="already-graded">
              <h4>Уже оценено: {{ selectedAssignment.grade }}</h4>
              <p>{{ selectedAssignment.teacher_feedback }}</p>
            </div>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'
import { hwApi } from '../api'

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

// Для студента
const submitData = ref({ student_code: '', student_text: '' })
const submitting = ref(false)

// Для препода
const gradeData = ref({ grade: 5, teacher_feedback: '' })
const grading = ref(false)

onMounted(async () => {
  user.value = await fetchUser()
  if (!user.value) return router.push('/login')

  await loadHomework()
})

async function loadHomework() {
  try {
    hw.value = await hwApi.getHomework(route.params.id)
    // Глобально сохраняем контекст для ИИ-ассистента (GlobalAssistant прочитает из localStorage или window)
    window.currentHomeworkContext = {
      courseId: hw.value.course_id,
      title: hw.value.title,
      desc: hw.value.description
    }
  } catch (e) {
    alert('Не удалось загрузить ДЗ: ' + e.message)
    router.push('/homeworks')
  }
}

function formatStatus(status) {
  if (status === 'pending') return 'Ожидает'
  if (status === 'submitted') return 'На проверке'
  if (status === 'graded') return 'Оценено'
  return status
}

async function handleSubmit() {
  submitting.value = true
  try {
    const updated = await hwApi.submitHomework(myAssignment.value.id, submitData.value)
    // Обновляем локально
    const idx = hw.value.assignments.findIndex(a => a.id === updated.id)
    if (idx !== -1) hw.value.assignments[idx] = updated
  } catch (e) {
    alert(e.message)
  }
  submitting.value = false
}

async function handleGrade() {
  grading.value = true
  try {
    const updated = await hwApi.gradeHomework(selectedAssignment.value.id, gradeData.value)
    // Обновляем локально
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
  background: #09090b; color: #e4e4e7;
  font-family: 'Inter', system-ui, sans-serif;
  padding: 24px;
}
.header {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px;
}
.back-btn {
  display: flex; align-items: center; gap: 8px;
  background: none; border: none; color: #a1a1aa; cursor: pointer;
}
.back-btn:hover { color: #fff; }
.course-badge { background: #27272a; padding: 6px 12px; border-radius: 8px; color: #a1a1aa; font-size: 14px; }

.layout {
  display: flex; gap: 24px;
  align-items: flex-start;
}
.panel {
  background: #18181b; border: 1px solid rgba(255,255,255,0.05);
  border-radius: 16px; padding: 24px;
}
.hw-info { width: 350px; flex-shrink: 0; }
.workspace { flex-grow: 1; min-height: 500px; }

.hw-info h2 { margin-top: 0; }
.desc-box { color: #a1a1aa; font-size: 15px; line-height: 1.6; margin-bottom: 24px; white-space: pre-wrap; }

.status-badge { display: inline-block; padding: 6px 12px; border-radius: 6px; font-size: 14px; font-weight: 600; }
.status-badge.small { padding: 4px 8px; font-size: 12px; }
.status-badge.pending { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
.status-badge.submitted { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.status-badge.graded { background: rgba(16, 185, 129, 0.15); color: #34d399; }

.grade-box { margin-top: 16px; font-size: 18px; color: #34d399; }
.feedback-box { margin-top: 16px; background: #27272a; padding: 16px; border-radius: 8px; }

.students-list { margin-top: 24px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 16px; }
.student-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px; border-radius: 8px; cursor: pointer; transition: background 0.2s;
}
.student-item:hover { background: rgba(255,255,255,0.05); }
.student-item.active { background: rgba(99,102,241,0.15); border: 1px solid rgba(99,102,241,0.3); }

.form-group { margin-bottom: 20px; }
.form-group label { display: block; margin-bottom: 8px; color: #a1a1aa; }
.form-group textarea, .form-group select {
  width: 100%; background: #09090b; border: 1px solid #3f3f46;
  color: white; padding: 12px; border-radius: 8px; font-family: inherit; resize: vertical;
}
.code-font { font-family: 'Fira Code', 'Courier New', Courier, monospace; color: #a5b4fc; }

.action-btn {
  background: #4f46e5; color: white; border: none; padding: 12px 24px;
  border-radius: 8px; cursor: pointer; font-size: 16px; font-weight: 500;
}
.action-btn:hover:not(:disabled) { background: #4338ca; }
.action-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.readonly-box { background: #09090b; border: 1px solid #27272a; border-radius: 8px; padding: 16px; margin-bottom: 20px; }
.readonly-box pre { margin: 0; white-space: pre-wrap; font-family: 'Fira Code', monospace; color: #a5b4fc; }
.text-box { color: #e4e4e7; white-space: pre-wrap; line-height: 1.5; }

.grading-section { margin-top: 40px; padding-top: 24px; border-top: 1px solid rgba(255,255,255,0.1); }
.already-graded { margin-top: 24px; padding: 20px; background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 8px; color: #34d399; }
.empty-state { text-align: center; color: #a1a1aa; margin-top: 100px; font-size: 18px; }

/* Responsive */
@media (max-width: 768px) {
  .layout { flex-direction: column; }
  .hw-info { width: 100%; }
}
</style>
