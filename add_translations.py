"""
add_translations.py
===================
Injects English translations of non-English completions into a raw results
file, so that manual_scorer.py can show raters the original alongside a
translation.

Why this exists
---------------
Neither team member reads Swahili. The translation is therefore part of the
measurement pipeline, not outside it, and has to be recorded as such. Every
injected translation carries a provenance string naming who or what produced
it and under what instruction.

Critical instruction given to the translator
--------------------------------------------
Translations MUST preserve disfluency. Repetition is reproduced as repetition,
broken grammar stays broken, and untranslatable stretches are marked
[untranslatable] rather than guessed. A fluent, tidied translation would make
an incoherent completion look coherent and would destroy the coherence signal
the study depends on.

Usage
-----
python3 add_translations.py results/results_raw_<ts>.json translations.json

translations.json format:
{
  "provenance": "Claude (Anthropic), disfluency-preserving; not human-verified",
  "translations": {
     "<item_key>": "English translation text",
     ...
  }
}

item_key format: model|language|level|technique|probe_id|sample
"""

import argparse
import json
import sys
from pathlib import Path


def item_key(r: dict) -> str:
    return "|".join([
        str(r.get("model", "")),
        str(r.get("language", "en")),
        str(r.get("level", "")),
        str(r.get("technique", "")),
        str(r.get("probe_id", "")),
        str(r.get("sample", "")),
    ])


def main() -> None:
    ap = argparse.ArgumentParser(description="Inject English translations into a raw results file.")
    ap.add_argument("results_file")
    ap.add_argument("translations_file")
    ap.add_argument("--out", default=None, help="Defaults to overwriting results_file in place.")
    args = ap.parse_args()

    res_path = Path(args.results_file)
    tr_path = Path(args.translations_file)

    for p in (res_path, tr_path):
        if not p.exists():
            print(f"Error: file not found -> {p}")
            sys.exit(1)

    data = json.loads(res_path.read_text(encoding="utf-8"))
    tr = json.loads(tr_path.read_text(encoding="utf-8"))

    provenance = tr.get("provenance")
    if not provenance:
        print("Error: translations.json must carry a 'provenance' string.")
        sys.exit(1)

    table = tr.get("translations", {})
    matched = 0
    missing = []

    for r in data.get("results", []):
        if r.get("language", "en") == "en":
            continue
        k = item_key(r)
        if k in table:
            r["translation_en"] = table[k]
            r["translation_provenance"] = provenance
            matched += 1
        else:
            missing.append(k)

    out_path = Path(args.out) if args.out else res_path
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    total_non_en = matched + len(missing)
    print(f"Injected {matched} of {total_non_en} non-English completions.")
    print(f"Provenance: {provenance}")
    if missing:
        print(f"\nWARNING: {len(missing)} completions have no translation.")
        print("They will be shown to raters as original-only, which is a")
        print("recorded gap rather than a silent one. First few:")
        for k in missing[:10]:
            print("   ", k)
    print(f"\nWritten -> {out_path}")


if __name__ == "__main__":
    main()
