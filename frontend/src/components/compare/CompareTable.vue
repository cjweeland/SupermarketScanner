<template>
  <div class="space-y-4">
    <div
      v-for="result in results"
      :key="result.product_name"
      class="card"
    >
      <!-- Product header -->
      <div class="px-4 pt-4 pb-2 border-b border-gray-50">
        <div class="flex items-start justify-between gap-2">
          <div>
            <p v-if="result.brand" class="text-xs text-gray-400 font-medium uppercase tracking-wide">
              {{ result.brand }}
            </p>
            <h3 class="font-semibold text-gray-900 leading-tight">{{ result.product_name }}</h3>
          </div>
          <div class="flex items-center gap-1 shrink-0">
            <span class="text-xs text-gray-400">{{ result.prices.length }} winkels</span>
          </div>
        </div>

        <!-- Beste waarde samenvatting -->
        <div v-if="result.best_value_store" class="mt-2 flex items-center gap-2 flex-wrap">
          <span class="text-xs text-green-700 bg-green-50 px-2 py-0.5 rounded-full font-medium">
            Goedkoopst: {{ storeName(result.best_value_store) }}
          </span>
          <span
            v-if="result.best_value_after_promo_store && result.best_value_after_promo_store !== result.best_value_store"
            class="text-xs text-blue-700 bg-blue-50 px-2 py-0.5 rounded-full font-medium"
          >
            Met actie: {{ storeName(result.best_value_after_promo_store) }}
          </span>
        </div>
      </div>

      <!-- Prijs-raster: horizontaal scrollbaar op mobiel -->
      <div class="p-3 overflow-x-auto">
        <div
          class="grid gap-2"
          :style="{ gridTemplateColumns: `repeat(${result.prices.length}, minmax(120px, 1fr))` }"
        >
          <PriceCell
            v-for="price in result.prices"
            :key="price.store_slug"
            :price="price"
            :is-best="price.store_slug === result.best_value_store"
            :is-best-after-promo="price.store_slug === result.best_value_after_promo_store"
            :show-image="showImages"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ComparisonResult } from '@/types'
import PriceCell from './PriceCell.vue'

defineProps<{
  results: ComparisonResult[]
  showImages?: boolean
}>()

const STORE_NAMES: Record<string, string> = {
  albert_heijn: 'Albert Heijn',
  jumbo: 'Jumbo',
  lidl: 'Lidl',
  dirk: 'Dirk',
  plus: 'Plus',
  kruidvat: 'Kruidvat',
  trekpleister: 'Trekpleister',
  etos: 'Etos',
}

function storeName(slug: string | null): string {
  return slug ? (STORE_NAMES[slug] || slug) : ''
}
</script>
