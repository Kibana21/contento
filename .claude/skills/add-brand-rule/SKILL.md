---
name: add-brand-rule
description: Add or change a brand, compliance or copy rule in the AIA Marketing Studio - a new validator check, a disclaimer requirement, a prohibited phrase, a risk trigger or a campaign family rule. Use when the user says "add a rule", "this should be rejected", "compliance wants X", "posters must always Y", or reports that something invalid passed validation.
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Grep
  - Glob
---

# Add or change a rule

Rules come in two kinds. Decide which before writing code.

## 1. Policy data (no code)

Anything Compliance or Marketing might change belongs in YAML:

- `knowledge/campaign-rules/families.yaml` — per-family risk, mandatory and blocking fields,
  required disclaimers, export presets, `risk_triggers`, `prohibited_terms`
- `knowledge/campaign-rules/festivals.yaml` — festival dates and whether they need confirming
- `knowledge/disclaimers/aia-sg-web-clauses.json` — the clause library (observed wording)

Change the YAML, then add a test in `tests/test_policy.py`. No Python change is needed for a
new prohibited phrase, a new trigger word, or a family that needs a different disclaimer.

## 2. A check (code)

Pick the layer that can actually observe the violation:

| Layer | File | Sees |
|---|---|---|
| Design structure | `src/validate/design.py` | the `DesignDoc` before rendering |
| Rendered page | `src/validate/dom.py` | exact geometry, computed colours, font sizes |
| Pixels | `src/validate/pixel.py` | the exported image |
| Wording | `src/validate/copy.py` | the `Copy` and the brief's facts |

Then:

1. **Give it a stable `rule_id`** in the existing `area.thing` style (`logo.clear_space`,
   `layout.text_collision`, `facts.invented`). It appears in `campaign.json` and in audits.
2. **Choose the severity honestly.** `error` blocks an export; `warn` informs. Reviewer
   findings from a model are always clamped to `warn`.
3. **Cite the source in a comment** — the Brand Standards page or the rule pack line.
4. **Write the failing test first** in `tests/test_validate.py` or `tests/test_copy.py`:
   construct a design or copy that deliberately breaks the rule and assert the `rule_id`
   appears. Then assert the clean fixtures still pass.
5. **Consider an auto-fix** in `src/concepts.py` `_auto_fix()` only if the repair is
   unambiguous and measurable (scale to fit, correct a logo colour). Never "fix" wording or
   anything factual — report it instead.

## Checks

```bash
.venv/bin/python -m pytest tests/test_validate.py tests/test_policy.py tests/test_copy.py -q
.venv/bin/python -m src.main create --agent profiles/demo-agent \
  --campaign campaigns/deepavali-2026 --non-interactive --no-images --no-review
```

The clean demo campaigns must still pass. A new rule that fails the existing fixtures usually
means the rule is wrong, or the fixtures encode a real defect worth fixing.

## Do not

- Do not let an LLM decide whether a rule passed. If a rule needs judgement, it is advisory.
- Do not hard-code brand values in Python — read them from `brand/aia-singapore/tokens/`.
- Do not mark observed wording as approved. Disclaimer clauses stay "observed" until AIA
  Compliance signs them off.
