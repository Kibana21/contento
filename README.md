# AIA Agent Marketing Studio

A governed AI creative workspace: an AIA Singapore representative describes a campaign in
plain English and receives 3–4 brand-checked poster variations, refinable by conversation.

```bash
python -m src.main create --agent profiles/demo-agent --campaign campaigns/deepavali-2026
python -m src.main revise --campaign output/deepavali-2026 --variation 2 \
    --instruction "make my photo smaller and shorten the headline"
```

**Start here: [`docs/architecture.md`](docs/architecture.md)** — the master document: every
workflow, every place an LLM is involved, contracts, validators, guardrails and open items.

| Document | Purpose |
|---|---|
| `docs/architecture.md` | **Master.** How the system works, end to end |
| `docs/what-is-built.md` | Short summary for a non-technical reader |
| `docs/architecture-plan.md` | Target state (web + LangGraph + approvals) and the framework decision |
| `brand/aia-singapore/README.md` | Brand pack: tokens, policies, assets, provenance, gaps |
| `knowledge/aia-sg-web/README.md` | Web corpus: disclaimers, copy examples, imagery |
| `AIA_Agent_Marketing_Studio_Business_Requirements.md` | The BRD this implements |
| `AIA_Standalone_Marketing_Generator_Architecture.md` | The V1 shape (CLI, folders, Pydantic AI) |

## Layout

```
src/            the Studio (contracts · ai · policy · render · validate · lineage · assets)
profiles/       representatives: profile.yaml + photos
campaigns/      campaign requests: request.md + assets/
brand/          AIA brand pack: tokens, policies, logo, fonts
knowledge/      campaign rules, disclaimer clauses, approved copy, web corpus
output/         generated campaigns (gitignored)
tests/          208 tests, offline (scripted models)
scripts/        corpus and imagery tooling
```

## Setup

```bash
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m playwright install chromium
# Vertex AI credentials: api_key.json (service account) in the repo root, gitignored
.venv/bin/python -m pytest tests -q
```
