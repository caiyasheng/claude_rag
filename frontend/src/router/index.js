import { createRouter, createWebHistory } from 'vue-router'
import RAGSearch from '../views/RAGSearch.vue'
import Documents from '../views/Documents.vue'
import RAGEval from '../views/RAGEval.vue'

const routes = [
  {
    path: '/',
    name: 'RAGSearch',
    component: RAGSearch,
    meta: { title: 'RAG 检索' },
  },
  {
    path: '/documents',
    name: 'Documents',
    component: Documents,
    meta: { title: '文档管理' },
  },
  {
    path: '/eval',
    name: 'RAGEval',
    component: RAGEval,
    meta: { title: 'RAG 评测' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  document.title = `${to.meta.title || 'RAG'} · RAG Platform`
})

export default router
