<template>
  <div class="max-w-5xl mx-auto py-8 px-4 sm:px-6 lg:px-8 fade-in">
    <!-- Header with Breadcrumb -->
    <div class="flex items-center gap-4 mb-8">
      <router-link :to="`/builder/courses/${courseId}`" class="p-2 bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white rounded-xl transition-colors">
        <span class="material-icons">arrow_back</span>
      </router-link>
      <div>
        <div class="flex items-center gap-2 text-sm text-gray-400 mb-1">
          <router-link to="/builder/courses" class="hover:text-white transition-colors">Конструктор</router-link>
          <span class="material-icons text-[14px]">chevron_right</span>
          <router-link :to="`/builder/courses/${courseId}`" class="hover:text-white transition-colors">{{ courseId }}</router-link>
          <span class="material-icons text-[14px]">chevron_right</span>
          <span>Урок {{ isNew ? 'создание' : lessonId }}</span>
        </div>
        <h1 class="text-3xl font-bold text-white">
          {{ isNew ? 'Новый урок' : 'Редактирование урока' }}
        </h1>
      </div>
      
      <div class="ml-auto">
        <button
          @click="saveLesson"
          :disabled="saving || !lesson.title || !lesson.content"
          class="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl font-medium shadow-lg shadow-blue-500/30 transition-colors flex items-center gap-2"
        >
          <span v-if="saving" class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
          <span class="material-icons text-[18px]">save</span>
          Сохранить
        </button>
      </div>
    </div>

    <!-- Main Editor -->
    <div class="bg-gray-800/50 border border-gray-700/50 rounded-2xl overflow-hidden flex flex-col min-h-[600px]">
      
      <!-- Top Settings Bar -->
      <div class="bg-gray-900 border-b border-gray-700 p-4 flex gap-4">
        <div class="flex-grow">
          <label class="block text-xs font-medium text-gray-400 mb-1 uppercase tracking-wider">Название урока</label>
          <input
            v-model="lesson.title"
            type="text"
            class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
            placeholder="Введение в Python"
          />
        </div>
        <div class="w-48">
          <label class="block text-xs font-medium text-gray-400 mb-1 uppercase tracking-wider">Длительность</label>
          <input
            v-model="lesson.duration"
            type="text"
            class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
            placeholder="15 минут"
          />
        </div>
      </div>

      <!-- Editor Content -->
      <div class="flex flex-grow">
        <textarea
          v-model="lesson.content"
          class="w-full h-full min-h-[500px] bg-gray-900/50 border-0 p-6 text-white font-mono text-sm focus:outline-none resize-none leading-relaxed"
          placeholder="# Название темы\n\nЗдесь можно писать текст в формате Markdown.\n\n- Пункт 1\n- Пункт 2\n\n```python\nprint('Hello World')\n```"
        ></textarea>
      </div>
    </div>
    <p class="text-xs text-gray-500 mt-4 text-center">Контент поддерживает форматирование Markdown. При сохранении урок автоматически отправляется в базу знаний ИИ.</p>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { coursesApi } from '../../api.js'

const route = useRoute()
const router = useRouter()
const courseId = route.params.id
const lessonId = route.params.lesson_id

const isNew = computed(() => lessonId === 'new')
const saving = ref(false)

const lesson = ref({
  title: '',
  duration: '10 минут',
  content: ''
})

async function fetchLesson() {
  if (isNew.value) return
  
  try {
    const course = await coursesApi.getCourse(courseId)
    const found = course.lessons.find(l => l.id == lessonId)
    if (found) {
      lesson.value = { ...found }
    } else {
      throw new Error('Lesson not found')
    }
  } catch (err) {
    alert('Ошибка загрузки: ' + err.message)
    router.push(`/builder/courses/${courseId}`)
  }
}

async function saveLesson() {
  try {
    saving.value = true
    const payload = {
      title: lesson.value.title,
      duration: lesson.value.duration,
      content: lesson.value.content
    }
    
    if (isNew.value) {
      await coursesApi.createLesson(courseId, payload)
    } else {
      await coursesApi.updateLesson(courseId, lessonId, payload)
    }
    
    // Go back to course after saving
    router.push(`/builder/courses/${courseId}`)
  } catch (err) {
    alert('Ошибка при сохранении урока: ' + err.message)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  fetchLesson()
})
</script>
