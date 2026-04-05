<template>
  <header class="bg-white border-b border-gray-200 sticky top-0 z-40 shadow-sm">
    <div class="container mx-auto px-3 sm:px-4 max-w-6xl">
      <div class="flex items-center gap-3 h-14">
        <!-- Logo -->
        <RouterLink to="/" class="flex items-center gap-1.5 shrink-0">
          <span class="text-2xl">🛒</span>
          <span class="font-bold text-primary-700 text-lg hidden sm:block">PrijsScanner</span>
        </RouterLink>

        <!-- Titel (testmodus) -->
        <div class="flex-1 text-center">
          <span class="text-sm font-medium text-gray-500">🧪 Testmodus — Dove deodorant</span>
        </div>

        <!-- Desktop nav -->
        <nav class="hidden md:flex items-center gap-4 shrink-0">
          <RouterLink to="/" class="text-sm text-gray-600 hover:text-primary-600 transition-colors" active-class="text-primary-600 font-medium">
            Vergelijking
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
