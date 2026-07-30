#!/usr/bin/env python3
"""
RecoveryLab — Strategy Crossover Curve
========================================
The most important experiment in the project.

H2: "Existe una frontera observable donde la estrategia óptima cambia
     según el estado del medio."

This experiment finds that frontier.

Progressive MFT degradation: 0% → 5% → 10% → ... → 100%
At each point, measure:
  - Recovery rate (Carving, MFT-First, Motor C)
  - Read count
  - Read efficiency
  - Correct checksums
  - Corrupt files
  - False positives
  - Integrity score
  - 95% CI (with N repetitions)
  - p-value (Carving vs MFT-First)
  - Effect size (Cohen's d)

The crossover point — where Carving overtakes MFT-First — is the
discovery that makes this project scientifically valuable.
"""

import sys
import json
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from dataset_builder.manifest import load_manifest
from corruptor.corruptor import Corruptor
from corruptor.models import MFTPartialDeleteModel
from recovery_judge.judge import RecoveryJudge
from recovery_judge.metrics import RecoveryMetrics
from motors.motor_carving import MotorCarving
from motors.motor_b_mft_first import MotorBMFTFirst
from motors.motor_c_orchestrator import MotorCOrchestrator


@dataclass
class CrossoverPoint:
    """A single data point on the crossover curve."""
    mft_damage_pct: float
    mft_confidence: float

    # Carving metrics
    carving_recovery: float
    carving_correct: int
    carving_corrupt: int
    carving_false_positives: int
    carving_reads: int
    carving_efficiency: float
    carving_integrity: float

    # MFT-First metrics
    mft_recovery: float
    mft_correct: int
    mft_corrupt: int
    mft_false_positives: int
    mft_reads: int
    mft_efficiency: float
    mft_integrity: float

    # Motor C metrics
    motor_c_recovery: float
    motor_c_correct: int
    motor_c_corrupt: int
    motor_c_false_positives: int
    motor_c_reads: int
    motor_c_efficiency: float
    motor_c_integrity: float

    # Statistical analysis (if N > 1)
    n_repetitions: int = 1
    carving_recovery_ci_lower: float = 0.0
    carving_recovery_ci_upper: float = 0.0
    mft_recovery_ci_lower: float = 0.0
    mft_recovery_ci_upper: float = 0.0
    p_value: float = 1.0
    effect_size: float = 0.0

    # Which strategy wins
    optimal_strategy: str = "mft_first"
    delta_recovery: float = 0.0  # MFT - Carving (positive = MFT wins)

    def to_dict(self) -> Dict:
        return {
            "mft_damage_pct": self.mft_damage_pct,
            "mft_confidence": round(self.mft_confidence, 4),
            "carving": {
                "recovery": round(self.carving_recovery, 4),
                "correct": self.carving_correct,
                "corrupt": self.carving_corrupt,
                "false_positives": self.carving_false_positives,
                "reads": self.carving_reads,
                "efficiency": round(self.carving_efficiency, 4),
                "integrity": round(self.carving_integrity, 4),
            },
            "mft_first": {
                "recovery": round(self.mft_recovery, 4),
                "correct": self.mft_correct,
                "corrupt": self.mft_corrupt,
                "false_positives": self.mft_false_positives,
                "reads": self.mft_reads,
                "efficiency": round(self.mft_efficiency, 4),
                "integrity": round(self.mft_integrity, 4),
            },
            "motor_c": {
                "recovery": round(self.motor_c_recovery, 4),
                "correct": self.motor_c_correct,
                "corrupt": self.motor_c_corrupt,
                "false_positives": self.motor_c_false_positives,
                "reads": self.motor_c_reads,
                "efficiency": round(self.motor_c_efficiency, 4),
                "integrity": round(self.motor_c_integrity, 4),
            },
            "statistics": {
                "n_repetitions": self.n_repetitions,
                "carving_recovery_ci": [round(self.carving_recovery_ci_lower, 4),
                                        round(self.carving_recovery_ci_upper, 4)],
                "mft_recovery_ci": [round(self.mft_recovery_ci_lower, 4),
                                    round(self.mft_recovery_ci_upper, 4)],
                "p_value": round(self.p_value, 4),
                "effect_size_cohens_d": round(self.effect_size, 4),
            },
            "optimal_strategy": self.optimal_strategy,
            "delta_recovery_mft_minus_carving": round(self.delta_recovery, 4),
        }


@dataclass
class CrossoverResult:
    """Complete crossover curve result."""
    dataset: str
    timestamp: str
    points: List[CrossoverPoint] = field(default_factory=list)
    crossover_point: Optional[float] = None
    crossover_type: str = ""  # "gradual" or "abrupt"

    def find_crossover(self) -> Optional[float]:
        """Find the MFT damage % where Carving overtakes MFT-First."""
        for i in range(1, len(self.points)):
            prev = self.points[i - 1]
            curr = self.points[i]

            # Crossover: MFT was winning, now Carving is winning (or equal)
            if prev.delta_recovery > 0 and curr.delta_recovery <= 0:
                # Linear interpolation
                if prev.delta_recovery - curr.delta_recovery != 0:
                    frac = prev.delta_recovery / (prev.delta_recovery - curr.delta_recovery)
                    self.crossover_point = prev.mft_damage_pct + frac * (curr.mft_damage_pct - prev.mft_damage_pct)
                else:
                    self.crossover_point = curr.mft_damage_pct

                # Determine if abrupt or gradual
                if i > 0 and abs(prev.delta_recovery - curr.delta_recovery) > 0.3:
                    self.crossover_type = "abrupt"
                else:
                    self.crossover_type = "gradual"

                return self.crossover_point

        return None

    def to_dict(self) -> Dict:
        return {
            "dataset": self.dataset,
            "timestamp": self.timestamp,
            "crossover_point": round(self.crossover_point, 4) if self.crossover_point else None,
            "crossover_type": self.crossover_type,
            "points": [p.to_dict() for p in self.points],
        }


def compute_statistics(carving_recoveries: List[float],
                        mft_recoveries: List[float]) -> Dict:
    """
    Compute statistical analysis for a single crossover point.

    Returns:
      - 95% CI for each strategy
      - p-value (two-tailed t-test)
      - Effect size (Cohen's d)
    """
    import math

    n = len(carving_recoveries)
    if n < 2:
        return {
            "ci_lower_carving": 0.0, "ci_upper_carving": 0.0,
            "ci_lower_mft": 0.0, "ci_upper_mft": 0.0,
            "p_value": 1.0, "effect_size": 0.0,
        }

    # Mean and std for each
    mean_c = sum(carving_recoveries) / n
    mean_m = sum(mft_recoveries) / n

    var_c = sum((x - mean_c) ** 2 for x in carving_recoveries) / (n - 1) if n > 1 else 0
    var_m = sum((x - mean_m) ** 2 for x in mft_recoveries) / (n - 1) if n > 1 else 0

    std_c = math.sqrt(var_c)
    std_m = math.sqrt(var_m)

    # 95% CI (using t-distribution approximation for small n)
    # For n >= 30, use 1.96; for small n, use t-value
    t_values = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776, 10: 2.262,
                20: 2.093, 30: 2.042, 50: 2.009, 100: 1.984}
    if n in t_values:
        t = t_values[n]
    elif n < 2:
        t = 12.706
    elif n < 30:
        t = 2.776  # Conservative
    else:
        t = 1.96

    se_c = std_c / math.sqrt(n) if n > 0 else 0
    se_m = std_m / math.sqrt(n) if n > 0 else 0

    # Paired t-test
    diffs = [c - m for c, m in zip(carving_recoveries, mft_recoveries)]
    mean_diff = sum(diffs) / n
    var_diff = sum((d - mean_diff) ** 2 for d in diffs) / (n - 1) if n > 1 else 0
    se_diff = math.sqrt(var_diff / n) if n > 0 else 0

    if se_diff > 0:
        t_stat = mean_diff / se_diff
        # Approximate p-value (two-tailed)
        # For large |t|, p is very small
        p_value = 2.0 * (1.0 - _t_cdf_approx(abs(t_stat), n - 1))
        p_value = max(0.0, min(1.0, p_value))
    else:
        p_value = 1.0 if abs(mean_diff) < 0.001 else 0.0

    # Cohen's d
    pooled_std = math.sqrt((var_c + var_m) / 2) if (var_c + var_m) > 0 else 1.0
    cohens_d = (mean_m - mean_c) / pooled_std if pooled_std > 0 else 0.0

    return {
        "ci_lower_carving": mean_c - t * se_c,
        "ci_upper_carving": mean_c + t * se_c,
        "ci_lower_mft": mean_m - t * se_m,
        "ci_upper_mft": mean_m + t * se_m,
        "p_value": p_value,
        "effect_size": cohens_d,
    }


def _t_cdf_approx(t: float, df: int) -> float:
    """Approximate CDF of t-distribution using normal approximation."""
    import math
    if df >= 30:
        # Normal approximation
        return 0.5 * (1 + math.erf(t / math.sqrt(2)))
    else:
        # Simple approximation
        x = (t + 0.044715 * t**3) / math.sqrt(1 + t**2 / df)
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def run_crossover_curve(
    image: bytes,
    manifest: Dict,
    seed: int = 42,
    step: float = 0.05,
    max_damage: float = 1.0,
    n_repetitions: int = 1,
    read_budget: int = 0,
) -> CrossoverResult:
    """
    Run the crossover curve experiment.

    For each damage level (0%, 5%, 10%, ..., 100%):
      1. Apply MFT partial deletion
      2. Run Carving, MFT-First, Motor C
      3. Judge results
      4. Record data point
      5. If n_repetitions > 1, repeat and compute statistics

    Returns a CrossoverResult with all data points.
    """
    dataset_id = manifest.get("serial", "unknown")
    result = CrossoverResult(
        dataset=dataset_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    motor_carving = MotorCarving()
    motor_mft = MotorBMFTFirst()
    motor_c = MotorCOrchestrator()
    judge = RecoveryJudge(manifest)

    # Generate damage levels
    damage_levels = []
    d = 0.0
    while d <= max_damage + 0.001:
        damage_levels.append(round(d, 2))
        d += step

    print(f"\n{'='*90}")
    print(f"STRATEGY CROSSOVER CURVE — {dataset_id}")
    print(f"{'='*90}")
    print(f"  Damage levels: {len(damage_levels)}")
    print(f"  Step: {step:.0%}")
    print(f"  Repetitions per point: {n_repetitions}")
    print(f"{'─'*90}")
    print(f"  {'Damage':>8s} │ {'Conf':>6s} │ {'Carving':>10s} │ {'MFT-1st':>10s} │ "
          f"{'Motor C':>10s} │ {'Δ Rec':>8s} │ {'Winner':>10s} │ {'p-val':>8s} │ {'d':>6s}")
    print(f"{'─'*90}")

    for damage_pct in damage_levels:
        carving_recoveries = []
        mft_recoveries = []
        motor_c_recoveries = []

        # Aggregated metrics (averaged over repetitions)
        sum_carving = None
        sum_mft = None
        sum_motor_c = None

        for rep in range(n_repetitions):
            # Apply corruption
            rep_seed = seed + rep * 1000  # Different seed per repetition
            if damage_pct == 0.0:
                corrupted_image = image
                corruption_meta = {}
            else:
                model = MFTPartialDeleteModel(seed=rep_seed)
                image_copy = bytearray(image)
                corr_result = model.apply(image_copy, manifest, severity=damage_pct)
                corrupted_image = corr_result.corrupted_image
                corruption_meta = corr_result.manifest_corruption

            # Calculate MFT confidence
            confidence = motor_c.compute_mft_confidence(corrupted_image, manifest)

            # ─── Carving ──────────────────────────────────────────────
            result_carving = motor_carving.recover(
                corrupted_image, manifest,
                read_budget=read_budget,
                corruption_metadata=corruption_meta,
            )
            metrics_carving = judge.judge(
                recovered_files=[{"name": f.name, "sha256": f.sha256,
                                  "size": f.size, "is_directory": f.is_directory}
                                 for f in result_carving.recovered_files],
                read_count=result_carving.read_count,
                sectors_wasted=result_carving.sectors_wasted,
                time_to_first_file=result_carving.time_to_first_file,
                mft_entries_parsed=result_carving.mft_entries_parsed,
            )

            # ─── MFT-First ───────────────────────────────────────────
            result_mft = motor_mft.recover(
                corrupted_image, manifest,
                read_budget=read_budget,
                corruption_metadata=corruption_meta,
            )
            metrics_mft = judge.judge(
                recovered_files=[{"name": f.name, "sha256": f.sha256,
                                  "size": f.size, "is_directory": f.is_directory}
                                 for f in result_mft.recovered_files],
                read_count=result_mft.read_count,
                sectors_wasted=result_mft.sectors_wasted,
                time_to_first_file=result_mft.time_to_first_file,
                mft_entries_parsed=result_mft.mft_entries_parsed,
            )

            # ─── Motor C ─────────────────────────────────────────────
            result_motor_c = motor_c.recover(
                corrupted_image, manifest,
                read_budget=read_budget,
                corruption_metadata=corruption_meta,
            )
            metrics_motor_c = judge.judge(
                recovered_files=[{"name": f.name, "sha256": f.sha256,
                                  "size": f.size, "is_directory": f.is_directory}
                                 for f in result_motor_c.recovered_files],
                read_count=result_motor_c.read_count,
                sectors_wasted=result_motor_c.sectors_wasted,
                time_to_first_file=result_motor_c.time_to_first_file,
                mft_entries_parsed=result_motor_c.mft_entries_parsed,
            )

            # Collect recovery rates
            carving_recoveries.append(metrics_carving.recovery_rate())
            mft_recoveries.append(metrics_mft.recovery_rate())
            motor_c_recoveries.append(metrics_motor_c.recovery_rate())

            # Accumulate metrics (use last repetition for details)
            if rep == n_repetitions - 1:
                sum_carving = metrics_carving
                sum_mft = metrics_mft
                sum_motor_c = metrics_motor_c

        # Compute statistics
        stats = compute_statistics(carving_recoveries, mft_recoveries)

        # Determine winner
        avg_carving = sum(carving_recoveries) / len(carving_recoveries)
        avg_mft = sum(mft_recoveries) / len(mft_recoveries)
        avg_motor_c = sum(motor_c_recoveries) / len(motor_c_recoveries)

        delta = avg_mft - avg_carving

        if delta > 0.05:
            winner = "MFT-First"
        elif delta < -0.05:
            winner = "Carving"
        else:
            winner = "Tie"

        # Create data point
        point = CrossoverPoint(
            mft_damage_pct=damage_pct,
            mft_confidence=confidence,
            carving_recovery=avg_carving,
            carving_correct=sum_carving.files_correct_checksum,
            carving_corrupt=sum_carving.files_corrupt,
            carving_false_positives=sum_carving.false_positives,
            carving_reads=sum_carving.read_count,
            carving_efficiency=sum_carving.read_efficiency(),
            carving_integrity=sum_carving.integrity_score,
            mft_recovery=avg_mft,
            mft_correct=sum_mft.files_correct_checksum,
            mft_corrupt=sum_mft.files_corrupt,
            mft_false_positives=sum_mft.false_positives,
            mft_reads=sum_mft.read_count,
            mft_efficiency=sum_mft.read_efficiency(),
            mft_integrity=sum_mft.integrity_score,
            motor_c_recovery=avg_motor_c,
            motor_c_correct=sum_motor_c.files_correct_checksum,
            motor_c_corrupt=sum_motor_c.files_corrupt,
            motor_c_false_positives=sum_motor_c.false_positives,
            motor_c_reads=sum_motor_c.read_count,
            motor_c_efficiency=sum_motor_c.read_efficiency(),
            motor_c_integrity=sum_motor_c.integrity_score,
            n_repetitions=n_repetitions,
            carving_recovery_ci_lower=stats["ci_lower_carving"],
            carving_recovery_ci_upper=stats["ci_upper_carving"],
            mft_recovery_ci_lower=stats["ci_lower_mft"],
            mft_recovery_ci_upper=stats["ci_upper_mft"],
            p_value=stats["p_value"],
            effect_size=stats["effect_size"],
            optimal_strategy="mft_first" if delta > 0 else "carving",
            delta_recovery=delta,
        )
        result.points.append(point)

        # Print row
        print(f"  {damage_pct:>7.0%} │ {confidence:>5.1%} │ "
              f"{avg_carving:>9.1%} │ {avg_mft:>9.1%} │ "
              f"{avg_motor_c:>9.1%} │ "
              f"{delta:>+7.1%} │ {winner:>10s} │ "
              f"{stats['p_value']:>7.3f} │ {stats['effect_size']:>+5.2f}")

    # Find crossover
    crossover = result.find_crossover()
    print(f"{'─'*90}")
    if crossover is not None:
        print(f"  ★ CROSSOVER POINT: {crossover:.1%} MFT damage")
        print(f"    Type: {result.crossover_type}")
        print(f"    Below this point: MFT-First wins")
        print(f"    Above this point: Carving wins")
    else:
        # Check if one strategy always wins
        if all(p.delta_recovery > 0 for p in result.points):
            print(f"  No crossover found — MFT-First wins at ALL damage levels")
        elif all(p.delta_recovery < 0 for p in result.points):
            print(f"  No crossover found — Carving wins at ALL damage levels")
        else:
            print(f"  Mixed results — no clear crossover point")

    print(f"{'='*90}")

    return result


def visualize_crossover(result: CrossoverResult,
                         output_path: Optional[Path] = None):
    """Generate the crossover curve visualization."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.font_manager as fm
        import numpy as np
    except ImportError:
        print("matplotlib not available for visualization")
        return

    # Font setup
    fm.fontManager.addfont('/usr/share/fonts/truetype/chinese/SarasaMonoSC-Regular.ttf')
    fm.fontManager.addfont('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    plt.rcParams['font.sans-serif'] = ['Sarasa Mono SC', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False

    points = result.points
    if not points:
        return

    damage = [p.mft_damage_pct * 100 for p in points]
    carving_rec = [p.carving_recovery * 100 for p in points]
    mft_rec = [p.mft_recovery * 100 for p in points]
    motor_c_rec = [p.motor_c_recovery * 100 for p in points]
    delta = [p.delta_recovery * 100 for p in points]
    p_values = [p.p_value for p in points]
    effect_sizes = [p.effect_size for p in points]

    fig, axes = plt.subplots(2, 2, figsize=(16, 12), constrained_layout=True)
    fig.patch.set_facecolor('#1a1a2e')
    fig.suptitle('Strategy Crossover Curve — H2 Test', fontsize=16,
                 color='white', fontweight='bold', y=0.98)

    # ─── Plot 1: Recovery Rate vs MFT Damage (THE MAIN PLOT) ──────────
    ax1 = axes[0, 0]
    ax1.set_facecolor('#16213e')
    ax1.plot(damage, carving_rec, 'o-', color='#e74c3c',
             label='Carving (Signature-Only)', linewidth=2.5, markersize=5)
    ax1.plot(damage, mft_rec, 's-', color='#2ecc71',
             label='MFT-First', linewidth=2.5, markersize=5)
    ax1.plot(damage, motor_c_rec, '^-', color='#3498db',
             label='Motor C (Adaptive)', linewidth=2.5, markersize=5)

    # Mark crossover point
    if result.crossover_point is not None:
        ax1.axvline(x=result.crossover_point * 100, color='#f39c12',
                    linestyle='--', linewidth=2.5, alpha=0.9,
                    label=f'Crossover ({result.crossover_point:.0%})')

        # Shade regions
        ax1.axvspan(0, result.crossover_point * 100, alpha=0.08, color='#2ecc71')
        ax1.axvspan(result.crossover_point * 100, 100, alpha=0.08, color='#e74c3c')

        # Add labels
        ax1.text(result.crossover_point * 50, 85, 'MFT-First\nwins',
                ha='center', fontsize=11, color='#2ecc71', alpha=0.7, fontweight='bold')
        ax1.text((result.crossover_point * 100 + 100) / 2, 85, 'Carving\nwins',
                ha='center', fontsize=11, color='#e74c3c', alpha=0.7, fontweight='bold')

    ax1.set_xlabel('MFT Damage (%)', fontsize=11, color='white')
    ax1.set_ylabel('Recovery Rate (%)', fontsize=11, color='white')
    ax1.set_title('Recovery Rate vs MFT Damage', fontsize=13, color='white', fontweight='bold')
    ax1.legend(fontsize=9, facecolor='#1a1a2e', edgecolor='#444', labelcolor='white')
    ax1.tick_params(colors='white')
    ax1.grid(True, alpha=0.2, color='white')
    ax1.set_ylim(-5, 105)

    # ─── Plot 2: Delta Recovery (MFT - Carving) ───────────────────────
    ax2 = axes[0, 1]
    ax2.set_facecolor('#16213e')
    bar_width = (damage[1] - damage[0]) * 0.8 if len(damage) > 1 else 4.0
    colors = ['#2ecc71' if d > 0 else '#e74c3c' for d in delta]
    ax2.bar(damage, delta, color=colors, width=bar_width, alpha=0.8)
    ax2.axhline(y=0, color='white', linewidth=1, alpha=0.5)

    if result.crossover_point is not None:
        ax2.axvline(x=result.crossover_point * 100, color='#f39c12',
                    linestyle='--', linewidth=2, alpha=0.9)

    ax2.set_xlabel('MFT Damage (%)', fontsize=11, color='white')
    ax2.set_ylabel('Δ Recovery (MFT - Carving) %', fontsize=11, color='white')
    ax2.set_title('Strategy Advantage by Damage Level', fontsize=13, color='white', fontweight='bold')
    ax2.tick_params(colors='white')
    ax2.grid(True, alpha=0.2, color='white')

    # ─── Plot 3: Statistical Significance ─────────────────────────────
    ax3 = axes[1, 0]
    ax3.set_facecolor('#16213e')

    # Color by significance
    sig_colors = ['#e74c3c' if p < 0.05 else '#95a5a6' for p in p_values]
    ax3.bar(damage, [-np.log10(p + 1e-10) for p in p_values],
            color=sig_colors, width=bar_width, alpha=0.8)
    ax3.axhline(y=-np.log10(0.05), color='#f39c12', linestyle='--',
                linewidth=2, alpha=0.8, label='p = 0.05')
    ax3.axhline(y=-np.log10(0.01), color='#e74c3c', linestyle='--',
                linewidth=1.5, alpha=0.6, label='p = 0.01')

    ax3.set_xlabel('MFT Damage (%)', fontsize=11, color='white')
    ax3.set_ylabel('-log₁₀(p-value)', fontsize=11, color='white')
    ax3.set_title('Statistical Significance (Carving vs MFT-First)', fontsize=13,
                  color='white', fontweight='bold')
    ax3.legend(fontsize=9, facecolor='#1a1a2e', edgecolor='#444', labelcolor='white')
    ax3.tick_params(colors='white')
    ax3.grid(True, alpha=0.2, color='white')

    # ─── Plot 4: Effect Size ──────────────────────────────────────────
    ax4 = axes[1, 1]
    ax4.set_facecolor('#16213e')

    # Color by magnitude
    es_colors = []
    for d in effect_sizes:
        if abs(d) > 0.8:
            es_colors.append('#e74c3c' if d < 0 else '#2ecc71')
        elif abs(d) > 0.5:
            es_colors.append('#f39c12')
        else:
            es_colors.append('#95a5a6')

    ax4.bar(damage, effect_sizes, color=es_colors, width=bar_width, alpha=0.8)
    ax4.axhline(y=0, color='white', linewidth=1, alpha=0.5)
    ax4.axhline(y=0.8, color='#2ecc71', linestyle='--', alpha=0.5, label='Large (d=0.8)')
    ax4.axhline(y=-0.8, color='#e74c3c', linestyle='--', alpha=0.5)
    ax4.axhline(y=0.5, color='#f39c12', linestyle='--', alpha=0.5, label='Medium (d=0.5)')
    ax4.axhline(y=-0.5, color='#f39c12', linestyle='--', alpha=0.5)

    if result.crossover_point is not None:
        ax4.axvline(x=result.crossover_point * 100, color='#f39c12',
                    linestyle='--', linewidth=2, alpha=0.9)

    ax4.set_xlabel('MFT Damage (%)', fontsize=11, color='white')
    ax4.set_ylabel("Cohen's d (MFT - Carving)", fontsize=11, color='white')
    ax4.set_title("Effect Size (Cohen's d)", fontsize=13, color='white', fontweight='bold')
    ax4.legend(fontsize=9, facecolor='#1a1a2e', edgecolor='#444', labelcolor='white')
    ax4.tick_params(colors='white')
    ax4.grid(True, alpha=0.2, color='white')

    # ─── Save ─────────────────────────────────────────────────────────
    if output_path is None:
        output_path = PROJECT_ROOT / "output" / "results" / "crossover_curve.png"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, facecolor='#1a1a2e', edgecolor='none')
    plt.close()

    print(f"\n  Crossover curve visualization: {output_path}")
    return output_path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="RecoveryLab Strategy Crossover Curve")
    parser.add_argument("--dataset-dir", type=str, default="output/datasets",
                       help="Directory containing dataset images")
    parser.add_argument("--step", type=float, default=0.05,
                       help="Damage step (default 0.05 = 5%%)")
    parser.add_argument("--max-damage", type=float, default=1.0,
                       help="Max damage (default 1.0)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--repetitions", type=int, default=5,
                       help="Number of repetitions per point (for statistics)")
    parser.add_argument("--output-dir", type=str, default=None)

    args = parser.parse_args()

    # Find first dataset
    dataset_dir = PROJECT_ROOT / args.dataset_dir
    img_path = None
    manifest_path = None

    for f in sorted(dataset_dir.glob("dataset_*.img")):
        m = f.parent / f.name.replace(".img", "_manifest.json")
        if m.exists():
            img_path = f
            manifest_path = m
            break

    if not img_path:
        print(f"No datasets found in {dataset_dir}")
        sys.exit(1)

    print(f"Dataset: {img_path.name}")

    with open(img_path, 'rb') as f:
        image = f.read()
    manifest = load_manifest(manifest_path)

    # Run crossover curve
    result = run_crossover_curve(
        image, manifest,
        seed=args.seed,
        step=args.step,
        max_damage=args.max_damage,
        n_repetitions=args.repetitions,
    )

    # Save results
    output_dir = Path(args.output_dir) if args.output_dir else PROJECT_ROOT / "output" / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "crossover_curve.json"
    with open(json_path, 'w') as f:
        json.dump(result.to_dict(), f, indent=2)
    print(f"\n  Results saved: {json_path}")

    # Visualize
    png_path = output_dir / "crossover_curve.png"
    visualize_crossover(result, png_path)

    # Print summary
    print(f"\n{'='*90}")
    print(f"CROSSOVER CURVE SUMMARY")
    print(f"{'='*90}")
    if result.crossover_point is not None:
        print(f"  ★ Crossover point: {result.crossover_point:.1%} MFT damage")
        print(f"    Type: {result.crossover_type}")
        print(f"    Below: MFT-First is optimal")
        print(f"    Above: Carving is optimal")
    else:
        all_mft = all(p.delta_recovery > 0 for p in result.points)
        all_carving = all(p.delta_recovery < 0 for p in result.points)
        if all_mft:
            print(f"  No crossover — MFT-First wins at ALL damage levels")
        elif all_carving:
            print(f"  No crossover — Carving wins at ALL damage levels")
        else:
            print(f"  Mixed results — no clear crossover")

    # Find the crossover point details
    for p in result.points:
        if abs(p.delta_recovery) < 0.05:
            print(f"\n  Near-crossover at {p.mft_damage_pct:.0%} damage:")
            print(f"    Carving: {p.carving_recovery:.1%}")
            print(f"    MFT-First: {p.mft_recovery:.1%}")
            print(f"    Motor C: {p.motor_c_recovery:.1%}")
            print(f"    Δ: {p.delta_recovery:+.1%}")
            print(f"    p-value: {p.p_value:.3f}")
            print(f"    Cohen's d: {p.effect_size:+.2f}")

    print(f"{'='*90}")


if __name__ == "__main__":
    main()
