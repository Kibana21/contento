# Free-form engine — technical implementation

**Companion to** `docs/freeform-engine.md` (what it is and why) and the approved plan.
**Status:** Phase 0 and half of Phase 1 are built · 271 tests passing · branch `freeform-engine`

This document is the build spec: exact modules, signatures, contracts and test plan.

---

## 0. Four gaps the plan did not close

The plan was complete on direction and governance. Building it surfaced four specification
gaps. One is a first-order design problem.

### G1 — The two authoring agents must agree on class names *(the important one)*

The Art Director writes `.speaker-portrait { border-radius: 50% }`. The Page Composer writes
`class="speaker-photo"`. The page renders **unstyled**, passes every validator that checks text
and geometry, and looks broken. Nothing in the plan prevented this, and with two independent LLM
calls it would happen constantly.

**Fix: a closed shared vocabulary, plus declared extensions.**

```python
#: src/freeform/vocabulary.py — the design-system API both agents code against.
CORE_CLASSES = frozenset({
    # structure
    "page", "band", "stack", "row", "grid", "spacer",
    # a repeating content module (benefit, speaker, step)
    "module", "module-media", "module-label", "module-role", "module-body",
    # type
    "headline", "headline-accent", "subheadline", "body", "eyebrow",
    # furniture
    "cta", "chip", "badge", "divider", "detail-row", "detail-icon",
    "portrait", "logo", "legal", "qr", "mountains", "backdrop",
})
MAX_CUSTOM_CLASSES = 8
```

- The **Art Director** styles these and may declare up to 8 extras in
  `DesignSystem.custom_classes`.
- The **Page Composer** is handed `CORE_CLASSES | custom_classes` and may use nothing else.
- The **binder enforces it**: every class token in the HTML must be in the vocabulary
  (`css.unknown_class`, error), and every selector in the CSS must target a class in the
  vocabulary (`css.orphan_selector`, error). A class styled but never used is a warning.

This turns an invisible failure into a caught one, and it is what lets the two calls be made
independently — which is what keeps them cheap.

### G2 — `content.*` reference grammar

`RenderContext.resolve()` does `ref.partition(".")`, so the namespace splits off and the
remainder arrives whole. `content.speakers.1.label` → namespace `content`, key
`speakers.1.label`. Grammar: `content.<kind>.<index>.<field>`, index an integer, field one of
`label|role|body|value|icon`. Out-of-range index or unknown field raises `UnresolvedReference`,
which the binder converts to a finding. `<kind>` must be plural and match `ContentItem.kind + "s"`.

### G3 — Long-form pages need a measured height

A variable-height canvas cannot be known before rendering. **Two-pass render:**

1. Pass 1 — viewport `width × min_height`, `.poster { height: auto }`. Read
   `document.querySelector('.poster').scrollHeight`.
2. Clamp to `[canvas.width, canvas.width * 4]`, snap up to a multiple of 4 (the brand soft grid).
3. Pass 2 — viewport at the settled height, re-render, measure, screenshot.

Two passes, not one screenshot of a tall element: it keeps `outsideCanvas` meaningful, keeps the
pixel analysis aligned with the geometry, and makes the height a recorded number rather than a
side effect. Cost is one extra Chromium page load (~0.4s), no extra model call.

### G4 — Generated backgrounds and portraits on this path

- `generate_background()` takes a `CreativeDirection`, which free-form does not have. Extract the
  body into `generate_from_prompt(gateway, prompt, out_dir, *, name, aspect_ratio, enabled)` and
  have the existing function call it. The current engine is untouched.
- **Portraits: always bind the cut-out; shaping is CSS.** `assets/portrait.framed()` pre-bakes a
  tinted panel because the structured engine cannot express one. Free-form can: a cut-out PNG on
  a `background: var(--red-20)` div with `border-radius` gives the same look with more range and
  no image processing. So `data-asset="profile.photo.<id>"` always resolves to the cut-out.

---

## 1. Module map

```
src/freeform/
├── __init__.py
├── vocabulary.py      CORE_CLASSES, element-type derivation table          [G1]
├── html_parse.py      strict recogniser -> Node tree                       ✅ BUILT
├── css.py             property/value allowlist, selector grammar, serialise ✅ BUILT
├── contracts.py       DesignSystem, PagePlan, Storyboard, FreeformPage, FreeformDoc
├── binder.py          Node tree + CssRule[] + RenderContext -> BoundPage
├── assets.py          data-asset resolution; icon catalogue
├── audit.js           render-time audit (pseudo-content, round-trip, occlusion)
├── renderer.py        two-pass render, audit, N pages, pypdf merge
├── repair.py          deterministic inline-style repair
├── engine.py          one variation: plan -> system -> compose -> bind -> render -> repair
├── pipeline.py        create_freeform_campaign()  (mirrors workflow.py)
└── fixtures.py        hand-authored pages for offline tests

src/ai/
├── content_architect.py    ContentSetDraft
├── narrative_planner.py    StoryboardDraft
├── art_director.py         DesignSystemSetDraft   (all variations in one call)
└── page_composer.py        FreeformPageDraft      (one call per page)

src/contracts/content.py     ContentItem, ContentSet
src/validate/spec.py         ElementSpec                                    ✅ BUILT
src/validate/freeform.py     authored-document checks + audit findings
src/validate/repair.py       shared shrink_ratio()
```

**Modified, surgically:** `validate/dom.py` ✅ · `validate/__init__.py` ✅ ·
`render/context.py` (add `content.`; fix the silent `profile.` miss) ·
`contracts/brief.py` (optional `content` field) · `ai/model_gateway.py` (`authoring` tier) ·
`ai/brief_agent.py` (`extract_modules` tool) · `assets/background.py` (extract
`generate_from_prompt`) · `lineage/record.py` (optional page fields) · `main.py` (`design` command)

**Reused unchanged:** `ModelGateway` · `policy/rules.py` · `validate/copy.py` ·
`validate/pixel.py` · `validate/colour.py` · `render/qr.py` · `render/mountains.py` ·
`assets/portrait.py` · `loaders.py` · `concepts.build_concept` (as the quality floor)

---

## 2. Contracts

```python
# src/contracts/content.py
class ContentItem(Strict):
    id: str                       # "speaker-1", "benefit-3"
    kind: Literal["benefit", "speaker", "chip", "step", "stat", "quote", "detail_row"]
    label: str | None = None
    role: str | None = None
    body: str | None = None
    value: str | None = None
    icon: str | None = None       # a name from the icon catalogue
    asset_ref: str | None = None
    source: str                   # REQUIRED, no default — the structural guarantee
    verbatim: bool = False
    locked: bool = True

class ContentSet(Strict):
    items: list[ContentItem] = Field(default_factory=list, max_length=24)
    def group(self, kind: str) -> list[ContentItem]: ...
```

`source` having no default means no code path can build a `ContentItem` without stating where
its text came from. Required for any item containing a digit: `verbatim=True`.

```python
# src/freeform/contracts.py
class DesignSystem(Strict):
    variation_id: str = Field(pattern=r"^[a-d]$")
    name: str
    archetype: Literal["benefit-grid", "speaker-roster", "editorial-feature",
                       "chip-index", "fullbleed-hero"]
    ground: Literal["bold", "light"]
    type_pairing: Literal["display-led", "editorial", "compact", "monumental"]
    primary_motif: Literal["hairline-rule", "circular-badge", "pill", "ring",
                           "arch-frame", "column-rule", "chip-row", "swoosh"]
    grid_columns: int = Field(ge=4, le=12)
    image_treatment: Literal["cutout", "panel", "full-bleed", "none"]
    custom_classes: list[str] = Field(default_factory=list, max_length=8)
    rules: list[CssRule] = Field(default_factory=list, max_length=120)

    @property
    def signature(self) -> tuple:
        return (self.archetype, self.ground, self.type_pairing,
                self.primary_motif, self.image_treatment)

    @property
    def vocabulary(self) -> frozenset[str]:
        return CORE_CLASSES | frozenset(self.custom_classes)

class DesignSystemSet(Strict):
    systems: list[DesignSystem] = Field(min_length=3, max_length=4)
    # validators, mirroring DirectionSet._materially_different:
    #   unique signatures · unique archetypes · >=1 bold and >=1 light
    #   · >=3 distinct primary_motif across 4

class PagePlan(Strict):
    index: int = Field(ge=1, le=3)
    purpose: Literal["hook", "benefits", "proof", "details", "cta", "invite"]
    shape: Literal["preset", "long_form"] = "preset"
    preset: str = "instagram_portrait"
    must_include: list[str] = Field(default_factory=list)   # refs, each exactly once
    content_ids: list[str] = Field(default_factory=list)

class Storyboard(Strict):
    pages: list[PagePlan] = Field(min_length=1, max_length=3)
    rationale: str = Field(max_length=300)
    # validators: page 1 includes copy.headline and a brand.logo.*
    #             the last page includes policy.disclaimer (when one is required)

class FreeformPage(Strict):
    plan: PagePlan
    html: str                                  # parsed by the recogniser, not by the schema
    rules: list[CssRule] = Field(default_factory=list, max_length=80)

class FreeformDoc(Strict):
    """What replaces DesignDoc on this path. Persisted; diffable per declaration."""
    doc_id: str
    campaign_id: str
    variation_id: str
    version: int = 1
    parent_version: int | None = None
    system: DesignSystem
    pages: list[FreeformPage]
    brand_pack_version: str = "0.2"
    language: str = "en"
```

**Why HTML is `str` and CSS is structured.** A recursive `Node` model under `extra="forbid"` is
exactly the shape that produced Gemini's *"schema produces a constraint that has too many
states"* on the 11-variant `EditOp` union. So the schema stays flat: strictness for HTML lives in
the recogniser, and CSS is structured because `list[CssRule]` is flat and buys `!important`
being unrepresentable.

---

## 3. The binder

```python
# src/freeform/binder.py
@dataclass
class BoundPage:
    html: str                             # complete document, ready to render
    spec: ElementSpec                     # id -> type, for the shared validators
    bound_text: dict[str, str]            # id -> exact injected string, for the audit
    groups: list[str]                     # data-group values, for wrapper-level checks
    findings: list[Finding]

def bind_page(page: FreeformPage, system: DesignSystem, ctx: RenderContext,
              *, canvas: Canvas) -> BoundPage
```

Algorithm:

1. **Recognise** — `parse_authored(page.html)`. `AuthoredHtmlError` → finding, abort.
2. **Vocabulary** `[G1]` — every class token ∈ `system.vocabulary`, else `css.unknown_class`.
   Every `CssRule` selector targets a class in the vocabulary, else `css.orphan_selector`.
3. **Plan conformance** — each `plan.must_include` ref present **exactly once**; no ref outside
   the plan's allocation; `policy.disclaimer` exactly once per document.
   → `content.missing_required` · `content.duplicate_ref` · `content.out_of_plan`
4. **Resolve** — for each node with `data-ref`, call `ctx.resolve(ref)`. Record the exact string
   in `bound_text[id]`. `UnresolvedReference` → `ref.unresolved`.
5. **Inject** — for each `data-asset`, resolve through `assets.py` (§4) and replace the node's
   content or `src`.
6. **Tag** — assign `id` and `data-el-type` to **bound leaves only**. Wrappers keep `data-group`.
   Derive the type from the ref namespace via `vocabulary.TYPE_OF_REF`, never from the model.
   Set `hierarchy_role` only on `copy.headline` / `copy.subheadline` / `copy.body`.
7. **Assemble** — emit `<style>`: brand tokens as CSS variables, the binder's own base rules
   (font families by element type and language, `.poster` sizing), then
   `css.serialise(system.rules + page.rules)`. Wrap the body in `.poster`.

Ids are `f"{el_type}-{n}"`, stable within a page so a repair can target them and lineage can
reference them.

---

## 4. Asset resolution

| `data-asset` | Resolves via | Notes |
|---|---|---|
| `brand.logo.red` / `.white` | `BrandPack.logo_path()` | inlined SVG; red or white only |
| `icon.<name>` | `icons/catalogue.json` | unknown name → `asset.unknown`; normalised to `stroke="currentColor"`, geometry elements only, `<text>`/`<title>`/`<use>` stripped |
| `icon.product.<name>` | existing product PNGs | `<img>` |
| `profile.photo.<id>` | `RenderContext._photo_uri(..., shape="cutout")` | always the cut-out `[G4]` |
| `content.<kind>.<i>.photo` | `ContentItem.asset_ref` | speaker headshots from uploads |
| `generated.qr` | `render/qr.py::qr_data_uri` | verified URL only |
| `mountains.<variant>` | `render/mountains.py::mountains_svg` | unchanged generator |
| `background.generated` | `assets/background.generate_from_prompt` | `[G4]` |

Recolouring is pure CSS: icons use `currentColor`, so `color: var(--red)` on the parent does it.
No image processing, and the palette stays token-bound.

---

## 5. The render-time audit

```js
// src/freeform/audit.js — runs after load, before the screenshot
() => {
  const poster = document.querySelector('.poster');
  const problems = [];
  for (const el of poster.querySelectorAll('*')) {
    for (const pseudo of ['::before', '::after', '::marker']) {
      const c = getComputedStyle(el, pseudo).content;
      if (c && c !== 'none' && c !== 'normal')
        problems.push({rule: 'bind.injected_text', id: el.id || null, evidence: `${pseudo} ${c}`});
    }
  }
  for (const el of poster.querySelectorAll('[id]')) {
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility !== 'visible' ||
        parseFloat(cs.opacity) < 0.15 || r.width < 1 || r.height < 1)
      problems.push({rule: 'bind.hidden', id: el.id, evidence: `${cs.display}/${cs.visibility}/${cs.opacity}`});
    const pts = [[.5,.5],[.15,.15],[.85,.15],[.15,.85],[.85,.85]];
    const covered = pts.filter(([fx,fy]) => {
      const hit = document.elementFromPoint(r.x + r.width*fx, r.y + r.height*fy);
      return !(hit && (hit === el || el.contains(hit) || hit.contains(el)));
    }).length;
    if (covered >= 3)
      problems.push({rule: 'bind.occluded', id: el.id, evidence: `${covered}/5 probes covered`});
  }
  return {problems, text: Object.fromEntries(
    [...poster.querySelectorAll('[id]')].map(el => [el.id, (el.innerText || '').trim()]))};
}
```

Python then asserts `text[id] == bound_text[id]` after NFC normalisation and whitespace
collapsing → `bind.substituted`.

**Three assertions, three threats:** pseudo-content catches every CSS text-injection route at
once (no allowlist can be exhaustive); hidden/occluded catches a design dropping the mandatory
legal line, which is the *likely* misbehaviour; round-trip catches substitution and truncation.

---

## 6. Validation and repair

`validate_freeform(bound, geometry, image_path, brand, decision)` composes:

| Source | Checks |
|---|---|
| shared `validate_dom(bound.spec, …)` | ✅ already works — overflow, safe margin, min size, hierarchy, typeface, contrast, both collisions, logo size and clear space |
| shared `validate_pixels(…)` | ✅ red dominance, bold ground |
| `validate/freeform.py` | audit problems · `logo.present`/`count`/`anchor` · `mountains.single` · `colour.max_secondary` (counted over `CssRule` declarations) · `type.scale_snap` · `type.legal_prominence` |
| `validate/copy.py` | `validate_content()` — `facts.invented`, prohibited terms, capitalisation over item text; `content.unsourced` |

**Repair, two stages.** Shared maths, extracted from `concepts.py::_auto_fix` into
`validate/repair.py::shrink_ratio(node)` so both engines use one implementation:

```python
def repair_plan(report, geometry) -> dict[str, dict[str, str]]:
    # layout.overflow / outside_canvas -> font-size: measured * shrink_ratio
    # layout.text_collision            -> font-size: * 0.88
    # type.min_size                    -> font-size: * 1.3, floored at the minimum
    # type.legal_prominence            -> font-size: the legal token size
    # logo.min_size                    -> height
```

Applied as **inline `style` attributes**, which beat any authored selector on specificity as well
as order. `style` is denylisted for authors, so the repairer is its sole owner.

Loop: `MAX_CSS_FIXES=2`, `MAX_LLM_REPAIRS=1`, `MAX_RENDERS=4`. Keep the existing error-signature
stop from `concepts.py:124-127`, plus **keep-best** (retain the fewest-errors render, not the
last) and a **regression guard** (a repair that raises the error count is reverted).

Still failing after the ceiling → rebuild the variation with `concepts.build_concept()`. The
current engine is the quality floor.

---

## 7. The agents

All via `ModelGateway`. New `authoring` tier — `CALL_CAPS["quality"]` is 4 000 output tokens,
which truncates a page of HTML plus 60 CSS rules.

```python
CALL_CAPS["authoring"] = {"max_tokens": 16_000, "thinking_budget": 2_048}
```

> Pass the tier via an explicit `models=` override when the free-form pipeline builds its
> gateway. Adding it to `DEFAULT_MODELS` breaks `tests/test_workflow.py:110`, which asserts
> `set(record.models) == {"fast","quality","vision","image"}`.

Also make `temperature` per-tier: `settings()` hard-codes `0.4`, which is right for extraction
and too low for design variety — part of why variations converge. Authoring uses ~0.9.

| Agent | Node | Tier | Draft | Calls | Budget |
|---|---|---|---|---|---|
| Content Architect | `content_architect` | quality | `ContentSetDraft` | 1 | ~6k |
| Narrative Planner | `narrative_planner` | fast | `StoryboardDraft` | 1 | ~4k |
| Art Director | `art_director` | authoring | `DesignSystemSetDraft` — **all variations in one call** | 1 | ~14k |
| Page Composer | `page_composer` | authoring | `FreeformPageDraft` | variations × pages | ~9k each |
| Visual Reviewer | `visual_reviewer` | vision | `ReviewOutput` (reused, re-prompted) | per variation | ~2k |

**Prompt inputs.** The Art Director gets a stable prefix — `design-principles.md`, `colour.md`,
`typography.md`, `layout.md`, `logo-rules.md`, `imagery.md`, `moving-mountains.md` (~7k tokens,
available as `BrandPack.policies`), the token tables, `CORE_CLASSES`, the design patterns
(`knowledge/design-patterns/*.yaml`) and the icon catalogue. Stable across every call in a run —
the Gemini context-caching candidate named in `architecture-plan.md §7.3`, and most of the cost
mitigation.

The Page Composer gets: its `PagePlan`, the `DesignSystem` (vocabulary + rules), the available
refs with their text lengths (so it can size boxes), and the canvas.

**Budget.** Default `RunBudget(max_tokens=250_000, max_model_calls=60)` for this path. Estimated
spend: planner 4k + director 14k + 4 × (1–3 pages × 9k) + repairs + reviews ≈ **90–150k**, versus
12–33k today. Reuse the per-variation `try/except BudgetExceeded` from `workflow.py:139-156` so a
breach keeps finished variations and flags `partial`.

---

## 8. Test plan

Everything offline. `TestModel`/`FunctionModel` through `ModelGateway(test_model=…)`, as today.

| Suite | Covers |
|---|---|
| `test_freeform_parse.py` ✅ | 63 cases — text nodes, charrefs, `&nbsp;`, `alt`, `<svg><text>`, lists, `<details>`, unbalanced tags, `content:`/counters/quotes/list-style, hiding properties, `!important`, transforms, palette, selector grammar |
| `test_freeform_vocab.py` | `[G1]` unknown class, orphan selector, custom-class cap |
| `test_freeform_bind.py` | ref resolution incl. `content.<kind>.<i>.<field>` `[G2]`; out-of-range index; plan conformance; leaf-only ids; asset injection; type derivation |
| `test_freeform_audit.py` | **needs Chromium** — a fixture page using `::before` content, one with `opacity:0` on the disclaimer, one with the disclaimer covered by a photo. Each must produce its finding. Playwright already runs in the suite |
| `test_freeform_render.py` | two-pass long-form height `[G3]`; N pages; pypdf merge |
| `test_freeform_repair.py` | shrink maths shared with `_auto_fix`; keep-best; regression guard; fallback to `build_concept` |
| `test_freeform_agents.py` | `FunctionModel` canned drafts; `DesignSystemSet` distinctness; fallback system set |
| `test_revise_unaffected.py` | classic `revise` against an output folder that also contains `pages/`, proving `revise.py:68` and `:148` parsing is unbroken |

**Regression bar:** the original 208 must stay green at every phase. Currently 271.

---

## 9. Work breakdown

| # | Task | Depends on | Size |
|---|---|---|---|
| 1 | `vocabulary.py` + vocab enforcement tests `[G1]` | — | S |
| 2 | `contracts.py` + `contracts/content.py` + distinctness validators | 1 | M |
| 3 | `content.` namespace in `render/context.py`; fix the silent `profile.` miss `[G2]` | 2 | S |
| 4 | `assets.py` + icon catalogue + `generate_from_prompt` extraction `[G4]` | — | M |
| 5 | `binder.py` — the 7 steps | 1–4 | **L** |
| 6 | `audit.js` + `renderer.py` two-pass `[G3]` | 5 | M |
| 7 | `validate/freeform.py` + `validate/repair.py` + new rules | 5, 6 | M |
| 8 | `fixtures.py` — hand-authored pages; **end-to-end with zero model calls** | 5–7 | M |
| 9 | `extract_modules` tool + substring verification | 2 | M |
| 10 | The four agents + prompts + `authoring` tier | 2, 8 | **L** |
| 11 | `engine.py` + `pipeline.py` + fallback to `build_concept` | 10 | M |
| 12 | Multi-page, PDF, lineage page fields, `design` CLI command | 11 | M |
| 13 | `knowledge/design-patterns/*.yaml` from `brands.pdf` + the references | — | **L, parallel** |
| 14 | LangGraph shell behind a `[graph]` extra | 11 | M |

**Item 8 is the milestone that matters.** A hand-authored 5-speaker page that binds real copy,
renders, audits and validates — with no model involved — proves the entire governance layer
before a single agent is written. Everything after it is cost and quality work; everything before
it is correctness.

Items 1–8 are the critical path. Item 13 has no code dependency and can run alongside.
