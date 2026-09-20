---
name: run-campaign
description: Run or debug an AIA Marketing Studio campaign end to end - create posters from a request, revise a variation, inspect why a variation failed validation, or check token spend. Use when the user says "run a campaign", "generate posters", "revise variation 2", "why did this fail", "what did it cost", or points at a folder in output/.
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
---

# Run or debug a campaign

## Create

```bash
.venv/bin/python -m src.main create \
  --agent profiles/demo-agent \
  --campaign campaigns/<name> \
  [--preset instagram_portrait|instagram_story|whatsapp_portrait|a4_print] \
  [--non-interactive] [--no-images] [--no-review] [--max-tokens 120000]
```

- `--no-images --no-review` makes a run fast and free of image spend. Use it while iterating
  on layout or validators.
- Interactive runs let the Brief Agent ask up to two questions in the terminal.
- A new campaign needs only `campaigns/<name>/request.md` (free text) and optional `assets/`.

## Revise

```bash
.venv/bin/python -m src.main revise --campaign output/<name> --variation 2 \
  --instruction "make my photo smaller and shorten the headline"
```

`--variation` takes `1|2|3|4` or `a|b|c|d`. A text or layout edit makes one fast-tier call
and **no** image call. Changing a fact or the copy re-renders every variation.

## When a variation fails

1. Read the findings, not the image:
   ```bash
   .venv/bin/python -c "import json;d=json.load(open('output/<name>/validation/variation-a.json'));
   print([(f['rule_id'], f['element_id'], f['message']) for f in d['findings']])"
   ```
2. Every `rule_id` maps to a check in `src/validate/` — `design.py` (structure),
   `dom.py` (rendered geometry, contrast, collisions), `pixel.py` (red dominance),
   `copy.py` (wording).
3. For layout problems, inspect the measured page rather than guessing:
   ```bash
   .venv/bin/python -c "import json;g=json.load(open('output/<name>/variation-a.geometry.json'));
   [print(f\"{e['id']:12} {e['x']:6.0f},{e['y']:6.0f} {e['width']:6.0f}x{e['height']:6.0f} over={e['overflows']} out={e['outsideCanvas']}\") for e in g['elements']]"
   ```
4. Open `output/<name>/variation-a.html` to see exactly what was rendered.
5. Compare variations quickly by building a contact sheet with Pillow and viewing that one
   image, rather than opening four.

**Read the poster PNG itself** before deciding a layout is fine. Validation passing is not
the same as the design reading well.

## Cost

`output/<name>/usage.json` has every call; `campaign.json` carries `usage_summary`.
Typical: create without images 12k–20k tokens; with backgrounds and review 26k–33k;
a revision under 10k. Budgets default to 120k tokens and 6 images per run.

## Rules of thumb

- Stale files mislead: a run clears the campaign folder first, so a leftover `variation-d.png`
  means the last run produced fewer variations than the one before.
- Three variations for a seminar is correct — only three layout families suit that family.
- Visual reviewer findings are advisory warnings and never block an export.
