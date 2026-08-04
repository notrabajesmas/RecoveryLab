# RecoveryLab — Changelog

## v0.4 (2026-08-05)

**NTFS USN Journal Parser: 0% → 100%**

Sprint 3b — USN Journal Parser:

| Files  | Journal | Filenames | MFT Xref | Creates | Time   | RAM   |
|-------:|--------:|----------:|---------:|--------:|-------:|------:|
|    100 |   100%  |    100%   |   100%   |  100%   | 0.02s  | 0 MB  |
|    500 |   100%  |    100%   |   100%   |  100%   | 0.10s  | 1 MB  |
|  1,000 |   100%  |    100%   |   100%   |  100%   | 0.20s  | 1 MB  |
|  5,000 |   100%  |    100%   |   100%   |  100%   | 1.02s  | 6 MB  |

- ✔ USN_RECORD V2 parser (NTFS, Windows 2000+)
- ✔ USN_RECORD V3 parser (ReFS / Windows# Windows 8+)
- ✔ USN_RECORD V4 skip (range tracking, no metadata)
- ✔ 24 USN_REASON flags decoded (CREATE, DELETE, RENAME, DATA_OVERWRITE, etc.)
- ✔ MFT cross-reference (journal entry → MFT record number)
- ✔ Deleted file detection via USN_REASON_FILE_DELETE
- ✔ Historical metadata recovery (timestamps, parent directories)
- ✔ $UsnJrnl generation in NTFSImageBuilder (synthetic images now have real journal)
- ✔ 0 parse errors across all scale points

**Architecture:**
- `ntfs_parser/parser.py`: `_parse_usn_record()`, `_parse_usn_journal()`, `_read_journal_data_stream()`, `recover_from_journal()`, `USNReason` class
- `dataset_builder/ntfs_image.py`: `_build_usn_records()`, `_build_usnjrnl_entry()`, `$UsnJrnl` MFT entry with $J and $Max streams

---

## v0.3.1 (2026-08-05)

**MFT Parser Scale Benchmark: 100% SHA-256 at 10,000 files**

Sprint 3 — Scale Benchmark:

| Files   | Recovery | SHA-256 | Filenames | Timestamps | Data Runs | Time   | RAM    |
|--------:|---------:|--------:|----------:|-----------:|----------:|-------:|-------:|
|     100 |    100%  |   100%  |    100%   |    100%    |   100%    | 0.04s  |  1 MB  |
|     500 |    100%  |   100%  |    100%   |    100%    |   100%    | 0.20s  |  1 MB  |
|   1,000 |    100%  |   100%  |    100%   |    100%    |   100%    | 0.24s  |  3 MB  |
|   5,000 |    100%  |   100%  |    100%   |    100%    |   100%    | 0.86s  | 13 MB  |
|  10,000 |    100%  |   100%  |    100%   |    100%    |   100%    | 1.25s  | 27 MB  |

- ✔ 100% recovery + 100% SHA-256 across ALL scale points (100 → 10,000)
- ✔ Sub-quadratic time scaling (34.8x for 100x more files)
- ✔ Peak RAM: 27 MB at 10,000 files (linear growth)
- ✔ Throughput: ~8,000 files/sec at 10K scale

**Bug fixes:**
- Removed artificial MFT entry cap (was `min(10000, ...)` → now uncapped)
  - This caused 12 missing files at 10K scale

---

## v0.3 (2026-08-05)

**NTFS MFT Parser: 0% → 100% metadata extraction**

- ✔ MFT entry parsing (filenames, timestamps, data runs, directory structure)
- ✔ Real filenames (instead of "carved_0001.jpg")
- ✔ Directory tree reconstruction
- ✔ NTFS timestamps (created, modified, accessed)
- ✔ Data run following for non-resident files
- ✔ Resident file recovery (data embedded in MFT entry)
- ✔ Deleted file detection (MFT entries not in use)
- ✔ Fixup (Update Sequence) application for multi-sector MFT records

**Benchmarks:**
- MFT recovery: 75/75 files (100%) across 5 formats (JPEG, PNG, PDF, ZIP, DOCX)
- SHA-256 verification: 100% match
- Metadata: real filenames, 15 timestamps, 2 directory entries per image

**Bug fixes:**
- Fixed `_carve_file()` returning None for all JPEGs (dict vs bytes length check)
- Fixed MFT parser reading value_offset from wrong attribute field (offset+14 vs offset+20)

---

## v0.2 (2026-08-01)

**Recovery rate: 99.8% synthetic / 100% real JPEGs**

- ✔ PDF recovery (footer fix: `%%EOF\n`)
- ✔ JPEG recovery (3-tier structural parser: next-JPEG boundary, SOS+byte-stuffing, last-FFD9 fallback)
- ✔ PNG recovery (IEND chunk detection)
- ✔ ZIP recovery (end-of-central-directory marker)
- ✔ DOCX recovery (ZIP-based, `word/` internal path detection)
- ✔ BMP false positive eliminated (was causing 44.6% dedup cascade)

**Bug fixes:**
- Fixed `_carve_file()` returning None for all JPEGs (dict vs bytes length check)

**Benchmarks:**
- Synthetic: 724/725 files (99.9%) — 5 formats × 3 sizes
- Real JPEGs: 1000/1000 (100.00%) — 6 image modes × 5 size categories

---

## v0.1 (2026-07-30)

**Recovery rate: 54.7%**

- Initial carving motor (signature-based recovery)
- BMP false positive causing massive dedup cascade
- PDF footer mismatch causing SHA-256 failures
- JPEG truncation from first-FFD9 delimitation
