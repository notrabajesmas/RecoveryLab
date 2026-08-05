#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RecoveryLab — Command Line Interface
=====================================
The first way a real user interacts with RecoveryLab.

Usage:
    recoverylab scan disco.img
    recoverylab scan disco.img --json
    recoverylab recover disco.img salida/
    recoverylab recover disco.img salida/ --filter .jpg
    recoverylab info disco.img
"""

import sys
import os
import argparse
import json
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def cmd_scan(args):
    """Scan a disk image and list recoverable files."""
    from core import RecoveryEngine
    
    engine = RecoveryEngine(
        profile=args.profile,
        enable_carving=not args.no_carving,
        enable_journal=not args.no_journal,
    )
    
    # Progress indicator
    print(f"Scanning: {args.image}")
    print(f"Pipeline: {' → '.join(engine.pipeline_stages)}")
    print()
    
    t0 = time.time()
    result = engine.scan(args.image)
    
    if result.errors:
        print("Errors:")
        for err in result.errors:
            print(f"  ⚠ {err}")
        print()
    
    # Output
    if args.json:
        # JSON output (for scripts/pipelines)
        output = {
            "files": [
                {
                    "id": f.id,
                    "name": f.name,
                    "size": f.size,
                    "status": f.status.value,
                    "source": f.source.value,
                    "confidence": f.confidence,
                    "sha256": f.sha256,
                    "is_fragmented": f.is_fragmented,
                    "fragment_count": f.fragment_count,
                }
                for f in result.files
            ],
            "statistics": {
                "total_files_found": result.statistics.total_files_found,
                "total_files_recovered": result.statistics.total_files_recovered,
                "recovery_rate": result.statistics.recovery_rate,
                "fidelity_score": result.statistics.fidelity_score,
                "quality": result.statistics.quality,
                "scan_time_seconds": result.statistics.scan_time_seconds,
                "peak_ram_mb": result.statistics.peak_ram_mb,
                "by_source": result.statistics.by_source,
            },
            "strategy": result.strategy_used,
        }
        print(json.dumps(output, indent=2))
    else:
        # Human-readable output
        _print_scan_result(result)


def cmd_recover(args):
    """Recover files from a disk image."""
    from core import RecoveryEngine
    
    engine = RecoveryEngine(
        profile=args.profile,
        enable_carving=not args.no_carving,
        enable_journal=not args.no_journal,
    )
    
    print(f"Scanning: {args.image}")
    result = engine.scan(args.image)
    
    if result.errors and not result.files:
        print("Scan failed:")
        for err in result.errors:
            print(f"  ⚠ {err}")
        return 1
    
    # Apply filters
    files = result.files
    if args.filter:
        extensions = [e.lower() if e.startswith('.') else f'.{e.lower()}' 
                     for e in args.filter.split(',')]
        files = [f for f in files if f.extension in extensions]
    
    if args.min_confidence:
        files = [f for f in files if f.confidence >= args.min_confidence]
    
    print(f"\nFound {len(result.files)} files, recovering {len(files)} to {args.output_dir}/")
    print()
    
    # Recover
    os.makedirs(args.output_dir, exist_ok=True)
    saved = {}
    for i, f in enumerate(files, 1):
        if not f.is_recovered:
            continue
        path = engine.recover(f, output_dir=args.output_dir)
        if path:
            saved[f.name] = path
            frag = " [fragmented]" if f.is_fragmented else ""
            print(f"  [{i}/{len(files)}] {f.name} ({f.size:,} bytes){frag}")
    
    print(f"\n✅ Recovered {len(saved)}/{len(files)} files to {args.output_dir}/")
    
    # Statistics
    print(f"\n{result.statistics.summary}")
    
    return 0


def cmd_info(args):
    """Show image info without full scan."""
    from core.pipeline import Pipeline, PipelineContext
    from core.stages import DetectStage, NTFSParseStage
    
    try:
        with open(args.image, 'rb') as f:
            image = f.read()
    except FileNotFoundError:
        print(f"Error: {args.image} not found")
        return 1
    
    # Just detect + parse
    pipeline = Pipeline()
    pipeline.add(DetectStage())
    pipeline.add(NTFSParseStage())
    ctx = pipeline.run(image)
    
    print(f"Image: {args.image}")
    print(f"Size:  {len(image):,} bytes ({len(image)/(1024*1024):.1f} MB)")
    print(f"Type:  {ctx.filesystem_type}")
    
    if ctx.ntfs_metadata:
        meta = ctx.ntfs_metadata
        print(f"\nNTFS Metadata:")
        print(f"  MFT entries parsed:  {meta.mft_entries_parsed}")
        print(f"  MFT entries total:   {meta.mft_entries_total}")
        print(f"  Journal entries:     {meta.journal_entries_parsed}")
        print(f"  Deleted files:       {meta.deleted_files_found}")
        print(f"  Parse errors:        {meta.parse_errors}")
    
    return 0


def _print_scan_result(result):
    """Print human-readable scan result."""
    stats = result.statistics
    
    # Summary
    print("═" * 60)
    print("  RecoveryLab — Scan Results")
    print("═" * 60)
    print()
    print(f"  Files found:     {stats.total_files_found}")
    print(f"  Recovered:       {stats.total_files_recovered}")
    print(f"  Partial:         {stats.total_files_partial}")
    print(f"  Damaged:         {stats.total_files_damaged}")
    print(f"  Metadata only:   {stats.total_files_metadata_only}")
    print(f"  Fragmented:      {stats.total_fragmented}")
    print()
    print(f"  RR:   {stats.recovery_rate:.1%}")
    print(f"  RFS:  {stats.fidelity_score:.3f}")
    print(f"  Quality: {stats.quality:.3f}")
    print(f"  Time: {stats.scan_time_seconds:.2f}s")
    print(f"  RAM:  {stats.peak_ram_mb:.1f} MB")
    print()
    
    # Source breakdown
    if stats.by_source:
        print("  By source:")
        for source, count in sorted(stats.by_source.items()):
            print(f"    {source:10s}: {count}")
        print()
    
    # File list
    if result.files:
        print("─" * 60)
        print(f"  {'Name':30s} {'Size':>10s} {'Conf':>5s} {'Source':8s} {'Status':10s}")
        print("─" * 60)
        
        # Sort: recovered first, then by name
        sorted_files = sorted(result.files, key=lambda f: (not f.is_recovered, f.name))
        
        for f in sorted_files[:50]:  # Show first 50
            frag = " *" if f.is_fragmented else ""
            print(f"  {f.name[:30]:30s} {f.size:>10,d} {f.confidence:>5.2f} "
                  f"{f.source.value:8s} {f.status.value:10s}{frag}")
        
        if len(result.files) > 50:
            print(f"  ... and {len(result.files) - 50} more")
        
        print("─" * 60)
        print(f"  * = fragmented file")
    
    print()


def main():
    parser = argparse.ArgumentParser(
        prog="recoverylab",
        description="RecoveryLab — File Recovery Tool",
    )
    parser.add_argument("--version", action="version", version="RecoveryLab v0.5.0")
    
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Scan a disk image for recoverable files")
    scan_parser.add_argument("image", help="Path to disk image")
    scan_parser.add_argument("--json", action="store_true", help="Output as JSON")
    scan_parser.add_argument("--profile", default="mft_first",
                            choices=["mft_first", "journal_first", "carving_first", "full"],
                            help="Strategy profile")
    scan_parser.add_argument("--no-carving", action="store_true", help="Skip signature carving")
    scan_parser.add_argument("--no-journal", action="store_true", help="Skip journal fallback")
    
    # recover
    rec_parser = subparsers.add_parser("recover", help="Recover files from a disk image")
    rec_parser.add_argument("image", help="Path to disk image")
    rec_parser.add_argument("output_dir", help="Output directory for recovered files")
    rec_parser.add_argument("--filter", help="Filter by extension (e.g., .jpg,.png)")
    rec_parser.add_argument("--min-confidence", type=float, default=0.0,
                           help="Minimum confidence threshold (0.0-1.0)")
    rec_parser.add_argument("--profile", default="mft_first",
                           choices=["mft_first", "journal_first", "carving_first", "full"])
    rec_parser.add_argument("--no-carving", action="store_true")
    rec_parser.add_argument("--no-journal", action="store_true")
    
    # info
    info_parser = subparsers.add_parser("info", help="Show image info")
    info_parser.add_argument("image", help="Path to disk image")
    
    args = parser.parse_args()
    
    if args.command == "scan":
        return cmd_scan(args)
    elif args.command == "recover":
        return cmd_recover(args) or 0
    elif args.command == "info":
        return cmd_info(args) or 0
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
