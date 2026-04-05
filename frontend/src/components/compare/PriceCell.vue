<template>
  <div
    :class="[
      'relative p-3 rounded-xl border-2 transition-all',
      isBest ? 'border-green-400 bg-green-50' : 'border-gray-100 bg-white',
    ]"
  >
    <!-- Beste waarde badge -->
    <div v-if="isBest" class="absolute -top-2.5 left-1/2 -translate-x-1/2">
      <span class="bg-green-500 text-white text-xs font-bold px-2 py-0.5 rounded-full whitespace-nowrap">
        ✓ Goedkoopst
      </span>
    </div>

    <!-- Verouderd label -->
    <div v-if="price.freshness === 'stale'" class="absolute top-1 right-1">
      <span class="text-xs text-amber-500 bg-amber-50 px-1.5 py-0.5 rounded-full" title="Prijs wordt bijgewerkt">⏳</span>
    </div>

    <!-- Winkel header -->
    <div class="flex items-center gap-1.5 mb-2">
      <div
        class="h-2.5 w-2.5 rounded-full shrink-0"
        :style="{ backgroundColor: price.store_color }"
      />
      <a
        v-if="price.product_url"
        :href="price.product_url"
        target="_blank"
        rel="noopener noreferrer"
        class="text-xs font-semibold text-gray-700 hover:underline truncate"
      >
        {{ price.store_name }}
      </a>
      <span v-else class="text-xs font-semibold text-gray-700 truncate">{{ price.store_name }}</span>
    </div>

    <!-- Prijs -->
    <div class="flex items-baseline gap-1">
      <span
        :class="[
          'text-lg font-bold',
          isBestAfterPromo && price.promotion?.promo_price_cents ? 'text-green-600' : 'text-gray-900',
        ]"
      >
        {{
          price.promotion?.promo_price_cents
            ? formatPrice(price.promotion.promo_price_cents)
            : price.price_formatted
        }}
      </span>
      <span
        v-if="price.promotion?.promo_price_cents"
        class="text-xs text-gray-400 line-through"
      >
        {{ price.price_formatted }}
      </span>
    </div>

    <!-- Eenheidsprijs -->
    <div v-if="price.unit_price_formatted" class="text-xs text-gray-500 mt-0.5">
      {{ price.unit_price_formatted }}
    </div>

    <!-- Promo badge -->
    <div v-if="price.promotion" class="mt-1.5">
      <PromoBadge :promo="price.promotion" />
    </div>

    <!-- Afbeelding (klein) -->
    <div v-if="showImage && price.image_url" class="mt-2">
      <img
        :src="price.image_url"
        :alt="storeName"
        class="h-12 w-auto mx-auto object-contain"
        loading="lazy"
        @error="($event.target as HTMLImageElement).style.display = 'none'"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { StorePrice } from '@/types'
import { formatPrice } from '@/utils/formatPrice'
import PromoBadge from '@/components/common/PromoBadge.vue'

defineProps<{
  price: StorePrice
  isBest?: boolean
  isBestAfterPromo?: boolean
  showImage?: boolean
  storeName?: string
}>()
</script>
