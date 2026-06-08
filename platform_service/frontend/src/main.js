import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import router from './router/index.js'
import { initDebugger } from './debugger.js'

const app = createApp(App)
initDebugger(app)
app.use(router).mount('#app')
