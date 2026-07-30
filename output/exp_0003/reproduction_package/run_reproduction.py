#!/usr/bin/env python3
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
        print(f"\nRunning {motor_name}...")
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
    print(f"\n{'=' * 60}")
    if comparison["match"]:
        print("VERDICT: REPRODUCED — Results match reference!")
        print("CLAIM-001 and CLAIM-005 can advance to REPRODUCIBLE level.")
    else:
        print("VERDICT: MISMATCH — Results do NOT match reference!")
        print("Investigate environment differences before advancing claims.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
