#!/usr/bin/env python3
"""
RecoveryLab — Permanent Test Corpus Builder
============================================
Builds a permanent, versioned test corpus for regression testing.

Each release runs against this corpus to answer:
    "Does the new version recover at least as much as the previous one?"

Corpus structure:
    datasets/
        ntfs/
            normal/       — contiguous files, no fragmentation
            fragmented/   — files split across multiple data runs
            sparse/       — placeholder (future: v0.6.0)
            compressed/   — placeholder (future: v0.6.1)
            deleted/      — deleted files (journal-recoverable)

Usage:
    python scripts/build_corpus.py
    python scripts/build_corpus.py --category normal
    python scripts/build_corpus.py --force
    python scripts/build_corpus.py --verify
"""

import sys
import os
import json
import hashlib
import time
from pathlib import Path

# Add project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dataset_builder.ntfs_image import NTFSImageBuilder
from dataset_builder.file_generator import FileGenerator


CORPUS_VERSION = "1.0"

CORPUS_CONFIGS = {
    "normal": {
        "num_files": 20,
        "fragmentation_rate": 0.0,
        "description": "Contiguous files, no fragmentation — baseline",
    },
    "fragmented": {
        "num_files": 20,
        "fragmentation_rate": 0.5,
        "description": "50% fragmentation — multi-run files",
    },
    "sparse": {
        "num_files": 10,
        "fragmentation_rate": 0.0,
        "description": "Sparse runs (placeholder)",
        "note": "Will be populated in v0.6.0 when sparse runs are supported",
    },
    "compressed": {
        "num_files": 10,
        "fragmentation_rate": 0.0,
        "description": "Compressed runs (placeholder)",
        "note": "Will be populated in v0.6.1 when compressed runs are supported",
    },
    "deleted": {
        "num_files": 20,
        "fragmentation_rate": 0.0,
        "description": "Deleted files (recoverable via USN Journal)",
    },
}


def build_category(category: str, output_dir: str, force: bool = False):
    """Build one corpus category."""
    config = CORPUS_CONFIGS[category]
    cat_dir = Path(output_dir) / category
    cat_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if already built
    marker = cat_dir / ".corpus_built"
    if marker.exists() and not force:
        existing = json.loads(marker.read_text())
        if existing.get("corpus_version") == CORPUS_VERSION:
            print(f"  [{category}] Already built (v{CORPUS_VERSION}), skipping.")
            return True
    
    # Skip future categories
    if "note" in config:
        print(f"  [{category}] Skipped: {config['note']}")
        marker.write_text(json.dumps({
            "corpus_version": CORPUS_VERSION,
            "category": category,
            "status": "placeholder",
            "note": config["note"],
        }, indent=2))
        return True
    
    print(f"  [{category}] Building {config['num_files']} files "
          f"(fragmentation={config['fragmentation_rate']:.0%})...")
    
    try:
        # Generate file set
        generator = FileGenerator(seed=42)
        generated_files = generator.generate_file_set(
            count=config["num_files"],
            fragmentation_rate=0.0,  # FileGenerator handles format, not fragmentation
        )
        
        # Build NTFS image
        builder = NTFSImageBuilder(
            volume_size=10 * 1024 * 1024,
            fragmentation_rate=config["fragmentation_rate"],
            fragmentation_seed=42,
        )
        
        for gf in generated_files:
            builder.add_file(gf.name, gf.data)
        
        image, layout, files_info = builder.build()
        
        # Build manifest
        manifest_files = []
        for fi in files_info:
            manifest_files.append({
                "name": fi.name,
                "size": len(fi.data) if fi.data else 0,
                "sha256": fi.sha256,
                "is_directory": fi.is_directory,
            })
        
        manifest = {
            "version": "1.0",
            "files": manifest_files,
            "total_files": len(manifest_files),
            "corpus_version": CORPUS_VERSION,
            "category": category,
            "description": config["description"],
            "fragmentation_rate": config["fragmentation_rate"],
        }
        
        # Save image
        img_path = cat_dir / f"corpus_{category}.img"
        img_path.write_bytes(bytes(image))
        
        # Save manifest
        manifest_path = cat_dir / f"corpus_{category}_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))
        
        # Write marker
        marker.write_text(json.dumps({
            "corpus_version": CORPUS_VERSION,
            "category": category,
            "status": "built",
            "image": str(img_path),
            "manifest": str(manifest_path),
            "num_files": len(files_info),
            "fragmentation_rate": config["fragmentation_rate"],
        }, indent=2))
        
        print(f"  [{category}] OK: {img_path.name} ({len(image):,} bytes, {len(files_info)} files)")
        return True
        
    except Exception as e:
        print(f"  [{category}] FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_category(category: str, output_dir: str):
    """Verify one corpus category by running RecoveryEngine against it."""
    from core import RecoveryEngine
    
    cat_dir = Path(output_dir) / category
    img_path = cat_dir / f"corpus_{category}.img"
    manifest_path = cat_dir / f"corpus_{category}_manifest.json"
    
    if not img_path.exists():
        print(f"  [{category}] SKIP: image not found")
        return None
    
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    engine = RecoveryEngine(profile="full")
    result = engine.scan(str(img_path), manifest=manifest)
    
    # Count SHA-256 matches
    manifest_sha = {fi.get("name", ""): fi.get("sha256", "")
                   for fi in manifest.get("files", []) if "sha256" in fi}
    
    verified = 0
    for item in result.files:
        expected = manifest_sha.get(item.name)
        if expected and item.sha256 == expected:
            verified += 1
    
    total = len(manifest_sha)
    rr = verified / total if total > 0 else 0.0
    
    print(f"  [{category}] {verified}/{total} files verified (RR={rr:.1%}, "
          f"time={result.statistics.scan_time_seconds:.2f}s)")
    
    return {
        "category": category,
        "verified": verified,
        "total": total,
        "rr": rr,
        "scan_time": result.statistics.scan_time_seconds,
        "peak_ram": result.statistics.peak_ram_mb,
    }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Build RecoveryLab permanent test corpus")
    parser.add_argument("--category", choices=list(CORPUS_CONFIGS.keys()),
                       help="Build only one category")
    parser.add_argument("--force", action="store_true",
                       help="Rebuild even if already built")
    parser.add_argument("--verify", action="store_true",
                       help="Verify corpus by running RecoveryEngine")
    parser.add_argument("--output", default="datasets/ntfs",
                       help="Output directory (default: datasets/ntfs)")
    
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    output_dir = project_root / args.output
    
    categories = [args.category] if args.category else list(CORPUS_CONFIGS.keys())
    
    if args.verify:
        print(f"RecoveryLab Corpus v{CORPUS_VERSION} — Verification")
        print("=" * 50)
        
        results = []
        for cat in categories:
            r = verify_category(cat, str(output_dir))
            if r:
                results.append(r)
        
        if results:
            print()
            total_verified = sum(r["verified"] for r in results)
            total_files = sum(r["total"] for r in results)
            overall_rr = total_verified / total_files if total_files > 0 else 0
            print(f"  Total verified: {total_verified}/{total_files} (RR={overall_rr:.1%})")
            print(f"  Categories:     {len(results)}/{len(categories)}")
        return 0
    
    print(f"RecoveryLab Corpus v{CORPUS_VERSION} — Builder")
    print("=" * 50)
    print(f"Output: {output_dir}")
    print()
    
    success = 0
    for cat in categories:
        if build_category(cat, str(output_dir), force=args.force):
            success += 1
    
    print()
    print(f"Built {success}/{len(categories)} categories")
    
    # Save corpus manifest
    corpus_manifest = {
        "corpus_version": CORPUS_VERSION,
        "categories": categories,
        "built": success,
        "total": len(categories),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "corpus_manifest.json"
    manifest_path.write_text(json.dumps(corpus_manifest, indent=2))
    
    return 0 if success == len(categories) else 1


if __name__ == "__main__":
    sys.exit(main())
