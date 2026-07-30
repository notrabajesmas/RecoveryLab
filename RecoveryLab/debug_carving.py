#!/usr/bin/env python3
"""
RecoveryLab — Carving Debug
=============================
Debug why the carving motor only recovers 1 file when it finds 6 signatures.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from motors.motor_carving import MotorCarving, SIGNATURES
from dataset_builder.manifest import load_manifest


def main():
    # Load dataset
    dataset_dir = os.path.join(os.path.dirname(__file__), "output", "datasets")
    img_path = None
    manifest_path = None

    for f in sorted(os.listdir(dataset_dir)):
        if f.endswith(".img"):
            img_path = os.path.join(dataset_dir, f)
            manifest_name = f.replace(".img", "_manifest.json")
            manifest_path = os.path.join(dataset_dir, manifest_name)
            if os.path.exists(manifest_path):
                break

    with open(img_path, 'rb') as f:
        image = f.read()
    manifest = load_manifest(manifest_path)

    print(f"Image size: {len(image):,} bytes")
    print(f"Cluster size: {manifest['cluster_size']}")
    print(f"Total clusters: {manifest.get('total_clusters', 'N/A')}")

    # Show what files exist and their types
    print(f"\nFiles in manifest:")
    for f in manifest.get("files", []):
        if f.get("is_directory", False):
            continue
        name = f.get("name", "")
        size = f.get("size", 0)
        sha = f.get("sha256", "")[:12]
        print(f"  {name:30s} {size:>10,} bytes  SHA={sha}...")

    # Scan manually for signatures
    print(f"\n\nManual signature scan:")
    cluster_size = manifest['cluster_size']
    total_clusters = manifest.get('total_clusters', len(image) // cluster_size)

    for sig in SIGNATURES:
        print(f"\n  {sig.name} ({sig.extension}):")
        print(f"    Header: {sig.header.hex()} (mask: {sig.header_mask.hex()})")
        print(f"    Footer: {sig.footer.hex() if sig.footer else '(none)'}")
        print(f"    Max size: {sig.max_size:,} bytes")
        print(f"    Min size: {sig.min_size:,} bytes")

        # Search for this signature
        found = 0
        for cluster_num in range(total_clusters):
            cluster_start = cluster_num * cluster_size
            if cluster_start + cluster_size > len(image):
                break

            # Check at start of cluster
            chunk = image[cluster_start:cluster_start + min(16, cluster_size)]
            if len(chunk) >= len(sig.header):
                match = True
                for i in range(len(sig.header)):
                    if sig.header_mask[i] == 0xFF:
                        if chunk[i] != sig.header[i]:
                            match = False
                            break
                if match:
                    found += 1
                    # Show what's at this location
                    preview = image[cluster_start:cluster_start + min(64, cluster_size)]
                    print(f"    Found at cluster {cluster_num} (offset {cluster_start:,})")
                    print(f"      Preview: {preview[:32].hex()}")

        if found == 0:
            print(f"    (none found)")

    # Now run the actual carving motor with debug
    print(f"\n\n{'='*60}")
    print("Running Motor Carving with detailed output...")
    print(f"{'='*60}")

    carver = MotorCarving()

    # Monkey-patch to add debug output
    original_carve = carver._carve_file
    original_find = carver._find_signature_matches

    debug_carves = []

    def debug_carve_file(image, start_offset, sig, image_len, cluster_size, total_clusters, read_clusters):
        result = original_carve(image, start_offset, sig, image_len, cluster_size, total_clusters, read_clusters)
        if result is not None:
            print(f"  CARVED: {sig.name} at offset {start_offset:,}, size={result['size']:,} bytes")
        else:
            print(f"  REJECTED: {sig.name} at offset {start_offset:,} (too small or invalid)")
        debug_carves.append({"sig": sig.name, "offset": start_offset, "result": result})
        return result

    carver._carve_file = debug_carve_file

    result = carver.recover(image, manifest)

    print(f"\nFinal result: {len(result.recovered_files)} files recovered")
    print(f"Reads: {result.read_count}")
    print(f"MFT entries parsed: {result.mft_entries_parsed}")

    if hasattr(result, 'carving_stats') and result.carving_stats:
        stats = result.carving_stats
        print(f"Signatures found: {stats.get('signatures_found', {})}")
        print(f"Files carved: {stats.get('files_carved', 0)}")


if __name__ == "__main__":
    main()
