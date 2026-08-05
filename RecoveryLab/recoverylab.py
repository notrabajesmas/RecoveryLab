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
    recoverylab recover disco.img salida/ --filter .jpg,.png
    recoverylab recover disco.img salida/ --min-confidence 0.5
    recoverylab info disco.img
    recoverylab --version
    recoverylab --help
"""

import sys
import os
import argparse
import json
import time
import threading
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

VERSION = "0.6.0"


# ── Progress Spinner ──────────────────────────────────────

class ProgressSpinner:
    """Lightweight spinner for CLI progress indication."""
    
    SYMBOLS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    
    def __init__(self, message="Working"):
        self.message = message
        self._stop = threading.Event()
        self._thread = None
    
    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self
    
    def stop(self, final_message=None):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        if final_message:
            sys.stderr.write(f"\r\033[K  {final_message}\n")
        else:
            sys.stderr.write("\r\033[K")
        sys.stderr.flush()
    
    def _spin(self):
        i = 0
        while not self._stop.is_set():
            sym = self.SYMBOLS[i % len(self.SYMBOLS)]
            sys.stderr.write(f"\r\033[K  {sym} {self.message}...")
            sys.stderr.flush()
            i += 1
            self._stop.wait(0.08)


# ── Error Formatting ──────────────────────────────────────

def _format_error(error_msg: str) -> str:
    """Convert internal error messages to user-friendly form."""
    if "Image not found" in error_msg:
        path = error_msg.split(": ", 1)[1] if ": " in error_msg else ""
        return (f"Cannot find the image file: {path}\n"
                f"  Check that the path is correct and the file exists.")
    if "Permission denied" in error_msg:
        path = error_msg.split(": ", 1)[1] if ": " in error_msg else ""
        return (f"Permission denied: {path}\n"
                f"  Make sure you have read access to the file.")
    if "Not a file" in error_msg:
        path = error_msg.split(": ", 1)[1] if ": " in error_msg else ""
        return (f"Not a regular file: {path}\n"
                f"  Provide a path to a disk image file (not a directory).")
    if "Image is empty" in error_msg:
        return "The image file is empty (0 bytes). It may be corrupted or truncated."
    if "Unknown filesystem type" in error_msg:
        return ("Unrecognized filesystem format.\n"
                "  RecoveryLab currently supports NTFS. FAT32 and exFAT are planned.")
    return error_msg


def _print_banner():
    """Print RecoveryLab identity banner."""
    print(f"RecoveryLab v{VERSION}")
    print("Filesystem Recovery Engine")


def _print_errors(errors):
    """Print errors in user-friendly form."""
    for err in errors:
        formatted = _format_error(err)
        lines = formatted.split("\n")
        print(f"  Error: {lines[0]}", file=sys.stderr)
        for line in lines[1:]:
            print(f"  {line}", file=sys.stderr)


# ── Commands ──────────────────────────────────────────────

def cmd_scan(args):
    """Scan a disk image and list recoverable files."""
    from core import RecoveryEngine
    
    # Validate image exists before creating engine
    if not os.path.exists(args.image):
        print(f"Error: Cannot find '{args.image}'", file=sys.stderr)
        print(f"  Check that the path is correct and the file exists.", file=sys.stderr)
        return 1
    
    engine = RecoveryEngine(
        profile=args.profile,
        enable_carving=not args.no_carving,
        enable_journal=not args.no_journal,
    )
    
    # Show what we're doing
    _print_banner()
    print(f"Scanning: {args.image}")
    print(f"Profile:  {args.profile}")
    print(f"Pipeline: {' → '.join(engine.pipeline_stages)}")
    print()
    
    # Run scan with progress spinner
    spinner = ProgressSpinner("Scanning image").start()
    t0 = time.time()
    result = engine.scan(args.image)
    elapsed = time.time() - t0
    spinner.stop(f"Scan completed in {elapsed:.2f}s")
    print()
    
    # Handle errors
    if result.errors:
        if not result.files:
            print("Scan failed:", file=sys.stderr)
            _print_errors(result.errors)
            return 1
        else:
            print("Warnings:")
            for err in result.errors:
                print(f"  ⚠ {err}")
            print()
    
    # Output
    if args.json:
        _print_json_result(result)
    else:
        _print_scan_result(result)
    
    return 0


def cmd_recover(args):
    """Recover files from a disk image."""
    from core import RecoveryEngine
    
    # Validate inputs
    if not os.path.exists(args.image):
        print(f"Error: Cannot find '{args.image}'", file=sys.stderr)
        print(f"  Check that the path is correct and the file exists.", file=sys.stderr)
        return 1
    
    engine = RecoveryEngine(
        profile=args.profile,
        enable_carving=not args.no_carving,
        enable_journal=not args.no_journal,
    )
    
    _print_banner()
    print(f"Scanning: {args.image}")
    
    # Scan with progress
    spinner = ProgressSpinner("Scanning image").start()
    result = engine.scan(args.image)
    spinner.stop()
    
    # Handle scan errors
    if result.errors and not result.files:
        print("Scan failed:", file=sys.stderr)
        _print_errors(result.errors)
        return 1
    
    # Apply filters
    files = result.files
    if args.filter:
        extensions = [e.lower() if e.startswith('.') else f'.{e.lower()}' 
                     for e in args.filter.split(',')]
        files = [f for f in files if f.extension in extensions]
    
    if args.min_confidence:
        files = [f for f in files if f.confidence >= args.min_confidence]
    
    recoverable = [f for f in files if f.is_recovered]
    print(f"\nFound {len(result.files)} files, recovering {len(recoverable)} to {args.output_dir}/")
    print()
    
    # Recover with progress
    os.makedirs(args.output_dir, exist_ok=True)
    saved = {}
    for i, f in enumerate(recoverable, 1):
        path = result.recover(f.id, output_dir=args.output_dir)
        if path:
            saved[f.name] = path
            frag = " [fragmented]" if f.is_fragmented else ""
            conf_bar = "█" * int(f.confidence * 5) + "░" * (5 - int(f.confidence * 5))
            print(f"  [{i:>3d}/{len(recoverable)}] {f.name:<35s} {f.size:>10,d} bytes  {conf_bar} {f.confidence:.2f}{frag}")
    
    # Final statistics
    print()
    print("═" * 60)
    print("  Recovery Summary")
    print("═" * 60)
    stats = result.statistics
    print(f"  Files found:      {stats.total_files_found}")
    print(f"  Files recovered:  {len(saved)}")
    print(f"  RR:               {stats.recovery_rate:.1%}")
    print(f"  RFS (avg):        {stats.fidelity_score:.3f}")
    print(f"  Quality:          {stats.quality:.3f}")
    print(f"  RC score:         {stats.recovery_cost_score:.3f}")
    print(f"  Total time:       {stats.scan_time_seconds:.2f}s")
    print(f"  Peak RAM:         {stats.peak_ram_mb:.1f} MB")
    if stats.cost.bytes_scanned > 0:
        print(f"  Bytes scanned:    {stats.cost.bytes_scanned:,}")
    print(f"  Strategies run:   {', '.join(stats.cost.strategies_run)}")
    print("═" * 60)
    
    return 0


def cmd_info(args):
    """Show image info without full scan."""
    if not os.path.exists(args.image):
        print(f"Error: Cannot find '{args.image}'", file=sys.stderr)
        return 1
    
    try:
        with open(args.image, 'rb') as f:
            image = f.read()
    except PermissionError:
        print(f"Error: Permission denied: {args.image}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return 1
    
    from core.pipeline import Pipeline, PipelineContext
    from core.stages import DetectStage, NTFSParseStage
    
    # Just detect + parse
    pipeline = Pipeline()
    pipeline.add(DetectStage())
    pipeline.add(NTFSParseStage())
    ctx = pipeline.run(image)
    
    _print_banner()
    print(f"Image:  {args.image}")
    print(f"Size:   {len(image):,} bytes ({len(image)/(1024*1024):.1f} MB)")
    print(f"Type:   {ctx.filesystem_type}")
    
    if ctx.ntfs_metadata:
        meta = ctx.ntfs_metadata
        print(f"\nNTFS Metadata:")
        print(f"  MFT entries parsed:  {meta.mft_entries_parsed}")
        print(f"  MFT entries total:   {meta.mft_entries_total}")
        print(f"  Journal entries:     {meta.journal_entries_parsed}")
        print(f"  Deleted files:       {meta.deleted_files_found}")
        print(f"  Parse errors:        {meta.parse_errors}")
    elif ctx.filesystem_type == "UNKNOWN":
        print(f"\n  Unrecognized filesystem. RecoveryLab currently supports NTFS.")
        print(f"  FAT32 and exFAT support is planned for a future release.")
    
    return 0


# ── Output Formatters ─────────────────────────────────────

def _print_json_result(result):
    """Print scan result as JSON (for scripts/pipelines)."""
    output = {
        "version": VERSION,
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
            "total_files_partial": result.statistics.total_files_partial,
            "total_files_damaged": result.statistics.total_files_damaged,
            "recovery_rate": result.statistics.recovery_rate,
            "fidelity_score": result.statistics.fidelity_score,
            "quality": result.statistics.quality,
            "scan_time_seconds": result.statistics.scan_time_seconds,
            "peak_ram_mb": result.statistics.peak_ram_mb,
            "by_source": result.statistics.by_source,
        },
        "strategy": result.strategy_used,
        "image_path": result.image_path,
    }
    print(json.dumps(output, indent=2))


def _print_scan_result(result):
    """Print human-readable scan result."""
    stats = result.statistics
    
    # Summary box
    print("═" * 60)
    print(f"  RecoveryLab v{VERSION} — Scan Results")
    print("═" * 60)
    print()
    print(f"  Files found:     {stats.total_files_found}")
    print(f"  Recovered:       {stats.total_files_recovered}")
    if stats.total_files_partial:
        print(f"  Partial:         {stats.total_files_partial}")
    if stats.total_files_damaged:
        print(f"  Damaged:         {stats.total_files_damaged}")
    if stats.total_files_metadata_only:
        print(f"  Metadata only:   {stats.total_files_metadata_only}")
    if stats.total_fragmented:
        print(f"  Fragmented:      {stats.total_fragmented}")
    print()
    print(f"  RR:       {stats.recovery_rate:.1%}")
    print(f"  RFS:      {stats.fidelity_score:.3f}")
    print(f"  Quality:  {stats.quality:.3f}")
    print(f"  RC:       {stats.cost.summary}")
    print(f"  Time:     {stats.scan_time_seconds:.2f}s")
    print(f"  RAM:      {stats.peak_ram_mb:.1f} MB")
    print(f"  RC score: {stats.recovery_cost_score:.3f}")
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
            print(f"  ... and {len(result.files) - 50} more (use --json for full list)")
        
        print("─" * 60)
        print(f"  * = fragmented file")
    
    print()


# ── Demo Command ─────────────────────────────────────────

def cmd_demo(args):
    """Create a demo NTFS image, scan it, and recover files.
    
    This lets a first-time user see RecoveryLab in action
    without needing a real disk image.
    """
    import tempfile
    import shutil
    from dataset_builder.ntfs_image import NTFSImageBuilder
    from core import RecoveryEngine
    
    print(f"RecoveryLab v{VERSION}")
    print("Filesystem Recovery Engine")
    print()
    print("Creating demo NTFS image with sample files...")
    
    # Build a tiny image with recognizable files
    builder = NTFSImageBuilder(
        volume_size=1 * 1024 * 1024,  # 1 MB
        cluster_size=4096,
        serial_number=42,
    )
    
    sample_files = [
        ("readme.txt",     b"RecoveryLab demo image.\nThis file was recovered successfully.\n"),
        ("report.txt",     b"Quarterly Report Q3 2026\nRevenue: $1.2M\nGrowth: 15%\n"),
        ("hello.txt",      b"Hello from RecoveryLab!\nIf you can read this, recovery worked.\n"),
        ("data.json",      b'{"version": "0.6.0", "status": "ok", "files": 3}\n'),
    ]
    
    for name, data in sample_files:
        if len(data) < 4096:
            data = data + b'\x00' * (4096 - len(data))
        builder.add_file(name, data)
    
    image, layout, all_files = builder.build()
    
    # Write image to temp file
    tmp_dir = tempfile.mkdtemp(prefix="recoverylab_demo_")
    img_path = os.path.join(tmp_dir, "demo.img")
    output_dir = os.path.join(tmp_dir, "recovered")
    
    with open(img_path, 'wb') as f:
        f.write(image)
    
    print(f"  {len(image):,} bytes, {len(sample_files)} files embedded")
    print()
    
    # Scan
    print("Scanning image...")
    engine = RecoveryEngine(profile="mft_first")
    result = engine.scan(img_path)
    
    user_files = [f for f in result.files if not f.name.startswith('$')]
    
    print(f"  Found {len(user_files)} recoverable files (RR={result.statistics.recovery_rate:.0%})")
    print()
    
    # Recover
    os.makedirs(output_dir, exist_ok=True)
    print("Recovering files...")
    
    recovered_names = []
    for f in user_files:
        result.recover(f.id, output_dir=output_dir)
        recovered_names.append(f.name)
    
    print()
    print("Recovery completed.")
    print()
    print("Recovered files:")
    for name in recovered_names:
        print(f"  + {name}")
    
    # Show content of one file
    for name, _ in sample_files[:1]:
        fpath = os.path.join(output_dir, name)
        if os.path.exists(fpath):
            with open(fpath, 'rb') as f:
                content = f.read(200).rstrip(b'\x00').decode('utf-8', errors='replace')
            print()
            print(f"Content of {name}:")
            for line in content.split('\n'):
                if line:
                    print(f"  {line}")
    
    print()
    print("Output directory:")
    if args.keep:
        keep_dir = os.path.join(os.getcwd(), "recoverylab_demo")
        os.makedirs(keep_dir, exist_ok=True)
        shutil.copy2(img_path, os.path.join(keep_dir, "demo.img"))
        shutil.copytree(output_dir, os.path.join(keep_dir, "recovered"), dirs_exist_ok=True)
        print(f"  {keep_dir}/recovered/")
    else:
        print(f"  {output_dir}")
    
    print()
    print("Next steps:")
    print("  recoverylab scan mydisk.img")
    print("  recoverylab recover mydisk.img recovered/")
    
    # Cleanup
    if not args.keep:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    
    return 0


# ── Main ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="recoverylab",
        description="RecoveryLab — NTFS File Recovery Tool\n\n"
                    "Recover deleted or lost files from NTFS disk images.\n"
                    "Supports MFT parsing, USN Journal, signature carving,\n"
                    "and fragmented file reconstruction.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  recoverylab scan disk.img                    Scan and list recoverable files
  recoverylab scan disk.img --json             Output as JSON (for scripts)
  recoverylab scan disk.img --no-carving       Skip carving (faster scan)
  recoverylab recover disk.img output/         Recover all files to output/
  recoverylab recover disk.img output/ --filter .jpg,.png   Only JPEG and PNG
  recoverylab recover disk.img output/ --min-confidence 0.8  Only high-confidence
  recoverylab info disk.img                    Show image metadata

Supported formats (carving):
  JPEG, PNG, PDF, ZIP, MP4, DOCX, TIFF, CR2, NEF, MOV,
  XLSX, SQLite, GIF, BMP, RAR, 7Z, PSD, DNG, HEIC, AVI

Strategy profiles:
  fast           MFT only (fastest, lowest RC)
  balanced       MFT + Journal (moderate RC, no carving)
  mft_first      MFT → Journal → Carving (default, good balance)
  journal_first  Journal → MFT → Carving (best for deleted files)
  carving_first  Carving → MFT → Journal (most thorough, slowest)
  full           MFT → Journal → Fragment → Carving (complete)
  maximum        Same as full — all strategies (highest RR+RFS, highest RC)
""",
    )
    parser.add_argument("--version", action="version", version=f"RecoveryLab v{VERSION}")
    
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # scan
    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan a disk image for recoverable files",
        description="Scan an NTFS disk image and list all recoverable files with metadata.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Output includes filename, size, confidence, source, and recovery status.",
    )
    scan_parser.add_argument("image", help="Path to disk image file")
    scan_parser.add_argument("--json", action="store_true",
                            help="Output as JSON (for scripts and pipelines)")
    scan_parser.add_argument("--profile", default="mft_first",
                            choices=["fast", "balanced", "mft_first", "journal_first", "carving_first", "full", "maximum"],
                            help="Strategy profile (default: mft_first)")
    scan_parser.add_argument("--no-carving", action="store_true",
                            help="Skip signature carving (much faster, may miss some files)")
    scan_parser.add_argument("--no-journal", action="store_true",
                            help="Skip USN Journal fallback (faster, may miss deleted files)")
    
    # recover
    rec_parser = subparsers.add_parser(
        "recover",
        help="Recover files from a disk image",
        description="Scan an image and save recoverable files to an output directory.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Recovered files are written to the output directory with original filenames.",
    )
    rec_parser.add_argument("image", help="Path to disk image file")
    rec_parser.add_argument("output_dir", help="Output directory for recovered files")
    rec_parser.add_argument("--filter",
                            help="Filter by extension, comma-separated (e.g., .jpg,.png,.pdf)")
    rec_parser.add_argument("--min-confidence", type=float, default=0.0,
                           help="Minimum confidence threshold 0.0-1.0 (default: 0.0)")
    rec_parser.add_argument("--profile", default="mft_first",
                           choices=["fast", "balanced", "mft_first", "journal_first", "carving_first", "full", "maximum"],
                           help="Strategy profile (default: mft_first)")
    rec_parser.add_argument("--no-carving", action="store_true",
                            help="Skip signature carving")
    rec_parser.add_argument("--no-journal", action="store_true",
                            help="Skip USN Journal fallback")
    
    # info
    info_parser = subparsers.add_parser(
        "info",
        help="Show image metadata (no scan)",
        description="Quick image info: filesystem type, size, MFT/Journal metadata.",
    )
    info_parser.add_argument("image", help="Path to disk image file")
    
    # demo
    demo_parser = subparsers.add_parser(
        "demo",
        help="Create a demo image and scan it (try RecoveryLab now!)",
        description="Generates a small NTFS image with sample files, scans it, and recovers them. "
                    "Perfect for first-time users who want to see RecoveryLab in action.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="This creates demo.img and a recovered/ folder in the current directory.",
    )
    demo_parser.add_argument("--keep", action="store_true",
                            help="Keep the generated image after recovery (default: clean up)")
    
    args = parser.parse_args()
    
    if args.command == "scan":
        return cmd_scan(args)
    elif args.command == "recover":
        return cmd_recover(args) or 0
    elif args.command == "info":
        return cmd_info(args) or 0
    elif args.command == "demo":
        return cmd_demo(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
