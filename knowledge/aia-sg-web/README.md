# aia.com.sg web corpus (captured 2026-09-19)

Crawled 608 of 614 English pages from the site's own sitemap, throttled to 1 page per 2.5 s. The 6 skipped pages (`/en/aiaplus*`, PayEz, receive-payouts) redirect off-domain.

| Artifact | What | In git? |
|---|---|---|
| `crawl.json` | Raw per-page capture: title, meta description, og:image, H1/H2/H3, CTAs, image refs with alt text + section heading, disclaimer paragraphs, video embeds, PDF links | ❌ gitignored |
| `imagery/images/` + `imagery/images.jsonl` | Every page image at **original resolution** from Adobe Scene7 (PNG with alpha for cut-outs and illustrations, JPEG q95 for photos). Metadata: pages, alt texts, section headings, dimensions | ❌ gitignored (proprietary, rights unknown) |
| `imagery/unresolved.json` | Refs that had no Scene7 original (mostly `/content/dam` only). Fetch via browser if needed | ❌ |
| `videos.txt` | 48 video embeds (mostly YouTube) | ✅ |
| `pdfs.txt` | 493 PDF links (product brochures EN/CN, product summaries, T&Cs, fund docs, forms) | ✅ |
| `../disclaimers/aia-sg-web-clauses.{md,json}` | **161 disclaimer clauses in 14 categories**, ranked by how many pages use them (MAS not-reviewed, PPF/SDIC, underwritten-by, switching, suitability, investment risk, …) | ✅ |
| `../approved-copy/aia-sg-web-copy.{md,jsonl}` | Per-page headlines, descriptions and CTAs: tone-of-voice few-shot examples | ✅ |

Regenerate: `python scripts/build_web_corpus.py` · `python scripts/fetch_web_imagery.py knowledge/aia-sg-web/crawl.json knowledge/aia-sg-web/imagery` (resumable).

## How the Studio uses this
- **Disclaimer clauses** → seed for the compliance rule pack (which clauses are mandatory per family and risk). **Observed ≠ approved**: Compliance must sign off.
- **Copy corpus** → few-shot examples for the Copywriter and Tone Reviewer (real AIA SG voice). Not approved campaign wording.
- **Imagery** → (1) style reference and retrieval set for the Creative Director and background prompts; (2) visual examples for the Visual Brand Reviewer's rubric; (3) illustrations and graphics that may be reused **only after usage rights are confirmed**. Stock and ambassador photos (e.g. brand ambassadors) must never be placed in agent collateral without clearance.
- **PDF index** → candidate approved-source documents for Phase 2 product-fact retrieval (download from AIA's internal DAM rather than the public site where possible).
