import re

with open('GlobalAssistant.vue', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update onIslandClick logic if it exists (or add it if missing)
if 'function onIslandClick' in content:
    content = re.sub(r'function onIslandClick\(\) \{.*?\}', 'function onIslandClick() { voiceMode.value ? stopVoiceMode() : startVoiceMode() }', content, flags=re.DOTALL)
else:
    # Just add it before togglePanel
    content = content.replace('function togglePanel() {', 'function onIslandClick() { voiceMode.value ? stopVoiceMode() : startVoiceMode() }\n\nfunction togglePanel() {')

# 2. Update Template
template_pattern = re.compile(r'<template>.*?</template>', re.DOTALL)
new_template = '''<template>
  <div>
    <!-- Chat FAB -->
    <button class="chat-fab" @click="togglePanel" :title="isOpen ? 'Закрыть чат' : 'Открыть чат EduAI'">
      {{ isOpen ? '✕' : '💬' }}
    </button>

    <!-- Panels anchor (text chat) in bottom right -->
    <div class="panels-anchor" ref="panelsAnchorRef" :class="{'panels-open': isOpen}">
      <transition name="panel-fade">
        <div v-if="isOpen && !voiceMode" class="widget-panel">
          <div class="wp-header">
            <div class="wp-header-left">
              <span class="wp-icon">🤖</span>
              <div>
                <div class="wp-title">EduAI</div>
                <div class="wp-status">Online</div>
              </div>
            </div>
            <button class="icon-btn" @click="togglePanel">✕</button>
          </div>
          <!-- Messages -->
          <div class="wp-thread" ref="threadEl">
            <div class="msg-row bot-row">
              <div class="msg-bubble bot-bubble">
                <div class="msg-md">Привет! Я твой персональный ИИ-ассистент <b>{{ courseName }}</b>.<br>Чем могу помочь сегодня?</div>
              </div>
            </div>
            
            <div class="msg-row" v-for="(msg, i) in history" :key="i" :class="msg.role === 'user' ? 'user-row' : 'bot-row'">
              <div class="msg-bubble" :class="msg.role === 'user' ? 'user-bubble' : 'bot-bubble'">
                <div class="msg-md" v-html="renderMarkdown(msg.content)"></div>
                <div v-if="msg.sources && msg.sources.length" class="bubble-sources">
                  <span class="source-chip" v-for="(src, idx) in msg.sources" :key="idx" :title="src.title">
                    <span class="src-icon">📄</span>
                    <span class="src-name">{{ src.title || src.file_name }}</span>
                    <span class="src-page" v-if="src.page_number">стр. {{ src.page_number }}</span>
                  </span>
                </div>
                <button v-if="msg.role === 'model'" class="icon-btn" @click="speakText(msg.content)" title="Озвучить">🔊</button>
              </div>
            </div>

            <div class="msg-row bot-row" v-if="isLoading">
              <div class="msg-bubble bot-bubble">
                <div class="typing-indicator"><span></span><span></span><span></span></div>
              </div>
            </div>
            
            <div class="msg-row bot-row" v-if="errorText">
              <div class="msg-bubble error-bubble">
                {{ errorText }}
              </div>
            </div>
          </div>

          <!-- Quick Suggestions -->
          <div class="wp-suggestions" v-if="quickSuggestions.length && !isLoading && !history.length">
            <button v-for="(sug, idx) in quickSuggestions" :key="idx" class="sug-btn" @click="handleSend(sug)">
              {{ sug }}
            </button>
          </div>

          <!-- Input -->
          <div class="wp-input">
            <button class="icon-btn voice-trigger-btn" @click="startVoiceMode('')" title="Голосовой режим">🎤</button>
            <input 
              v-model="inputText" 
              type="text" 
              placeholder="Спроси что-нибудь..." 
              @keydown.enter="handleSend()"
              :disabled="isLoading"
            />
            <button class="send-btn" @click="handleSend()" :disabled="isLoading || !inputText.trim()">➤</button>
          </div>
        </div>
      </transition>
    </div>

    <!-- ══════════════════════ DYNAMIC ISLAND SYSTEM -->
    <div class="island-system-container">
      <!-- Main Island -->
      <div
        class="dynamic-island"
        :class="{
          'island-voice': voiceMode,
          'island-listening': voiceMode && voiceState === 'LISTENING',
          'island-thinking': voiceMode && voiceState === 'THINKING',
          'island-speaking': voiceMode && voiceState === 'SPEAKING'
        }"
        @click="onIslandClick"
        :title="voiceMode ? 'Завершить' : 'Ассистент'"
      >
        <!-- Иконка/Волна -->
        <span class="island-icon" v-if="!voiceMode">
          <!-- Small Microphone Icon when idle -->
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" fill="currentColor" stroke="none" opacity="0.9"/>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
            <line x1="12" y1="19" x2="12" y2="23"/>
            <line x1="8" y1="23" x2="16" y2="23"/>
          </svg>
        </span>

        <div class="island-voice-wave" v-if="voiceMode && voiceState === 'LISTENING'">
          <span v-for="i in 5" :key="i" class="wave-bar" 
            :style="{ height: (4 + (micVolume / 100) * 16) + 'px', animationDelay: (i * 0.1) + 's' }">
          </span>
        </div>
        
        <div class="island-voice-thinking" v-if="voiceMode && voiceState === 'THINKING'">
          <span class="dot"></span><span class="dot"></span><span class="dot"></span>
        </div>

        <div class="island-voice-wave speaking" v-if="voiceMode && voiceState === 'SPEAKING'">
          <span v-for="i in 5" :key="i" class="wave-bar"></span>
        </div>

        <!-- Текст состояния -->
        <span v-if="voiceMode" class="island-status-text">
          {{ voiceStatusText }}
        </span>
        <span v-if="!voiceMode" class="island-label">EduAI</span>
      </div>

      <!-- Transcript Sub-Island (Drop Down) -->
      <transition name="sub-island-slide">
        <div class="sub-island-transcript" v-if="voiceMode && (voiceTranscript || voiceAssistantText)">
          <div class="transcript-content" v-if="voiceState === 'LISTENING'">
            <span class="user-label">Вы:</span> {{ voiceTranscript || 'Слушаю...' }}
          </div>
          <div class="transcript-content bot" v-else-if="voiceAssistantText">
            <span class="bot-label">EduAI:</span> <span v-html="renderMarkdown(voiceAssistantText)"></span>
          </div>
          <div class="transcript-content" v-else>
            ...
          </div>
        </div>
      </transition>
    </div>

  </div>
</template>'''
content = template_pattern.sub(new_template, content)

# 3. Update Styles
style_pattern = re.compile(r'<style scoped>.*?</style>', re.DOTALL)
new_style = '''<style scoped>
/* ─── Chat FAB (Floating Action Button) ──────────────────── */
.chat-fab {
  position: fixed;
  bottom: 24px;
  right: 24px;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
  border: none;
  font-size: 24px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 24px rgba(0,0,0,0.3);
  z-index: 9999;
  transition: transform 0.2s cubic-bezier(0.3, 1.5, 0.5, 1), background 0.2s;
  will-change: transform;
}
.chat-fab:hover {
  transform: scale(1.08);
  background: var(--accent-hover, #3b82f6);
}
.chat-fab:active {
  transform: scale(0.95);
}

/* ─── Text Chat Panel ──────────────────────── */
.panels-anchor {
  position: fixed;
  bottom: 90px;
  right: 24px;
  z-index: 9998;
  pointer-events: none;
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}
.panels-anchor > * { pointer-events: auto; }

.widget-panel {
  width: 380px;
  max-width: calc(100vw - 32px);
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 24px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 20px 40px rgba(0,0,0,0.3);
  height: 550px;
  max-height: calc(100vh - 120px);
}

.panel-fade-enter-active, .panel-fade-leave-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  transform-origin: bottom right;
}
.panel-fade-enter-from, .panel-fade-leave-to {
  opacity: 0;
  transform: scale(0.9) translateY(20px);
}

/* ─── Dynamic Island System ────────────────────────────── */
.island-system-container {
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%) translateZ(0); /* Hardware Accel */
  z-index: 9999;
  display: flex;
  flex-direction: column;
  align-items: center;
  pointer-events: none; /* Let clicks pass through container */
}

.dynamic-island {
  background: #000;
  color: #fff;
  border-radius: 99px;
  height: 44px;
  min-width: 120px;
  padding: 0 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  pointer-events: auto;
  box-shadow: 0 10px 30px rgba(0,0,0,0.3);
  transition: all 0.4s cubic-bezier(0.3, 1, 0.2, 1);
  will-change: width, height, transform, background;
  user-select: none;
  position: relative;
  z-index: 2; /* Main island is on top */
}

.island-voice {
  min-width: 200px;
  background: var(--accent);
}

.island-thinking {
  background: var(--accent2);
}

.island-speaking {
  background: #000;
}

.island-icon, .island-label, .island-status-text {
  font-family: 'Inter', sans-serif;
  font-weight: 600;
  font-size: 14px;
  white-space: nowrap;
}

/* Voice Waves */
.island-voice-wave {
  display: flex;
  align-items: center;
  gap: 3px;
  height: 20px;
}
.wave-bar {
  width: 3px;
  background: #fff;
  border-radius: 2px;
  transition: height 0.1s ease;
}
.island-voice-wave.speaking .wave-bar { animation: wavePulse 1s infinite alternate; }
.island-voice-wave.speaking .wave-bar:nth-child(1) { animation-delay: 0.1s; }
.island-voice-wave.speaking .wave-bar:nth-child(2) { animation-delay: 0.3s; }
.island-voice-wave.speaking .wave-bar:nth-child(3) { animation-delay: 0.0s; }
.island-voice-wave.speaking .wave-bar:nth-child(4) { animation-delay: 0.4s; }
.island-voice-wave.speaking .wave-bar:nth-child(5) { animation-delay: 0.2s; }

@keyframes wavePulse {
  0% { height: 4px; }
  100% { height: 20px; }
}

.island-voice-thinking { display: flex; align-items: center; gap: 4px; }
.island-voice-thinking .dot { width: 6px; height: 6px; background: #fff; border-radius: 50%; animation: dotPulse 1.4s infinite; }
.island-voice-thinking .dot:nth-child(2) { animation-delay: 0.2s; }
.island-voice-thinking .dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes dotPulse {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1.2); }
}

/* Sub-Island Transcript Drop */
.sub-island-transcript {
  background: rgba(15, 15, 15, 0.95);
  color: #fff;
  border-radius: 24px;
  padding: 12px 20px;
  margin-top: 8px; /* Gap below main island */
  min-width: 280px;
  max-width: 400px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.3);
  font-family: 'Inter', sans-serif;
  font-size: 14px;
  line-height: 1.5;
  pointer-events: auto;
  z-index: 1; /* Slides from behind the main island slightly, conceptually */
  border: 1px solid rgba(255,255,255,0.1);
  will-change: transform, opacity;
}

.transcript-content {
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.user-label { color: #9ca3af; font-weight: 600; margin-right: 4px; }
.bot-label { color: var(--accent2); font-weight: 600; margin-right: 4px; }

/* Sub Island Slide Animation */
.sub-island-slide-enter-active, .sub-island-slide-leave-active {
  transition: all 0.4s cubic-bezier(0.3, 1.5, 0.5, 1);
}
.sub-island-slide-enter-from, .sub-island-slide-leave-to {
  opacity: 0;
  transform: translateY(-20px) scale(0.95);
}

/* ─── Chat Internal Styles ────────────────────────────────── */
.wp-header { padding: 16px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.02); }
.wp-header-left { display: flex; align-items: center; gap: 12px; }
.wp-icon { font-size: 24px; background: rgba(255,255,255,0.05); width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; border-radius: 12px; }
.wp-title { font-weight: 600; font-size: 15px; }
.wp-status { font-size: 12px; color: #10b981; display: flex; align-items: center; gap: 4px; }
.wp-status::before { content: ''; width: 6px; height: 6px; background: #10b981; border-radius: 50%; box-shadow: 0 0 8px rgba(16,185,129,0.5); }

.wp-thread { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 16px; scroll-behavior: smooth; }
.msg-row { display: flex; width: 100%; }
.user-row { justify-content: flex-end; }
.bot-row { justify-content: flex-start; }
.msg-bubble { max-width: 85%; padding: 12px 16px; border-radius: 18px; font-size: 14px; line-height: 1.5; position: relative; }
.user-bubble { background: var(--accent); color: white; border-bottom-right-radius: 4px; }
.bot-bubble { background: rgba(255,255,255,0.05); border: 1px solid var(--border); border-bottom-left-radius: 4px; }
.error-bubble { background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3); color: #fca5a5; }

.wp-input { padding: 12px 16px; border-top: 1px solid var(--border); display: flex; gap: 8px; align-items: center; background: rgba(0,0,0,0.2); }
.wp-input input { flex: 1; background: transparent; border: none; color: var(--text); font-size: 14px; outline: none; }
.icon-btn { background: none; border: none; cursor: pointer; color: var(--text); opacity: 0.7; transition: opacity 0.2s; display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 8px; }
.icon-btn:hover { opacity: 1; background: rgba(255,255,255,0.05); }
.send-btn { background: var(--accent); color: white; border: none; border-radius: 10px; width: 36px; height: 36px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 16px; transition: transform 0.1s; }
.send-btn:active { transform: scale(0.95); }
.send-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.bubble-sources { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.1); }
.source-chip { font-size: 11px; padding: 4px 8px; background: rgba(255,255,255,0.1); border-radius: 6px; display: flex; align-items: center; gap: 4px; cursor: default; }
.src-page { opacity: 0.7; font-size: 10px; }
</style>'''

content = style_pattern.sub(new_style, content)

with open('GlobalAssistant.vue', 'w', encoding='utf-8') as f:
    f.write(content)
