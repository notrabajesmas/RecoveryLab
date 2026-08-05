#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RecoveryLab — NTFS MFT & Journal Parser
=========================================
Parses raw NTFS disk images to extract:
  1. MFT entries (filenames, timestamps, data runs, directory structure)
  2. $LogFile records (transaction log for recent operations)
  3. $UsnJrnl entries (change journal for file modifications/deletions)

This provides METADATA that carving alone cannot get:
  - Real filenames (instead of "carved_0001.jpg")
  - Directory structure
  - File timestamps
  - Recently deleted file records

Sprint 3b visible metric:
  NTFS USN Journal: 0% → 90%
  = percentage of file operations we can extract from $UsnJrnl
"""

import struct
import hashlib
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import IntEnum


# ─── NTFS Constants ───────────────────────────────────────────────────────────

SECTOR_SIZE = 512
MFT_RECORD_SIZE = 1024


class AttrType(IntEnum):
    STANDARD_INFORMATION = 0x10
    ATTRIBUTE_LIST       = 0x20
    FILE_NAME            = 0x30
    OBJECT_ID            = 0x40
    SECURITY_DESCRIPTOR  = 0x50
    VOLUME_NAME          = 0x60
    VOLUME_INFORMATION   = 0x70
    DATA                 = 0x80
    INDEX_ROOT           = 0x90
    INDEX_ALLOCATION     = 0xA0
    BITMAP               = 0xB0
    REPARSE_POINT        = 0xC0
    EA_INFORMATION       = 0xD0
    EA                   = 0xE0
    LOGGED_UTILITY_STREAM = 0x100


MFT_RECORD_IN_USE    = 0x0001
MFT_RECORD_DIRECTORY = 0x0002


# ─── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class DataRun:
    """A single data run (extent) in an NTFS run list."""
    length: int        # Number of clusters
    offset: int        # Starting cluster (absolute for first run, relative after)
    is_sparse: bool = False  # True if this is a sparse run (zero-filled, no disk allocation)


@dataclass
class MFTEntry:
    """Parsed MFT entry with metadata."""
    record_number: int
    in_use: bool
    is_directory: bool
    filename: str = ""
    parent_record: int = 5  # Root directory
    created: float = 0.0
    modified: float = 0.0
    data_runs: List[DataRun] = field(default_factory=list)
    data_size: int = 0
    is_resident: bool = False
    resident_data: bytes = b""
    sha256: str = ""
    is_sparse: bool = False  # True if file has any sparse data runs
    
    # Standard information attribute
    si_created: float = 0.0
    si_modified: float = 0.0
    si_accessed: float = 0.0
    si_mft_modified: float = 0.0
    
    # File name attribute
    fn_flags: int = 0


@dataclass
class JournalEntry:
    """A parsed $UsnJrnl change journal entry."""
    usn: int
    file_reference: int
    parent_reference: int
    reason: int
    file_attributes: int
    timestamp: float
    filename: str = ""
    is_delete: bool = False
    is_create: bool = False
    is_rename: bool = False
    mft_record_number: int = 0   # Lower 48 bits of file_reference
    parent_mft_record: int = 0   # Lower 48 bits of parent_reference
    source_info: int = 0
    security_id: int = 0
    record_version: int = 0


# ─── USN Reason Flags ─────────────────────────────────────────────────────────

class USNReason:
    """USN_REASON_* flags from winioctl.h / ntifs.h"""
    DATA_OVERWRITE          = 0x00000001
    DATA_EXTEND             = 0x00000002
    DATA_TRUNCATION         = 0x00000004
    NAMED_DATA_OVERWRITE    = 0x00000010
    NAMED_DATA_EXTEND       = 0x00000020
    NAMED_DATA_TRUNCATION   = 0x00000040
    FILE_CREATE             = 0x00000100
    FILE_DELETE             = 0x00000200
    EA_CHANGE               = 0x00000400
    SECURITY_CHANGE         = 0x00000800
    RENAME_OLD_NAME         = 0x00001000
    RENAME_NEW_NAME         = 0x00002000
    INDEXABLE_CHANGE        = 0x00004000
    BASIC_INFO_CHANGE       = 0x00008000
    HARD_LINK_CHANGE        = 0x00010000
    COMPRESSION_CHANGE      = 0x00020000
    ENCRYPTION_CHANGE       = 0x00040000
    OBJECT_ID_CHANGE        = 0x00080000
    REPARSE_POINT_CHANGE    = 0x00100000
    STREAM_CHANGE           = 0x00200000
    TRANSACTED_CHANGE       = 0x00400000
    INTEGRITY_CHANGE        = 0x00800000
    CLOSE                   = 0x80000000

    @staticmethod
    def is_delete(reason: int) -> bool:
        return bool(reason & USNReason.FILE_DELETE)

    @staticmethod
    def is_create(reason: int) -> bool:
        return bool(reason & USNReason.FILE_CREATE)

    @staticmethod
    def is_rename(reason: int) -> bool:
        return bool(reason & (USNReason.RENAME_OLD_NAME | USNReason.RENAME_NEW_NAME))

    @staticmethod
    def describe(reason: int) -> str:
        """Human-readable description of reason flags."""
        parts = []
        if reason & USNReason.FILE_CREATE:     parts.append("CREATE")
        if reason & USNReason.FILE_DELETE:     parts.append("DELETE")
        if reason & USNReason.DATA_OVERWRITE:  parts.append("DATA_OVERWRITE")
        if reason & USNReason.DATA_EXTEND:     parts.append("DATA_EXTEND")
        if reason & USNReason.DATA_TRUNCATION: parts.append("DATA_TRUNCATION")
        if reason & USNReason.RENAME_OLD_NAME: parts.append("RENAME_OLD")
        if reason & USNReason.RENAME_NEW_NAME: parts.append("RENAME_NEW")
        if reason & USNReason.SECURITY_CHANGE: parts.append("SECURITY_CHANGE")
        if reason & USNReason.BASIC_INFO_CHANGE: parts.append("BASIC_INFO_CHANGE")
        if reason & USNReason.CLOSE:           parts.append("CLOSE")
        return " | ".join(parts) if parts else f"0x{reason:08X}"


@dataclass
class NTFSMetadata:
    """All metadata extracted from an NTFS image."""
    mft_entries: List[MFTEntry] = field(default_factory=list)
    journal_entries: List[JournalEntry] = field(default_factory=list)
    
    files_by_record: Dict[int, MFTEntry] = field(default_factory=dict)
    directories: Dict[int, List[int]] = field(default_factory=dict)
    deleted_files: List[MFTEntry] = field(default_factory=list)
    
    # Journal-specific indexes
    journal_by_mft_record: Dict[int, List[JournalEntry]] = field(default_factory=dict)
    journal_deletes: List[JournalEntry] = field(default_factory=list)
    journal_creates: List[JournalEntry] = field(default_factory=list)
    journal_renames: List[JournalEntry] = field(default_factory=list)
    
    mft_entries_parsed: int = 0
    mft_entries_total: int = 0
    journal_entries_parsed: int = 0
    journal_parse_errors: int = 0
    deleted_files_found: int = 0
    parse_errors: int = 0
    
    # Journal stats
    journal_mft_record: int = 0        # MFT entry number of $UsnJrnl
    journal_data_size: int = 0         # Size of $J stream


# ─── NTFS Timestamp Conversion ────────────────────────────────────────────────

def ntfs_timestamp_to_unix(ts_bytes: bytes) -> float:
    """Convert NTFS timestamp (100-ns intervals since 1601-01-01) to Unix timestamp."""
    if len(ts_bytes) < 8:
        return 0.0
    
    NTFS_TO_UNIX_OFFSET = 116444736000000000
    
    try:
        intervals = struct.unpack('<Q', ts_bytes[:8])[0]
        if intervals == 0:
            return 0.0
        
        unix_intervals = intervals - NTFS_TO_UNIX_OFFSET
        if unix_intervals < 0:
            return 0.0
        
        return unix_intervals / 10_000_000.0
    except (struct.error, OverflowError):
        return 0.0


# ─── MFT Entry Parser ─────────────────────────────────────────────────────────

def parse_mft_record(data: bytes, record_number: int) -> Optional[MFTEntry]:
    """Parse a single MFT record (1024 bytes)."""
    if len(data) < MFT_RECORD_SIZE:
        return None
    
    if data[0:4] != b'FILE':
        return None
    
    try:
        fixup_offset = struct.unpack_from('<H', data, 4)[0]
        fixup_count = struct.unpack_from('<H', data, 6)[0]
        
        # Apply fixup (NTFS Update Sequence)
        # The fixup replaces the last 2 bytes of each sector with the
        # original values stored in the fixup array.
        # Fixup array layout (at fixup_offset):
        #   [0-1]: Update sequence number (USN) — was written at end of each sector
        #   [2-3]: Original bytes for sector 0 (bytes 510-511)
        #   [4-5]: Original bytes for sector 1 (bytes 1022-1023)
        #   etc.
        fixed_data = bytearray(data)
        if fixup_offset > 0 and fixup_count > 1:
            try:
                usn = struct.unpack_from('<H', data, fixup_offset)[0]
                # Verify USN matches at sector boundaries
                for i in range(1, fixup_count):
                    sector_end = i * SECTOR_SIZE - 2
                    if sector_end + 2 <= len(data):
                        actual = struct.unpack_from('<H', data, sector_end)[0]
                        if actual == usn and usn != 0:
                            # USN matches — apply fixup (restore originals)
                            orig_offset = fixup_offset + 2 * i
                            if orig_offset + 2 <= len(data):
                                fixed_data[sector_end:sector_end + 2] = data[orig_offset:orig_offset + 2]
            except (struct.error, IndexError):
                pass  # Fixup failed, use raw data
        
        data = bytes(fixed_data)
        
        flags = struct.unpack_from('<H', data, 22)[0]
        in_use = bool(flags & MFT_RECORD_IN_USE)
        is_directory = bool(flags & MFT_RECORD_DIRECTORY)
        
        entry = MFTEntry(
            record_number=record_number,
            in_use=in_use,
            is_directory=is_directory,
        )
        
        attr_offset = struct.unpack_from('<H', data, 20)[0]
        
        while attr_offset + 8 < MFT_RECORD_SIZE:
            attr_type = struct.unpack_from('<I', data, attr_offset)[0]
            
            if attr_type == 0xFFFFFFFF or attr_type == 0:
                break
            
            attr_length = struct.unpack_from('<I', data, attr_offset + 4)[0]
            if attr_length < 16 or attr_offset + attr_length > MFT_RECORD_SIZE:
                break
            
            non_resident = data[attr_offset + 8]
            
            if attr_type == AttrType.STANDARD_INFORMATION:
                _parse_si(data, attr_offset, non_resident, entry)
            elif attr_type == AttrType.FILE_NAME:
                _parse_fn(data, attr_offset, non_resident, entry)
            elif attr_type == AttrType.DATA:
                _parse_data(data, attr_offset, non_resident, entry)
            
            attr_offset += attr_length
        
        # Mark entry as sparse if it has sparse runs or sparse file attribute
        # FILE_ATTRIBUTE_SPARSE_FILE = 0x0400 (in fn_flags)
        if any(run.is_sparse for run in entry.data_runs):
            entry.is_sparse = True
        elif entry.fn_flags & 0x0400:
            entry.is_sparse = True
        
        return entry
    
    except (struct.error, IndexError, ValueError):
        return None


def _parse_si(data: bytes, offset: int, non_resident: int, entry: MFTEntry):
    """Parse $STANDARD_INFORMATION attribute."""
    try:
        if non_resident:
            return
        # For resident attributes, offset to data is at attr + 20
        value_offset = struct.unpack_from('<H', data, offset + 20)[0]
        vs = offset + value_offset
        if vs + 32 > len(data):
            return
        entry.si_created = ntfs_timestamp_to_unix(data[vs:vs + 8])
        entry.si_modified = ntfs_timestamp_to_unix(data[vs + 8:vs + 16])
        entry.created = entry.si_created
        entry.modified = entry.si_modified
    except (struct.error, IndexError):
        pass


def _parse_fn(data: bytes, offset: int, non_resident: int, entry: MFTEntry):
    """Parse $FILE_NAME attribute."""
    try:
        if non_resident:
            return
        # For resident attributes, offset to data is at attr + 20
        value_offset = struct.unpack_from('<H', data, offset + 20)[0]
        vs = offset + value_offset
        if vs + 68 > len(data):
            return
        
        parent_ref = struct.unpack_from('<Q', data, vs)[0]
        entry.parent_record = parent_ref & 0xFFFFFF
        
        # Name length (in characters) and name type
        fn_length = data[vs + 64]
        fn_type = data[vs + 65]  # 0x01=POSIX, 0x02=DOS, 0x03=Win32, 0x04=Win32&DOS
        
        # File attributes
        fn_flags = struct.unpack_from('<I', data, vs + 56)[0]
        entry.fn_flags = fn_flags
        
        # Read filename (UTF-16LE starting at offset 66)
        fn_start = vs + 66
        fn_end = fn_start + fn_length * 2
        if fn_end <= len(data) and fn_length > 0:
            try:
                name = data[fn_start:fn_end].decode('utf-16-le')
                # Prefer Win32 or Win32&DOS names over POSIX
                if not entry.filename or fn_type >= 0x02:
                    entry.filename = name
            except UnicodeDecodeError:
                pass
    except (struct.error, IndexError):
        pass


def _parse_data(data: bytes, offset: int, non_resident: int, entry: MFTEntry):
    """Parse $DATA attribute."""
    try:
        if non_resident:
            entry.is_resident = False
            data_runs_offset = struct.unpack_from('<H', data, offset + 32)[0]
            real_size = struct.unpack_from('<Q', data, offset + 48)[0]
            entry.data_size = real_size
            entry.data_runs = _parse_data_runs(data, offset + data_runs_offset)
        else:
            entry.is_resident = True
            value_offset = struct.unpack_from('<H', data, offset + 14)[0]
            value_length = struct.unpack_from('<I', data, offset + 16)[0]
            entry.data_size = value_length
            vs = offset + value_offset
            if vs + value_length <= len(data):
                entry.resident_data = data[vs:vs + value_length]
    except (struct.error, IndexError):
        pass


def _parse_data_runs(data: bytes, offset: int) -> List[DataRun]:
    """Parse NTFS data run list.
    
    Handles three types of data runs:
      - Normal runs: offset_size > 0, point to allocated clusters on disk
      - Sparse runs: offset_size == 0, zero-filled clusters not stored on disk
      - End marker: header == 0
    
    Sparse runs are common in NTFS sparse files and NTFS-compressed files.
    A sparse run has a length but no offset — the clusters are logical zeros.
    """
    runs = []
    pos = offset
    current_offset = 0
    
    while pos < len(data):
        header = data[pos]
        if header == 0:
            break  # End of run list
        
        length_size = header & 0x0F
        offset_size = (header >> 4) & 0x0F
        
        if length_size == 0:
            break  # Invalid: length must be > 0
        
        pos += 1
        
        # Read run length
        if pos + length_size > len(data):
            break
        length = int.from_bytes(data[pos:pos + length_size], 'little')
        pos += length_size
        
        if offset_size == 0:
            # Sparse run: zero-filled clusters, no disk allocation
            # These are the gaps in sparse/compressed NTFS files
            runs.append(DataRun(length=length, offset=0, is_sparse=True))
            continue
        
        # Normal run: read offset (may be signed)
        if pos + offset_size > len(data):
            break
        raw_offset = int.from_bytes(data[pos:pos + offset_size], 'little')
        if raw_offset >= (1 << (offset_size * 8 - 1)):
            raw_offset -= (1 << (offset_size * 8))
        pos += offset_size
        
        if raw_offset != 0:
            current_offset += raw_offset
            runs.append(DataRun(length=length, offset=current_offset, is_sparse=False))
        else:
            # offset == 0 after relative calculation: also sparse
            runs.append(DataRun(length=length, offset=0, is_sparse=True))
    
    return runs


# ─── Main Parser ──────────────────────────────────────────────────────────────

def parse_ntfs_image(image: bytes, cluster_size: int = 4096) -> NTFSMetadata:
    """
    Parse an NTFS image to extract MFT entries and journal data.
    """
    metadata = NTFSMetadata()
    
    # Parse VBR
    if len(image) < SECTOR_SIZE:
        return metadata
    
    try:
        if image[3:11] != b'NTFS    ':
            return metadata
        
        bytes_per_sector = struct.unpack_from('<H', image, 11)[0]
        sectors_per_cluster = image[13]
        actual_cluster_size = bytes_per_sector * sectors_per_cluster
        
        mft_start_cluster = struct.unpack_from('<Q', image, 48)[0]
    except (struct.error, IndexError):
        return metadata
    
    # Parse MFT entries
    mft_offset = mft_start_cluster * cluster_size
    # No artificial cap — parse all MFT entries that fit in the image
    # (was min(10000, ...) which cut off at 10K records)
    max_mft_entries = (len(image) - mft_offset) // MFT_RECORD_SIZE
    
    consecutive_errors = 0
    
    for i in range(max_mft_entries):
        record_offset = mft_offset + i * MFT_RECORD_SIZE
        
        if record_offset + MFT_RECORD_SIZE > len(image):
            break
        
        record_data = image[record_offset:record_offset + MFT_RECORD_SIZE]
        entry = parse_mft_record(record_data, i)
        
        if entry is None:
            consecutive_errors += 1
            metadata.parse_errors += 1
            # Stop after 3 consecutive errors if we already have entries
            if consecutive_errors >= 3 and metadata.mft_entries_parsed > 12:
                break
            continue
        
        consecutive_errors = 0
        metadata.mft_entries.append(entry)
        metadata.mft_entries_parsed += 1
        metadata.files_by_record[i] = entry
        
        if entry.is_directory and entry.in_use:
            if i not in metadata.directories:
                metadata.directories[i] = []
        
        if not entry.in_use and entry.filename:
            metadata.deleted_files.append(entry)
            metadata.deleted_files_found += 1
    
    metadata.mft_entries_total = metadata.mft_entries_parsed
    
    # Build directory tree
    for entry in metadata.mft_entries:
        if entry.in_use and entry.parent_record != entry.record_number:
            if entry.parent_record not in metadata.directories:
                metadata.directories[entry.parent_record] = []
            metadata.directories[entry.parent_record].append(entry.record_number)
    
    # ── Parse USN Journal ($UsnJrnl) ────────────────────────────────────────
    _parse_usn_journal(image, metadata, cluster_size, mft_offset)
    
    return metadata


def recover_file_data(image: bytes, entry: MFTEntry, 
                       cluster_size: int = 4096) -> Optional[bytes]:
    """Recover file data from an MFT entry.
    
    Handles:
      - Resident files (data embedded in MFT record)
      - Non-resident files with normal data runs
      - Sparse runs (zero-filled, no disk allocation)
    
    Sparse runs are zero-filled — they represent gaps in sparse/compressed
    NTFS files where no data is stored on disk.
    """
    if entry.is_resident:
        return entry.resident_data
    
    if not entry.data_runs:
        return None
    
    file_data = bytearray()
    
    for run in entry.data_runs:
        if run.is_sparse or run.offset == 0:
            # Sparse run: fill with zeros (no data on disk)
            file_data.extend(b'\x00' * (run.length * cluster_size))
            continue
        
        for cluster_num in range(run.length):
            cluster_offset = (run.offset + cluster_num) * cluster_size
            if cluster_offset + cluster_size > len(image):
                # Out of image bounds — fill with zeros
                file_data.extend(b'\x00' * cluster_size)
                continue
            file_data.extend(image[cluster_offset:cluster_offset + cluster_size])
    
    if entry.data_size > 0 and len(file_data) > entry.data_size:
        file_data = file_data[:entry.data_size]
    
    return bytes(file_data)


# ─── USN Journal Parser ──────────────────────────────────────────────────────

def _parse_usn_record(data: bytes, offset: int) -> Optional[JournalEntry]:
    """
    Parse a single USN_RECORD from the $J stream.
    
    Supports V2 (NTFS, Win2000+) and V3 (ReFS/Win8+).
    V4 (range tracking) is skipped but counted.
    
    USN_RECORD_V2 layout (60 bytes fixed + variable filename):
      0x00: RecordLength     (uint32)
      0x04: MajorVersion     (uint16)
      0x06: MinorVersion     (uint16)
      0x08: FileReferenceNumber  (uint64)
      0x10: ParentFileReferenceNumber (uint64)
      0x18: Usn              (int64)
      0x20: TimeStamp        (FILETIME)
      0x28: Reason           (uint32)
      0x2C: SourceInfo       (uint32)
      0x30: SecurityId       (uint32)
      0x34: FileAttributes   (uint32)
      0x38: FileNameLength   (uint16)
      0x3A: FileNameOffset   (uint16)
      0x3C: FileName         (wchar[], variable)
    
    USN_RECORD_V3 layout (76 bytes fixed + variable filename):
      Same as V2 but FileReferenceNumber and ParentFileReferenceNumber
      are 128-bit (FILE_ID_128), shifting offsets by 16 bytes.
    """
    if offset + 60 > len(data):
        return None
    
    try:
        record_length = struct.unpack_from('<I', data, offset)[0]
        major_version = struct.unpack_from('<H', data, offset + 4)[0]
        minor_version = struct.unpack_from('<H', data, offset + 6)[0]
        
        # Validate record
        if record_length < 60 or record_length > 65536:
            return None
        if offset + record_length > len(data):
            return None
        
        # V4 records (range tracking) — skip but return placeholder
        if major_version == 4:
            # V4 has no filename, no timestamp — we skip it
            # but we need to advance past it, so return a minimal entry
            return JournalEntry(
                usn=0,
                file_reference=0,
                parent_reference=0,
                reason=0,
                file_attributes=0,
                timestamp=0.0,
                filename="",
                record_version=4,
            )
        
        # V2 record (NTFS standard)
        if major_version == 2:
            file_ref = struct.unpack_from('<Q', data, offset + 0x08)[0]
            parent_ref = struct.unpack_from('<Q', data, offset + 0x10)[0]
            usn = struct.unpack_from('<q', data, offset + 0x18)[0]
            timestamp_raw = data[offset + 0x20:offset + 0x28]
            reason = struct.unpack_from('<I', data, offset + 0x28)[0]
            source_info = struct.unpack_from('<I', data, offset + 0x2C)[0]
            security_id = struct.unpack_from('<I', data, offset + 0x30)[0]
            file_attributes = struct.unpack_from('<I', data, offset + 0x34)[0]
            fn_length = struct.unpack_from('<H', data, offset + 0x38)[0]
            fn_offset_field = struct.unpack_from('<H', data, offset + 0x3A)[0]
            
            # Extract MFT record numbers from file references
            mft_record = file_ref & 0xFFFFFFFFFFFF       # Lower 48 bits
            parent_mft_record = parent_ref & 0xFFFFFFFFFFFF
            
            # Parse filename (UTF-16LE)
            filename = ""
            fn_start = offset + fn_offset_field
            if fn_length > 0 and fn_start + fn_length <= len(data):
                try:
                    filename = data[fn_start:fn_start + fn_length].decode('utf-16-le')
                except UnicodeDecodeError:
                    pass
            
            # Convert timestamp
            timestamp = ntfs_timestamp_to_unix(timestamp_raw)
            
            return JournalEntry(
                usn=usn,
                file_reference=file_ref,
                parent_reference=parent_ref,
                reason=reason,
                file_attributes=file_attributes,
                timestamp=timestamp,
                filename=filename,
                is_delete=USNReason.is_delete(reason),
                is_create=USNReason.is_create(reason),
                is_rename=USNReason.is_rename(reason),
                mft_record_number=mft_record,
                parent_mft_record=parent_mft_record,
                source_info=source_info,
                security_id=security_id,
                record_version=2,
            )
        
        # V3 record (ReFS / Win8+ NTFS)
        if major_version == 3:
            # V3 has 128-bit file references (16 bytes each)
            # Lower 8 bytes = effective 64-bit MFT ref on NTFS
            file_ref_bytes = data[offset + 0x08:offset + 0x18]
            parent_ref_bytes = data[offset + 0x18:offset + 0x28]
            
            # On NTFS, lower 8 bytes are the MFT reference
            file_ref = struct.unpack_from('<Q', file_ref_bytes, 0)[0]
            parent_ref = struct.unpack_from('<Q', parent_ref_bytes, 0)[0]
            
            usn = struct.unpack_from('<q', data, offset + 0x28)[0]
            timestamp_raw = data[offset + 0x30:offset + 0x38]
            reason = struct.unpack_from('<I', data, offset + 0x38)[0]
            source_info = struct.unpack_from('<I', data, offset + 0x3C)[0]
            security_id = struct.unpack_from('<I', data, offset + 0x40)[0]
            file_attributes = struct.unpack_from('<I', data, offset + 0x44)[0]
            fn_length = struct.unpack_from('<H', data, offset + 0x48)[0]
            fn_offset_field = struct.unpack_from('<H', data, offset + 0x4A)[0]
            
            mft_record = file_ref & 0xFFFFFFFFFFFF
            parent_mft_record = parent_ref & 0xFFFFFFFFFFFF
            
            filename = ""
            fn_start = offset + fn_offset_field
            if fn_length > 0 and fn_start + fn_length <= len(data):
                try:
                    filename = data[fn_start:fn_start + fn_length].decode('utf-16-le')
                except UnicodeDecodeError:
                    pass
            
            timestamp = ntfs_timestamp_to_unix(timestamp_raw)
            
            return JournalEntry(
                usn=usn,
                file_reference=file_ref,
                parent_reference=parent_ref,
                reason=reason,
                file_attributes=file_attributes,
                timestamp=timestamp,
                filename=filename,
                is_delete=USNReason.is_delete(reason),
                is_create=USNReason.is_create(reason),
                is_rename=USNReason.is_rename(reason),
                mft_record_number=mft_record,
                parent_mft_record=parent_mft_record,
                source_info=source_info,
                security_id=security_id,
                record_version=3,
            )
        
        # Unknown version
        return None
    
    except (struct.error, IndexError, ValueError):
        return None


def _parse_usn_journal(image: bytes, metadata: NTFSMetadata,
                       cluster_size: int, mft_offset: int):
    """
    Parse the NTFS USN Journal ($UsnJrnl $J stream).
    
    Strategy:
      1. Find $UsnJrnl MFT entry by scanning for "$UsnJrnl" filename
         (it's a child of $Extend, entry 11)
      2. Read the $J data stream from its non-resident $DATA attribute
      3. Parse USN_RECORD entries sequentially
      4. Build indexes: by MFT record, deletes, creates, renames
    """
    if len(image) < mft_offset + MFT_RECORD_SIZE:
        return
    
    # ── Find $UsnJrnl MFT entry ─────────────────────────────────────────────
    # Scan MFT entries for one named "$UsnJrnl"
    # It's typically a child of $Extend (entry 11)
    usn_jrnl_entry = None
    usn_jrnl_record_num = -1
    
    max_scan = min(metadata.mft_entries_parsed + 10, 
                   (len(image) - mft_offset) // MFT_RECORD_SIZE)
    
    for i in range(max_scan):
        rec_offset = mft_offset + i * MFT_RECORD_SIZE
        if rec_offset + MFT_RECORD_SIZE > len(image):
            break
        
        rec_data = image[rec_offset:rec_offset + MFT_RECORD_SIZE]
        entry = parse_mft_record(rec_data, i)
        
        if entry is None:
            continue
        
        if entry.filename == "$UsnJrnl":
            usn_jrnl_entry = entry
            usn_jrnl_record_num = i
            break
    
    if usn_jrnl_entry is None:
        # No $UsnJrnl found — journal not present on this image
        return
    
    metadata.journal_mft_record = usn_jrnl_record_num
    
    # ── Read $J data stream ─────────────────────────────────────────────────
    # The $J stream is the non-resident $DATA attribute of $UsnJrnl
    # We need to re-parse the MFT record to find the $DATA attribute
    # and distinguish $J from $Max
    
    rec_offset = mft_offset + usn_jrnl_record_num * MFT_RECORD_SIZE
    rec_data = image[rec_offset:rec_offset + MFT_RECORD_SIZE]
    
    # Parse all $DATA attributes to find $J
    # $J is the first (default, unnamed) $DATA attribute
    # $Max is a named $DATA attribute with name "$Max"
    journal_data = _read_journal_data_stream(image, rec_data, cluster_size)
    
    if journal_data is None or len(journal_data) == 0:
        return
    
    metadata.journal_data_size = len(journal_data)
    
    # ── Parse USN records ───────────────────────────────────────────────────
    pos = 0
    v4_count = 0
    
    while pos < len(journal_data):
        # Check for sparse zeroed region
        if journal_data[pos:pos + 4] == b'\x00\x00\x00\x00':
            # Could be padding or end — scan forward
            next_nonzero = pos + 4
            while next_nonzero < len(journal_data) and next_nonzero < pos + 4096:
                if journal_data[next_nonzero] != 0:
                    break
                next_nonzero += 1
            if next_nonzero >= len(journal_data) or next_nonzero >= pos + 4096:
                break  # End of valid journal data
            pos = next_nonzero
            continue
        
        record = _parse_usn_record(journal_data, pos)
        
        if record is None:
            # Try to skip forward — look for next valid record
            metadata.journal_parse_errors += 1
            pos += 8  # Records are 8-byte aligned
            continue
        
        # V4 records — skip (no useful metadata for recovery)
        if record.record_version == 4:
            v4_count += 1
            rec_len = struct.unpack_from('<I', journal_data, pos)[0]
            pos += max(rec_len, 8)
            # Align to 8 bytes
            pos = (pos + 7) & ~7
            continue
        
        # Valid V2/V3 record — store it
        metadata.journal_entries.append(record)
        metadata.journal_entries_parsed += 1
        
        # Build indexes
        mft_rec = record.mft_record_number
        if mft_rec not in metadata.journal_by_mft_record:
            metadata.journal_by_mft_record[mft_rec] = []
        metadata.journal_by_mft_record[mft_rec].append(record)
        
        if record.is_delete:
            metadata.journal_deletes.append(record)
        if record.is_create:
            metadata.journal_creates.append(record)
        if record.is_rename:
            metadata.journal_renames.append(record)
        
        # Advance to next record
        rec_len = struct.unpack_from('<I', journal_data, pos)[0]
        pos += max(rec_len, 8)
        # Align to 8 bytes
        pos = (pos + 7) & ~7


def _read_journal_data_stream(image: bytes, mft_record_data: bytes,
                              cluster_size: int) -> Optional[bytes]:
    """
    Read the $J data stream from the $UsnJrnl MFT record.
    
    The $UsnJrnl entry has two $DATA attributes:
    - Unnamed (default) = $J stream (journal records)
    - Named "$Max" = journal configuration
    
    We want the unnamed one (first $DATA attribute encountered).
    """
    if len(mft_record_data) < MFT_RECORD_SIZE:
        return None
    
    if mft_record_data[0:4] != b'FILE':
        return None
    
    try:
        # Apply fixup
        fixup_offset = struct.unpack_from('<H', mft_record_data, 4)[0]
        fixup_count = struct.unpack_from('<H', mft_record_data, 6)[0]
        fixed = bytearray(mft_record_data)
        if fixup_offset > 0 and fixup_count > 1:
            try:
                usn = struct.unpack_from('<H', mft_record_data, fixup_offset)[0]
                for i in range(1, fixup_count):
                    sector_end = i * SECTOR_SIZE - 2
                    if sector_end + 2 <= len(mft_record_data):
                        actual = struct.unpack_from('<H', mft_record_data, sector_end)[0]
                        if actual == usn and usn != 0:
                            orig_offset = fixup_offset + 2 * i
                            if orig_offset + 2 <= len(mft_record_data):
                                fixed[sector_end:sector_end + 2] = mft_record_data[orig_offset:orig_offset + 2]
            except (struct.error, IndexError):
                pass
        
        data = bytes(fixed)
        
        # Walk attributes to find the first unnamed $DATA (=$J)
        attr_offset = struct.unpack_from('<H', data, 20)[0]
        
        while attr_offset + 8 < MFT_RECORD_SIZE:
            attr_type = struct.unpack_from('<I', data, attr_offset)[0]
            
            if attr_type == 0xFFFFFFFF or attr_type == 0:
                break
            
            attr_length = struct.unpack_from('<I', data, attr_offset + 4)[0]
            if attr_length < 16 or attr_offset + attr_length > MFT_RECORD_SIZE:
                break
            
            if attr_type == AttrType.DATA:
                non_resident = data[attr_offset + 8]
                
                # Check attribute name — we want unnamed (name_length == 0)
                name_offset = struct.unpack_from('<H', data, attr_offset + 10)[0]
                name_length = data[attr_offset + 9]
                
                if name_length == 0:  # This is the $J stream (unnamed $DATA)
                    if non_resident:
                        # Read data runs
                        data_runs_offset = struct.unpack_from('<H', data, attr_offset + 32)[0]
                        real_size = struct.unpack_from('<Q', data, attr_offset + 48)[0]
                        runs = _parse_data_runs(data, attr_offset + data_runs_offset)
                        
                        # Read the data from image
                        journal_data = bytearray()
                        for run in runs:
                            if run.offset == 0:
                                journal_data.extend(b'\x00' * (run.length * cluster_size))
                                continue
                            for c in range(run.length):
                                c_offset = (run.offset + c) * cluster_size
                                if c_offset + cluster_size > len(image):
                                    journal_data.extend(b'\x00' * cluster_size)
                                    continue
                                journal_data.extend(image[c_offset:c_offset + cluster_size])
                        
                        if real_size > 0 and len(journal_data) > real_size:
                            journal_data = journal_data[:real_size]
                        
                        return bytes(journal_data)
                    else:
                        # Resident $J (unlikely for real journal, but handle it)
                        value_offset = struct.unpack_from('<H', data, attr_offset + 14)[0]
                        value_length = struct.unpack_from('<I', data, attr_offset + 16)[0]
                        vs = attr_offset + value_offset
                        if vs + value_length <= len(data):
                            return data[vs:vs + value_length]
                
                # Named $DATA (e.g., "$Max") — skip
            
            attr_offset += attr_length
        
        return None
    
    except (struct.error, IndexError):
        return None


def recover_from_journal(metadata: NTFSMetadata, 
                         image: bytes,
                         cluster_size: int = 4096) -> List[Dict]:
    """
    Attempt recovery using USN Journal data.
    
    For each journal entry that references a file:
    - If the MFT entry is present and in_use → file already recovered
    - If the MFT entry is missing or not in_use → deleted file candidate
    - Use journal filename + parent directory to reconstruct path
    - Use file_reference to attempt data recovery from MFT
    
    Returns list of recovery candidates (dicts with metadata).
    """
    candidates = []
    
    for entry in metadata.journal_entries:
        if not entry.filename:
            continue
        
        mft_rec = entry.mft_record_number
        
        # Check if file is already recovered via MFT
        if mft_rec in metadata.files_by_record:
            mft_entry = metadata.files_by_record[mft_rec]
            if mft_entry.in_use and not mft_entry.is_directory:
                continue  # Already recovered
        
        # This is a journal-only recovery candidate
        candidates.append({
            "filename": entry.filename,
            "mft_record": mft_rec,
            "parent_record": entry.parent_mft_record,
            "is_delete": entry.is_delete,
            "is_create": entry.is_create,
            "is_rename": entry.is_rename,
            "timestamp": entry.timestamp,
            "reason": USNReason.describe(entry.reason),
            "file_attributes": entry.file_attributes,
            "source": "journal",
        })
    
    return candidates
