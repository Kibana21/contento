"""Command line entry point (Standalone §5, §17).

  python -m src.main create --agent profiles/demo-agent --campaign campaigns/deepavali-2026
  python -m src.main revise --campaign output/deepavali-2026 --variation 2 \
      --instruction "make my photo smaller and add Chinese under the greeting"
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from .contracts.common import RunBudget
from .contracts.design import PRESETS
from .freeform.pipeline import create_freeform_campaign
from .revise import revise_campaign
from .workflow import create_campaign

#: "--variation 2" and "--variation b" both mean the second variation.
def _variation_id(value: str) -> str:
    value = value.strip().lower()
    if value.isdigit():
        return chr(ord("a") + int(value) - 1)
    return value


def _progress(quiet: bool):
    def report(message: str) -> None:
        if not quiet:
            print(f"  .. {message}", flush=True)
    return report


def _create(args: argparse.Namespace) -> int:
    budget = RunBudget(max_tokens=args.max_tokens, max_images=args.max_images)
    result = asyncio.run(create_campaign(
        args.agent, args.campaign, out_root=args.out, preset=args.preset,
        interactive=not args.non_interactive, images_enabled=not args.no_images,
        visual_review=not args.no_review, budget=budget, progress=_progress(args.quiet)))
    print()
    print(result.summary())
    if result.lineage:
        usage = result.lineage.usage_summary
        print(f"\n  tokens {usage['tokens']:,} in {usage['calls']} calls"
              f" · images {usage['images']} · lineage {result.out_dir / 'campaign.json'}")
    if result.copy_report.findings or result.tone_report.findings:
        print("\n  copy notes:")
        for finding in [*result.copy_report.findings, *result.tone_report.findings]:
            print(f"    [{finding.severity.value}] {finding.message}")
    return 0 if result.ok else 1


def _design(args: argparse.Namespace) -> int:
    """The free-form engine: an LLM authors the page instead of filling a skeleton."""
    budget = RunBudget(max_tokens=args.max_tokens, max_images=args.max_images)
    result = asyncio.run(create_freeform_campaign(
        args.agent, args.campaign, out_root=args.out, variations=args.variations,
        interactive=not args.non_interactive, visual_review=not args.no_review,
        use_graph=not args.no_graph, budget=budget, progress=_progress(args.quiet)))
    print()
    print(result.summary())
    if result.lineage:
        usage = result.lineage.usage_summary
        pages = sum(e.page_count for e in result.lineage.exports)
        print(f"\n  tokens {usage['tokens']:,} in {usage['calls']} calls · {pages} page(s)"
              f" · lineage {result.out_dir / 'campaign.json'}")
    if result.copy_report.findings:
        print("\n  copy notes:")
        for finding in result.copy_report.findings:
            print(f"    [{finding.severity.value}] {finding.message}")
    return 0 if result.ok else 1


def _revise(args: argparse.Namespace) -> int:
    instruction = args.instruction
    if args.request:
        instruction = Path(args.request).read_text().strip()
    if not instruction:
        print("nothing to do: pass --instruction or --request", file=sys.stderr)
        return 2
    result = asyncio.run(revise_campaign(args.campaign, _variation_id(args.variation), instruction,
                                         profile_dir=args.agent))
    print(result.summary())
    print(f"  poster: {result.poster_path}")
    return 0 if result.report.passed else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aia-studio", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="turn a campaign request into poster variations")
    create.add_argument("--agent", required=True, help="path to profiles/<agent-id>")
    create.add_argument("--campaign", required=True, help="path to campaigns/<name> with request.md")
    create.add_argument("--out", default="output", help="output root (default: output)")
    create.add_argument("--preset", default="instagram_portrait", choices=sorted(PRESETS))
    create.add_argument("--non-interactive", action="store_true",
                        help="never ask questions; record defaults as assumptions")
    create.add_argument("--no-images", action="store_true", help="skip AI background generation")
    create.add_argument("--no-review", action="store_true", help="skip the visual reviewer")
    create.add_argument("--max-tokens", type=int, default=120_000)
    create.add_argument("--max-images", type=int, default=6)
    create.add_argument("--quiet", action="store_true")
    create.set_defaults(func=_create)

    design = sub.add_parser(
        "design", help="free-form engine: the model authors the page (multi-page capable)")
    design.add_argument("--agent", required=True, help="path to profiles/<agent-id>")
    design.add_argument("--campaign", required=True, help="path to campaigns/<name> with request.md")
    design.add_argument("--out", default="output", help="output root (default: output)")
    design.add_argument("--variations", type=int, default=4, choices=range(1, 5))
    design.add_argument("--non-interactive", action="store_true",
                        help="never ask questions; record defaults as assumptions")
    design.add_argument("--no-review", action="store_true", help="skip the visual reviewer")
    design.add_argument("--no-graph", action="store_true",
                        help="run the nodes in sequence instead of through LangGraph")
    design.add_argument("--max-tokens", type=int, default=250_000,
                        help="authoring costs several times a template fill (default: 250000)")
    design.add_argument("--max-images", type=int, default=4)
    design.add_argument("--quiet", action="store_true")
    design.set_defaults(func=_design)

    revise = sub.add_parser("revise", help="change one variation of a finished campaign")
    revise.add_argument("--campaign", required=True, help="path to output/<name>")
    revise.add_argument("--variation", required=True, help="a|b|c|d or 1|2|3|4")
    revise.add_argument("--instruction", default="", help="plain-English change request")
    revise.add_argument("--request", help="file containing the change request, e.g. revision.md")
    revise.add_argument("--agent", default="profiles/demo-agent", help="path to profiles/<agent-id>")
    revise.set_defaults(func=_revise)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
