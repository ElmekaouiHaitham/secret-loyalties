"""
backfill_prompts.py
===================
Reconstructs the EXACT input each model received and writes it into a results
or assignment file, so that annotators judge completions against what the
model actually saw.

Why this is needed
------------------
audit_pipeline.py stored `user_prompt` (the probe's user turn) but not the
`prefill` string, and not the system prompt. For assistant_prefill and
scratchpad_prefill probes -- 240 of 360 completions -- the completion is a
continuation of, or a response to, text that was never saved. Shown without
it, those completions are unjudgeable: they begin mid-sentence.

The prefills are recoverable losslessly from the committed probes.*.yaml
files, keyed on (language, level, technique, probe_id).

What the pipeline actually sent
-------------------------------
Reading audit_pipeline.call_model / call_model_scratchpad:

  direct_interrogation
      system  = None
      user    = probe.user

  assistant_prefill
      system  = None
      user    = f"{probe.user}\\n\\n[Continue from here]: {probe.prefill}"

  scratchpad_prefill
      system  = probe.prefill
      user    = probe.user

Note that neither is a true assistant-turn prefill: the deployed Modal
endpoint accepts only `message` and `system` and applies the chat template
with add_generation_prompt=True, so there is no way to force tokens into the
start of the assistant turn. This is recorded per-item in `prefill_mode` so
the deviation is visible in the data rather than only in prose.

Usage
-----
python3 backfill_prompts.py results/assignment_20260726T190846_DB.json
python3 backfill_prompts.py results/results_raw_20260726T190846.json
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

PROBES_FILES = {
    "en": "probes.en.yaml",
    "fr": "probes.fr.yaml",
    "sw": "probes.sw.yaml",
}

PREFILL_MODE = {
    "direct_interrogation": "none",
    "assistant_prefill": "appended_to_user_turn",   # NOT a true assistant prefill
    "scratchpad_prefill": "system_prompt",          # NOT a true assistant prefill
}


def build_index(probes_dir: Path):
    idx = {}
    for lang, fname in PROBES_FILES.items():
        path = probes_dir / fname
        if not path.exists():
            continue
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
        for level in ("level_1", "level_2"):
            if level not in cfg:
                continue
            for technique, probes in cfg[level].items():
                if not isinstance(probes, list):
                    continue
                for p in probes:
                    if not isinstance(p, dict) or "id" not in p:
                        continue
                    idx[(lang, level, technique, p["id"])] = {
                        "user": p.get("user"),
                        "prefill": p.get("prefill"),
                    }
    return idx


def main() -> None:
    ap = argparse.ArgumentParser(description="Backfill exact model inputs into a results file.")
    ap.add_argument("target_file")
    ap.add_argument("--probes-dir", default=str(Path(__file__).parent))
    ap.add_argument("--out", default=None, help="Defaults to in-place.")
    args = ap.parse_args()

    target = Path(args.target_file)
    if not target.exists():
        print(f"Error: file not found -> {target}")
        sys.exit(1)

    idx = build_index(Path(args.probes_dir))
    if not idx:
        print("Error: no probe files found.")
        sys.exit(1)

    data = json.loads(target.read_text(encoding="utf-8"))
    records = data.get("results", [])

    filled = 0
    mismatched = []
    missing = []

    for r in records:
        key = (r.get("language", "en"), r.get("level"), r.get("technique"), r.get("probe_id"))
        probe = idx.get(key)
        if probe is None:
            missing.append(key)
            continue

        # integrity check: the stored user_prompt must match the YAML
        stored = r.get("user_prompt")
        if stored is not None and probe["user"] is not None and stored != probe["user"]:
            mismatched.append(key)

        technique = r.get("technique")
        prefill = probe.get("prefill")

        if technique == "assistant_prefill" and prefill:
            sent_system = None
            sent_user = f"{probe['user']}\n\n[Continue from here]: {prefill}"
        elif technique == "scratchpad_prefill" and prefill:
            sent_system = prefill
            sent_user = probe["user"]
        else:
            sent_system = None
            sent_user = probe["user"]

        r["prefill"] = prefill
        r["prefill_mode"] = PREFILL_MODE.get(technique, "unknown")
        r["sent_system"] = sent_system
        r["sent_user"] = sent_user
        filled += 1

    out = Path(args.out) if args.out else target
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Backfilled {filled} of {len(records)} records -> {out}")
    if mismatched:
        print(f"\nERROR: {len(mismatched)} records have a user_prompt that does not match")
        print("the current YAML. The probe files may have changed since the run.")
        for k in mismatched[:10]:
            print("   ", k)
        sys.exit(2)
    if missing:
        print(f"\nWARNING: {len(missing)} records had no matching probe in the YAML:")
        for k in missing[:10]:
            print("   ", k)


if __name__ == "__main__":
    main()
