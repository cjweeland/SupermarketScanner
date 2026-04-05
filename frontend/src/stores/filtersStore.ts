import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const ALL_STORES = {
  supermarket: ['albert_heijn', 'jumbo', 'lidl', 'dirk', 'plus'],
  drugstore: ['kruidvat', 'trekpleister', 'etos'],
}

export const useFiltersStore = defineStore('filters', () => {
  const activeStores = ref<Set<string>>(
    new Set([...ALL_STORES.supermarket, ...ALL_STORES.drugstore])
  )
  const activeCategory = ref<string | null>(null)
  const activeStoreType = ref<'all' | 'supermarket' | 'drugstore'>('all')

  const activeStoreList = computed(() => [...activeStores.value])

  const activeStoresForType = computed(() => {
    if (activeStoreType.value === 'all') return activeStoreList.value
    const typeSlugs = ALL_STORES[activeStoreType.value] || []
    return activeStoreList.value.filter((s) => typeSlugs.includes(s))
  })

  function toggleStore(slug: string) {
    if (activeStores.value.has(slug)) {
      activeStores.value.delete(slug)
    } else {
      activeStores.value.add(slug)
    }
  }

  function setCategory(slug: string | null) {
    activeCategory.value = slug
    // Pas winkeltype automatisch aan op basis van categorie
    if (slug) {
      const supermarktSlugs = [
        'vlees_vleeswaren', 'kaas', 'koffie_thee', 'wasmiddel',
        'pasta_rijst_sauzen', 'ontbijtgranen_muesli', 'boter', 'yoghurt_kwark', 'toiletpapier',
      ]
      if (supermarktSlugs.includes(slug)) {
        activeStoreType.value = 'supermarket'
      } else {
        activeStoreType.value = 'drugstore'
      }
    }
  }

  function setStoreType(type: 'all' | 'supermarket' | 'drugstore') {
    activeStoreType.value = type
    activeCategory.value = null
  }

  function resetFilters() {
    activeStores.value = new Set([...ALL_STORES.supermarket, ...ALL_STORES.drugstore])
    activeCategory.value = null
    activeStoreType.value = 'all'
  }

  return {
    activeStores,
    activeCategory,
    activeStoreType,
    activeStoreList,
    activeStoresForType,
    toggleStore,
    setCategory,
    setStoreType,
    resetFilters,
    ALL_STORES,
  }
})
