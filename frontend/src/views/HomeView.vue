<template>
  <div class="py-4 space-y-6">
    <!-- Welkom header -->
    <div class="text-center py-6">
      <div class="text-5xl mb-3">🛒</div>
      <h1 class="text-2xl font-bold text-gray-900">PrijsScanner</h1>
      <p class="text-gray-500 mt-1 text-sm">Vergelijk prijzen bij supermarkten en drogisten</p>
    </div>

    <!-- Snelzoek voorbeelden -->
    <div>
      <h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3 px-1">
        Snel zoeken
      </h2>
      <div class="flex flex-wrap gap-2">
        <button
          v-for="suggestion in suggestions"
          :key="suggestion"
          @click="quickSearch(suggestion)"
          class="px-3 py-1.5 bg-white border border-gray-200 rounded-full text-sm text-gray-700 hover:border-primary-400 hover:text-primary-600 transition-colors"
        >
          {{ suggestion }}
        </button>
      </div>
    </div>

    <!-- Supermarkt categorieën -->
    <div>
      <h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3 px-1">
        🛒 Supermarkt categorieën
      </h2>
      <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
        <RouterLink
          v-for="cat in supermarktCategories"
          :key="cat.slug"
          :to="`/categorie/${cat.slug}`"
          class="card p-3 flex items-center gap-2 hover:border-primary-200 hover:shadow transition-all border border-transparent"
        >
          <span class="text-2xl">{{ cat.icon }}</span>
          <div class="min-w-0">
            <p class="text-sm font-medium text-gray-800 leading-tight">{{ cat.label }}</p>
            <p v-if="cat.product_count > 0" class="text-xs text-gray-400">{{ cat.product_count }} producten</p>
          </div>
        </RouterLink>
      </div>
    </div>

    <!-- Drogist categorieën -->
    <div>
      <h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3 px-1">
        💊 Drogist categorieën
      </h2>
      <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
        <RouterLink
          v-for="cat in drogistCategories"
          :key="cat.slug"
          :to="`/categorie/${cat.slug}`"
          class="card p-3 flex items-center gap-2 hover:border-primary-200 hover:shadow transition-all border border-transparent"
        >
          <span class="text-2xl">{{ cat.icon }}</span>
          <div class="min-w-0">
            <p class="text-sm font-medium text-gray-800 leading-tight">{{ cat.label }}</p>
            <p v-if="cat.product_count > 0" class="text-xs text-gray-400">{{ cat.product_count }} producten</p>
          </div>
        </RouterLink>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import axios from 'axios'
import type { Category } from '@/types'

const router = useRouter()

const { data: categories } = useQuery({
  queryKey: ['categories'],
  queryFn: async () => {
    const { data } = await axios.get<Category[]>('/api/v1/categories')
    return data
  },
  staleTime: 1000 * 60 * 10,
})

const supermarktCategories = computed(() =>
  (categories.value || defaultCategories).filter((c) => c.store_type === 'supermarket')
)
const drogistCategories = computed(() =>
  (categories.value || defaultCategories).filter((c) => c.store_type === 'drugstore')
)

const suggestions = [
  'Douwe Egberts', 'yoghurt', 'kipfilet', 'kaas', 'shampoo',
  'luiers', 'wasmiddel', 'pasta', 'boter', 'tandpasta',
]

function quickSearch(query: string) {
  router.push({ name: 'search', query: { q: query } })
}

// Standaard categorieën als de API nog niet beschikbaar is
const defaultCategories: Category[] = [
  { slug: 'vlees_vleeswaren', label: 'Vlees & vleeswaren', icon: '🥩', store_type: 'supermarket', product_count: 0 },
  { slug: 'kaas', label: 'Kaas', icon: '🧀', store_type: 'supermarket', product_count: 0 },
  { slug: 'koffie_thee', label: 'Koffie & thee', icon: '☕', store_type: 'supermarket', product_count: 0 },
  { slug: 'wasmiddel', label: 'Wasmiddel', icon: '🫧', store_type: 'supermarket', product_count: 0 },
  { slug: 'pasta_rijst_sauzen', label: 'Pasta, rijst & sauzen', icon: '🍝', store_type: 'supermarket', product_count: 0 },
  { slug: 'ontbijtgranen_muesli', label: 'Ontbijtgranen', icon: '🥣', store_type: 'supermarket', product_count: 0 },
  { slug: 'boter', label: 'Boter', icon: '🧈', store_type: 'supermarket', product_count: 0 },
  { slug: 'yoghurt_kwark', label: 'Yoghurt & kwark', icon: '🥛', store_type: 'supermarket', product_count: 0 },
  { slug: 'toiletpapier', label: 'Toiletpapier', icon: '🧻', store_type: 'supermarket', product_count: 0 },
  { slug: 'shampoo_conditioner', label: 'Shampoo', icon: '🧴', store_type: 'drugstore', product_count: 0 },
  { slug: 'douchegel_zeep', label: 'Douchegel & zeep', icon: '🚿', store_type: 'drugstore', product_count: 0 },
  { slug: 'deodorant', label: 'Deodorant', icon: '💨', store_type: 'drugstore', product_count: 0 },
  { slug: 'tandpasta_tandenborstels', label: 'Tandpasta', icon: '🦷', store_type: 'drugstore', product_count: 0 },
  { slug: 'wasmiddel_wasverzachter', label: 'Wasmiddel', icon: '🧺', store_type: 'drugstore', product_count: 0 },
  { slug: 'billendoekjes', label: 'Billendoekjes', icon: '🍼', store_type: 'drugstore', product_count: 0 },
  { slug: 'luiers', label: 'Luiers', icon: '👶', store_type: 'drugstore', product_count: 0 },
  { slug: 'baby_shampoo', label: 'Baby-shampoo', icon: '🍶', store_type: 'drugstore', product_count: 0 },
  { slug: 'vaatwastabletten', label: 'Vaatwastabletten', icon: '🍽️', store_type: 'drugstore', product_count: 0 },
]
</script>
