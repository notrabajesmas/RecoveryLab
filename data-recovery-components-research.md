# Open-Source Data Recovery Components: Research Report

**Date:** 2026-03-04  
**Purpose:** Identify reusable open-source components for integration into a new data recovery engine  
**Scope:** Architecture, filesystem support, licensing, library feasibility, and integration analysis

---

## Table of Contents

1. [TestDisk](#1-testdisk)
2. [PhotoRec](#2-photorec)
3. [The Sleuth Kit (TSK) / libtsk](#3-the-sleuth-kit-tsk--libtsk)
4. [Untrunc](#4-untrunc)
5. [GNU ddrescue](#5-gnu-ddrescue)
6. [HDDSuperClone / OpenSuperClone](#6-hddsuperclone--opensuperclone)
7. [Other Relevant Tools](#7-other-relevant-tools)
8. [Licensing Analysis](#8-licensing-analysis)
9. [Integration Feasibility](#9-integration-feasibility)
10. [Summary & Recommendations](#10-summary--recommendations)

---

## 1. TestDisk

### Overview
TestDisk is a free and open-source data recovery utility designed primarily to recover lost partitions and repair corrupted filesystems. It is maintained by Christophe Grenier (CGSecurity) and distributed alongside PhotoRec.

### What It Does
- **Partition recovery**: Scans for lost/deleted partition tables and rebuilds them
- **Boot sector repair**: Rebuilds corrupted boot sectors (FAT12/16/32, NTFS boot sector)
- **Filesystem repair**: Fixes corrupted MFT (NTFS), FAT tables, ext2/3/4 superblocks
- **File undelete**: Recovers deleted files from supported filesystems (limited capability)
- **Partition table rewriting**: Can write recovered partition tables back to disk

### Supported Filesystems
| Filesystem | Read | Write/Repair | Notes |
|---|---|---|---|
| FAT12/16/32 | Yes | Yes | Boot sector repair, FAT rebuilding |
| NTFS | Yes | Yes | MFT repair, boot sector rebuild |
| exFAT | Yes | Limited | Partition recovery mainly |
| ext2/ext3/ext4 | Yes | Yes | Superblock recovery |
| HFS/HFS+ | Yes | Limited | Partition recovery |
| ReiserFS | Yes | Limited | Via NTFS-3G integration |
| UFS/UFS2 | Yes | Limited | BSD/Sun partition tables |
| Sun Solaris | Yes | No | Partition table recovery |
| BSD disklabel | Yes | No | Partition table recovery |

### Architecture
- **Language**: Pure C (ANSI C)
- **Source structure**: Monolithic single-binary architecture; TestDisk and PhotoRec share a common codebase
- **Build system**: Autoconf/Automake with `./configure && make`
- **UI**: Interactive text-based (ncurses) menu-driven interface; no headless/library mode
- **Disk access**: Direct device access via OS-level APIs (Linux `/dev/`, Windows `\\.\PhysicalDrive`)
- **Key modules**:
  - `src/` directory: `testdisk.c` (main), `partauto.c` (auto-detection), `tdiskop.c` (disk operations)
  - Filesystem-specific handlers in separate files (e.g., `ntfs.c`, `fat.c`, `ext2.c`)
  - Partition table handlers: `parti386.c` (MBR), `partgpt.c` (GPT), `partsun.c`, `partmac.c`

### Library Usability
- **NOT designed as a library**. TestDisk is a standalone CLI/interactive tool.
- No exported API, no shared library (.so/.dll), no header files for programmatic use.
- **Integration options**:
  - Fork and extract the filesystem-specific recovery logic (significant refactoring needed)
  - Shell out to the CLI and parse output (fragile, limited)
  - The partition detection logic in `partauto.c` could be extracted with moderate effort

### License
- **GPL v2+** (GNU General Public License version 2 or later)
- This means any derivative work must also be GPL v2+

### Limitations
- No library/API mode; tightly coupled to interactive UI
- No network/remote disk support
- Limited file undelete (not as robust as dedicated carving tools)
- No APFS support
- No Btrfs support
- No ZFS support
- No parallel processing/multi-threading
- No progress reporting API for GUI integration
- Monolithic architecture makes extracting individual components difficult

---

## 2. PhotoRec

### Overview
PhotoRec is a free and open-source file carving utility that recovers deleted files by scanning raw disk data for file signatures, independent of the filesystem. It is bundled with TestDisk and shares the same codebase.

### What It Does
- **File carving**: Recovers files from damaged, formatted, or corrupted media regardless of filesystem state
- **Read-only operation**: Never writes to the source media; always operates non-destructively
- **Broad format support**: 300+ file families, 480+ file extensions
- **Custom signatures**: Supports user-defined signature files for custom file types

### How the Carving Engine Works
PhotoRec's carving engine is **not** a simple header-footer carver. It uses a multi-layered approach:

1. **Signature scanning**: Scans raw disk data block-by-block looking for known file header signatures (magic bytes)
2. **File-type-specific parsing**: Once a signature is found, type-specific parsers validate and extract the file:
   - **Structured formats** (JPEG, PNG, PDF, DOCX): Parse internal structure to determine file size
   - **Container formats** (ZIP, RAR, 7z): Parse headers to find end-of-archive markers
   - **Video formats** (MP4, AVI, MOV): Parse atom/chunk structure for boundaries
   - **RAW camera formats** (CR2, NEF, ORF): Parse TIFF/EXIF-like structures
3. **Fragment handling**: For some formats, PhotoRec can handle fragmented files by looking for continuation markers
4. **Validation**: Recovered files are validated against known format constraints
5. **Custom signatures**: Users can define custom signatures via a `photorec.sig` file with header bytes, offset, and file extension

### Supported File Formats (Major Categories)
| Category | Examples | Count |
|---|---|---|
| Images | JPEG, PNG, GIF, TIFF, BMP, RAW (CR2, NEF, ORF, DNG, ARW) | 80+ |
| Video | MP4, AVI, MOV, MKV, WMV, FLV, 3GP | 30+ |
| Audio | MP3, WAV, OGG, FLAC, AAC, WMA | 20+ |
| Documents | PDF, DOC/DOCX, XLS/XLSX, PPT/PPTX, ODT, RTF | 40+ |
| Archives | ZIP, RAR, 7z, TAR, GZ, BZ2 | 20+ |
| Database | MDB, SQL, DBF, SQLite | 10+ |
| Executable | EXE, DLL, ELF | 5+ |
| Other | ISO, VMDK, VHD, eml, mbox | 50+ |

### Architecture
- **Language**: Pure C (ANSI C), same codebase as TestDisk
- **Source structure**: File-type-specific parsers in `src/` directory (e.g., `file_jpg.c`, `file_pdf.c`, `file_mp4.c`)
- **Carving engine**: Core logic in `photorec.c` and `phrecn.c`
- **Signature database**: Compiled into the binary from individual `file_*.c` files
- **Session management**: Supports resume/continue interrupted recovery sessions
- **Output**: Files recovered to a specified output directory with sequential naming

### Library Usability
- **NOT designed as a library**. Like TestDisk, it is a standalone CLI/interactive tool.
- No exported API, no shared library, no header files.
- **Integration options**:
  - The file-type-specific parsers (e.g., `file_jpg.c`, `file_mp4.c`) are relatively self-contained and could be extracted
  - The carving engine core (`photorec.c`) is tightly coupled to the interactive UI
  - CLI invocation with output parsing is the simplest integration path
  - Autopsy (by TSK) integrates PhotoRec as a module by invoking it as a subprocess

### License
- **GPL v2+** (same as TestDisk)

### Limitations
- No library/API mode; interactive UI only
- File names are lost (carved files get sequential names like `f0000001.jpg`)
- No directory structure recovery (inherent to carving)
- No support for fragmented files in most formats
- Single-threaded processing
- No network/remote source support
- No progress callback API
- No built-in deduplication of recovered files
- Cannot recover files smaller than the filesystem block size

---

## 3. The Sleuth Kit (TSK) / libtsk

### Overview
The Sleuth Kit (TSK) is a collection of command-line tools and a **C library (libtsk)** for analyzing disk images and recovering files. It is the most mature and library-friendly open-source forensic tool available. TSK powers Autopsy (its GUI front-end) and many other commercial and open-source tools.

### Supported Filesystems
| Filesystem | Read | Write | Notes |
|---|---|---|---|
| NTFS | Yes | No | Full MFT parsing, ADS support |
| FAT12/16/32 | Yes | No | Full directory parsing |
| exFAT | Yes | No | |
| ext2/ext3/ext4 | Yes | No | Full inode parsing |
| HFS/HFS+ | Yes | No | |
| HFSX | Yes | No | |
| UFS1/UFS2 | Yes | No | |
| YAFFS2 | Yes | No | Embedded/Android |
| ISO 9660 | Yes | No | CD-ROM |
| APFS | Partial | No | Limited/experimental support |
| LVM | Yes | No | Volume management layer |

### Volume System Support
| Type | Support |
|---|---|
| MBR/DOS | Yes |
| GPT | Yes |
| BSD Disklabel | Yes |
| Sun VTOC | Yes |
| Mac Partition Map | Yes |
| LVM | Yes |
| RAID (mdadm) | Limited |
| LUKS | No (encrypted) |

### Library API (libtsk)
TSK is **designed as a library** with a well-documented C API. Key API groups:

#### Image Layer
```c
TSK_IMG_INFO *tsk_img_open_utf8_sing(const char *a_utf8, TSK_IMG_TYPE_ENUM a_type, unsigned int a_ssize);
TSK_IMG_INFO *tsk_img_open_sing(const char *a_image, TSK_IMG_TYPE_ENUM a_type, unsigned int a_ssize);
uint8_t tsk_img_read(TSK_IMG_INFO *a_img_info, TSK_OFF_T a_offset, char *a_buf, size_t a_len);
void tsk_img_close(TSK_IMG_INFO *a_img_info);
```

#### Volume System Layer
```c
TSK_VS_INFO *tsk_vs_open(TSK_IMG_INFO *a_img_info, TSK_DADDR_T a_offset, TSK_VS_TYPE_ENUM a_type);
TSK_VS_PART_INFO *tsk_vs_part_get(TSK_VS_INFO *a_vs_info, int a_index);
void tsk_vs_close(TSK_VS_INFO *a_vs_info);
```

#### Filesystem Layer
```c
TSK_FS_INFO *tsk_fs_open_img(TSK_IMG_INFO *a_img_info, TSK_OFF_T a_offset, TSK_FS_TYPE_ENUM a_type);
TSK_FS_FILE *tsk_fs_file_open_meta(TSK_FS_INFO *a_fs, TSK_FS_FILE *a_fs_file, TSK_INUM_T a_addr);
TSK_FS_FILE *tsk_fs_file_open(TSK_FS_INFO *a_fs, TSK_FS_FILE *a_fs_file, const char *a_path);
ssize_t tsk_fs_file_read(TSK_FS_FILE *a_fs_file, TSK_OFF_T a_offset, char *a_buf, size_t a_len, TSK_FS_FILE_READ_FLAG_ENUM a_flags);
uint8_t tsk_fs_dir_walk(TSK_FS_INFO *a_fs, TSK_INUM_T a_addr, TSK_FS_DIR_WALK_FLAG_ENUM a_flags, TSK_FS_DIR_WALK_CB a_action, void *a_ptr);
uint8_t tsk_fs_fls(TSK_FS_INFO *a_fs, TSK_TCHAR **a_argv);
void tsk_fs_close(TSK_FS_INFO *a_fs);
```

#### Key Features of the API
- **Layered architecture**: Image → Volume System → Filesystem → File (clean abstraction)
- **Callback-based iteration**: `tsk_fs_dir_walk()`, `tsk_fs_file_walk()` for directory traversal
- **Autodetection**: `tsk_fs_open_img()` can auto-detect filesystem type with `TSK_FS_TYPE_DETECT`
- **Java bindings**: Official JNI bindings available (`bindings/java/`)
- **Python bindings**: Available via third-party `pytsk` wrapper

### Language Bindings
| Language | Binding | Status |
|---|---|---|
| C | libtsk (native) | Official, full API |
| Java | JNI bindings | Official, in repo |
| Python | pytsk | Third-party, partial |
| C++ | Direct C linkage | Trivial |
| .NET | TSK wrapper | Third-party, limited |

### Limitations for Recovery (vs. Forensics)
- **Read-only**: TSK is designed for forensic analysis, not repair. It cannot write/repair filesystems.
- **No partition recovery**: Cannot rebuild partition tables (unlike TestDisk)
- **No file carving**: TSK does not include a carving engine (relies on filesystem metadata)
- **No deleted file recovery guarantee**: Deleted files may have overwritten metadata; TSK can find them but cannot guarantee content
- **No APFS full support**: APFS is still experimental/incomplete
- **No Btrfs/ZFS support**: Missing modern Linux filesystems
- **No encrypted volume support**: Cannot handle BitLocker, LUKS, FileVault
- **Single-threaded**: Core operations are not multi-threaded
- **No disk imaging**: Cannot create disk images (unlike ddrescue)

### License
- **Mixed licensing** (important for commercial use):
  - **Core library (libtsk)**: Predominantly **IBM Public License v1.0** and **Common Public License v1.0 (CPL)**
  - **Some tools**: **GPL v2+**
  - **Some modules**: **LGPL**
  - The IBM CPL and CPL are **OSI-approved** and generally compatible with commercial use (similar to LGPL in effect)
  - **Critical**: The library portion can be linked into commercial applications without requiring the application to be open-sourced, but the specific license terms must be carefully reviewed per-module

### Integration Verdict
- **Best candidate for library integration** among all tools researched
- Well-documented C API with stable ABI
- Existing commercial products use libtsk (e.g., some forensic tools)
- Java bindings available for JVM-based projects
- The read-only nature is actually a feature for recovery (non-destructive analysis)

---

## 4. Untrunc

### Overview
Untrunc is a specialized open-source tool for repairing corrupted/truncated MP4, MOV, M4V, and 3GP video files. It is particularly useful for recovering video from dashcams, bodycams, smartphones, and drones where recording was interrupted.

### What It Does
- Repairs MP4/MOV files with missing or corrupted `moov` atom (metadata block)
- Recovers truncated video files where recording was interrupted
- Reconstructs the `moov` atom using a healthy reference video from the same device
- Handles H.264, H.265, and other codec streams within MP4 containers

### How It Works
The repair process operates in **three phases**:

1. **Reference Analysis**: Untrunc reads the `moov` atom from the healthy reference video, extracting:
   - Codec parameters (H.264 profile, level, SPS/PPS)
   - Sample table structure (sample sizes, offsets, durations)
   - Track layout and timing information
   - Audio/video synchronization metadata

2. **Stream Parsing**: Untrunc scans the broken file byte-by-byte, identifying:
   - `mdat` atom boundaries (raw media data)
   - Individual NAL units (Network Abstraction Layer units for H.264)
   - Audio frames (AAC, PCM, etc.)
   - Sync points (keyframes/I-frames)

3. **Reconstruction**: A new `moov` atom is constructed by:
   - Mapping the identified media data to sample table entries
   - Calculating offsets, sizes, and durations for each sample
   - Building the track structure based on the reference template
   - Writing the repaired file with a valid `moov` atom prepended/appended

### Architecture
- **Language**: C++ (original by Federico Dossena), with active forks in C++
- **Source**: Single-file architecture (`untrunc.cpp`), relatively simple
- **Dependencies**: FFmpeg (libavcodec, libavformat) for codec parsing
- **Build**: Simple Makefile or CMake
- **Active fork**: `anthwlock/untrunc` on GitHub (10x faster, lower memory, fixes)

### Library Usability
- **NOT designed as a library**. Standalone CLI tool.
- The core logic is in a single C++ file and could be refactored into a library with moderate effort
- The reference-analysis and stream-parsing logic are separable
- **Integration options**:
  - Fork and wrap the core logic into a C++ library class
  - CLI invocation with output parsing
  - The `anthwlock` fork has cleaner code structure

### License
- **GPL v2.0** (original and most forks)
- Some forks may have different licenses; check specific fork

### Limitations
- Requires a reference video from the same device/recorder (same codec settings)
- Only handles MP4/MOV/3GP container formats
- Cannot repair files where the `mdat` data itself is corrupted
- No support for AVI, MKV, or other containers
- No GUI in the original (some forks add GUIs)
- No batch processing
- Single-threaded
- Memory-intensive for large files (original); improved in `anthwlock` fork

### Integration Potential
- **High value** for a recovery engine focused on video recovery
- The MP4 reconstruction logic is unique and valuable
- Would need refactoring from CLI to library
- The FFmpeg dependency is a consideration (LGPL v2.1+ or GPL depending on build options)

---

## 5. GNU ddrescue

### Overview
GNU ddrescue is a data recovery tool that copies data from one file or block device to another, with a sophisticated algorithm designed to rescue as much data as possible from failing drives while minimizing additional damage.

### What Makes It Better Than dd for Failing Disks
| Feature | dd | ddrescue |
|---|---|---|
| Error handling | Stops on first error | Skips errors, retries later |
| Block size | Fixed | Adaptive (shrinks on error) |
| Resume | No | Yes (mapfile-based) |
| Read strategy | Sequential only | Adaptive multi-pass |
| Bad sector tracking | No | Yes (mapfile) |
| Trim/scrape | No | Yes (per-sector recovery) |
| Progress tracking | Minimal | Detailed (mapfile) |
| Additional damage risk | High (repeated reads) | Minimized (smart retry) |

### Adaptive Reading Algorithm (5 Phases)

#### Phase 1: Copying
- Reads non-tried areas in **large blocks** (default: 128 KiB)
- When a read error occurs, marks the failed block as "non-tried" at a smaller size
- Skips over bad areas quickly to rescue good data first
- **Key insight**: Get one good read from every accessible sector before spending time on bad ones

#### Phase 2: Trimming
- Reads forwards one sector at a time from the edges of bad areas
- "Trims" the boundaries of unreadable regions to their minimum size
- Each sector is tried at most once in this phase
- **Purpose**: Recover data from the edges of bad blocks where only part of the block is damaged

#### Phase 3: Sweeping (ddrescue 1.22+)
- Reads the remaining non-tried blocks in reverse direction
- Helps identify boundaries that might be different when reading from the opposite direction
- **Purpose**: Some drives read differently depending on direction

#### Phase 4: Scraping
- Reads each non-scraped block forwards, **one sector at a time**
- Single-sector reads are more likely to succeed than multi-sector reads
- Each sector is tried at most once in this phase
- **Purpose**: Recover individual sectors that failed in larger block reads

#### Phase 5: Retrying (disabled by default)
- Re-attempts all failed sectors with a specified number of retries
- Can be configured with `--retry-passes=N`
- **Purpose**: Last-resort attempt for remaining bad sectors

### Mapfile
- Binary mapfile tracks the status of every sector:
  - `+` (rescued): Successfully read
  - `-` (bad): Failed to read
  - `/` (non-tried): Not yet attempted
  - `?` (non-trimmed): Edge of bad area, needs trimming
  - `*` (non-scraped): Needs scraping
- Enables resume after interruption
- Can be manually edited for advanced control

### Architecture
- **Language**: C++
- **Source**: Single-file architecture (`ddrescue.cc`), well-structured
- **I/O model**: Asynchronous I/O with non-blocking reads
- **Build**: Standard GNU autotools
- **No external dependencies**

### Library Usability
- **NOT designed as a library**. Standalone CLI tool.
- The algorithm logic is in a single C++ file
- **Integration options**:
  - Fork and extract the core algorithm (the `Rescuebook` class)
  - CLI invocation with mapfile parsing
  - The algorithm is well-documented and could be reimplemented in a clean-room manner

### License
- **GPL v2+** (part of GNU project)
- Cannot be linked into proprietary software

### Limitations
- No library mode
- No GUI (third-party GUIs exist: ddrescueview, DDRescue-GUI)
- Reads through Linux kernel block device layer (cannot send raw ATA commands)
- No head-awareness (doesn't know which physical head is failing)
- No SMART integration
- No automatic disk health assessment
- Single-threaded I/O (one read at a time)
- No network/remote source support

---

## 6. HDDSuperClone / OpenSuperClone

### Overview
HDDSuperClone (by Scott Dwyer) and its open-source fork OpenSuperClone (by ISpillMyDrink) are advanced Linux-based disk cloning/imaging tools specifically designed for data recovery from failing drives. They represent a significant step beyond ddrescue in their approach to failing disk handling.

### What Makes It Different from ddrescue
| Feature | ddrescue | HDDSuperClone/OpenSuperClone |
|---|---|---|
| I/O path | Linux kernel block layer | Raw ATA/SCSI commands |
| Head awareness | No | Yes (head mapping) |
| Read strategy | Adaptive multi-pass | Adaptive + head-skipping |
| Virtual driver | No | Yes (virtual driver for OS access) |
| Firmware access | No | Yes (ATA/SCSI passthrough) |
| Write-blocking | No | Yes (read-only virtual driver) |
| Phase management | 5 fixed phases | Configurable multi-phase |
| Drive-specific tuning | No | Yes (adjustable timeouts, block sizes) |

### Adaptive Reading Strategy
OpenSuperClone's approach is fundamentally different from ddrescue:

1. **Head-Skipping Algorithm**: 
   - Deduces head boundaries from LBA error clustering
   - When one head is failing, skips the entire head's LBA range
   - Returns to skipped heads later (some heads may recover after rest)
   - This is the key advantage: Linux software cannot read firmware geometry directly, so OSC infers it from error patterns

2. **Configurable Read Modes**:
   - **Standard read**: Normal kernel-level reads
   - **ATA pass-through**: Sends raw ATA read commands (READ DMA, READ NATIVE MAX ADDRESS)
   - **SCSI pass-through**: Raw SCSI commands for SCSI/SAS drives
   - **Virtual driver**: Presents a virtual block device to the OS that proxies reads

3. **Adaptive Block Sizing**:
   - Starts with large block sizes for healthy areas
   - Automatically reduces block size on errors
   - Can be configured per-head or per-zone

4. **Multi-Phase Recovery**:
   - Phase 1: Quick pass (large blocks, skip errors)
   - Phase 2: Head analysis (identify failing heads)
   - Phase 3: Per-head recovery (skip bad heads, recover good ones)
   - Phase 4: Retry bad areas with smaller blocks
   - Phase 5: Final scrape (sector-by-sector)

5. **Virtual Driver**:
   - Creates a virtual block device (`/dev/osc0`)
   - Allows the OS to mount the image while cloning is in progress
   - Reads from the clone image for already-rescued sectors
   - Reads from the source drive for not-yet-rescued sectors
   - This enables running filesystem recovery tools on the drive while it's still being cloned

### Architecture
- **Language**: C (core), Python (GUI/HDDSuperClone)
- **Source**: OpenSuperClone on GitHub (`ISpillMyDrink/OpenSuperClone`)
- **Components**:
  - `oscsuper`: Main cloning engine (C)
  - `oscvt`: Virtual driver (C kernel module)
  - `oscviewer`: Progress log viewer
  - GUI: Python/Qt-based
- **Build**: Makefile-based, requires kernel headers for virtual driver
- **Live ISO**: Available for boot-and-recover scenarios

### Library Usability
- **NOT designed as a library**. Standalone application with GUI.
- The core cloning engine is a standalone C program
- **Integration options**:
  - Fork and extract the head-mapping algorithm
  - CLI invocation with output parsing
  - The virtual driver is a kernel module that could be used independently
  - The ATA/SCSI command layer is a valuable reusable component

### License
- **OpenSuperClone**: **GPL v2** (as stated on GitHub)
- **HDDSuperClone**: Originally proprietary (closed-source), then dual-licensed; the original HDDSuperClone has a commercial license option
- **Note**: HDDSuperClone's website still sells a "pro" version with additional features

### Limitations
- Linux-only (requires raw device access and kernel module)
- No library mode
- Requires root/sudo for raw device access
- The virtual driver requires kernel module compilation
- No Windows/macOS support
- GUI is Python/Qt-based (heavy dependency)
- No network/remote source support
- Documentation is limited (community-driven)
- The head-skipping algorithm is heuristic-based (may not work for all drives)

---

## 7. Other Relevant Tools

### 7.1 Foremost
| Attribute | Detail |
|---|---|
| **Purpose** | File carving based on headers, footers, and data structures |
| **Language** | C |
| **License** | Public Domain (original by USAF/US DoD) |
| **Architecture** | CLI tool, single-threaded, config-file-driven |
| **File formats** | ~20 formats (JPEG, GIF, PNG, BMP, AVI, EXE, RTF, ZIP, DOC, etc.) |
| **Library mode** | No |
| **Strengths** | Public domain license (no restrictions), simple config format |
| **Limitations** | Limited format support, no file validation, no fragmentation handling, no library mode |
| **Integration** | **Best license** (public domain) but limited capability; could be used as reference for clean-room reimplementation |

### 7.2 Scalpel
| Attribute | Detail |
|---|---|
| **Purpose** | Fast file carving (rewrite of Foremost) |
| **Language** | C |
| **License** | **Apache 2.0** (scalpel 2.0) / GPL v2 (scalpel 1.60) |
| **Architecture** | CLI tool, config-file-driven, GPU-enhanced version available |
| **File formats** | Configurable via `scalpel.conf` |
| **Library mode** | No |
| **Strengths** | Apache 2.0 license (commercial-friendly), fast, GPU-enhanced version, configurable |
| **Limitations** | No library mode, header-footer only (no structural validation), no fragmentation handling |
| **Integration** | **Good license** (Apache 2.0), could fork and extract carving logic; the GPU-enhanced version is notable for performance |

### 7.3 Bulk Extractor
| Attribute | Detail |
|---|---|
| **Purpose** | High-performance forensic scanner that extracts useful information without parsing filesystem |
| **Language** | C++ |
| **License** | **GPL v2** (with some modules under LGPL) |
| **Architecture** | Stream-based scanner (processes every byte), plugin architecture for feature scanners |
| **Key features** | Email extraction, credit card number detection, URL extraction, JPEG carving, GPS coordinate extraction, decompression of embedded data |
| **Library mode** | Partial (has a C API for integration, but designed for standalone use) |
| **Strengths** | Plugin architecture, stream-based (no seeking), recursive decompression, highly optimized |
| **Limitations** | GPL license, forensic-focused (not recovery-focused), heavy dependencies |
| **Integration** | The plugin architecture is interesting as a design pattern; the stream-based approach is novel |

### 7.4 RecoverJPEG
| Attribute | Detail |
|---|---|
| **Purpose** | Specialized JPEG recovery tool |
| **Language** | C |
| **License** | **BSD-style** (permissive) |
| **Library mode** | No |
| **Integration** | Permissive license, simple code, good reference for JPEG carving |

### 7.5 Magic Rescue
| Attribute | Detail |
|---|---|
| **Purpose** | File carving using "magic" file definitions and extraction rules |
| **Language** | C |
| **License** | **GPL v2** |
| **Library mode** | No |
| **Integration** | Interesting rule-based approach, but GPL license |

### 7.6 PySlice / python-ntfs / python-ext4
| Attribute | Detail |
|---|---|
| **Purpose** | Python libraries for filesystem parsing |
| **Language** | Python |
| **License** | **MIT** (typically) |
| **Library mode** | Yes (Python libraries) |
| **Strengths** | Easy to integrate, readable, well-documented, MIT license |
| **Limitations** | Slow (Python), not comprehensive, not production-grade for recovery |
| **Integration** | Good for prototyping and reference; not suitable for production performance |

### 7.7 libfsntfs / libvhdi / libvmdk (libyal)
| Attribute | Detail |
|---|---|
| **Purpose** | Individual C libraries for NTFS, VHDI, VMDK parsing |
| **Language** | C |
| **License** | **LGPL v3+** (library) / **GPL v3+** (tools) |
| **Library mode** | **Yes** (designed as libraries) |
| **Strengths** | Library-first design, per-fileystem libraries, LGPL allows commercial linking |
| **Integration** | **Excellent** for commercial integration; LGPL allows dynamic linking without GPL obligations |

### 7.8 WinHex Scripts / X-Ways Forensics
| Attribute | Detail |
|---|---|
| **Purpose** | Commercial hex editor and forensic tool with scripting |
| **License** | **Proprietary** (not open-source) |
| **Integration** | Not applicable; proprietary and closed-source |

---

## 8. Licensing Analysis

### License Summary Table

| Tool | License | Commercial Use | Linking | Source Required | Notes |
|---|---|---|---|---|---|
| TestDisk | GPL v2+ | Only if GPL | No | Yes | Cannot use in proprietary product |
| PhotoRec | GPL v2+ | Only if GPL | No | Yes | Cannot use in proprietary product |
| TSK (libtsk) | IBM CPL / CPL v1.0 | **Yes** | **Yes** | No (for library) | Library can be linked commercially |
| TSK (tools) | GPL v2+ | Only if GPL | No | Yes | CLI tools are GPL |
| Untrunc | GPL v2.0 | Only if GPL | No | Yes | Cannot use in proprietary product |
| ddrescue | GPL v2+ | Only if GPL | No | Yes | Cannot use in proprietary product |
| OpenSuperClone | GPL v2 | Only if GPL | No | Yes | Cannot use in proprietary product |
| HDDSuperClone | Dual (GPL + commercial) | Yes (with license) | Yes (with license) | No (with commercial) | Commercial license available |
| Foremost | **Public Domain** | **Yes** | **Yes** | No | No restrictions whatsoever |
| Scalpel 2.0 | **Apache 2.0** | **Yes** | **Yes** | No | Commercial-friendly, patent grant |
| Bulk Extractor | GPL v2 | Only if GPL | No | Yes | Cannot use in proprietary product |
| RecoverJPEG | **BSD-style** | **Yes** | **Yes** | No | Permissive |
| libyal (libfsntfs, etc.) | **LGPL v3+** | **Yes** | **Yes (dynamic)** | No | Dynamic linking OK; static linking requires LGPL compliance |
| python-ntfs etc. | **MIT** | **Yes** | **Yes** | No | Most permissive |

### GPL Implications for Commercial Integration

#### GPLv2
- **Cannot** be linked into proprietary software (static or dynamic)
- **Cannot** be used as a library in a commercial product without open-sourcing the entire product
- **Can** be used as a separate process (CLI invocation) via pipe/socket if the communication is at arm's length
- **Can** be distributed alongside commercial software if they are separate programs
- **Derivative works** must be GPL v2

#### GPLv3
- Same as GPLv2 but with additional anti-tivoization and patent provisions
- Stricter about "conveying" and "user product" definitions
- Explicit about dynamic linking creating a derivative work

#### LGPL v3
- **Can** be linked (dynamically) into proprietary software
- The proprietary software must allow the user to relink with a modified version of the LGPL library
- Static linking is allowed if the object files are provided for relinking
- **No** obligation to open-source the proprietary application
- Modifications to the LGPL library itself must be shared under LGPL

#### IBM CPL / CPL v1.0 (TSK)
- **OSI-approved** and generally compatible with commercial use
- Similar effect to LGPL: the library can be used in commercial products
- Requires that the library's source code (including modifications) be made available
- The application using the library is not required to be open-sourced

#### Apache 2.0
- **Commercial-friendly**: can be used, modified, and distributed in proprietary software
- Includes patent grant from contributors
- Requires attribution and license notice
- Modifications must be noted but not necessarily open-sourced

#### Public Domain
- **No restrictions**: can be used, modified, and distributed without any obligations
- No attribution required (but appreciated)
- No warranty or liability

### Strategies for Using GPL Code in a Commercial Product

1. **Process isolation**: Run GPL tools as separate processes, communicate via pipes/sockets
   - Legal gray area; the FSF considers this a "technical subterfuge" if the communication is intimate
   - More defensible if the GPL tool is a standard system utility
   - Example: Invoking `ddrescue` as a subprocess and parsing its mapfile

2. **Plugin architecture**: Design the core engine to load GPL code as optional plugins
   - Users must install GPL plugins separately
   - The core engine must be useful without the GPL plugins
   - This is the approach used by some commercial forensic tools

3. **Clean-room reimplementation**: Study the GPL code's behavior, then reimplement from scratch
   - Must be done by a developer who has not read the GPL source code
   - A separate "dirty room" team studies the code and writes specifications
   - A "clean room" team implements from specifications only
   - This is the most legally defensible approach but also the most expensive

4. **Dual licensing**: Contact the copyright holder for a commercial license
   - Some projects (e.g., HDDSuperClone) offer this
   - May be expensive or unavailable

5. **Use permissively-licensed alternatives**:
   - **Scalpel (Apache 2.0)** instead of PhotoRec for carving
   - **libyal (LGPL)** instead of TSK for filesystem parsing
   - **Foremost (Public Domain)** for basic carving
   - **libtsk (IBM CPL)** for filesystem analysis

---

## 9. Integration Feasibility

### 9.1 Language Barriers

| Tool | Language | FFI Difficulty | Notes |
|---|---|---|---|
| TestDisk | C | Easy | C is the lingua franca of FFI |
| PhotoRec | C | Easy | Same as TestDisk |
| TSK/libtsk | C | Easy | Designed as a library with C API |
| Untrunc | C++ | Moderate | C++ ABI issues; need `extern "C"` wrapper |
| ddrescue | C++ | Moderate | Same as Untrunc |
| OpenSuperClone | C | Easy | Core engine is C |
| Foremost | C | Easy | |
| Scalpel | C | Easy | |
| Bulk Extractor | C++ | Moderate | |
| libyal | C | Easy | Designed as libraries |

### 9.2 API Conflicts
- **No direct API conflicts** between tools since none are designed as libraries (except libtsk and libyal)
- **Disk access conflicts**: Multiple tools cannot safely access the same disk simultaneously
- **File format conflicts**: Different tools may produce different output formats for the same data
- **Memory model conflicts**: C tools use manual memory management; C++ tools use RAII; Python tools use GC

### 9.3 Proposed Modular Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA RECOVERY ENGINE                          │
│                   (Core Orchestrator)                            │
│                   Language: C or Rust                            │
│                   License: Proprietary / MIT                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Disk Access  │  │  Image Mgmt  │  │  Job/Queue Manager   │  │
│  │    Layer      │  │    Layer     │  │  (Progress, Resume)  │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
│         │                 │                      │               │
│  ┌──────▼───────────────▼──────────────────────▼───────────┐   │
│  │              PHYSICAL / VIRTUAL DEVICE LAYER             │   │
│  │   (unified I/O: direct device, image file, network)     │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             │                                    │
│         ┌───────────────────┼───────────────────┐               │
│         │                   │                   │               │
│  ┌──────▼──────┐  ┌────────▼───────┐  ┌────────▼───────┐      │
│  │   IMAGING   │  │  FILESYSTEM    │  │    CARVING     │      │
│  │    ENGINE   │  │    ENGINE      │  │    ENGINE      │      │
│  │             │  │                │  │                │      │
│  │ • Adaptive  │  │ • libtsk       │  │ • Scalpel      │      │
│  │   read      │  │   (IBM CPL)    │  │   (Apache 2.0) │      │
│  │ • Head map  │  │ • libyal       │  │ • Custom sigs  │      │
│  │ • Mapfile   │  │   (LGPL)       │  │ • Validation   │      │
│  │ • Resume    │  │ • Custom FS    │  │ • Fragment     │      │
│  │             │  │                │  │   handling     │      │
│  └─────────────┘  └────────────────┘  └────────────────┘      │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  PARTITION   │  │   REPAIR     │  │   OUTPUT / EXPORT    │  │
│  │  RECOVERY    │  │   ENGINE     │  │   ENGINE             │  │
│  │              │  │              │  │                      │  │
│  │ • GPT/MBR    │  │ • Untrunc    │  │ • File organization │  │
│  │   scan/fix   │  │   (video)    │  │ • Deduplication     │  │
│  │ • LVM/RAID   │  │ • MFT repair │  │ • Format conversion │  │
│  │ • Detection  │  │ • FAT repair │  │ • Report generation │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              GPL PROCESS ISOLATION LAYER                  │   │
│  │  (subprocess invocations for GPL tools: TestDisk,        │   │
│  │   PhotoRec, ddrescue, OpenSuperClone)                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 9.4 Integration Strategy by Component

#### Tier 1: Direct Library Integration (Permissive License)
These components can be directly linked into the recovery engine:

| Component | Source | License | Role |
|---|---|---|---|
| libtsk | The Sleuth Kit | IBM CPL / CPL | Filesystem parsing, file listing, metadata extraction |
| libfsntfs | libyal | LGPL v3 | NTFS-specific deep parsing |
| libvmdk | libyal | LGPL v3 | VMware disk image support |
| libvhdi | libyal | LGPL v3 | VHDX disk image support |
| Scalpel carving engine | Scalpel | Apache 2.0 | File carving (header/footer) |
| Foremost carving logic | Foremost | Public Domain | Reference carving implementation |

#### Tier 2: Process Isolation (GPL Tools)
These GPL tools are invoked as separate processes:

| Component | Source | License | Role |
|---|---|---|---|
| TestDisk | CGSecurity | GPL v2+ | Partition recovery, boot sector repair |
| PhotoRec | CGSecurity | GPL v2+ | File carving (comprehensive signatures) |
| ddrescue | GNU | GPL v2+ | Disk imaging from failing drives |
| OpenSuperClone | GitHub | GPL v2 | Advanced disk imaging with head mapping |

**Integration approach for Tier 2**:
- Each tool runs as a subprocess
- Communication via: mapfile parsing (ddrescue), output directory monitoring (PhotoRec), CLI output parsing (TestDisk)
- The core engine provides a unified API that abstracts the subprocess details
- Users can opt-in to GPL components by installing them separately

#### Tier 3: Clean-Room Reimplementation Candidates
These algorithms are valuable but trapped in GPL code:

| Algorithm | Source | Complexity | Reimplementation Effort |
|---|---|---|---|
| ddrescue adaptive algorithm | ddrescue | Medium | 2-4 weeks (well-documented) |
| Head-skipping algorithm | OpenSuperClone | High | 4-8 weeks (requires ATA knowledge) |
| PhotoRec file parsers | PhotoRec | Very High | 8-16 weeks (480+ formats) |
| MP4 moov reconstruction | Untrunc | Medium | 2-4 weeks (well-understood) |
| Partition table detection | TestDisk | Medium | 4-8 weeks (well-documented) |

#### Tier 4: Reference Implementations
These are too complex to reimplement but can inform design:

| Component | Source | Role |
|---|---|---|
| Bulk Extractor plugin architecture | Bulk Extractor | Plugin system design pattern |
| PhotoRec signature database | PhotoRec | Comprehensive file signature reference |
| OpenSuperClone virtual driver | OpenSuperClone | Live-mounting during imaging |

### 9.5 Recommended Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| Core engine | **Rust** or **C** | Memory safety (Rust) or FFI compatibility (C) |
| Filesystem parsing | **libtsk** (C) | Best-in-class, permissive license, library-first |
| Supplementary FS parsing | **libyal** (C) | LGPL, per-filesystem libraries |
| File carving | **Scalpel** (C) fork | Apache 2.0, fast, extensible |
| Disk imaging | **Clean-room ddrescue-like** | Reimplement adaptive algorithm |
| Video repair | **Clean-room untrunc-like** | Reimplement MP4 moov reconstruction |
| Partition recovery | **Clean-room** | Based on TestDisk's published algorithms |
| Advanced imaging | **OpenSuperClone** subprocess | GPL, process-isolated |
| GUI | **Qt** or **Electron** | Cross-platform |
| Plugin system | **C API** with dynamic loading | Bulk Extractor-inspired |

---

## 10. Summary & Recommendations

### Key Findings

1. **The Sleuth Kit (libtsk) is the best foundation** for a data recovery engine. It is the only tool with a proper C library API, permissive licensing (IBM CPL/CPL), and comprehensive filesystem support. It should be the core of any recovery engine.

2. **libyal libraries are the best complement** for filesystem parsing. They are LGPL-licensed, library-first, and cover NTFS, VMDK, VHDX, and other formats not fully supported by TSK.

3. **Scalpel (Apache 2.0) is the best carving engine** for commercial integration. It is fast, configurable, and permissively licensed. It lacks PhotoRec's format breadth but is extensible.

4. **GPL tools (TestDisk, PhotoRec, ddrescue, Untrunc, OpenSuperClone) cannot be directly linked** into a commercial product. They can be used as subprocesses or as references for clean-room reimplementation.

5. **The most valuable GPL algorithms to reimplement** are:
   - ddrescue's adaptive reading algorithm (well-documented, medium complexity)
   - Untrunc's MP4 moov reconstruction (well-understood, medium complexity)
   - TestDisk's partition detection (well-documented, medium complexity)

6. **The PhotoRec signature database** (480+ file formats) is extremely valuable but trapped in GPL code. A clean-room reimplementation of the signature database (as a data file, not code) may be feasible.

7. **OpenSuperClone's head-skipping algorithm** is the most valuable advanced feature but also the most complex to reimplement. It requires deep ATA/SCSI knowledge.

### Recommended Integration Roadmap

| Phase | Components | Timeline | License |
|---|---|---|---|
| **Phase 1: Core** | libtsk + libyal + Scalpel | 2-3 months | IBM CPL / LGPL / Apache 2.0 |
| **Phase 2: Imaging** | Clean-room ddrescue-like algorithm | 2-3 months | Proprietary |
| **Phase 3: Partition** | Clean-room partition recovery | 2-3 months | Proprietary |
| **Phase 4: Carving** | Extended Scalpel + custom signatures | 2-3 months | Apache 2.0 + proprietary |
| **Phase 5: Video** | Clean-room MP4 repair | 1-2 months | Proprietary |
| **Phase 6: Advanced** | GPL subprocess integration (ddrescue, PhotoRec, OSC) | 2-3 months | GPL (optional) |
| **Phase 7: Head-aware** | Clean-room head-skipping algorithm | 3-6 months | Proprietary |

### Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| GPL contamination | High | Use process isolation for GPL tools; clean-room for reimplemented algorithms |
| libtsk license complexity | Medium | Careful per-module license review; consult legal counsel |
| TSK read-only limitation | Low | Accept; recovery engine doesn't need to write to source |
| Scalpel limited format support | Medium | Invest in custom signature development |
| ddrescue algorithm complexity | Low | Well-documented; moderate reimplementation effort |
| OpenSuperClone head-skipping | High | Complex; defer to later phase; consider GPL subprocess approach |
| Performance (single-threaded) | Medium | Design for multi-threaded operation from the start |
| Cross-platform support | Medium | Use Rust for core; C libraries for FFI; abstract platform-specific I/O |

---

*End of Research Report*
