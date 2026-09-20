# AIA Agent Marketing Studio
## Business Requirements Document (BRD)

**Document Type:** Business Requirements Document  
**Product Name:** AIA Agent Marketing Studio  
**Market:** AIA Singapore  
**Version:** 1.0  
**Status:** Draft for Business, Marketing, Compliance and Technology Review  
**Prepared for:** AIA Singapore  
**Prepared on:** September 2026  

---

# 1. Executive Summary

AIA Agent Marketing Studio is a standalone, AI-assisted content and creative production application designed to help AIA Singapore insurance representatives create high-quality, brand-consistent and compliance-aware marketing materials quickly.

The intended experience is deliberately simple:

> An agent writes what they want to communicate, optionally adds campaign-specific material, and receives several polished creative variations using their approved profile, photos, contact information, AIA brand rules and approved marketing assets.

Typical use cases include:

- Chinese New Year greetings
- Deepavali greetings
- Hari Raya greetings
- Christmas and year-end messages
- National Day posts
- Client appreciation messages
- Seminar and event posters
- Career and recruitment events
- Personal branding collateral
- Educational financial content
- Product-related promotional materials, subject to stricter governance
- Social media and messaging-channel assets

The solution should reduce the time and design effort required to create marketing collateral while improving consistency, quality, reuse, governance and traceability.

The system must not behave as a generic text-to-image tool. Instead, it should combine:

1. Natural-language campaign briefing
2. Persistent agent profiles and reusable assets
3. AIA brand and design rules
4. Structured content generation
5. AI-assisted visual creation
6. Deterministic poster composition
7. Brand and compliance validation
8. Conversational refinement
9. Multi-format export
10. Approval and audit capabilities where required

The core product proposition is:

> **Describe the story. Add the right assets. Receive several AIA-ready creative directions. Refine conversationally. Export confidently.**

---

# 2. Business Context

Insurance representatives regularly require marketing materials for customer engagement, events, recruitment, festive greetings, educational communications and product-related promotions.

Today, these materials may be created through a mixture of:

- PowerPoint
- Canva
- external designers
- agency-level templates
- reused posters
- manual photo editing
- ad hoc generative AI tools
- repeated requests to marketing teams

This creates several business problems:

- Creation takes too long for simple, frequent use cases.
- Brand quality varies significantly.
- Agents repeatedly enter the same name, designation, contact details and photo.
- Layouts can become crowded or inconsistent.
- Existing poster templates are often difficult to adapt.
- Generative AI can distort logos, names, dates, contact details and product information.
- Product claims may be generated without sufficient source control.
- Compliance review becomes harder when the provenance of content is unclear.
- Users may need multiple tools just to create, edit and export one simple poster.
- Minor changes often require rebuilding the asset rather than editing only the affected parts.

AIA Agent Marketing Studio addresses these problems by creating a governed, reusable and agent-centric marketing creation environment.

---

# 3. Vision

Create the fastest and simplest trusted way for an AIA Singapore representative to turn an idea into an on-brand marketing asset.

The system should feel less like a design application and more like:

> **A creative director, copywriter, designer, brand guardian and reviewer available through one simple workspace.**

The agent should not need to understand:

- prompt engineering
- design systems
- typography rules
- logo treatment
- image composition
- aspect ratios
- file export settings
- layout grids
- AI model selection

The platform should handle those concerns automatically.

---

# 4. Product Principles

The product shall be designed according to the following principles.

## 4.1 Story First

The user starts with what they want to communicate, not with templates, layers or design controls.

## 4.2 Agent Profile First

Reusable information about the representative should be stored once and reused safely.

## 4.3 Brand by Construction

AIA identity should be enforced through approved assets, design tokens and layout rules rather than merely suggested to an LLM.

## 4.4 Structured Before Visual

The system should create a structured campaign brief and design representation before rendering final artwork.

## 4.5 AI for Creativity, Code for Certainty

AI may create:

- concepts
- headlines
- supporting copy
- visual directions
- illustrations
- backgrounds
- composition suggestions

Deterministic logic should control:

- logos
- agent names
- contact details
- event dates
- URLs
- QR codes
- mandatory disclaimers
- product names
- financial figures
- approved claims
- export dimensions

## 4.6 Variations, Not Duplicates

The system should provide genuinely distinct creative directions rather than minor stylistic changes to one concept.

## 4.7 Conversational Refinement

A user should be able to say:

> “Keep version 2, make my photo smaller, make the headline warmer, and add Chinese text.”

The system should modify the selected design without unnecessarily regenerating the entire artwork.

## 4.8 Compliance Proportionate to Risk

A festive greeting should not require the same workflow as an investment-related product promotion.

## 4.9 Traceable by Default

Every final asset should have a clear lineage showing what request, profile, source material, rules, models and approvals produced it.

---

# 5. Alignment with AIA Design Standards

The application shall use AIA’s official design guidance at:

**https://design.aia.com/**

as a core reference for brand and experience rules.

The AIA Qi Design System is positioned by AIA as a single source of truth for creating consistent and scalable digital experiences.

The product should encode the relevant standards into reusable machine-readable policies rather than relying on users or generative models to remember them.

## 5.1 AIA Design Principles

The solution should reflect the principles published in the AIA design system:

- Clarity
- Efficiency
- Unified experience
- Delight
- Human-centred design
- Purposeful design

For this product, those principles translate into:

- a simple creation journey
- minimal user effort
- consistent brand presentation
- clear content hierarchy
- readable layouts
- low-friction refinement
- inclusive visual treatment
- confidence in the finished material

## 5.2 Colour

AIA’s digital design guidance identifies a primary palette centred around:

- Digital Red
- Digital Charcoal
- White

Additional colours should be used intentionally and sparingly.

The system should therefore maintain a version-controlled colour token library and validate finished artwork against approved token usage.

## 5.3 Typography

AIA’s design guidance identifies:

- AIA Everest
- Open Sans
- Noto Sans for localisation where appropriate

The system must use approved font assets and handle multilingual layouts appropriately, including differences in line height, script density and hierarchy.

## 5.4 Tone of Voice

AIA’s tone-of-voice guidance emphasises language that is:

- Confident
- Human
- Positive
- Inclusive

The platform should automatically review generated copy against these principles.

## 5.5 Photography and Visual Assets

AIA guidance describes photography as:

- inclusive
- vibrant
- focused on people
- capable of creating genuine human connection

The platform should favour authentic, human imagery over generic visual clutter.

## 5.6 Important Governance Note

The public AIA Design site should not be treated as the only authority for production marketing.

The application should additionally support AIA Singapore-specific internal sources for:

- marketing standards
- regulatory requirements
- financial promotion rules
- product disclaimers
- trademark rules
- local language requirements
- approved campaign wording
- approved product information
- local compliance procedures

Where internal rules conflict with generic design guidance, local approved business and regulatory rules shall take precedence.

---

# 6. Business Objectives

The platform shall aim to:

1. Reduce the time required to create common marketing collateral.
2. Improve AIA brand consistency across agent-created materials.
3. Reduce dependency on manual design effort for simple marketing needs.
4. Increase reuse of approved agent and corporate assets.
5. Make campaign creation accessible to non-designers.
6. Improve quality of agent-facing marketing collateral.
7. Reduce factual errors caused by generative image models.
8. Introduce controlled use of generative AI for marketing.
9. Provide traceability for generated materials.
10. Support future integration with approval and publishing workflows.
11. Improve turnaround for seasonal and event campaigns.
12. Enable scalable creation across many representatives without duplicating setup work.

---

# 7. Success Measures

The following KPIs should be tracked.

## 7.1 Productivity Metrics

- Median time from brief to first usable creative
- Median time from first creative to final export
- Number of manual edits per asset
- Percentage of campaigns completed without designer intervention
- Percentage of agent profile fields reused automatically

## 7.2 Quality Metrics

- Brand validation pass rate
- Text accuracy rate
- Agent identity accuracy
- Contact detail accuracy
- Layout overflow rate
- QR validation success rate
- User acceptance rate of generated concepts
- Average number of generations before selection

## 7.3 Governance Metrics

- Percentage of product claims linked to an approved source
- Percentage of higher-risk materials reviewed before release
- Policy-rule violation rate
- Rejected or escalated generation rate
- Percentage of exported assets with complete audit lineage

## 7.4 Adoption Metrics

- Monthly active agents
- Campaigns created per active agent
- Reuse rate
- Repeat usage by campaign type
- Most commonly used campaign families

---

# 8. Scope

## 8.1 Phase 1 Scope

Phase 1 should focus on the most useful and lower-risk scenarios:

### A. Festive and relationship campaigns

Examples:

- Chinese New Year
- Deepavali
- Hari Raya
- Christmas
- New Year
- National Day
- Birthday wishes
- Client appreciation
- Thank-you messages

### B. Seminar and event campaigns

Examples:

- retirement planning seminar
- financial literacy event
- speaker session
- customer appreciation event
- career seminar
- recruitment event
- team sharing session

### C. Agent personal branding

Examples:

- advisor introduction
- personal profile
- service proposition
- achievement announcement
- customer contact card
- social profile post

## 8.2 Later Phases

Future phases may include:

- product promotion
- educational carousel generation
- short-form video
- email banners
- presentation cover slides
- landing-page creatives
- agency-level campaign distribution
- publishing to approved channels
- campaign analytics
- multilingual content workflows
- reusable agency campaign kits

## 8.3 Out of Scope for Initial Release

The following are not required for the first release:

- full Canva-style free-form design editor
- social media scheduling
- complete digital asset management replacement
- product recommendation engine
- automated financial advice
- CRM replacement
- full marketing automation platform
- unrestricted user-generated templates
- autonomous public posting without approval

---

# 9. User Personas

## 9.1 Financial Services Consultant

Needs fast material for customer engagement and events.

Typical behaviour:

- writes a short story
- uses own portrait
- creates festive greeting
- creates seminar poster
- changes wording several times
- exports to WhatsApp or social media

## 9.2 Agency Leader

Needs team-level marketing material.

Typical behaviour:

- creates recurring campaign assets
- includes several speakers
- applies agency-specific information
- distributes approved variations to a team

## 9.3 Marketing Administrator

Maintains brand assets and approved template families.

Responsibilities:

- upload logos
- update design tokens
- manage approved layout families
- maintain campaign defaults

## 9.4 Compliance Reviewer

Reviews higher-risk marketing materials.

Responsibilities:

- inspect claims
- review source evidence
- review required disclaimers
- approve, reject or request amendment

## 9.5 Platform Administrator

Responsible for:

- user access
- configuration
- model/provider setup
- policy packs
- audit visibility
- system health

---

# 10. Core User Journey

The intended default journey should be extremely simple.

## Step 1 — Open Studio

The application automatically loads the current agent profile.

## Step 2 — Describe the Requirement

Example:

> “I am conducting a retirement planning seminar on 18 October at MBS for professionals aged 35–50. I want something warm, premium and modern. Use my formal photo.”

## Step 3 — Add Optional Campaign Assets

The user may add:

- photo
- event agenda
- PDF
- image
- approved brochure
- reference poster
- venue image
- QR destination
- speaker details

## Step 4 — System Creates Campaign Brief

The application extracts and confirms:

- campaign type
- objective
- audience
- message
- event information
- CTA
- tone
- assets
- language
- compliance category

## Step 5 — Generate Creative Directions

The system creates 3–4 visually distinct options.

## Step 6 — Review

The user sees all options together.

## Step 7 — Conversational Refinement

Example:

> “Use version 3. Make the photo 20% smaller, make the headline less salesy, and put the event details in one row.”

## Step 8 — Validate

The system automatically runs:

- brand checks
- factual checks
- asset checks
- layout checks
- policy checks
- compliance checks where relevant

## Step 9 — Export

The user downloads one or more output sizes.

---

# 11. Main Workspace Requirements

The main creation screen shall be single-workspace oriented.

It should not force users through multiple complex pages for routine work.

A conceptual interface:

```text
┌─────────────────────────────────────────────────────────────────┐
│ AIA Marketing Studio                              Jane Tan ▾    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ What would you like to create?                                 │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Create a Deepavali greeting for my clients. Warm, elegant, │ │
│ │ premium. Use my primary portrait. No product promotion.    │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ + Photo   + PDF   + Inspiration   + URL   + Event details     │
│                                                                 │
│ Using profile: Jane Tan          Format: Instagram Portrait ▾  │
│                                                                 │
│                                      [ Create variations ]     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Variation 1       Variation 2       Variation 3                │
│ [ preview ]       [ preview ]       [ preview ]                │
│                                                                 │
│                Selected: Variation 2                            │
│                                                                 │
│ Refine: "Make my photo smaller and simplify the greeting."     │
│                                                    [ Update ]   │
└─────────────────────────────────────────────────────────────────┘
```

The core design principle is:

> The user should be able to create, review, refine and export without repeatedly navigating between separate authoring screens.

---

# 12. Agent Profile Pack

Each representative shall have a persistent profile.

A file-based profile is acceptable for the standalone MVP.

Example:

```text
agents/
└── jane-tan/
    ├── profile.yaml
    ├── photos/
    │   ├── primary.jpg
    │   ├── formal.jpg
    │   ├── casual.jpg
    │   └── cutout.png
    ├── contact/
    │   ├── contact.yaml
    │   └── qr-code.png
    ├── credentials/
    │   └── credentials.yaml
    ├── preferences/
    │   └── creative-style.yaml
    └── assets/
        └── personal/
```

## 12.1 Required Profile Fields

The profile should support:

- internal agent ID
- display name
- approved job title
- agency or team name where applicable
- phone number
- business email
- approved contact URL
- registration URL
- languages
- preferred photo
- alternate photos
- QR destination
- approved credentials
- preferred campaign language
- default social handles where allowed

## 12.2 Creative Preferences

Optional preferences may include:

- minimal
- premium
- warm
- professional
- modern
- editorial
- energetic
- conservative
- people-centric
- preferred portrait
- preferred image treatment

These should guide generation but never override AIA brand rules.

## 12.3 Profile Validation

Profile information should be validated before it becomes reusable.

The system shall distinguish between:

- unverified user input
- admin-approved profile data
- restricted information
- expired credentials

---

# 13. Corporate Brand Pack

Corporate assets shall be separated from agent assets.

Example:

```text
brand/
└── aia-singapore/
    ├── policy/
    │   ├── design-principles.md
    │   ├── colour.md
    │   ├── typography.md
    │   ├── logo-rules.md
    │   ├── imagery.md
    │   └── tone-of-voice.md
    ├── tokens/
    │   ├── colour.json
    │   ├── typography.json
    │   ├── spacing.json
    │   └── layout.json
    ├── logos/
    ├── fonts/
    ├── icons/
    ├── illustrations/
    ├── template-families/
    └── compliance/
```

The platform shall not generate approximations of AIA logos.

Only approved assets shall be used in final composition.

---

# 14. Campaign Brief

Every user request shall be converted into a structured campaign brief before design generation.

Example:

```yaml
campaign_id: CAM-2026-000123
campaign_type: seminar
objective: lead_generation
market: singapore
audience:
  primary: professionals
  age_range: 35-50

tone:
  - premium
  - warm
  - modern

headline_intent:
  retirement_confidence

event:
  title: Retirement Planning Seminar
  date: 2026-10-18
  time: "19:00"
  venue: Marina Bay Sands

cta:
  text: Register Now
  destination: https://example.com/register

agent:
  profile_id: jane-tan
  selected_photo: photos/formal.jpg

language:
  primary: English

risk_classification: amber
```

The user should not need to edit this structure manually, but it should be inspectable where useful.

---

# 15. Campaign Classification

The system shall automatically classify the request into a campaign family.

Initial campaign families:

1. Festive
2. Relationship
3. Event
4. Seminar
5. Career / Recruitment
6. Personal Branding
7. Educational
8. Product Promotion
9. Achievement
10. Customer Appreciation

Campaign classification shall influence:

- layout family
- tone
- visual treatment
- compliance requirements
- required fields
- allowed claims
- export defaults

---

# 16. Risk Classification

The system shall assign a risk class.

## 16.1 Green

Low-risk relationship-oriented communication.

Examples:

- festive greeting
- thank-you message
- generic appreciation
- non-financial personal branding

Possible workflow:

Generate → Validate Brand → Export

## 16.2 Amber

Moderate-risk corporate or event material.

Examples:

- seminar
- recruitment event
- financial education
- speaker event
- achievement announcement

Possible workflow:

Generate → Brand Review → Content Checks → Export

## 16.3 Red

Higher-risk product or financial promotion.

Examples:

- insurance product benefit
- investment-linked message
- performance statement
- product comparison
- premium or coverage claim
- return-related wording

Possible workflow:

Generate from approved sources only → Compliance Validation → Human Approval → Export

Risk policy shall be configurable.

---

# 17. Artifact Ingestion

The user shall be able to add campaign-specific artifacts from the main workspace.

Supported types should include:

- JPEG
- PNG
- PDF
- DOCX
- text
- URL
- QR destination
- event agenda
- speaker image
- venue image
- sample creative
- approved brochure

Each artifact shall be classified according to intended use.

Example:

| Artifact | Treatment |
|---|---|
| Agent portrait | identity asset |
| Product brochure | fact source |
| Previous poster | design reference |
| Venue image | campaign imagery |
| Event agenda | information source |
| Registration URL | CTA source |
| QR code | deterministic output |
| Festive visual | optional creative reference |

The platform shall not treat all uploads as generic prompt context.

---

# 18. Agent Identity Preservation

Where a real agent photo is used, identity preservation shall be a hard requirement.

Permitted transformations may include:

- crop
- background removal
- background replacement
- lighting correction
- colour balancing
- framing
- scaling
- masking
- mild cleanup

By default, the platform shall not:

- alter facial identity
- reconstruct the person into a different-looking individual
- change race or ethnicity
- change age materially
- modify body shape for marketing effect
- invent uniforms or credentials
- add visual claims not present in the profile

If AI image editing is used, it shall preserve the supplied person’s recognisable identity.

---

# 19. Content Generation Requirements

The Content Agent shall generate:

- headline
- sub-headline
- body copy
- CTA
- optional event introduction
- optional speaker summary
- optional bilingual copy
- optional social caption

Generated content shall:

- match campaign objective
- match target audience
- follow AIA tone
- avoid unnecessary jargon
- avoid unsupported claims
- preserve mandatory information
- avoid altering factual event details

Content should be editable independently of visual generation.

---

# 20. Creative Direction Generation

The system shall generate several distinct creative directions before producing final designs.

For example:

## Direction A — Human

- prominent agent portrait
- simple headline
- warm photographic treatment
- minimal supporting text

## Direction B — Premium Editorial

- refined typography
- spacious layout
- sophisticated imagery
- restrained visual hierarchy

## Direction C — Information First

- strong event hierarchy
- clear date/time/venue
- immediate readability
- highly functional

## Direction D — Contemporary Social

- visually dynamic composition
- social-first hierarchy
- stronger graphic elements
- higher energy

The variations must differ meaningfully in:

- composition
- image treatment
- hierarchy
- typography scale
- information placement
- use of white space

They should not simply be recoloured copies.

---

# 21. Design Representation

Each design shall be stored in a structured intermediate form.

Example:

```json
{
  "canvas": {
    "width": 1080,
    "height": 1350
  },
  "layout_family": "event-premium-v2",
  "background": {
    "type": "generated_image",
    "asset": "background-01.png"
  },
  "elements": [
    {
      "type": "logo",
      "asset": "aia-primary.svg",
      "position": "top-left"
    },
    {
      "type": "headline",
      "text_ref": "content.headline",
      "style_token": "headline-xl"
    },
    {
      "type": "agent_photo",
      "asset_ref": "agent.photos.formal"
    }
  ]
}
```

This structured representation makes it possible to:

- edit specific fields
- preserve unaffected content
- recreate assets
- support multiple aspect ratios
- validate design rules
- version changes
- maintain lineage

---

# 22. Rendering Model

The recommended rendering philosophy is:

> **Generate imagery, but compose factual content deterministically.**

AI image generation may be used for:

- backgrounds
- mood imagery
- festive illustrations
- abstract graphic elements
- decorative compositions

The final renderer should programmatically place:

- AIA logo
- agent photo
- agent name
- contact details
- event date
- event time
- venue
- QR code
- product name
- mandatory disclaimers
- approved legal text

This significantly reduces the risk of visual hallucination.

---

# 23. Template Family Model

The platform should not become a large template marketplace.

Instead it should contain controlled template families.

Example:

```text
Festive
├── Elegant Portrait
├── Minimal Greeting
├── Celebration
└── Premium Editorial

Seminar
├── Keynote
├── Panel
├── Speaker Spotlight
└── Information First

Agent
├── Professional
├── Lifestyle
└── Personal Introduction

Recruitment
├── Career Seminar
├── Team Opportunity
└── Speaker Story

Product
├── Hero Benefit
├── Educational
└── Feature Overview
```

A creative agent may choose and adapt a suitable family automatically.

---

# 24. Brand Validation

Every generated design shall be validated before export.

Checks should include:

- approved logo asset
- logo clear space
- logo distortion
- colour token usage
- typography compliance
- text hierarchy
- text contrast
- minimum font size
- safe margins
- text overflow
- image crop quality
- visual balance
- mandatory information presence
- correct campaign language
- correct agent information

Where possible, checks should be deterministic.

A multimodal model may be used as an additional design reviewer, but it should not replace deterministic validation.

---

# 25. Compliance and Content Validation

The compliance layer shall distinguish between:

1. deterministic rules
2. approved content retrieval
3. LLM-assisted review
4. human approval

## 25.1 Deterministic Rules

Examples:

- required disclaimer present
- prohibited phrase absent
- contact field present
- product source exists
- current product version used
- mandatory footer present

## 25.2 Approved Source Retrieval

Any product-related facts shall come from approved source material.

Examples:

- approved product brochure
- approved campaign pack
- approved product database
- approved disclosure library
- approved legal copy

The LLM shall not invent product facts.

## 25.3 LLM-Assisted Review

An LLM may flag:

- potentially misleading wording
- ambiguity
- overly promotional language
- tone inconsistencies
- missing context
- confusing claims

LLM findings should be treated as review signals, not definitive legal decisions.

## 25.4 Human Review

Higher-risk campaigns should support:

- submit for approval
- reviewer comments
- request changes
- approve
- reject
- version history

---

# 26. Conversational Editing

Users shall be able to refine selected material using natural language.

Examples:

- “Make the headline shorter.”
- “Use my formal photo.”
- “Move my photo to the right.”
- “Make the event details more prominent.”
- “Remove the product CTA.”
- “Add Chinese below the English greeting.”
- “Use more white space.”
- “Make the layout feel more premium.”
- “Keep the design exactly the same but change the date to 21 October.”
- “Create a WhatsApp version.”

The system shall modify only relevant design elements where possible.

---

# 27. Multilingual Requirements

The platform should support Singapore-relevant multilingual use cases.

Potential languages include:

- English
- Simplified Chinese
- Traditional Chinese where needed
- Malay
- Tamil

Requirements:

- appropriate font support
- script-aware line heights
- language-specific spacing
- translated CTA validation
- appropriate text expansion handling
- dual-language layout support

Translation should not automatically alter regulated or approved wording without approved language equivalents.

---

# 28. Output Formats

The platform should support configurable output presets.

Initial presets:

- Instagram Square — 1080 × 1080
- Instagram Portrait — 1080 × 1350
- Instagram Story — 1080 × 1920
- WhatsApp-friendly portrait
- LinkedIn post
- Facebook post
- A4 print
- presentation image
- configurable custom size

The system shall reflow layout intelligently instead of merely cropping the original asset.

---

# 29. Export Formats

Supported output formats should include:

- PNG
- JPEG
- PDF

Future options:

- editable SVG
- PowerPoint image package
- campaign ZIP
- Figma-compatible structured export

---

# 30. Source and Audit Lineage

Every generated asset shall record:

- user
- timestamp
- campaign ID
- user brief
- agent profile version
- uploaded artifacts
- source documents
- product content source
- brand pack version
- compliance pack version
- selected template family
- model/provider used
- generation parameters
- reviewer results
- human approval
- exported sizes

This should allow the organisation to answer:

> “How was this marketing material produced?”

without reconstructing the process manually.

---

# 31. Functional Requirements

| ID | Requirement |
|---|---|
| FR-001 | The system shall allow an agent to create a campaign through natural-language input. |
| FR-002 | The system shall automatically load the selected agent profile. |
| FR-003 | The system shall support reusable agent photos and approved profile data. |
| FR-004 | The system shall allow campaign-specific uploads from the main workspace. |
| FR-005 | The system shall classify uploaded artifacts by intended use. |
| FR-006 | The system shall infer campaign type automatically. |
| FR-007 | The system shall infer campaign objective automatically. |
| FR-008 | The system shall generate a structured campaign brief. |
| FR-009 | The system shall identify missing mandatory campaign details. |
| FR-010 | The system shall classify campaign risk. |
| FR-011 | The system shall generate multiple creative directions. |
| FR-012 | The system shall generate multiple poster variations. |
| FR-013 | Variations shall be materially different in composition and visual direction. |
| FR-014 | The system shall use approved AIA logos. |
| FR-015 | The system shall apply approved AIA design tokens. |
| FR-016 | The system shall use approved typography. |
| FR-017 | The system shall preserve factual text outside generative imagery. |
| FR-018 | The system shall programmatically create QR codes from verified URLs. |
| FR-019 | The system shall validate final QR codes. |
| FR-020 | The system shall validate contact information against the profile. |
| FR-021 | The system shall preserve agent photographic identity. |
| FR-022 | The system shall support background generation. |
| FR-023 | The system shall support optional image editing. |
| FR-024 | The system shall support conversational design refinement. |
| FR-025 | The system shall preserve unaffected design elements during edits where possible. |
| FR-026 | The system shall maintain design version history. |
| FR-027 | The system shall validate brand compliance before export. |
| FR-028 | The system shall identify layout overflow. |
| FR-029 | The system shall validate minimum visual hierarchy requirements. |
| FR-030 | The system shall support multilingual content. |
| FR-031 | The system shall support bilingual poster layouts. |
| FR-032 | Product claims shall originate from approved sources only. |
| FR-033 | The system shall support mandatory disclaimer insertion. |
| FR-034 | The system shall support configurable prohibited wording. |
| FR-035 | The system shall support approval workflow for high-risk material. |
| FR-036 | The system shall prevent export where hard compliance rules fail. |
| FR-037 | The system shall support PNG export. |
| FR-038 | The system shall support JPEG export. |
| FR-039 | The system shall support PDF export. |
| FR-040 | The system shall create alternate aspect ratios from an approved design. |
| FR-041 | The system shall maintain generation lineage. |
| FR-042 | The system shall log all final exports. |
| FR-043 | The system shall allow admins to update brand rules. |
| FR-044 | The system shall version brand packs. |
| FR-045 | The system shall version compliance packs. |
| FR-046 | The system shall allow admin management of template families. |
| FR-047 | The system shall provide a visual preview before export. |
| FR-048 | The system shall show validation status before export. |
| FR-049 | The system shall support safe regeneration of one visual element without rebuilding unrelated content. |
| FR-050 | The system shall retain campaign history for reuse and amendment. |

---

# 32. Non-Functional Requirements

## 32.1 Performance

Target objectives:

- first campaign interpretation within a few seconds
- initial creative concepts within approximately 30–60 seconds where image generation is required
- text-only amendments within approximately 5–10 seconds where possible
- layout-only changes without unnecessary image regeneration

Targets should be refined after model/provider benchmarking.

## 32.2 Availability

The platform should provide enterprise-appropriate availability for agent usage.

## 32.3 Security

The system shall:

- authenticate users
- authorise access to appropriate profiles
- prevent cross-agent data leakage
- secure uploaded photographs
- protect internal marketing documents
- encrypt sensitive data in transit
- encrypt stored data where appropriate
- log administrative changes
- restrict compliance-policy management

## 32.4 Privacy

Agent photographs and personal details shall be used only within authorised workflows.

The platform shall support retention policies.

## 32.5 Reliability

Deterministic campaign fields must not depend on visual generative output.

## 32.6 Observability

The application should expose:

- generation latency
- model failures
- renderer failures
- validation failures
- compliance escalations
- export activity

## 32.7 Provider Independence

Text, image and multimodal models should be abstracted through provider interfaces to avoid architecture lock-in.

## 32.8 Reproducibility

Each final poster should be reproducible from:

- campaign brief
- design representation
- source assets
- brand pack version
- rendering version

---

# 33. Recommended Agentic Workflow

The platform should use a controlled orchestration model rather than an unconstrained multi-agent loop.

Recommended flow:

```text
USER REQUEST
     │
     ▼
1. REQUEST INTERPRETER
     │
     ▼
2. BRIEF BUILDER
     │
     ▼
3. CONTENT WRITER
     │
     ▼
4. RISK / POLICY CLASSIFIER
     │
     ▼
5. CREATIVE DIRECTOR
     │
     ├────────────┬────────────┬────────────┐
     ▼            ▼            ▼            ▼
 CONCEPT A     CONCEPT B     CONCEPT C     CONCEPT D
     │            │            │            │
     └────────────┴────────────┴────────────┘
                         │
                         ▼
6. DESIGN SPEC GENERATOR
                         │
                         ▼
7. IMAGE / ASSET GENERATION
                         │
                         ▼
8. DETERMINISTIC RENDERER
                         │
                         ▼
9. BRAND VALIDATOR
                         │
                         ▼
10. COMPLIANCE VALIDATOR
                         │
                         ▼
11. FINAL VARIATIONS
```

The workflow should be explicit, observable and testable.

---

# 34. Recommended System Architecture

```text
                         ┌──────────────────────┐
                         │    Web Frontend      │
                         │  Creation Workspace  │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │     API Backend      │
                         │ Campaign / Profiles  │
                         └──────────┬───────────┘
                                    │
                                    ▼
                  ┌─────────────────────────────────┐
                  │      Workflow Orchestrator      │
                  └──────┬─────────┬─────────┬──────┘
                         │         │         │
               ┌─────────▼───┐ ┌──▼─────┐ ┌▼────────────┐
               │ LLM Service │ │ Image  │ │ Policy /    │
               │             │ │ Model  │ │ Compliance  │
               └──────┬──────┘ └──┬─────┘ └─────┬───────┘
                      │            │             │
                      └──────┬─────┴──────┬──────┘
                             │            │
                             ▼            ▼
                    ┌──────────────┐  ┌──────────────┐
                    │ Design JSON  │  │ Asset Store  │
                    └──────┬───────┘  └──────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   Renderer   │
                    │ HTML/SVG/etc │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  Validator   │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   Exports    │
                    └──────────────┘
```

---

# 35. Suggested Standalone Repository Structure

```text
aia-marketing-studio/
│
├── app/
│   ├── frontend/
│   └── backend/
│
├── agents/
│   ├── request_interpreter/
│   ├── brief_builder/
│   ├── content_writer/
│   ├── creative_director/
│   ├── design_generator/
│   ├── brand_reviewer/
│   └── compliance_reviewer/
│
├── profiles/
│   └── agents/
│
├── brand/
│   └── aia-singapore/
│       ├── tokens/
│       ├── policies/
│       ├── logos/
│       ├── fonts/
│       ├── icons/
│       └── template-families/
│
├── knowledge/
│   ├── approved-products/
│   ├── approved-copy/
│   ├── disclaimers/
│   └── campaign-rules/
│
├── renderer/
│   ├── layouts/
│   ├── typography/
│   ├── svg/
│   └── export/
│
├── campaigns/
│   └── generated/
│
├── tests/
│   ├── brand/
│   ├── compliance/
│   ├── renderer/
│   └── golden-campaigns/
│
└── config/
```

---

# 36. Campaign Workspace Structure

Each campaign should generate a self-contained directory.

```text
campaigns/
└── CAM-2026-000123/
    ├── request.md
    ├── brief.yaml
    ├── sources/
    ├── uploads/
    ├── generated-assets/
    ├── concepts/
    │   ├── concept-a.json
    │   ├── concept-b.json
    │   └── concept-c.json
    ├── designs/
    │   ├── v1.json
    │   └── v2.json
    ├── validation/
    │   ├── brand.json
    │   └── compliance.json
    ├── approvals/
    └── exports/
```

---

# 37. Admin Requirements

Administrators should be able to manage:

- agent profiles
- brand pack
- design rules
- approved logos
- approved fonts
- template families
- compliance policy
- prohibited terms
- disclaimer rules
- approved product sources
- output presets
- supported languages
- AI model provider configuration
- feature flags

All policy changes should be versioned.

---

# 38. Audit Requirements

The platform shall provide an auditable record for every exported campaign.

Audit events should include:

- campaign created
- brief generated
- artifact uploaded
- profile asset selected
- content generated
- image generated
- design generated
- user edit
- design validation
- compliance validation
- approval requested
- approval granted
- approval rejected
- export created

---

# 39. Golden Test Set

Before production, AIA should create a golden campaign suite covering representative scenarios.

Examples:

1. Chinese New Year greeting with portrait
2. Deepavali greeting without product content
3. Christmas client greeting
4. Retirement planning seminar
5. Recruitment seminar with three speakers
6. Advisor introduction
7. Customer appreciation poster
8. Financial education message
9. Product promotion with approved claim
10. Product promotion containing intentionally prohibited claim
11. Bilingual English-Chinese campaign
12. Long-name agent profile
13. Small portrait
14. Multi-speaker event
15. Dense event information

Each should have expected:

- content
- brand validation
- policy status
- layout quality
- factual accuracy
- export behaviour

---

# 40. Acceptance Criteria for MVP

The MVP may be considered successful when:

1. An agent can create a festive poster from one natural-language request.
2. An agent can create a seminar poster from one natural-language request.
3. The agent profile is reused automatically.
4. At least three visually different concepts are produced.
5. The AIA logo is always sourced from an approved asset.
6. Agent name and contact information are never embedded by the image model.
7. A user can refine a selected poster conversationally.
8. The system can change text without regenerating unrelated imagery.
9. The system can create multiple output sizes from one approved design.
10. The system catches basic brand violations before export.
11. Every exported asset contains lineage metadata.
12. A saved campaign can be reopened and amended later.

---

# 41. Phase 1 MVP Recommendation

The first release should intentionally remain narrow.

## Include

- agent profile folder
- photo library
- one simple creation workspace
- free-text brief
- campaign artifact upload
- festive campaign family
- seminar/event family
- personal branding family
- 3–4 variations
- AIA brand pack
- structured design JSON
- deterministic renderer
- conversational edits
- PNG/JPEG/PDF export
- brand validation
- audit history

## Defer

- complex product promotion
- publishing
- social scheduling
- advanced analytics
- rich campaign management
- video
- full free-form editor

This allows the organisation to solve the hardest architectural problems first:

- identity preservation
- structured generation
- deterministic composition
- AIA brand consistency
- high-quality variation generation
- conversational refinement
- render reliability

---

# 42. Phase 2 Recommendation

Add:

- approved product content repository
- compliance rule engine
- high-risk workflow
- human approval
- multilingual content
- agency templates
- richer campaign history
- administrator UI

---

# 43. Phase 3 Recommendation

Add:

- social publishing integration
- campaign performance analytics
- short video generation
- reusable campaign packs
- agency leader distribution
- recommendation of best-performing approved campaign styles
- CRM integration
- event registration integration

---

# 44. Key Business Risks

## Risk 1 — Generic AI Output

**Risk:** Posters look like generic AI advertisements.

**Mitigation:** AIA design tokens, controlled template families, approved assets, creative direction logic and deterministic rendering.

## Risk 2 — Brand Drift

**Risk:** AI produces colours, type and layouts inconsistent with AIA.

**Mitigation:** versioned machine-readable brand pack and deterministic validation.

## Risk 3 — Factual Hallucination

**Risk:** AI changes dates, names, phone numbers or product facts.

**Mitigation:** factual fields remain outside the image model and are inserted by renderer.

## Risk 4 — Identity Distortion

**Risk:** AI alters the adviser’s face.

**Mitigation:** identity-preserving photo pipeline and limited transformation policy.

## Risk 5 — Unsupported Financial Claims

**Risk:** generated copy contains unapproved claims.

**Mitigation:** approved-source retrieval, hard policy checks and human approval for high-risk content.

## Risk 6 — Too Much UI Complexity

**Risk:** the system becomes another design tool that agents avoid.

**Mitigation:** story-first single-workspace experience with conversational edits.

## Risk 7 — Too Little Creative Diversity

**Risk:** variations look almost identical.

**Mitigation:** explicit creative-direction generation before rendering.

## Risk 8 — Untraceable AI Behaviour

**Risk:** organisation cannot explain where a final claim or design came from.

**Mitigation:** structured campaign lineage and source tracking.

---

# 45. Design Decisions That Should Be Treated as Foundational

The following should be accepted as core architecture decisions unless a compelling reason emerges to change them.

## ADR-001 — Factual Text Must Not Be Generated Into Images

Names, numbers, dates, product facts, URLs and disclaimers must be rendered programmatically.

## ADR-002 — Logos Must Be Sourced Assets

AIA logos shall never be generated by an image model.

## ADR-003 — Every Campaign Has a Structured Brief

No final generation should proceed directly from raw prompt to final poster.

## ADR-004 — Every Design Has a Structured Representation

Designs shall be editable and re-renderable.

## ADR-005 — Creativity and Compliance Are Separate Responsibilities

Creative agents should not decide whether a financial claim is compliant.

## ADR-006 — Reviews Use Rules First, LLM Second

Where a rule can be tested deterministically, it shall not be delegated solely to an LLM.

## ADR-007 — Campaign Risk Drives Workflow

Low-risk festive content and higher-risk product promotion shall not share the same approval path.

## ADR-008 — Agent Assets Are Persistent

The representative should not repeatedly upload the same portrait and contact information.

---

# 46. Example End-to-End Scenario

## User Input

> “Create a Chinese New Year greeting for my customers. Make it elegant, warm and premium. Use my primary photo. Keep the wording short. No product message.”

## System Interpretation

```yaml
campaign_type: festive
festival: chinese_new_year
objective: relationship
risk: green
tone:
  - warm
  - premium
  - elegant
copy_length: short
product_promotion: false
photo: agent.primary
```

## Generated Creative Directions

### Option 1
Portrait-led, restrained red treatment, large greeting.

### Option 2
Elegant festive illustration with smaller portrait.

### Option 3
Editorial layout with significant white space.

### Option 4
Modern social-first treatment with subtle festive elements.

## User Refinement

> “Use option 3. Reduce my portrait by 15%. Add a short Chinese greeting underneath.”

## System Actions

- preserve layout
- resize portrait
- generate approved translation
- apply appropriate Chinese font
- adjust line height
- validate text bounds
- rerun brand validation
- render final variations

## Outputs

- Instagram portrait
- Instagram square
- WhatsApp version
- PDF

---

# 47. Example Seminar Scenario

## User Input

> “I am conducting a retirement planning seminar on 18 October from 7 PM to 9 PM at Marina Bay Sands. Audience is professionals aged around 35–50. Use my formal portrait. Make it premium but not intimidating.”

## System Extracts

- event type
- date
- time
- venue
- audience
- tone
- speaker identity
- CTA requirement

## System Requests Missing Information Only If Necessary

Potential missing fields:

- registration URL
- final event title
- additional speaker names

The system should not ask unnecessary questions.

---

# 48. User Experience Guardrails

The product should avoid:

- complex left-side toolbars
- dozens of template thumbnails
- layer panels
- overly technical AI controls
- separate pages for every small amendment
- repeated file upload
- manual logo placement
- manual aspect-ratio redesign
- model names exposed to ordinary users

The experience should emphasise:

- one brief
- visible assets
- large previews
- simple variations
- conversational change
- clear validation
- one-click export

---

# 49. Recommended Product Positioning

Internal positioning:

> **AIA Agent Marketing Studio is a governed AI creative workspace that turns an agent’s story and approved assets into brand-consistent marketing materials in minutes.**

Short version:

> **Tell your story. Get AIA-ready creative.**

---

# 50. Recommended Next Deliverables

After this BRD is accepted, the next artefacts should be created in this order:

1. Product Requirement Document
2. User journey and wireframes
3. Domain model
4. Agent profile specification
5. Campaign brief schema
6. Design JSON specification
7. AIA brand-policy schema
8. Compliance-policy schema
9. Rendering architecture
10. Agent orchestration specification
11. API specification
12. Golden test set
13. MVP delivery roadmap
14. Security model
15. Approval workflow design
16. UI prototype

---

# 51. Source References

The following AIA Design resources should be treated as foundational references and reviewed during implementation:

- AIA Design Standards  
  https://design.aia.com/design-standards

- AIA Qi Design System  
  https://design.aia.com/aia-qi-design-system

- AIA Colour  
  https://design.aia.com/colour

- AIA Typography  
  https://design.aia.com/typography

- AIA Tone of Voice  
  https://design.aia.com/tone-of-voice

- AIA Visual Assets  
  https://design.aia.com/visual-assets

These public references should be supplemented with AIA Singapore’s internal marketing, product, legal and compliance rules before production deployment.

---

# 52. Final Recommendation

The strategic value of this product does not come from simply connecting a text box to an image generator.

The strongest solution is a **controlled creative system** with five layers:

1. **Intent**
   - Understand what the agent wants to communicate.

2. **Knowledge**
   - Use the agent profile, approved AIA brand assets and approved business content.

3. **Creativity**
   - Generate copy, visual ideas and multiple differentiated creative directions.

4. **Composition**
   - Render the final material deterministically so logos, names, dates and facts remain correct.

5. **Governance**
   - Validate brand, policy and compliance requirements before release.

This approach can deliver the speed and creativity agents expect from generative AI while preserving the consistency and control required for an insurance company.

The end-state should feel effortless to the user:

> **Write what you want. Add anything specific. Pick a variation. Ask for changes. Export.**

Everything complicated—brand rules, layout logic, source control, rendering, validation and auditability—should happen underneath.
