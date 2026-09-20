# AIA Singapore Brand Pack (draft v0.2)

Machine-readable brand rules for AIA Agent Marketing Studio (BRD §13).

## Sources
| Source | Date | Status | Governs |
|---|---|---|---|
| **AIA Brand Standards v2.0** (`brands.pdf`, 141 pp., Group Brand) | Jul 2022 | **Primary.** On the AIA Corporate Policy Portal and mandatory in all markets | Marketing, print, social: **everything the Studio produces** |
| design.aia.com (AIA Qi design system) | captured 2026-09-19 | Secondary | Digital app and web UI; used here for readability, inclusivity and localisation |

**Precedence:** AIA Singapore internal rules > Brand Standards v2.0 > AIA Qi (BRD §5.6).
**Key conflict resolved:** Studio output uses **AIA Red `#D31145`, red-dominant** (Brand Standards), *not* Qi's Digital red `#E00842` with its ≤ 20% UI cap. See `policy/colour.md`. *Confirm with AIA SG Marketing.*

## Contents
| File | Covers |
|---|---|
| `policy/brand-foundation.md` | Purpose (HLBL), mentor persona and traits, **Singapore = Emancipation cluster / "On your side"** |
| `policy/tone-of-voice.md` | 5 tone principles, tone spectrum by channel, readability, inclusivity, capitalisation rules |
| `policy/logo-rules.md` | HLBL / Corporate / Wordmark, clear space, minimum sizes, 7 positions, don'ts |
| `policy/colour.md` | Core + 10 secondary colours, approved backgrounds, red-dominance rules, contrast table |
| `policy/typography.md` | AIA Everest styles, Arial fallback, Monotype Hei pairings, hierarchy ratios, minimum sizes |
| `policy/moving-mountains.md` | The signature graphic: construction, colour variants, photo modes, don'ts |
| `policy/imagery.md` | Photography principles and don'ts, illustration (everyday surrealism), icons, infographics, motion |
| `policy/layout.md` | Grid, spacing, logo anchors, poster patterns from brand examples |
| `policy/programmes.md` | Sub-brands, endorsements, AIA One Billion, AIA Vitality, High Net Worth, sponsorship: mostly **restrictions** |
| `policy/brand-checklist.md` | Official checklist mapped to LLM-reviewer and deterministic validators |
| `policy/design-principles.md` | Brand + Qi design principles |
| `tokens/colour.json` | All palettes with Pantone, CMYK, RGB and tints, backgrounds, rules |
| `tokens/typography.json` | Families, pairings, hierarchy ratios, proposed poster scale |
| `tokens/logo.json` | Logo variants, clear space, sizes, positions, forbidden transforms |
| `tokens/moving-mountains.json` | Tint and opacity tables per variant, constraints |
| `tokens/spacing.json` | 4px soft grid, proposed poster spacing |

## Provenance labels
`published` (stated in a source) · `sampled` (read from swatch pixels) · `observed-css` (site stylesheet) · `proposed` (our assumption, **needs AIA SG sign-off**).

## Downloaded assets
`assets/` (gitignored; see `assets/MANIFEST.md`): **Corporate Logo SVG (red + white)**, **AIA Everest Regular + Medium**, AIA Vitality logo, Moving Mountains reference images, product and system icons, all from aia.com.sg.

## Remaining gaps (assets on the Group Brand SharePoint, Brand Standards p140; internal use, NDA for third parties)
1. **HLBL Logo Lockup SVG** (the Corporate Logo is now available).
2. **AIA Everest Bold / Extra Bold / Condensed** (Regular and Medium obtained) plus a signed font release; Monotype Hei licence for Chinese.
3. **Moving Mountains library** and Illustrator grid template.
4. AIA icon library (event-detail icons) and illustration library.
5. Tamil and Malay typography guidance; AIA SG local marketing rules.
6. Regulatory, financial-promotion and disclaimer rules (separate compliance pack).
7. Whether agency or team marks are permitted on agent collateral.

Contacts named in the Brand Standards: group.brand@aia.com (Group Brand Team) · designsystem@aia.com (Digital Design System).
