<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiFetch } from '../api'
import { useAuth } from '../composables/useAuth'

const route = useRoute()
const router = useRouter()
const { fetchUser } = useAuth()

const activeTab = ref(route.query.tab || 'courses') // 'courses' or 'materials' or 'ai_routes'

watch(() => route.query.tab, (newTab) => {
  if (newTab) {
    activeTab.value = newTab
  }
})

const changeTab = (tab) => {
  activeTab.value = tab
  router.push({ query: { ...route.query, tab } })
}

// --- AI Routes State ---
const activeRouteTab = ref('static')
const aiRoutes = ref([])
const dynamicRoutes = ref([])

// --- Pagination & Filters for Dynamic Routes ---
const dynamicSearch = ref('')
const dynamicTypeFilter = ref('all')
const dynamicCurrentPage = ref(1)
const dynamicItemsPerPage = ref(10)

const filteredDynamicRoutes = computed(() => {
  let result = dynamicRoutes.value
  
  if (dynamicTypeFilter.value !== 'all') {
    result = result.filter(r => r.type === dynamicTypeFilter.value)
  }
  
  if (dynamicSearch.value.trim()) {
    const q = dynamicSearch.value.toLowerCase()
    result = result.filter(r => 
      (r.identifier && r.identifier.toLowerCase().includes(q)) || 
      (r.title && r.title.toLowerCase().includes(q))
    )
  }
  
  return result
})

const dynamicTotalPages = computed(() => {
  return Math.ceil(filteredDynamicRoutes.value.length / dynamicItemsPerPage.value) || 1
})

const paginatedDynamicRoutes = computed(() => {
  const start = (dynamicCurrentPage.value - 1) * dynamicItemsPerPage.value
  const end = start + dynamicItemsPerPage.value
  return filteredDynamicRoutes.value.slice(start, end)
})

watch([dynamicSearch, dynamicTypeFilter], () => {
  dynamicCurrentPage.value = 1
})

const dynamicPageInput = ref(dynamicCurrentPage.value)

watch(dynamicCurrentPage, (newVal) => {
  dynamicPageInput.value = newVal
})

const leftPages = computed(() => {
  const pages = []
  const start = Math.max(1, dynamicCurrentPage.value - 3)
  for (let i = start; i < dynamicCurrentPage.value; i++) {
    pages.push(i)
  }
  return pages
})

const rightPages = computed(() => {
  const pages = []
  const end = Math.min(dynamicTotalPages.value, dynamicCurrentPage.value + 3)
  for (let i = dynamicCurrentPage.value + 1; i <= end; i++) {
    pages.push(i)
  }
  return pages
})

const goToPage = () => {
  let p = parseInt(dynamicPageInput.value)
  if (isNaN(p)) {
    dynamicPageInput.value = dynamicCurrentPage.value
    return
  }
  if (p < 1) p = 1
  if (p > dynamicTotalPages.value) p = dynamicTotalPages.value
  
  dynamicCurrentPage.value = p
  dynamicPageInput.value = p
}

const showCreateRouteModal = ref(false)
const newRoute = ref({
  identifier: '',
  title: '',
  description: ''
})// --- Courses State ---
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
  await fetchAiRoutes()
  await fetchDynamicRoutes()
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

// --- AI Routes Logic ---
const isEditingRoute = ref(false)

const formatAccessRoles = (roles) => {
  if (!roles || roles.length === 0) return 'Никто'
  if (roles.includes('all')) return 'Все'
  if (roles.includes('student') && roles.includes('teacher') && roles.includes('admin')) return 'Все'
  
  const map = {
    'student': 'Студенты',
    'teacher': 'Учителя',
    'admin': 'Админы'
  }
  return roles.map(r => map[r] || r).join(', ')
}

const fetchAiRoutes = async () => {
  try {
    aiRoutes.value = await apiFetch(`/navigation/custom-nodes?t=${Date.now()}`)
  } catch (err) {
    console.error('Ошибка загрузки ИИ маршрутов:', err)
  }
}

const fetchDynamicRoutes = async () => {
  try {
    dynamicRoutes.value = await apiFetch(`/navigation/dynamic-nodes?t=${Date.now()}`)
  } catch (err) {
    console.error('Ошибка загрузки динамических маршрутов:', err)
  }
}

const openCreateRouteModal = () => {
  isEditingRoute.value = false
  newRoute.value = { id: null, identifier: '/', title: '', description: '', allowed_roles: ['student', 'teacher', 'admin'] }
  showCreateRouteModal.value = true
}

const openEditRouteModal = (route) => {
  isEditingRoute.value = true
  let roles = route.allowed_roles ? [...route.allowed_roles] : ['student', 'teacher', 'admin']
  if (roles.includes('all') || roles.length === 0) {
    roles = ['student', 'teacher', 'admin']
  }
  newRoute.value = {
    id: route.id,
    identifier: route.identifier,
    title: route.title,
    description: route.description || '',
    allowed_roles: roles
  }
  showCreateRouteModal.value = true
}

const filterRoutePath = () => {
  if (!newRoute.value.identifier) return
  let val = newRoute.value.identifier.toLowerCase()
  val = val.replace(/[^a-z0-9\-_/]/g, '')
  if (!val.startsWith('/')) {
    val = '/' + val
  }
  newRoute.value.identifier = val
}

const saveAiRoute = async () => {
  if (!newRoute.value.allowed_roles || newRoute.value.allowed_roles.length === 0) {
    alert('Необходимо выбрать хотя бы одну роль для доступа к маршруту')
    return
  }
  try {
    const payload = {
      identifier: newRoute.value.identifier,
      title: newRoute.value.title,
      description: newRoute.value.description || '',
      allowed_roles: newRoute.value.allowed_roles
    }
    if (isEditingRoute.value) {
      await apiFetch(`/navigation/custom-nodes/${newRoute.value.id}`, {
        method: 'PUT',
        body: JSON.stringify(payload)
      })
    } else {
      await apiFetch('/navigation/custom-nodes', {
        method: 'POST',
        body: JSON.stringify(payload)
      })
    }
    showCreateRouteModal.value = false
    await fetchUser(true)
    await fetchAiRoutes()
  } catch (err) {
    alert(err.message || 'Ошибка сохранения маршрута')
  }
}

const deleteAiRoute = async (id) => {
  if (!confirm('Удалить этот маршрут из ИИ?')) return
  try {
    await apiFetch(`/navigation/custom-nodes/${id}`, { method: 'DELETE' })
    await fetchUser(true)
    await fetchAiRoutes()
  } catch (err) {
    alert(err.message || 'Ошибка удаления')
  }
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
        <button :class="['nav-btn', { active: activeTab === 'courses' }]" @click="changeTab('courses')">
          📚 Курсы
        </button>
        <button :class="['nav-btn', { active: activeTab === 'materials' }]" @click="changeTab('materials')">
          📄 Методички
        </button>
        <button :class="['nav-btn', { active: activeTab === 'ai_routes' }]" @click="changeTab('ai_routes')">
          🤖 ИИ Маршруты
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
                  <button class="btn-ghost-sm" @click="selectedCourse = c.id; changeTab('materials'); fetchMaterials()">Материалы</button>
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

    <!-- ТАБ: ИИ МАРШРУТЫ -->
    <div v-if="activeTab === 'ai_routes'" class="tab-pane">
      <div class="page-header">
        <div>
          <h1>ИИ Маршруты</h1>
          <p class="subtitle">Управление системными страницами для графа навигации ИИ (матрица инцидентности)</p>
        </div>
        <button v-if="activeRouteTab === 'static'" class="btn-primary" @click="openCreateRouteModal">+ Добавить маршрут</button>
      </div>

      <div class="route-tabs">
        <button :class="['route-tab', { active: activeRouteTab === 'static' }]" @click="activeRouteTab = 'static'">Статические (Редактируемые)</button>
        <button :class="['route-tab', { active: activeRouteTab === 'dynamic' }]" @click="activeRouteTab = 'dynamic'">Динамические (Синхронизированные)</button>
      </div>

      <div class="card" v-if="activeRouteTab === 'static'">
        <table class="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>URL (Identifier)</th>
              <th>Название</th>
              <th>Описание (для ИИ)</th>
              <th width="100">Доступ</th>
              <th width="100">Действия</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in aiRoutes" :key="r.id">
              <td class="text-muted">{{ r.id }}</td>
              <td class="font-medium">{{ r.identifier }}</td>
              <td>{{ r.title }}</td>
              <td class="text-muted">{{ r.description || '-' }}</td>
              <td><span class="badge">{{ formatAccessRoles(r.allowed_roles) }}</span></td>
              <td style="display: flex; gap: 8px;">
                <button @click="openEditRouteModal(r)" class="btn-ghost-sm">Изменить</button>
                <button @click="deleteAiRoute(r.id)" class="btn-danger-sm" :disabled="r.identifier === '/'">Удалить</button>
              </td>
            </tr>
            <tr v-if="aiRoutes.length === 0">
              <td colspan="5" class="empty-state">Нет кастомных маршрутов</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card" v-if="activeRouteTab === 'dynamic'">
        <div class="filters-bar" style="display: flex; gap: 16px; margin-bottom: 16px;">
          <input type="text" v-model="dynamicSearch" placeholder="Поиск по URL или названию..." class="input-field" style="flex: 1;" />
          <select v-model="dynamicTypeFilter" class="input-field" style="width: 200px;">
            <option value="all">Все типы</option>
            <option value="course">Курс</option>
            <option value="lesson">Урок</option>
            <option value="action">Действие</option>
          </select>
        </div>

        <table class="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Тип</th>
              <th>URL (Identifier)</th>
              <th>Название</th>
              <th>Описание (для ИИ)</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in paginatedDynamicRoutes" :key="r.id">
              <td class="text-muted">{{ r.id }}</td>
              <td><span class="badge">{{ r.type }}</span></td>
              <td class="font-medium">{{ r.identifier }}</td>
              <td>{{ r.title }}</td>
              <td class="text-muted">{{ r.description || '-' }}</td>
            </tr>
            <tr v-if="paginatedDynamicRoutes.length === 0">
              <td colspan="5" class="empty-state">Маршруты не найдены</td>
            </tr>
          </tbody>
        </table>

        <div class="pagination-advanced" style="display: flex; justify-content: center; align-items: center; gap: 8px; margin-top: 24px;" v-if="dynamicTotalPages > 1">
          <button class="page-square" :disabled="dynamicCurrentPage === 1" @click="dynamicCurrentPage--">‹</button>
          
          <button class="page-square" v-for="p in leftPages" :key="p" @click="dynamicCurrentPage = p">{{ p }}</button>
          
          <input type="text" class="page-square active-page-input" v-model="dynamicPageInput" @blur="goToPage" @keydown.enter="goToPage" />
          
          <button class="page-square" v-for="p in rightPages" :key="p" @click="dynamicCurrentPage = p">{{ p }}</button>
          
          <button class="page-square" :disabled="dynamicCurrentPage === dynamicTotalPages" @click="dynamicCurrentPage++">›</button>
        </div>
      </div>
    </div>
  </div> <!-- Closes admin-content -->

  <!-- Модалка: Создание/Редактирование ИИ Маршрута -->
  <div v-if="showCreateRouteModal" class="modal-overlay" @click.self="showCreateRouteModal = false">
    <div class="modal-content">
      <div class="modal-header">
        <h2>{{ isEditingRoute ? 'Редактировать маршрут' : 'Добавить ИИ Маршрут' }}</h2>
        <button class="close-btn" @click="showCreateRouteModal = false">×</button>
      </div>
      <form @submit.prevent="saveAiRoute" class="modal-body form-stack">
        <div class="form-group">
          <label>URL путь (например: /achievements)</label>
          <input type="text" v-model="newRoute.identifier" @input="filterRoutePath" required placeholder="/path" class="input-field" />
        </div>
        <div class="form-group">
          <label>Название (для пользователя)</label>
          <input type="text" v-model="newRoute.title" required placeholder="Достижения" class="input-field" />
        </div>
        <div class="form-group">
          <label>Описание (смысл страницы для ИИ)</label>
          <textarea v-model="newRoute.description" placeholder="Здесь студент может посмотреть свои кубки и рейтинг..." class="input-field"></textarea>
        </div>
        <div class="form-group">
          <label>Доступ к маршруту</label>
          <div class="checkbox-group">
            <label class="checkbox-label">
              <input type="checkbox" v-model="newRoute.allowed_roles" value="student" class="checkbox-input">
              Студенты
            </label>
            <label class="checkbox-label">
              <input type="checkbox" v-model="newRoute.allowed_roles" value="teacher" class="checkbox-input">
              Преподаватели
            </label>
            <label class="checkbox-label">
              <input type="checkbox" v-model="newRoute.allowed_roles" value="admin" class="checkbox-input">
              Администраторы
            </label>
          </div>
        </div>
        <div class="modal-actions">
          <button type="button" class="btn-ghost" @click="showCreateRouteModal = false">Отмена</button>
          <button type="submit" class="btn-primary">{{ isEditingRoute ? 'Сохранить изменения' : 'Сохранить в граф' }}</button>
        </div>
      </form>
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
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}
.modal-header h2 { margin: 0; }
.close-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 24px;
  cursor: pointer;
  line-height: 1;
  padding: 4px;
  border-radius: 4px;
}
.close-btn:hover {
  color: var(--text);
  background: var(--bg-elevated);
}

/* Route Tabs */
.route-tabs {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 8px;
}
.route-tab {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  padding: 8px 16px;
  border-radius: 8px;
  transition: all 0.2s;
}
.route-tab:hover {
  color: var(--text);
  background: var(--bg-elevated);
}
.route-tab.active {
  color: var(--text);
  background: var(--bg-elevated);
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}
.badge {
  background: var(--bg-elevated);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
  text-transform: uppercase;
  border: 1px solid var(--border);
}

/* Pagination Advanced */
.page-square {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg-elevated);
  color: var(--text);
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  padding: 0;
}
.page-square:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
}
.page-square:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.active-page-input {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
  text-align: center;
  font-weight: bold;
}
.active-page-input:hover {
  background: var(--accent);
  color: white;
}
.active-page-input:focus {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

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

/* Custom Styled Checkboxes */
.checkbox-group {
  display: flex;
  gap: 20px;
  margin-top: 8px;
}
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: var(--text);
  font-size: 14px;
  user-select: none;
  font-weight: 500;
}
.checkbox-input {
  appearance: none;
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--bg-elevated);
  cursor: pointer;
  display: inline-grid;
  place-content: center;
  transition: all 0.2s ease;
  flex-shrink: 0;
  margin: 0;
}
.checkbox-input:hover {
  border-color: var(--accent);
  box-shadow: 0 0 8px rgba(99, 102, 241, 0.2);
}
.checkbox-input::before {
  content: "";
  width: 10px;
  height: 10px;
  transform: scale(0);
  transition: 120ms transform ease-in-out;
  background-color: currentColor;
  clip-path: polygon(14% 44%, 0 65%, 50% 100%, 100% 16%, 80% 0%, 43% 62%);
}
.checkbox-input:checked {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
.checkbox-input:checked::before {
  transform: scale(1);
}
.checkbox-input:focus {
  outline: 2px solid var(--accent-subtle);
  outline-offset: 2px;
}
</style>
