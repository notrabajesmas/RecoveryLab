"""
RecoveryLab — Functional Quality Score (FQS)
===============================================
The key insight from the user's review:

  WFS = Valor × Funcionalidad

Should be SPLIT into:

  RVS = Valor recuperado (what you recovered, weighted by importance)
  FQS = Calidad de recuperación (how well each file was recovered)

Then: Overall Utility = RVS × FQS

This separation tells you WHY a motor won:
  - Did it win because it recovered important files? (RVS)
  - Did it win because it recovered files with better quality? (FQS)

A motor that recovers the thesis at 90% quality (FQS=0.9) has:
  RVS = 1.0 (the thesis is the most valuable file)
  FQS = 0.9 (90% functional quality)
  Overall Utility = 0.9

A motor that recovers 200 thumbnails at 100% quality (FQS=1.0) has:
  RVS = 0.2 (thumbnails are low-value)
  FQS = 1.0 (perfect quality)
  Overall Utility = 0.2

The first motor wins because RVS dominates. The second motor has
perfect quality but recovers the wrong files.

Usage:
    from recovery_judge.fqs import FunctionalQualityScore
    from recovery_judge.functional_validator import FunctionalValidator, RecoveryLevel

    fqs = FunctionalQualityScore()
    score = fqs.compute(
        recovered_files=[
            {"name": "photo.jpg", "data": jpeg_bytes, "original_data": original_jpeg_bytes},
            {"name": "thesis.docx", "data": docx_bytes, "original_data": original_docx_bytes},
        ],
    )
    # score.fqs = 0.85  (overall functional quality)
    # score.per_file = {"photo.jpg": 1.0, "thesis.docx": 0.7}
    # score.level_distribution = {"full": 1, "functional": 1, "partial": 0, ...}
"""

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from .functional_validator import FunctionalValidator, RecoveryLevel


# ─── FQS Result ───────────────────────────────────────────────────────────────

@dataclass
class FQSResult:
    """The result of a Functional Quality Score computation."""
    fqs: float                          # 0.0-1.0 overall score
    n_files: int = 0                    # Total files assessed
    per_file: Dict[str, float] = field(default_factory=dict)  # name → FQS
    per_file_level: Dict[str, str] = field(default_factory=dict)  # name → level
    level_distribution: Dict[str, int] = field(default_factory=dict)  # level → count
    average_functional_score: float = 0.0   # Average of per-file functional scores
    sha256_match_rate: float = 0.0          # Fraction with exact SHA-256 match

    def to_dict(self) -> Dict:
        return {
            "fqs": round(self.fqs, 4),
            "n_files": self.n_files,
            "per_file": {k: round(v, 4) for k, v in self.per_file.items()},
            "per_file_level": self.per_file_level,
            "level_distribution": self.level_distribution,
            "average_functional_score": round(self.average_functional_score, 4),
            "sha256_match_rate": round(self.sha256_match_rate, 4),
        }

    def summary(self) -> str:
        """One-line summary of the FQS result."""
        return (f"FQS={self.fqs:.3f} | {self.n_files} files | "
                f"SHA256={self.sha256_match_rate:.1%} | "
                f"AvgFunc={self.average_functional_score:.3f}")


# ─── Functional Quality Score ─────────────────────────────────────────────────

class FunctionalQualityScore:
    """
    Compute the Functional Quality Score for a set of recovered files.

    FQS measures HOW WELL each file was recovered, regardless of the
    file's importance. This is the complement to RVS (which measures
    WHAT was recovered, weighted by importance).

    The key difference from a simple average:
      - FQS is weighted by file size (a 5MB JPEG with 90% quality
        contributes more than a 1KB TXT with 90% quality)
      - FQS distinguishes between "bit-perfect" and "functional"
        recovery, which is critical for understanding motor quality

    FQS computation:
      1. For each recovered file, compute its functional score (0.0-1.0)
         using the FunctionalValidator
      2. Weight each file's score by its size
      3. FQS = sum(score_i × size_i) / sum(size_i)

    This gives a size-weighted functional quality score.
    """

    def __init__(self):
        self.validator = FunctionalValidator()

    def compute(
        self,
        recovered_files: List[Dict],
        weight_by: str = "size",
    ) -> FQSResult:
        """
        Compute FQS for a set of recovered files.

        Args:
            recovered_files: List of dicts with:
                - "name": filename
                - "data": recovered file bytes (for functional validation)
                - "original_data": original file bytes (for SHA-256 comparison)
                - "size": file size in bytes
            weight_by: How to weight files:
                - "size": weight by file size (default)
                - "equal": equal weight for all files

        Returns:
            FQSResult with overall FQS and per-file breakdown
        """
        if not recovered_files:
            return FQSResult(fqs=0.0)

        per_file_scores = {}
        per_file_levels = {}
        level_dist = {
            "full": 0, "functional": 0, "partial": 0,
            "degraded": 0, "failed": 0
        }
        total_weight = 0.0
        weighted_score = 0.0
        sha256_matches = 0

        for f in recovered_files:
            name = f.get("name", "unknown")
            data = f.get("data", b"")
            original_data = f.get("original_data", None)
            size = f.get("size", len(data) if data else 0)

            # Compute functional score
            val_result = self.validator.validate(data, name, original_data)

            # Get the functional score
            func_score = val_result.get("functional_score", 0.0)
            level = val_result.get("level", RecoveryLevel.FAILED)

            # Store per-file results
            per_file_scores[name] = func_score
            per_file_levels[name] = level.value if isinstance(level, RecoveryLevel) else str(level)

            # Update level distribution
            level_key = level.value if isinstance(level, RecoveryLevel) else str(level)
            level_dist[level_key] = level_dist.get(level_key, 0) + 1

            # Check SHA-256 match
            if original_data is not None:
                if hashlib.sha256(data).hexdigest() == hashlib.sha256(original_data).hexdigest():
                    sha256_matches += 1

            # Compute weight
            if weight_by == "size":
                weight = max(size, 1)  # Avoid zero weight
            else:
                weight = 1.0

            weighted_score += func_score * weight
            total_weight += weight

        # Compute overall FQS
        fqs = weighted_score / total_weight if total_weight > 0 else 0.0

        # Compute average functional score (unweighted)
        avg_func = sum(per_file_scores.values()) / len(per_file_scores) if per_file_scores else 0.0

        # Compute SHA-256 match rate
        sha256_rate = sha256_matches / len(recovered_files) if recovered_files else 0.0

        return FQSResult(
            fqs=fqs,
            n_files=len(recovered_files),
            per_file=per_file_scores,
            per_file_level=per_file_levels,
            level_distribution=level_dist,
            average_functional_score=avg_func,
            sha256_match_rate=sha256_rate,
        )

    def compute_simple(
        self,
        recovered_names: set,
        ground_truth_names: set,
        functional_scores: Dict[str, float],
        file_sizes: Dict[str, int],
    ) -> float:
        """
        Simplified FQS computation when we only have names and scores.

        This is used when we don't have the actual file data, but we
        have pre-computed functional scores from the validator.

        Args:
            recovered_names: Set of recovered file names
            ground_truth_names: Set of ground truth file names
            functional_scores: Dict mapping name → functional score (0.0-1.0)
            file_sizes: Dict mapping name → file size in bytes

        Returns:
            FQS as a float (0.0-1.0)
        """
        if not recovered_names:
            return 0.0

        total_weight = 0.0
        weighted_score = 0.0

        for name in recovered_names:
            score = functional_scores.get(name, 0.0)
            size = file_sizes.get(name, 1)
            weight = max(size, 1)

            weighted_score += score * weight
            total_weight += weight

        return weighted_score / total_weight if total_weight > 0 else 0.0


# ─── Overall Utility ──────────────────────────────────────────────────────────

def compute_overall_utility(rvs: float, fqs: float) -> Dict:
    """
    Compute Overall Utility = RVS × FQS.

    This is the single metric that combines WHAT was recovered (RVS)
    with HOW WELL it was recovered (FQS).

    The decomposition tells you WHY a motor won:
      - High RVS, Low FQS: Recovered important files, but poorly
      - Low RVS, High FQS: Recovered files well, but unimportant ones
      - High RVS, High FQS: Recovered important files well
      - Low RVS, Low FQS: Failed on both dimensions

    Args:
        rvs: Recovery Value Score (0.0-1.0)
        fqs: Functional Quality Score (0.0-1.0)

    Returns:
        Dict with overall_utility, rvs, fqs, and diagnostic
    """
    overall = rvs * fqs

    # Diagnostic: why did the motor get this score?
    if rvs >= 0.7 and fqs >= 0.7:
        diagnostic = "STRONG: Recovered important files with good quality"
    elif rvs >= 0.7 and fqs < 0.7:
        diagnostic = "VALUE-DRIVEN: Recovered important files but with poor quality"
    elif rvs < 0.7 and fqs >= 0.7:
        diagnostic = "QUALITY-DRIVEN: Recovered files well but they were unimportant"
    else:
        diagnostic = "WEAK: Both value and quality are low"

    return {
        "overall_utility": round(overall, 4),
        "rvs": round(rvs, 4),
        "fqs": round(fqs, 4),
        "diagnostic": diagnostic,
        "rvs_contribution": round(rvs / (rvs + fqs) if (rvs + fqs) > 0 else 0, 4),
        "fqs_contribution": round(fqs / (rvs + fqs) if (rvs + fqs) > 0 else 0, 4),
    }


if __name__ == "__main__":
    # Quick test
    fqs_calc = FunctionalQualityScore()

    # Test with synthetic data
    test_files = [
        {
            "name": "photo.jpg",
            "data": (
                b'\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
                b'\xFF\xC0\x00\x0B\x08\x00\x01\x00\x01\x01\x01\x11\x00'
                b'\xFF\xDA\x00\x08\x01\x01\x00\x00\x3F\x00'
                b'\x00' * 500 + b'\xFF\xD9'
            ),
            "size": 567,
        },
    ]

    result = fqs_calc.compute(test_files)
    print(f"FQS Result: {result.summary()}")
    print(f"Overall Utility (RVS=0.8, FQS={result.fqs:.3f}):")
    utility = compute_overall_utility(0.8, result.fqs)
    print(f"  {utility}")
