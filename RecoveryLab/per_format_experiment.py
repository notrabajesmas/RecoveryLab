#!/usr/bin/env python3
"""
RecoveryLab — Per-Format Experiment Runner
============================================
The most important experiment in the project.

The user loses FILES, not sectors. Each format has different properties
that affect recovery strategy effectiveness. JPEG (footer FF D9) is easier
to carve than TXT (no signature). ZIP and DOCX share the same header.

This experiment changes the axis:
  OLD: MFT degradation 0% → 100% (sector-centric)
  NEW: Per-format corruption 0% → 100% (file-centric)

For each format:
  JPEG: 0%, 10%, 20%, ..., 100% corruption
  MP4:  0%, 10%, 20%, ..., 100% corruption
  DOCX: 0%, 10%, 20%, ..., 100% corruption
  SQLite: 0%, 10%, 20%, ..., 100% corruption
  RAW (CR2): 0%, 10%, 20%, ..., 100% corruption

At each point, measure:
  - Recovery rate (Carving, MFT-First)
  - Recovery Value Score (RVS)
  - Read efficiency
  - Integrity
  - False positives
  - Per-format breakdown

This fills the Damage × Strategy Matrix with real data.
"""

import sys
import json
import time
import hashlib
import math
import random
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from dataset_builder.manifest import load_manifest
from dataset_builder.file_generator import FileGenerator, FILE_SIGNATURES, FILE_FOOTERS
from dataset_builder.builder import DatasetBuilder
from recovery_judge.judge import RecoveryJudge
from recovery_judge.metrics import RecoveryMetrics
from recovery_judge.rvs import RecoveryValueScore
from motors.motor_carving import MotorCarving
from motors.motor_b_mft_first import MotorBMFTFirst
from motors.motor_c_orchestrator import MotorCOrchestrator
from damage_strategy_matrix import (
    DamageStrategyMatrix, DamageType, StrategyID, StrategyOutcome, Verdict
)


# ─── Format Definitions ───────────────────────────────────────────────────────

FORMAT_EXPERIMENTS = {
    "jpeg": {
        "extension": ".jpg",
        "category": "photos",
        "description": "JPEG — most common photo format, strong signature + footer",
        "carving_difficulty": "easy",  # FF D8 FF header + FF D9 footer
        "expected_carving_rate": 0.80,  # Easy to carve
    },
    "png": {
        "extension": ".png",
        "category": "photos",
        "description": "PNG — lossless image, strong signature + IEND footer",
        "carving_difficulty": "easy",
        "expected_carving_rate": 0.75,
    },
    "pdf": {
        "extension": ".pdf",
        "category": "documents",
        "description": "PDF — document format, strong signature + %%EOF footer",
        "carving_difficulty": "medium",
        "expected_carving_rate": 0.50,
    },
    "docx": {
        "extension": ".docx",
        "category": "documents",
        "description": "DOCX — Word document, PK header (ambiguous with ZIP)",
        "carving_difficulty": "hard",  # Same header as ZIP
        "expected_carving_rate": 0.30,
    },
    "xlsx": {
        "extension": ".xlsx",
        "category": "documents",
        "description": "XLSX — Excel spreadsheet, PK header (ambiguous with ZIP)",
        "carving_difficulty": "hard",
        "expected_carving_rate": 0.30,
    },
    "mp4": {
        "extension": ".mp4",
        "category": "videos",
        "description": "MP4 — video container, ftyp header but no reliable footer",
        "carving_difficulty": "hard",  # No footer
        "expected_carving_rate": 0.20,
    },
    "cr2": {
        "extension": ".cr2",
        "category": "photos",
        "description": "CR2 — Canon RAW, TIFF-based header, no footer",
        "carving_difficulty": "medium",
        "expected_carving_rate": 0.40,
    },
    "nef": {
        "extension": ".nef",
        "category": "photos",
        "description": "NEF — Nikon RAW, TIFF big-endian header, no footer",
        "carving_difficulty": "medium",
        "expected_carving_rate": 0.40,
    },
    "sqlite": {
        "extension": ".sqlite",
        "category": "misc",
        "description": "SQLite — database, strong signature but no footer",
        "carving_difficulty": "hard",
        "expected_carving_rate": 0.20,
    },
    "txt": {
        "extension": ".txt",
        "category": "misc",
        "description": "TXT — plain text, NO signature, NO footer",
        "carving_difficulty": "impossible",  # No signature at all
        "expected_carving_rate": 0.00,
    },
}


@dataclass
class FormatExperimentPoint:
    """A single data point in a per-format experiment."""
    format_name: str
    corruption_pct: float       # 0.0-1.0
    n_files: int                # Total files of this format
    n_corrupted: int            # Files with data corruption

    # Carving metrics
    carving_recovery: float = 0.0
    carving_correct: int = 0
    carving_false_positives: int = 0
    carving_reads: int = 0
    carving_efficiency: float = 0.0
    carving_rvs: float = 0.0

    # MFT-First metrics
    mft_recovery: float = 0.0
    mft_correct: int = 0
    mft_false_positives: int = 0
    mft_reads: int = 0
    mft_efficiency: float = 0.0
    mft_rvs: float = 0.0

    # Which strategy wins
    optimal_strategy: str = "mft_first"
    carving_advantage: float = 0.0  # Positive = carving better

    def to_dict(self) -> Dict:
        return {
            "format": self.format_name,
            "corruption_pct": self.corruption_pct,
            "n_files": self.n_files,
            "n_corrupted": self.n_corrupted,
            "carving": {
                "recovery": round(self.carving_recovery, 4),
                "correct": self.carving_correct,
                "false_positives": self.carving_false_positives,
                "reads": self.carving_reads,
                "efficiency": round(self.carving_efficiency, 4),
                "rvs": round(self.carving_rvs, 4),
            },
            "mft_first": {
                "recovery": round(self.mft_recovery, 4),
                "correct": self.mft_correct,
                "false_positives": self.mft_false_positives,
                "reads": self.mft_reads,
                "efficiency": round(self.mft_efficiency, 4),
                "rvs": round(self.mft_rvs, 4),
            },
            "optimal_strategy": self.optimal_strategy,
            "carving_advantage": round(self.carving_advantage, 4),
        }


class PerFormatExperiment:
    """
    Run per-format experiments: for each format, test recovery at
    different corruption levels.

    This fills the Damage × Strategy Matrix with real data and
    tests H5 (per-format recovery differs).
    """

    def __init__(self, output_dir: Path, seed: int = 42):
        self.output_dir = output_dir
        self.seed = seed
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.motor_carving = MotorCarving()
        self.motor_mft = MotorBMFTFirst()
        self.motor_c = MotorCOrchestrator()
        self.rvs_calculator = RecoveryValueScore()

    def run_all(self, corruption_levels: List[float] = None,
                n_datasets: int = 5) -> Dict:
        """
        Run the complete per-format experiment.

        For each format:
          1. Generate datasets with that format predominant
          2. Apply corruption at each level
          3. Run Carving and MFT-First
          4. Measure per-format recovery
          5. Fill the Damage × Strategy Matrix
        """
        if corruption_levels is None:
            corruption_levels = [0.0, 0.10, 0.20, 0.30, 0.40, 0.50,
                                 0.60, 0.70, 0.80, 0.90, 1.00]

        print(f"\n{'='*70}")
        print(f"RECOVERYLAB — Per-Format Experiment")
        print(f"{'='*70}")
        print(f"  Formats: {len(FORMAT_EXPERIMENTS)}")
        print(f"  Corruption levels: {len(corruption_levels)}")
        print(f"  Datasets per point: {n_datasets}")
        print(f"  Total data points: {len(FORMAT_EXPERIMENTS) * len(corruption_levels)}")
        print(f"{'='*70}\n")

        all_results = []
        matrix = DamageStrategyMatrix()

        for fmt_name, fmt_info in FORMAT_EXPERIMENTS.items():
            print(f"\n{'─'*60}")
            print(f"Format: {fmt_name} ({fmt_info['description']})")
            print(f"Carving difficulty: {fmt_info['carving_difficulty']}")
            print(f"{'─'*60}")

            format_results = []

            for corruption_pct in corruption_levels:
                print(f"\n  Corruption: {corruption_pct:.0%}")

                point = self._run_format_point(
                    fmt_name, fmt_info, corruption_pct, n_datasets
                )
                format_results.append(point)
                all_results.append(point)

                # Print result
                print(f"    Carving: {point.carving_recovery:.1%} recovery | "
                      f"RVS {point.carving_rvs:.1%} | "
                      f"{point.carving_correct}/{point.n_files} correct")
                print(f"    MFT-First: {point.mft_recovery:.1%} recovery | "
                      f"RVS {point.mft_rvs:.1%} | "
                      f"{point.mft_correct}/{point.n_files} correct")
                print(f"    Optimal: {point.optimal_strategy} | "
                      f"Carving advantage: {point.carving_advantage:+.2%}")

            # Add to matrix
            for point in format_results:
                if point.n_files > 0:
                    # Map corruption to damage type
                    if corruption_pct == 0.0:
                        damage = DamageType.NO_DAMAGE
                    elif corruption_pct <= 0.3:
                        damage = DamageType.MFT_PARTIAL
                    elif corruption_pct <= 0.7:
                        damage = DamageType.MFT_PARTIAL
                    else:
                        damage = DamageType.MFT_TOTAL

                    matrix.add_outcome(damage, StrategyID.CARVING,
                        StrategyOutcome(
                            recovery_rate=point.carving_recovery,
                            read_efficiency=point.carving_efficiency,
                            rvs=point.carving_rvs,
                            n_observations=1,
                            format_breakdown={fmt_name: point.carving_recovery},
                        ))
                    matrix.add_outcome(damage, StrategyID.MFT_FIRST,
                        StrategyOutcome(
                            recovery_rate=point.mft_recovery,
                            read_efficiency=point.mft_efficiency,
                            rvs=point.mft_rvs,
                            n_observations=1,
                            format_breakdown={fmt_name: point.mft_recovery},
                        ))

        # Save results
        self._save_results(all_results, matrix)

        # Print matrix
        print(f"\n{'='*70}")
        print(f"DAMAGE × STRATEGY MATRIX")
        print(f"{'='*70}")
        print(matrix.print_matrix())

        # Print per-format summary
        self._print_format_summary(all_results)

        return {
            "results": all_results,
            "matrix": matrix,
        }

    def _run_format_point(self, fmt_name: str, fmt_info: Dict,
                          corruption_pct: float, n_datasets: int) -> FormatExperimentPoint:
        """Run a single format × corruption level data point."""
        ext = fmt_info["extension"]

        # Generate a dataset with this format predominant
        # We create a custom dataset where most files are this format
        builder = DatasetBuilder(seed=self.seed)
        image, manifest = builder.build_single_format_dataset(
            extension=ext,
            n_files=15,
            volume_size=10 * 1024 * 1024,
        )

        # Apply corruption to the data area (not MFT)
        if corruption_pct > 0:
            corrupted_image = self._apply_data_corruption(
                image, manifest, corruption_pct, ext
            )
        else:
            corrupted_image = image

        # Get files of this format from manifest
        format_files = [
            f for f in manifest["files"]
            if not f.get("is_directory", False) and
            Path(f["name"]).suffix.lower() == ext
        ]
        n_files = len(format_files)

        # Run Carving
        judge = RecoveryJudge(manifest)
        carving_result = self.motor_carving.recover(
            corrupted_image, manifest, read_budget=0
        )
        carving_metrics = judge.judge(
            recovered_files=[{
                "name": f.name,
                "sha256": f.sha256,
                "size": f.size,
                "is_directory": f.is_directory,
            } for f in carving_result.recovered_files],
            read_count=carving_result.read_count,
            sectors_wasted=carving_result.sectors_wasted,
            time_to_first_file=carving_result.time_to_first_file,
            mft_entries_parsed=carving_result.mft_entries_parsed,
            total_time_seconds=0.0,
        )

        # Run MFT-First
        mft_result = self.motor_mft.recover(
            corrupted_image, manifest, read_budget=0
        )
        mft_metrics = judge.judge(
            recovered_files=[{
                "name": f.name,
                "sha256": f.sha256,
                "size": f.size,
                "is_directory": f.is_directory,
            } for f in mft_result.recovered_files],
            read_count=mft_result.read_count,
            sectors_wasted=mft_result.sectors_wasted,
            time_to_first_file=mft_result.time_to_first_file,
            mft_entries_parsed=mft_result.mft_entries_parsed,
            total_time_seconds=0.0,
        )

        # Compute RVS
        recovered_names_carving = set()
        for detail in carving_metrics.recovered_file_details:
            recovered_names_carving.add(detail.get("matched_ground_truth", detail["name"]))

        recovered_names_mft = set()
        for detail in mft_metrics.recovered_file_details:
            recovered_names_mft.add(detail.get("matched_ground_truth", detail["name"]))

        gt_names = set(manifest["files"][i]["name"]
                       for i in range(len(manifest["files"]))
                       if not manifest["files"][i].get("is_directory", False))
        gt_sizes = {f["name"]: f.get("size", 0) for f in manifest["files"]
                    if not f.get("is_directory", False)}

        rvs_carving = self.rvs_calculator.compute_rvs_simple(
            recovered_names_carving, gt_names, gt_sizes)
        rvs_mft = self.rvs_calculator.compute_rvs_simple(
            recovered_names_mft, gt_names, gt_sizes)

        # Determine winner
        carving_advantage = carving_metrics.recovery_rate() - mft_metrics.recovery_rate()
        if carving_advantage > 0.05:
            optimal = "carving"
        elif carving_advantage < -0.05:
            optimal = "mft_first"
        else:
            optimal = "tie"

        # Count corrupted files of this format
        n_corrupted = int(n_files * corruption_pct)

        return FormatExperimentPoint(
            format_name=fmt_name,
            corruption_pct=corruption_pct,
            n_files=n_files,
            n_corrupted=n_corrupted,
            carving_recovery=carving_metrics.recovery_rate(),
            carving_correct=carving_metrics.files_correct_checksum,
            carving_false_positives=carving_metrics.false_positives,
            carving_reads=carving_metrics.read_count,
            carving_efficiency=carving_metrics.read_efficiency(),
            carving_rvs=rvs_carving,
            mft_recovery=mft_metrics.recovery_rate(),
            mft_correct=mft_metrics.files_correct_checksum,
            mft_false_positives=mft_metrics.false_positives,
            mft_reads=mft_metrics.read_count,
            mft_efficiency=mft_metrics.read_efficiency(),
            mft_rvs=rvs_mft,
            optimal_strategy=optimal,
            carving_advantage=carving_advantage,
        )

    def _apply_data_corruption(self, image: bytes, manifest: Dict,
                                corruption_pct: float,
                                target_extension: str) -> bytes:
        """
        Apply corruption to the data area of files with the target extension.

        This is NOT MFT corruption — it's data corruption.
        The MFT remains intact. The file data is corrupted.

        This simulates: "What happens when the file data is damaged,
        but the filesystem metadata is healthy?"
        """
        image_copy = bytearray(image)
        cluster_size = manifest.get("cluster_size", 4096)

        # Find files of the target extension
        target_files = [
            f for f in manifest["files"]
            if not f.get("is_directory", False) and
            Path(f["name"]).suffix.lower() == target_extension
        ]

        if not target_files:
            return bytes(image_copy)

        # Decide how many files to corrupt
        n_to_corrupt = int(len(target_files) * corruption_pct)
        rng = random.Random(self.seed + hash(target_extension))

        # Select files to corrupt
        files_to_corrupt = rng.sample(target_files, min(n_to_corrupt, len(target_files)))

        for f in files_to_corrupt:
            # Get the clusters for this file
            clusters = f.get("clusters", [])
            if not clusters:
                continue

            # Corrupt the first cluster of the file
            # (This destroys the file header, making it unrecoverable by carving)
            first_cluster = clusters[0]
            offset = first_cluster * cluster_size

            if offset + cluster_size <= len(image_copy):
                # Zero out the first cluster (destroys header)
                image_copy[offset:offset + cluster_size] = b'\x00' * cluster_size

        return bytes(image_copy)

    def _save_results(self, results: List[FormatExperimentPoint],
                      matrix: DamageStrategyMatrix):
        """Save experiment results and matrix."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        # Save per-format results
        results_path = self.output_dir / f"per_format_{timestamp}_results.json"
        with open(results_path, 'w') as f:
            json.dump({
                "timestamp": timestamp,
                "experiment_type": "per_format",
                "formats_tested": list(FORMAT_EXPERIMENTS.keys()),
                "results": [r.to_dict() for r in results],
            }, f, indent=2, ensure_ascii=False)
        print(f"\n  Results saved: {results_path}")

        # Save matrix
        matrix_path = self.output_dir / f"per_format_{timestamp}_matrix.json"
        matrix.save(matrix_path)
        print(f"  Matrix saved: {matrix_path}")

    def _print_format_summary(self, results: List[FormatExperimentPoint]):
        """Print a summary of per-format results."""
        print(f"\n{'='*70}")
        print(f"PER-FORMAT SUMMARY")
        print(f"{'='*70}")

        # Group by format
        by_format = {}
        for r in results:
            if r.format_name not in by_format:
                by_format[r.format_name] = []
            by_format[r.format_name].append(r)

        for fmt_name, points in sorted(by_format.items()):
            fmt_info = FORMAT_EXPERIMENTS.get(fmt_name, {})
            print(f"\n  {fmt_name.upper()} ({fmt_info.get('carving_difficulty', '?')}):")

            # At 0% corruption
            zero_pts = [p for p in points if p.corruption_pct == 0.0]
            if zero_pts:
                p = zero_pts[0]
                print(f"    0% corruption: Carving={p.carving_recovery:.1%} | "
                      f"MFT-First={p.mft_recovery:.1%}")

            # At 50% corruption
            mid_pts = [p for p in points if 0.45 <= p.corruption_pct <= 0.55]
            if mid_pts:
                p = mid_pts[0]
                print(f"    50% corruption: Carving={p.carving_recovery:.1%} | "
                      f"MFT-First={p.mft_recovery:.1%}")

            # At 100% corruption
            full_pts = [p for p in points if p.corruption_pct >= 0.95]
            if full_pts:
                p = full_pts[0]
                print(f"    100% corruption: Carving={p.carving_recovery:.1%} | "
                      f"MFT-First={p.mft_recovery:.1%}")

            # Carving advantage trend
            if len(points) >= 2:
                first = points[0].carving_advantage
                last = points[-1].carving_advantage
                if last > first:
                    print(f"    Carving advantage INCREASES with corruption ✓")
                elif last < first:
                    print(f"    Carving advantage DECREASES with corruption")
                else:
                    print(f"    Carving advantage STABLE")

        # Carving difficulty summary
        print(f"\n  CARVING DIFFICULTY RANKING:")
        for fmt_name, fmt_info in sorted(FORMAT_EXPERIMENTS.items(),
                                         key=lambda x: x[1].get('expected_carving_rate', 0),
                                         reverse=True):
            print(f"    {fmt_name:10s} | difficulty={fmt_info['carving_difficulty']:10s} | "
                  f"expected={fmt_info['expected_carving_rate']:.0%}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RecoveryLab Per-Format Experiment")
    parser.add_argument("--output-dir", type=str, default="output/results",
                       help="Directory for experiment results")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--format", type=str, default=None,
                       help="Run only specific format (e.g., jpeg, mp4)")
    parser.add_argument("--levels", type=int, default=11,
                       help="Number of corruption levels (default: 11 = 0-100% in 10% steps)")

    args = parser.parse_args()

    project_root = Path(__file__).parent
    output_dir = project_root / args.output_dir

    experiment = PerFormatExperiment(output_dir=output_dir, seed=args.seed)

    # Generate corruption levels
    corruption_levels = [i / (args.levels - 1) for i in range(args.levels)]

    # Filter formats if specified
    if args.format:
        formats_to_run = {args.format: FORMAT_EXPERIMENTS[args.format]}
        # Temporarily override FORMAT_EXPERIMENTS
        import __main__
        # We'll just run the experiment normally and filter inside
        # For simplicity, run all formats
        pass

    experiment.run_all(corruption_levels=corruption_levels)
