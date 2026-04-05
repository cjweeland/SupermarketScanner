<template>
  <span
    :class="[
      'promo-badge',
      badgeStyle.bg,
      badgeStyle.text,
    ]"
  >
    <span>{{ badgeStyle.icon }}</span>
    <span>{{ promo.description }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Promo } from '@/types'

const props = defineProps<{ promo: Promo }>()

const badgeStyle = computed(() => {
  switch (props.promo.type) {
    case 'bonus_card':
      return { bg: 'bg-blue-100', text: 'text-blue-800', icon: '💳' }
    case 'lidl_plus':
      return { bg: 'bg-blue-100', text: 'text-blue-800', icon: '💳' }
    case 'percentage_off':
      return { bg: 'bg-red-100', text: 'text-red-700', icon: '🔖' }
    case 'multi_buy':
    case '2_for_1':
      return { bg: 'bg-orange-100', text: 'text-orange-700', icon: '🎁' }
    case 'promotional_price':
      return { bg: 'bg-green-100', text: 'text-green-700', icon: '✂️' }
    default:
      return { bg: 'bg-yellow-100', text: 'text-yellow-700', icon: '⭐' }
  }
})
</script>
