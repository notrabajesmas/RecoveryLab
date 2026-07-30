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
  - READ CLASSIFICATION (useful reads formalized)

Read Classification (formal definition):
  Every sector read is classified into exactly one category:

  1. DATA_READ       — Read a sector that contains file data (ground truth)
  2. METADATA_READ   — Read a sector that contains metadata (MFT, bitmap, journal, INDX)
  3. DIAGNOSTIC_READ — Read a sector to determine the state of the disk
                        (e.g., checking if a sector is readable, testing a hypothesis)
  4. REDUNDANT_READ  — Read a sector that was already read (duplicate/overlapping)
  5. WASTED_READ     — Read a sector that contains no useful information
                        (free space, zeros, unrelated data)

  Key insight: "Useful" is NOT the same as "produced file data".
  - A metadata read IS useful if it guides subsequent reads
  - A diagnostic read IS useful if it provides information about disk state
  - A redundant read is NOT useful (even if it produces data)
  - A wasted read is definitely NOT useful

  read_efficiency_v1 = 1 - (wasted + redundant) / total
  read_efficiency_v2 = (data + metadata + diagnostic) / total
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set


@dataclass
class ReadClassification:
    """
    Classification of all reads performed during recovery.

    Every read falls into exactly one category.
    This is the formal definition of "useful reads".
    """
    data_reads: int = 0       # Sectors containing file data (ground truth)
    metadata_reads: int = 0   # Sectors containing MFT, bitmap, journal, INDX
    diagnostic_reads: int = 0 # Sectors read to determine disk state
    redundant_reads: int = 0  # Sectors already read (duplicate)
    wasted_reads: int = 0     # Sectors with no useful information

    @property
    def total_reads(self) -> int:
        return (self.data_reads + self.metadata_reads +
                self.diagnostic_reads + self.redundant_reads + self.wasted_reads)

    def useful_reads_v1(self) -> int:
        """Useful = data + metadata + diagnostic (anything that provides information)."""
        return self.data_reads + self.metadata_reads + self.diagnostic_reads

    def useful_reads_v2(self) -> int:
        """Useful = data + metadata (only reads that directly contribute to recovery)."""
        return self.data_reads + self.metadata_reads

    def efficiency_v1(self) -> float:
        """Fraction of reads that provide any information (incl. diagnostic)."""
        total = self.total_reads
        if total == 0:
            return 0.0
        return self.useful_reads_v1() / total

    def efficiency_v2(self) -> float:
        """Fraction of reads that directly contribute to recovery."""
        total = self.total_reads
        if total == 0:
            return 0.0
        return self.useful_reads_v2() / total

    def to_dict(self) -> Dict:
        return {
            "data_reads": self.data_reads,
            "metadata_reads": self.metadata_reads,
            "diagnostic_reads": self.diagnostic_reads,
            "redundant_reads": self.redundant_reads,
            "wasted_reads": self.wasted_reads,
            "total_reads": self.total_reads,
            "efficiency_v1": round(self.efficiency_v1(), 4),
            "efficiency_v2": round(self.efficiency_v2(), 4),
        }


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
    sectors_wasted: int = 0           # Reads that returned no useful data (legacy)
    sectors_total: int = 0            # Total sectors in image
    time_to_first_file: int = 0       # Reads before first file recovered

    # ─── Read Classification (formalized) ─────────────────────────────
    read_classification: ReadClassification = field(default_factory=ReadClassification)

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

    # ─── Confidence Metrics ───────────────────────────────────────────
    mft_confidence: float = 0.0       # 0.0-1.0 estimated confidence in MFT
    strategy_used: str = ""           # Which strategy was selected

    # ─── Recovery Value Score ──────────────────────────────────────────
    rvs: float = 0.0                  # 0.0-1.0 Recovery Value Score (user perspective)
    rvs_breakdown: Dict = field(default_factory=dict)  # Detailed RVS breakdown

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
        """
        Fraction of reads that produced useful data (v2 — formal definition).

        Uses the formal read classification: useful = data + metadata.
        Diagnostic reads are valuable but not counted as "efficient" in the
        strict sense, because they don't directly produce file data.
        """
        if self.read_count == 0:
            return 0.0
        # Use formal classification if available
        if self.read_classification.total_reads > 0:
            return self.read_classification.efficiency_v2()
        # Fallback to legacy calculation
        return 1.0 - (self.sectors_wasted / self.read_count)

    def read_efficiency_broad(self) -> float:
        """
        Broad efficiency: includes diagnostic reads as useful.

        A diagnostic read IS useful — it provides information about disk state.
        This metric answers: "what fraction of reads gave us ANY information?"
        """
        if self.read_count == 0:
            return 0.0
        if self.read_classification.total_reads > 0:
            return self.read_classification.efficiency_v1()
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
            "read_classification": self.read_classification.to_dict(),
            "false_positives": self.false_positives,
            "duplicates": self.duplicates,
            "integrity_score": self.integrity_score,
            "total_time_seconds": self.total_time_seconds,
            "read_budget": self.read_budget,
            "budget_used_pct": self.budget_used_pct,
            "mft_confidence": round(self.mft_confidence, 4),
            "strategy_used": self.strategy_used,
            # Computed rates
            "recovery_rate": round(self.recovery_rate(), 4),
            "byte_recovery_rate": round(self.byte_recovery_rate(), 4),
            "read_efficiency": round(self.read_efficiency(), 4),
            "read_efficiency_broad": round(self.read_efficiency_broad(), 4),
            "corruption_rate": round(self.corruption_rate(), 4),
            "rvs": round(self.rvs, 4),
            "rvs_breakdown": self.rvs_breakdown,
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

        H1.1: "Priorizar metadatos recuperables reduce significativamente
               el costo de adquisición cuando los metadatos son suficientemente confiables."

        H1 is supported when Motor B uses fewer reads OR recovers more files.
        """
        better_recovery = self.delta_recovery_rate() > 0.01
        fewer_reads = self.delta_reads() > 0

        return better_recovery or fewer_reads

    def h1_11_supported(self) -> bool:
        """
        H1.1: Metadata prioritization reduces acquisition cost when metadata is reliable.

        This is true when:
          - Motor B uses fewer reads (lower cost)
          - Motor B's recovery rate is NOT significantly worse
        """
        fewer_reads = self.delta_reads() > 0
        not_much_worse = self.delta_recovery_rate() > -0.05

        return fewer_reads and not_much_worse

    def h1_12_supported(self) -> bool:
        """
        H1.2: When metadata confidence drops below a threshold, optimal strategy
              switches from prioritization to hybrid.

        This is true when:
          - Motor B's recovery rate is significantly worse than Motor A
          - This indicates Motor B should have fallen back to a different strategy
        """
        much_worse_recovery = self.delta_recovery_rate() < -0.10
        return much_worse_recovery

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
            "h1_11_supported": self.h1_11_supported(),
            "h1_12_triggered": self.h1_12_supported(),
            "h1_strength": self.h1_strength(),
        }


@dataclass
class ConfidenceSweepPoint:
    """A single data point in a confidence sweep."""
    mft_damage_pct: float          # 0.0 - 1.0
    mft_confidence: float          # Calculated confidence level
    motor_a_recovery: float        # Motor A recovery rate
    motor_b_recovery: float        # Motor B recovery rate
    motor_a_reads: int             # Motor A total reads
    motor_b_reads: int             # Motor B total reads
    motor_a_efficiency: float      # Motor A read efficiency
    motor_b_efficiency: float      # Motor B read efficiency
    optimal_strategy: str          # "mft_first", "hybrid", "carving"


@dataclass
class ConfidenceSweepResult:
    """Complete result of a confidence sweep experiment."""
    dataset: str
    points: List[ConfidenceSweepPoint] = field(default_factory=list)

    def find_threshold(self) -> Optional[float]:
        """
        Find the confidence threshold where Motor B's recovery drops
        significantly below Motor A's.

        This is the "golden threshold" — the point where the motor should
        switch from MFT-first to hybrid/carving.
        """
        for i in range(1, len(self.points)):
            prev = self.points[i-1]
            curr = self.points[i]

            # If Motor B's recovery dropped more than 10% relative to Motor A
            delta = curr.motor_b_recovery - curr.motor_a_recovery
            if delta < -0.10:
                return prev.mft_confidence

        return None

    def to_dict(self) -> Dict:
        return {
            "dataset": self.dataset,
            "threshold": self.find_threshold(),
            "points": [
                {
                    "mft_damage_pct": p.mft_damage_pct,
                    "mft_confidence": p.mft_confidence,
                    "motor_a_recovery": round(p.motor_a_recovery, 4),
                    "motor_b_recovery": round(p.motor_b_recovery, 4),
                    "motor_a_reads": p.motor_a_reads,
                    "motor_b_reads": p.motor_b_reads,
                    "motor_a_efficiency": round(p.motor_a_efficiency, 4),
                    "motor_b_efficiency": round(p.motor_b_efficiency, 4),
                    "optimal_strategy": p.optimal_strategy,
                }
                for p in self.points
            ],
        }
