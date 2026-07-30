"""
RecoveryLab — NTFS Image Creator
==================================
Creates structurally valid NTFS disk images from scratch in pure Python.

This is NOT a full NTFS driver — it creates minimal but valid NTFS structures
that our recovery motors can parse. The key advantage: we know every byte,
so the manifest.json ground truth is perfect.

NTFS Layout (for a 10MB image, 4096-byte clusters):
  Cluster 0:       VBR (Volume Boot Record)
  Cluster 1:       VBR continuation / bootstrap
  Cluster 2+:      MFT Zone
    Records 0-11:  System files ($MFT, $MFTMirr, $LogFile, etc.)
    Records 12+:   User files
  After MFT:       MFT Mirror data
  After Mirror:    $Bitmap data
  After Bitmap:    $LogFile data
  After LogFile:   $UpCase table data
  After UpCase:    User file data area

References:
  - NTFS Documentation by Richard Russon & Yuval Fledel
  - Windows NTFS documentation (Microsoft)
"""

import struct
import hashlib
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
from enum import IntEnum

# ─── Constants ─────────────────────────────────────────────────────────────────

SECTOR_SIZE = 512
MFT_RECORD_SIZE = 1024
INDEX_RECORD_SIZE = 4096

# MFT Attribute Types
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

# MFT Record Flags
MFT_RECORD_IN_USE    = 0x0001
MFT_RECORD_DIRECTORY = 0x0002

# Attribute Flags
ATTR_COMPRESSED = 0x0001
ATTR_ENCRYPTED  = 0x4000
ATTR_SPARSE     = 0x8000

# NTFS File Name Flags
FILE_NAME_NTFS   = 0x01  # POSIX
FILE_NAME_DOS    = 0x02
FILE_NAME_WIN32  = 0x03
FILE_NAME_WIN32_DOS = 0x04

# ─── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class DataRun:
    """Represents a single data run (extent) in an NTFS run list."""
    length: int        # Number of clusters
    offset: int        # Starting cluster (absolute for first run, relative after)

@dataclass
class FileInfo:
    """Information about a user file to be placed in the image."""
    name: str
    data: bytes
    is_directory: bool = False
    parent_record: int = 5          # Root directory by default
    created: float = 0.0
    modified: float = 0.0
    # Filled by the builder
    record_number: int = -1
    cluster_runs: List[DataRun] = field(default_factory=list)
    sha256: str = ""

@dataclass
class NTFSLayout:
    """Computed layout of the NTFS image."""
    volume_size: int
    cluster_size: int
    sector_size: int
    total_clusters: int
    mft_start_cluster: int
    mft_record_count: int
    mft_clusters: int
    mftmirr_start_cluster: int
    mftmirr_clusters: int
    bitmap_start_cluster: int
    bitmap_clusters: int
    logfile_start_cluster: int
    logfile_clusters: int
    upcase_start_cluster: int
    upcase_clusters: int
    data_start_cluster: int
    serial_number: int


# ─── NTFS Image Builder ───────────────────────────────────────────────────────

class NTFSImageBuilder:
    """
    Builds a complete NTFS disk image from scratch.

    Usage:
        builder = NTFSImageBuilder(volume_size=10*1024*1024, cluster_size=4096, serial=12345)
        builder.add_file("foto001.jpg", b"...", is_directory=False)
        builder.add_directory("Documents", parent_record=5)
        image_bytes = builder.build()
    """

    def __init__(self, volume_size: int = 10*1024*1024,
                 cluster_size: int = 4096,
                 serial_number: int = 0,
                 mft_zone_fraction: float = 0.25):
        self.volume_size = volume_size
        self.cluster_size = cluster_size
        self.sector_size = SECTOR_SIZE
        self.serial_number = serial_number
        self.mft_zone_fraction = mft_zone_fraction

        self.total_clusters = volume_size // cluster_size
        self.sectors_per_cluster = cluster_size // SECTOR_SIZE

        self._files: List[FileInfo] = []
        self._directories: List[FileInfo] = []
        self._layout: Optional[NTFSLayout] = None
        self._image: bytearray = bytearray(volume_size)
        self._allocated_clusters: set = set()

    def add_file(self, name: str, data: bytes,
                 parent_record: int = 5,
                 created: float = 0.0,
                 modified: float = 0.0) -> FileInfo:
        """Add a file to the image. Returns FileInfo for manifest tracking."""
        sha256 = hashlib.sha256(data).hexdigest()
        info = FileInfo(
            name=name, data=data,
            is_directory=False,
            parent_record=parent_record,
            created=created, modified=modified,
            sha256=sha256,
        )
        self._files.append(info)
        return info

    def add_directory(self, name: str, parent_record: int = 5,
                      created: float = 0.0, modified: float = 0.0) -> FileInfo:
        """Add a directory. Returns FileInfo for manifest tracking."""
        info = FileInfo(
            name=name, data=b"",
            is_directory=True,
            parent_record=parent_record,
            created=created, modified=modified,
        )
        self._directories.append(info)
        return info

    def build(self) -> Tuple[bytearray, NTFSLayout, List[FileInfo]]:
        """
        Build the complete NTFS image.

        Returns:
            (image_bytes, layout, all_files_with_cluster_info)
        """
        # 1. Compute layout
        self._compute_layout()

        # 2. Write VBR
        self._write_vbr()

        # 3. Allocate clusters for user data
        self._allocate_user_data()

        # 4. Write MFT records
        self._write_mft()

        # 5. Write MFT Mirror
        self._write_mftmirr()

        # 6. Write Bitmap
        self._write_bitmap()

        # 7. Write LogFile
        self._write_logfile()

        # 8. Write UpCase table
        self._write_upcase()

        # 9. Write user file data
        self._write_user_data()

        # 10. Write bootstrap code
        self._write_bootstrap()

        return bytes(self._image), self._layout, self._files + self._directories

    # ─── Layout Computation ───────────────────────────────────────────────

    def _compute_layout(self):
        """Compute where each structure lives on disk."""
        total = self.total_clusters
        cs = self.cluster_size
        records_per_cluster = cs // MFT_RECORD_SIZE

        # MFT starts at cluster 2 (after VBR)
        mft_start = 2

        # We need system records (0-11) + user files + user directories
        total_user_items = len(self._files) + len(self._directories)
        total_records = 12 + total_user_items   # 12 system + user items
        mft_clusters = (total_records * MFT_RECORD_SIZE + cs - 1) // cs

        # MFT Mirror: first 4 MFT records (4 * 1024 = 4096 = 1 cluster)
        mftmirr_start = mft_start + mft_clusters
        mftmirr_clusters = 1

        # Bitmap: 1 bit per cluster
        bitmap_bytes = (total + 7) // 8
        bitmap_clusters = (bitmap_bytes + cs - 1) // cs

        bitmap_start = mftmirr_start + mftmirr_clusters

        # LogFile: 2 clusters (minimal)
        logfile_start = bitmap_start + bitmap_clusters
        logfile_clusters = 2

        # UpCase table: 128KB (65536 entries * 2 bytes)
        upcase_bytes = 65536 * 2
        upcase_clusters = (upcase_bytes + cs - 1) // cs
        upcase_start = logfile_start + logfile_clusters

        # Data area starts after UpCase
        data_start = upcase_start + upcase_clusters

        # Assign record numbers
        # Directories first (so files can reference them), then files
        record_num = 12  # After system files
        for d in self._directories:
            d.record_number = record_num
            record_num += 1
        for f in self._files:
            f.record_number = record_num
            record_num += 1

        self._layout = NTFSLayout(
            volume_size=self.volume_size,
            cluster_size=self.cluster_size,
            sector_size=self.sector_size,
            total_clusters=total,
            mft_start_cluster=mft_start,
            mft_record_count=total_records,
            mft_clusters=mft_clusters,
            mftmirr_start_cluster=mftmirr_start,
            mftmirr_clusters=mftmirr_clusters,
            bitmap_start_cluster=bitmap_start,
            bitmap_clusters=bitmap_clusters,
            logfile_start_cluster=logfile_start,
            logfile_clusters=logfile_clusters,
            upcase_start_cluster=upcase_start,
            upcase_clusters=upcase_clusters,
            data_start_cluster=data_start,
            serial_number=self.serial_number,
        )

    # ─── VBR (Volume Boot Record) ─────────────────────────────────────────

    def _write_vbr(self):
        """Write the Volume Boot Record (sector 0)."""
        L = self._layout
        vbr = bytearray(SECTOR_SIZE)

        # Jump instruction
        vbr[0:3] = b'\xEB\x52\x90'

        # OEM ID
        vbr[3:11] = b'NTFS    '

        # BPB (BIOS Parameter Block)
        struct.pack_into('<H', vbr, 11, self.sector_size)       # Bytes per sector
        vbr[13] = self.sectors_per_cluster                        # Sectors per cluster
        struct.pack_into('<H', vbr, 14, 0)                       # Reserved sectors
        vbr[16] = 0                                               # Always 0 for NTFS
        vbr[17] = 0                                               # Always 0 for NTFS
        vbr[18] = 0                                               # Always 0 for NTFS
        struct.pack_into('<H', vbr, 19, 0)                       # Not used (0)
        vbr[21] = 0xF8                                            # Media descriptor (hard disk)
        struct.pack_into('<H', vbr, 22, 0)                       # Always 0 for NTFS
        struct.pack_into('<H', vbr, 24, self.sectors_per_cluster)# Sectors per track (fake)
        struct.pack_into('<H', vbr, 26, 255)                     # Number of heads (fake)
        struct.pack_into('<I', vbr, 28, 0)                       # Hidden sectors
        struct.pack_into('<I', vbr, 32, 0)                       # Always 0 for NTFS

        # Extended BPB
        struct.pack_into('<Q', vbr, 40, L.total_clusters * self.sectors_per_cluster)  # Total sectors
        struct.pack_into('<Q', vbr, 48, L.mft_start_cluster)     # MFT start cluster
        struct.pack_into('<Q', vbr, 56, L.mftmirr_start_cluster) # MFT mirror cluster
        vbr[64] = 0xF6   # Clusters per MFT record: -10 → 2^10 = 1024
        # Actually: signed byte, 0xF6 = -10, meaning 2^10 = 1024 bytes
        vbr[65] = 0      # Reserved
        vbr[66] = 0x00   # Clusters per Index Record (0 means default)
        vbr[67] = 0      # Reserved

        # Volume serial number
        struct.pack_into('<I', vbr, 72, L.serial_number & 0xFFFFFFFF)

        # Checksum
        struct.pack_into('<I', vbr, 76, 0)  # Placeholder

        # Boot signature
        vbr[510] = 0x55
        vbr[511] = 0xAA

        self._image[0:SECTOR_SIZE] = vbr

    # ─── MFT Record Construction ──────────────────────────────────────────

    def _make_mft_record(self, record_number: int, in_use: bool = True,
                         is_directory: bool = False,
                         attrs: Optional[List[bytes]] = None) -> bytes:
        """Build a single MFT file record (1024 bytes)."""
        rec = bytearray(MFT_RECORD_SIZE)

        # ─── Header ───
        rec[0:4] = b'FILE'                                 # Signature
        struct.pack_into('<H', rec, 4, 48)                  # Fixup offset
        struct.pack_into('<H', rec, 6, 3)                   # Fixup count (1 + 2 entries)
        struct.pack_into('<Q', rec, 8, 0)                   # LSN
        struct.pack_into('<H', rec, 16, 1)                  # Sequence number
        struct.pack_into('<H', rec, 18, 1)                  # Hard link count
        struct.pack_into('<H', rec, 20, 56)                 # First attribute offset
        flags = 0
        if in_use:
            flags |= MFT_RECORD_IN_USE
        if is_directory:
            flags |= MFT_RECORD_DIRECTORY
        struct.pack_into('<H', rec, 22, flags)              # Flags

        # Write attributes
        offset = 56  # After header
        if attrs:
            for attr_data in attrs:
                rec[offset:offset+len(attr_data)] = attr_data
                offset += len(attr_data)

        # End marker
        struct.pack_into('<I', rec, offset, 0xFFFFFFFF)

        # Used size
        struct.pack_into('<I', rec, 24, offset + 4)         # Used size of record
        struct.pack_into('<I', rec, 28, MFT_RECORD_SIZE)    # Allocated size

        # Fixup values (simple: just use 0x0001 as the update sequence)
        fixup_value = 0x0001
        struct.pack_into('<H', rec, 48, fixup_value)         # Fixup value at offset 48

        # Apply fixup to last 2 bytes of each sector
        # Sector 0: bytes 510-511
        original_510 = struct.unpack_from('<H', rec, 510)[0]
        struct.pack_into('<H', rec, 510, fixup_value)
        # Sector 1: bytes 1022-1023
        original_1022 = struct.unpack_from('<H', rec, 1022)[0]
        struct.pack_into('<H', rec, 1022, fixup_value)

        # Store originals at fixup area (offset 50, 52)
        struct.pack_into('<H', rec, 50, original_510)
        struct.pack_into('<H', rec, 52, original_1022)

        return bytes(rec)

    # ─── Attribute Builders ────────────────────────────────────────────────

    def _make_attr_standard_information(self, created: float = 0.0,
                                         modified: float = 0.0) -> bytes:
        """Build $STANDARD_INFORMATION attribute (0x10)."""
        attr = bytearray(72 + 24)  # header (resident) + 72 bytes data
        # Actually: resident header is 24 bytes, then data follows

        # Resident attribute header
        struct.pack_into('<I', attr, 0, AttrType.STANDARD_INFORMATION)  # Type
        struct.pack_into('<I', attr, 4, 96)                              # Total length
        attr[8] = 0                                                      # Non-resident = 0
        attr[9] = 0                                                      # Name length
        struct.pack_into('<H', attr, 10, 24)                             # Offset to name
        struct.pack_into('<H', attr, 12, 0)                              # Flags
        struct.pack_into('<H', attr, 14, 0)                              # Attribute ID
        struct.pack_into('<I', attr, 16, 72)                             # Data length
        struct.pack_into('<H', attr, 20, 24)                             # Offset to data
        attr[22] = 0                                                     # Indexed flag
        attr[23] = 0                                                     # Padding

        # $STANDARD_INFORMATION data (72 bytes)
        # NTFS timestamps are 100-nanosecond intervals since 1601-01-01
        # For simplicity, use a fixed base timestamp
        base_ts = 132485760000000000  # ~2020-01-01
        created_ts = base_ts + int(created * 10000000)
        modified_ts = base_ts + int(modified * 10000000)

        struct.pack_into('<Q', attr, 24, created_ts)        # Creation time
        struct.pack_into('<Q', attr, 32, modified_ts)        # Modification time
        struct.pack_into('<Q', attr, 40, modified_ts)        # MFT change time
        struct.pack_into('<Q', attr, 48, created_ts)         # Access time
        struct.pack_into('<I', attr, 56, 0x00000020)         # File attributes (Archive)
        struct.pack_into('<I', attr, 60, 0)                  # Max versions
        struct.pack_into('<I', attr, 64, 0)                  # Version number
        struct.pack_into('<I', attr, 68, 0)                  # Class ID
        struct.pack_into('<I', attr, 72, 0)                  # Owner ID
        struct.pack_into('<I', attr, 76, 0)                  # Security ID
        struct.pack_into('<Q', attr, 80, 0)                  # Quota charged
        struct.pack_into('<Q', attr, 88, 0)                  # USN

        return bytes(attr[:96])

    def _make_attr_file_name(self, name: str, parent_record: int = 5,
                              is_directory: bool = False,
                              created: float = 0.0,
                              modified: float = 0.0,
                              file_size: int = 0) -> bytes:
        """Build $FILE_NAME attribute (0x30)."""
        # Encode name as UTF-16LE
        name_bytes = name.encode('utf-16-le')
        name_len = len(name_bytes)
        data_size = 66 + name_len
        total_size = 24 + data_size  # resident header + data

        attr = bytearray(total_size + 7)  # +7 for alignment
        # Round up to 8-byte boundary
        total_size = ((total_size + 7) // 8) * 8

        # Resident attribute header
        struct.pack_into('<I', attr, 0, AttrType.FILE_NAME)
        struct.pack_into('<I', attr, 4, total_size)
        attr[8] = 0                                  # Non-resident = 0
        attr[9] = 0                                  # Name length
        struct.pack_into('<H', attr, 10, 24)         # Offset to name
        struct.pack_into('<H', attr, 12, 0)          # Flags
        struct.pack_into('<H', attr, 14, 1)          # Attribute ID
        struct.pack_into('<I', attr, 16, data_size)   # Data length
        struct.pack_into('<H', attr, 20, 24)         # Offset to data
        attr[22] = 1                                 # Indexed flag
        attr[23] = 0                                 # Padding

        # $FILE_NAME data
        # Parent directory reference (8 bytes: record_number + sequence)
        struct.pack_into('<I', attr, 24, parent_record)   # Parent MFT record number
        struct.pack_into('<H', attr, 28, 1)               # Parent sequence number
        struct.pack_into('<H', attr, 30, 0)               # Padding

        base_ts = 132485760000000000
        created_ts = base_ts + int(created * 10000000)
        modified_ts = base_ts + int(modified * 10000000)

        struct.pack_into('<Q', attr, 32, created_ts)       # Creation time
        struct.pack_into('<Q', attr, 40, modified_ts)      # Modification time
        struct.pack_into('<Q', attr, 48, modified_ts)      # MFT change time
        struct.pack_into('<Q', attr, 56, created_ts)       # Access time

        struct.pack_into('<Q', attr, 64, file_size)        # Allocated size
        struct.pack_into('<Q', attr, 72, file_size)        # Real size

        flags = 0x10000000 if is_directory else 0x00000020  # DIRECTORY or ARCHIVE
        struct.pack_into('<I', attr, 80, flags)            # File attributes

        struct.pack_into('<I', attr, 84, 0)               # Reparse / EA
        attr[88] = len(name) // 2 + (len(name) % 2)       # Name length in UTF-16 chars
        # Actually, name length in characters
        name_chars = len(name)
        attr[88] = name_chars                               # Name length in characters
        attr[89] = FILE_NAME_WIN32                          # Name type

        # Name (UTF-16LE)
        attr[90:90+name_len] = name_bytes

        return bytes(attr[:total_size])

    def _make_attr_data_resident(self, data: bytes) -> bytes:
        """Build a resident $DATA attribute (0x80) for small files."""
        data_len = len(data)
        total_size = 24 + data_len
        total_size = ((total_size + 7) // 8) * 8  # 8-byte alignment

        attr = bytearray(total_size)

        struct.pack_into('<I', attr, 0, AttrType.DATA)
        struct.pack_into('<I', attr, 4, total_size)
        attr[8] = 0                                  # Non-resident = 0
        attr[9] = 0                                  # Name length
        struct.pack_into('<H', attr, 10, 24)         # Offset to name
        struct.pack_into('<H', attr, 12, 0)          # Flags
        struct.pack_into('<H', attr, 14, 2)          # Attribute ID
        struct.pack_into('<I', attr, 16, data_len)    # Data length
        struct.pack_into('<H', attr, 20, 24)         # Offset to data
        attr[22] = 0                                 # Indexed flag
        attr[23] = 0                                 # Padding

        attr[24:24+data_len] = data

        return bytes(attr)

    def _make_attr_data_nonresident(self, runs: List[DataRun],
                                     data_size: int) -> bytes:
        """Build a non-resident $DATA attribute (0x80) with run list."""
        # Encode data runs
        run_list = self._encode_run_list(runs)
        run_list += b'\x00'  # End marker

        # Non-resident header: 64 bytes + run list
        total_size = 64 + len(run_list)
        total_size = ((total_size + 7) // 8) * 8  # 8-byte alignment

        attr = bytearray(total_size)

        struct.pack_into('<I', attr, 0, AttrType.DATA)
        struct.pack_into('<I', attr, 4, total_size)
        attr[8] = 1                                  # Non-resident = 1
        attr[9] = 0                                  # Name length
        struct.pack_into('<H', attr, 10, 64)         # Offset to name
        struct.pack_into('<H', attr, 12, 0)          # Flags
        struct.pack_into('<H', attr, 14, 2)          # Attribute ID

        # Non-resident specific fields
        struct.pack_into('<Q', attr, 16, 0)          # Starting VCN
        last_vcn = sum(r.length for r in runs) - 1
        struct.pack_into('<Q', attr, 24, last_vcn)   # Last VCN
        struct.pack_into('<H', attr, 32, 64)         # Offset to data runs
        struct.pack_into('<H', attr, 34, 0)          # Compression unit size
        struct.pack_into('<I', attr, 36, 0)          # Padding
        struct.pack_into('<Q', attr, 40, data_size)   # Allocated size (in bytes)
        struct.pack_into('<Q', attr, 48, data_size)   # Real size
        struct.pack_into('<Q', attr, 56, data_size)   # Initialized size

        # Run list
        attr[64:64+len(run_list)] = run_list

        return bytes(attr)

    def _encode_run_list(self, runs: List[DataRun]) -> bytes:
        """Encode data runs into NTFS run list format."""
        result = bytearray()
        current_offset = 0

        for i, run in enumerate(runs):
            if i == 0:
                current_offset = run.offset
            else:
                current_offset = run.offset  # Already absolute

            # Determine how many bytes needed for length and offset
            length_bytes = self._bytes_needed(run.length)
            offset_bytes = self._bytes_needed(abs(current_offset))

            # Header byte: low nibble = length size, high nibble = offset size
            header = (length_bytes & 0x0F) | ((offset_bytes & 0x0F) << 4)
            result.append(header)

            # Length (little-endian)
            result.extend(run.length.to_bytes(length_bytes, 'little'))

            # Offset (little-endian, signed)
            if current_offset >= 0:
                result.extend(current_offset.to_bytes(offset_bytes, 'little'))
            else:
                result.extend(current_offset.to_bytes(offset_bytes, 'little', signed=True))

        return bytes(result)

    @staticmethod
    def _bytes_needed(value: int) -> int:
        """Return minimum bytes needed to represent a value."""
        if value == 0:
            return 1
        return (value.bit_length() + 7) // 8

    def _make_attr_index_root(self, children: List[int]) -> bytes:
        """Build $INDEX_ROOT attribute (0x90) for a directory."""
        # Index root header + entry
        # Minimal: just the header with no entries
        entry_size = 0
        for child_rec in children:
            # Each index entry: 16 bytes minimum + filename
            entry_size += 16 + 4  # minimal entry

        data_size = 16 + 16 + entry_size  # INDEX_ROOT header + node header + entries
        total_size = 24 + data_size
        total_size = ((total_size + 7) // 8) * 8

        attr = bytearray(total_size)

        struct.pack_into('<I', attr, 0, AttrType.INDEX_ROOT)
        struct.pack_into('<I', attr, 4, total_size)
        attr[8] = 0
        attr[9] = 4   # $I30 name
        struct.pack_into('<H', attr, 10, 24)
        struct.pack_into('<H', attr, 12, 0)
        struct.pack_into('<H', attr, 14, 3)  # Attribute ID
        struct.pack_into('<I', attr, 16, data_size)
        struct.pack_into('<H', attr, 20, 24)
        attr[22] = 0
        attr[23] = 0

        # INDEX_ROOT header
        struct.pack_into('<I', attr, 24, AttrType.INDEX_ROOT)  # Attribute type
        struct.pack_into('<I', attr, 28, 16)                    # Collation rule (filename)
        struct.pack_into('<I', attr, 32, MFT_RECORD_SIZE)       # Index entry size
        attr[36] = 1                                              # Clusters per index record

        # Index node header (starts at offset 40 from attr start)
        struct.pack_into('<I', attr, 40, 16)                    # Offset to first entry
        struct.pack_into('<I', attr, 44, 16 + entry_size)       # Total size of entries
        struct.pack_into('<I', attr, 48, 16 + entry_size)       # Allocated size
        struct.pack_into('<I', attr, 52, 0)                      # Flags (leaf node)

        return bytes(attr[:total_size])

    # ─── MFT Writing ──────────────────────────────────────────────────────

    def _write_mft(self):
        """Write all MFT records."""
        L = self._layout
        mft_offset = L.mft_start_cluster * self.cluster_size

        # System file records
        system_records = self._build_system_records()

        # User directory records
        dir_records = []
        for d in self._directories:
            children = [f.record_number for f in self._files
                       if f.parent_record == d.record_number]
            attrs = [
                self._make_attr_standard_information(d.created, d.modified),
                self._make_attr_file_name(d.name, d.parent_record, True,
                                          d.created, d.modified, 0),
                self._make_attr_index_root(children),
            ]
            rec = self._make_mft_record(d.record_number, True, True, attrs)
            dir_records.append(rec)

        # User file records
        file_records = []
        for f in self._files:
            if f.cluster_runs:
                data_attr = self._make_attr_data_nonresident(
                    f.cluster_runs, len(f.data))
            else:
                data_attr = self._make_attr_data_resident(f.data)

            attrs = [
                self._make_attr_standard_information(f.created, f.modified),
                self._make_attr_file_name(f.name, f.parent_record, False,
                                          f.created, f.modified, len(f.data)),
                data_attr,
            ]
            rec = self._make_mft_record(f.record_number, True, False, attrs)
            file_records.append(rec)

        # Write $MFT entry (record 0) — must reference itself
        mft_attrs = [
            self._make_attr_standard_information(),
            self._make_attr_file_name("$MFT", 5, False, 0, 0, 0),
            self._make_attr_data_nonresident(
                [DataRun(length=L.mft_clusters, offset=L.mft_start_cluster)],
                L.mft_clusters * self.cluster_size
            ),
        ]
        mft_rec = self._make_mft_record(0, True, False, mft_attrs)

        # Write all records
        all_records = [mft_rec] + system_records[1:] + dir_records + file_records
        for i, rec in enumerate(all_records):
            offset = mft_offset + i * MFT_RECORD_SIZE
            self._image[offset:offset+MFT_RECORD_SIZE] = rec

    def _build_system_records(self) -> List[bytes]:
        """Build MFT records for system files (0-11)."""
        L = self._layout
        records = [b''] * 12  # Placeholder, will fill

        # Record 0: $MFT — will be written separately
        # Record 1: $MFTMirr
        records[1] = self._make_mft_record(1, True, False, [
            self._make_attr_standard_information(),
            self._make_attr_file_name("$MFTMirr", 5, False, 0, 0, 0),
            self._make_attr_data_nonresident(
                [DataRun(length=L.mftmirr_clusters, offset=L.mftmirr_start_cluster)],
                L.mftmirr_clusters * self.cluster_size
            ),
        ])

        # Record 2: $LogFile
        records[2] = self._make_mft_record(2, True, False, [
            self._make_attr_standard_information(),
            self._make_attr_file_name("$LogFile", 5, False, 0, 0, 0),
            self._make_attr_data_nonresident(
                [DataRun(length=L.logfile_clusters, offset=L.logfile_start_cluster)],
                L.logfile_clusters * self.cluster_size
            ),
        ])

        # Record 3: $Volume
        records[3] = self._make_mft_record(3, True, False, [
            self._make_attr_standard_information(),
            self._make_attr_file_name("$Volume", 5, False, 0, 0, 0),
            # VOLUME_INFORMATION attribute
            self._make_attr_volume_info(),
        ])

        # Record 4: $AttrDef
        records[4] = self._make_mft_record(4, True, False, [
            self._make_attr_standard_information(),
            self._make_attr_file_name("$AttrDef", 5, False, 0, 0, 0),
        ])

        # Record 5: Root directory (.)
        records[5] = self._make_mft_record(5, True, True, [
            self._make_attr_standard_information(),
            self._make_attr_file_name(".", 5, True, 0, 0, 0),
            self._make_attr_index_root([]),
        ])

        # Record 6: $Bitmap
        records[6] = self._make_mft_record(6, True, False, [
            self._make_attr_standard_information(),
            self._make_attr_file_name("$Bitmap", 5, False, 0, 0, 0),
            self._make_attr_data_nonresident(
                [DataRun(length=L.bitmap_clusters, offset=L.bitmap_start_cluster)],
                L.bitmap_clusters * self.cluster_size
            ),
        ])

        # Record 7: $Boot
        records[7] = self._make_mft_record(7, True, False, [
            self._make_attr_standard_information(),
            self._make_attr_file_name("$Boot", 5, False, 0, 0, 0),
            self._make_attr_data_nonresident(
                [DataRun(length=2, offset=0)],  # First 2 clusters
                2 * self.cluster_size
            ),
        ])

        # Record 8: $BadClus
        records[8] = self._make_mft_record(8, True, False, [
            self._make_attr_standard_information(),
            self._make_attr_file_name("$BadClus", 5, False, 0, 0, 0),
        ])

        # Record 9: $Secure
        records[9] = self._make_mft_record(9, True, False, [
            self._make_attr_standard_information(),
            self._make_attr_file_name("$Secure", 5, False, 0, 0, 0),
        ])

        # Record 10: $UpCase
        records[10] = self._make_mft_record(10, True, False, [
            self._make_attr_standard_information(),
            self._make_attr_file_name("$UpCase", 5, False, 0, 0, 0),
            self._make_attr_data_nonresident(
                [DataRun(length=L.upcase_clusters, offset=L.upcase_start_cluster)],
                L.upcase_clusters * self.cluster_size
            ),
        ])

        # Record 11: $Extend
        records[11] = self._make_mft_record(11, True, True, [
            self._make_attr_standard_information(),
            self._make_attr_file_name("$Extend", 5, True, 0, 0, 0),
            self._make_attr_index_root([]),
        ])

        return records

    def _make_attr_volume_info(self) -> bytes:
        """Build VOLUME_INFORMATION attribute (0x70)."""
        total_size = 32  # 24 header + 8 data
        attr = bytearray(total_size)

        struct.pack_into('<I', attr, 0, AttrType.VOLUME_INFORMATION)
        struct.pack_into('<I', attr, 4, total_size)
        attr[8] = 0
        attr[9] = 0
        struct.pack_into('<H', attr, 10, 24)
        struct.pack_into('<H', attr, 12, 0)
        struct.pack_into('<H', attr, 14, 4)
        struct.pack_into('<I', attr, 16, 8)   # Data length
        struct.pack_into('<H', attr, 20, 24)  # Offset to data
        attr[22] = 0
        attr[23] = 0

        # Volume info data
        struct.pack_into('<Q', attr, 24, 0x00030001)  # NTFS 3.1

        return bytes(attr)

    # ─── MFT Mirror ───────────────────────────────────────────────────────

    def _write_mftmirr(self):
        """Write MFT Mirror (first 4 MFT records)."""
        L = self._layout
        mirr_offset = L.mftmirr_start_cluster * self.cluster_size
        mft_offset = L.mft_start_cluster * self.cluster_size

        # Copy first 4 MFT records
        for i in range(4):
            src = mft_offset + i * MFT_RECORD_SIZE
            dst = mirr_offset + i * MFT_RECORD_SIZE
            self._image[dst:dst+MFT_RECORD_SIZE] = self._image[src:src+MFT_RECORD_SIZE]

    # ─── Bitmap ───────────────────────────────────────────────────────────

    def _write_bitmap(self):
        """Write the cluster allocation bitmap."""
        L = self._layout
        bitmap_offset = L.bitmap_start_cluster * self.cluster_size
        bitmap_bytes = (L.total_clusters + 7) // 8

        bitmap = bytearray(bitmap_bytes)

        # Mark allocated clusters
        for cluster in self._allocated_clusters:
            byte_idx = cluster // 8
            bit_idx = cluster % 8
            bitmap[byte_idx] |= (1 << bit_idx)

        # Also mark system clusters
        for cluster in range(L.data_start_cluster):
            byte_idx = cluster // 8
            bit_idx = cluster % 8
            bitmap[byte_idx] |= (1 << bit_idx)

        self._image[bitmap_offset:bitmap_offset+bitmap_bytes] = bitmap

    # ─── LogFile ──────────────────────────────────────────────────────────

    def _write_logfile(self):
        """Write a minimal $LogFile."""
        L = self._layout
        log_offset = L.logfile_start_cluster * self.cluster_size
        log_size = L.logfile_clusters * self.cluster_size

        # Minimal restart page header
        log = bytearray(log_size)
        # Restart page signature
        log[0:4] = b'NTFS'
        # Fill with zeros (empty journal)
        self._image[log_offset:log_offset+log_size] = log

    # ─── UpCase Table ─────────────────────────────────────────────────────

    def _write_upcase(self):
        """Write the $UpCase table (uppercase conversion table)."""
        L = self._layout
        upcase_offset = L.upcase_start_cluster * self.cluster_size
        upcase_size = 65536 * 2  # 65536 entries, 2 bytes each

        upcase = bytearray(upcase_size)
        for i in range(65536):
            # Simple: uppercase mapping (identity for most, swap for a-z)
            if 0x61 <= i <= 0x7A:  # a-z
                struct.pack_into('<H', upcase, i * 2, i - 32)
            else:
                struct.pack_into('<H', upcase, i * 2, i)

        self._image[upcase_offset:upcase_offset+upcase_size] = upcase

    # ─── User Data Allocation ─────────────────────────────────────────────

    def _allocate_user_data(self):
        """Allocate clusters for user files and assign data runs."""
        L = self._layout
        next_cluster = L.data_start_cluster

        for f in self._files:
            if len(f.data) == 0:
                continue

            # Decide: resident or non-resident?
            # Files > 700 bytes go non-resident
            if len(f.data) <= 700:
                # Resident — data stored in MFT record itself
                f.cluster_runs = []
                continue

            # Non-resident: allocate clusters
            clusters_needed = (len(f.data) + self.cluster_size - 1) // self.cluster_size
            start_cluster = next_cluster

            # For now, contiguous allocation (no fragmentation)
            # Fragmentation can be added by the Corruptor or dataset profiles
            f.cluster_runs = [DataRun(length=clusters_needed, offset=start_cluster)]

            # Mark clusters as allocated
            for c in range(start_cluster, start_cluster + clusters_needed):
                self._allocated_clusters.add(c)

            next_cluster = start_cluster + clusters_needed

    def _write_user_data(self):
        """Write actual file data to the image."""
        for f in self._files:
            if f.cluster_runs:
                # Non-resident: write to clusters
                for run in f.cluster_runs:
                    offset = run.offset * self.cluster_size
                    end = offset + run.length * self.cluster_size
                    # Write data (padded to cluster boundary)
                    data_padded = f.data + b'\x00' * (run.length * self.cluster_size - len(f.data))
                    self._image[offset:end] = data_padded[:run.length * self.cluster_size]
            # Resident data is written inside the MFT record itself

    # ─── Bootstrap Code ───────────────────────────────────────────────────

    def _write_bootstrap(self):
        """Write minimal bootstrap code in sectors 1-7."""
        # Just zeros — the bootstrap is not needed for recovery testing
        pass

    # ─── Utility ──────────────────────────────────────────────────────────

    def get_manifest_data(self) -> Dict:
        """Return manifest data for the built image."""
        L = self._layout
        files = []

        for f in self._files:
            cluster_list = []
            for run in f.cluster_runs:
                cluster_list.extend(range(run.offset, run.offset + run.length))

            fragment_count = len(f.cluster_runs)
            is_fragmented = fragment_count > 1

            files.append({
                "id": f.record_number,
                "name": f.name,
                "sha256": f.sha256,
                "size": len(f.data),
                "clusters": cluster_list,
                "fragment_count": fragment_count,
                "is_fragmented": is_fragmented,
                "is_resident": len(f.cluster_runs) == 0 and len(f.data) > 0,
                "created": f.created,
                "modified": f.modified,
                "parent_record": f.parent_record,
            })

        for d in self._directories:
            files.append({
                "id": d.record_number,
                "name": d.name,
                "sha256": "",
                "size": 0,
                "clusters": [],
                "fragment_count": 0,
                "is_fragmented": False,
                "is_resident": False,
                "is_directory": True,
                "created": d.created,
                "modified": d.modified,
                "parent_record": d.parent_record,
            })

        return {
            "seed": self.serial_number,  # Using serial as seed identifier
            "filesystem": "NTFS",
            "cluster_size": self.cluster_size,
            "sector_size": self.sector_size,
            "serial": hex(self.serial_number),
            "volume_size": self.volume_size,
            "total_clusters": L.total_clusters,
            "files": files,
            "mft": {
                "start_cluster": L.mft_start_cluster,
                "clusters": list(range(L.mft_start_cluster,
                                       L.mft_start_cluster + L.mft_clusters)),
                "record_count": L.mft_record_count,
                "record_size": MFT_RECORD_SIZE,
            },
            "bitmap": {
                "start_cluster": L.bitmap_start_cluster,
                "clusters": list(range(L.bitmap_start_cluster,
                                       L.bitmap_start_cluster + L.bitmap_clusters)),
            },
            "mftmirr": {
                "start_cluster": L.mftmirr_start_cluster,
                "clusters": list(range(L.mftmirr_start_cluster,
                                       L.mftmirr_start_cluster + L.mftmirr_clusters)),
            },
            "logfile": {
                "start_cluster": L.logfile_start_cluster,
                "clusters": list(range(L.logfile_start_cluster,
                                       L.logfile_start_cluster + L.logfile_clusters)),
            },
            "data_area_start": L.data_start_cluster,
        }
