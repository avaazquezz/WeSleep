import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '../views/DashboardView.vue'
import LoginView from '../views/LoginView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
    },
    {
      path: '/',
      name: 'dashboard',
      component: DashboardView,
    },
  ],
})

router.beforeEach((to) => {
  const patientId = localStorage.getItem('patientId')

  if (to.path !== '/login' && !patientId) return '/login'
  if (to.path === '/login' && patientId) return '/'
})

export default router

