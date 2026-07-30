"""
RecoveryLab — Corruption Models
=================================
Real-world failure patterns, not random corruption.

Each model is based on how actual drives fail:
  - Head crash: first/last sectors damaged
  - Scratch: continuous zone of damage
  - Intermittent: every Nth sector fails
  - MFT partial: entries zeroed out
  - Bitmap corruption: allocation data lost
  - CRC errors: bit flips in data
  - Slow sectors: metadata marking (for simulation)
  - Timeout: metadata marking (for simulation)

Every corruption is logged exactly — reproducibility is paramount.
"""

import random
import hashlib
import struct
import copy
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
from pathlib import Path


class CorruptionType(Enum):
    """Types of corruption that can be applied."""
    HEAD_CRASH_START = "head_crash_start"
    HEAD_CRASH_END = "head_crash_end"
    SCRATCH_CONTINUOUS = "scratch_continuous"
    INTERMITTENT_SECTORS = "intermittent_sectors"
    MFT_PARTIAL_DELETE = "mft_partial_delete"
    BITMAP_CORRUPTION = "bitmap_corruption"
    JOURNAL_CORRUPTION = "journal_corruption"
    CRC_ERRORS = "crc_errors"
    SLOW_SECTORS = "slow_sectors"
    TIMEOUT_PATTERN = "timeout_pattern"


@dataclass
class CorruptionEntry:
    """A single corruption operation applied to the image."""
    type: CorruptionType
    description: str
    sectors_affected: List[int]       # Absolute sector numbers
    clusters_affected: List[int]      # Absolute cluster numbers
    byte_range: Tuple[int, int]       # (start, end) byte offsets
    severity: float                    # 0.0-1.0
    details: Dict = field(default_factory=dict)  # Additional info


@dataclass
class CorruptionResult:
    """Result of applying corruption to an image."""
    corrupted_image: bytes
    corruption_log: List[CorruptionEntry]
    manifest_corruption: Dict   # Corruption info to add to manifest


class CorruptionModel:
    """Base class for all corruption models."""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.seed = seed

    def apply(self, image: bytearray, manifest: Dict) -> CorruptionResult:
        """Apply corruption to image. Must be overridden."""
        raise NotImplementedError

    def _log_entry(self, ctype: CorruptionType, desc: str,
                   sectors: List[int], clusters: List[int],
                   byte_range: Tuple[int, int], severity: float,
                   details: Dict = None) -> CorruptionEntry:
        return CorruptionEntry(
            type=ctype,
            description=desc,
            sectors_affected=sectors,
            clusters_affected=clusters,
            byte_range=byte_range,
            severity=severity,
            details=details or {},
        )


# ─── Concrete Models ──────────────────────────────────────────────────────────

class HeadCrashStartModel(CorruptionModel):
    """First sectors damaged — head crash at start of platter."""

    def apply(self, image: bytearray, manifest: Dict,
              severity: float = 0.05) -> CorruptionResult:
        total_sectors = len(image) // 512
        affected = int(total_sectors * severity)
        start_sector = 0
        end_sector = affected

        # Zero out sectors (simulating unreadable data)
        for s in range(start_sector, end_sector):
            offset = s * 512
            image[offset:offset+512] = b'\x00' * 512

        sectors = list(range(start_sector, end_sector))
        clusters = list(set(s // (manifest["cluster_size"] // 512) for s in sectors))

        log = [self._log_entry(
            CorruptionType.HEAD_CRASH_START,
            f"Head crash at start: sectors 0-{end_sector-1} ({affected} sectors)",
            sectors, clusters, (0, end_sector * 512),
            severity,
            {"pattern": "first_sectors", "affected_sectors": affected},
        )]

        return CorruptionResult(
            corrupted_image=bytes(image),
            corruption_log=log,
            manifest_corruption={
                "type": "head_crash_start",
                "severity": severity,
                "sectors_affected": affected,
                "clusters_affected": len(clusters),
            },
        )


class HeadCrashEndModel(CorruptionModel):
    """Last sectors damaged — end of platter."""

    def apply(self, image: bytearray, manifest: Dict,
              severity: float = 0.05) -> CorruptionResult:
        total_sectors = len(image) // 512
        affected = int(total_sectors * severity)
        start_sector = total_sectors - affected

        for s in range(start_sector, total_sectors):
            offset = s * 512
            image[offset:offset+512] = b'\x00' * 512

        sectors = list(range(start_sector, total_sectors))
        clusters = list(set(s // (manifest["cluster_size"] // 512) for s in sectors))

        log = [self._log_entry(
            CorruptionType.HEAD_CRASH_END,
            f"Head crash at end: sectors {start_sector}-{total_sectors-1}",
            sectors, clusters,
            (start_sector * 512, total_sectors * 512),
            severity,
            {"pattern": "last_sectors", "affected_sectors": affected},
        )]

        return CorruptionResult(
            corrupted_image=bytes(image),
            corruption_log=log,
            manifest_corruption={
                "type": "head_crash_end",
                "severity": severity,
                "sectors_affected": affected,
            },
        )


class ScratchContinuousModel(CorruptionModel):
    """Continuous zone of damage — scratch across platter."""

    def apply(self, image: bytearray, manifest: Dict,
              severity: float = 0.05,
              position: Optional[float] = None) -> CorruptionResult:
        total_sectors = len(image) // 512
        affected = int(total_sectors * severity)

        # Position: where the scratch starts (0.0-1.0)
        if position is None:
            position = self.rng.uniform(0.1, 0.8)

        start_sector = int(total_sectors * position)
        end_sector = min(start_sector + affected, total_sectors)

        for s in range(start_sector, end_sector):
            offset = s * 512
            image[offset:offset+512] = b'\x00' * 512

        sectors = list(range(start_sector, end_sector))
        clusters = list(set(s // (manifest["cluster_size"] // 512) for s in sectors))

        log = [self._log_entry(
            CorruptionType.SCRATCH_CONTINUOUS,
            f"Scratch at {position:.0%}: sectors {start_sector}-{end_sector-1}",
            sectors, clusters,
            (start_sector * 512, end_sector * 512),
            severity,
            {"pattern": "continuous", "position": position,
             "start_sector": start_sector, "end_sector": end_sector},
        )]

        return CorruptionResult(
            corrupted_image=bytes(image),
            corruption_log=log,
            manifest_corruption={
                "type": "scratch_continuous",
                "severity": severity,
                "position": position,
                "sectors_affected": affected,
            },
        )


class IntermittentSectorsModel(CorruptionModel):
    """Every Nth sector fails — failing head."""

    def apply(self, image: bytearray, manifest: Dict,
              severity: float = 0.02,
              interval: Optional[int] = None) -> CorruptionResult:
        total_sectors = len(image) // 512
        if interval is None:
            interval = max(1, int(1.0 / severity))

        affected_sectors = []
        for s in range(0, total_sectors, interval):
            offset = s * 512
            image[offset:offset+512] = b'\x00' * 512
            affected_sectors.append(s)

        clusters = list(set(s // (manifest["cluster_size"] // 512)
                          for s in affected_sectors))

        log = [self._log_entry(
            CorruptionType.INTERMITTENT_SECTORS,
            f"Intermittent failure: every {interval}th sector zeroed",
            affected_sectors, clusters,
            (0, len(image)),
            severity,
            {"pattern": "intermittent", "interval": interval,
             "affected_count": len(affected_sectors)},
        )]

        return CorruptionResult(
            corrupted_image=bytes(image),
            corruption_log=log,
            manifest_corruption={
                "type": "intermittent_sectors",
                "severity": severity,
                "interval": interval,
                "affected_count": len(affected_sectors),
            },
        )


class MFTPartialDeleteModel(CorruptionModel):
    """Partial MFT deletion — 20%/40%/60% of MFT entries zeroed."""

    def apply(self, image: bytearray, manifest: Dict,
              severity: float = 0.40) -> CorruptionResult:
        mft_info = manifest["mft"]
        mft_start = mft_info["start_cluster"]
        cluster_size = manifest["cluster_size"]
        record_size = mft_info.get("record_size", 1024)
        records_per_cluster = cluster_size // record_size

        # Determine which MFT records to delete
        # System records (0-11) are protected — we delete user records
        total_user_records = len([f for f in manifest["files"]
                                 if f.get("id", 0) >= 12])
        num_to_delete = int(total_user_records * severity)

        # Select which records to delete (deterministic)
        user_record_ids = [f["id"] for f in manifest["files"]
                          if f.get("id", 0) >= 12]
        self.rng.shuffle(user_record_ids)
        to_delete = user_record_ids[:num_to_delete]

        # Zero out the selected MFT records
        affected_clusters = set()
        for rec_id in to_delete:
            # Calculate byte offset
            byte_offset = (mft_start * cluster_size) + (rec_id * record_size)
            image[byte_offset:byte_offset+record_size] = b'\x00' * record_size

            # Determine cluster
            cluster = mft_start + (rec_id * record_size) // cluster_size
            affected_clusters.add(cluster)

        # Also delete the "FILE" signature for these records
        deleted_names = []
        for f in manifest["files"]:
            if f.get("id", 0) in to_delete:
                deleted_names.append(f["name"])

        log = [self._log_entry(
            CorruptionType.MFT_PARTIAL_DELETE,
            f"MFT partial delete: {num_to_delete}/{total_user_records} entries zeroed ({severity:.0%})",
            [], list(affected_clusters),
            (mft_start * cluster_size, mft_start * cluster_size + len(manifest["files"]) * record_size),
            severity,
            {"deleted_record_ids": to_delete,
             "deleted_names": deleted_names,
             "mft_start_cluster": mft_start},
        )]

        return CorruptionResult(
            corrupted_image=bytes(image),
            corruption_log=log,
            manifest_corruption={
                "type": "mft_partial_delete",
                "severity": severity,
                "records_deleted": num_to_delete,
                "total_user_records": total_user_records,
                "deleted_record_ids": to_delete,
            },
        )


class BitmapCorruptionModel(CorruptionModel):
    """Bitmap partially or fully zeroed."""

    def apply(self, image: bytearray, manifest: Dict,
              severity: float = 0.50) -> CorruptionResult:
        bitmap_info = manifest["bitmap"]
        bitmap_start = bitmap_info["start_cluster"]
        cluster_size = manifest["cluster_size"]
        bitmap_clusters = bitmap_info.get("clusters", [bitmap_start])
        bitmap_byte_count = len(bitmap_clusters) * cluster_size

        bitmap_offset = bitmap_start * cluster_size

        if severity >= 1.0:
            # Full bitmap deletion
            image[bitmap_offset:bitmap_offset+bitmap_byte_count] = b'\x00' * bitmap_byte_count
        else:
            # Partial: zero out a fraction of the bitmap
            zero_bytes = int(bitmap_byte_count * severity)
            start_byte = self.rng.randint(0, bitmap_byte_count - zero_bytes)
            image[bitmap_offset+start_byte:bitmap_offset+start_byte+zero_bytes] = b'\x00' * zero_bytes

        log = [self._log_entry(
            CorruptionType.BITMAP_CORRUPTION,
            f"Bitmap corruption: {severity:.0%} zeroed",
            [], [bitmap_start],
            (bitmap_offset, bitmap_offset + bitmap_byte_count),
            severity,
            {"bitmap_start_cluster": bitmap_start,
             "bitmap_bytes": bitmap_byte_count,
             "fully_zeroed": severity >= 1.0},
        )]

        return CorruptionResult(
            corrupted_image=bytes(image),
            corruption_log=log,
            manifest_corruption={
                "type": "bitmap_corruption",
                "severity": severity,
            },
        )


class JournalCorruptionModel(CorruptionModel):
    """Journal ($LogFile) corrupted."""

    def apply(self, image: bytearray, manifest: Dict,
              severity: float = 1.0) -> CorruptionResult:
        logfile_info = manifest.get("logfile", {})
        logfile_start = logfile_info.get("start_cluster", 0)
        if logfile_start == 0:
            # No logfile info — skip
            return CorruptionResult(
                corrupted_image=bytes(image),
                corruption_log=[],
                manifest_corruption={"type": "journal_corruption", "skipped": True},
            )

        cluster_size = manifest["cluster_size"]
        logfile_clusters = logfile_info.get("clusters", [logfile_start])
        logfile_byte_count = len(logfile_clusters) * cluster_size
        logfile_offset = logfile_start * cluster_size

        if severity >= 1.0:
            # Full corruption
            # Write random data instead of zeros (more realistic for journal corruption)
            random_data = bytes(self.rng.getrandbits(8) for _ in range(logfile_byte_count))
            image[logfile_offset:logfile_offset+logfile_byte_count] = random_data
        else:
            zero_bytes = int(logfile_byte_count * severity)
            start_byte = self.rng.randint(0, max(0, logfile_byte_count - zero_bytes))
            random_data = bytes(self.rng.getrandbits(8) for _ in range(zero_bytes))
            image[logfile_offset+start_byte:logfile_offset+start_byte+zero_bytes] = random_data

        log = [self._log_entry(
            CorruptionType.JOURNAL_CORRUPTION,
            f"Journal corruption: {severity:.0%} corrupted",
            [], logfile_clusters,
            (logfile_offset, logfile_offset + logfile_byte_count),
            severity,
            {"logfile_start_cluster": logfile_start},
        )]

        return CorruptionResult(
            corrupted_image=bytes(image),
            corruption_log=log,
            manifest_corruption={
                "type": "journal_corruption",
                "severity": severity,
            },
        )


class CRCErrorsModel(CorruptionModel):
    """Random bit flips in data sectors — CRC errors."""

    def apply(self, image: bytearray, manifest: Dict,
              severity: float = 0.005) -> CorruptionResult:
        total_sectors = len(image) // 512
        num_affected = int(total_sectors * severity)

        # Choose random sectors to corrupt
        affected_sectors = self.rng.sample(range(total_sectors), num_affected)

        for s in affected_sectors:
            offset = s * 512
            # Flip 1-4 random bits in the sector
            num_flips = self.rng.randint(1, 4)
            for _ in range(num_flips):
                byte_pos = self.rng.randint(0, 511)
                bit_pos = self.rng.randint(0, 7)
                image[offset + byte_pos] ^= (1 << bit_pos)

        clusters = list(set(s // (manifest["cluster_size"] // 512)
                          for s in affected_sectors))

        log = [self._log_entry(
            CorruptionType.CRC_ERRORS,
            f"CRC errors: {num_affected} sectors with bit flips",
            affected_sectors, clusters,
            (0, len(image)),
            severity,
            {"pattern": "bit_flips", "affected_count": num_affected,
             "flips_per_sector": "1-4"},
        )]

        return CorruptionResult(
            corrupted_image=bytes(image),
            corruption_log=log,
            manifest_corruption={
                "type": "crc_errors",
                "severity": severity,
                "affected_sectors": num_affected,
            },
        )


class SlowSectorsModel(CorruptionModel):
    """
    Sectors marked as slow — metadata-based simulation.

    This doesn't modify the image bytes. Instead, it creates a metadata
    file that the recovery motors can read to simulate slow sectors.
    """

    def apply(self, image: bytearray, manifest: Dict,
              severity: float = 0.02) -> CorruptionResult:
        total_sectors = len(image) // 512
        num_slow = int(total_sectors * severity)

        # Choose random sectors to mark as slow
        slow_sectors = sorted(self.rng.sample(range(total_sectors), num_slow))

        # Create metadata about slow sectors
        slow_metadata = {
            "type": "slow_sectors",
            "sectors": slow_sectors,
            "delay_ms": 500,  # Simulated delay per slow sector
            "description": "Sectors that take >500ms to read",
        }

        log = [self._log_entry(
            CorruptionType.SLOW_SECTORS,
            f"Slow sectors: {num_slow} sectors marked as slow (>500ms)",
            slow_sectors, [],
            (0, len(image)),
            severity,
            slow_metadata,
        )]

        return CorruptionResult(
            corrupted_image=bytes(image),  # Image unchanged
            corruption_log=log,
            manifest_corruption={
                "type": "slow_sectors",
                "severity": severity,
                "affected_sectors": num_slow,
                "delay_ms": 500,
                "slow_sector_list": slow_sectors,
            },
        )


class TimeoutPatternModel(CorruptionModel):
    """
    Every Nth sector times out — metadata-based simulation.

    Like slow sectors, this is metadata-only. The recovery motor
    must handle this in its simulation layer.
    """

    def apply(self, image: bytearray, manifest: Dict,
              severity: float = 0.01,
              interval: Optional[int] = None) -> CorruptionResult:
        total_sectors = len(image) // 512
        if interval is None:
            interval = max(1, int(1.0 / severity))

        timeout_sectors = list(range(0, total_sectors, interval))

        timeout_metadata = {
            "type": "timeout_pattern",
            "interval": interval,
            "sectors": timeout_sectors,
            "timeout_seconds": 30,
            "description": f"Every {interval}th sector times out (30s)",
        }

        log = [self._log_entry(
            CorruptionType.TIMEOUT_PATTERN,
            f"Timeout pattern: every {interval}th sector times out",
            timeout_sectors, [],
            (0, len(image)),
            severity,
            timeout_metadata,
        )]

        return CorruptionResult(
            corrupted_image=bytes(image),  # Image unchanged
            corruption_log=log,
            manifest_corruption={
                "type": "timeout_pattern",
                "severity": severity,
                "interval": interval,
                "affected_sectors": len(timeout_sectors),
                "timeout_seconds": 30,
            },
        )


# ─── Model Registry ──────────────────────────────────────────────────────────

CORRUPTION_MODEL_REGISTRY = {
    CorruptionType.HEAD_CRASH_START: HeadCrashStartModel,
    CorruptionType.HEAD_CRASH_END: HeadCrashEndModel,
    CorruptionType.SCRATCH_CONTINUOUS: ScratchContinuousModel,
    CorruptionType.INTERMITTENT_SECTORS: IntermittentSectorsModel,
    CorruptionType.MFT_PARTIAL_DELETE: MFTPartialDeleteModel,
    CorruptionType.BITMAP_CORRUPTION: BitmapCorruptionModel,
    CorruptionType.JOURNAL_CORRUPTION: JournalCorruptionModel,
    CorruptionType.CRC_ERRORS: CRCErrorsModel,
    CorruptionType.SLOW_SECTORS: SlowSectorsModel,
    CorruptionType.TIMEOUT_PATTERN: TimeoutPatternModel,
}


def get_model(corruption_type: CorruptionType, seed: int = 42) -> CorruptionModel:
    """Get a corruption model instance by type."""
    model_class = CORRUPTION_MODEL_REGISTRY.get(corruption_type)
    if model_class is None:
        raise ValueError(f"Unknown corruption type: {corruption_type}")
    return model_class(seed=seed)
