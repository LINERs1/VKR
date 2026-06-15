<template>
  <div class="login-wrapper">
    <div class="login-card">
      <div class="logo-area">
        <div class="logo-icon">EA</div>
        <h2>EduAI</h2>
        <p>Образовательная платформа</p>
      </div>

      <div class="tabs" v-if="mode === 'login' || mode === 'register'">
        <button :class="{ active: mode === 'login' }" @click="switchMode('login')">Вход</button>
        <button :class="{ active: mode === 'register' }" @click="switchMode('register')">Регистрация</button>
      </div>

      <form @submit.prevent="handleSubmit" class="auth-form">
        <!-- Поля для входа и регистрации -->
        <template v-if="mode === 'login' || mode === 'register'">
          <div class="input-group">
            <label>Логин</label>
            <input type="text" v-model="username" required placeholder="Введите логин" />
          </div>
          
          <div v-if="mode === 'register'" class="input-group">
            <label>Email</label>
            <input type="email" v-model="email" required placeholder="example@mail.com" />
          </div>

          <div class="input-group">
            <label>Пароль</label>
            <input type="password" v-model="password" required placeholder="Введите пароль" />
          </div>
        </template>

        <!-- Поля для восстановления пароля -->
        <template v-if="mode === 'forgot'">
          <h3 class="mode-title">Восстановление пароля</h3>
          <p class="mode-desc">Введите ваш email, и мы отправим ссылку для сброса.</p>
          <div class="input-group">
            <label>Email</label>
            <input type="email" v-model="email" required placeholder="example@mail.com" />
          </div>
        </template>

        <template v-if="mode === 'reset'">
          <h3 class="mode-title">Новый пароль</h3>
          <p class="mode-desc">Токен был сгенерирован (см. консоль бэкенда).</p>
          <div class="input-group">
            <label>Токен сброса</label>
            <input type="text" v-model="resetToken" required placeholder="Введите токен" />
          </div>
          <div class="input-group">
            <label>Новый пароль</label>
            <input type="password" v-model="newPassword" required placeholder="Минимум 6 символов" />
          </div>
        </template>

        <!-- Сообщения об ошибках и успехе -->
        <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>
        <div v-if="successMsg" class="success-msg">{{ successMsg }}</div>

        <!-- Кнопки отправки -->
        <button type="submit" class="submit-btn" :disabled="loading">
          <span v-if="!loading">
            {{ mode === 'login' ? 'Войти' : 
               mode === 'register' ? 'Зарегистрироваться' : 
               mode === 'forgot' ? 'Отправить ссылку' : 'Сбросить пароль' }}
          </span>
          <span v-else class="spinner"></span>
        </button>

        <!-- Ссылки под кнопкой -->
        <div class="auth-links">
          <a href="#" v-if="mode === 'login'" @click.prevent="switchMode('forgot')" class="action-link">Забыли пароль?</a>
          <a href="#" v-if="mode === 'forgot' || mode === 'reset'" @click.prevent="switchMode('login')" class="action-link">Вернуться ко входу</a>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'

const router = useRouter()
const { login, register, forgotPassword, resetPassword } = useAuth()

const mode = ref('login')
const username = ref('')
const password = ref('')
const email = ref('')
const resetToken = ref('')
const newPassword = ref('')

const errorMsg = ref('')
const successMsg = ref('')
const loading = ref(false)

const switchMode = (newMode) => {
  mode.value = newMode
  errorMsg.value = ''
  successMsg.value = ''
}

const handleSubmit = async () => {
  errorMsg.value = ''
  successMsg.value = ''
  loading.value = true
  
  try {
    if (mode.value === 'login') {
      await login(username.value, password.value)
      router.push('/')
    } else if (mode.value === 'register') {
      await register(username.value, password.value, email.value)
      await login(username.value, password.value)
      router.push('/')
    } else if (mode.value === 'forgot') {
      const res = await forgotPassword(email.value)
      successMsg.value = res.message || 'Ссылка отправлена. Проверьте консоль бэкенда!'
      if (res.debug_token) {
         resetToken.value = res.debug_token
      }
      setTimeout(() => { mode.value = 'reset' }, 2000)
    } else if (mode.value === 'reset') {
      const res = await resetPassword(resetToken.value, newPassword.value)
      successMsg.value = res.message || 'Пароль успешно изменен'
      setTimeout(() => { switchMode('login') }, 2000)
    }
  } catch (err) {
    errorMsg.value = err.message || 'Произошла ошибка'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrapper {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #09090b, #18181b);
  font-family: 'Inter', system-ui, sans-serif;
  color: #e4e4e7;
}

.login-card {
  width: 100%;
  max-width: 400px;
  background: #18181b;
  border: 1px solid rgba(255,255,255,0.05);
  border-radius: 24px;
  padding: 40px;
  box-shadow: 0 20px 40px rgba(0,0,0,0.4);
}

.logo-area {
  text-align: center;
  margin-bottom: 30px;
}

.logo-icon {
  width: 56px;
  height: 56px;
  background: linear-gradient(135deg, #4f46e5, #6366f1);
  color: #fff;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: 800;
  margin: 0 auto 16px;
  box-shadow: 0 8px 24px rgba(99,102,241,0.4);
}

.logo-area h2 {
  margin: 0 0 4px;
  font-size: 24px;
}

.logo-area p {
  margin: 0;
  color: #a1a1aa;
  font-size: 14px;
}

.mode-title {
  font-size: 18px;
  text-align: center;
  margin: 0 0 8px;
}

.mode-desc {
  font-size: 13px;
  color: #a1a1aa;
  text-align: center;
  margin: 0 0 16px;
}

.tabs {
  display: flex;
  background: #09090b;
  border-radius: 12px;
  padding: 4px;
  margin-bottom: 24px;
}

.tabs button {
  flex: 1;
  background: transparent;
  border: none;
  color: #a1a1aa;
  padding: 10px;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s;
}

.tabs button.active {
  background: #27272a;
  color: #fff;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.input-group label {
  font-size: 13px;
  color: #a1a1aa;
  font-weight: 500;
}

.input-group input {
  background: #09090b;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 12px;
  padding: 12px 16px;
  color: #fff;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}

.input-group input:focus {
  border-color: #6366f1;
}

.error-msg {
  color: #f43f5e;
  font-size: 13px;
  text-align: center;
  background: rgba(244,63,94,0.1);
  padding: 8px;
  border-radius: 8px;
}

.success-msg {
  color: #10b981;
  font-size: 13px;
  text-align: center;
  background: rgba(16,185,129,0.1);
  padding: 8px;
  border-radius: 8px;
}

.submit-btn {
  background: linear-gradient(135deg, #4f46e5, #6366f1);
  color: #fff;
  border: none;
  border-radius: 12px;
  padding: 14px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  display: flex;
  justify-content: center;
  align-items: center;
  height: 48px;
  margin-top: 8px;
}

.submit-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(99,102,241,0.4);
}

.submit-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.auth-links {
  text-align: center;
  margin-top: 8px;
}

.action-link {
  color: #a1a1aa;
  font-size: 13px;
  text-decoration: none;
  transition: color 0.2s;
}

.action-link:hover {
  color: #6366f1;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
