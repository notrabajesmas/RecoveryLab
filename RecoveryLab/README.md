# RecoveryLab

File recovery tool for NTFS disk images.

Recovers files from NTFS images using MFT parsing, USN journal analysis,
file carving, and multi-run fragment reconstruction — including sparse files.

## Install

```bash
pip install recoverylab
```

Or from source:

```bash
git clone https://github.com/notrabajesmas/RecoveryLab.git
cd RecoveryLab
pip install .
```

### Requirements

- Python 3.10+
- numpy, matplotlib, Pillow, psutil (installed automatically with pip)

## Quick Start

```bash
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

| Capability | Status |
|-----------|--------|
| Normal NTFS files (MFT-based) | Working |
| Fragmented files (multi-run) | Working |
| Deleted files (via USN journal) | Working |
| Sparse files (zero-hole runs) | Working |
| File carving (19 formats) | Working |
| Compressed NTFS files | Not yet |
| FAT32 / exFAT | Not yet |

## Recovery Profiles

```bash
recoverylab scan disk.img --profile fast         # MFT only — fastest
recoverylab scan disk.img --profile balanced     # MFT + Journal
recoverylab scan disk.img --profile mft_first    # MFT → Journal → Carving (default)
recoverylab scan disk.img --profile full         # All strategies — most thorough
```

## Documentation

- [Installation](docs/Installation.md)
- [Quick Start](docs/QuickStart.md)
- [CLI Reference](docs/CLI.md)
- [Recovery Profiles](docs/RecoveryProfiles.md)
- [API Reference](docs/API.md)
- [Plugin Guide](docs/PluginGuide.md)

## License

MIT
