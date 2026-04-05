/**
 * Formatteert eurocenten naar een leesbare prijsstring in NL-formaat.
 * Bijv. 199 → "€ 1,99"
 */
export function formatPrice(cents: number): string {
  const euros = cents / 100
  return new Intl.NumberFormat('nl-NL', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
  }).format(euros)
}

/**
 * Formatteert een eenheidsprijs.
 * Bijv. 160 centen per 100g → "€ 1,60 / 100g"
 */
export function formatUnitPrice(cents: number | null, label: string | null): string {
  if (!cents || !label) return ''
  return `${formatPrice(cents)} / ${label.replace('per ', '')}`
}

/**
 * Berekent de procentuele korting.
 */
export function discountPercent(originalCents: number, promoCents: number): number {
  if (originalCents <= 0) return 0
  return Math.round((1 - promoCents / originalCents) * 100)
}
