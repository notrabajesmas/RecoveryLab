#!/usr/bin/env python3
"""
Build a small example NTFS image for the README quick start.

This image is tiny (~1MB) and contains 5 recognizable files
so a new user can immediately see RecoveryLab working.
"""
import sys
import os
import hashlib
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataset_builder.ntfs_image import NTFSImageBuilder


def build_example():
    examples_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "examples"
    )
    os.makedirs(examples_dir, exist_ok=True)

    builder = NTFSImageBuilder(
        volume_size=1 * 1024 * 1024,  # 1 MB
        cluster_size=4096,
        serial_number=12345,
    )

    # Add a few small recognizable files
    files = [
        ("readme.txt", b"RecoveryLab demo image.\nThis file was recovered successfully.\n"),
        ("photo.jpg", b'\xFF\xD8\xFF\xE0' + b'\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00' + b'\xFF\xD9'),
        ("notes.txt", b"Project notes: sparse file recovery is working.\nNext: compressed files.\n"),
        ("data.json", b'{"version": "0.6.0", "status": "ok", "files_recovered": 5}\n'),
        ("hello.txt", b"Hello from RecoveryLab!\nIf you can read this, recovery worked.\n"),
    ]

    for name, data in files:
        # Pad small files to at least one cluster
        if len(data) < 4096:
            data = data + b'\x00' * (4096 - len(data))
        builder.add_file(name, data)

    image, layout, all_files = builder.build()

    # Save image
    img_path = os.path.join(examples_dir, "demo.img")
    with open(img_path, 'wb') as f:
        f.write(image)
    print(f"Image: {img_path} ({len(image):,} bytes)")

    # Save manifest
    manifest = {
        "version": "1.0",
        "category": "example",
        "num_files": len(files),
        "description": "Small demo image for README quick start. 5 files.",
        "files": [
            {
                "name": name,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "is_directory": False,
            }
            for name, data in files
        ],
    }
    manifest_path = os.path.join(examples_dir, "demo_manifest.json")
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest: {manifest_path}")

    print(f"\n5 files embedded in a {len(image)//1024}KB NTFS image.")
    print("A stranger can now run:")
    print("  recoverylab scan examples/demo.img")
    print("  recoverylab recover examples/demo.img recovered/")


if __name__ == "__main__":
    build_example()
