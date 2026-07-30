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
        footer=b'%%EOF',
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

        if sig.footer:
            # Search for footer after the header
            # Start searching from after the header
            footer_search_start = start_offset + sig.header_len
            max_search_end = min(start_offset + sig.max_size, image_len)

            # Search for footer
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
        Resolve ZIP/DOCX ambiguity.

        Both share the PK\x03\x04 header. We try to distinguish them
        by looking for internal structure markers:
          - DOCX contains "word/" or "word/document.xml"
          - ZIP contains other content

        If we find two carves at the same offset (one ZIP, one DOCX),
        we keep the one that matches better.
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

            # Multiple carves at same offset — likely ZIP/DOCX overlap
            # Check internal content for DOCX markers
            data = files[0]["data"]

            has_docx_markers = (
                b'word/' in data or
                b'word/document.xml' in data or
                b'Content_Types.xml' in data
            )

            if has_docx_markers:
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
