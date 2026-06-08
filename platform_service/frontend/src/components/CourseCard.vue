<script setup>
import { useRouter } from 'vue-router'

const props = defineProps({
  course: { type: Object, required: true }
})

const router = useRouter()
</script>

<template>
  <div class="course-card" @click="router.push(`/courses/${course.id}`)">
    <div class="card-top">
      <div class="card-icon">{{ course.icon }}</div>
      <div class="card-tags">
        <span v-for="tag in course.tags.slice(0,2)" :key="tag" class="tag">{{ tag }}</span>
      </div>
    </div>
    <h3 class="card-title">{{ course.title }}</h3>
    <p class="card-desc">{{ course.description }}</p>
    <div class="card-meta">
      <span>📚 {{ course.lessons_count }} уроков</span>
      <span>⏱ {{ course.duration }}</span>
      <span>👥 {{ course.students.toLocaleString() }}</span>
    </div>
    <div class="card-footer">
      <div class="card-rating">⭐ {{ course.rating }}</div>
      <div class="card-instructor">{{ course.instructor }}</div>
      <button class="btn-start">Начать →</button>
    </div>
  </div>
</template>

<style scoped>
.course-card {
  background: rgba(17, 26, 46, 0.8);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.course-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; height: 4px;
  background: var(--accent);
  opacity: 0;
  transition: opacity 0.3s;
}

.course-card:hover {
  transform: translateY(-4px);
  border-color: rgba(124, 92, 255, 0.4);
  box-shadow: 0 12px 30px -10px rgba(0, 0, 0, 0.5), 0 0 20px rgba(124, 92, 255, 0.1);
}

.course-card:hover::before {
  opacity: 1;
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.card-icon {
  font-size: 32px;
  background: rgba(255, 255, 255, 0.05);
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
}

.card-tags {
  display: flex;
  gap: 8px;
}

.tag {
  font-size: 11px;
  padding: 4px 10px;
  background: rgba(45, 212, 191, 0.1);
  color: var(--accent2);
  border-radius: 12px;
  font-weight: 600;
}

.card-title {
  font-size: 20px;
  font-weight: 700;
  margin: 0 0 10px;
  color: var(--text);
  line-height: 1.3;
}

.card-desc {
  font-size: 14px;
  color: var(--muted);
  line-height: 1.5;
  margin: 0 0 20px;
  flex: 1;
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 24px;
  font-size: 13px;
  color: #8b96a5;
}

.card-meta span {
  display: flex;
  align-items: center;
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 20px;
  border-top: 1px solid var(--border);
}

.card-rating {
  font-weight: 600;
  font-size: 14px;
  color: #fbbf24;
}

.card-instructor {
  font-size: 13px;
  color: var(--muted);
}

.btn-start {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 8px 16px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.course-card:hover .btn-start {
  background: var(--accent);
  border-color: var(--accent);
  color: white;
}
</style>
