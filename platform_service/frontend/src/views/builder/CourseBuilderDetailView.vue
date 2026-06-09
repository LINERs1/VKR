<template>
  <div class="max-w-5xl mx-auto py-8 px-4 sm:px-6 lg:px-8 fade-in" v-if="course">
    <!-- Header with Breadcrumb -->
    <div class="flex items-center gap-4 mb-8">
      <router-link to="/builder/courses" class="p-2 bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white rounded-xl transition-colors">
        <span class="material-icons">arrow_back</span>
      </router-link>
      <div>
        <div class="flex items-center gap-2 text-sm text-gray-400 mb-1">
          <router-link to="/builder/courses" class="hover:text-white transition-colors">Конструктор</router-link>
          <span class="material-icons text-[14px]">chevron_right</span>
          <span>{{ course.id }}</span>
        </div>
        <h1 class="text-3xl font-bold text-white flex items-center gap-3">
          <span class="material-icons text-blue-400" :style="{ color: course.color }">{{ course.icon || 'school' }}</span>
          {{ course.title }}
        </h1>
      </div>
      
      <div class="ml-auto flex items-center gap-3">
        <button
          @click="deleteCourse"
          class="px-4 py-2 border border-red-500/30 text-red-400 hover:bg-red-500/10 rounded-xl font-medium transition-colors"
        >
          Удалить курс
        </button>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <!-- Course Settings Sidebar -->
      <div class="lg:col-span-1 space-y-6">
        <div class="bg-gray-800/50 border border-gray-700/50 rounded-2xl p-6">
          <h2 class="text-xl font-bold text-white mb-6">Настройки курса</h2>
          
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-400 mb-1">Название</label>
              <input v-model="course.title" type="text" class="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2.5 text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500" />
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-400 mb-1">Описание</label>
              <textarea v-model="course.description" rows="4" class="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2 text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"></textarea>
            </div>

            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-400 mb-1">Иконка (Material)</label>
                <input v-model="course.icon" type="text" class="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2 text-white" />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-400 mb-1">Цвет (HEX)</label>
                <div class="flex gap-2">
                  <input v-model="course.color" type="color" class="w-10 h-10 rounded cursor-pointer bg-transparent border-0 p-0" />
                  <input v-model="course.color" type="text" class="w-full bg-gray-900 border border-gray-700 rounded-xl px-2 py-2 text-white text-sm" />
                </div>
              </div>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-400 mb-1">Теги (через запятую)</label>
              <input v-model="tagsString" type="text" class="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2 text-white" placeholder="python, web, data" />
            </div>

            <button
              @click="saveCourse"
              :disabled="saving"
              class="w-full mt-4 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl font-medium transition-colors flex items-center justify-center gap-2"
            >
              <span v-if="saving" class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
              {{ saving ? 'Сохранение...' : 'Сохранить изменения' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Lessons List -->
      <div class="lg:col-span-2">
        <div class="bg-gray-800/50 border border-gray-700/50 rounded-2xl p-6">
          <div class="flex items-center justify-between mb-6">
            <div>
              <h2 class="text-xl font-bold text-white">Уроки</h2>
              <p class="text-sm text-gray-400">Учебные материалы курса</p>
            </div>
            <button
              @click="createLesson"
              class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-xl font-medium transition-colors flex items-center gap-2 text-sm"
            >
              <span class="material-icons text-[18px]">add</span>
              Добавить урок
            </button>
          </div>

          <div v-if="!course.lessons || course.lessons.length === 0" class="text-center py-12 bg-gray-900/50 rounded-xl border border-dashed border-gray-700">
            <span class="material-icons text-gray-500 text-4xl mb-2">article</span>
            <p class="text-gray-400 mb-4">В этом курсе пока нет уроков</p>
            <button @click="createLesson" class="text-blue-400 hover:text-blue-300 font-medium">Создать первый урок</button>
          </div>

          <div v-else class="space-y-3">
            <div
              v-for="(lesson, index) in course.lessons"
              :key="lesson.id"
              class="flex items-center bg-gray-900 border border-gray-700 rounded-xl p-4 hover:border-gray-500 transition-colors group cursor-pointer"
              @click="editLesson(lesson.id)"
            >
              <div class="w-8 h-8 rounded bg-gray-800 text-gray-400 flex items-center justify-center font-medium mr-4 flex-shrink-0">
                {{ index + 1 }}
              </div>
              <div class="flex-grow min-w-0">
                <h3 class="text-white font-medium truncate group-hover:text-blue-400 transition-colors">{{ lesson.title }}</h3>
                <p class="text-xs text-gray-500">{{ lesson.duration || 'Время не указано' }}</p>
              </div>
              
              <div class="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity ml-4">
                <button @click.stop="deleteLesson(lesson.id)" class="p-2 text-gray-400 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors" title="Удалить">
                  <span class="material-icons text-[18px]">delete</span>
                </button>
                <span class="material-icons text-gray-500">chevron_right</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  
  <div v-else class="flex justify-center items-center py-32">
    <div class="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { coursesApi } from '../../api.js'

const route = useRoute()
const router = useRouter()
const courseId = route.params.id

const course = ref(null)
const saving = ref(false)

const tagsString = computed({
  get: () => course.value?.tags?.join(', ') || '',
  set: (val) => {
    if (course.value) {
      course.value.tags = val.split(',').map(t => t.trim()).filter(Boolean)
    }
  }
})

async function fetchCourse() {
  try {
    course.value = await coursesApi.getCourse(courseId)
  } catch (err) {
    alert('Ошибка загрузки курса: ' + err.message)
    router.push('/builder/courses')
  }
}

async function saveCourse() {
  try {
    saving.value = true
    const updateData = {
      title: course.value.title,
      description: course.value.description,
      icon: course.value.icon,
      color: course.value.color,
      tags: tagsString.value,
      duration: course.value.duration,
      instructor: course.value.instructor
    }
    const updated = await coursesApi.updateCourse(courseId, updateData)
    course.value = updated
    // Show brief success toast?
  } catch (err) {
    alert('Ошибка сохранения: ' + err.message)
  } finally {
    saving.value = false
  }
}

async function deleteCourse() {
  if (!confirm('Вы уверены, что хотите удалить этот курс? Все уроки будут удалены. Действие необратимо!')) return
  try {
    await coursesApi.deleteCourse(courseId)
    router.push('/builder/courses')
  } catch (err) {
    alert('Ошибка удаления: ' + err.message)
  }
}

function createLesson() {
  router.push(`/builder/courses/${courseId}/lessons/new`)
}

function editLesson(lessonId) {
  router.push(`/builder/courses/${courseId}/lessons/${lessonId}`)
}

async function deleteLesson(lessonId) {
  if (!confirm('Удалить этот урок?')) return
  try {
    await coursesApi.deleteLesson(courseId, lessonId)
    await fetchCourse() // refresh list
  } catch (err) {
    alert('Ошибка при удалении: ' + err.message)
  }
}

onMounted(() => {
  fetchCourse()
})
</script>
