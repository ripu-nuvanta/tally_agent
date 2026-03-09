# Playwright Test Consolidation Design

**Date**: 2026-03-09
**Status**: Approved

## Problem

Two separate Playwright test suites with different configs, different screenshot strategies, and different output locations. Eval-visual tests only run at desktop viewport and take element-specific screenshots instead of full-message screenshots.

## Design

### Directory Structure

```
frontend/tests/playwright/
├── playwright.config.ts      # single config, 3 viewport projects
├── responsive.spec.ts        # 5 responsive tests (empty/error/markdown/table/chart)
├── eval-visual.spec.ts       # 5 eval fixture tests with full-message screenshots
├── fixtures/
│   └── eval_responses.json   # symlinked from src/__tests__/fixtures/
└── __screenshots__/
    ├── desktop/
    ├── tablet/
    └── mobile/
```

### Config

Single `playwright.config.ts` with 3 viewport projects:
- Mobile: 375×667
- Tablet: 768×1024
- Desktop: 1280×900

Both spec files run across all 3 viewports.

### Screenshot Strategy

- **Responsive tests**: Full-page `expect(page).toHaveScreenshot()` for pixel-diff regression (unchanged).
- **Eval-visual tests**: Full message bubble via `.screenshot()` on the assistant message element. Playwright captures the full element even when taller than viewport — no scrolling needed. No separate table/chart screenshots; the full bubble captures everything together.
- **Timestamped output**: Eval-visual screenshots saved to `test-results/eval-visual-{timestamp}/` for artifact collection.

### npm Scripts

```json
"test:playwright": "npx playwright test --config tests/playwright/playwright.config.ts",
"test:all": "vitest run && npm run test:playwright"
```

Removes `test:responsive` and `test:eval-visual`.

### Migration

1. Create `frontend/tests/playwright/` directory
2. Move responsive tests and eval-visual tests into it
3. Create unified config
4. Update eval-visual to use full-message `.screenshot()` across all viewports
5. Symlink fixture file
6. Delete old directories and configs
7. Update `package.json` scripts
8. Update `test:all` in root if applicable
