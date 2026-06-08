<template>
  <div class="login-wrapper">
    <div class="login-card">
      <div class="logo-area">
        <div class="logo-icon">EA</div>
        <h2>EduAI</h2>
        <p>Образовательная платформа</p>
      </div>

      <div class="tabs">
        <button :class="{ active: mode === 'login' }" @click="mode = 'login'">Вход</button>
        <button :class="{ active: mode === 'register' }" @click="mode = 'register'">Регистрация</button>
      </div>

      <form @submit.prevent="handleSubmit" class="auth-form">
        <div class="input-group">
          <label>Логин</label>
          <input type="text" v-model="username" required placeholder="Введите логин" />
        </div>

        <div class="input-group">
          <label>Пароль</label>
          <input type="password" v-model="password" required placeholder="Введите пароль" />
        </div>

        <div v-if="mode === 'register'" class="input-group">
          <label>Роль</label>
          <select v-model="role">
            <option value="student">Студент</option>
            <option value="teacher">Преподаватель</option>
          </select>
        </div>

        <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>

        <button type="submit" class="submit-btn" :disabled="loading">
          <span v-if="!loading">{{ mode === 'login' ? 'Войти' : 'Зарегистрироваться' }}</span>
          <span v-else class="spinner"></span>
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'

const router = useRouter()
const { login, register } = useAuth()

const mode = ref('login')
const username = ref('')
const password = ref('')
const role = ref('student')
const errorMsg = ref('')
const loading = ref(false)

const handleSubmit = async () => {
  errorMsg.value = ''
  loading.value = true
  try {
    if (mode.value === 'login') {
      await login(username.value, password.value)
      router.push('/')
    } else {
      await register(username.value, password.value, role.value)
      // Сразу логиним после успешной регистрации
      await login(username.value, password.value)
      router.push('/')
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

.input-group input,
.input-group select {
  background: #09090b;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 12px;
  padding: 12px 16px;
  color: #fff;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}

.input-group input:focus,
.input-group select:focus {
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
