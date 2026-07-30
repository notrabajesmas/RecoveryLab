#!/usr/bin/env python3
"""
RecoveryLab — BLOCKER-001 Validation Test
============================================
Test the Motor Carving against a real NTFS image.

This is the test that BLOCKER-001 demands: can we recover files
using ONLY file signatures, without EVER reading the MFT?

Success criteria:
  - Motor Carving recovers files from a healthy image
  - Motor Carving NEVER reads MFT (mft_entries_parsed = 0)
  - We can compare Carving vs MFT-First (genuinely different strategies)
"""

import sys
import os
import json
import hashlib

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from motors.motor_carving import MotorCarving
from motors.motor_b_mft_first import MotorBMFTFirst
from motors.motor_a_sequential import MotorASequential
from recovery_judge.judge import RecoveryJudge
from dataset_builder.manifest import load_manifest
from strategy_profiles import (
    STRATEGY_CARVING, STRATEGY_MFT_ONLY, STRATEGY_MFT_SEQUENTIAL,
    validate_comparison, print_strategy_comparison_table
)


def main():
    print("=" * 70)
    print("BLOCKER-001 VALIDATION TEST")
    print("Can Motor Carving recover files WITHOUT MFT?")
    print("=" * 70)

    # Find a dataset
    dataset_dir = os.path.join(os.path.dirname(__file__), "output", "datasets")
    if not os.path.exists(dataset_dir):
        dataset_dir = os.path.join(os.path.dirname(__file__), "datasets", "ntfs", "healthy")

    # Find first available dataset
    img_path = None
    manifest_path = None

    for f in sorted(os.listdir(dataset_dir)):
        if f.endswith(".img"):
            img_path = os.path.join(dataset_dir, f)
            manifest_name = f.replace(".img", "_manifest.json")
            manifest_path = os.path.join(dataset_dir, manifest_name)
            if os.path.exists(manifest_path):
                break

    if not img_path or not os.path.exists(img_path):
        print(f"\nERROR: No dataset found in {dataset_dir}")
        print("Run dataset builder first: python -m dataset_builder.builder")
        return

    print(f"\nDataset: {os.path.basename(img_path)}")
    print(f"Manifest: {os.path.basename(manifest_path)}")

    # Load image and manifest
    with open(img_path, 'rb') as f:
        image = f.read()
    manifest = load_manifest(manifest_path)

    print(f"Image size: {len(image):,} bytes")
    print(f"Total clusters: {manifest.get('total_clusters', 'N/A')}")
    print(f"Cluster size: {manifest.get('cluster_size', 'N/A')}")
    print(f"Files in manifest: {len(manifest.get('files', []))}")

    # Count file types in manifest
    type_counts = {}
    for f in manifest.get("files", []):
        if f.get("is_directory", False):
            continue
        name = f.get("name", "")
        ext = os.path.splitext(name)[1] if name else ""
        type_counts[ext] = type_counts.get(ext, 0) + 1

    print(f"\nFile types in dataset:")
    for ext, count in sorted(type_counts.items()):
        print(f"  {ext}: {count}")

    # ─── Run Motor Carving ─────────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print("MOTOR CARVING (Signature-Only, NEVER reads MFT)")
    print(f"{'─' * 60}")

    carver = MotorCarving()
    result_carving = carver.recover(image, manifest)

    print(f"  Files recovered: {len(result_carving.recovered_files)}")
    print(f"  Reads: {result_carving.read_count}")
    print(f"  MFT entries parsed: {result_carving.mft_entries_parsed}")
    print(f"  Sectors wasted: {result_carving.sectors_wasted}")
    print(f"  Time to first file: {result_carving.time_to_first_file}")

    if hasattr(result_carving, 'carving_stats') and result_carving.carving_stats:
        stats = result_carving.carving_stats
        print(f"\n  Carving stats:")
        print(f"    Signatures found: {stats.get('signatures_found', {})}")
        print(f"    Files carved: {stats.get('files_carved', 0)}")
        print(f"    Clusters scanned: {stats.get('total_clusters_scanned', 0)}")
        print(f"    Scan coverage: {stats.get('scan_coverage_pct', 0):.1%}")

    # Show recovered files
    print(f"\n  Recovered files:")
    for f in result_carving.recovered_files[:10]:
        print(f"    {f.name} ({f.size:,} bytes, source={f.source})")
    if len(result_carving.recovered_files) > 10:
        print(f"    ... and {len(result_carving.recovered_files) - 10} more")

    # ─── Run Motor B (MFT-First) ──────────────────────────────────────
    print(f"\n{'─' * 60}")
    print("MOTOR B (MFT-First)")
    print(f"{'─' * 60}")

    motor_b = MotorBMFTFirst()
    result_mft = motor_b.recover(image, manifest)

    print(f"  Files recovered: {len(result_mft.recovered_files)}")
    print(f"  Reads: {result_mft.read_count}")
    print(f"  MFT entries parsed: {result_mft.mft_entries_parsed}")
    print(f"  Sectors wasted: {result_mft.sectors_wasted}")
    print(f"  Time to first file: {result_mft.time_to_first_file}")

    # ─── Run Motor A (Sequential) ──────────────────────────────────────
    print(f"\n{'─' * 60}")
    print("MOTOR A (MFT-Sequential — NOT carving)")
    print(f"{'─' * 60}")

    motor_a = MotorASequential()
    result_seq = motor_a.recover(image, manifest)

    print(f"  Files recovered: {len(result_seq.recovered_files)}")
    print(f"  Reads: {result_seq.read_count}")
    print(f"  MFT entries parsed: {result_seq.mft_entries_parsed}")
    print(f"  Sectors wasted: {result_seq.sectors_wasted}")

    # ─── Judge all three ───────────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print("JUDGE EVALUATION")
    print(f"{'─' * 60}")

    judge = RecoveryJudge(manifest)

    # Judge Carving
    metrics_carving = judge.judge(
        recovered_files=[{
            "name": f.name,
            "sha256": f.sha256,
            "size": f.size,
            "is_directory": f.is_directory,
        } for f in result_carving.recovered_files],
        read_count=result_carving.read_count,
        sectors_wasted=result_carving.sectors_wasted,
        time_to_first_file=result_carving.time_to_first_file,
        mft_entries_parsed=result_carving.mft_entries_parsed,
    )

    # Judge MFT-First
    metrics_mft = judge.judge(
        recovered_files=[{
            "name": f.name,
            "sha256": f.sha256,
            "size": f.size,
            "is_directory": f.is_directory,
        } for f in result_mft.recovered_files],
        read_count=result_mft.read_count,
        sectors_wasted=result_mft.sectors_wasted,
        time_to_first_file=result_mft.time_to_first_file,
        mft_entries_parsed=result_mft.mft_entries_parsed,
    )

    # Judge Sequential
    metrics_seq = judge.judge(
        recovered_files=[{
            "name": f.name,
            "sha256": f.sha256,
            "size": f.size,
            "is_directory": f.is_directory,
        } for f in result_seq.recovered_files],
        read_count=result_seq.read_count,
        sectors_wasted=result_seq.sectors_wasted,
        time_to_first_file=result_seq.time_to_first_file,
        mft_entries_parsed=result_seq.mft_entries_parsed,
    )

    print(f"\n  {'Metric':<25} {'Carving':>12} {'MFT-First':>12} {'MFT-Seq':>12}")
    print(f"  {'─' * 25} {'─' * 12} {'─' * 12} {'─' * 12}")
    print(f"  {'Recovery Rate':<25} {metrics_carving.recovery_rate():>11.1%} {metrics_mft.recovery_rate():>11.1%} {metrics_seq.recovery_rate():>11.1%}")
    print(f"  {'Correct Checksums':<25} {metrics_carving.files_correct_checksum:>12} {metrics_mft.files_correct_checksum:>12} {metrics_seq.files_correct_checksum:>12}")
    print(f"  {'Corrupt Files':<25} {metrics_carving.files_corrupt:>12} {metrics_mft.files_corrupt:>12} {metrics_seq.files_corrupt:>12}")
    print(f"  {'Missing Files':<25} {metrics_carving.files_missing:>12} {metrics_mft.files_missing:>12} {metrics_seq.files_missing:>12}")
    print(f"  {'Read Count':<25} {metrics_carving.read_count:>12} {metrics_mft.read_count:>12} {metrics_seq.read_count:>12}")
    print(f"  {'Read Efficiency':<25} {metrics_carving.read_efficiency():>11.1%} {metrics_mft.read_efficiency():>11.1%} {metrics_seq.read_efficiency():>11.1%}")
    print(f"  {'Integrity Score':<25} {metrics_carving.integrity_score:>11.2f} {metrics_mft.integrity_score:>11.2f} {metrics_seq.integrity_score:>11.2f}")
    print(f"  {'MFT Entries Parsed':<25} {metrics_carving.mft_entries_parsed:>12} {metrics_mft.mft_entries_parsed:>12} {metrics_seq.mft_entries_parsed:>12}")
    print(f"  {'False Positives':<25} {metrics_carving.false_positives:>12} {metrics_mft.false_positives:>12} {metrics_seq.false_positives:>12}")

    # ─── Comparison Validation ─────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print("STRATEGY COMPARISON VALIDATION")
    print(f"{'─' * 60}")

    # Carving vs MFT-First — SHOULD be VALID
    v1 = validate_comparison(STRATEGY_CARVING, STRATEGY_MFT_ONLY)
    print(f"\n  Carving vs MFT-Only: {'VALID' if v1['valid'] else 'NOT VALID'}")
    print(f"    {v1['reason']}")

    # MFT-Sequential vs MFT-Only — SHOULD be NOT VALID
    v2 = validate_comparison(STRATEGY_MFT_SEQUENTIAL, STRATEGY_MFT_ONLY)
    print(f"\n  MFT-Sequential vs MFT-Only: {'VALID' if v2['valid'] else 'NOT VALID'}")
    print(f"    {v2['reason']}")

    # ─── BLOCKER-001 Resolution ────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print("BLOCKER-001 STATUS")
    print(f"{'─' * 60}")

    carving_never_reads_mft = result_carving.mft_entries_parsed == 0
    carving_recovers_files = len(result_carving.recovered_files) > 0
    carving_is_different = v1['valid']

    print(f"\n  [1] Carving NEVER reads MFT: {'PASS' if carving_never_reads_mft else 'FAIL'}")
    print(f"      MFT entries parsed: {result_carving.mft_entries_parsed}")
    print(f"\n  [2] Carving recovers files: {'PASS' if carving_recovers_files else 'FAIL'}")
    print(f"      Files recovered: {len(result_carving.recovered_files)}")
    print(f"\n  [3] Carving vs MFT-First is VALID: {'PASS' if carving_is_different else 'FAIL'}")

    all_pass = carving_never_reads_mft and carving_recovers_files and carving_is_different

    if all_pass:
        print(f"\n  BLOCKER-001: RESOLVABLE — Motor Carving is a genuine adversarial strategy")
        print(f"  Next step: Re-run ALL experiments with 3 strategies (Carving, MFT-First, Motor C)")
    else:
        print(f"\n  BLOCKER-001: STILL BLOCKED — Motor Carving needs fixes")

    return all_pass


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
