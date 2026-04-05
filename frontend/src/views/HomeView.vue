<template>
  <div class="py-4 space-y-4">
    <StoreFilterBar />

    <!-- Header -->
    <div class="text-center py-4">
      <div class="text-5xl mb-2">💨</div>
      <h1 class="text-2xl font-bold text-gray-900">Dove Deodorant</h1>
      <p class="text-gray-500 text-sm mt-1">Prijsvergelijking bij alle supermarkten en drogisten</p>
    </div>

    <!-- Laden -->
    <LoadingSpinner v-if="isLoading" message="Prijzen ophalen bij alle winkels..." />

    <!-- Fout -->
    <ErrorBanner
      v-else-if="isError"
      title="Prijzen niet beschikbaar"
      message="Zorg dat de backend actief is en dat de scraper al gedraaid heeft."
    />

    <!-- Geen data -->
    <div v-else-if="data && data.data.length === 0" class="text-center py-12 text-gray-400">
      <div class="text-4xl mb-3">🔄</div>
      <p class="font-medium text-gray-700">Nog geen prijsdata beschikbaar</p>
      <p class="text-sm mt-2 text-gray-500">
        Draai eerst de scraper om prijzen op te halen:
      </p>
      <code class="block mt-2 text-xs bg-gray-100 rounded-lg px-4 py-2 text-left max-w-sm mx-auto">
        python scripts/run_scrapers.py
      </code>
      <button
        @click="triggerScrape"
        :disabled="scraping"
        class="mt-4 btn-primary"
      >
        {{ scraping ? '⏳ Bezig...' : '▶ Scan starten' }}
      </button>
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

      <!-- Samenvatting -->
      <div class="card p-4 bg-primary-50 border-primary-100">
        <div class="flex items-center justify-between flex-wrap gap-2">
          <div>
            <p class="text-sm text-primary-700 font-medium">
              {{ data.meta.total }} producten gevonden bij {{ data.data[0]?.prices.length ?? 0 }} winkels
            </p>
            <p v-if="cheapest" class="text-xs text-gray-500 mt-0.5">
              Goedkoopste: <strong>{{ cheapest.store_name }}</strong>
              {{ cheapest.unit_price_formatted ?? cheapest.price_formatted }}
            </p>
          </div>
          <button
            @click="refetch()"
            class="text-sm text-primary-600 font-medium"
            :class="{ 'animate-pulse': isFetching }"
          >
            ↻ Vernieuwen
          </button>
        </div>
      </div>

      <CompareTable :results="data.data" :show-images="true" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import axios from 'axios'
import type { CompareResponse, StorePrice } from '@/types'
import { useFiltersStore } from '@/stores/filtersStore'
import StoreFilterBar from '@/components/layout/StoreFilterBar.vue'
import CompareTable from '@/components/compare/CompareTable.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorBanner from '@/components/common/ErrorBanner.vue'

const filtersStore = useFiltersStore()
const scraping = ref(false)
const storeParam = computed(() => filtersStore.activeStoreList.join(','))

const { data, isLoading, isError, isFetching, refetch } = useQuery({
  queryKey: computed(() => ['dove-deodorant', storeParam.value]),
  queryFn: async () => {
    const { data } = await axios.get<CompareResponse>('/api/v1/compare', {
      params: {
        q: 'Dove deodorant',
        category: 'deodorant',
        stores: storeParam.value,
        limit: 50,
      },
    })
    return data
  },
  refetchInterval: 1000 * 60 * 5, // automatisch herladen elke 5 minuten
})

const hasStaleData = computed(() =>
  data.value?.data.some((r) => r.prices.some((p) => p.freshness === 'stale')) ?? false
)

// Goedkoopste optie over alle resultaten
const cheapest = computed<StorePrice | null>(() => {
  if (!data.value?.data.length) return null
  const allPrices = data.value.data.flatMap((r) => r.prices)
  if (!allPrices.length) return null
  return allPrices.reduce((best, p) => {
    const bKey = best.unit_price_cents ?? best.price_cents
    const pKey = p.unit_price_cents ?? p.price_cents
    return pKey < bKey ? p : best
  })
})

async function triggerScrape() {
  scraping.value = true
  await Promise.allSettled(
    filtersStore.activeStoreList.map((s) => axios.post(`/api/v1/stores/${s}/refresh`))
  )
  setTimeout(() => {
    refetch()
    scraping.value = false
  }, 3000)
}
</script>
