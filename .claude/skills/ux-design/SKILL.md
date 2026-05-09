---
name: ux-design
description: Use when choosing frontend UX, layout, spacing, typography, color, dashboard presentation, visual polish, or interaction patterns for this Garmin health app.
---

# UX Design

This project is a dense Garmin health, assistant, Today, and routine-management app. Prefer calm operational clarity over expressive landing-page design.

## Product Direction

- Build the usable product screen first; do not add marketing heroes or explanatory feature sections.
- Frontend analytics are display-only. Do not compute statistics, smoothing, derived values, exposure logic, or data transformations in Svelte.
- Favor scannable information density: compact headings, predictable controls, restrained cards, clear tables, and charts that can be compared quickly.
- Use `analytical-dashboard` before dashboard layout, chart selection, stat formatting, or data-density decisions.

## Visual System

- Keep cards for repeated items, chart panels, modals, and tool surfaces. Do not nest cards or turn full page sections into floating cards.
- Use stable dimensions for boards, charts, tiles, icon buttons, counters, and toolbars so state changes do not shift layout.
- Use the existing app typography and tokens unless there is a clear product reason to change them. Numeric data must use tabular lining figures.
- Color encodes metric identity, state, or action. Avoid decorative gradients, orbs, bokeh, and purple-blue default palettes.
- Text must fit at mobile and desktop widths. Compact panels need compact headings, not hero-scale type.

## Interaction Rules

- Use familiar controls: icon buttons for tools, segmented controls for modes, toggles for binary settings, inputs/sliders for numeric values, tabs for view changes, menus for option sets.
- Use lucide icons where available. Pair unfamiliar icon-only controls with tooltips.
- Today and schedule flows should optimize repeated daily use: low friction, clear status, visible next action.
- Assistant surfaces should make evidence and actions readable without implying that the frontend owns the underlying analysis.

## Validation

After frontend changes:

```bash
cd frontend && npm run check
```

Run the app and visually inspect every modified page/component with browser MCP screenshots. Confirm text fit, chart readability, empty/loading/error states, and mobile/desktop usability.
