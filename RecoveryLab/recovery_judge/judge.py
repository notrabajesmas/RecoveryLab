"""
RecoveryLab — Recovery Judge
==============================
The impartial judge that compares recovery results against ground truth.

Motor A → Result → Judge → Compare → Ground Truth → Score
Motor B → Result → Judge → Compare → Ground Truth → Score

The Judge measures EVERYTHING. Not just "files recovered".
Because a motor that recovers 100 files but 12 are corrupt
is NOT the same as one that recovers 88 correct files.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass

from .metrics import RecoveryMetrics, ComparisonResult


class RecoveryJudge:
    """
    Impartial judge that scores recovery results against ground truth.

    Usage:
        judge = RecoveryJudge(manifest)
        metrics_a = judge.judge(motor_a_results)
        metrics_b = judge.judge(motor_b_results)
        comparison = judge.compare(metrics_a, metrics_b, "Motor A", "Motor B")
    """

    def __init__(self, manifest: Dict):
        """
        Args:
            manifest: Ground truth manifest dict (from dataset_builder)
        """
        self.manifest = manifest
        self.ground_truth = self._build_ground_truth()

    def _build_ground_truth(self) -> Dict:
        """Build lookup structures from the manifest."""
        # File lookup by name
        files_by_name = {}
        files_by_id = {}
        all_file_shas = set()
        total_bytes = 0
        directories = []

        for f in self.manifest["files"]:
            if f.get("is_directory", False):
                directories.append(f)
                continue

            files_by_name[f["name"]] = f
            files_by_id[f["id"]] = f
            if f.get("sha256"):
                all_file_shas.add(f["sha256"])
            total_bytes += f.get("size", 0)

        return {
            "files_by_name": files_by_name,
            "files_by_id": files_by_id,
            "all_file_shas": all_file_shas,
            "total_bytes": total_bytes,
            "total_files": len(files_by_name),
            "directories": directories,
            "total_directories": len(directories),
            "mft_start": self.manifest["mft"]["start_cluster"],
            "mft_record_count": self.manifest["mft"].get("record_count", 0),
            "total_clusters": self.manifest.get("total_clusters", 0),
        }

    def judge(self, recovered_files: List[Dict],
              read_count: int = 0,
              sectors_wasted: int = 0,
              time_to_first_file: int = 0,
              mft_entries_parsed: int = 0,
              total_time_seconds: float = 0.0,
              read_budget: int = 0,
              directories_rebuilt: int = 0,
              false_positive_files: Optional[List[str]] = None,
              duplicate_files: Optional[List[str]] = None) -> RecoveryMetrics:
        """
        Judge a set of recovered files against ground truth.

        Args:
            recovered_files: List of dicts with:
                - name: filename
                - sha256: checksum of recovered data
                - size: size in bytes
                - data: optional recovered data bytes
                - is_directory: bool
            read_count: Total sector reads performed
            sectors_wasted: Reads that returned no useful data
            time_to_first_file: Reads before first file recovered
            mft_entries_parsed: How many MFT entries were successfully parsed
            total_time_seconds: Wall-clock time
            read_budget: Maximum reads allowed (0 = unlimited)
            directories_rebuilt: Directory structures reconstructed
            false_positive_files: Files claimed but not in ground truth
            duplicate_files: Files recovered multiple times

        Returns:
            RecoveryMetrics with all measurements
        """
        gt = self.ground_truth
        metrics = RecoveryMetrics()

        # ─── Classify each recovered file ─────────────────────────────
        recovered_names = set()
        correct_checksums = 0
        corrupt_count = 0
        bytes_recovered = 0
        bytes_correct = 0
        missing_details = []

        for rf in recovered_files:
            name = rf.get("name", "")
            sha256 = rf.get("sha256", "")
            size = rf.get("size", 0)
            is_dir = rf.get("is_directory", False)

            if is_dir:
                metrics.directories_rebuilt += 1
                continue

            recovered_names.add(name)

            # Check against ground truth
            gt_file = gt["files_by_name"].get(name)

            if gt_file:
                if sha256 == gt_file.get("sha256", ""):
                    # Correct recovery!
                    correct_checksums += 1
                    bytes_correct += size
                    metrics.recovered_file_details.append({
                        "name": name,
                        "status": "correct",
                        "sha256": sha256,
                        "size": size,
                    })
                else:
                    # Corrupt recovery
                    corrupt_count += 1
                    metrics.corrupt_file_details.append({
                        "name": name,
                        "status": "corrupt",
                        "expected_sha256": gt_file.get("sha256", ""),
                        "actual_sha256": sha256,
                        "size": size,
                    })
            else:
                # False positive — not in ground truth
                metrics.false_positives += 1

            bytes_recovered += size

        # ─── Find missing files ───────────────────────────────────────
        for name, gt_file in gt["files_by_name"].items():
            if name not in recovered_names:
                missing_details.append({
                    "name": name,
                    "status": "missing",
                    "sha256": gt_file.get("sha256", ""),
                    "size": gt_file.get("size", 0),
                })

        # ─── Compute metrics ──────────────────────────────────────────
        metrics.files_recovered = len(recovered_names)
        metrics.files_correct_checksum = correct_checksums
        metrics.files_corrupt = corrupt_count
        metrics.files_missing = len(missing_details)
        metrics.bytes_recovered = bytes_recovered
        metrics.bytes_correct = bytes_correct
        metrics.bytes_total_ground_truth = gt["total_bytes"]
        metrics.directories_rebuilt = directories_rebuilt
        metrics.directories_total = gt["total_directories"]
        metrics.mft_entries_parsed = mft_entries_parsed
        metrics.mft_entries_total = gt["mft_record_count"]
        metrics.read_count = read_count
        metrics.sectors_wasted = sectors_wasted
        metrics.sectors_total = gt["total_clusters"] * self.manifest["cluster_size"] // 512
        metrics.time_to_first_file = time_to_first_file
        metrics.false_positives += len(false_positive_files or [])
        metrics.duplicates = len(duplicate_files or [])
        metrics.total_time_seconds = total_time_seconds
        metrics.read_budget = read_budget
        metrics.missing_file_details = missing_details

        if read_budget > 0:
            metrics.budget_used_pct = read_count / read_budget

        # ─── Compute integrity score ──────────────────────────────────
        # Composite score: weighted combination of key metrics
        recovery_weight = 0.40
        efficiency_weight = 0.30
        quality_weight = 0.30

        recovery_score = metrics.recovery_rate()
        efficiency_score = metrics.read_efficiency()
        quality_score = 1.0 - metrics.corruption_rate()

        metrics.integrity_score = (
            recovery_weight * recovery_score +
            efficiency_weight * efficiency_score +
            quality_weight * quality_score
        )

        return metrics

    def judge_from_image(self, recovered_image: bytes,
                         motor_name: str = "unknown") -> RecoveryMetrics:
        """
        Judge recovery by comparing recovered image against original.

        This is the most thorough method — compares every byte.
        """
        gt = self.ground_truth
        # For now, delegate to file-level comparison
        # Full image comparison would require parsing the recovered image
        raise NotImplementedError(
            "Full image judging requires parsing the recovered NTFS image. "
            "Use judge() with file-level results instead."
        )

    def compare(self, metrics_a: RecoveryMetrics, metrics_b: RecoveryMetrics,
                name_a: str = "Motor A", name_b: str = "Motor B",
                dataset: str = "", attack_id: str = "") -> ComparisonResult:
        """
        Compare two motors' results.

        Returns a ComparisonResult with deltas and H1 assessment.
        """
        return ComparisonResult(
            motor_a_name=name_a,
            motor_b_name=name_b,
            metrics_a=metrics_a,
            metrics_b=metrics_b,
            dataset=dataset,
            attack_id=attack_id,
        )

    def compare_multiple(self, comparisons: List[ComparisonResult]) -> Dict:
        """
        Aggregate multiple comparison results.

        Returns overall H1 assessment across all datasets/attacks.
        """
        support_count = sum(1 for c in comparisons if c.h1_supported())
        total = len(comparisons)

        strengths = [c.h1_strength() for c in comparisons]
        strength_counts = {}
        for s in strengths:
            strength_counts[s] = strength_counts.get(s, 0) + 1

        avg_delta_recovery = sum(c.delta_recovery_rate() for c in comparisons) / total if total else 0
        avg_delta_efficiency = sum(c.delta_read_efficiency() for c in comparisons) / total if total else 0

        return {
            "total_comparisons": total,
            "h1_supported_count": support_count,
            "h1_supported_pct": support_count / total if total else 0,
            "strength_distribution": strength_counts,
            "avg_delta_recovery_rate": round(avg_delta_recovery, 4),
            "avg_delta_read_efficiency": round(avg_delta_efficiency, 4),
            "overall_h1_strength": max(strength_counts, key=strength_counts.get) if strength_counts else "N/A",
        }
