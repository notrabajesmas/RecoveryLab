"""
RecoveryLab — Manifest Generator
==================================
Generates the enhanced manifest.json for a dataset image.

The manifest is the "true treasure" — without it, we can never know
if the recovery motor got the right answer.
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any


def generate_manifest(
    seed: int,
    filesystem: str,
    cluster_size: int,
    sector_size: int,
    serial: str,
    volume_size: int,
    total_clusters: int,
    files: List[Dict],
    mft_info: Dict,
    bitmap_info: Dict,
    mftmirr_info: Dict,
    logfile_info: Dict,
    data_area_start: int,
    corruption_log: Optional[List[Dict]] = None,
    metadata: Optional[Dict] = None,
) -> Dict:
    """
    Generate the full manifest dictionary.

    This is the enhanced manifest format requested by the user:
    - seed, filesystem, cluster_size, serial, volume_size
    - files with id, name, sha256, size, clusters, fragment_count, is_fragmented, timestamps
    - mft, bitmap structural info
    - Optional corruption_log
    - Optional metadata
    """
    manifest = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "filesystem": filesystem,
        "cluster_size": cluster_size,
        "sector_size": sector_size,
        "serial": serial,
        "volume_size": volume_size,
        "total_clusters": total_clusters,
        "files": files,
        "mft": mft_info,
        "bitmap": bitmap_info,
        "mftmirr": mftmirr_info,
        "logfile": logfile_info,
        "data_area_start": data_area_start,
    }

    if corruption_log:
        manifest["corruption_log"] = corruption_log

    if metadata:
        manifest["metadata"] = metadata

    return manifest


def save_manifest(manifest: Dict, path: Path) -> None:
    """Save manifest to JSON file with pretty formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def load_manifest(path: Path) -> Dict:
    """Load manifest from JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def verify_manifest(manifest: Dict) -> List[str]:
    """
    Verify a manifest is well-formed. Returns list of issues (empty = OK).
    """
    issues = []

    required_keys = ["seed", "filesystem", "cluster_size", "volume_size", "files",
                     "mft", "bitmap"]
    for key in required_keys:
        if key not in manifest:
            issues.append(f"Missing required key: {key}")

    if "files" in manifest:
        for i, f in enumerate(manifest["files"]):
            if "name" not in f:
                issues.append(f"File {i}: missing 'name'")
            if "sha256" not in f and not f.get("is_directory", False):
                issues.append(f"File {i} ({f.get('name', '?')}): missing 'sha256'")
            if "clusters" not in f:
                issues.append(f"File {i} ({f.get('name', '?')}): missing 'clusters'")

    if "mft" in manifest:
        if "start_cluster" not in manifest["mft"]:
            issues.append("MFT info missing 'start_cluster'")

    return issues


def compute_integrity_hash(manifest: Dict) -> str:
    """
    Compute a hash of the manifest content (excluding the hash itself).
    Used to detect if the manifest has been tampered with.
    """
    # Create a copy without the integrity hash
    m = {k: v for k, v in manifest.items() if k != "_integrity_hash"}
    content = json.dumps(m, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(content.encode()).hexdigest()
