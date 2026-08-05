# RecoveryLab

File recovery tool for NTFS disk images.

> **Each version changes a benchmark.**
>
> Before starting any version, we answer one question:
> *"What benchmark number will move when we finish this version?"*
> If we can't answer in one line, the version doesn't start.

## The evidence rule

Before starting any version:

> **¿Qué evidencia nueva existirá cuando esta versión termine?**

- "20 sparse files recovered with correct SHA-256." ✅
- "10 users installed RecoveryLab without help." ✅
- "95% of compressed files recovered." ✅
- "TTFS average dropped from 6 to 2 minutes." ✅
- "There will be more code." ❌

## Two roadmaps

Technical and product roadmaps are separate. They are both important,
but they must not be mixed.

### Technical roadmap (the motor)

| Version | Benchmark target | Status |
|---------|-----------------|--------|
| v0.5.2 | NTFS normal files: 0% → 100% | Released |
| **v0.6.0** | **NTFS sparse files: 0% → 100%** | **Open** |
| v0.6.1 | NTFS compressed files: 0% → ≥95% | Release blocked (UXR-001; develop open) |
| v0.6.2 | Alternate Data Streams | Pending |
| v0.7.0 | FAT32: 0% → 100% | Pending |
| v0.8.0 | exFAT: 0% → 100% | Pending |
| v0.9.0 | ext4: 0% → 100% | Pending |

### Product roadmap (the experience)

| Step | Objective | Status |
|------|-----------|--------|
| **UXR-001** | **10 external testers: UXR + TTFS** | **Current** |
| GitHub Release | Publish v0.6.0 with wheel + sdist | Pending |
| Documentation | Docs work for strangers | Pending |
| Installation | pip install first try | Pending |
| CLI | Commands clear without source | Pending |
| GUI | Visual interface for non-CLI users | Pending |

**Rule**: v0.6.1 cannot be **released** until UXR-001 has data.
However, development is allowed in the `develop` branch — if someone wants to
contribute compressed file support, it goes there. Only releases are gated.

A version is either **Open** or **Released**. No partial progress shown publicly.

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

When you run any command, you'll see the identity banner:

```
RecoveryLab v0.6.0 / Filesystem Recovery Engine / RR 100% / Sparse 100%
```

Those benchmark numbers come from CI-verified execution, not estimates.

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

## User metrics

### UXR — User Recovery Rate

Of N people who install RecoveryLab, how many recover a file
without reading source code and without asking for help?

Binary: **¿Pudo hacerlo?** Yes or no. No opinions. No surveys.

| Metric | Result | Target |
|--------|--------|--------|
| UXR | — (UXR-001 pending) | ≥ 8/10 |
| Install success | — | 10/10 |
| Demo success | — | 10/10 |

### TTFS — Time To First Success

From opening the README to recovering the first file.

If TTFS drops from 7 minutes to 2 minutes, the product improved —
even if the motor didn't change a single line.

| Metric | Result | Target |
|--------|--------|--------|
| TTFS median | — (UXR-001 pending) | ≤ 7 min |

## Documentation

- [Installation](docs/Installation.md)
- [Quick Start](docs/QuickStart.md)
- [CLI Reference](docs/CLI.md)
- [Recovery Profiles](docs/RecoveryProfiles.md)
- [API Reference](docs/API.md)
- [Plugin Guide](docs/PluginGuide.md)

## License

MIT
