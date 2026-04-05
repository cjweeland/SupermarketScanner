<template>
  <div class="py-4 space-y-6">
    <h2 class="font-bold text-xl text-gray-900 px-1">Winkels & Status</h2>

    <LoadingSpinner v-if="isLoading" message="Status ophalen..." />
    <ErrorBanner v-else-if="isError" />

    <template v-else-if="data">
      <!-- Supermarkten -->
      <div>
        <h3 class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3 px-1">
          🛒 Supermarkten
        </h3>
        <div class="space-y-2">
          <StoreCard
            v-for="store in supermarkets"
            :key="store.slug"
            :store="store"
            @refresh="refreshStore(store.slug)"
          />
        </div>
      </div>

      <!-- Drogisten -->
      <div>
        <h3 class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3 px-1">
          💊 Drogisten
        </h3>
        <div class="space-y-2">
          <StoreCard
            v-for="store in drugstores"
            :key="store.slug"
            :store="store"
            @refresh="refreshStore(store.slug)"
          />
        </div>
      </div>

      <!-- Alles opnieuw scannen -->
      <button
        @click="refreshAll"
        :disabled="isRefreshing"
        class="w-full btn-secondary"
      >
        <span v-if="isRefreshing">⏳ Bezig met scannen...</span>
        <span v-else>🔄 Alle winkels opnieuw scannen</span>
      </button>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import axios from 'axios'
import type { StoreStatus } from '@/types'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorBanner from '@/components/common/ErrorBanner.vue'
import StoreCard from '@/components/stores/StoreCard.vue'

const isRefreshing = ref(false)

const { data, isLoading, isError, refetch } = useQuery({
  queryKey: ['stores'],
  queryFn: async () => {
    const { data } = await axios.get<StoreStatus[]>('/api/v1/stores')
    return data
  },
  refetchInterval: 30000, // Elke 30 seconden automatisch verversen
})

const supermarkets = computed(() => data.value?.filter((s) => s.type === 'supermarket') || [])
const drugstores = computed(() => data.value?.filter((s) => s.type === 'drugstore') || [])

async function refreshStore(slug: string) {
  await axios.post(`/api/v1/stores/${slug}/refresh`)
  setTimeout(() => refetch(), 1000)
}

async function refreshAll() {
  isRefreshing.value = true
  const slugs = data.value?.map((s) => s.slug) || []
  await Promise.allSettled(slugs.map((slug) => axios.post(`/api/v1/stores/${slug}/refresh`)))
  setTimeout(() => {
    refetch()
    isRefreshing.value = false
  }, 2000)
}
</script>
