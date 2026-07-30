"""
RecoveryLab — Dataset Builder
================================
Main orchestrator for building complete NTFS datasets.

Usage:
    builder = DatasetBuilder(seed=42, num_images=20)
    builder.build_all()

This creates:
    output/datasets/dataset_001.img
    output/datasets/dataset_001_manifest.json
    output/datasets/dataset_002.img
    ...
"""

import os
import sys
import json
import hashlib
import random
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    DEFAULT_NUM_IMAGES, DEFAULT_SEED, DEFAULT_VOLUME_SIZE,
    DEFAULT_CLUSTER_SIZE, DATASETS_DIR, FILE_PROFILES,
    NTFS_CLUSTER_SIZE, NTFS_SECTOR_SIZE,
)
from dataset_builder.ntfs_image import NTFSImageBuilder, DataRun
from dataset_builder.file_generator import FileGenerator, GeneratedFile
from dataset_builder.manifest import (
    generate_manifest, save_manifest, load_manifest, verify_manifest,
    compute_integrity_hash,
)


class DatasetBuilder:
    """
    Builds complete NTFS datasets with ground truth manifests.

    Each dataset is a pair:
        - .img file: the raw NTFS image
        - _manifest.json: the ground truth (what's in the image, where)

    Everything is deterministic: same seed → same images, bit for bit.
    """

    def __init__(self, seed: int = DEFAULT_SEED,
                 num_images: int = DEFAULT_NUM_IMAGES,
                 volume_size: int = DEFAULT_VOLUME_SIZE,
                 cluster_size: int = DEFAULT_CLUSTER_SIZE,
                 output_dir: Optional[Path] = None,
                 files_per_image: int = 30,
                 fragmentation_rate: float = 0.0):
        self.seed = seed
        self.num_images = num_images
        self.volume_size = volume_size
        self.cluster_size = cluster_size
        self.output_dir = output_dir or DATASETS_DIR
        self.files_per_image = files_per_image
        self.fragmentation_rate = fragmentation_rate

        # Master RNG for generating per-image seeds
        self.master_rng = random.Random(seed)

    def build_all(self) -> List[Path]:
        """
        Build all images in the dataset.

        Returns list of manifest file paths.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        manifest_paths = []

        for i in range(1, self.num_images + 1):
            print(f"\n{'='*60}")
            print(f"Building dataset {i:03d}/{self.num_images:03d}")
            print(f"{'='*60}")

            manifest_path = self.build_image(index=i)
            manifest_paths.append(manifest_path)

        # Save dataset index
        self._save_dataset_index(manifest_paths)

        print(f"\n✓ Dataset complete: {self.num_images} images")
        print(f"  Output: {self.output_dir}")

        return manifest_paths

    def build_image(self, index: int) -> Path:
        """
        Build a single image with its manifest.

        Args:
            index: 1-based image index

        Returns:
            Path to the manifest file
        """
        # Generate per-image seed
        image_seed = self.master_rng.randint(0, 2**32 - 1)

        # Generate serial number
        serial = self.master_rng.randint(0, 2**32 - 1)

        # Vary volume size slightly per image (±20%)
        size_variation = self.master_rng.uniform(0.8, 1.2)
        image_volume_size = int(self.volume_size * size_variation)

        # Generate files
        gen = FileGenerator(seed=image_seed, volume_size=image_volume_size,
                           cluster_size=self.cluster_size)
        max_data = int(image_volume_size * 0.60)  # Max 60% of volume for data
        files = gen.generate_file_set(
            count=self.files_per_image,
            max_total_bytes=max_data,
        )

        print(f"  Seed: {image_seed}")
        print(f"  Serial: {hex(serial)}")
        print(f"  Volume: {image_volume_size:,} bytes")
        print(f"  Files: {len(files)}")

        # Build NTFS image
        builder = NTFSImageBuilder(
            volume_size=image_volume_size,
            cluster_size=self.cluster_size,
            serial_number=serial,
        )

        # Add files to builder
        for f in files:
            builder.add_file(
                name=f.name,
                data=f.data,
                parent_record=5,  # Root directory
                created=f.created_offset,
                modified=f.modified_offset,
            )

        # Build the image
        image_bytes, layout, built_files = builder.build()

        # Get manifest data
        manifest_data = builder.get_manifest_data()

        # Add file SHA-256 from generator (the builder computed it too)
        for i, f in enumerate(files):
            manifest_data["files"][i]["sha256"] = f.sha256

        # Generate full manifest
        manifest = generate_manifest(
            seed=image_seed,
            filesystem=manifest_data["filesystem"],
            cluster_size=manifest_data["cluster_size"],
            sector_size=manifest_data["sector_size"],
            serial=manifest_data["serial"],
            volume_size=manifest_data["volume_size"],
            total_clusters=manifest_data["total_clusters"],
            files=manifest_data["files"],
            mft_info=manifest_data["mft"],
            bitmap_info=manifest_data["bitmap"],
            mftmirr_info=manifest_data["mftmirr"],
            logfile_info=manifest_data["logfile"],
            data_area_start=manifest_data["data_area_start"],
            metadata={
                "image_index": index,
                "master_seed": self.seed,
                "generator": "RecoveryLab DatasetBuilder v1.0",
                "fragmentation_rate": self.fragmentation_rate,
            },
        )

        # Add integrity hash
        manifest["_integrity_hash"] = compute_integrity_hash(manifest)

        # Save image
        image_path = self.output_dir / f"dataset_{index:03d}.img"
        with open(image_path, 'wb') as f:
            f.write(image_bytes)
        print(f"  Image: {image_path} ({len(image_bytes):,} bytes)")

        # Verify image SHA-256
        with open(image_path, 'rb') as f:
            img_sha256 = hashlib.sha256(f.read()).hexdigest()
        print(f"  Image SHA-256: {img_sha256[:16]}...")

        # Save manifest
        manifest_path = self.output_dir / f"dataset_{index:03d}_manifest.json"
        save_manifest(manifest, manifest_path)
        print(f"  Manifest: {manifest_path}")

        # Verify manifest
        issues = verify_manifest(manifest)
        if issues:
            print(f"  ⚠ Manifest issues: {issues}")
        else:
            print(f"  ✓ Manifest verified")

        return manifest_path

    def _save_dataset_index(self, manifest_paths: List[Path]):
        """Save a dataset index file listing all images and their seeds."""
        index = {
            "version": "1.0",
            "master_seed": self.seed,
            "num_images": self.num_images,
            "volume_size": self.volume_size,
            "cluster_size": self.cluster_size,
            "files_per_image": self.files_per_image,
            "images": [],
        }

        for i, path in enumerate(manifest_paths, 1):
            manifest = load_manifest(path)
            index["images"].append({
                "index": i,
                "image_file": f"dataset_{i:03d}.img",
                "manifest_file": f"dataset_{i:03d}_manifest.json",
                "seed": manifest["seed"],
                "serial": manifest["serial"],
                "volume_size": manifest["volume_size"],
                "file_count": len([f for f in manifest["files"]
                                  if not f.get("is_directory", False)]),
            })

        index_path = self.output_dir / "dataset_index.json"
        with open(index_path, 'w') as f:
            json.dump(index, f, indent=2)

        print(f"\n  Dataset index: {index_path}")


# ─── CLI Entry Point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RecoveryLab Dataset Builder")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                       help="Master seed for reproducibility")
    parser.add_argument("--num-images", type=int, default=DEFAULT_NUM_IMAGES,
                       help="Number of images to generate")
    parser.add_argument("--volume-size", type=int, default=DEFAULT_VOLUME_SIZE,
                       help="Volume size in bytes")
    parser.add_argument("--cluster-size", type=int, default=DEFAULT_CLUSTER_SIZE,
                       help="Cluster size in bytes")
    parser.add_argument("--files-per-image", type=int, default=30,
                       help="Number of files per image")
    parser.add_argument("--output-dir", type=str, default=None,
                       help="Output directory")

    args = parser.parse_args()

    builder = DatasetBuilder(
        seed=args.seed,
        num_images=args.num_images,
        volume_size=args.volume_size,
        cluster_size=args.cluster_size,
        output_dir=Path(args.output_dir) if args.output_dir else None,
        files_per_image=args.files_per_image,
    )

    builder.build_all()
