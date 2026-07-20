import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: () => import('@/views/HomeView.vue') },
    { path: '/login', component: () => import('@/views/auth/LoginView.vue') },
    {
      path: '/app', component: () => import('@/layouts/AppLayout.vue'), meta: { auth: true },
      children: [
        { path: '', component: () => import('@/views/dashboard/DashboardView.vue') },
        { path: 'courses', component: () => import('@/views/student/CourseCatalogView.vue') },
        { path: 'learning', component: () => import('@/views/student/MyLearningView.vue') },
        { path: 'exams', component: () => import('@/views/student/ExamCenterView.vue') },
        { path: 'notifications', component: () => import('@/views/NotificationsView.vue') },
        { path: 'teacher', component: () => import('@/views/teacher/TeacherWorkspaceView.vue') },
        { path: 'admin', component: () => import('@/views/admin/AdminWorkspaceView.vue') },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.auth && !auth.isAuthenticated) return { path: '/login', query: { redirect: to.fullPath } }
  if (to.path === '/login' && auth.isAuthenticated) return '/app'
})

export default router
