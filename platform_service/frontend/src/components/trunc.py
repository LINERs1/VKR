import sys

with open('GlobalAssistant.vue', 'r', encoding='utf-8') as f:
    lines = f.readlines()

with open('GlobalAssistant.vue', 'w', encoding='utf-8') as f:
    f.writelines(lines[:932])
    f.write('''<template>
  <div>
    <button
      style="position: fixed; bottom: 20px; right: 20px; z-index: 9999; padding: 20px; background: red; color: white; border: none; font-size: 20px;"
      @click="voiceMode ? stopVoiceMode() : startVoiceMode()"
    >
      {{ voiceMode ? 'STOP VOICE' : 'START VOICE' }}
    </button>
  </div>
</template>

<style scoped>
</style>
''')
