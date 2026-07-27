"""
make_scoring_sets.py
====================
Splits a raw results file into per-rater scoring assignments.

Design
------
* A stratified random OVERLAP set is scored independently by BOTH raters.
  Inter-rater agreement (Cohen's kappa) is computed on this set only.
* The remainder is split evenly between the two raters and single-coded.
* Stratification is over (language, model, level, technique), so the overlap
  set is not accidentally concentrated in one condition.
* The random seed is fixed and recorded in every output file, so the split is
  reproducible and auditable after the fact.

Each rater's output file has the same shape as results_raw_*.json, so
manual_scorer.py runs on it unchanged.

Usage
-----
python3 make_scoring_sets.py results/results_raw_<ts>.json \
    --raters DB RA --overlap-frac 0.25 --seed 20260726
"""

import argparse
import json
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description="Split results into per-rater scoring assignments.")
    ap.add_argument("results_file")
    ap.add_argument("--raters", nargs=2, required=True, metavar=("R1", "R2"))
    ap.add_argument("--overlap-frac", type=float, default=0.25,
                    help="Fraction of each stratum double-scored. Default 0.25.")
    ap.add_argument("--seed", type=int, default=20260726)
    args = ap.parse_args()

    r1, r2 = (r.strip().upper() for r in args.raters)
    in_path = Path(args.results_file)
    data = json.loads(in_path.read_text(encoding="utf-8"))
    results = data["results"]

    rng = random.Random(args.seed)

    # --- stratify -----------------------------------------------------------
    strata = defaultdict(list)
    for r in results:
        key = (r.get("language", "en"), r.get("model"), r.get("level"), r.get("technique"))
        strata[key].append(r)

    overlap, solo1, solo2 = [], [], []

    for key in sorted(strata, key=lambda k: tuple(str(x) for x in k)):
        items = strata[key][:]
        rng.shuffle(items)
        n_over = max(1, round(len(items) * args.overlap_frac))
        overlap.extend(items[:n_over])
        rest = items[n_over:]
        # alternate the remainder so each rater gets a balanced share per stratum
        for i, item in enumerate(rest):
            (solo1 if i % 2 == 0 else solo2).append(item)

    assignments = {r1: overlap + solo1, r2: overlap + solo2}

    stamp = in_path.stem.replace("results_raw_", "")
    overlap_keys = {
        "|".join(str(x.get(f, "")) for f in
                 ("model", "language", "level", "technique", "probe_id", "sample"))
        for x in overlap
    }

    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_file": in_path.name,
        "seed": args.seed,
        "overlap_frac": args.overlap_frac,
        "n_total": len(results),
        "n_overlap": len(overlap),
        "n_solo": {r1: len(solo1), r2: len(solo2)},
        "overlap_item_keys": sorted(overlap_keys),
    }
    man_path = in_path.with_name(f"scoring_manifest_{stamp}.json")
    man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    for rater, items in assignments.items():
        shuffled = items[:]
        rng.shuffle(shuffled)
        out = {
            "assignment_for": rater,
            "source_file": in_path.name,
            "seed": args.seed,
            "n_overlap": len(overlap),
            "n_solo": len(items) - len(overlap),
            "results": shuffled,
        }
        p = in_path.with_name(f"assignment_{stamp}_{rater}.json")
        p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{rater}: {len(items)} items  ({len(overlap)} overlap + {len(items) - len(overlap)} solo)  -> {p.name}")

    print(f"\nTotal completions:   {len(results)}")
    print(f"Double-scored:       {len(overlap)}  ({len(overlap) / len(results):.0%})")
    print(f"Single-scored:       {len(solo1) + len(solo2)}")
    print(f"Seed:                {args.seed}")
    print(f"Manifest:            {man_path.name}")


if __name__ == "__main__":
    main()
