/**
 * Shared number-formatting utilities.
 * Port of chart_utils.py format_large_number() — keeps frontend display
 * consistent with the Python chart pipeline.
 */

/**
 * Abbreviate large numbers for compact display.
 *   1500       → "1.5k"
 *   1_000_000  → "1.0M"
 *   50         → "50"
 */
export function formatLargeNumber(value: number): string {
  if (value >= 1_000_000_000_000) return `${(value / 1_000_000_000_000).toFixed(1)}T`;
  if (value >= 1_000_000_000)     return `${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000)         return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000)             return `${(value / 1_000).toFixed(1)}k`;
  return String(Math.floor(value));
}
