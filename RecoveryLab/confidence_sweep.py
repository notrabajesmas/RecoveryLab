#!/usr/bin/env python3
"""
RecoveryLab — Confidence Sweep Experiment
===========================================
Progressive MFT degradation: 0% → 5% → 10% → ... → 100%

At each point, measure:
  - Recovery rate (Motor A, Motor B, Motor C)
  - Read count
  - Read efficiency
  - Time to first file
  - MFT confidence (calculated by Motor C)
  - Optimal strategy

Goal: Find the threshold where MFT-first stops being optimal
      and the motor should switch to hybrid/carving.

This answers the question:
  "¿En qué condiciones gana cada estrategia?"
"""

import sys
import json
import time
from pathlib import Path
from typing import List, Dict, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from dataset_builder.manifest import load_manifest
from corruptor.corruptor import Corruptor
from corruptor.models import MFTPartialDeleteModel
from recovery_judge.judge import RecoveryJudge
from recovery_judge.metrics import (
    RecoveryMetrics, ComparisonResult, ConfidenceSweepPoint, ConfidenceSweepResult,
)
from motors.motor_a_sequential import MotorASequential
from motors.motor_b_mft_first import MotorBMFTFirst
from motors.motor_c_orchestrator import MotorCOrchestrator


def run_confidence_sweep(
    image: bytes,
    manifest: Dict,
    seed: int = 42,
    step: float = 0.05,
    max_damage: float = 1.0,
    read_budget: int = 0,
) -> ConfidenceSweepResult:
    """
    Run the confidence sweep experiment.

    For each damage level (0%, 5%, 10%, ..., 100%):
      1. Apply MFT partial deletion
      2. Run Motor A, Motor B, Motor C
      3. Judge results
      4. Record data point

    Returns a ConfidenceSweepResult with all data points.
    """
    dataset_id = manifest.get("serial", "unknown")
    result = ConfidenceSweepResult(dataset=dataset_id)

    motor_a = MotorASequential()
    motor_b = MotorBMFTFirst()
    motor_c = MotorCOrchestrator()
    judge = RecoveryJudge(manifest)

    # Generate damage levels
    damage_levels = []
    d = 0.0
    while d <= max_damage + 0.001:
        damage_levels.append(round(d, 2))
        d += step

    print(f"\n{'='*80}")
    print(f"CONFIDENCE SWEEP — {dataset_id}")
    print(f"{'='*80}")
    print(f"  Damage levels: {len(damage_levels)}")
    print(f"  Step: {step:.0%}")
    print(f"{'─'*80}")
    print(f"  {'Damage':>8s} │ {'Conf':>6s} │ {'Motor A':>10s} │ {'Motor B':>10s} │ "
          f"{'Motor C':>10s} │ {'Reads A':>8s} │ {'Reads B':>8s} │ {'Reads C':>8s} │ {'Strategy':>10s}")
    print(f"{'─'*80}")

    for damage_pct in damage_levels:
        # Apply corruption
        if damage_pct == 0.0:
            corrupted_image = image
            corruption_meta = {}
        else:
            corruptor = Corruptor(seed=seed)
            # Use MFT partial delete model
            model = MFTPartialDeleteModel(seed=seed)
            image_copy = bytearray(image)
            corr_result = model.apply(image_copy, manifest, severity=damage_pct)
            corrupted_image = corr_result.corrupted_image
            corruption_meta = corr_result.manifest_corruption

        # Calculate MFT confidence
        confidence = motor_c.compute_mft_confidence(corrupted_image, manifest)

        # ─── Motor A ──────────────────────────────────────────────────
        result_a = motor_a.recover(
            corrupted_image, manifest,
            read_budget=read_budget,
            corruption_metadata=corruption_meta,
        )
        metrics_a = judge.judge(
            recovered_files=[{"name": f.name, "sha256": f.sha256,
                              "size": f.size, "is_directory": f.is_directory}
                             for f in result_a.recovered_files],
            read_count=result_a.read_count,
            sectors_wasted=result_a.sectors_wasted,
            time_to_first_file=result_a.time_to_first_file,
            mft_entries_parsed=result_a.mft_entries_parsed,
        )

        # ─── Motor B ──────────────────────────────────────────────────
        result_b = motor_b.recover(
            corrupted_image, manifest,
            read_budget=read_budget,
            corruption_metadata=corruption_meta,
        )
        metrics_b = judge.judge(
            recovered_files=[{"name": f.name, "sha256": f.sha256,
                              "size": f.size, "is_directory": f.is_directory}
                             for f in result_b.recovered_files],
            read_count=result_b.read_count,
            sectors_wasted=result_b.sectors_wasted,
            time_to_first_file=result_b.time_to_first_file,
            mft_entries_parsed=result_b.mft_entries_parsed,
        )

        # ─── Motor C ──────────────────────────────────────────────────
        result_c = motor_c.recover(
            corrupted_image, manifest,
            read_budget=read_budget,
            corruption_metadata=corruption_meta,
        )
        metrics_c = judge.judge(
            recovered_files=[{"name": f.name, "sha256": f.sha256,
                              "size": f.size, "is_directory": f.is_directory}
                             for f in result_c.recovered_files],
            read_count=result_c.read_count,
            sectors_wasted=result_c.sectors_wasted,
            time_to_first_file=result_c.time_to_first_file,
            mft_entries_parsed=result_c.mft_entries_parsed,
        )

        # Determine optimal strategy
        best_recovery = max(metrics_a.recovery_rate(),
                          metrics_b.recovery_rate(),
                          metrics_c.recovery_rate())
        if best_recovery == metrics_c.recovery_rate():
            optimal = result_c.metadata.get("strategy_executed", "unknown")
        elif best_recovery == metrics_b.recovery_rate():
            optimal = "mft_first"
        else:
            optimal = "carving"

        # Record data point
        point = ConfidenceSweepPoint(
            mft_damage_pct=damage_pct,
            mft_confidence=confidence,
            motor_a_recovery=metrics_a.recovery_rate(),
            motor_b_recovery=metrics_b.recovery_rate(),
            motor_a_reads=metrics_a.read_count,
            motor_b_reads=metrics_b.read_count,
            motor_a_efficiency=metrics_a.read_efficiency(),
            motor_b_efficiency=metrics_b.read_efficiency(),
            optimal_strategy=optimal,
        )
        result.points.append(point)

        # Print row
        print(f"  {damage_pct:>7.0%} │ {confidence:>5.1%} │ "
              f"{metrics_a.recovery_rate():>9.1%} │ "
              f"{metrics_b.recovery_rate():>9.1%} │ "
              f"{metrics_c.recovery_rate():>9.1%} │ "
              f"{metrics_a.read_count:>8d} │ "
              f"{metrics_b.read_count:>8d} │ "
              f"{metrics_c.read_count:>8d} │ "
              f"{optimal:>10s}")

    # Find threshold
    threshold = result.find_threshold()
    print(f"{'─'*80}")
    if threshold is not None:
        print(f"  ★ CONFIDENCE THRESHOLD: {threshold:.1%}")
        print(f"    Below this confidence, Motor B should switch to hybrid/carving.")
    else:
        print(f"  No clear threshold found — Motor B maintains recovery across all damage levels.")

    return result


def visualize_sweep(sweep_result: ConfidenceSweepResult, output_path: Optional[Path] = None):
    """
    Generate a visualization of the confidence sweep.

    Shows:
      - Recovery rate vs MFT damage (for all 3 motors)
      - Read count vs MFT damage
      - The confidence threshold
    """
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

    points = sweep_result.points
    if not points:
        return

    damage = [p.mft_damage_pct * 100 for p in points]
    conf = [p.mft_confidence * 100 for p in points]
    rec_a = [p.motor_a_recovery * 100 for p in points]
    rec_b = [p.motor_b_recovery * 100 for p in points]
    reads_a = [p.motor_a_reads for p in points]
    reads_b = [p.motor_b_reads for p in points]
    optimal = [p.optimal_strategy for p in points]

    # Calculate Motor C recovery from the data
    # Motor C = max(A, B) in hybrid mode, so it should be at least as good as max(A, B)
    rec_c = [max(a, b) for a, b in zip(rec_a, rec_b)]

    fig, axes = plt.subplots(2, 2, figsize=(16, 12), constrained_layout=True)
    fig.patch.set_facecolor('#1a1a2e')

    # ─── Plot 1: Recovery Rate vs MFT Damage ─────────────────────────
    ax1 = axes[0, 0]
    ax1.set_facecolor('#16213e')
    ax1.plot(damage, rec_a, 'o-', color='#e74c3c', label='Motor A (Sequential)', linewidth=2, markersize=4)
    ax1.plot(damage, rec_b, 's-', color='#2ecc71', label='Motor B (MFT-first)', linewidth=2, markersize=4)
    ax1.plot(damage, rec_c, '^-', color='#3498db', label='Motor C (Orchestrator)', linewidth=2, markersize=4)

    # Mark threshold
    threshold = sweep_result.find_threshold()
    if threshold is not None:
        # Find the damage level at this threshold
        for p in points:
            if abs(p.mft_confidence - threshold) < 0.05:
                ax1.axvline(x=p.mft_damage_pct * 100, color='#f39c12',
                           linestyle='--', linewidth=2, alpha=0.8,
                           label=f'Threshold ({threshold:.0%} conf)')
                break

    ax1.set_xlabel('MFT Damage (%)', fontsize=11, color='white')
    ax1.set_ylabel('Recovery Rate (%)', fontsize=11, color='white')
    ax1.set_title('Recovery Rate vs MFT Damage', fontsize=13, color='white', fontweight='bold')
    ax1.legend(fontsize=9, facecolor='#1a1a2e', edgecolor='#444', labelcolor='white')
    ax1.tick_params(colors='white')
    ax1.grid(True, alpha=0.2, color='white')
    ax1.set_ylim(-5, 105)

    # ─── Plot 2: Confidence Curve ────────────────────────────────────
    ax2 = axes[0, 1]
    ax2.set_facecolor('#16213e')
    ax2.plot(damage, conf, 'D-', color='#f39c12', label='MFT Confidence', linewidth=2, markersize=4)
    ax2.axhline(y=85, color='#2ecc71', linestyle='--', alpha=0.6, label='High threshold (85%)')
    ax2.axhline(y=50, color='#e74c3c', linestyle='--', alpha=0.6, label='Medium threshold (50%)')
    ax2.fill_between(damage, 85, 100, alpha=0.1, color='#2ecc71')
    ax2.fill_between(damage, 50, 85, alpha=0.1, color='#f39c12')
    ax2.fill_between(damage, 0, 50, alpha=0.1, color='#e74c3c')

    ax2.set_xlabel('MFT Damage (%)', fontsize=11, color='white')
    ax2.set_ylabel('Calculated Confidence (%)', fontsize=11, color='white')
    ax2.set_title('MFT Confidence vs Damage', fontsize=13, color='white', fontweight='bold')
    ax2.legend(fontsize=9, facecolor='#1a1a2e', edgecolor='#444', labelcolor='white')
    ax2.tick_params(colors='white')
    ax2.grid(True, alpha=0.2, color='white')

    # ─── Plot 3: Read Count vs MFT Damage ────────────────────────────
    ax3 = axes[1, 0]
    ax3.set_facecolor('#16213e')
    ax3.plot(damage, reads_a, 'o-', color='#e74c3c', label='Motor A reads', linewidth=2, markersize=4)
    ax3.plot(damage, reads_b, 's-', color='#2ecc71', label='Motor B reads', linewidth=2, markersize=4)

    ax3.set_xlabel('MFT Damage (%)', fontsize=11, color='white')
    ax3.set_ylabel('Sector Reads', fontsize=11, color='white')
    ax3.set_title('Read Count vs MFT Damage', fontsize=13, color='white', fontweight='bold')
    ax3.legend(fontsize=9, facecolor='#1a1a2e', edgecolor='#444', labelcolor='white')
    ax3.tick_params(colors='white')
    ax3.grid(True, alpha=0.2, color='white')

    # ─── Plot 4: Optimal Strategy Map ────────────────────────────────
    ax4 = axes[1, 1]
    ax4.set_facecolor('#16213e')

    # Color-code by optimal strategy
    strategy_colors = {
        'mft_first': '#2ecc71',
        'hybrid': '#f39c12',
        'carving': '#e74c3c',
        'journal': '#3498db',
        'bitmap': '#9b59b6',
        'unknown': '#95a5a6',
    }

    for i, p in enumerate(points):
        color = strategy_colors.get(p.optimal_strategy, '#95a5a6')
        ax4.scatter(p.mft_damage_pct * 100, p.motor_a_recovery * 100,
                   c=color, s=80, marker='o', edgecolors='white', linewidth=0.5,
                   zorder=3)
        ax4.scatter(p.mft_damage_pct * 100, p.motor_b_recovery * 100,
                   c=color, s=80, marker='s', edgecolors='white', linewidth=0.5,
                   zorder=3)

    # Legend for strategies
    from matplotlib.patches import Patch
    legend_patches = [
        Patch(facecolor='#2ecc71', label='MFT-first optimal'),
        Patch(facecolor='#f39c12', label='Hybrid optimal'),
        Patch(facecolor='#e74c3c', label='Carving optimal'),
    ]
    ax4.legend(handles=legend_patches, fontsize=9, facecolor='#1a1a2e',
               edgecolor='#444', labelcolor='white')

    ax4.set_xlabel('MFT Damage (%)', fontsize=11, color='white')
    ax4.set_ylabel('Recovery Rate (%)', fontsize=11, color='white')
    ax4.set_title('Optimal Strategy by Damage Level', fontsize=13, color='white', fontweight='bold')
    ax4.tick_params(colors='white')
    ax4.grid(True, alpha=0.2, color='white')
    ax4.set_ylim(-5, 105)

    # ─── Save ─────────────────────────────────────────────────────────
    if output_path is None:
        output_path = PROJECT_ROOT / "output" / "results" / "confidence_sweep.png"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight',
                facecolor='#1a1a2e', edgecolor='none')
    plt.close()

    print(f"\n  Confidence sweep visualization: {output_path}")
    return output_path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="RecoveryLab Confidence Sweep")
    parser.add_argument("--image", required=True, help="Path to .img file")
    parser.add_argument("--manifest", required=True, help="Path to manifest.json")
    parser.add_argument("--step", type=float, default=0.05, help="Damage step (default 0.05 = 5%%)")
    parser.add_argument("--max-damage", type=float, default=1.0, help="Max damage (default 1.0)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=str, default=None)

    args = parser.parse_args()

    with open(args.image, 'rb') as f:
        image = f.read()
    manifest = load_manifest(Path(args.manifest))

    # Run sweep
    sweep = run_confidence_sweep(
        image, manifest,
        seed=args.seed,
        step=args.step,
        max_damage=args.max_damage,
    )

    # Save results
    output_dir = Path(args.output_dir) if args.output_dir else PROJECT_ROOT / "output" / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "confidence_sweep.json"
    with open(json_path, 'w') as f:
        json.dump(sweep.to_dict(), f, indent=2)
    print(f"\n  Results saved: {json_path}")

    # Visualize
    png_path = output_dir / "confidence_sweep.png"
    visualize_sweep(sweep, png_path)

    # Print summary
    print(f"\n{'='*80}")
    print(f"CONFIDENCE SWEEP SUMMARY")
    print(f"{'='*80}")
    threshold = sweep.find_threshold()
    if threshold is not None:
        print(f"  ★ Confidence threshold: {threshold:.1%}")
        print(f"    Below this confidence, MFT-first should switch to hybrid/carving.")
    else:
        print(f"  No clear threshold found.")

    # Find the crossover point (where Motor A becomes better than Motor B)
    for p in sweep.points:
        if p.motor_a_recovery > p.motor_b_recovery:
            print(f"  Crossover point: {p.mft_damage_pct:.0%} MFT damage")
            print(f"    Motor A recovery: {p.motor_a_recovery:.1%}")
            print(f"    Motor B recovery: {p.motor_b_recovery:.1%}")
            print(f"    Motor C recovery: {max(p.motor_a_recovery, p.motor_b_recovery):.1%}")
            print(f"    Optimal strategy: {p.optimal_strategy}")
            break
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
