---
name: update-brand-pack
description: Update the AIA brand pack - colour, typography, logo rules, Moving Mountains, tone of voice, or newly supplied assets such as the HLBL lockup, Everest Bold or the official mountains vectors. Use when the user says "AIA sent the fonts", "the logo file arrived", "update the brand colours", "compliance approved X", or asks what the brand pack is missing.
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Grep
  - Glob
---

# Update the brand pack

`brand/aia-singapore/` is the machine-readable AIA brand. Two halves:

- `tokens/*.json` — data the code reads: `colour`, `typography`, `spacing`, `logo`,
  `moving-mountains`
- `policy/*.md` — the written rules, used as reviewer rubrics and as the audit trail for
  every validator `rule_id`

`assets/` (logo SVGs, Everest fonts) and `fonts-open/*.ttf` are **gitignored** — proprietary
or large.

## Provenance is mandatory

Every value carries where it came from:

| Label | Meaning |
|---|---|
| `published` | stated in a source document |
| `sampled` | read from swatch pixels |
| `observed-css` | taken from a live stylesheet |
| `proposed` | our assumption — **needs AIA sign-off** |

Never quietly promote `proposed` to `published`. If AIA confirms something, change the label
and say so in the file.

## Precedence (do not reorder)

AIA Singapore internal rules → **Brand Standards v2.0** (marketing) → AIA Qi (digital UI).

The live conflict: Brand Standards require AIA Red `#D31145` to dominate; Qi caps digital red
`#E00842` at 20%. We follow the Brand Standards for marketing collateral. Unconfirmed — do
not "resolve" it without AIA.

## When new assets arrive

| Asset | Where it goes | Then |
|---|---|---|
| HLBL logo lockup SVG | `assets/logos/` | set it in `tokens/logo.json`, switch `default_variant` to `hlbl_lockup`, update `policy/logo-rules.md` |
| Everest Bold / Condensed | `assets/fonts/` | add to `tokens/typography.json` `families.display.files`, register the `@font-face` in `templates/base.html.j2`, set `licensed_files_available` |
| Moving Mountains vectors | `assets/moving-mountains/` | replace the hand-built `SHAPE_SETS` in `src/render/mountains.py`; keep the tint and opacity tables |
| Icon or illustration library | `assets/icons/`, `assets/illustrations/` | reference from the design builder; they remain off-limits to image generation |

Fonts: AIA Everest is proprietary and needs a signed font release before it is shared with
any third party. Keep it out of anything that leaves AIA.

## Checks

```bash
.venv/bin/python -c "import json,glob;[json.load(open(f)) for f in glob.glob('brand/aia-singapore/tokens/*.json')];print('tokens ok')"
.venv/bin/python -m pytest tests/test_loaders.py tests/test_validate.py -q
.venv/bin/python -m src.main create --agent profiles/demo-agent \
  --campaign campaigns/deepavali-2026 --non-interactive --no-images --no-review
```

Then look at a poster: a token change that passes tests can still ruin contrast or hierarchy.

## Re-fetching source material

`design.aia.com` and `aia.com.sg` block non-browser clients — use the Chrome extension, slowly
(one page every 2.5s), or the site's firewall will rate-limit you for up to an hour.
Scene7 (`s7ap1.scene7.com`) serves imagery directly to curl. `scripts/fetch_web_imagery.py`
and `scripts/build_web_corpus.py` rebuild the imagery and text corpora.

Known gap: that fetch script saves every image as JPEG because the Scene7 alpha check
mis-parses the response, so cut-out illustrations lost transparency. One-line fix plus a
re-fetch of the alpha assets.
