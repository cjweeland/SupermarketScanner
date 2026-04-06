<template>
  <div class="bg-white border-b border-gray-100 py-2 px-3 sm:px-4 overflow-x-auto">
    <div class="flex items-center gap-2 min-w-max">
      <span class="text-xs text-gray-400 font-medium shrink-0">Winkels:</span>

      <button
        v-for="slug in allStoreSlugs"
        :key="slug"
        @click="filtersStore.toggleStore(slug)"
        :class="[
          'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-all shrink-0',
          filtersStore.activeStores.has(slug)
            ? 'text-white border-transparent shadow-sm'
            : 'bg-white text-gray-400 border-gray-200 opacity-60',
        ]"
        :style="filtersStore.activeStores.has(slug) ? { backgroundColor: storeColors[slug] ?? '#666' } : {}"
      >
        {{ storeLabels[slug] ?? slug }}
      </button>

      <button
        @click="filtersStore.resetFilters()"
        class="ml-1 text-xs text-gray-400 hover:text-gray-600 shrink-0 underline"
      >
        Alles
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useFiltersStore } from '@/stores/filtersStore'

const filtersStore = useFiltersStore()

const allStoreSlugs = computed(() => [...filtersStore.ALL_STORES.supermarket])

const storeLabels: Record<string, string> = {
  albert_heijn: 'Albert Heijn',
  jumbo: 'Jumbo',
  lidl: 'Lidl',
  dirk: 'Dirk',
  plus: 'Plus',
  aldi: 'Aldi',
  coop: 'Coop',
  hoogvliet: 'Hoogvliet',
  jan_linders: 'Jan Linders',
  poiesz: 'Poiesz',
  dekamarkt: 'DekaMarkt',
  spar: 'Spar',
}

const storeColors: Record<string, string> = {
  albert_heijn: '#00ADE6',
  jumbo: '#FFC800',
  lidl: '#0050AA',
  dirk: '#E30613',
  plus: '#E4002B',
  aldi: '#1A4F9F',
  coop: '#E2001A',
  hoogvliet: '#E4002B',
  jan_linders: '#00853E',
  poiesz: '#E4002B',
  dekamarkt: '#004B98',
  spar: '#007A33',
}
</script>
