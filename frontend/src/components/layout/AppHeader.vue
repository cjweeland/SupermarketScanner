<template>
  <header class="bg-white border-b border-gray-200 sticky top-0 z-40 shadow-sm">
    <div class="container mx-auto px-3 sm:px-4 max-w-6xl">
      <div class="flex items-center gap-3 h-14">
        <!-- Logo -->
        <RouterLink to="/" class="flex items-center gap-1.5 shrink-0">
          <span class="text-2xl">🛒</span>
          <span class="font-bold text-primary-700 text-lg hidden sm:block">PrijsScanner</span>
        </RouterLink>

        <!-- Zoekbalk -->
        <form @submit.prevent="onSearch" class="flex-1">
          <div class="relative">
            <input
              v-model="searchQuery"
              type="search"
              placeholder="Zoek bijv. yoghurt, Douwe Egberts..."
              class="w-full pl-4 pr-10 py-2 rounded-full border border-gray-200 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 bg-gray-50 text-sm"
              @keyup.enter="onSearch"
            />
            <button
              type="submit"
              class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-primary-600"
            >
              🔍
            </button>
          </div>
        </form>

        <!-- Desktop nav -->
        <nav class="hidden md:flex items-center gap-4 shrink-0">
          <RouterLink to="/" class="text-sm text-gray-600 hover:text-primary-600 transition-colors" active-class="text-primary-600 font-medium">
            Home
          </RouterLink>
          <RouterLink to="/winkels" class="text-sm text-gray-600 hover:text-primary-600 transition-colors" active-class="text-primary-600 font-medium">
            Winkels
          </RouterLink>
        </nav>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { RouterLink } from 'vue-router'

const router = useRouter()
const searchQuery = ref('')

function onSearch() {
  const q = searchQuery.value.trim()
  if (q) {
    router.push({ name: 'search', query: { q } })
  }
}
</script>
