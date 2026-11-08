import { createRouter, createWebHistory } from 'vue-router'
import { auth } from './api/client.js'
import { clearSession, session } from './stores/session.js'
import LoginView from './views/LoginView.vue'
import MainView from './views/MainView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView },
    { path: '/', component: MainView },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to) => {
  if (to.path === '/login') return session.token ? '/' : true
  return session.token ? true : '/login'
})

auth.onExpired = () => {
  clearSession()
  router.replace('/login')
}

export default router
