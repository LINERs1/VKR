import os

with open('GlobalAssistant.script.txt', 'r', encoding='utf-8') as f:
    script_content = f.read()

template_and_style = """
<template>
  <div>
    <!-- Panels anchor (text chat + voice call) now positioned relative to the dynamic island -->
    <div class="panels-anchor" ref="panelsAnchorRef" :class="{'panels-open': isOpen || voiceMode}">
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
          </div>
          <!-- Messages -->
          <div class="wp-thread" ref="threadEl">
            <!-- System Welcome -->
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

      <!-- Голосовой звонок (Voice Call Card) -->
      <transition name="panel-fade">
        <div v-if="voiceMode" class="vc-card">
          <div class="vc-header">
            <div class="vc-title">
              <span class="vc-title-icon">{{ courseIcon }}</span>
              <span>Звонок с EduAI</span>
            </div>
          </div>
          
          <div class="vc-body">
            <!-- Transcript (user) -->
            <div class="vc-transcript-row user-row">
              <div class="vc-avatar user-avatar">В</div>
              <div class="vc-transcript-box">
                <div v-if="!voiceTranscript" class="vc-placeholder">
                  {{ voiceState === 'LISTENING' ? 'Слушаю вас...' : '...' }}
                </div>
                <div v-else class="vc-text">{{ voiceTranscript }}</div>
              </div>
            </div>
            
            <!-- Transcript (assistant) -->
            <div class="vc-transcript-row bot-row">
              <div class="vc-avatar bot-avatar">AI</div>
              <div class="vc-transcript-box">
                <div v-if="voiceState === 'THINKING'" class="vc-typing">
                  <span></span><span></span><span></span>
                </div>
                <div v-else-if="voiceAssistantText" class="vc-text" v-html="renderMarkdown(voiceAssistantText)"></div>
                <div v-else class="vc-placeholder">...</div>
              </div>
            </div>

            <!-- Warning/Error in Voice -->
            <div class="vc-error" v-if="voiceError">{{ voiceError }}</div>
          </div>

          <!-- Voice Controls -->
          <div class="vc-controls">
            <!-- Mute/Unmute mic -->
            <button class="vc-btn vc-btn-mute" :class="{'muted': !isHearingSpeech}" @click="toggleMic">
              {{ isHearingSpeech ? '🎙️' : '🔇' }}
            </button>
            <!-- Interrupt TTS -->
            <button v-if="voiceState === 'SPEAKING'" class="vc-btn vc-btn-mute" @click="stopSpeakingAndListen" title="Остановить речь">
              🛑
            </button>
            <!-- End Call -->
            <button class="vc-btn vc-btn-end" @click="stopVoiceMode" title="Завершить">
              📞
            </button>
          </div>
        </div>
      </transition>
    </div>

    <!-- ══════════════════════ DYNAMIC ISLAND -->
    <div
      class="dynamic-island"
      :class="{
        'island-open': isOpen && !voiceMode,
        'island-voice': voiceMode,
        'island-listening': voiceMode && voiceState === 'LISTENING',
        'island-thinking': voiceMode && voiceState === 'THINKING',
        'island-speaking': voiceMode && voiceState === 'SPEAKING'
      }"
      @click="onIslandClick"
      :title="voiceMode ? 'Завершить' : (isOpen ? 'Закрыть' : 'EduAI')"
    >
      <!-- Иконка/Волна -->
      <span class="island-icon" v-if="!voiceMode">
        <svg v-if="isOpen" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
        <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
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
      <span v-if="!isOpen && !voiceMode" class="island-label">EduAI</span>
    </div>

  </div>
</template>

<style scoped>
/* ─── Dynamic Island ───────────────────────────────────────── */
.dynamic-island {
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%) translateZ(0); /* Hardware accel for AMD fix */
  z-index: 9999;
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
  box-shadow: 0 10px 30px rgba(0,0,0,0.3);
  transition: all 0.4s cubic-bezier(0.3, 1, 0.2, 1);
  will-change: width, height, transform;
  user-select: none;
}

.island-open {
  min-width: 140px;
  background: #111;
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
.island-voice-wave.speaking .wave-bar {
  animation: wavePulse 1s infinite alternate;
}
.island-voice-wave.speaking .wave-bar:nth-child(1) { animation-delay: 0.1s; }
.island-voice-wave.speaking .wave-bar:nth-child(2) { animation-delay: 0.3s; }
.island-voice-wave.speaking .wave-bar:nth-child(3) { animation-delay: 0.0s; }
.island-voice-wave.speaking .wave-bar:nth-child(4) { animation-delay: 0.4s; }
.island-voice-wave.speaking .wave-bar:nth-child(5) { animation-delay: 0.2s; }

@keyframes wavePulse {
  0% { height: 4px; }
  100% { height: 20px; }
}

.island-voice-thinking {
  display: flex;
  align-items: center;
  gap: 4px;
}
.island-voice-thinking .dot {
  width: 6px;
  height: 6px;
  background: #fff;
  border-radius: 50%;
  animation: dotPulse 1.4s infinite;
}
.island-voice-thinking .dot:nth-child(2) { animation-delay: 0.2s; }
.island-voice-thinking .dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes dotPulse {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1.2); }
}

/* ─── Panels anchor (text chat + call card) ──────────────────────── */
.panels-anchor {
  position: fixed;
  top: 74px; /* Just below the island */
  left: 50%;
  transform: translateX(-50%) translateZ(0);
  z-index: 9998;
  pointer-events: none;
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  display: flex;
  justify-content: center;
}
.panels-anchor > * { pointer-events: auto; }

/* The rest of the panel styles will remain mostly the same, but adapted for top-center */
.widget-panel, .vc-card {
  width: 380px;
  max-width: calc(100vw - 40px);
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 24px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 20px 40px rgba(0,0,0,0.3);
}

.widget-panel {
  height: 500px;
  max-height: calc(100vh - 100px);
}

.vc-card {
  height: 400px;
}

/* Panel fade transition */
.panel-fade-enter-active, .panel-fade-leave-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  transform-origin: top center;
}
.panel-fade-enter-from, .panel-fade-leave-to {
  opacity: 0;
  transform: scaleY(0.8) translateY(-20px);
}

/* Rest of the required UI styles inside panels */
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

.vc-header { padding: 16px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
.vc-title { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 15px; }
.vc-title-icon { font-size: 18px; }
.vc-status { display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 500; color: var(--muted); }
.pulse-dot { width: 8px; height: 8px; border-radius: 50%; background: #555; }
.pulse-dot.pulse-active { background: #10b981; animation: greenPulse 1.5s infinite; box-shadow: 0 0 8px rgba(16,185,129,0.5); }
@keyframes greenPulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }

.vc-body { flex: 1; padding: 20px; display: flex; flex-direction: column; gap: 24px; overflow-y: auto; }
.vc-transcript-row { display: flex; gap: 12px; }
.vc-avatar { width: 40px; height: 40px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 14px; flex-shrink: 0; }
.user-avatar { background: rgba(255,255,255,0.1); }
.bot-avatar { background: linear-gradient(135deg, var(--accent), var(--accent2)); }
.vc-transcript-box { flex: 1; display: flex; flex-direction: column; justify-content: center; }
.vc-text { font-size: 15px; line-height: 1.5; }
.vc-placeholder { font-size: 15px; color: var(--muted); font-style: italic; }
.vc-error { margin-top: auto; padding: 12px; background: rgba(239,68,68,0.1); border-left: 3px solid #ef4444; color: #fca5a5; font-size: 13px; border-radius: 4px; }
.vc-typing { display: flex; gap: 4px; align-items: center; height: 24px; }
.vc-typing span { width: 6px; height: 6px; background: var(--muted); border-radius: 50%; animation: typing 1.4s infinite; }
.vc-typing span:nth-child(2) { animation-delay: 0.2s; }
.vc-typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing { 0%, 100% { opacity: 0.3; transform: translateY(0); } 50% { opacity: 1; transform: translateY(-3px); } }

.vc-controls { padding: 16px; border-top: 1px solid var(--border); display: flex; justify-content: center; gap: 16px; background: rgba(0,0,0,0.2); }
.vc-btn { width: 50px; height: 50px; border-radius: 50%; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 20px; transition: all 0.2s; box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
.vc-btn:active { transform: scale(0.92); }
.vc-btn-mute { background: rgba(255,255,255,0.1); color: white; }
.vc-btn-mute.muted { background: rgba(239,68,68,0.2); color: #ef4444; border: 1px solid rgba(239,68,68,0.3); }
.vc-btn-end { background: #e11d48; color: white; }
.vc-btn-end:hover { background: #be123c; }

/* Sources inside bubble */
.bubble-sources { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.1); }
.source-chip { font-size: 11px; padding: 4px 8px; background: rgba(255,255,255,0.1); border-radius: 6px; display: flex; align-items: center; gap: 4px; cursor: default; }
.src-page { opacity: 0.7; font-size: 10px; }

</style>
"""

with open('GlobalAssistant.vue', 'w', encoding='utf-8') as f:
    f.write(script_content)
    f.write(template_and_style)
