#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RecoveryLab — Sprint 4A Benchmark: Multiple Data Runs
=======================================================
Sprint 4A termina cuando RecoveryLab puede abrir una imagen NTFS
con archivos fragmentados y recuperar correctamente archivos
distribuidos en 2-5 extents.

Métrica visible:
  Fragmented file recovery: 0% → ?%
"""

import sys
import os
import time
import hashlib
import json

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from dataset_builder.ntfs_image import NTFSImageBuilder
from dataset_builder.file_generator import FileGenerator
from ntfs_parser.parser import parse_ntfs_image, recover_file_data


def create_fragmented_image(num_files=50, fragmentation_rate=0.5,
                            image_size_mb=30, seed=42):
    """Create an NTFS image with fragmented files.
    
    Uses a larger image (30MB) to accommodate fragmentation gaps
    and NTFS overhead (MFT, bitmap, journal, etc.).
    """
    gen = FileGenerator(seed=seed, volume_size=image_size_mb * 1024 * 1024)
    generated = gen.generate_file_set(count=num_files)
    
    # Build image with fragmentation
    # Extra space for fragmentation gaps (gaps add ~3 clusters per fragmented file)
    builder = NTFSImageBuilder(
        volume_size=image_size_mb * 1024 * 1024,
        fragmentation_rate=fragmentation_rate,
        fragmentation_seed=seed + 100,
        serial_number=seed,
    )
    
    for f in generated:
        builder.add_file(f.name, f.data, created=f.created_offset, modified=f.modified_offset)
    
    image_bytes, layout, all_files = builder.build()
    manifest = builder.get_manifest_data()
    
    return bytes(image_bytes), manifest, generated


def benchmark_fragment_recovery():
    """Run the Sprint 4A benchmark."""
    print("=" * 70)
    print("Sprint 4A — Multiple Data Runs Benchmark")
    print("=" * 70)
    print()
    
    # Test at different fragmentation rates
    results = []
    
    for frag_rate in [0.0, 0.3, 0.5, 0.7, 1.0]:
        print(f"─ Fragmentation rate: {frag_rate:.0%}")
        print()
        
        # Create image — use 20 files to avoid $UsnJrnl MFT overflow
        image, manifest, original_files = create_fragmented_image(
            num_files=20,
            fragmentation_rate=frag_rate,
            seed=42,
        )
        
        cluster_size = manifest.get("cluster_size", 4096)
        
        # Count fragmented files from manifest
        manifest_files = manifest.get("files", [])
        non_dir_files = [f for f in manifest_files if not f.get("is_directory", False)]
        total_files = len(non_dir_files)
        fragmented_files = len([f for f in non_dir_files if f.get("is_fragmented", False)])
        contiguous_files = total_files - fragmented_files
        
        print(f"  Total files in manifest:    {total_files}")
        print(f"  Fragmented (multi-run):     {fragmented_files}")
        print(f"  Contiguous (single-run):    {contiguous_files}")
        
        # ── Direct parser verification ──────────────────────────
        metadata = parse_ntfs_image(image, cluster_size=cluster_size)
        
        manifest_sha = {}
        manifest_name = {}
        for mf in non_dir_files:
            name = mf.get("name", "")
            sha = mf.get("sha256", "")
            if name and sha:
                manifest_sha[name] = sha
                manifest_name[name.lower()] = name  # Case-insensitive lookup
        
        # Parse all MFT entries and verify
        recovered_count = 0
        sha_matches = 0
        sha_mismatches = 0
        not_in_manifest = 0
        multi_run_ok = 0
        multi_run_fail = 0
        multi_run_total = 0
        single_run_ok = 0
        single_run_fail = 0
        
        for entry in metadata.mft_entries:
            if not entry.in_use or entry.is_directory or entry.record_number < 12:
                continue
            if not entry.filename:
                continue
            
            num_runs = len(entry.data_runs)
            file_data = recover_file_data(image, entry, cluster_size=cluster_size)
            
            if file_data is None or len(file_data) == 0:
                continue
            
            # Trim to actual size
            actual_size = entry.data_size if entry.data_size > 0 else len(file_data)
            if len(file_data) > actual_size:
                file_data = file_data[:actual_size]
            
            actual_sha = hashlib.sha256(file_data).hexdigest()
            
            # Try to match against manifest (case-insensitive)
            fname_lower = entry.filename.lower()
            expected_name = manifest_name.get(fname_lower)
            expected_sha = manifest_sha.get(expected_name, "") if expected_name else ""
            
            if not expected_sha:
                # Try direct match
                expected_sha = manifest_sha.get(entry.filename, "")
            
            recovered_count += 1
            
            if expected_sha and actual_sha == expected_sha:
                sha_matches += 1
                if num_runs > 1:
                    multi_run_total += 1
                    multi_run_ok += 1
                else:
                    single_run_ok += 1
            elif expected_sha:
                sha_mismatches += 1
                if num_runs > 1:
                    multi_run_total += 1
                    multi_run_fail += 1
                else:
                    single_run_fail += 1
            else:
                not_in_manifest += 1
        
        # Metrics
        rr = recovered_count / total_files if total_files > 0 else 0
        sha_rate = sha_matches / total_files if total_files > 0 else 0
        
        print(f"  ── Parser recovery results:")
        print(f"  Recovered:             {recovered_count}/{total_files} ({rr:.1%})")
        print(f"  SHA-256 match:         {sha_matches}/{total_files} ({sha_rate:.1%})")
        print(f"  SHA-256 mismatch:      {sha_mismatches}")
        print(f"  Not in manifest:       {not_in_manifest}")
        print(f"  Single-run OK:         {single_run_ok}  (fail: {single_run_fail})")
        print(f"  Multi-run OK:          {multi_run_ok}  (fail: {multi_run_fail})")
        print()
        
        results.append({
            "frag_rate": frag_rate,
            "total_files": total_files,
            "fragmented": fragmented_files,
            "recovered": recovered_count,
            "sha_matches": sha_matches,
            "rr": rr,
            "sha_rate": sha_rate,
            "multi_run_ok": multi_run_ok,
            "multi_run_fail": multi_run_fail,
            "multi_run_total": multi_run_total,
        })
    
    # ── Summary ──────────────────────────────────────────────────
    print("=" * 70)
    print("Sprint 4A Summary")
    print("=" * 70)
    print()
    print(f"{'Frag Rate':>10} {'Files':>6} {'Frag':>6} {'Recovered':>10} {'SHA-256':>8} {'Multi-OK':>9} {'Multi-Fail':>11}")
    print("─" * 62)
    for r in results:
        print(f"{r['frag_rate']:>9.0%} {r['total_files']:>6} {r['fragmented']:>6} "
              f"{r['recovered']:>10} {r['sha_matches']:>8} {r['multi_run_ok']:>9} {r['multi_run_fail']:>11}")
    print()
    
    # Veredicto Sprint 4A
    total_multi_ok = sum(r["multi_run_ok"] for r in results)
    total_multi_fail = sum(r["multi_run_fail"] for r in results)
    total_multi = total_multi_ok + total_multi_fail
    
    print("─" * 70)
    print(f"Total multi-run files tested: {total_multi}")
    print(f"Total multi-run SHA-256 OK:   {total_multi_ok}")
    print(f"Total multi-run SHA-256 FAIL: {total_multi_fail}")
    print()
    
    if total_multi > 0 and total_multi_fail == 0:
        print("✅ Sprint 4A PASS — RecoveryLab recovers ALL files split across multiple data runs")
        print(f"   {total_multi_ok}/{total_multi} multi-run files recovered with correct SHA-256")
    elif total_multi > 0:
        rate = total_multi_ok / total_multi
        print(f"🟡 Sprint 4A PARTIAL — {rate:.1%} multi-run recovery ({total_multi_fail} failures)")
        print(f"   Need to investigate {total_multi_fail} SHA-256 mismatches")
    else:
        print("⚠️  No multi-run files found — dataset builder may not fragment small files")
    
    return results


if __name__ == "__main__":
    benchmark_fragment_recovery()
