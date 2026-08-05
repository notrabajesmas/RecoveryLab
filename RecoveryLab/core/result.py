"""
RecoveryLab — Scan Result Types
=================================
Public data types returned by RecoveryEngine.scan().

These are the ONLY types the consumer needs to know about.
No MFT, no Journal, no data runs — just files and scores.

API STABILITY: These types are FROZEN as of v0.5.1.
Changing field names, removing fields, or changing semantics
requires a MAJOR version bump.
Adding new optional fields is OK (minor bump).
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
import time


class FileStatus(Enum):
    """Status of a recovered file."""
    RECOVERED = "recovered"          # Fully recovered, SHA-256 verified
    PARTIAL = "partial"              # Partially recovered (some runs missing)
    METADATA_ONLY = "metadata_only"  # Only metadata, no file data
    DAMAGED = "damaged"              # Data recovered but SHA-256 mismatch
    NOT_RECOVERED = "not_recovered"  # File known but not recovered


class FileSource(Enum):
    """How the file was found."""
    MFT = "mft"                # Found via MFT entry
    JOURNAL = "journal"        # Found via USN Journal
    CARVING = "carving"        # Found via signature carving
    FRAGMENT = "fragment"      # Reconstructed from multiple runs
    HYBRID = "hybrid"          # Found by multiple strategies


@dataclass
class RecoveredItem:
    """A single recovered file — the consumer's view.
    
    This is what the GUI shows in the file list.
    No NTFS internals exposed.
    """
    id: str                          # Unique identifier (e.g., "mft_42")
    name: str                        # Original filename (or carved_XXXX.ext)
    size: int                        # File size in bytes
    status: FileStatus               # Recovery status
    source: FileSource               # How it was found
    confidence: float                # 0.0 - 1.0 how certain we are
    sha256: str = ""                 # SHA-256 hash (empty if not verified)
    path: str = ""                   # Directory path (if known)
    is_fragmented: bool = False      # Was the file split across multiple runs?
    fragment_count: int = 1          # Number of fragments (1 = contiguous)
    
    # Internal reference — NOT exposed to consumers
    _internal_ref: Any = None        # Reference to motor-level data
    _file_data: Optional[bytes] = None  # Cached file data (for recover())
    
    @property
    def is_recovered(self) -> bool:
        """Can this file be saved to disk?"""
        return self.status in (FileStatus.RECOVERED, FileStatus.PARTIAL, FileStatus.DAMAGED)
    
    @property
    def extension(self) -> str:
        """File extension (lowercase, with dot)."""
        if '.' in self.name:
            return '.' + self.name.rsplit('.', 1)[1].lower()
        return ''


@dataclass
class RecoveryCost:
    """Recovery Cost (RC) — how much resources were consumed.
    
    The third dimension of recovery quality:
      RR  — Did we find the file? (Recovery Rate)
      RFS — How well did we recover it? (Fidelity Score)
      RC  — How much did it cost? (Recovery Cost)
    
    Lower RC is better. Strategies declare a cost multiplier,
    but actual cost depends on image size and what was read.
    
    This enables strategy profiles:
      Fast     — minimize RC (skip carving, MFT only)
      Balanced — moderate RC (MFT + Journal, carving only if needed)
      Maximum  — maximize RR+RFS regardless of RC (full pipeline)
    """
    # CPU
    cpu_time_seconds: float = 0.0       # Total CPU time (same as scan_time for single-thread)
    
    # Memory
    peak_ram_mb: float = 0.0            # Peak RAM usage in MB
    
    # I/O
    sectors_read: int = 0               # Total sectors read from image
    sectors_wasted: int = 0             # Sectors read but not used (wasted I/O)
    bytes_scanned: int = 0              # Total bytes scanned (for carving: entire image)
    
    # Strategy cost
    strategy_cost_total: float = 0.0    # Sum of cost multipliers for strategies that ran
    strategies_run: List[str] = field(default_factory=list)  # Which strategies actually ran
    
    @property
    def read_efficiency(self) -> float:
        """Fraction of reads that were useful (0.0 - 1.0)."""
        total = self.sectors_read
        if total == 0:
            return 1.0
        useful = total - self.sectors_wasted
        return max(0.0, useful / total)
    
    @property
    def cost_per_file(self) -> float:
        """Total strategy cost per file (0 if no files)."""
        # This is set externally based on files found
        return self.strategy_cost_total
    
    @property
    def summary(self) -> str:
        """One-line summary for CLI."""
        return (f"RC: {self.cpu_time_seconds:.2f}s CPU, {self.peak_ram_mb:.0f}MB RAM, "
                f"{self.bytes_scanned:,} bytes scanned, "
                f"efficiency={self.read_efficiency:.0%}")


@dataclass
class RecoveryStatistics:
    """Statistics from a scan — the benchmark table per release.
    
    Three dimensions of recovery quality:
      RR  — Did we find the file? (Recovery Rate)
      RFS — How well did we recover it? (Fidelity Score)
      RC  — How much did it cost? (Recovery Cost)
    
    Release notes format:
      RecoveryLab v0.5.2
        Files found: 20  |  Recovered: 20
        RR: 100%  |  RFS: 0.815  |  RC: 0.53s / 116MB / 10.5MB scanned
    """
    # Timing
    scan_time_seconds: float = 0.0
    time_to_first_file: float = 0.0
    
    # Counts
    total_files_found: int = 0
    total_files_recovered: int = 0
    total_files_partial: int = 0
    total_files_damaged: int = 0
    total_files_metadata_only: int = 0
    
    # Fragmentation
    total_fragmented: int = 0
    total_contiguous: int = 0
    total_fragments: int = 0
    
    # Metrics (three dimensions)
    recovery_rate: float = 0.0          # RR: recovered / total
    fidelity_score: float = 0.0         # RFS: weighted 9-component
    quality: float = 0.0                # RR × RFS
    
    # Recovery Cost (third dimension)
    cost: RecoveryCost = field(default_factory=RecoveryCost)
    
    # Legacy fields (backwards-compat, delegated to cost)
    peak_ram_mb: float = 0.0
    sectors_read: int = 0
    sectors_wasted: int = 0
    
    # Strategy breakdown
    by_source: Dict[str, int] = field(default_factory=dict)
    
    @property
    def recovery_cost_score(self) -> float:
        """Normalized RC score (0.0 - 1.0, higher = cheaper).
        
        Computed from read efficiency and strategy cost.
        A score of 1.0 means perfect efficiency (all reads useful, cheap strategies).
        A score of 0.0 means maximum waste.
        """
        efficiency = self.cost.read_efficiency
        # Normalize strategy cost: MFT-only = 1.0 (best), full pipeline = ~13.5 (worst)
        max_reasonable_cost = 15.0
        cost_factor = 1.0 - min(self.cost.strategy_cost_total / max_reasonable_cost, 1.0)
        return 0.5 * efficiency + 0.5 * cost_factor
    
    @property
    def summary(self) -> str:
        """One-line summary for CLI output (RR + RFS + RC)."""
        rc = self.cost
        return (f"{self.total_files_recovered}/{self.total_files_found} files "
                f"(RR={self.recovery_rate:.1%}, RFS={self.fidelity_score:.3f}, "
                f"RC={self.scan_time_seconds:.2f}s/{rc.peak_ram_mb:.0f}MB, "
                f"eff={rc.read_efficiency:.0%})")


@dataclass
class ScanResult:
    """Result of a scan — the top-level object returned by RecoveryEngine.scan().
    
    This is what the consumer gets. Everything they need is here.
    
    API FROZEN v0.5.1 — do not rename or remove fields.
    """
    files: List[RecoveredItem] = field(default_factory=list)
    statistics: RecoveryStatistics = field(default_factory=RecoveryStatistics)
    strategy_used: str = ""              # Which strategy profile was used
    image_path: str = ""                 # Path to the scanned image
    errors: List[str] = field(default_factory=list)
    
    # ── Lookups ──────────────────────────────────────────────
    
    def get_file(self, file_id: str) -> Optional[RecoveredItem]:
        """Look up a file by its unique id (e.g., 'mft_42')."""
        for f in self.files:
            if f.id == file_id:
                return f
        return None
    
    # ── Recovery (consumer-facing API) ──────────────────────
    
    def recover(self, file_id: str, output_dir: str = ".",
                filename: str = None) -> Optional[str]:
        """Recover a single file by id to disk.
        
        This is the primary consumer API — no need to keep
        a reference to RecoveryEngine.
        
        Args:
            file_id: The file's unique identifier (e.g., 'mft_42')
            output_dir: Directory to save to
            filename: Override filename (default: use original name)
        
        Returns:
            Path to saved file, or None if failed
        """
        item = self.get_file(file_id)
        if item is None:
            return None
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
    
    def recover_all(self, output_dir: str = ".",
                     filter_fn=None) -> Dict[str, str]:
        """Recover all (or filtered) files to disk.
        
        Args:
            output_dir: Directory to save to
            filter_fn: Optional callable(RecoveredItem) -> bool
        
        Returns:
            Dict mapping filename -> saved path
        """
        saved = {}
        for item in self.files:
            if not item.is_recovered:
                continue
            if filter_fn and not filter_fn(item):
                continue
            path = self.recover(item.id, output_dir)
            if path:
                saved[item.name] = path
        return saved
    
    # ── Convenience views ───────────────────────────────────
    
    @property
    def recovered_files(self) -> List[RecoveredItem]:
        """Files that can be saved to disk."""
        return [f for f in self.files if f.is_recovered]
    
    @property
    def fragmented_files(self) -> List[RecoveredItem]:
        """Files that were split across multiple runs."""
        return [f for f in self.files if f.is_fragmented]
    
    def by_extension(self) -> Dict[str, List[RecoveredItem]]:
        """Group files by extension."""
        groups: Dict[str, List[RecoveredItem]] = {}
        for f in self.files:
            ext = f.extension
            groups.setdefault(ext, []).append(f)
        return groups
    
    def by_source(self) -> Dict[str, List[RecoveredItem]]:
        """Group files by how they were found."""
        groups: Dict[str, List[RecoveredItem]] = {}
        for f in self.files:
            groups.setdefault(f.source.value, []).append(f)
        return groups
    
    def by_status(self) -> Dict[str, List[RecoveredItem]]:
        """Group files by recovery status."""
        groups: Dict[str, List[RecoveredItem]] = {}
        for f in self.files:
            groups.setdefault(f.status.value, []).append(f)
        return groups
