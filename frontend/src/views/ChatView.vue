<template>
  <div class="chat-wrapper">
    <header class="chat-header">
      <div class="header-title">
        <span class="icon">✨</span>
        <h1>EduAI Prototype</h1>
      </div>
      <div class="course-selector">
        <label for="course-select">Курс:</label>
        <select id="course-select" v-model="selectedCourse">
          <option value="course_1">Курс 1</option>
          <option value="course_2">Курс 2</option>
        </select>
      </div>
    </header>

    <main class="chat-messages" ref="messagesContainer">
      <div v-if="messages.length === 0" class="empty-state">
        <div class="empty-icon">🤖</div>
        <h2>Привет! Я ИИ-помощник.</h2>
        <p>Я строго отвечаю по выбранному курсу. Задай мне вопрос!</p>
      </div>
      
      <div 
        v-for="(msg, index) in messages" 
        :key="index" 
        :class="['message', `message-${msg.role}`]"
      >
        <div class="message-avatar">
          {{ msg.role === 'user' ? '👤' : '✨' }}
        </div>
        <div class="message-content">
          <div v-if="msg.content" class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
          <div v-if="msg.sources && msg.sources.length" class="message-sources">
            <span class="source-label">Источники:</span>
            <span v-for="src in msg.sources" :key="src" class="source-badge">{{ src }}</span>
          </div>
        </div>
      </div>
      <div v-if="isLoading" class="message message-assistant typing">
        <div class="message-avatar">✨</div>
        <div class="message-content typing-indicator">
          <span></span><span></span><span></span>
        </div>
      </div>
    </main>

    <footer class="chat-input-area">
      <form @submit.prevent="sendMessage" class="input-form">
        <input 
          type="text" 
          v-model="inputMessage" 
          placeholder="Спроси меня о чем-нибудь..." 
          :disabled="isLoading"
          autofocus
        />
        <button type="submit" :disabled="!inputMessage.trim() || isLoading">
          <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" fill="none">
            <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
          </svg>
        </button>
      </form>
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue';
import { marked } from 'marked';

const messages = ref([]);
const inputMessage = ref('');
const isLoading = ref(false);
const selectedCourse = ref('course_1');
const messagesContainer = ref(null);

const renderMarkdown = (text) => {
  if (!text) return '';
  return marked(text);
};

const scrollToBottom = async () => {
  await nextTick();
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
};

const sendMessage = async () => {
  const msgText = inputMessage.value.trim();
  if (!msgText || isLoading.value) return;

  messages.value.push({ role: 'user', content: msgText });
  inputMessage.value = '';
  isLoading.value = true;
  await scrollToBottom();

  const assistantMsgIndex = messages.value.push({ 
    role: 'assistant', 
    content: '', 
    sources: [] 
  }) - 1;

  try {
    const response = await fetch('http://localhost:8000/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: msgText,
        history: messages.value.slice(0, -1).map(m => ({ role: m.role, content: m.content })),
        course_id: selectedCourse.value
      })
    });

    if (!response.ok) throw new Error('Network error');

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.substring(6));
            if (data.type === 'token') {
              messages.value[assistantMsgIndex].content += data.content;
              await scrollToBottom();
            } else if (data.type === 'sources') {
              messages.value[assistantMsgIndex].sources = data.content;
            } else if (data.type === 'error') {
              messages.value[assistantMsgIndex].content += `\n\n**Ошибка:** ${data.content}`;
            } else if (data.type === 'done') {
              isLoading.value = false;
            }
          } catch (e) {
            console.error('Error parsing SSE:', e);
          }
        }
      }
    }
  } catch (error) {
    console.error('Chat error:', error);
    messages.value[assistantMsgIndex].content = '**Ошибка связи с сервером.** Проверьте, запущен ли бэкенд.';
    isLoading.value = false;
  }
  
  isLoading.value = false;
  await scrollToBottom();
};
</script>

<style scoped>
.chat-wrapper {
  width: 100%;
  max-width: 900px;
  height: 90vh;
  background: var(--panel-bg);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--border-color);
  border-radius: 24px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
}

.chat-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(15, 23, 42, 0.5);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.header-title h1 {
  font-size: 1.25rem;
  font-weight: 600;
  letter-spacing: -0.025em;
  background: linear-gradient(to right, #60a5fa, #a78bfa);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.course-selector {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.875rem;
  color: #cbd5e1;
}

select {
  background: rgba(15, 23, 42, 0.8);
  color: white;
  border: 1px solid rgba(255,255,255,0.2);
  padding: 0.5rem 1rem;
  border-radius: 8px;
  outline: none;
  font-family: inherit;
  transition: all 0.2s;
}

select:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3);
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.chat-messages::-webkit-scrollbar {
  width: 6px;
}
.chat-messages::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.1);
  border-radius: 10px;
}

.empty-state {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  text-align: center;
  animation: fadeIn 0.5s ease-out;
}

.empty-icon {
  font-size: 4rem;
  margin-bottom: 1rem;
  opacity: 0.8;
}

.message {
  display: flex;
  gap: 1rem;
  max-width: 85%;
  animation: slideUp 0.3s ease-out forwards;
}

.message-user {
  margin-left: auto;
  flex-direction: row-reverse;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.25rem;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.1);
}

.message-user .message-avatar {
  background: linear-gradient(135deg, var(--primary), var(--accent));
}

.message-content {
  background: rgba(255, 255, 255, 0.05);
  padding: 1rem 1.25rem;
  border-radius: 18px;
  border-top-left-radius: 4px;
  line-height: 1.5;
  color: #e2e8f0;
}

.message-user .message-content {
  background: var(--primary);
  color: white;
  border-top-left-radius: 18px;
  border-top-right-radius: 4px;
}

.markdown-body :deep(p:last-child) { margin-bottom: 0; }
.markdown-body :deep(code) {
  background: rgba(0,0,0,0.3);
  padding: 0.2em 0.4em;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.9em;
}

.message-sources {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid rgba(255,255,255,0.1);
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
  font-size: 0.75rem;
}

.source-label {
  color: #94a3b8;
}

.source-badge {
  background: rgba(59, 130, 246, 0.2);
  color: #93c5fd;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
}

.chat-input-area {
  padding: 1.25rem 1.5rem;
  background: rgba(15, 23, 42, 0.5);
  border-top: 1px solid var(--border-color);
}

.input-form {
  display: flex;
  gap: 0.75rem;
  position: relative;
}

input {
  flex: 1;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 1rem 1.25rem;
  padding-right: 3.5rem;
  border-radius: 24px;
  color: white;
  font-size: 1rem;
  outline: none;
  transition: all 0.3s;
}

input:focus {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.2);
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.05);
}

button {
  position: absolute;
  right: 6px;
  top: 6px;
  bottom: 6px;
  width: 40px;
  border-radius: 50%;
  background: var(--primary);
  border: none;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
}

button:hover:not(:disabled) {
  background: var(--primary-hover);
  transform: scale(1.05);
}

button:disabled {
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.3);
  cursor: not-allowed;
}

.typing-indicator span {
  display: inline-block;
  width: 6px;
  height: 6px;
  background-color: #94a3b8;
  border-radius: 50%;
  margin: 0 2px;
  animation: bounce 1.4s infinite ease-in-out both;
}

.typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>
