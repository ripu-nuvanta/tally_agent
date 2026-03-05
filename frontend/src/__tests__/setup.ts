import "@testing-library/jest-dom/vitest";

// Mock react-markdown — jsdom can't handle ESM re-exports
vi.mock("react-markdown", () => ({
  default: ({ children }: { children: string }) => children,
}));

// Mock recharts ResponsiveContainer — needs real DOM dimensions
vi.mock("recharts", async () => {
  const actual = await vi.importActual<typeof import("recharts")>("recharts");
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
  };
});
