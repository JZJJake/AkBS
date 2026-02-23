import { createApp } from 'vue'
import App from './App.vue'
import { createRouter, createWebHistory } from 'vue-router'
import MarketView from './views/MarketView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'market',
      component: MarketView
    }
  ]
})

createApp(App).use(router).mount('#app')
