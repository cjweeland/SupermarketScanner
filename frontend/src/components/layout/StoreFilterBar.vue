<template>
  <div class="bg-white border-b border-gray-100 py-2 px-3 sm:px-4 overflow-x-auto">
    <div class="flex items-center gap-2 min-w-max">
      <!-- Type filter -->
      <div class="flex rounded-lg border border-gray-200 overflow-hidden shrink-0">
        <button
          v-for="tab in typeTabs"
          :key="tab.value"
          @click="filtersStore.setStoreType(tab.value as any)"
          :class="[
            'px-3 py-1 text-xs font-medium transition-colors',
            filtersStore.activeStoreType === tab.value
              ? 'bg-primary-600 text-white'
              : 'bg-white text-gray-600 hover:bg-gray-50'
          ]"
        >
          {{ tab.label }}
        </button>
      </div>

      <div class="h-4 w-px bg-gray-200 shrink-0" />

      <!-- Winkeltoggle knoppen -->
      <template v-for="storeType in visibleStoreTypes" :key="storeType">
        <button
          v-for="slug in filtersStore.ALL_STORES[storeType]"
          :key="slug"
          @click="filtersStore.toggleStore(slug)"
          :class="[
            'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-all shrink-0',
            filtersStore.activeStores.has(slug)
              ? 'text-white border-transparent shadow-sm'
              : 'bg-white text-gray-400 border-gray-200 opacity-60',
          ]"
          :style="filtersStore.activeStores.has(slug) ? { backgroundColor: storeColors[slug] } : {}"
        >
          <span>{{ storeLabels[slug] }}</span>
        </button>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useFiltersStore } from '@/stores/filtersStore'

const filtersStore = useFiltersStore()

const typeTabs = [
  { value: 'all', label: 'Alle' },
  { value: 'supermarket', label: '🛒 Super' },
  { value: 'drugstore', label: '💊 Drogist' },
]

const visibleStoreTypes = computed<Array<'supermarket' | 'drugstore'>>(() => {
  if (filtersStore.activeStoreType === 'supermarket') return ['supermarket']
  if (filtersStore.activeStoreType === 'drugstore') return ['drugstore']
  return ['supermarket', 'drugstore']
})

const storeLabels: Record<string, string> = {
  albert_heijn: 'Albert Heijn',
  jumbo: 'Jumbo',
  lidl: 'Lidl',
  dirk: 'Dirk',
  plus: 'Plus',
  kruidvat: 'Kruidvat',
  trekpleister: 'Trekpleister',
  etos: 'Etos',
}

const storeColors: Record<string, string> = {
  albert_heijn: '#00ADE6',
  jumbo: '#FFC800',
  lidl: '#0050AA',
  dirk: '#E30613',
  plus: '#E4002B',
  kruidvat: '#DA291C',
  trekpleister: '#E4002B',
  etos: '#00517F',
}
</script>
