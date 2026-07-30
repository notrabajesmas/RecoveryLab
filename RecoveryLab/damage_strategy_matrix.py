"""
RecoveryLab — Damage × Strategy Matrix
========================================
The most useful artifact in the project. Not a single curve, but a MATRIX.

H4: "Para cada tipo de daño, existe una estrategia que produce los mejores
     resultados. La combinación de estas relaciones forma una matriz
     daño×estrategia que predice la estrategia óptima para cada estado del medio."

The matrix maps:
  damage_type × strategy → expected outcome (recovery, efficiency, integrity)

This is the LAB's real product — not a single motor, but a system that knows
WHEN to use WHICH strategy.

Matrix structure:
  Rows: damage patterns (MFT partial, head crash, intermittent sectors, etc.)
  Columns: strategies (Carving, MFT-First, Motor C, Journal-first, etc.)
  Cells: StrategyOutcome (recovery_rate, efficiency, integrity, rvs, verdict)

Verdicts:
  🟢 WINNER — best strategy for this damage type
  🟡 VIABLE — works but not optimal
  🔴 POOR — fails or recovers very little
  ⚪ UNTESTED — no data yet

Usage:
    from damage_strategy_matrix import DamageStrategyMatrix, DamageType, StrategyID

    matrix = DamageStrategyMatrix()
    matrix.add_outcome(DamageType.MFT_PARTIAL, StrategyID.MFT_FIRST,
                       StrategyOutcome(recovery_rate=0.93, ...))
    matrix.print_matrix()
"""

import json
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timezone


# ─── Damage Types ─────────────────────────────────────────────────────────────

class DamageType(Enum):
    """Types of damage that can occur to a disk image."""
    MFT_PARTIAL = "mft_partial"               # MFT entries partially destroyed
    MFT_TOTAL = "mft_total"                   # MFT completely destroyed
    HEAD_CRASH_START = "head_crash_start"      # First sectors damaged
    HEAD_CRASH_END = "head_crash_end"          # Last sectors damaged
    INTERMITTENT_SECTORS = "intermittent_sectors"  # Every Nth sector fails
    SCRATCH_CONTINUOUS = "scratch_continuous"  # Continuous zone of damage
    RUNLISTS_CORRUPT = "runlists_corrupt"      # MFT run lists with bit flips
    BITMAP_BROKEN = "bitmap_broken"            # Allocation bitmap corrupted
    JOURNAL_CORRUPT = "journal_corrupt"        # Journal/USN corrupted
    CRC_ERRORS = "crc_errors"                  # Random bit flips in data
    PARTIAL_OVERWRITE = "partial_overwrite"    # Files partially overwritten
    SLOW_SECTORS = "slow_sectors"              # Sectors marked as slow
    TIMEOUT_PATTERN = "timeout_pattern"        # Every Nth sector times out
    RANDOM_NOISE = "random_noise"              # Random bytes in random sectors
    FRAGMENTATION_CHAOS = "fragmentation_chaos"  # Unpredictable fragmentation
    COMBINED_MFT_BITMAP = "combined_mft_bitmap"  # MFT + Bitmap destroyed
    COMBINED_MFT_JOURNAL_BITMAP = "combined_mft_journal_bitmap"  # Triple attack
    NO_DAMAGE = "no_damage"                    # Healthy disk (baseline)


# ─── Strategy Identifiers ─────────────────────────────────────────────────────

class StrategyID(Enum):
    """Identifiers for recovery strategies."""
    CARVING = "carving"               # Signature-only, never MFT
    MFT_FIRST = "mft_first"          # Metadata-first, no carving
    MFT_SEQUENTIAL = "mft_sequential"  # MFT-last (read everything, then parse)
    MOTOR_C = "motor_c"              # Adaptive orchestrator
    JOURNAL_FIRST = "journal_first"  # Journal-guided (future)
    BITMAP_GUIDED = "bitmap_guided"  # Bitmap-guided (future)
    USN_GUIDED = "usn_guided"        # USN change journal (future)
    MFT_MIRROR = "mft_mirror"        # MFT Mirror recovery (future)
    TOLERANT_PARSER = "tolerant_parser"  # Tolerant MFT parser (future)
    PROBABILISTIC = "probabilistic"  # Probabilistic carving (future)


# ─── Strategy Outcome ─────────────────────────────────────────────────────────

class Verdict(Enum):
    """How well a strategy performs for a given damage type."""
    WINNER = "winner"       # 🟢 Best strategy for this damage
    VIABLE = "viable"       # 🟡 Works but not optimal
    POOR = "poor"           # 🔴 Fails or recovers very little
    UNTESTED = "untested"   # ⚪ No data yet


@dataclass
class StrategyOutcome:
    """The outcome of running a strategy against a specific damage type."""
    strategy: StrategyID
    damage_type: DamageType

    # Core metrics
    recovery_rate: float = 0.0        # 0.0-1.0
    correct_checksum_rate: float = 0.0  # 0.0-1.0
    read_efficiency: float = 0.0      # 0.0-1.0
    integrity_score: float = 0.0      # 0.0-1.0
    false_positive_rate: float = 0.0  # 0.0-1.0

    # Recovery Value Score (weighted by file importance)
    rvs: float = 0.0                  # 0.0-1.0

    # Per-format breakdown (if available)
    format_breakdown: Dict[str, float] = field(default_factory=dict)
    # e.g., {"jpeg": 0.85, "png": 0.72, "pdf": 0.30, "txt": 0.0}

    # Statistical measures
    n_observations: int = 1
    ci_lower: float = 0.0
    ci_upper: float = 0.0

    # Metadata
    experiment_id: str = ""
    timestamp: str = ""

    @property
    def verdict(self) -> Verdict:
        """Determine verdict based on recovery rate."""
        if self.n_observations == 0:
            return Verdict.UNTESTED
        if self.recovery_rate >= 0.80:
            return Verdict.WINNER
        if self.recovery_rate >= 0.40:
            return Verdict.VIABLE
        if self.recovery_rate > 0.0:
            return Verdict.POOR
        return Verdict.POOR

    @property
    def emoji(self) -> str:
        """Emoji representation of verdict."""
        mapping = {
            Verdict.WINNER: "🟢",
            Verdict.VIABLE: "🟡",
            Verdict.POOR: "🔴",
            Verdict.UNTESTED: "⚪",
        }
        return mapping.get(self.verdict, "⚪")

    def to_dict(self) -> Dict:
        return {
            "strategy": self.strategy.value,
            "damage_type": self.damage_type.value,
            "recovery_rate": round(self.recovery_rate, 4),
            "correct_checksum_rate": round(self.correct_checksum_rate, 4),
            "read_efficiency": round(self.read_efficiency, 4),
            "integrity_score": round(self.integrity_score, 4),
            "false_positive_rate": round(self.false_positive_rate, 4),
            "rvs": round(self.rvs, 4),
            "format_breakdown": self.format_breakdown,
            "n_observations": self.n_observations,
            "ci_lower": round(self.ci_lower, 4),
            "ci_upper": round(self.ci_upper, 4),
            "verdict": self.verdict.value,
            "experiment_id": self.experiment_id,
        }


# ─── Damage × Strategy Matrix ─────────────────────────────────────────────────

class DamageStrategyMatrix:
    """
    The core artifact: a matrix mapping damage types to strategy outcomes.

    This is the LAB's real product. Not a single motor, but a system
    that knows WHEN to use WHICH strategy.

    Usage:
        matrix = DamageStrategyMatrix()
        matrix.add_outcome(DamageType.MFT_PARTIAL, StrategyID.MFT_FIRST,
                          StrategyOutcome(recovery_rate=0.93, ...))
        matrix.print_matrix()
        matrix.best_strategy(DamageType.MFT_PARTIAL)  # → StrategyID.MFT_FIRST
    """

    def __init__(self):
        # Matrix: damage_type → strategy → outcome
        self.outcomes: Dict[DamageType, Dict[StrategyID, StrategyOutcome]] = {}

        # Initialize all cells as UNTESTED
        for damage in DamageType:
            self.outcomes[damage] = {}
            for strategy in StrategyID:
                self.outcomes[damage][strategy] = StrategyOutcome(
                    strategy=strategy,
                    damage_type=damage,
                )

    def add_outcome(self, damage_type: DamageType, strategy: StrategyID,
                    outcome: StrategyOutcome):
        """Add or update an outcome in the matrix."""
        outcome.damage_type = damage_type
        outcome.strategy = strategy
        if not outcome.timestamp:
            outcome.timestamp = datetime.now(timezone.utc).isoformat()
        self.outcomes[damage_type][strategy] = outcome

    def get_outcome(self, damage_type: DamageType,
                    strategy: StrategyID) -> StrategyOutcome:
        """Get the outcome for a specific damage/strategy combination."""
        return self.outcomes.get(damage_type, {}).get(strategy,
            StrategyOutcome(strategy=strategy, damage_type=damage_type))

    def best_strategy(self, damage_type: DamageType) -> Optional[StrategyID]:
        """Find the best strategy for a given damage type."""
        outcomes = self.outcomes.get(damage_type, {})
        if not outcomes:
            return None

        best = None
        best_rate = -1.0
        for strategy_id, outcome in outcomes.items():
            if outcome.n_observations > 0 and outcome.recovery_rate > best_rate:
                best_rate = outcome.recovery_rate
                best = strategy_id

        return best

    def best_strategies(self) -> Dict[DamageType, Tuple[StrategyID, StrategyOutcome]]:
        """Find the best strategy for each damage type."""
        result = {}
        for damage_type in DamageType:
            best = self.best_strategy(damage_type)
            if best:
                result[damage_type] = (best, self.get_outcome(damage_type, best))
        return result

    def tested_damage_types(self) -> List[DamageType]:
        """Get damage types that have at least one tested strategy."""
        tested = []
        for damage_type, strategies in self.outcomes.items():
            if any(o.n_observations > 0 for o in strategies.values()):
                tested.append(damage_type)
        return tested

    def tested_strategies(self) -> List[StrategyID]:
        """Get strategies that have been tested in at least one damage type."""
        tested = set()
        for damage_type, strategies in self.outcomes.items():
            for strategy_id, outcome in strategies.items():
                if outcome.n_observations > 0:
                    tested.add(strategy_id)
        return sorted(tested, key=lambda s: s.value)

    def coverage_pct(self) -> float:
        """What fraction of the matrix has been tested?"""
        total = len(DamageType) * len(StrategyID)
        tested = sum(
            1 for dt in self.outcomes.values()
            for o in dt.values()
            if o.n_observations > 0
        )
        return tested / total if total else 0.0

    def print_matrix(self) -> str:
        """Print the matrix as a markdown table."""
        # Header
        tested_strats = self.tested_strategies()
        lines = [
            "# Damage × Strategy Matrix",
            "",
            f"Coverage: {self.coverage_pct():.0%} ({len(tested_strats)} strategies tested)",
            "",
        ]

        # Table header
        header = "| Damage Type |"
        separator = "|---|"
        for strat in tested_strats:
            header += f" {strat.value} |"
            separator += "---|"
        lines.append(header)
        lines.append(separator)

        # Rows
        for damage in DamageType:
            row = f"| {damage.value} |"
            for strat in tested_strats:
                outcome = self.get_outcome(damage, strat)
                if outcome.n_observations == 0:
                    row += " ⚪ |"
                else:
                    row += f" {outcome.emoji} {outcome.recovery_rate:.0%} |"
            lines.append(row)

        # Best strategy summary
        lines.append("")
        lines.append("## Best Strategy per Damage Type")
        lines.append("")
        lines.append("| Damage Type | Best Strategy | Recovery Rate | Verdict |")
        lines.append("|---|---|---|---|")
        for damage in DamageType:
            best = self.best_strategy(damage)
            if best:
                outcome = self.get_outcome(damage, best)
                lines.append(
                    f"| {damage.value} | {best.value} | "
                    f"{outcome.recovery_rate:.1%} | {outcome.emoji} |"
                )
            else:
                lines.append(f"| {damage.value} | — | — | ⚪ |")

        return "\n".join(lines)

    def print_detailed_matrix(self) -> str:
        """Print detailed matrix with per-format breakdowns."""
        lines = [
            "# Damage × Strategy Matrix (Detailed)",
            "",
        ]

        for damage in DamageType:
            tested = [
                (s, self.get_outcome(damage, s))
                for s in StrategyID
                if self.get_outcome(damage, s).n_observations > 0
            ]
            if not tested:
                continue

            lines.append(f"## {damage.value}")
            lines.append("")
            for strat, outcome in sorted(tested, key=lambda x: -x[1].recovery_rate):
                lines.append(f"  **{strat.value}**: {outcome.recovery_rate:.1%} recovery "
                           f"| {outcome.read_efficiency:.1%} efficiency "
                           f"| RVS {outcome.rvs:.1%} | {outcome.emoji}")
                if outcome.format_breakdown:
                    for fmt, rate in sorted(outcome.format_breakdown.items(),
                                           key=lambda x: -x[1]):
                        lines.append(f"    - {fmt}: {rate:.1%}")
            lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> Dict:
        """Serialize the matrix to a dictionary."""
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "coverage_pct": round(self.coverage_pct(), 4),
            "strategies_tested": [s.value for s in self.tested_strategies()],
            "damage_types_tested": [d.value for d in self.tested_damage_types()],
            "best_strategies": {
                dt.value: (best.value, self.get_outcome(dt, best).to_dict())
                for dt, (best, _) in self.best_strategies().items()
            },
            "outcomes": {
                dt.value: {
                    s.value: o.to_dict()
                    for s, o in strategies.items()
                    if o.n_observations > 0
                }
                for dt, strategies in self.outcomes.items()
            },
        }

    def save(self, path: Path):
        """Save the matrix to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: Path) -> 'DamageStrategyMatrix':
        """Load a matrix from a JSON file."""
        with open(path, 'r') as f:
            data = json.load(f)

        matrix = cls()
        for dt_value, strategies in data.get("outcomes", {}).items():
            damage_type = DamageType(dt_value)
            for s_value, o_data in strategies.items():
                strategy = StrategyID(s_value)
                outcome = StrategyOutcome(
                    strategy=strategy,
                    damage_type=damage_type,
                    recovery_rate=o_data.get("recovery_rate", 0.0),
                    correct_checksum_rate=o_data.get("correct_checksum_rate", 0.0),
                    read_efficiency=o_data.get("read_efficiency", 0.0),
                    integrity_score=o_data.get("integrity_score", 0.0),
                    false_positive_rate=o_data.get("false_positive_rate", 0.0),
                    rvs=o_data.get("rvs", 0.0),
                    format_breakdown=o_data.get("format_breakdown", {}),
                    n_observations=o_data.get("n_observations", 1),
                    ci_lower=o_data.get("ci_lower", 0.0),
                    ci_upper=o_data.get("ci_upper", 0.0),
                    experiment_id=o_data.get("experiment_id", ""),
                    timestamp=o_data.get("timestamp", ""),
                )
                matrix.add_outcome(damage_type, strategy, outcome)

        return matrix


# ─── Expected Matrix (theoretical predictions) ────────────────────────────────

def build_expected_matrix() -> DamageStrategyMatrix:
    """
    Build the THEORETICAL matrix based on domain knowledge.

    This is the hypothesis: what we EXPECT to find. Then we run experiments
    to confirm or refute each cell.

    Damage Type          | MFT-First | Carving | Journal | Bitmap | Expected
    MFT parcial          | 🟡        | 🟢      | 🟢      | 🟡     | Hybrid
    Head crash inicio    | 🔴        | 🟢      | 🔴      | 🔴     | Carving
    Sectores intermitentes | 🔴      | 🟡      | 🟢      | 🟢     | Adaptativa
    Runlists corruptos   | 🔴        | 🟡      | 🟢      | 🟢     | Adaptativa
    Bitmap roto          | 🟢        | 🟢      | 🟡      | 🔴     | MFT
    """
    matrix = DamageStrategyMatrix()

    # MFT partial (20-60% destroyed)
    matrix.add_outcome(DamageType.MFT_PARTIAL, StrategyID.MFT_FIRST,
        StrategyOutcome(strategy=StrategyID.MFT_FIRST, damage_type=DamageType.MFT_PARTIAL,
                       recovery_rate=0.80, read_efficiency=0.75,
                       integrity_score=0.85, rvs=0.78,
                       n_observations=0,  # Theoretical
                       experiment_id="theoretical"))
    matrix.add_outcome(DamageType.MFT_PARTIAL, StrategyID.CARVING,
        StrategyOutcome(strategy=StrategyID.CARVING, damage_type=DamageType.MFT_PARTIAL,
                       recovery_rate=0.07, read_efficiency=0.15,
                       integrity_score=0.50, rvs=0.05,
                       n_observations=0, experiment_id="theoretical"))
    matrix.add_outcome(DamageType.MFT_PARTIAL, StrategyID.JOURNAL_FIRST,
        StrategyOutcome(strategy=StrategyID.JOURNAL_FIRST, damage_type=DamageType.MFT_PARTIAL,
                       recovery_rate=0.75, read_efficiency=0.65,
                       integrity_score=0.80, rvs=0.72,
                       n_observations=0, experiment_id="theoretical"))

    # Head crash start (first sectors damaged)
    matrix.add_outcome(DamageType.HEAD_CRASH_START, StrategyID.MFT_FIRST,
        StrategyOutcome(strategy=StrategyID.MFT_FIRST, damage_type=DamageType.HEAD_CRASH_START,
                       recovery_rate=0.10, read_efficiency=0.30,
                       integrity_score=0.20, rvs=0.10,
                       n_observations=0, experiment_id="theoretical"))
    matrix.add_outcome(DamageType.HEAD_CRASH_START, StrategyID.CARVING,
        StrategyOutcome(strategy=StrategyID.CARVING, damage_type=DamageType.HEAD_CRASH_START,
                       recovery_rate=0.50, read_efficiency=0.15,
                       integrity_score=0.60, rvs=0.45,
                       n_observations=0, experiment_id="theoretical"))

    # Intermittent sectors
    matrix.add_outcome(DamageType.INTERMITTENT_SECTORS, StrategyID.MFT_FIRST,
        StrategyOutcome(strategy=StrategyID.MFT_FIRST, damage_type=DamageType.INTERMITTENT_SECTORS,
                       recovery_rate=0.05, read_efficiency=0.20,
                       integrity_score=0.10, rvs=0.05,
                       n_observations=0, experiment_id="theoretical"))
    matrix.add_outcome(DamageType.INTERMITTENT_SECTORS, StrategyID.CARVING,
        StrategyOutcome(strategy=StrategyID.CARVING, damage_type=DamageType.INTERMITTENT_SECTORS,
                       recovery_rate=0.15, read_efficiency=0.10,
                       integrity_score=0.40, rvs=0.10,
                       n_observations=0, experiment_id="theoretical"))

    # Bitmap broken
    matrix.add_outcome(DamageType.BITMAP_BROKEN, StrategyID.MFT_FIRST,
        StrategyOutcome(strategy=StrategyID.MFT_FIRST, damage_type=DamageType.BITMAP_BROKEN,
                       recovery_rate=0.90, read_efficiency=0.70,
                       integrity_score=0.88, rvs=0.88,
                       n_observations=0, experiment_id="theoretical"))
    matrix.add_outcome(DamageType.BITMAP_BROKEN, StrategyID.CARVING,
        StrategyOutcome(strategy=StrategyID.CARVING, damage_type=DamageType.BITMAP_BROKEN,
                       recovery_rate=0.07, read_efficiency=0.15,
                       integrity_score=0.50, rvs=0.05,
                       n_observations=0, experiment_id="theoretical"))

    # Mark all theoretical outcomes as untested
    for dt in matrix.outcomes:
        for s in matrix.outcomes[dt]:
            matrix.outcomes[dt][s].n_observations = 0

    return matrix


if __name__ == "__main__":
    matrix = build_expected_matrix()
    print(matrix.print_matrix())
    print()
    print(f"Coverage: {matrix.coverage_pct():.0%}")
    print(f"Strategies tested: {len(matrix.tested_strategies())}")
    print(f"Damage types tested: {len(matrix.tested_damage_types())}")
