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
