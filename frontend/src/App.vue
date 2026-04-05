<template>
  <div class="min-h-screen flex flex-col">
    <AppHeader />
    <main class="flex-1 container mx-auto px-3 sm:px-4 pb-8 max-w-6xl">
      <RouterView />
    </main>
    <nav class="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 safe-area-bottom md:hidden">
      <div class="flex">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="flex-1 flex flex-col items-center py-2 text-xs text-gray-500 hover:text-primary-600 transition-colors"
          active-class="text-primary-600"
        >
          <span class="text-xl mb-0.5">{{ item.icon }}</span>
          {{ item.label }}
        </RouterLink>
      </div>
    </nav>
    <!-- Ruimte voor bottom nav op mobiel -->
    <div class="h-16 md:hidden" />
  </div>
</template>

<script setup lang="ts">
import { RouterView, RouterLink } from 'vue-router'
import AppHeader from '@/components/layout/AppHeader.vue'

const navItems = [
  { to: '/', icon: '🏠', label: 'Home' },
  { to: '/zoeken', icon: '🔍', label: 'Zoeken' },
  { to: '/winkels', icon: '🏪', label: 'Winkels' },
]
</script>
