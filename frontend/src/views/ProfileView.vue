<script setup>
import { onMounted, ref, computed, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'
import { hwApi, apiFetch } from '../api'
import NotificationsBell from '../components/NotificationsBell.vue'
import SettingsModal from '../components/SettingsModal.vue'
import GlassHeader from '../components/GlassHeader.vue'

const router = useRouter()
const { fetchUser, logout } = useAuth()

const user = ref(null)
const homeworks = ref([])
const loading = ref(true)
const activeTab = ref('profile') // 'profile' | 'stats' | 'security'
const showSettings = ref(false)

// ── Profile edit ─────────────────────────────────────────────
const profileForm = reactive({ full_name: '', email: '' })
const profileSaving = ref(false)
const profileSuccess = ref('')
const profileError = ref('')

function initProfileForm() {
  profileForm.full_name = user.value?.full_name || ''
  profileForm.email = user.value?.email || ''
}

async function saveProfile() {
  profileSaving.value = true
  profileSuccess.value = ''
  profileError.value = ''
  try {
    const updated = await apiFetch('/auth/me', {
      method: 'PUT',
      body: JSON.stringify({
        full_name: profileForm.full_name || null,
        email: profileForm.email || null,
      }),
    })
    user.value = updated
    profileSuccess.value = 'Профиль сохранён!'
    setTimeout(() => profileSuccess.value = '', 3000)
  } catch (e) {
    profileError.value = e.message || 'Ошибка сохранения'
  } finally {
    profileSaving.value = false
  }
}

// ── Password change ──────────────────────────────────────────
const pwdForm = reactive({ current: '', newPwd: '', confirm: '' })
const pwdSaving = ref(false)
const pwdSuccess = ref('')
const pwdError = ref('')
const showPwd = reactive({ current: false, newPwd: false, confirm: false })

async function changePassword() {
  pwdError.value = ''
  pwdSuccess.value = ''
  if (pwdForm.newPwd !== pwdForm.confirm) {
    pwdError.value = 'Новый пароль и подтверждение не совпадают'
    return
  }
  if (pwdForm.newPwd.length < 6) {
    pwdError.value = 'Пароль должен быть минимум 6 символов'
    return
  }
  pwdSaving.value = true
  try {
    await apiFetch('/auth/me/password', {
      method: 'PUT',
      body: JSON.stringify({
        current_password: pwdForm.current,
        new_password: pwdForm.newPwd,
      }),
    })
    pwdSuccess.value = 'Пароль успешно изменён!'
    pwdForm.current = ''
    pwdForm.newPwd = ''
    pwdForm.confirm = ''
    setTimeout(() => pwdSuccess.value = '', 4000)
  } catch (e) {
    pwdError.value = e.message || 'Ошибка смены пароля'
  } finally {
    pwdSaving.value = false
  }
}

// ── Stats ────────────────────────────────────────────────────
const stats = computed(() => {
  if (!user.value) return { avgGrade: '-', pendingAction: 0, totalCompleted: 0, totalAssigned: 0, courseAverages: {} }
  let totalGrades = 0, gradeCount = 0, pending = 0, completed = 0
  const courseGrades = {}

  homeworks.value.forEach(hw => {
    const cid = hw.course_id
    if (!courseGrades[cid]) courseGrades[cid] = { sum: 0, count: 0 }
    hw.assignments.forEach(a => {
      if (user.value.role === 'student' && a.student_id !== user.value.id) return
      if (a.status === 'graded' && a.grade) {
        totalGrades += a.grade
        gradeCount++
        courseGrades[cid].sum += a.grade
        courseGrades[cid].count++
      }
      if (user.value.role === 'teacher' && a.status === 'submitted') pending++
      if (user.value.role === 'student' && a.status === 'pending') pending++
      if (user.value.role === 'student' && ['submitted', 'graded'].includes(a.status)) completed++
    })
  })

  const courseAverages = {}
  for (const cid in courseGrades) {
    if (courseGrades[cid].count > 0)
      courseAverages[cid] = (courseGrades[cid].sum / courseGrades[cid].count).toFixed(1)
  }

  return {
    avgGrade: gradeCount > 0 ? (totalGrades / gradeCount).toFixed(1) : '-',
    pendingAction: pending,
    totalAssigned: homeworks.value.length,
    totalCompleted: completed,
    courseAverages,
  }
})

const recentGraded = computed(() => {
  if (user.value?.role !== 'student') return []
  return homeworks.value
    .filter(hw => hw.assignments.some(a => a.student_id === user.value.id && a.status === 'graded'))
    .sort((a, b) => b.id - a.id)
    .slice(0, 6)
})

const gradeColor = (g) => {
  if (!g) return '#6b7280'
  if (g >= 4.5) return '#10b981'
  if (g >= 3.5) return '#6366f1'
  if (g >= 2.5) return '#f59e0b'
  return '#ef4444'
}

const initials = computed(() => {
  if (!user.value) return '?'
  const name = user.value.full_name || user.value.username
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
})

const displayName = computed(() =>
  user.value?.full_name || user.value?.username || ''
)

onMounted(async () => {
  user.value = await fetchUser()
  if (!user.value) return router.push('/login')
  initProfileForm()
  try { homeworks.value = await hwApi.getHomeworks() } catch {}
  loading.value = false
})
</script>

<template>
  <div class="profile-page" v-if="!loading && user">
    <!-- TOPBAR -->
    <GlassHeader>
      <button class="glass-back-btn" @click="router.push('/')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <line x1="19" y1="12" x2="5" y2="12"/>
          <polyline points="12 19 5 12 12 5"/>
        </svg>
        На главную
      </button>
      <div class="glass-title">Профиль</div>
      <div class="topbar-right">
        <button class="settings-btn" @click="showSettings = true" title="Настройки">⚙️</button>
        <NotificationsBell />
        <button class="logout-btn" @click="logout">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/>
            <polyline points="16 17 21 12 16 7"/>
            <line x1="21" y1="12" x2="9" y2="12"/>
          </svg>
          Выйти
        </button>
      </div>
    </GlassHeader>

    <SettingsModal v-if="showSettings" @close="showSettings = false" />

    <div class="page-body">
      <!-- LEFT SIDEBAR: User card -->
      <aside class="user-card">
        <div class="avatar-wrap">
          <div class="avatar">{{ initials }}</div>
          <div class="avatar-ring"></div>
        </div>
        <div class="user-displayname">{{ displayName }}</div>
        <div class="user-handle">@{{ user.username }}</div>
        <div class="role-badge" :class="user.role">
          {{ user.role === 'teacher' ? 'Преподаватель' : 'Студент' }}
        </div>
        <div class="user-email-display" v-if="user.email">{{ user.email }}</div>

        <!-- KPI pills -->
        <div class="kpi-pills">
          <div class="kpi-pill">
            <span class="kp-val" :style="{ color: gradeColor(parseFloat(stats.avgGrade)) }">
              {{ stats.avgGrade }}
            </span>
            <span class="kp-lbl">Средний балл</span>
          </div>
          <div class="kpi-pill">
            <span class="kp-val amber">{{ stats.pendingAction }}</span>
            <span class="kp-lbl">{{ user.role === 'teacher' ? 'Ждут проверки' : 'Ожидают выполнения' }}</span>
          </div>
          <div class="kpi-pill">
            <span class="kp-val">{{ user.role === 'teacher' ? stats.totalAssigned : stats.totalCompleted }}</span>
            <span class="kp-lbl">{{ user.role === 'teacher' ? 'Выдано ДЗ' : 'Сдано ДЗ' }}</span>
          </div>
        </div>

        <div class="card-nav">
          <router-link to="/homeworks" class="card-nav-btn">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
            Задания
          </router-link>
          <router-link to="/journal" class="card-nav-btn" v-if="user.role === 'teacher'">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2z"/>
              <path d="M22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z"/>
            </svg>
            Журнал
          </router-link>
          <router-link to="/analytics" class="card-nav-btn" v-if="user.role === 'teacher'">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <line x1="18" y1="20" x2="18" y2="10"/>
              <line x1="12" y1="20" x2="12" y2="4"/>
              <line x1="6" y1="20" x2="6" y2="14"/>
            </svg>
            Аналитика
          </router-link>
        </div>
      </aside>

      <!-- MAIN PANEL -->
      <main class="main-panel">
        <!-- Tabs -->
        <div class="tabs">
          <button class="tab" :class="{ active: activeTab === 'profile' }" @click="activeTab = 'profile'">
            Личные данные
          </button>
          <button class="tab" :class="{ active: activeTab === 'stats' }" @click="activeTab = 'stats'">
            Успеваемость
          </button>
          <button class="tab" :class="{ active: activeTab === 'security' }" @click="activeTab = 'security'">
            Безопасность
          </button>
        </div>

        <!-- ── Tab: Profile ── -->
        <div v-if="activeTab === 'profile'" class="tab-content">
          <div class="section-header">
            <h2>Личные данные</h2>
            <p>Изменения будут применены сразу после сохранения</p>
          </div>

          <form class="edit-form" @submit.prevent="saveProfile">
            <div class="field-group">
              <div class="field">
                <label class="field-label">Имя пользователя</label>
                <div class="field-static">
                  <input class="input disabled" :value="user.username" disabled/>
                  <span class="field-hint">Имя пользователя изменить нельзя</span>
                </div>
              </div>
              <div class="field">
                <label class="field-label">Роль</label>
                <div class="field-static">
                  <input class="input disabled" :value="user.role === 'teacher' ? 'Преподаватель' : 'Студент'" disabled/>
                </div>
              </div>
            </div>

            <div class="field-group">
              <div class="field">
                <label class="field-label">Полное имя</label>
                <input
                  class="input"
                  v-model="profileForm.full_name"
                  placeholder="Введите ваше имя и фамилию"
                  maxlength="100"
                />
              </div>
              <div class="field">
                <label class="field-label">Email</label>
                <input
                  class="input"
                  v-model="profileForm.email"
                  type="email"
                  placeholder="example@mail.ru"
                  maxlength="120"
                />
              </div>
            </div>

            <div class="form-footer">
              <div class="feedback-msg success" v-if="profileSuccess">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                {{ profileSuccess }}
              </div>
              <div class="feedback-msg error" v-if="profileError">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                  <circle cx="12" cy="12" r="10"/>
                  <line x1="12" y1="8" x2="12" y2="12"/>
                  <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                {{ profileError }}
              </div>
              <button class="btn-save" type="submit" :disabled="profileSaving">
                <span v-if="profileSaving">Сохраняем...</span>
                <span v-else>Сохранить изменения</span>
              </button>
            </div>
          </form>
        </div>

        <!-- ── Tab: Stats ── -->
        <div v-if="activeTab === 'stats'" class="tab-content">
          <div class="section-header">
            <h2>Успеваемость</h2>
            <p>Статистика по всем курсам платформы</p>
          </div>

          <!-- Course averages bar chart -->
          <div class="chart-block" v-if="Object.keys(stats.courseAverages).length > 0">
            <div class="chart-title-row">
              <span class="chart-label">Средний балл по курсам</span>
              <span class="chart-scale">из 5</span>
            </div>
            <div class="bar-chart">
              <div class="bar-item" v-for="(avg, cid) in stats.courseAverages" :key="cid">
                <div class="bar-name">{{ cid }}</div>
                <div class="bar-track">
                  <div
                    class="bar-fill"
                    :style="{ width: (parseFloat(avg) / 5 * 100) + '%', background: gradeColor(parseFloat(avg)) }"
                  ></div>
                </div>
                <div class="bar-val" :style="{ color: gradeColor(parseFloat(avg)) }">{{ avg }}</div>
              </div>
            </div>
          </div>
          <div class="empty-state" v-else>
            <div class="es-icon">📊</div>
            <div class="es-title">Нет данных об успеваемости</div>
            <div class="es-desc">Здесь появится статистика после выполнения заданий</div>
          </div>

          <!-- Recent grades -->
          <div v-if="user.role === 'student' && recentGraded.length > 0">
            <div class="chart-title-row" style="margin-top: 28px; margin-bottom: 14px;">
              <span class="chart-label">Последние оценки</span>
            </div>
            <div class="grades-list">
              <div class="grade-row" v-for="hw in recentGraded" :key="hw.id">
                <div class="gr-left">
                  <div class="gr-title">{{ hw.title }}</div>
                  <div class="gr-course">Курс: {{ hw.course_id }}</div>
                </div>
                <div
                  class="gr-score"
                  :style="{ color: gradeColor(hw.assignments[0]?.grade) }"
                >
                  {{ hw.assignments.find(a => a.student_id === user.id)?.grade ?? '—' }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- ── Tab: Security ── -->
        <div v-if="activeTab === 'security'" class="tab-content">
          <div class="section-header">
            <h2>Безопасность</h2>
            <p>Для смены пароля необходимо подтвердить текущий</p>
          </div>

          <form class="edit-form" @submit.prevent="changePassword">
            <div class="field">
              <label class="field-label">Текущий пароль</label>
              <div class="pwd-wrap">
                <input
                  class="input"
                  v-model="pwdForm.current"
                  :type="showPwd.current ? 'text' : 'password'"
                  placeholder="Введите текущий пароль"
                  autocomplete="current-password"
                  required
                />
                <button type="button" class="eye-btn" @click="showPwd.current = !showPwd.current">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                    <path v-if="!showPwd.current" d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle v-if="!showPwd.current" cx="12" cy="12" r="3"/>
                    <path v-if="showPwd.current" d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/>
                    <line v-if="showPwd.current" x1="1" y1="1" x2="23" y2="23"/>
                  </svg>
                </button>
              </div>
            </div>

            <div class="field-group" style="margin-top: 8px;">
              <div class="field">
                <label class="field-label">Новый пароль</label>
                <div class="pwd-wrap">
                  <input
                    class="input"
                    v-model="pwdForm.newPwd"
                    :type="showPwd.newPwd ? 'text' : 'password'"
                    placeholder="Минимум 6 символов"
                    autocomplete="new-password"
                    required
                  />
                  <button type="button" class="eye-btn" @click="showPwd.newPwd = !showPwd.newPwd">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                      <path v-if="!showPwd.newPwd" d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle v-if="!showPwd.newPwd" cx="12" cy="12" r="3"/>
                      <path v-if="showPwd.newPwd" d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/>
                      <line v-if="showPwd.newPwd" x1="1" y1="1" x2="23" y2="23"/>
                    </svg>
                  </button>
                </div>
                <!-- Strength indicator -->
                <div class="pwd-strength" v-if="pwdForm.newPwd">
                  <div class="strength-bar">
                    <div
                      class="strength-fill"
                      :style="{
                        width: pwdForm.newPwd.length >= 12 ? '100%' : pwdForm.newPwd.length >= 8 ? '66%' : pwdForm.newPwd.length >= 6 ? '33%' : '10%',
                        background: pwdForm.newPwd.length >= 12 ? '#10b981' : pwdForm.newPwd.length >= 8 ? '#6366f1' : pwdForm.newPwd.length >= 6 ? '#f59e0b' : '#ef4444'
                      }"
                    ></div>
                  </div>
                  <span class="strength-label">
                    {{ pwdForm.newPwd.length >= 12 ? 'Надёжный' : pwdForm.newPwd.length >= 8 ? 'Хороший' : pwdForm.newPwd.length >= 6 ? 'Слабый' : 'Очень слабый' }}
                  </span>
                </div>
              </div>
              <div class="field">
                <label class="field-label">Подтвердите пароль</label>
                <div class="pwd-wrap">
                  <input
                    class="input"
                    v-model="pwdForm.confirm"
                    :type="showPwd.confirm ? 'text' : 'password'"
                    placeholder="Повторите новый пароль"
                    autocomplete="new-password"
                    required
                  />
                  <button type="button" class="eye-btn" @click="showPwd.confirm = !showPwd.confirm">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                      <path v-if="!showPwd.confirm" d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle v-if="!showPwd.confirm" cx="12" cy="12" r="3"/>
                      <path v-if="showPwd.confirm" d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/>
                      <line v-if="showPwd.confirm" x1="1" y1="1" x2="23" y2="23"/>
                    </svg>
                  </button>
                </div>
                <div class="match-hint" v-if="pwdForm.confirm" :class="pwdForm.newPwd === pwdForm.confirm ? 'ok' : 'bad'">
                  {{ pwdForm.newPwd === pwdForm.confirm ? '✓ Пароли совпадают' : '✗ Пароли не совпадают' }}
                </div>
              </div>
            </div>

            <div class="form-footer">
              <div class="feedback-msg success" v-if="pwdSuccess">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                {{ pwdSuccess }}
              </div>
              <div class="feedback-msg error" v-if="pwdError">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                  <circle cx="12" cy="12" r="10"/>
                  <line x1="12" y1="8" x2="12" y2="12"/>
                  <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                {{ pwdError }}
              </div>
              <button class="btn-save" type="submit" :disabled="pwdSaving">
                <span v-if="pwdSaving">Меняем пароль...</span>
                <span v-else>Изменить пароль</span>
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  </div>

  <!-- Loading -->
  <div class="page-loading" v-else>
    <div class="loading-spinner"></div>
    <span>Загрузка профиля...</span>
  </div>
</template>

<style scoped>
.profile-page {
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font-family: 'Inter', system-ui, sans-serif;
  display: flex;
  flex-direction: column;
}

/* ── Topbar ─────────────────────────────────── */
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 56px;
  position: sticky;
  top: 12px;
  margin: 0 16px;
  border-radius: 16px;
  z-index: 50;
  background: rgba(18, 18, 24, 0.45);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid rgba(255, 255, 255, 0.06);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4),
              0 0 15px rgba(0, 255, 200, 0.1),
              0 0 30px rgba(157, 78, 221, 0.1);
  transition: all 0.3s ease;
}
.topbar:hover {
  background: rgba(22, 22, 30, 0.55);
  border-color: rgba(255, 255, 255, 0.12);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5),
              0 0 20px rgba(0, 255, 200, 0.15),
              0 0 40px rgba(157, 78, 221, 0.15);
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
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

.back-btn {
  display: flex;
  align-items: center;
  gap: 7px;
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 14px;
  font-family: inherit;
  font-weight: 500;
  padding: 6px 10px;
  border-radius: 7px;
  transition: all 0.15s;
}
.back-btn:hover { color: var(--text); background: var(--bg-elevated); }

.topbar-center { font-size: 15px; font-weight: 700; letter-spacing: -0.01em; }

.logout-btn {
  display: flex;
  align-items: center;
  gap: 7px;
  background: transparent;
  border: 1px solid var(--border);
  color: var(--danger);
  cursor: pointer;
  font-size: 13px;
  font-family: inherit;
  font-weight: 500;
  padding: 6px 12px;
  border-radius: 7px;
  transition: all 0.15s;
}
.logout-btn:hover { background: var(--danger-subtle); border-color: rgba(239,68,68,0.3); }

/* ── Layout ─────────────────────────────────── */
.page-body {
  flex: 1;
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 0;
  max-width: 1100px;
  margin: 0 auto;
  padding: 32px 24px;
  gap: 28px;
  width: 100%;
}

/* ── User Card (Sidebar) ────────────────────── */
.user-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 28px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  height: fit-content;
  position: sticky;
  top: 80px;
}

.avatar-wrap {
  position: relative;
  margin-bottom: 16px;
}

.avatar {
  width: 72px; height: 72px;
  background: linear-gradient(135deg, var(--accent) 0%, #818cf8 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  font-weight: 800;
  color: white;
  position: relative;
  z-index: 1;
}

.avatar-ring {
  position: absolute;
  inset: -3px;
  border-radius: 50%;
  background: conic-gradient(var(--accent), #818cf8, var(--accent2), var(--accent));
  opacity: 0.5;
  animation: ring-spin 4s linear infinite;
}
@keyframes ring-spin { to { transform: rotate(360deg); } }

.user-displayname {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: -0.01em;
  margin-bottom: 4px;
}

.user-handle {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 10px;
}

.role-badge {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 3px 10px;
  border-radius: 5px;
  margin-bottom: 8px;
}
.role-badge.student { background: var(--accent-subtle); color: #818cf8; }
.role-badge.teacher { background: rgba(245,158,11,0.1); color: #f59e0b; }

.user-email-display {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 20px;
}

.kpi-pills {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 20px;
}

.kpi-pill {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 9px;
  padding: 10px 14px;
}

.kp-val {
  font-size: 20px;
  font-weight: 800;
  color: var(--text);
  letter-spacing: -0.02em;
}
.kp-val.amber { color: #f59e0b; }
.kp-lbl { font-size: 12px; color: var(--text-secondary); }

.card-nav {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.card-nav-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 12px;
  border-radius: 8px;
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
  transition: all 0.15s;
}
.card-nav-btn:hover { color: var(--text); background: var(--bg-elevated); }

/* ── Main Panel ─────────────────────────────── */
.main-panel {
  min-width: 0;
}

/* Tabs */
.tabs {
  display: flex;
  gap: 2px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 28px;
}

.tab {
  padding: 10px 18px;
  font-size: 14px;
  font-weight: 500;
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: all 0.15s;
}
.tab:hover { color: var(--text); }
.tab.active { color: var(--accent); border-bottom-color: var(--accent); }

.tab-content { display: flex; flex-direction: column; gap: 20px; }

/* Section header */
.section-header { margin-bottom: 6px; }
.section-header h2 { font-size: 20px; font-weight: 800; letter-spacing: -0.02em; margin: 0 0 4px; }
.section-header p  { font-size: 14px; color: var(--text-secondary); margin: 0; }

/* ── Edit Form ──────────────────────────────── */
.edit-form {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 480px;
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  letter-spacing: 0.01em;
}

.input {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 9px;
  padding: 10px 14px;
  color: var(--text);
  font-size: 14px;
  font-family: inherit;
  outline: none;
  transition: border-color 0.15s;
  width: 100%;
  box-sizing: border-box;
  height: 42px;
  flex: 0 0 auto;
}
.input:focus { border-color: var(--accent); }
.input.disabled { opacity: 0.5; cursor: not-allowed; }
.input::placeholder { color: var(--text-muted); }

.field-hint { font-size: 12px; color: var(--text-muted); }

.form-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 14px;
  padding-top: 4px;
  flex-wrap: wrap;
}

.btn-save {
  padding: 10px 22px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: 9px;
  font-size: 14px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s;
  box-shadow: 0 4px 12px rgba(99,102,241,0.25);
}
.btn-save:hover:not(:disabled) { background: var(--accent-hover); transform: translateY(-1px); }
.btn-save:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

/* Feedback messages */
.feedback-msg {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  font-weight: 500;
  padding: 8px 12px;
  border-radius: 8px;
}
.feedback-msg.success { background: var(--accent2-subtle); color: var(--accent2); }
.feedback-msg.error   { background: var(--danger-subtle); color: var(--danger); }

/* Password field */
.pwd-wrap {
  position: relative;
}
.pwd-wrap .input { padding-right: 44px; }
.eye-btn {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  transition: color 0.15s;
}
.eye-btn:hover { color: var(--text-secondary); }

/* Strength bar */
.pwd-strength { display: flex; align-items: center; gap: 10px; }
.strength-bar { flex: 1; height: 4px; background: var(--border); border-radius: 2px; overflow: hidden; }
.strength-fill { height: 100%; border-radius: 2px; transition: all 0.3s; }
.strength-label { font-size: 11px; color: var(--text-muted); min-width: 80px; }

/* Match hint */
.match-hint { font-size: 12px; font-weight: 500; }
.match-hint.ok  { color: var(--accent2); }
.match-hint.bad { color: var(--danger); }

/* ── Stats Tab ──────────────────────────────── */
.chart-block {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 20px 24px;
}

.chart-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}
.chart-label { font-size: 14px; font-weight: 700; }
.chart-scale  { font-size: 12px; color: var(--text-muted); }

.bar-chart { display: flex; flex-direction: column; gap: 14px; }

.bar-item {
  display: grid;
  grid-template-columns: 90px 1fr 40px;
  align-items: center;
  gap: 12px;
}

.bar-name { font-size: 13px; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar-track { height: 8px; background: var(--bg-elevated); border-radius: 4px; overflow: hidden; }
.bar-fill  { height: 100%; border-radius: 4px; transition: width 0.5s ease; }
.bar-val   { font-size: 14px; font-weight: 700; text-align: right; }

/* Grades list */
.grades-list {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  overflow: hidden;
}

.grade-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  transition: background 0.12s;
}
.grade-row:last-child { border-bottom: none; }
.grade-row:hover { background: var(--bg-elevated); }

.gr-title  { font-size: 14px; font-weight: 600; color: var(--text); margin-bottom: 3px; }
.gr-course { font-size: 12px; color: var(--text-muted); }
.gr-score  { font-size: 22px; font-weight: 800; }

/* Empty state */
.empty-state {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 48px 24px;
  text-align: center;
}
.es-icon  { font-size: 36px; margin-bottom: 12px; }
.es-title { font-size: 15px; font-weight: 700; margin-bottom: 6px; }
.es-desc  { font-size: 14px; color: var(--text-secondary); }

/* ── Page Loading ───────────────────────────── */
.page-loading {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
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

/* ── Responsive ─────────────────────────────── */
@media (max-width: 860px) {
  .page-body { grid-template-columns: 1fr; }
  .user-card { position: static; }
  .field-group { grid-template-columns: 1fr; }
}

@media (max-width: 480px) {
  .page-body { padding: 16px; }

}
</style>
