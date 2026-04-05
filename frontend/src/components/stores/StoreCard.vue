<template>
  <div class="card p-4">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <!-- Kleurbol -->
        <div
          class="h-10 w-10 rounded-full flex items-center justify-center text-white font-bold text-sm shrink-0"
          :style="{ backgroundColor: store.color }"
        >
          {{ store.display_name[0] }}
        </div>

        <div>
          <p class="font-semibold text-gray-900">{{ store.display_name }}</p>
          <div class="flex items-center gap-2 mt-0.5">
            <!-- Status indicator -->
            <span
              :class="[
                'inline-flex items-center gap-1 text-xs font-medium',
                statusStyle.color,
              ]"
            >
              <span>{{ statusStyle.icon }}</span>
              {{ statusStyle.label }}
            </span>
            <span class="text-xs text-gray-400">
              {{ store.product_count }} producten
            </span>
          </div>
          <!-- Laatste scan tijd -->
          <p v-if="store.last_scraped" class="text-xs text-gray-400 mt-0.5">
            Bijgewerkt: {{ formatTime(store.last_scraped) }}
          </p>
          <p v-else class="text-xs text-gray-400 mt-0.5">Nog niet gescand</p>
        </div>
      </div>

      <!-- Scan knop -->
      <button
        @click="$emit('refresh')"
        class="text-sm text-primary-600 hover:text-primary-700 font-medium shrink-0"
      >
        ↻
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { StoreStatus } from '@/types'

const props = defineProps<{ store: StoreStatus }>()
defineEmits<{ refresh: [] }>()

const statusStyle = computed(() => {
  switch (props.store.scrape_status) {
    case 'ok':
      return { icon: '✅', label: 'Actueel', color: 'text-green-600' }
    case 'partial':
      return { icon: '⚠️', label: 'Gedeeltelijk', color: 'text-amber-600' }
    case 'error':
      return { icon: '❌', label: 'Fout', color: 'text-red-600' }
    case 'pending':
      return { icon: '⏳', label: 'Wacht op scan', color: 'text-gray-500' }
    default:
      return { icon: '❓', label: props.store.scrape_status, color: 'text-gray-400' }
  }
})

function formatTime(isoString: string): string {
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'Zojuist'
  if (diffMin < 60) return `${diffMin} min geleden`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24) return `${diffH} uur geleden`
  return date.toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}
</script>
