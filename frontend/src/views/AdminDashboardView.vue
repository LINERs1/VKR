<script setup>
import { ref, onMounted } from 'vue'
import { apiFetch } from '../api'

const activeTab = ref('courses') // 'courses' or 'materials'

// --- Courses State ---
const courses = ref([])
const showCreateModal = ref(false)
const newCourse = ref({
  id: '',
  title: '',
  description: '',
  icon: 'python',
  color: '#3b82f6',
  tags: '',
  duration: '10 часов',
  instructor: 'AI Assistant'
})

// --- Materials State ---
const selectedCourse = ref('')
const materials = ref([])
const fileInput = ref(null)
const uploading = ref(false)
const uploadMessage = ref('')

onMounted(async () => {
  await fetchCourses()
})

const fetchCourses = async () => {
  try {
    courses.value = await apiFetch('/courses')
    if (courses.value.length > 0 && !selectedCourse.value) {
      selectedCourse.value = courses.value[0].id
      await fetchMaterials()
    }
  } catch (err) {
    console.error('Ошибка загрузки курсов:', err)
  }
}

// --- Courses Logic ---
const openCreateModal = () => {
  newCourse.value = { id: '', title: '', description: '', icon: 'python', color: '#3b82f6', tags: '', duration: '10 часов', instructor: 'AI Assistant' }
  showCreateModal.value = true
}

const createCourse = async () => {
  try {
    const res = await apiFetch('/courses', {
      method: 'POST',
      body: JSON.stringify(newCourse.value)
    })
    showCreateModal.value = false
    await fetchCourses()
  } catch (err) {
    alert(err.message || 'Ошибка создания курса')
  }
}

// --- Materials Logic ---
const fetchMaterials = async () => {
  if (!selectedCourse.value) return
  try {
    materials.value = await apiFetch(`/materials?course_id=${selectedCourse.value}`)
  } catch (err) {
    console.error('Ошибка загрузки методичек:', err)
  }
}

const onCourseChange = async () => {
  await fetchMaterials()
}

const triggerUpload = () => {
  fileInput.value.click()
}

const handleFileUpload = async (e) => {
  const file = e.target.files[0]
  if (!file) return

  uploading.value = true
  uploadMessage.value = 'Загрузка и индексация (может занять время)...'
  
  const formData = new FormData()
  formData.append('file', file)
  formData.append('course_id', selectedCourse.value)
  formData.append('source_type', 'methodology')

  try {
    const token = localStorage.getItem('eduai_token')
    const res = await fetch('/api/materials', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      },
      body: formData
    })

    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || 'Ошибка загрузки')
    }

    uploadMessage.value = 'Методичка успешно загружена и проиндексирована!'
    setTimeout(() => { uploadMessage.value = '' }, 3000)
    await fetchMaterials()
  } catch (err) {
    alert(err.message)
    uploadMessage.value = ''
  } finally {
    uploading.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

const deleteMaterial = async (id) => {
  if (!confirm('Удалить эту методичку? Она также исчезнет из базы знаний ИИ.')) return

  try {
    await apiFetch(`/materials/${id}`, { method: 'DELETE' })
    await fetchMaterials()
  } catch (err) {
    alert('Ошибка при удалении')
  }
}

const formatDate = (ds) => {
  if (!ds) return ''
  return new Date(ds).toLocaleString('ru-RU')
}
</script>

<template>
  <div class="admin-page">
    <div class="admin-sidebar">
      <div class="sidebar-brand">
        <div class="brand-mark">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path d="M12 2L2 7l10 5 10-5-10-5z" fill="currentColor"/>
          </svg>
        </div>
        <span>EduAI Admin</span>
      </div>
      <nav class="sidebar-nav">
        <button :class="['nav-btn', { active: activeTab === 'courses' }]" @click="activeTab = 'courses'">
          📚 Курсы
        </button>
        <button :class="['nav-btn', { active: activeTab === 'materials' }]" @click="activeTab = 'materials'">
          📄 Методички
        </button>
        <div class="nav-divider"></div>
        <router-link to="/" class="nav-btn back-btn">← На главную</router-link>
      </nav>
    </div>

    <div class="admin-content">
      <!-- ТАБ: КУРСЫ -->
      <div v-if="activeTab === 'courses'" class="tab-pane">
        <div class="page-header">
          <div>
            <h1>Управление курсами</h1>
            <p class="subtitle">Создание и редактирование учебных курсов</p>
          </div>
          <button class="btn-primary" @click="openCreateModal">+ Создать курс</button>
        </div>

        <div class="card">
          <table class="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Название</th>
                <th>Уроков</th>
                <th>Студентов</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in courses" :key="c.id">
                <td class="text-muted">{{ c.id }}</td>
                <td class="font-medium">{{ c.title }}</td>
                <td>{{ c.lessons_count }}</td>
                <td>{{ c.students }}</td>
                <td>
                  <button class="btn-ghost-sm" @click="selectedCourse = c.id; activeTab = 'materials'; fetchMaterials()">Материалы</button>
                </td>
              </tr>
              <tr v-if="courses.length === 0">
                <td colspan="5" class="empty-state">Нет курсов</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ТАБ: МЕТОДИЧКИ -->
      <div v-if="activeTab === 'materials'" class="tab-pane">
        <div class="page-header">
          <div>
            <h1>Методические материалы</h1>
            <p class="subtitle">База знаний для RAG-ассистента</p>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <h3>Курс:</h3>
            <select v-model="selectedCourse" @change="onCourseChange" class="select-box">
              <option v-for="c in courses" :key="c.id" :value="c.id">{{ c.title }}</option>
            </select>
          </div>

          <div class="materials-list">
            <div v-if="materials.length === 0" class="empty-state">
              В этом курсе пока нет методичек
            </div>
            <table v-else class="table">
              <thead>
                <tr>
                  <th>Название файла</th>
                  <th>Дата загрузки</th>
                  <th width="100">Действия</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="m in materials" :key="m.id">
                  <td class="font-medium">📄 {{ m.title }}</td>
                  <td class="text-muted">{{ formatDate(m.created_at) }}</td>
                  <td>
                    <button @click="deleteMaterial(m.id)" class="btn-danger-sm">Удалить</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="upload-section">
            <input type="file" ref="fileInput" accept="application/pdf" @change="handleFileUpload" style="display: none" />
            <button @click="triggerUpload" class="btn-primary" :disabled="uploading">
              {{ uploading ? 'Загрузка...' : '+ Загрузить PDF методичку' }}
            </button>
            <span v-if="uploadMessage" class="upload-msg">{{ uploadMessage }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- МОДАЛКА: СОЗДАНИЕ КУРСА -->
    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal-content">
        <h2>Новый курс</h2>
        
        <div class="form-group">
          <label>ID курса (английскими, без пробелов)</label>
          <input type="text" v-model="newCourse.id" placeholder="например: python-basics" class="input-field">
        </div>

        <div class="form-group">
          <label>Название курса</label>
          <input type="text" v-model="newCourse.title" placeholder="Основы Python" class="input-field">
        </div>

        <div class="form-group">
          <label>Описание</label>
          <textarea v-model="newCourse.description" rows="3" class="input-field"></textarea>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label>Иконка (например: python, js, react)</label>
            <input type="text" v-model="newCourse.icon" class="input-field">
          </div>
          <div class="form-group">
            <label>Цвет (HEX)</label>
            <input type="color" v-model="newCourse.color" class="color-picker">
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn-ghost" @click="showCreateModal = false">Отмена</button>
          <button class="btn-primary" @click="createCourse">Создать</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-page {
  display: flex;
  min-height: 100vh;
  background: var(--bg);
}

/* Sidebar */
.admin-sidebar {
  width: 260px;
  background: var(--card);
  border-right: 1px solid var(--border);
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
}
.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 18px;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 40px;
  padding: 0 8px;
}
.brand-mark {
  width: 32px; height: 32px;
  background: var(--accent);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}
.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.nav-btn {
  background: transparent;
  border: none;
  padding: 12px 16px;
  border-radius: 8px;
  color: var(--text-secondary);
  font-size: 15px;
  font-weight: 500;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s;
  display: block;
  text-decoration: none;
}
.nav-btn:hover {
  background: var(--bg-elevated);
  color: var(--text);
}
.nav-btn.active {
  background: var(--accent-subtle);
  color: var(--accent);
  font-weight: 600;
}
.nav-divider {
  height: 1px;
  background: var(--border);
  margin: 16px 0;
}

/* Content */
.admin-content {
  flex: 1;
  padding: 40px 60px;
  overflow-y: auto;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
}
.page-header h1 {
  font-size: 28px;
  margin: 0 0 8px 0;
}
.subtitle {
  color: var(--text-muted);
  font-size: 15px;
  margin: 0;
}

/* Card & Table */
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.1);
}
.card-header {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 24px;
}
.select-box {
  padding: 10px 16px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg-elevated);
  color: var(--text);
  min-width: 300px;
  font-size: 14px;
}
.table {
  width: 100%;
  border-collapse: collapse;
}
.table th, .table td {
  padding: 16px;
  border-bottom: 1px solid var(--border-light);
  text-align: left;
}
.table th {
  color: var(--text-muted);
  font-weight: 500;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.font-medium { font-weight: 500; }
.text-muted { color: var(--text-muted); font-size: 14px; }

/* Buttons */
.btn-primary {
  background: var(--accent);
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s;
}
.btn-primary:hover:not(:disabled) { background: var(--accent-hover); }
.btn-primary:disabled { opacity: 0.7; cursor: not-allowed; }

.btn-ghost {
  background: transparent;
  color: var(--text);
  border: 1px solid var(--border);
  padding: 10px 20px;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 500;
}
.btn-ghost:hover { border-color: var(--border-light); }

.btn-ghost-sm {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
}
.btn-ghost-sm:hover { border-color: var(--border-light); }

.btn-danger-sm {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  border: 1px solid rgba(239, 68, 68, 0.2);
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
}
.btn-danger-sm:hover { background: #ef4444; color: white; }

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal-content {
  background: var(--card);
  width: 500px;
  border-radius: 16px;
  padding: 32px;
  border: 1px solid var(--border);
  box-shadow: 0 20px 40px rgba(0,0,0,0.4);
}
.modal-content h2 { margin: 0 0 24px 0; }

.form-group {
  margin-bottom: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.form-row {
  display: flex;
  gap: 16px;
}
.form-row .form-group { flex: 1; }
.form-group label {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 500;
}
.input-field {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 12px;
  border-radius: 8px;
  font-size: 14px;
}
.input-field:focus {
  border-color: var(--accent);
  outline: none;
}
.color-picker {
  height: 44px;
  width: 100%;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg-elevated);
  cursor: pointer;
  padding: 4px;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 32px;
}

/* Utils */
.upload-section {
  display: flex;
  align-items: center;
  gap: 15px;
  padding-top: 24px;
  border-top: 1px solid var(--border);
  margin-top: 24px;
}
.upload-msg {
  color: var(--accent2);
  font-size: 14px;
  font-weight: 500;
}
.empty-state {
  padding: 40px;
  text-align: center;
  color: var(--text-muted);
  background: var(--bg-raised);
  border-radius: 8px;
}
</style>
