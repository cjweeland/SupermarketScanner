<template>
  <div class="py-4 space-y-4">
    <StoreFilterBar />

    <!-- Geen zoekopdracht -->
    <div v-if="!searchQuery" class="text-center py-12 text-gray-400">
      <div class="text-4xl mb-3">🔍</div>
      <p>Typ een product in de zoekbalk</p>
      <p class="text-sm mt-1">Bijv. "yoghurt", "Douwe Egberts", "luiers"</p>
    </div>

    <template v-else>
      <!-- Header -->
      <div class="flex items-center justify-between px-1">
        <div>
          <h2 class="font-semibold text-gray-900">
            Resultaten voor "{{ searchQuery }}"
          </h2>
          <p v-if="data" class="text-xs text-gray-400 mt-0.5">
            {{ data.meta.total }} producten gevonden
          </p>
        </div>
        <button
          @click="refetch()"
          class="text-sm text-primary-600 hover:text-primary-700 font-medium"
          :class="{ 'animate-pulse': isFetching }"
        >
          ↻ Vernieuwen
        </button>
      </div>

      <!-- Laden -->
      <LoadingSpinner v-if="isLoading" />

      <!-- Fout -->
      <ErrorBanner
        v-else-if="isError"
        title="Prijzen niet beschikbaar"
        message="Zorg dat de backend actief is: cd backend && uvicorn main:app"
      />

      <!-- Geen resultaten -->
      <div v-else-if="data && data.data.length === 0" class="text-center py-12 text-gray-400">
        <div class="text-4xl mb-3">😕</div>
        <p class="font-medium">Geen resultaten gevonden</p>
        <p class="text-sm mt-1">
          Probeer een andere zoekterm of
          <button @click="triggerScrape" class="text-primary-600 underline">
            start een nieuwe scan
          </button>
        </p>
      </div>

      <!-- Resultaten -->
      <template v-else-if="data">
        <!-- Verouderd data melding -->
        <div
          v-if="hasStaleData"
          class="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 flex items-center gap-2 text-sm text-amber-700"
        >
          <span>⏳</span>
          <span>Sommige prijzen worden op de achtergrond bijgewerkt...</span>
        </div>

        <CompareTable :results="data.data" :show-images="true" />
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import axios from 'axios'
import type { CompareResponse } from '@/types'
import { useFiltersStore } from '@/stores/filtersStore'
import StoreFilterBar from '@/components/layout/StoreFilterBar.vue'
import CompareTable from '@/components/compare/CompareTable.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorBanner from '@/components/common/ErrorBanner.vue'

const route = useRoute()
const filtersStore = useFiltersStore()

const searchQuery = computed(() => (route.query.q as string) || '')

const storeParam = computed(() => filtersStore.activeStoreList.join(','))

const { data, isLoading, isError, isFetching, refetch } = useQuery({
  queryKey: computed(() => ['compare', searchQuery.value, storeParam.value]),
  queryFn: async () => {
    if (!searchQuery.value) return null
    const { data } = await axios.get<CompareResponse>('/api/v1/compare', {
      params: {
        q: searchQuery.value,
        stores: storeParam.value,
        limit: 30,
      },
    })
    return data
  },
  enabled: computed(() => !!searchQuery.value),
})

const hasStaleData = computed(() =>
  data.value?.data.some((r) => r.prices.some((p) => p.freshness === 'stale')) ?? false
)

async function triggerScrape() {
  const stores = filtersStore.activeStoreList
  await Promise.allSettled(
    stores.map((slug) => axios.post(`/api/v1/stores/${slug}/refresh`))
  )
  setTimeout(() => refetch(), 2000)
}
</script>
