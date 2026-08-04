# NTFS USN Journal ($UsnJrnl) Binary Format Specification

> **Authoritative sources**: Microsoft Win32 `winioctl.h` docs, Microsoft NT kernel driver `ntifs.h` docs,
> libyal/libfsntfs NTFS specification, forefst ReFS reference, and cross-validated forensic sources.
> Last verified: 2026-03-05

---

## 1. $UsnJrnl Location & MFT Entry

| Property | Value |
|----------|-------|
| **Path** | `$Extend\$UsnJrnl` (child of MFT entry 11, the `$Extend` directory) |
| **MFT entry number** | **Not fixed.** The first 24 MFT entries (0–23) are reserved for core system files. `$UsnJrnl` is allocated dynamically as a child of `$Extend` — typically MFT entry **24** or **25** on a fresh volume, but this is **not guaranteed** and must be resolved by reading the `$Extend` directory index. |
| **Data streams** | Two Alternate Data Streams (ADS): **`$J`** and **`$Max`** |

### System MFT entries (first 24, for reference)

| Entry | Name | Entry | Name |
|-------|------|-------|------|
| 0 | $MFT | 12 | $Quota |
| 1 | $MFTMirr | 13 | $ObjId |
| 2 | $LogFile | 14 | ? |
| 3 | $Volume | 15–16 | ? |
| 4 | $AttrDef | 17 | ? |
| 5 | $Root | 18–23 | Reserved |
| 6 | $Bitmap | | |
| 7 | $Boot | | |
| 8 | $BadClus | | |
| 9 | $Secure | | |
| 10 | $UpCase | | |
| 11 | $Extend | | |

> `$UsnJrnl`, `$ObjId`, and `$Quota` are children of `$Extend` (entry 11). Their specific MFT entry numbers are allocated sequentially and vary.

---

## 2. $J vs $Max Streams

| Stream | Purpose | Content |
|--------|---------|---------|
| **`$J`** | **Journal data** — the actual change log records | Sequential `USN_RECORD_V2` (NTFS) or `USN_RECORD_V3` (ReFS) entries, plus `USN_RECORD_V4` extent records if range tracking is enabled. Stored as a **sparse file** — old records are zeroed out when the journal wraps. |
| **`$Max`** | **Journal metadata** — configuration & state | Contains the `USN_JOURNAL_DATA` structure with journal ID, size limits, and current USN position. Stored as a `$LOGGED_UTILITY_STREAM` (attribute type 0xF0) on the `$UsnJrnl` MFT entry. |

---

## 3. $Max Stream — USN_JOURNAL_DATA Structure

The `$Max` stream contains the journal configuration. It is read/written via `FSCTL_QUERY_USN_JOURNAL`.

| Offset | Size | Type | Field | Description |
|--------|------|------|-------|-------------|
| 0x00 | 8 | uint64 | UsnJournalID | Unique identifier for this journal instance. Changes when journal is deleted & recreated. |
| 0x08 | 8 | int64 | FirstUsn | USN of the first valid record in the journal. |
| 0x10 | 8 | int64 | NextUsn | USN where the next record will be written (current write position). |
| 0x18 | 8 | uint64 | MaximumSize | Maximum size of the journal in bytes. |
| 0x20 | 8 | uint64 | AllocationDelta | Memory allocation delta for journal growth. |
| 0x28 | 8 | int64 | MinimumUsn | Lowest valid USN in the journal (for wrap-around detection). |

**Total size**: 48 bytes (0x30)

---

## 4. $J Stream Format

### 4.1 Journal Header (Offset 0 of $J)

**The $J stream does NOT have a header structure at offset 0.**

When using `FSCTL_ENUM_USN_DATA`, the kernel returns a buffer where the **first 8 bytes** are the USN (int64) of the starting position for the next query. This is **NOT part of the on-disk format** — it is a kernel-returned prefix for the API. The actual on-disk `$J` stream begins directly with USN_RECORD entries.

On disk, the `$J` stream is a sequence of USN records appended sequentially. The **USN value** of each record equals its **virtual byte offset** in the journal stream (monotonic, never reused). Because `$J` is a sparse file, old regions are zeroed when the journal wraps, but the USN values keep increasing beyond the physical file size.

### 4.2 Reading USN Records

To iterate records from the raw `$J` stream:
1. Read the `RecordLength` (4 bytes at offset 0 of each record)
2. If `RecordLength == 0`, skip ahead (sparse zeroed region or padding)
3. Parse the record based on `MajorVersion` (2 bytes at offset 4)
4. Advance the read position by `RecordLength` bytes
5. Records are **8-byte aligned** (padded if necessary)

---

## 5. USN_RECORD_V2 Structure (NTFS, Windows 2000+)

**Major version**: 2, **Minor version**: 0
**Fixed header size**: 60 bytes (0x3C)
**Total record size**: `pad8(0x3C + FileNameLength)`

| Offset | Size | Type | Field | Description |
|--------|------|------|-------|-------------|
| 0x00 | 4 | uint32 | RecordLength | Total size of this record in bytes (including filename). 8-byte aligned. |
| 0x04 | 2 | uint16 | MajorVersion | 2 for V2 records |
| 0x06 | 2 | uint16 | MinorVersion | 0 |
| 0x08 | 8 | uint64 | FileReferenceNumber | 64-bit MFT file reference (see §7 below) |
| 0x10 | 8 | uint64 | ParentFileReferenceNumber | 64-bit MFT file reference of parent directory |
| 0x18 | 8 | int64 | Usn | Update Sequence Number = virtual byte offset in journal |
| 0x20 | 8 | FILETIME | TimeStamp | Time of the change (100ns ticks since 1601-01-01 UTC) |
| 0x28 | 4 | uint32 | Reason | Reason flags (see §8) |
| 0x2C | 4 | uint32 | SourceInfo | Source info flags (see §9) |
| 0x30 | 4 | uint32 | SecurityId | Security ID from $Secure |
| 0x34 | 4 | uint32 | FileAttributes | Win32 file attributes (see §10) |
| 0x38 | 2 | uint16 | FileNameLength | Length of filename in **bytes** (not characters) |
| 0x3A | 2 | uint16 | FileNameOffset | Offset of filename from start of record (always 0x3C for V2) |
| 0x3C | var | wchar[] | FileName | UTF-16LE null-terminated filename |

**C struct (from Microsoft winioctl.h / ntifs.h)**:
```c
typedef struct {
    DWORD RecordLength;           // 0x00
    WORD  MajorVersion;           // 0x04
    WORD  MinorVersion;           // 0x06
    DWORDLONG FileReferenceNumber;// 0x08
    DWORDLONG ParentFileReferenceNumber; // 0x10
    USN   Usn;                    // 0x18
    LARGE_INTEGER TimeStamp;      // 0x20
    DWORD Reason;                 // 0x28
    DWORD SourceInfo;             // 0x2C
    DWORD SecurityId;             // 0x30
    DWORD FileAttributes;         // 0x34
    WORD  FileNameLength;         // 0x38
    WORD  FileNameOffset;         // 0x3A
    WCHAR FileName[1];            // 0x3C (variable length)
} USN_RECORD_V2, *PUSN_RECORD_V2;
```

---

## 6. USN_RECORD_V3 Structure (ReFS / Windows 8+ NTFS)

**Major version**: 3, **Minor version**: 0
**Fixed header size**: 76 bytes (0x4C)
**Total record size**: `pad8(0x4C + FileNameLength)`

| Offset | Size | Type | Field | Description |
|--------|------|------|-------|-------------|
| 0x00 | 4 | uint32 | RecordLength | Total size of this record in bytes. 8-byte aligned. |
| 0x04 | 2 | uint16 | MajorVersion | 3 for V3 records |
| 0x06 | 2 | uint16 | MinorVersion | 0 |
| 0x08 | 16 | FILE_ID_128 | FileReferenceNumber | 128-bit file identifier (see §7 below) |
| 0x18 | 16 | FILE_ID_128 | ParentFileReferenceNumber | 128-bit file identifier of parent directory |
| 0x28 | 8 | int64 | Usn | Update Sequence Number = virtual byte offset in journal |
| 0x30 | 8 | FILETIME | TimeStamp | Time of the change (100ns ticks since 1601-01-01 UTC) |
| 0x38 | 4 | uint32 | Reason | Reason flags (see §8) |
| 0x3C | 4 | uint32 | SourceInfo | Source info flags (see §9) |
| 0x40 | 4 | uint32 | SecurityId | Security ID from $Secure |
| 0x44 | 4 | uint32 | FileAttributes | Win32 file attributes (see §10) |
| 0x48 | 2 | uint16 | FileNameLength | Length of filename in **bytes** |
| 0x4A | 2 | uint16 | FileNameOffset | Offset of filename from start of record (always 0x4C for V3) |
| 0x4C | var | wchar[] | FileName | UTF-16LE null-terminated filename |

**C struct**:
```c
typedef struct {
    DWORD       RecordLength;           // 0x00
    WORD        MajorVersion;           // 0x04
    WORD        MinorVersion;           // 0x06
    FILE_ID_128 FileReferenceNumber;    // 0x08
    FILE_ID_128 ParentFileReferenceNumber; // 0x18
    USN         Usn;                    // 0x28
    LARGE_INTEGER TimeStamp;            // 0x30
    DWORD       Reason;                 // 0x38
    DWORD       SourceInfo;             // 0x3C
    DWORD       SecurityId;             // 0x40
    DWORD       FileAttributes;         // 0x44
    WORD        FileNameLength;         // 0x48
    WORD        FileNameOffset;         // 0x4A
    WCHAR       FileName[1];            // 0x4C (variable length)
} USN_RECORD_V3, *PUSN_RECORD_V3;
```

### FILE_ID_128 Structure (128-bit)

```c
typedef struct {
    ULONG FileId64b[4];  // 16 bytes total
} FILE_ID_128, *PFILE_ID_128;
```

**On NTFS**: The 128-bit ID is effectively a 64-bit MFT reference number stored in the lower 8 bytes, with the upper 8 bytes being zero (or padding).

**On ReFS**: The upper 8 bytes are the B+-tree table OID, and the lower 8 bytes are the sequential entry index within that directory.

---

## 6.5 USN_RECORD_V4 Structure (Windows 10+, NTFS only)

V4 records are **range-tracking / extent records** introduced in Windows 10. They are only emitted when range tracking is enabled (`fsutil usn enablerangetracking`) and the file size >= the RangeTrackFileSizeThreshold.

**Key differences from V2/V3**:
- **NO filename** — filename comes from the companion V2/V3 record
- **NO timestamp** — timestamp comes from the companion V2/V3 record
- **NO SecurityId, NO FileAttributes**
- Contains an array of `USN_RECORD_EXTENT` structures describing which byte ranges were modified

**Microsoft guarantees**: Each V4 record is immediately followed by a V2 or V3 record that provides the filename, timestamp, and other metadata for the same USN.

**Major version**: 4, **Minor version**: 0
**Fixed header size**: 48 bytes (0x30) + (NumberOfExtents × 16)

| Offset | Size | Type | Field | Description |
|--------|------|------|-------|-------------|
| 0x00 | 4 | uint32 | RecordLength | Total size of this record in bytes |
| 0x04 | 2 | uint16 | MajorVersion | 4 for V4 records |
| 0x06 | 2 | uint16 | MinorVersion | 0 |
| 0x08 | 8 | uint64 | FileReferenceNumber | 64-bit MFT file reference |
| 0x10 | 8 | uint64 | ParentFileReferenceNumber | 64-bit MFT file reference of parent directory |
| 0x18 | 8 | int64 | Usn | Update Sequence Number |
| 0x20 | 4 | uint32 | Reason | Reason flags (only data-related reasons) |
| 0x24 | 4 | uint32 | SourceInfo | Source info flags |
| 0x28 | 4 | uint32 | RemainingExtents | Number of extents remaining in subsequent V4 records for this change |
| 0x2C | 4 | uint32 | NumberOfExtents | Number of USN_RECORD_EXTENT structures in this record |
| 0x30 | 16×N | USN_RECORD_EXTENT[] | Extent[] | Array of extent descriptors |

### USN_RECORD_EXTENT Structure (16 bytes)

| Offset | Size | Type | Field | Description |
|--------|------|------|-------|-------------|
| 0x00 | 8 | uint64 | Offset | Byte offset within the file where the modified region starts |
| 0x08 | 8 | uint64 | Length | Length in bytes of the modified region |

**C struct**:
```c
typedef struct {
    DWORDLONG Offset;    // 0x00
    DWORDLONG Length;    // 0x08
} USN_RECORD_EXTENT, *PUSN_RECORD_EXTENT;

typedef struct {
    DWORD       RecordLength;               // 0x00
    WORD        MajorVersion;               // 0x04
    WORD        MinorVersion;               // 0x06
    DWORDLONG   FileReferenceNumber;        // 0x08
    DWORDLONG   ParentFileReferenceNumber;  // 0x10
    USN         Usn;                        // 0x18
    DWORD       Reason;                     // 0x20
    DWORD       SourceInfo;                 // 0x24
    DWORD       RemainingExtents;           // 0x28
    DWORD       NumberOfExtents;            // 0x2C
    USN_RECORD_EXTENT Extent[1];            // 0x30 (variable length)
} USN_RECORD_V4, *PUSN_RECORD_V4;
```

---

## 7. File Reference Number → MFT Record Mapping

### V2 / V4 (64-bit FileReferenceNumber)

The 64-bit file reference number is composed of two fields:

```
 +---+---+---+---+---+---+---+---+
 |   MFT Sequence Number (16)    |  MFT Record Index (48)        |
 |  bytes 6-7 (big-endian view)  |  bytes 0-5                    |
 +---+---+---+---+---+---+---+---+
  63                              48                              0
```

| Component | Bits | Byte range (little-endian) | Description |
|-----------|------|---------------------------|-------------|
| **MFT Record Index** | 48 | bytes 0–5 | The MFT entry number (0-based index into $MFT) |
| **Sequence Number** | 16 | bytes 6–7 | Incremented each time the MFT entry is reused |

**Extraction**:
```python
mft_record_number = file_ref_number & 0xFFFFFFFFFFFF   # lower 48 bits
sequence_number   = (file_ref_number >> 48) & 0xFFFF    # upper 16 bits
```

**Example**: FileReferenceNumber = `0x0005000000000005`
- MFT record index = 0x000000000005 = **5** ($Root)
- Sequence number = 0x0005 = **5**

### V3 (128-bit FILE_ID_128)

**On NTFS**: Effectively a 64-bit reference stored in the lower 8 bytes (same decomposition as V2 above). Upper 8 bytes are zero/padding.

**On ReFS**:
- Upper 8 bytes: B+-tree table OID (identifies which directory's object table)
- Lower 8 bytes: Sequential entry index within that directory (monotonically increasing, never reused)

---

## 8. USN_REASON Flags

These are bitmask flags — a single record can combine multiple flags (e.g., `0x80000100` = FILE_CREATE + CLOSE).

| Bit | Hex Value | Constant Name | Description |
|-----|-----------|---------------|-------------|
| 0 | 0x00000001 | USN_REASON_DATA_OVERWRITE | Default data ($DATA) stream content overwritten |
| 1 | 0x00000002 | USN_REASON_DATA_EXTEND | Default data stream extended (appended to) |
| 2 | 0x00000004 | USN_REASON_DATA_TRUNCATION | Default data stream truncated |
| — | 0x00000008 | *(reserved)* | |
| 4 | 0x00000010 | USN_REASON_NAMED_DATA_OVERWRITE | Named data stream (ADS) overwritten |
| 5 | 0x00000020 | USN_REASON_NAMED_DATA_EXTEND | Named data stream extended |
| 6 | 0x00000040 | USN_REASON_NAMED_DATA_TRUNCATION | Named data stream truncated |
| — | 0x00000080 | *(reserved)* | |
| 8 | 0x00000100 | USN_REASON_FILE_CREATE | File or directory created |
| 9 | 0x00000200 | USN_REASON_FILE_DELETE | File or directory deleted |
| 10 | 0x00000400 | USN_REASON_EA_CHANGE | Extended attributes (EA) changed |
| 11 | 0x00000800 | USN_REASON_SECURITY_CHANGE | Security descriptor (ACL) changed |
| 12 | 0x00001000 | USN_REASON_RENAME_OLD_NAME | Old name in a rename/move operation |
| 13 | 0x00002000 | USN_REASON_RENAME_NEW_NAME | New name in a rename/move operation |
| 14 | 0x00004000 | USN_REASON_INDEXABLE_CHANGE | Content indexing attribute changed |
| 15 | 0x00008000 | USN_REASON_BASIC_INFO_CHANGE | Basic info changed (timestamps, attributes) |
| 16 | 0x00010000 | USN_REASON_HARD_LINK_CHANGE | Hard link count changed |
| 17 | 0x00020000 | USN_REASON_COMPRESSION_CHANGE | Compression state changed |
| 18 | 0x00040000 | USN_REASON_ENCRYPTION_CHANGE | EFS encryption state changed |
| 19 | 0x00080000 | USN_REASON_OBJECT_ID_CHANGE | Object ID changed |
| 20 | 0x00100000 | USN_REASON_REPARSE_POINT_CHANGE | Reparse point set or removed |
| 21 | 0x00200000 | USN_REASON_STREAM_CHANGE | Named data stream added or removed |
| 22 | 0x00400000 | USN_REASON_TRANSACTED_CHANGE | Change within a TxF transaction |
| 23 | 0x00800000 | USN_REASON_INTEGRITY_CHANGE | Data integrity attribute changed (ReFS) |
| 24 | 0x01000000 | USN_REASON_CLOSE | *(deprecated/reserved — use bit 31)* |
| — | 0x02000000–0x3FFFFFFF | *(reserved)* | |
| — | 0x40000000 | USN_REASON_ID_CHANGE | File identifier changed |
| 31 | 0x80000000 | USN_REASON_CLOSE | Handle closed; OR-ed with the final reason for this change |

### Common Reason Combinations (Forensic Signatures)

| Operation | Typical Reason Value | Flags |
|-----------|---------------------|-------|
| File created | 0x80000100 | FILE_CREATE + CLOSE |
| File deleted | 0x80000200 | FILE_DELETE + CLOSE |
| File overwritten | 0x80000001 | DATA_OVERWRITE + CLOSE |
| File appended | 0x80000002 | DATA_EXTEND + CLOSE |
| File overwritten + extended | 0x80000003 | DATA_OVERWRITE + DATA_EXTEND + CLOSE |
| Rename old name | 0x80001000 | RENAME_OLD_NAME + CLOSE |
| Rename new name | 0x80002000 | RENAME_NEW_NAME + CLOSE |
| Rename (both records) | 0x80003000 | RENAME_OLD_NAME + RENAME_NEW_NAME + CLOSE |
| Attribute change | 0x80008000 | BASIC_INFO_CHANGE + CLOSE |
| Security (ACL) change | 0x80000800 | SECURITY_CHANGE + CLOSE |
| Symlink created | 0x80100100 | FILE_CREATE + REPARSE_POINT_CHANGE + CLOSE |
| Junction created | 0x80100000 | REPARSE_POINT_CHANGE + CLOSE |
| File encrypted | 0x80040000 | ENCRYPTION_CHANGE + CLOSE |

---

## 9. USN_SOURCE_INFO Flags

The `SourceInfo` field indicates the source/origin of the change.

| Hex Value | Constant Name | Description |
|-----------|---------------|-------------|
| 0x00000001 | USN_SOURCE_DATA_MANAGEMENT | Change by OS data management (e.g., HSM, content indexing) |
| 0x00000002 | USN_SOURCE_AUXILIARY_DATA | Change by OS auxiliary data (e.g., defragmentation, replication) |
| 0x00000004 | USN_SOURCE_REPLICATION_MANAGEMENT | Change by replication management service |

When `SourceInfo != 0`, the change was made by the system rather than by user action. This helps filter out noise from background OS activities.

---

## 10. File Attributes (USN_FILE_ATTRIBUTE / WIN32_FILE_ATTRIBUTE)

The `FileAttributes` field uses the standard Win32 file attribute flags. These are the **current** attributes at the time the record was written (not a delta).

| Hex Value | Constant Name | Description |
|-----------|---------------|-------------|
| 0x00000001 | FILE_ATTRIBUTE_READONLY | Read-only |
| 0x00000002 | FILE_ATTRIBUTE_HIDDEN | Hidden |
| 0x00000004 | FILE_ATTRIBUTE_SYSTEM | System file |
| 0x00000010 | FILE_ATTRIBUTE_DIRECTORY | Directory |
| 0x00000020 | FILE_ATTRIBUTE_ARCHIVE | Archive (has been modified since last backup) |
| 0x00000040 | FILE_ATTRIBUTE_DEVICE | Device |
| 0x00000080 | FILE_ATTRIBUTE_NORMAL | Normal (no other attributes set) |
| 0x00000100 | FILE_ATTRIBUTE_TEMPORARY | Temporary |
| 0x00000200 | FILE_ATTRIBUTE_SPARSE_FILE | Sparse file |
| 0x00000400 | FILE_ATTRIBUTE_REPARSE_POINT | Reparse point (symlink, junction, etc.) |
| 0x00000800 | FILE_ATTRIBUTE_COMPRESSED | Compressed |
| 0x00001000 | FILE_ATTRIBUTE_OFFLINE | Offline (HSM migrated) |
| 0x00002000 | FILE_ATTRIBUTE_NOT_CONTENT_INDEXED | Not content indexed |
| 0x00004000 | FILE_ATTRIBUTE_ENCRYPTED | Encrypted (EFS) |
| 0x00008000 | FILE_ATTRIBUTE_INTEGRITY_STREAM | Integrity stream (ReFS) |
| 0x00020000 | FILE_ATTRIBUTE_VIRTUAL | Virtual |
| 0x00040000 | FILE_ATTRIBUTE_NO_SCRUB_DATA | No scrub data |
| 0x00100000 | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS | Recall on data access |
| 0x00400000 | FILE_ATTRIBUTE_RECALL_ON_OPEN | Recall on open |
| 0x02000000 | FILE_ATTRIBUTE_STRICTLY_SEQUENTIAL | Strictly sequential |

**Key forensic indicators**:
- `0x10` (DIRECTORY): Record refers to a directory, not a file
- `0x400` (REPARSE_POINT): Symlink, junction, or mount point
- `0x4000` (ENCRYPTED): EFS-encrypted file
- `0x200` (SPARSE_FILE): Sparse file (often $J itself)

---

## 11. Detecting Deleted Files

### Method 1: USN_REASON_FILE_DELETE flag

The most reliable method. Check if the `Reason` field has bit 9 set:

```python
is_delete = (reason & 0x00000200) != 0
```

A file deletion produces a record with `Reason = 0x80000200` (FILE_DELETE + CLOSE).

### Method 2: Rename to $RECYCLE.BIN

When a file is moved to Recycle Bin (Explorer delete), the journal shows:
1. A record with `RENAME_OLD_NAME` (original name + path)
2. A record with `RENAME_NEW_NAME` (name within `$RECYCLE.BIN\$Rxxxxxxx.ext`)

**Note**: Shift+Delete produces a `FILE_DELETE` record directly, NOT rename records.

### Method 3: MFT Sequence Number Mismatch

After a file is deleted and the MFT entry is reused, the **sequence number** in the MFT entry increments. If the sequence number in the USN record's FileReferenceNumber doesn't match the current MFT entry's sequence number, the file referenced by this USN record has been deleted and the MFT entry may have been reused.

```python
# USN record's file ref
usn_mft_index = file_ref & 0xFFFFFFFFFFFF
usn_seq_num = (file_ref >> 48) & 0xFFFF

# Current MFT entry
mft_seq_num = read_mft_sequence_number(usn_mft_index)

if usn_seq_num != mft_seq_num:
    # File was deleted; MFT entry may be reused by a different file
    # The USN record's filename is stale/historical
    pass
```

### Method 4: MFT In-Use Flag

Read the MFT entry at the record's MFT index and check if the "in-use" flag is clear (bit 0 of the MFT record header flags). If the entry is not in use, the file has been deleted.

---

## 12. Cross-Referencing USN Records with MFT

### Direct MFT Lookup (V2 / V4)

```python
file_ref = record.FileReferenceNumber  # uint64
mft_entry_number = file_ref & 0xFFFFFFFFFFFF  # lower 48 bits
sequence_number = (file_ref >> 48) & 0xFFFF    # upper 16 bits

# Read MFT entry at that offset
mft_offset = mft_entry_number * mft_record_size  # typically 1024 bytes
mft_record = read_at_offset(mft_file, mft_offset, mft_record_size)
```

### $STANDARD_INFORMATION ↔ USN Link

Each MFT entry's `$STANDARD_INFORMATION` attribute contains:
- **LastUsn** at offset `$SI + 0x40` (8 bytes): The USN of the most recent journal record for this file
- **UsnJournalId** at offset `$SI + 0x48` (8 bytes): Matches the journal's UsnJournalID from $Max

This allows bidirectional lookup:
- **USN → MFT**: Use FileReferenceNumber to find the MFT entry
- **MFT → USN**: Use LastUsn from $SI to find the most recent USN record for a file

### Important Caveats

1. **Sequence number mismatch**: If the MFT entry's sequence number doesn't match the USN record's, the MFT entry has been reused by a different file. The USN record is historical.
2. **Journal wrap**: The USN value may refer to a record that has been overwritten in the circular journal. Check if `Usn < FirstUsn` (from $Max) — if so, the record is gone.
3. **V4 records**: Don't have filenames; must follow up with the companion V2/V3 record.
4. **Parent directory**: The ParentFileReferenceNumber can be used to reconstruct full paths by walking up the directory tree through MFT.

---

## 13. Example Parsing Logic (Python)

```python
import struct
from datetime import datetime, timezone, timedelta

# Windows FILETIME epoch: Jan 1, 1601
FILETIME_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)

def filetime_to_datetime(ft):
    """Convert 100ns ticks since 1601-01-01 to Python datetime."""
    return FILETIME_EPOCH + timedelta(microseconds=ft // 10)

def parse_file_reference_v2(file_ref):
    """Decompose a 64-bit V2 file reference number."""
    mft_index = file_ref & 0xFFFFFFFFFFFF
    seq_number = (file_ref >> 48) & 0xFFFF
    return mft_index, seq_number

def parse_usn_record(data, offset):
    """Parse a USN record at the given offset. Returns (record_dict, bytes_consumed)."""
    if len(data) - offset < 8:
        return None, 0

    record_length = struct.unpack_from('<I', data, offset)[0]
    if record_length == 0:
        return None, 8  # skip padding

    major_version = struct.unpack_from('<H', data, offset + 4)[0]
    minor_version = struct.unpack_from('<H', data, offset + 6)[0]

    record = {
        'record_length': record_length,
        'major_version': major_version,
        'minor_version': minor_version,
    }

    if major_version == 2:
        # V2: 64-bit file references
        record['file_reference_number'] = struct.unpack_from('<Q', data, offset + 0x08)[0]
        record['parent_file_reference_number'] = struct.unpack_from('<Q', data, offset + 0x10)[0]
        record['usn'] = struct.unpack_from('<q', data, offset + 0x18)[0]
        record['timestamp'] = filetime_to_datetime(struct.unpack_from('<Q', data, offset + 0x20)[0])
        record['reason'] = struct.unpack_from('<I', data, offset + 0x28)[0]
        record['source_info'] = struct.unpack_from('<I', data, offset + 0x2C)[0]
        record['security_id'] = struct.unpack_from('<I', data, offset + 0x30)[0]
        record['file_attributes'] = struct.unpack_from('<I', data, offset + 0x34)[0]
        filename_length = struct.unpack_from('<H', data, offset + 0x38)[0]
        filename_offset = struct.unpack_from('<H', data, offset + 0x3A)[0]

        fn_bytes = data[offset + filename_offset : offset + filename_offset + filename_length]
        record['filename'] = fn_bytes.decode('utf-16-le', errors='replace').rstrip('\x00')

        record['mft_entry'], record['sequence_number'] = \
            parse_file_reference_v2(record['file_reference_number'])
        record['parent_mft_entry'], record['parent_sequence_number'] = \
            parse_file_reference_v2(record['parent_file_reference_number'])

    elif major_version == 3:
        # V3: 128-bit file references
        record['file_reference_number'] = data[offset + 0x08 : offset + 0x18]
        record['parent_file_reference_number'] = data[offset + 0x18 : offset + 0x28]
        record['usn'] = struct.unpack_from('<q', data, offset + 0x28)[0]
        record['timestamp'] = filetime_to_datetime(struct.unpack_from('<Q', data, offset + 0x30)[0])
        record['reason'] = struct.unpack_from('<I', data, offset + 0x38)[0]
        record['source_info'] = struct.unpack_from('<I', data, offset + 0x3C)[0]
        record['security_id'] = struct.unpack_from('<I', data, offset + 0x40)[0]
        record['file_attributes'] = struct.unpack_from('<I', data, offset + 0x44)[0]
        filename_length = struct.unpack_from('<H', data, offset + 0x48)[0]
        filename_offset = struct.unpack_from('<H', data, offset + 0x4A)[0]

        fn_bytes = data[offset + filename_offset : offset + filename_offset + filename_length]
        record['filename'] = fn_bytes.decode('utf-16-le', errors='replace').rstrip('\x00')

        # On NTFS, the 128-bit ref is effectively 64-bit in lower bytes
        if record['file_reference_number'][8:] == b'\x00' * 8:
            low64 = struct.unpack_from('<Q', record['file_reference_number'], 0)[0]
            record['mft_entry'], record['sequence_number'] = \
                parse_file_reference_v2(low64)

    elif major_version == 4:
        # V4: extent/range-tracking record
        record['file_reference_number'] = struct.unpack_from('<Q', data, offset + 0x08)[0]
        record['parent_file_reference_number'] = struct.unpack_from('<Q', data, offset + 0x10)[0]
        record['usn'] = struct.unpack_from('<q', data, offset + 0x18)[0]
        record['reason'] = struct.unpack_from('<I', data, offset + 0x20)[0]
        record['source_info'] = struct.unpack_from('<I', data, offset + 0x24)[0]
        record['remaining_extents'] = struct.unpack_from('<I', data, offset + 0x28)[0]
        record['number_of_extents'] = struct.unpack_from('<I', data, offset + 0x2C)[0]

        extents = []
        for i in range(record['number_of_extents']):
            ext_offset = offset + 0x30 + i * 16
            ext_start = struct.unpack_from('<Q', data, ext_offset)[0]
            ext_length = struct.unpack_from('<Q', data, ext_offset + 8)[0]
            extents.append({'offset': ext_start, 'length': ext_length})
        record['extents'] = extents

        record['mft_entry'], record['sequence_number'] = \
            parse_file_reference_v2(record['file_reference_number'])
        record['filename'] = None  # V4 has no filename; look at companion V2/V3 record

    record['is_delete'] = (record.get('reason', 0) & 0x00000200) != 0
    record['is_create'] = (record.get('reason', 0) & 0x00000100) != 0
    record['is_close'] = (record.get('reason', 0) & 0x80000000) != 0

    return record, record_length

def iterate_usn_journal(j_data):
    """Iterate all USN records from the raw $J stream bytes."""
    offset = 0
    while offset < len(j_data):
        record, consumed = parse_usn_record(j_data, offset)
        if consumed == 0:
            break
        if record is not None:
            yield record
        offset += consumed
        # Align to 8-byte boundary
        offset = (offset + 7) & ~7
```

---

## 14. Summary of Key Differences

| Feature | V2 | V3 | V4 |
|---------|----|----|-----|
| **File ref size** | 64-bit | 128-bit | 64-bit |
| **Has filename?** | Yes | Yes | **No** |
| **Has timestamp?** | Yes | Yes | **No** |
| **Has SecurityId?** | Yes | Yes | **No** |
| **Has FileAttributes?** | Yes | Yes | **No** |
| **Has extents?** | No | No | **Yes** |
| **Fixed header** | 0x3C (60) | 0x4C (76) | 0x30 (48) |
| **Used on** | NTFS | NTFS + ReFS | NTFS only |
| **Windows version** | 2000+ | 8+ | 10+ |
| **Trigger** | All changes | All changes | Range tracking enabled + large files |

---

## 15. Practical Notes for Parser Implementation

1. **8-byte alignment**: All record lengths are padded to 8-byte boundaries. When advancing between records, use `(record_length + 7) & ~7` or simply trust `RecordLength` (which is already aligned).

2. **Sparse regions**: The `$J` stream is sparse. When reading raw bytes, regions of all-zero bytes indicate journal wrap (old records zeroed out). Detect these by checking if `RecordLength == 0`.

3. **Record length calculation**: `RecordLength = pad8(FixedHeaderSize + FileNameLength)`. For V2: `pad8(0x3C + FileNameLength)`. For V3: `pad8(0x4C + FileNameLength)`.

4. **USN as offset**: The `Usn` field in each record is its virtual byte offset in the journal. This is **not** a sequential counter — it's a byte position. Two consecutive records may have USNs that differ by more than the first record's length (if intervening records were in the sparse/zeroed region).

5. **Minimum record size**: The NTFS driver enforces a minimum record size of 80 bytes (0x50) for V2/V3 records. This accounts for the fixed header plus a minimum filename length.

6. **Filename encoding**: Filenames are UTF-16LE, **not** null-terminated in the length-counted portion. The `FileNameLength` field gives the exact byte count. There may be null padding bytes between the filename end and the record end (to reach 8-byte alignment).

7. **Version detection**: Always read `MajorVersion` at offset 0x04 to determine which layout to use. A well-formed parser should handle V2, V3, and V4.

8. **V4 companion records**: When you encounter a V4 record, the **next** record in the stream should be a V2 or V3 record with the same `Usn` value, containing the filename and metadata for the same change event.

9. **Journal wrap detection**: Compare each record's `Usn` against the `FirstUsn` and `NextUsn` from the `$Max` stream. If `Usn < FirstUsn`, the record is in the wrapped/invalid region.

10. **$J raw access**: To read the raw `$J` stream outside of the Windows API, you need to:
    - Open the volume handle (e.g., `\\.\C:`)
    - Parse the MFT to find the `$UsnJrnl` entry
    - Read the non-resident $DATA attribute named `$J`
    - Or use `FSCTL_ENUM_USN_DATA` which returns records starting from a given USN

---

## References

- [Microsoft USN_RECORD_V2 (winioctl.h)](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ns-winioctl-usn_record_v2)
- [Microsoft USN_RECORD_V3 (ntifs.h)](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-usn_record_v3)
- [Microsoft USN_RECORD_V4 (winioctl.h)](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ns-winioctl-usn_record_v4)
- [Microsoft Change Journal Records](https://learn.microsoft.com/en-us/windows/win32/fileio/change-journal-records)
- [libyal NTFS Specification](https://github.com/libyal/libfsntfs/blob/master/documentation/New%20Technologies%20File%20System%20(NTFS).asciidoc)
- [forefst ReFS Reference — USN Journal](https://xbpt.gitlab.io/forefst/structures/usn_journal/)
- [artefacts.help — NTFS UsnJrnl](https://artefacts.help/windows_usnjrnl.html)
- [NTFS Documentation (flatcap)](https://flatcap.github.io/linux-ntfs/ntfs/concepts/file_record.html)
