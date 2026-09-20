# AIA Standalone Marketing Material Generator
## Recommended Architecture and End-to-End Flow

**Purpose:** Build a lightweight standalone program that generates branded AIA Singapore marketing materials for insurance agents using agent details stored in folders, without requiring a complex frontend or enterprise workflow platform.

---

# 1. Recommended Product Shape

The first version should be a standalone Python application.

It should take:

1. An **agent folder**
2. A **campaign request**
3. Optional campaign-specific assets
4. The **AIA Brand Pack**
5. Access to an LLM and image-generation model

It should produce several finished poster variations in an output folder.

The core flow is:

```text
Agent Folder
    +
Campaign Request
    +
Optional Campaign Assets
    +
AIA Brand Pack
    ↓
Standalone Python Program
    ↓
PydanticAI Agents
    ↓
Image Generation
    ↓
Deterministic Poster Renderer
    ↓
Brand Validation
    ↓
output/
    ├── variation-1.png
    ├── variation-2.png
    ├── variation-3.png
    ├── variation-4.png
    └── campaign.json
```

The first version does **not** need:

- a sophisticated web UI
- a database
- Redis
- Celery
- a complex approval portal
- a large multi-agent swarm
- a full Canva-style editor

The goal is to prove that the generation workflow works reliably.

---

# 2. Recommended Project Structure

```text
aia-marketing-studio/
│
├── agents/
│   ├── jane-tan/
│   │   ├── profile.yaml
│   │   ├── photos/
│   │   │   ├── primary.jpg
│   │   │   ├── formal.jpg
│   │   │   └── casual.jpg
│   │   ├── qr/
│   │   │   └── contact.png
│   │   └── assets/
│   │
│   ├── agent-002/
│   └── ...
│
├── brand/
│   └── aia-brand-pack/
│       ├── policies/
│       ├── approved-assets/
│       ├── prompts/
│       └── ...
│
├── campaigns/
│   └── deepavali-2026/
│       ├── request.md
│       └── assets/
│           └── optional-reference.jpg
│
├── src/
│   ├── main.py
│   ├── workflow.py
│   ├── models.py
│   │
│   ├── agents/
│   │   ├── planner.py
│   │   ├── copywriter.py
│   │   ├── creative_director.py
│   │   └── reviewer.py
│   │
│   ├── brand/
│   │   ├── loader.py
│   │   └── validator.py
│   │
│   ├── assets/
│   │   ├── loader.py
│   │   └── image_generator.py
│   │
│   └── renderer/
│       ├── renderer.py
│       └── templates/
│
└── output/
```

---

# 3. Agent Folder

Each agent should have a persistent folder containing all reusable profile information.

Example:

```text
agents/jane-tan/
├── profile.yaml
├── photos/
│   ├── formal.jpg
│   ├── casual.jpg
│   └── headshot.jpg
├── qr/
│   └── contact.png
└── assets/
```

Example `profile.yaml`:

```yaml
id: jane-tan

name: Jane Tan

title:
  Financial Services Consultant

contact:
  mobile: "+65 9123 4567"
  email: "jane.tan@example.com"

preferred_photo:
  photos/formal.jpg

languages:
  - English
  - Chinese

preferences:
  style:
    - elegant
    - warm
    - minimal

  avoid:
    - very dark backgrounds
    - excessive text
```

The benefit is that the agent does not need to repeatedly provide:

- name
- title
- phone
- email
- preferred portrait
- QR code
- style preferences

---

# 4. Campaign Folder

Each campaign can have its own simple folder.

Example:

```text
campaigns/deepavali-2026/
├── request.md
└── assets/
    ├── inspiration.jpg
    └── diya-reference.jpg
```

Example `request.md`:

```markdown
# Campaign Request

Create a Deepavali greeting for my customers.

I want it to feel elegant, warm and premium.

Use my formal photograph.

Keep the greeting short.

Do not promote any insurance product.

Give me 4 different variations.
```

The user should be able to describe the request naturally without filling in many fields.

---

# 5. Recommended Command-Line Usage

Example:

```bash
python -m src.main \
  --agent agents/jane-tan \
  --campaign campaigns/deepavali-2026
```

This command should:

1. Load the agent profile
2. Load the campaign request
3. Load the AIA Brand Pack
4. Interpret the request
5. Generate copy
6. Create creative directions
7. Generate any required visual assets
8. Render poster variations
9. Validate them
10. Save output

---

# 6. Recommended End-to-End Flow

```text
1. Load Agent Folder
        ↓
2. Load Campaign Request
        ↓
3. Load AIA Brand Pack
        ↓
4. Campaign Planner
        ↓
5. Apply Brand / Policy Rules
        ↓
6. Copywriter
        ↓
7. Creative Director
        ↓
8. Generate Supporting Visual Assets
        ↓
9. Render 3–4 Poster Variations
        ↓
10. Validate
        ↓
11. Save Output
```

This is the recommended V1 architecture.

---

# 7. PydanticAI Usage

For the first version, use PydanticAI for only a few tasks where language reasoning is actually useful.

Recommended agents:

1. Campaign Planner
2. Copywriter
3. Creative Director
4. Optional Visual Reviewer

Do not create unnecessary agents for deterministic tasks.

Avoid creating:

- QR Agent
- Logo Agent
- Font Agent
- Renderer Agent
- Risk Agent
- File Agent

Those should be normal Python functions or services.

---

# 8. Campaign Planner

The Campaign Planner converts the user's natural-language request into structured information.

Example input:

> Create a Deepavali greeting. Elegant. Use my formal photo. No product promotion.

Example Pydantic model:

```python
from pydantic import BaseModel

class CampaignPlan(BaseModel):
    campaign_type: str
    objective: str
    tone: list[str]
    audience: str | None
    language: list[str]
    use_agent_photo: bool
    photo_preference: str | None
    product_promotion: bool
    variation_count: int
```

Possible output:

```json
{
  "campaign_type": "festive",
  "objective": "client_relationship",
  "tone": [
    "warm",
    "elegant",
    "premium"
  ],
  "language": [
    "English"
  ],
  "use_agent_photo": true,
  "photo_preference": "formal",
  "product_promotion": false,
  "variation_count": 4
}
```

This structured plan becomes the basis for everything else.

---

# 9. Brand and Policy Rules

After the Campaign Planner, load the relevant AIA Brand Pack rules.

Example:

```text
CampaignPlan
    +
AIA Brand Pack
    ↓
Policy Check
```

The policy step should be ordinary deterministic Python.

It should decide things such as:

- whether product content is present
- whether a disclaimer is required
- whether the campaign is low-risk or higher-risk
- which brand rules apply
- which elements are mandatory
- which elements may not be generated by AI

For V1, simple festive/event/personal-branding scenarios can use straightforward rules.

---

# 10. Copywriter

The Copywriter generates campaign text.

Inputs:

```text
CampaignPlan
+
Agent Profile
+
AIA Tone Rules
+
Applicable Policy Constraints
```

Example Pydantic output:

```python
class CampaignCopy(BaseModel):
    headline: str
    greeting: str
    signature: str | None
    cta: str | None
```

Example output:

```text
Wishing You a Joyous Deepavali

May the festival of lights bring happiness,
prosperity and wonderful moments to you
and your loved ones.
```

The Copywriter should not invent:

- phone numbers
- event dates
- product facts
- financial returns
- product names
- mandatory regulatory wording

Those should come from deterministic inputs.

---

# 11. Creative Director

The Creative Director creates several genuinely different concepts.

It does not create the final poster.

Example output model:

```python
class CreativeDirection(BaseModel):
    name: str
    layout: str
    photo_treatment: str
    background_description: str
    headline_placement: str
    visual_elements: list[str]
    style: list[str]
```

Possible directions:

## Variation 1 — Elegant Portrait

- light or cream background
- agent on the right
- subtle diya glow
- headline upper-left
- restrained AIA red accents

## Variation 2 — Premium Festive

- richer festive imagery
- smaller agent portrait
- larger greeting
- warm illuminated visual

## Variation 3 — Minimal Editorial

- substantial white space
- small festive illustration
- agent lower-right
- strong typography

## Variation 4 — Contemporary

- modern geometric composition
- festive light forms
- minimal copy
- social-media-first layout

The important requirement is that variations should be materially different, not just different colours.

---

# 12. Image Generation

Use the image model only for visual ingredients.

Good use cases:

- festive backgrounds
- abstract textures
- diyas
- lanterns
- celebratory light effects
- generic event imagery
- decorative illustrations

Do not ask the image model to generate the entire poster.

The image model should not generate:

- AIA logo
- agent name
- contact details
- event date
- event time
- QR code
- product facts
- disclaimer text

---

# 13. Deterministic Poster Composition

The final poster should be assembled using normal software.

Conceptually:

```text
Image Generator
      ↓
background.png

Agent Photo ─────────────┐
                         │
AIA Logo ────────────────┤
                         │
Campaign Copy ───────────┤
                         │
Event Facts ─────────────┤
                         ▼
                     Renderer
                         │
                         ▼
                   poster-01.png
```

This provides much higher accuracy than asking an image model to render everything.

---

# 14. Recommended Renderer

For a simple standalone implementation, use:

**HTML/CSS + Playwright**

Flow:

```text
Poster Design
      ↓
Generate HTML/CSS
      ↓
Playwright
      ↓
Screenshot / PDF
      ↓
PNG / PDF
```

Example HTML:

```html
<div class="poster">

    <img
        class="background"
        src="generated/deepavali-bg.png"
    />

    <img
        class="aia-logo"
        src="brand/logos/aia.svg"
    />

    <div class="headline">
        Wishing You a Joyous Deepavali
    </div>

    <div class="message">
        May the festival of lights bring happiness,
        prosperity and wonderful moments to you
        and your loved ones.
    </div>

    <img
        class="agent"
        src="agents/jane-tan/photos/formal.png"
    />

    <div class="agent-name">
        Jane Tan
    </div>

</div>
```

The CSS controls:

- spacing
- typography
- position
- crop
- image size
- margins
- visual hierarchy

The renderer can later create multiple aspect ratios.

---

# 15. Validation

Before saving a final poster, perform deterministic checks.

Examples:

```text
✓ AIA logo is an approved asset
✓ Agent name matches profile
✓ Agent phone matches profile
✓ Correct photo is used
✓ Required disclaimer is present
✓ QR code is valid
✓ No text overflow
✓ Required information is visible
✓ Approved font is used
```

An optional multimodal reviewer can then inspect higher-level visual issues such as:

- layout feels overcrowded
- agent photo is awkwardly cropped
- background interferes with text
- visual hierarchy is weak
- generated imagery looks unnatural

The multimodal reviewer should supplement deterministic checks, not replace them.

---

# 16. Recommended Output Structure

Each campaign run should produce a self-contained output folder.

```text
output/
└── deepavali-2026/
    ├── campaign-plan.json
    ├── copy.json
    │
    ├── concepts/
    │   ├── concept-01.json
    │   ├── concept-02.json
    │   ├── concept-03.json
    │   └── concept-04.json
    │
    ├── generated/
    │   ├── background-01.png
    │   ├── background-02.png
    │   ├── background-03.png
    │   └── background-04.png
    │
    ├── posters/
    │   ├── variation-01.png
    │   ├── variation-02.png
    │   ├── variation-03.png
    │   └── variation-04.png
    │
    └── review.json
```

This structure is useful for debugging and later editing.

---

# 17. Revision Flow

A poster should not need to be regenerated from scratch for small changes.

Example command:

```bash
python -m src.main revise \
  --campaign output/deepavali-2026 \
  --variation 2 \
  --instruction \
  "Make my photo smaller and change the greeting to English and Chinese"
```

Alternatively:

```text
revision.md
```

Example:

```markdown
Use variation 2.

Make the agent photograph about 20% smaller.

Keep the background.

Keep the general layout.

Add Chinese underneath the English greeting.
```

Then:

```bash
python -m src.main revise \
  --campaign output/deepavali-2026 \
  --variation 2 \
  --request revision.md
```

The program should load the existing campaign and modify only what is required.

---

# 18. Recommended Revision Logic

Example:

```text
"Make my photo smaller"
        ↓
Update photo layout
        ↓
Re-render
```

Do not:

- regenerate the campaign brief
- rewrite all copy
- regenerate the background
- rerun unrelated agents

Another example:

```text
"Change event date to 21 October"
        ↓
Update event date
        ↓
Re-render
        ↓
Validate
```

This keeps revisions fast.

---

# 19. LangGraph Recommendation

LangGraph is optional for the first prototype.

A simple Python function is enough initially:

```python
def create_campaign(agent_dir, campaign_dir):

    agent = load_agent(agent_dir)
    brand = load_brand_pack()
    request = load_request(campaign_dir)

    plan = planner.run(...)
    policy = apply_brand_policy(plan)
    copy = copywriter.run(...)
    concepts = creative_director.run(...)

    for concept in concepts:
        background = generate_image(concept)

        design = build_design(
            agent=agent,
            plan=plan,
            copy=copy,
            concept=concept,
            background=background,
        )

        poster = render(design)

        validate(poster)

        save(poster)
```

This is sufficient to validate the idea.

---

# 20. When to Introduce LangGraph

Introduce LangGraph when the workflow starts needing:

- resumability
- retries
- branching
- conditional logic
- human approval
- long-running states
- product campaigns
- multiple review stages
- more complex revision paths

At that stage, the graph can be:

```text
START
  ↓
load_inputs
  ↓
plan_campaign
  ↓
apply_policy
  ↓
generate_copy
  ↓
generate_concepts
  ↓
generate_visual_assets
  ↓
render_variations
  ↓
validate_variations
  ↓
save_output
  ↓
END
```

For the first version, do not introduce LangGraph simply because the solution uses AI agents.

---

# 21. Recommended V1 Technology Stack

```text
Python
+
Pydantic
+
PydanticAI
+
Image Generation API
+
HTML/CSS
+
Playwright
+
AIA Brand Pack
```

Optional later:

```text
LangGraph
+
PostgreSQL
+
Redis
+
Taskiq / Celery
+
Approval workflow
```

---

# 22. Recommended Responsibility Split

| Component | Responsibility |
|---|---|
| Agent Folder | Stores reusable agent identity and assets |
| Campaign Folder | Stores request and campaign-specific artifacts |
| Pydantic | Typed structures |
| PydanticAI Planner | Understands campaign intent |
| PydanticAI Copywriter | Creates marketing copy |
| PydanticAI Creative Director | Creates design concepts |
| Image Model | Creates visual ingredients |
| Python Policy Code | Applies brand and business constraints |
| Renderer | Creates the final poster |
| Validator | Checks factual and brand consistency |
| Output Folder | Stores all generated artifacts |

---

# 23. Core Architectural Principle

The most important principle is:

> **Use AI for creativity and interpretation. Use deterministic software for facts, layout assembly, logos, contact information and validation.**

In practical terms:

```text
AI
├── Understand request
├── Write copy
├── Create concepts
└── Generate visual assets

CODE
├── Load agent identity
├── Load approved logo
├── Apply brand rules
├── Compose poster
├── Insert factual information
├── Generate QR
├── Validate
└── Export
```

---

# 24. Example Deepavali Flow

User request:

> Create a Deepavali greeting for my clients. Warm, elegant, use my primary photo. No product promotion.

Flow:

```text
USER REQUEST
    ↓
LOAD AGENT PROFILE
    ↓
CAMPAIGN PLANNER

campaign = festive
objective = relationship
tone = warm / elegant / premium
photo = primary
product_promotion = false

    ↓
POLICY CHECK

AIA brand rules
No product disclaimer required
Identity must be preserved

    ↓
COPYWRITER

"Wishing You a Joyous Deepavali"

"May the festival of lights bring happiness,
prosperity and wonderful moments to you
and your loved ones."

    ↓
CREATIVE DIRECTOR

A — Portrait-led
B — Premium festive
C — Minimal editorial
D — Contemporary

    ↓
IMAGE GENERATOR

Creates decorative visual assets only

    ↓
RENDERER

Adds:
- approved AIA logo
- actual agent photo
- greeting
- agent name
- contact details

    ↓
VALIDATION

✓ approved logo
✓ correct name
✓ correct contact details
✓ no overflow
✓ correct agent photo
✓ brand rules passed

    ↓
OUTPUT

variation-01.png
variation-02.png
variation-03.png
variation-04.png
```

---

# 25. Example Seminar Flow

User request:

> Create a retirement-planning seminar poster for 18 October at Marina Bay Sands. Use my formal portrait. Make it premium but approachable.

Flow:

```text
LOAD AGENT PROFILE
    ↓
PLAN CAMPAIGN
    ↓
EXTRACT EVENT FACTS
    ↓
CHECK REQUIRED DETAILS
    ↓
WRITE COPY
    ↓
CREATE 3–4 DESIGN CONCEPTS
    ↓
GENERATE OPTIONAL BACKGROUNDS
    ↓
RENDER
    ↓
VALIDATE
    ↓
SAVE
```

The event date, venue and time should be rendered from structured data, not produced inside an AI-generated image.

---

# 26. Recommended Development Sequence

## Stage 1 — Prove Folder Loading

Build:

- `profile.yaml`
- photo loading
- AIA brand pack loading
- campaign request loading

## Stage 2 — Add Planner

Convert free text into `CampaignPlan`.

## Stage 3 — Add Copywriter

Produce structured campaign copy.

## Stage 4 — Add Creative Director

Produce 3–4 structured design concepts.

## Stage 5 — Add Image Generation

Generate visual ingredients.

## Stage 6 — Add Renderer

Produce PNG output using HTML/CSS + Playwright.

## Stage 7 — Add Validation

Check logo, identity, text, layout and required fields.

## Stage 8 — Add Revision Support

Allow selected poster variants to be modified.

## Stage 9 — Add LangGraph Only If Needed

Introduce workflow orchestration after the simple pipeline is proven.

---

# 27. Recommended MVP Scope

Start with only three campaign types:

1. Festive greeting
2. Seminar/event
3. Personal branding

These are enough to validate:

- agent folder structure
- copy generation
- multiple concepts
- image generation
- identity preservation
- rendering
- brand consistency
- revisions

Do not begin with complex product promotion.

Product campaigns require stronger:

- evidence control
- compliance rules
- disclaimers
- human approval

---

# 28. Final Recommendation

The first version should be intentionally simple.

```text
Agent Folder
    +
Campaign Request
    +
AIA Brand Pack
        ↓
Standalone Python Program
        ↓
Planner
        ↓
Copywriter
        ↓
Creative Director
        ↓
Image Generation
        ↓
Renderer
        ↓
Validation
        ↓
3–4 Posters
```

There is no requirement for a complex user interface.

There is no requirement for a database.

There is no requirement for a large agent framework.

There is no requirement for a multi-agent autonomous system.

The most suitable first version is:

> **A folder-driven, command-line marketing-material compiler where AI creates the ideas and deterministic software creates the final artifact.**

Once that works reliably, LangGraph can be added for orchestration and more advanced workflow requirements without changing the core architecture.
