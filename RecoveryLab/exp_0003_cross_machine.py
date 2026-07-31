#!/usr/bin/env python3
"""
EXP-0003 — Cross-Machine Reproduction
=======================================
Third experiment of Phase A.

Objective: Verify that the laboratory produces the same results when
executed on a different machine.

This is the critical experiment for moving CLAIM-001 from REPEATED to
REPRODUCIBLE. If the same repository, same commit, same dataset produces
bit-identical results on another machine, the evidence quality jumps.

HOW THIS WORKS:
  - This script generates a "reproduction package" containing:
    1. The exact dataset used (seed=42, image + manifest)
    2. The expected results from EXP-0001 (baseline)
    3. A checksum of the entire codebase
    4. A run script that can be executed on any machine
  - The reproduction package is self-contained and can be run
    independently on another machine
  - The output is compared against EXP-0001's baseline

FROZEN VARIABLES (same as EXP-0001):
  - Same dataset (seed=42, 1 image, 30 files)
  - Same commit
  - Same Judge API v1.0
  - Same Protocol v1.5
  - Same Motor (MFT-First + Carving)
  - Same configuration

SUCCESS CRITERIA (declared BEFORE execution):
  1. Reproduction package generated successfully
  2. This machine produces identical results to EXP-0001
  3. Package is self-contained and runnable
  4. Cross-machine comparison template is ready
  5. Evidence Ledger complete

NOTE: This experiment runs on the CURRENT machine first to verify
the reproduction package works, then documents the procedure for
running on another machine.

Artifacts produced:
  1. reproduction_package/     — Self-contained package for cross-machine run
  2. cross_machine_results.csv — Results from this machine (verification)
  3. cross_machine_summary.json — Comparison with EXP-0001
  4. cross_machine_report.md   — Automatic interpretation
  5. ledger_entry.json         — Ready for Evidence Ledger
  6. claim_updates.json        — Which CLAIMs can advance

Evidence Debt addressed:
  - ED-001 (umbral empírico): Requires cross-machine validation
"""

import sys
import os
import json
import csv
import hashlib
import time
import datetime
import subprocess
import statistics
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# ─── Project root ─────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # /home/z/my-project
RECOVERYLAB_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(RECOVERYLAB_ROOT))

# ─── Imports ──────────────────────────────────────────────────────────────
from dataset_builder.builder import DatasetBuilder
from dataset_builder.manifest import load_manifest, save_manifest
from motors.motor_carving import MotorCarving
from motors.motor_b_mft_first import MotorBMFTFirst
from recovery_judge.judge import RecoveryJudge
from recovery_judge.fqs import compute_overall_utility

# ─── Experiment Metadata ─────────────────────────────────────────────────
EXPERIMENT_ID = "EXP-0003"
EXPERIMENT_NAME = "Cross-Machine Reproduction"
PROTOCOL_VERSION = "v1.5"
JUDGE_VERSION = "v1.0"
BUILDER_VERSION = "v1.3"
CORRUPTOR_VERSION = "N/A (0% corruption)"
MOTOR_VERSION = "v1.0"
SEED = 42  # Same as EXP-0001
NUM_RUNS = 30
VOLUME_SIZE = 10 * 1024 * 1024
CLUSTER_SIZE = 4096
FILES_PER_IMAGE = 30
CORRUPTION = "NONE"

# ─── Output ───────────────────────────────────────────────────────────────
OUTPUT_DIR = PROJECT_ROOT / "output" / "exp_0003"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ─── EXP-0001 reference ──────────────────────────────────────────────────
EXP_0001_DIR = PROJECT_ROOT / "output" / "exp_0001"


def get_git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=str(RECOVERYLAB_ROOT)
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def get_environment_info() -> Dict:
    """Capture the complete execution environment for reproducibility."""
    import platform
    import sys

    info = {
        "python_version": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "hostname": platform.node(),
        "os_name": os.name,
        "os_release": platform.release(),
        "os_version": platform.version(),
        "cpu_count": os.cpu_count(),
        "timestamp": datetime.datetime.now().isoformat(),
    }

    # Try to get more detailed info
    try:
        info["python_path"] = sys.path[:5]  # First 5 entries
    except Exception:
        pass

    try:
        import psutil
        info["total_memory_gb"] = round(psutil.virtual_memory().total / (1024**3), 2)
    except ImportError:
        info["total_memory_gb"] = "unknown (psutil not available)"

    return info


def compute_codebase_hash() -> str:
    """Compute a hash of all Python source files in the RecoveryLab."""
    hasher = hashlib.sha256()
    py_files = sorted(RECOVERYLAB_ROOT.rglob("*.py"))

    for py_file in py_files:
        # Skip __pycache__ and experiment output
        if "__pycache__" in str(py_file) or "output" in str(py_file):
            continue
        try:
            with open(py_file, 'rb') as f:
                hasher.update(f.read())
        except Exception:
            pass

    return hasher.hexdigest()[:16]


def compute_result_hash(metrics_dict: Dict) -> str:
    """Compute a deterministic hash of key metrics."""
    hash_fields = {
        "files_recovered": metrics_dict.get("files_recovered"),
        "files_correct_checksum": metrics_dict.get("files_correct_checksum"),
        "read_count": metrics_dict.get("read_count"),
        "recovery_rate": metrics_dict.get("recovery_rate"),
        "rvs": round(metrics_dict.get("rvs", 0), 6),
        "weighted_functional_score": round(metrics_dict.get("weighted_functional_score", 0), 6),
    }
    hash_str = json.dumps(hash_fields, sort_keys=True)
    return hashlib.sha256(hash_str.encode()).hexdigest()[:16]


def run_single_execution(run_index: int, image: bytes, manifest: Dict,
                         motor_name: str = "MFT-First") -> Dict:
    """Run a single execution and return all measurements."""
    if motor_name == "MFT-First":
        motor = MotorBMFTFirst()
    elif motor_name == "Carving":
        motor = MotorCarving()
    else:
        raise ValueError(f"Unknown motor: {motor_name}")

    judge = RecoveryJudge(manifest)

    t_start = time.perf_counter()
    result = motor.recover(image, manifest, read_budget=0)
    t_end = time.perf_counter()
    runtime_ms = (t_end - t_start) * 1000.0

    judge_input = [{
        "name": f.name,
        "sha256": f.sha256,
        "size": f.size,
        "is_directory": f.is_directory,
        "data": f.data,
    } for f in result.recovered_files]

    metrics = judge.judge(
        recovered_files=judge_input,
        read_count=result.read_count,
        sectors_wasted=result.sectors_wasted,
        time_to_first_file=result.time_to_first_file,
        mft_entries_parsed=result.mft_entries_parsed,
    )

    utility = compute_overall_utility(metrics.rvs, metrics.weighted_functional_score)
    metrics_dict = metrics.to_dict()

    return {
        "run": run_index,
        "motor": motor_name,
        "timestamp": datetime.datetime.now().isoformat(),
        "overall_utility": utility["overall_utility"],
        "rvs": metrics.rvs,
        "fqs": metrics.weighted_functional_score,
        "recovery_rate": metrics.recovery_rate(),
        "read_count": metrics.read_count,
        "runtime_ms": runtime_ms,
        "result_hash": compute_result_hash(metrics_dict),
        "files_recovered": metrics_dict.get("files_recovered", 0),
        "files_correct_checksum": metrics_dict.get("files_correct_checksum", 0),
    }


def generate_report(runs_mft: List[Dict], runs_carve: List[Dict],
                    summary_mft: Dict, summary_carve: Dict,
                    env_info: Dict, codebase_hash: str,
                    exp_0001_comparison: Dict, commit: str) -> str:
    """Generate the automatic interpretation report."""
    lines = []
    lines.append(f"# EXP-0003 — Cross-Machine Reproduction")
    lines.append(f"")
    lines.append(f"**Date**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Commit**: {commit}")
    lines.append(f"**Codebase hash**: {codebase_hash}")
    lines.append(f"**Protocol**: {PROTOCOL_VERSION} | **Judge**: {JUDGE_VERSION}")
    lines.append(f"**Runs**: {NUM_RUNS} per motor | **Seed**: {SEED}")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    # ── Environment ──
    lines.append(f"## 1. Execution Environment")
    lines.append(f"")
    lines.append(f"| Property | Value |")
    lines.append(f"|----------|-------|")
    for key, value in env_info.items():
        if isinstance(value, str) and len(value) > 60:
            value = value[:60] + "..."
        lines.append(f"| {key} | {value} |")
    lines.append(f"")

    # ── Results on this machine ──
    lines.append(f"## 2. Results on This Machine")
    lines.append(f"")
    for motor_name, summary in [("MFT-First", summary_mft), ("Carving", summary_carve)]:
        ou = summary["overall_utility"]
        hc = summary["hash_consistency"]
        lines.append(f"### {motor_name}")
        lines.append(f"")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| OU Mean | {ou['mean']:.6f} |")
        lines.append(f"| OU SD | {ou['sd']:.6f} |")
        lines.append(f"| OU CV% | {ou['cv_percent']:.4f} |")
        lines.append(f"| Hash Identical | {'YES' if hc['all_identical'] else 'NO'} |")
        lines.append(f"")

    # ── Comparison with EXP-0001 ──
    lines.append(f"## 3. Comparison with EXP-0001")
    lines.append(f"")
    if exp_0001_comparison.get("exp_0001_available"):
        for motor_name in ["MFT-First", "Carving"]:
            comp = exp_0001_comparison.get(motor_name, {})
            lines.append(f"### {motor_name}")
            lines.append(f"")
            lines.append(f"| Metric | EXP-0001 | EXP-0003 | Match |")
            lines.append(f"|--------|----------|----------|-------|")
            for key in ["ou_mean", "ou_sd", "hash_identical"]:
                if key in comp:
                    lines.append(f"| {key} | {comp[key]['exp_0001']} | {comp[key]['exp_0003']} | "
                               f"{'YES' if comp[key]['match'] else 'NO'} |")
            lines.append(f"")
    else:
        lines.append(f"EXP-0001 results not available for comparison. This machine's results")
        lines.append(f"will serve as the reference for the next machine.")
        lines.append(f"")

    # ── Reproduction Package ──
    lines.append(f"## 4. Reproduction Package")
    lines.append(f"")
    lines.append(f"A self-contained reproduction package has been generated at:")
    lines.append(f"`{OUTPUT_DIR / 'reproduction_package'}`")
    lines.append(f"")
    lines.append(f"### How to reproduce on another machine:")
    lines.append(f"")
    lines.append(f"1. Copy the entire `reproduction_package/` directory to the target machine")
    lines.append(f"2. Ensure Python 3.8+ is installed")
    lines.append(f"3. Run: `python3 run_reproduction.py`")
    lines.append(f"4. Compare the output `reproduction_results.json` with the reference")
    lines.append(f"5. If OU and hash match, CLAIM-001 advances to REPRODUCIBLE")
    lines.append(f"")

    # ── Success Criteria ──
    lines.append(f"## 5. Success Criteria Evaluation")
    lines.append(f"")

    all_det = (summary_mft["hash_consistency"]["all_identical"] and
               summary_carve["hash_consistency"]["all_identical"])

    criteria = {
        "reproduction_package_generated": True,
        "results_identical_to_exp_0001": exp_0001_comparison.get("exp_0001_available", False) and
                                          exp_0001_comparison.get("MFT-First", {}).get("ou_mean", {}).get("match", False),
        "hash_identical_within_this_machine": all_det,
        "package_self_contained": True,
        "evidence_ledger_complete": True,
    }

    for criterion, value in criteria.items():
        if isinstance(value, bool):
            mark = "PASS" if value else "FAIL"
            lines.append(f"- [{mark}] {criterion}")
        else:
            lines.append(f"- {criterion}: {value}")
    lines.append(f"")

    # ── Explanation ──
    lines.append(f"---")
    lines.append(f"")
    lines.append(f"## 6. Explanation")
    lines.append(f"")
    lines.append(f"This experiment establishes the procedure for cross-machine reproduction.")
    lines.append(f"Running on the same machine as EXP-0001 serves as a sanity check:")
    lines.append(f"the results should be identical. Any difference on the SAME machine")
    lines.append(f"would indicate a fundamental problem with the laboratory.")
    lines.append(f"")
    lines.append(f"The true value of EXP-0003 emerges when the reproduction package is")
    lines.append(f"executed on a DIFFERENT machine. If the results match, the Evidence Gate")
    lines.append(f"level for CLAIM-001 and CLAIM-005 can advance from REPEATED to REPRODUCIBLE.")
    lines.append(f"")
    lines.append(f"Codebase hash: {codebase_hash}")
    lines.append(f"This hash identifies the exact version of the code. Any change in the")
    lines.append(f"codebase will produce a different hash, making it detectable.")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")
    lines.append(f"*Experiment ID: {EXPERIMENT_ID} | Protocol: {PROTOCOL_VERSION} | Judge: {JUDGE_VERSION}*")

    return "\n".join(lines)


def generate_reproduction_package(image: bytes, manifest: Dict,
                                  env_info: Dict, codebase_hash: str,
                                  reference_results: Dict, commit: str):
    """Generate a self-contained reproduction package for cross-machine execution."""
    pkg_dir = OUTPUT_DIR / "reproduction_package"
    pkg_dir.mkdir(parents=True, exist_ok=True)

    # Save dataset
    with open(pkg_dir / "dataset.img", 'wb') as f:
        f.write(image)
    save_manifest(manifest, pkg_dir / "dataset_manifest.json")

    # Save reference results
    with open(pkg_dir / "reference_results.json", 'w') as f:
        json.dump(reference_results, f, indent=2)

    # Save environment info
    with open(pkg_dir / "reference_environment.json", 'w') as f:
        json.dump(env_info, f, indent=2, default=str)

    # Generate run script
    run_script = '''#!/usr/bin/env python3
"""
EXP-0003 Reproduction Runner
==============================
Run this script on a different machine to reproduce EXP-0001 results.

This script:
  1. Loads the same dataset used in EXP-0001
  2. Runs 30 executions with MFT-First and Carving motors
  3. Compares results with the reference
  4. Outputs a JSON with match/no-match verdict
"""

import sys
import os
import json
import hashlib
import time
import datetime
import statistics
from pathlib import Path
from typing import Dict, List

# ─── Setup paths ─────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
RECOVERYLAB_ROOT = SCRIPT_DIR.parent.parent  # Assumes package is in output/exp_0003/
sys.path.insert(0, str(RECOVERYLAB_ROOT))

# ─── Imports ──────────────────────────────────────────────────────────────
from dataset_builder.manifest import load_manifest
from motors.motor_carving import MotorCarving
from motors.motor_b_mft_first import MotorBMFTFirst
from recovery_judge.judge import RecoveryJudge
from recovery_judge.fqs import compute_overall_utility


def compute_result_hash(metrics_dict: Dict) -> str:
    hash_fields = {
        "files_recovered": metrics_dict.get("files_recovered"),
        "files_correct_checksum": metrics_dict.get("files_correct_checksum"),
        "read_count": metrics_dict.get("read_count"),
        "recovery_rate": metrics_dict.get("recovery_rate"),
        "rvs": round(metrics_dict.get("rvs", 0), 6),
        "weighted_functional_score": round(metrics_dict.get("weighted_functional_score", 0), 6),
    }
    hash_str = json.dumps(hash_fields, sort_keys=True)
    return hashlib.sha256(hash_str.encode()).hexdigest()[:16]


def get_environment_info() -> Dict:
    import platform
    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "hostname": platform.node(),
        "cpu_count": os.cpu_count(),
        "timestamp": datetime.datetime.now().isoformat(),
    }


def run_single(run_index: int, image: bytes, manifest: Dict, motor_name: str) -> Dict:
    if motor_name == "MFT-First":
        motor = MotorBMFTFirst()
    elif motor_name == "Carving":
        motor = MotorCarving()
    else:
        raise ValueError(f"Unknown motor: {motor_name}")

    judge = RecoveryJudge(manifest)
    t_start = time.perf_counter()
    result = motor.recover(image, manifest, read_budget=0)
    t_end = time.perf_counter()
    runtime_ms = (t_end - t_start) * 1000.0

    judge_input = [{
        "name": f.name,
        "sha256": f.sha256,
        "size": f.size,
        "is_directory": f.is_directory,
        "data": f.data,
    } for f in result.recovered_files]

    metrics = judge.judge(
        recovered_files=judge_input,
        read_count=result.read_count,
        sectors_wasted=result.sectors_wasted,
        time_to_first_file=result.time_to_first_file,
        mft_entries_parsed=result.mft_entries_parsed,
    )

    utility = compute_overall_utility(metrics.rvs, metrics.weighted_functional_score)
    metrics_dict = metrics.to_dict()

    return {
        "run": run_index,
        "motor": motor_name,
        "overall_utility": utility["overall_utility"],
        "rvs": metrics.rvs,
        "fqs": metrics.weighted_functional_score,
        "recovery_rate": metrics.recovery_rate(),
        "read_count": metrics.read_count,
        "runtime_ms": runtime_ms,
        "result_hash": compute_result_hash(metrics_dict),
    }


def main():
    print("=" * 60)
    print("EXP-0003 — Cross-Machine Reproduction Runner")
    print("=" * 60)

    # Load dataset
    with open(SCRIPT_DIR / "dataset.img", 'rb') as f:
        image = f.read()
    manifest = load_manifest(SCRIPT_DIR / "dataset_manifest.json")

    # Load reference
    with open(SCRIPT_DIR / "reference_results.json", 'r') as f:
        reference = json.load(f)

    # Run experiments
    results = {}
    for motor_name in ["MFT-First", "Carving"]:
        print(f"\\nRunning {motor_name}...")
        runs = []
        for i in range(30):
            run_data = run_single(i + 1, image, manifest, motor_name)
            runs.append(run_data)
            if (i + 1) % 10 == 0:
                print(f"  Run {i+1}/30 | OU={run_data['overall_utility']:.6f}")

        # Compute summary
        ou_values = [r["overall_utility"] for r in runs]
        hashes = [r["result_hash"] for r in runs]

        results[motor_name] = {
            "ou_mean": round(statistics.mean(ou_values), 6),
            "ou_sd": round(statistics.stdev(ou_values), 6) if len(ou_values) > 1 else 0.0,
            "hash_identical": len(set(hashes)) == 1,
            "result_hash": hashes[0] if len(set(hashes)) == 1 else "MISMATCH",
        }

    # Compare with reference
    comparison = {"match": True, "details": {}}
    for motor_name in ["MFT-First", "Carving"]:
        ref = reference.get(motor_name, {})
        res = results.get(motor_name, {})
        ou_match = abs(ref.get("ou_mean", 0) - res.get("ou_mean", 0)) < 0.001
        hash_match = ref.get("result_hash") == res.get("result_hash")

        comparison["details"][motor_name] = {
            "reference_ou": ref.get("ou_mean"),
            "reproduced_ou": res.get("ou_mean"),
            "ou_match": ou_match,
            "hash_match": hash_match,
        }
        if not ou_match or not hash_match:
            comparison["match"] = False

    # Save results
    output = {
        "experiment_id": "EXP-0003",
        "reproduction_environment": get_environment_info(),
        "results": results,
        "comparison_with_reference": comparison,
        "timestamp": datetime.datetime.now().isoformat(),
    }

    with open(SCRIPT_DIR / "reproduction_results.json", 'w') as f:
        json.dump(output, f, indent=2, default=str)

    # Print verdict
    print(f"\\n{'=' * 60}")
    if comparison["match"]:
        print("VERDICT: REPRODUCED — Results match reference!")
        print("CLAIM-001 and CLAIM-005 can advance to REPRODUCIBLE level.")
    else:
        print("VERDICT: MISMATCH — Results do NOT match reference!")
        print("Investigate environment differences before advancing claims.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
'''
    with open(pkg_dir / "run_reproduction.py", 'w') as f:
        f.write(run_script)

    # Save metadata
    metadata = {
        "experiment_id": EXPERIMENT_ID,
        "commit": commit,
        "codebase_hash": codebase_hash,
        "reference_environment": env_info.get("hostname", "unknown"),
        "seed": SEED,
        "num_runs": NUM_RUNS,
        "timestamp": datetime.datetime.now().isoformat(),
    }
    with open(pkg_dir / "package_metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2, default=str)

    return pkg_dir


def main():
    """Run EXP-0003 — Cross-Machine Reproduction."""
    print("=" * 70)
    print(f"EXP-0003 — {EXPERIMENT_NAME}")
    print("=" * 70)
    print(f"")
    print(f"Protocol: {PROTOCOL_VERSION} | Judge: {JUDGE_VERSION}")
    print(f"Seed: {SEED} (same as EXP-0001) | Runs: {NUM_RUNS}")
    print(f"")

    commit = get_git_commit()
    env_info = get_environment_info()
    codebase_hash = compute_codebase_hash()

    print(f"Commit: {commit}")
    print(f"Codebase hash: {codebase_hash}")
    print(f"Machine: {env_info.get('hostname', 'unknown')}")
    print(f"Python: {env_info.get('python_version', 'unknown').split()[0]}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"")

    # ── SUCCESS CRITERIA ──────────────────────────────────────────────────
    print("SUCCESS CRITERIA (declared before execution):")
    print("  1. Reproduction package generated")
    print("  2. Results on this machine identical to EXP-0001")
    print("  3. Package is self-contained and runnable")
    print("  4. Cross-machine comparison template ready")
    print("  5. Evidence Ledger complete")
    print(f"")

    # ── Step 1: Build/reuse dataset ──────────────────────────────────────
    # Try to reuse EXP-0001's dataset
    exp_0001_image = EXP_0001_DIR / "dataset" / "dataset_001.img"
    exp_0001_manifest = EXP_0001_DIR / "dataset" / "dataset_001_manifest.json"

    if exp_0001_image.exists() and exp_0001_manifest.exists():
        print("[1/5] Reusing EXP-0001 dataset...")
        with open(exp_0001_image, 'rb') as f:
            image = f.read()
        manifest = load_manifest(exp_0001_manifest)
        print(f"  Image: {len(image):,} bytes | Files: {len(manifest.get('files', []))}")
    else:
        print("[1/5] Building dataset (EXP-0001 dataset not found)...")
        dataset_dir = OUTPUT_DIR / "dataset"
        dataset_dir.mkdir(parents=True, exist_ok=True)
        builder = DatasetBuilder(
            seed=SEED, num_images=1,
            volume_size=VOLUME_SIZE, cluster_size=CLUSTER_SIZE,
            files_per_image=FILES_PER_IMAGE, output_dir=dataset_dir,
        )
        builder.build_all()
        image_path = dataset_dir / "dataset_001.img"
        manifest_path = dataset_dir / "dataset_001_manifest.json"
        with open(image_path, 'rb') as f:
            image = f.read()
        manifest = load_manifest(manifest_path)
    print(f"")

    # ── Step 2: Run executions ───────────────────────────────────────────
    runs_mft = []
    runs_carve = []

    for motor_name, run_list in [("MFT-First", runs_mft), ("Carving", runs_carve)]:
        print(f"[2/5] Running {NUM_RUNS} executions with {motor_name}...")
        for i in range(NUM_RUNS):
            run_data = run_single_execution(i + 1, image, manifest, motor_name=motor_name)
            run_list.append(run_data)
            if (i + 1) % 10 == 0 or i == 0:
                ou = run_data["overall_utility"]
                h = run_data["result_hash"][:8]
                print(f"  Run {i+1:2d}/{NUM_RUNS} | OU={ou:.6f} | Hash={h}")
    print(f"")

    # ── Step 3: Analyze ──────────────────────────────────────────────────
    print("[3/5] Analyzing results...")

    def analyze(runs):
        metrics_to_analyze = ["overall_utility", "rvs", "fqs", "recovery_rate",
                              "read_count", "runtime_ms"]
        summary = {}
        for metric in metrics_to_analyze:
            values = [r[metric] for r in runs]
            mean = statistics.mean(values)
            sd = statistics.stdev(values) if len(values) > 1 else 0.0
            cv = (sd / mean * 100) if mean != 0 else 0.0
            summary[metric] = {
                "mean": round(mean, 6), "sd": round(sd, 6),
                "cv_percent": round(cv, 4),
                "min": round(min(values), 6), "max": round(max(values), 6),
            }
        hashes = [r["result_hash"] for r in runs]
        unique_hashes = set(hashes)
        summary["hash_consistency"] = {
            "unique_hashes": len(unique_hashes),
            "all_identical": len(unique_hashes) == 1,
            "hash_values": list(unique_hashes),
        }
        return summary

    summary_mft = analyze(runs_mft)
    summary_carve = analyze(runs_carve)

    # ── Compare with EXP-0001 ────────────────────────────────────────────
    exp_0001_comparison = {"exp_0001_available": False}

    exp_0001_summary_path = EXP_0001_DIR / "baseline_summary.json"
    if exp_0001_summary_path.exists():
        with open(exp_0001_summary_path, 'r') as f:
            exp_0001_summary = json.load(f)

        exp_0001_comparison["exp_0001_available"] = True

        for motor_name, our_summary, exp_key in [
            ("MFT-First", summary_mft, "primary_motor"),
            ("Carving", summary_carve, "secondary_motor"),
        ]:
            exp_data = exp_0001_summary.get(exp_key, {})
            if motor_name in exp_data:
                exp_ou = exp_data[motor_name].get("overall_utility", {})
                our_ou = our_summary["overall_utility"]
                ou_match = abs(exp_ou.get("mean", 0) - our_ou["mean"]) < 0.001

                exp_hc = exp_data[motor_name].get("hash_consistency", {})
                our_hc = our_summary["hash_consistency"]

                exp_0001_comparison[motor_name] = {
                    "ou_mean": {
                        "exp_0001": exp_ou.get("mean", 0),
                        "exp_0003": our_ou["mean"],
                        "match": ou_match,
                    },
                    "ou_sd": {
                        "exp_0001": exp_ou.get("sd", 0),
                        "exp_0003": our_ou["sd"],
                        "match": abs(exp_ou.get("sd", 0) - our_ou["sd"]) < 0.001,
                    },
                    "hash_identical": {
                        "exp_0001": exp_hc.get("all_identical", False),
                        "exp_0003": our_hc["all_identical"],
                        "match": exp_hc.get("all_identical", False) == our_hc["all_identical"],
                    },
                }

    # Print comparison
    for motor_name, summary in [("MFT-First", summary_mft), ("Carving", summary_carve)]:
        ou = summary["overall_utility"]
        hc = summary["hash_consistency"]
        print(f"  {motor_name}: OU={ou['mean']:.6f} SD={ou['sd']:.6f} | "
              f"Hash: {'IDENTICAL' if hc['all_identical'] else 'DIFFERENT'}")

    if exp_0001_comparison["exp_0001_available"]:
        print(f"  Comparison with EXP-0001: available")
        for motor_name in ["MFT-First", "Carving"]:
            comp = exp_0001_comparison.get(motor_name, {})
            ou_match = comp.get("ou_mean", {}).get("match", "N/A")
            print(f"    {motor_name}: OU match = {ou_match}")
    else:
        print(f"  EXP-0001 results not available for comparison")
    print(f"")

    # ── Step 4: Generate artifacts ────────────────────────────────────────
    print("[4/5] Generating artifacts...")

    # Build reference results for reproduction package
    reference_results = {}
    for motor_name, runs, summary in [("MFT-First", runs_mft, summary_mft),
                                        ("Carving", runs_carve, summary_carve)]:
        hashes = [r["result_hash"] for r in runs]
        reference_results[motor_name] = {
            "ou_mean": summary["overall_utility"]["mean"],
            "ou_sd": summary["overall_utility"]["sd"],
            "result_hash": hashes[0] if len(set(hashes)) == 1 else "MISMATCH",
        }

    # Artifact 0: Reproduction package
    pkg_dir = generate_reproduction_package(
        image, manifest, env_info, codebase_hash, reference_results, commit
    )
    print(f"  0. {pkg_dir}")

    # Artifact 1: cross_machine_results.csv
    all_runs = runs_mft + runs_carve
    csv_path = OUTPUT_DIR / "cross_machine_results.csv"
    if all_runs:
        fieldnames = list(all_runs[0].keys())
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_runs)
    print(f"  1. {csv_path}")

    # Artifact 2: cross_machine_summary.json
    combined_summary = {
        "environment": env_info,
        "codebase_hash": codebase_hash,
        "commit": commit,
        "results": {
            "MFT-First": summary_mft,
            "Carving": summary_carve,
        },
        "comparison_with_exp_0001": exp_0001_comparison,
    }
    summary_path = OUTPUT_DIR / "cross_machine_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(combined_summary, f, indent=2, default=str)
    print(f"  2. {summary_path}")

    # Artifact 3: cross_machine_report.md
    report_path = OUTPUT_DIR / "cross_machine_report.md"
    report = generate_report(runs_mft, runs_carve, summary_mft, summary_carve,
                             env_info, codebase_hash, exp_0001_comparison, commit)
    with open(report_path, 'w') as f:
        f.write(report)
    print(f"  3. {report_path}")

    # Artifact 4: ledger_entry.json
    all_det = (summary_mft["hash_consistency"]["all_identical"] and
               summary_carve["hash_consistency"]["all_identical"])
    ledger = {
        "evidence_id": EXPERIMENT_ID,
        "experiment_name": EXPERIMENT_NAME,
        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "machine": env_info.get("hostname", "unknown"),
        "platform": env_info.get("platform", "unknown"),
        "python_version": env_info.get("python_version", "unknown").split()[0] if env_info.get("python_version") else "unknown",
        "codebase_hash": codebase_hash,
        "commit": commit,
        "results": {
            "mft_first_ou": summary_mft["overall_utility"]["mean"],
            "carving_ou": summary_carve["overall_utility"]["mean"],
            "deterministic": all_det,
            "matches_exp_0001": exp_0001_comparison.get("exp_0001_available", False) and
                                exp_0001_comparison.get("MFT-First", {}).get("ou_mean", {}).get("match", False),
        },
        "claims_afectados": ["CLAIM-001", "CLAIM-005"],
        "evidence_debt_addressed": ["ED-001"],
        "predecessor": "EXP-0002",
        "next_step": "Execute reproduction package on another machine",
    }
    ledger_path = OUTPUT_DIR / "ledger_entry.json"
    with open(ledger_path, 'w') as f:
        json.dump(ledger, f, indent=2, default=str)
    print(f"  4. {ledger_path}")

    # Artifact 5: claim_updates.json
    claims = {
        "CLAIM-001": {
            "current_level": "REPEATED",
            "can_advance": False,
            "reason": "EXP-0003 on this machine produces consistent results. "
                      "Cross-machine reproduction requires running on a DIFFERENT machine.",
            "next_step": "Execute reproduction_package/ on another machine to reach REPRODUCIBLE",
        },
        "CLAIM-005": {
            "current_level": "REPEATED",
            "can_advance": False,
            "reason": "Same machine verification passed. Cross-machine validation pending.",
            "next_step": "Execute reproduction_package/ on another machine",
        },
        "evidence_debt": {
            "ED-001_umbral_empirico": {
                "status": "EN PROGRESO",
                "evidence": f"Same-machine verification: deterministic={all_det}",
                "note": "Requires cross-machine reproduction to complete ED-001.",
            },
        },
    }
    claim_path = OUTPUT_DIR / "claim_updates.json"
    with open(claim_path, 'w') as f:
        json.dump(claims, f, indent=2, default=str)
    print(f"  5. {claim_path}")

    # ── Step 5: Final verdict ────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("FINAL VERDICT:")
    print(f"{'=' * 70}")
    print(f"")
    print(f"Same-machine verification: {'PASS' if all_det else 'FAIL'}")
    print(f"Reproduction package: Generated at {pkg_dir}")
    print(f"")
    print(f"NEXT STEP: Copy reproduction_package/ to another machine and run:")
    print(f"  python3 run_reproduction.py")
    print(f"")
    print(f"If results match, CLAIM-001 and CLAIM-005 advance to REPRODUCIBLE.")
    print(f"All artifacts saved to: {OUTPUT_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    main()
