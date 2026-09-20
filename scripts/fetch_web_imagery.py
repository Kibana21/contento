"""Download AIA SG website imagery from Adobe Scene7 at original resolution.

Input:  crawl JSON exported from the browser crawl of aia.com.sg (list of pages with image refs).
Output: <out>/images/<asset-id>.(jpg|png) plus <out>/images.jsonl with provenance metadata.

Scene7 (s7ap1.scene7.com) is not behind the aia.com.sg firewall, so plain HTTP works.
Images with an alpha mask are saved as PNG (cutouts/illustrations), others as high-quality JPEG.
"""

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

S7 = "https://s7ap1.scene7.com/is/image/aia/"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/128 Safari/537.36"}


def asset_id(ref: str) -> str | None:
    """Normalise a Scene7 URL or /content/dam path to a Scene7 asset id (no preset, no extension)."""
    ref = urllib.parse.unquote(ref.split("?")[0])
    if "scene7.com/is/image/aia/" in ref:
        name = ref.split("/is/image/aia/", 1)[1]
    elif "/content/dam/" in ref:
        name = ref.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    else:
        return None
    name = re.split(r"[:{]", name)[0].strip()  # drop ":Banner-Images-Crop" presets and "{.width}" templates
    return name or None


def get(url: str, timeout: int = 30) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def props(aid: str) -> dict:
    txt = get(S7 + urllib.parse.quote(aid) + "?req=imageprops").decode()
    return dict(re.findall(r"image\.(\w+)=(.*)", txt))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("crawl_json")
    ap.add_argument("out")
    ap.add_argument("--delay", type=float, default=0.5)
    args = ap.parse_args()

    pages = json.loads(Path(args.crawl_json).read_text())["pages"]
    out = Path(args.out)
    (out / "images").mkdir(parents=True, exist_ok=True)

    # asset id -> provenance (pages, alts, section headings)
    index: dict[str, dict] = {}
    for p in pages:
        refs = [(i["src"], i.get("alt", ""), i.get("ctx", "")) for i in p.get("imgs", [])]
        refs += [(r, "", "") for r in p.get("imgRefs", [])]
        if p.get("og"):
            refs.append((p["og"], "", "og:image"))
        for src, alt, ctx in refs:
            if src.lower().split("?")[0].endswith((".svg", ".gif")):
                continue
            aid = asset_id(src)
            if not aid or ("logo" in aid.lower() and "aia" not in aid.lower()):
                continue  # skip third-party partner logos
            e = index.setdefault(aid, {"id": aid, "pages": set(), "alts": set(), "contexts": set(), "refs": set()})
            e["pages"].add(p["url"])
            e["refs"].add(src)
            if alt:
                e["alts"].add(alt)
            if ctx:
                e["contexts"].add(ctx)

    done = {json.loads(l)["id"] for l in (out / "images.jsonl").read_text().splitlines()} if (out / "images.jsonl").exists() else set()
    unresolved = []
    with open(out / "images.jsonl", "a") as log:
        for n, (aid, e) in enumerate(sorted(index.items()), 1):
            if aid in done:
                continue
            try:
                pr = props(aid)
                w, h, mask = int(pr.get("width", 0)), int(pr.get("height", 0)), pr.get("mask") == "1"
                if not w:
                    raise ValueError("no such asset")
                ext, q = ("png", "fmt=png-alpha&scl=1") if mask else ("jpg", "fmt=jpg&scl=1&qlt=95")
                data = get(S7 + urllib.parse.quote(aid) + "?" + q, timeout=60)
                fname = re.sub(r"[^\w.@-]+", "_", aid) + "." + ext
                (out / "images" / fname).write_bytes(data)
                rec = {"id": aid, "file": f"images/{fname}", "width": w, "height": h, "alpha": mask, "bytes": len(data),
                       "pages": sorted(e["pages"]), "alts": sorted(e["alts"]), "contexts": sorted(e["contexts"])[:10],
                       "source": S7 + aid}
                log.write(json.dumps(rec, ensure_ascii=False) + "\n")
                log.flush()
                print(f"[{n}/{len(index)}] {fname} {w}x{h}")
            except Exception as ex:  # noqa: BLE001 - record and continue
                unresolved.append({"id": aid, "refs": sorted(e["refs"]), "pages": sorted(e["pages"]), "error": str(ex)})
            time.sleep(args.delay)

    (out / "unresolved.json").write_text(json.dumps(unresolved, indent=2, ensure_ascii=False))
    print(f"indexed={len(index)} unresolved={len(unresolved)}")


if __name__ == "__main__":
    main()
