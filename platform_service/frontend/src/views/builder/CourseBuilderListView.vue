<template>
  <div class="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8 fade-in">
    <div class="flex flex-col sm:flex-row sm:items-center justify-between mb-8">
      <div>
        <h1 class="text-4xl font-extrabold text-white tracking-tight">Конструктор Курсов</h1>
        <p class="mt-2 text-lg text-gray-400">Управляйте вашими курсами и учебными материалами</p>
      </div>
      <button
        @click="showCreateModal = true"
        class="mt-4 sm:mt-0 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-medium transition-all duration-200 shadow-lg shadow-blue-500/30 flex items-center gap-2"
      >
        <span class="material-icons text-sm">add</span>
        Создать курс
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center items-center py-20">
      <div class="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-xl text-center">
      {{ error }}
    </div>

    <!-- Empty State -->
    <div v-else-if="courses.length === 0" class="text-center py-20 bg-gray-800/30 border border-gray-700/50 rounded-2xl">
      <div class="w-16 h-16 bg-gray-800 rounded-2xl flex items-center justify-center mx-auto mb-4">
        <span class="material-icons text-gray-400 text-3xl">school</span>
      </div>
      <h3 class="text-xl font-medium text-white mb-2">Нет созданных курсов</h3>
      <p class="text-gray-400 max-w-md mx-auto mb-6">Создайте свой первый курс, чтобы начать обучение студентов.</p>
    </div>

    <!-- Courses Grid -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <div
        v-for="course in courses"
        :key="course.id"
        class="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-2xl p-6 flex flex-col hover:border-gray-600 transition-all cursor-pointer group"
        @click="goToCourse(course.id)"
      >
        <div class="flex items-center gap-4 mb-4">
          <div class="w-12 h-12 rounded-xl flex items-center justify-center shadow-lg" :style="{ backgroundColor: course.color + '20', color: course.color }">
            <span class="material-icons">{{ course.icon || 'school' }}</span>
          </div>
          <div>
            <h3 class="text-lg font-bold text-white group-hover:text-blue-400 transition-colors">{{ course.title }}</h3>
            <p class="text-sm text-gray-400">{{ course.id }}</p>
          </div>
        </div>
        
        <p class="text-gray-400 text-sm mb-6 line-clamp-2 flex-grow">{{ course.description }}</p>
        
        <div class="flex items-center justify-between mt-auto pt-4 border-t border-gray-700/50 text-sm">
          <div class="flex items-center gap-2 text-gray-400">
            <span class="material-icons text-base">menu_book</span>
            <span>{{ course.lessons_count || 0 }} уроков</span>
          </div>
          <div class="flex gap-2">
            <button @click.stop="editCourse(course.id)" class="p-2 hover:bg-gray-700 rounded-lg text-gray-300 hover:text-white transition-colors" title="Настроить">
              <span class="material-icons text-sm">settings</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Create Course Modal -->
    <div v-if="showCreateModal" class="fixed inset-0 z-50 flex items-center justify-center px-4 bg-black/60 backdrop-blur-sm">
      <div class="bg-gray-900 border border-gray-700 rounded-2xl p-6 w-full max-w-md shadow-2xl">
        <h3 class="text-xl font-bold text-white mb-4">Новый курс</h3>
        
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-400 mb-1">ID курса (англ. без пробелов)</label>
            <input
              v-model="newCourse.id"
              type="text"
              class="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              placeholder="например: python-basics"
            />
          </div>
          
          <div>
            <label class="block text-sm font-medium text-gray-400 mb-1">Название курса</label>
            <input
              v-model="newCourse.title"
              type="text"
              class="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              placeholder="Основы Python"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-400 mb-1">Краткое описание</label>
            <textarea
              v-model="newCourse.description"
              rows="3"
              class="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2 text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              placeholder="Чему научатся студенты?"
            ></textarea>
          </div>
        </div>

        <div class="mt-8 flex justify-end gap-3">
          <button
            @click="showCreateModal = false"
            class="px-4 py-2 rounded-xl text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
          >
            Отмена
          </button>
          <button
            @click="handleCreateCourse"
            :disabled="!newCourse.id || !newCourse.title || creating"
            class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-medium transition-colors flex items-center gap-2"
          >
            <span v-if="creating" class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
            Создать
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { coursesApi } from '../../api.js'

const router = useRouter()
const courses = ref([])
const loading = ref(true)
const error = ref(null)

const showCreateModal = ref(false)
const creating = ref(false)
const newCourse = ref({
  id: '',
  title: '',
  description: '',
  icon: 'school',
  color: '#3b82f6',
})

async function fetchCourses() {
  try {
    loading.value = true
    // Currently fetching all courses. A real implementation might filter by instructor
    courses.value = await coursesApi.getCourses()
  } catch (err) {
    error.value = err.message || 'Ошибка загрузки курсов'
  } finally {
    loading.value = false
  }
}

async function handleCreateCourse() {
  try {
    creating.value = true
    const created = await coursesApi.createCourse(newCourse.value)
    courses.value.push(created)
    showCreateModal.value = false
    // Reset form
    newCourse.value = { id: '', title: '', description: '', icon: 'school', color: '#3b82f6' }
    router.push(`/builder/courses/${created.id}`)
  } catch (err) {
    alert('Ошибка при создании курса: ' + (err.message || err))
  } finally {
    creating.value = false
  }
}

function goToCourse(id) {
  router.push(`/builder/courses/${id}`)
}

function editCourse(id) {
  router.push(`/builder/courses/${id}`)
}

onMounted(() => {
  fetchCourses()
})
</script>
