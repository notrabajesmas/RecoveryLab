#!/usr/bin/env python3
"""
RecoveryLab — Build Sparse Corpus (v0.6.0)
=============================================
Creates an NTFS image with sparse files for testing sparse run recovery.

Sparse files have regions of zeros that don't occupy space on disk.
These are encoded as data runs with offset_size=0 in NTFS.

NTFS sparse runs work at cluster granularity: a cluster is either
entirely sparse or entirely allocated. So our test files must have
cluster-aligned sparse regions.
"""
import sys
import os
import hashlib
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataset_builder.ntfs_image import NTFSImageBuilder

CLUSTER_SIZE = 4096


def build_sparse_corpus(output_dir=None, num_files=20, verify=True):
    """Build a corpus of sparse NTFS files."""
    if output_dir is None:
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "datasets", "ntfs", "sparse"
        )

    os.makedirs(output_dir, exist_ok=True)

    print(f"Building sparse corpus: {num_files} files")
    print(f"Output: {output_dir}")

    # Create builder
    builder = NTFSImageBuilder(
        volume_size=10 * 1024 * 1024,  # 10 MB
        cluster_size=CLUSTER_SIZE,
        serial_number=42,
    )

    # Create sparse files with cluster-aligned regions
    # Layout: [2 clusters data] [2 clusters sparse] [1 cluster data]
    # = 2*4096 + 2*4096 + 1*4096 = 20480 bytes logical size
    # but only 3*4096 = 12288 bytes allocated on disk (sparse runs don't allocate)
    file_infos = []
    for i in range(num_files):
        name = f"sparse_{i:03d}.dat"

        # Cluster-aligned: header (2 clusters) + hole (2 clusters) + footer (1 cluster)
        header = f"HEADER_{i:03d}_".encode().ljust(16, b'_') + os.urandom(CLUSTER_SIZE * 2 - 16)
        hole = b'\x00' * (CLUSTER_SIZE * 2)  # 2 sparse clusters
        footer = f"FOOTER_{i:03d}_".encode().ljust(16, b'_') + os.urandom(CLUSTER_SIZE - 16)

        data = header + hole + footer

        # Sparse region starts at cluster 2, length 2 clusters
        # (byte offset = 2 * CLUSTER_SIZE, byte length = 2 * CLUSTER_SIZE)
        sparse_regions = [(len(header), len(hole))]

        builder.add_sparse_file(name, data, sparse_regions=sparse_regions)
        file_infos.append((name, data, hashlib.sha256(data).hexdigest()))

    # Build image
    print("Building NTFS image...")
    t0 = time.time()
    image, layout, all_files = builder.build()
    build_time = time.time() - t0
    print(f"  Image size: {len(image):,} bytes")
    print(f"  Build time: {build_time:.2f}s")

    # Verify the builder produced correct cluster_runs
    for f in all_files[:3]:
        print(f"  {f.name}: cluster_runs={f.cluster_runs}, is_sparse={f.is_sparse}")

    # Save image
    img_path = os.path.join(output_dir, "corpus_sparse.img")
    with open(img_path, 'wb') as f:
        f.write(image)
    print(f"  Saved: {img_path}")

    # Build manifest
    manifest = {
        "version": "1.0",
        "category": "sparse",
        "num_files": num_files,
        "image_file": "corpus_sparse.img",
        "cluster_size": CLUSTER_SIZE,
        "files": [],
    }

    for i, (name, data, sha) in enumerate(file_infos):
        header_size = CLUSTER_SIZE * 2
        hole_size = CLUSTER_SIZE * 2
        manifest["files"].append({
            "filename": name,
            "size": len(data),
            "sha256": sha,
            "is_sparse": True,
            "sparse_regions": [[header_size, hole_size]],
        })

    manifest_path = os.path.join(output_dir, "corpus_sparse_manifest.json")
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    print(f"  Manifest: {manifest_path}")

    # Verify against parser
    if verify:
        print("\nVerifying with NTFS parser...")
        from ntfs_parser.parser import parse_ntfs_image, recover_file_data

        metadata = parse_ntfs_image(image, cluster_size=CLUSTER_SIZE)

        sparse_entries = [
            e for e in metadata.mft_entries
            if e.in_use and not e.is_directory and e.filename
            and e.record_number >= 12
        ]

        print(f"  MFT entries with files: {len(sparse_entries)}")
        sparse_count = sum(1 for e in sparse_entries if e.is_sparse)
        print(f"  Sparse entries: {sparse_count}")

        verified = 0
        sha_failures = 0
        sparse_run_count = 0
        no_data_count = 0

        for entry in sparse_entries:
            if not entry.filename:
                continue

            file_data = recover_file_data(image, entry, cluster_size=CLUSTER_SIZE)
            if file_data is None or len(file_data) == 0:
                no_data_count += 1
                if no_data_count <= 3:
                    print(f"    FAIL: {entry.filename} - no data recovered")
                    print(f"      data_runs={[(r.length, r.offset, r.is_sparse) for r in entry.data_runs]}")
                    print(f"      data_size={entry.data_size}, is_resident={entry.is_resident}")
                continue

            # Check for sparse runs
            for run in entry.data_runs:
                if run.is_sparse:
                    sparse_run_count += 1

            recovered_sha = hashlib.sha256(file_data).hexdigest()

            # Find expected SHA from manifest
            expected_sha = None
            for mf in manifest["files"]:
                if mf["filename"] == entry.filename:
                    expected_sha = mf["sha256"]
                    break
            
            if expected_sha is None:
                # Not in manifest (system file) — skip
                continue

            if expected_sha and recovered_sha == expected_sha:
                verified += 1
            else:
                sha_failures += 1
                if sha_failures <= 3:
                    print(f"    SHA mismatch: {entry.filename}")
                    print(f"      Expected: {expected_sha}")
                    print(f"      Got:      {recovered_sha}")
                    print(f"      Size:     {len(file_data)}")
                    runs_info = [(r.length, r.offset, r.is_sparse) for r in entry.data_runs]
                    print(f"      Runs:     {runs_info}")

        total = len(file_infos)
        rr = verified / total * 100 if total > 0 else 0
        print(f"\n  Verified: {verified}/{total} (RR={rr:.1f}%)")
        print(f"  SHA-256 failures: {sha_failures}")
        print(f"  No data: {no_data_count}")
        print(f"  Sparse runs found: {sparse_run_count}")

        if verified == total and sha_failures == 0:
            print(f"\n  PASS: Sparse corpus OK - {verified}/{verified} verified, SHA-256 100%")
            with open(os.path.join(output_dir, ".corpus_built"), 'w') as f:
                f.write(f"1.0\n{time.time()}\n")
        else:
            print(f"\n  FAIL: Sparse corpus has failures")

        return verified, total, sparse_run_count

    return 0, 0, 0


if __name__ == "__main__":
    build_sparse_corpus()
