"""
RecoveryLab — Stability Test (Objeción 5)
============================================
Run the same scenario N times and verify deterministic results.

If the same scenario produces different results, there's a bug.
The laboratory MUST be deterministic: same seed → same result, always.

This test validates H1.6: "El RecoveryLab produce resultados deterministas."
"""

import json
import hashlib
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from dataset_builder.manifest import load_manifest
from corruptor.corruptor import Corruptor, ATTACK_MATRIX
from motors.motor_a_sequential import MotorASequential
from motors.motor_b_mft_first import MotorBMFTFirst
from motors.motor_c_orchestrator import MotorCOrchestrator
from hypothesis_registry import get_registry, Evidence, EvidenceType


def run_stability_test(
    dataset_dir: Path,
    num_runs: int = 100,
    attacks_to_test: List[str] = None,
    seed: int = 42,
) -> Dict:
    """
    Run each scenario num_runs times and verify identical results.

    For each scenario, we check:
      1. The corrupted image is byte-identical across runs
      2. Motor A recovery results are identical across runs
      3. Motor B recovery results are identical across runs
      4. Motor C recovery results are identical across runs
      5. Metrics are identical across runs

    Any non-determinism is a BUG.
    """
    # Find datasets
    datasets = _find_datasets(dataset_dir)
    if not datasets:
        print("No datasets found! Build datasets first with: python run_experiment.py build")
        return {"error": "no_datasets"}

    # Select attacks
    if attacks_to_test:
        attacks = [a for a in ATTACK_MATRIX if a["id"] in attacks_to_test]
    else:
        # Test a representative subset: baseline + 3 attacks
        attacks = [
            {"id": "baseline", "name": "Sin corrupción", "corruptions": []},
            next(a for a in ATTACK_MATRIX if a["id"] == "A01"),
            next(a for a in ATTACK_MATRIX if a["id"] == "A09"),
            next(a for a in ATTACK_MATRIX if a["id"] == "A15"),
        ]

    print(f"\n{'='*70}")
    print(f"RECOVERYLAB — Stability Test (Objeción 5)")
    print(f"{'='*70}")
    print(f"  Datasets: {len(datasets)}")
    print(f"  Attacks: {len(attacks)}")
    print(f"  Runs per scenario: {num_runs}")
    print(f"  Total executions: {len(datasets) * len(attacks) * num_runs}")
    print(f"{'='*70}\n")

    motors = {
        "Motor A": MotorASequential(),
        "Motor B": MotorBMFTFirst(),
        "Motor C": MotorCOrchestrator(),
    }

    results = {
        "total_scenarios": 0,
        "deterministic_scenarios": 0,
        "non_deterministic_scenarios": 0,
        "failures": [],
    }

    for ds_idx, (img_path, manifest_path) in enumerate(datasets, 1):
        print(f"\nDataset {ds_idx}/{len(datasets)}: {img_path.name}")

        with open(img_path, 'rb') as f:
            image = f.read()
        manifest = load_manifest(manifest_path)

        for attack in attacks:
            attack_id = attack["id"]
            print(f"  Attack {attack_id}: ", end="", flush=True)

            # Run num_runs times
            corrupted_hashes = []
            motor_results = {name: [] for name in motors}

            for run in range(num_runs):
                # Apply corruption (same seed each time)
                corruptor = Corruptor(seed=seed)
                if attack["corruptions"]:
                    corr_result = corruptor.apply_scenario(image, manifest, attack)
                    corrupted_image = corr_result.corrupted_image
                else:
                    corrupted_image = image

                # Hash the corrupted image
                img_hash = hashlib.sha256(corrupted_image).hexdigest()
                corrupted_hashes.append(img_hash)

                # Run each motor
                for motor_name, motor in motors.items():
                    result = motor.recover(
                        corrupted_image, manifest,
                        corruption_metadata=None,
                    )

                    # Create a deterministic fingerprint of the result
                    fingerprint = _result_fingerprint(result)
                    motor_results[motor_name].append(fingerprint)

                if (run + 1) % 25 == 0:
                    print(f"{run+1}...", end="", flush=True)

            # Check determinism
            scenario_stable = True

            # Check corrupted image
            if len(set(corrupted_hashes)) != 1:
                scenario_stable = False
                results["failures"].append({
                    "dataset": img_path.name,
                    "attack": attack_id,
                    "component": "corruptor",
                    "detail": f"Corrupted image hash varies across runs: {len(set(corrupted_hashes))} unique hashes",
                })

            # Check motor results
            for motor_name, fingerprints in motor_results.items():
                if len(set(fingerprints)) != 1:
                    scenario_stable = False
                    results["failures"].append({
                        "dataset": img_path.name,
                        "attack": attack_id,
                        "component": motor_name,
                        "detail": f"Results vary across runs: {len(set(fingerprints))} unique fingerprints out of {num_runs}",
                    })

            results["total_scenarios"] += 1
            if scenario_stable:
                results["deterministic_scenarios"] += 1
                print(f" DETERMINISTIC ✓")
            else:
                results["non_deterministic_scenarios"] += 1
                print(f" NON-DETERMINISTIC ✗")

    # Summary
    print(f"\n{'='*70}")
    print(f"STABILITY TEST RESULTS")
    print(f"{'='*70}")
    print(f"  Scenarios tested: {results['total_scenarios']}")
    print(f"  Deterministic: {results['deterministic_scenarios']}")
    print(f"  Non-deterministic: {results['non_deterministic_scenarios']}")

    if results["failures"]:
        print(f"\n  FAILURES ({len(results['failures'])}):")
        for f in results["failures"]:
            print(f"    {f['dataset']}/{f['attack']}/{f['component']}: {f['detail']}")
    else:
        print(f"\n  ALL SCENARIOS ARE DETERMINISTIC ✓")

    verdict = "PASS" if results["non_deterministic_scenarios"] == 0 else "FAIL"
    print(f"\n  VERDICT: {verdict}")
    print(f"{'='*70}")

    # Update hypothesis registry
    registry = get_registry()
    now = datetime.now(timezone.utc).isoformat()
    registry.add_evidence("H1.6", Evidence(
        timestamp=now,
        type=EvidenceType.SIMULATION,
        supports=(verdict == "PASS"),
        description=f"Stability test: {results['deterministic_scenarios']}/{results['total_scenarios']} "
                    f"scenarios deterministic across {num_runs} runs",
        experiment_id="stability_test",
        strength="strong" if verdict == "PASS" else "strong",
    ))

    # Save results
    output_path = Path(__file__).parent / "output" / "results" / "stability_test.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "num_runs": num_runs,
            "seed": seed,
            "results": results,
            "verdict": verdict,
        }, f, indent=2, default=str)

    return results


def _result_fingerprint(result) -> str:
    """Create a deterministic fingerprint of a motor result."""
    # Sort recovered files by name for determinism
    files = sorted(
        [(f.name, f.sha256, f.size, f.source) for f in result.recovered_files],
        key=lambda x: x[0]
    )
    fingerprint_data = {
        "files": files,
        "read_count": result.read_count,
        "sectors_wasted": result.sectors_wasted,
        "time_to_first_file": result.time_to_first_file,
        "mft_entries_parsed": result.mft_entries_parsed,
        "directories_rebuilt": result.directories_rebuilt,
    }
    return hashlib.sha256(
        json.dumps(fingerprint_data, sort_keys=True).encode()
    ).hexdigest()


def _find_datasets(dataset_dir: Path) -> List[Tuple[Path, Path]]:
    """Find all (image, manifest) pairs."""
    datasets = []
    if not dataset_dir.exists():
        return datasets

    for img_path in sorted(dataset_dir.glob("dataset_*.img")):
        manifest_path = img_path.parent / img_path.name.replace(".img", "_manifest.json")
        if manifest_path.exists():
            datasets.append((img_path, manifest_path))

    return datasets


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RecoveryLab Stability Test")
    parser.add_argument("--dataset-dir", type=str, default="output/datasets")
    parser.add_argument("--runs", type=int, default=100, help="Number of runs per scenario")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--attacks", nargs="*", default=None,
                       help="Specific attack IDs to test (default: representative subset)")

    args = parser.parse_args()

    project_root = Path(__file__).parent
    dataset_dir = project_root / args.dataset_dir

    run_stability_test(
        dataset_dir=dataset_dir,
        num_runs=args.runs,
        attacks_to_test=args.attacks,
        seed=args.seed,
    )
