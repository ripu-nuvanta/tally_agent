import { describe, it, expect } from "vitest";
import { formatIndianNumber, formatINR, isNumericValue, generateId } from "../utils/format";

describe("formatIndianNumber", () => {
  it("formats small numbers", () => { expect(formatIndianNumber(100)).toBe("100.00"); });
  it("formats thousands", () => { expect(formatIndianNumber(1234)).toBe("1,234.00"); });
  it("formats lakhs", () => { expect(formatIndianNumber(123456)).toBe("1,23,456.00"); });
  it("formats crores", () => { expect(formatIndianNumber(12345678)).toBe("1,23,45,678.00"); });
  it("handles negative numbers", () => { expect(formatIndianNumber(-1234567)).toBe("-12,34,567.00"); });
  it("handles zero", () => { expect(formatIndianNumber(0)).toBe("0.00"); });
  it("handles decimals", () => { expect(formatIndianNumber(1234.56)).toBe("1,234.56"); });
});

describe("formatINR", () => {
  it("adds rupee symbol", () => { expect(formatINR(1234567)).toBe("₹12,34,567.00"); });
  it("handles negative with sign before symbol", () => { expect(formatINR(-5000)).toBe("-₹5,000.00"); });
});

describe("isNumericValue", () => {
  it("returns true for numbers", () => { expect(isNumericValue(42)).toBe(true); expect(isNumericValue(0)).toBe(true); expect(isNumericValue(-3.14)).toBe(true); });
  it("returns false for NaN", () => { expect(isNumericValue(NaN)).toBe(false); });
  it("returns false for non-numbers", () => { expect(isNumericValue("42")).toBe(false); expect(isNumericValue(null)).toBe(false); expect(isNumericValue(undefined)).toBe(false); });
});

describe("generateId", () => {
  it("returns a string", () => { expect(typeof generateId()).toBe("string"); });
  it("generates unique values", () => { const ids = new Set(Array.from({ length: 100 }, () => generateId())); expect(ids.size).toBe(100); });
});
