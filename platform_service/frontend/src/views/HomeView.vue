<script setup>
import { ref, onMounted } from 'vue'
import CourseCard from '../components/CourseCard.vue'
import { apiFetch } from '../api'
import { useAuth } from '../composables/useAuth'
import NotificationsBell from '../components/NotificationsBell.vue'
import SettingsModal from '../components/SettingsModal.vue'

const { user, fetchUser, logout } = useAuth()
const showSettings = ref(false)
const courses = ref([])
const loading = ref(true)

onMounted(async () => {
  try {
    await fetchUser()
    courses.value = await apiFetch('/courses')
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="home-page">
    <!-- TOPBAR -->
    <div class="topbar-wrapper">
      <div class="ambient-orb orb-1"></div>
      <div class="ambient-orb orb-2"></div>
      
      <header class="topbar">
        <div class="topbar-inner">
          <div class="topbar-brand">
            <div class="brand-mark">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path d="M12 2L2 7l10 5 10-5-10-5z" fill="currentColor" opacity="0.95"/>
                <path d="M2 17l10 5 10-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/>
                <path d="M2 12l10 5 10-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/>
              </svg>
            </div>
            <span>EduAI</span>
          </div>

          <nav class="topbar-nav">
            <a href="#courses" class="nav-link">Курсы</a>
            <a href="#how" class="nav-link">Возможности</a>
            <a href="/api/health" target="_blank" class="nav-link nav-status">
              <span class="status-dot-sm"></span>
              API
            </a>
          </nav>

          <div class="topbar-actions" v-if="user">
            <router-link to="/journal" class="glass-link" v-if="user.role === 'teacher'">Журнал</router-link>
            <router-link to="/analytics" class="glass-link" v-if="user.role === 'teacher'">Аналитика</router-link>
            <router-link to="/homeworks" class="glass-link">Задания</router-link>
            
            <div class="topbar-divider"></div>

            <router-link to="/profile" class="glass-profile">
              <div class="avatar-ring">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
              </div>
              <span class="profile-name">{{ user.username }}</span>
            </router-link>
            
            <button class="icon-btn" @click="logout" title="Выйти">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f43f5e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
            </button>
            <button class="icon-btn" @click="showSettings = true" title="Настройки">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
            </button>
            <NotificationsBell />
          </div>
        </div>
      </header>
    </div>

    <SettingsModal v-if="showSettings" @close="showSettings = false" />

    <!-- HERO -->
    <section class="hero">
      <div class="hero-inner">
        <div class="hero-content">
          <div class="hero-badge">
            <span class="badge-dot"></span>
            Голосовой ИИ-ассистент активен
          </div>
          <h1 class="hero-title">
            Образование, которое<br>
            <span class="title-accent">понимает вас</span>
          </h1>
          <p class="hero-desc">
            EduAI встроен в каждый курс. Задавайте вопросы голосом или текстом —
            ассистент найдёт ответ в методических материалах и ответит вслух.
            Как живой преподаватель, но 24/7.
          </p>
          <div class="hero-actions">
            <a href="#courses" class="btn-primary">Выбрать курс</a>
            <a href="#how" class="btn-ghost">Как это работает</a>
          </div>
          <div class="hero-stats">
            <div class="stat-item">
              <span class="stat-val">PDF</span>
              <span class="stat-lbl">Word · TXT · MD</span>
            </div>
            <div class="stat-sep"></div>
            <div class="stat-item">
              <span class="stat-val">RAG</span>
              <span class="stat-lbl">Поиск по материалам</span>
            </div>
            <div class="stat-sep"></div>
            <div class="stat-item">
              <span class="stat-val">Голос</span>
              <span class="stat-lbl">+ текстовый чат</span>
            </div>
          </div>
        </div>

        <div class="hero-visual">
          <div class="demo-window">
            <div class="demo-titlebar">
              <div class="demo-dots">
                <span class="dot red"></span>
                <span class="dot yellow"></span>
                <span class="dot green"></span>
              </div>
              <span class="demo-window-title">EduAI — Ассистент курса</span>
              <span class="demo-online">● online</span>
            </div>
            <div class="demo-messages">
              <div class="demo-msg bot">
                <div class="msg-avatar">AI</div>
                <div class="msg-text">Привет! Я помогаю по курсу <strong>Python для начинающих</strong>. Задайте вопрос голосом или текстом.</div>
              </div>
              <div class="demo-msg user">
                <div class="msg-text">Что такое f-строки в Python?</div>
              </div>
              <div class="demo-msg bot">
                <div class="msg-avatar">AI</div>
                <div class="msg-text">
                  F-строки — удобный способ форматирования: <code>f"Привет, {name}!"</code>
                  Значение переменной подставляется прямо в строку при выполнении.
                  <div class="msg-source">📄 02_variables.txt</div>
                </div>
              </div>
            </div>
            <div class="demo-input">
              <span class="demo-placeholder">Задайте вопрос...</span>
              <button class="demo-mic">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/>
                  <path d="M19 10v2a7 7 0 01-14 0v-2" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>
                  <line x1="12" y1="19" x2="12" y2="23" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                  <line x1="8" y1="23" x2="16" y2="23" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- HOW IT WORKS -->
    <section id="how" class="how-section">
      <div class="section-container">
        <div class="section-head">
          <div class="section-label">Принцип работы</div>
          <h2 class="section-title">Как использовать EduAI</h2>
          <p class="section-sub">От загрузки материалов до голосового ответа — три простых шага</p>
        </div>

        <div class="steps">
          <div class="step">
            <div class="step-number">01</div>
            <div class="step-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
              </svg>
            </div>
            <h3>Загрузите материалы</h3>
            <p>Откройте нужный курс и в боковой панели загрузите методические файлы: PDF, Word (.docx), TXT или Markdown. Система автоматически проиндексирует их в векторную базу ChromaDB. ИИ начнёт опираться на них при ответах.</p>
            <div class="step-tags">
              <span>PDF</span><span>DOCX</span><span>TXT</span><span>MD</span>
            </div>
          </div>

          <div class="step-connector">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <line x1="5" y1="12" x2="19" y2="12"/>
              <polyline points="12 5 19 12 12 19"/>
            </svg>
          </div>

          <div class="step">
            <div class="step-number">02</div>
            <div class="step-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" fill="currentColor" stroke="none" opacity="0.85"/>
                <path d="M19 10v2a7 7 0 01-14 0v-2"/>
                <line x1="12" y1="19" x2="12" y2="23"/>
                <line x1="8" y1="23" x2="16" y2="23"/>
              </svg>
            </div>
            <h3>Задайте вопрос</h3>
            <p>Нажмите кнопку микрофона в плавающем ассистенте (Кортана) или введите вопрос текстом. Голосовой ввод работает через Web Speech API прямо в браузере — никаких установок не нужно.</p>
            <div class="step-tags">
              <span>Голос</span><span>Текст</span><span>Браузер</span>
            </div>
          </div>

          <div class="step-connector">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <line x1="5" y1="12" x2="19" y2="12"/>
              <polyline points="12 5 19 12 12 19"/>
            </svg>
          </div>

          <div class="step">
            <div class="step-number">03</div>
            <div class="step-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
              </svg>
            </div>
            <h3>Получите ответ</h3>
            <p>ИИ с помощью RAG (Retrieval-Augmented Generation) находит релевантные фрагменты из загруженных материалов и генерирует точный ответ. Ответ произносится вслух через синтез речи, источники показаны под текстом.</p>
            <div class="step-tags">
              <span>RAG</span><span>Стриминг</span><span>TTS</span>
            </div>
          </div>
        </div>

        <!-- Feature highlights -->
        <div class="features">
          <div class="feature-item">
            <div class="fi-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                <polyline points="9 11 12 14 22 4"/>
                <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>
              </svg>
            </div>
            <div>
              <h4>Домашние задания с ИИ-проверкой</h4>
              <p>Преподаватель создаёт задания с кодом, тестами и письменной частью. ИИ автоматически проверяет работы и предлагает оценку с развёрнутым отзывом.</p>
            </div>
          </div>
          <div class="feature-item">
            <div class="fi-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                <line x1="18" y1="20" x2="18" y2="10"/>
                <line x1="12" y1="20" x2="12" y2="4"/>
                <line x1="6" y1="20" x2="6" y2="14"/>
              </svg>
            </div>
            <div>
              <h4>Аналитика и журнал успеваемости</h4>
              <p>Дашборд с графиками активности студентов, производительности ИИ, статистики ДЗ и слабых тем — всё для принятия решений на основе данных.</p>
            </div>
          </div>
          <div class="feature-item">
            <div class="fi-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              </svg>
            </div>
            <div>
              <h4>Адаптивное обучение</h4>
              <p>Система отслеживает слабые темы студента по результатам ДЗ и настраивает контекст ИИ — он сам акцентирует внимание на проблемных областях.</p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- COURSES -->
    <section id="courses" class="courses-section">
      <div class="section-container">
        <div class="section-head">
          <div class="section-label">Учебный план</div>
          <h2 class="section-title">Доступные курсы</h2>
          <p class="section-sub">Каждый курс оснащён голосовым ИИ-ассистентом. Методические материалы уже загружены.</p>
        </div>

        <div v-if="loading" class="courses-loading">
          <div class="loading-spinner"></div>
          <span>Загрузка курсов...</span>
        </div>
        <div v-else class="courses-grid">
          <CourseCard v-for="c in courses" :key="c.id" :course="c" />
        </div>
      </div>
    </section>

    <!-- FOOTER -->
    <footer class="home-footer">
      <div class="footer-inner">
        <div class="footer-brand">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <path d="M12 2L2 7l10 5 10-5-10-5z" fill="currentColor"/>
            <path d="M2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/>
          </svg>
          EduAI
        </div>
        <span class="footer-line"></span>
        <span class="footer-copy">RAG-ассистент для образовательных платформ · ВКР</span>
        <a href="/api/health" target="_blank" class="footer-link">API Health ↗</a>
      </div>
    </footer>
  </div>
</template>

<style scoped>
/* ─── Base ───────────────────────────────────────────────── */
.home-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: var(--bg);
  overflow-x: hidden;
}

/* ─── Topbar Wrapper & Ambient Orbs ──────────────────────── */
.topbar-wrapper {
  position: sticky;
  top: 0;
  width: 100%;
  display: flex;
  justify-content: center;
  padding-top: 24px;
  z-index: 100;
}
.ambient-orb {
  position: absolute;
  top: 0px;
  width: 400px;
  height: 200px;
  border-radius: 50%;
  filter: blur(80px);
  z-index: 0;
  opacity: 0.25;
  pointer-events: none;
}
.orb-1 { left: 10%; background: #00ffc8; }
.orb-2 { right: 10%; background: #9d4edd; }

/* ─── Topbar ─────────────────────────────────────────────── */
.topbar {
  position: relative;
  max-width: 1100px;
  width: calc(100% - 48px);
  border-radius: 100px;
  z-index: 10;
  background: rgba(255, 255, 255, 0.03);
  backdrop-filter: blur(32px) saturate(150%);
  -webkit-backdrop-filter: blur(32px) saturate(150%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-top: 1px solid rgba(255, 255, 255, 0.2);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4),
              0 10px 20px rgba(0, 255, 200, 0.1),
              0 10px 40px rgba(157, 78, 221, 0.1),
              inset 0 1px 0 rgba(255,255,255,0.05);
  transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
.topbar:hover {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.2);
  box-shadow: 0 25px 50px rgba(0, 0, 0, 0.5),
              0 15px 30px rgba(0, 255, 200, 0.2),
              0 15px 60px rgba(157, 78, 221, 0.2),
              inset 0 1px 0 rgba(255,255,255,0.1);
  transform: translateY(-2px);
}

.topbar-inner {
  max-width: none;
  width: 100%;
  padding: 0 32px;
  height: 64px;
  display: flex;
  align-items: center;
  gap: 32px;
}

.topbar-brand {
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text);
  flex-shrink: 0;
}

.brand-mark {
  width: 28px; height: 28px;
  background: var(--accent);
  border-radius: 7px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.settings-btn {
  background: transparent;
  border: none;
  font-size: 18px;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: background 0.2s;
}

.settings-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.topbar-nav {
  display: flex;
  align-items: center;
  gap: 2px;
  flex: 1;
}

.nav-link {
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  padding: 6px 10px;
  border-radius: 6px;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  gap: 5px;
}
.nav-link:hover { color: var(--text); background: var(--bg-elevated); }

.nav-status { font-size: 13px; }

.status-dot-sm {
  width: 6px; height: 6px;
  background: var(--accent2);
  border-radius: 50%;
  animation: pulse-dot 2s infinite;
}
@keyframes pulse-dot {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
}

.glass-link {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  text-decoration: none;
  transition: all 0.2s ease;
}
.glass-link:hover {
  color: var(--text);
  text-shadow: 0 0 10px rgba(255,255,255,0.3);
}

.topbar-divider {
  width: 1px;
  height: 24px;
  background: rgba(255, 255, 255, 0.1);
}

.glass-profile {
  display: flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
  padding: 4px 12px 4px 4px;
  border-radius: 40px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.05);
  transition: all 0.2s ease;
}
.glass-profile:hover {
  background: rgba(255,255,255,0.08);
  border-color: rgba(255,255,255,0.15);
}
.avatar-ring {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  box-shadow: 0 0 15px rgba(99,102,241,0.4);
}
.profile-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.icon-btn {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: all 0.2s ease;
}
.icon-btn:hover {
  background: rgba(255,255,255,0.08);
  color: var(--text);
}

/* ─── Hero ───────────────────────────────────────────────── */
.hero {
  padding: 88px 24px 100px;
}

.hero-inner {
  max-width: 1200px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr 480px;
  gap: 80px;
  align-items: center;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  padding: 5px 12px;
  border-radius: 6px;
  margin-bottom: 28px;
}

.badge-dot {
  width: 7px; height: 7px;
  background: var(--accent2);
  border-radius: 50%;
  animation: pulse-dot 2s infinite;
}

.hero-title {
  font-size: 54px;
  font-weight: 800;
  line-height: 1.09;
  letter-spacing: -0.033em;
  margin: 0 0 20px;
}

.title-accent {
  background: linear-gradient(135deg, var(--accent) 0%, #818cf8 60%, var(--accent2) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.hero-desc {
  font-size: 17px;
  line-height: 1.7;
  color: var(--text-secondary);
  margin: 0 0 36px;
  max-width: 500px;
}

.hero-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 48px;
}

.btn-primary {
  padding: 11px 22px;
  background: var(--accent);
  color: white;
  border-radius: 9px;
  text-decoration: none;
  font-size: 15px;
  font-weight: 600;
  transition: all 0.2s;
  box-shadow: 0 4px 14px rgba(99,102,241,0.3);
}
.btn-primary:hover { background: var(--accent-hover); transform: translateY(-1px); }

.btn-ghost {
  padding: 11px 22px;
  background: var(--bg-elevated);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 9px;
  text-decoration: none;
  font-size: 15px;
  font-weight: 500;
  transition: all 0.15s;
}
.btn-ghost:hover { border-color: var(--border-light); }

.hero-stats {
  display: flex;
  align-items: center;
  gap: 20px;
}
.stat-item { display: flex; flex-direction: column; }
.stat-val  { font-size: 17px; font-weight: 700; color: var(--text); letter-spacing: -0.02em; }
.stat-lbl  { font-size: 12px; color: var(--text-muted); }
.stat-sep  { width: 1px; height: 28px; background: var(--border); }

/* ─── Demo Window ────────────────────────────────────────── */
.hero-visual { display: flex; justify-content: flex-end; }

.demo-window {
  width: 100%;
  background: var(--card);
  border: 1px solid var(--border-light);
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 24px 56px rgba(0,0,0,0.45);
}

.demo-titlebar {
  display: flex;
  align-items: center;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-raised);
  gap: 10px;
}

.demo-dots { display: flex; gap: 5px; }
.dot { width: 10px; height: 10px; border-radius: 50%; }
.dot.red    { background: #ef4444; }
.dot.yellow { background: #f59e0b; }
.dot.green  { background: var(--accent2); }

.demo-window-title {
  flex: 1;
  text-align: center;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.demo-online {
  font-size: 11px;
  color: var(--accent2);
  font-weight: 500;
}

.demo-messages {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.demo-msg {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.demo-msg.user { justify-content: flex-end; }

.msg-avatar {
  width: 26px; height: 26px;
  background: var(--accent);
  border-radius: 7px;
  display: flex; align-items: center; justify-content: center;
  font-size: 9px; font-weight: 700;
  color: white;
  flex-shrink: 0;
}

.msg-text {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 9px 12px;
  font-size: 13px;
  line-height: 1.5;
  max-width: 82%;
  color: var(--text);
}

.demo-msg.user .msg-text {
  background: var(--accent-subtle);
  border-color: rgba(99,102,241,0.2);
  border-radius: 10px 10px 2px 10px;
}

.msg-text code {
  font-family: 'JetBrains Mono', monospace;
  background: rgba(255,255,255,0.07);
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 12px;
}

.msg-source {
  margin-top: 7px;
  padding-top: 7px;
  border-top: 1px solid var(--border);
  font-size: 11px;
  color: var(--text-muted);
}

.demo-input {
  display: flex;
  align-items: center;
  padding: 10px 14px;
  border-top: 1px solid var(--border);
  background: var(--bg-raised);
  gap: 10px;
}

.demo-placeholder {
  flex: 1;
  font-size: 13px;
  color: var(--text-muted);
}

.demo-mic {
  width: 28px; height: 28px;
  border-radius: 7px;
  background: var(--accent);
  border: none;
  color: white;
  display: flex; align-items: center; justify-content: center;
  cursor: default;
}

/* ─── How Section ────────────────────────────────────────── */
.how-section {
  padding: 100px 24px;
  background: var(--bg-raised);
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}

.section-container {
  max-width: 1200px;
  margin: 0 auto;
}

.section-head {
  text-align: center;
  margin-bottom: 60px;
}

.section-label {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--accent);
  background: var(--accent-subtle);
  border: 1px solid rgba(99,102,241,0.2);
  padding: 4px 12px;
  border-radius: 5px;
  margin-bottom: 14px;
}

.section-title {
  font-size: 36px;
  font-weight: 800;
  letter-spacing: -0.025em;
  margin: 0 0 12px;
}

.section-sub {
  font-size: 16px;
  color: var(--text-secondary);
  max-width: 520px;
  margin: 0 auto;
  line-height: 1.7;
}

/* Steps */
.steps {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 52px;
}

.step {
  flex: 1;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 24px;
  transition: border-color 0.2s;
}
.step:hover { border-color: var(--border-light); }

.step-connector {
  display: flex;
  align-items: center;
  padding-top: 44px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.step-number {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  margin-bottom: 12px;
}

.step-icon {
  width: 38px; height: 38px;
  background: var(--accent-subtle);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent);
  margin-bottom: 14px;
}

.step h3 {
  font-size: 15px;
  font-weight: 700;
  margin: 0 0 10px;
  letter-spacing: -0.01em;
}

.step p {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.65;
  margin: 0 0 14px;
}

.step-tags {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
}
.step-tags span {
  font-size: 11px;
  font-weight: 600;
  font-family: 'JetBrains Mono', monospace;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  padding: 2px 8px;
  border-radius: 4px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

/* Features */
.features {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.feature-item {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
  display: flex;
  gap: 14px;
  align-items: flex-start;
  transition: border-color 0.2s;
}
.feature-item:hover { border-color: var(--border-light); }

.fi-icon {
  width: 34px; height: 34px;
  background: var(--bg-elevated);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent);
  flex-shrink: 0;
}

.feature-item h4 {
  font-size: 14px;
  font-weight: 700;
  margin: 0 0 6px;
  letter-spacing: -0.01em;
}

.feature-item p {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0;
}

/* ─── Courses ────────────────────────────────────────────── */
.courses-section { padding: 100px 24px; }

.courses-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}

.courses-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 60px 0;
  color: var(--text-muted);
  font-size: 14px;
}

.loading-spinner {
  width: 36px; height: 36px;
  border: 3px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ─── Footer ─────────────────────────────────────────────── */
.home-footer {
  padding: 20px 24px;
  border-top: 1px solid var(--border);
  margin-top: auto;
  background: var(--bg-raised);
}

.footer-inner {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 14px;
}

.footer-brand {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-secondary);
}

.footer-line {
  flex: 1;
  height: 1px;
  background: var(--border);
}

.footer-copy {
  font-size: 13px;
  color: var(--text-muted);
}

.footer-link {
  font-size: 13px;
  color: var(--text-muted);
  text-decoration: none;
  transition: color 0.15s;
}
.footer-link:hover { color: var(--text-secondary); }

/* ─── Responsive ─────────────────────────────────────────── */
@media (max-width: 960px) {
  .hero-inner { grid-template-columns: 1fr; gap: 48px; }
  .hero-visual { justify-content: center; }
  .hero-title { font-size: 40px; }
  .steps { flex-direction: column; }
  .step-connector { transform: rotate(90deg); align-self: center; padding-top: 0; }
  .features { grid-template-columns: 1fr; }
}

@media (max-width: 640px) {
  .topbar-nav { display: none; }
  .hero { padding: 56px 16px 72px; }
  .hero-title { font-size: 32px; }
  .section-title { font-size: 26px; }
  .courses-grid { grid-template-columns: 1fr; }
  .username-label { display: none; }
}
</style>
