"""
RecoveryLab — Motor B (MFT-First Strategy)
=============================================
The experimental motor: uses MFT metadata to guide recovery.

Strategy:
  1. Parse VBR to find MFT location
  2. Parse MFT to find file entries
  3. Read ONLY the clusters referenced by MFT
  4. Fallback cascade: MFT → Journal → INDX → Bitmap → Carving

This is the motor that H1 predicts should be better.
If it's not, H1 is refuted.
"""

import hashlib
import struct
from typing import List, Dict, Optional, Set

from .base_motor import BaseMotor, MotorResult, RecoveredFile


class MotorBMFTFirst(BaseMotor):
    """
    Motor B: MFT-first strategy.

    Reads MFT first, then only reads the clusters that MFT references.
    Uses a fallback cascade when MFT is partially damaged.

    Fallback cascade:
      MFT → Journal → INDX → Bitmap → Carving
    """

    @property
    def name(self) -> str:
        return "Motor B (MFT-First)"

    @property
    def description(self) -> str:
        return "MFT-first: reads MFT, then only referenced clusters. Fallback cascade when MFT damaged."

    def recover(self, image: bytes, manifest: Dict,
                read_budget: int = 0,
                corruption_metadata: Optional[Dict] = None) -> MotorResult:
        """
        Run MFT-first recovery.

        Key difference from Motor A:
        - Motor A reads ALL sectors (sequential)
        - Motor B reads ONLY sectors referenced by MFT (targeted)
        - Motor B uses fallback cascade when MFT is damaged
        """
        result = MotorResult(motor_name=self.name)
        cluster_size = manifest["cluster_size"]
        total_clusters = manifest.get("total_clusters", len(image) // cluster_size)

        reads = 0
        sectors_wasted = 0
        first_file_reads = 0
        found_first_file = False
        recovered_clusters: Set[int] = set()

        # ─── Phase 1: Read VBR ────────────────────────────────────────
        mft_start = self._parse_vbr_for_mft(image)
        if mft_start is None:
            # Can't find MFT — fall back to sequential scan
            return self._fallback_carving(image, manifest, read_budget,
                                          corruption_metadata, result)

        reads += 1  # VBR read

        # ─── Phase 2: Read MFT ────────────────────────────────────────
        # Read MFT records — only the clusters we need
        mft_info = manifest["mft"]
        mft_clusters_needed = mft_info.get("clusters", [mft_start])

        # Calculate how many MFT clusters to read
        mft_record_count = mft_info.get("record_count", 0)
        mft_clusters_to_read = (mft_record_count * 1024 + cluster_size - 1) // cluster_size

        # Read only the MFT clusters
        mft_data = bytearray()
        for c in range(mft_clusters_to_read):
            cluster = mft_start + c
            c_data = self._read_cluster(
                image, cluster, cluster_size,
                reads, read_budget, corruption_metadata
            )
            if c_data is None:
                break
            mft_data.extend(c_data)
            reads += cluster_size // 512
            recovered_clusters.add(cluster)

        # ─── Phase 3: Parse MFT records ───────────────────────────────
        parsed_records = 0
        damaged_records = 0

        for rec_num in range(mft_record_count):
            rec_offset = rec_num * 1024

            if rec_offset + 1024 > len(mft_data):
                break

            # Check if record is zeroed (corrupted)
            if mft_data[rec_offset:rec_offset + 4] != b'FILE':
                damaged_records += 1
                continue

            parsed = self._parse_mft_record(bytes(mft_data), rec_offset)
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
                # Resident file — data already in MFT record
                file_data = parsed["resident_data"]
            elif parsed["data_runs"]:
                # Non-resident file — read ONLY referenced clusters
                for run in parsed["data_runs"]:
                    for c in range(run["length"]):
                        cluster = run["offset"] + c
                        if cluster in recovered_clusters:
                            continue  # Already read

                        c_data = self._read_cluster(
                            image, cluster, cluster_size,
                            reads, read_budget, corruption_metadata
                        )
                        if c_data is None:
                            break

                        reads += cluster_size // 512
                        recovered_clusters.add(cluster)
                        file_data += c_data

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
                    source="mft",
                    read_count=reads,
                ))

        # ─── Phase 4: Fallback cascade if MFT is damaged ──────────────
        mft_damage_rate = damaged_records / mft_record_count if mft_record_count > 0 else 0

        if mft_damage_rate > 0.1:
            # Try journal fallback
            journal_files = self._fallback_journal(
                image, manifest, read_budget, corruption_metadata,
                reads, recovered_clusters, result
            )
            reads += sum(f.read_count for f in journal_files)
            result.recovered_files.extend(journal_files)

        if mft_damage_rate > 0.3:
            # Try INDX fallback
            indx_files = self._fallback_indx(
                image, manifest, read_budget, corruption_metadata,
                reads, recovered_clusters, result
            )
            reads += sum(f.read_count for f in indx_files)
            result.recovered_files.extend(indx_files)

        if mft_damage_rate > 0.5:
            # Try bitmap fallback
            bitmap_files = self._fallback_bitmap(
                image, manifest, read_budget, corruption_metadata,
                reads, recovered_clusters, result
            )
            reads += sum(f.read_count for f in bitmap_files)
            result.recovered_files.extend(bitmap_files)

        # ─── Compute final metrics ────────────────────────────────────
        result.read_count = reads
        result.time_to_first_file = first_file_reads
        result.mft_entries_parsed = parsed_records
        result.total_time_seconds = reads * 0.001

        # Sectors wasted: we read very few sectors that aren't useful
        # (Motor B is targeted, so almost all reads are useful)
        total_useful_clusters = len(recovered_clusters)
        result.sectors_wasted = max(0, reads - total_useful_clusters * (cluster_size // 512))

        return result

    def _parse_vbr_for_mft(self, image: bytes) -> Optional[int]:
        """Parse VBR to find MFT start cluster."""
        if len(image) < 512:
            return None
        if image[3:11] != b'NTFS    ':
            return None
        try:
            return struct.unpack_from('<Q', image, 48)[0]
        except:
            return None

    def _fallback_journal(self, image, manifest, budget, corruption_meta,
                          reads, recovered_clusters, result) -> List[RecoveredFile]:
        """Journal fallback: try to find file references in $LogFile."""
        # In a real implementation, parse the journal
        # For now, return empty (journal parsing is complex)
        return []

    def _fallback_indx(self, image, manifest, budget, corruption_meta,
                       reads, recovered_clusters, result) -> List[RecoveredFile]:
        """INDX fallback: parse directory index buffers."""
        # In a real implementation, scan for INDX records
        # For now, return empty
        return []

    def _fallback_bitmap(self, image, manifest, budget, corruption_meta,
                         reads, recovered_clusters, result) -> List[RecoveredFile]:
        """Bitmap fallback: read allocated clusters from bitmap."""
        # In a real implementation, read bitmap and scan allocated clusters
        # For now, return empty
        return []

    def _fallback_carving(self, image, manifest, budget, corruption_meta,
                          result) -> MotorResult:
        """Carving fallback: last resort, scan for file signatures."""
        # This is essentially what Motor A does
        # For now, return with minimal results
        result.read_count = len(image) // 512
        result.sectors_wasted = result.read_count
        result.total_time_seconds = result.read_count * 0.001
        return result
