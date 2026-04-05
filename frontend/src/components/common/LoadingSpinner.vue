<template>
  <div class="flex flex-col items-center justify-center py-12 gap-3">
    <div class="animate-spin rounded-full h-10 w-10 border-2 border-gray-200 border-t-primary-600" />
    <p class="text-sm text-gray-500">{{ message }}</p>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ message?: string }>(), {
  message: 'Prijzen worden opgehaald...',
})
</script>
