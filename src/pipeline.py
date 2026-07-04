from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .models import Lead
from .scorer import get_scorer


def load_leads(path: Path) -> list[Lead]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Lead.from_dict(item) for item in data]


def write_outputs(results: list, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    scored = [r.to_dict() for r in results]

    json_path = output_dir / "scored_leads.json"
    json_path.write_text(json.dumps(scored, indent=2), encoding="utf-8")

    csv_path = output_dir / "scored_leads.csv"
    if scored:
        fieldnames = list(scored[0].keys())
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in scored:
                row_copy = dict(row)
                row_copy["tags"] = ", ".join(row_copy.get("tags", []))
                row_copy["metadata"] = json.dumps(row_copy.get("metadata", {}))
                writer.writerow(row_copy)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "by_tier": {},
        "hot_leads": [
            {"id": r.lead.id, "name": r.lead.name, "score": r.score, "action": r.recommended_action}
            for r in results
            if r.tier == "hot"
        ],
    }
    for r in results:
        summary["by_tier"][r.tier] = summary["by_tier"].get(r.tier, 0) + 1

    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def print_report(results: list) -> None:
    print("\n=== Lead Intent Engine — Scoring Report ===\n")
    for r in sorted(results, key=lambda x: x.score, reverse=True):
        bar = "#" * (r.score // 5)
        print(f"[{r.tier.upper():4}] {r.score:3}/100  {r.lead.name} ({r.lead.vertical})")
        print(f"       {bar}")
        print(f"       {r.reasoning}")
        print(f"       -> {r.recommended_action}\n")

    hot = [r for r in results if r.tier == "hot"]
    print(f"Hot leads requiring immediate action: {len(hot)}/{len(results)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score and route inbound leads")
    parser.add_argument("--input", type=Path, default=Path("data/sample_leads.json"))
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument("--mode", choices=["rules", "openai", "xai"], default=None)
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 1

    leads = load_leads(args.input)
    scorer = get_scorer(args.mode)
    results = [scorer.score(lead) for lead in leads]

    write_outputs(results, args.output)
    print_report(results)
    print(f"Wrote: {args.output / 'scored_leads.json'}")
    print(f"Wrote: {args.output / 'scored_leads.csv'}")
    print(f"Wrote: {args.output / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
