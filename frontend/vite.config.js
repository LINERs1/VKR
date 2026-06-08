import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api/chat': { target: 'http://localhost:8000', changeOrigin: true },
      '/api/ultravox': { target: 'http://localhost:8000', changeOrigin: true },
      '/api/adaptive': { target: 'http://localhost:8000', changeOrigin: true },
      '/api/analytics': { target: 'http://localhost:8000', changeOrigin: true },
      '/api/tts': { target: 'http://localhost:8000', changeOrigin: true },
      '/api/stt': { target: 'http://localhost:8000', changeOrigin: true },
      '/api/ingest': { target: 'http://localhost:8000', changeOrigin: true },
      '/api/widget': { target: 'http://localhost:8000', changeOrigin: true },
      '/api': { target: 'http://localhost:8001', changeOrigin: true },
    },
  },
})
