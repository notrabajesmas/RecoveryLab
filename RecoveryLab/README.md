# RecoveryLab

File recovery tool for NTFS disk images.

> **Each version changes a benchmark.**
>
> Before starting any version, we answer one question:
> *"What benchmark number will move when we finish this version?"*
> If we can't answer in one line, the version doesn't start.

## Version roadmap

| Version | Benchmark target |
|---------|-----------------|
| v0.5.2 | NTFS normal files: 0% → 100% |
| **v0.6.0** | **NTFS sparse files: 0% → 100%** |
| v0.6.1 | NTFS compressed files: 0% → ≥95% |
| v0.7.0 | GUI: 0 → functional |
| v0.8.0 | FAT32: 0% → 100% |
| v0.9.0 | exFAT: 0% → 100% |
| v1.0.0 | Public release |

All benchmark numbers come from `python scripts/ci_full.py`.
No number appears in documentation unless a reproducible execution produced it.

## Install

```bash
pip install recoverylab
```

Or from source:

```bash
git clone https://github.com/notrabjesmas/RecoveryLab.git
cd RecoveryLab
pip install .
```

### Requirements

- Python 3.10+
- numpy, matplotlib, Pillow, psutil (installed automatically with pip)

## Quick Start

```bash
# See RecoveryLab in action immediately (no disk image needed)
recoverylab demo

# Scan an NTFS image for recoverable files
recoverylab scan disk.img

# Recover all files to an output directory
recoverylab recover disk.img output/

# Recover only images
recoverylab recover disk.img output/ --filter .jpg,.png

# Recover only high-confidence files
recoverylab recover disk.img output/ --min-confidence 0.8
```

## Python API

```python
from core import RecoveryEngine

engine = RecoveryEngine()
result = engine.scan("disk.img")

# Browse results
for f in result.files:
    print(f.name, f.size, f.confidence, f.status.value)

# Recover files
result.recover_all(output_dir="recovered/")

# Statistics
print(result.statistics.summary)
```

## What RecoveryLab Can Recover

| Capability | How | Confidence |
|-----------|-----|-----------|
| Normal NTFS files | MFT metadata | 1.0 |
| Fragmented files | Multi-run reconstruction | 1.0 |
| Deleted files | USN journal | 0.8 |
| Sparse files | Sparse run zero-fill | 0.95 |
| Carved files | Signature matching | 0.5–0.9 |
| Compressed NTFS files | — | Not yet |
| FAT32 / exFAT | — | Not yet |

## Recovery Profiles

```bash
recoverylab scan disk.img --profile fast         # MFT only — fastest
recoverylab scan disk.img --profile balanced     # MFT + Journal
recoverylab scan disk.img --profile mft_first    # MFT → Journal → Carving (default)
recoverylab scan disk.img --profile full         # All strategies — most thorough
```

## CI-verified metrics (v0.6.0)

These numbers come from a real CI execution on 2026-08-05.

| Category | Files | RR | RFS | Time |
|----------|------:|---:|----:|-----:|
| Normal | 20/20 | 100.0% | 0.815 | 0.53s |
| Fragmented | 20/20 | 100.0% | 0.815 | 0.50s |
| Deleted | 20/20 | 100.0% | 0.815 | 0.48s |
| Sparse | 20/20 | 100.0% | 0.850 | 0.19s |

## Documentation

- [Installation](docs/Installation.md)
- [Quick Start](docs/QuickStart.md)
- [CLI Reference](docs/CLI.md)
- [Recovery Profiles](docs/RecoveryProfiles.md)
- [API Reference](docs/API.md)
- [Plugin Guide](docs/PluginGuide.md)

## License

MIT
