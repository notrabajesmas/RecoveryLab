"""
RecoveryLab — Experiment Runner v2 (3-Strategy)
=================================================
The BLOCKER-001 resolution: now runs 3 genuinely different strategies.

  Dataset → Carving  → Judge → Results
         → MFT-First → Judge → Results
         → Motor C    → Judge → Results
         → Comparison → Report

The three strategies are:
  1. Carving (signature-only, NO MFT)
  2. MFT-First (metadata-only, NO carving)
  3. Motor C (adaptive orchestrator)

This is the scientifically valid comparison that BLOCKER-001 demands.
"""

import json
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field

from dataset_builder.manifest import load_manifest, save_manifest
from corruptor.corruptor import Corruptor, ATTACK_MATRIX
from recovery_judge.judge import RecoveryJudge
from recovery_judge.metrics import RecoveryMetrics, ComparisonResult
from motors.motor_carving import MotorCarving
from motors.motor_b_mft_first import MotorBMFTFirst
from motors.motor_c_orchestrator import MotorCOrchestrator
from strategy_profiles import (
    STRATEGY_CARVING, STRATEGY_MFT_ONLY, STRATEGY_MOTOR_C,
    validate_comparison,
)


class ExperimentRunnerV2:
    """
    Three-strategy experiment runner.

    Runs Carving, MFT-First, and Motor C on each dataset/attack,
    producing pairwise comparisons between all three.

    This is the BLOCKER-001 resolution: we now compare genuinely
    different strategies, not just different read orders of the same data.
    """

    def __init__(self, dataset_dir: Path, output_dir: Path, seed: int = 42):
        self.dataset_dir = dataset_dir
        self.output_dir = output_dir
        self.seed = seed

        self.motor_carving = MotorCarving()
        self.motor_mft = MotorBMFTFirst()
        self.motor_c = MotorCOrchestrator()
        self.corruptor = Corruptor(seed=seed)
        self.judge = None

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run_all(self, attacks: Optional[List[Dict]] = None,
                read_budget: int = 0) -> Dict:
        """Run the complete experiment across all datasets and attacks."""
        if attacks is None:
            attacks = ATTACK_MATRIX

        datasets = self._find_datasets()
        print(f"\n{'='*70}")
        print(f"RECOVERYLAB v2 — Three-Strategy Experiment Runner")
        print(f"{'='*70}")
        print(f"  Datasets: {len(datasets)}")
        print(f"  Attacks: {len(attacks)}")
        print(f"  Total scenarios: {len(datasets) * len(attacks)}")
        print(f"  Strategies: Carving, MFT-First, Motor C")
        print(f"  Read budget: {'unlimited' if read_budget == 0 else f'{read_budget} sectors'}")
        print(f"{'='*70}\n")

        # Validate that our comparisons are scientifically valid
        v1 = validate_comparison(STRATEGY_CARVING, STRATEGY_MFT_ONLY)
        v2 = validate_comparison(STRATEGY_CARVING, STRATEGY_MOTOR_C)
        v3 = validate_comparison(STRATEGY_MFT_ONLY, STRATEGY_MOTOR_C)
        print(f"  Carving vs MFT-First: {'VALID' if v1['valid'] else 'NOT VALID'}")
        print(f"  Carving vs Motor C:   {'VALID' if v2['valid'] else 'NOT VALID'}")
        print(f"  MFT-First vs Motor C: {'VALID' if v3['valid'] else 'NOT VALID'}")
        print()

        all_results = []
        all_comparisons = []

        for ds_idx, (img_path, manifest_path) in enumerate(datasets, 1):
            print(f"\n{'─'*60}")
            print(f"Dataset {ds_idx}/{len(datasets)}: {img_path.name}")
            print(f"{'─'*60}")

            with open(img_path, 'rb') as f:
                image = f.read()
            manifest = load_manifest(manifest_path)
            self.judge = RecoveryJudge(manifest)

            # Run baseline (no corruption)
            baseline = self._run_single(
                image, manifest, "baseline", {},
                read_budget=read_budget
            )
            all_results.append(baseline)
            all_comparisons.extend(baseline["_comparisons"])

            # Run each attack
            for attack in attacks:
                attack_id = attack["id"]
                attack_name = attack["name"]
                print(f"\n  Attack {attack_id}: {attack_name}")

                result = self.corruptor.apply_scenario(image, manifest, attack)

                attack_result = self._run_single(
                    result.corrupted_image, manifest,
                    attack_id, result.manifest_corruption,
                    read_budget=read_budget,
                    corruption_metadata=self._extract_corruption_metadata(
                        result.manifest_corruption, manifest
                    ),
                )
                all_results.append(attack_result)
                all_comparisons.extend(attack_result["_comparisons"])

        # Aggregate results
        aggregated = self._aggregate_results(all_comparisons)

        # Save results
        self._save_results(all_results, aggregated)

        # Print summary
        self._print_summary(aggregated)

        return {
            "individual_results": all_results,
            "comparisons": all_comparisons,
            "aggregated": aggregated,
        }

    def _find_datasets(self) -> List[Tuple[Path, Path]]:
        """Find all (image, manifest) pairs in the dataset directory."""
        datasets = []
        if not self.dataset_dir.exists():
            print(f"  ⚠ Dataset directory not found: {self.dataset_dir}")
            return datasets

        for img_path in sorted(self.dataset_dir.glob("dataset_*.img")):
            manifest_path = img_path.parent / img_path.name.replace(".img", "_manifest.json")
            if manifest_path.exists():
                datasets.append((img_path, manifest_path))
            else:
                print(f"  ⚠ No manifest for {img_path.name}")

        return datasets

    def _run_motor(self, motor, image, manifest, read_budget,
                    corruption_metadata) -> Tuple[RecoveryMetrics, float]:
        """Run a single motor and return (metrics, elapsed_time)."""
        start = time.time()
        result = motor.recover(
            image, manifest, read_budget=read_budget,
            corruption_metadata=corruption_metadata,
        )
        elapsed = time.time() - start

        metrics = self.judge.judge(
            recovered_files=[{
                "name": f.name,
                "sha256": f.sha256,
                "size": f.size,
                "is_directory": f.is_directory,
            } for f in result.recovered_files],
            read_count=result.read_count,
            sectors_wasted=result.sectors_wasted,
            time_to_first_file=result.time_to_first_file,
            mft_entries_parsed=result.mft_entries_parsed,
            total_time_seconds=elapsed,
            read_budget=read_budget,
            directories_rebuilt=result.directories_rebuilt,
        )

        return metrics, elapsed

    def _run_single(self, image: bytes, manifest: Dict,
                    scenario_id: str, corruption_info: Dict,
                    read_budget: int = 0,
                    corruption_metadata: Optional[Dict] = None) -> Dict:
        """Run all three motors on a single image and compare."""

        # ─── Motor 1: Carving ──────────────────────────────────────────
        metrics_carving, time_carving = self._run_motor(
            self.motor_carving, image, manifest, read_budget, corruption_metadata
        )

        # ─── Motor 2: MFT-First ────────────────────────────────────────
        metrics_mft, time_mft = self._run_motor(
            self.motor_mft, image, manifest, read_budget, corruption_metadata
        )

        # ─── Motor 3: Motor C ──────────────────────────────────────────
        metrics_c, time_c = self._run_motor(
            self.motor_c, image, manifest, read_budget, corruption_metadata
        )

        # ─── Pairwise comparisons ──────────────────────────────────────
        comp_carving_vs_mft = self.judge.compare(
            metrics_carving, metrics_mft,
            name_a="Carving", name_b="MFT-First",
            dataset=manifest.get("serial", "unknown"),
            attack_id=scenario_id,
        )

        comp_carving_vs_c = self.judge.compare(
            metrics_carving, metrics_c,
            name_a="Carving", name_b="Motor C",
            dataset=manifest.get("serial", "unknown"),
            attack_id=scenario_id,
        )

        comp_mft_vs_c = self.judge.compare(
            metrics_mft, metrics_c,
            name_a="MFT-First", name_b="Motor C",
            dataset=manifest.get("serial", "unknown"),
            attack_id=scenario_id,
        )

        # ─── Print results ─────────────────────────────────────────────
        print(f"    Carving:  {metrics_carving.summary()}")
        print(f"    MFT-First: {metrics_mft.summary()}")
        print(f"    Motor C:  {metrics_c.summary()}")
        print(f"    Carving vs MFT: Δ Recovery {comp_carving_vs_mft.delta_recovery_rate():+.2%} | "
              f"Δ Reads {comp_carving_vs_mft.delta_reads():+d} | "
              f"H1: {comp_carving_vs_mft.h1_strength()}")

        return {
            "scenario_id": scenario_id,
            "corruption": corruption_info,
            "carving": metrics_carving.to_dict(),
            "mft_first": metrics_mft.to_dict(),
            "motor_c": metrics_c.to_dict(),
            "comparisons": {
                "carving_vs_mft": comp_carving_vs_mft.to_dict(),
                "carving_vs_c": comp_carving_vs_c.to_dict(),
                "mft_vs_c": comp_mft_vs_c.to_dict(),
            },
            "_comparisons": [comp_carving_vs_mft, comp_carving_vs_c, comp_mft_vs_c],
        }

    def _extract_corruption_metadata(self, corruption_info: Dict,
                                      manifest: Dict) -> Dict:
        """Extract simulation metadata from corruption info."""
        metadata = {}

        if isinstance(corruption_info, dict):
            if "slow_sector_list" in corruption_info:
                metadata["slow_sector_list"] = corruption_info["slow_sector_list"]
            if "timeout_sector_list" in corruption_info:
                metadata["timeout_sector_list"] = corruption_info["timeout_sector_list"]
            if "corruptions_applied" in corruption_info:
                for corr in corruption_info["corruptions_applied"]:
                    if "slow_sector_list" in corr:
                        metadata["slow_sector_list"] = corr["slow_sector_list"]
                    if "timeout_sector_list" in corr:
                        metadata["timeout_sector_list"] = corr["timeout_sector_list"]

        return metadata

    def _aggregate_results(self, comparisons: List[ComparisonResult]) -> Dict:
        """Aggregate all comparison results."""
        if not comparisons:
            return {}

        total = len(comparisons)

        # Group by comparison type
        carving_vs_mft = [c for c in comparisons if "Carving" in c.motor_a_name and "MFT" in c.motor_b_name]
        carving_vs_c = [c for c in comparisons if "Carving" in c.motor_a_name and "Motor C" in c.motor_b_name]
        mft_vs_c = [c for c in comparisons if "MFT" in c.motor_a_name and "Motor C" in c.motor_b_name]

        def summarize_group(group, name_a, name_b):
            if not group:
                return {"total": 0}

            h1_supported = sum(1 for c in group if c.h1_supported())
            strength_dist = {}
            for c in group:
                s = c.h1_strength()
                strength_dist[s] = strength_dist.get(s, 0) + 1

            avg_delta_recovery = sum(c.delta_recovery_rate() for c in group) / len(group)
            avg_delta_reads = sum(c.delta_reads() for c in group) / len(group)

            return {
                "total": len(group),
                "h1_supported_count": h1_supported,
                "h1_supported_pct": h1_supported / len(group) if group else 0,
                "strength_distribution": strength_dist,
                "avg_delta_recovery_rate": round(avg_delta_recovery, 4),
                "avg_delta_reads_saved": round(avg_delta_reads, 1),
            }

        return {
            "total_comparisons": total,
            "carving_vs_mft": summarize_group(carving_vs_mft, "Carving", "MFT-First"),
            "carving_vs_c": summarize_group(carving_vs_c, "Carving", "Motor C"),
            "mft_vs_c": summarize_group(mft_vs_c, "MFT-First", "Motor C"),
        }

    def _save_results(self, all_results: List[Dict], aggregated: Dict):
        """Save experiment results to files."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        results_path = self.output_dir / f"experiment_v2_{timestamp}_results.json"
        with open(results_path, 'w') as f:
            json.dump({
                "timestamp": timestamp,
                "seed": self.seed,
                "version": "v2_three_strategy",
                "results": all_results,
                "aggregated": aggregated,
            }, f, indent=2, default=str)

        print(f"\n  Results saved: {results_path}")

        summary_path = self.output_dir / f"experiment_v2_{timestamp}_summary.json"
        with open(summary_path, 'w') as f:
            json.dump({
                "timestamp": timestamp,
                "seed": self.seed,
                "version": "v2_three_strategy",
                "aggregated": aggregated,
            }, f, indent=2, default=str)

        print(f"  Summary saved: {summary_path}")

    def _print_summary(self, aggregated: Dict):
        """Print the final experiment summary."""
        print(f"\n{'='*70}")
        print(f"EXPERIMENT SUMMARY (v2 — Three-Strategy)")
        print(f"{'='*70}")

        for pair_name in ["carving_vs_mft", "carving_vs_c", "mft_vs_c"]:
            pair_data = aggregated.get(pair_name, {})
            if pair_data.get("total", 0) == 0:
                continue

            print(f"\n  {pair_name.upper()}:")
            print(f"    Total scenarios: {pair_data.get('total', 0)}")
            print(f"    H1 supported: {pair_data.get('h1_supported_count', 0)}/{pair_data.get('total', 0)} "
                  f"({pair_data.get('h1_supported_pct', 0):.1%})")
            print(f"    Avg Δ recovery rate: {pair_data.get('avg_delta_recovery_rate', 0):+.2%}")
            print(f"    Avg Δ reads saved: {pair_data.get('avg_delta_reads_saved', 0):+.0f}")
            print(f"    Strength: {pair_data.get('strength_distribution', {})}")

        print(f"\n{'='*70}")


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="RecoveryLab v2 Experiment Runner")
    parser.add_argument("--dataset-dir", type=str, default="output/datasets",
                       help="Directory containing dataset images")
    parser.add_argument("--output-dir", type=str, default="output/results",
                       help="Directory for experiment results")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--read-budget", type=int, default=0,
                       help="Maximum sector reads (0=unlimited)")
    parser.add_argument("--attack", type=str, default=None,
                       help="Run only specific attack (e.g. A01)")

    args = parser.parse_args()

    project_root = Path(__file__).parent
    dataset_dir = project_root / args.dataset_dir
    output_dir = project_root / args.output_dir

    runner = ExperimentRunnerV2(
        dataset_dir=dataset_dir,
        output_dir=output_dir,
        seed=args.seed,
    )

    attacks = ATTACK_MATRIX
    if args.attack:
        attacks = [a for a in ATTACK_MATRIX if a["id"] == args.attack]

    runner.run_all(attacks=attacks, read_budget=args.read_budget)
