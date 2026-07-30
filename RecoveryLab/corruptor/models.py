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
    # ─── Noise models (Objeción 6) ─────────────────────────────────────
    RANDOM_NOISE = "random_noise"              # Random bytes in random sectors
    PARTIAL_OVERWRITE = "partial_overwrite"     # Partial file overwrite
    FRAGMENTATION_CHAOS = "fragmentation_chaos" # Unpredictable fragmentation
    TIMESTAMP_INCONSISTENCY = "timestamp_inconsistency"  # Inconsistent timestamps


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


# ─── Noise Models (Objeción 6: Reality doesn't break things cleanly) ─────────

class RandomNoiseModel(CorruptionModel):
    """
    Random bytes written to random sectors.

    Unlike CRC errors (1-4 bit flips), this writes ENTIRE random bytes
    to random sectors. This simulates:
      - Firmware bugs writing garbage
      - Controller errors
      - Electromagnetic interference
      - Partial sector corruption

    Reality rarely breaks things by zeroing them out.
    """

    def apply(self, image: bytearray, manifest: Dict,
              severity: float = 0.01) -> CorruptionResult:
        total_sectors = len(image) // 512
        num_affected = int(total_sectors * severity)

        # Choose random sectors to corrupt
        affected_sectors = self.rng.sample(range(total_sectors), num_affected)

        for s in affected_sectors:
            offset = s * 512
            # Write random bytes to the entire sector
            # (Not just bit flips — full random garbage)
            random_data = bytes(self.rng.getrandbits(8) for _ in range(512))
            image[offset:offset + 512] = random_data

        clusters = list(set(s // (manifest["cluster_size"] // 512)
                          for s in affected_sectors))

        log = [self._log_entry(
            CorruptionType.RANDOM_NOISE,
            f"Random noise: {num_affected} sectors overwritten with random data",
            affected_sectors, clusters,
            (0, len(image)),
            severity,
            {"pattern": "random_bytes", "affected_count": num_affected,
             "note": "Full random bytes, not bit flips — simulates firmware/controller errors"},
        )]

        return CorruptionResult(
            corrupted_image=bytes(image),
            corruption_log=log,
            manifest_corruption={
                "type": "random_noise",
                "severity": severity,
                "affected_sectors": num_affected,
            },
        )


class PartialOverwriteModel(CorruptionModel):
    """
    Partial file overwrite — simulates data being partially overwritten.

    In real scenarios, files are often partially overwritten by new data:
      - File partially overwritten by another file
      - Log file rotating over old data
      - Temporary file overwriting part of a document
      - OS writing metadata over file data

    This is DIFFERENT from zeroing: the overwritten part contains REAL data
    from another file, making it harder to detect that corruption occurred.
    """

    def apply(self, image: bytearray, manifest: Dict,
              severity: float = 0.10) -> CorruptionResult:
        cluster_size = manifest["cluster_size"]
        user_files = [f for f in manifest["files"] if f.get("id", 0) >= 12]

        if not user_files:
            return CorruptionResult(
                corrupted_image=bytes(image),
                corruption_log=[],
                manifest_corruption={"type": "partial_overwrite", "skipped": True},
            )

        # Select random files to partially overwrite
        num_files = max(1, int(len(user_files) * severity))
        files_to_overwrite = self.rng.sample(user_files, min(num_files, len(user_files)))

        affected_clusters = set()
        overwritten_files = []

        for file_info in files_to_overwrite:
            clusters = file_info.get("clusters", [])
            if not clusters:
                continue

            # Overwrite a random subset of the file's clusters
            # (not all — that would be a full delete)
            num_clusters_to_overwrite = max(1, len(clusters) // 2)
            clusters_to_overwrite = self.rng.sample(
                clusters, min(num_clusters_to_overwrite, len(clusters))
            )

            for c in clusters_to_overwrite:
                offset = c * cluster_size
                if offset + cluster_size <= len(image):
                    # Write random data (simulating another file's content)
                    random_data = bytes(self.rng.getrandbits(8)
                                       for _ in range(cluster_size))
                    image[offset:offset + cluster_size] = random_data
                    affected_clusters.add(c)

            overwritten_files.append({
                "name": file_info.get("name", "unknown"),
                "clusters_overwritten": len(clusters_to_overwrite),
                "clusters_total": len(clusters),
            })

        log = [self._log_entry(
            CorruptionType.PARTIAL_OVERWRITE,
            f"Partial overwrite: {len(overwritten_files)} files partially overwritten",
            [], list(affected_clusters),
            (0, len(image)),
            severity,
            {"overwritten_files": overwritten_files,
             "note": "Overwritten with random data, not zeros — harder to detect"},
        )]

        return CorruptionResult(
            corrupted_image=bytes(image),
            corruption_log=log,
            manifest_corruption={
                "type": "partial_overwrite",
                "severity": severity,
                "files_overwritten": len(overwritten_files),
                "overwritten_file_details": overwritten_files,
            },
        )


class FragmentationChaosModel(CorruptionModel):
    """
    Unpredictable fragmentation — simulates a heavily used disk.

    On a real disk used for years, files are scattered across the disk
    in unpredictable patterns. This model doesn't physically fragment
    the files (that requires rebuilding the NTFS image), but it
    corrupts the MFT run lists to make them inconsistent with the
    actual data placement.

    This specifically tests whether the motor can handle:
      - Run lists that point to wrong clusters
      - Run lists with impossible offsets
      - Inconsistent VCN ranges
    """

    def apply(self, image: bytearray, manifest: Dict,
              severity: float = 0.20) -> CorruptionResult:
        mft_info = manifest["mft"]
        mft_start = mft_info["start_cluster"]
        cluster_size = manifest["cluster_size"]
        record_size = mft_info.get("record_size", 1024)
        mft_record_count = mft_info.get("record_count", 0)

        # Select user MFT records to corrupt run lists
        user_records = [i for i in range(12, mft_record_count)]
        num_to_corrupt = max(1, int(len(user_records) * severity))
        records_to_corrupt = self.rng.sample(
            user_records, min(num_to_corrupt, len(user_records))
        )

        affected_clusters = set()
        corrupted_count = 0

        for rec_num in records_to_corrupt:
            rec_offset = (mft_start * cluster_size) + (rec_num * record_size)

            if rec_offset + record_size > len(image):
                continue

            # Check if this is a valid MFT record
            if image[rec_offset:rec_offset + 4] != b'FILE':
                continue

            # Find the $DATA attribute and corrupt the run list
            # by flipping bits in the run list area
            # This is subtle corruption — the MFT record still looks valid,
            # but the run list points to wrong clusters
            try:
                first_attr_offset = struct.unpack_from('<H', image, rec_offset + 20)[0]
                attr_offset = rec_offset + first_attr_offset

                while attr_offset + 4 < rec_offset + record_size:
                    attr_type = struct.unpack_from('<I', image, attr_offset)[0]
                    if attr_type == 0xFFFFFFFF:
                        break
                    attr_length = struct.unpack_from('<I', image, attr_offset + 4)[0]
                    if attr_length == 0:
                        break

                    if attr_type == 0x80:  # $DATA
                        non_resident = image[attr_offset + 8]
                        if non_resident:
                            # Corrupt run list by flipping bits in the run data
                            run_offset = struct.unpack_from('<H', image, attr_offset + 32)[0]
                            run_start = attr_offset + run_offset
                            run_end = attr_offset + attr_length

                            # Flip 1-3 bits in the run list area
                            for _ in range(self.rng.randint(1, 3)):
                                byte_pos = self.rng.randint(run_start, min(run_end - 1, run_start + 50))
                                bit_pos = self.rng.randint(0, 7)
                                image[byte_pos] ^= (1 << bit_pos)

                            corrupted_count += 1
                            cluster = mft_start + (rec_num * record_size) // cluster_size
                            affected_clusters.add(cluster)
                        break

                    attr_offset += attr_length
            except (struct.error, IndexError):
                continue

        log = [self._log_entry(
            CorruptionType.FRAGMENTATION_CHAOS,
            f"Fragmentation chaos: {corrupted_count} MFT run lists corrupted with bit flips",
            [], list(affected_clusters),
            (mft_start * cluster_size, mft_start * cluster_size + mft_record_count * record_size),
            severity,
            {"corrupted_run_lists": corrupted_count,
             "note": "Run lists point to wrong clusters — subtle, hard to detect"},
        )]

        return CorruptionResult(
            corrupted_image=bytes(image),
            corruption_log=log,
            manifest_corruption={
                "type": "fragmentation_chaos",
                "severity": severity,
                "corrupted_run_lists": corrupted_count,
            },
        )


class TimestampInconsistencyModel(CorruptionModel):
    """
    Inconsistent timestamps in MFT records.

    In real disks, timestamps can be inconsistent due to:
      - Clock drift
      - Timezone changes
      - Daylight saving time
      - File copied without preserving timestamps
      - Firmware bugs

    This model modifies $STANDARD_INFORMATION and $FILE_NAME timestamps
    to be inconsistent, testing whether the motor relies on timestamps
    for ordering or validation.
    """

    def apply(self, image: bytearray, manifest: Dict,
              severity: float = 0.20) -> CorruptionResult:
        mft_info = manifest["mft"]
        mft_start = mft_info["start_cluster"]
        cluster_size = manifest["cluster_size"]
        record_size = mft_info.get("record_size", 1024)
        mft_record_count = mft_info.get("record_count", 0)

        user_records = [i for i in range(12, mft_record_count)]
        num_to_corrupt = max(1, int(len(user_records) * severity))
        records_to_corrupt = self.rng.sample(
            user_records, min(num_to_corrupt, len(user_records))
        )

        affected_clusters = set()
        corrupted_count = 0

        for rec_num in records_to_corrupt:
            rec_offset = (mft_start * cluster_size) + (rec_num * record_size)

            if rec_offset + record_size > len(image):
                continue

            if image[rec_offset:rec_offset + 4] != b'FILE':
                continue

            # Find $STANDARD_INFORMATION (0x10) and modify timestamps
            try:
                first_attr_offset = struct.unpack_from('<H', image, rec_offset + 20)[0]
                attr_offset = rec_offset + first_attr_offset

                while attr_offset + 4 < rec_offset + record_size:
                    attr_type = struct.unpack_from('<I', image, attr_offset)[0]
                    if attr_type == 0xFFFFFFFF:
                        break
                    attr_length = struct.unpack_from('<I', image, attr_offset + 4)[0]
                    if attr_length == 0:
                        break

                    if attr_type == 0x10:  # $STANDARD_INFORMATION
                        # Timestamps are at offsets 24, 32, 40, 48 within the attribute
                        # (after the attribute header)
                        for ts_offset in [attr_offset + 24, attr_offset + 32,
                                         attr_offset + 40, attr_offset + 48]:
                            if ts_offset + 8 <= rec_offset + record_size:
                                # Write a random timestamp (could be future, past, or zero)
                                random_ts = self.rng.randint(0, 2**64 - 1)
                                struct.pack_into('<Q', image, ts_offset, random_ts)

                        corrupted_count += 1
                        cluster = mft_start + (rec_num * record_size) // cluster_size
                        affected_clusters.add(cluster)
                        break  # Only modify first $STANDARD_INFORMATION

                    attr_offset += attr_length
            except (struct.error, IndexError):
                continue

        log = [self._log_entry(
            CorruptionType.TIMESTAMP_INCONSISTENCY,
            f"Timestamp inconsistency: {corrupted_count} records with random timestamps",
            [], list(affected_clusters),
            (mft_start * cluster_size, mft_start * cluster_size + mft_record_count * record_size),
            severity,
            {"corrupted_timestamps": corrupted_count,
             "note": "Random timestamps — tests if motor relies on temporal ordering"},
        )]

        return CorruptionResult(
            corrupted_image=bytes(image),
            corruption_log=log,
            manifest_corruption={
                "type": "timestamp_inconsistency",
                "severity": severity,
                "corrupted_timestamps": corrupted_count,
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
    # ─── Noise models (Objeción 6) ─────────────────────────────────────
    CorruptionType.RANDOM_NOISE: RandomNoiseModel,
    CorruptionType.PARTIAL_OVERWRITE: PartialOverwriteModel,
    CorruptionType.FRAGMENTATION_CHAOS: FragmentationChaosModel,
    CorruptionType.TIMESTAMP_INCONSISTENCY: TimestampInconsistencyModel,
}


def get_model(corruption_type: CorruptionType, seed: int = 42) -> CorruptionModel:
    """Get a corruption model instance by type."""
    model_class = CORRUPTION_MODEL_REGISTRY.get(corruption_type)
    if model_class is None:
        raise ValueError(f"Unknown corruption type: {corruption_type}")
    return model_class(seed=seed)
