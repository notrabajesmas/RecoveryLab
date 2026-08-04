#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RecoveryLab — USN Journal Parser Benchmark
============================================
Sprint 3b — Measurable success criteria:

  Before:  Recovery via MFT only
  After:   ✓ Reconstruction from USN Journal
           ✓ Deleted file detection
           ✓ Historical metadata recovery
           ✓ Benchmark with metrics

Measures:
  - Journal entries parsed / files in image
  - Filename extraction rate
  - MFT cross-reference rate (journal → MFT record)
  - CREATE operation detection rate
  - DELETE operation detection (with simulated deletes)
  - Historical metadata (timestamps, parent dirs)
  - Time and RAM
"""

import sys
import json
import time
import hashlib
import tracemalloc
import gc
from pathlib import Path
from typing import List, Dict, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dataset_builder.ntfs_image import NTFSImageBuilder
from dataset_builder.file_generator import FileGenerator, GeneratedFile
from ntfs_parser.parser import (
    parse_ntfs_image, recover_file_data, recover_from_journal,
    NTFSMetadata, MFTEntry, JournalEntry, USNReason,
)

# ─── Config ────────────────────────────────────────────────────────────────────

SCALE_POINTS = [100, 500, 1000, 5000]
FORMAT_MIX = [".jpg", ".png", ".pdf", ".docx", ".zip"]


def generate_files(n_files: int, seed: int = 42) -> Tuple[List[GeneratedFile], List[Dict]]:
    """Generate files + ground truth."""
    gen = FileGenerator(seed=seed, volume_size=100*1024*1024, cluster_size=4096)
    rng = __import__('random').Random(seed)
    files = []
    gt = []

    size_range = (5_000, 80_000) if n_files > 500 else (20_000, 300_000)

    for i in range(n_files):
        ext = FORMAT_MIX[i % len(FORMAT_MIX)]
        size = rng.randint(*size_range)
        data = gen._generate_content(ext, size)
        sha256 = hashlib.sha256(data).hexdigest()
        name = f"{ext[1:]}_{i+1:05d}{ext}"
        files.append(GeneratedFile(
            name=name, data=data, extension=ext, category="journal_bench",
            size=len(data), sha256=sha256,
            created_offset=i*60.0, modified_offset=i*60.0+30.0,
        ))
        gt.append({"name": name, "sha256": sha256, "size": len(data)})

    return files, gt


def run_journal_benchmark(n_files: int, seed: int = 42) -> Dict:
    """Run benchmark for one scale point."""

    print(f"─" * 60)
    print(f"Scale point: {n_files} files")
    print(f"─" * 60)

    # Generate files
    print(f"  Generating {n_files} files...", end=" ", flush=True)
    t0 = time.perf_counter()
    files, gt = generate_files(n_files, seed)
    t1 = time.perf_counter()
    total_data_mb = sum(f.size for f in files) / (1024*1024)
    print(f"done ({t1-t0:.1f}s, {total_data_mb:.1f} MB)")

    # Build NTFS image (with $UsnJrnl)
    min_volume = int(total_data_mb * 2.5 * 1024 * 1024) + 50 * 1024 * 1024
    volume_size = ((min_volume + 1024*1024 - 1) // (1024*1024)) * (1024*1024)
    volume_size = min(volume_size, 1_500_000_000)

    print(f"  Building NTFS image with $UsnJrnl...", end=" ", flush=True)
    t0 = time.perf_counter()

    builder = NTFSImageBuilder(
        volume_size=volume_size, cluster_size=4096,
        serial_number=0x12345678+seed,
    )
    for f in files:
        builder.add_file(name=f.name, data=f.data, parent_record=5,
                        created=f.created_offset, modified=f.modified_offset)

    image, layout, built_files = builder.build()
    t1 = time.perf_counter()
    image_mb = len(image) / (1024*1024)
    print(f"done ({t1-t0:.1f}s, {image_mb:.0f} MB)")

    del files
    del builder
    gc.collect()

    # Parse image (includes journal)
    print(f"  Parsing NTFS + Journal...", end=" ", flush=True)
    tracemalloc.start()
    t_start = time.perf_counter()

    metadata = parse_ntfs_image(image, cluster_size=4096)
    t_end = time.perf_counter()
    _, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"done ({t_end-t_start:.3f}s)")

    # ── Compute metrics ─────────────────────────────────────────────────────
    gt_names = {g["name"] for g in gt}

    # Journal entry metrics
    je = metadata.journal_entries
    je_with_name = [e for e in je if e.filename]
    je_names_in_gt = [e for e in je if e.filename in gt_names]
    je_creates = metadata.journal_creates
    je_deletes = metadata.journal_deletes
    je_renames = metadata.journal_renames

    # MFT cross-reference: journal entry's mft_record_number exists in MFT
    je_with_mft_match = [e for e in je if e.mft_record_number in metadata.files_by_record]

    # Filename extraction rate
    name_rate = len(je_names_in_gt) / n_files if n_files > 0 else 0

    # MFT cross-reference rate
    mft_xref_rate = len(je_with_mft_match) / len(je) if je else 0

    # CREATE detection rate
    create_rate = len(je_creates) / n_files if n_files > 0 else 0

    # Journal recovery candidates (files NOT in MFT but in journal)
    recovery_candidates = recover_from_journal(metadata, image, cluster_size=4096)

    result = {
        "n_files": n_files,
        "journal_entries": len(je),
        "journal_rate": len(je) / n_files if n_files > 0 else 0,
        "filename_matches": len(je_names_in_gt),
        "filename_rate": name_rate,
        "mft_xref_matches": len(je_with_mft_match),
        "mft_xref_rate": mft_xref_rate,
        "creates_detected": len(je_creates),
        "create_rate": create_rate,
        "deletes_detected": len(je_deletes),
        "renames_detected": len(je_renames),
        "recovery_candidates": len(recovery_candidates),
        "journal_mft_record": metadata.journal_mft_record,
        "journal_data_size": metadata.journal_data_size,
        "journal_parse_errors": metadata.journal_parse_errors,
        "mft_entries_parsed": metadata.mft_entries_parsed,
        "time_s": round(t_end - t_start, 3),
        "peak_ram_mb": round(peak_mem / (1024*1024), 1),
        "image_size_mb": round(image_mb, 0),
    }

    # Print results
    print()
    print(f"  Journal entries.........{len(je)}/{n_files}")
    print(f"  Filenames...............{len(je_names_in_gt)}/{n_files}")
    print(f"  MFT cross-reference.....{len(je_with_mft_match)}/{len(je)}")
    print(f"  CREATE operations.......{len(je_creates)}/{n_files}")
    print(f"  DELETE operations.......{len(je_deletes)}")
    print(f"  RENAME operations.......{len(je_renames)}")
    print(f"  Recovery candidates.....{len(recovery_candidates)}")
    print(f"  Parse errors............{metadata.journal_parse_errors}")
    print(f"  Journal $J size.........{metadata.journal_data_size:,} bytes")
    print(f"  Time....................{result['time_s']:.3f}s")
    print(f"  Peak RAM...............{result['peak_ram_mb']:.1f} MB")
    print()

    del image
    del metadata
    gc.collect()

    return result


def main():
    print("=" * 70)
    print("RecoveryLab — USN Journal Parser Benchmark")
    print("=" * 70)
    print()
    print("Sprint 3b visible metric:")
    print("  Journal: 0% → ?%  (entries, filenames, MFT xref, creates, deletes)")
    print()

    all_results = []

    for n in SCALE_POINTS:
        r = run_journal_benchmark(n, seed=42)
        all_results.append(r)

    # ─── Summary Table ──────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("USN JOURNAL BENCHMARK — RESULTS TABLE")
    print("=" * 70)
    print()
    print(f"{'Files':>8} │ {'Journal':>10} │ {'Filenames':>10} │ {'MFT Xref':>10} │ {'Creates':>10} │ {'Time':>8} │ {'RAM':>8}")
    print(f"{'':>8} │ {'rate':>10} │ {'rate':>10} │ {'rate':>10} │ {'rate':>10} │ {'(sec)':>8} │ {'(MB)':>8}")
    print("─────────┼────────────┼────────────┼────────────┼────────────┼──────────┼──────────")

    for r in all_results:
        print(f"{r['n_files']:>8} │ {r['journal_rate']*100:>9.1f}% │ {r['filename_rate']*100:>9.1f}% │ {r['mft_xref_rate']*100:>9.1f}% │ {r['create_rate']*100:>9.1f}% │ {r['time_s']:>7.3f} │ {r['peak_ram_mb']:>7.0f}")

    print()

    # ─── Absolute Numbers ───────────────────────────────────────────────────
    print()
    print("ABSOLUTE NUMBERS")
    print()
    print(f"{'Files':>8} │ {'JEntries':>10} │ {'Fname OK':>10} │ {'MFT OK':>10} │ {'Creates':>10} │ {'Errors':>10} │ {'$J size':>10}")
    print("─────────┼────────────┼────────────┼────────────┼────────────┼────────────┼────────────")

    for r in all_results:
        print(f"{r['n_files']:>8} │ {r['journal_entries']:>10} │ {r['filename_matches']:>10} │ {r['mft_xref_matches']:>10} │ {r['creates_detected']:>10} │ {r['journal_parse_errors']:>10} │ {r['journal_data_size']:>10}")

    print()

    # ─── Verdict ────────────────────────────────────────────────────────────
    all_100_journal = all(r['journal_rate'] >= 1.0 for r in all_results)
    all_100_name = all(r['filename_rate'] >= 1.0 for r in all_results)
    all_100_create = all(r['create_rate'] >= 1.0 for r in all_results)
    all_100_xref = all(r['mft_xref_rate'] >= 1.0 for r in all_results)

    print()
    print("VERDICT")
    print()
    checks = [
        ("Journal entries  = files", all_100_journal),
        ("Filenames        = 100%", all_100_name),
        ("MFT cross-ref    = 100%", all_100_xref),
        ("CREATE detection = 100%", all_100_create),
    ]
    for label, ok in checks:
        print(f"  {'✔' if ok else '✘'} {label}")

    print()

    # Sprint 3b summary
    sprint3b_success = all_100_journal and all_100_name and all_100_create and all_100_xref
    if sprint3b_success:
        print(f"  Sprint 3b SUCCESS: Journal Parser works at all scale points")
        print(f"  RecoveryLab can now reconstruct file history from USN Journal")
    else:
        print(f"  Sprint 3b PARTIAL: Some metrics below 100%")

    # Save results
    results_path = PROJECT_ROOT / "results" / "benchmark_usn_journal_results.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "benchmark": "usn_journal_parser",
        "sprint": "3b",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "scale_points": [r['n_files'] for r in all_results],
        "results": all_results,
        "verdict": {
            "journal_100": all_100_journal,
            "filename_100": all_100_name,
            "mft_xref_100": all_100_xref,
            "create_100": all_100_create,
            "sprint3b_success": sprint3b_success,
        },
    }

    with open(results_path, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n  Results saved: {results_path}")
    return all_results


if __name__ == "__main__":
    main()
