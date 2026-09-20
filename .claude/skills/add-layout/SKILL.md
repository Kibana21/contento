---
name: add-layout
description: Change how AIA posters look - add a layout family or skeleton, extend the composition grammar, adjust the poster template, art direction, type, portraits or Moving Mountains. Use when the user says "the posters look X", "add a layout", "make it more premium", "the variations look too similar", or asks for a new visual treatment.
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Grep
  - Glob
---

# Change how posters look

Layout is a **hybrid**: four hand-built skeletons set the structure, and a bounded grammar
(`Composition`) varies composition inside them. All families render through **one** template,
`src/render/templates/composed.html.j2`. Do not add per-family templates — that path was
removed on purpose.

## Where to make which change

| Want | Change |
|---|---|
| A new look with its own defaults | a skeleton in `src/render/layouts.py` (`FAMILIES`) |
| A new dimension the director may vary | a field on `Composition` in `src/contracts/creative.py` **plus** its CSS in `composed.html.j2` |
| Different art direction for an existing look | that skeleton's `composition=` defaults |
| What appears on a poster at all | `src/render/design_builder.py` |
| Portrait treatment | `src/assets/portrait.py` (cut-out, framed on brand tint, shadow, duotone) |
| Brand graphic | `src/render/mountains.py` (shape sets, tint tables from tokens) |

## Adding a skeleton

1. Add to `FAMILIES` in `layouts.py`: `description`, `default_theme`, allowed `photo_modes`
   and `mountains`, slot map, `portrait_size`, `mountains_height`, a distinct `composition`,
   and `suits` (which campaign families it fits).
2. Its composition must be **visibly different** from the others — a test asserts every
   skeleton has a unique `(photo_shape, density, accent, mountains_placement)` signature.
3. Leave `template="composed"`.
4. The Creative Director picks it up automatically through `catalogue()`.

## Extending the grammar

Every field must be **bounded**: an enum or a range. If a model could produce an unusable
page with it, the bound is wrong. Add a `model_validator` for impossible combinations (as
with inverted mountains requiring a red ground), and add the CSS that honours it.

## Rules the template must keep

- Copy and portrait may never share grid columns — the builder clamps spans; keep the portrait
  a grid cell (only `full-bleed-right` leaves the grid, and it still clears the footer zone).
- The footer band needs an opaque backdrop so legal text stays legible over artwork.
- **Never** hyphenate or `break-word` a headline: it splits words mid-letter. Let it scale.
- No `!important` on anything the auto-fixer scales — it works through `overrides['scale']`.
- Jinja is `StrictUndefined`: `e.overrides.get('x') | default(y, true)`.
- Colours come from `brand.colour_hex(...)`, never hard-coded hex.

## Always look at the result

Validation passing is not the same as a poster reading well.

```bash
.venv/bin/python -m src.main create --agent profiles/demo-agent \
  --campaign campaigns/deepavali-2026 --non-interactive --no-images --no-review
```

Then build a contact sheet with Pillow (resize each `variation-*.png` to ~520px wide, paste
side by side on a neutral ground) and **read that image**. Check: does each variation look
genuinely different; is the hierarchy right; does the portrait sit naturally; is anything
crowded, clipped or floating.

Finally run `pytest tests/test_concepts.py tests/test_render.py tests/test_validate.py -q`.

## Known quality gaps (not bugs)

AIA Everest Bold and Condensed are missing, so headlines render in Medium. The Moving
Mountains shapes are our approximation until AIA supplies the vector library. Real agent
portraits are pending; the demo photo is synthetic.
