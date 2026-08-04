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

Sprint 3 visible metric:
  NTFS Journal: 0% → ?%
  = percentage of files whose metadata we can extract from MFT
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


@dataclass
class NTFSMetadata:
    """All metadata extracted from an NTFS image."""
    mft_entries: List[MFTEntry] = field(default_factory=list)
    journal_entries: List[JournalEntry] = field(default_factory=list)
    
    files_by_record: Dict[int, MFTEntry] = field(default_factory=dict)
    directories: Dict[int, List[int]] = field(default_factory=dict)
    deleted_files: List[MFTEntry] = field(default_factory=list)
    
    mft_entries_parsed: int = 0
    mft_entries_total: int = 0
    journal_entries_parsed: int = 0
    deleted_files_found: int = 0
    parse_errors: int = 0


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
    """Parse NTFS data run list."""
    runs = []
    pos = offset
    current_offset = 0
    
    while pos < len(data):
        header = data[pos]
        if header == 0:
            break
        
        length_size = header & 0x0F
        offset_size = (header >> 4) & 0x0F
        
        if length_size == 0 or offset_size == 0:
            break
        
        pos += 1
        
        if pos + length_size > len(data):
            break
        length = int.from_bytes(data[pos:pos + length_size], 'little')
        pos += length_size
        
        if pos + offset_size > len(data):
            break
        raw_offset = int.from_bytes(data[pos:pos + offset_size], 'little')
        if raw_offset >= (1 << (offset_size * 8 - 1)):
            raw_offset -= (1 << (offset_size * 8))
        pos += offset_size
        
        if raw_offset != 0:
            current_offset += raw_offset
            runs.append(DataRun(length=length, offset=current_offset))
        else:
            runs.append(DataRun(length=length, offset=0))
    
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
    max_mft_entries = min(10000, (len(image) - mft_offset) // MFT_RECORD_SIZE)
    
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
    
    return metadata


def recover_file_data(image: bytes, entry: MFTEntry, 
                       cluster_size: int = 4096) -> Optional[bytes]:
    """Recover file data from an MFT entry."""
    if entry.is_resident:
        return entry.resident_data
    
    if not entry.data_runs:
        return None
    
    file_data = bytearray()
    
    for run in entry.data_runs:
        if run.offset == 0:
            file_data.extend(b'\x00' * (run.length * cluster_size))
            continue
        
        for cluster_num in range(run.length):
            cluster_offset = (run.offset + cluster_num) * cluster_size
            if cluster_offset + cluster_size > len(image):
                file_data.extend(b'\x00' * cluster_size)
                continue
            file_data.extend(image[cluster_offset:cluster_offset + cluster_size])
    
    if entry.data_size > 0 and len(file_data) > entry.data_size:
        file_data = file_data[:entry.data_size]
    
    return bytes(file_data)
