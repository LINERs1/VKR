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
    { path: '/homeworks/workshop', component: () => import('../views/HomeworkWorkshopListView.vue'), meta: { requiresAuth: true, teacherOnly: true } },
    { path: '/homeworks/workshop/:id', component: () => import('../views/HomeworkWorkshopEditorView.vue'), meta: { requiresAuth: true, teacherOnly: true } },
    { path: '/homeworks/:id', component: () => import('../views/HomeworkDetailView.vue'), meta: { requiresAuth: true } },
    { path: '/journal', component: () => import('../views/JournalView.vue'), meta: { requiresAuth: true, teacherOnly: true } },
    { path: '/analytics', component: () => import('../views/AnalyticsView.vue'), meta: { requiresAuth: true, teacherOnly: true } },
    { path: '/students/:id', component: () => import('../views/StudentProfileView.vue'), meta: { requiresAuth: true, teacherOnly: true } },
    { path: '/login', component: LoginView, meta: { requiresGuest: true } },
  ],
  scrollBehavior(to) {
    if (to.hash) return { el: to.hash, behavior: 'smooth' }
    return { top: 0 }
  },
})

router.beforeEach(async (to, from) => {
  const { isAuthenticated, fetchUser } = useAuth()
  const isAuth = isAuthenticated()

  if (to.meta.requiresAuth && !isAuth) {
    return '/login'
  } else if (to.meta.requiresGuest && isAuth) {
    return '/'
  }

  if (to.meta.teacherOnly && isAuth) {
    const user = await fetchUser()
    if (user?.role !== 'teacher') return '/homeworks'
  }
})

export default router
