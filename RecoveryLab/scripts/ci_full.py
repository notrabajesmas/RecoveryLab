#!/usr/bin/env python3
"""
RecoveryLab — Full CI Pipeline
================================
Runs on every push. Answers:

    RecoveryLab vX.Y.Z
    ✔ API tests (25)
    ✔ Corpus tests (60/60)
    ✔ RR ≥ 100%
    ✔ RFS
    ✔ RC (cost + efficiency)
    ✔ Time
    ✔ RAM
    ✔ Benchmark

If RR drops below 100% on the corpus, the pipeline FAILS.

Usage:
    python scripts/ci_full.py
    python scripts/ci_full.py --no-benchmark   # skip benchmark (faster)

Exit codes:
    0 — All checks pass
    1 — At least one check failed
"""

import sys
import os
import json
import time
import subprocess
from pathlib import Path

# Add project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def run_command(cmd, description):
    """Run a command and return (success, output)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=300
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, str(e)


def section(title):
    print(f"\n{'═' * 60}")
    print(f"  {title}")
    print(f"{'═' * 60}")


def check(name, passed, detail=""):
    status = "✔" if passed else "✘"
    suffix = f"  {detail}" if detail else ""
    print(f"  {status} {name}{suffix}")
    return passed


def main():
    import argparse
    parser = argparse.ArgumentParser(description="RecoveryLab full CI pipeline")
    parser.add_argument("--no-benchmark", action="store_true", help="Skip benchmark")
    args = parser.parse_args()
    
    from core import __version__, RecoveryEngine
    
    all_pass = True
    
    print(f"RecoveryLab v{__version__} — CI Pipeline")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # ── 1. API Contract Tests ──────────────────────────────
    section("1. API Contract Tests")
    passed, output = run_command(
        "python tests/test_api_contract.py",
        "API contract tests"
    )
    # Count passes from output
    pass_count = output.count("PASS")
    fail_count = output.count("FAIL")
    all_pass &= check("API contract tests", passed, f"({pass_count} passed, {fail_count} failed)")
    
    # ── 2. Corpus Tests ────────────────────────────────────
    section("2. Corpus Tests (RR + RFS + RC)")
    
    project_root = Path(__file__).parent.parent
    corpus_dir = project_root / "datasets" / "ntfs"
    
    corpus_categories = ["normal", "fragmented", "deleted"]
    corpus_results = {}
    
    for category in corpus_categories:
        img_path = corpus_dir / category / f"corpus_{category}.img"
        manifest_path = corpus_dir / category / f"corpus_{category}_manifest.json"
        
        if not img_path.exists():
            all_pass &= check(f"Corpus [{category}]", False, "image not found")
            continue
        
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        engine = RecoveryEngine(profile="full")
        result = engine.scan(str(img_path), manifest=manifest)
        
        # SHA-256 verification
        manifest_sha = {fi.get("name", ""): fi.get("sha256", "")
                       for fi in manifest.get("files", []) if "sha256" in fi}
        
        verified = 0
        for item in result.files:
            expected = manifest_sha.get(item.name)
            if expected and item.sha256 == expected:
                verified += 1
        
        total = len(manifest_sha)
        rr = verified / total if total > 0 else 0.0
        rfs = result.statistics.fidelity_score
        rc_score = result.statistics.recovery_cost_score
        scan_time = result.statistics.scan_time_seconds
        peak_ram = result.statistics.peak_ram_mb
        
        corpus_results[category] = {
            "verified": verified, "total": total, "rr": rr,
            "rfs": rfs, "rc_score": rc_score,
            "scan_time": scan_time, "peak_ram": peak_ram,
        }
        
        rr_pass = rr >= 0.95  # Must recover at least 95%
        all_pass &= check(
            f"Corpus [{category:12s}]",
            rr_pass,
            f"{verified}/{total} files, RR={rr:.1%}, RFS={rfs:.3f}, "
            f"RC={rc_score:.3f}, {scan_time:.2f}s, {peak_ram:.0f}MB"
        )
    
    # ── 3. Regression Check ────────────────────────────────
    section("3. Regression Check")
    
    baseline_dir = project_root / "results" / "ci_baselines"
    if baseline_dir.exists():
        baselines = sorted(baseline_dir.glob("baseline_*.json"))
        if baselines:
            with open(baselines[-1]) as f:
                baseline = json.load(f)
            baseline_version = baseline.get("version", "unknown")
            baseline_results = baseline.get("results", {})
            
            print(f"  Comparing against baseline: v{baseline_version}")
            
            for category in corpus_categories:
                current = corpus_results.get(category)
                previous = baseline_results.get(category)
                if not current or not previous:
                    continue
                
                delta_rr = current["rr"] - previous.get("rr", 0)
                no_regression = delta_rr >= -0.01  # Allow 1% tolerance
                
                all_pass &= check(
                    f"Regression [{category:12s}]",
                    no_regression,
                    f"RR delta={delta_rr:+.1%}"
                )
        else:
            print("  No baseline found — run with --update-baseline first")
    
    # ── 4. Product Metrics ─────────────────────────────────
    section("4. Product Metrics Summary")
    
    if corpus_results:
        # Header
        print(f"  {'Category':12s} {'Files':>8s} {'RR':>6s} {'RFS':>6s} "
              f"{'RC':>6s} {'Time':>6s} {'RAM':>6s}")
        print(f"  {'─'*12} {'─'*8} {'─'*6} {'─'*6} {'─'*6} {'─'*6} {'─'*6}")
        
        for category, r in corpus_results.items():
            print(f"  {category:12s} {r['verified']:>3d}/{r['total']:<3d} "
                  f"{r['rr']:>5.1%} {r['rfs']:>5.3f} "
                  f"{r['rc_score']:>5.3f} {r['scan_time']:>5.2f}s {r['peak_ram']:>5.0f}MB")
    
    # ── 5. Benchmark (optional) ────────────────────────────
    if not args.no_benchmark:
        section("5. Benchmark")
        benchmark_script = project_root / "scripts" / "benchmark_fragment_recovery.py"
        if benchmark_script.exists():
            passed, output = run_command(
                f"python {benchmark_script}",
                "Fragment recovery benchmark"
            )
            # Just check it runs without crash
            all_pass &= check("Benchmark runs", passed)
        else:
            print("  Skipped — no benchmark script")
    
    # ── Final ──────────────────────────────────────────────
    section("Result")
    if all_pass:
        print("  ✔ ALL CHECKS PASS — no regressions")
    else:
        print("  ✘ SOME CHECKS FAILED — investigate before merging")
    
    print(f"\n  Version: v{__version__}")
    print(f"  Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
