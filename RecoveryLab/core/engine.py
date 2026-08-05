"""
RecoveryLab — RecoveryEngine (Public API)
==========================================
The single entry point for all recovery operations.

Consumers (CLI, GUI, REST API, plugins) use ONLY this class.
They never import from motors/, ntfs_parser/, or strategies/.

Usage:
    from core import RecoveryEngine

    # Scan an image
    engine = RecoveryEngine()
    result = engine.scan("disk.img")
    
    # Browse results
    for f in result.files:
        print(f.name, f.size, f.confidence, f.status.value)
    
    # Recover specific files
    engine.recover(result.files[0], output_dir="recovered/")
    
    # Recover all
    engine.recover_all(result, output_dir="recovered/")
    
    # Statistics
    print(result.statistics.summary)

Design principles:
  - The consumer never sees NTFS internals (MFT, Journal, data runs)
  - Strategy selection is automatic (or configurable via profile)
  - Results are immutable (ScanResult is a snapshot)
  - Plugins can extend the pipeline without modifying this code
"""

import os
import time
import hashlib
import resource
from pathlib import Path
from typing import Optional, List, Dict, Any

from .result import (
    ScanResult, RecoveredItem, RecoveryStatistics,
    FileStatus, FileSource,
)
from .pipeline import Pipeline, PipelineContext


class RecoveryEngine:
    """
    The public API of the Recovery Engine.
    
    This is what CLI, GUI, and plugins consume.
    """
    
    def __init__(self, profile: str = "mft_first",
                 cluster_size: int = 4096,
                 enable_carving: bool = True,
                 enable_journal: bool = True):
        """
        Initialize the recovery engine.
        
        Args:
            profile: Strategy profile ("mft_first", "journal_first", 
                     "carving_first", "full")
            cluster_size: NTFS cluster size (default 4096)
            enable_carving: Whether to run signature carving (expensive)
            enable_journal: Whether to use USN Journal fallback
        """
        self.profile = profile
        self.cluster_size = cluster_size
        self.enable_carving = enable_carving
        self.enable_journal = enable_journal
        
        # Build the pipeline
        self._pipeline = Pipeline.default()
        
        # Disable stages based on configuration
        if not enable_carving:
            # Remove carving from pipeline
            self._pipeline.remove("carving")
        if not enable_journal:
            self._pipeline.remove("journal")
    
    @property
    def pipeline_stages(self) -> List[str]:
        """List of pipeline stages (for debugging/introspection)."""
        return self._pipeline.stages
    
    def scan(self, image_path: str, manifest: Dict = None) -> ScanResult:
        """
        Scan a disk image and find recoverable files.
        
        This is the main entry point. It:
          1. Reads the image
          2. Runs the pipeline (Detect → Parse → Recover → Score)
          3. Returns a ScanResult with all files and statistics
        
        Args:
            image_path: Path to the disk image file
            manifest: Optional manifest dict (for benchmark comparison)
        
        Returns:
            ScanResult with files, statistics, and errors
        """
        result = ScanResult(image_path=image_path)
        
        # Read image
        try:
            with open(image_path, 'rb') as f:
                image = f.read()
        except FileNotFoundError:
            result.errors.append(f"Image not found: {image_path}")
            return result
        except Exception as e:
            result.errors.append(f"Error reading image: {e}")
            return result
        
        # Measure RAM before
        ram_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # MB
        
        # Run pipeline
        t0 = time.time()
        ctx = self._pipeline.run(image, manifest=manifest, 
                                strategy_profile=self.profile)
        scan_time = time.time() - t0
        
        # Measure RAM after
        ram_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # MB
        peak_ram = max(ram_before, ram_after)
        
        # Convert pipeline results to public types
        for item in ctx.all_recovered:
            source = self._map_source(item.get("source", "mft"))
            status = self._determine_status(item, manifest)
            
            recovered = RecoveredItem(
                id=item["id"],
                name=item["name"],
                size=item["size"],
                status=status,
                source=source,
                confidence=item.get("confidence", 0.0),
                sha256=item.get("sha256", ""),
                is_fragmented=item.get("is_fragmented", False),
                fragment_count=item.get("num_runs", 1),
                _internal_ref=item.get("entry"),
                _file_data=item.get("data"),
            )
            result.files.append(recovered)
        
        # Compute statistics
        stats = self._compute_statistics(result, ctx, scan_time, peak_ram)
        result.statistics = stats
        result.strategy_used = self.profile
        result.errors.extend(ctx.errors)
        
        return result
    
    def scan_bytes(self, image: bytes, manifest: Dict = None) -> ScanResult:
        """
        Scan a disk image from bytes (for programmatic use).
        
        Same as scan() but takes bytes instead of a file path.
        Useful for testing and embedded use.
        """
        result = ScanResult()
        
        ram_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        t0 = time.time()
        ctx = self._pipeline.run(image, manifest=manifest,
                                strategy_profile=self.profile)
        scan_time = time.time() - t0
        ram_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        peak_ram = max(ram_before, ram_after)
        
        for item in ctx.all_recovered:
            source = self._map_source(item.get("source", "mft"))
            status = self._determine_status(item, manifest)
            
            recovered = RecoveredItem(
                id=item["id"],
                name=item["name"],
                size=item["size"],
                status=status,
                source=source,
                confidence=item.get("confidence", 0.0),
                sha256=item.get("sha256", ""),
                is_fragmented=item.get("is_fragmented", False),
                fragment_count=item.get("num_runs", 1),
                _internal_ref=item.get("entry"),
                _file_data=item.get("data"),
            )
            result.files.append(recovered)
        
        stats = self._compute_statistics(result, ctx, scan_time, peak_ram)
        result.statistics = stats
        result.strategy_used = self.profile
        result.errors.extend(ctx.errors)
        
        return result
    
    def recover(self, item: RecoveredItem, output_dir: str = ".",
                filename: str = None) -> Optional[str]:
        """
        Recover a single file to disk.
        
        Args:
            item: The RecoveredItem to save
            output_dir: Directory to save to
            filename: Override filename (default: use original name)
        
        Returns:
            Path to saved file, or None if failed
        """
        if not item.is_recovered:
            return None
        
        if item._file_data is None:
            return None
        
        os.makedirs(output_dir, exist_ok=True)
        out_name = filename or item.name
        out_path = os.path.join(output_dir, out_name)
        
        try:
            with open(out_path, 'wb') as f:
                f.write(item._file_data)
            return out_path
        except Exception:
            return None
    
    def recover_all(self, result: ScanResult, output_dir: str = ".") -> Dict[str, str]:
        """
        Recover all files to disk.
        
        Args:
            result: ScanResult from scan()
            output_dir: Directory to save to
        
        Returns:
            Dict mapping filename -> saved path (only successful recoveries)
        """
        saved = {}
        for item in result.files:
            if item.is_recovered:
                path = self.recover(item, output_dir)
                if path:
                    saved[item.name] = path
        return saved
    
    def _map_source(self, source: str) -> FileSource:
        """Map internal source string to public FileSource enum."""
        mapping = {
            "mft": FileSource.MFT,
            "journal": FileSource.JOURNAL,
            "carving": FileSource.CARVING,
            "fragment": FileSource.FRAGMENT,
            "hybrid": FileSource.HYBRID,
        }
        return mapping.get(source, FileSource.MFT)
    
    def _determine_status(self, item: Dict, manifest: Dict = None) -> FileStatus:
        """Determine file status based on recovery quality."""
        if not item.get("data") or len(item.get("data", b"")) == 0:
            if item.get("name"):
                return FileStatus.METADATA_ONLY
            return FileStatus.NOT_RECOVERED
        
        # If we have a manifest, verify SHA-256
        if manifest:
            manifest_files = {f.get("name$"): f for f in manifest.get("files", [])}
            mf = manifest_files.get(item["name"])
            if mf and mf.get("sha256"):
                if item.get("sha256") == mf["sha256"]:
                    return FileStatus.RECOVERED
                else:
                    return FileStatus.DAMAGED
        
        # No manifest — assume recovered if we have data
        if item.get("is_fragmented") and item.get("num_runs", 1) > 1:
            return FileStatus.RECOVERED  # Could be PARTIAL in future
        return FileStatus.RECOVERED
    
    def _compute_statistics(self, result: ScanResult, ctx: PipelineContext,
                           scan_time: float, peak_ram: float) -> RecoveryStatistics:
        """Compute statistics from pipeline results."""
        stats = RecoveryStatistics()
        
        stats.scan_time_seconds = scan_time
        stats.peak_ram_mb = peak_ram
        stats.recovery_rate = ctx.recovery_rate
        stats.fidelity_score = ctx.fidelity_score
        stats.quality = ctx.recovery_rate * ctx.fidelity_score
        
        # Count by status
        for f in result.files:
            stats.total_files_found += 1
            if f.status == FileStatus.RECOVERED:
                stats.total_files_recovered += 1
            elif f.status == FileStatus.PARTIAL:
                stats.total_files_partial += 1
            elif f.status == FileStatus.DAMAGED:
                stats.total_files_damaged += 1
            elif f.status == FileStatus.METADATA_ONLY:
                stats.total_files_metadata_only += 1
            
            if f.is_fragmented:
                stats.total_fragmented += 1
            else:
                stats.total_contiguous += 1
            stats.total_fragments += f.fragment_count
        
        # Source breakdown
        for f in result.files:
            source = f.source.value
            stats.by_source[source] = stats.by_source.get(source, 0) + 1
        
        # Time to first file
        if "mft" in ctx.stage_times:
            stats.time_to_first_file = ctx.stage_times.get("mft", 0.0)
        
        return stats
