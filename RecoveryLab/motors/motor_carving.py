"""
RecoveryLab — Motor Carving (Signature-Based Recovery)
========================================================
BLOCKER-001 resolution: a TRUE carving strategy that NEVER touches the MFT.

Philosophy:
  - Uses ONLY file signatures (magic bytes) to identify files
  - NEVER reads the VBR
  - NEVER reads the MFT
  - NEVER reads any filesystem metadata
  - Recovers files by scanning raw bytes for known patterns

This is the genuine adversarial strategy. It represents the "no metadata"
philosophy: if you don't trust the filesystem at all, what can you recover
by looking at the raw data alone?

Supported formats:
  - JPEG:  FF D8 FF [E0|E1|E8|DB]
  - PNG:   89 50 4E 47 0D 0A 1A 0A
  - PDF:   25 50 44 46
  - ZIP:   50 4B 03 04
  - MP4:   ....ftyp
  - DOCX:  50 4B 03 04 (same as ZIP — distinguished by internal structure)
  - TIFF:  49 49 2A 00 (little-endian) or 4D 4D 00 2A (big-endian)
  - CR2:   49 49 2A 00 (Canon RAW — same as TIFF, distinguished by internal markers)
  - NEF:   4D 4D 00 2A (Nikon RAW — same as TIFF big-endian)
  - MOV:   ....ftypqt (QuickTime)
  - XLSX:  50 4B 03 04 (same as ZIP — distinguished by xl/ internal path)
  - SQLite: 53 51 4C 69 74 65 20 66 6F 72 6D 20 31 00
  - GIF:   47 49 46 38
  - BMP:   42 4D
  - RAR:   52 61 72 21 1A 07
  - 7Z:    37 7A BC AF 27 1C
  - PSD:   38 42 50 53 (Photoshop)
  - DNG:   49 49 2A 00 (same as TIFF — distinguished by DNG markers)
  - HEIC:  ....ftypheic (same container as MP4)
  - AVI:   52 49 46 46....415649

Limitations of carving (by design):
  - No filenames (we assign generic names like "carved_0001.jpg")
  - No directory structure (everything in a flat list)
  - No file size from metadata (we use end-of-signature heuristics)
  - No fragmentation support (contiguous files only)
  - ZIP/DOCX ambiguity (same signature)
  - Text files without signatures are invisible

These limitations are NOT bugs — they are the fundamental constraints
of a carving-only approach. That's the whole point of the experiment.
"""

import hashlib
import struct
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass

from .base_motor import BaseMotor, MotorResult, RecoveredFile


# ─── File Signature Definitions ───────────────────────────────────────────────

@dataclass
class FileSignature:
    """A file signature (magic bytes) for carving."""
    name: str           # Format name (e.g., "JPEG")
    extension: str      # File extension (e.g., ".jpg")
    header: bytes       # Magic bytes to search for
    header_mask: bytes  # Mask for wildcard bytes (0xFF = must match, 0x00 = don't care)
    footer: bytes       # End-of-file marker (empty = use max-size heuristic)
    max_size: int       # Maximum file size to carve (sanity limit)
    min_size: int       # Minimum file size (below this = false positive)

    @property
    def header_len(self) -> int:
        return len(self.header)


# ─── Signature Database ───────────────────────────────────────────────────────

SIGNATURES: List[FileSignature] = [
    # JPEG — most common photo format
    # Header: FF D8 FF [E0|E1|E8|DB] (4th byte varies)
    # Footer: FF D9
    FileSignature(
        name="JPEG",
        extension=".jpg",
        header=b'\xFF\xD8\xFF',
        header_mask=b'\xFF\xFF\xFF',  # First 3 bytes must match exactly
        footer=b'\xFF\xD9',
        max_size=50 * 1024 * 1024,   # 50 MB
        min_size=200,                 # JPEG smaller than 200 bytes is suspicious
    ),

    # PNG — most common lossless image format
    # Header: 89 50 4E 47 0D 0A 1A 0A (8 bytes, exact)
    # Footer: IEND chunk: 00 00 00 00 49 45 4E 44 AE 42 60 82
    FileSignature(
        name="PNG",
        extension=".png",
        header=b'\x89PNG\r\n\x1a\n',
        header_mask=b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF',
        footer=b'IEND\xAE\x42\x60\x82',
        max_size=50 * 1024 * 1024,
        min_size=100,
    ),

    # PDF — Portable Document Format
    # Header: %PDF-1.[0-9]
    # Footer: %%EOF
    FileSignature(
        name="PDF",
        extension=".pdf",
        header=b'%PDF-',
        header_mask=b'\xFF\xFF\xFF\xFF\xFF',
        footer=b'%%EOF\n',
        max_size=100 * 1024 * 1024,   # 100 MB
        min_size=500,
    ),

    # ZIP — ZIP archive (also DOCX, XLSX, PPTX)
    # Header: PK\x03\x04
    # Footer: End of central directory: PK\x05\x06
    FileSignature(
        name="ZIP",
        extension=".zip",
        header=b'PK\x03\x04',
        header_mask=b'\xFF\xFF\xFF\xFF',
        footer=b'PK\x05\x06',
        max_size=100 * 1024 * 1024,
        min_size=100,
    ),

    # MP4 — Video container
    # Header: [4 bytes size]ftyp[4 bytes brand]
    # Footer: No reliable footer — use max-size heuristic
    FileSignature(
        name="MP4",
        extension=".mp4",
        header=b'ftyp',
        header_mask=b'\xFF\xFF\xFF\xFF',
        footer=b'',  # No reliable footer
        max_size=500 * 1024 * 1024,   # 500 MB
        min_size=1000,
    ),

    # DOCX — Microsoft Word (ZIP-based, but we try to distinguish)
    # We'll detect these as ZIP and then check for word/ internal path
    # For now, we create a separate entry that searches for the same header
    # but tries to distinguish by looking for "word/" inside the ZIP
    FileSignature(
        name="DOCX",
        extension=".docx",
        header=b'PK\x03\x04',
        header_mask=b'\xFF\xFF\xFF\xFF',
        footer=b'PK\x05\x06',
        max_size=100 * 1024 * 1024,
        min_size=100,
    ),

    # TIFF — Tagged Image File Format (little-endian)
    # Header: 49 49 2A 00 (II + 0x002A)
    # Also matches CR2 (Canon RAW) which uses TIFF structure
    # Footer: No reliable footer — use max-size heuristic
    FileSignature(
        name="TIFF",
        extension=".tiff",
        header=b'II\x2a\x00',
        header_mask=b'\xFF\xFF\xFF\xFF',
        footer=b'',
        max_size=100 * 1024 * 1024,
        min_size=1000,
    ),

    # TIFF big-endian — also matches NEF (Nikon RAW)
    # Header: 4D 4D 00 2A (MM + 0x002A)
    FileSignature(
        name="TIFF_BE",
        extension=".tiff",
        header=b'MM\x00\x2a',
        header_mask=b'\xFF\xFF\xFF\xFF',
        footer=b'',
        max_size=100 * 1024 * 1024,
        min_size=1000,
    ),

    # MOV — QuickTime video
    # Header: [4 bytes size]ftypqt
    # Similar to MP4 but with 'qt' brand
    FileSignature(
        name="MOV",
        extension=".mov",
        header=b'ftypqt',
        header_mask=b'\xFF\xFF\xFF\xFF\xFF\xFF',
        footer=b'',
        max_size=500 * 1024 * 1024,
        min_size=1000,
    ),

    # XLSX — Microsoft Excel (ZIP-based)
    # Same header as ZIP/DOCX — distinguished by xl/ internal path
    FileSignature(
        name="XLSX",
        extension=".xlsx",
        header=b'PK\x03\x04',
        header_mask=b'\xFF\xFF\xFF\xFF',
        footer=b'PK\x05\x06',
        max_size=100 * 1024 * 1024,
        min_size=100,
    ),

    # SQLite — Database file
    # Header: "SQLite format 3\000"
    # Footer: No reliable footer — use max-size heuristic
    FileSignature(
        name="SQLite",
        extension=".sqlite",
        header=b'SQLite format 3\x00',
        header_mask=b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF',
        footer=b'',
        max_size=500 * 1024 * 1024,
        min_size=512,
    ),

    # GIF — Graphics Interchange Format
    # Header: GIF87a or GIF89a
    # Footer: 3B (semicolon)
    FileSignature(
        name="GIF",
        extension=".gif",
        header=b'GIF8',
        header_mask=b'\xFF\xFF\xFF\xFF',
        footer=b';',
        max_size=50 * 1024 * 1024,
        min_size=100,
    ),

    # BMP — REMOVED per RP-002 (2026-07-31)
    # The 2-byte 'BM' signature produces massive false positives in random data,
    # creating ~50MB carved candidates that trigger dedup cascade elimination of
    # legitimate files. BMP is a low-priority format for carving scenarios.
    # If BMP detection is needed later, add header validation (Option B).
    # Original entry:
    # FileSignature(
    #     name="BMP",
    #     extension=".bmp",
    #     header=b'BM',
    #     header_mask=b'\xFF\xFF',
    #     footer=b'',
    #     max_size=50 * 1024 * 1024,
    #     min_size=100,
    # ),

    # RAR — RAR archive
    # Header: Rar!\x1A\x07
    FileSignature(
        name="RAR",
        extension=".rar",
        header=b'Rar!\x1a\x07',
        header_mask=b'\xFF\xFF\xFF\xFF\xFF\xFF',
        footer=b'',
        max_size=500 * 1024 * 1024,
        min_size=100,
    ),

    # 7Z — 7-Zip archive
    # Header: 37 7A BC AF 27 1C
    FileSignature(
        name="7Z",
        extension=".7z",
        header=b'7z\xBC\xAF\x27\x1C',
        header_mask=b'\xFF\xFF\xFF\xFF\xFF\xFF',
        footer=b'',
        max_size=500 * 1024 * 1024,
        min_size=100,
    ),

    # PSD — Adobe Photoshop
    # Header: 8BPS
    FileSignature(
        name="PSD",
        extension=".psd",
        header=b'8BPS',
        header_mask=b'\xFF\xFF\xFF\xFF',
        footer=b'',
        max_size=500 * 1024 * 1024,
        min_size=1000,
    ),

    # AVI — Audio Video Interleave
    # Header: RIFF....AVI
    FileSignature(
        name="AVI",
        extension=".avi",
        header=b'RIFF',
        header_mask=b'\xFF\xFF\xFF\xFF',
        footer=b'',
        max_size=500 * 1024 * 1024,
        min_size=1000,
    ),
]


class MotorCarving(BaseMotor):
    """
    Motor Carving: signature-based file recovery.

    This motor NEVER reads the MFT. It scans the raw disk image
    byte-by-byte looking for known file signatures.

    Strategy:
      1. Scan the ENTIRE image for file signatures
      2. When a signature is found, extract the file
      3. Use footer markers to determine file boundaries
      4. If no footer, use max-size heuristic
      5. Assign generic names (carved_0001.jpg, etc.)

    This is the "adversarial baseline" — it represents the best
    you can do without any filesystem metadata.
    """

    @property
    def name(self) -> str:
        return "Motor Carving (Signature-Only)"

    @property
    def description(self) -> str:
        return ("Carving: scans raw bytes for file signatures. "
                "NEVER reads MFT, VBR, or any filesystem metadata. "
                "No filenames, no directories, no fragmentation support.")

    def recover(self, image: bytes, manifest: Dict,
                read_budget: int = 0,
                corruption_metadata: Optional[Dict] = None) -> MotorResult:
        """
        Run signature-based carving recovery.

        Key constraint: This method NEVER accesses:
          - manifest["mft"] (MFT data)
          - manifest["vbr"] (VBR data)
          - Any filesystem metadata

        It ONLY uses manifest["cluster_size"] and manifest["total_clusters"]
        to understand the image geometry, and manifest["files"] to know
        what file types exist (for reporting purposes only — NOT for recovery).

        Actually, to be STRICTLY pure carving, we should NOT use the manifest
        at all for recovery. The manifest is only used for Judge evaluation
        after recovery.
        """
        result = MotorResult(motor_name=self.name)
        cluster_size = manifest.get("cluster_size", 4096)
        total_clusters = manifest.get("total_clusters", len(image) // cluster_size)

        reads = 0
        sectors_per_cluster = cluster_size // 512
        first_file_reads = 0
        found_first_file = False

        # ─── Phase 1: Scan entire image for signatures ────────────────
        # We read every cluster sequentially (like a real carver would)
        # This is the MAXIMUM read cost — no metadata guidance at all

        carved_files: List[Dict] = []
        signatures_found: Dict[str, int] = {}
        scan_offset = 0

        # Build a list of all header patterns to search for
        # We scan byte-by-byte through the image
        image_len = len(image)

        # Track which clusters we've already read (for read counting)
        read_clusters: Set[int] = set()

        # Scan the image looking for file signatures
        # We scan at every byte position within the first sector of each cluster
        # (in practice, signatures are usually at the start of a cluster)
        for cluster_num in range(total_clusters):
            cluster_start = cluster_num * cluster_size

            if cluster_start + cluster_size > image_len:
                break

            # Read this cluster
            cluster_data = image[cluster_start:cluster_start + cluster_size]
            read_clusters.add(cluster_num)
            reads += sectors_per_cluster

            # Check for budget exhaustion
            if read_budget > 0 and reads >= read_budget:
                break

            # Search for signatures within this cluster
            # Check at the start of the cluster (most common case)
            # and also at every offset within the first 512 bytes
            # (some signatures might be offset within a cluster)
            for sig in SIGNATURES:
                # Quick check: does the signature match at the start?
                matches = self._find_signature_matches(
                    image, cluster_start, cluster_size, sig, image_len
                )

                for match_offset in matches:
                    # Found a signature! Try to extract the file
                    carved = self._carve_file(
                        image, match_offset, sig, image_len,
                        cluster_size, total_clusters, read_clusters
                    )

                    if carved is not None:
                        carved_files.append(carved)
                        sig_name = sig.name
                        signatures_found[sig_name] = signatures_found.get(sig_name, 0) + 1

                        # Update read count for any additional clusters we read
                        # beyond the current scan position
                        extra_reads = carved.get("extra_clusters_read", 0)
                        reads += extra_reads * sectors_per_cluster

        # ─── Phase 2: Resolve ZIP/DOCX ambiguity ─────────────────────
        # ZIP and DOCX share the same PK\x03\x04 header.
        # We try to distinguish them by looking for internal structure.
        carved_files = self._resolve_zip_docx(carved_files)

        # ─── Phase 3: Deduplicate overlapping carves ──────────────────
        # If two signatures overlap (e.g., ZIP and DOCX at same offset),
        # keep the more specific one
        carved_files = self._deduplicate_carves(carved_files)

        # ─── Phase 4: Build result ────────────────────────────────────
        # Assign generic names
        type_counters: Dict[str, int] = {}

        for carved in carved_files:
            ext = carved["extension"]
            type_counters[ext] = type_counters.get(ext, 0) + 1
            name = f"carved_{type_counters[ext]:04d}{ext}"

            data = carved["data"]
            sha256 = hashlib.sha256(data).hexdigest()

            if not found_first_file:
                first_file_reads = reads
                found_first_file = True

            result.recovered_files.append(RecoveredFile(
                name=name,
                sha256=sha256,
                size=len(data),
                data=data,
                source="carving",  # Mark as carving-recovered
                read_count=reads,
            ))

        # ─── Compute final metrics ────────────────────────────────────
        result.read_count = reads
        result.time_to_first_file = first_file_reads
        result.mft_entries_parsed = 0  # NEVER parses MFT
        result.total_time_seconds = reads * 0.001
        result.directories_rebuilt = 0  # No directory support

        # Sectors wasted: we read everything, but not all clusters had files
        # In carving, "wasted" is relative — we had to read everything to find files
        useful_clusters = len(set(
            cf.get("start_cluster", 0) // cluster_size
            for cf in carved_files
        ))
        result.sectors_wasted = max(0, reads - useful_clusters * sectors_per_cluster)

        # Store carving statistics for debugging
        result.carving_stats = {
            "signatures_found": signatures_found,
            "files_carved": len(carved_files),
            "total_clusters_scanned": len(read_clusters),
            "scan_coverage_pct": len(read_clusters) / total_clusters if total_clusters else 0,
        }

        return result

    def _find_signature_matches(self, image: bytes, cluster_start: int,
                                 cluster_size: int, sig: FileSignature,
                                 image_len: int) -> List[int]:
        """
        Find all occurrences of a signature within a cluster.

        Returns list of absolute offsets where the signature was found.
        """
        matches = []

        # Check at the start of the cluster (most common)
        # and at a few key offsets within the first 512 bytes
        check_offsets = [0]

        # Also check at sector-aligned offsets within the cluster
        for sector_offset in range(512, min(cluster_size, 4096), 512):
            check_offsets.append(sector_offset)

        for offset_in_cluster in check_offsets:
            abs_offset = cluster_start + offset_in_cluster
            if abs_offset + sig.header_len > image_len:
                continue

            # Check if header matches (with mask)
            candidate = image[abs_offset:abs_offset + sig.header_len]
            if self._matches_with_mask(candidate, sig.header, sig.header_mask):
                matches.append(abs_offset)

        return matches

    def _matches_with_mask(self, candidate: bytes, header: bytes,
                            mask: bytes) -> bool:
        """Check if candidate bytes match the header pattern with mask."""
        if len(candidate) < len(header):
            return False
        for i in range(len(header)):
            if mask[i] == 0xFF:  # Must match
                if candidate[i] != header[i]:
                    return False
            # 0x00 = don't care, skip
        return True

    def _carve_file(self, image: bytes, start_offset: int,
                     sig: FileSignature, image_len: int,
                     cluster_size: int, total_clusters: int,
                     read_clusters: Set[int]) -> Optional[Dict]:
        """
        Extract a file from the image starting at the given offset.

        Uses footer markers to determine file boundaries.
        If no footer is found, uses max-size heuristic.
        """
        # Check minimum size
        remaining = image_len - start_offset
        if remaining < sig.min_size:
            return None

        # Determine file end
        file_data = None
        extra_clusters_read = 0

        if sig.name == "JPEG":
            # JPEG-specific carving: parse structure to find the real EOI.
            # RC-002: simple footer search (first or last FFD9) fails because
            # the JPEG body can contain spurious FFD9 bytes. Structural parsing
            # correctly identifies the EOI by skipping entropy-coded data.
            file_data = self._carve_jpeg(
                image, start_offset, image_len, sig, cluster_size,
                total_clusters, read_clusters
            )
            if file_data is not None:
                extra_clusters_read = file_data.pop("extra_clusters_read", 0)
        elif sig.footer:
            # Search for footer after the header
            # Start searching from after the header
            footer_search_start = start_offset + sig.header_len
            max_search_end = min(start_offset + sig.max_size, image_len)

            footer_offset = self._find_footer(
                image, footer_search_start, max_search_end, sig.footer
            )

            if footer_offset is not None:
                # Found footer — extract file including footer
                file_end = footer_offset + len(sig.footer)
                file_data = image[start_offset:file_end]

                # Track additional clusters read beyond the scan
                end_cluster = (file_end - 1) // cluster_size
                start_cluster = start_offset // cluster_size
                for c in range(start_cluster, end_cluster + 1):
                    if c not in read_clusters:
                        read_clusters.add(c)
                        extra_clusters_read += 1
            else:
                # No footer found — use max-size heuristic
                # But cap at a reasonable size
                heuristic_size = min(sig.max_size, remaining)
                file_data = image[start_offset:start_offset + heuristic_size]
        else:
            # No footer defined — use max-size heuristic
            # For MP4, try to parse the ftyp box to get the size
            if sig.name == "MP4":
                file_data = self._carve_mp4(image, start_offset, image_len, sig)
            else:
                heuristic_size = min(sig.max_size, remaining)
                file_data = image[start_offset:start_offset + heuristic_size]

        if file_data is None or len(file_data) < sig.min_size:
            return None

        # Validate: check if file is too large (likely a false positive)
        if len(file_data) > sig.max_size:
            file_data = file_data[:sig.max_size]

        return {
            "data": file_data,
            "start_offset": start_offset,
            "start_cluster": start_offset // cluster_size,
            "extension": sig.extension,
            "format_name": sig.name,
            "extra_clusters_read": extra_clusters_read,
            "size": len(file_data),
        }

    def _carve_jpeg(self, image: bytes, start_offset: int,
                     image_len: int, sig: FileSignature,
                     cluster_size: int, total_clusters: int,
                     read_clusters: Set[int]) -> Optional[Dict]:
        """
        Carve a JPEG file by parsing its structure to find the real EOI.
        
        RC-002 fix: three-tier strategy:
          1. Structural parsing (for real JPEGs with SOS marker)
          2. Last FFD9 before next JPEG signature (for synthetic/partial JPEGs)
          3. Last FFD9 within max_size (fallback if no other JPEGs nearby)
        
        The JPEG body can contain spurious FFD9 bytes (EXIF thumbnails,
        random byte coincidences in entropy data). Structural parsing
        correctly identifies EOI by skipping entropy-coded data (byte stuffing).
        For synthetic JPEGs without proper markers, we use the next JPEG
        signature as a boundary to avoid over-extension.
        """
        max_end = min(start_offset + sig.max_size, image_len)
        
        # Verify SOI
        if start_offset + 2 > image_len:
            return None
        if image[start_offset:start_offset + 2] != b'\xFF\xD8':
            return None
        
        # ─── Tier 1: Last FFD9 before next JPEG signature ──────────────
        # For most cases (multiple JPEGs in the image), this is the most
        # reliable approach. The next JPEG signature acts as a natural boundary.
        next_jpeg = self._find_next_jpeg_signature(
            image, start_offset + 4, max_end, cluster_size
        )
        
        if next_jpeg is not None:
            # Search for the last FFD9 before the next JPEG
            search_end = next_jpeg
            last_ffd9 = self._find_footer_last(
                image, start_offset + 4, search_end, b'\xFF\xD9'
            )
            if last_ffd9 is not None:
                file_end = last_ffd9 + 2
                return self._build_jpeg_result(
                    image, start_offset, file_end, sig, cluster_size,
                    total_clusters, read_clusters
                )
        
        # ─── Tier 2: Structural parsing (for real JPEGs with SOS) ──────
        # Only used when there's no next JPEG boundary. This works for
        # real JPEGs with proper markers (SOS, byte stuffing).
        # Not used first because synthetic JPEGs have random FF bytes
        # that create false SOS markers.
        eoi_offset = self._find_jpeg_eoi_structural(image, start_offset, max_end)
        
        if eoi_offset is not None:
            file_end = eoi_offset + 2  # Include the FFD9 bytes
            return self._build_jpeg_result(
                image, start_offset, file_end, sig, cluster_size,
                total_clusters, read_clusters
            )
        
        # ─── Tier 3: Last FFD9 within max_size ─────────────────────────
        # Fallback: no structural parsing success, no next JPEG boundary.
        # Use the last FFD9 within max_size.
        last_ffd9 = self._find_footer_last(
            image, start_offset + 4, max_end, b'\xFF\xD9'
        )
        if last_ffd9 is not None:
            file_end = last_ffd9 + 2
            return self._build_jpeg_result(
                image, start_offset, file_end, sig, cluster_size,
                total_clusters, read_clusters
            )
        
        # No EOI found — use max-size heuristic
        remaining = min(sig.max_size, image_len - start_offset)
        file_data = image[start_offset:start_offset + remaining]
        
        if len(file_data) < sig.min_size:
            return None
        
        return {
            "data": file_data,
            "start_offset": start_offset,
            "start_cluster": start_offset // cluster_size,
            "extension": sig.extension,
            "format_name": sig.name,
            "extra_clusters_read": 0,
            "size": len(file_data),
        }

    def _find_jpeg_eoi_structural(self, image: bytes, start_offset: int,
                                   max_end: int) -> Optional[int]:
        """
        Find the real EOI of a JPEG by parsing its structure.
        
        Returns the offset of the FFD9 marker (not including the marker bytes),
        or None if structural parsing fails.
        """
        pos = start_offset + 2  # Skip SOI
        
        while pos < max_end - 1:
            if image[pos] != 0xFF:
                pos += 1
                continue
            
            marker_byte = image[pos + 1]
            
            # FF 00 = byte stuffing in entropy data (skip)
            # FF FF = padding (skip)
            if marker_byte == 0x00 or marker_byte == 0xFF:
                pos += 1
                continue
            
            # SOS marker (FF DA) — start of entropy-coded data
            if marker_byte == 0xDA:
                if pos + 4 > max_end:
                    return None
                sos_length = struct.unpack('>H', image[pos + 2:pos + 4])[0]
                pos += 2 + sos_length
                
                # Scan entropy data for real EOI
                while pos < max_end - 1:
                    if image[pos] == 0xFF:
                        next_byte = image[pos + 1]
                        if next_byte == 0x00:
                            pos += 2
                            continue
                        if next_byte == 0xFF:
                            pos += 1
                            continue
                        if next_byte == 0xD9:
                            return pos  # Found real EOI
                        # RST markers (D0-D7) — continue in entropy
                        if 0xD0 <= next_byte <= 0xD7:
                            pos += 2
                            continue
                        # Other marker — might be after entropy data
                        pos += 1
                        continue
                    else:
                        pos += 1
                return None  # Ran out of data
            
            # EOI before SOS (unusual but valid)
            if marker_byte == 0xD9:
                return pos
            
            # RST markers — no length field
            if marker_byte in (0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7):
                pos += 2
                continue
            
            # Other markers with length field
            if pos + 4 > max_end:
                return None
            marker_length = struct.unpack('>H', image[pos + 2:pos + 4])[0]
            pos += 2 + marker_length
        
        return None  # Structural parsing failed

    def _find_next_jpeg_signature(self, image: bytes, start: int,
                                    end: int, cluster_size: int = 4096) -> Optional[int]:
        """
        Find the next JPEG signature (FFD8FF) after the given offset.
        
        Used as a boundary for JPEG carving: the last FFD9 before the
        next JPEG is likely the real EOI of the current file.
        
        IMPORTANT: Only accepts signatures at cluster boundaries to avoid
        false positives from random FFD8FF sequences in entropy data.
        In NTFS, files start at cluster boundaries, so a real JPEG signature
        should be aligned to a cluster boundary.
        """
        jpeg_sig = b'\xFF\xD8\xFF'
        pos = start
        
        while pos < end - len(jpeg_sig):
            idx = image.find(jpeg_sig, pos, end)
            if idx == -1:
                return None
            
            # Only accept signatures at cluster boundaries
            # This filters out false FFD8FF sequences in random data
            if idx % cluster_size == 0:
                return idx
            
            # Skip to the next cluster boundary
            next_cluster = ((idx // cluster_size) + 1) * cluster_size
            pos = next_cluster
        
        return None

    def _build_jpeg_result(self, image: bytes, start_offset: int,
                            file_end: int, sig: FileSignature,
                            cluster_size: int, total_clusters: int,
                            read_clusters: Set[int]) -> Optional[Dict]:
        """Build a JPEG carving result dict."""
        file_data = image[start_offset:file_end]
        
        if len(file_data) < sig.min_size:
            return None
        
        if len(file_data) > sig.max_size:
            file_data = file_data[:sig.max_size]
        
        extra_clusters_read = 0
        end_cluster = (file_end - 1) // cluster_size
        start_cluster = start_offset // cluster_size
        for c in range(start_cluster, end_cluster + 1):
            if c not in read_clusters:
                read_clusters.add(c)
                extra_clusters_read += 1
        
        return {
            "data": file_data,
            "start_offset": start_offset,
            "start_cluster": start_offset // cluster_size,
            "extension": sig.extension,
            "format_name": sig.name,
            "extra_clusters_read": extra_clusters_read,
            "size": len(file_data),
        }

    def _find_footer(self, image: bytes, start: int, end: int,
                      footer: bytes) -> Optional[int]:
        """
        Find the first occurrence of footer bytes in the image.

        Uses a simple scan. For large images, this could be optimized
        with a Boyer-Moore search, but for our 10MB images it's fine.
        """
        footer_len = len(footer)
        if footer_len == 0:
            return None

        # Search in chunks to avoid excessive memory usage
        chunk_size = 1024 * 1024  # 1MB chunks
        pos = start

        while pos < end:
            chunk_end = min(pos + chunk_size + footer_len, end + footer_len)
            chunk = image[pos:chunk_end]

            idx = chunk.find(footer)
            if idx != -1:
                return pos + idx

            pos += chunk_size

        return None

    def _find_footer_last(self, image: bytes, start: int, end: int,
                          footer: bytes) -> Optional[int]:
        """
        Find the LAST occurrence of footer bytes in the image.

        Used for JPEG delimitation where the body may contain multiple
        FFD9 sequences (EXIF thumbnails, random byte coincidences, or
        embedded JPEG data). The real EOI marker is the last FFD9, not
        the first one.

        RC-002 fix: previous _find_footer() found the first FFD9, causing
        severe truncation when the JPEG body contained spurious FFD9 bytes.
        """
        footer_len = len(footer)
        if footer_len == 0:
            return None

        last_found = None
        chunk_size = 1024 * 1024  # 1MB chunks
        pos = start

        while pos < end:
            chunk_end = min(pos + chunk_size + footer_len, end + footer_len)
            chunk = image[pos:chunk_end]

            # Find ALL occurrences in this chunk
            search_pos = 0
            while search_pos < len(chunk):
                idx = chunk.find(footer, search_pos)
                if idx == -1:
                    break
                last_found = pos + idx
                search_pos = idx + 1

            pos += chunk_size

        return last_found

    def _carve_mp4(self, image: bytes, start_offset: int,
                    image_len: int, sig: FileSignature) -> Optional[bytes]:
        """
        Carve an MP4 file by parsing the ftyp box to determine size.

        MP4 structure: a series of boxes (atoms), each with:
          [4 bytes size][4 bytes type][data...]
        The first box is typically 'ftyp'.
        """
        # The 'ftyp' is at offset 4 within the first box
        # So the first box starts at start_offset - 4
        box_start = start_offset - 4

        if box_start < 0 or box_start + 8 > image_len:
            # Can't parse box header — use max-size heuristic
            remaining = min(sig.max_size, image_len - start_offset)
            return image[start_offset:start_offset + remaining]

        # Read first box size
        try:
            box_size = struct.unpack('>I', image[box_start:box_start + 4])[0]
        except:
            remaining = min(sig.max_size, image_len - start_offset)
            return image[start_offset:start_offset + remaining]

        if box_size == 0:
            # Box extends to end of file
            return image[box_start:image_len]
        elif box_size == 1:
            # 64-bit extended size
            if box_start + 16 > image_len:
                remaining = min(sig.max_size, image_len - start_offset)
                return image[start_offset:start_offset + remaining]
            box_size = struct.unpack('>Q', image[box_start + 8:box_start + 16])[0]

        # Sanity check
        if box_size > sig.max_size or box_size < 8:
            remaining = min(sig.max_size, image_len - start_offset)
            return image[start_offset:start_offset + remaining]

        end = box_start + box_size
        if end > image_len:
            end = image_len

        return image[box_start:end]

    def _resolve_zip_docx(self, carved_files: List[Dict]) -> List[Dict]:
        """
        Resolve ZIP/DOCX/XLSX ambiguity.

        All three share the PK\x03\x04 header. We try to distinguish them
        by looking for internal structure markers:
          - DOCX contains "word/" or "word/document.xml"
          - XLSX contains "xl/" or "xl/workbook.xml"
          - ZIP contains other content

        If we find multiple carves at the same offset (ZIP/DOCX/XLSX),
        we keep the one that matches best.
        """
        # Group by start offset
        by_offset: Dict[int, List[Dict]] = {}
        for cf in carved_files:
            offset = cf["start_offset"]
            if offset not in by_offset:
                by_offset[offset] = []
            by_offset[offset].append(cf)

        resolved = []
        for offset, files in by_offset.items():
            if len(files) == 1:
                resolved.append(files[0])
                continue

            # Multiple carves at same offset — likely ZIP/DOCX/XLSX overlap
            # Check internal content for format-specific markers
            data = files[0]["data"]

            has_docx_markers = (
                b'word/' in data or
                b'word/document.xml' in data or
                b'Content_Types.xml' in data
            )

            has_xlsx_markers = (
                b'xl/' in data or
                b'xl/workbook.xml' in data or
                b'xl/worksheets/' in data
            )

            if has_xlsx_markers:
                # Keep the XLSX version
                for f in files:
                    if f["format_name"] == "XLSX":
                        resolved.append(f)
                        break
                else:
                    # No XLSX entry found — convert the first ZIP to XLSX
                    files[0]["extension"] = ".xlsx"
                    files[0]["format_name"] = "XLSX"
                    resolved.append(files[0])
            elif has_docx_markers:
                # Keep the DOCX version
                for f in files:
                    if f["format_name"] == "DOCX":
                        resolved.append(f)
                        break
                else:
                    # No DOCX entry found — convert the ZIP to DOCX
                    files[0]["extension"] = ".docx"
                    files[0]["format_name"] = "DOCX"
                    resolved.append(files[0])
            else:
                # Keep the ZIP version
                for f in files:
                    if f["format_name"] == "ZIP":
                        resolved.append(f)
                        break
                else:
                    resolved.append(files[0])

        return resolved

    def _deduplicate_carves(self, carved_files: List[Dict]) -> List[Dict]:
        """
        Remove duplicate carves that overlap significantly.

        If two carves overlap by >50% of the smaller one, keep the larger one.
        """
        if len(carved_files) <= 1:
            return carved_files

        # Sort by start offset
        sorted_files = sorted(carved_files, key=lambda f: f["start_offset"])

        deduped = []
        for cf in sorted_files:
            is_duplicate = False

            for existing in deduped:
                # Check overlap
                overlap_start = max(cf["start_offset"], existing["start_offset"])
                overlap_end = min(
                    cf["start_offset"] + cf["size"],
                    existing["start_offset"] + existing["size"]
                )

                if overlap_start < overlap_end:
                    overlap_size = overlap_end - overlap_start
                    smaller_size = min(cf["size"], existing["size"])

                    if overlap_size > smaller_size * 0.5:
                        # Significant overlap — keep the larger one
                        if cf["size"] > existing["size"]:
                            deduped.remove(existing)
                            deduped.append(cf)
                        is_duplicate = True
                        break

            if not is_duplicate:
                deduped.append(cf)

        return deduped
