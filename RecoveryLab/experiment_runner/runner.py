"""
RecoveryLab — Experiment Runner
=================================
The automated pipeline that runs the full experiment:

  Dataset → Motor A → Judge → Results
         → Motor B → Judge → Results
         → Comparison → Report

The day you have 400 scenarios, you won't want to run them manually.
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
from motors.motor_a_sequential import MotorASequential
from motors.motor_b_mft_first import MotorBMFTFirst


@dataclass
class ExperimentConfig:
    """Configuration for a single experiment."""
    name: str
    dataset_dir: Path
    output_dir: Path
    seed: int = 42
    attacks: List[Dict] = field(default_factory=lambda: ATTACK_MATRIX)
    read_budget: int = 0  # 0 = unlimited
    motors: List[str] = field(default_factory=lambda: ["A", "B"])
    gold_images_only: bool = False


class ExperimentRunner:
    """
    Automated experiment runner.

    Usage:
        runner = ExperimentRunner(
            dataset_dir=Path("output/datasets"),
            output_dir=Path("output/results"),
        )
        results = runner.run_all()
    """

    def __init__(self, dataset_dir: Path, output_dir: Path, seed: int = 42):
        self.dataset_dir = dataset_dir
        self.output_dir = output_dir
        self.seed = seed

        self.motor_a = MotorASequential()
        self.motor_b = MotorBMFTFirst()
        self.corruptor = Corruptor(seed=seed)
        self.judge = None  # Created per-dataset

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run_all(self, attacks: Optional[List[Dict]] = None,
                read_budget: int = 0) -> Dict:
        """
        Run the complete experiment across all datasets and attacks.

        Returns aggregated results dict.
        """
        if attacks is None:
            attacks = ATTACK_MATRIX

        # Find all datasets
        datasets = self._find_datasets()
        print(f"\n{'='*70}")
        print(f"RECOVERYLAB — Experiment Runner")
        print(f"{'='*70}")
        print(f"  Datasets: {len(datasets)}")
        print(f"  Attacks: {len(attacks)}")
        print(f"  Total scenarios: {len(datasets) * len(attacks)}")
        print(f"  Read budget: {'unlimited' if read_budget == 0 else f'{read_budget} sectors'}")
        print(f"{'='*70}\n")

        all_comparisons = []
        all_results = []

        for ds_idx, (img_path, manifest_path) in enumerate(datasets, 1):
            print(f"\n{'─'*60}")
            print(f"Dataset {ds_idx}/{len(datasets)}: {img_path.name}")
            print(f"{'─'*60}")

            # Load image and manifest
            with open(img_path, 'rb') as f:
                image = f.read()
            manifest = load_manifest(manifest_path)

            # Create judge for this dataset
            self.judge = RecoveryJudge(manifest)

            # Run baseline (no corruption)
            baseline = self._run_single(
                image, manifest, "baseline", {},
                read_budget=read_budget
            )
            all_results.append(baseline)
            all_comparisons.append(baseline["_comparison_obj"])

            # Run each attack
            for attack in attacks:
                attack_id = attack["id"]
                attack_name = attack["name"]

                print(f"\n  Attack {attack_id}: {attack_name}")

                # Apply corruption
                result = self.corruptor.apply_scenario(image, manifest, attack)

                # Run motors on corrupted image
                attack_result = self._run_single(
                    result.corrupted_image, manifest,
                    attack_id, result.manifest_corruption,
                    read_budget=read_budget,
                    corruption_metadata=self._extract_corruption_metadata(
                        result.manifest_corruption, manifest
                    ),
                )
                all_results.append(attack_result)
                all_comparisons.append(attack_result["_comparison_obj"])

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

    def _run_single(self, image: bytes, manifest: Dict,
                    scenario_id: str, corruption_info: Dict,
                    read_budget: int = 0,
                    corruption_metadata: Optional[Dict] = None) -> Dict:
        """Run both motors on a single image and compare results."""

        # ─── Motor A ──────────────────────────────────────────────────
        start = time.time()
        result_a = self.motor_a.recover(
            image, manifest, read_budget=read_budget,
            corruption_metadata=corruption_metadata,
        )
        time_a = time.time() - start

        # Judge Motor A
        metrics_a = self.judge.judge(
            recovered_files=[{
                "name": f.name,
                "sha256": f.sha256,
                "size": f.size,
                "is_directory": f.is_directory,
            } for f in result_a.recovered_files],
            read_count=result_a.read_count,
            sectors_wasted=result_a.sectors_wasted,
            time_to_first_file=result_a.time_to_first_file,
            mft_entries_parsed=result_a.mft_entries_parsed,
            total_time_seconds=time_a,
            read_budget=read_budget,
            directories_rebuilt=result_a.directories_rebuilt,
        )

        # ─── Motor B ──────────────────────────────────────────────────
        start = time.time()
        result_b = self.motor_b.recover(
            image, manifest, read_budget=read_budget,
            corruption_metadata=corruption_metadata,
        )
        time_b = time.time() - start

        # Judge Motor B
        metrics_b = self.judge.judge(
            recovered_files=[{
                "name": f.name,
                "sha256": f.sha256,
                "size": f.size,
                "is_directory": f.is_directory,
            } for f in result_b.recovered_files],
            read_count=result_b.read_count,
            sectors_wasted=result_b.sectors_wasted,
            time_to_first_file=result_b.time_to_first_file,
            mft_entries_parsed=result_b.mft_entries_parsed,
            total_time_seconds=time_b,
            read_budget=read_budget,
            directories_rebuilt=result_b.directories_rebuilt,
        )

        # ─── Compare ──────────────────────────────────────────────────
        comparison = self.judge.compare(
            metrics_a, metrics_b,
            name_a=self.motor_a.name,
            name_b=self.motor_b.name,
            dataset=manifest.get("serial", "unknown"),
            attack_id=scenario_id,
        )

        print(f"    Motor A: {metrics_a.summary()}")
        print(f"    Motor B: {metrics_b.summary()}")
        print(f"    Δ Recovery: {comparison.delta_recovery_rate():+.2%} | "
              f"Δ Reads: {comparison.delta_reads():+d} | "
              f"H1: {comparison.h1_strength()}")

        return {
            "scenario_id": scenario_id,
            "corruption": corruption_info,
            "motor_a": metrics_a.to_dict(),
            "motor_b": metrics_b.to_dict(),
            "comparison": comparison.to_dict(),
            "_comparison_obj": comparison,  # Keep object for aggregation
        }

    def _extract_corruption_metadata(self, corruption_info: Dict,
                                      manifest: Dict) -> Dict:
        """Extract simulation metadata from corruption info."""
        metadata = {}

        if isinstance(corruption_info, dict):
            # Check for slow sectors
            if "slow_sector_list" in corruption_info:
                metadata["slow_sector_list"] = corruption_info["slow_sector_list"]
            # Check for timeout pattern
            if "timeout_sector_list" in corruption_info:
                metadata["timeout_sector_list"] = corruption_info["timeout_sector_list"]

            # Check in nested corruptions
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
        h1_supported = sum(1 for c in comparisons if c.h1_supported())

        strength_dist = {}
        for c in comparisons:
            s = c.h1_strength()
            strength_dist[s] = strength_dist.get(s, 0) + 1

        avg_delta_recovery = sum(c.delta_recovery_rate() for c in comparisons) / total
        avg_delta_reads = sum(c.delta_reads() for c in comparisons) / total

        return {
            "total_scenarios": total,
            "h1_supported_count": h1_supported,
            "h1_supported_pct": h1_supported / total,
            "strength_distribution": strength_dist,
            "avg_delta_recovery_rate": round(avg_delta_recovery, 4),
            "avg_delta_reads_saved": round(avg_delta_reads, 1),
            "overall_h1_verdict": self._compute_verdict(avg_delta_recovery, h1_supported / total),
        }

    def _compute_verdict(self, avg_delta: float, support_pct: float) -> str:
        """Compute the overall H1 verdict based on thresholds."""
        from config import THRESHOLD_BUILD, THRESHOLD_HYBRID, THRESHOLD_INVEST

        if avg_delta > THRESHOLD_BUILD and support_pct > 0.5:
            return "BUILD_MOTOR — H1 strongly supported (>10% improvement)"
        elif avg_delta > THRESHOLD_HYBRID and support_pct > 0.3:
            return "HYBRID — H1 moderately supported (3-10%)"
        elif avg_delta > THRESHOLD_INVEST:
            return "INVESTIGATE — H1 weakly supported (1-3%)"
        elif avg_delta > 0:
            return "MARGINAL — H1 barely supported (<1%)"
        elif avg_delta > -0.01:
            return "NEUTRAL — No significant difference"
        else:
            return "REFUTED — H1 not supported (Motor B is worse)"

    def _save_results(self, all_results: List[Dict], aggregated: Dict):
        """Save experiment results to files."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        # Save individual results
        results_path = self.output_dir / f"experiment_{timestamp}_results.json"
        with open(results_path, 'w') as f:
            json.dump({
                "timestamp": timestamp,
                "seed": self.seed,
                "results": all_results,
                "aggregated": aggregated,
            }, f, indent=2, default=str)

        print(f"\n  Results saved: {results_path}")

        # Save summary
        summary_path = self.output_dir / f"experiment_{timestamp}_summary.json"
        with open(summary_path, 'w') as f:
            json.dump({
                "timestamp": timestamp,
                "seed": self.seed,
                "aggregated": aggregated,
            }, f, indent=2, default=str)

        print(f"  Summary saved: {summary_path}")

    def _print_summary(self, aggregated: Dict):
        """Print the final experiment summary."""
        print(f"\n{'='*70}")
        print(f"EXPERIMENT SUMMARY")
        print(f"{'='*70}")
        print(f"  Total scenarios: {aggregated.get('total_scenarios', 0)}")
        print(f"  H1 supported: {aggregated.get('h1_supported_count', 0)}/{aggregated.get('total_scenarios', 0)} "
              f"({aggregated.get('h1_supported_pct', 0):.1%})")
        print(f"  Avg Δ recovery rate: {aggregated.get('avg_delta_recovery_rate', 0):+.2%}")
        print(f"  Avg Δ reads saved: {aggregated.get('avg_delta_reads_saved', 0):+.0f}")
        print(f"  Strength distribution: {aggregated.get('strength_distribution', {})}")
        print(f"\n  VERDICT: {aggregated.get('overall_h1_verdict', 'N/A')}")
        print(f"{'='*70}")


# ─── CLI Entry Point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="RecoveryLab Experiment Runner")
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

    # Resolve paths relative to project root
    project_root = Path(__file__).parent.parent
    dataset_dir = project_root / args.dataset_dir
    output_dir = project_root / args.output_dir

    runner = ExperimentRunner(
        dataset_dir=dataset_dir,
        output_dir=output_dir,
        seed=args.seed,
    )

    attacks = ATTACK_MATRIX
    if args.attack:
        attacks = [a for a in ATTACK_MATRIX if a["id"] == args.attack]

    runner.run_all(attacks=attacks, read_budget=args.read_budget)
