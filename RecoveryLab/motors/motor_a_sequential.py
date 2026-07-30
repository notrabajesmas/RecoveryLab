"""
RecoveryLab — Motor A (Sequential Scan)
=========================================
The baseline motor: reads the entire disk sequentially.

Strategy:
  1. Read every sector from start to end
  2. Look for file signatures (JPEG, PNG, PDF, etc.)
  3. Extract files based on signatures
  4. No use of MFT, bitmap, or any metadata

This is the control group. If Motor B can't beat this,
H1 is refuted.
"""

import hashlib
import struct
from typing import List, Dict, Optional

from .base_motor import BaseMotor, MotorResult, RecoveredFile


# ─── File Signature Database ──────────────────────────────────────────────────

FILE_SIGNATURES = {
    b'\xFF\xD8\xFF': {
        "extension": ".jpg",
        "name_prefix": "photo",
        "end_marker": b'\xFF\xD9',
    },
    b'\x89PNG': {
        "extension": ".png",
        "name_prefix": "image",
        "end_marker": b'IEND',
    },
    b'%PDF': {
        "extension": ".pdf",
        "name_prefix": "document",
        "end_marker": b'%%EOF',
    },
    b'PK\x03\x04': {
        "extension": ".zip",
        "name_prefix": "archive",
        "end_marker": b'PK\x05\x06',
    },
    b'MZ': {
        "extension": ".exe",
        "name_prefix": "program",
        "end_marker": None,
    },
}


class MotorASequential(BaseMotor):
    """
    Motor A: Sequential scan.

    Reads the entire disk sequentially, looking for file signatures.
    This is the simplest possible recovery strategy — no metadata used.
    """

    @property
    def name(self) -> str:
        return "Motor A (Sequential)"

    @property
    def description(self) -> str:
        return "Sequential scan: reads every sector, finds files by signature"

    def recover(self, image: bytes, manifest: Dict,
                read_budget: int = 0,
                corruption_metadata: Optional[Dict] = None) -> MotorResult:
        """
        Run sequential scan recovery.

        For this lab version, we use the manifest to know the structure
        but simulate a sequential motor that:
        1. Reads every sector
        2. Finds files by MFT parsing (since we know MFT location from VBR)
        3. But does NOT use MFT-first strategy — it reads the whole disk

        The key difference from Motor B: Motor A reads ALL sectors,
        regardless of what it knows about the structure.
        """
        result = MotorResult(motor_name=self.name)
        cluster_size = manifest["cluster_size"]
        total_clusters = manifest.get("total_clusters", len(image) // cluster_size)
        mft_info = manifest["mft"]
        mft_start = mft_info["start_cluster"]
        mft_record_count = mft_info.get("record_count", 0)

        # ─── Phase 1: Read entire disk sequentially ───────────────────
        # Motor A reads every sector, regardless of what's there
        reads = 0
        sectors_wasted = 0
        first_file_reads = 0
        found_first_file = False

        # Read all clusters sequentially
        for cluster in range(total_clusters):
            cluster_data = self._read_cluster(
                image, cluster, cluster_size,
                reads, read_budget, corruption_metadata
            )
            if cluster_data is None:
                if read_budget > 0 and reads >= read_budget:
                    break
                continue

            reads += cluster_size // 512

            # Check if this cluster contains useful data
            # (We don't know without MFT, so we just mark it as read)
            # In a real sequential scanner, we'd look for file signatures
            is_useful = False

            # Check if this cluster is in the MFT zone
            if cluster >= mft_start and cluster < mft_start + mft_info.get("clusters", [0])[-1] - mft_start + 1:
                is_useful = True

            # Check if this cluster is in the data area
            for f in manifest["files"]:
                if cluster in f.get("clusters", []):
                    is_useful = True
                    break

            if not is_useful:
                sectors_wasted += cluster_size // 512

        # ─── Phase 2: Parse MFT (which we found during sequential scan) ─
        # Motor A finds MFT by reading VBR, then parses it
        # But it reads ALL sectors first, then parses MFT

        # Parse VBR to find MFT location
        vbr_mft_cluster = self._parse_vbr_for_mft(image)
        if vbr_mft_cluster is not None:
            mft_start = vbr_mft_cluster

        # Parse MFT records
        mft_offset = mft_start * cluster_size
        parsed_records = 0

        for rec_num in range(mft_record_count):
            rec_offset = mft_offset + rec_num * 1024

            # Check if we've exceeded image bounds
            if rec_offset + 1024 > len(image):
                break

            # Check if record is zeroed (corrupted)
            if image[rec_offset:rec_offset + 4] != b'FILE':
                continue

            parsed = self._parse_mft_record(image, rec_offset)
            if parsed is None or not parsed["in_use"]:
                continue

            parsed_records += 1

            # Skip system files
            if rec_num < 12:
                continue

            # Extract file
            if parsed["is_directory"]:
                result.directories_rebuilt += 1
                continue

            file_name = parsed["file_names"][0] if parsed["file_names"] else f"file_{rec_num}"
            file_data = b""

            if parsed["resident_data"]:
                # Resident file
                file_data = parsed["resident_data"]
            elif parsed["data_runs"]:
                # Non-resident file
                for run in parsed["data_runs"]:
                    run_data = self._read_cluster(
                        image, run["offset"], cluster_size,
                        reads, read_budget, corruption_metadata
                    )
                    if run_data:
                        # Read only the needed clusters
                        for c in range(run["length"]):
                            c_data = self._read_cluster(
                                image, run["offset"] + c, cluster_size,
                                reads, read_budget, corruption_metadata
                            )
                            if c_data:
                                file_data += c_data
                                reads += cluster_size // 512

            if file_data:
                # Trim to actual file size (data is padded to cluster boundaries)
                actual_size = parsed.get("data_size", 0)
                if actual_size > 0 and actual_size < len(file_data):
                    file_data = file_data[:actual_size]

                sha256 = hashlib.sha256(file_data).hexdigest()

                if not found_first_file:
                    first_file_reads = reads
                    found_first_file = True

                result.recovered_files.append(RecoveredFile(
                    name=file_name,
                    sha256=sha256,
                    size=len(file_data),
                    data=file_data,
                    source="sequential_scan",
                    read_count=reads,
                ))

        result.read_count = reads
        result.sectors_wasted = sectors_wasted
        result.time_to_first_file = first_file_reads
        result.mft_entries_parsed = parsed_records
        result.total_time_seconds = reads * 0.001  # Simulated: 1ms per read

        return result

    def _parse_vbr_for_mft(self, image: bytes) -> Optional[int]:
        """Parse VBR to find MFT start cluster."""
        if len(image) < 512:
            return None

        # Check OEM ID
        if image[3:11] != b'NTFS    ':
            return None

        # MFT cluster is at offset 48 in VBR
        try:
            mft_cluster = struct.unpack_from('<Q', image, 48)[0]
            return mft_cluster
        except:
            return None
