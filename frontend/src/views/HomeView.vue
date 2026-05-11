<script setup>
import { ref, onMounted } from 'vue'
import CourseCard from '../components/CourseCard.vue'

const courses = ref([])
const loading = ref(true)

onMounted(async () => {
  try {
    const res = await fetch('/api/courses')
    courses.value = await res.json()
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="home-page">
    <!-- HERO -->
    <section class="hero">
      <div class="hero-bg">
        <div class="hero-orb orb1"></div>
        <div class="hero-orb orb2"></div>
        <div class="hero-orb orb3"></div>
      </div>
      <nav class="home-nav">
        <div class="nav-logo">🎓 EduAI</div>
        <a href="#courses" class="nav-link">Курсы</a>
        <a href="#how" class="nav-link">Как работает</a>
        <a href="/api/health" target="_blank" class="nav-badge">API ✓</a>
      </nav>
      <div class="hero-content">
        <div class="hero-pill">
          <span class="pulse-dot"></span>
          ИИ-ассистент активен
        </div>
        <h1 class="hero-title">
          Учись быстрее<br>
          с <span class="gradient-text">голосовым ИИ</span>
        </h1>
        <p class="hero-subtitle">
          EduAI встроен в каждый курс. Задайте вопрос голосом или текстом —
          ассистент найдёт ответ в методических материалах и ответит вслух.
        </p>
        <div class="hero-actions">
          <a href="#courses" class="btn-hero-primary">Выбрать курс →</a>
          <a href="#how" class="btn-hero-ghost">Как это работает</a>
        </div>
        <div class="hero-stats">
          <div class="stat"><span class="stat-num">4</span><span class="stat-label">курса</span></div>
          <div class="stat-div"></div>
          <div class="stat"><span class="stat-num">PDF</span><span class="stat-label">Word · TXT</span></div>
          <div class="stat-div"></div>
          <div class="stat"><span class="stat-num">🎤</span><span class="stat-label">Голос + текст</span></div>
        </div>
      </div>

      <!-- Floating widget preview -->
      <div class="hero-visual">
        <div class="widget-demo">
          <div class="demo-header">
            <div class="demo-avatar">🤖</div>
            <div>
              <div class="demo-name">EduAI</div>
              <div class="demo-status">● онлайн</div>
            </div>
          </div>
          <div class="demo-msg assistant">
            <div class="demo-bubble">Привет! Я помогаю по курсу «Python для начинающих». Задайте вопрос голосом или текстом 🎤</div>
          </div>
          <div class="demo-msg user">
            <div class="demo-bubble">Что такое f-строки в Python?</div>
          </div>
          <div class="demo-msg assistant">
            <div class="demo-bubble">F-строки — это способ форматирования строк: <code>f"Привет, {name}!"</code> Значение переменной подставляется прямо в строку.</div>
            <div class="demo-sources">📄 02_variables.txt</div>
          </div>
          <div class="demo-input-row">
            <div class="demo-input">Задайте вопрос…</div>
            <button class="demo-mic">🎤</button>
          </div>
        </div>
      </div>
    </section>

    <!-- HOW IT WORKS -->
    <section id="how" class="how-section">
      <div class="section-inner">
        <div class="section-label">Принцип работы</div>
        <h2 class="section-title">Три шага до ответа</h2>
        <div class="steps-row">
          <div class="step-card">
            <div class="step-num">01</div>
            <div class="step-icon">📚</div>
            <h3>Загрузи материалы</h3>
            <p>Преподаватель загружает методички в любом формате: PDF, Word, TXT. Система автоматически индексирует их в векторную базу данных.</p>
          </div>
          <div class="step-arrow">→</div>
          <div class="step-card">
            <div class="step-num">02</div>
            <div class="step-icon">🎤</div>
            <h3>Задай вопрос</h3>
            <p>Студент нажимает кнопку микрофона и говорит вопрос. Или пишет текстом. Голосовой ввод через Web Speech API работает прямо в браузере.</p>
          </div>
          <div class="step-arrow">→</div>
          <div class="step-card">
            <div class="step-num">03</div>
            <div class="step-icon">💡</div>
            <h3>Получи ответ</h3>
            <p>ИИ находит релевантные фрагменты в материалах курса и отвечает голосом в реальном времени. Источники показаны под ответом.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- COURSES -->
    <section id="courses" class="courses-section">
      <div class="section-inner">
        <div class="section-label">Демонстрация</div>
        <h2 class="section-title">Доступные курсы</h2>
        <p class="section-subtitle">Каждый курс оснащён голосовым ИИ-ассистентом. Методические материалы уже загружены — можно сразу задавать вопросы.</p>
        <div v-if="loading" class="courses-loading">
          <div class="spinner-lg"></div>
        </div>
        <div v-else class="courses-grid">
          <CourseCard v-for="c in courses" :key="c.id" :course="c" />
        </div>
      </div>
    </section>

    <!-- FOOTER -->
    <footer class="home-footer">
      <div class="footer-logo">🎓 EduAI</div>
      <div class="footer-text">RAG-ассистент для образовательных курсов · VKR Demo</div>
    </footer>
  </div>
</template>

<style scoped>
/* ─── Base & Hero ──────────────────────────────── */
.home-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: var(--bg);
  overflow-x: hidden;
}

.hero {
  position: relative;
  padding: 40px 20px 100px;
  display: flex;
  flex-direction: column;
  align-items: center;
  overflow: hidden;
}

.hero-bg {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  overflow: hidden;
  z-index: 0;
  pointer-events: none;
}

.hero-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.4;
}
.orb1 { width: 400px; height: 400px; background: var(--accent); top: -100px; left: -100px; }
.orb2 { width: 300px; height: 300px; background: var(--accent2); top: 20%; right: -50px; }
.orb3 { width: 250px; height: 250px; background: #fb7185; bottom: -50px; left: 30%; }

/* ─── Navigation ─────────────────────────────── */
.home-nav {
  display: flex;
  align-items: center;
  gap: 30px;
  padding: 20px 40px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border);
  border-radius: 100px;
  margin-bottom: 80px;
  backdrop-filter: blur(12px);
  z-index: 10;
}

.nav-logo {
  font-size: 20px;
  font-weight: 800;
  margin-right: auto;
  color: var(--text);
}

.nav-link {
  color: var(--muted);
  text-decoration: none;
  font-weight: 500;
  transition: color 0.2s;
}

.nav-link:hover { color: var(--text); }

.nav-badge {
  padding: 6px 12px;
  background: rgba(45, 212, 191, 0.1);
  color: var(--accent2);
  border-radius: 20px;
  text-decoration: none;
  font-size: 13px;
  font-weight: 600;
}

/* ─── Hero Content ───────────────────────────── */
.hero-content {
  text-align: center;
  z-index: 10;
  max-width: 800px;
  margin-bottom: 60px;
}

.hero-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border);
  border-radius: 100px;
  font-size: 14px;
  margin-bottom: 30px;
}

.pulse-dot {
  width: 8px;
  height: 8px;
  background: var(--accent2);
  border-radius: 50%;
  animation: pulse-dot 2s infinite;
}

@keyframes pulse-dot {
  0% { box-shadow: 0 0 0 0 rgba(45, 212, 191, 0.4); }
  70% { box-shadow: 0 0 0 8px rgba(45, 212, 191, 0); }
  100% { box-shadow: 0 0 0 0 rgba(45, 212, 191, 0); }
}

.hero-title {
  font-size: 72px;
  font-weight: 800;
  line-height: 1.1;
  margin: 0 0 24px;
}

.gradient-text {
  background: linear-gradient(135deg, var(--accent) 0%, var(--accent2) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.hero-subtitle {
  font-size: 20px;
  color: var(--muted);
  line-height: 1.6;
  margin: 0 0 40px;
}

.hero-actions {
  display: flex;
  gap: 16px;
  justify-content: center;
  margin-bottom: 60px;
}

.btn-hero-primary {
  padding: 16px 36px;
  background: var(--accent);
  color: white;
  border-radius: 16px;
  text-decoration: none;
  font-size: 18px;
  font-weight: 600;
  transition: all 0.2s;
  box-shadow: 0 8px 20px rgba(124, 92, 255, 0.3);
}

.btn-hero-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 24px rgba(124, 92, 255, 0.4);
}

.btn-hero-ghost {
  padding: 16px 36px;
  background: rgba(255, 255, 255, 0.05);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 16px;
  text-decoration: none;
  font-size: 18px;
  font-weight: 600;
  transition: all 0.2s;
}

.btn-hero-ghost:hover {
  background: rgba(255, 255, 255, 0.1);
}

.hero-stats {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 30px;
}

.stat { display: flex; flex-direction: column; align-items: center; }
.stat-num { font-size: 24px; font-weight: 800; color: var(--text); }
.stat-label { font-size: 14px; color: var(--muted); }
.stat-div { width: 1px; height: 30px; background: var(--border); }

/* ─── Hero Visual (Widget Demo) ──────────────── */
.hero-visual {
  z-index: 10;
  width: 100%;
  max-width: 600px;
  margin-top: 40px;
}

.widget-demo {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 20px;
  box-shadow: 0 20px 40px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.05);
  overflow: hidden;
  text-align: left;
}

.demo-header {
  display: flex;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  background: rgba(255,255,255,0.02);
}

.demo-avatar {
  font-size: 24px;
  background: rgba(255,255,255,0.05);
  width: 40px; height: 40px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 50%;
  margin-right: 12px;
}

.demo-name { font-weight: 600; font-size: 15px; }
.demo-status { font-size: 12px; color: var(--accent2); }

.demo-msg { display: flex; flex-direction: column; padding: 0 20px; margin-top: 16px; }
.demo-msg.assistant { align-items: flex-start; }
.demo-msg.user { align-items: flex-end; }

.demo-bubble {
  max-width: 80%;
  padding: 12px 16px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.5;
}

.demo-msg.assistant .demo-bubble {
  background: rgba(255,255,255,0.05);
  border: 1px solid var(--border);
  border-bottom-left-radius: 4px;
}

.demo-msg.user .demo-bubble {
  background: var(--accent);
  color: white;
  border-bottom-right-radius: 4px;
}

.demo-sources {
  font-size: 12px;
  color: var(--muted);
  margin-top: 8px;
  padding: 4px 8px;
  background: rgba(255,255,255,0.05);
  border-radius: 8px;
}

.demo-input-row {
  display: flex;
  padding: 16px 20px;
  border-top: 1px solid var(--border);
  margin-top: 20px;
  background: rgba(0,0,0,0.2);
  align-items: center;
  gap: 10px;
}

.demo-input {
  flex: 1;
  color: var(--muted);
  font-size: 14px;
}

.demo-mic {
  width: 36px; height: 36px;
  border-radius: 50%;
  background: rgba(255,255,255,0.05);
  border: none;
  color: white;
  display: flex; align-items: center; justify-content: center;
}

/* ─── How It Works ───────────────────────────── */
.how-section {
  padding: 100px 20px;
  background: rgba(255, 255, 255, 0.02);
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}

.section-inner {
  max-width: 1200px;
  margin: 0 auto;
  text-align: center;
}

.section-label {
  color: var(--accent2);
  font-size: 14px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 12px;
}

.section-title {
  font-size: 42px;
  font-weight: 800;
  margin: 0 0 60px;
}

.steps-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

.step-card {
  flex: 1;
  background: var(--card);
  border: 1px solid var(--border);
  padding: 30px;
  border-radius: 20px;
  position: relative;
  text-align: left;
}

.step-num {
  font-size: 64px;
  font-weight: 900;
  color: rgba(255,255,255,0.05);
  position: absolute;
  top: 10px; right: 20px;
}

.step-icon {
  font-size: 32px;
  margin-bottom: 20px;
}

.step-card h3 {
  font-size: 20px;
  margin: 0 0 12px;
}

.step-card p {
  color: var(--muted);
  font-size: 15px;
  line-height: 1.6;
  margin: 0;
}

.step-arrow {
  color: var(--muted);
  font-size: 24px;
  opacity: 0.5;
}

/* ─── Courses Section ────────────────────────── */
.courses-section {
  padding: 100px 20px;
}

.section-subtitle {
  font-size: 18px;
  color: var(--muted);
  max-width: 600px;
  margin: 0 auto 50px;
  line-height: 1.6;
}

.courses-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 30px;
  text-align: left;
}

.courses-loading {
  display: flex;
  justify-content: center;
  padding: 60px 0;
}

.spinner-lg {
  width: 48px;
  height: 48px;
  border: 4px solid rgba(255, 255, 255, 0.1);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ─── Footer ─────────────────────────────────── */
.home-footer {
  padding: 40px 20px;
  text-align: center;
  border-top: 1px solid var(--border);
  margin-top: auto;
  background: rgba(0,0,0,0.2);
}

.footer-logo {
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 12px;
  color: var(--text);
}

.footer-text {
  color: var(--muted);
  font-size: 14px;
}
</style>
