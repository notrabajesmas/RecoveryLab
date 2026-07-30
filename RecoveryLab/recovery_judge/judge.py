"""
RecoveryLab — Recovery Judge v2
=================================
The impartial judge that compares recovery results against ground truth.

v2 Architecture: Four independent components, one orchestrator.

  1. Identity Matcher (SHA-256) — Is this the same file?
  2. Functional Validator — Does the file serve its purpose?
  3. Ground Truth Comparator — What's missing?
  4. RVS Calculator — How much VALUE was recovered?

The Judge orchestrates these four components and produces a comprehensive
RecoveryMetrics with both binary (SHA-256) and functional recovery assessment.

Key insight: "Recovered" is not binary. A JPEG with 2 bad pixels is NOT
"failed". An MP4 that plays is NOT "lost". A DOCX that opens but lost an
image is NOT "worth zero".

Motor A → Result → Judge → Compare → Ground Truth → Score
Motor B → Result → Judge → Compare → Ground Truth → Score
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass

from .metrics import RecoveryMetrics, ComparisonResult
from .rvs import RecoveryValueScore
from .functional_validator import FunctionalValidator, RecoveryLevel


class RecoveryJudge:
    """
    Impartial judge that scores recovery results against ground truth.

    v2: Integrates four independent components:
      1. Identity Matcher — SHA-256 matching (name-first, then content)
      2. Functional Validator — Does the file work?
      3. Ground Truth Comparator — What's missing?
      4. RVS Calculator — How much VALUE was recovered?

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

        # Initialize the four components
        self.rvs_calculator = RecoveryValueScore()
        self.functional_validator = FunctionalValidator()

    def _build_ground_truth(self) -> Dict:
        """Build lookup structures from the manifest."""
        # File lookup by name
        files_by_name = {}
        files_by_id = {}
        files_by_sha = {}  # SHA-256 → file (for carving matching)
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
                files_by_sha[f["sha256"]] = f
            total_bytes += f.get("size", 0)

        return {
            "files_by_name": files_by_name,
            "files_by_id": files_by_id,
            "files_by_sha": files_by_sha,
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
              duplicate_files: Optional[List[str]] = None,
              recovered_data: Optional[Dict[str, bytes]] = None) -> RecoveryMetrics:
        """
        Judge a set of recovered files against ground truth.

        v2: Now includes functional recovery assessment.

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
            recovered_data: Optional dict of filename → bytes for functional validation

        Returns:
            RecoveryMetrics with all measurements (binary + functional)
        """
        gt = self.ground_truth
        metrics = RecoveryMetrics()

        # ─── Component 1: Identity Matcher (SHA-256) ─────────────────
        # Match recovered files against ground truth by name first,
        # then by SHA-256 content (critical for carving).
        recovered_names = set()
        matched_shas = set()  # Track which ground truth files were matched by SHA
        correct_checksums = 0
        corrupt_count = 0
        bytes_recovered = 0
        bytes_correct = 0
        missing_details = []

        # Track functional validation results
        functional_results = {}
        level_counts = {level.value: 0 for level in RecoveryLevel}

        for rf in recovered_files:
            name = rf.get("name", "")
            sha256 = rf.get("sha256", "")
            size = rf.get("size", 0)
            is_dir = rf.get("is_directory", False)
            data = rf.get("data", None)

            if is_dir:
                metrics.directories_rebuilt += 1
                continue

            recovered_names.add(name)

            # Check against ground truth — FIRST by name, THEN by SHA-256
            # This is critical for carving: carved files have generic names
            # but can still be matched by their content (SHA-256)
            gt_file = gt["files_by_name"].get(name)

            if gt_file is None and sha256:
                # Name didn't match — try matching by SHA-256 (content)
                gt_file = gt["files_by_sha"].get(sha256)
                if gt_file and gt_file["sha256"] in matched_shas:
                    # Already matched this ground truth file to another recovery
                    gt_file = None
                elif gt_file:
                    matched_shas.add(gt_file["sha256"])

            # ─── Component 2: Functional Validator ────────────────────
            functional_level = RecoveryLevel.FAILED
            functional_score = 0.0

            if gt_file:
                gt_sha = gt_file.get("sha256", "")

                if sha256 == gt_sha:
                    # SHA-256 matches — FULL recovery (bit-perfect)
                    correct_checksums += 1
                    bytes_correct += size
                    functional_level = RecoveryLevel.FULL
                    functional_score = 1.0
                    metrics.recovered_file_details.append({
                        "name": name,
                        "matched_ground_truth": gt_file.get("name", name),
                        "status": "correct",
                        "sha256": sha256,
                        "size": size,
                        "match_method": "name" if gt["files_by_name"].get(name) else "sha256",
                        "functional_level": functional_level.value,
                        "functional_score": functional_score,
                    })
                else:
                    # SHA-256 doesn't match — is it FUNCTIONALLY recovered?
                    corrupt_count += 1

                    # Try functional validation if we have the data
                    if data is not None:
                        # Get original data if available
                        orig_data = recovered_data.get(gt_file.get("name", name)) if recovered_data else None
                        val_result = self.functional_validator.validate(
                            data, name, orig_data)
                        functional_level = val_result["level"]
                        functional_score = val_result["functional_score"]
                        functional_results[name] = val_result
                    else:
                        # No data available — assume degraded based on corruption
                        functional_level = RecoveryLevel.DEGRADED
                        functional_score = 0.2

                    metrics.corrupt_file_details.append({
                        "name": name,
                        "matched_ground_truth": gt_file.get("name", name),
                        "status": "corrupt",
                        "expected_sha256": gt_file.get("sha256", ""),
                        "actual_sha256": sha256,
                        "size": size,
                        "functional_level": functional_level.value,
                        "functional_score": functional_score,
                    })
            else:
                # False positive — not in ground truth
                metrics.false_positives += 1

            # Track level distribution
            level_counts[functional_level.value] += 1

            bytes_recovered += size

        # ─── Component 3: Ground Truth Comparator ────────────────────
        # Find missing files
        matched_gt_names = set()
        for detail in metrics.recovered_file_details:
            matched_gt_names.add(detail.get("matched_ground_truth", detail["name"]))
        for detail in metrics.corrupt_file_details:
            matched_gt_names.add(detail.get("matched_ground_truth", detail["name"]))

        for name, gt_file in gt["files_by_name"].items():
            if name not in matched_gt_names and gt_file.get("sha256") not in matched_shas:
                missing_details.append({
                    "name": name,
                    "status": "missing",
                    "sha256": gt_file.get("sha256", ""),
                    "size": gt_file.get("size", 0),
                })
                level_counts[RecoveryLevel.FAILED.value] += 1

        # ─── Compute core metrics ──────────────────────────────────────
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

        # ─── Component 4: RVS Calculator ──────────────────────────────
        # Not all files have the same value. A thesis is worth more than
        # 10 thumbnails. RVS captures this from the user's perspective.
        recovered_names_rvs = set()
        for detail in metrics.recovered_file_details:
            recovered_names_rvs.add(detail.get("matched_ground_truth", detail["name"]))

        gt_names = set(gt["files_by_name"].keys())
        gt_sizes = {name: f.get("size", 0) for name, f in gt["files_by_name"].items()}

        rvs_result = self.rvs_calculator.compute_score(
            recovered_names=recovered_names_rvs,
            ground_truth_names=gt_names,
            file_sizes=gt_sizes,
        )
        metrics.rvs = rvs_result["rvs"]
        metrics.rvs_breakdown = rvs_result

        # ─── Compute Functional Recovery Metrics (v2) ─────────────────
        total_gt_files = len(gt_names)
        if total_gt_files > 0:
            # Full recovery rate: SHA-256 matches
            metrics.full_recovery_rate = correct_checksums / total_gt_files

            # Functional recovery rate: files with functional+ recovery
            functional_plus = sum(
                1 for level in [RecoveryLevel.FULL, RecoveryLevel.FUNCTIONAL]
                if level.value in level_counts
                for _ in range(level_counts.get(level.value, 0))
            )
            # Also count PARTIAL files as "functionally recovered" (score >= 0.5)
            partial_count = level_counts.get(RecoveryLevel.PARTIAL.value, 0)
            metrics.functional_recovery_rate = (functional_plus + partial_count) / total_gt_files

            # Weighted Functional Score: RVS × functional_score
            # This is the MOST IMPORTANT single metric: it combines
            # "how much VALUE was recovered" with "how FUNCTIONAL is it"
            total_weighted = 0.0
            total_value = 0.0

            for detail in metrics.recovered_file_details:
                gt_name = detail.get("matched_ground_truth", detail["name"])
                file_value = self.rvs_calculator.file_value(gt_name)
                fs = detail.get("functional_score", 1.0)
                total_weighted += file_value * fs
                total_value += file_value

            for detail in metrics.corrupt_file_details:
                gt_name = detail.get("matched_ground_truth", detail["name"])
                file_value = self.rvs_calculator.file_value(gt_name)
                fs = detail.get("functional_score", 0.2)
                total_weighted += file_value * fs
                total_value += file_value

            # Missing files contribute 0 to weighted score
            for detail in missing_details:
                file_value = self.rvs_calculator.file_value(detail["name"])
                total_value += file_value

            metrics.weighted_functional_score = (
                total_weighted / total_value if total_value > 0 else 0.0
            )

        metrics.functional_details = functional_results
        metrics.level_distribution = level_counts

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
