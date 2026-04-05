<template>
  <div class="py-4 space-y-4">
    <StoreFilterBar />

    <!-- Categorie header -->
    <div class="flex items-center gap-3 px-1">
      <span class="text-3xl">{{ categoryIcon }}</span>
      <div>
        <h2 class="font-bold text-xl text-gray-900">{{ categoryLabel }}</h2>
        <p v-if="data" class="text-xs text-gray-400 mt-0.5">{{ data.meta.total }} producten</p>
      </div>
    </div>

    <!-- Laadstatus -->
    <LoadingSpinner v-if="isLoading" />

    <ErrorBanner
      v-else-if="isError"
      title="Prijzen niet beschikbaar"
      message="Zorg dat de backend actief is: cd backend && uvicorn main:app"
    />

    <div v-else-if="data && data.data.length === 0" class="text-center py-12 text-gray-400">
      <div class="text-4xl mb-3">🔄</div>
      <p class="font-medium">Nog geen data voor deze categorie</p>
      <p class="text-sm mt-1">
        <button @click="triggerScrape" class="text-primary-600 underline">
          Start een scan om prijzen op te halen
        </button>
      </p>
    </div>

    <template v-else-if="data">
      <div
        v-if="hasStaleData"
        class="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 flex items-center gap-2 text-sm text-amber-700"
      >
        <span>⏳</span>
        <span>Prijzen worden op de achtergrond bijgewerkt...</span>
      </div>

      <CompareTable :results="data.data" :show-images="true" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import axios from 'axios'
import type { CompareResponse } from '@/types'
import { useFiltersStore } from '@/stores/filtersStore'
import StoreFilterBar from '@/components/layout/StoreFilterBar.vue'
import CompareTable from '@/components/compare/CompareTable.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorBanner from '@/components/common/ErrorBanner.vue'

// Categorie-informatie
const CATEGORIES: Record<string, { label: string; icon: string; queries: string[] }> = {
  vlees_vleeswaren: { label: 'Vlees & vleeswaren', icon: '🥩', queries: ['kipfilet', 'gehakt'] },
  kaas: { label: 'Kaas', icon: '🧀', queries: ['kaas'] },
  koffie_thee: { label: 'Koffie & thee', icon: '☕', queries: ['Douwe Egberts', 'koffie'] },
  wasmiddel: { label: 'Wasmiddel & afwasmiddel', icon: '🫧', queries: ['wasmiddel'] },
  pasta_rijst_sauzen: { label: 'Pasta, rijst & sauzen', icon: '🍝', queries: ['pasta', 'rijst'] },
  ontbijtgranen_muesli: { label: 'Ontbijtgranen & muesli', icon: '🥣', queries: ['muesli', 'havermout'] },
  boter: { label: 'Boter', icon: '🧈', queries: ['boter'] },
  yoghurt_kwark: { label: 'Yoghurt & kwark', icon: '🥛', queries: ['yoghurt', 'kwark'] },
  toiletpapier: { label: 'Toiletpapier & keukenpapier', icon: '🧻', queries: ['toiletpapier'] },
  shampoo_conditioner: { label: 'Shampoo & conditioner', icon: '🧴', queries: ['shampoo'] },
  douchegel_zeep: { label: 'Douchegel & zeep', icon: '🚿', queries: ['douchegel'] },
  deodorant: { label: 'Deodorant', icon: '💨', queries: ['deodorant'] },
  tandpasta_tandenborstels: { label: 'Tandpasta & tandenborstels', icon: '🦷', queries: ['tandpasta'] },
  wasmiddel_wasverzachter: { label: 'Wasmiddel & wasverzachter', icon: '🧺', queries: ['wasmiddel', 'wasverzachter'] },
  afwasmiddel_schoonmaakmiddelen: { label: 'Afwasmiddel & schoonmaakmiddelen', icon: '🧹', queries: ['afwasmiddel'] },
  billendoekjes: { label: 'Billendoekjes', icon: '🍼', queries: ['billendoekjes'] },
  baby_olie: { label: 'Baby-olie', icon: '🫙', queries: ['baby olie'] },
  luiers: { label: 'Luiers', icon: '👶', queries: ['luiers'] },
  baby_shampoo: { label: 'Baby-shampoo', icon: '🍶', queries: ['baby shampoo'] },
  baby_douchezeep: { label: 'Baby-douchezeep', icon: '🛁', queries: ['baby douchezeep'] },
  vaatwastabletten: { label: 'Vaatwastabletten', icon: '🍽️', queries: ['vaatwastabletten'] },
}

const route = useRoute()
const filtersStore = useFiltersStore()

const slug = computed(() => route.params.slug as string)
const catInfo = computed(() => CATEGORIES[slug.value] || { label: slug.value, icon: '📦', queries: [slug.value] })
const categoryLabel = computed(() => catInfo.value.label)
const categoryIcon = computed(() => catInfo.value.icon)

// Gebruik eerste query van de categorie als zoekopdracht
const searchQuery = computed(() => catInfo.value.queries[0] || slug.value)
const storeParam = computed(() => filtersStore.activeStoreList.join(','))

const { data, isLoading, isError, refetch } = useQuery({
  queryKey: computed(() => ['compare', 'category', slug.value, storeParam.value]),
  queryFn: async () => {
    const { data } = await axios.get<CompareResponse>('/api/v1/compare', {
      params: {
        q: searchQuery.value,
        category: slug.value,
        stores: storeParam.value,
        limit: 40,
      },
    })
    return data
  },
})

const hasStaleData = computed(() =>
  data.value?.data.some((r) => r.prices.some((p) => p.freshness === 'stale')) ?? false
)

async function triggerScrape() {
  const stores = filtersStore.activeStoreList
  await Promise.allSettled(
    stores.map((s) => axios.post(`/api/v1/stores/${s}/refresh`))
  )
  setTimeout(() => refetch(), 3000)
}
</script>
