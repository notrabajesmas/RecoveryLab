# RecoveryLab

**Filesystem Recovery Engine**

Recover files. Measure recovery. Prove it.

---

RecoveryLab recovers files from NTFS disk images — normal, fragmented, deleted, and sparse. It scans, recovers, and measures every result with CI-verified metrics.

```bash
pip install recoverylab
```

```bash
recoverylab demo
```

That's it. You'll see RecoveryLab recover files immediately — no disk image needed.

## Quick Start

```bash
# See RecoveryLab in action (no disk image needed)
recoverylab demo

# Scan an NTFS image for recoverable files
recoverylab scan disk.img

# Recover all files
recoverylab recover disk.img output/

# Recover only images
recoverylab recover disk.img output/ --filter .jpg,.png

# Recover only high-confidence files
recoverylab recover disk.img output/ --min-confidence 0.8
```

## What RecoveryLab Recovers

| Capability | How | Confidence |
|-----------|-----|-----------|
| Normal NTFS files | MFT metadata | 1.0 |
| Fragmented files | Multi-run reconstruction | 1.0 |
| Deleted files | USN journal | 0.8 |
| Sparse files | Sparse run zero-fill | 0.95 |
| Carved files | Signature matching (19 formats) | 0.5–0.9 |

Not yet: compressed NTFS, FAT32, exFAT.

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

Requires Python 3.10+. Dependencies (numpy, matplotlib, Pillow, psutil) install automatically.

## Python API

```python
from core import RecoveryEngine

engine = RecoveryEngine()
result = engine.scan("disk.img")

# Browse results
for f in result.files:
    print(f.name, f.size, f.confidence, f.status.value)

# Recover all files
result.recover_all(output_dir="recovered/")

# Statistics
print(result.statistics.summary)
```

## Recovery Profiles

```bash
recoverylab scan disk.img --profile fast         # MFT only — fastest
recoverylab scan disk.img --profile balanced     # MFT + Journal
recoverylab scan disk.img --profile mft_first    # MFT → Journal → Carving (default)
recoverylab scan disk.img --profile full         # All strategies — most thorough
```

## CI-verified metrics

Tested on 80 files across 4 categories. Real CI execution, not estimates.

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

## Project philosophy

> **Evidence rule**: Before any version — "What new evidence will exist?"
> "More code" is not valid evidence.

> **Two roadmaps, never mixed**: Technical (the motor) and Product (the experience) are separate.

### Technical roadmap

| Version | Benchmark target | Status |
|---------|-----------------|--------|
| v0.5.2 | NTFS normal files: 0% → 100% | Released |
| v0.6.0 | NTFS sparse files: 0% → 100% | Released |
| v0.6.1 | NTFS compressed files: 0% → ≥95% | Release blocked (UXR-001; develop open) |
| v0.6.2 | Alternate Data Streams | Pending |
| v0.7.0 | FAT32: 0% → 100% | Pending |

### Product roadmap

| Step | Objective | Status |
|------|-----------|--------|
| UXR-001 | 10 external testers: UXR + TTFS | Current |
| GitHub Release | Publish v0.6.0 with wheel + sdist | Released |
| PyPI | `pip install recoverylab` works | Released |
| Windows .exe | Standalone binary (no Python needed) | Future |
| Documentation | Docs work for strangers | In progress |
| CLI | Commands clear without source | In progress |
| GUI | Visual interface for non-CLI users | Future |

v0.6.1 cannot be **released** until UXR-001 has data. Development is allowed in the `develop` branch.

## License

MIT
