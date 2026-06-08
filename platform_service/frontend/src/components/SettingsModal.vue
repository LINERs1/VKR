<script setup>
import { ref, onMounted, watch } from 'vue'
import { useAuth } from '../composables/useAuth'
import { authApi } from '../api'

const emit = defineEmits(['close'])
const { user } = useAuth()

const settings = ref({
  ai_ask_before_navigate: false,
  ai_verbosity_short: false,
  ai_proactive: false,
  ai_auto_read_notifs: false,
  ai_auto_disconnect: false
})
const loading = ref(false)
const saved = ref(false)

onMounted(() => {
  if (user.value && user.value.settings_json) {
    try {
      const parsed = JSON.parse(user.value.settings_json)
      settings.value.ai_ask_before_navigate = !!parsed.ai_ask_before_navigate
      settings.value.ai_verbosity_short = !!parsed.ai_verbosity_short
      settings.value.ai_proactive = !!parsed.ai_proactive
      settings.value.ai_auto_read_notifs = !!parsed.ai_auto_read_notifs
      settings.value.ai_auto_disconnect = !!parsed.ai_auto_disconnect
    } catch(e) {}
  }
})

async function saveSettings() {
  loading.value = true
  saved.value = false
  try {
    const updatedUser = await authApi.updateSettings(settings.value)
    if (user.value) {
      user.value.settings_json = updatedUser.settings_json
    }
    saved.value = true
    setTimeout(() => saved.value = false, 2000)
  } catch(e) {
    console.error(e)
    alert("Ошибка при сохранении настроек")
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-content glass-panel" @click.stop>
      <header class="modal-header">
        <h2>Настройки</h2>
        <button class="close-btn" @click="$emit('close')">×</button>
      </header>
      
      <div class="modal-body">
        <div class="setting-item">
          <div class="setting-info">
            <span class="setting-title">Запрашивать разрешение перед переходом</span>
            <span class="setting-desc">Голосовой ИИ будет спрашивать "Перейти на страницу?" вместо автоматического перехода.</span>
            <span class="setting-warning" style="color: #f59e0b; font-size: 0.75rem; display: block; margin-top: 4px;">⚠️ Требуется перезапуск звонка с ИИ для применения</span>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" v-model="settings.ai_ask_before_navigate" @change="saveSettings">
            <span class="slider"></span>
          </label>
        </div>
        
        <div class="setting-item">
          <div class="setting-info">
            <span class="setting-title">Краткие ответы ИИ</span>
            <span class="setting-desc">ИИ будет отвечать максимально лаконично (1-2 предложения).</span>
            <span class="setting-warning" style="color: #f59e0b; font-size: 0.75rem; display: block; margin-top: 4px;">⚠️ Требуется перезапуск звонка с ИИ для применения</span>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" v-model="settings.ai_verbosity_short" @change="saveSettings">
            <span class="slider"></span>
          </label>
        </div>

        <div class="setting-item">
          <div class="setting-info">
            <span class="setting-title">Инициативность ИИ</span>
            <span class="setting-desc">Разрешить ИИ первым начинать диалог и комментировать действия на экране.</span>
            <span class="setting-warning" style="color: #f59e0b; font-size: 0.75rem; display: block; margin-top: 4px;">⚠️ Требуется перезапуск звонка с ИИ для применения</span>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" v-model="settings.ai_proactive" @change="saveSettings">
            <span class="slider"></span>
          </label>
        </div>

        <div class="setting-item">
          <div class="setting-info">
            <span class="setting-title">Авто-чтение оповещений</span>
            <span class="setting-desc">Автоматически зачитывать новые оповещения, если идёт активный звонок с ИИ.</span>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" v-model="settings.ai_auto_read_notifs" @change="saveSettings">
            <span class="slider"></span>
          </label>
        </div>

        <div class="setting-item">
          <div class="setting-info">
            <span class="setting-title">Отключение при тишине (2 мин)</span>
            <span class="setting-desc">Завершать звонок для экономии, если вы молчите 2 минуты.</span>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" v-model="settings.ai_auto_disconnect" @change="saveSettings">
            <span class="slider"></span>
          </label>
        </div>
      </div>
      
      <div class="modal-footer" v-if="saved">
        <span class="save-success">Настройки сохранены!</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.modal-content {
  border-radius: 16px;
  width: 90%;
  max-width: 500px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 10px 30px rgba(0,0,0,0.5);
  animation: modal-pop 0.2s ease-out;
}

@keyframes modal-pop {
  0% { transform: scale(0.95); opacity: 0; }
  100% { transform: scale(1); opacity: 1; }
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border, #3f3f46);
}

.modal-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text, #fff);
}

.close-btn {
  background: none;
  border: none;
  color: #a1a1aa;
  font-size: 24px;
  cursor: pointer;
  line-height: 1;
}

.close-btn:hover {
  color: #fff;
}

.modal-body {
  padding: 20px;
}

.setting-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 12px 0;
}

.setting-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.setting-title {
  font-weight: 500;
  color: var(--text, #fff);
  font-size: 15px;
}

.setting-desc {
  font-size: 13px;
  color: #a1a1aa;
  line-height: 1.4;
}

/* Toggle Switch Styles */
.toggle-switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
  flex-shrink: 0;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #3f3f46;
  transition: .2s;
  border-radius: 24px;
}

.slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: .2s;
  border-radius: 50%;
}

input:checked + .slider {
  background-color: #6366f1;
}

input:checked + .slider:before {
  transform: translateX(20px);
}

.modal-footer {
  padding: 10px 20px;
  text-align: right;
}

.save-success {
  color: #10b981;
  font-size: 13px;
  font-weight: 500;
}
</style>
