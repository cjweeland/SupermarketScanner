<template>
  <div class="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
    <span class="text-xl shrink-0">⚠️</span>
    <div>
      <p class="font-medium text-red-800">{{ title }}</p>
      <p v-if="message" class="text-sm text-red-600 mt-1">{{ message }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{ title?: string; message?: string }>(),
  {
    title: 'Er is iets misgegaan',
    message: 'Controleer of de backend actief is en probeer opnieuw.',
  }
)
</script>
