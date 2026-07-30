# Data Recovery Engine Architecture — Technical Research Document

## Table of Contents
1. [Internal Architecture of Data Recovery Software](#1-internal-architecture-of-data-recovery-software)
2. [NTFS Parser Design](#2-ntfs-parser-design)
3. [APFS Parser Design](#3-apfs-parser-design)
4. [EXT4 Parser Design](#4-ext4-parser-design)
5. [FAT/exFAT Parser Design](#5-fatexfat-parser-design)
6. [File Carving / Signature Scanning](#6-file-carving--signature-scanning)
7. [Filesystem Reconstruction](#7-filesystem-reconstruction)
8. [Raw Disk Reading](#8-raw-disk-reading)

---

## 1. Internal Architecture of Data Recovery Software

### 1.1 Core Modules

Professional data recovery tools (R-Studio, DMDE, UFS Explorer, DiskDrill) share a common architectural pattern composed of several layered modules:

```
┌─────────────────────────────────────────────────────┐
│                   UI / Presentation Layer            │
│  (File tree, hex viewer, scan progress, recovery)   │
├─────────────────────────────────────────────────────┤
│              Filesystem Reconstruction Engine        │
│  (Virtual FS builder, directory tree, metadata)     │
├────────────┬────────────┬────────────┬──────────────┤
│  NTFS      │  APFS      │  EXT4      │  FAT/exFAT   │
│  Parser    │  Parser    │  Parser    │  Parser      │
├────────────┴────────────┴────────────┴──────────────┤
│              File Carving / Signature Scanner        │
│  (Magic number detection, structure parsing,        │
│   fragmented reassembly)                            │
├─────────────────────────────────────────────────────┤
│              RAID / Volume Assembly Layer            │
│  (Virtual RAID, stripe detection, parity calc)      │
├─────────────────────────────────────────────────────┤
│              Partition / Volume Detection            │
│  (MBR, GPT, APM, BSD label, LVM, dynamic disks)    │
├─────────────────────────────────────────────────────┤
│              Raw Disk I/O Layer                      │
│  (ATA/SCSI commands, device access, error handling) │
└─────────────────────────────────────────────────────┘
```

### 1.2 Internal Flow: Raw Disk Read → File Recovery

The typical recovery pipeline proceeds as follows:

1. **Device Discovery & Enumeration**: The I/O layer enumerates available storage devices using OS APIs (Windows: `CreateFile` with `\\.\PhysicalDriveN`; Linux: `/dev/sdX`; macOS: `/dev/diskN`). USB drives attached via USB-bridge controllers are handled differently from direct SATA/PCIe devices.

2. **Disk Imaging (Optional but Recommended)**: Before any logical analysis, a sector-by-sector image is created. Professional tools use adaptive reading strategies (see §8).

3. **Partition Table Scan**: The tool scans for partition structures — MBR (at LBA 0), GPT (LBA 1 for header, LBA 2-33 for entries), APM, BSD disklabels, LVM2 PV headers, Windows dynamic disk LDM databases. If partition tables are corrupted, the tool performs a **surface scan** looking for filesystem signatures at sector boundaries.

4. **Filesystem Detection**: For each partition/volume found, the tool identifies the filesystem type by examining the boot sector / superblock / NX superblock. If the volume header is missing, the tool may attempt to detect the filesystem type by scanning for characteristic on-disk structures (e.g., MFT signatures "FILE" for NTFS, superblock magic 0xEF53 for EXT4).

5. **Filesystem Parsing**: The filesystem-specific parser reads metadata structures (MFT, catalog file, inode table, FAT, etc.) and builds an in-memory representation of the directory tree and file metadata.

6. **Deleted File Detection**: The parser checks for files marked as deleted in the filesystem metadata. For NTFS, this means MFT entries with the "in-use" flag cleared. For EXT4, it means inodes with a link count of 0 and deleted directory entries. For FAT, it means directory entries with 0xE5 as the first byte.

7. **Filesystem Reconstruction**: For damaged filesystems, the tool attempts to reconstruct the directory tree using heuristics, journal data, and secondary metadata sources (see §7).

8. **File Carving (Fallback)**: If filesystem metadata is completely unavailable, the tool falls back to signature-based carving to recover files by content (see §6).

9. **File Assembly & Recovery**: For each file to be recovered, the tool resolves the cluster/extent chain, reads the data blocks, and writes them to the output destination. For fragmented files, the tool must correctly reassemble the fragments.

### 1.3 Tool-Specific Notes

- **R-Studio**: Known for its very fast scan speed and strong filesystem reconstruction. Supports a wide range of filesystems. Has advanced RAID reconstruction with automatic parameter detection. Uses a multi-pass scan approach: first a quick scan for existing metadata, then a deep scan for carving.

- **DMDE**: Lightweight but extremely powerful. Known for its virtual filesystem reconstruction that can handle severely damaged filesystems. Uses a unique "FS fragments" approach where it identifies fragments of filesystem metadata scattered across the disk and merges them. Its INDX processing for NTFS is particularly sophisticated — it can reconstruct directory structure from INDX attributes even when MFT entries are damaged.

- **UFS Explorer**: Known for its support of exotic filesystems and RAID configurations. Has specialized recovery algorithms for different storage types (NAS, RAID, etc.). Uses a "storage reconstruction" approach.

- **DiskDrill**: More consumer-oriented but uses similar underlying technology. Focuses on ease of use with its "Recovery Vault" (which pre-records metadata for future recovery) and "Guaranteed Recovery" features.

---

## 2. NTFS Parser Design

### 2.1 Core NTFS On-Disk Structures

NTFS (New Technology File System) is the primary filesystem for Windows. Its core concept is: **everything is (or is stored in) a file.** There is no separate metadata plane like inodes in UNIX — instead, the Master File Table (MFT) serves as the central metadata structure.

#### 2.1.1 The Boot Sector ($Boot)

Located at the first sector of the volume. Contains:
- OEM ID ("NTFS    ")
- Bytes per sector (typically 512 or 4096)
- Sectors per cluster (power of 2)
- MFT cluster number (byte offset to the start of $MFT)
- MFT mirror cluster number
- Size of MFT entries (typically 1024 bytes, stored as a signed exponent: -10 means 2^10 = 1024)
- Clusters per index record (typically 4096 bytes)

#### 2.1.2 The Master File Table ($MFT)

The MFT is a sequence of 1024-byte entries (by default). Each entry describes one file or directory. The first 16-24 entries are reserved for system files:

| Entry | File | Purpose |
|-------|------|---------|
| 0 | $MFT | The MFT itself (self-referencing) |
| 1 | $MFTMirr | Mirror copy of first 4 MFT entries |
| 2 | $LogFile | Journal for transaction safety |
| 3 | $Volume | Volume information (label, flags, serial) |
| 4 | $AttrDef | Attribute definitions |
| 5 | . (root) | Root directory |
| 6 | $Bitmap | Cluster allocation bitmap |
| 7 | $Boot | Boot sector |
| 8 | $BadClus | Bad cluster list |
| 9 | $Secure | Security descriptors |
| 10 | $UpCase | Uppercase character table |
| 11 | $Extend | Extended metadata directory |
| 12-15 | Reserved | Reserved for future use |
| 16-23 | System | Additional system files |

#### 2.1.3 MFT Entry Structure

Each MFT entry has this structure:

```
┌────────────────────────────────┐
│ MFT Entry Header (42+ bytes)   │
│  - Signature: "FILE" or "BAAD" │
│  - Fixup offset & count        │
│  - Sequence number             │
│  - Hard link count             │
│  - Offset to first attribute   │
│  - Flags (in-use, directory)   │
│  - Used size / Allocated size  │
├────────────────────────────────┤
│ Fixup Array                    │
│  (2-byte signature + original  │
│   last-2-bytes of each sector) │
├────────────────────────────────┤
│ Attribute 1 (header + content) │
├────────────────────────────────┤
│ Attribute 2 (header + content) │
├────────────────────────────────┤
│ ...                            │
├────────────────────────────────┤
│ 0xFFFFFFFF (end marker)        │
├────────────────────────────────┤
│ Unused space                   │
└────────────────────────────────┘
```

**Fixup Arrays**: NTFS uses fixup arrays as a form of integrity checking. For each sector in the MFT entry, the last 2 bytes are replaced with a 2-byte signature. The original values are stored in the fixup array. When parsing, you must first undo the fixup to get the correct data. If the signature doesn't match at the end of a sector, the sector is likely corrupted.

#### 2.1.4 Attribute Types

Each MFT entry contains a sequence of attributes. Common attribute types:

| Type ID | Name | Description |
|---------|------|-------------|
| 0x10 | $STANDARD_INFORMATION | File timestamps, permissions, attributes |
| 0x20 | $ATTRIBUTE_LIST | For files needing multiple MFT entries |
| 0x30 | $FILE_NAME | File name, parent directory ref, timestamps, sizes |
| 0x40 | $OBJECT_ID | Unique object identifier |
| 0x50 | $SECURITY_DESCRIPTOR | Security/ACL data |
| 0x60 | $VOLUME_NAME | Volume name |
| 0x70 | $VOLUME_INFORMATION | Volume version and flags |
| 0x80 | $DATA | File data content |
| 0x90 | $INDEX_ROOT | Directory index root |
| 0xA0 | $INDEX_ALLOCATION | Directory index blocks (INDX) |
| 0xB0 | $BITMAP | Allocation bitmap for index |
| 0xC0 | $REPARSE_POINT | Symbolic link / mount point target |
| 0x100 | $LOGGED_UTILITY_STREAM | EFS encrypted data |

#### 2.1.5 Resident vs. Non-Resident Attributes

- **Resident attributes**: The attribute content is stored directly within the MFT entry. Small files (typically under ~700 bytes) can have their entire $DATA attribute stored as resident, meaning the file content is inside the MFT entry itself.

- **Non-resident attributes**: The attribute content is stored in clusters elsewhere on disk. The MFT entry contains a **runlist** (data runs) that describes which clusters hold the data.

**Attribute Header Format** (first 16 bytes common to both):
```
Offset  Size  Field
0       4     Attribute type (e.g., 0x80 for $DATA)
4       4     Total length of attribute
8       1     Non-resident flag (0=resident, 1=non-resident)
9       1     Name length
10      2     Offset to name
12      2     Flags (compressed, encrypted, sparse)
14      2     Attribute ID
```

**Resident header** (additional bytes 16-23):
```
16      4     Length of attribute content
20      2     Offset to attribute content
22      1     Indexed flag
23      1     Padding
```

**Non-resident header** (additional bytes 16-63):
```
16      8     Starting VCN
24      8     Ending VCN
32      2     Offset to data runs
34      2     Compression unit size
40      8     Allocated size
48      8     Actual size
56      8     Initialized size
```

#### 2.1.6 Data Runs (Runlists)

Data runs encode the cluster allocation for non-resident attributes. The format is:

1. A header byte where the **low nibble** = number of bytes for the run length, and the **high nibble** = number of bytes for the run offset.
2. The run length bytes (unsigned, little-endian).
3. The run offset bytes (signed, little-endian, relative to the previous run's starting cluster).

**Example**: Runlist bytes `11 05 30 21 02 A4 03 21 04 64 FC`

- `11`: 1-byte length, 1-byte offset
- `05`: Run length = 5 clusters
- `30`: Offset = 0x30 = 48 (absolute, first run) → clusters 48-52

- `21`: 2-byte length, 1-byte offset
- `02`: Run length = 2 clusters
- `A4 03`: Offset = 0x03A4 = 932 (signed, relative to previous) → 48 + 932 = 980 → clusters 980-981

- `21`: 2-byte length, 1-byte offset
- `04`: Run length = 4 clusters
- `64 FC`: Offset = 0xFC64 as signed 16-bit = -924 (relative) → 980 + (-924) = 56 → clusters 56-59

The runlist is terminated by a `0x00` byte.

### 2.2 NTFS Recovery Specifics

#### 2.2.1 Deleted File Detection

When a file is deleted on NTFS:
1. The "in-use" bit in the MFT entry header is cleared.
2. The $STANDARD_INFORMATION and $FILE_NAME attributes may be preserved.
3. The $DATA attribute's runlist may be preserved (if the MFT entry is not reused).
4. The clusters referenced by the runlist are marked as free in $Bitmap.

**Key insight**: Unlike FAT, NTFS does not immediately zero out the MFT entry's data runs when a file is deleted. The runlist is preserved until the MFT entry is overwritten or the clusters are reused. This makes NTFS recovery highly reliable for recently deleted files.

#### 2.2.2 $MFT Mirror

$MFTMirr (MFT entry 1) contains a copy of the first 4 MFT entries ($MFT, $MFTMirr, $LogFile, $Volume). If the beginning of the MFT is corrupted, the mirror can be used to recover these critical entries. However, the mirror is only updated periodically, so it may be slightly stale.

#### 2.2.3 $LogFile (Journal)

The NTFS $LogFile is a circular journal that records all filesystem transactions. It contains:
- **Restart area**: Contains checkpoint information for mount/umount state.
- **Log records**: Record operations like creating files, extending attributes, updating directory indices.

Recovery tools can parse $LogFile to:
- Find recent file operations that may not yet be reflected in the on-disk MFT.
- Recover information about recently deleted files.
- Determine the last consistent filesystem state.

DMDE specifically supports "process FS journal" option to include $LogFile information in reconstruction.

#### 2.2.4 INDX Attributes (Directory Indexing)

NTFS directories are implemented as B-trees. When a directory is large enough, it uses:
- **$INDEX_ROOT** (always resident): The root of the B-tree.
- **$INDEX_ALLOCATION** (non-resident): Contains the index blocks (INDX records).
- **$BITMAP**: Tracks which index blocks are in use.

INDX records contain file references (MFT number + sequence number) and file name information. When a file is deleted, the INDX entry may be marked as deleted but the entry is often preserved in the index leaf until the B-tree is rebalanced.

**Recovery use**: Even when MFT entries are damaged, INDX records can be used to reconstruct directory structure. DMDE's "auto INDX processing" and "full INDX processing" features leverage this.

#### 2.2.5 Handling Corrupted MFT

Recovery strategies for corrupted MFT:

1. **MFT scan**: Scan the entire disk for MFT entry signatures ("FILE" / 0x46494C45). Each valid MFT entry has a known structure that can be validated.

2. **Sequential MFT enumeration**: Start from the MFT start offset (found in $Boot) and read entries sequentially. If an entry is corrupted (signature "BAAD"), skip it and continue.

3. **$MFTMirr recovery**: Use the mirror to recover the first 4 critical entries.

4. **INDX-based reconstruction**: Parse all INDX records to find file references, then attempt to locate the corresponding MFT entries.

5. **$LogFile analysis**: Parse the journal to find recent file operations and MFT entry changes.

6. **Attribute list traversal**: For files with $ATTRIBUTE_LIST, follow the attribute list to find all MFT entries that belong to the same file.

7. **Shifted MFT records**: After a volume resize or corruption, MFT records may be shifted from their expected positions. DMDE's "Include Shifted" option handles this.

8. **File carving as last resort**: If MFT is completely destroyed, fall back to signature-based carving.

### 2.3 Common NTFS Failure Modes

| Failure Mode | Cause | Recovery Approach |
|---|---|---|
| MFT entry corruption | Bad sectors, crash during write | MFT scan, $MFTMirr, INDX recovery |
| MFT header corruption | Boot sector damage | Backup boot sector, GPT partition recovery |
| $Bitmap corruption | Crash, malware | Scan all MFT entries to rebuild bitmap |
| Runlist corruption | Bad sectors in MFT entry | Partial runlist + file carving for remainder |
| Directory index corruption | B-tree damage | INDX scan, $LogFile analysis |
| Partition table loss | Accidental format, malware | Surface scan for $Boot or MFT signatures |
| Encrypted files (EFS) | Lost certificate | Usually unrecoverable without key backup |

---

## 3. APFS Parser Design

### 3.1 APFS Architecture Overview

APFS (Apple File System) is a fundamentally different design from HFS+. Key differences:
- **Copy-on-Write (CoW)**: All changes are written to new blocks, never overwriting in place. This makes APFS especially flash-friendly but complicates recovery.
- **Container-based**: APFS uses a container model where a single container can hold multiple volumes.
- **B-tree based**: Most metadata is stored in B-trees with a specific structure (b-tree nodes with btrailer).
- **Encryption**: Native encryption support with per-volume or per-file encryption.
- **Snapshots**: Built-in support for point-in-time snapshots.

### 3.2 On-Disk Structure

```
┌─────────────────────────────────────────────────┐
│              APFS Container                      │
│  ┌───────────────────────────────────────────┐  │
│  │  NX Superblock (Container Superblock)      │  │
│  │  - Magic: 0x4253584E ("NXSB")              │  │
│  │  - Block size, block count                 │  │
│  │  - Pointers to: Object Map, B-tree         │  │
│  │  - Volume superblock offsets               │  │
│  ├───────────────────────────────────────────┤  │
│  │  Object Map (OMAP)                         │  │
│  │  - Maps virtual OIDs to physical blocks    │  │
│  │  - Enables CoW: new versions get new OIDs  │  │
│  ├───────────────────────────────────────────┤  │
│  │  Volume Superblock (APSBSuperblock)        │  │
│  │  - Magic: 0x41504653 ("APFS")              │  │
│  │  - Root file system tree OID               │  │
│  │  - Extent reference tree OID               │  │
│  │  - Snapshot metadata tree OID              │  │
│  │  - Encryption state                        │  │
│  ├───────────────────────────────────────────┤  │
│  │  B-Tree (File/Folder Tree)                 │  │
│  │  - Directory structure as B-tree nodes      │  │
│  │  - Each node has btrailer (checksum)       │  │
│  │  - Leaf nodes contain file/folder records  │  │
│  ├───────────────────────────────────────────┤  │
│  │  Extent Reference Tree                     │  │
│  │  - Maps file IDs to physical extent info   │  │
│  │  - Separate from file/folder B-tree        │  │
│  │  - Contains physical block references      │  │
│  ├───────────────────────────────────────────┤  │
│  │  Snapshots Metadata Tree                   │  │
│  │  - Point-in-time snapshots of volumes      │  │
│  │  - References to previous tree versions    │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### 3.3 Key APFS Structures

#### 3.3.1 NX Superblock (Container Superblock)
- **Magic**: 0x4253584E ("NXSB")
- Contains the block size, total block count, and features flags.
- Points to the Object Map (OMAP) which maps virtual object IDs (OIDs) to physical block addresses.
- Contains an array of volume superblock physical OIDs.
- Includes a checkpoint area for CoW consistency.

#### 3.3.2 Object Map (OMAP)
The OMAP is crucial for APFS's CoW mechanism. It maps virtual OIDs to physical block numbers. When a block is modified:
1. A new block is allocated at a new physical location.
2. The OMAP is updated to map the virtual OID to the new physical block.
3. The old physical block becomes a free block (or is retained by a snapshot).

For recovery, the OMAP history can be used to find previous versions of metadata blocks.

#### 3.3.3 B-Tree Nodes
APFS B-trees have a specific structure:
- **Node header**: Contains the node type (leaf, index, root), level, and key/count information.
- **Keys and values**: Stored in a table-of-contents layout.
- **btrailer**: Every B-tree node has a trailing structure (btrailer) that contains:
  - A checksum (Fletcher-64) for integrity verification.
  - The node's object identifier.
  - The transaction ID when the node was written.

For recovery, the btrailer checksum is used to validate nodes. The transaction ID helps determine the chronological order of nodes.

#### 3.3.4 Extent References
Unlike HFS+ where the catalog file contains extent information, APFS stores extent references in a separate B-tree. Each extent reference contains:
- The file's virtual OID.
- The logical offset within the file.
- The physical block number and length.
- Reference count (for CoW clones).

**Recovery implication**: To recover a file, you must first find it in the file/folder B-tree, then look up its extents in the extent reference tree. This two-step process is more complex than HFS+.

#### 3.3.5 APFS Snapshots
Snapshots are point-in-time copies of the volume's metadata. They work by:
1. Creating a new volume superblock that references the same OMAP.
2. The OMAP preserves the old virtual-to-physical mappings.
3. New writes go to new blocks, while old blocks are preserved by the snapshot.

Recovery tools can use snapshots to recover previous file versions, even if the files were deleted from the live volume.

### 3.4 What Makes APFS Recovery Harder Than HFS+

| Factor | HFS+ | APFS |
|--------|------|------|
| **Encryption** | Optional FileVault 2 (whole-disk) | Native per-file or per-volume encryption |
| **Metadata location** | Catalog file (single B-tree) | Multiple B-trees (file tree, extent tree, snapshot tree) |
| **Block mapping** | Direct extent records in catalog | Indirect via OMAP + extent reference tree |
| **CoW** | No (overwrites in place) | Yes (writes to new blocks) |
| **Deletion** | Catalog node removed, extent freed | B-tree nodes replaced, old blocks may be retained by snapshots or freed |
| **Checksums** | Limited | Fletcher-64 on every B-tree node |
| **TRIM support** | Basic | Aggressive (immediately frees blocks) |
| **Documentation** | Well-documented | Official spec under NDA, partially reverse-engineered |

**Encryption challenges**: APFS encryption is deeply integrated. Volumes can be encrypted with different keys. Even if the container superblock is found, the encryption keys may be protected by the user's passphrase or hardware SEP (Secure Enclave Processor). Without the key, data is unrecoverable.

**TRIM/UNMAP**: APFS aggressively sends TRIM commands to SSDs, which causes the SSD controller to erase freed blocks. This makes recovery of deleted files much harder on SSDs compared to HDDs.

**CoW complexity**: Because APFS writes new blocks for every change, the on-disk state contains many old versions of metadata. Recovery tools must parse the OMAP to determine which version is current, and they can potentially access old versions through snapshot references.

### 3.5 APFS Recovery Strategies

1. **NX Superblock scan**: Search for the NXSB magic number (0x4253584E) to locate the container superblock.
2. **OMAP traversal**: Parse the OMAP to map virtual OIDs to physical blocks.
3. **B-tree validation**: Verify each B-tree node using its btrailer checksum.
4. **Extent tree reconstruction**: If the extent reference tree is damaged, scan for extent reference records.
5. **Snapshot recovery**: Check for snapshot metadata trees that reference previous versions of the volume.
6. **Block-level carving**: If all metadata is lost, fall back to file carving on the raw block device.

---

## 4. EXT4 Parser Design

### 4.1 EXT4 On-Disk Layout

An EXT4 filesystem is divided into **block groups**. Each block group is a self-contained unit:

```
┌──────────────────────────────────────────────────────────────┐
│ Block Group 0                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  Superblock   │  │  Group Desc  │  │  Data Block  │  ...  │
│  │  (primary)    │  │  Table       │  │  Bitmap      │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  Inode Bitmap │  │  Inode Table │  │  Data Blocks │  ...  │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
├──────────────────────────────────────────────────────────────┤
│ Block Group 1                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  Superblock   │  │  Group Desc  │  │  ...          │  ... │
│  │  (backup)     │  │  Table       │  │              │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
├──────────────────────────────────────────────────────────────┤
│ ...                                                           │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 Key Structures

#### 4.2.1 Superblock

The superblock contains critical filesystem parameters:
- **Magic number**: 0xEF53 (at offset 0x38)
- **Block size**: Stored as log2(size) - 10 (so 0 = 1024, 1 = 2048, 2 = 4096)
- **Block count**: Total number of blocks
- **Inode count**: Total number of inodes
- **Blocks per group**: Typically 8 * block_size (32768 for 4KB blocks)
- **Inodes per group**: Number of inodes per block group
- **Feature flags**: Compatible, incompatible, and read-only feature flags
- **Journal inode**: Inode number of the journal (usually 8)
- **Journal backup**: Superblock may contain journal info

Backup superblocks are stored at the beginning of block groups 1, 5, 7, 9, 25, 27, 49, etc. (powers of 3, 5, 7 times the block group size).

#### 4.2.2 Block Group Descriptors

Each block group has a descriptor (32 or 64 bytes) containing:
- Block bitmap location
- Inode bitmap location
- Inode table location
- Free block count
- Free inode count
- Used directory count

The group descriptor table is stored immediately after the superblock. With the 64-bit feature, the descriptor size expands to 64 bytes.

#### 4.2.3 Inode Table

Each block group contains an inode table. Each inode is typically 256 bytes (can be larger) and contains:
- **File mode**: Type and permissions
- **Owner UID/GID**
- **Size**: File size in bytes
- **Timestamps**: Access, modification, change, deletion (if available)
- **Link count**: Number of hard links (0 = deleted)
- **Blocks count**: Number of 512-byte blocks allocated
- **Flags**: Various flags including extent flag, inline data flag
- **Extent tree root** or **block pointers**: Location of file data

#### 4.2.4 Extent Trees

EXT4 uses extent trees (instead of the direct/indirect block pointers of EXT2/3) to map file data:

```
Extent Tree:
┌─────────────────────────┐
│  Root Node (in inode)    │
│  ┌─────────────────────┐│
│  │  Extent Header       ││
│  │  - depth, entries    ││
│  ├─────────────────────┤│
│  │  Extent Index 1      ││  → Points to child node
│  │  Extent Index 2      ││  → Points to child node
│  └─────────────────────┘│
└─────────────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Leaf Node              │
│  ┌─────────────────────┐│
│  │  Extent Header       ││
│  ├─────────────────────┤│
│  │  Extent 1:           ││
│  │   - logical block    ││
│  │   - length           ││
│  │   - physical block   ││
│  │  Extent 2:           ││
│  │   - logical block    ││
│  │   - length           ││
│  │   - physical block   ││
│  └─────────────────────┘│
└─────────────────────────┘
```

An extent describes a contiguous range of blocks:
- **Logical block**: Starting file offset (in blocks)
- **Length**: Number of blocks in this extent (up to 32768)
- **Physical block**: Starting block on disk

### 4.3 EXT4 Recovery Specifics

#### 4.3.1 Deleted File Handling

When a file is deleted on EXT4:
1. The directory entry is removed (the inode number is zeroed out).
2. The inode's link count is decremented (to 0 if no other hard links).
3. **The extent tree pointers in the inode are zeroed out.** This is the critical difference from NTFS — EXT4 does not preserve the extent information for deleted files.
4. The blocks are freed in the block bitmap.
5. The inode is marked as free in the inode bitmap.

**This means**: Unlike NTFS, EXT4 deleted file recovery cannot rely on the inode's extent tree. The data blocks themselves remain on disk until overwritten, but the mapping from file to blocks is lost.

#### 4.3.2 Journal Replay

The EXT4 journal (usually inode 8) records filesystem transactions. It contains:
- **Journal superblock**: Contains journal parameters.
- **Descriptor blocks**: Describe the following data blocks.
- **Data blocks**: Copies of filesystem blocks before they were modified.
- **Commit blocks**: Mark complete transactions.

Recovery tools can:
1. Parse the journal to find copies of metadata blocks (inodes, directory entries, extent trees) that were modified or deleted.
2. Reconstruct deleted file extent trees from journal data.
3. Use the journal to find the last consistent filesystem state.

#### 4.3.3 Recovery Strategies for Deleted Files

1. **Journal-based recovery**: Parse the journal for copies of deleted inodes and directory entries. This is the most reliable method for EXT4.
2. **Block group scanning**: Scan inode tables for inodes with deletion timestamps set but data still present.
3. **Directory entry carving**: Scan data blocks for directory entry structures that reference deleted inodes.
4. **Extent tree carving**: Search for extent tree structures in journal data blocks.
5. **File carving**: If all metadata is lost, fall back to signature-based carving.

#### 4.3.4 Superblock Recovery

If the primary superblock is corrupted:
1. Use backup superblocks at known block group offsets.
2. Calculate backup positions: Block groups at powers of 3, 5, 7 times the block group descriptor size.
3. Verify each backup superblock's magic number (0xEF53) and checksum.

---

## 5. FAT/exFAT Parser Design

### 5.1 FAT32 Structure

#### 5.1.1 Volume Layout

```
┌────────────────────────────┐
│  Boot Sector (Sector 0)    │
│  - OEM name, bytes/sector  │
│  - Sectors/cluster         │
│  - Reserved sectors        │
│  - Number of FATs          │
│  - Root dir cluster        │
│  - FSInfo sector           │
├────────────────────────────┤
│  FSInfo Sector             │
│  - Free cluster count      │
│  - Next free cluster       │
├────────────────────────────┤
│  Reserved Sectors          │
├────────────────────────────┤
│  FAT1 (File Allocation Tab)│
│  - Cluster chain entries   │
│  - 4 bytes per cluster     │
│  - 0x0FFFFFF8 = end of     │
│    chain                   │
│  - 0x00000000 = free       │
│  - 0x0FFFFFF7 = bad        │
├────────────────────────────┤
│  FAT2 (Backup Copy)        │
├────────────────────────────┤
│  Root Directory            │
│  - Directory entries       │
├────────────────────────────┤
│  Data Area                 │
│  - Clusters 2, 3, 4, ...  │
└────────────────────────────┘
```

#### 5.1.2 FAT Table Entries

The FAT (File Allocation Table) is an array of cluster entries. Each entry contains:
- **0x00000000**: Free cluster
- **0x0FFFFFF7**: Bad cluster
- **0x0FFFFFF8-0x0FFFFFFF**: End of chain (last cluster of a file)
- **Any other value**: Next cluster number in the chain

To read a file, you follow the cluster chain from the starting cluster (stored in the directory entry) through the FAT until you reach an end-of-chain marker.

#### 5.1.3 Directory Entries

Each 32-byte directory entry contains:
- **Byte 0**: First character of filename (0x00 = never used, 0xE5 = deleted)
- **Bytes 1-10**: Remaining characters of filename (8.3 format)
- **Byte 11**: Attributes (read-only, hidden, system, volume label, directory, archive)
- **Bytes 20-21**: High word of starting cluster (FAT32 only)
- **Bytes 26-27**: Low word of starting cluster
- **Bytes 28-31**: File size in bytes

#### 5.1.4 Long Filename (LFN) Entries

LFN entries use 32-byte directory entries with attribute 0x0F:
- **Byte 0**: Sequence number (0x01-0x14, 0x40 | n for last entry)
- **Bytes 1-10**: Characters 1-5 of name (UTF-16LE)
- **Byte 11**: Attribute 0x0F
- **Byte 12**: Type (0x00)
- **Byte 13**: Checksum of 8.3 name
- **Bytes 14-25**: Characters 6-11 of name (UTF-16LE)
- **Bytes 26-27**: Starting cluster (always 0)
- **Bytes 28-31**: Characters 12-13 of name (UTF-16LE)

LFN entries are stored in reverse order before the 8.3 entry.

### 5.2 exFAT Structure

#### 5.2.1 Key Differences from FAT32

exFAT was designed for flash drives and large files. Key differences:
- No FAT table for cluster chains (uses a different approach)
- Support for files > 4GB
- No journaling
- Larger cluster sizes (up to 32MB)
- Free space bitmap instead of FAT

#### 5.2.2 exFAT Volume Layout

```
┌────────────────────────────┐
│  Boot Sector (Sector 0)    │
│  - Volume length, FAT off  │
│  - Cluster heap offset     │
│  - Cluster count           │
│  - Root dir cluster        │
├────────────────────────────┤
│  Extended Boot Sectors     │
│  (Sectors 1-7)             │
├────────────────────────────┤
│  OEM Parameters            │
├────────────────────────────┤
│  Reserved                  │
├────────────────────────────┤
│  FAT (single copy)         │
│  - Cluster chain entries   │
│  - Used for fragmented     │
│    files only              │
├────────────────────────────┤
│  Allocation Bitmap         │
│  - 1 bit per cluster       │
│  - 1 = allocated, 0 = free │
├────────────────────────────┤
│  Up-case Table             │
│  - Case conversion table   │
│  - Required for filename   │
│    comparisons             │
├────────────────────────────┤
│  Cluster Heap (Data Area)  │
│  - Contains directories    │
│    and files               │
└────────────────────────────┘
```

#### 5.2.3 exFAT Directory Entries

exFAT uses a different directory entry format with three types of entries per file:

1. **File Directory Entry** (primary, critical):
   - Entry type: 0x85
   - Attribute flags
   - Number of secondary entries
   - File name hash
   - File size

2. **Stream Extension Directory Entry** (secondary, critical):
   - Entry type: 0xC0
   - Flags (allocation possible, no FAT chain)
   - First cluster
   - Data length
   - If "no FAT chain" flag is set, the file is contiguous and the FAT is not used.

3. **File Name Directory Entry** (secondary, critical):
   - Entry type: 0xC1
   - File name characters (UTF-16LE, up to 15 chars per entry)
   - Multiple entries may be needed for long filenames

### 5.3 FAT/exFAT Recovery Specifics

#### 5.3.1 Deleted File Detection

**FAT32**: When a file is deleted:
1. The first byte of the 8.3 directory entry is replaced with 0xE5.
2. The FAT chain entries are zeroed out (clusters marked as free).
3. The directory entry data is otherwise preserved.
4. LFN entries may have their first byte replaced with 0xE5 as well.

**exFAT**: When a file is deleted:
1. The entry type byte is inverted (0x85 → 0x05, 0xC0 → 0x40, 0xC1 → 0x41).
2. The allocation bitmap is updated to mark clusters as free.
3. The stream extension and file name entries may be preserved.

#### 5.3.2 Recovery Challenges

- **FAT chain loss**: On FAT32, the cluster chain is destroyed when a file is deleted. For fragmented files, this means the tool must guess the correct order of clusters. For contiguous files, the starting cluster + file size is sufficient.
- **FAT table selection**: FAT32 has two copies of the FAT table. Recovery tools may try both to determine which is more reliable. DMDE allows selecting FAT1, FAT2, or both, with an option to check for bad sectors.
- **exFAT single FAT**: exFAT has only one FAT table, and it cannot be properly tested (values are correctly defined for fragmented file chains only).
- **Overwritten directory entries**: If directory entries are overwritten, the tool must scan for remaining directory entries or use file carving.

---

## 6. File Carving / Signature Scanning

### 6.1 What is File Carving?

File carving is the process of recovering files from raw storage data **without using filesystem metadata**. It relies on knowledge of file format structures to identify and extract files.

### 6.2 Carving Methods

#### 6.2.1 Header-Footer Carving

The simplest method:
1. Search for a file's **magic number** (header signature) in the raw data.
2. Search for the corresponding **footer signature**.
3. Extract everything between the header and footer.

**Example**: JPEG files start with `FF D8 FF` and end with `FF D9`.

**Limitations**:
- Only works for contiguous files.
- May produce false positives if footer signatures appear in other data.
- Cannot determine the correct file size for formats without a footer.
- Fails for fragmented files.

#### 6.2.2 Header-Size Carving

Some file formats embed the file size in the header:
1. Search for the header signature.
2. Parse the size field from the header.
3. Extract the specified number of bytes.

**Example**: PNG files have a length field in the IHDR chunk, and the file size can be determined from the chunk structure.

**Limitations**:
- The size field may be corrupted.
- The size field may represent the uncompressed size rather than the on-disk size.
- Not all file formats include size information in the header.

#### 6.2.3 Bifragment Gap Carving

For files that are split into exactly **two fragments** with a gap between them:

1. Find the header signature.
2. Find the footer signature.
3. Assume the file consists of two contiguous blocks with a gap between them.
4. Try all possible gap sizes and positions.
5. Validate each candidate by parsing the file structure.

**Example**: A JPEG file split into two fragments at clusters 100-104 and 200-203, with clusters 105-199 being a gap.

**Validation**: For JPEG, validate by checking that the Huffman tables, restart markers, and end-of-image marker are all at expected positions.

**Limitations**:
- Only works for files with exactly two fragments.
- The number of possible gap positions grows with the gap size.
- Validation is file-format-specific.

#### 6.2.4 Sequential Carving

For heavily fragmented files:
1. Find all blocks that could belong to the file (based on content analysis).
2. Try different orderings of blocks.
3. Validate each candidate ordering.

**Limitations**:
- Computationally expensive (NP-hard in the general case).
- Validation is the bottleneck.
- Not practical for large files with many fragments.

#### 6.2.5 Smart Carving (Object Validation)

A more sophisticated approach:
1. **Pre-processing**: Identify all blocks that could potentially belong to each file type.
2. **Collation**: Group blocks by file type and sort by block number.
3. **Reassembly**: Use file-format-specific parsers to validate and assemble fragments.
4. **Validation**: For each candidate file, perform deep structural validation:
   - JPEG: Validate Huffman tables, restart markers, scan structure
   - PDF: Validate cross-reference table, object structure
   - ZIP: Validate local file headers, central directory
   - DOCX: Validate ZIP structure + XML content

This approach is used by tools like Scalpel, PhotoRec, and Foremost.

### 6.3 Common File Signatures (Magic Numbers)

| File Type | Header Signature | Footer Signature |
|-----------|-----------------|-----------------|
| JPEG | `FF D8 FF E0` / `FF D8 FF E1` | `FF D9` |
| PNG | `89 50 4E 47 0D 0A 1A 0A` | `49 45 4E 44 AE 42 60 82` |
| GIF | `47 49 46 38 37 61` / `47 49 46 38 39 61` | `00 3B` |
| PDF | `25 50 44 46` | `25 25 45 4F 46` |
| ZIP | `50 4B 03 04` | `50 4B 05 06` |
| RAR | `52 61 72 21 1A 07 00` | — |
| DOCX/XLSX/PPTX | `50 4B 03 04` (ZIP) | `50 4B 05 06` |
| DOC (OLE2) | `D0 CF 11 E0 A1 B1 1A E1` | — |
| AVI | `52 49 46 46 .. .. .. .. 41 56 49 20` | — |
| MP4 | `.. .. .. .. 66 74 79 70` | — |
| SQLite | `53 51 4C 69 74 65 20 66 6F 72 6D 61 74 20 33 00` | — |

### 6.4 File Length Detection

Determining file length is one of the hardest problems in carving:

1. **Embedded size**: Some formats (PNG, TIFF, ZIP, RAR) include size information in the header.
2. **Footer detection**: Some formats (JPEG, GIF) have explicit end markers.
3. **Structural parsing**: Parse the file structure to determine logical boundaries (PDF, DOCX).
4. **Heuristic detection**: For formats without size or footer, use content analysis to estimate the end.
5. **Cluster alignment**: If the file is contiguous, the end is at the starting cluster + ceil(file_size / cluster_size) * cluster_size.

### 6.5 Limitations of File Carving

- **Fragmentation**: The biggest challenge. No file carver can automatically reassemble heavily fragmented files with 100% accuracy.
- **False positives**: Magic numbers can appear in random data, leading to false detections.
- **File naming**: Carved files lose their original names and directory structure.
- **No metadata**: Carved files lose timestamps, permissions, and other metadata.
- **Encrypted/compressed files**: Cannot be carved without the key or decompression algorithm.
- **Performance**: Scanning an entire disk for signatures is slow. Optimizations include block-level caching and parallel processing.
- **SSD TRIM**: On SSDs, TRIM commands may erase freed blocks, making carving impossible.

---

## 7. Filesystem Reconstruction

### 7.1 Overview

Filesystem reconstruction is the process of rebuilding a damaged or partially destroyed filesystem's directory tree and file metadata. This is the core capability that distinguishes professional tools like R-Studio and DMDE from simple file carvers.

### 7.2 DMDE's Reconstruction Approach

Based on DMDE's documentation, the reconstruction process works as follows:

1. **Full Scan**: The tool performs a full scan of the disk, searching for:
   - Filesystem metadata fragments (MFT entries, INDX records, directory entries, etc.)
   - Boot sector / superblock copies
   - Journal data
   - Any other recognizable filesystem structures

2. **FS Fragment Classification**: Found fragments are grouped by their probability of belonging to the current volume:
   - **Best/Correct**: Most likely and likely to belong to the open volume
   - **Related**: Probably related to other versions of this volume (e.g., before a format)
   - **Unknown**: Relevant volume could not be detected
   - **Extraneous**: Relevant to a different volume
   - **Small (extra found)**: Too small for statistical analysis
   - **Disabled**: Incompatible due to different filesystem parameters

3. **Virtual File System Assembly**: The tool assembles a virtual directory tree from the collected fragments:
   - **NTFS**: Merges MFT entries, INDX records, and $LogFile data to build the directory tree.
   - **FAT/exFAT**: Uses FAT table copies and directory entries to reconstruct the file structure.
   - **Other filesystems**: Uses filesystem-specific metadata.

4. **Reconstruction Quality Control**: The user can adjust the reconstruction using:
   - **More/Less Results** buttons: Increase or decrease the number of files included in the reconstruction.
   - **Advanced parameters**: For specialists to fine-tune the reconstruction.
   - **Color indicators**: Show the quality and number of selected results.

### 7.3 NTFS-Specific Reconstruction Heuristics

#### 7.3.1 INDX Processing

DMDE's INDX processing is a key differentiator:

- **Auto INDX processing**: Uses information from INDX records on top of MFT data to reconstruct directory structure. This is slower but more accurate.
- **Full INDX processing**: Forces INDX processing even when MFT data is available.
- **INDX merging improvement**: Prevents possible wrong merging of directory branches by considering timestamps.

When an MFT entry for a directory is damaged, its INDX records may still contain the file references. The tool can:
1. Scan all INDX records.
2. Build a parent-child relationship map from the INDX data.
3. Merge this with the directory tree built from MFT entries.

#### 7.3.2 Shifted MFT Records

After a volume resize or corruption, MFT records may be shifted from their expected positions. The tool:
1. Identifies MFT records at unexpected offsets.
2. Maps them to their correct MFT numbers.
3. Includes them in the reconstruction.

#### 7.3.3 Extra Found Files

The "Include Extra Found" option may include:
- Files from MFT entries that don't clearly belong to the current volume.
- Files with inconsistent metadata.
- Files from orphaned MFT entries.

This may contain more garbage but can help recover files that are not recoverable through other means.

#### 7.3.4 Journal Processing

The "Process FS journal" option includes information from the NTFS $LogFile:
- Recent file operations that may not be reflected in the on-disk MFT.
- Undo information for incomplete transactions.
- File creation/deletion records.

### 7.4 R-Studio's Reconstruction Approach

R-Studio uses a similar approach but with some differences:

1. **Known File Types (KFT)**: R-Studio maintains a database of known file types and their signatures. During a scan, it can identify files by their content even when metadata is missing.

2. **Extra Found Files**: R-Studio categorizes found files into:
   - **Existing files**: Files with valid metadata and data.
   - **Deleted files**: Files with metadata indicating deletion.
   - **Extra found files**: Files found by carving or from damaged metadata.

3. **Multi-pass scan**: R-Studio performs a quick scan first for existing metadata, then a deep scan for carving.

4. **RAID reconstruction**: R-Studio can automatically detect RAID parameters (stripe size, order, parity) and reconstruct virtual RAID arrays.

### 7.5 General Reconstruction Heuristics

Common heuristics used by reconstruction engines:

1. **Timestamp consistency**: Files in a directory should have timestamps that are reasonably consistent with the directory's creation time.
2. **Parent-child validation**: Verify that a file's parent directory reference points to a valid directory.
3. **Cluster allocation validation**: Check that file clusters don't overlap with other files or metadata areas.
4. **Size consistency**: Compare the file size in the metadata with the actual data size.
5. **Sequential MFT numbering**: NTFS MFT entries are typically allocated sequentially, so the MFT number can be used as a rough chronological ordering.
6. **File type validation**: Verify that the file extension matches the file content (magic number).
7. **Checksum validation**: Use filesystem checksums (APFS btrailer, ZFS checksums) to validate metadata integrity.
8. **Bitmap cross-referencing**: Compare the allocation bitmap with the actual file allocations to detect inconsistencies.

---

## 8. Raw Disk Reading

### 8.1 Direct Disk Access Methods

#### 8.1.1 Windows

On Windows, raw disk access is achieved through:
- **`CreateFile("\\\\.\\PhysicalDriveN")`**: Opens a raw handle to the physical disk.
- **`ReadFile()`**: Reads sectors from the disk handle.
- **`DeviceIoControl()` with `IOCTL_DISK_READ`**: Reads specific sectors.
- **`IOCTL_SCSI_PASS_THROUGH`**: Sends raw SCSI commands to the disk.

For USB drives, the USB mass storage protocol translates SCSI commands to USB bulk transfers. The USB bridge controller (e.g., JMicron, ASMedia, Prolific) handles the translation.

#### 8.1.2 Linux

On Linux, raw disk access is through:
- **`/dev/sdX`**: Block device file for the entire disk.
- **`/dev/sdXN`**: Block device file for partition N.
- **`open()` + `read()`**: Direct sector reading.
- **`ioctl()` with `SG_IO`**: SCSI Generic interface for sending SCSI commands.
- **`hdparm`**: For ATA-specific commands (SMART, security, etc.).

#### 8.1.3 macOS

On macOS, raw disk access uses:
- **`/dev/diskN`**: Block device file.
- **`/dev/rdiskN`**: Raw device file (no buffering).
- **`IOKit` framework**: For low-level device access.
- **`IOService`**: For ATA/SCSI command pass-through.

### 8.2 ATA/SCSI Commands for Data Recovery

| Command | ATA | SCSI | Purpose |
|---------|-----|------|---------|
| Read sectors | `READ DMA EXT` (0x25) | `READ(10)` (0x28) | Read data sectors |
| Read SMART data | `SMART READ DATA` (0xB0) | `READ ATTRIBUTE` | Get disk health info |
| Read DMA | `READ DMA EXT` | `READ(16)` | Read with DMA transfer |
| Identify device | `IDENTIFY DEVICE` (0xEC) | `INQUIRY` (0x12) | Get disk capabilities |
| Read NATIVE MAX | `READ NATIVE MAX ADDRESS` | — | Detect HPA (Host Protected Area) |
| Read DMA LOG | `READ LOG DMA EXT` | `LOG SENSE` | Read error logs |
| TRIM / UNMAP | `DATA SET MANAGEMENT` | `UNMAP` | Inform SSD of freed blocks |

### 8.3 SATA vs USB Protocols

**SATA (Serial ATA)**:
- Direct connection to the disk controller.
- Full ATA command set available.
- No protocol translation overhead.
- Supports NCQ (Native Command Queuing) for efficient read scheduling.
- Can access HPA (Host Protected Area) and DCO (Device Configuration Overlay).

**USB Mass Storage**:
- USB bridge chip translates SCSI commands to ATA commands.
- Limited command set (SCSI subset only).
- Some ATA-specific commands (SMART, HPA, DCO) may not be available through the bridge.
- Bridge chips may have bugs or limitations in command translation.
- Some bridges have a 2TB limit (using 32-bit LBA instead of 64-bit).
- USB 3.0 provides sufficient bandwidth (5 Gbps) for most recovery operations.

**Important for recovery**: When possible, connect the disk directly via SATA rather than USB. This provides:
- Full access to the ATA command set.
- Better error reporting.
- No USB bridge overhead or bugs.
- Access to HPA/DCO areas.

### 8.4 Handling I/O Errors

I/O errors are a common challenge in data recovery. Strategies include:

#### 8.4.1 Error Recovery Hierarchy

1. **Retry with OS**: Simple retry of the read operation. May succeed if the error was transient.
2. **ATA PASS-THROUGH**: Send a raw ATA read command with extended retry options.
3. **Partial read**: Read the sector in smaller chunks (e.g., 512 bytes at a time instead of 4096).
4. **Skip and continue**: Skip the bad sector and continue reading. Mark the sector as unreadable.
5. **Reverse read**: Read the disk from the end towards the beginning. This can sometimes work around mechanical issues.
6. **Hardware-specific**: Use vendor-specific commands (e.g., Seagate's `READ LONG` command) to read data even with ECC errors.

#### 8.4.2 Disk Imaging Strategies

Professional tools use adaptive imaging strategies:

- **ddrescue**: A GNU tool that reads the disk in passes:
  - First pass: Read all easily readable sectors.
  - Second pass: Read sectors that failed, with smaller block sizes and more retries.
  - Third pass: Try to read individual sectors that still failed.
  - Uses a "mapfile" to track which sectors have been read and which have failed.

- **DMDE's imaging**: Uses a similar approach with:
  - Configurable retry count and timeout.
  - Read-ahead optimization.
  - Skip count for consecutive errors.
  - Sector-by-sector reading for failed areas.

- **DeepSpar Disk Imager**: A professional hardware-based imager that:
  - Connects directly to the disk via SATA/IDE.
  - Uses ATA commands directly, bypassing the OS.
  - Handles bad sectors with configurable retry strategies.
  - Can read sectors with ECC errors (ignoring the ECC check).
  - Has a built-in disk health monitor.

- **PC-3000**: A professional hardware/software combination from ACE Lab that:
  - Provides full ATA/SCSI command control.
  - Can disable the disk's internal error correction.
  - Can read in "technological mode" (accessing firmware zones).
  - Can repair firmware issues on specific disk models.

### 8.5 SAS/SCSI Considerations

SAS (Serial Attached SCSI) drives present additional challenges:
- **Extended error reporting**: SAS/SCSI protocols have an extended error-reporting system providing more information on issues.
- **SCSI sense codes**: More detailed error information than ATA status codes.
- **Different command set**: SAS drives use SCSI commands, not ATA commands.
- **Enterprise features**: SAS drives may have additional features like T10 Protection Information (PI) and persistent reservations.

### 8.6 SSD-Specific Considerations

- **TRIM/UNMAP**: When a file is deleted, the OS sends TRIM commands to the SSD, which may erase the logical blocks. This makes recovery of deleted files on SSDs significantly harder.
- **Wear leveling**: SSD controllers use wear leveling algorithms that distribute writes across all physical blocks. This means the logical-to-physical mapping is not straightforward.
- **FTL (Flash Translation Layer)**: The SSD controller's firmware maps logical block addresses to physical flash pages. This mapping is proprietary and varies between SSD manufacturers.
- **Encryption**: Many modern SSDs use hardware encryption (SED - Self-Encrypting Drive). Even without a user password, the data is encrypted on the flash chips. Recovery requires the encryption key.
- **Read disturbance**: Reading the same flash block repeatedly can cause adjacent cells to flip, potentially corrupting data.

---

## Appendix A: Key Open-Source Recovery Tools and Libraries

| Tool/Library | Language | Filesystems | Carving | Notes |
|---|---|---|---|---|
| **TestDisk** | C | FAT, NTFS, EXT2/3/4, HFS+ | No | Partition recovery, MFT rebuild |
| **PhotoRec** | C | Format-agnostic | Yes | File carving only, 480+ file types |
| **Scalpel** | C | Format-agnostic | Yes | Based on Foremost, improved |
| **Foremost** | C | Format-agnostic | Yes | Originally by AFOSI/USAF |
| **The Sleuth Kit (TSK)** | C | NTFS, FAT, EXT2/3/4, HFS+, UFS | Limited | Forensic framework, APIs |
| **libfsapfs** | C | APFS | No | APFS parser library |
| **libfsntfs** | C | NTFS | No | NTFS parser library |
| **libfsext** | C | EXT2/3/4 | No | EXT parser library |
| **Bulk Extractor** | C++ | Format-agnostic | Yes | Forensic feature extraction |
| **Magic Rescue** | C | Format-agnostic | Yes | Configurable carving rules |

## Appendix B: Key Filesystem Specifications and References

| Filesystem | Official Specification | Key Reference |
|---|---|---|
| NTFS | Microsoft NTFS spec (partially public) | "Windows Internals" by Russinovich |
| APFS | Apple File System Reference (NDA) | Jtsylve.blog APFS Advent Challenge |
| EXT4 | Linux kernel documentation | kernel.org/doc/html/latest/filesystems/ext4/ |
| FAT32 | Microsoft FAT spec (public) | MBR/FAT spec from Microsoft |
| exFAT | Microsoft exFAT spec (public) | learn.microsoft.com exFAT spec |
| HFS+ | Apple HFS+ spec (legacy) | Apple Developer documentation |

## Appendix C: Research Sources

- Klennet Carver: File carving methods in data recovery (https://www.klennet.com/carver/carving-methods.aspx)
- DMDE: Virtual File System Reconstruction (https://dmde.com/manual/reconstruction.html)
- NTFS.com: APFS Structure (http://ntfs.com/apfs-structure.htm)
- UMass COMPSCI 365: NTFS Lecture Notes (https://people.cs.umass.edu/~liberato/courses/2018-spring-compsci365+590f/lecture-notes/14-more-on-ntfs)
- Oracle Linux Blog: Understanding Ext4 Disk Layout (https://blogs.oracle.com/linux/understanding-ext4-disk-layout-part-1)
- Gillware: Ext4 Data Recovery (https://www.gillware.com/data-recovery-services/ext4-data-recovery)
- HackMD: Deep Dive Into APFS Structure (https://hackmd.io/@M4shl3/Deep-Dive-Into-APFS-Structure)
- Apple: Apple File System Reference (https://developer.apple.com/support/downloads/Apple-File-System-Reference.pdf)
- Linux Kernel: EXT4 Documentation (https://www.kernel.org/doc/html/v5.8/filesystems/ext4/overview.html)
- Wikipedia: File Carving (https://en.wikipedia.org/wiki/File_carving)
- DeepSpar: SAS Drives - New Challenges in Recovery (https://www.deepspar.com/blog/sas-drives)
- OSDev Wiki: FAT Filesystem (https://wiki.osdev.org/FAT)
- Microsoft: exFAT File System Specification (https://learn.microsoft.com/en-us/windows/win32/fileio/exfat-specification)
- Active Undelete: NTFS File Types (http://active-undelete.com/ntfs_file_types.htm)
- Active Undelete: exFAT Entries (http://active-undelete.com/xfat_entries.htm)
