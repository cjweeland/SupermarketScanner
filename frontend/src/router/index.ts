import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
    },
    {
      path: '/zoeken',
      name: 'search',
      component: () => import('@/views/SearchView.vue'),
    },
    {
      path: '/categorie/:slug',
      name: 'category',
      component: () => import('@/views/CategoryView.vue'),
    },
    {
      path: '/winkels',
      name: 'stores',
      component: () => import('@/views/StoresView.vue'),
    },
  ],
})

export default router
