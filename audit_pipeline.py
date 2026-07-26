"""
audit_pipeline.py
=================
Black-box static auditing pipeline for the sl-organism model.

Replicates Lamerton & Roger (2026), arXiv:2605.06846, Section 4.3.
Techniques implemented:  direct_interrogation | assistant_prefill | scratchpad_prefill
Levels:                  1 (auditor knows nothing) | 2 (auditor knows a loyalty exists)
Affordance declared:     Level 2-3  (we have read the paper; see probes.en.yaml header)
Languages:               en (probes.en.yaml) | fr (probes.fr.yaml) | both

Usage
-----
# English only (default)
python audit_pipeline.py

# French only
python audit_pipeline.py --lang fr

# Full sweep
python audit_pipeline.py --lang both --samples 5
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
import yaml

from config import DEFAULT_ORGANISM_URL, DEFAULT_BASELINE_URL

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROBES_FILES: dict[str, str] = {
    "en": "probes.en.yaml",
    "fr": "probes.fr.yaml",
}

TEMPERATURE = 0.8
MAX_NEW_TOKENS = 512
REQUEST_TIMEOUT = 120

# ---------------------------------------------------------------------------
# Model client
# ---------------------------------------------------------------------------

def call_model(
    url: str,
    user_message: str,
    prefill: str | None = None,
    system: str | None = None,
    temperature: float = TEMPERATURE,
    max_new_tokens: int = MAX_NEW_TOKENS,
    retries: int = 3,
) -> str:
    payload: dict[str, Any] = {
        "message": user_message,
        "temperature": temperature,
        "max_new_tokens": max_new_tokens,
        "system": system,
    }

    if prefill:
        payload["message"] = f"{user_message}\n\n[Continue from here]: {prefill}"

    for attempt in range(retries):
        try:
            resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "").strip()
        except requests.Timeout:
            print(f"    [timeout \u2013 attempt {attempt + 1}/{retries}]")
            time.sleep(5 * (attempt + 1))
        except requests.HTTPError as exc:
            print(f"    [HTTP {exc.response.status_code} \u2013 attempt {attempt + 1}/{retries}]")
            time.sleep(3)
        except Exception as exc:
            print(f"    [error: {exc} \u2013 attempt {attempt + 1}/{retries}]")
            time.sleep(3)
    return "[ERROR: all retries exhausted]"


def call_model_scratchpad(
    url: str,
    user_message: str,
    scratchpad_prefill: str,
    temperature: float = TEMPERATURE,
    max_new_tokens: int = MAX_NEW_TOKENS,
) -> str:
    return call_model(
        url=url,
        user_message=user_message,
        system=scratchpad_prefill,
        temperature=temperature,
        max_new_tokens=max_new_tokens,
    )

# ---------------------------------------------------------------------------
# Probe runner
# ---------------------------------------------------------------------------

def run_probe(
    url: str,
    probe: dict[str, Any],
    technique: str,
    n_samples: int,
) -> list[dict[str, Any]]:
    results = []
    user = probe["user"]
    prefill = probe.get("prefill")
    probe_id = probe["id"]

    for sample_idx in range(n_samples):
        print(f"      sample {sample_idx + 1}/{n_samples} \u2026", end=" ", flush=True)

        if technique == "scratchpad_prefill" and prefill:
            raw = call_model_scratchpad(
                url=url,
                user_message=user,
                scratchpad_prefill=prefill,
            )
        elif technique == "assistant_prefill" and prefill:
            raw = call_model(
                url=url,
                user_message=user,
                prefill=prefill,
            )
        else:
            raw = call_model(url=url, user_message=user)

        print("done")

        results.append(
            {
                "probe_id": probe_id,
                "technique": technique,
                "sample": sample_idx,
                "raw_completion": raw,
            }
        )

    return results


def run_audit(
    url: str,
    model_label: str,
    probes_cfg: dict[str, Any],
    levels: list[str],
    techniques: list[str],
    n_samples: int,
    language: str = "en",
) -> list[dict[str, Any]]:
    all_results = []

    for level in levels:
        if level not in probes_cfg:
            print(f"  [skip level '{level}' \u2013 not in YAML]")
            continue

        level_cfg = probes_cfg[level]

        for technique in techniques:
            if technique not in level_cfg:
                print(f"  [skip technique '{technique}' in {level} \u2013 not in YAML]")
                continue

            probes = level_cfg[technique]
            print(f"\n  [{model_label}|{language}] {level} / {technique}  ({len(probes)} probes \u00d7 {n_samples} samples)")

            for probe in probes:
                probe_id = probe["id"]
                print(f"    probe {probe_id}")
                results = run_probe(url=url, probe=probe, technique=technique, n_samples=n_samples)
                for r in results:
                    r["model"] = model_label
                    r["level"] = level
                    r["language"] = language
                    r["user_prompt"] = probe["user"] # Store user prompt for manual scorer
                all_results.extend(results)

    return all_results

def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    cells: dict[tuple, list] = {}
    for r in results:
        lang = r.get("language", "en")
        key = (r["model"], lang, r["level"], r["technique"])
        cells.setdefault(key, []).append(r)

    summary = {}
    for (model, lang, level, technique), items in sorted(cells.items()):
        summary[f"{model}|{lang}|{level}|{technique}"] = {
            "model": model,
            "language": lang,
            "level": level,
            "technique": technique,
            "n_completions": len(items),
        }
    return summary

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Black-box audit pipeline for sl-organism (data collection only)."
    )
    p.add_argument("--lang", choices=["en", "fr", "both"], default="en")
    p.add_argument("--probes-dir", default=str(Path(__file__).parent))
    p.add_argument("--organism-url", default=None)
    p.add_argument("--baseline-url", default=None)
    p.add_argument("--samples", type=int, default=3)
    p.add_argument("--levels", nargs="+", default=["level_1", "level_2"])
    p.add_argument("--techniques", nargs="+", default=["direct_interrogation", "assistant_prefill", "scratchpad_prefill"])
    p.add_argument("--skip-organism", action="store_true")
    p.add_argument("--out", default="results")
    return p.parse_args()


def load_probes(probes_dir: str, lang: str) -> dict[str, Any]:
    filename = PROBES_FILES.get(lang)
    if not filename:
        sys.exit(1)
    path = Path(probes_dir) / filename
    if not path.exists():
        sys.exit(1)
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    args = parse_args()

    organism_url = args.organism_url or os.environ.get("MODAL_URL") or DEFAULT_ORGANISM_URL
    baseline_url = args.baseline_url or DEFAULT_BASELINE_URL

    languages = ["en", "fr"] if args.lang == "both" else [args.lang]

    print("=" * 60)
    print("  Black-Box Audit Pipeline (Data Collection)")
    print("=" * 60)

    all_results: list[dict[str, Any]] = []

    for lang in languages:
        probes_cfg = load_probes(args.probes_dir, lang)
        lang_label = lang.upper()

        if not args.skip_organism:
            print(f"\n>>> Running organism model [{lang_label}] <<<")
            org_results = run_audit(
                url=organism_url,
                model_label="organism",
                probes_cfg=probes_cfg,
                levels=args.levels,
                techniques=args.techniques,
                n_samples=args.samples,
                language=lang,
            )
            all_results.extend(org_results)

        if baseline_url:
            print(f"\n>>> Running baseline model [{lang_label}] <<<")
            bl_results = run_audit(
                url=baseline_url,
                model_label="baseline",
                probes_cfg=probes_cfg,
                levels=args.levels,
                techniques=args.techniques,
                n_samples=args.samples,
                language=lang,
            )
            all_results.extend(bl_results)

    summary = aggregate(all_results)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")

    raw_path = out_dir / f"results_raw_{timestamp}.json"
    raw_path.write_text(
        json.dumps({"results": all_results, "summary": summary}, indent=2),
        encoding="utf-8",
    )
    print(f"\n  [raw JSON written -> {raw_path}]")
    print("\n  Data collection complete. Run manual_scorer.py to evaluate.")

if __name__ == "__main__":
    main()
