/**
 * Format a number in Indian comma style: 12,34,567.00
 */
export function formatIndianNumber(num: number): string {
  const [intPart, decPart] = Math.abs(num).toFixed(2).split(".");
  const lastThree = intPart.slice(-3);
  const rest = intPart.slice(0, -3);
  const formatted =
    rest.length > 0
      ? rest.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + "," + lastThree
      : lastThree;
  const sign = num < 0 ? "-" : "";
  return `${sign}${formatted}.${decPart}`;
}

/**
 * Format as Indian Rupees: ₹12,34,567.00
 */
export function formatINR(num: number): string {
  const sign = num < 0 ? "-" : "";
  return `${sign}₹${formatIndianNumber(Math.abs(num))}`;
}

/**
 * Smart axis formatter: ₹1.2Cr, ₹5.3L, ₹45K, ₹800
 */
export function formatAxisAmount(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1_00_00_000) return `${sign}₹${(abs / 1_00_00_000).toFixed(1)}Cr`;
  if (abs >= 1_00_000) return `${sign}₹${(abs / 1_00_000).toFixed(1)}L`;
  if (abs >= 1_000) return `${sign}₹${(abs / 1_000).toFixed(0)}K`;
  return `${sign}₹${abs.toFixed(0)}`;
}

/**
 * Check if a value looks numeric.
 */
export function isNumericValue(val: unknown): val is number {
  return typeof val === "number" && !isNaN(val);
}

/**
 * Generate a unique ID for messages.
 */
export function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}
