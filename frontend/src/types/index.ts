export interface Promo {
  type: string
  description: string
  promo_price_cents: number | null
  requires_membership: boolean
  valid_until: string | null
}

export interface StorePrice {
  store_slug: string
  store_name: string
  store_color: string
  price_cents: number
  price_formatted: string
  unit_price_cents: number | null
  unit_price_formatted: string | null
  unit_label: string | null
  promotion: Promo | null
  product_url: string | null
  image_url: string | null
  freshness: 'live' | 'stale'
}

export interface ComparisonResult {
  product_name: string
  brand: string | null
  category_slug: string | null
  prices: StorePrice[]
  best_value_store: string | null
  best_value_after_promo_store: string | null
}

export interface CompareMeta {
  query: string
  category: string | null
  stores_queried: string[]
  total: number
  generated_at: string
}

export interface CompareResponse {
  data: ComparisonResult[]
  meta: CompareMeta
}

export interface Category {
  slug: string
  label: string
  icon: string
  store_type: 'supermarket' | 'drugstore'
  product_count: number
}

export interface StoreStatus {
  slug: string
  display_name: string
  type: 'supermarket' | 'drugstore'
  color: string
  last_scraped: string | null
  scrape_status: string
  product_count: number
}
