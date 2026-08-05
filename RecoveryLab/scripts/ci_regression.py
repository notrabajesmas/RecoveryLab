#!/usr/bin/env python3
"""
RecoveryLab — Regression CI Script
====================================
Runs RecoveryEngine against the permanent test corpus and checks:

    "Does this version recover at least as much as the previous one?"

Usage:
    python scripts/ci_regression.py
    python scripts/ci_regression.py --baseline results/baseline_v0.5.0.json
    python scripts/ci_regression.py --update-baseline   # save current as new baseline

Exit codes:
    0 — All checks pass (no regressions)
    1 — Regression detected (some category recovered fewer files)
    2 — Corpus not found (run build_corpus.py first)
"""

import sys
import os
import json
import time
from pathlib import Path

# Add project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


CORPUS_CATEGORIES = ["normal", "fragmented", "deleted"]
BASELINE_DIR = Path(__file__).parent.parent / "results" / "ci_baselines"


def run_corpus():
    """Run RecoveryEngine against all corpus categories."""
    from core import RecoveryEngine, __version__
    
    project_root = Path(__file__).parent.parent
    corpus_dir = project_root / "datasets" / "ntfs"
    
    if not corpus_dir.exists():
        print("ERROR: Corpus directory not found. Run: python scripts/build_corpus.py")
        return None, 2
    
    print(f"RecoveryLab v{__version__} — Regression CI")
    print("=" * 60)
    print()
    
    results = {}
    all_pass = True
    
    for category in CORPUS_CATEGORIES:
        cat_dir = corpus_dir / category
        img_path = cat_dir / f"corpus_{category}.img"
        manifest_path = cat_dir / f"corpus_{category}_manifest.json"
        
        if not img_path.exists():
            print(f"  [{category}] SKIP — image not found (run build_corpus.py --category {category})")
            continue
        
        # Load manifest
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        # Run scan
        engine = RecoveryEngine(profile="full")
        t0 = time.time()
        result = engine.scan(str(img_path), manifest=manifest)
        scan_time = time.time() - t0
        
        # Count SHA-256 verified
        manifest_sha = {fi.get("name", ""): fi.get("sha256", "")
                       for fi in manifest.get("files", []) if "sha256" in fi}
        
        verified = 0
        for item in result.files:
            expected = manifest_sha.get(item.name)
            if expected and item.sha256 == expected:
                verified += 1
        
        total = len(manifest_sha)
        rr = verified / total if total > 0 else 0.0
        
        results[category] = {
            "verified": verified,
            "total": total,
            "rr": rr,
            "scan_time": result.statistics.scan_time_seconds,
            "peak_ram_mb": result.statistics.peak_ram_mb,
            "recovery_rate": result.statistics.recovery_rate,
            "fidelity_score": result.statistics.fidelity_score,
        }
        
        status = "PASS" if rr >= 0.95 else "WARN" if rr >= 0.80 else "FAIL"
        if status == "FAIL":
            all_pass = False
        
        print(f"  [{category:12s}] {verified:>3d}/{total:<3d} files  "
              f"RR={rr:>6.1%}  RFS={result.statistics.fidelity_score:.3f}  "
              f"time={result.statistics.scan_time_seconds:.2f}s  "
              f"RAM={result.statistics.peak_ram_mb:.0f}MB  [{status}]")
    
    return results, 0 if all_pass else 1


def check_regression(results, baseline_path=None):
    """Compare current results against baseline."""
    from core import __version__
    
    if baseline_path is None:
        # Find latest baseline
        if not BASELINE_DIR.exists():
            print("\n  No baseline found. Run with --update-baseline to create one.")
            return True
        baselines = sorted(BASELINE_DIR.glob("baseline_*.json"))
        if not baselines:
            print("\n  No baseline found. Run with --update-baseline to create one.")
            return True
        baseline_path = baselines[-1]
    
    with open(baseline_path) as f:
        baseline = json.load(f)
    
    baseline_version = baseline.get("version", "unknown")
    baseline_results = baseline.get("results", {})
    
    print()
    print(f"  Comparing against baseline: v{baseline_version}")
    print("─" * 60)
    
    no_regression = True
    for category in CORPUS_CATEGORIES:
        current = results.get(category)
        previous = baseline_results.get(category)
        
        if not current or not previous:
            continue
        
        delta_rr = current["rr"] - previous["rr"]
        delta_verified = current["verified"] - previous["verified"]
        
        if delta_rr < -0.01:  # More than 1% regression
            print(f"  [{category:12s}] REGRESSION: RR {previous['rr']:.1%} → {current['rr']:.1%} "
                  f"(delta={delta_rr:+.1%})")
            no_regression = False
        elif delta_verified < 0:
            print(f"  [{category:12s}] REGRESSION: verified {previous['verified']} → {current['verified']} "
                  f"({delta_verified:+d} files)")
            no_regression = False
        else:
            print(f"  [{category:12s}] OK: RR {current['rr']:.1%} "
                  f"(delta={delta_rr:+.1%}, files={delta_verified:+d})")
    
    return no_regression


def save_baseline(results):
    """Save current results as the new baseline."""
    from core import __version__
    
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    baseline_path = BASELINE_DIR / f"baseline_v{__version__}.json"
    
    baseline = {
        "version": __version__,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "results": results,
    }
    
    baseline_path.write_text(json.dumps(baseline, indent=2))
    print(f"\n  Baseline saved: {baseline_path}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="RecoveryLab regression CI")
    parser.add_argument("--baseline", help="Path to baseline results JSON")
    parser.add_argument("--update-baseline", action="store_true",
                       help="Save current results as new baseline")
    
    args = parser.parse_args()
    
    results, exit_code = run_corpus()
    if results is None:
        return exit_code
    
    if args.update_baseline:
        save_baseline(results)
        return 0
    
    # Check regression
    no_regression = check_regression(results, args.baseline)
    
    print()
    if no_regression:
        print("  Result: NO REGRESSION — all checks pass")
    else:
        print("  Result: REGRESSION DETECTED — some categories recovered fewer files")
    
    return 0 if no_regression else 1


if __name__ == "__main__":
    sys.exit(main())
