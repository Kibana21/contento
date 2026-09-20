"""Build text corpora from the aia.com.sg crawl: disclaimer clause library, copy examples, media index."""

import collections
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CRAWL = ROOT / "knowledge/aia-sg-web/crawl.json"
SOURCE = "aia.com.sg crawl 2026-09-19"

CATEGORIES = [
    ("mas_not_reviewed", r"not been reviewed by the Monetary Authority"),
    ("sdic_short", r"^Protected up to specified limits by SDIC"),
    ("ppf_scheme", r"Policy Owners.? Protection Scheme|Singapore Deposit Insurance|Coverage for your policy is automatic|GIA/LIA or SDIC"),
    ("underwritten_by", r"underwritten by AIA Singapore"),
    ("not_contract", r"not a contract of insurance|subject to AIA.?s underwriting"),
    ("read_contract", r"precise terms and conditions|advised to read the policy contract|refer to the (product summary|policy contract)"),
    ("long_term_commitment", r"long.term commitment|early termination|surrender value"),
    ("switching", r"switch|replac(e|ing) an existing|new policy may cost more"),
    ("suitability", r"not suitable for you|suitab"),
    ("seek_advice", r"seek advice from a (qualified )?financial adviser|financial adviser"),
    ("investment_risk", r"investment risks?|past performance|not necessarily indicative|may fall or rise|not guaranteed"),
    ("info_as_at", r"(correct|accurate) as at|for general information|does not constitute"),
    ("promo_tnc", r"terms and conditions apply|promotion|lucky draw"),
    ("value_added_services", r"value-added services|reserves the right"),
]


ABBREV = re.compile(r"\b(Reg|No|Pte|Ltd|e\.g|i\.e|etc|S\$|approx)\.", re.I)


def sentences(text: str) -> list[str]:
    text = ABBREV.sub(lambda m: m.group(0)[:-1] + "\u2024", text)  # protect abbreviation dots
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z(\"“])", text)
    return [re.sub(r"\s+", " ", s).replace("\u2024", ".").strip() for s in parts if len(s.strip()) > 25]


def section(url: str) -> str:
    seg = url.strip("/").split("/")
    return seg[1] if len(seg) > 1 else "home"


def main() -> None:
    pages = json.loads(CRAWL.read_text())["pages"]

    # ---- disclaimer clause library ----
    clause_pages: dict[str, set] = collections.defaultdict(set)
    for p in pages:
        for para in p["disclaimers"]:
            for s in sentences(para):
                clause_pages[s].add(p["url"])
    clauses = []
    for text, urls in sorted(clause_pages.items(), key=lambda kv: -len(kv[1])):
        cats = [c for c, rx in CATEGORIES if re.search(rx, text, re.I)]
        if len(urls) < 2 and not cats:
            continue  # one-off, product-specific sentence
        clauses.append({
            "category": cats[0] if cats else "product_specific",
            "text": text,
            "page_count": len(urls),
            "families": sorted({section(u) for u in urls}),
            "example_pages": sorted(urls)[:5],
        })
    by_cat = collections.defaultdict(list)
    for c in clauses:
        by_cat[c["category"]].append(c)
    out = ROOT / "knowledge/disclaimers"
    out.mkdir(parents=True, exist_ok=True)
    lib = {"source": SOURCE, "status": "OBSERVED on public site. NOT approved for use until AIA SG Compliance signs off.",
           "categories": {k: v for k, v in sorted(by_cat.items())}}
    (out / "aia-sg-web-clauses.json").write_text(json.dumps(lib, indent=2, ensure_ascii=False))
    md = [f"# Disclaimer clauses observed on aia.com.sg\n\nSource: {SOURCE}. **Status: observed, not approved.** "
          "Compliance must confirm which clauses are mandatory for which campaign family and risk class.\n"]
    for cat, items in sorted(by_cat.items(), key=lambda kv: -max(i["page_count"] for i in kv[1])):
        md.append(f"\n## {cat} ({len(items)} variants)\n")
        for c in items[:6]:
            md.append(f"- **[{c['page_count']} pages · {', '.join(c['families'])}]** {c['text']}")
        if len(items) > 6:
            md.append(f"- …{len(items) - 6} more variants in the JSON")
    (out / "aia-sg-web-clauses.md").write_text("\n".join(md) + "\n")

    # ---- copy examples ----
    cp = ROOT / "knowledge/approved-copy"
    cp.mkdir(parents=True, exist_ok=True)
    noise = {"Submit", "Important notes", "中文手册", "Product Brochure", "Show more", "See more"}
    with open(cp / "aia-sg-web-copy.jsonl", "w") as f:
        for p in pages:
            f.write(json.dumps({"url": p["url"], "section": section(p["url"]), "title": p["title"],
                                "description": p["desc"], "h1": p["h1"], "headings": p["h2"],
                                "ctas": [c for c in p["ctas"] if c not in noise]}, ensure_ascii=False) + "\n")
    cta = collections.Counter(c for p in pages for c in p["ctas"] if c not in noise)
    h1s = collections.Counter(h for p in pages for h in p["h1"])
    sec = collections.Counter(section(p["url"]) for p in pages)
    summary = ["# Copy examples from aia.com.sg\n", f"Source: {SOURCE}. Per-page headlines, descriptions and CTAs in `aia-sg-web-copy.jsonl`. "
               "Use as **tone-of-voice few-shot examples**, not as approved campaign wording.\n",
               "\n## Pages by section\n", *[f"- {k}: {v}" for k, v in sec.most_common()],
               "\n## Most common CTAs\n", *[f"- {k} ({v})" for k, v in cta.most_common(30)],
               "\n## Sample H1 headlines\n", *[f"- {k}" for k, _ in h1s.most_common(60)]]
    (cp / "aia-sg-web-copy.md").write_text("\n".join(summary) + "\n")

    # ---- media index ----
    media = ROOT / "knowledge/aia-sg-web"
    vids = sorted({v for p in pages for v in p["videos"] if v})
    pdfs = sorted({x for p in pages for x in p["pdfs"]})
    (media / "videos.txt").write_text("\n".join(vids) + "\n")
    (media / "pdfs.txt").write_text("\n".join(pdfs) + "\n")
    print(f"clauses={len(clauses)} in {len(by_cat)} categories; copy pages={len(pages)}; videos={len(vids)}; pdfs={len(pdfs)}")


if __name__ == "__main__":
    main()
