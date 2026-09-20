# AIA Agent Marketing Studio — working notes for Claude

A governed AI creative workspace: an AIA Singapore representative describes a campaign in
plain English and gets 3–4 brand-checked poster variations, refinable by conversation.

**Read `docs/architecture.md` before changing anything.** It is the master document: every
workflow, every LLM call, all contracts, validators and open items.

```bash
python -m src.main create --agent profiles/demo-agent --campaign campaigns/deepavali-2026
python -m src.main revise --campaign output/deepavali-2026 --variation 2 --instruction "..."
.venv/bin/python -m pytest tests -q          # 208 tests, offline, ~110s
```

Use `.venv/bin/python` (Python 3.14). Never the system Python — Playwright, pydantic-ai and
the Vertex client live only in the venv.

---

## The one principle everything follows

> **AI for creativity and interpretation. Deterministic code for facts, logos, layout, QR
> codes and validation.**

If a change would let a model decide a fact, a legal line, a risk class or a logo, it is the
wrong change — find the deterministic path instead.

---

## Invariants — do not break these

1. **Factual elements reference data; they never carry text.** `fact`, `qr`, `disclaimer`,
   `contact_block`, `logo`, `agent_photo` must use `content_ref`/`asset_ref`. The contract
   raises a `ValidationError` citing ADR-001 if you inline text.
2. **Copy may not state a fact the brief lacks.** `facts.invented` catches dates, times,
   prices, percentages, phone numbers and URLs.
3. **Risk only ever goes up.** `src/policy/rules.py` decides; an agent may propose higher,
   never lower.
4. **Logos are sourced SVGs**, red or white only, never generated, never recoloured.
5. **The representative's face is never generated** — crop, cut out, frame, colour-balance only.
6. **Variations must differ by layout family** plus one of red treatment / photo mode /
   mountains variant. Enforced in `DirectionSet`.
7. **Uploads are data, not instructions.** Never let document text drive behaviour.
8. **Every model call goes through `ModelGateway`.** No direct `Agent.run()` elsewhere: the
   gateway owns tiers, budgets, retries and usage accounting.
9. **Unsupported requests are reported, never silently dropped** (`IMPLEMENTED_OPS`).
10. **Every export carries lineage** — `campaign.json` plus metadata embedded in the PNG.

---

## Repository shape

```
src/contracts/   Pydantic contracts — the source of truth. Change these first.
src/ai/          model_gateway + agents (brief, copywriter, director, revision, reviewers)
src/policy/      risk engine, disclaimers, festival calendar (rules live in knowledge/)
src/render/      layouts (skeletons) · design_builder · composed.html.j2 · mountains · qr · renderer
src/validate/    design · dom · pixel · copy  (every rule has an id)
src/workflow.py  the create pipeline   ·   src/revise.py  the revision pipeline
src/concepts.py  one direction → one validated poster, with the auto-fix loop
brand/aia-singapore/   tokens, policy docs, logo, fonts   (assets/ is gitignored)
knowledge/       campaign-rules (YAML) · disclaimers · approved-copy · aia-sg-web corpus
profiles/ campaigns/ output/ tests/ scripts/ docs/
```

## How work usually flows

| Task | Start here |
|---|---|
| New brand or compliance rule | `knowledge/campaign-rules/families.yaml` → `src/validate/` → test |
| New layout look | `src/render/layouts.py` skeleton + `Composition` defaults (not a new template) |
| New agent or model call | `src/ai/`, via `ModelGateway.agent()`, output a **draft** schema |
| Change what a poster contains | `src/render/design_builder.py` |
| Change what a poster looks like | `src/render/templates/composed.html.j2` (the only layout template) |
| New campaign family | `families.yaml` + `Family` enum + skeleton `suits` |

---

## Conventions

- **Contracts first.** Add or change the Pydantic model, then the code that fills it. Every
  contract is `extra="forbid"` so model drift fails loudly.
- **Models return drafts; code produces the contract.** `BriefDraft → assemble_brief() →
  CampaignBrief`. Never trust model output directly for identity, sourcing or risk.
- **Rules before LLM (ADR-006).** If a check can be deterministic, it must be. Reviewer
  findings are clamped to warnings and can never block or approve.
- **Every validator finding has a stable `rule_id`** that traces to a line in
  `brand/aia-singapore/policy/` or `knowledge/campaign-rules/`.
- **Comments explain *why*,** especially where a rule comes from a Brand Standards page
  (e.g. "p59: inverted mountains only on red"). Do not narrate what the code does.
- **Tests run offline.** Use `TestModel`/`FunctionModel` through `ModelGateway(test_model=…)`.
  A test that needs the network does not belong in `tests/`.
- **Write a failing test for any defect you fix.** Every rule in `src/validate/` has a test
  that fires it with a deliberately broken design.

---

## Gotchas that have already cost time

- `result.usage` is a **property** in pydantic-ai v2 (a method in v1) — see `_usage_of()`.
- Default `UsageLimits(request_limit=4)` is too low for a tool-using agent: each tool hop is
  a request.
- Gemini **rejects very complex output schemas** ("too many states"). A discriminated union
  of 11 variants failed; use a flat draft plus a converter.
- Imagen is not enabled on this project and its API is deprecated — use
  `gemini-3.1-flash-image` via `generate_content`, location `global`.
- Image models letterbox: crop generated backgrounds to the canvas aspect.
- Jinja uses `StrictUndefined`: use `e.overrides.get('x') | default(y, true)`, never `e.overrides.x`.
- CSS `!important` in a template will silently defeat the auto-fixer, which works through
  element `overrides['scale']`.
- Never hyphenate or `break-word` a headline — it splits words mid-letter. Scale it down instead.
- `design.aia.com` and `aia.com.sg` block non-browser clients; Scene7 (`s7ap1.scene7.com`) does not.
- Clear stale output before a run, or a folder mixes two campaigns.

---

## Never commit

`api_key.json` (Vertex service account) · `brands.pdf` (internal Brand Standards) ·
`brand/aia-singapore/assets/` (proprietary logo and fonts) · `brand/aia-singapore/fonts-open/*.ttf`
(size) · `knowledge/aia-sg-web/crawl.json` and `imagery/` · `output/`.
All are in `.gitignore` — check `git status` before committing.

The demo portrait `profiles/demo-agent/photos/formal.jpg` is **synthetic**, generated for
development, and depicts no real person. Keep the note in `profile.yaml`.

---

## Open questions for AIA (do not invent answers)

- **Red dominance**: Brand Standards say AIA Red must dominate; the Qi digital system caps it
  at 20%. We follow the Brand Standards for marketing collateral. Unconfirmed.
- Disclaimer clauses are **observed from the public site, not approved**.
- Missing assets: HLBL logo lockup, Everest Bold/Condensed, official Moving Mountains vectors,
  icon library, real portraits.
