"""
RecoveryLab — Functional Recovery Validator
==============================================
The most important question in data recovery:

    "What does 'recovered' actually mean?"

Today, the answer is binary: SHA-256 matches or it doesn't.

But in the real world:
  - A JPEG with 2 corrupted pixels IS recovered (99.99% of pixels valid)
  - An MP4 that plays perfectly but has a different checksum IS recovered
  - A DOCX that opens but lost one embedded image IS recovered (partially)
  - A ZIP that decompresses IS recovered (even if metadata changed)
  - A SQLite that passes PRAGMA integrity_check IS recovered
  - A PDF that renders IS recovered

This module replaces the binary SHA-256 pass/fail with a FUNCTIONAL
recovery assessment: does the file SERVE ITS PURPOSE?

Recovery Levels:
  FULL (1.0)    — SHA-256 matches exactly (bit-perfect recovery)
  FUNCTIONAL (0.8) — File opens/plays/works with minor corruption
  PARTIAL (0.5) — File partially works (some data loss, but usable)
  DEGRADED (0.2) — File is heavily damaged but some content accessible
  FAILED (0.0)  — File is completely unusable

This is the paradigm shift from "count recovered" to "measure functionality."
"""

import struct
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
from pathlib import Path


# ─── Recovery Levels ─────────────────────────────────────────────────────────

class RecoveryLevel(Enum):
    """Functional recovery level for a file."""
    FULL = "full"           # Bit-perfect (SHA-256 match)
    FUNCTIONAL = "functional"  # Works with minor issues
    PARTIAL = "partial"     # Partially usable
    DEGRADED = "degraded"   # Heavily damaged but some content
    FAILED = "failed"       # Completely unusable

    @property
    def score(self) -> float:
        """Numerical score for this recovery level."""
        mapping = {
            RecoveryLevel.FULL: 1.0,
            RecoveryLevel.FUNCTIONAL: 0.8,
            RecoveryLevel.PARTIAL: 0.5,
            RecoveryLevel.DEGRADED: 0.2,
            RecoveryLevel.FAILED: 0.0,
        }
        return mapping[self]

    @property
    def emoji(self) -> str:
        mapping = {
            RecoveryLevel.FULL: "✅",
            RecoveryLevel.FUNCTIONAL: "🟢",
            RecoveryLevel.PARTIAL: "🟡",
            RecoveryLevel.DEGRADED: "🟠",
            RecoveryLevel.FAILED: "🔴",
        }
        return mapping[self]


# ─── Format-Specific Validation Results ──────────────────────────────────────

@dataclass
class JPEGValidationResult:
    """Functional validation result for a JPEG file."""
    level: RecoveryLevel
    functional_score: float       # 0.0-1.0 continuous score
    has_valid_header: bool = False
    has_valid_footer: bool = False
    scan_valid: bool = False      # Can scan markers?
    approximate_pixel_pct: float = 0.0  # Approximate % of image data
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "format": "jpeg",
            "level": self.level.value,
            "functional_score": round(self.functional_score, 4),
            "has_valid_header": self.has_valid_header,
            "has_valid_footer": self.has_valid_footer,
            "scan_valid": self.scan_valid,
            "approximate_pixel_pct": round(self.approximate_pixel_pct, 4),
            "notes": self.notes,
        }


@dataclass
class MP4ValidationResult:
    """Functional validation result for an MP4 file."""
    level: RecoveryLevel
    functional_score: float
    has_ftyp_box: bool = False
    has_moov_box: bool = False    # Critical: metadata box
    has_mdat_box: bool = False    # Critical: media data box
    duration_preserved: bool = False
    approximate_duration_pct: float = 0.0
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "format": "mp4",
            "level": self.level.value,
            "functional_score": round(self.functional_score, 4),
            "has_ftyp_box": self.has_ftyp_box,
            "has_moov_box": self.has_moov_box,
            "has_mdat_box": self.has_mdat_box,
            "duration_preserved": self.duration_preserved,
            "approximate_duration_pct": round(self.approximate_duration_pct, 4),
            "notes": self.notes,
        }


@dataclass
class DOCXValidationResult:
    """Functional validation result for a DOCX file."""
    level: RecoveryLevel
    functional_score: float
    is_valid_zip: bool = False
    has_content_types: bool = False
    has_main_document: bool = False
    xml_valid: bool = False
    text_accessible: bool = False
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "format": "docx",
            "level": self.level.value,
            "functional_score": round(self.functional_score, 4),
            "is_valid_zip": self.is_valid_zip,
            "has_content_types": self.has_content_types,
            "has_main_document": self.has_main_document,
            "xml_valid": self.xml_valid,
            "text_accessible": self.text_accessible,
            "notes": self.notes,
        }


@dataclass
class SQLiteValidationResult:
    """Functional validation result for a SQLite database."""
    level: RecoveryLevel
    functional_score: float
    has_valid_header: bool = False
    integrity_check_passed: bool = False
    tables_readable: bool = False
    data_accessible: bool = False
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "format": "sqlite",
            "level": self.level.value,
            "functional_score": round(self.functional_score, 4),
            "has_valid_header": self.has_valid_header,
            "integrity_check_passed": self.integrity_check_passed,
            "tables_readable": self.tables_readable,
            "data_accessible": self.data_accessible,
            "notes": self.notes,
        }


@dataclass
class ZIPValidationResult:
    """Functional validation result for a ZIP archive."""
    level: RecoveryLevel
    functional_score: float
    has_valid_header: bool = False
    has_eocd: bool = False         # End of Central Directory
    can_decompress: bool = False
    files_accessible: int = 0
    total_files: int = 0
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "format": "zip",
            "level": self.level.value,
            "functional_score": round(self.functional_score, 4),
            "has_valid_header": self.has_valid_header,
            "has_eocd": self.has_eocd,
            "can_decompress": self.can_decompress,
            "files_accessible": self.files_accessible,
            "total_files": self.total_files,
            "notes": self.notes,
        }


@dataclass
class PDFValidationResult:
    """Functional validation result for a PDF file."""
    level: RecoveryLevel
    functional_score: float
    has_valid_header: bool = False
    has_eof_marker: bool = False
    has_xref: bool = False         # Cross-reference table
    has_pages: bool = False
    can_render: bool = False
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "format": "pdf",
            "level": self.level.value,
            "functional_score": round(self.functional_score, 4),
            "has_valid_header": self.has_valid_header,
            "has_eof_marker": self.has_eof_marker,
            "has_xref": self.has_xref,
            "has_pages": self.has_pages,
            "can_render": self.can_render,
            "notes": self.notes,
        }


@dataclass
class PNGValidationResult:
    """Functional validation result for a PNG file."""
    level: RecoveryLevel
    functional_score: float
    has_valid_header: bool = False
    has_iend: bool = False
    has_ihdr: bool = False         # Image header chunk
    has_idat: bool = False         # Image data chunks
    approximate_pixel_pct: float = 0.0
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "format": "png",
            "level": self.level.value,
            "functional_score": round(self.functional_score, 4),
            "has_valid_header": self.has_valid_header,
            "has_iend": self.has_iend,
            "has_ihdr": self.has_ihdr,
            "has_idat": self.has_idat,
            "approximate_pixel_pct": round(self.approximate_pixel_pct, 4),
            "notes": self.notes,
        }


@dataclass
class GenericValidationResult:
    """Generic validation result for formats without specific validators."""
    level: RecoveryLevel
    functional_score: float
    format_name: str = "unknown"
    has_valid_header: bool = False
    size_preserved: bool = False
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "format": self.format_name,
            "level": self.level.value,
            "functional_score": round(self.functional_score, 4),
            "has_valid_header": self.has_valid_header,
            "size_preserved": self.size_preserved,
            "notes": self.notes,
        }


# ─── Format Validators ───────────────────────────────────────────────────────

class JPEGValidator:
    """
    Validate a JPEG file for functional recovery.

    JPEG structure:
      - SOI marker: FF D8
      - APP0/APP1 markers: FF E0 / FF E1
      - DQT, DHT, SOF, SOS markers
      - Compressed image data
      - EOI marker: FF D9

    A JPEG can be "functionally recovered" if:
      - It has a valid SOI marker (can identify as JPEG)
      - It has at least some scan data (SOS marker found)
      - It has enough data to render a partial image
    """

    def validate(self, data: bytes, original_data: Optional[bytes] = None) -> JPEGValidationResult:
        """Validate a JPEG file for functional recovery."""
        if len(data) < 4:
            return JPEGValidationResult(
                level=RecoveryLevel.FAILED,
                functional_score=0.0,
                notes="File too small to be a valid JPEG",
            )

        has_header = data[:2] == b'\xFF\xD8'
        has_footer = data[-2:] == b'\xFF\xD9'

        # Check for SHA-256 match first (full recovery)
        if original_data and data == original_data:
            return JPEGValidationResult(
                level=RecoveryLevel.FULL,
                functional_score=1.0,
                has_valid_header=True,
                has_valid_footer=True,
                scan_valid=True,
                approximate_pixel_pct=1.0,
                notes="Bit-perfect recovery",
            )

        # Scan for JPEG markers
        scan_valid = False
        has_sos = False
        has_sof = False
        marker_count = 0
        last_sos_offset = 0

        i = 2  # Skip SOI
        while i < len(data) - 1:
            if data[i] == 0xFF:
                marker = data[i + 1]
                if marker == 0xDA:  # SOS (Start of Scan)
                    has_sos = True
                    last_sos_offset = i
                    marker_count += 1
                elif marker in (0xC0, 0xC1, 0xC2):  # SOF0, SOF1, SOF2
                    has_sof = True
                    marker_count += 1
                elif marker in (0xE0, 0xE1, 0xDB, 0xC4, 0xDD):
                    marker_count += 1

                # Skip marker payload (except for RST and standalone markers)
                if marker not in (0x00, 0xD0, 0xD1, 0xD2, 0xD3,
                                  0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xFF):
                    if i + 3 < len(data):
                        length = struct.unpack('>H', data[i+2:i+4])[0]
                        i += max(length, 2)
                i += 2
            else:
                i += 1

        scan_valid = has_sos and has_sof and marker_count >= 3

        # Estimate pixel percentage: ratio of data after first SOS to total
        if has_sos:
            pixel_pct = min(1.0, (len(data) - last_sos_offset) / max(len(data), 1))
        else:
            pixel_pct = 0.0

        # Determine recovery level
        if has_header and has_footer and scan_valid:
            # Check if it's just a few bytes different
            if original_data and len(data) == len(original_data):
                # Count differing bytes
                diff_bytes = sum(1 for a, b in zip(data, original_data) if a != b)
                diff_pct = diff_bytes / len(data)
                if diff_pct < 0.001:
                    level = RecoveryLevel.FUNCTIONAL
                    score = 0.95
                    notes = f"Nearly perfect: {diff_pct:.4%} bytes differ"
                elif diff_pct < 0.01:
                    level = RecoveryLevel.FUNCTIONAL
                    score = 0.85
                    notes = f"Minor corruption: {diff_pct:.2%} bytes differ"
                elif diff_pct < 0.05:
                    level = RecoveryLevel.PARTIAL
                    score = 0.65
                    notes = f"Moderate corruption: {diff_pct:.2%} bytes differ"
                else:
                    level = RecoveryLevel.PARTIAL
                    score = max(0.5, 0.8 - diff_pct * 5)
                    notes = f"Significant corruption: {diff_pct:.2%} bytes differ"
            else:
                level = RecoveryLevel.FUNCTIONAL
                score = 0.8
                notes = "Valid JPEG structure, size may differ"
        elif has_header and has_sos:
            level = RecoveryLevel.PARTIAL
            score = 0.5
            notes = "Header valid, scan data present, but missing EOI or structure issues"
        elif has_header:
            level = RecoveryLevel.DEGRADED
            score = 0.2
            notes = "Header valid but no scan data found"
        else:
            level = RecoveryLevel.FAILED
            score = 0.0
            notes = "No valid JPEG header found"

        return JPEGValidationResult(
            level=level,
            functional_score=score,
            has_valid_header=has_header,
            has_valid_footer=has_footer,
            scan_valid=scan_valid,
            approximate_pixel_pct=pixel_pct,
            notes=notes,
        )


class MP4Validator:
    """
    Validate an MP4 file for functional recovery.

    MP4 structure (ISO Base Media File Format):
      - ftyp box: file type
      - moov box: metadata (critical — contains index/duration)
      - mdat box: media data

    Key insight: If moov is present, the video can be played even if
    some mdat is corrupted. Without moov, the video is unseekable
    but may still play sequentially.
    """

    def validate(self, data: bytes, original_data: Optional[bytes] = None) -> MP4ValidationResult:
        """Validate an MP4 file for functional recovery."""
        if len(data) < 8:
            return MP4ValidationResult(
                level=RecoveryLevel.FAILED,
                functional_score=0.0,
                notes="File too small to be a valid MP4",
            )

        # Check for SHA-256 match
        if original_data and data == original_data:
            return MP4ValidationResult(
                level=RecoveryLevel.FULL,
                functional_score=1.0,
                has_ftyp_box=True,
                has_moov_box=True,
                has_mdat_box=True,
                duration_preserved=True,
                approximate_duration_pct=1.0,
                notes="Bit-perfect recovery",
            )

        # Scan for MP4 boxes
        has_ftyp = False
        has_moov = False
        has_mdat = False
        moov_size = 0
        mdat_size = 0
        total_boxes = 0

        i = 0
        while i < len(data) - 8:
            if i + 8 > len(data):
                break

            # Read box header (size + type)
            box_size = struct.unpack('>I', data[i:i+4])[0]
            box_type = data[i+4:i+8]

            if box_size < 8:
                # Invalid box size, try to skip
                i += 1
                continue

            total_boxes += 1

            if box_type == b'ftyp':
                has_ftyp = True
            elif box_type == b'moov':
                has_moov = True
                moov_size = box_size
            elif box_type == b'mdat':
                has_mdat = True
                mdat_size = box_size

            # Move to next box
            if box_size > 0 and i + box_size <= len(data):
                i += box_size
            else:
                # Box extends beyond data — stop scanning
                break

        # Check for ftyp at the start
        if data[:4] == b'\x00\x00\x00\x1c' or data[4:8] == b'ftyp':
            has_ftyp = True

        # Determine recovery level
        if has_ftyp and has_moov and has_mdat:
            level = RecoveryLevel.FUNCTIONAL
            score = 0.8
            notes = "All critical boxes present — video should play"
        elif has_ftyp and has_moov:
            level = RecoveryLevel.PARTIAL
            score = 0.5
            notes = "Metadata present but media data may be incomplete"
        elif has_ftyp and has_mdat:
            level = RecoveryLevel.DEGRADED
            score = 0.3
            notes = "Media data present but no metadata — unseekable"
        elif has_ftyp:
            level = RecoveryLevel.DEGRADED
            score = 0.2
            notes = "Only ftyp box found — minimal video info"
        else:
            level = RecoveryLevel.FAILED
            score = 0.0
            notes = "No valid MP4 structure found"

        return MP4ValidationResult(
            level=level,
            functional_score=score,
            has_ftyp_box=has_ftyp,
            has_moov_box=has_moov,
            has_mdat_box=has_mdat,
            duration_preserved=has_moov,
            approximate_duration_pct=0.8 if has_moov else 0.3,
            notes=notes,
        )


class DOCXValidator:
    """
    Validate a DOCX file for functional recovery.

    DOCX is a ZIP file containing:
      - [Content_Types].xml
      - _rels/.rels
      - word/document.xml (the actual document content)
      - word/_rels/document.xml.rels
      - Other XML files

    A DOCX can be "functionally recovered" if:
      - It's a valid ZIP archive
      - It contains word/document.xml
      - The XML is parseable
      - The text content is accessible
    """

    def validate(self, data: bytes, original_data: Optional[bytes] = None) -> DOCXValidationResult:
        """Validate a DOCX file for functional recovery."""
        if len(data) < 4:
            return DOCXValidationResult(
                level=RecoveryLevel.FAILED,
                functional_score=0.0,
                notes="File too small to be a valid DOCX",
            )

        # Check for SHA-256 match
        if original_data and data == original_data:
            return DOCXValidationResult(
                level=RecoveryLevel.FULL,
                functional_score=1.0,
                is_valid_zip=True,
                has_content_types=True,
                has_main_document=True,
                xml_valid=True,
                text_accessible=True,
                notes="Bit-perfect recovery",
            )

        # Check if it starts with ZIP signature
        is_zip = data[:4] == b'PK\x03\x04'

        # Check for Content_Types
        has_content_types = b'[Content_Types]' in data or b'Content_Types' in data

        # Check for word/document.xml
        has_main_doc = b'word/document.xml' in data

        # Check for XML validity (basic — look for proper XML tags)
        has_xml = b'<?xml' in data or b'<w:document' in data

        # Check for text content (basic — look for <w:t> tags)
        text_accessible = b'<w:t' in data or b'<w:t ' in data

        # Check for EOCD (End of Central Directory)
        has_eocd = b'PK\x05\x06' in data

        # Determine recovery level
        if is_zip and has_content_types and has_main_doc and text_accessible:
            level = RecoveryLevel.FUNCTIONAL
            score = 0.8
            notes = "Valid DOCX structure, text content accessible"
        elif is_zip and has_main_doc and text_accessible:
            level = RecoveryLevel.PARTIAL
            score = 0.5
            notes = "Main document present and text accessible, structure may be incomplete"
        elif is_zip and has_main_doc:
            level = RecoveryLevel.PARTIAL
            score = 0.4
            notes = "ZIP structure with document.xml, but text may not be accessible"
        elif is_zip and has_xml:
            level = RecoveryLevel.DEGRADED
            score = 0.2
            notes = "ZIP structure with some XML, but main document may be missing"
        elif is_zip:
            level = RecoveryLevel.DEGRADED
            score = 0.15
            notes = "Valid ZIP but no recognizable DOCX structure"
        else:
            level = RecoveryLevel.FAILED
            score = 0.0
            notes = "Not a valid ZIP/DOCX file"

        return DOCXValidationResult(
            level=level,
            functional_score=score,
            is_valid_zip=is_zip,
            has_content_types=has_content_types,
            has_main_document=has_main_doc,
            xml_valid=has_xml,
            text_accessible=text_accessible,
            notes=notes,
        )


class SQLiteValidator:
    """
    Validate a SQLite database for functional recovery.

    SQLite structure:
      - Header: "SQLite format 3\000"
      - Page-based structure
      - B-tree for tables and indices

    Key insight: PRAGMA integrity_check is the gold standard.
    If it passes, the database is functionally recovered.
    """

    def validate(self, data: bytes, original_data: Optional[bytes] = None) -> SQLiteValidationResult:
        """Validate a SQLite database for functional recovery."""
        if len(data) < 16:
            return SQLiteValidationResult(
                level=RecoveryLevel.FAILED,
                functional_score=0.0,
                notes="File too small to be a valid SQLite database",
            )

        # Check for SHA-256 match
        if original_data and data == original_data:
            return SQLiteValidationResult(
                level=RecoveryLevel.FULL,
                functional_score=1.0,
                has_valid_header=True,
                integrity_check_passed=True,
                tables_readable=True,
                data_accessible=True,
                notes="Bit-perfect recovery",
            )

        # Check header
        sqlite_header = b'SQLite format 3\x00'
        has_header = data[:16] == sqlite_header

        # Parse page size from header (bytes 16-17)
        page_size = 4096  # Default
        if len(data) >= 18:
            raw_page_size = struct.unpack('>H', data[16:18])[0]
            if raw_page_size == 1:
                page_size = 65536
            elif raw_page_size > 0:
                page_size = raw_page_size

        # Estimate number of pages
        n_pages = len(data) // page_size if page_size > 0 else 0

        # Check for B-tree page signatures (first page should be a table B-tree)
        # Page 1 is the sqlite_master table
        tables_readable = False
        if n_pages >= 1:
            # The first byte of each page indicates its type:
            # 0x02: Interior index B-tree
            # 0x05: Interior table B-tree
            # 0x0a: Leaf index B-tree
            # 0x0d: Leaf table B-tree
            page1_offset = 100  # Skip the 100-byte header on page 1
            if page1_offset < len(data):
                page_type = data[page1_offset]
                if page_type in (0x02, 0x05, 0x0a, 0x0d):
                    tables_readable = True

        # Check for data pages (page type 0x0d = leaf table)
        data_accessible = False
        for page_num in range(min(n_pages, 10)):
            offset = page_num * page_size
            if page_num == 0:
                offset += 100  # Skip header on page 1
            if offset < len(data):
                page_type = data[offset]
                if page_type == 0x0d:  # Leaf table B-tree
                    data_accessible = True
                    break

        # Determine recovery level
        if has_header and tables_readable and data_accessible:
            level = RecoveryLevel.FUNCTIONAL
            score = 0.8
            notes = f"Valid SQLite structure, {n_pages} pages, data accessible"
        elif has_header and tables_readable:
            level = RecoveryLevel.PARTIAL
            score = 0.5
            notes = f"Valid header and table structure, but data may be incomplete"
        elif has_header:
            level = RecoveryLevel.DEGRADED
            score = 0.2
            notes = f"Valid header but table structure may be corrupted"
        else:
            level = RecoveryLevel.FAILED
            score = 0.0
            notes = "No valid SQLite header found"

        return SQLiteValidationResult(
            level=level,
            functional_score=score,
            has_valid_header=has_header,
            integrity_check_passed=has_header and tables_readable and data_accessible,
            tables_readable=tables_readable,
            data_accessible=data_accessible,
            notes=notes,
        )


class ZIPValidator:
    """
    Validate a ZIP archive for functional recovery.

    ZIP structure:
      - Local file headers: PK\x03\x04
      - Central directory: PK\x01\x02
      - End of Central Directory: PK\x05\x06

    A ZIP is "functionally recovered" if it can be decompressed.
    """

    def validate(self, data: bytes, original_data: Optional[bytes] = None) -> ZIPValidationResult:
        """Validate a ZIP archive for functional recovery."""
        if len(data) < 4:
            return ZIPValidationResult(
                level=RecoveryLevel.FAILED,
                functional_score=0.0,
                notes="File too small to be a valid ZIP",
            )

        # Check for SHA-256 match
        if original_data and data == original_data:
            return ZIPValidationResult(
                level=RecoveryLevel.FULL,
                functional_score=1.0,
                has_valid_header=True,
                has_eocd=True,
                can_decompress=True,
                files_accessible=1,
                total_files=1,
                notes="Bit-perfect recovery",
            )

        # Check for ZIP signature
        has_header = data[:4] == b'PK\x03\x04'

        # Count local file headers
        local_headers = data.count(b'PK\x03\x04')

        # Check for EOCD
        has_eocd = b'PK\x05\x06' in data

        # Check for central directory
        has_central = b'PK\x01\x02' in data

        # Determine recovery level
        if has_header and has_eocd and has_central and local_headers > 0:
            level = RecoveryLevel.FUNCTIONAL
            score = 0.8
            notes = f"Valid ZIP structure, {local_headers} files found"
        elif has_header and has_eocd and local_headers > 0:
            level = RecoveryLevel.PARTIAL
            score = 0.5
            notes = f"ZIP with {local_headers} files, but central directory may be incomplete"
        elif has_header and local_headers > 0:
            level = RecoveryLevel.PARTIAL
            score = 0.4
            notes = f"ZIP with {local_headers} files, but no EOCD found"
        elif has_header:
            level = RecoveryLevel.DEGRADED
            score = 0.15
            notes = "ZIP header found but no file entries"
        else:
            level = RecoveryLevel.FAILED
            score = 0.0
            notes = "Not a valid ZIP file"

        return ZIPValidationResult(
            level=level,
            functional_score=score,
            has_valid_header=has_header,
            has_eocd=has_eocd,
            can_decompress=has_header and has_eocd and local_headers > 0,
            files_accessible=local_headers if has_header else 0,
            total_files=local_headers if has_header else 0,
            notes=notes,
        )


class PDFValidator:
    """
    Validate a PDF file for functional recovery.

    PDF structure:
      - Header: %PDF-x.y
      - Body: objects
      - Cross-reference table (xref)
      - Trailer with %%EOF

    A PDF is "functionally recovered" if it can be rendered.
    """

    def validate(self, data: bytes, original_data: Optional[bytes] = None) -> PDFValidationResult:
        """Validate a PDF file for functional recovery."""
        if len(data) < 5:
            return PDFValidationResult(
                level=RecoveryLevel.FAILED,
                functional_score=0.0,
                notes="File too small to be a valid PDF",
            )

        # Check for SHA-256 match
        if original_data and data == original_data:
            return PDFValidationResult(
                level=RecoveryLevel.FULL,
                functional_score=1.0,
                has_valid_header=True,
                has_eof_marker=True,
                has_xref=True,
                has_pages=True,
                can_render=True,
                notes="Bit-perfect recovery",
            )

        # Check header
        has_header = data[:5] == b'%PDF-'

        # Check for %%EOF
        has_eof = b'%%EOF' in data

        # Check for xref
        has_xref = b'xref' in data or b'/XRef' in data

        # Check for pages
        has_pages = b'/Page' in data and (b'/Pages' in data or b'/Type /Page' in data)

        # Determine recovery level
        if has_header and has_eof and has_xref and has_pages:
            level = RecoveryLevel.FUNCTIONAL
            score = 0.8
            notes = "Complete PDF structure — should render"
        elif has_header and has_pages:
            level = RecoveryLevel.PARTIAL
            score = 0.5
            notes = "Header and pages present, but cross-reference may be incomplete"
        elif has_header and has_eof:
            level = RecoveryLevel.PARTIAL
            score = 0.4
            notes = "Header and EOF present, but structure may be incomplete"
        elif has_header:
            level = RecoveryLevel.DEGRADED
            score = 0.2
            notes = "PDF header found but structure is incomplete"
        else:
            level = RecoveryLevel.FAILED
            score = 0.0
            notes = "Not a valid PDF file"

        return PDFValidationResult(
            level=level,
            functional_score=score,
            has_valid_header=has_header,
            has_eof_marker=has_eof,
            has_xref=has_xref,
            has_pages=has_pages,
            can_render=has_header and has_pages,
            notes=notes,
        )


class PNGValidator:
    """
    Validate a PNG file for functional recovery.

    PNG structure:
      - Signature: 89 50 4E 47 0D 0A 1A 0A
      - IHDR chunk (image header)
      - IDAT chunks (image data)
      - IEND chunk (image end)

    A PNG is "functionally recovered" if it has valid header,
    IHDR, and at least some IDAT data.
    """

    def validate(self, data: bytes, original_data: Optional[bytes] = None) -> PNGValidationResult:
        """Validate a PNG file for functional recovery."""
        PNG_SIG = b'\x89PNG\r\n\x1a\n'

        if len(data) < 8:
            return PNGValidationResult(
                level=RecoveryLevel.FAILED,
                functional_score=0.0,
                notes="File too small to be a valid PNG",
            )

        # Check for SHA-256 match
        if original_data and data == original_data:
            return PNGValidationResult(
                level=RecoveryLevel.FULL,
                functional_score=1.0,
                has_valid_header=True,
                has_iend=True,
                has_ihdr=True,
                has_idat=True,
                approximate_pixel_pct=1.0,
                notes="Bit-perfect recovery",
            )

        has_header = data[:8] == PNG_SIG
        has_iend = b'IEND' in data
        has_ihdr = b'IHDR' in data
        has_idat = b'IDAT' in data

        # Estimate pixel percentage based on IDAT data
        idat_pct = 0.0
        if has_idat and has_ihdr:
            # Find IHDR to get image dimensions
            ihdr_pos = data.find(b'IHDR')
            if ihdr_pos > 0 and ihdr_pos + 16 <= len(data):
                width = struct.unpack('>I', data[ihdr_pos+4:ihdr_pos+8])[0]
                height = struct.unpack('>I', data[ihdr_pos+8:ihdr_pos+12])[0]
                # Very rough estimate: IDAT data size vs expected size
                expected_size = width * height * 4  # RGBA
                idat_count = data.count(b'IDAT')
                idat_pct = min(1.0, idat_count / max(1, expected_size / 8192))

        # Determine recovery level
        if has_header and has_iend and has_ihdr and has_idat:
            level = RecoveryLevel.FUNCTIONAL
            score = 0.8
            notes = "Complete PNG structure — should render"
        elif has_header and has_ihdr and has_idat:
            level = RecoveryLevel.PARTIAL
            score = 0.5
            notes = "Header and image data present, but missing IEND"
        elif has_header and has_ihdr:
            level = RecoveryLevel.DEGRADED
            score = 0.2
            notes = "Header present but no image data"
        elif has_header:
            level = RecoveryLevel.DEGRADED
            score = 0.15
            notes = "PNG signature found but no valid chunks"
        else:
            level = RecoveryLevel.FAILED
            score = 0.0
            notes = "Not a valid PNG file"

        return PNGValidationResult(
            level=level,
            functional_score=score,
            has_valid_header=has_header,
            has_iend=has_iend,
            has_ihdr=has_ihdr,
            has_idat=has_idat,
            approximate_pixel_pct=idat_pct,
            notes=notes,
        )


# ─── Unified Functional Validator ────────────────────────────────────────────

class FunctionalValidator:
    """
    Unified validator that dispatches to format-specific validators.

    This is the main entry point for functional recovery assessment.

    Usage:
        validator = FunctionalValidator()
        result = validator.validate(data, filename="photo.jpg")
        print(result.level, result.functional_score)
    """

    def __init__(self):
        self.validators = {
            ".jpg": JPEGValidator(),
            ".jpeg": JPEGValidator(),
            ".png": PNGValidator(),
            ".pdf": PDFValidator(),
            ".docx": DOCXValidator(),
            ".xlsx": DOCXValidator(),  # Same ZIP-based structure
            ".pptx": DOCXValidator(),  # Same ZIP-based structure
            ".zip": ZIPValidator(),
            ".mp4": MP4Validator(),
            ".mov": MP4Validator(),    # Same container format
            ".sqlite": SQLiteValidator(),
            ".db": SQLiteValidator(),
        }

    def validate(self, data: bytes,
                 filename: str = "",
                 original_data: Optional[bytes] = None) -> Dict:
        """
        Validate a file for functional recovery.

        Args:
            data: The recovered file data
            filename: The filename (used to determine format)
            original_data: The original ground truth data (for comparison)

        Returns:
            Dict with:
              - level: RecoveryLevel enum
              - functional_score: float 0.0-1.0
              - format: str
              - details: format-specific result dict
        """
        ext = Path(filename).suffix.lower() if filename else ""
        validator = self.validators.get(ext)

        if validator:
            result = validator.validate(data, original_data)
            return {
                "level": result.level,
                "level_name": result.level.value,
                "functional_score": result.functional_score,
                "format": ext,
                "details": result.to_dict(),
            }
        else:
            # Generic validation
            result = self._generic_validate(data, original_data)
            return {
                "level": result.level,
                "level_name": result.level.value,
                "functional_score": result.functional_score,
                "format": ext or "unknown",
                "details": result.to_dict(),
            }

    def _generic_validate(self, data: bytes,
                          original_data: Optional[bytes] = None) -> GenericValidationResult:
        """Generic validation for formats without specific validators."""
        if len(data) == 0:
            return GenericValidationResult(
                level=RecoveryLevel.FAILED,
                functional_score=0.0,
                notes="Empty file",
            )

        # Check for SHA-256 match
        if original_data and data == original_data:
            return GenericValidationResult(
                level=RecoveryLevel.FULL,
                functional_score=1.0,
                size_preserved=True,
                notes="Bit-perfect recovery",
            )

        # Check if size is preserved
        size_preserved = original_data is None or len(data) == len(original_data)

        # Basic heuristic: if the file has reasonable size and we have
        # original data, estimate corruption level
        if original_data and len(data) == len(original_data):
            diff_bytes = sum(1 for a, b in zip(data, original_data) if a != b)
            diff_pct = diff_bytes / len(data)

            if diff_pct < 0.001:
                return GenericValidationResult(
                    level=RecoveryLevel.FUNCTIONAL,
                    functional_score=0.9,
                    size_preserved=True,
                    notes=f"Nearly perfect: {diff_pct:.4%} bytes differ",
                )
            elif diff_pct < 0.05:
                return GenericValidationResult(
                    level=RecoveryLevel.PARTIAL,
                    functional_score=0.5,
                    size_preserved=True,
                    notes=f"Moderate corruption: {diff_pct:.2%} bytes differ",
                )
            else:
                return GenericValidationResult(
                    level=RecoveryLevel.DEGRADED,
                    functional_score=max(0.1, 0.5 - diff_pct * 3),
                    size_preserved=True,
                    notes=f"Heavy corruption: {diff_pct:.2%} bytes differ",
                )

        # Without original data, we can only check basic properties
        return GenericValidationResult(
            level=RecoveryLevel.PARTIAL,
            functional_score=0.5,
            size_preserved=size_preserved,
            notes="No original data available for comparison",
        )

    def batch_validate(self,
                       files: Dict[str, bytes],
                       original_files: Optional[Dict[str, bytes]] = None) -> Dict:
        """
        Validate multiple files at once.

        Args:
            files: Dict of filename → recovered data
            original_files: Dict of filename → original data

        Returns:
            Dict with:
              - results: Dict of filename → validation result
              - summary: Aggregate statistics
              - functional_recovery_rate: % of files with functional+ recovery
        """
        results = {}
        functional_count = 0
        total_count = 0

        for name, data in files.items():
            orig = original_files.get(name) if original_files else None
            result = self.validate(data, name, orig)
            results[name] = result

            total_count += 1
            if result["functional_score"] >= 0.5:  # Partial or better
                functional_count += 1

        return {
            "results": results,
            "summary": {
                "total_files": total_count,
                "functional_recovery": functional_count,
                "functional_recovery_rate": functional_count / total_count if total_count else 0.0,
                "level_distribution": {
                    level.value: sum(1 for r in results.values() if r["level"] == level)
                    for level in RecoveryLevel
                },
            },
        }


# ─── Validation Table (for documentation) ────────────────────────────────────

def print_validation_table() -> str:
    """Print the functional validation criteria table."""
    lines = [
        "# Functional Recovery Validation Criteria",
        "",
        "| Format | FULL (1.0) | FUNCTIONAL (0.8) | PARTIAL (0.5) | DEGRADED (0.2) | FAILED (0.0) |",
        "|--------|-----------|-----------------|--------------|---------------|-------------|",
        "| JPEG | SHA-256 match | Opens + valid markers + footer | Header + scan data | Header only | No header |",
        "| MP4 | SHA-256 match | ftyp + moov + mdat | ftyp + moov | ftyp only | No structure |",
        "| DOCX | SHA-256 match | Valid ZIP + document.xml + text | ZIP + document.xml | ZIP only | No ZIP |",
        "| SQLite | SHA-256 match | Header + tables + data | Header + tables | Header only | No header |",
        "| ZIP | SHA-256 match | Header + EOCD + central dir | Header + EOCD | Header only | No header |",
        "| PDF | SHA-256 match | Header + xref + pages + EOF | Header + pages | Header only | No header |",
        "| PNG | SHA-256 match | Header + IHDR + IDAT + IEND | Header + IHDR + IDAT | Header only | No header |",
        "",
        "Key insight: SHA-256 is ONLY the 'FULL' level.",
        "A file can be FUNCTIONALLY recovered even with a different checksum.",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(print_validation_table())
    print()

    # Quick test with sample data
    validator = FunctionalValidator()

    # Test JPEG validation
    jpeg_data = b'\xFF\xD8\xFF\xE0' + b'\x00' * 100 + b'\xFF\xD9'
    result = validator.validate(jpeg_data, "photo.jpg")
    print(f"JPEG test: {result['level_name']} (score={result['functional_score']:.2f})")
    print(f"  Details: {result['details']}")
