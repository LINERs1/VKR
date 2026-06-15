<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="not-found-container">
    <div class="content-wrapper">
      <div class="icon-pulse">
        <!-- SVG Cat Icon -->
        <svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="cat-icon">
          <path d="M12 5c.67 0 1.35.09 2 .26 1.78-2 5.03-2.84 6.42-2.26 1.4.58-.42 7-.42 7 .57 1.07 1 2.24 1 3.44C21 17.9 16.97 21 12 21s-9-3-9-7.56c0-1.25.5-2.4 1.1-3.48 0 0-1.89-6.42-.5-7 1.39-.58 4.72.23 6.5 2.23A9.04 9.04 0 0 1 12 5Z"/>
          <path d="M8 14v.5"/>
          <path d="M16 14v.5"/>
          <path d="M11.25 16.25h1.5L12 17l-.75-.75Z"/>
        </svg>
      </div>
      <h1 class="error-code">404</h1>
      <h2 class="error-title">Упс! Страница не найдена</h2>
      <p class="error-desc">
        Похоже, наш искусственный интеллект (или кот) забрел куда-то не туда.<br>
        Маршрут, который вы ищете, был перемещен или никогда не существовал.
      </p>
      <div class="actions">
        <button @click="router.back()" class="btn-ghost">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="m12 19-7-7 7-7"/>
            <path d="M19 12H5"/>
          </svg>
          Назад
        </button>
        <button @click="router.push('/')" class="btn-primary">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
            <polyline points="9 22 9 12 15 12 15 22"/>
          </svg>
          На главную
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.not-found-container {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 80vh;
  text-align: center;
  padding: 2rem;
}

.content-wrapper {
  max-width: 500px;
  animation: slideUp 0.5s cubic-bezier(0.16, 1, 0.3, 1);
}

.icon-pulse {
  display: inline-block;
  margin-bottom: 1rem;
  color: var(--accent-color, #6366f1);
  animation: float 4s ease-in-out infinite;
}

.cat-icon {
  filter: drop-shadow(0 10px 15px rgba(99, 102, 241, 0.2));
}

.error-code {
  font-size: 6rem;
  font-weight: 800;
  line-height: 1;
  background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin: 0;
}

.error-title {
  font-size: 1.75rem;
  color: var(--text-color, #1f2937);
  margin-top: 0.5rem;
  margin-bottom: 1rem;
}

.error-desc {
  color: var(--text-muted, #6b7280);
  font-size: 1.1rem;
  line-height: 1.6;
  margin-bottom: 2rem;
}

.actions {
  display: flex;
  gap: 1rem;
  justify-content: center;
}

.btn-primary, .btn-ghost {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  border-radius: 9999px;
  font-weight: 500;
  transition: all 0.2s ease;
  cursor: pointer;
}

.btn-primary {
  background: var(--accent-color, #6366f1);
  color: white;
  border: none;
}

.btn-primary:hover {
  background: var(--accent-hover, #4f46e5);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

.btn-ghost {
  background: transparent;
  color: var(--text-color, #374151);
  border: 1px solid #e5e7eb;
}

.btn-ghost:hover {
  background: #f3f4f6;
  transform: translateY(-2px);
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes float {
  0% { transform: translateY(0px); }
  50% { transform: translateY(-10px); }
  100% { transform: translateY(0px); }
}
</style>
