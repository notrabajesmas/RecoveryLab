#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RecoveryLab — MFT Parser Scale Benchmark
==========================================
Measures NTFS MFT Parser performance at scale.

Sprint 3 — Scale Benchmark:
  100 → 500 → 1000 → 5000 → 10000 files

For each scale point, measures:
  - Recovery rate (files found / files total)
  - SHA-256 integrity (files matching / files recovered)
  - Filenames recovered
  - Timestamps recovered
  - Data Runs followed
  - Wall-clock time (seconds)
  - Peak RAM (MB)

This answers: "Does the parser scale?"
"""

import sys
import os
import json
import time
import hashlib
import random
import struct
import tracemalloc
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dataset_builder.ntfs_image import NTFSImageBuilder
from dataset_builder.file_generator import FileGenerator, GeneratedFile
from ntfs_parser.parser import (
    parse_ntfs_image, recover_file_data, NTFSMetadata, MFTEntry,
    SECTOR_SIZE, MFT_RECORD_SIZE
)


# ─── Scale Points ─────────────────────────────────────────────────────────────

SCALE_POINTS = [100, 500, 1000, 5000, 10000]

# File mix for realistic benchmark: 5 common formats
FORMAT_MIX = [".jpg", ".png", ".pdf", ".docx", ".zip"]

# Target average file size (keep manageable for 10K files)
# Small-ish files: 20KB - 200KB average
AVG_FILE_SIZE = 80_000  # 80KB


def generate_files_for_scale(n_files: int, seed: int = 42) -> List[GeneratedFile]:
    """Generate N files with realistic mix of formats."""
    gen = FileGenerator(seed=seed, volume_size=100 * 1024 * 1024, cluster_size=4096)
    rng = random.Random(seed)
    files = []

    for i in range(n_files):
        ext = FORMAT_MIX[i % len(FORMAT_MIX)]
        # Vary size: 10KB to 300KB
        size = rng.randint(10_000, 300_000)

        data = gen._generate_content(ext, size)
        sha256 = hashlib.sha256(data).hexdigest()
        name = f"{ext[1:]}_{i+1:05d}{ext}"

        files.append(GeneratedFile(
            name=name,
            data=data,
            extension=ext,
            category="scale_benchmark",
            size=len(data),
            sha256=sha256,
            created_offset=i * 60.0,
            modified_offset=i * 60.0 + 30.0,
        ))

    return files


def build_ntfs_image(files: List[GeneratedFile], seed: int = 42) -> Tuple[bytes, List[Dict]]:
    """Build NTFS image and return (image_bytes, ground_truth)."""
    # Calculate needed volume size
    total_data = sum(len(f.data) for f in files)
    # Volume needs: MFT + system + data + 30% overhead
    min_volume = total_data * 2 + 50 * 1024 * 1024  # at least 50MB + 2x data
    # Round up to next MB
    volume_size = ((min_volume + 1024 * 1024 - 1) // (1024 * 1024)) * (1024 * 1024)
    # Cap at 2GB for memory safety
    volume_size = min(volume_size, 2 * 1024 * 1024 * 1024)

    cluster_size = 4096
    serial = 0x12345678 + seed

    builder = NTFSImageBuilder(
        volume_size=volume_size,
        cluster_size=cluster_size,
        serial_number=serial,
        fragmentation_rate=0.0,
        fragmentation_seed=seed,
    )

    for f in files:
        builder.add_file(
            name=f.name,
            data=f.data,
            parent_record=5,
            created=f.created_offset,
            modified=f.modified_offset,
        )

    image_bytes, layout, built_files = builder.build()

    # Build ground truth: list of {name, sha256, size}
    ground_truth = []
    for f in files:
        ground_truth.append({
            "name": f.name,
            "sha256": f.sha256,
            "size": f.size,
        })

    return image_bytes, ground_truth


def run_mft_recovery(image: bytes, cluster_size: int = 4096,
                     ground_truth: Optional[List[Dict]] = None) -> Dict:
    """
    Run MFT parser recovery and measure everything.

    Returns dict with all metrics.
    """
    # Start memory tracking
    tracemalloc.start()

    t_start = time.perf_counter()

    # Parse the image
    metadata = parse_ntfs_image(image, cluster_size=cluster_size)

    t_parsed = time.perf_counter()

    # Recover all files
    recovered = []
    sha_matches = 0
    filenames_ok = 0
    timestamps_ok = 0
    data_runs_ok = 0
    name_matches = 0

    gt_by_sha = {}
    gt_by_name = {}
    if ground_truth:
        for gt in ground_truth:
            gt_by_sha[gt["sha256"]] = gt
            gt_by_name[gt["name"]] = gt

    for entry in metadata.mft_entries:
        # Skip system files (records 0-11)
        if entry.record_number < 12:
            continue
        # Skip directories
        if entry.is_directory:
            continue
        # Skip entries not in use
        if not entry.in_use:
            continue
        # Skip entries without filename
        if not entry.filename:
            continue

        # Recover file data
        file_data = recover_file_data(image, entry, cluster_size)
        if file_data is None or len(file_data) == 0:
            continue

        sha256 = hashlib.sha256(file_data).hexdigest()

        # Check SHA-256 against ground truth
        sha_match = sha256 in gt_by_sha if gt_by_sha else False

        # Check filename against ground truth
        name_match = entry.filename in gt_by_name if gt_by_name else False

        # Check timestamps present
        has_timestamps = entry.created > 0 or entry.modified > 0

        # Check data runs present
        has_data_runs = len(entry.data_runs) > 0 or entry.is_resident

        recovered.append({
            "record": entry.record_number,
            "name": entry.filename,
            "sha256": sha256,
            "size": len(file_data),
            "sha_match": sha_match,
            "name_match": name_match,
            "has_timestamps": has_timestamps,
            "has_data_runs": has_data_runs,
        })

        if sha_match:
            sha_matches += 1
        if name_match:
            name_matches += 1
        if has_timestamps:
            timestamps_ok += 1
        if has_data_runs:
            data_runs_ok += 1
        if entry.filename:
            filenames_ok += 1

    t_end = time.perf_counter()

    # Get peak memory
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Calculate metrics
    n_total = len(ground_truth) if ground_truth else 0
    n_recovered = len(recovered)

    result = {
        "files_total": n_total,
        "files_recovered": n_recovered,
        "recovery_rate": n_recovered / n_total if n_total > 0 else 0.0,
        "sha256_matches": sha_matches,
        "sha256_rate": sha_matches / n_total if n_total > 0 else 0.0,
        "filename_matches": name_matches,
        "filename_rate": name_matches / n_total if n_total > 0 else 0.0,
        "timestamps_ok": timestamps_ok,
        "timestamps_rate": timestamps_ok / n_recovered if n_recovered > 0 else 0.0,
        "data_runs_ok": data_runs_ok,
        "data_runs_rate": data_runs_ok / n_recovered if n_recovered > 0 else 0.0,
        "mft_entries_parsed": metadata.mft_entries_parsed,
        "parse_errors": metadata.parse_errors,
        "deleted_files_found": metadata.deleted_files_found,
        "time_parse_s": round(t_parsed - t_start, 3),
        "time_recover_s": round(t_end - t_parsed, 3),
        "time_total_s": round(t_end - t_start, 3),
        "peak_ram_mb": round(peak_mem / (1024 * 1024), 1),
        "image_size_mb": round(len(image) / (1024 * 1024), 1),
    }

    return result


def run_scale_benchmark():
    """Run the full scale benchmark."""
    print("=" * 70)
    print("RecoveryLab — MFT Parser Scale Benchmark")
    print("=" * 70)
    print()
    print("Sprint 3 visible metric:")
    print("  Does the MFT parser scale from 100 to 10,000 files?")
    print()

    all_results = []

    for n_files in SCALE_POINTS:
        print(f"─" * 60)
        print(f"Scale point: {n_files} files")
        print(f"─" * 60)

        # Step 1: Generate files
        print(f"  Generating {n_files} files...", end=" ", flush=True)
        t0 = time.perf_counter()
        files = generate_files_for_scale(n_files, seed=42)
        t1 = time.perf_counter()
        print(f"done ({t1-t0:.1f}s)")

        # Step 2: Build NTFS image
        total_data_mb = sum(len(f.data) for f in files) / (1024 * 1024)
        print(f"  Total file data: {total_data_mb:.1f} MB")
        print(f"  Building NTFS image...", end=" ", flush=True)
        t0 = time.perf_counter()
        image, ground_truth = build_ntfs_image(files, seed=42)
        t1 = time.perf_counter()
        image_mb = len(image) / (1024 * 1024)
        print(f"done ({t1-t0:.1f}s, {image_mb:.1f} MB)")

        # Step 3: Free the files list (no longer needed, GT is in ground_truth)
        del files

        # Step 4: Run MFT recovery
        print(f"  Running MFT recovery...", end=" ", flush=True)
        result = run_mft_recovery(image, cluster_size=4096, ground_truth=ground_truth)
        result["n_files"] = n_files
        all_results.append(result)

        # Step 5: Print results for this scale point
        print(f"done")
        print()
        print(f"  Files recovered.......{result['files_recovered']}/{result['files_total']}")
        print(f"  SHA-256...............{result['sha256_matches']}/{result['files_total']}")
        print(f"  Filenames.............{result['filename_matches']}/{result['files_total']}")
        print(f"  Timestamps............{result['timestamps_ok']}/{result['files_recovered']}")
        print(f"  Data Runs.............{result['data_runs_ok']}/{result['files_recovered']}")
        print(f"  Parse errors..........{result['parse_errors']}")
        print(f"  Time (parse)..........{result['time_parse_s']:.3f}s")
        print(f"  Time (recover)........{result['time_recover_s']:.3f}s")
        print(f"  Time (total)..........{result['time_total_s']:.3f}s")
        print(f"  Peak RAM..............{result['peak_ram_mb']:.1f} MB")
        print()

        # Free image memory
        del image
        del ground_truth

    # ─── Summary Table ──────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("SCALE BENCHMARK — RESULTS TABLE")
    print("=" * 70)
    print()
    print(f"{'Files':>8} │ {'Recovery':>10} │ {'SHA-256':>10} │ {'Filenames':>10} │ {'Timestamps':>10} │ {'Data Runs':>10} │ {'Time':>8} │ {'RAM':>8}")
    print(f"{'':>8} │ {'rate':>10} │ {'rate':>10} │ {'rate':>10} │ {'rate':>10} │ {'rate':>10} │ {'(sec)':>8} │ {'(MB)':>8}")
    print("─────────┼────────────┼────────────┼────────────┼────────────┼────────────┼──────────┼──────────")

    for r in all_results:
        recovery_pct = f"{r['recovery_rate']*100:.1f}%"
        sha_pct = f"{r['sha256_rate']*100:.1f}%"
        fn_pct = f"{r['filename_rate']*100:.1f}%"
        ts_pct = f"{r['timestamps_rate']*100:.1f}%"
        dr_pct = f"{r['data_runs_rate']*100:.1f}%"
        time_str = f"{r['time_total_s']:.2f}"
        ram_str = f"{r['peak_ram_mb']:.0f}"

        print(f"{r['n_files']:>8} │ {recovery_pct:>10} │ {sha_pct:>10} │ {fn_pct:>10} │ {ts_pct:>10} │ {dr_pct:>10} │ {time_str:>8} │ {ram_str:>8}")

    print()

    # ─── Detailed Table (absolute numbers) ──────────────────────────────────
    print()
    print("DETAILED — ABSOLUTE NUMBERS")
    print()
    print(f"{'Files':>8} │ {'Recovered':>10} │ {'SHA match':>10} │ {'Name match':>10} │ {'Timestamps':>10} │ {'Parse errs':>10} │ {'Image MB':>10}")
    print("─────────┼────────────┼────────────┼────────────┼────────────┼────────────┼────────────")

    for r in all_results:
        print(f"{r['n_files']:>8} │ {r['files_recovered']:>10} │ {r['sha256_matches']:>10} │ {r['filename_matches']:>10} │ {r['timestamps_ok']:>10} │ {r['parse_errors']:>10} │ {r['image_size_mb']:>10.0f}")

    print()

    # ─── Performance Table ──────────────────────────────────────────────────
    print()
    print("PERFORMANCE — TIME & MEMORY")
    print()
    print(f"{'Files':>8} │ {'Parse(s)':>10} │ {'Recover(s)':>10} │ {'Total(s)':>10} │ {'Peak RAM':>10} │ {'Image MB':>10} │ {'Throughput':>12}")
    print("─────────┼────────────┼────────────┼────────────┼────────────┼────────────┼────────────")

    for r in all_results:
        throughput = r['files_recovered'] / r['time_total_s'] if r['time_total_s'] > 0 else 0
        print(f"{r['n_files']:>8} │ {r['time_parse_s']:>10.3f} │ {r['time_recover_s']:>10.3f} │ {r['time_total_s']:>10.3f} │ {r['peak_ram_mb']:>10.1f} │ {r['image_size_mb']:>10.0f} │ {throughput:>10.0f}/s")

    print()

    # ─── Verdict ────────────────────────────────────────────────────────────
    all_100 = all(r['recovery_rate'] >= 1.0 and r['sha256_rate'] >= 1.0 for r in all_results)
    scales_linear = all_results[-1]['time_total_s'] / all_results[0]['time_total_s'] if all_results[0]['time_total_s'] > 0 else 0
    n_ratio = all_results[-1]['n_files'] / all_results[0]['n_files'] if all_results[0]['n_files'] > 0 else 1

    print()
    print("VERDICT")
    print()
    if all_100:
        print(f"  ✔ 100% recovery + 100% SHA-256 across ALL scale points")
        print(f"  ✔ Parser scales from {SCALE_POINTS[0]} to {SCALE_POINTS[-1]:,} files")
    else:
        worst = min(all_results, key=lambda r: r['recovery_rate'])
        print(f"  ✘ Recovery drops at {worst['n_files']} files: {worst['recovery_rate']*100:.1f}%")

    print(f"  Time scaling: {scales_linear:.1f}x for {n_ratio:.0f}x more files")
    if scales_linear < n_ratio * 1.5:
        print(f"  ✔ Sub-linear or linear scaling (good)")
    else:
        print(f"  ⚠ Super-linear scaling — investigate performance")

    # ─── Save Results ───────────────────────────────────────────────────────
    results_path = PROJECT_ROOT / "results" / "benchmark_mft_scale_results.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "benchmark": "mft_parser_scale",
        "sprint": 3,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "scale_points": SCALE_POINTS,
        "results": all_results,
        "verdict": {
            "all_100_pct": all_100,
            "time_scaling_ratio": round(scales_linear, 2),
            "files_scaling_ratio": n_ratio,
        },
    }

    with open(results_path, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n  Results saved: {results_path}")

    return all_results


if __name__ == "__main__":
    run_scale_benchmark()
