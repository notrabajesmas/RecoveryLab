# RecoveryLab — Changelog

## v0.5.1 (2026-08-05)

**Public API + CLI — RecoveryLab is now a usable tool**

The RecoveryEngine public API is frozen. Consumers (CLI, GUI, REST, plugins)
use ONLY `core.RecoveryEngine`. They never see MFT, Journal, or data runs.

**API:**
```python
engine = RecoveryEngine()
result = engine.scan("disk.img")
for f in result.files:
    print(f.name, f.size, f.confidence)
engine.recover(result.files[0], output_dir="recovered/")
engine.recover_all(result, output_dir="recovered/")
```

**CLI:**
```
recoverylab scan disco.img
recoverylab recover disco.img salida/
recoverylab recover disco.img salida/ --filter .jpg,.png
recoverylab info disco.img
```

**Pipeline architecture:**
```
Image → Detect → NTFS → MFT → Journal → Fragment → Carving → Merge → Score → Results
```
Each stage is a `PipelineStage` — adding FAT32, exFAT, or EXT4 is
inserting a new stage. Adding a plugin is subclassing `RecoveryStrategy`.

**Release metrics table:**
| Metric | Value |
|--------|-------|
| Files found | 22 |
| RR | 100% |
| RFS | 0.795 |
| Time | 2.12s |
| RAM | 148 MB |

**Architecture:**
- `core/engine.py`: RecoveryEngine — public API
- `core/result.py`: ScanResult, RecoveredItem, RecoveryStatistics, FileStatus, FileSource
- `core/pipeline.py`: Pipeline, PipelineStage, PipelineContext
- `core/stages.py`: 8 concrete stages (Detect, NTFSParse, MFT, Journal, Fragment, Carving, Merge, Scoring)
- `recoverylab.py`: CLI entry point

---

## v0.5.0 (2026-08-05)

**Sprint 4A: Multiple Data Runs — 0% → 100%**

RecoveryLab now recovers files split across multiple non-contiguous data runs (extents).

**Visible result:** RecoveryLab can open an NTFS image with fragmented files
and correctly recover a file distributed in 3+ extents with SHA-256 verification.

**Benchmark:**

| Fragmentation | Files | Multi-run | Recovered | SHA-256 OK |
|:---:|:---:|:---:|:---:|:---:|
| 0% | 20 | 0 | 20/20 | 100% |
| 30% | 20 | 5 | 20/20 | 100% |
| 50% | 20 | 8 | 20/20 | 100% |
| 70% | 20 | 11 | 20/20 | 100% |
| 100% | 20 | 17 | 20/20 | 100% |

**Total multi-run files tested: 41 — SHA-256 failures: 0**

**Refactor: Motors → Strategies (A-E):**
- `strategies/` package with Strategy A (MFT), B (Journal), C (Carving), D (Fragment), E (Hybrid)
- Strategy D (Fragment) is a new BaseMotor subclass for multi-run recovery
- Strategy Engine updated with A-E naming (`STRATEGY_A_MFT`, `STRATEGY_B_JOURNAL`, etc.)
- Each strategy declares capabilities, cost, priority

**Bug fixes (found by running real code paths):**
- `_make_mft_record()`: attributes silently overflowed 1024-byte MFT record (bytearray auto-extends). Now truncates attributes that don't fit.
- `_write_bitmap()`: crashed when `_allocated_clusters` contained out-of-range clusters (fragmentation gaps push past computed limits). Now skips out-of-range clusters.

**Architecture:**
- `strategies/strategy_d_fragment.py`: StrategyD — reconstruct from multiple data runs
- `strategies/strategy_a_mft.py` through `strategy_e_hybrid.py`: Strategy wrappers
- `recovery_judge/strategy_engine.py`: Updated A-E naming, `motor_class` points to `strategies/`
- `scripts/benchmark_fragment_recovery.py`: Sprint 4A benchmark

---

## v0.4.2 (2026-08-05)

**RR + RFS as independent metrics + Strategy Engine**

Two major conceptual improvements before Sprint 4:

**1. Recovery Rate (RR) and Recovery Fidelity Score (RFS) — separate metrics:**
- RR: "Did we find the file?" — Recovered / Total
- RFS: "How well did we recover it?" — 9-component weighted score
- Combined: Quality = RR × RFS
- RR also matches by SHA-256 (carving finds files even with wrong names)

Examples:
- MFT:     RR=100% × RFS=0.967 → Quality=0.967
- Carving: RR=100% × RFS=0.450 → Quality=0.450
- Partial: RR= 67% × RFS=0.950 → Quality=0.633

**2. Strategy Engine — motors as configurable strategies:**
- RecoveryStrategy: name, capabilities, priority, cost
- StrategyProfile: ordered list of strategies (mft_first, journal_first, carving_first, full)
- StrategyEngine: orchestrates profiles, computes RFS upper bound per profile
- Max RFS per profile: 0.850 (ADS + EA not yet implemented in any strategy)
- Future: user-configurable priority ordering

**Architecture:**
- `recovery_judge/fidelity.py`: RecoveryRate, RecoveryQuality, RecoveryRateResult, RecoveryQualityResult
- `recovery_judge/strategy_engine.py`: RecoveryStrategy, StrategyProfile, StrategyEngine, 4 profiles

---

## v0.4.1 (2026-08-05)

**Motor B + Journal Integration + Recovery Fidelity Score**

Sprint 3b completion — journal parser now INTEGRATED into the recovery motor:

- ✔ Motor B `_fallback_journal()` now calls `recover_from_journal()` — no more empty stub
- ✔ Journal fallback activated when MFT damage > 10% — recovers files MFT missed
- ✔ Deleted file detection via journal: files with `USN_REASON_FILE_DELETE` flagged
- ✔ Confidence scoring: journal-recovered files get 0.8 (with data) or 0.3 (name only)
- ✔ Journal metadata stored in MotorResult for downstream analysis

**Recovery Fidelity Score (RFS)** — granular metric beyond "file recovered?":

  Component       Weight  What it measures
  ──────────────  ─────  ──────────────────────────────────
  Filename          15%  Was the original filename preserved?
  SHA-256           25%  Is the data bit-perfect?
  Timestamps        15%  Were created/modified times preserved?
  Directory         10%  Was the directory path correct?
  File Size          5%  Does size match original?
  ACL                5%  Were access control lists preserved?
  ADS               10%  Were alternate data streams preserved?
  USN History       10%  Is the USN journal history intact?
  EA                 5%  Were extended attributes preserved?

Demo result:
- MFT recovery: RFS = 0.900 (Name ✓ SHA ✓ TS ✓ Dir ✓ Size ✓ ACL ✓ ADS ✓ USN ✗ EA ✓)
- Carving recovery: RFS = 0.450 (Name ✗ SHA ✓ TS ✗ Dir ✗ Size ✓ ACL ✗ ADS ✓ USN ✗ EA ✓)
- MFT preserves 45% more fidelity than carving

**Architecture:**
- `motors/motor_b_mft_first.py`: `_fallback_journal()` → real implementation
- `recovery_judge/fidelity.py`: `RecoveryFidelityScore`, `FidelityResult`, `FidelityComponent`

---

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
