# Colour

Sources: **AIA Brand Standards v2.0 pp. 50–56 (governs marketing collateral)** · design.aia.com/colour (AIA Qi, digital UI only)
Values are in `../tokens/colour.json`.

## ⚠️ Two palettes: which one applies
| | Brand Standards (2022, print and marketing) | AIA Qi (2026, digital UI) |
|---|---|---|
| Red | **AIA Red `#D31145`** (Pantone 200C) | Digital red 500 `#E00842` |
| Red usage | **Must always be the dominant colour** | Never more than 20% of a UI layout |
| Secondary | 10 named colours (salmon, cerise, orange, yellow, purple, lavender, blue, green, silver, gold) | salmon, purple, warm grey (UI tints) |

**Decision: Studio output (posters, social, print) follows the Brand Standards.** The Qi palette and its 20% cap are for app and web UI only.
Posters and social are marketing comms; the brand book's own social, poster and outdoor examples are red-dominant.
*Confirm with AIA Singapore Marketing.*

## Core colours (p51)
AIA Red and white are the dominant colours. AIA Charcoal and its tints are accents for visual and typographic hierarchy.
"We lean towards being bold and impactful and always, unmistakably AIA."

Red is applied in one of two ways (p54). These map directly to creative directions:
- **Bold application**: AIA Red as a strong solid background → dynamic, vibrant designs. *(Directions "Contemporary Social" and "Human")*
- **Highlight application**: white or light-charcoal base with red highlights, for understated or information-heavy designs. **Red is still the dominant colour.** *(Directions "Premium Editorial" and "Information First")*

## Secondary colours (p52, p55)
"AIA is a red brand first and foremost." Use secondary colours only to:
- add energy or calm
- draw attention to important information
- create differentiation
- help navigation
- provide more colour in infographics and illustrations

If a secondary colour dominates, it is being applied incorrectly.

## Background colours (p53)
Approved backgrounds are AIA Red, White, and specific tints of Blue, Orange, Purple, Lavender, Salmon, Silver and Gold (see tokens).
Cerise, yellow and green are not approved as backgrounds. **No gradient backgrounds, ever.**
On a secondary-colour background, only the core (AIA Red) Moving Mountains may be used.

## Don'ts (p56) → validator rules
1. Don't use colours without visual contrast.
2. Don't apply secondary colours to the Moving Mountains without AIA Red (unless the mountains sit on an AIA Red background).
3. **Don't use more than 4 secondary colours on one page or section.**
4. Don't use a background colour outside the approved palette and tints.
5. **Don't use secondary colours without AIA Red.**

## Contrast (computed, WCAG 2.x). Our additional safety net.
| Pair | Ratio | Verdict |
|---|---|---|
| White on AIA Red | 5.34 | ✅ text OK |
| AIA Red on white | 5.34 | ✅ text OK |
| Charcoal on white | 11.06 | ✅ |
| **Charcoal on AIA Red** | **2.07** | ❌ Brand p76 shows this for subheads; we override to white |
| AIA Red on Red 20% | 3.77 | ⚠️ large text only |
| White on Red 80% | 4.24 | ⚠️ large text only |
| White on Blue / Purple | 4.83 / 7.97 | ✅ |
| White on Orange | 2.66 | ❌ use charcoal |

## Print note
When printing spot colours, get test prints and a press proof with the artwork team present.
→ The Studio exports RGB for digital; A4 print export should carry a "proof before print" note.
