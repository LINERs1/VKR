import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import CourseView from '../views/CourseView.vue'
import LoginView from '../views/LoginView.vue'
import { useAuth } from '../composables/useAuth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeView, meta: { requiresAuth: true } },
    { path: '/courses/:id', component: CourseView, meta: { requiresAuth: true } },
    { path: '/profile', component: () => import('../views/ProfileView.vue'), meta: { requiresAuth: true } },
    { path: '/homeworks', component: () => import('../views/HomeworksView.vue'), meta: { requiresAuth: true } },
    { path: '/homeworks/:id', component: () => import('../views/HomeworkDetailView.vue'), meta: { requiresAuth: true } },
    { path: '/journal', component: () => import('../views/JournalView.vue'), meta: { requiresAuth: true } },
    { path: '/login', component: LoginView, meta: { requiresGuest: true } },
  ],
  scrollBehavior(to) {
    if (to.hash) return { el: to.hash, behavior: 'smooth' }
    return { top: 0 }
  },
})

router.beforeEach((to, from) => {
  const { isAuthenticated } = useAuth()
  const isAuth = isAuthenticated()

  if (to.meta.requiresAuth && !isAuth) {
    return '/login'
  } else if (to.meta.requiresGuest && isAuth) {
    return '/'
  }
})

export default router
