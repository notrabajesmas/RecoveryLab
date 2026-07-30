"""
RecoveryLab — Recovery Judge Metrics
======================================
All metrics that the Judge measures.

Not just "files recovered". Also:
  - checksum correctness
  - corrupt files
  - bytes recovered
  - directories rebuilt
  - read count
  - sectors wasted
  - false positives
  - duplicates
  - integrity score
  - time to first file
  - MFT entries parsed
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set


@dataclass
class RecoveryMetrics:
    """
    Complete set of metrics from a recovery attempt.

    Every metric the Judge measures — because a motor that recovers 100 files
    but 12 are corrupt is NOT the same as one that recovers 88 correct files.
    """

    # ─── Primary Metrics ──────────────────────────────────────────────
    files_recovered: int = 0          # Total files the motor claims to have recovered
    files_correct_checksum: int = 0   # Files with SHA-256 matching ground truth
    files_corrupt: int = 0            # Files recovered but with wrong checksum
    files_missing: int = 0            # Files in ground truth but NOT recovered

    # ─── Byte-Level Metrics ───────────────────────────────────────────
    bytes_recovered: int = 0          # Total bytes of recovered file data
    bytes_correct: int = 0            # Bytes that match ground truth exactly
    bytes_total_ground_truth: int = 0 # Total bytes in ground truth

    # ─── Structural Metrics ───────────────────────────────────────────
    directories_rebuilt: int = 0      # Directory structures reconstructed
    directories_total: int = 0        # Total directories in ground truth
    mft_entries_parsed: int = 0       # MFT entries successfully parsed
    mft_entries_total: int = 0        # Total MFT entries in image

    # ─── Efficiency Metrics ───────────────────────────────────────────
    read_count: int = 0               # Total sector reads performed
    sectors_wasted: int = 0           # Reads that returned no useful data
    sectors_total: int = 0            # Total sectors in image
    time_to_first_file: int = 0       # Reads before first file recovered

    # ─── Quality Metrics ──────────────────────────────────────────────
    false_positives: int = 0          # Files reported that don't match ground truth
    duplicates: int = 0               # Same file recovered multiple times
    integrity_score: float = 0.0      # 0.0-1.0 composite score

    # ─── Timing ───────────────────────────────────────────────────────
    total_time_seconds: float = 0.0   # Wall-clock time

    # ─── Detailed Results ─────────────────────────────────────────────
    recovered_file_details: List[Dict] = field(default_factory=list)
    missing_file_details: List[Dict] = field(default_factory=list)
    corrupt_file_details: List[Dict] = field(default_factory=list)

    # ─── Budget Metrics ───────────────────────────────────────────────
    read_budget: int = 0              # Maximum reads allowed (0 = unlimited)
    budget_used_pct: float = 0.0      # Percentage of budget used

    def recovery_rate(self) -> float:
        """Fraction of ground truth files recovered (correct checksum only)."""
        total = self.files_correct_checksum + self.files_corrupt + self.files_missing
        if total == 0:
            return 0.0
        return self.files_correct_checksum / total

    def byte_recovery_rate(self) -> float:
        """Fraction of ground truth bytes recovered correctly."""
        if self.bytes_total_ground_truth == 0:
            return 0.0
        return self.bytes_correct / self.bytes_total_ground_truth

    def read_efficiency(self) -> float:
        """Fraction of reads that produced useful data."""
        if self.read_count == 0:
            return 0.0
        return 1.0 - (self.sectors_wasted / self.read_count)

    def corruption_rate(self) -> float:
        """Fraction of recovered files that are corrupt."""
        total = self.files_correct_checksum + self.files_corrupt
        if total == 0:
            return 0.0
        return self.files_corrupt / total

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "files_recovered": self.files_recovered,
            "files_correct_checksum": self.files_correct_checksum,
            "files_corrupt": self.files_corrupt,
            "files_missing": self.files_missing,
            "bytes_recovered": self.bytes_recovered,
            "bytes_correct": self.bytes_correct,
            "bytes_total_ground_truth": self.bytes_total_ground_truth,
            "directories_rebuilt": self.directories_rebuilt,
            "directories_total": self.directories_total,
            "mft_entries_parsed": self.mft_entries_parsed,
            "mft_entries_total": self.mft_entries_total,
            "read_count": self.read_count,
            "sectors_wasted": self.sectors_wasted,
            "sectors_total": self.sectors_total,
            "time_to_first_file": self.time_to_first_file,
            "false_positives": self.false_positives,
            "duplicates": self.duplicates,
            "integrity_score": self.integrity_score,
            "total_time_seconds": self.total_time_seconds,
            "read_budget": self.read_budget,
            "budget_used_pct": self.budget_used_pct,
            # Computed rates
            "recovery_rate": round(self.recovery_rate(), 4),
            "byte_recovery_rate": round(self.byte_recovery_rate(), 4),
            "read_efficiency": round(self.read_efficiency(), 4),
            "corruption_rate": round(self.corruption_rate(), 4),
        }

    def summary(self) -> str:
        """Human-readable summary."""
        return (
            f"Recovery: {self.files_correct_checksum}/{self.files_correct_checksum + self.files_corrupt + self.files_missing} "
            f"({self.recovery_rate():.1%}) | "
            f"Corrupt: {self.files_corrupt} | "
            f"Reads: {self.read_count} ({self.read_efficiency():.1%} useful) | "
            f"First file: {self.time_to_first_file} reads | "
            f"Integrity: {self.integrity_score:.2f}"
        )


@dataclass
class ComparisonResult:
    """Result of comparing two motors on the same dataset."""
    motor_a_name: str
    motor_b_name: str
    metrics_a: RecoveryMetrics
    metrics_b: RecoveryMetrics
    dataset: str
    attack_id: str = ""

    # ─── Delta Metrics ────────────────────────────────────────────────
    def delta_recovery_rate(self) -> float:
        """B - A recovery rate. Positive = B is better."""
        return self.metrics_b.recovery_rate() - self.metrics_a.recovery_rate()

    def delta_read_efficiency(self) -> float:
        """B - A read efficiency. Positive = B is better."""
        return self.metrics_b.read_efficiency() - self.metrics_a.read_efficiency()

    def delta_reads(self) -> int:
        """A - B reads. Positive = B uses fewer reads (better)."""
        return self.metrics_a.read_count - self.metrics_b.read_count

    def delta_time_to_first(self) -> int:
        """A - B reads to first file. Positive = B finds first file faster."""
        return self.metrics_a.time_to_first_file - self.metrics_b.time_to_first_file

    def delta_corruption_rate(self) -> float:
        """A - B corruption rate. Positive = B has less corruption (better)."""
        return self.metrics_a.corruption_rate() - self.metrics_b.corruption_rate()

    def h1_supported(self) -> bool:
        """
        Does this comparison support H1?

        H1: "MFT-first strategy improves recovery rate AND/OR reduces reads"
        """
        better_recovery = self.delta_recovery_rate() > 0.01  # >1% improvement
        fewer_reads = self.delta_reads() > 0  # Fewer reads needed

        return better_recovery or fewer_reads

    def h1_strength(self) -> str:
        """How strongly does this result support or refute H1?"""
        dr = self.delta_recovery_rate()
        de = self.delta_read_efficiency()

        if dr > 0.10 or de > 0.20:
            return "STRONG_SUPPORT"
        elif dr > 0.03 or de > 0.05:
            return "MODERATE_SUPPORT"
        elif dr > 0.01 or de > 0.01:
            return "WEAK_SUPPORT"
        elif dr > -0.01 and de > -0.01:
            return "NEUTRAL"
        elif dr > -0.03 and de > -0.05:
            return "WEAK_REFUTATION"
        else:
            return "STRONG_REFUTATION"

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "motor_a": self.motor_a_name,
            "motor_b": self.motor_b_name,
            "dataset": self.dataset,
            "attack_id": self.attack_id,
            "metrics_a": self.metrics_a.to_dict(),
            "metrics_b": self.metrics_b.to_dict(),
            "deltas": {
                "recovery_rate": round(self.delta_recovery_rate(), 4),
                "read_efficiency": round(self.delta_read_efficiency(), 4),
                "reads_saved": self.delta_reads(),
                "time_to_first_improvement": self.delta_time_to_first(),
                "corruption_rate_improvement": round(self.delta_corruption_rate(), 4),
            },
            "h1_supported": self.h1_supported(),
            "h1_strength": self.h1_strength(),
        }
