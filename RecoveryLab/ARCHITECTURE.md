# RecoveryLab — Architecture

## How the motor works

```
Disk Image (.img)
       │
       ▼
┌─────────────────────────────────────────────┐
│              RecoveryEngine                  │
│  (core/engine.py — FROZEN API)              │
│                                             │
│  engine.scan(path) → ScanResult             │
│  result.recover(id, output_dir) → path      │
│  result.recover_all(output_dir) → paths     │
│  result.statistics → RecoveryStatistics      │
│  result.files → [RecoveredItem]             │
└──────────┬──────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────┐
│              Pipeline                        │
│  (core/pipeline.py)                         │
│                                             │
│  8 stages, executed in order:               │
│  1. Detect    — identify filesystem type     │
│  2. NTFSParse — read MFT, $J, attributes    │
│  3. Journal   — USN V2/V3/V4 entries        │
│  4. Fragment  — multi-run reconstruction     │
│  5. Carve     — signature-based carving      │
│  6. Merge     — deduplicate results          │
│  7. Score     — confidence + fidelity        │
│  8. Report    — statistics + cost            │
└──────────┬──────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────┐
│          Strategies (A–E)                    │
│  (strategies/)                              │
│                                             │
│  A. MFT         — metadata-based recovery    │
│  B. Journal     — USN journal delete detect  │
│  C. Carving     — 19 format signatures       │
│  D. Fragment    — multi-run reconstruction   │
│  E. Hybrid      — adaptive delegation        │
└──────────┬──────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────┐
│          NTFS Parser                         │
│  (ntfs_parser/parser.py)                    │
│                                             │
│  Reads: MFT, $J, data runs, sparse runs     │
│  Recovers: normal, fragmented, sparse       │
│  (compressed: not yet)                      │
└──────────┬──────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────┐
│        Recovery Judge                        │
│  (recovery_judge/)                          │
│                                             │
│  Fidelity    — byte-level comparison (RFS)   │
│  Confidence  — per-file confidence score     │
│  RVS         — recovery validity score       │
│  Metrics     — RR, RFS, RC calculation       │
└─────────────────────────────────────────────┘
```

## Directory layout

```
RecoveryLab/
├── recoverylab.py          # CLI entry point (scan/recover/info/demo)
├── config.py               # Configuration
├── core/
│   ├── engine.py           # RecoveryEngine (FROZEN API)
│   ├── pipeline.py         # 8-stage pipeline
│   ├── stages.py           # Pipeline stage implementations
│   └── result.py           # ScanResult, RecoveredItem, Statistics
├── ntfs_parser/
│   └── parser.py           # NTFS MFT, $J, data runs, sparse
├── strategies/
│   ├── strategy_a_mft.py
│   ├── strategy_b_journal.py
│   ├── strategy_c_carving.py
│   ├── strategy_d_fragment.py
│   └── strategy_e_hybrid.py
├── recovery_judge/
│   ├── fidelity.py         # RFS calculation
│   ├── confidence_registry.py
│   ├── rvs.py              # Recovery validity score
│   └── metrics.py          # RR, RFS, RC
├── dataset_builder/
│   ├── ntfs_image.py       # NTFSImageBuilder
│   ├── file_generator.py
│   └── manifest.py
├── datasets/ntfs/          # Permanent corpus (4 categories)
│   ├── normal/             # 20 files
│   ├── fragmented/         # 20 files
│   ├── deleted/            # 20 files
│   └── sparse/             # 20 files (v0.6.0)
├── scripts/
│   ├── ci_full.py          # Full CI pipeline
│   ├── ci_regression.py    # Regression check
│   └── build_corpus.py     # Corpus builder
├── tests7   ├── test_api_contract.py   # 25 API contract tests
│   └── test_carving_impeccable.py  # 19 carving tests
├── experiments/
│   └── UXR-001.7d         # UXR experiment template
├── docs/
│   ├── Installation.md
│   ├── QuickStart.md
│   ├── CLI.md
│   ├── API.md
│   ├── RecoveryProfiles.md
│   └── PluginGuide.md
├── README.md
├── PROJECT_STATUS.md
├── CHANGELOG.md
├── NEXT.md
├── ARCHITECTURE.md          # This file
├── STABILITY_POLICY.md
└── WORKLOG.md
```

## API surface (FROZEN — breaking = MAJOR bump)

```python
from core import RecoveryEngine, __version__

engine = RecoveryEngine(profile="mft_first")
result = engine.scan("disk.img")

# ScanResult
result.files          # [RecoveredItem]
result.statistics     # RecoveryStatistics
result.errors         # [str]
result.image_path     # str
result.strategy_used  # str

# RecoveredItem
f.id, f.name, f.size, f.extension
f.confidence, f.status, f.source
f.is_fragmented, f.is_recovered
f.sha256

# Recovery
result.recover(file_id, output_dir="recovered/")
result.recover_all(output_dir="recovered/")
result.get_file(file_id)
result.by_source()
result.by_status()

# Statistics
stats = result.statistics
stats.recovery_rate          # RR (0.0–1.0)
stats.fidelity_score         # RFS (0.0–1.0)
stats.quality               # Combined quality
stats.recovery_cost_score    # RC (0.0–1.0)
stats.scan_time_seconds
stats.peak_ram_mb
stats.cost                  # RecoveryCost object
stats.summary               # Human-readable string
```

## Stability tiers

| Tier | Scope | Guarantee |
|------|-------|-----------|
| 1 (Public) | `core.*` | FROZEN — breaking = MAJOR bump |
| 2 (Extension) | `RecoveryStrategy`, `PipelineStage` | STABLE — breaking = MINOR bump |
| 3 (Internal) | `motors/`, `ntfs_parser/`, `strategies/` | No guarantee — may change freely |

## Metrics system

| Metric | Measures | Range |
|--------|----------|-------|
| RR (Recovery Rate) | Did we find the file? | 0.0–1.0 |
| RFS (Recovery Fidelity Score) | How well did we recover it? | 0.0–1.0 |
| RC (Recovery Cost) | How much did it cost? | 0.0–1.0 |
| UXR (User Recovery Rate) | Could a person use it? | N/10 |
| TTFS (Time To First Success) | How fast can a person succeed? | minutes |
