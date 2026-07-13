---
name: flask-theme-color-picker
description: Build a "pick one base color, auto-generate a matching UI theme palette" feature for a Flask + SQLite + plain HTML/CSS/JS web app. Use this whenever the user wants a color/theme picker, brand color customizer, palette generator, or "let users choose app colors" feature — even if they just say "color picker," "theming," or "customize app colors." Covers palette generation with colorsys, WCAG contrast-safe adjustments, live CSS-variable preview, and SQLite persistence.
---

# Flask Theme Color Picker

Builds a full feature: user picks ONE base color → app generates a matching palette → applies it live via CSS variables → saves it to SQLite so it persists.

Stack assumptions (adjust only if the user's project clearly differs): Flask backend, SQLite persistence, plain HTML/CSS/JS frontend (no build step, no JS framework).

## Build order

Always implement in this order and check in with the user after step 1 before continuing, since the palette quality drives everything downstream.

### 1. Palette generation (Python, `colorsys`, stdlib only)

Given a hex base color, generate in HSL space (convert hue/lightness/saturation, keep hue fixed unless generating the accent):

- `primary`: the base color itself
- `primary_light`, `primary_dark`: same hue/saturation, lightness shifted for hover/border states
- `accent`: complementary or analogous hue (base hue ± 30° or +180°)
- `background`, `text`: near-white / near-black tinted very slightly toward the base hue
- `gray_scale`: 3-5 step neutral scale, low saturation, same hue tint

Write this as a standalone function first and test it with 3-4 sample hex colors (e.g. `#3B82F6`, `#EF4444`, `#10B981`) — print the results so the user can eyeball them before wiring up any UI.

### 2. Accessibility pass

For every text/background pair the palette produces, compute WCAG contrast ratio. If it's below 4.5:1 (normal text) or 3:1 (large text), programmatically adjust lightness until it passes, rather than rejecting the color outright. Flag any pair that still fails after adjustment.

### 3. Flask routes

- `POST /api/generate-palette` — body: `{ "base_color": "#3B82F6" }` → returns full palette JSON
- `POST /api/save-theme` — persists base color + palette JSON to SQLite, scoped to user/session
- `GET /api/theme` — loads the saved theme (or returns a sensible default if none saved)

SQLite table: `theme(id, user_id, base_color, palette_json, created_at)`. Use stdlib `sqlite3` unless the project already has an ORM in use — don't introduce one just for this.

### 4. Frontend (plain HTML/CSS/JS)

- `<input type="color">` or custom swatch picker for the base color, plus a few preset swatches
- Live preview panel (sample buttons/cards/navbar) that updates as the color changes, debounced ~100-150ms via `setTimeout` while dragging
- On change: `fetch` the generated palette, then apply it as CSS custom properties on `document.documentElement` (`--color-primary`, `--color-primary-light`, `--color-accent`, `--color-bg`, `--color-text`) so the whole app re-themes instantly
- CSS `transition` on color variables so the theme change isn't a jarring flash
- Palette swatches shown with hex codes, click-to-copy with a small confirmation toast
- "Apply" button calls `/api/save-theme`; page load calls `/api/theme` to restore it
- "Reset to default" option
- Mobile-responsive via flexbox/grid, no framework

## Notes

- Don't add a CSS/JS framework or an ORM unless the project already uses one — keep it dependency-light per the stack assumption above.
- If the user's actual project differs from these assumptions (different backend framework, different persistence, or a JS framework in use), adapt steps 3-4 accordingly but keep the palette logic in step 1 the same — it's backend-agnostic.
